/* AdLib music/effect engine (ADLIB.DAT 0000..059F): update 0115, detection
   00A3 and reset 003A with every routine they reach. Contracts and the stream
   grammar are specified in the header and routine comments of
   src/sound/adlib.asm; field and table offsets come from the symbol ledger
   (sound_latches_sym.h).

   Memory model. The engine owns no C state: every engine field is a byte of
   the canonical driver image at segment CS (loaded at a DOS allocation), read
   and written in original order through the optional raster bus. Offsets are
   16-bit and wrap inside the segment; a word's second byte is the next
   physical byte. DS/ES are the values actually popped after PUSH CS, and the
   physical stack (register saves, CALL return offsets, PUSH DX of 0559, the
   PUSH AX of 0381) is the live SS:SP stack. These are the original's
   observable memory effects; the x86 register file is kept only as the
   intermediate mechanism that carries them (e.g. the live DX of level
   tokens, AL from the last OPL delay read).

   Platform seam. All port traffic is the LmnOplPorts boundary (see header).
   FLAGS: TF/IF/DF are carried (no instruction changes them; DF steers the
   LODS reads of 004F, 0370 and 048B..04C6); per-instruction arithmetic flags
   are not modeled because no path reads them across an access and IRET
   replaces them. The service exits report the defined flags of their last
   flag-setting instruction. */
#include "adlib_engine.h"
#include "sound_latches.h"
#include "sound_latches_sym.h"

#ifndef ADLIB_ENGINE_MUTATION
#define ADLIB_ENGINE_MUTATION 0
#endif

enum {
    FLAG_CF=0x0001u, FLAG_PF=0x0004u, FLAG_AF=0x0010u, FLAG_ZF=0x0040u,
    FLAG_SF=0x0080u, FLAG_DF=0x0400u, FLAG_OF=0x0800u,
    FLAG_ARITHMETIC=0x08d5u
};

/* Channel record fields (9 x 14h bytes at adlib_Channels). */
enum {
    REC_NOTE=0x00, REC_COUNTDOWN=0x01, REC_INSTRUMENT=0x02,
    REC_INSTRUMENT_ID=0x04, REC_OPERATORS=0x05, REC_OPL_CHANNEL=0x07,
    REC_KEY_OFF=0x08, REC_ORDER=0x0a, REC_STREAM=0x0c, REC_LEVEL=0x0e,
    REC_CARRIER_BIAS=0x0f, REC_MODE=0x10, REC_DURATION=0x11,
    REC_TRANSPOSE=0x12, REC_SLIDE=0x13,
    RECORD_SIZE=0x14, RECORD_COUNT=9
};
/* Instrument record fields (16 bytes). */
enum {
    INS_ATTACK0=0x00, INS_ATTACK1=0x01, INS_SUSTAIN0=0x02, INS_SUSTAIN1=0x03,
    INS_CHARACTER0=0x04, INS_CHARACTER1=0x05, INS_WAVE0=0x06, INS_WAVE1=0x07,
    INS_TRANSPOSE=0x08, INS_FEEDBACK=0x09, INS_VOLUME=0x0a,
    INS_CARRIER_OFFSET=0x0b, INS_KEY_SCALE=0x0c, INS_RELEASE=0x0e
};
enum { MODE_MUSIC=1, MODE_EFFECT=2 };
/* First effect record (05FC is idle; the bank switch compares with it). */
enum { EFFECT_BANK_RECORD=ADLIB_Channels+4u*RECORD_SIZE };
/* Payload offsets are stored relative to the song directory. */
enum { PAYLOAD_BASE=ADLIB_SongDirectory };

/* Return offsets of the original CALL instructions (pushed and checked). */
enum {
    RET_RESET_STOP=0x0045, RET_RESET_PACKET=0x0053,
    RET_DETECT_1=0x00af, RET_DETECT_2=0x00b5, RET_DETECT_3=0x00bd,
    RET_DETECT_4=0x00c3, RET_DETECT_5=0x00d0, RET_DETECT_6=0x00d6,
    RET_UPDATE_SONG=0x0124, RET_UPDATE_EFFECT=0x0127,
    RET_STEP_PITCH=0x0199, RET_RELEASE=0x019c,
    RET_NOTE_KEY_OFF=0x01b0, RET_NOTE_PITCH=0x01b3, RET_KEY_OFF=0x01c7,
    RET_LEVEL_0=0x021f, RET_LEVEL_1=0x0243,
    RET_PITCH_LOW=0x038d, RET_PITCH_HIGH=0x03a7,
    RET_STOP=0x03b8, RET_RELEASE_KEY_OFF=0x03e4, RET_END=0x0441,
    RET_SONG_KEY_OFF=0x04f8, RET_SONG_01=0x0504, RET_SONG_BD=0x050a,
    RET_SONG_08=0x0510, RET_SONG_04=0x0516
};
/* SelectInstrument's eleven register writes return here, in order. */
static const uint16_t instrument_returns[11]={
    0x027f,0x028a,0x0295,0x02a0,0x02ab,0x02b6,0x02c3,0x02ce,0x02d9,
    0x0305,0x032d
};
/* UpdateService visits the records in ascending order; CALL returns. */
static const uint16_t channel_returns[RECORD_COUNT]={
    0x0131,0x0137,0x013d,0x0143,0x0149,0x014f,0x0155,0x015b,0x0161
};
/* Service IRET sites. */
enum { IRET_RESET=0x006c, IRET_DETECT_FOUND=0x00e8,
       IRET_DETECT_ABSENT=0x00ec, IRET_UPDATE=0x0176 };
/* The register/value table of the reset service holds 27 words. */
enum { RESET_PACKET_COUNT=27 };
/* Stream command dispatch: SI=03EA+2*(token-80h), JMP [SI] at 01EA. */
enum { COMMAND_DISPATCH_SITE=0x01ea, COMMAND_TABLE_END=0x03fa };

typedef struct AdlibMachine {
    uint8_t *memory;
    const LmnRasterBus *bus;
    const LmnOplPorts *ports;
    LmnRegs r;
    uint16_t status;
} AdlibMachine;

/* Stream handler outcomes: keep fetching, reached the stream RET, stopped. */
enum { FETCH_STOPPED=0, FETCH_CONTINUE=1, FETCH_DONE=2 };

#define TRY(expression) do { if(!(expression)) return 0; } while(0)

static uint8_t lo(uint16_t value) { return (uint8_t)value; }
static uint8_t hi(uint16_t value) { return (uint8_t)(value>>8); }
static uint16_t with_lo(uint16_t value,uint8_t low) {
    return (uint16_t)((value&0xff00u)|low);
}
static uint16_t with_hi(uint16_t value,uint8_t high) {
    return (uint16_t)((value&0x00ffu)|((uint16_t)high<<8));
}
static uint16_t pair(uint8_t low,uint8_t high) {
    return (uint16_t)(low|((uint16_t)high<<8));
}

/* ---- flags of the service exits ----------------------------------- */

static uint16_t parity(uint8_t value) {
    unsigned bits=0,bit;
    for(bit=0;bit<8;++bit)bits+=(value>>bit)&1u;
    return (bits&1u)?0u:FLAG_PF;
}

/* Flags of SUB/CMP before-value (8-bit). */
static uint16_t sub8_flags(uint16_t flags,uint8_t before,uint8_t value) {
    uint8_t after=(uint8_t)(before-value);
    flags=(uint16_t)((flags&~FLAG_ARITHMETIC)|parity(after));
    if(before<value)flags|=FLAG_CF;
    if((before^value^after)&0x10u)flags|=FLAG_AF;
    if(after==0)flags|=FLAG_ZF;
    if(after&0x80u)flags|=FLAG_SF;
    if(((before^value)&(before^after))&0x80u)flags|=FLAG_OF;
    return flags;
}

/* Flags of a 16-bit ADD. */
static uint16_t add16_flags(uint16_t flags,uint16_t before,uint16_t value) {
    uint16_t after=(uint16_t)(before+value);
    flags=(uint16_t)((flags&~FLAG_ARITHMETIC)|parity(lo(after)));
    if(after<before)flags|=FLAG_CF;
    if((before^value^after)&0x10u)flags|=FLAG_AF;
    if(after==0)flags|=FLAG_ZF;
    if(after&0x8000u)flags|=FLAG_SF;
    if(~(before^value)&(before^after)&0x8000u)flags|=FLAG_OF;
    return flags;
}

/* ---- canonical memory ------------------------------------------------- */

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(AdlibMachine *m,uint32_t address) {
    address&=0xfffffu;
    if(m->bus&&m->bus->read_byte)
        return m->bus->read_byte(m->bus->context,m->memory,address,m->r.flags);
    return m->memory[address];
}

static void write_physical(AdlibMachine *m,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(m->bus&&m->bus->write_byte)
        m->bus->write_byte(m->bus->context,m->memory,address,value,m->r.flags);
    else
        m->memory[address]=value;
}

static uint8_t read8(AdlibMachine *m,uint16_t segment,uint16_t offset) {
    return read_physical(m,physical(segment,offset));
}
static void write8(AdlibMachine *m,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(m,physical(segment,offset),value);
}
static uint16_t read16(AdlibMachine *m,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(m,address);
    return pair(low,read_physical(m,address+1u));
}
static void write16(AdlibMachine *m,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(m,address,lo(value));
    write_physical(m,address+1u,hi(value));
}

/* Engine data: DS (CS after the service prologue). */
static uint8_t data8(AdlibMachine *m,uint16_t offset) {
    return read8(m,m->r.ds,offset);
}
static uint16_t data16(AdlibMachine *m,uint16_t offset) {
    return read16(m,m->r.ds,offset);
}
static void set8(AdlibMachine *m,uint16_t offset,uint8_t value) {
    write8(m,m->r.ds,offset,value);
}
static void set16(AdlibMachine *m,uint16_t offset,uint16_t value) {
    write16(m,m->r.ds,offset,value);
}
/* Channel record field at DI. */
static uint8_t field8(AdlibMachine *m,unsigned field) {
    return data8(m,(uint16_t)(m->r.di+field));
}
static uint16_t field16(AdlibMachine *m,unsigned field) {
    return data16(m,(uint16_t)(m->r.di+field));
}
static void set_field8(AdlibMachine *m,unsigned field,uint8_t value) {
    set8(m,(uint16_t)(m->r.di+field),value);
}
static void set_field16(AdlibMachine *m,unsigned field,uint16_t value) {
    set16(m,(uint16_t)(m->r.di+field),value);
}

/* LODSB/LODSW at DS:SI; SI moves by the caller's DF (never changed here). */
static uint8_t lodsb(AdlibMachine *m) {
    uint8_t value=data8(m,m->r.si);
    m->r.si=(uint16_t)(m->r.si+((m->r.flags&FLAG_DF)?0xffffu:1u));
    return value;
}
static uint16_t lodsw(AdlibMachine *m) {
    uint16_t value=data16(m,m->r.si);
    m->r.si=(uint16_t)(m->r.si+((m->r.flags&FLAG_DF)?0xfffeu:2u));
    return value;
}

static void push(AdlibMachine *m,uint16_t value) {
    m->r.sp=(uint16_t)(m->r.sp-2u);
    write16(m,m->r.ss,m->r.sp,value);
}
static uint16_t pop(AdlibMachine *m) {
    uint16_t value=read16(m,m->r.ss,m->r.sp);
    m->r.sp=(uint16_t)(m->r.sp+2u);
    return value;
}

/* A near RET consumes the live stack word; it must be the CALL's offset. */
static int near_return(AdlibMachine *m,uint16_t return_offset) {
    uint16_t target=pop(m);
    if(target!=return_offset) {
        m->r.ip=target;
        m->status=LMN_ADLIB_ENGINE_RETURN_CHANGED;
        return 0;
    }
    return 1;
}

typedef int (*Routine)(AdlibMachine *);

static int call_near(AdlibMachine *m,uint16_t return_offset,Routine routine) {
    push(m,return_offset);
    TRY(routine(m));
    return near_return(m,return_offset);
}

/* ---- OPL port boundary ------------------------------------------------ */

static int port_out(AdlibMachine *m,uint16_t site,uint16_t port,uint8_t value) {
    if(!m->ports||!m->ports->out_byte) {
        m->r.ip=site;
        m->status=LMN_ADLIB_ENGINE_MISSING_PORT;
        return 0;
    }
    m->ports->out_byte(m->ports->context,m->memory,port,value,m->r.flags);
    return 1;
}

/* IN AL,DX: AL receives the port value. */
static int port_in(AdlibMachine *m,uint16_t site,uint16_t port) {
    if(!m->ports||!m->ports->in_byte) {
        m->r.ip=site;
        m->status=LMN_ADLIB_ENGINE_MISSING_PORT;
        return 0;
    }
    m->r.ax=with_lo(m->r.ax,
        m->ports->in_byte(m->ports->context,m->memory,port,m->r.flags));
    return 1;
}

/* 0559 WriteOplRegister: AL = register, AH = value. Port word [08A3] is
   reread on every call. 12 address-delay and 47 data-delay reads; AL keeps
   the last value read; DX is restored from the live stack. */
enum { ADDRESS_DELAY_READS=12, DATA_DELAY_READS=47 };
static int write_opl_register(AdlibMachine *m) {
    unsigned i;
    push(m,m->r.dx);                                    /* 0559 */
    m->r.dx=data16(m,ADLIB_OplBasePort);                /* 055A */
    TRY(port_out(m,0x055e,m->r.dx,lo(m->r.ax)));        /* 055E */
    for(i=0;i<ADDRESS_DELAY_READS;++i)                  /* 055F..056A */
        TRY(port_in(m,(uint16_t)(0x055fu+i),m->r.dx));
    m->r.ax=with_lo(m->r.ax,hi(m->r.ax));               /* 056B MOV AL,AH */
    m->r.dx=(uint16_t)(m->r.dx+1u);                     /* 056D */
    TRY(port_out(m,0x056e,m->r.dx,lo(m->r.ax)));        /* 056E */
#if ADLIB_ENGINE_MUTATION == 5
    for(i=1;i<DATA_DELAY_READS;++i)
#else
    for(i=0;i<DATA_DELAY_READS;++i)                     /* 056F..059D */
#endif
        TRY(port_in(m,(uint16_t)(0x056fu+i),m->r.dx));
    m->r.dx=pop(m);                                     /* 059E */
    return 1;                                           /* 059F RET */
}

/* CALL 0559 with AX = value:register. */
static int opl_write(AdlibMachine *m,uint16_t return_offset,uint8_t reg,
                     uint8_t value) {
    m->r.ax=pair(reg,value);
    return call_near(m,return_offset,write_opl_register);
}

/* CALL 0559 with the record's saved key-off packet +08 (MOV AX,[DI+8]). */
static int send_key_off_packet(AdlibMachine *m,uint16_t return_offset) {
    m->r.ax=field16(m,REC_KEY_OFF);
    return call_near(m,return_offset,write_opl_register);
}

/* 40h+op: Level[volume & 7F] | KSL bits from instrument +0C. The modulator
   KSL is bits 5..4 shifted left twice, the carrier KSL bits 1..0 rotated
   right twice; both are masked to bits 7..6. */
static uint8_t modulator_ksl(uint8_t key_scale) {
    return (uint8_t)(((unsigned)key_scale<<2)&0xc0u);
}
static uint8_t carrier_ksl(uint8_t key_scale) {
    uint8_t rotated=(uint8_t)((key_scale>>2)|(key_scale<<6));
    return (uint8_t)(rotated&0xc0u);
}

/* ---- channel stream --------------------------------------------------- */

static int stream_fetch(AdlibMachine *m);

/* 01B3 FinishTimedEvent: +0C := BX; countdown := duration; RET. */
static int finish_timed_event(AdlibMachine *m) {
    set_field16(m,REC_STREAM,m->r.bx);
    m->r.ax=with_lo(m->r.ax,field8(m,REC_DURATION));
    set_field8(m,REC_COUNTDOWN,lo(m->r.ax));
    return FETCH_DONE;
}

/* 0349 WriteChannelPitch (and the tail of StepChannelPitch 0339). */
static int write_channel_pitch(AdlibMachine *m) {
    uint8_t n,block,semitone,channel;
    uint16_t frequency;
    push(m,m->r.bx);                                    /* 0349 */
    push(m,m->r.si);                                    /* 034A */
    n=field8(m,REC_NOTE);                               /* 034B */
    n=(uint8_t)(n+field8(m,REC_TRANSPOSE));             /* 034F */
    n=(uint8_t)(n+4u);                                  /* 0353 */
    m->r.si=n;                                          /* 0355..0357 */
    /* n is not range checked: 0AA7+n / 0B07+n may read past both tables. */
    block=data8(m,(uint16_t)(m->r.si+ADLIB_NoteOctave));    /* 0359 */
    m->r.bx=with_lo(m->r.bx,block);
    semitone=data8(m,(uint16_t)(m->r.si+ADLIB_NoteSemitone)); /* 035D */
    /* Four byte doublings then a word doubling: selector 20h*semitone & 1FEh,
       always the first word of a 32-byte frequency row. */
    m->r.ax=(uint16_t)((uint8_t)(semitone<<4)*2u);      /* 0361..0369 */
    m->r.si=(uint16_t)(ADLIB_FrequencyTable+m->r.ax);   /* 036B..036E */
    frequency=lodsw(m);                                 /* 0370 */
    block=(uint8_t)(block-1u);                          /* 0371 */
    if(frequency&0x8000u)block=(uint8_t)(block+1u);     /* 0373..0377 */
    if(block&0x80u) {                                   /* 0379..037B */
        block=(uint8_t)(block+1u);                      /* 037D */
        frequency=(uint16_t)((frequency>>1)|(frequency&0x8000u)); /* SAR */
    }
    m->r.bx=with_lo(m->r.bx,block);
    m->r.ax=frequency;
    push(m,m->r.ax);                                    /* 0381 */
    channel=field8(m,REC_OPL_CHANNEL);                  /* 0384 */
    TRY(opl_write(m,RET_PITCH_LOW,(uint8_t)(channel+0xa0u),lo(frequency)));
    m->r.ax=pop(m);                                     /* 038D */
    block=(uint8_t)(lo(m->r.bx)*4u);                    /* 0391..0393 */
    m->r.bx=with_lo(m->r.bx,block);
    m->r.ax=with_hi(m->r.ax,(uint8_t)((hi(m->r.ax)&3u)|block));
    channel=field8(m,REC_OPL_CHANNEL);                  /* 0397 */
    m->r.ax=with_lo(m->r.ax,(uint8_t)(channel+0xb0u));
    set_field16(m,REC_KEY_OFF,m->r.ax);                 /* 039D */
    m->r.ax=with_hi(m->r.ax,(uint8_t)(hi(m->r.ax)|0x20u)); /* key on */
    TRY(call_near(m,RET_PITCH_HIGH,write_opl_register)); /* 03A4 */
    m->r.si=pop(m);                                   /* 03A7 */
    m->r.bx=pop(m);                                     /* 03A8 */
    return 1;                                           /* 03A9 RET */
}

/* 0339 StepChannelPitch: a nonzero slide changes the note and rewrites the
   pitch with key-on still set (no key-off, so the note glides). */
static int step_channel_pitch(AdlibMachine *m) {
    uint8_t slide=field8(m,REC_SLIDE);                  /* 0339 */
    m->r.ax=with_lo(m->r.ax,slide);
    if(slide==0)return 1;                               /* 033F */
    m->r.ax=with_lo(m->r.ax,(uint8_t)(slide+field8(m,REC_NOTE)));
    set_field8(m,REC_NOTE,lo(m->r.ax));                 /* 0345 */
    return write_channel_pitch(m);
}

/* 03CA ReleaseBeforeNextEvent. Instrument pointer 0000 (never selected)
   reads driver byte 000E (FEh, the DEC AH opcode) as its release point. */
static int release_before_next_event(AdlibMachine *m) {
    uint8_t release;
    if(data8(m,m->r.bx)==0x82u)return 1;                /* 03CA */
    m->r.si=field16(m,REC_INSTRUMENT);                  /* 03CF */
#if ADLIB_ENGINE_MUTATION == 11
    if(m->r.si==0)return 1;
#endif
    release=data8(m,(uint16_t)(m->r.si+INS_RELEASE));   /* 03D3 */
    m->r.ax=with_lo(m->r.ax,release);
    if(release!=field8(m,REC_COUNTDOWN))return 1;       /* 03D7 */
    TRY(send_key_off_packet(m,RET_RELEASE_KEY_OFF));    /* 03DD */
    set_field8(m,REC_SLIDE,0);                          /* 03E4 */
    return 1;
}

/* 03AA StopMusicChannels: key off and deactivate the first [B6C] records
   (LOOP: 0 means 65536), then clear ED and EE with one word write. */
static int stop_music_channels(AdlibMachine *m) {
    m->r.di=ADLIB_Channels;                             /* 03AA */
    m->r.cx=data16(m,ADLIB_MusicChannelCount);          /* 03AD */
    do {
        TRY(send_key_off_packet(m,RET_STOP));           /* 03B1 */
        set_field8(m,REC_MODE,0);                       /* 03B8 */
        m->r.di=(uint16_t)(m->r.di+RECORD_SIZE);        /* 03BD */
        m->r.cx=(uint16_t)(m->r.cx-1u);                 /* 03C1 LOOP */
    } while(m->r.cx!=0);
    set16(m,ADLIB_Command3Latch,0);                     /* 03C3: ED, EE */
    return 1;
}

/* 01C0 KeyOffTimedEvent (command 81). */
static int key_off_timed_event(AdlibMachine *m) {
    TRY(send_key_off_packet(m,RET_KEY_OFF));
    set_field8(m,REC_SLIDE,0);                          /* 01C7 */
    return finish_timed_event(m);
}

/* 0415 AdvanceOrder / 03FA RedirectOrderList / 041F EnterPattern
   (command 80). The redirect is followed once; its target is not tested. */
static int advance_order(AdlibMachine *m) {
    m->r.bx=field16(m,REC_ORDER);                       /* 0415 */
    m->r.cx=data16(m,m->r.bx);                          /* 0419 */
    m->r.bx=(uint16_t)(m->r.bx+2u);                     /* 041B..041C */
    if(m->r.cx==0) {                                    /* 041D JCXZ */
        m->r.bx=data16(m,m->r.bx);                      /* 03FA */
        m->r.bx=(uint16_t)(m->r.bx+PAYLOAD_BASE);       /* 03FC */
        m->r.cx=data16(m,m->r.bx);                      /* 0400 */
        m->r.cx=(uint16_t)(m->r.cx+PAYLOAD_BASE);       /* 0402 */
#if ADLIB_ENGINE_MUTATION != 3
        m->r.bx=(uint16_t)(m->r.bx+2u);                 /* 0406..0407 */
#endif
        set_field16(m,REC_ORDER,m->r.bx);               /* 0408 */
        set_field16(m,REC_STREAM,m->r.cx);              /* 040C */
        m->r.bx=m->r.cx;                                /* 0410 */
        return FETCH_CONTINUE;
    }
    m->r.cx=(uint16_t)(m->r.cx+PAYLOAD_BASE);           /* 041F */
    set_field16(m,REC_ORDER,m->r.bx);                   /* 0423 */
    set_field16(m,REC_STREAM,m->r.cx);                  /* 0427 */
    m->r.bx=m->r.cx;                                    /* 042B */
    return FETCH_CONTINUE;
}

/* 01F4 SetOperatorLevels (B0..BF xx). The operator offsets are the LIVE DL
   and DH: the last instrument programmed in this update, or the caller's DX
   before any. The carrier is re-sent at the instrument's own level. */
static int set_operator_levels(AdlibMachine *m) {
    uint8_t level,key_scale,carrier;
    level=data8(m,m->r.bx);                             /* 01F4 */
    m->r.bx=(uint16_t)(m->r.bx+1u);
    m->r.ax=with_lo(m->r.ax,level);
    set_field8(m,REC_LEVEL,level);                      /* 01F7 */
    push(m,m->r.bx);                                    /* 01FB */
    push(m,m->r.si);                                    /* 01FC */
#if ADLIB_ENGINE_MUTATION == 9
    m->r.dx=field16(m,REC_OPERATORS);
#endif
    m->r.si=field16(m,REC_INSTRUMENT);                  /* 01FD */
    m->r.bx=(uint16_t)(level&0x7fu);                    /* 0201..0205 */
    m->r.ax=with_hi(m->r.ax,
        data8(m,(uint16_t)(m->r.bx+ADLIB_LevelToAttenuation))); /* 0208 */
    key_scale=data8(m,(uint16_t)(m->r.si+INS_KEY_SCALE));       /* 020C */
    m->r.ax=with_hi(m->r.ax,(uint8_t)(hi(m->r.ax)|modulator_ksl(key_scale)));
    TRY(opl_write(m,RET_LEVEL_0,(uint8_t)(lo(m->r.dx)+0x40u),hi(m->r.ax)));
    carrier=field8(m,REC_CARRIER_BIAS);                 /* 021F */
    carrier=(uint8_t)(carrier+data8(m,(uint16_t)(m->r.si+INS_VOLUME)));
    m->r.bx=(uint16_t)(carrier&0x7fu);                  /* 0227..022A */
    m->r.ax=with_hi(m->r.ax,
        data8(m,(uint16_t)(m->r.bx+ADLIB_LevelToAttenuation))); /* 022C */
    key_scale=data8(m,(uint16_t)(m->r.si+INS_KEY_SCALE));       /* 0230 */
    m->r.ax=with_hi(m->r.ax,(uint8_t)(hi(m->r.ax)|carrier_ksl(key_scale)));
    TRY(opl_write(m,RET_LEVEL_1,(uint8_t)(hi(m->r.dx)+0x40u),hi(m->r.ax)));
    m->r.si=pop(m);                                     /* 0243 */
    m->r.bx=pop(m);                                     /* 0244 */
    return FETCH_CONTINUE;
}

/* 0248 SelectInstrument (C0..DF). Record = bank + 2*byte(8*(ID-1)): ID 0
   selects bank+1F0h. Bank by record address, not mode. DX := operators and
   stays loaded for the rest of the update. */
static int select_instrument(AdlibMachine *m) {
    static const struct { uint8_t field,base,use_carrier; } writes[9]={
        {INS_ATTACK0,0x60,0},{INS_ATTACK1,0x60,1},
        {INS_SUSTAIN0,0x80,0},{INS_SUSTAIN1,0x80,1},
        {INS_WAVE0,0xe0,0},{INS_WAVE1,0xe0,1},
        {INS_FEEDBACK,0xc0,2},
        {INS_CHARACTER0,0x20,0},{INS_CHARACTER1,0x20,1}
    };
    uint8_t id,volume,key_scale,carrier;
    unsigned i;
    id=(uint8_t)(lo(m->r.ax)-0xc0u);                    /* 0248 */
    push(m,m->r.bx);                                    /* 024C */
    set_field8(m,REC_INSTRUMENT_ID,id);                 /* 024D */
    m->r.ax=(uint16_t)((uint8_t)((uint8_t)(id-1u)*8u)*2u); /* 0251..025B */
    m->r.si=data16(m,ADLIB_MusicInstrumentBank);        /* 025D */
    if(m->r.di>=EFFECT_BANK_RECORD)                     /* 0261..0265 */
        m->r.si=ADLIB_EffectInstrumentBank;             /* 0267 */
    m->r.si=(uint16_t)(m->r.si+m->r.ax);                /* 026A */
    set_field16(m,REC_INSTRUMENT,m->r.si);              /* 026C */
    m->r.dx=field16(m,REC_OPERATORS);                   /* 0270 */
    for(i=0;i<9;++i) {
        unsigned w=i;
        uint8_t value,reg;
#if ADLIB_ENGINE_MUTATION == 1
        /* Mutation: waveform pair before the sustain pair. */
        if(i==2||i==3)w=i+2;
        else if(i==4||i==5)w=i-2;
#endif
        value=data8(m,(uint16_t)(m->r.si+writes[w].field));
        if(writes[w].use_carrier==2)
            reg=(uint8_t)(field8(m,REC_OPL_CHANNEL)+writes[w].base);
        else
            reg=(uint8_t)((writes[w].use_carrier?hi(m->r.dx):lo(m->r.dx))+
                          writes[w].base);
        TRY(opl_write(m,instrument_returns[i],reg,value));
    }
    m->r.ax=with_lo(m->r.ax,data8(m,(uint16_t)(m->r.si+INS_TRANSPOSE)));
    set_field8(m,REC_TRANSPOSE,lo(m->r.ax));            /* 02DD */
    volume=data8(m,(uint16_t)(m->r.si+INS_VOLUME));     /* 02E1 */
    set_field8(m,REC_LEVEL,volume);                     /* 02E5 */
    m->r.bx=(uint16_t)(volume&0x7fu);                   /* 02E9..02EB */
    m->r.ax=with_hi(m->r.ax,
        data8(m,(uint16_t)(m->r.bx+ADLIB_LevelToAttenuation))); /* 02EE */
    key_scale=data8(m,(uint16_t)(m->r.si+INS_KEY_SCALE));       /* 02F2 */
    m->r.ax=with_hi(m->r.ax,(uint8_t)(hi(m->r.ax)|modulator_ksl(key_scale)));
    TRY(opl_write(m,instrument_returns[9],(uint8_t)(lo(m->r.dx)+0x40u),
                  hi(m->r.ax)));
    carrier=data8(m,(uint16_t)(m->r.si+INS_CARRIER_OFFSET)); /* 0305 */
    set_field8(m,REC_CARRIER_BIAS,carrier);             /* 0309 */
    carrier=(uint8_t)(carrier+data8(m,(uint16_t)(m->r.si+INS_VOLUME)));
    m->r.bx=(uint16_t)(carrier&0x7fu);                  /* 0311..0314 */
    m->r.ax=with_hi(m->r.ax,
        data8(m,(uint16_t)(m->r.bx+ADLIB_LevelToAttenuation))); /* 0316 */
    key_scale=data8(m,(uint16_t)(m->r.si+INS_KEY_SCALE));       /* 031A */
    m->r.ax=with_hi(m->r.ax,(uint8_t)(hi(m->r.ax)|carrier_ksl(key_scale)));
    TRY(opl_write(m,instrument_returns[10],(uint8_t)(hi(m->r.dx)+0x40u),
                  hi(m->r.ax)));
    m->r.ax=with_lo(m->r.ax,data8(m,(uint16_t)(m->r.si+INS_TRANSPOSE)));
    set_field8(m,REC_TRANSPOSE,lo(m->r.ax));            /* 0331 again */
    m->r.bx=pop(m);                                     /* 0335 */
    return FETCH_CONTINUE;
}

/* 01E0..01EA: commands 80..AF through StreamCommandTargets. The table word
   is read live from driver memory; 88..AF would read code bytes. */
static int stream_command(AdlibMachine *m,uint8_t token) {
    uint16_t target;
    m->r.ax=(uint8_t)(token*2u);                        /* 01E0..01E2 */
    m->r.si=(uint16_t)(m->r.ax+ADLIB_StreamCommandTargets); /* 01E4..01E6 */
#if ADLIB_ENGINE_MUTATION == 8
    if(m->r.si>=COMMAND_TABLE_END)return FETCH_CONTINUE;
#endif
    if(m->r.si>=COMMAND_TABLE_END) {
        /* Characterized corrupted-control escape; no shipped data or main
           request produces it. Report instead of executing code bytes. */
        m->r.ip=COMMAND_DISPATCH_SITE;
        m->r.flags=add16_flags(m->r.flags,m->r.ax,ADLIB_StreamCommandTargets);
        m->status=LMN_ADLIB_ENGINE_STREAM_ESCAPE;
        return FETCH_STOPPED;
    }
    target=data16(m,m->r.si);                           /* 01EA JMP [SI] */
    switch(target) {
    case ADLIB_AdvanceOrder:                            /* 80 NEXT */
        return advance_order(m);
    case ADLIB_KeyOffTimedEvent:                        /* 81 OFF */
        return key_off_timed_event(m);
    case ADLIB_FinishTimedEvent:                        /* 82 HOLD */
        return finish_timed_event(m);
    case ADLIB_StopMusicChannels:                       /* 83 STOP */
        return stop_music_channels(m) ? FETCH_DONE : FETCH_STOPPED;
    case ADLIB_SetTranspose:                            /* 84 xx */
        m->r.ax=with_lo(m->r.ax,data8(m,m->r.bx));      /* 0430 */
        m->r.bx=(uint16_t)(m->r.bx+1u);
        set_field8(m,REC_TRANSPOSE,lo(m->r.ax));        /* 0433 */
        return FETCH_CONTINUE;
    case ADLIB_EndChannel:                              /* 85 END */
        if(!send_key_off_packet(m,RET_END))return FETCH_STOPPED;
        set_field8(m,REC_MODE,0);                       /* 0441 */
        return FETCH_DONE;                              /* BX not saved */
    case ADLIB_SetAscendingPitchStep:                   /* 86 */
        set_field8(m,REC_SLIDE,0x01);
        return FETCH_CONTINUE;
    case ADLIB_SetDescendingPitchStep:                  /* 87 */
        set_field8(m,REC_SLIDE,0xff);
        return FETCH_CONTINUE;
    default:
        /* A changed table word: arbitrary control transfer. */
        m->r.ip=target;
        m->status=LMN_ADLIB_ENGINE_STREAM_ESCAPE;
        return FETCH_STOPPED;
    }
}

/* 019E StreamFetch: consume control tokens until a timed event, whose RET
   (in FinishTimedEvent, EndChannel or StopMusicChannels) ends the tick. BX
   walks the stream with 16-bit wrap and no guard. */
static int stream_fetch(AdlibMachine *m) {
    for(;;) {
        uint8_t token=data8(m,m->r.bx);                 /* 019E */
        int outcome;
        m->r.bx=(uint16_t)(m->r.bx+1u);
        m->r.ax=with_lo(m->r.ax,token);
        if(token<0x80u) {                               /* note */
            set_field8(m,REC_NOTE,token);               /* 01A5 */
            TRY(send_key_off_packet(m,RET_NOTE_KEY_OFF)); /* 01A9 */
            TRY(call_near(m,RET_NOTE_PITCH,write_channel_pitch));
            outcome=finish_timed_event(m);
        } else if(token>=0xe0u) {                       /* 01EC duration */
            m->r.ax=with_lo(m->r.ax,(uint8_t)(token-0xdfu));
            set_field8(m,REC_DURATION,lo(m->r.ax));
            outcome=FETCH_CONTINUE;
        } else if(token>=0xc0u) {
            outcome=select_instrument(m);
        } else if(token>=0xb0u) {
            outcome=set_operator_levels(m);
        } else {
            outcome=stream_command(m,token);
        }
        if(outcome==FETCH_STOPPED)return 0;
        if(outcome==FETCH_DONE)return 1;
    }
}

/* 0177 AdvanceChannel: one tick of the record at DI. BX := +0C even when the
   tick is skipped. Music waits for tempo phase 0; effects run every update. */
static int advance_channel(AdlibMachine *m) {
    uint8_t countdown;
    if(field8(m,REC_MODE)==0)return 1;                  /* 0177 */
    m->r.bx=field16(m,REC_STREAM);                      /* 017E */
    if(field8(m,REC_MODE)!=MODE_EFFECT&&                /* 0182, 2nd read */
       data8(m,ADLIB_TempoPhase)!=0)                    /* 0189 */
        return 1;
    countdown=(uint8_t)(field8(m,REC_COUNTDOWN)-1u);    /* 0190 DEC */
    set_field8(m,REC_COUNTDOWN,countdown);
    if(countdown==0)return stream_fetch(m);             /* 0194 JZ */
    TRY(call_near(m,RET_STEP_PITCH,step_channel_pitch));
    return call_near(m,RET_RELEASE,release_before_next_event);
}

/* ---- request processing ---------------------------------------------- */

/* 0457 ProcessSongRequest. With EE=0, AL := ED and EF := ED. A raw EE<>0,
   EF<>0 entry would keep the caller's AL (no service leaves EF nonzero). */
static int process_song_request(AdlibMachine *m) {
    uint8_t id;
    if(data8(m,ADLIB_Command5Latch)==0) {               /* 0457 */
        m->r.ax=with_lo(m->r.ax,data8(m,ADLIB_Command3Latch));
        set8(m,ADLIB_SongRequestScratch,lo(m->r.ax));   /* 0461 */
    }
    if(data8(m,ADLIB_SongRequestScratch)==0)return 1;   /* 0464 */
    set8(m,ADLIB_Command3Latch,0);                      /* 046E */
    set8(m,ADLIB_SongRequestScratch,0);                 /* 0473 */
    id=lo(m->r.ax);
    if(id>=0x16u)return stop_music_channels(m);         /* 0478..047C */
    set8(m,ADLIB_Command5Latch,id);                     /* 047F */
    /* Header pointer: word [0B6C + 2*ID] (directory 0B6E holds ID 1). */
    m->r.ax=(uint8_t)(id*2u);                           /* 0482..0487 */
    m->r.si=(uint16_t)(ADLIB_MusicChannelCount+m->r.ax);
    m->r.ax=lodsw(m);                                   /* 048B */
    m->r.si=m->r.ax;
    m->r.ax=with_lo(m->r.ax,0);                         /* 048E */
    {   /* 0490..04A8: every record's mode, effects included. */
        unsigned record;
        for(record=0;record<RECORD_COUNT;++record)
            set8(m,(uint16_t)(ADLIB_Channels+record*RECORD_SIZE+REC_MODE),0);
    }
    m->r.ax=lodsw(m);                                   /* 04AB */
    set16(m,ADLIB_SongHeaderWord0,m->r.ax);
    m->r.ax=(uint16_t)(lodsw(m)+PAYLOAD_BASE);          /* 04AF..04B0 */
    set16(m,ADLIB_MusicInstrumentBank,m->r.ax);
    m->r.ax=with_lo(m->r.ax,lodsb(m));                  /* 04B6 */
    set8(m,ADLIB_TempoReload,lo(m->r.ax));
    m->r.ax=with_lo(m->r.ax,lodsb(m));                  /* 04BA */
    m->r.cx=lo(m->r.ax);                                /* 04BB..04BD */
    set16(m,ADLIB_MusicChannelCount,m->r.cx);           /* 04BF */
    m->r.di=ADLIB_Channels;                             /* 04C3 */
    do {        /* count unchecked: 0 loops 65536 times, >9 runs past */
        m->r.ax=(uint16_t)(lodsw(m)+PAYLOAD_BASE);      /* 04C6..04C7 */
        m->r.bx=m->r.ax;
        m->r.ax=(uint16_t)(data16(m,m->r.bx)+PAYLOAD_BASE); /* 04CC..04CE */
        m->r.bx=(uint16_t)(m->r.bx+2u);                 /* 04D1..04D2 */
        set_field16(m,REC_ORDER,m->r.bx);               /* 04D3 */
        set_field16(m,REC_STREAM,m->r.ax);              /* 04D7 */
        set_field8(m,REC_COUNTDOWN,1);                  /* 04DB */
        set_field8(m,REC_MODE,MODE_MUSIC);              /* 04E0 */
#if ADLIB_ENGINE_MUTATION == 6
        set_field16(m,REC_KEY_OFF,(uint16_t)(0xb0u+field8(m,REC_OPL_CHANNEL)));
#endif
        m->r.di=(uint16_t)(m->r.di+RECORD_SIZE);        /* 04E5 */
        m->r.cx=(uint16_t)(m->r.cx-1u);                 /* 04E9 LOOP */
    } while(m->r.cx!=0);
    /* Key off all nine records with their retained packets. */
    m->r.di=ADLIB_Channels;                             /* 04EB */
    m->r.cx=RECORD_COUNT;                               /* 04EE */
    do {
        TRY(send_key_off_packet(m,RET_SONG_KEY_OFF));   /* 04F1 */
        m->r.di=(uint16_t)(m->r.di+RECORD_SIZE);        /* 04F8 */
        m->r.cx=(uint16_t)(m->r.cx-1u);                 /* 04FC LOOP */
    } while(m->r.cx!=0);
    TRY(opl_write(m,RET_SONG_01,0x01,0x20));            /* waveform select */
    TRY(opl_write(m,RET_SONG_BD,0xbd,0xc0));            /* AM/vib depth */
    TRY(opl_write(m,RET_SONG_08,0x08,0x00));            /* CSM off */
    TRY(opl_write(m,RET_SONG_04,0x04,0x21));            /* timer reg */
    set8(m,ADLIB_TempoPhase,1);                         /* 0516 */
    return 1;
}

/* 051C ProcessEffectRequest: grant one of records 8..5 (064C down to 0610)
   whose mode is 0, then fetch the effect's first tokens immediately. */
static int process_effect_request(AdlibMachine *m) {
    uint8_t id=data8(m,ADLIB_Command4Latch);            /* 051C */
    m->r.bx=with_lo(m->r.bx,id);
    if(id==0||id>=0x13u)return 1;                       /* invalid stays */
#if ADLIB_ENGINE_MUTATION == 4
    m->r.di=(uint16_t)(ADLIB_Channels+5u*RECORD_SIZE);
#else
    m->r.di=(uint16_t)(ADLIB_Channels+8u*RECORD_SIZE);  /* 0529 */
#endif
    m->r.cx=4;                                          /* 052C */
    do {
        if(field8(m,REC_MODE)==0) {                     /* 052F */
            set8(m,ADLIB_Command4Latch,0);              /* 053D */
            set_field8(m,REC_MODE,MODE_EFFECT);         /* 0542 */
            m->r.bx=(uint16_t)((uint8_t)(id*2u)+ADLIB_EffectDirectory);
            m->r.bx=data16(m,m->r.bx);                  /* 054F */
            set_field8(m,REC_SLIDE,0);                  /* 0551 */
#if ADLIB_ENGINE_MUTATION == 7
            set_field8(m,REC_COUNTDOWN,1);
            set_field16(m,REC_STREAM,m->r.bx);
            return 1;
#else
            return stream_fetch(m);                     /* 0556 JMP */
#endif
        }
#if ADLIB_ENGINE_MUTATION == 4
        m->r.di=(uint16_t)(m->r.di+RECORD_SIZE);
#else
        m->r.di=(uint16_t)(m->r.di-RECORD_SIZE);        /* 0536 */
#endif
        m->r.cx=(uint16_t)(m->r.cx-1u);                 /* 053A LOOP */
    } while(m->r.cx!=0);
    return 1;                                           /* no stealing */
}

/* ---- services --------------------------------------------------------- */

/* PUSH CS / POP DS (and the update's second PUSH CS / POP ES) travel
   through the live stack. */
static void select_driver_segments(AdlibMachine *m,int with_es) {
    push(m,m->r.cs);
    if(with_es)push(m,m->r.cs);
    m->r.ds=pop(m);
    if(with_es)m->r.es=pop(m);
}

/* 0115 UpdateService. */
static int update_service(AdlibMachine *m) {
    unsigned record;
    uint8_t phase;
    push(m,m->r.ax); push(m,m->r.bx); push(m,m->r.cx); push(m,m->r.dx);
    push(m,m->r.di); push(m,m->r.si); push(m,m->r.ds); push(m,m->r.es);
    select_driver_segments(m,1);                        /* 011D..0120 */
    TRY(call_near(m,RET_UPDATE_SONG,process_song_request));
    TRY(call_near(m,RET_UPDATE_EFFECT,process_effect_request));
#if ADLIB_ENGINE_MUTATION == 2
    phase=data8(m,ADLIB_TempoPhase);
    if(phase==0)set8(m,ADLIB_TempoPhase,data8(m,ADLIB_TempoReload));
#endif
    phase=(uint8_t)(data8(m,ADLIB_TempoPhase)-1u);      /* 0127 DEC */
    set8(m,ADLIB_TempoPhase,phase);
    for(record=0;record<RECORD_COUNT;++record) {
        m->r.di=(uint16_t)(ADLIB_Channels+record*RECORD_SIZE);
        TRY(call_near(m,channel_returns[record],advance_channel));
    }
    phase=data8(m,ADLIB_TempoPhase);                    /* 0161 CMP */
#if ADLIB_ENGINE_MUTATION != 2
    if(phase==0) {                                      /* reload 0 = 256 */
        m->r.ax=with_lo(m->r.ax,data8(m,ADLIB_TempoReload)); /* 0168 */
        set8(m,ADLIB_TempoPhase,lo(m->r.ax));           /* 016B */
    }
#endif
    m->r.es=pop(m); m->r.ds=pop(m); m->r.si=pop(m); m->r.di=pop(m);
    m->r.dx=pop(m); m->r.cx=pop(m); m->r.bx=pop(m); m->r.ax=pop(m);
    m->r.flags=sub8_flags(m->r.flags,phase,0);
    m->r.ip=IRET_UPDATE;
    return 1;
}

/* 003A ResetService. MOV DX,0388 at 0045 is not the port (0559 loads
   [08A3]); BX, BP and ES are untouched; F0, EF, tempo and every other record
   field survive. */
static int reset_service(AdlibMachine *m) {
    unsigned packet;
    uint16_t last_di=0;
    push(m,m->r.ds); push(m,m->r.ax); push(m,m->r.di); push(m,m->r.si);
    push(m,m->r.cx); push(m,m->r.dx);
    select_driver_segments(m,0);                        /* 0040..0041 */
    TRY(call_near(m,RET_RESET_STOP,stop_music_channels));
    m->r.dx=0x0388;                                     /* 0045 */
    m->r.si=ADLIB_ResetOplPackets;                      /* 0048 LEA */
    m->r.cx=RESET_PACKET_COUNT;                         /* 004C */
    for(packet=0;packet<RESET_PACKET_COUNT;++packet) {
        m->r.ax=lodsw(m);                               /* 004F */
        TRY(call_near(m,RET_RESET_PACKET,write_opl_register));
        m->r.cx=(uint16_t)(m->r.cx-1u);                 /* 0053 LOOP */
    }
    m->r.di=ADLIB_Channels;                             /* 0055 */
    m->r.cx=RECORD_COUNT;                               /* 0058 */
    do {
        set_field8(m,REC_MODE,0);                       /* 005B */
        last_di=m->r.di;
        m->r.di=(uint16_t)(m->r.di+RECORD_SIZE);        /* 0060 */
        m->r.cx=(uint16_t)(m->r.cx-1u);                 /* 0064 LOOP */
    } while(m->r.cx!=0);
    m->r.dx=pop(m); m->r.cx=pop(m); m->r.si=pop(m); m->r.di=pop(m);
    m->r.ax=pop(m); m->r.ds=pop(m);
    m->r.flags=add16_flags(m->r.flags,last_di,RECORD_SIZE);
    m->r.ip=IRET_RESET;
    return 1;
}

/* 00A3 DetectService: OPL timer-1 test. The status reads use the literal
   port in DX (restored by every 0559 call from the live stack). */
static int detect_service(AdlibMachine *m) {
    uint8_t status1,status2;
    push(m,m->r.ds);                                    /* 00A3 */
    select_driver_segments(m,0);
    m->r.dx=0x0388;                                     /* 00A6 */
    TRY(opl_write(m,RET_DETECT_1,0x04,0x60));           /* reset timers */
    TRY(opl_write(m,RET_DETECT_2,0x04,0x80));           /* reset IRQ */
    TRY(port_in(m,0x00b5,m->r.dx));                     /* status 1 */
    push(m,m->r.ax);                                    /* 00B6 */
    TRY(opl_write(m,RET_DETECT_3,0x02,0xff));           /* timer 1 = FF */
    TRY(opl_write(m,RET_DETECT_4,0x04,0x21));           /* start timer 1 */
    m->r.cx=0;                                          /* 00C3/00C6: */
    /* MOV CX,012C; LOOP $ is a CPU-speed wait with no access. */
    TRY(port_in(m,0x00c8,m->r.dx));                     /* status 2 */
    push(m,m->r.ax);                                    /* 00C9 */
    TRY(opl_write(m,RET_DETECT_5,0x04,0x60));
    TRY(opl_write(m,RET_DETECT_6,0x04,0x80));
    m->r.ax=pop(m);                                     /* 00D6 */
    m->r.bx=pop(m);                                     /* 00D7 */
    status2=(uint8_t)(lo(m->r.ax)&0xe0u);               /* 00D8 */
    status1=(uint8_t)(lo(m->r.bx)&0xe0u);               /* 00DA */
    m->r.ax=with_lo(m->r.ax,status2);
    m->r.bx=with_lo(m->r.bx,status1);
#if ADLIB_ENGINE_MUTATION == 10
    status1=0;
#endif
    if(status1==0&&status2==0xc0u) {                    /* 00DD..00E3 */
        m->r.flags=sub8_flags(m->r.flags,status2,0xc0u);
        m->r.ax=with_lo(m->r.ax,1);                     /* 00E5 */
        m->r.ds=pop(m);
        m->r.ip=IRET_DETECT_FOUND;
        return 1;
    }
    m->r.ax=with_lo(m->r.ax,0);                         /* 00E9 XOR */
    m->r.flags=(uint16_t)((m->r.flags&~FLAG_ARITHMETIC)|FLAG_ZF|FLAG_PF);
    m->r.ds=pop(m);
    m->r.ip=IRET_DETECT_ABSENT;
    return 1;
}

uint16_t lmn_adlib_service_core(uint8_t *memory,LmnRegs *regs,
    const LmnRasterBus *bus,const LmnOplPorts *ports) {
    AdlibMachine m;
    int ok;
    m.memory=memory;
    m.bus=bus;
    m.ports=ports;
    m.r=*regs;
    m.status=LMN_ADLIB_ENGINE_IRET;
    switch(regs->ip) {
    case ADLIB_UpdateService: ok=update_service(&m); break;
    case ADLIB_DetectService: ok=detect_service(&m); break;
    case ADLIB_ResetService: ok=reset_service(&m); break;
    default: return LMN_ADLIB_ENGINE_NOT_A_SERVICE;
    }
    (void)ok;
    *regs=m.r;
    return m.status;
}

/* IRET: IP, CS, FLAGS from the live stack; FLAGS bit1 set, 3/5/15 clear. */
static void interrupt_return(uint8_t *memory,LmnRegs *regs,
                             const LmnRasterBus *bus) {
    AdlibMachine m;
    m.memory=memory;
    m.bus=bus;
    m.ports=0;
    m.r=*regs;
    m.status=LMN_ADLIB_ENGINE_IRET;
    regs->ip=pop(&m);
    regs->cs=pop(&m);
    regs->flags=(uint16_t)((pop(&m)&0x7fd5u)|2u);
    regs->sp=m.r.sp;
}

uint16_t lmn_adlib_service_adapter(uint8_t *memory,LmnRegs *regs,
    const LmnRasterBus *bus,const LmnOplPorts *ports) {
    uint16_t status=lmn_adlib_service_core(memory,regs,bus,ports);
    if(status==LMN_ADLIB_ENGINE_IRET)interrupt_return(memory,regs,bus);
    return status;
}

uint16_t lmn_adlib_int61_adapter(uint8_t *memory,LmnRegs *regs,
    const LmnRasterBus *bus,const LmnOplPorts *ports) {
    /* AH=3/4/5 and AH>=6 complete with their own IRET in sound_latches.c;
       AH=0/1/2 continue at 0115/00A3/003A with AH reduced to zero. */
    if(lmn_adlib_control_adapter(memory,regs,bus)==LMN_SOUND_CONTROL_IRET)
        return LMN_ADLIB_ENGINE_IRET;
    return lmn_adlib_service_adapter(memory,regs,bus,ports);
}

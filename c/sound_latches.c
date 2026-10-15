#include "sound_latches.h"
#include "sound_latches_sym.h"

#ifndef SOUND_LATCH_MUTATION
#define SOUND_LATCH_MUTATION 0
#endif

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(uint8_t *memory,uint32_t address,uint16_t flags,
                             const LmnRasterBus *bus) {
    address&=0xfffffu;
    if(bus&&bus->read_byte)
        return bus->read_byte(bus->context,memory,address,flags);
    return memory[address];
}

static void write_physical(uint8_t *memory,uint32_t address,uint8_t value,
                            uint16_t flags,const LmnRasterBus *bus) {
    address&=0xfffffu;
    if(bus&&bus->write_byte)
        bus->write_byte(bus->context,memory,address,value,flags);
    else
        memory[address]=value;
}

/* PUSH/POP word bytes are adjacent physical bytes, even when the offset is
   FFFFh or the first byte is at the end of the 20-bit address space. */
static void push_word(uint8_t *memory,uint16_t ss,uint16_t *sp,uint16_t value,
                      uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address;
    *sp=(uint16_t)(*sp-2u);
    address=physical(ss,*sp);
    write_physical(memory,address,(uint8_t)value,flags,bus);
    write_physical(memory,address+1u,(uint8_t)(value>>8),flags,bus);
}

static uint16_t pop_word(uint8_t *memory,uint16_t ss,uint16_t *sp,
                         uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(ss,*sp);
    uint8_t low=read_physical(memory,address,flags,bus);
    uint8_t high=read_physical(memory,address+1u,flags,bus);
    *sp=(uint16_t)(*sp+2u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static LmnSoundLatchResult latch_core(uint8_t *memory,
    const LmnSoundLatchCall *call,const LmnRasterBus *bus,
    uint16_t latch_offset) {
    uint16_t ds=call->data_segment,sp=call->stack_offset;
    uint16_t write_ds;
    uint32_t address;

    /* PUSH DS; PUSH CS; POP DS; MOV [moffs16],AL; POP DS. The two
       segment transfers deliberately travel through the caller's live stack. */
    push_word(memory,call->stack_segment,&sp,ds,call->flags,bus);
#if SOUND_LATCH_MUTATION != 3
    push_word(memory,call->stack_segment,&sp,call->driver_segment,
              call->flags,bus);
    ds=pop_word(memory,call->stack_segment,&sp,call->flags,bus);
#else
    ds=call->driver_segment;
#endif
    write_ds=ds;
#if SOUND_LATCH_MUTATION == 2
    write_ds=call->driver_segment;
#endif
#if SOUND_LATCH_MUTATION == 5
    ++latch_offset;
#endif
    address=physical(write_ds,latch_offset);
    write_physical(memory,address,(uint8_t)call->value,call->flags,bus);

    ds=pop_word(memory,call->stack_segment,&sp,call->flags,bus);
#if SOUND_LATCH_MUTATION == 1
    ds=call->data_segment;
#endif
    {
        LmnSoundLatchResult result;
        result.data_segment=ds;
        result.stack_offset=sp;
        result.flags=call->flags; /* None of these instructions changes flags. */
        return result;
    }
}

/* AdLib 0022/002A/0032 and Tandy 0019/0021/0029, respectively. */
LmnSoundLatchResult lmn_adlib_latch3_core(
    uint8_t *m,const LmnSoundLatchCall *c,const LmnRasterBus *b) {
    return latch_core(m,c,b,ADLIB_Command3Latch);
}
LmnSoundLatchResult lmn_adlib_latch4_core(
    uint8_t *m,const LmnSoundLatchCall *c,const LmnRasterBus *b) {
    return latch_core(m,c,b,ADLIB_Command4Latch);
}
LmnSoundLatchResult lmn_adlib_latch5_core(
    uint8_t *m,const LmnSoundLatchCall *c,const LmnRasterBus *b) {
    return latch_core(m,c,b,ADLIB_Command5Latch);
}
LmnSoundLatchResult lmn_tandy_latch3_core(
    uint8_t *m,const LmnSoundLatchCall *c,const LmnRasterBus *b) {
    return latch_core(m,c,b,TANDY_Command3Latch);
}
LmnSoundLatchResult lmn_tandy_latch4_core(
    uint8_t *m,const LmnSoundLatchCall *c,const LmnRasterBus *b) {
    return latch_core(m,c,b,TANDY_Command4Latch);
}
LmnSoundLatchResult lmn_tandy_latch5_core(
    uint8_t *m,const LmnSoundLatchCall *c,const LmnRasterBus *b) {
    return latch_core(m,c,b,TANDY_Command5Latch);
}

static uint16_t iret_pop(uint8_t *memory,uint16_t ss,uint16_t *sp,
                         uint16_t flags,const LmnRasterBus *bus) {
    return pop_word(memory,ss,sp,flags,bus);
}

typedef struct LmnSoundIretFrame {
    uint16_t ip,cs,flags,stack_offset;
} LmnSoundIretFrame;

/* IRET performs three distinct stack word reads, advancing the 16-bit SP
   after each one. The second byte of each word remains physically adjacent. */
static LmnSoundIretFrame read_iret_frame(uint8_t *memory,uint16_t ss,
    uint16_t stack_offset,uint16_t access_flags,const LmnRasterBus *bus) {
    LmnSoundIretFrame frame;
    frame.ip=iret_pop(memory,ss,&stack_offset,access_flags,bus);
    frame.cs=iret_pop(memory,ss,&stack_offset,access_flags,bus);
    /* The represented FLAGS word has bit1 fixed at one and bits3/5/15
       reserved at zero, including when the saved frame was overwritten. */
#if SOUND_LATCH_MUTATION == 10
    frame.flags=iret_pop(memory,ss,&stack_offset,access_flags,bus);
#else
    frame.flags=(uint16_t)((iret_pop(memory,ss,&stack_offset,access_flags,bus)
                            &0x7fd5u)|2u);
#endif
    frame.stack_offset=stack_offset;
    return frame;
}

static void apply_iret_frame(LmnRegs *regs,const LmnSoundIretFrame *frame) {
    regs->ip=frame->ip;
    regs->cs=frame->cs;
    regs->flags=frame->flags;
    regs->sp=frame->stack_offset;
}

static void latch_adapter(uint8_t *memory,LmnRegs *regs,const LmnRasterBus *bus,
    LmnSoundLatchResult (*core)(uint8_t *,const LmnSoundLatchCall *,const LmnRasterBus *)) {
    LmnSoundLatchCall call;
    LmnSoundLatchResult result;
    LmnSoundIretFrame frame;
#if SOUND_LATCH_MUTATION == 4
    frame=read_iret_frame(memory,regs->ss,regs->sp,regs->flags,bus);
#endif
    call.driver_segment=regs->cs;
    call.data_segment=regs->ds;
    call.stack_segment=regs->ss;
    call.stack_offset=regs->sp;
    call.value=(uint8_t)regs->ax;
    call.flags=regs->flags;
    result=core(memory,&call,bus);
#if SOUND_LATCH_MUTATION == 4
    frame.stack_offset=(uint16_t)(result.stack_offset+6u);
#else
    frame=read_iret_frame(memory,regs->ss,result.stack_offset,
                          result.flags,bus);
#if SOUND_LATCH_MUTATION == 6
    frame.cs=regs->cs;
    frame.flags=regs->flags;
#endif
#endif
    apply_iret_frame(regs,&frame);
    regs->ds=result.data_segment;
}

void lmn_adlib_latch3_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *b) {
    latch_adapter(m,r,b,lmn_adlib_latch3_core);
}
void lmn_adlib_latch4_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *b) {
    latch_adapter(m,r,b,lmn_adlib_latch4_core);
}
void lmn_adlib_latch5_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *b) {
    latch_adapter(m,r,b,lmn_adlib_latch5_core);
}
void lmn_tandy_latch3_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *b) {
    latch_adapter(m,r,b,lmn_tandy_latch3_core);
}
void lmn_tandy_latch4_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *b) {
    latch_adapter(m,r,b,lmn_tandy_latch4_core);
}
void lmn_tandy_latch5_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *b) {
    latch_adapter(m,r,b,lmn_tandy_latch5_core);
}

enum { SOUND_CF=0x0001, SOUND_PF=0x0004, SOUND_AF=0x0010,
       SOUND_ZF=0x0040, SOUND_SF=0x0080, SOUND_OF=0x0800 };
enum { SOUND_LOGIC_FLAGS=SOUND_CF|SOUND_PF|SOUND_AF|SOUND_ZF|SOUND_SF|SOUND_OF,
       SOUND_DEC_FLAGS=SOUND_PF|SOUND_AF|SOUND_ZF|SOUND_SF|SOUND_OF };

static uint16_t even_parity_flag(uint8_t value) {
    unsigned parity=0,bit;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    return parity ? 0u : SOUND_PF;
}

static uint16_t and_ah_flags(uint16_t flags,uint8_t value) {
    uint16_t status=even_parity_flag(value);
    flags=(uint16_t)(flags&~SOUND_LOGIC_FLAGS);
    if(value==0)status|=SOUND_ZF;
    if(value&0x80u)status|=SOUND_SF;
    /* AND defines CF/OF as zero. AF is undefined; keep the chosen value zero. */
    return (uint16_t)(flags|status);
}

static uint16_t dec_ah_flags(uint16_t flags,uint8_t before,uint8_t after) {
    uint16_t status=even_parity_flag(after);
    flags=(uint16_t)(flags&~SOUND_DEC_FLAGS); /* DEC preserves CF. */
    if((before&0x0fu)==0)status|=SOUND_AF;
    if(after==0)status|=SOUND_ZF;
    if(after&0x80u)status|=SOUND_SF;
    if(before==0x80u)status|=SOUND_OF;
    return (uint16_t)(flags|status);
}

static LmnSoundControlResult sound_control_result(uint16_t value,
    uint16_t ds,uint16_t sp,uint16_t flags,uint16_t continuation,
    uint16_t exit_kind) {
    LmnSoundControlResult result;
    result.value=value;
    result.data_segment=ds;
    result.stack_offset=sp;
    result.flags=flags;
    result.continuation=continuation;
    result.exit_kind=exit_kind;
    return result;
}

static LmnSoundControlResult sound_control_core(uint8_t *memory,
    const LmnSoundLatchCall *call,const LmnRasterBus *bus,unsigned adlib) {
    uint16_t ax=call->value,flags=call->flags;
    uint8_t entry_ah=(uint8_t)(ax>>8),ah=entry_ah;
    uint16_t continuation,reported_ax;

    /* Entry bytes 22 E4 are AND AH,AH. */
    flags=and_ah_flags(flags,ah);
    if(ah==0) {
        continuation=adlib ? ADLIB_UpdateService : TANDY_UpdateService;
        return sound_control_result(ax,call->data_segment,call->stack_offset,
            flags,continuation,LMN_SOUND_CONTROL_UNTRANSLATED);
    }

    for(unsigned step=1;step<=5;++step) {
        uint8_t before=ah;
        ah=(uint8_t)(ah-1u);
        ax=(uint16_t)((ax&0x00ffu)|((uint16_t)ah<<8));
        flags=dec_ah_flags(flags,before,ah);
#if SOUND_LATCH_MUTATION == 8
        flags=and_ah_flags(call->flags,entry_ah);
#endif
        if(ah==0) {
            reported_ax=ax;
#if SOUND_LATCH_MUTATION == 7
            reported_ax=(uint16_t)((reported_ax&0x00ffu)|
                                    ((uint16_t)entry_ah<<8));
#endif
            if(step==1) {
                continuation=adlib ? ADLIB_DetectService : TANDY_DetectService;
                return sound_control_result(reported_ax,call->data_segment,
                    call->stack_offset,flags,continuation,
                    LMN_SOUND_CONTROL_UNTRANSLATED);
            }
            if(step==2) {
                continuation=adlib ? ADLIB_ResetService : TANDY_ResetService;
                return sound_control_result(reported_ax,call->data_segment,
                    call->stack_offset,flags,continuation,
                    LMN_SOUND_CONTROL_UNTRANSLATED);
            }
            {
                LmnSoundLatchCall tail_call=*call;
                LmnSoundLatchResult tail;
                uint16_t iret_offset;
                tail_call.value=reported_ax;
                tail_call.flags=flags;
                if(step==3) {
                    if(adlib) {
                        tail=lmn_adlib_latch3_core(memory,&tail_call,bus);
                        iret_offset=ADLIB_Command3Return;
                    } else {
                        tail=lmn_tandy_latch3_core(memory,&tail_call,bus);
                        iret_offset=TANDY_Command3Return;
                    }
                } else if(step==4) {
                    if(adlib) {
                        tail=lmn_adlib_latch4_core(memory,&tail_call,bus);
                        iret_offset=ADLIB_Command4Return;
                    } else {
                        tail=lmn_tandy_latch4_core(memory,&tail_call,bus);
                        iret_offset=TANDY_Command4Return;
                    }
                } else {
                    if(adlib) {
                        tail=lmn_adlib_latch5_core(memory,&tail_call,bus);
                        iret_offset=ADLIB_Command5Return;
                    } else {
                        tail=lmn_tandy_latch5_core(memory,&tail_call,bus);
                        iret_offset=TANDY_Command5Return;
                    }
                }
                return sound_control_result(reported_ax,tail.data_segment,
                    tail.stack_offset,tail.flags,iret_offset,
                    LMN_SOUND_CONTROL_IRET);
            }
        }
    }

#if SOUND_LATCH_MUTATION == 7
    ax=(uint16_t)((ax&0x00ffu)|((uint16_t)entry_ah<<8));
#endif
#if SOUND_LATCH_MUTATION == 9
    if(entry_ah==6) {
        continuation=adlib ? ADLIB_ResetService : TANDY_ResetService;
        return sound_control_result(ax,call->data_segment,call->stack_offset,
            flags,continuation,LMN_SOUND_CONTROL_UNTRANSLATED);
    }
#endif
    continuation=adlib ? ADLIB_UnhandledCommandReturn :
                         TANDY_UnhandledCommandReturn;
    return sound_control_result(ax,call->data_segment,call->stack_offset,
        flags,continuation,LMN_SOUND_CONTROL_IRET);
}

LmnSoundControlResult lmn_adlib_control_core(uint8_t *memory,
    const LmnSoundLatchCall *call,const LmnRasterBus *bus) {
    return sound_control_core(memory,call,bus,1);
}

LmnSoundControlResult lmn_tandy_control_core(uint8_t *memory,
    const LmnSoundLatchCall *call,const LmnRasterBus *bus) {
    return sound_control_core(memory,call,bus,0);
}

static uint16_t sound_control_adapter(uint8_t *memory,LmnRegs *regs,
    const LmnRasterBus *bus,
    LmnSoundControlResult (*core)(uint8_t *,const LmnSoundLatchCall *,
                                  const LmnRasterBus *)) {
    LmnSoundLatchCall call;
    LmnSoundControlResult result;
    LmnSoundIretFrame frame;
#if SOUND_LATCH_MUTATION == 6
    uint16_t entry_cs=regs->cs,entry_flags=regs->flags;
#endif
#if SOUND_LATCH_MUTATION == 4
    /* Deliberately wrong ordering for the cached-frame mutation. */
    frame=read_iret_frame(memory,regs->ss,regs->sp,regs->flags,bus);
#endif
    call.driver_segment=regs->cs;
    call.data_segment=regs->ds;
    call.stack_segment=regs->ss;
    call.stack_offset=regs->sp;
    call.value=regs->ax;
    call.flags=regs->flags;
    result=core(memory,&call,bus);
    regs->ax=result.value;
    regs->ds=result.data_segment;
    regs->sp=result.stack_offset;
    regs->flags=result.flags;
    regs->ip=result.continuation;
    if(result.exit_kind==LMN_SOUND_CONTROL_IRET) {
#if SOUND_LATCH_MUTATION == 4
        frame.stack_offset=(uint16_t)(result.stack_offset+6u);
#else
        frame=read_iret_frame(memory,regs->ss,result.stack_offset,
                              result.flags,bus);
#if SOUND_LATCH_MUTATION == 6
        frame.cs=entry_cs;
        frame.flags=entry_flags;
#endif
#endif
        apply_iret_frame(regs,&frame);
        regs->ds=result.data_segment;
    }
    return result.exit_kind;
}

uint16_t lmn_adlib_control_adapter(uint8_t *memory,LmnRegs *regs,
    const LmnRasterBus *bus) {
    return sound_control_adapter(memory,regs,bus,lmn_adlib_control_core);
}

uint16_t lmn_tandy_control_adapter(uint8_t *memory,LmnRegs *regs,
    const LmnRasterBus *bus) {
    return sound_control_adapter(memory,regs,bus,lmn_tandy_control_core);
}

#include "entity_zero_state.h"
#include "lemmings_sym.h"

#ifndef ENTITY_ZERO_STATE_MUTATION
#define ENTITY_ZERO_STATE_MUTATION 0
#endif

enum {
    CF=0x0001u, PF=0x0004u, AF=0x0010u, ZF=0x0040u,
    SF=0x0080u, OF=0x0800u, ARITH=0x08d5u
};

typedef struct ZeroState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
    uint16_t cached_pitch;
    unsigned pitch_cached;
} ZeroState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(ZeroState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(ZeroState *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(ZeroState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(ZeroState *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* Word accesses wrap the 20-bit physical address for their high byte. */
static uint16_t read16(ZeroState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ZeroState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned parity=0,bit;
    uint16_t out=0;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&(1u<<(bits-1u)))out|=SF;
    return out;
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)(sum&mask),status=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if(sum>mask)status|=CF;
    if((left^right^value)&AF)status|=AF;
    if((~(left^right)&(left^value)&sign)!=0)status|=OF;
    return (uint16_t)((flags&~ARITH)|status);
}

static uint16_t sub_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint16_t value=(uint16_t)(((uint32_t)left-(uint32_t)right)&mask);
    uint16_t status=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if((left&mask)<(right&mask))status|=CF;
    if((left^right^value)&AF)status|=AF;
    if(((left^right)&(left^value)&sign)!=0)status|=OF;
    return (uint16_t)((flags&~ARITH)|status);
}

static uint16_t inc_flags(uint16_t flags,uint16_t value,unsigned bits) {
    uint16_t before_cf=(uint16_t)(flags&CF);
    return (uint16_t)((add_flags(flags,value,1u,bits)&~CF)|before_cf);
}

static uint16_t dec_flags(uint16_t flags,uint16_t value,unsigned bits) {
    uint16_t before_cf=(uint16_t)(flags&CF);
    return (uint16_t)((sub_flags(flags,value,1u,bits)&~CF)|before_cf);
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static uint16_t neg_flags(uint16_t flags,uint8_t operand) {
    uint8_t value=(uint8_t)(0u-operand);
    uint16_t status=szp(value,8);
    if(operand)status|=CF;
    if(operand&0x0fu)status|=AF;
    if(operand==0x80u)status|=OF;
    return (uint16_t)((flags&~ARITH)|status);
}

static uint16_t row_pitch(ZeroState *s) {
#if ENTITY_ZERO_STATE_MUTATION == 2
    if(!s->pitch_cached) {
        s->cached_pitch=read16(s,s->data_segment,
                               SEG09A9_EntityPixelRowPitchBytes);
        s->pitch_cached=1u;
    }
    return s->cached_pitch;
#else
    return read16(s,s->data_segment,SEG09A9_EntityPixelRowPitchBytes);
#endif
}

static uint8_t sample_pixel(ZeroState *s) {
    uint8_t ah=(uint8_t)(s->value>>8);
    uint8_t pixel=read8(s,s->extra_segment,s->object_cursor);
    /* MOV AL,[ES:DI] replaces the old low product byte before AND AL,AH. */
    uint8_t al=(uint8_t)(pixel&ah);
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=logic_flags(s->flags,al,8);
    return al;
}

static void add_di_pitch(ZeroState *s) {
    uint16_t entry=s->flags;
    uint16_t pitch=row_pitch(s);
    uint16_t next=(uint16_t)(s->object_cursor+pitch);
    s->flags=add_flags(entry,s->object_cursor,pitch,16);
    s->object_cursor=next;
}

static void sub_di_pitch(ZeroState *s) {
    uint16_t entry=s->flags;
    uint16_t pitch=row_pitch(s);
    uint16_t next=(uint16_t)(s->object_cursor-pitch);
    s->flags=sub_flags(entry,s->object_cursor,pitch,16);
    s->object_cursor=next;
}

static void inc_bp(ZeroState *s) {
    s->flags=inc_flags(s->flags,s->candidate_y,16);
    s->candidate_y=(uint16_t)(s->candidate_y+1u);
}

static void dec_bp(ZeroState *s) {
    s->flags=dec_flags(s->flags,s->candidate_y,16);
    s->candidate_y=(uint16_t)(s->candidate_y-1u);
}

static void or_record_word(ZeroState *s,uint16_t displacement,uint16_t mask) {
    uint16_t entry=s->flags;
    uint16_t offset=(uint16_t)(s->record_cursor+displacement);
#if ENTITY_ZERO_STATE_MUTATION == 6
    if(displacement==0x08u&&mask==0x0004u)mask=0x0008u;
#endif
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value=(uint16_t)(old|mask);
    uint16_t write_flags=entry;
#if ENTITY_ZERO_STATE_MUTATION == 7
    write_flags=logic_flags(entry,value,16);
#endif
    write16(s,s->data_segment,offset,value,write_flags);
    s->flags=logic_flags(entry,value,16);
}

static void and_record_byte(ZeroState *s,uint16_t displacement,uint8_t mask) {
    uint16_t entry=s->flags;
    uint16_t offset=(uint16_t)(s->record_cursor+displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(old&mask);
    uint16_t write_flags=entry;
#if ENTITY_ZERO_STATE_MUTATION == 7
    write_flags=logic_flags(entry,value,8);
#endif
    write8(s,s->data_segment,offset,value,write_flags);
    s->flags=logic_flags(entry,value,8);
}

static void neg_record_byte(ZeroState *s,uint16_t displacement) {
    uint16_t entry=s->flags;
    uint16_t offset=(uint16_t)(s->record_cursor+displacement);
    uint8_t old=read8(s,s->data_segment,offset);
    uint8_t value=(uint8_t)(0u-old);
    uint16_t write_flags=entry;
#if ENTITY_ZERO_STATE_MUTATION == 7
    write_flags=neg_flags(entry,old);
#endif
    write8(s,s->data_segment,offset,value,write_flags);
    s->flags=neg_flags(entry,old);
}

static void mov_record_byte(ZeroState *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+displacement),
           value,s->flags);
}

static void mov_record_word(ZeroState *s,uint16_t displacement,uint16_t value) {
    write16(s,s->data_segment,(uint16_t)(s->record_cursor+displacement),
            value,s->flags);
}

static void push_word(ZeroState *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(ZeroState *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityZeroStateResult result_of(const ZeroState *s) {
    LmnEntityZeroStateResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;out.record_cursor=s->record_cursor;
    out.object_cursor=s->object_cursor;out.candidate_y=s->candidate_y;
    out.code_segment=s->code_segment;out.data_segment=s->data_segment;
    out.extra_segment=s->extra_segment;out.stack_segment=s->stack_segment;
    out.stack_offset=s->stack_offset;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

static LmnEntityZeroStateResult finish(ZeroState *s,uint16_t entry,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=entry;
    call.value=s->value;call.map_cursor=s->map_cursor;call.count=s->count;
    call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
    call.flags=s->flags;
    out=lmn_entity_finish_core(s->memory,&call,pc_binding,sound_binding,s->bus);
    s->value=out.value;s->map_cursor=out.map_cursor;s->count=out.count;
    s->auxiliary_value=out.auxiliary_value;
    s->record_cursor=out.record_cursor;s->object_cursor=out.object_cursor;
    s->candidate_y=out.candidate_y;s->code_segment=out.code_segment;
    s->data_segment=out.data_segment;s->extra_segment=out.extra_segment;
    s->stack_segment=out.stack_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;s->status=out.status;
    return result_of(s);
}

static int signed_ge(uint16_t flags) { return (!!(flags&SF)==!!(flags&OF)); }
static int signed_lt(uint16_t flags) { return (!!(flags&SF)!=!!(flags&OF)); }

LmnEntityZeroStateResult lmn_entity_zero_state_core(uint8_t *memory,
    const LmnEntityZeroStateCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    ZeroState s;
    uint16_t entry,record_value,comparison;
    uint8_t al,old_byte;
    unsigned reverse_index;
    LmnEntityPixelCall pixel_call;
    LmnEntityPixelResult pixel;
    uint16_t actual_return;

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityZeroState;
    s.status=LMN_ENTITY_ZERO_READY;s.cached_pitch=0;s.pitch_cached=0;

    /* 2047: INC/AND the cadence byte. INC leaves CF alone; AND makes AF
       undefined, represented as zero, while defining the remaining logic bits. */
    al=read8(&s,s.data_segment,(uint16_t)(s.record_cursor+0x28u));
    al=(uint8_t)(al+1u);
    s.flags=inc_flags(s.flags,(uint8_t)(al-1u),8);
    al&=7u;
    s.flags=logic_flags(s.flags,al,8);
    mov_record_byte(&s,0x28u,al);

    /* 2051..2065: signed X bound and the shared reversal path. */
    al=read8(&s,s.data_segment,(uint16_t)(s.record_cursor+0x27u));
    s.value=(al&0x80u)?0xff00u|al:al; /* MOV AL followed by CBW. */
    entry=s.flags;
    record_value=read16(&s,s.data_segment,s.record_cursor);
    comparison=(uint16_t)(record_value+s.value);
    write16(&s,s.data_segment,s.record_cursor,comparison,entry);
    s.flags=add_flags(entry,record_value,s.value,16);
    record_value=read16(&s,s.data_segment,s.record_cursor);
    s.flags=sub_flags(s.flags,record_value,0x0010u,16);
    if(!signed_ge(s.flags))goto reverse_at_2142;
    record_value=read16(&s,s.data_segment,s.record_cursor);
    s.flags=sub_flags(s.flags,record_value,0x0680u,16);
    if(signed_lt(s.flags))goto call_pixel;
    goto reverse_at_2142;

call_pixel:
    /* 2068 CALL pushes the native return address before entering 5DC6. */
    push_word(&s,CS_EntityZeroStateAfterPixelCall);
    pixel_call.data_segment=s.data_segment;
    pixel_call.stack_segment=s.stack_segment;
    pixel_call.stack_offset=s.stack_offset;
    pixel_call.record_cursor=s.record_cursor;
    pixel_call.saved_value=s.auxiliary_value;
    pixel_call.flags=s.flags;
    pixel=lmn_prepare_entity_pixel_bus_core(memory,&pixel_call,bus);
    s.value=pixel.value;s.map_cursor=pixel.table_cursor;
    s.count=pixel.column_byte;s.object_cursor=pixel.destination_offset;
    s.auxiliary_value=pixel.restored_value;s.stack_offset=pixel.stack_offset;
    s.extra_segment=0xa000u;s.flags=pixel.flags;
    actual_return=pop_word(&s);
#if ENTITY_ZERO_STATE_MUTATION == 8
    (void)actual_return;
#else
    if(actual_return!=CS_EntityZeroStateAfterPixelCall) {
        s.continuation=actual_return;
        s.status=LMN_ENTITY_ZERO_CHANGED_PIXEL_RETURN;
        return result_of(&s);
    }
#endif
    s.continuation=CS_EntityZeroStateAfterPixelCall;

    /* MOV BP,[SI+2], then the initial masked VGA sample. */
    s.candidate_y=read16(&s,s.data_segment,(uint16_t)(s.record_cursor+2u));
    if(sample_pixel(&s))goto reverse_probe_1;

    /* Four probes at increasing DI. Each pitch operand is reread from live DS. */
    inc_bp(&s);add_di_pitch(&s);
    if(sample_pixel(&s))goto finish_20d6;
    inc_bp(&s);add_di_pitch(&s);
    if(sample_pixel(&s))goto finish_20d6;
    inc_bp(&s);add_di_pitch(&s);
    al=sample_pixel(&s);
#if ENTITY_ZERO_STATE_MUTATION != 1
    if(al)goto finish_20d6;
#endif
    inc_bp(&s);

    /* 209A..20D2: become the empty-state form, preserving store order. */
    or_record_word(&s,0x08u,0x0004u);
    mov_record_word(&s,0x0au,0x0000u);
    mov_record_word(&s,0x0cu,0x0a42u);
    mov_record_word(&s,0x10u,0x005au);
    mov_record_word(&s,0x12u,0x003cu);
    mov_record_byte(&s,0x28u,0x00u);
    mov_record_byte(&s,0x23u,0x03u);
    mov_record_word(&s,0x04u,0xfff8u);
    mov_record_word(&s,0x06u,0xfff6u);
    mov_record_byte(&s,0x29u,0x04u);
    s.value=read16(&s,s.data_segment,
                   (uint16_t)(SEG09A9_DrawingCallbackSlots+0u));
    mov_record_word(&s,0x14u,s.value);
    mov_record_byte(&s,0x2au,0x00u);
    and_record_byte(&s,0x24u,0x01u);
    return finish(&s,LMN_ENTITY_FINISH_STORE_HEIGHT_20D6,
                  pc_binding,sound_binding);

reverse_probe_1:
    /* 20E9, then six more descending probes. The first three zero branches
       enter 2148; later zero branches enter 2169 before that shared tail. */
    sub_di_pitch(&s);
    if(!sample_pixel(&s))goto finish_2148;
    for(reverse_index=0;reverse_index<6u;++reverse_index) {
        dec_bp(&s);sub_di_pitch(&s);
        al=sample_pixel(&s);
        if(!al) {
#if ENTITY_ZERO_STATE_MUTATION == 3
            if(reverse_index==5u)continue;
#endif
            if(reverse_index<2u)goto finish_2148;
            goto state_2169;
        }
    }
    old_byte=read8(&s,s.data_segment,(uint16_t)(s.record_cursor+0x24u));
    entry=s.flags;
    al=(uint8_t)(old_byte&1u);
    s.flags=logic_flags(entry,al,8); /* TEST byte [SI+24],1. */
    if(al&&(ENTITY_ZERO_STATE_MUTATION!=4))goto transition_2179;
    goto reverse_at_2142;

state_2169:
    or_record_word(&s,0x08u,0x0008u);
    mov_record_byte(&s,0x28u,0x08u);
    s.candidate_y=read16(&s,s.data_segment,(uint16_t)(s.record_cursor+2u));
    comparison=(uint16_t)(s.candidate_y-2u);
    s.flags=sub_flags(s.flags,s.candidate_y,2u,16);
    s.candidate_y=comparison;
    goto finish_2148;

finish_2148:
#if ENTITY_ZERO_STATE_MUTATION == 5
    /* The shared signed JNG is intentionally delegated; this test hook
       mutates only the candidate presented to its boundary. */
    s.candidate_y=(uint16_t)(s.candidate_y+1u);
#endif
    return finish(&s,LMN_ENTITY_FINISH_RESOLVE_HEIGHT_2148,
                  pc_binding,sound_binding);

finish_20d6:
    return finish(&s,LMN_ENTITY_FINISH_STORE_HEIGHT_20D6,
                  pc_binding,sound_binding);

reverse_at_2142:
    neg_record_byte(&s,0x27u);
    return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);

transition_2179:
    mov_record_byte(&s,0x28u,0x00u);
    mov_record_word(&s,0x0au,0x0000u);
    mov_record_word(&s,0x0cu,0x039au);
    or_record_word(&s,0x08u,0x0020u);
    mov_record_word(&s,0x10u,0x0048u);
    mov_record_word(&s,0x12u,0x0030u);
    mov_record_word(&s,0x04u,0xfff8u);
    mov_record_word(&s,0x06u,0xfff4u);
    s.value=read16(&s,s.data_segment,
                   (uint16_t)(SEG09A9_DrawingCallbackSlots+2u));
    mov_record_word(&s,0x14u,s.value);
    mov_record_byte(&s,0x2au,0xffu);
    mov_record_byte(&s,0x29u,0x08u);
    return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);
}

uint16_t lmn_entity_zero_state_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityZeroStateCall call;
    LmnEntityZeroStateResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_zero_state_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}

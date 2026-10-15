#include "entity_state8.h"
#include "lemmings_sym.h"

#ifndef ENTITY_STATE8_MUTATION
#define ENTITY_STATE8_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State8 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
    uint16_t cached_pitch;
    unsigned pitch_cached;
} State8;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State8 *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(State8 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State8 *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

#if ENTITY_STATE8_MUTATION != 6
static void write8(State8 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}
#endif

/* The second byte is the next physical byte, including 20-bit wrap. */
static uint16_t read16(State8 *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t lo=read_physical(s,address);
    uint8_t hi=read_physical(s,address+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}

static void write16(State8 *s,uint16_t segment,uint16_t offset,uint16_t value,
                    uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp(uint16_t value) {
    unsigned parity=0,bit;
    uint16_t out=0;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum,out=szp(value);
    if(sum>0xffffu)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if((~(left^right)&(left^value)&0x8000u)!=0)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t sub16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint16_t value=(uint16_t)(left-right),out=szp(value);
    if(left<right)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if(((left^right)&(left^value)&0x8000u)!=0)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc16_flags(uint16_t flags,uint16_t value) {
    uint16_t old_cf=(uint16_t)(flags&CF);
    return (uint16_t)((add16_flags(flags,value,1u)&~CF)|old_cf);
}

static uint16_t dec16_flags(uint16_t flags,uint16_t value) {
    uint16_t old_cf=(uint16_t)(flags&CF);
    return (uint16_t)((sub16_flags(flags,value,1u)&~CF)|old_cf);
}

static uint16_t logic16_flags(uint16_t flags,uint16_t value) {
    /* AND leaves AF undefined; choose zero in this declared oracle domain. */
    return (uint16_t)((flags&~ARITH)|szp(value));
}

static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    /* Logical byte operations set SF from bit 7, and AF is chosen as zero. */
    uint16_t out=(uint16_t)(flags&~ARITH);
    unsigned parity=0,bit;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&0x80u)out|=SF;
    return out;
}

static uint16_t record_offset(const State8 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint16_t record_word(State8 *s,uint16_t displacement) {
    return read16(s,s->data_segment,record_offset(s,displacement));
}

#if ENTITY_STATE8_MUTATION != 6
static void set_record_byte(State8 *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}
#endif

static void write_record_word_rmw(State8 *s,uint16_t displacement,
                                  uint16_t value,uint16_t entry_flags,
                                  uint16_t result_flags) {
    uint16_t write_flags=entry_flags;
#if ENTITY_STATE8_MUTATION == 7
    write_flags=result_flags;
#else
    (void)result_flags;
#endif
    write16(s,s->data_segment,record_offset(s,displacement),value,write_flags);
}

static void adjust_record_y(State8 *s,unsigned first_decrement) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,2u);
    uint16_t old=read16(s,s->data_segment,offset);
    uint16_t value,updated;
#if ENTITY_STATE8_MUTATION == 1
    if(first_decrement) {
        value=(uint16_t)(old+1u);
        updated=inc16_flags(entry,old);
    } else {
        value=(uint16_t)(old-1u);
        updated=dec16_flags(entry,old);
    }
#else
    (void)first_decrement;
    value=(uint16_t)(old-1u);
    updated=dec16_flags(entry,old);
#endif
    write_record_word_rmw(s,2u,value,entry,updated);
    s->flags=updated;
}

static void and_state_word(State8 *s) {
    uint16_t entry=s->flags;
    uint16_t offset=record_offset(s,8u);
    uint16_t old=read16(s,s->data_segment,offset);
#if ENTITY_STATE8_MUTATION == 5
    uint16_t value=(uint16_t)(old&0xffefu);
#else
    uint16_t value=(uint16_t)(old&0xfff7u);
#endif
    uint16_t updated=logic16_flags(entry,value);
    write_record_word_rmw(s,8u,value,entry,updated);
    s->flags=updated;
}

static void push_word(State8 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(State8 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityState8Result result_of(const State8 *s) {
    LmnEntityState8Result out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static uint16_t map_finish_status(uint16_t status) {
    switch(status) {
    case LMN_ENTITY_FINISH_RETURNED: return LMN_ENTITY_STATE8_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE8_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_STATE8_UNTRANSLATED_CHILD;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE8_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE8_CHANGED_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_STATE8_CHANGED_FINISH_CALL_RETURN;
    default: return LMN_ENTITY_STATE8_INVALID_CHILD;
    }
}

static LmnEntityState8Result finish_step(State8 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=LMN_ENTITY_FINISH_RESOLVE_HEIGHT_2148;
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
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=map_finish_status(out.status);
    return result_of(s);
}

static void subtract_live_pitch(State8 *s) {
    uint16_t entry=s->flags,pitch,old=s->object_cursor;
#if ENTITY_STATE8_MUTATION == 2
    if(!s->pitch_cached) {
        s->cached_pitch=read16(s,s->data_segment,
                               SEG09A9_EntityPixelRowPitchBytes);
        s->pitch_cached=1u;
    }
    pitch=s->cached_pitch;
#else
    pitch=read16(s,s->data_segment,SEG09A9_EntityPixelRowPitchBytes);
#endif
    s->object_cursor=(uint16_t)(old-pitch);
    s->flags=sub16_flags(entry,old,pitch);
}

static uint8_t sample_pixel(State8 *s) {
    uint8_t pixel=read8(s,s->extra_segment,s->object_cursor);
    uint8_t ah=(uint8_t)(s->value>>8),al;
#if ENTITY_STATE8_MUTATION == 3
    al=(uint8_t)((uint8_t)s->value&pixel&ah);
#else
    /* MOV AL,[ES:DI] replaces the old low byte before AND AL,AH. */
    al=(uint8_t)(pixel&ah);
#endif
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=logic8_flags(s->flags,al);
    return al;
}

static LmnEntityState8Result call_pixel(State8 *s) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult out;
    uint16_t actual_return;
    push_word(s,CS_EntityState0008AfterPixelCall);
    call.data_segment=s->data_segment;
    call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;
    call.record_cursor=s->record_cursor;
    call.saved_value=s->auxiliary_value;
    call.flags=s->flags;
    out=lmn_prepare_entity_pixel_bus_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.table_cursor;s->count=out.column_byte;
    s->object_cursor=out.destination_offset;
    s->auxiliary_value=out.restored_value;s->stack_offset=out.stack_offset;
    s->extra_segment=0xa000u;s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE8_MUTATION == 8
    (void)actual_return;
#else
    if(actual_return!=CS_EntityState0008AfterPixelCall) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE8_CHANGED_PIXEL_RETURN;
        return result_of(s);
    }
#endif
    s->continuation=CS_EntityState0008AfterPixelCall;
    s->status=LMN_ENTITY_STATE8_READY;
    return result_of(s);
}

LmnEntityState8Result lmn_entity_state8_core(uint8_t *memory,
    const LmnEntityState8Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    State8 s;
    LmnEntityState8Result child;
    uint8_t al;

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityState0008;
    s.status=LMN_ENTITY_STATE8_READY;s.cached_pitch=0;s.pitch_cached=0;

    child=call_pixel(&s);
    if(child.status!=LMN_ENTITY_STATE8_READY)return child;

    /* 23C2: memory DEC writes with entry FLAGS; DEC itself preserves CF. */
    adjust_record_y(&s,1u);
    subtract_live_pitch(&s);
    al=sample_pixel(&s);
#if ENTITY_STATE8_MUTATION == 4
    if(al)goto clear_probe;
#else
    if(!al)goto clear_probe;
#endif

    /* A nonzero first sample falls through to the second live probe. */
    adjust_record_y(&s,0u);
    subtract_live_pitch(&s);
    al=sample_pixel(&s);
    if(!al)goto clear_probe;

    /* Both samples are occupied: MOV BP,[SI+2], then direct JMP 2148. */
    s.candidate_y=record_word(&s,2u);
    return finish_step(&s,pc_binding,sound_binding);

clear_probe:
    and_state_word(&s);
#if ENTITY_STATE8_MUTATION != 6
    set_record_byte(&s,0x28u,0u);
#endif
    s.candidate_y=record_word(&s,2u);
    s.flags=inc16_flags(s.flags,s.candidate_y);
    s.candidate_y=(uint16_t)(s.candidate_y+1u);
    /* Both paths are original JMPs. No CALL frame is made for 2148. */
    return finish_step(&s,pc_binding,sound_binding);
}

uint16_t lmn_entity_state8_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityState8Call call;
    LmnEntityState8Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state8_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}

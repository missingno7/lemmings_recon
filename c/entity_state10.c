#include "entity_state10.h"
#include "lemmings_sym.h"
#include "sound_interrupt.h"

#ifndef ENTITY_STATE10_MUTATION
#define ENTITY_STATE10_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State10 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} State10;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State10 *s,uint32_t address,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,flags);
    return s->memory[address];
}

static void write_physical(State10 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State10 *s,uint16_t segment,uint16_t offset,
                     uint16_t flags) {
    return read_physical(s,physical(segment,offset),flags);
}

static void write8(State10 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

static uint16_t read16(State10 *s,uint16_t segment,uint16_t offset,
                       uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t lo=read_physical(s,address,flags);
    uint8_t hi=read_physical(s,address+1u,flags);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}

static void write16(State10 *s,uint16_t segment,uint16_t offset,uint16_t value,
                    uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned parity=0,bit;
    uint16_t out=0;
    value=(uint16_t)(value&(bits==8u?0x00ffu:0xffffu));
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&(uint16_t)(1u<<(bits-1u)))out|=SF;
    return out;
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t l=(uint32_t)(left&mask),r=(uint32_t)(right&mask);
    uint32_t sum=l+r;
    uint16_t value=(uint16_t)(sum&mask),out=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if(sum>mask)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if((~(left^right)&(left^value)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t sub_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint16_t l=(uint16_t)(left&mask),r=(uint16_t)(right&mask);
    uint16_t value=(uint16_t)(((uint32_t)l-(uint32_t)r)&mask);
    uint16_t out=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if(l<r)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if(((left^right)&(left^value)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    /* AF after AND/OR/TEST is undefined; this model clears it. */
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static uint16_t inc_flags(uint16_t flags,uint16_t before,unsigned bits) {
    uint16_t cf=(uint16_t)(flags&CF);
    return (uint16_t)((add_flags(flags,before,1u,bits)&~CF)|cf);
}

/* SHR defines CF/OF/SZP; AF is undefined and retained as an opaque bit. */
static uint16_t shr_flags(uint16_t flags,uint16_t before,unsigned bits) {
    uint16_t after=(uint16_t)(before>>1u),out=szp(after,bits);
    if(before&1u)out|=CF;
    if(before&(uint16_t)(1u<<(bits-1u)))out|=OF;
    return (uint16_t)((flags&~(ARITH&~AF))|out);
}

/* RCR DL,1 changes only CF and OF; SZP and AF remain from preceding SHR. */
#if ENTITY_STATE10_MUTATION != 4
static uint16_t rcr8_flags(uint16_t flags,uint8_t result,uint8_t new_cf) {
    uint16_t out=(uint16_t)(flags&~(CF|OF));
    if(new_cf)out|=CF;
    if((((result>>7u)^(result>>6u))&1u)!=0u)out|=OF;
    return out;
}
#endif

static uint16_t record_offset(const State10 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint8_t record_byte(State10 *s,uint16_t displacement) {
    return read8(s,s->data_segment,record_offset(s,displacement),s->flags);
}

static uint16_t record_word(State10 *s,uint16_t displacement) {
    return read16(s,s->data_segment,record_offset(s,displacement),s->flags);
}

static void set_record_byte(State10 *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static void set_record_word(State10 *s,uint16_t displacement,uint16_t value) {
    write16(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static void add_record_word(State10 *s,uint16_t displacement,uint16_t value) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset,entry);
    uint16_t updated=(uint16_t)(old+value);
    uint16_t flags=add_flags(entry,old,value,16u);
    write16(s,s->data_segment,offset,updated,entry);
    s->flags=flags;
}

static void sub_record_word(State10 *s,uint16_t displacement,uint16_t value) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset,entry);
    uint16_t updated=(uint16_t)(old-value);
    uint16_t flags=sub_flags(entry,old,value,16u);
    write16(s,s->data_segment,offset,updated,entry);
    s->flags=flags;
}

static void inc_record_word(State10 *s,uint16_t displacement) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset,entry);
    uint16_t updated=(uint16_t)(old+1u);
    uint16_t flags=inc_flags(entry,old,16u);
    write16(s,s->data_segment,offset,updated,entry);
    s->flags=flags;
}

static void and_record_word(State10 *s,uint16_t displacement,uint16_t mask) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset,entry);
    uint16_t updated=(uint16_t)(old&mask);
    uint16_t flags=logic_flags(entry,updated,16u);
    write16(s,s->data_segment,offset,updated,entry);
    s->flags=flags;
}

static void or_record_word(State10 *s,uint16_t displacement,uint16_t bits) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint16_t old=read16(s,s->data_segment,offset,entry);
    uint16_t updated=(uint16_t)(old|bits);
    uint16_t flags=logic_flags(entry,updated,16u);
    write16(s,s->data_segment,offset,updated,entry);
    s->flags=flags;
}

static void and_record_byte(State10 *s,uint16_t displacement,uint8_t mask) {
    uint16_t entry=s->flags,offset=record_offset(s,displacement);
    uint8_t old=read8(s,s->data_segment,offset,entry);
    uint8_t updated=(uint8_t)(old&mask);
    uint16_t flags=logic_flags(entry,updated,8u);
    write8(s,s->data_segment,offset,updated,entry);
    s->flags=flags;
}

static void push_word(State10 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(State10 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset,s->flags);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityState10Result result_of(const State10 *s) {
    LmnEntityState10Result out;
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
    case LMN_ENTITY_FINISH_RETURNED:return LMN_ENTITY_STATE10_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE10_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_STATE10_UNTRANSLATED_CHILD;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE10_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE10_CHANGED_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_STATE10_CHANGED_FINISH_CALL_RETURN;
    default:return LMN_ENTITY_STATE10_INVALID_CHILD;
    }
}

static LmnEntityState10Result finish(State10 *s,uint16_t entry,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=entry;call.value=s->value;call.map_cursor=s->map_cursor;
    call.count=s->count;call.auxiliary_value=s->auxiliary_value;
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

static uint16_t map_sound_status(uint16_t status) {
    switch(status) {
    case LMN_SOUND_INTERRUPT_RETURNED:return LMN_ENTITY_STATE10_READY;
    case LMN_SOUND_INTERRUPT_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE10_UNBOUND_VECTOR;
    case LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE:
        return LMN_ENTITY_STATE10_UNTRANSLATED_CHILD;
    case LMN_SOUND_INTERRUPT_CHANGED_RETURN:
        return LMN_ENTITY_STATE10_CHANGED_INTERRUPT_RETURN;
    default:return LMN_ENTITY_STATE10_INVALID_CHILD;
    }
}

static uint16_t call_sound(State10 *s,
                           const LmnSoundDriverBinding *sound_binding) {
    LmnSoundInterruptCall call;
    LmnSoundInterruptResult out;
    call.value=0x040au;call.data_segment=s->data_segment;
    call.code_segment=s->code_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.flags=s->flags;
    call.return_offset=CS_EntityState0010AfterSound;
    out=lmn_sound_interrupt61_core(s->memory,&call,sound_binding,s->bus);
    s->value=out.value;s->data_segment=out.data_segment;
    s->code_segment=out.code_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=map_sound_status(out.status);
    if(out.status==LMN_SOUND_INTERRUPT_RETURNED)
        s->continuation=CS_EntityState0010AfterSound;
    return s->status;
}

static LmnEntityState10Result call_pixel(State10 *s,uint16_t return_offset) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult out;
    uint16_t actual_return;
    push_word(s,return_offset);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.saved_value=s->auxiliary_value;call.flags=s->flags;
    out=lmn_prepare_entity_pixel_bus_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.table_cursor;
    s->count=out.column_byte;s->object_cursor=out.destination_offset;
    s->auxiliary_value=out.restored_value;s->extra_segment=0xa000u;
    s->stack_offset=out.stack_offset;s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE10_MUTATION != 6
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE10_CHANGED_PIXEL_RETURN;
        return result_of(s);
    }
#else
    (void)actual_return;
#endif
    s->continuation=return_offset;s->status=LMN_ENTITY_STATE10_READY;
    return result_of(s);
}

static LmnEntityState10Result call_exchange(State10 *s,
                                             uint16_t return_offset) {
    LmnEntityPixelExchangeResult out;
    uint16_t actual_return;
    push_word(s,return_offset);
    out=lmn_exchange_entity_pixel_bytes_core(s->memory,s->stack_segment,
        s->object_cursor,s->map_cursor,s->count,s->flags,s->bus);
    s->value=out.value;s->map_cursor=out.packed_bytes;
    s->count=out.third_byte_word;s->object_cursor=out.destination_offset;
    s->extra_segment=out.output_segment;s->auxiliary_value=out.port;
    s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE10_MUTATION != 6
    if(actual_return!=return_offset) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE10_CHANGED_EXCHANGE_RETURN;
        return result_of(s);
    }
#else
    (void)actual_return;
#endif
    s->continuation=return_offset;s->status=LMN_ENTITY_STATE10_READY;
    return result_of(s);
}

#if ENTITY_STATE10_MUTATION != 3
static uint16_t signed_less(uint16_t flags) {
    return (uint16_t)(((flags&SF)!=0u)!=((flags&OF)!=0u));
}
#endif

static void prepare_masks(State10 *s) {
    uint8_t dl;
    uint16_t n;
    s->map_cursor=0x0ff8u;
    s->auxiliary_value=(uint16_t)(s->auxiliary_value&0xff00u);
    s->flags=logic_flags(s->flags,(uint16_t)(s->count&7u),16u);
    s->count=(uint16_t)(s->count&7u);
    while(s->count!=0u) {
        s->flags=shr_flags(s->flags,s->map_cursor,16u);
        s->map_cursor=(uint16_t)(s->map_cursor>>1u);
        dl=(uint8_t)s->auxiliary_value;
#if ENTITY_STATE10_MUTATION == 4
        n=(uint16_t)(dl&1u);
        dl=(uint8_t)(dl>>1u);
        s->flags=shr_flags(s->flags,(uint16_t)(s->auxiliary_value&0xffu),8u);
        (void)n;
#else
        n=(uint16_t)(s->flags&CF);
        dl=(uint8_t)((dl>>1u)|(uint8_t)(n?0x80u:0u));
        s->flags=rcr8_flags(s->flags,dl,(uint8_t)(s->auxiliary_value&1u));
#endif
        s->auxiliary_value=(uint16_t)((s->auxiliary_value&0xff00u)|dl);
        s->count=(uint16_t)(s->count-1u); /* LOOP does not alter FLAGS. */
    }
    s->count=(uint16_t)((s->count&0xff00u)|(uint8_t)s->auxiliary_value);
}

LmnEntityState10Result lmn_entity_state10_core(uint8_t *memory,
    const LmnEntityState10Call *call,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    State10 s;
    LmnEntityState10Result child;
    uint8_t al;
    uint16_t word;
    uint32_t product;
#if ENTITY_STATE10_MUTATION == 7
    uint16_t cached_normal_x;
#endif

    s.memory=memory;s.bus=bus;s.value=call->value;
    s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityState0010;
    s.status=LMN_ENTITY_STATE10_READY;

    /* 23F3..240C: special state, then the modulo-16 cadence update. */
    al=record_byte(&s,0x28u);
#if ENTITY_STATE10_MUTATION == 1
    s.flags=sub_flags(s.flags,al,0x10u,8u);
    if(al==0x10u)goto special_path;
#else
    s.flags=sub_flags(s.flags,al,0x11u,8u);
    if(al==0x11u)goto special_path;
#endif
    al=record_byte(&s,0x28u);
    s.flags=inc_flags(s.flags,al,8u);
    al=(uint8_t)(al+1u);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.flags=logic_flags(s.flags,(uint16_t)(al&0x0fu),8u);
    al=(uint8_t)(al&0x0fu);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    set_record_byte(&s,0x28u,al);
    if(al==0u)goto normal_path;
#if ENTITY_STATE10_MUTATION != 2
    s.flags=sub_flags(s.flags,al,0x08u,8u);
    if(al==0x08u)goto normal_path;
#else
    s.flags=sub_flags(s.flags,al,0x08u,8u);
#endif
    s.continuation=CS_EntityIterationTail;
    return result_of(&s);

special_path:
    /* 250C..2522: two live stack saves surround the altered pixel sample. */
    word=record_word(&s,0u);
    push_word(&s,word);
    word=record_word(&s,2u);
    push_word(&s,word);
    s.value=record_word(&s,4u);
    add_record_word(&s,0u,s.value);
    sub_record_word(&s,2u,2u);
    child=call_pixel(&s,CS_EntityState0010AfterSpecialPixelCall);
    if(child.status!=LMN_ENTITY_STATE10_READY)return child;
    s.count=record_word(&s,0u);
    word=pop_word(&s);
    set_record_word(&s,2u,word);
    word=pop_word(&s);
    set_record_word(&s,0u,word);
    s.map_cursor=0x0ff8u;
    s.auxiliary_value=(uint16_t)(s.auxiliary_value&0xff00u);
    s.flags=logic_flags(s.flags,(uint16_t)(s.count&7u),16u);
    s.count=(uint16_t)(s.count&7u);
    while(s.count!=0u) {
        s.flags=shr_flags(s.flags,s.map_cursor,16u);
        s.map_cursor=(uint16_t)(s.map_cursor>>1u);
        al=(uint8_t)s.auxiliary_value;
#if ENTITY_STATE10_MUTATION == 4
        word=(uint16_t)(al&1u);
        al=(uint8_t)(al>>1u);
        s.flags=shr_flags(s.flags,(uint16_t)(s.auxiliary_value&0xffu),8u);
        (void)word;
#else
        word=(uint16_t)(s.flags&CF);
        al=(uint8_t)((al>>1u)|(word?0x80u:0u));
        s.flags=rcr8_flags(s.flags,al,(uint8_t)(s.auxiliary_value&1u));
#endif
        s.auxiliary_value=(uint16_t)((s.auxiliary_value&0xff00u)|al);
        s.count=(uint16_t)(s.count-1u);
    }
    s.count=(uint16_t)((s.count&0xff00u)|(uint8_t)s.auxiliary_value);
    push_word(&s,s.object_cursor);
    push_word(&s,s.count);
    push_word(&s,s.map_cursor);
    push_word(&s,s.candidate_y);
    child=call_exchange(&s,CS_EntityState0010AfterSpecialFirstExchange);
    if(child.status!=LMN_ENTITY_STATE10_READY)return child;
    s.candidate_y=pop_word(&s);
    s.map_cursor=pop_word(&s);
    s.count=pop_word(&s);
    s.object_cursor=pop_word(&s);
    word=read16(&s,s.data_segment,SEG09A9_EntityPixelRowPitchBytes,s.flags);
    s.flags=add_flags(s.flags,s.object_cursor,word,16u);
    s.object_cursor=(uint16_t)(s.object_cursor+word);
#if ENTITY_STATE10_MUTATION != 8
    child=call_exchange(&s,CS_EntityState0010AfterSpecialSecondExchange);
    if(child.status!=LMN_ENTITY_STATE10_READY)return child;
#endif
    set_record_byte(&s,0x28u,0u);
    goto normal_path; /* 254C joins 240F; it does not restart 23F3. */

normal_path:
    /* 240F..242A: move one sample, then use signed post-increment Y. */
    s.candidate_y=record_word(&s,0u);
    s.value=record_word(&s,4u);
    add_record_word(&s,0u,s.value);
    word=record_word(&s,0u);
#if ENTITY_STATE10_MUTATION == 7
    cached_normal_x=word;
#endif
    push_word(&s,word);
    child=call_pixel(&s,CS_EntityState0010AfterFirstPixelCall);
    if(child.status!=LMN_ENTITY_STATE10_READY)return child;
    set_record_word(&s,0u,s.candidate_y);
    inc_record_word(&s,2u);
    s.count=pop_word(&s);
#if ENTITY_STATE10_MUTATION == 7
    s.count=cached_normal_x;
#endif
    s.candidate_y=record_word(&s,2u);
    s.flags=sub_flags(s.flags,s.candidate_y,0x00b4u,16u);
#if ENTITY_STATE10_MUTATION == 3
    if(s.candidate_y>=0x00b4u)
        return finish(&s,LMN_ENTITY_FINISH_MARK_INACTIVE_20E2,
                      pc_binding,sound_binding);
#else
    if(!signed_less(s.flags))
        return finish(&s,LMN_ENTITY_FINISH_MARK_INACTIVE_20E2,
                      pc_binding,sound_binding);
#endif

    /* 242D..2445: preserve SHR/RCR carry propagation and saved operands. */
    prepare_masks(&s);
    push_word(&s,s.map_cursor);
    push_word(&s,s.count);
    child=call_exchange(&s,CS_EntityState0010AfterFirstExchange);
    if(child.status!=LMN_ENTITY_STATE10_READY)return child;
    s.value=pop_word(&s); /* the parent's live POP AX */
    s.auxiliary_value=pop_word(&s); /* live POP DX */
    s.flags=logic_flags(s.flags,
        (uint16_t)(s.auxiliary_value&s.map_cursor),16u); /* TEST DX,BX */
    if((s.auxiliary_value&s.map_cursor)==0u) {
        s.flags=logic_flags(s.flags,(uint16_t)(s.value&s.count),16u);
        if((s.value&s.count)==0u) {
            /* 244E..248E: collision-free state and direct JMP 1FE8. */
            and_record_word(&s,8u,0xffefu);
            or_record_word(&s,8u,0x0004u);
            set_record_word(&s,0x0au,0u);
            set_record_word(&s,0x0cu,0x0a42u);
            set_record_word(&s,0x10u,0x005au);
            set_record_word(&s,0x12u,0x003cu);
            set_record_byte(&s,0x28u,0u);
            set_record_byte(&s,0x23u,0x03u);
            set_record_word(&s,4u,0xfff8u);
            set_record_word(&s,6u,0xfff6u);
            set_record_byte(&s,0x29u,0x04u);
            s.value=read16(&s,s.data_segment,
                SEG09A9_DrawingCallbackSlots,s.flags);
            set_record_word(&s,0x14u,s.value);
            set_record_byte(&s,0x2au,0u);
            and_record_byte(&s,0x24u,0x01u);
            return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                          pc_binding,sound_binding);
        }
    }

    /* 2491..24BA: live DS coordinates select an explicitly SS-backed nibble. */
    s.value=record_word(&s,0u);
    s.map_cursor=record_word(&s,2u);
    s.flags=sub_flags(s.flags,s.map_cursor,0x10u,16u);
    s.map_cursor=(uint16_t)(s.map_cursor-0x10u);
    s.flags=shr_flags(s.flags,s.value,16u);
    s.value=(uint16_t)(s.value>>1u);
    s.flags=shr_flags(s.flags,s.value,16u);
    s.value=(uint16_t)(s.value>>1u);
    s.flags=shr_flags(s.flags,s.map_cursor,16u);
    s.map_cursor=(uint16_t)(s.map_cursor>>1u);
    s.flags=shr_flags(s.flags,s.map_cursor,16u);
    s.map_cursor=(uint16_t)(s.map_cursor>>1u);
    push_word(&s,s.value);
    push_word(&s,s.auxiliary_value);
    s.value=s.map_cursor;
    word=0x01a0u;
    product=(uint32_t)s.value*word;
    s.flags=(uint16_t)((s.flags&~(CF|OF))|
                       ((product>>16)?(CF|OF):0u));
    s.value=(uint16_t)product;
    s.auxiliary_value=(uint16_t)(product>>16);
    s.auxiliary_value=pop_word(&s);
    s.map_cursor=pop_word(&s);
    s.flags=add_flags(s.flags,s.map_cursor,s.value,16u);
    s.map_cursor=(uint16_t)(s.map_cursor+s.value);
    s.flags=add_flags(s.flags,s.map_cursor,0x12u,16u);
    s.map_cursor=(uint16_t)(s.map_cursor+0x12u);
#if ENTITY_STATE10_MUTATION == 5
    al=read8(&s,s.data_segment,s.map_cursor,s.flags);
#else
    al=read8(&s,s.stack_segment,s.map_cursor,s.flags);
#endif
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.flags=logic_flags(s.flags,(uint16_t)(al&0x0fu),8u);
    al=(uint8_t)(al&0x0fu);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.flags=sub_flags(s.flags,al,0x09u,8u);
    if(al!=0x09u)
        return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                      pc_binding,sound_binding);

    /* 24BD..2509: optional real INT61 frame then live reset/callback data. */
    word=read8(&s,s.data_segment,SEG09A9_ExternalSoundDriverEnabled,s.flags);
    s.flags=sub_flags(s.flags,word,0xffu,8u);
    if((s.flags&ZF)!=0u) {
        al=read8(&s,s.data_segment,SEG09A9_SoundOptionBits,s.flags);
        s.flags=logic_flags(s.flags,(uint16_t)(al&0x03u),8u);
        if((s.flags&ZF)==0u) {
            s.value=0x040au;
            if(call_sound(&s,sound_binding)!=LMN_ENTITY_STATE10_READY)
                return result_of(&s);
        }
    }
    set_record_word(&s,8u,0u);
    set_record_word(&s,0x0au,0u);
    set_record_word(&s,0x0cu,0u);
    set_record_word(&s,0x10u,0x005au);
    set_record_word(&s,0x12u,0x003cu);
    set_record_byte(&s,0x28u,0u);
    set_record_word(&s,4u,0xfff8u);
    set_record_word(&s,6u,0xfff6u);
    set_record_byte(&s,0x29u,0x09u);
    s.value=read16(&s,s.data_segment,SEG09A9_DrawingCallbackSlots,s.flags);
    set_record_word(&s,0x14u,s.value);
    set_record_byte(&s,0x2au,0u);
    and_record_byte(&s,0x24u,0x01u);
    return finish(&s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);
}

uint16_t lmn_entity_state10_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityState10Call call;
    LmnEntityState10Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state10_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;r->es=out.extra_segment;
    r->ss=out.stack_segment;r->sp=out.stack_offset;r->flags=out.flags;
    r->ip=out.continuation;
    return out.status;
}

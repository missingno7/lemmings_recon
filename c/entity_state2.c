#include "entity_state2.h"
#include "lemmings_sym.h"
#include "pcspeaker_interrupt.h"

#ifndef ENTITY_STATE2_MUTATION
#define ENTITY_STATE2_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State2 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} State2;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State2 *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(State2 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State2 *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(State2 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* The high byte is the next physical byte, with 20-bit physical wrapping. */
static uint16_t read16(State2 *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(State2 *s,uint16_t segment,uint16_t offset,uint16_t value,
                    uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned parity=0,bit;
    uint16_t out=0;
    uint16_t mask=(uint16_t)(bits==8u?0x00ffu:0xffffu);
    value=(uint16_t)(value&mask);
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
    if((~(left^right)&(left^value)&sign)!=0)out|=OF;
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
    if(((left^right)&(left^value)&sign)!=0)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint16_t updated=add_flags(flags,before,1u,8u);
    return (uint16_t)((updated&~CF)|(flags&CF));
}

static uint16_t dec8_flags(uint16_t flags,uint8_t before) {
    uint16_t updated=sub_flags(flags,before,1u,8u);
    return (uint16_t)((updated&~CF)|(flags&CF));
}

/* SHR word,1 defines CF/OF/SZP. AF is undefined; preserve its opaque bit. */
static uint16_t shr16_flags(uint16_t flags,uint16_t before) {
    uint16_t after=(uint16_t)(before>>1);
    uint16_t out=szp(after,16u);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    return (uint16_t)((flags&~(ARITH&~AF))|out);
}

/* MUL defines only CF/OF; retain the remaining arithmetic bits as opaque. */
static uint16_t mul_flags(uint16_t flags,uint32_t product) {
    uint16_t out=(uint16_t)(flags&~(CF|OF));
    if(product>>16)out|=CF|OF;
    return out;
}

static uint16_t record_offset(const State2 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint8_t record_byte(State2 *s,uint16_t displacement) {
    return read8(s,s->data_segment,record_offset(s,displacement));
}

static void set_record_byte(State2 *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,record_offset(s,displacement),value,s->flags);
}

static uint16_t record_word(State2 *s,uint16_t displacement) {
    return read16(s,s->data_segment,record_offset(s,displacement));
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    /* AF after TEST/AND is undefined; this oracle chooses zero. */
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static void push_word(State2 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(State2 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityState2Result result_of(const State2 *s) {
    LmnEntityState2Result out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void apply_regs(State2 *s,const LmnRegs *r) {
    s->value=r->ax;s->map_cursor=r->bx;s->count=r->cx;
    s->auxiliary_value=r->dx;s->record_cursor=r->si;s->object_cursor=r->di;
    s->candidate_y=r->bp;s->code_segment=r->cs;s->data_segment=r->ds;
    s->extra_segment=r->es;s->stack_segment=r->ss;
    s->stack_offset=r->sp;s->flags=r->flags;
    s->continuation=r->ip;
}

static LmnRegs regs_from_state(const State2 *s) {
    LmnRegs r;
    r.ax=s->value;r.bx=s->map_cursor;r.cx=s->count;r.dx=s->auxiliary_value;
    r.si=s->record_cursor;r.di=s->object_cursor;r.bp=s->candidate_y;
    r.cs=s->code_segment;r.ds=s->data_segment;r.es=s->extra_segment;
    r.ss=s->stack_segment;r.sp=s->stack_offset;r.flags=s->flags;
    r.ip=s->continuation;
    return r;
}

static uint16_t pc_status(uint16_t status) {
    switch(status) {
    case LMN_PC_INTERRUPT_RETURNED:
        return LMN_ENTITY_STATE2_READY;
    case LMN_PC_INTERRUPT_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE2_UNBOUND_VECTOR;
    case LMN_PC_INTERRUPT_UNTRANSLATED_CHILD:
        return LMN_ENTITY_STATE2_UNTRANSLATED_CHILD;
    case LMN_PC_INTERRUPT_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE2_CHANGED_PC_CHILD_RETURN;
    case LMN_PC_INTERRUPT_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE2_CHANGED_PC_INTERRUPT_RETURN;
    default:
        return LMN_ENTITY_STATE2_INVALID_CHILD;
    }
}

static uint16_t invoke_pc(State2 *s,const LmnPcSpeakerBinding *binding) {
    LmnPcSpeakerInterruptCall call;
    LmnPcSpeakerInterruptResult out;
    call.registers=regs_from_state(s);
    call.return_offset=CS_EntityState0002AfterSound;
    out=lmn_pc_speaker_interrupt60_core(s->memory,&call,binding,s->bus);
    apply_regs(s,&out.registers);
    s->status=pc_status(out.status);
    if(out.status==LMN_PC_INTERRUPT_RETURNED) {
        s->continuation=CS_EntityState0002AfterSound;
    }
    return s->status;
}

static uint16_t finish_status(uint16_t status) {
    switch(status) {
    case LMN_ENTITY_FINISH_RETURNED:return LMN_ENTITY_STATE2_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        return LMN_ENTITY_STATE2_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_STATE2_UNTRANSLATED_CHILD;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_STATE2_CHANGED_PC_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_STATE2_CHANGED_PC_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_STATE2_CHANGED_FINISH_CALL_RETURN;
    default:return LMN_ENTITY_STATE2_INVALID_CHILD;
    }
}

static LmnEntityState2Result mark_inactive(State2 *s) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=LMN_ENTITY_FINISH_MARK_INACTIVE_20E2;
    call.value=s->value;call.map_cursor=s->map_cursor;call.count=s->count;
    call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
    call.flags=s->flags;
    out=lmn_entity_finish_core(s->memory,&call,NULL,NULL,s->bus);
    s->value=out.value;s->map_cursor=out.map_cursor;s->count=out.count;
    s->auxiliary_value=out.auxiliary_value;
    s->record_cursor=out.record_cursor;s->object_cursor=out.object_cursor;
    s->candidate_y=out.candidate_y;s->code_segment=out.code_segment;
    s->data_segment=out.data_segment;s->extra_segment=out.extra_segment;
    s->stack_segment=out.stack_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=finish_status(out.status);
    return result_of(s);
}

static LmnEntityState2Result call_pattern(State2 *s) {
    LmnEntityPatternCall call;
    LmnEntityPatternResult out;
    uint16_t actual_return;

    push_word(s,CS_EntityState0002AfterPatternCall);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.saved_destination=s->object_cursor;
    call.saved_value=s->auxiliary_value;call.saved_segment=s->extra_segment;
    call.flags=s->flags;
    out=lmn_copy_entity_pattern_bus_core(s->memory,&call,s->bus);

    /* 283B restores the values by popping their live SS words. */
    s->value=out.product;s->map_cursor=out.map_offset;
    s->auxiliary_value=out.restored_value;s->record_cursor=out.record_cursor;
    s->object_cursor=out.restored_destination;s->extra_segment=out.restored_segment;
    s->stack_offset=out.stack_offset;s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE2_MUTATION != 3
    if(actual_return!=CS_EntityState0002AfterPatternCall) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE2_CHANGED_PATTERN_RETURN;
        return result_of(s);
    }
#else
    (void)actual_return;
#endif
    s->continuation=CS_EntityState0002AfterPatternCall;
    return result_of(s);
}

#if ENTITY_STATE2_MUTATION != 8
static LmnEntityState2Result call_mask(State2 *s) {
    LmnEntityMaskCall call;
    LmnEntityMaskResult out;
    uint16_t actual_return;

    push_word(s,CS_EntityState0002AfterMaskCall);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.flags=s->flags;
    out=lmn_draw_clipped_entity_mask_core(s->memory,&call,s->bus);

    s->value=out.value;s->map_cursor=out.mask_word;s->count=out.row_count;
    s->auxiliary_value=out.port;s->record_cursor=out.source_cursor;
    s->object_cursor=out.destination_offset;s->data_segment=out.data_segment;
    s->extra_segment=out.output_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE2_MUTATION != 3
    if(actual_return!=CS_EntityState0002AfterMaskCall) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE2_CHANGED_MASK_RETURN;
        return result_of(s);
    }
#else
    (void)actual_return;
#endif
    s->continuation=CS_EntityState0002AfterMaskCall;
    return result_of(s);
}
#endif

LmnEntityState2Result lmn_entity_state2_core(uint8_t *memory,
    const LmnEntityState2Call *call,
    const LmnPcSpeakerBinding *pc_binding,const LmnRasterBus *bus) {
    State2 s;
    LmnEntityState2Result child;
    uint8_t al,field;
    uint16_t ax,bx,dx,state_bits;
    uint32_t product;
#if ENTITY_STATE2_MUTATION == 4
    uint16_t saved_dx;
#endif
#if ENTITY_STATE2_MUTATION == 6
    uint16_t data_before_interrupt,record_before_interrupt;
#endif

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityState0002;
    s.status=LMN_ENTITY_STATE2_READY;

    /* 2350..2363: full-byte INC, raw compare, then DEC's residual AL. */
    al=record_byte(&s,0x28u);
    s.flags=inc8_flags(s.flags,al);
    al=(uint8_t)(al+1u);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    set_record_byte(&s,0x28u,al);
#if ENTITY_STATE2_MUTATION == 1
    s.flags=sub_flags(s.flags,al,0x33u,8u);
    if(al==0x33u)return mark_inactive(&s);
#else
    s.flags=sub_flags(s.flags,al,0x34u,8u);
    if(al==0x34u)return mark_inactive(&s);
#endif
    s.flags=dec8_flags(s.flags,al);
    al=(uint8_t)(al-1u);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    if(al!=0u) {
        s.continuation=CS_EntityIterationTail;
        return result_of(&s);
    }

    /* 2366..2372: provider reads are ordered and live. */
    field=read8(&s,s.data_segment,SEG09A9_ExternalSoundDriverEnabled);
    s.flags=sub_flags(s.flags,field,0xffu,8u);
    if(s.flags&ZF)goto test_pattern_gate;
    field=read8(&s,s.data_segment,SEG09A9_SoundOptionBits);
    s.flags=logic_flags(s.flags,(uint16_t)(field&0x01u),8u);
    if(s.flags&ZF)goto test_pattern_gate;

    /* INT 60h supplies all live registers and owns its actual frame/IRET. */
    s.value=0x030cu;
    s.continuation=0x2377u;
#if ENTITY_STATE2_MUTATION == 6
    data_before_interrupt=s.data_segment;
    record_before_interrupt=s.record_cursor;
#endif
    if(invoke_pc(&s,pc_binding)!=LMN_ENTITY_STATE2_READY)
        return result_of(&s);
#if ENTITY_STATE2_MUTATION == 6
    s.data_segment=data_before_interrupt;
    s.record_cursor=record_before_interrupt;
#endif

test_pattern_gate:
#if ENTITY_STATE2_MUTATION == 5
    state_bits=(uint16_t)(record_word(&s,0x08u)&0x0001u);
#else
    state_bits=(uint16_t)(record_word(&s,0x08u)&0x0100u);
#endif
    s.flags=logic_flags(s.flags,state_bits,16u);
    if(state_bits!=0u) {
        child=call_pattern(&s);
        if(child.status!=LMN_ENTITY_STATE2_READY)return child;
    }

    /* 2386..23A9 rereads the record after pattern RET and keeps each live
       PUSH/POP result; the nibble lookup is explicitly through SS. */
    ax=record_word(&s,0u);
    s.value=ax;
    bx=record_word(&s,2u);
    s.map_cursor=bx;
    s.flags=sub_flags(s.flags,bx,0x10u,16u);
    bx=(uint16_t)(bx-0x10u);
    s.flags=shr16_flags(s.flags,ax);
    ax=(uint16_t)(ax>>1);
    s.flags=shr16_flags(s.flags,ax);
    ax=(uint16_t)(ax>>1);
    s.value=ax;
    s.flags=shr16_flags(s.flags,bx);
    bx=(uint16_t)(bx>>1);
    s.flags=shr16_flags(s.flags,bx);
    bx=(uint16_t)(bx>>1);
    s.map_cursor=bx;

#if ENTITY_STATE2_MUTATION == 4
    saved_dx=s.auxiliary_value;
#endif
    push_word(&s,ax);
    push_word(&s,s.auxiliary_value);
    ax=bx;
    dx=0x01a0u;
    product=(uint32_t)ax*dx;
    s.flags=mul_flags(s.flags,product);
    ax=(uint16_t)product;
    dx=(uint16_t)(product>>16);
    s.value=ax;
    s.auxiliary_value=dx;
    dx=pop_word(&s);
#if ENTITY_STATE2_MUTATION == 4
    (void)dx;
    s.auxiliary_value=saved_dx;
#else
    s.auxiliary_value=dx;
#endif
    bx=pop_word(&s);
    s.map_cursor=bx;
    s.flags=add_flags(s.flags,bx,ax,16u);
    bx=(uint16_t)(bx+ax);
    s.flags=add_flags(s.flags,bx,0x12u,16u);
    bx=(uint16_t)(bx+0x12u);
    s.map_cursor=bx;
#if ENTITY_STATE2_MUTATION == 7
    al=read8(&s,s.data_segment,bx);
#else
    al=read8(&s,s.stack_segment,bx);
#endif
    ax=(uint16_t)((ax&0xff00u)|al);
    s.value=ax;
    s.flags=logic_flags(s.flags,(uint16_t)(al&0x0fu),8u);
    al=(uint8_t)(al&0x0fu);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.flags=sub_flags(s.flags,al,0x09u,8u);
    if(al==0x09u) {
        s.continuation=CS_EntityIterationTail;
        return result_of(&s);
    }
    s.flags=sub_flags(s.flags,al,0x05u,8u);
#if ENTITY_STATE2_MUTATION != 2
    if(al==0x05u) {
        s.continuation=CS_EntityIterationTail;
        return result_of(&s);
    }
#endif

#if ENTITY_STATE2_MUTATION == 8
    s.continuation=CS_EntityIterationTail;
    return result_of(&s);
#else
    child=call_mask(&s);
    if(child.status!=LMN_ENTITY_STATE2_READY)return child;
    s.continuation=CS_EntityIterationTail;
    return result_of(&s);
#endif
}

uint16_t lmn_entity_state2_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,const LmnRasterBus *bus) {
    LmnEntityState2Call call;
    LmnEntityState2Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state2_core(memory,&call,pc_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}

#include "entity_state40.h"
#include "lemmings_sym.h"

#ifndef ENTITY_STATE40_MUTATION
#define ENTITY_STATE40_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State40 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} State40;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State40 *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(State40 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State40 *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(State40 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* A word's high byte follows the low byte physically, including 20-bit wrap. */
static uint16_t read16(State40 *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(State40 *s,uint16_t segment,uint16_t offset,uint16_t value,
                    uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t record_offset(const State40 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint16_t szp(uint16_t value,unsigned bits) {
    uint16_t mask=(uint16_t)(bits==8u?0x00ffu:0xffffu);
    uint16_t sign=(uint16_t)(1u<<(bits-1u));
    unsigned parity=0u,bit;
    uint16_t out=0u;
    value=(uint16_t)(value&mask);
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&sign)out|=SF;
    return out;
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t sum=(uint32_t)left+(uint32_t)right;
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
    uint16_t lhs=(uint16_t)(left&mask),rhs=(uint16_t)(right&mask);
    uint16_t value=(uint16_t)(((uint32_t)lhs-(uint32_t)rhs)&mask);
    uint16_t out=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if(lhs<rhs)out|=CF;
    if((lhs^rhs^value)&AF)out|=AF;
    if(((lhs^rhs)&(lhs^value)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint16_t old_cf=(uint16_t)(flags&CF);
    uint16_t result=add_flags(flags,before,1u,8u);
    return (uint16_t)((result&~CF)|old_cf);
}

static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    /* AND leaves AF undefined; use zero, matching neighboring state cores. */
    uint16_t out=(uint16_t)(flags&~ARITH);
    unsigned parity=0u,bit;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&0x80u)out|=SF;
    return out;
}

static void copy_finish(State40 *s,const LmnEntityFinishResult *out) {
    s->value=out->value;s->map_cursor=out->map_cursor;
    s->count=out->count;s->auxiliary_value=out->auxiliary_value;
    s->record_cursor=out->record_cursor;s->object_cursor=out->object_cursor;
    s->candidate_y=out->candidate_y;s->code_segment=out->code_segment;
    s->data_segment=out->data_segment;s->extra_segment=out->extra_segment;
    s->stack_segment=out->stack_segment;s->stack_offset=out->stack_offset;
    s->flags=out->flags;s->continuation=out->continuation;
    switch(out->status) {
    case LMN_ENTITY_FINISH_RETURNED:
        s->status=LMN_ENTITY_STATE40_READY;break;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:
        s->status=LMN_ENTITY_STATE40_UNBOUND_VECTOR;break;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        s->status=LMN_ENTITY_STATE40_UNTRANSLATED_CHILD;break;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        s->status=LMN_ENTITY_STATE40_CHANGED_CHILD_RETURN;break;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        s->status=LMN_ENTITY_STATE40_CHANGED_INTERRUPT_RETURN;break;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        s->status=LMN_ENTITY_STATE40_CHANGED_FINISH_CALL_RETURN;break;
    default:
        s->status=LMN_ENTITY_STATE40_INVALID_CHILD;break;
    }
}

static LmnEntityState40Result result_of(const State40 *s) {
    LmnEntityState40Result out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static LmnEntityState40Result finish_step(State40 *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
#if ENTITY_STATE40_MUTATION == 8
    /* Mutant invents a CALL frame for the original direct JMP to 2148. */
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,
            CS_EntityIterationTail,s->flags);
#endif
    call.entry=LMN_ENTITY_FINISH_RESOLVE_HEIGHT_2148;
    call.value=s->value;call.map_cursor=s->map_cursor;call.count=s->count;
    call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
    call.flags=s->flags;
    out=lmn_entity_finish_core(s->memory,&call,pc_binding,sound_binding,s->bus);
    copy_finish(s,&out);
    return result_of(s);
}

LmnEntityState40Result lmn_entity_state40_core(uint8_t *memory,
    const LmnEntityState40Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    State40 s;
    uint8_t al;
#if ENTITY_STATE40_MUTATION == 4
    uint16_t early_callback_word;
#endif

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_AdvanceEntityState0040;
    s.status=LMN_ENTITY_STATE40_READY;

    /* 2637..2640: MOV AL,[SI+28]; INC AL; AND AL,7; MOV [SI+28],AL. */
    al=read8(&s,s.data_segment,record_offset(&s,0x28u));
    s.flags=inc8_flags(s.flags,al);
    al=(uint8_t)(al+1u);
#if ENTITY_STATE40_MUTATION == 1
    al=(uint8_t)(al&0x0fu);
#else
    al=(uint8_t)(al&0x07u);
#endif
    s.flags=logic8_flags(s.flags,al);
    s.value=(uint16_t)((s.value&0xff00u)|al);
    write8(&s,s.data_segment,record_offset(&s,0x28u),al,s.flags);

    /* JZ loc_2654; otherwise CMP AL,5 / signed JL loc_264A. */
    if(al==0u) {
        /* 2654..268D: ordered zero-state field stores and live rereads. */
#if ENTITY_STATE40_MUTATION == 4
        early_callback_word=read16(&s,s.data_segment,
                                   SEG09A9_DrawingCallbackSlots);
#endif
#if ENTITY_STATE40_MUTATION == 3
        write16(&s,s.data_segment,record_offset(&s,0x08u),1u,s.flags);
#else
        write16(&s,s.data_segment,record_offset(&s,0x08u),0u,s.flags);
#endif
        write16(&s,s.data_segment,record_offset(&s,0x0au),0u,s.flags);
        write16(&s,s.data_segment,record_offset(&s,0x0cu),0u,s.flags);
        write16(&s,s.data_segment,record_offset(&s,0x10u),0x005au,s.flags);
        write16(&s,s.data_segment,record_offset(&s,0x12u),0x003cu,s.flags);
        write8(&s,s.data_segment,record_offset(&s,0x28u),0u,s.flags);
        write16(&s,s.data_segment,record_offset(&s,0x04u),0xfff8u,s.flags);
        write16(&s,s.data_segment,record_offset(&s,0x06u),0xfff6u,s.flags);
        write8(&s,s.data_segment,record_offset(&s,0x29u),9u,s.flags);
#if ENTITY_STATE40_MUTATION == 4
        s.value=early_callback_word;
#else
        s.value=read16(&s,s.data_segment,SEG09A9_DrawingCallbackSlots);
#endif
        write16(&s,s.data_segment,record_offset(&s,0x14u),s.value,s.flags);
        write8(&s,s.data_segment,record_offset(&s,0x2au),0u,s.flags);
        {
            uint16_t entry_flags=s.flags;
            uint16_t offset=record_offset(&s,0x24u);
            uint8_t old=read8(&s,s.data_segment,offset);
#if ENTITY_STATE40_MUTATION == 7
            uint8_t updated=(uint8_t)(old&0u);
#else
            uint8_t updated=(uint8_t)(old&1u);
#endif
            uint16_t result_flags=logic8_flags(entry_flags,updated);
            /* RMW writes are observed before the AND defines its FLAGS. */
            write8(&s,s.data_segment,offset,updated,entry_flags);
            s.flags=result_flags;
        }
#if ENTITY_STATE40_MUTATION == 5
        s.candidate_y=call->candidate_y;
#else
        s.candidate_y=read16(&s,s.data_segment,record_offset(&s,2u));
#endif
        return finish_step(&s,pc_binding,sound_binding);
    }

    {
#if ENTITY_STATE40_MUTATION == 2
        const uint8_t threshold=4u;
#else
        const uint8_t threshold=5u;
#endif
        s.flags=sub_flags(s.flags,al,threshold,8u); /* CMP AL,5 */
        if(((s.flags&SF)!=0u)!=((s.flags&OF)!=0u)) {
            /* 264A: SUB word [SI+2],2 observes instruction-entry FLAGS. */
            uint16_t entry_flags=s.flags;
            uint16_t offset=record_offset(&s,2u);
            uint16_t old=read16(&s,s.data_segment,offset);
#if ENTITY_STATE40_MUTATION == 6
            const uint16_t amount=1u;
#else
            const uint16_t amount=2u;
#endif
            uint16_t updated=(uint16_t)(old-amount);
            uint16_t result_flags=sub_flags(entry_flags,old,amount,16u);
            write16(&s,s.data_segment,offset,updated,entry_flags);
            s.flags=result_flags;
#if ENTITY_STATE40_MUTATION == 5
            s.candidate_y=call->candidate_y;
#else
            s.candidate_y=read16(&s,s.data_segment,offset);
#endif
            return finish_step(&s,pc_binding,sound_binding);
        }
    }

    /* 2647: values 5..7 JMP directly to 1FEB. */
    s.continuation=CS_EntityIterationTail;
    return result_of(&s);
}

uint16_t lmn_entity_state40_adapter(uint8_t *memory,LmnRegs *r,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityState40Call call;
    LmnEntityState40Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state40_core(memory,&call,pc_binding,sound_binding,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}

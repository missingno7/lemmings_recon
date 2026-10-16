#include "entity_state100.h"
#include "lemmings_sym.h"

#ifndef ENTITY_STATE100_MUTATION
#define ENTITY_STATE100_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,OF=0x0800u,ARITH=0x08d5u };

typedef struct State100 {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} State100;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(State100 *s,uint32_t address,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,flags);
    return s->memory[address];
}

static void write_physical(State100 *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(State100 *s,uint16_t segment,uint16_t offset,
                     uint16_t flags) {
    return read_physical(s,physical(segment,offset),flags);
}

static void write8(State100 *s,uint16_t segment,uint16_t offset,uint8_t value,
                   uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* A real-mode word's high byte is the next physical byte, including 20-bit
   wrap, rather than a new segment:wrapped-offset calculation. */
static uint16_t read16(State100 *s,uint16_t segment,uint16_t offset,
                       uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address,flags);
    uint8_t high=read_physical(s,address+1u,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(State100 *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t record_offset(const State100 *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint16_t szp8(uint8_t value) {
    unsigned parity=0u,bit;
    uint16_t flags=0u;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)flags|=PF;
    if(!value)flags|=ZF;
    if(value&0x80u)flags|=SF;
    return flags;
}

static uint16_t add8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    unsigned sum=(unsigned)left+(unsigned)right;
    uint8_t result=(uint8_t)sum;
    uint16_t arithmetic=szp8(result);
    if(sum>0xffu)arithmetic|=CF;
    if((left^right^result)&AF)arithmetic|=AF;
    if(((~(left^right)&(left^result))&0x80u)!=0u)arithmetic|=OF;
    return (uint16_t)((flags&~ARITH)|arithmetic);
}

static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint16_t carry=(uint16_t)(flags&CF);
    uint16_t result=add8_flags(flags,before,1u);
    return (uint16_t)((result&~CF)|carry);
}

static uint16_t logic8_flags(uint16_t flags,uint8_t result) {
    /* AND defines CF/OF/SZP, leaves AF undefined; clear its modeled bit. */
    return (uint16_t)((flags&~ARITH)|szp8(result));
}

static void push_word(State100 *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(State100 *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset,s->flags);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static LmnEntityState100Result result_of(const State100 *s) {
    LmnEntityState100Result out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static uint16_t call_pixel(State100 *s) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult child;
    uint16_t actual_return;

    /* CALL 27EF pushes 27F2; the child sees and preserves that live SS word. */
    push_word(s,CS_EntityState0100AfterPixelCall);
    call.data_segment=s->data_segment;
    call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;
    call.record_cursor=s->record_cursor;
    call.saved_value=s->auxiliary_value;
    call.flags=s->flags;
    child=lmn_prepare_entity_pixel_bus_core(s->memory,&call,s->bus);

    s->value=child.value;s->map_cursor=child.table_cursor;
    s->count=child.column_byte;s->object_cursor=child.destination_offset;
    s->auxiliary_value=child.restored_value;s->extra_segment=0xa000u;
    s->stack_offset=child.stack_offset;s->flags=child.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE100_MUTATION == 2
    (void)actual_return;
#else
    if(actual_return!=CS_EntityState0100AfterPixelCall) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE100_CHANGED_PIXEL_RETURN;
        return 0u;
    }
#endif
    return 1u;
}

static uint16_t call_pattern(State100 *s,uint16_t entry_extra_segment) {
    LmnEntityPatternCall call;
    LmnEntityPatternResult child;
    uint16_t actual_return;

    /* CALL 2835 and the child RET both consume the actual SS frame. */
    push_word(s,CS_EntityState0100AfterPatternCall);
    call.data_segment=s->data_segment;
    call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;
    call.record_cursor=s->record_cursor;
    call.saved_destination=s->object_cursor;
    call.saved_value=s->auxiliary_value;
#if ENTITY_STATE100_MUTATION == 4
    call.saved_segment=entry_extra_segment; /* cached before the pixel child */
#else
    (void)entry_extra_segment;
    call.saved_segment=s->extra_segment;
#endif
    call.flags=s->flags;
    child=lmn_copy_entity_pattern_bus_core(s->memory,&call,s->bus);

    s->value=child.product;s->map_cursor=child.map_offset;
    s->auxiliary_value=child.restored_value;
    s->record_cursor=child.record_cursor;
    s->object_cursor=child.restored_destination;
    s->extra_segment=child.restored_segment;
    s->stack_offset=child.stack_offset;s->flags=child.flags;
    actual_return=pop_word(s);
#if ENTITY_STATE100_MUTATION == 3
    (void)actual_return;
#else
    if(actual_return!=CS_EntityState0100AfterPatternCall) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_STATE100_CHANGED_PATTERN_RETURN;
        return 0u;
    }
#endif
    return 1u;
}

static void transition_to_pattern(State100 *s) {
    uint16_t callback=0u;

#if ENTITY_STATE100_MUTATION == 5
    /* Mutant reads DS:002E before stores that may alias that word. */
    callback=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots,s->flags);
#endif
    /* Ordered 27FC..282D MOV stores preserve the AND-produced FLAGS. */
    write16(s,s->data_segment,record_offset(s,0x08u),0u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x0au),0u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x0cu),0u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x10u),0x005au,s->flags);
    write16(s,s->data_segment,record_offset(s,0x12u),0x003cu,s->flags);
    write8(s,s->data_segment,record_offset(s,0x28u),0u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x04u),0xfff8u,s->flags);
    write16(s,s->data_segment,record_offset(s,0x06u),0xfff6u,s->flags);
    write8(s,s->data_segment,record_offset(s,0x29u),9u,s->flags);
#if ENTITY_STATE100_MUTATION != 5
    callback=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots,s->flags);
#endif
    write16(s,s->data_segment,record_offset(s,0x14u),callback,s->flags);
    write8(s,s->data_segment,record_offset(s,0x2au),0u,s->flags);

    /* AND byte [SI+24],1: bus sees entry FLAGS, then logic FLAGS become live. */
    {
        uint16_t entry_flags=s->flags;
        uint16_t offset=record_offset(s,0x24u);
        uint8_t old=read8(s,s->data_segment,offset,entry_flags);
        uint8_t updated=(uint8_t)(old&1u);
        write8(s,s->data_segment,offset,updated,entry_flags);
        s->flags=logic8_flags(entry_flags,updated);
    }
}

LmnEntityState100Result lmn_entity_state100_core(uint8_t *memory,
    const LmnEntityState100Call *call,const LmnRasterBus *bus) {
    State100 s;
    uint8_t pixel;
    uint8_t al;

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_EntityIterationTail;
    s.status=LMN_ENTITY_STATE100_READY;

    /* 27E8 INC byte [SI+28], then 27EB AND byte [SI+28],0Fh. Both are
       separate memory RMW instructions and their writes see entry FLAGS. */
    {
        uint16_t entry_flags=s.flags;
        uint16_t offset=record_offset(&s,0x28u);
        uint8_t old=read8(&s,s.data_segment,offset,entry_flags);
        uint8_t updated=(uint8_t)(old+1u);
        uint16_t result_flags=inc8_flags(entry_flags,old);
        write8(&s,s.data_segment,offset,updated,entry_flags);
        s.flags=result_flags;
    }
    {
        uint16_t entry_flags=s.flags;
        uint16_t offset=record_offset(&s,0x28u);
        uint8_t old=read8(&s,s.data_segment,offset,entry_flags);
#if ENTITY_STATE100_MUTATION == 1
        uint8_t updated=(uint8_t)(old&0x07u);
#else
        uint8_t updated=(uint8_t)(old&0x0fu);
#endif
        write8(&s,s.data_segment,offset,updated,entry_flags);
        s.flags=logic8_flags(entry_flags,updated);
    }

    if(!call_pixel(&s))return result_of(&s);

    /* MOV AL,[ES:DI] replaces only AL and preserves FLAGS; AND AL,AH then
       defines the branch flags. */
    pixel=read8(&s,s.extra_segment,s.object_cursor,s.flags);
#if ENTITY_STATE100_MUTATION == 6
    (void)pixel;
    al=(uint8_t)(s.value&((s.value>>8)&0xffu));
#else
    al=(uint8_t)(pixel&(uint8_t)(s.value>>8));
#endif
    s.value=(uint16_t)((s.value&0xff00u)|al);
    s.flags=logic8_flags(s.flags,al);
    if(al!=0u)return result_of(&s); /* JZ 27FC, otherwise JMP 1FEB. */

    transition_to_pattern(&s);
    if(!call_pattern(&s,call->extra_segment))return result_of(&s);
    return result_of(&s); /* JMP 1FEB. */
}

uint16_t lmn_entity_state100_adapter(uint8_t *memory,LmnRegs *r,
    const LmnRasterBus *bus) {
    LmnEntityState100Call call;
    LmnEntityState100Result out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_entity_state100_core(memory,&call,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;r->ip=out.continuation;
    return out.status;
}

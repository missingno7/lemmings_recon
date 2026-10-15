#include "entity_pattern.h"
#include "lemmings_sym.h"

#ifndef MUTATION
#define MUTATION 0
#endif

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}
static uint16_t word(const uint8_t *memory, uint16_t segment, uint16_t offset) {
    uint32_t p=physical(segment,offset);
    return (uint16_t)(memory[p] | ((uint16_t)memory[(p+1u)&0xfffffu] << 8));
}
static void store_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value) {
    uint32_t p=physical(segment,offset);
    memory[p]=(uint8_t)value;
    memory[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static void push(uint8_t *memory, uint16_t ss, uint16_t *sp, uint16_t value) {
    *sp=(uint16_t)(*sp-2u);
    store_word(memory,ss,*sp,value);
}
static uint16_t pop(const uint8_t *memory, uint16_t ss, uint16_t *sp) {
    uint16_t value=word(memory,ss,*sp);
    *sp=(uint16_t)(*sp+2u);
    return value;
}
static uint16_t add_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t sum=(uint32_t)left+right;
    uint16_t value=(uint16_t)sum;
    unsigned parity=0, bit;
    uint16_t status=0;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    if(!parity)status|=4u;
    if(!value)status|=0x40u;
    if(value&0x8000u)status|=0x80u;
    if(sum>0xffffu)status|=1u;
    if((left^right^value)&0x10u)status|=0x10u;
    if((~(left^right)&(left^value)&0x8000u)!=0)status|=0x800u;
    return (uint16_t)((flags&~0x8d5u)|status);
}

LmnEntityPatternResult lmn_copy_entity_pattern_core(
    uint8_t *memory, const LmnEntityPatternCall *call) {
    uint16_t ds=call->data_segment, ss=call->stack_segment;
    uint16_t sp=call->stack_offset, si=call->record_cursor;
    uint16_t x=word(memory,ds,si);
    uint16_t y=word(memory,ds,(uint16_t)(si+2u));
    uint16_t qx=(uint16_t)(x-4u), qy=(uint16_t)(y-6u-0x10u);
    uint16_t product, bx, dx, es, di, flags=call->flags;
    uint16_t step=(flags&0x400u)?0xffffu:1u;
    unsigned row;
    LmnEntityPatternResult out;
#if MUTATION == 1
    qx=(uint16_t)((qx>>2)|((qx&0x8000u)?0xc000u:0u));
    qy=(uint16_t)((qy>>2)|((qy&0x8000u)?0xc000u:0u));
#else
    qx>>=2;
    qy>>=2;
#endif
#if MUTATION == 3
    step=1u;
#endif
    push(memory,ss,&sp,qx);
    push(memory,ss,&sp,call->saved_value);
    product=(uint16_t)((uint32_t)qy*0x1a0u);
    dx=pop(memory,ss,&sp);
    bx=pop(memory,ss,&sp);
    bx=(uint16_t)(bx+product+SEG143E_InteractionCellMapBase);
    push(memory,ss,&sp,si);
    push(memory,ss,&sp,call->saved_destination);
    push(memory,ss,&sp,call->saved_segment);
    push(memory,ss,&sp,ss);
    es=pop(memory,ss,&sp);
    di=bx;
    si=(uint16_t)(si+0x16u);
    for(row=0;row<3;++row) {
        uint16_t value=word(memory,ds,si);
        /* MOVSW reads the whole word before writing, even with overlap/DF. */
        store_word(memory,es,di,value);
        si=(uint16_t)(si+2u*step);
        di=(uint16_t)(di+2u*step);
        memory[physical(es,di)]=memory[physical(ds,si)];
        si=(uint16_t)(si+step);
        di=(uint16_t)(di+step);
        if(row<2) {
            flags=add_flags(flags,di,0x19du);
#if MUTATION == 2
            di=(uint16_t)(di+0x19eu);
#else
            di=(uint16_t)(di+0x19du);
#endif
        }
    }
    out.restored_segment=pop(memory,ss,&sp);
    out.restored_destination=pop(memory,ss,&sp);
    out.record_cursor=pop(memory,ss,&sp);
    out.product=product;
    out.map_offset=bx;
    out.restored_value=dx;
    out.stack_offset=sp;
    out.flags=flags;
    return out;
}

void lmn_copy_entity_pattern_adapter(uint8_t *memory, LmnRegs *r) {
    LmnEntityPatternCall call={r->ds,r->ss,r->sp,r->si,r->di,r->dx,r->es,r->flags};
#if MUTATION == 4
    uint16_t target=word(memory,r->ss,r->sp);
#endif
    LmnEntityPatternResult out=lmn_copy_entity_pattern_core(memory,&call);
    r->ax=out.product;
    r->bx=out.map_offset;
    r->dx=out.restored_value;
    r->si=out.record_cursor;
    r->di=out.restored_destination;
    r->es=out.restored_segment;
    r->sp=out.stack_offset;
    r->flags=out.flags;
#if MUTATION == 4
    r->ip=target;
    r->sp=(uint16_t)(r->sp+2u);
#else
    r->ip=pop(memory,r->ss,&r->sp);
#endif
}

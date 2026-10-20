#include "decimal_digits.h"

#ifndef DECIMAL_MUTATION
#define DECIMAL_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040,
       SF=0x0080, DF=0x0400, OF=0x0800 };
enum { ARITH=CF|PF|AF|ZF|SF|OF };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static void put8(uint8_t *mem,uint16_t segment,uint16_t offset,uint8_t value,
    uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=physical(segment,offset);
    if(bus&&bus->write_byte)bus->write_byte(bus->context,mem,at,value,flags);
    else mem[at]=value;
}

static uint16_t add8_flags(uint16_t flags, uint8_t left, uint8_t right) {
    uint16_t result=(uint16_t)left+right;
    uint8_t value=(uint8_t)result;
    uint16_t arithmetic=(uint16_t)((result>0xffu ? CF:0) |
        ((value==0 ? ZF:0) | (value&SF)) |
        (((left^right^value)&0x10u) ? AF:0) |
        ((~(left^right)&(left^value)&0x80u) ? OF:0));
    unsigned bits=0;
    unsigned n;
    for(n=0;n<8;++n)bits+=(value>>n)&1u;
    if((bits&1u)==0)arithmetic|=PF;
    return (uint16_t)((flags&(uint16_t)~ARITH)|arithmetic);
}

LmnDecimalDigitsResult lmn_write_decimal_digits_bus_core(uint8_t *mem,
    uint16_t segment,uint16_t cursor,uint8_t number,uint16_t flags,const LmnRasterBus *bus) {
    uint8_t hundreds,tens,units;
    LmnDecimalDigitsResult out;
#if DECIMAL_MUTATION == 1
    number=(uint8_t)(number+1u);
#endif
    hundreds=(uint8_t)(number/100u);
    tens=(uint8_t)((number/10u)%10u);
    units=(uint8_t)(number%10u);
    put8(mem,segment,cursor,(uint8_t)(hundreds+'0'),add8_flags(flags,(uint8_t)(hundreds+1u),0x2Fu),bus);
#if DECIMAL_MUTATION == 3
    if(flags&DF) {
        put8(mem,segment,(uint16_t)(cursor-1u),(uint8_t)(tens+'0'),add8_flags(flags,(uint8_t)(tens+1u),0x2Fu),bus);
        put8(mem,segment,(uint16_t)(cursor-2u),(uint8_t)(units+'0'),add8_flags(flags,units,0x30u),bus);
    } else
#endif
    {
        put8(mem,segment,(uint16_t)(cursor+1u),(uint8_t)(tens+'0'),add8_flags(flags,(uint8_t)(tens+1u),0x2Fu),bus);
        put8(mem,segment,(uint16_t)(cursor+2u),(uint8_t)(units+'0'),add8_flags(flags,units,0x30u),bus);
    }
    out.value=(uint16_t)(((uint16_t)(tens+'0')<<8)|(uint16_t)(units+'0'));
    out.cursor=(uint16_t)(cursor+2u);
#if DECIMAL_MUTATION == 2
    out.cursor=(uint16_t)(out.cursor+1u);
#endif
    /* The leaf's last arithmetic instruction is ADD AL,30h. */
    out.flags=add8_flags(flags,units,0x30u);
    return out;
}

LmnDecimalDigitsResult lmn_write_decimal_digits_core(uint8_t *mem,
    uint16_t segment,uint16_t cursor,uint8_t number,uint16_t flags) {
    return lmn_write_decimal_digits_bus_core(mem,segment,cursor,number,flags,0);
}

void lmn_write_decimal_digits_adapter(uint8_t *mem, LmnRegs *r) {
    LmnDecimalDigitsResult out=lmn_write_decimal_digits_core(mem,r->ds,r->si,
        (uint8_t)r->ax,r->flags);
    uint32_t stack=physical(r->ss,r->sp);
    r->ax=out.value;
    r->si=out.cursor;
    r->flags=out.flags;
    /* RET fetches its word after the live DS write, so an alias can change it. */
    r->ip=(uint16_t)(mem[stack]|((uint16_t)mem[(stack+1u)&0xfffffu]<<8));
    r->sp=(uint16_t)(r->sp+2u);
}

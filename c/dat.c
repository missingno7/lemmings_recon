#include "dat.h"
#ifndef MUTATION
#define MUTATION 0
#endif
enum { CF=1,PF=4,AF=16,ZF=64,SF=128,OF=2048,ARITH=0x8d5 };

static uint32_t physical(uint16_t seg,uint16_t off) {
    return (((uint32_t)seg<<4)+off)&0xfffffu;
}
static uint8_t read8(const uint8_t *mem,uint16_t seg,uint16_t off) {
    return mem[physical(seg,off)];
}
static void write8(uint8_t *mem,uint16_t seg,uint16_t off,uint8_t value) {
    mem[physical(seg,off)]=value;
}
static uint16_t read16(const uint8_t *mem,uint16_t seg,uint16_t off) {
    uint32_t at=physical(seg,off);
    return (uint16_t)(mem[at]|((uint16_t)mem[(at+1u)&0xfffffu]<<8));
}
static void write16(uint8_t *mem,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t at=physical(seg,off);mem[at]=(uint8_t)value;
    mem[(at+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static uint16_t szp16(uint16_t value) {
    unsigned i,parity=0;uint16_t out=0;
    for(i=0;i<8;++i)parity^=(value>>i)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

LmnReverseBitsResult lmn_dat_read_bits_core(const uint8_t *mem,uint16_t ds,
    uint16_t cursor,uint8_t remaining,uint8_t shifted_byte,uint8_t checksum,
    uint8_t count,uint16_t flags) {
    LmnReverseBitsResult out={0,cursor,flags,remaining,shifted_byte,checksum};
    uint8_t left=count;unsigned carry=0;
    /* A zero request executes 256 iterations in the original DEC CL loop. */
    do {
        out.remaining=(uint8_t)(out.remaining-1u);
        if(out.remaining==0) {
            out.cursor=(uint16_t)(out.cursor-1u);
            out.shifted_byte=read8(mem,ds,out.cursor);
            out.checksum^=out.shifted_byte;out.remaining=8;
        }
        carry=out.value>>15;
        out.value=(uint16_t)((out.value<<1)|(out.shifted_byte&1u));
        out.shifted_byte>>=1;
        left=(uint8_t)(left-1u);
#if MUTATION == 1
        if(count==0)break;
#endif
    } while(left!=0);
    /* DEC CL 1->0 replaces arithmetic flags except RCL's carry. */
    out.flags=(uint16_t)((flags&(0xffffu^ARITH))|PF|ZF|(carry ? CF:0));
    return out;
}

LmnDatCopyResult lmn_dat_copy_match_core(uint8_t *mem,uint16_t es,
    uint16_t cursor,uint16_t distance,uint16_t count_minus_one,uint16_t flags) {
    uint16_t count=(uint16_t)(count_minus_one+1u),left=count;
    uint16_t source=0,before=0;uint32_t sum=0;uint8_t byte=0;
    do {
        cursor=(uint16_t)(cursor-1u);
        sum=(uint32_t)cursor+distance;before=(uint16_t)sum;
        source=(uint16_t)(before+1u);
#if MUTATION == 2
        source=before;
#endif
        byte=read8(mem,es,source);write8(mem,es,cursor,byte);
        left=(uint16_t)(left-1u);
    } while(left!=0);
    /* Last INC SI supplies flags; carry survives from ADD SI,AX. */
    flags=(uint16_t)((flags&(0xffffu^ARITH))|szp16(source)|
        (sum>0xffffu ? CF:0)|((before&15u)==15u ? AF:0)|
        (before==0x7fffu ? OF:0));
    {
        LmnDatCopyResult out={cursor,source,flags,count,byte};return out;
    }
}

LmnDatCopyResult lmn_dat_write_literal_core(uint8_t *mem,uint16_t es,
    uint16_t cursor,uint8_t value,uint16_t flags) {
    uint16_t before=cursor;cursor=(uint16_t)(cursor-1u);
#if MUTATION == 3
    write8(mem,es,before,value);
#else
    write8(mem,es,cursor,value);
#endif
    flags=(uint16_t)((flags&(0xffffu^ARITH))|(flags&CF)|szp16(cursor)|
        ((before&15u)==0 ? AF:0)|(before==0x8000u ? OF:0));
    { LmnDatCopyResult out={cursor,0,flags,0,value};return out; }
}

static void near_return(uint8_t *mem,LmnRegs *r) {
    r->ip=read16(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);
}
void lmn_dat_read_bits_adapter(uint8_t *mem,LmnRegs *r) {
    LmnReverseBitsResult out=lmn_dat_read_bits_core(mem,r->ds,r->si,
        (uint8_t)(r->cx>>8),(uint8_t)r->dx,(uint8_t)(r->dx>>8),(uint8_t)r->cx,r->flags);
    r->ax=out.value;r->si=out.cursor;r->cx=(uint16_t)((uint16_t)out.remaining<<8);
    r->dx=(uint16_t)(((uint16_t)out.checksum<<8)|out.shifted_byte);r->flags=out.flags;
    near_return(mem,r);
}
void lmn_dat_copy_match_adapter(uint8_t *mem,LmnRegs *r) {
    uint16_t sp=r->sp,count=(uint16_t)(r->bx+1u);
    LmnDatCopyResult out;
    write16(mem,r->ss,(uint16_t)(sp-2u),r->si);
    write16(mem,r->ss,(uint16_t)(sp-4u),r->ds);
    write16(mem,r->ss,(uint16_t)(sp-6u),r->cx);
    write16(mem,r->ss,(uint16_t)(sp-8u),r->es);
    out=lmn_dat_copy_match_core(mem,r->es,r->di,r->ax,r->bx,r->flags);
    r->di=out.cursor;r->flags=out.flags;r->bx=(uint16_t)((count&0xff00u)|out.last_byte);
    /* A live dictionary write can change saved registers before these POPs. */
    r->cx=read16(mem,r->ss,(uint16_t)(sp-6u));
    r->ds=read16(mem,r->ss,(uint16_t)(sp-4u));
    r->si=read16(mem,r->ss,(uint16_t)(sp-2u));
    near_return(mem,r);
}
void lmn_dat_write_literal_adapter(uint8_t *mem,LmnRegs *r) {
    LmnDatCopyResult out=lmn_dat_write_literal_core(mem,r->es,r->di,(uint8_t)r->ax,r->flags);
    r->di=out.cursor;r->flags=out.flags;near_return(mem,r);
}

#include "object_graphics.h"
#include "lemmings_sym.h"

#ifndef OBJECT_MUTATION
#define OBJECT_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040,
       SF=0x0080, DF=0x0400, OF=0x0800 };
enum { ARITH=CF|PF|AF|ZF|SF|OF };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read8(const uint8_t *mem, uint16_t segment, uint16_t offset) {
    return mem[physical(segment,offset)];
}

static void write8(uint8_t *mem, uint16_t segment, uint16_t offset,
                   uint8_t value) {
    mem[physical(segment,offset)]=value;
}

/* Word accesses use two physically consecutive bytes even at offset FFFF. */
static uint16_t read16(const uint8_t *mem, uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    return (uint16_t)(mem[address] |
        ((uint16_t)mem[(address+1u)&0xfffffu] << 8));
}

static void write16(uint8_t *mem, uint16_t segment, uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    mem[address]=(uint8_t)value;
    mem[(address+1u)&0xfffffu]=(uint8_t)(value>>8);
}

static uint16_t push16(uint8_t *mem, uint16_t segment, uint16_t sp,
                       uint16_t value) {
    sp=(uint16_t)(sp-2u);
    write16(mem,segment,sp,value);
    return sp;
}

static uint16_t pop16(const uint8_t *mem, uint16_t segment, uint16_t *sp) {
    uint16_t value=read16(mem,segment,*sp);
    *sp=(uint16_t)(*sp+2u);
    return value;
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t result=(uint32_t)left+right;
    uint16_t value=(uint16_t)result;
    uint16_t arithmetic=(uint16_t)((result>0xffffu ? CF:0) |
        (value==0 ? ZF:0) | ((value&0x8000u) ? SF:0) |
        (((left^right^value)&0x0010u) ? AF:0) |
        (((~(left^right)&(left^value))&0x8000u) ? OF:0));
    unsigned bits=0;
    unsigned n;
    for(n=0;n<8;++n)bits+=(value>>n)&1u;
    if((bits&1u)==0)arithmetic|=PF;
    return (uint16_t)((flags&(uint16_t)~ARITH)|arithmetic);
}

LmnObjectGraphicsResult lmn_copy_object_graphics_core(uint8_t *mem,
    uint16_t data_segment, uint16_t stack_segment, uint16_t stack_offset,
    uint16_t product_high, uint16_t flags) {
    uint16_t ax=0,bx,cx,si,di,es;

    /* PUSH DS / POP ES are live stack operations, including their memory write. */
    stack_offset=push16(mem,stack_segment,stack_offset,data_segment);
    es=pop16(mem,stack_segment,&stack_offset);
    bx=SEG09A9_LevelObjectDefinitions;
    si=SEG09A9_GroundResourceBuffer;
    di=SEG09A9_LevelObjectGraphicsRecords;
    cx=0x0020;

    do {
        uint16_t active_word=(uint16_t)(((uint16_t)read8(mem,data_segment,bx)<<8) |
            read8(mem,data_segment,(uint16_t)(bx+1u)));
        ax=active_word;
        if(active_word!=0) {
            uint16_t type=(uint16_t)(((uint16_t)read8(mem,data_segment,(uint16_t)(bx+4u))<<8) |
                read8(mem,data_segment,(uint16_t)(bx+5u)));
            uint32_t product;
            uint16_t source_step=(flags&DF) ? 0xffffu:1u;
            uint16_t dest_step=source_step;
            unsigned n;
#if OBJECT_MUTATION == 2
            if(type>37u)type=37u;
#endif
            stack_offset=push16(mem,stack_segment,stack_offset,si);
            stack_offset=push16(mem,stack_segment,stack_offset,cx);
            stack_offset=push16(mem,stack_segment,stack_offset,di);
            cx=0x001c;
            product=(uint32_t)type*cx;
            ax=(uint16_t)product;
            product_high=(uint16_t)(product>>16);
            si=(uint16_t)(si+ax);
#if OBJECT_MUTATION == 3
            source_step=1;
            dest_step=1;
#endif
            for(n=0;n<0x1cu;++n) {
                uint8_t value=read8(mem,data_segment,si);
                write8(mem,es,di,value);
                si=(uint16_t)(si+source_step);
                di=(uint16_t)(di+dest_step);
                cx=(uint16_t)(cx-1u);
            }
            di=pop16(mem,stack_segment,&stack_offset);
            cx=pop16(mem,stack_segment,&stack_offset);
            si=pop16(mem,stack_segment,&stack_offset);
        }
#if OBJECT_MUTATION == 1
        else {
            unsigned n;
            for(n=0;n<0x1cu;++n)write8(mem,es,(uint16_t)(di+n),0);
        }
#endif
        bx=(uint16_t)(bx+8u);
        flags=add16_flags(flags,di,0x001cu);
        di=(uint16_t)(di+0x1cu);
        cx=(uint16_t)(cx-1u); /* LOOP changes CX but leaves the ADD flags live. */
    } while(cx!=0);

    {
        LmnObjectGraphicsResult out={
            .value=ax,
            .definition_cursor=bx,
            .count=cx,
            .product_high=product_high,
            .source_cursor=si,
            .output_cursor=di,
            .extra_segment=es,
            .stack_offset=stack_offset,
            .flags=flags
        };
        return out;
    }
}

void lmn_copy_object_graphics_adapter(uint8_t *mem, LmnRegs *r) {
    LmnObjectGraphicsResult out=lmn_copy_object_graphics_core(mem,r->ds,r->ss,
        r->sp,r->dx,r->flags);
    r->ax=out.value;r->bx=out.definition_cursor;r->cx=out.count;
    r->dx=out.product_high;r->si=out.source_cursor;r->di=out.output_cursor;
    r->es=out.extra_segment;r->sp=out.stack_offset;r->flags=out.flags;
    r->ip=read16(mem,r->ss,r->sp);
    r->sp=(uint16_t)(r->sp+2u);
}

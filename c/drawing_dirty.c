#include "drawing_dirty.h"
#include "lemmings_sym.h"

#ifndef DIRTY_MUTATION
#define DIRTY_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040, SF=0x0080,
       IF=0x0200, DF=0x0400, OF=0x0800, ARITH=0x08d5 };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read_byte(uint8_t *memory, const LmnRasterBus *bus,
                         uint32_t address, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address]=value;
}

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset, uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(memory,bus,address,flags);
    uint8_t high=read_byte(memory,bus,(address+1u)&0xfffffu,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_word(uint8_t *memory, const LmnRasterBus *bus,
                       uint16_t segment, uint16_t offset, uint16_t value,
                       uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_byte(memory,bus,address,(uint8_t)value,flags);
    write_byte(memory,bus,(address+1u)&0xfffffu,(uint8_t)(value>>8),flags);
}

static uint16_t push16(uint8_t *memory, const LmnRasterBus *bus,
                       uint16_t segment, uint16_t sp, uint16_t value,
                       uint16_t flags) {
    sp=(uint16_t)(sp-2u);
    write_word(memory,bus,segment,sp,value,flags);
    return sp;
}

static uint16_t pop16(uint8_t *memory, const LmnRasterBus *bus,
                      uint16_t segment, uint16_t *sp, uint16_t flags) {
    uint16_t value=read_word(memory,bus,segment,*sp,flags);
    *sp=(uint16_t)(*sp+2u);
    return value;
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity=0;
    unsigned bit;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    return parity==0u;
}

static uint16_t set_szp(uint16_t flags, uint16_t value, unsigned bits) {
    uint16_t sign=(uint16_t)(1u<<(bits-1u));
    flags=(uint16_t)(flags&(uint16_t)~(PF|ZF|SF));
    if((value&(bits==8u ? 0x00ffu : 0xffffu))==0u)flags|=ZF;
    if(value&sign)flags|=SF;
    if(even_parity8((uint8_t)value))flags|=PF;
    return flags;
}

static uint16_t add_flags(uint16_t flags, uint16_t left, uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u ? 0xffu : 0xffffu;
    uint32_t sign=1u<<(bits-1u);
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)(wide&mask);
    flags=(uint16_t)(flags&(uint16_t)~ARITH);
    flags=set_szp(flags,value,bits);
    if(wide>mask)flags|=CF;
    if(((left^right^value)&0x10u)!=0u)flags|=AF;
    if(((~(left^right)&(left^value))&sign)!=0u)flags|=OF;
    return flags;
}

static uint16_t sub_flags(uint16_t flags, uint16_t left, uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u ? 0xffu : 0xffffu;
    uint32_t sign=1u<<(bits-1u);
    uint16_t value=(uint16_t)(((uint32_t)left-(uint32_t)right)&mask);
    flags=(uint16_t)(flags&(uint16_t)~ARITH);
    flags=set_szp(flags,value,bits);
    if((uint32_t)left<(uint32_t)right)flags|=CF;
    if(((left^right^value)&0x10u)!=0u)flags|=AF;
    if((((left^right)&(left^value))&sign)!=0u)flags|=OF;
    return flags;
}

static uint16_t test_flags(uint16_t flags, uint16_t value, unsigned bits) {
    flags=(uint16_t)(flags&(uint16_t)~(CF|OF));
    return set_szp(flags,value,bits);
}

static uint16_t shift_right_one(uint16_t *value, uint16_t flags) {
    uint16_t before=*value;
    uint16_t after=(uint16_t)(before>>1);
    flags=(uint16_t)(flags&(uint16_t)~(CF|PF|ZF|SF|OF));
    if(before&1u)flags|=CF;
    flags=set_szp(flags,after,16u);
    if(before&0x8000u)flags|=OF;
    *value=after;
    return flags;
}

static uint16_t shift_left_one(uint16_t *value, uint16_t flags) {
    uint16_t before=*value;
    uint16_t after=(uint16_t)(before<<1);
    flags=(uint16_t)(flags&(uint16_t)~(CF|PF|ZF|SF|OF));
    if(before&0x8000u)flags|=CF;
    flags=set_szp(flags,after,16u);
    if(((before^after)&0x8000u)!=0u)flags|=OF;
    *value=after;
    return flags;
}

static uint16_t inc_flags(uint16_t flags, uint16_t before) {
    uint16_t carry=(uint16_t)(flags&CF);
    flags=add_flags(flags,before,1u,16u);
    return (uint16_t)((flags&(uint16_t)~CF)|carry);
}

static uint16_t dec_flags(uint16_t flags, uint16_t before) {
    uint16_t carry=(uint16_t)(flags&CF);
    flags=sub_flags(flags,before,1u,16u);
    return (uint16_t)((flags&(uint16_t)~CF)|carry);
}

LmnDrawingDirtyResult lmn_mark_drawing_dirty_cells_core(uint8_t *memory,
    const LmnDrawingDirtyCall *call, const LmnRasterBus *bus) {
    uint16_t ax=call->left, bx=call->top, cx=call->packed_height;
    uint16_t dx=call->width, si=call->source_cursor;
    uint16_t di=call->destination_cursor, bp=call->control;
    uint16_t sp=call->stack_offset, flags=call->flags;
    uint16_t map_base;

    /* PUSH SI,DI,BP,AX,BX,CX,DX. All writes precede the live DS read. */
    sp=push16(memory,bus,call->stack_segment,sp,si,flags);
    sp=push16(memory,bus,call->stack_segment,sp,di,flags);
    sp=push16(memory,bus,call->stack_segment,sp,bp,flags);
    sp=push16(memory,bus,call->stack_segment,sp,ax,flags);
    sp=push16(memory,bus,call->stack_segment,sp,bx,flags);
    sp=push16(memory,bus,call->stack_segment,sp,cx,flags);
    sp=push16(memory,bus,call->stack_segment,sp,dx,flags);

    flags=sub_flags(flags,ax,0x0010u,16u);
    ax=(uint16_t)(ax-0x0010u);
    if(flags&SF) {
        ax=0;
        /* XOR AX,AX sets CF/PF/ZF/SF/OF; AF is undefined and retained. */
        flags=(uint16_t)(flags&(uint16_t)~(CF|PF|ZF|SF|OF));
        flags|=ZF|PF;
    }

    map_base=read_word(memory,bus,call->data_segment,
                       SEG09A9_DrawingDirtyCellMapOffset,flags);
    si=map_base;
    bp=si;
    flags=add_flags(flags,bp,0x0321u,16u);
    bp=(uint16_t)(bp+0x0321u);
    flags=inc_flags(flags,si);
    si=(uint16_t)(si+1u);

    flags=test_flags(flags,(uint16_t)(ax&0x0007u),16u);
    if(ax&0x0007u) {
        flags=add_flags(flags,dx,0x0008u,16u);
        dx=(uint16_t)(dx+0x0008u);
    }
    flags=shift_right_one(&ax,flags);
    flags=shift_right_one(&ax,flags);
    flags=shift_right_one(&ax,flags);
    flags=add_flags(flags,si,ax,16u);
    si=(uint16_t)(si+ax);

    flags=test_flags(flags,(uint16_t)(bx&0x0007u),16u);
    if(bx&0x0007u) {
        uint8_t cl=(uint8_t)cx;
#if DIRTY_MUTATION == 1
        /* Test mutation: fractional CL rounding saturates instead of wrapping. */
        cl=(uint8_t)(cl>0xf7u ? 0xffu : cl+8u);
#else
        flags=add_flags(flags,cl,0x08u,8u);
        cl=(uint8_t)(cl+8u);
#endif
        cx=(uint16_t)((cx&0xff00u)|cl);
    }
    flags=test_flags(flags,(uint16_t)(bx&0xfff8u),16u);
    bx=(uint16_t)(bx&0xfff8u);
    flags=add_flags(flags,si,bx,16u);
    si=(uint16_t)(si+bx);
    flags=shift_left_one(&bx,flags);
    flags=shift_left_one(&bx,flags);
    flags=add_flags(flags,si,bx,16u);
    si=(uint16_t)(si+bx);

    flags=test_flags(flags,(uint16_t)((uint8_t)cx&0x07u),16u);
    if((uint8_t)cx&0x07u) {
        uint8_t cl=(uint8_t)cx;
#if DIRTY_MUTATION == 1
        /* Same byte-wrap defect at the height-rounding site. */
        cl=(uint8_t)(cl>0xf7u ? 0xffu : cl+8u);
#else
        flags=add_flags(flags,cl,0x08u,8u);
        cl=(uint8_t)(cl+8u);
#endif
        cx=(uint16_t)((cx&0xff00u)|cl);
    }
    cx=(uint16_t)(cx&0x00ffu); /* XOR CH,CH. */
    flags=(uint16_t)(flags&(uint16_t)~(CF|PF|ZF|SF|OF));
    flags|=ZF|PF;
    flags=shift_right_one(&cx,flags);
    flags=shift_right_one(&cx,flags);
    flags=shift_right_one(&cx,flags);

    flags=test_flags(flags,(uint16_t)(dx&0x0007u),16u);
    if(dx&0x0007u) {
        flags=add_flags(flags,dx,0x0008u,16u);
        dx=(uint16_t)(dx+0x0008u);
    }
    flags=shift_right_one(&dx,flags);
    flags=shift_right_one(&dx,flags);
    flags=shift_right_one(&dx,flags);
    ax=(uint16_t)((ax&0xff00u)|0x0001u); /* MOV AL,1. */

    do {
        sp=push16(memory,bus,call->stack_segment,sp,dx,flags);
        sp=push16(memory,bus,call->stack_segment,sp,si,flags);
        do {
            uint16_t target_segment=call->stack_segment;
#if DIRTY_MUTATION == 2
            /* Test mutation: route dirty bytes through DS instead of SS. */
            target_segment=call->data_segment;
#endif
            uint32_t address=physical(target_segment,si);
            write_byte(memory,bus,address,1u,flags);
            flags=inc_flags(flags,si);
            si=(uint16_t)(si+1u);
            flags=dec_flags(flags,dx);
            dx=(uint16_t)(dx-1u);
        } while(dx!=0u);
        si=pop16(memory,bus,call->stack_segment,&sp,flags);
        dx=pop16(memory,bus,call->stack_segment,&sp,flags);
        flags=add_flags(flags,si,0x0028u,16u);
        si=(uint16_t)(si+0x0028u);
        flags=sub_flags(flags,si,bp,16u); /* CMP SI,BP; JNC exits. */
        if(!(flags&CF))break;
        cx=(uint16_t)(cx-1u); /* LOOP does not change flags. */
    } while(cx!=0u);

    /* Final POPs read the live stack; map writes may have changed every word. */
    dx=pop16(memory,bus,call->stack_segment,&sp,flags);
    cx=pop16(memory,bus,call->stack_segment,&sp,flags);
    bx=pop16(memory,bus,call->stack_segment,&sp,flags);
    ax=pop16(memory,bus,call->stack_segment,&sp,flags);
    bp=pop16(memory,bus,call->stack_segment,&sp,flags);
    di=pop16(memory,bus,call->stack_segment,&sp,flags);
    si=pop16(memory,bus,call->stack_segment,&sp,flags);
#if DIRTY_MUTATION == 3
    /* Test mutation: return stale pre-call saved registers after stack aliases. */
    ax=call->left; bx=call->top; cx=call->packed_height; dx=call->width;
    si=call->source_cursor; di=call->destination_cursor; bp=call->control;
#endif
    {
        LmnDrawingDirtyResult result={ax,bx,cx,dx,si,di,bp,sp,flags};
        return result;
    }
}

void lmn_mark_drawing_dirty_cells_adapter(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus) {
    LmnDrawingDirtyCall call={regs->ds,regs->ss,regs->sp,regs->ax,regs->bx,
        regs->cx,regs->dx,regs->si,regs->di,regs->bp,regs->flags};
    LmnDrawingDirtyResult result=
        lmn_mark_drawing_dirty_cells_core(memory,&call,bus);
    uint16_t ret;
    uint32_t address;
    uint8_t low, high;

    regs->ax=result.left;
    regs->bx=result.top;
    regs->cx=result.packed_height;
    regs->dx=result.width;
    regs->si=result.source_cursor;
    regs->di=result.destination_cursor;
    regs->bp=result.control;
    regs->sp=result.stack_offset;
    regs->flags=result.flags;
    address=physical(regs->ss,regs->sp);
    low=read_byte(memory,bus,address,regs->flags);
    high=read_byte(memory,bus,(address+1u)&0xfffffu,regs->flags);
    ret=(uint16_t)(low|((uint16_t)high<<8));
    regs->ip=ret;
    regs->sp=(uint16_t)(regs->sp+2u);
}

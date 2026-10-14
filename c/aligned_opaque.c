#include "aligned_opaque.h"
#include "lemmings_sym.h"

#ifndef OPAQUE_MUTATION
#define OPAQUE_MUTATION 0
#endif

enum { CF=0x001, PF=0x004, AF=0x010, ZF=0x040, SF=0x080,
       IF=0x200, DF=0x400, OF=0x800, ARITH=0x8d5 };

typedef struct OpaqueState {
    uint8_t *mem;
    const LmnRasterBus *bus;
    uint16_t ax,cx,dx,si,di,bp,sp,ds,es,ss,flags;
    uint16_t game_ds;
} OpaqueState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+(uint32_t)offset)&0xfffffu;
}

static uint8_t read_byte(OpaqueState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->mem,address,s->flags);
    return s->mem[address];
}

static void write_byte(OpaqueState *s,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->mem,address,value,s->flags);
    else
        s->mem[address]=value;
}

static uint8_t read8(OpaqueState *s,uint16_t segment,uint16_t offset) {
    return read_byte(s,physical(segment,offset));
}

static uint16_t read16(OpaqueState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(s,address);
    uint8_t high=read_byte(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(OpaqueState *s,uint16_t segment,uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_byte(s,address,(uint8_t)value);
    write_byte(s,address+1u,(uint8_t)(value>>8));
}

static void push(OpaqueState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(OpaqueState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static uint16_t szp(uint16_t value,unsigned width) {
    uint16_t result=0;
    uint8_t low=(uint8_t)value;
    unsigned parity=0;
    unsigned bit;
    for(bit=0;bit<8;++bit) parity^=(low>>bit)&1u;
    if(!parity) result|=PF;
    if(width==8 ? (uint8_t)value==0 : value==0) result|=ZF;
    if(width==8 ? (value&0x80u)!=0 : (value&0x8000u)!=0) result|=SF;
    return result;
}

static void logical_flags(OpaqueState *s,uint16_t value,unsigned width) {
    /* AF is undefined for XOR in the original instruction. Preserve its
       current bit; differential checks do not assign it a defined value. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(value,width));
}

static void add_flags(OpaqueState *s,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum;
    s->flags=(uint16_t)((s->flags&(uint16_t)~ARITH)|szp(value,16)|
        (sum>0xffffu?CF:0u)|((left^right^value)&AF)|
        (((uint16_t)~(left^right)&(left^value)&0x8000u)?OF:0u));
}

static uint8_t dec8(OpaqueState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0?AF:0u)|(before==0x80u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint16_t dec16(OpaqueState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0?AF:0u)|(before==0x8000u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static void output(OpaqueState *s,uint16_t mirror,uint16_t value) {
    write16(s,s->ss,mirror,value);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,value,s->flags);
}

static void draw_rows(OpaqueState *s,int final_plane) {
    uint16_t step=(s->flags&DF)?0xffffu:1u;
    uint8_t rows;
    if(!final_plane) {
        push(s,s->di);
        push(s,s->si);
        push(s,s->cx);
    }
    for(;;) {
        push(s,s->cx);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        s->flags=(uint16_t)(s->flags&(uint16_t)~IF); /* CLI */
        do {
#if OPAQUE_MUTATION != 1
            s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->es,s->di));
#endif
            {
                uint8_t source=read8(s,s->ds,s->si);
                write_byte(s,physical(s->es,s->di),source);
            }
            s->si=(uint16_t)(s->si+step);
            s->di=(uint16_t)(s->di+step);
            s->cx=(uint16_t)(s->cx-1u); /* LOOP changes no flags. */
        } while(s->cx!=0);
        s->flags=(uint16_t)(s->flags|IF); /* STI */

        push(s,s->ds);
        s->ax=s->game_ds;
        s->ds=s->ax;
        {
            uint16_t before=s->si;
            uint16_t advance=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
            s->si=(uint16_t)(before+advance);
            add_flags(s,before,advance);
        }
        {
            uint16_t before=s->di;
            uint16_t advance=read16(s,s->ds,SEG09A9_DrawingActiveDestinationRowAdvance);
            s->di=(uint16_t)(before+advance);
            add_flags(s,before,advance);
        }
#if OPAQUE_MUTATION == 2
        (void)pop(s); /* Leave DS at the temporary game segment. */
#else
        s->ds=pop(s);
#endif
        s->cx=pop(s);
        rows=dec8(s,(uint8_t)(s->cx>>8));
        s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)rows<<8));
        if(rows==0) break;
    }
    if(!final_plane) {
        s->cx=pop(s);
        s->si=pop(s);
        s->di=pop(s);
        s->bp=dec16(s,s->bp);
    }
}

LmnAlignedOpaqueResult lmn_draw_aligned_opaque_core(
    uint8_t *memory,const LmnAlignedOpaqueCall *call,const LmnRasterBus *bus) {
    OpaqueState s={memory,bus,0,call->packed_counts,call->width_state,
        call->source_cursor,call->destination_cursor,0,call->stack_offset,
        0,0,call->stack_segment,call->flags,call->game_data_segment};
    uint16_t source_row_advance;
    push(&s,call->initial_data_segment);
    s.ds=read16(&s,call->initial_data_segment,SEG09A9_GraphicsResourceSegment);
    s.ax=0xa000u;
    s.es=s.ax;
    {
        uint8_t low=(uint8_t)s.dx,high=(uint8_t)(s.dx>>8);
        s.dx=(uint16_t)(((uint16_t)low<<8)|high); /* XCHG DL,DH */
        s.dx=(uint16_t)(s.dx&0x00ffu); /* XOR DH,DH */
        logical_flags(&s,0,8);
        s.bp=s.dx;
    }
    s.dx=0x03c4u;
    s.ax=0x0f02u;
    output(&s,SEG143E_VgaMapMaskMirror,s.ax);
    s.dx=0x03ceu;
    s.ax=0;
    logical_flags(&s,0,16); /* XOR AX,AX */
    output(&s,SEG143E_VgaSetResetMirror,s.ax);
    s.ax=0x0e01u;
    output(&s,SEG143E_VgaEnableSetResetMirror,s.ax);
    s.ax=0x0005u;
    output(&s,SEG143E_VgaGraphicsModeMirror,s.ax);
    s.ax=0x0003u;
    output(&s,SEG143E_VgaDataRotateMirror,s.ax);
    s.ax=0xff08u;
    output(&s,SEG143E_VgaBitMaskMirror,s.ax);

    draw_rows(&s,0);
    if(s.bp!=0) {
        push(&s,s.ds);
        s.ax=s.game_ds;
        s.ds=s.ax;
        {
            uint16_t before=s.si;
            source_row_advance=read16(&s,s.ds,SEG09A9_DrawingSourcePlaneExtent);
            s.si=(uint16_t)(before+source_row_advance);
            add_flags(&s,before,source_row_advance);
        }
        s.ds=pop(&s);
        s.ax=0x0001u;
        output(&s,SEG143E_VgaEnableSetResetMirror,s.ax);
        s.dx=(uint16_t)((s.dx&0xff00u)|0x00c4u);
        s.ax=0x0202u;
        output(&s,SEG143E_VgaMapMaskMirror,s.ax);

        draw_rows(&s,0);
        if(s.bp!=0) {
            push(&s,s.ds);
            s.ax=s.game_ds;
            s.ds=s.ax;
            {
                uint16_t before=s.si;
                source_row_advance=read16(&s,s.ds,SEG09A9_DrawingSourcePlaneExtent);
                s.si=(uint16_t)(before+source_row_advance);
                add_flags(&s,before,source_row_advance);
            }
            s.ds=pop(&s);
            s.ax=0x0402u;
            output(&s,SEG143E_VgaMapMaskMirror,s.ax);

            draw_rows(&s,0);
            if(s.bp!=0) {
                push(&s,s.ds);
                s.ax=s.game_ds;
                s.ds=s.ax;
                {
                    uint16_t before=s.si;
                    source_row_advance=read16(&s,s.ds,SEG09A9_DrawingSourcePlaneExtent);
                    s.si=(uint16_t)(before+source_row_advance);
                    add_flags(&s,before,source_row_advance);
                }
                s.ds=pop(&s);
#if OPAQUE_MUTATION == 3
                s.ax=0x0402u;
#else
                s.ax=0x0802u;
#endif
                output(&s,SEG143E_VgaMapMaskMirror,s.ax);
                draw_rows(&s,1);
            }
        }
    }
    s.ds=pop(&s);
    {
        LmnAlignedOpaqueResult result={s.ax,s.cx,s.dx,s.si,s.di,s.bp,s.sp,
            s.ds,s.es,s.flags};
        return result;
    }
}

void lmn_draw_aligned_opaque_adapter(uint8_t *memory,LmnRegs *regs,
    uint16_t game_data_segment,const LmnRasterBus *bus) {
    LmnAlignedOpaqueCall call={regs->ds,game_data_segment,regs->ss,regs->sp,
        regs->cx,regs->dx,regs->si,regs->di,regs->flags};
    LmnAlignedOpaqueResult result=lmn_draw_aligned_opaque_core(memory,&call,bus);
    OpaqueState s={memory,bus,result.work_value,result.packed_counts,result.port,
        result.source_cursor,result.destination_cursor,result.plane_counter,
        result.stack_offset,result.source_segment,result.output_segment,regs->ss,
        result.flags,game_data_segment};
    uint16_t ip=read16(&s,s.ss,s.sp);
    s.sp=(uint16_t)(s.sp+2u);
    regs->ip=ip;
    regs->cs=read16(&s,s.ss,s.sp);
    s.sp=(uint16_t)(s.sp+2u);
    regs->ax=result.work_value;
    regs->cx=result.packed_counts;
    regs->dx=result.port;
    regs->si=result.source_cursor;
    regs->di=result.destination_cursor;
    regs->bp=result.plane_counter;
    regs->sp=s.sp;
    regs->ds=result.source_segment;
    regs->es=result.output_segment;
    regs->flags=result.flags;
}

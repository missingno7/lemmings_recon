#include "aligned_masked.h"
#include "lemmings_sym.h"

#ifndef MASKED_MUTATION
#define MASKED_MUTATION 0
#endif

enum { CF=0x001, PF=0x004, AF=0x010, ZF=0x040, SF=0x080,
       IF=0x200, DF=0x400, OF=0x800, ARITH=0x8d5 };

typedef struct MaskedState {
    uint8_t *mem;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp,sp,ds,es,ss,flags;
    uint16_t game_ds;
} MaskedState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+(uint32_t)offset)&0xfffffu;
}

static uint8_t read_byte(MaskedState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->mem,address,s->flags);
    return s->mem[address];
}

static void write_byte(MaskedState *s,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->mem,address,value,s->flags);
    else
        s->mem[address]=value;
}

static uint8_t read8(MaskedState *s,uint16_t segment,uint16_t offset) {
    return read_byte(s,physical(segment,offset));
}

static uint16_t read16(MaskedState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(s,address);
    uint8_t high=read_byte(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(MaskedState *s,uint16_t segment,uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_byte(s,address,(uint8_t)value);
    write_byte(s,address+1u,(uint8_t)(value>>8));
}

static void push(MaskedState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(MaskedState *s) {
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

static void logical_flags(MaskedState *s,uint16_t value,unsigned width) {
    /* AF is undefined for XOR in the original instruction. Keep its current
       bit while replacing the other defined logical-result flags. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(value,width));
}

static void add_flags(MaskedState *s,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum;
    s->flags=(uint16_t)((s->flags&(uint16_t)~ARITH)|szp(value,16)|
        (sum>0xffffu?CF:0u)|((left^right^value)&AF)|
        (((uint16_t)~(left^right)&(left^value)&0x8000u)?OF:0u));
}

static uint16_t inc16(MaskedState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fffu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t dec8(MaskedState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0?AF:0u)|(before==0x80u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint16_t dec16(MaskedState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0?AF:0u)|(before==0x8000u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static void output(MaskedState *s,uint16_t mirror,uint16_t value) {
    write16(s,s->ss,mirror,value);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,value,s->flags);
}

static uint16_t direction_step(const MaskedState *s) {
    return (s->flags&DF)?0xffffu:1u;
}

static void move_source_byte(MaskedState *s) {
    uint8_t source=read8(s,s->ds,s->si);
    s->ax=(uint16_t)((s->ax&0xff00u)|source); /* LODSB updates AL. */
    uint16_t step=direction_step(s);
    s->si=(uint16_t)(s->si+step);
    write_byte(s,physical(s->es,s->di),source);
    s->di=(uint16_t)(s->di+step);
}

static void masked_first_pass(MaskedState *s) {
    uint8_t rows;
    push(s,s->di);
    push(s,s->si);
    push(s,s->cx);
    for(;;) {
        push(s,s->cx);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        do {
            uint8_t mask=read8(s,s->ds,s->bx);
            s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)mask<<8)); /* MOV AH,[BX]. */
            s->bx=inc16(s,s->bx); /* INC BX preserves CF. */
            s->ax=(uint16_t)((s->ax&0xff00u)|0x0008u); /* MOV AL,8. */
            write16(s,s->ss,SEG143E_VgaBitMaskMirror,s->ax);
            if(s->bus&&s->bus->out_word)
                s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
            s->flags=(uint16_t)(s->flags&(uint16_t)~IF); /* CLI */
#if MASKED_MUTATION != 1
            s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->es,s->di));
#endif
            move_source_byte(s); /* LODSB then STOSB, with live DF. */
            s->flags=(uint16_t)(s->flags|IF); /* STI, once per byte. */
            s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves flags. */
        } while(s->cx!=0);

        push(s,s->ds);
        s->ax=s->game_ds;
        s->ds=s->ax;
        s->ax=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
        {
            uint16_t before=s->si;
            s->si=(uint16_t)(before+s->ax);
            add_flags(s,before,s->ax);
        }
        {
            uint16_t before=s->bx;
            s->bx=(uint16_t)(before+s->ax);
            add_flags(s,before,s->ax);
        }
        {
            uint16_t before=s->di;
            uint16_t advance=read16(s,s->ds,SEG09A9_DrawingActiveDestinationRowAdvance);
            s->di=(uint16_t)(before+advance);
            add_flags(s,before,advance);
        }
#if MASKED_MUTATION == 2
        (void)pop(s); /* Deliberately leave DS at the temporary game segment. */
#else
        s->ds=pop(s);
#endif
        s->cx=pop(s);
        rows=dec8(s,(uint8_t)(s->cx>>8));
        s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)rows<<8));
        if(rows==0) break;
    }
    s->cx=pop(s);
    s->si=pop(s);
    s->di=pop(s);
    s->bp=dec16(s,s->bp);
}

static void masked_later_rows(MaskedState *s,int final_plane) {
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
        s->flags=(uint16_t)(s->flags&(uint16_t)~IF); /* CLI once per row. */
        do {
            s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->es,s->di));
            move_source_byte(s);
            s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves flags. */
        } while(s->cx!=0);
        s->flags=(uint16_t)(s->flags|IF); /* STI once per row. */

        push(s,s->ds);
        s->ax=s->game_ds;
        s->ds=s->ax;
        s->ax=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
        {
            uint16_t before=s->si;
            s->si=(uint16_t)(before+s->ax);
            add_flags(s,before,s->ax);
        }
        {
            uint16_t before=s->di;
            uint16_t advance=read16(s,s->ds,SEG09A9_DrawingActiveDestinationRowAdvance);
            s->di=(uint16_t)(before+advance);
            add_flags(s,before,advance);
        }
        s->ds=pop(s);
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

static void advance_plane_source(MaskedState *s) {
    push(s,s->ds);
    s->ax=s->game_ds;
    s->ds=s->ax;
    {
        uint16_t before=s->si;
        uint16_t extent=read16(s,s->ds,SEG09A9_DrawingSourcePlaneExtent);
        s->si=(uint16_t)(before+extent);
        add_flags(s,before,extent);
    }
    s->ds=pop(s);
}

LmnAlignedMaskedResult lmn_draw_aligned_masked_core(
    uint8_t *memory,const LmnAlignedMaskedCall *call,const LmnRasterBus *bus) {
    MaskedState s={memory,bus,0,call->mask_cursor,call->packed_counts,
        call->width_state,call->source_cursor,call->destination_cursor,0,
        call->stack_offset,0,0,call->stack_segment,call->flags,
        call->game_data_segment};
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

    masked_first_pass(&s);
    if(s.bp!=0) {
        advance_plane_source(&s);
        s.ax=0x0001u;
        output(&s,SEG143E_VgaEnableSetResetMirror,s.ax);
        s.ax=0x1003u;
        output(&s,SEG143E_VgaDataRotateMirror,s.ax);
        s.ax=0xff08u;
        output(&s,SEG143E_VgaBitMaskMirror,s.ax);
        s.dx=(uint16_t)((s.dx&0xff00u)|0x00c4u);
        s.ax=0x0202u;
        output(&s,SEG143E_VgaMapMaskMirror,s.ax);

        masked_later_rows(&s,0);
        if(s.bp!=0) {
            advance_plane_source(&s);
            s.ax=0x0402u;
            output(&s,SEG143E_VgaMapMaskMirror,s.ax);

            masked_later_rows(&s,0);
            if(s.bp!=0) {
                advance_plane_source(&s);
#if MASKED_MUTATION == 3
                s.ax=0x0402u;
#else
                s.ax=0x0802u;
#endif
                output(&s,SEG143E_VgaMapMaskMirror,s.ax);
                masked_later_rows(&s,1);
            }
        }
    }
    s.ds=pop(&s);
    {
        LmnAlignedMaskedResult result={s.ax,s.cx,s.dx,s.si,s.bx,s.di,
            s.bp,s.sp,s.ds,s.es,s.flags};
        return result;
    }
}

void lmn_draw_aligned_masked_adapter(uint8_t *memory,LmnRegs *regs,
    uint16_t game_data_segment,const LmnRasterBus *bus) {
    LmnAlignedMaskedCall call={regs->ds,game_data_segment,regs->ss,regs->sp,
        regs->cx,regs->dx,regs->si,regs->bx,regs->di,regs->flags};
    LmnAlignedMaskedResult result=lmn_draw_aligned_masked_core(memory,&call,bus);
    MaskedState s={memory,bus,result.work_value,result.mask_cursor,
        result.packed_counts,result.port,result.source_cursor,
        result.destination_cursor,result.plane_counter,result.stack_offset,
        result.source_segment,result.output_segment,regs->ss,result.flags,
        game_data_segment};
    uint16_t ip=read16(&s,s.ss,s.sp);
    s.sp=(uint16_t)(s.sp+2u);
    regs->ip=ip;
    regs->cs=read16(&s,s.ss,s.sp);
    s.sp=(uint16_t)(s.sp+2u);
    regs->ax=result.work_value;
    regs->bx=result.mask_cursor;
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

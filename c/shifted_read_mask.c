#include "shifted_read_mask.h"
#include "lemmings_sym.h"

#ifndef SHIFTED_READ_MASK_MUTATION
#define SHIFTED_READ_MASK_MUTATION 0
#endif

enum { CF=0x001, PF=0x004, AF=0x010, ZF=0x040, SF=0x080,
       IF=0x200, DF=0x400, OF=0x800, ARITH=0x8d5 };

typedef struct ShiftedReadMaskState {
    uint8_t *mem;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp,sp,ds,es,ss,flags;
} ShiftedReadMaskState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+(uint32_t)offset)&0xfffffu;
}

static uint8_t read_byte(ShiftedReadMaskState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->mem,address,s->flags);
    return s->mem[address];
}

static void write_byte(ShiftedReadMaskState *s,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->mem,address,value,s->flags);
    else
        s->mem[address]=value;
}

static uint8_t read8(ShiftedReadMaskState *s,uint16_t segment,uint16_t offset) {
    return read_byte(s,physical(segment,offset));
}

static uint16_t read16(ShiftedReadMaskState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(s,address);
    uint8_t high=read_byte(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ShiftedReadMaskState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_byte(s,address,(uint8_t)value);
    write_byte(s,address+1u,(uint8_t)(value>>8));
}

static void push(ShiftedReadMaskState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(ShiftedReadMaskState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static uint16_t szp(uint16_t value,unsigned width) {
    uint16_t result=0;
    uint8_t low=(uint8_t)value;
    unsigned parity=0,bit;
    for(bit=0;bit<8;++bit) parity^=(low>>bit)&1u;
    if(!parity) result|=PF;
    if(width==8 ? (uint8_t)value==0 : value==0) result|=ZF;
    if(width==8 ? (value&0x80u)!=0 : (value&0x8000u)!=0) result|=SF;
    return result;
}

static void logical_flags(ShiftedReadMaskState *s,uint16_t value,unsigned width) {
    /* AF is undefined for the XOR/AND instructions; retain its physical bit. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(value,width));
}

static uint16_t dec16(ShiftedReadMaskState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0?AF:0u)|(before==0x8000u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t dec8(ShiftedReadMaskState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0?AF:0u)|(before==0x80u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint16_t inc16(ShiftedReadMaskState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fffu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t inc8(ShiftedReadMaskState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static void add16(ShiftedReadMaskState *s,uint16_t *target,uint16_t value) {
    uint16_t before=*target;
    uint32_t sum=(uint32_t)before+(uint32_t)value;
    uint16_t result=(uint16_t)sum;
    s->flags=(uint16_t)((s->flags&(uint16_t)~ARITH)|szp(result,16)|
        (sum>0xffffu?CF:0u)|((before^value^result)&AF)|
        (((uint16_t)~(before^value)&(before^result)&0x8000u)?OF:0u));
    *target=result;
}

static uint8_t shr1(ShiftedReadMaskState *s,uint8_t value) {
    uint8_t result=(uint8_t)(value>>1);
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(result,8)|(value&1u)|((value&0x80u)?OF:0u));
    return result;
}

static uint8_t rcr1(ShiftedReadMaskState *s,uint8_t value) {
    uint8_t carry=(uint8_t)(s->flags&CF);
    uint8_t result=(uint8_t)((value>>1)|(carry?0x80u:0u));
#if SHIFTED_READ_MASK_MUTATION == 1
    result=(uint8_t)(value>>1); /* Deliberately lose the preceding carry. */
#endif
    {
        uint16_t changed=(uint16_t)((s->flags&(uint16_t)~(CF|OF))|
            (value&1u));
        if(((result>>7)^((result>>6)&1u))!=0) changed|=OF;
        s->flags=changed;
    }
    return result;
}

static void and_flags8(ShiftedReadMaskState *s,uint8_t value) {
    logical_flags(s,value,8);
}

static void output(ShiftedReadMaskState *s,uint16_t mirror,uint16_t value) {
    write16(s,s->ss,mirror,value);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,value,s->flags);
}

static uint16_t direction_step(const ShiftedReadMaskState *s) {
    return (s->flags&DF)?0xffffu:1u;
}

static void movsb(ShiftedReadMaskState *s) {
    uint8_t value=read8(s,s->ds,s->si);
    uint16_t step=direction_step(s);
    s->si=(uint16_t)(s->si+step);
    write_byte(s,physical(s->es,s->di),value);
    s->di=(uint16_t)(s->di+step);
}

static void stosb(ShiftedReadMaskState *s,uint8_t value) {
    write_byte(s,physical(s->es,s->di),value);
    s->di=(uint16_t)(s->di+direction_step(s));
}

static void lodsb(ShiftedReadMaskState *s) {
    uint8_t value=read8(s,s->ds,s->si);
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
    s->si=(uint16_t)(s->si+direction_step(s));
}

static void shiftright_scratch(ShiftedReadMaskState *s,int use_si) {
    uint8_t shifts=(uint8_t)s->ax;
    do {
        uint16_t saved_cursor;
        push(s,use_si?s->si:s->bx);
        push(s,s->cx);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        saved_cursor=use_si?s->si:s->bx;
        {
            uint8_t value=read8(s,s->ds,saved_cursor);
            uint16_t access_flags=s->flags;
            uint8_t shifted=shr1(s,value);
            uint16_t result_flags=s->flags;
            s->flags=access_flags;
            write_byte(s,physical(s->ds,saved_cursor),shifted);
            s->flags=result_flags;
        }
        if(use_si) s->si=inc16(s,s->si);
        else s->bx=inc16(s,s->bx);
        do {
            saved_cursor=use_si?s->si:s->bx;
            {
                uint8_t value=read8(s,s->ds,saved_cursor);
                uint16_t access_flags=s->flags;
                uint8_t shifted=rcr1(s,value);
                uint16_t result_flags=s->flags;
                /* Unicorn's memory hook observes flags from instruction entry. */
                s->flags=access_flags;
                write_byte(s,physical(s->ds,saved_cursor),shifted);
                s->flags=result_flags;
            }
            if(use_si) s->si=inc16(s,s->si);
            else s->bx=inc16(s,s->bx);
            s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves flags. */
        } while(s->cx!=0);
        s->cx=pop(s);
        if(use_si) s->si=pop(s);
        else s->bx=pop(s);
        shifts=dec8(s,shifts);
        s->ax=(uint16_t)((s->ax&0xff00u)|shifts);
    } while(shifts!=0);
}

static void copy_scratch_row(ShiftedReadMaskState *s,uint16_t scratch) {
    push(s,s->ds);
    push(s,s->es);
    push(s,s->cx);
    push(s,s->cx);
    push(s,s->di);
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8); /* XOR CH,CH */
    s->di=scratch;
    while(s->cx!=0) {
        movsb(s);
        s->cx=(uint16_t)(s->cx-1u); /* REP count; flags are unchanged. */
    }
    s->ax&=0xff00u;
    logical_flags(s,0,8); /* XOR AL,AL */
    stosb(s,0);
    s->di=pop(s);
    s->cx=pop(s);
    push(s,s->si);
    push(s,s->es);
    s->ds=pop(s);
    s->ax=0xa000u;
    s->es=s->ax;
}

static void prepare_mask_cache(ShiftedReadMaskState *s) {
    push(s,s->cx);
    push(s,s->bp);
    push(s,s->di);
    push(s,s->si);
    s->bp=SEG09A9_DrawingMaskRowScratch; /* LEA BP,[6748]. */
    for(;;) {
        uint8_t rows;
        push(s,s->cx);
        push(s,s->ds);
        push(s,s->es);
        push(s,s->cx);
        push(s,s->di);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        s->di=s->bp;
        s->si=s->bx;
        s->bx=s->bp;
        while(s->cx!=0) {
            movsb(s);
            s->cx=(uint16_t)(s->cx-1u);
        }
        s->ax&=0xff00u;
        logical_flags(s,0,8); /* XOR AL,AL */
        stosb(s,0);
        s->bp=s->di;
        s->di=pop(s);
        s->cx=pop(s);
        push(s,s->si);
        push(s,s->es);
        s->ds=pop(s);
        s->ax=0xa000u;
        s->es=s->ax;
        s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->ds,
            SEG09A9_DrawingLeftBitShiftByte));
        shiftright_scratch(s,0);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        {
            uint8_t before=(uint8_t)s->cx;
            uint8_t low=inc8(s,before);
            s->cx=(uint16_t)((s->cx&0xff00u)|low);
        }
        do {
            uint8_t gate=read8(s,s->es,s->di); /* VGA read mode 1 loads latches. */
            s->ax=(uint16_t)((s->ax&0xff00u)|gate);
            uint8_t mask=read8(s,s->ds,s->bx);
            uint8_t result=(uint8_t)(mask&gate);
            write_byte(s,physical(s->ds,s->bx),result);
            and_flags8(s,result);
            s->bx=inc16(s,s->bx);
            s->di=inc16(s,s->di); /* This cache pass is forward regardless of DF. */
            s->cx=(uint16_t)(s->cx-1u);
        } while(s->cx!=0);
        s->bx=pop(s); /* Restores the mask source after REP MOVSB. */
#if SHIFTED_READ_MASK_MUTATION == 2
        /* Mutation omits ADD BX,[DS:6702] after each mask source row. */
#else
        {
            uint16_t advance=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
            add16(s,&s->bx,advance);
        }
#endif
        {
            uint16_t advance=read16(s,s->ds,
                SEG09A9_DrawingActiveDestinationRowAdvance);
            add16(s,&s->di,advance);
        }
        s->es=pop(s);
        s->ds=pop(s);
        s->cx=pop(s); /* The original CX saved before this row. */
        rows=dec8(s,(uint8_t)(s->cx>>8));
        s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)rows<<8));
        if(rows==0) break;
    }
    s->si=pop(s);
    s->di=pop(s);
    s->bp=pop(s);
    s->cx=pop(s);
    s->bx=SEG09A9_DrawingMaskRowScratch;
}

static void draw_source_rows(ShiftedReadMaskState *s,unsigned plane) {
    /* 8F9B is the terminal path: unlike the three preceding bodies it has
       no outer cursor/count save frame, so the final live cursors escape. */
    if(plane!=3u) {
        push(s,s->di);
        push(s,s->si);
        push(s,s->cx);
        push(s,s->bx);
    }
    for(;;) {
        uint8_t rows;
        copy_scratch_row(s,SEG09A9_DrawingSourceRowScratch);
        s->si=SEG09A9_DrawingSourceRowScratch;
        s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->ds,
            SEG09A9_DrawingLeftBitShiftByte));
        shiftright_scratch(s,1);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        {
            uint8_t before=(uint8_t)s->cx;
            uint8_t low=inc8(s,before);
            s->cx=(uint16_t)((s->cx&0xff00u)|low);
        }
        if(plane==1u) s->flags=(uint16_t)(s->flags&~IF); /* CLI at 8EF0. */
        do {
            uint8_t mask;
            if(plane==0u) {
                mask=read8(s,s->ds,s->bx);
                s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)mask<<8));
                s->bx=inc16(s,s->bx);
                s->ax=(uint16_t)((s->ax&0xff00u)|0x0008u);
                output(s,SEG143E_VgaBitMaskMirror,s->ax);
                s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->es,s->di));
            } else if(plane==3u) {
                s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->es,s->di));
                mask=read8(s,s->ds,s->bx);
                s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)mask<<8));
                s->bx=inc16(s,s->bx);
            } else {
                /* The middle passes read the destination into AH, then replace
                   AH with the mask byte before consuming the source scratch. */
                s->ax=(uint16_t)((s->ax&0x00ffu)|
                    ((uint16_t)read8(s,s->es,s->di)<<8));
                mask=read8(s,s->ds,s->bx);
                s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)mask<<8));
                s->bx=inc16(s,s->bx);
            }
            mask=(uint8_t)(s->ax>>8);
            lodsb(s);
            s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)mask<<8));
            {
                uint8_t value=(uint8_t)((s->ax&0xffu)&mask);
                s->ax=(uint16_t)((s->ax&0xff00u)|value);
                and_flags8(s,value);
                stosb(s,value);
            }
            s->cx=(uint16_t)(s->cx-1u);
        } while(s->cx!=0);
        if(plane==1u) s->flags=(uint16_t)(s->flags|IF); /* STI at 8EFD. */
        s->si=pop(s); /* Restores the source cursor after REP MOVSB. */
        {
            uint16_t advance=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
            add16(s,&s->si,advance);
        }
        {
            uint16_t advance=read16(s,s->ds,
                SEG09A9_DrawingActiveDestinationRowAdvance);
            add16(s,&s->di,advance);
        }
        s->cx=pop(s);
        s->es=pop(s);
        s->ds=pop(s);
        rows=dec8(s,(uint8_t)(s->cx>>8));
        s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)rows<<8));
        if(rows==0) break;
    }
    if(plane!=3u) {
        s->bx=pop(s);
        s->cx=pop(s);
        s->si=pop(s);
        s->di=pop(s);
    }
}

static void advance_plane_source(ShiftedReadMaskState *s) {
#if SHIFTED_READ_MASK_MUTATION == 3
    (void)s; /* Deliberately omit the live ES:66F8 advance between planes. */
#else
    uint16_t advance=read16(s,s->es,SEG09A9_DrawingSourcePlaneExtent);
    add16(s,&s->si,advance);
#endif
}

static LmnShiftedReadMaskResult run_shifted_read_mask(uint8_t *memory,
    const LmnShiftedReadMaskCall *call,const LmnRasterBus *bus) {
    ShiftedReadMaskState s={memory,bus,0,call->mask_cursor,call->packed_counts,
        call->width_state,call->source_cursor,call->destination_cursor,0,
        call->stack_offset,call->initial_data_segment,0,call->stack_segment,
        call->flags};
    uint16_t entry_row_advance;

    /* DEC [DS:6704] happens before the original DS is saved or changed. */
    entry_row_advance=read16(&s,s.ds,
        SEG09A9_DrawingActiveDestinationRowAdvance);
    write16(&s,s.ds,SEG09A9_DrawingActiveDestinationRowAdvance,
        (uint16_t)(entry_row_advance-1u));
    s.flags=(uint16_t)((s.flags&(uint16_t)~(PF|AF|ZF|SF|OF))|
        szp((uint16_t)(entry_row_advance-1u),16)|
        ((entry_row_advance&0x0fu)==0?AF:0u)|
        (entry_row_advance==0x8000u?OF:0u));
    push(&s,s.ds);
    s.ds=read16(&s,s.ds,SEG09A9_GraphicsResourceSegment);
    s.ax=call->game_data_segment;
    s.es=call->game_data_segment; /* MOV AX,relocated 09A9; MOV ES,AX. */
    {
        uint8_t low=(uint8_t)s.dx,high=(uint8_t)(s.dx>>8);
        s.dx=(uint16_t)(((uint16_t)low<<8)|high); /* XCHG DL,DH. */
        s.dx=(uint16_t)(s.dx&0x00ffu); /* XOR DH,DH. */
        logical_flags(&s,0,8);
        s.bp=s.dx;
    }
    s.flags=(uint16_t)(s.flags&~IF); /* CLI. */
    s.dx=0x03c4u;
    s.ax=0x0f02u;
    output(&s,SEG143E_VgaMapMaskMirror,s.ax);
    s.dx=0x03ceu;
    s.ax=0;
    logical_flags(&s,0,16); /* XOR AX,AX. */
    output(&s,SEG143E_VgaSetResetMirror,s.ax);
    s.ax=0x0e01u; output(&s,SEG143E_VgaEnableSetResetMirror,s.ax);
    s.ax=0x0003u; output(&s,SEG143E_VgaDataRotateMirror,s.ax);
    s.ax=0x0805u; output(&s,SEG143E_VgaGraphicsModeMirror,s.ax);
    s.ax=0x0807u; output(&s,SEG143E_VgaColorCareMirror,s.ax);
    s.ax=0x0802u; output(&s,SEG143E_VgaColorCompareMirror,s.ax);

    prepare_mask_cache(&s);

    draw_source_rows(&s,0u);
    s.bp=dec16(&s,s.bp);
    if(s.bp!=0) {
        advance_plane_source(&s);
        s.ax=0x1003u; output(&s,SEG143E_VgaDataRotateMirror,s.ax);
        s.ax=0xff08u; output(&s,SEG143E_VgaBitMaskMirror,s.ax);
        s.ax=0x0001u; output(&s,SEG143E_VgaEnableSetResetMirror,s.ax);
        s.dx=(uint16_t)((s.dx&0xff00u)|0x00c4u);
        s.ax=0x0202u; output(&s,SEG143E_VgaMapMaskMirror,s.ax);
        draw_source_rows(&s,1u);
        s.bp=dec16(&s,s.bp);
        if(s.bp!=0) {
            advance_plane_source(&s);
            s.ax=0x0402u; output(&s,SEG143E_VgaMapMaskMirror,s.ax);
            draw_source_rows(&s,2u);
            s.bp=dec16(&s,s.bp);
            if(s.bp!=0) {
                advance_plane_source(&s);
                s.ax=0x0802u; output(&s,SEG143E_VgaMapMaskMirror,s.ax);
                draw_source_rows(&s,3u);
            }
        }
    }
    s.flags=(uint16_t)(s.flags|IF); /* Shared STI at 8FF4, even when IF started clear. */
    s.ds=pop(&s);
    {
        LmnShiftedReadMaskResult result={s.ax,s.cx,s.dx,s.si,s.bx,s.di,
            s.bp,s.sp,s.ds,s.es,s.flags};
        return result;
    }
}

LmnShiftedReadMaskResult lmn_draw_shifted_read_mask_core(uint8_t *memory,
    const LmnShiftedReadMaskCall *call,const LmnRasterBus *bus) {
    return run_shifted_read_mask(memory,call,bus);
}

void lmn_draw_shifted_read_mask_adapter(uint8_t *memory,LmnRegs *regs,
    uint16_t game_data_segment,const LmnRasterBus *bus) {
    LmnShiftedReadMaskCall call={regs->ds,game_data_segment,regs->ss,regs->sp,
        regs->cx,regs->dx,regs->si,regs->bx,regs->di,regs->flags};
    LmnShiftedReadMaskResult result=run_shifted_read_mask(memory,&call,bus);
    ShiftedReadMaskState s={memory,bus,result.work_value,result.mask_cursor,
        result.packed_counts,result.port,result.source_cursor,
        result.destination_cursor,result.plane_counter,result.stack_offset,
        result.source_segment,result.output_segment,regs->ss,result.flags};
    regs->ip=read16(&s,s.ss,s.sp);
    s.sp=(uint16_t)(s.sp+2u);
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

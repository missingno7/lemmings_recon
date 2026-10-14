#include "shifted_opaque.h"
#include "lemmings_sym.h"

#ifndef SHIFTED_OPAQUE_MUTATION
#define SHIFTED_OPAQUE_MUTATION 0
#endif

enum { CF=0x001, PF=0x004, AF=0x010, ZF=0x040, SF=0x080,
       IF=0x200, DF=0x400, OF=0x800, ARITH=0x8d5 };

typedef struct ShiftedOpaqueState {
    uint8_t *mem;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp,sp,ds,es,ss,flags;
    uint8_t source_shift_count;
} ShiftedOpaqueState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+(uint32_t)offset)&0xfffffu;
}

static uint8_t read_byte(ShiftedOpaqueState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->mem,address,s->flags);
    return s->mem[address];
}

static void write_byte(ShiftedOpaqueState *s,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->mem,address,value,s->flags);
    else
        s->mem[address]=value;
}

static uint8_t read8(ShiftedOpaqueState *s,uint16_t segment,uint16_t offset) {
    return read_byte(s,physical(segment,offset));
}

static uint16_t read16(ShiftedOpaqueState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(s,address);
    uint8_t high=read_byte(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ShiftedOpaqueState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_byte(s,address,(uint8_t)value);
    write_byte(s,address+1u,(uint8_t)(value>>8));
}

static void push(ShiftedOpaqueState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(ShiftedOpaqueState *s) {
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

static void logical_flags(ShiftedOpaqueState *s,uint16_t value,unsigned width) {
    /* AF is undefined after logical operations; retain its physical bit. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(value,width));
}

static void add_flags16(ShiftedOpaqueState *s,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum;
    s->flags=(uint16_t)((s->flags&(uint16_t)~ARITH)|szp(value,16)|
        (sum>0xffffu?CF:0u)|((left^right^value)&AF)|
        (((uint16_t)~(left^right)&(left^value)&0x8000u)?OF:0u));
}

static void dec_flags8(ShiftedOpaqueState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0?AF:0u)|(before==0x80u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
}

static void dec_flags16(ShiftedOpaqueState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0?AF:0u)|(before==0x8000u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
}

static uint16_t inc_flags16(ShiftedOpaqueState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fffu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t inc_flags8(ShiftedOpaqueState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t shr1(ShiftedOpaqueState *s,uint8_t value) {
    uint8_t result=(uint8_t)(value>>1);
    /* SHR count one defines CF/OF; AF is undefined. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(result,8)|(value&1u)|((value&0x80u)?OF:0u));
    return result;
}

static uint8_t rcr1(ShiftedOpaqueState *s,uint8_t value) {
    uint8_t carry=(uint8_t)(s->flags&CF);
    uint8_t result=(uint8_t)((value>>1)|(carry?0x80u:0u));
#if SHIFTED_OPAQUE_MUTATION == 1
    result=(uint8_t)(value>>1); /* Mutant: discard the preceding carry. */
#endif
    {
        uint16_t changed=(uint16_t)((s->flags&(uint16_t)~(CF|OF))|
            (value&1u));
        if(((result>>7)^((result>>6)&1u))!=0) changed|=OF;
        s->flags=changed;
    }
    return result;
}

static void out_word(ShiftedOpaqueState *s,uint16_t mirror,uint16_t value) {
    write16(s,s->ss,mirror,value);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,value,s->flags);
}

static void rep_movsb(ShiftedOpaqueState *s) {
    int direction=(s->flags&DF)?-1:1;
    while(s->cx!=0) {
        uint8_t value=read8(s,s->ds,s->si);
        write_byte(s,physical(s->es,s->di),value);
        s->si=(uint16_t)(s->si+direction);
        s->di=(uint16_t)(s->di+direction);
        s->cx=(uint16_t)(s->cx-1u);
    }
}

static void stosb(ShiftedOpaqueState *s,uint8_t value) {
    int direction=(s->flags&DF)?-1:1;
    write_byte(s,physical(s->es,s->di),value);
    s->di=(uint16_t)(s->di+direction);
}

static void source_shift_step(ShiftedOpaqueState *s) {
    uint32_t address=physical(s->ds,s->si);
    uint16_t before=s->flags;
    uint8_t value=read_byte(s,address);
    uint16_t after;
    value=shr1(s,value);
    after=s->flags;
    s->flags=before;
    write_byte(s,address,value);
    s->flags=after;
    s->si=inc_flags16(s,s->si);
    address=physical(s->ds,s->si);
    before=s->flags;
    value=read_byte(s,address);
    value=rcr1(s,value);
    after=s->flags;
    s->flags=before;
    write_byte(s,address,value);
    s->flags=after;
    s->si=inc_flags16(s,s->si);
    s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves flags. */
}

static void mask_shift_step(ShiftedOpaqueState *s) {
    uint32_t address=physical(s->ds,s->bx);
    uint16_t before=s->flags;
    uint8_t value=read_byte(s,address);
    uint16_t after;
    value=shr1(s,value);
    after=s->flags;
    s->flags=before;
    write_byte(s,address,value);
    s->flags=after;
    s->bx=inc_flags16(s,s->bx);
    address=physical(s->ds,s->bx);
    before=s->flags;
    value=read_byte(s,address);
    value=rcr1(s,value);
    after=s->flags;
    s->flags=before;
    write_byte(s,address,value);
    s->flags=after;
    s->bx=inc_flags16(s,s->bx);
    s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves flags. */
}

static void shift_source_row(ShiftedOpaqueState *s) {
    uint8_t shifts=read8(s,s->ds,SEG09A9_DrawingLeftBitShiftByte);
    s->source_shift_count=shifts;
    do {
        uint16_t saved_si,saved_cx;
        uint16_t loop_count;

        push(s,s->si);
        push(s,s->cx);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        source_shift_step(s); /* SHR first byte; RCR and LOOP thereafter. */
        loop_count=s->cx;
        while(loop_count!=0) {
            uint32_t address=physical(s->ds,s->si);
            uint16_t before=s->flags;
            uint8_t value=read_byte(s,address);
            uint16_t after;
            value=rcr1(s,value);
            after=s->flags;
            s->flags=before;
            write_byte(s,address,value);
            s->flags=after;
            s->si=inc_flags16(s,s->si);
            loop_count=(uint16_t)(loop_count-1u);
        }
        saved_cx=pop(s);
        saved_si=pop(s);
        s->cx=saved_cx;
        s->si=saved_si;
        {
            uint8_t before=(uint8_t)shifts;
            shifts=(uint8_t)(before-1u);
            dec_flags8(s,before);
        }
    } while(shifts!=0);
}

static void shift_mask_row(ShiftedOpaqueState *s) {
    uint8_t shifts=read8(s,s->ds,SEG09A9_DrawingLeftBitShiftByte);
#if SHIFTED_OPAQUE_MUTATION == 2
    /* Mutant uses a stale source shift count rather than the live reread. */
    shifts=s->source_shift_count;
#endif
    do {
        uint16_t saved_bx,saved_cx;
        uint16_t loop_count;

        push(s,s->bx);
        push(s,s->cx);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        mask_shift_step(s);
        loop_count=s->cx;
        while(loop_count!=0) {
            uint32_t address=physical(s->ds,s->bx);
            uint16_t before=s->flags;
            uint8_t value=read_byte(s,address);
            uint16_t after;
            value=rcr1(s,value);
            after=s->flags;
            s->flags=before;
            write_byte(s,address,value);
            s->flags=after;
            s->bx=inc_flags16(s,s->bx);
            loop_count=(uint16_t)(loop_count-1u);
        }
        saved_cx=pop(s);
        saved_bx=pop(s);
        s->cx=saved_cx;
        s->bx=saved_bx;
        {
            uint8_t before=(uint8_t)shifts;
            shifts=(uint8_t)(before-1u);
            dec_flags8(s,before);
        }
    } while(shifts!=0);
}

static void draw_shifted_row(ShiftedOpaqueState *s,int first_plane) {
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8); /* XOR CH,CH */
    {
        uint8_t before=(uint8_t)s->cx;
        uint8_t after=inc_flags8(s,before);
        s->cx=(uint16_t)((s->cx&0xff00u)|after);
    }
    do {
        s->flags=(uint16_t)(s->flags&(uint16_t)~IF); /* CLI */
        if(first_plane) {
            s->ax=(uint16_t)((s->ax&0xff00u)|0x0008u);
            s->ax=(uint16_t)((s->ax&0x00ffu)|
                ((uint16_t)read8(s,s->ds,s->bx)<<8));
            s->bx=inc_flags16(s,s->bx);
            if(s->bus&&s->bus->out_word)
                s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
        }
        (void)read8(s,s->es,s->di); /* VGA latch read. */
        s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->ds,s->si));
        s->si=(uint16_t)(s->si+((s->flags&DF)?0xffffu:1u));
        stosb(s,(uint8_t)s->ax);
        s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves flags. */
    } while(s->cx!=0);
    s->flags=(uint16_t)(s->flags|IF); /* STI. */
}

static void draw_row(ShiftedOpaqueState *s,int first_plane) {
    (void)first_plane;
    push(s,s->ds);
    push(s,s->es);
    push(s,s->cx);
    push(s,s->cx);
    push(s,s->di);

    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8); /* XOR CH,CH */
    s->di=SEG09A9_DrawingSourceRowScratch;
    rep_movsb(s);
    s->ax=(uint16_t)(s->ax&0xff00u); /* XOR AL,AL */
    logical_flags(s,0,8);
    stosb(s,(uint8_t)s->ax); /* Source sentinel follows DF. */

    s->di=pop(s);
    s->cx=pop(s);
    if(first_plane) {
        push(s,s->cx);
        push(s,s->di);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        s->ax=(uint16_t)((s->ax&0xff00u)|0x00ffu);
        s->di=SEG09A9_DrawingMaskRowScratch;
        while(s->cx!=0) {
            stosb(s,(uint8_t)s->ax);
            s->cx=(uint16_t)(s->cx-1u); /* REP STOSB. */
        }
        s->ax=(uint16_t)(s->ax&0xff00u); /* XOR AL,AL */
        logical_flags(s,0,8);
        stosb(s,(uint8_t)s->ax); /* Mask sentinel. */
        s->di=pop(s);
        s->cx=pop(s);
    }

    push(s,s->si);
    push(s,s->es);
    s->ds=pop(s);
    s->ax=0xa000u;
    s->es=s->ax;
    s->si=SEG09A9_DrawingSourceRowScratch;
    if(first_plane) {
        s->bx=SEG09A9_DrawingMaskRowScratch;
    }

    shift_source_row(s);
    if(first_plane) {
        /* The original performs a second live read at DS:A948 after source writes. */
        shift_mask_row(s);
    }
    draw_shifted_row(s,first_plane);

    s->si=pop(s);
    {
        uint16_t before=s->si;
        uint16_t advance=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
        s->ax=advance; /* MOV AX,[DS:6702] precedes ADD SI,AX. */
        s->si=(uint16_t)(before+s->ax);
        add_flags16(s,before,s->ax);
    }
    {
        uint16_t before=s->di;
        uint16_t advance=read16(s,s->ds,
            SEG09A9_DrawingActiveDestinationRowAdvance);
        s->di=(uint16_t)(before+advance);
        add_flags16(s,before,advance);
    }

    s->cx=pop(s);
    s->es=pop(s);
    s->ds=pop(s);
    {
        uint8_t before=(uint8_t)(s->cx>>8);
        uint8_t after=(uint8_t)(before-1u);
        dec_flags8(s,before);
        s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)after<<8));
    }
}

static void draw_plane_rows(ShiftedOpaqueState *s,int first_plane) {
    do {
        draw_row(s,first_plane);
    } while((s->cx&0xff00u)!=0);
}

static void begin_following_plane(ShiftedOpaqueState *s,uint8_t map_mask,
                                  int configure_graphics_controller) {
    uint16_t before=s->si;
    uint16_t pitch=read16(s,s->es,SEG09A9_DrawingSourcePlaneExtent);
#if SHIFTED_OPAQUE_MUTATION == 3
    pitch=0; /* Mutant: omit the live per-plane source advance. */
#endif
    s->si=(uint16_t)(before+pitch);
    add_flags16(s,before,pitch);

    if(configure_graphics_controller) {
        s->ax=0x0001u;
        out_word(s,SEG143E_VgaEnableSetResetMirror,s->ax);
        s->ax=0x1003u;
        out_word(s,SEG143E_VgaDataRotateMirror,s->ax);
        s->ax=0xff08u;
        out_word(s,SEG143E_VgaBitMaskMirror,s->ax);
        s->dx=0x03c4u;
    }
    s->ax=(uint16_t)(((uint16_t)map_mask<<8)|0x0002u);
    out_word(s,SEG143E_VgaMapMaskMirror,s->ax);
}

static void one_plane(ShiftedOpaqueState *s,int first_plane,
                      uint8_t map_mask,int configure_graphics_controller) {
    if(first_plane) {
        push(s,s->di);
        push(s,s->si);
        push(s,s->cx);
    } else {
        begin_following_plane(s,map_mask,configure_graphics_controller);
        push(s,s->di);
        push(s,s->si);
        push(s,s->cx);
    }

    /* Outer plane save stays live on SS and rows consume it by POP. */
    draw_plane_rows(s,first_plane);
    s->cx=pop(s);
    s->si=pop(s);
    s->di=pop(s);
}

static LmnShiftedOpaqueResult run_shifted_opaque(uint8_t *memory,
    const LmnShiftedOpaqueCall *call,const LmnRasterBus *bus) {
    ShiftedOpaqueState s={memory,bus,0,0,call->packed_counts,
        call->width_state,call->source_cursor,call->destination_cursor,
        0,call->stack_offset,call->initial_data_segment,0,
        call->stack_segment,call->flags,0};
    uint16_t entry_advance;

    entry_advance=read16(&s,s.ds,SEG09A9_DrawingActiveDestinationRowAdvance);
    write16(&s,s.ds,SEG09A9_DrawingActiveDestinationRowAdvance,
        (uint16_t)(entry_advance-1u));
    dec_flags16(&s,entry_advance);
    push(&s,s.ds);
    s.ds=read16(&s,s.ds,SEG09A9_GraphicsResourceSegment);
    s.ax=call->game_data_segment; /* relocated MOV AX,09A9 immediate */
    s.es=s.ax;
    s.ax=s.dx;
    {
        uint8_t low=(uint8_t)s.ax,high=(uint8_t)(s.ax>>8);
        s.ax=(uint16_t)(((uint16_t)low<<8)|high); /* XCHG DL,DH */
    }
    s.ax=(uint16_t)(s.ax&0x00ffu); /* XOR DH,DH */
    logical_flags(&s,0,8);
    s.bp=s.ax;
    s.dx=0x03c4u;
    s.ax=0x0f02u;
    out_word(&s,SEG143E_VgaMapMaskMirror,s.ax);
    s.dx=0x03ceu;
    s.ax=0;
    logical_flags(&s,0,16); /* XOR AX,AX */
    out_word(&s,SEG143E_VgaSetResetMirror,s.ax);
    s.ax=0x0e01u;
    out_word(&s,SEG143E_VgaEnableSetResetMirror,s.ax);
    s.ax=0x0005u;
    out_word(&s,SEG143E_VgaGraphicsModeMirror,s.ax);
    s.ax=0x0003u;
    out_word(&s,SEG143E_VgaDataRotateMirror,s.ax);

    /* The first pass always runs.  Later passes are selected by BP after DEC.
       The fourth pass deliberately has no further BP test. */
    one_plane(&s,1,0x0f,0);
    dec_flags16(&s,s.bp);
    s.bp=(uint16_t)(s.bp-1u);
    if(s.bp!=0) {
        one_plane(&s,0,0x02,1);
        dec_flags16(&s,s.bp);
        s.bp=(uint16_t)(s.bp-1u);
        if(s.bp!=0) {
            one_plane(&s,0,0x04,0);
            dec_flags16(&s,s.bp);
            s.bp=(uint16_t)(s.bp-1u);
            if(s.bp!=0) {
                /* The fourth pass is a shared-tail row loop: unlike the
                   first three passes it has no outer DI/SI/CX save/pop and
                   no following BP test/decrement. */
                begin_following_plane(&s,0x08,0);
                draw_plane_rows(&s,0);
            }
        }
    }

    s.ds=pop(&s); /* POP DS at 939C; core ends before RETF 939D. */
    {
        LmnShiftedOpaqueResult result={s.ax,s.cx,s.dx,s.si,s.bx,s.di,
            s.bp,s.sp,s.ds,s.es,s.flags};
        return result;
    }
}

LmnShiftedOpaqueResult lmn_draw_shifted_opaque_core(uint8_t *memory,
    const LmnShiftedOpaqueCall *call,const LmnRasterBus *bus) {
    return run_shifted_opaque(memory,call,bus);
}

void lmn_draw_shifted_opaque_adapter(uint8_t *memory,LmnRegs *regs,
    uint16_t game_data_segment,const LmnRasterBus *bus) {
    LmnShiftedOpaqueCall call={regs->ds,game_data_segment,regs->ss,regs->sp,
        regs->cx,regs->dx,regs->si,regs->di,regs->flags};
    LmnShiftedOpaqueResult result=run_shifted_opaque(memory,&call,bus);
    ShiftedOpaqueState s={memory,bus,result.work_value,result.mask_cursor,
        result.packed_counts,result.port,result.source_cursor,
        result.destination_cursor,result.plane_counter,result.stack_offset,
        result.source_segment,result.output_segment,regs->ss,result.flags,0};
    regs->ip=pop(&s);
    regs->cs=pop(&s);
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

#include "shifted_protected.h"
#include "lemmings_sym.h"

#ifndef SHIFTED_PROTECTED_MUTATION
#define SHIFTED_PROTECTED_MUTATION 0
#endif

enum { CF=0x001, PF=0x004, AF=0x010, ZF=0x040, SF=0x080,
       IF=0x200, DF=0x400, OF=0x800, ARITH=0x8d5 };

typedef struct ShiftedProtectedState {
    uint8_t *mem;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp,sp,ds,es,ss,flags,game_ds;
} ShiftedProtectedState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+(uint32_t)offset)&0xfffffu;
}

static uint8_t read_byte(ShiftedProtectedState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->mem,address,s->flags);
    return s->mem[address];
}

static void write_byte(ShiftedProtectedState *s,uint32_t address,
                       uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->mem,address,value,s->flags);
    else
        s->mem[address]=value;
}

static uint8_t read8(ShiftedProtectedState *s,uint16_t segment,
                     uint16_t offset) {
    return read_byte(s,physical(segment,offset));
}

static uint16_t read16(ShiftedProtectedState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(s,address);
    uint8_t high=read_byte(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ShiftedProtectedState *s,uint16_t segment,
                    uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_byte(s,address,(uint8_t)value);
    write_byte(s,address+1u,(uint8_t)(value>>8));
}

static void push(ShiftedProtectedState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(ShiftedProtectedState *s) {
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

static void logical_flags(ShiftedProtectedState *s,uint16_t value,
                          unsigned width) {
    /* AF is undefined after XOR; preserve its incoming physical bit. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(value,width));
}

static void add_flags(ShiftedProtectedState *s,uint16_t left,
                      uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum;
    s->flags=(uint16_t)((s->flags&(uint16_t)~ARITH)|szp(value,16)|
        (sum>0xffffu?CF:0u)|((left^right^value)&AF)|
        (((uint16_t)~(left^right)&(left^value)&0x8000u)?OF:0u));
}

static uint8_t dec8(ShiftedProtectedState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0?AF:0u)|(before==0x80u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint16_t dec16(ShiftedProtectedState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0?AF:0u)|(before==0x8000u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint16_t inc16(ShiftedProtectedState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fffu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t inc8(ShiftedProtectedState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t shr1(ShiftedProtectedState *s,uint8_t value) {
    uint8_t result=(uint8_t)(value>>1);
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(result,8)|(value&1u)|((value&0x80u)?OF:0u));
    return result;
}

static uint8_t rcr1(ShiftedProtectedState *s,uint8_t value) {
    uint8_t carry=(uint8_t)(s->flags&CF);
    uint8_t result=(uint8_t)((value>>1)|(carry?0x80u:0u));
#if SHIFTED_PROTECTED_MUTATION == 1
    result=(uint8_t)(value>>1); /* Mutant drops the SHR/RCR carry chain. */
#endif
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|OF))|(value&1u)|
        ((((result>>7)^((result>>6)&1u))!=0)?OF:0u));
    return result;
}

static void output(ShiftedProtectedState *s,uint16_t mirror,uint16_t value) {
    write16(s,s->ss,mirror,value);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,value,s->flags);
}

static uint16_t direction_step(const ShiftedProtectedState *s) {
#if SHIFTED_PROTECTED_MUTATION == 2
    (void)s;
    return 1u; /* Mutant ignores the live DF for source and VGA cursors. */
#else
    return (s->flags&DF)?0xffffu:1u;
#endif
}

static void dec_live_destination_advance(ShiftedProtectedState *s) {
    uint16_t input_flags=s->flags;
    uint16_t before=read16(s,s->ds,
        SEG09A9_DrawingActiveDestinationRowAdvance);
    uint16_t after=dec16(s,before);
    uint16_t result_flags=s->flags;
    /* The write callback observes the instruction's incoming flags. */
    s->flags=input_flags;
    write16(s,s->ds,SEG09A9_DrawingActiveDestinationRowAdvance,after);
    s->flags=result_flags;
}

static void source_copy_and_sentinel(ShiftedProtectedState *s) {
    uint16_t count=(uint8_t)s->cx;
    uint16_t step=direction_step(s);
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8); /* XOR CH,CH. */
    s->di=SEG09A9_DrawingSourceRowScratch;
    while(count!=0) {
        uint8_t value=read8(s,s->ds,s->si);
        uint16_t before=s->flags;
        s->si=(uint16_t)(s->si+step);
        write_byte(s,physical(s->es,s->di),value);
        s->flags=before;
        s->di=(uint16_t)(s->di+step);
        s->cx=(uint16_t)(s->cx-1u);
        --count;
    }
    s->ax=(uint16_t)(s->ax&0xff00u);
    logical_flags(s,0,8); /* XOR AL,AL. */
    write_byte(s,physical(s->es,s->di),(uint8_t)s->ax); /* STOSB. */
    s->di=(uint16_t)(s->di+step);
}

static void shifted_source_pass(ShiftedProtectedState *s) {
    s->si=SEG09A9_DrawingSourceRowScratch;
    s->ax=(uint16_t)((s->ax&0xff00u)|
        read8(s,s->ds,SEG09A9_DrawingLeftBitShiftByte));
    do {
        uint8_t value;
        uint16_t before_flags;
        push(s,s->si);
        push(s,s->cx);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH. */

        value=read8(s,s->ds,s->si);
        before_flags=s->flags;
        value=shr1(s,value);
        {
            uint16_t after_flags=s->flags;
            s->flags=before_flags;
            write_byte(s,physical(s->ds,s->si),value);
            s->flags=after_flags;
        }
        s->si=inc16(s,s->si); /* INC preserves SHR carry. */

        do {
            value=read8(s,s->ds,s->si);
            before_flags=s->flags;
            value=rcr1(s,value);
            {
                uint16_t after_flags=s->flags;
                s->flags=before_flags;
                write_byte(s,physical(s->ds,s->si),value);
                s->flags=after_flags;
            }
            s->si=inc16(s,s->si); /* INC preserves the RCR carry. */
            s->cx=(uint16_t)(s->cx-1u); /* LOOP has no flag effects. */
        } while(s->cx!=0);

        s->cx=pop(s);
        s->si=pop(s);
        {
            uint8_t before=(uint8_t)s->ax;
            uint8_t low=dec8(s,before);
            s->ax=(uint16_t)((s->ax&0xff00u)|low);
        }
    } while((s->flags&ZF)==0);
}

static void draw_protected_row_bytes(ShiftedProtectedState *s) {
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8); /* XOR CH,CH. */
    {
        uint8_t before=(uint8_t)s->cx;
        uint8_t low=inc8(s,before); /* INC CL, including 0xFF wrap. */
        s->cx=(uint16_t)(s->cx&0xff00u)|low;
    }
    s->flags=(uint16_t)(s->flags&(uint16_t)~IF); /* CLI. */
    do {
        uint8_t value=read8(s,s->es,s->di);
        s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
        s->ax=(uint16_t)((s->ax&0x00ffu)|
            ((uint16_t)(uint8_t)~(uint8_t)(s->ax>>8)<<8)); /* NOT AH. */
        s->ax=(uint16_t)((s->ax&0xff00u)|0x0008u); /* MOV AL,8. */
        output(s,SEG143E_VgaBitMaskMirror,s->ax);

        value=read8(s,s->ds,s->si); /* LODSB. */
        s->ax=(uint16_t)((s->ax&0xff00u)|value);
        s->si=(uint16_t)(s->si+direction_step(s));
        write_byte(s,physical(s->es,s->di),(uint8_t)s->ax); /* STOSB. */
        s->di=(uint16_t)(s->di+direction_step(s));
        s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves flags. */
    } while(s->cx!=0);
    s->flags=(uint16_t)(s->flags|IF); /* STI. */
}

static void draw_rows(ShiftedProtectedState *s,int restore_plane_state) {
    if(restore_plane_state) {
        push(s,s->di);
        push(s,s->si);
        push(s,s->cx);
    }
    for(;;) {
        push(s,s->ds);
        push(s,s->es);
        push(s,s->cx);
        push(s,s->cx);
        push(s,s->di);
        source_copy_and_sentinel(s);
        s->di=pop(s);
        s->cx=pop(s);

        push(s,s->si);
        push(s,s->es);
        s->ds=pop(s); /* PUSH ES / POP DS. */
        s->ax=0xa000u;
        s->es=s->ax;
        shifted_source_pass(s);
        draw_protected_row_bytes(s);

        s->si=pop(s);
        s->ax=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
        {
            uint16_t before=s->si;
            s->si=(uint16_t)(before+s->ax);
            add_flags(s,before,s->ax);
        }
        {
            uint16_t before=s->di;
            uint16_t advance=read16(s,s->ds,
                SEG09A9_DrawingActiveDestinationRowAdvance);
            s->di=(uint16_t)(before+advance);
            add_flags(s,before,advance);
        }
        s->cx=pop(s);
        s->es=pop(s);
        s->ds=pop(s);
        {
            uint8_t before=(uint8_t)(s->cx>>8);
            uint8_t high=dec8(s,before);
            s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)high<<8));
            if(high==0) break;
        }
    }

    if(restore_plane_state) {
        s->cx=pop(s);
        s->si=pop(s);
        s->di=pop(s);
        s->bp=dec16(s,s->bp);
    }
}

static void advance_plane_source(ShiftedProtectedState *s) {
    uint16_t before=s->si;
    uint16_t extent=read16(s,s->es,SEG09A9_DrawingSourcePlaneExtent);
    s->si=(uint16_t)(before+extent);
    add_flags(s,before,extent);
}

static void select_later_plane(ShiftedProtectedState *s,uint16_t map_mask) {
    push(s,s->dx);
    s->dx=(uint16_t)((s->dx&0xff00u)|0x00c4u);
    s->ax=map_mask;
    output(s,SEG143E_VgaMapMaskMirror,s->ax);
    s->dx=pop(s);
}

static LmnShiftedProtectedResult run_shifted_protected(uint8_t *memory,
    const LmnShiftedProtectedCall *call,const LmnRasterBus *bus) {
    ShiftedProtectedState s={memory,bus,0,0,call->packed_counts,
        call->width_state,call->source_cursor,call->destination_cursor,0,
        call->stack_offset,call->initial_data_segment,0,
        call->stack_segment,call->flags,call->game_data_segment};
    uint8_t low,high;

    dec_live_destination_advance(&s);
    push(&s,s.ds);
    s.ds=read16(&s,s.ds,SEG09A9_GraphicsResourceSegment);
    s.ax=s.game_ds; /* MOV AX,09A9 is a relocated segment operand. */
    s.es=s.ax;
    low=(uint8_t)s.dx;
    high=(uint8_t)(s.dx>>8);
    s.dx=(uint16_t)(((uint16_t)low<<8)|high); /* XCHG DL,DH. */
    s.dx=(uint16_t)(s.dx&0x00ffu); /* XOR DH,DH. */
    logical_flags(&s,0,8);
    s.bp=s.dx;

    s.dx=0x03c4u;
    s.ax=0x0102u;
    output(&s,SEG143E_VgaMapMaskMirror,s.ax);
    s.dx=0x03ceu;
    s.ax=0;
    logical_flags(&s,0,16); /* XOR AX,AX. */
    output(&s,SEG143E_VgaSetResetMirror,s.ax);
    s.ax=0x0001u;
    output(&s,SEG143E_VgaEnableSetResetMirror,s.ax);
    s.ax=0x1003u;
    output(&s,SEG143E_VgaDataRotateMirror,s.ax);
    s.ax=0x0805u;
    output(&s,SEG143E_VgaGraphicsModeMirror,s.ax);
    s.ax=0x0807u;
    output(&s,SEG143E_VgaColorCareMirror,s.ax);
    s.ax=0x0802u;
    output(&s,SEG143E_VgaColorCompareMirror,s.ax);

    draw_rows(&s,1);
    if(s.bp!=0) {
        advance_plane_source(&s);
        select_later_plane(&s,0x0202u);
        draw_rows(&s,1);
        if(s.bp!=0) {
            advance_plane_source(&s);
            select_later_plane(&s,0x0402u);
            draw_rows(&s,1);
            if(s.bp!=0) {
                advance_plane_source(&s);
                select_later_plane(&s,0x0802u);
                draw_rows(&s,0);
#if SHIFTED_PROTECTED_MUTATION == 3
                s.bp=dec16(&s,s.bp); /* Mutant adds a fourth BP test/decrement. */
#endif
            }
        }
    }

    s.ds=pop(&s);
    {
        LmnShiftedProtectedResult result={s.ax,s.cx,s.dx,s.si,s.di,s.bp,
            s.sp,s.ds,s.es,s.flags};
        return result;
    }
}

LmnShiftedProtectedResult lmn_draw_shifted_protected_core(
    uint8_t *memory,const LmnShiftedProtectedCall *call,
    const LmnRasterBus *bus) {
    return run_shifted_protected(memory,call,bus);
}

void lmn_draw_shifted_protected_adapter(uint8_t *memory,LmnRegs *regs,
    uint16_t game_data_segment,const LmnRasterBus *bus) {
    LmnShiftedProtectedCall call={regs->ds,game_data_segment,regs->ss,
        regs->sp,regs->cx,regs->dx,regs->si,regs->di,regs->flags};
    LmnShiftedProtectedResult result=run_shifted_protected(memory,&call,bus);
    ShiftedProtectedState s={memory,bus,result.work_value,regs->bx,
        result.packed_counts,result.port,result.source_cursor,
        result.destination_cursor,result.plane_counter,result.stack_offset,
        result.source_segment,result.output_segment,regs->ss,result.flags,
        game_data_segment};

    regs->ip=pop(&s);
    regs->cs=pop(&s);
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

#include "shifted_masked.h"
#include "lemmings_sym.h"

#ifndef SHIFTED_MASKED_MUTATION
#define SHIFTED_MASKED_MUTATION 0
#endif

enum { CF=0x001, PF=0x004, AF=0x010, ZF=0x040, SF=0x080,
       IF=0x200, DF=0x400, OF=0x800, ARITH=0x8d5 };

typedef struct ShiftedMaskedState {
    uint8_t *mem;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp,sp,ds,es,ss,flags;
    uint16_t game_ds;
} ShiftedMaskedState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+(uint32_t)offset)&0xfffffu;
}

static uint8_t read_byte(ShiftedMaskedState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->mem,address,s->flags);
    return s->mem[address];
}

static void write_byte(ShiftedMaskedState *s,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->mem,address,value,s->flags);
    else
        s->mem[address]=value;
}

static uint8_t read8(ShiftedMaskedState *s,uint16_t segment,uint16_t offset) {
    return read_byte(s,physical(segment,offset));
}

static uint16_t read16(ShiftedMaskedState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(s,address);
    uint8_t high=read_byte(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ShiftedMaskedState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_byte(s,address,(uint8_t)value);
    write_byte(s,address+1u,(uint8_t)(value>>8));
}

static void push(ShiftedMaskedState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(ShiftedMaskedState *s) {
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

static void logical_flags(ShiftedMaskedState *s,uint16_t value,unsigned width) {
    /* AF is undefined after these logical instructions; retain its bit. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(value,width));
}

static void add_flags16(ShiftedMaskedState *s,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum;
    s->flags=(uint16_t)((s->flags&(uint16_t)~ARITH)|szp(value,16)|
        (sum>0xffffu?CF:0u)|((left^right^value)&AF)|
        (((uint16_t)~(left^right)&(left^value)&0x8000u)?OF:0u));
}

static uint16_t inc16(ShiftedMaskedState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fffu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t inc8(ShiftedMaskedState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t dec8(ShiftedMaskedState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0?AF:0u)|(before==0x80u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint16_t dec16(ShiftedMaskedState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0?AF:0u)|(before==0x8000u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static void sub_word_at(ShiftedMaskedState *s,uint16_t segment,uint16_t offset) {
    uint16_t before=read16(s,segment,offset);
    uint16_t value=(uint16_t)(before-1u);
    /* The original memory-write observation precedes DEC's flag update. */
    write16(s,segment,offset,value);
    (void)dec16(s,before);
}

static void add_si(ShiftedMaskedState *s,uint16_t value) {
    uint16_t before=s->si;
    s->si=(uint16_t)(before+value);
    add_flags16(s,before,value);
}

static void add_bx(ShiftedMaskedState *s,uint16_t value) {
    uint16_t before=s->bx;
    s->bx=(uint16_t)(before+value);
    add_flags16(s,before,value);
}

static void add_di(ShiftedMaskedState *s,uint16_t value) {
    uint16_t before=s->di;
    s->di=(uint16_t)(before+value);
    add_flags16(s,before,value);
}

static void out_word(ShiftedMaskedState *s,uint16_t mirror,uint16_t value) {
    write16(s,s->ss,mirror,value);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,value,s->flags);
}

static uint16_t direction_step(const ShiftedMaskedState *s) {
    return (s->flags&DF)?0xffffu:1u;
}

static void stosb(ShiftedMaskedState *s) {
    write_byte(s,physical(s->es,s->di),(uint8_t)s->ax);
    s->di=(uint16_t)(s->di+direction_step(s));
}

static void copy_string(ShiftedMaskedState *s) {
    /* REP MOVSB: CX is already narrowed to CL by the preceding XOR CH,CH. */
    while(s->cx!=0) {
        uint8_t value=read8(s,s->ds,s->si);
        write_byte(s,physical(s->es,s->di),value);
        s->si=(uint16_t)(s->si+direction_step(s));
        s->di=(uint16_t)(s->di+direction_step(s));
        s->cx=(uint16_t)(s->cx-1u);
    }
}

static uint8_t shr1(ShiftedMaskedState *s,uint8_t value) {
    uint8_t result=(uint8_t)(value>>1);
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(result,8)|(value&1u)|((value&0x80u)?OF:0u));
    return result;
}

static uint8_t rcr1(ShiftedMaskedState *s,uint8_t value) {
    uint8_t carry=(uint8_t)(s->flags&CF);
    uint8_t result=(uint8_t)((value>>1)|(carry?0x80u:0u));
#if SHIFTED_MASKED_MUTATION == 1
    result=(uint8_t)(value>>1);
#endif
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|OF))|(value&1u));
    if(((result>>7)^((result>>6)&1u))!=0) s->flags|=OF;
    return result;
}

static void shifted_rmw(ShiftedMaskedState *s,uint16_t segment,uint16_t offset,
                        unsigned rotate) {
    uint8_t value=read8(s,segment,offset);
    uint16_t flags_before=s->flags;
    uint16_t flags_after;
    value=rotate ? rcr1(s,value) : shr1(s,value);
    flags_after=s->flags;
    /* The MMIO/write observation is made with the instruction's old flags. */
    s->flags=flags_before;
    write_byte(s,physical(segment,offset),value);
    s->flags=flags_after;
}

static void increment_scratch(ShiftedMaskedState *s,uint16_t *cursor) {
#if SHIFTED_MASKED_MUTATION == 2
    uint16_t before=*cursor;
    (void)inc16(s,before);
    *cursor=(uint16_t)(before+direction_step(s));
#else
    *cursor=inc16(s,*cursor);
#endif
}

static void shift_source_and_mask(ShiftedMaskedState *s,uint16_t shifts,
                                  int include_mask) {
    uint8_t remaining=(uint8_t)shifts;
    do {
        uint16_t loop_count;
        push(s,s->si);
        if(include_mask) push(s,s->bx);
        push(s,s->cx);
        s->cx=(uint16_t)(s->cx&0x00ffu);
        logical_flags(s,0,8); /* XOR CH,CH */
        shifted_rmw(s,s->ds,s->si,0); /* SHR [SI],1 */
        increment_scratch(s,&s->si);
        loop_count=s->cx;
        do {
            shifted_rmw(s,s->ds,s->si,1); /* RCR [SI],1 */
            increment_scratch(s,&s->si);
            loop_count=(uint16_t)(loop_count-1u); /* LOOP */
            s->cx=loop_count;
        } while(loop_count!=0);
        s->cx=pop(s);

        if(include_mask) {
            push(s,s->cx);
            s->cx=(uint16_t)(s->cx&0x00ffu);
            logical_flags(s,0,8); /* second XOR CH,CH */
            shifted_rmw(s,s->ds,s->bx,0); /* SHR [BX],1 */
            increment_scratch(s,&s->bx);
            loop_count=s->cx;
            do {
                shifted_rmw(s,s->ds,s->bx,1); /* RCR [BX],1 */
                increment_scratch(s,&s->bx);
                loop_count=(uint16_t)(loop_count-1u); /* LOOP */
                s->cx=loop_count;
            } while(loop_count!=0);
            s->cx=pop(s);
            s->bx=pop(s);
        }
        s->si=pop(s);
        remaining=dec8(s,remaining); /* DEC AL */
        s->ax=(uint16_t)((s->ax&0xff00u)|remaining);
    } while(remaining!=0);
}

static void shift_source_only(ShiftedMaskedState *s,uint16_t shifts) {
    shift_source_and_mask(s,shifts,0);
}

static void setup_first_plane(ShiftedMaskedState *s) {
    uint8_t low=(uint8_t)s->dx,high=(uint8_t)(s->dx>>8);
    s->dx=(uint16_t)(((uint16_t)low<<8)|high); /* XCHG DL,DH */
    s->dx=(uint16_t)(s->dx&0x00ffu); /* XOR DH,DH */
    logical_flags(s,0,8);
    s->bp=s->dx;

    s->dx=0x03c4u;
    s->ax=0x0f02u;
    out_word(s,SEG143E_VgaMapMaskMirror,s->ax);
    s->dx=0x03ceu;
    s->ax=0;
    logical_flags(s,s->ax,16); /* XOR AX,AX */
    out_word(s,SEG143E_VgaSetResetMirror,s->ax);
    s->ax=0x0e01u;
    out_word(s,SEG143E_VgaEnableSetResetMirror,s->ax);
    s->ax=0x0005u;
    out_word(s,SEG143E_VgaGraphicsModeMirror,s->ax);
    s->ax=0x0003u;
    out_word(s,SEG143E_VgaDataRotateMirror,s->ax);
}

static void mask_draw_byte(ShiftedMaskedState *s) {
    uint8_t mask=read8(s,s->ds,s->bx);
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)mask<<8));
    s->bx=inc16(s,s->bx); /* INC BX always moves forward and preserves CF. */
    s->ax=(uint16_t)((s->ax&0xff00u)|0x0008u);
    out_word(s,SEG143E_VgaBitMaskMirror,s->ax);
    s->flags=(uint16_t)(s->flags&(uint16_t)~IF); /* CLI */
    s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->es,s->di)); /* VGA latch read */
    s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->ds,s->si)); /* LODSB */
    s->si=(uint16_t)(s->si+direction_step(s));
    stosb(s);
    s->flags=(uint16_t)(s->flags|IF); /* STI */
}

static void plain_draw_byte(ShiftedMaskedState *s) {
    s->flags=(uint16_t)(s->flags&(uint16_t)~IF); /* CLI */
    s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->es,s->di)); /* VGA latch read */
    s->ax=(uint16_t)((s->ax&0xff00u)|read8(s,s->ds,s->si)); /* LODSB */
    s->si=(uint16_t)(s->si+direction_step(s));
    stosb(s);
    s->flags=(uint16_t)(s->flags|IF); /* STI */
}

static void enter_scratch_draw(ShiftedMaskedState *s) {
    push(s,s->es);
    s->ds=pop(s); /* PUSH ES / POP DS: the live saved segment owns scratch. */
    s->ax=0xa000u;
    s->es=s->ax;
    s->si=SEG09A9_DrawingSourceRowScratch;
}

static uint8_t load_shift_count(ShiftedMaskedState *s) {
    uint8_t shift=read8(s,s->ds,SEG09A9_DrawingLeftBitShiftByte);
    s->ax=(uint16_t)((s->ax&0xff00u)|shift);
    return shift;
}

static void first_masked_row(ShiftedMaskedState *s) {
    uint8_t shift;
    uint16_t source_advance,destination_advance;

    push(s,s->ds);
    push(s,s->es);
    push(s,s->cx);
    push(s,s->cx);
    push(s,s->di);
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8); /* XOR CH,CH */
    s->di=SEG09A9_DrawingSourceRowScratch; /* LEA DI,[6706] */
    copy_string(s);
    s->ax=(uint16_t)(s->ax&0xff00u);
    logical_flags(s,0,8); /* XOR AL,AL */
    stosb(s); /* source sentinel follows DF */
    s->di=pop(s);
    s->cx=pop(s);

    push(s,s->si);
    push(s,s->cx);
    push(s,s->di);
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8);
    s->si=s->bx; /* MOV SI,BX */
    s->di=SEG09A9_DrawingMaskRowScratch;
    copy_string(s);
    s->ax=(uint16_t)(s->ax&0xff00u);
    logical_flags(s,0,8);
    stosb(s); /* mask sentinel follows DF */
    s->di=pop(s);
    s->cx=pop(s);
    push(s,s->si); /* advanced mask source cursor */

    enter_scratch_draw(s);
    s->bx=SEG09A9_DrawingMaskRowScratch;
    s->si=SEG09A9_DrawingSourceRowScratch;
    shift=load_shift_count(s);
    shift_source_and_mask(s,shift,1);

    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8);
    {
        uint8_t low=inc8(s,(uint8_t)s->cx);
        s->cx=(uint16_t)((s->cx&0xff00u)|low);
    }
    do {
        mask_draw_byte(s);
        s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves flags. */
    } while(s->cx!=0);

    s->bx=pop(s); /* saved mask source cursor */
    s->si=pop(s); /* saved source cursor */
    s->ax=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
    source_advance=s->ax;
    add_si(s,source_advance);
    add_bx(s,source_advance);
    destination_advance=read16(s,s->ds,
        SEG09A9_DrawingActiveDestinationRowAdvance);
    add_di(s,destination_advance);
    s->cx=pop(s);
    s->es=pop(s);
    s->ds=pop(s);
    {
        uint8_t high=dec8(s,(uint8_t)(s->cx>>8));
        s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)high<<8));
    }
}

static void later_maskless_row(ShiftedMaskedState *s) {
    uint8_t shift;
    uint16_t source_advance,destination_advance;

    push(s,s->ds);
    push(s,s->es);
    push(s,s->cx);
    push(s,s->cx);
    push(s,s->di);
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8);
    s->di=SEG09A9_DrawingSourceRowScratch;
    copy_string(s);
    s->ax=(uint16_t)(s->ax&0xff00u);
    logical_flags(s,0,8);
    stosb(s);
    s->di=pop(s);
    s->cx=pop(s);

    push(s,s->si);
    enter_scratch_draw(s);
    shift=load_shift_count(s);
    shift_source_only(s,shift);
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8);
    {
        uint8_t low=inc8(s,(uint8_t)s->cx);
        s->cx=(uint16_t)((s->cx&0xff00u)|low);
    }
    do {
        plain_draw_byte(s);
        s->cx=(uint16_t)(s->cx-1u);
    } while(s->cx!=0);

    s->si=pop(s);
    s->ax=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
    source_advance=s->ax;
    add_si(s,source_advance);
    destination_advance=read16(s,s->ds,
        SEG09A9_DrawingActiveDestinationRowAdvance);
    add_di(s,destination_advance);
    s->cx=pop(s);
    s->es=pop(s);
    s->ds=pop(s);
    {
        uint8_t high=dec8(s,(uint8_t)(s->cx>>8));
        s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)high<<8));
    }
}

static void final_maskless_row(ShiftedMaskedState *s) {
    uint8_t shift;
    uint16_t source_advance,destination_advance;

    push(s,s->ds);
    push(s,s->es);
    push(s,s->cx);
    push(s,s->cx);
    push(s,s->di);
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8);
    s->di=SEG09A9_DrawingSourceRowScratch;
    copy_string(s);
    s->ax=(uint16_t)(s->ax&0xff00u);
    logical_flags(s,0,8);
    stosb(s);
    s->di=pop(s);
    s->cx=pop(s);

    push(s,s->si);
    push(s,s->es);
    s->ds=pop(s);
    s->ax=0xa000u;
    s->es=s->ax;
    s->si=SEG09A9_DrawingSourceRowScratch;
    shift=load_shift_count(s);
    shift_source_only(s,shift);
    s->cx=(uint16_t)(s->cx&0x00ffu);
    logical_flags(s,0,8);
    {
        uint8_t low=inc8(s,(uint8_t)s->cx);
        s->cx=(uint16_t)((s->cx&0xff00u)|low);
    }
    do {
        plain_draw_byte(s);
        s->cx=(uint16_t)(s->cx-1u);
    } while(s->cx!=0);

    s->si=pop(s);
    s->ax=read16(s,s->ds,SEG09A9_DrawingSourceRowAdvance);
    source_advance=s->ax;
    add_si(s,source_advance);
    destination_advance=read16(s,s->ds,
        SEG09A9_DrawingActiveDestinationRowAdvance);
    add_di(s,destination_advance);
    s->cx=pop(s);
    s->es=pop(s);
    s->ds=pop(s);
    {
        uint8_t high=dec8(s,(uint8_t)(s->cx>>8));
        s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)high<<8));
    }
}

static void first_plane(ShiftedMaskedState *s) {
    push(s,s->di);
    push(s,s->si);
    push(s,s->cx);
    do {
        first_masked_row(s);
    } while((s->cx&0xff00u)!=0);
    s->cx=pop(s);
    s->si=pop(s);
    s->di=pop(s);
    s->bp=dec16(s,s->bp); /* DEC BP; first/next plane guard */
}

static uint16_t live_plane_extent(ShiftedMaskedState *s) {
    uint16_t extent;
#if SHIFTED_MASKED_MUTATION == 3
    extent=read16(s,s->ds,SEG09A9_DrawingSourcePlaneExtent);
#else
    extent=read16(s,s->es,SEG09A9_DrawingSourcePlaneExtent);
#endif
    return extent;
}

static void setup_second_plane(ShiftedMaskedState *s) {
    add_si(s,live_plane_extent(s)); /* ES:66F8 is the live plane stride. */
    s->ax=0x0001u;
    out_word(s,SEG143E_VgaEnableSetResetMirror,s->ax);
    s->ax=0x1003u;
    out_word(s,SEG143E_VgaDataRotateMirror,s->ax);
    s->ax=0xff08u;
    out_word(s,SEG143E_VgaBitMaskMirror,s->ax);
    s->dx=(uint16_t)((s->dx&0xff00u)|0x00c4u); /* MOV DL,C4 */
    s->ax=0x0202u;
    out_word(s,SEG143E_VgaMapMaskMirror,s->ax);
}

static void setup_next_plane(ShiftedMaskedState *s,uint8_t map_mask) {
    add_si(s,live_plane_extent(s));
    s->ax=(uint16_t)(((uint16_t)map_mask<<8)|0x02u);
    out_word(s,SEG143E_VgaMapMaskMirror,s->ax);
}

static void later_plane(ShiftedMaskedState *s) {
    push(s,s->di);
    push(s,s->si);
    push(s,s->cx);
    do {
        later_maskless_row(s);
    } while((s->cx&0xff00u)!=0);
    s->cx=pop(s);
    s->si=pop(s);
    s->di=pop(s);
    s->bp=dec16(s,s->bp);
}

static void final_plane(ShiftedMaskedState *s) {
    do {
        final_maskless_row(s);
    } while((s->cx&0xff00u)!=0);
}

static LmnShiftedMaskedResult run_core(uint8_t *memory,
    const LmnShiftedMaskedCall *call,const LmnRasterBus *bus) {
    ShiftedMaskedState s={memory,bus,0,call->mask_cursor,call->packed_counts,
        call->width_state,call->source_cursor,call->destination_cursor,0,
        call->stack_offset,call->initial_data_segment,0,call->stack_segment,
        call->flags,call->game_data_segment};

    sub_word_at(&s,s.ds,SEG09A9_DrawingActiveDestinationRowAdvance);
    push(&s,s.ds);
    s.ds=read16(&s,s.ds,SEG09A9_GraphicsResourceSegment);
    s.ax=s.game_ds; /* relocated MOV AX,09A9 */
    s.es=s.ax;
    setup_first_plane(&s);

    first_plane(&s);
    if(s.bp!=0) {
        setup_second_plane(&s);
        later_plane(&s);
        if(s.bp!=0) {
            setup_next_plane(&s,0x04u);
            later_plane(&s);
            if(s.bp!=0) {
                setup_next_plane(&s,0x08u);
                final_plane(&s);
            }
        }
    }

    s.ds=pop(&s); /* 8B40 POP DS; the original 8B41 RETF remains outside. */
    {
        LmnShiftedMaskedResult result={s.ax,s.cx,s.dx,s.si,s.bx,s.di,s.bp,
            s.sp,s.ds,s.es,s.flags};
        return result;
    }
}

LmnShiftedMaskedResult lmn_draw_shifted_masked_core(uint8_t *memory,
    const LmnShiftedMaskedCall *call,const LmnRasterBus *bus) {
    return run_core(memory,call,bus);
}

void lmn_draw_shifted_masked_adapter(uint8_t *memory,LmnRegs *regs,
    uint16_t game_data_segment,const LmnRasterBus *bus) {
    LmnShiftedMaskedCall call={regs->ds,game_data_segment,regs->ss,regs->sp,
        regs->cx,regs->dx,regs->si,regs->bx,regs->di,regs->flags};
    LmnShiftedMaskedResult result=run_core(memory,&call,bus);
    ShiftedMaskedState s={memory,bus,result.work_value,result.mask_cursor,
        result.packed_counts,result.port,result.source_cursor,
        result.destination_cursor,result.plane_counter,result.stack_offset,
        result.source_segment,result.output_segment,regs->ss,result.flags,
        game_data_segment};
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

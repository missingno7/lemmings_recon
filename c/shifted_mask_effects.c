#include "shifted_mask_effects.h"
#include "lemmings_sym.h"

#ifndef SHIFTED_EFFECT_MUTATION
#define SHIFTED_EFFECT_MUTATION 0
#endif

enum { CF=0x001, PF=0x004, AF=0x010, ZF=0x040, SF=0x080,
       IF=0x200, DF=0x400, OF=0x800, ARITH=0x8d5 };

typedef struct ShiftedEffectState {
    uint8_t *mem;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp,sp,ds,es,ss,flags;
} ShiftedEffectState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+(uint32_t)offset)&0xfffffu;
}

static uint8_t read_byte(ShiftedEffectState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->mem,address,s->flags);
    return s->mem[address];
}

static void write_byte(ShiftedEffectState *s,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->mem,address,value,s->flags);
    else
        s->mem[address]=value;
}

static uint8_t read8(ShiftedEffectState *s,uint16_t segment,uint16_t offset) {
    return read_byte(s,physical(segment,offset));
}

static uint16_t read16(ShiftedEffectState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(s,address);
    uint8_t high=read_byte(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ShiftedEffectState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_byte(s,address,(uint8_t)value);
    write_byte(s,address+1u,(uint8_t)(value>>8));
}

static void push(ShiftedEffectState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(ShiftedEffectState *s) {
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

static void logical_flags(ShiftedEffectState *s,uint16_t value,unsigned width) {
    /* AF is undefined after logical operations; retain its physical bit. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(value,width));
}

static void and_flags8(ShiftedEffectState *s,uint8_t value) {
    logical_flags(s,value,8);
}

static void add_flags16(ShiftedEffectState *s,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum;
    s->flags=(uint16_t)((s->flags&(uint16_t)~ARITH)|szp(value,16)|
        (sum>0xffffu?CF:0u)|((left^right^value)&AF)|
        (((uint16_t)~(left^right)&(left^value)&0x8000u)?OF:0u));
}

static void dec_flags8(ShiftedEffectState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0?AF:0u)|(before==0x80u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
}

static void dec_flags16(ShiftedEffectState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0?AF:0u)|(before==0x8000u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
}

static uint16_t inc_flags16(ShiftedEffectState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fffu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t inc_flags8(ShiftedEffectState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t shr1(ShiftedEffectState *s,uint8_t value) {
    uint8_t result=(uint8_t)(value>>1);
    /* SHR count one defines CF and OF; AF is undefined. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(result,8)|(value&1u)|((value&0x80u)?OF:0u));
    return result;
}

static uint8_t rcr1(ShiftedEffectState *s,uint8_t value) {
    uint8_t carry=(uint8_t)(s->flags&CF);
    uint8_t result=(uint8_t)((value>>1)|(carry?0x80u:0u));
#if SHIFTED_EFFECT_MUTATION == 1
    result=(uint8_t)(value>>1); /* Test mutant drops the incoming carry. */
#endif
    {
        uint16_t changed=(uint16_t)((s->flags&(uint16_t)~(CF|OF))|
            (value&1u));
        if(((result>>7)^((result>>6)&1u))!=0) changed|=OF;
        s->flags=changed;
    }
    return result;
}

static void out_word(ShiftedEffectState *s,uint16_t mirror,uint16_t value) {
    write16(s,s->ss,mirror,value);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,value,s->flags);
}

static void mask_draw_byte(ShiftedEffectState *s) {
    uint8_t mask=read8(s,s->ds,s->bx);
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)mask<<8));
    s->bx=inc_flags16(s,s->bx); /* INC BX is forward even under DF. */
    s->ax=(uint16_t)((s->ax&0xff00u)|0x0008u);
    out_word(s,SEG143E_VgaBitMaskMirror,s->ax);
    s->flags=(uint16_t)(s->flags&(uint16_t)~IF); /* CLI */
    (void)read8(s,s->es,s->di); /* VGA latch read */
    s->ax=(uint16_t)((s->ax&0xff00u)|0x00ffu);
    write_byte(s,physical(s->es,s->di),(uint8_t)s->ax); /* STOSB */
    s->di=(uint16_t)(s->di+((s->flags&DF)?0xffffu:1u));
    s->flags=(uint16_t)(s->flags|IF); /* STI */
    s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves flags. */
}

static LmnShiftedMaskEffectResult run_shifted_effect(uint8_t *memory,
    const LmnShiftedMaskEffectCall *call,const LmnRasterBus *bus,
    unsigned forty) {
    ShiftedEffectState s={memory,bus,0,call->mask_cursor,call->packed_counts,
        0,0,call->destination_cursor,call->control,call->stack_offset,
        call->initial_data_segment,0,call->stack_segment,call->flags};
    uint16_t initial_row_word;
    uint8_t shifts;

    /* Entry DEC reads incoming DS. Later fields are read through the live DS
       restored from the relocated ES value and the original SS save words. */
    initial_row_word=read16(&s,s.ds,SEG09A9_DrawingActiveDestinationRowAdvance);
    write16(&s,s.ds,SEG09A9_DrawingActiveDestinationRowAdvance,
        (uint16_t)(initial_row_word-1u));
    dec_flags16(&s,initial_row_word);
    push(&s,s.ds);
    s.ds=read16(&s,s.ds,SEG09A9_GraphicsResourceSegment);
    s.ax=call->game_data_segment;
    s.es=s.ax;
    s.dx=0x03c4u;
    s.ax=0x0f02u;
    out_word(&s,SEG143E_VgaMapMaskMirror,s.ax);
    s.dx=0x03ceu;
    if(forty) {
        s.ax=0;
        logical_flags(&s,s.ax,16); /* XOR AX,AX */
    } else {
        s.ax=0x0f00u;
    }
    out_word(&s,SEG143E_VgaSetResetMirror,s.ax);
    s.ax=(uint16_t)((s.bp&0x0f00u)|0x0001u);
    and_flags8(&s,(uint8_t)(s.ax>>8));
    s.ax=(uint16_t)((s.ax&0xff00u)|0x0001u);
    out_word(&s,SEG143E_VgaEnableSetResetMirror,s.ax);
    s.ax=0x0005u;
    out_word(&s,SEG143E_VgaGraphicsModeMirror,s.ax);
    s.ax=0x0003u;
    out_word(&s,SEG143E_VgaDataRotateMirror,s.ax);
    s.si=s.bx; /* MOV SI,BX */

    for(;;) {
        uint16_t saved_ds,saved_es;
        uint8_t count;
        int direction=(s.flags&DF)?-1:1;

        push(&s,s.ds);
        push(&s,s.es);
        push(&s,s.cx);
        push(&s,s.cx);
        push(&s,s.di);
        s.cx=(uint16_t)(s.cx&0x00ffu);
        logical_flags(&s,0,8); /* XOR CH,CH */
        s.di=SEG09A9_DrawingMaskRowScratch;
        count=(uint8_t)s.cx;
        while(count!=0) {
            uint8_t value=read8(&s,s.ds,s.si);
            write_byte(&s,physical(s.es,s.di),value);
            s.si=(uint16_t)(s.si+direction);
            s.di=(uint16_t)(s.di+direction);
            --count;
        }
        s.ax=(uint16_t)(s.ax&0xff00u); /* XOR AL,AL */
        logical_flags(&s,0,8);
        write_byte(&s,physical(s.es,s.di),(uint8_t)s.ax); /* STOSB */
        s.di=(uint16_t)(s.di+direction);
        s.di=pop(&s);
        s.cx=pop(&s);
        push(&s,s.si);
        push(&s,s.es);
        s.ds=pop(&s);
        s.ax=0xa000u;
        s.es=s.ax;
        s.bx=SEG09A9_DrawingMaskRowScratch;
        shifts=read8(&s,s.ds,SEG09A9_DrawingLeftBitShiftByte);
        do {
            uint16_t loop_count;
            uint8_t value;

            push(&s,s.bx);
            push(&s,s.cx);
            s.cx=(uint16_t)(s.cx&0x00ffu);
            logical_flags(&s,0,8); /* XOR CH,CH */
            value=read8(&s,s.ds,s.bx);
            {
                uint16_t flags_before=s.flags;
                uint16_t flags_after;
                value=shr1(&s,value);
                flags_after=s.flags;
                /* The memory write hook sees incoming SHR flags. */
                s.flags=flags_before;
                write_byte(&s,physical(s.ds,s.bx),value);
                s.flags=flags_after;
            }
            s.bx=inc_flags16(&s,s.bx);
#if SHIFTED_EFFECT_MUTATION == 2
            if(s.flags&DF) s.bx=(uint16_t)(s.bx-2u);
#endif
            loop_count=s.cx;
            do {
                value=read8(&s,s.ds,s.bx);
                {
                    uint16_t flags_before=s.flags;
                    uint16_t flags_after;
                    value=rcr1(&s,value);
                    flags_after=s.flags;
                    s.flags=flags_before;
                    write_byte(&s,physical(s.ds,s.bx),value);
                    s.flags=flags_after;
                }
                s.bx=inc_flags16(&s,s.bx);
#if SHIFTED_EFFECT_MUTATION == 2
                if(s.flags&DF) s.bx=(uint16_t)(s.bx-2u);
#endif
                loop_count=(uint16_t)(loop_count-1u);
            } while(loop_count!=0);
            s.cx=pop(&s);
            s.bx=pop(&s);
            shifts=(uint8_t)(shifts-1u);
            dec_flags8(&s,(uint8_t)(shifts+1u));
        } while(shifts!=0);

        s.cx=(uint16_t)(s.cx&0x00ffu);
        logical_flags(&s,0,8); /* XOR CH,CH */
        {
            uint8_t before=(uint8_t)s.cx;
            uint8_t low=inc_flags8(&s,before);
            s.cx=(uint16_t)((s.cx&0xff00u)|low);
        }
        do {
            mask_draw_byte(&s);
        } while(s.cx!=0);

        s.si=pop(&s);
        {
            uint16_t before=s.si;
            uint16_t advance=read16(&s,s.ds,
                SEG09A9_DrawingSourceRowAdvance);
#if SHIFTED_EFFECT_MUTATION == 3
            if(forty) s.bx=(uint16_t)(s.bx+advance);
#endif
            s.si=(uint16_t)(before+advance);
            add_flags16(&s,before,advance);
        }
        {
            uint16_t before=s.di;
            uint16_t advance=read16(&s,s.ds,
                SEG09A9_DrawingActiveDestinationRowAdvance);
            s.di=(uint16_t)(before+advance);
            add_flags16(&s,before,advance);
        }
        s.cx=pop(&s);
        saved_es=pop(&s);
        saved_ds=pop(&s);
        s.es=saved_es;
        s.ds=saved_ds;
        {
            uint8_t before=(uint8_t)(s.cx>>8);
            uint8_t high=(uint8_t)(before-1u);
            dec_flags8(&s,before);
            s.cx=(uint16_t)((s.cx&0x00ffu)|((uint16_t)high<<8));
            if(high==0) break;
        }
    }

    s.ds=pop(&s);
    {
        LmnShiftedMaskEffectResult result={s.ax,s.cx,s.dx,s.si,s.bx,s.di,
            s.bp,s.sp,s.ds,s.es,s.flags};
        return result;
    }
}

LmnShiftedMaskEffectResult lmn_draw_shifted_mask20_core(uint8_t *memory,
    const LmnShiftedMaskEffectCall *call,const LmnRasterBus *bus) {
    return run_shifted_effect(memory,call,bus,0);
}

LmnShiftedMaskEffectResult lmn_draw_shifted_mask40_core(uint8_t *memory,
    const LmnShiftedMaskEffectCall *call,const LmnRasterBus *bus) {
    return run_shifted_effect(memory,call,bus,1);
}

static void adapter(uint8_t *memory,LmnRegs *regs,uint16_t game_data_segment,
    const LmnRasterBus *bus,unsigned forty) {
    LmnShiftedMaskEffectCall call={regs->ds,game_data_segment,regs->ss,
        regs->sp,regs->cx,regs->bx,regs->di,regs->bp,regs->flags};
    LmnShiftedMaskEffectResult result=run_shifted_effect(memory,&call,bus,forty);
    ShiftedEffectState s={memory,bus,result.work_value,result.mask_cursor,
        result.packed_counts,result.port,result.source_cursor,
        result.destination_cursor,result.control,result.stack_offset,
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
    regs->bp=result.control;
    regs->sp=s.sp;
    regs->ds=result.source_segment;
    regs->es=result.output_segment;
    regs->flags=result.flags;
}

void lmn_draw_shifted_mask20_adapter(uint8_t *memory,LmnRegs *regs,
    uint16_t game_data_segment,const LmnRasterBus *bus) {
    adapter(memory,regs,game_data_segment,bus,0);
}

void lmn_draw_shifted_mask40_adapter(uint8_t *memory,LmnRegs *regs,
    uint16_t game_data_segment,const LmnRasterBus *bus) {
    adapter(memory,regs,game_data_segment,bus,1);
}

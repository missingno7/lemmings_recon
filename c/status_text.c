#include "status_text.h"
#include "status_glyph.h"
#include "lemmings_sym.h"

#ifndef STATUS_TEXT_MUTATION
#define STATUS_TEXT_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffffu,
    CF = 0x0001u, PF = 0x0004u, AF = 0x0010u, ZF = 0x0040u,
    SF = 0x0080u, IF = 0x0200u, DF = 0x0400u, OF = 0x0800u,
    ARITHMETIC_FLAGS = CF | PF | AF | ZF | SF | OF,
    LOGIC_FLAGS = CF | PF | ZF | SF | OF
};

typedef struct StatusTextState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
    uint16_t initial_data_segment;
} StatusTextState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment << 4) + offset) & MEMORY_MASK);
}

static uint8_t read_physical(StatusTextState *s,uint32_t address,
                             uint16_t flags) {
    address &= MEMORY_MASK;
    if(s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,flags);
    return s->memory[address];
}

static void write_physical(StatusTextState *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address &= MEMORY_MASK;
    if(s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(StatusTextState *s,uint16_t segment,uint16_t offset,
                     uint16_t flags) {
    return read_physical(s,physical(segment,offset),flags);
}

static uint16_t read16(StatusTextState *s,uint16_t segment,uint16_t offset,
                       uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address,flags);
    uint8_t high=read_physical(s,address+1u,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(StatusTextState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp8(uint8_t value) {
    unsigned parity=0,bit;
    uint16_t out=0;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x80u)out|=SF;
    return out;
}

/* AND defines CF/OF/SZP and leaves AF undefined; retain its opaque value. */
static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    return (uint16_t)((flags&~LOGIC_FLAGS)|szp8(value));
}

#if STATUS_TEXT_MUTATION != 3
static uint16_t add8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint16_t sum=(uint16_t)left+right;
    uint8_t value=(uint8_t)sum;
    uint16_t out=szp8(value);
    if(sum>0xffu)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if((~(left^right)&(left^value)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITHMETIC_FLAGS)|out);
}
#endif

static uint8_t al(const StatusTextState *s) {
    return (uint8_t)s->ax;
}

static uint8_t ah(const StatusTextState *s) {
    return (uint8_t)(s->ax>>8);
}

static void set_al(StatusTextState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(StatusTextState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void lodsb(StatusTextState *s) {
    uint16_t segment=s->ds;
    uint8_t value;
#if STATUS_TEXT_MUTATION == 5
    segment=s->initial_data_segment;
#endif
    value=read8(s,segment,s->si,s->flags);
    set_al(s,value);
#if STATUS_TEXT_MUTATION == 1
    s->si=(uint16_t)(s->si+1u);
#else
    s->si=(uint16_t)(s->si+((s->flags&DF)?(uint16_t)-1:1u));
#endif
}

static void push_word(StatusTextState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value,s->flags);
}

static uint16_t pop_word(StatusTextState *s) {
    uint16_t value=read16(s,s->ss,s->sp,s->flags);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

#if STATUS_TEXT_MUTATION != 3
static void inc_ah(StatusTextState *s) {
    uint16_t carry=(uint16_t)(s->flags&CF);
    uint8_t before=ah(s);
    set_ah(s,(uint8_t)(before+1u));
    s->flags=(uint16_t)((add8_flags(s->flags,before,1u)&~CF)|carry);
}
#endif

static LmnStatusGlyphCall glyph_call(const StatusTextState *s) {
    LmnStatusGlyphCall call;
    call.value=s->ax;call.map_cursor=s->bx;call.count=s->cx;
    call.auxiliary_value=s->dx;call.record_cursor=s->si;
    call.object_cursor=s->di;call.candidate_y=s->bp;
    call.code_segment=s->cs;call.data_segment=s->ds;
    call.extra_segment=s->es;call.stack_segment=s->ss;
    call.stack_offset=s->sp;call.flags=s->flags;
    return call;
}

static void apply_glyph(StatusTextState *s,const LmnStatusGlyphResult *glyph) {
    s->ax=glyph->value;s->bx=glyph->map_cursor;s->cx=glyph->count;
    s->dx=glyph->auxiliary_value;s->si=glyph->record_cursor;
    s->di=glyph->object_cursor;s->bp=glyph->candidate_y;
    s->cs=glyph->code_segment;s->ds=glyph->data_segment;
    s->es=glyph->extra_segment;s->ss=glyph->stack_segment;
    s->sp=glyph->stack_offset;s->flags=glyph->flags;
}

static LmnStatusTextResult result_of(const StatusTextState *s) {
    LmnStatusTextResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

LmnStatusTextResult lmn_draw_status_text_core(uint8_t *memory,
    const LmnStatusTextCall *call,const LmnRasterBus *bus) {
    StatusTextState s;
    s.memory=memory;s.bus=bus;
    s.ax=call->value;s.bx=call->map_cursor;s.cx=call->count;
    s.dx=call->auxiliary_value;s.si=call->record_cursor;
    s.di=call->object_cursor;s.bp=call->candidate_y;
    s.cs=call->code_segment;s.ds=call->data_segment;
    s.es=call->extra_segment;s.ss=call->stack_segment;
    s.sp=call->stack_offset;s.flags=call->flags;
    s.continuation=CS_StatusTextReturn;s.status=LMN_STATUS_TEXT_READY;
    s.initial_data_segment=s.ds;

    for(;;) {
#if STATUS_TEXT_MUTATION == 4
        uint16_t saved_ax,saved_si;
#endif
        uint16_t child_target;
        LmnStatusGlyphCall child_call;
        LmnStatusGlyphResult child;

        lodsb(&s);                                      /* LODSB */
        s.flags=logic8_flags(s.flags,al(&s));            /* AND AL,AL */
#if STATUS_TEXT_MUTATION == 2
        s.flags|=CF;                                     /* Wrong AND carry. */
#endif
        if(al(&s)==0u)break;                             /* JZ outer RET */

#if STATUS_TEXT_MUTATION == 4
        saved_ax=s.ax;saved_si=s.si;
#endif
        push_word(&s,s.ax);                              /* PUSH AX */
        push_word(&s,s.si);                              /* PUSH SI */
        push_word(&s,CS_StatusTextAfterGlyph);           /* CALL 7708 */
        child_call=glyph_call(&s);
        child=lmn_draw_status_glyph_core(memory,&child_call,bus);
        apply_glyph(&s,&child);                          /* all child outputs */

        if(child.status!=LMN_STATUS_GLYPH_READY) {
            s.continuation=child.continuation;
            s.status=LMN_STATUS_TEXT_CHILD_STOP;
            return result_of(&s);
        }
        if(child.continuation!=CS_StatusGlyphReturn &&
           child.continuation!=CS_StatusGlyphSpaceReturn) {
            s.continuation=child.continuation;
            s.status=LMN_STATUS_TEXT_UNEXPECTED_GLYPH_RETURN;
            return result_of(&s);                        /* stop before RET */
        }
#if STATUS_TEXT_MUTATION == 7
        if(child.continuation==CS_StatusGlyphSpaceReturn) {
            s.continuation=child.continuation;
            s.status=LMN_STATUS_TEXT_UNEXPECTED_GLYPH_RETURN;
            return result_of(&s);
        }
#endif

        child_target=pop_word(&s);                       /* actual glyph RET */
        s.continuation=child_target;
#if STATUS_TEXT_MUTATION != 6
        if(child_target!=CS_StatusTextAfterGlyph) {
            s.status=LMN_STATUS_TEXT_CHANGED_CHILD_RETURN;
            return result_of(&s);                        /* before caller POPs */
        }
#endif
        s.si=pop_word(&s);                               /* POP SI, live SS */
#if STATUS_TEXT_MUTATION == 4
        s.si=saved_si;
#endif
        s.ax=pop_word(&s);                               /* POP AX, live SS */
#if STATUS_TEXT_MUTATION == 4
        s.ax=saved_ax;
#endif
#if STATUS_TEXT_MUTATION == 3
        /* Mutation: skip INC AH. */
        set_ah(&s,ah(&s));
#else
        inc_ah(&s);                                      /* INC AH */
#endif
    }

    s.continuation=CS_StatusTextReturn;
    s.status=LMN_STATUS_TEXT_READY;
    return result_of(&s);                                /* before outer RET */
}

static uint16_t adapter_read_return(uint8_t *memory,uint16_t ss,uint16_t sp,
    uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(ss,sp);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,(address+1u)&MEMORY_MASK,flags);
    } else {
        low=memory[address];high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void apply_result(LmnRegs *r,const LmnStatusTextResult *out) {
    r->ax=out->value;r->bx=out->map_cursor;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->record_cursor;
    r->di=out->object_cursor;r->bp=out->candidate_y;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;r->ip=out->continuation;
}

uint16_t lmn_draw_status_text_adapter(uint8_t *memory,LmnRegs *r,
    const LmnRasterBus *bus) {
    LmnStatusTextCall call;
    LmnStatusTextResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_draw_status_text_core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_STATUS_TEXT_READY) {
        r->ip=adapter_read_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

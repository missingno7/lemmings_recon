#include "status_count.h"
#include "lemmings_sym.h"

#ifndef STATUS_COUNT_MUTATION
#define STATUS_COUNT_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF,
    INC_ARITH=PF|AF|ZF|SF|OF
};

typedef struct StatusCountState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
} StatusCountState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(StatusCountState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(StatusCountState *s,uint32_t address,uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(StatusCountState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(StatusCountState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(StatusCountState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(StatusCountState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static uint16_t szp8(uint8_t value) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x80u)out|=SF;
    return out;
}

static uint16_t szp16(uint16_t value) {
    uint16_t out=(uint16_t)(szp8((uint8_t)value)&PF);
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    /* Logical AF is undefined; keep it stable for bus observations. */
    return (uint16_t)((flags&~LOGIC)|szp8(value));
}

static uint16_t logic16_flags(uint16_t flags,uint16_t value) {
    return (uint16_t)((flags&~LOGIC)|szp16(value));
}

static uint16_t add8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint16_t wide=(uint16_t)left+(uint16_t)right;
    uint8_t result=(uint8_t)wide;
    uint16_t out=szp8(result);
    if(wide>0xffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t sub8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t result=(uint8_t)(left-right);
    uint16_t out=szp8(result);
    if(left<right)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)wide,out=szp16(result);
    if(wide>0xffffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before+1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0x0fu)out|=AF;
    if(before==0x7fu)out|=OF;
    return (uint16_t)((flags&~INC_ARITH)|out|(flags&CF));
}

static uint16_t inc16_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before+1u);
    uint16_t out=szp16(result);
    if((before&0x000fu)==0x000fu)out|=AF;
    if(before==0x7fffu)out|=OF;
    return (uint16_t)((flags&~INC_ARITH)|out|(flags&CF));
}

static uint16_t dec8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before-1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0u)out|=AF;
    if(before==0x80u)out|=OF;
    return (uint16_t)((flags&~INC_ARITH)|out|(flags&CF));
}

static uint16_t add_di_flags(uint16_t flags,uint16_t before,uint16_t amount) {
    return add16_flags(flags,before,amount);
}

static uint8_t al(const StatusCountState *s) {
    return (uint8_t)s->ax;
}

static uint8_t ah(const StatusCountState *s) {
    return (uint8_t)(s->ax>>8);
}

static void set_al(StatusCountState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(StatusCountState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void add_di(StatusCountState *s,uint16_t amount) {
    uint16_t before=s->di;
    s->di=(uint16_t)(before+amount);
    s->flags=add_di_flags(s->flags,before,amount);
}

static uint16_t pop_word(StatusCountState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void push_word(StatusCountState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static void port_word(StatusCountState *s) {
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
}

static void mirror_and_out(StatusCountState *s,uint16_t mirror_offset) {
    write16(s,s->ss,mirror_offset,s->ax);
    port_word(s);
}

static void cli(StatusCountState *s) {
#if STATUS_COUNT_MUTATION == 7
    (void)s;
#else
    s->flags=(uint16_t)(s->flags&~IF);
#endif
}

static void sti(StatusCountState *s) {
    s->flags=(uint16_t)(s->flags|IF);
}

static void lodsb(StatusCountState *s) {
    uint16_t offset=s->si;
    uint8_t value=read8(s,s->ds,offset);
    set_al(s,value);
#if STATUS_COUNT_MUTATION == 6
    s->si=(uint16_t)(offset+1u);
#else
    s->si=(uint16_t)(offset+((s->flags&DF)?(uint16_t)-1:1u));
#endif
}

static void stosb(StatusCountState *s) {
    uint16_t offset=s->di;
    write8(s,s->es,offset,al(s));
#if STATUS_COUNT_MUTATION == 6
    s->di=(uint16_t)(offset+1u);
#else
    s->di=(uint16_t)(offset+((s->flags&DF)?(uint16_t)-1:1u));
#endif
}

static void output_word(StatusCountState *s,uint16_t mirror,uint16_t value) {
    s->ax=value;
    mirror_and_out(s,mirror);
}

static void setup_vga(StatusCountState *s) {
    s->dx=0xa000u;s->es=s->dx;
    s->dx=0x03c4u;
    output_word(s,SEG143E_VgaMapMaskMirror,0x0f02u);
    s->dx=0x03ceu;
    s->ax=0u;s->flags=logic16_flags(s->flags,0u);
    mirror_and_out(s,SEG143E_VgaSetResetMirror);
    output_word(s,SEG143E_VgaEnableSetResetMirror,0x0c01u);
    output_word(s,SEG143E_VgaGraphicsModeMirror,0x0005u);
    output_word(s,SEG143E_VgaDataRotateMirror,0x0003u);
    output_word(s,SEG143E_VgaBitMaskMirror,0x0f08u);
}

static void read_pixel_into_al(StatusCountState *s) {
    set_al(s,read8(s,s->es,s->di));
}

static void read_pixel_into_ah(StatusCountState *s) {
    set_ah(s,read8(s,s->es,s->di));
}

static void draw_glyph_rows(StatusCountState *s) {
    unsigned row;
    s->cx=8u;
    for(row=0;row<8u;++row) {
        cli(s);
        read_pixel_into_al(s);   /* MOV AL,[ES:DI] observes VGA latch. */
        lodsb(s);                /* LODSB uses the live DS:SI and DF. */
        stosb(s);                /* STOSB uses the live ES:DI and DF. */
        sti(s);
        add_di(s,0x002bu);       /* Fixed forward row increment. */
        s->cx=(uint16_t)(s->cx-1u); /* LOOP does not change FLAGS. */
    }
}

static void blank_rows(StatusCountState *s) {
    unsigned row;
    s->cx=8u;
    set_al(s,0xffu);
    for(row=0;row<8u;++row) {
        cli(s);
        read_pixel_into_ah(s);   /* MOV AH,[ES:DI] loads the VGA latch. */
        stosb(s);
        sti(s);
        add_di(s,0x002bu);
        s->cx=(uint16_t)(s->cx-1u); /* LOOP preserves FLAGS. */
    }
}

static LmnStatusCountResult result_of(const StatusCountState *s) {
    LmnStatusCountResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

LmnStatusCountResult lmn_draw_status_count_core(uint8_t *memory,
    const LmnStatusCountCall *call,const LmnRasterBus *bus) {
    StatusCountState s;
#if STATUS_COUNT_MUTATION == 3
    uint16_t entry_value=call->value;
#endif
#if STATUS_COUNT_MUTATION == 4
    uint16_t saved_di_value;
#endif
#if STATUS_COUNT_MUTATION == 5
    uint16_t cached_glyph_segment;
#endif

    s.memory=memory;s.bus=bus;
    s.ax=call->value;s.bx=call->map_cursor;s.cx=call->count;
    s.dx=call->auxiliary_value;s.si=call->record_cursor;
    s.di=call->object_cursor;s.bp=call->candidate_y;
    s.cs=call->code_segment;s.ds=call->data_segment;
    s.es=call->extra_segment;s.ss=call->stack_segment;
    s.sp=call->stack_offset;s.flags=call->flags;
    s.continuation=CS_StatusCountReturn;s.status=LMN_STATUS_COUNT_READY;
#if STATUS_COUNT_MUTATION == 5
    /* Mutant reads the source segment before setup/provider activity. */
    cached_glyph_segment=read16(&s,s.ds,
                                SEG09A9_StatusGlyphBufferSegment);
#endif

    push_word(&s,s.ds);                         /* PUSH DS */
    push_word(&s,s.ax);                         /* PUSH AX */
    set_ah(&s,0u);                              /* XOR AH,AH */
    s.flags=logic8_flags(s.flags,0u);
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(before+before);          /* ADD AX,AX */
        s.flags=add16_flags(s.flags,before,before);
    }
    s.di=s.ax;                                  /* MOV DI,AX */
    add_di(&s,0x212cu);
    {
        uint16_t origin=read16(&s,s.ds,SEG09A9_DrawingOrigin);
        add_di(&s,origin);
    }
    add_di(&s,0x0002u);
    setup_vga(&s);

    s.ax=pop_word(&s);                          /* POP AX from live SS:SP */
#if STATUS_COUNT_MUTATION == 3
    s.ax=entry_value;                            /* Ignore the actual word. */
#endif
#if STATUS_COUNT_MUTATION == 1
    if(ah(&s)>=100u)set_ah(&s,99u);              /* Incorrect count clamp. */
#endif
    s.flags=logic8_flags(s.flags,ah(&s));         /* AND AH,AH */
    if(ah(&s)==0u) {
        push_word(&s,s.di);                      /* PUSH DI */
        blank_rows(&s);                          /* Eight blank first rows. */
        s.di=pop_word(&s);                       /* POP DI, live stack read. */
        s.di=(uint16_t)(s.di+1u);                /* INC DI */
        s.flags=inc16_flags(s.flags,(uint16_t)(s.di-1u));
        s.ax=0xf008u;                           /* MOV AX,F008 */
        mirror_and_out(&s,SEG143E_VgaBitMaskMirror);
        set_al(&s,0xffu);                       /* MOV AL,FF */
        blank_rows(&s);                         /* Eight blank second rows. */
        s.ds=pop_word(&s);                      /* POP DS, live stack read. */
        s.continuation=CS_StatusCountBlankReturn;
        return result_of(&s);
    }

    set_al(&s,0u);                              /* XOR AL,AL */
    s.flags=logic8_flags(s.flags,0u);
    for(;;) {
        uint8_t before_al=al(&s),before_ah=ah(&s);
        set_al(&s,(uint8_t)(before_al+1u));      /* INC AL */
        s.flags=inc8_flags(s.flags,before_al);
        set_ah(&s,(uint8_t)(before_ah-0x0au));  /* SUB AH,0A */
        s.flags=sub8_flags(s.flags,before_ah,0x0au);
        if(s.flags&CF)break;                     /* JNC loc_767E */
    }
    {
        uint8_t before=al(&s);
        set_al(&s,(uint8_t)(before-1u));         /* DEC AL */
        s.flags=dec8_flags(s.flags,before);
    }
    {
        uint8_t before=ah(&s);
        set_ah(&s,(uint8_t)(before+0x0au));     /* ADD AH,0A */
        s.flags=add8_flags(s.flags,before,0x0au);
    }
    push_word(&s,s.ax);                          /* PUSH quotient/remainder */
    set_ah(&s,0u);                              /* XOR AH,AH */
    s.flags=logic8_flags(s.flags,0u);
    {
        unsigned i;
        for(i=0;i<4u;++i) {
            uint16_t before=s.ax;
            s.ax=(uint16_t)(before+before);      /* Four ADD AX,AXs */
            s.flags=add16_flags(s.flags,before,before);
        }
    }
#if STATUS_COUNT_MUTATION == 2
    s.ax=(uint16_t)((s.ax/16u)*10u);              /* Wrong 10-byte stride. */
    s.flags=add16_flags(s.flags,s.ax,0u);
#else
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(before+0u);              /* ADD AX,0 */
        s.flags=add16_flags(s.flags,before,0u);
    }
#endif
    s.si=s.ax;                                  /* MOV SI,AX */
#if STATUS_COUNT_MUTATION == 5
    s.ds=cached_glyph_segment;
#else
    s.ds=read16(&s,s.ds,SEG09A9_StatusGlyphBufferSegment);
#endif
#if STATUS_COUNT_MUTATION == 4
    saved_di_value=s.di;
#endif
    push_word(&s,s.di);                          /* PUSH DI */
    draw_glyph_rows(&s);                        /* Eight first-glyph rows. */
    s.di=pop_word(&s);                          /* POP DI, actual live word. */
#if STATUS_COUNT_MUTATION == 4
    s.di=saved_di_value;
#endif
    {
        uint16_t before=s.di;
        s.di=(uint16_t)(before+1u);              /* INC DI */
        s.flags=inc16_flags(s.flags,before);
    }
    s.ax=pop_word(&s);                          /* POP AX, actual count. */
#if STATUS_COUNT_MUTATION == 3
    s.ax=entry_value;
#endif
    set_al(&s,ah(&s));                          /* MOV AL,AH */
    set_ah(&s,0u);                              /* XOR AH,AH */
    s.flags=logic8_flags(s.flags,0u);
    {
        unsigned i;
        for(i=0;i<4u;++i) {
            uint16_t before=s.ax;
            s.ax=(uint16_t)(before+before);      /* Four ADD AX,AXs */
            s.flags=add16_flags(s.flags,before,before);
        }
    }
#if STATUS_COUNT_MUTATION == 2
    s.ax=(uint16_t)((s.ax/16u)*10u+8u);
    s.flags=add16_flags(s.flags,s.ax,0u);
#else
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(before+8u);             /* ADD AX,8 */
        s.flags=add16_flags(s.flags,before,8u);
    }
#endif
    s.si=s.ax;                                  /* MOV SI,AX */
    s.ax=0xf008u;                               /* MOV AX,F008 */
    mirror_and_out(&s,SEG143E_VgaBitMaskMirror);
    draw_glyph_rows(&s);                        /* Eight remainder rows. */
    s.ds=pop_word(&s);                          /* POP DS, actual saved word. */
    s.continuation=CS_StatusCountReturn;
    return result_of(&s);
}

static void apply_result(LmnRegs *r,const LmnStatusCountResult *out) {
    r->ax=out->value;r->bx=out->map_cursor;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->record_cursor;
    r->di=out->object_cursor;r->bp=out->candidate_y;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;r->ip=out->continuation;
}

static uint16_t read_stack_return(uint8_t *memory,uint16_t ss,uint16_t sp,
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

uint16_t lmn_draw_status_count_adapter(uint8_t *memory,LmnRegs *r,
    const LmnRasterBus *bus) {
    LmnStatusCountCall call;
    LmnStatusCountResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_draw_status_count_core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_STATUS_COUNT_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

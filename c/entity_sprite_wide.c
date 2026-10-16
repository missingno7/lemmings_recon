#include "entity_sprite_wide.h"

#include "lemmings_sym.h"

#ifndef ENTITY_SPRITE_WIDE_MUTATION
#define ENTITY_SPRITE_WIDE_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF,
    DEC_FLAGS=PF|AF|ZF|SF|OF
};

typedef struct EntityWideSpriteState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t entry_ds,continuation,status;
} EntityWideSpriteState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+(uint32_t)offset)&MEMORY_MASK);
}

static uint8_t read_physical(EntityWideSpriteState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(EntityWideSpriteState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(EntityWideSpriteState *s,uint16_t segment,
                     uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(EntityWideSpriteState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(EntityWideSpriteState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(EntityWideSpriteState *s,uint16_t segment,
                    uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static uint16_t szp16(uint16_t value) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0u;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)wide,out=szp16(result);
    if(wide>0xffffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc16_flags(uint16_t flags,uint16_t before) {
    uint16_t updated=add16_flags(flags,before,1u);
    return (uint16_t)((updated&~CF)|(flags&CF));
}

static uint16_t dec16_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before-1u),out=szp16(result);
    if((before^1u^result)&AF)out|=AF;
    if(before==0x8000u)out|=OF;
    return (uint16_t)((flags&~DEC_FLAGS)|out);
}

static uint16_t logic16_flags(uint16_t flags,uint16_t value) {
    return (uint16_t)((flags&~LOGIC)|szp16(value));
}

static void set_al(EntityWideSpriteState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(EntityWideSpriteState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void set_cl(EntityWideSpriteState *s,uint8_t value) {
    s->cx=(uint16_t)((s->cx&0xff00u)|value);
}

static void set_ch(EntityWideSpriteState *s,uint8_t value) {
    s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)value<<8));
}

static void inc_bx(EntityWideSpriteState *s) {
    uint16_t before=s->bx;
    s->bx=(uint16_t)(before+1u);
    s->flags=inc16_flags(s->flags,before);
}

static void add_di_row(EntityWideSpriteState *s) {
    uint16_t before=s->di;
    s->di=(uint16_t)(before+0x27u);
    s->flags=add16_flags(s->flags,before,0x27u);
}

static void push16(EntityWideSpriteState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop16(EntityWideSpriteState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void out_word(EntityWideSpriteState *s) {
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
}

static void out_then_mirror(EntityWideSpriteState *s,uint16_t mirror) {
    out_word(s);
#if ENTITY_SPRITE_WIDE_MUTATION != 6
    write16(s,s->ss,mirror,s->ax);
#else
    (void)mirror;
#endif
}

static void mirror_then_out(EntityWideSpriteState *s,uint16_t mirror) {
#if ENTITY_SPRITE_WIDE_MUTATION != 6
    write16(s,s->ss,mirror,s->ax);
#else
    (void)mirror;
#endif
    out_word(s);
}

static void cli(EntityWideSpriteState *s) {
#if ENTITY_SPRITE_WIDE_MUTATION != 7
    s->flags=(uint16_t)(s->flags&~IF);
#else
    (void)s;
#endif
}

static void sti(EntityWideSpriteState *s) {
    s->flags=(uint16_t)(s->flags|IF);
}

static uint8_t latch_read(EntityWideSpriteState *s) {
#if ENTITY_SPRITE_WIDE_MUTATION == 3
    (void)s;
    return 0u;
#else
    return read8(s,s->es,s->di);
#endif
}

static int lods_delta(const EntityWideSpriteState *s) {
#if ENTITY_SPRITE_WIDE_MUTATION == 1
    (void)s;
    return 1;
#else
    return (s->flags&DF)?-1:1;
#endif
}

static int stos_delta(const EntityWideSpriteState *s) {
#if ENTITY_SPRITE_WIDE_MUTATION == 2
    (void)s;
    return 1;
#else
    return (s->flags&DF)?-1:1;
#endif
}

static void lodsw(EntityWideSpriteState *s) {
    s->ax=read16(s,s->ds,s->si);
    s->si=(uint16_t)(s->si+2*lods_delta(s));
}

static void lodsb(EntityWideSpriteState *s) {
    set_al(s,read8(s,s->ds,s->si));
    s->si=(uint16_t)(s->si+lods_delta(s));
}

static void stosb(EntityWideSpriteState *s) {
    write8(s,s->es,s->di,(uint8_t)s->ax);
    s->di=(uint16_t)(s->di+stos_delta(s));
}

static void first_pass_row(EntityWideSpriteState *s) {
    push16(s,s->cx);                                   /* PUSH CX @6C15 */
    s->cx=read16(s,s->ds,s->bx);                       /* MOV CX,[BX] */
    inc_bx(s);inc_bx(s);                               /* INC BX x2 */
    set_al(s,0x08u);set_ah(s,(uint8_t)s->cx);          /* AL=8; AH=CL */
    mirror_then_out(s,SEG143E_VgaBitMaskMirror);
    cli(s);
    set_al(s,latch_read(s));
    lodsw(s);stosb(s);                                 /* source bytes 1-2 */
    sti(s);

    {
        uint8_t old_ch=(uint8_t)(s->cx>>8);
        uint8_t old_ah=(uint8_t)(s->ax>>8);
        set_ch(s,old_ah);set_ah(s,old_ch);             /* XCHG CH,AH */
    }
    set_al(s,0x08u);
    mirror_then_out(s,SEG143E_VgaBitMaskMirror);
    cli(s);
    set_al(s,latch_read(s));
    set_al(s,(uint8_t)(s->cx>>8));                     /* MOV AL,CH */
    stosb(s);
    sti(s);

    s->cx=read16(s,s->ds,s->bx);                       /* MOV CX,[BX] */
    inc_bx(s);inc_bx(s);
    set_al(s,0x08u);set_ah(s,(uint8_t)s->cx);
    mirror_then_out(s,SEG143E_VgaBitMaskMirror);
    cli(s);
    set_al(s,latch_read(s));
    lodsw(s);stosb(s);                                 /* source bytes 3-4 */
    sti(s);

    {
        uint8_t old_ch=(uint8_t)(s->cx>>8);
        uint8_t old_ah=(uint8_t)(s->ax>>8);
        set_ch(s,old_ah);set_ah(s,old_ch);             /* XCHG CH,AH */
    }
    set_al(s,0x08u);
    mirror_then_out(s,SEG143E_VgaBitMaskMirror);
    cli(s);
    set_al(s,latch_read(s));
    set_al(s,(uint8_t)(s->cx>>8));
    stosb(s);
    sti(s);

    set_cl(s,read8(s,s->ds,s->bx));                    /* MOV CL,[BX] */
    inc_bx(s);
#if ENTITY_SPRITE_WIDE_MUTATION == 9
    inc_bx(s);                                         /* extra cursor step */
#endif
    set_al(s,0x08u);set_ah(s,(uint8_t)s->cx);          /* AH=CL */
    mirror_then_out(s,SEG143E_VgaBitMaskMirror);
    cli(s);
    set_al(s,latch_read(s));
    lodsb(s);stosb(s);                                 /* source byte 5 */
    sti(s);
    add_di_row(s);
}

static void second_or_third_pass_row(EntityWideSpriteState *s) {
    push16(s,s->cx);                                   /* PUSH CX */
    cli(s);
    set_al(s,latch_read(s));
    lodsw(s);stosb(s);
    set_al(s,latch_read(s));
    set_al(s,(uint8_t)(s->ax>>8));                     /* MOV AL,AH */
    stosb(s);
    set_al(s,latch_read(s));
    lodsw(s);stosb(s);
    set_al(s,latch_read(s));
    set_al(s,(uint8_t)(s->ax>>8));
    stosb(s);
    set_al(s,latch_read(s));
    lodsb(s);stosb(s);
    sti(s);
    add_di_row(s);
}

static void first_pass(EntityWideSpriteState *s) {
#if ENTITY_SPRITE_WIDE_MUTATION == 8
    unsigned rows=0u;
#endif
    s->cx=0x20u;                                       /* MOV CX,20h */
    for(;;) {
        first_pass_row(s);
        s->cx=pop16(s);                                /* POP CX @6C76 */
        {
            uint16_t before=s->cx;
            s->cx=(uint16_t)(before-1u);               /* DEC CX @6C77 */
            s->flags=dec16_flags(s->flags,before);
        }
#if ENTITY_SPRITE_WIDE_MUTATION == 8
        ++rows;
        if(rows==0x20u)break;                           /* ignore live JZ */
#else
        if(s->cx==0u)break;                            /* JZ @6C78 */
#endif
    }
}

static void later_plane_pass(EntityWideSpriteState *s) {
    s->cx=0x20u;
    for(;;) {
        second_or_third_pass_row(s);
        s->cx=pop16(s);
        s->cx=(uint16_t)(s->cx-1u);                    /* LOOP dec; flags stay */
        if(s->cx==0u)break;
    }
}

static void initialize(EntityWideSpriteState *s,uint8_t *memory,
    const LmnEntityWideSpriteCall *call,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->entry_ds=call->data_segment;
    s->continuation=CS_EntityWideSprite32Return;
    s->status=LMN_ENTITY_WIDE_SPRITE_READY;
}

static LmnEntityWideSpriteResult result_of(const EntityWideSpriteState *s) {
    LmnEntityWideSpriteResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

LmnEntityWideSpriteResult lmn_draw_entity_wide_sprite32_core(uint8_t *memory,
    const LmnEntityWideSpriteCall *call,const LmnRasterBus *bus) {
    EntityWideSpriteState s;
    uint16_t live_ds;
    initialize(&s,memory,call,bus);

    push16(&s,s.ds);                                   /* PUSH DS @6BDB */
    s.dx=0x03c4u;s.ax=0x0f02u;
    out_then_mirror(&s,SEG143E_VgaMapMaskMirror);
    s.dx=0x03ceu;
    s.ax=0u;s.flags=logic16_flags(s.flags,s.ax);       /* XOR AX,AX */
    out_then_mirror(&s,SEG143E_VgaSetResetMirror);
    s.ax=0x0e01u;
    out_then_mirror(&s,SEG143E_VgaEnableSetResetMirror);
    s.ax=0x0005u;
    out_then_mirror(&s,SEG143E_VgaGraphicsModeMirror);
    s.ax=0x0003u;
    out_then_mirror(&s,SEG143E_VgaDataRotateMirror);
#if ENTITY_SPRITE_WIDE_MUTATION == 4
    s.ds=s.entry_ds;
#else
    s.ds=s.cx;                                         /* MOV DS,CX @6C09 */
#endif
    s.cx=0xa000u;s.es=s.cx;
    s.bp=s.di;
    first_pass(&s);

    s.di=s.bp;                                         /* MOV DI,BP @6C7C */
    s.ax=0x0001u;
    mirror_then_out(&s,SEG143E_VgaEnableSetResetMirror);
    s.ax=0x1003u;
    mirror_then_out(&s,SEG143E_VgaDataRotateMirror);
    s.ax=0xff08u;
    mirror_then_out(&s,SEG143E_VgaBitMaskMirror);
    s.dx=(uint16_t)((s.dx&0xff00u)|0x00c4u);           /* MOV DL,C4 */
    s.ax=0x0202u;
    mirror_then_out(&s,SEG143E_VgaMapMaskMirror);
    later_plane_pass(&s);

    s.di=s.bp;                                         /* MOV DI,BP @6CC7 */
    s.dx=(uint16_t)((s.dx&0xff00u)|0x00c4u);
#if ENTITY_SPRITE_WIDE_MUTATION == 10
    s.ax=0x0202u;                                      /* duplicate plane 2 */
#else
    s.ax=0x0402u;
#endif
    mirror_then_out(&s,SEG143E_VgaMapMaskMirror);
    later_plane_pass(&s);

    live_ds=pop16(&s);                                 /* POP DS @6CFA */
#if ENTITY_SPRITE_WIDE_MUTATION == 5
    (void)live_ds;
    s.ds=s.entry_ds;
#else
    s.ds=live_ds;
#endif
    return result_of(&s);                              /* before RET @6CFB */
}

static void apply_result(LmnRegs *r,const LmnEntityWideSpriteResult *out) {
    r->ax=out->value;r->bx=out->map_cursor;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->record_cursor;
    r->di=out->object_cursor;r->bp=out->candidate_y;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;
    r->ip=out->continuation;
}

static uint16_t read_return(uint8_t *memory,uint16_t ss,uint16_t sp,
    uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(ss,sp);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,
                            (address+1u)&MEMORY_MASK,flags);
    } else {
        low=memory[address];high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

uint16_t lmn_draw_entity_wide_sprite32_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus) {
    LmnEntityWideSpriteCall call;
    LmnEntityWideSpriteResult out;
    call.value=registers->ax;call.map_cursor=registers->bx;
    call.count=registers->cx;call.auxiliary_value=registers->dx;
    call.record_cursor=registers->si;call.object_cursor=registers->di;
    call.candidate_y=registers->bp;call.code_segment=registers->cs;
    call.data_segment=registers->ds;call.extra_segment=registers->es;
    call.stack_segment=registers->ss;call.stack_offset=registers->sp;
    call.flags=registers->flags;
    out=lmn_draw_entity_wide_sprite32_core(memory,&call,bus);
    apply_result(registers,&out);
    if(out.status==LMN_ENTITY_WIDE_SPRITE_READY) {
        registers->ip=read_return(memory,registers->ss,registers->sp,
                                  registers->flags,bus);
        registers->sp=(uint16_t)(registers->sp+2u);
    }
    return out.status;
}

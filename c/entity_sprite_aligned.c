#include "entity_sprite_aligned.h"

#include "lemmings_sym.h"

#ifndef ENTITY_SPRITE_ALIGNED_MUTATION
#define ENTITY_SPRITE_ALIGNED_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct EntityAlignedSpriteState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t entry_ds,continuation,status;
} EntityAlignedSpriteState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+(uint32_t)offset)&MEMORY_MASK);
}

static uint8_t read_physical(EntityAlignedSpriteState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(EntityAlignedSpriteState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(EntityAlignedSpriteState *s,uint16_t segment,
                     uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(EntityAlignedSpriteState *s,uint16_t segment,
                   uint16_t offset,uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(EntityAlignedSpriteState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(EntityAlignedSpriteState *s,uint16_t segment,
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

static uint16_t logic16_flags(uint16_t flags,uint16_t value) {
    uint16_t result=szp16(value);
    return (uint16_t)((flags&~LOGIC)|result);
}

static void set_al(EntityAlignedSpriteState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(EntityAlignedSpriteState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void set_ch(EntityAlignedSpriteState *s,uint8_t value) {
    s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)value<<8));
}

static void inc_bx(EntityAlignedSpriteState *s) {
    uint16_t before=s->bx;
    s->bx=(uint16_t)(before+1u);
    s->flags=inc16_flags(s->flags,before);
}

static void add_di_row(EntityAlignedSpriteState *s) {
    uint16_t before=s->di;
#if ENTITY_SPRITE_ALIGNED_MUTATION == 9
    const uint16_t stride=0x28u;
#else
    const uint16_t stride=0x29u;
#endif
    s->di=(uint16_t)(before+stride);
    s->flags=add16_flags(s->flags,before,stride);
}

static void push16(EntityAlignedSpriteState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop16(EntityAlignedSpriteState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void out_word(EntityAlignedSpriteState *s) {
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
}

static void mirror_out(EntityAlignedSpriteState *s,uint16_t mirror) {
#if ENTITY_SPRITE_ALIGNED_MUTATION == 6
    if(mirror!=SEG143E_VgaBitMaskMirror)
        write16(s,s->ss,mirror,s->ax);
#else
    write16(s,s->ss,mirror,s->ax);
#endif
    out_word(s);
}

static void cli(EntityAlignedSpriteState *s) {
#if ENTITY_SPRITE_ALIGNED_MUTATION != 7
    s->flags=(uint16_t)(s->flags&~IF);
#else
    (void)s;
#endif
}

static void sti(EntityAlignedSpriteState *s) {
    s->flags=(uint16_t)(s->flags|IF);
}

static uint8_t latch_read(EntityAlignedSpriteState *s) {
#if ENTITY_SPRITE_ALIGNED_MUTATION == 3
    (void)s;
    return 0u;
#else
    return read8(s,s->es,s->di);
#endif
}

static void lodsw(EntityAlignedSpriteState *s) {
    int16_t delta;
    s->ax=read16(s,s->ds,s->si);
#if ENTITY_SPRITE_ALIGNED_MUTATION == 1
    delta=1;
#else
    delta=(s->flags&DF)?-1:1;
#endif
    s->si=(uint16_t)(s->si+delta*2);
}

static void lodsb(EntityAlignedSpriteState *s) {
    int16_t delta;
    set_al(s,read8(s,s->ds,s->si));
#if ENTITY_SPRITE_ALIGNED_MUTATION == 1
    delta=1;
#else
    delta=(s->flags&DF)?-1:1;
#endif
    s->si=(uint16_t)(s->si+delta);
}

static void stosb(EntityAlignedSpriteState *s) {
    int16_t delta;
    write8(s,s->es,s->di,(uint8_t)s->ax);
#if ENTITY_SPRITE_ALIGNED_MUTATION == 2
    delta=1;
#else
    delta=(s->flags&DF)?-1:1;
#endif
    s->di=(uint16_t)(s->di+delta);
}

static void first_pass_row(EntityAlignedSpriteState *s) {
    s->cx=read16(s,s->ds,s->bx);                     /* MOV CX,[BX] */
    inc_bx(s);inc_bx(s);                              /* INC BX x2 */
    set_al(s,0x08u);set_ah(s,(uint8_t)s->cx);         /* AL=8; AH=CL */
    mirror_out(s,SEG143E_VgaBitMaskMirror);
    cli(s);
    set_al(s,latch_read(s));                          /* VGA latch read */
    lodsw(s);stosb(s);                                /* first source byte */
    sti(s);

    {
        uint8_t old_ch=(uint8_t)(s->cx>>8);
        uint8_t old_ah=(uint8_t)(s->ax>>8);
        set_ch(s,old_ah);set_ah(s,old_ch);            /* XCHG CH,AH */
    }
    set_al(s,0x08u);
    mirror_out(s,SEG143E_VgaBitMaskMirror);
    cli(s);
    set_al(s,latch_read(s));                          /* VGA latch read */
    set_al(s,(uint8_t)(s->cx>>8));                    /* MOV AL,CH */
    stosb(s);                                         /* second source byte */
    sti(s);

    set_ah(s,read8(s,s->ds,s->bx));                   /* MOV AH,[BX] */
    inc_bx(s);
    set_al(s,0x08u);
    mirror_out(s,SEG143E_VgaBitMaskMirror);
    cli(s);
    set_al(s,latch_read(s));                          /* VGA latch read */
    lodsb(s);stosb(s);                                /* third source byte */
    sti(s);
    add_di_row(s);
}

#if ENTITY_SPRITE_ALIGNED_MUTATION != 10
static void second_pass_row(EntityAlignedSpriteState *s) {
    cli(s);
    set_al(s,latch_read(s));                          /* VGA latch read */
    lodsw(s);stosb(s);
    set_al(s,latch_read(s));                          /* VGA latch read */
    set_al(s,(uint8_t)(s->ax>>8));                    /* MOV AL,AH */
    stosb(s);
    set_al(s,latch_read(s));                          /* VGA latch read */
    lodsb(s);stosb(s);
    sti(s);
    add_di_row(s);
}
#endif

static void initialize(EntityAlignedSpriteState *s,uint8_t *memory,
    const LmnEntityAlignedSpriteCall *call,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->entry_ds=call->data_segment;
    s->continuation=CS_EntityAlignedSpriteReturn;
    s->status=LMN_ENTITY_ALIGNED_SPRITE_READY;
}

static LmnEntityAlignedSpriteResult result_of(
    const EntityAlignedSpriteState *s) {
    LmnEntityAlignedSpriteResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

LmnEntityAlignedSpriteResult lmn_draw_entity_aligned_sprite_core(
    uint8_t *memory,const LmnEntityAlignedSpriteCall *call,
    const LmnRasterBus *bus) {
    EntityAlignedSpriteState s;
    unsigned row;
    initialize(&s,memory,call,bus);

    push16(&s,s.ds);                                   /* PUSH DS @6170 */
    s.dx=0x03c4u;
    s.ax=0x0f02u;
    mirror_out(&s,SEG143E_VgaMapMaskMirror);
    s.dx=0x03ceu;
    s.ax=0u;                                           /* XOR AX,AX */
    s.flags=logic16_flags(s.flags,s.ax);
    mirror_out(&s,SEG143E_VgaSetResetMirror);
    s.ax=0x0e01u;
    mirror_out(&s,SEG143E_VgaEnableSetResetMirror);
    s.ax=0x0005u;
    mirror_out(&s,SEG143E_VgaGraphicsModeMirror);
    s.ax=0x0003u;
    mirror_out(&s,SEG143E_VgaDataRotateMirror);
#if ENTITY_SPRITE_ALIGNED_MUTATION == 4
    s.ds=s.entry_ds;
#else
    s.ds=s.cx;                                         /* MOV DS,CX */
#endif
    s.cx=0xa000u;
    s.es=s.cx;                                         /* ES=A000 */
    s.bp=s.di;                                         /* BP=DI */

    for(row=0u;row<10u;++row)first_pass_row(&s);

    s.di=s.bp;                                         /* MOV DI,BP */
    s.ax=0x0001u;
    mirror_out(&s,SEG143E_VgaEnableSetResetMirror);
    s.ax=0x1003u;
    mirror_out(&s,SEG143E_VgaDataRotateMirror);
    s.ax=0xff08u;
    mirror_out(&s,SEG143E_VgaBitMaskMirror);
    s.dx=(uint16_t)((s.dx&0xff00u)|0x00c4u);           /* MOV DL,C4 */
    s.ax=0x0202u;
    mirror_out(&s,SEG143E_VgaMapMaskMirror);
    cli(&s);                                           /* CLI @6405 */

#if ENTITY_SPRITE_ALIGNED_MUTATION != 10
    {
#if ENTITY_SPRITE_ALIGNED_MUTATION == 8
        const unsigned rows=9u;
#else
        const unsigned rows=10u;
#endif
        for(row=0u;row<rows;++row)second_pass_row(&s);
    }
#endif

    {
        uint16_t live_ds=pop16(&s);                    /* POP DS @64D7 */
#if ENTITY_SPRITE_ALIGNED_MUTATION == 5
        (void)live_ds;
        s.ds=s.entry_ds;
#else
        s.ds=live_ds;
#endif
    }
    return result_of(&s);                              /* before RET @64D8 */
}

static void apply_result(LmnRegs *r,const LmnEntityAlignedSpriteResult *out) {
    r->ax=out->value;r->bx=out->map_cursor;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->record_cursor;
    r->di=out->object_cursor;r->bp=out->candidate_y;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;
    r->ip=out->continuation;
}

static uint16_t read_stack_return(uint8_t *memory,uint16_t ss,uint16_t sp,
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

uint16_t lmn_draw_entity_aligned_sprite_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus) {
    LmnEntityAlignedSpriteCall call;
    LmnEntityAlignedSpriteResult out;
    call.value=registers->ax;call.map_cursor=registers->bx;
    call.count=registers->cx;call.auxiliary_value=registers->dx;
    call.record_cursor=registers->si;call.object_cursor=registers->di;
    call.candidate_y=registers->bp;call.code_segment=registers->cs;
    call.data_segment=registers->ds;call.extra_segment=registers->es;
    call.stack_segment=registers->ss;call.stack_offset=registers->sp;
    call.flags=registers->flags;
    out=lmn_draw_entity_aligned_sprite_core(memory,&call,bus);
    apply_result(registers,&out);
    if(out.status==LMN_ENTITY_ALIGNED_SPRITE_READY) {
        registers->ip=read_stack_return(memory,registers->ss,registers->sp,
                                        registers->flags,bus);
        registers->sp=(uint16_t)(registers->sp+2u);
    }
    return out.status;
}

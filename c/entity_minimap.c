#include "entity_minimap.h"

#include "lemmings_sym.h"

#ifndef ENTITY_MINIMAP_MUTATION
#define ENTITY_MINIMAP_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct EntityMinimapState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
} EntityMinimapState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(EntityMinimapState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(EntityMinimapState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(EntityMinimapState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(EntityMinimapState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(EntityMinimapState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(EntityMinimapState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
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

static uint16_t sub16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint16_t result=(uint16_t)(left-right),out=szp16(result);
    if(left<right)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&0x8000u)!=0u)out|=OF;
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

static uint16_t shift_right_one_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before>>1);
    uint16_t out=szp16(result);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    return (uint16_t)((flags&~(CF|PF|ZF|SF|OF))|out);
}

static uint16_t logic16_flags(uint16_t flags,uint16_t value) {
    return (uint16_t)((flags&~LOGIC)|szp16(value));
}

static void shift_ax_right(EntityMinimapState *s) {
    uint16_t before=s->ax;
    s->ax=(uint16_t)(before>>1);
    s->flags=shift_right_one_flags(s->flags,before);
}

static void add_si(EntityMinimapState *s,uint16_t amount) {
    uint16_t before=s->si;
    s->si=(uint16_t)(before+amount);
    s->flags=add16_flags(s->flags,before,amount);
}

#if ENTITY_MINIMAP_MUTATION != 4
static void add_si_memory(EntityMinimapState *s,uint16_t segment,
                         uint16_t offset) {
    uint16_t value=read16(s,segment,offset);
    add_si(s,value);
}
#endif

static void push16(EntityMinimapState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop16(EntityMinimapState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void mirror_and_out(EntityMinimapState *s,uint16_t mirror) {
    write16(s,s->ss,mirror,s->ax);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
}

static void initialize(EntityMinimapState *s,uint8_t *memory,
    const LmnEntityMinimapCall *call,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=CS_EntityMinimapPixelReturn;
    s->status=LMN_ENTITY_MINIMAP_READY;
}

static LmnEntityMinimapResult result_of(const EntityMinimapState *s) {
    LmnEntityMinimapResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

LmnEntityMinimapResult lmn_draw_entity_minimap_pixel_core(uint8_t *memory,
    const LmnEntityMinimapCall *call,const LmnRasterBus *bus) {
    EntityMinimapState s;
    uint16_t product_high;
#if ENTITY_MINIMAP_MUTATION == 7
    uint16_t cached_mask_source;
#endif
    initialize(&s,memory,call,bus);

    s.ax=read16(&s,s.ds,(uint16_t)(s.di+2u));         /* MOV AX,[DI+2] */
    s.flags=sub16_flags(s.flags,s.ax,0x00b0u);         /* CMP AX,B0 */
#if ENTITY_MINIMAP_MUTATION == 6
    if(s.ax>=0x00b0u) {                                /* unsigned-JL mutant */
#else
    if(((s.flags&SF)!=0u)==((s.flags&OF)!=0u)) {       /* JGE: no signed JL */
#endif
 #if ENTITY_MINIMAP_MUTATION == 2
        s.flags=(uint16_t)(s.flags|IF);                /* bad early STI */
 #endif
        return result_of(&s);                          /* JMP 706E */
    }

    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(before-0x0020u);
        s.flags=sub16_flags(s.flags,before,0x0020u);
    }
    if(s.flags&SF) {                                   /* JS 706E */
 #if ENTITY_MINIMAP_MUTATION == 2
        s.flags=(uint16_t)(s.flags|IF);                /* bad early STI */
 #endif
        return result_of(&s);
    }
    shift_ax_right(&s);                                /* SHR AX,1 x3 */
    shift_ax_right(&s);
    shift_ax_right(&s);
    s.dx=0x002cu;
    {
        uint32_t product=(uint32_t)s.ax*(uint32_t)s.dx;
        s.ax=(uint16_t)product;
        product_high=(uint16_t)(product>>16);
        s.dx=product_high;
        /* MUL defines only CF/OF; leave other arithmetic bits opaque. */
        s.flags=(uint16_t)((s.flags&~(CF|OF))|
                           (product_high?(CF|OF):0u));
    }
    s.si=s.ax;                                         /* MOV SI,AX */
    s.ax=read16(&s,s.ds,s.di);                         /* MOV AX,[DI] */
    shift_ax_right(&s);                                /* SHR AX,1 x4 */
    shift_ax_right(&s);
    shift_ax_right(&s);
#if ENTITY_MINIMAP_MUTATION != 1
    shift_ax_right(&s);
#endif
#if ENTITY_MINIMAP_MUTATION == 7
    cached_mask_source=s.ax;
#endif
    push16(&s,s.ax);                                   /* PUSH AX */
    shift_ax_right(&s);                                /* SHR AX,1 x3 */
    shift_ax_right(&s);
    shift_ax_right(&s);
    add_si(&s,s.ax);                                   /* ADD SI,AX */
#if ENTITY_MINIMAP_MUTATION == 4
    (void)read16(&s,s.ds,SEG09A9_DrawingOrigin);       /* dropped add only */
#else
    add_si_memory(&s,s.ds,SEG09A9_DrawingOrigin);     /* ADD SI,[origin] */
#endif
    add_si(&s,0x2172u);
    add_si(&s,0x0002u);
    add_si(&s,0x002cu);

    s.dx=0x03c4u;s.ax=0x0f02u;
#if ENTITY_MINIMAP_MUTATION == 5
    if(s.bus&&s.bus->out_word)
        s.bus->out_word(s.bus->context,s.dx,s.ax,s.flags);
#else
    mirror_and_out(&s,0x0008u);                        /* SEQ map mask */
#endif
    s.dx=0x03ceu;s.ax=0x0200u;
    mirror_and_out(&s,0x000au);                        /* GC set/reset, index 0 */
    s.ax=0x0f01u;
    mirror_and_out(&s,0x000cu);                        /* GC enable set/reset, index 1 */
    s.ax=0x0005u;
    mirror_and_out(&s,0x0000u);                        /* GC mode */
    s.ax=0x0003u;
    mirror_and_out(&s,0x0002u);                        /* GC data rotate */
    s.ax=0xa000u;
    s.es=s.ax;
    s.ax=pop16(&s);                                    /* live POP AX */
#if ENTITY_MINIMAP_MUTATION == 7
    s.ax=cached_mask_source;
#endif
    s.bx=SEG09A9_PixelBitMasks;                        /* LEA BX,table */
    s.ax=(uint16_t)(s.ax&0x0007u);                     /* AND AX,7 */
    s.flags=logic16_flags(s.flags,s.ax);
    {
        uint16_t before=s.bx;
        s.bx=(uint16_t)(before+s.ax);                  /* ADD BX,AX */
        s.flags=add16_flags(s.flags,before,s.ax);
    }
#if ENTITY_MINIMAP_MUTATION == 8
    s.ax=(uint16_t)((s.ax&0x00ffu)|
        ((uint16_t)(0x80u>>(s.ax&7u))<<8));
#else
    s.ax=(uint16_t)((s.ax&0x00ffu)|
        ((uint16_t)read8(&s,s.ds,s.bx)<<8));           /* MOV AH,[BX] */
#endif
    s.ax=(uint16_t)((s.ax&0xff00u)|0x0008u);           /* MOV AL,8 */
    mirror_and_out(&s,0x000eu);                        /* GC bit mask */
#if ENTITY_MINIMAP_MUTATION != 3
    s.flags=(uint16_t)(s.flags&~IF);                   /* CLI */
#endif
    {
        uint8_t previous=read8(&s,s.es,s.si);          /* MOV AL,[ES:SI] */
        s.ax=(uint16_t)((s.ax&0xff00u)|previous);
        write8(&s,s.es,s.si,(uint8_t)(s.ax>>8));       /* MOV [ES:SI],AH */
    }
    s.flags=(uint16_t)(s.flags|IF);                    /* STI */
    return result_of(&s);
}

static void apply_result(LmnRegs *r,const LmnEntityMinimapResult *out) {
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
        high=bus->read_byte(bus->context,memory,(address+1u)&MEMORY_MASK,
                            flags);
    } else {
        low=memory[address];high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

uint16_t lmn_draw_entity_minimap_pixel_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    LmnEntityMinimapCall call;
    LmnEntityMinimapResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_draw_entity_minimap_pixel_core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_ENTITY_MINIMAP_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

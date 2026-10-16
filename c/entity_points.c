#include "entity_points.h"

#include "lemmings_sym.h"

#ifndef ENTITY_POINTS_MUTATION
#define ENTITY_POINTS_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct EntityPointsState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
#if ENTITY_POINTS_MUTATION == 5
    uint8_t cached_color;
    unsigned have_cached_color;
#endif
} EntityPointsState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(EntityPointsState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(EntityPointsState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(EntityPointsState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(EntityPointsState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

/* Word operations advance through the 20-bit physical address space. */
static uint16_t read16(EntityPointsState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(EntityPointsState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0u;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&(bits==8u?0x0080u:0x8000u))out|=SF;
    return out;
}

static uint16_t sub_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t sign=bits==8u?0x80u:0x8000u;
    uint16_t result=(uint16_t)((left-right)&mask),out=szp(result,bits);
    if(left<right)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t sign=bits==8u?0x80u:0x8000u;
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)(wide&mask),out=szp(result,bits);
    if(wide>mask)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return (uint16_t)((flags&~LOGIC)|szp(value,bits));
}

static uint16_t inc_flags(uint16_t flags,uint16_t before) {
    uint16_t carry=(uint16_t)(flags&CF);
    flags=add_flags(flags,before,1u,16u);
    return (uint16_t)((flags&~CF)|carry);
}

static uint16_t dec_flags(uint16_t flags,uint16_t before) {
    uint16_t carry=(uint16_t)(flags&CF);
    flags=sub_flags(flags,before,1u,16u);
    return (uint16_t)((flags&~CF)|carry);
}

static uint16_t shr_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before>>1),out=szp(result,16u);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    return (uint16_t)((flags&~(CF|PF|ZF|SF|OF))|out);
}

static uint16_t shl_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before<<1),out=szp(result,16u);
    if(before&0x8000u)out|=CF;
    if((before^result)&0x8000u)out|=OF;
    return (uint16_t)((flags&~(CF|PF|ZF|SF|OF))|out);
}

static uint16_t mul8_flags(uint16_t flags,uint16_t product) {
    return (uint16_t)((flags&~(CF|OF))|
        ((product&0xff00u)?(CF|OF):0u));
}

static uint16_t mul16_flags(uint16_t flags,uint32_t product) {
    return (uint16_t)((flags&~(CF|OF))|
        ((product>>16)?(CF|OF):0u));
}

static void set_al(EntityPointsState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(EntityPointsState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static uint8_t al(const EntityPointsState *s) {
    return (uint8_t)s->ax;
}

static uint8_t ah(const EntityPointsState *s) {
    return (uint8_t)(s->ax>>8);
}

static void push16(EntityPointsState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop16(EntityPointsState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void mirror_and_out(EntityPointsState *s,uint16_t mirror) {
    write16(s,s->ss,mirror,s->ax);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
}

static void initialize(EntityPointsState *s,uint8_t *memory,
    const LmnEntityPointsCall *call,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=CS_EntityPointCloudReturn;
    s->status=LMN_ENTITY_POINTS_READY;
#if ENTITY_POINTS_MUTATION == 5
    s->cached_color=0u;s->have_cached_color=0u;
#endif
}

static LmnEntityPointsResult result_of(const EntityPointsState *s) {
    LmnEntityPointsResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void setup_vga(EntityPointsState *s) {
    s->dx=0x03c4u;s->ax=0x0f02u;
    mirror_and_out(s,SEG143E_VgaMapMaskMirror);        /* @06E92..06E9C */
    s->dx=0x03ceu;s->ax=0x0f01u;
    mirror_and_out(s,SEG143E_VgaEnableSetResetMirror); /* @06E9D..06EA7 */
    s->ax=0x0005u;
    mirror_and_out(s,SEG143E_VgaGraphicsModeMirror);   /* @06EA8..06EAF */
    s->ax=0x0003u;
    mirror_and_out(s,SEG143E_VgaDataRotateMirror);     /* @06EB0..06EB7 */
    s->ax=0xa000u;s->es=s->ax;                         /* @06EB8..06EBB */
}

static void draw_point_pixel(EntityPointsState *s) {
    uint32_t product;
    uint16_t value;
#if ENTITY_POINTS_MUTATION == 4
    uint16_t cached_si=s->si,cached_bp=s->bp,cached_dx=s->dx;
#endif

    /* Inner save frame; the dirty-map store can alias every saved word. */
    push16(s,s->dx);                                   /* PUSH DX @06EFE */
    push16(s,s->bp);                                   /* PUSH BP @06EFF */
    push16(s,s->si);                                   /* PUSH SI @06F00 */
    s->si=read16(s,s->ds,SEG09A9_DrawingDirtyCellMapOffset);
    s->si=(uint16_t)(s->si+1u);                        /* INC SI @06F05 */
    s->flags=inc_flags(s->flags,(uint16_t)(s->si-1u));

    value=s->bp;s->bp=(uint16_t)(s->bp-0x0010u);       /* SUB BP,10 @06F06 */
    s->flags=sub_flags(s->flags,value,0x0010u,16u);
    if(s->flags&SF) {
        s->bp=0;                                       /* XOR BP,BP @06F0B */
        s->flags=logic_flags(s->flags,0u,16u);
    }
    value=s->bp;s->bp=(uint16_t)(s->bp>>1);            /* SHR BP,1 @06F0D */
    s->flags=shr_flags(s->flags,value);
    value=s->bp;s->bp=(uint16_t)(s->bp>>1);            /* @06F0F */
    s->flags=shr_flags(s->flags,value);
    value=s->bp;s->bp=(uint16_t)(s->bp>>1);            /* @06F11 */
    s->flags=shr_flags(s->flags,value);
    value=s->si;s->si=(uint16_t)(s->si+s->bp);         /* ADD SI,BP @06F13 */
    s->flags=add_flags(s->flags,value,s->bp,16u);
    value=s->dx;s->dx=(uint16_t)(s->dx&0xfff8u);       /* AND DX,-8 @06F15 */
    s->flags=logic_flags(s->flags,s->dx,16u);
    value=s->si;s->si=(uint16_t)(s->si+s->dx);         /* ADD SI,DX @06F18 */
    s->flags=add_flags(s->flags,value,s->dx,16u);
    value=s->dx;s->dx=(uint16_t)(s->dx<<1);            /* SHL DX,1 @06F1A */
    s->flags=shl_flags(s->flags,value);
    value=s->dx;s->dx=(uint16_t)(s->dx<<1);            /* @06F1C */
    s->flags=shl_flags(s->flags,value);
    value=s->si;s->si=(uint16_t)(s->si+s->dx);         /* ADD SI,DX @06F1E */
    s->flags=add_flags(s->flags,value,s->dx,16u);
    write8(s,s->ss,s->si,0x01u);                       /* MOV SS:[SI],1 */

    s->si=pop16(s);                                    /* POP SI @06F24 */
    s->bp=pop16(s);                                    /* POP BP @06F25 */
    s->dx=pop16(s);                                    /* POP DX @06F26 */
#if ENTITY_POINTS_MUTATION == 4
    s->si=cached_si;s->bp=cached_bp;s->dx=cached_dx;
#endif

    s->ax=0x002cu;                                     /* MOV AX,2C @06F27 */
    product=(uint32_t)s->ax*(uint32_t)s->dx;           /* MUL DX @06F2A */
    s->ax=(uint16_t)product;
    s->dx=(uint16_t)(product>>16);
    s->flags=mul16_flags(s->flags,product);
    s->di=s->ax;                                       /* MOV DI,AX @06F2C */
    s->ax=s->bp;                                       /* MOV AX,BP @06F2E */
    value=s->bp;s->bp=(uint16_t)(s->bp>>1);            /* SHR BP,1 @06F30 */
    s->flags=shr_flags(s->flags,value);
    value=s->bp;s->bp=(uint16_t)(s->bp>>1);            /* @06F32 */
    s->flags=shr_flags(s->flags,value);
    value=s->bp;s->bp=(uint16_t)(s->bp>>1);            /* @06F34 */
    s->flags=shr_flags(s->flags,value);
    value=s->di;s->di=(uint16_t)(s->di+s->bp);         /* ADD DI,BP @06F36 */
    s->flags=add_flags(s->flags,value,s->bp,16u);
    value=read16(s,s->ds,SEG09A9_DrawingOrigin);       /* live DS read */
    s->di=(uint16_t)(s->di+value);                     /* ADD DI,[origin] */
    s->flags=add_flags(s->flags,(uint16_t)(s->di-value),value,16u);
    value=read16(s,s->ds,SEG09A9_DrawingPageByteOffset);
#if ENTITY_POINTS_MUTATION == 10
    (void)value;                                       /* retain read, drop ADD */
#else
    s->di=(uint16_t)(s->di+value);                     /* ADD DI,[page] */
    s->flags=add_flags(s->flags,(uint16_t)(s->di-value),value,16u);
#endif
    s->ax=(uint16_t)(s->ax&0x0007u);                   /* AND AX,7 @06F40 */
    s->flags=logic_flags(s->flags,s->ax,16u);
    s->bx=SEG09A9_PixelBitMasks;                       /* LEA BX,table */
    value=s->bx;s->bx=(uint16_t)(s->bx+s->ax);         /* ADD BX,AX @06F47 */
    s->flags=add_flags(s->flags,value,s->ax,16u);
    value=read8(s,s->ds,s->bx);                       /* live mask byte */
#if ENTITY_POINTS_MUTATION == 6
    (void)value;                                      /* ignore read value */
    set_ah(s,0x80u);
#else
    set_ah(s,(uint8_t)value);
#endif
    set_al(s,0x08u);                                   /* MOV AL,8 @06F4B */
    write16(s,s->ss,SEG143E_VgaBitMaskMirror,s->ax);   /* MOV SS:[E],AX */
    s->dx=0x03ceu;                                     /* MOV DX,3CE @06F51 */
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);

    push16(s,s->ax);                                   /* PUSH AX @06F55 */
    s->bx=s->cx;                                       /* MOV BX,CX @06F56 */
    s->bx=(uint16_t)(s->bx&0x000fu);                   /* AND BX,0F @06F58 */
    s->flags=logic_flags(s->flags,s->bx,16u);
    value=s->bx;
    s->bx=(uint16_t)(s->bx+SEG09A9_EntityPointColors); /* ADD BX,2778 */
    s->flags=add_flags(s->flags,value,SEG09A9_EntityPointColors,16u);
    value=read8(s,s->ds,s->bx);                       /* live DS color */
#if ENTITY_POINTS_MUTATION == 5
    if(!s->have_cached_color) {
        s->cached_color=(uint8_t)value;
        s->have_cached_color=1u;
    }
    set_ah(s,s->cached_color);                        /* stale cached color */
#else
    set_ah(s,(uint8_t)value);
#endif
    set_al(s,0x00u);                                   /* XOR AL,AL @06F61 */
    s->flags=logic_flags(s->flags,0u,8u);
    write16(s,s->ss,SEG143E_VgaSetResetMirror,s->ax);  /* MOV SS:[A],AX */
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
    s->ax=pop16(s);                                    /* live POP AX @06F68 */

#if ENTITY_POINTS_MUTATION != 7
    s->flags=(uint16_t)(s->flags&~IF);                 /* CLI @06F69 */
#endif
    value=read8(s,s->es,s->di);                        /* MOV AL,[ES:DI] */
    set_al(s,(uint8_t)value);
    write8(s,s->es,s->di,ah(s));                       /* MOV [ES:DI],AH */
    s->flags=(uint16_t)(s->flags|IF);                  /* STI @06F70 */
}

LmnEntityPointsResult lmn_draw_entity_point_cloud_core(uint8_t *memory,
    const LmnEntityPointsCall *call,const LmnRasterBus *bus) {
    EntityPointsState s;
    uint8_t source_index;
    uint16_t point_word,original_bp,original_dx;
    initialize(&s,memory,call,bus);

    source_index=read8(&s,s.ds,(uint16_t)(s.si+0x0028u)); /* MOV AL,[SI+28] */
    set_al(&s,source_index);
    s.flags=sub_flags(s.flags,al(&s),1u,8u);          /* SUB AL,1 @06E86 */
    set_al(&s,(uint8_t)(al(&s)-1u));
    s.bx=(uint16_t)((s.bx&0xff00u)|0x00a0u);           /* MOV BL,A0 */
    point_word=(uint16_t)((uint16_t)al(&s)*0x00a0u);   /* byte MUL @06E8A */
    s.ax=point_word;
    s.flags=mul8_flags(s.flags,point_word);
    s.bx=SEG09A9_EntityPointFrames;                    /* LEA BX,2788 */
    point_word=s.bx;s.bx=(uint16_t)(s.bx+s.ax);        /* ADD BX,AX @06E90 */
    s.flags=add_flags(s.flags,point_word,s.ax,16u);

    setup_vga(&s);
    s.bp=read16(&s,s.ds,s.si);                         /* MOV BP,[SI] @06EBD */
    point_word=read16(&s,s.ds,SEG09A9_LevelViewOriginPixels);
    original_bp=s.bp;s.bp=(uint16_t)(s.bp-point_word);
    s.flags=sub_flags(s.flags,original_bp,point_word,16u);
    original_bp=s.bp;s.bp=(uint16_t)(s.bp+0x0010u);    /* ADD BP,10 @06EC3 */
    s.flags=add_flags(s.flags,original_bp,0x0010u,16u);
    s.dx=read16(&s,s.ds,(uint16_t)(s.si+2u));          /* MOV DX,[SI+2] */
    original_dx=s.dx;s.dx=(uint16_t)(s.dx-0x0010u);    /* SUB DX,10 @06EC9 */
    s.flags=sub_flags(s.flags,original_dx,0x0010u,16u);
    source_index=read8(&s,s.ds,SEG09A9_EntityPointCount); /* MOV CL,[4D] */
    s.cx=(uint16_t)((s.cx&0xff00u)|source_index);
    s.cx=(uint16_t)(s.cx&0x00ffu);                     /* XOR CH,CH @06ED0 */
    s.flags=logic_flags(s.flags,0u,8u);
#if ENTITY_POINTS_MUTATION == 8
    if(s.cx==0u)return result_of(&s);                  /* erroneous early exit */
#endif

    for(;;) {
        uint8_t x_delta,y_delta;
        uint16_t table_ax;
        int stop_after_point=0;
        int sentinel;

        s.ax=read16(&s,s.ds,s.bx);                     /* MOV AX,[BX] @06ED2 */
        point_word=s.bx;s.bx=(uint16_t)(s.bx+2u);      /* ADD BX,2 @06ED4 */
        s.flags=add_flags(s.flags,point_word,2u,16u);
        s.flags=sub_flags(s.flags,al(&s),0x80u,8u);    /* CMP AL,80 @06ED7 */
        sentinel=al(&s)==0x80u;
        if(sentinel) {
#if ENTITY_POINTS_MUTATION == 9
            stop_after_point=1;
#endif
            goto point_loop_tail;                      /* skip this point */
        }

        push16(&s,s.bp);                                /* PUSH BP @06EDE */
        push16(&s,s.dx);                                /* PUSH DX @06EDF */
        push16(&s,s.bx);                                /* PUSH BX @06EE0 */
        push16(&s,s.ax);                                /* PUSH AX @06EE1 */
#if ENTITY_POINTS_MUTATION == 1
        set_ah(&s,0u);                                 /* unsigned low delta */
#elif ENTITY_POINTS_MUTATION == 3
        set_al(&s,ah(&s));
        set_ah(&s,(al(&s)&0x80u)?0xffu:0x00u);         /* swapped X delta */
#else
        set_ah(&s,(al(&s)&0x80u)?0xffu:0x00u);         /* CBW @06EE2 */
#endif
        table_ax=s.ax;
        original_bp=s.bp;s.bp=(uint16_t)(s.bp+s.ax);   /* ADD BP,AX @06EE3 */
        s.flags=add_flags(s.flags,original_bp,table_ax,16u);
        s.ax=pop16(&s);                                 /* POP AX @06EE5 */
        if(s.flags&SF)goto point_cleanup;               /* JNS @06EE6 */

#if ENTITY_POINTS_MUTATION == 3
        x_delta=ah(&s);y_delta=al(&s);
#else
        x_delta=al(&s);y_delta=ah(&s);
#endif
        set_al(&s,y_delta);set_ah(&s,x_delta);          /* XCHG AL,AH */
#if ENTITY_POINTS_MUTATION == 2
        set_ah(&s,0u);                                 /* unsigned Y delta */
#else
        set_ah(&s,(al(&s)&0x80u)?0xffu:0x00u);         /* CBW @06EED */
#endif
        original_dx=s.dx;s.dx=(uint16_t)(s.dx+s.ax);   /* ADD DX,AX @06EEE */
        s.flags=add_flags(s.flags,original_dx,s.ax,16u);
        if(s.flags&SF)goto point_cleanup;               /* JS @06EF0 */
        s.flags=sub_flags(s.flags,s.bp,0x0150u,16u);   /* CMP BP,150 @06EF2 */
        if(((s.flags&SF)!=0u)==((s.flags&OF)!=0u))
            goto point_cleanup;                         /* JNL @06EF6 */
        s.flags=sub_flags(s.flags,s.dx,0x00a0u,16u);   /* CMP DX,A0 @06EF8 */
        if(((s.flags&SF)!=0u)==((s.flags&OF)!=0u))
            goto point_cleanup;                         /* JNL @06EFC */

        draw_point_pixel(&s);                           /* @06EFE..06F70 */

point_cleanup:
        s.bx=pop16(&s);                                 /* POP BX @06F71 */
        s.dx=pop16(&s);                                 /* POP DX @06F72 */
        s.bp=pop16(&s);                                 /* POP BP @06F73 */

point_loop_tail:
        original_bp=s.cx;s.cx=(uint16_t)(s.cx-1u);     /* DEC CX @06F74 */
        s.flags=dec_flags(s.flags,original_bp);
        if(s.cx==0u||stop_after_point)break;            /* JZ / bad BREAK */
    }

    return result_of(&s);                               /* before RET @06F7A */
}

static void apply_result(LmnRegs *r,const LmnEntityPointsResult *out) {
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

uint16_t lmn_draw_entity_point_cloud_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    LmnEntityPointsCall call;
    LmnEntityPointsResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_draw_entity_point_cloud_core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_ENTITY_POINTS_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

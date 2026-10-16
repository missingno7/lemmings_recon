#include "entity_sprite_dispatch.h"

#include "entity_sprite_aligned.h"
#include "entity_sprite_shifted.h"
#include "entity_sprite_wide.h"
#include "entity_strip.h"
#include "lemmings_sym.h"

#ifndef ENTITY_SPRITE_DISPATCH_MUTATION
#define ENTITY_SPRITE_DISPATCH_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF
};

typedef struct DispatchState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp,sp;
    uint16_t cs,ds,es,ss,ip,flags;
    uint16_t continuation,status;
    uint16_t entry_di,cached_callback;
} DispatchState;

typedef uint16_t (*SpriteAdapter)(uint8_t *,LmnRegs *,const LmnRasterBus *);

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+(uint32_t)offset)&MEMORY_MASK);
}

static uint8_t read_physical(DispatchState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(DispatchState *s,uint32_t address,uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(DispatchState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static uint16_t read16(DispatchState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(DispatchState *s,uint16_t segment,uint16_t offset,
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
    if(value&(1u<<(bits-1u)))out|=SF;
    return out;
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)wide,out=szp(value,16u);
    if(wide>0xffffu)out|=CF;
    if((left^right^value)&0x10u)out|=AF;
    if((~(left^right)&(left^value)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t sub16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint16_t value=(uint16_t)(left-right),out=szp(value,16u);
    if(left<right)out|=CF;
    if((left^right^value)&0x10u)out|=AF;
    if(((left^right)&(left^value)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t add8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    unsigned wide=(unsigned)left+(unsigned)right;
    uint8_t value=(uint8_t)wide;
    uint16_t out=szp(value,8u);
    if(wide>0xffu)out|=CF;
    if((left^right^value)&0x10u)out|=AF;
    if((~(left^right)&(left^value)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t sub8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t value=(uint8_t)(left-right);
    uint16_t out=szp(value,8u);
    if(left<right)out|=CF;
    if((left^right^value)&0x10u)out|=AF;
    if(((left^right)&(left^value)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t shr16_flags(uint16_t flags,uint16_t before,uint16_t *after) {
    uint16_t value=(uint16_t)(before>>1),out=szp(value,16u);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    *after=value;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t rcr16_flags(uint16_t flags,uint16_t before,uint16_t *after) {
    unsigned old_carry=(flags&CF)!=0u;
    uint16_t value=(uint16_t)((before>>1)|(old_carry?0x8000u:0u));
    uint16_t out=(uint16_t)(flags&~(CF|OF));
    if(before&1u)out|=CF;
    if((((value>>15)^(value>>14))&1u)!=0u)out|=OF;
    *after=value;
    return out;
}

static uint16_t shl16_flags(uint16_t flags,uint16_t before,uint16_t *after) {
    uint16_t value=(uint16_t)(before<<1),out=szp(value,16u);
    unsigned carry=(before&0x8000u)!=0u;
    if(carry)out|=CF;
    if(((value>>15)^carry)&1u)out|=OF;
    *after=value;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t shl8_flags(uint16_t flags,uint8_t before,uint8_t *after) {
    uint8_t value=(uint8_t)(before<<1);
    unsigned carry=(before&0x80u)!=0u;
    uint16_t out=szp(value,8u);
    if(carry)out|=CF;
    if((((value>>7)^carry)&1u)!=0u)out|=OF;
    *after=value;
    return (uint16_t)((flags&~ARITH)|out);
}

static void push(DispatchState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(DispatchState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static uint8_t al(const DispatchState *s) { return (uint8_t)s->ax; }
static uint8_t ah(const DispatchState *s) { return (uint8_t)(s->ax>>8); }
static uint8_t dl(const DispatchState *s) { return (uint8_t)s->dx; }

static void set_al(DispatchState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(DispatchState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void set_dl(DispatchState *s,uint8_t value) {
    s->dx=(uint16_t)((s->dx&0xff00u)|value);
}

static void set_dh(DispatchState *s,uint8_t value) {
    s->dx=(uint16_t)((s->dx&0x00ffu)|((uint16_t)value<<8));
}

static void set_result_state(DispatchState *s,const LmnEntitySpriteDispatchCall *call,
                             uint8_t *memory,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->ip=CS_DrawObjectSprite;s->continuation=s->ip;
    s->status=LMN_ENTITY_SPRITE_DISPATCH_READY;
    s->entry_di=s->di;s->cached_callback=0u;
}

static LmnEntitySpriteDispatchResult result_of(const DispatchState *s) {
    LmnEntitySpriteDispatchResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void state_from_regs(DispatchState *s,const LmnRegs *r) {
    s->ax=r->ax;s->bx=r->bx;s->cx=r->cx;s->dx=r->dx;
    s->si=r->si;s->di=r->di;s->bp=r->bp;s->sp=r->sp;
    s->cs=r->cs;s->ds=r->ds;s->es=r->es;s->ss=r->ss;
    s->ip=r->ip;s->flags=r->flags;
}

static void regs_from_state(const DispatchState *s,LmnRegs *r) {
    r->ax=s->ax;r->bx=s->bx;r->cx=s->cx;r->dx=s->dx;
    r->si=s->si;r->di=s->di;r->bp=s->bp;r->sp=s->sp;
    r->cs=s->cs;r->ds=s->ds;r->es=s->es;r->ss=s->ss;
    r->ip=s->ip;r->flags=s->flags;
}

static LmnEntitySpriteDispatchResult stop_at(DispatchState *s,uint16_t ip,
                                              uint16_t status) {
    s->ip=ip;s->continuation=ip;s->status=status;
    return result_of(s);
}

static SpriteAdapter callback_adapter(uint16_t target) {
    switch(target) {
    case CS_DrawEntityAlignedSprite:
        return lmn_draw_entity_aligned_sprite_adapter;
    case CS_DrawEntityShiftedSprite12:
        return lmn_draw_entity_shifted_sprite12_adapter;
    case CS_DrawEntityShiftedSprite13:
        return lmn_draw_entity_shifted_sprite13_adapter;
    case CS_DrawEntityShiftedSprite3Plane10:
        return lmn_draw_entity_sprite_3plane_10_adapter;
    case CS_DrawEntityShiftedSprite3Plane13:
        return lmn_draw_entity_sprite_3plane_13_adapter;
    case CS_DrawEntityShiftedSprite3Plane14:
        return lmn_draw_entity_sprite_3plane_14_adapter;
    case CS_DrawEntityShiftedSprite3Plane16:
        return lmn_draw_entity_sprite_3plane_16_adapter;
    case CS_DrawEntityWideSprite32:
        return lmn_draw_entity_wide_sprite32_adapter;
    case CS_DrawEntityShiftedSprite4Plane14:
        return lmn_draw_entity_sprite_4plane_14_adapter;
    default:
        return (SpriteAdapter)0;
    }
}

static uint16_t dispatch_callback(DispatchState *s,uint16_t target) {
    SpriteAdapter adapter=callback_adapter(target);
    LmnRegs registers;
    uint16_t old_cs=s->cs,status;
    if(!adapter)return 0xffffu;
#if ENTITY_SPRITE_DISPATCH_MUTATION == 6
    if(target==CS_DrawEntityShiftedSprite12)
        adapter=lmn_draw_entity_shifted_sprite13_adapter;
#endif
    regs_from_state(s,&registers);
    registers.ip=target;
    push(s,CS_EntitySpriteRestoreDI);
    registers.sp=s->sp;
    status=adapter(s->memory,&registers,s->bus);
    state_from_regs(s,&registers);
    if(status!=0u||s->cs!=old_cs||s->ip!=CS_EntitySpriteRestoreDI)
        return 1u;
    return 0u;
}

static LmnEntitySpriteDispatchResult call_strip(DispatchState *s) {
    LmnRegs registers;
    uint16_t old_cs=s->cs,status;
    uint16_t expected=CS_EntitySpriteStripResume;
#if ENTITY_SPRITE_DISPATCH_MUTATION == 4
    expected=(uint16_t)(expected-1u);
#endif
    regs_from_state(s,&registers);
    registers.ip=CS_DrawEntityTwoByteStrip;
    push(s,expected);
    registers.sp=s->sp;
    status=lmn_draw_entity_two_byte_strip_adapter(s->memory,&registers,s->bus);
    state_from_regs(s,&registers);
    if(status!=0u||s->cs!=old_cs||s->ip!=CS_EntitySpriteStripResume) {
#if ENTITY_SPRITE_DISPATCH_MUTATION == 8
        s->ip=CS_EntitySpriteStripResume;
        return result_of(s);
#else
        return stop_at(s,s->ip,LMN_ENTITY_SPRITE_DISPATCH_CHILD_RETURN);
#endif
    }
    return result_of(s);
}

LmnEntitySpriteDispatchResult lmn_draw_entity_sprite_core(
    uint8_t *memory,const LmnEntitySpriteDispatchCall *call,
    const LmnRasterBus *bus) {
    DispatchState s;
    uint16_t operand,visible;
    LmnEntitySpriteDispatchResult child;
    set_result_state(&s,call,memory,bus);

    /* PUSH DI; ADD BX,[DI+4], using the current record segment and live DI. */
    push(&s,s.di);
    s.bx=read16(&s,s.ds,s.di);
    operand=read16(&s,s.ds,(uint16_t)(s.di+4u));
    {
        uint16_t before=s.bx;
        s.bx=(uint16_t)(s.bx+operand);
        s.flags=add16_flags(s.flags,before,operand);
    }
    if((s.flags&SF)==0u)goto visibility_sum_ready;
    {
        uint16_t before=s.bx;
        s.bx=(uint16_t)(s.bx+0x0160u);
        s.flags=add16_flags(s.flags,before,0x0160u);
    }
visibility_sum_ready:
    s.dx=s.bx;                                         /* MOV DX,BX */
    {
        unsigned shifts=3u;
#if ENTITY_SPRITE_DISPATCH_MUTATION == 5
        shifts=2u;
#endif
        while(shifts--!=0u) {
            uint16_t before=s.bx;
            s.bx=(uint16_t)(before>>1);
            s.flags=(uint16_t)((s.flags&~ARITH)|szp(s.bx,16u)|
                              ((before&1u)?CF:0u)|((before&0x8000u)?OF:0u));
        }
    }
    s.si=SEG09A9_ViewVisibilityMapBase;                /* MOV SI,EA8 */
    visible=read8(&s,s.ds,(uint16_t)(s.bx+s.si));
    s.flags=sub8_flags(s.flags,(uint8_t)visible,1u);    /* CMP [BX+SI],1 */
#if ENTITY_SPRITE_DISPATCH_MUTATION == 1
    if(s.flags&ZF)goto visibility_miss;
#else
    if((s.flags&ZF)==0u)goto visibility_miss;
#endif

    /* Wrapped horizontal view origin and the live frame selector math. */
    s.ax=read16(&s,s.ds,0u);
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(s.ax-0x10u);
        s.flags=sub16_flags(s.flags,before,0x10u);      /* SUB AX,10 */
    }
    {
        uint16_t before=s.dx;
        s.dx=(uint16_t)(s.dx-s.ax);
        s.flags=sub16_flags(s.flags,before,s.ax);       /* SUB DX,AX */
    }
    if(s.flags&SF) {
        uint16_t before=s.dx;
        s.dx=(uint16_t)(s.dx+0x0160u);
        s.flags=add16_flags(s.flags,before,0x0160u);   /* ADD DX,160 */
    }
    s.bx=s.dx;
    s.bx=(uint16_t)(s.bx&7u);
    s.flags=logic_flags(s.flags,s.bx,16u);             /* AND BX,7 */
    push(&s,s.bx);

    set_al(&s,read8(&s,s.ds,(uint16_t)(s.di+0x28u)));
    operand=read8(&s,s.ds,(uint16_t)(s.di+0x27u));
    s.flags=sub8_flags(s.flags,(uint8_t)operand,1u);   /* CMP [DI+27],1 */
    if((s.flags&ZF)==0u) {
        uint8_t addend=read8(&s,s.ds,(uint16_t)(s.di+0x29u));
        uint8_t before=(uint8_t)s.ax;
        set_al(&s,(uint8_t)(before+addend));
        s.flags=add8_flags(s.flags,before,addend);     /* ADD AL,[DI+29] */
    }
    set_ah(&s,0u);
    s.flags=logic_flags(s.flags,0u,8u);                /* XOR AH,AH */
    operand=read8(&s,s.ds,(uint16_t)(s.di+0x2au));
    s.flags=sub8_flags(s.flags,(uint8_t)operand,0xffu);/* CMP [DI+2A],FF */
    if((s.flags&ZF)==0u) {
        unsigned i;
        for(i=0u;i<3u;++i) {
            uint16_t before=s.ax;
            s.flags=shl16_flags(s.flags,before,&s.ax);
        }
        {
            uint16_t before=s.ax;
            s.ax=(uint16_t)(s.ax+s.bx);
            s.flags=add16_flags(s.flags,before,s.bx);  /* ADD AX,BX */
        }
    }

    /* MUL stride, then the four-bit DX:AX to BP reduction. */
    push(&s,s.dx);
    s.cx=read16(&s,s.ds,(uint16_t)(s.di+0x10u));
    {
        uint32_t product=(uint32_t)s.ax*(uint32_t)s.cx;
        s.ax=(uint16_t)product;s.dx=(uint16_t)(product>>16);
        s.flags=(uint16_t)((s.flags&~ARITH)|((s.dx!=0u)?(CF|OF):0u));
    }
    s.bp=s.ax;
    {
        unsigned i;
        for(i=0u;i<4u;++i) {
            s.flags=shr16_flags(s.flags,s.dx,&s.dx);
            s.flags=rcr16_flags(s.flags,s.bp,&s.bp);
        }
    }
    operand=read16(&s,s.ds,(uint16_t)(s.di+0x0cu));
    {
        uint16_t before=s.bp;
        s.bp=(uint16_t)(s.bp+operand);
        s.flags=add16_flags(s.flags,before,operand);   /* ADD BP,[DI+0C] */
    }
    s.ax=(uint16_t)(s.ax&0x000fu);
    s.flags=logic_flags(s.flags,s.ax,16u);             /* AND AX,0F */
    s.dx=pop(&s);                                      /* POP DX */
    s.si=s.ax;
    operand=read16(&s,s.ds,(uint16_t)(s.di+0x0au));
    {
        uint16_t before=s.si;
        s.si=(uint16_t)(s.si+operand);
        s.flags=add16_flags(s.flags,before,operand);   /* ADD SI,[DI+0A] */
    }
    s.bx=s.si;
    operand=read16(&s,s.ds,(uint16_t)(s.di+0x12u));
    {
        uint16_t before=s.bx;
        s.bx=(uint16_t)(s.bx+operand);
        s.flags=add16_flags(s.flags,before,operand);   /* ADD BX,[DI+12] */
    }
    {
        unsigned i;
        for(i=0u;i<3u;++i) {
            uint16_t before=s.dx;
            s.dx=(uint16_t)(before>>1);
            s.flags=(uint16_t)((s.flags&~ARITH)|szp(s.dx,16u)|
                              ((before&1u)?CF:0u)|((before&0x8000u)?OF:0u));
        }
    }
    s.cx=read16(&s,s.ds,(uint16_t)(s.di+0x06u));
    s.cached_callback=read16(&s,s.ds,(uint16_t)(s.di+0x14u));
    push(&s,s.cached_callback);                        /* PUSH [DI+14] */
    set_al(&s,read8(&s,s.ds,(uint16_t)(s.di+0x20u)));
    s.di=read16(&s,s.ds,(uint16_t)(s.di+0x02u));
    {
        uint16_t before=s.di;
        s.di=(uint16_t)(s.di+s.cx);
        s.flags=add16_flags(s.flags,before,s.cx);      /* ADD DI,CX */
    }
    if((s.flags&SF)!=0u) {
        s.di=0u;s.flags=logic_flags(s.flags,0u,16u);   /* XOR DI,DI */
    }
    push(&s,s.ax);                                     /* PUSH AX */
    push(&s,s.dx);                                     /* PUSH DX */
    s.ax=s.di;s.di=0x2cu;                              /* MOV AX,DI / DI,2C */
    {
        uint32_t product=(uint32_t)s.ax*(uint32_t)s.di;
        s.ax=(uint16_t)product;s.dx=(uint16_t)(product>>16);
        s.flags=(uint16_t)((s.flags&~ARITH)|((s.dx!=0u)?(CF|OF):0u));
    }
    s.di=s.ax;
    s.dx=pop(&s);                                      /* POP DX */
    s.ax=pop(&s);                                      /* POP AX */
    {
        uint16_t before=s.di;
        s.di=(uint16_t)(s.di+s.dx);
        s.flags=add16_flags(s.flags,before,s.dx);      /* ADD DI,DX */
    }
    operand=read16(&s,s.ds,SEG09A9_DrawingOrigin);
    {
        uint16_t before=s.di;
        s.di=(uint16_t)(s.di+operand);
        s.flags=add16_flags(s.flags,before,operand);   /* ADD DI,[origin] */
    }
    s.cx=read16(&s,s.ds,SEG09A9_EntitySpriteBufferSegment);
    {
        uint16_t before=s.cx;
        s.cx=(uint16_t)(s.cx+s.bp);
        s.flags=add16_flags(s.flags,before,s.bp);     /* ADD CX,BP */
    }
    s.flags=logic_flags(s.flags,al(&s),8u);            /* AND AL,AL */
#if ENTITY_SPRITE_DISPATCH_MUTATION == 2
    if((s.flags&ZF)!=0u) {
#else
    if((s.flags&ZF)==0u) {
#endif
        uint16_t before_strip_ds,before_strip_es,before_strip_flags;
        s.bp=s.ax;
        s.ax=pop(&s);                                  /* POP AX: callback */
        s.dx=pop(&s);                                  /* POP DX: saved angle */
        if(ENTITY_SPRITE_DISPATCH_MUTATION==3)
            s.ax=s.cached_callback;

        push(&s,s.dx);                                 /* PUSH DX */
        push(&s,s.ax);                                 /* PUSH AX */
        push(&s,s.di);                                 /* PUSH DI */
        push(&s,s.cx);                                 /* PUSH CX */
        push(&s,s.si);                                 /* PUSH SI */
        push(&s,s.bx);                                 /* PUSH BX */
        s.cx=read16(&s,s.ds,SEG09A9_GeneratedGraphicsBufferSegment);
        {
            unsigned i;
            for(i=0u;i<4u;++i) {
                uint8_t before=dl(&s),after;
                s.flags=shl8_flags(s.flags,before,&after);
                set_dl(&s,after);                       /* SHL DL,1 */
            }
        }
        set_dh(&s,0u);s.flags=logic_flags(s.flags,0u,8u);/* XOR DH,DH */
        s.ax=s.bp;set_ah(&s,al(&s));                    /* MOV AX,BP; AH,AL */
        set_ah(&s,(uint8_t)(ah(&s)&0xf0u));
        s.flags=logic_flags(s.flags,ah(&s),8u);         /* AND AH,F0 */
        set_al(&s,0x40u);
        {
            uint8_t before=al(&s),right=ah(&s);
            set_al(&s,(uint8_t)(before-right));
            s.flags=sub8_flags(s.flags,before,right);  /* SUB AL,AH */
        }
        set_ah(&s,0u);s.flags=logic_flags(s.flags,0u,8u); /* XOR AH,AH */
        {
            unsigned i;
            for(i=0u;i<3u;++i) {
                uint16_t before=s.ax;
                s.flags=shl16_flags(s.flags,before,&s.ax);
            }
        }
        {
            uint16_t before=s.ax;
            s.ax=(uint16_t)(s.ax+0x1070u);
            s.flags=add16_flags(s.flags,before,0x1070u);/* ADD AX,1070 */
        }
        {
            uint16_t before=s.ax;
            s.ax=(uint16_t)(s.ax+s.dx);
            s.flags=add16_flags(s.flags,before,s.dx);  /* ADD AX,DX */
        }
        s.si=s.ax;
        {
            uint16_t before=s.di;
            s.di=(uint16_t)(s.di-0x015fu);
            s.flags=sub16_flags(s.flags,before,0x015fu);/* SUB DI,15F */
        }
        before_strip_ds=s.ds;before_strip_es=s.es;before_strip_flags=s.flags;
        child=call_strip(&s);
        if(child.status!=LMN_ENTITY_SPRITE_DISPATCH_READY)return child;
        s.bx=pop(&s);                                  /* POP BX */
        s.si=pop(&s);                                  /* POP SI */
        s.cx=pop(&s);                                  /* POP CX */
        s.di=pop(&s);                                  /* POP DI */
#if ENTITY_SPRITE_DISPATCH_MUTATION == 9
        s.ds=before_strip_ds;s.es=before_strip_es;s.flags=before_strip_flags;
#else
        (void)before_strip_ds;(void)before_strip_es;(void)before_strip_flags;
#endif
    }

    /* Both strip and no-strip paths resume at 7159 with the same live stack. */
    s.ax=pop(&s);                                      /* POP AX callback */
    s.dx=pop(&s);                                      /* POP DX angle */
    if(ENTITY_SPRITE_DISPATCH_MUTATION==3)
        s.ax=s.cached_callback;
    {
        uint16_t target=s.ax;
        uint16_t child_status=dispatch_callback(&s,target);
        if(child_status==0xffffu) {
            return stop_at(&s,CS_EntitySpriteIndirectCall,
                           LMN_ENTITY_SPRITE_DISPATCH_UNKNOWN_CALLBACK);
        }
        if(child_status!=0u)
            return stop_at(&s,s.ip,LMN_ENTITY_SPRITE_DISPATCH_CHILD_RETURN);
    }
    s.di=pop(&s);                                      /* POP DI at 715D */
#if ENTITY_SPRITE_DISPATCH_MUTATION == 7
    s.di=s.entry_di;
#endif
    return stop_at(&s,CS_EntitySpriteReturn,LMN_ENTITY_SPRITE_DISPATCH_READY);

visibility_miss:
    s.di=pop(&s);                                      /* shared POP DI */
#if ENTITY_SPRITE_DISPATCH_MUTATION == 7
    s.di=s.entry_di;
#endif
    return stop_at(&s,CS_EntitySpriteReturn,LMN_ENTITY_SPRITE_DISPATCH_READY);
}

static void apply_result(LmnRegs *r,const LmnEntitySpriteDispatchResult *out) {
    r->ax=out->value;r->bx=out->map_cursor;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->record_cursor;
    r->di=out->object_cursor;r->bp=out->candidate_y;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;
    r->ip=out->continuation;
}

#if ENTITY_SPRITE_DISPATCH_MUTATION != 10
static uint16_t read_return(uint8_t *memory,uint16_t ss,uint16_t sp,
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
#endif

uint16_t lmn_draw_entity_sprite_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus) {
    LmnEntitySpriteDispatchCall call={
        registers->ax,registers->bx,registers->cx,registers->dx,
        registers->si,registers->di,registers->bp,
        registers->cs,registers->ds,registers->es,
        registers->ss,registers->sp,registers->flags
    };
    LmnEntitySpriteDispatchResult out=lmn_draw_entity_sprite_core(memory,&call,bus);
    apply_result(registers,&out);
    if(out.status==LMN_ENTITY_SPRITE_DISPATCH_READY) {
#if ENTITY_SPRITE_DISPATCH_MUTATION == 10
        /* Mutation: leave the actual outer RET word unconsumed. */
#else
        registers->ip=read_return(memory,registers->ss,registers->sp,
                                  registers->flags,bus);
        registers->sp=(uint16_t)(registers->sp+2u);
#endif
    }
    return out.status;
}

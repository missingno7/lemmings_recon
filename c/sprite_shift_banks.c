#include "sprite_shift_banks.h"

#include "lemmings_sym.h"

#ifndef SPRITE_SHIFT_BANKS_MUTATION
#define SPRITE_SHIFT_BANKS_MUTATION 0
#endif

#if SPRITE_SHIFT_BANKS_MUTATION < 0 || SPRITE_SHIFT_BANKS_MUTATION > 10
#error "SPRITE_SHIFT_BANKS_MUTATION must be a numeric ID from 0 through 10"
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct SpriteShiftBanksState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
} SpriteShiftBanksState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+(uint32_t)offset)&MEMORY_MASK);
}

static uint8_t read_physical(SpriteShiftBanksState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(SpriteShiftBanksState *s,uint32_t address,
                           uint8_t value,uint16_t flags) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

/* Byte operands wrap their effective offsets independently. The mutation
   models incorrectly treating a high byte as the next physical byte. */
static uint8_t read_operand(SpriteShiftBanksState *s,uint16_t segment,
                            uint16_t base,uint16_t displacement) {
#if SPRITE_SHIFT_BANKS_MUTATION == 5
    uint32_t address=(physical(segment,base)+(uint32_t)displacement)&
                     MEMORY_MASK;
    return read_physical(s,address);
#else
    uint16_t offset=(uint16_t)(base+displacement);
    return read_physical(s,physical(segment,offset));
#endif
}

static void write_operand(SpriteShiftBanksState *s,uint16_t segment,
                          uint16_t base,uint16_t displacement,uint8_t value) {
#if SPRITE_SHIFT_BANKS_MUTATION == 5
    uint32_t address=(physical(segment,base)+(uint32_t)displacement)&
                     MEMORY_MASK;
    write_physical(s,address,value,s->flags);
#else
    uint16_t offset=(uint16_t)(base+displacement);
    write_physical(s,physical(segment,offset),value,s->flags);
#endif
}

/* A real-mode stack word is two consecutive physical bytes. */
static uint16_t read16(SpriteShiftBanksState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(SpriteShiftBanksState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
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
    /* AF is undefined on logical operations; preserve it as opaque state. */
    return (uint16_t)((flags&~LOGIC)|szp(value,bits));
}

static uint16_t sub8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t value=(uint8_t)(left-right);
    uint16_t out=szp(value,8u);
    if(left<right)out|=CF;
    if((left^right^value)&0x10u)out|=AF;
    if(((left^right)&(left^value)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)wide,out=szp(value,16u);
    if(wide>0xffffu)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if((~(left^right)&(left^value)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t sub16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint16_t value=(uint16_t)(left-right),out=szp(value,16u);
    if(left<right)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if(((left^right)&(left^value)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t dec8_flags(uint16_t flags,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t out=szp(value,8u);
    if((before^1u^value)&0x10u)out|=AF;
    if(before==0x80u)out|=OF;
    return (uint16_t)((flags&~(ARITH&~CF))|out);
}

static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint8_t value=(uint8_t)(before+1u);
    uint16_t out=szp(value,8u);
    if((before^1u^value)&0x10u)out|=AF;
    if(before==0x7fu)out|=OF;
    return (uint16_t)((flags&~(ARITH&~CF))|out);
}

static uint8_t shr8(SpriteShiftBanksState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before>>1);
    uint16_t out=szp(value,8u);
    if(before&1u)out|=CF;
    if(before&0x80u)out|=OF;
    /* AF is undefined on SHR and stays opaque. */
    s->flags=(uint16_t)((s->flags&~(ARITH&~AF))|out);
    return value;
}

static uint8_t rcr8(SpriteShiftBanksState *s,uint8_t before) {
    uint8_t old_cf=(uint8_t)(s->flags&CF);
    uint8_t new_cf=(uint8_t)(before&1u);
    uint8_t value=(uint8_t)((before>>1)|((uint16_t)old_cf<<7));
    uint16_t out=(uint16_t)(new_cf?CF:0u);
    if((((value>>7)^(value>>6))&1u)!=0u)out|=OF;
    /* RCR updates CF/OF only for this one-bit rotation. */
    s->flags=(uint16_t)((s->flags&~(CF|OF))|out);
    return value;
}

static uint8_t ch(const SpriteShiftBanksState *s) {
    return (uint8_t)(s->cx>>8);
}
static uint8_t cl(const SpriteShiftBanksState *s) {
    return (uint8_t)s->cx;
}
static uint8_t dh(const SpriteShiftBanksState *s) {
    return (uint8_t)(s->dx>>8);
}
static uint8_t dl(const SpriteShiftBanksState *s) {
    return (uint8_t)s->dx;
}
static uint8_t ah(const SpriteShiftBanksState *s) {
    return (uint8_t)(s->ax>>8);
}
static uint8_t al(const SpriteShiftBanksState *s) {
    return (uint8_t)s->ax;
}
static uint8_t bh(const SpriteShiftBanksState *s) {
    return (uint8_t)(s->bx>>8);
}
static uint8_t bl(const SpriteShiftBanksState *s) {
    return (uint8_t)s->bx;
}

static void set_ch(SpriteShiftBanksState *s,uint8_t value) {
    s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)value<<8));
}
static void set_cl(SpriteShiftBanksState *s,uint8_t value) {
    s->cx=(uint16_t)((s->cx&0xff00u)|value);
}
static void set_ah(SpriteShiftBanksState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}
static void set_al(SpriteShiftBanksState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}
static void set_bh(SpriteShiftBanksState *s,uint8_t value) {
    s->bx=(uint16_t)((s->bx&0x00ffu)|((uint16_t)value<<8));
}
static void set_bl(SpriteShiftBanksState *s,uint8_t value) {
    s->bx=(uint16_t)((s->bx&0xff00u)|value);
}

static void push(SpriteShiftBanksState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value,s->flags);
}

static uint16_t pop(SpriteShiftBanksState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void initialize_state(SpriteShiftBanksState *s,uint8_t *memory,
                             const LmnSpriteShiftBanksCall *call,
                             const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->ax;s->bx=call->bx;s->cx=call->cx;s->dx=call->dx;
    s->si=call->si;s->di=call->di;s->bp=call->bp;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=CS_ThreeByteSpriteBanksReturn;
    s->status=LMN_SPRITE_SHIFT_BANKS_READY;
}

static LmnSpriteShiftBanksResult result_of(const SpriteShiftBanksState *s) {
    LmnSpriteShiftBanksResult out;
    out.ax=s->ax;out.bx=s->bx;out.cx=s->cx;out.dx=s->dx;
    out.si=s->si;out.di=s->di;out.bp=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;out.extra_segment=s->es;
    out.stack_segment=s->ss;out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

LmnSpriteShiftBanksResult lmn_generate_sprite_shift_banks3_core(
    uint8_t *memory,const LmnSpriteShiftBanksCall *call,
    const LmnRasterBus *bus) {
    SpriteShiftBanksState s;
    initialize_state(&s,memory,call,bus);

    /* XOR CL,CL; the bank pass saves and restores its live entry registers. */
    set_cl(&s,0u);
    s.flags=logic_flags(s.flags,0u,8u);
    for(;;) {
#if SPRITE_SHIFT_BANKS_MUTATION == 7
        uint16_t cached_bank_si=s.si;
#endif
        push(&s,s.cx);                         /* PUSH CX at 5B13 */
        push(&s,s.si);                         /* PUSH SI at 5B14 */
        s.bp=s.di;                             /* MOV BP,DI */
        set_ch(&s,dh(&s));                    /* MOV CH,DH */

        /* Each DH plane emits DL shifted source triples. Both counters use
           DEC/JNZ do-while loops, so zero means 256 iterations. */
#if SPRITE_SHIFT_BANKS_MUTATION == 1
        if(dh(&s)!=0u)
#endif
        {
            do {
                push(&s,s.cx);                 /* PUSH CX at 5B19 */
                set_ch(&s,dl(&s));            /* MOV CH,DL */
#if SPRITE_SHIFT_BANKS_MUTATION == 2
                if(dl(&s)!=0u)
#endif
                {
                    do {
                        uint8_t v;
                        v=read_operand(&s,s.ds,s.si,0u); /* MOV AH,[SI] */
                        set_ah(&s,v);
                        v=read_operand(&s,s.ds,s.si,1u); /* MOV AL,[SI+1] */
                        set_al(&s,v);
                        s.si=(uint16_t)(s.si+2u);       /* ADD SI,2 */
                        s.flags=add16_flags(s.flags,(uint16_t)(s.si-2u),2u);
                        set_bl(&s,0u);                  /* XOR BL,BL */
                        s.flags=logic_flags(s.flags,0u,8u);
                        {
                            uint8_t mask=cl(&s);        /* AND CL,CL */
                            s.flags=logic_flags(s.flags,mask,8u);
                            if(mask!=0u) {
                                set_bh(&s,mask);        /* MOV BH,CL */
                                do {
                                    set_ah(&s,shr8(&s,ah(&s)));
#if SPRITE_SHIFT_BANKS_MUTATION == 3
                                    set_al(&s,shr8(&s,al(&s)));
#else
                                    set_al(&s,rcr8(&s,al(&s)));
#endif
                                    set_bl(&s,rcr8(&s,bl(&s)));
                                    {
                                        uint8_t before=bh(&s);
                                        set_bh(&s,(uint8_t)(before-1u));
                                        s.flags=dec8_flags(s.flags,before);
                                    }
                                } while(bh(&s)!=0u);
                            }
                        }
                        write_operand(&s,s.es,s.di,0u,ah(&s)); /* MOV [ES:DI],AH */
                        write_operand(&s,s.es,s.di,1u,al(&s));
                        write_operand(&s,s.es,s.di,2u,bl(&s));
                        s.di=(uint16_t)(s.di+3u);       /* ADD DI,3 */
                        s.flags=add16_flags(s.flags,(uint16_t)(s.di-3u),3u);
                        {
                            uint8_t before=ch(&s);
                            set_ch(&s,(uint8_t)(before-1u));
                            s.flags=dec8_flags(s.flags,before);
                        }
                    } while(ch(&s)!=0u);
                }
                s.cx=pop(&s);                  /* POP CX at 5B48 */
                {
                    uint8_t before=ch(&s);
                    set_ch(&s,(uint8_t)(before-1u));
                    s.flags=dec8_flags(s.flags,before);
                }
            } while(ch(&s)!=0u);
        }

        s.si=s.bp;                             /* MOV SI,BP */
        set_ch(&s,dl(&s));                    /* MOV CH,DL */

        /* Mask each output row by ORing DH source planes. The three mask
           byte reads are separate EA16 operands; DX is saved/restored live. */
#if SPRITE_SHIFT_BANKS_MUTATION == 2
        if(dl(&s)!=0u)
#endif
        {
            do {
#if SPRITE_SHIFT_BANKS_MUTATION == 8
                uint16_t cached_mask_cx=s.cx;
#endif
                push(&s,s.si);                 /* PUSH SI at 5B51 */
                push(&s,s.cx);                 /* PUSH CX at 5B52 */
                set_ch(&s,dh(&s));            /* MOV CH,DH */
                push(&s,s.dx);                 /* PUSH DX at 5B55 */
                {
                    s.dx=(uint16_t)(s.dx&0x00ffu); /* XOR DH,DH */
                    s.flags=logic_flags(s.flags,0u,8u);
                }
                s.bp=s.dx;                     /* MOV BP,DX */
                {
                    uint16_t before=s.dx;
                    s.dx=(uint16_t)(s.dx+s.dx); /* ADD DX,DX */
                    s.flags=add16_flags(s.flags,before,before);
                }
                {
                    uint16_t before=s.bp;
                    s.bp=(uint16_t)(s.bp+s.dx); /* ADD BP,DX */
                    s.flags=add16_flags(s.flags,before,s.dx);
                }
                s.dx=pop(&s);                  /* POP DX, live stack word */
                s.ax=0u;                       /* XOR AX,AX */
                s.flags=logic_flags(s.flags,0u,16u);
                set_bl(&s,0u);                 /* XOR BL,BL */
                s.flags=logic_flags(s.flags,0u,8u);

                do {                           /* 5B63, zero DH means 256 */
                    uint8_t value;
                    value=read_operand(&s,
#if SPRITE_SHIFT_BANKS_MUTATION == 4
                                       s.ds,
#else
                                       s.es,
#endif
                                       s.si,0u); /* OR AH,[ES:SI] */
                    {
                        uint8_t merged=(uint8_t)(ah(&s)|value);
                        set_ah(&s,merged);
                        s.flags=logic_flags(s.flags,merged,8u);
                    }
                    value=read_operand(&s,
#if SPRITE_SHIFT_BANKS_MUTATION == 4
                                       s.ds,
#else
                                       s.es,
#endif
                                       s.si,1u); /* OR AL,[ES:SI+1] */
                    {
                        uint8_t merged=(uint8_t)(al(&s)|value);
                        set_al(&s,merged);
                        s.flags=logic_flags(s.flags,merged,8u);
                    }
                    value=read_operand(&s,
#if SPRITE_SHIFT_BANKS_MUTATION == 4
                                       s.ds,
#else
                                       s.es,
#endif
                                       s.si,2u); /* OR BL,[ES:SI+2] */
                    {
                        uint8_t merged=(uint8_t)(bl(&s)|value);
                        set_bl(&s,merged);
                        s.flags=logic_flags(s.flags,merged,8u);
                    }
                    {
                        uint16_t before=s.si;
                        s.si=(uint16_t)(s.si+s.bp); /* ADD SI,BP */
                        s.flags=add16_flags(s.flags,before,s.bp);
                    }
                    {
                        uint8_t before=ch(&s);
                        set_ch(&s,(uint8_t)(before-1u));
                        s.flags=dec8_flags(s.flags,before);
                    }
                } while(ch(&s)!=0u);

                write_operand(&s,s.es,s.di,0u,ah(&s)); /* MOV [ES:DI],AH */
                write_operand(&s,s.es,s.di,1u,al(&s));
                write_operand(&s,s.es,s.di,2u,bl(&s));
                s.di=(uint16_t)(s.di+3u);     /* ADD DI,3 */
                s.flags=add16_flags(s.flags,(uint16_t)(s.di-3u),3u);
#if SPRITE_SHIFT_BANKS_MUTATION == 8
                s.sp=(uint16_t)(s.sp+2u);
                s.cx=cached_mask_cx;
#else
                s.cx=pop(&s);                 /* POP CX at 5B82 */
#endif
                s.si=pop(&s);                 /* POP SI at 5B83 */
                {
                    uint16_t before=s.si;
                    s.si=(uint16_t)(s.si+3u);  /* ADD SI,3 */
                    s.flags=add16_flags(s.flags,before,3u);
                }
                {
                    uint8_t before=ch(&s);
                    set_ch(&s,(uint8_t)(before-1u));
                    s.flags=dec8_flags(s.flags,before);
                }
            } while(ch(&s)!=0u);
        }

#if SPRITE_SHIFT_BANKS_MUTATION == 7
        s.sp=(uint16_t)(s.sp+2u);
        s.si=cached_bank_si;
#else
        s.si=pop(&s);                          /* POP SI at 5B8B */
#endif
        s.cx=pop(&s);                          /* POP CX at 5B8C */
        {
            uint8_t before=cl(&s);
            set_cl(&s,(uint8_t)(before+1u));   /* INC CL */
            s.flags=inc8_flags(s.flags,before);
        }
        {
            uint8_t before=cl(&s);
            s.flags=sub8_flags(s.flags,before,8u); /* CMP CL,8 */
            if(before==8u)break;               /* JZ 5B97 */
        }
    }

    /* CMP DI,10h / signed JL; negative DI values skip segment folding. */
    {
        uint16_t before=s.di;
        s.flags=sub16_flags(s.flags,before,0x10u);
#if SPRITE_SHIFT_BANKS_MUTATION == 6
        if(before<0x10u)goto done;
#else
        if(((s.flags&SF)!=0u)!=((s.flags&OF)!=0u))goto done;
#endif
    }
    s.ax=s.di;                                 /* MOV AX,DI */
    {
        unsigned count;
        for(count=0u;count<4u;++count) {
            uint16_t before=s.ax;
            s.ax=(uint16_t)(before>>1);        /* SHR AX,1 */
            {
                uint16_t out=szp(s.ax,16u);
                if(before&1u)out|=CF;
                if(before&0x8000u)out|=OF;
                s.flags=(uint16_t)((s.flags&~(ARITH&~AF))|out);
            }
        }
    }
    s.cx=s.es;                                 /* MOV CX,ES */
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(s.ax+s.cx);            /* ADD AX,CX */
        s.flags=add16_flags(s.flags,before,s.cx);
    }
    s.es=s.ax;                                 /* MOV ES,AX */
    s.di=(uint16_t)(s.di&0x000fu);             /* AND DI,0Fh */
    s.flags=logic_flags(s.flags,s.di,16u);

done:
    return result_of(&s);
}

static void regs_from_result(const LmnSpriteShiftBanksResult *s,LmnRegs *r) {
    r->ax=s->ax;r->bx=s->bx;r->cx=s->cx;r->dx=s->dx;
    r->si=s->si;r->di=s->di;r->bp=s->bp;
    r->cs=s->code_segment;r->ds=s->data_segment;r->es=s->extra_segment;
    r->ss=s->stack_segment;r->sp=s->stack_offset;r->flags=s->flags;
    r->ip=s->continuation;
}

uint16_t lmn_generate_sprite_shift_banks3_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus) {
    LmnSpriteShiftBanksCall call={
        registers->ax,registers->bx,registers->cx,registers->dx,
        registers->si,registers->di,registers->bp,
        registers->cs,registers->ds,registers->es,
        registers->ss,registers->sp,registers->flags
    };
    LmnSpriteShiftBanksResult result;
#if SPRITE_SHIFT_BANKS_MUTATION == 9
    SpriteShiftBanksState prefetch_state;
    uint16_t prefetched_return;
    initialize_state(&prefetch_state,memory,&call,bus);
    prefetched_return=read16(&prefetch_state,registers->ss,registers->sp);
#endif
    result=lmn_generate_sprite_shift_banks3_core(memory,&call,bus);
    regs_from_result(&result,registers);
    if(result.status==LMN_SPRITE_SHIFT_BANKS_READY) {
#if SPRITE_SHIFT_BANKS_MUTATION == 10
        registers->ip=result.continuation;
#else
        uint16_t return_word;
#if SPRITE_SHIFT_BANKS_MUTATION == 9
        return_word=prefetched_return;
#else
        SpriteShiftBanksState ret_state;
        initialize_state(&ret_state,memory,&call,bus);
        ret_state.flags=result.flags;
        return_word=read16(&ret_state,result.stack_segment,
                           result.stack_offset);
#endif
        registers->ip=return_word;
        registers->sp=(uint16_t)(result.stack_offset+2u);
#endif
    }
    return result.status;
}

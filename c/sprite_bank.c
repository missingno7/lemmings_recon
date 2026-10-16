#include "sprite_bank.h"

#include "lemmings_sym.h"

#ifndef SPRITE_BANK_MUTATION
#define SPRITE_BANK_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct SpriteBankState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
    uint16_t entry_si;
    uint16_t saved_mask_cx;
} SpriteBankState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+(uint32_t)offset)&MEMORY_MASK);
}

static uint8_t read_physical(SpriteBankState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(SpriteBankState *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(SpriteBankState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

/* Real-mode word transfers fetch/write the high byte at the next physical
   address, even when the low byte used offset FFFFh. */
static uint16_t read16(SpriteBankState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(SpriteBankState *s,uint16_t segment,uint16_t offset,
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
    /* AF is undefined on logical operations; keep it opaque. */
    return (uint16_t)((flags&~LOGIC)|szp(value,bits));
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

static uint16_t shr16_flags(uint16_t flags,uint16_t before) {
    uint16_t value=(uint16_t)(before>>1),out=szp(value,16u);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    /* AF is undefined on SHR and remains opaque. */
    return (uint16_t)((flags&~(ARITH&~AF))|out);
}

static uint16_t and16_flags(uint16_t flags,uint16_t value) {
    /* AND clears CF/OF; AF is undefined and remains opaque. */
    return (uint16_t)((flags&~LOGIC)|szp(value,16u));
}

static uint8_t ch(const SpriteBankState *s) { return (uint8_t)(s->cx>>8); }
static uint8_t dh(const SpriteBankState *s) { return (uint8_t)(s->dx>>8); }
static uint8_t dl(const SpriteBankState *s) { return (uint8_t)s->dx; }
static uint8_t al(const SpriteBankState *s) { return (uint8_t)s->ax; }
static uint8_t ah(const SpriteBankState *s) { return (uint8_t)(s->ax>>8); }

static void set_ch(SpriteBankState *s,uint8_t value) {
    s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)value<<8));
}
static void set_cl(SpriteBankState *s,uint8_t value) {
    s->cx=(uint16_t)((s->cx&0xff00u)|value);
}
static void set_al(SpriteBankState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}
static void set_ah(SpriteBankState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void push(SpriteBankState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value,s->flags);
}

static uint16_t pop(SpriteBankState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void rep_movsw(SpriteBankState *s) {
    uint16_t step=(s->flags&DF)?0xfffeu:2u;
#if SPRITE_BANK_MUTATION == 3
    step=2u;
#endif
    while(s->cx!=0u) {
        uint16_t word=read16(s,s->ds,s->si);
        write16(s,s->es,s->di,word,s->flags);
        s->si=(uint16_t)(s->si+step);
        s->di=(uint16_t)(s->di+step);
        s->cx=(uint16_t)(s->cx-1u);
    }
}

static void stosw(SpriteBankState *s) {
    uint16_t step=(s->flags&DF)?0xfffeu:2u;
#if SPRITE_BANK_MUTATION == 3
    step=2u;
#endif
    write16(s,s->es,s->di,s->ax,s->flags);
    s->di=(uint16_t)(s->di+step);
}

static void initialize_state(SpriteBankState *s,uint8_t *memory,
                             const LmnSpriteBankCall *call,
                             const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->ax;s->bx=call->bx;s->cx=call->cx;s->dx=call->dx;
    s->si=call->si;s->di=call->di;s->bp=call->bp;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=CS_SpriteBankReturn;
    s->status=LMN_SPRITE_BANK_READY;
    s->entry_si=call->si;s->saved_mask_cx=0u;
}

static LmnSpriteBankResult result_of(const SpriteBankState *s) {
    LmnSpriteBankResult out;
    out.ax=s->ax;out.bx=s->bx;out.cx=s->cx;out.dx=s->dx;
    out.si=s->si;out.di=s->di;out.bp=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;out.extra_segment=s->es;
    out.stack_segment=s->ss;out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

LmnSpriteBankResult lmn_copy_sprite_planes_mask_core(
    uint8_t *memory,const LmnSpriteBankCall *call,const LmnRasterBus *bus) {
    SpriteBankState s;
    initialize_state(&s,memory,call,bus);

    /* PUSH SI; MOV BP,DI; MOV CH,DH. The save is a live SS word. */
    push(&s,s.si);
    s.bp=s.di;
    set_ch(&s,dh(&s));

    /* Each plane uses CL=DL and XOR CH,CH before REP MOVSW. POP CX and DEC
       CH are deliberately live so aliases can change the next loop count. */
#if SPRITE_BANK_MUTATION == 1
    if(dh(&s)!=0u)
#endif
    {
        do {
            uint16_t saved_cx;
            push(&s,s.cx);
            set_cl(&s,dl(&s));
            set_ch(&s,0u);
            s.flags=logic_flags(s.flags,0u,8u); /* XOR CH,CH */
            rep_movsw(&s);
            saved_cx=pop(&s);
            s.cx=saved_cx;
            {
                uint8_t before=ch(&s);
                set_ch(&s,(uint8_t)(before-1u));
                s.flags=dec8_flags(s.flags,before);
            }
        } while(ch(&s)!=0u);
    }

    /* MOV SI,BP; MOV CH,DL. Mask cursor advances forward between outputs. */
    s.si=s.bp;
    set_ch(&s,dl(&s));

    /* The outer CH loop is a do-while, so DL=0 means 256 mask words. */
#if SPRITE_BANK_MUTATION == 2
    if(dl(&s)!=0u)
#endif
    {
        do {
#if SPRITE_BANK_MUTATION != 8
            uint16_t saved_cx;
#endif
            push(&s,s.si);
            s.saved_mask_cx=s.cx;
            push(&s,s.cx);
            set_ch(&s,dh(&s));
            set_al(&s,dl(&s));
            set_ah(&s,0u);
            s.flags=logic_flags(s.flags,0u,8u); /* XOR AH,AH */
            {
                uint16_t before=s.ax;
                s.ax=(uint16_t)(s.ax<<1);
                s.flags=(uint16_t)((s.flags&~(ARITH&~AF))|
                                   szp(s.ax,16u));
                if(before&0x8000u)s.flags|=CF;
                if((((before>>15)^(s.ax>>15))&1u)!=0u)s.flags|=OF;
            }
            s.bp=s.ax;
            s.ax=0u;
            s.flags=logic_flags(s.flags,0u,16u); /* XOR AX,AX */
            s.bx=(uint16_t)(s.bx&0xff00u);       /* XOR BL,BL */
            s.flags=logic_flags(s.flags,0u,8u);

            /* OR AL,[ES:SI]; OR AH,[ES:(SI+1)&FFFF]; ADD SI,BP; DEC CH.
               The two mask byte operands wrap their offsets independently. */
            do {
                uint8_t value=read8(&s,
#if SPRITE_BANK_MUTATION == 4
                                    s.ds,
#else
                                    s.es,
#endif
                                    s.si);
                uint8_t merged=(uint8_t)(al(&s)|value);
                set_al(&s,merged);
                s.flags=logic_flags(s.flags,merged,8u);
                {
#if SPRITE_BANK_MUTATION == 5
                    uint32_t next=(physical(s.es,s.si)+1u)&MEMORY_MASK;
                    value=read_physical(&s,next);
#else
                    uint16_t high_offset=(uint16_t)(s.si+1u);
#if SPRITE_BANK_MUTATION == 4
                    value=read8(&s,s.ds,high_offset);
#else
                    value=read8(&s,s.es,high_offset);
#endif
#endif
                }
                merged=(uint8_t)(ah(&s)|value);
                set_ah(&s,merged);
                s.flags=logic_flags(s.flags,merged,8u);
                {
                    uint16_t before=s.si;
                    s.si=(uint16_t)(s.si+s.bp);
                    s.flags=add16_flags(s.flags,before,s.bp);
                }
                {
                    uint8_t before=ch(&s);
                    set_ch(&s,(uint8_t)(before-1u));
                    s.flags=dec8_flags(s.flags,before);
                }
            } while(ch(&s)!=0u);

            stosw(&s);
#if SPRITE_BANK_MUTATION == 8
            s.cx=s.saved_mask_cx;
            s.sp=(uint16_t)(s.sp+2u);
#else
            saved_cx=pop(&s);
            s.cx=saved_cx;
#endif
            s.si=pop(&s);
            {
                uint16_t before=s.si;
                s.si=(uint16_t)(s.si+2u);
                s.flags=add16_flags(s.flags,before,2u);
            }
            {
                uint8_t before=ch(&s);
                set_ch(&s,(uint8_t)(before-1u));
                s.flags=dec8_flags(s.flags,before);
            }
        } while(ch(&s)!=0u);
    }

    /* POP SI; CMP DI,10h; signed JL skips ES folding for negative DI. */
#if SPRITE_BANK_MUTATION == 7
    s.sp=(uint16_t)(s.sp+2u);
    s.si=s.entry_si;
#else
    s.si=pop(&s);
#endif
    {
        uint16_t before=s.di;
        s.flags=sub16_flags(s.flags,before,0x10u);
    }
#if SPRITE_BANK_MUTATION == 6
    if(s.di<0x10u)
#else
    if(((s.flags&SF)!=0u)!=((s.flags&OF)!=0u))
#endif
        goto done;

    s.ax=s.di;
    {
        unsigned shift;
        for(shift=0u;shift<4u;++shift) {
            uint16_t before=s.ax;
            s.ax=(uint16_t)(before>>1);
            s.flags=shr16_flags(s.flags,before);
        }
    }
    s.cx=s.es;
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(s.ax+s.cx);
        s.flags=add16_flags(s.flags,before,s.cx);
    }
    s.es=s.ax;
    s.di=(uint16_t)(s.di&0x000fu);
    s.flags=and16_flags(s.flags,s.di);

done:
    s.continuation=CS_SpriteBankReturn;
    return result_of(&s);
}

static void regs_from_result(const LmnSpriteBankResult *s,LmnRegs *r) {
    r->ax=s->ax;r->bx=s->bx;r->cx=s->cx;r->dx=s->dx;
    r->si=s->si;r->di=s->di;r->bp=s->bp;
    r->cs=s->code_segment;r->ds=s->data_segment;r->es=s->extra_segment;
    r->ss=s->stack_segment;r->sp=s->stack_offset;r->flags=s->flags;
    r->ip=s->continuation;
}

uint16_t lmn_copy_sprite_planes_mask_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus) {
    LmnSpriteBankCall call={
        registers->ax,registers->bx,registers->cx,registers->dx,
        registers->si,registers->di,registers->bp,
        registers->cs,registers->ds,registers->es,
        registers->ss,registers->sp,registers->flags
    };
    LmnSpriteBankResult result;
#if SPRITE_BANK_MUTATION == 9
    uint16_t prefetched_return=0u;
    SpriteBankState prefetch_state;
    initialize_state(&prefetch_state,memory,&call,bus);
    prefetched_return=read16(&prefetch_state,registers->ss,registers->sp);
#endif
    result=lmn_copy_sprite_planes_mask_core(memory,&call,bus);
    regs_from_result(&result,registers);
    if(result.status==LMN_SPRITE_BANK_READY) {
#if SPRITE_BANK_MUTATION == 10
        registers->ip=result.continuation;
#else
        uint16_t return_word;
#if SPRITE_BANK_MUTATION == 9
        return_word=prefetched_return;
#else
        SpriteBankState ret_state;
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

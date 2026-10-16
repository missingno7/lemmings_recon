#include "entity_sprite_shifted.h"

#include "lemmings_sym.h"

#ifndef ENTITY_SPRITE_SHIFTED_MUTATION
#define ENTITY_SPRITE_SHIFTED_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF
};

typedef struct ShiftedSpriteState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
} ShiftedSpriteState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(ShiftedSpriteState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(ShiftedSpriteState *s,uint32_t address,uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(ShiftedSpriteState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(ShiftedSpriteState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(ShiftedSpriteState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ShiftedSpriteState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned parity=0u,bit;
    uint16_t result=0u;
    for(bit=0u;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)result|=PF;
    if(value==0u)result|=ZF;
    if(value&(1u<<(bits-1u)))result|=SF;
    return result;
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)wide,out=szp(value,16u);
    if(wide>0xffffu)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if((~(left^right)&(left^value)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t dec8_flags(uint16_t flags,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t out=szp(value,8u);
    if((before^1u^value)&0x10u)out|=AF;
    if(before==0x80u)out|=OF;
    return (uint16_t)((flags&~(PF|AF|ZF|SF|OF))|out);
}

static uint16_t dec16_flags(uint16_t flags,uint16_t before) {
    uint16_t value=(uint16_t)(before-1u),out=szp(value,16u);
    if((before^1u^value)&0x10u)out|=AF;
    if(before==0x8000u)out|=OF;
    return (uint16_t)((flags&~(PF|AF|ZF|SF|OF))|out);
}

static uint16_t shr16_flags(uint16_t flags,uint16_t before,uint16_t *after) {
    uint16_t value=(uint16_t)(before>>1),out=szp(value,16u);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    *after=value;
    return (uint16_t)((flags&~(CF|PF|AF|ZF|SF|OF))|out);
}

static uint16_t rcr8_flags(uint16_t flags,uint8_t before,uint8_t *after) {
    unsigned old_carry=flags&CF;
    uint8_t value=(uint8_t)((before>>1)|(old_carry?0x80u:0u));
    unsigned carry=before&1u;
    uint16_t out=(uint16_t)((flags&~(CF|OF))|(carry?CF:0u));
    if((((value>>7)^(value>>6))&1u)!=0u)out|=OF;
    *after=value;
    return out;
}

static void push(ShiftedSpriteState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(ShiftedSpriteState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void output(ShiftedSpriteState *s,uint16_t mirror) {
    write16(s,s->ss,mirror,s->ax);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
}

static void set_al(ShiftedSpriteState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(ShiftedSpriteState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void set_ch(ShiftedSpriteState *s,uint8_t value) {
    s->cx=(uint16_t)((s->cx&0x00ffu)|((uint16_t)value<<8));
}

static void lodsw(ShiftedSpriteState *s) {
    s->ax=read16(s,s->ds,s->si);
#if ENTITY_SPRITE_SHIFTED_MUTATION == 1
    s->si=(uint16_t)(s->si+2u);
#else
    s->si=(uint16_t)(s->si+((s->flags&DF)?(uint16_t)-2:2u));
#endif
}

static void stosb(ShiftedSpriteState *s) {
    write8(s,s->es,s->di,(uint8_t)s->ax);
#if ENTITY_SPRITE_SHIFTED_MUTATION == 2
    s->di=(uint16_t)(s->di+1u);
#else
    s->di=(uint16_t)(s->di+((s->flags&DF)?(uint16_t)-1:1u));
#endif
}

static void read_unused_vga(ShiftedSpriteState *s,unsigned phase) {
#if ENTITY_SPRITE_SHIFTED_MUTATION == 6
    if(phase==1u)return;
#elif ENTITY_SPRITE_SHIFTED_MUTATION == 7
    if(phase==2u)return;
#else
    (void)phase;
#endif
    (void)read8(s,s->es,s->di);
}

static LmnEntityShiftedSpriteResult result_of(const ShiftedSpriteState *s) {
    LmnEntityShiftedSpriteResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void initialize(ShiftedSpriteState *s,uint8_t *memory,
    const LmnEntityShiftedSpriteCall *call,const LmnRasterBus *bus,
    unsigned rows) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=rows==12u?CS_EntityShiftedSprite12Return:
                                   CS_EntityShiftedSprite13Return;
    s->status=LMN_ENTITY_SHIFTED_SPRITE_READY;
}

static void initial_vga_setup(ShiftedSpriteState *s) {
    s->dx=0x03c4u;s->ax=0x0f02u;output(s,SEG143E_VgaMapMaskMirror);
    s->dx=0x03ceu;s->ax=0u;
    s->flags=logic_flags(s->flags,s->ax,16u); /* XOR AX,AX */
    output(s,SEG143E_VgaSetResetMirror);
    s->ax=0x0e01u;output(s,SEG143E_VgaEnableSetResetMirror);
    s->ax=0x0005u;output(s,SEG143E_VgaGraphicsModeMirror);
    s->ax=0x0003u;output(s,SEG143E_VgaDataRotateMirror);
    s->ax=0xa000u;s->es=s->ax;
}

/* This deliberately spells the two-pass shifts as the original instruction
   sequences.  CH is the live loop counter; the incoming low byte is unchecked. */
static void shifted_first_pass(ShiftedSpriteState *s,unsigned rows) {
#if ENTITY_SPRITE_SHIFTED_MUTATION == 5
    uint16_t cached_mask=0u;
    unsigned have_cached_mask=0u;
#endif
    s->bp=(uint16_t)rows;
    do {
#if ENTITY_SPRITE_SHIFTED_MUTATION == 8
        uint16_t pushed_bx;
#endif
        uint8_t shifts;
        push(s,s->bp);                                 /* PUSH BP */
        lodsw(s);                                      /* LODSW */
        push(s,s->si);                                 /* PUSH SI */
        s->ax=(uint16_t)((s->ax<<8)|(s->ax>>8));       /* XCHG AL,AH */
        s->si=s->ax;                                  /* MOV SI,AX */
#if ENTITY_SPRITE_SHIFTED_MUTATION == 5
        if(!have_cached_mask) {
            s->ax=read16(s,s->ds,s->bx);              /* MOV AX,[BX] */
            cached_mask=s->ax;have_cached_mask=1u;
        } else {
            s->ax=cached_mask;                        /* mutation: stale mask */
        }
#else
        s->ax=read16(s,s->ds,s->bx);                  /* MOV AX,[BX] */
#endif
        {
            uint16_t before=s->bx;
            s->bx=(uint16_t)(s->bx+2u);
            s->flags=add16_flags(s->flags,before,2u); /* ADD BX,2 */
        }
#if ENTITY_SPRITE_SHIFTED_MUTATION == 8
        pushed_bx=s->bx;
#endif
        s->ax=(uint16_t)((s->ax<<8)|(s->ax>>8));      /* XCHG AL,AH */
        s->bp=s->ax;                                  /* MOV BP,AX */
        set_ch(s,(uint8_t)s->cx);                     /* MOV CH,CL */
        s->ax=0u;s->flags=logic_flags(s->flags,0u,16u); /* XOR AX,AX */
        s->flags=logic_flags(s->flags,(uint8_t)(s->cx>>8),8u); /* AND CH,CH */
        shifts=(uint8_t)(s->cx>>8);
#if ENTITY_SPRITE_SHIFTED_MUTATION == 4
        if(shifts>7u) {
            shifts=7u;set_ch(s,shifts);
            s->flags=logic_flags(s->flags,shifts,8u);
        }
#endif
        while(shifts!=0u) {
            uint8_t al,ah,old_ch;
            s->flags=shr16_flags(s->flags,s->si,&s->si);
            al=(uint8_t)s->ax;s->flags=rcr8_flags(s->flags,al,&al);set_al(s,al);
            s->flags=shr16_flags(s->flags,s->bp,&s->bp);
            ah=(uint8_t)(s->ax>>8);s->flags=rcr8_flags(s->flags,ah,&ah);set_ah(s,ah);
            old_ch=(uint8_t)(s->cx>>8);set_ch(s,(uint8_t)(old_ch-1u));
            s->flags=dec8_flags(s->flags,old_ch);
            shifts=(uint8_t)(s->cx>>8);
        }

        push(s,s->bx);                                 /* PUSH BX */
        push(s,s->cx);                                 /* PUSH CX */
        s->bx=s->bp;                                  /* MOV BX,BP */
        s->cx=s->si;                                  /* MOV CX,SI */
        s->bp=s->ax;                                  /* MOV BP,AX */
        s->ax=(uint16_t)((s->ax&0xff00u)|0x08u);      /* MOV AL,8 */
        set_ah(s,(uint8_t)(s->bx>>8));                /* MOV AH,BH */
        output(s,SEG143E_VgaBitMaskMirror);
#if ENTITY_SPRITE_SHIFTED_MUTATION == 9
        /* Mutation omits only this CLI; the live read remains. */
#else
        s->flags=(uint16_t)(s->flags&~IF);             /* CLI */
#endif
        read_unused_vga(s,1u);                         /* MOV AL,[ES:DI] */
        set_al(s,(uint8_t)(s->cx>>8));                /* MOV AL,CH */
        stosb(s);
        s->flags=(uint16_t)(s->flags|IF);             /* STI */

        set_al(s,0x08u);set_ah(s,(uint8_t)s->bx);     /* MOV AL,8 / AH,BL */
        output(s,SEG143E_VgaBitMaskMirror);
        s->flags=(uint16_t)(s->flags&~IF);             /* CLI */
        set_al(s,read8(s,s->es,s->di));
        set_al(s,(uint8_t)s->cx);                     /* MOV AL,CL */
        stosb(s);
        s->flags=(uint16_t)(s->flags|IF);             /* STI */

        s->bx=s->bp;                                  /* MOV BX,BP */
        set_al(s,0x08u);set_ah(s,(uint8_t)(s->bx>>8));/* MOV AL,8 / AH,BH */
        output(s,SEG143E_VgaBitMaskMirror);
        s->flags=(uint16_t)(s->flags&~IF);             /* CLI */
        set_al(s,read8(s,s->es,s->di));
        set_al(s,(uint8_t)s->bx);                     /* MOV AL,BL */
        stosb(s);
        s->flags=(uint16_t)(s->flags|IF);             /* STI */
        {
            uint16_t before=s->di;
            s->di=(uint16_t)(s->di+0x29u);
            s->flags=add16_flags(s->flags,before,0x29u); /* ADD DI,29 */
        }
        s->cx=pop(s);                                  /* POP CX */
        s->bx=pop(s);                                  /* POP BX */
#if ENTITY_SPRITE_SHIFTED_MUTATION == 8
        s->bx=pushed_bx;
#endif
        s->si=pop(s);                                  /* POP SI */
        s->bp=pop(s);                                  /* POP BP */
        {
            uint16_t before=s->bp;
            s->bp=(uint16_t)(s->bp-1u);
            s->flags=dec16_flags(s->flags,before);     /* DEC BP */
        }
    } while(s->bp!=0u);
}

static void second_vga_setup(ShiftedSpriteState *s) {
    s->ax=1u;output(s,SEG143E_VgaEnableSetResetMirror);
    s->ax=0x1003u;output(s,SEG143E_VgaDataRotateMirror);
    s->ax=0xff08u;output(s,SEG143E_VgaBitMaskMirror);
    s->dx=(uint16_t)((s->dx&0xff00u)|0xc4u);          /* MOV DL,C4 */
    s->ax=0x0202u;output(s,SEG143E_VgaMapMaskMirror);
}

static void shifted_second_pass(ShiftedSpriteState *s,unsigned rows) {
    s->bp=(uint16_t)rows;
    do {
        uint8_t shifts;
        lodsw(s);                                      /* LODSW */
        s->ax=(uint16_t)((s->ax<<8)|(s->ax>>8));       /* XCHG AL,AH */
        s->bx=s->ax;                                  /* MOV BX,AX */
        set_ch(s,(uint8_t)s->cx);                     /* MOV CH,CL */
        set_al(s,0u);                                  /* XOR AL,AL */
        s->flags=logic_flags(s->flags,0u,8u);
        s->flags=logic_flags(s->flags,(uint8_t)(s->cx>>8),8u); /* AND CH,CH */
        shifts=(uint8_t)(s->cx>>8);
#if ENTITY_SPRITE_SHIFTED_MUTATION == 4
        if(shifts>7u) {
            shifts=7u;set_ch(s,shifts);
            s->flags=logic_flags(s->flags,shifts,8u);
        }
#endif
        while(shifts!=0u) {
            uint8_t al,old_ch;
            s->flags=shr16_flags(s->flags,s->bx,&s->bx);
            al=(uint8_t)s->ax;s->flags=rcr8_flags(s->flags,al,&al);set_al(s,al);
            old_ch=(uint8_t)(s->cx>>8);set_ch(s,(uint8_t)(old_ch-1u));
            s->flags=dec8_flags(s->flags,old_ch);
            shifts=(uint8_t)(s->cx>>8);
        }
        set_ch(s,(uint8_t)s->ax);                     /* MOV CH,AL */
        s->flags=(uint16_t)(s->flags&~IF);             /* CLI */
        read_unused_vga(s,2u);                         /* MOV AL,[ES:DI] */
        set_al(s,(uint8_t)(s->bx>>8));                /* MOV AL,BH */
        stosb(s);
        read_unused_vga(s,2u);
        set_al(s,(uint8_t)s->bx);                     /* MOV AL,BL */
        stosb(s);
        read_unused_vga(s,2u);
        set_al(s,(uint8_t)(s->cx>>8));                /* MOV AL,CH */
        stosb(s);
        s->flags=(uint16_t)(s->flags|IF);             /* STI */
        {
            uint16_t before=s->di;
            s->di=(uint16_t)(s->di+0x29u);
            s->flags=add16_flags(s->flags,before,0x29u); /* ADD DI,29 */
        }
        {
            uint16_t before=s->bp;
            s->bp=(uint16_t)(s->bp-1u);
            s->flags=dec16_flags(s->flags,before);     /* DEC BP */
        }
    } while(s->bp!=0u);
}

static LmnEntityShiftedSpriteResult draw(uint8_t *memory,
    const LmnEntityShiftedSpriteCall *call,const LmnRasterBus *bus,
    unsigned rows) {
    ShiftedSpriteState s;
    initialize(&s,memory,call,bus,rows);
    push(&s,s.ds);                                     /* PUSH DS */
#if ENTITY_SPRITE_SHIFTED_MUTATION == 3
    s.ds=call->data_segment;
#else
    s.ds=s.cx;                                         /* MOV DS,CX */
#endif
    {
        uint16_t old_dx=s.dx,old_cx=s.cx;
        s.dx=old_cx;s.cx=old_dx;                       /* XCHG DX,CX */
    }
#if ENTITY_SPRITE_SHIFTED_MUTATION == 4
    if((uint8_t)s.cx>7u)s.cx=(uint16_t)((s.cx&0xff00u)|7u);
#endif
    initial_vga_setup(&s);
    push(&s,s.di);                                     /* PUSH DI */
    shifted_first_pass(&s,rows);
    s.di=pop(&s);                                      /* POP DI */
    second_vga_setup(&s);
    shifted_second_pass(&s,rows);
#if ENTITY_SPRITE_SHIFTED_MUTATION == 10
    /* Deliberately leave the live saved DS word on the stack. */
#else
    s.ds=pop(&s);                                      /* POP DS */
#endif
    return result_of(&s);
}

LmnEntityShiftedSpriteResult lmn_draw_entity_shifted_sprite12_core(
    uint8_t *memory,const LmnEntityShiftedSpriteCall *call,
    const LmnRasterBus *bus) {
    return draw(memory,call,bus,12u);
}

LmnEntityShiftedSpriteResult lmn_draw_entity_shifted_sprite13_core(
    uint8_t *memory,const LmnEntityShiftedSpriteCall *call,
    const LmnRasterBus *bus) {
    return draw(memory,call,bus,13u);
}

static void apply_result(LmnRegs *r,const LmnEntityShiftedSpriteResult *out) {
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
        high=bus->read_byte(bus->context,memory,(address+1u)&MEMORY_MASK,flags);
    } else {
        low=memory[address];high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

static uint16_t adapt(uint8_t *memory,LmnRegs *r,const LmnRasterBus *bus,
                      unsigned rows) {
    LmnEntityShiftedSpriteCall call={
        r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,
        r->cs,r->ds,r->es,r->ss,r->sp,r->flags
    };
    LmnEntityShiftedSpriteResult out=draw(memory,&call,bus,rows);
    apply_result(r,&out);
    if(out.status==LMN_ENTITY_SHIFTED_SPRITE_READY) {
        r->ip=read_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

uint16_t lmn_draw_entity_shifted_sprite12_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus) {
    return adapt(memory,registers,bus,12u);
}

uint16_t lmn_draw_entity_shifted_sprite13_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus) {
    return adapt(memory,registers,bus,13u);
}

#include "entity_pattern.h"
#include "lemmings_sym.h"

#ifndef MUTATION
#define MUTATION 0
#endif
#ifndef ENTITY_PATTERN_BUS_MUTATION
#define ENTITY_PATTERN_BUS_MUTATION 0
#endif

enum {
    CF=0x0001u, PF=0x0004u, AF=0x0010u, ZF=0x0040u,
    SF=0x0080u, DF=0x0400u, OF=0x0800u,
    ARITH=0x08d5u
};

typedef struct PatternState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t flags;
} PatternState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}

static const LmnRasterBus *access_bus(const LmnRasterBus *bus) {
#if ENTITY_PATTERN_BUS_MUTATION == 1
    (void)bus;
    return NULL;
#else
    return bus;
#endif
}

static uint8_t read_physical(PatternState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(PatternState *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(PatternState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(PatternState *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* Real-mode word accesses consume the next physical byte, including at
   offset FFFFh and across the 20-bit physical wrap. */
static uint16_t read_word(PatternState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_word(PatternState *s,uint16_t segment,uint16_t offset,
                       uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp16(uint16_t value) {
    unsigned parity=0,bit;
    uint16_t status=0;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    if(!parity)status|=PF;
    if(!value)status|=ZF;
    if(value&0x8000u)status|=SF;
    return status;
}

static uint16_t sub16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint16_t value=(uint16_t)(left-right);
    uint16_t status=szp16(value);
    if(left<right)status|=CF;
    if((left^right^value)&AF)status|=AF;
    if(((left^right)&(left^value)&0x8000u)!=0)status|=OF;
    return (uint16_t)((flags&~ARITH)|status);
}

/* SHR word,1 defines CF/OF/SZP. AF is undefined, so retain its prior opaque
   bit; TF/IF/DF and other control bits are preserved. */
#if MUTATION != 1
static uint16_t shr16_flags(uint16_t flags,uint16_t before) {
    uint16_t value=(uint16_t)(before>>1);
    uint16_t status=szp16(value);
    if(before&1u)status|=CF;
    if(before&0x8000u)status|=OF;
    return (uint16_t)((flags&~(ARITH&~AF))|status);
}
#endif

#if MUTATION == 1
static uint16_t sar16_flags(uint16_t flags,uint16_t before) {
    uint16_t value=(uint16_t)((before>>1)|(before&0x8000u));
    uint16_t status=szp16(value);
    if(before&1u)status|=CF;
    /* SAR clears OF for a one-bit shift; AF is undefined and retained. */
    return (uint16_t)((flags&~(ARITH&~AF))|status);
}
#endif

/* MUL defines only CF/OF. Remaining arithmetic flags stay opaque. */
static uint16_t mul_flags(uint16_t flags,uint32_t product) {
    uint16_t status=(product>>16)?(CF|OF):0u;
    return (uint16_t)((flags&~(CF|OF))|status);
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum,status=szp16(value);
    if(sum>0xffffu)status|=CF;
    if((left^right^value)&AF)status|=AF;
    if((~(left^right)&(left^value)&0x8000u)!=0)status|=OF;
    return (uint16_t)((flags&~ARITH)|status);
}

static void push(PatternState *s,uint16_t ss,uint16_t *sp,uint16_t value) {
    *sp=(uint16_t)(*sp-2u);
    write_word(s,ss,*sp,value,s->flags);
}

static uint16_t pop(PatternState *s,uint16_t ss,uint16_t *sp) {
    uint16_t value=read_word(s,ss,*sp);
    *sp=(uint16_t)(*sp+2u);
    return value;
}

LmnEntityPatternResult lmn_copy_entity_pattern_bus_core(
    uint8_t *memory,const LmnEntityPatternCall *call,
    const LmnRasterBus *bus) {
    PatternState s;
    uint16_t ds=call->data_segment,ss=call->stack_segment;
    uint16_t sp=call->stack_offset,si=call->record_cursor;
    uint16_t ax,bx,dx,es,di;
    uint16_t qx,qy,product;
#if ENTITY_PATTERN_BUS_MUTATION == 3
    uint16_t post_sub_flags;
#endif
    uint16_t step=(call->flags&DF)?0xffffu:1u;
    unsigned row;
    LmnEntityPatternResult out;

    s.memory=memory;s.bus=access_bus(bus);s.flags=call->flags;

    /* MOV AX,[SI]; MOV BX,[SI+2]; SUB AX,4; SUB BX,6; SUB BX,10h. */
    ax=read_word(&s,ds,si);
    bx=read_word(&s,ds,(uint16_t)(si+2u));
    qx=(uint16_t)(ax-4u);
    s.flags=sub16_flags(s.flags,ax,4u);
    qy=(uint16_t)(bx-6u);
    s.flags=sub16_flags(s.flags,bx,6u);
    {
        uint16_t prior=qy;
        qy=(uint16_t)(qy-0x10u);
        s.flags=sub16_flags(s.flags,prior,0x10u);
    }
#if ENTITY_PATTERN_BUS_MUTATION == 3
    post_sub_flags=s.flags;
#endif

    /* Two logical SHR instructions per coordinate, with flags live at each
       subsequent PUSH and through MUL/POP. */
#if MUTATION == 1
    {
        uint16_t prior=qx;
        qx=(uint16_t)((qx>>1)|(qx&0x8000u));
        s.flags=sar16_flags(s.flags,prior);
        prior=qx;qx=(uint16_t)((qx>>1)|(qx&0x8000u));
        s.flags=sar16_flags(s.flags,prior);
        prior=qy;qy=(uint16_t)((qy>>1)|(qy&0x8000u));
        s.flags=sar16_flags(s.flags,prior);
        prior=qy;qy=(uint16_t)((qy>>1)|(qy&0x8000u));
        s.flags=sar16_flags(s.flags,prior);
    }
#else
    {
        uint16_t prior=qx;
        qx=(uint16_t)(qx>>1);
        s.flags=shr16_flags(s.flags,prior);
        prior=qx;qx=(uint16_t)(qx>>1);
        s.flags=shr16_flags(s.flags,prior);
        prior=qy;qy=(uint16_t)(qy>>1);
        s.flags=shr16_flags(s.flags,prior);
        prior=qy;qy=(uint16_t)(qy>>1);
        s.flags=shr16_flags(s.flags,prior);
    }
#endif

    /* PUSH AX; PUSH DX; MOV AX,BX; MOV DX,01A0; MUL DX; POP DX; POP BX. */
    push(&s,ss,&sp,qx);
    push(&s,ss,&sp,call->saved_value);
    ax=qy;
    dx=0x01a0u;
    product=(uint16_t)((uint32_t)ax*dx);
    s.flags=mul_flags(s.flags,(uint32_t)ax*dx);
    dx=(uint16_t)(((uint32_t)ax*0x01a0u)>>16);
    dx=pop(&s,ss,&sp);
    bx=pop(&s,ss,&sp);
    (void)dx; /* DX is returned below as the live popped saved value. */

    /* ADD BX,AX; ADD BX,12h. */
    {
        uint16_t prior=bx;
        bx=(uint16_t)(bx+product);
        s.flags=add_flags(s.flags,prior,product);
        prior=bx;
        bx=(uint16_t)(bx+SEG143E_InteractionCellMapBase);
        s.flags=add_flags(s.flags,prior,SEG143E_InteractionCellMapBase);
    }

    /* PUSH SI/DI/ES/SS; POP ES. Every stack access is live and bus-backed. */
    push(&s,ss,&sp,si);
    push(&s,ss,&sp,call->saved_destination);
    push(&s,ss,&sp,call->saved_segment);
    push(&s,ss,&sp,ss);
    es=pop(&s,ss,&sp);
#if ENTITY_PATTERN_BUS_MUTATION == 2
    /* Mutant still performs the live read but reuses pre-PUSH SS. */
    es=ss;
#endif
    di=bx;

    /* ADD SI,16h. The original's explicit cursor update is flag-defining. */
    {
        uint16_t prior=si;
        si=(uint16_t)(si+0x16u);
        s.flags=add_flags(s.flags,prior,0x16u);
    }
#if MUTATION == 3
    step=1u;
#endif
    for(row=0;row<3u;++row) {
        uint16_t value;
        uint16_t write_flags=s.flags;
#if ENTITY_PATTERN_BUS_MUTATION == 3
        write_flags=post_sub_flags;
#endif
        /* MOVSW reads both source bytes before either destination write. */
        value=read_word(&s,ds,si);
        write_word(&s,es,di,value,write_flags);
        si=(uint16_t)(si+2u*step);
        di=(uint16_t)(di+2u*step);

        /* MOVSB follows the same live DF and flags as MOVSW. */
        {
            uint8_t byte=read8(&s,ds,si);
            write8(&s,es,di,byte,write_flags);
        }
        si=(uint16_t)(si+step);
        di=(uint16_t)(di+step);
        if(row<2u) {
            uint16_t prior=di;
            di=(uint16_t)(di+0x019du);
#if MUTATION == 2
            s.flags=add_flags(s.flags,prior,0x019du);
            di=(uint16_t)(prior+0x019eu);
#else
            s.flags=add_flags(s.flags,prior,0x019du);
#endif
        }
    }

    /* POP ES/DI/SI all consume the live SS saves after possible overlap. */
    out.restored_segment=pop(&s,ss,&sp);
    out.restored_destination=pop(&s,ss,&sp);
    out.record_cursor=pop(&s,ss,&sp);
    out.product=product;
    out.map_offset=bx;
    out.restored_value=dx;
    out.stack_offset=sp;
    out.flags=s.flags;
    return out;
}

LmnEntityPatternResult lmn_copy_entity_pattern_core(
    uint8_t *memory,const LmnEntityPatternCall *call) {
    return lmn_copy_entity_pattern_bus_core(memory,call,NULL);
}

static uint16_t read_return(uint8_t *memory,uint16_t ss,uint16_t sp,
                            uint16_t flags,const LmnRasterBus *bus) {
    PatternState s;
    s.memory=memory;s.bus=access_bus(bus);s.flags=flags;
    return read_word(&s,ss,sp);
}

void lmn_copy_entity_pattern_bus_adapter(uint8_t *memory,LmnRegs *r,
    const LmnRasterBus *bus) {
    LmnEntityPatternCall call={r->ds,r->ss,r->sp,r->si,r->di,
                               r->dx,r->es,r->flags};
    LmnEntityPatternResult out;
#if MUTATION == 4 || ENTITY_PATTERN_BUS_MUTATION == 4
    uint16_t target;
#endif
    const LmnRasterBus *bus_for_access=access_bus(bus);

#if MUTATION == 4 || ENTITY_PATTERN_BUS_MUTATION == 4
    target=read_return(memory,r->ss,r->sp,r->flags,bus_for_access);
#endif
    out=lmn_copy_entity_pattern_bus_core(memory,&call,bus);
    r->ax=out.product;
    r->bx=out.map_offset;
    r->dx=out.restored_value;
    r->si=out.record_cursor;
    r->di=out.restored_destination;
    r->es=out.restored_segment;
    r->sp=out.stack_offset;
    r->flags=out.flags;
#if MUTATION == 4 || ENTITY_PATTERN_BUS_MUTATION == 4
    r->ip=target;
    r->sp=(uint16_t)(r->sp+2u);
#else
    r->ip=read_return(memory,r->ss,r->sp,r->flags,bus_for_access);
    r->sp=(uint16_t)(r->sp+2u);
#endif
}

void lmn_copy_entity_pattern_adapter(uint8_t *memory,LmnRegs *regs) {
    lmn_copy_entity_pattern_bus_adapter(memory,regs,NULL);
}

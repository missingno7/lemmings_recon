#include "status_icons.h"
#include "lemmings_sym.h"

#ifndef STATUS_ICONS_MUTATION
#define STATUS_ICONS_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct StatusIconState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
    uint16_t pushed_di;
} StatusIconState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(StatusIconState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(StatusIconState *s,uint32_t address,uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(StatusIconState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(StatusIconState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(StatusIconState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(StatusIconState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static uint16_t szp8(uint8_t value) {
    unsigned parity=0,bit;
    uint16_t out=0;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x80u)out|=SF;
    return out;
}

static uint16_t szp16(uint16_t value) {
    uint16_t out=0;
    unsigned parity=0,bit;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

/* XOR/logic leaves AF undefined; preserve it for a stable bus observation. */
static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    return (uint16_t)((flags&~LOGIC)|szp8(value));
}

static uint16_t logic16_flags(uint16_t flags,uint16_t value) {
    return (uint16_t)((flags&~LOGIC)|szp16(value));
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t l=left&mask,r=right&mask,sum=l+r;
    uint16_t value=(uint16_t)(sum&mask);
    uint16_t out=(bits==8u)?szp8((uint8_t)value):szp16(value);
    uint32_t sign=1u<<(bits-1u);
    if(sum>mask)out|=CF;
    if((l^r^value)&AF)out|=AF;
    if((~(l^r)&(l^value)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t sub_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint16_t l=(uint16_t)(left&mask),r=(uint16_t)(right&mask);
    uint16_t value=(uint16_t)((l-r)&mask);
    uint16_t out=(bits==8u)?szp8((uint8_t)value):szp16(value);
    uint32_t sign=1u<<(bits-1u);
    if(l<r)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if(((left^right)&(left^value)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint8_t al(const StatusIconState *s) {
    return (uint8_t)s->ax;
}

static void set_al(StatusIconState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(StatusIconState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void add_di(StatusIconState *s,uint16_t amount) {
    uint16_t before=s->di;
    s->di=(uint16_t)(before+amount);
    s->flags=add_flags(s->flags,before,amount,16u);
}

static void add_si(StatusIconState *s,uint16_t amount) {
    uint16_t before=s->si;
    s->si=(uint16_t)(before+amount);
    s->flags=add_flags(s->flags,before,amount,16u);
}

static void port_word(StatusIconState *s) {
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
}

static void mirror_and_out(StatusIconState *s,uint16_t offset) {
#if STATUS_ICONS_MUTATION == 7
    /* Mutation: the VGA port sees the value before its live SS mirror. */
    port_word(s);
    write16(s,s->ss,offset,s->ax);
#else
    write16(s,s->ss,offset,s->ax);
    port_word(s);
#endif
}

static void stosb(StatusIconState *s) {
    uint16_t before=s->di;
    write8(s,s->es,before,al(s));
    if(s->flags&DF)s->di=(uint16_t)(before-1u);
    else s->di=(uint16_t)(before+1u);
}

static void movsb(StatusIconState *s) {
    uint16_t src=s->si,dst=s->di;
    uint8_t value=read8(s,s->ds,src);
    write8(s,s->es,dst,value);
#if STATUS_ICONS_MUTATION == 5
    s->si=(uint16_t)(src+1u);
    s->di=(uint16_t)(dst+1u);
#else
    if(s->flags&DF) {
        s->si=(uint16_t)(src-1u);
        s->di=(uint16_t)(dst-1u);
    } else {
        s->si=(uint16_t)(src+1u);
        s->di=(uint16_t)(dst+1u);
    }
#endif
}

static void push_word(StatusIconState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop_word(StatusIconState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static LmnStatusIconsResult result_of(const StatusIconState *s) {
    LmnStatusIconsResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void initialize(StatusIconState *s,uint8_t *memory,
                       const LmnStatusIconsCall *call,
                       const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=0;s->status=LMN_STATUS_ICONS_READY;
    s->pushed_di=0;
}

LmnStatusIconsResult lmn_draw_status_icon_outline_core(uint8_t *memory,
    const LmnStatusIconsCall *call,const LmnRasterBus *bus) {
    StatusIconState s;
    uint16_t origin;
    unsigned row;
    initialize(&s,memory,call,bus);

    /* 780D..7857: zero-extend AL, derive the first VGA byte and select planes. */
    set_ah(&s,0u);                                      /* XOR AH,AH */
    s.flags=logic8_flags(s.flags,0u);
    s.ax=(uint16_t)(al(&s)*2u);                         /* ADD AX,AX */
    s.flags=add_flags(s.flags,(uint16_t)(s.ax/2u),
                      (uint16_t)(s.ax/2u),16u);
    s.di=s.ax;                                         /* MOV DI,AX */
    add_di(&s,0x2100u);
    origin=read16(&s,s.ds,SEG09A9_DrawingOrigin);
    add_di(&s,origin);                                 /* live origin read */
    add_di(&s,0x0002u);
    s.dx=0xa000u;s.es=s.dx;
    s.dx=0x03c4u;s.ax=0x0f02u;
    mirror_and_out(&s,0x0008u);
    s.dx=0x03ceu;
    s.ax=0;
    s.flags=logic16_flags(s.flags,s.ax);                /* XOR AX,AX */
    mirror_and_out(&s,0x000au);
    s.ax=0x0c01u;mirror_and_out(&s,0x000cu);
    s.ax=0x0005u;mirror_and_out(&s,0x0000u);
    s.ax=0x0003u;mirror_and_out(&s,0x0002u);
    s.ax=0xff08u;mirror_and_out(&s,0x000eu);

    s.flags=(uint16_t)(s.flags&~IF);                   /* CLI */
    set_al(&s,0xffu);
    set_ah(&s,read8(&s,s.es,s.di));                    /* latch read */
    stosb(&s);
    set_ah(&s,read8(&s,s.es,s.di));                    /* latch read */
    stosb(&s);
    add_di(&s,0x002au);
    s.cx=0x0016u;
    for(row=0;row<0x16u;++row) {
        s.ax=0x8008u;mirror_and_out(&s,0x000eu);
        set_ah(&s,read8(&s,s.es,s.di));
        set_al(&s,0x80u);stosb(&s);
        s.ax=0x0108u;mirror_and_out(&s,0x000eu);
        set_ah(&s,read8(&s,s.es,s.di));
        set_al(&s,0x01u);stosb(&s);
        add_di(&s,0x002au);
        s.cx=(uint16_t)(s.cx-1u);                     /* LOOP preserves FLAGS */
    }
    s.ax=0xff08u;mirror_and_out(&s,0x000eu);
    set_al(&s,0xffu);
    set_ah(&s,read8(&s,s.es,s.di));
    stosb(&s);
    set_ah(&s,read8(&s,s.es,s.di));
    stosb(&s);
#if STATUS_ICONS_MUTATION == 8
    set_ah(&s,0u);                                     /* Drop final latch AH. */
#endif
    s.flags=(uint16_t)(s.flags|IF);                    /* STI */
    s.continuation=CS_StatusIconOutlineReturn;
    s.status=LMN_STATUS_ICONS_READY;
    return result_of(&s);
}

LmnStatusIconsResult lmn_restore_status_icon_core(uint8_t *memory,
    const LmnStatusIconsCall *call,const LmnRasterBus *bus) {
    StatusIconState s;
    uint8_t value;
    uint16_t offset,origin;
    unsigned row,rows=0x18u;
    initialize(&s,memory,call,bus);

    /* 789E..78B3: JNL is signed; negative AL values take the reset write. */
    value=al(&s);
    s.flags=sub_flags(s.flags,value,0x0au,8u);
#if STATUS_ICONS_MUTATION == 1
    if(value>=0x0au)goto copy_setup;                    /* unsigned JNL */
#else
    if(((s.flags&SF)!=0u)==((s.flags&OF)!=0u))goto copy_setup;
#endif

    /* BL arithmetic wraps at eight bits before BH is cleared. */
    s.bx=(uint16_t)((s.bx&0xff00u)|value);
    value=(uint8_t)(s.bx&0xffu);
    s.bx=(uint16_t)((s.bx&0xff00u)|(uint8_t)(value+value));
    s.flags=add_flags(s.flags,value,value,8u);
    value=al(&s);
    {
        uint8_t bl=(uint8_t)s.bx;
        s.bx=(uint16_t)((s.bx&0xff00u)|(uint8_t)(bl+value));
        s.flags=add_flags(s.flags,bl,value,8u);
    }
#if STATUS_ICONS_MUTATION != 2
    s.bx=(uint16_t)(s.bx&0x00ffu);                     /* XOR BH,BH */
    s.flags=logic8_flags(s.flags,0u);
#endif
    {
        uint16_t before=s.bx;
        s.bx=(uint16_t)(before+0x0064u);
        s.flags=add_flags(s.flags,before,0x0064u,16u);
    }
    offset=(uint16_t)(s.bx+1u);
    write16(&s,s.ds,offset,0u);                        /* MOV [DS:BX+1],0 */

copy_setup:
    push_word(&s,s.ds);                               /* PUSH DS */
    set_ah(&s,0u);                                    /* XOR AH,AH */
    s.flags=logic8_flags(s.flags,0u);
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(before+before);                /* ADD AX,AX */
        s.flags=add_flags(s.flags,before,before,16u);
    }
    s.di=s.ax;                                        /* MOV DI,AX */
    s.pushed_di=s.di;
    push_word(&s,s.di);                               /* PUSH DI */
    add_di(&s,0x2100u);
    origin=read16(&s,s.ds,SEG09A9_DrawingOrigin);
    add_di(&s,origin);
    add_di(&s,0x0002u);
    s.dx=0xa000u;s.es=s.dx;
    s.dx=0x03c4u;s.ax=0x0f02u;
    mirror_and_out(&s,0x0008u);
    s.dx=0x03ceu;s.ax=0x0105u;
    mirror_and_out(&s,0x0000u);

    s.si=pop_word(&s);                                /* POP SI, live SS read */
#if STATUS_ICONS_MUTATION == 3
    s.si=s.pushed_di;                                 /* Ignore overwritten POP. */
#endif
    add_si(&s,0x02c0u);
    add_si(&s,0xf91fu);
    s.dx=0xa000u;s.es=s.dx;
#if STATUS_ICONS_MUTATION != 4
    s.ds=s.dx;                                        /* MOV DS,DX */
#endif
    s.cx=0x0018u;
#if STATUS_ICONS_MUTATION == 6
    rows=0x17u;
#endif
    for(row=0;row<rows;++row) {
        movsb(&s);
        movsb(&s);
        add_di(&s,0x002au);
        add_si(&s,0x002au);
        s.cx=(uint16_t)(s.cx-1u);                     /* LOOP preserves FLAGS */
    }
    s.ds=pop_word(&s);                                /* POP DS from live SS */
    s.continuation=CS_StatusIconRestoreReturn;
    s.status=LMN_STATUS_ICONS_READY;
    return result_of(&s);
}

static void apply_result(LmnRegs *registers,const LmnStatusIconsResult *out) {
    registers->ax=out->value;registers->bx=out->map_cursor;
    registers->cx=out->count;registers->dx=out->auxiliary_value;
    registers->si=out->record_cursor;registers->di=out->object_cursor;
    registers->bp=out->candidate_y;registers->cs=out->code_segment;
    registers->ds=out->data_segment;registers->es=out->extra_segment;
    registers->ss=out->stack_segment;registers->sp=out->stack_offset;
    registers->flags=out->flags;registers->ip=out->continuation;
}

static uint16_t read_stack_return(uint8_t *memory,uint16_t stack_segment,
    uint16_t stack_offset,uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(stack_segment,stack_offset);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,
                            (address+1u)&MEMORY_MASK,flags);
    } else {
        low=memory[address];
        high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

static uint16_t adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus,
    LmnStatusIconsResult (*core)(uint8_t *,const LmnStatusIconsCall *,
                                const LmnRasterBus *)) {
    LmnStatusIconsCall call;
    LmnStatusIconsResult out;
    call.value=registers->ax;call.map_cursor=registers->bx;
    call.count=registers->cx;call.auxiliary_value=registers->dx;
    call.record_cursor=registers->si;call.object_cursor=registers->di;
    call.candidate_y=registers->bp;call.code_segment=registers->cs;
    call.data_segment=registers->ds;call.extra_segment=registers->es;
    call.stack_segment=registers->ss;call.stack_offset=registers->sp;
    call.flags=registers->flags;
    out=core(memory,&call,bus);
    apply_result(registers,&out);
    if(out.status==LMN_STATUS_ICONS_READY) {
#if STATUS_ICONS_MUTATION == 9
        (void)read_stack_return(memory,registers->ss,registers->sp,
                                registers->flags,bus);
        registers->ip=out.continuation;
#else
        registers->ip=read_stack_return(memory,registers->ss,registers->sp,
                                        registers->flags,bus);
#endif
        registers->sp=(uint16_t)(registers->sp+2u);
    }
    return out.status;
}

uint16_t lmn_draw_status_icon_outline_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus) {
    return adapter(memory,registers,bus,lmn_draw_status_icon_outline_core);
}

uint16_t lmn_restore_status_icon_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus) {
    return adapter(memory,registers,bus,lmn_restore_status_icon_core);
}

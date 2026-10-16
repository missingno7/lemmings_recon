#include "status_copy.h"

#include "lemmings_sym.h"

#ifndef STATUS_COPY_MUTATION
#define STATUS_COPY_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF
};

typedef struct StatusCopyState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
} StatusCopyState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(StatusCopyState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(StatusCopyState *s,uint32_t address,uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(StatusCopyState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(StatusCopyState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(StatusCopyState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(StatusCopyState *s,uint16_t segment,uint16_t offset,
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

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)wide,out=szp16(result);
    if(wide>0xffffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static void add_di(StatusCopyState *s,uint16_t amount) {
    uint16_t before=s->di;
    s->di=(uint16_t)(before+amount);
    s->flags=add16_flags(s->flags,before,amount);
}

static void push16(StatusCopyState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop16(StatusCopyState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void copy_bytes(StatusCopyState *s) {
#if STATUS_COPY_MUTATION == 2
    uint16_t saved_ds=s->ds;
#endif
#if STATUS_COPY_MUTATION == 3
    unsigned index;
#endif
    push16(s,s->ds);                                  /* PUSH DS */
    s->dx=0x03c4u;
    s->ax=0x0f02u;
    write16(s,s->ss,0x0008u,s->ax);                  /* SS:0008 mirror */
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
    s->dx=0x03ceu;
    s->ax=0x0105u;
    write16(s,s->ss,0x0000u,s->ax);                  /* SS:0000 mirror */
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
    s->si=0xf91fu;
    s->dx=0xa000u;
    s->es=s->dx;
    s->ds=s->dx;
#if STATUS_COPY_MUTATION == 7
    s->cx=0x06dfu;
#else
    s->cx=0x06e0u;
#endif

#if STATUS_COPY_MUTATION == 3
    {
        uint8_t snapshot[0x06e0];
        uint16_t source=s->si,destination=s->di;
        uint16_t remaining=s->cx;
        for(index=0u;index<remaining;++index) {
            snapshot[index]=read8(s,s->ds,source);
#if STATUS_COPY_MUTATION == 1
            source=(uint16_t)(source+1u);
#else
            source=(uint16_t)(source+((s->flags&0x0400u)?-1:1));
#endif
        }
        remaining=s->cx;
        for(index=0u;index<remaining;++index) {
            write8(s,s->es,destination,snapshot[index]);
#if STATUS_COPY_MUTATION == 1
            destination=(uint16_t)(destination+1u);
#else
            destination=(uint16_t)(destination+((s->flags&0x0400u)?-1:1));
#endif
        }
        s->si=source;s->di=destination;s->cx=0u;
    }
#else
    while(s->cx!=0u) {
        uint8_t value=read8(s,s->ds,s->si);
        write8(s,s->es,s->di,value);
#if STATUS_COPY_MUTATION == 1
        s->si=(uint16_t)(s->si+1u);
        s->di=(uint16_t)(s->di+1u);
#else
        if(s->flags&0x0400u) {
            s->si=(uint16_t)(s->si-1u);
            s->di=(uint16_t)(s->di-1u);
        } else {
            s->si=(uint16_t)(s->si+1u);
            s->di=(uint16_t)(s->di+1u);
        }
#endif
        s->cx=(uint16_t)(s->cx-1u);
    }
#endif
    {
        uint16_t popped_ds=pop16(s);                  /* POP DS */
#if STATUS_COPY_MUTATION == 2
        (void)popped_ds;
        s->ds=saved_ds;
#else
        s->ds=popped_ds;
#endif
    }
    s->continuation=CS_StatusCopyReturn;
}

static void initialize(StatusCopyState *s,uint8_t *memory,
    const LmnStatusCopyCall *call,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->status=LMN_STATUS_COPY_READY;
}

static LmnStatusCopyResult result_of(const StatusCopyState *s) {
    LmnStatusCopyResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

LmnStatusCopyResult lmn_copy_status_region_to_vga_core(uint8_t *memory,
    const LmnStatusCopyCall *call,const LmnRasterBus *bus) {
    StatusCopyState s;
    initialize(&s,memory,call,bus);
    copy_bytes(&s);
    return result_of(&s);
}

LmnStatusCopyResult lmn_copy_status_region_to_both_origins_core(
    uint8_t *memory,const LmnStatusCopyCall *call,const LmnRasterBus *bus) {
    StatusCopyState s;
    uint16_t first_child_return;
#if STATUS_COPY_MUTATION == 5
    uint16_t cached_alternate_origin;
#endif
    initialize(&s,memory,call,bus);
    s.di=read16(&s,s.ds,SEG09A9_DrawingOrigin);     /* MOV DI,[DrawingOrigin] */
    add_di(&s,0x1e42u);                              /* ADD DI,1E42 */
#if STATUS_COPY_MUTATION == 5
    cached_alternate_origin=read16(&s,s.ds,
        SEG09A9_AlternateDrawingOrigin);
#endif
    push16(&s,CS_StatusCopyAfterFirst);              /* CALL 7602 */
    copy_bytes(&s);
    first_child_return=pop16(&s);                    /* actual child RET */
    if(first_child_return!=CS_StatusCopyAfterFirst) {
#if STATUS_COPY_MUTATION != 6
        s.status=LMN_STATUS_COPY_CHANGED_CHILD_RETURN;
        s.continuation=first_child_return;
        return result_of(&s);
#endif
    }
    s.di=read16(&s,s.ds,SEG09A9_AlternateDrawingOrigin);
#if STATUS_COPY_MUTATION == 5
    s.di=cached_alternate_origin;
#endif
    add_di(&s,0x1e42u);                              /* ADD DI,1E42 */
#if STATUS_COPY_MUTATION == 4
    push16(&s,CS_StatusCopyReturn);                  /* fake second CALL */
#endif
    copy_bytes(&s);                                  /* fall through to 7602 */
#if STATUS_COPY_MUTATION == 4
    (void)pop16(&s);                                 /* fake child RET */
#endif
    s.continuation=CS_StatusCopyReturn;
    return result_of(&s);
}

static void apply_result(LmnRegs *r,const LmnStatusCopyResult *out) {
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

typedef LmnStatusCopyResult (*StatusCopyCore)(uint8_t *,
    const LmnStatusCopyCall *,const LmnRasterBus *);

static uint16_t adapter(uint8_t *memory,LmnRegs *r,const LmnRasterBus *bus,
                        StatusCopyCore core) {
    LmnStatusCopyCall call;
    LmnStatusCopyResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_STATUS_COPY_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

uint16_t lmn_copy_status_region_to_vga_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    return adapter(memory,r,bus,lmn_copy_status_region_to_vga_core);
}

uint16_t lmn_copy_status_region_to_both_origins_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    return adapter(memory,r,bus,lmn_copy_status_region_to_both_origins_core);
}

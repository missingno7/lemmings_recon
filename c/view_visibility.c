#include "view_visibility.h"

#include "lemmings_sym.h"

#ifndef VIEW_VISIBILITY_MUTATION
#define VIEW_VISIBILITY_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|AF|ZF|SF|OF
};

typedef struct ViewVisibilityState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t runtime_stack_segment;
    uint16_t continuation,status;
} ViewVisibilityState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(ViewVisibilityState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(ViewVisibilityState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static void write8(ViewVisibilityState *s,uint16_t segment,
                   uint16_t offset,uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(ViewVisibilityState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ViewVisibilityState *s,uint16_t segment,
                    uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

#if VIEW_VISIBILITY_MUTATION != 6
static uint16_t read_code_operand16(const ViewVisibilityState *s,
                                    uint16_t offset) {
    uint32_t address=physical(s->cs,offset);
    uint8_t low=s->memory[address];
    uint8_t high=s->memory[(address+1u)&MEMORY_MASK];
    return (uint16_t)(low|((uint16_t)high<<8));
}
#endif

static uint16_t szp16(uint16_t value) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0u;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

static uint16_t xor16_flags(uint16_t flags,uint16_t result) {
    /* AF is undefined after XOR; use zero as the boundary representative. */
    return (uint16_t)((flags&~LOGIC)|szp16(result));
}

static uint16_t shr16_one_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before>>1);
    uint16_t out=szp16(result);
    if(before&1u)out|=CF;
    if(before&0x8000u)out|=OF;
    /* AF is undefined after SHR and remains at its prior representative. */
    return (uint16_t)((flags&~(CF|PF|ZF|SF|OF))|out);
}

static uint16_t dec16_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before-1u);
    uint16_t out=szp16(result);
    if((before&0x000fu)==0u)out|=AF;
    if(before==0x8000u)out|=OF;
    return (uint16_t)((flags&~(PF|AF|ZF|SF|OF))|out);
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)wide,out=szp16(result);
    if(wide>0xffffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

#if VIEW_VISIBILITY_MUTATION != 7
static void push_word(ViewVisibilityState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop_word(ViewVisibilityState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}
#endif

static void stosw_repeat(ViewVisibilityState *s,uint16_t count) {
    uint16_t i;
    int direction=(s->flags&DF)?-2:2;
#if VIEW_VISIBILITY_MUTATION == 1
    /* Fault forces the initial clear to advance forward despite DF. */
    direction=2;
#endif
    for(i=0u;i<count;++i) {
        write16(s,s->es,s->di,s->ax);
        s->di=(uint16_t)(s->di+direction);
    }
    s->cx=0u;
}

static void stosb_repeat(ViewVisibilityState *s,uint16_t count) {
    uint16_t i;
    int direction=(s->flags&DF)?-1:1;
    uint8_t value=(uint8_t)s->ax;
    for(i=0u;i<count;++i) {
        write8(s,s->es,s->di,value);
        s->di=(uint16_t)(s->di+direction);
    }
    s->cx=0u;
}

static void initialize_state(ViewVisibilityState *s,uint8_t *memory,
    const LmnViewVisibilityCall *call,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->runtime_stack_segment=call->runtime_stack_segment;
    s->continuation=CS_RebuildViewVisibilityMap;
    s->status=LMN_VIEW_VISIBILITY_READY;
}

static LmnViewVisibilityResult result_of(const ViewVisibilityState *s) {
    LmnViewVisibilityResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

static LmnViewVisibilityResult run_view_visibility_map(
    uint8_t *memory,const LmnViewVisibilityCall *call,
    const LmnRasterBus *bus,int live_operand) {
    ViewVisibilityState s;
    uint16_t map_offset;
#if VIEW_VISIBILITY_MUTATION == 2
    uint16_t early_map_offset;
#endif
#if VIEW_VISIBILITY_MUTATION == 8
    uint16_t early_second_map_offset;
#endif
    unsigned shift_count=3u,dec_count=2u;
    initialize_state(&s,memory,call,bus);

#if VIEW_VISIBILITY_MUTATION == 2
    /* Fault reads the later live DS:0000 source before the clear. */
    early_map_offset=read16(&s,s.ds,SEG09A9_LevelViewOriginPixels);
#endif
#if VIEW_VISIBILITY_MUTATION == 7
    /* Fault bypasses PUSH DS/POP ES and their live stack aliasing. */
    s.es=s.ds;
#else
    push_word(&s,s.ds);                                /* PUSH DS */
    s.es=pop_word(&s);                                 /* POP ES */
#endif
    s.ax=0u;                                           /* XOR AX,AX */
    s.flags=xor16_flags(s.flags,s.ax);
    s.di=SEG09A9_ViewVisibilityMapBase;                 /* MOV DI,0EA8 */
    s.cx=0x0068u;                                     /* MOV CX,68 */
    stosw_repeat(&s,0x0068u);                          /* REP STOSW */

#if VIEW_VISIBILITY_MUTATION == 2
    map_offset=early_map_offset;
#else
    map_offset=read16(&s,s.ds,SEG09A9_LevelViewOriginPixels);                /* MOV DI,[DS:0000] */
#endif
    s.di=map_offset;
    for(unsigned i=0u;i<shift_count;++i) {
#if VIEW_VISIBILITY_MUTATION == 3
        if(i==shift_count-1u)continue;
#endif
        {
            uint16_t before=s.di;
            s.di=(uint16_t)(before>>1);
            s.flags=shr16_one_flags(s.flags,before);
        }
    }
#if VIEW_VISIBILITY_MUTATION == 4
    dec_count=1u;
#endif
    for(unsigned i=0u;i<dec_count;++i) {
        uint16_t before=s.di;
        s.di=(uint16_t)(before-1u);
        s.flags=dec16_flags(s.flags,before);
    }
    {
        uint16_t before=s.di;
        s.di=(uint16_t)(before+SEG09A9_ViewVisibilityMapBase);
        s.flags=add16_flags(s.flags,before,
            SEG09A9_ViewVisibilityMapBase);             /* ADD DI,0EA8 */
    }
    s.cx=0x0029u;                                     /* MOV CX,29 */
    s.ax=0x0101u;                                     /* MOV AX,0101 */
    stosb_repeat(&s,0x0029u);                          /* REP STOSB */

#if VIEW_VISIBILITY_MUTATION != 5
    s.flags=(uint16_t)(s.flags&~IF);                  /* CLI */
#endif
    s.ax=s.es;                                         /* MOV AX,ES */
#if VIEW_VISIBILITY_MUTATION == 6
    (void)live_operand;
    s.cx=s.ss;
#else
    if(live_operand)
        s.cx=read_code_operand16(&s,CS_ViewVisibilityStackSegmentOperand);
    else
        s.cx=s.runtime_stack_segment;                 /* MOV CX,[operand 4137] */
#endif
    s.es=s.cx;                                         /* MOV ES,CX */
    s.bx=read16(&s,s.ds,SEG09A9_DrawingDirtyCellMapOffset);
#if VIEW_VISIBILITY_MUTATION == 8
    early_second_map_offset=read16(&s,s.ds,
        SEG09A9_AlternateDrawingDirtyCellMapOffset);
#endif
    write8(&s,s.es,s.bx,0xffu);                       /* MOV ES:[BX],FF */
#if VIEW_VISIBILITY_MUTATION == 8
    s.bx=early_second_map_offset;
#else
    s.bx=read16(&s,s.ds,
        SEG09A9_AlternateDrawingDirtyCellMapOffset);    /* MOV BX,[DS:0028] */
#endif
    write8(&s,s.es,s.bx,0xffu);                       /* MOV ES:[BX],FF */
    s.es=s.ax;                                         /* MOV ES,AX */
    s.flags=(uint16_t)(s.flags|IF);                    /* STI */
    s.continuation=CS_ViewVisibilityReturn;
    return result_of(&s);
}

LmnViewVisibilityResult lmn_rebuild_view_visibility_map_core(
    uint8_t *memory,const LmnViewVisibilityCall *call,
    const LmnRasterBus *bus) {
    return run_view_visibility_map(memory,call,bus,0);
}

static void apply_result(LmnRegs *r,const LmnViewVisibilityResult *out) {
    r->ax=out->value;r->bx=out->map_cursor;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->record_cursor;
    r->di=out->object_cursor;r->bp=out->candidate_y;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;r->ip=out->continuation;
}

static uint16_t read_stack_return(uint8_t *memory,uint16_t ss,uint16_t sp,
    uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(ss,sp);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,(address+1u)&MEMORY_MASK,flags);
    } else {
        low=memory[address];
        high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

static uint16_t run_view_visibility_map_adapter(uint8_t *memory,
    LmnRegs *r,uint16_t runtime_stack_segment,int live_operand,
    const LmnRasterBus *bus) {
    LmnViewVisibilityCall call;
    LmnViewVisibilityResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    call.runtime_stack_segment=runtime_stack_segment;
    out=run_view_visibility_map(memory,&call,bus,live_operand);
    apply_result(r,&out);
    if(out.status==LMN_VIEW_VISIBILITY_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

uint16_t lmn_rebuild_view_visibility_map_adapter(uint8_t *memory,
    LmnRegs *r,uint16_t runtime_stack_segment,const LmnRasterBus *bus) {
    return run_view_visibility_map_adapter(memory,r,runtime_stack_segment,
                                           0,bus);
}

uint16_t lmn_rebuild_view_visibility_map_live_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    return run_view_visibility_map_adapter(memory,r,0,1,bus);
}

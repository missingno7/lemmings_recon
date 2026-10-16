#include "entity_drawing.h"

#include "decimal_field.h"
#include "entity_dirty.h"
#include "entity_minimap.h"
#include "entity_points.h"
#include "entity_sprite_dispatch.h"
#include "lemmings_sym.h"

#ifndef ENTITY_DRAWING_MUTATION
#define ENTITY_DRAWING_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffff,
    CF = 0x0001,
    PF = 0x0004,
    AF = 0x0010,
    ZF = 0x0040,
    SF = 0x0080,
    OF = 0x0800,
    ARITH = CF | PF | AF | ZF | SF | OF,
    INC_FLAGS = PF | AF | ZF | SF | OF,
    LOGIC_FLAGS = CF | PF | ZF | SF | OF
};

typedef struct EntityDrawingState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status,child_entry,child_status;
#if ENTITY_DRAWING_MUTATION == 5 || ENTITY_DRAWING_MUTATION == 6
    uint16_t iteration_di,iteration_cx;
#endif
} EntityDrawingState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment << 4) + offset) & MEMORY_MASK);
}

static uint8_t read_physical(EntityDrawingState *s,uint32_t address) {
    address &= MEMORY_MASK;
    if(s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(EntityDrawingState *s,uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if(s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address] = value;
}

static uint8_t read8(EntityDrawingState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(EntityDrawingState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(EntityDrawingState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(EntityDrawingState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static void push16(EntityDrawingState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop16(EntityDrawingState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static unsigned even_parity(uint8_t value) {
    unsigned ones=0u,bit;
    for(bit=0u;bit<8u;++bit)ones+=(value>>bit)&1u;
    return (ones&1u)==0u;
}

static uint16_t szp8(uint8_t value) {
    uint16_t out=0u;
    if(even_parity(value))out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x80u)out|=SF;
    return out;
}

static uint16_t szp16(uint16_t value) {
    uint16_t out=0u;
    if(even_parity((uint8_t)value))out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    return (uint16_t)((flags&~LOGIC_FLAGS)|szp8(value));
}

static uint16_t sub8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t result=(uint8_t)(left-right);
    uint16_t out=szp8(result);
    if(left<right)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
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

#if ENTITY_DRAWING_MUTATION != 3
static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before+1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0x0fu)out|=AF;
    if(before==0x7fu)out|=OF;
    return (uint16_t)((flags&~INC_FLAGS)|out);
}
#endif

static uint16_t replace_low(uint16_t value,uint8_t low) {
    return (uint16_t)((value&0xff00u)|low);
}

static void state_from_call(EntityDrawingState *s,uint8_t *memory,
                            const LmnEntityDrawingCall *call,
                            const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=CS_DrawEntityRecords;
    s->status=LMN_ENTITY_DRAWING_READY;
    s->child_entry=0u;s->child_status=0xffffu;
}

static LmnEntityDrawingResult result_of(const EntityDrawingState *s) {
    LmnEntityDrawingResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    out.child_entry=s->child_entry;out.child_status=s->child_status;
    return out;
}

static void state_from_regs(EntityDrawingState *s,const LmnRegs *r) {
    s->ax=r->ax;s->bx=r->bx;s->cx=r->cx;s->dx=r->dx;
    s->si=r->si;s->di=r->di;s->bp=r->bp;
    s->cs=r->cs;s->ds=r->ds;s->es=r->es;s->ss=r->ss;
    s->sp=r->sp;s->flags=r->flags;
    s->continuation=r->ip;
}

static void regs_from_state(const EntityDrawingState *s,LmnRegs *r) {
    r->ax=s->ax;r->bx=s->bx;r->cx=s->cx;r->dx=s->dx;
    r->si=s->si;r->di=s->di;r->bp=s->bp;
    r->cs=s->cs;r->ds=s->ds;r->es=s->es;r->ss=s->ss;
    r->sp=s->sp;r->flags=s->flags;r->ip=s->continuation;
}

typedef uint16_t (*ChildAdapter)(uint8_t *,LmnRegs *,const LmnRasterBus *);

static int invoke_child(EntityDrawingState *s,uint16_t entry,
                        uint16_t expected_return,ChildAdapter adapter) {
    LmnRegs registers;
    uint16_t saved_cs=s->cs,child_status;

    push16(s,expected_return);
    regs_from_state(s,&registers);
    registers.ip=entry;
    child_status=adapter(s->memory,&registers,s->bus);
    state_from_regs(s,&registers);

    if(child_status!=0u) {
        s->child_entry=entry;s->child_status=child_status;
        s->status=LMN_ENTITY_DRAWING_CHILD_STOP;
        return 0;
    }
    if(s->cs!=saved_cs || s->continuation!=expected_return) {
#if ENTITY_DRAWING_MUTATION == 8
        /* Mutation: hide a changed child RET and follow the assumed return. */
        s->cs=saved_cs;s->continuation=expected_return;
#else
        s->child_entry=entry;s->child_status=child_status;
        s->status=LMN_ENTITY_DRAWING_CHANGED_CHILD_RETURN;
        return 0;
#endif
    }
    return 1;
}

static void set_al(EntityDrawingState *s,uint8_t value) {
    s->ax=replace_low(s->ax,value);
}

static int call_minimap(EntityDrawingState *s) {
    return invoke_child(s,CS_DrawEntityMinimapPixel,
        CS_EntityDrawingAfterMinimap,
        lmn_draw_entity_minimap_pixel_adapter);
}

static int call_dirty(EntityDrawingState *s) {
    return invoke_child(s,CS_MarkEntityDrawingDirty,
        CS_EntityDrawingAfterDirty,
        lmn_mark_entity_drawing_dirty_adapter);
}

static int call_points(EntityDrawingState *s) {
    return invoke_child(s,CS_DrawEntityPointCloud,
        CS_EntityDrawingAfterPoints,
        lmn_draw_entity_point_cloud_adapter);
}

static int call_sprite(EntityDrawingState *s) {
    return invoke_child(s,CS_DrawObjectSprite,
        CS_EntityDrawingSpriteResume,
        lmn_draw_entity_sprite_adapter);
}

static void call_decimal_tail(EntityDrawingState *s) {
    LmnDecimalFieldCall call;
    LmnDecimalFieldResult out;
    call.data_segment=s->ds;call.value=s->ax;call.prefix_value=s->bx;
    call.cursor=s->si;call.flags=s->flags;
    out=lmn_write_decimal_field_core(s->memory,&call,s->bus);
    s->ax=out.value;s->bx=out.prefix_value;s->si=out.cursor;
    s->flags=out.flags;
    s->continuation=CS_DecimalFieldReturn;
    s->status=LMN_ENTITY_DRAWING_READY;
}

LmnEntityDrawingResult lmn_draw_entity_records_core(uint8_t *memory,
    const LmnEntityDrawingCall *call,const LmnRasterBus *bus) {
    EntityDrawingState s;
    uint8_t bound;

    state_from_call(&s,memory,call,bus);
    s.di=SEG09A9_EntityRecordsBase;                 /* MOV DI,0088 */
    bound=read8(&s,s.ds,SEG09A9_EntitySlotBound);
    s.cx=(uint16_t)((s.cx&0xff00u)|bound);          /* MOV CL,[0043] */
    s.flags=logic8_flags(s.flags,bound);            /* AND CL,CL */
    if(bound==0u) {
#if ENTITY_DRAWING_MUTATION == 1
        /* Mutation: clear the stale pass count on the zero-bound path. */
        write8(&s,s.ds,SEG09A9_EntityDrawingPassCount,0u);
#endif
        s.continuation=CS_EntityDrawingEarlyReturn;
        s.status=LMN_ENTITY_DRAWING_READY;
        return result_of(&s);
    }

    s.cx=(uint16_t)(s.cx&0x00ffu);
    s.flags=logic8_flags(s.flags,0u);              /* XOR CH,CH */
    write8(&s,s.ds,SEG09A9_EntityDrawingPassCount,0u);

    for(;;) {
        uint8_t skipped;
#if ENTITY_DRAWING_MUTATION == 5 || ENTITY_DRAWING_MUTATION == 6
        s.iteration_di=s.di;s.iteration_cx=s.cx;
#endif
        s.continuation=CS_EntityDrawingLoop;
        push16(&s,s.cx);                           /* PUSH CX */
        push16(&s,s.di);                           /* PUSH DI */

        skipped=read8(&s,s.ds,
            (uint16_t)(s.di+SEG09A9_EntityRecordDrawingSkipGate-
                       SEG09A9_EntityRecordsBase));
        s.flags=sub8_flags(s.flags,skipped,0xffu);  /* CMP byte [DI+26],FF */
#if ENTITY_DRAWING_MUTATION == 2
        if((s.flags&ZF)==0u)goto restore_record;
#else
        if((s.flags&ZF)!=0u)goto restore_record;
#endif

#if ENTITY_DRAWING_MUTATION != 3
        {
            uint8_t before=read8(&s,s.ds,SEG09A9_EntityDrawingPassCount);
            uint8_t after=(uint8_t)(before+1u);
            write8(&s,s.ds,SEG09A9_EntityDrawingPassCount,after);
            s.flags=inc8_flags(s.flags,before);     /* INC byte [0045] */
        }
#endif
        if(!call_minimap(&s))return result_of(&s);
        if(!call_dirty(&s))return result_of(&s);

        s.ax=read16(&s,s.ds,
            (uint16_t)(SEG09A9_DrawingCallbackSlots+0x0eu));
        {
            uint16_t record_callback=read16(&s,s.ds,
                (uint16_t)(s.di+SEG09A9_EntityRecordSpriteCallback-
                           SEG09A9_EntityRecordsBase));
            s.flags=sub16_flags(s.flags,s.ax,record_callback);
        }
        if((s.flags&ZF)==0u)goto draw_sprite;

        set_al(&s,read8(&s,s.ds,
            (uint16_t)(s.di+SEG09A9_EntityRecordFrameSelector-
                       SEG09A9_EntityRecordsBase)));
        s.flags=sub8_flags(s.flags,(uint8_t)s.ax,1u); /* CMP AL,1 */
#if ENTITY_DRAWING_MUTATION == 4
        if((s.flags&CF)!=0u)goto draw_sprite;         /* unsigned JB */
#else
        if(((s.flags&SF)!=0u)!=((s.flags&OF)!=0u))goto draw_sprite;
#endif

        push16(&s,s.di);                            /* PUSH DI */
        {
            uint16_t old_di=s.di;
            s.di=s.si;s.si=old_di;                 /* XCHG SI,DI */
        }
        if(!call_points(&s))return result_of(&s);
        s.di=pop16(&s);                             /* POP DI */
        s.continuation=CS_EntityDrawingRestoreRecord;/* JMP 367D */
        goto restore_record;

draw_sprite:
        write8(&s,s.ds,SEG09A9_EntityWorkGuard,0xffu);
        if(!call_sprite(&s)) {
#if ENTITY_DRAWING_MUTATION == 7
            if(s.status==LMN_ENTITY_DRAWING_CHILD_STOP)
                write8(&s,s.ds,SEG09A9_EntityWorkGuard,0u);
#endif
            return result_of(&s);
        }
        write8(&s,s.ds,SEG09A9_EntityWorkGuard,0u);/* MOV byte [0050],0 */
        s.continuation=CS_EntityDrawingRestoreRecord;

restore_record:
        s.di=pop16(&s);                             /* POP DI */
#if ENTITY_DRAWING_MUTATION == 5
        s.di=s.iteration_di;
#endif
        s.cx=pop16(&s);                             /* POP CX */
#if ENTITY_DRAWING_MUTATION == 6
        s.cx=s.iteration_cx;
#endif
        {
            uint16_t before=s.di;
            s.di=(uint16_t)(s.di+0x002du);
            s.flags=add16_flags(s.flags,before,0x002du);/* ADD DI,2D */
        }
        s.cx=(uint16_t)(s.cx-1u);                  /* LOOP's DEC CX */
        if(s.cx!=0u)continue;

        s.continuation=CS_EntityDrawingDecimalTail;
        set_al(&s,read8(&s,s.ds,SEG09A9_EntityDrawingPassCount));
        s.si=SEG09A9_StatusEntityCountField;        /* MOV SI,2095 */
        s.continuation=CS_EntityDrawingDecimalJump;
#if ENTITY_DRAWING_MUTATION == 9
        /* Mutation: invent a near-CALL frame before the frame-free JMP. */
        push16(&s,CS_EntityDrawingEarlyReturn);
#endif
        call_decimal_tail(&s);
        return result_of(&s);
    }
}

static void apply_result(LmnRegs *r,const LmnEntityDrawingResult *out) {
    r->ax=out->value;r->bx=out->map_cursor;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->record_cursor;
    r->di=out->object_cursor;r->bp=out->candidate_y;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;
    r->ip=out->continuation;
}

#if ENTITY_DRAWING_MUTATION != 10
static uint16_t read_return(uint8_t *memory,uint16_t ss,uint16_t sp,
                            uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(ss,sp);
    uint8_t low,high;
    if(bus && bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,(address+1u)&MEMORY_MASK,flags);
    } else {
        low=memory[address];high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}
#endif

uint16_t lmn_draw_entity_records_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus) {
    LmnEntityDrawingCall call={
        registers->ax,registers->bx,registers->cx,registers->dx,
        registers->si,registers->di,registers->bp,
        registers->cs,registers->ds,registers->es,
        registers->ss,registers->sp,registers->flags
    };
    LmnEntityDrawingResult out=lmn_draw_entity_records_core(memory,&call,bus);
    apply_result(registers,&out);
    if(out.status==LMN_ENTITY_DRAWING_READY) {
#if ENTITY_DRAWING_MUTATION == 10
        /* Mutation: leave the original caller's RET word unconsumed. */
#else
        registers->ip=read_return(memory,registers->ss,registers->sp,
                                  registers->flags,bus);
        registers->sp=(uint16_t)(registers->sp+2u);
#endif
    }
    return out.status;
}

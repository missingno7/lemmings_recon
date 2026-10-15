#include "entity_cadence.h"
#include "lemmings_sym.h"

#ifndef ENTITY_CADENCE_MUTATION
#define ENTITY_CADENCE_MUTATION 0
#endif

enum {
    CF=0x0001u, PF=0x0004u, AF=0x0010u, ZF=0x0040u,
    SF=0x0080u, OF=0x0800u, ARITH=0x08d5u
};

typedef struct CadenceState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} CadenceState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(CadenceState *s,uint32_t address,
                             uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,flags);
    return s->memory[address];
}

static void write_physical(CadenceState *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(CadenceState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset),s->flags);
}

static void write8(CadenceState *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

static uint16_t read16(CadenceState *s,uint16_t segment,uint16_t offset,
                       uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address,flags);
    uint8_t high=read_physical(s,address+1u,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(CadenceState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp(uint16_t value,unsigned bits) {
    uint16_t status=0;
    unsigned parity=0,bit;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    if(!parity)status|=PF;
    if(!(value&((1u<<bits)-1u)))status|=ZF;
    if(value&(1u<<(bits-1u)))status|=SF;
    return status;
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t sum=(uint32_t)(left&mask)+(uint32_t)(right&mask);
    uint16_t value=(uint16_t)(sum&mask),status=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if(sum>mask)status|=CF;
    if((left^right^value)&AF)status|=AF;
    if((~(left^right)&(left^value)&sign)!=0)status|=OF;
    return (uint16_t)((flags&~ARITH)|status);
}

static uint16_t sub_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint16_t l=(uint16_t)(left&mask),r=(uint16_t)(right&mask);
    uint16_t value=(uint16_t)((l-r)&mask),status=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if(l<r)status|=CF;
    if((left^right^value)&AF)status|=AF;
    if(((left^right)&(left^value)&sign)!=0)status|=OF;
    return (uint16_t)((flags&~ARITH)|status);
}

static uint16_t inc_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return (uint16_t)((add_flags(flags,value,1u,bits)&~CF)|(flags&CF));
}

/* AND's AF is undefined. The model chooses zero for it; all defined flags
   follow the 8086 logic-result rule. */
static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static LmnEntityCadenceResult result_of(const CadenceState *s) {
    LmnEntityCadenceResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;
    out.count=s->count;out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;
    out.status=s->status;
    return out;
}

static void set_record_byte(CadenceState *s,uint16_t displacement,
                            uint8_t value) {
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+displacement),
           value,s->flags);
}

/* INC r/m8 is a read-modify-write: the memory write observes entry FLAGS,
   while the logical outgoing FLAGS come from the increment. */
static uint8_t inc_record_byte(CadenceState *s,uint16_t displacement) {
    uint16_t entry_flags=s->flags;
    uint16_t offset=(uint16_t)(s->record_cursor+displacement);
    uint8_t before=read8(s,s->data_segment,offset);
    uint8_t after=(uint8_t)(before+1u);
    s->flags=inc_flags(entry_flags,before,8);
#if ENTITY_CADENCE_MUTATION == 8
    write8(s,s->data_segment,offset,after,s->flags);
#else
    write8(s,s->data_segment,offset,after,entry_flags);
#endif
    return after;
}

static void inc_data_byte(CadenceState *s,uint16_t offset) {
    uint16_t entry_flags=s->flags;
    uint8_t before=read8(s,s->data_segment,offset);
    uint8_t after=(uint8_t)(before+1u);
    s->flags=inc_flags(entry_flags,before,8);
#if ENTITY_CADENCE_MUTATION == 8
    write8(s,s->data_segment,offset,after,s->flags);
#else
    write8(s,s->data_segment,offset,after,entry_flags);
#endif
}

static void mark_inline(CadenceState *s) {
    set_record_byte(s,0x26u,0xffu);
    s->continuation=CS_EntityIterationTail;
    s->status=LMN_ENTITY_CADENCE_READY;
}

/* These two entries execute JMP 20E2, whose body is the existing common
   mark-inactive tail. It returns to the shared 1FEB continuation without an
   additional call frame or register pop. */
static LmnEntityCadenceResult mark_through_finish(CadenceState *s) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=LMN_ENTITY_FINISH_MARK_INACTIVE_20E2;
    call.value=s->value;call.map_cursor=s->map_cursor;
    call.count=s->count;call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
    call.flags=s->flags;
    out=lmn_entity_finish_core(s->memory,&call,NULL,NULL,s->bus);
    s->value=out.value;s->map_cursor=out.map_cursor;s->count=out.count;
    s->auxiliary_value=out.auxiliary_value;
    s->record_cursor=out.record_cursor;s->object_cursor=out.object_cursor;
    s->candidate_y=out.candidate_y;s->code_segment=out.code_segment;
    s->data_segment=out.data_segment;s->extra_segment=out.extra_segment;
    s->stack_segment=out.stack_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=(out.status==LMN_ENTITY_FINISH_RETURNED)
        ? LMN_ENTITY_CADENCE_READY : LMN_ENTITY_CADENCE_INVALID_ENTRY;
    return result_of(s);
}

static LmnEntityCadenceResult state_0001(CadenceState *s) {
    uint16_t offset=(uint16_t)(s->record_cursor+0x28u);
    uint8_t al=read8(s,s->data_segment,offset);
    uint8_t before=al;
    al=(uint8_t)(al+1u);
    s->flags=inc_flags(s->flags,before,8);
#if ENTITY_CADENCE_MUTATION == 1
    al&=7u;
#else
    al&=0x0fu;
#endif
    s->flags=logic_flags(s->flags,al,8);
    s->value=(uint16_t)((s->value&0xff00u)|al);
    set_record_byte(s,0x28u,al);
    if(al==0u)mark_inline(s);
    else {
        s->continuation=CS_EntityIterationTail;
        s->status=LMN_ENTITY_CADENCE_READY;
    }
    return result_of(s);
}

static LmnEntityCadenceResult state_1000(CadenceState *s) {
    uint16_t cadence_offset=(uint16_t)(s->record_cursor+0x28u);
    uint8_t al=read8(s,s->data_segment,cadence_offset);
    uint8_t before=al;
    uint16_t ax,entry_flags;
    uint16_t pushed_ax,actual_return;
    LmnCoordinatePixelCall pixel_call;
    LmnCoordinatePixelResult pixel;
    uint8_t pixel_byte,ah,masked;

    al=(uint8_t)(al+1u);
    s->flags=inc_flags(s->flags,before,8);
    al&=0x0fu;
    s->flags=logic_flags(s->flags,al,8);
    s->value=(uint16_t)((s->value&0xff00u)|al);
    set_record_byte(s,0x28u,al);
    if(al==0u)return mark_through_finish(s);

    /* MOV AL,[SI+27]; CBW. CBW leaves FLAGS alone. */
    al=read8(s,s->data_segment,(uint16_t)(s->record_cursor+0x27u));
    ax=(al&0x80u)?(uint16_t)(0xff00u|al):(uint16_t)al;
    s->value=ax;

    /* PUSH AX occurs before the three word doublings. The live SS word is
       later consumed by the parent's POP BX. */
    pushed_ax=ax;
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,pushed_ax,s->flags);

    {
        unsigned doubling;
        unsigned doubling_count=3u;
#if ENTITY_CADENCE_MUTATION == 2
        /* Mutant adds a fourth doubling, scaling signed motion by 16. */
        doubling_count=4u;
#endif
        for(doubling=0;doubling<doubling_count;++doubling) {
            uint16_t prior=ax;
            ax=(uint16_t)(ax+ax);
            s->flags=add_flags(s->flags,prior,prior,16);
        }
    }
    s->value=ax;

    /* MOV CX,[SI]; ADD CX,AX; MOV BX,[SI+2]. */
    s->count=read16(s,s->data_segment,s->record_cursor,s->flags);
    {
        uint16_t prior=s->count;
        s->count=(uint16_t)(s->count+ax);
        s->flags=add_flags(s->flags,prior,ax,16);
    }
    s->map_cursor=read16(s,s->data_segment,
        (uint16_t)(s->record_cursor+2u),s->flags);

    /* CALL 6141 pushes its actual near return through live SS. */
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,
            CS_EntityState1000AfterPixelCall,s->flags);
#if ENTITY_CADENCE_MUTATION == 5
    actual_return=read16(s,s->stack_segment,s->stack_offset,s->flags);
#endif
    pixel_call.data_segment=s->data_segment;
    pixel_call.stack_segment=s->stack_segment;
    pixel_call.stack_offset=s->stack_offset;
    pixel_call.column_value=s->count;
    pixel_call.row_value=s->map_cursor;
    pixel_call.saved_value=s->auxiliary_value;
    pixel_call.flags=s->flags;
    pixel=lmn_prepare_coordinate_pixel_core(s->memory,&pixel_call,s->bus);
    s->value=pixel.value;s->map_cursor=pixel.row_value;
    s->count=pixel.column_value;s->auxiliary_value=pixel.restored_value;
    s->object_cursor=pixel.destination_offset;
    s->extra_segment=pixel.output_segment;
    s->stack_offset=pixel.stack_offset;s->flags=pixel.flags;

    /* RET reads after the child so stack aliases can change the target. */
#if ENTITY_CADENCE_MUTATION == 5
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
#else
    actual_return=read16(s,s->stack_segment,s->stack_offset,s->flags);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
#endif
    s->continuation=actual_return;
    if(actual_return!=CS_EntityState1000AfterPixelCall) {
        s->status=LMN_ENTITY_CADENCE_CHANGED_PIXEL_RETURN;
        return result_of(s);
    }

    /* POP BX consumes the live word below the CALL frame. */
    {
        uint16_t popped=read16(s,s->stack_segment,s->stack_offset,s->flags);
        s->stack_offset=(uint16_t)(s->stack_offset+2u);
#if ENTITY_CADENCE_MUTATION == 6
        (void)popped; /* Still consume/read the live SS word for the trace. */
        s->map_cursor=pushed_ax;
#else
        s->map_cursor=popped;
#endif
    }

    /* MOV AL,[ES:DI]; AND AL,AH. Both retain the helper's AH byte. */
    pixel_byte=read8(s,s->extra_segment,s->object_cursor);
    ah=(uint8_t)(s->value>>8);
    masked=(uint8_t)(pixel_byte&ah);
    s->value=(uint16_t)((s->value&0xff00u)|masked);
    s->flags=logic_flags(s->flags,masked,8);
    if(masked==0u) {
        uint16_t old=read16(s,s->data_segment,s->record_cursor,s->flags);
        uint16_t next=(uint16_t)(old+s->map_cursor);
        entry_flags=s->flags;
        write16(s,s->data_segment,s->record_cursor,next,entry_flags);
        s->flags=add_flags(entry_flags,old,s->map_cursor,16);
    }
    s->continuation=CS_EntityIterationTail;
    s->status=LMN_ENTITY_CADENCE_READY;
    return result_of(s);
}

static LmnEntityCadenceResult state_2000(CadenceState *s) {
    uint16_t offset=(uint16_t)(s->record_cursor+0x28u);
    uint8_t al=read8(s,s->data_segment,offset);
    uint8_t before=al;
    al=(uint8_t)(al+1u);
    s->flags=inc_flags(s->flags,before,8);
#if ENTITY_CADENCE_MUTATION == 3
    al&=0x0fu;
#else
    al&=0x07u;
#endif
    s->flags=logic_flags(s->flags,al,8);
    s->value=(uint16_t)((s->value&0xff00u)|al);
    set_record_byte(s,0x28u,al);
    if(al==0u) {
        inc_data_byte(s,SEG09A9_EntityCompletionCounter);
        mark_inline(s);
    } else {
        s->continuation=CS_EntityIterationTail;
        s->status=LMN_ENTITY_CADENCE_READY;
    }
    return result_of(s);
}

static LmnEntityCadenceResult state_4000(CadenceState *s) {
    uint8_t al=inc_record_byte(s,0x28u);
#if ENTITY_CADENCE_MUTATION == 7
    /* Mutant reuses INC's value rather than performing MOV AL,[SI+28]. */
#else
    uint16_t offset=(uint16_t)(s->record_cursor+0x28u);
    al=read8(s,s->data_segment,offset);
#endif
    s->value=(uint16_t)((s->value&0xff00u)|al);
#if ENTITY_CADENCE_MUTATION == 4
    s->flags=sub_flags(s->flags,al,0x0du,8);
#else
    s->flags=sub_flags(s->flags,al,0x0eu,8);
#endif
    if(s->flags&ZF)return mark_through_finish(s);
    s->continuation=CS_EntityIterationTail;
    s->status=LMN_ENTITY_CADENCE_READY;
    return result_of(s);
}

LmnEntityCadenceResult lmn_entity_cadence_core(
    uint8_t *memory,const LmnEntityCadenceCall *call,
    const LmnRasterBus *bus) {
    CadenceState s;
    s.memory=memory;s.bus=bus;s.entry=call->entry;
    s.value=call->value;s.map_cursor=call->map_cursor;
    s.count=call->count;s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=0;
    s.status=LMN_ENTITY_CADENCE_INVALID_ENTRY;
    switch(call->entry) {
    case LMN_ENTITY_CADENCE_STATE_0001:return state_0001(&s);
    case LMN_ENTITY_CADENCE_STATE_1000:return state_1000(&s);
    case LMN_ENTITY_CADENCE_STATE_2000:return state_2000(&s);
    case LMN_ENTITY_CADENCE_STATE_4000:return state_4000(&s);
    default:return result_of(&s);
    }
}

uint16_t lmn_entity_cadence_adapter(uint8_t *memory,LmnRegs *registers,
    enum LmnEntityCadenceEntry entry,const LmnRasterBus *bus) {
    LmnEntityCadenceCall call;
    LmnEntityCadenceResult out;
    call.entry=(uint16_t)entry;
    call.value=registers->ax;call.map_cursor=registers->bx;
    call.count=registers->cx;call.auxiliary_value=registers->dx;
    call.record_cursor=registers->si;call.object_cursor=registers->di;
    call.candidate_y=registers->bp;call.code_segment=registers->cs;
    call.data_segment=registers->ds;call.extra_segment=registers->es;
    call.stack_segment=registers->ss;call.stack_offset=registers->sp;
    call.flags=registers->flags;
    out=lmn_entity_cadence_core(memory,&call,bus);
    registers->ax=out.value;registers->bx=out.map_cursor;
    registers->cx=out.count;registers->dx=out.auxiliary_value;
    registers->si=out.record_cursor;registers->di=out.object_cursor;
    registers->bp=out.candidate_y;registers->cs=out.code_segment;
    registers->ds=out.data_segment;registers->es=out.extra_segment;
    registers->ss=out.stack_segment;registers->sp=out.stack_offset;
    registers->flags=out.flags;registers->ip=out.continuation;
    return out.status;
}

#include "entity_create.h"
#include "lemmings_sym.h"

#ifndef ENTITY_CREATE_MUTATION
#define ENTITY_CREATE_MUTATION 0
#endif

enum {
    CF=0x0001u, PF=0x0004u, AF=0x0010u, ZF=0x0040u,
    SF=0x0080u, OF=0x0800u, ARITH=0x08d5u
};

typedef struct CreateState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags,continuation;
} CreateState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(CreateState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(CreateState *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(CreateState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(CreateState *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* Real-mode word accesses advance physically, with 20-bit wrap. */
static uint16_t read16(CreateState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(CreateState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t even_parity(uint8_t value) {
    unsigned bit,ones=0;
    for(bit=0;bit<8u;++bit)ones+=(value>>bit)&1u;
    return (ones&1u)?0u:PF;
}

static uint16_t szp_flags(uint16_t value,unsigned bits) {
    uint16_t flags=even_parity((uint8_t)value);
    if(bits==8u) {
        if(!(uint8_t)value)flags|=ZF;
        if(value&0x80u)flags|=SF;
    } else {
        if(!value)flags|=ZF;
        if(value&0x8000u)flags|=SF;
    }
    return flags;
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return (uint16_t)((flags&~ARITH)|szp_flags(value,bits));
}

static uint16_t compare8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t result=(uint8_t)(left-right);
    uint16_t out=(uint16_t)((flags&~ARITH)|even_parity(result));
    if(!result)out|=ZF;
    if(result&0x80u)out|=SF;
    if(left<right)out|=CF;
    if((left^right^result)&0x10u)out|=AF;
    if(((left^right)&(left^result)&0x80u)!=0)out|=OF;
    return out;
}

static uint16_t decrement8_flags(uint16_t flags,uint8_t old_value,
                                 uint8_t new_value) {
    uint16_t out=(uint16_t)((flags&~(PF|AF|ZF|SF|OF))|even_parity(new_value));
    if(!new_value)out|=ZF;
    if(new_value&0x80u)out|=SF;
    if((old_value&0x0fu)==0u)out|=AF;
    if(old_value==0x80u)out|=OF;
    return out;
}

static uint16_t increment8_flags(uint16_t flags,uint8_t old_value,
                                 uint8_t new_value) {
    uint16_t out=(uint16_t)((flags&~(PF|AF|ZF|SF|OF))|even_parity(new_value));
    if(!new_value)out|=ZF;
    if(new_value&0x80u)out|=SF;
    if((old_value&0x0fu)==0x0fu)out|=AF;
    if(old_value==0x7fu)out|=OF;
    return out;
}

static uint16_t increment16_flags(uint16_t flags,uint16_t old_value,
                                  uint16_t new_value) {
    uint16_t out=(uint16_t)((flags&~(PF|AF|ZF|SF|OF))|szp_flags(new_value,16u));
    if((old_value&0x000fu)==0x000fu)out|=AF;
    if(old_value==0x7fffu)out|=OF;
    return out;
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t sum=(uint32_t)(left&mask)+(uint32_t)(right&mask);
    uint16_t result=(uint16_t)(sum&mask);
    uint16_t out=(uint16_t)((flags&~ARITH)|szp_flags(result,bits));
    uint32_t sign=1u<<(bits-1u);
    if(sum>mask)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&sign)!=0u)out|=OF;
    return out;
}

static uint16_t decrement_memory8(CreateState *s,uint16_t offset) {
    uint8_t old_value=read8(s,s->data_segment,offset);
    uint8_t new_value=(uint8_t)(old_value-1u);
    uint16_t entry_flags=s->flags;
    uint16_t result_flags=decrement8_flags(entry_flags,old_value,new_value);
    /* RMW writes expose instruction-entry FLAGS; DEC defines them afterward. */
    write8(s,s->data_segment,offset,new_value,entry_flags);
    s->flags=result_flags;
    return new_value;
}

#if ENTITY_CREATE_MUTATION != 7
static uint16_t increment_memory8(CreateState *s,uint16_t segment,
                                  uint16_t offset) {
    uint8_t old_value=read8(s,segment,offset);
    uint8_t new_value=(uint8_t)(old_value+1u);
    uint16_t entry_flags=s->flags;
    uint16_t result_flags=increment8_flags(entry_flags,old_value,new_value);
#if ENTITY_CREATE_MUTATION == 8
    write8(s,segment,offset,new_value,result_flags);
#else
    write8(s,segment,offset,new_value,entry_flags);
#endif
    s->flags=result_flags;
    return new_value;
}
#endif

#if ENTITY_CREATE_MUTATION == 7
static uint16_t increment_memory8_from(CreateState *s,uint16_t segment,
                                       uint16_t offset,uint8_t old_value) {
    uint8_t observed=read8(s,segment,offset);
    uint8_t new_value=(uint8_t)(old_value+1u);
    uint16_t entry_flags=s->flags;
    uint16_t result_flags=increment8_flags(entry_flags,old_value,new_value);
    (void)observed; /* The mutant ignores the live INC read result. */
    write8(s,segment,offset,new_value,entry_flags);
    s->flags=result_flags;
    return new_value;
}
#endif

static LmnEntityCreateResult result_of(const CreateState *s) {
    LmnEntityCreateResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;
    out.count=s->count;out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;
    out.status=LMN_ENTITY_CREATE_READY;
    return out;
}

static void write_record8(CreateState *s,uint16_t displacement,uint8_t value) {
    write8(s,s->data_segment,(uint16_t)(s->record_cursor+displacement),
           value,s->flags);
}

static void write_record16(CreateState *s,uint16_t displacement,uint16_t value) {
    write16(s,s->data_segment,(uint16_t)(s->record_cursor+displacement),
            value,s->flags);
}

static void and_record8(CreateState *s,uint16_t displacement,uint8_t mask) {
    uint16_t offset=(uint16_t)(s->record_cursor+displacement);
    uint16_t entry_flags=s->flags;
    uint8_t old_value=read8(s,s->data_segment,offset);
    uint8_t new_value=(uint8_t)(old_value&mask);
    write8(s,s->data_segment,offset,new_value,entry_flags);
    s->flags=logic_flags(entry_flags,new_value,8u);
}

static void or_record16(CreateState *s,uint16_t displacement,
                        uint16_t immediate) {
    uint16_t offset=(uint16_t)(s->record_cursor+displacement);
    uint16_t entry_flags=s->flags;
    uint16_t old_value=read16(s,s->data_segment,offset);
    uint16_t new_value=(uint16_t)(old_value|immediate);
    write16(s,s->data_segment,offset,new_value,entry_flags);
    s->flags=logic_flags(entry_flags,new_value,16u);
}

static void clear_record(CreateState *s,uint16_t start) {
    uint16_t di=start;
    uint16_t cx=0x002du;
#if ENTITY_CREATE_MUTATION == 2
    cx=0x002cu;
#endif
    while(cx) {
        write8(s,s->data_segment,di,0u,s->flags);
        {
            uint16_t old_di=di;
#if ENTITY_CREATE_MUTATION == 1
            di=(uint16_t)(di+((s->flags&0x0400u)?0xffffu:1u));
#else
            di=(uint16_t)(di+1u);
#endif
            s->flags=increment16_flags(s->flags,old_di,di);
        }
        --cx; /* LOOP does not modify FLAGS. */
    }
    s->count=cx;
    s->object_cursor=di;
}

LmnEntityCreateResult lmn_create_entity_record_core(uint8_t *memory,
    const LmnEntityCreateCall *call,const LmnRasterBus *bus) {
    CreateState s;
    uint8_t gate,creation_gate,countdown,limit,bound;
    uint16_t bx,product,coordinates;
#if ENTITY_CREATE_MUTATION == 6
    uint8_t reload;
#endif
#if ENTITY_CREATE_MUTATION == 7
    uint8_t cached_bound_before_callback;
#endif
#if ENTITY_CREATE_MUTATION == 4
    uint16_t prefetched_x,prefetched_y;
#endif

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;
    s.count=call->count;s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=CS_EntityCreationReturn;

    gate=read8(&s,s.data_segment,SEG09A9_EntityUpdateGate);
    s.flags=compare8_flags(s.flags,gate,0xffu);
    if(gate==0xffu)return result_of(&s);

    creation_gate=read8(&s,s.data_segment,SEG09A9_EntityCreationGate);
    s.flags=compare8_flags(s.flags,creation_gate,0xffu);
    if(creation_gate!=0xffu)return result_of(&s);

#if ENTITY_CREATE_MUTATION == 6
    reload=read8(&s,s.data_segment,SEG09A9_EntityCreationReload);
#endif
    countdown=decrement_memory8(&s,SEG09A9_EntityCreationCountdown);
    if(countdown!=0u)return result_of(&s);

#if ENTITY_CREATE_MUTATION == 6
    s.value=(uint16_t)((s.value&0xff00u)|(uint8_t)reload);
#else
    s.value=(uint16_t)((s.value&0xff00u)|
        read8(&s,s.data_segment,SEG09A9_EntityCreationReload));
#endif
    write8(&s,s.data_segment,SEG09A9_EntityCreationCountdown,
           (uint8_t)s.value,s.flags);

    s.record_cursor=SEG09A9_EntityRecordsBase;
    limit=read8(&s,s.data_segment,SEG09A9_LevelCreationLimit);
    bound=read8(&s,s.data_segment,SEG09A9_EntitySlotBound);
    s.value=(uint16_t)(((uint16_t)bound<<8)|limit);
    s.flags=compare8_flags(s.flags,limit,bound);
#if ENTITY_CREATE_MUTATION == 3
    if(bound>=limit)return result_of(&s);
#else
    if(limit==bound)return result_of(&s);
#endif

    /* MOV BL,AH; XOR BH,BH; AND BX,3; SHL BX,1 twice; ADD BX,E98. */
    bx=(uint16_t)(bound&0x00ffu);
    s.flags=logic_flags(s.flags,0u,8u); /* XOR BH,BH */
    s.map_cursor=bx;
    bx&=0x0003u;
    s.flags=logic_flags(s.flags,bx,16u);
    s.map_cursor=bx;
    bx=(uint16_t)(bx<<1);
    s.flags=logic_flags(s.flags,bx,16u); /* SHL BX,1 */
    s.map_cursor=bx;
    bx=(uint16_t)(bx<<1);
    s.flags=logic_flags(s.flags,bx,16u); /* SHL BX,1 */
    s.map_cursor=bx;
    {
        uint16_t old_bx=bx;
        bx=(uint16_t)(bx+SEG09A9_TypeOneObjectCoordinates);
        s.flags=add_flags(s.flags,old_bx,SEG09A9_TypeOneObjectCoordinates,16u);
    }
    coordinates=bx;
    s.map_cursor=bx;

#if ENTITY_CREATE_MUTATION == 5
    s.value=(uint16_t)((s.value&0xff00u)|limit); /* Skip MOV AL,AH. */
#else
    s.value=(uint16_t)((s.value&0xff00u)|bound);
#endif
    /* MUL CL with CL=2D: only CF/OF are defined by 8-bit MUL. */
    product=(uint16_t)((uint8_t)s.value*0x2du);
    s.value=product;
    s.flags=(uint16_t)((s.flags&~(CF|OF))|
        ((product&0xff00u)?(CF|OF):0u));
    s.record_cursor=(uint16_t)(s.record_cursor+product);
    s.flags=add_flags(s.flags,(uint16_t)(s.record_cursor-product),product,16u);

#if ENTITY_CREATE_MUTATION == 4
    prefetched_x=read16(&s,s.data_segment,coordinates);
    prefetched_y=read16(&s,s.data_segment,(uint16_t)(coordinates+2u));
#endif
    clear_record(&s,s.record_cursor);

#if ENTITY_CREATE_MUTATION == 4
    s.value=prefetched_x;
#else
    s.value=read16(&s,s.data_segment,coordinates);
#endif
    write_record16(&s,0u,s.value);
#if ENTITY_CREATE_MUTATION == 4
    s.value=prefetched_y;
#else
    s.value=read16(&s,s.data_segment,(uint16_t)(coordinates+2u));
#endif
    write_record16(&s,2u,s.value);

    write_record8(&s,0x27u,1u);
    write_record8(&s,0x25u,0u);
    and_record8(&s,0x24u,1u);
    or_record16(&s,0x08u,4u);
    write_record16(&s,0x0au,0u);
    write_record16(&s,0x0cu,0x0a42u);
    write_record16(&s,0x10u,0x005au);
    write_record16(&s,0x12u,0x003cu);
    write_record8(&s,0x28u,0u);
    write_record8(&s,0x23u,3u);
    write_record16(&s,0x04u,0xfff8u);
    write_record16(&s,0x06u,0xfff6u);
    write_record8(&s,0x29u,4u);

#if ENTITY_CREATE_MUTATION == 7
    cached_bound_before_callback=read8(&s,s.data_segment,
        SEG09A9_EntitySlotBound);
#endif
    s.value=read16(&s,s.data_segment,SEG09A9_DrawingCallbackSlots);
    write_record16(&s,0x14u,s.value);
    write_record8(&s,0x2au,0u);
    and_record8(&s,0x24u,1u);

#if ENTITY_CREATE_MUTATION == 7
    {
        (void)increment_memory8_from(&s,s.data_segment,
            SEG09A9_EntitySlotBound,cached_bound_before_callback);
    }
#else
    (void)increment_memory8(&s,s.data_segment,SEG09A9_EntitySlotBound);
#endif
    return result_of(&s);
}

uint16_t lmn_create_entity_record_adapter(uint8_t *memory,LmnRegs *r,
    const LmnRasterBus *bus) {
    LmnEntityCreateCall call;
    LmnEntityCreateResult out;
    uint32_t address;
    uint8_t low,high;

    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_create_entity_record_core(memory,&call,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;
    r->es=out.extra_segment;r->ss=out.stack_segment;
    r->sp=out.stack_offset;r->flags=out.flags;
    r->ip=out.continuation;
    if(out.status==LMN_ENTITY_CREATE_READY) {
        address=physical(r->ss,r->sp);
        if(bus&&bus->read_byte) {
            low=bus->read_byte(bus->context,memory,address,r->flags);
            high=bus->read_byte(bus->context,memory,
                (address+1u)&0xfffffu,r->flags);
        } else {
            low=memory[address];
            high=memory[(address+1u)&0xfffffu];
        }
        r->ip=(uint16_t)(low|((uint16_t)high<<8));
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

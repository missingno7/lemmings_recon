#include "entity_select.h"
#include "decimal_field.h"
#include "lemmings_sym.h"

#ifndef ENTITY_SELECT_MUTATION
#define ENTITY_SELECT_MUTATION 0
#endif

enum { CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
       SF=0x0080u,DF=0x0400u,OF=0x0800u,ARITH=0x08d5u,
       INC_ARITH=0x08d4u };

typedef struct EntitySelectState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} EntitySelectState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(EntitySelectState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(EntitySelectState *s,uint32_t address,
                           uint8_t value,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(EntitySelectState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(EntitySelectState *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

/* Word accesses advance in the physical 20-bit address domain. */
static uint16_t read16(EntitySelectState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(EntitySelectState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp8(uint8_t value) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x80u)out|=SF;
    return out;
}

static uint16_t szp16(uint16_t value) {
    uint16_t out=(uint16_t)(szp8((uint8_t)value)&PF);
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

static uint16_t logic8_flags(uint16_t flags,uint8_t result) {
    /* AND/XOR clear CF/OF; undefined AF is represented as zero. */
    return (uint16_t)((flags&~ARITH)|szp8(result));
}

static uint16_t logic16_flags(uint16_t flags,uint16_t result) {
    /* AND/XOR clear CF/OF; undefined AF is represented as zero. */
    return (uint16_t)((flags&~ARITH)|szp16(result));
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)sum,out=szp16(result);
    if(sum>0xffffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
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

static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before+1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0x0fu)out|=AF;
    if(before==0x7fu)out|=OF;
    return (uint16_t)((flags&~INC_ARITH)|out|(flags&CF));
}

static uint16_t dec8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before-1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0u)out|=AF;
    if(before==0x80u)out|=OF;
    return (uint16_t)((flags&~INC_ARITH)|out|(flags&CF));
}

static uint16_t inc16_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before+1u),out=szp16(result);
    if((before&0x000fu)==0x000fu)out|=AF;
    if(before==0x7fffu)out|=OF;
    return (uint16_t)((flags&~INC_ARITH)|out|(flags&CF));
}

static uint16_t dec16_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before-1u),out=szp16(result);
    if((before&0x000fu)==0u)out|=AF;
    if(before==0x8000u)out|=OF;
    return (uint16_t)((flags&~INC_ARITH)|out|(flags&CF));
}

static uint8_t low8(uint16_t value) { return (uint8_t)value; }
static uint8_t high8(uint16_t value) { return (uint8_t)(value>>8); }

static uint16_t replace_low(uint16_t value,uint8_t low) {
    return (uint16_t)((value&0xff00u)|low);
}

static void push_word(EntitySelectState *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,value,s->flags);
}

static uint16_t pop_word(EntitySelectState *s) {
    uint16_t value=read16(s,s->stack_segment,s->stack_offset);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    return value;
}

static uint16_t inc_memory_byte(EntitySelectState *s,uint16_t offset) {
    uint16_t entry_flags=s->flags;
    uint8_t before=read8(s,s->data_segment,offset);
    uint8_t after=(uint8_t)(before+1u);
#if ENTITY_SELECT_MUTATION == 6
    write8(s,s->data_segment,offset,after,inc8_flags(entry_flags,before));
#else
    write8(s,s->data_segment,offset,after,entry_flags);
#endif
    s->flags=inc8_flags(entry_flags,before);
    return after;
}

static LmnEntitySelectResult result_of(const EntitySelectState *s) {
    LmnEntitySelectResult out;
    out.value=s->value;out.map_cursor=s->map_cursor;out.count=s->count;
    out.auxiliary_value=s->auxiliary_value;
    out.record_cursor=s->record_cursor;out.object_cursor=s->object_cursor;
    out.candidate_y=s->candidate_y;out.code_segment=s->code_segment;
    out.data_segment=s->data_segment;out.extra_segment=s->extra_segment;
    out.stack_segment=s->stack_segment;out.stack_offset=s->stack_offset;
    out.flags=s->flags;out.continuation=s->continuation;out.status=s->status;
    return out;
}

static LmnEntitySelectResult at_return(EntitySelectState *s) {
    s->continuation=CS_EntitySelectionReturn;
    s->status=LMN_ENTITY_SELECT_READY;
    return result_of(s);
}

static int signed_ge(const EntitySelectState *s) {
    return ((s->flags&SF)!=0u)==((s->flags&OF)!=0u);
}

static int signed_le(const EntitySelectState *s) {
    return (s->flags&ZF)!=0u || (((s->flags&SF)!=0u)!=((s->flags&OF)!=0u));
}

static void state_to_regs(const EntitySelectState *s,LmnRegs *r) {
    r->ax=s->value;r->bx=s->map_cursor;r->cx=s->count;
    r->dx=s->auxiliary_value;r->si=s->record_cursor;
    r->di=s->object_cursor;r->bp=s->candidate_y;
    r->cs=s->code_segment;r->ds=s->data_segment;r->es=s->extra_segment;
    r->ss=s->stack_segment;r->sp=s->stack_offset;r->flags=s->flags;
}

static void regs_to_state(EntitySelectState *s,const LmnRegs *r) {
    s->value=r->ax;s->map_cursor=r->bx;s->count=r->cx;
    s->auxiliary_value=r->dx;s->record_cursor=r->si;
    s->object_cursor=r->di;s->candidate_y=r->bp;
    s->code_segment=r->cs;s->data_segment=r->ds;s->extra_segment=r->es;
    s->stack_segment=r->ss;s->stack_offset=r->sp;s->flags=r->flags;
}

static int invoke_formatter(EntitySelectState *s) {
    LmnRegs regs;
    uint16_t expected_cs=s->code_segment;
    s->record_cursor=0x208bu; /* MOV SI,208Bh precedes the count read. */
    s->value=replace_low(s->value,
        read8(s,s->data_segment,SEG09A9_EntityCandidateCount));
    push_word(s,CS_EntitySelectionAfterFormatter);
    state_to_regs(s,&regs);
    regs.ip=CS_WriteDecimalByteField;
    lmn_write_decimal_field_adapter(s->memory,&regs,s->bus);
    regs_to_state(s,&regs);
    if(s->code_segment!=expected_cs ||
       regs.ip!=CS_EntitySelectionAfterFormatter) {
        s->continuation=regs.ip;
        s->status=LMN_ENTITY_SELECT_CHANGED_FORMATTER_RETURN;
#if ENTITY_SELECT_MUTATION == 9
        /* Mutation: swallow the altered near-RET target and continue locally. */
        s->status=LMN_ENTITY_SELECT_READY;
        s->continuation=CS_EntitySelectionAfterFormatter;
        return 1;
#else
        return 0;
#endif
    }
    s->continuation=CS_EntitySelectionAfterFormatter;
    s->status=LMN_ENTITY_SELECT_READY;
    return 1;
}

static void scan_candidate(EntitySelectState *s,uint8_t bound,
                           uint8_t frozen_cl,
                           uint8_t *preferred_seen,uint8_t *alternate_seen) {
    uint16_t old,extent;
#if ENTITY_SELECT_MUTATION != 2
    (void)bound;
#endif
#if ENTITY_SELECT_MUTATION != 3
    (void)frozen_cl;
#endif
    uint8_t active=read8(s,s->data_segment,
                         (uint16_t)(s->record_cursor+0x26u));
    s->flags=sub8_flags(s->flags,active,0xffu);
    if(active==0xffu)return;

    s->candidate_y=read16(s,s->data_segment,s->record_cursor);
    extent=read16(s,s->data_segment,(uint16_t)(s->record_cursor+0x04u));
    old=s->candidate_y;s->candidate_y=(uint16_t)(old+extent);
    s->flags=add16_flags(s->flags,old,extent);
    old=s->candidate_y;s->candidate_y=(uint16_t)(old-0x0004u);
    s->flags=sub16_flags(s->flags,old,0x0004u);
    if((s->flags&SF)!=0u) {
        s->candidate_y=0u; /* XOR BP,BP. */
        s->flags=logic16_flags(s->flags,0u);
    }

    s->object_cursor=read16(s,s->data_segment,
                            (uint16_t)(s->record_cursor+0x02u));
    extent=read16(s,s->data_segment,(uint16_t)(s->record_cursor+0x06u));
    old=s->object_cursor;s->object_cursor=(uint16_t)(old+extent);
    s->flags=add16_flags(s->flags,old,extent);
    old=s->object_cursor;s->object_cursor=(uint16_t)(old-1u);
    s->flags=dec16_flags(s->flags,old);
    if((s->flags&SF)==0u) {
        /* JNS uses SF only. */
    } else {
        s->object_cursor=0u; /* XOR DI,DI. */
        s->flags=logic16_flags(s->flags,0u);
    }

    s->flags=sub16_flags(s->flags,s->value,s->candidate_y);
#if ENTITY_SELECT_MUTATION == 4
    if(s->value<s->candidate_y)return; /* unsigned JAE mutant */
#else
    if(!signed_ge(s))return;
#endif
    s->flags=sub16_flags(s->flags,s->map_cursor,s->object_cursor);
    if(!signed_ge(s))return;

    old=s->candidate_y;s->candidate_y=(uint16_t)(old+0x000cu);
    s->flags=add16_flags(s->flags,old,0x000cu);
    s->flags=sub16_flags(s->flags,s->candidate_y,0x0680u);
    if(signed_ge(s)) {
#if ENTITY_SELECT_MUTATION == 5
        s->candidate_y=0x0680u;
#else
        s->candidate_y=0x00d0u;
#endif
    }
    old=s->object_cursor;s->object_cursor=(uint16_t)(old+0x000cu);
    s->flags=add16_flags(s->flags,old,0x000cu);
    s->flags=sub16_flags(s->flags,s->object_cursor,0x00b0u);
    if(signed_ge(s))s->object_cursor=0x00b0u;

    s->flags=sub16_flags(s->flags,s->value,s->candidate_y);
    if(!signed_le(s))return;
    s->flags=sub16_flags(s->flags,s->map_cursor,s->object_cursor);
    if(!signed_le(s))return;

    {
        uint16_t pushed_value=s->value;
        uint16_t state_word;
        push_word(s,s->value); /* PUSH AX, including live SS aliasing. */
        active=read8(s,s->data_segment,(uint16_t)(s->record_cursor+0x24u));
        s->flags=logic8_flags(s->flags,(uint8_t)(active&0x80u));
        if((s->flags&ZF)!=0u) {
            state_word=read16(s,s->data_segment,
                              (uint16_t)(s->record_cursor+0x08u));
            s->flags=logic16_flags(s->flags,(uint16_t)(state_word&0x8b90u));
        }
        if((s->flags&ZF)!=0u) {
            uint8_t live_bound=read8(s,s->data_segment,
                                     SEG09A9_EntitySlotBound);
#if ENTITY_SELECT_MUTATION == 2
            live_bound=bound;
#endif
#if ENTITY_SELECT_MUTATION == 3
            active=frozen_cl;
#else
            active=(uint8_t)s->count;
#endif
            s->value=replace_low(s->value,live_bound);
            s->value=replace_low(s->value,
                (uint8_t)(low8(s->value)-active)); /* SUB AL,CL. */
            s->flags=sub8_flags(s->flags,live_bound,active);
#if ENTITY_SELECT_MUTATION == 8
            if(!*alternate_seen) {
#endif
                write8(s,s->data_segment,
                       SEG09A9_EntityAlternateSlotIndex,low8(s->value),
                       s->flags);
                write16(s,s->data_segment,
                        SEG09A9_EntityAlternateRecordOffset,s->record_cursor,
                        s->flags);
                *alternate_seen=1u;
#if ENTITY_SELECT_MUTATION == 8
            }
#endif
        } else {
            uint8_t live_bound=read8(s,s->data_segment,
                                     SEG09A9_EntitySlotBound);
#if ENTITY_SELECT_MUTATION == 2
            live_bound=bound;
#endif
#if ENTITY_SELECT_MUTATION == 3
            active=frozen_cl;
#else
            active=(uint8_t)s->count;
#endif
            s->value=replace_low(s->value,live_bound);
            s->value=replace_low(s->value,
                (uint8_t)(low8(s->value)-active)); /* SUB AL,CL. */
            s->flags=sub8_flags(s->flags,live_bound,active);
#if ENTITY_SELECT_MUTATION == 8
            if(!*preferred_seen) {
#endif
                write8(s,s->data_segment,
                       SEG09A9_EntityPreferredSlotIndex,low8(s->value),
                       s->flags);
                write16(s,s->data_segment,
                        SEG09A9_EntityPreferredRecordOffset,s->record_cursor,
                        s->flags);
                *preferred_seen=1u;
#if ENTITY_SELECT_MUTATION == 8
            }
#endif
        }

        s->value=pop_word(s); /* POP AX consumes the actual saved word. */
#if ENTITY_SELECT_MUTATION == 7
        s->value=pushed_value;
#else
        (void)pushed_value;
#endif
        (void)inc_memory_byte(s,SEG09A9_EntityCandidateCount);
    }
}

LmnEntitySelectResult lmn_select_entity_core(uint8_t *memory,
    const LmnEntitySelectCall *call,const LmnRasterBus *bus) {
    EntitySelectState s;
    uint8_t bound,frozen_cl;
    uint8_t preferred_seen=0u,alternate_seen=0u;

    s.memory=memory;s.bus=bus;
    s.value=call->value;s.map_cursor=call->map_cursor;s.count=call->count;
    s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=0u;s.status=LMN_ENTITY_SELECT_READY;

    bound=read8(&s,s.data_segment,SEG09A9_EntitySlotBound);
    s.count=replace_low(s.count,bound); /* MOV CL,[0043]. */
    frozen_cl=bound;
    s.flags=logic8_flags(s.flags,bound); /* AND CL,CL. */
#if ENTITY_SELECT_MUTATION != 1
    if(bound==0u)return at_return(&s);
#endif

    s.record_cursor=0x2083u; /* SI=2083; fill eleven bytes with spaces. */
    s.value=(uint16_t)((s.value&0x00ffu)|0x0b00u); /* MOV AH,0Bh. */
    {
        uint8_t remaining=0x0bu;
        do {
            write8(&s,s.data_segment,s.record_cursor,0x20u,s.flags);
            {
                uint16_t before=s.record_cursor;
                s.record_cursor=(uint16_t)(before+1u);
                s.flags=inc16_flags(s.flags,before);
            }
            {
                uint8_t before=high8(s.value);
                remaining=(uint8_t)(before-1u);
                s.value=(uint16_t)((s.value&0x00ffu)|
                                   ((uint16_t)remaining<<8));
                s.flags=dec8_flags(s.flags,before);
            }
        } while(remaining!=0u);
    }
    write8(&s,s.data_segment,SEG09A9_EntityCandidateCount,0u,s.flags);
    write8(&s,s.data_segment,SEG09A9_EntitySelectedSlotIndex,0xffu,s.flags);
    write8(&s,s.data_segment,SEG09A9_EntityPreferredSlotIndex,0xffu,s.flags);
    write8(&s,s.data_segment,SEG09A9_EntityAlternateSlotIndex,0xffu,s.flags);

    s.value=read16(&s,s.data_segment,0x0000u);
    {
        uint16_t before=s.value;s.value=(uint16_t)(before-0x0010u);
        s.flags=sub16_flags(s.flags,before,0x0010u);
    }
    {
        uint16_t extent=read16(&s,s.data_segment,0x0010u);
        uint16_t before=s.value;s.value=(uint16_t)(before+extent);
        s.flags=add16_flags(s.flags,before,extent);
    }
    s.map_cursor=read16(&s,s.data_segment,0x0012u);
    {
        uint16_t before=s.map_cursor;s.map_cursor=(uint16_t)(before+0x0008u);
        s.flags=add16_flags(s.flags,before,0x0008u);
    }
    s.record_cursor=SEG09A9_EntityRecordsBase;

    for(;;) {
        uint8_t cl=low8(s.count);
        scan_candidate(&s,bound,frozen_cl,&preferred_seen,&alternate_seen);
        {
            uint16_t before=s.record_cursor;
            s.record_cursor=(uint16_t)(before+0x002du);
            s.flags=add16_flags(s.flags,before,0x002du);
        }
        cl=(uint8_t)(cl-1u);
        s.count=replace_low(s.count,cl);
        s.flags=dec8_flags(s.flags,(uint8_t)(cl+1u));
        if(cl==0u)break;
    }

    write8(&s,s.data_segment,SEG09A9_EntitySelectionPresent,0u,s.flags);
    s.value=read16(&s,s.data_segment,SEG09A9_InputButtonsWord);
    s.flags=logic16_flags(s.flags,(uint16_t)(s.value&0x0002u));
    if((s.flags&ZF)!=0u) {
        s.value=replace_low(s.value,
            read8(&s,s.data_segment,SEG09A9_EntityPreferredSlotIndex));
        s.flags=sub8_flags(s.flags,low8(s.value),0xffu);
        if(low8(s.value)!=0xffu) {
            s.record_cursor=read16(&s,s.data_segment,
                                   SEG09A9_EntityPreferredRecordOffset);
            write8(&s,s.data_segment,SEG09A9_EntitySelectedSlotIndex,
                   low8(s.value),s.flags);
            write16(&s,s.data_segment,SEG09A9_EntitySelectedRecordOffset,
                    s.record_cursor,s.flags);
        } else {
            s.value=replace_low(s.value,
                read8(&s,s.data_segment,SEG09A9_EntityAlternateSlotIndex));
            s.record_cursor=read16(&s,s.data_segment,
                                   SEG09A9_EntityAlternateRecordOffset);
            write8(&s,s.data_segment,SEG09A9_EntitySelectedSlotIndex,
                   low8(s.value),s.flags);
            write16(&s,s.data_segment,SEG09A9_EntitySelectedRecordOffset,
                    s.record_cursor,s.flags);
        }
    } else {
        s.value=replace_low(s.value,
            read8(&s,s.data_segment,SEG09A9_EntityAlternateSlotIndex));
        s.record_cursor=read16(&s,s.data_segment,
                               SEG09A9_EntityAlternateRecordOffset);
        write8(&s,s.data_segment,SEG09A9_EntitySelectedSlotIndex,
               low8(s.value),s.flags);
        write16(&s,s.data_segment,SEG09A9_EntitySelectedRecordOffset,
                s.record_cursor,s.flags);
    }

    {
        uint8_t selected=read8(&s,s.data_segment,
                               SEG09A9_EntitySelectedSlotIndex);
        s.flags=sub8_flags(s.flags,selected,0xffu);
        if(selected==0xffu)return at_return(&s);
    }

    write8(&s,s.data_segment,SEG09A9_EntitySelectionPresent,0xffu,s.flags);
    if(!invoke_formatter(&s))return result_of(&s);

    /* SI is freshly reloaded after formatter RET; do not cache the pointer. */
    s.record_cursor=read16(&s,s.data_segment,
                           SEG09A9_EntitySelectedRecordOffset);
    s.map_cursor=0x48dbu;
    s.value=replace_low(s.value,
        read8(&s,s.data_segment,(uint16_t)(s.record_cursor+0x24u)));
    s.flags=logic8_flags(s.flags,(uint8_t)(low8(s.value)&0x80u));
    if((s.flags&ZF)==0u)goto copy_template;

    s.map_cursor=0x48bfu;
    s.flags=logic8_flags(s.flags,(uint8_t)(low8(s.value)&0x01u));
    if((s.flags&ZF)==0u) {
        uint8_t marker=read8(&s,s.data_segment,
                             (uint16_t)(s.record_cursor+0x25u));
        s.flags=sub8_flags(s.flags,marker,0u);
        if(marker==0u)goto copy_template;
        s.map_cursor=0x490cu;
        goto copy_template;
    }

    s.map_cursor=0x48c6u;
    {
        uint8_t marker=read8(&s,s.data_segment,
                             (uint16_t)(s.record_cursor+0x25u));
        s.flags=sub8_flags(s.flags,marker,0u);
        if(marker!=0u)goto copy_template;
    }
    s.map_cursor=0x48d4u;
    {
        uint16_t state=read16(&s,s.data_segment,
                              (uint16_t)(s.record_cursor+0x08u));
        s.flags=logic16_flags(s.flags,(uint16_t)(state&0x0100u));
        if((s.flags&ZF)==0u)goto copy_template;
    }
    s.map_cursor=0x48dbu;
    {
        uint16_t state=read16(&s,s.data_segment,
                              (uint16_t)(s.record_cursor+0x08u));
        s.flags=logic16_flags(s.flags,(uint16_t)(state&0x0080u));
        if((s.flags&ZF)==0u)goto copy_template;
    }
    s.map_cursor=0x48e2u;
    {
        uint16_t state=read16(&s,s.data_segment,
                              (uint16_t)(s.record_cursor+0x08u));
        s.flags=logic16_flags(s.flags,(uint16_t)(state&0x0200u));
        if((s.flags&ZF)==0u)goto copy_template;
    }
    s.map_cursor=0x48e9u;
    {
        uint16_t state=read16(&s,s.data_segment,
                              (uint16_t)(s.record_cursor+0x08u));
        s.flags=logic16_flags(s.flags,(uint16_t)(state&0x0800u));
        if((s.flags&ZF)==0u)goto copy_template;
    }
    s.map_cursor=0x48f0u;
    {
        uint16_t state=read16(&s,s.data_segment,
                              (uint16_t)(s.record_cursor+0x08u));
        s.flags=logic16_flags(s.flags,(uint16_t)(state&0x0010u));
        if((s.flags&ZF)==0u)goto copy_template;
    }
    s.map_cursor=0x48feu;
    {
        uint16_t state=read16(&s,s.data_segment,
                              (uint16_t)(s.record_cursor+0x08u));
        s.flags=logic16_flags(s.flags,(uint16_t)(state&0x0004u));
        if((s.flags&ZF)==0u)goto copy_template;
    }
    s.map_cursor=0x48f7u;

copy_template:
    s.record_cursor=0x2083u;
    s.value=(uint16_t)((s.value&0x00ffu)|0x0700u); /* MOV AH,7. */
    for(;;) {
        uint8_t template_byte=read8(&s,s.data_segment,s.map_cursor);
        s.value=replace_low(s.value,template_byte);
        write8(&s,s.data_segment,s.record_cursor,template_byte,s.flags);
        {
            uint16_t before=s.record_cursor;
            s.record_cursor=(uint16_t)(before+1u);
            s.flags=inc16_flags(s.flags,before);
        }
        {
            uint16_t before=s.map_cursor;
            s.map_cursor=(uint16_t)(before+1u);
            s.flags=inc16_flags(s.flags,before);
        }
        {
            uint8_t before=high8(s.value);
            uint8_t after=(uint8_t)(before-1u);
            s.value=(uint16_t)((s.value&0x00ffu)|((uint16_t)after<<8));
            s.flags=dec8_flags(s.flags,before);
            if(after==0u)break;
        }
    }
    return at_return(&s);
}

static uint16_t read_return(uint8_t *memory,const LmnRasterBus *bus,
                            uint16_t ss,uint16_t sp,uint16_t flags) {
    uint32_t address=physical(ss,sp);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,(address+1u)&0xfffffu,flags);
    } else {
        low=memory[address];
        high=memory[(address+1u)&0xfffffu];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

uint16_t lmn_select_entity_adapter(uint8_t *memory,LmnRegs *r,
    const LmnRasterBus *bus) {
    LmnEntitySelectCall call;
    LmnEntitySelectResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_select_entity_core(memory,&call,bus);
    r->ax=out.value;r->bx=out.map_cursor;r->cx=out.count;
    r->dx=out.auxiliary_value;r->si=out.record_cursor;
    r->di=out.object_cursor;r->bp=out.candidate_y;
    r->cs=out.code_segment;r->ds=out.data_segment;r->es=out.extra_segment;
    r->ss=out.stack_segment;r->sp=out.stack_offset;
    r->flags=out.flags;r->ip=out.continuation;
    if(out.status==LMN_ENTITY_SELECT_READY) {
        r->ip=read_return(memory,bus,r->ss,r->sp,r->flags);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

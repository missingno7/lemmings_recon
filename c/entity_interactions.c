#include "entity_interactions.h"
#include "lemmings_sym.h"

#ifndef ENTITY_INTERACTIONS_MUTATION
#define ENTITY_INTERACTIONS_MUTATION 0
#endif

enum {
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,SF=0x0080u,
    DF=0x0400u,OF=0x0800u,ARITH=0x08d5u,
    RET_2F3A=0x2f3au,RET_2FAB=0x2fabu,RET_2FB5=0x2fb5u
};

typedef struct InteractionState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    LmnRegs r;
} InteractionState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(InteractionState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->r.flags);
    return s->memory[address];
}

static void write_physical_flags(InteractionState *s,uint32_t address,
                                 uint8_t value,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(InteractionState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8_flags(InteractionState *s,uint16_t segment,uint16_t offset,
                         uint8_t value,uint16_t flags) {
    write_physical_flags(s,physical(segment,offset),value,flags);
}

static void write8(InteractionState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write8_flags(s,segment,offset,value,s->r.flags);
}

/* The word's high byte is the next physical byte, even at offset FFFF. */
static uint16_t read16(InteractionState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16_flags(InteractionState *s,uint16_t segment,uint16_t offset,
                          uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical_flags(s,address,(uint8_t)value,flags);
    write_physical_flags(s,address+1u,(uint8_t)(value>>8),flags);
}

static void write16(InteractionState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    write16_flags(s,segment,offset,value,s->r.flags);
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8 ? 0xffu:0xffffu;
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)(sum&mask),out=(uint16_t)(flags&~ARITH);
    unsigned sign=bits==8 ? 0x80u:0x8000u;
    unsigned parity=0,n;
    if(sum>mask) out|=CF;
    if((left^right^result)&AF) out|=AF;
    if((~(left^right)&(left^result)&sign)!=0) out|=OF;
    if(!result) out|=ZF;
    if(result&sign) out|=SF;
    for(n=0;n<8;++n) parity^=(result>>n)&1u;
    if(!parity) out|=PF;
    return out;
}

static uint16_t sub_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8 ? 0xffu:0xffffu;
    uint16_t result=(uint16_t)(((uint32_t)left-(uint32_t)right)&mask);
    uint16_t out=(uint16_t)(flags&~ARITH);
    unsigned sign=bits==8 ? 0x80u:0x8000u;
    unsigned parity=0,n;
    if((uint32_t)left<right) out|=CF;
    if((left^right^result)&AF) out|=AF;
    if(((left^right)&(left^result)&sign)!=0) out|=OF;
    if(!result) out|=ZF;
    if(result&sign) out|=SF;
    for(n=0;n<8;++n) parity^=(result>>n)&1u;
    if(!parity) out|=PF;
    return out;
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    uint16_t out=(uint16_t)(flags&~ARITH);
    unsigned sign=bits==8 ? 0x80u:0x8000u;
    unsigned parity=0,n;
    value=(uint16_t)(value&(bits==8 ? 0xffu:0xffffu));
    if(!value) out|=ZF;
    if(value&sign) out|=SF;
    for(n=0;n<8;++n) parity^=(value>>n)&1u;
    if(!parity) out|=PF;
    return out;
}

static uint16_t decrement8_flags(uint16_t flags,uint8_t old_value,
                                 uint8_t new_value) {
    uint16_t out=(uint16_t)(flags&~(PF|AF|ZF|SF|OF));
    unsigned parity=0,n;
    for(n=0;n<8;++n) parity^=(new_value>>n)&1u;
    if(!parity) out|=PF;
    if((old_value&0x0fu)==0) out|=AF;
    if(!new_value) out|=ZF;
    if(new_value&0x80u) out|=SF;
    if(old_value==0x80u) out|=OF;
    return out;
}

static uint16_t negate8_flags(uint16_t flags,uint8_t value,uint8_t result) {
    uint16_t out=(uint16_t)(flags&~ARITH);
    unsigned parity=0,n;
    if(value) out|=CF;
    if((value&0x0fu)!=0) out|=AF;
    if(value==0x80u) out|=OF;
    if(!result) out|=ZF;
    if(result&0x80u) out|=SF;
    for(n=0;n<8;++n) parity^=(result>>n)&1u;
    if(!parity) out|=PF;
    return out;
}

static uint16_t shift_right_flags(uint16_t flags,uint16_t old_value,
                                  uint16_t new_value,unsigned bits,
                                  int arithmetic) {
    uint16_t out=(uint16_t)(flags&~ARITH);
    unsigned sign=bits==8 ? 0x80u:0x8000u;
    unsigned parity=0,n;
    if(old_value&1u) out|=CF;
    if(!arithmetic && (old_value&sign)) out|=OF; /* SHR's count-one OF. */
    if(!new_value) out|=ZF;
    if(new_value&sign) out|=SF;
    for(n=0;n<8;++n) parity^=(new_value>>n)&1u;
    if(!parity) out|=PF;
    return out;
}

static uint16_t multiply_flags(uint16_t flags,uint32_t product) {
    uint16_t out=(uint16_t)(flags&~(CF|OF));
    if(product>>16) out|=CF|OF;
    return out;
}

static void push(InteractionState *s,uint16_t value) {
    s->r.sp=(uint16_t)(s->r.sp-2u);
    write16(s,s->r.ss,s->r.sp,value);
}

static uint16_t pop(InteractionState *s) {
    uint16_t value=read16(s,s->r.ss,s->r.sp);
    s->r.sp=(uint16_t)(s->r.sp+2u);
    return value;
}

static uint16_t record_offset(const InteractionState *s,uint16_t displacement) {
    return (uint16_t)(s->r.si+displacement);
}

static LmnEntityInteractionsResult result(const InteractionState *s,
                                           uint16_t status) {
    LmnEntityInteractionsResult out;
    out.value=s->r.ax;
    out.map_cursor=s->r.bx;
    out.count=s->r.cx;
    out.auxiliary_value=s->r.dx;
    out.record_cursor=s->r.si;
    out.object_cursor=s->r.di;
    out.data_segment=s->r.ds;
    out.code_segment=s->r.cs;
    out.stack_segment=s->r.ss;
    out.stack_offset=s->r.sp;
    out.flags=s->r.flags;
    out.continuation=s->r.ip;
    out.status=status;
    return out;
}

static LmnEntityInteractionsResult ready_at(InteractionState *s,
                                             uint16_t continuation) {
    s->r.ip=continuation;
    return result(s,LMN_ENTITY_INTERACTION_RET_READY);
}

static uint16_t pc_status(uint16_t status) {
    switch(status) {
    case LMN_PC_INTERRUPT_RETURNED:
        return LMN_ENTITY_INTERACTION_RET_READY;
    case LMN_PC_INTERRUPT_UNBOUND_VECTOR:
        return LMN_ENTITY_INTERACTION_UNBOUND_VECTOR;
    case LMN_PC_INTERRUPT_UNTRANSLATED_CHILD:
        return LMN_ENTITY_INTERACTION_UNTRANSLATED_SOUND;
    case LMN_PC_INTERRUPT_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_INTERACTION_CHANGED_CHILD_RETURN;
    case LMN_PC_INTERRUPT_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_INTERACTION_CHANGED_INTERRUPT_RETURN;
    default:
        return LMN_ENTITY_INTERACTION_UNBOUND_VECTOR;
    }
}

static uint16_t sound_status(uint16_t status) {
    switch(status) {
    case LMN_SOUND_INTERRUPT_RETURNED:
        return LMN_ENTITY_INTERACTION_RET_READY;
    case LMN_SOUND_INTERRUPT_UNBOUND_VECTOR:
        return LMN_ENTITY_INTERACTION_UNBOUND_VECTOR;
    case LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE:
        return LMN_ENTITY_INTERACTION_UNTRANSLATED_SOUND;
    case LMN_SOUND_INTERRUPT_CHANGED_RETURN:
        return LMN_ENTITY_INTERACTION_CHANGED_INTERRUPT_RETURN;
    default:
        return LMN_ENTITY_INTERACTION_UNBOUND_VECTOR;
    }
}

static uint16_t invoke_pc(InteractionState *s,uint16_t return_offset,
                          const LmnPcSpeakerBinding *binding) {
    LmnPcSpeakerInterruptCall call;
    LmnPcSpeakerInterruptResult child;
    uint16_t old_ds=s->r.ds,old_si=s->r.si;
    call.registers=s->r;
    call.return_offset=return_offset;
    child=lmn_pc_speaker_interrupt60_core(s->memory,&call,binding,s->bus);
    s->r=child.registers;
#if ENTITY_INTERACTIONS_MUTATION == 6
    s->r.ds=old_ds;s->r.si=old_si;
#else
    (void)old_ds;(void)old_si;
#endif
    return pc_status(child.status);
}

static uint16_t invoke_sound(InteractionState *s,uint16_t return_offset,
                             const LmnSoundDriverBinding *binding) {
    LmnSoundInterruptCall call;
    LmnSoundInterruptResult child;
    call.value=s->r.ax;
    call.data_segment=s->r.ds;
    call.code_segment=s->r.cs;
    call.stack_segment=s->r.ss;
    call.stack_offset=s->r.sp;
    call.flags=s->r.flags;
    call.return_offset=return_offset;
    child=lmn_sound_interrupt61_core(s->memory,&call,binding,s->bus);
    s->r.ax=child.value;
    s->r.ds=child.data_segment;
    s->r.cs=child.code_segment;
    s->r.sp=child.stack_offset;
    s->r.flags=child.flags;
    s->r.ip=child.continuation;
    return sound_status(child.status);
}

static void compare_external_sound(InteractionState *s) {
    uint8_t value=read8(s,s->r.ds,SEG09A9_ExternalSoundDriverEnabled);
    s->r.flags=sub_flags(s->r.flags,value,0xffu,8);
}

static void test_sound_options(InteractionState *s,uint8_t mask) {
    uint8_t options=read8(s,s->r.ds,SEG09A9_SoundOptionBits);
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(options&mask),8);
}

static LmnEntityInteractionsResult transition_one(InteractionState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint16_t entry=s->r.flags;
    uint16_t test=read16(s,s->r.ds,record_offset(s,0x08u));
    s->r.flags=logic_flags(entry,(uint16_t)(test&0x0004u),16);
    if(s->r.flags&ZF) {
        /* TEST bit 2 was clear: install transition 1 in original store order. */
        write16(s,s->r.ds,record_offset(s,0x08u),0x2000u);
        write16(s,s->r.ds,record_offset(s,0x0au),0x0000u);
        write16(s,s->r.ds,record_offset(s,0x0cu),0x0efau);
        write16(s,s->r.ds,record_offset(s,0x10u),0x004eu);
        write16(s,s->r.ds,record_offset(s,0x12u),0x0034u);
        write8(s,s->r.ds,record_offset(s,0x28u),0x00u);
        write16(s,s->r.ds,record_offset(s,0x04u),0xfff8u);
        write16(s,s->r.ds,record_offset(s,0x06u),0xfff3u);
        write8(s,s->r.ds,record_offset(s,0x29u),0x00u);
        s->r.ax=read16(s,s->r.ds,
            (uint16_t)(SEG09A9_DrawingCallbackSlots+4u));
        write16(s,s->r.ds,record_offset(s,0x14u),s->r.ax);
        write8(s,s->r.ds,record_offset(s,0x2au),0xffu);
        entry=s->r.flags;
        test=read8(s,s->r.ds,record_offset(s,0x24u));
        write8_flags(s,s->r.ds,record_offset(s,0x24u),
                     (uint8_t)(test&1u),entry);
        s->r.flags=logic_flags(entry,(uint16_t)(test&1u),8);
    } else {
        return ready_at(s,RET_2F3A);
    }

    compare_external_sound(s);
    if(!(s->r.flags&ZF)) {
        test_sound_options(s,0x01u);
        if(!(s->r.flags&ZF)) {
            s->r.ax=0x0302u;
            {
                uint16_t status=invoke_pc(s,CS_EntityInteractionPcSoundReturn,
                                          pc_binding);
                if(status!=LMN_ENTITY_INTERACTION_RET_READY)
                    return result(s,status);
            }
            s->r.ip=CS_EntityInteractionPcSoundReturn;
        }
    }

    if(ENTITY_INTERACTIONS_MUTATION!=7)
        compare_external_sound(s);
    if(!(s->r.flags&ZF))
        return ready_at(s,CS_EntityInteractionFirstSoundReturn);
    test_sound_options(s,0x03u);
    if(s->r.flags&ZF)
        return ready_at(s,CS_EntityInteractionFirstSoundReturn);
    s->r.ax=0x0410u;
    {
        uint16_t status=invoke_sound(s,CS_EntityInteractionFirstSoundReturn,
                                     sound_binding);
        if(status!=LMN_ENTITY_INTERACTION_RET_READY)
            return result(s,status);
    }
    return ready_at(s,CS_EntityInteractionFirstSoundReturn);
}

static LmnEntityInteractionsResult transition_five(InteractionState *s,
    const LmnSoundDriverBinding *sound_binding) {
    uint16_t entry=s->r.flags;
    uint16_t test=read16(s,s->r.ds,record_offset(s,0x08u));
    s->r.flags=logic_flags(entry,(uint16_t)(test&0x1000u),16);
    if(!(s->r.flags&ZF))
        return ready_at(s,RET_2F3A);

    write16(s,s->r.ds,record_offset(s,0x08u),0x1000u);
    write16(s,s->r.ds,record_offset(s,0x0au),0x0000u);
    write16(s,s->r.ds,record_offset(s,0x0cu),0x03e2u);
    write16(s,s->r.ds,record_offset(s,0x10u),0x005au);
    write16(s,s->r.ds,record_offset(s,0x12u),0x003cu);
    write8(s,s->r.ds,record_offset(s,0x28u),0x00u);
    write16(s,s->r.ds,record_offset(s,0x04u),0xfff8u);
    write16(s,s->r.ds,record_offset(s,0x06u),0xfff6u);
    write8(s,s->r.ds,record_offset(s,0x29u),0x00u);
    s->r.ax=read16(s,s->r.ds,SEG09A9_DrawingCallbackSlots);
    write16(s,s->r.ds,record_offset(s,0x14u),s->r.ax);
    write8(s,s->r.ds,record_offset(s,0x2au),0x00u);
    entry=s->r.flags;
    test=read8(s,s->r.ds,record_offset(s,0x24u));
    write8_flags(s,s->r.ds,record_offset(s,0x24u),(uint8_t)(test&1u),entry);
    s->r.flags=logic_flags(entry,(uint16_t)(test&1u),8);

    compare_external_sound(s);
    if(!(s->r.flags&ZF))
        return ready_at(s,CS_EntityInteractionSecondSoundReturn);
    test_sound_options(s,0x03u);
    if(s->r.flags&ZF)
        return ready_at(s,CS_EntityInteractionSecondSoundReturn);
    s->r.ax=0x0411u;
    {
        uint16_t status=invoke_sound(s,CS_EntityInteractionSecondSoundReturn,
                                     sound_binding);
        if(status!=LMN_ENTITY_INTERACTION_RET_READY)
            return result(s,status);
    }
    return ready_at(s,CS_EntityInteractionSecondSoundReturn);
}

static LmnEntityInteractionsResult transition_six(InteractionState *s,
    const LmnSoundDriverBinding *sound_binding) {
    uint16_t entry=s->r.flags;
    uint16_t test=read16(s,s->r.ds,record_offset(s,0x08u));
    s->r.flags=logic_flags(entry,(uint16_t)(test&0x4000u),16);
    if(!(s->r.flags&ZF))
        return ready_at(s,RET_2F3A);

    write16(s,s->r.ds,record_offset(s,0x08u),0x4000u);
    write16(s,s->r.ds,record_offset(s,0x0au),0x0000u);
    write16(s,s->r.ds,record_offset(s,0x0cu),0x0f21u);
    write16(s,s->r.ds,record_offset(s,0x10u),0x008cu);
    write16(s,s->r.ds,record_offset(s,0x12u),0x0070u);
    write8(s,s->r.ds,record_offset(s,0x28u),0x00u);
    write16(s,s->r.ds,record_offset(s,0x04u),0xfff8u);
    write16(s,s->r.ds,record_offset(s,0x06u),0xfff2u);
    write8(s,s->r.ds,record_offset(s,0x29u),0x00u);
    s->r.ax=read16(s,s->r.ds,
        (uint16_t)(SEG09A9_DrawingCallbackSlots+0x10u));
    write16(s,s->r.ds,record_offset(s,0x14u),s->r.ax);
    write8(s,s->r.ds,record_offset(s,0x2au),0xffu);
    entry=s->r.flags;
    test=read8(s,s->r.ds,record_offset(s,0x24u));
    write8_flags(s,s->r.ds,record_offset(s,0x24u),(uint8_t)(test&1u),entry);
    s->r.flags=logic_flags(entry,(uint16_t)(test&1u),8);

    compare_external_sound(s);
    if(!(s->r.flags&ZF))
        return ready_at(s,CS_EntityInteractionThirdSoundReturn);
    test_sound_options(s,0x03u);
    if(s->r.flags&ZF)
        return ready_at(s,CS_EntityInteractionThirdSoundReturn);
    s->r.ax=0x040du;
    {
        uint16_t status=invoke_sound(s,CS_EntityInteractionThirdSoundReturn,
                                     sound_binding);
        if(status!=LMN_ENTITY_INTERACTION_RET_READY)
            return result(s,status);
    }
    return ready_at(s,CS_EntityInteractionThirdSoundReturn);
}

static LmnEntityInteractionsResult negative_record_byte(InteractionState *s,
                                                          uint16_t tail) {
    uint16_t entry=s->r.flags;
    uint8_t value=read8(s,s->r.ds,record_offset(s,0x27u));
    uint8_t result=(uint8_t)(0u-value);
    uint16_t updated=negate8_flags(entry,value,result);
#if ENTITY_INTERACTIONS_MUTATION == 4
    write8_flags(s,s->r.ds,record_offset(s,0x27u),result,updated);
#else
    write8_flags(s,s->r.ds,record_offset(s,0x27u),result,entry);
#endif
    s->r.flags=updated;
    return ready_at(s,tail);
}

LmnEntityInteractionsResult lmn_entity_interactions_core(uint8_t *memory,
    const LmnEntityInteractionsCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    InteractionState s;
    uint16_t pushed_ax=0;
    uint8_t high_nibble,low_nibble;
    unsigned n;
    s.memory=memory;
    s.bus=bus;
    s.r=(LmnRegs){0};
    s.r.cx=call->count;
    s.r.dx=call->auxiliary_value;
    s.r.si=call->record_cursor;
    s.r.di=call->object_cursor;
    s.r.ds=call->data_segment;
    s.r.cs=call->code_segment;
    s.r.ss=call->stack_segment;
    s.r.sp=call->stack_offset;
    s.r.flags=call->flags;
    s.r.ip=CS_ApplyEntityCellInteractions;

    s.r.ax=read16(&s,s.r.ds,s.r.si);
    s.r.bx=read16(&s,s.r.ds,(uint16_t)(s.r.si+2u));
    s.r.flags=sub_flags(s.r.flags,s.r.bx,0x00b0u,16);
    if(((s.r.flags&SF)!=0)==((s.r.flags&OF)!=0))
        return ready_at(&s,RET_2F3A);

#if ENTITY_INTERACTIONS_MUTATION == 3
    /* Wrongly clamp low Y before the original subtract/shift sequence. */
    if(s.r.bx<0x0010u) s.r.bx=0x0010u;
#endif
    {
        uint16_t old=s.r.bx;
        s.r.bx=(uint16_t)(s.r.bx-0x0010u);
        s.r.flags=sub_flags(s.r.flags,old,0x0010u,16);
    }
    for(n=0;n<2;++n) {
        uint16_t old=s.r.ax;
        s.r.ax=(uint16_t)(old>>1);
        s.r.flags=shift_right_flags(s.r.flags,old,s.r.ax,16,0);
    }
#if ENTITY_INTERACTIONS_MUTATION == 1
    for(n=0;n<2;++n) {
        uint16_t old=s.r.bx;
        s.r.bx=(uint16_t)((old>>1)|((old&0x8000u)?0x8000u:0u));
        s.r.flags=shift_right_flags(s.r.flags,old,s.r.bx,16,1);
    }
#else
    for(n=0;n<2;++n) {
        uint16_t old=s.r.bx;
        s.r.bx=(uint16_t)(s.r.bx>>1);
        s.r.flags=shift_right_flags(s.r.flags,old,s.r.bx,16,0);
    }
#endif
    push(&s,s.r.ax);
    push(&s,s.r.dx);
    s.r.ax=s.r.bx;
    s.r.dx=0x01a0u;
    {
        uint32_t product=(uint32_t)s.r.ax*s.r.dx;
        s.r.ax=(uint16_t)product;
        s.r.dx=(uint16_t)(product>>16);
        s.r.flags=multiply_flags(s.r.flags,product);
    }
    s.r.dx=pop(&s);
    s.r.bx=pop(&s);
    {
        uint16_t old=s.r.bx;
        s.r.bx=(uint16_t)(s.r.bx+s.r.ax);
        s.r.flags=add_flags(s.r.flags,old,s.r.ax,16);
    }
    s.r.flags=add_flags(s.r.flags,s.r.bx,0x0012u,16);
    s.r.bx=(uint16_t)(s.r.bx+0x0012u);
    s.r.ax=(uint16_t)((s.r.ax&0xff00u)|read8(&s,s.r.ss,s.r.bx));
    pushed_ax=s.r.ax;
    push(&s,s.r.ax);
    write8(&s,s.r.ds,record_offset(&s,0x2cu),(uint8_t)s.r.ax);
    {
        uint8_t signed_y=read8(&s,s.r.ds,record_offset(&s,0x27u));
        s.r.ax=(signed_y&0x80u) ? (uint16_t)(0xff00u|signed_y):signed_y;
    }
    {
        uint16_t old=s.r.bx;
        s.r.bx=(uint16_t)(s.r.bx-0x0340u);
        s.r.flags=sub_flags(s.r.flags,old,0x0340u,16);
    }
    s.r.flags=add_flags(s.r.flags,s.r.bx,s.r.ax,16);
    s.r.bx=(uint16_t)(s.r.bx+s.r.ax);
    s.r.flags=add_flags(s.r.flags,s.r.bx,s.r.ax,16);
    s.r.bx=(uint16_t)(s.r.bx+s.r.ax);
    s.r.ax=(uint16_t)((s.r.ax&0xff00u)|read8(&s,s.r.ss,s.r.bx));
    write8(&s,s.r.ds,record_offset(&s,0x2bu),(uint8_t)s.r.ax);
    s.r.ax=pop(&s);
#if ENTITY_INTERACTIONS_MUTATION == 2
    s.r.ax=pushed_ax;
#else
    (void)pushed_ax;
#endif
    s.r.ax=(uint16_t)((s.r.ax&0x00ffu)|((s.r.ax&0x00ffu)<<8));
    s.r.flags=logic_flags(s.r.flags,(uint16_t)(s.r.ax&0x000fu),8);
    s.r.ax=(uint16_t)((s.r.ax&0xff00u)|(s.r.ax&0x000fu));
    for(n=0;n<4;++n) {
        uint8_t old=(uint8_t)(s.r.ax>>8);
        uint8_t value=(uint8_t)(old>>1);
        s.r.flags=shift_right_flags(s.r.flags,old,value,8,0);
        s.r.ax=(uint16_t)((s.r.ax&0x00ffu)|((uint16_t)value<<8));
    }
    {
        uint8_t old=(uint8_t)(s.r.ax>>8);
        uint8_t value=(uint8_t)(old&0x0fu);
        s.r.flags=logic_flags(s.r.flags,value,8);
        s.r.ax=(uint16_t)((s.r.ax&0x00ffu)|((uint16_t)value<<8));
    }
    high_nibble=(uint8_t)(s.r.ax>>8);
    low_nibble=(uint8_t)s.r.ax;
    s.r.flags=logic_flags(s.r.flags,low_nibble,8); /* AND AL,AL */
    if(low_nibble==0)
        return ready_at(&s,RET_2F3A);
    for(n=1;n<=6;++n) {
        uint8_t old=(uint8_t)s.r.ax;
        uint8_t value=(uint8_t)(old-1u);
        s.r.ax=(uint16_t)((s.r.ax&0xff00u)|value);
        s.r.flags=decrement8_flags(s.r.flags,old,value);
        low_nibble=value;
        if(value==0) {
            switch(n) {
            case 1: return transition_one(&s,pc_binding,sound_binding);
            case 2: {
                uint8_t record=read8(&s,s.r.ds,record_offset(&s,0x27u));
                s.r.flags=sub_flags(s.r.flags,record,0xffu,8);
                if(record==0xffu) return ready_at(&s,RET_2F3A);
                return negative_record_byte(&s,RET_2FAB);
            }
            case 3: {
                uint8_t record=read8(&s,s.r.ds,record_offset(&s,0x27u));
                s.r.flags=sub_flags(s.r.flags,record,0x01u,8);
                if(record==0x01u) return ready_at(&s,RET_2F3A);
                return negative_record_byte(&s,RET_2FB5);
            }
            case 4: {
#if ENTITY_INTERACTIONS_MUTATION == 5
                uint8_t cached_sound=0;
#endif
                s.r.ax=(uint16_t)((s.r.ax&0x00ffu)|
                                  ((uint16_t)high_nibble<<8));
                s.r.ax=(uint16_t)((s.r.ax&0xff00u)|high_nibble);
                s.r.ax&=0x00ffu; /* MOV AL,AH; XOR AH,AH. */
                s.r.flags=logic_flags(s.r.flags,0,8);
                s.r.dx=0x001cu;
                {
                    uint32_t product=(uint32_t)s.r.ax*s.r.dx;
                    s.r.ax=(uint16_t)product;
                    s.r.dx=(uint16_t)(product>>16);
                    s.r.flags=multiply_flags(s.r.flags,product);
                }
                s.r.di=s.r.ax;
                {
                    uint16_t old=s.r.di;
                    s.r.di=(uint16_t)(s.r.di+SEG09A9_LevelObjectGraphicsRecords);
                    s.r.flags=add_flags(s.r.flags,old,
                        SEG09A9_LevelObjectGraphicsRecords,16);
                }
                {
                    uint16_t entry=s.r.flags;
                    uint16_t object=read16(&s,s.r.ds,s.r.di);
                    s.r.flags=logic_flags(entry,(uint16_t)(object&2u),16);
                    if(!(s.r.flags&ZF)) return ready_at(&s,RET_2F3A);
                }
#if ENTITY_INTERACTIONS_MUTATION == 5
                cached_sound=read8(&s,s.r.ds,(uint16_t)(s.r.di+0x1bu));
#endif
                {
                    uint16_t entry=s.r.flags;
                    uint16_t object=read16(&s,s.r.ds,s.r.di);
                    uint16_t value=(uint16_t)(object|2u);
                    write16_flags(&s,s.r.ds,s.r.di,value,entry);
                    s.r.flags=logic_flags(entry,value,16);
                }
                write8(&s,s.r.ds,record_offset(&s,0x26u),0xffu);
                compare_external_sound(&s);
                if(!(s.r.flags&ZF)) return ready_at(&s,RET_2F3A);
                test_sound_options(&s,0x03u);
                if(s.r.flags&ZF) return ready_at(&s,RET_2F3A);
#if ENTITY_INTERACTIONS_MUTATION == 5
                s.r.ax=(uint16_t)((s.r.ax&0xff00u)|cached_sound);
#else
                s.r.ax=(uint16_t)((s.r.ax&0xff00u)|
                    read8(&s,s.r.ds,(uint16_t)(s.r.di+0x1bu)));
#endif
                s.r.flags=logic_flags(s.r.flags,(uint8_t)s.r.ax,8);
                if(!(s.r.flags&ZF)) {
                    s.r.ax=(uint16_t)((s.r.ax&0x00ffu)|0x0400u);
                    {
                        uint16_t status=invoke_sound(&s,
                            CS_EntityInteractionObjectSoundReturn,sound_binding);
                        if(status!=LMN_ENTITY_INTERACTION_RET_READY)
                            return result(&s,status);
                    }
                    return ready_at(&s,CS_EntityInteractionObjectSoundReturn);
                }
                return ready_at(&s,RET_2F3A);
            }
            case 5: return transition_five(&s,sound_binding);
            case 6: return transition_six(&s,sound_binding);
            default: break;
            }
        }
    }
    (void)low_nibble;
    return ready_at(&s,RET_2F3A);
}

uint16_t lmn_entity_interactions_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityInteractionsCall call;
    LmnEntityInteractionsResult out;
#if ENTITY_INTERACTIONS_MUTATION == 8
    uint16_t cached_return=0;
#endif
    call.count=registers->cx;
    call.auxiliary_value=registers->dx;
    call.record_cursor=registers->si;
    call.object_cursor=registers->di;
    call.data_segment=registers->ds;
    call.code_segment=registers->cs;
    call.stack_segment=registers->ss;
    call.stack_offset=registers->sp;
    call.flags=registers->flags;
#if ENTITY_INTERACTIONS_MUTATION == 8
    {
        InteractionState s;
        s.memory=memory;s.bus=bus;s.r=*registers;
        cached_return=read16(&s,s.r.ss,s.r.sp);
    }
#endif
    out=lmn_entity_interactions_core(memory,&call,pc_binding,sound_binding,bus);
    registers->ax=out.value;
    registers->bx=out.map_cursor;
    registers->cx=out.count;
    registers->dx=out.auxiliary_value;
    registers->si=out.record_cursor;
    registers->di=out.object_cursor;
    registers->ds=out.data_segment;
    registers->cs=out.code_segment;
    registers->ss=out.stack_segment;
    registers->sp=out.stack_offset;
    registers->flags=out.flags;
    registers->ip=out.continuation;
    if(out.status==LMN_ENTITY_INTERACTION_RET_READY) {
#if ENTITY_INTERACTIONS_MUTATION == 8
        registers->ip=cached_return;
#else
        {
            InteractionState s;
            s.memory=memory;s.bus=bus;s.r=*registers;
            registers->ip=read16(&s,registers->ss,registers->sp);
        }
#endif
        registers->sp=(uint16_t)(registers->sp+2u);
    }
    return out.status;
}

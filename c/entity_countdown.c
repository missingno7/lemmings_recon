#include "entity_countdown.h"
#include "lemmings_sym.h"

#ifndef ENTITY_COUNTDOWN_MUTATION
#define ENTITY_COUNTDOWN_MUTATION 0
#endif

enum {
    CF=0x0001u, PF=0x0004u, AF=0x0010u, ZF=0x0040u,
    SF=0x0080u, OF=0x0800u, ARITH=0x08d5u
};

typedef struct CountdownState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t value,ds,cs,ss,sp,si,flags,continuation;
} CountdownState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(CountdownState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(CountdownState *s,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read_byte(CountdownState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write_byte(CountdownState *s,uint16_t segment,uint16_t offset,
                       uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

/* A real-mode word's high byte is the next physical byte, with 20-bit wrap. */
static uint16_t read_word(CountdownState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_word(CountdownState *s,uint16_t segment,uint16_t offset,
                       uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static uint16_t record_offset(const CountdownState *s,uint16_t displacement) {
    return (uint16_t)(s->si+displacement);
}

static uint16_t even_parity(uint8_t value) {
    unsigned i,ones=0;
    for(i=0;i<8;++i) ones+=(value>>i)&1u;
    return (ones&1u) ? 0u:PF;
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned width) {
    uint16_t out=(uint16_t)(flags&~ARITH);
    uint16_t sign=width==8 ? 0x0080u:0x8000u;
    if(!(uint8_t)value) out|=PF;
    else out|=even_parity((uint8_t)value);
    if(!value) out|=ZF;
    if(value&sign) out|=SF;
    return out;
}

static uint16_t compare8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t result=(uint8_t)(left-right);
    uint16_t out=(uint16_t)((flags&~ARITH)|even_parity(result));
    if(!result) out|=ZF;
    if(result&0x80u) out|=SF;
    if(left<right) out|=CF;
    if((left^right^result)&0x10u) out|=AF;
    if(((left^right)&(left^result)&0x80u)!=0) out|=OF;
    return out;
}

static uint16_t decrement8_flags(uint16_t flags,uint8_t old_value,
                                 uint8_t new_value) {
    uint16_t out=(uint16_t)((flags&~(PF|AF|ZF|SF|OF))|even_parity(new_value));
    if(!new_value) out|=ZF;
    if(new_value&0x80u) out|=SF;
    if((old_value&0x0fu)==0) out|=AF;
    if(old_value==0x80u) out|=OF;
    return out;
}

#if ENTITY_COUNTDOWN_MUTATION != 7
static uint16_t pop_stack_word(CountdownState *s) {
    uint16_t value=read_word(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}
#endif

static LmnEntityCountdownResult make_result(const CountdownState *s,
                                             uint16_t cursor,
                                             uint16_t status) {
    LmnEntityCountdownResult out;
    out.value=s->value;
    out.data_segment=s->ds;
    out.code_segment=s->cs;
    out.stack_offset=s->sp;
    out.record_cursor=cursor;
    out.flags=s->flags;
    out.continuation=s->continuation;
    out.status=status;
    return out;
}

static uint16_t sound_status(uint16_t status) {
    switch(status) {
    case LMN_SOUND_INTERRUPT_UNBOUND_VECTOR:
        return LMN_ENTITY_COUNTDOWN_UNBOUND_VECTOR;
    case LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE:
        return LMN_ENTITY_COUNTDOWN_UNTRANSLATED_SOUND;
    case LMN_SOUND_INTERRUPT_CHANGED_RETURN:
        return LMN_ENTITY_COUNTDOWN_CHANGED_SOUND_RETURN;
    default:
        return LMN_ENTITY_COUNTDOWN_READY;
    }
}

static uint16_t invoke_sound(CountdownState *s,uint16_t return_offset,
    const LmnSoundDriverBinding *binding,const LmnRasterBus *bus) {
    LmnSoundInterruptCall call;
    LmnSoundInterruptResult result;
    call.value=s->value;
    call.data_segment=s->ds;
    call.code_segment=s->cs;
    call.stack_segment=s->ss;
    call.stack_offset=s->sp;
    call.flags=s->flags;
    call.return_offset=return_offset;
    result=lmn_sound_interrupt61_core(s->memory,&call,binding,bus);
    s->value=result.value;
    s->ds=result.data_segment;
    s->cs=result.code_segment;
    s->sp=result.stack_offset;
    s->flags=result.flags;
    s->continuation=result.continuation;
    return sound_status(result.status);
}

static uint8_t countdown_byte(CountdownState *s) {
    uint8_t old_value=read_byte(s,s->ds,record_offset(s,0x20u));
    uint8_t new_value;
    uint16_t entry_flags=s->flags;
#if ENTITY_COUNTDOWN_MUTATION == 1
    new_value=old_value ? (uint8_t)(old_value-1u):0u;
#else
    new_value=(uint8_t)(old_value-1u);
#endif
#if ENTITY_COUNTDOWN_MUTATION == 6
    s->flags=decrement8_flags(entry_flags,old_value,new_value);
    write_byte(s,s->ds,record_offset(s,0x20u),new_value);
#else
    write_byte(s,s->ds,record_offset(s,0x20u),new_value);
    s->flags=decrement8_flags(entry_flags,old_value,new_value);
#endif
    return new_value;
}

static uint16_t test_transition_word(CountdownState *s,uint16_t mask,
                                     uint16_t *tested_word) {
    uint16_t value=read_word(s,s->ds,record_offset(s,0x08u));
    if(tested_word) *tested_word=value;
    s->flags=logic_flags(s->flags,(uint16_t)(value&mask),16);
    return value;
}

static void or_transition_word(CountdownState *s,uint16_t immediate) {
    uint16_t offset=record_offset(s,0x08u);
    uint16_t old_value=read_word(s,s->ds,offset);
    uint16_t new_value=(uint16_t)(old_value|immediate);
    write_word(s,s->ds,offset,new_value);
    s->flags=logic_flags(s->flags,new_value,16);
}

static void write_record_byte(CountdownState *s,uint16_t displacement,
                              uint8_t value) {
    write_byte(s,s->ds,record_offset(s,displacement),value);
}

static void write_record_word(CountdownState *s,uint16_t displacement,
                              uint16_t value) {
    write_word(s,s->ds,record_offset(s,displacement),value);
}

static void and_record_byte(CountdownState *s,uint16_t displacement,
                            uint8_t mask) {
    uint16_t offset=record_offset(s,displacement);
    uint8_t old_value=read_byte(s,s->ds,offset);
    uint8_t new_value=(uint8_t)(old_value&mask);
    write_byte(s,s->ds,offset,new_value);
    s->flags=logic_flags(s->flags,new_value,8);
}

static int sound_gate_open(CountdownState *s) {
    uint8_t enabled=read_byte(s,s->ds,SEG09A9_ExternalSoundDriverEnabled);
    s->flags=compare8_flags(s->flags,enabled,0xffu);
    if(enabled!=0xffu) return 0;
    {
        uint8_t options=read_byte(s,s->ds,SEG09A9_SoundOptionBits);
        s->flags=logic_flags(s->flags,(uint8_t)(options&0x03u),8);
        return (options&0x03u)!=0;
    }
}

static void xor_al_zero(CountdownState *s) {
#if ENTITY_COUNTDOWN_MUTATION == 5
    s->value=0;
#else
    s->value=(uint16_t)(s->value&0xff00u);
#endif
    s->flags=logic_flags(s->flags,0,8);
}

static uint16_t slot_word(CountdownState *s,uint16_t index) {
    return read_word(s,s->ds,
        (uint16_t)(SEG09A9_DrawingCallbackSlots+index));
}

LmnEntityCountdownResult lmn_advance_entity_countdown_core(uint8_t *memory,
    const LmnEntityCountdownCall *call,const LmnSoundDriverBinding *binding,
    const LmnRasterBus *bus) {
    CountdownState s;
    uint16_t cursor=call->record_cursor;
#if ENTITY_COUNTDOWN_MUTATION == 4
    uint16_t tested_word=0;
#endif
    uint8_t remaining;
#if ENTITY_COUNTDOWN_MUTATION == 7
    uint16_t cached_outer_return;
#endif
    s.memory=memory;
    s.bus=bus;
    s.value=call->value;
    s.ds=call->data_segment;
    s.cs=call->code_segment;
    s.ss=call->stack_segment;
    s.sp=call->stack_offset;
    s.si=call->record_cursor;
    s.flags=call->flags;
    s.continuation=CS_AdvanceEntityCountdown;
#if ENTITY_COUNTDOWN_MUTATION == 7
    cached_outer_return=read_word(&s,s.ss,s.sp);
#endif
    s.value=(uint16_t)((s.value&0xff00u)|1u); /* MOV AL,1 */
    remaining=countdown_byte(&s);
    if(remaining) {
        s.continuation=CS_EntityCountdownReturn;
        s.flags=logic_flags(s.flags,(uint8_t)s.value,8); /* AND AL,AL */
#if ENTITY_COUNTDOWN_MUTATION == 7
        s.continuation=cached_outer_return;
#endif
        return make_result(&s,cursor,LMN_ENTITY_COUNTDOWN_READY);
    }

#if ENTITY_COUNTDOWN_MUTATION == 2
#if ENTITY_COUNTDOWN_MUTATION == 4
    (void)test_transition_word(&s,0x5004u,&tested_word);
#else
    (void)test_transition_word(&s,0x5004u,NULL);
#endif
#else
#if ENTITY_COUNTDOWN_MUTATION == 4
    (void)test_transition_word(&s,0x5404u,&tested_word);
#else
    (void)test_transition_word(&s,0x5404u,NULL);
#endif
#endif
    if(!(s.flags&ZF)) {
#if ENTITY_COUNTDOWN_MUTATION == 3
        uint16_t selected_slot=slot_word(&s,0x0eu);
#endif
        or_transition_word(&s,0x0002u);
        write_record_word(&s,0x0au,0x0008u);
        write_record_word(&s,0x0cu,0x180bu);
        write_record_word(&s,0x10u,0x0280u);
        write_record_word(&s,0x12u,0x01e0u);
        write_record_byte(&s,0x28u,0);
        write_record_word(&s,0x06u,0xffe7u);
        write_record_word(&s,0x04u,0xfff0u);
        write_record_byte(&s,0x29u,0);
#if ENTITY_COUNTDOWN_MUTATION == 3
        s.value=selected_slot;
#else
        s.value=slot_word(&s,0x0eu);
#endif
        write_record_word(&s,0x14u,s.value);
        write_record_byte(&s,0x2au,0);
        write_record_byte(&s,0x22u,0x0fu);
#if ENTITY_COUNTDOWN_MUTATION == 8
        and_record_byte(&s,0x24u,0x7fu);
#else
        and_record_byte(&s,0x24u,0x01u);
#endif
        if(sound_gate_open(&s)) {
            s.value=0x040cu;
            s.continuation=CS_EntityCountdownMaskedSoundReturn;
            {
                uint16_t status=invoke_sound(&s,
                    CS_EntityCountdownMaskedSoundReturn,binding,bus);
                if(status!=LMN_ENTITY_COUNTDOWN_READY)
                    return make_result(&s,cursor,status);
            }
        } else {
            s.continuation=CS_EntityCountdownMaskedSoundReturn;
        }

#if ENTITY_COUNTDOWN_MUTATION == 4
        s.flags=logic_flags(s.flags,(uint16_t)(tested_word&0x0004u),16);
        if(tested_word&0x0004u) write_record_byte(&s,0x22u,0);
#else
        {
            uint16_t live_word=read_word(&s,s.ds,record_offset(&s,0x08u));
            s.flags=logic_flags(s.flags,(uint16_t)(live_word&0x0004u),16);
            if(live_word&0x0004u) write_record_byte(&s,0x22u,0);
        }
#endif
        xor_al_zero(&s);
        s.continuation=CS_EntityCountdownMaskedReturn;
#if ENTITY_COUNTDOWN_MUTATION == 7
        s.continuation=cached_outer_return;
#endif
        return make_result(&s,cursor,LMN_ENTITY_COUNTDOWN_READY);
    }

    {
#if ENTITY_COUNTDOWN_MUTATION == 3
        uint16_t selected_slot=slot_word(&s,0x00u);
#endif
        or_transition_word(&s,0x8000u);
        write_record_word(&s,0x0au,0x0008u);
        write_record_word(&s,0x0cu,0x153bu);
        write_record_word(&s,0x10u,0x005au);
        write_record_word(&s,0x12u,0x003cu);
        write_record_byte(&s,0x28u,0);
        write_record_word(&s,0x04u,0xfff8u);
        write_record_word(&s,0x06u,0xfff6u);
        write_record_byte(&s,0x29u,0);
#if ENTITY_COUNTDOWN_MUTATION == 3
        s.value=selected_slot;
#else
        s.value=slot_word(&s,0x00u);
#endif
        write_record_word(&s,0x14u,s.value);
        write_record_byte(&s,0x2au,0);
#if ENTITY_COUNTDOWN_MUTATION == 8
        and_record_byte(&s,0x24u,0x7fu);
#else
        and_record_byte(&s,0x24u,0x01u);
#endif
        if(sound_gate_open(&s)) {
            s.value=0x0405u;
            s.continuation=CS_EntityCountdownSoundReturn;
            {
                uint16_t status=invoke_sound(&s,
                    CS_EntityCountdownSoundReturn,binding,bus);
                if(status!=LMN_ENTITY_COUNTDOWN_READY)
                    return make_result(&s,cursor,status);
            }
        } else {
            s.continuation=CS_EntityCountdownSoundReturn;
        }
        xor_al_zero(&s);
        s.flags=logic_flags(s.flags,(uint8_t)s.value,8); /* AND AL,AL */
        s.continuation=CS_EntityCountdownReturn;
#if ENTITY_COUNTDOWN_MUTATION == 7
        s.continuation=cached_outer_return;
#endif
        return make_result(&s,cursor,LMN_ENTITY_COUNTDOWN_READY);
    }
}

uint16_t lmn_advance_entity_countdown_adapter(uint8_t *memory,LmnRegs *r,
    const LmnSoundDriverBinding *binding,const LmnRasterBus *bus) {
    LmnEntityCountdownCall call;
    LmnEntityCountdownResult out;
    call.value=r->ax;
    call.data_segment=r->ds;
    call.code_segment=r->cs;
    call.stack_segment=r->ss;
    call.stack_offset=r->sp;
    call.record_cursor=r->si;
    call.flags=r->flags;
    out=lmn_advance_entity_countdown_core(memory,&call,binding,bus);
    r->ax=out.value;
    r->ds=out.data_segment;
    r->cs=out.code_segment;
    r->sp=out.stack_offset;
    r->si=out.record_cursor;
    r->flags=out.flags;
    r->ip=out.continuation;
    if(out.status==LMN_ENTITY_COUNTDOWN_READY) {
#if ENTITY_COUNTDOWN_MUTATION == 7
        r->ip=out.continuation;
        r->sp=(uint16_t)(r->sp+2u);
#else
        {
            CountdownState stack_state;
            stack_state.memory=memory;
            stack_state.bus=bus;
            stack_state.value=r->ax;
            stack_state.ds=r->ds;
            stack_state.cs=r->cs;
            stack_state.ss=r->ss;
            stack_state.sp=r->sp;
            stack_state.si=r->si;
            stack_state.flags=r->flags;
            stack_state.continuation=r->ip;
            r->ip=pop_stack_word(&stack_state);
            r->sp=stack_state.sp;
        }
#endif
    }
    return out.status;
}

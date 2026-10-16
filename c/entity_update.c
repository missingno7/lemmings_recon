#include "entity_update.h"
#include "lemmings_sym.h"

#ifndef ENTITY_UPDATE_MUTATION
#define ENTITY_UPDATE_MUTATION 0
#endif

enum {
    CF=0x0001u, PF=0x0004u, AF=0x0010u, ZF=0x0040u,
    SF=0x0080u, OF=0x0800u, ARITH=0x08d5u
};

typedef struct UpdateRegisters {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} UpdateRegisters;

typedef struct UpdateState {
    uint8_t *memory;
    const LmnPcSpeakerBinding *pc_binding;
    const LmnSoundDriverBinding *sound_binding;
    const LmnRasterBus *bus;
    UpdateRegisters r;
    uint16_t continuation,status,child_entry,child_status;
} UpdateState;

#define COPY_REGISTERS(dst,src) do { \
    (dst).value=(src).value; \
    (dst).map_cursor=(src).map_cursor; \
    (dst).count=(src).count; \
    (dst).auxiliary_value=(src).auxiliary_value; \
    (dst).record_cursor=(src).record_cursor; \
    (dst).object_cursor=(src).object_cursor; \
    (dst).candidate_y=(src).candidate_y; \
    (dst).code_segment=(src).code_segment; \
    (dst).data_segment=(src).data_segment; \
    (dst).extra_segment=(src).extra_segment; \
    (dst).stack_segment=(src).stack_segment; \
    (dst).stack_offset=(src).stack_offset; \
    (dst).flags=(src).flags; \
} while(0)

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+(uint32_t)offset)&0xfffffu);
}

static uint8_t read_physical(UpdateState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->r.flags);
    return s->memory[address];
}

static void write_physical(UpdateState *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(UpdateState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(UpdateState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value,s->r.flags);
}

/* Real-mode word accesses are two successive physical bytes. */
static uint16_t read16(UpdateState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(UpdateState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,s->r.flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),s->r.flags);
}

static uint16_t even_parity(uint8_t value) {
    unsigned i,ones=0;
    for(i=0;i<8u;++i)ones+=(value>>i)&1u;
    return (ones&1u)?0u:PF;
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    uint16_t out=(uint16_t)(flags&~ARITH);
    uint16_t mask=bits==8u?0x00ffu:0xffffu;
    uint16_t sign=bits==8u?0x0080u:0x8000u;
    value=(uint16_t)(value&mask);
    out=(uint16_t)(out|even_parity((uint8_t)value));
    if(value==0u)out=(uint16_t)(out|ZF);
    if(value&sign)out=(uint16_t)(out|SF);
    return out;
}

static uint16_t compare8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t result=(uint8_t)(left-right);
    uint16_t out=(uint16_t)((flags&~ARITH)|even_parity(result));
    if(result==0u)out=(uint16_t)(out|ZF);
    if(result&0x80u)out=(uint16_t)(out|SF);
    if(left<right)out=(uint16_t)(out|CF);
    if((left^right^result)&0x10u)out=(uint16_t)(out|AF);
    if(((left^right)&(left^result)&0x80u)!=0u)out=(uint16_t)(out|OF);
    return out;
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)sum;
    uint16_t out=(uint16_t)((flags&~ARITH)|even_parity((uint8_t)result));
    if(sum>0xffffu)out=(uint16_t)(out|CF);
    if((left^right^result)&AF)out=(uint16_t)(out|AF);
    if((~(left^right)&(left^result)&0x8000u)!=0u)out=(uint16_t)(out|OF);
    if(result==0u)out=(uint16_t)(out|ZF);
    if(result&0x8000u)out=(uint16_t)(out|SF);
    return out;
}

static uint16_t inc8_flags(uint16_t flags,uint8_t old_value,uint8_t new_value) {
    uint16_t out=(uint16_t)((flags&~(PF|AF|ZF|SF|OF))|even_parity(new_value));
    if(new_value==0u)out=(uint16_t)(out|ZF);
    if(new_value&0x80u)out=(uint16_t)(out|SF);
    if((old_value&0x0fu)==0x0fu)out=(uint16_t)(out|AF);
    if(old_value==0x7fu)out=(uint16_t)(out|OF);
    return out;
}

static uint16_t dec8_flags(uint16_t flags,uint8_t old_value,uint8_t new_value) {
    uint16_t out=(uint16_t)((flags&~(PF|AF|ZF|SF|OF))|even_parity(new_value));
    if(new_value==0u)out=(uint16_t)(out|ZF);
    if(new_value&0x80u)out=(uint16_t)(out|SF);
    if((old_value&0x0fu)==0u)out=(uint16_t)(out|AF);
    if(old_value==0x80u)out=(uint16_t)(out|OF);
    return out;
}

static void push16(UpdateState *s,uint16_t value) {
    s->r.stack_offset=(uint16_t)(s->r.stack_offset-2u);
    write16(s,s->r.stack_segment,s->r.stack_offset,value);
}

static uint16_t pop16(UpdateState *s) {
    uint16_t value=read16(s,s->r.stack_segment,s->r.stack_offset);
    s->r.stack_offset=(uint16_t)(s->r.stack_offset+2u);
    return value;
}

static LmnEntityUpdateResult result_of(const UpdateState *s) {
    LmnEntityUpdateResult out;
    out.value=s->r.value;out.map_cursor=s->r.map_cursor;
    out.count=s->r.count;out.auxiliary_value=s->r.auxiliary_value;
    out.record_cursor=s->r.record_cursor;out.object_cursor=s->r.object_cursor;
    out.candidate_y=s->r.candidate_y;out.code_segment=s->r.code_segment;
    out.data_segment=s->r.data_segment;out.extra_segment=s->r.extra_segment;
    out.stack_segment=s->r.stack_segment;out.stack_offset=s->r.stack_offset;
    out.flags=s->r.flags;out.continuation=s->continuation;
    out.status=s->status;out.child_entry=s->child_entry;
    out.child_status=s->child_status;
    return out;
}

static void increment_global(UpdateState *s,uint16_t offset) {
    uint8_t old_value=read8(s,s->r.data_segment,offset);
    uint8_t new_value=(uint8_t)(old_value+1u);
#if ENTITY_UPDATE_MUTATION == 5
    s->r.flags=inc8_flags(s->r.flags,old_value,new_value);
    write8(s,s->r.data_segment,offset,new_value);
#else
    write8(s,s->r.data_segment,offset,new_value);
    s->r.flags=inc8_flags(s->r.flags,old_value,new_value);
#endif
}

/* Child call/result packets share the ordinary 13-register prefix. The
   named assignments keep that translation explicit and portable. */
#define RUN_CHILD(entry_,CallType,ResultType,ready_,expression_) \
    do { \
        CallType child_call; \
        ResultType child_result; \
        COPY_REGISTERS(child_call,s->r); \
        child_result=(expression_); \
        COPY_REGISTERS(s->r,child_result); \
        if(child_result.status!=(ready_)) { \
            s->continuation=child_result.continuation; \
            s->status=LMN_ENTITY_UPDATE_CHILD_BOUNDARY; \
            s->child_entry=(uint16_t)(entry_); \
            s->child_status=(uint16_t)child_result.status; \
            return 1; \
        } \
    } while(0)

#define RUN_ENTRY_CHILD(entry_,entry_value_,CallType,ResultType,ready_,expression_) \
    do { \
        CallType child_call; \
        ResultType child_result; \
        child_call.entry=(uint16_t)(entry_value_); \
        COPY_REGISTERS(child_call,s->r); \
        child_result=(expression_); \
        COPY_REGISTERS(s->r,child_result); \
        if(child_result.status!=(ready_)) { \
            s->continuation=child_result.continuation; \
            s->status=LMN_ENTITY_UPDATE_CHILD_BOUNDARY; \
            s->child_entry=(uint16_t)(entry_); \
            s->child_status=(uint16_t)child_result.status; \
            return 1; \
        } \
    } while(0)

static int dispatch_state(UpdateState *s,uint16_t entry) {
    switch(entry) {
    case CS_AdvanceEntityZeroState:
        RUN_CHILD(CS_AdvanceEntityZeroState,LmnEntityZeroStateCall,
            LmnEntityZeroStateResult,LMN_ENTITY_ZERO_READY,
            (lmn_entity_zero_state_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0002:
        RUN_CHILD(CS_AdvanceEntityState0002,LmnEntityState2Call,
            LmnEntityState2Result,LMN_ENTITY_STATE2_READY,
            (lmn_entity_state2_core(s->memory,&child_call,s->pc_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0004:
        RUN_CHILD(CS_AdvanceEntityState0004,LmnEntityState4Call,
            LmnEntityState4Result,LMN_ENTITY_STATE4_READY,
            (lmn_entity_state4_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState8000:
        RUN_ENTRY_CHILD(CS_AdvanceEntityState8000,LMN_ENTITY_LATE_STATE_8000,
            LmnEntityLateStatesCall,
            LmnEntityLateStatesResult,LMN_ENTITY_LATE_READY,
            (lmn_entity_late_states_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0001:
    case CS_AdvanceEntityState1000:
    case CS_AdvanceEntityState2000:
    case CS_AdvanceEntityState4000: {
        uint16_t entry_kind=entry==CS_AdvanceEntityState0001 ?
            LMN_ENTITY_CADENCE_STATE_0001 :
            entry==CS_AdvanceEntityState1000 ? LMN_ENTITY_CADENCE_STATE_1000 :
            entry==CS_AdvanceEntityState2000 ? LMN_ENTITY_CADENCE_STATE_2000 :
            LMN_ENTITY_CADENCE_STATE_4000;
        RUN_ENTRY_CHILD(entry,entry_kind,LmnEntityCadenceCall,LmnEntityCadenceResult,
            LMN_ENTITY_CADENCE_READY,
            (lmn_entity_cadence_core(s->memory,&child_call,s->bus)));
        break;
    }
    case CS_AdvanceEntityState0008:
        RUN_CHILD(CS_AdvanceEntityState0008,LmnEntityState8Call,
            LmnEntityState8Result,LMN_ENTITY_STATE8_READY,
            (lmn_entity_state8_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0010:
        RUN_CHILD(CS_AdvanceEntityState0010,LmnEntityState10Call,
            LmnEntityState10Result,LMN_ENTITY_STATE10_READY,
            (lmn_entity_state10_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0020:
        RUN_CHILD(CS_AdvanceEntityState0020,LmnEntityState20Call,
            LmnEntityState20Result,LMN_ENTITY_STATE20_READY,
            (lmn_entity_state20_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0040:
        RUN_CHILD(CS_AdvanceEntityState0040,LmnEntityState40Call,
            LmnEntityState40Result,LMN_ENTITY_STATE40_READY,
            (lmn_entity_state40_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0080:
        RUN_CHILD(CS_AdvanceEntityState0080,LmnEntityState80Call,
            LmnEntityState80Result,LMN_ENTITY_STATE80_READY,
            (lmn_entity_state80_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0100:
        RUN_CHILD(CS_AdvanceEntityState0100,LmnEntityState100Call,
            LmnEntityState100Result,LMN_ENTITY_STATE100_READY,
            (lmn_entity_state100_core(s->memory,&child_call,s->bus)));
        break;
    case CS_AdvanceEntityState0200:
        RUN_CHILD(CS_AdvanceEntityState0200,LmnEntityState200Call,
            LmnEntityState200Result,LMN_ENTITY_STATE200_READY,
            (lmn_entity_state200_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0400:
        RUN_CHILD(CS_AdvanceEntityState0400,LmnEntityState400Call,
            LmnEntityState400Result,LMN_ENTITY_STATE400_READY,
            (lmn_entity_state400_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityState0800:
        RUN_CHILD(CS_AdvanceEntityState0800,LmnEntityState800Call,
            LmnEntityState800Result,LMN_ENTITY_STATE800_READY,
            (lmn_entity_state800_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_AdvanceEntityFlag80Override:
        RUN_ENTRY_CHILD(CS_AdvanceEntityFlag80Override,
            LMN_ENTITY_LATE_FLAG80_OVERRIDE,
            LmnEntityLateStatesCall,LmnEntityLateStatesResult,
            LMN_ENTITY_LATE_READY,
            (lmn_entity_late_states_core(s->memory,&child_call,s->pc_binding,
                s->sound_binding,s->bus)));
        break;
    case CS_FinishEntityInteractions: {
        LmnEntityFinishCall child_call;
        LmnEntityFinishResult child_result;
        child_call.entry=LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8;
        COPY_REGISTERS(child_call,s->r);
        child_result=lmn_entity_finish_core(s->memory,&child_call,
            s->pc_binding,s->sound_binding,s->bus);
        COPY_REGISTERS(s->r,child_result);
        if(child_result.status!=LMN_ENTITY_FINISH_RETURNED) {
            s->continuation=child_result.continuation;
            s->status=LMN_ENTITY_UPDATE_CHILD_BOUNDARY;
            s->child_entry=CS_FinishEntityInteractions;
            s->child_status=child_result.status;
            return 1;
        }
        break;
    }
    default:
        return 1;
    }
    s->continuation=CS_EntityIterationTail;
    return 0;
}

static uint16_t select_state(UpdateState *s,uint16_t ax) {
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0002u),16u);
    if(ax&0x0002u)return CS_AdvanceEntityState0002;
#if ENTITY_UPDATE_MUTATION == 1
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0004u),16u);
    if(ax&0x0004u)return CS_AdvanceEntityState0004;
#endif
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x8000u),16u);
#if ENTITY_UPDATE_MUTATION != 8
    if(ax&0x8000u)return CS_AdvanceEntityState8000;
#endif
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0004u),16u);
    if(ax&0x0004u)return CS_AdvanceEntityState0004;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0400u),16u);
    if(ax&0x0400u)return CS_AdvanceEntityState0400;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0001u),16u);
    if(ax&0x0001u)return CS_AdvanceEntityState0001;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0008u),16u);
    if(ax&0x0008u)return CS_AdvanceEntityState0008;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0010u),16u);
    if(ax&0x0010u)return CS_AdvanceEntityState0010;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0020u),16u);
    if(ax&0x0020u)return CS_AdvanceEntityState0020;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0040u),16u);
    if(ax&0x0040u)return CS_AdvanceEntityState0040;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0080u),16u);
    if(ax&0x0080u)return CS_AdvanceEntityState0080;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0100u),16u);
    if(ax&0x0100u)return CS_AdvanceEntityState0100;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0200u),16u);
    if(ax&0x0200u)return CS_AdvanceEntityState0200;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x0800u),16u);
    if(ax&0x0800u)return CS_AdvanceEntityState0800;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x1000u),16u);
    if(ax&0x1000u)return CS_AdvanceEntityState1000;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x2000u),16u);
    if(ax&0x2000u)return CS_AdvanceEntityState2000;
    s->r.flags=logic_flags(s->r.flags,(uint16_t)(ax&0x4000u),16u);
    if(ax&0x4000u)return CS_AdvanceEntityState4000;
    return CS_FinishEntityInteractions;
}

static int configure_readback(UpdateState *s) {
    LmnEntityReadbackResult child_result;
    uint16_t actual_return;
#if ENTITY_UPDATE_MUTATION == 6
    uint16_t cached_return;
#endif
    push16(s,CS_EntityUpdateAfterReadbackCall);
#if ENTITY_UPDATE_MUTATION == 6
    cached_return=read16(s,s->r.stack_segment,s->r.stack_offset);
#endif
    child_result=lmn_configure_entity_readback_core(s->memory,
        s->r.data_segment,s->r.stack_segment,s->r.flags,s->bus);
    s->r.value=child_result.value;
    s->r.extra_segment=child_result.output_segment;
    s->r.auxiliary_value=child_result.port;
    s->r.flags=child_result.flags;
    actual_return=pop16(s);
#if ENTITY_UPDATE_MUTATION == 6
    actual_return=cached_return;
#endif
    if(actual_return!=CS_EntityUpdateAfterReadbackCall) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_UPDATE_CHANGED_CALL_RETURN;
        s->child_entry=CS_ConfigureEntityPixelReadback;
        s->child_status=LMN_ENTITY_UPDATE_NO_CHILD_STATUS;
        return 1;
    }
    s->continuation=CS_EntityUpdateAfterReadbackCall;
    return 0;
}

static int call_countdown(UpdateState *s) {
    LmnEntityCountdownCall child_call;
    LmnEntityCountdownResult child_result;
    uint16_t actual_return;
#if ENTITY_UPDATE_MUTATION == 7
    uint16_t cached_return;
#endif
    push16(s,CS_EntityUpdateAfterCountdownCall);
#if ENTITY_UPDATE_MUTATION == 7
    cached_return=read16(s,s->r.stack_segment,s->r.stack_offset);
#endif
    child_call.value=s->r.value;
    child_call.data_segment=s->r.data_segment;
    child_call.code_segment=s->r.code_segment;
    child_call.stack_segment=s->r.stack_segment;
    child_call.stack_offset=s->r.stack_offset;
    child_call.record_cursor=s->r.record_cursor;
    child_call.flags=s->r.flags;
    child_result=lmn_advance_entity_countdown_core(s->memory,&child_call,
        s->sound_binding,s->bus);
    s->r.value=child_result.value;
    s->r.data_segment=child_result.data_segment;
    s->r.code_segment=child_result.code_segment;
    s->r.stack_offset=child_result.stack_offset;
    s->r.record_cursor=child_result.record_cursor;
    s->r.flags=child_result.flags;
    if(child_result.status!=LMN_ENTITY_COUNTDOWN_READY) {
        s->continuation=child_result.continuation;
        s->status=LMN_ENTITY_UPDATE_CHILD_BOUNDARY;
        s->child_entry=CS_AdvanceEntityCountdown;
        s->child_status=child_result.status;
        return 1;
    }
    actual_return=pop16(s);
#if ENTITY_UPDATE_MUTATION == 7
    actual_return=cached_return;
#endif
    if(actual_return!=CS_EntityUpdateAfterCountdownCall) {
        s->continuation=actual_return;
        s->status=LMN_ENTITY_UPDATE_CHANGED_CALL_RETURN;
        s->child_entry=CS_AdvanceEntityCountdown;
        s->child_status=child_result.status;
        return 1;
    }
    s->continuation=CS_EntityUpdateAfterCountdownCall;
    return 0;
}

static void store_guard_zero(UpdateState *s) {
    write8(s,s->r.data_segment,SEG09A9_EntityWorkGuard,0u);
}

static void scan_exhausted(UpdateState *s) {
    write8(s,s->r.data_segment,SEG09A9_EntityScanRequest,0u);
    store_guard_zero(s);
    s->continuation=CS_EntityUpdateScanExhaustedReturn;
    s->status=LMN_ENTITY_UPDATE_RETURN_PENDING;
    s->child_entry=0u;s->child_status=LMN_ENTITY_UPDATE_NO_CHILD_STATUS;
}

static void scan_candidate_return(UpdateState *s) {
    increment_global(s,SEG09A9_EntityScanCursor);
    s->continuation=CS_EntityUpdateScanCandidateReturn;
    s->status=LMN_ENTITY_UPDATE_RETURN_PENDING;
    s->child_entry=0u;s->child_status=LMN_ENTITY_UPDATE_NO_CHILD_STATUS;
}

static void scan_entities(UpdateState *s) {
    for(;;) {
        uint8_t cursor=read8(s,s->r.data_segment,SEG09A9_EntityScanCursor);
        uint8_t bound=read8(s,s->r.data_segment,SEG09A9_EntitySlotBound);
        uint16_t si;
        uint8_t active,inactive;
        uint16_t state_word;
        s->r.value=(uint16_t)((s->r.value&0xff00u)|cursor);
        s->r.flags=compare8_flags(s->r.flags,cursor,bound);
#if ENTITY_UPDATE_MUTATION == 4
        if(cursor>=bound) {
#else
        if(cursor==bound) {
#endif
            scan_exhausted(s);
            return;
        }
        s->r.count=0x002du;
        /* XOR AH,AH; MUL CX; ADD AX,88. MUL's undefined flags are replaced
           by ADD before any following conditional instruction. */
        s->r.value=(uint16_t)(s->r.value&0x00ffu);
        s->r.flags=logic_flags(s->r.flags,(uint8_t)(s->r.value>>8),8u);
        s->r.auxiliary_value=0u;
        {
            uint32_t product=(uint32_t)(uint8_t)s->r.value*0x2du;
            s->r.value=(uint16_t)product;
            s->r.auxiliary_value=(uint16_t)(product>>16);
        }
        s->r.flags=add16_flags(s->r.flags,s->r.value,0x0088u);
        s->r.value=(uint16_t)(s->r.value+0x0088u);
        s->r.record_cursor=s->r.value;
        si=s->r.record_cursor;
        active=read8(s,s->r.data_segment,(uint16_t)(si+0x20u));
        s->r.flags=compare8_flags(s->r.flags,active,0u);
        if(active!=0u) {
            scan_candidate_return(s);
            return;
        }
        inactive=read8(s,s->r.data_segment,(uint16_t)(si+0x26u));
        s->r.flags=compare8_flags(s->r.flags,inactive,0xffu);
        if(inactive==0xffu) {
            increment_global(s,SEG09A9_EntityScanCursor);
            continue;
        }
        state_word=read16(s,s->r.data_segment,(uint16_t)(si+8u));
        s->r.flags=logic_flags(s->r.flags,(uint16_t)(state_word&0x0003u),16u);
        if((state_word&0x0003u)==0u)
            write8(s,s->r.data_segment,(uint16_t)(si+0x20u),0x4fu);
        scan_candidate_return(s);
        return;
    }
}

LmnEntityUpdateResult lmn_entity_update_core(uint8_t *memory,
    const LmnEntityUpdateCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    UpdateState s;
    uint8_t gate,slots_remaining;
    s.memory=memory;s.pc_binding=pc_binding;s.sound_binding=sound_binding;
    s.bus=bus;COPY_REGISTERS(s.r,*call);
    s.continuation=CS_AdvanceEntityRecords;
    s.status=LMN_ENTITY_UPDATE_RETURN_PENDING;
    s.child_entry=0u;s.child_status=LMN_ENTITY_UPDATE_NO_CHILD_STATUS;

    gate=read8(&s,s.r.data_segment,SEG09A9_EntityUpdateGate);
    s.r.flags=compare8_flags(s.r.flags,gate,0xffu);
    if(gate==0xffu) {
        store_guard_zero(&s);
        s.continuation=CS_EntityUpdateOrdinaryReturn;
        return result_of(&s);
    }

    if(configure_readback(&s))return result_of(&s);
    write8(&s,s.r.data_segment,SEG09A9_EntityWorkGuard,0xffu);
    s.r.record_cursor=SEG09A9_EntityRecordsBase;
    slots_remaining=read8(&s,s.r.data_segment,SEG09A9_EntitySlotBound);
    write8(&s,s.r.data_segment,SEG09A9_EntitySlotsRemaining,slots_remaining);
    s.r.value=(uint16_t)((s.r.value&0xff00u)|slots_remaining);
    s.r.flags=logic_flags(s.r.flags,slots_remaining,8u);
    if(slots_remaining==0u)goto exhausted_without_scan;

    for(;;) {
        uint8_t inactive,remaining;
        uint8_t countdown;
        uint16_t state_word,entry;
        uint8_t record_flag;
        uint16_t saved_es=s.r.extra_segment;
        s.r.stack_offset=(uint16_t)(s.r.stack_offset-2u);
        write16(&s,s.r.stack_segment,s.r.stack_offset,saved_es);

        inactive=read8(&s,s.r.data_segment,(uint16_t)(s.r.record_cursor+0x26u));
        s.r.flags=compare8_flags(s.r.flags,inactive,0xffu);
        if(inactive==0xffu)goto iteration_tail;

        countdown=read8(&s,s.r.data_segment,(uint16_t)(s.r.record_cursor+0x20u));
        s.r.value=(uint16_t)((s.r.value&0xff00u)|countdown);
        s.r.flags=logic_flags(s.r.flags,countdown,8u);
        if(countdown!=0u) {
            if(call_countdown(&s))return result_of(&s);
            if(!(s.r.flags&ZF))goto dispatch_record;
            goto iteration_tail;
        }

dispatch_record:
        record_flag=read8(&s,s.r.data_segment,
            (uint16_t)(s.r.record_cursor+0x24u));
        s.r.value=(uint16_t)((s.r.value&0xff00u)|record_flag);
        s.r.flags=logic_flags(s.r.flags,
#if ENTITY_UPDATE_MUTATION == 2
            0u,
#else
            (uint8_t)(record_flag&0x80u),
#endif
            8u);
#if ENTITY_UPDATE_MUTATION == 2
        (void)record_flag;
#else
        if(record_flag&0x80u) {
            if(dispatch_state(&s,CS_AdvanceEntityFlag80Override))
                return result_of(&s);
            goto iteration_tail;
        }
#endif
        state_word=read16(&s,s.r.data_segment,
            (uint16_t)(s.r.record_cursor+8u));
        s.r.value=state_word;
        s.r.flags=logic_flags(s.r.flags,state_word,16u);
        if(state_word==0u) {
            if(dispatch_state(&s,CS_AdvanceEntityZeroState))
                return result_of(&s);
            goto iteration_tail;
        }
        entry=select_state(&s,state_word);
        if(dispatch_state(&s,entry))return result_of(&s);
        goto iteration_tail;

iteration_tail:
#if ENTITY_UPDATE_MUTATION == 3
        (void)pop16(&s);
        s.r.extra_segment=saved_es;
#else
        s.r.extra_segment=pop16(&s);
#endif
        s.r.flags=add16_flags(s.r.flags,s.r.record_cursor,0x002du);
        s.r.record_cursor=(uint16_t)(s.r.record_cursor+0x002du);
        remaining=read8(&s,s.r.data_segment,SEG09A9_EntitySlotsRemaining);
        {
            uint8_t next=(uint8_t)(remaining-1u);
            uint16_t entry_flags=s.r.flags;
            write_physical(&s,physical(s.r.data_segment,
                SEG09A9_EntitySlotsRemaining),next,entry_flags);
            s.r.flags=dec8_flags(entry_flags,remaining,next);
            if(next!=0u)continue;
        }
        break;
    }

    {
        uint8_t request=read8(&s,s.r.data_segment,
            SEG09A9_EntityScanRequest);
        s.r.flags=compare8_flags(s.r.flags,request,0u);
        if(request!=0u) {
            scan_entities(&s);
            return result_of(&s);
        }
    }
    store_guard_zero(&s);
    s.continuation=CS_EntityUpdateOrdinaryReturn;
    s.status=LMN_ENTITY_UPDATE_RETURN_PENDING;
    s.child_entry=0u;s.child_status=LMN_ENTITY_UPDATE_NO_CHILD_STATUS;
    return result_of(&s);

exhausted_without_scan:
    store_guard_zero(&s);
    s.continuation=CS_EntityUpdateOrdinaryReturn;
    s.status=LMN_ENTITY_UPDATE_RETURN_PENDING;
    s.child_entry=0u;s.child_status=LMN_ENTITY_UPDATE_NO_CHILD_STATUS;
    return result_of(&s);
}

uint16_t lmn_entity_update_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityUpdateCall call;
    LmnEntityUpdateResult out;
    call.value=registers->ax;call.map_cursor=registers->bx;
    call.count=registers->cx;call.auxiliary_value=registers->dx;
    call.record_cursor=registers->si;call.object_cursor=registers->di;
    call.candidate_y=registers->bp;call.code_segment=registers->cs;
    call.data_segment=registers->ds;call.extra_segment=registers->es;
    call.stack_segment=registers->ss;call.stack_offset=registers->sp;
    call.flags=registers->flags;
    out=lmn_entity_update_core(memory,&call,pc_binding,sound_binding,bus);
    registers->ax=out.value;registers->bx=out.map_cursor;
    registers->cx=out.count;registers->dx=out.auxiliary_value;
    registers->si=out.record_cursor;registers->di=out.object_cursor;
    registers->bp=out.candidate_y;registers->cs=out.code_segment;
    registers->ds=out.data_segment;registers->es=out.extra_segment;
    registers->ss=out.stack_segment;registers->sp=out.stack_offset;
    registers->flags=out.flags;registers->ip=out.continuation;
    if(out.status==LMN_ENTITY_UPDATE_RETURN_PENDING) {
        UpdateState s;
        s.memory=memory;s.bus=bus;s.r.flags=registers->flags;
        registers->ip=read16(&s,registers->ss,registers->sp);
        registers->sp=(uint16_t)(registers->sp+2u);
    }
    return out.status;
}

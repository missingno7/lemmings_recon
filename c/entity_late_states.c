#include "entity_late_states.h"
#include "lemmings_sym.h"

#ifndef ENTITY_LATE_STATES_MUTATION
#define ENTITY_LATE_STATES_MUTATION 0
#endif

enum {
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,OF=0x0800u,ARITH=0x08d5u
};

typedef struct LateState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LateState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(LateState *s,uint32_t address,uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,flags);
    return s->memory[address];
}

static void write_physical(LateState *s,uint32_t address,uint8_t value,
                           uint16_t flags) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(LateState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset),s->flags);
}

static void write8(LateState *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

static uint16_t read16(LateState *s,uint16_t segment,uint16_t offset,
                       uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address,flags);
    uint8_t high=read_physical(s,address+1u,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(LateState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
}

static uint16_t szp(uint16_t value,unsigned bits) {
    uint16_t out=0;
    unsigned parity=0,bit;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(!(value&((1u<<bits)-1u)))out|=ZF;
    if(value&(1u<<(bits-1u)))out|=SF;
    return out;
}

static uint16_t add_flags(uint16_t flags,uint16_t left,uint16_t right,
                          unsigned bits) {
    uint32_t mask=bits==8u?0xffu:0xffffu;
    uint32_t l=left&mask,r=right&mask,sum=l+r;
    uint16_t value=(uint16_t)(sum&mask),out=szp(value,bits);
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
    uint16_t value=(uint16_t)((l-r)&mask),out=szp(value,bits);
    uint32_t sign=1u<<(bits-1u);
    if(l<r)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if(((left^right)&(left^value)&sign)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return (uint16_t)((add_flags(flags,value,1u,bits)&~CF)|(flags&CF));
}

/* AND/OR define CF, OF, SF, ZF and PF. AF is undefined; use zero. */
static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return (uint16_t)((flags&~ARITH)|szp(value,bits));
}

static uint16_t test_flags(uint16_t flags,uint16_t value,unsigned bits) {
    return logic_flags(flags,value,bits);
}

static LmnEntityLateStatesResult result_of(const LateState *s) {
    LmnEntityLateStatesResult out;
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

static uint16_t record_byte_offset(const LateState *s,uint16_t displacement) {
    return (uint16_t)(s->record_cursor+displacement);
}

static uint16_t record_word(LateState *s,uint16_t displacement) {
    return read16(s,s->data_segment,
                  record_byte_offset(s,displacement),s->flags);
}

static uint8_t read_record_byte(LateState *s,uint16_t displacement) {
    return read8(s,s->data_segment,record_byte_offset(s,displacement));
}

static void set_record_byte(LateState *s,uint16_t displacement,
                            uint8_t value) {
    write8(s,s->data_segment,record_byte_offset(s,displacement),value,
           s->flags);
}

static void set_record_word(LateState *s,uint16_t displacement,
                            uint16_t value) {
    write16(s,s->data_segment,record_byte_offset(s,displacement),value,
            s->flags);
}

static uint8_t and_record_byte(LateState *s,uint16_t displacement,
                               uint8_t mask) {
    uint16_t entry_flags=s->flags;
    uint8_t old_value=read_record_byte(s,displacement);
    uint8_t new_value=(uint8_t)(old_value&mask);
    write8(s,s->data_segment,record_byte_offset(s,displacement),new_value,
           entry_flags);
    s->flags=logic_flags(entry_flags,new_value,8u);
    return new_value;
}

static uint16_t or_record_word(LateState *s,uint16_t displacement,
                               uint16_t operand) {
    uint16_t entry_flags=s->flags;
    uint16_t old_value=record_word(s,displacement);
    uint16_t new_value=(uint16_t)(old_value|operand);
    write16(s,s->data_segment,record_byte_offset(s,displacement),new_value,
            entry_flags);
    s->flags=logic_flags(entry_flags,new_value,16u);
    return new_value;
}

static uint16_t map_finish_status(uint16_t status) {
    switch(status) {
    case LMN_ENTITY_FINISH_RETURNED:return LMN_ENTITY_LATE_READY;
    case LMN_ENTITY_FINISH_UNBOUND_VECTOR:return LMN_ENTITY_LATE_UNBOUND_VECTOR;
    case LMN_ENTITY_FINISH_UNTRANSLATED_SOUND:
        return LMN_ENTITY_LATE_UNTRANSLATED_SOUND;
    case LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN:
        return LMN_ENTITY_LATE_CHANGED_CHILD_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN:
        return LMN_ENTITY_LATE_CHANGED_INTERRUPT_RETURN;
    case LMN_ENTITY_FINISH_CHANGED_CALL_RETURN:
        return LMN_ENTITY_LATE_CHANGED_FINISH_CALL_RETURN;
    case LMN_ENTITY_FINISH_INVALID_ENTRY:return LMN_ENTITY_LATE_INVALID_CHILD;
    default:return LMN_ENTITY_LATE_INVALID_CHILD;
    }
}

static LmnEntityLateStatesResult finish(LateState *s,uint16_t entry,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    LmnEntityFinishCall call;
    LmnEntityFinishResult out;
    call.entry=entry;call.value=s->value;call.map_cursor=s->map_cursor;
    call.count=s->count;call.auxiliary_value=s->auxiliary_value;
    call.record_cursor=s->record_cursor;call.object_cursor=s->object_cursor;
    call.candidate_y=s->candidate_y;call.code_segment=s->code_segment;
    call.data_segment=s->data_segment;call.extra_segment=s->extra_segment;
    call.stack_segment=s->stack_segment;call.stack_offset=s->stack_offset;
    call.flags=s->flags;
    out=lmn_entity_finish_core(s->memory,&call,pc_binding,sound_binding,s->bus);
    s->value=out.value;s->map_cursor=out.map_cursor;s->count=out.count;
    s->auxiliary_value=out.auxiliary_value;
    s->record_cursor=out.record_cursor;s->object_cursor=out.object_cursor;
    s->candidate_y=out.candidate_y;s->code_segment=out.code_segment;
    s->data_segment=out.data_segment;s->extra_segment=out.extra_segment;
    s->stack_segment=out.stack_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=map_finish_status(out.status);
    return result_of(s);
}

static uint16_t map_sound_status(uint16_t status) {
    switch(status) {
    case LMN_SOUND_INTERRUPT_RETURNED:return LMN_ENTITY_LATE_READY;
    case LMN_SOUND_INTERRUPT_UNBOUND_VECTOR:return LMN_ENTITY_LATE_UNBOUND_VECTOR;
    case LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE:
        return LMN_ENTITY_LATE_UNTRANSLATED_SOUND;
    case LMN_SOUND_INTERRUPT_CHANGED_RETURN:
        return LMN_ENTITY_LATE_CHANGED_INTERRUPT_RETURN;
    default:return LMN_ENTITY_LATE_INVALID_CHILD;
    }
}

static uint16_t call_sound(LateState *s,
    const LmnSoundDriverBinding *sound_binding) {
    LmnSoundInterruptCall call;
    LmnSoundInterruptResult out;
    call.value=s->value;call.data_segment=s->data_segment;
    call.code_segment=s->code_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.flags=s->flags;
    call.return_offset=CS_EntityState8000AfterSound;
    out=lmn_sound_interrupt61_core(s->memory,&call,sound_binding,s->bus);
    s->value=out.value;s->data_segment=out.data_segment;
    s->code_segment=out.code_segment;s->stack_offset=out.stack_offset;
    s->flags=out.flags;s->continuation=out.continuation;
    s->status=map_sound_status(out.status);
    if(out.status==LMN_SOUND_INTERRUPT_RETURNED)
        s->continuation=CS_EntityState8000AfterSound;
    return s->status;
}

static LmnEntityLateStatesResult call_pixel(LateState *s) {
    LmnEntityPixelCall call;
    LmnEntityPixelResult out;
    uint16_t actual_return;
    uint16_t return_offset=CS_EntityState8000AfterPixelCall;
    s->stack_offset=(uint16_t)(s->stack_offset-2u);
    write16(s,s->stack_segment,s->stack_offset,return_offset,s->flags);
    call.data_segment=s->data_segment;call.stack_segment=s->stack_segment;
    call.stack_offset=s->stack_offset;call.record_cursor=s->record_cursor;
    call.saved_value=s->auxiliary_value;call.flags=s->flags;
    out=lmn_prepare_entity_pixel_bus_core(s->memory,&call,s->bus);
    s->value=out.value;s->map_cursor=out.table_cursor;
    s->count=out.column_byte;s->auxiliary_value=out.restored_value;
    s->object_cursor=out.destination_offset;s->extra_segment=0xa000u;
    s->stack_offset=out.stack_offset;s->flags=out.flags;
    actual_return=read16(s,s->stack_segment,s->stack_offset,s->flags);
    s->stack_offset=(uint16_t)(s->stack_offset+2u);
    s->continuation=actual_return;
    if(actual_return!=return_offset) {
        s->status=LMN_ENTITY_LATE_CHANGED_PIXEL_RETURN;
        return result_of(s);
    }
    s->continuation=CS_EntityState8000AfterPixelCall;
    s->status=LMN_ENTITY_LATE_READY;
    return result_of(s);
}

static uint8_t probe_pixel_and_mask(LateState *s) {
    uint16_t segment=s->extra_segment;
    uint8_t pixel,mask=(uint8_t)(s->value>>8),result;
#if ENTITY_LATE_STATES_MUTATION == 3
    segment=s->data_segment;
#endif
    pixel=read8(s,segment,s->object_cursor);
    result=(uint8_t)(pixel&mask);
    s->value=(uint16_t)((s->value&0xff00u)|result);
    s->flags=logic_flags(s->flags,result,8u);
    return result;
}

static void inc_candidate_y(LateState *s) {
    uint16_t old=s->candidate_y;
    s->candidate_y=(uint16_t)(old+1u);
    s->flags=inc_flags(s->flags,old,16u);
}

static LmnEntityLateStatesResult store_probe_height(LateState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    return finish(s,LMN_ENTITY_FINISH_STORE_HEIGHT_20D6,
                  pc_binding,sound_binding);
}

static LmnEntityLateStatesResult state8000(LateState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t al,scan_request,driver_enabled,sound_options;
    uint16_t pitch;
    unsigned probe;

    /* 2D0F..2D19: full four-bit cadence. */
    al=read_record_byte(s,0x28u);
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=inc_flags(s->flags,al,8u);
    al=(uint8_t)(al+1u);
#if ENTITY_LATE_STATES_MUTATION == 1
    s->flags=logic_flags(s->flags,(uint16_t)(al&0x07u),8u);
    al=(uint8_t)(al&0x07u);
#else
    s->flags=logic_flags(s->flags,(uint16_t)(al&0x0fu),8u);
    al=(uint8_t)(al&0x0fu);
#endif
    s->value=(uint16_t)((s->value&0xff00u)|al);
    set_record_byte(s,0x28u,al);
    if(al==0u) {
        /* 2D1B..2D75: ordered reset, late callback, optional INT61. */
        or_record_word(s,8u,0x0002u);
        set_record_word(s,0x0au,0x0008u);
        set_record_word(s,0x0cu,0x180bu);
        set_record_word(s,0x10u,0x0280u);
        set_record_word(s,0x12u,0x01e0u);
        set_record_byte(s,0x28u,0u);
        set_record_word(s,6u,0xffe7u);
        set_record_word(s,4u,0xfff0u);
        set_record_byte(s,0x29u,0u);
#if ENTITY_LATE_STATES_MUTATION == 4
        s->value=read16(s,s->data_segment,SEG09A9_DrawingCallbackSlots,
                        s->flags);
#else
        s->value=read16(s,s->data_segment,
            (uint16_t)(SEG09A9_DrawingCallbackSlots+0x0eu),s->flags);
#endif
        set_record_word(s,0x14u,s->value);
        set_record_byte(s,0x2au,0u);
        set_record_byte(s,0x22u,0x0fu);
        and_record_byte(s,0x24u,0x01u);

        driver_enabled=read8(s,s->data_segment,
                             SEG09A9_ExternalSoundDriverEnabled);
        s->flags=sub_flags(s->flags,driver_enabled,0xffu,8u);
        if(driver_enabled==0xffu) {
            sound_options=read8(s,s->data_segment,SEG09A9_SoundOptionBits);
            s->flags=test_flags(s->flags,
                                (uint16_t)(sound_options&0x03u),8u);
            if(sound_options&0x03u) {
                s->value=0x040cu;
                if(call_sound(s,sound_binding)!=LMN_ENTITY_LATE_READY)
                    return result_of(s);
            }
        }

        /* 2D6A..2D75 follows a returning INT with live DS and record memory. */
        {
            uint16_t word=record_word(s,8u);
            s->flags=test_flags(s->flags,(uint16_t)(word&0x0004u),16u);
            if(word&0x0004u)set_record_byte(s,0x22u,0u);
        }
        s->continuation=CS_EntityIterationTail;
        s->status=LMN_ENTITY_LATE_READY;
        return result_of(s);
    }

    /* Both JNZ edges meet at 2D83. CMPs still define the flags passed to CALL. */
    s->flags=sub_flags(s->flags,al,0x05u,8u);
    if(al==0x05u) {
        scan_request=read8(s,s->data_segment,SEG09A9_EntityScanRequest);
#if ENTITY_LATE_STATES_MUTATION == 2
        s->flags=sub_flags(s->flags,scan_request,0xfeu,8u);
#else
        s->flags=sub_flags(s->flags,scan_request,0xffu,8u);
#endif
        /* The original JNZ target and fallthrough are both exactly 2D83. */
    }
    if(call_pixel(s).status!=LMN_ENTITY_LATE_READY)return result_of(s);
    s->candidate_y=record_word(s,2u); /* MOV BP,[SI+2], after child return. */

    for(probe=0;probe<3u;++probe) {
        if(probe_pixel_and_mask(s)!=0u)
            return store_probe_height(s,pc_binding,sound_binding);
        inc_candidate_y(s);
        if(probe!=2u) {
            pitch=read16(s,s->data_segment,SEG09A9_EntityPixelRowPitchBytes,
                         s->flags);
            s->flags=add_flags(s->flags,s->object_cursor,pitch,16u);
            s->object_cursor=(uint16_t)(s->object_cursor+pitch);
        }
    }
    return store_probe_height(s,pc_binding,sound_binding);
}

static LmnEntityLateStatesResult flag80_override(LateState *s,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding) {
    uint8_t al;
    uint16_t callback_offset;
    /* 2DB5..2E03: modulo-eight cadence and bit-80 reset entry. */
    al=read_record_byte(s,0x28u);
    s->value=(uint16_t)((s->value&0xff00u)|al);
    s->flags=inc_flags(s->flags,al,8u);
    al=(uint8_t)(al+1u);
#if ENTITY_LATE_STATES_MUTATION == 5
    s->flags=logic_flags(s->flags,(uint16_t)(al&0x0fu),8u);
    al=(uint8_t)(al&0x0fu);
#else
    s->flags=logic_flags(s->flags,(uint16_t)(al&0x07u),8u);
    al=(uint8_t)(al&0x07u);
#endif
    s->value=(uint16_t)((s->value&0xff00u)|al);
    set_record_byte(s,0x28u,al);
    if(al!=0u) {
        s->continuation=CS_EntityIterationTail;
        s->status=LMN_ENTITY_LATE_READY;
        return result_of(s);
    }

    set_record_word(s,8u,0u);
    set_record_word(s,0x0au,0u);
    set_record_word(s,0x0cu,0u);
    set_record_word(s,0x10u,0x005au);
    set_record_word(s,0x12u,0x003cu);
    set_record_byte(s,0x28u,0u);
    set_record_word(s,4u,0xfff8u);
    set_record_word(s,6u,0xfff6u);
    set_record_byte(s,0x29u,0x09u);
#if ENTITY_LATE_STATES_MUTATION == 6
    callback_offset=(uint16_t)(SEG09A9_DrawingCallbackSlots+0x0eu);
#else
    callback_offset=SEG09A9_DrawingCallbackSlots;
#endif
    s->value=read16(s,s->data_segment,callback_offset,s->flags);
    set_record_word(s,0x14u,s->value);
    set_record_byte(s,0x2au,0u);
    and_record_byte(s,0x24u,0x01u);
    and_record_byte(s,0x24u,0x7fu);
    return finish(s,LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8,
                  pc_binding,sound_binding);
}

LmnEntityLateStatesResult lmn_entity_late_states_core(uint8_t *memory,
    const LmnEntityLateStatesCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LateState s;
    s.memory=memory;s.bus=bus;s.entry=call->entry;
    s.value=call->value;s.map_cursor=call->map_cursor;
    s.count=call->count;s.auxiliary_value=call->auxiliary_value;
    s.record_cursor=call->record_cursor;s.object_cursor=call->object_cursor;
    s.candidate_y=call->candidate_y;s.code_segment=call->code_segment;
    s.data_segment=call->data_segment;s.extra_segment=call->extra_segment;
    s.stack_segment=call->stack_segment;s.stack_offset=call->stack_offset;
    s.flags=call->flags;s.continuation=0;
    s.status=LMN_ENTITY_LATE_INVALID_ENTRY;
    switch(call->entry) {
    case LMN_ENTITY_LATE_STATE_8000:
        return state8000(&s,pc_binding,sound_binding);
    case LMN_ENTITY_LATE_FLAG80_OVERRIDE:
        return flag80_override(&s,pc_binding,sound_binding);
    default:return result_of(&s);
    }
}

uint16_t lmn_entity_late_states_adapter(uint8_t *memory,LmnRegs *registers,
    enum LmnEntityLateStatesEntry entry,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus) {
    LmnEntityLateStatesCall call;
    LmnEntityLateStatesResult out;
    call.entry=(uint16_t)entry;
    call.value=registers->ax;call.map_cursor=registers->bx;
    call.count=registers->cx;call.auxiliary_value=registers->dx;
    call.record_cursor=registers->si;call.object_cursor=registers->di;
    call.candidate_y=registers->bp;call.code_segment=registers->cs;
    call.data_segment=registers->ds;call.extra_segment=registers->es;
    call.stack_segment=registers->ss;call.stack_offset=registers->sp;
    call.flags=registers->flags;
    out=lmn_entity_late_states_core(memory,&call,pc_binding,sound_binding,bus);
    registers->ax=out.value;registers->bx=out.map_cursor;
    registers->cx=out.count;registers->dx=out.auxiliary_value;
    registers->si=out.record_cursor;registers->di=out.object_cursor;
    registers->bp=out.candidate_y;registers->cs=out.code_segment;
    registers->ds=out.data_segment;registers->es=out.extra_segment;
    registers->ss=out.stack_segment;registers->sp=out.stack_offset;
    registers->flags=out.flags;registers->ip=out.continuation;
    return out.status;
}

#include "sound_interrupt.h"
#include "sound_latches.h"

#ifndef SOUND_INTERRUPT_MUTATION
#define SOUND_INTERRUPT_MUTATION 0
#endif

enum { INT_IF=0x0200u, INT_TF=0x0100u, INT_CLEAR_IF_TF=INT_IF|INT_TF };

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(uint8_t *memory,uint32_t address,uint16_t flags,
                             const LmnRasterBus *bus) {
    address&=0xfffffu;
    if(bus&&bus->read_byte)
        return bus->read_byte(bus->context,memory,address,flags);
    return memory[address];
}

static void write_physical(uint8_t *memory,uint32_t address,uint8_t value,
                           uint16_t flags,const LmnRasterBus *bus) {
    address&=0xfffffu;
    if(bus&&bus->write_byte)
        bus->write_byte(bus->context,memory,address,value,flags);
    else
        memory[address]=value;
}

/* A real-mode word starts at the segment:offset physical byte; its second
   byte is the following physical address, not a wrapped segment offset. */
static uint16_t read_word(uint8_t *memory,uint16_t segment,uint16_t offset,
                          uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(memory,address,flags,bus);
    uint8_t high=read_physical(memory,address+1u,flags,bus);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_word(uint8_t *memory,uint16_t segment,uint16_t offset,
                       uint16_t value,uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    write_physical(memory,address,(uint8_t)value,flags,bus);
    write_physical(memory,address+1u,(uint8_t)(value>>8),flags,bus);
}

static void push_word(uint8_t *memory,uint16_t segment,uint16_t *sp,
                      uint16_t value,uint16_t flags,const LmnRasterBus *bus) {
    *sp=(uint16_t)(*sp-2u);
    write_word(memory,segment,*sp,value,flags,bus);
}

static uint16_t pop_word(uint8_t *memory,uint16_t segment,uint16_t *sp,
                         uint16_t flags,const LmnRasterBus *bus) {
    uint16_t value=read_word(memory,segment,*sp,flags,bus);
    *sp=(uint16_t)(*sp+2u);
    return value;
}

typedef struct LmnSoundVector {
    uint16_t code_segment,instruction_pointer;
} LmnSoundVector;

/* The platform model follows Intel's INT real-address pseudocode: CS first,
   then IP. This describes the declared boundary, not hardware bus timing. */
static LmnSoundVector read_vector61(uint8_t *memory,uint16_t flags,
                                    const LmnRasterBus *bus) {
    LmnSoundVector vector;
    uint16_t vector_ip_offset=(uint16_t)(0x61u*4u);
    vector.code_segment=read_word(memory,0,
        (uint16_t)(vector_ip_offset+2u),flags,bus);
    vector.instruction_pointer=read_word(memory,0,vector_ip_offset,flags,bus);
    return vector;
}

static LmnSoundInterruptResult result(uint16_t value,uint16_t ds,uint16_t cs,
    uint16_t sp,uint16_t flags,uint16_t continuation,uint16_t status) {
    LmnSoundInterruptResult out;
    out.value=value;
    out.data_segment=ds;
    out.code_segment=cs;
    out.stack_offset=sp;
    out.flags=flags;
    out.continuation=continuation;
    out.status=status;
    return out;
}

static LmnSoundControlResult invoke_driver(uint8_t *memory,
    const LmnSoundLatchCall *call,uint16_t kind,const LmnRasterBus *bus) {
    if(kind==LMN_SOUND_DRIVER_ADLIB)
        return lmn_adlib_control_core(memory,call,bus);
    return lmn_tandy_control_core(memory,call,bus);
}

LmnSoundInterruptResult lmn_sound_interrupt61_core(uint8_t *memory,
    const LmnSoundInterruptCall *call,const LmnSoundDriverBinding *binding,
    const LmnRasterBus *bus) {
    uint16_t sp=call->stack_offset;
    uint16_t live_flags=(uint16_t)(call->flags&~INT_CLEAR_IF_TF);
    LmnSoundVector vector;
#if SOUND_INTERRUPT_MUTATION == 1
    /* Mutation: read both IVT words before INT's frame stores can alias them. */
    vector=read_vector61(memory,live_flags,bus);
#endif
    push_word(memory,call->stack_segment,&sp,call->flags,call->flags,bus);
#if SOUND_INTERRUPT_MUTATION != 2
    live_flags=(uint16_t)(call->flags&~INT_CLEAR_IF_TF);
#else
    live_flags=call->flags;
#endif
#if SOUND_INTERRUPT_MUTATION == 5
    push_word(memory,call->stack_segment,&sp,call->return_offset,live_flags,bus);
    push_word(memory,call->stack_segment,&sp,call->code_segment,live_flags,bus);
#else
    push_word(memory,call->stack_segment,&sp,call->code_segment,live_flags,bus);
    push_word(memory,call->stack_segment,&sp,call->return_offset,live_flags,bus);
#endif
#if SOUND_INTERRUPT_MUTATION != 1
    vector=read_vector61(memory,live_flags,bus);
#endif

    if(!binding || (binding->driver_kind!=LMN_SOUND_DRIVER_ADLIB &&
                    binding->driver_kind!=LMN_SOUND_DRIVER_TANDY) ||
       vector.instruction_pointer!=0 ||
       vector.code_segment!=binding->driver_segment) {
        return result(call->value,call->data_segment,vector.code_segment,sp,
            live_flags,vector.instruction_pointer,
            LMN_SOUND_INTERRUPT_UNBOUND_VECTOR);
    }

    {
        LmnSoundLatchCall child_call;
        LmnSoundControlResult child;
        uint16_t child_sp;
        child_call.driver_segment=vector.code_segment;
        child_call.data_segment=call->data_segment;
        child_call.stack_segment=call->stack_segment;
        child_call.stack_offset=sp;
        child_call.value=call->value;
        child_call.flags=live_flags;
#if SOUND_INTERRUPT_MUTATION == 3
        /* AH=0..2 exits without IRET; otherwise cache the live frame early. */
        uint8_t command=(uint8_t)(call->value>>8);
        uint16_t cached_ip=0,cached_cs=0,cached_flags=0;
        uint16_t cached_sp=sp;
        int cache_iret=command>=3;
        if(cache_iret) {
            cached_ip=pop_word(memory,call->stack_segment,&cached_sp,
                               live_flags,bus);
            cached_cs=pop_word(memory,call->stack_segment,&cached_sp,
                               live_flags,bus);
            cached_flags=pop_word(memory,call->stack_segment,&cached_sp,
                                  live_flags,bus);
        }
#endif
        child=invoke_driver(memory,&child_call,binding->driver_kind,bus);
        if(child.exit_kind==LMN_SOUND_CONTROL_UNTRANSLATED) {
            uint16_t ds=child.data_segment;
#if SOUND_INTERRUPT_MUTATION == 6
            ds=call->data_segment;
#endif
            return result(child.value,ds,vector.code_segment,
                child.stack_offset,child.flags,child.continuation,
                LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE);
        }

        child_sp=child.stack_offset;
#if SOUND_INTERRUPT_MUTATION == 3
        if(cache_iret) {
            uint16_t restored_flags=(uint16_t)((cached_flags&0x7fd5u)|2u);
            child_sp=(uint16_t)(child_sp+6u);
            {
                uint16_t ds=child.data_segment;
#if SOUND_INTERRUPT_MUTATION == 6
                ds=call->data_segment;
#endif
                {
                    uint16_t status=(cached_cs==call->code_segment &&
                                    cached_ip==call->return_offset) ?
                        LMN_SOUND_INTERRUPT_RETURNED :
                        LMN_SOUND_INTERRUPT_CHANGED_RETURN;
#if SOUND_INTERRUPT_MUTATION == 4
                    status=LMN_SOUND_INTERRUPT_RETURNED;
#endif
                    return result(child.value,ds,cached_cs,child_sp,
                                  restored_flags,cached_ip,status);
                }
            }
        }
#endif
        {
            uint16_t ip=pop_word(memory,call->stack_segment,&child_sp,
                                 child.flags,bus);
            uint16_t cs=pop_word(memory,call->stack_segment,&child_sp,
                                 child.flags,bus);
            uint16_t popped_flags=pop_word(memory,call->stack_segment,&child_sp,
                                           child.flags,bus);
            uint16_t restored_flags=(uint16_t)((popped_flags&0x7fd5u)|2u);
            uint16_t ds=child.data_segment;
            uint16_t status;
#if SOUND_INTERRUPT_MUTATION == 6
            ds=call->data_segment;
#endif
            status=(cs==call->code_segment && ip==call->return_offset) ?
                LMN_SOUND_INTERRUPT_RETURNED :
                LMN_SOUND_INTERRUPT_CHANGED_RETURN;
#if SOUND_INTERRUPT_MUTATION == 4
            status=LMN_SOUND_INTERRUPT_RETURNED;
#endif
            return result(child.value,ds,cs,child_sp,restored_flags,ip,status);
        }
    }
}

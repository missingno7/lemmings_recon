#include "pcspeaker_interrupt.h"
#include "pcspeaker_dispatch.h"
#include "pcspeaker_sym.h"

#ifndef PC_INTERRUPT_MUTATION
#define PC_INTERRUPT_MUTATION 0
#endif

enum {
    PC_INTERRUPT_IF=0x0200u,
    PC_INTERRUPT_TF=0x0100u,
    PC_INTERRUPT_CLEAR_IF_TF=PC_INTERRUPT_IF|PC_INTERRUPT_TF
};

typedef struct PcSpeakerVector {
    uint16_t code_segment,instruction_pointer;
} PcSpeakerVector;

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

/* The second byte of a real-mode word is the next physical byte. */
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

static void push_word(uint8_t *memory,uint16_t ss,uint16_t *sp,uint16_t value,
                      uint16_t flags,const LmnRasterBus *bus) {
    *sp=(uint16_t)(*sp-2u);
    write_word(memory,ss,*sp,value,flags,bus);
}

/* INT 60 uses the same declared real-mode vector order as the INT 61 model:
   target CS at IVT+182h, then target IP at IVT+180h. */
static PcSpeakerVector read_vector60(uint8_t *memory,uint16_t flags,
                                     const LmnRasterBus *bus) {
    PcSpeakerVector vector;
    const uint16_t vector_ip_offset=(uint16_t)(0x60u*4u);
    vector.code_segment=read_word(memory,0,
        (uint16_t)(vector_ip_offset+2u),flags,bus);
    vector.instruction_pointer=read_word(memory,0,vector_ip_offset,flags,bus);
    return vector;
}

static LmnPcSpeakerInterruptResult make_result(const LmnRegs *registers,
                                               uint16_t status) {
    LmnPcSpeakerInterruptResult result;
    result.registers=*registers;
    result.status=status;
    return result;
}

LmnPcSpeakerInterruptResult lmn_pc_speaker_interrupt60_core(uint8_t *memory,
    const LmnPcSpeakerInterruptCall *call,const LmnPcSpeakerBinding *binding,
    const LmnRasterBus *bus) {
    uint16_t sp=call->registers.sp;
    uint16_t live_flags=(uint16_t)(call->registers.flags&
                                   (uint16_t)~PC_INTERRUPT_CLEAR_IF_TF);
    PcSpeakerVector vector;
#if PC_INTERRUPT_MUTATION == 1
    /* Read the vector before the INT frame can alias and alter the IVT. */
    vector=read_vector60(memory,live_flags,bus);
#endif

    /* The declared INT frame stores entry FLAGS first, then post-INT CS:IP. */
    push_word(memory,call->registers.ss,&sp,call->registers.flags,
              call->registers.flags,bus);
#if PC_INTERRUPT_MUTATION == 2
    live_flags=call->registers.flags;
#endif
#if PC_INTERRUPT_MUTATION == 5
    push_word(memory,call->registers.ss,&sp,call->return_offset,
              live_flags,bus);
    push_word(memory,call->registers.ss,&sp,call->registers.cs,
              live_flags,bus);
#else
    push_word(memory,call->registers.ss,&sp,call->registers.cs,
              live_flags,bus);
    push_word(memory,call->registers.ss,&sp,call->return_offset,
              live_flags,bus);
#endif
#if PC_INTERRUPT_MUTATION != 1
    vector=read_vector60(memory,live_flags,bus);
#endif

    {
        LmnRegs interrupted=call->registers;
        interrupted.sp=sp;
        interrupted.flags=live_flags;
        interrupted.cs=vector.code_segment;
        interrupted.ip=vector.instruction_pointer;

        if(!binding || vector.code_segment!=binding->driver_segment ||
#if PC_INTERRUPT_MUTATION != 6
           vector.instruction_pointer!=PC_InterruptEntry
#else
           0
#endif
          )
            return make_result(&interrupted,LMN_PC_INTERRUPT_UNBOUND_VECTOR);

        {
            uint16_t child_status=lmn_pc_speaker_dispatch_adapter(
                memory,&interrupted,bus);
#if PC_INTERRUPT_MUTATION == 3
            interrupted.ds=call->registers.ds;
#endif
            if(child_status==LMN_PC_SPEAKER_UNTRANSLATED_CHILD)
                return make_result(&interrupted,
                    LMN_PC_INTERRUPT_UNTRANSLATED_CHILD);
            if(child_status==LMN_PC_SPEAKER_CHANGED_CHILD_RETURN)
                return make_result(&interrupted,
                    LMN_PC_INTERRUPT_CHANGED_CHILD_RETURN);

            if(interrupted.cs!=call->registers.cs ||
               interrupted.ip!=call->return_offset) {
#if PC_INTERRUPT_MUTATION == 4
                return make_result(&interrupted,LMN_PC_INTERRUPT_RETURNED);
#else
                return make_result(&interrupted,
                    LMN_PC_INTERRUPT_CHANGED_INTERRUPT_RETURN);
#endif
            }
            return make_result(&interrupted,LMN_PC_INTERRUPT_RETURNED);
        }
    }
}

#ifndef LEMMINGS_PCSPEAKER_INTERRUPT_H
#define LEMMINGS_PCSPEAKER_INTERRUPT_H

#include <stdint.h>
#include "regs.h"
#include "special_blit.h"

typedef struct LmnPcSpeakerBinding {
    uint16_t driver_segment;
} LmnPcSpeakerBinding;

typedef struct LmnPcSpeakerInterruptCall {
    LmnRegs registers;
    uint16_t return_offset;
} LmnPcSpeakerInterruptCall;

typedef struct LmnPcSpeakerInterruptResult {
    LmnRegs registers;
    uint16_t status;
} LmnPcSpeakerInterruptResult;

enum LmnPcSpeakerInterruptStatus {
    LMN_PC_INTERRUPT_RETURNED=0,
    LMN_PC_INTERRUPT_UNBOUND_VECTOR=1,
    LMN_PC_INTERRUPT_UNTRANSLATED_CHILD=2,
    LMN_PC_INTERRUPT_CHANGED_CHILD_RETURN=3,
    LMN_PC_INTERRUPT_CHANGED_INTERRUPT_RETURN=4
};

LmnPcSpeakerInterruptResult lmn_pc_speaker_interrupt60_core(
    uint8_t *memory,const LmnPcSpeakerInterruptCall *call,
    const LmnPcSpeakerBinding *binding,const LmnRasterBus *bus);

#endif

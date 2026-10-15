#ifndef LEMMINGS_ENTITY_INTERACTIONS_H
#define LEMMINGS_ENTITY_INTERACTIONS_H

#include "pcspeaker_interrupt.h"
#include "sound_interrupt.h"
#include "regs.h"

enum {
    LMN_ENTITY_INTERACTION_RET_READY=0,
    LMN_ENTITY_INTERACTION_UNBOUND_VECTOR=1,
    LMN_ENTITY_INTERACTION_UNTRANSLATED_SOUND=2,
    LMN_ENTITY_INTERACTION_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_INTERACTION_CHANGED_INTERRUPT_RETURN=4
};

typedef struct LmnEntityInteractionsCall {
    uint16_t count,auxiliary_value,record_cursor,object_cursor;
    uint16_t data_segment,code_segment,stack_segment,stack_offset,flags;
} LmnEntityInteractionsCall;

typedef struct LmnEntityInteractionsResult {
    uint16_t value,map_cursor,count,auxiliary_value,record_cursor,object_cursor;
    uint16_t data_segment,code_segment,stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityInteractionsResult;

LmnEntityInteractionsResult lmn_entity_interactions_core(uint8_t *memory,
    const LmnEntityInteractionsCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

uint16_t lmn_entity_interactions_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

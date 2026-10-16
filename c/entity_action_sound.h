#ifndef LEMMINGS_ENTITY_ACTION_SOUND_H
#define LEMMINGS_ENTITY_ACTION_SOUND_H

#include "pcspeaker_interrupt.h"
#include "sound_interrupt.h"

enum LmnEntityActionSoundEntry {
    LMN_ENTITY_ACTION_SOUND_DUAL_FEEDBACK_31E5=0,
    LMN_ENTITY_ACTION_SOUND_SERVICE_0412_3287=1
};

enum LmnEntityActionSoundStatus {
    LMN_ENTITY_ACTION_SOUND_READY=0,
    LMN_ENTITY_ACTION_SOUND_UNBOUND_VECTOR=1,
    LMN_ENTITY_ACTION_SOUND_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_ACTION_SOUND_CHANGED_DRIVER_CHILD=3,
    LMN_ENTITY_ACTION_SOUND_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_ACTION_SOUND_INVALID_ENTRY=5,
    LMN_ENTITY_ACTION_SOUND_INVALID_CHILD=6
};

/* Logical live registers at either sound-tail entry. INT frames and the
   surrounding near-RET word remain in the canonical memory image. */
typedef struct LmnEntityActionSoundCall {
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityActionSoundCall;

typedef struct LmnEntityActionSoundResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityActionSoundResult;

/* Executes the known 31E5..320B dual gate or 3287..329A external-only gate,
   stopping immediately before its outer RET. */
LmnEntityActionSoundResult lmn_entity_action_sound_core(uint8_t *memory,
    const LmnEntityActionSoundCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* The oracle adapter executes the outer near RET using the live SS:SP word. */
uint16_t lmn_entity_action_sound_adapter(uint8_t *memory,LmnRegs *registers,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

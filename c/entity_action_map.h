#ifndef LEMMINGS_ENTITY_ACTION_MAP_H
#define LEMMINGS_ENTITY_ACTION_MAP_H

#include "entity_actions_basic.h"

enum LmnEntityActionMapEntry {
    LMN_ENTITY_ACTION_MAP_SELECTOR_5=5
};

enum LmnEntityActionMapStatus {
    LMN_ENTITY_ACTION_MAP_READY=0,
    LMN_ENTITY_ACTION_MAP_UNBOUND_VECTOR=1,
    LMN_ENTITY_ACTION_MAP_UNTRANSLATED_SOUND=2,
    LMN_ENTITY_ACTION_MAP_CHANGED_DRIVER_CHILD=3,
    LMN_ENTITY_ACTION_MAP_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_ACTION_MAP_INVALID_SOUND_ENTRY=5,
    LMN_ENTITY_ACTION_MAP_INVALID_CHILD=6,
    LMN_ENTITY_ACTION_MAP_INVALID_ENTRY=7
};

/* The selector-5 entry uses the exact same live register layout as the other
   three basic actions so dispatch can select it without shadow-state copies. */
typedef LmnEntityActionsBasicCall LmnEntityActionMapCall;
typedef LmnEntityActionsBasicResult LmnEntityActionMapResult;

/* Executes 3336h..34CDh, composing the direct feedback JMP and stopping before
   the actual outer near RET. Failure branches stop at shared RET 320Ch. */
LmnEntityActionMapResult lmn_entity_action_map_core(uint8_t *memory,
    const LmnEntityActionMapCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Executes the live outer RET only when the core returns READY. */
uint16_t lmn_entity_action_map_adapter(uint8_t *memory,LmnRegs *registers,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_ENTITY_ACTIONS_ADVANCED_H
#define LEMMINGS_ENTITY_ACTIONS_ADVANCED_H

#include "entity_actions_basic.h"

enum LmnEntityActionsAdvancedEntry {
    LMN_ENTITY_ACTIONS_ADVANCED_SELECTOR_6=6,
    LMN_ENTITY_ACTIONS_ADVANCED_SELECTOR_7=7,
    LMN_ENTITY_ACTIONS_ADVANCED_SELECTOR_8=8,
    LMN_ENTITY_ACTIONS_ADVANCED_SELECTOR_9=9
};

/* Child statuses retain the sound core's numeric identities. READY means the
   action path is stopped immediately before its live outer near RET. */
enum LmnEntityActionsAdvancedStatus {
    LMN_ENTITY_ACTIONS_ADVANCED_READY=LMN_ENTITY_ACTION_SOUND_READY,
    LMN_ENTITY_ACTIONS_ADVANCED_UNBOUND_VECTOR=
        LMN_ENTITY_ACTION_SOUND_UNBOUND_VECTOR,
    LMN_ENTITY_ACTIONS_ADVANCED_UNTRANSLATED_CHILD=
        LMN_ENTITY_ACTION_SOUND_UNTRANSLATED_CHILD,
    LMN_ENTITY_ACTIONS_ADVANCED_CHANGED_DRIVER_CHILD=
        LMN_ENTITY_ACTION_SOUND_CHANGED_DRIVER_CHILD,
    LMN_ENTITY_ACTIONS_ADVANCED_CHANGED_INTERRUPT_RETURN=
        LMN_ENTITY_ACTION_SOUND_CHANGED_INTERRUPT_RETURN,
    LMN_ENTITY_ACTIONS_ADVANCED_SOUND_INVALID_ENTRY=
        LMN_ENTITY_ACTION_SOUND_INVALID_ENTRY,
    LMN_ENTITY_ACTIONS_ADVANCED_INVALID_CHILD=
        LMN_ENTITY_ACTION_SOUND_INVALID_CHILD,
    LMN_ENTITY_ACTIONS_ADVANCED_INVALID_ENTRY=7
};

/* Logical live registers at selector 6/7/8/9 JMP entries. */
typedef LmnEntityActionsBasicCall LmnEntityActionsAdvancedCall;
typedef LmnEntityActionsBasicResult LmnEntityActionsAdvancedResult;

/* Executes one known selector action, stopping at the shared failure RET or
   composing the existing feedback/service tail without adding a CALL frame. */
LmnEntityActionsAdvancedResult lmn_entity_actions_advanced_core(
    uint8_t *memory,const LmnEntityActionsAdvancedCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Executes the actual outer near RET only for READY, reading live SS:SP. */
uint16_t lmn_entity_actions_advanced_adapter(uint8_t *memory,LmnRegs *registers,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_ENTITY_ACTIONS_BASIC_H
#define LEMMINGS_ENTITY_ACTIONS_BASIC_H

#include "entity_action_sound.h"

enum LmnEntityActionsBasicEntry {
    LMN_ENTITY_ACTIONS_BASIC_SELECTOR_2=2,
    LMN_ENTITY_ACTIONS_BASIC_SELECTOR_3=3,
    LMN_ENTITY_ACTIONS_BASIC_SELECTOR_4=4
};

/* Child statuses retain the sound core's numeric identities. READY means the
   action path is stopped immediately before its live outer near RET. */
enum LmnEntityActionsBasicStatus {
    LMN_ENTITY_ACTIONS_BASIC_READY=LMN_ENTITY_ACTION_SOUND_READY,
    LMN_ENTITY_ACTIONS_BASIC_UNBOUND_VECTOR=
        LMN_ENTITY_ACTION_SOUND_UNBOUND_VECTOR,
    LMN_ENTITY_ACTIONS_BASIC_UNTRANSLATED_CHILD=
        LMN_ENTITY_ACTION_SOUND_UNTRANSLATED_CHILD,
    LMN_ENTITY_ACTIONS_BASIC_CHANGED_DRIVER_CHILD=
        LMN_ENTITY_ACTION_SOUND_CHANGED_DRIVER_CHILD,
    LMN_ENTITY_ACTIONS_BASIC_CHANGED_INTERRUPT_RETURN=
        LMN_ENTITY_ACTION_SOUND_CHANGED_INTERRUPT_RETURN,
    LMN_ENTITY_ACTIONS_BASIC_SOUND_INVALID_ENTRY=
        LMN_ENTITY_ACTION_SOUND_INVALID_ENTRY,
    LMN_ENTITY_ACTIONS_BASIC_INVALID_CHILD=
        LMN_ENTITY_ACTION_SOUND_INVALID_CHILD,
    LMN_ENTITY_ACTIONS_BASIC_INVALID_ENTRY=7
};

/* Logical live register roles at the selector 2/3/4 JMP entries. */
typedef struct LmnEntityActionsBasicCall {
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityActionsBasicCall;

typedef struct LmnEntityActionsBasicResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityActionsBasicResult;

/* Executes one independently known selector action. Failure paths stop at
   shared RET 320C; successful paths compose the 31E5 feedback tail without
   adding a CALL frame. */
LmnEntityActionsBasicResult lmn_entity_actions_basic_core(uint8_t *memory,
    const LmnEntityActionsBasicCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Executes the action's actual outer RET only for READY, reading SS:SP live. */
uint16_t lmn_entity_actions_basic_adapter(uint8_t *memory,LmnRegs *registers,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

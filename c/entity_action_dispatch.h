#ifndef LEMMINGS_ENTITY_ACTION_DISPATCH_H
#define LEMMINGS_ENTITY_ACTION_DISPATCH_H

#include "entity_actions_basic.h"

enum LmnEntityActionDispatchStatus {
    LMN_ENTITY_ACTION_DISPATCH_READY=0,
    LMN_ENTITY_ACTION_DISPATCH_UNTRANSLATED_ACTION=1,
    LMN_ENTITY_ACTION_DISPATCH_BASIC_CHILD_STOP=2
};

/* Logical live register roles entering the fixed 3150h dispatch prefix. */
typedef struct LmnEntityActionDispatchCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityActionDispatchCall;

/* Diagnostics: no child is 0/FFFF; a composed basic action reports its entry
   and raw child status, including READY. An untranslated action reports its
   target/FFFF. Neither diagnostic inserts an original stack frame. */
typedef struct LmnEntityActionDispatchResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} LmnEntityActionDispatchResult;

/* Executes only the known gates/latch/selector prefix. Selectors 2, 3 and 4
   compose their direct-JMP child; other action entries remain explicit stops. */
LmnEntityActionDispatchResult lmn_entity_action_dispatch_core(uint8_t *memory,
    const LmnEntityActionDispatchCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Executes an actual live outer RET only when the core returns READY. */
uint16_t lmn_entity_action_dispatch_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

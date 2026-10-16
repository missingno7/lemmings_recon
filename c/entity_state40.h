#ifndef LEMMINGS_ENTITY_STATE40_H
#define LEMMINGS_ENTITY_STATE40_H

#include "entity_finish.h"

enum LmnEntityState40Status {
    LMN_ENTITY_STATE40_READY=0,
    LMN_ENTITY_STATE40_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE40_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE40_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_STATE40_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE40_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_STATE40_INVALID_CHILD=6
};

/* Logical live values entering the state-0040 body. The register packet is
   confined to the oracle adapter; all record and stack data stays in memory. */
typedef struct LmnEntityState40Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState40Call;

typedef struct LmnEntityState40Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState40Result;

/* Executes 2637..2692. Direct JMPs to 2148 compose the shared finish core;
   ordinary successful exits stop at 1FEB without running the iteration tail. */
LmnEntityState40Result lmn_entity_state40_core(uint8_t *memory,
    const LmnEntityState40Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Oracle adapter: applies the logical result and IP, without an extra RET. */
uint16_t lmn_entity_state40_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

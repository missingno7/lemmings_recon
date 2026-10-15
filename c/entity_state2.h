#ifndef LEMMINGS_ENTITY_STATE2_H
#define LEMMINGS_ENTITY_STATE2_H

#include "entity_finish.h"
#include "entity_mask.h"
#include "entity_pattern.h"

enum LmnEntityState2Status {
    LMN_ENTITY_STATE2_READY=0,
    LMN_ENTITY_STATE2_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE2_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE2_CHANGED_PC_CHILD_RETURN=3,
    LMN_ENTITY_STATE2_CHANGED_PC_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE2_CHANGED_PATTERN_RETURN=5,
    LMN_ENTITY_STATE2_CHANGED_MASK_RETURN=6,
    LMN_ENTITY_STATE2_CHANGED_FINISH_CALL_RETURN=7,
    LMN_ENTITY_STATE2_INVALID_CHILD=8
};

/* Logical live values at the state-0002 JMP entry. The record and all maps
   remain in canonical memory; LmnRegs is used only by the adapter and the
   existing INT 60 boundary. */
typedef struct LmnEntityState2Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState2Call;

typedef struct LmnEntityState2Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState2Result;

/* Executes 2350..23BE, stopping at the 1FEB shared tail or at a changed
   child target. Calls to 283B and 5DF8 use live SS frames and optional bus
   callbacks; UNKNOWN byte 2382 is not executed or included. */
LmnEntityState2Result lmn_entity_state2_core(uint8_t *memory,
    const LmnEntityState2Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnRasterBus *bus);

/* Oracle adapter applies returned registers and continuation only. */
uint16_t lmn_entity_state2_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,const LmnRasterBus *bus);

#endif

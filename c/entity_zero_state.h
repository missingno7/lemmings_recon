#ifndef LEMMINGS_ENTITY_ZERO_STATE_H
#define LEMMINGS_ENTITY_ZERO_STATE_H

#include "entity_finish.h"
#include "entity_pixel.h"

enum LmnEntityZeroStateStatus {
    LMN_ENTITY_ZERO_READY=0,
    LMN_ENTITY_ZERO_UNBOUND_VECTOR=1,
    LMN_ENTITY_ZERO_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_ZERO_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_ZERO_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_ZERO_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_ZERO_INVALID_CHILD=6,
    LMN_ENTITY_ZERO_CHANGED_PIXEL_RETURN=7
};

/* Logical live values entering 2047. These names retain the native register
   roles but keep the boundary separate from the LmnRegs adapter convention. */
typedef struct LmnEntityZeroStateCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityZeroStateCall;

typedef struct LmnEntityZeroStateResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityZeroStateResult;

/* Executes the 2047 body and composes its actual CALL/JMP children. The
   successful boundary is the shared 1FEB continuation; it does not execute
   an outer return or copy the live entity record. */
LmnEntityZeroStateResult lmn_entity_zero_state_core(uint8_t *memory,
    const LmnEntityZeroStateCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Oracle adapter for a register packet; it only applies the returned state
   and IP and returns the explicit seam status. */
uint16_t lmn_entity_zero_state_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

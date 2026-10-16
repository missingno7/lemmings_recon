#ifndef LEMMINGS_ENTITY_LATE_STATES_H
#define LEMMINGS_ENTITY_LATE_STATES_H

#include "entity_finish.h"
#include "entity_pixel.h"

enum LmnEntityLateStatesEntry {
    LMN_ENTITY_LATE_STATE_8000 = 0,
    LMN_ENTITY_LATE_FLAG80_OVERRIDE = 1
};

enum LmnEntityLateStatesStatus {
    LMN_ENTITY_LATE_READY = 0,
    LMN_ENTITY_LATE_UNBOUND_VECTOR = 1,
    LMN_ENTITY_LATE_UNTRANSLATED_SOUND = 2,
    LMN_ENTITY_LATE_CHANGED_CHILD_RETURN = 3,
    LMN_ENTITY_LATE_CHANGED_INTERRUPT_RETURN = 4,
    LMN_ENTITY_LATE_CHANGED_FINISH_CALL_RETURN = 5,
    LMN_ENTITY_LATE_INVALID_CHILD = 6,
    LMN_ENTITY_LATE_CHANGED_PIXEL_RETURN = 7,
    LMN_ENTITY_LATE_INVALID_ENTRY = 8
};

/* Logical live values entering either direct-JMP state entry. The record,
   callback slots, stack words and device aliases remain in canonical memory. */
typedef struct LmnEntityLateStatesCall {
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityLateStatesCall;

typedef struct LmnEntityLateStatesResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityLateStatesResult;

/* Executes one direct entry and composes its actual near CALL/RET, INT61/IRET,
   or shared-finish boundary. Successful bodies stop at 1FEB. */
LmnEntityLateStatesResult lmn_entity_late_states_core(uint8_t *memory,
    const LmnEntityLateStatesCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Register adapter for original-code differential boundaries. */
uint16_t lmn_entity_late_states_adapter(uint8_t *memory,LmnRegs *registers,
    enum LmnEntityLateStatesEntry entry,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

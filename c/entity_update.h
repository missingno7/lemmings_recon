#ifndef LEMMINGS_ENTITY_UPDATE_H
#define LEMMINGS_ENTITY_UPDATE_H

#include "entity_cadence.h"
#include "entity_countdown.h"
#include "entity_finish.h"
#include "entity_late_states.h"
#include "entity_state10.h"
#include "entity_state100.h"
#include "entity_state2.h"
#include "entity_state20.h"
#include "entity_state200.h"
#include "entity_state4.h"
#include "entity_state40.h"
#include "entity_state400.h"
#include "entity_state8.h"
#include "entity_state80.h"
#include "entity_state800.h"
#include "entity_zero_state.h"
#include "entity_vga.h"

enum LmnEntityUpdateStatus {
    /* The logical core stopped on the identified outer RET instruction.
       The adapter must fetch that RET's live SS:SP word. */
    LMN_ENTITY_UPDATE_RETURN_PENDING=0,
    /* A composed child returned a non-READY status. child_entry and
       child_status preserve the child's actual entry and raw enum value. */
    LMN_ENTITY_UPDATE_CHILD_BOUNDARY=1,
    /* A real CALL executed its child RET from live SS:SP to a changed IP. */
    LMN_ENTITY_UPDATE_CHANGED_CALL_RETURN=2
};

enum { LMN_ENTITY_UPDATE_NO_CHILD_STATUS=0xffffu };

/* Live register roles at AdvanceEntityRecords (1F19). Memory-backed globals,
   entity records, and every stack save remain in the supplied 1 MiB image. */
typedef struct LmnEntityUpdateCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityUpdateCall;

typedef struct LmnEntityUpdateResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
    uint16_t child_entry,child_status;
} LmnEntityUpdateResult;

/* Executes the known 1F19..2046 outer update body, composing maintained
   state, readback, countdown and finish cores. It stops immediately before
   the live near RET at 2004, 203B or 2046. No iteration or scan cap is added;
   callers that use callbacks must bound those callbacks externally. */
LmnEntityUpdateResult lmn_entity_update_core(uint8_t *memory,
    const LmnEntityUpdateCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Applies a core result. RETURN_PENDING executes the actual RET word through
   the supplied memory/bus; child boundaries transfer to their continuation. */
uint16_t lmn_entity_update_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

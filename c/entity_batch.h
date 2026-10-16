#ifndef LEMMINGS_ENTITY_BATCH_H
#define LEMMINGS_ENTITY_BATCH_H

#include "entity_create.h"
#include "entity_update.h"

enum LmnEntityBatchStatus {
    LMN_ENTITY_BATCH_READY=0,
    LMN_ENTITY_BATCH_CHANGED_CALL_RETURN=1,
    LMN_ENTITY_BATCH_CHILD_BOUNDARY=2
};

enum { LMN_ENTITY_BATCH_NO_CHILD_STATUS=0xffffu };

/* Logical register values at the two-call 01B0 prefix. */
typedef struct LmnEntityBatchCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityBatchCall;

typedef struct LmnEntityBatchResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} LmnEntityBatchResult;

/* Executes the scoped 01B0..01B5 prefix, including both actual near CALL
   frames. READY stops at 01B6 before the following CALL 3944. For a changed
   CALL return, child_entry/status identify the completed child; for a child
   boundary they retain the nested dependency entry and raw status. */
LmnEntityBatchResult lmn_entity_batch_core(uint8_t *memory,
    const LmnEntityBatchCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Applies the logical result and IP. The scope has no outer RET. */
uint16_t lmn_entity_batch_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

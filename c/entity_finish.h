#ifndef LEMMINGS_ENTITY_FINISH_H
#define LEMMINGS_ENTITY_FINISH_H

#include "entity_interactions.h"

enum LmnEntityFinishEntry {
    LMN_ENTITY_FINISH_INTERACTION_CALL_1FE8=0,
    LMN_ENTITY_FINISH_STORE_HEIGHT_20D6=1,
    LMN_ENTITY_FINISH_MARK_INACTIVE_20E2=2,
    LMN_ENTITY_FINISH_RESOLVE_HEIGHT_2148=3
};

enum LmnEntityFinishStatus {
    LMN_ENTITY_FINISH_RETURNED=0,
    LMN_ENTITY_FINISH_UNBOUND_VECTOR=1,
    LMN_ENTITY_FINISH_UNTRANSLATED_SOUND=2,
    LMN_ENTITY_FINISH_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_FINISH_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_FINISH_CHANGED_CALL_RETURN=5,
    LMN_ENTITY_FINISH_INVALID_ENTRY=6
};

/* Named live values consumed or preserved at the shared JMP entries.
   candidate_y is BP; cursor and auxiliary names describe their data roles.
   CALL/RET stack traffic still uses the canonical memory image. */
typedef struct LmnEntityFinishCall {
    uint16_t entry;
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityFinishCall;

typedef struct LmnEntityFinishResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityFinishResult;

LmnEntityFinishResult lmn_entity_finish_core(uint8_t *memory,
    const LmnEntityFinishCall *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Register adapters are oracle boundaries. The 1FEB body remains the caller's
   continuation; this adapter only transfers IP to the returned address. */
uint16_t lmn_entity_finish_adapter(uint8_t *memory,LmnRegs *registers,
    uint16_t entry,const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

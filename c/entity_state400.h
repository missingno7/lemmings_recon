#ifndef LEMMINGS_ENTITY_STATE400_H
#define LEMMINGS_ENTITY_STATE400_H

#include "entity_finish.h"
#include "entity_pixel.h"

enum LmnEntityState400Status {
    LMN_ENTITY_STATE400_READY=0,
    LMN_ENTITY_STATE400_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE400_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE400_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_STATE400_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE400_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_STATE400_INVALID_CHILD=6,
    LMN_ENTITY_STATE400_CHANGED_PIXEL_RETURN=7
};

/* Logical live values entering state 0400. Entity records, the unchecked
   pair table and stack frames remain in canonical memory. */
typedef struct LmnEntityState400Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState400Call;

typedef struct LmnEntityState400Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState400Result;

/* Executes 2A6D..2B34 and composes selected pixel calls plus the shared
   1FE8/20E2 tails through their logical cores. UNKNOWN bytes are excluded. */
LmnEntityState400Result lmn_entity_state400_core(uint8_t *memory,
    const LmnEntityState400Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

uint16_t lmn_entity_state400_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

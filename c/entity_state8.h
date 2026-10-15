#ifndef LEMMINGS_ENTITY_STATE8_H
#define LEMMINGS_ENTITY_STATE8_H

#include "entity_finish.h"
#include "entity_pixel.h"

enum LmnEntityState8Status {
    LMN_ENTITY_STATE8_READY=0,
    LMN_ENTITY_STATE8_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE8_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE8_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_STATE8_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE8_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_STATE8_INVALID_CHILD=6,
    LMN_ENTITY_STATE8_CHANGED_PIXEL_RETURN=7
};

/* Logical live machine values entering the state-0008 body. The register
   packet remains confined to the oracle adapter. */
typedef struct LmnEntityState8Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState8Call;

typedef struct LmnEntityState8Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState8Result;

/* Executes 23BF..23F2, including the actual 5DC6 CALL/RET, then composes
   the direct JMP to the shared 2148 entry. Successful work ends at 1FEB. */
LmnEntityState8Result lmn_entity_state8_core(uint8_t *memory,
    const LmnEntityState8Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Oracle adapter that applies returned live registers and continuation only. */
uint16_t lmn_entity_state8_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

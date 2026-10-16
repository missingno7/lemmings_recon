#ifndef LEMMINGS_ENTITY_STATE200_H
#define LEMMINGS_ENTITY_STATE200_H

#include "coordinate_pixel.h"
#include "entity_finish.h"
#include "entity_mask_rows.h"
#include "entity_pixel.h"
#include "sound_interrupt.h"

enum LmnEntityState200Status {
    LMN_ENTITY_STATE200_READY=0,
    LMN_ENTITY_STATE200_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE200_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE200_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_STATE200_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE200_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_STATE200_INVALID_CHILD=6,
    LMN_ENTITY_STATE200_CHANGED_PIXEL_RETURN=7,
    LMN_ENTITY_STATE200_CHANGED_COORDINATE_RETURN=8,
    LMN_ENTITY_STATE200_CHANGED_MASK_RETURN=9
};

/* Logical live values entering the state-0200 body. Memory-backed records and
   actual SS call/temporary-save words remain in the canonical memory image. */
typedef struct LmnEntityState200Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState200Call;

typedef struct LmnEntityState200Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState200Result;

/* Executes only the known 287D..2A6C state-0200 body. Mask, coordinate,
   pixel, INT61 and shared-finish seams preserve actual live SS words/returns. */
LmnEntityState200Result lmn_entity_state200_core(uint8_t *memory,
    const LmnEntityState200Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

uint16_t lmn_entity_state200_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

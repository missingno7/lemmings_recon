#ifndef LEMMINGS_ENTITY_STATE800_H
#define LEMMINGS_ENTITY_STATE800_H

#include "entity_finish.h"
#include "entity_mask_rows.h"
#include "entity_pixel.h"
#include "sound_interrupt.h"

enum LmnEntityState800Status {
    LMN_ENTITY_STATE800_READY=0,
    LMN_ENTITY_STATE800_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE800_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE800_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_STATE800_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE800_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_STATE800_INVALID_CHILD=6,
    LMN_ENTITY_STATE800_CHANGED_PIXEL_RETURN=7,
    LMN_ENTITY_STATE800_CHANGED_MASK_RETURN=8
};

/* Logical live register roles entering the state-0800 body. Entity records,
   mask/map data, and actual SS call/temporary-save words remain in memory. */
typedef struct LmnEntityState800Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState800Call;

typedef struct LmnEntityState800Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState800Result;

/* Executes only known bytes in 2B35..2D0E. UNKNOWN 2B50 is excluded. The
   mask, pixel, INT 61h and shared finish seams use their native logical cores. */
LmnEntityState800Result lmn_entity_state800_core(uint8_t *memory,
    const LmnEntityState800Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

uint16_t lmn_entity_state800_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

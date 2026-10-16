#ifndef LEMMINGS_ENTITY_STATE80_H
#define LEMMINGS_ENTITY_STATE80_H

#include "entity_finish.h"
#include "entity_pixel.h"
#include "entity_stroke.h"
#include "pcspeaker_interrupt.h"
#include "sound_interrupt.h"

enum LmnEntityState80Status {
    LMN_ENTITY_STATE80_READY=0,
    LMN_ENTITY_STATE80_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE80_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE80_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_STATE80_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE80_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_STATE80_INVALID_CHILD=6,
    LMN_ENTITY_STATE80_CHANGED_PIXEL_RETURN=7,
    LMN_ENTITY_STATE80_CHANGED_STROKE_PIXEL_RETURN=8,
    LMN_ENTITY_STATE80_CHANGED_STROKE_CALL_RETURN=9
};

/* Logical live values at the state-0080 entry. Memory-backed records and
   actual SS save/return words remain in the canonical memory image. */
typedef struct LmnEntityState80Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState80Call;

typedef struct LmnEntityState80Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState80Result;

/* Executes only the known 2693..27E7 state-0080 body. The four UNKNOWN bytes
   remain outside this core. Pixel/stroke calls consume and check their live
   return words; optional INT60/INT61 and shared finish paths compose directly. */
LmnEntityState80Result lmn_entity_state80_core(uint8_t *memory,
    const LmnEntityState80Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

uint16_t lmn_entity_state80_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

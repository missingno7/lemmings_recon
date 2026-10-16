#ifndef LEMMINGS_ENTITY_STATE10_H
#define LEMMINGS_ENTITY_STATE10_H

#include "entity_finish.h"
#include "entity_pixel.h"
#include "entity_vga.h"

enum LmnEntityState10Status {
    LMN_ENTITY_STATE10_READY=0,
    LMN_ENTITY_STATE10_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE10_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE10_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_STATE10_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE10_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_STATE10_INVALID_CHILD=6,
    LMN_ENTITY_STATE10_CHANGED_PIXEL_RETURN=7,
    LMN_ENTITY_STATE10_CHANGED_EXCHANGE_RETURN=8
};

/* Logical live values at the state-0010 entry. Memory-backed entity records,
   stack saves and display state remain in the canonical image. */
typedef struct LmnEntityState10Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState10Call;

typedef struct LmnEntityState10Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState10Result;

/* Executes the known 23F3..254E body and stops at its actual shared-tail or
   child boundary. Calls use live SS return words and optional bus callbacks. */
LmnEntityState10Result lmn_entity_state10_core(uint8_t *memory,
    const LmnEntityState10Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

uint16_t lmn_entity_state10_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

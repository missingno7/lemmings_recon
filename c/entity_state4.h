#ifndef LEMMINGS_ENTITY_STATE4_H
#define LEMMINGS_ENTITY_STATE4_H

#include "entity_finish.h"
#include "entity_pixel.h"

enum LmnEntityState4Status {
    LMN_ENTITY_STATE4_READY=0,
    LMN_ENTITY_STATE4_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE4_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE4_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_STATE4_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE4_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_STATE4_INVALID_CHILD=6,
    LMN_ENTITY_STATE4_CHANGED_PIXEL_RETURN=7
};

/* Live values at the state-0004 entry. These remain a logical boundary,
   distinct from the register packet used only by the oracle adapter. */
typedef struct LmnEntityState4Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState4Call;

typedef struct LmnEntityState4Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState4Result;

/* Executes 21B0..22DE and its selected 5DC6, INT 61h, and shared-tail
   children through their native logical cores. The normal boundary is the
   shared 1FEB continuation; no outer iteration body is executed here. */
LmnEntityState4Result lmn_entity_state4_core(uint8_t *memory,
    const LmnEntityState4Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

/* Oracle adapter: applies all returned registers and IP without executing
   an extra RET or the shared 1FEB continuation. */
uint16_t lmn_entity_state4_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

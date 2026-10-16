#ifndef LEMMINGS_ENTITY_STATE20_H
#define LEMMINGS_ENTITY_STATE20_H

#include "entity_finish.h"
#include "entity_pixel.h"

enum LmnEntityState20Status {
    LMN_ENTITY_STATE20_READY=0,
    LMN_ENTITY_STATE20_UNBOUND_VECTOR=1,
    LMN_ENTITY_STATE20_UNTRANSLATED_CHILD=2,
    LMN_ENTITY_STATE20_CHANGED_CHILD_RETURN=3,
    LMN_ENTITY_STATE20_CHANGED_INTERRUPT_RETURN=4,
    LMN_ENTITY_STATE20_CHANGED_FINISH_CALL_RETURN=5,
    LMN_ENTITY_STATE20_INVALID_CHILD=6,
    LMN_ENTITY_STATE20_CHANGED_PIXEL_RETURN=7
};

/* Logical live values entering the state-0020 body. The register packet is
   confined to the oracle adapter. */
typedef struct LmnEntityState20Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState20Call;

typedef struct LmnEntityState20Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState20Result;

/* Executes 254F..2636. Pixel CALLs consume their actual live return words;
   original JMPs compose the shared 1FE8/2148/1FEB continuations directly. */
LmnEntityState20Result lmn_entity_state20_core(uint8_t *memory,
    const LmnEntityState20Call *call,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

uint16_t lmn_entity_state20_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnPcSpeakerBinding *pc_binding,
    const LmnSoundDriverBinding *sound_binding,const LmnRasterBus *bus);

#endif

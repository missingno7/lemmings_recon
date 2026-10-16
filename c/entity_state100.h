#ifndef LEMMINGS_ENTITY_STATE100_H
#define LEMMINGS_ENTITY_STATE100_H

#include "entity_pattern.h"
#include "entity_pixel.h"

enum LmnEntityState100Status {
    LMN_ENTITY_STATE100_READY=0,
    LMN_ENTITY_STATE100_CHANGED_PIXEL_RETURN=1,
    LMN_ENTITY_STATE100_CHANGED_PATTERN_RETURN=2
};

/* Logical live values entering state 0100. Record fields and stack saves stay
   in canonical memory; this packet is only the native oracle boundary. */
typedef struct LmnEntityState100Call {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityState100Call;

typedef struct LmnEntityState100Result {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityState100Result;

/* Executes 27E8..283A. It composes the pixel and pattern children through
   actual SS return words. Both normal branches stop at 1FEB. */
LmnEntityState100Result lmn_entity_state100_core(uint8_t *memory,
    const LmnEntityState100Call *call,const LmnRasterBus *bus);

/* Oracle adapter: applies the logical result and continuation, no extra RET. */
uint16_t lmn_entity_state100_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

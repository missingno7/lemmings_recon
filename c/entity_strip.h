#ifndef LEMMINGS_ENTITY_STRIP_H
#define LEMMINGS_ENTITY_STRIP_H

#include "special_blit.h"

enum LmnEntityStripStatus {
    LMN_ENTITY_STRIP_READY = 0
};

/* Live register roles at DrawEntityTwoByteStrip (6F7B). */
typedef struct LmnEntityStripCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityStripCall;

typedef struct LmnEntityStripResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityStripResult;

/* Executes the 6F7B body through STI and its live POP DS, then stops before
   the actual RET at 6FE1. The routine adds no guest CALL frame of its own. */
LmnEntityStripResult lmn_draw_entity_two_byte_strip_core(
    uint8_t *memory,const LmnEntityStripCall *call,
    const LmnRasterBus *bus);

/* Applies returned roles and consumes the actual live SS:SP RET when READY. */
uint16_t lmn_draw_entity_two_byte_strip_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

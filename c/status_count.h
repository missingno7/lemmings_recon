#ifndef LEMMINGS_STATUS_COUNT_H
#define LEMMINGS_STATUS_COUNT_H

#include "special_blit.h"

enum LmnStatusCountStatus {
    LMN_STATUS_COUNT_READY = 0
};

/* Live register roles at DrawStatusCount (762A). */
typedef struct LmnStatusCountCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnStatusCountCall;

typedef struct LmnStatusCountResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnStatusCountResult;

/* The core stops before the selected live RET at 76DA or 7707. */
LmnStatusCountResult lmn_draw_status_count_core(uint8_t *memory,
    const LmnStatusCountCall *call,const LmnRasterBus *bus);

/* Applies the result and consumes the actual return word from SS:SP. */
uint16_t lmn_draw_status_count_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

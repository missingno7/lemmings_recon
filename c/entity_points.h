#ifndef LEMMINGS_ENTITY_POINTS_H
#define LEMMINGS_ENTITY_POINTS_H

#include "special_blit.h"

enum LmnEntityPointsStatus {
    LMN_ENTITY_POINTS_READY = 0
};

/* Live register roles at DrawEntityPointCloud (6E83). */
typedef struct LmnEntityPointsCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityPointsCall;

typedef struct LmnEntityPointsResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityPointsResult;

/* Stops immediately before the actual near RET at 6F7A. */
LmnEntityPointsResult lmn_draw_entity_point_cloud_core(uint8_t *memory,
    const LmnEntityPointsCall *call,const LmnRasterBus *bus);

/* Applies all logical roles and consumes the live near-RET word. */
uint16_t lmn_draw_entity_point_cloud_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

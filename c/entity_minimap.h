#ifndef LEMMINGS_ENTITY_MINIMAP_H
#define LEMMINGS_ENTITY_MINIMAP_H

#include "special_blit.h"

enum LmnEntityMinimapStatus {
    LMN_ENTITY_MINIMAP_READY = 0
};

/* Live register roles at DrawEntityMinimapPixel (6FE2). */
typedef struct LmnEntityMinimapCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityMinimapCall;

typedef struct LmnEntityMinimapResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityMinimapResult;

/* Stops immediately before the shared 706E near RET. */
LmnEntityMinimapResult lmn_draw_entity_minimap_pixel_core(uint8_t *memory,
    const LmnEntityMinimapCall *call,const LmnRasterBus *bus);

/* Applies all logical roles and consumes the actual live near-RET word. */
uint16_t lmn_draw_entity_minimap_pixel_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

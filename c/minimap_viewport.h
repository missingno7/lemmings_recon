#ifndef LEMMINGS_MINIMAP_VIEWPORT_H
#define LEMMINGS_MINIMAP_VIEWPORT_H

#include "special_blit.h"

enum LmnMinimapViewportStatus {
    LMN_MINIMAP_VIEWPORT_READY = 0
};

/* Live register roles at DrawMinimapViewport (7A5A). */
typedef struct LmnMinimapViewportCall {
    uint16_t value, map_cursor, count, auxiliary_value;
    uint16_t record_cursor, object_cursor, candidate_y;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnMinimapViewportCall;

typedef struct LmnMinimapViewportResult {
    uint16_t value, map_cursor, count, auxiliary_value;
    uint16_t record_cursor, object_cursor, candidate_y;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status;
} LmnMinimapViewportResult;

/* Draws to ES=A000 and stops at the live RET 7BB7 boundary. */
LmnMinimapViewportResult lmn_draw_minimap_viewport_core(uint8_t *memory,
    const LmnMinimapViewportCall *call, const LmnRasterBus *bus);

/* Applies the core result and executes the actual RET from SS:SP when READY. */
uint16_t lmn_draw_minimap_viewport_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus);

#endif

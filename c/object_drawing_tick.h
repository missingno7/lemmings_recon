#ifndef LEMMINGS_OBJECT_DRAWING_TICK_H
#define LEMMINGS_OBJECT_DRAWING_TICK_H

#include "drawing_render.h"

enum LmnObjectDrawingTickStatus {
    LMN_OBJECT_DRAWING_TICK_READY = 0,
    LMN_OBJECT_DRAWING_TICK_MISSING_PROVIDER = 1,
    LMN_OBJECT_DRAWING_TICK_CHANGED_CHILD_NEAR = 2,
    LMN_OBJECT_DRAWING_TICK_CHILD_BOUNDARY = 3,
    LMN_OBJECT_DRAWING_TICK_CHANGED_FAR_RETURN = 4
};

/* Live 13 register roles at DrawLevelObjectGraphics (7BB8). Entry starts with
   CX=32, but each active iteration reloads CX from the live saved stack word;
   the loop therefore follows the restored CX rather than imposing a cap.
   game_data_segment is an explicit child-provider input, not a CPU register. */
typedef struct LmnObjectDrawingTickCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t game_data_segment;
} LmnObjectDrawingTickCall;

typedef struct LmnObjectDrawingTickResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t game_data_segment;
    uint16_t continuation,status;
} LmnObjectDrawingTickResult;

/* Runs the 32-entry loop through the native 8822 bitmap child. The core stops
   before the near RET at 7C09 or at an explicit child/provider seam. */
LmnObjectDrawingTickResult lmn_draw_level_object_graphics_core(
    uint8_t *memory,const LmnObjectDrawingTickCall *call,
    const LmnRasterBus *bus,const LmnRasterBytePorts *ports);

/* Applies all returned roles and consumes the actual outer SS:SP RET only
   when the core reaches READY. */
uint16_t lmn_draw_level_object_graphics_adapter(uint8_t *memory,
    LmnRegs *registers,uint16_t game_data_segment,const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports);

#endif

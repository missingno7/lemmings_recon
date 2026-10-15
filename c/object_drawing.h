#ifndef LEMMINGS_OBJECT_DRAWING_H
#define LEMMINGS_OBJECT_DRAWING_H

#include "drawing_source.h"
#include "drawing_render.h"

typedef struct LmnObjectDrawingCall {
    uint16_t data_segment, game_data_segment, output_segment;
    uint16_t code_segment, stack_segment, stack_offset;
    /* Entry BX, DX and BP values. The loop overwrites SI, DI and CX itself. */
    uint16_t second_source_cursor, width_state, control, flags;
} LmnObjectDrawingCall;

typedef struct LmnObjectDrawingResult {
    LmnDrawingSourceResult state;
    uint16_t data_segment, output_segment, code_segment;
    uint16_t stopped, missing_provider, changed_child_near;
    uint16_t changed_far_return, ready_to_return;
} LmnObjectDrawingResult;

/* Executes the object-drawing suffix beginning at397D. It composes the
   existing planar-bitmap core, stops on child continuations or changed far
   returns, and stops at the caller's own39CD RET with ready_to_return set.
   Missing or incomplete byte-port callbacks leave969C as an explicit stop. */
LmnObjectDrawingResult lmn_draw_level_objects_core(
    uint8_t *memory, const LmnObjectDrawingCall *call,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports);

/* Boundary adapter for397D..39CD. It consumes the actual SS word for the
   suffix's near RET only when the core reports ready_to_return. */
void lmn_draw_level_objects_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports);

#endif

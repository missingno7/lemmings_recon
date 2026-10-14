#ifndef LEMMINGS_DRAWING_CLIP_H
#define LEMMINGS_DRAWING_CLIP_H

#include "special_blit.h"

typedef struct LmnDrawingClipCall {
    uint16_t data_segment, stack_segment, stack_offset;
    uint16_t left, top, packed_height, width;
    uint16_t source_cursor, destination_cursor, control, flags;
} LmnDrawingClipCall;

typedef struct LmnDrawingClipResult {
    uint16_t left, top, packed_height, width;
    uint16_t source_cursor, destination_cursor, control;
    uint16_t stack_offset, flags;
} LmnDrawingClipResult;

/* Logical core for ClipPlanarDrawingRectangle. The stack frame and drawing
   fields remain live in the supplied 20-bit RAM/bus; the core leaves the
   near-return word at SS:SP for its register adapter. */
LmnDrawingClipResult lmn_clip_planar_drawing_rectangle_core(uint8_t *memory,
    const LmnDrawingClipCall *call, const LmnRasterBus *bus);

/* Near-call boundary adapter. It consumes the return word only after the
   logical body has restored BP and the original stack offset. */
void lmn_clip_planar_drawing_rectangle_adapter(uint8_t *memory,
    LmnRegs *regs, const LmnRasterBus *bus);

#endif

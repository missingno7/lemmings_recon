#ifndef LEMMINGS_DRAWING_DIRTY_H
#define LEMMINGS_DRAWING_DIRTY_H

#include <stdint.h>
#include "regs.h"
#include "special_blit.h"

typedef struct LmnDrawingDirtyCall {
    uint16_t data_segment;
    uint16_t stack_segment;
    uint16_t stack_offset;
    uint16_t left;
    uint16_t top;
    uint16_t packed_height;
    uint16_t width;
    uint16_t source_cursor;
    uint16_t destination_cursor;
    uint16_t control;
    uint16_t flags;
} LmnDrawingDirtyCall;

typedef struct LmnDrawingDirtyResult {
    uint16_t left;
    uint16_t top;
    uint16_t packed_height;
    uint16_t width;
    uint16_t source_cursor;
    uint16_t destination_cursor;
    uint16_t control;
    uint16_t stack_offset;
    uint16_t flags;
} LmnDrawingDirtyResult;

/* Marks bytes in the live SS dirty map selected by the word at DS:0026.
   The core leaves RET to the adapter. A null bus uses ordinary 20-bit RAM. */
LmnDrawingDirtyResult lmn_mark_drawing_dirty_cells_core(uint8_t *memory,
    const LmnDrawingDirtyCall *call, const LmnRasterBus *bus);

void lmn_mark_drawing_dirty_cells_adapter(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus);

#endif

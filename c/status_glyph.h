#ifndef LEMMINGS_STATUS_GLYPH_H
#define LEMMINGS_STATUS_GLYPH_H

#include "special_blit.h"

enum LmnStatusGlyphStatus {
    LMN_STATUS_GLYPH_READY = 0
};

/* Live register roles at DrawStatusGlyph (7708). */
typedef struct LmnStatusGlyphCall {
    uint16_t value, map_cursor, count, auxiliary_value;
    uint16_t record_cursor, object_cursor, candidate_y;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnStatusGlyphCall;

typedef struct LmnStatusGlyphResult {
    uint16_t value, map_cursor, count, auxiliary_value;
    uint16_t record_cursor, object_cursor, candidate_y;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status;
} LmnStatusGlyphResult;

/* The core stops before the branch-specific live RET. The adapter consumes
   the actual return word from canonical SS:SP after applying the result. */
LmnStatusGlyphResult lmn_draw_status_glyph_core(uint8_t *memory,
    const LmnStatusGlyphCall *call, const LmnRasterBus *bus);
uint16_t lmn_draw_status_glyph_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

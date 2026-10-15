#ifndef LEMMINGS_TEXT_GLYPH_H
#define LEMMINGS_TEXT_GLYPH_H

#include "drawing_render.h"
#include "video_restore.h"

/* The glyph routine's transient CPU image is the same twelve-register
   boundary used by the nearby video and display helpers. */
typedef LmnVideoRestoreState LmnTextGlyphState;

typedef enum LmnTextGlyphStatus {
    LMN_TEXT_GLYPH_READY = 0,
    LMN_TEXT_GLYPH_RENDERER_STOP = 1,
    LMN_TEXT_GLYPH_CHANGED_RETURN = 2,
    LMN_TEXT_GLYPH_PREPARED = 3
} LmnTextGlyphStatus;

typedef struct LmnTextGlyphResult {
    LmnTextGlyphState state;
    uint16_t code_segment, continuation;
    enum LmnTextGlyphStatus status;
} LmnTextGlyphResult;

_Static_assert(sizeof(LmnTextGlyphResult) == 32u,
    "LmnTextGlyphResult must remain a 32-byte boundary result");

/* Runs 4D78..4DBA, stopping before the relocated far CALL at4DBB after the
   live PUSH BP. Space follows the CMP branch and stops before the near RET at
   4DC1. Reads and writes use the canonical 20-bit bus; stack words wrap SP
   at16 bits and access their high byte at physical-address+1.

   The draw core requires the intact relocated operand at4DBE to target
   code_segment:8822. It directly composes the known planar bitmap core and
   returns changed or unsupported child continuations without running them. */
LmnTextGlyphResult lmn_prepare_text_glyph_core(uint8_t *memory,
    uint16_t code_segment, const LmnTextGlyphState *input,
    const LmnRasterBus *bus);

LmnTextGlyphResult lmn_draw_text_glyph_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnTextGlyphState *input, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports);

/* Maps all twelve fields and consumes the live outer near RET only on READY. */
void lmn_draw_text_glyph_adapter(uint8_t *memory, LmnRegs *registers,
    uint16_t game_data_segment, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports);

#endif

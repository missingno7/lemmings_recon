#ifndef LEMMINGS_TEXT_STREAM_H
#define LEMMINGS_TEXT_STREAM_H

#include "text_glyph.h"

/* The stream carries the same transient CPU image as its glyph child. */
typedef LmnTextGlyphState LmnTextStreamState;

typedef enum LmnTextStreamStatus {
    LMN_TEXT_STREAM_READY = 0,
    LMN_TEXT_STREAM_CHILD_STOP = 1,
    LMN_TEXT_STREAM_CHANGED_RETURN = 2
} LmnTextStreamStatus;

typedef struct LmnTextStreamResult {
    LmnTextStreamState state;
    uint16_t code_segment, continuation;
    enum LmnTextStreamStatus status;
} LmnTextStreamResult;

_Static_assert(sizeof(LmnTextStreamResult) == 32u,
    "LmnTextStreamResult must remain a 32-byte boundary result");

/* Runs 4D4D..4D76 on canonical memory, stopping before the stream RET at
   4D77. It reads live DS:SI in the incoming DF direction and composes each
   glyph directly. The glyph CALL and all saves use live SS:SP; a changed
   glyph-child continuation is returned with its actual frames intact. */
LmnTextStreamResult lmn_draw_text_stream_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnTextStreamState *input, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports);

/* Maps the twelve registers and consumes the actual outer near RET only for
   READY. */
void lmn_draw_text_stream_adapter(uint8_t *memory, LmnRegs *registers,
    uint16_t game_data_segment, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports);

#endif

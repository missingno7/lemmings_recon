#ifndef LEMMINGS_PALETTE_ROWS_H
#define LEMMINGS_PALETTE_ROWS_H

#include "palette_channels.h"

typedef enum LmnPaletteRowEntry {
    LMN_PALETTE_ROW_PACKED = 0,
    LMN_PALETTE_ROW_RGB = 1
} LmnPaletteRowEntry;

typedef enum LmnPaletteRowStatus {
    LMN_PALETTE_ROW_READY = 0,
    LMN_PALETTE_ROW_CHANNEL_STOP = 1,
    LMN_PALETTE_ROW_CHANGED_RETURN = 2
} LmnPaletteRowStatus;

typedef struct LmnPaletteRowResult {
    LmnVideoRestoreState state;
    uint16_t code_segment, continuation;
    enum LmnPaletteRowStatus status;
} LmnPaletteRowResult;

_Static_assert(sizeof(LmnPaletteRowResult) == 32u,
    "LmnPaletteRowResult must remain a 32-byte boundary result");

/* Steps one packed or RGB row, stopping before its final near RET. Child
   channel calls and all RAM/stack accesses use the optional 20-bit bus. */
LmnPaletteRowResult lmn_step_palette_row_core(uint8_t *memory,
    uint16_t code_segment, const LmnVideoRestoreState *input,
    enum LmnPaletteRowEntry entry, const LmnRasterBus *bus);

/* Applies all twelve fields and consumes the live outer near RET only when
   the core reaches the row's declared return site. */
void lmn_step_palette_row_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnPaletteRowEntry entry, const LmnRasterBus *bus);

#endif

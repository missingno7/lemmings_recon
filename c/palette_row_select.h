#ifndef LEMMINGS_PALETTE_ROW_SELECT_H
#define LEMMINGS_PALETTE_ROW_SELECT_H

#include "palette_rows.h"

/* Executes the live 5569 selector and tail-enters the selected row core.
   The verified domain preserves decoded instruction bytes and CS, with TF
   clear and IRQs quiescent. Canonical table/data/stack effects remain live. */
LmnPaletteRowResult lmn_select_and_step_palette_row_core(uint8_t *memory,
    uint16_t code_segment, const LmnVideoRestoreState *input,
    const LmnRasterBus *bus);

/* Applies the selector and row result, consuming the original near RET only
   when the selected row reaches its normal return site. */
void lmn_select_and_step_palette_row_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_ENTITY_MASK_ROWS_H
#define LEMMINGS_ENTITY_MASK_ROWS_H
#include "regs.h"
#include "special_blit.h"

typedef struct LmnEntityMaskRowsCall {
    uint16_t data_segment, stack_segment, stack_offset, record_cursor;
    uint16_t selection, alignment_index, flags;
} LmnEntityMaskRowsCall;
typedef struct LmnEntityMaskRowsResult {
    uint16_t value, mask_word, row_count, port, source_cursor;
    uint16_t destination_offset, data_segment, output_segment, stack_offset;
    uint16_t alignment_index, flags;
} LmnEntityMaskRowsResult;

/* 5FAC..6069 and 606B..613F, before the respective near RETs. Selection
   is unchecked. The ten-row entry preserves alignment_index (BP), while
   the thirteen-row entry returns its wrapped coordinate sum masked to 7.
   All saved base/DX/DS/SI words, selectors and return words remain live. */
LmnEntityMaskRowsResult lmn_draw_ten_row_entity_mask_core(uint8_t *,
    const LmnEntityMaskRowsCall *, const LmnRasterBus *);
LmnEntityMaskRowsResult lmn_draw_thirteen_row_entity_mask_core(uint8_t *,
    const LmnEntityMaskRowsCall *, const LmnRasterBus *);
void lmn_draw_ten_row_entity_mask_adapter(uint8_t *, LmnRegs *, const LmnRasterBus *);
void lmn_draw_thirteen_row_entity_mask_adapter(uint8_t *, LmnRegs *, const LmnRasterBus *);
#endif

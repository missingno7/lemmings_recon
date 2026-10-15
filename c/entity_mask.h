#ifndef LEMMINGS_ENTITY_MASK_H
#define LEMMINGS_ENTITY_MASK_H
#include "regs.h"
#include "special_blit.h"

typedef struct LmnEntityMaskCall {
    uint16_t data_segment, stack_segment, stack_offset, record_cursor, flags;
} LmnEntityMaskCall;
typedef struct LmnEntityMaskResult {
    uint16_t value, mask_word, row_count, port, source_cursor;
    uint16_t destination_offset, data_segment, output_segment, stack_offset, flags;
} LmnEntityMaskResult;

/* 5DF8..5EB8, before the common near RET at 5EB9. The early clipped-out
   path does not execute CLI/STI or push the drawing saves. All source,
   record, mirror and live SS accesses pass through the optional bus. */
LmnEntityMaskResult lmn_draw_clipped_entity_mask_core(uint8_t *,
    const LmnEntityMaskCall *, const LmnRasterBus *);
void lmn_draw_clipped_entity_mask_adapter(uint8_t *, LmnRegs *, const LmnRasterBus *);
#endif

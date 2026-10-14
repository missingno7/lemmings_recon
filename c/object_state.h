#ifndef LEMMINGS_OBJECT_STATE_H
#define LEMMINGS_OBJECT_STATE_H
#include <stdint.h>
#include "regs.h"

typedef struct LmnObjectStateCall {
    uint16_t data_segment, stack_segment, stack_offset;
    uint16_t product_high, base_cursor, flags;
} LmnObjectStateCall;

typedef struct LmnObjectStateResult {
    uint16_t value, cell_cursor, remaining_records, dimension_state;
    uint16_t source_cursor, definition_cursor, base_cursor, extra_segment;
    uint16_t stack_offset, flags, continuation;
    uint16_t changed_return;
} LmnObjectStateResult;

/* The four original calls at 376A..3775. Normal continuation is 3776;
   a changed near-return word exposes that transfer without executing its target.
   The outer 36B6 return word is not consumed by this fragment. */
LmnObjectStateResult lmn_prepare_level_object_state_core(uint8_t *,const LmnObjectStateCall *);
void lmn_prepare_level_object_state_adapter(uint8_t *,LmnRegs *);
#endif

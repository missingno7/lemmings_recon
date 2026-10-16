#ifndef LEMMINGS_DECIMAL_FIELD_H
#define LEMMINGS_DECIMAL_FIELD_H

#include <stdint.h>
#include "regs.h"
#include "special_blit.h"

typedef struct LmnDecimalFieldCall {
    uint16_t data_segment;
    uint16_t value;
    uint16_t prefix_value;
    uint16_t cursor;
    uint16_t flags;
} LmnDecimalFieldCall;

typedef struct LmnDecimalFieldResult {
    uint16_t value;
    uint16_t prefix_value;
    uint16_t cursor;
    uint16_t flags;
} LmnDecimalFieldResult;

/* 4B68: left-align the digits and leave trailing spaces; SI advances past units. */
LmnDecimalFieldResult lmn_write_decimal_field_core(uint8_t *memory,
    const LmnDecimalFieldCall *call, const LmnRasterBus *bus);
/* 4BBE: write the two-character quotient/remainder field (AL=255 -> "I5"). */
LmnDecimalFieldResult lmn_write_decimal_pair_core(uint8_t *memory,
    const LmnDecimalFieldCall *call, const LmnRasterBus *bus);

/* Apply the core result and execute the leaf's live near RET from SS:SP. */
void lmn_write_decimal_field_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus);
void lmn_write_decimal_pair_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

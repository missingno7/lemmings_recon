#ifndef LEMMINGS_DECIMAL_DIGITS_H
#define LEMMINGS_DECIMAL_DIGITS_H
#include <stdint.h>
#include "regs.h"

typedef struct LmnDecimalDigitsResult {
    uint16_t value, cursor, flags;
} LmnDecimalDigitsResult;

/* Writes the live three-byte decimal field at segment:cursor. The original
   leaves SI two bytes past its entry value after writing all three bytes. */
LmnDecimalDigitsResult lmn_write_decimal_digits_core(uint8_t *mem,
    uint16_t segment, uint16_t cursor, uint8_t number, uint16_t flags);
void lmn_write_decimal_digits_adapter(uint8_t *mem, LmnRegs *r);

#endif

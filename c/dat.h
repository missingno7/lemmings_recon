#ifndef LEMMINGS_DAT_H
#define LEMMINGS_DAT_H
#include <stdint.h>
#include "regs.h"

typedef struct LmnReverseBitsResult {
    uint16_t value, cursor, flags;
    uint8_t remaining, shifted_byte, checksum;
} LmnReverseBitsResult;

typedef struct LmnDatCopyResult {
    uint16_t cursor, source, flags, count_word;
    uint8_t last_byte;
} LmnDatCopyResult;

/* CH is the original remaining-bit counter, not a normalized bit count. */
LmnReverseBitsResult lmn_dat_read_bits_core(const uint8_t *mem,uint16_t ds,
    uint16_t cursor,uint8_t remaining,uint8_t shifted_byte,uint8_t checksum,
    uint8_t count,uint16_t flags);
LmnDatCopyResult lmn_dat_copy_match_core(uint8_t *mem,uint16_t es,
    uint16_t cursor,uint16_t distance,uint16_t count_minus_one,uint16_t flags);
LmnDatCopyResult lmn_dat_write_literal_core(uint8_t *mem,uint16_t es,
    uint16_t cursor,uint8_t value,uint16_t flags);

void lmn_dat_read_bits_adapter(uint8_t *mem,LmnRegs *r);
void lmn_dat_copy_match_adapter(uint8_t *mem,LmnRegs *r);
void lmn_dat_write_literal_adapter(uint8_t *mem,LmnRegs *r);
#endif

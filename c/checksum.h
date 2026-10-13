#ifndef LEMMINGS_CHECKSUM_H
#define LEMMINGS_CHECKSUM_H

#include <stdint.h>
#include "regs.h"

typedef struct LmnChecksumResult {
    uint16_t ax, bx, cx, flags, defined_flags_mask;
} LmnChecksumResult;

/* Core routines operate directly on memory and CS; they do not emulate CALL/RET. */
LmnChecksumResult lmn_initialize_code_checksum_core(uint8_t *mem, uint16_t cs,
                                                     uint16_t initial_ax,
                                                     uint16_t initial_flags);
LmnChecksumResult lmn_advance_code_checksum_core(uint8_t *mem, uint16_t cs,
                                                  uint16_t initial_cx,
                                                  uint16_t initial_flags);

/* Boundary adapters model DS save/restore, temporary CS load, and near RET. */
void lmn_initialize_code_checksum_adapter(uint8_t *mem, LmnRegs *r);
void lmn_advance_code_checksum_adapter(uint8_t *mem, LmnRegs *r);

#endif

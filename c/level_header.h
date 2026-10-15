#ifndef LEMMINGS_LEVEL_HEADER_H
#define LEMMINGS_LEVEL_HEADER_H

#include "special_blit.h"

typedef struct LmnLevelHeaderResult {
    uint16_t value;
    uint16_t header_cursor;
    uint16_t flags;
} LmnLevelHeaderResult;

/* Executes the straight-line header prefix at CS:36B9 through CS:3741.
   Source and destination fields remain in one live 20-bit RAM image. */
LmnLevelHeaderResult lmn_apply_level_header_core(uint8_t *memory,
    uint16_t data_segment, uint16_t flags, const LmnRasterBus *bus);

/* Boundary adapter for entering at CS:36B9. It publishes AX, DI, flags and
   IP=3742, preserving every other register and consuming no stack words. */
void lmn_apply_level_header_adapter(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus);

#endif

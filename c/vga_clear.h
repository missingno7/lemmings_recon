#ifndef LEMMINGS_VGA_CLEAR_H
#define LEMMINGS_VGA_CLEAR_H

#include "special_blit.h"

typedef struct LmnVgaClearResult {
    uint16_t value, count, output_cursor, output_segment, stack_offset, flags, port;
} LmnVgaClearResult;

/* Required bus callbacks own byte reads/writes and word port outputs. */
LmnVgaClearResult lmn_clear_vga_bytes_core(uint8_t *mem, uint16_t stack_segment,
    uint16_t stack_offset, uint16_t output_cursor, uint16_t count, uint16_t flags,
    const LmnRasterBus *bus);
void lmn_clear_vga_bytes_adapter(uint8_t *mem, LmnRegs *regs,
    const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_VGA_MIRRORS_H
#define LEMMINGS_VGA_MIRRORS_H

#include "special_blit.h"

enum LmnVgaMirrorsStatus {
    LMN_VGA_MIRRORS_READY = 0
};

/* The 13 live register and segment roles at both mirror leaves. */
typedef struct LmnVgaMirrorsCall {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnVgaMirrorsCall;

typedef struct LmnVgaMirrorsResult {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status;
} LmnVgaMirrorsResult;

/* Runs through the instruction immediately before RET at 58D1. */
LmnVgaMirrorsResult lmn_restore_vga_register_mirrors_core(
    uint8_t *memory, const LmnVgaMirrorsCall *call, const LmnRasterBus *bus);

/* Applies the core result and consumes the actual live near-RET word. */
uint16_t lmn_restore_vga_register_mirrors_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus);

/* Runs through the instruction immediately before RET at 054D. */
LmnVgaMirrorsResult lmn_initialize_vga_register_mirrors_core(
    uint8_t *memory, const LmnVgaMirrorsCall *call, const LmnRasterBus *bus);

/* Applies the core result and consumes the actual live near-RET word. */
uint16_t lmn_initialize_vga_register_mirrors_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus);

#endif

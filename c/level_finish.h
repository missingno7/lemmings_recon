#ifndef LEMMINGS_LEVEL_FINISH_H
#define LEMMINGS_LEVEL_FINISH_H

#include <stdint.h>
#include "special_blit.h"

typedef struct LmnLevelFinishCall {
    uint16_t code_segment, data_segment, stack_segment, stack_offset;
    uint16_t height_state, source_cursor, flags;
} LmnLevelFinishCall;

typedef struct LmnLevelFinishResult {
    uint16_t value, target_cursor, count, port_or_population;
    uint16_t source_cursor, output_cursor, data_segment, extra_segment;
    uint16_t stack_offset, flags, continuation, changed_return;
} LmnLevelFinishResult;

/* Composes 3776..3788 through the VGA clear and the nominal thirteen-column
   loop; aliases in live SS memory can change its iteration count. The core
   stops before the caller's RET at 3789. A complete raster bus with byte
   read/write and word-port callbacks is required by both child cores. */
LmnLevelFinishResult lmn_finish_level_initialization_core(
    uint8_t *memory, const LmnLevelFinishCall *call,
    const LmnRasterBus *bus);

/* Consumes the live caller RET only after the core reaches its3789 boundary. */
void lmn_finish_level_initialization_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus);

#endif

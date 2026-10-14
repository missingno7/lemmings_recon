#ifndef LEMMINGS_ALIGNED_READ_MASK_H
#define LEMMINGS_ALIGNED_READ_MASK_H
#include "special_blit.h"

/* Mandatory byte-port provider for 969C. Each call observes canonical RAM and
   current flags; a provider may change live stack words. No fixed IN value is
   substituted for hardware. The raster bus retains word-port/MMIO ownership. */
typedef struct LmnRasterBytePorts {
    void *context;
    void (*out_byte)(void *, uint8_t *memory, uint16_t port,
                     uint8_t value, uint16_t flags);
    uint8_t (*in_byte)(void *, uint8_t *memory, uint16_t port, uint16_t flags);
} LmnRasterBytePorts;

typedef struct LmnAlignedReadMaskCall {
    uint16_t initial_data_segment, game_data_segment, stack_segment, stack_offset;
    uint16_t packed_counts, width_state, source_cursor, mask_cursor;
    uint16_t destination_cursor, flags;
} LmnAlignedReadMaskCall;
typedef struct LmnAlignedReadMaskResult {
    uint16_t work_value, packed_counts, port, source_cursor, mask_cursor;
    uint16_t destination_cursor, plane_counter, stack_offset;
    uint16_t source_segment, output_segment, flags;
} LmnAlignedReadMaskResult;

/* 969C through POP DS9735. ports and both of its callbacks must be supplied.
   The live outer return words remain in RAM for the boundary adapter. */
LmnAlignedReadMaskResult lmn_draw_aligned_read_mask_core(
    uint8_t *, const LmnAlignedReadMaskCall *, const LmnRasterBus *,
    const LmnRasterBytePorts *ports);
void lmn_draw_aligned_read_mask_adapter(
    uint8_t *, LmnRegs *, uint16_t game_data_segment, const LmnRasterBus *,
    const LmnRasterBytePorts *ports);
#endif

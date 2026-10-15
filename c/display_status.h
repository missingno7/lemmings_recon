#ifndef LEMMINGS_DISPLAY_STATUS_H
#define LEMMINGS_DISPLAY_STATUS_H
#include "aligned_read_mask.h"

/* Transient register state for 1550..1561. Port callbacks can mutate the
   canonical memory image, but they do not return modified CPU registers. */
typedef struct LmnDisplayStatusState {
    uint16_t value, base_value, count, argument;
    uint16_t source_cursor, output_cursor, frame_cursor;
    uint16_t data_segment, extra_segment, stack_segment, stack_offset, flags;
} LmnDisplayStatusState;

typedef enum LmnDisplayStatusStatus {
    LMN_DISPLAY_STATUS_READY = 0,
    LMN_DISPLAY_STATUS_MISSING_PROVIDER = 1
} LmnDisplayStatusStatus;

typedef struct LmnDisplayStatusResult {
    LmnDisplayStatusState state;
    uint16_t continuation;
    enum LmnDisplayStatusStatus status;
} LmnDisplayStatusResult;

/* Polls the supplied byte-port provider until status bit 3 sets and then
   clears. The original loops are unbounded. A missing IN provider returns at
   the first polling instruction after the original DS word read and ADD. */
LmnDisplayStatusResult lmn_wait_display_status_bit3_cycle_core(
    uint8_t *memory, const LmnDisplayStatusState *input,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

/* Maps all twelve state fields back to registers and consumes the actual near
   RET word, in low/high byte order, only after both polling phases complete. */
void lmn_wait_display_status_bit3_cycle_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus);

#endif

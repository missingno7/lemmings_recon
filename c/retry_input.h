#ifndef LEMMINGS_RETRY_INPUT_H
#define LEMMINGS_RETRY_INPUT_H

#include "special_blit.h"

typedef struct LmnRetryInputResult {
    uint16_t value, flags, continuation;
} LmnRetryInputResult;

_Static_assert(sizeof(LmnRetryInputResult) == 6u,
    "retry-input result must remain three 16-bit fields");

/* Logical boundary for the reset prefix at 4B3B and polling loop 4B40..4B4F.
   The result stops at 4B50 before its CALL: it creates no target CALL/RET
   frame and has no stack effects. Polling remains unbounded, as in the DOS
   code. The memory image is canonical 1 MiB RAM; optional bus callbacks may
   observe each byte access and update that image. The contract assumes intact
   code, unchanged CS, TF clear, quiescent IRQ scheduling, and finite provider-driven
   memory updates; incoming AX is overwritten by the first word read;
   ownership and scheduling of the actual keyboard IRQ remain open. */
LmnRetryInputResult lmn_wait_retry_input_core(uint8_t *memory,
    uint16_t data_segment, uint16_t flags,
    const LmnRasterBus *bus);

/* Executes the 4B3B latch reset before entering the same polling loop. */
LmnRetryInputResult lmn_clear_and_wait_retry_input_core(uint8_t *memory,
    uint16_t data_segment, uint16_t flags,
    const LmnRasterBus *bus);

/* Maps AX and FLAGS, sets IP=4B50, and leaves every other register unchanged. */
void lmn_retry_input_adapter(uint8_t *memory, LmnRegs *registers,
    int clear_scan_code, const LmnRasterBus *bus);

#endif

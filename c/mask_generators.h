#ifndef LEMMINGS_MASK_GENERATORS_H
#define LEMMINGS_MASK_GENERATORS_H
#include "regs.h"
#include "special_blit.h"

/* Entry state for the 5CDD word-mask and 5D66 byte-mask generators. The
   register-shaped fields retain the complete BX/CX/DX values: the routines
   use BL, CX and DH while live PUSH/POP aliases can affect their high bytes. */
typedef struct LmnMaskGeneratorCall {
    uint16_t source_segment, output_segment, stack_segment, stack_offset;
    uint16_t source_cursor, output_cursor, column_repetitions, row_count;
    uint16_t shift_state, flags;
} LmnMaskGeneratorCall;

/* Core boundary is immediately before each generator's RET. shift_state is
   the complete returned DX, including DL and the final live DH value. */
typedef struct LmnMaskGeneratorResult {
    uint16_t value, column_repetitions, row_count, shift_state;
    uint16_t source_cursor, output_cursor, stack_offset, flags;
} LmnMaskGeneratorResult;

LmnMaskGeneratorResult lmn_generate_word_mask_shifts_core(
    uint8_t *memory, const LmnMaskGeneratorCall *call,
    const LmnRasterBus *bus);
LmnMaskGeneratorResult lmn_generate_byte_mask_shifts_core(
    uint8_t *memory, const LmnMaskGeneratorCall *call,
    const LmnRasterBus *bus);
void lmn_generate_word_mask_shifts_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus);
void lmn_generate_byte_mask_shifts_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus);

#endif

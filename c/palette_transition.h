#ifndef LEMMINGS_PALETTE_TRANSITION_H
#define LEMMINGS_PALETTE_TRANSITION_H

#include "palette_ports.h"
#include "palette_rows.h"
#include "display_status.h"

typedef enum LmnPaletteTransitionEntry {
    LMN_PALETTE_TRANSITION_SLOT1 = 0,
    LMN_PALETTE_TRANSITION_SLOT2 = 1
} LmnPaletteTransitionEntry;

typedef enum LmnPaletteTransitionStatus {
    LMN_PALETTE_TRANSITION_READY = 0,
    LMN_PALETTE_TRANSITION_MISSING_INPUT = 1,
    LMN_PALETTE_TRANSITION_MISSING_OUTPUT = 2,
    LMN_PALETTE_TRANSITION_ROW_CHANNEL_STOP = 3,
    LMN_PALETTE_TRANSITION_ROW_CHANGED_RETURN = 4,
    LMN_PALETTE_TRANSITION_CHANGED_RETURN = 5,
    LMN_PALETTE_TRANSITION_MISSING_WORD_OUTPUT = 6,
    LMN_PALETTE_TRANSITION_MISSING_CLEAR_BUS = 7
} LmnPaletteTransitionStatus;

typedef struct LmnPaletteTransitionResult {
    LmnVideoRestoreState state;
    uint16_t code_segment, continuation;
    enum LmnPaletteTransitionStatus status;
} LmnPaletteTransitionResult;

_Static_assert(sizeof(LmnPaletteTransitionResult) == 32u,
    "LmnPaletteTransitionResult must remain a 32-byte boundary result");

/* Composes 531E/536C through the shared 55B7 loop. The core stops before the
   transition's own RET at 5600 or 563D. A child stop returns its live code
   segment and instruction pointer without consuming the child's caller frame.
   Verified providers preserve decoded instructions and CS, with TF clear and
   IRQs quiescent. Canonical data/table/stack mutations remain live. */
LmnPaletteTransitionResult lmn_transition_palette_core(uint8_t *memory,
    uint16_t code_segment, const LmnVideoRestoreState *input,
    enum LmnPaletteTransitionEntry entry, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus);

/* Maps all twelve fields and consumes the actual outer near RET only when the
   composed transition reaches its own RET boundary. */
void lmn_transition_palette_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnPaletteTransitionEntry entry, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus);

typedef enum LmnSplitPaletteStepEntry {
    LMN_SPLIT_PALETTE_TO_SLOT1, LMN_SPLIT_PALETTE_TO_TARGETS
} LmnSplitPaletteStepEntry;
/* 5329/534B use actual saved words and two native5569 row calls. */
LmnPaletteTransitionResult lmn_step_split_palette_core(uint8_t *memory,uint16_t cs,
    const LmnVideoRestoreState *input,LmnSplitPaletteStepEntry entry,const LmnRasterBus *bus);
LmnPaletteTransitionResult lmn_step_split_palette_adapter(uint8_t *memory,LmnRegs *registers,
    LmnSplitPaletteStepEntry entry,const LmnRasterBus *bus);
/* 46B9 status-bit/raster palette sequence; 46A2 repeats it with upper-half
   publication and native row steps, then tail-enters the native page clear. */
LmnPaletteTransitionResult lmn_refresh_split_palette_core(uint8_t *memory,uint16_t cs,
    const LmnVideoRestoreState *input,const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
LmnPaletteTransitionResult lmn_fade_split_palette_core(uint8_t *memory,uint16_t cs,
    const LmnVideoRestoreState *input,const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
LmnPaletteTransitionResult lmn_refresh_split_palette_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
LmnPaletteTransitionResult lmn_fade_split_palette_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
#endif

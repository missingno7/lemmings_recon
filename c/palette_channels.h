#ifndef LEMMINGS_PALETTE_CHANNELS_H
#define LEMMINGS_PALETTE_CHANNELS_H

#include "video_restore.h"

typedef enum LmnPaletteChannelEntry {
    LMN_PALETTE_CHANNEL_HIGH = 0,
    LMN_PALETTE_CHANNEL_MIDDLE = 1,
    LMN_PALETTE_CHANNEL_LOW = 2,
    LMN_PALETTE_CHANNEL_PACKED = 3,
    LMN_PALETTE_CHANNEL_RGB = 4
} LmnPaletteChannelEntry;

typedef enum LmnPaletteChannelStatus {
    LMN_PALETTE_CHANNEL_READY = 0,
    LMN_PALETTE_CHANNEL_CHANGED_RETURN = 1
} LmnPaletteChannelStatus;

typedef struct LmnPaletteChannelResult {
    LmnVideoRestoreState state;
    uint16_t code_segment, continuation;
    enum LmnPaletteChannelStatus status;
} LmnPaletteChannelResult;

_Static_assert(sizeof(LmnPaletteChannelResult) == 32u,
    "LmnPaletteChannelResult must remain a 32-byte boundary result");

/* Steps one channel using the original byte instructions and flag effects.
   Wrapper entries perform their real stack CALL/RET accesses through bus. */
LmnPaletteChannelResult lmn_step_palette_channel_core(uint8_t *memory,
    uint16_t code_segment, const LmnVideoRestoreState *input,
    enum LmnPaletteChannelEntry entry, const LmnRasterBus *bus);

/* Maps the twelve transient fields to registers and consumes the actual
   outer near RET only when the core reaches its declared return site. */
void lmn_step_palette_channel_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnPaletteChannelEntry entry, const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_BACKGROUND_DRAWING_H
#define LEMMINGS_BACKGROUND_DRAWING_H

#include "drawing_render.h"
#include "video_restore.h"

typedef LmnVideoRestoreState LmnBackgroundDrawingState;

typedef enum LmnBackgroundDrawingEntry {
    LMN_BACKGROUND_DRAWING_FULL = 0,
    LMN_BACKGROUND_DRAWING_FROM_ROW = 1,
    LMN_BACKGROUND_DRAWING_TILES = 2
} LmnBackgroundDrawingEntry;

typedef enum LmnBackgroundDrawingStatus {
    LMN_BACKGROUND_DRAWING_READY = 0,
    LMN_BACKGROUND_DRAWING_RENDERER_STOP = 1,
    LMN_BACKGROUND_DRAWING_CHANGED_RETURN = 2
} LmnBackgroundDrawingStatus;

typedef struct LmnBackgroundDrawingResult {
    LmnBackgroundDrawingState state;
    uint16_t code_segment, continuation;
    enum LmnBackgroundDrawingStatus status;
} LmnBackgroundDrawingResult;

_Static_assert(sizeof(LmnBackgroundDrawingResult) == 32u,
    "LmnBackgroundDrawingResult must remain a 32-byte boundary result");

/* Models the 5017/5019 bridge and the shared 7E76..7EB1 tile loop. The core
   stops before the outer RET; child calls require intact relocated operands
   targeting code_segment:8822 and use live SS return/save words. */
LmnBackgroundDrawingResult lmn_draw_background_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnBackgroundDrawingState *input,
    enum LmnBackgroundDrawingEntry entry, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports);

/* Maps every logical field and consumes the outer near RET only when READY. */
void lmn_draw_background_adapter(uint8_t *memory, LmnRegs *registers,
    uint16_t game_data_segment, enum LmnBackgroundDrawingEntry entry,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports);

#endif

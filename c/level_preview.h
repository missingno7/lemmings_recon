#ifndef LEMMINGS_LEVEL_PREVIEW_H
#define LEMMINGS_LEVEL_PREVIEW_H

#include "video_restore.h"

typedef LmnVideoRestoreState LmnLevelPreviewState;
typedef enum LmnLevelPreviewStatus {
    LMN_LEVEL_PREVIEW_READY = 0,
    LMN_LEVEL_PREVIEW_MISSING_WORD_OUTPUT = 1
} LmnLevelPreviewStatus;

typedef struct LmnLevelPreviewResult {
    LmnLevelPreviewState state;
    uint16_t code_segment, continuation;
    LmnLevelPreviewStatus status;
} LmnLevelPreviewResult;
_Static_assert(sizeof(LmnLevelPreviewResult)==32u,"preview boundary size");

/* 7EB2..80FC. Reads live drawing coordinates, samples bits5/1 from four
   source bytes per plane and ORs them through the destination VGA latches.
   All saves/counts/cursors use canonical SS memory. Stops before outer RET;
   absent word output stops before the actual OUT after its SS mirror write. */
LmnLevelPreviewResult lmn_draw_level_preview_core(uint8_t *memory,
    uint16_t code_segment,const LmnLevelPreviewState *input,const LmnRasterBus *bus);
LmnLevelPreviewResult lmn_draw_level_preview_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

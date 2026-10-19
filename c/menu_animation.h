#ifndef LEMMINGS_MENU_ANIMATION_H
#define LEMMINGS_MENU_ANIMATION_H
#include "drawing_render.h"
#include "video_restore.h"

typedef enum LmnMenuAnimationEntry {
    LMN_MENU_ANIMATION_INITIALIZE = 0, /* 4FF8 */
    LMN_MENU_ANIMATION_TICK = 1        /* 4F96 */
} LmnMenuAnimationEntry;
typedef enum LmnMenuAnimationStatus {
    LMN_MENU_ANIMATION_READY = 0,
    LMN_MENU_ANIMATION_RENDERER_STOP = 1,
    LMN_MENU_ANIMATION_CHANGED_RETURN = 2
} LmnMenuAnimationStatus;
typedef struct LmnMenuAnimationResult {
    LmnVideoRestoreState state;
    uint16_t code_segment, continuation;
    enum LmnMenuAnimationStatus status;
} LmnMenuAnimationResult;

/* Canonical ten-record initializer and countdown/bitmap parent. Intact relocated
   4FEB far CALL targets code_segment:8822. Actual saved SI/CX, far-return words,
   live DS/ES/SS and flags remain observable. READY stops before the entry's own
   RET; no executable image or data record is copied to a shadow representation. */
LmnMenuAnimationResult lmn_menu_animation_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnVideoRestoreState *input, enum LmnMenuAnimationEntry entry,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports);

/* Applies all returned fields; consumes the outer near RET only when READY. */
LmnMenuAnimationResult lmn_menu_animation_adapter(uint8_t *memory, const LmnRegs *registers,
    uint16_t game_data_segment, enum LmnMenuAnimationEntry entry,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports);
#endif

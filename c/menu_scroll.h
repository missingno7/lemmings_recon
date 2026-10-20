#ifndef LEMMINGS_MENU_SCROLL_H
#define LEMMINGS_MENU_SCROLL_H
#include "drawing_render.h"
#include "video_restore.h"

typedef enum LmnMenuScrollEntry {
    LMN_MENU_SCROLL_INITIALIZE, LMN_MENU_SCROLL_DRAW, LMN_MENU_SCROLL_TICK,
    LMN_MENU_SCROLL_TILE, LMN_MENU_SCROLL_GLYPH, LMN_MENU_SCROLL_EDGE
} LmnMenuScrollEntry;
typedef enum LmnMenuScrollStatus {
    LMN_MENU_SCROLL_READY, LMN_MENU_SCROLL_RENDERER_STOP,
    LMN_MENU_SCROLL_CHANGED_RETURN
} LmnMenuScrollStatus;
typedef struct LmnMenuScrollResult {
    LmnVideoRestoreState state;
    uint16_t code_segment, continuation;
    enum LmnMenuScrollStatus status;
} LmnMenuScrollResult;
_Static_assert(sizeof(LmnMenuScrollResult)==32u,"32-byte scroll boundary");

/* Six connected original entries, one canonical RAM image. READY stops before
   the entry's actual RET (including shared edge tail); adapter consumes it.
   Intact relocated far operands target same-CS:8822. Live DS/ES/SS, saved
   words, DF, flags and changed near/far continuations remain observable. */
LmnMenuScrollResult lmn_menu_scroll_core(uint8_t *memory,uint16_t code_segment,
    uint16_t game_data_segment,const LmnVideoRestoreState *input,
    enum LmnMenuScrollEntry entry,const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports);
LmnMenuScrollResult lmn_menu_scroll_adapter(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_data_segment,enum LmnMenuScrollEntry entry,
    const LmnRasterBus *bus,const LmnRasterBytePorts *ports);
#endif

#ifndef LEMMINGS_MENU_CACHE_H
#define LEMMINGS_MENU_CACHE_H
#include "drawing_render.h"
#include "video_restore.h"

typedef enum LmnMenuCacheEntry {
    LMN_MENU_CACHE_SOUND = 0,       /* 4E37 */
    LMN_MENU_CACHE_LEVEL_GROUP = 1  /* 4EA2 */
} LmnMenuCacheEntry;
typedef enum LmnMenuCacheStatus {
    LMN_MENU_CACHE_READY = 0,
    LMN_MENU_CACHE_RENDERER_STOP = 1,
    LMN_MENU_CACHE_CHANGED_RETURN = 2
} LmnMenuCacheStatus;
typedef struct LmnMenuCacheResult {
    LmnVideoRestoreState state;
    uint16_t code_segment, continuation;
    enum LmnMenuCacheStatus status;
} LmnMenuCacheResult;
_Static_assert(sizeof(LmnMenuCacheResult)==32u,
    "LmnMenuCacheResult must remain a 32-byte native boundary result");

/* Live byte caches with markers2/4, not shadow page state. Actual near/far
   frames and returned DS/ES/SS/flags remain observable. Intact relocated calls
   4E7E/4E9C/4EE1 target same-CS:8822; game_data_segment owns its relocated scratch.
   READY stops before the actual entry's own RET, including the no-draw path. */
LmnMenuCacheResult lmn_menu_cache_core(uint8_t *memory,uint16_t code_segment,
    uint16_t game_data_segment,const LmnVideoRestoreState *input,
    enum LmnMenuCacheEntry entry,const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports);
LmnMenuCacheResult lmn_menu_cache_adapter(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_data_segment,enum LmnMenuCacheEntry entry,
    const LmnRasterBus *bus,const LmnRasterBytePorts *ports);
#endif

#ifndef LEMMINGS_GAME_PREPARE_H
#define LEMMINGS_GAME_PREPARE_H
#include "palette_ports.h"
typedef enum LmnGamePrepareEntry {
    LMN_GAME_PREPARE_BASE_PALETTE,LMN_GAME_PREPARE_FADE_PALETTE,
    LMN_GAME_PREPARE_SOUND,LMN_GAME_PREPARE_STATUS_BACKDROP,
    LMN_GAME_PREPARE_DIRTY_ROWS,LMN_GAME_PREPARE_DRAWING_PAGES
} LmnGamePrepareEntry;
typedef enum LmnGamePrepareStatus {
    LMN_GAME_PREPARE_READY,LMN_GAME_PREPARE_CHILD_STOP,
    LMN_GAME_PREPARE_CHANGED_RETURN,LMN_GAME_PREPARE_MISSING_WORD_OUTPUT
} LmnGamePrepareStatus;
typedef struct LmnGamePrepareResult {
    LmnRegs registers;uint16_t status,child_status;
} LmnGamePrepareResult;
_Static_assert(sizeof(LmnGamePrepareResult)==32u,"32-byte preparation result");
/* Six identified setup entries on canonical memory. Logical cores leave the
   active outer RET pending, including inherited palette tails. Actual child
   frames, repeated scans/copies and returned DS/ES/SS remain live. */
LmnGamePrepareResult lmn_game_prepare_core(uint8_t *,const LmnRegs *,LmnGamePrepareEntry,
    const LmnRasterBytePorts *,const LmnRasterBus *);
LmnGamePrepareResult lmn_game_prepare_adapter(uint8_t *,const LmnRegs *,LmnGamePrepareEntry,
    const LmnRasterBytePorts *,const LmnRasterBus *);
#endif

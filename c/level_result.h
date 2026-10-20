#ifndef LEMMINGS_LEVEL_RESULT_H
#define LEMMINGS_LEVEL_RESULT_H
#include "foreground_poll.h"
#include "display_setup.h"
#include "palette_ports.h"

typedef struct LmnLevelResultServices {
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    const LmnVideoRestoreServices *video;
    const LmnForegroundPoll *poll;
    uint16_t game_data_segment;
} LmnLevelResultServices;

enum LmnLevelResultStatus {
    LMN_LEVEL_RESULT_READY, LMN_LEVEL_RESULT_MAIN_MENU,
    LMN_LEVEL_RESULT_START_LEVEL, LMN_LEVEL_RESULT_WAITING,
    LMN_LEVEL_RESULT_POLL_STOP, LMN_LEVEL_RESULT_CHILD_STOP,
    LMN_LEVEL_RESULT_CHANGED_RETURN, LMN_LEVEL_RESULT_DIVIDE_ERROR,
    LMN_LEVEL_RESULT_INVALID_ENTRY
};
typedef struct LmnLevelResultResult {
    LmnRegs registers;
    uint16_t status,child_entry,child_status,service_status;
} LmnLevelResultResult;

/* 46EB has no outer RET: stop after JMP4401/4551, before either destination.
   Helpers48BD/48F6 tail into the existing text child; core leaves its RET
   pending, adapter consumes the actual inherited word. WAITING/POLL_STOP
   may resume at the returned poll IP (47A9/47B1/47BE/480A/4812).
   Polls precede each IRQ-owned button/key read, with full live CPU state.
   NULL polling runs any immediately satisfiable predicates, then WAITING
   stops at the first back edge requiring an external change. Child provider,
   alias and platform domains remain those of the composed implementations. */
LmnLevelResultResult lmn_level_result_core(uint8_t *,const LmnRegs *,const LmnLevelResultServices *);
LmnLevelResultResult lmn_level_result_adapter(uint8_t *,const LmnRegs *,const LmnLevelResultServices *);
#endif

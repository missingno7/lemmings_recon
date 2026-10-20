#ifndef LEMMINGS_GAME_LOOP_H
#define LEMMINGS_GAME_LOOP_H
#include "main_menu.h"
#include "level_start.h"
#include "game_session.h"
#include "level_result.h"

/* Read-only observation before each dispatched core, including initial entry.
   No state copy, synthetic CALL/RET, IRQ delivery or cancellation here. */
typedef void (*LmnGameLoopObserveFn)(void *,const uint8_t *,const LmnRegs *);
typedef struct LmnGameLoopServices {
    const LmnVideoRestoreServices *video;
    const LmnInterruptService *dos;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    const LmnForegroundPoll *poll;
    const LmnLevelStartServices *start;
    const LmnGameSessionServices *session;
    const LmnLevelResultServices *result;
    void *observer_context;
    LmnGameLoopObserveFn observe;
    uint16_t game_data_segment,code_segment;
} LmnGameLoopServices;
enum LmnGameLoopStatus {
    LMN_GAME_LOOP_CORE_STOP, LMN_GAME_LOOP_FATAL_CLEANUP,
    LMN_GAME_LOOP_RESOURCE_RETRY, LMN_GAME_LOOP_DOS_EXIT,
    LMN_GAME_LOOP_UNSUPPORTED_TRANSFER, LMN_GAME_LOOP_UNBOUND_SERVICE
};
typedef struct LmnGameLoopResult {
    LmnRegs registers;
    uint16_t status,core_entry,core_status,child_status,service_status;
} LmnGameLoopResult;

/* CONDITIONAL READY: actual JMP dispatch in the existing child/provider and
   IRQ-at-poll domains. Entry43F2 or4401; destination cores also accepted for
   explicit platform handoffs. No outer RET and no internal step/frame cap.
   Every stop retains live registers/RAM/stack. Poll cancellation is a core
   stop, not a resumable coroutine for cores with pending internal CALLs.
   DAT retry callbacks run the native 4B1C screen on live RAM/registers and
   resume the saved-register re-probe/reload tails on an intact near RET.
   The void callback still needs setjmp/longjmp for unbound UI services,
   child/poll stops or changed returns; stopped packets retain the exact site.
   A raw 4B1C driver entry has no suspended DAT parent and remains an explicit
   RESOURCE_RETRY stop. No retry count or synthetic successful probe is added.
   See build/worker-retryroute-report.md for the caller contract proposal and
   build/worker-loop-report.md for the underlying loop annotation;
   this batch is deliberately forbidden from editing either source. */
LmnGameLoopResult lmn_game_loop_core(uint8_t *,const LmnRegs *,const LmnGameLoopServices *);
#endif

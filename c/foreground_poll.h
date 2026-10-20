#ifndef LEMMINGS_FOREGROUND_POLL_H
#define LEMMINGS_FOREGROUND_POLL_H
#include "regs.h"

/* Platform seam for foreground loops that read bytes owned by the INT08 tail
   (TimerChainFlag1FCF, TimerForegroundCounter1FCD): 0179/01DF in the frame and
   04AA/04BA in session initialization. The menu/briefing/result polled APIs
   also expose button/key reads (sites are listed in their public contracts).
   `poll` runs immediately before the
   original instruction at `site` reads that byte; registers hold the complete
   live state with IP=site. A native platform delivers any pending hardware
   INT08 there (only when FLAGS.IF is set), e.g. by pushing the real FLAGS/CS/IP
   frame and running the native timer handler; a verifier mirrors the same
   delivery on the original side. Zero continues; nonzero stops the caller at
   `site` with that status, which bounded fixtures use instead of a timeout.
   This is the only place asynchronous timer effects enter these loops. */
typedef uint16_t (*LmnForegroundPollFn)(void *context, uint8_t *memory,
    LmnRegs *registers, uint16_t site);

typedef struct LmnForegroundPoll {
    void *context;
    LmnForegroundPollFn poll;
} LmnForegroundPoll;

#endif

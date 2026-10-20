#ifndef LEMMINGS_RESOURCE_RETRY_H
#define LEMMINGS_RESOURCE_RETRY_H

#include "background_drawing.h"
#include "display_pages.h"
#include "display_setup.h"
#include "display_start.h"
#include "display_status.h"
#include "palette_transition.h"
#include "text_stream.h"
#include "foreground_poll.h"

typedef enum LmnResourceRetryStatus {
    LMN_RESOURCE_RETRY_READY = 0,
    LMN_RESOURCE_RETRY_CHILD_STOP = 1,
    LMN_RESOURCE_RETRY_CHANGED_RETURN = 2,
    LMN_RESOURCE_RETRY_WAITING = 3,
    LMN_RESOURCE_RETRY_POLL_STOP = 4
} LmnResourceRetryStatus;

typedef struct LmnResourceRetryResult {
    LmnVideoRestoreState state;
    uint16_t code_segment;
    uint16_t continuation;
    enum LmnResourceRetryStatus status;
    uint16_t child_entry;
    uint16_t child_status;
} LmnResourceRetryResult;

typedef struct LmnResourceRetryInputResult {
    uint16_t value, flags, continuation, status, service_status;
} LmnResourceRetryInputResult;

_Static_assert(sizeof(LmnResourceRetryResult) == 36u,
    "retry-UI result must remain a 36-byte boundary result");

/* Frame-free 4B3B..4B4F prefix for the focused input-site oracle. */
LmnResourceRetryInputResult lmn_resource_retry_input_core(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus,
    const LmnForegroundPoll *poll);

/* Composes the 4B1C resource-retry screen from maintained native children.
   Each near CALL uses its actual live SS:SP return word. A non-ready child
   preserves that frame and returns its entry, status, continuation, and all
   twelve live state fields. READY stops before the caller RET at 4B5B.

   game_data_segment is only the graphics/text renderer dependency; DS remains
   the live segment carried by state. The frame-free retry-input core is
   bounded only by finite constructed input updates. Polling runs before each
   IRQ-owned input read at 4B40 and 4B48; NULL polling stops at 4B40 as WAITING.
   Bus callbacks may own
   memory/VGA effects; missing child-required providers retain the child stop.
   The domain assumes intact decoded code and relocated far operands, a common
   CS, TF clear, quiescent IRQ scheduling, and finite constructed byte/memory
   providers. Native hardware timing and installed-handler/IRQ ownership
   remain seams. */
LmnResourceRetryResult lmn_resource_retry_screen_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnVideoRestoreState *input,
    const LmnVideoRestoreServices *services,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports,
    const LmnForegroundPoll *poll);

/* Maps all twelve fields and consumes the actual outer near RET only on READY. */
void lmn_resource_retry_screen_adapter(uint8_t *memory,
    LmnRegs *registers, uint16_t game_data_segment,
    const LmnVideoRestoreServices *services,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports,
    const LmnForegroundPoll *poll);

#endif

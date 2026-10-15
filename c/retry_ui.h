#ifndef LEMMINGS_RETRY_UI_H
#define LEMMINGS_RETRY_UI_H

#include "background_drawing.h"
#include "display_pages.h"
#include "display_setup.h"
#include "display_start.h"
#include "display_status.h"
#include "palette_transition.h"
#include "retry_input.h"
#include "text_stream.h"

typedef enum LmnRetryUiStatus {
    LMN_RETRY_UI_READY = 0,
    LMN_RETRY_UI_CHILD_STOP = 1,
    LMN_RETRY_UI_CHANGED_RETURN = 2
} LmnRetryUiStatus;

typedef struct LmnRetryUiResult {
    LmnVideoRestoreState state;
    uint16_t code_segment;
    uint16_t continuation;
    enum LmnRetryUiStatus status;
    uint16_t child_entry;
    uint16_t child_status;
} LmnRetryUiResult;

_Static_assert(sizeof(LmnRetryUiResult) == 36u,
    "retry-UI result must remain a 36-byte boundary result");

/* UNVERIFIED composition; see docs/retry-ui.md. No caller C coverage claimed.
   Composes the 4B1C resource-retry screen from the maintained native children.
   Each near CALL uses its actual live SS:SP return word. A non-ready child
   preserves that frame and returns its entry, status, continuation, and all
   twelve live state fields. READY stops before the caller RET at 4B5B.

   game_data_segment is only the graphics/text renderer dependency; DS remains
   the live segment carried by state. The frame-free retry-input core is
   bounded only by finite constructed input updates. Bus callbacks may own
   memory/VGA effects; missing child-required providers retain the child stop.
   The domain assumes intact decoded code and relocated far operands, a common
   CS, TF clear, quiescent IRQ scheduling, and finite constructed byte/memory
   providers. Native hardware timing and installed-handler/IRQ ownership
   remain seams. */
LmnRetryUiResult lmn_show_resource_retry_screen_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnVideoRestoreState *input,
    const LmnVideoRestoreServices *services,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports);

/* Maps all twelve fields and consumes the actual outer near RET only on READY. */
void lmn_show_resource_retry_screen_adapter(uint8_t *memory,
    LmnRegs *registers, uint16_t game_data_segment,
    const LmnVideoRestoreServices *services,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports);

#endif

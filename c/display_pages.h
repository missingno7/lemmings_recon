#ifndef LEMMINGS_DISPLAY_PAGES_H
#define LEMMINGS_DISPLAY_PAGES_H

#include "video_restore.h"
#include "vga_clear.h"

/* Transient CPU state used by display-page routines. */
typedef LmnVideoRestoreState LmnDisplayPagesState;

typedef enum LmnDisplayPagesStatus {
    LMN_DISPLAY_PAGES_READY = 0,
    LMN_DISPLAY_PAGES_MISSING_PORT = 1,
    LMN_DISPLAY_PAGES_MISSING_CLEAR_BUS = 2
} LmnDisplayPagesStatus;

typedef struct LmnDisplayPagesResult {
    LmnDisplayPagesState state;
    uint16_t continuation;
    enum LmnDisplayPagesStatus status;
} LmnDisplayPagesResult;

/* Runs 4DC2 through the live POP DS, stopping before its near RET. RAM and
   CPU word accesses use the optional bus callbacks when present and otherwise
   use canonical memory. Each word OUT is required and is checked at its own
   original instruction after that site's SS mirror store. */
LmnDisplayPagesResult lmn_copy_drawing_page_core(uint8_t *memory,
    const LmnDisplayPagesState *input, const LmnRasterBus *bus);

/* Runs 4DEF into the shared 4DF8 clear tail, stopping before the RET at 4E36.
   The clear tail requires read, write, and word-OUT callbacks; when one is
   absent, this returns at 4DF8 after only the wrapper's DI/CX loads. */
LmnDisplayPagesResult lmn_clear_full_drawing_page_core(uint8_t *memory,
    const LmnDisplayPagesState *input, const LmnRasterBus *bus);

/* Apply the logical result and consume the actual near RET only on READY. */
void lmn_copy_drawing_page_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus);
void lmn_clear_full_drawing_page_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

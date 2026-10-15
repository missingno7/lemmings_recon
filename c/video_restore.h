#ifndef LEMMINGS_VIDEO_RESTORE_H
#define LEMMINGS_VIDEO_RESTORE_H
#include "special_blit.h"

/* Transient BIOS boundary state. These are returned registers, not a copy of
   persistent game state; services may also mutate canonical memory directly. */
typedef struct LmnVideoRestoreState {
    uint16_t value, base_value, count, argument;
    uint16_t source_cursor, output_cursor, frame_cursor;
    uint16_t data_segment, extra_segment, stack_segment, stack_offset, flags;
} LmnVideoRestoreState;

typedef struct LmnVideoRestoreServices {
    void *context;
    /* These callbacks model the INT 10h seams, not BIOS hardware. They receive
       all twelve fields at INT entry and return them at the next instruction
       in the same CS; CS is caller-owned. They may mutate canonical memory. */
    void (*set_mode)(void *, uint8_t *memory,
        const LmnVideoRestoreState *input, LmnVideoRestoreState *out);
    void (*set_active_page)(void *, uint8_t *memory,
        const LmnVideoRestoreState *input, LmnVideoRestoreState *out);
} LmnVideoRestoreServices;

typedef enum LmnVideoRestoreStatus {
    LMN_VIDEO_RESTORE_READY = 0,
    LMN_VIDEO_RESTORE_MISSING_MODE = 1,
    LMN_VIDEO_RESTORE_MISSING_PAGE = 2
} LmnVideoRestoreStatus;

typedef struct LmnVideoRestoreResult {
    LmnVideoRestoreState state;
    uint16_t continuation;
    enum LmnVideoRestoreStatus status;
} LmnVideoRestoreResult;

/* Calls the two optional INT 10h services in sequence. Memory reads use the
   canonical 20-bit bus; no stack frame or persistent game-state copy is made. */
LmnVideoRestoreResult lmn_restore_video_mode_page_core(uint8_t *memory,
    const LmnVideoRestoreState *input, const LmnVideoRestoreServices *services,
    const LmnRasterBus *bus);

/* Maps the twelve returned logical fields to registers and consumes the live
   near RET only for a ready result. CS is preserved across each BIOS seam. */
void lmn_restore_video_mode_page_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnVideoRestoreServices *services, const LmnRasterBus *bus);

#endif

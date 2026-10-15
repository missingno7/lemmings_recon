#ifndef LEMMINGS_LEVEL_REDRAW_H
#define LEMMINGS_LEVEL_REDRAW_H

#include "aligned_read_mask.h"
#include "drawing_source.h"
#include "regs.h"
#include "special_setup.h"

typedef struct LmnLevelRedrawCall {
    /* Logical general-register state at entry to394F. The initializer replaces
       AX/CX/DX/DI on its normal path; BX is supplied to368E, while SI/BP flow
       through the callees that preserve them. */
    LmnDrawingSourceResult state;
    uint16_t data_segment, output_segment, code_segment, stack_segment;
    uint16_t game_data_segment;
} LmnLevelRedrawCall;

typedef struct LmnLevelRedrawServices {
    /* Required only when DS:0FE8 selects the special-resource branch. */
    const LmnDatLoadSegments *dat_segments;
    /* Its DOS callbacks are used; its raster slot is replaced locally with
       the parent's canonical bus below and may be NULL. */
    const LmnSpecialSetupServices *special;
    /* The clear and drawing children require a complete raster bus. */
    const LmnRasterBus *raster;
    /* Optional. An absent or incomplete provider stops at969C if selected. */
    const LmnRasterBytePorts *ports;
} LmnLevelRedrawServices;

typedef enum LmnLevelRedrawStatus {
    LMN_LEVEL_REDRAW_READY_TO_RETURN = 0,
    LMN_LEVEL_REDRAW_MISSING_SERVICES = 1,
    LMN_LEVEL_REDRAW_MISSING_PROVIDER = 2,
    LMN_LEVEL_REDRAW_UNPORTED_CONTINUATION = 3,
    LMN_LEVEL_REDRAW_FATAL_FILE = 4,
    LMN_LEVEL_REDRAW_FATAL_DECODE = 5,
    LMN_LEVEL_REDRAW_CHANGED_RETURN = 6
} LmnLevelRedrawStatus;

typedef struct LmnLevelRedrawResult {
    LmnDrawingSourceResult state;
    uint16_t data_segment, output_segment, code_segment;
    LmnLevelRedrawStatus status;
    /* Mirrors LmnDatFileResult.fatal (1=file transfer,2=decoder transfer). */
    uint16_t fatal;
    uint16_t missing_services, missing_provider, unported;
    uint16_t changed_return, ready_to_return;
} LmnLevelRedrawResult;

/* Composes394F through the object suffix's39CD RET boundary on canonical
   memory. Required services and changed/fatal/unported exits remain explicit.
   A ready result leaves the parent's own live RET word unconsumed. This
   composition inherits each child's documented RAM, intact-code, active-RET,
   provider, VGA, and IRQ boundaries; it does not widen them. In particular,
   the special path keeps special_setup's ordinary-RAM input/heap/stack and
   narrow DOS-provider preconditions. */
LmnLevelRedrawResult lmn_redraw_level_core(
    uint8_t *memory, const LmnLevelRedrawCall *call,
    const LmnLevelRedrawServices *services);

/* Boundary adapter for the outer near RET. It consumes the actual SS word
   only when the core reaches its own39CD return boundary. */
void lmn_redraw_level_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment,
    const LmnLevelRedrawServices *services);

#endif

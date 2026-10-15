#ifndef LEMMINGS_LEVEL_INITIALIZE_H
#define LEMMINGS_LEVEL_INITIALIZE_H

#include "aligned_read_mask.h"
#include "drawing_source.h"
#include "special_setup.h"

typedef struct LmnLevelInitializeCall {
    /* Logical AX/BX/CX/DX/SI/DI/BP/SP and flags at CS:36B6. */
    LmnDrawingSourceResult state;
    uint16_t data_segment, output_segment, code_segment, stack_segment;
    uint16_t game_data_segment;
} LmnLevelInitializeCall;

typedef struct LmnLevelInitializeServices {
    const LmnDatLoadSegments *dat_segments;
    const LmnSpecialSetupServices *special;
    const LmnRasterBus *raster;
    const LmnRasterBytePorts *ports;
} LmnLevelInitializeServices;

typedef enum LmnLevelInitializeStatus {
    LMN_LEVEL_INITIALIZE_READY_TO_RETURN = 0,
    LMN_LEVEL_INITIALIZE_MISSING_SERVICES = 1,
    LMN_LEVEL_INITIALIZE_MISSING_PROVIDER = 2,
    LMN_LEVEL_INITIALIZE_UNPORTED_CONTINUATION = 3,
    LMN_LEVEL_INITIALIZE_FATAL_FILE = 4,
    LMN_LEVEL_INITIALIZE_FATAL_DECODE = 5,
    LMN_LEVEL_INITIALIZE_CHANGED_RETURN = 6
} LmnLevelInitializeStatus;

typedef struct LmnLevelInitializeResult {
    LmnDrawingSourceResult state;
    uint16_t data_segment, output_segment, code_segment;
    LmnLevelInitializeStatus status;
    uint16_t fatal;
    uint16_t missing_services, missing_provider, unported;
    uint16_t changed_return, ready_to_return;
} LmnLevelInitializeResult;

/* Composes the initialized caller span 36B6..3789 through the live RET
   boundary. Child provider, fatal, and changed-return exits remain explicit;
   the ordinary-memory and DOS assumptions of the special-resource child are
   inherited from that child. A ready result leaves the outer SS:SP RET live. */
LmnLevelInitializeResult lmn_initialize_level_core(
    uint8_t *memory, const LmnLevelInitializeCall *call,
    const LmnLevelInitializeServices *services);

/* Consumes the caller's actual outer near RET only on a ready result. */
void lmn_initialize_level_adapter(
    uint8_t *memory, LmnRegs *registers, uint16_t game_data_segment,
    const LmnLevelInitializeServices *services);

#endif

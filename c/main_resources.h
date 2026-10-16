#ifndef LEMMINGS_MAIN_RESOURCES_H
#define LEMMINGS_MAIN_RESOURCES_H

#include "dat_load.h"
#include "special_blit.h"

enum LmnMainResourceSectionsStatus {
    LMN_MAIN_RESOURCE_SECTIONS_READY = 0,
    LMN_MAIN_RESOURCE_SECTIONS_CHILD_STOP = 1,
    LMN_MAIN_RESOURCE_SECTIONS_CHANGED_CHILD_RETURN = 2,
    LMN_MAIN_RESOURCE_SECTIONS_FATAL = 3
};

/* Live roles at LoadMainResourceSections (58D2). */
typedef struct LmnMainResourceSectionsCall {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnMainResourceSectionsCall;

typedef struct LmnMainResourceSectionsResult {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status, child_entry, child_status;
} LmnMainResourceSectionsResult;

/* Executes 58D2..59B9, stopping before the caller RET at 59BA. The DAT
   service callbacks model DOS boundaries; raster callbacks observe parent
   RAM/stack/string traffic and the composed graphics children. */
LmnMainResourceSectionsResult lmn_load_main_resource_sections_core(
    uint8_t *memory, const LmnMainResourceSectionsCall *call,
    const LmnDatFileServices *files, const LmnDatIo *io,
    const LmnRasterBus *raster);

/* Maps LmnRegs to the core and consumes the actual outer RET only on READY. */
uint16_t lmn_load_main_resource_sections_adapter(
    uint8_t *memory, LmnRegs *registers,
    const LmnDatFileServices *files, const LmnDatIo *io,
    const LmnRasterBus *raster);

#endif

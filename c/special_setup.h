#ifndef LEMMINGS_SPECIAL_SETUP_H
#define LEMMINGS_SPECIAL_SETUP_H
#include "dat_load.h"
#include "special_blit.h"

typedef struct LmnSpecialSetupServices {
    const LmnDatFileServices *files;
    const LmnDatIo *io;
    const LmnRasterBus *raster;
    void *context;
    /* DOS AH3E preserves registers other than AX; supplied flags remain explicit.
       value includes the original partial AH write. The caller ignores carry. */
    void (*close)(void *,uint8_t *,uint16_t handle,uint16_t value,uint16_t flags,LmnDatDosResult *);
} LmnSpecialSetupServices;

LmnDatFileResult lmn_setup_special_graphics_core(uint8_t *,const LmnDatFileCall *,
    const LmnDatLoadSegments *,const LmnSpecialSetupServices *);
void lmn_setup_special_graphics_adapter(uint8_t *,LmnRegs *,const LmnSpecialSetupServices *);
#endif

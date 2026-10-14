#ifndef LEMMINGS_RESOURCE_SELECT_H
#define LEMMINGS_RESOURCE_SELECT_H
#include "dat_load.h"
#include "resource_raw.h"

typedef struct LmnResourceSelectionCall {
    uint16_t main_data_segment,stack_segment,stack_offset,flags,base_cursor;
} LmnResourceSelectionCall;
typedef struct LmnResourceSelectionServices {
    const LmnDatFileServices *files;
    const LmnDatIo *io;
    const LmnRawResourceServices *raw;
} LmnResourceSelectionServices;

/* Original unchecked selector and byte/word domains. Native dependencies use
   their declared DOS/retry seams; fatal 1949/04D0 exits keep all live frames. */
LmnDatFileResult lmn_load_selected_resources_core(uint8_t *,const LmnResourceSelectionCall *,
    const LmnDatLoadSegments *,const LmnResourceSelectionServices *);
void lmn_load_selected_resources_adapter(uint8_t *,LmnRegs *,const LmnResourceSelectionServices *);
#endif

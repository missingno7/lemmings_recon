#ifndef LEMMINGS_RESOURCE_SELECT_FULL_H
#define LEMMINGS_RESOURCE_SELECT_FULL_H

#include "resource_select.h"
#include "file_error.h"

typedef LmnFileErrorState LmnResourceSelectionFullState;

typedef struct LmnResourceSelectionFullServices {
    const LmnResourceSelectionServices *selection;
    const LmnFileErrorServices *file_error;
    const LmnFatalCleanupServices *cleanup;
} LmnResourceSelectionFullServices;

typedef enum LmnResourceSelectionFullStatus {
    LMN_RESOURCE_SELECTION_FULL_READY = 0,
    LMN_RESOURCE_SELECTION_FULL_TERMINATED = 1,
    LMN_RESOURCE_SELECTION_FULL_MISSING_PROVIDER = 2,
    LMN_RESOURCE_SELECTION_FULL_CHANGED_RETURN = 3
} LmnResourceSelectionFullStatus;

typedef struct LmnResourceSelectionFullResult {
    LmnResourceSelectionFullState state;
    uint16_t continuation;
    enum LmnResourceSelectionFullStatus status;
} LmnResourceSelectionFullResult;

/* RAM-only logical composition. The selected-resource execution core consumes
   each actual immediate-child CALL return and stops on changed targets. READY
   stops before the selector's outer RET, whose actual word remains at state
   SS:SP. Input carries all twelve registers, including fields still live at
   the early decimal-call boundary. Fatal transfers enter 1949 or 04D0
   directly with live frames intact;
   neither connection adds a CALL frame or unwinds the selector stack. */
LmnResourceSelectionFullResult lmn_load_selected_resources_full_core(
    uint8_t *memory, uint16_t error_main_data_segment,
    const LmnDatFileCall *input, const LmnDatLoadSegments *segments,
    const LmnResourceSelectionFullServices *services);
/* Bus-aware selector and fatal tails; RAM-only DAT/raw child domains remain. */
LmnResourceSelectionFullResult lmn_load_selected_resources_full_bus_core(
    uint8_t *memory,uint16_t error_main_data_segment,const LmnDatFileCall *input,
    const LmnDatLoadSegments *segments,const LmnResourceSelectionFullServices *services,
    const LmnRasterBus *bus);

/* Reads the four relocated DAT segment operands and the 194B main-data
   operand, maps all twelve CPU fields, and consumes the actual outer RET only
   for READY. Every other status sets IP to continuation and leaves the current
   stack frame intact. This adapter has no raster-bus argument. */
void lmn_load_selected_resources_full_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnResourceSelectionFullServices *services);

#endif

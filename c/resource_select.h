#ifndef LEMMINGS_RESOURCE_SELECT_H
#define LEMMINGS_RESOURCE_SELECT_H
#include "dat_load.h"
#include "resource_raw.h"
#include "special_blit.h"

typedef struct LmnResourceSelectionCall {
    uint16_t main_data_segment,stack_segment,stack_offset,flags,base_cursor;
} LmnResourceSelectionCall;
typedef struct LmnResourceSelectionServices {
    const LmnDatFileServices *files;
    const LmnDatIo *io;
    const LmnRawResourceServices *raw;
} LmnResourceSelectionServices;

typedef enum LmnResourceSelectionStatus {
    LMN_RESOURCE_SELECTION_READY = 0,
    LMN_RESOURCE_SELECTION_FILE_ERROR = 1,
    LMN_RESOURCE_SELECTION_CLEANUP = 2,
    LMN_RESOURCE_SELECTION_CHANGED_RETURN = 3
} LmnResourceSelectionStatus;

typedef struct LmnResourceSelectionExecution {
    LmnDatFileCall state;
    uint16_t continuation;
    enum LmnResourceSelectionStatus status;
} LmnResourceSelectionExecution;

/* Original unchecked selector and byte/word domains. Native dependencies use
   their declared DOS/retry seams. The execution API consumes each actual
   immediate-child return word and stops on a changed target. Fatal 1949/04D0
   exits keep all live frames. Its LmnDatFileCall input carries all twelve
   entry fields so an early changed return after decimal conversion preserves
   incoming DX, DI and ES before the selector overwrites them. */
LmnResourceSelectionExecution lmn_load_selected_resources_execution_core(
    uint8_t *,const LmnDatFileCall *,const LmnDatLoadSegments *,
    const LmnResourceSelectionServices *);
/* Selector-owned reads/writes/saves and decimal stores use this bus. DAT/raw
   children retain their documented ordinary-RAM/DOS/retry domains. This does
   not claim arbitrary VGA input/heap/stack support inside those children. */
LmnResourceSelectionExecution lmn_load_selected_resources_bus_execution_core(
    uint8_t *,const LmnDatFileCall *,const LmnDatLoadSegments *,
    const LmnResourceSelectionServices *,const LmnRasterBus *);

/* Legacy result API: callers must provide intact immediate child return words.
   Its five-field input preserves the historical zero initialization of the
   other entry registers. A changed child return is outside this ABI domain
   and is reported as fatal=3. */
LmnDatFileResult lmn_load_selected_resources_core(uint8_t *,const LmnResourceSelectionCall *,
    const LmnDatLoadSegments *,const LmnResourceSelectionServices *);

/* Uses the execution API. READY consumes the actual outer near-return word at
   returned SS:SP; every non-READY status reports its continuation and leaves
   that outer frame unconsumed. Changed child returns have already consumed
   their own actual return word. */
void lmn_load_selected_resources_adapter(uint8_t *,LmnRegs *,const LmnResourceSelectionServices *);
#endif

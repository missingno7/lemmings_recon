#ifndef LEMMINGS_RESOURCE_RAW_FULL_H
#define LEMMINGS_RESOURCE_RAW_FULL_H

#include "resource_raw.h"
#include "file_error.h"

typedef LmnFileErrorState LmnRawResourceFullState;

typedef struct LmnRawResourceFullServices {
    const LmnRawResourceServices *raw;
    const LmnFileErrorServices *file_error;
} LmnRawResourceFullServices;

typedef enum LmnRawResourceFullStatus {
    LMN_RAW_RESOURCE_FULL_READY = 0,
    LMN_RAW_RESOURCE_FULL_TERMINATED = 1,
    LMN_RAW_RESOURCE_FULL_MISSING_PROVIDER = 2,
    LMN_RAW_RESOURCE_FULL_CHANGED_RETURN = 3
} LmnRawResourceFullStatus;

typedef struct LmnRawResourceFullResult {
    LmnRawResourceFullState state;
    uint16_t continuation;
    enum LmnRawResourceFullStatus status;
} LmnRawResourceFullResult;

/* services, services->raw and all three raw callbacks must be present.
   Printer services may be missing; their original INT boundary is returned.
   READY stops before 1939 RET; fatal paths never unwind the raw save frame. */
LmnRawResourceFullResult lmn_read_raw_resource_full_core(uint8_t *memory,
    uint16_t main_data_segment, const LmnRawResourceFullState *input,
    const LmnRawResourceFullServices *services, const LmnRasterBus *bus);

void lmn_read_raw_resource_full_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnRawResourceFullServices *services, const LmnRasterBus *bus);

#endif

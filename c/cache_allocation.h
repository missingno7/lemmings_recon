#ifndef LEMMINGS_CACHE_ALLOCATION_H
#define LEMMINGS_CACHE_ALLOCATION_H
#include "special_blit.h"

/* INT 21h/AH=48h seam. Inputs are AX, BX, and FLAGS. The provider may mutate
   the canonical 1 MiB memory through the supplied pointer and returns AX, BX,
   and FLAGS; it preserves other machine state. The services configuration is
   read-only to the core. */
typedef struct LmnCacheAllocationServiceResult {
    uint16_t value, paragraphs, flags;
} LmnCacheAllocationServiceResult;

typedef struct LmnCacheAllocationServices {
    void *context;
    void (*allocate)(void *, uint8_t *memory, uint16_t value,
        uint16_t paragraphs, uint16_t flags,
        LmnCacheAllocationServiceResult *out);
} LmnCacheAllocationServices;

typedef enum LmnCacheAllocationStatus {
    LMN_CACHE_ALLOCATION_READY = 0,
    LMN_CACHE_ALLOCATION_MISSING_PROVIDER = 1
} LmnCacheAllocationStatus;

typedef struct LmnCacheAllocationResult {
    uint16_t value, paragraphs, flags, continuation;
    enum LmnCacheAllocationStatus status;
} LmnCacheAllocationResult;

/* The core owns no stack frame. Its ready continuation names the next RET site.
   Optional bus callbacks receive canonical 20-bit physical addresses and the
   live flags; word stores issue low byte then physical+1 with 20-bit wrap. */
LmnCacheAllocationResult lmn_allocate_dat_cache_core(uint8_t *memory,
    uint16_t data_segment, uint16_t incoming_value, uint16_t flags,
    const LmnCacheAllocationServices *services, const LmnRasterBus *bus);

/* The adapter consumes the live near-RET word through the optional bus only
   after a ready core result, reading low then high and advancing SP modulo
   16 bits. On a missing provider it stops at the first INT 21h boundary. */
void lmn_allocate_dat_cache_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnCacheAllocationServices *services, const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_MINIMAP_SAMPLE_H
#define LEMMINGS_MINIMAP_SAMPLE_H

#include "special_blit.h"

typedef struct LmnMinimapSampleResult {
    uint16_t value;          /* AX is zero after sixteen SHR instructions. */
    uint16_t population_mask; /* DH is population; DL is the incoming mask. */
    uint16_t count;          /* CX is restored from the live SS stack word. */
    uint16_t stack_offset;   /* SP after PUSH CX and POP CX. */
    uint16_t flags;
} LmnMinimapSampleResult;

/* Accumulate one pair of ES bytes into a CS byte when its population exceeds
   eight.  The optional bus covers byte accesses, including the live stack. */
LmnMinimapSampleResult lmn_accumulate_minimap_sample_core(uint8_t *mem,
    uint16_t code_segment, uint16_t extra_segment, uint16_t stack_segment,
    uint16_t stack_offset, uint16_t source_cursor, uint16_t target_cursor,
    uint8_t mask, uint16_t count, uint16_t flags, const LmnRasterBus *bus);

/* Near-return adapter: CX restoration and RET both reread live SS memory. */
void lmn_accumulate_minimap_sample_adapter(uint8_t *mem, LmnRegs *regs,
    const LmnRasterBus *bus);

#endif

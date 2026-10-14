#ifndef LEMMINGS_MINIMAP_ROW_H
#define LEMMINGS_MINIMAP_ROW_H
#include "special_blit.h"
typedef struct LmnMinimapRowCall {
    uint16_t code_segment,extra_segment,stack_segment,stack_offset;
    uint16_t source_cursor,target_cursor,count,flags;
} LmnMinimapRowCall;
typedef struct LmnMinimapRowResult {
    uint16_t value,population_mask,count,source_cursor,stack_offset,flags,continuation,changed_return;
} LmnMinimapRowResult;
LmnMinimapRowResult lmn_accumulate_minimap_row_core(uint8_t *,const LmnMinimapRowCall *,const LmnRasterBus *);
void lmn_accumulate_minimap_row_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);
#endif

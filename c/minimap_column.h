#ifndef LEMMINGS_MINIMAP_COLUMN_H
#define LEMMINGS_MINIMAP_COLUMN_H
#include "special_blit.h"
typedef struct LmnMinimapColumnCall {
    uint16_t code_segment,data_segment,stack_segment,stack_offset,flags;
} LmnMinimapColumnCall;
typedef struct LmnMinimapColumnResult {
    uint16_t value,target_cursor,count,port_or_population,source_cursor,output_cursor;
    uint16_t data_segment,extra_segment,stack_offset,flags,continuation,changed_return;
} LmnMinimapColumnResult;
/* A raster bus with word-port output is required. Device-owned planes and
   latches must remain shared with its byte callbacks throughout the call. */
LmnMinimapColumnResult lmn_update_minimap_column_core(uint8_t *,const LmnMinimapColumnCall *,const LmnRasterBus *);
void lmn_update_minimap_column_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);
#endif

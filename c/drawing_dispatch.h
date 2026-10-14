#ifndef LEMMINGS_DRAWING_DISPATCH_H
#define LEMMINGS_DRAWING_DISPATCH_H

#include "special_blit.h"

typedef struct LmnDrawingDispatchCall {
    uint16_t data_segment,stack_segment,stack_offset,left,top,packed_height,width;
    uint16_t source_cursor,destination_cursor,control,flags;
} LmnDrawingDispatchCall;

typedef struct LmnDrawingDispatchResult {
    uint16_t work_value,second_source_cursor,packed_counts,width_state;
    uint16_t source_cursor,destination_cursor,control,stack_offset,flags,continuation;
} LmnDrawingDispatchResult;

/* Logical entry at CS:885E. Ends at 88BF, 9140, 93A7, 9810, or the
   unexecuted outer far return at 88AB. Memory aliases remain canonical RAM. */
LmnDrawingDispatchResult lmn_prepare_planar_drawing_dispatch_core(
    uint8_t *memory,const LmnDrawingDispatchCall *call,const LmnRasterBus *bus);

/* Shared unshifted selector at CS:939E; leaves all registers except flags and
   the continuation unchanged. */
LmnDrawingDispatchResult lmn_select_unshifted_planar_path_core(
    uint8_t *memory,const LmnDrawingDispatchCall *call,const LmnRasterBus *bus);

/* Register adapter for the 885E, 88A6, and 939E logical entries. */
void lmn_prepare_planar_drawing_dispatch_adapter(uint8_t *memory,LmnRegs *regs,
    const LmnRasterBus *bus);

#endif

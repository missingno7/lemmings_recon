#ifndef LEMMINGS_DRAWING_INPUTS_H
#define LEMMINGS_DRAWING_INPUTS_H
#include "special_blit.h"
typedef struct LmnDrawingInputsCall {
    uint16_t data_segment,stack_segment,stack_offset,source_pitch,top,packed_height,width;
    uint16_t source_cursor,destination_cursor,control,flags;
} LmnDrawingInputsCall;
typedef struct LmnDrawingInputsResult {
    uint16_t left,top,packed_height,width,source_cursor,destination_cursor,control;
    uint16_t stack_offset,flags,continuation,changed_return;
} LmnDrawingInputsResult;
/* 882D assumes three pending save words from the original 8822 prologue.
   Ends before the separately scoped 885E drawing dispatch or 88AB RETF, or at changed RET. */
LmnDrawingInputsResult lmn_prepare_planar_drawing_inputs_core(uint8_t *,const LmnDrawingInputsCall *,const LmnRasterBus *);
void lmn_prepare_planar_drawing_inputs_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);
#endif

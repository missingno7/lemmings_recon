#ifndef LEMMINGS_LEVEL_DRAWING_H
#define LEMMINGS_LEVEL_DRAWING_H
#include "special_blit.h"
typedef struct LmnLevelDrawingCall {
    uint16_t data_segment,stack_segment,stack_offset,code_segment,height_state,flags;
} LmnLevelDrawingCall;
typedef struct LmnLevelDrawingResult {
    uint16_t value,height_state,count,product_high,output_cursor,output_segment;
    uint16_t stack_offset,flags,continuation,code_segment,changed_return;
} LmnLevelDrawingResult;
/* Inner CALL frames use the same live memory as the clear/layout stores.
   A changed inner RET/RETF stops at its actual target before executing it. */
LmnLevelDrawingResult lmn_initialize_level_drawing_core(uint8_t *,const LmnLevelDrawingCall *,const LmnRasterBus *);
void lmn_level_drawing_adapter(uint8_t *,LmnRegs *,unsigned tail,const LmnRasterBus *);
#endif

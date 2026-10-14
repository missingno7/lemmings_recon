#ifndef LEMMINGS_DRAWING_PLAN_H
#define LEMMINGS_DRAWING_PLAN_H
#include "drawing_inputs.h"
#include "drawing_source.h"
typedef struct LmnDrawingPlanResult {
    LmnDrawingSourceResult state;
    uint16_t changed_return;
} LmnDrawingPlanResult;
/* Starts at 882D with the three live prologue saves. Stops before the selected
   variant drawing body, outer far return, or changed child return target. */
LmnDrawingPlanResult lmn_prepare_planar_drawing_plan_core(
    uint8_t *, const LmnDrawingInputsCall *, const LmnRasterBus *);
void lmn_prepare_planar_drawing_plan_adapter(uint8_t *, LmnRegs *, const LmnRasterBus *);
#endif

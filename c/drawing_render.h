#ifndef LEMMINGS_DRAWING_RENDER_H
#define LEMMINGS_DRAWING_RENDER_H
#include "drawing_plan.h"
#include "aligned_read_mask.h"
typedef struct LmnDrawingRenderCall {
    LmnDrawingInputsCall inputs;
    uint16_t game_data_segment, output_segment;
} LmnDrawingRenderCall;
typedef struct LmnDrawingRenderResult {
    LmnDrawingPlanResult plan;
    uint16_t source_segment, output_segment, body_returned;
} LmnDrawingRenderResult;
/* Composes 882D preparation with the aligned opaque 983B body. Other selected
   drawing bodies and changed child returns remain explicit continuations. */
LmnDrawingRenderResult lmn_draw_prepared_aligned_opaque_core(
    uint8_t *, const LmnDrawingRenderCall *, const LmnRasterBus *);
void lmn_draw_prepared_aligned_opaque_adapter(
    uint8_t *, LmnRegs *, uint16_t game_data_segment, const LmnRasterBus *);

/* Composes preparation with either aligned opaque or default masked drawing.
   All other selected bodies and changed child returns retain their seams. */
LmnDrawingRenderResult lmn_draw_prepared_planar_core(
    uint8_t *, const LmnDrawingRenderCall *, const LmnRasterBus *);
void lmn_draw_prepared_planar_adapter(
    uint8_t *, LmnRegs *, uint16_t game_data_segment, const LmnRasterBus *);
/* All six aligned bodies. A missing byte-port provider leaves969C explicit;
   shifted bodies and changed child returns retain their original seams. */
LmnDrawingRenderResult lmn_draw_prepared_aligned_core(
    uint8_t *, const LmnDrawingRenderCall *, const LmnRasterBus *,
    const LmnRasterBytePorts *);
void lmn_draw_prepared_aligned_adapter(
    uint8_t *, LmnRegs *, uint16_t game_data_segment, const LmnRasterBus *,
    const LmnRasterBytePorts *);
/* Preparation, all six aligned bodies and the shifted 20/40 effects.
   Other shifted bodies, absent byte providers and changed child returns stop
   at their explicit continuations. Existing API scopes remain unchanged. */
LmnDrawingRenderResult lmn_draw_prepared_planar_effects_core(
    uint8_t *, const LmnDrawingRenderCall *, const LmnRasterBus *,
    const LmnRasterBytePorts *);
void lmn_draw_prepared_planar_effects_adapter(
    uint8_t *, LmnRegs *, uint16_t game_data_segment, const LmnRasterBus *,
    const LmnRasterBytePorts *);
#endif

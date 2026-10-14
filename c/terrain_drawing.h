#ifndef LEMMINGS_TERRAIN_DRAWING_H
#define LEMMINGS_TERRAIN_DRAWING_H

#include "drawing_render.h"

typedef struct LmnTerrainPieceCall {
    uint16_t data_segment, game_data_segment, stack_segment, stack_offset;
    uint16_t code_segment, packed_horizontal, packed_vertical, source_cursor;
    uint16_t output_segment, flags;
} LmnTerrainPieceCall;

typedef struct LmnTerrainPieceResult {
    LmnDrawingRenderResult drawing;
    uint16_t code_segment, ready_to_return, changed_far_return;
} LmnTerrainPieceResult;

/* Executes7C67..7CB4 and stops at the far child call. The saved SI remains live
   on SS. Record bytes and every stack word are read from canonical memory. */
LmnPlanarBitmapCall lmn_prepare_terrain_piece_core(
    uint8_t *, const LmnTerrainPieceCall *, const LmnRasterBus *);
void lmn_prepare_terrain_piece_adapter(
    uint8_t *, LmnRegs *, uint16_t game_data_segment, const LmnRasterBus *);

/* Composes the prefix with the normal8822 planar bitmap core. A normal child
   far return consumes the live IP/CS frame and POP SI, then stops before7CBB.
   Changed child far returns and drawing continuations remain explicit. */
LmnTerrainPieceResult lmn_draw_terrain_piece_core(
    uint8_t *, const LmnTerrainPieceCall *, const LmnRasterBus *,
    const LmnRasterBytePorts *);
void lmn_draw_terrain_piece_adapter(
    uint8_t *, LmnRegs *, uint16_t game_data_segment,
    const LmnRasterBus *, const LmnRasterBytePorts *);

#endif

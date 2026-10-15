#ifndef LEMMINGS_COORDINATE_PIXEL_H
#define LEMMINGS_COORDINATE_PIXEL_H

#include "regs.h"
#include "special_blit.h"

/* Inputs are the caller's live registers: BX=row_value (Y),
   CX=column_value (X), and DX=saved_value. */
typedef struct LmnCoordinatePixelCall {
    uint16_t data_segment, stack_segment, stack_offset;
    uint16_t column_value, row_value, saved_value, flags;
} LmnCoordinatePixelCall;

/* The core returns immediately before the original RET. BX/CX are the live
   values popped from SS, which may differ from their input values. */
typedef struct LmnCoordinatePixelResult {
    uint16_t value, row_value, column_value, restored_value;
    uint16_t destination_offset, output_segment, stack_offset, flags;
} LmnCoordinatePixelResult;

LmnCoordinatePixelResult lmn_prepare_coordinate_pixel_core(
    uint8_t *memory, const LmnCoordinatePixelCall *call,
    const LmnRasterBus *bus);
void lmn_prepare_coordinate_pixel_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_DRAWING_LAYOUT_H
#define LEMMINGS_DRAWING_LAYOUT_H
#include <stdint.h>
#include "regs.h"
#include "special_blit.h"

typedef struct LmnDrawingLayoutResult {
    uint16_t value;          /* AX: low half of pitch * height */
    uint16_t product_high;   /* DX: high half of the unsigned product */
    uint16_t flags;
    uint16_t pitch_bytes;
    uint16_t extent_bytes;
} LmnDrawingLayoutResult;

/* Stores the live drawing fields through DS. A null raster bus uses ordinary
   20-bit RAM; a bus lets the caller retain device/alias behavior. */
LmnDrawingLayoutResult lmn_set_drawing_layout_core(uint8_t *memory,
    uint16_t data_segment, uint16_t width_pixels, uint16_t height_pixels,
    uint16_t origin, uint16_t flags, const LmnRasterBus *bus);

/* Far-call boundary adapter under the permissive 20-bit RAM/16-bit SP model.
   CPU-family stack-limit faults are outside this adapter's tested domain. */
void lmn_set_drawing_layout_adapter(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus);

#endif

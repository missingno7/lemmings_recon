#ifndef LEMMINGS_OBJECT_GRAPHICS_H
#define LEMMINGS_OBJECT_GRAPHICS_H
#include <stdint.h>
#include "regs.h"
#include "special_blit.h"

typedef struct LmnObjectGraphicsResult {
    uint16_t value;
    uint16_t definition_cursor, count, product_high;
    uint16_t source_cursor, output_cursor, extra_segment;
    uint16_t stack_offset, flags;
} LmnObjectGraphicsResult;

/* Copies active 28-byte ground records into the live graphics slots. The
   single memory image includes the caller's live SS stack and DS/ES aliases.
   stack_offset remains on the caller's live RET word for the adapter. */
LmnObjectGraphicsResult lmn_copy_object_graphics_core(uint8_t *mem,
    uint16_t data_segment, uint16_t stack_segment, uint16_t stack_offset,
    uint16_t product_high, uint16_t flags);
LmnObjectGraphicsResult lmn_copy_object_graphics_bus_core(uint8_t *mem,
    uint16_t data_segment, uint16_t stack_segment, uint16_t stack_offset,
    uint16_t product_high, uint16_t flags, const LmnRasterBus *bus);
void lmn_copy_object_graphics_adapter(uint8_t *mem, LmnRegs *r);
void lmn_copy_object_graphics_bus_adapter(uint8_t *mem, LmnRegs *r,
    const LmnRasterBus *bus);

#endif

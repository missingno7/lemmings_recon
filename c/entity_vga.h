#ifndef LEMMINGS_ENTITY_VGA_H
#define LEMMINGS_ENTITY_VGA_H
#include "special_blit.h"

typedef struct LmnEntityReadbackResult {
    uint16_t value, output_segment, port, flags;
} LmnEntityReadbackResult;
typedef struct LmnEntityPixelExchangeResult {
    uint16_t value, packed_bytes, third_byte_word, destination_offset;
    uint16_t output_segment, port, flags;
} LmnEntityPixelExchangeResult;

/* Logical cores stop immediately before their near RET. The optional bus
   owns VGA planes/latches and word ports; missing callbacks use RAM/no-op
   ports for constructed RAM callers, not a replacement VGA device. */
LmnEntityReadbackResult lmn_configure_entity_readback_core(uint8_t *memory,
    uint16_t data_segment, uint16_t stack_segment, uint16_t flags,
    const LmnRasterBus *bus);
LmnEntityPixelExchangeResult lmn_exchange_entity_pixel_bytes_core(uint8_t *memory,
    uint16_t stack_segment, uint16_t destination_offset, uint16_t packed_masks,
    uint16_t third_mask_word, uint16_t flags, const LmnRasterBus *bus);
void lmn_configure_entity_readback_adapter(uint8_t *, LmnRegs *, const LmnRasterBus *);
void lmn_exchange_entity_pixel_bytes_adapter(uint8_t *, LmnRegs *, const LmnRasterBus *);
#endif

#ifndef LEMMINGS_ENTITY_SPRITE_ALIGNED_H
#define LEMMINGS_ENTITY_SPRITE_ALIGNED_H

#include "special_blit.h"

enum LmnEntityAlignedSpriteStatus {
    LMN_ENTITY_ALIGNED_SPRITE_READY = 0
};

/* Live register roles at DrawEntityAlignedSprite (6170). */
typedef struct LmnEntityAlignedSpriteCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityAlignedSpriteCall;

typedef struct LmnEntityAlignedSpriteResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityAlignedSpriteResult;

/* Executes the live POP DS, stopping immediately before RET at 64D8. */
LmnEntityAlignedSpriteResult lmn_draw_entity_aligned_sprite_core(
    uint8_t *memory,const LmnEntityAlignedSpriteCall *call,
    const LmnRasterBus *bus);

/* Applies all roles and consumes the actual live near-RET word. */
uint16_t lmn_draw_entity_aligned_sprite_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_ENTITY_SPRITE_WIDE_H
#define LEMMINGS_ENTITY_SPRITE_WIDE_H

#include "special_blit.h"

enum LmnEntityWideSpriteStatus {
    LMN_ENTITY_WIDE_SPRITE_READY = 0
};

/* Live register roles at DrawEntityWideSprite32 (6BDB). */
typedef struct LmnEntityWideSpriteCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityWideSpriteCall;

typedef struct LmnEntityWideSpriteResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityWideSpriteResult;

/* Executes all live row PUSH/POP effects and the final POP DS, stopping
   immediately before the actual near RET at 6CFB. */
LmnEntityWideSpriteResult lmn_draw_entity_wide_sprite32_core(uint8_t *memory,
    const LmnEntityWideSpriteCall *call,const LmnRasterBus *bus);

/* Applies all returned roles and consumes the actual live near-RET word. */
uint16_t lmn_draw_entity_wide_sprite32_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

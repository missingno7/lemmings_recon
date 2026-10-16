#ifndef LEMMINGS_ENTITY_SPRITE_SHIFTED_H
#define LEMMINGS_ENTITY_SPRITE_SHIFTED_H

#include "special_blit.h"

enum LmnEntityShiftedSpriteStatus {
    LMN_ENTITY_SHIFTED_SPRITE_READY = 0
};

/* Live register roles at DrawEntityShiftedSprite12/13 (64D9/65D8). */
typedef struct LmnEntityShiftedSpriteCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityShiftedSpriteCall;

typedef struct LmnEntityShiftedSpriteResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityShiftedSpriteResult;

/* Each core executes its independent 12- or 13-row body through the live
   POP DS and stops immediately before that entry's near RET. */
LmnEntityShiftedSpriteResult lmn_draw_entity_shifted_sprite12_core(
    uint8_t *memory,const LmnEntityShiftedSpriteCall *call,
    const LmnRasterBus *bus);
LmnEntityShiftedSpriteResult lmn_draw_entity_shifted_sprite13_core(
    uint8_t *memory,const LmnEntityShiftedSpriteCall *call,
    const LmnRasterBus *bus);

/* Applies all returned roles and consumes the actual live SS:SP RET. */
uint16_t lmn_draw_entity_shifted_sprite12_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus);
uint16_t lmn_draw_entity_shifted_sprite13_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus);

#endif

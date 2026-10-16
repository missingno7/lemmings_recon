#ifndef LEMMINGS_ENTITY_SPRITE_DISPATCH_H
#define LEMMINGS_ENTITY_SPRITE_DISPATCH_H

#include "special_blit.h"

enum LmnEntitySpriteDispatchStatus {
    LMN_ENTITY_SPRITE_DISPATCH_READY = 0,
    LMN_ENTITY_SPRITE_DISPATCH_UNKNOWN_CALLBACK = 1,
    LMN_ENTITY_SPRITE_DISPATCH_CHILD_RETURN = 2
};

/* Live roles at DrawObjectSprite (706F). */
typedef struct LmnEntitySpriteDispatchCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntitySpriteDispatchCall;

typedef struct LmnEntitySpriteDispatchResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntitySpriteDispatchResult;

/* Executes 706F..715D through the final POP DI. READY stops just before the
   outer RET at 715E. An unsupported live callback stops before CALL AX at
   715B; changed child returns retain the child-returned machine state. */
LmnEntitySpriteDispatchResult lmn_draw_entity_sprite_core(
    uint8_t *memory,const LmnEntitySpriteDispatchCall *call,
    const LmnRasterBus *bus);

/* Applies the logical result and consumes the live outer RET only on READY. */
uint16_t lmn_draw_entity_sprite_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

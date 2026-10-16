#ifndef LEMMINGS_SPRITE_WIDE_BANKS_H
#define LEMMINGS_SPRITE_WIDE_BANKS_H

#include "regs.h"
#include "special_blit.h"

enum LmnSpriteWideBanksStatus {
    LMN_SPRITE_WIDE_BANKS_READY = 0
};

/* Live register and segment roles at GenerateFiveByteSpriteBanks (5C06). */
typedef struct LmnSpriteWideBanksCall {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnSpriteWideBanksCall;

typedef struct LmnSpriteWideBanksResult {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnSpriteWideBanksResult;

/* Executes 5C06..5CBD and stops before the real RET at 5CC0. */
LmnSpriteWideBanksResult lmn_generate_sprite_shift_banks5_core(
    uint8_t *memory,const LmnSpriteWideBanksCall *call,
    const LmnRasterBus *bus);

/* Maps LmnRegs to the core and consumes the actual live SS:SP RET on READY. */
uint16_t lmn_generate_sprite_shift_banks5_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus);

#endif

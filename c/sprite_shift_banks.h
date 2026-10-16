#ifndef LEMMINGS_SPRITE_SHIFT_BANKS_H
#define LEMMINGS_SPRITE_SHIFT_BANKS_H

#include "regs.h"
#include "special_blit.h"

enum LmnSpriteShiftBanksStatus {
    LMN_SPRITE_SHIFT_BANKS_READY = 0
};

/* Live register and segment roles at GenerateThreeByteSpriteBanks (5B11). */
typedef struct LmnSpriteShiftBanksCall {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnSpriteShiftBanksCall;

typedef struct LmnSpriteShiftBanksResult {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnSpriteShiftBanksResult;

/* Executes 5B11..5BAC and stops before the real RET at 5BAF. */
LmnSpriteShiftBanksResult lmn_generate_sprite_shift_banks3_core(
    uint8_t *memory,const LmnSpriteShiftBanksCall *call,
    const LmnRasterBus *bus);

/* Maps LmnRegs to the core and consumes the actual live SS:SP RET on READY. */
uint16_t lmn_generate_sprite_shift_banks3_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus);

#endif

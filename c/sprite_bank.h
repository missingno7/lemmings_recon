#ifndef LEMMINGS_SPRITE_BANK_H
#define LEMMINGS_SPRITE_BANK_H

#include "regs.h"
#include "special_blit.h"

enum LmnSpriteBankStatus {
    LMN_SPRITE_BANK_READY = 0
};

/* Live register and segment roles at CopySpritePlanesAndAppendMask (5BB0). */
typedef struct LmnSpriteBankCall {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnSpriteBankCall;

typedef struct LmnSpriteBankResult {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnSpriteBankResult;

/* Executes 5BB0..5C02 and stops before the real RET at 5C05. All source,
   destination, mask, and stack words remain in canonical 20-bit memory. */
LmnSpriteBankResult lmn_copy_sprite_planes_mask_core(
    uint8_t *memory,const LmnSpriteBankCall *call,const LmnRasterBus *bus);

/* Maps LmnRegs to the core and consumes the actual live SS:SP RET on READY. */
uint16_t lmn_copy_sprite_planes_mask_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus);

#endif

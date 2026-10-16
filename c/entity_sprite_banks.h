#ifndef LEMMINGS_ENTITY_SPRITE_BANKS_H
#define LEMMINGS_ENTITY_SPRITE_BANKS_H

#include "regs.h"
#include "special_blit.h"

enum LmnEntitySpriteBanksStatus {
    LMN_ENTITY_SPRITE_BANKS_READY = 0,
    LMN_ENTITY_SPRITE_BANKS_CHILD_STOP = 1,
    LMN_ENTITY_SPRITE_BANKS_CHANGED_CHILD_RETURN = 2
};

/* Live register and segment roles at GenerateEntitySpriteBanks (59BB). */
typedef struct LmnEntitySpriteBanksCall {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntitySpriteBanksCall;

typedef struct LmnEntitySpriteBanksResult {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} LmnEntitySpriteBanksResult;

/* Executes 59BB..5ABF through the actual child adapters and stops before
   the outer RET at 5AC0. Child stops retain their full returned machine state. */
LmnEntitySpriteBanksResult lmn_generate_entity_sprite_banks_core(
    uint8_t *memory,const LmnEntitySpriteBanksCall *call,
    const LmnRasterBus *bus);

/* Maps LmnRegs to the core and consumes the actual live SS:SP RET on READY. */
uint16_t lmn_generate_entity_sprite_banks_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_FIXED_WORD_BANKS_H
#define LEMMINGS_FIXED_WORD_BANKS_H

#include "regs.h"
#include "special_blit.h"

enum LmnFixedWordBanksStatus {
    LMN_FIXED_WORD_BANKS_READY = 0,
    LMN_FIXED_WORD_BANKS_CHANGED_CHILD_RETURN = 1
};

/* Live register and segment roles at GenerateFixedWordMaskBanks (5CC1). */
typedef struct LmnFixedWordBanksCall {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnFixedWordBanksCall;

typedef struct LmnFixedWordBanksResult {
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry;
} LmnFixedWordBanksResult;

/* Executes 5CC1..5CDC and the 5CDD..5D16 fall-through, stopping before RET
   5D17. The first child call uses its real SS:SP return word. */
LmnFixedWordBanksResult lmn_generate_fixed_word_mask_banks_core(
    uint8_t *memory,const LmnFixedWordBanksCall *call,
    const LmnRasterBus *bus);

/* Maps LmnRegs to the core and consumes the live outer SS:SP RET only on READY. */
uint16_t lmn_generate_fixed_word_mask_banks_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_ENTITY_COUNTDOWN_H
#define LEMMINGS_ENTITY_COUNTDOWN_H

#include "sound_interrupt.h"

enum {
    LMN_ENTITY_COUNTDOWN_READY=0,
    LMN_ENTITY_COUNTDOWN_UNBOUND_VECTOR=1,
    LMN_ENTITY_COUNTDOWN_UNTRANSLATED_SOUND=2,
    LMN_ENTITY_COUNTDOWN_CHANGED_SOUND_RETURN=3
};

typedef struct LmnEntityCountdownCall {
    uint16_t value,data_segment,code_segment,stack_segment,stack_offset;
    uint16_t record_cursor,flags;
} LmnEntityCountdownCall;

typedef struct LmnEntityCountdownResult {
    uint16_t value,data_segment,code_segment,stack_offset,record_cursor;
    uint16_t flags,continuation,status;
} LmnEntityCountdownResult;

/* Executes only the countdown transition at 2E04..2EBF on canonical memory. */
LmnEntityCountdownResult lmn_advance_entity_countdown_core(uint8_t *memory,
    const LmnEntityCountdownCall *call,const LmnSoundDriverBinding *binding,
    const LmnRasterBus *bus);

/* Applies the core registers. READY additionally executes the live outer RET. */
uint16_t lmn_advance_entity_countdown_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnSoundDriverBinding *binding,const LmnRasterBus *bus);

#endif

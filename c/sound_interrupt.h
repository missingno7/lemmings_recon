#ifndef LEMMINGS_SOUND_INTERRUPT_H
#define LEMMINGS_SOUND_INTERRUPT_H
#include "special_blit.h"

enum { LMN_SOUND_DRIVER_ADLIB=1, LMN_SOUND_DRIVER_TANDY=2 };
enum {
    LMN_SOUND_INTERRUPT_RETURNED=0,
    LMN_SOUND_INTERRUPT_UNBOUND_VECTOR=1,
    LMN_SOUND_INTERRUPT_UNTRANSLATED_SERVICE=2,
    LMN_SOUND_INTERRUPT_CHANGED_RETURN=3
};

typedef struct LmnSoundDriverBinding {
    uint16_t driver_segment,driver_kind;
} LmnSoundDriverBinding;

typedef struct LmnSoundInterruptCall {
    uint16_t value,data_segment,code_segment,stack_segment;
    uint16_t stack_offset,flags,return_offset;
} LmnSoundInterruptCall;

typedef struct LmnSoundInterruptResult {
    uint16_t value,data_segment,code_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnSoundInterruptResult;

/* Models the declared INT 61h frame/vector transport and composes only the two
   pinned native driver entry cores. Other IVT targets stay explicit exits. */
LmnSoundInterruptResult lmn_sound_interrupt61_core(uint8_t *memory,
    const LmnSoundInterruptCall *call,const LmnSoundDriverBinding *binding,
    const LmnRasterBus *bus);

#endif

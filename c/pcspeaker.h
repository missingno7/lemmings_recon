#ifndef LEMMINGS_PCSPEAKER_H
#define LEMMINGS_PCSPEAKER_H
#include <stdint.h>
#include "regs.h"
#include "special_blit.h"

typedef uint8_t (*LmnReadPort8)(void *context, uint16_t port);
typedef void (*LmnWritePort8)(void *context, uint16_t port, uint8_t value);
typedef struct LmnPort8 {
    void *context;
    LmnReadPort8 read;
    LmnWritePort8 write;
} LmnPort8;

typedef struct LmnPcSoundResult {
    uint16_t ax, bx, cx, dx, si, flags, defined_flags_mask;
} LmnPcSoundResult;

/* Operate directly on the original component's live data segment. */
LmnPcSoundResult lmn_pc_sound_effect_core(uint8_t *mem, uint16_t ds,
                                         uint8_t effect, uint16_t initial_dx,
                                         uint16_t flags);
LmnPcSoundResult lmn_pc_sound_effect_bus_core(uint8_t *mem,uint16_t ds,
    uint8_t effect,uint16_t initial_dx,uint16_t flags,const LmnRasterBus *bus);
LmnPcSoundResult lmn_pc_sound_tick_core(uint8_t *mem, uint16_t ds,
                                       uint16_t initial_ax, uint16_t initial_bx,
                                       uint16_t initial_dx, uint16_t initial_si,
                                       uint16_t flags, const LmnPort8 *ports);
LmnPcSoundResult lmn_pc_sound_stop_core(uint8_t *mem, uint16_t ds,
                                       uint16_t initial_ax, uint16_t initial_bx,
                                       uint16_t initial_cx, uint16_t initial_dx,
                                       uint16_t initial_si, uint16_t flags);
LmnPcSoundResult lmn_pc_sound_stop_bus_core(uint8_t *mem,uint16_t ds,
    uint16_t initial_ax,uint16_t initial_bx,uint16_t initial_cx,
    uint16_t initial_dx,uint16_t initial_si,uint16_t flags,
    const LmnRasterBus *bus);

/* Near-call adapters preserve observable register and return-stack behavior. */
void lmn_pc_sound_effect_adapter(uint8_t *mem, LmnRegs *r);
void lmn_pc_sound_effect_bus_adapter(uint8_t *mem,LmnRegs *r,
                                     const LmnRasterBus *bus);
void lmn_pc_sound_tick_adapter(uint8_t *mem, LmnRegs *r, const LmnPort8 *ports);
void lmn_pc_sound_stop_adapter(uint8_t *mem, LmnRegs *r);
void lmn_pc_sound_stop_bus_adapter(uint8_t *mem,LmnRegs *r,
                                   const LmnRasterBus *bus);
#endif

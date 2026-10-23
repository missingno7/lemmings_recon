#ifndef LEMMINGS_SOUND_LATCHES_H
#define LEMMINGS_SOUND_LATCHES_H
#include "regs.h"
#include "special_blit.h"

typedef struct LmnSoundLatchCall {
    uint16_t driver_segment, data_segment;
    uint16_t stack_segment, stack_offset;
    uint16_t value, flags;
} LmnSoundLatchCall;

typedef struct LmnSoundLatchResult {
    uint16_t data_segment, stack_offset, flags;
} LmnSoundLatchResult;

/* UNTRANSLATED (historical name) = the dispatcher stopped at a service body
   label (AH=0/1/2) without consuming the interrupt frame. For AdLib those
   bodies continue in c/adlib_engine.c (lmn_adlib_int61_adapter composes this
   dispatcher with them); Tandy bodies remain untranslated. */
enum { LMN_SOUND_CONTROL_IRET=0, LMN_SOUND_CONTROL_UNTRANSLATED=1 };

typedef struct LmnSoundControlResult {
    uint16_t value, data_segment, stack_offset, flags;
    uint16_t continuation, exit_kind;
} LmnSoundControlResult;

/* Six 8-byte sound-driver setter tails. Cores stop immediately before IRET;
   adapters perform the original three word pops from the live SS:SP frame. */
LmnSoundLatchResult lmn_adlib_latch3_core(uint8_t *,const LmnSoundLatchCall *,const LmnRasterBus *);
LmnSoundLatchResult lmn_adlib_latch4_core(uint8_t *,const LmnSoundLatchCall *,const LmnRasterBus *);
LmnSoundLatchResult lmn_adlib_latch5_core(uint8_t *,const LmnSoundLatchCall *,const LmnRasterBus *);
LmnSoundLatchResult lmn_tandy_latch3_core(uint8_t *,const LmnSoundLatchCall *,const LmnRasterBus *);
LmnSoundLatchResult lmn_tandy_latch4_core(uint8_t *,const LmnSoundLatchCall *,const LmnRasterBus *);
LmnSoundLatchResult lmn_tandy_latch5_core(uint8_t *,const LmnSoundLatchCall *,const LmnRasterBus *);

void lmn_adlib_latch3_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);
void lmn_adlib_latch4_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);
void lmn_adlib_latch5_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);
void lmn_tandy_latch3_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);
void lmn_tandy_latch4_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);
void lmn_tandy_latch5_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);

/* Execute the entry-0 dispatcher through a recognized service target or IRET.
   AH=0/1/2 stop at their service body labels (continuation = 0115/00A3/003A
   for AdLib, served by c/adlib_engine.c; Tandy bodies are untranslated). */
LmnSoundControlResult lmn_adlib_control_core(
    uint8_t *,const LmnSoundLatchCall *,const LmnRasterBus *);
LmnSoundControlResult lmn_tandy_control_core(
    uint8_t *,const LmnSoundLatchCall *,const LmnRasterBus *);
uint16_t lmn_adlib_control_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);
uint16_t lmn_tandy_control_adapter(uint8_t *,LmnRegs *,const LmnRasterBus *);

#endif

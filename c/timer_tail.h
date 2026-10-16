#ifndef LEMMINGS_TIMER_TAIL_H
#define LEMMINGS_TIMER_TAIL_H

#include "input_poll.h"
#include "interrupt_service.h"
#include "port_io.h"

typedef struct LmnTimerTailResult {
    LmnRegs registers;
    uint16_t status;
    uint16_t child_status;
    uint16_t service_status;
} LmnTimerTailResult;

enum LmnTimerTailStatus {
    LMN_TIMER_TAIL_READY = 0,
    LMN_TIMER_TAIL_UNBOUND_SERVICE = 1,
    LMN_TIMER_TAIL_EXTERNAL_STOP = 2,
    LMN_TIMER_TAIL_CHANGED_INTERRUPT_RETURN = 3,
    LMN_TIMER_TAIL_CHANGED_CHILD_RETURN = 4,
    LMN_TIMER_TAIL_CHILD_STOP = 5
};

/* The caller supplies the live timer frame already present at 183E:
   FLAGS, DI, SI, BP, BX, DX, CX, ES, DS, AX, hardware IP, CS, FLAGS.
   Core stops before the outer IRET at 18B1; adapter consumes that frame. */
LmnTimerTailResult lmn_game_timer_tail_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInputPollService *mouse,
    const LmnInterruptService *int60,
    const LmnInterruptService *int61,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

LmnTimerTailResult lmn_game_timer_tail_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInputPollService *mouse,
    const LmnInterruptService *int60,
    const LmnInterruptService *int61,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

#endif

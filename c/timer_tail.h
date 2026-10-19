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
    LMN_TIMER_TAIL_CHILD_STOP = 5,
    LMN_GAME_TIMER_MISSING_BYTE_INPUT = 6,
    LMN_GAME_TIMER_MISSING_PORT_OUTPUT = 7
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

/* Full handler entry at 17C7, including its ten live PUSH saves. The actual
   hardware IP/CS/FLAGS frame is already at SS:SP. registers.flags supplies live
   architectural entry FLAGS (reserved bits normalized, bit1 set, TF clear);
   a hardware IRQ normally also cleared IF. Constructed IF-set calls are a
   separate synchronous test domain. Uses the shared tail's service seams. */
LmnTimerTailResult lmn_game_timer_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInputPollService *mouse,
    const LmnInterruptService *int60,
    const LmnInterruptService *int61,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

LmnTimerTailResult lmn_game_timer_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInputPollService *mouse,
    const LmnInterruptService *int60,
    const LmnInterruptService *int61,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

/* Menu IRQ4C47: hardware frame already at liveSS:SP; eight actual saves.
   ES and entryFLAGS are not saved. Core stops before4C7D, adapter executes IRET.
   Uses the same architectural FLAGS and declared service preconditions as above. */
LmnTimerTailResult lmn_menu_timer_core(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *mouse,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnTimerTailResult lmn_menu_timer_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *mouse,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

/* Direct IVT08 installer5028. Core before503A; adapter consumes actual nearRET.
   Its vector writes can change the savedDS/return words through stack aliases. */
LmnTimerTailResult lmn_install_menu_timer_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBus *bus);
LmnTimerTailResult lmn_install_menu_timer_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBus *bus);

#endif

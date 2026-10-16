#ifndef LEMMINGS_INPUT_POLL_H
#define LEMMINGS_INPUT_POLL_H

#include "port_io.h"

/* INT 33 service entry is after the real FLAGS/CS/IP frame writes through the
   current IVT target. Return zero at pre-IRET with full live registers and
   canonical RAM; nonzero stops without IRET. The returned SS:SP owns its frame. */
typedef uint16_t (*LmnInputPollInterrupt33)(
    void *context, uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus);

typedef struct LmnInputPollService {
    void *context;
    LmnInputPollInterrupt33 interrupt33;
    uint16_t code_segment;
    uint16_t instruction_pointer;
} LmnInputPollService;

typedef struct LmnInputPollResult {
    LmnRegs registers;
    uint16_t status;
    uint16_t service_status;
} LmnInputPollResult;

enum LmnInputPollStatus {
    LMN_INPUT_POLL_READY = 0,
    LMN_INPUT_POLL_UNBOUND_SERVICE = 1,
    LMN_INPUT_POLL_EXTERNAL_STOP = 2,
    LMN_INPUT_POLL_CHANGED_INTERRUPT_RETURN = 3,
    LMN_INPUT_POLL_CHANGED_CHILD_RETURN = 4,
    LMN_INPUT_POLL_CHILD_STOP = 5,
    LMN_INPUT_POLL_UNSUPPORTED_CALLBACK = 6
};

/* Missing port providers propagate as CHILD_STOP with service_status set to
   the port status. Unknown indirect targets stop before CALL with status 6. */

/* Stops before the outer RET at 42A0; the adapter consumes its live word. */
LmnInputPollResult lmn_poll_mouse_position_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInputPollService *service, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus);
LmnInputPollResult lmn_poll_mouse_position_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInputPollService *service, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus);

/* Mode paths stop before their actual shared RET (4251, 42A0, or 4333). */
LmnInputPollResult lmn_poll_input_state_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInputPollService *service, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus);
LmnInputPollResult lmn_poll_input_state_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInputPollService *service, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus);

#endif

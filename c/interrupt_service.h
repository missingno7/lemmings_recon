#ifndef LEMMINGS_INTERRUPT_SERVICE_H
#define LEMMINGS_INTERRUPT_SERVICE_H

#include "special_blit.h"

/* Called at the current IVT target after FLAGS, CS and resume IP have been
   written to the live stack. A zero result returns at pre-IRET; nonzero stops
   before IRET. The provider owns the returned SS:SP and may change all roles. */
typedef uint16_t (*LmnInterruptBody)(void *context, uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus);

typedef struct LmnInterruptService {
    void *context;
    LmnInterruptBody execute;
    uint16_t code_segment;
    uint16_t instruction_pointer;
} LmnInterruptService;

typedef struct LmnInterruptResult {
    uint16_t status;
    uint16_t service_status;
} LmnInterruptResult;

enum LmnInterruptStatus {
    LMN_INTERRUPT_RETURNED = 0,
    LMN_INTERRUPT_UNBOUND_SERVICE = 1,
    LMN_INTERRUPT_PROVIDER_STOP = 2,
    LMN_INTERRUPT_CHANGED_IRET = 3
};

/* Consume a live IRET frame using returned SS:SP and preinstruction FLAGS. */
void lmn_interrupt_return(uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus);

/* Invoke a bound pre-IRET provider at the current CS:IP, then consume its live
   frame. Used after an actual far chain as well as software INT transport. */
LmnInterruptResult lmn_interrupt_invoke(uint8_t *memory, LmnRegs *registers,
    uint16_t return_cs, uint16_t resume_ip,
    const LmnInterruptService *service, const LmnRasterBus *bus);

/* Dispatch an actual software interrupt using the live IVT and stack frame.
   interrupt_number is the unsigned INT vector (for example, 0x33). */
LmnInterruptResult lmn_interrupt_service(uint8_t *memory, LmnRegs *registers,
    uint16_t interrupt_number, uint16_t resume_ip,
    const LmnInterruptService *service, const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_MOUSE_IRQ_BRIDGE_H
#define LEMMINGS_MOUSE_IRQ_BRIDGE_H

#include "vga_mirrors.h"

/* Opaque external body, entered at the currently bound INT62 target after the
   real FLAGS/CS/IP frame writes. It may change all registers and canonical RAM.
   Zero means stopped immediately before external IRET: the bridge consumes the
   actual frame through returned SS:SP. Nonzero is a provider stop and is retained
   as service_status, without consuming IRET. No external instruction or IRQ
   scheduling behavior is supplied by this interface. */
typedef uint16_t (*LmnMouseIrqInterrupt62)(
    void *context, uint8_t *memory, LmnRegs *registers,
    const LmnRasterBus *bus);

typedef struct LmnMouseIrqService {
    void *context;
    LmnMouseIrqInterrupt62 interrupt62;
    uint16_t code_segment;
    uint16_t instruction_pointer;
} LmnMouseIrqService;

typedef struct LmnMouseIrqBridgeResult {
    LmnRegs registers;
    uint16_t status;
    uint16_t service_status;
} LmnMouseIrqBridgeResult;

enum LmnMouseIrqBridgeStatus {
    LMN_MOUSE_IRQ_BRIDGE_READY = 0,
    LMN_MOUSE_IRQ_BRIDGE_UNBOUND_SERVICE = 1,
    LMN_MOUSE_IRQ_BRIDGE_EXTERNAL_STOP = 2,
    LMN_MOUSE_IRQ_BRIDGE_CHANGED_INTERRUPT_RETURN = 3,
    LMN_MOUSE_IRQ_BRIDGE_CHANGED_CHILD_RETURN = 4,
    LMN_MOUSE_IRQ_BRIDGE_CHILD_STOP = 5
};

/* Runs through the instruction immediately before the outer IRET at 0F9F. */
LmnMouseIrqBridgeResult lmn_mouse_irq_bridge_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnMouseIrqService *service, const LmnRasterBus *bus);

/* Copies the core result and consumes the actual live three-word outer IRET. */
LmnMouseIrqBridgeResult lmn_mouse_irq_bridge_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnMouseIrqService *service, const LmnRasterBus *bus);

#endif

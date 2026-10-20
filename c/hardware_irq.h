#ifndef LEMMINGS_HARDWARE_IRQ_H
#define LEMMINGS_HARDWARE_IRQ_H
#include "timer_tail.h"
#include "keyboard_input.h"
typedef struct LmnHardwareIrqServices {
    const LmnInputPollService *mouse;
    const LmnInterruptService *int60,*int61,*saved_int08;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    uint16_t code_segment;
} LmnHardwareIrqServices;
enum LmnHardwareIrqStatus {
    LMN_HARDWARE_IRQ_DELIVERED, LMN_HARDWARE_IRQ_DEFERRED,
    LMN_HARDWARE_IRQ_UNSUPPORTED, LMN_HARDWARE_IRQ_UNBOUND_VECTOR,
    LMN_HARDWARE_IRQ_HANDLER_STOP, LMN_HARDWARE_IRQ_CHANGED_RETURN
};
typedef struct LmnHardwareIrqResult {
    LmnRegs registers;
    uint16_t status,handler_status,child_status,service_status;
} LmnHardwareIrqResult;
/* Invoke from LmnForegroundPoll when the platform has a pending08/09.
   DEFERRED leaves state untouched; the platform retains its pending request.
   For IRQ09 the platform supplies its pending scan code through the real
   port60 provider (and owns its consumption). Read the live IVT after the
   real FLAGS/CS/IP pushes,
   clearing IF/TF after saving FLAGS. Only the declared relocated17C7/4C47/16D4
   bindings are implemented; unsupported vectors stop with the live frame.
   Adapters execute IRET; a changed return is reported, never repaired.
   No nested delivery or scheduling inside handlers/children is implied. */
LmnHardwareIrqResult lmn_deliver_hardware_irq(uint8_t *,const LmnRegs *,
    uint16_t number,const LmnHardwareIrqServices *);
#endif

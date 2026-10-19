#ifndef LEMMINGS_PORT_IO_H
#define LEMMINGS_PORT_IO_H

#include "aligned_read_mask.h"

enum LmnPortIoStatus {
    LMN_PORT_IO_READY = 0,
    LMN_PORT_IO_MISSING_PROVIDER = 1,
    LMN_PORT_IO_CHANGED_CHILD_RETURN = 2
};

typedef struct LmnPortIoResult {
    LmnRegs registers;
    uint16_t status;
} LmnPortIoResult;

/* Each core stops immediately before its literal RET. Providers are required
   only at the port instruction reached; missing callbacks stop at that site. */
LmnPortIoResult lmn_send_master_pic_eoi_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnPortIoResult lmn_send_master_pic_eoi_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

LmnPortIoResult lmn_measure_port201_axes_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnPortIoResult lmn_measure_port201_axes_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

LmnPortIoResult lmn_poll_port201_buttons_low_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnPortIoResult lmn_poll_port201_buttons_low_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

LmnPortIoResult lmn_poll_port201_buttons_high_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnPortIoResult lmn_poll_port201_buttons_high_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

/* Keyboard controller leaves17BE/17B4. Wait starts CX at zero: LOOPNE can
   consume65,536 samples. Command preserves AX via actual saves, sets IF. */
LmnPortIoResult lmn_wait_keyboard_controller_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnPortIoResult lmn_wait_keyboard_controller_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnPortIoResult lmn_send_keyboard_command_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnPortIoResult lmn_send_keyboard_command_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

#endif

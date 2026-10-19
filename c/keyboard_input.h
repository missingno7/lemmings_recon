#ifndef LEMMINGS_KEYBOARD_INPUT_H
#define LEMMINGS_KEYBOARD_INPUT_H
#include "port_io.h"
#include "interrupt_service.h"

typedef struct LmnKeyboardResult {
    LmnRegs registers;
    uint16_t status, child_status, service_status;
} LmnKeyboardResult;
enum LmnKeyboardStatus {
    LMN_KEYBOARD_READY=0, LMN_KEYBOARD_MISSING_INPUT=1,
    LMN_KEYBOARD_MISSING_OUTPUT=2, LMN_KEYBOARD_CHILD_STOP=3,
    LMN_KEYBOARD_CHANGED_CHILD_RETURN=4, LMN_KEYBOARD_UNBOUND_SERVICE=5,
    LMN_KEYBOARD_PROVIDER_STOP=6, LMN_KEYBOARD_CHANGED_INTERRUPT_RETURN=7
};
/* INT09 entry16D4, with actual hardware frame at live SS:SP.
   Core before17B3; adapter consumes hardware IRET. Relocated16D9 stays live. */
LmnKeyboardResult lmn_keyboard_irq_core(uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnKeyboardResult lmn_keyboard_irq_adapter(uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
/* DOS3509 query stores through returned DS; DOS2509 owns returned SS:SP.
   Core before1581; adapter executes actual nearRET. */
LmnKeyboardResult lmn_install_keyboard_core(uint8_t *memory, const LmnRegs *registers,
    const LmnInterruptService *dos, const LmnRasterBus *bus);
LmnKeyboardResult lmn_install_keyboard_adapter(uint8_t *memory, const LmnRegs *registers,
    const LmnInterruptService *dos, const LmnRasterBus *bus);

/* Reader4D1A: scans live83-byte state, advances repeat counts, XLATs through
  202E (overlapping the last binding). Core leaves either realRET unconsumed. */
LmnKeyboardResult lmn_read_keyboard_character_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBus *bus);
LmnKeyboardResult lmn_read_keyboard_character_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBus *bus);

/* Menu span4A9F..4AB4, no synthetic RET. Runs the real loop,
   actual child CALL frames and JMP4401 after accepting character31..34.
   The surrounding menu remains a separate untranslated continuation. */
LmnKeyboardResult lmn_select_input_scale(uint8_t *memory, const LmnRegs *registers,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

/* 43CE choice: repeated live latch/port201 reads, AL remains the inverted
   port byte or77; CL0/1/2, CH unchanged. Core before43ED; adapter actualRET. */
LmnKeyboardResult lmn_choose_input_controller_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
LmnKeyboardResult lmn_choose_input_controller_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
/* Scoped menu path4A4E..4ABC, including native text/swap, choice, calibration,
   and scale loop. Ends at untranslated4401 without an invented outer RET. */
LmnKeyboardResult lmn_select_input_controller(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports, const LmnRasterBus *bus);
/* Active input-menu domain4A2E..4AC4, including mouse availability gate,
   controller calibration and scale selection. Ends at original4401. */
LmnKeyboardResult lmn_select_input_mode(uint8_t *memory,const LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
#endif

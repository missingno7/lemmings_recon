#ifndef LEMMINGS_MAIN_MENU_H
#define LEMMINGS_MAIN_MENU_H
#include "menu_scroll.h"
#include "menu_animation.h"
#include "menu_cache.h"
#include "keyboard_input.h"
#include "display_setup.h"

typedef enum LmnMainMenuEntry {
    LMN_MAIN_MENU_REFRESH, LMN_MAIN_MENU_RELEASE,
    LMN_MAIN_MENU_FRAME, LMN_MAIN_MENU_KEYBOARD
} LmnMainMenuEntry;
typedef enum LmnMainMenuStatus {
    LMN_MAIN_MENU_CONTINUATION, LMN_MAIN_MENU_CHILD_STOP,
    LMN_MAIN_MENU_CHANGED_CHILD_RETURN,
    LMN_MAIN_MENU_UNBOUND_DOS,LMN_MAIN_MENU_DOS_STOP,LMN_MAIN_MENU_CHANGED_IRET
} LmnMainMenuStatus;
typedef struct LmnMainMenuResult {
    LmnRegs registers;
    uint16_t status,child_status;
} LmnMainMenuResult;
_Static_assert(sizeof(LmnMainMenuResult)==32u,"32-byte main-menu boundary");

/* Connected4401 refresh,4453 release wait,445B frame loop and4478 keyboard.
   No outer RET exists. Normal results keep the actual JMP destination04D0,
   4967,4A01 or454C. Canonical RAM,live CS table and actual child CALL frames
   own all state. Entry43F2 startup and destination bodies remain separate. */
LmnMainMenuResult lmn_run_main_menu(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_data_segment,enum LmnMainMenuEntry entry,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus);

/* 4AC5 availability/retry core stops before4B1B; adapter consumes that live
   caller word only on READY. DOS uses the shared actual INT21/IRET transport. */
LmnMainMenuResult lmn_check_menu_resource_core(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_data_segment,const LmnInterruptService *dos,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
LmnMainMenuResult lmn_check_menu_resource_adapter(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_data_segment,const LmnInterruptService *dos,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
/* 43F2's five real child calls, then fallthrough4401. BIOS retains the existing
   display-setup service ABI; DOS and timer-vector writes remain explicit. */
LmnMainMenuResult lmn_enter_main_menu(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_data_segment,const LmnVideoRestoreServices *video,
    const LmnInterruptService *dos,const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
/* 5042/51A2 over live DS buffers; core stops before the original RET.
   Decoder validity is returned in ZF, not the transport status. Failed decode
   may already have changed the special latch, selection and input buffer. */
LmnMainMenuResult lmn_encode_level_code_core(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus);
LmnMainMenuResult lmn_encode_level_code_adapter(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus);
LmnMainMenuResult lmn_decode_level_code_core(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus);
LmnMainMenuResult lmn_decode_level_code_adapter(uint8_t *memory,const LmnRegs *registers,const LmnRasterBus *bus);
#endif

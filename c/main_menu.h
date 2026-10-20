#ifndef LEMMINGS_MAIN_MENU_H
#define LEMMINGS_MAIN_MENU_H
#include "menu_scroll.h"
#include "menu_animation.h"
#include "menu_cache.h"
#include "keyboard_input.h"

typedef enum LmnMainMenuEntry {
    LMN_MAIN_MENU_REFRESH, LMN_MAIN_MENU_RELEASE,
    LMN_MAIN_MENU_FRAME, LMN_MAIN_MENU_KEYBOARD
} LmnMainMenuEntry;
typedef enum LmnMainMenuStatus {
    LMN_MAIN_MENU_CONTINUATION, LMN_MAIN_MENU_CHILD_STOP,
    LMN_MAIN_MENU_CHANGED_CHILD_RETURN
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
#endif

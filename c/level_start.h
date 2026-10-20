#ifndef LEMMINGS_LEVEL_START_H
#define LEMMINGS_LEVEL_START_H
#include "resource_select_full.h"
#include "level_briefing.h"

typedef enum LmnLevelStartEntry {
    LMN_LEVEL_START_FROM_MENU,LMN_LEVEL_START_COMMON
} LmnLevelStartEntry;
typedef enum LmnLevelStartStatus {
    LMN_LEVEL_START_CONTINUATION=0,LMN_LEVEL_START_UNBOUND_RESOURCES=1,
    LMN_LEVEL_START_RESOURCE_STOP=2,LMN_LEVEL_START_CHANGED_RETURN=3,
    LMN_LEVEL_START_BRIEFING_STOP=4,LMN_LEVEL_START_UNBOUND_BRIEFING=5
} LmnLevelStartStatus;
typedef struct LmnLevelStartServices {
    const LmnDatLoadSegments *segments;
    const LmnResourceSelectionFullServices *resources;
    const LmnBriefingServices *briefing;
    const LmnRasterBus *bus;
    /* Explicit relocated194B value, supplied by the platform/load binding. */
    uint16_t error_main_data_segment;
} LmnLevelStartServices;
typedef struct LmnLevelStartResult {
    LmnRegs registers;
    uint16_t status,child_status,detail;
} LmnLevelStartResult;
_Static_assert(sizeof(LmnLevelStartResult)==34u,"34-byte level-start boundary");

/* 454C/4551 through4565. Normal exit is JMP00FB; cancellation retains the
   briefing's JMP4401 and already consumed caller word. Neither is an outer
   RET. The selector bus covers its own instructions; its DAT/raw services
   retain ordinary-RAM, preserving DOS and intact internal-return contracts. */
LmnLevelStartResult lmn_start_selected_level(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_data_segment,LmnLevelStartEntry entry,const LmnLevelStartServices *services);
#endif

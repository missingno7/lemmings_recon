#ifndef LEMMINGS_LEVEL_BRIEFING_H
#define LEMMINGS_LEVEL_BRIEFING_H
#include "level_redraw.h"
#include "palette_transition.h"

typedef enum LmnBriefingStatus {
    LMN_BRIEFING_CONTINUATION=0,
    LMN_BRIEFING_CHILD_STOP=1,
    LMN_BRIEFING_CHANGED_RETURN=2,
    LMN_BRIEFING_DIVIDE_ERROR=3
} LmnBriefingStatus;
typedef struct LmnBriefingResult {
    LmnRegs registers;
    uint16_t status,child_status;
} LmnBriefingResult;
_Static_assert(sizeof(LmnBriefingResult)==32u,"32-byte briefing boundary");
typedef enum LmnBriefingHelper {
    LMN_BRIEFING_PERCENT,LMN_BRIEFING_CLEAR_LOWER,LMN_BRIEFING_BASE_PALETTE
} LmnBriefingHelper;
typedef struct LmnBriefingServices {
    const LmnLevelRedrawServices *redraw;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
} LmnBriefingServices;

/* 4B5C,4C17,5447 retain actual decimal/DAC frames and inherited clear/writer
   tails. Missing/changed child boundaries are returned without an outer RET. */
LmnBriefingResult lmn_briefing_helper_core(uint8_t *memory,const LmnRegs *registers,
    LmnBriefingHelper entry,const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
LmnBriefingResult lmn_briefing_helper_adapter(uint8_t *memory,const LmnRegs *registers,
    LmnBriefingHelper entry,const LmnRasterBytePorts *ports,const LmnRasterBus *bus);
/* 4566 formats live fields, composes redraw/preview/text/palettes and waits
   for finite platform input. Normal exit tail-enters fade/clear and leaves its
   RET live. Cancel consumes the actual saved word into AX and JMPs4401.
   DIV zero/byte overflow stops at459C as an explicit processor-fault seam. */
LmnBriefingResult lmn_show_level_briefing_core(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_data_segment,const LmnBriefingServices *services);
LmnBriefingResult lmn_show_level_briefing_adapter(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_data_segment,const LmnBriefingServices *services);
#endif

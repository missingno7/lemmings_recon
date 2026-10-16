#ifndef LEMMINGS_STATUS_ICONS_H
#define LEMMINGS_STATUS_ICONS_H

#include "special_blit.h"

enum LmnStatusIconsStatus {
    LMN_STATUS_ICONS_READY = 0
};

/* Live register roles at the two independent status-icon drawing leaves. */
typedef struct LmnStatusIconsCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnStatusIconsCall;

typedef struct LmnStatusIconsResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnStatusIconsResult;

/* Cores stop at the live near RET instructions; adapters consume the actual
   return words from canonical SS:SP after applying all returned registers. */
LmnStatusIconsResult lmn_draw_status_icon_outline_core(uint8_t *memory,
    const LmnStatusIconsCall *call,const LmnRasterBus *bus);
LmnStatusIconsResult lmn_restore_status_icon_core(uint8_t *memory,
    const LmnStatusIconsCall *call,const LmnRasterBus *bus);

uint16_t lmn_draw_status_icon_outline_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);
uint16_t lmn_restore_status_icon_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_STATUS_DISPLAY_H
#define LEMMINGS_STATUS_DISPLAY_H

#include "special_blit.h"

enum LmnStatusDisplayStatus {
    LMN_STATUS_DISPLAY_READY = 0,
    LMN_STATUS_DISPLAY_DIVIDE_ERROR = 1,
    LMN_STATUS_DISPLAY_CHANGED_CHILD_RETURN = 2,
    LMN_STATUS_DISPLAY_UNEXPECTED_CHILD_BOUNDARY = 3,
    LMN_STATUS_DISPLAY_CHILD_STOP = 4
};

enum { LMN_STATUS_DISPLAY_NO_CHILD_STATUS = 0xffffu };

/* Live register roles at StatusDisplayAfterMinimapViewport (3ACE). */
typedef struct LmnStatusDisplayCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnStatusDisplayCall;

typedef struct LmnStatusDisplayResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} LmnStatusDisplayResult;

/* The core stops before the outer RET at 3CDD, at a DIV exception boundary,
   or at an explicit child stop. Child CALL/RET words use canonical SS:SP. */
LmnStatusDisplayResult lmn_update_status_display_suffix_core(
    uint8_t *memory,const LmnStatusDisplayCall *call,
    const LmnRasterBus *bus);

/* Applies the core outputs and consumes the actual outer near-RET word only
   when status is READY. */
uint16_t lmn_update_status_display_suffix_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

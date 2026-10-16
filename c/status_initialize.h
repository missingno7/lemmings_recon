#ifndef LEMMINGS_STATUS_INITIALIZE_H
#define LEMMINGS_STATUS_INITIALIZE_H

#include "special_blit.h"

enum LmnStatusInitializeStatus {
    LMN_STATUS_INITIALIZE_READY = 0,
    LMN_STATUS_INITIALIZE_CHILD_STOP = 1,
    LMN_STATUS_INITIALIZE_CHANGED_CHILD_RETURN = 2
};

enum { LMN_STATUS_INITIALIZE_NO_CHILD_STATUS = 0xffffu };

/* Live register roles at InitializeStatusDisplay (39CE). */
typedef struct LmnStatusInitializeCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnStatusInitializeCall;

typedef struct LmnStatusInitializeResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} LmnStatusInitializeResult;

/* Composes the status-copy wrapper, ten count draws, decimal field and icon
   outline with their live CALL/RET frames. READY stops before the outer RET
   at 3AC7; child stops preserve their actual continuation and register state. */
LmnStatusInitializeResult lmn_initialize_status_display_core(
    uint8_t *memory,const LmnStatusInitializeCall *call,
    const LmnRasterBus *bus);

/* Applies all returned roles and consumes the actual outer SS:SP RET only
   when the core reaches READY. */
uint16_t lmn_initialize_status_display_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

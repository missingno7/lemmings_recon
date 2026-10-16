#ifndef LEMMINGS_ENTITY_DRAWING_H
#define LEMMINGS_ENTITY_DRAWING_H

#include "special_blit.h"

enum LmnEntityDrawingStatus {
    LMN_ENTITY_DRAWING_READY = 0,
    LMN_ENTITY_DRAWING_CHILD_STOP = 1,
    LMN_ENTITY_DRAWING_CHANGED_CHILD_RETURN = 2
};

/* Live register roles at DrawEntityRecords (3634). */
typedef struct LmnEntityDrawingCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityDrawingCall;

typedef struct LmnEntityDrawingResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} LmnEntityDrawingResult;

/* Executes the known 3634 body, excluding UNKNOWN 366F. READY stops before
   RET 368D for a zero bound or before the shared decimal RET at 4BBD. */
LmnEntityDrawingResult lmn_draw_entity_records_core(uint8_t *memory,
    const LmnEntityDrawingCall *call,const LmnRasterBus *bus);

/* Applies the logical result and consumes the live caller word only on READY. */
uint16_t lmn_draw_entity_records_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

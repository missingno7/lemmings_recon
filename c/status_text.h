#ifndef LEMMINGS_STATUS_TEXT_H
#define LEMMINGS_STATUS_TEXT_H

#include "special_blit.h"

enum LmnStatusTextStatus {
    LMN_STATUS_TEXT_READY = 0,
    LMN_STATUS_TEXT_CHANGED_CHILD_RETURN = 1,
    LMN_STATUS_TEXT_UNEXPECTED_GLYPH_RETURN = 2,
    LMN_STATUS_TEXT_CHILD_STOP = 3
};

/* Live register roles at DrawStatusText (417B). */
typedef struct LmnStatusTextCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnStatusTextCall;

typedef struct LmnStatusTextResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnStatusTextResult;

/* The core stops before the outer RET, or at a changed/unsupported glyph
   return. The adapter consumes only the actual outer near-return word. */
LmnStatusTextResult lmn_draw_status_text_core(uint8_t *memory,
    const LmnStatusTextCall *call,const LmnRasterBus *bus);
uint16_t lmn_draw_status_text_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_OBJECT_ANIMATION_H
#define LEMMINGS_OBJECT_ANIMATION_H

#include "special_blit.h"

enum LmnObjectAnimationStatus {
    LMN_OBJECT_ANIMATION_READY = 0
};

/* Live register roles at the gated 3944 entry or direct 7C0A tail. */
typedef struct LmnObjectAnimationCall {
    uint16_t value,object_flags,count,auxiliary_value;
    uint16_t graphics_cursor,definition_cursor,frame_stride;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnObjectAnimationCall;

typedef struct LmnObjectAnimationResult {
    uint16_t value,object_flags,count,auxiliary_value;
    uint16_t graphics_cursor,definition_cursor,frame_stride;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnObjectAnimationResult;

/* 3944 compares the live DS:002B gate and either stops before RET at 394E or
   jumps directly into the shared 32-record tail. */
LmnObjectAnimationResult lmn_advance_level_object_animations_core(
    uint8_t *memory,const LmnObjectAnimationCall *call,
    const LmnRasterBus *bus);

/* Direct 7C0A entry into the same tail, without adding a stack frame. */
LmnObjectAnimationResult lmn_advance_level_object_animation_records_core(
    uint8_t *memory,const LmnObjectAnimationCall *call,
    const LmnRasterBus *bus);

/* Each adapter applies all 13 roles and consumes the live near-RET word. */
uint16_t lmn_advance_level_object_animations_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);
uint16_t lmn_advance_level_object_animation_records_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

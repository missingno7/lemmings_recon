#ifndef LEMMINGS_VIEW_VISIBILITY_H
#define LEMMINGS_VIEW_VISIBILITY_H

#include "special_blit.h"

enum LmnViewVisibilityStatus {
    LMN_VIEW_VISIBILITY_READY = 0
};

/* Live 16-bit roles at the shared 410F body. The relocated immediate loaded
   into ES is explicit because it is independent of live CS and SS. */
typedef struct LmnViewVisibilityCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t runtime_stack_segment;
} LmnViewVisibilityCall;

typedef struct LmnViewVisibilityResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnViewVisibilityResult;

/* Rebuilds the shared visibility tail 410F..414D and stops before its RET. */
LmnViewVisibilityResult lmn_rebuild_view_visibility_map_core(
    uint8_t *memory,const LmnViewVisibilityCall *call,
    const LmnRasterBus *bus);

/* Applies live roles and executes the actual RET at 414E when READY. */
uint16_t lmn_rebuild_view_visibility_map_adapter(uint8_t *memory,
    LmnRegs *registers,uint16_t runtime_stack_segment,
    const LmnRasterBus *bus);

#endif

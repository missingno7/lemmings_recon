#ifndef LEMMINGS_STATUS_COPY_H
#define LEMMINGS_STATUS_COPY_H

#include "special_blit.h"

enum LmnStatusCopyStatus {
    LMN_STATUS_COPY_READY = 0,
    LMN_STATUS_COPY_CHANGED_CHILD_RETURN = 1
};

/* Live register roles at either status-region copy entry. */
typedef struct LmnStatusCopyCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnStatusCopyCall;

typedef struct LmnStatusCopyResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnStatusCopyResult;

/* The direct core stops before the near RET at 7629. */
LmnStatusCopyResult lmn_copy_status_region_to_vga_core(uint8_t *memory,
    const LmnStatusCopyCall *call,const LmnRasterBus *bus);

/* The wrapper CALLs the direct leaf once, checks the live return at 75FA,
   then falls through into a second leaf invocation without another frame. */
LmnStatusCopyResult lmn_copy_status_region_to_both_origins_core(
    uint8_t *memory,const LmnStatusCopyCall *call,const LmnRasterBus *bus);

/* Adapters consume the actual final near-RET word only for READY results. */
uint16_t lmn_copy_status_region_to_vga_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);
uint16_t lmn_copy_status_region_to_both_origins_adapter(uint8_t *memory,
    LmnRegs *registers,const LmnRasterBus *bus);

#endif

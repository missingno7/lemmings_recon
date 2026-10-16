#ifndef LEMMINGS_MINIMAP_STATUS_H
#define LEMMINGS_MINIMAP_STATUS_H

#include "special_blit.h"

enum LmnMinimapStatusCode {
    LMN_MINIMAP_STATUS_READY = 0,
    LMN_MINIMAP_STATUS_CHILD_BOUNDARY = 1,
    LMN_MINIMAP_STATUS_CHANGED_CALL_RETURN = 2
};

enum { LMN_MINIMAP_STATUS_NO_CHILD_STATUS = 0xffffu };

/* Live register roles at the 3AC8 two-call prefix. */
typedef struct LmnMinimapStatusCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnMinimapStatusCall;

typedef struct LmnMinimapStatusResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status,child_entry,child_status;
} LmnMinimapStatusResult;

/* Executes only the 3AC8..3ACE two-CALL prefix, not the rest of the status
   display. The nonnull VGA raster bus must provide out_word (required by the
   column) and shared byte callbacks for the device state used by both children.
   READY stops before the separately implemented status suffix at 3ACE; neither the core
   nor adapter adds RET. */
LmnMinimapStatusResult lmn_update_minimap_status_core(uint8_t *memory,
    const LmnMinimapStatusCall *call,const LmnRasterBus *bus);

/* Applies the result and IP without consuming an outer return word. */
uint16_t lmn_update_minimap_status_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_ENTITY_SELECT_H
#define LEMMINGS_ENTITY_SELECT_H

#include "special_blit.h"

enum LmnEntitySelectStatus {
    LMN_ENTITY_SELECT_READY=0,
    LMN_ENTITY_SELECT_CHANGED_FORMATTER_RETURN=1
};

/* Live register roles at SelectEntityCandidate (3CDE). */
typedef struct LmnEntitySelectCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntitySelectCall;

typedef struct LmnEntitySelectResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntitySelectResult;

/* Executes 3CDE..3E6E, composing the live 4B68 CALL/RET. READY stops before
   the actual outer RET at 3E62; changed formatter targets stop at that target. */
LmnEntitySelectResult lmn_select_entity_core(uint8_t *memory,
    const LmnEntitySelectCall *call,const LmnRasterBus *bus);

/* Applies the result and executes the live outer RET only for READY. */
uint16_t lmn_select_entity_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

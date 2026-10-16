#ifndef LEMMINGS_ENTITY_CREATE_H
#define LEMMINGS_ENTITY_CREATE_H

#include "special_blit.h"

enum LmnEntityCreateStatus {
    LMN_ENTITY_CREATE_READY=0
};

/* Logical live register roles at CreateEntityRecordIfDue (30A6). */
typedef struct LmnEntityCreateCall {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
} LmnEntityCreateCall;

typedef struct LmnEntityCreateResult {
    uint16_t value,map_cursor,count,auxiliary_value;
    uint16_t record_cursor,object_cursor,candidate_y;
    uint16_t code_segment,data_segment,extra_segment;
    uint16_t stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnEntityCreateResult;

/* Executes the known 30A6..314E body and stops immediately before RET 314F.
   All globals, record bytes and stack words remain in canonical memory. */
LmnEntityCreateResult lmn_create_entity_record_core(uint8_t *memory,
    const LmnEntityCreateCall *call,const LmnRasterBus *bus);

/* Applies the logical result and executes the actual outer RET word at SS:SP. */
uint16_t lmn_create_entity_record_adapter(uint8_t *memory,LmnRegs *registers,
    const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_ENTITY_CADENCE_H
#define LEMMINGS_ENTITY_CADENCE_H

#include "entity_finish.h"
#include "coordinate_pixel.h"

enum LmnEntityCadenceEntry {
    LMN_ENTITY_CADENCE_STATE_0001 = 0,
    LMN_ENTITY_CADENCE_STATE_1000 = 1,
    LMN_ENTITY_CADENCE_STATE_2000 = 2,
    LMN_ENTITY_CADENCE_STATE_4000 = 3
};

enum LmnEntityCadenceStatus {
    LMN_ENTITY_CADENCE_READY = 0,
    LMN_ENTITY_CADENCE_CHANGED_PIXEL_RETURN = 1,
    LMN_ENTITY_CADENCE_INVALID_ENTRY = 2
};

/* Logical live state at one of the four direct JMP entry points. These names
   mirror the neighboring entity-state APIs; the record itself remains in
   canonical memory at data_segment:record_cursor. */
typedef struct LmnEntityCadenceCall {
    uint16_t entry;
    uint16_t value, map_cursor, count, auxiliary_value;
    uint16_t record_cursor, object_cursor, candidate_y;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnEntityCadenceCall;

typedef struct LmnEntityCadenceResult {
    uint16_t value, map_cursor, count, auxiliary_value;
    uint16_t record_cursor, object_cursor, candidate_y;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status;
} LmnEntityCadenceResult;

/* Executes one direct state entry and returns at 1FEB or a changed
   coordinate-helper return. The 20E2 expiry tail is composed internally.
   CALL/RET/PUSH/POP traffic uses live SS memory. */
LmnEntityCadenceResult lmn_entity_cadence_core(
    uint8_t *memory, const LmnEntityCadenceCall *call,
    const LmnRasterBus *bus);

/* Register adapter for original-code differential boundaries. */
uint16_t lmn_entity_cadence_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnEntityCadenceEntry entry, const LmnRasterBus *bus);

#endif

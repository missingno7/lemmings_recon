#ifndef LEMMINGS_OBJECT_COORDINATES_H
#define LEMMINGS_OBJECT_COORDINATES_H
#include <stdint.h>
#include "regs.h"

/* Logical boundary state for the 389F type-one coordinate collector. */
typedef struct LmnObjectCoordinatesCall {
    uint16_t data_segment;
    uint16_t flags;
} LmnObjectCoordinatesCall;

typedef struct LmnObjectCoordinatesResult {
    uint16_t value;              /* AX */
    uint16_t count;              /* CX */
    uint16_t definition_cursor;   /* SI */
    uint16_t output_cursor;       /* BX */
    uint16_t selected_count;      /* BP */
    uint16_t flags;
} LmnObjectCoordinatesResult;

/* Reads the 32 live eight-byte definitions at DS:0FEB and writes coordinate
   pairs at DS:0E98. The core takes only the live data segment and entry flags;
   stack and register effects belong to the boundary adapter. */
LmnObjectCoordinatesResult lmn_collect_type_one_object_coordinates_core(
    uint8_t *memory, const LmnObjectCoordinatesCall *call);
void lmn_collect_type_one_object_coordinates_adapter(uint8_t *memory, LmnRegs *r);

#endif

#ifndef LEMMINGS_TERRAIN_STREAM_H
#define LEMMINGS_TERRAIN_STREAM_H

#include "terrain_drawing.h"

typedef struct LmnTerrainCommand {
    uint16_t packed_horizontal, packed_vertical, command_cursor;
    uint16_t flags, end_of_stream;
} LmnTerrainCommand;

typedef struct LmnTerrainStreamCall {
    uint16_t data_segment, game_data_segment, code_segment;
    uint16_t stack_segment, stack_offset, packed_counts, width_state;
    uint16_t mask_cursor, control, output_segment, flags;
} LmnTerrainStreamCall;

typedef struct LmnTerrainStreamResult {
    LmnDrawingSourceResult state;
    uint16_t data_segment, output_segment, code_segment;
    uint16_t stopped, changed_return;
} LmnTerrainStreamResult;

/* Reads the four packed command bytes as four separate DS:SI byte loads.
   Each effective offset wraps at16 bits before real-mode physical wrapping. */
LmnTerrainCommand lmn_read_terrain_command_core(
    uint8_t *memory, uint16_t data_segment, uint16_t command_cursor,
    uint16_t flags, const LmnRasterBus *bus);
void lmn_read_terrain_command_adapter(
    uint8_t *memory, LmnRegs *regs, unsigned redraw,
    const LmnRasterBus *bus);

/* Executes the MOV SI initialization and command loop through its sentinel
   exit, or stops at an unsupported/changed child return. A normal sentinel
   exit remains inside36B6/394F; it never consumes the caller's RET. */
LmnTerrainStreamResult lmn_draw_terrain_stream_core(
    uint8_t *memory, const LmnTerrainStreamCall *call, unsigned redraw,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports);
void lmn_draw_terrain_stream_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment,
    unsigned redraw, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports);

#endif

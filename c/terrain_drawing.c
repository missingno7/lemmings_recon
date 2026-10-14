#include "terrain_drawing.h"
#include "lemmings_sym.h"

#ifndef TERRAIN_MUTATION
#define TERRAIN_MUTATION 0
#endif

#define MEMORY_MASK 0xfffffu
#define ARITHMETIC_FLAGS 0x08d5u

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & MEMORY_MASK;
}

static uint8_t read_byte(uint8_t *memory, uint32_t address, uint16_t flags,
                         const LmnRasterBus *bus) {
    address &= MEMORY_MASK;
    return bus && bus->read_byte
        ? bus->read_byte(bus->context, memory, address, flags)
        : memory[address];
}

static void write_byte(uint8_t *memory, uint32_t address, uint8_t value,
                       uint16_t flags, const LmnRasterBus *bus) {
    address &= MEMORY_MASK;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static uint16_t read_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                          uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, address, flags, bus);
    uint8_t high = read_byte(memory, (address + 1u) & MEMORY_MASK, flags, bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, address, (uint8_t)value, flags, bus);
    write_byte(memory, (address + 1u) & MEMORY_MASK,
               (uint8_t)(value >> 8), flags, bus);
}

static uint16_t pop_word(uint8_t *memory, uint16_t segment,
                         uint16_t *stack_offset, uint16_t flags,
                         const LmnRasterBus *bus) {
    uint16_t value = read_word(memory, segment, *stack_offset, flags, bus);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

static void push_word(uint8_t *memory, uint16_t segment,
                      uint16_t *stack_offset, uint16_t value,
                      uint16_t flags, const LmnRasterBus *bus) {
    *stack_offset = (uint16_t)(*stack_offset - 2u);
    write_word(memory, segment, *stack_offset, value, flags, bus);
}

static unsigned even_parity(uint8_t value) {
    unsigned parity = 0;
    for (unsigned bit = 0; bit != 8; ++bit)
        parity ^= (value >> bit) & 1u;
    return parity == 0;
}

static uint16_t szp16(uint16_t value) {
    return (uint16_t)((even_parity((uint8_t)value) ? 0x04u : 0u) |
                      (value == 0 ? 0x40u : 0u) |
                      (value & 0x8000u ? 0x80u : 0u));
}

static uint16_t logic_flags(uint16_t flags, uint16_t value) {
    /* AF is undefined for logical operations; use a cleared representative. */
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | szp16(value));
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right,
                            uint16_t result) {
    uint32_t sum = (uint32_t)left + right;
    uint16_t changed = szp16(result);
    if (sum > 0xffffu) changed |= 0x01u;
    if ((left ^ right ^ result) & 0x10u) changed |= 0x10u;
    if ((~(left ^ right) & (left ^ result)) & 0x8000u)
        changed |= 0x800u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

static uint16_t sub16_flags(uint16_t flags, uint16_t left, uint16_t right,
                            uint16_t result) {
    uint16_t changed = szp16(result);
    if (left < right) changed |= 0x01u;
    if ((left ^ right ^ result) & 0x10u) changed |= 0x10u;
    if (((left ^ right) & (left ^ result)) & 0x8000u)
        changed |= 0x800u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

static uint16_t shift_right_flags(uint16_t flags, uint16_t original,
                                  uint16_t result, unsigned count) {
    uint16_t changed = szp16(result);
    if ((original >> (count - 1u)) & 1u) changed |= 0x01u;
    if (count == 1u && (original & 0x8000u)) changed |= 0x800u;
    /* For counts above one OF is undefined; leave it clear in the model. */
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

static uint16_t rotate_left_carry_flags(uint16_t flags, uint16_t result,
                                        unsigned carry) {
    uint16_t changed = 0;
    if (carry) changed |= 0x01u;
    if (((result >> 15) ^ carry) & 1u) changed |= 0x800u;
    /* RCL changes only CF and OF; it leaves the other status flags alone. */
    return (uint16_t)((flags & ~0x0801u) | changed);
}

static uint16_t sar7(uint16_t value) {
    uint16_t shifted = (uint16_t)(value >> 7);
    if (value & 0x8000u) shifted |= 0xfe00u;
    return shifted;
}

LmnPlanarBitmapCall lmn_prepare_terrain_piece_core(
    uint8_t *memory, const LmnTerrainPieceCall *call,
    const LmnRasterBus *bus) {
    uint16_t flags = call->flags;
    uint16_t stack_offset = call->stack_offset;
    uint16_t dx = call->packed_horizontal;
    uint16_t ax = call->packed_horizontal;
    uint16_t bx = call->packed_vertical;
    uint16_t control, left, top, packed_height, width, source, mask;
    uint16_t record_index, record_offset, product;
    uint16_t record_ds_offset;

    /* 7C67 PUSH SI. The later POP SI deliberately reads this live word. */
    push_word(memory, call->stack_segment, &stack_offset,
              call->source_cursor, flags, bus);

    /* 7C68..7C79: copy AX, derive the high packed control bits, then test. */
    dx = (uint16_t)(dx >> 7);
    flags = shift_right_flags(flags, call->packed_horizontal, dx, 7);
    dx &= 0x00c0u;
    flags = logic_flags(flags, dx);
    dx |= 0x000fu;
    flags = logic_flags(flags, dx);
    flags = logic_flags(flags, (uint16_t)(dx & 0x0040u)); /* TEST DX,40h */
    if (dx & 0x0040u) {
#if TERRAIN_MUTATION != 3
        dx |= 0x0f00u;
        flags = logic_flags(flags, dx);
#endif
    }

    /* TEST cleared CF, so RCL shifts AX left with a zero low bit. */
    {
        unsigned carry = (ax >> 15) & 1u;
        ax = (uint16_t)(ax << 1);
        flags = rotate_left_carry_flags(flags, ax, carry);
        if (carry) {
            dx |= 0x8000u;
            flags = logic_flags(flags, dx);
        }
    }
    {
        uint16_t before = ax;
        ax = (uint16_t)(ax >> 1);
        flags = shift_right_flags(flags, before, ax, 1);
    }

    control = dx;
    dx = call->packed_vertical;
    record_index = (uint16_t)(dx & 0x003fu);
#if TERRAIN_MUTATION == 1
    record_index = (uint16_t)(dx & 0x007fu);
#endif
    dx = record_index;
    flags = logic_flags(flags, dx); /* AND DX,3Fh */

    top = sar7(bx);
    flags = shift_right_flags(flags, bx, top, 7);
#if TERRAIN_MUTATION == 2
    top = (uint16_t)(bx >> 7);
#endif
    {
        uint16_t before = top;
        top = (uint16_t)(top - 4u);
        flags = sub16_flags(flags, before, 4u, top);
    }
    left = (uint16_t)(ax & 0x1fffu);
    flags = logic_flags(flags, left);

    /* PUSH BX; PUSH AX, then live record loads, POP AX; POP BX. */
    push_word(memory, call->stack_segment, &stack_offset, top, flags, bus);
    push_word(memory, call->stack_segment, &stack_offset, left, flags, bus);

    product = (uint16_t)(8u * record_index);
    dx = 0;
    /* MUL DX defines only CF/OF here; the following ADD replaces status flags. */
    flags &= (uint16_t)~0x0801u;
    record_offset = (uint16_t)(product + SEG09A9_GroundTerrainRecordWidthByte);
    flags = add16_flags(flags, product,
                        SEG09A9_GroundTerrainGraphicsRecords, record_offset);
    record_ds_offset = record_offset;

    /* BX is the live record pointer. Reads stay ordered as in7CA4..7CB0. */
    width = read_byte(memory, physical(call->data_segment, record_ds_offset),
                      flags, bus);
    dx = (uint16_t)((dx & 0xff00u) | width);
    dx &= 0x00ffu;
    flags = logic_flags(flags, 0); /* XOR DH,DH sets flags from the zero byte. */
    packed_height = read_byte(memory,
        physical(call->data_segment, (uint16_t)(record_ds_offset +
            SEG09A9_GroundTerrainRecordHeightByte -
            SEG09A9_GroundTerrainRecordWidthByte)),
        flags, bus);
    source = read_word(memory, call->data_segment,
        (uint16_t)(record_ds_offset +
            SEG09A9_GroundTerrainRecordSourceOffset -
            SEG09A9_GroundTerrainRecordWidthByte), flags, bus);
    mask = read_word(memory, call->data_segment,
        (uint16_t)(record_ds_offset +
            SEG09A9_GroundTerrainRecordMaskOffset -
            SEG09A9_GroundTerrainRecordWidthByte), flags, bus);

    left = pop_word(memory, call->stack_segment, &stack_offset, flags, bus);
    top = pop_word(memory, call->stack_segment, &stack_offset, flags, bus);
    packed_height = (uint16_t)(0x0400u | packed_height);

    return (LmnPlanarBitmapCall){call->data_segment,
        call->game_data_segment, call->stack_segment, stack_offset,
        left, top, packed_height, width, source, mask, control,
        call->output_segment, flags};
}

void lmn_prepare_terrain_piece_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment,
    const LmnRasterBus *bus) {
    LmnTerrainPieceCall call = {regs->ds, game_data_segment, regs->ss,
        regs->sp, regs->cs, regs->ax, regs->bx, regs->si, regs->es,
        regs->flags};
    LmnPlanarBitmapCall prepared =
        lmn_prepare_terrain_piece_core(memory, &call, bus);
    regs->ax = prepared.left;
    regs->bx = prepared.top;
    regs->cx = prepared.packed_height;
    regs->dx = prepared.width;
    regs->si = prepared.source_cursor;
    regs->di = prepared.destination_cursor;
    regs->bp = prepared.control;
    regs->sp = prepared.stack_offset;
    regs->flags = prepared.flags;
    regs->ip = CS_TerrainPieceBitmapCall;
}

LmnTerrainPieceResult lmn_draw_terrain_piece_core(
    uint8_t *memory, const LmnTerrainPieceCall *call,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnTerrainPieceResult result = {0};
    LmnPlanarBitmapCall prepared =
        lmn_prepare_terrain_piece_core(memory, call, bus);
    uint16_t stack_offset = prepared.stack_offset;
    uint16_t returned_ip, returned_cs;

    result.code_segment = call->code_segment;
    /* The far CALL pushes the current CS first, then its7CBA return offset. */
    push_word(memory, call->stack_segment, &stack_offset,
              call->code_segment, prepared.flags, bus);
    push_word(memory, call->stack_segment, &stack_offset,
              CS_TerrainPieceAfterBitmap, prepared.flags, bus);
    prepared.stack_offset = stack_offset;
    result.drawing = lmn_draw_planar_bitmap_core(memory, &prepared, bus, ports);
    if (!result.drawing.body_returned)
        return result;

    stack_offset = result.drawing.plan.state.stack_offset;
    returned_ip = pop_word(memory, call->stack_segment, &stack_offset,
                           result.drawing.plan.state.flags, bus);
    returned_cs = pop_word(memory, call->stack_segment, &stack_offset,
                           result.drawing.plan.state.flags, bus);
#if TERRAIN_MUTATION == 4
    /* Parent-only fault: hide a live far-return overwrite after reading it. */
    returned_ip = CS_TerrainPieceAfterBitmap;
    returned_cs = call->code_segment;
#endif
    result.code_segment = returned_cs;
    result.drawing.plan.state.stack_offset = stack_offset;
    if (returned_ip != CS_TerrainPieceAfterBitmap ||
        returned_cs != call->code_segment) {
        result.drawing.plan.state.continuation = returned_ip;
        result.changed_far_return = 1;
        return result;
    }

    result.drawing.plan.state.source_cursor =
        pop_word(memory, call->stack_segment, &stack_offset,
                 result.drawing.plan.state.flags, bus);
#if TERRAIN_MUTATION == 5
    result.drawing.plan.state.source_cursor = call->source_cursor;
#endif
    result.drawing.plan.state.stack_offset = stack_offset;
    result.drawing.plan.state.continuation = CS_TerrainPieceReturn;
    result.ready_to_return = 1;
    return result;
}

void lmn_draw_terrain_piece_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnTerrainPieceCall call = {regs->ds, game_data_segment, regs->ss,
        regs->sp, regs->cs, regs->ax, regs->bx, regs->si, regs->es,
        regs->flags};
    LmnTerrainPieceResult result =
        lmn_draw_terrain_piece_core(memory, &call, bus, ports);
    LmnDrawingSourceResult *state = &result.drawing.plan.state;
    regs->ax = state->work_value;
    regs->bx = state->second_source_cursor;
    regs->cx = state->packed_counts;
    regs->dx = state->width_state;
    regs->si = state->source_cursor;
    regs->di = state->destination_cursor;
    regs->bp = state->control;
    regs->sp = state->stack_offset;
    regs->ds = result.drawing.source_segment;
    regs->es = result.drawing.output_segment;
    regs->cs = result.code_segment;
    regs->ip = state->continuation;
    regs->flags = state->flags;
    if (result.ready_to_return) {
        regs->ip = pop_word(memory, regs->ss, &regs->sp, regs->flags, bus);
    }
}

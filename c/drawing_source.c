#include "drawing_source.h"
#include "lemmings_sym.h"

#ifndef SOURCE_MUTATION
#define SOURCE_MUTATION 0
#endif

#define MEMORY_MASK 0xfffffu
#define ARITHMETIC_FLAGS 0x08d5u

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & MEMORY_MASK;
}

static uint8_t read_byte(uint8_t *memory, uint32_t address,
                         uint16_t flags, const LmnRasterBus *bus) {
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
    uint8_t high = read_byte(memory, (address + 1u) & MEMORY_MASK,
                             flags, bus);
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

static unsigned parity_even(uint8_t value) {
    unsigned parity = 0;
    for (unsigned bit = 0; bit != 8; ++bit)
        parity ^= (value >> bit) & 1u;
    return parity == 0;
}

static uint16_t szp16(uint16_t value) {
    return (uint16_t)((parity_even((uint8_t)value) ? 0x04u : 0u) |
                      (value == 0 ? 0x40u : 0u) |
                      (value & 0x8000u ? 0x80u : 0u));
}

static uint16_t test16(uint16_t flags, uint16_t value) {
    /* AF is undefined for TEST. Its representative value is immaterial. */
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | szp16(value));
}

static uint16_t add16_flags(uint16_t flags, uint16_t left,
                            uint16_t right, uint16_t result) {
    uint32_t sum = (uint32_t)left + right;
    uint16_t changed = szp16(result);
    if (sum > 0xffffu) changed |= 0x01u;
    if ((left ^ right ^ result) & 0x10u) changed |= 0x10u;
    if ((~(left ^ right) & (left ^ result)) & 0x8000u)
        changed |= 0x800u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

static uint16_t sub16_flags(uint16_t flags, uint16_t left,
                            uint16_t right, uint16_t result) {
    uint16_t changed = szp16(result);
    if (left < right) changed |= 0x01u;
    if ((left ^ right ^ result) & 0x10u) changed |= 0x10u;
    if (((left ^ right) & (left ^ result)) & 0x8000u)
        changed |= 0x800u;
    return (uint16_t)((flags & ~ARITHMETIC_FLAGS) | changed);
}

static uint16_t pop_word(uint8_t *memory, uint16_t segment,
                         uint16_t *stack_offset, uint16_t flags,
                         const LmnRasterBus *bus) {
    uint16_t value = read_word(memory, segment, *stack_offset, flags, bus);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

static unsigned is_masked(uint16_t entry) {
    return entry == CS_PrepareShiftedMaskedPlanarRows ||
           entry == CS_PrepareAlignedMaskedPlanarRows;
}

static uint16_t dispatch(uint16_t entry, uint16_t control) {
    unsigned shifted = entry == CS_PrepareShiftedMaskedPlanarRows;
    if (control & 0x4000u)
        return shifted ? CS_PlanarShiftedMasked4000Body
                       : CS_PlanarAlignedMasked4000Body;
    if (control & 0x8000u)
        return shifted ? CS_PlanarShiftedMasked8000Body
                       : CS_PlanarAlignedMasked8000Body;
    if (control & 0x0020u)
        return shifted ? CS_PlanarShiftedMasked20Body
                       : CS_PlanarAlignedMasked20Body;
    if (control & 0x0040u)
        return shifted ? CS_PlanarShiftedMasked40Body
                       : CS_PlanarAlignedMasked40Body;
    return shifted ? CS_PlanarShiftedMaskedDefaultBody
                   : CS_PlanarAlignedMaskedDefaultBody;
}

LmnDrawingSourceResult lmn_prepare_planar_source_rows_core(
    uint8_t *memory, const LmnDrawingSourceCall *call,
    const LmnRasterBus *bus) {
    LmnDrawingSourceResult state = {
        call->work_value, call->second_source_cursor, call->packed_counts,
        call->width_state, call->source_cursor, call->destination_cursor,
        call->control, call->stack_offset, call->flags, call->entry
    };
    uint16_t working_bp;

    if (call->entry != CS_PrepareShiftedMaskedPlanarRows &&
        call->entry != CS_PrepareShiftedOpaquePlanarRows &&
        call->entry != CS_PrepareAlignedMaskedPlanarRows &&
        call->entry != CS_PrepareAlignedOpaquePlanarRows)
        return state;

    /* MOV AX,BP; PUSH BP; MOV BP,[DS:66FC]. PUSH is live: its write can
       replace the horizontal-skip word or any later source operand. */
    state.work_value = state.control;
    state.stack_offset = (uint16_t)(state.stack_offset - 2u);
    write_word(memory, call->stack_segment, state.stack_offset,
               state.control, state.flags, bus);
    working_bp = read_word(memory, call->data_segment,
                           SEG09A9_DrawingHorizontalSkipBytes,
                           state.flags, bus);

    state.flags = test16(state.flags,
                         (uint16_t)(state.work_value & 0x0080u));
    if (state.work_value & 0x0080u) {
        uint16_t extent = read_word(memory, call->data_segment,
                                    SEG09A9_DrawingSourcePlaneExtent,
                                    state.flags, bus);
        uint16_t vertical = read_word(memory, call->data_segment,
                                      SEG09A9_DrawingVerticalSkipBytes,
                                      state.flags, bus);
        uint16_t old = extent;
        extent = (uint16_t)(extent - vertical);
        state.flags = sub16_flags(state.flags, old, vertical, extent);

        vertical = read_word(memory, call->data_segment,
                             SEG09A9_DrawingVerticalSkipBytes,
                             state.flags, bus);
#if SOURCE_MUTATION != 2
        old = extent;
        extent = (uint16_t)(extent - vertical);
        state.flags = sub16_flags(state.flags, old, vertical, extent);
#endif

        old = state.second_source_cursor;
        state.second_source_cursor =
            (uint16_t)(state.second_source_cursor + extent);
        state.flags = add16_flags(state.flags, old, extent,
                                  state.second_source_cursor);
        old = state.source_cursor;
        state.source_cursor = (uint16_t)(state.source_cursor + extent);
        state.flags = add16_flags(state.flags, old, extent,
                                  state.source_cursor);

        state.work_value = read_word(memory, call->data_segment,
                                     SEG09A9_DrawingSourcePitchBytes,
                                     state.flags, bus);
        old = state.second_source_cursor;
        state.second_source_cursor = (uint16_t)(old - state.work_value);
        state.flags = sub16_flags(state.flags, old, state.work_value,
                                  state.second_source_cursor);
        old = state.source_cursor;
#if SOURCE_MUTATION != 3
        state.source_cursor = (uint16_t)(old - state.work_value);
        state.flags = sub16_flags(state.flags, old, state.work_value,
                                  state.source_cursor);
#endif
        old = working_bp;
        working_bp = (uint16_t)(working_bp - state.work_value);
        state.flags = sub16_flags(state.flags, old, state.work_value,
                                  working_bp);
        old = working_bp;
        working_bp = (uint16_t)(working_bp - state.work_value);
        state.flags = sub16_flags(state.flags, old, state.work_value,
                                  working_bp);
    }

    write_word(memory, call->data_segment,
               SEG09A9_DrawingSourceRowAdvance, working_bp,
               state.flags, bus);
    state.control = pop_word(memory, call->stack_segment,
                             &state.stack_offset, state.flags, bus);
#if SOURCE_MUTATION == 1
    state.control = call->control;
#endif

    if (is_masked(call->entry)) {
        state.flags = test16(state.flags,
                             (uint16_t)(state.control & 0x4000u));
        if (state.control & 0x4000u) {
            state.continuation = dispatch(call->entry, state.control);
            return state;
        }
        state.flags = test16(state.flags,
                             (uint16_t)(state.control & 0x8000u));
        if (state.control & 0x8000u) {
            state.continuation = dispatch(call->entry, state.control);
            return state;
        }
        state.flags = test16(state.flags,
                             (uint16_t)(state.control & 0x0020u));
        if (state.control & 0x0020u) {
            state.continuation = dispatch(call->entry, state.control);
            return state;
        }
        state.flags = test16(state.flags,
                             (uint16_t)(state.control & 0x0040u));
        if (state.control & 0x0040u) {
            state.continuation = dispatch(call->entry, state.control);
            return state;
        }
    }

    switch (call->entry) {
    case CS_PrepareShiftedMaskedPlanarRows:
        state.continuation = CS_PlanarShiftedMaskedDefaultBody; break;
    case CS_PrepareShiftedOpaquePlanarRows:
        state.continuation = CS_PlanarShiftedOpaqueBody; break;
    case CS_PrepareAlignedMaskedPlanarRows:
        state.continuation = CS_PlanarAlignedMaskedDefaultBody; break;
    default:
        state.continuation = CS_PlanarAlignedOpaqueBody; break;
    }
    return state;
}

void lmn_prepare_planar_source_rows_adapter(
    uint8_t *memory, LmnRegs *regs, const LmnRasterBus *bus) {
    LmnDrawingSourceCall call = {
        regs->ds, regs->ss, regs->sp,
        regs->ax, regs->bx, regs->cx, regs->dx,
        regs->si, regs->di, regs->bp, regs->flags, regs->ip
    };
    LmnDrawingSourceResult state =
        lmn_prepare_planar_source_rows_core(memory, &call, bus);
    regs->ax = state.work_value;
    regs->bx = state.second_source_cursor;
    regs->cx = state.packed_counts;
    regs->dx = state.width_state;
    regs->si = state.source_cursor;
    regs->di = state.destination_cursor;
    regs->bp = state.control;
    regs->sp = state.stack_offset;
    regs->flags = state.flags;
    regs->ip = state.continuation;
}

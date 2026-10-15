#include "object_drawing.h"
#include "lemmings_sym.h"

#ifndef OBJECT_DRAWING_MUTATION
#define OBJECT_DRAWING_MUTATION 0
#endif

enum {
    CF = 0x0001u, PF = 0x0004u, AF = 0x0010u, ZF = 0x0040u,
    SF = 0x0080u, OF = 0x0800u,
    ARITHMETIC_FLAGS = CF | PF | AF | ZF | SF | OF,
    LOGIC_DEFINED_FLAGS = CF | PF | ZF | SF | OF
};

/* Repeated-record offsets are derived from ledger-owned first-record anchors. */
enum {
    OBJECT_DEFINITION_X_HIGH = SEG09A9_FirstObjectDefinitionX - SEG09A9_LevelObjectDefinitions,
    OBJECT_DEFINITION_X_LOW = OBJECT_DEFINITION_X_HIGH + 1u,
    OBJECT_DEFINITION_Y_HIGH = SEG09A9_FirstObjectDefinitionY - SEG09A9_LevelObjectDefinitions,
    OBJECT_DEFINITION_Y_LOW = OBJECT_DEFINITION_Y_HIGH + 1u,
    OBJECT_DEFINITION_FLAGS_HIGH = SEG09A9_FirstObjectDefinitionFlags - SEG09A9_LevelObjectDefinitions,
    OBJECT_DEFINITION_FLAGS_LOW = OBJECT_DEFINITION_FLAGS_HIGH + 1u,
    OBJECT_GRAPHICS_WIDTH = SEG09A9_FirstObjectGraphicsWidth - SEG09A9_LevelObjectGraphicsRecords,
    OBJECT_GRAPHICS_HEIGHT = SEG09A9_FirstObjectGraphicsHeight - SEG09A9_LevelObjectGraphicsRecords,
    OBJECT_GRAPHICS_MASK_SOURCE = SEG09A9_FirstObjectGraphicsMaskOffset - SEG09A9_LevelObjectGraphicsRecords,
    OBJECT_GRAPHICS_FRAME_SOURCE = SEG09A9_FirstObjectGraphicsFrameOffset - SEG09A9_LevelObjectGraphicsRecords
};

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read_byte_at(uint8_t *memory, uint32_t address,
                            uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xfffffu;
    return bus && bus->read_byte
        ? bus->read_byte(bus->context, memory, address, flags)
        : memory[address];
}

static void write_byte_at(uint8_t *memory, uint32_t address, uint8_t value,
                          uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static uint8_t read_byte(uint8_t *memory, uint16_t segment, uint16_t offset,
                         uint16_t flags, const LmnRasterBus *bus) {
    return read_byte_at(memory, physical(segment, offset), flags, bus);
}

static uint16_t read_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                          uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte_at(memory, address, flags, bus);
    uint8_t high = read_byte_at(memory, (address + 1u) & 0xfffffu,
                                flags, bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_byte_at(memory, address, (uint8_t)value, flags, bus);
    write_byte_at(memory, (address + 1u) & 0xfffffu,
                  (uint8_t)(value >> 8), flags, bus);
}

static void push_word(uint8_t *memory, uint16_t segment, uint16_t *stack_offset,
                      uint16_t value, uint16_t flags,
                      const LmnRasterBus *bus) {
    *stack_offset = (uint16_t)(*stack_offset - 2u);
    write_word(memory, segment, *stack_offset, value, flags, bus);
}

static uint16_t pop_word(uint8_t *memory, uint16_t segment,
                         uint16_t *stack_offset, uint16_t flags,
                         const LmnRasterBus *bus) {
    uint16_t value = read_word(memory, segment, *stack_offset, flags, bus);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

static unsigned even_parity(uint8_t value) {
    unsigned parity = 0;
    unsigned bit;
    for (bit = 0; bit != 8; ++bit)
        parity ^= (value >> bit) & 1u;
    return parity == 0;
}

static uint16_t szp16(uint16_t value) {
    return (uint16_t)((even_parity((uint8_t)value) ? PF : 0u) |
                      (value == 0 ? ZF : 0u) |
                      ((value & 0x8000u) ? SF : 0u));
}

static uint16_t logic16_flags(uint16_t flags, uint16_t value) {
    /* 8086 leaves AF undefined for AND; preserve its incoming representative. */
    return (uint16_t)((flags & (uint16_t)~LOGIC_DEFINED_FLAGS) |
                      szp16(value));
}

static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    uint16_t changed = 0;
    if (even_parity(value)) changed |= PF;
    if (value == 0) changed |= ZF;
    if (value & 0x80u) changed |= SF;
    /* XOR DH,DH likewise leaves AF undefined. */
    return (uint16_t)((flags & (uint16_t)~LOGIC_DEFINED_FLAGS) | changed);
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right,
                            uint16_t result) {
    uint32_t sum = (uint32_t)left + right;
    uint16_t changed = szp16(result);
    if (sum > 0xffffu) changed |= CF;
    if ((left ^ right ^ result) & 0x0010u) changed |= AF;
    if ((~(left ^ right) & (left ^ result)) & 0x8000u) changed |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) | changed);
}

static void take_child_state(LmnObjectDrawingResult *result,
                             const LmnDrawingRenderResult *drawing) {
    const LmnDrawingSourceResult *child = &drawing->plan.state;
    result->state.work_value = child->work_value;
    result->state.second_source_cursor = child->second_source_cursor;
    result->state.packed_counts = child->packed_counts;
    result->state.width_state = child->width_state;
    result->state.source_cursor = child->source_cursor;
    result->state.destination_cursor = child->destination_cursor;
    result->state.control = child->control;
    result->state.stack_offset = child->stack_offset;
    result->state.flags = child->flags;
    result->state.continuation = child->continuation;
    result->data_segment = drawing->source_segment;
    result->output_segment = drawing->output_segment;
}

LmnObjectDrawingResult lmn_draw_level_objects_core(
    uint8_t *memory, const LmnObjectDrawingCall *call,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnObjectDrawingResult result = {0};
    uint16_t stack_offset;

    result.data_segment = call->data_segment;
    result.output_segment = call->output_segment;
    result.code_segment = call->code_segment;
    result.state = (LmnDrawingSourceResult){
        .work_value = 0,
        .second_source_cursor = call->second_source_cursor,
        .packed_counts = 0x0020u,
        .width_state = call->width_state,
        .source_cursor = SEG09A9_LevelObjectGraphicsRecords,
        .destination_cursor = SEG09A9_LevelObjectDefinitions,
        .control = call->control,
        .stack_offset = call->stack_offset,
        .flags = call->flags,
        .continuation = CS_LevelObjectsLoop
    };

    /* 3988..398B load the live graphics segment and publish it before the
       loop. The word bytes and both memory operations are provider-visible. */
    result.state.work_value = read_word(memory, result.data_segment,
        SEG09A9_LevelGraphicsSegment, result.state.flags, bus);
    write_word(memory, result.data_segment, SEG09A9_GraphicsResourceSegment,
        result.state.work_value, result.state.flags, bus);

    for (;;) {
        uint16_t definition = result.state.destination_cursor;
        uint16_t active_x;
        uint16_t flags_word;
        uint8_t x_high, x_low;

        /* The X word is two independent big-endian byte instructions. */
        x_high = read_byte(memory, result.data_segment,
            (uint16_t)(definition + OBJECT_DEFINITION_X_HIGH),
            result.state.flags, bus);
        x_low = read_byte(memory, result.data_segment,
            (uint16_t)(definition + OBJECT_DEFINITION_X_LOW),
            result.state.flags, bus);
        active_x = (uint16_t)(((uint16_t)x_high << 8) | x_low);
        result.state.work_value = active_x;
        result.state.flags = logic16_flags(result.state.flags, active_x);

        if (active_x != 0) {
#if OBJECT_DRAWING_MUTATION == 4
            uint16_t saved_si = result.state.source_cursor;
            uint16_t saved_di = result.state.destination_cursor;
            uint16_t saved_cx = result.state.packed_counts;
#endif
            uint8_t y_high, y_low;
            uint8_t flags_high, flags_low;
            uint8_t object_width, object_height;
            uint16_t data_word;
            uint16_t child_return_ip, child_return_cs;
            uint16_t expected_ip = CS_LevelObjectsAfterBitmap;

            /* PUSH CX / DI / SI are live writes through SS, in this order. */
            stack_offset = result.state.stack_offset;
            push_word(memory, call->stack_segment, &stack_offset,
                result.state.packed_counts, result.state.flags, bus);
            push_word(memory, call->stack_segment, &stack_offset,
                result.state.destination_cursor, result.state.flags, bus);
            push_word(memory, call->stack_segment, &stack_offset,
                result.state.source_cursor, result.state.flags, bus);
            result.state.stack_offset = stack_offset;

            y_high = read_byte(memory, result.data_segment,
                (uint16_t)(definition + OBJECT_DEFINITION_Y_HIGH),
                result.state.flags, bus);
            y_low = read_byte(memory, result.data_segment,
                (uint16_t)(definition + OBJECT_DEFINITION_Y_LOW),
                result.state.flags, bus);
            result.state.second_source_cursor =
                (uint16_t)(((uint16_t)y_high << 8) | y_low);

            flags_high = read_byte(memory, result.data_segment,
                (uint16_t)(definition + OBJECT_DEFINITION_FLAGS_HIGH),
                result.state.flags, bus);
            flags_low = read_byte(memory, result.data_segment,
                (uint16_t)(definition + OBJECT_DEFINITION_FLAGS_LOW),
                result.state.flags, bus);
            flags_word = (uint16_t)(((uint16_t)flags_high << 8) | flags_low);
            result.state.control = flags_word;
            {
                uint16_t masked = (uint16_t)(flags_word & 0xfffeu);
                result.state.flags = logic16_flags(result.state.flags, masked);
#if OBJECT_DRAWING_MUTATION == 1
                /* Fault: retain drawing flag bit 0 while preserving AND flags. */
                result.state.control = flags_word;
#else
                result.state.control = masked;
#endif
            }

            /* DL receives width; XOR DH,DH then makes DX=00:width. */
            object_width = read_byte(memory, result.data_segment,
                (uint16_t)(result.state.source_cursor +
                           OBJECT_GRAPHICS_WIDTH),
                result.state.flags, bus);
            result.state.width_state = (uint16_t)(
                (result.state.width_state & 0xff00u) |
                object_width);
            result.state.width_state &= 0x00ffu;
            result.state.flags = logic8_flags(result.state.flags, 0);

            /* CL load preserves CH until the explicit MOV CH,4 below. */
            object_height = read_byte(memory, result.data_segment,
                (uint16_t)(result.state.source_cursor +
                           OBJECT_GRAPHICS_HEIGHT),
                result.state.flags, bus);
            result.state.packed_counts = (uint16_t)(
                (result.state.packed_counts & 0xff00u) |
                object_height);

            /* These are actual word memory operands with adjacent physical
               high-byte accesses, even if the effective offset wraps. */
            data_word = read_word(memory, result.data_segment,
                (uint16_t)(result.state.source_cursor +
                           OBJECT_GRAPHICS_MASK_SOURCE),
                result.state.flags, bus);
            result.state.destination_cursor = data_word;
            data_word = read_word(memory, result.data_segment,
                (uint16_t)(result.state.source_cursor +
                           OBJECT_GRAPHICS_FRAME_SOURCE),
                result.state.flags, bus);
            result.state.source_cursor = data_word;

            {
                uint16_t old_di = result.state.destination_cursor;
                result.state.destination_cursor = (uint16_t)(old_di +
                    result.state.source_cursor);
                result.state.flags = add16_flags(result.state.flags, old_di,
                    result.state.source_cursor,
                    result.state.destination_cursor);
            }
            result.state.packed_counts = (uint16_t)(
                (result.state.packed_counts & 0x00ffu) | 0x0400u);

            /* The far CALL pushes CS then its live39C2 continuation. */
            stack_offset = result.state.stack_offset;
            push_word(memory, call->stack_segment, &stack_offset,
                result.code_segment, result.state.flags, bus);
            push_word(memory, call->stack_segment, &stack_offset,
                expected_ip, result.state.flags, bus);
            result.state.stack_offset = stack_offset;

            {
                /* The lower renderer's non-NULL provider contract requires
                   both callbacks. An incomplete host capability takes the
                   same explicit969C stop as an absent provider. */
                const LmnRasterBytePorts *child_ports = ports;
                if (!child_ports || !child_ports->out_byte || !child_ports->in_byte)
                    child_ports = NULL;
                LmnPlanarBitmapCall drawing_call = {
                    result.data_segment, call->game_data_segment,
                    call->stack_segment, result.state.stack_offset,
                    result.state.work_value,
                    result.state.second_source_cursor,
                    result.state.packed_counts,
                    result.state.width_state,
                    result.state.source_cursor,
                    result.state.destination_cursor,
                    result.state.control,
                    result.output_segment,
                    result.state.flags
                };
                LmnDrawingRenderResult drawing =
                    lmn_draw_planar_bitmap_core(memory, &drawing_call,
                                                 bus, child_ports);
                take_child_state(&result, &drawing);
                result.changed_child_near = drawing.plan.changed_return;

                if (!drawing.body_returned) {
                    result.stopped = 1;
                    result.missing_provider = (uint16_t)(
                        !drawing.plan.changed_return &&
                        !child_ports &&
                        drawing.plan.state.continuation ==
                            CS_PlanarAlignedMasked4000Body);
                    return result;
                }
            }

            /* The child RETF reads the actual live IP and CS words. */
            stack_offset = result.state.stack_offset;
            child_return_ip = pop_word(memory, call->stack_segment,
                &stack_offset, result.state.flags, bus);
            child_return_cs = pop_word(memory, call->stack_segment,
                &stack_offset, result.state.flags, bus);
#if OBJECT_DRAWING_MUTATION == 3
            /* Fault: hide a changed live child far-return frame. */
            child_return_ip = expected_ip;
            child_return_cs = call->code_segment;
#endif
            result.code_segment = child_return_cs;
            result.state.stack_offset = stack_offset;
            if (child_return_ip != expected_ip ||
                child_return_cs != call->code_segment) {
                result.state.continuation = child_return_ip;
                result.changed_far_return = 1;
                result.stopped = 1;
                return result;
            }

            /* POP SI / DI / CX restore their live stack words. */
            result.state.source_cursor = pop_word(memory,
                call->stack_segment, &stack_offset, result.state.flags, bus);
            result.state.destination_cursor = pop_word(memory,
                call->stack_segment, &stack_offset, result.state.flags, bus);
            result.state.packed_counts = pop_word(memory,
                call->stack_segment, &stack_offset, result.state.flags, bus);
#if OBJECT_DRAWING_MUTATION == 4
            /* Fault: replace popped values with cached pre-child registers. */
            result.state.source_cursor = saved_si;
            result.state.destination_cursor = saved_di;
            result.state.packed_counts = saved_cx;
#endif
            result.state.stack_offset = stack_offset;

#if OBJECT_DRAWING_MUTATION == 2
            /* Fault: restore/cache entry DS across a child that changed DS. */
            result.data_segment = call->data_segment;
#endif
        }

        /* 39C5 / 39C8 ADD update flags in order; LOOP preserves them and has
           no artificial iteration limit after a live saved-CX overwrite. */
        {
            uint16_t old_di = result.state.destination_cursor;
            result.state.destination_cursor = (uint16_t)(old_di + 8u);
            result.state.flags = add16_flags(result.state.flags, old_di, 8u,
                result.state.destination_cursor);
        }
        {
            uint16_t old_si = result.state.source_cursor;
            result.state.source_cursor = (uint16_t)(old_si + 0x001cu);
            result.state.flags = add16_flags(result.state.flags, old_si,
                0x001cu, result.state.source_cursor);
        }
        result.state.packed_counts =
            (uint16_t)(result.state.packed_counts - 1u);
        if (result.state.packed_counts == 0) {
            result.state.continuation = CS_LevelObjectsReturn;
            result.ready_to_return = 1;
            return result;
        }
        result.state.continuation = CS_LevelObjectsLoop;
    }
}

void lmn_draw_level_objects_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports) {
    LmnObjectDrawingCall call = {
        regs->ds, game_data_segment, regs->es,
        regs->cs, regs->ss, regs->sp,
        regs->bx, regs->dx, regs->bp, regs->flags
    };
    LmnObjectDrawingResult result = lmn_draw_level_objects_core(
        memory, &call, bus, ports);
    regs->ax = result.state.work_value;
    regs->bx = result.state.second_source_cursor;
    regs->cx = result.state.packed_counts;
    regs->dx = result.state.width_state;
    regs->si = result.state.source_cursor;
    regs->di = result.state.destination_cursor;
    regs->bp = result.state.control;
    regs->sp = result.state.stack_offset;
    regs->ds = result.data_segment;
    regs->es = result.output_segment;
    regs->cs = result.code_segment;
    regs->ip = result.state.continuation;
    regs->flags = result.state.flags;
    if (result.ready_to_return)
        regs->ip = pop_word(memory, regs->ss, &regs->sp, regs->flags, bus);
}

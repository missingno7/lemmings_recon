#include "level_initialize.h"

#include "level_drawing.h"
#include "level_finish.h"
#include "level_header.h"
#include "lemmings_sym.h"
#include "object_state_bus.h"
#include "terrain_stream.h"

#ifndef LEVEL_INITIALIZE_MUTATION
#define LEVEL_INITIALIZE_MUTATION 0
#endif

enum {
    FLAG_CF = 0x0001u, FLAG_PF = 0x0004u, FLAG_ZF = 0x0040u,
    FLAG_SF = 0x0080u, FLAG_OF = 0x0800u,
    LOGIC8_DEFINED_FLAGS = FLAG_CF | FLAG_PF | FLAG_ZF | FLAG_SF | FLAG_OF
};

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read_byte_at(uint8_t *memory, uint32_t address,
                            uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write_byte_at(uint8_t *memory, uint32_t address, uint8_t value,
                          uint16_t flags, const LmnRasterBus *bus) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static uint16_t read_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                          uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte_at(memory, address, flags, bus);
    uint8_t high = read_byte_at(memory, address + 1u, flags, bus);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, uint16_t segment, uint16_t offset,
                       uint16_t value, uint16_t flags,
                       const LmnRasterBus *bus) {
    uint32_t address = physical(segment, offset);
    write_byte_at(memory, address, (uint8_t)value, flags, bus);
    write_byte_at(memory, address + 1u, (uint8_t)(value >> 8), flags, bus);
}

static void push_word(uint8_t *memory, uint16_t stack_segment,
                      uint16_t *stack_offset, uint16_t value, uint16_t flags,
                      const LmnRasterBus *bus) {
    *stack_offset = (uint16_t)(*stack_offset - 2u);
    write_word(memory, stack_segment, *stack_offset, value, flags, bus);
}

static uint16_t pop_word(uint8_t *memory, uint16_t stack_segment,
                         uint16_t *stack_offset, uint16_t flags,
                         const LmnRasterBus *bus) {
    uint16_t value = read_word(memory, stack_segment, *stack_offset, flags,
                               bus);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    uint16_t changed = 0;
    unsigned parity = 0;
    unsigned bit;
    for (bit = 0; bit != 8; ++bit)
        parity ^= (value >> bit) & 1u;
    if (parity == 0)
        changed |= FLAG_PF;
    if (value == 0)
        changed |= FLAG_ZF;
    if (value & 0x80u)
        changed |= FLAG_SF;
    /* AND AL,AL leaves AF undefined; retain its live representative. */
    return (uint16_t)((flags & (uint16_t)~LOGIC8_DEFINED_FLAGS) | changed);
}

static int raster_ready(const LmnRasterBus *bus) {
    return bus && bus->read_byte && bus->write_byte && bus->out_word;
}

static const LmnRasterBytePorts *complete_byte_ports(
    const LmnRasterBytePorts *ports) {
    return ports && ports->out_byte && ports->in_byte ? ports : NULL;
}

static int special_ready(const LmnSpecialSetupServices *special) {
    return special && special->files && special->files->open_readonly &&
        special->files->attributes && special->files->retry_ui &&
        special->io && special->io->query_size && special->io->read &&
        special->close;
}

static int consume_near_return(uint8_t *memory,
                               LmnLevelInitializeResult *result,
                               uint16_t stack_segment, uint16_t expected,
                               const LmnRasterBus *bus) {
    uint16_t actual = pop_word(memory, stack_segment,
        &result->state.stack_offset, result->state.flags, bus);
    result->state.continuation = actual;
    if (actual != expected) {
        result->status = LMN_LEVEL_INITIALIZE_CHANGED_RETURN;
        result->changed_return = 1;
        return 0;
    }
    result->changed_return = 0;
    return 1;
}

static void map_drawing(LmnLevelInitializeResult *result,
                        const LmnLevelDrawingResult *drawing) {
    result->state.work_value = drawing->value;
    result->state.second_source_cursor = drawing->height_state;
    result->state.packed_counts = drawing->count;
    result->state.width_state = drawing->product_high;
    result->state.destination_cursor = drawing->output_cursor;
    result->state.stack_offset = drawing->stack_offset;
    result->state.flags = drawing->flags;
    result->state.continuation = drawing->continuation;
    result->output_segment = drawing->output_segment;
    result->code_segment = drawing->code_segment;
}

static void map_terrain(LmnLevelInitializeResult *result,
                        const LmnTerrainStreamResult *terrain) {
    result->state = terrain->state;
    result->data_segment = terrain->data_segment;
    result->output_segment = terrain->output_segment;
    result->code_segment = terrain->code_segment;
}

static void map_special(LmnLevelInitializeResult *result,
                        const LmnDatFileResult *special) {
    result->state.work_value = special->value;
    result->state.second_source_cursor = special->handle;
    result->state.packed_counts = special->count;
    result->state.width_state = special->filename_offset;
    result->state.source_cursor = special->source_cursor;
    result->state.destination_cursor = special->output_cursor;
    result->state.control = special->base_cursor;
    result->state.stack_offset = special->stack_offset;
    result->state.flags = special->flags;
    result->data_segment = special->segment;
    result->output_segment = special->extra_segment;
}

static void map_object_state(LmnLevelInitializeResult *result,
                             const LmnObjectStateResult *objects) {
    result->state.work_value = objects->value;
    result->state.second_source_cursor = objects->cell_cursor;
    result->state.packed_counts = objects->remaining_records;
    result->state.width_state = objects->dimension_state;
    result->state.source_cursor = objects->source_cursor;
    result->state.destination_cursor = objects->definition_cursor;
    result->state.control = objects->base_cursor;
    result->state.stack_offset = objects->stack_offset;
    result->state.flags = objects->flags;
    result->state.continuation = objects->continuation;
    result->output_segment = objects->extra_segment;
}

static void map_finish(LmnLevelInitializeResult *result,
                       const LmnLevelFinishResult *finish) {
    result->state.work_value = finish->value;
    result->state.second_source_cursor = finish->target_cursor;
    result->state.packed_counts = finish->count;
    result->state.width_state = finish->port_or_population;
    result->state.source_cursor = finish->source_cursor;
    result->state.destination_cursor = finish->output_cursor;
    result->state.stack_offset = finish->stack_offset;
    result->state.flags = finish->flags;
    result->state.continuation = finish->continuation;
    result->data_segment = finish->data_segment;
    result->output_segment = finish->extra_segment;
}

LmnLevelInitializeResult lmn_initialize_level_core(
    uint8_t *memory, const LmnLevelInitializeCall *call,
    const LmnLevelInitializeServices *services) {
    LmnLevelInitializeResult result = {0};
    const LmnRasterBus *bus = services ? services->raster : NULL;
    const LmnRasterBytePorts *ports = complete_byte_ports(
        services ? services->ports : NULL);
#if LEVEL_INITIALIZE_MUTATION == 3
    uint16_t entry_data_segment = call->data_segment;
#endif
    uint8_t selector;
    unsigned use_special;

    result.state = call->state;
    result.data_segment = call->data_segment;
    result.output_segment = call->output_segment;
    result.code_segment = call->code_segment;
    result.state.continuation = CS_InitializeLevelFromRecord;

    /* 368E clears and configures VGA; do not mutate before its bus is ready. */
    if (!raster_ready(bus)) {
        result.status = LMN_LEVEL_INITIALIZE_MISSING_SERVICES;
        result.missing_services = 1;
        return result;
    }

    /* CALL 368E pushes its actual 36B9 continuation before the child runs. */
    push_word(memory, call->stack_segment, &result.state.stack_offset,
              CS_ApplyLevelHeader, result.state.flags, bus);
    {
        LmnLevelDrawingCall drawing_call = {
            result.data_segment, call->stack_segment,
            result.state.stack_offset, result.code_segment,
            result.state.second_source_cursor, result.state.flags
        };
        LmnLevelDrawingResult drawing = lmn_initialize_level_drawing_core(
            memory, &drawing_call, bus);
        map_drawing(&result, &drawing);
        /* 368E preserves DS, SI and BP on every normal return. */
        result.state.source_cursor = call->state.source_cursor;
        result.state.control = call->state.control;
        result.data_segment = call->data_segment;
        if (drawing.changed_return) {
#if LEVEL_INITIALIZE_MUTATION == 4
            /* Mutant: ignore the initial drawing child's changed transfer. */
            result.state.continuation = CS_ApplyLevelHeader;
            result.changed_return = 0;
#else
            result.status = LMN_LEVEL_INITIALIZE_CHANGED_RETURN;
            result.changed_return = 1;
            return result;
#endif
        }
    }
    if (!consume_near_return(memory, &result, call->stack_segment,
                             CS_ApplyLevelHeader, bus))
        return result;

    /* Header bytes are a fallthrough from 36B9, with no caller-owned frame. */
#if LEVEL_INITIALIZE_MUTATION == 1
    /* Mutant: invent a CALL/RET boundary around the straight-line header. */
    push_word(memory, call->stack_segment, &result.state.stack_offset,
              CS_LevelAfterHeader, result.state.flags, bus);
#endif
    {
        LmnLevelHeaderResult header = lmn_apply_level_header_core(memory,
            result.data_segment, result.state.flags, bus);
        result.state.work_value = header.value;
        result.state.destination_cursor = header.header_cursor;
        result.state.flags = header.flags;
        result.state.continuation = CS_LevelAfterHeader;
    }
#if LEVEL_INITIALIZE_MUTATION == 1
    if (!consume_near_return(memory, &result, call->stack_segment,
                             CS_LevelAfterHeader, bus))
        return result;
#endif

    /* MOV AL,[DS:0FE8] then AND AL,AL; AH remains live. */
    selector = read_byte_at(memory,
        physical(result.data_segment, SEG09A9_LevelSpecialGraphicsSetByte),
        result.state.flags, bus);
    result.state.work_value = (uint16_t)(
        (result.state.work_value & 0xff00u) | selector);
    result.state.flags = logic8_flags(result.state.flags, selector);
#if LEVEL_INITIALIZE_MUTATION == 2
    /* Mutant: branch on whole AX after the real AL load. */
    use_special = result.state.work_value != 0;
#else
    use_special = selector != 0;
#endif

    if (use_special) {
        LmnSpecialSetupServices special_services;
        LmnDatFileCall special_call;
        LmnDatFileResult special_result;

        /* CALL 1A7B writes the live 374C return before service validation. */
        push_word(memory, call->stack_segment, &result.state.stack_offset,
                  CS_LevelInitializeAfterSpecial, result.state.flags, bus);
        result.state.continuation = CS_SetupSpecialGraphicsResource;
        if (!services || !services->dat_segments ||
            !special_ready(services->special)) {
            result.status = LMN_LEVEL_INITIALIZE_MISSING_SERVICES;
            result.missing_services = 1;
            return result;
        }
        special_call = (LmnDatFileCall){
            result.state.work_value,
            result.state.second_source_cursor,
            result.state.packed_counts,
            result.state.width_state,
            result.state.source_cursor,
            result.state.destination_cursor,
            result.state.control,
            result.data_segment,
            result.output_segment,
            call->stack_segment,
            result.state.stack_offset,
            result.state.flags
        };
        special_services = *services->special;
        special_services.raster = bus;
        special_result = lmn_setup_special_graphics_core(memory,
            &special_call, services->dat_segments, &special_services);
        map_special(&result, &special_result);
        result.fatal = special_result.fatal;
        if (special_result.fatal) {
            result.state.continuation = special_result.fatal == 1
                ? CS_DatFileErrorTransfer : CS_DatFatalTransfer;
            result.status = special_result.fatal == 1
                ? LMN_LEVEL_INITIALIZE_FATAL_FILE
                : LMN_LEVEL_INITIALIZE_FATAL_DECODE;
            return result;
        }
        if (!consume_near_return(memory, &result, call->stack_segment,
                CS_LevelInitializeAfterSpecial, bus))
            return result;
        /* The original JMP to 376A leaves flags and stack unchanged. */
        result.state.continuation = CS_PrepareLevelObjectState;
    } else {
        LmnTerrainStreamCall terrain_call;
        LmnTerrainStreamResult terrain;

        result.state.continuation = CS_DrawLevelTerrainStream;
        terrain_call = (LmnTerrainStreamCall){
            result.data_segment,
            call->game_data_segment,
            result.code_segment,
            call->stack_segment,
            result.state.stack_offset,
            result.state.packed_counts,
            result.state.width_state,
            result.state.destination_cursor,
            result.state.control,
            result.output_segment,
            result.state.flags
        };
        terrain = lmn_draw_terrain_stream_core(memory, &terrain_call, 0,
                                               bus, ports);
        map_terrain(&result, &terrain);
        if (terrain.stopped) {
            if (terrain.changed_return) {
                result.status = LMN_LEVEL_INITIALIZE_CHANGED_RETURN;
                result.changed_return = 1;
            } else if (!ports && result.state.continuation ==
                           CS_PlanarAlignedMasked4000Body) {
                result.status = LMN_LEVEL_INITIALIZE_MISSING_PROVIDER;
                result.missing_provider = 1;
                result.unported = 1;
            } else {
                result.status = LMN_LEVEL_INITIALIZE_UNPORTED_CONTINUATION;
                result.unported = 1;
            }
            return result;
        }
        result.state.continuation = CS_PrepareLevelObjectState;
    }

    /* The four object-state CALLs own their frames through the 3776 boundary. */
    {
        LmnObjectStateCall objects_call;
        LmnObjectStateResult objects;
#if LEVEL_INITIALIZE_MUTATION == 3
        objects_call = (LmnObjectStateCall){
            entry_data_segment, call->stack_segment,
            result.state.stack_offset, result.state.width_state,
            result.state.control, result.state.flags
        };
#else
        objects_call = (LmnObjectStateCall){
            result.data_segment, call->stack_segment,
            result.state.stack_offset, result.state.width_state,
            result.state.control, result.state.flags
        };
#endif
        objects = lmn_prepare_level_object_state_bus_core(memory,
                                                           &objects_call, bus);
        map_object_state(&result, &objects);
        if (objects.changed_return) {
            result.status = LMN_LEVEL_INITIALIZE_CHANGED_RETURN;
            result.changed_return = 1;
            return result;
        }
    }

    /* The finish child owns 3776..3789 up to, but not including, its RET. */
    {
        LmnLevelFinishCall finish_call = {
            result.code_segment,
            result.data_segment,
            call->stack_segment,
            result.state.stack_offset,
            result.state.second_source_cursor,
            result.state.source_cursor,
            result.state.flags
        };
        LmnLevelFinishResult finish = lmn_finish_level_initialization_core(
            memory, &finish_call, bus);
        map_finish(&result, &finish);
        if (finish.changed_return) {
            result.status = LMN_LEVEL_INITIALIZE_CHANGED_RETURN;
            result.changed_return = 1;
            return result;
        }
    }

    result.status = LMN_LEVEL_INITIALIZE_READY_TO_RETURN;
    result.ready_to_return = 1;
    return result;
}

static void apply_result(LmnRegs *registers,
                         const LmnLevelInitializeResult *result) {
    registers->ax = result->state.work_value;
    registers->bx = result->state.second_source_cursor;
    registers->cx = result->state.packed_counts;
    registers->dx = result->state.width_state;
    registers->si = result->state.source_cursor;
    registers->di = result->state.destination_cursor;
    registers->bp = result->state.control;
    registers->sp = result->state.stack_offset;
    registers->ds = result->data_segment;
    registers->es = result->output_segment;
    registers->cs = result->code_segment;
    registers->ip = result->state.continuation;
    registers->flags = result->state.flags;
}

void lmn_initialize_level_adapter(
    uint8_t *memory, LmnRegs *registers, uint16_t game_data_segment,
    const LmnLevelInitializeServices *services) {
    LmnLevelInitializeCall call = {
        {
            registers->ax, registers->bx, registers->cx, registers->dx,
            registers->si, registers->di, registers->bp, registers->sp,
            registers->flags, registers->ip
        },
        registers->ds, registers->es, registers->cs, registers->ss,
        game_data_segment
    };
    LmnLevelInitializeResult result = lmn_initialize_level_core(
        memory, &call, services);
    apply_result(registers, &result);
    if (result.ready_to_return) {
        const LmnRasterBus *bus = services ? services->raster : NULL;
        registers->ip = pop_word(memory, registers->ss, &registers->sp,
                                 registers->flags, bus);
    }
}

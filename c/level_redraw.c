#include "level_redraw.h"

#include "lemmings_sym.h"
#include "level_drawing.h"
#include "object_drawing.h"
#include "object_graphics.h"
#include "terrain_stream.h"

#ifndef LEVEL_REDRAW_MUTATION
#define LEVEL_REDRAW_MUTATION 0
#endif

enum {
    CF = 0x0001u, PF = 0x0004u, ZF = 0x0040u, SF = 0x0080u,
    OF = 0x0800u,
    LOGIC_DEFINED_FLAGS = CF | PF | ZF | SF | OF
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

static void push_word(uint8_t *memory, uint16_t stack_segment,
                      uint16_t *stack_offset, uint16_t value,
                      uint16_t flags, const LmnRasterBus *bus) {
    *stack_offset = (uint16_t)(*stack_offset - 2u);
    write_word(memory, stack_segment, *stack_offset, value, flags, bus);
}

static uint16_t pop_word(uint8_t *memory, uint16_t stack_segment,
                         uint16_t *stack_offset, uint16_t flags,
                         const LmnRasterBus *bus) {
    uint16_t value = read_word(memory, stack_segment, *stack_offset,
                               flags, bus);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    uint16_t changed = 0;
    unsigned parity = 0;
    unsigned bit;
    for (bit = 0; bit != 8; ++bit)
        parity ^= (value >> bit) & 1u;
    if (parity == 0) changed |= PF;
    if (value == 0) changed |= ZF;
    if (value & 0x80u) changed |= SF;
    /* AND AL,AL leaves AF undefined; preserve its live representative. */
    return (uint16_t)((flags & (uint16_t)~LOGIC_DEFINED_FLAGS) | changed);
}

static int raster_ready(const LmnRasterBus *bus) {
    return bus && bus->read_byte && bus->write_byte && bus->out_word;
}

static int special_ready(const LmnSpecialSetupServices *special) {
    return special && special->files && special->files->open_readonly &&
        special->files->attributes && special->files->retry_ui &&
        special->io && special->io->query_size && special->io->read &&
        special->close;
}

static const LmnRasterBytePorts *complete_byte_ports(
    const LmnRasterBytePorts *ports) {
    return ports && ports->out_byte && ports->in_byte ? ports : NULL;
}

static void map_dat_state(LmnLevelRedrawResult *result,
                          const LmnDatFileResult *dat) {
    result->state.work_value = dat->value;
    result->state.second_source_cursor = dat->handle;
    result->state.packed_counts = dat->count;
    result->state.width_state = dat->filename_offset;
    result->state.source_cursor = dat->source_cursor;
    result->state.destination_cursor = dat->output_cursor;
    result->state.control = dat->base_cursor;
    result->state.stack_offset = dat->stack_offset;
    result->state.flags = dat->flags;
    result->data_segment = dat->segment;
    result->output_segment = dat->extra_segment;
}

static void map_level_drawing_state(LmnLevelRedrawResult *result,
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

static void map_terrain_state(LmnLevelRedrawResult *result,
                              const LmnTerrainStreamResult *terrain) {
    result->state = terrain->state;
    result->data_segment = terrain->data_segment;
    result->output_segment = terrain->output_segment;
    result->code_segment = terrain->code_segment;
}

static void map_object_graphics_state(LmnLevelRedrawResult *result,
                                      const LmnObjectGraphicsResult *copy) {
    result->state.work_value = copy->value;
    result->state.second_source_cursor = copy->definition_cursor;
    result->state.packed_counts = copy->count;
    result->state.width_state = copy->product_high;
    result->state.source_cursor = copy->source_cursor;
    result->state.destination_cursor = copy->output_cursor;
    result->state.stack_offset = copy->stack_offset;
    result->state.flags = copy->flags;
    result->output_segment = copy->extra_segment;
}

static void map_object_drawing_state(LmnLevelRedrawResult *result,
                                     const LmnObjectDrawingResult *drawing) {
    result->state = drawing->state;
    result->data_segment = drawing->data_segment;
    result->output_segment = drawing->output_segment;
    result->code_segment = drawing->code_segment;
}

static void stop_changed_return(LmnLevelRedrawResult *result,
                                uint16_t continuation) {
    result->state.continuation = continuation;
    result->status = LMN_LEVEL_REDRAW_CHANGED_RETURN;
    result->changed_return = 1;
}

static void stop_unported(LmnLevelRedrawResult *result) {
    result->status = LMN_LEVEL_REDRAW_UNPORTED_CONTINUATION;
    result->unported = 1;
}

static uint16_t consume_near_call_return(
    uint8_t *memory, LmnLevelRedrawResult *result, uint16_t stack_segment,
    uint16_t expected, const LmnRasterBus *bus) {
    uint16_t target = pop_word(memory, stack_segment,
        &result->state.stack_offset, result->state.flags, bus);
    result->state.continuation = target;
    if (target != expected) {
        stop_changed_return(result, target);
        return 0;
    }
    return 1;
}

LmnLevelRedrawResult lmn_redraw_level_core(
    uint8_t *memory, const LmnLevelRedrawCall *call,
    const LmnLevelRedrawServices *services) {
    LmnLevelRedrawResult result = {0};
    LmnLevelDrawingCall initialize_call;
    LmnLevelDrawingResult initialized;
    const LmnRasterBus *bus = services ? services->raster : NULL;
    const LmnRasterBytePorts *ports = complete_byte_ports(
        services ? services->ports : NULL);
#if LEVEL_REDRAW_MUTATION == 2
    uint16_t original_data_segment = call->data_segment;
#endif
    uint16_t return_word;
    uint8_t selector;
    unsigned use_special;

    result.state = call->state;
    result.data_segment = call->data_segment;
    result.output_segment = call->output_segment;
    result.code_segment = call->code_segment;
    result.state.continuation = CS_RedrawLevel;

    /*368E's clear uses all raster callbacks. Do not enter it with a partial
       device service and then invent a fallback for VGA or stack aliases. */
    if (!raster_ready(bus)) {
        result.status = LMN_LEVEL_REDRAW_MISSING_SERVICES;
        result.missing_services = 1;
        return result;
    }

    /* CALL368E writes its live near return before the child executes. */
    push_word(memory, call->stack_segment, &result.state.stack_offset,
              CS_LevelRedrawAfterInitialize, result.state.flags, bus);
    result.state.continuation = CS_InitializeLevelDrawing;
    initialize_call = (LmnLevelDrawingCall){
        result.data_segment, call->stack_segment, result.state.stack_offset,
        result.code_segment, result.state.second_source_cursor,
        result.state.flags
    };
    initialized = lmn_initialize_level_drawing_core(
        memory, &initialize_call, bus);
    map_level_drawing_state(&result, &initialized);
    /*368E preserves DS, SI and BP; its result exposes the changed registers. */
    result.state.source_cursor = call->state.source_cursor;
    result.state.control = call->state.control;
    result.data_segment = call->data_segment;
    if (initialized.changed_return) {
        result.status = LMN_LEVEL_REDRAW_CHANGED_RETURN;
        result.changed_return = 1;
        return result;
    }
    if (!consume_near_call_return(memory, &result, call->stack_segment,
            CS_LevelRedrawAfterInitialize, bus))
        return result;

    /* MOV AL,[DS:0FE8] changes only AX's low byte. AND AL,AL supplies the
       branch flags while preserving the undefined AF representative. */
    selector = read_byte(memory, result.data_segment,
        SEG09A9_LevelSpecialGraphicsSetByte, result.state.flags, bus);
    result.state.work_value = (uint16_t)(
        (result.state.work_value & 0xff00u) | selector);
    result.state.flags = logic8_flags(result.state.flags, selector);
    use_special = selector != 0;
#if LEVEL_REDRAW_MUTATION == 1
    use_special = !use_special;
#endif

    if (use_special) {
        LmnSpecialSetupServices special_services;
        LmnDatFileCall special_call;
        LmnDatFileResult special_result;
        /* CALL1A7B's return stays live even when services are unavailable. */
        push_word(memory, call->stack_segment, &result.state.stack_offset,
                  CS_LevelRedrawAfterSpecial, result.state.flags, bus);
        result.state.continuation = CS_SetupSpecialGraphicsResource;
        if (!services || !services->dat_segments ||
            !special_ready(services->special)) {
            result.status = LMN_LEVEL_REDRAW_MISSING_SERVICES;
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
        /* Keep every child on the exact same canonical raster bus. The
           service object supplies DOS callbacks; its bus slot is overridden
           locally so stack/device aliases share this parent's provider. */
        special_services = *services->special;
        special_services.raster = bus;
        special_result = lmn_setup_special_graphics_core(memory,
            &special_call, services->dat_segments, &special_services);
        map_dat_state(&result, &special_result);
        result.fatal = special_result.fatal;
        if (special_result.fatal) {
            result.state.continuation = special_result.fatal == 1
                ? CS_DatFileErrorTransfer : CS_DatFatalTransfer;
            result.status = special_result.fatal == 1
                ? LMN_LEVEL_REDRAW_FATAL_FILE
                : LMN_LEVEL_REDRAW_FATAL_DECODE;
            return result;
        }
#if LEVEL_REDRAW_MUTATION == 2
        result.data_segment = original_data_segment;
#endif
        if (!consume_near_call_return(memory, &result,
                call->stack_segment, CS_LevelRedrawAfterSpecial, bus))
            return result;
    } else {
        LmnTerrainStreamCall terrain_call;
        LmnTerrainStreamResult terrain;
        result.state.continuation = CS_RedrawLevelTerrainStream;
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
        terrain = lmn_draw_terrain_stream_core(memory, &terrain_call, 1,
                                               bus, ports);
        map_terrain_state(&result, &terrain);
        if (terrain.stopped) {
            if (terrain.changed_return) {
                result.status = LMN_LEVEL_REDRAW_CHANGED_RETURN;
                result.changed_return = 1;
            } else if (!ports && result.state.continuation ==
                           CS_PlanarAlignedMasked4000Body) {
                result.status = LMN_LEVEL_REDRAW_MISSING_PROVIDER;
                result.missing_provider = 1;
                result.unported = 1;
            } else {
                stop_unported(&result);
            }
            return result;
        }
#if LEVEL_REDRAW_MUTATION == 2
        result.data_segment = original_data_segment;
#endif
        /* The sentinel branch reaches397A directly; no extra call frame. */
        result.state.continuation = CS_RedrawTerrainFinished;
    }

    /* CALL378A. Its bus-aware core leaves the actual return word for this
       parent to consume before entering the397D object suffix. */
    push_word(memory, call->stack_segment, &result.state.stack_offset,
              CS_DrawLevelObjects, result.state.flags, bus);
    result.state.continuation = CS_CopyLevelObjectGraphicsRecords;
    {
        LmnObjectGraphicsResult copied = lmn_copy_object_graphics_bus_core(
            memory, result.data_segment, call->stack_segment,
            result.state.stack_offset, result.state.width_state,
            result.state.flags, bus);
        map_object_graphics_state(&result, &copied);
    }
    return_word = pop_word(memory, call->stack_segment,
        &result.state.stack_offset, result.state.flags, bus);
#if LEVEL_REDRAW_MUTATION == 3
    return_word = CS_DrawLevelObjects;
#endif
    result.state.continuation = return_word;
    if (return_word != CS_DrawLevelObjects) {
        stop_changed_return(&result, return_word);
        return result;
    }

    /* The prefix LEAs and MOVs are represented by397D's existing object core.
       It rereads DS:1FF0 and publishes the live word at DS:1FE4 itself. */
    {
        LmnObjectDrawingCall drawing_call = {
            result.data_segment,
            call->game_data_segment,
            result.output_segment,
            result.code_segment,
            call->stack_segment,
            result.state.stack_offset,
            result.state.second_source_cursor,
            result.state.width_state,
            result.state.control,
            result.state.flags
        };
        LmnObjectDrawingResult drawing = lmn_draw_level_objects_core(
            memory, &drawing_call, bus, ports);
        map_object_drawing_state(&result, &drawing);
        if (drawing.ready_to_return) {
            result.state.continuation = CS_LevelObjectsReturn;
            result.status = LMN_LEVEL_REDRAW_READY_TO_RETURN;
            result.ready_to_return = 1;
            return result;
        }
        if (drawing.changed_child_near || drawing.changed_far_return) {
            result.status = LMN_LEVEL_REDRAW_CHANGED_RETURN;
            result.changed_return = 1;
            return result;
        }
        if (drawing.missing_provider) {
            result.status = LMN_LEVEL_REDRAW_MISSING_PROVIDER;
            result.missing_provider = 1;
            result.unported = 1;
            return result;
        }
        stop_unported(&result);
        return result;
    }
}

static void apply_result(LmnRegs *regs, const LmnLevelRedrawResult *result) {
    regs->ax = result->state.work_value;
    regs->bx = result->state.second_source_cursor;
    regs->cx = result->state.packed_counts;
    regs->dx = result->state.width_state;
    regs->si = result->state.source_cursor;
    regs->di = result->state.destination_cursor;
    regs->bp = result->state.control;
    regs->sp = result->state.stack_offset;
    regs->ds = result->data_segment;
    regs->es = result->output_segment;
    regs->cs = result->code_segment;
    regs->ip = result->state.continuation;
    regs->flags = result->state.flags;
}

void lmn_redraw_level_adapter(
    uint8_t *memory, LmnRegs *regs, uint16_t game_data_segment,
    const LmnLevelRedrawServices *services) {
    LmnLevelRedrawCall call = {
        {
            regs->ax, regs->bx, regs->cx, regs->dx,
            regs->si, regs->di, regs->bp, regs->sp,
            regs->flags, regs->ip
        },
        regs->ds, regs->es, regs->cs, regs->ss, game_data_segment
    };
    LmnLevelRedrawResult result = lmn_redraw_level_core(
        memory, &call, services);
    apply_result(regs, &result);
    if (result.ready_to_return) {
        regs->ip = pop_word(memory, regs->ss, &regs->sp,
                            regs->flags, services->raster);
    }
}

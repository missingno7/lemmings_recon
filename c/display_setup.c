#include "display_setup.h"
#include "drawing_layout.h"
#include "lemmings_sym.h"

#ifndef DISPLAY_SETUP_MUTATION
#define DISPLAY_SETUP_MUTATION 0
#endif

enum { IF = 0x0200 };

/* Segmented words access the physical successor byte, with 20-bit wrap. */
static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + (uint32_t)offset) & 0xfffffu;
}

static uint8_t read_byte(uint8_t *memory, const LmnRasterBus *bus,
                         uint32_t address, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset,
                          uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(uint8_t *memory, const LmnRasterBus *bus,
                       uint16_t segment, uint16_t offset, uint16_t value,
                       uint16_t flags) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, bus, address, (uint8_t)value, flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), flags);
}

static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      LmnDisplaySetupState *state, uint16_t value) {
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    write_word(memory, bus, state->stack_segment, state->stack_offset,
               value, state->flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         LmnDisplaySetupState *state) {
    uint16_t value = read_word(memory, bus, state->stack_segment,
                               state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return value;
}

static LmnDisplaySetupResult make_result(
    const LmnDisplaySetupState *state, uint16_t code_segment,
    uint16_t continuation, enum LmnDisplaySetupStatus status) {
    LmnDisplaySetupResult result = {
        *state, code_segment, continuation, status
    };
    return result;
}

LmnDisplaySetupResult lmn_setup_display_core(uint8_t *memory,
    uint16_t code_segment, const LmnDisplaySetupState *input,
    enum LmnDisplaySetupEntry entry,
    const LmnVideoRestoreServices *services, const LmnRasterBus *bus) {
    LmnDisplaySetupState state = *input;
    uint16_t live_code_segment = code_segment;
    uint16_t continuation;
#if DISPLAY_SETUP_MUTATION == 1
    uint16_t entry_data_segment = input->data_segment;
#endif

    if (entry == LMN_DISPLAY_SETUP_ENTRY_FULL) {
        /* MOV byte [CS:83BE],FF; NOP; CLI; MOV AX,0090. 83BE is the
           shared checksum window's third successor byte, not new game state. */
        write_byte(memory, bus,
            physical(code_segment, (uint16_t)(CS_ChecksumCursor + 3u)),
            0xffu, state.flags);
        state.flags &= (uint16_t)~IF;
        state.value = 0x0090u;

        if (!services || !services->set_mode) {
            /* Stop at the INT 10h site. The original path has not executed
               the BIOS call or the following STI and has no outer RET yet. */
            return make_result(&state, code_segment, CS_DisplaySetupModeInterrupt,
                               LMN_DISPLAY_SETUP_MISSING_MODE);
        }

        {
            LmnDisplaySetupState returned = state;
            services->set_mode(services->context, memory, &state, &returned);
            state = returned;
        }
#if DISPLAY_SETUP_MUTATION == 1
        /* Mutant: throw away BIOS-returned DS before the live DS accesses. */
        state.data_segment = entry_data_segment;
#endif
#if DISPLAY_SETUP_MUTATION != 2
        /* STI is unconditional and changes only IF after BIOS returns. */
        state.flags |= IF;
#endif
    }

    if (entry != LMN_DISPLAY_SETUP_ENTRY_LAYOUT) {
        /* 4BF5, 4BFB and 4C01: ordered immediate stores through live DS. */
        write_word(memory, bus, state.data_segment, SEG09A9_DrawingOrigin,
                   0x0000u, state.flags);
        write_word(memory, bus, state.data_segment,
                   SEG09A9_AlternateDrawingOrigin, 0x6d60u, state.flags);
        write_word(memory, bus, state.data_segment,
                   SEG09A9_DrawingPageByteOffset, 0x0000u, state.flags);
    }

    /* 4C07: MOV AX,0280; MOV BX,015E; MOV DX,[DS:1F76]. */
    state.value = 0x0280u;
    state.base_value = 0x015eu;
    state.argument = read_word(memory, bus, state.data_segment,
                               SEG09A9_DrawingOrigin, state.flags);

    /* 4C11 far CALL: x86 pushes CS then the following IP. The RETF below
       reads IP then CS from the same live stack, so aliases remain visible. */
#if DISPLAY_SETUP_MUTATION == 4
    push_word(memory, bus, &state, CS_DisplaySetupAfterLayout);
    push_word(memory, bus, &state, code_segment);
#else
    push_word(memory, bus, &state, code_segment);
    push_word(memory, bus, &state, CS_DisplaySetupAfterLayout);
#endif

    {
        LmnDrawingLayoutResult layout = lmn_set_drawing_layout_core(
            memory, state.data_segment, state.value, state.base_value,
            state.argument, state.flags, bus);
        /* 8808 supplies AX, DX and FLAGS; all other saved fields flow through. */
        state.value = layout.value;
        state.argument = layout.product_high;
        state.flags = layout.flags;
    }

    continuation = pop_word(memory, bus, &state); /* RETF: pop IP first. */
    live_code_segment = pop_word(memory, bus, &state); /* Then pop CS. */

#if DISPLAY_SETUP_MUTATION == 3
    /* Mutant: consume the actual words, then pretend RETF used its nominal
       target and same segment. */
    continuation = CS_DisplaySetupAfterLayout;
    live_code_segment = code_segment;
#else
    if (continuation != CS_DisplaySetupAfterLayout || live_code_segment != code_segment) {
        return make_result(&state, live_code_segment, continuation,
                           LMN_DISPLAY_SETUP_CHANGED_RETURN);
    }
#endif

    /* Normal execution reaches the outer RET at 4C16. */
    return make_result(&state, live_code_segment, continuation,
                       LMN_DISPLAY_SETUP_READY);
}

static LmnDisplaySetupState state_from_registers(const LmnRegs *registers) {
    LmnDisplaySetupState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnDisplaySetupState *state) {
    registers->ax = state->value;
    registers->bx = state->base_value;
    registers->cx = state->count;
    registers->dx = state->argument;
    registers->si = state->source_cursor;
    registers->di = state->output_cursor;
    registers->bp = state->frame_cursor;
    registers->ds = state->data_segment;
    registers->es = state->extra_segment;
    registers->ss = state->stack_segment;
    registers->sp = state->stack_offset;
    registers->flags = state->flags;
}

void lmn_setup_display_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnDisplaySetupEntry entry,
    const LmnVideoRestoreServices *services, const LmnRasterBus *bus) {
    LmnDisplaySetupState input = state_from_registers(registers);
    LmnDisplaySetupResult result = lmn_setup_display_core(
        memory, registers->cs, &input, entry, services, bus);

    apply_state(registers, &result.state);
    registers->cs = result.code_segment;
    registers->ip = result.continuation;
    if (result.status != LMN_DISPLAY_SETUP_READY)
        return;

    /* Outer near RET reads the actual live SS:SP word after all child effects. */
    {
        LmnDisplaySetupState state = result.state;
        registers->ip = pop_word(memory, bus, &state);
        registers->sp = state.stack_offset;
    }
}

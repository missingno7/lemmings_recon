#include "fatal_cleanup.h"
#include "lemmings_sym.h"

#ifndef FATAL_CLEANUP_MUTATION
#define FATAL_CLEANUP_MUTATION 0
#endif

enum {
    FLAG_CF = 0x0001,
    FLAG_PF = 0x0004,
    FLAG_AF = 0x0010,
    FLAG_ZF = 0x0040,
    FLAG_SF = 0x0080,
    FLAG_OF = 0x0800,
    ARITHMETIC_FLAGS = 0x08d5
};

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static uint8_t read_byte(uint8_t *memory, const LmnRasterBus *bus,
                         uint32_t address, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->read_byte)
        return bus->read_byte(bus->context, memory, address, flags);
    return memory[address];
}

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset, uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static void write_word(uint8_t *memory, const LmnRasterBus *bus,
                       uint16_t segment, uint16_t offset, uint16_t value,
                       uint16_t flags) {
    uint32_t address = physical(segment, offset);
    write_byte(memory, bus, address, (uint8_t)value, flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), flags);
}

#if FATAL_CLEANUP_MUTATION == 2
static uint8_t direct_byte(const uint8_t *memory, uint32_t address) {
    return memory[address & 0xfffffu];
}
#endif

static void push_near_call(uint8_t *memory, const LmnRasterBus *bus,
                           LmnFatalCleanupState *state,
                           uint16_t continuation) {
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    write_word(memory, bus, state->stack_segment, state->stack_offset,
               continuation, state->flags);
}

static uint16_t consume_near_return(uint8_t *memory, const LmnRasterBus *bus,
                                    LmnFatalCleanupState *state) {
    uint16_t target = read_word(memory, bus, state->stack_segment,
                                state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return target;
}

static int changed_return(uint16_t actual, uint16_t expected) {
#if FATAL_CLEANUP_MUTATION == 3
    (void)actual;
    (void)expected;
    return 0;
#else
    return actual != expected;
#endif
}

static int even_parity(uint8_t value) {
    unsigned ones = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        ones += (value >> bit) & 1u;
    return (ones & 1u) == 0;
}

static uint16_t compare_ff_flags(uint16_t flags, uint8_t value) {
    uint8_t result = (uint8_t)(value - 0xffu);
    uint16_t out = (uint16_t)(flags & (uint16_t)~ARITHMETIC_FLAGS);

    if (value < 0xffu)
        out |= FLAG_CF;
    if (((value ^ 0xffu ^ result) & 0x10u) != 0)
        out |= FLAG_AF;
    if (even_parity(result))
        out |= FLAG_PF;
    if (result == 0)
        out |= FLAG_ZF;
    if (result & 0x80u)
        out |= FLAG_SF;
    if (((value ^ 0xffu) & (value ^ result) & 0x80u) != 0)
        out |= FLAG_OF;
    return out;
}

static uint16_t xor_zero_flags(uint16_t flags) {
    /* XOR defines CF/OF/PF/ZF/SF. AF is undefined, so preserve its old bit. */
    uint16_t out = (uint16_t)(flags &
        (uint16_t)~(FLAG_CF | FLAG_PF | FLAG_ZF | FLAG_SF | FLAG_OF));
    return (uint16_t)(out | FLAG_PF | FLAG_ZF);
}

static LmnTimerRestoreState timer_state_from_fatal(
    const LmnFatalCleanupState *state) {
    LmnTimerRestoreState out = {
        state->value, state->base_value, state->count, state->argument,
        state->source_cursor, state->output_cursor, state->frame_cursor,
        state->data_segment, state->extra_segment, state->stack_segment,
        state->stack_offset, state->flags
    };
    return out;
}

static LmnFatalCleanupState fatal_state_from_timer(
    const LmnTimerRestoreState *state) {
    LmnFatalCleanupState out = {
        state->value, state->base_value, state->count, state->argument,
        state->source_cursor, state->output_cursor, state->frame_cursor,
        state->data_segment, state->extra_segment, state->stack_segment,
        state->stack_offset, state->flags
    };
    return out;
}

static LmnVideoRestoreState video_state_from_fatal(
    const LmnFatalCleanupState *state) {
    LmnVideoRestoreState out = {
        state->value, state->base_value, state->count, state->argument,
        state->source_cursor, state->output_cursor, state->frame_cursor,
        state->data_segment, state->extra_segment, state->stack_segment,
        state->stack_offset, state->flags
    };
    return out;
}

static LmnFatalCleanupState fatal_state_from_video(
    const LmnVideoRestoreState *state) {
    LmnFatalCleanupState out = {
        state->value, state->base_value, state->count, state->argument,
        state->source_cursor, state->output_cursor, state->frame_cursor,
        state->data_segment, state->extra_segment, state->stack_segment,
        state->stack_offset, state->flags
    };
    return out;
}

static LmnFatalCleanupState call_mouse(
    const LmnFatalCleanupServices *services, uint8_t *memory,
    const LmnFatalCleanupState *input) {
    LmnFatalCleanupState out = *input;
    services->disable_mouse(services->context, memory, input, &out);
    return out;
}

static LmnFatalCleanupState call_write_message(
    const LmnFatalCleanupServices *services, uint8_t *memory,
    const LmnFatalCleanupState *input) {
    LmnFatalCleanupState out = *input;
    services->write_message(services->context, memory, input, &out);
    return out;
}

static LmnFatalCleanupState state_from_registers(const LmnRegs *registers) {
    LmnFatalCleanupState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnFatalCleanupState *state) {
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

static LmnFatalCleanupResult result(const LmnFatalCleanupState *state,
    uint16_t continuation, enum LmnFatalCleanupStatus status) {
    LmnFatalCleanupResult out = { *state, continuation, status };
    return out;
}

LmnFatalCleanupResult lmn_fatal_cleanup_core(uint8_t *memory,
    const LmnFatalCleanupState *input, unsigned suffix,
    const LmnFatalCleanupServices *services, const LmnRasterBus *bus) {
    LmnFatalCleanupState state = *input;
#if FATAL_CLEANUP_MUTATION == 2
    uint8_t cached_gate = 0;
    if (suffix == 0)
        cached_gate = direct_byte(memory,
            physical(input->data_segment, SEG09A9_MouseServicesDisabledByte));
#endif

    if (suffix == 0) {
        LmnTimerRestoreState timer_input;
        LmnTimerRestoreResult timer_result;
        uint16_t actual_target;

        push_near_call(memory, bus, &state, CS_CleanupAfterTimer);
        timer_input = timer_state_from_fatal(&state);
        timer_result = lmn_restore_timer_state_core(
            memory, &timer_input, services ? services->timer : 0, bus);
        state = fatal_state_from_timer(&timer_result.state);
        if (timer_result.status != LMN_TIMER_RESTORE_READY)
            return result(&state, timer_result.continuation,
                          LMN_FATAL_CLEANUP_MISSING_PROVIDER);
        actual_target = consume_near_return(memory, bus, &state);
        if (changed_return(actual_target, CS_CleanupAfterTimer))
            return result(&state, actual_target,
                          LMN_FATAL_CLEANUP_CHANGED_RETURN);

        push_near_call(memory, bus, &state, CS_CleanupAfterKeyboard);
        {
            LmnVectorRestoreResult child = lmn_restore_keyboard_vector_core(
                memory, &state, services ? services->vectors : 0, bus);
            state = child.state;
            if (child.status != LMN_VECTOR_RESTORE_READY)
                return result(&state, child.continuation,
                              LMN_FATAL_CLEANUP_MISSING_PROVIDER);
        }
        actual_target = consume_near_return(memory, bus, &state);
        if (changed_return(actual_target, CS_CleanupAfterKeyboard))
            return result(&state, actual_target,
                          LMN_FATAL_CLEANUP_CHANGED_RETURN);

        push_near_call(memory, bus, &state, CS_CleanupAfterPrivate);
        {
            LmnVectorRestoreResult child = lmn_restore_private_vector_core(
                memory, &state, services ? services->vectors : 0, bus);
            state = child.state;
            if (child.status != LMN_VECTOR_RESTORE_READY)
                return result(&state, child.continuation,
                              LMN_FATAL_CLEANUP_MISSING_PROVIDER);
        }
        actual_target = consume_near_return(memory, bus, &state);
        if (changed_return(actual_target, CS_CleanupAfterPrivate))
            return result(&state, actual_target,
                          LMN_FATAL_CLEANUP_CHANGED_RETURN);

        push_near_call(memory, bus, &state, CS_CleanupAfterVideo);
        {
            LmnVideoRestoreState video_input;
            LmnVideoRestoreResult child;
            video_input = video_state_from_fatal(&state);
            child = lmn_restore_video_mode_page_core(
                memory, &video_input, services ? services->video : 0, bus);
            state = fatal_state_from_video(&child.state);
            if (child.status != LMN_VIDEO_RESTORE_READY)
                return result(&state, child.continuation,
                              LMN_FATAL_CLEANUP_MISSING_PROVIDER);
        }
        actual_target = consume_near_return(memory, bus, &state);
        if (changed_return(actual_target, CS_CleanupAfterVideo))
            return result(&state, actual_target,
                          LMN_FATAL_CLEANUP_CHANGED_RETURN);

        {
            uint8_t live_gate = read_byte(memory, bus,
                physical(state.data_segment,
                         SEG09A9_MouseServicesDisabledByte), state.flags);
#if FATAL_CLEANUP_MUTATION == 2
            /* Keep the ordinary live bus read in its ordered position, but
               compare the entry-DS byte cached before the child calls. */
            (void)live_gate;
            live_gate = cached_gate;
#endif
            state.flags = compare_ff_flags(state.flags, live_gate);
            if (live_gate != 0xffu) {
                state.value = 0x000cu;
                state.count = 0;
                state.flags = xor_zero_flags(state.flags);
                if (!services || !services->disable_mouse)
                    return result(&state, CS_CleanupMouseInterrupt,
                                  LMN_FATAL_CLEANUP_MISSING_PROVIDER);
                state = call_mouse(services, memory, &state);
            }
        }
    }

#if FATAL_CLEANUP_MUTATION == 1
    /* Mutant: omit only the second keyboard CALL at 04EA. */
#else
    {
        LmnVectorRestoreResult child;
        uint16_t actual_target;
        push_near_call(memory, bus, &state, CS_CleanupAfterFinalKeyboard);
        child = lmn_restore_keyboard_vector_core(
            memory, &state, services ? services->vectors : 0, bus);
        state = child.state;
        if (child.status != LMN_VECTOR_RESTORE_READY)
            return result(&state, child.continuation,
                          LMN_FATAL_CLEANUP_MISSING_PROVIDER);
        actual_target = consume_near_return(memory, bus, &state);
        if (changed_return(actual_target, CS_CleanupAfterFinalKeyboard))
            return result(&state, actual_target,
                          LMN_FATAL_CLEANUP_CHANGED_RETURN);
    }
#endif

    /* MOV DX,20ACh; MOV AH,09h; INT 21h. */
    state.argument = SEG09A9_CleanupExitMessage;
    state.value = (uint16_t)((state.value & 0x00ffu) | 0x0900u);
    if (!services || !services->write_message)
        return result(&state, CS_CleanupMessageInterrupt,
                      LMN_FATAL_CLEANUP_MISSING_PROVIDER);
#if FATAL_CLEANUP_MUTATION == 4
    {
        uint16_t pre_dos_stack_segment = state.stack_segment;
        uint16_t pre_dos_stack_offset = state.stack_offset;
        state = call_write_message(services, memory, &state);
        state.stack_segment = pre_dos_stack_segment;
        state.stack_offset = pre_dos_stack_offset;
    }
#else
    state = call_write_message(services, memory, &state);
#endif

    /* MOV AX,4C00h; terminal INT 21h. */
    state.value = 0x4c00u;
    if (!services || !services->terminate)
        return result(&state, CS_CleanupTerminateInterrupt,
                      LMN_FATAL_CLEANUP_MISSING_PROVIDER);
    services->terminate(services->context, memory, &state);
    return result(&state, CS_CleanupAfterTerminate,
                  LMN_FATAL_CLEANUP_TERMINATED);
}

void lmn_fatal_cleanup_adapter(uint8_t *memory, LmnRegs *registers,
    unsigned suffix, const LmnFatalCleanupServices *services,
    const LmnRasterBus *bus) {
    LmnFatalCleanupState input = state_from_registers(registers);
    LmnFatalCleanupResult out = lmn_fatal_cleanup_core(
        memory, &input, suffix, services, bus);
    apply_state(registers, &out.state);
    registers->ip = out.continuation;
}

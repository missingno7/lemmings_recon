#include "file_error.h"
#include "lemmings_sym.h"

#ifndef FILE_ERROR_MUTATION
#define FILE_ERROR_MUTATION 0
#endif

enum {
    FLAG_CF = 0x0001,
    FLAG_PF = 0x0004,
    FLAG_AF = 0x0010,
    FLAG_ZF = 0x0040,
    FLAG_SF = 0x0080,
    FLAG_OF = 0x0800,
    INC_ARITHMETIC_FLAGS = FLAG_PF | FLAG_AF | FLAG_ZF | FLAG_SF | FLAG_OF,
    AND_DEFINED_FLAGS = FLAG_CF | FLAG_PF | FLAG_ZF | FLAG_SF | FLAG_OF
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

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset, uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      LmnFileErrorState *state, uint16_t value) {
    uint32_t address;
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    address = physical(state->stack_segment, state->stack_offset);
    write_byte(memory, bus, address, (uint8_t)value, state->flags);
    write_byte(memory, bus, address + 1u, (uint8_t)(value >> 8), state->flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         LmnFileErrorState *state) {
    uint16_t value = read_word(memory, bus, state->stack_segment,
                               state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return value;
}

static int even_parity(uint8_t value) {
    unsigned ones = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        ones += (value >> bit) & 1u;
    return (ones & 1u) == 0;
}

static uint16_t and_self_flags(uint16_t flags, uint8_t value) {
    uint16_t out = (uint16_t)(flags & (uint16_t)~AND_DEFINED_FLAGS);
    if (even_parity(value))
        out |= FLAG_PF;
    if (value == 0)
        out |= FLAG_ZF;
    if (value & 0x80u)
        out |= FLAG_SF;
    /* AF is undefined for AND; retain its prior value as the chosen model. */
    return out;
}

static uint16_t increment_word_flags(uint16_t flags, uint16_t value) {
    uint16_t result = (uint16_t)(value + 1u);
    uint16_t out = (uint16_t)(flags & (uint16_t)~INC_ARITHMETIC_FLAGS);
    uint8_t low = (uint8_t)result;

    /* INC preserves CF; AF is carry from bit 3 and OF is 7FFF -> 8000. */
    if ((value & 0x000fu) == 0x000fu)
        out |= FLAG_AF;
    if (value == 0x7fffu)
        out |= FLAG_OF;
    if (even_parity(low))
        out |= FLAG_PF;
    if (result == 0)
        out |= FLAG_ZF;
    if (result & 0x8000u)
        out |= FLAG_SF;
    return out;
}

static LmnFileErrorState call_message(const LmnFileErrorServices *services,
    uint8_t *memory, const LmnFileErrorState *input) {
    LmnFileErrorState out = *input;
    services->write_message(services->context, memory, input, &out);
    return out;
}

static LmnFileErrorState call_character(const LmnFileErrorServices *services,
    uint8_t *memory, const LmnFileErrorState *input) {
    LmnFileErrorState out = *input;
    services->write_character(services->context, memory, input, &out);
    return out;
}

static LmnVideoRestoreState video_state_from_file(
    const LmnFileErrorState *state) {
    LmnVideoRestoreState out = {
        state->value, state->base_value, state->count, state->argument,
        state->source_cursor, state->output_cursor, state->frame_cursor,
        state->data_segment, state->extra_segment, state->stack_segment,
        state->stack_offset, state->flags
    };
    return out;
}

static LmnFileErrorState file_state_from_video(
    const LmnVideoRestoreState *state) {
    LmnFileErrorState out = {
        state->value, state->base_value, state->count, state->argument,
        state->source_cursor, state->output_cursor, state->frame_cursor,
        state->data_segment, state->extra_segment, state->stack_segment,
        state->stack_offset, state->flags
    };
    return out;
}

static LmnFileErrorResult result(const LmnFileErrorState *state,
    uint16_t continuation, enum LmnFileErrorStatus status) {
    LmnFileErrorResult out = { *state, continuation, status };
    return out;
}

LmnFileErrorResult lmn_file_error_core(uint8_t *memory,
    uint16_t main_data_segment, const LmnFileErrorState *input,
    const LmnFileErrorServices *services, const LmnRasterBus *bus) {
    LmnFileErrorState state = *input;
#if FILE_ERROR_MUTATION == 1
    uint16_t entry_dx = input->argument;
#endif
#if FILE_ERROR_MUTATION == 2
    uint16_t cached_filename_offset;
#endif

    /* PUSH DX; MOV DX,main-data-segment; MOV DS,DX; CALL 0FF8. */
    push_word(memory, bus, &state, state.argument);
    state.argument = main_data_segment;
    state.data_segment = state.argument;
    push_word(memory, bus, &state, CS_FileErrorAfterVideo);
    {
        LmnVideoRestoreState video_input = video_state_from_file(&state);
        LmnVideoRestoreResult child = lmn_restore_video_mode_page_core(
            memory, &video_input, services ? services->video : 0, bus);
        uint16_t actual_target;
        state = file_state_from_video(&child.state);
        if (child.status != LMN_VIDEO_RESTORE_READY)
            return result(&state, child.continuation,
                          LMN_FILE_ERROR_MISSING_PROVIDER);

        /* The CALL's RET reads the provider-returned live SS:SP. */
        actual_target = pop_word(memory, bus, &state);
        if (actual_target != CS_FileErrorAfterVideo)
            return result(&state, actual_target,
                          LMN_FILE_ERROR_CHANGED_RETURN);
    }

    /* POP DX observes the current live stack, including provider changes. */
    {
        uint16_t popped_dx = pop_word(memory, bus, &state);
#if FILE_ERROR_MUTATION == 1
        (void)popped_dx;
        state.argument = entry_dx;
#else
        state.argument = popped_dx;
#endif
    }

    /* MOV AH,09h; INT 21h. */
    state.value = (uint16_t)((state.value & 0x00ffu) | 0x0900u);
    if (!services || !services->write_message)
        return result(&state, CS_FileErrorMessageInterrupt,
                      LMN_FILE_ERROR_MISSING_PROVIDER);
    state = call_message(services, memory, &state);

    /* MOV AH,02h; MOV DL,20h; INT 21h. */
    state.value = (uint16_t)((state.value & 0x00ffu) | 0x0200u);
    state.argument = (uint16_t)((state.argument & 0xff00u) | 0x0020u);
#if FILE_ERROR_MUTATION == 2
    cached_filename_offset = read_word(memory, bus, state.data_segment,
        SEG09A9_LastResourceFilenameOffset, state.flags);
#endif
    if (!services || !services->write_character)
        return result(&state, CS_FileErrorSpaceInterrupt,
                      LMN_FILE_ERROR_MISSING_PROVIDER);
    state = call_character(services, memory, &state);

    /* MOV BX,[DS:LastResourceFilenameOffset] happens after DOS AH=02h. */
    state.base_value = read_word(memory, bus, state.data_segment,
                                 SEG09A9_LastResourceFilenameOffset,
                                 state.flags);
#if FILE_ERROR_MUTATION == 2
    state.base_value = cached_filename_offset;
#endif

    for (;;) {
        uint8_t character = read_byte(memory, bus,
            physical(state.data_segment, state.base_value), state.flags);
        state.argument = (uint16_t)((state.argument & 0xff00u) | character);
        state.flags = and_self_flags(state.flags, character);
        if (character == 0)
            break;

        {
            uint16_t old_bx = state.base_value;
            state.base_value = (uint16_t)(old_bx + 1u);
            state.flags = increment_word_flags(state.flags, old_bx);
        }
        state.value = (uint16_t)((state.value & 0x00ffu) | 0x0200u);
#if FILE_ERROR_MUTATION == 3
        uint16_t pre_character_ds = state.data_segment;
        uint16_t pre_character_bx = state.base_value;
#endif
        if (!services || !services->write_character)
            return result(&state, CS_FileErrorCharacterInterrupt,
                          LMN_FILE_ERROR_MISSING_PROVIDER);
        state = call_character(services, memory, &state);
#if FILE_ERROR_MUTATION == 3
        state.data_segment = pre_character_ds;
        state.base_value = pre_character_bx;
#endif
    }

    /* MOV DL,0Dh; MOV AH,02h; INT 21h. */
    state.argument = (uint16_t)((state.argument & 0xff00u) | 0x000du);
    state.value = (uint16_t)((state.value & 0x00ffu) | 0x0200u);
    if (!services || !services->write_character)
        return result(&state, CS_FileErrorCrInterrupt,
                      LMN_FILE_ERROR_MISSING_PROVIDER);
    state = call_character(services, memory, &state);

    /* MOV DL,0Ah; MOV AH,02h; INT 21h. */
    state.argument = (uint16_t)((state.argument & 0xff00u) | 0x000au);
    state.value = (uint16_t)((state.value & 0x00ffu) | 0x0200u);
    if (!services || !services->write_character)
        return result(&state, CS_FileErrorLfInterrupt,
                      LMN_FILE_ERROR_MISSING_PROVIDER);
    state = call_character(services, memory, &state);

    /* The original JMP enters 04EA directly; it creates no CALL return word. */
#if FILE_ERROR_MUTATION == 4
    push_word(memory, bus, &state,
              (uint16_t)(CS_FileErrorCleanupTail + 3u));
#endif
    {
        LmnFatalCleanupResult child = lmn_fatal_cleanup_core(memory, &state, 1,
            services ? services->cleanup : 0, bus);
        return result(&child.state, child.continuation,
                      (enum LmnFileErrorStatus)child.status);
    }
}

static LmnFileErrorState state_from_registers(const LmnRegs *registers) {
    LmnFileErrorState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnFileErrorState *state) {
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

void lmn_file_error_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnFileErrorServices *services, const LmnRasterBus *bus) {
    uint32_t operand_address = physical(registers->cs,
                                        CS_FileErrorDataSegmentOperand);
    /* Instruction fetches are direct RAM reads, outside the CPU data bus. */
    uint16_t main_data_segment = (uint16_t)(memory[operand_address] |
        ((uint16_t)memory[(operand_address + 1u) & 0xfffffu] << 8));
    LmnFileErrorState input = state_from_registers(registers);
    LmnFileErrorResult out = lmn_file_error_core(memory, main_data_segment,
                                                 &input, services, bus);
    apply_state(registers, &out.state);
    registers->ip = out.continuation;
}

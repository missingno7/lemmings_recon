#include "display_start.h"
#include "lemmings_sym.h"

#ifndef DISPLAY_START_MUTATION
#define DISPLAY_START_MUTATION 0
#endif

enum { CF = 0x0001, PF = 0x0004, AF = 0x0010, ZF = 0x0040,
       SF = 0x0080, IF = 0x0200, OF = 0x0800,
       INC_ARITHMETIC_FLAGS = CF | PF | AF | ZF | SF | OF };

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

/* Word operands use the physical successor byte, including offset FFFF. */
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

/* CALL/RET use wrapping 16-bit SP and preserve the original low/high order. */
static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      uint16_t stack_segment, uint16_t *stack_offset,
                      uint16_t value, uint16_t flags) {
    *stack_offset = (uint16_t)(*stack_offset - 2u);
    write_word(memory, bus, stack_segment, *stack_offset, value, flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         uint16_t stack_segment, uint16_t *stack_offset,
                         uint16_t flags) {
    uint16_t value = read_word(memory, bus, stack_segment, *stack_offset,
                               flags);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

static uint16_t inc8_flags(uint16_t flags, uint8_t before, uint8_t after) {
    unsigned parity = 0u;
    unsigned bit;
    uint16_t defined = 0u;

    for (bit = 0u; bit < 8u; ++bit)
        parity ^= (after >> bit) & 1u;
    if (!parity)
        defined |= PF;
    if (after == 0u)
        defined |= ZF;
    if (after & 0x80u)
        defined |= SF;
    if ((before & 0x0fu) == 0x0fu)
        defined |= AF;
    if (before == 0x7fu)
        defined |= OF;

    /* INC defines all arithmetic flags except CF, which it preserves. */
    return (uint16_t)((flags & (uint16_t)~(INC_ARITHMETIC_FLAGS & (uint16_t)~CF)) |
                      defined | (flags & CF));
}

static LmnDisplayStartResult make_result(const LmnDisplayStartState *state,
                                         uint16_t continuation,
                                         enum LmnDisplayStartStatus status) {
    LmnDisplayStartResult result = { *state, continuation, status };
    return result;
}

/* 4C36..4C46, stopping before the shared RET. */
static LmnDisplayStartResult run_shared_output(
    uint8_t *memory, LmnDisplayStartState *state, const LmnRasterBus *bus) {
    uint8_t before;

    /* CLI; MOV DX,[DS:1FDA]; MOV AH,BH; MOV AL,0C. */
    state->flags &= (uint16_t)~IF;
    state->argument = read_word(memory, bus, state->data_segment,
        SEG09A9_DisplayControllerBasePort, state->flags);
    state->value = (uint16_t)((state->base_value & 0xff00u) | 0x000cu);

    if (!bus || !bus->out_word)
        return make_result(state, CS_DisplayStartFirstOutput,
                           LMN_DISPLAY_START_MISSING_PORT);

    /* OUT DX,AX. Providers may change canonical memory/device state, but not
       the CPU registers represented by this state. */
    bus->out_word(bus->context, state->argument, state->value, state->flags);

#if DISPLAY_START_MUTATION == 2
    /* Mutant: replace the live BL from the original BX with a fresh word. */
    state->base_value = read_word(memory, bus, state->data_segment,
        SEG09A9_AlternateDrawingOrigin, state->flags);
#endif

    /* MOV AH,BL; INC AL. DX and BX are not re-read by the original code. */
    state->value = (uint16_t)(((state->base_value & 0x00ffu) << 8) |
                              (state->value & 0x00ffu));
    state->value = (uint16_t)((state->value & 0xff00u) |
                              (uint8_t)(state->value + 1u));
    before = 0x0cu;
    state->flags = inc8_flags(state->flags, before,
                              (uint8_t)state->value);

    /* The second OUT reuses the exact DX computed before the first one. */
    bus->out_word(bus->context, state->argument, state->value, state->flags);

#if DISPLAY_START_MUTATION != 1
    /* STI is unconditional, including when entry IF was clear. */
    state->flags |= IF;
#endif

    return make_result(state, CS_DisplayStartReturn, LMN_DISPLAY_START_READY);
}

LmnDisplayStartResult lmn_program_display_start_core(
    uint8_t *memory, const LmnDisplayStartState *input,
    enum LmnDisplayStartEntry entry, const LmnRasterBus *bus) {
    LmnDisplayStartState state = *input;
    LmnDisplayStartResult child;
    uint16_t target;

    if (entry == LMN_DISPLAY_START_ENTRY_VALUE)
        return run_shared_output(memory, &state, bus);

    if (entry == LMN_DISPLAY_START_ENTRY_SAVED) {
        /* 4C32 reads the alternate origin into BX, then falls into 4C36. */
        state.base_value = read_word(memory, bus, state.data_segment,
            SEG09A9_AlternateDrawingOrigin, state.flags);
        return run_shared_output(memory, &state, bus);
    }

    /* 4C20 reads the primary origin into BX before CALL 4C36. */
    state.base_value = read_word(memory, bus, state.data_segment,
        SEG09A9_DrawingOrigin, state.flags);
#if DISPLAY_START_MUTATION == 3
    {
        /* Mutant caches both origins before callbacks can alter canonical RAM. */
        uint16_t cached_primary = state.base_value;
        uint16_t cached_alternate = read_word(memory, bus,
            state.data_segment, SEG09A9_AlternateDrawingOrigin, state.flags);
#endif

        push_word(memory, bus, state.stack_segment, &state.stack_offset,
                  CS_DisplaySwapAfterProgram, state.flags);
        child = run_shared_output(memory, &state, bus);
        state = child.state;
        if (child.status != LMN_DISPLAY_START_READY)
            return child; /* Keep the child frame if the provider is absent. */

        /* RET at 4C46 consumes the actual CALL word after provider effects. */
        target = pop_word(memory, bus, state.stack_segment,
                                      &state.stack_offset, state.flags);
        if (target != CS_DisplaySwapAfterProgram) {
#if DISPLAY_START_MUTATION != 4
            return make_result(&state, target,
                               LMN_DISPLAY_START_CHANGED_RETURN);
#endif
        }

        /* MOV AX,[DS:1F76]; XCHG [DS:1F78],AX; MOV [DS:1F76],AX. */
#if DISPLAY_START_MUTATION == 3
        state.value = cached_primary;
        write_word(memory, bus, state.data_segment,
            SEG09A9_AlternateDrawingOrigin, state.value, state.flags);
        state.value = cached_alternate;
#else
        state.value = read_word(memory, bus, state.data_segment,
            SEG09A9_DrawingOrigin, state.flags);
        {
            uint16_t old_alternate = read_word(memory, bus,
                state.data_segment, SEG09A9_AlternateDrawingOrigin,
                state.flags);
            write_word(memory, bus, state.data_segment,
                SEG09A9_AlternateDrawingOrigin, state.value, state.flags);
            state.value = old_alternate;
        }
#endif
        write_word(memory, bus, state.data_segment,
            SEG09A9_DrawingOrigin, state.value, state.flags);
        return make_result(&state, CS_DisplaySwapReturn,
                           LMN_DISPLAY_START_READY);
#if DISPLAY_START_MUTATION == 3
    }
#endif
}

static LmnDisplayStartState state_from_registers(const LmnRegs *registers) {
    LmnDisplayStartState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnDisplayStartState *state) {
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

void lmn_program_display_start_adapter(uint8_t *memory, LmnRegs *registers,
    enum LmnDisplayStartEntry entry, const LmnRasterBus *bus) {
    LmnDisplayStartState input = state_from_registers(registers);
    LmnDisplayStartResult result = lmn_program_display_start_core(
        memory, &input, entry, bus);

    apply_state(registers, &result.state);
    registers->ip = result.continuation;
    if (result.status != LMN_DISPLAY_START_READY)
        return;

    /* The public subroutine's final RET is distinct from SWAP's child RET. */
    registers->ip = pop_word(memory, bus, registers->ss, &registers->sp,
                             registers->flags);
}

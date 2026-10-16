#include "palette_ports.h"
#include "lemmings_sym.h"

#ifndef PALETTE_PORTS_MUTATION
#define PALETTE_PORTS_MUTATION 0
#endif
#ifndef PALETTE_TIMER_MUTATION
#define PALETTE_TIMER_MUTATION 0
#endif

enum { CF = 0x0001, PF = 0x0004, AF = 0x0010, ZF = 0x0040,
       SF = 0x0080, IF = 0x0200, DF = 0x0400, OF = 0x0800,
       ARITHMETIC_FLAGS = 0x08d5 };

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

/* The high byte of a word operand uses the physical successor, including at
   offset FFFF; only the separately modeled SP wraps as a 16-bit register. */
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

static uint16_t szp8(uint8_t value) {
    unsigned parity = 0u;
    unsigned bit;
    uint16_t result = 0u;
    for (bit = 0u; bit < 8u; ++bit)
        parity ^= (value >> bit) & 1u;
    if (!parity)
        result |= PF;
    if (value == 0u)
        result |= ZF;
    if (value & 0x80u)
        result |= SF;
    return result;
}

/* Word parity is still the parity of the low byte, as on the 8086. */
static uint16_t szp16(uint16_t value) {
    uint16_t result = szp8((uint8_t)value);
    if (value == 0u)
        result |= ZF;
    else
        result &= (uint16_t)~ZF;
    if (value & 0x8000u)
        result |= SF;
    else
        result &= (uint16_t)~SF;
    return result;
}

#if PALETTE_PORTS_MUTATION != 1
static uint8_t add8_flags(uint16_t *flags, uint8_t left, uint8_t right) {
    uint16_t sum = (uint16_t)left + (uint16_t)right;
    uint8_t value = (uint8_t)sum;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
        szp8(value) | (sum > 0xffu ? CF : 0u) |
        (((left ^ right ^ value) & 0x10u) ? AF : 0u) |
        (((uint8_t)~(left ^ right) & (left ^ value) & 0x80u) ? OF : 0u));
    return value;
}
#endif

static uint16_t add16_flags(uint16_t *flags, uint16_t left,
                            uint16_t right) {
    uint32_t sum = (uint32_t)left + (uint32_t)right;
    uint16_t value = (uint16_t)sum;
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
        szp16(value) | (sum > 0xffffu ? CF : 0u) |
        (((left ^ right ^ value) & 0x0010u) ? AF : 0u) |
        (((uint16_t)~(left ^ right) & (left ^ value) & 0x8000u) ? OF : 0u));
    return value;
}

static uint8_t sub8_flags(uint16_t *flags, uint8_t left, uint8_t right) {
    uint8_t value = (uint8_t)(left - right);
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
        szp8(value) | (left < right ? CF : 0u) |
        (((left ^ right ^ value) & 0x10u) ? AF : 0u) |
        (((left ^ right) & (left ^ value) & 0x80u) ? OF : 0u));
    return value;
}

static uint16_t sub16_flags(uint16_t *flags, uint16_t left,
                            uint16_t right) {
    uint16_t value = (uint16_t)(left - right);
    *flags = (uint16_t)((*flags & (uint16_t)~ARITHMETIC_FLAGS) |
        szp16(value) | (left < right ? CF : 0u) |
        (((left ^ right ^ value) & 0x0010u) ? AF : 0u) |
        (((left ^ right) & (left ^ value) & 0x8000u) ? OF : 0u));
    return value;
}

static void logic8_flags(uint16_t *flags, uint8_t value) {
    /* AF is undefined for these logical instructions; preserve its prior bit. */
    *flags = (uint16_t)((*flags & (uint16_t)~(CF | PF | ZF | SF | OF)) |
                        szp8(value));
}

static uint8_t inc8(LmnPalettePortsState *state, uint8_t before) {
    uint8_t value = (uint8_t)(before + 1u);
    uint16_t changed = (uint16_t)(szp8(value) |
        ((before & 0x0fu) == 0x0fu ? AF : 0u) |
        (before == 0x7fu ? OF : 0u));
    state->flags = (uint16_t)((state->flags &
        (uint16_t)~(PF | AF | ZF | SF | OF)) | changed);
    return value;
}

static uint16_t inc16(LmnPalettePortsState *state, uint16_t before) {
    uint16_t value = (uint16_t)(before + 1u);
    uint16_t changed = (uint16_t)(szp16(value) |
        ((before & 0x000fu) == 0x000fu ? AF : 0u) |
        (before == 0x7fffu ? OF : 0u));
    state->flags = (uint16_t)((state->flags &
        (uint16_t)~(PF | AF | ZF | SF | OF)) | changed);
    return value;
}

static uint16_t dec16(LmnPalettePortsState *state, uint16_t before) {
    uint16_t value = (uint16_t)(before - 1u);
    uint16_t changed = (uint16_t)(szp16(value) |
        ((before & 0x000fu) == 0u ? AF : 0u) |
        (before == 0x8000u ? OF : 0u));
    state->flags = (uint16_t)((state->flags &
        (uint16_t)~(PF | AF | ZF | SF | OF)) | changed);
    return value;
}

static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      LmnPalettePortsState *state, uint16_t value) {
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    write_word(memory, bus, state->stack_segment, state->stack_offset,
               value, state->flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         LmnPalettePortsState *state) {
    uint16_t value = read_word(memory, bus, state->stack_segment,
                               state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return value;
}

static uint8_t lodsb(uint8_t *memory, const LmnRasterBus *bus,
                     LmnPalettePortsState *state) {
    uint8_t value = read_byte(memory, bus,
        physical(state->data_segment, state->source_cursor), state->flags);
#if PALETTE_PORTS_MUTATION == 2
    state->source_cursor = (uint16_t)(state->source_cursor + 1u);
#else
    state->source_cursor = (uint16_t)(state->source_cursor +
        ((state->flags & DF) ? (uint16_t)-1 : 1u));
#endif
    state->value = (uint16_t)((state->value & 0xff00u) | value);
    return value;
}

static int has_input(const LmnRasterBytePorts *ports) {
    return ports && ports->in_byte;
}

static int has_output(const LmnRasterBytePorts *ports) {
    return ports && ports->out_byte;
}

static LmnPalettePortsResult result(const LmnPalettePortsState *state,
                                    uint16_t continuation,
                                    enum LmnPalettePortsStatus status) {
    LmnPalettePortsResult out = { *state, continuation, status };
    return out;
}

static LmnPalettePortsResult missing_input(
    const LmnPalettePortsState *state, uint16_t continuation) {
    return result(state, continuation, LMN_PALETTE_PORTS_MISSING_INPUT);
}

static LmnPalettePortsResult missing_output(
    const LmnPalettePortsState *state, uint16_t continuation) {
    return result(state, continuation, LMN_PALETTE_PORTS_MISSING_OUTPUT);
}

static void cli(LmnPalettePortsState *state) {
    state->flags &= (uint16_t)~IF;
}

static void sti(LmnPalettePortsState *state, uint16_t incoming_if) {
#if PALETTE_PORTS_MUTATION == 5
    state->flags = (uint16_t)((state->flags & (uint16_t)~IF) | incoming_if);
#else
    (void)incoming_if;
    state->flags |= IF;
#endif
}

static LmnPalettePortsResult write_attribute_palette(
    uint8_t *memory, LmnPalettePortsState *state,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus,
    uint16_t incoming_if) {
#if PALETTE_PORTS_MUTATION != 1
    uint8_t before;
#endif

    /* CLI; MOV BL,CH; XOR CH,CH; MOV DX,[DS:1FDA]. */
    cli(state);
    state->base_value = (uint16_t)((state->base_value & 0xff00u) |
                                   (state->count >> 8));
    state->count &= 0x00ffu;
    logic8_flags(&state->flags, 0u);
    state->argument = read_word(memory, bus, state->data_segment,
        SEG09A9_DisplayControllerBasePort, state->flags);

    /* The decoded ADD is byte-width and preserves DH. Mutant 1 widens it. */
#if PALETTE_PORTS_MUTATION != 1
    before = (uint8_t)state->argument;
#else
    state->argument = add16_flags(&state->flags, state->argument, 6u);
#endif
#if PALETTE_PORTS_MUTATION != 1
    state->argument = (uint16_t)((state->argument & 0xff00u) |
        add8_flags(&state->flags, before, 6u));
#endif
    if (!has_input(ports))
        return missing_input(state, 0x5431u);
    state->value = (uint16_t)((state->value & 0xff00u) |
        ports->in_byte(ports->context, memory, state->argument, state->flags));

    /* PUSH DX; MOV DL,C0. */
    push_word(memory, bus, state, state->argument);
    state->argument = (uint16_t)((state->argument & 0xff00u) | 0x00c0u);

    /* LOOP is a do-while count: incoming CX=0 executes 65,536 iterations. */
    do {
        state->value = (uint16_t)((state->value & 0xff00u) |
                                  (uint8_t)state->base_value);
        if (!has_output(ports))
            return missing_output(state, 0x5437u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        (void)lodsb(memory, bus, state);
        if (!has_output(ports))
            return missing_output(state, 0x5439u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        state->base_value = (uint16_t)((state->base_value & 0xff00u) |
            inc8(state, (uint8_t)state->base_value));
        state->count = (uint16_t)(state->count - 1u);
    } while (state->count != 0u);

    /* POP DX is live and may observe stack aliases written by a port provider. */
    state->argument = pop_word(memory, bus, state);
    if (!has_input(ports))
        return missing_input(state, 0x543fu);
    state->value = (uint16_t)((state->value & 0xff00u) |
        ports->in_byte(ports->context, memory, state->argument, state->flags));

    state->argument = (uint16_t)((state->argument & 0xff00u) | 0x00c0u);
    state->value = (uint16_t)((state->value & 0xff00u) | 0x0020u);
    if (!has_output(ports))
        return missing_output(state, 0x5444u);
    ports->out_byte(ports->context, memory, state->argument,
                    (uint8_t)state->value, state->flags);
    sti(state, incoming_if);
    return result(state, CS_AttributePaletteReturn5446,
                   LMN_PALETTE_PORTS_READY);
}

static uint8_t read_control(uint8_t *memory, LmnPalettePortsState *state,
                            const LmnRasterBus *bus) {
    return read_byte(memory, bus,
        physical(state->data_segment, SEG09A9_PaletteBlankingControl),
        state->flags);
}

static LmnPalettePortsResult write_mapped_dac_palette(
    uint8_t *memory, uint16_t code_segment, LmnPalettePortsState *state,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus,
    uint16_t incoming_if) {
    uint8_t initial_control;
    uint8_t control;
    uint8_t value;
#if PALETTE_PORTS_MUTATION == 3
    uint8_t second_control;
#endif
#if PALETTE_PORTS_MUTATION == 4
    uint16_t entry_di = state->output_cursor;
#endif

    /* PUSH DI precedes CLI, and CMP observes the live byte through DS. */
    push_word(memory, bus, state, state->output_cursor);
    cli(state);
    initial_control = read_control(memory, state, bus);
    (void)sub8_flags(&state->flags, initial_control, 0xffu);

    if (initial_control != 0xffu) {
        /* Select sequencer register 1 and read its live value. */
        state->argument = 0x03c4u;
        state->value = (uint16_t)((state->value & 0xff00u) | 0x0001u);
        if (!has_output(ports))
            return missing_output(state, 0x54d2u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        state->argument = inc16(state, state->argument);
        if (!has_input(ports))
            return missing_input(state, 0x54d4u);
        state->value = (uint16_t)((state->value & 0xff00u) |
            ports->in_byte(ports->context, memory, state->argument,
                           state->flags));

        value = (uint8_t)((uint8_t)state->value | 0x20u);
        logic8_flags(&state->flags, value);
        state->value = (uint16_t)((state->value & 0xff00u) | value);
        if (!has_output(ports))
            return missing_output(state, 0x54d7u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);
        push_word(memory, bus, state, state->value);
        push_word(memory, bus, state, state->argument);
    }

    /* MOV DX,3C8; MOV AL,CH; XOR AH,AH; LEA DI,5507; ADD DI,AX. */
    state->argument = 0x03c8u;
#if PALETTE_PORTS_MUTATION == 6
    state->value = (uint16_t)((state->value & 0xff00u) |
        (uint8_t)((state->count >> 8) & 0x0fu));
#else
    state->value = (uint16_t)((state->value & 0xff00u) |
                              (uint8_t)(state->count >> 8));
#endif
    state->value &= 0x00ffu; /* XOR AH,AH, retaining the MOV AL result. */
    logic8_flags(&state->flags, 0u);
    state->output_cursor = CS_MappedDacPaletteIndexes;
    state->output_cursor = add16_flags(&state->flags,
        state->output_cursor, state->value);

    /* XOR CH,CH; CX is then the live full-word LOOP count. */
    state->count &= 0x00ffu;
    logic8_flags(&state->flags, 0u);
    do {
        /* MOV AL,[CS:DI] is a fresh table read each iteration. */
        value = read_byte(memory, bus,
            physical(code_segment, state->output_cursor), state->flags);
        state->output_cursor = inc16(state, state->output_cursor);
        state->value = (uint16_t)((state->value & 0xff00u) | value);
        if (!has_output(ports))
            return missing_output(state, 0x54edu);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        state->argument = inc16(state, state->argument);
        (void)lodsb(memory, bus, state);
        if (!has_output(ports))
            return missing_output(state, 0x54f0u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        (void)lodsb(memory, bus, state);
        if (!has_output(ports))
            return missing_output(state, 0x54f2u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        (void)lodsb(memory, bus, state);
        if (!has_output(ports))
            return missing_output(state, 0x54f4u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        state->argument = dec16(state, state->argument);
        state->count = (uint16_t)(state->count - 1u);
    } while (state->count != 0u);

#if PALETTE_PORTS_MUTATION == 3
    second_control = initial_control;
    control = second_control;
#else
    control = read_control(memory, state, bus);
#endif
    (void)sub8_flags(&state->flags, control, 0xffu);
    if (control != 0xffu) {
        /* The saved DX and AX words are popped live, after the fresh CMP. */
        state->argument = pop_word(memory, bus, state);
        state->value = pop_word(memory, bus, state);
        value = (uint8_t)((uint8_t)state->value & 0xdfu);
        logic8_flags(&state->flags, value);
        state->value = (uint16_t)((state->value & 0xff00u) | value);
        if (!has_output(ports))
            return missing_output(state, 0x5503u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);
    }

    sti(state, incoming_if);
    /* POP DI consumes the actual stack word after STI. */
#if PALETTE_PORTS_MUTATION == 4
    (void)pop_word(memory, bus, state);
    state->output_cursor = entry_di;
#else
    state->output_cursor = pop_word(memory, bus, state);
#endif
    return result(state, CS_MappedDacPaletteReturn5506,
                  LMN_PALETTE_PORTS_READY);
}

/* 548C advances the DAC index sequentially. Unlike the mapped writer above,
   it has no DI table walk or outer DI save. */
static uint8_t lodsb_direct(uint8_t *memory, const LmnRasterBus *bus,
                            LmnPalettePortsState *state) {
    uint8_t value = read_byte(memory, bus,
        physical(state->data_segment, state->source_cursor), state->flags);
#if PALETTE_TIMER_MUTATION == 1
    state->source_cursor = (uint16_t)(state->source_cursor + 1u);
#else
    state->source_cursor = (uint16_t)(state->source_cursor +
        ((state->flags & DF) ? (uint16_t)-1 : 1u));
#endif
    state->value = (uint16_t)((state->value & 0xff00u) | value);
    return value;
}

static void sti_direct(LmnPalettePortsState *state, uint16_t incoming_if) {
#if PALETTE_TIMER_MUTATION == 4
    state->flags = (uint16_t)((state->flags & (uint16_t)~IF) | incoming_if);
#else
    (void)incoming_if;
    state->flags |= IF;
#endif
}

static LmnPalettePortsResult write_direct_dac_palette(
    uint8_t *memory, LmnPalettePortsState *state,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus,
    uint16_t incoming_if) {
    uint8_t initial_control;
    uint8_t control;
    uint8_t value;

    /* CLI; CMP byte [DS:200C],FF. This first read is always live. */
    cli(state);
    initial_control = read_control(memory, state, bus);
    (void)sub8_flags(&state->flags, initial_control, 0xffu);

    if (initial_control != 0xffu) {
        /* MOV DX,3C4; MOV AL,1; OUT; INC DX; IN; OR AL,20; OUT. */
        state->argument = 0x03c4u;
        state->value = (uint16_t)((state->value & 0xff00u) | 0x01u);
        if (!has_output(ports))
            return missing_output(state, 0x5499u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        state->argument = inc16(state, state->argument);
        if (!has_input(ports))
            return missing_input(state, 0x549bu);
        state->value = (uint16_t)((state->value & 0xff00u) |
            ports->in_byte(ports->context, memory, state->argument,
                           state->flags));

        value = (uint8_t)((uint8_t)state->value | 0x20u);
        logic8_flags(&state->flags, value);
        state->value = (uint16_t)((state->value & 0xff00u) | value);
        if (!has_output(ports))
            return missing_output(state, 0x549eu);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);
        push_word(memory, bus, state, state->value);
        push_word(memory, bus, state, state->argument);
    }

    /* MOV DX,3C8; MOV AL,CH; XOR CH,CH; OUT; MOV AH,AL; INC DX. */
    state->argument = 0x03c8u;
#if PALETTE_TIMER_MUTATION == 3
    state->value = (uint16_t)((state->value & 0xff00u) |
        (uint8_t)((state->count >> 8) & 0x0fu));
#else
    state->value = (uint16_t)((state->value & 0xff00u) |
                              (uint8_t)(state->count >> 8));
#endif
    state->count &= 0x00ffu;
    logic8_flags(&state->flags, 0u);
    if (!has_output(ports))
        return missing_output(state, 0x54a8u);
    ports->out_byte(ports->context, memory, state->argument,
                    (uint8_t)state->value, state->flags);
    state->value = (uint16_t)(((uint16_t)(uint8_t)state->value << 8) |
                              (uint8_t)state->value);
    state->argument = inc16(state, state->argument);

    /* LOOP is a do/while count: CL=0 runs a full 65,536 iterations. */
    do {
        (void)lodsb_direct(memory, bus, state);
        if (!has_output(ports))
            return missing_output(state, 0x54adu);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        (void)lodsb_direct(memory, bus, state);
        if (!has_output(ports))
            return missing_output(state, 0x54afu);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        (void)lodsb_direct(memory, bus, state);
        if (!has_output(ports))
            return missing_output(state, 0x54b1u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);

        value = inc8(state, (uint8_t)(state->value >> 8));
        state->value = (uint16_t)((state->value & 0x00ffu) |
                                  ((uint16_t)value << 8));
        state->count = (uint16_t)(state->count - 1u);
    } while (state->count != 0u);

#if PALETTE_TIMER_MUTATION == 2
    control = initial_control;
#else
    control = read_control(memory, state, bus);
#endif
    (void)sub8_flags(&state->flags, control, 0xffu);
    if (control != 0xffu) {
        /* The live control byte chooses whether these actual words are popped. */
        state->argument = pop_word(memory, bus, state);
        state->value = pop_word(memory, bus, state);
        value = (uint8_t)((uint8_t)state->value & 0xdfu);
        logic8_flags(&state->flags, value);
        state->value = (uint16_t)((state->value & 0xff00u) | value);
        if (!has_output(ports))
            return missing_output(state, 0x54c1u);
        ports->out_byte(ports->context, memory, state->argument,
                        (uint8_t)state->value, state->flags);
    }

    sti_direct(state, incoming_if);
    return result(state, CS_SequentialDacPaletteReturn54C3,
                  LMN_PALETTE_PORTS_READY);
}

static LmnPalettePortsState state_from_registers(const LmnRegs *registers) {
    LmnPalettePortsState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnPalettePortsState *state) {
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

LmnPalettePortsResult lmn_write_palette_ports_core(uint8_t *memory,
    uint16_t code_segment, const LmnPalettePortsState *input,
    LmnPalettePortsEntry entry, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    LmnPalettePortsState state = *input;
    uint16_t incoming_if = (uint16_t)(state.flags & IF);

    if (entry == LMN_PALETTE_PORTS_ENTRY_MAPPED_DAC)
        return write_mapped_dac_palette(memory, code_segment, &state, ports,
                                        bus, incoming_if);
    if (entry == LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC)
        return write_direct_dac_palette(memory, &state, ports, bus,
                                        incoming_if);
    return write_attribute_palette(memory, &state, ports, bus, incoming_if);
}

void lmn_write_palette_ports_adapter(uint8_t *memory, LmnRegs *registers,
    LmnPalettePortsEntry entry, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    LmnPalettePortsState input = state_from_registers(registers);
    LmnPalettePortsResult result = lmn_write_palette_ports_core(memory,
        registers->cs, &input, entry, ports, bus);

    apply_state(registers, &result.state);
    registers->ip = result.continuation;
    if (result.status != LMN_PALETTE_PORTS_READY)
        return;

    {
        uint32_t address = physical(registers->ss, registers->sp);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u,
                                 registers->flags);
        registers->sp = (uint16_t)(registers->sp + 2u);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
    }
}

static LmnTimerPaletteResult timer_result(const LmnRegs *input,
    const LmnPalettePortsState *state, uint16_t continuation,
    uint16_t status) {
    LmnTimerPaletteResult out = { *input, status };
    apply_state(&out.registers, state);
    out.registers.ip = continuation;
    return out;
}

static LmnTimerPaletteResult timer_child(uint8_t *memory,
    const LmnRegs *input, const LmnPalettePortsState *state,
    LmnPalettePortsEntry entry, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    LmnPalettePortsResult child = lmn_write_palette_ports_core(memory,
        input->cs, state, entry, ports, bus);
    return timer_result(input, &child.state, child.continuation,
                        (uint16_t)child.status);
}

LmnTimerPaletteResult lmn_timer_palette_core(uint8_t *memory,
    const LmnRegs *registers, LmnTimerPaletteEntry entry,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    LmnPalettePortsState state = state_from_registers(registers);

    if (entry == LMN_TIMER_PALETTE_ENTRY_DIRECT)
        return timer_child(memory, registers, &state,
            LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC, ports, bus);

    if (entry == LMN_TIMER_PALETTE_ENTRY_BEFORE) {
        uint16_t mode = read_word(memory, bus, state.data_segment,
            SEG09A9_PaletteDisplayModeWord, state.flags);
        (void)sub16_flags(&state.flags, mode, 4u);
        if (mode == 4u) {
            state.source_cursor = SEG09A9_TimerPaletteSource2668;
            state.count = 0x1008u;
            return timer_child(memory, registers, &state,
                LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC, ports, bus);
        }

        /* The second CMP rereads the word at DS:1F7C. */
        mode = read_word(memory, bus, state.data_segment,
            SEG09A9_PaletteDisplayModeWord, state.flags);
        (void)sub16_flags(&state.flags, mode, 2u);
        if (mode == 2u) {
            state.source_cursor = SEG09A9_TimerPaletteSource2668;
            state.count = 0x0808u;
            return timer_child(memory, registers, &state,
                LMN_PALETTE_PORTS_ENTRY_ATTRIBUTE, ports, bus);
        }

        /* The prefix's own RET is at 5484. */
        return timer_result(registers, &state, 0x5484u,
                            LMN_TIMER_PALETTE_READY);
    }

    /* MOV AX,[DS:1F7C]; CMP AX,4; CMP AX,2. */
    state.value = read_word(memory, bus, state.data_segment,
        SEG09A9_PaletteDisplayModeWord, state.flags);
    (void)sub16_flags(&state.flags, state.value, 4u);
    if (state.value == 4u) {
        LmnPalettePortsResult child;
        uint16_t returned_ip;

        state.source_cursor = SEG09A9_TimerPaletteSource2638;
        state.count = 0x0008u;
        /* CALL 548C pushes the real continuation at 5555. */
        push_word(memory, bus, &state, CS_TimerPaletteAfterFirstDac5555);
        child = lmn_write_palette_ports_core(memory, registers->cs, &state,
            LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC, ports, bus);
        if (child.status != LMN_PALETTE_PORTS_READY)
            return timer_result(registers, &child.state, child.continuation,
                                (uint16_t)child.status);

        state = child.state;
        returned_ip = pop_word(memory, bus, &state);
        if (returned_ip != CS_TimerPaletteAfterFirstDac5555 &&
            PALETTE_TIMER_MUTATION != 5)
            return timer_result(registers, &state, returned_ip,
                                LMN_TIMER_PALETTE_CHANGED_CHILD_RETURN);

        /* Continue at the instruction following the real child CALL. */
        state.source_cursor = SEG09A9_TimerPaletteSource2650;
        state.count = 0x1008u;
        return timer_child(memory, registers, &state,
            LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC, ports, bus);
    }

    (void)sub16_flags(&state.flags, state.value, 2u);
    if (state.value == 2u) {
        state.source_cursor = SEG09A9_TimerPaletteSource2638;
        state.count = 0x0010u;
        return timer_child(memory, registers, &state,
            LMN_PALETTE_PORTS_ENTRY_ATTRIBUTE, ports, bus);
    }

    /* Unsupported modes execute the prefix's own RET at 554A. */
    return timer_result(registers, &state, 0x554au,
                        LMN_TIMER_PALETTE_READY);
}

LmnTimerPaletteResult lmn_timer_palette_adapter(uint8_t *memory,
    const LmnRegs *registers, LmnTimerPaletteEntry entry,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    LmnTimerPaletteResult out = lmn_timer_palette_core(memory, registers,
        entry, ports, bus);

    if (out.status != LMN_TIMER_PALETTE_READY)
        return out;

    /* Only the active leaf/prefix RET is consumed; child CALL RETs are owned
       by the core before it continues through the caller's instructions. */
    {
        LmnPalettePortsState state = state_from_registers(&out.registers);
        out.registers.ip = pop_word(memory, bus, &state);
        apply_state(&out.registers, &state);
    }
    return out;
}

#include "mouse_irq_bridge.h"

#include "lemmings_sym.h"

#ifndef MOUSE_IRQ_BRIDGE_MUTATION
#define MOUSE_IRQ_BRIDGE_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffffu,
    CF = 0x0001u,
    PF = 0x0004u,
    AF = 0x0010u,
    ZF = 0x0040u,
    SF = 0x0080u,
    TF = 0x0100u,
    IF = 0x0200u,
    OF = 0x0800u,
    INC_DEC_FLAGS = PF | AF | ZF | SF | OF,
    ARITHMETIC_FLAGS = CF | PF | AF | ZF | SF | OF,
    LOGIC_FLAGS = CF | PF | ZF | SF | OF,
    IRET_FLAGS = 0x7fd5u,
    SOFTWARE_INT_FLAGS = TF | IF
};

typedef struct MouseIrqVector {
    uint16_t code_segment;
    uint16_t instruction_pointer;
} MouseIrqVector;

typedef struct MouseIrqState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    LmnRegs registers;
    uint16_t status;
    uint16_t service_status;
} MouseIrqState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return ((((uint32_t)segment << 4) + offset) & MEMORY_MASK);
}

static uint8_t read_byte(MouseIrqState *state, uint16_t segment,
                         uint16_t offset) {
    uint32_t address = physical(segment, offset);
    if (state->bus && state->bus->read_byte)
        return state->bus->read_byte(state->bus->context, state->memory,
                                     address, state->registers.flags);
    return state->memory[address];
}

static uint8_t read_physical_byte(MouseIrqState *state, uint32_t address,
                                  uint16_t flags) {
    address &= MEMORY_MASK;
    if (state->bus && state->bus->read_byte)
        return state->bus->read_byte(state->bus->context, state->memory,
                                     address, flags);
    return state->memory[address];
}

static void write_physical_byte(MouseIrqState *state, uint32_t address,
                                uint8_t value, uint16_t flags) {
    address &= MEMORY_MASK;
    if (state->bus && state->bus->write_byte)
        state->bus->write_byte(state->bus->context, state->memory, address,
                               value, flags);
    else
        state->memory[address] = value;
}

/* A real-mode word's high byte is the next physical byte, not wrapped EA. */
static uint16_t read_word(MouseIrqState *state, uint16_t segment,
                          uint16_t offset, uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical_byte(state, address, flags);
    uint8_t high = read_physical_byte(state, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write_word(MouseIrqState *state, uint16_t segment,
                       uint16_t offset, uint16_t value, uint16_t flags) {
    uint32_t address = physical(segment, offset);
    write_physical_byte(state, address, (uint8_t)value, flags);
    write_physical_byte(state, address + 1u, (uint8_t)(value >> 8), flags);
}

static void push_word(MouseIrqState *state, uint16_t value, uint16_t flags) {
    LmnRegs *r = &state->registers;
    r->sp = (uint16_t)(r->sp - 2u);
    write_word(state, r->ss, r->sp, value, flags);
}

static uint16_t pop_word_from(MouseIrqState *state, uint16_t segment,
                              uint16_t *stack_offset, uint16_t flags) {
    uint16_t value = read_word(state, segment, *stack_offset, flags);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

static uint16_t pop_word(MouseIrqState *state) {
    LmnRegs *r = &state->registers;
    return pop_word_from(state, r->ss, &r->sp, r->flags);
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity = 0u;
    unsigned bit;
    for (bit = 0u; bit < 8u; ++bit)
        parity ^= (unsigned)((value >> bit) & 1u);
    return parity == 0u;
}

static uint16_t szp_flags(uint8_t value) {
    uint16_t flags = 0u;
    if (even_parity8(value)) flags |= PF;
    if (value == 0u) flags |= ZF;
    if (value & 0x80u) flags |= SF;
    return flags;
}

static void inc_byte(MouseIrqState *state, uint16_t segment,
                     uint16_t offset) {
    uint8_t before = read_byte(state, segment, offset);
    uint8_t after = (uint8_t)(before + 1u);
    uint16_t defined = szp_flags(after);
    if ((before & 0x0fu) == 0x0fu) defined |= AF;
    if (before == 0x7fu) defined |= OF;
    write_physical_byte(state, physical(segment, offset), after,
                        state->registers.flags);
    state->registers.flags = (uint16_t)(
        (state->registers.flags & (uint16_t)~INC_DEC_FLAGS) | defined);
}

static void dec_byte(MouseIrqState *state, uint16_t segment,
                     uint16_t offset) {
    uint8_t before = read_byte(state, segment, offset);
    uint8_t after = (uint8_t)(before - 1u);
    uint16_t defined = szp_flags(after);
    if ((before & 0x0fu) == 0u) defined |= AF;
    if (before == 0x80u) defined |= OF;
    write_physical_byte(state, physical(segment, offset), after,
                        state->registers.flags);
    state->registers.flags = (uint16_t)(
        (state->registers.flags & (uint16_t)~INC_DEC_FLAGS) | defined);
}

static uint16_t normalize_iret_flags(uint16_t flags) {
    return (uint16_t)((flags & IRET_FLAGS) | 2u);
}

static void consume_iret(MouseIrqState *state, uint16_t segment,
                         uint16_t *stack_offset, uint16_t access_flags) {
    uint16_t ip = pop_word_from(state, segment, stack_offset, access_flags);
    uint16_t cs = pop_word_from(state, segment, stack_offset, access_flags);
    uint16_t flags = pop_word_from(state, segment, stack_offset, access_flags);
    state->registers.ip = ip;
    state->registers.cs = cs;
    state->registers.flags = normalize_iret_flags(flags);
}

static MouseIrqVector read_int62_vector(MouseIrqState *state,
                                        uint16_t flags) {
    MouseIrqVector vector;
    /* This intentionally follows the PC interrupt model's CS-before-IP reads. */
    vector.code_segment = read_word(state, 0u, 0x018au, flags);
    vector.instruction_pointer = read_word(state, 0u, 0x0188u, flags);
    return vector;
}

static LmnMouseIrqBridgeResult result_of(const MouseIrqState *state) {
    LmnMouseIrqBridgeResult result;
    result.registers = state->registers;
    result.status = state->status;
    result.service_status = state->service_status;
    return result;
}

static void set_status(MouseIrqState *state, uint16_t status) {
    state->status = status;
}

static uint16_t and_al_flags(uint16_t flags, uint8_t value) {
    uint16_t defined = szp_flags(value);
    /* AF is undefined by AND and stays opaque in this partial FLAGS model. */
    return (uint16_t)((flags & (uint16_t)~LOGIC_FLAGS) | defined);
}

static uint16_t cmp_zero_flags(uint16_t flags, uint8_t value) {
    /* CMP byte,0 has no borrow, auxiliary borrow or signed overflow. */
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) |
                      szp_flags(value));
}

LmnMouseIrqBridgeResult lmn_mouse_irq_bridge_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnMouseIrqService *service, const LmnRasterBus *bus) {
    MouseIrqState state;
    LmnRegs *r;
    uint16_t entry_cs, entry_ss, entry_ds, entry_es, entry_ax;
    uint16_t operand_segment;
    MouseIrqVector vector;
    uint8_t al;

    state.memory = memory;
    state.bus = bus;
    state.registers = *registers;
    state.status = LMN_MOUSE_IRQ_BRIDGE_READY;
    state.service_status = 0u;
    r = &state.registers;
    entry_cs = r->cs;
    entry_ss = r->ss;
    entry_ds = r->ds;
    entry_es = r->es;
    entry_ax = r->ax;
    (void)entry_ss;
    (void)entry_ds;
    (void)entry_es;
    (void)entry_ax;

#if MOUSE_IRQ_BRIDGE_MUTATION == 1
    /* Read before pushes, so an IVT/stack alias cannot replace the target. */
    vector = read_int62_vector(&state, r->flags);
#endif

    push_word(&state, r->ds, r->flags);             /* PUSH DS @0F70 */
    push_word(&state, r->ax, r->flags);             /* PUSH AX @0F71 */

    /* MOV AX,imm16 reads its relocated instruction operand from live RAM. */
    {
        uint32_t operand = physical(r->cs, CS_MouseIrqDataFrameOperand0F73);
        uint8_t low = state.memory[operand];
        uint8_t high = state.memory[(operand + 1u) & MEMORY_MASK];
        operand_segment = (uint16_t)(low | ((uint16_t)high << 8));
    }
    r->ax = operand_segment;                        /* MOV AX,imm @0F72 */
    r->ds = r->ax;                                  /* MOV DS,AX @0F75 */

    inc_byte(&state, r->ds, SEG09A9_PrivateIrqCounter2002);
    inc_byte(&state, r->ds, SEG09A9_PrivateIrqCounter2003);

    /* INT 62: push current FLAGS, clear IF/TF, then push CS and return IP. */
    {
        uint16_t entry_flags = r->flags;
        uint16_t interrupt_flags = (uint16_t)(
            entry_flags & (uint16_t)~SOFTWARE_INT_FLAGS);
        r->ip = CS_MouseIrqInt62Return;
        push_word(&state, entry_flags, entry_flags);
#if MOUSE_IRQ_BRIDGE_MUTATION == 2
        push_word(&state, CS_MouseIrqInt62Return, interrupt_flags);
        push_word(&state, r->cs, interrupt_flags);
#else
        push_word(&state, r->cs, interrupt_flags);
        push_word(&state, CS_MouseIrqInt62Return, interrupt_flags);
#endif
        r->flags = interrupt_flags;
    }

#if MOUSE_IRQ_BRIDGE_MUTATION != 1
    vector = read_int62_vector(&state, r->flags);
#endif
    r->cs = vector.code_segment;
    r->ip = vector.instruction_pointer;

    if (!service || !service->interrupt62
#if MOUSE_IRQ_BRIDGE_MUTATION != 3
        || vector.code_segment != service->code_segment
        || vector.instruction_pointer != service->instruction_pointer
#endif
       ) {
        set_status(&state, LMN_MOUSE_IRQ_BRIDGE_UNBOUND_SERVICE);
        return result_of(&state);
    }

    state.service_status = service->interrupt62(
        service->context, memory, r, bus);
    if (state.service_status != 0u) {
        set_status(&state, LMN_MOUSE_IRQ_BRIDGE_EXTERNAL_STOP);
        return result_of(&state);
    }

#if MOUSE_IRQ_BRIDGE_MUTATION == 4
    r->ds = entry_ds;
#endif
#if MOUSE_IRQ_BRIDGE_MUTATION == 5
    r->es = entry_es;
#endif

    /* External IRET consumes live SS:SP and normalizes the returned FLAGS. */
    {
        uint16_t live_ss = r->ss;
        uint16_t access_flags = r->flags;
#if MOUSE_IRQ_BRIDGE_MUTATION == 6
        live_ss = entry_ss;
#endif
        consume_iret(&state, live_ss, &r->sp, access_flags);
    }
    if (r->cs != entry_cs || r->ip != CS_MouseIrqInt62Return) {
        set_status(&state, LMN_MOUSE_IRQ_BRIDGE_CHANGED_INTERRUPT_RETURN);
        return result_of(&state);
    }

    r->ip = CS_MouseIrqInt62Return;
    dec_byte(&state, r->ds, SEG09A9_PrivateIrqCounter2003);
    dec_byte(&state, r->ds, SEG09A9_PrivateIrqCounter2002);

    al = read_byte(&state, r->cs, CS_MouseIrqMirrorGate83BE);
    r->ax = (uint16_t)((r->ax & 0xff00u) | al);     /* MOV AL,[CS:83BE] */
    r->flags = and_al_flags(r->flags, al);          /* AND AL,AL @0F8D */
    if (al != 0u) {
#if MOUSE_IRQ_BRIDGE_MUTATION != 8
        goto bridge_epilogue;
#endif
    }

    al = read_byte(&state, r->ds, SEG09A9_PrivateIrqCounter2002);
    r->flags = cmp_zero_flags(r->flags, al);        /* CMP [DS:2002],0 @0F91 */
    if (al != 0u) {
#if MOUSE_IRQ_BRIDGE_MUTATION != 8
        goto bridge_epilogue;
#endif
    }

    /* PUSH DX; CALL RestoreVgaRegisterMirrors; the child's RET is live. */
    push_word(&state, r->dx, r->flags);
    push_word(&state, CS_MouseIrqRestoreReturn, r->flags);
    r->ip = CS_RestoreVgaRegisterMirrors;
    {
        uint16_t child_status = lmn_restore_vga_register_mirrors_adapter(
            memory, r, bus);
        if (child_status != LMN_VGA_MIRRORS_READY) {
            set_status(&state, LMN_MOUSE_IRQ_BRIDGE_CHILD_STOP);
            return result_of(&state);
        }
    }
#if MOUSE_IRQ_BRIDGE_MUTATION != 9
    if (r->cs != entry_cs || r->ip != CS_MouseIrqRestoreReturn) {
        set_status(&state, LMN_MOUSE_IRQ_BRIDGE_CHANGED_CHILD_RETURN);
        return result_of(&state);
    }
#endif
    r->dx = pop_word(&state);                       /* POP DX @0F9C */

#if MOUSE_IRQ_BRIDGE_MUTATION != 8
bridge_epilogue:
#endif
    r->ip = 0x0f9du;
    r->ax = pop_word(&state);                       /* POP AX @0F9D */
#if MOUSE_IRQ_BRIDGE_MUTATION == 7
    r->ax = entry_ax;
#endif
    r->ds = pop_word(&state);                       /* POP DS @0F9E */
    r->ip = CS_MouseIrqOuterIret;
    return result_of(&state);
}

LmnMouseIrqBridgeResult lmn_mouse_irq_bridge_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnMouseIrqService *service, const LmnRasterBus *bus) {
    LmnMouseIrqBridgeResult result = lmn_mouse_irq_bridge_core(
        memory, registers, service, bus);
    if (result.status == LMN_MOUSE_IRQ_BRIDGE_READY) {
        MouseIrqState state;
        uint16_t access_flags = result.registers.flags;
        uint16_t live_ss = result.registers.ss;
#if MOUSE_IRQ_BRIDGE_MUTATION == 10
        live_ss = registers->ss;
#endif
        state.memory = memory;
        state.bus = bus;
        state.registers = result.registers;
        state.status = result.status;
        state.service_status = result.service_status;
        consume_iret(&state, live_ss, &state.registers.sp, access_flags);
        result.registers = state.registers;
    }
    return result;
}

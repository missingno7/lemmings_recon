#include "input_poll.h"

#include "interrupt_service.h"
#include "lemmings_sym.h"

#ifndef INPUT_POLL_MUTATION
#define INPUT_POLL_MUTATION 0
#endif

enum {
    ADDRESS_MASK = 0xfffff,
    CF = 0x0001,
    PF = 0x0004,
    AF = 0x0010,
    ZF = 0x0040,
    SF = 0x0080,
    OF = 0x0800,
    ARITH = CF | PF | AF | ZF | SF | OF,
    LOGIC = CF | PF | ZF | SF | OF
};

typedef struct InputPollState {
    uint8_t *memory;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    LmnRegs r;
    uint16_t status;
    uint16_t service_status;
} InputPollState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + (uint32_t)offset) & ADDRESS_MASK;
}

static uint8_t read_physical8(InputPollState *s, uint32_t address,
                              uint16_t flags) {
    address &= ADDRESS_MASK;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address, flags);
    return s->memory[address];
}

static void write_physical8(InputPollState *s, uint32_t address,
                            uint8_t value, uint16_t flags) {
    address &= ADDRESS_MASK;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value, flags);
    else
        s->memory[address] = value;
}

static uint8_t read8_at(InputPollState *s, uint16_t segment,
                        uint16_t offset, uint16_t flags) {
    return read_physical8(s, physical(segment, offset), flags);
}

static uint8_t read8(InputPollState *s, uint16_t segment, uint16_t offset) {
    return read8_at(s, segment, offset, s->r.flags);
}

/* A word's high byte follows the low byte physically, including at EA wrap. */
static uint16_t read16_at(InputPollState *s, uint16_t segment,
                          uint16_t offset, uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical8(s, address, flags);
    uint8_t high = read_physical8(s, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static uint16_t read16(InputPollState *s, uint16_t segment, uint16_t offset) {
    return read16_at(s, segment, offset, s->r.flags);
}

static void write16(InputPollState *s, uint16_t segment, uint16_t offset,
                    uint16_t value) {
    uint32_t address = physical(segment, offset);
    write_physical8(s, address, (uint8_t)value, s->r.flags);
    write_physical8(s, address + 1u, (uint8_t)(value >> 8), s->r.flags);
}

static void push16_flags(InputPollState *s, uint16_t value,
                         uint16_t access_flags) {
    s->r.sp = (uint16_t)(s->r.sp - 2u);
    {
        uint32_t address = physical(s->r.ss, s->r.sp);
        write_physical8(s, address, (uint8_t)value, access_flags);
        write_physical8(s, address + 1u, (uint8_t)(value >> 8), access_flags);
    }
}

static void push16(InputPollState *s, uint16_t value) {
    push16_flags(s, value, s->r.flags);
}

static uint16_t pop16_from(InputPollState *s, uint16_t segment,
                           uint16_t *stack_offset, uint16_t access_flags) {
    uint16_t value = read16_at(s, segment, *stack_offset, access_flags);
    *stack_offset = (uint16_t)(*stack_offset + 2u);
    return value;
}

static uint16_t pop16(InputPollState *s) {
    return pop16_from(s, s->r.ss, &s->r.sp, s->r.flags);
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        parity ^= (unsigned)((value >> bit) & 1u);
    return parity == 0;
}

static uint16_t szp_flags(uint16_t value, unsigned width) {
    uint8_t low = (uint8_t)value;
    uint16_t flags = 0;
    if (even_parity8(low))
        flags |= PF;
    if (width == 8 ? low == 0 : value == 0)
        flags |= ZF;
    if (width == 8 ? (low & 0x80u) != 0 : (value & 0x8000u) != 0)
        flags |= SF;
    return flags;
}

static void logic_flags(InputPollState *s, uint16_t value, unsigned width) {
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~LOGIC) |
                            szp_flags(value, width));
}

static void cmp8(InputPollState *s, uint8_t left, uint8_t right) {
    uint8_t result = (uint8_t)(left - right);
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~ARITH) |
        szp_flags(result, 8) | (left < right ? CF : 0u) |
        ((left ^ right ^ result) & AF) |
        (((left ^ right) & (left ^ result) & 0x80u) ? OF : 0u));
}

static void cmp16(InputPollState *s, uint16_t left, uint16_t right) {
    uint16_t result = (uint16_t)(left - right);
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~ARITH) |
        szp_flags(result, 16) | (left < right ? CF : 0u) |
        ((left ^ right ^ result) & AF) |
        (((left ^ right) & (left ^ result) & 0x8000u) ? OF : 0u));
}

static uint16_t add16(InputPollState *s, uint16_t left, uint16_t right) {
    uint32_t sum = (uint32_t)left + right;
    uint16_t result = (uint16_t)sum;
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~ARITH) |
        szp_flags(result, 16) | (sum > 0xffffu ? CF : 0u) |
        ((left ^ right ^ result) & AF) |
        (((uint16_t)~(left ^ right) & (left ^ result) & 0x8000u) ? OF : 0u));
    return result;
}

static uint16_t sub16(InputPollState *s, uint16_t left, uint16_t right) {
    uint16_t result = (uint16_t)(left - right);
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~ARITH) |
        szp_flags(result, 16) | (left < right ? CF : 0u) |
        ((left ^ right ^ result) & AF) |
        (((left ^ right) & (left ^ result) & 0x8000u) ? OF : 0u));
    return result;
}

static uint16_t shr16(InputPollState *s, uint16_t before) {
    uint16_t result = (uint16_t)(before >> 1);
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~LOGIC) |
        szp_flags(result, 16) | ((before & 1u) ? CF : 0u) |
        ((before & 0x8000u) ? OF : 0u));
    return result;
}

#if INPUT_POLL_MUTATION != 7
static uint16_t sar16(InputPollState *s, uint16_t before) {
    uint16_t result = (uint16_t)((before >> 1) | (before & 0x8000u));
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~LOGIC) |
        szp_flags(result, 16) | ((before & 1u) ? CF : 0u));
    return result;
}
#endif

static int signed_ge(const InputPollState *s) {
    return ((s->r.flags & SF) != 0) == ((s->r.flags & OF) != 0);
}

static int signed_le(const InputPollState *s) {
    return (s->r.flags & ZF) != 0 || !signed_ge(s);
}

static int signed_gt(const InputPollState *s) {
    return (s->r.flags & ZF) == 0 && signed_ge(s);
}

static LmnInputPollResult result_of(const InputPollState *s) {
    LmnInputPollResult result;
    result.registers = s->r;
    result.status = s->status;
    result.service_status = s->service_status;
    return result;
}

static void set_status(InputPollState *s, uint16_t status,
                       uint16_t service_status) {
    s->status = status;
    s->service_status = service_status;
}

static void clamp_mouse_coordinate(InputPollState *s, uint16_t *value,
                                   uint16_t maximum) {
    cmp16(s, *value, 8);
    if (!signed_ge(s))
        *value = 8;
    cmp16(s, *value, maximum);
    if (!signed_le(s))
        *value = maximum;
}

static void poll_mouse_body(InputPollState *s,
                            const LmnInputPollService *service) {
    LmnInterruptService interrupt_service;
    const LmnInterruptService *provider = NULL;
    LmnInterruptResult interrupt_result;

    push16(s, s->r.es); /* PUSH ES @4252 */
    push16(s, s->r.ds); /* PUSH DS @4253 */
    push16(s, s->r.bp); /* PUSH BP @4254 */
    push16(s, s->r.si); /* PUSH SI @4255 */
    push16(s, s->r.di); /* PUSH DI @4256 */
    push16(s, s->r.ax); /* PUSH AX @4257 */
    push16(s, s->r.bx); /* PUSH BX @4258 */
    push16(s, s->r.cx); /* PUSH CX @4259 */
    push16(s, s->r.dx); /* PUSH DX @425A */
    push16(s, s->r.ds); /* PUSH DS @425B */
    s->r.ax = 3;        /* MOV AX,3 @425C */
    s->r.ip = CS_MousePollInt33;
    if (service) {
        interrupt_service.context = service->context;
        interrupt_service.execute = service->interrupt33;
        interrupt_service.code_segment = service->code_segment;
        interrupt_service.instruction_pointer = service->instruction_pointer;
        provider = &interrupt_service;
    }
    interrupt_result = lmn_interrupt_service(s->memory, &s->r, 0x33u,
        CS_MousePollInt33Return, provider, s->bus);
    if (interrupt_result.status != LMN_INTERRUPT_RETURNED) {
        uint16_t status = LMN_INPUT_POLL_UNBOUND_SERVICE;
        if (interrupt_result.status == LMN_INTERRUPT_PROVIDER_STOP)
            status = LMN_INPUT_POLL_EXTERNAL_STOP;
        else if (interrupt_result.status == LMN_INTERRUPT_CHANGED_IRET)
            status = LMN_INPUT_POLL_CHANGED_INTERRUPT_RETURN;
        set_status(s, status, interrupt_result.service_status);
        return;
    }
    s->service_status = interrupt_result.service_status;

    s->r.ip = CS_MousePollInt33Return;
    s->r.ds = pop16(s); /* POP DS @4261 */
    s->r.ip = 0x4262u;
    {
        uint8_t suppression = read8(s, s->r.ds,
                                    SEG09A9_MouseButtonSuppression200B);
        cmp8(s, suppression, 0xffu);
        if ((s->r.flags & ZF) == 0)
            write16(s, s->r.ds, SEG09A9_InputButtonsWord, s->r.bx);
    }

    clamp_mouse_coordinate(s, &s->r.cx, 0x0148u);
    write16(s, s->r.ds, SEG09A9_PointerX, s->r.cx);
    clamp_mouse_coordinate(s, &s->r.dx, 0x00c8u);
    write16(s, s->r.ds, SEG09A9_PointerY, s->r.dx);

    s->r.dx = pop16(s); /* POP DX @4297 */
    s->r.cx = pop16(s); /* POP CX @4298 */
    s->r.bx = pop16(s); /* POP BX @4299 */
    s->r.ax = pop16(s); /* POP AX @429A */
    s->r.di = pop16(s); /* POP DI @429B */
    s->r.si = pop16(s); /* POP SI @429C */
    s->r.bp = pop16(s); /* POP BP @429D */
    s->r.ds = pop16(s); /* POP DS @429E */
    s->r.es = pop16(s); /* POP ES @429F */
    s->r.ip = CS_PollMousePositionReturn42A0;
}

static void sar_steps(InputPollState *s, uint16_t *value, unsigned count) {
    unsigned i;
    for (i = 0; i < count; ++i) {
#if INPUT_POLL_MUTATION == 7
        *value = shr16(s, *value);
#else
        *value = sar16(s, *value);
#endif
    }
}

static unsigned x_scale_shifts(InputPollState *s, uint8_t scale) {
    cmp8(s, scale, 2);
    if (s->r.flags & ZF)
        return 5;
    cmp8(s, scale, 3);
    if (s->r.flags & ZF)
        return 3;
    cmp8(s, scale, 4);
    if (s->r.flags & ZF)
        return 2;
    return 6;
}

static unsigned y_scale_shifts(InputPollState *s, uint8_t scale) {
    cmp8(s, scale, 2);
    if (s->r.flags & ZF)
        return 4;
    cmp8(s, scale, 3);
    if (s->r.flags & ZF)
        return 2;
    cmp8(s, scale, 4);
    if (s->r.flags & ZF)
        return 1;
    return 5;
}

static void calibrate_axis(InputPollState *s, uint16_t *value,
                           uint16_t position_offset,
                           uint16_t maximum, int horizontal, uint8_t scale) {
    cmp16(s, *value, 8);
    if (!signed_gt(s)) {
        cmp16(s, *value, 0xfff8u);
        if (signed_ge(s))
            return;
    }

    sar_steps(s, value, horizontal ? x_scale_shifts(s, scale)
                                   : y_scale_shifts(s, scale));
    *value = add16(s, *value, read16(s, s->r.ds, position_offset));
    cmp16(s, *value, 8);
    if (!signed_gt(s)) {
        *value = 8;
    } else {
        cmp16(s, *value, maximum);
        if (!signed_le(s))
            *value = maximum;
    }
    write16(s, s->r.ds, position_offset, *value);
}

static void poll_keyboard_body(InputPollState *s) {
    uint16_t key_mask;

    s->r.ip = 0x41a0u;
    s->r.bx = read16(s, s->r.ds, SEG09A9_InputAccelerationX0016);
    s->r.cx = read16(s, s->r.ds, SEG09A9_InputAccelerationY0018);
    s->r.ax = read16(s, s->r.ds, SEG09A9_InputKeyMask1FC7);
    key_mask = s->r.ax;

    logic_flags(s, (uint16_t)(s->r.ax & 0x0c03u), 16); /* TEST AX,0C03. */
    if ((s->r.flags & ZF) == 0) {
        logic_flags(s, (uint16_t)(s->r.ax & 0x0401u), 16);
        if ((s->r.flags & ZF) == 0) {
            s->r.cx = sub16(s, s->r.cx, 1);
            if ((s->r.flags & SF) != 0) {
                s->r.cx = 0;
                logic_flags(s, 0, 16);
            }
        }
        logic_flags(s, (uint16_t)(s->r.ax & 0x0802u), 16);
        if ((s->r.flags & ZF) == 0) {
            s->r.cx = add16(s, s->r.cx, 1);
            cmp16(s, s->r.cx, 0x0020u);
            if (!signed_le(s))
                s->r.cx = 0x0020u;
        }
    } else {
        s->r.cx = 0x0010u;
    }

    logic_flags(s, (uint16_t)(key_mask & 0x300cu), 16); /* TEST AX,300C. */
    if ((s->r.flags & ZF) == 0) {
        logic_flags(s, (uint16_t)(key_mask & 0x1004u), 16);
        if ((s->r.flags & ZF) == 0) {
            s->r.bx = sub16(s, s->r.bx, 1);
            if ((s->r.flags & SF) != 0) {
                s->r.bx = 0;
                logic_flags(s, 0, 16);
            }
        }
        logic_flags(s, (uint16_t)(key_mask & 0x2008u), 16);
        if ((s->r.flags & ZF) == 0) {
            s->r.bx = add16(s, s->r.bx, 1);
            cmp16(s, s->r.bx, 0x0020u);
            if (!signed_le(s))
                s->r.bx = 0x0020u;
        }
    } else {
        s->r.bx = 0x0010u;
    }

    write16(s, s->r.ds, SEG09A9_InputAccelerationX0016, s->r.bx);
    write16(s, s->r.ds, SEG09A9_InputAccelerationY0018, s->r.cx);
    s->r.bx = shr16(s, s->r.bx);
    s->r.cx = shr16(s, s->r.cx);
    s->r.bx = shr16(s, s->r.bx);
    s->r.cx = shr16(s, s->r.cx);
    s->r.bx = sub16(s, s->r.bx, 4);
    s->r.cx = sub16(s, s->r.cx, 4);
    s->r.bx = add16(s, s->r.bx,
                    read16(s, s->r.ds, SEG09A9_PointerX));
    cmp16(s, s->r.bx, 8);
    if (!signed_gt(s)) {
        s->r.bx = 8;
    } else {
        cmp16(s, s->r.bx, 0x0148u);
        if (!signed_le(s))
            s->r.bx = 0x0148u;
    }
    write16(s, s->r.ds, SEG09A9_PointerX, s->r.bx);
    s->r.cx = add16(s, s->r.cx,
                    read16(s, s->r.ds, SEG09A9_PointerY));
    cmp16(s, s->r.cx, 8);
    if (!signed_gt(s)) {
        s->r.cx = 8;
    } else {
        cmp16(s, s->r.cx, 0x00c8u);
        if (!signed_le(s))
            s->r.cx = 0x00c8u;
    }
    write16(s, s->r.ds, SEG09A9_PointerY, s->r.cx);

    s->r.bx = 0;
    logic_flags(s, 0, 16); /* XOR BX,BX. */
    logic_flags(s, (uint16_t)(key_mask & 0x4010u), 16); /* TEST AX,4010. */
    if ((s->r.flags & ZF) == 0) {
        s->r.bx = (uint16_t)(s->r.bx | 1u);
        logic_flags(s, s->r.bx, 16);
    }
    write16(s, s->r.ds, SEG09A9_InputButtonsWord, s->r.bx);
    s->r.ip = CS_PollInputKeyboardReturn4251;
}

static void poll_input_body(InputPollState *s,
                            const LmnInputPollService *service) {
    uint8_t mode = read8(s, s->r.ds, SEG09A9_InputModeByte25A6);
    cmp8(s, mode, 0);
    if (s->r.flags & ZF) {
        s->r.ip = CS_PollMousePosition;
        poll_mouse_body(s, service); /* JMP at 4193: no new frame. */
        return;
    }

    mode = read8(s, s->r.ds, SEG09A9_InputModeByte25A6);
    cmp8(s, mode, 1);
    if (s->r.flags & ZF) {
        uint16_t target;
        uint16_t child_return = CS_InputPollCallbackReturn42A7;
        LmnInputPollResult child_result;
        s->r.ip = 0x42a1u;
        s->r.ax = read16(s, s->r.ds, SEG09A9_InputPollCallback);
        push16(s, s->r.dx); /* PUSH DX @42A4. */
        s->r.ip = CS_InputPollCallbackCall42A5;
        target = s->r.ax;
        if (target == CS_PollMousePosition) {
            push16(s, child_return);
            s->r.ip = target;
            poll_mouse_body(s, service);
            child_result = result_of(s);
            if (child_result.status != LMN_INPUT_POLL_READY)
                return;
        } else if (target == CS_PollPort201ButtonsLow ||
                   target == CS_PollPort201ButtonsHigh) {
            push16(s, child_return);
            s->r.ip = target;
            if (target == CS_PollPort201ButtonsLow) {
                LmnPortIoResult port = lmn_poll_port201_buttons_low_core(
                    s->memory, &s->r, s->ports, s->bus);
                s->r = port.registers;
                if (port.status != LMN_PORT_IO_READY) {
                    set_status(s, LMN_INPUT_POLL_CHILD_STOP, port.status);
                    return;
                }
            } else {
                LmnPortIoResult port = lmn_poll_port201_buttons_high_core(
                    s->memory, &s->r, s->ports, s->bus);
                s->r = port.registers;
                if (port.status != LMN_PORT_IO_READY) {
                    set_status(s, LMN_INPUT_POLL_CHILD_STOP, port.status);
                    return;
                }
            }
        } else {
#if INPUT_POLL_MUTATION == 4
            /* Mutant executes the low wrapper instead of stopping pre-CALL. */
            push16(s, child_return);
            s->r.ip = CS_PollPort201ButtonsLow;
            {
                LmnPortIoResult port = lmn_poll_port201_buttons_low_core(
                    s->memory, &s->r, s->ports, s->bus);
                s->r = port.registers;
                if (port.status != LMN_PORT_IO_READY) {
                    set_status(s, LMN_INPUT_POLL_CHILD_STOP, port.status);
                    return;
                }
            }
#else
            set_status(s, LMN_INPUT_POLL_UNSUPPORTED_CALLBACK, 0);
            return;
#endif
        }

        s->r.ip = pop16(s); /* CALL AX's live near RET. */
        if (s->r.ip != child_return && INPUT_POLL_MUTATION != 5) {
            set_status(s, LMN_INPUT_POLL_CHANGED_CHILD_RETURN, 0);
            return;
        }
        if (s->r.ip != child_return)
            s->r.ip = child_return;
        s->r.dx = pop16(s); /* POP DX @42A7. */
        s->r.ip = 0x42a8u;
        if (INPUT_POLL_MUTATION == 6) {
            cmp16(s, s->r.dx, 0x00ffu);
        } else {
            cmp8(s, (uint8_t)s->r.dx, 0xffu);
        }
        if (s->r.flags & ZF) {
            s->r.ip = CS_InputPollOuterReturn4333;
            return;
        }

        s->r.bx = sub16(s, s->r.bx,
                        read16(s, s->r.ds, SEG09A9_InputAxisBaselineX25A2));
        s->r.cx = sub16(s, s->r.cx,
                        read16(s, s->r.ds, SEG09A9_InputAxisBaselineY25A4));
        s->r.ax = (uint16_t)((s->r.ax & 0xff00u) |
            read8(s, s->r.ds, SEG09A9_InputAxisScaleSelector2005));
        calibrate_axis(s, &s->r.bx, SEG09A9_PointerX, 0x0148u, 1,
                       (uint8_t)s->r.ax);
        calibrate_axis(s, &s->r.cx, SEG09A9_PointerY, 0x00c8u, 0,
                       (uint8_t)s->r.ax);
        s->r.ip = CS_InputPollOuterReturn4333;
        return;
    }

    poll_keyboard_body(s);
}

LmnInputPollResult lmn_poll_mouse_position_core(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *service,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    InputPollState s;
    s.memory = memory;
    s.ports = ports;
    s.bus = bus;
    s.r = *registers;
    s.status = LMN_INPUT_POLL_READY;
    s.service_status = 0;
    s.r.ip = CS_PollMousePosition;
    poll_mouse_body(&s, service);
    return result_of(&s);
}

static LmnInputPollResult consume_outer_ret(uint8_t *memory,
    LmnInputPollResult result, const LmnRasterBus *bus) {
    InputPollState s;
    if (result.status != LMN_INPUT_POLL_READY)
        return result;
    s.memory = memory;
    s.ports = NULL;
    s.bus = bus;
    s.r = result.registers;
    s.status = result.status;
    s.service_status = result.service_status;
    s.r.ip = pop16(&s);
    result.registers = s.r;
    return result;
}

LmnInputPollResult lmn_poll_mouse_position_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *service,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    return consume_outer_ret(memory,
        lmn_poll_mouse_position_core(memory, registers, service, ports, bus),
        bus);
}

LmnInputPollResult lmn_poll_input_state_core(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *service,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    InputPollState s = {memory, ports, bus, *registers,
                        LMN_INPUT_POLL_READY, 0};
    s.r.ip = CS_PollInputState418C;
    poll_input_body(&s, service);
    return result_of(&s);
}

LmnInputPollResult lmn_poll_input_state_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *service,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    return consume_outer_ret(memory,
        lmn_poll_input_state_core(memory, registers, service, ports, bus), bus);
}

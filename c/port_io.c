#include "port_io.h"
#include "lemmings_sym.h"

#ifndef PORT_IO_MUTATION
#define PORT_IO_MUTATION 0
#endif

enum {
    CF = 0x001,
    PF = 0x004,
    AF = 0x010,
    ZF = 0x040,
    SF = 0x080,
    IF = 0x200,
    OF = 0x800,
    ARITH = CF | PF | AF | ZF | SF | OF,
    LOGIC = CF | PF | ZF | SF | OF
};

typedef struct PortIoState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    const LmnRasterBytePorts *ports;
    LmnRegs r;
    uint16_t status;
} PortIoState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + (uint32_t)offset) & 0xfffffu;
}

static uint8_t read_physical8(PortIoState *s, uint32_t address) {
    address &= 0xfffffu;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address,
                                 s->r.flags);
    return s->memory[address];
}

static void write_physical8(PortIoState *s, uint32_t address, uint8_t value) {
    address &= 0xfffffu;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value,
                           s->r.flags);
    else
        s->memory[address] = value;
}

static uint8_t read8(PortIoState *s, uint16_t segment, uint16_t offset) {
    return read_physical8(s, physical(segment, offset));
}

static void write8(PortIoState *s, uint16_t segment, uint16_t offset,
                   uint8_t value) {
    write_physical8(s, physical(segment, offset), value);
}

static uint16_t read16(PortIoState *s, uint16_t segment, uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical8(s, address);
    uint8_t high = read_physical8(s, address + 1u);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(PortIoState *s, uint16_t segment, uint16_t offset,
                    uint16_t value) {
    uint32_t address = physical(segment, offset);
    write_physical8(s, address, (uint8_t)value);
    write_physical8(s, address + 1u, (uint8_t)(value >> 8));
}

static void push16(PortIoState *s, uint16_t value) {
    s->r.sp = (uint16_t)(s->r.sp - 2u);
    write16(s, s->r.ss, s->r.sp, value);
}

static uint16_t pop16(PortIoState *s) {
    uint16_t value = read16(s, s->r.ss, s->r.sp);
    s->r.sp = (uint16_t)(s->r.sp + 2u);
    return value;
}

static uint16_t szp(uint16_t value, unsigned width) {
    uint16_t flags = 0;
    uint8_t low = (uint8_t)value;
    unsigned ones = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        ones += (unsigned)((low >> bit) & 1u);
    if ((ones & 1u) == 0)
        flags |= PF;
    if (width == 8 ? (uint8_t)value == 0 : value == 0)
        flags |= ZF;
    if (width == 8 ? (value & 0x80u) != 0 : (value & 0x8000u) != 0)
        flags |= SF;
    return flags;
}

static void logic_flags(PortIoState *s, uint16_t value, unsigned width) {
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~LOGIC) |
                            szp(value, width));
}

static uint16_t xor16(PortIoState *s, uint16_t value) {
    (void)value;
    logic_flags(s, 0, 16);
    return 0;
}

static void cmp8(PortIoState *s, uint8_t left, uint8_t right) {
    uint8_t result = (uint8_t)(left - right);
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~ARITH) |
        szp(result, 8) | (left < right ? CF : 0u) |
        ((left ^ right ^ result) & AF) |
        (((left ^ right) & (left ^ result) & 0x80u) ? OF : 0u));
}

static void cmp16(PortIoState *s, uint16_t left, uint16_t right) {
    uint16_t result = (uint16_t)(left - right);
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~ARITH) |
        szp(result, 16) | (left < right ? CF : 0u) |
        ((left ^ right ^ result) & AF) |
        (((left ^ right) & (left ^ result) & 0x8000u) ? OF : 0u));
}

static uint16_t and16(PortIoState *s, uint16_t left, uint16_t right) {
    uint16_t result = (uint16_t)(left & right);
    logic_flags(s, result, 16);
    return result;
}

static void add16(PortIoState *s, uint16_t *target, uint16_t value) {
    uint16_t left = *target;
    uint32_t sum = (uint32_t)left + value;
    uint16_t result = (uint16_t)sum;
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~ARITH) |
        szp(result, 16) | (sum > 0xffffu ? CF : 0u) |
        ((left ^ value ^ result) & AF) |
        (((uint16_t)~(left ^ value) & (left ^ result) & 0x8000u) ? OF : 0u));
    *target = result;
}

static uint16_t shr16(PortIoState *s, uint16_t before) {
    uint16_t result = (uint16_t)(before >> 1);
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~LOGIC) |
        szp(result, 16) | ((before & 1u) ? CF : 0u) |
        ((before & 0x8000u) ? OF : 0u));
    return result;
}

static uint16_t sar16(PortIoState *s, uint16_t before) {
    uint16_t result = (uint16_t)((before >> 1) | (before & 0x8000u));
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~LOGIC) |
        szp(result, 16) | ((before & 1u) ? CF : 0u));
    return result;
}

static uint8_t ror8(PortIoState *s, uint8_t before) {
    uint8_t result = (uint8_t)((before >> 1) | ((before & 1u) << 7));
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~(CF | OF));
    uint16_t carry = (before & 1u) ? CF : 0u;
    if ((((result >> 7) ^ (result >> 6)) & 1u) != 0)
        flags |= OF;
    s->r.flags = (uint16_t)(flags | carry);
    return result;
}

static void set_missing(PortIoState *s, uint16_t ip) {
    s->r.ip = ip;
    s->status = LMN_PORT_IO_MISSING_PROVIDER;
}

static LmnPortIoResult result_of(const PortIoState *s) {
    LmnPortIoResult result;
    result.registers = s->r;
    result.status = s->status;
    return result;
}

static PortIoState state_from(uint8_t *memory, const LmnRegs *registers,
                              const LmnRasterBytePorts *ports,
                              const LmnRasterBus *bus) {
    PortIoState s;
    s.memory = memory;
    s.bus = bus;
    s.ports = ports;
    s.r = *registers;
    s.status = LMN_PORT_IO_READY;
    return s;
}

static LmnPortIoResult consume_near_return(uint8_t *memory,
                                           LmnPortIoResult result,
                                           const LmnRasterBus *bus,
                                           int eoi_adapter) {
    PortIoState s;
    if (result.status != LMN_PORT_IO_READY)
        return result;
    s.memory = memory;
    s.bus = bus;
    s.ports = NULL;
    s.r = result.registers;
    s.status = result.status;
#if PORT_IO_MUTATION == 2
    /* Deliberately leave the real outer return word unconsumed. */
    if (eoi_adapter)
        return result;
#else
    (void)eoi_adapter;
#endif
    s.r.ip = pop16(&s);
    return result_of(&s);
}

static void measure_axes(PortIoState *s) {
    uint8_t cached_mask = 0;
    s->r.ip = CS_MeasurePort201Axes;
    s->r.flags = (uint16_t)(s->r.flags & (uint16_t)~IF); /* CLI */
    s->r.bx = xor16(s, s->r.bx); /* XOR BX,BX */
    s->r.cx = xor16(s, s->r.cx); /* XOR CX,CX */
    s->r.si = xor16(s, s->r.si); /* XOR SI,SI */
    s->r.di = xor16(s, s->r.di); /* XOR DI,DI */
    s->r.dx = 0x0201u;

    if (!s->ports || !s->ports->out_byte) {
        set_missing(s, CS_Port201PulseOut4392);
        return;
    }
    s->r.ip = CS_Port201PulseOut4392;
    s->ports->out_byte(s->ports->context, s->memory, s->r.dx,
                       (uint8_t)s->r.ax, s->r.flags);
    /* JMP 4396, UNKNOWN 4395, JMP 4399, UNKNOWN 4398. */
    s->r.ip = CS_Port201SampleIn4399;
#if PORT_IO_MUTATION == 3
    cached_mask = read8(s, s->r.ds, SEG09A9_Port201MaskByte0051);
#endif
    for (;;) {
        uint8_t input;
        uint8_t mask;
        s->r.ip = CS_Port201SampleIn4399;
        if (!s->ports || !s->ports->in_byte) {
            set_missing(s, CS_Port201SampleIn4399);
            return;
        }
        input = s->ports->in_byte(s->ports->context, s->memory, s->r.dx,
                                  s->r.flags);
        s->r.ax = (uint16_t)((s->r.ax & 0xff00u) | input);
        mask = PORT_IO_MUTATION == 3
            ? cached_mask
            : read8(s, s->r.ds, SEG09A9_Port201MaskByte0051);
        s->r.ax = (uint16_t)((s->r.ax & 0xff00u) |
                             ((uint8_t)s->r.ax & mask));
        logic_flags(s, (uint8_t)s->r.ax, 8); /* AND AL,[0051]. */
        s->r.ax = (uint16_t)(s->r.ax & 0x00ffu); /* XOR AH,AH. */
        logic_flags(s, 0, 8);
        s->r.bp = s->r.ax; /* MOV BP,AX. */

        s->r.ax = and16(s, s->r.ax, 0x0001u);
        add16(s, &s->r.bx, s->r.ax);
        s->r.ax = s->r.bp;
        s->r.ax = and16(s, s->r.ax, 0x0002u);
        add16(s, &s->r.cx, s->r.ax);
        s->r.ax = s->r.bp;
        s->r.ax = and16(s, s->r.ax, 0x0004u);
        s->r.ax = shr16(s, s->r.ax);
        s->r.ax = shr16(s, s->r.ax);
        add16(s, &s->r.si, s->r.ax);
        s->r.ax = s->r.bp;
        s->r.ax = and16(s, s->r.ax, 0x0008u);
        s->r.ax = shr16(s, s->r.ax);
        s->r.ax = shr16(s, s->r.ax);
        add16(s, &s->r.di, s->r.ax);

        logic_flags(s, s->r.bp, 16); /* OR BP,BP. */
        if (s->r.bp == 0)
            break;
    }

    s->r.flags = (uint16_t)(s->r.flags | IF); /* STI. */
#if PORT_IO_MUTATION == 4
    s->r.cx = shr16(s, s->r.cx);
#else
    s->r.cx = sar16(s, s->r.cx);
#endif
#if PORT_IO_MUTATION == 5
    s->r.di = shr16(s, s->r.di);
#else
    s->r.di = sar16(s, s->r.di);
#endif
    s->r.ip = CS_Port201MeasureReturn43CD;
}

static LmnPortIoResult poll_buttons(uint8_t *memory, const LmnRegs *registers,
                                    const LmnRasterBytePorts *ports,
                                    const LmnRasterBus *bus, int high) {
    PortIoState s = state_from(memory, registers, ports, bus);
    uint16_t child_return = high ? CS_Port201HighAfterAxes
                                 : CS_Port201LowAfterAxes;
    uint16_t input_ip = high ? CS_Port201HighInput436E
                             : CS_Port201LowInput4345;
    uint16_t ret_ip = high ? CS_Port201HighReturn4385
                           : CS_Port201LowReturn4358;
    uint16_t continuation_ip = high ?
        (uint16_t)(CS_Port201HighAfterAxes + 4u) : CS_Port201LowAfterAxes;
    unsigned rotations = high ? 6u : 4u;
    uint8_t value;
    unsigned i;

    s.r.ip = high ? CS_PollPort201ButtonsHigh : CS_PollPort201ButtonsLow;
    write8(&s, s.r.ds, SEG09A9_Port201MaskByte0051, high ? 0x0cu : 0x03u);
    if (PORT_IO_MUTATION == 7) {
        cmp16(&s, s.r.dx, 0x00ffu);
    } else {
        cmp8(&s, (uint8_t)s.r.dx, 0xffu);
    }
    if (!(s.r.flags & ZF)) {
        push16(&s, child_return);
        s.r.ip = CS_MeasurePort201Axes;
        {
            LmnPortIoResult child = lmn_measure_port201_axes_core(
                s.memory, &s.r, s.ports, s.bus);
            s.r = child.registers;
            if (child.status != LMN_PORT_IO_READY) {
                s.status = child.status;
                return result_of(&s);
            }
        }
        s.r.ip = pop16(&s); /* Consume the actual child RET word. */
        if (s.r.ip != child_return && PORT_IO_MUTATION != 9) {
            s.status = LMN_PORT_IO_CHANGED_CHILD_RETURN;
            return result_of(&s);
        }
        if (s.r.ip != child_return)
            s.r.ip = child_return; /* Mutant ignores the changed target. */
        if (high) {
            s.r.bx = s.r.si;
            s.r.cx = s.r.di;
        }
        continuation_ip = high ?
            (uint16_t)(CS_Port201HighAfterAxes + 4u) : CS_Port201LowAfterAxes;
    } else if (high && PORT_IO_MUTATION == 8) {
        /* Mutant performs the high-only copies despite the skipped CALL. */
        s.r.bx = s.r.si;
        s.r.cx = s.r.di;
    }

    s.r.ip = continuation_ip;
    s.r.flags = (uint16_t)(s.r.flags & (uint16_t)~IF); /* CLI. */
    s.r.dx = 0x0201u;
    s.r.ip = input_ip;
    if (!s.ports || !s.ports->in_byte) {
        set_missing(&s, input_ip);
        return result_of(&s);
    }
    value = s.ports->in_byte(s.ports->context, s.memory, s.r.dx, s.r.flags);
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | value);
    s.r.flags = (uint16_t)(s.r.flags | IF); /* STI. */
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | (uint8_t)~(uint8_t)s.r.ax);
#if PORT_IO_MUTATION == 10
    --rotations;
#endif
    for (i = 0; i < rotations; ++i)
        s.r.ax = (uint16_t)((s.r.ax & 0xff00u) |
                            ror8(&s, (uint8_t)s.r.ax));
    value = (uint8_t)s.r.ax & 0x03u;
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | value);
    logic_flags(&s, value, 8); /* AND AL,3. */
#if PORT_IO_MUTATION == 6
    s.r.ax = 0; /* Mutant XOR AX,AX. */
#else
    s.r.ax &= 0x00ffu; /* XOR AH,AH. */
#endif
    logic_flags(&s, 0, 8);
    write16(&s, s.r.ds, SEG09A9_InputButtonsWord, s.r.ax);
    s.r.ip = ret_ip;
    return result_of(&s);
}

LmnPortIoResult lmn_send_master_pic_eoi_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    PortIoState s = state_from(memory, registers, ports, bus);
    (void)bus;
    s.r.ip = CS_SendMasterPicEoi;
#if PORT_IO_MUTATION == 1
    s.r.ax = 0x0020u;
#else
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | 0x20u);
#endif
    s.r.ip = CS_MasterPicEoiOut18B4;
    if (!s.ports || !s.ports->out_byte) {
        set_missing(&s, CS_MasterPicEoiOut18B4);
        return result_of(&s);
    }
    s.ports->out_byte(s.ports->context, s.memory, 0x0020u,
                      (uint8_t)s.r.ax, s.r.flags);
    s.r.ip = CS_MasterPicEoiReturn18B6;
    return result_of(&s);
}

LmnPortIoResult lmn_send_master_pic_eoi_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    return consume_near_return(memory,
        lmn_send_master_pic_eoi_core(memory, registers, ports, bus), bus, 1);
}

LmnPortIoResult lmn_measure_port201_axes_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    PortIoState s = state_from(memory, registers, ports, bus);
    measure_axes(&s);
    return result_of(&s);
}

LmnPortIoResult lmn_measure_port201_axes_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    return consume_near_return(memory,
        lmn_measure_port201_axes_core(memory, registers, ports, bus), bus, 0);
}

LmnPortIoResult lmn_poll_port201_buttons_low_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    return poll_buttons(memory, registers, ports, bus, 0);
}

LmnPortIoResult lmn_poll_port201_buttons_low_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    return consume_near_return(memory,
        lmn_poll_port201_buttons_low_core(memory, registers, ports, bus), bus, 0);
}

LmnPortIoResult lmn_poll_port201_buttons_high_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    return poll_buttons(memory, registers, ports, bus, 1);
}

LmnPortIoResult lmn_poll_port201_buttons_high_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus) {
    return consume_near_return(memory,
        lmn_poll_port201_buttons_high_core(memory, registers, ports, bus), bus, 0);
}

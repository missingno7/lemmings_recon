#include "vga_mirrors.h"

#include "lemmings_sym.h"

#ifndef VGA_MIRRORS_MUTATION
#define VGA_MIRRORS_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffffu,
    CF = 0x0001u, PF = 0x0004u, AF = 0x0010u, ZF = 0x0040u,
    SF = 0x0080u, IF = 0x0200u, OF = 0x0800u,
    ARITHMETIC_FLAGS = CF | PF | AF | ZF | SF | OF,
    LOGIC_FLAGS = CF | PF | ZF | SF | OF,
    VGA_SEQUENCER = 0x03c4u,
    VGA_GRAPHICS_CONTROLLER = 0x03ceu
};

typedef struct VgaMirrorsState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t cs, ds, es, ss, sp, flags;
    uint16_t continuation, status;
} VgaMirrorsState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return ((((uint32_t)segment << 4) + offset) & MEMORY_MASK);
}

static uint8_t read_physical(VgaMirrorsState *s, uint32_t address) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address,
                                 s->flags);
    return s->memory[address];
}

static void write_physical(VgaMirrorsState *s, uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value,
                           s->flags);
    else
        s->memory[address] = value;
}

/* A real-mode word uses the next physical byte, including at FFFFFh. */
static uint16_t read16(VgaMirrorsState *s, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(s, address);
    uint8_t high = read_physical(s, address + 1u);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(VgaMirrorsState *s, uint16_t segment, uint16_t offset,
                    uint16_t value) {
    uint32_t address = physical(segment, offset);
    write_physical(s, address, (uint8_t)value);
    write_physical(s, address + 1u, (uint8_t)(value >> 8));
}

static void push_word(VgaMirrorsState *s, uint16_t value) {
    s->sp = (uint16_t)(s->sp - 2u);
    write16(s, s->ss, s->sp, value);
}

static uint16_t pop_word(VgaMirrorsState *s) {
    uint16_t value = read16(s, s->ss, s->sp);
    s->sp = (uint16_t)(s->sp + 2u);
    return value;
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity = 0u;
    unsigned bit;
    for (bit = 0u; bit < 8u; ++bit)
        parity ^= (unsigned)((value >> bit) & 1u);
    return parity == 0u;
}

static uint16_t szp8(uint8_t value) {
    uint16_t flags = 0u;
    if (even_parity8(value)) flags |= PF;
    if (value == 0u) flags |= ZF;
    if (value & 0x80u) flags |= SF;
    return flags;
}

static uint16_t add8_flags(uint16_t flags, uint8_t left, uint8_t right) {
    uint16_t wide = (uint16_t)left + (uint16_t)right;
    uint8_t result = (uint8_t)wide;
    uint16_t defined = szp8(result);
    if (wide > 0xffu) defined |= CF;
    if ((left ^ right ^ result) & 0x10u) defined |= AF;
    if (((uint8_t)~(left ^ right) & (left ^ result) & 0x80u) != 0u)
        defined |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) | defined);
}

static uint16_t xor_al_zero_flags(uint16_t flags) {
    /* XOR defines CF/PF/ZF/SF/OF. AF is left opaque because it is undefined. */
    return (uint16_t)((flags & (uint16_t)~LOGIC_FLAGS) | PF | ZF);
}

static void out_word(VgaMirrorsState *s) {
    if (s->bus && s->bus->out_word)
        s->bus->out_word(s->bus->context, s->dx, s->ax, s->flags);
}

static void initialize(VgaMirrorsState *s, uint8_t *memory,
                       const LmnVgaMirrorsCall *call, uint16_t continuation) {
    s->memory = memory;
    s->bus = NULL;
    s->ax = call->ax; s->bx = call->bx; s->cx = call->cx;
    s->dx = call->dx; s->si = call->si; s->di = call->di;
    s->bp = call->bp; s->cs = call->code_segment;
    s->ds = call->data_segment; s->es = call->extra_segment;
    s->ss = call->stack_segment; s->sp = call->stack_offset;
    s->flags = call->flags;
    s->continuation = continuation;
    s->status = LMN_VGA_MIRRORS_READY;
}

static LmnVgaMirrorsResult result_of(const VgaMirrorsState *s) {
    LmnVgaMirrorsResult out;
    out.ax = s->ax; out.bx = s->bx; out.cx = s->cx;
    out.dx = s->dx; out.si = s->si; out.di = s->di; out.bp = s->bp;
    out.code_segment = s->cs; out.data_segment = s->ds;
    out.extra_segment = s->es; out.stack_segment = s->ss;
    out.stack_offset = s->sp; out.flags = s->flags;
    out.continuation = s->continuation; out.status = s->status;
    return out;
}

static void mirror_read_and_out(VgaMirrorsState *s, uint16_t offset,
                                uint8_t index) {
    uint8_t mirror_low;
    s->ax = read16(s, s->es, offset);
    mirror_low = (uint8_t)s->ax;
    (void)mirror_low;
    s->ax = (uint16_t)((s->ax & 0xff00u) | index);
#if VGA_MIRRORS_MUTATION == 4
    s->ax = (uint16_t)(((uint16_t)mirror_low << 8) | index);
#endif
#if VGA_MIRRORS_MUTATION == 5
    if (index == 0u) {
        /* Omit XOR AL,AL at 58B5; retain the low byte just read. */
        s->ax = (uint16_t)((s->ax & 0xff00u) | mirror_low);
    } else
#endif
    if (index == 0u) {
        s->ax &= 0xff00u;                         /* XOR AL,AL @58B5 */
        s->flags = xor_al_zero_flags(s->flags);
    }
    out_word(s);
}

static void apply_result(LmnRegs *r, const LmnVgaMirrorsResult *out) {
    r->ax = out->ax; r->bx = out->bx; r->cx = out->cx;
    r->dx = out->dx; r->si = out->si; r->di = out->di;
    r->bp = out->bp; r->cs = out->code_segment;
    r->ds = out->data_segment; r->es = out->extra_segment;
    r->ss = out->stack_segment; r->sp = out->stack_offset;
    r->flags = out->flags; r->ip = out->continuation;
}

static uint16_t read_stack_return(uint8_t *memory, uint16_t ss,
                                  uint16_t sp, uint16_t flags,
                                  const LmnRasterBus *bus) {
    uint32_t address = physical(ss, sp);
    uint8_t low, high;
    if (bus && bus->read_byte) {
        low = bus->read_byte(bus->context, memory, address, flags);
        high = bus->read_byte(bus->context, memory,
                              (address + 1u) & MEMORY_MASK, flags);
    } else {
        low = memory[address];
        high = memory[(address + 1u) & MEMORY_MASK];
    }
    return (uint16_t)(low | ((uint16_t)high << 8));
}

LmnVgaMirrorsResult lmn_restore_vga_register_mirrors_core(
    uint8_t *memory, const LmnVgaMirrorsCall *call, const LmnRasterBus *bus) {
    VgaMirrorsState s;
    uint16_t relocated_mirror_segment;
#if VGA_MIRRORS_MUTATION == 1
    uint16_t entry_cx = call->cx;
#endif
    initialize(&s, memory, call, CS_VgaMirrorRestoreReturn);
    s.bus = bus;

    s.flags &= (uint16_t)~IF;                    /* CLI @587F */
    push_word(&s, s.cx);                         /* PUSH CX @5880 */
    s.cx = s.es;                                 /* MOV CX,ES @5881 */
    /* Immediate instruction operand is sampled after PUSH, from live CS. */
    relocated_mirror_segment = (uint16_t)(
        memory[physical(s.cs, CS_VgaMirrorFrameOperand5884)] |
        ((uint16_t)memory[physical(s.cs,
            (uint16_t)(CS_VgaMirrorFrameOperand5884 + 1u))] << 8));
    s.ax = relocated_mirror_segment;             /* MOV AX,imm16 @5883; bytes at CS:5884 */
    s.es = s.ax;                                 /* MOV ES,AX @5886 */

#if VGA_MIRRORS_MUTATION == 2
    s.es = s.ss;
#endif
#if VGA_MIRRORS_MUTATION == 3
    s.dx = VGA_GRAPHICS_CONTROLLER;              /* swapped first pair */
    mirror_read_and_out(&s, SEG143E_VgaGraphicsModeMirror, 0x05u);
    s.dx = VGA_SEQUENCER;
    mirror_read_and_out(&s, SEG143E_VgaMapMaskMirror, 0x02u);
    s.dx = VGA_GRAPHICS_CONTROLLER;
#else
    s.dx = VGA_SEQUENCER;                        /* MOV DX,3C4 @5888 */
    mirror_read_and_out(&s, SEG143E_VgaMapMaskMirror, 0x02u);
    s.dx = VGA_GRAPHICS_CONTROLLER;              /* MOV DX,3CE @5892 */
    mirror_read_and_out(&s, SEG143E_VgaGraphicsModeMirror, 0x05u);
#endif
    mirror_read_and_out(&s, SEG143E_VgaDataRotateMirror, 0x03u);
    mirror_read_and_out(&s, SEG143E_VgaColorCompareMirror, 0x02u);
    mirror_read_and_out(&s, SEG143E_VgaColorCareMirror, 0x07u);
    mirror_read_and_out(&s, SEG143E_VgaSetResetMirror, 0x00u);
    mirror_read_and_out(&s, SEG143E_VgaEnableSetResetMirror, 0x01u);
    mirror_read_and_out(&s, SEG143E_VgaBitMaskMirror, 0x08u);
    mirror_read_and_out(&s, SEG143E_VgaReadMapMirror, 0x04u);

    s.es = s.cx;                                 /* MOV ES,CX @58CD */
#if VGA_MIRRORS_MUTATION == 1
    (void)pop_word(&s);
    s.cx = entry_cx;                             /* preserve entry CX */
#else
    s.cx = pop_word(&s);                         /* POP CX @58CF */
#endif
#if VGA_MIRRORS_MUTATION != 6
    s.flags |= IF;                               /* STI @58D0 */
#endif
    return result_of(&s);                        /* before RET @58D1 */
}

LmnVgaMirrorsResult lmn_initialize_vga_register_mirrors_core(
    uint8_t *memory, const LmnVgaMirrorsCall *call, const LmnRasterBus *bus) {
    VgaMirrorsState s;
    initialize(&s, memory, call, CS_VgaMirrorInitializeReturn);
    s.bus = bus;

    s.ax = 0x0040u;                              /* MOV AX,40 @04F9 */
    s.es = s.ax;                                 /* MOV ES,AX @04FC */
    s.dx = read16(&s, s.es, 0x0063u);            /* MOV DX,[ES:63] @04FE */
#if VGA_MIRRORS_MUTATION == 10
    s.dx = 0x03d4u;
#endif
    write16(&s, s.ds, SEG09A9_DisplayControllerBasePort, s.dx);
                                                    /* MOV [DS:1FDA],DX @0503 */
    {
        uint8_t before = (uint8_t)s.dx;
        uint8_t after = (uint8_t)(before + 6u);
        s.dx = (uint16_t)((s.dx & 0xff00u) | after);
        s.flags = add8_flags(s.flags, before, 6u); /* ADD DL,6 @0507 */
    }
    write16(&s, s.ds, SEG09A9_DisplayStatusPort1FDC, s.dx);
                                                    /* MOV [DS:1FDC],DX @050A */

    s.ax = 0x0002u; write16(&s, s.ss, SEG143E_VgaMapMaskMirror, s.ax);
    s.ax = 0x0000u; write16(&s, s.ss, SEG143E_VgaSetResetMirror, s.ax);
    s.ax = 0x0001u; write16(&s, s.ss, SEG143E_VgaEnableSetResetMirror, s.ax);
    s.ax = 0x0002u; write16(&s, s.ss, SEG143E_VgaColorCompareMirror, s.ax);
    s.ax = 0x0003u; write16(&s, s.ss, SEG143E_VgaDataRotateMirror, s.ax);
#if VGA_MIRRORS_MUTATION == 9
    s.ax = 0x0004u; write16(&s, s.ss, SEG143E_VgaBitMaskMirror, s.ax);
#else
    s.ax = 0x0004u;
#if VGA_MIRRORS_MUTATION != 8
    write16(&s, s.ss, SEG143E_VgaReadMapMirror, s.ax);
#endif
#endif
    s.ax = 0x0005u; write16(&s, s.ss, SEG143E_VgaGraphicsModeMirror, s.ax);
    s.ax = 0x0f07u; write16(&s, s.ss, SEG143E_VgaColorCareMirror, s.ax);
#if VGA_MIRRORS_MUTATION == 7
    s.ax = 0xff08u; write16(&s, s.ss, SEG143E_VgaBitMaskMirror, s.ax);
#else
    s.ax = 0xff08u; write16(&s, s.ss, SEG143E_VgaReadMapMirror, s.ax);
#endif
    return result_of(&s);                        /* before RET @054D */
}

static LmnVgaMirrorsCall call_from_registers(const LmnRegs *r) {
    LmnVgaMirrorsCall call;
    call.ax = r->ax; call.bx = r->bx; call.cx = r->cx;
    call.dx = r->dx; call.si = r->si; call.di = r->di;
    call.bp = r->bp; call.code_segment = r->cs;
    call.data_segment = r->ds; call.extra_segment = r->es;
    call.stack_segment = r->ss; call.stack_offset = r->sp;
    call.flags = r->flags;
    return call;
}

uint16_t lmn_restore_vga_register_mirrors_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus) {
    LmnVgaMirrorsCall call = call_from_registers(registers);
    LmnVgaMirrorsResult out =
        lmn_restore_vga_register_mirrors_core(memory, &call, bus);
    apply_result(registers, &out);
    if (out.status == LMN_VGA_MIRRORS_READY) {
        registers->ip = read_stack_return(memory, registers->ss,
            registers->sp, registers->flags, bus);
        registers->sp = (uint16_t)(registers->sp + 2u);
    }
    return out.status;
}

uint16_t lmn_initialize_vga_register_mirrors_adapter(
    uint8_t *memory, LmnRegs *registers, const LmnRasterBus *bus) {
    LmnVgaMirrorsCall call = call_from_registers(registers);
    LmnVgaMirrorsResult out =
        lmn_initialize_vga_register_mirrors_core(memory, &call, bus);
    apply_result(registers, &out);
    if (out.status == LMN_VGA_MIRRORS_READY) {
        registers->ip = read_stack_return(memory, registers->ss,
            registers->sp, registers->flags, bus);
        registers->sp = (uint16_t)(registers->sp + 2u);
    }
    return out.status;
}

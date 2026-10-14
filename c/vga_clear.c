#include "vga_clear.h"
#include "lemmings_sym.h"

#ifndef CLEAR_MUTATION
#define CLEAR_MUTATION 0
#endif

enum { CF=1, PF=4, AF=16, ZF=64, SF=128, OF=2048, ARITH=0x8d5,
       VGA_ES=0xa000, VGA_SEQ=0x3c4, VGA_GC=0x3ce };

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & 0xfffffu;
}

static void write_byte(uint8_t *mem, uint16_t ss, uint16_t offset,
                       uint8_t value, uint16_t flags, const LmnRasterBus *bus) {
    bus->write_byte(bus->context, mem, physical(ss, offset), value, flags);
}

static void write_word(uint8_t *mem, uint16_t ss, uint16_t offset,
                       uint16_t value, uint16_t flags, const LmnRasterBus *bus) {
    uint32_t address = physical(ss, offset);
    bus->write_byte(bus->context, mem, address, (uint8_t)value, flags);
    bus->write_byte(bus->context, mem, (address + 1u) & 0xfffffu,
                    (uint8_t)(value >> 8), flags);
}

static uint16_t xor_zero_flags(uint16_t flags) {
    /* XOR sets PF/ZF, clears CF/OF, and leaves AF undefined. */
    return (uint16_t)((flags & (uint16_t)~ARITH) | PF | ZF);
}

static void output(uint8_t *mem, uint16_t ss, uint16_t mirror, uint16_t port,
                   uint16_t value, uint16_t flags, const LmnRasterBus *bus) {
    write_word(mem, ss, mirror, value, flags, bus);
    bus->out_word(bus->context, port, value, flags);
}

LmnVgaClearResult lmn_clear_vga_bytes_core(uint8_t *mem, uint16_t stack_segment,
    uint16_t stack_offset, uint16_t output_cursor, uint16_t count, uint16_t flags,
    const LmnRasterBus *bus) {
    uint16_t port = VGA_SEQ;
    uint16_t value = 0x0f02;
    uint32_t writes;
    uint16_t step;

#if CLEAR_MUTATION == 1
    value = 0x0702;
#endif
    output(mem, stack_segment, SEG143E_VgaMapMaskMirror, port, value, flags, bus);
    port = VGA_GC;
    value = 0;
    flags = xor_zero_flags(flags);
    output(mem, stack_segment, SEG143E_VgaSetResetMirror, port, value, flags, bus);
    value = 0x0f01;
    output(mem, stack_segment, SEG143E_VgaEnableSetResetMirror, port, value, flags, bus);
    value = 0x0005;
    output(mem, stack_segment, SEG143E_VgaGraphicsModeMirror, port, value, flags, bus);
    value = 0x0003;
    output(mem, stack_segment, SEG143E_VgaDataRotateMirror, port, value, flags, bus);
    value = 0xff08;
    output(mem, stack_segment, SEG143E_VgaBitMaskMirror, port, value, flags, bus);

    value = VGA_ES;
    flags = xor_zero_flags(flags);
    step = (flags & 0x0400u) ? 0xffffu : 1u;
#if CLEAR_MUTATION == 2
    step = 1u;
#endif
#if CLEAR_MUTATION == 3
    writes = count ? count : 1u;
#else
    writes = count;
#endif
    while (writes != 0) {
        write_byte(mem, VGA_ES, output_cursor, 0, flags, bus);
        output_cursor = (uint16_t)(output_cursor + step);
        --writes;
        --count;
    }
    {
        LmnVgaClearResult result = { value, count, output_cursor, VGA_ES,
            stack_offset, flags, VGA_GC };
        return result;
    }
}

void lmn_clear_vga_bytes_adapter(uint8_t *mem, LmnRegs *regs,
    const LmnRasterBus *bus) {
    LmnVgaClearResult result = lmn_clear_vga_bytes_core(mem, regs->ss, regs->sp,
        regs->di, regs->cx, regs->flags, bus);
    uint32_t address;
    uint8_t low, high;

    regs->ax = result.value;
    regs->cx = result.count;
    regs->dx = result.port;
    regs->di = result.output_cursor;
    regs->es = result.output_segment;
    regs->flags = result.flags;

    /* RET is outside the logical core but retains the live SS:SP bus alias. */
    address = physical(regs->ss, result.stack_offset);
    low = bus->read_byte(bus->context, mem, address, result.flags);
    high = bus->read_byte(bus->context, mem, (address + 1u) & 0xfffffu,
                          result.flags);
    regs->ip = (uint16_t)(low | ((uint16_t)high << 8));
    regs->sp = (uint16_t)(result.stack_offset + 2u);
}

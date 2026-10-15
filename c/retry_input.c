#include "retry_input.h"
#include "lemmings_sym.h"

#ifndef RETRY_INPUT_MUTATION
#define RETRY_INPUT_MUTATION 0
#endif

enum {
    CF = 0x0001, PF = 0x0004, AF = 0x0010, ZF = 0x0040,
    SF = 0x0080, OF = 0x0800, ARITHMETIC_FLAGS = 0x08d5
};

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

#if RETRY_INPUT_MUTATION != 6
static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address] = value;
}
#endif

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset,
                          uint16_t flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_byte(memory, bus, address, flags);
    uint8_t high = read_byte(memory, bus, address + 1u, flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static uint16_t szp_flags(uint16_t value, unsigned width) {
    uint8_t low = (uint8_t)value;
    unsigned parity = 0, bit;
    uint16_t result = 0;
    for (bit = 0; bit < 8u; ++bit)
        parity ^= (low >> bit) & 1u;
    if (!parity)
        result |= PF;
    if (width == 8u ? low == 0u : value == 0u)
        result |= ZF;
    if (width == 8u ? (low & 0x80u) != 0u : (value & 0x8000u) != 0u)
        result |= SF;
    return result;
}

static uint16_t and_flags(uint16_t flags, uint16_t value, unsigned width) {
    /* AND defines CF/OF as zero and sets SZP. AF is undefined; choose clear. */
    return (uint16_t)((flags & (uint16_t)~ARITHMETIC_FLAGS) |
                      szp_flags(value, width));
}

static LmnRetryInputResult wait_loop(uint8_t *memory,
    uint16_t data_segment, uint16_t flags,
    const LmnRasterBus *bus) {
#if RETRY_INPUT_MUTATION == 4
    uint16_t cached_buttons = 0;
    unsigned have_cached_buttons = 0;
#endif

    for (;;) {
        uint16_t buttons, value;
        uint16_t tested;
#if RETRY_INPUT_MUTATION == 4
        if (have_cached_buttons) {
            buttons = cached_buttons;
        } else {
            buttons = read_word(memory, bus, data_segment,
                SEG09A9_InputButtonsWord, flags);
            cached_buttons = buttons;
            have_cached_buttons = 1;
        }
#else
        buttons = read_word(memory, bus, data_segment,
            SEG09A9_InputButtonsWord, flags);
#endif
        value = buttons;
#if RETRY_INPUT_MUTATION == 1
        tested = (uint16_t)(buttons & 0x0003u);
#elif RETRY_INPUT_MUTATION == 2
        tested = buttons;
#else
        tested = (uint16_t)(buttons & 0x0007u);
#endif
        flags = and_flags(flags, tested, 16u);

        if (tested != 0u) {
#if RETRY_INPUT_MUTATION == 3
            uint8_t scan = read_byte(memory, bus,
                physical(data_segment, SEG09A9_KeyboardScanCodeByte), flags);
            value = (uint16_t)((value & 0x00ffu) | ((uint16_t)scan << 8));
            flags = and_flags(flags, scan, 8u);
#endif
            {
                LmnRetryInputResult result = {
                    value, flags, CS_RetryInputReady
                };
                return result;
            }
        }

        {
            uint8_t scan = read_byte(memory, bus,
                physical(data_segment, SEG09A9_KeyboardScanCodeByte), flags);
            value = (uint16_t)((value & 0x00ffu) | ((uint16_t)scan << 8));
#if RETRY_INPUT_MUTATION == 5
            flags = and_flags(flags, value, 16u);
            if (value != 0u) {
#else
            flags = and_flags(flags, scan, 8u);
            if (scan != 0u) {
#endif
                LmnRetryInputResult result = {
                    value, flags, CS_RetryInputReady
                };
                return result;
            }
        }
    }
}

LmnRetryInputResult lmn_wait_retry_input_core(uint8_t *memory,
    uint16_t data_segment, uint16_t flags,
    const LmnRasterBus *bus) {
    return wait_loop(memory, data_segment, flags, bus);
}

LmnRetryInputResult lmn_clear_and_wait_retry_input_core(uint8_t *memory,
    uint16_t data_segment, uint16_t flags,
    const LmnRasterBus *bus) {
#if RETRY_INPUT_MUTATION != 6
    write_byte(memory, bus,
        physical(data_segment, SEG09A9_KeyboardScanCodeByte), 0u, flags);
#endif
    return wait_loop(memory, data_segment, flags, bus);
}

void lmn_retry_input_adapter(uint8_t *memory, LmnRegs *registers,
    int clear_scan_code, const LmnRasterBus *bus) {
    LmnRetryInputResult result = clear_scan_code
        ? lmn_clear_and_wait_retry_input_core(memory, registers->ds,
            registers->flags, bus)
        : lmn_wait_retry_input_core(memory, registers->ds,
            registers->flags, bus);

    registers->ax = result.value;
    registers->flags = result.flags;
    registers->ip = result.continuation;
#if RETRY_INPUT_MUTATION == 7
    {
        uint32_t address = physical(registers->ss, registers->sp);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u, registers->flags);
        registers->sp = (uint16_t)(registers->sp + 2u);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
    }
#endif
}

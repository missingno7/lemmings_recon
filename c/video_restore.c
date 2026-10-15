#include "video_restore.h"
#include "lemmings_sym.h"

#ifndef VIDEO_RESTORE_MUTATION
#define VIDEO_RESTORE_MUTATION 0
#endif

enum {PF = 0x0004, ZF = 0x0040, SF = 0x0080, ARITHMETIC_FLAGS = 0x08d5};

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

static uint16_t logical_flags(uint16_t flags, uint16_t value) {
    unsigned parity = 0, bit;
    uint16_t result = (uint16_t)(flags & (uint16_t)~ARITHMETIC_FLAGS);
    for (bit = 0; bit < 8; ++bit)
        parity ^= (value >> bit) & 1u;
    if (!parity)
        result |= PF;
    if ((value & 0x00ffu) == 0)
        result |= ZF;
    if (value & 0x0080u)
        result |= SF;
    return result;
}

static LmnVideoRestoreState call_mode(const LmnVideoRestoreServices *services,
    uint8_t *memory, const LmnVideoRestoreState *input) {
    LmnVideoRestoreState out = *input;
    services->set_mode(services->context, memory, input, &out);
    return out;
}

static LmnVideoRestoreState call_page(const LmnVideoRestoreServices *services,
    uint8_t *memory, const LmnVideoRestoreState *input) {
    LmnVideoRestoreState out = *input;
    services->set_active_page(services->context, memory, input, &out);
    return out;
}

LmnVideoRestoreResult lmn_restore_video_mode_page_core(uint8_t *memory,
    const LmnVideoRestoreState *input, const LmnVideoRestoreServices *services,
    const LmnRasterBus *bus) {
    LmnVideoRestoreState state = *input;
#if VIDEO_RESTORE_MUTATION == 1 || VIDEO_RESTORE_MUTATION == 3
    uint16_t entry_data_segment = input->data_segment;
#endif
    uint8_t mode, page;
#if VIDEO_RESTORE_MUTATION == 2
    uint16_t saved_xor_flags;
#endif
#if VIDEO_RESTORE_MUTATION == 3
    uint8_t entry_page;
#endif

#if VIDEO_RESTORE_MUTATION == 3
    /* Mutant-only snapshot; the ordinary path reads the live byte after BIOS. */
    entry_page = memory[physical(entry_data_segment,
                                 SEG09A9_SavedVideoPage)];
#endif
    mode = read_byte(memory, bus,
                     physical(state.data_segment, SEG09A9_SavedVideoMode),
                     state.flags);
    state.value = (uint16_t)(mode);
    state.flags = logical_flags(state.flags, 0); /* XOR AH,AH */
#if VIDEO_RESTORE_MUTATION == 2
    saved_xor_flags = state.flags;
#endif

    if (!services || !services->set_mode) {
        LmnVideoRestoreResult out = {
            state, CS_RestoreVideoModeInterrupt,
            LMN_VIDEO_RESTORE_MISSING_MODE
        };
        return out;
    }
    state = call_mode(services, memory, &state);

#if VIDEO_RESTORE_MUTATION == 3
    /* Mutant: use the page byte cached before the first BIOS provider. */
    page = entry_page;
#elif VIDEO_RESTORE_MUTATION == 1
    /* Mutant: address the page byte with DS from routine entry. */
    page = read_byte(memory, bus,
                     physical(entry_data_segment, SEG09A9_SavedVideoPage),
                     state.flags);
#else
    page = read_byte(memory, bus,
                     physical(state.data_segment, SEG09A9_SavedVideoPage),
                     state.flags);
#endif
    state.value = (uint16_t)(0x0500u | page); /* MOV AH,05; MOV AL,[DS:page] */

    if (!services->set_active_page) {
        LmnVideoRestoreResult out = {
            state, CS_RestoreVideoPageInterrupt,
            LMN_VIDEO_RESTORE_MISSING_PAGE
        };
        return out;
    }
    state = call_page(services, memory, &state);
#if VIDEO_RESTORE_MUTATION == 2
    /* Mutant: discard FLAGS returned by the second BIOS provider. */
    state.flags = saved_xor_flags;
#endif
    {
        LmnVideoRestoreResult out = {
            state, CS_RestoreVideoReturn, LMN_VIDEO_RESTORE_READY
        };
        return out;
    }
}

static LmnVideoRestoreState state_from_registers(const LmnRegs *registers) {
    LmnVideoRestoreState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers, const LmnVideoRestoreState *state) {
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

void lmn_restore_video_mode_page_adapter(uint8_t *memory, LmnRegs *registers,
    const LmnVideoRestoreServices *services, const LmnRasterBus *bus) {
#if VIDEO_RESTORE_MUTATION == 4
    uint32_t entry_address = physical(registers->ss, registers->sp);
    uint16_t stale_return = (uint16_t)(memory[entry_address] |
        ((uint16_t)memory[(entry_address + 1u) & 0xfffffu] << 8));
#endif
    LmnVideoRestoreState input = state_from_registers(registers);
    LmnVideoRestoreResult out = lmn_restore_video_mode_page_core(
        memory, &input, services, bus);

    apply_state(registers, &out.state);
    registers->ip = out.continuation;
    if (out.status != LMN_VIDEO_RESTORE_READY)
        return;

    /* RET observes the post-provider live stack and reads low byte first. */
    {
        uint32_t address = physical(registers->ss, registers->sp);
        uint8_t low = read_byte(memory, bus, address, registers->flags);
        uint8_t high = read_byte(memory, bus, address + 1u, registers->flags);
        registers->sp = (uint16_t)(registers->sp + 2u);
        registers->ip = (uint16_t)(low | ((uint16_t)high << 8));
#if VIDEO_RESTORE_MUTATION == 4
        /* Mutant: return to the word cached before providers ran. */
        registers->ip = stale_return;
#endif
    }
}

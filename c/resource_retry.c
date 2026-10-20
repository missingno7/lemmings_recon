#include "resource_retry.h"
#include "lemmings_sym.h"

#ifndef RESOURCE_RETRY_MUTATION
#define RESOURCE_RETRY_MUTATION 0
#endif

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

/* The word's high byte is at physical-address+1, including offset FFFF. */
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

static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      LmnVideoRestoreState *state, uint16_t value) {
    state->stack_offset = (uint16_t)(state->stack_offset - 2u);
    write_word(memory, bus, state->stack_segment, state->stack_offset,
               value, state->flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         LmnVideoRestoreState *state) {
    uint16_t value = read_word(memory, bus, state->stack_segment,
                               state->stack_offset, state->flags);
    state->stack_offset = (uint16_t)(state->stack_offset + 2u);
    return value;
}

static LmnResourceRetryResult make_result(const LmnVideoRestoreState *state,
                                    uint16_t code_segment,
                                    uint16_t continuation,
                                    enum LmnResourceRetryStatus status,
                                    uint16_t child_entry,
                                    uint16_t child_status) {
    LmnResourceRetryResult result = {
        *state, code_segment, continuation, status, child_entry, child_status
    };
    return result;
}

static LmnResourceRetryResult child_stop(const LmnVideoRestoreState *state,
                                  uint16_t code_segment,
                                  uint16_t continuation,
                                  uint16_t child_entry,
                                  uint16_t child_status) {
    return make_result(state, code_segment, continuation,
        LMN_RESOURCE_RETRY_CHILD_STOP, child_entry, child_status);
}

#if RESOURCE_RETRY_MUTATION != 2
static LmnResourceRetryResult changed_return(const LmnVideoRestoreState *state,
                                       uint16_t code_segment,
                                       uint16_t child_entry,
                                       uint16_t target) {
    return make_result(state, code_segment, target,
        LMN_RESOURCE_RETRY_CHANGED_RETURN, child_entry, 0u);
}
#endif

/* Display status/start deliberately have their own twelve-field boundary
   type. Keep both maps explicit so DS/ES/SS and all general registers survive. */
static LmnDisplayStatusState display_status_from_restore(
    const LmnVideoRestoreState *state) {
    LmnDisplayStatusState mapped = {
        state->value, state->base_value, state->count, state->argument,
        state->source_cursor, state->output_cursor, state->frame_cursor,
        state->data_segment, state->extra_segment, state->stack_segment,
        state->stack_offset, state->flags
    };
    return mapped;
}

static void display_status_to_restore(LmnVideoRestoreState *state,
    const LmnDisplayStatusState *mapped) {
    state->value = mapped->value;
    state->base_value = mapped->base_value;
    state->count = mapped->count;
    state->argument = mapped->argument;
    state->source_cursor = mapped->source_cursor;
    state->output_cursor = mapped->output_cursor;
    state->frame_cursor = mapped->frame_cursor;
    state->data_segment = mapped->data_segment;
    state->extra_segment = mapped->extra_segment;
    state->stack_segment = mapped->stack_segment;
    state->stack_offset = mapped->stack_offset;
    state->flags = mapped->flags;
}

static LmnDisplayStartState display_start_from_restore(
    const LmnVideoRestoreState *state) {
    LmnDisplayStartState mapped = {
        state->value, state->base_value, state->count, state->argument,
        state->source_cursor, state->output_cursor, state->frame_cursor,
        state->data_segment, state->extra_segment, state->stack_segment,
        state->stack_offset, state->flags
    };
    return mapped;
}

static void display_start_to_restore(LmnVideoRestoreState *state,
    const LmnDisplayStartState *mapped) {
    state->value = mapped->value;
    state->base_value = mapped->base_value;
    state->count = mapped->count;
    state->argument = mapped->argument;
    state->source_cursor = mapped->source_cursor;
    state->output_cursor = mapped->output_cursor;
    state->frame_cursor = mapped->frame_cursor;
    state->data_segment = mapped->data_segment;
    state->extra_segment = mapped->extra_segment;
    state->stack_segment = mapped->stack_segment;
    state->stack_offset = mapped->stack_offset;
    state->flags = mapped->flags;
}

static LmnVideoRestoreState state_from_registers(const LmnRegs *registers) {
    LmnVideoRestoreState state = {
        registers->ax, registers->bx, registers->cx, registers->dx,
        registers->si, registers->di, registers->bp, registers->ds,
        registers->es, registers->ss, registers->sp, registers->flags
    };
    return state;
}

static void apply_state(LmnRegs *registers,
                        const LmnVideoRestoreState *state) {
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

static uint16_t szp_flags(uint16_t value, unsigned width) {
    uint8_t low = (uint8_t)value;
    unsigned parity = 0, bit;
    uint16_t result = 0;
    for (bit = 0; bit < 8u; ++bit) parity ^= (low >> bit) & 1u;
    if (!parity) result |= 0x0004u;
    if (width == 8u ? low == 0u : value == 0u) result |= 0x0040u;
    if (width == 8u ? (low & 0x80u) != 0u : (value & 0x8000u) != 0u)
        result |= 0x0080u;
    return result;
}

static uint16_t and_flags(uint16_t flags, uint16_t value, unsigned width) {
    return (uint16_t)((flags & (uint16_t)~0x08d5u) | szp_flags(value, width));
}

LmnResourceRetryInputResult lmn_resource_retry_input_core(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus,
    const LmnForegroundPoll *poll) {
    write_byte(memory,bus,physical(registers->ds,
        SEG09A9_KeyboardScanCodeByte),0u,registers->flags);
    for (;;) {
        uint16_t buttons, tested;
        uint8_t scan;
        if (!poll || !poll->poll) {
            registers->ip=0x4B40u;
            return (LmnResourceRetryInputResult){registers->ax,registers->flags,
                0x4B40u,LMN_RESOURCE_RETRY_WAITING,0u};
        }
        registers->ip=0x4B40u;
        {
            uint16_t status=poll->poll(poll->context,memory,registers,0x4B40u);
            if(status){registers->ip=0x4B40u;return (LmnResourceRetryInputResult){registers->ax,registers->flags,
                0x4B40u,LMN_RESOURCE_RETRY_POLL_STOP,status};}
        }
        buttons=read_word(memory,bus,registers->ds,SEG09A9_InputButtonsWord,registers->flags);
        registers->ax=buttons;
#if RESOURCE_RETRY_MUTATION == 10
        tested=(uint16_t)(buttons&3u);
#elif RESOURCE_RETRY_MUTATION == 11
        tested=buttons;
#else
        tested=(uint16_t)(buttons&7u);
#endif
        registers->flags=and_flags(registers->flags,tested,16u);
        if(tested) {
#if RESOURCE_RETRY_MUTATION == 12
            (void)read_byte(memory,bus,physical(registers->ds,
                SEG09A9_KeyboardScanCodeByte),registers->flags);
#endif
            registers->ip=0x4B50u;
            return (LmnResourceRetryInputResult){registers->ax,registers->flags,
                0x4B50u,LMN_RESOURCE_RETRY_READY,0u};
        }
        registers->ip=0x4B48u;
        {
            uint16_t status=poll->poll(poll->context,memory,registers,0x4B48u);
            if(status){registers->ip=0x4B48u;return (LmnResourceRetryInputResult){registers->ax,registers->flags,
                0x4B48u,LMN_RESOURCE_RETRY_POLL_STOP,status};}
        }
        scan=read_byte(memory,bus,physical(registers->ds,
            SEG09A9_KeyboardScanCodeByte),registers->flags);
        registers->ax=(uint16_t)((registers->ax&0x00ffu)|((uint16_t)scan<<8));
        registers->flags=and_flags(registers->flags,scan,8u);
        if(scan){registers->ip=0x4B50u;return (LmnResourceRetryInputResult){registers->ax,registers->flags,
            0x4B50u,LMN_RESOURCE_RETRY_READY,0u};}
    }
}

LmnResourceRetryResult lmn_resource_retry_screen_core(uint8_t *memory,
    uint16_t code_segment, uint16_t game_data_segment,
    const LmnVideoRestoreState *input,
    const LmnVideoRestoreServices *services,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports,
    const LmnForegroundPoll *poll) {
    LmnVideoRestoreState state = *input;
    uint16_t actual_return;

    /* 4B1C CALL 4BE7: mode, DS stores, layout child, then the live child RET. */
    push_word(memory, bus, &state, CS_RetryUiAfterSetup);
    {
        LmnDisplaySetupResult child = lmn_setup_display_core(memory,
            code_segment, &state, LMN_DISPLAY_SETUP_ENTRY_FULL, services, bus);
        state = child.state;
        code_segment = child.code_segment;
        if (child.status != LMN_DISPLAY_SETUP_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_SetupDisplayModeAndLayout, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterSetup)
            return changed_return(&state, code_segment,
                CS_SetupDisplayModeAndLayout, actual_return);
#else
        (void)actual_return;
#endif
    }

#if RESOURCE_RETRY_MUTATION == 4
    /* Mutant: restore the DS captured at entry after the setup child. */
    state.data_segment = input->data_segment;
#endif

#if RESOURCE_RETRY_MUTATION != 1
    /* 4B1F CALL 531E: palette slot one. */
    push_word(memory, bus, &state, CS_RetryUiAfterPalette1);
    {
        LmnPaletteTransitionResult child = lmn_transition_palette_core(
            memory, code_segment, &state, LMN_PALETTE_TRANSITION_SLOT1,
            ports, bus);
        state = child.state;
        code_segment = child.code_segment;
        if (child.status != LMN_PALETTE_TRANSITION_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_TransitionPaletteToSlot1, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterPalette1)
            return changed_return(&state, code_segment,
                CS_TransitionPaletteToSlot1, actual_return);
#else
        (void)actual_return;
#endif
    }
#endif

    /* 4B22 CALL 4DEF: full drawing-page clear. */
    push_word(memory, bus, &state, CS_RetryUiAfterFirstClear);
    {
        LmnDisplayPagesResult child = lmn_clear_full_drawing_page_core(
            memory, &state, bus);
        state = child.state;
        if (child.status != LMN_DISPLAY_PAGES_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_ClearFullDrawingPage, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterFirstClear)
            return changed_return(&state, code_segment,
                CS_ClearFullDrawingPage, actual_return);
#else
        (void)actual_return;
#endif
    }

    /* 4B25 CALL 5017: retain live DS separately from renderer game data. */
    push_word(memory, bus, &state, CS_RetryUiAfterBackground);
    {
        LmnBackgroundDrawingResult child = lmn_draw_background_core(memory,
            code_segment, game_data_segment, &state,
            LMN_BACKGROUND_DRAWING_FULL, bus, ports);
        state = child.state;
        code_segment = child.code_segment;
        if (child.status != LMN_BACKGROUND_DRAWING_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_DrawScreenBackground, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterBackground)
            return changed_return(&state, code_segment,
                CS_DrawScreenBackground, actual_return);
#else
        (void)actual_return;
#endif
    }

    /* 4B28 LEA SI,4ECF; the text core reads through this live DS:SI. */
    state.source_cursor = SEG09A9_ResourceRetryPromptText;
#if RESOURCE_RETRY_MUTATION == 3
    state.data_segment = game_data_segment;
#endif
    /* 4B2C CALL 4D4D. */
    push_word(memory, bus, &state, CS_RetryUiAfterText);
    {
        LmnTextStreamResult child = lmn_draw_text_stream_core(memory,
            code_segment, game_data_segment, &state, bus, ports);
        state = child.state;
        code_segment = child.code_segment;
        if (child.status != LMN_TEXT_STREAM_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_DrawTextStream, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterText)
            return changed_return(&state, code_segment,
                CS_DrawTextStream, actual_return);
#else
        (void)actual_return;
#endif
    }

    /* 4B2F CALL 4DC2: copy the page and retain its live POP DS result. */
    push_word(memory, bus, &state, CS_RetryUiAfterCopy);
    {
        LmnDisplayPagesResult child = lmn_copy_drawing_page_core(
            memory, &state, bus);
        state = child.state;
        if (child.status != LMN_DISPLAY_PAGES_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_CopyDrawingPageToAlternate, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterCopy)
            return changed_return(&state, code_segment,
                CS_CopyDrawingPageToAlternate, actual_return);
#else
        (void)actual_return;
#endif
    }

    /* 4B32 CALL 1550: explicitly map the distinct status boundary type. */
    push_word(memory, bus, &state, CS_RetryUiAfterStatus);
    {
        LmnDisplayStatusState child_input = display_status_from_restore(&state);
        LmnDisplayStatusResult child =
            lmn_wait_display_status_bit3_cycle_core(memory, &child_input,
                                                     ports, bus);
        display_status_to_restore(&state, &child.state);
        if (child.status != LMN_DISPLAY_STATUS_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_WaitForDisplayStatusBit3Cycle, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterStatus)
            return changed_return(&state, code_segment,
                CS_WaitForDisplayStatusBit3Cycle, actual_return);
#else
        (void)actual_return;
#endif
    }

    /* 4B35 CALL 4C32: use the SAVED display-start entry. */
    push_word(memory, bus, &state, CS_RetryUiAfterDisplayStart);
    {
        LmnDisplayStartState child_input = display_start_from_restore(&state);
        LmnDisplayStartResult child = lmn_program_display_start_core(
            memory, &child_input, LMN_DISPLAY_START_ENTRY_SAVED, bus);
        display_start_to_restore(&state, &child.state);
        if (child.status != LMN_DISPLAY_START_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_ProgramAlternateDisplayStart, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterDisplayStart)
            return changed_return(&state, code_segment,
                CS_ProgramAlternateDisplayStart, actual_return);
#else
        (void)actual_return;
#endif
    }

    /* 4B38 CALL 536C: palette slot two. */
    push_word(memory, bus, &state, CS_RetryUiAfterPalette2);
    {
        LmnPaletteTransitionResult child = lmn_transition_palette_core(
            memory, code_segment, &state, LMN_PALETTE_TRANSITION_SLOT2,
            ports, bus);
        state = child.state;
        code_segment = child.code_segment;
        if (child.status != LMN_PALETTE_TRANSITION_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_TransitionPaletteToSlot2, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterPalette2)
            return changed_return(&state, code_segment,
                CS_TransitionPaletteToSlot2, actual_return);
#else
        (void)actual_return;
#endif
    }

    /* 4B3B..4B4F is frame-free. Poll at each IRQ-owned read boundary. */
    {
        LmnRegs registers={state.value,state.base_value,state.count,state.argument,
            state.source_cursor,state.output_cursor,state.frame_cursor,state.stack_offset,
            code_segment,state.data_segment,state.extra_segment,state.stack_segment,
            0x4B40u,state.flags};
        LmnResourceRetryInputResult input_result=lmn_resource_retry_input_core(
            memory,&registers,bus,poll);
        state.value=registers.ax;state.base_value=registers.bx;state.count=registers.cx;
        state.argument=registers.dx;state.source_cursor=registers.si;state.output_cursor=registers.di;
        state.frame_cursor=registers.bp;state.data_segment=registers.ds;state.extra_segment=registers.es;
        state.stack_segment=registers.ss;state.stack_offset=registers.sp;state.flags=registers.flags;
        code_segment=registers.cs;
        if(input_result.status!=LMN_RESOURCE_RETRY_READY)
            return make_result(&state,code_segment,input_result.continuation,
                (enum LmnResourceRetryStatus)input_result.status,0u,input_result.service_status);
    }

    /* 4B50 CALL 531E: palette slot one after retry input. */
    push_word(memory, bus, &state, CS_RetryUiAfterExitPalette);
    {
        LmnPaletteTransitionResult child = lmn_transition_palette_core(
            memory, code_segment, &state, LMN_PALETTE_TRANSITION_SLOT1,
            ports, bus);
        state = child.state;
        code_segment = child.code_segment;
        if (child.status != LMN_PALETTE_TRANSITION_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_TransitionPaletteToSlot1, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterExitPalette)
            return changed_return(&state, code_segment,
                CS_TransitionPaletteToSlot1, actual_return);
#else
        (void)actual_return;
#endif
    }

    /* 4B53 CALL 4DEF: final clear. */
    push_word(memory, bus, &state, CS_RetryUiAfterFinalClear);
    {
        LmnDisplayPagesResult child = lmn_clear_full_drawing_page_core(
            memory, &state, bus);
        state = child.state;
        if (child.status != LMN_DISPLAY_PAGES_READY)
            return child_stop(&state, code_segment, child.continuation,
                CS_ClearFullDrawingPage, (uint16_t)child.status);
        actual_return = pop_word(memory, bus, &state);
#if RESOURCE_RETRY_MUTATION != 2
        if (actual_return != CS_RetryUiAfterFinalClear)
            return changed_return(&state, code_segment,
                CS_ClearFullDrawingPage, actual_return);
#else
        (void)actual_return;
#endif
    }

    /* 4B56 clears the then-live DS byte; 4B5B's outer RET stays unconsumed. */
#if RESOURCE_RETRY_MUTATION != 5
    write_byte(memory, bus,
        physical(state.data_segment, SEG09A9_DatCriticalErrorFlag), 0u,
        state.flags);
#endif
    return make_result(&state, code_segment, CS_RetryUiReturn,
                       LMN_RESOURCE_RETRY_READY, 0u, 0u);
}

void lmn_resource_retry_screen_adapter(uint8_t *memory,
    LmnRegs *registers, uint16_t game_data_segment,
    const LmnVideoRestoreServices *services,
    const LmnRasterBus *bus, const LmnRasterBytePorts *ports,
    const LmnForegroundPoll *poll) {
#if RESOURCE_RETRY_MUTATION == 6
    uint16_t entry_stack_segment = registers->ss;
    uint16_t entry_stack_offset = registers->sp;
    uint16_t cached_return = read_word(memory, bus, entry_stack_segment,
        entry_stack_offset, registers->flags);
#endif
    LmnVideoRestoreState input = state_from_registers(registers);
    LmnResourceRetryResult result = lmn_resource_retry_screen_core(memory,
        registers->cs, game_data_segment, &input, services, bus, ports, poll);

    apply_state(registers, &result.state);
    registers->cs = result.code_segment;
    registers->ip = result.continuation;
    if (result.status != LMN_RESOURCE_RETRY_READY)
        return;

#if RESOURCE_RETRY_MUTATION == 6
    registers->ss = entry_stack_segment;
    registers->sp = (uint16_t)(entry_stack_offset + 2u);
    registers->ip = cached_return;
#else
    {
        LmnVideoRestoreState state = result.state;
        registers->ip = pop_word(memory, bus, &state);
        registers->ss = state.stack_segment;
        registers->sp = state.stack_offset;
    }
#endif
}

#include "timer_tail.h"

#include "lemmings_sym.h"
#include "fixed_pattern_update.h"
#include "palette_ports.h"
#include "ui_commands.h"
#include "vga_mirrors.h"
#include <stddef.h>

#ifndef TIMER_TAIL_MUTATION
#define TIMER_TAIL_MUTATION 0
#endif
#ifndef GAME_TIMER_MUTATION
#define GAME_TIMER_MUTATION 0
#endif
#ifndef MENU_TIMER_MUTATION
#define MENU_TIMER_MUTATION 0
#endif
#ifndef TIMER_INSTALL_MUTATION
#define TIMER_INSTALL_MUTATION 0
#endif

enum {
    MEMORY_MASK = 0xfffff,
    CF = 0x0001,
    PF = 0x0004,
    AF = 0x0010,
    ZF = 0x0040,
    SF = 0x0080,
    TF = 0x0100,
    IF = 0x0200,
    OF = 0x0800,
    ARITH = CF | PF | AF | ZF | SF | OF,
    /* AF is architecturally undefined for logic. The bounded original oracle
       clears it; keep that concrete value when PUSHF materializes the flags. */
    LOGIC = CF | PF | AF | ZF | SF | OF,
    IRET_FLAGS = 0x7fd5,
    TIMER_INPUT_RETURN = CS_GameTimerAfterInput1843,
    TIMER_INT60 = CS_GameTimerInt60185F,
    TIMER_AFTER_INT60 = CS_GameTimerAfterInt601861,
    TIMER_INT61 = CS_GameTimerInt611872,
    TIMER_AFTER_INT61 = CS_GameTimerAfterInt611874,
    TIMER_COMMAND_RETURN = CS_GameTimerAfterCommands1877,
    TIMER_MIRROR_RETURN = CS_GameTimerAfterMirrors1881,
    TIMER_EOI_RETURN = CS_GameTimerAfterEoi1891,
    TIMER_CHAIN_RESUME = CS_GameTimerChainReturn189D,
    TIMER_CHAIN_JUMP = CS_GameTimerFarChain1899,
    TIMER_OUTER_IRET = CS_GameTimerOuterIret18B1
};

typedef struct TimerTailState {
    uint8_t *memory;
    const LmnInputPollService *mouse;
    const LmnInterruptService *int60;
    const LmnInterruptService *int61;
    const LmnInterruptService *saved_int08;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    LmnRegs r;
    uint16_t entry_cs;
    uint16_t entry_ds;
    uint16_t entry_ss;
    uint16_t status;
    uint16_t child_status;
    uint16_t service_status;
    uint16_t saved_chain_returned;
} TimerTailState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + (uint32_t)offset) & MEMORY_MASK;
}

static uint8_t read_physical8(TimerTailState *s, uint32_t address,
                              uint16_t access_flags) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address,
                                 access_flags);
    return s->memory[address];
}

static void write_physical8(TimerTailState *s, uint32_t address,
                            uint8_t value, uint16_t access_flags) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value,
                           access_flags);
    else
        s->memory[address] = value;
}

static uint8_t read8_at(TimerTailState *s, uint16_t segment,
                        uint16_t offset, uint16_t access_flags) {
    return read_physical8(s, physical(segment, offset), access_flags);
}

static uint8_t read8(TimerTailState *s, uint16_t segment, uint16_t offset) {
    return read8_at(s, segment, offset, s->r.flags);
}

/* Word high bytes follow the low byte physically, including at EA wrap. */
static uint16_t read16_at(TimerTailState *s, uint16_t segment,
                          uint16_t offset, uint16_t access_flags) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical8(s, address, access_flags);
    uint8_t high = read_physical8(s, address + 1u, access_flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static uint16_t read16(TimerTailState *s, uint16_t segment,
                       uint16_t offset) {
    return read16_at(s, segment, offset, s->r.flags);
}

static void write8_at(TimerTailState *s, uint16_t segment, uint16_t offset,
                      uint8_t value, uint16_t access_flags) {
    write_physical8(s, physical(segment, offset), value, access_flags);
}

static void write8(TimerTailState *s, uint16_t segment, uint16_t offset,
                   uint8_t value) {
    write8_at(s, segment, offset, value, s->r.flags);
}

static void write16(TimerTailState *s, uint16_t segment, uint16_t offset,
                    uint16_t value, uint16_t access_flags) {
    uint32_t address = physical(segment, offset);
    write_physical8(s, address, (uint8_t)value, access_flags);
    write_physical8(s, address + 1u, (uint8_t)(value >> 8), access_flags);
}

static void push16(TimerTailState *s, uint16_t value) {
    s->r.sp = (uint16_t)(s->r.sp - 2u);
    write16(s, s->r.ss, s->r.sp, value, s->r.flags);
}

static uint16_t pop16_from(TimerTailState *s, uint16_t stack_segment) {
    uint16_t value = read16(s, stack_segment, s->r.sp);
    s->r.sp = (uint16_t)(s->r.sp + 2u);
    return value;
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity = 0;
    unsigned bit;
    for (bit = 0; bit < 8; ++bit)
        parity ^= (unsigned)((value >> bit) & 1u);
    return parity == 0u;
}

static uint16_t szp8(uint8_t value) {
    uint16_t flags = 0;
    if (even_parity8(value))
        flags |= PF;
    if (value == 0u)
        flags |= ZF;
    if (value & 0x80u)
        flags |= SF;
    return flags;
}

static void logic8(TimerTailState *s, uint8_t value) {
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~LOGIC) | szp8(value));
}

static void cmp8(TimerTailState *s, uint8_t left, uint8_t right) {
    uint8_t result = (uint8_t)(left - right);
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~ARITH);
    flags |= szp8(result);
    if (left < right)
        flags |= CF;
    if ((left ^ right ^ result) & 0x10u)
        flags |= AF;
    if (((left ^ right) & (left ^ result) & 0x80u) != 0u)
        flags |= OF;
    s->r.flags = flags;
}

static uint8_t inc8(TimerTailState *s, uint8_t before) {
    uint8_t result = (uint8_t)(before + 1u);
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~(PF | AF | ZF | SF | OF));
    flags |= szp8(result);
    if ((before & 0x0fu) == 0x0fu)
        flags |= AF;
    if (before == 0x7fu)
        flags |= OF;
    s->r.flags = flags;
    return result;
}

static uint16_t szp16(uint16_t value) {
    uint16_t flags = szp8((uint8_t)value);
    if (value == 0u)
        flags |= ZF;
    else
        flags &= (uint16_t)~ZF;
    if (value & 0x8000u)
        flags |= SF;
    else
        flags &= (uint16_t)~SF;
    return flags;
}

static uint16_t add16(TimerTailState *s, uint16_t left, uint16_t right) {
    uint32_t sum = (uint32_t)left + (uint32_t)right;
    uint16_t result = (uint16_t)sum;
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~ARITH);
    flags |= szp16(result);
    if (sum > 0xffffu)
        flags |= CF;
    if ((left ^ right ^ result) & 0x0010u)
        flags |= AF;
    if (((uint16_t)~(left ^ right) & (left ^ result) & 0x8000u) != 0u)
        flags |= OF;
    s->r.flags = flags;
    return result;
}

static uint8_t add8(TimerTailState *s, uint8_t left, uint8_t right) {
    uint16_t sum = (uint16_t)left + right;
    uint8_t result = (uint8_t)sum;
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~ARITH);
    flags |= szp8(result);
    if (sum > 0xffu)
        flags |= CF;
    if ((left ^ right ^ result) & 0x10u)
        flags |= AF;
    if (((uint8_t)~(left ^ right) & (left ^ result) & 0x80u) != 0u)
        flags |= OF;
    s->r.flags = flags;
    return result;
}

static uint8_t inc_memory8(TimerTailState *s, uint16_t segment,
                           uint16_t offset) {
    uint16_t access_flags = s->r.flags;
    uint8_t before = read8_at(s, segment, offset, access_flags);
    uint8_t result = inc8(s, before);
    /* Both sides of the memory RMW expose the original instruction flags. */
    write8_at(s, segment, offset, result, access_flags);
    return result;
}

static LmnTimerTailResult result_of(const TimerTailState *s) {
    LmnTimerTailResult result;
    result.registers = s->r;
    result.status = s->status;
    result.child_status = s->child_status;
    result.service_status = s->service_status;
    return result;
}

static TimerTailState state_from_registers(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *mouse,
    const LmnInterruptService *int60, const LmnInterruptService *int61,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    TimerTailState s;
    s.memory = memory;
    s.mouse = mouse;
    s.int60 = int60;
    s.int61 = int61;
    s.saved_int08 = saved_int08;
    s.ports = ports;
    s.bus = bus;
    s.r = *registers;
    s.entry_cs = registers->cs;
    s.entry_ds = registers->ds;
    s.entry_ss = registers->ss;
    s.status = LMN_TIMER_TAIL_READY;
    s.child_status = 0u;
    s.service_status = 0u;
    s.saved_chain_returned = 0u;
    return s;
}

static int child_result(TimerTailState *s, uint16_t child_status,
                        uint16_t service_status, uint16_t continuation) {
    if (child_status != 0u) {
        s->status = LMN_TIMER_TAIL_CHILD_STOP;
        s->child_status = child_status;
        s->service_status = service_status;
        return 0;
    }
    if (s->r.cs != s->entry_cs || s->r.ip != continuation) {
#if TIMER_TAIL_MUTATION == 5
        /* Mutant discards the actual child RET target and forces fallthrough. */
        s->r.cs = s->entry_cs;
        s->r.ip = continuation;
#else
        s->status = LMN_TIMER_TAIL_CHANGED_CHILD_RETURN;
        return 0;
#endif
    }
    return 1;
}

static int call_input_poll(TimerTailState *s) {
    LmnInputPollResult child;
    push16(s, TIMER_INPUT_RETURN);              /* CALL 418C @1840 */
    s->r.ip = CS_PollInputState418C;
    child = lmn_poll_input_state_adapter(s->memory, &s->r, s->mouse,
                                         s->ports, s->bus);
    s->r = child.registers;
    return child_result(s, child.status, child.service_status,
                        TIMER_INPUT_RETURN);
}

static int invoke_software_interrupt(TimerTailState *s,
                                     const LmnInterruptService *service,
                                     uint16_t instruction_ip,
                                     uint16_t resume_ip) {
    LmnInterruptResult interrupt_result;
    s->r.ax = 0u;                               /* MOV AX,0 before INT. */
    s->r.ip = instruction_ip;
    interrupt_result = lmn_interrupt_service(s->memory, &s->r,
        instruction_ip == TIMER_INT60 ? 0x60u : 0x61u, resume_ip,
        service, s->bus);
    if (interrupt_result.status == LMN_INTERRUPT_RETURNED)
        return 1;
    s->service_status = interrupt_result.service_status;
    if (interrupt_result.status == LMN_INTERRUPT_UNBOUND_SERVICE)
        s->status = LMN_TIMER_TAIL_UNBOUND_SERVICE;
    else if (interrupt_result.status == LMN_INTERRUPT_PROVIDER_STOP)
        s->status = LMN_TIMER_TAIL_EXTERNAL_STOP;
    else
        s->status = LMN_TIMER_TAIL_CHANGED_INTERRUPT_RETURN;
    return 0;
}

static int call_input_commands(TimerTailState *s) {
    LmnUiCommandsResult child;
    push16(s, TIMER_COMMAND_RETURN);            /* CALL 3E6F @1874 */
    s->r.ip = CS_ProcessInputCommands3E6F;
    child = lmn_process_input_commands_adapter(s->memory, &s->r,
        s->int60, s->int61, s->bus);
    s->r = child.registers;
    return child_result(s, child.status, child.service_status,
                        TIMER_COMMAND_RETURN);
}

static int call_vga_mirrors(TimerTailState *s) {
    uint16_t status;
    push16(s, TIMER_MIRROR_RETURN);             /* CALL 587F @187E */
    s->r.ip = CS_RestoreVgaRegisterMirrors;
    status = lmn_restore_vga_register_mirrors_adapter(s->memory, &s->r,
                                                       s->bus);
    return child_result(s, status, 0u, TIMER_MIRROR_RETURN);
}

static int call_eoi(TimerTailState *s) {
    LmnPortIoResult child;
    push16(s, TIMER_EOI_RETURN);                /* CALL 18B2 @188E */
    s->r.ip = CS_SendMasterPicEoi;
    child = lmn_send_master_pic_eoi_adapter(s->memory, &s->r, s->ports,
                                             s->bus);
    s->r = child.registers;
    return child_result(s, child.status, 0u, TIMER_EOI_RETURN);
}

static int chain_saved_timer(TimerTailState *s) {
    uint16_t target_ip;
    uint16_t target_cs;
    LmnInterruptResult interrupt_result;

    s->r.ax = TIMER_CHAIN_RESUME;               /* MOV AX,189D @1893 */
    push16(s, s->r.flags);                      /* PUSHF @1896 */
    push16(s, s->r.cs);                         /* PUSH CS @1897 */
    push16(s, s->r.ax);                         /* PUSH AX @1898 */

    /* JMP FAR [DS:1FBE] @1899: read offset then segment, live DS. */
    s->r.ip = TIMER_CHAIN_JUMP;
    target_ip = read16(s, s->r.ds, SEG09A9_SavedTimerVector);
    target_cs = read16(s, s->r.ds,
                       (uint16_t)(SEG09A9_SavedTimerVector + 2u));
    s->r.ip = target_ip;
    s->r.cs = target_cs;
    interrupt_result = lmn_interrupt_invoke(s->memory, &s->r,
        s->entry_cs, TIMER_CHAIN_RESUME, s->saved_int08, s->bus);
    if (interrupt_result.status != LMN_INTERRUPT_RETURNED) {
        s->service_status = interrupt_result.service_status;
        if (interrupt_result.status == LMN_INTERRUPT_UNBOUND_SERVICE)
            s->status = LMN_TIMER_TAIL_UNBOUND_SERVICE;
        else if (interrupt_result.status == LMN_INTERRUPT_PROVIDER_STOP)
            s->status = LMN_TIMER_TAIL_EXTERNAL_STOP;
        else
            s->status = LMN_TIMER_TAIL_CHANGED_INTERRUPT_RETURN;
        return 0;
    }
#if TIMER_TAIL_MUTATION == 3
    /* Mutant hides the actual DS returned by the external saved handler. */
    s->r.ds = s->entry_ds;
#endif
    s->saved_chain_returned = 1u;
    return 1;
}

static void finish_local_tail(TimerTailState *s) {
    uint16_t stack_segment;
    uint16_t saved_flags;

    s->r.ip = TIMER_CHAIN_RESUME;
    s->r.flags = (uint16_t)(s->r.flags | IF);  /* STI @189D */
    write8(s, s->r.ds, SEG09A9_TimerChainFlag1FCF, 0xffu);
    (void)inc_memory8(s, s->r.ds, SEG09A9_TimerForegroundCounter1FCD);

#if TIMER_TAIL_MUTATION == 4
    stack_segment = s->saved_chain_returned ? s->entry_ss : s->r.ss;
#else
    stack_segment = s->r.ss;
#endif
    saved_flags = pop16_from(s, stack_segment);  /* POPF @18A7 */
    s->r.flags = (uint16_t)((saved_flags & IRET_FLAGS) | 2u);
    s->r.di = pop16_from(s, stack_segment);      /* POP DI @18A8 */
    s->r.si = pop16_from(s, stack_segment);      /* POP SI @18A9 */
    s->r.bp = pop16_from(s, stack_segment);      /* POP BP @18AA */
    s->r.bx = pop16_from(s, stack_segment);      /* POP BX @18AB */
    s->r.dx = pop16_from(s, stack_segment);      /* POP DX @18AC */
    s->r.cx = pop16_from(s, stack_segment);      /* POP CX @18AD */
    s->r.es = pop16_from(s, stack_segment);      /* POP ES @18AE */
    s->r.ds = pop16_from(s, stack_segment);      /* POP DS @18AF */
    s->r.ax = pop16_from(s, stack_segment);      /* POP AX @18B0 */

    s->r.ip = TIMER_OUTER_IRET;
}

LmnTimerTailResult lmn_game_timer_tail_core(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *mouse,
    const LmnInterruptService *int60, const LmnInterruptService *int61,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    TimerTailState s = state_from_registers(memory, registers, mouse,
        int60, int61, saved_int08, ports, bus);
    uint8_t value;

    s.r.ip = CS_GameTimerTail183E;
    /* Encoded XOR DL,DL @183E preserves DH and leaves AF undefined. */
#if TIMER_TAIL_MUTATION == 1
    s.r.dx = 0u;
#else
    s.r.dx = (uint16_t)(s.r.dx & 0xff00u);
#endif
    logic8(&s, 0u);

    if (!call_input_poll(&s))
        return result_of(&s);

    /* INC byte [DS:001C], MOV AL,[001C], AND AL,1 @1843..184A. */
    (void)inc_memory8(&s, s.r.ds, SEG09A9_TimerCadenceCounter001C);
    value = read8(&s, s.r.ds, SEG09A9_TimerCadenceCounter001C);
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | value);
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | (value & 0x01u));
    logic8(&s, (uint8_t)s.r.ax);
    if ((s.r.flags & ZF) != 0u)
        goto after_int60;

    value = read8(&s, s.r.ds, SEG09A9_ExternalSoundDriverEnabled);
    cmp8(&s, value, 0xffu);
    if ((s.r.flags & ZF) != 0u)
        goto after_int60;
    value = read8(&s, s.r.ds, SEG09A9_SoundOptionBits);
    logic8(&s, (uint8_t)(value & 0x01u));
    if ((s.r.flags & ZF) != 0u)
        goto after_int60;
    if (!invoke_software_interrupt(&s, int60, TIMER_INT60,
                                   TIMER_AFTER_INT60))
        return result_of(&s);

after_int60:
    value = read8(&s, s.r.ds, SEG09A9_ExternalSoundDriverEnabled);
    cmp8(&s, value, 0xffu);
    if ((s.r.flags & ZF) == 0u)
        goto after_int61;
    value = read8(&s, s.r.ds, SEG09A9_SoundOptionBits);
    logic8(&s, (uint8_t)(value & 0x03u));
    if ((s.r.flags & ZF) != 0u)
        goto after_int61;
    if (!invoke_software_interrupt(&s, int61, TIMER_INT61,
                                   TIMER_AFTER_INT61))
        return result_of(&s);

after_int61:
    if (!call_input_commands(&s))
        return result_of(&s);

    value = read8(&s, s.r.ds, SEG09A9_PrivateIrqCounter2002);
    cmp8(&s, value, 0u);
    if ((s.r.flags & ZF) == 0u)
        goto after_mirrors;
    if (!call_vga_mirrors(&s))
        return result_of(&s);

after_mirrors:
    s.r.flags = (uint16_t)(s.r.flags & (uint16_t)~IF); /* CLI @1881 */
    value = read8(&s, s.r.ds, SEG09A9_TimerChainPhase1FE3);
    value = inc8(&s, value);                    /* INC AL @1885 */
#if TIMER_TAIL_MUTATION == 2
    /* Mutant omits the modulo-four AND which controls the timer chain. */
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | value);
#else
    value &= 0x03u;                              /* AND AL,3 @1887 */
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | value);
    logic8(&s, value);
#endif
    write8(&s, s.r.ds, SEG09A9_TimerChainPhase1FE3, value);
    if ((s.r.flags & ZF) == 0u) {
        if (!call_eoi(&s))
            return result_of(&s);
        s.r.ip = TIMER_CHAIN_RESUME;             /* JMP SHORT @1891 */
    } else if (!chain_saved_timer(&s)) {
        return result_of(&s);
    }

    finish_local_tail(&s);
    return result_of(&s);
}

static int full_child_result(TimerTailState *s, uint16_t child_status,
                             uint16_t service_status,
                             uint16_t continuation) {
    if (child_status != 0u) {
        s->status = LMN_TIMER_TAIL_CHILD_STOP;
        s->child_status = child_status;
        s->service_status = service_status;
        return 0;
    }
    if (s->r.cs != s->entry_cs || s->r.ip != continuation) {
#if GAME_TIMER_MUTATION == 5
        /* Mutant discards the actual palette/pattern CALL return target. */
        s->r.cs = s->entry_cs;
        s->r.ip = continuation;
#else
        s->status = LMN_TIMER_TAIL_CHANGED_CHILD_RETURN;
        return 0;
#endif
    }
    return 1;
}

static int timer_palette_call(TimerTailState *s,
    LmnTimerPaletteEntry entry, uint16_t entry_ip, uint16_t return_ip) {
    LmnTimerPaletteResult child;
    push16(s, return_ip);
    s->r.ip = entry_ip;
    child = lmn_timer_palette_adapter(s->memory, &s->r, entry,
                                     s->ports, s->bus);
    s->r = child.registers;

    if (child.status == LMN_TIMER_PALETTE_MISSING_INPUT) {
        s->status = LMN_TIMER_TAIL_CHILD_STOP;
        s->child_status = child.status;
        return 0;
    }
    if (child.status == LMN_TIMER_PALETTE_MISSING_OUTPUT) {
        s->status = LMN_TIMER_TAIL_CHILD_STOP;
        s->child_status = child.status;
        return 0;
    }
    if (child.status == LMN_TIMER_PALETTE_CHANGED_CHILD_RETURN) {
#if GAME_TIMER_MUTATION == 5
        /* Ignore the changed nested palette RET; then consume this CALL's word. */
        s->r.ip = pop16_from(s, s->r.ss);
        return full_child_result(s, 0u, 0u, return_ip);
#else
        s->status = LMN_TIMER_TAIL_CHILD_STOP;
        s->child_status = child.status;
        return 0;
#endif
    }
    if (child.status != LMN_TIMER_PALETTE_READY) {
        s->status = LMN_TIMER_TAIL_CHILD_STOP;
        s->child_status = child.status;
        return 0;
    }
    return full_child_result(s, 0u, 0u, return_ip);
}

static int fixed_pattern_call(TimerTailState *s) {
    uint16_t child_status;
    push16(s, CS_GameTimerTail183E);                         /* CALL 5827 returns 183E */
    s->r.ip = CS_UpdateFixedWordPattern;
    child_status = lmn_update_fixed_word_pattern_adapter(s->memory,
                                                          &s->r, s->bus);
    if (child_status == LMN_FIXED_PATTERN_UPDATE_CHANGED_CHILD_RETURN) {
#if GAME_TIMER_MUTATION == 5
        /* Ignore the changed nested pattern RET and consume this CALL's word. */
        s->r.ip = pop16_from(s, s->r.ss);
        return full_child_result(s, 0u, 0u, CS_GameTimerTail183E);
#else
        s->status = LMN_TIMER_TAIL_CHILD_STOP;
        s->child_status = child_status;
        return 0;
#endif
    }
    return full_child_result(s, child_status, 0u, CS_GameTimerTail183E);
}

static uint16_t read_code_word(const TimerTailState *s, uint16_t offset) {
    uint32_t address = physical(s->r.cs, offset);
    uint8_t low = s->memory[address];
    uint8_t high = s->memory[(address + 1u) & MEMORY_MASK];
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static int timer_word_out(TimerTailState *s, uint16_t port,
                          uint16_t value, uint16_t instruction_ip) {
    s->r.ip = instruction_ip;
    if (!s->bus || !s->bus->out_word) {
        s->status = LMN_GAME_TIMER_MISSING_PORT_OUTPUT;
        return 0;
    }
    s->bus->out_word(s->bus->context, port, value, s->r.flags);
    return 1;
}

static int timer_byte_out(TimerTailState *s, uint16_t port,
                          uint8_t value, uint16_t instruction_ip) {
    s->r.ip = instruction_ip;
    if (!s->ports || !s->ports->out_byte) {
        s->status = LMN_GAME_TIMER_MISSING_PORT_OUTPUT;
        return 0;
    }
    s->ports->out_byte(s->ports->context, s->memory, port, value,
                       s->r.flags);
    return 1;
}

static int timer_byte_in(TimerTailState *s, uint16_t instruction_ip) {
    uint8_t value;
    s->r.ip = instruction_ip;
    if (!s->ports || !s->ports->in_byte) {
        s->status = LMN_GAME_TIMER_MISSING_BYTE_INPUT;
        return 0;
    }
    value = s->ports->in_byte(s->ports->context, s->memory, s->r.dx,
                              s->r.flags);
    s->r.ax = (uint16_t)((s->r.ax & 0xff00u) | value);
    return 1;
}

static int game_timer_prefix(TimerTailState *s) {
    uint8_t value;
    uint16_t crtc_value;
#if GAME_TIMER_MUTATION == 3
    uint16_t cached_pit_reload;
#endif

    /* Preserve the ten actual handler saves in original push order. */
    s->r.ip = 0x17c7u; push16(s, s->r.ax);
    s->r.ip = 0x17c8u; push16(s, s->r.ds);
    s->r.ip = 0x17c9u; push16(s, s->r.es);
    s->r.ip = 0x17cau; push16(s, s->r.cx);
    s->r.ip = 0x17cbu; push16(s, s->r.dx);
    s->r.ip = 0x17ccu; push16(s, s->r.bx);
    s->r.ip = 0x17cdu; push16(s, s->r.bp);
    s->r.ip = 0x17ceu; push16(s, s->r.si);
    s->r.ip = 0x17cfu; push16(s, s->r.di);
    s->r.ip = 0x17d0u; push16(s, s->r.flags);

    /* MOV AX,imm16 at 17D1 reads its operand from the canonical CS image. */
    s->r.ip = 0x17d1u;
#if GAME_TIMER_MUTATION == 1
    s->r.ax = s->entry_ds;
#else
    s->r.ax = read_code_word(s, CS_GameTimerDataSegmentOperand17D2);
#endif
    s->r.ds = s->r.ax;

    s->r.ip = 0x17d6u;
    value = read8(s, s->r.ds, SEG09A9_ConfigurationOption200E);
    cmp8(s, value, 0xffu);
    if ((s->r.flags & ZF) != 0u) {
        s->r.ip = CS_GameTimerTail183E;
        return 1;
    }

    if (!timer_palette_call(s, LMN_TIMER_PALETTE_ENTRY_BEFORE,
                            CS_UpdateTimerPaletteBefore5473,
                            CS_GameTimerAfterPaletteBefore17E0))
        return 0;

    s->r.ip = 0x17e0u;
    s->r.flags = (uint16_t)(s->r.flags & (uint16_t)~IF); /* CLI @17E0 */
    s->r.ip = 0x17e1u;
    s->r.dx = read16(s, s->r.ds, SEG09A9_DisplayControllerBasePort);
    s->r.ip = 0x17e5u;
    s->r.bx = read16(s, s->r.ds, SEG09A9_AlternateDrawingOrigin);
    s->r.ip = 0x17e9u;
    crtc_value = read16(s, s->r.ds, SEG09A9_DrawingPageByteOffset);
    s->r.bx = add16(s, s->r.bx, crtc_value);
    s->r.ip = 0x17edu;
    s->r.bx = add16(s, s->r.bx, 2u);

    /* MOV AH,BH; MOV AL,0C; OUT DX,AX. */
    s->r.ax = (uint16_t)((s->r.ax & 0x00ffu) | (s->r.bx & 0xff00u));
    s->r.ax = (uint16_t)((s->r.ax & 0xff00u) | 0x0cu);
    if (!timer_word_out(s, s->r.dx, s->r.ax, 0x17f4u))
        return 0;
    /* MOV AH,BL; INC AL; OUT DX,AX. */
    s->r.ax = (uint16_t)((s->r.ax & 0x00ffu) |
                         ((s->r.bx & 0x00ffu) << 8));
    value = inc8(s, (uint8_t)s->r.ax);
    s->r.ax = (uint16_t)((s->r.ax & 0xff00u) | value);
    if (!timer_word_out(s, s->r.dx, s->r.ax, 0x17f9u))
        return 0;

    /* ADD DL,6 leaves DH intact; mutation2 widens the addition to DX. */
    s->r.ip = 0x17fau;
    if (GAME_TIMER_MUTATION == 2) {
        s->r.dx = add16(s, s->r.dx, 6u);
    } else {
        value = add8(s, (uint8_t)s->r.dx, 6u);
        s->r.dx = (uint16_t)((s->r.dx & 0xff00u) | value);
    }
    s->r.flags = (uint16_t)(s->r.flags | IF);  /* STI @17FD */

#if GAME_TIMER_MUTATION == 3
    cached_pit_reload = read16(s, s->r.ds, SEG09A9_TimerPitReload1FC9);
#endif
    /* IN/three short jumps/TEST/JZ. The callback owns the finite bound. */
    for (;;) {
        if (!timer_byte_in(s, 0x17feu))
            return 0;
        s->r.ip = 0x1805u;
        logic8(s, (uint8_t)((uint8_t)s->r.ax & 0x08u));
        if ((s->r.flags & ZF) == 0u)
            break;
    }
    /* The second literal loop waits for bit 3 to clear. */
    for (;;) {
        if (!timer_byte_in(s, 0x1809u))
            return 0;
        s->r.ip = 0x1810u;
        logic8(s, (uint8_t)((uint8_t)s->r.ax & 0x08u));
        if ((s->r.flags & ZF) != 0u)
            break;
    }

    s->r.ip = 0x1814u;
#if GAME_TIMER_MUTATION != 4
    s->r.flags = (uint16_t)(s->r.flags & (uint16_t)~IF); /* CLI @1814 */
#endif
    s->r.ip = 0x1815u;
#if GAME_TIMER_MUTATION == 3
    s->r.cx = cached_pit_reload;
#else
    s->r.cx = read16(s, s->r.ds, SEG09A9_TimerPitReload1FC9);
#endif
    s->r.ax = (uint16_t)((s->r.ax & 0xff00u) | 0x36u);
    if (!timer_byte_out(s, 0x43u, (uint8_t)s->r.ax, 0x181bu))
        return 0;
    s->r.ax = (uint16_t)((s->r.ax & 0xff00u) | (uint8_t)s->r.cx);
    if (!timer_byte_out(s, 0x40u, (uint8_t)s->r.ax, 0x1825u))
        return 0;
    s->r.ax = (uint16_t)((s->r.ax & 0xff00u) | (uint8_t)(s->r.cx >> 8));
    if (!timer_byte_out(s, 0x40u, (uint8_t)s->r.ax, 0x182fu))
        return 0;

    s->r.flags = (uint16_t)(s->r.flags | IF);  /* STI @1837 */
    if (!timer_palette_call(s, LMN_TIMER_PALETTE_ENTRY_AFTER,
                            CS_UpdateTimerPaletteAfter553D,
                            CS_GameTimerAfterPaletteAfter183B))
        return 0;
    if (!fixed_pattern_call(s))
        return 0;
    s->r.ip = CS_GameTimerTail183E;
    return 1;
}

LmnTimerTailResult lmn_game_timer_core(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *mouse,
    const LmnInterruptService *int60, const LmnInterruptService *int61,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    TimerTailState s = state_from_registers(memory, registers, mouse,
        int60, int61, saved_int08, ports, bus);
    LmnTimerTailResult result;

    s.r.ip = CS_GameTimerIrqHandler;
    if (!game_timer_prefix(&s))
        return result_of(&s);
    result = lmn_game_timer_tail_core(memory, &s.r, mouse, int60, int61,
                                      saved_int08, ports, bus);
    return result;
}

LmnTimerTailResult lmn_game_timer_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *mouse,
    const LmnInterruptService *int60, const LmnInterruptService *int61,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    LmnTimerTailResult result = lmn_game_timer_core(memory, registers,
        mouse, int60, int61, saved_int08, ports, bus);
    if (result.status == LMN_TIMER_TAIL_READY)
        lmn_interrupt_return(memory, &result.registers, bus);
    return result;
}

LmnTimerTailResult lmn_game_timer_tail_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *mouse,
    const LmnInterruptService *int60, const LmnInterruptService *int61,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    LmnTimerTailResult result = lmn_game_timer_tail_core(memory, registers,
        mouse, int60, int61, saved_int08, ports, bus);
    if (result.status == LMN_TIMER_TAIL_READY)
        lmn_interrupt_return(memory, &result.registers, bus);
    return result;
}

/* Menu4C47 and installer5028 compose the same canonical memory/return services. */
static int menu_child_result(TimerTailState *s, uint16_t status,
                             uint16_t service_status, uint16_t resume) {
    int ready = child_result(s, status, service_status, resume);
#if MENU_TIMER_MUTATION == 5
    if (!ready && s->status == LMN_TIMER_TAIL_CHANGED_CHILD_RETURN) {
        s->r.cs = s->entry_cs; s->r.ip = resume;
        s->status = LMN_TIMER_TAIL_READY;
        return 1;
    }
#endif
    return ready;
}

LmnTimerTailResult lmn_menu_timer_core(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *mouse,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    TimerTailState s = state_from_registers(memory, registers, mouse,
        NULL, NULL, saved_int08, ports, bus);
    uint8_t phase;
#if MENU_TIMER_MUTATION == 3
    uint16_t entry_es = registers->es;
#endif
    push16(&s, s.r.ax); push16(&s, s.r.bx); push16(&s, s.r.cx);
    push16(&s, s.r.dx); push16(&s, s.r.si); push16(&s, s.r.di);
    push16(&s, s.r.bp); push16(&s, s.r.ds);
    s.r.ax = read_code_word(&s, CS_MenuTimerDataSegmentOperand4C50);
    s.r.ds = s.r.ax;
    phase = read8(&s, s.r.ds, SEG09A9_TimerChainPhase1FE3);
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | phase);
    phase = inc8(&s, phase);
    phase &= 3u;
    logic8(&s, phase);
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | phase);
    write8(&s, s.r.ds, SEG09A9_TimerChainPhase1FE3, phase);
#if MENU_TIMER_MUTATION == 1
    if (phase != 0u) {
#else
    if (phase == 0u) {
#endif
        LmnPortIoResult child;
        push16(&s, CS_MenuTimerAfterEoi4C63);
        s.r.ip = CS_SendMasterPicEoi;
        child = lmn_send_master_pic_eoi_adapter(memory, &s.r, ports, bus);
        s.r = child.registers;
        if (!menu_child_result(&s, child.status, 0u, CS_MenuTimerAfterEoi4C63))
            return result_of(&s);
    } else {
        uint16_t target_ip, target_cs;
        LmnInterruptResult chained;
        s.r.ax = CS_MenuTimerChainReturn4C70;
        push16(&s, s.r.flags); push16(&s, s.r.cs); push16(&s, s.r.ax);
        s.r.ip = CS_MenuTimerFarChain4C6C;
        target_ip = read16(&s, s.r.ds, SEG09A9_SavedTimerVector);
        target_cs = read16(&s, s.r.ds, (uint16_t)(SEG09A9_SavedTimerVector + 2u));
        s.r.ip = target_ip; s.r.cs = target_cs;
        chained = lmn_interrupt_invoke(memory, &s.r, s.entry_cs,
            CS_MenuTimerChainReturn4C70, saved_int08, bus);
        if (chained.status != LMN_INTERRUPT_RETURNED) {
            s.service_status = chained.service_status;
            s.status = chained.status == LMN_INTERRUPT_UNBOUND_SERVICE ?
                LMN_TIMER_TAIL_UNBOUND_SERVICE :
                chained.status == LMN_INTERRUPT_PROVIDER_STOP ?
                LMN_TIMER_TAIL_EXTERNAL_STOP : LMN_TIMER_TAIL_CHANGED_INTERRUPT_RETURN;
            return result_of(&s);
        }
#if MENU_TIMER_MUTATION == 4
        s.r.ss = s.entry_ss;
#endif
    }
    s.r.ip = CS_MenuTimerChainReturn4C70;
#if MENU_TIMER_MUTATION == 2
    s.r.dx = 0x00ffu;
#else
    s.r.dx = (uint16_t)((s.r.dx & 0xff00u) | 0xffu);
#endif
    {
        LmnInputPollResult child;
        push16(&s, CS_MenuTimerAfterInput4C75);
        s.r.ip = CS_PollInputState418C;
        child = lmn_poll_input_state_adapter(memory, &s.r, mouse, ports, bus);
        s.r = child.registers;
        if (!menu_child_result(&s, child.status, child.service_status,
                               CS_MenuTimerAfterInput4C75))
            return result_of(&s);
    }
    s.r.ds = pop16_from(&s, s.r.ss); s.r.bp = pop16_from(&s, s.r.ss);
    s.r.di = pop16_from(&s, s.r.ss); s.r.si = pop16_from(&s, s.r.ss);
    s.r.dx = pop16_from(&s, s.r.ss); s.r.cx = pop16_from(&s, s.r.ss);
    s.r.bx = pop16_from(&s, s.r.ss); s.r.ax = pop16_from(&s, s.r.ss);
#if MENU_TIMER_MUTATION == 3
    s.r.es = entry_es;
#endif
    s.r.ip = CS_MenuTimerOuterIret4C7D;
    return result_of(&s);
}

LmnTimerTailResult lmn_menu_timer_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnInputPollService *mouse,
    const LmnInterruptService *saved_int08,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    LmnTimerTailResult out = lmn_menu_timer_core(memory, registers, mouse,
        saved_int08, ports, bus);
    if (out.status == LMN_TIMER_TAIL_READY)
        lmn_interrupt_return(memory, &out.registers, bus);
    return out;
}

LmnTimerTailResult lmn_install_menu_timer_core(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBus *bus) {
    TimerTailState s = state_from_registers(memory, registers, NULL,
        NULL, NULL, NULL, NULL, bus);
#if MENU_TIMER_MUTATION == 7
    uint16_t cached_ds = s.r.ds;
#endif
    s.r.flags &= (uint16_t)~IF;
    push16(&s, s.r.ds);
    s.r.ax = 0u; logic8(&s, 0u); /* XOR AX,AX has the same zero SZP/CF/OF. */
#if MENU_TIMER_MUTATION != 6
    s.r.ds = s.r.ax;
#endif
    write16(&s, s.r.ds, 0x20u, CS_MenuTimerIrqHandler, s.r.flags);
    write16(&s, s.r.ds, 0x22u, s.r.cs, s.r.flags);
#if MENU_TIMER_MUTATION == 7
    s.r.sp = (uint16_t)(s.r.sp + 2u); s.r.ds = cached_ds;
#else
    s.r.ds = pop16_from(&s, s.r.ss);
#endif
#if MENU_TIMER_MUTATION != 8
    s.r.flags |= IF;
#endif
    s.r.ip = CS_MenuTimerInstallReturn503A;
    return result_of(&s);
}

LmnTimerTailResult lmn_install_menu_timer_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnRasterBus *bus) {
    LmnTimerTailResult out = lmn_install_menu_timer_core(memory, registers, bus);
    if (out.status == LMN_TIMER_TAIL_READY) {
        TimerTailState s = state_from_registers(memory, &out.registers, NULL,
            NULL, NULL, NULL, NULL, bus);
        s.r.ip = pop16_from(&s, s.r.ss);
        out.registers = s.r;
    }
    return out;
}

/* Lifecycle entries share bus/flags/transport with the IRQ bodies. */
static int lifecycle_interrupt(TimerTailState *s, uint8_t number,
                               uint16_t resume,
                               const LmnInterruptService *service) {
    LmnInterruptResult out = lmn_interrupt_service(s->memory, &s->r,
        number, resume, service, s->bus);
    if (out.status == LMN_INTERRUPT_RETURNED) return 1;
    s->service_status = out.service_status;
    s->status = out.status == LMN_INTERRUPT_UNBOUND_SERVICE ?
        LMN_TIMER_TAIL_UNBOUND_SERVICE :
        out.status == LMN_INTERRUPT_PROVIDER_STOP ? LMN_TIMER_TAIL_EXTERNAL_STOP :
        LMN_TIMER_TAIL_CHANGED_INTERRUPT_RETURN;
    return 0;
}

LmnTimerTailResult lmn_install_game_timer_core(uint8_t *memory,
    const LmnRegs *registers, const LmnInterruptService *dos,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    TimerTailState s = state_from_registers(memory, registers,
        NULL, NULL, NULL, NULL, ports, bus);
    uint8_t status;
#if TIMER_INSTALL_MUTATION == 6
    uint16_t cached_pit;
#endif
    s.r.flags &= (uint16_t)~IF;
    push16(&s, s.r.ds);
    s.r.ax = 0x2508u;
    push16(&s, s.r.cs);
    s.r.ds = pop16_from(&s, s.r.ss);
    s.r.dx = CS_GameTimerIrqHandler;
    if (!lifecycle_interrupt(&s, 0x21u, CS_GameTimerInstallAfterVector08, dos))
        return result_of(&s);
    s.r.ds = pop16_from(&s, s.r.ss);
#if TIMER_INSTALL_MUTATION == 2
    s.r.ds = s.entry_ds;
#endif
    push16(&s, s.r.ds);
#if TIMER_INSTALL_MUTATION == 1
    s.r.ax = (uint16_t)(s.entry_cs + 0x0842u);
#else
    s.r.ax = read_code_word(&s, CS_GameTimerSoundSegmentOperand);
#endif
    s.r.ds = s.r.ax;
    s.r.ax = 0x2560u;
    s.r.dx = 0x0182u;
    if (!lifecycle_interrupt(&s, 0x21u, CS_GameTimerInstallAfterVector60, dos))
        return result_of(&s);
    s.r.ds = pop16_from(&s, s.r.ss);
    s.r.dx = read16(&s, s.r.ds, SEG09A9_DisplayControllerBasePort);
#if TIMER_INSTALL_MUTATION == 6
    cached_pit = read16(&s, s.r.ds, SEG09A9_TimerPitReload1FC9);
#endif
#if TIMER_INSTALL_MUTATION == 3
    s.r.dx = add16(&s, s.r.dx, 6u);
#else
    s.r.dx = (uint16_t)((s.r.dx & 0xff00u) | add8(&s, (uint8_t)s.r.dx, 6u));
#endif
    do {
        if (!timer_byte_in(&s, 0x1667u)) return result_of(&s);
        status = (uint8_t)s.r.ax & 8u; logic8(&s, status);
    } while (status == 0u);
    do {
        if (!timer_byte_in(&s, 0x166cu)) return result_of(&s);
        status = (uint8_t)s.r.ax & 8u; logic8(&s, status);
    } while (status != 0u);
    s.r.flags &= (uint16_t)~IF;
#if TIMER_INSTALL_MUTATION == 6
    s.r.cx = cached_pit;
#else
    s.r.cx = read16(&s, s.r.ds, SEG09A9_TimerPitReload1FC9);
#endif
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | 0x36u);
    if (!timer_byte_out(&s, 0x43u, (uint8_t)s.r.ax, 0x1678u)) return result_of(&s);
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | (uint8_t)s.r.cx);
    if (!timer_byte_out(&s, 0x40u, (uint8_t)s.r.ax, 0x1682u)) return result_of(&s);
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | (uint8_t)(s.r.cx >> 8));
    if (!timer_byte_out(&s, 0x40u, (uint8_t)s.r.ax, 0x168cu)) return result_of(&s);
#if TIMER_INSTALL_MUTATION != 4
    s.r.flags |= IF;
#endif
    s.r.ip = CS_GameTimerInstallReturn;
    return result_of(&s);
}

static LmnTimerTailResult lifecycle_near_return(uint8_t *memory,
    LmnTimerTailResult out, const LmnRasterBus *bus) {
    if (out.status == LMN_TIMER_TAIL_READY) {
        TimerTailState s = state_from_registers(memory, &out.registers,
            NULL, NULL, NULL, NULL, NULL, bus);
        s.r.ip = pop16_from(&s, s.r.ss);
        out.registers = s.r;
    }
    return out;
}

LmnTimerTailResult lmn_install_game_timer_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnInterruptService *dos,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    return lifecycle_near_return(memory,
        lmn_install_game_timer_core(memory, registers, dos, ports, bus), bus);
}

LmnTimerTailResult lmn_restore_timer_interrupt_core(uint8_t *memory,
    const LmnRegs *registers, const LmnInterruptService *bios_clock,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    TimerTailState s = state_from_registers(memory, registers,
        NULL, NULL, NULL, NULL, ports, bus);
    push16(&s, s.r.ds);
    s.r.flags &= (uint16_t)~IF;
    s.r.ax = (uint16_t)((s.r.ax & 0xff00u) | 0x36u);
    if (!timer_byte_out(&s, 0x43u, (uint8_t)s.r.ax, CS_TimerRestoreControlPort)) return result_of(&s);
    s.r.ax &= 0xff00u; logic8(&s, 0u);
    if (!timer_byte_out(&s, 0x40u, 0u, CS_TimerRestoreCounterLowPort)) return result_of(&s);
    if (!timer_byte_out(&s, 0x40u, 0u, CS_TimerRestoreCounterHighPort)) return result_of(&s);
    s.r.ax = 0u; logic8(&s, 0u);
    s.r.bx = read16(&s, s.r.ds, SEG09A9_SavedTimerVector);
    s.r.es = read16(&s, s.r.ds, (uint16_t)(SEG09A9_SavedTimerVector + 2u));
    s.r.ds = s.r.ax;
#if TIMER_INSTALL_MUTATION == 5
    write16(&s, 0u, 0x22u, s.r.es, s.r.flags);
    write16(&s, 0u, 0x20u, s.r.bx, s.r.flags);
#else
    write16(&s, 0u, 0x20u, s.r.bx, s.r.flags);
    write16(&s, 0u, 0x22u, s.r.es, s.r.flags);
#endif
    s.r.flags |= IF;
    s.r.ds = pop16_from(&s, s.r.ss);
    s.r.cx = read16(&s, s.r.ds, SEG09A9_SavedBiosClockHigh);
    s.r.dx = read16(&s, s.r.ds, SEG09A9_SavedBiosClockLow);
    s.r.ax = (uint16_t)((s.r.ax & 0x00ffu) | 0x0100u);
    if (!lifecycle_interrupt(&s, 0x1au, CS_TimerRestoreReturn, bios_clock))
        return result_of(&s);
    s.r.ip = CS_TimerRestoreReturn;
    return result_of(&s);
}

LmnTimerTailResult lmn_restore_timer_interrupt_adapter(uint8_t *memory,
    const LmnRegs *registers, const LmnInterruptService *bios_clock,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus) {
    return lifecycle_near_return(memory,
        lmn_restore_timer_interrupt_core(memory, registers, bios_clock, ports, bus), bus);
}

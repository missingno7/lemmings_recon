#include "timer_tail.h"

#include "lemmings_sym.h"
#include "ui_commands.h"
#include "vga_mirrors.h"

#ifndef TIMER_TAIL_MUTATION
#define TIMER_TAIL_MUTATION 0
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
    TimerTailState s;
    uint8_t value;

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

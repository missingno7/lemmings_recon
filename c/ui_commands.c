#include "ui_commands.h"

#include "lemmings_sym.h"
#include "view_visibility.h"

#ifndef UI_COMMANDS_MUTATION
#define UI_COMMANDS_MUTATION 0
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
    LOGIC = CF | PF | AF | ZF | SF | OF
};

typedef struct UiCommandsState {
    uint8_t *memory;
    const LmnInterruptService *int60;
    const LmnInterruptService *int61;
    const LmnRasterBus *bus;
    LmnRegs r;
    uint16_t initial_ds;
    uint16_t status;
    uint16_t service_status;
} UiCommandsState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + (uint32_t)offset) & MEMORY_MASK;
}

static uint8_t read_physical8(UiCommandsState *s, uint32_t address,
                              uint16_t flags) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address, flags);
    return s->memory[address];
}

static void write_physical8(UiCommandsState *s, uint32_t address,
                            uint8_t value, uint16_t flags) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value, flags);
    else
        s->memory[address] = value;
}

static uint8_t read8(UiCommandsState *s, uint16_t segment,
                     uint16_t offset) {
    return read_physical8(s, physical(segment, offset), s->r.flags);
}

static uint16_t read16(UiCommandsState *s, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical8(s, address, s->r.flags);
    uint8_t high = read_physical8(s, address + 1u, s->r.flags);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write8(UiCommandsState *s, uint16_t segment, uint16_t offset,
                   uint8_t value) {
    write_physical8(s, physical(segment, offset), value, s->r.flags);
}

static void write16(UiCommandsState *s, uint16_t segment, uint16_t offset,
                    uint16_t value) {
    uint32_t address = physical(segment, offset);
    write_physical8(s, address, (uint8_t)value, s->r.flags);
    write_physical8(s, address + 1u, (uint8_t)(value >> 8), s->r.flags);
}

static uint8_t al(const UiCommandsState *s) {
    return (uint8_t)s->r.ax;
}

static uint8_t ah(const UiCommandsState *s) {
    return (uint8_t)(s->r.ax >> 8);
}

static uint8_t bl(const UiCommandsState *s) {
    return (uint8_t)s->r.bx;
}

static void set_al(UiCommandsState *s, uint8_t value) {
    s->r.ax = (uint16_t)((s->r.ax & 0xff00u) | value);
}

static void set_ah(UiCommandsState *s, uint8_t value) {
    s->r.ax = (uint16_t)((s->r.ax & 0x00ffu) | ((uint16_t)value << 8));
}

static void set_bl(UiCommandsState *s, uint8_t value) {
    s->r.bx = (uint16_t)((s->r.bx & 0xff00u) | value);
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity = 0;
    unsigned bit;
    for (bit = 0; bit < 8u; ++bit)
        parity ^= (unsigned)((value >> bit) & 1u);
    return parity == 0u;
}

static uint16_t szp_flags(uint16_t value, unsigned width) {
    uint8_t low = (uint8_t)value;
    uint16_t flags = 0;
    uint16_t sign = (width == 8u) ? 0x80u : 0x8000u;
    uint16_t mask = (width == 8u) ? 0x00ffu : 0xffffu;
    value &= mask;
    if (value == 0u)
        flags |= ZF;
    if ((value & sign) != 0u)
        flags |= SF;
    if (even_parity8(low))
        flags |= PF;
    return flags;
}

static void arithmetic_flags(UiCommandsState *s, uint16_t result,
                             unsigned width, unsigned carry,
                             unsigned auxiliary, unsigned overflow) {
    uint16_t mask = (width == 8u) ? 0x00ffu : 0xffffu;
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~ARITH);
    result &= mask;
    flags |= szp_flags(result, width);
    if (carry)
        flags |= CF;
    if (auxiliary)
        flags |= AF;
    if (overflow)
        flags |= OF;
    s->r.flags = flags;
}

static void logic_flags(UiCommandsState *s, uint16_t result,
                        unsigned width) {
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~LOGIC);
    flags |= szp_flags(result, width);
    s->r.flags = flags;
}

static uint8_t sub8(UiCommandsState *s, uint8_t left, uint8_t right) {
    uint16_t wide = (uint16_t)left - (uint16_t)right;
    uint8_t result = (uint8_t)wide;
    arithmetic_flags(s, result, 8u, left < right,
        ((left ^ right ^ result) & 0x10u) != 0u,
        (((left ^ right) & (left ^ result) & 0x80u) != 0u));
    return result;
}

static uint16_t sub16(UiCommandsState *s, uint16_t left, uint16_t right) {
    uint32_t wide = (uint32_t)left - (uint32_t)right;
    uint16_t result = (uint16_t)wide;
    arithmetic_flags(s, result, 16u, left < right,
        ((left ^ right ^ result) & 0x10u) != 0u,
        (((left ^ right) & (left ^ result) & 0x8000u) != 0u));
    return result;
}

static uint8_t add8(UiCommandsState *s, uint8_t left, uint8_t right) {
    uint16_t wide = (uint16_t)left + (uint16_t)right;
    uint8_t result = (uint8_t)wide;
    arithmetic_flags(s, result, 8u, wide > 0xffu,
        ((left ^ right ^ result) & 0x10u) != 0u,
        ((~(left ^ right) & (left ^ result) & 0x80u) != 0u));
    return result;
}

static uint16_t add16(UiCommandsState *s, uint16_t left, uint16_t right) {
    uint32_t wide = (uint32_t)left + (uint32_t)right;
    uint16_t result = (uint16_t)wide;
    arithmetic_flags(s, result, 16u, wide > 0xffffu,
        ((left ^ right ^ result) & 0x10u) != 0u,
        ((~(left ^ right) & (left ^ result) & 0x8000u) != 0u));
    return result;
}

static void cmp8(UiCommandsState *s, uint8_t left, uint8_t right) {
    (void)sub8(s, left, right);
}

static void cmp16(UiCommandsState *s, uint16_t left, uint16_t right) {
    (void)sub16(s, left, right);
}

static int zero(const UiCommandsState *s) {
    return (s->r.flags & ZF) != 0u;
}

static int signed_less(const UiCommandsState *s) {
    return ((s->r.flags & SF) != 0u) != ((s->r.flags & OF) != 0u);
}

static int signed_ge(const UiCommandsState *s) {
    return !signed_less(s);
}

static int signed_le(const UiCommandsState *s) {
    return zero(s) || signed_less(s);
}

static void inc8(UiCommandsState *s, uint8_t *value) {
    uint8_t old = *value;
    uint8_t result = (uint8_t)(old + 1u);
    uint16_t carry = (uint16_t)(s->r.flags & CF);
    arithmetic_flags(s, result, 8u, 0u,
        ((old ^ result) & 0x10u) != 0u,
        old == 0x7fu);
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~CF) | carry);
    *value = result;
}

static void dec8(UiCommandsState *s, uint8_t *value) {
    uint8_t old = *value;
    uint8_t result = (uint8_t)(old - 1u);
    uint16_t carry = (uint16_t)(s->r.flags & CF);
    arithmetic_flags(s, result, 8u, 0u,
        ((old ^ result) & 0x10u) != 0u,
        old == 0x80u);
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~CF) | carry);
    *value = result;
}

static void shr16_once(UiCommandsState *s, uint16_t *value) {
    uint16_t old = *value;
    uint16_t result = (uint16_t)(old >> 1);
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~LOGIC);
    if ((old & 1u) != 0u)
        flags |= CF;
    flags |= szp_flags(result, 16u);
    if ((old & 0x8000u) != 0u)
        flags |= OF;
    s->r.flags = flags;
    *value = result;
}

static void shl16_once(UiCommandsState *s, uint16_t *value) {
    uint16_t old = *value;
    uint16_t result = (uint16_t)(old << 1);
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~LOGIC);
    if ((old & 0x8000u) != 0u)
        flags |= CF;
    flags |= szp_flags(result, 16u);
    if ((((old >> 15) ^ (result >> 15)) & 1u) != 0u)
        flags |= OF;
    s->r.flags = flags;
    *value = result;
}

static void shr8_once(UiCommandsState *s, uint8_t *value) {
    uint8_t old = *value;
    uint8_t result = (uint8_t)(old >> 1);
    uint16_t flags = (uint16_t)(s->r.flags & (uint16_t)~LOGIC);
    if ((old & 1u) != 0u)
        flags |= CF;
    flags |= szp_flags(result, 8u);
    if ((old & 0x80u) != 0u)
        flags |= OF;
    s->r.flags = flags;
    *value = result;
}

static void neg8(UiCommandsState *s, uint8_t *value) {
    uint8_t old = *value;
    uint8_t result = (uint8_t)(0u - old);
    arithmetic_flags(s, result, 8u, old != 0u,
        ((old ^ result) & 0x10u) != 0u,
        old == 0x80u);
    *value = result;
}

static void set_status(UiCommandsState *s, uint16_t status,
                       uint16_t service_status) {
    s->status = status;
    s->service_status = service_status;
}

static void push16(UiCommandsState *s, uint16_t value) {
    s->r.sp = (uint16_t)(s->r.sp - 2u);
    {
        uint32_t address = physical(s->r.ss, s->r.sp);
        write_physical8(s, address, (uint8_t)value, s->r.flags);
        write_physical8(s, address + 1u, (uint8_t)(value >> 8), s->r.flags);
    }
}

static uint16_t pop16(UiCommandsState *s) {
    uint16_t value = read16(s, s->r.ss, s->r.sp);
    s->r.sp = (uint16_t)(s->r.sp + 2u);
    return value;
}

static int stop_at_return(const UiCommandsState *s) {
    return s->status != LMN_UI_COMMANDS_READY;
}

static void do_interrupt(UiCommandsState *s, uint16_t vector,
                         uint16_t resume_ip,
                         const LmnInterruptService *service) {
    LmnInterruptResult interrupt_result = lmn_interrupt_service(
        s->memory, &s->r, vector, resume_ip, service, s->bus);
    if (interrupt_result.status == LMN_INTERRUPT_RETURNED) {
        s->service_status = interrupt_result.service_status;
#if UI_COMMANDS_MUTATION == 2
        s->r.ds = s->initial_ds;
#endif
    } else if (interrupt_result.status == LMN_INTERRUPT_UNBOUND_SERVICE) {
        set_status(s, LMN_UI_COMMANDS_UNBOUND_SERVICE,
                   interrupt_result.service_status);
    } else if (interrupt_result.status == LMN_INTERRUPT_PROVIDER_STOP) {
        set_status(s, LMN_UI_COMMANDS_EXTERNAL_STOP,
                   interrupt_result.service_status);
    } else {
        set_status(s, LMN_UI_COMMANDS_CHANGED_INTERRUPT_RETURN,
                   interrupt_result.service_status);
    }
}

static LmnUiCommandsResult result_of(const UiCommandsState *s) {
    LmnUiCommandsResult result;
    result.registers = s->r;
    result.status = s->status;
    result.service_status = s->service_status;
    return result;
}

LmnUiCommandsResult lmn_process_input_commands_core(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInterruptService *int60,
    const LmnInterruptService *int61,
    const LmnRasterBus *bus) {
    UiCommandsState s;
    s.memory = memory;
    s.int60 = int60;
    s.int61 = int61;
    s.bus = bus;
    s.r = *registers;
    s.initial_ds = registers->ds;
    s.status = LMN_UI_COMMANDS_READY;
    s.service_status = 0u;

    s.r.ip = CS_ProcessInputCommands3E6F;
    set_al(&s, read8(&s, s.r.ds, SEG09A9_KeyboardScanCodeByte));
    cmp8(&s, al(&s), 0x3bu);
    if (zero(&s))
        goto loc_4068;

    s.r.ip = 0x3e79u;
    cmp8(&s, al(&s), 0x3cu);
    if (zero(&s))
        goto loc_403d;

    s.r.ip = 0x3e80u;
    cmp8(&s, al(&s), 0x4eu);
    if (zero(&s))
        goto loc_4018;

    s.r.ip = 0x3e87u;
    cmp8(&s, al(&s), 0x57u);
    if (zero(&s))
        goto loc_4018;

    s.r.ip = 0x3e8eu;
    cmp8(&s, al(&s), 0x58u);
    if (zero(&s))
        goto loc_3fef;

    s.r.ip = 0x3e95u;
    cmp8(&s, al(&s), 0x53u);
    if (zero(&s))
        goto loc_3fef;

    s.r.ip = 0x3e9cu;
    set_ah(&s, al(&s));
    s.r.ip = 0x3e9eu;
    set_al(&s, 0x02u);
    s.r.ip = 0x3ea0u;
    cmp8(&s, ah(&s), 0x3du);
    if (zero(&s))
        goto loc_3f5c;

    s.r.ip = 0x3ea8u;
    {
        uint8_t value = al(&s);
        inc8(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x3eaau;
    cmp8(&s, ah(&s), 0x3eu);
    if (zero(&s))
        goto loc_3f5c;

    s.r.ip = 0x3eb2u;
    {
        uint8_t value = al(&s);
        inc8(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x3eb4u;
    cmp8(&s, ah(&s), 0x3fu);
    if (zero(&s))
        goto loc_3f5c;

    s.r.ip = 0x3ebcu;
    {
        uint8_t value = al(&s);
        inc8(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x3ebeu;
    cmp8(&s, ah(&s), 0x40u);
    if (zero(&s))
        goto loc_3f5c;

    s.r.ip = 0x3ec6u;
    {
        uint8_t value = al(&s);
        inc8(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x3ec8u;
    cmp8(&s, ah(&s), 0x41u);
    if (zero(&s))
        goto loc_3f5c;

    s.r.ip = 0x3ed0u;
    {
        uint8_t value = al(&s);
        inc8(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x3ed2u;
    cmp8(&s, ah(&s), 0x42u);
    if (zero(&s))
        goto loc_3f5c;

    s.r.ip = 0x3edau;
    {
        uint8_t value = al(&s);
        inc8(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x3edcu;
    cmp8(&s, ah(&s), 0x43u);
    if (zero(&s))
        goto loc_3f5c;
    /* UNKNOWN 3EE3 is skipped by the conditional jump in the oracle. */
    s.r.ip = 0x3ee4u;
    {
        uint8_t value = al(&s);
        inc8(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x3ee6u;
    cmp8(&s, ah(&s), 0x44u);
    if (zero(&s))
        goto loc_3f5c;
    /* UNKNOWN 3EED is skipped by fallthrough control flow. */

    s.r.ip = 0x3eeeu;
    s.r.ax = read16(&s, s.r.ds, SEG09A9_InputButtonsWord);
    s.r.ip = 0x3ef1u;
    logic_flags(&s, (uint16_t)(s.r.ax & 1u), 16u);
    if (!zero(&s))
        goto loc_3ef9;
    goto loc_3fe3;

loc_3ef9:
    s.r.ip = 0x3ef9u;
    s.r.ax = read16(&s, s.r.ds, SEG09A9_PointerY);
    s.r.ip = 0x3efcu;
    s.r.ax = add16(&s, s.r.ax, 0x0008u);
    s.r.ip = 0x3effu;
    cmp16(&s, s.r.ax, 0x00c0u);
    if (signed_ge(&s))
        goto loc_3f07;
    goto loc_3fe9;

loc_3f07:
    s.r.ip = 0x3f07u;
    s.r.ax = read16(&s, s.r.ds, SEG09A9_PointerX);
    s.r.ip = 0x3f0au;
    s.r.ax = add16(&s, s.r.ax, 0xfff8u);
    s.r.ip = 0x3f0du;
    cmp16(&s, s.r.ax, 0x00d0u);
    if (signed_less(&s))
        goto loc_3f15;
    goto loc_3f92;
    /* UNKNOWN 3F14 is skipped by the short jump. */

loc_3f15:
    s.r.ip = 0x3f15u;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_StatusIconRefreshCounter), 0u);
    if (!zero(&s))
        goto loc_3fe9;

    s.r.ip = 0x3f1fu;
    shr16_once(&s, &s.r.ax);
    s.r.ip = 0x3f21u;
    shr16_once(&s, &s.r.ax);
    s.r.ip = 0x3f23u;
    shr16_once(&s, &s.r.ax);
    s.r.ip = 0x3f25u;
    shr16_once(&s, &s.r.ax);
    s.r.ip = 0x3f27u;
    cmp8(&s, al(&s), 0x02u);
    if (signed_ge(&s))
        goto loc_3f2e;
    goto loc_4032;

loc_3f2e:
    s.r.ip = 0x3f2eu;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_PanelClickLatch0062), 0xffu);
    if (!zero(&s))
        goto loc_3f38;
    goto loc_3fe9;

loc_3f38:
    s.r.ip = 0x3f38u;
    write8(&s, s.r.ds, SEG09A9_PanelClickLatch0062, 0xffu);
    s.r.ip = 0x3f3du;
    cmp8(&s, al(&s), 0x0au);
    if (zero(&s))
        goto loc_4018;

    s.r.ip = 0x3f44u;
    cmp8(&s, al(&s), 0x0bu);
    if (zero(&s))
        goto loc_3fef;

    s.r.ip = 0x3f4bu;
    cmp8(&s, al(&s), 0x0cu);
    if (zero(&s))
        goto loc_3fee;

    s.r.ip = 0x3f52u;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_EntityUpdateGate), 0xffu);
    if (zero(&s))
        goto loc_3fe9;

loc_3f5c:
    s.r.ip = 0x3f5cu;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_StatusIconRefreshCounter), 0u);
    if (!zero(&s))
        goto loc_3fe9;

    s.r.ip = 0x3f66u;
    write8(&s, s.r.ds, SEG09A9_EntityActionSelector, al(&s));
    s.r.ip = 0x3f69u;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_ExternalSoundDriverEnabled), 0xffu);
    if (!zero(&s))
        goto loc_3f7c;
    s.r.ip = 0x3f70u;
    logic_flags(&s,
        (uint16_t)(read8(&s, s.r.ds, SEG09A9_SoundOptionBits) & 0x03u), 8u);
    if (zero(&s))
        goto loc_3f7c;
    s.r.ip = CS_InputCommandsInt613F7A;
    s.r.ax = 0x0401u;
    do_interrupt(&s, 0x61u, CS_InputCommandsAfterInt613F7C, s.int61);
    if (stop_at_return(&s))
        return result_of(&s);

loc_3f7c:
    s.r.ip = CS_InputCommandsAfterInt613F7C;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_ExternalSoundDriverEnabled), 0xffu);
    if (zero(&s))
        goto loc_3f8f;
    s.r.ip = 0x3f83u;
    logic_flags(&s,
        (uint16_t)(read8(&s, s.r.ds, SEG09A9_SoundOptionBits) & 0x01u), 8u);
    if (zero(&s))
        goto loc_3f8f;
    s.r.ip = CS_InputCommandsInt603F8D;
    s.r.ax = 0x0313u;
    do_interrupt(&s, 0x60u, CS_InputCommandsAfterInt603F8F, s.int60);
    if (stop_at_return(&s))
        return result_of(&s);

loc_3f8f:
    goto loc_3fe9;
    /* UNKNOWN 3F91 is skipped by the short jump. */

loc_3f92:
    s.r.ip = 0x3f92u;
    write8(&s, s.r.ds, SEG09A9_PanelClickLatch0062, 0xffu);
    s.r.ip = 0x3f97u;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_TimerChainFlag1FCF), 0u);
    if (!zero(&s))
        goto loc_3fee;

    s.r.ip = 0x3f9eu;
    s.r.bx = read16(&s, s.r.ds, SEG09A9_LevelViewOriginPixels);
    s.r.ip = 0x3fa2u;
    s.r.bx >>= 1;
    s.r.ip = 0x3fa4u;
    s.r.bx >>= 1;
    s.r.ip = 0x3fa6u;
    s.r.bx >>= 1;
    s.r.ip = 0x3fa8u;
    s.r.bx >>= 1;
    s.r.ip = 0x3faau;
    s.r.bx = add16(&s, s.r.bx, 0x00d0u);
    s.r.ip = 0x3faeu;
    cmp16(&s, s.r.ax, s.r.bx);
    if (signed_ge(&s))
        goto loc_3fbe;

    s.r.ip = 0x3fb2u;
    s.r.bx = add16(&s, s.r.bx, 0x0018u);
    s.r.ip = 0x3fb5u;
    cmp16(&s, s.r.ax, s.r.bx);
    if (signed_less(&s))
        goto loc_3fbe;
    s.r.ip = 0x3fb9u;
    cmp16(&s, s.r.ax, 0x00d0u);
    if (signed_less(&s))
        goto loc_3fe9;

loc_3fbe:
    s.r.ip = 0x3fbeu;
    s.r.ax = sub16(&s, s.r.ax, 0x00dau);
    s.r.ip = 0x3fc1u;
    if ((s.r.flags & SF) == 0u)
        goto loc_3fc5;
    s.r.ip = 0x3fc3u;
    s.r.ax = 0u;
    logic_flags(&s, s.r.ax, 16u);

loc_3fc5:
    s.r.ip = 0x3fc5u;
    cmp16(&s, s.r.ax, 0x004fu);
    if (!signed_le(&s))
        goto loc_3fca;
    goto loc_3fcd;

loc_3fca:
    s.r.ip = 0x3fcau;
    s.r.ax = 0x004fu;

loc_3fcd:
    s.r.ip = 0x3fcdu;
    shl16_once(&s, &s.r.ax);
    s.r.ip = 0x3fcfu;
    s.r.ax = add16(&s, s.r.ax, 0x0002u);
    s.r.ip = 0x3fd2u;
    write16(&s, s.r.ds, SEG09A9_LevelViewOriginBytes, s.r.ax);
    s.r.ip = 0x3fd5u;
    shl16_once(&s, &s.r.ax);
    s.r.ip = 0x3fd7u;
    shl16_once(&s, &s.r.ax);
    s.r.ip = 0x3fd9u;
    shl16_once(&s, &s.r.ax);
    s.r.ip = 0x3fdbu;
    write16(&s, s.r.ds, SEG09A9_LevelViewOriginPixels, s.r.ax);

    s.r.ip = CS_InputCommandsViewCall3FDE;
    push16(&s, CS_InputCommandsAfterView3FE1);
    s.r.ip = CS_InputCommandsViewCall3FDE;
    {
        uint16_t child_status = lmn_rebuild_view_visibility_map_live_adapter(
            s.memory, &s.r, s.bus);
        if (child_status != LMN_VIEW_VISIBILITY_READY) {
            set_status(&s, LMN_UI_COMMANDS_CHILD_STOP, child_status);
            return result_of(&s);
        }
#if UI_COMMANDS_MUTATION != 4
        if (s.r.ip != CS_InputCommandsAfterView3FE1) {
            set_status(&s, LMN_UI_COMMANDS_CHANGED_CHILD_RETURN, 0u);
            return result_of(&s);
        }
#endif
    }
    s.r.ip = CS_InputCommandsAfterView3FE1;
    goto loc_3fe9;

loc_3fe3:
    s.r.ip = 0x3fe3u;
    write8(&s, s.r.ds, SEG09A9_PanelClickLatch0062, 0u);
    s.r.ip = CS_InputCommandsReleaseReturn3FE8;
    return result_of(&s);

loc_3fe9:
    s.r.ip = 0x3fe9u;
    write8(&s, s.r.ds, SEG09A9_PanelClickLatch0062, 0xffu);
loc_3fee:
    s.r.ip = CS_InputCommandsReturn3FEE;
    return result_of(&s);

loc_3fef:
    s.r.ip = 0x3fefu;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_EntityUpdateGate), 0xffu);
    if (zero(&s))
        goto loc_3fee;
    s.r.ip = 0x3ff6u;
    write8(&s, s.r.ds, SEG09A9_KeyboardScanCodeByte, 0u);
    s.r.ip = 0x3ffbu;
    set_al(&s, read8(&s, s.r.ds, SEG09A9_ForegroundCounter1FD3));
    s.r.ip = 0x3ffeu;
    set_ah(&s, read8(&s, s.r.ds, SEG09A9_InputActionSnapshot1FD4));
    s.r.ip = 0x4002u;
    write8(&s, s.r.ds, SEG09A9_InputActionSnapshot1FD4, al(&s));
    s.r.ip = 0x4005u;
    set_al(&s, sub8(&s, al(&s), ah(&s)));
    s.r.ip = 0x4007u;
    cmp8(&s, al(&s), 0x05u);
#if UI_COMMANDS_MUTATION == 1
    if ((s.r.flags & (CF | ZF)) == 0u)
        goto loc_3fee;
#else
    if (!zero(&s) && signed_ge(&s))
        goto loc_3fee;
#endif
    s.r.ip = 0x400bu;
    write8(&s, s.r.ds, SEG09A9_EntityScanRequest, 0xffu);
    s.r.ip = 0x4010u;
    set_al(&s, read8(&s, s.r.ds, SEG09A9_EntitySlotBound));
    s.r.ip = 0x4013u;
    write8(&s, s.r.ds, SEG09A9_LevelCreationLimit, al(&s));
    goto loc_3fee;

loc_4018:
    s.r.ip = 0x4018u;
    set_al(&s, read8(&s, s.r.ds, SEG09A9_ForegroundCounter0052));
    s.r.ip = 0x401bu;
    set_bl(&s, al(&s));
    s.r.ip = 0x401du;
    set_bl(&s, sub8(&s, bl(&s),
        read8(&s, s.r.ds, SEG09A9_InputToggleSnapshot0053)));
    s.r.ip = 0x4021u;
    cmp8(&s, bl(&s), 0x02u);
#if UI_COMMANDS_MUTATION == 5
    if (signed_less(&s))
        goto loc_3fee;
#else
    if ((s.r.flags & CF) != 0u)
        goto loc_3fee;
#endif

    s.r.ip = 0x4028u;
    {
        uint8_t old = read8(&s, s.r.ds, SEG09A9_EntityUpdateGate);
        uint8_t result = (uint8_t)(old ^ 0xffu);
        write8(&s, s.r.ds, SEG09A9_EntityUpdateGate, result);
        logic_flags(&s, result, 8u);
    }
    s.r.ip = 0x402du;
    write8(&s, s.r.ds, SEG09A9_InputToggleSnapshot0053, al(&s));
    goto loc_3fee;

loc_4032:
    s.r.ip = 0x4032u;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_EntityUpdateGate), 0xffu);
    if (zero(&s))
        goto loc_3fee;
    s.r.ip = 0x4039u;
    logic_flags(&s, al(&s), 8u);
    if (zero(&s))
        goto loc_4068;

loc_403d:
    s.r.ip = 0x403du;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_LevelReleaseSettingRefreshCounter), 0u);
    if (zero(&s))
        goto loc_4046;
    goto loc_3fe9;

loc_4046:
    s.r.ip = 0x4046u;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_LevelReleaseSetting), 0x63u);
    if (!zero(&s))
        goto loc_404f;
    goto loc_3fe9;

loc_404f:
    s.r.ip = 0x404fu;
    {
        uint8_t value = read8(&s, s.r.ds, SEG09A9_LevelReleaseSetting);
        uint8_t original = value;
        value = (uint8_t)(value + 1u);
        write8(&s, s.r.ds, SEG09A9_LevelReleaseSetting, value);
        inc8(&s, &original);
    }
    goto loc_4053;

loc_4053:
    s.r.ip = 0x4053u;
    set_al(&s, 0x63u);
    s.r.ip = 0x4055u;
    set_al(&s, sub8(&s, al(&s),
        read8(&s, s.r.ds, SEG09A9_LevelReleaseSetting)));
    s.r.ip = 0x4059u;
    {
        uint8_t value = al(&s);
        shr8_once(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x405bu;
    {
        uint8_t value = al(&s);
        neg8(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x405du;
    set_al(&s, add8(&s, al(&s), 0x35u));
    s.r.ip = 0x405fu;
    {
        uint8_t value = al(&s);
        neg8(&s, &value);
        set_al(&s, value);
    }
    s.r.ip = 0x4061u;
    set_al(&s, add8(&s, al(&s), 0x39u));
    s.r.ip = 0x4063u;
    write8(&s, s.r.ds, SEG09A9_EntityCreationReload, al(&s));
    goto loc_3fe9;

loc_4068:
    s.r.ip = 0x4068u;
    set_bl(&s, read8(&s, s.r.ds, SEG09A9_LevelReleaseSettingMinimum));
    s.r.ip = 0x406cu;
    cmp8(&s, read8(&s, s.r.ds, SEG09A9_LevelReleaseSettingRefreshCounter), 0u);
    if (!zero(&s))
        goto loc_3fe9;
    s.r.ip = 0x4076u;
    {
        uint8_t setting = read8(&s, s.r.ds,
                                SEG09A9_LevelReleaseSetting);
        cmp8(&s, setting, bl(&s));
#if UI_COMMANDS_MUTATION == 3
        if ((s.r.flags & (CF | ZF)) != 0u)
            goto loc_3fe9;
#else
        if (zero(&s))
            goto loc_3fe9;
#endif
    }

    s.r.ip = 0x407fu;
    {
        uint8_t value = read8(&s, s.r.ds, SEG09A9_LevelReleaseSetting);
        uint8_t original = value;
        value = (uint8_t)(value - 1u);
        write8(&s, s.r.ds, SEG09A9_LevelReleaseSetting, value);
        dec8(&s, &original);
    }
    goto loc_4053;
}

LmnUiCommandsResult lmn_process_input_commands_adapter(
    uint8_t *memory, const LmnRegs *registers,
    const LmnInterruptService *int60,
    const LmnInterruptService *int61,
    const LmnRasterBus *bus) {
    LmnUiCommandsResult result = lmn_process_input_commands_core(
        memory, registers, int60, int61, bus);
    if (result.status == LMN_UI_COMMANDS_READY) {
        UiCommandsState s;
        s.memory = memory;
        s.int60 = int60;
        s.int61 = int61;
        s.bus = bus;
        s.r = result.registers;
        s.initial_ds = registers->ds;
        s.status = result.status;
        s.service_status = result.service_status;
        s.r.ip = result.registers.ip;
        s.r.ip = pop16(&s);
        result.registers = s.r;
    }
    return result;
}

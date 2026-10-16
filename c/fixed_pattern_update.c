#include "fixed_pattern_update.h"

#include "fixed_pattern_copy.h"
#include "fixed_pattern_draw.h"
#include "lemmings_sym.h"

#ifndef FIXED_PATTERN_UPDATE_MUTATION
#define FIXED_PATTERN_UPDATE_MUTATION 0
#endif

#if FIXED_PATTERN_UPDATE_MUTATION < 0 || FIXED_PATTERN_UPDATE_MUTATION > 10
#error "FIXED_PATTERN_UPDATE_MUTATION must be in the range 0..10"
#endif

enum {
    MEMORY_MASK = 0xfffffu,
    CF = 0x0001u, PF = 0x0004u, AF = 0x0010u, ZF = 0x0040u,
    SF = 0x0080u, OF = 0x0800u,
    ARITH = CF | PF | AF | ZF | SF | OF,
    LOGIC = CF | PF | ZF | SF | OF
};

typedef struct PatternUpdateState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    LmnRegs r;
    uint16_t status, child_entry;
} PatternUpdateState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return (((uint32_t)segment << 4) + offset) & MEMORY_MASK;
}

static uint8_t read_physical(PatternUpdateState *s, uint32_t address) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->read_byte)
        return s->bus->read_byte(s->bus->context, s->memory, address,
                                s->r.flags);
    return s->memory[address];
}

static void write_physical(PatternUpdateState *s, uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if (s->bus && s->bus->write_byte)
        s->bus->write_byte(s->bus->context, s->memory, address, value,
                           s->r.flags);
    else
        s->memory[address] = value;
}

static uint8_t read8(PatternUpdateState *s, uint16_t offset) {
    return read_physical(s, physical(s->r.ds, offset));
}

static uint16_t read16(PatternUpdateState *s, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(s, address);
    uint8_t high = read_physical(s, address + 1u);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

static void write16(PatternUpdateState *s, uint16_t segment,
                    uint16_t offset, uint16_t value) {
    uint32_t address = physical(segment, offset);
    write_physical(s, address, (uint8_t)value);
    write_physical(s, address + 1u, (uint8_t)(value >> 8));
}

static void push(PatternUpdateState *s, uint16_t value) {
    s->r.sp = (uint16_t)(s->r.sp - 2u);
    write16(s, s->r.ss, s->r.sp, value);
}

static uint16_t pop(PatternUpdateState *s) {
    uint16_t value = read16(s, s->r.ss, s->r.sp);
    s->r.sp = (uint16_t)(s->r.sp + 2u);
    return value;
}

static uint16_t szp(uint16_t value, unsigned width) {
    unsigned bit, parity = 0u;
    uint16_t out = 0u;
    for (bit = 0u; bit < 8u; ++bit) parity ^= (value >> bit) & 1u;
    if (!parity) out |= PF;
    if (!value) out |= ZF;
    if (value & (width == 8u ? 0x80u : 0x8000u)) out |= SF;
    return out;
}

static uint16_t logic8_flags(uint16_t flags, uint8_t value) {
    /* AF is undefined after AND/XOR. */
    return (uint16_t)((flags & (uint16_t)~LOGIC) | szp(value, 8u));
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t wide = (uint32_t)left + right;
    uint16_t value = (uint16_t)wide;
    uint16_t out = szp(value, 16u);
    if (wide > 0xffffu) out |= CF;
    out |= (uint16_t)((left ^ right ^ value) & AF);
    if ((~(left ^ right) & (left ^ value) & 0x8000u) != 0u) out |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | out);
}

static uint16_t sub8_flags(uint16_t flags, uint8_t left, uint8_t right) {
    uint8_t value = (uint8_t)(left - right);
    uint16_t out = szp(value, 8u);
    if (left < right) out |= CF;
    out |= (uint16_t)((left ^ right ^ value) & AF);
    if (((left ^ right) & (left ^ value) & 0x80u) != 0u) out |= OF;
    return (uint16_t)((flags & (uint16_t)~ARITH) | out);
}

static void shl_bx_one(PatternUpdateState *s) {
    uint16_t before = s->r.bx;
    uint16_t value = (uint16_t)(before << 1);
    uint16_t out = szp(value, 16u);
    if (before & 0x8000u) out |= CF;
    if (((value >> 15) ^ (before >> 15)) & 1u) out |= OF;
    /* One-bit SHL defines CF/OF/SF/ZF/PF; AF remains opaque. */
    s->r.flags = (uint16_t)((s->r.flags & (uint16_t)~LOGIC) | out);
    s->r.bx = value;
}

static int consume_child_return(PatternUpdateState *s, uint16_t expected,
                                 uint16_t entry, unsigned first) {
    uint16_t target = pop(s);
    if (target == expected) return 1;
#if FIXED_PATTERN_UPDATE_MUTATION == 1
    if (first) return 1;
#else
    (void)first;
#endif
    s->r.ip = target;
    s->status = LMN_FIXED_PATTERN_UPDATE_CHANGED_CHILD_RETURN;
    s->child_entry = entry;
    return 0;
}

static int call_copy(PatternUpdateState *s) {
    LmnFixedPatternCopyCall call;
    LmnFixedPatternCopyResult out;
    push(s, 0x582au);
    call = (LmnFixedPatternCopyCall){s->r.ax, s->r.bx, s->r.cx, s->r.dx,
        s->r.si, s->r.di, s->r.bp, s->r.cs, s->r.ds, s->r.es,
        s->r.ss, s->r.sp, s->r.flags};
    out = lmn_copy_fixed_pattern_vga_spans_core(s->memory, &call, s->bus);
    s->r.ax = out.ax; s->r.bx = out.bx; s->r.cx = out.cx; s->r.dx = out.dx;
    s->r.si = out.si; s->r.di = out.di; s->r.bp = out.bp;
    s->r.cs = out.code_segment; s->r.ds = out.data_segment;
    s->r.es = out.extra_segment; s->r.ss = out.stack_segment;
    s->r.sp = out.stack_offset; s->r.flags = out.flags;
    return consume_child_return(s, 0x582au, CS_CopyFixedPatternVgaSpans, 1u);
}

static int call_draw(PatternUpdateState *s) {
    LmnFixedPatternDrawCall call;
    LmnFixedPatternDrawResult out;
    push(s, 0x5869u);
    call = (LmnFixedPatternDrawCall){s->r.ax, s->r.bx, s->r.cx, s->r.dx,
        s->r.si, s->r.di, s->r.bp, s->r.cs, s->r.ds, s->r.es,
        s->r.ss, s->r.sp, s->r.flags};
    out = lmn_draw_fixed_word_pattern_core(s->memory, &call, s->bus);
    s->r.ax = out.ax; s->r.bx = out.bx; s->r.cx = out.cx; s->r.dx = out.dx;
    s->r.si = out.si; s->r.di = out.di; s->r.bp = out.bp;
    s->r.cs = out.code_segment; s->r.ds = out.data_segment;
    s->r.es = out.extra_segment; s->r.ss = out.stack_segment;
    s->r.sp = out.stack_offset; s->r.flags = out.flags;
    return consume_child_return(s, 0x5869u, CS_DrawFixedWordPattern, 0u);
}

static LmnFixedPatternUpdateResult result_of(const PatternUpdateState *s) {
    LmnFixedPatternUpdateResult out = {
        s->r.ax, s->r.bx, s->r.cx, s->r.dx, s->r.si, s->r.di, s->r.bp,
        s->r.cs, s->r.ds, s->r.es, s->r.ss, s->r.sp, s->r.flags,
        s->r.ip, s->status, s->child_entry};
    return out;
}

LmnFixedPatternUpdateResult lmn_update_fixed_word_pattern_core(
    uint8_t *memory, const LmnFixedPatternUpdateCall *call,
    const LmnRasterBus *bus) {
    PatternUpdateState s = {memory, bus,
        {call->ax, call->bx, call->cx, call->dx, call->si, call->di, call->bp,
         call->stack_offset, call->code_segment, call->data_segment,
         call->extra_segment, call->stack_segment, CS_FixedPatternUpdateReturn,
         call->flags}, LMN_FIXED_PATTERN_UPDATE_READY, 0u};
    uint8_t present;
#if FIXED_PATTERN_UPDATE_MUTATION == 7
    uint16_t cached_ds;
#endif
    if (!call_copy(&s)) return result_of(&s);
    s.r.bx = read16(&s, s.r.ds, SEG09A9_PointerX);              /* 582A */
    s.r.cx = (uint16_t)((s.r.cx & 0xff00u) |
                        read8(&s, SEG09A9_FixedPatternOffsetBias1FE0));
    s.r.cx &= 0x00ffu;
    s.r.flags = logic8_flags(s.r.flags, 0u);                   /* XOR CH,CH */
    s.r.flags = add16_flags(s.r.flags, s.r.bx, s.r.cx);
    s.r.bx = (uint16_t)(s.r.bx + s.r.cx);
#if FIXED_PATTERN_UPDATE_MUTATION == 2
    s.r.bx = (uint16_t)((s.r.bx & 0xff00u) | (s.r.bx & 6u));
#else
    s.r.bx = (uint16_t)((s.r.bx & 0xff00u) | (s.r.bx & 7u));
#endif
    s.r.flags = logic8_flags(s.r.flags, (uint8_t)s.r.bx);      /* AND BL,7 */
    s.r.bx &= 0x00ffu;
    s.r.flags = logic8_flags(s.r.flags, 0u);                   /* XOR BH,BH */
    shl_bx_one(&s); shl_bx_one(&s); shl_bx_one(&s); shl_bx_one(&s);
    s.r.si = s.r.bx;                                          /* 5843 */
    shl_bx_one(&s); shl_bx_one(&s); shl_bx_one(&s);
    s.r.flags = add16_flags(s.r.flags, s.r.si, s.r.bx);
    s.r.si = (uint16_t)(s.r.si + s.r.bx);                      /* ADD SI,BX */
#if FIXED_PATTERN_UPDATE_MUTATION == 3
    s.r.si = (uint16_t)((s.r.si / 0x90u) * 0x60u);
#endif
    present = read8(&s, SEG09A9_EntitySelectionPresent);
    s.r.flags = sub8_flags(s.r.flags, present, 0xffu);
#if FIXED_PATTERN_UPDATE_MUTATION == 4
    if (present != 0u) {
#else
    if (present == 0xffu) {
#endif
#if FIXED_PATTERN_UPDATE_MUTATION == 5
        const uint16_t offset = 0x400u;
#else
        const uint16_t offset = 0x480u;
#endif
        s.r.flags = add16_flags(s.r.flags, s.r.si, offset);
        s.r.si = (uint16_t)(s.r.si + offset);
    }
    s.r.bx = s.r.si;
#if FIXED_PATTERN_UPDATE_MUTATION == 6
    s.r.flags = add16_flags(s.r.flags, s.r.bx, 0x30u);
    s.r.bx = (uint16_t)(s.r.bx + 0x30u);
#else
    s.r.flags = add16_flags(s.r.flags, s.r.bx, 0x60u);
    s.r.bx = (uint16_t)(s.r.bx + 0x60u);
#endif
    s.r.di = read16(&s, s.r.ds, SEG09A9_FixedPatternVgaOffset000C);
#if FIXED_PATTERN_UPDATE_MUTATION == 7
    cached_ds = s.r.ds;
#endif
    push(&s, s.r.ds);                                         /* 5861 */
    s.r.ds = read16(&s, s.r.ds, SEG09A9_GeneratedWordPatternBufferSegment);
    if (!call_draw(&s)) return result_of(&s);
#if FIXED_PATTERN_UPDATE_MUTATION == 7
    (void)pop(&s);
    s.r.ds = cached_ds;
#else
    s.r.ds = pop(&s);                                         /* 5869 */
#endif
    s.r.ax = read16(&s, s.r.ds, SEG09A9_FixedPatternVgaOffset000C);
    {
        uint16_t old = read16(&s, s.r.ds, SEG09A9_FixedPatternVgaOffset000E);
        write16(&s, s.r.ds, SEG09A9_FixedPatternVgaOffset000E, s.r.ax);
        s.r.ax = old;
    }
    write16(&s, s.r.ds, SEG09A9_FixedPatternVgaOffset000C, s.r.ax);
#if FIXED_PATTERN_UPDATE_MUTATION != 8
    s.r.ax = read16(&s, s.r.ds, SEG09A9_FixedPatternVgaOffset0008);
    {
        uint16_t old = read16(&s, s.r.ds, SEG09A9_FixedPatternVgaOffset000A);
        write16(&s, s.r.ds, SEG09A9_FixedPatternVgaOffset000A, s.r.ax);
        s.r.ax = old;
    }
    write16(&s, s.r.ds, SEG09A9_FixedPatternVgaOffset0008, s.r.ax);
#endif
    s.r.ip = CS_FixedPatternUpdateReturn;
    return result_of(&s);
}

uint16_t lmn_update_fixed_word_pattern_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus) {
    LmnFixedPatternUpdateCall call = {registers->ax, registers->bx,
        registers->cx, registers->dx, registers->si, registers->di,
        registers->bp, registers->cs, registers->ds, registers->es,
        registers->ss, registers->sp, registers->flags};
    LmnFixedPatternUpdateResult out;
#if FIXED_PATTERN_UPDATE_MUTATION == 9
    PatternUpdateState return_state = {memory, bus, *registers, 0u, 0u};
    uint16_t prefetched = read16(&return_state, registers->ss, registers->sp);
#endif
    out = lmn_update_fixed_word_pattern_core(memory, &call, bus);
    registers->ax = out.ax; registers->bx = out.bx; registers->cx = out.cx;
    registers->dx = out.dx; registers->si = out.si; registers->di = out.di;
    registers->bp = out.bp; registers->cs = out.code_segment;
    registers->ds = out.data_segment; registers->es = out.extra_segment;
    registers->ss = out.stack_segment; registers->sp = out.stack_offset;
    registers->flags = out.flags; registers->ip = out.continuation;
    if (out.status == LMN_FIXED_PATTERN_UPDATE_READY) {
#if FIXED_PATTERN_UPDATE_MUTATION == 10
        /* Mutation: omit the actual outer RET. */
#else
#if FIXED_PATTERN_UPDATE_MUTATION == 9
        registers->ip = prefetched;
#else
        PatternUpdateState return_state = {memory, bus, *registers, 0u, 0u};
        registers->ip = read16(&return_state, registers->ss, registers->sp);
#endif
        registers->sp = (uint16_t)(registers->sp + 2u);
#endif
    }
    return out.status;
}

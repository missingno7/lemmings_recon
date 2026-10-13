#include "checksum.h"
#include "lemmings_sym.h"

#define MEM_SIZE 0x100000u

#ifndef MUTATION
#define MUTATION 0
#endif

#if MUTATION == 1
#define CURSOR_STEP(v) ((uint16_t)((v) + 2u))
#else
#define CURSOR_STEP(v) ((uint16_t)((v) + 1u))
#endif

#if MUTATION == 2
#define INIT_WINDOW_START (CS_ChecksumWindow + 1u)
#else
#define INIT_WINDOW_START CS_ChecksumWindow
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040, SF=0x0080, OF=0x0800 };
enum { ARITH_FLAGS = CF | PF | AF | ZF | SF | OF };
enum { DEFINED_FLAGS = 0x0fd7 };

static uint32_t physical(uint16_t seg, uint16_t off) {
    return ((((uint32_t)seg << 4) + off) & (MEM_SIZE - 1u));
}

static uint8_t read8(const uint8_t *mem, uint16_t seg, uint16_t off) {
    return mem[physical(seg, off)];
}

static void write8(uint8_t *mem, uint16_t seg, uint16_t off, uint8_t v) {
    mem[physical(seg, off)] = v;
}

static uint16_t read16(const uint8_t *mem, uint16_t seg, uint16_t off) {
    uint32_t at = physical(seg, off);
    return (uint16_t)(mem[at] | ((uint16_t)mem[(at + 1u) & (MEM_SIZE - 1u)] << 8));
}

static void write16(uint8_t *mem, uint16_t seg, uint16_t off, uint16_t v) {
    uint32_t at = physical(seg, off);
    mem[at] = (uint8_t)v;
    mem[(at + 1u) & (MEM_SIZE - 1u)] = (uint8_t)(v >> 8);
}

static unsigned parity_even8(uint8_t value) {
    unsigned parity = 0;
    unsigned i;
    for (i = 0; i < 8; ++i) {
        parity ^= value & 1u;
        value >>= 1;
    }
    return parity == 0;
}

static void set_szp8(uint16_t *flags, uint8_t v) {
    *flags &= (uint16_t)~(PF | ZF | SF);
    if (v == 0) *flags |= ZF;
    if (v & 0x80u) *flags |= SF;
    if (parity_even8(v)) *flags |= PF;
}

/* XOR and AND leave AF undefined; the result mask identifies that case. */
static uint8_t logic8(uint16_t *flags, uint8_t v) {
    *flags &= (uint16_t)~(CF | OF);
    set_szp8(flags, v);
    return v;
}

static void inc8(uint16_t *flags, uint8_t v) {
    uint8_t out = (uint8_t)(v + 1u);
    uint16_t carry = *flags & CF;
    *flags &= (uint16_t)~(AF | OF);
    if ((v & 0x0fu) == 0x0fu) *flags |= AF;
    if (v == 0x7fu) *flags |= OF;
    set_szp8(flags, out);
    *flags = (uint16_t)((*flags & (uint16_t)~CF) | carry);
}

static void inc16(uint16_t *flags, uint16_t v) {
    uint16_t out = (uint16_t)(v + 1u);
    uint16_t carry = *flags & CF;
    *flags &= (uint16_t)~(AF | OF | PF | ZF | SF);
    if ((v & 0x0fu) == 0x0fu) *flags |= AF;
    if (v == 0x7fffu) *flags |= OF;
    if (out == 0) *flags |= ZF;
    if (out & 0x8000u) *flags |= SF;
    if (parity_even8((uint8_t)out)) *flags |= PF;
    *flags = (uint16_t)((*flags & (uint16_t)~CF) | carry);
}

static void cmp16(uint16_t *flags, uint16_t lhs, uint16_t rhs) {
    uint16_t out = (uint16_t)(lhs - rhs);
    *flags &= (uint16_t)~ARITH_FLAGS;
    if (lhs < rhs) *flags |= CF;
    if (((lhs ^ rhs ^ out) & 0x10u) != 0) *flags |= AF;
    if (out == 0) *flags |= ZF;
    if (out & 0x8000u) *flags |= SF;
    if (parity_even8((uint8_t)out)) *flags |= PF;
    if (((lhs ^ rhs) & (lhs ^ out) & 0x8000u) != 0) *flags |= OF;
}

static LmnChecksumResult result(uint16_t ax, uint16_t bx, uint16_t cx,
                                uint16_t flags, uint16_t defined) {
    LmnChecksumResult out = { ax, bx, cx, flags, defined };
    return out;
}

LmnChecksumResult lmn_initialize_code_checksum_core(uint8_t *mem, uint16_t cs,
                                                      uint16_t initial_ax,
                                                      uint16_t initial_flags) {
    uint16_t bx = INIT_WINDOW_START;
    uint16_t cx = (uint16_t)(CS_ChecksumWindowEnd - CS_ChecksumWindow);
    uint16_t flags = initial_flags;
    uint8_t al = 0;

    al = logic8(&flags, al);                /* xor al,al */
    write8(mem, cs, CS_ChecksumPhase, al);
    write8(mem, cs, CS_ChecksumAccumulator, al);
    write16(mem, cs, CS_ChecksumCursor, bx);
    do {
        al = logic8(&flags, (uint8_t)(al ^ read8(mem, cs, bx)));
        inc16(&flags, bx);
        bx = CURSOR_STEP(bx);
        cx = (uint16_t)(cx - 1u);           /* LOOP does not change flags. */
    } while (cx != 0);
    return result((uint16_t)((initial_ax & 0xff00u) | al), bx, cx,
                  flags, DEFINED_FLAGS);
}

LmnChecksumResult lmn_advance_code_checksum_core(uint8_t *mem, uint16_t cs,
                                                  uint16_t initial_cx,
                                                  uint16_t initial_flags) {
    uint16_t flags = initial_flags;
    uint8_t phase, al;
    uint16_t bx, cx;

    phase = read8(mem, cs, CS_ChecksumPhase);
    inc8(&flags, phase);
    phase = (uint8_t)(phase + 1u);
    write8(mem, cs, CS_ChecksumPhase, phase);
    al = logic8(&flags, phase);             /* and al,al */
    if (al == 0) {
        bx = 0;
        write16(mem, cs, CS_ChecksumCursor, bx);
        al = read8(mem, cs, CS_ChecksumAccumulator);
        write8(mem, cs, CS_ChecksumAccumulator, 0);
        logic8(&flags, 0);                  /* xor ah,ah; AF remains undefined. */
        return result(al, bx, initial_cx, flags, (uint16_t)(DEFINED_FLAGS & ~AF));
    }

    cx = 0x0800u;
    bx = read16(mem, cs, CS_ChecksumCursor);
    al = read8(mem, cs, CS_ChecksumAccumulator);
    while (1) {
        cmp16(&flags, bx, CS_ChecksumLimit);
#if MUTATION == 3
        if (bx >= CS_ChecksumLimit) {
#else
        if (bx == CS_ChecksumLimit) {
#endif
            write8(mem, cs, CS_ChecksumAccumulator, al);
            write8(mem, cs, CS_ChecksumPhase, 0xffu);
            return result(0xffffu, bx, cx, flags, DEFINED_FLAGS);
        }
        al = logic8(&flags, (uint8_t)(al ^ read8(mem, cs, bx)));
        inc16(&flags, bx);
        bx = CURSOR_STEP(bx);
        cx = (uint16_t)(cx - 1u);
        if (cx == 0) break;
    }
    write8(mem, cs, CS_ChecksumAccumulator, al);
    write16(mem, cs, CS_ChecksumCursor, bx);
    return result((uint16_t)(0xff00u | al), bx, cx, flags, DEFINED_FLAGS);
}

/* The adapters alone model the near-call stack and register boundary. */
static void push16(uint8_t *mem, LmnRegs *r, uint16_t value) {
    r->sp = (uint16_t)(r->sp - 2u);
    write16(mem, r->ss, r->sp, value);
}

static uint16_t pop16(const uint8_t *mem, LmnRegs *r) {
    uint16_t value = read16(mem, r->ss, r->sp);
    r->sp = (uint16_t)(r->sp + 2u);
    return value;
}

static void apply_result(LmnRegs *r, LmnChecksumResult out) {
    r->ax = out.ax;
    r->bx = out.bx;
    r->cx = out.cx;
    r->flags = out.flags;
}

void lmn_initialize_code_checksum_adapter(uint8_t *mem, LmnRegs *r) {
    LmnChecksumResult out;
    push16(mem, r, r->ds);
    push16(mem, r, r->cs);
    r->ds = pop16(mem, r);
    out = lmn_initialize_code_checksum_core(mem, r->cs, r->ax, r->flags);
    apply_result(r, out);
    r->ds = pop16(mem, r);
    r->ip = pop16(mem, r);
}

void lmn_advance_code_checksum_adapter(uint8_t *mem, LmnRegs *r) {
    LmnChecksumResult out;
    push16(mem, r, r->ds);
    push16(mem, r, r->cs);
    r->ds = pop16(mem, r);
    out = lmn_advance_code_checksum_core(mem, r->cs, r->cx, r->flags);
    apply_result(r, out);
    r->ds = pop16(mem, r);
    r->ip = pop16(mem, r);
}

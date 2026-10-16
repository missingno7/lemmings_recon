#include "main_resources.h"

#include "entity_sprite_banks.h"
#include "fixed_word_banks.h"
#include "generated_graphics.h"
#include "lemmings_sym.h"
#include "vga_plane_copy.h"

#ifndef MAIN_RESOURCES_MUTATION
#define MAIN_RESOURCES_MUTATION 0
#endif

#if MAIN_RESOURCES_MUTATION < 0 || MAIN_RESOURCES_MUTATION > 10
#error "MAIN_RESOURCES_MUTATION must be a numeric ID from 0 through 10"
#endif

enum {
    MEMORY_MASK = 0xfffffu,
    CF = 0x0001u, PF = 0x0004u, AF = 0x0010u, ZF = 0x0040u,
    SF = 0x0080u, DF = 0x0400u, OF = 0x0800u,
    ARITH = CF | PF | AF | ZF | SF | OF,
    LOGIC = CF | PF | ZF | SF | OF
};

typedef struct MainResourcesState {
    uint8_t *memory;
    const LmnRasterBus *raster;
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t cs, ds, es, ss, sp, flags;
    uint16_t continuation, status, child_entry, child_status;
} MainResourcesState;

static uint32_t physical(uint16_t segment, uint16_t offset) {
    return ((((uint32_t)segment << 4) + (uint32_t)offset) & MEMORY_MASK);
}

static uint8_t read_physical(MainResourcesState *s, uint32_t address) {
    address &= MEMORY_MASK;
    if (s->raster && s->raster->read_byte)
        return s->raster->read_byte(s->raster->context, s->memory, address,
                                    s->flags);
    return s->memory[address];
}

static void write_physical(MainResourcesState *s, uint32_t address,
                           uint8_t value) {
    address &= MEMORY_MASK;
    if (s->raster && s->raster->write_byte)
        s->raster->write_byte(s->raster->context, s->memory, address, value,
                              s->flags);
    else
        s->memory[address] = value;
}

static uint8_t read8(MainResourcesState *s, uint16_t segment,
                     uint16_t offset) {
    return read_physical(s, physical(segment, offset));
}

static uint16_t read16(MainResourcesState *s, uint16_t segment,
                       uint16_t offset) {
    uint32_t address = physical(segment, offset);
    uint8_t low = read_physical(s, address);
    uint8_t high = read_physical(s, address + 1u);
    return (uint16_t)(low | ((uint16_t)high << 8));
}

/* This read models an immediate code operand. Original instruction fetches
   and relocated immediates are not raster data-bus transactions. */
static uint16_t raw_code_word(const MainResourcesState *s, uint16_t offset) {
    uint32_t address = physical(s->cs, offset);
    return (uint16_t)(s->memory[address] |
        ((uint16_t)s->memory[(address + 1u) & MEMORY_MASK] << 8));
}

static void push16(MainResourcesState *s, uint16_t value) {
    s->sp = (uint16_t)(s->sp - 2u);
    write_physical(s, physical(s->ss, s->sp), (uint8_t)value);
    write_physical(s, physical(s->ss, s->sp) + 1u, (uint8_t)(value >> 8));
}

static uint16_t pop16(MainResourcesState *s) {
    uint16_t value = read16(s, s->ss, s->sp);
    s->sp = (uint16_t)(s->sp + 2u);
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

static uint16_t logic_flags(uint16_t flags, uint16_t value,
                            unsigned width) {
    /* AF is undefined on XOR; retain its incoming opaque value. */
    return (uint16_t)((flags & (uint16_t)~LOGIC) | szp(value, width));
}

static uint16_t add16_flags(uint16_t flags, uint16_t left, uint16_t right) {
    uint32_t wide = (uint32_t)left + (uint32_t)right;
    uint16_t value = (uint16_t)wide;
    uint16_t out = (uint16_t)((flags & (uint16_t)~ARITH) | szp(value, 16u));
    if (wide > 0xffffu) out |= CF;
    out |= (uint16_t)((left ^ right ^ value) & AF);
    if (((uint16_t)~(left ^ right) & (left ^ value) & 0x8000u) != 0u)
        out |= OF;
    return out;
}

static uint16_t sub8_flags(uint16_t flags, uint8_t left, uint8_t right) {
    uint8_t value = (uint8_t)(left - right);
    uint16_t out = (uint16_t)((flags & (uint16_t)~ARITH) | szp(value, 8u));
    if (left < right) out |= CF;
    out |= (uint16_t)((left ^ right ^ value) & AF);
    if (((left ^ right) & (left ^ value) & 0x80u) != 0u) out |= OF;
    return out;
}

static void movs_words(MainResourcesState *s) {
    uint16_t step = (s->flags & DF) ? 0xfffeu : 2u;
    while (s->cx) {
        uint16_t value = read16(s, s->ds, s->si);
        uint32_t destination = physical(s->es, s->di);
        write_physical(s, destination, (uint8_t)value);
        write_physical(s, destination + 1u, (uint8_t)(value >> 8));
        s->si = (uint16_t)(s->si + step);
        s->di = (uint16_t)(s->di + step);
        s->cx = (uint16_t)(s->cx - 1u);
    }
}

static void movs_bytes(MainResourcesState *s) {
    uint16_t step = (s->flags & DF) ? 0xffffu : 1u;
    while (s->cx) {
        uint8_t value = read8(s, s->ds, s->si);
        write_physical(s, physical(s->es, s->di), value);
        s->si = (uint16_t)(s->si + step);
        s->di = (uint16_t)(s->di + step);
        s->cx = (uint16_t)(s->cx - 1u);
    }
}

static LmnMainResourceSectionsResult result_of(const MainResourcesState *s) {
    LmnMainResourceSectionsResult out = {
        s->ax, s->bx, s->cx, s->dx, s->si, s->di, s->bp,
        s->cs, s->ds, s->es, s->ss, s->sp, s->flags,
        s->continuation, s->status, s->child_entry, s->child_status
    };
    return out;
}

static void stop_child(MainResourcesState *s, uint16_t entry,
                       uint16_t continuation, uint16_t status,
                       uint16_t child_status) {
    s->continuation = continuation;
    s->status = status;
    s->child_entry = entry;
    s->child_status = child_status;
}

static int consume_child_return(MainResourcesState *s, uint16_t expected,
                                uint16_t entry) {
    uint16_t target = pop16(s);
    if (target == expected) return 1;
#if MAIN_RESOURCES_MUTATION == 8
    /* Mutation: resume as though the top-level child returned as expected. */
    (void)entry;
    return 1;
#else
    stop_child(s, entry, target, LMN_MAIN_RESOURCE_SECTIONS_CHANGED_CHILD_RETURN,
               0u);
    return 0;
#endif
}

static LmnDatLoadSegments live_dat_segments(const MainResourcesState *s) {
    LmnDatLoadSegments segments = {
        raw_code_word(s, (uint16_t)(CS_CheckDatFile + 0x33u)),
        raw_code_word(s, (uint16_t)(CS_SelectCachedDatFile + 0x50u)),
        raw_code_word(s, (uint16_t)(CS_ReadDatBytes + 8u)),
        raw_code_word(s, (uint16_t)(CS_DatReadFailure + 1u))
    };
    return segments;
}

static LmnDatFileCall dat_call_state(const MainResourcesState *s) {
    LmnDatFileCall out = {s->ax, s->bx, s->cx, s->dx, s->si, s->di, s->bp,
        s->ds, s->es, s->ss, s->sp, s->flags};
    return out;
}

static void apply_dat_result(MainResourcesState *s,
                             const LmnDatFileResult *out) {
    s->ax = out->value; s->bx = out->handle; s->cx = out->count;
    s->dx = out->filename_offset; s->si = out->source_cursor;
    s->di = out->output_cursor; s->bp = out->base_cursor;
    s->ds = out->segment; s->es = out->extra_segment;
    s->sp = out->stack_offset; s->flags = out->flags;
}

static int call_dat(MainResourcesState *s, uint16_t entry, uint16_t ret,
                    unsigned is_loader, const LmnDatFileServices *files,
                    const LmnDatIo *io) {
    LmnDatLoadSegments segments;
    LmnDatFileCall call;
    LmnDatFileResult out;
    push16(s, ret);
    /* Re-read each relocated service-segment immediate at this CALL site. */
    segments = live_dat_segments(s);
    call = dat_call_state(s);
    out = is_loader ? lmn_dat_load_core(s->memory, &call, &segments, files, io) :
        lmn_dat_decode_preserving_segment_core(s->memory, &call, &segments, io);
    apply_dat_result(s, &out);
    if (out.fatal) {
        uint16_t transfer = out.fatal == 1u ? CS_DatFileErrorTransfer :
                                               CS_DatFatalTransfer;
        stop_child(s, entry, transfer, LMN_MAIN_RESOURCE_SECTIONS_FATAL,
                   out.fatal);
        return 0;
    }
    return consume_child_return(s, ret, entry);
}

static LmnEntitySpriteBanksCall entity_call_state(const MainResourcesState *s) {
    LmnEntitySpriteBanksCall out = {s->ax, s->bx, s->cx, s->dx, s->si, s->di,
        s->bp, s->cs, s->ds, s->es, s->ss, s->sp, s->flags};
    return out;
}

static void apply_entity_result(MainResourcesState *s,
                                const LmnEntitySpriteBanksResult *out) {
    s->ax = out->ax; s->bx = out->bx; s->cx = out->cx; s->dx = out->dx;
    s->si = out->si; s->di = out->di; s->bp = out->bp;
    s->cs = out->code_segment; s->ds = out->data_segment;
    s->es = out->extra_segment; s->ss = out->stack_segment;
    s->sp = out->stack_offset; s->flags = out->flags;
}

static int call_entity_banks(MainResourcesState *s,
                             const LmnRasterBus *raster) {
    const uint16_t ret = 0x58e8u;
    LmnEntitySpriteBanksCall call;
    LmnEntitySpriteBanksResult out;
    push16(s, ret);
    call = entity_call_state(s);
    out = lmn_generate_entity_sprite_banks_core(s->memory, &call, raster);
    apply_entity_result(s, &out);
    if (out.status != LMN_ENTITY_SPRITE_BANKS_READY) {
        uint16_t parent_status = out.status == LMN_ENTITY_SPRITE_BANKS_CHILD_STOP ?
            LMN_MAIN_RESOURCE_SECTIONS_CHILD_STOP :
            LMN_MAIN_RESOURCE_SECTIONS_CHANGED_CHILD_RETURN;
        stop_child(s, CS_GenerateEntitySpriteBanks, out.continuation,
                   parent_status, out.status);
        return 0;
    }
    return consume_child_return(s, ret, CS_GenerateEntitySpriteBanks);
}

static LmnFixedWordBanksCall fixed_call_state(const MainResourcesState *s) {
    LmnFixedWordBanksCall out = {s->ax, s->bx, s->cx, s->dx, s->si, s->di,
        s->bp, s->cs, s->ds, s->es, s->ss, s->sp, s->flags};
    return out;
}

static void apply_fixed_result(MainResourcesState *s,
                               const LmnFixedWordBanksResult *out) {
    s->ax = out->ax; s->bx = out->bx; s->cx = out->cx; s->dx = out->dx;
    s->si = out->si; s->di = out->di; s->bp = out->bp;
    s->cs = out->code_segment; s->ds = out->data_segment;
    s->es = out->extra_segment; s->ss = out->stack_segment;
    s->sp = out->stack_offset; s->flags = out->flags;
}

static int call_fixed_banks(MainResourcesState *s,
                            const LmnRasterBus *raster) {
    const uint16_t ret = 0x58ebu;
    LmnFixedWordBanksCall call;
    LmnFixedWordBanksResult out;
    push16(s, ret);
    call = fixed_call_state(s);
    out = lmn_generate_fixed_word_mask_banks_core(s->memory, &call, raster);
    apply_fixed_result(s, &out);
    if (out.status != LMN_FIXED_WORD_BANKS_READY) {
        stop_child(s, CS_GenerateFixedWordMaskBanks, out.continuation,
                   LMN_MAIN_RESOURCE_SECTIONS_CHANGED_CHILD_RETURN,
                   out.status);
        return 0;
    }
    return consume_child_return(s, ret, CS_GenerateFixedWordMaskBanks);
}

static int call_generated_graphics(MainResourcesState *s,
                                   const LmnRasterBus *raster) {
    const uint16_t ret = 0x5901u;
    LmnGeneratedGraphicsCall call;
    LmnGeneratedGraphicsResult out;
    push16(s, ret);
    call = (LmnGeneratedGraphicsCall){s->ds, s->ss, s->sp,
        s->bx, s->dx, s->flags};
    out = lmn_generate_graphics_mask_banks_core(s->memory, &call, raster);
    s->ax = out.value; s->bx = out.column_repetitions;
    s->cx = out.row_count; s->dx = out.shift_state;
    s->si = out.source_cursor; s->di = out.output_cursor;
    s->ds = out.source_segment; s->es = out.output_segment;
    s->sp = out.stack_offset; s->flags = out.flags;
    if (!out.ready_to_return) {
        stop_child(s, CS_GenerateGraphicsMaskBanks, out.continuation,
                   LMN_MAIN_RESOURCE_SECTIONS_CHANGED_CHILD_RETURN, 0u);
        return 0;
    }
    return consume_child_return(s, ret, CS_GenerateGraphicsMaskBanks);
}

static LmnCopyResourcePlanesVgaCall vga_call_state(const MainResourcesState *s) {
    LmnCopyResourcePlanesVgaCall out = {s->ax, s->bx, s->cx, s->dx, s->si,
        s->di, s->bp, s->cs, s->ds, s->es, s->ss, s->sp, s->flags};
    return out;
}

static void apply_vga_result(MainResourcesState *s,
                             const LmnCopyResourcePlanesVgaResult *out) {
    s->ax = out->ax; s->bx = out->bx; s->cx = out->cx; s->dx = out->dx;
    s->si = out->si; s->di = out->di; s->bp = out->bp;
    s->cs = out->code_segment; s->ds = out->data_segment;
    s->es = out->extra_segment; s->ss = out->stack_segment;
    s->sp = out->stack_offset; s->flags = out->flags;
}

static int call_vga_copy(MainResourcesState *s, uint16_t ret,
                         const LmnRasterBus *raster) {
    LmnCopyResourcePlanesVgaCall call;
    LmnCopyResourcePlanesVgaResult out;
    push16(s, ret);
    call = vga_call_state(s);
    out = lmn_copy_resource_planes_vga_core(s->memory, &call, raster);
    apply_vga_result(s, &out);
    if (out.status != LMN_COPY_RESOURCE_PLANES_VGA_READY) {
        stop_child(s, CS_CopyResourcePlanesToVga, out.continuation,
                   LMN_MAIN_RESOURCE_SECTIONS_CHANGED_CHILD_RETURN,
                   out.status);
        return 0;
    }
    return consume_child_return(s, ret, CS_CopyResourcePlanesToVga);
}

static void load_segment_into_es(MainResourcesState *s, uint16_t selector) {
    s->es = read16(s, s->ds, selector);
}

static void load_segment_into_ds(MainResourcesState *s, uint16_t selector) {
    uint16_t value = read16(s, s->ds, selector);
    s->ds = value;
}

LmnMainResourceSectionsResult lmn_load_main_resource_sections_core(
    uint8_t *memory, const LmnMainResourceSectionsCall *call,
    const LmnDatFileServices *files, const LmnDatIo *io,
    const LmnRasterBus *raster) {
    MainResourcesState s = {memory, raster,
        call->ax, call->bx, call->cx, call->dx, call->si, call->di, call->bp,
        call->code_segment, call->data_segment, call->extra_segment,
        call->stack_segment, call->stack_offset, call->flags,
        0u, LMN_MAIN_RESOURCE_SECTIONS_READY, 0u, 0u};
#if MAIN_RESOURCES_MUTATION == 1
    uint16_t initial_ds = s.ds;
#endif
#if MAIN_RESOURCES_MUTATION == 2
    uint16_t saved_bx_before_graphics;
#endif
    uint8_t configuration;

    /* 58D2: PUSH DS; prepare and load section zero. */
    push16(&s, s.ds);
    s.dx = 0x252bu;
    load_segment_into_es(&s, SEG09A9_GraphicsResourceSegment);
    s.di = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.si = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.cx = s.es;
    if (!call_dat(&s, CS_LoadDatResource, 0x58e3u, 1u, files, io))
        return result_of(&s);
    {
        uint16_t restored = pop16(&s);
#if MAIN_RESOURCES_MUTATION == 1
        (void)restored;
        s.ds = initial_ds;
#else
        s.ds = restored;
#endif
    }

    /* 58E4..58EB: the two initial bank builders share a live BX save. */
    push16(&s, s.bx);
    if (!call_entity_banks(&s, raster)) return result_of(&s);
    if (!call_fixed_banks(&s, raster)) return result_of(&s);
    s.bx = pop16(&s);

    /* Section one, then the generated mask-bank child. */
    push16(&s, s.ds);
    s.di = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.si = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    load_segment_into_es(&s, SEG09A9_GraphicsResourceSegment);
    load_segment_into_ds(&s, SEG09A9_GraphicsResourceSegment);
    if (!call_dat(&s, CS_DecodeDatPreservingSegment, 0x58fcu, 0u,
                  files, io)) return result_of(&s);
    s.ds = pop16(&s);

    /* 58FD PUSH BX; 58FE CALL GenerateGraphicsMaskBanks; 5901 POP BX. */
    push16(&s, s.bx);
#if MAIN_RESOURCES_MUTATION == 2
    saved_bx_before_graphics = s.bx;
#endif
    if (!call_generated_graphics(&s, raster)) return result_of(&s);
#if MAIN_RESOURCES_MUTATION == 2
    (void)pop16(&s);
    s.bx = saved_bx_before_graphics;
#else
    s.bx = pop16(&s);
#endif

    /* Section two is decoded after the graphics child returns. */
    push16(&s, s.ds);
    s.di = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.si = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    load_segment_into_es(&s, SEG09A9_GraphicsResourceSegment);
    load_segment_into_ds(&s, SEG09A9_GraphicsResourceSegment);
    if (!call_dat(&s, CS_DecodeDatPreservingSegment, 0x5912u, 0u,
                  files, io)) return result_of(&s);
    s.ds = pop16(&s);

    /* 5913 PUSH BX; 5914 PUSH DS; four VGA planes; then glyph word copy. */
    push16(&s, s.bx);
    push16(&s, s.ds);
    s.di = 0xf91fu;
    s.si = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.cx = 0x28u; s.ax = 0x2cu; s.bx = 0x0428u;
    load_segment_into_ds(&s, SEG09A9_GraphicsResourceSegment);
    if (!call_vga_copy(&s, 0x592au, raster)) return result_of(&s);
    s.ds = pop16(&s);

    push16(&s, s.ds);
    s.si = 0x1900u;
    s.di = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    load_segment_into_es(&s, SEG09A9_StatusGlyphBufferSegment);
    load_segment_into_ds(&s, SEG09A9_GraphicsResourceSegment);
    s.cx = 0x03e0u;
#if MAIN_RESOURCES_MUTATION == 3
    s.cx = 0x03dfu;
#endif
    movs_words(&s);
    s.ds = pop16(&s);
    s.bx = pop16(&s);

    /* Section three. */
    push16(&s, s.ds);
    s.di = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.si = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    load_segment_into_es(&s, SEG09A9_UiGraphicsBufferSegment);
    load_segment_into_ds(&s, SEG09A9_UiGraphicsBufferSegment);
    if (!call_dat(&s, CS_DecodeDatPreservingSegment, 0x5950u, 0u,
                  files, io)) return result_of(&s);
    s.ds = pop16(&s);

    /* Section four uses the word-sized paragraph addition and live selector. */
    push16(&s, s.ds);
    s.ax = read16(&s, s.ds, SEG09A9_UiGraphicsBufferSegment);
#if MAIN_RESOURCES_MUTATION == 6
    s.flags = add16_flags(s.flags, s.ax, 0x0f20u);
    s.ax = (uint16_t)(s.ax + 0x0f20u);
#else
    s.flags = add16_flags(s.flags, s.ax, 0x0f21u);
    s.ax = (uint16_t)(s.ax + 0x0f21u);
#endif
    s.es = s.ax; s.ds = s.ax;
    s.di = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.si = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    if (!call_dat(&s, CS_DecodeDatPreservingSegment, 0x5963u, 0u,
                  files, io)) return result_of(&s);
    s.ds = pop16(&s);

    /* 5964/5965 are real SS traffic despite restoring the same BX. */
#if MAIN_RESOURCES_MUTATION == 5
    /* Mutation: omit this no-op pair. */
#else
    push16(&s, s.bx);
    s.bx = pop16(&s);
#endif

    /* Section five's segment is a relocated, mutable immediate in code. */
    push16(&s, s.ds);
    s.ax = raw_code_word(&s, CS_MainResourceSoundSegmentOperand5968);
    s.es = s.ax; s.ds = s.ax;
    s.di = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.si = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    if (!call_dat(&s, CS_DecodeDatPreservingSegment, 0x5975u, 0u,
                  files, io)) return result_of(&s);
    s.ds = pop16(&s);

    /* 5976 CMP byte [DS:200E],FFh; JNZ skips the optional final section. */
    configuration = read8(&s, s.ds, SEG09A9_ConfigurationOption200E);
    s.flags = sub8_flags(s.flags, configuration, 0xffu);
#if MAIN_RESOURCES_MUTATION == 7
    if (configuration == 0u) {
#else
    if (configuration != 0xffu) {
#endif
        s.continuation = CS_MainResourceSectionsReturn;
        s.status = LMN_MAIN_RESOURCE_SECTIONS_READY;
        return result_of(&s);
    }

    /* Section six, its VGA plane copy, then byte glyph copy at 59A5..59B9. */
    push16(&s, s.ds);
    load_segment_into_es(&s, SEG09A9_GraphicsResourceSegment);
    load_segment_into_ds(&s, SEG09A9_GraphicsResourceSegment);
    s.di = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.si = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    if (!call_dat(&s, CS_DecodeDatPreservingSegment, 0x598du, 0u,
                  files, io)) return result_of(&s);
    s.ds = pop16(&s);

    push16(&s, s.ds);
    s.di = 0xf91fu;
    s.si = 0u; s.flags = logic_flags(s.flags, 0u, 16u);
    s.cx = 0x28u; s.ax = 0x2cu; s.bx = 0x0428u;
    load_segment_into_ds(&s, SEG09A9_GraphicsResourceSegment);
    if (!call_vga_copy(&s, 0x59a4u, raster)) return result_of(&s);
    s.ds = pop16(&s);

    push16(&s, s.ds);
    s.di = 0x00a0u;
#if MAIN_RESOURCES_MUTATION == 4
    s.si = 0x1901u;
#else
    s.si = 0x1900u;
#endif
    load_segment_into_es(&s, SEG09A9_StatusGlyphBufferSegment);
    load_segment_into_ds(&s, SEG09A9_GraphicsResourceSegment);
    s.cx = 0x0720u;
    movs_bytes(&s);
    s.ds = pop16(&s);

    s.continuation = CS_MainResourceSectionsReturn;
    s.status = LMN_MAIN_RESOURCE_SECTIONS_READY;
    return result_of(&s);
}

static LmnMainResourceSectionsCall call_from_regs(const LmnRegs *r) {
    LmnMainResourceSectionsCall out = {r->ax, r->bx, r->cx, r->dx, r->si,
        r->di, r->bp, r->cs, r->ds, r->es, r->ss, r->sp, r->flags};
    return out;
}

static void apply_result(const LmnMainResourceSectionsResult *out,
                         LmnRegs *r) {
    r->ax = out->ax; r->bx = out->bx; r->cx = out->cx; r->dx = out->dx;
    r->si = out->si; r->di = out->di; r->bp = out->bp;
    r->cs = out->code_segment; r->ds = out->data_segment;
    r->es = out->extra_segment; r->ss = out->stack_segment;
    r->sp = out->stack_offset; r->flags = out->flags;
    r->ip = out->continuation;
}

#if MAIN_RESOURCES_MUTATION != 10
static uint16_t read_outer_return(uint8_t *memory, const LmnRegs *r,
                                  const LmnRasterBus *raster) {
    MainResourcesState s = {memory, raster, 0u, 0u, 0u, 0u, 0u, 0u, 0u,
        r->cs, r->ds, r->es, r->ss, r->sp, r->flags, 0u, 0u, 0u, 0u};
    return read16(&s, r->ss, r->sp);
}
#endif

uint16_t lmn_load_main_resource_sections_adapter(
    uint8_t *memory, LmnRegs *registers,
    const LmnDatFileServices *files, const LmnDatIo *io,
    const LmnRasterBus *raster) {
    LmnMainResourceSectionsCall call = call_from_regs(registers);
    LmnMainResourceSectionsResult out;
#if MAIN_RESOURCES_MUTATION == 9
    uint16_t prefetched_outer_return =
        read_outer_return(memory, registers, raster);
#endif
    out = lmn_load_main_resource_sections_core(memory, &call, files, io, raster);
    apply_result(&out, registers);
    if (out.status == LMN_MAIN_RESOURCE_SECTIONS_READY) {
#if MAIN_RESOURCES_MUTATION == 10
        /* Mutation: stop before consuming the caller's live RET word. */
#else
#if MAIN_RESOURCES_MUTATION == 9
        registers->ip = prefetched_outer_return;
#else
        registers->ip = read_outer_return(memory, registers, raster);
#endif
        registers->sp = (uint16_t)(out.stack_offset + 2u);
#endif
    }
    return out.status;
}

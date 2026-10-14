#include "aligned_read_mask.h"
#include "lemmings_sym.h"

#ifndef READ_MASK_MUTATION
#define READ_MASK_MUTATION 0
#endif

enum { CF=0x001, PF=0x004, AF=0x010, ZF=0x040, SF=0x080,
       IF=0x200, DF=0x400, OF=0x800, ARITH=0x8d5 };

typedef struct ReadMaskState {
    uint8_t *mem;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp,sp,ds,es,ss,flags;
    uint16_t game_ds;
} ReadMaskState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+(uint32_t)offset)&0xfffffu;
}

static uint8_t read_byte(ReadMaskState *s,uint32_t address) {
    address&=0xfffffu;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->mem,address,s->flags);
    return s->mem[address];
}

static void write_byte(ReadMaskState *s,uint32_t address,uint8_t value) {
    address&=0xfffffu;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->mem,address,value,s->flags);
    else
        s->mem[address]=value;
}

static uint8_t read8(ReadMaskState *s,uint16_t segment,uint16_t offset) {
    return read_byte(s,physical(segment,offset));
}

static uint16_t read16(ReadMaskState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(s,address);
    uint8_t high=read_byte(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ReadMaskState *s,uint16_t segment,uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_byte(s,address,(uint8_t)value);
    write_byte(s,address+1u,(uint8_t)(value>>8));
}

static void push(ReadMaskState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop(ReadMaskState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static uint16_t szp(uint16_t value,unsigned width) {
    uint16_t result=0;
    uint8_t low=(uint8_t)value;
    unsigned parity=0;
    unsigned bit;
    for(bit=0;bit<8;++bit) parity^=(low>>bit)&1u;
    if(!parity) result|=PF;
    if(width==8 ? (uint8_t)value==0 : value==0) result|=ZF;
    if(width==8 ? (value&0x80u)!=0 : (value&0x8000u)!=0) result|=SF;
    return result;
}

static void logical_flags(ReadMaskState *s,uint16_t value,unsigned width) {
    /* AF is undefined for XOR in the original instruction. Keep its current
       bit while replacing the other defined logical-result flags. */
    s->flags=(uint16_t)((s->flags&(uint16_t)~(CF|PF|ZF|SF|OF))|
        szp(value,width));
}

static void add_flags(ReadMaskState *s,uint16_t left,uint16_t right) {
    uint32_t sum=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)sum;
    s->flags=(uint16_t)((s->flags&(uint16_t)~ARITH)|szp(value,16)|
        (sum>0xffffu?CF:0u)|((left^right^value)&AF)|
        (((uint16_t)~(left^right)&(left^value)&0x8000u)?OF:0u));
}

static uint16_t inc16(ReadMaskState *s,uint16_t before) {
    uint16_t value=(uint16_t)(before+1u);
    uint16_t changed=(uint16_t)(szp(value,16)|
        ((before&0x0fu)==0x0fu?AF:0u)|(before==0x7fffu?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static uint8_t dec8(ReadMaskState *s,uint8_t before) {
    uint8_t value=(uint8_t)(before-1u);
    uint16_t changed=(uint16_t)(szp(value,8)|
        ((before&0x0fu)==0?AF:0u)|(before==0x80u?OF:0u));
    s->flags=(uint16_t)((s->flags&(uint16_t)~(PF|AF|ZF|SF|OF))|changed);
    return value;
}

static void output(ReadMaskState *s,uint16_t mirror,uint16_t value) {
    write16(s,s->ss,mirror,value);
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,value,s->flags);
}

static void compare_mode_byte(ReadMaskState *s, uint8_t value) {
    uint8_t result = (uint8_t)(value - 8u);
    s->flags = (uint16_t)((s->flags & (uint16_t)~ARITH) | szp(result, 8) |
        (value < 8u ? CF : 0u) | ((value ^ 8u ^ result) & AF) |
        (((value ^ 8u) & (value ^ result) & 0x80u) ? OF : 0u));
}

LmnAlignedReadMaskResult lmn_draw_aligned_read_mask_core(uint8_t *memory,
    const LmnAlignedReadMaskCall *call, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    ReadMaskState s = {memory, bus, 0, call->mask_cursor, call->packed_counts,
        call->width_state, call->source_cursor, call->destination_cursor, 0,
        call->stack_offset, 0, 0, call->stack_segment, call->flags,
        call->game_data_segment};
    push(&s, call->initial_data_segment);
    s.ds = read16(&s, call->initial_data_segment, SEG09A9_GraphicsResourceSegment);
    s.ax = 0xa000u; s.es = s.ax;
    s.dx = (uint16_t)(s.dx >> 8); /* XCHG DL,DH / XOR DH,DH. */
    logical_flags(&s, 0, 8); s.bp = s.dx;
    s.dx = 0x03c4u; s.ax = 0x0f02u;
    output(&s, SEG143E_VgaMapMaskMirror, s.ax);
    s.dx = 0x03ceu; s.ax = 0x0400u;
    output(&s, SEG143E_VgaSetResetMirror, s.ax);
    s.ax = 0x0e01u; output(&s, SEG143E_VgaEnableSetResetMirror, s.ax);
    s.ax = 0x0003u; output(&s, SEG143E_VgaDataRotateMirror, s.ax);
    s.ax = 0x0805u; output(&s, SEG143E_VgaGraphicsModeMirror, s.ax);
    s.ax = 0x0802u; output(&s, SEG143E_VgaColorCompareMirror, s.ax);
    s.ax = 0x0807u; output(&s, SEG143E_VgaColorCareMirror, s.ax);
    s.ax = 0x0804u; output(&s, SEG143E_VgaReadMapMirror, s.ax);
    push(&s, s.cx); push(&s, s.si); push(&s, s.di); push(&s, s.bx);
    for (;;) {
        uint8_t rows;
        push(&s, s.cx);
        s.flags = (uint16_t)(s.flags & (uint16_t)~IF);
        push(&s, s.dx);
        s.ax = (uint16_t)((s.ax & 0xff00u) | 5u);
        ports->out_byte(ports->context, memory, s.dx, (uint8_t)s.ax, s.flags);
        s.dx = inc16(&s, s.dx);
        s.ax = (uint16_t)((s.ax & 0xff00u) |
            ports->in_byte(ports->context, memory, s.dx, s.flags));
        compare_mode_byte(&s, (uint8_t)s.ax);
        /* JZ skips only the known NOP9702; neither path changes state. */
        s.dx = pop(&s); /* Byte-port providers can change this live word. */
        s.cx &= 0x00ffu; logical_flags(&s, 0, 8);
        do {
            uint8_t destination;
            uint8_t mask;
            uint16_t step = (s.flags & DF) ? 0xffffu : 1u;
#if READ_MASK_MUTATION == 1
            destination = (uint8_t)(s.ax >> 8);
#else
            destination = read8(&s, s.es, s.di);
#endif
            s.ax = (uint16_t)((s.ax & 0x00ffu) | ((uint16_t)destination << 8));
            mask = read8(&s, s.ds, s.bx);
#if READ_MASK_MUTATION == 2
            mask = (uint8_t)(mask | destination);
#else
            mask = (uint8_t)(mask & destination);
#endif
            s.ax = (uint16_t)(((uint16_t)mask << 8) | (s.ax & 0xffu));
            logical_flags(&s, mask, 8); /* AND AH,[BX]. NOP970B/970C follow. */
            s.ax = (uint16_t)((s.ax & 0xff00u) | 8u);
            output(&s, SEG143E_VgaBitMaskMirror, s.ax);
            {
                uint8_t source = read8(&s, s.ds, s.si);
                write_byte(&s, physical(s.es, s.di), source); /* MOVSB keeps AX. */
            }
            s.si = (uint16_t)(s.si + step);
            s.di = (uint16_t)(s.di + step);
            s.bx = inc16(&s, s.bx);
            s.cx = (uint16_t)(s.cx - 1u);
        } while (s.cx != 0);
        s.flags = (uint16_t)(s.flags | IF);
        push(&s, s.ds); s.ax = s.game_ds; s.ds = s.ax;
        {
            uint16_t before = s.bx;
            uint16_t advance = read16(&s, s.ds, SEG09A9_DrawingSourceRowAdvance);
            s.bx = (uint16_t)(before + advance); add_flags(&s, before, advance);
        }
        {
            uint16_t before = s.si;
            uint16_t advance = read16(&s, s.ds, SEG09A9_DrawingSourceRowAdvance);
            s.si = (uint16_t)(before + advance); add_flags(&s, before, advance);
        }
        {
            uint16_t before = s.di;
            uint16_t advance = read16(&s, s.ds, SEG09A9_DrawingActiveDestinationRowAdvance);
            s.di = (uint16_t)(before + advance); add_flags(&s, before, advance);
        }
#if READ_MASK_MUTATION == 3
        (void)pop(&s);
#else
        s.ds = pop(&s);
#endif
        s.cx = pop(&s); rows = dec8(&s, (uint8_t)(s.cx >> 8));
        s.cx = (uint16_t)((s.cx & 0xffu) | ((uint16_t)rows << 8));
        if (rows == 0) break;
    }
    s.bx = pop(&s); s.di = pop(&s); s.si = pop(&s); s.cx = pop(&s);
    s.ds = pop(&s);
    {
        LmnAlignedReadMaskResult result = {s.ax, s.cx, s.dx, s.si, s.bx, s.di,
            s.bp, s.sp, s.ds, s.es, s.flags};
        return result;
    }
}

void lmn_draw_aligned_read_mask_adapter(uint8_t *memory, LmnRegs *regs,
    uint16_t game_data_segment, const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    LmnAlignedReadMaskCall call = {regs->ds, game_data_segment, regs->ss, regs->sp,
        regs->cx, regs->dx, regs->si, regs->bx, regs->di, regs->flags};
    LmnAlignedReadMaskResult result =
        lmn_draw_aligned_read_mask_core(memory, &call, bus, ports);
    ReadMaskState s = {memory, bus, result.work_value, result.mask_cursor,
        result.packed_counts, result.port, result.source_cursor, result.destination_cursor,
        result.plane_counter, result.stack_offset, result.source_segment,
        result.output_segment, regs->ss, result.flags, game_data_segment};
    uint16_t ip = read16(&s, s.ss, s.sp);
    s.sp = (uint16_t)(s.sp + 2u); regs->ip = ip;
    regs->cs = read16(&s, s.ss, s.sp); s.sp = (uint16_t)(s.sp + 2u);
    regs->ax = result.work_value; regs->bx = result.mask_cursor;
    regs->cx = result.packed_counts; regs->dx = result.port;
    regs->si = result.source_cursor; regs->di = result.destination_cursor;
    regs->bp = result.plane_counter; regs->sp = s.sp;
    regs->ds = result.source_segment; regs->es = result.output_segment;
    regs->flags = result.flags;
}

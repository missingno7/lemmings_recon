#include "drawing_clip.h"
#include "lemmings_sym.h"

#ifndef CLIP_MUTATION
#define CLIP_MUTATION 0
#endif

enum { CF=0x0001, PF=0x0004, AF=0x0010, ZF=0x0040, SF=0x0080,
       IF=0x0200, DF=0x0400, OF=0x0800 };

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

static void write_byte(uint8_t *memory, const LmnRasterBus *bus,
                       uint32_t address, uint8_t value, uint16_t flags) {
    address &= 0xfffffu;
    if (bus && bus->write_byte)
        bus->write_byte(bus->context, memory, address, value, flags);
    else
        memory[address]=value;
}

static uint16_t read_word(uint8_t *memory, const LmnRasterBus *bus,
                          uint16_t segment, uint16_t offset, uint16_t flags) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_byte(memory,bus,address,flags);
    uint8_t high=read_byte(memory,bus,(address+1u)&0xfffffu,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_word(uint8_t *memory, const LmnRasterBus *bus,
                       uint16_t segment, uint16_t offset, uint16_t value,
                       uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_byte(memory,bus,address,(uint8_t)value,flags);
    write_byte(memory,bus,(address+1u)&0xfffffu,(uint8_t)(value>>8),flags);
}

static uint16_t read_word_address(uint8_t *memory, const LmnRasterBus *bus,
                                  uint32_t address, uint16_t flags) {
    uint8_t low=read_byte(memory,bus,address,flags);
    uint8_t high=read_byte(memory,bus,(address+1u)&0xfffffu,flags);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static unsigned even_parity8(uint8_t value) {
    unsigned parity=0;
    for (unsigned bit=0;bit<8;++bit) parity^=(value>>bit)&1u;
    return parity==0u;
}

static uint16_t arithmetic_flags(uint16_t old_flags, uint16_t a,
                                 uint16_t b, uint16_t result,
                                 unsigned subtract) {
    uint16_t set=0;
    uint32_t full;
    if (subtract) {
        if (a<b) set|=CF;
        if (((a^b^result)&0x10u)!=0u) set|=AF;
        if ((((a^b)&(a^result))&0x8000u)!=0u) set|=OF;
    } else {
        full=(uint32_t)a+(uint32_t)b;
        if (full>0xffffu) set|=CF;
        if (((a&0x0fu)+(b&0x0fu))>0x0fu) set|=AF;
        if (((~(a^b)&(a^result))&0x8000u)!=0u) set|=OF;
    }
    if (even_parity8((uint8_t)result)) set|=PF;
    if (result==0u) set|=ZF;
    if (result&0x8000u) set|=SF;
    return (uint16_t)((old_flags&~(CF|PF|AF|ZF|SF|OF))|set);
}

/* TEST, AND and XOR define CF/PF/ZF/SF/OF. AF is intentionally retained as
   one representative because the processor leaves it undefined. */
static uint16_t logic_flags(uint16_t old_flags, uint16_t result) {
    uint16_t set=0;
    if (even_parity8((uint8_t)result)) set|=PF;
    if (result==0u) set|=ZF;
    if (result&0x8000u) set|=SF;
    return (uint16_t)((old_flags&~(CF|PF|ZF|SF|OF))|set);
}

static void push_word(uint8_t *memory, const LmnRasterBus *bus,
                      const LmnDrawingClipCall *call,
                      LmnDrawingClipResult *state, uint16_t value) {
    state->stack_offset=(uint16_t)(state->stack_offset-2u);
    write_word(memory,bus,call->stack_segment,state->stack_offset,value,
               state->flags);
}

static uint16_t pop_word(uint8_t *memory, const LmnRasterBus *bus,
                         const LmnDrawingClipCall *call,
                         LmnDrawingClipResult *state) {
    uint16_t value=read_word(memory,bus,call->stack_segment,
                             state->stack_offset,state->flags);
    state->stack_offset=(uint16_t)(state->stack_offset+2u);
    return value;
}

static uint8_t read_saved_height(uint8_t *memory, const LmnRasterBus *bus,
                                 const LmnDrawingClipCall *call,
                                 LmnDrawingClipResult *state) {
    return read_byte(memory,bus,
        physical(call->data_segment,SEG09A9_DrawingSavedHeightHighByte),
        state->flags);
}

static void restore_height_high_byte(uint8_t *memory,
                                     const LmnRasterBus *bus,
                                     const LmnDrawingClipCall *call,
                                     LmnDrawingClipResult *state) {
    uint8_t saved=read_saved_height(memory,bus,call,state);
    state->packed_height=(uint16_t)((state->packed_height&0x00ffu)|
                                    ((uint16_t)saved<<8));
}

static void return_body(uint8_t *memory, const LmnRasterBus *bus,
                        const LmnDrawingClipCall *call,
                        LmnDrawingClipResult *state, unsigned rejected) {
    if (rejected) state->left=0xffffu;
    restore_height_high_byte(memory,bus,call,state);
    state->control=pop_word(memory,bus,call,state);
}

LmnDrawingClipResult lmn_clip_planar_drawing_rectangle_core(uint8_t *memory,
    const LmnDrawingClipCall *call, const LmnRasterBus *bus) {
    LmnDrawingClipResult state={
        call->left,call->top,call->packed_height,call->width,
        call->source_cursor,call->destination_cursor,call->control,
        call->stack_offset,call->flags
    };
    uint16_t saved_height_high=(uint16_t)(state.packed_height>>8);

    /* PUSH BP precedes the saved-CH store. Both can alias DS fields. */
    push_word(memory,bus,call,&state,state.control);
    write_byte(memory,bus,
        physical(call->data_segment,SEG09A9_DrawingSavedHeightHighByte),
        (uint8_t)saved_height_high,state.flags);
    state.packed_height&=0x00ffu;
    state.flags=logic_flags(state.flags,0u); /* XOR CH,CH */

    /* TEST BP,4; JZ 99B4. */
    state.flags=logic_flags(state.flags,(uint16_t)(state.control&4u));
    if (!(state.flags&ZF)) {
        state.control=state.left;
        state.flags=logic_flags(state.flags,state.control); /* AND BP,BP */
        if (state.flags&SF) {
            uint16_t sum=(uint16_t)(state.control+state.width);
            state.flags=arithmetic_flags(state.flags,state.control,state.width,
                                         sum,0);
            if (state.flags&SF) goto reject;
            for (;;) {
                state.source_cursor=(uint16_t)(state.source_cursor+1u);
                state.flags=arithmetic_flags(state.flags,
                    (uint16_t)(state.source_cursor-1u),1u,
                    state.source_cursor,0);
                state.destination_cursor=(uint16_t)(state.destination_cursor+1u);
                state.flags=arithmetic_flags(state.flags,
                    (uint16_t)(state.destination_cursor-1u),1u,
                    state.destination_cursor,0);
                {
                    uint16_t access_flags=state.flags;
                    uint16_t old=read_word(memory,bus,call->data_segment,
                        SEG09A9_DrawingHorizontalSkipBytes,state.flags);
                    uint16_t next=(uint16_t)(old+1u);
                    state.flags=arithmetic_flags(state.flags,old,1u,next,0);
                    write_word(memory,bus,call->data_segment,
                        SEG09A9_DrawingHorizontalSkipBytes,next,access_flags);
                }
#if CLIP_MUTATION == 3
                {
                    uint16_t old_width=state.width;
                state.width=(uint16_t)(state.width-7u);
                    state.flags=arithmetic_flags(state.flags,old_width,7u,
                                                 state.width,1);
                }
#else
                {
                    uint16_t old_width=state.width;
                state.width=(uint16_t)(state.width-8u);
                    state.flags=arithmetic_flags(state.flags,old_width,8u,
                                                 state.width,1);
                }
#endif
                state.left=(uint16_t)(state.left+8u);
                state.flags=arithmetic_flags(state.flags,
                    (uint16_t)(state.left-8u),8u,state.left,0);
                if (!(state.flags&SF)) break;
            }
        } else {
            uint16_t width_pixels=read_word(memory,bus,call->data_segment,
                SEG09A9_DrawingWidthPixels,state.flags);
            uint16_t compare=(uint16_t)(state.left-width_pixels);
            state.flags=arithmetic_flags(state.flags,state.left,width_pixels,
                                         compare,1);
#if CLIP_MUTATION == 1
            if (!(state.flags&CF)) goto reject;
#else
            if (!!(state.flags&SF)==!!(state.flags&OF)) goto reject;
#endif
            state.control=state.left;
            state.control=(uint16_t)(state.control+state.width);
            state.flags=arithmetic_flags(state.flags,state.left,state.width,
                                         state.control,0);
            for (;;) {
                width_pixels=read_word(memory,bus,call->data_segment,
                    SEG09A9_DrawingWidthPixels,state.flags);
                compare=(uint16_t)(state.control-width_pixels);
                state.flags=arithmetic_flags(state.flags,state.control,
                                             width_pixels,compare,1);
                if (!!(state.flags&SF)!=!!(state.flags&OF)) break;
                {
                    uint16_t access_flags=state.flags;
                    uint16_t old=read_word(memory,bus,call->data_segment,
                        SEG09A9_DrawingHorizontalSkipBytes,state.flags);
                    uint16_t next=(uint16_t)(old+1u);
                    state.flags=arithmetic_flags(state.flags,old,1u,next,0);
                    write_word(memory,bus,call->data_segment,
                        SEG09A9_DrawingHorizontalSkipBytes,next,access_flags);
                }
#if CLIP_MUTATION == 3
                state.width=(uint16_t)(state.width-7u);
                state.flags=arithmetic_flags(state.flags,
                    (uint16_t)(state.width+7u),7u,state.width,1);
#else
                state.width=(uint16_t)(state.width-8u);
                state.flags=arithmetic_flags(state.flags,
                    (uint16_t)(state.width+8u),8u,state.width,1);
#endif
                state.control=(uint16_t)(state.control-8u);
                state.flags=arithmetic_flags(state.flags,
                    (uint16_t)(state.control+8u),8u,state.control,1);
            }
        }
    }

    /* POP BP / PUSH BP is deliberately live: DS clipping writes can alter it. */
    state.control=pop_word(memory,bus,call,&state);
    push_word(memory,bus,call,&state,state.control);
    state.flags=logic_flags(state.flags,(uint16_t)(state.control&8u));
    if (state.flags&ZF) goto success_restore;

    state.control=state.top;
    state.flags=logic_flags(state.flags,state.control); /* AND BP,BP */
    if (!(state.flags&SF)) goto nonnegative_top;
    {
        uint16_t sum=(uint16_t)(state.control+state.packed_height);
        state.flags=arithmetic_flags(state.flags,state.control,
                                     state.packed_height,sum,0);
        if (state.flags&SF) goto reject;
    }
    state.packed_height=(uint16_t)(state.packed_height+state.top);
    state.flags=arithmetic_flags(state.flags,
        (uint16_t)(state.packed_height-state.top),state.top,
        state.packed_height,0);
    state.top=(uint16_t)(0u-state.top);
    state.flags=arithmetic_flags(state.flags,0u,(uint16_t)(0u-state.top),
                                 state.top,1); /* NEG BX */
    state.control=read_word(memory,bus,call->data_segment,
        SEG09A9_DrawingSourcePitchBytes,state.flags);
    push_word(memory,bus,call,&state,state.left);
    push_word(memory,bus,call,&state,state.width);
    {
        uint32_t product=(uint32_t)state.top*(uint32_t)state.control;
        uint16_t product_low=(uint16_t)product;
        uint16_t product_high=(uint16_t)(product>>16);
        state.flags=(uint16_t)((state.flags&~(CF|OF))|
                               (product_high?(CF|OF):0u));
        state.control=product_low;
    }
    state.width=pop_word(memory,bus,call,&state);
    state.left=pop_word(memory,bus,call,&state);
    state.source_cursor=(uint16_t)(state.source_cursor+state.control);
    state.flags=arithmetic_flags(state.flags,
        (uint16_t)(state.source_cursor-state.control),state.control,
        state.source_cursor,0);
    state.destination_cursor=(uint16_t)(state.destination_cursor+state.control);
    state.flags=arithmetic_flags(state.flags,
        (uint16_t)(state.destination_cursor-state.control),state.control,
        state.destination_cursor,0);
    write_word(memory,bus,call->data_segment,
        SEG09A9_DrawingVerticalSkipBytes,state.control,state.flags);
    state.top=0;
    state.flags=logic_flags(state.flags,0u); /* XOR BX,BX */
    goto success_restore;

nonnegative_top:
    {
        uint16_t height=read_word(memory,bus,call->data_segment,
            SEG09A9_DrawingHeight,state.flags);
        uint16_t compare=(uint16_t)(state.top-height);
        state.flags=arithmetic_flags(state.flags,state.top,height,compare,1);
#if CLIP_MUTATION == 2
        if (!(state.flags&CF)) goto reject;
#else
        if (!!(state.flags&SF)==!!(state.flags&OF)) goto reject;
#endif
        state.control=state.top;
        state.control=(uint16_t)(state.control+state.packed_height);
        state.flags=arithmetic_flags(state.flags,state.top,state.packed_height,
                                     state.control,0);
        height=read_word(memory,bus,call->data_segment,
            SEG09A9_DrawingHeight,state.flags);
        compare=(uint16_t)(state.control-height);
        state.flags=arithmetic_flags(state.flags,state.control,height,compare,1);
        if (!!(state.flags&SF)!=!!(state.flags&OF)) goto nonnegative_zero_check;
        height=read_word(memory,bus,call->data_segment,
            SEG09A9_DrawingHeight,state.flags);
        state.packed_height=height;
        state.packed_height=(uint16_t)(state.packed_height-state.top);
        state.flags=arithmetic_flags(state.flags,height,state.top,
                                     state.packed_height,1);
    }

nonnegative_zero_check:
    state.flags=logic_flags(state.flags,state.width); /* AND DX,DX */
    if (state.flags&ZF) goto reject;
    state.flags=logic_flags(state.flags,state.packed_height); /* AND CX,CX */
    if (state.flags&ZF) goto reject;
    goto success_restore;

success_restore:
    restore_height_high_byte(memory,bus,call,&state);
    state.control=pop_word(memory,bus,call,&state);
    return state;

reject:
    return_body(memory,bus,call,&state,1u);
    return state;
}

void lmn_clip_planar_drawing_rectangle_adapter(uint8_t *memory,
    LmnRegs *regs, const LmnRasterBus *bus) {
    LmnDrawingClipCall call={regs->ds,regs->ss,regs->sp,
        regs->ax,regs->bx,regs->cx,regs->dx,
        regs->si,regs->di,regs->bp,regs->flags};
    LmnDrawingClipResult result=
        lmn_clip_planar_drawing_rectangle_core(memory,&call,bus);
    uint16_t ip;

    regs->ax=result.left;
    regs->bx=result.top;
    regs->cx=result.packed_height;
    regs->dx=result.width;
    regs->si=result.source_cursor;
    regs->di=result.destination_cursor;
    regs->bp=result.control;
    regs->sp=result.stack_offset;
    regs->flags=result.flags;
    ip=read_word_address(memory,bus,physical(regs->ss,regs->sp),regs->flags);
    regs->ip=ip;
    regs->sp=(uint16_t)(regs->sp+2u);
}

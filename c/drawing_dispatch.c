#include "drawing_dispatch.h"
#include "lemmings_sym.h"

#ifndef DISPATCH_MUTATION
#define DISPATCH_MUTATION 0
#endif

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}

static uint8_t read_byte(uint8_t *m,uint32_t address,uint16_t flags,const LmnRasterBus *bus) {
    address&=0xfffffu;
    return bus&&bus->read_byte?bus->read_byte(bus->context,m,address,flags):m[address];
}

static uint16_t read_word(uint8_t *m,uint16_t segment,uint16_t offset,uint16_t flags,
    const LmnRasterBus *bus) {
    uint32_t p=physical(segment,offset);
    uint8_t low=read_byte(m,p,flags,bus);
    uint8_t high=read_byte(m,(p+1u)&0xfffffu,flags,bus);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_byte(uint8_t *m,uint32_t address,uint8_t value,uint16_t flags,
    const LmnRasterBus *bus) {
    address&=0xfffffu;
    if(bus&&bus->write_byte)bus->write_byte(bus->context,m,address,value,flags);
    else m[address]=value;
}

static void write_word(uint8_t *m,uint16_t segment,uint16_t offset,uint16_t value,
    uint16_t flags,const LmnRasterBus *bus) {
    uint32_t p=physical(segment,offset);
    write_byte(m,p,(uint8_t)value,flags,bus);
    write_byte(m,(p+1u)&0xfffffu,(uint8_t)(value>>8),flags,bus);
}

static uint16_t pop_word(uint8_t *m,uint16_t ss,LmnDrawingDispatchResult *state,
    const LmnRasterBus *bus) {
    uint16_t value=read_word(m,ss,state->stack_offset,state->flags,bus);
    state->stack_offset=(uint16_t)(state->stack_offset+2u);
    return value;
}

static void push_word(uint8_t *m,uint16_t ss,LmnDrawingDispatchResult *state,
    uint16_t value,const LmnRasterBus *bus) {
    state->stack_offset=(uint16_t)(state->stack_offset-2u);
    write_word(m,ss,state->stack_offset,value,state->flags,bus);
}

static unsigned parity_even(uint8_t value) {
    value^=(uint8_t)(value>>4);
    value&=15u;
    return ((0x6996u>>value)&1u)?0u:1u;
}

static uint16_t szp16(uint16_t value) {
    return (uint16_t)((parity_even((uint8_t)value)?4u:0u)|
        (value?0u:0x40u)|(value&0x8000u?0x80u:0u));
}

static uint16_t logic16(uint16_t flags,uint16_t value) {
    return (uint16_t)((flags&~0x8d5u)|szp16(value));
}

static uint16_t add16_flags(uint16_t flags,uint16_t a,uint16_t b,uint16_t result) {
    uint32_t wide=(uint32_t)a+(uint32_t)b;
    uint16_t defined=(uint16_t)(szp16(result)|((a^b^result)&0x10u)|
        (wide>0xffffu?1u:0u)|((~(a^b)&(a^result)&0x8000u)?0x800u:0u));
    return (uint16_t)((flags&~0x8d5u)|defined);
}

static uint16_t sub16_flags(uint16_t flags,uint16_t a,uint16_t b,uint16_t result) {
    uint16_t defined=(uint16_t)(szp16(result)|((a^b^result)&0x10u)|
        (a<b?1u:0u)|(((a^b)&(a^result)&0x8000u)?0x800u:0u));
    return (uint16_t)((flags&~0x8d5u)|defined);
}

static uint16_t add16(uint16_t *value,uint16_t operand,uint16_t flags) {
    uint16_t before=*value;
    *value=(uint16_t)(before+operand);
    return add16_flags(flags,before,operand,*value);
}

static uint16_t sub16(uint16_t *value,uint16_t operand,uint16_t flags) {
    uint16_t before=*value;
    *value=(uint16_t)(before-operand);
    return sub16_flags(flags,before,operand,*value);
}

static uint16_t cmp8_flags(uint16_t flags,uint8_t a,uint8_t b) {
    uint8_t result=(uint8_t)(a-b);
    uint16_t szp=(uint16_t)((parity_even(result)?4u:0u)|(result?0u:0x40u)|
        (result&0x80u?0x80u:0u));
    uint16_t defined=(uint16_t)(szp|((a^b^result)&0x10u)|(a<b?1u:0u)|
        (((a^b)&(a^result)&0x80u)?0x800u:0u));
    return (uint16_t)((flags&~0x8d5u)|defined);
}

static uint16_t shr16_one(uint16_t *value,uint16_t flags) {
    uint16_t before=*value;
    uint16_t result=(uint16_t)(before>>1);
    uint16_t defined=(uint16_t)(szp16(result)|((before&1u)?1u:0u)|
        ((before&0x8000u)?0x800u:0u));
    *value=result;
    /* AF is undefined for SHR and is retained as an arbitrary representative. */
    return (uint16_t)((flags&~0x8c5u)|defined);
}

static LmnDrawingDispatchResult initial_state(const LmnDrawingDispatchCall *call) {
    LmnDrawingDispatchResult state={0};
    state.work_value=call->left;                 /* AX */
    state.second_source_cursor=call->top;        /* BX */
    state.packed_counts=call->packed_height;     /* CX */
    state.width_state=call->width;               /* DX */
    state.source_cursor=call->source_cursor;     /* SI */
    state.destination_cursor=call->destination_cursor; /* DI */
    state.control=call->control;                 /* BP */
    state.stack_offset=call->stack_offset;
    state.flags=call->flags;
    return state;
}

static LmnDrawingDispatchResult select_from_state(LmnDrawingDispatchResult state) {
    state.flags=logic16(state.flags,(uint16_t)(state.control&2u));
    state.continuation=(state.control&2u)?CS_PrepareAlignedMaskedPlanarRows:
        CS_PrepareAlignedOpaquePlanarRows;
    return state;
}

LmnDrawingDispatchResult lmn_select_unshifted_planar_path_core(uint8_t *memory,
    const LmnDrawingDispatchCall *call,const LmnRasterBus *bus) {
    (void)memory;
    (void)bus;
    return select_from_state(initial_state(call));
}

static LmnDrawingDispatchResult call_unshifted_selector(uint8_t *m,
    LmnDrawingDispatchResult state,uint16_t data_segment,uint16_t stack_segment,
    const LmnRasterBus *bus) {
    LmnDrawingDispatchCall call={data_segment,stack_segment,state.stack_offset,
        state.work_value,state.second_source_cursor,state.packed_counts,state.width_state,
        state.source_cursor,state.destination_cursor,state.control,state.flags};
    return lmn_select_unshifted_planar_path_core(m,&call,bus);
}

static LmnDrawingDispatchResult dispatch_state_from_88a6(uint8_t *m,
    LmnDrawingDispatchResult state,uint16_t data_segment,uint16_t stack_segment,
    const LmnRasterBus *bus) {
    /* The normal 885E path has ZF clear here; a direct 88A6 entry may not. */
    if(state.flags&0x40u) {
        state.continuation=CS_PlanarDrawingAbortReturn;
        return state;
    }
    {
        uint8_t shift=read_byte(m,physical(data_segment,SEG09A9_DrawingLeftBitShiftByte),
            state.flags,bus);
        state.flags=cmp8_flags(state.flags,shift,0);
        if(shift==0u)return call_unshifted_selector(m,state,data_segment,stack_segment,bus);
    }

    state.flags=logic16(state.flags,(uint16_t)(state.control&2u));
    state.continuation=(state.control&2u)?CS_PrepareShiftedMaskedPlanarRows:
        CS_PrepareShiftedOpaquePlanarRows;
    return state;
}

LmnDrawingDispatchResult lmn_prepare_planar_drawing_dispatch_core(uint8_t *m,
    const LmnDrawingDispatchCall *call,const LmnRasterBus *bus) {
    LmnDrawingDispatchResult state=initial_state(call);
    uint16_t pitch,mul_high,product,byte_width,row_advance;
    uint16_t saved_left;
    uint8_t original_ch,original_cl,shifted_dl,shift;

    /* XCHG AX,BX; PUSH BX; AND BX,7; save BL; POP BX. */
    saved_left=state.work_value;
    state.work_value=state.second_source_cursor;
    state.second_source_cursor=saved_left;
    shift=(uint8_t)(state.second_source_cursor&7u);
#if DISPATCH_MUTATION == 1
    shift=(uint8_t)(state.second_source_cursor&3u);
#endif
    push_word(m,call->stack_segment,&state,state.second_source_cursor,bus);
    state.second_source_cursor=shift;
    state.flags=logic16(state.flags,state.second_source_cursor);
    write_byte(m,physical(call->data_segment,SEG09A9_DrawingLeftBitShiftByte),
        (uint8_t)state.second_source_cursor,state.flags,bus);
    state.second_source_cursor=pop_word(m,call->stack_segment,&state,bus);

    /* SHR BX,1 x3; PUSH DX; MUL DS:[pitch]; POP DX through live SS. */
    state.flags=shr16_one(&state.second_source_cursor,state.flags);
    state.flags=shr16_one(&state.second_source_cursor,state.flags);
    state.flags=shr16_one(&state.second_source_cursor,state.flags);
    push_word(m,call->stack_segment,&state,state.width_state,bus);
    pitch=read_word(m,call->data_segment,SEG09A9_DrawingPitchBytes,state.flags,bus);
    {
        uint32_t full=(uint32_t)state.work_value*(uint32_t)pitch;
        product=(uint16_t)full;
        mul_high=(uint16_t)(full>>16);
    }
    state.work_value=product;
    state.flags=(uint16_t)((state.flags&~0x801u)|(mul_high?0x801u:0u));
    state.width_state=pop_word(m,call->stack_segment,&state,bus);
#if DISPATCH_MUTATION == 3
    /* Emulate losing the saved width and retaining MUL's high half instead. */
    state.width_state=mul_high;
#endif

    /* ADD BX,AX; ADD BX,DS:[origin]; ADD BX,DS:[page]; XCHG DI,BX. */
    state.flags=add16(&state.second_source_cursor,state.work_value,state.flags);
    pitch=read_word(m,call->data_segment,SEG09A9_DrawingOrigin,state.flags,bus);
    state.flags=add16(&state.second_source_cursor,pitch,state.flags);
    pitch=read_word(m,call->data_segment,SEG09A9_DrawingPageByteOffset,state.flags,bus);
#if DISPATCH_MUTATION != 2
    state.flags=add16(&state.second_source_cursor,pitch,state.flags);
#endif
    {
        uint16_t computed_destination=state.second_source_cursor;
        state.second_source_cursor=state.destination_cursor;
        state.destination_cursor=computed_destination;
    }

    /* SHR DX,1 x3; AX=DX; SUB AX,pitch; NEG AX; two DS stores. */
    state.flags=shr16_one(&state.width_state,state.flags);
    state.flags=shr16_one(&state.width_state,state.flags);
    state.flags=shr16_one(&state.width_state,state.flags);
    byte_width=state.width_state;
    row_advance=byte_width;
    pitch=read_word(m,call->data_segment,SEG09A9_DrawingPitchBytes,state.flags,bus);
    state.flags=sub16(&row_advance,pitch,state.flags);
    {
        uint16_t negated_operand=row_advance;
        row_advance=(uint16_t)(0u-negated_operand);
        state.flags=sub16_flags(state.flags,0u,negated_operand,row_advance);
    }
    write_word(m,call->data_segment,SEG09A9_DrawingDestinationRowAdvance,
        row_advance,state.flags,bus);
    write_word(m,call->data_segment,SEG09A9_DrawingActiveDestinationRowAdvance,
        row_advance,state.flags,bus);

    /* DH=original CH, CH=original CL, CL=shifted DL, then AX=live extent. */
    original_ch=(uint8_t)(state.packed_counts>>8);
    original_cl=(uint8_t)state.packed_counts;
    shifted_dl=(uint8_t)state.width_state;
    state.width_state=(uint16_t)(((uint16_t)original_ch<<8)|shifted_dl);
    state.packed_counts=(uint16_t)(((uint16_t)original_cl<<8)|shifted_dl);
    state.work_value=read_word(m,call->data_segment,SEG09A9_DrawingSourcePlaneExtent,
        state.flags,bus);

    /* TEST BP,1; normal ZF=0 arrival at 88A6 follows only when set. */
    state.flags=logic16(state.flags,(uint16_t)(state.control&1u));
    if(state.control&1u)
        return dispatch_state_from_88a6(m,state,call->data_segment,call->stack_segment,bus);
    return call_unshifted_selector(m,state,call->data_segment,call->stack_segment,bus);
}

static void store_regs(LmnRegs *regs,const LmnDrawingDispatchResult *state) {
    regs->ax=state->work_value;
    regs->bx=state->second_source_cursor;
    regs->cx=state->packed_counts;
    regs->dx=state->width_state;
    regs->si=state->source_cursor;
    regs->di=state->destination_cursor;
    regs->bp=state->control;
    regs->sp=state->stack_offset;
    regs->flags=state->flags;
    regs->ip=state->continuation;
}

void lmn_prepare_planar_drawing_dispatch_adapter(uint8_t *m,LmnRegs *regs,
    const LmnRasterBus *bus) {
    LmnDrawingDispatchCall call={regs->ds,regs->ss,regs->sp,regs->ax,regs->bx,
        regs->cx,regs->dx,regs->si,regs->di,regs->bp,regs->flags};
    LmnDrawingDispatchResult state;
    if(regs->ip==CS_PlanarInputsReady)
        state=lmn_prepare_planar_drawing_dispatch_core(m,&call,bus);
    else if(regs->ip==CS_PlanarIncomingFlagGate)
        state=dispatch_state_from_88a6(m,initial_state(&call),regs->ds,regs->ss,bus);
    else if(regs->ip==CS_SelectUnshiftedPlanarPath)
        state=lmn_select_unshifted_planar_path_core(m,&call,bus);
    else return;
    store_regs(regs,&state);
}

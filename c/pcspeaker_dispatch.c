#include "pcspeaker_dispatch.h"
#include "pcspeaker.h"
#include "pcspeaker_sym.h"

#ifndef PC_DISPATCH_MUTATION
#define PC_DISPATCH_MUTATION 0
#endif

enum {
    DISPATCH_CF=0x0001u, DISPATCH_PF=0x0004u, DISPATCH_AF=0x0010u,
    DISPATCH_ZF=0x0040u, DISPATCH_SF=0x0080u, DISPATCH_IF=0x0200u,
    DISPATCH_OF=0x0800u,
    DISPATCH_ARITH=0x08d5u, DISPATCH_IRET_FLAGS=0x7fd5u
};

typedef struct DispatchState {
    uint16_t ax,bx,cx,dx,si,di,ds,cs,ss,sp,flags;
} DispatchState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&0xfffffu);
}

static uint8_t read_physical(uint8_t *memory,uint32_t address,uint16_t flags,
                             const LmnRasterBus *bus) {
    address&=0xfffffu;
    if(bus&&bus->read_byte)
        return bus->read_byte(bus->context,memory,address,flags);
    return memory[address];
}

static void write_physical(uint8_t *memory,uint32_t address,uint8_t value,
                           uint16_t flags,const LmnRasterBus *bus) {
    address&=0xfffffu;
    if(bus&&bus->write_byte)
        bus->write_byte(bus->context,memory,address,value,flags);
    else
        memory[address]=value;
}

/* A real-mode word crosses to the next physical byte, even at offset FFFF. */
static uint16_t read_word(uint8_t *memory,uint16_t segment,uint16_t offset,
                          uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(memory,address,flags,bus);
    uint8_t high=read_physical(memory,address+1u,flags,bus);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write_word(uint8_t *memory,uint16_t segment,uint16_t offset,
                       uint16_t value,uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(segment,offset);
    write_physical(memory,address,(uint8_t)value,flags,bus);
    write_physical(memory,address+1u,(uint8_t)(value>>8),flags,bus);
}

static void push_word(uint8_t *memory,DispatchState *state,uint16_t value,
                      const LmnRasterBus *bus) {
    state->sp=(uint16_t)(state->sp-2u);
    write_word(memory,state->ss,state->sp,value,state->flags,bus);
}

static uint16_t pop_word(uint8_t *memory,DispatchState *state,
                         const LmnRasterBus *bus) {
    uint16_t value=read_word(memory,state->ss,state->sp,state->flags,bus);
    state->sp=(uint16_t)(state->sp+2u);
    return value;
}

static uint16_t parity_flag(uint8_t value) {
    unsigned parity=0,bit;
    for(bit=0;bit<8;++bit)parity^=(value>>bit)&1u;
    return parity ? 0u : DISPATCH_PF;
}

static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    uint16_t result=(uint16_t)(flags&(uint16_t)~DISPATCH_ARITH);
    result=(uint16_t)(result|parity_flag(value));
    if(value==0)result=(uint16_t)(result|DISPATCH_ZF);
    if(value&0x80u)result=(uint16_t)(result|DISPATCH_SF);
    /* AF is undefined after XOR; the reconstruction chooses zero. */
    return result;
}

static uint16_t sub8_flags(uint16_t flags,uint8_t before,uint8_t value,
                           uint8_t after) {
    uint16_t result=(uint16_t)(flags&(uint16_t)~DISPATCH_ARITH);
    result=(uint16_t)(result|parity_flag(after));
    if(before<value)result=(uint16_t)(result|DISPATCH_CF);
    if(((before^value^after)&0x10u)!=0)result=(uint16_t)(result|DISPATCH_AF);
    if(after==0)result=(uint16_t)(result|DISPATCH_ZF);
    if(after&0x80u)result=(uint16_t)(result|DISPATCH_SF);
    if((((before^value)&(before^after))&0x80u)!=0)
        result=(uint16_t)(result|DISPATCH_OF);
    return result;
}

static uint16_t shl8_one_flags(uint16_t flags,uint8_t before,uint8_t after) {
    uint16_t result=(uint16_t)(flags&(uint16_t)~DISPATCH_ARITH);
    uint16_t carry=(uint16_t)((before&0x80u)?DISPATCH_CF:0u);
    result=(uint16_t)(result|parity_flag(after)|carry);
    if(after==0)result=(uint16_t)(result|DISPATCH_ZF);
    if(after&0x80u)result=(uint16_t)(result|DISPATCH_SF);
    /* For a one-bit shift, OF is the result MSB XOR the last carry. */
    if(((after&0x80u)!=0)!=((carry&DISPATCH_CF)!=0))
        result=(uint16_t)(result|DISPATCH_OF);
    return result;
}

static LmnPcSpeakerDispatchResult make_result(const DispatchState *state,
                                              uint16_t continuation,
                                              uint16_t status) {
    LmnPcSpeakerDispatchResult result;
    result.value=state->ax;
    result.base_value=state->bx;
    result.count=state->cx;
    result.argument=state->dx;
    result.source_cursor=state->si;
    result.output_cursor=state->di;
    result.data_segment=state->ds;
    result.driver_segment=state->cs;
    result.stack_segment=state->ss;
    result.stack_offset=state->sp;
    result.flags=state->flags;
    result.continuation=continuation;
    result.status=status;
    return result;
}

static void restore_pushed_registers(uint8_t *memory,DispatchState *state,
    uint16_t original_bx,uint16_t original_cx,uint16_t original_dx,
    uint16_t original_si,uint16_t original_di,uint16_t original_ds,
    const LmnRasterBus *bus) {
#if PC_DISPATCH_MUTATION != 2
    (void)original_ds;
#endif
#if PC_DISPATCH_MUTATION != 6
    (void)original_bx;(void)original_cx;(void)original_dx;
    (void)original_si;(void)original_di;
#endif
    uint16_t saved_ds=pop_word(memory,state,bus);
#if PC_DISPATCH_MUTATION == 2
    (void)saved_ds;
    state->ds=original_ds;
#else
    state->ds=saved_ds;
#endif
    {
        uint16_t saved_di=pop_word(memory,state,bus);
        uint16_t saved_si=pop_word(memory,state,bus);
        uint16_t saved_dx=pop_word(memory,state,bus);
        uint16_t saved_cx=pop_word(memory,state,bus);
        uint16_t saved_bx=pop_word(memory,state,bus);
#if PC_DISPATCH_MUTATION == 6
        (void)saved_di;(void)saved_si;(void)saved_dx;
        (void)saved_cx;(void)saved_bx;
        state->di=original_di;
        state->si=original_si;
        state->dx=original_dx;
        state->cx=original_cx;
        state->bx=original_bx;
#else
        state->di=saved_di;
        state->si=saved_si;
        state->dx=saved_dx;
        state->cx=saved_cx;
        state->bx=saved_bx;
#endif
    }
}

LmnPcSpeakerDispatchResult lmn_pc_speaker_dispatch_core(uint8_t *memory,
    const LmnPcSpeakerDispatchCall *call,const LmnRasterBus *bus) {
    DispatchState state;
    uint16_t original_bx=call->base_value,original_cx=call->count;
    uint16_t original_dx=call->argument,original_si=call->source_cursor;
    uint16_t original_di=call->output_cursor,original_ds=call->data_segment;
    uint8_t selector,ah,bl;
    uint16_t target,table_offset;

    state.ax=call->value;state.bx=call->base_value;state.cx=call->count;
    state.dx=call->argument;state.si=call->source_cursor;
    state.di=call->output_cursor;state.ds=call->data_segment;
    state.cs=call->driver_segment;state.ss=call->stack_segment;
    state.sp=call->stack_offset;state.flags=call->flags;

    /* 0182: STI, then the six original register saves. */
#if PC_DISPATCH_MUTATION != 1
    state.flags=(uint16_t)(state.flags|DISPATCH_IF);
#endif
    push_word(memory,&state,state.bx,bus); /* 0183 PUSH BX */
    push_word(memory,&state,state.cx,bus); /* 0184 PUSH CX */
    push_word(memory,&state,state.dx,bus); /* 0185 PUSH DX */
    push_word(memory,&state,state.si,bus); /* 0186 PUSH SI */
    push_word(memory,&state,state.di,bus); /* 0187 PUSH DI */
    push_word(memory,&state,state.ds,bus); /* 0188 PUSH DS */

    /* 0189 PUSH CS / 018A POP DS uses the live SS frame. */
    push_word(memory,&state,state.cs,bus);
    state.ds=pop_word(memory,&state,bus);
#if PC_DISPATCH_MUTATION == 8
    state.ds=state.cs; /* Mutation: bypass the live PUSH CS / POP DS value. */
#endif

    /* 018B XOR BH,BH; 018D MOV BL,AH; 018F SUB AH,10h. */
    state.bx=(uint16_t)(state.bx&0x00ffu);
    state.flags=logic8_flags(state.flags,0);
    ah=(uint8_t)(state.ax>>8);
    state.bx=(uint16_t)((state.bx&0xff00u)|ah);
    state.ax=(uint16_t)((state.ax&0x00ffu)|
        ((uint16_t)(uint8_t)(ah-0x10u)<<8));
    state.flags=sub8_flags(state.flags,ah,0x10u,(uint8_t)(ah-0x10u));

    /* 0192 JA uses the unsigned flags from SUB AH,10h. */
    if(ah>0x10u) {
        /* 01A1 SUB BL,20h; 01A4 JC selects a raw data-byte read. */
        uint8_t before=(uint8_t)state.bx;
        uint8_t after=(uint8_t)(before-0x20u);
        state.flags=sub8_flags(state.flags,before,0x20u,after);
        state.bx=(uint16_t)((state.bx&0xff00u)|after);
        if(before<0x20u) {
            /* 01AA MOV BL,AH (the SUB AH,10h residual), then 01AC read. */
            state.bx=(uint16_t)((state.bx&0xff00u)|(uint8_t)(state.ax>>8));
            state.ax=(uint16_t)((state.ax&0xff00u)|
                read_physical(memory,physical(state.ds,state.bx),
                              state.flags,bus));
        } else {
            /* 01A6 MOV [BX],AL.  The raw 00..DF write range is unchecked. */
            write_physical(memory,physical(state.ds,state.bx),
                           (uint8_t)state.ax,state.flags,bus);
        }
#if PC_DISPATCH_MUTATION == 7
        state.ax=(uint16_t)(state.ax&0x00ffu);
#endif
        restore_pushed_registers(memory,&state,original_bx,original_cx,
                                 original_dx,original_si,original_di,
                                 original_ds,bus);
        return make_result(&state,PC_DispatchReturn01A0,
                           LMN_PC_SPEAKER_IRET_READY);
    }

    /* 0194 SHL BL,1 creates the unchecked near-pointer offset. */
    bl=(uint8_t)state.bx;
#if PC_DISPATCH_MUTATION == 3
    if(bl>4u)bl=4u;
#endif
    selector=(uint8_t)(bl<<1);
    state.bx=(uint16_t)((state.bx&0xff00u)|selector);
    state.flags=shl8_one_flags(state.flags,bl,selector);
    table_offset=(uint16_t)(PC_DispatchTable001E+state.bx);

    /* CALL r/m16 reads its live table operand before pushing the return IP. */
#if PC_DISPATCH_MUTATION == 5
    push_word(memory,&state,PC_DispatchCallReturn019A,bus);
#endif
    target=read_word(memory,state.ds,table_offset,state.flags,bus);

#if PC_DISPATCH_MUTATION != 5
    push_word(memory,&state,PC_DispatchCallReturn019A,bus);
#endif

    /* The two proved executable table destinations are composed as bus cores.
       Tick and all other live targets remain explicit child-boundary exits. */
#if PC_DISPATCH_MUTATION == 7
    state.ax=(uint16_t)(state.ax&0x00ffu);
#endif
    if(target!=PC_LoadEffect && target!=PC_Stop) {
        return make_result(&state,target,LMN_PC_SPEAKER_UNTRANSLATED_CHILD);
    }

    if(target==PC_LoadEffect) {
        LmnPcSoundResult child=lmn_pc_sound_effect_bus_core(memory,state.ds,
            (uint8_t)state.ax,state.dx,state.flags,bus);
        state.ax=child.ax;state.bx=child.bx;state.cx=child.cx;
        state.dx=child.dx;state.si=child.si;state.flags=child.flags;
        /* LoadEffect has no DI/DS/SS effects. */
    } else {
        LmnPcSoundResult child=lmn_pc_sound_stop_bus_core(memory,state.ds,
            state.ax,state.bx,state.cx,state.dx,state.si,state.flags,bus);
        state.ax=child.ax;state.bx=child.bx;state.cx=child.cx;
        state.dx=child.dx;state.si=child.si;state.flags=child.flags;
        /* Stop has no DI/DS/SS effects. */
    }

    /* The child RET reads the real live return word, then increments SP. */
#if PC_DISPATCH_MUTATION == 4
    target=PC_DispatchCallReturn019A;
    state.sp=(uint16_t)(state.sp+2u);
#else
    target=pop_word(memory,&state,bus);
#endif
    if(target!=PC_DispatchCallReturn019A)
        return make_result(&state,target,LMN_PC_SPEAKER_CHANGED_CHILD_RETURN);

    restore_pushed_registers(memory,&state,original_bx,original_cx,
                             original_dx,original_si,original_di,original_ds,bus);
    return make_result(&state,PC_DispatchReturn01A0,
                       LMN_PC_SPEAKER_IRET_READY);
}

static void apply_result(LmnRegs *registers,
                         const LmnPcSpeakerDispatchResult *result) {
    registers->ax=result->value;
    registers->bx=result->base_value;
    registers->cx=result->count;
    registers->dx=result->argument;
    registers->si=result->source_cursor;
    registers->di=result->output_cursor;
    registers->ds=result->data_segment;
    registers->cs=result->driver_segment;
    registers->ss=result->stack_segment;
    registers->sp=result->stack_offset;
    registers->flags=result->flags;
    registers->ip=result->continuation;
}

uint16_t lmn_pc_speaker_dispatch_adapter(uint8_t *memory,LmnRegs *registers,
                                          const LmnRasterBus *bus) {
    LmnPcSpeakerDispatchCall call;
    LmnPcSpeakerDispatchResult result;
    uint16_t ip,cs,flags,sp;

    call.value=registers->ax;call.base_value=registers->bx;
    call.count=registers->cx;call.argument=registers->dx;
    call.source_cursor=registers->si;call.output_cursor=registers->di;
    call.data_segment=registers->ds;call.driver_segment=registers->cs;
    call.stack_segment=registers->ss;call.stack_offset=registers->sp;
    call.flags=registers->flags;
    result=lmn_pc_speaker_dispatch_core(memory,&call,bus);
    apply_result(registers,&result);
    if(result.status!=LMN_PC_SPEAKER_IRET_READY)return result.status;

    /* The native core ends before IRET; consume its live three-word frame. */
    sp=result.stack_offset;
    ip=read_word(memory,registers->ss,sp,result.flags,bus);
    sp=(uint16_t)(sp+2u);
    cs=read_word(memory,registers->ss,sp,result.flags,bus);
    sp=(uint16_t)(sp+2u);
    flags=read_word(memory,registers->ss,sp,result.flags,bus);
    sp=(uint16_t)(sp+2u);

    registers->ip=ip;registers->cs=cs;
    registers->flags=(uint16_t)((flags&DISPATCH_IRET_FLAGS)|2u);
    registers->sp=sp;
    return result.status;
}

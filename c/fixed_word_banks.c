#include "fixed_word_banks.h"

#include "lemmings_sym.h"
#include "mask_generators.h"

#ifndef FIXED_WORD_BANKS_MUTATION
#define FIXED_WORD_BANKS_MUTATION 0
#endif

#if FIXED_WORD_BANKS_MUTATION < 0 || FIXED_WORD_BANKS_MUTATION > 10
#error "FIXED_WORD_BANKS_MUTATION must be a numeric ID from 0 through 10"
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,ZF=0x0040u,SF=0x0080u,
    DF=0x0400u,OF=0x0800u,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct FixedWordBanksState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status,child_entry;
} FixedWordBanksState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+(uint32_t)offset)&MEMORY_MASK);
}

static uint8_t read_physical(FixedWordBanksState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(FixedWordBanksState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

/* MOV ES,[DS:1FEA] wraps its high byte in the 20-bit physical domain. */
static uint16_t read_word_physical(FixedWordBanksState *s,uint16_t segment,
                                   uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,(address+1u)&MEMORY_MASK);
    return (uint16_t)(low|((uint16_t)high<<8));
}

/* Parent stack words normally use physical+1; mutation 8 substitutes EA16. */
#if FIXED_WORD_BANKS_MUTATION != 10
static uint16_t read_stack_word(FixedWordBanksState *s,uint16_t offset) {
    uint32_t address=physical(s->ss,offset);
    uint32_t high_address;
#if FIXED_WORD_BANKS_MUTATION == 8
    high_address=physical(s->ss,(uint16_t)(offset+1u));
#else
    high_address=(address+1u)&MEMORY_MASK;
#endif
    {
        uint8_t low=read_physical(s,address);
        uint8_t high=read_physical(s,high_address);
        return (uint16_t)(low|((uint16_t)high<<8));
    }
}
#endif

static void write_stack_word(FixedWordBanksState *s,uint16_t offset,
                             uint16_t value) {
    uint32_t address=physical(s->ss,offset);
    uint32_t high_address;
#if FIXED_WORD_BANKS_MUTATION == 8
    high_address=physical(s->ss,(uint16_t)(offset+1u));
#else
    high_address=(address+1u)&MEMORY_MASK;
#endif
    write_physical(s,address,(uint8_t)value);
    write_physical(s,high_address,(uint8_t)(value>>8));
}

static void push16(FixedWordBanksState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write_stack_word(s,s->sp,value);
}

#if FIXED_WORD_BANKS_MUTATION == 4
static uint16_t pop16(FixedWordBanksState *s) {
    uint16_t value=read_stack_word(s,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}
#endif

static uint16_t logic_flags(uint16_t flags) {
    /* XOR DI,DI sets CF/OF=0 and PF/ZF=1; AF remains opaque. */
    return (uint16_t)((flags&~LOGIC)|PF|ZF);
}

static void state_from_call(FixedWordBanksState *s,uint8_t *memory,
                            const LmnFixedWordBanksCall *call,
                            const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->ax;s->bx=call->bx;s->cx=call->cx;s->dx=call->dx;
    s->si=call->si;s->di=call->di;s->bp=call->bp;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=CS_WordMaskGeneratorReturn;
    s->status=LMN_FIXED_WORD_BANKS_READY;
    s->child_entry=0u;
}

static LmnFixedWordBanksResult result_of(const FixedWordBanksState *s) {
    LmnFixedWordBanksResult out;
    out.ax=s->ax;out.bx=s->bx;out.cx=s->cx;out.dx=s->dx;
    out.si=s->si;out.di=s->di;out.bp=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    out.child_entry=s->child_entry;
    return out;
}

static void state_from_regs(FixedWordBanksState *s,const LmnRegs *r) {
    s->ax=r->ax;s->bx=r->bx;s->cx=r->cx;s->dx=r->dx;
    s->si=r->si;s->di=r->di;s->bp=r->bp;
    s->cs=r->cs;s->ds=r->ds;s->es=r->es;s->ss=r->ss;
    s->sp=r->sp;s->flags=r->flags;s->continuation=r->ip;
}

static void regs_from_state(const FixedWordBanksState *s,LmnRegs *r) {
    r->ax=s->ax;r->bx=s->bx;r->cx=s->cx;r->dx=s->dx;
    r->si=s->si;r->di=s->di;r->bp=s->bp;
    r->cs=s->cs;r->ds=s->ds;r->es=s->es;r->ss=s->ss;
    r->sp=s->sp;r->flags=s->flags;r->ip=s->continuation;
}

static int invoke_word_mask_shifts(FixedWordBanksState *s,
                                   uint16_t expected_return) {
    LmnRegs registers;
    uint16_t saved_cs=s->cs;

    push16(s,expected_return);                 /* Actual near CALL frame. */
#if FIXED_WORD_BANKS_MUTATION == 6
    s->flags=(uint16_t)(s->flags&~DF);         /* Force DF clear at child entry. */
#endif
    regs_from_state(s,&registers);
    registers.ip=CS_GenerateWordMaskShifts;
    lmn_generate_word_mask_shifts_adapter(s->memory,&registers,s->bus);
    state_from_regs(s,&registers);
    if(s->cs!=saved_cs||s->continuation!=expected_return) {
#if FIXED_WORD_BANKS_MUTATION == 5
        /* Ignore a changed RET target and resume the known parent sequence. */
        s->cs=saved_cs;s->continuation=expected_return;
        return 1;
#else
        s->status=LMN_FIXED_WORD_BANKS_CHANGED_CHILD_RETURN;
        s->child_entry=CS_GenerateWordMaskShifts;
        return 0;
#endif
    }
    return 1;
}

LmnFixedWordBanksResult lmn_generate_fixed_word_mask_banks_core(
    uint8_t *memory,const LmnFixedWordBanksCall *call,
    const LmnRasterBus *bus) {
    FixedWordBanksState s;
#if FIXED_WORD_BANKS_MUTATION == 3
    uint16_t entry_bx=call->bx;
#endif

    state_from_call(&s,memory,call,bus);
#if FIXED_WORD_BANKS_MUTATION == 2
    s.si=SEG09A9_FixedWordPatternA+2u;
#else
    s.si=SEG09A9_FixedWordPatternA;             /* MOV SI,52BCh */
#endif
    {
        uint16_t selected_es=read_word_physical(&s,s.ds,SEG09A9_GeneratedWordPatternBufferSegment);
#if FIXED_WORD_BANKS_MUTATION == 1
        (void)selected_es;                     /* Mutation: retain entry ES. */
#else
        s.es=selected_es;                      /* MOV ES,[DS:1FEA] */
#endif
    }
    s.di=0u;                                   /* XOR DI,DI */
    s.flags=logic_flags(s.flags);
    s.cx=0x10u;                                /* MOV CX,10h */
    s.bx=(uint16_t)((s.bx&0xff00u)|3u);        /* MOV BL,3 */
    if(!invoke_word_mask_shifts(&s,0x5cd2u))
        return result_of(&s);

#if FIXED_WORD_BANKS_MUTATION == 3
    s.bx=(uint16_t)((s.bx&0x00ffu)|(entry_bx&0xff00u));
#endif
    s.si=SEG09A9_FixedWordPatternB;             /* MOV SI,531Ch */
#if FIXED_WORD_BANKS_MUTATION == 7
    s.di=0x0481u;                              /* Mutation: second DI immediate. */
#else
    s.di=0x0480u;                              /* MOV DI,480h */
#endif
    s.bx=(uint16_t)((s.bx&0xff00u)|3u);        /* MOV BL,3, preserving returned BH */
    s.cx=0x10u;                                /* MOV CX,10h */

#if FIXED_WORD_BANKS_MUTATION == 4
    push16(&s,0x5ce0u);                        /* Erroneous CALL frame for fall-through. */
#endif
    {
        LmnMaskGeneratorCall child={
            s.ds,s.es,s.ss,s.sp,s.si,s.di,s.bx,s.cx,s.dx,s.flags
        };
        LmnMaskGeneratorResult out=
            lmn_generate_word_mask_shifts_core(memory,&child,bus);
        s.ax=out.value;s.bx=out.column_repetitions;s.cx=out.row_count;
        s.dx=out.shift_state;s.si=out.source_cursor;s.di=out.output_cursor;
        s.sp=out.stack_offset;s.flags=out.flags;
    }

#if FIXED_WORD_BANKS_MUTATION == 4
    s.continuation=pop16(&s);                  /* Consume erroneous child's own frame. */
    s.status=LMN_FIXED_WORD_BANKS_CHANGED_CHILD_RETURN;
    s.child_entry=CS_GenerateWordMaskShifts;
    return result_of(&s);                      /* Stop before outer RET 5D17. */
#else
    s.continuation=CS_WordMaskGeneratorReturn;  /* Core boundary before RET 5D17. */
    s.status=LMN_FIXED_WORD_BANKS_READY;
    return result_of(&s);
#endif
}

static void regs_from_result(const LmnFixedWordBanksResult *s,LmnRegs *r) {
    r->ax=s->ax;r->bx=s->bx;r->cx=s->cx;r->dx=s->dx;
    r->si=s->si;r->di=s->di;r->bp=s->bp;
    r->cs=s->code_segment;r->ds=s->data_segment;r->es=s->extra_segment;
    r->ss=s->stack_segment;r->sp=s->stack_offset;r->flags=s->flags;
    r->ip=s->continuation;
}

uint16_t lmn_generate_fixed_word_mask_banks_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus) {
    LmnFixedWordBanksCall call={
        registers->ax,registers->bx,registers->cx,registers->dx,
        registers->si,registers->di,registers->bp,
        registers->cs,registers->ds,registers->es,
        registers->ss,registers->sp,registers->flags
    };
    LmnFixedWordBanksResult result;
#if FIXED_WORD_BANKS_MUTATION == 9
    FixedWordBanksState prefetch_state;
    uint16_t prefetched_return;
    state_from_call(&prefetch_state,memory,&call,bus);
    prefetched_return=read_stack_word(&prefetch_state,registers->sp);
#endif

    result=lmn_generate_fixed_word_mask_banks_core(memory,&call,bus);
    regs_from_result(&result,registers);
    if(result.status==LMN_FIXED_WORD_BANKS_READY) {
#if FIXED_WORD_BANKS_MUTATION == 10
        /* Mutation: leave the caller's real RET word unconsumed. */
#else
        uint16_t return_word;
#if FIXED_WORD_BANKS_MUTATION == 9
        return_word=prefetched_return;
#else
        FixedWordBanksState ret_state;
        state_from_call(&ret_state,memory,&call,bus);
        ret_state.ss=result.stack_segment;ret_state.sp=result.stack_offset;
        ret_state.flags=result.flags;
        return_word=read_stack_word(&ret_state,result.stack_offset);
#endif
        registers->ip=return_word;
        registers->sp=(uint16_t)(result.stack_offset+2u);
#endif
    }
    return result.status;
}

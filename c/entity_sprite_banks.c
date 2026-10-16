#include "entity_sprite_banks.h"

#include "sprite_bank.h"
#include "sprite_shift_banks.h"
#include "sprite_wide_banks.h"
#include "lemmings_sym.h"

#ifndef ENTITY_SPRITE_BANKS_MUTATION
#define ENTITY_SPRITE_BANKS_MUTATION 0
#endif

#if ENTITY_SPRITE_BANKS_MUTATION < 0 || ENTITY_SPRITE_BANKS_MUTATION > 10
#error "ENTITY_SPRITE_BANKS_MUTATION must be a numeric ID from 0 through 10"
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct EntitySpriteBanksState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status,child_entry,child_status;
} EntitySpriteBanksState;

typedef uint16_t (*EntitySpriteBanksChildAdapter)(
    uint8_t *,LmnRegs *,const LmnRasterBus *);

typedef struct EntitySpriteBanksGroup {
    uint16_t count,dx,entry,return_ip,source_advance;
    EntitySpriteBanksChildAdapter adapter;
} EntitySpriteBanksGroup;

static const EntitySpriteBanksGroup groups[] = {
    {0x12u,0x020au,CS_GenerateThreeByteSpriteBanks,0x59d2u,0x28u,
     lmn_generate_sprite_shift_banks3_adapter},
    {0x10u,0x030eu,CS_CopySpritePlanesAndAppendMask,0x59e2u,0x54u,
     lmn_copy_sprite_planes_mask_adapter},
    {0x10u,0x020cu,CS_CopySpritePlanesAndAppendMask,0x59f2u,0x30u,
     lmn_copy_sprite_planes_mask_adapter},
    {0x10u,0x020au,CS_GenerateThreeByteSpriteBanks,0x5a02u,0x28u,
     lmn_generate_sprite_shift_banks3_adapter},
    {0x10u,0x020cu,CS_CopySpritePlanesAndAppendMask,0x5a12u,0x30u,
     lmn_copy_sprite_planes_mask_adapter},
    {0x20u,0x030du,CS_CopySpritePlanesAndAppendMask,0x5a22u,0x4eu,
     lmn_copy_sprite_planes_mask_adapter},
    {0x40u,0x030au,CS_CopySpritePlanesAndAppendMask,0x5a32u,0x3cu,
     lmn_copy_sprite_planes_mask_adapter},
    {0x30u,0x030du,CS_CopySpritePlanesAndAppendMask,0x5a42u,0x4eu,
     lmn_copy_sprite_planes_mask_adapter},
    {0x08u,0x020au,CS_GenerateThreeByteSpriteBanks,0x5a52u,0x28u,
     lmn_generate_sprite_shift_banks3_adapter},
    {0x10u,0x0310u,CS_CopySpritePlanesAndAppendMask,0x5a62u,0x60u,
     lmn_copy_sprite_planes_mask_adapter},
    {0x10u,0x020au,CS_GenerateThreeByteSpriteBanks,0x5a72u,0x28u,
     lmn_generate_sprite_shift_banks3_adapter},
    {0x08u,0x020du,CS_CopySpritePlanesAndAppendMask,0x5a82u,0x34u,
     lmn_copy_sprite_planes_mask_adapter},
    {0x0eu,0x040eu,CS_CopySpritePlanesAndAppendMask,0x5a92u,0x70u,
     lmn_copy_sprite_planes_mask_adapter},
    {0x10u,0x020au,CS_GenerateThreeByteSpriteBanks,0x5aa2u,0x28u,
     lmn_generate_sprite_shift_banks3_adapter},
    {0x20u,0x020au,CS_GenerateThreeByteSpriteBanks,0x5ab2u,0x28u,
     lmn_generate_sprite_shift_banks3_adapter}
};

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+(uint32_t)offset)&MEMORY_MASK);
}

static uint8_t read_physical(EntitySpriteBanksState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(EntitySpriteBanksState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint16_t read16(EntitySpriteBanksState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint32_t high_address;
#if ENTITY_SPRITE_BANKS_MUTATION == 8
    high_address=physical(segment,(uint16_t)(offset+1u));
#else
    high_address=(address+1u)&MEMORY_MASK;
#endif
    {
        uint8_t low=read_physical(s,address);
        uint8_t high=read_physical(s,high_address);
        return (uint16_t)(low|((uint16_t)high<<8));
    }
}

static void write16(EntitySpriteBanksState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    uint32_t high_address;
#if ENTITY_SPRITE_BANKS_MUTATION == 8
    high_address=physical(segment,(uint16_t)(offset+1u));
#else
    high_address=(address+1u)&MEMORY_MASK;
#endif
    write_physical(s,address,(uint8_t)value);
    write_physical(s,high_address,(uint8_t)(value>>8));
}

static void push16(EntitySpriteBanksState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop16(EntitySpriteBanksState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0u;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&(1u<<(bits-1u)))out|=SF;
    return out;
}

static uint16_t logic_flags(uint16_t flags,uint16_t value,unsigned bits) {
    /* AF is undefined on XOR; preserve it as opaque state. */
    return (uint16_t)((flags&~LOGIC)|szp(value,bits));
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t value=(uint16_t)wide,out=szp(value,16u);
    if(wide>0xffffu)out|=CF;
    if((left^right^value)&AF)out|=AF;
    if((~(left^right)&(left^value)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static void state_from_call(EntitySpriteBanksState *s,uint8_t *memory,
                            const LmnEntitySpriteBanksCall *call,
                            const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->ax;s->bx=call->bx;s->cx=call->cx;s->dx=call->dx;
    s->si=call->si;s->di=call->di;s->bp=call->bp;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=CS_EntitySpriteBanksReturn;
    s->status=LMN_ENTITY_SPRITE_BANKS_READY;
    s->child_entry=0u;s->child_status=0xffffu;
}

static LmnEntitySpriteBanksResult result_of(const EntitySpriteBanksState *s) {
    LmnEntitySpriteBanksResult out;
    out.ax=s->ax;out.bx=s->bx;out.cx=s->cx;out.dx=s->dx;
    out.si=s->si;out.di=s->di;out.bp=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    out.child_entry=s->child_entry;out.child_status=s->child_status;
    return out;
}

static void state_from_regs(EntitySpriteBanksState *s,const LmnRegs *r) {
    s->ax=r->ax;s->bx=r->bx;s->cx=r->cx;s->dx=r->dx;
    s->si=r->si;s->di=r->di;s->bp=r->bp;
    s->cs=r->cs;s->ds=r->ds;s->es=r->es;s->ss=r->ss;
    s->sp=r->sp;s->flags=r->flags;s->continuation=r->ip;
}

static void regs_from_state(const EntitySpriteBanksState *s,LmnRegs *r) {
    r->ax=s->ax;r->bx=s->bx;r->cx=s->cx;r->dx=s->dx;
    r->si=s->si;r->di=s->di;r->bp=s->bp;
    r->cs=s->cs;r->ds=s->ds;r->es=s->es;r->ss=s->ss;
    r->sp=s->sp;r->flags=s->flags;r->ip=s->continuation;
}

static int invoke_child(EntitySpriteBanksState *s,uint16_t entry,
                        uint16_t expected_return,uint16_t call_word,
                        EntitySpriteBanksChildAdapter adapter) {
    LmnRegs registers;
    uint16_t saved_cs=s->cs,child_status;
#if ENTITY_SPRITE_BANKS_MUTATION == 3
    uint16_t saved_es=s->es;
#endif

    push16(s,call_word);                       /* Actual near CALL frame. */
    regs_from_state(s,&registers);
    registers.ip=entry;
    child_status=adapter(s->memory,&registers,s->bus);
    state_from_regs(s,&registers);
#if ENTITY_SPRITE_BANKS_MUTATION == 3
    s->es=saved_es;
#endif

    if(child_status!=0u) {
        s->child_entry=entry;s->child_status=child_status;
        s->status=LMN_ENTITY_SPRITE_BANKS_CHILD_STOP;
        return 0;
    }
    if(s->cs!=saved_cs || s->continuation!=expected_return) {
#if ENTITY_SPRITE_BANKS_MUTATION == 5
        /* Mutation: hide a changed near-return target and resume the caller. */
        s->cs=saved_cs;s->continuation=expected_return;
        return 1;
#else
        s->child_entry=entry;s->child_status=child_status;
        s->status=LMN_ENTITY_SPRITE_BANKS_CHANGED_CHILD_RETURN;
        return 0;
#endif
    }
    return 1;
}

LmnEntitySpriteBanksResult lmn_generate_entity_sprite_banks_core(
    uint8_t *memory,const LmnEntitySpriteBanksCall *call,
    const LmnRasterBus *bus) {
    EntitySpriteBanksState s;
    size_t index;
#if ENTITY_SPRITE_BANKS_MUTATION == 7
    uint16_t cached_saved_ds=call->data_segment;
#endif

    state_from_call(&s,memory,call,bus);

#if ENTITY_SPRITE_BANKS_MUTATION == 1
    {
        uint16_t selected_es=read16(&s,s.ds,
            (uint16_t)(SEG09A9_EntitySpriteBufferSegment-
                       SEG09A9_GameDataImage));
        uint16_t selected_ds=read16(&s,s.ds,
            (uint16_t)(SEG09A9_GraphicsResourceSegment-
                       SEG09A9_GameDataImage));
        push16(&s,s.ds);                       /* Mutation reorders selector reads. */
        s.es=selected_es;
        s.ds=selected_ds;
    }
#else
    push16(&s,s.ds);                           /* PUSH DS before selector reads. */
    s.es=read16(&s,s.ds,
        (uint16_t)(SEG09A9_EntitySpriteBufferSegment-
                   SEG09A9_GameDataImage));
    s.ds=read16(&s,s.ds,
        (uint16_t)(SEG09A9_GraphicsResourceSegment-
                   SEG09A9_GameDataImage));
#endif
    s.si=0u;                                   /* XOR SI,SI */
    s.flags=logic_flags(s.flags,0u,16u);
    s.di=0u;                                   /* XOR DI,DI */
    s.flags=logic_flags(s.flags,0u,16u);

    for(index=0u;index<sizeof(groups)/sizeof(groups[0]);++index) {
        const EntitySpriteBanksGroup *group=&groups[index];
        s.cx=group->count;                     /* MOV CX,imm */
        for(;;) {
#if ENTITY_SPRITE_BANKS_MUTATION == 2
            uint16_t cached_outer_cx=s.cx;
#endif
            uint16_t call_word=group->return_ip;
            push16(&s,s.cx);                   /* PUSH CX */
            s.dx=group->dx;                    /* MOV DX,imm */
            if(!invoke_child(&s,group->entry,group->return_ip,
                             call_word,group->adapter))
                return result_of(&s);
#if ENTITY_SPRITE_BANKS_MUTATION == 2
            s.sp=(uint16_t)(s.sp+2u);
            s.cx=cached_outer_cx;
#else
            s.cx=pop16(&s);                    /* Live POP CX after CALL. */
#endif
            {
                uint16_t advance=group->source_advance;
                uint16_t before=s.si;
#if ENTITY_SPRITE_BANKS_MUTATION == 4
                if(index==0u)advance=0x29u;
#endif
                s.si=(uint16_t)(s.si+advance);  /* ADD SI,byte immediate */
                s.flags=add16_flags(s.flags,before,advance);
            }
            s.cx=(uint16_t)(s.cx-1u);           /* LOOP decrements without flags. */
            if(s.cx==0u)break;
        }
    }

    {
        uint16_t call_word=0x5abbu;
#if ENTITY_SPRITE_BANKS_MUTATION == 6
        call_word=0x5abcu;
#endif
        if(!invoke_child(&s,CS_GenerateFiveByteSpriteBanks,0x5abbu,
                         call_word,lmn_generate_sprite_shift_banks5_adapter))
            return result_of(&s);
    }
    {
        uint16_t before=s.si;
        s.si=(uint16_t)(s.si+0x0180u);          /* ADD SI,180h */
        s.flags=add16_flags(s.flags,before,0x0180u);
    }
#if ENTITY_SPRITE_BANKS_MUTATION == 7
    s.sp=(uint16_t)(s.sp+2u);
    s.ds=cached_saved_ds;
#else
    s.ds=pop16(&s);                            /* POP DS; actual SS save. */
#endif
    s.continuation=CS_EntitySpriteBanksReturn;
    s.status=LMN_ENTITY_SPRITE_BANKS_READY;
    return result_of(&s);
}

static void regs_from_result(const LmnEntitySpriteBanksResult *s,LmnRegs *r) {
    r->ax=s->ax;r->bx=s->bx;r->cx=s->cx;r->dx=s->dx;
    r->si=s->si;r->di=s->di;r->bp=s->bp;
    r->cs=s->code_segment;r->ds=s->data_segment;r->es=s->extra_segment;
    r->ss=s->stack_segment;r->sp=s->stack_offset;r->flags=s->flags;
    r->ip=s->continuation;
}

uint16_t lmn_generate_entity_sprite_banks_adapter(
    uint8_t *memory,LmnRegs *registers,const LmnRasterBus *bus) {
    LmnEntitySpriteBanksCall call={
        registers->ax,registers->bx,registers->cx,registers->dx,
        registers->si,registers->di,registers->bp,
        registers->cs,registers->ds,registers->es,
        registers->ss,registers->sp,registers->flags
    };
    LmnEntitySpriteBanksResult result;
#if ENTITY_SPRITE_BANKS_MUTATION == 9
    EntitySpriteBanksState prefetch_state;
    uint16_t prefetched_return;
    state_from_call(&prefetch_state,memory,&call,bus);
    prefetched_return=read16(&prefetch_state,registers->ss,
                             registers->sp);
#endif
    result=lmn_generate_entity_sprite_banks_core(memory,&call,bus);
    regs_from_result(&result,registers);
    if(result.status==LMN_ENTITY_SPRITE_BANKS_READY) {
#if ENTITY_SPRITE_BANKS_MUTATION == 10
        /* Mutation: leave the caller's real RET word unconsumed. */
#else
        uint16_t return_word;
#if ENTITY_SPRITE_BANKS_MUTATION == 9
        return_word=prefetched_return;
#else
        EntitySpriteBanksState ret_state;
        state_from_call(&ret_state,memory,&call,bus);
        ret_state.ss=result.stack_segment;
        ret_state.sp=result.stack_offset;
        ret_state.flags=result.flags;
        return_word=read16(&ret_state,result.stack_segment,
                           result.stack_offset);
#endif
        registers->ip=return_word;
        registers->sp=(uint16_t)(result.stack_offset+2u);
#endif
    }
    return result.status;
}

#include "object_animation.h"

#include "lemmings_sym.h"

#ifndef OBJECT_ANIMATION_MUTATION
#define OBJECT_ANIMATION_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct ObjectAnimationState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
} ObjectAnimationState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(ObjectAnimationState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(ObjectAnimationState *s,uint32_t address,
                           uint8_t value,uint16_t flags) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(ObjectAnimationState *s,uint16_t segment,
                     uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(ObjectAnimationState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value,s->flags);
}

static uint16_t read16(ObjectAnimationState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ObjectAnimationState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,s->flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),s->flags);
}

static uint16_t szp8(uint8_t value) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0u;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x80u)out|=SF;
    return out;
}

static uint16_t szp16(uint16_t value) {
    uint16_t out=(uint16_t)(szp8((uint8_t)value)&PF);
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    /* AF is undefined after logical instructions; retain its opaque value. */
    return (uint16_t)((flags&~LOGIC)|szp8(value));
}

static uint16_t logic16_flags(uint16_t flags,uint16_t value) {
    return (uint16_t)((flags&~LOGIC)|szp16(value));
}

static uint16_t sub8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t result=(uint8_t)(left-right);
    uint16_t out=szp8(result);
    if(left<right)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)wide,out=szp16(result);
    if(wide>0xffffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before+1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0x0fu)out|=AF;
    if(before==0x7fu)out|=OF;
    return (uint16_t)((flags&~(PF|AF|ZF|SF|OF))|out|(flags&CF));
}

static uint16_t graphics_field(uint16_t cursor,uint16_t absolute_field) {
    return (uint16_t)(cursor+
        (uint16_t)(absolute_field-SEG09A9_LevelObjectGraphicsRecords));
}

static LmnObjectAnimationResult result_of(const ObjectAnimationState *s) {
    LmnObjectAnimationResult out;
    out.value=s->ax;out.object_flags=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.graphics_cursor=s->si;
    out.definition_cursor=s->di;out.frame_stride=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void initialize(ObjectAnimationState *s,uint8_t *memory,
    const LmnObjectAnimationCall *call,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->object_flags;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->graphics_cursor;
    s->di=call->definition_cursor;s->bp=call->frame_stride;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->status=LMN_OBJECT_ANIMATION_READY;
}

static void advance_records(ObjectAnimationState *s) {
    unsigned iteration;
    s->si=SEG09A9_LevelObjectGraphicsRecords;   /* LEA SI,[records] */
    s->di=SEG09A9_LevelObjectDefinitions;       /* LEA DI,[definitions] */
    s->cx=0x0020u;                              /* MOV CX,20h */

    for(iteration=0u;iteration<0x20u;++iteration) {
        uint8_t x_high=read8(s,s->ds,s->di);    /* MOV AH,[DI] */
        uint8_t x_low=read8(s,s->ds,(uint16_t)(s->di+1u));
        uint16_t definition_x=(uint16_t)(((uint16_t)x_high<<8)|x_low);
        uint8_t zero_x,store_flags_word=0u;
        s->ax=definition_x;
        s->flags=logic16_flags(s->flags,s->ax); /* AND AX,AX */
        zero_x=(uint8_t)(definition_x==0u);

        if(zero_x) {
            store_flags_word=1u;
        } else {
            uint8_t type_low=read8(s,s->ds,(uint16_t)(s->di+5u));
            uint8_t is_type_one=(uint8_t)(type_low==1u);
            s->dx=(uint16_t)((s->dx&0xff00u)|type_low); /* MOV DL,[DI+5] */
#if OBJECT_ANIMATION_MUTATION == 3
            {
                uint8_t type_high=read8(s,s->ds,(uint16_t)(s->di+4u));
                is_type_one=(uint8_t)(type_high==0u&&type_low==1u);
            }
#endif
            s->flags=sub8_flags(s->flags,type_low,1u);  /* CMP DL,1 */
            if(is_type_one) {
                uint8_t gate=read8(s,s->ds,SEG09A9_EntityCreationGate);
                s->flags=sub8_flags(s->flags,gate,0xffu);
                if(gate!=0xffu)goto iteration_end;      /* JNZ 7C5E */
            }

            s->bx=read16(s,s->ds,s->si);                 /* MOV BX,[SI] */
            store_flags_word=1u;
            s->flags=logic16_flags(s->flags,
                (uint16_t)(s->bx&0x0002u));              /* TEST BX,2 */
            if(s->bx&0x0002u) {
#if OBJECT_ANIMATION_MUTATION == 8
                uint16_t cached_base=read16(s,s->ds,
                    graphics_field(s->si,
                        SEG09A9_FirstObjectGraphicsAnimationBase));
#endif
                uint8_t frame=read8(s,s->ds,
                    graphics_field(s->si,
                        SEG09A9_FirstObjectGraphicsAnimationFrame));
                uint8_t limit=read8(s,s->ds,
                    graphics_field(s->si,
                        SEG09A9_FirstObjectGraphicsAnimationLimit));
                uint8_t incremented=(uint8_t)(frame+1u);
#if OBJECT_ANIMATION_MUTATION == 5
                uint16_t widened=(uint16_t)frame+1u;
#endif
                s->ax=(uint16_t)((s->ax&0xff00u)|incremented);
                s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)limit<<8));
                s->flags=inc8_flags(s->flags,frame);     /* INC AL */
                s->flags=sub8_flags(s->flags,incremented,limit);
#if OBJECT_ANIMATION_MUTATION == 5
                if(widened==limit) {
#elif OBJECT_ANIMATION_MUTATION == 4
                if(incremented>=limit) {
#else
                if(incremented==limit) {
#endif
                    s->ax=(uint16_t)(s->ax&0xff00u);    /* XOR AL,AL */
                    s->flags=logic8_flags(s->flags,0u);
                    s->flags=logic16_flags(s->flags,
                        (uint16_t)(s->bx&0x0001u));      /* TEST BX,1 */
                    if(s->bx&0x0001u) {
#if OBJECT_ANIMATION_MUTATION != 6
                        s->bx=(uint16_t)(s->bx&0xfffdu);
                        s->flags=logic16_flags(s->flags,s->bx);
#endif
                    }
                }
                write8(s,s->ds,graphics_field(s->si,
                    SEG09A9_FirstObjectGraphicsAnimationFrame),
                    (uint8_t)s->ax);                    /* MOV [SI+2],AL */

                s->ax=(uint16_t)(s->ax&0x00ffu);          /* XOR AH,AH */
                s->flags=logic8_flags(s->flags,0u);
                s->bp=read16(s,s->ds,graphics_field(s->si,
                    SEG09A9_FirstObjectGraphicsFrameStride));
                {
                    uint32_t product=(uint32_t)s->ax*(uint32_t)s->bp;
                    uint16_t high=(uint16_t)(product>>16);
                    s->ax=(uint16_t)product;
#if OBJECT_ANIMATION_MUTATION == 7
                    s->dx=0u;
#else
                    s->dx=high;
#endif
                    /* MUL sets only CF/OF deterministically in this model. */
                    s->flags=(uint16_t)((s->flags&~(CF|OF))|
                        (high?CF|OF:0u));
                }
                {
#if OBJECT_ANIMATION_MUTATION == 8
                    uint16_t base=cached_base;
#else
                    uint16_t base=read16(s,s->ds,graphics_field(s->si,
                        SEG09A9_FirstObjectGraphicsAnimationBase));
#endif
                    uint16_t before=s->ax;
                    s->ax=(uint16_t)(before+base);
                    s->flags=add16_flags(s->flags,before,base);
                }
                write16(s,s->ds,graphics_field(s->si,
                    SEG09A9_FirstObjectGraphicsFrameOffset),s->ax);
            }
        }
        if(zero_x&&OBJECT_ANIMATION_MUTATION==2) {
            s->bx=0u;                                     /* break stale BX */
        }

        /* MOV [SI],BX is reached for zero X or after the record-flag test. */
        if(store_flags_word)write16(s,s->ds,s->si,s->bx);

iteration_end:
        {
            uint16_t before=s->di;
            s->di=(uint16_t)(before+8u);
            s->flags=add16_flags(s->flags,before,8u);    /* ADD DI,8 */
        }
        {
            uint16_t before=s->si;
            s->si=(uint16_t)(before+0x001cu);
            s->flags=add16_flags(s->flags,before,0x001cu);/* ADD SI,1C */
        }
        s->cx=(uint16_t)(s->cx-1u);                     /* LOOP, flags kept */
    }
    s->continuation=CS_ObjectAnimationReturn;
}

LmnObjectAnimationResult lmn_advance_level_object_animation_records_core(
    uint8_t *memory,const LmnObjectAnimationCall *call,
    const LmnRasterBus *bus) {
    ObjectAnimationState s;
    initialize(&s,memory,call,bus);
    advance_records(&s);
    return result_of(&s);
}

LmnObjectAnimationResult lmn_advance_level_object_animations_core(
    uint8_t *memory,const LmnObjectAnimationCall *call,
    const LmnRasterBus *bus) {
    ObjectAnimationState s;
    uint8_t gate;
    initialize(&s,memory,call,bus);
    gate=read8(&s,s.ds,SEG09A9_EntityUpdateGate);
    s.flags=sub8_flags(s.flags,gate,0xffu);              /* CMP [002B],FF */
#if OBJECT_ANIMATION_MUTATION == 1
    if(gate!=0xffu) {
#else
    if(gate==0xffu) {
#endif
        s.continuation=CS_ObjectAnimationEarlyReturn;
        return result_of(&s);                           /* before RET 394E */
    }
    advance_records(&s);                                /* JMP 7C0A */
    return result_of(&s);
}

static void apply_result(LmnRegs *r,const LmnObjectAnimationResult *out) {
    r->ax=out->value;r->bx=out->object_flags;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->graphics_cursor;
    r->di=out->definition_cursor;r->bp=out->frame_stride;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;
    r->ip=out->continuation;
}

static uint16_t read_stack_return(uint8_t *memory,uint16_t ss,uint16_t sp,
    uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(ss,sp);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,(address+1u)&MEMORY_MASK,
                            flags);
    } else {
        low=memory[address];high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

typedef LmnObjectAnimationResult (*ObjectAnimationCore)(uint8_t *,
    const LmnObjectAnimationCall *,const LmnRasterBus *);

static uint16_t adapter(uint8_t *memory,LmnRegs *r,const LmnRasterBus *bus,
                        ObjectAnimationCore core) {
    LmnObjectAnimationCall call;
    LmnObjectAnimationResult out;
    call.value=r->ax;call.object_flags=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.graphics_cursor=r->si;
    call.definition_cursor=r->di;call.frame_stride=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_OBJECT_ANIMATION_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

uint16_t lmn_advance_level_object_animations_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    return adapter(memory,r,bus,lmn_advance_level_object_animations_core);
}

uint16_t lmn_advance_level_object_animation_records_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    return adapter(memory,r,bus,
        lmn_advance_level_object_animation_records_core);
}

#include "object_drawing_tick.h"

#include "lemmings_sym.h"

#ifndef OBJECT_DRAWING_TICK_MUTATION
#define OBJECT_DRAWING_TICK_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct ObjectDrawingTickState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags,game_data_segment;
    uint16_t continuation,status;
} ObjectDrawingTickState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(ObjectDrawingTickState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(ObjectDrawingTickState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(ObjectDrawingTickState *s,uint16_t segment,
                     uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static uint16_t read16(ObjectDrawingTickState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(ObjectDrawingTickState *s,uint16_t segment,
                    uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static uint16_t szp8(uint8_t value) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
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
    /* XOR/AND AF is undefined; preserve its incoming representative. */
    return (uint16_t)((flags&~LOGIC)|szp8(value));
}

static uint16_t logic16_flags(uint16_t flags,uint16_t value) {
    return (uint16_t)((flags&~LOGIC)|szp16(value));
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)wide,out=szp16(result);
    if(wide>0xffffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

#if OBJECT_DRAWING_TICK_MUTATION != 1
static uint16_t sub16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint16_t result=(uint16_t)(left-right),out=szp16(result);
    if(left<right)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}
#endif

static void push_word(ObjectDrawingTickState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop_word(ObjectDrawingTickState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static LmnObjectDrawingTickResult result_of(
    const ObjectDrawingTickState *s) {
    LmnObjectDrawingTickResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.game_data_segment=s->game_data_segment;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

static int complete_byte_ports(const LmnRasterBytePorts *ports) {
    return ports&&ports->out_byte&&ports->in_byte;
}

LmnObjectDrawingTickResult lmn_draw_level_object_graphics_core(
    uint8_t *memory,const LmnObjectDrawingTickCall *call,
    const LmnRasterBus *bus,const LmnRasterBytePorts *ports) {
    ObjectDrawingTickState s;
    const LmnRasterBytePorts *child_ports=complete_byte_ports(ports)?ports:NULL;

    s.memory=memory;s.bus=bus;
    s.ax=call->value;s.bx=call->map_cursor;s.cx=0x0020u;
    s.dx=call->auxiliary_value;s.si=SEG09A9_LevelObjectGraphicsRecords;
    s.di=SEG09A9_LevelObjectDefinitions;s.bp=call->candidate_y;
    s.cs=call->code_segment;s.ds=call->data_segment;
    s.es=call->extra_segment;s.ss=call->stack_segment;
    s.sp=call->stack_offset;s.flags=call->flags;
    s.game_data_segment=call->game_data_segment;
    s.continuation=CS_DrawLevelObjectGraphics;s.status=LMN_OBJECT_DRAWING_TICK_READY;

    for(;;) {
        uint8_t x_high=read8(&s,s.ds,s.di);
        uint8_t x_low=read8(&s,s.ds,(uint16_t)(s.di+1u));
        s.ax=(uint16_t)(((uint16_t)x_high<<8)|x_low); /* MOV AH/AL */
        s.flags=logic16_flags(s.flags,s.ax);           /* AND AX,AX */

        if(s.ax!=0u) {
#if OBJECT_DRAWING_TICK_MUTATION == 4
            uint16_t saved_cx=s.cx,saved_di=s.di,saved_si=s.si;
#endif
#if OBJECT_DRAWING_TICK_MUTATION != 1
            uint16_t scroll;
#endif
            uint16_t control_mask;
            uint16_t child_ip,child_cs;

            /* PUSH CX, DI, SI writes use live SS:SP in source order. */
            push_word(&s,s.cx);
            push_word(&s,s.di);
            push_word(&s,s.si);

#if OBJECT_DRAWING_TICK_MUTATION == 1
            /* Fault omits the live DS:0000 scroll subtraction. */
#else
            scroll=read16(&s,s.ds,SEG09A9_LevelViewOriginPixels);
            {
                uint16_t before=s.ax;
                s.ax=(uint16_t)(before-scroll);
                s.flags=sub16_flags(s.flags,before,scroll);
            }
#endif
            {
                uint16_t before=s.ax;
                s.ax=(uint16_t)(before+0x0010u);        /* ADD AX,10h */
                s.flags=add16_flags(s.flags,before,0x0010u);
            }

            /* MOV BH/BL and DH/DL load live big-endian definition bytes. */
            s.bx=(uint16_t)((s.bx&0x00ffu)|
                ((uint16_t)read8(&s,s.ds,(uint16_t)(s.di+2u))<<8));
            s.bx=(uint16_t)((s.bx&0xff00u)|
                read8(&s,s.ds,(uint16_t)(s.di+3u)));
            s.dx=(uint16_t)((s.dx&0x00ffu)|
                ((uint16_t)read8(&s,s.ds,(uint16_t)(s.di+6u))<<8));
            s.dx=(uint16_t)((s.dx&0xff00u)|
                read8(&s,s.ds,(uint16_t)(s.di+7u)));

            s.bp=s.dx;                               /* MOV BP,DX */
            control_mask=(uint16_t)(s.bp&0xfffeu);    /* AND BP,-2 */
            s.flags=logic16_flags(s.flags,control_mask);
            s.bp=control_mask;
#if OBJECT_DRAWING_TICK_MUTATION == 2
            s.bp=s.dx;                                /* retain bit 0 only */
#endif

            {
                uint8_t width=read8(&s,s.ds,(uint16_t)(s.si+4u));
                s.dx=(uint16_t)((s.dx&0xff00u)|width);
            }
            /* XOR DH,DH sets DH=0 and updates the live arithmetic flags. */
            s.dx=(uint16_t)(s.dx&0x00ffu);
            s.flags=logic8_flags(s.flags,0u);
            {
                uint8_t height=read8(&s,s.ds,(uint16_t)(s.si+5u));
                s.cx=(uint16_t)((s.cx&0xff00u)|height); /* MOV CL,[SI+5] */
            }
            s.di=read16(&s,s.ds,(uint16_t)(s.si+8u));    /* MOV DI,[SI+8] */
            s.si=read16(&s,s.ds,(uint16_t)(s.si+0x17u)); /* MOV SI,[SI+17] */
            {
                uint16_t before=s.di;
                s.di=(uint16_t)(before+s.si);           /* ADD DI,SI */
                s.flags=add16_flags(s.flags,before,s.si);
            }
            s.cx=(uint16_t)((s.cx&0x00ffu)|0x0400u);     /* MOV CH,4 */

            /* CALL FAR 0000:8822 pushes the real caller CS and 7BFE IP. */
            push_word(&s,s.cs);
            push_word(&s,CS_DrawLevelObjectGraphicsAfterBitmap);
            {
                LmnPlanarBitmapCall child_call;
                LmnDrawingRenderResult child;
                child_call.data_segment=s.ds;
                child_call.game_data_segment=s.game_data_segment;
                child_call.stack_segment=s.ss;
                child_call.stack_offset=s.sp;
                child_call.left=s.ax;child_call.top=s.bx;
                child_call.packed_height=s.cx;child_call.width=s.dx;
                child_call.source_cursor=s.si;
                child_call.destination_cursor=s.di;
                child_call.control=s.bp;child_call.output_segment=s.es;
                child_call.flags=s.flags;
                child=lmn_draw_planar_bitmap_core(memory,&child_call,bus,
                                                   child_ports);

                s.ax=child.plan.state.work_value;
                s.bx=child.plan.state.second_source_cursor;
                s.cx=child.plan.state.packed_counts;
                s.dx=child.plan.state.width_state;
                s.si=child.plan.state.source_cursor;
                s.di=child.plan.state.destination_cursor;
                s.bp=child.plan.state.control;
                s.ds=child.source_segment;s.es=child.output_segment;
                s.sp=child.plan.state.stack_offset;
                s.flags=child.plan.state.flags;
                s.continuation=child.plan.state.continuation;

                if(!child.body_returned) {
#if OBJECT_DRAWING_TICK_MUTATION == 6
                    /* Fault swallows a child boundary as the parent's RET;
                       preserve the live unfinished child/far-call stack. */
                    s.continuation=CS_DrawLevelObjectGraphicsReturn;
                    s.status=LMN_OBJECT_DRAWING_TICK_READY;
                    return result_of(&s);
#else
                    if(child.plan.changed_return) {
                        s.status=LMN_OBJECT_DRAWING_TICK_CHANGED_CHILD_NEAR;
                    } else if(!child_ports&&
                        child.plan.state.continuation==
                            CS_PlanarAlignedMasked4000Body) {
                        s.status=LMN_OBJECT_DRAWING_TICK_MISSING_PROVIDER;
                    } else {
                        s.status=LMN_OBJECT_DRAWING_TICK_CHILD_BOUNDARY;
                    }
                    return result_of(&s);
#endif
                }
            }

            /* RETF consumes live IP then CS before the caller's POPs. */
            child_ip=pop_word(&s);
            child_cs=pop_word(&s);
            s.cs=child_cs;
            if(child_ip!=CS_DrawLevelObjectGraphicsAfterBitmap||
               child_cs!=call->code_segment) {
#if OBJECT_DRAWING_TICK_MUTATION != 5
                s.continuation=child_ip;
                s.status=LMN_OBJECT_DRAWING_TICK_CHANGED_FAR_RETURN;
                return result_of(&s);
#else
                /* Fault ignores the changed RETF target and resumes here. */
                s.cs=call->code_segment;
#endif
            }
            s.continuation=CS_DrawLevelObjectGraphicsAfterBitmap;

            /* POP SI / DI / CX reread the real live stack after RETF. */
            s.si=pop_word(&s);s.di=pop_word(&s);s.cx=pop_word(&s);
#if OBJECT_DRAWING_TICK_MUTATION == 4
            s.si=saved_si;s.di=saved_di;s.cx=saved_cx;
#endif
#if OBJECT_DRAWING_TICK_MUTATION == 3
            s.ds=call->data_segment;
#endif
        }

        {
            uint16_t before=s.di;
            s.di=(uint16_t)(before+8u);                /* ADD DI,8 */
            s.flags=add16_flags(s.flags,before,8u);
        }
        {
            uint16_t before=s.si;
            s.si=(uint16_t)(before+0x001cu);            /* ADD SI,1C */
            s.flags=add16_flags(s.flags,before,0x001cu);
        }
        s.cx=(uint16_t)(s.cx-1u);                       /* LOOP preserves FLAGS */
        if(s.cx==0u) {
            s.continuation=CS_DrawLevelObjectGraphicsReturn;
            s.status=LMN_OBJECT_DRAWING_TICK_READY;
            return result_of(&s);
        }
        s.continuation=CS_DrawLevelObjectGraphics;
    }
}

static void apply_result(LmnRegs *r,const LmnObjectDrawingTickResult *out) {
    r->ax=out->value;r->bx=out->map_cursor;r->cx=out->count;
    r->dx=out->auxiliary_value;r->si=out->record_cursor;
    r->di=out->object_cursor;r->bp=out->candidate_y;
    r->cs=out->code_segment;r->ds=out->data_segment;
    r->es=out->extra_segment;r->ss=out->stack_segment;
    r->sp=out->stack_offset;r->flags=out->flags;r->ip=out->continuation;
}

static uint16_t read_stack_return(uint8_t *memory,uint16_t ss,uint16_t sp,
                                  uint16_t flags,const LmnRasterBus *bus) {
    uint32_t address=physical(ss,sp);
    uint8_t low,high;
    if(bus&&bus->read_byte) {
        low=bus->read_byte(bus->context,memory,address,flags);
        high=bus->read_byte(bus->context,memory,(address+1u)&MEMORY_MASK,flags);
    } else {
        low=memory[address];high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

uint16_t lmn_draw_level_object_graphics_adapter(uint8_t *memory,LmnRegs *r,
    uint16_t game_data_segment,const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    LmnObjectDrawingTickCall call;
    LmnObjectDrawingTickResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    call.game_data_segment=game_data_segment;
    out=lmn_draw_level_object_graphics_core(memory,&call,bus,ports);
    apply_result(r,&out);
    if(out.status==LMN_OBJECT_DRAWING_TICK_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

#include "entity_strip.h"

#include "lemmings_sym.h"

#ifndef ENTITY_STRIP_MUTATION
#define ENTITY_STRIP_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF
};

typedef struct EntityStripState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status;
} EntityStripState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(EntityStripState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(EntityStripState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(EntityStripState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(EntityStripState *s,uint16_t segment,uint16_t offset,
                   uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(EntityStripState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(EntityStripState *s,uint16_t segment,uint16_t offset,
                    uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
}

static uint16_t szp16(uint16_t value) {
    unsigned parity=0u,bit;
    uint16_t out=0u;
    for(bit=0u;bit<8u;++bit)parity^=(value>>bit)&1u;
    if(!parity)out|=PF;
    if(value==0u)out|=ZF;
    if(value&0x8000u)out|=SF;
    return out;
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right) {
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    uint16_t result=(uint16_t)wide,out=szp16(result);
    if(wide>0xffffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x8000u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
}

static void write_out(EntityStripState *s) {
    if(s->bus&&s->bus->out_word)
        s->bus->out_word(s->bus->context,s->dx,s->ax,s->flags);
}

static void push_word(EntityStripState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop_word(EntityStripState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void set_al(EntityStripState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(EntityStripState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void write_mirror_and_out(EntityStripState *s,uint16_t offset) {
#if ENTITY_STRIP_MUTATION == 6
    write_out(s);
    write16(s,s->ss,offset,s->ax);
#else
    write16(s,s->ss,offset,s->ax);
    write_out(s);
#endif
}

static void stosb(EntityStripState *s) {
    int direction=(s->flags&DF)?-1:1;
#if ENTITY_STRIP_MUTATION == 2
    direction=1;
#endif
    write8(s,s->es,s->di,(uint8_t)s->ax);
    s->di=(uint16_t)(s->di+direction);
}

static LmnEntityStripResult result_of(const EntityStripState *s) {
    LmnEntityStripResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    return out;
}

static void initialize_state(EntityStripState *s,uint8_t *memory,
    const LmnEntityStripCall *call,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=CS_DrawEntityTwoByteStrip;
    s->status=LMN_ENTITY_STRIP_READY;
}

LmnEntityStripResult lmn_draw_entity_two_byte_strip_core(
    uint8_t *memory,const LmnEntityStripCall *call,
    const LmnRasterBus *bus) {
    EntityStripState s;
#if ENTITY_STRIP_MUTATION == 8
    uint16_t entry_ds;
#endif
    initialize_state(&s,memory,call,bus);
#if ENTITY_STRIP_MUTATION == 8
    entry_ds=s.ds;
#endif

    s.flags=(uint16_t)(s.flags&~IF);                    /* CLI */
    push_word(&s,s.ds);                                 /* PUSH DS */
    s.dx=0x03c4u;s.ax=0x0f02u;
    write16(&s,s.ss,SEG143E_VgaMapMaskMirror,s.ax);write_out(&s);
    s.dx=0x03ceu;s.ax=0x0300u;
    write16(&s,s.ss,SEG143E_VgaSetResetMirror,s.ax);write_out(&s);
    s.ax=0x0e01u;
    write16(&s,s.ss,SEG143E_VgaEnableSetResetMirror,s.ax);write_out(&s);
    s.ax=0x0005u;
    write16(&s,s.ss,SEG143E_VgaGraphicsModeMirror,s.ax);write_out(&s);
    s.ax=0x0003u;
    write16(&s,s.ss,SEG143E_VgaDataRotateMirror,s.ax);write_out(&s);

#if ENTITY_STRIP_MUTATION == 3
    s.ds=call->data_segment;
#else
    s.ds=s.cx;                                          /* MOV DS,CX */
#endif
    s.cx=0xa000u;s.es=s.cx;                             /* MOV ES,A000 */
    s.bp=s.di;                                          /* MOV BP,DI */
    s.cx=0x0008u;                                       /* MOV CX,8 */

    do {
        uint16_t source_word;
#if ENTITY_STRIP_MUTATION != 1
        int lods_direction=(s.flags&DF)?-2:2;
#endif
        push_word(&s,s.cx);                             /* PUSH CX */
#if ENTITY_STRIP_MUTATION != 4
        set_al(&s,read8(&s,s.es,s.di));                 /* MOV AL,[ES:DI] */
#endif
        source_word=read16(&s,s.ds,s.si);               /* LODSW */
        s.ax=source_word;
#if ENTITY_STRIP_MUTATION == 1
        s.si=(uint16_t)(s.si+2u);
#else
        s.si=(uint16_t)(s.si+lods_direction);
#endif
        s.cx=s.ax;                                      /* MOV CX,AX */
        set_ah(&s,(uint8_t)s.ax);                       /* MOV AH,AL */
        set_al(&s,0x08u);                               /* MOV AL,8 */
        write_mirror_and_out(&s,SEG143E_VgaBitMaskMirror); /* SS:E / OUT */
        set_al(&s,(uint8_t)(s.ax>>8));                  /* MOV AL,AH */
        stosb(&s);                                      /* STOSB low */

#if ENTITY_STRIP_MUTATION != 5
        set_al(&s,read8(&s,s.es,s.di));                 /* unused live read */
#endif
        set_al(&s,0x08u);                               /* MOV AL,8 */
        set_ah(&s,(uint8_t)(s.cx>>8));                  /* MOV AH,CH */
        write_mirror_and_out(&s,SEG143E_VgaBitMaskMirror); /* SS:E / OUT */
        set_al(&s,(uint8_t)(s.ax>>8));                  /* MOV AL,AH */
        stosb(&s);                                      /* STOSB high */
        {
            uint16_t before=s.di;
            s.di=(uint16_t)(before+0x002au);
            s.flags=add16_flags(s.flags,before,0x002au);/* ADD DI,2A */
        }
        s.cx=pop_word(&s);                              /* POP CX */
        s.cx=(uint16_t)(s.cx-1u);                       /* LOOP */
    } while(s.cx!=0u);

#if ENTITY_STRIP_MUTATION != 7
    s.flags=(uint16_t)(s.flags|IF);                     /* STI */
#endif
#if ENTITY_STRIP_MUTATION == 8
    s.ds=entry_ds;
    s.sp=(uint16_t)(s.sp+2u);
#else
    s.ds=pop_word(&s);                                  /* POP DS */
#endif
    s.continuation=CS_EntityTwoByteStripReturn;
    return result_of(&s);
}

static void apply_result(LmnRegs *r,const LmnEntityStripResult *out) {
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
        low=memory[address];
        high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

uint16_t lmn_draw_entity_two_byte_strip_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    LmnEntityStripCall call;
    LmnEntityStripResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_draw_entity_two_byte_strip_core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_ENTITY_STRIP_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

#include "status_display.h"

#include "lemmings_sym.h"
#include "status_count.h"
#include "status_icons.h"
#include "status_text.h"

#ifndef STATUS_DISPLAY_MUTATION
#define STATUS_DISPLAY_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,IF=0x0200u,DF=0x0400u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF,
    INC_ARITH=PF|AF|ZF|SF|OF
};

typedef struct StatusDisplayState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status,child_entry,child_status;
} StatusDisplayState;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(StatusDisplayState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(StatusDisplayState *s,uint32_t address,
                           uint8_t value,uint16_t flags) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(StatusDisplayState *s,uint16_t segment,uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(StatusDisplayState *s,uint16_t segment,uint16_t offset,
                   uint8_t value,uint16_t flags) {
    write_physical(s,physical(segment,offset),value,flags);
}

static uint16_t read16(StatusDisplayState *s,uint16_t segment,uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(StatusDisplayState *s,uint16_t segment,uint16_t offset,
                    uint16_t value,uint16_t flags) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value,flags);
    write_physical(s,address+1u,(uint8_t)(value>>8),flags);
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
    /* AF is undefined after AND/XOR; preserve its opaque value. */
    return (uint16_t)((flags&~LOGIC)|szp8(value));
}

static uint16_t add8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint16_t wide=(uint16_t)left+(uint16_t)right;
    uint8_t result=(uint8_t)wide;
    uint16_t out=szp8(result);
    if(wide>0xffu)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if((~(left^right)&(left^result)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
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

static uint16_t shl16_one_flags(uint16_t flags,uint16_t before) {
    uint16_t result=(uint16_t)(before<<1);
    uint16_t out=szp16(result);
    uint16_t carry=(uint16_t)((before>>15)&1u);
    if(carry)out|=CF;
    if(((result>>15)^carry)&1u)out|=OF;
    return (uint16_t)((flags&~(CF|PF|ZF|SF|OF))|out);
}

static uint16_t inc8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before+1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0x0fu)out|=AF;
    if(before==0x7fu)out|=OF;
    return (uint16_t)((flags&~INC_ARITH)|out|(flags&CF));
}

static uint16_t dec8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before-1u);
    uint16_t out=szp8(result);
    if((before&0x0fu)==0u)out|=AF;
    if(before==0x80u)out|=OF;
    return (uint16_t)((flags&~INC_ARITH)|out|(flags&CF));
}

static uint8_t al(const StatusDisplayState *s) {
    return (uint8_t)s->ax;
}

static uint8_t ah(const StatusDisplayState *s) {
    return (uint8_t)(s->ax>>8);
}

static void set_al(StatusDisplayState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(StatusDisplayState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void push_word(StatusDisplayState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value,s->flags);
}

static uint16_t pop_word(StatusDisplayState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static void inc_memory_byte(StatusDisplayState *s,uint16_t offset) {
    uint8_t before=read8(s,s->ds,offset);
    uint8_t after=(uint8_t)(before+1u);
    uint16_t after_flags=inc8_flags(s->flags,before);
    /* Both RMW accesses expose instruction-entry flags on the raster bus. */
    write8(s,s->ds,offset,after,s->flags);
    s->flags=after_flags;
}

static uint16_t compare_snapshot_flags(uint16_t flags,uint8_t snapshot,
                                       uint8_t live) {
    return sub8_flags(flags,snapshot,live);
}

static LmnStatusDisplayResult result_of(const StatusDisplayState *s) {
    LmnStatusDisplayResult out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    out.continuation=s->continuation;out.status=s->status;
    out.child_entry=s->child_entry;out.child_status=s->child_status;
    return out;
}

static void take_text(StatusDisplayState *s,const LmnStatusTextResult *out) {
    s->ax=out->value;s->bx=out->map_cursor;s->cx=out->count;
    s->dx=out->auxiliary_value;s->si=out->record_cursor;
    s->di=out->object_cursor;s->bp=out->candidate_y;
    s->cs=out->code_segment;s->ds=out->data_segment;
    s->es=out->extra_segment;s->ss=out->stack_segment;
    s->sp=out->stack_offset;s->flags=out->flags;
    s->continuation=out->continuation;
}

static void take_icons(StatusDisplayState *s,const LmnStatusIconsResult *out) {
    s->ax=out->value;s->bx=out->map_cursor;s->cx=out->count;
    s->dx=out->auxiliary_value;s->si=out->record_cursor;
    s->di=out->object_cursor;s->bp=out->candidate_y;
    s->cs=out->code_segment;s->ds=out->data_segment;
    s->es=out->extra_segment;s->ss=out->stack_segment;
    s->sp=out->stack_offset;s->flags=out->flags;
    s->continuation=out->continuation;
}

static void take_count(StatusDisplayState *s,const LmnStatusCountResult *out) {
    s->ax=out->value;s->bx=out->map_cursor;s->cx=out->count;
    s->dx=out->auxiliary_value;s->si=out->record_cursor;
    s->di=out->object_cursor;s->bp=out->candidate_y;
    s->cs=out->code_segment;s->ds=out->data_segment;
    s->es=out->extra_segment;s->ss=out->stack_segment;
    s->sp=out->stack_offset;s->flags=out->flags;
    s->continuation=out->continuation;
}

static void child_stop(StatusDisplayState *s,uint16_t entry,
                       uint16_t child_status,uint16_t continuation,
                       uint16_t parent_status) {
    s->child_entry=entry;s->child_status=child_status;
    s->continuation=continuation;s->status=parent_status;
}

static LmnStatusTextCall text_call_from_state(const StatusDisplayState *s) {
    LmnStatusTextCall call;
    call.value=s->ax;call.map_cursor=s->bx;call.count=s->cx;
    call.auxiliary_value=s->dx;call.record_cursor=s->si;
    call.object_cursor=s->di;call.candidate_y=s->bp;
    call.code_segment=s->cs;call.data_segment=s->ds;
    call.extra_segment=s->es;call.stack_segment=s->ss;
    call.stack_offset=s->sp;call.flags=s->flags;
    return call;
}

static LmnStatusIconsCall icons_call_from_state(const StatusDisplayState *s) {
    LmnStatusIconsCall call;
    call.value=s->ax;call.map_cursor=s->bx;call.count=s->cx;
    call.auxiliary_value=s->dx;call.record_cursor=s->si;
    call.object_cursor=s->di;call.candidate_y=s->bp;
    call.code_segment=s->cs;call.data_segment=s->ds;
    call.extra_segment=s->es;call.stack_segment=s->ss;
    call.stack_offset=s->sp;call.flags=s->flags;
    return call;
}

static LmnStatusCountCall count_call_from_state(const StatusDisplayState *s) {
    LmnStatusCountCall call;
    call.value=s->ax;call.map_cursor=s->bx;call.count=s->cx;
    call.auxiliary_value=s->dx;call.record_cursor=s->si;
    call.object_cursor=s->di;call.candidate_y=s->bp;
    call.code_segment=s->cs;call.data_segment=s->ds;
    call.extra_segment=s->es;call.stack_segment=s->ss;
    call.stack_offset=s->sp;call.flags=s->flags;
    return call;
}

static int return_from_child(StatusDisplayState *s,uint16_t entry,
    uint16_t child_status,uint16_t expected_target,uint16_t expected_code,
    uint16_t parent_status) {
    uint16_t actual_target=pop_word(s);
    s->continuation=actual_target;
#if STATUS_DISPLAY_MUTATION == 7
    (void)entry;(void)child_status;(void)parent_status;
#endif
    if(actual_target!=expected_target||s->cs!=expected_code) {
#if STATUS_DISPLAY_MUTATION == 7
        s->continuation=expected_target;
        return 1;
#else
        child_stop(s,entry,child_status,actual_target,parent_status);
        return 0;
#endif
    }
    s->continuation=expected_target;
    return 1;
}

static int call_text(StatusDisplayState *s,uint16_t parent_target) {
    const uint16_t entry=CS_DrawStatusText;
    uint16_t expected_code=s->cs;
#if STATUS_DISPLAY_MUTATION == 8
    uint16_t entry_ds=s->ds;
#endif
    LmnStatusTextCall call;
    LmnStatusTextResult out;
    push_word(s,parent_target);
    call=text_call_from_state(s);
    out=lmn_draw_status_text_core(s->memory,&call,s->bus);
    take_text(s,&out);
#if STATUS_DISPLAY_MUTATION == 8
    s->ds=entry_ds;
#endif
    if(out.status!=LMN_STATUS_TEXT_READY) {
        child_stop(s,entry,out.status,out.continuation,
                   LMN_STATUS_DISPLAY_CHILD_STOP);
        return 0;
    }
    if(out.continuation!=CS_StatusTextReturn) {
        child_stop(s,entry,out.status,out.continuation,
                   LMN_STATUS_DISPLAY_UNEXPECTED_CHILD_BOUNDARY);
        return 0;
    }
    if(!return_from_child(s,entry,out.status,parent_target,expected_code,
                          LMN_STATUS_DISPLAY_CHANGED_CHILD_RETURN))return 0;
    return 1;
}

static int call_icon_outline(StatusDisplayState *s,uint16_t parent_target) {
    const uint16_t entry=CS_DrawStatusIconOutline;
    uint16_t expected_code=s->cs;
#if STATUS_DISPLAY_MUTATION == 8
    uint16_t entry_ds=s->ds;
#endif
    LmnStatusIconsCall call;
    LmnStatusIconsResult out;
    push_word(s,parent_target);
    call=icons_call_from_state(s);
    out=lmn_draw_status_icon_outline_core(s->memory,&call,s->bus);
    take_icons(s,&out);
#if STATUS_DISPLAY_MUTATION == 8
    s->ds=entry_ds;
#endif
    if(out.status!=LMN_STATUS_ICONS_READY) {
        child_stop(s,entry,out.status,out.continuation,
                   LMN_STATUS_DISPLAY_CHILD_STOP);
        return 0;
    }
    if(out.continuation!=CS_StatusIconOutlineReturn) {
        child_stop(s,entry,out.status,out.continuation,
                   LMN_STATUS_DISPLAY_UNEXPECTED_CHILD_BOUNDARY);
        return 0;
    }
    if(!return_from_child(s,entry,out.status,parent_target,expected_code,
                          LMN_STATUS_DISPLAY_CHANGED_CHILD_RETURN))return 0;
    return 1;
}

static int call_icon_restore(StatusDisplayState *s,uint16_t parent_target) {
    const uint16_t entry=CS_RestoreStatusIcon;
    uint16_t expected_code=s->cs;
#if STATUS_DISPLAY_MUTATION == 8
    uint16_t entry_ds=s->ds;
#endif
    LmnStatusIconsCall call;
    LmnStatusIconsResult out;
    push_word(s,parent_target);
    call=icons_call_from_state(s);
    out=lmn_restore_status_icon_core(s->memory,&call,s->bus);
    take_icons(s,&out);
#if STATUS_DISPLAY_MUTATION == 8
    s->ds=entry_ds;
#endif
    if(out.status!=LMN_STATUS_ICONS_READY) {
        child_stop(s,entry,out.status,out.continuation,
                   LMN_STATUS_DISPLAY_CHILD_STOP);
        return 0;
    }
    if(out.continuation!=CS_StatusIconRestoreReturn) {
        child_stop(s,entry,out.status,out.continuation,
                   LMN_STATUS_DISPLAY_UNEXPECTED_CHILD_BOUNDARY);
        return 0;
    }
    if(!return_from_child(s,entry,out.status,parent_target,expected_code,
                          LMN_STATUS_DISPLAY_CHANGED_CHILD_RETURN))return 0;
    return 1;
}

static int call_count(StatusDisplayState *s,uint16_t parent_target) {
    const uint16_t entry=CS_DrawStatusCount;
    uint16_t expected_code=s->cs;
#if STATUS_DISPLAY_MUTATION == 8
    uint16_t entry_ds=s->ds;
#endif
    LmnStatusCountCall call;
    LmnStatusCountResult out;
    push_word(s,parent_target);
    call=count_call_from_state(s);
    out=lmn_draw_status_count_core(s->memory,&call,s->bus);
    take_count(s,&out);
#if STATUS_DISPLAY_MUTATION == 8
    s->ds=entry_ds;
#endif
    if(out.status!=LMN_STATUS_COUNT_READY) {
        child_stop(s,entry,out.status,out.continuation,
                   LMN_STATUS_DISPLAY_CHILD_STOP);
        return 0;
    }
    if(out.continuation!=CS_StatusCountReturn&&
       out.continuation!=CS_StatusCountBlankReturn) {
        child_stop(s,entry,out.status,out.continuation,
                   LMN_STATUS_DISPLAY_UNEXPECTED_CHILD_BOUNDARY);
        return 0;
    }
    if(!return_from_child(s,entry,out.status,parent_target,expected_code,
                          LMN_STATUS_DISPLAY_CHANGED_CHILD_RETURN))return 0;
    return 1;
}

static int process_count_block(StatusDisplayState *s,uint16_t value_offset,
    uint16_t snapshot_offset,uint16_t counter_offset,uint8_t slot,
    uint16_t parent_target) {
    uint8_t live=read8(s,s->ds,value_offset);
    set_ah(s,live);
    s->flags=logic8_flags(s->flags,live);                /* AND AH,AH */
    if(live!=0u||STATUS_DISPLAY_MUTATION==4) {
        uint8_t snapshot=read8(s,s->ds,snapshot_offset);
        s->flags=compare_snapshot_flags(s->flags,snapshot,live);
        if(snapshot==live)return 1;                     /* JZ next block */
    }

    {
        uint8_t counter=read8(s,s->ds,counter_offset);
        s->flags=sub8_flags(s->flags,counter,0x02u);     /* CMP counter,2 */
        if(counter==0x02u&&STATUS_DISPLAY_MUTATION!=5) {
            write8(s,s->ds,snapshot_offset,ah(s),s->flags);
            write8(s,s->ds,counter_offset,0xffu,s->flags);
        }
    }
    inc_memory_byte(s,counter_offset);                  /* INC [counter] */
#if STATUS_DISPLAY_MUTATION == 6
    slot=(uint8_t)(slot+1u);                            /* wrong count slot */
#endif
    set_al(s,slot);                                      /* MOV AL,slot */
    return call_count(s,parent_target);
}

static int display_icon(StatusDisplayState *s) {
    uint8_t selector=read8(s,s->ds,SEG09A9_EntityActionSelector);
    uint8_t snapshot=read8(s,s->ds,SEG09A9_StatusIconDisplaySnapshot);
    set_ah(s,selector);                                  /* MOV AH,[0082] */
    s->flags=sub8_flags(s->flags,snapshot,ah(s));         /* CMP [0083],AH */
    if(snapshot==ah(s))return 1;

    set_al(s,read8(s,s->ds,SEG09A9_EntityActionSelector));
    if(!call_icon_outline(s,CS_StatusDisplayAfterIconOutline))return 0;

    {
        uint8_t old_selector=read8(s,s->ds,
                                   SEG09A9_StatusIconDisplaySnapshot);
#if STATUS_DISPLAY_MUTATION == 3
        (void)old_selector;                             /* still perform read */
        set_al(s,snapshot);                              /* stale old icon */
#else
        set_al(s,old_selector);
#endif
    }
    if(!call_icon_restore(s,CS_StatusDisplayAfterIconRestore))return 0;

    {
        uint8_t counter=read8(s,s->ds,SEG09A9_StatusIconRefreshCounter);
        s->flags=sub8_flags(s->flags,counter,0x02u);     /* CMP counter,2 */
        if(counter==0x02u&&STATUS_DISPLAY_MUTATION!=5) {
            set_ah(s,read8(s,s->ds,SEG09A9_EntityActionSelector));
            write8(s,s->ds,SEG09A9_StatusIconDisplaySnapshot,ah(s),s->flags);
            write8(s,s->ds,SEG09A9_StatusIconRefreshCounter,0xffu,s->flags);
        }
    }
    inc_memory_byte(s,SEG09A9_StatusIconRefreshCounter);
    return 1;
}

LmnStatusDisplayResult lmn_update_status_display_suffix_core(uint8_t *memory,
    const LmnStatusDisplayCall *call,const LmnRasterBus *bus) {
    StatusDisplayState s;
    uint16_t product;
    uint8_t divisor;
    s.memory=memory;s.bus=bus;
    s.ax=call->value;s.bx=call->map_cursor;s.cx=call->count;
    s.dx=call->auxiliary_value;s.si=call->record_cursor;
    s.di=call->object_cursor;s.bp=call->candidate_y;
    s.cs=call->code_segment;s.ds=call->data_segment;
    s.es=call->extra_segment;s.ss=call->stack_segment;
    s.sp=call->stack_offset;s.flags=call->flags;
    s.continuation=CS_StatusDisplayReturn;
    s.status=LMN_STATUS_DISPLAY_READY;s.child_entry=0u;
    s.child_status=LMN_STATUS_DISPLAY_NO_CHILD_STATUS;

    /* 3ACE..3AE4: construct 100*the live completion byte in AX. */
    set_al(&s,read8(&s,s.ds,SEG09A9_EntityCompletionCounter));
    set_ah(&s,0u);                                      /* XOR AH,AH */
    s.flags=logic8_flags(s.flags,0u);
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(before<<1);s.flags=shl16_one_flags(s.flags,before);
        before=s.ax;
        s.ax=(uint16_t)(before<<1);s.flags=shl16_one_flags(s.flags,before);
    }
    s.cx=s.ax;                                          /* MOV CX,AX */
    {
        unsigned i;
        for(i=0u;i<3u;++i) {
            uint16_t before=s.ax;
            s.ax=(uint16_t)(before<<1);
            s.flags=shl16_one_flags(s.flags,before);
        }
    }
    {
        uint16_t before=s.cx;
        s.cx=(uint16_t)(before+s.ax);                   /* ADD CX,AX */
        s.flags=add16_flags(s.flags,before,s.ax);
    }
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(before<<1);s.flags=shl16_one_flags(s.flags,before);
    }
    {
        uint16_t before=s.ax;
        s.ax=(uint16_t)(before+s.cx);                   /* ADD AX,CX */
        s.flags=add16_flags(s.flags,before,s.cx);
    }

    divisor=read8(&s,s.ds,SEG09A9_LevelCreationLimit);
    s.cx=(uint16_t)((s.cx&0xff00u)|divisor);            /* MOV CL,[0047] */
    s.flags=logic8_flags(s.flags,divisor);              /* AND CL,CL */
    product=s.ax;
    if(divisor!=0u) {
        uint32_t quotient=(uint32_t)product/divisor;
        uint8_t remainder=(uint8_t)(product%divisor);
        if(quotient>0xffu) {
#if STATUS_DISPLAY_MUTATION == 1
            s.ax=0x00ffu;                                /* clamp DIV overflow */
#else
            s.continuation=CS_StatusDisplayDivide;
            s.status=LMN_STATUS_DISPLAY_DIVIDE_ERROR;
            return result_of(&s);
#endif
        } else {
            s.ax=(uint16_t)(((uint16_t)remainder<<8)|(uint8_t)quotient);
        }
        /* DIV leaves flags undefined; preserve the opaque model value. */
    }

    s.si=(uint16_t)(SEG09A9_StatusPercentDigits+1u);     /* MOV SI,209D */
    set_ah(&s,0u);                                      /* XOR AH,AH */
    s.flags=logic8_flags(s.flags,0u);
    write8(&s,s.ds,SEG09A9_StatusCompletionDisplayValue,al(&s),s.flags);
    s.flags=sub8_flags(s.flags,al(&s),0x64u);            /* CMP AL,64 */
    if(al(&s)==0x64u) {
        write8(&s,s.ds,(uint16_t)(s.si-1u),0x31u,s.flags);
        write8(&s,s.ds,s.si,0x30u,s.flags);
        write8(&s,s.ds,(uint16_t)(s.si+1u),0x30u,s.flags);
    } else {
        for(;;) {
            uint8_t before=ah(&s);
            set_ah(&s,(uint8_t)(before+1u));
            s.flags=inc8_flags(s.flags,before);          /* INC AH */
            before=al(&s);
            set_al(&s,(uint8_t)(before-0x0au));
            s.flags=sub8_flags(s.flags,before,0x0au);    /* SUB AL,0A */
            if(s.flags&CF)break;
        }
        {
            uint8_t before=al(&s);
            set_al(&s,(uint8_t)(before+0x3au));
            s.flags=add8_flags(s.flags,before,0x3au);    /* ADD AL,3A */
        }
        {
            uint8_t before=ah(&s);
            set_ah(&s,(uint8_t)(before-1u));
            s.flags=dec8_flags(s.flags,before);           /* DEC AH */
        }
        s.flags=logic8_flags(s.flags,ah(&s));             /* AND AH,AH */
        if(ah(&s)==0u)set_ah(&s,0xf0u);                  /* MOV AH,F0 */
        {
            uint8_t before=ah(&s);
            set_ah(&s,(uint8_t)(before+0x30u));
            s.flags=add8_flags(s.flags,before,0x30u);    /* ADD AH,30 */
        }
        write8(&s,s.ds,s.si,ah(&s),s.flags);
        write8(&s,s.ds,(uint16_t)(s.si+1u),al(&s),s.flags);
#if STATUS_DISPLAY_MUTATION == 2
        write8(&s,s.ds,(uint16_t)(s.si-1u),0x20u,s.flags);
#endif
    }

    set_ah(&s,0u);                                      /* XOR AH,AH */
    s.flags=logic8_flags(s.flags,0u);
    s.si=0x2083u;                                       /* MOV SI,2083 */
    if(!call_text(&s,CS_StatusDisplayAfterText))return result_of(&s);

    if(!display_icon(&s))return result_of(&s);

    if(!process_count_block(&s,SEG09A9_LevelReleaseSettingMinimum,
        SEG09A9_LevelReleaseMinimumDisplaySnapshot,
        SEG09A9_LevelReleaseMinimumRefreshCounter,0u,0x3b7eu))
        return result_of(&s);
    if(!process_count_block(&s,SEG09A9_LevelReleaseSetting,
        SEG09A9_LevelReleaseSettingDisplaySnapshot,
        SEG09A9_LevelReleaseSettingRefreshCounter,1u,0x3ba5u))
        return result_of(&s);
    if(!process_count_block(&s,SEG09A9_LevelActionCount2,
        SEG09A9_LevelActionCountDisplaySnapshot2,
        SEG09A9_LevelActionCountRefreshCounter2,4u,0x3bccu))
        return result_of(&s);
    if(!process_count_block(&s,SEG09A9_LevelActionCount7,
        SEG09A9_LevelActionCountDisplaySnapshot7,
        SEG09A9_LevelActionCountRefreshCounter7,9u,0x3bf3u))
        return result_of(&s);
    if(!process_count_block(&s,SEG09A9_LevelActionCount0,
        SEG09A9_LevelActionCountDisplaySnapshot0,
        SEG09A9_LevelActionCountRefreshCounter0,2u,0x3c1au))
        return result_of(&s);
    if(!process_count_block(&s,SEG09A9_LevelActionCount4,
        SEG09A9_LevelActionCountDisplaySnapshot4,
        SEG09A9_LevelActionCountRefreshCounter4,6u,0x3c41u))
        return result_of(&s);
    if(!process_count_block(&s,SEG09A9_LevelActionCount3,
        SEG09A9_LevelActionCountDisplaySnapshot3,
        SEG09A9_LevelActionCountRefreshCounter3,5u,0x3c68u))
        return result_of(&s);
    if(!process_count_block(&s,SEG09A9_LevelActionCount5,
        SEG09A9_LevelActionCountDisplaySnapshot5,
        SEG09A9_LevelActionCountRefreshCounter5,7u,0x3c8fu))
        return result_of(&s);
    if(!process_count_block(&s,SEG09A9_LevelActionCount1,
        SEG09A9_LevelActionCountDisplaySnapshot1,
        SEG09A9_LevelActionCountRefreshCounter1,3u,0x3cb6u))
        return result_of(&s);
    if(!process_count_block(&s,SEG09A9_LevelActionCount6,
        SEG09A9_LevelActionCountDisplaySnapshot6,
        SEG09A9_LevelActionCountRefreshCounter6,8u,CS_StatusDisplayReturn))
        return result_of(&s);

    s.continuation=CS_StatusDisplayReturn;
    s.status=LMN_STATUS_DISPLAY_READY;
    return result_of(&s);                               /* before outer RET */
}

static void apply_result(LmnRegs *r,const LmnStatusDisplayResult *out) {
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
        high=bus->read_byte(bus->context,memory,(address+1u)&MEMORY_MASK,
                            flags);
    } else {
        low=memory[address];high=memory[(address+1u)&MEMORY_MASK];
    }
    return (uint16_t)(low|((uint16_t)high<<8));
}

uint16_t lmn_update_status_display_suffix_adapter(uint8_t *memory,
    LmnRegs *r,const LmnRasterBus *bus) {
    LmnStatusDisplayCall call;
    LmnStatusDisplayResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_update_status_display_suffix_core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_STATUS_DISPLAY_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

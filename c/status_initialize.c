#include "status_initialize.h"

#include "decimal_field.h"
#include "lemmings_sym.h"
#include "status_copy.h"
#include "status_count.h"
#include "status_icons.h"

#ifndef STATUS_INITIALIZE_MUTATION
#define STATUS_INITIALIZE_MUTATION 0
#endif

enum {
    MEMORY_MASK=0xfffffu,
    CF=0x0001u,PF=0x0004u,AF=0x0010u,ZF=0x0040u,
    SF=0x0080u,OF=0x0800u,
    ARITH=CF|PF|AF|ZF|SF|OF,
    LOGIC=CF|PF|ZF|SF|OF
};

typedef struct StatusInitializeState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    uint16_t ax,bx,cx,dx,si,di,bp;
    uint16_t cs,ds,es,ss,sp,flags;
    uint16_t continuation,status,child_entry,child_status;
} StatusInitializeState;

typedef struct StatusCountStep {
    uint16_t source_offset,return_offset;
    uint8_t selector;
} StatusCountStep;

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return ((((uint32_t)segment<<4)+offset)&MEMORY_MASK);
}

static uint8_t read_physical(StatusInitializeState *s,uint32_t address) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->read_byte)
        return s->bus->read_byte(s->bus->context,s->memory,address,s->flags);
    return s->memory[address];
}

static void write_physical(StatusInitializeState *s,uint32_t address,
                           uint8_t value) {
    address&=MEMORY_MASK;
    if(s->bus&&s->bus->write_byte)
        s->bus->write_byte(s->bus->context,s->memory,address,value,s->flags);
    else
        s->memory[address]=value;
}

static uint8_t read8(StatusInitializeState *s,uint16_t segment,
                     uint16_t offset) {
    return read_physical(s,physical(segment,offset));
}

static void write8(StatusInitializeState *s,uint16_t segment,
                   uint16_t offset,uint8_t value) {
    write_physical(s,physical(segment,offset),value);
}

static uint16_t read16(StatusInitializeState *s,uint16_t segment,
                       uint16_t offset) {
    uint32_t address=physical(segment,offset);
    uint8_t low=read_physical(s,address);
    uint8_t high=read_physical(s,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static void write16(StatusInitializeState *s,uint16_t segment,
                    uint16_t offset,uint16_t value) {
    uint32_t address=physical(segment,offset);
    write_physical(s,address,(uint8_t)value);
    write_physical(s,address+1u,(uint8_t)(value>>8));
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

static uint16_t logic8_flags(uint16_t flags,uint8_t value) {
    /* AF after XOR is undefined; keep its incoming representative. */
    return (uint16_t)((flags&~LOGIC)|szp8(value));
}

static uint16_t sub8_flags(uint16_t flags,uint8_t left,uint8_t right) {
    uint8_t result=(uint8_t)(left-right);
    uint16_t out=szp8(result);
    if(left<right)out|=CF;
    if((left^right^result)&AF)out|=AF;
    if(((left^right)&(left^result)&0x80u)!=0u)out|=OF;
    return (uint16_t)((flags&~ARITH)|out);
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

static uint16_t neg8_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(0u-before);
    uint16_t out=szp8(result);
    if(before!=0u)out|=CF;
    if(before==0x80u)out|=OF;
    if((before&0x0fu)!=0u)out|=AF;
    return (uint16_t)((flags&~ARITH)|out);
}

#if STATUS_INITIALIZE_MUTATION != 2
static uint16_t shr8_one_flags(uint16_t flags,uint8_t before) {
    uint8_t result=(uint8_t)(before>>1);
    uint16_t out=szp8(result);
    if(before&1u)out|=CF;
    /* OF for SHR by one is the old most-significant bit. */
    if(before&0x80u)out|=OF;
    return (uint16_t)((flags&~(CF|PF|ZF|SF|OF))|out);
}
#endif

static uint8_t al(const StatusInitializeState *s) {
    return (uint8_t)s->ax;
}

static void set_al(StatusInitializeState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0xff00u)|value);
}

static void set_ah(StatusInitializeState *s,uint8_t value) {
    s->ax=(uint16_t)((s->ax&0x00ffu)|((uint16_t)value<<8));
}

static void push_word(StatusInitializeState *s,uint16_t value) {
    s->sp=(uint16_t)(s->sp-2u);
    write16(s,s->ss,s->sp,value);
}

static uint16_t pop_word(StatusInitializeState *s) {
    uint16_t value=read16(s,s->ss,s->sp);
    s->sp=(uint16_t)(s->sp+2u);
    return value;
}

static LmnStatusInitializeResult result_of(const StatusInitializeState *s) {
    LmnStatusInitializeResult out;
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

static void initialize_state(StatusInitializeState *s,uint8_t *memory,
    const LmnStatusInitializeCall *call,const LmnRasterBus *bus) {
    s->memory=memory;s->bus=bus;
    s->ax=call->value;s->bx=call->map_cursor;s->cx=call->count;
    s->dx=call->auxiliary_value;s->si=call->record_cursor;
    s->di=call->object_cursor;s->bp=call->candidate_y;
    s->cs=call->code_segment;s->ds=call->data_segment;
    s->es=call->extra_segment;s->ss=call->stack_segment;
    s->sp=call->stack_offset;s->flags=call->flags;
    s->continuation=CS_InitializeStatusDisplay;
    s->status=LMN_STATUS_INITIALIZE_READY;
    s->child_entry=0u;
    s->child_status=LMN_STATUS_INITIALIZE_NO_CHILD_STATUS;
}

#if STATUS_INITIALIZE_MUTATION != 1
static LmnStatusCopyCall status_copy_call_from_state(
    const StatusInitializeState *s) {
    LmnStatusCopyCall out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    return out;
}

static void take_status_copy(StatusInitializeState *s,
                             const LmnStatusCopyResult *out) {
    s->ax=out->value;s->bx=out->map_cursor;s->cx=out->count;
    s->dx=out->auxiliary_value;s->si=out->record_cursor;
    s->di=out->object_cursor;s->bp=out->candidate_y;
    s->cs=out->code_segment;s->ds=out->data_segment;
    s->es=out->extra_segment;s->ss=out->stack_segment;
    s->sp=out->stack_offset;s->flags=out->flags;
    s->continuation=out->continuation;
}
#endif

static void take_status_count(StatusInitializeState *s,
                              const LmnStatusCountResult *out) {
    s->ax=out->value;s->bx=out->map_cursor;s->cx=out->count;
    s->dx=out->auxiliary_value;s->si=out->record_cursor;
    s->di=out->object_cursor;s->bp=out->candidate_y;
    s->cs=out->code_segment;s->ds=out->data_segment;
    s->es=out->extra_segment;s->ss=out->stack_segment;
    s->sp=out->stack_offset;s->flags=out->flags;
    s->continuation=out->continuation;
}

static LmnStatusCountCall status_count_call_from_state(
    const StatusInitializeState *s) {
    LmnStatusCountCall out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    return out;
}

#if STATUS_INITIALIZE_MUTATION != 7
static void take_status_icons(StatusInitializeState *s,
                              const LmnStatusIconsResult *out) {
    s->ax=out->value;s->bx=out->map_cursor;s->cx=out->count;
    s->dx=out->auxiliary_value;s->si=out->record_cursor;
    s->di=out->object_cursor;s->bp=out->candidate_y;
    s->cs=out->code_segment;s->ds=out->data_segment;
    s->es=out->extra_segment;s->ss=out->stack_segment;
    s->sp=out->stack_offset;s->flags=out->flags;
    s->continuation=out->continuation;
}

static LmnStatusIconsCall status_icons_call_from_state(
    const StatusInitializeState *s) {
    LmnStatusIconsCall out;
    out.value=s->ax;out.map_cursor=s->bx;out.count=s->cx;
    out.auxiliary_value=s->dx;out.record_cursor=s->si;
    out.object_cursor=s->di;out.candidate_y=s->bp;
    out.code_segment=s->cs;out.data_segment=s->ds;
    out.extra_segment=s->es;out.stack_segment=s->ss;
    out.stack_offset=s->sp;out.flags=s->flags;
    return out;
}
#endif

static void stop_at_child(StatusInitializeState *s,uint16_t entry,
    uint16_t child_status,uint16_t continuation) {
    s->child_entry=entry;s->child_status=child_status;
    s->continuation=continuation;
    s->status=LMN_STATUS_INITIALIZE_CHILD_STOP;
}

static int consume_child_return(StatusInitializeState *s,uint16_t entry,
    uint16_t child_status,uint16_t expected_target,uint16_t expected_code) {
    uint16_t actual_target=pop_word(s);
    s->continuation=actual_target;
    if(actual_target!=expected_target||s->cs!=expected_code) {
        s->status=LMN_STATUS_INITIALIZE_CHANGED_CHILD_RETURN;
        s->child_entry=entry;s->child_status=child_status;
        return 0;
    }
    s->continuation=expected_target;
    return 1;
}

static int call_copy_wrapper(StatusInitializeState *s) {
#if STATUS_INITIALIZE_MUTATION == 1
    /* Fault bypasses the initial copy call and continues at 39D1. */
    s->continuation=CS_InitializeStatusAfterCopy;
    return 1;
#else
    const uint16_t entry=CS_CopyStatusRegionToBothDrawingOrigins;
    uint16_t expected_code=s->cs;
    LmnStatusCopyCall call;
    LmnStatusCopyResult out;
    push_word(s,CS_InitializeStatusAfterCopy);          /* CALL 75EF */
    call=status_copy_call_from_state(s);
    out=lmn_copy_status_region_to_both_origins_core(s->memory,&call,s->bus);
    take_status_copy(s,&out);
    if(out.status!=LMN_STATUS_COPY_READY) {
        /* Respect the child's status even when its IP aliases 39D1. */
        stop_at_child(s,entry,out.status,out.continuation);
        return 0;
    }
    if(out.continuation!=CS_StatusCopyReturn) {
        stop_at_child(s,entry,out.status,out.continuation);
        return 0;
    }
    return consume_child_return(s,entry,out.status,
        CS_InitializeStatusAfterCopy,expected_code);
#endif
}

static int call_status_count(StatusInitializeState *s,uint16_t source_offset,
    uint8_t selector,uint16_t parent_target,uint8_t zero_al) {
    const uint16_t entry=CS_DrawStatusCount;
    uint16_t expected_code=s->cs;
    LmnStatusCountCall call;
    LmnStatusCountResult out;
    uint8_t count_value=read8(s,s->ds,source_offset);
    set_ah(s,count_value);                              /* MOV AH,[source] */
    if(zero_al) {
        set_al(s,0u);                                   /* XOR AL,AL */
        s->flags=logic8_flags(s->flags,0u);
    } else {
        set_al(s,selector);                             /* MOV AL,selector */
    }
    push_word(s,parent_target);                         /* CALL 762A */
    call=status_count_call_from_state(s);
    out=lmn_draw_status_count_core(s->memory,&call,s->bus);
    take_status_count(s,&out);
    if(out.status!=LMN_STATUS_COUNT_READY) {
        stop_at_child(s,entry,out.status,out.continuation);
        return 0;
    }
    if(out.continuation!=CS_StatusCountReturn&&
       out.continuation!=CS_StatusCountBlankReturn) {
        stop_at_child(s,entry,out.status,out.continuation);
        return 0;
    }
    return consume_child_return(s,entry,out.status,parent_target,
                                expected_code);
}

static int call_decimal_field(StatusInitializeState *s) {
    const uint16_t entry=CS_WriteDecimalByteField;
    uint16_t expected_code=s->cs;
    LmnDecimalFieldCall call;
    LmnDecimalFieldResult out;
    set_al(s,read8(s,s->ds,SEG09A9_EntityDrawingPassCount)); /* MOV AL,[45] */
    s->si=SEG09A9_StatusEntityCountField;                /* MOV SI,2095 */
    push_word(s,CS_InitializeStatusAfterDecimal);        /* CALL 4B68 */
    call.data_segment=s->ds;call.value=s->ax;
    call.prefix_value=s->bx;call.cursor=s->si;call.flags=s->flags;
    out=lmn_write_decimal_field_core(s->memory,&call,s->bus);
    s->ax=out.value;s->bx=out.prefix_value;s->si=out.cursor;
    s->flags=out.flags;s->continuation=CS_DecimalFieldReturn;
    return consume_child_return(s,entry,LMN_STATUS_INITIALIZE_NO_CHILD_STATUS,
        CS_InitializeStatusAfterDecimal,expected_code);
}

static int call_status_icon_outline(StatusInitializeState *s) {
#if STATUS_INITIALIZE_MUTATION == 7
    /* Keep the preceding selector load but omit CALL 780D. */
    set_al(s,read8(s,s->ds,SEG09A9_EntityActionSelector));
    s->continuation=CS_InitializeStatusReturn;
    return 1;
#else
    const uint16_t entry=CS_DrawStatusIconOutline;
    uint16_t expected_code=s->cs;
    LmnStatusIconsCall call;
    LmnStatusIconsResult out;
    set_al(s,read8(s,s->ds,SEG09A9_EntityActionSelector));
    push_word(s,CS_InitializeStatusReturn);             /* CALL 780D */
    call=status_icons_call_from_state(s);
    out=lmn_draw_status_icon_outline_core(s->memory,&call,s->bus);
    take_status_icons(s,&out);
    if(out.status!=LMN_STATUS_ICONS_READY) {
        stop_at_child(s,entry,out.status,out.continuation);
        return 0;
    }
    if(out.continuation!=CS_StatusIconOutlineReturn) {
        stop_at_child(s,entry,out.status,out.continuation);
        return 0;
    }
    return consume_child_return(s,entry,out.status,
        CS_InitializeStatusReturn,expected_code);
#endif
}

LmnStatusInitializeResult lmn_initialize_status_display_core(
    uint8_t *memory,const LmnStatusInitializeCall *call,
    const LmnRasterBus *bus) {
    static const uint16_t counter_offsets[11]={
        SEG09A9_LevelReleaseMinimumRefreshCounter,
        SEG09A9_LevelReleaseSettingRefreshCounter,
        SEG09A9_LevelActionCountRefreshCounter2,
        SEG09A9_LevelActionCountRefreshCounter7,
        SEG09A9_LevelActionCountRefreshCounter0,
        SEG09A9_LevelActionCountRefreshCounter4,
        SEG09A9_LevelActionCountRefreshCounter3,
        SEG09A9_LevelActionCountRefreshCounter5,
        SEG09A9_LevelActionCountRefreshCounter1,
        SEG09A9_LevelActionCountRefreshCounter6,
        SEG09A9_StatusIconRefreshCounter
    };
    static const uint16_t snapshot_offsets[11]={
        SEG09A9_LevelReleaseMinimumDisplaySnapshot,
        SEG09A9_LevelReleaseSettingDisplaySnapshot,
        SEG09A9_LevelActionCountDisplaySnapshot2,
        SEG09A9_LevelActionCountDisplaySnapshot7,
        SEG09A9_LevelActionCountDisplaySnapshot0,
        SEG09A9_LevelActionCountDisplaySnapshot4,
        SEG09A9_LevelActionCountDisplaySnapshot3,
        SEG09A9_LevelActionCountDisplaySnapshot5,
        SEG09A9_LevelActionCountDisplaySnapshot1,
        SEG09A9_LevelActionCountDisplaySnapshot6,
        SEG09A9_StatusIconDisplaySnapshot
    };
    static const StatusCountStep count_steps[10]={
        {SEG09A9_LevelReleaseSettingMinimum,CS_InitializeStatusAfterMinimum,0x0u},
        {SEG09A9_LevelReleaseSetting,CS_InitializeStatusAfterRelease,0x1u},
        {SEG09A9_LevelActionCount2,CS_InitializeStatusAfterAction2,0x4u},
        {SEG09A9_LevelActionCount7,CS_InitializeStatusAfterAction7,0x9u},
        {SEG09A9_LevelActionCount0,CS_InitializeStatusAfterAction0,0x2u},
        {SEG09A9_LevelActionCount4,CS_InitializeStatusAfterAction4,0x6u},
        {SEG09A9_LevelActionCount3,CS_InitializeStatusAfterAction3,0x5u},
        {SEG09A9_LevelActionCount5,CS_InitializeStatusAfterAction5,0x7u},
        {SEG09A9_LevelActionCount1,CS_InitializeStatusAfterAction1,0x3u},
        {SEG09A9_LevelActionCount6,CS_InitializeStatusAfterAction6,0x8u}
    };
    StatusInitializeState s;
    uint8_t rate,release_setting;
    unsigned i;
    initialize_state(&s,memory,call,bus);

    if(!call_copy_wrapper(&s))return result_of(&s);

#if STATUS_INITIALIZE_MUTATION != 8
    write8(&s,s.ds,SEG09A9_EntityCreationCountdown,0x14u);
#endif
    set_al(&s,0x63u);                                   /* MOV AL,63 */
    release_setting=read8(&s,s.ds,SEG09A9_LevelReleaseSetting);
    rate=(uint8_t)(al(&s)-release_setting);
    s.flags=sub8_flags(s.flags,al(&s),release_setting);
    set_al(&s,rate);                                    /* SUB AL,[67] */
#if STATUS_INITIALIZE_MUTATION == 2
    /* Fault omits the SHR AL,1 instruction. */
#else
    rate=(uint8_t)(al(&s)>>1);
    s.flags=shr8_one_flags(s.flags,al(&s));
    set_al(&s,rate);                                    /* SHR AL,1 */
#endif
    rate=(uint8_t)(0u-al(&s));
    s.flags=neg8_flags(s.flags,al(&s));
    set_al(&s,rate);                                    /* NEG AL */
    rate=(uint8_t)(al(&s)+0x35u);
    s.flags=add8_flags(s.flags,al(&s),0x35u);
    set_al(&s,rate);                                    /* ADD AL,35 */
    rate=(uint8_t)(0u-al(&s));
    s.flags=neg8_flags(s.flags,al(&s));
    set_al(&s,rate);                                    /* NEG AL */
    rate=(uint8_t)(al(&s)+0x39u);
    s.flags=add8_flags(s.flags,al(&s),0x39u);
    set_al(&s,rate);                                    /* ADD AL,39 */
    write8(&s,s.ds,SEG09A9_EntityCreationReload,al(&s));

#if STATUS_INITIALIZE_MUTATION == 3
    for(i=0u;i<11u;++i)
        write8(&s,s.ds,snapshot_offsets[i],i==10u?0x03u:0xffu);
#endif
    for(i=0u;i<11u;++i)write8(&s,s.ds,counter_offsets[i],0u);
#if STATUS_INITIALIZE_MUTATION != 3
    for(i=0u;i<11u;++i)
        write8(&s,s.ds,snapshot_offsets[i],i==10u?0x03u:0xffu);
#endif

    for(i=0u;i<10u;++i) {
        uint16_t source=count_steps[i].source_offset;
        uint8_t selector=count_steps[i].selector;
#if STATUS_INITIALIZE_MUTATION == 4
        if(i==2u) {
            source=SEG09A9_LevelActionCount7;selector=0x9u;
        } else if(i==3u) {
            source=SEG09A9_LevelActionCount2;selector=0x4u;
        }
#endif
#if STATUS_INITIALIZE_MUTATION == 5
        if(i==2u) {
            /* Fault omits the count-2 draw at the third count slot. */
            s.continuation=count_steps[i].return_offset;
            continue;
        }
#endif
        if(!call_status_count(&s,source,selector,
            count_steps[i].return_offset,(uint8_t)(i==0u)))
            return result_of(&s);
    }

    if(!call_decimal_field(&s))return result_of(&s);

    s.si=(uint16_t)(SEG09A9_StatusPercentDigits+1u);     /* MOV SI,209D */
#if STATUS_INITIALIZE_MUTATION != 6
    write8(&s,s.ds,(uint16_t)(s.si-1u),0x20u);          /* MOV [SI-1],20 */
#endif
    if(!call_status_icon_outline(&s))return result_of(&s);

    s.continuation=CS_InitializeStatusReturn;
    s.status=LMN_STATUS_INITIALIZE_READY;
    return result_of(&s);
}

static void apply_result(LmnRegs *r,const LmnStatusInitializeResult *out) {
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

uint16_t lmn_initialize_status_display_adapter(uint8_t *memory,LmnRegs *r,
    const LmnRasterBus *bus) {
    LmnStatusInitializeCall call;
    LmnStatusInitializeResult out;
    call.value=r->ax;call.map_cursor=r->bx;call.count=r->cx;
    call.auxiliary_value=r->dx;call.record_cursor=r->si;
    call.object_cursor=r->di;call.candidate_y=r->bp;
    call.code_segment=r->cs;call.data_segment=r->ds;
    call.extra_segment=r->es;call.stack_segment=r->ss;
    call.stack_offset=r->sp;call.flags=r->flags;
    out=lmn_initialize_status_display_core(memory,&call,bus);
    apply_result(r,&out);
    if(out.status==LMN_STATUS_INITIALIZE_READY) {
        r->ip=read_stack_return(memory,r->ss,r->sp,r->flags,bus);
        r->sp=(uint16_t)(r->sp+2u);
    }
    return out.status;
}

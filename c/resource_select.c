#include "resource_select.h"
#include "decimal_digits.h"
#include "lemmings_sym.h"
#ifndef SELECT_MUTATION
#define SELECT_MUTATION 0
#endif
#ifndef SELECT_RETURN_MUTATION
#define SELECT_RETURN_MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,DF=1024,OF=2048,ARITH=0x8d5};
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint16_t word(const uint8_t *mem,uint16_t seg,uint16_t off) {
    uint32_t p=physical(seg,off);return (uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));
}
static uint8_t read8(uint8_t *mem,uint16_t seg,uint16_t off,uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=physical(seg,off);return bus&&bus->read_byte?bus->read_byte(bus->context,mem,at,flags):mem[at];
}
static uint16_t read16(uint8_t *mem,uint16_t seg,uint16_t off,uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=physical(seg,off);uint8_t lo,hi;
    if(bus&&bus->read_byte){lo=bus->read_byte(bus->context,mem,at,flags);hi=bus->read_byte(bus->context,mem,(at+1u)&0xFFFFFu,flags);}
    else {lo=mem[at];hi=mem[(at+1u)&0xFFFFFu];}return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void write8(uint8_t *mem,uint16_t seg,uint16_t off,uint8_t value,uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=physical(seg,off);
    if(bus&&bus->write_byte)bus->write_byte(bus->context,mem,at,value,flags);else mem[at]=value;
}
static void write16(uint8_t *mem,uint16_t seg,uint16_t off,uint16_t value,uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=physical(seg,off);
    if(bus&&bus->write_byte){bus->write_byte(bus->context,mem,at,(uint8_t)value,flags);bus->write_byte(bus->context,mem,(at+1u)&0xFFFFFu,(uint8_t)(value>>8),flags);}
    else {mem[at]=(uint8_t)value;mem[(at+1u)&0xFFFFFu]=(uint8_t)(value>>8);}
}
static void push(uint8_t *mem,LmnDatFileCall *s,uint16_t value,const LmnRasterBus *bus) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);write16(mem,s->stack_segment,s->stack_offset,value,s->flags,bus);
}
static uint16_t pop(uint8_t *mem,LmnDatFileCall *s,const LmnRasterBus *bus) {
    uint16_t value=read16(mem,s->stack_segment,s->stack_offset,s->flags,bus);s->stack_offset=(uint16_t)(s->stack_offset+2u);return value;
}
static uint16_t szp(uint16_t value,unsigned width) {
    unsigned i,parity=0;uint16_t flags=0;
    for(i=0;i<8;++i)parity^=(value>>i)&1u;
    if(!parity)flags|=PF;
    if(!value)flags|=ZF;
    if(value&(width==8 ? 128u:0x8000u))flags|=SF;
    return flags;
}
static uint16_t logical(uint16_t flags,uint16_t value,unsigned width) {
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,width));
}
static uint16_t addition(uint16_t flags,uint16_t a,uint16_t b,unsigned width) {
    uint32_t sum=(uint32_t)a+b;uint16_t mask=width==8 ? 255u:65535u,sign=width==8 ? 128u:0x8000u;
    uint16_t value=(uint16_t)(sum&mask);
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,width)|(sum>mask ? CF:0)|
        ((a^b^value)&AF)|(((0xffffu^(a^b))&(a^value)&sign) ? OF:0));
}
static LmnDatFileCall state_from_result(const LmnDatFileResult *out,uint16_t ss) {
    LmnDatFileCall s={out->value,out->handle,out->count,out->filename_offset,out->source_cursor,
        out->output_cursor,out->base_cursor,out->segment,out->extra_segment,ss,out->stack_offset,out->flags};return s;
}
static LmnDatFileResult legacy_result(const LmnDatFileCall *s,unsigned fatal) {
    LmnDatFileResult out={s->value,s->handle,s->count,s->filename_offset,s->source_cursor,
        s->output_cursor,s->base_cursor,s->segment,s->extra_segment,s->stack_offset,s->flags,(uint16_t)fatal};return out;
}
static LmnResourceSelectionExecution execution_result(const LmnDatFileCall *s,
    uint16_t continuation,enum LmnResourceSelectionStatus status) {
    LmnResourceSelectionExecution out={*s,continuation,status};return out;
}
typedef struct ChildTransfer {
    uint16_t continuation;
    enum LmnResourceSelectionStatus status;
} ChildTransfer;
static ChildTransfer child_transfer(uint16_t continuation,
    enum LmnResourceSelectionStatus status) {
    ChildTransfer out={continuation,status};return out;
}
static ChildTransfer consumed_child_return(uint8_t *mem,LmnDatFileCall *s,
    uint16_t expected,const LmnRasterBus *bus) {
    uint16_t target=pop(mem,s,bus);
#if SELECT_RETURN_MUTATION == 1
    (void)target;
    return child_transfer(expected,LMN_RESOURCE_SELECTION_READY);
#else
    return child_transfer(target,target==expected ? LMN_RESOURCE_SELECTION_READY:
        LMN_RESOURCE_SELECTION_CHANGED_RETURN);
#endif
}
static ChildTransfer dat_call(uint8_t *mem,LmnDatFileCall *s,uint16_t continuation,unsigned first,
    const LmnDatLoadSegments *segments,const LmnResourceSelectionServices *services,const LmnRasterBus *bus) {
    LmnDatFileResult out;ChildTransfer transfer;push(mem,s,continuation,bus);
    out=first ? lmn_dat_load_core(mem,s,segments,services->files,services->io):
        lmn_dat_decode_preserving_segment_core(mem,s,segments,services->io);
    *s=state_from_result(&out,s->stack_segment);
    if(out.fatal==1)return child_transfer(CS_DatFileErrorTransfer,LMN_RESOURCE_SELECTION_FILE_ERROR);
    if(out.fatal)return child_transfer(CS_DatFatalTransfer,LMN_RESOURCE_SELECTION_CLEANUP);
    transfer=consumed_child_return(mem,s,continuation,bus);return transfer;
}
static ChildTransfer raw_call(uint8_t *mem,LmnDatFileCall *s,uint16_t continuation,
    const LmnRawResourceServices *services,const LmnRasterBus *bus) {
    LmnRawResourceCall call;LmnRawResourceResult out;ChildTransfer transfer;push(mem,s,continuation,bus);
    call=(LmnRawResourceCall){s->segment,s->filename_offset,s->extra_segment,s->value,s->count,s->handle,s->stack_segment,s->stack_offset,s->flags};
    out=lmn_read_raw_resource_core(mem,&call,services);s->value=out.value;s->handle=out.handle;s->count=out.count;
    s->filename_offset=out.offset;s->segment=out.segment;s->extra_segment=out.extra_segment;s->stack_offset=out.stack_offset;s->flags=out.flags;
    if(out.error_stage)return child_transfer(CS_DatFileErrorTransfer,LMN_RESOURCE_SELECTION_FILE_ERROR);
    transfer=consumed_child_return(mem,s,continuation,bus);return transfer;
}
static void copy_words(uint8_t *mem,LmnDatFileCall *s,const LmnRasterBus *bus) {
    uint16_t step=(s->flags&DF) ? 0xfffeu:2u;
    while(s->count) {
        uint16_t value=read16(mem,s->segment,s->source_cursor,s->flags,bus);
        write16(mem,s->extra_segment,s->output_cursor,value,s->flags,bus);
        s->source_cursor=(uint16_t)(s->source_cursor+step);s->output_cursor=(uint16_t)(s->output_cursor+step);--s->count;
    }
}
static unsigned close_file(uint8_t *mem,LmnDatFileCall *s,const LmnRawResourceServices *services) {
    LmnDatDosResult out;s->value=(uint16_t)((s->value&255u)|0x3e00u);
    services->close(services->context,mem,s->handle,s->value,s->flags,&out);s->value=out.value;s->flags=out.flags;
#if SELECT_MUTATION == 3
    if(s->flags&CF)return 1;
#endif
    return 0;
}

LmnResourceSelectionExecution lmn_load_selected_resources_bus_execution_core(uint8_t *mem,
    const LmnDatFileCall *call,const LmnDatLoadSegments *segments,
    const LmnResourceSelectionServices *services,const LmnRasterBus *bus) {
    LmnDatFileCall s=*call;
    LmnDecimalDigitsResult digits;ChildTransfer transfer;uint16_t decimal_return;
    s.handle=read8(mem,s.segment,SEG09A9_LevelResourceSelectionByte,s.flags,bus);
    s.flags=logical(s.flags,0,8); /* XOR BH,BH precedes the order read. */
    s.source_cursor=SEG09A9_LevelResourceOrderBytes;
    s.count=read8(mem,s.segment,(uint16_t)(s.source_cursor+s.handle),s.flags,bus);
#if SELECT_MUTATION == 1
    s.count=s.count ? (uint8_t)(s.count-1u):0;
#else
    s.count=(uint8_t)(s.count-1u);
#endif
    s.flags=logical(s.flags,0,8); /* XOR CH,CH precedes the first save. */
    /* The saved order word and section counter are live. No index validation
       or filename normalization substitutes for the original byte arithmetic. */
    push(mem,&s,s.count,bus);s.count>>=1;s.value=(uint16_t)(s.count>>3);s.count&=7u;
    s.flags=logical(s.flags,s.count,16);s.source_cursor=SEG09A9_LevelResourceFilenameDigits;
    push(mem,&s,s.count,bus);push(mem,&s,CS_SelectionAfterDecimal,bus);
    digits=lmn_write_decimal_digits_bus_core(mem,s.segment,s.source_cursor,(uint8_t)s.value,s.flags,bus);
    s.value=digits.value;s.source_cursor=digits.cursor;s.flags=digits.flags;
    decimal_return=pop(mem,&s,bus);
#if SELECT_RETURN_MUTATION == 1
    (void)decimal_return;
#else
    if(decimal_return!=CS_SelectionAfterDecimal)
        return execution_result(&s,decimal_return,LMN_RESOURCE_SELECTION_CHANGED_RETURN);
#endif
    s.count=pop(mem,&s,bus);
    s.filename_offset=SEG09A9_LevelResourceFilename;push(mem,&s,s.segment,bus);s.extra_segment=pop(mem,&s,bus);
    s.output_cursor=SEG09A9_LoadedLevelRecord;push(mem,&s,s.count,bus);s.count=s.extra_segment;s.source_cursor=s.output_cursor;
    transfer=dat_call(mem,&s,CS_SelectionAfterFirstLevelSection,1,segments,services,bus);
    if(transfer.status!=LMN_RESOURCE_SELECTION_READY)return execution_result(&s,transfer.continuation,transfer.status);
    s.count=pop(mem,&s,bus);
    while(s.count) {
        push(mem,&s,s.count,bus);s.output_cursor=SEG09A9_LoadedLevelRecord;
        transfer=dat_call(mem,&s,CS_SelectionAfterNextLevelSection,0,segments,services,bus);
        if(transfer.status!=LMN_RESOURCE_SELECTION_READY)return execution_result(&s,transfer.continuation,transfer.status);
        s.count=pop(mem,&s,bus);--s.count;
    }
    if(close_file(mem,&s,services->raw))
        return execution_result(&s,CS_DatFileErrorTransfer,LMN_RESOURCE_SELECTION_FILE_ERROR);
    s.value=pop(mem,&s,bus);s.flags=logical(s.flags,(uint16_t)(s.value&1u),16);
    if(s.value&1u) {
        push(mem,&s,s.value,bus);push(mem,&s,s.segment,bus);s.extra_segment=pop(mem,&s,bus);
        s.filename_offset=SEG09A9_OddLevelOverrideFilename;s.value=SEG09A9_OddLevelOverrideBuffer;s.count=0x1180;
        transfer=raw_call(mem,&s,CS_SelectionAfterOddOverrideRead,services->raw,bus);
        if(transfer.status!=LMN_RESOURCE_SELECTION_READY)return execution_result(&s,transfer.continuation,transfer.status);
        s.value=pop(mem,&s,bus);
        /* SHR AL / MUL DH discard incoming AH; DX retains its previous low byte. */
        s.value=(uint16_t)(((uint8_t)s.value>>1)*56u);s.filename_offset=(uint16_t)((s.filename_offset&255u)|0x3800u);
        s.output_cursor=SEG09A9_LoadedLevelRecord;s.source_cursor=SEG09A9_OddLevelOverrideBuffer;
        s.flags=addition(s.flags,s.source_cursor,s.value,16);s.source_cursor=(uint16_t)(s.source_cursor+s.value);
        s.count=12;push(mem,&s,s.segment,bus);s.extra_segment=pop(mem,&s,bus);copy_words(mem,&s,bus);
        s.output_cursor=SEG09A9_LoadedLevelFooterBytes;s.count=16;copy_words(mem,&s,bus);
    }
    s.value=(uint16_t)((s.value&0xff00u)|read8(mem,s.segment,SEG09A9_LevelGraphicsSetByte,s.flags,bus));
    s.source_cursor=SEG09A9_GroundFilenameSelector;s.flags=addition(s.flags,(uint8_t)s.value,0x30,8);
    s.value=(uint16_t)((s.value&0xff00u)|(uint8_t)(s.value+0x30u));write8(mem,s.segment,s.source_cursor,(uint8_t)s.value,s.flags,bus);
    s.filename_offset=SEG09A9_GroundResourceFilename;push(mem,&s,s.segment,bus);s.extra_segment=pop(mem,&s,bus);
    s.value=SEG09A9_GroundResourceBuffer;s.count=0x1000;
    transfer=raw_call(mem,&s,CS_SelectionAfterGroundRead,services->raw,bus);
    if(transfer.status!=LMN_RESOURCE_SELECTION_READY)return execution_result(&s,transfer.continuation,transfer.status);
#if SELECT_MUTATION == 2
    s.segment=call->segment;
#endif
    s.value=(uint16_t)((s.value&0xff00u)|read8(mem,s.segment,SEG09A9_LevelGraphicsSetByte,s.flags,bus));
    s.source_cursor=SEG09A9_GraphicsFilenameSelector;s.flags=addition(s.flags,(uint8_t)s.value,0x30,8);
    s.value=(uint16_t)((s.value&0xff00u)|(uint8_t)(s.value+0x30u));write8(mem,s.segment,s.source_cursor,(uint8_t)s.value,s.flags,bus);
    s.value=(uint16_t)((s.value&0xff00u)|read8(mem,s.segment,SEG09A9_LevelSpecialGraphicsSetByte,s.flags,bus));
    s.flags=logical(s.flags,(uint8_t)s.value,8);
    if((uint8_t)s.value==0) {
        push(mem,&s,s.segment,bus);s.filename_offset=SEG09A9_GraphicsDatFilename;
        s.extra_segment=read16(mem,s.segment,SEG09A9_GraphicsResourceInputSegment,s.flags,bus);s.output_cursor=0x10;s.source_cursor=0;
        s.flags=logical(s.flags,0,16);s.count=s.extra_segment;
        transfer=dat_call(mem,&s,CS_SelectionAfterGraphicsLoad,1,segments,services,bus);
        if(transfer.status!=LMN_RESOURCE_SELECTION_READY)return execution_result(&s,transfer.continuation,transfer.status);
        s.segment=pop(mem,&s,bus);push(mem,&s,s.segment,bus);s.output_cursor=0;s.source_cursor=0;s.flags=logical(s.flags,0,16);
        s.extra_segment=read16(mem,s.segment,SEG09A9_LevelGraphicsSegment,s.flags,bus);s.segment=read16(mem,s.segment,SEG09A9_LevelGraphicsSegment,s.flags,bus);
        transfer=dat_call(mem,&s,CS_SelectionAfterGraphicsDecode,0,segments,services,bus);
        if(transfer.status!=LMN_RESOURCE_SELECTION_READY)return execution_result(&s,transfer.continuation,transfer.status);
        s.segment=pop(mem,&s,bus);
        if(close_file(mem,&s,services->raw))
            return execution_result(&s,CS_DatFileErrorTransfer,LMN_RESOURCE_SELECTION_FILE_ERROR);
        return execution_result(&s,CS_SelectionNormalReturn,LMN_RESOURCE_SELECTION_READY);
    } else {
        s.source_cursor=SEG09A9_SpecialFilenameSelector;s.flags=addition(s.flags,(uint8_t)s.value,0x2f,8);
        s.value=(uint16_t)((s.value&0xff00u)|(uint8_t)(s.value+0x2fu));write8(mem,s.segment,s.source_cursor,(uint8_t)s.value,s.flags,bus);
        push(mem,&s,s.segment,bus);s.filename_offset=SEG09A9_SpecialResourceFilename;
        s.extra_segment=read16(mem,s.segment,SEG09A9_GraphicsResourceInputSegment,s.flags,bus);s.source_cursor=0;s.flags=logical(s.flags,0,16);
        s.output_cursor=0x10;s.count=s.extra_segment;
        transfer=dat_call(mem,&s,CS_SelectionAfterSpecialLoad,1,segments,services,bus);
        if(transfer.status!=LMN_RESOURCE_SELECTION_READY)return execution_result(&s,transfer.continuation,transfer.status);
        s.segment=pop(mem,&s,bus);
        if(close_file(mem,&s,services->raw))
            return execution_result(&s,CS_DatFileErrorTransfer,LMN_RESOURCE_SELECTION_FILE_ERROR);
        return execution_result(&s,CS_SelectionSpecialReturn,LMN_RESOURCE_SELECTION_READY);
    }
}

LmnResourceSelectionExecution lmn_load_selected_resources_execution_core(uint8_t *mem,
    const LmnDatFileCall *call,const LmnDatLoadSegments *segments,
    const LmnResourceSelectionServices *services) {
    return lmn_load_selected_resources_bus_execution_core(mem,call,segments,services,0);
}

LmnDatFileResult lmn_load_selected_resources_core(uint8_t *mem,const LmnResourceSelectionCall *call,
    const LmnDatLoadSegments *segments,const LmnResourceSelectionServices *services) {
    LmnDatFileCall input={0,0,0,0,0,0,call->base_cursor,call->main_data_segment,0,
        call->stack_segment,call->stack_offset,call->flags};
    LmnResourceSelectionExecution execution=lmn_load_selected_resources_execution_core(mem,&input,segments,services);
    unsigned fatal=execution.status==LMN_RESOURCE_SELECTION_FILE_ERROR ? 1u:
        execution.status==LMN_RESOURCE_SELECTION_CLEANUP ? 2u:
        execution.status==LMN_RESOURCE_SELECTION_CHANGED_RETURN ? 3u:0u;
    return legacy_result(&execution.state,fatal);
}

void lmn_load_selected_resources_adapter(uint8_t *mem,LmnRegs *r,const LmnResourceSelectionServices *services) {
    LmnDatFileCall call={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};
    LmnDatLoadSegments segments={word(mem,r->cs,(uint16_t)(CS_CheckDatFile+0x33u)),
        word(mem,r->cs,(uint16_t)(CS_SelectCachedDatFile+0x50u)),word(mem,r->cs,(uint16_t)(CS_ReadDatBytes+8u)),
        word(mem,r->cs,(uint16_t)(CS_DatReadFailure+1u))};
    LmnResourceSelectionExecution out=lmn_load_selected_resources_execution_core(mem,&call,&segments,services);
    r->ax=out.state.value;r->bx=out.state.handle;r->cx=out.state.count;r->dx=out.state.filename_offset;
    r->si=out.state.source_cursor;r->di=out.state.output_cursor;r->bp=out.state.base_cursor;
    r->ds=out.state.segment;r->es=out.state.extra_segment;r->ss=out.state.stack_segment;
    r->sp=out.state.stack_offset;r->flags=out.state.flags;
    if(out.status==LMN_RESOURCE_SELECTION_READY) {
        r->ip=word(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);
    } else r->ip=out.continuation;
}

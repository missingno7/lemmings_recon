#include "resource_select.h"
#include "decimal_digits.h"
#include "lemmings_sym.h"
#ifndef SELECT_MUTATION
#define SELECT_MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,DF=1024,OF=2048,ARITH=0x8d5};
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint8_t byte(const uint8_t *mem,uint16_t seg,uint16_t off) {return mem[physical(seg,off)];}
static uint16_t word(const uint8_t *mem,uint16_t seg,uint16_t off) {
    uint32_t p=physical(seg,off);return (uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));
}
static void putword(uint8_t *mem,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t p=physical(seg,off);mem[p]=(uint8_t)value;mem[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static void push(uint8_t *mem,LmnDatFileCall *s,uint16_t value) {
    s->stack_offset=(uint16_t)(s->stack_offset-2u);putword(mem,s->stack_segment,s->stack_offset,value);
}
static uint16_t pop(const uint8_t *mem,LmnDatFileCall *s) {
    uint16_t value=word(mem,s->stack_segment,s->stack_offset);s->stack_offset=(uint16_t)(s->stack_offset+2u);return value;
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
static LmnDatFileResult result(const LmnDatFileCall *s,unsigned fatal) {
    LmnDatFileResult out={s->value,s->handle,s->count,s->filename_offset,s->source_cursor,
        s->output_cursor,s->base_cursor,s->segment,s->extra_segment,s->stack_offset,s->flags,(uint16_t)fatal};return out;
}
static unsigned dat_call(uint8_t *mem,LmnDatFileCall *s,uint16_t continuation,unsigned first,
    const LmnDatLoadSegments *segments,const LmnResourceSelectionServices *services) {
    LmnDatFileResult out;push(mem,s,continuation);
    out=first ? lmn_dat_load_core(mem,s,segments,services->files,services->io):
        lmn_dat_decode_preserving_segment_core(mem,s,segments,services->io);
    *s=state_from_result(&out,s->stack_segment);
    if(out.fatal)return out.fatal;
    (void)pop(mem,s);return 0;
}
static unsigned raw_call(uint8_t *mem,LmnDatFileCall *s,uint16_t continuation,const LmnRawResourceServices *services) {
    LmnRawResourceCall call;LmnRawResourceResult out;push(mem,s,continuation);
    call=(LmnRawResourceCall){s->segment,s->filename_offset,s->extra_segment,s->value,s->count,s->handle,s->stack_segment,s->stack_offset,s->flags};
    out=lmn_read_raw_resource_core(mem,&call,services);s->value=out.value;s->handle=out.handle;s->count=out.count;
    s->filename_offset=out.offset;s->segment=out.segment;s->extra_segment=out.extra_segment;s->stack_offset=out.stack_offset;s->flags=out.flags;
    if(out.error_stage)return 1;
    (void)pop(mem,s);return 0;
}
static void copy_words(uint8_t *mem,LmnDatFileCall *s) {
    uint16_t step=(s->flags&DF) ? 0xfffeu:2u;
    while(s->count) {
        uint16_t value=word(mem,s->segment,s->source_cursor);
        putword(mem,s->extra_segment,s->output_cursor,value);
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
LmnDatFileResult lmn_load_selected_resources_core(uint8_t *mem,const LmnResourceSelectionCall *call,
    const LmnDatLoadSegments *segments,const LmnResourceSelectionServices *services) {
    LmnDatFileCall s={0,0,0,0,0,0,call->base_cursor,call->main_data_segment,0,call->stack_segment,call->stack_offset,call->flags};
    LmnDecimalDigitsResult digits;unsigned fatal;
    s.handle=byte(mem,s.segment,SEG09A9_LevelResourceSelectionByte);s.source_cursor=SEG09A9_LevelResourceOrderBytes;
    s.count=byte(mem,s.segment,(uint16_t)(s.source_cursor+s.handle));
#if SELECT_MUTATION == 1
    s.count=s.count ? (uint8_t)(s.count-1u):0;
#else
    s.count=(uint8_t)(s.count-1u);
#endif
    /* The saved order word and section counter are live. No index validation
       or filename normalization substitutes for the original byte arithmetic. */
    push(mem,&s,s.count);s.count>>=1;s.value=(uint16_t)(s.count>>3);s.count&=7u;
    s.flags=logical(s.flags,s.count,16);s.source_cursor=SEG09A9_LevelResourceFilenameDigits;
    push(mem,&s,s.count);push(mem,&s,CS_SelectionAfterDecimal);
    digits=lmn_write_decimal_digits_core(mem,s.segment,s.source_cursor,(uint8_t)s.value,s.flags);
    s.value=digits.value;s.source_cursor=digits.cursor;s.flags=digits.flags;(void)pop(mem,&s);s.count=pop(mem,&s);
    s.filename_offset=SEG09A9_LevelResourceFilename;push(mem,&s,s.segment);s.extra_segment=pop(mem,&s);
    s.output_cursor=SEG09A9_LoadedLevelRecord;push(mem,&s,s.count);s.count=s.extra_segment;s.source_cursor=s.output_cursor;
    fatal=dat_call(mem,&s,CS_SelectionAfterFirstLevelSection,1,segments,services);if(fatal)return result(&s,fatal);
    s.count=pop(mem,&s);
    while(s.count) {
        push(mem,&s,s.count);s.output_cursor=SEG09A9_LoadedLevelRecord;
        fatal=dat_call(mem,&s,CS_SelectionAfterNextLevelSection,0,segments,services);if(fatal)return result(&s,fatal);
        s.count=pop(mem,&s);--s.count;
    }
    if(close_file(mem,&s,services->raw))return result(&s,1);
    s.value=pop(mem,&s);s.flags=logical(s.flags,(uint16_t)(s.value&1u),16);
    if(s.value&1u) {
        push(mem,&s,s.value);push(mem,&s,s.segment);s.extra_segment=pop(mem,&s);
        s.filename_offset=SEG09A9_OddLevelOverrideFilename;s.value=SEG09A9_OddLevelOverrideBuffer;s.count=0x1180;
        fatal=raw_call(mem,&s,CS_SelectionAfterOddOverrideRead,services->raw);if(fatal)return result(&s,fatal);
        s.value=pop(mem,&s);
        /* SHR AL / MUL DH discard incoming AH; DX retains its previous low byte. */
        s.value=(uint16_t)(((uint8_t)s.value>>1)*56u);s.filename_offset=(uint16_t)((s.filename_offset&255u)|0x3800u);
        s.output_cursor=SEG09A9_LoadedLevelRecord;s.source_cursor=SEG09A9_OddLevelOverrideBuffer;
        s.flags=addition(s.flags,s.source_cursor,s.value,16);s.source_cursor=(uint16_t)(s.source_cursor+s.value);
        s.count=12;push(mem,&s,s.segment);s.extra_segment=pop(mem,&s);copy_words(mem,&s);
        s.output_cursor=SEG09A9_LoadedLevelFooterBytes;s.count=16;copy_words(mem,&s);
    }
    s.value=(uint16_t)((s.value&0xff00u)|byte(mem,s.segment,SEG09A9_LevelGraphicsSetByte));
    s.source_cursor=SEG09A9_GroundFilenameSelector;s.flags=addition(s.flags,(uint8_t)s.value,0x30,8);
    s.value=(uint16_t)((s.value&0xff00u)|(uint8_t)(s.value+0x30u));mem[physical(s.segment,s.source_cursor)]=(uint8_t)s.value;
    s.filename_offset=SEG09A9_GroundResourceFilename;push(mem,&s,s.segment);s.extra_segment=pop(mem,&s);
    s.value=SEG09A9_GroundResourceBuffer;s.count=0x1000;
    fatal=raw_call(mem,&s,CS_SelectionAfterGroundRead,services->raw);if(fatal)return result(&s,fatal);
#if SELECT_MUTATION == 2
    s.segment=call->main_data_segment;
#endif
    s.value=(uint16_t)((s.value&0xff00u)|byte(mem,s.segment,SEG09A9_LevelGraphicsSetByte));
    s.source_cursor=SEG09A9_GraphicsFilenameSelector;s.flags=addition(s.flags,(uint8_t)s.value,0x30,8);
    s.value=(uint16_t)((s.value&0xff00u)|(uint8_t)(s.value+0x30u));mem[physical(s.segment,s.source_cursor)]=(uint8_t)s.value;
    s.value=(uint16_t)((s.value&0xff00u)|byte(mem,s.segment,SEG09A9_LevelSpecialGraphicsSetByte));
    s.flags=logical(s.flags,(uint8_t)s.value,8);
    if((uint8_t)s.value==0) {
        push(mem,&s,s.segment);s.filename_offset=SEG09A9_GraphicsDatFilename;
        s.extra_segment=word(mem,s.segment,SEG09A9_GraphicsResourceInputSegment);s.output_cursor=0x10;s.source_cursor=0;
        s.flags=logical(s.flags,0,16);s.count=s.extra_segment;
        fatal=dat_call(mem,&s,CS_SelectionAfterGraphicsLoad,1,segments,services);if(fatal)return result(&s,fatal);
        s.segment=pop(mem,&s);push(mem,&s,s.segment);s.output_cursor=0;s.source_cursor=0;s.flags=logical(s.flags,0,16);
        s.extra_segment=word(mem,s.segment,SEG09A9_LevelGraphicsSegment);s.segment=word(mem,s.segment,SEG09A9_LevelGraphicsSegment);
        fatal=dat_call(mem,&s,CS_SelectionAfterGraphicsDecode,0,segments,services);if(fatal)return result(&s,fatal);
        s.segment=pop(mem,&s);
    } else {
        s.source_cursor=SEG09A9_SpecialFilenameSelector;s.flags=addition(s.flags,(uint8_t)s.value,0x2f,8);
        s.value=(uint16_t)((s.value&0xff00u)|(uint8_t)(s.value+0x2fu));mem[physical(s.segment,s.source_cursor)]=(uint8_t)s.value;
        push(mem,&s,s.segment);s.filename_offset=SEG09A9_SpecialResourceFilename;
        s.extra_segment=word(mem,s.segment,SEG09A9_GraphicsResourceInputSegment);s.source_cursor=0;s.flags=logical(s.flags,0,16);
        s.output_cursor=0x10;s.count=s.extra_segment;
        fatal=dat_call(mem,&s,CS_SelectionAfterSpecialLoad,1,segments,services);if(fatal)return result(&s,fatal);
        s.segment=pop(mem,&s);
    }
    if(close_file(mem,&s,services->raw))return result(&s,1);
    return result(&s,0);
}
void lmn_load_selected_resources_adapter(uint8_t *mem,LmnRegs *r,const LmnResourceSelectionServices *services) {
    LmnResourceSelectionCall call={r->ds,r->ss,r->sp,r->flags,r->bp};
    LmnDatLoadSegments segments={word(mem,r->cs,(uint16_t)(CS_CheckDatFile+0x33u)),
        word(mem,r->cs,(uint16_t)(CS_SelectCachedDatFile+0x50u)),word(mem,r->cs,(uint16_t)(CS_ReadDatBytes+8u)),
        word(mem,r->cs,(uint16_t)(CS_DatReadFailure+1u))};
    LmnDatFileResult out=lmn_load_selected_resources_core(mem,&call,&segments,services);
    r->ax=out.value;r->bx=out.handle;r->cx=out.count;r->dx=out.filename_offset;r->si=out.source_cursor;r->di=out.output_cursor;
    r->bp=out.base_cursor;r->ds=out.segment;r->es=out.extra_segment;r->sp=out.stack_offset;r->flags=out.flags;
    if(out.fatal)r->ip=out.fatal==1 ? CS_DatFileErrorTransfer:CS_DatFatalTransfer;
    else {r->ip=word(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);}
}

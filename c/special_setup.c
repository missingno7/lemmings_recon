#include "special_setup.h"
#include "resource_rle.h"
#include "lemmings_sym.h"
#ifndef SETUP_MUTATION
#define SETUP_MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,DF=1024,OF=2048,ARITH=0x8d5};
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint16_t word(const uint8_t *mem,uint16_t seg,uint16_t off) {
    uint32_t p=physical(seg,off);return (uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));
}
static void push(uint8_t *mem,LmnDatFileCall *s,uint16_t value) {
    uint32_t p;s->stack_offset=(uint16_t)(s->stack_offset-2u);p=physical(s->stack_segment,s->stack_offset);
    mem[p]=(uint8_t)value;mem[(p+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static uint16_t pop(const uint8_t *mem,LmnDatFileCall *s) {
    uint16_t out=word(mem,s->stack_segment,s->stack_offset);s->stack_offset=(uint16_t)(s->stack_offset+2u);return out;
}
static uint16_t szp(uint16_t value,unsigned width) {
    unsigned i,parity=0;uint16_t out=0;
    for(i=0;i<8;++i)parity^=(value>>i)&1u;
    if(!parity)out|=PF;
    if(!value)out|=ZF;
    if(value&(width==8 ? 128u:0x8000u))out|=SF;
    return out;
}
static uint16_t logical(uint16_t flags,uint16_t value,unsigned width) {
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,width));
}
static uint16_t addition(uint16_t flags,uint16_t a,uint16_t b) {
    uint32_t sum=(uint32_t)a+b;uint16_t value=(uint16_t)sum;
    return (uint16_t)((flags&(0xffffu^ARITH))|szp(value,16)|(sum>65535u ? CF:0)|
        ((a^b^value)&AF)|(((0xffffu^(a^b))&(a^value)&0x8000u) ? OF:0));
}
static void store_byte(uint8_t *mem,LmnDatFileCall *s,uint8_t value) {
    mem[physical(s->extra_segment,s->output_cursor)]=value;
    s->output_cursor=(uint16_t)(s->output_cursor+((s->flags&DF) ? 0xffffu:1u));
}
static void copy_bytes(uint8_t *mem,LmnDatFileCall *s) {
    uint16_t step=(s->flags&DF) ? 0xffffu:1u;
    while(s->count) {
        store_byte(mem,s,mem[physical(s->segment,s->source_cursor)]);
        s->source_cursor=(uint16_t)(s->source_cursor+step);--s->count;
    }
}
static LmnDatFileCall state_from_result(const LmnDatFileResult *out,uint16_t ss) {
    LmnDatFileCall s={out->value,out->handle,out->count,out->filename_offset,out->source_cursor,
        out->output_cursor,out->base_cursor,out->segment,out->extra_segment,ss,out->stack_offset,out->flags};return s;
}
static LmnDatFileResult result(const LmnDatFileCall *s,uint16_t fatal) {
    LmnDatFileResult out={s->value,s->handle,s->count,s->filename_offset,s->source_cursor,
        s->output_cursor,s->base_cursor,s->segment,s->extra_segment,s->stack_offset,s->flags,fatal};return out;
}
LmnDatFileResult lmn_setup_special_graphics_core(uint8_t *mem,const LmnDatFileCall *call,
    const LmnDatLoadSegments *segments,const LmnSpecialSetupServices *services) {
    static const uint16_t after_rle[4]={CS_SpecialAfterRle0,CS_SpecialAfterRle1,CS_SpecialAfterRle2,CS_SpecialAfterRle3};
    static const uint16_t after_strip[4]={CS_SpecialAfterStrip0,CS_SpecialAfterStrip1,CS_SpecialAfterStrip2,CS_SpecialAfterStrip3};
    LmnDatFileCall s=*call;unsigned strip;
    /* Prefix copies keep the original duplicate pushes, fixed destinations and
       DF-dependent traversal. Restores always read the live saved words. */
    push(mem,&s,s.segment);s.count=24;s.output_cursor=SEG09A9_SpecialMetadata24;s.source_cursor=0x10;
    push(mem,&s,s.segment);s.extra_segment=pop(mem,&s);s.segment=word(mem,s.segment,SEG09A9_GraphicsResourceInputSegment);
    push(mem,&s,s.output_cursor);copy_bytes(mem,&s);s.output_cursor=pop(mem,&s);
    s.value=(uint16_t)((s.value&0xff00u)|0x1fu);store_byte(mem,&s,0x1f);store_byte(mem,&s,0x1f);
    s.value&=0xff00u;s.flags=logical(s.flags,0,8);store_byte(mem,&s,0);
    s.count=24;s.output_cursor=SEG09A9_SpecialMetadataDuplicateBase;
    s.flags=addition(s.flags,s.output_cursor,24);s.output_cursor=(uint16_t)(s.output_cursor+24u);s.source_cursor=0x10;
    copy_bytes(mem,&s);s.count=8;s.output_cursor=SEG09A9_SpecialMetadata8Base;
    s.flags=addition(s.flags,s.output_cursor,8);s.output_cursor=(uint16_t)(s.output_cursor+8u);copy_bytes(mem,&s);
    s.count=8;s.output_cursor=SEG09A9_SpecialMetadataRemap8;push(mem,&s,s.output_cursor);copy_bytes(mem,&s);s.output_cursor=pop(mem,&s);
#if SETUP_MUTATION == 1
    s.value=(uint16_t)((s.value&0xff00u)|7u);store_byte(mem,&s,7);
#else
    s.value=(uint16_t)((s.value&0xff00u)|6u);store_byte(mem,&s,6);
#endif
    s.segment=pop(mem,&s);s.source_cursor=0x38;
    for(strip=0;strip<4;++strip) {
        LmnResourceRleResult decoded;LmnSpecialBlitResult drawn;
        /* Re-read both segment slots after each saved-DS push. No retained heap
           pointer or copied input bank replaces the original alias behavior. */
        push(mem,&s,s.segment);s.output_cursor=0x8000;s.extra_segment=word(mem,s.segment,SEG09A9_LevelGraphicsSegment);
        s.segment=word(mem,s.segment,SEG09A9_GraphicsResourceInputSegment);push(mem,&s,after_rle[strip]);
        decoded=lmn_decode_resource_rle_core(mem,s.segment,s.source_cursor,s.extra_segment,s.output_cursor,s.value,s.count,s.flags);
        s.value=decoded.value;s.count=decoded.count;s.source_cursor=decoded.source_cursor;s.output_cursor=decoded.output_cursor;
        s.extra_segment=decoded.output_segment;s.flags=decoded.flags;(void)pop(mem,&s);s.segment=pop(mem,&s);
        push(mem,&s,s.source_cursor);push(mem,&s,after_strip[strip]);
        drawn=lmn_blit_special_strip_core(mem,s.segment,s.stack_segment,s.stack_offset,(uint16_t)(strip*40u),strip==0,s.flags,services->raster);
        s.value=drawn.value;s.count=drawn.count;s.source_cursor=drawn.source_cursor;s.output_cursor=drawn.output_cursor;
        s.handle=drawn.vertical_offset;s.filename_offset=drawn.port;s.segment=drawn.source_segment;s.extra_segment=drawn.output_segment;
        s.stack_offset=drawn.stack_offset;s.flags=drawn.flags;(void)pop(mem,&s);
#if SETUP_MUTATION == 2
        (void)pop(mem,&s);
#else
        s.source_cursor=pop(mem,&s);
#endif
    }
    {
        LmnDatFileResult loaded;
        /* The drawn special image stays in device planes while ordinary DAT
           sections replace the same working heap. Fatal exits keep every frame. */
        push(mem,&s,s.segment);s.filename_offset=SEG09A9_GraphicsDatFilename;
        s.extra_segment=word(mem,s.segment,SEG09A9_LevelGraphicsSegment);s.output_cursor=0x10;s.source_cursor=0;
        s.flags=logical(s.flags,0,16);s.count=s.extra_segment;push(mem,&s,CS_SpecialAfterDatLoad);
        loaded=lmn_dat_load_core(mem,&s,segments,services->files,services->io);s=state_from_result(&loaded,s.stack_segment);
        if(loaded.fatal)return loaded;
        (void)pop(mem,&s);s.segment=pop(mem,&s);push(mem,&s,s.segment);s.output_cursor=0;s.source_cursor=0;s.flags=logical(s.flags,0,16);
        s.extra_segment=word(mem,s.segment,SEG09A9_LevelGraphicsSegment);s.segment=word(mem,s.segment,SEG09A9_LevelGraphicsSegment);
        push(mem,&s,CS_SpecialAfterDatDecode);loaded=lmn_dat_decode_preserving_segment_core(mem,&s,segments,services->io);
        s=state_from_result(&loaded,s.stack_segment);if(loaded.fatal)return loaded;
        (void)pop(mem,&s);s.segment=pop(mem,&s);
    }
    {
        LmnDatDosResult closed;s.value=(uint16_t)((s.value&255u)|0x3e00u);
        services->close(services->context,mem,s.handle,s.value,s.flags,&closed);s.value=closed.value;s.flags=closed.flags;
#if SETUP_MUTATION == 3
        if(s.flags&CF)return result(&s,1);
#endif
    }
    return result(&s,0);
}
void lmn_setup_special_graphics_adapter(uint8_t *mem,LmnRegs *r,const LmnSpecialSetupServices *services) {
    LmnDatFileCall call={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};
    LmnDatLoadSegments segments={word(mem,r->cs,(uint16_t)(CS_CheckDatFile+0x33u)),
        word(mem,r->cs,(uint16_t)(CS_SelectCachedDatFile+0x50u)),word(mem,r->cs,(uint16_t)(CS_ReadDatBytes+8u)),
        word(mem,r->cs,(uint16_t)(CS_DatReadFailure+1u))};
    LmnDatFileResult out=lmn_setup_special_graphics_core(mem,&call,&segments,services);
    r->ax=out.value;r->bx=out.handle;r->cx=out.count;r->dx=out.filename_offset;r->si=out.source_cursor;r->di=out.output_cursor;
    r->bp=out.base_cursor;r->ds=out.segment;r->es=out.extra_segment;r->sp=out.stack_offset;r->flags=out.flags;
    if(out.fatal)r->ip=out.fatal==1 ? CS_DatFileErrorTransfer:CS_DatFatalTransfer;
    else {r->ip=word(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);}
}

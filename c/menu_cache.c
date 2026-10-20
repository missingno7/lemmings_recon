#include "menu_cache.h"
#include "lemmings_sym.h"

#ifndef MENU_CACHE_MUTATION
#define MENU_CACHE_MUTATION 0
#endif
enum { CF=1, PF=4, AF=16, ZF=64, SF=128, OF=2048, ARITH=0x8d5 };
typedef struct Cache {
    uint8_t *memory;
    const LmnRasterBus *bus;
    LmnVideoRestoreState r;
    uint16_t cs;
} Cache;
static uint32_t physical(uint16_t seg,uint16_t off) {
    return (((uint32_t)seg<<4)+off)&0xfffffu;
}
static uint8_t read8(Cache *s,uint32_t at) {
    at&=0xfffffu;
    return s->bus&&s->bus->read_byte ?
        s->bus->read_byte(s->bus->context,s->memory,at,s->r.flags):s->memory[at];
}
static void write8(Cache *s,uint32_t at,uint8_t value) {
    at&=0xfffffu;
    if(s->bus&&s->bus->write_byte)s->bus->write_byte(s->bus->context,s->memory,at,value,s->r.flags);
    else s->memory[at]=value;
}
static uint16_t read16(Cache *s,uint16_t seg,uint16_t off) {
    uint32_t at=physical(seg,off);
    uint8_t lo=read8(s,at),hi=read8(s,at+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void write16(Cache *s,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t at=physical(seg,off);
    write8(s,at,(uint8_t)value);write8(s,at+1u,(uint8_t)(value>>8));
}
static void push(Cache *s,uint16_t value) {
    s->r.stack_offset=(uint16_t)(s->r.stack_offset-2u);
    write16(s,s->r.stack_segment,s->r.stack_offset,value);
}
static uint16_t pop(Cache *s) {
    uint16_t value=read16(s,s->r.stack_segment,s->r.stack_offset);
    s->r.stack_offset=(uint16_t)(s->r.stack_offset+2u);return value;
}
static uint16_t szp(uint16_t value,uint16_t sign) {
    unsigned parity=0;
    for(unsigned bit=0;bit<8u;++bit)parity^=(value>>bit)&1u;
    return (uint16_t)((parity?0u:PF)|(value?0u:ZF)|(value&sign?SF:0u));
}
static void cmp8(Cache *s,uint8_t left,uint8_t right) {
    uint8_t value=(uint8_t)(left-right);
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(value,0x80u)|
        (left<right?CF:0u)|((left^right^value)&16u)|
        (((left^right)&(left^value)&0x80u)?OF:0u));
}
static void logic8(Cache *s,uint8_t value) {
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(value,0x80u));
}
static uint16_t add16(Cache *s,uint16_t left,uint16_t right) {
    uint16_t value=(uint16_t)(left+right);
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(value,0x8000u)|
        ((uint32_t)left+right>0xffffu?CF:0u)|((left^right^value)&16u)|
        ((~(left^right)&(left^value)&0x8000u)?OF:0u));
    return value;
}
static void al(Cache *s,uint8_t value) {
#if MENU_CACHE_MUTATION == 1
    s->r.value=value;
#else
    s->r.value=(uint16_t)((s->r.value&0xff00u)|value);
#endif
}
static LmnMenuCacheResult result(Cache *s,uint16_t ip,enum LmnMenuCacheStatus status) {
    LmnMenuCacheResult out={s->r,s->cs,ip,status};return out;
}
static LmnMenuCacheResult bitmap(Cache *s,uint16_t game_ds,uint16_t resume,
    const LmnRasterBytePorts *ports) {
    uint16_t cs=s->cs,ip;
    push(s,cs);push(s,resume);
    {
        LmnPlanarBitmapCall call={s->r.data_segment,game_ds,s->r.stack_segment,s->r.stack_offset,
            s->r.value,s->r.base_value,s->r.count,s->r.argument,s->r.source_cursor,
            s->r.output_cursor,s->r.frame_cursor,s->r.extra_segment,s->r.flags};
        LmnDrawingRenderResult drawing=lmn_draw_planar_bitmap_core(s->memory,&call,s->bus,ports);
        const LmnDrawingSourceResult *r=&drawing.plan.state;
        s->r=(LmnVideoRestoreState){r->work_value,r->second_source_cursor,r->packed_counts,r->width_state,
            r->source_cursor,r->destination_cursor,r->control,drawing.source_segment,
            drawing.output_segment,s->r.stack_segment,r->stack_offset,r->flags};
        if(!drawing.body_returned)return result(s,r->continuation,LMN_MENU_CACHE_RENDERER_STOP);
    }
    ip=pop(s);s->cs=pop(s);
#if MENU_CACHE_MUTATION == 7
    s->cs=cs;(void)ip;
#else
    if(ip!=resume||s->cs!=cs)return result(s,ip,LMN_MENU_CACHE_CHANGED_RETURN);
#endif
    return result(s,resume,LMN_MENU_CACHE_READY);
}

LmnMenuCacheResult lmn_menu_cache_core(uint8_t *memory,uint16_t cs,uint16_t game_ds,
    const LmnVideoRestoreState *input,enum LmnMenuCacheEntry entry,
    const LmnRasterBus *bus,const LmnRasterBytePorts *ports) {
    Cache s={memory,bus,*input,cs};
    uint16_t current=entry==LMN_MENU_CACHE_SOUND?SEG09A9_MenuSoundRedrawToggle:SEG09A9_MenuLevelGroupIndex;
    uint16_t cached=entry==LMN_MENU_CACHE_SOUND?SEG09A9_MenuSoundRedrawCache:SEG09A9_MenuLevelGroupRedrawCache;
    uint8_t marker=entry==LMN_MENU_CACHE_SOUND?2u:4u,observed;
    uint16_t ret=entry==LMN_MENU_CACHE_SOUND?CS_MenuSoundIconReturn:CS_MenuLevelGroupReturn;
    al(&s,read8(&s,physical(s.r.data_segment,cached)));
    cmp8(&s,(uint8_t)s.r.value,marker);
    if(s.r.flags&ZF) {
#if MENU_CACHE_MUTATION == 2
        return result(&s,ret,LMN_MENU_CACHE_READY);
#else
        observed=read8(&s,physical(s.r.data_segment,current));al(&s,observed);
        write8(&s,physical(s.r.data_segment,cached),(uint8_t)s.r.value);
#endif
    } else {
        observed=read8(&s,physical(s.r.data_segment,current));
        cmp8(&s,observed,(uint8_t)s.r.value);
        if(s.r.flags&ZF)return result(&s,ret,LMN_MENU_CACHE_READY);
        write8(&s,physical(s.r.data_segment,cached),marker);
    }
    s.r.value=read16(&s,s.r.data_segment,SEG09A9_UiGraphicsBufferSegment);
    if(entry==LMN_MENU_CACHE_LEVEL_GROUP)s.r.value=add16(&s,s.r.value,0x1000u);
    write16(&s,s.r.data_segment,SEG09A9_GraphicsResourceSegment,s.r.value);
    if(entry==LMN_MENU_CACHE_SOUND) {
        uint8_t gate;
        s.r.source_cursor=0xee30u;
        al(&s,read8(&s,physical(s.r.data_segment,SEG09A9_SoundOptionBits)));
        logic8(&s,(uint8_t)s.r.value&3u);
        if(s.r.flags&ZF) {
            s.r.base_value=120u;s.r.value=324u;s.r.source_cursor=0xb120u;
            s.r.frame_cursor=3u;s.r.count=0x043du;s.r.argument=0x0078u;
            s.r.output_cursor=s.r.source_cursor;
            s.r.output_cursor=add16(&s,s.r.output_cursor,0x0ab9u);
            return bitmap(&s,game_ds,CS_MenuSoundBackgroundReturn,ports);
        }
        logic8(&s,(uint8_t)s.r.value&2u);
        if(!(s.r.flags&ZF)) {
            gate=read8(&s,physical(s.r.data_segment,SEG09A9_ExternalSoundDriverEnabled));
            cmp8(&s,gate,0xffu);
#if MENU_CACHE_MUTATION == 3
            if(gate)s.r.source_cursor=0xea50u;
#else
            if(s.r.flags&ZF)s.r.source_cursor=0xea50u;
#endif
        }
        s.r.value=351u;s.r.base_value=146u;s.r.argument=64u;s.r.count=0x041fu;s.r.frame_cursor=1u;
    } else {
#if MENU_CACHE_MUTATION == 4
        s.r.base_value=(uint16_t)((s.r.base_value&0xff00u)|observed);
#else
        s.r.base_value=(uint16_t)((s.r.base_value&0xff00u)|read8(&s,physical(s.r.data_segment,current)));
#endif
#if MENU_CACHE_MUTATION != 5
        s.r.base_value&=0x00ffu;
#endif
        logic8(&s,0u); /* XOR BH,BH; then SHL BX,1 (AF undefined). */
        {
            uint16_t old=s.r.base_value;s.r.base_value=(uint16_t)(old<<1);
            s.r.flags=(uint16_t)((s.r.flags&~ARITH)|szp(s.r.base_value,0x8000u)|
                (old&0x8000u?CF:0u)|((old^s.r.base_value)&0x8000u?OF:0u));
        }
#if MENU_CACHE_MUTATION == 6
        s.r.source_cursor=read16(&s,s.r.data_segment,(uint16_t)(s.r.base_value+CS_MenuLevelGroupGraphicSources));
#else
        s.r.source_cursor=read16(&s,s.cs,(uint16_t)(s.r.base_value+CS_MenuLevelGroupGraphicSources));
#endif
        s.r.value=486u;s.r.base_value=145u;s.r.argument=72u;s.r.count=0x041bu;s.r.frame_cursor=1u;
    }
    return bitmap(&s,game_ds,ret,ports);
}

LmnMenuCacheResult lmn_menu_cache_adapter(uint8_t *memory,const LmnRegs *r,
    uint16_t game_ds,enum LmnMenuCacheEntry entry,const LmnRasterBus *bus,
    const LmnRasterBytePorts *ports) {
    LmnVideoRestoreState in={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};
    LmnMenuCacheResult out=lmn_menu_cache_core(memory,r->cs,game_ds,&in,entry,bus,ports);
    Cache s={memory,bus,out.state,out.code_segment};
    if(out.status==LMN_MENU_CACHE_READY){out.continuation=pop(&s);out.state=s.r;}
    return out;
}

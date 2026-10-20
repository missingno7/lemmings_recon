#ifndef LEMMINGS_GAME_FOREGROUND_INTERNAL_H
#define LEMMINGS_GAME_FOREGROUND_INTERNAL_H
#include "special_blit.h"
#include "lemmings_sym.h"

/* Transient CPU roles only; every game byte stays on the canonical bus. */
typedef struct LmnForegroundState {
    uint8_t *memory;
    const LmnRasterBus *bus;
    LmnRegs *r;
} LmnForegroundState;
enum { FG_CF=1,FG_PF=4,FG_AF=16,FG_ZF=64,FG_SF=128,
       FG_IF=512,FG_OF=2048,FG_ARITH=0x8D5 };
static inline uint32_t fg_physical(uint16_t seg,uint16_t off) {
    return (((uint32_t)seg<<4)+off)&0xFFFFFu;
}
static inline uint8_t fg_read_at(LmnForegroundState *s,uint32_t at) {
    at&=0xFFFFFu;
    return s->bus&&s->bus->read_byte?s->bus->read_byte(s->bus->context,s->memory,at,s->r->flags):s->memory[at];
}
static inline void fg_write_at(LmnForegroundState *s,uint32_t at,uint8_t v) {
    at&=0xFFFFFu;
    if(s->bus&&s->bus->write_byte)s->bus->write_byte(s->bus->context,s->memory,at,v,s->r->flags);
    else s->memory[at]=v;
}
static inline uint8_t fg_read8(LmnForegroundState *s,uint16_t off) {
    return fg_read_at(s,fg_physical(s->r->ds,off));
}
static inline void fg_write8(LmnForegroundState *s,uint16_t off,uint8_t v) {
    fg_write_at(s,fg_physical(s->r->ds,off),v);
}
static inline uint16_t fg_word(LmnForegroundState *s,uint16_t seg,uint16_t off) {
    uint32_t at=fg_physical(seg,off);
    uint8_t lo=fg_read_at(s,at),hi=fg_read_at(s,at+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static inline void fg_store_word(LmnForegroundState *s,uint16_t seg,uint16_t off,uint16_t v) {
    uint32_t at=fg_physical(seg,off);
    fg_write_at(s,at,(uint8_t)v);fg_write_at(s,at+1u,(uint8_t)(v>>8));
}
static inline uint16_t fg_read16(LmnForegroundState *s,uint16_t off) {return fg_word(s,s->r->ds,off);}
static inline void fg_write16(LmnForegroundState *s,uint16_t off,uint16_t v) {fg_store_word(s,s->r->ds,off,v);}
static inline void fg_push(LmnForegroundState *s,uint16_t v) {
    s->r->sp=(uint16_t)(s->r->sp-2u);fg_store_word(s,s->r->ss,s->r->sp,v);
}
static inline uint16_t fg_pop(LmnForegroundState *s) {
    uint16_t v=fg_word(s,s->r->ss,s->r->sp);s->r->sp=(uint16_t)(s->r->sp+2u);return v;
}
static inline void fg_al(LmnForegroundState *s,uint16_t v) {s->r->ax=(uint16_t)((s->r->ax&0xFF00u)|(v&255u));}
static inline void fg_dl(LmnForegroundState *s,uint16_t v) {s->r->dx=(uint16_t)((s->r->dx&0xFF00u)|(v&255u));}
static inline uint16_t fg_szp(uint16_t v,int byte) {
    unsigned p=0;for(unsigned n=0;n<8;n++)p^=(v>>n)&1u;
    return (uint16_t)((p?0:FG_PF)|(v?0:FG_ZF)|(v&(byte?128u:0x8000u)?FG_SF:0));
}
static inline uint16_t fg_arithmetic(LmnForegroundState *s,uint16_t a,uint16_t b,int sub,int byte) {
    uint16_t mask=byte?255u:65535u,sign=byte?128u:0x8000u,v=(uint16_t)((sub?a-b:a+b)&mask);
    s->r->flags=(uint16_t)((s->r->flags&~FG_ARITH)|fg_szp(v,byte)|
        ((sub?a<b:(uint32_t)a+b>mask)?FG_CF:0)|((a^b^v)&FG_AF)|
        (((sub?(a^b):~(a^b))&(a^v)&sign)?FG_OF:0));return v;
}
static inline void fg_cmp(LmnForegroundState *s,uint16_t a,uint16_t b,int byte) {(void)fg_arithmetic(s,a,b,1,byte);}
static inline void fg_logic(LmnForegroundState *s,uint16_t v,int byte) {
    s->r->flags=(uint16_t)((s->r->flags&~FG_ARITH)|fg_szp(v,byte));
}
static inline uint16_t fg_incdec(LmnForegroundState *s,uint16_t v,int dec,int byte) {
    uint16_t cf=s->r->flags&FG_CF;v=fg_arithmetic(s,v,1,dec,byte);
    s->r->flags=(uint16_t)((s->r->flags&~FG_CF)|cf);return v;
}
static inline void fg_incdec_memory(LmnForegroundState *s,uint16_t off,int dec) {
    uint16_t before=s->r->flags;
    uint8_t v=(uint8_t)fg_incdec(s,fg_read8(s,off),dec,1);
    uint16_t after=s->r->flags;s->r->flags=before;fg_write8(s,off,v);s->r->flags=after;
}
static inline int fg_greater(const LmnForegroundState *s) {
    uint16_t f=s->r->flags;return !(f&FG_ZF)&&((!!(f&FG_SF))==(!!(f&FG_OF)));
}
static inline int fg_less(const LmnForegroundState *s) {
    uint16_t f=s->r->flags;return (!!(f&FG_SF))!=(!!(f&FG_OF));
}
static inline uint16_t fg_shr_one(LmnForegroundState *s,uint16_t v) {
    s->r->flags=(uint16_t)((s->r->flags&~(FG_CF|FG_PF|FG_ZF|FG_SF|FG_OF))|
        fg_szp(v>>1,0)|(v&1u?FG_CF:0)|(v&0x8000u?FG_OF:0));return v>>1;
}
#endif

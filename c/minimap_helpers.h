#ifndef LEMMINGS_MINIMAP_HELPERS_H
#define LEMMINGS_MINIMAP_HELPERS_H
#include "special_blit.h"
/* Canonical byte bus helpers and arithmetic, not machine-state dispatch. */
static inline uint32_t lmn_mm_physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}
static inline uint8_t lmn_mm_byte(uint8_t *m,uint32_t p,uint16_t flags,const LmnRasterBus *bus) {
    return bus&&bus->read_byte?bus->read_byte(bus->context,m,p,flags):m[p];
}
static inline void lmn_mm_putbyte(uint8_t *m,uint32_t p,uint8_t value,uint16_t flags,const LmnRasterBus *bus) {
    if(bus&&bus->write_byte)bus->write_byte(bus->context,m,p,value,flags);else m[p]=value;
}
static inline uint16_t lmn_mm_word(uint8_t *m,uint16_t segment,uint16_t offset,uint16_t flags,const LmnRasterBus *bus) {
    uint32_t p=lmn_mm_physical(segment,offset);uint8_t low=lmn_mm_byte(m,p,flags,bus);
    return (uint16_t)(low|((uint16_t)lmn_mm_byte(m,(p+1u)&0xfffffu,flags,bus)<<8));
}
static inline void lmn_mm_putword(uint8_t *m,uint16_t segment,uint16_t offset,uint16_t value,uint16_t flags,const LmnRasterBus *bus) {
    uint32_t p=lmn_mm_physical(segment,offset);
    lmn_mm_putbyte(m,p,(uint8_t)value,flags,bus);lmn_mm_putbyte(m,(p+1u)&0xfffffu,(uint8_t)(value>>8),flags,bus);
}
static inline void lmn_mm_push(uint8_t *m,uint16_t ss,uint16_t *sp,uint16_t value,uint16_t flags,const LmnRasterBus *bus) {
    *sp=(uint16_t)(*sp-2u);lmn_mm_putword(m,ss,*sp,value,flags,bus);
}
static inline uint16_t lmn_mm_pop(uint8_t *m,uint16_t ss,uint16_t *sp,uint16_t flags,const LmnRasterBus *bus) {
    uint16_t value=lmn_mm_word(m,ss,*sp,flags,bus);*sp=(uint16_t)(*sp+2u);return value;
}
static inline uint16_t lmn_mm_szp(uint16_t value,unsigned width) {
    unsigned parity=0;for(unsigned i=0;i<8;i++)parity^=(value>>i)&1u;
    return (uint16_t)((parity?0u:4u)|(value?0u:0x40u)|(value&(width==8?0x80u:0x8000u)?0x80u:0u));
}
static inline uint16_t lmn_mm_logic(uint16_t flags,uint16_t value,unsigned width) {
    return (uint16_t)((flags&~0x8d5u)|lmn_mm_szp(value,width));
}
static inline uint16_t lmn_mm_add(uint16_t flags,uint16_t a,uint16_t b) {
    uint32_t wide=(uint32_t)a+b;uint16_t value=(uint16_t)wide;
    return (uint16_t)((flags&~0x8d5u)|lmn_mm_szp(value,16)|(wide>65535u?1u:0u)|
        ((a^b^value)&16u)|((~(a^b)&(a^value)&0x8000u)?0x800u:0u));
}
static inline uint16_t lmn_mm_cmp(uint16_t flags,uint16_t a,uint16_t b) {
    uint16_t value=(uint16_t)(a-b);
    return (uint16_t)((flags&~0x8d5u)|lmn_mm_szp(value,16)|(a<b?1u:0u)|
        ((a^b^value)&16u)|(((a^b)&(a^value)&0x8000u)?0x800u:0u));
}
static inline uint16_t lmn_mm_inc(uint16_t flags,uint16_t value) {
    return (uint16_t)((lmn_mm_add(flags,value,1u)&~1u)|(flags&1u));
}
static inline uint16_t lmn_mm_shr(uint16_t flags,uint16_t value,unsigned width) {
    return (uint16_t)((flags&~0x8c5u)|lmn_mm_szp((uint16_t)(value>>1),width)|
        (value&1u)|(value&(width==8?0x80u:0x8000u)?0x800u:0u));
}
#endif

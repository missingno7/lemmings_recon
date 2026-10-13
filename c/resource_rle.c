#include "resource_rle.h"
#ifndef MUTATION
#define MUTATION 0
#endif
enum {DF=0x400,ARITH=0x8d5};
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xfffffu;}
static uint8_t take(const uint8_t *mem,uint16_t seg,uint16_t *cursor,uint16_t step) {
    uint8_t byte=mem[physical(seg,*cursor)];*cursor=(uint16_t)(*cursor+step);return byte;
}
LmnResourceRleResult lmn_decode_resource_rle_core(uint8_t *mem,uint16_t source_segment,
    uint16_t source_cursor,uint16_t output_segment,uint16_t output_cursor,
    uint16_t value,uint16_t count,uint16_t flags) {
    uint16_t step=(flags&DF) ? 0xffffu:1u;
    for(;;) {
        uint8_t control=take(mem,source_segment,&source_cursor,step);
        unsigned repeat;
        value=(uint16_t)((value&0xff00u)|control);
        if(control==0x80u)break;
        repeat=control>0x80u;
        count=repeat ? (uint16_t)(uint8_t)(1u-control):(uint16_t)(control+1u);
#if MUTATION == 1
        if(!repeat && count>1)count=(uint16_t)(count-1u);
#endif
        value=(uint16_t)((value&0xff00u)|count);
        if(repeat)value=(uint16_t)((value&0xff00u)|take(mem,source_segment,&source_cursor,step));
        do {
            uint8_t byte=repeat ? (uint8_t)value:take(mem,source_segment,&source_cursor,step);
            mem[physical(output_segment,output_cursor)]=byte;output_cursor=(uint16_t)(output_cursor+step);
            if(output_cursor==0) {
                uint16_t next=(uint16_t)(output_segment+0x1000u);
#if MUTATION == 2
                next=output_segment;
#endif
                output_segment=next;
                /* MOV AX,ES / ADD AX,1000 replaces AL even inside a repeat run. */
#if MUTATION == 3
                value=(uint16_t)((next&0xff00u)|(value&255u));
#else
                value=next;
#endif
            }
            count=(uint16_t)(count-1u);
        } while(count!=0);
    }
    flags=(uint16_t)((flags&(0xffffu^ARITH))|0x44u); /* final CMP AL,80 equal */
    {LmnResourceRleResult out={value,count,source_cursor,output_cursor,output_segment,flags};return out;}
}
void lmn_decode_resource_rle_adapter(uint8_t *mem,LmnRegs *r) {
    LmnResourceRleResult out=lmn_decode_resource_rle_core(mem,r->ds,r->si,r->es,r->di,r->ax,r->cx,r->flags);
    uint32_t p=physical(r->ss,r->sp);
    r->ax=out.value;r->cx=out.count;r->si=out.source_cursor;r->di=out.output_cursor;r->es=out.output_segment;r->flags=out.flags;
    r->ip=(uint16_t)(mem[p]|((uint16_t)mem[(p+1u)&0xfffffu]<<8));r->sp=(uint16_t)(r->sp+2u);
}

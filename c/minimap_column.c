#include "minimap_column.h"
#include "minimap_row.h"
#include "minimap_helpers.h"
#include "lemmings_sym.h"
#ifndef COLUMN_MUTATION
#define COLUMN_MUTATION 0
#endif
static void output(uint8_t *m,const LmnMinimapColumnCall *c,LmnMinimapColumnResult *s,uint16_t mirror,uint16_t value,const LmnRasterBus *bus) {
    s->value=value;lmn_mm_putword(m,c->stack_segment,mirror,value,s->flags,bus);
    bus->out_word(bus->context,s->port_or_population,value,s->flags);
}
LmnMinimapColumnResult lmn_update_minimap_column_core(uint8_t *m,const LmnMinimapColumnCall *c,const LmnRasterBus *bus) {
    LmnMinimapColumnResult s={0};uint16_t step;
    s.data_segment=c->data_segment;s.stack_offset=c->stack_offset;s.flags=c->flags;
    lmn_mm_push(m,c->stack_segment,&s.stack_offset,s.data_segment,s.flags,bus);
    s.output_cursor=CS_MinimapColumnBits;s.count=10u;s.value=0;s.flags=lmn_mm_logic(s.flags,0,16);
    lmn_mm_push(m,c->stack_segment,&s.stack_offset,c->code_segment,s.flags,bus);
    s.extra_segment=lmn_mm_pop(m,c->stack_segment,&s.stack_offset,s.flags,bus);
    step=s.flags&0x400u?0xfffeu:2u;
    do {
        lmn_mm_putword(m,s.extra_segment,s.output_cursor,0,s.flags,bus);
        s.output_cursor=(uint16_t)(s.output_cursor+step);s.count--;
    } while(s.count);
    s.source_cursor=lmn_mm_word(m,s.data_segment,SEG09A9_MinimapSourceColumnByteOffset,s.flags,bus);
    s.flags=lmn_mm_add(s.flags,s.source_cursor,16u);s.source_cursor=(uint16_t)(s.source_cursor+16u);
    s.flags=lmn_mm_cmp(s.flags,s.source_cursor,208u);
#if COLUMN_MUTATION == 1
    if(s.source_cursor>=208u){
#else
    if((s.flags&0x80u)==((s.flags&0x800u)>>4)){
#endif
        s.source_cursor=0;s.flags=lmn_mm_logic(s.flags,0,16);
    }
    lmn_mm_putword(m,s.data_segment,SEG09A9_MinimapSourceColumnByteOffset,s.source_cursor,s.flags,bus);
    s.output_cursor=s.source_cursor;
    s.flags=lmn_mm_add(s.flags,s.source_cursor,0x0d00u);s.source_cursor=(uint16_t)(s.source_cursor+0x0d00u);
    s.flags=lmn_mm_add(s.flags,s.source_cursor,0x4a40u);s.source_cursor=(uint16_t)(s.source_cursor+0x4a40u);
    for(unsigned i=0;i<4;i++){s.flags=lmn_mm_shr(s.flags,s.output_cursor,16);s.output_cursor>>=1;}
    s.flags=lmn_mm_add(s.flags,s.output_cursor,0xd320u);s.output_cursor=(uint16_t)(s.output_cursor+0xd320u);
    s.extra_segment=0xa000u;s.port_or_population=0x3c4u;
    output(m,c,&s,SEG143E_VgaMapMaskMirror,0x0f02u,bus);s.port_or_population=0x3ceu;
    output(m,c,&s,SEG143E_VgaSetResetMirror,0x0600u,bus);
    output(m,c,&s,SEG143E_VgaEnableSetResetMirror,0x0801u,bus);
    output(m,c,&s,SEG143E_VgaGraphicsModeMirror,0x0805u,bus);
    output(m,c,&s,SEG143E_VgaDataRotateMirror,0x0003u,bus);
    output(m,c,&s,SEG143E_VgaColorCareMirror,0x0807u,bus);
    output(m,c,&s,SEG143E_VgaColorCompareMirror,0x0802u,bus);
    output(m,c,&s,SEG143E_VgaBitMaskMirror,0xff08u,bus);
    s.count=20u;s.target_cursor=CS_MinimapColumnBits;
    do {
        LmnMinimapRowCall rc;LmnMinimapRowResult row;
        lmn_mm_push(m,c->stack_segment,&s.stack_offset,CS_MinimapColumnAfterRow,s.flags,bus);
        rc=(LmnMinimapRowCall){c->code_segment,s.extra_segment,c->stack_segment,s.stack_offset,
            s.source_cursor,s.target_cursor,s.count,s.flags};
        row=lmn_accumulate_minimap_row_core(m,&rc,bus);
        s.value=row.value;s.port_or_population=row.population_mask;s.count=row.count;s.source_cursor=row.source_cursor;
        s.stack_offset=row.stack_offset;s.flags=row.flags;
        if(row.changed_return){s.continuation=row.continuation;s.changed_return=1;return s;}
        s.continuation=lmn_mm_pop(m,c->stack_segment,&s.stack_offset,s.flags,bus);
        if(s.continuation!=CS_MinimapColumnAfterRow){s.changed_return=1;return s;}
        s.flags=lmn_mm_add(s.flags,s.source_cursor,0x680u);s.source_cursor=(uint16_t)(s.source_cursor+0x680u);
        s.flags=lmn_mm_inc(s.flags,s.target_cursor);s.target_cursor++;
        s.count=(uint16_t)(s.count-1u);
    } while(s.count);
    s.port_or_population=0x3ceu;output(m,c,&s,SEG143E_VgaGraphicsModeMirror,5u,bus);
#if COLUMN_MUTATION == 2
    s.count=20u;
#else
    s.count=19u;
#endif
    s.target_cursor=CS_MinimapColumnBits;
    do {
        uint8_t bits=lmn_mm_byte(m,lmn_mm_physical(c->code_segment,s.target_cursor),s.flags,bus);
        uint8_t old=lmn_mm_byte(m,lmn_mm_physical(s.extra_segment,s.output_cursor),s.flags,bus);
        s.value=(uint16_t)(((uint16_t)bits<<8)|old);
        lmn_mm_putbyte(m,lmn_mm_physical(s.extra_segment,s.output_cursor),bits,s.flags,bus);
        s.flags=lmn_mm_add(s.flags,s.output_cursor,13u);s.output_cursor=(uint16_t)(s.output_cursor+13u);
        s.flags=lmn_mm_inc(s.flags,s.target_cursor);s.target_cursor++;
        s.count=(uint16_t)(s.count-1u);
    } while(s.count);
    s.data_segment=lmn_mm_pop(m,c->stack_segment,&s.stack_offset,s.flags,bus);
#if COLUMN_MUTATION == 3
    s.data_segment=c->data_segment;
#endif
    return s;
}
void lmn_update_minimap_column_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnMinimapColumnCall c={r->cs,r->ds,r->ss,r->sp,r->flags};
    LmnMinimapColumnResult s=lmn_update_minimap_column_core(m,&c,bus);
    r->ax=s.value;r->bx=s.target_cursor;r->cx=s.count;r->dx=s.port_or_population;r->si=s.source_cursor;r->di=s.output_cursor;
    r->ds=s.data_segment;r->es=s.extra_segment;r->sp=s.stack_offset;r->flags=s.flags;
    r->ip=s.changed_return?s.continuation:lmn_mm_pop(m,r->ss,&r->sp,r->flags,bus);
}

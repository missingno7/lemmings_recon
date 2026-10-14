#include "minimap_row.h"
#include "minimap_sample.h"
#include "minimap_helpers.h"
#include "lemmings_sym.h"
#ifndef ROW_MUTATION
#define ROW_MUTATION 0
#endif
LmnMinimapRowResult lmn_accumulate_minimap_row_core(uint8_t *m,const LmnMinimapRowCall *c,const LmnRasterBus *bus) {
    LmnMinimapRowResult s={0};s.stack_offset=c->stack_offset;s.flags=c->flags;s.source_cursor=c->source_cursor;
    lmn_mm_push(m,c->stack_segment,&s.stack_offset,c->count,s.flags,bus);
    lmn_mm_push(m,c->stack_segment,&s.stack_offset,c->source_cursor,s.flags,bus);
    s.population_mask=0x80u;s.count=8u;
    do {
        LmnMinimapSampleResult sample;
        lmn_mm_push(m,c->stack_segment,&s.stack_offset,CS_MinimapRowAfterSample,s.flags,bus);
        sample=lmn_accumulate_minimap_sample_core(m,c->code_segment,c->extra_segment,c->stack_segment,
            s.stack_offset,s.source_cursor,c->target_cursor,(uint8_t)s.population_mask,s.count,s.flags,bus);
        s.value=sample.value;s.population_mask=sample.population_mask;s.count=sample.count;
        s.stack_offset=sample.stack_offset;s.flags=sample.flags;
        s.continuation=lmn_mm_pop(m,c->stack_segment,&s.stack_offset,s.flags,bus);
#if ROW_MUTATION == 3
        s.continuation=CS_MinimapRowAfterSample;
#endif
        if(s.continuation!=CS_MinimapRowAfterSample){s.changed_return=1;return s;}
        s.flags=lmn_mm_add(s.flags,s.source_cursor,2u);s.source_cursor=(uint16_t)(s.source_cursor+2u);
        s.flags=lmn_mm_shr(s.flags,(uint8_t)s.population_mask,8);
#if ROW_MUTATION == 1
        s.population_mask=(uint16_t)((s.population_mask&0xff00u)|((uint8_t)s.population_mask<<1));
#else
        s.population_mask=(uint16_t)((s.population_mask&0xff00u)|((uint8_t)s.population_mask>>1));
#endif
        s.count=(uint16_t)(s.count-1u);
    } while(s.count);
    s.source_cursor=lmn_mm_pop(m,c->stack_segment,&s.stack_offset,s.flags,bus);
#if ROW_MUTATION == 2
    s.source_cursor=c->source_cursor;
#endif
    s.count=lmn_mm_pop(m,c->stack_segment,&s.stack_offset,s.flags,bus);
    return s;
}
void lmn_accumulate_minimap_row_adapter(uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnMinimapRowCall c={r->cs,r->es,r->ss,r->sp,r->si,r->bx,r->cx,r->flags};
    LmnMinimapRowResult s=lmn_accumulate_minimap_row_core(m,&c,bus);
    r->ax=s.value;r->dx=s.population_mask;r->cx=s.count;r->si=s.source_cursor;r->sp=s.stack_offset;r->flags=s.flags;
    r->ip=s.changed_return?s.continuation:lmn_mm_pop(m,r->ss,&r->sp,r->flags,bus);
}

#include "view_scroll.h"
#include "game_foreground_internal.h"
#ifndef VIEW_SCROLL_MUTATION
#define VIEW_SCROLL_MUTATION 0
#endif

LmnViewScrollResult lmn_view_scroll_core(uint8_t *memory,const LmnRegs *registers,
    LmnViewScrollEntry entry,const LmnRasterBus *bus) {
    LmnViewScrollResult out={*registers,0};LmnRegs *r=&out.registers;
    LmnForegroundState s={memory,bus,r};
    if(entry==LMN_VIEW_SCROLL_LEFT)goto left;
    fg_al(&s,fg_read8(&s,SEG09A9_KeyboardScanCodeByte));
    fg_cmp(&s,(uint8_t)r->ax,0x2C,1);
    if(r->flags&FG_ZF) {
        fg_cmp(&s,fg_read8(&s,SEG09A9_StatusIconRefreshCounter),0,1);
        if(!(r->flags&FG_ZF))goto key_return;
        fg_incdec_memory(&s,SEG09A9_EntityActionSelector,1);
        fg_cmp(&s,fg_read8(&s,SEG09A9_EntityActionSelector),1,1);
        if(r->flags&FG_ZF)fg_write8(&s,SEG09A9_EntityActionSelector,
            VIEW_SCROLL_MUTATION==1?8:9);
        goto key_return;
    }
    fg_cmp(&s,(uint8_t)r->ax,0x2D,1);
    if(r->flags&FG_ZF) {
        fg_cmp(&s,fg_read8(&s,SEG09A9_StatusIconRefreshCounter),0,1);
        if(!(r->flags&FG_ZF))goto key_return;
        fg_incdec_memory(&s,SEG09A9_EntityActionSelector,0);
        fg_cmp(&s,fg_read8(&s,SEG09A9_EntityActionSelector),0xA,1);
        if(!(r->flags&FG_ZF))goto key_return;
        fg_write8(&s,SEG09A9_EntityActionSelector,2);r->ip=CS_ScrollViewRight-1u;return out;
    }
    r->ax=fg_read16(&s,SEG09A9_PointerY);r->ax=fg_arithmetic(&s,r->ax,8,0,0);
    fg_cmp(&s,r->ax,0xC0,0);
    if(VIEW_SCROLL_MUTATION==2?(r->ax>=0xC0):!fg_less(&s))goto none;
    r->ax=fg_read16(&s,SEG09A9_PointerX);fg_cmp(&s,r->ax,8,0);
    if(r->flags&FG_ZF)goto left;
    fg_cmp(&s,r->ax,0x148,0);if(!(r->flags&FG_ZF))goto none;
    r->ax=fg_read16(&s,SEG09A9_LevelViewOriginPixels);fg_cmp(&s,r->ax,0x500,0);
    if(VIEW_SCROLL_MUTATION==3?r->ax>=0x500:(r->flags&FG_ZF))goto rebuild;
    r->ax=fg_arithmetic(&s,r->ax,8,0,0);
    fg_logic(&s,fg_read16(&s,SEG09A9_InputButtonsWord)&2u,0);
    if(!(r->flags&FG_ZF)) {
        fg_cmp(&s,r->ax,0x500,0);if(!(r->flags&FG_ZF))r->ax=fg_arithmetic(&s,r->ax,8,0,0);
    }
    goto store;
left:
    r->ax=fg_read16(&s,SEG09A9_LevelViewOriginPixels);fg_cmp(&s,r->ax,0x10,0);
    if(!fg_greater(&s))goto rebuild;
    r->ax=fg_arithmetic(&s,r->ax,8,1,0);
    fg_logic(&s,fg_read16(&s,SEG09A9_InputButtonsWord)&2u,0);
    if(!(r->flags&FG_ZF)) {
        fg_cmp(&s,r->ax,0x10,0);
        if(!fg_greater(&s)&&VIEW_SCROLL_MUTATION!=4)goto rebuild;
        r->ax=fg_arithmetic(&s,r->ax,8,1,0);
    }
store:
    fg_write16(&s,SEG09A9_LevelViewOriginPixels,r->ax);r->dx=r->ax;
    for(unsigned n=0;n<3;n++)r->dx=fg_shr_one(&s,r->dx);
    fg_write16(&s,SEG09A9_LevelViewOriginBytes,r->dx);
rebuild:
    {
        uint32_t at=fg_physical(r->cs,CS_ViewVisibilityStackSegmentOperand);
        uint16_t runtime=(uint16_t)(memory[at]|((uint16_t)memory[(at+1u)&0xFFFFFu]<<8));
        LmnViewVisibilityCall call={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,
            r->cs,r->ds,r->es,r->ss,r->sp,r->flags,runtime};
        LmnViewVisibilityResult child=lmn_rebuild_view_visibility_map_core(memory,&call,bus);
        r->ax=child.value;r->bx=child.map_cursor;r->cx=child.count;r->dx=child.auxiliary_value;
        r->si=child.record_cursor;r->di=child.object_cursor;r->bp=child.candidate_y;
        r->cs=child.code_segment;r->ds=child.data_segment;r->es=child.extra_segment;
        r->ss=child.stack_segment;r->sp=child.stack_offset;r->flags=child.flags;r->ip=child.continuation;
        out.status=child.status;return out;
    }
key_return:r->ip=CS_SelectorKeyReturn;return out;
none:r->ip=CS_EdgeScrollNoneReturn;return out;
}
LmnViewScrollResult lmn_view_scroll_adapter(uint8_t *memory,const LmnRegs *registers,
    LmnViewScrollEntry entry,const LmnRasterBus *bus) {
    LmnViewScrollResult out=lmn_view_scroll_core(memory,registers,entry,bus);
    if(!out.status){LmnForegroundState s={memory,bus,&out.registers};out.registers.ip=fg_pop(&s);}
    return out;
}

#include "level_start.h"
#include "lemmings_sym.h"

#ifndef LEVEL_START_MUTATION
#define LEVEL_START_MUTATION 0
#endif
typedef struct Start {
    uint8_t *memory;
    const LmnRasterBus *bus;
    LmnLevelStartResult out;
} Start;
static uint32_t physical(uint16_t seg,uint16_t off) {return (((uint32_t)seg<<4)+off)&0xFFFFFu;}
static uint8_t read_at(Start *s,uint32_t at) {
    at&=0xFFFFFu;return s->bus&&s->bus->read_byte?
        s->bus->read_byte(s->bus->context,s->memory,at,s->out.registers.flags):s->memory[at];
}
static void write_at(Start *s,uint32_t at,uint8_t value) {
    at&=0xFFFFFu;
    if(s->bus&&s->bus->write_byte)s->bus->write_byte(s->bus->context,s->memory,at,value,s->out.registers.flags);
    else s->memory[at]=value;
}
static void push(Start *s,uint16_t value) {
    LmnRegs *r=&s->out.registers;r->sp=(uint16_t)(r->sp-2u);uint32_t at=physical(r->ss,r->sp);
    write_at(s,at,(uint8_t)value);write_at(s,at+1u,(uint8_t)(value>>8));
}
static uint16_t pop(Start *s) {
    LmnRegs *r=&s->out.registers;uint32_t at=physical(r->ss,r->sp);
    uint8_t a=read_at(s,at),b=read_at(s,at+1u);r->sp=(uint16_t)(r->sp+2u);return (uint16_t)(a|((uint16_t)b<<8));
}
static int returned(Start *s,uint16_t expected) {
    s->out.registers.ip=pop(s);
#if LEVEL_START_MUTATION == 3
    s->out.registers.ip=expected;
#endif
    if(s->out.registers.ip!=expected){s->out.status=LMN_LEVEL_START_CHANGED_RETURN;return 0;}return 1;
}
static void apply(Start *s,const LmnResourceSelectionFullState *v,uint16_t ip) {
    LmnRegs *r=&s->out.registers;
    r->ax=v->value;r->bx=v->base_value;r->cx=v->count;r->dx=v->argument;
    r->si=v->source_cursor;r->di=v->output_cursor;r->bp=v->frame_cursor;
    r->ds=v->data_segment;r->es=v->extra_segment;r->ss=v->stack_segment;r->sp=v->stack_offset;
    r->flags=v->flags;r->ip=ip;
}
static int resource_binding(const LmnLevelStartServices *s) {
    if(!s||!s->segments||!s->resources||!s->resources->selection)return 0;
    const LmnResourceSelectionServices *v=s->resources->selection;
    return v->files&&v->files->open_readonly&&v->files->attributes&&v->files->retry_ui&&
        v->io&&v->io->query_size&&v->io->read&&v->raw&&v->raw->open_readonly&&v->raw->read&&v->raw->close;
}
LmnLevelStartResult lmn_start_selected_level(uint8_t *memory,const LmnRegs *registers,
    uint16_t game_ds,LmnLevelStartEntry entry,const LmnLevelStartServices *services) {
    Start s={memory,services?services->bus:0,{*registers,0,0,0}};LmnRegs *r=&s.out.registers;
    if(entry==LMN_LEVEL_START_FROM_MENU) {
#if LEVEL_START_MUTATION != 1
        write_at(&s,physical(r->ds,SEG09A9_LevelOutcomeSuccessByte),0);
#endif
    }
    push(&s,r->ds);r->es=pop(&s);r->di=0;r->cx=0x0FCAu;r->ax&=0xFF00u;
    r->flags=(uint16_t)((r->flags&~0x8D5u)|0x44u);
    do {
        write_at(&s,physical(r->es,r->di),(uint8_t)r->ax);
#if LEVEL_START_MUTATION == 2
        r->di=(uint16_t)(r->di+1u);
#else
        r->di=(uint16_t)(r->di+((r->flags&0x400u)?0xFFFFu:1u));
#endif
        --r->cx;
    }while(r->cx);
    push(&s,CS_LevelStartAfterResources);r->ip=CS_LoadSelectedLevelResources;
    if(!resource_binding(services)){s.out.status=LMN_LEVEL_START_UNBOUND_RESOURCES;return s.out;}
    LmnDatFileCall call={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};
    LmnResourceSelectionFullResult resource=lmn_load_selected_resources_full_bus_core(memory,
        services->error_main_data_segment,&call,services->segments,services->resources,s.bus);
    apply(&s,&resource.state,resource.continuation);
    if(resource.status){s.out.status=LMN_LEVEL_START_RESOURCE_STOP;s.out.child_status=(uint16_t)resource.status;return s.out;}
    if(!returned(&s,CS_LevelStartAfterResources))return s.out;
    push(&s,CS_LevelStartAfterBriefing);r->ip=CS_ShowLevelBriefing;
    if(!services->briefing){s.out.status=LMN_LEVEL_START_UNBOUND_BRIEFING;return s.out;}
    LmnBriefingServices binding=*services->briefing;binding.bus=s.bus;
    LmnBriefingResult briefing=lmn_show_level_briefing_core(memory,r,game_ds,&binding);
    *r=briefing.registers;
    if(briefing.status){s.out.status=LMN_LEVEL_START_BRIEFING_STOP;s.out.child_status=briefing.status;s.out.detail=briefing.child_status;return s.out;}
    if(r->ip==CS_MenuRefresh4401) {
#if LEVEL_START_MUTATION == 4
        (void)pop(&s);
#endif
        return s.out;
    }
    if(!returned(&s,CS_LevelStartAfterBriefing))return s.out;
    r->ip=CS_EnterLoadedLevelGame;return s.out;
}

#include "game_initialize.h"
#include "lemmings_sym.h"
#include "view_visibility.h"
#include "entity_create.h"
#include "status_initialize.h"
#include "timer_tail.h"
#include "object_animation.h"
#include "object_drawing_tick.h"
#include "status_display_full.h"

#ifndef GAME_INITIALIZE_MUTATION
#define GAME_INITIALIZE_MUTATION 0
#endif

enum {CF=1,PF=4,AF=16,ZF=64,SF=128,DF=1024,OF=2048,ARITH=0x8D5};

static uint32_t physical(uint16_t segment,uint16_t offset){
    return (((uint32_t)segment<<4)+offset)&0xFFFFFu;
}

static void write_at(uint8_t *memory,const LmnRasterBus *bus,uint16_t flags,
                     uint32_t address,uint8_t value){
    address&=0xFFFFFu;
    if(bus&&bus->write_byte)bus->write_byte(bus->context,memory,address,value,flags);
    else memory[address]=value;
}

static uint8_t read_at(uint8_t *memory,const LmnRasterBus *bus,uint16_t flags,
                       uint32_t address){
    address&=0xFFFFFu;
    return bus&&bus->read_byte?bus->read_byte(bus->context,memory,address,flags):memory[address];
}

static void write8(uint8_t *memory,const LmnRasterBus *bus,const LmnRegs *r,
                   uint16_t offset,uint8_t value){
    write_at(memory,bus,r->flags,physical(r->ds,offset),value);
}

static void write16(uint8_t *memory,const LmnRasterBus *bus,const LmnRegs *r,
                    uint16_t offset,uint16_t value){
    uint32_t address=physical(r->ds,offset);
    write_at(memory,bus,r->flags,address,(uint8_t)value);
    write_at(memory,bus,r->flags,address+1u,(uint8_t)(value>>8));
}

static uint16_t read16(uint8_t *memory,const LmnRasterBus *bus,const LmnRegs *r,
                       uint16_t offset){
    uint32_t address=physical(r->ss,offset);
    uint8_t low=read_at(memory,bus,r->flags,address);
    uint8_t high=read_at(memory,bus,r->flags,address+1u);
    return (uint16_t)(low|((uint16_t)high<<8));
}

static uint16_t push_ss_pop_es(uint8_t *memory,const LmnRasterBus *bus,LmnRegs *r){
    r->sp=(uint16_t)(r->sp-2u);
    uint32_t address=physical(r->ss,r->sp);
    write_at(memory,bus,r->flags,address,(uint8_t)r->ss);
    write_at(memory,bus,r->flags,address+1u,(uint8_t)(r->ss>>8));
    uint16_t value=read16(memory,bus,r,r->sp);
    r->sp=(uint16_t)(r->sp+2u);
    return value;
}

static void push_word(uint8_t *memory,const LmnRasterBus *bus,LmnRegs *r,uint16_t value){
    r->sp=(uint16_t)(r->sp-2u);
    uint32_t address=physical(r->ss,r->sp);
    write_at(memory,bus,r->flags,address,(uint8_t)value);
    write_at(memory,bus,r->flags,address+1u,(uint8_t)(value>>8));
}

static uint16_t pop_word(uint8_t *memory,const LmnRasterBus *bus,LmnRegs *r){
    uint16_t value=read16(memory,bus,r,r->sp);
    r->sp=(uint16_t)(r->sp+2u);
    return value;
}

static void zero_al(LmnRegs *r){
    r->ax&=0xFF00u;
    r->flags=(uint16_t)((r->flags&~ARITH)|PF|ZF);
}

static void stosb(uint8_t *memory,const LmnRasterBus *bus,LmnRegs *r){
    uint16_t step=(r->flags&DF)?0xFFFFu:1u;
    while(r->cx){
        write_at(memory,bus,r->flags,physical(r->es,r->di),(uint8_t)r->ax);
        r->di=(uint16_t)(r->di+step);
        --r->cx;
    }
}

/* Only the original arithmetic widths; DEC preserves incoming CF. */
static uint16_t arithmetic(LmnRegs *r,uint16_t a,uint16_t b,unsigned carry,
                           int subtract,int byte){
    uint32_t mask=byte?255u:65535u,sign=byte?128u:32768u;
    uint32_t wide=subtract?(uint32_t)a-b-carry:(uint32_t)a+b+carry;
    uint16_t value=(uint16_t)(wide&mask),f=0;
    if(subtract?(uint32_t)a<(uint32_t)b+carry:wide>mask)f|=CF;
    if((a^b^value)&16u)f|=AF;
    if((subtract?(a^b):~(a^b))&(a^value)&sign)f|=OF;
    if(!value)f|=ZF;
    if(value&sign)f|=SF;
    unsigned low=value&255u,parity=0;
    for(unsigned i=0;i<8u;++i)parity^=(low>>i)&1u;
    if(!parity)f|=PF;
    r->flags=(uint16_t)((r->flags&~ARITH)|f);
    return value;
}

static uint16_t decrement(LmnRegs *r,uint16_t value){
    uint16_t cf=r->flags&CF;
    value=arithmetic(r,value,1,0,1,0);
    r->flags=(uint16_t)((r->flags&~CF)|cf);
    return value;
}

static int foreground_poll(uint8_t *memory,LmnGameInitializeResult *out,
                           const LmnForegroundPoll *poll,uint16_t site){
    out->registers.ip=site;
    if(!poll||!poll->poll){out->status=LMN_GAME_INITIALIZE_POLL_REQUIRED;return 0;}
    uint16_t status=poll->poll(poll->context,memory,&out->registers,site);
    if(status){out->status=LMN_GAME_INITIALIZE_POLL_STOP;out->service_status=status;return 0;}
    return 1;
}

/* CONDITIONAL readiness: known03E7..04CF flow and child handoffs; canonical
   DS owns the flag/wait words, INT08:189E produces FF and0164 consumes them.
   Children retain their provider/alias domains. IRQ delivery is explicit only
   at04AA/04BA; general preemption and whole-game scheduling remain open.
   The maintained ASM contract is unchanged (see docs/game-initialize.md). */
static LmnGameInitializeResult finish_session(uint8_t *memory,
    LmnGameInitializeResult out,const LmnGameInitializeServices *services){
    LmnRegs *r=&out.registers;
    const LmnRasterBus *bus=services?services->bus:0;
    const LmnRasterBytePorts *ports=services?services->ports:0;
    uint8_t disabled=read_at(memory,bus,r->flags,
        physical(r->ds,SEG09A9_MouseServicesDisabledByte));
    (void)arithmetic(r,disabled,255,0,1,1);
#if GAME_INITIALIZE_MUTATION == 9
    if(!disabled){
#else
    if(!(r->flags&ZF)){
#endif
        r->ax=4;r->cx=150;r->dx=100;
        LmnInterruptResult mouse=lmn_interrupt_service(memory,r,0x33,
            CS_InitializeGameVisibilityAndStatus,services?services->mouse:0,bus);
        if(mouse.status){
            out.status=mouse.status==LMN_INTERRUPT_CHANGED_IRET?
                LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN:LMN_GAME_INITIALIZE_CHILD_STOP;
            out.child_status=mouse.status;out.service_status=mouse.service_status;return out;
        }
    }
    static const uint16_t entries[]={CS_RebuildViewVisibilityMap,
        CS_CreateEntityRecordIfDue,CS_SeedGameFadePalette,CS_SelectLevelSoundId,
        CS_InitializeGameDrawingPages,CS_InitializeStatusDisplay,CS_InstallGameTimerVector,
        CS_AdvanceLevelObjectAnimations,CS_DrawLevelObjectGraphics,
        CS_CopyStatusBackdropToDrawingPage,CS_UpdateStatusDisplay};
    static const uint16_t resumes[]={CS_InitializeGameAfterVisibility,
        CS_InitializeGameAfterFirstCreate,CS_InitializeGameAfterFadeSeed,
        CS_InitializeGameAfterSoundSelect,CS_InitializeGameAfterDrawingPages,
        CS_InitializeGameAfterStatusInit,CS_InitializeGameAfterTimerInstall,
        CS_InitializeGameAfterObjectAnimations,CS_InitializeGameAfterObjectGraphics,
        CS_InitializeGameAfterStatusBackdrop,CS_InitializeGameAfterStatusDisplay};
    for(unsigned n=0;n<11u;++n){
        uint16_t cs=r->cs,status=0,service=0;int changed=0;
        push_word(memory,bus,r,resumes[n]);r->ip=entries[n];
        switch(n){
        case 0:status=lmn_rebuild_view_visibility_map_live_adapter(memory,r,bus);break;
        case 1:status=lmn_create_entity_record_adapter(memory,r,bus);break;
        case 2:case 3:case 4:case 9:{
            LmnGamePrepareEntry entry=n==2?LMN_GAME_PREPARE_FADE_PALETTE:
                n==3?LMN_GAME_PREPARE_SOUND:n==4?LMN_GAME_PREPARE_DRAWING_PAGES:
                LMN_GAME_PREPARE_STATUS_BACKDROP;
            LmnGamePrepareResult child=lmn_game_prepare_adapter(memory,r,entry,ports,bus);
            *r=child.registers;status=child.status;service=child.child_status;
            changed=status==LMN_GAME_PREPARE_CHANGED_RETURN;break;
        }
        case 5:status=lmn_initialize_status_display_adapter(memory,r,bus);
            changed=status==LMN_STATUS_INITIALIZE_CHANGED_CHILD_RETURN;break;
        case 6:{
            LmnTimerTailResult child=lmn_install_game_timer_adapter(memory,r,
                services?services->dos:0,ports,bus);
            *r=child.registers;status=child.status;service=child.service_status;
            changed=status==LMN_TIMER_TAIL_CHANGED_INTERRUPT_RETURN||
                status==LMN_TIMER_TAIL_CHANGED_CHILD_RETURN;break;
        }
        case 7:status=lmn_advance_level_object_animations_adapter(memory,r,bus);break;
        case 8:status=lmn_draw_level_object_graphics_adapter(memory,r,
            services?services->game_data_segment:0,bus,ports);
            changed=status==LMN_OBJECT_DRAWING_TICK_CHANGED_CHILD_NEAR||
                status==LMN_OBJECT_DRAWING_TICK_CHANGED_FAR_RETURN;break;
        case 10:status=lmn_update_status_display_full_adapter(memory,r,bus);
            changed=status==LMN_STATUS_DISPLAY_CHANGED_CHILD_RETURN;break;
        }
#if GAME_INITIALIZE_MUTATION == 10
        if(n==6u)status=0;
#endif
        if(status){
            out.status=changed?LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN:LMN_GAME_INITIALIZE_CHILD_STOP;
            out.child_status=status;out.service_status=service;return out;
        }
#if GAME_INITIALIZE_MUTATION == 11
        r->ip=resumes[n];
#endif
        if(r->cs!=cs||r->ip!=resumes[n]){
            out.status=LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN;return out;
        }
    }
    r->cx=0;r->flags=(uint16_t)((r->flags&~ARITH)|ZF|PF);
    r->dx=0;r->flags=(uint16_t)((r->flags&~ARITH)|ZF|PF);
    write8(memory,bus,r,SEG09A9_TimerChainFlag1FCF,0);
    const LmnForegroundPoll *poll=services?services->foreground:0;
    do{
        if(!foreground_poll(memory,&out,poll,CS_GameWaitCalibrationFirstEdge))return out;
        (void)arithmetic(r,read_at(memory,bus,r->flags,
            physical(r->ds,SEG09A9_TimerChainFlag1FCF)),255,0,1,1);
    }while(!(r->flags&ZF));
    write8(memory,bus,r,SEG09A9_TimerChainFlag1FCF,0);
    do{
        r->cx=decrement(r,r->cx);
#if GAME_INITIALIZE_MUTATION == 12
        if(r->cx==65535u)r->dx=decrement(r,r->dx);
#else
        if(!r->cx)r->dx=decrement(r,r->dx);
#endif
        if(!foreground_poll(memory,&out,poll,CS_GameCheckCalibrationSecondEdge))return out;
        (void)arithmetic(r,read_at(memory,bus,r->flags,
            physical(r->ds,SEG09A9_TimerChainFlag1FCF)),255,0,1,1);
    }while(!(r->flags&ZF));
    r->cx=arithmetic(r,r->cx,r->cx,0,0,0);
#if GAME_INITIALIZE_MUTATION == 13
    r->flags&=(uint16_t)~CF;
#endif
    r->dx=arithmetic(r,r->dx,r->dx,r->flags&CF,0,0);
#if GAME_INITIALIZE_MUTATION != 14
    r->dx=arithmetic(r,0,r->dx,0,1,0);
#endif
    write16(memory,bus,r,SEG09A9_ForegroundWaitLowWord,r->cx);
    write16(memory,bus,r,SEG09A9_ForegroundWaitHighWord,r->dx);
    r->ip=pop_word(memory,bus,r);
    out.status=LMN_GAME_INITIALIZE_RETURNED;return out;
}

LmnGameInitializeResult lmn_initialize_game_core(uint8_t *memory,
    const LmnRegs *registers,const LmnGameInitializeServices *services){
    const LmnRasterBus *bus=services?services->bus:0;
    LmnGameInitializeResult out={*registers,LMN_GAME_INITIALIZE_AT_MOUSE_SERVICE_CHECK,0,0};
    LmnRegs *r=&out.registers;

    /* Literal stores from 03E7..0449, in their original order. */
    write16(memory,bus,r,0x0000,0x0218);
    write16(memory,bus,r,0x0002,0x0043);
    write8(memory,bus,r,0x001A,0x00);
    write16(memory,bus,r,SEG09A9_PointerX,0x0096);
    write16(memory,bus,r,SEG09A9_PointerY,0x0064);
    write8(memory,bus,r,SEG09A9_LevelCreationLimit,0xC8);
    write8(memory,bus,r,0x004A,0x00);
    write8(memory,bus,r,0x20A9,0x30);
    write8(memory,bus,r,0x20AA,0x30);
    write8(memory,bus,r,0x0085,0x11);
    write8(memory,bus,r,0x0086,0x11);
    write8(memory,bus,r,SEG09A9_EntityActionSelector,0x02);
    write8(memory,bus,r,SEG09A9_StatusIconDisplaySnapshot,0x03);
    write8(memory,bus,r,SEG09A9_EntityPointCount,0x50);
    write8(memory,bus,r,0x004E,0x01);

    zero_al(r);
    write8(memory,bus,r,SEG09A9_InputActionSnapshot1FD4,(uint8_t)r->ax);
    write8(memory,bus,r,SEG09A9_ForegroundCounter1FD3,(uint8_t)r->ax);
    write8(memory,bus,r,0x004F,(uint8_t)r->ax);
    write8(memory,bus,r,SEG09A9_DrawingDirtyCellsEnabledByte,(uint8_t)r->ax);
    write8(memory,bus,r,SEG09A9_ForegroundCounter0052,(uint8_t)r->ax);
    write8(memory,bus,r,SEG09A9_EntityCreationGate,(uint8_t)r->ax);

    /* Preserve both actual PUSH SS / POP ES stack frames and their bus effects. */
    r->es=push_ss_pop_es(memory,bus,r);
    r->di=0x0012;
    r->cx=0x42A0;
    zero_al(r);
#if GAME_INITIALIZE_MUTATION == 2
    r->flags&=(uint16_t)~DF;
#endif
    stosb(memory,bus,r);

    r->es=push_ss_pop_es(memory,bus,r);
    r->di=0x42B2;
    r->cx=0x0642;
    zero_al(r);
#if GAME_INITIALIZE_MUTATION == 3
    ++r->di;
#endif
    stosb(memory,bus,r);

#if GAME_INITIALIZE_MUTATION == 1
    write8(memory,bus,r,SEG09A9_PointerX,0x95);
#endif

    /* CALL SetupGameVideoAndSpriteCallbacks at0462; retain its real stack word. */
    const uint16_t resume=CS_InitializeGameAfterVideoSetup;
    uint16_t expected_cs=r->cs;
    push_word(memory,bus,r,resume);
    r->ip=CS_SetupGameVideoAndSpriteCallbacks;
    const LmnVideoProbeServices *video=services?services->video:0;
    LmnVideoProbeServices binding={video?video->bios:0,video?video->ports:0,bus};
    LmnVideoProbeResult child=lmn_video_probe_core(memory,r,LMN_VIDEO_GAME_SETUP,&binding);
    *r=child.registers;
    if(child.status){
        out.status=LMN_GAME_INITIALIZE_CHILD_STOP;
        out.child_status=child.status;
        out.service_status=child.service_status;
        return out;
    }
    r->ip=pop_word(memory,bus,r);
#if GAME_INITIALIZE_MUTATION == 4
    r->ip=resume;
#endif
    if(r->cs!=expected_cs||r->ip!=resume){
        out.status=LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN;
        return out;
    }
    r->ip=resume;

    /* CALL PublishGameBasePalette at0465; it returns to the next live word. */
    const uint16_t palette_resume=CS_InitializeGameAfterPalette;
    expected_cs=r->cs;
    push_word(memory,bus,r,palette_resume);
    r->ip=CS_PublishGameBasePalette;
    LmnGamePrepareResult palette=lmn_game_prepare_core(memory,r,
        LMN_GAME_PREPARE_BASE_PALETTE,services?services->ports:0,bus);
    *r=palette.registers;
    if(palette.status){
        out.status=palette.status==LMN_GAME_PREPARE_CHANGED_RETURN
            ?LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN:LMN_GAME_INITIALIZE_CHILD_STOP;
        out.child_status=palette.status;
        out.service_status=palette.child_status;
        return out;
    }
    r->ip=pop_word(memory,bus,r);
#if GAME_INITIALIZE_MUTATION == 5
    r->ip=palette_resume;
#endif
    if(r->cs!=expected_cs||r->ip!=palette_resume){
        out.status=LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN;
        return out;
    }
    r->ip=palette_resume;

    /* CALL CalibrateGameTimerReload at0468 with the live display services. */
    const uint16_t timer_resume=CS_InitializeGameAfterTimerCalibration;
    expected_cs=r->cs;
    push_word(memory,bus,r,timer_resume);
    r->ip=CS_CalibrateGameTimerReload;
    LmnVideoProbeResult timer=lmn_video_probe_core(memory,r,
        LMN_VIDEO_CALIBRATE,services?services->video:0);
    *r=timer.registers;
    if(timer.status){
        out.status=LMN_GAME_INITIALIZE_CHILD_STOP;
        out.child_status=timer.status;
        out.service_status=timer.service_status;
        return out;
    }
    r->ip=pop_word(memory,bus,r);
#if GAME_INITIALIZE_MUTATION == 6
    r->ip=timer_resume;
#endif
    if(r->cs!=expected_cs||r->ip!=timer_resume){
        out.status=LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN;
        return out;
    }
    r->ip=timer_resume;

    /* CALL InitializeLevelFromRecord at046B with the explicit live game-data
       segment and the caller's raster, byte-port and resource contracts. */
    const uint16_t level_resume=CS_InitializeGameAfterLevelInitialization;
    expected_cs=r->cs;
    push_word(memory,bus,r,level_resume);
    r->ip=CS_InitializeLevelFromRecord;
    LmnLevelInitializeCall level_call={
        {r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->sp,r->flags,r->ip},
        r->ds,r->es,r->cs,r->ss,
        services?services->game_data_segment:0
    };
    LmnLevelInitializeResult level=lmn_initialize_level_core(memory,&level_call,
        services?services->level:0);
    r->ax=level.state.work_value;
    r->bx=level.state.second_source_cursor;
    r->cx=level.state.packed_counts;
    r->dx=level.state.width_state;
    r->si=level.state.source_cursor;
    r->di=level.state.destination_cursor;
    r->bp=level.state.control;
    r->sp=level.state.stack_offset;
    r->ds=level.data_segment;
    r->es=level.output_segment;
    r->cs=level.code_segment;
    r->ip=level.state.continuation;
    r->flags=level.state.flags;
    if(level.status!=LMN_LEVEL_INITIALIZE_READY_TO_RETURN){
#if GAME_INITIALIZE_MUTATION == 7
        /* Mutant: discard the level child's explicit stop boundary. */
        r->ip=level_resume;
        return out;
#else
        out.status=level.status==LMN_LEVEL_INITIALIZE_CHANGED_RETURN
            ?LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN:LMN_GAME_INITIALIZE_CHILD_STOP;
        out.child_status=(uint16_t)level.status;
        out.service_status=level.fatal?level.fatal:
            level.missing_services?level.missing_services:
            level.missing_provider?level.missing_provider:
            level.unported?level.unported:0;
        return out;
#endif
    }

    /* The logical child leaves its actual outer RET pending at3789. Consume
       that live SS word here, exactly as the original CALL at046B does. */
    r->ip=pop_word(memory,bus,r);
#if GAME_INITIALIZE_MUTATION == 7
    r->ip=level_resume;
#endif
#if GAME_INITIALIZE_MUTATION == 8
    r->ip=level_resume;
#endif
    if(r->cs!=expected_cs||r->ip!=level_resume){
        out.status=LMN_GAME_INITIALIZE_CHANGED_CHILD_RETURN;
        return out;
    }
    r->ip=level_resume;
    if(services&&services->stop_at_mouse_check)return out;
    return finish_session(memory,out,services);
}

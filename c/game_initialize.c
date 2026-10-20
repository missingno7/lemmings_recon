#include "game_initialize.h"
#include "lemmings_sym.h"

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

LmnGameInitializeResult lmn_initialize_game_core(uint8_t *memory,
    const LmnRegs *registers,const LmnGameInitializeServices *services){
    const LmnRasterBus *bus=services?services->bus:0;
    LmnGameInitializeResult out={*registers,LMN_GAME_INITIALIZE_AT_LEVEL_INITIALIZATION,0,0};
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
    return out;
}

#include "pcspeaker.h"
#include "pcspeaker_sym.h"

#ifndef MUTATION
#define MUTATION 0
#endif
#ifndef EFFECT_BUS_MUTATION
#define EFFECT_BUS_MUTATION 0
#endif

enum { CF=1, PF=4, AF=16, ZF=64, SF=128, OF=2048 };
enum { ARITH=CF|PF|AF|ZF|SF|OF, DEFINED=0x0fd7 };

static uint32_t physical(uint16_t seg, uint16_t off) {
    return (((uint32_t)seg << 4) + off) & 0xfffffu;
}
static uint8_t get8(const uint8_t *mem, uint16_t seg, uint16_t off) {
    return mem[physical(seg,off)];
}
static void put8(uint8_t *mem, uint16_t seg, uint16_t off, uint8_t value) {
    mem[physical(seg,off)]=value;
}
static uint16_t get16(const uint8_t *mem, uint16_t seg, uint16_t off) {
    uint32_t at=physical(seg,off);
    return (uint16_t)(mem[at] | ((uint16_t)mem[(at+1u)&0xfffffu]<<8));
}
static void put16(uint8_t *mem, uint16_t seg, uint16_t off, uint16_t value) {
    uint32_t at=physical(seg,off);
    mem[at]=(uint8_t)value;mem[(at+1u)&0xfffffu]=(uint8_t)(value>>8);
}
static uint8_t bus_read8(const uint8_t *mem,uint16_t seg,uint16_t off,
                         uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=physical(seg,off);
    if(bus && bus->read_byte)
        return bus->read_byte(bus->context,(uint8_t *)(void *)mem,at,flags);
    return mem[at];
}
static void bus_write8(uint8_t *mem,uint16_t seg,uint16_t off,uint8_t value,
                       uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=physical(seg,off);
    if(bus && bus->write_byte)
        bus->write_byte(bus->context,mem,at,value,flags);
    else
        mem[at]=value;
}
static uint16_t bus_read16(const uint8_t *mem,uint16_t seg,uint16_t off,
                           uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=physical(seg,off);
    uint8_t lo,hi;
    if(bus && bus->read_byte) {
        lo=bus->read_byte(bus->context,(uint8_t *)(void *)mem,at,flags);
        hi=bus->read_byte(bus->context,(uint8_t *)(void *)mem,
                          (at+1u)&0xfffffu,flags);
    } else {
        lo=mem[at];hi=mem[(at+1u)&0xfffffu];
    }
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void bus_write16(uint8_t *mem,uint16_t seg,uint16_t off,uint16_t value,
                        uint16_t flags,const LmnRasterBus *bus) {
    uint32_t at=physical(seg,off);
    if(bus && bus->write_byte) {
        bus->write_byte(bus->context,mem,at,(uint8_t)value,flags);
        bus->write_byte(bus->context,mem,(at+1u)&0xfffffu,
                        (uint8_t)(value>>8),flags);
    } else {
        mem[at]=(uint8_t)value;mem[(at+1u)&0xfffffu]=(uint8_t)(value>>8);
    }
}
static uint16_t szp8(uint8_t value) {
    unsigned n,parity=0;
    uint16_t flags=(uint16_t)((value==0 ? ZF:0) | (value&SF));
    for(n=0;n<8;++n) parity^=(value>>n)&1u;
    if(!parity) flags|=PF;
    return flags;
}
static uint16_t logic_flags(uint16_t flags, uint8_t value) {
    /* AF has no defined result after OR/XOR. Other non-arithmetic bits survive. */
    return (uint16_t)((flags&(0xffffu^ARITH))|szp8(value));
}
static uint8_t rotate_byte(uint8_t value) {
    return (uint8_t)((value>>1)|(value<<7));
}

static uint16_t add16_flags(uint16_t flags,uint16_t left,uint16_t right,
                            uint16_t result) {
    uint16_t f=(uint16_t)(flags&(0xffffu^ARITH));
    unsigned parity=0,n;
    uint32_t wide=(uint32_t)left+(uint32_t)right;
    if(wide&0x10000u) f|=CF;
    if((left^right^result)&0x10u) f|=AF;
    if(result==0) f|=ZF;
    if(result&0x8000u) f|=SF;
    for(n=0;n<8;++n) parity^=(result>>n)&1u;
    if(!parity) f|=PF;
    if((~(left^right)&(left^result)&0x8000u)!=0) f|=OF;
    return f;
}
static uint16_t inc16_flags(uint16_t flags,uint16_t value,uint16_t result) {
    uint16_t f=(uint16_t)(flags&(0xffffu^ARITH));
    unsigned parity=0,n;
    f|=(uint16_t)(flags&CF);
    for(n=0;n<8;++n) parity^=(result>>n)&1u;
    if(!parity) f|=PF;
    if((value&0x000fu)==0x000fu) f|=AF;
    if(result==0) f|=ZF;
    if(result&0x8000u) f|=SF;
    if(value==0x7fffu) f|=OF;
    return f;
}
static uint16_t dec16_flags(uint16_t flags,uint16_t value,uint16_t result) {
    uint16_t f=(uint16_t)(flags&(0xffffu^ARITH));
    unsigned parity=0,n;
    f|=(uint16_t)(flags&CF);
    for(n=0;n<8;++n) parity^=(result>>n)&1u;
    if(!parity) f|=PF;
    if((value&0x000fu)==0) f|=AF;
    if(result==0) f|=ZF;
    if(result&0x8000u) f|=SF;
    if(value==0x8000u) f|=OF;
    return f;
}
static uint16_t dec8_flags(uint16_t flags,uint8_t value,uint8_t result) {
    return (uint16_t)((flags&(0xffffu^ARITH))|(flags&CF)|
        (value==0x80u ? OF:0)|((value&15u)==0 ? AF:0)|szp8(result));
}

LmnPcSoundResult lmn_pc_sound_effect_core(uint8_t *mem,uint16_t ds,
                                         uint8_t effect,uint16_t initial_dx,
                                         uint16_t flags) {
    return lmn_pc_sound_effect_bus_core(mem,ds,effect,initial_dx,flags,NULL);
}

LmnPcSoundResult lmn_pc_sound_effect_bus_core(uint8_t *mem,uint16_t ds,
                                         uint8_t effect,uint16_t initial_dx,
                                         uint16_t flags,const LmnRasterBus *bus) {
    /* IMUL CL uses signed AL and 15, then ADD BX,AX sets the first flags. */
    int32_t signed_effect=effect<128u ? (int32_t)effect : (int32_t)effect-256;
#if MUTATION == 1
    signed_effect=effect;
#endif
    uint16_t product=(uint16_t)(signed_effect*(int32_t)PC_EffectRecordSize);
    uint16_t bx=(uint16_t)(PC_EffectRecords+product);
    uint16_t cx=PC_EffectRecordSize,si=PC_CurrentEffect;
    uint16_t current_flags=add16_flags(flags,PC_EffectRecords,product,bx);
    uint16_t cached_reload=0;
    unsigned n;
    LmnPcSoundResult out;

    /* MOV CX,15 made CH zero; the first live write clears EffectActive. */
    bus_write8(mem,ds,PC_EffectActive,0,current_flags,bus);
#if EFFECT_BUS_MUTATION == 2
    cached_reload=bus_read16(mem,ds,PC_EffectReload,current_flags,bus);
#endif
    for(n=0;n<PC_EffectRecordSize;++n) {
        uint8_t byte=bus_read8(mem,ds,bx,current_flags,bus);
        bus_write8(mem,ds,si,byte,current_flags,bus);
        if(EFFECT_BUS_MUTATION == 5 && (current_flags&0x0400u)) {
            uint16_t old=bx;bx=(uint16_t)(bx-1u);
            current_flags=dec16_flags(current_flags,old,bx);
            old=si;si=(uint16_t)(si-1u);
            current_flags=dec16_flags(current_flags,old,si);
        } else {
            uint16_t old=bx;bx=(uint16_t)(bx+1u);
            current_flags=inc16_flags(current_flags,old,bx);
            old=si;si=(uint16_t)(si+1u);
            current_flags=inc16_flags(current_flags,old,si);
        }
        cx=(uint16_t)(cx-1u); /* LOOP does not change flags. */
    }
    out.ax=cached_reload;
#if EFFECT_BUS_MUTATION != 2
    out.ax=bus_read16(mem,ds,PC_EffectReload,current_flags,bus);
#endif
    bus_write16(mem,ds,PC_PulseCountdown,out.ax,current_flags,bus);
    {
        uint8_t before=bus_read8(mem,ds,PC_EffectActive,current_flags,bus);
        uint8_t decremented;
#if EFFECT_BUS_MUTATION == 3
        before=0;
#endif
        decremented=(uint8_t)(before-1u);
        out.flags=dec8_flags(current_flags,before,decremented);
#if MUTATION == 2
        decremented=1;
#endif
#if EFFECT_BUS_MUTATION == 1
        bus_write8(mem,ds,PC_EffectActive,decremented,out.flags,bus);
#else
        bus_write8(mem,ds,PC_EffectActive,decremented,current_flags,bus);
#endif
    }
    out.bx=bx;out.cx=cx;out.dx=initial_dx;out.si=si;
    out.defined_flags_mask=DEFINED;
    return out;
}
LmnPcSoundResult lmn_pc_sound_tick_core(uint8_t *mem, uint16_t ds,
                                       uint16_t initial_ax, uint16_t initial_bx,
                                       uint16_t initial_dx, uint16_t initial_si,
                                       uint16_t flags, const LmnPort8 *ports) {
    LmnPcSoundResult out={initial_ax,(uint16_t)(initial_bx&255u),2,
                         initial_dx,initial_si,flags,(uint16_t)(DEFINED&~AF)};
    uint8_t phase=get8(mem,ds,PC_NoiseStep);
    put8(mem,ds,PC_NoisePhase,(uint8_t)(get8(mem,ds,PC_NoisePhase)+phase));
    out.ax=(uint16_t)((out.ax&0xff00u)|phase);
    if(get8(mem,ds,PC_EffectActive)!=0) {
        uint8_t remaining=(uint8_t)(get8(mem,ds,PC_EffectDuration)-1u);
        put8(mem,ds,PC_EffectDuration,remaining);
        if(remaining==0) {
            put8(mem,ds,PC_EffectActive,0);
        } else {
            uint8_t countdown,pattern;
            out.ax=get16(mem,ds,PC_EffectReload);
            countdown=(uint8_t)(get8(mem,ds,PC_ModulationCountdown)-1u);
            put8(mem,ds,PC_ModulationCountdown,countdown);
            if(countdown==0) {
                put8(mem,ds,PC_ModulationCountdown,(uint8_t)(out.ax>>8));
                pattern=get8(mem,ds,PC_ModulationPattern);
                put8(mem,ds,PC_ModulationPattern,rotate_byte(pattern));
                out.dx=get16(mem,ds,(pattern&1u) ? PC_ModulationDeltaA : PC_ModulationDeltaB);
                put16(mem,ds,PC_CurrentPeriod,(uint16_t)(get16(mem,ds,PC_CurrentPeriod)+out.dx));
            }
            out.dx=(uint16_t)(get16(mem,ds,PC_CurrentPeriod)+get16(mem,ds,PC_PeriodStep));
            countdown=(uint8_t)(get8(mem,ds,PC_PulseCountdown)-1u);
            put8(mem,ds,PC_PulseCountdown,countdown);
            if(countdown==0) {
                put8(mem,ds,PC_PulseCountdown,(uint8_t)out.ax);
                out.dx=get16(mem,ds,PC_PulseResetPeriod);
            }
            put16(mem,ds,PC_CurrentPeriod,out.dx);
            pattern=get8(mem,ds,PC_GatePattern);
            put8(mem,ds,PC_GatePattern,rotate_byte(pattern));
            if(!(pattern&1u)) out.cx=out.dx;
        }
    }
    if(get16(mem,ds,PC_LastPitPeriod)!=out.cx) {
        ports->write(ports->context,0x43,0xb6);
        ports->write(ports->context,0x42,(uint8_t)out.cx);
        ports->write(ports->context,0x42,(uint8_t)(out.cx>>8));
        put16(mem,ds,PC_LastPitPeriod,out.cx);
    }
    {
        uint8_t gate=(uint8_t)(ports->read(ports->context,0x61)|3u);
#if MUTATION == 3
        gate=(uint8_t)(gate&0xfeu);
#endif
        ports->write(ports->context,0x61,gate);
        out.ax=(uint16_t)((out.ax&0xff00u)|gate);
        out.flags=logic_flags(flags,gate);
    }
    return out;
}

LmnPcSoundResult lmn_pc_sound_stop_core(uint8_t *mem,uint16_t ds,
                                       uint16_t initial_ax,uint16_t initial_bx,
                                       uint16_t initial_cx,uint16_t initial_dx,
                                       uint16_t initial_si,uint16_t flags) {
    return lmn_pc_sound_stop_bus_core(mem,ds,initial_ax,initial_bx,initial_cx,
                                     initial_dx,initial_si,flags,NULL);
}
LmnPcSoundResult lmn_pc_sound_stop_bus_core(uint8_t *mem,uint16_t ds,
                                       uint16_t initial_ax,uint16_t initial_bx,
                                       uint16_t initial_cx,uint16_t initial_dx,
                                       uint16_t initial_si,uint16_t flags,
                                       const LmnRasterBus *bus) {
    LmnPcSoundResult out={(uint16_t)(initial_ax&0xff00u),initial_bx,initial_cx,
                         initial_dx,initial_si,logic_flags(flags,0),(uint16_t)(DEFINED&~AF)};
    bus_write8(mem,ds,PC_EffectActive,0,out.flags,bus);
    return out;
}
static void finish(uint8_t *mem,LmnRegs *r,LmnPcSoundResult out) {
    r->ax=out.ax;r->bx=out.bx;r->cx=out.cx;r->dx=out.dx;r->si=out.si;r->flags=out.flags;
    r->ip=get16(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);
}
static void finish_bus(LmnRegs *r,LmnPcSoundResult out,uint16_t return_ip) {
    r->ax=out.ax;r->bx=out.bx;r->cx=out.cx;r->dx=out.dx;r->si=out.si;r->flags=out.flags;
    r->ip=return_ip;r->sp=(uint16_t)(r->sp+2u);
}
void lmn_pc_sound_effect_adapter(uint8_t *mem,LmnRegs *r) {
    lmn_pc_sound_effect_bus_adapter(mem,r,NULL);
}
void lmn_pc_sound_effect_bus_adapter(uint8_t *mem,LmnRegs *r,
                                     const LmnRasterBus *bus) {
    uint16_t return_ip=0;
#if EFFECT_BUS_MUTATION == 4
    return_ip=bus_read16(mem,r->ss,r->sp,r->flags,bus);
#endif
    {
        LmnPcSoundResult out=lmn_pc_sound_effect_bus_core(mem,r->ds,(uint8_t)r->ax,
                                                          r->dx,r->flags,bus);
#if EFFECT_BUS_MUTATION != 4
        return_ip=bus_read16(mem,r->ss,r->sp,out.flags,bus);
#endif
        finish_bus(r,out,return_ip);
    }
}
void lmn_pc_sound_tick_adapter(uint8_t *mem,LmnRegs *r,const LmnPort8 *ports) {
    finish(mem,r,lmn_pc_sound_tick_core(mem,r->ds,r->ax,r->bx,r->dx,r->si,r->flags,ports));
}
void lmn_pc_sound_stop_adapter(uint8_t *mem,LmnRegs *r) {
    lmn_pc_sound_stop_bus_adapter(mem,r,NULL);
}
void lmn_pc_sound_stop_bus_adapter(uint8_t *mem,LmnRegs *r,
                                   const LmnRasterBus *bus) {
    uint16_t return_ip=0;
#if EFFECT_BUS_MUTATION == 4
    return_ip=bus_read16(mem,r->ss,r->sp,r->flags,bus);
#endif
    {
        LmnPcSoundResult out=lmn_pc_sound_stop_bus_core(mem,r->ds,r->ax,r->bx,
            r->cx,r->dx,r->si,r->flags,bus);
#if EFFECT_BUS_MUTATION != 4
        return_ip=bus_read16(mem,r->ss,r->sp,out.flags,bus);
#endif
        finish_bus(r,out,return_ip);
    }
}

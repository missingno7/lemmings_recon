#include "pcspeaker.h"
#include "pcspeaker_sym.h"

#ifndef MUTATION
#define MUTATION 0
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

LmnPcSoundResult lmn_pc_sound_effect_core(uint8_t *mem, uint16_t ds,
                                         uint8_t effect, uint16_t initial_dx,
                                         uint16_t flags) {
    /* IMUL CL uses signed AL and 15, followed by an unsigned 16-bit ADD. */
    int32_t signed_effect=effect<128u ? (int32_t)effect : (int32_t)effect-256;
#if MUTATION == 1
    signed_effect=effect;
#endif
    uint16_t product=(uint16_t)(signed_effect*(int32_t)PC_EffectRecordSize);
    uint32_t sum=(uint32_t)PC_EffectRecords+product;
    uint16_t source=(uint16_t)sum,destination=PC_CurrentEffect;
    unsigned n;
    LmnPcSoundResult out;
    put8(mem,ds,PC_EffectActive,0);
    /* Read each byte at the moment it is copied; overlapping live data is valid. */
    for(n=0;n<PC_EffectRecordSize;++n) {
        uint8_t byte=get8(mem,ds,source);
        put8(mem,ds,destination,byte);
        source=(uint16_t)(source+1u);destination=(uint16_t)(destination+1u);
    }
    out.ax=get16(mem,ds,PC_EffectReload);
    put16(mem,ds,PC_PulseCountdown,out.ax);
    put8(mem,ds,PC_EffectActive,0xff);
#if MUTATION == 2
    put8(mem,ds,PC_EffectActive,1);
#endif
    /* DEC 0 -> FF defines all arithmetic flags except the preserved ADD carry. */
    out.flags=(uint16_t)((flags&(0xffffu^ARITH))|PF|AF|SF|(sum>0xffffu ? CF:0));
    out.bx=source;out.cx=0;out.dx=initial_dx;out.si=destination;
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

LmnPcSoundResult lmn_pc_sound_stop_core(uint8_t *mem, uint16_t ds,
                                       uint16_t initial_ax, uint16_t initial_bx,
                                       uint16_t initial_cx, uint16_t initial_dx,
                                       uint16_t initial_si, uint16_t flags) {
    LmnPcSoundResult out={(uint16_t)(initial_ax&0xff00u),initial_bx,initial_cx,
                         initial_dx,initial_si,logic_flags(flags,0),(uint16_t)(DEFINED&~AF)};
    put8(mem,ds,PC_EffectActive,0);
    return out;
}
static void finish(uint8_t *mem, LmnRegs *r, LmnPcSoundResult out) {
    r->ax=out.ax;r->bx=out.bx;r->cx=out.cx;r->dx=out.dx;r->si=out.si;r->flags=out.flags;
    r->ip=get16(mem,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);
}
void lmn_pc_sound_effect_adapter(uint8_t *mem, LmnRegs *r) {
    finish(mem,r,lmn_pc_sound_effect_core(mem,r->ds,(uint8_t)r->ax,r->dx,r->flags));
}
void lmn_pc_sound_tick_adapter(uint8_t *mem, LmnRegs *r,const LmnPort8 *ports) {
    finish(mem,r,lmn_pc_sound_tick_core(mem,r->ds,r->ax,r->bx,r->dx,r->si,r->flags,ports));
}
void lmn_pc_sound_stop_adapter(uint8_t *mem, LmnRegs *r) {
    finish(mem,r,lmn_pc_sound_stop_core(mem,r->ds,r->ax,r->bx,r->cx,r->dx,r->si,r->flags));
}

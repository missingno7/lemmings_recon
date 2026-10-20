#include "video_probe.h"
#include "lemmings_sym.h"
#ifndef VIDEO_PROBE_MUTATION
#define VIDEO_PROBE_MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,IF=512,DF=1024,OF=2048,ARITH=0x8D5};
typedef struct Probe {
    uint8_t *mem;const LmnVideoProbeServices *services;LmnVideoProbeResult out;
} Probe;
static const LmnRasterBus *bus(Probe *s){return s->services?s->services->bus:0;}
static uint32_t physical(uint16_t seg,uint16_t off){return (((uint32_t)seg<<4)+off)&0xFFFFFu;}
static uint8_t read_at(Probe *s,uint32_t at){
    const LmnRasterBus *b=bus(s);at&=0xFFFFFu;
    return b&&b->read_byte?b->read_byte(b->context,s->mem,at,s->out.registers.flags):s->mem[at];
}
static void write_at(Probe *s,uint32_t at,uint8_t value){
    const LmnRasterBus *b=bus(s);at&=0xFFFFFu;
    if(b&&b->write_byte)b->write_byte(b->context,s->mem,at,value,s->out.registers.flags);else s->mem[at]=value;
}
static uint8_t read8(Probe *s,uint16_t seg,uint16_t off){return read_at(s,physical(seg,off));}
static uint16_t read16(Probe *s,uint16_t seg,uint16_t off){
    uint32_t p=physical(seg,off);uint8_t lo=read_at(s,p),hi=read_at(s,p+1u);return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void write8(Probe *s,uint16_t off,uint8_t v){write_at(s,physical(s->out.registers.ds,off),v);}
static void write16(Probe *s,uint16_t seg,uint16_t off,uint16_t v){
    uint32_t p=physical(seg,off);write_at(s,p,(uint8_t)v);write_at(s,p+1u,(uint8_t)(v>>8));
}
static void push(Probe *s,uint16_t v){LmnRegs *r=&s->out.registers;r->sp=(uint16_t)(r->sp-2u);write16(s,r->ss,r->sp,v);}
static uint16_t pop(Probe *s){LmnRegs *r=&s->out.registers;uint16_t v=read16(s,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);return v;}
static void al(Probe *s,uint8_t v){s->out.registers.ax=(uint16_t)((s->out.registers.ax&0xFF00u)|v);}
static void ah(Probe *s,uint8_t v){s->out.registers.ax=(uint16_t)((s->out.registers.ax&255u)|((uint16_t)v<<8));}
static uint16_t szp(uint16_t v,int byte){
    unsigned parity=0;for(unsigned n=0;n<8;n++)parity^=(v>>n)&1u;
    return (uint16_t)((parity?0:PF)|(v?0:ZF)|(v&(byte?128u:0x8000u)?SF:0));
}
static uint16_t arith(Probe *s,uint16_t a,uint16_t b,int sub,int byte){
    uint16_t mask=byte?255u:65535u,sign=byte?128u:0x8000u,v=(uint16_t)((sub?a-b:a+b)&mask);
    s->out.registers.flags=(uint16_t)((s->out.registers.flags&~ARITH)|szp(v,byte)|
        ((sub?a<b:(uint32_t)a+b>mask)?CF:0)|((a^b^v)&AF)|(((sub?(a^b):~(a^b))&(a^v)&sign)?OF:0));return v;
}
static void logic(Probe *s,uint16_t v,int byte){s->out.registers.flags=(uint16_t)((s->out.registers.flags&~ARITH)|szp(v,byte));}
static uint16_t inc(Probe *s,uint16_t v){uint16_t cf=s->out.registers.flags&CF;v=arith(s,v,1,0,0);s->out.registers.flags=(uint16_t)((s->out.registers.flags&~CF)|cf);return v;}
static uint16_t shr(Probe *s,uint16_t v,int byte){
    uint16_t out=v>>1;s->out.registers.flags=(uint16_t)((s->out.registers.flags&~ARITH)|szp(out,byte)|(v&1u)|(v&(byte?128u:0x8000u)?OF:0));return out;
}
static int inp(Probe *s,uint16_t port,uint16_t pc){
    LmnRegs *r=&s->out.registers;const LmnRasterBytePorts *p=s->services?s->services->ports:0;
    if(!p||!p->in_byte){r->ip=pc;s->out.status=LMN_VIDEO_PROBE_MISSING_INPUT;return 0;}
    al(s,p->in_byte(p->context,s->mem,port,r->flags));return 1;
}
static int outp(Probe *s,uint16_t port,uint16_t pc){
    LmnRegs *r=&s->out.registers;const LmnRasterBytePorts *p=s->services?s->services->ports:0;
    if(!p||!p->out_byte){r->ip=pc;s->out.status=LMN_VIDEO_PROBE_MISSING_OUTPUT;return 0;}
    p->out_byte(p->context,s->mem,port,(uint8_t)r->ax,r->flags);return 1;
}
static int bios(Probe *s,uint16_t resume){
    LmnInterruptResult out=lmn_interrupt_service(s->mem,&s->out.registers,0x10,resume,s->services?s->services->bios:0,bus(s));
    if(!out.status)return 1;
    s->out.status=LMN_VIDEO_PROBE_INTERRUPT_STOP;s->out.child_status=out.status;s->out.service_status=out.service_status;return 0;
}
static int returned(Probe *s,uint16_t cs,uint16_t resume){
    if(s->out.status)return 0;
    s->out.registers.ip=pop(s);
#if VIDEO_PROBE_MUTATION == 5
    s->out.registers.ip=resume;
#endif
    if(s->out.registers.cs!=cs||s->out.registers.ip!=resume){s->out.status=LMN_VIDEO_PROBE_CHANGED_RETURN;return 0;}return 1;
}
typedef void (*Body)(Probe *);
static int child(Probe *s,uint16_t target,uint16_t resume,Body body){
    uint16_t cs=s->out.registers.cs;push(s,resume);s->out.registers.ip=target;body(s);return returned(s,cs,resume);
}
static void store_pair(Probe *s){
    LmnRegs *r=&s->out.registers;r->bx=r->di;(void)arith(s,read8(s,r->ds,r->bx),0,1,1);
    if(!(r->flags&ZF))r->bx=(uint16_t)(r->di+2u);
    write16(s,r->ds,r->bx,r->ax);r->ip=0x152F;
}
static void probe_crtc(Probe *s){
    LmnRegs *r=&s->out.registers;al(s,15);if(!outp(s,r->dx,0x14E2))return;
    r->dx=inc(s,r->dx);if(!inp(s,r->dx,0x14E4))return;
    ah(s,(uint8_t)r->ax);
    al(s,0x66);if(!outp(s,r->dx,0x14E9))return;
    r->cx=0x100;
    do{--r->cx;}while(r->cx); /* LOOP preserves flags. */
    if(!inp(s,r->dx,0x14EF))return;
    r->ax=(uint16_t)((r->ax<<8)|(r->ax>>8));
#if VIDEO_PROBE_MUTATION == 6
    al(s,0x66);
#endif
    if(!outp(s,r->dx,0x14F2))return;
    (void)arith(s,(uint8_t)(r->ax>>8),0x66,1,1);if(!(r->flags&ZF))r->flags|=CF;r->ip=0x14F9;
}
static void color(Probe *s){
    LmnRegs *r=&s->out.registers;r->dx=0x3D4;
    if(!child(s,CS_ProbeCrtcRegister0F,0x1496,probe_crtc))return;
    if(!(r->flags&CF)){r->ax=0x0202;if(!child(s,CS_StoreDetectedAdapterPair,0x149F,store_pair))return;
    }r->ip=0x149F;
}
static void mono(Probe *s){
    LmnRegs *r=&s->out.registers;r->dx=0x3B4;
    if(!child(s,CS_ProbeCrtcRegister0F,0x14A6,probe_crtc))return;
    if(r->flags&CF){r->ip=0x14DF;return;
    }
    r->dx=(uint16_t)((r->dx&0xFF00u)|0xBAu);if(!inp(s,r->dx,0x14AA))return;
    al(s,(uint8_t)(r->ax&128u));logic(s,(uint8_t)r->ax,1);ah(s,(uint8_t)r->ax);r->cx=0x8000;
    do{
        if(!inp(s,r->dx,0x14B2))return;
        al(s,(uint8_t)(r->ax&128u));logic(s,(uint8_t)r->ax,1);
        (void)arith(s,(uint8_t)(r->ax>>8),(uint8_t)r->ax,1,1);--r->cx;
    }while(r->cx&&(r->flags&ZF));
    if(r->flags&ZF){r->ax=0x0101;store_pair(s);return;
    }
    if(!inp(s,r->dx,0x14C2))return;
    r->dx=(uint16_t)((r->dx&0xFF00u)|(uint8_t)r->ax);
    r->dx=(uint16_t)((r->dx&0xFF00u)|(r->dx&0x70u));logic(s,(uint8_t)r->dx,1);
    r->ax=0x0181;(void)arith(s,(uint8_t)r->dx,0x10,1,1);
    if(!(r->flags&ZF)){
        al(s,0x80);(void)arith(s,(uint8_t)r->dx,0x50,1,1);if(r->flags&ZF)r->ax=0x0382;
    }
    if(!child(s,CS_StoreDetectedAdapterPair,0x14DF,store_pair))return;
    r->ip=0x14DF;
}
static void ega(Probe *s){
    LmnRegs *r=&s->out.registers;r->bx=(uint16_t)((r->bx&0xFF00u)|0x10u);ah(s,0x12);
    if(!bios(s,0x1468))return;
    (void)arith(s,(uint8_t)r->bx,0x10,1,1);
    if(!(r->flags&ZF)){
        al(s,(uint8_t)r->cx);al(s,(uint8_t)shr(s,(uint8_t)r->ax,1));r->bx=CS_DisplayConfigLookup;
        al(s,read8(s,r->cs,(uint16_t)(r->bx+(uint8_t)r->ax)));ah(s,(uint8_t)r->ax);al(s,3);
        if(!child(s,CS_StoreDetectedAdapterPair,0x147E,store_pair))return;
        (void)arith(s,(uint8_t)(r->ax>>8),1,1,1);write8(s,(r->flags&ZF)?SEG09A9_MonoCrtcProbeEnableByte:SEG09A9_ColorCrtcProbeEnableByte,0);
    }r->ip=0x148F;
}
static void dcc(Probe *s){
    LmnRegs *r=&s->out.registers;r->ax=0x1A00;if(!bios(s,0x1415))return;
    (void)arith(s,(uint8_t)r->ax,0x1A,1,1);if(!(r->flags&ZF)){r->ip=0x1461;return;
    }
    r->cx=r->bx;r->bx&=255u;logic(s,0,1);logic(s,(uint8_t)(r->cx>>8),1);
    if(!(r->flags&ZF)){
        r->bx=(uint8_t)(r->cx>>8);r->bx=arith(s,r->bx,r->bx,0,0);
        r->ax=read16(s,r->cs,(uint16_t)(CS_BiosDisplayPairLookup+r->bx));write16(s,r->ds,(uint16_t)(r->di+2u),r->ax);
        r->bx=(uint8_t)r->cx;logic(s,0,1);
    }
    r->bx=arith(s,r->bx,r->bx,0,0);r->ax=read16(s,r->cs,(uint16_t)(CS_BiosDisplayPairLookup+r->bx));
    write16(s,r->ds,r->di,r->ax);write8(s,SEG09A9_ColorCrtcProbeEnableByte,0);write8(s,SEG09A9_EgaProbeEnableByte,0);write8(s,SEG09A9_MonoCrtcProbeEnableByte,0);
    r->bx=r->di;(void)arith(s,read8(s,r->ds,r->bx),1,1,1);
    if(!(r->flags&ZF)){r->bx=(uint16_t)(r->di+2u);(void)arith(s,read8(s,r->ds,r->bx),1,1,1);}
    if(r->flags&ZF){write16(s,r->ds,r->bx,0);write8(s,SEG09A9_MonoCrtcProbeEnableByte,255);}r->ip=0x1461;
}
static void detect(Probe *s){
    LmnRegs *r=&s->out.registers;r->di=SEG09A9_PrimaryDetectedAdapterPair;write16(s,r->ds,r->di,0);write16(s,r->ds,(uint16_t)(r->di+2u),0);
    write8(s,SEG09A9_ColorCrtcProbeEnableByte,255);write8(s,SEG09A9_EgaProbeEnableByte,255);write8(s,SEG09A9_MonoCrtcProbeEnableByte,255);r->cx=4;r->si=SEG09A9_DisplayProbeRecords;
    do{
        uint16_t step=(r->flags&DF)?0xFFFFu:1u;
#if VIDEO_PROBE_MUTATION == 2
        step=1;
#endif
        al(s,read8(s,r->ds,r->si));r->si=(uint16_t)(r->si+step);logic(s,(uint8_t)r->ax,1);
        r->ax=read16(s,r->ds,r->si);r->si=(uint16_t)(r->si+2u*step);
        if(!(r->flags&ZF)){
            push(s,r->si);push(s,r->cx);Body body=0;
            switch(r->ax){case CS_ProbeDisplayCombination:body=dcc;break;case CS_ProbeEgaConfiguration:body=ega;break;
                case CS_ProbeColorCrtc:body=color;break;case CS_ProbeMonochromeCrtc:body=mono;break;default:break;}
            if(!body){r->ip=0x1407;s->out.status=LMN_VIDEO_PROBE_UNBOUND_TARGET;return;
            }
            if(!child(s,r->ax,0x1409,body))return;
            r->cx=pop(s);r->si=pop(s);
        }--r->cx;
    }while(r->cx);
    (void)arith(s,read16(s,r->ds,(uint16_t)(r->di+2u)),0,1,0);
    if(!(r->flags&ZF)){
        (void)arith(s,read8(s,r->ds,r->di),4,1,1);
        if(!((!!(r->flags&SF))^(!!(r->flags&OF)))){r->ip=0x1522;return;
        }
        (void)arith(s,read8(s,r->ds,(uint16_t)(r->di+2u)),4,1,1);
        if(!((!!(r->flags&SF))^(!!(r->flags&OF)))){r->ip=0x1522;return;
        }
        ah(s,15);if(!bios(s,0x150F))return;
        al(s,(uint8_t)(r->ax&7u));logic(s,(uint8_t)r->ax,1);
        (void)arith(s,(uint8_t)r->ax,7,1,1);
        if(!(r->flags&ZF))(void)arith(s,read8(s,r->ds,(uint16_t)(r->di+1u)),1,1,1);
        if(r->flags&ZF){
            r->ax=read16(s,r->ds,r->di);uint16_t v=read16(s,r->ds,(uint16_t)(r->di+2u));
            write16(s,r->ds,(uint16_t)(r->di+2u),r->ax);r->ax=v;write16(s,r->ds,r->di,r->ax);
        }
    }r->ip=0x1522;
}
static void measure(Probe *s){
    LmnRegs *r=&s->out.registers;r->cx=0xFFFF;r->dx=read16(s,r->ds,SEG09A9_DisplayControllerBasePort);
    r->dx=(uint16_t)((r->dx&0xFF00u)|arith(s,(uint8_t)r->dx,6,0,1));
    do{if(!inp(s,r->dx,0x160C))return;
    logic(s,(uint8_t)r->ax&8u,1);}while(r->flags&ZF);
    do{if(!inp(s,r->dx,0x1611))return;
    logic(s,(uint8_t)r->ax&8u,1);}while(!(r->flags&ZF));
    al(s,0x30);if(!outp(s,0x43,0x1618))return;al(s,(uint8_t)r->cx);if(!outp(s,0x40,0x161C))return;
    al(s,(uint8_t)(r->cx>>8));if(!outp(s,0x40,0x1620))return;
    r->cx=r->bx;
    do{
        do{if(!inp(s,r->dx,0x1624))return;
        logic(s,(uint8_t)r->ax&1u,1);}while(!(r->flags&ZF));
        do{if(!inp(s,r->dx,0x1629))return;
        logic(s,(uint8_t)r->ax&1u,1);}while(r->flags&ZF);
        --r->cx;
    }while(r->cx);
    al(s,6);if(!outp(s,0x43,0x1632))return;al(s,0x36);if(!outp(s,0x43,0x1636))return;
    if(!inp(s,0x40,0x163B))return;
    r->cx=(uint8_t)r->ax;
    if(!inp(s,0x40,0x163F))return;
    r->cx=(uint16_t)(r->cx|((uint16_t)(uint8_t)r->ax<<8));r->ip=0x1643;
}
static void calibrate(Probe *s){
    LmnRegs *r=&s->out.registers;uint8_t option=read8(s,r->ds,SEG09A9_ConfigurationOption200E);
    (void)arith(s,option,255,1,1);int fixed=(r->flags&ZF)!=0;
#if VIDEO_PROBE_MUTATION == 8
    fixed=option!=0;
#endif
    if(fixed){write16(s,r->ds,SEG09A9_TimerPitReload1FC9,0x4000);r->ip=0x15BA;return;
    }
    r->ax=read16(s,r->ds,SEG09A9_TimerPitReload1FC9);push(s,r->ax);r->bx=0x140;
    r->ax=read16(s,r->ds,SEG09A9_RasterMeasurementMode2011);logic(s,r->ax,0);int probe=(r->flags&ZF)!=0;
    if(!probe){
        (void)arith(s,r->ax,0x190,1,0);
        if(!(r->flags&ZF)){r->bx=shr(s,r->bx,0);(void)arith(s,r->ax,0xC8,1,0);probe=!(r->flags&ZF);}
    }
    if(probe){
        if(!child(s,CS_DetectVideoAdapters,0x15D8,detect))return;
        r->bx=0x140;r->di=SEG09A9_PrimaryDetectedAdapterPair;
        al(s,read8(s,r->ds,(uint16_t)(r->di+1u)));(void)arith(s,(uint8_t)r->ax,3,1,1);
        int slow=(!!(r->flags&SF))^(!!(r->flags&OF));
#if VIDEO_PROBE_MUTATION == 3
        slow=(uint8_t)r->ax<3u;
#endif
        if(slow)r->bx=0xA0;
    }
#if VIDEO_PROBE_MUTATION != 7
    r->flags&=(uint16_t)~IF;
#endif
    if(!child(s,CS_MeasureRasterPitCounter,0x15ED,measure))return;
    r->ax=arith(s,0xFFFF,r->cx,1,0);r->bp=r->ax;write16(s,r->ds,SEG09A9_TimerPitReload1FC9,r->bp);
    r->ax=pop(s);logic(s,r->ax,0);
#if VIDEO_PROBE_MUTATION != 4
    if(!(r->flags&ZF))write16(s,r->ds,SEG09A9_TimerPitReload1FC9,r->ax);
#endif
    r->flags|=IF;r->ip=0x1601;
}
static void game_video(Probe *s){
    LmnRegs *r=&s->out.registers;r->flags&=(uint16_t)~IF;r->ax=0x8D;if(!bios(s,0xFB8))return;
    r->dx=read16(s,r->ds,SEG09A9_DisplayControllerBasePort);r->ax=0x1613;
    const LmnRasterBus *b=bus(s);if(!b||!b->out_word){r->ip=0xFBF;s->out.status=LMN_VIDEO_PROBE_MISSING_WORD_OUTPUT;return;
    }
    b->out_word(b->context,r->dx,r->ax,r->flags);
#if VIDEO_PROBE_MUTATION != 1
    r->flags|=IF;
#endif
    const uint16_t slots[]={CS_DrawEntityAlignedSprite,CS_DrawEntityShiftedSprite12,CS_DrawEntityShiftedSprite13,
        CS_DrawEntityShiftedSprite3Plane10,CS_DrawEntityShiftedSprite3Plane13,CS_DrawEntityShiftedSprite3Plane14,
        CS_DrawEntityShiftedSprite3Plane16,CS_DrawEntityWideSprite32,CS_DrawEntityShiftedSprite4Plane14};
    for(unsigned n=0;n<9;n++)write16(s,r->ds,(uint16_t)(SEG09A9_DrawingCallbackSlots+2u*n),slots[n]);
    r->ip=0xFF7;
}
LmnVideoProbeResult lmn_video_probe_core(uint8_t *memory,const LmnRegs *registers,LmnVideoProbeEntry entry,const LmnVideoProbeServices *services){
    Probe s={memory,services,{*registers,0,0,0}};
    const Body bodies[]={detect,dcc,ega,color,mono,probe_crtc,store_pair,calibrate,measure,game_video};
    bodies[entry](&s);return s.out;
}
LmnVideoProbeResult lmn_video_probe_adapter(uint8_t *memory,const LmnRegs *registers,LmnVideoProbeEntry entry,const LmnVideoProbeServices *services){
    LmnVideoProbeResult out=lmn_video_probe_core(memory,registers,entry,services);Probe s={memory,services,out};
    if(!out.status)s.out.registers.ip=pop(&s);
    return s.out;
}

#include "startup.h"
#include "checksum.h"
#include "dat_cache.h"
#include "vga_mirrors.h"
#include "display_status.h"
#include "lemmings_sym.h"

#ifndef STARTUP_MUTATION
#define STARTUP_MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,IF=512,DF=1024,OF=2048,ARITH=0x8D5};
typedef struct Startup {
    uint8_t *mem;
    const LmnStartupServices *services;
    LmnStartupResult out;
} Startup;
static const LmnRasterBus *bus(Startup *s){return s->services?s->services->bus:0;}
static uint32_t physical(uint16_t seg,uint16_t off){return (((uint32_t)seg<<4)+off)&0xFFFFFu;}
static uint8_t read_at(Startup *s,uint32_t p){
    const LmnRasterBus *b=bus(s);p&=0xFFFFFu;
    return b&&b->read_byte?b->read_byte(b->context,s->mem,p,s->out.registers.flags):s->mem[p];
}
static void write_at(Startup *s,uint32_t p,uint8_t v){
    const LmnRasterBus *b=bus(s);p&=0xFFFFFu;
    if(b&&b->write_byte)b->write_byte(b->context,s->mem,p,v,s->out.registers.flags);else s->mem[p]=v;
}
static uint8_t read8(Startup *s,uint16_t seg,uint16_t off){return read_at(s,physical(seg,off));}
static uint16_t read16(Startup *s,uint16_t seg,uint16_t off){
    uint32_t p=physical(seg,off);uint8_t lo=read_at(s,p),hi=read_at(s,p+1u);return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void write16(Startup *s,uint16_t seg,uint16_t off,uint16_t v){
    uint32_t p=physical(seg,off);write_at(s,p,(uint8_t)v);write_at(s,p+1u,(uint8_t)(v>>8));
}
static void store(Startup *s,uint16_t off,uint16_t v){write16(s,s->out.registers.ds,off,v);}
static void byte(Startup *s,uint16_t off,uint8_t v){write_at(s,physical(s->out.registers.ds,off),v);}
static void push(Startup *s,uint16_t v){LmnRegs *r=&s->out.registers;r->sp=(uint16_t)(r->sp-2u);write16(s,r->ss,r->sp,v);}
static uint16_t pop(Startup *s){LmnRegs *r=&s->out.registers;uint16_t v=read16(s,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);return v;}
static void al(Startup *s,uint8_t v){s->out.registers.ax=(uint16_t)((s->out.registers.ax&0xFF00u)|v);}
static void ah(Startup *s,uint8_t v){s->out.registers.ax=(uint16_t)((s->out.registers.ax&255u)|((uint16_t)v<<8));}
static void bl(Startup *s,uint8_t v){s->out.registers.bx=(uint16_t)((s->out.registers.bx&0xFF00u)|v);}
static void dl(Startup *s,uint8_t v){s->out.registers.dx=(uint16_t)((s->out.registers.dx&0xFF00u)|v);}
static uint16_t szp(uint16_t v,int narrow){
    unsigned parity=0;for(unsigned n=0;n<8;n++)parity^=(v>>n)&1u;
    return (uint16_t)((parity?0:PF)|(v?0:ZF)|(v&(narrow?128u:0x8000u)?SF:0));
}
static uint16_t arithmetic(Startup *s,uint16_t a,uint16_t b,int sub,int narrow){
    uint16_t mask=narrow?255u:65535u,sign=narrow?128u:0x8000u,v=(uint16_t)((sub?a-b:a+b)&mask);
    s->out.registers.flags=(uint16_t)((s->out.registers.flags&~ARITH)|szp(v,narrow)|
        ((sub?a<b:(uint32_t)a+b>mask)?CF:0)|((a^b^v)&AF)|(((sub?(a^b):~(a^b))&(a^v)&sign)?OF:0));return v;
}
static uint16_t step(Startup *s,uint16_t v,int sub,int narrow){
    uint16_t cf=s->out.registers.flags&CF;v=arithmetic(s,v,1,sub,narrow);
    s->out.registers.flags=(uint16_t)((s->out.registers.flags&~CF)|cf);return v;
}
static void logic(Startup *s,uint16_t v,int narrow){s->out.registers.flags=(uint16_t)((s->out.registers.flags&~ARITH)|szp(v,narrow));}
static int equal(Startup *s,uint16_t a,uint16_t b,int narrow){(void)arithmetic(s,a,b,1,narrow);return (s->out.registers.flags&ZF)!=0;}
static int less(Startup *s,uint8_t a,uint8_t b){(void)arithmetic(s,a,b,1,1);return !!(s->out.registers.flags&SF)!=!!(s->out.registers.flags&OF);}
static int greater(Startup *s,uint8_t a,uint8_t b){
    (void)arithmetic(s,a,b,1,1);return !(s->out.registers.flags&ZF) && (!!(s->out.registers.flags&SF)==!!(s->out.registers.flags&OF));
}
static uint16_t shl(Startup *s,uint16_t v){
    uint16_t out=(uint16_t)(v<<1);s->out.registers.flags=(uint16_t)((s->out.registers.flags&~ARITH)|szp(out,0)|
        (v&0x8000u?CF:0)|((v^out)&0x8000u?OF:0));return out;
}
static int returned(Startup *s,uint16_t cs,uint16_t resume){
    LmnRegs *r=&s->out.registers;if(s->out.status)return 0;r->ip=pop(s);
    if(r->cs==cs&&r->ip==resume)return 1;
    s->out.status=LMN_STARTUP_CHANGED_RETURN;return 0;
}
typedef void (*Child)(Startup *);
static int child(Startup *s,uint16_t entry,uint16_t resume,Child fn){
    uint16_t cs=s->out.registers.cs;push(s,resume);s->out.registers.ip=entry;s->out.child_entry=entry;
    fn(s);return returned(s,cs,resume);
}
static int interrupt(Startup *s,uint16_t number,uint16_t resume){
    const LmnStartupServices *p=s->services;const LmnInterruptService *service=0;
    if(p)service=number==0x21?p->dos:number==0x10?p->bios:number==0x1A?p->clock:p->mouse;
    LmnInterruptResult out=lmn_interrupt_service(s->mem,&s->out.registers,number,resume,service,bus(s));
    if(out.status){s->out.status=LMN_STARTUP_INTERRUPT_STOP;s->out.child_status=out.status;s->out.service_status=out.service_status;return 0;}
    return 1;
}
static void terminate(Startup *s,uint16_t resume){
    s->out.registers.ax=0x4C00;
    if(interrupt(s,0x21,resume))s->out.status=LMN_STARTUP_DOS_EXIT;
}
static int output(Startup *s,uint16_t port,uint16_t pc){
    const LmnRasterBytePorts *p=s->services?s->services->ports:0;
    if(!p||!p->out_byte){s->out.registers.ip=pc;s->out.status=LMN_STARTUP_MISSING_PORT;return 0;}
    p->out_byte(p->context,s->mem,port,(uint8_t)s->out.registers.ax,s->out.registers.flags);return 1;
}

/* 13A8 parses unsigned decimal into a wrapped word. A final byte is read but
   discarded if its preceding DEC makes CX zero. Separator consumption and
   the caller's LOOP decrement are independent and intentionally retained. */
static void parse_reload(Startup *s){
    LmnRegs *r=&s->out.registers;
    do{
        r->bx=0;logic(s,0,0);al(s,read8(s,r->es,r->si));r->si=step(s,r->si,0,0);
        r->cx=step(s,r->cx,1,0);logic(s,r->cx,0);if(!r->cx){r->ip=0x12B0;return;}
    }while(equal(s,(uint8_t)r->ax,0x20,1));
    for(;;){
        if(less(s,(uint8_t)r->ax,'0'))break;
        if(greater(s,(uint8_t)r->ax,'9'))break;
        al(s,(uint8_t)arithmetic(s,(uint8_t)r->ax,'0',1,1));ah(s,0);logic(s,0,1);
        r->bx=shl(s,r->bx);r->dx=r->bx;r->bx=shl(s,r->bx);r->bx=shl(s,r->bx);
        r->bx=arithmetic(s,r->bx,r->dx,0,0);r->bx=arithmetic(s,r->bx,r->ax,0,0);
        r->cx=step(s,r->cx,1,0);if(!r->cx)break;
        al(s,read8(s,r->es,r->si));r->si=step(s,r->si,0,0);
    }r->ip=0x13DB;
}
static void command_line(Startup *s){
    LmnRegs *r=&s->out.registers;r->es=read16(s,r->ds,0x1FF6);r->si=0x80;
    r->cx=read8(s,r->es,r->si);logic(s,0,1);if(!r->cx){r->ip=0x12B0;return;}
    r->si=step(s,r->si,0,0);
    do{
        al(s,read8(s,r->es,r->si));r->si=step(s,r->si,0,0);
        if(!equal(s,(uint8_t)r->ax,'-',1)&&!equal(s,(uint8_t)r->ax,'/',1))goto next;
        r->cx=step(s,r->cx,1,0);if(!r->cx)break;
        al(s,read8(s,r->es,r->si));r->si=step(s,r->si,0,0);
        if(!less(s,(uint8_t)r->ax,'A')&&!greater(s,(uint8_t)r->ax,'Z')){
#if STARTUP_MUTATION != 2
            al(s,(uint8_t)(r->ax|0x20u));logic(s,(uint8_t)r->ax,1);
#endif
        }
        /* CMP order is observable in returned flags for an unknown switch. */
        if(equal(s,(uint8_t)r->ax,'a',1))byte(s,0x2010,255);
        else if(equal(s,(uint8_t)r->ax,'m',1)){byte(s,0x200F,255);store(s,0x1FDA,0x3D4);store(s,0x1FDC,0x3DA);}
        else if(equal(s,(uint8_t)r->ax,'n',1))byte(s,SEG09A9_MouseServicesDisabledByte,255);
        else if(equal(s,(uint8_t)r->ax,'d',1)){byte(s,0x200B,255);byte(s,0x200E,255);}
        else if(equal(s,(uint8_t)r->ax,'e',1))store(s,0x1F7C,2);
        else if(equal(s,(uint8_t)r->ax,'p',1)){byte(s,0x200A,255);byte(s,0x1FC6,0x74);store(s,0x1FC9,0x3468);store(s,0x1FDA,0x3D4);store(s,0x1FDC,0x3DA);}
        else if(equal(s,(uint8_t)r->ax,'o',1)){byte(s,0x200D,255);byte(s,0x200C,255);}
        else if(equal(s,(uint8_t)r->ax,'v',1))store(s,0x1F7C,4);
        else if(equal(s,(uint8_t)r->ax,'2',1))store(s,0x2011,200);
        else if(equal(s,(uint8_t)r->ax,'4',1))store(s,0x2011,400);
        else if(equal(s,(uint8_t)r->ax,'i',1)){
            if(!child(s,0x13A8,0x1396,parse_reload)){return;}
#if STARTUP_MUTATION == 6
            ++r->bx;
#endif
            logic(s,r->bx,0);if(r->bx)store(s,0x1FC9,r->bx);logic(s,r->cx,0);if(!r->cx)break;
        }else if(equal(s,(uint8_t)r->ax,'x',1))byte(s,0x200E,255);
next:  --r->cx;
    }while(r->cx);
    r->ip=0x12B0;
}
static void print_zero_string(Startup *s){
    LmnRegs *r=&s->out.registers;
    for(;;){
        dl(s,read8(s,r->ds,r->bx));r->bx=step(s,r->bx,0,0);logic(s,(uint8_t)r->dx,1);
        if(!(uint8_t)r->dx){r->ip=0x1227;return;}
        push(s,r->bx);ah(s,2);if(!interrupt(s,0x21,0x1224)){return;}r->bx=pop(s);
    }
}
static void mark_selection(Startup *s){
    LmnRegs *r=&s->out.registers;
#if STARTUP_MUTATION == 5
    r->si=0x239F;
#endif
    store(s,r->di,0x2020);store(s,r->si,0x3E2D);r->di=r->si;
    push(s,r->di);push(s,r->bx);ah(s,15);if(!interrupt(s,0x10,0x11A4)){return;}
    ah(s,2);r->dx=0x100;if(!interrupt(s,0x10,0x11AB)){return;}r->bx=0x2384;
    if(!child(s,0x1218,0x11B2,print_zero_string)){return;}
    r->bx=pop(s);r->di=pop(s);r->ip=0x11B4;
}
static int wait_display(Startup *s){
    LmnRegs *r=&s->out.registers;uint16_t cs=r->cs;push(s,0x1113);r->ip=0x1550;
    lmn_wait_display_status_bit3_cycle_adapter(s->mem,r,s->services?s->services->ports:0,bus(s));
    if(r->ip==CS_DisplayStatusWaitSet||r->ip==CS_DisplayStatusWaitClear){s->out.status=LMN_STARTUP_MISSING_PORT;return 0;}
    if(r->cs!=cs||r->ip!=0x1113){s->out.status=LMN_STARTUP_CHANGED_RETURN;return 0;}return 1;
}
static int direct_marker(Startup *s){mark_selection(s);return !s->out.status;}
static void options(Startup *s){
    LmnRegs *r=&s->out.registers;r->ax=3;if(!interrupt(s,0x10,0x1073)){return;}
    if(!equal(s,read16(s,r->ds,0x1F7C),255,0)){
        const uint16_t flags[]={0x200A,0x200B,0x200D,0x200C};
        for(unsigned n=0;n<4;n++)if(equal(s,read8(s,r->ds,flags[n]),255,1)){r->ip=0x1227;return;}
    }
    r->bx=0x2260;if(!child(s,0x1218,0x10AA,print_zero_string)){return;}
    if(equal(s,read16(s,r->ds,0x1F7C),255,0)){
        r->bx=0x22E1;if(!child(s,0x1218,0x10B8,print_zero_string)){return;}
        for(;;){
            ah(s,7);if(!interrupt(s,0x21,0x10BC)){return;}if(equal(s,(uint8_t)r->ax,27,1))goto exit;
            r->cx=4;if(equal(s,(uint8_t)r->ax,'1',1))break;
            r->cx=2;if(equal(s,(uint8_t)r->ax,'2',1))break;
        }
        store(s,0x1F7C,r->cx);dl(s,(uint8_t)r->ax);ah(s,2);if(!interrupt(s,0x21,0x10DB)){return;}
    }
    /* The original early flag paths tail-enter1194 with live parser SI/DI. */
    for(unsigned n=0;n<3;n++){
        const uint16_t off[]={0x200A,0x200B,0x200D};
        if(equal(s,read8(s,r->ds,off[n]),255,1)){(void)direct_marker(s);return;}
    }
    ah(s,15);if(!interrupt(s,0x10,0x10FD)){return;}ah(s,2);r->dx=0x100;
    if(!interrupt(s,0x10,0x1104)){return;}r->bx=0x2384;
    if(!child(s,0x1218,0x110A,print_zero_string)){return;}bl(s,0);logic(s,0,1);r->di=0x239F;
    for(;;){
        if(!wait_display(s)){return;}push(s,r->bx);ah(s,7);if(!interrupt(s,0x21,0x1118)){return;}r->bx=pop(s);logic(s,(uint8_t)r->ax,1);
        if(!(uint8_t)r->ax){
            push(s,r->bx);ah(s,7);if(!interrupt(s,0x21,0x1122)){return;}r->bx=pop(s);
            if(equal(s,(uint8_t)r->ax,0x48,1)){logic(s,(uint8_t)r->bx,1);if(!(uint8_t)r->bx)continue;bl(s,(uint8_t)step(s,(uint8_t)r->bx,1,1));}
            else {if(!equal(s,(uint8_t)r->ax,0x50,1))continue;if(equal(s,(uint8_t)r->bx,4,1))continue;bl(s,(uint8_t)step(s,(uint8_t)r->bx,0,1));}
            r->si=0x239F;logic(s,(uint8_t)r->bx,1);
            if((uint8_t)r->bx){r->si=0x240B;if(!equal(s,(uint8_t)r->bx,2,1)){r->si=0x2442;if(!equal(s,(uint8_t)r->bx,3,1)){r->si=0x23D2;if(!equal(s,(uint8_t)r->bx,1,1))r->si=0x248A;}}}
            if(!child(s,0x1194,0x11DF,mark_selection)){return;}continue;
        }
        if(equal(s,(uint8_t)r->ax,27,1))goto exit;
        if(!equal(s,(uint8_t)r->ax,13,1)&&!equal(s,(uint8_t)r->ax,10,1)){
            if(equal(s,(uint8_t)r->ax,'1',1)){bl(s,0);logic(s,0,1);}
            else if(equal(s,(uint8_t)r->ax,'2',1))bl(s,1);
            else if(equal(s,(uint8_t)r->ax,'3',1))bl(s,2);
            else if(equal(s,(uint8_t)r->ax,'4',1))bl(s,3);else continue;
        }
        r->si=0x239F;logic(s,(uint8_t)r->bx,1);
        if(!(uint8_t)r->bx){byte(s,0x200E,255);byte(s,0x200C,255);(void)direct_marker(s);return;}
        r->si=0x240B;if(equal(s,(uint8_t)r->bx,2,1)){byte(s,0x200A,255);byte(s,0x1FC6,0x74);store(s,0x1FC9,0x3468);(void)direct_marker(s);return;}
        r->si=0x2442;if(equal(s,(uint8_t)r->bx,3,1)){byte(s,0x200B,255);byte(s,0x200E,255);(void)direct_marker(s);return;}
        r->si=0x23D2;if(equal(s,(uint8_t)r->bx,1,1)){(void)direct_marker(s);return;}
        goto exit;
    }
exit:r->si=0x248A;if(!child(s,0x1194,0x1213,mark_selection)){return;}terminate(s,0x1218);
}

static void restore_video(Startup *s){
    LmnRegs *r=&s->out.registers;al(s,read8(s,r->ds,SEG09A9_SavedVideoMode));ah(s,0);logic(s,0,1);
    if(!interrupt(s,0x10,0x0FFF)){return;}ah(s,5);al(s,read8(s,r->ds,SEG09A9_SavedVideoPage));
    if(interrupt(s,0x10,0x1006))r->ip=0x1006;
}
static void restore_keyboard(Startup *s){
    LmnRegs *r=&s->out.registers;push(s,r->ds);r->ax=0x2509;r->dx=read16(s,r->ds,0x1FBA);r->ds=read16(s,r->ds,0x1FBC);
    if(!interrupt(s,0x21,0x1590)){return;}r->ds=pop(s);r->ip=0x1591;
}
static void hex_nibble(Startup *s){
    LmnRegs *r=&s->out.registers;ah(s,(uint8_t)((r->ax>>8)&15u));logic(s,(uint8_t)(r->ax>>8),1);
    r->bx=(uint8_t)(r->ax>>8);logic(s,0,1);r->bx=arithmetic(s,r->bx,0x224F,0,0);
    dl(s,read8(s,r->ds,r->bx));byte(s,r->si,(uint8_t)r->dx);r->si=step(s,r->si,0,0);r->ip=0x124F;
}
static void shift_high_nibble(Startup *s){
    LmnRegs *r=&s->out.registers;r->cx=(uint16_t)((r->cx&0xFF00u)|4u);
    uint8_t in=(uint8_t)(r->ax>>8),v=in>>4;ah(s,v);
    /* OF and AF are undefined for SHR by four. */
    r->flags=(uint16_t)((r->flags&~ARITH)|szp(v,1)|((in>>3)&1u));
}
static void hex_word(Startup *s){
    LmnRegs *r=&s->out.registers;push(s,r->ax);shift_high_nibble(s);
    if(!child(s,0x123F,0x1230,hex_nibble)){return;}r->ax=pop(s);
    if(!child(s,0x123F,0x1234,hex_nibble)){return;}ah(s,(uint8_t)r->ax);push(s,r->ax);shift_high_nibble(s);
    if(!child(s,0x123F,0x123E,hex_nibble)){return;}r->ax=pop(s);hex_nibble(s);
}
static void allocate(Startup *s){
    LmnRegs *r=&s->out.registers;ah(s,0x48);r->bx=0x5571;if(!interrupt(s,0x21,0x100E)){return;}
    if(!(r->flags&CF)){
        store(s,0x1FE4,r->ax);store(s,0x1FF0,r->ax);
        const uint16_t delta[]={0x1000+(STARTUP_MUTATION==3),0x1D0C,0x166,0x90,0x7C,0x17F3,0x200};
        const uint16_t off[]={0x1FE6,0x1FE8,0x1FEA,0x1FEC,0x1FEE,0x1FF2,0x1FF4};
        for(unsigned n=0;n<7;n++){r->ax=arithmetic(s,r->ax,delta[n],0,0);store(s,off[n],r->ax);}
        r->ax=arithmetic(s,r->ax,0xC00,0,0);r->ip=0x1043;return;
    }
    push(s,r->ax);push(s,r->bx);if(!child(s,0xFF8,0x1049,restore_video)){return;}
    r->bx=pop(s);r->ax=r->bx;if(!child(s,0x1228,0x104F,hex_word)){return;}
    dl(s,':');ah(s,2);if(!interrupt(s,0x21,0x1055)){return;}dl(s,' ');ah(s,2);if(!interrupt(s,0x21,0x105B)){return;}
    r->ax=pop(s);r->dx=0x21C8;if(!equal(s,r->ax,7,0))r->dx=0x21EA;
    ah(s,9);if(!interrupt(s,0x21,0x106B)){return;}
    if(!child(s,0x1582,0x4ED,restore_keyboard)){return;}r->dx=SEG09A9_CleanupExitMessage;ah(s,9);
    if(!interrupt(s,0x21,0x4F4)){return;}terminate(s,0x4F9);
}
static void mouse_hooks(Startup *s){
    LmnRegs *r=&s->out.registers;if(equal(s,read8(s,r->ds,SEG09A9_MouseServicesDisabledByte),255,1))goto absent;
    r->ax=0;logic(s,0,0);if(!interrupt(s,0x33,0xF13)){return;}logic(s,r->ax,0);if(!r->ax)goto absent;
    r->ax=15;r->cx=16;r->dx=16;if(!interrupt(s,0x33,0xF22)){return;}
    r->ax=7;r->cx=8;r->dx=0x148;if(!interrupt(s,0x33,0xF2D)){return;}
    r->ax=8;r->cx=8;r->dx=0xC8;if(!interrupt(s,0x33,0xF38)){return;}
    r->ax=4;r->cx=0x96;r->dx=0x64;if(!interrupt(s,0x33,0xF43)){return;}
    r->ax=2;if(!interrupt(s,0x33,0xF48)){return;}r->ax=12;r->cx=STARTUP_MUTATION==4?0x3F:0x7F;push(s,r->cs);r->es=pop(s);r->dx=0xF6F;
    if(!interrupt(s,0x33,0xF55)){return;}ah(s,0x25);al(s,read8(s,r->ds,0x1FC6));push(s,r->ds);push(s,r->cs);r->ds=pop(s);r->dx=0xF70;
    if(!interrupt(s,0x21,0xF62)){return;}r->ds=pop(s);r->ip=0xF63;return;
absent:byte(s,0x25A6,2);byte(s,SEG09A9_MouseServicesDisabledByte,255);r->ip=0xF6E;
}
static int provider_child(Startup *s,uint16_t entry,uint16_t resume,LmnStartupChild fn){
    uint16_t cs=s->out.registers.cs;push(s,resume);s->out.registers.ip=entry;s->out.child_entry=entry;
    uint16_t status=fn(s->services->child_context,s->mem,&s->out.registers,bus(s));
    if(status){s->out.status=LMN_STARTUP_CHILD_STOP;s->out.child_status=status;return 0;}
    return returned(s,cs,resume);
}
static int adapted(Startup *s,uint16_t cs,uint16_t resume,uint16_t status){
    if(status){s->out.status=LMN_STARTUP_CHILD_STOP;s->out.child_status=status;return 0;}
    if(s->out.registers.cs!=cs||s->out.registers.ip!=resume){s->out.status=LMN_STARTUP_CHANGED_RETURN;return 0;}return 1;
}
static void program(Startup *s){
    LmnRegs *r=&s->out.registers;uint16_t cs=r->cs,status;
    r->dx=(uint16_t)(s->mem[physical(r->cs,1)]|((uint16_t)s->mem[physical(r->cs,2)]<<8));r->ds=r->dx;push(s,r->es);
    s->out.child_entry=0x8343;
    push(s,9);lmn_initialize_code_checksum_adapter(s->mem,r);if(!adapted(s,cs,9,0)){return;}
    write_at(s,physical(r->cs,0x83B8),(uint8_t)r->ax);
    push(s,0x10);lmn_initialize_code_checksum_adapter(s->mem,r);if(!adapted(s,cs,0x10,0)){return;}
    write_at(s,physical(r->cs,0x83BD),(uint8_t)r->ax);ah(s,0);logic(s,0,1);
    if(!interrupt(s,0x1A,0x18)){return;}store(s,SEG09A9_SavedBiosClockLow,r->dx);store(s,SEG09A9_SavedBiosClockHigh,r->cx);
    ah(s,0x4A);r->bx=0x1911;if(!interrupt(s,0x21,0x27)){return;}
    push(s,r->ds);r->es=pop(s);r->di=0;r->cx=0x2012;al(s,0);logic(s,0,1);
    do{write_at(s,physical(r->es,r->di),(uint8_t)r->ax);r->di=(uint16_t)(r->di+(r->flags&DF?-1:1));--r->cx;}while(r->cx);
    r->ax=pop(s);store(s,0x1FF6,r->ax);
    s->out.child_entry=0x4F9;
    push(s,0x3A);status=lmn_initialize_vga_register_mirrors_adapter(s->mem,r,bus(s));if(!adapted(s,cs,0x3A,status)){return;}
    store(s,0x1F7C,255);byte(s,0x1FC6,12);byte(s,0x200F,255);
    if(!child(s,0x1293,0x4D,command_line)||!child(s,0x106E,0x50,options)){return;}
    r->ax=0x3509;if(!interrupt(s,0x21,0x55)){return;}store(s,0x1FBC,r->es);store(s,0x1FBA,r->bx);
    r->ax=0x3508;if(!interrupt(s,0x21,0x62)){return;}store(s,0x1FBE,r->bx);store(s,0x1FC0,r->es);
    ah(s,0x35);al(s,read8(s,r->ds,0x1FC6));if(!interrupt(s,0x21,0x71)){return;}store(s,0x1FC2,r->bx);store(s,0x1FC4,r->es);
    r->ax=0x2562;push(s,r->ds);push(s,r->es);r->ds=pop(s);r->dx=r->bx;if(!interrupt(s,0x21,0x83)){return;}r->ds=pop(s);
    push(s,r->ds);r->ax=0x2524;push(s,r->cs);r->ds=pop(s);r->dx=0x18F8;if(!interrupt(s,0x21,0x8F)){return;}r->ds=pop(s);byte(s,0x1FDF,0);
    push(s,r->ds);ah(s,0x1B);if(!interrupt(s,0x21,0x9A)){return;}al(s,read8(s,r->ds,r->bx));r->ds=pop(s);
#if STARTUP_MUTATION == 1
    byte(s,0x1FDF,(uint8_t)r->ax);
#else
    byte(s,0x1FDE,(uint8_t)r->ax);
#endif
    ah(s,15);if(!interrupt(s,0x10,0xA4)){return;}byte(s,SEG09A9_SavedVideoMode,(uint8_t)r->ax);byte(s,SEG09A9_SavedVideoPage,(uint8_t)(r->bx>>8));
    r->ip=0xAB;s->out.child_entry=0x54E;
    if(!s->services||!s->services->sound){s->out.status=LMN_STARTUP_SOUND_SEAM;return;}
    push(s,0xAE);r->ip=0x54E;
    LmnSoundDriverInitResult sound=lmn_initialize_sound_driver_adapter(s->mem,r,s->services->sound,bus(s));
    if(!adapted(s,cs,0xAE,sound.status)){s->out.service_status=sound.service_status;return;}
    if(!child(s,0x1007,0xB1,allocate)||!child(s,0xF08,0xB4,mouse_hooks)){return;}
    write_at(s,physical(r->cs,0x83BE),255);r->ax=13;if(!interrupt(s,0x10,0xC0)){return;}ah(s,9);r->dx=0x2200;if(!interrupt(s,0x21,0xC8)){return;}
    push(s,0xCB);r->ip=0x15AD;s->out.child_entry=0x15AD;
    LmnVideoProbeServices probe={s->services->bios,s->services->ports,bus(s)};
    LmnVideoProbeResult video=lmn_video_probe_adapter(s->mem,r,LMN_VIDEO_CALIBRATE,&probe);*r=video.registers;
    if(!adapted(s,cs,0xCB,video.status)){s->out.service_status=video.service_status;return;}
    al(s,0x36);if(!output(s,0x43,0xCD)){return;}al(s,0);logic(s,0,1);if(!output(s,0x40,0xD1)||!output(s,0x40,0xD3)){return;}
    push(s,0xD8);r->ip=0x58D2;s->out.child_entry=0x58D2;
    status=lmn_load_main_resource_sections_adapter(s->mem,r,s->services->files,s->services->io,bus(s));
    if(!adapted(s,cs,0xD8,status)){return;}
    push(s,0xDB);s->out.child_entry=0x1ED1;lmn_dat_disable_cache_adapter(s->mem,r);if(!adapted(s,cs,0xDB,0)){return;}byte(s,SEG09A9_DatRetryEnabled,255);
    r->ip=0xE0;s->out.child_entry=0x62B;
    if(!s->services->protection){s->out.status=LMN_STARTUP_PROTECTION_SEAM;return;}
    if(!provider_child(s,0x62B,0xE3,s->services->protection)){return;}
    push(s,0xE6);r->ip=0x1562;s->out.child_entry=0x1562;
    LmnKeyboardResult keyboard=lmn_install_keyboard_adapter(s->mem,r,s->services->dos,bus(s));*r=keyboard.registers;
    if(!adapted(s,cs,0xE6,keyboard.status)){s->out.service_status=keyboard.service_status;return;}
    r->flags&=(uint16_t)~IF;r->cx=read16(s,r->ds,0x1FC9);al(s,0x36);if(!output(s,0x43,0xED)){return;}
    al(s,(uint8_t)r->cx);if(!output(s,0x40,0xF1)){return;}al(s,(uint8_t)(r->cx>>8));if(!output(s,0x40,0xF5)){return;}
    r->flags|=IF;r->ip=0x43F2;s->out.child_entry=0;
}
LmnStartupResult lmn_startup_core(uint8_t *memory,const LmnRegs *registers,enum LmnStartupEntry entry,const LmnStartupServices *services){
    Startup s={memory,services,{*registers,0,0,0,0}};
    switch(entry){case LMN_STARTUP_PROGRAM:program(&s);break;case LMN_STARTUP_COMMAND_LINE:command_line(&s);break;
        case LMN_STARTUP_OPTIONS:options(&s);break;case LMN_STARTUP_ALLOCATE:allocate(&s);break;case LMN_STARTUP_MOUSE:mouse_hooks(&s);break;}
    return s.out;
}

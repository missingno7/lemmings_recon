#include "keyboard_input.h"
#include "lemmings_sym.h"

#ifndef KEYBOARD_INPUT_MUTATION
#define KEYBOARD_INPUT_MUTATION 0
#endif

enum {CF=1,PF=4,AF=16,ZF=64,SF=128,IF=512,OF=2048,
      ARITH=CF|PF|AF|ZF|SF|OF,LOGIC=CF|PF|ZF|SF|OF};
typedef struct KeyboardState {
    uint8_t *memory;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    LmnRegs r;
    uint16_t entry_cs,status,child_status,service_status;
} KeyboardState;

static uint32_t physical(uint16_t seg,uint16_t off) {
    return (((uint32_t)seg<<4)+off)&0xfffffu;
}
static uint8_t read_physical(KeyboardState *s,uint32_t at) {
    at&=0xfffffu;
    return s->bus && s->bus->read_byte ?
        s->bus->read_byte(s->bus->context,s->memory,at,s->r.flags):s->memory[at];
}
static void write_physical(KeyboardState *s,uint32_t at,uint8_t v,uint16_t f) {
    at&=0xfffffu;
    if(s->bus && s->bus->write_byte)s->bus->write_byte(s->bus->context,s->memory,at,v,f);
    else s->memory[at]=v;
}
static uint8_t read8(KeyboardState *s,uint16_t seg,uint16_t off) {
    return read_physical(s,physical(seg,off));
}
static uint16_t read16(KeyboardState *s,uint16_t seg,uint16_t off) {
    uint32_t at=physical(seg,off);
    uint8_t lo=read_physical(s,at),hi=read_physical(s,at+1u);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void write8(KeyboardState *s,uint16_t seg,uint16_t off,uint8_t v) {
    write_physical(s,physical(seg,off),v,s->r.flags);
}
static void write16(KeyboardState *s,uint16_t seg,uint16_t off,uint16_t v,uint16_t f) {
    uint32_t at=physical(seg,off);
    write_physical(s,at,(uint8_t)v,f);write_physical(s,at+1u,(uint8_t)(v>>8),f);
}
static void push16(KeyboardState *s,uint16_t v) {
    s->r.sp=(uint16_t)(s->r.sp-2u);write16(s,s->r.ss,s->r.sp,v,s->r.flags);
}
static uint16_t pop16(KeyboardState *s) {
    uint16_t v=read16(s,s->r.ss,s->r.sp);s->r.sp=(uint16_t)(s->r.sp+2u);return v;
}
static uint16_t szp(uint16_t v,unsigned width) {
    unsigned parity=0,i;uint16_t f=0;
    for(i=0;i<8;++i)parity^=(v>>i)&1u;
    if(parity==0u)f|=PF;
    if(width==8 ? (uint8_t)v==0u : v==0u)f|=ZF;
    if(v&(width==8?0x80u:0x8000u))f|=SF;
    return f;
}
static void logic(KeyboardState *s,uint16_t v,unsigned width) {
    s->r.flags=(uint16_t)((s->r.flags&~LOGIC)|szp(v,width));
}
static void cmp8(KeyboardState *s,uint8_t a,uint8_t b) {
    uint8_t v=(uint8_t)(a-b);
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(v,8)|(a<b?CF:0)|
        ((a^b^v)&AF)|(((a^b)&(a^v)&0x80u)?OF:0));
}
static uint16_t add16(KeyboardState *s,uint16_t a,uint16_t b) {
    uint32_t sum=(uint32_t)a+b;uint16_t v=(uint16_t)sum;
    s->r.flags=(uint16_t)((s->r.flags&~ARITH)|szp(v,16)|(sum>0xffffu?CF:0)|
        ((a^b^v)&AF)|(((uint16_t)~(a^b)&(a^v)&0x8000u)?OF:0));
    return v;
}
static void inc_bx(KeyboardState *s) {
    uint16_t carry=s->r.flags&CF;
    s->r.bx=add16(s,s->r.bx,1u);s->r.flags=(uint16_t)((s->r.flags&~CF)|carry);
}
static void shift_cx(KeyboardState *s) {
    uint16_t old=s->r.cx;s->r.cx=(uint16_t)(old<<1);
    logic(s,s->r.cx,16);
    if(old&0x8000u)s->r.flags|=CF;
    if((old^s->r.cx)&0x8000u)s->r.flags|=OF;
}
static void al(KeyboardState *s,uint8_t v) {s->r.ax=(uint16_t)((s->r.ax&0xff00u)|v);}
static KeyboardState state(uint8_t *m,const LmnRegs *r,
    const LmnRasterBytePorts *p,const LmnRasterBus *b) {
    KeyboardState s={m,p,b,*r,r->cs,0,0,0};return s;
}
static LmnKeyboardResult result(const KeyboardState *s) {
    LmnKeyboardResult out={s->r,s->status,s->child_status,s->service_status};return out;
}
static int in_byte(KeyboardState *s,uint16_t port,uint16_t ip) {
    s->r.ip=ip;
    if(!s->ports||!s->ports->in_byte){s->status=LMN_KEYBOARD_MISSING_INPUT;return 0;}
    al(s,s->ports->in_byte(s->ports->context,s->memory,port,s->r.flags));return 1;
}
static int out_byte(KeyboardState *s,uint16_t port,uint16_t ip) {
    s->r.ip=ip;
    if(!s->ports||!s->ports->out_byte){s->status=LMN_KEYBOARD_MISSING_OUTPUT;return 0;}
    s->ports->out_byte(s->ports->context,s->memory,port,(uint8_t)s->r.ax,s->r.flags);return 1;
}
static int child(KeyboardState *s,int command,uint16_t resume) {
    LmnPortIoResult out;
    push16(s,resume);
    s->r.ip=command?CS_SendKeyboardControllerCommand:CS_SendMasterPicEoi;
    out=command?lmn_send_keyboard_command_adapter(s->memory,&s->r,s->ports,s->bus):
        lmn_send_master_pic_eoi_adapter(s->memory,&s->r,s->ports,s->bus);
    s->r=out.registers;
    if(out.status){s->status=LMN_KEYBOARD_CHILD_STOP;s->child_status=out.status;return 0;}
    if(s->r.cs!=s->entry_cs||s->r.ip!=resume) {
#if KEYBOARD_INPUT_MUTATION == 6
        s->r.cs=s->entry_cs;s->r.ip=resume;
#else
        s->status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return 0;
#endif
    }
    return 1;
}
static void buttons(KeyboardState *s,uint16_t mask,int set) {
    uint16_t f=s->r.flags,v=read16(s,s->r.ds,SEG09A9_InputButtonsWord);
    v=set?(uint16_t)(v|mask):(uint16_t)(v&mask);logic(s,v,16);
    write16(s,s->r.ds,SEG09A9_InputButtonsWord,v,f);
}
static void key_mask(KeyboardState *s,int set) {
    uint16_t f=s->r.flags,v=read16(s,s->r.ds,SEG09A9_InputKeyMask1FC7);
    v=set?(uint16_t)(v|s->r.cx):(uint16_t)(v&s->r.cx);logic(s,v,16);
    write16(s,s->r.ds,SEG09A9_InputKeyMask1FC7,v,f);
}

LmnKeyboardResult lmn_keyboard_irq_core(uint8_t *memory,const LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    KeyboardState s=state(memory,registers,ports,bus);uint8_t v;
    push16(&s,s.r.ds);push16(&s,s.r.ax);push16(&s,s.r.bx);push16(&s,s.r.cx);
#if KEYBOARD_INPUT_MUTATION == 5
    s.r.ax=(uint16_t)(s.entry_cs+0x09a9u);
#else
    {uint32_t at=physical(s.r.cs,CS_KeyboardDataSegmentOperand16D9);
     s.r.ax=(uint16_t)(memory[at]|((uint16_t)memory[(at+1u)&0xfffffu]<<8));}
#endif
    s.r.ds=s.r.ax;
    v=read8(&s,s.r.ds,SEG09A9_KeyboardControllerGate200A);al(&s,v);logic(&s,v,8);
    if(v!=0u){al(&s,0xadu);if(!child(&s,1,CS_KeyboardAfterDisable16E9))return result(&s);}
    if(!in_byte(&s,0x60u,0x16e9u))return result(&s);
    push16(&s,s.r.ax);
    if(!in_byte(&s,0x61u,0x16ecu))return result(&s);
    v=(uint8_t)s.r.ax|0x80u;al(&s,v);logic(&s,v,8);
    if(!out_byte(&s,0x61u,0x16f0u))return result(&s);
    v=(uint8_t)s.r.ax&0x7fu;al(&s,v);logic(&s,v,8);
    if(!out_byte(&s,0x61u,0x16f4u))return result(&s);
    s.r.ax=pop16(&s);push16(&s,s.r.ax);
    s.r.bx=SEG09A9_KeyboardBindings201F;s.r.cx=1u;
    v=(uint8_t)s.r.ax&0x7fu;
    s.r.ax=(uint16_t)((s.r.ax&0xffu)|((uint16_t)v<<8));logic(&s,v,8);
    logic(&s,(uint8_t)s.r.ax&0x80u,8);
    if((s.r.flags&ZF)!=0u) {
        write8(&s,s.r.ds,SEG09A9_KeyboardScanCodeByte,(uint8_t)(s.r.ax>>8));
        cmp8(&s,read8(&s,s.r.ds,SEG09A9_MouseButtonSuppression200B),0xffu);
        if(s.r.flags&ZF) {
            cmp8(&s,(uint8_t)(s.r.ax>>8),0x7du);
            if(s.r.flags&ZF) {
                write8(&s,s.r.ds,SEG09A9_KeyboardScanCodeByte,0u);
                s.r.ax=0u;logic(&s,0u,16);buttons(&s,2u,1);
            }
            cmp8(&s,(uint8_t)(s.r.ax>>8),0x7eu);
            if(s.r.flags&ZF) {
                write8(&s,s.r.ds,SEG09A9_KeyboardScanCodeByte,0u);
                s.r.ax=0u;logic(&s,0u,16);buttons(&s,1u,1);
            }
        }
    } else {
        write8(&s,s.r.ds,SEG09A9_KeyboardScanCodeByte,0u);
        cmp8(&s,read8(&s,s.r.ds,SEG09A9_MouseButtonSuppression200B),0xffu);
        if(s.r.flags&ZF) {
            cmp8(&s,(uint8_t)(s.r.ax>>8),0x7du);
            if(s.r.flags&ZF){s.r.ax=0u;logic(&s,0u,16);buttons(&s,0xfffdu,0);}
            cmp8(&s,(uint8_t)(s.r.ax>>8),0x7eu);
            if(s.r.flags&ZF){s.r.ax=0u;logic(&s,0u,16);buttons(&s,0xfffeu,0);}
        }
    }
#if KEYBOARD_INPUT_MUTATION == 3
    /* Mutant repairs the special-scan AX-zero quirk before binding lookup. */
    s.r.ax=read16(&s,s.r.ss,s.r.sp);
    s.r.ax=(uint16_t)((s.r.ax&0xffu)|((s.r.ax&0x7fu)<<8));
#endif
    for(;;) {
        cmp8(&s,read8(&s,s.r.ds,s.r.bx),0xffu);
        if(!(s.r.flags&ZF)) {
            cmp8(&s,(uint8_t)(s.r.ax>>8),read8(&s,s.r.ds,s.r.bx));
            if(s.r.flags&ZF) {
                logic(&s,(uint8_t)s.r.ax&0x80u,8);
                if(s.r.flags&ZF)key_mask(&s,1);
                else{s.r.cx=(uint16_t)~s.r.cx;key_mask(&s,0);write8(&s,s.r.ds,SEG09A9_KeyboardScanCodeByte,0u);}
                break;
            }
        }
        inc_bx(&s);shift_cx(&s);if(s.r.flags&CF)break;
    }
    s.r.ax=pop16(&s);s.r.bx=SEG09A9_KeyboardStateBytes0F78;
    s.r.ax&=0xffu;logic(&s,0u,8);s.r.cx=s.r.ax;
    v=(uint8_t)s.r.ax&0x7fu;al(&s,v);logic(&s,v,8);
    cmp8(&s,v,0x53u);
#if KEYBOARD_INPUT_MUTATION == 4
    if(v<0x80u) {
#else
    if(((s.r.flags&SF)!=0u)!=((s.r.flags&OF)!=0u)) {
#endif
        s.r.bx=add16(&s,s.r.bx,s.r.ax);
        v=(uint8_t)s.r.cx&0x80u;logic(&s,v,8);v^=0x80u;logic(&s,v,8);
        s.r.cx=(uint16_t)((s.r.cx&0xff00u)|v);logic(&s,v&0x80u,8);
        if(!(s.r.flags&ZF)){v|=0x14u;logic(&s,v,8);s.r.cx=(uint16_t)((s.r.cx&0xff00u)|v);}
        write8(&s,s.r.ds,s.r.bx,(uint8_t)s.r.cx);
    }
    if(!child(&s,0,CS_KeyboardAfterEoi17A3))return result(&s);
    v=read8(&s,s.r.ds,SEG09A9_KeyboardControllerGate200A);al(&s,v);logic(&s,v,8);
    if(v!=0u){al(&s,0xaeu);if(!child(&s,1,CS_KeyboardAfterEnable17AF))return result(&s);}
    s.r.cx=pop16(&s);s.r.bx=pop16(&s);s.r.ax=pop16(&s);s.r.ds=pop16(&s);
    s.r.ip=CS_KeyboardOuterIret17B3;return result(&s);
}

LmnKeyboardResult lmn_keyboard_irq_adapter(uint8_t *memory,const LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnKeyboardResult out=lmn_keyboard_irq_core(memory,registers,ports,bus);
    if(out.status==0u)lmn_interrupt_return(memory,&out.registers,bus);
    return out;
}

static int dos_interrupt(KeyboardState *s,const LmnInterruptService *dos,uint16_t resume) {
    LmnInterruptResult out=lmn_interrupt_service(s->memory,&s->r,0x21u,resume,dos,s->bus);
    if(out.status==0u)return 1;
    s->service_status=out.service_status;
    s->status=out.status==LMN_INTERRUPT_UNBOUND_SERVICE?LMN_KEYBOARD_UNBOUND_SERVICE:
        out.status==LMN_INTERRUPT_PROVIDER_STOP?LMN_KEYBOARD_PROVIDER_STOP:LMN_KEYBOARD_CHANGED_INTERRUPT_RETURN;
    return 0;
}
LmnKeyboardResult lmn_install_keyboard_core(uint8_t *memory,const LmnRegs *registers,
    const LmnInterruptService *dos,const LmnRasterBus *bus) {
    KeyboardState s=state(memory,registers,0,bus);
    s.r.flags&=(uint16_t)~IF;push16(&s,s.r.ds);push16(&s,s.r.es);
    s.r.ax=0x3509u;
    if(!dos_interrupt(&s,dos,CS_KeyboardInstallAfterQuery156A))return result(&s);
#if KEYBOARD_INPUT_MUTATION == 7
    s.r.ds=registers->ds;
#endif
    write16(&s,s.r.ds,(uint16_t)(SEG09A9_SavedKeyboardVector+2u),s.r.es,s.r.flags);
    write16(&s,s.r.ds,SEG09A9_SavedKeyboardVector,s.r.bx,s.r.flags);
    s.r.dx=s.r.cs;s.r.ds=s.r.dx;s.r.dx=CS_KeyboardIrqHandler;s.r.ax=0x2509u;
    if(!dos_interrupt(&s,dos,CS_KeyboardInstallAfterSet157E))return result(&s);
    s.r.es=pop16(&s);s.r.ds=pop16(&s);s.r.flags|=IF;
    s.r.ip=CS_KeyboardInstallReturn1581;return result(&s);
}
LmnKeyboardResult lmn_install_keyboard_adapter(uint8_t *memory,const LmnRegs *registers,
    const LmnInterruptService *dos,const LmnRasterBus *bus) {
    LmnKeyboardResult out=lmn_install_keyboard_core(memory,registers,dos,bus);
    if(out.status==0u){KeyboardState s=state(memory,&out.registers,0,bus);s.r.ip=pop16(&s);out.registers=s.r;}
    return out;
}

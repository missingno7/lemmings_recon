#include "keyboard_input.h"
#include "lemmings_sym.h"
#include "display_status.h"
#include "display_start.h"
#include "text_stream.h"
#include "background_drawing.h"
#include "display_setup.h"
#include "display_pages.h"
#include "palette_transition.h"

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

LmnKeyboardResult lmn_read_keyboard_character_core(uint8_t *memory,
    const LmnRegs *registers,const LmnRasterBus *bus) {
    KeyboardState s=state(memory,registers,0,bus);
    s.r.si=SEG09A9_KeyboardStateBytes0F78;s.r.bx=0u;logic(&s,0u,16);
    s.r.cx=0x53u;
    for(;;) {
        uint16_t at=(uint16_t)(s.r.bx+s.r.si);
        uint8_t v=read8(&s,s.r.ds,at);
        logic(&s,v&0x80u,8);
        if(!(s.r.flags&ZF)) {
#if KEYBOARD_INPUT_MUTATION != 10
            v=read8(&s,s.r.ds,at);
#endif
            v&=0x7fu;al(&s,v);logic(&s,v,8);
            {uint16_t carry=s.r.flags&CF;
             cmp8(&s,v,1u);v=(uint8_t)(v-1u);al(&s,v);
             s.r.flags=(uint16_t)((s.r.flags&~CF)|carry);}
            logic(&s,v,8);
            if(s.r.flags&ZF) {
#if KEYBOARD_INPUT_MUTATION == 8
                write8(&s,s.r.ds,at,0x85u);
#else
                write8(&s,s.r.ds,at,0x86u);
#endif
                break;
            }
            v|=0x80u;al(&s,v);logic(&s,v,8);
            write8(&s,s.r.ds,at,v);cmp8(&s,v,0x93u);
            if(s.r.flags&ZF)break;
        }
        inc_bx(&s);s.r.cx=(uint16_t)(s.r.cx-1u);
        if(s.r.cx==0u) {
            al(&s,0xffu);s.r.ip=CS_KeyboardCharacterEmptyReturn4D2D;
            return result(&s);
        }
    }
    al(&s,(uint8_t)s.r.bx);s.r.bx=SEG09A9_KeyboardCharacterTable202E;
#if KEYBOARD_INPUT_MUTATION == 9
    s.r.bx=(uint16_t)(s.r.bx+1u);
#endif
    al(&s,read8(&s,s.r.ds,(uint16_t)(s.r.bx+(uint8_t)s.r.ax)));
    s.r.ip=CS_KeyboardCharacterReadyReturn4D4C;return result(&s);
}

LmnKeyboardResult lmn_read_keyboard_character_adapter(uint8_t *memory,
    const LmnRegs *registers,const LmnRasterBus *bus) {
    LmnKeyboardResult out=lmn_read_keyboard_character_core(memory,registers,bus);
    KeyboardState s=state(memory,&out.registers,0,bus);
    s.r.ip=pop16(&s);out.registers=s.r;return out;
}

LmnKeyboardResult lmn_select_input_scale(uint8_t *memory,const LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    KeyboardState s=state(memory,registers,ports,bus);
    for(;;) {
        LmnKeyboardResult character;
        push16(&s,CS_InputScaleAfterWait4AA2);
        s.r.ip=CS_WaitForDisplayStatusBit3Cycle;
        lmn_wait_display_status_bit3_cycle_adapter(memory,&s.r,ports,bus);
        if(!ports||!ports->in_byte) {
            s.status=LMN_KEYBOARD_CHILD_STOP;s.child_status=1u;return result(&s);
        }
        if(s.r.cs!=s.entry_cs||s.r.ip!=CS_InputScaleAfterWait4AA2) {
            s.status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return result(&s);
        }
        push16(&s,CS_InputScaleAfterCharacter4AA5);
        s.r.ip=CS_ReadKeyboardCharacter;
        character=lmn_read_keyboard_character_adapter(memory,&s.r,bus);s.r=character.registers;
        if(s.r.cs!=s.entry_cs||s.r.ip!=CS_InputScaleAfterCharacter4AA5) {
            s.status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return result(&s);
        }
        cmp8(&s,(uint8_t)s.r.ax,0x31u);
        if(s.r.flags&CF)continue;
        cmp8(&s,(uint8_t)s.r.ax,0x34u);
#if KEYBOARD_INPUT_MUTATION == 11
        if(s.r.flags&(CF|ZF))continue;
#else
        if(!(s.r.flags&(CF|ZF)))continue;
#endif
        {uint8_t v=(uint8_t)s.r.ax;cmp8(&s,v,0x30u);al(&s,(uint8_t)(v-0x30u));}
        write8(&s,s.r.ds,SEG09A9_InputAxisScaleSelector2005,(uint8_t)s.r.ax);
        s.r.ip=CS_MenuRefresh4401;return result(&s);
    }
}

LmnKeyboardResult lmn_choose_input_controller_core(uint8_t *memory,
    const LmnRegs *registers,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    KeyboardState s=state(memory,registers,ports,bus);
    for(;;) {
        uint8_t v=read8(&s,s.r.ds,SEG09A9_KeyboardScanCodeByte);
        al(&s,v);logic(&s,v,8);
        if(v!=0u) {
            cmp8(&s,v,0x77u);
            if(s.r.flags&ZF) {
                s.r.cx=(uint16_t)((s.r.cx&0xff00u)|2u);
                s.r.ip=CS_InputControllerChoiceReturn43ED;return result(&s);
            }
        }
        s.r.flags&=(uint16_t)~IF;s.r.dx=0x201u;
        if(!in_byte(&s,s.r.dx,0x43ddu))return result(&s);
        s.r.flags|=IF;v=(uint8_t)~s.r.ax;al(&s,v);logic(&s,v&0xf0u,8);
        if(s.r.flags&ZF)continue;
        s.r.cx&=0xff00u;logic(&s,0u,8);logic(&s,v&0x30u,8);
        if(s.r.flags&ZF) {
            uint16_t carry=s.r.flags&CF;
            s.r.cx|=1u;cmp8(&s,1u,0u); /* INC CL from its known zero. */
            s.r.flags=(uint16_t)((s.r.flags&~CF)|carry);
        }
        s.r.ip=CS_InputControllerChoiceReturn43ED;return result(&s);
    }
}

LmnKeyboardResult lmn_choose_input_controller_adapter(uint8_t *memory,
    const LmnRegs *registers,const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    LmnKeyboardResult out=lmn_choose_input_controller_core(memory,registers,ports,bus);
    if(out.status==0u){KeyboardState s=state(memory,&out.registers,ports,bus);s.r.ip=pop16(&s);out.registers=s.r;}
    return out;
}

static int menu_text(KeyboardState *s,uint16_t resume) {
    LmnTextStreamState in;
    LmnTextStreamResult out;
    push16(s,resume);
    in=(LmnTextStreamState){s->r.ax,s->r.bx,s->r.cx,s->r.dx,s->r.si,s->r.di,s->r.bp,
        s->r.ds,s->r.es,s->r.ss,s->r.sp,s->r.flags};
    out=lmn_draw_text_stream_core(s->memory,s->r.cs,(uint16_t)(s->entry_cs+0x09a9u),&in,s->bus,s->ports);
    s->r=(LmnRegs){out.state.value,out.state.base_value,out.state.count,out.state.argument,
        out.state.source_cursor,out.state.output_cursor,out.state.frame_cursor,out.state.stack_offset,
        out.code_segment,out.state.data_segment,out.state.extra_segment,out.state.stack_segment,
        out.continuation,out.state.flags};
    if(out.status){s->status=LMN_KEYBOARD_CHILD_STOP;s->child_status=(uint16_t)out.status;return 0;}
    s->r.ip=pop16(s);
    if(s->r.cs!=s->entry_cs||s->r.ip!=resume){s->status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return 0;}
    return 1;
}

static int menu_display(KeyboardState *s,uint16_t resume,enum LmnDisplayStartEntry entry) {
    LmnDisplayStartState in;
    LmnDisplayStartResult out;
    uint16_t cs=s->r.cs;
    push16(s,resume);
    in=(LmnDisplayStartState){s->r.ax,s->r.bx,s->r.cx,s->r.dx,s->r.si,s->r.di,s->r.bp,
        s->r.ds,s->r.es,s->r.ss,s->r.sp,s->r.flags};
    out=lmn_program_display_start_core(s->memory,&in,entry,s->bus);
    s->r=(LmnRegs){out.state.value,out.state.base_value,out.state.count,out.state.argument,
        out.state.source_cursor,out.state.output_cursor,out.state.frame_cursor,out.state.stack_offset,
        cs,out.state.data_segment,out.state.extra_segment,out.state.stack_segment,out.continuation,out.state.flags};
    if(out.status){s->status=LMN_KEYBOARD_CHILD_STOP;s->child_status=(uint16_t)out.status;return 0;}
    s->r.ip=pop16(s);
    if(s->r.cs!=s->entry_cs||s->r.ip!=resume){s->status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return 0;}
    return 1;
}

static int menu_swap(KeyboardState *s,uint16_t resume) {
    return menu_display(s,resume,LMN_DISPLAY_START_ENTRY_SWAP);
}

/* These children share the same transient twelve-field ABI. Canonical RAM,
   including all real CALL/save words, remains the only persistent state. */
static int input_screen_child(KeyboardState *s,uint16_t resume,uint16_t entry) {
    LmnVideoRestoreState in,out;
    uint16_t cs=s->r.cs,ip,status;
    push16(s,resume);
    in=(LmnVideoRestoreState){s->r.ax,s->r.bx,s->r.cx,s->r.dx,s->r.si,s->r.di,s->r.bp,
        s->r.ds,s->r.es,s->r.ss,s->r.sp,s->r.flags};
    if(entry==CS_ClearFullDrawingPage||entry==CS_CopyDrawingPageToAlternate) {
        LmnDisplayPagesResult child=entry==CS_ClearFullDrawingPage ?
            lmn_clear_full_drawing_page_core(s->memory,&in,s->bus):
            lmn_copy_drawing_page_core(s->memory,&in,s->bus);
        out=child.state;ip=child.continuation;status=(uint16_t)child.status;
    } else if(entry==CS_InitializeDisplayOrigins) {
        LmnDisplaySetupResult child=lmn_setup_display_core(s->memory,cs,&in,
            LMN_DISPLAY_SETUP_ENTRY_INITIALIZE,NULL,s->bus);
        out=child.state;cs=child.code_segment;ip=child.continuation;status=(uint16_t)child.status;
    } else if(entry==CS_DrawScreenBackground) {
        LmnBackgroundDrawingResult child=lmn_draw_background_core(s->memory,cs,
            (uint16_t)(s->entry_cs+0x09a9u),&in,LMN_BACKGROUND_DRAWING_FULL,s->bus,s->ports);
        out=child.state;cs=child.code_segment;ip=child.continuation;status=(uint16_t)child.status;
    } else {
        LmnPaletteTransitionResult child=lmn_transition_palette_core(s->memory,cs,&in,
            #if KEYBOARD_INPUT_MUTATION == 17
            LMN_PALETTE_TRANSITION_SLOT1,
#else
            entry==CS_TransitionPaletteToSlot1?LMN_PALETTE_TRANSITION_SLOT1:LMN_PALETTE_TRANSITION_SLOT2,
#endif
            s->ports,s->bus);
        out=child.state;cs=child.code_segment;ip=child.continuation;status=(uint16_t)child.status;
    }
    s->r=(LmnRegs){out.value,out.base_value,out.count,out.argument,
        out.source_cursor,out.output_cursor,out.frame_cursor,out.stack_offset,
        cs,out.data_segment,out.extra_segment,out.stack_segment,ip,out.flags};
    if(status){s->status=LMN_KEYBOARD_CHILD_STOP;s->child_status=status;return 0;}
    s->r.ip=pop16(s);
    if(s->r.cs!=s->entry_cs||s->r.ip!=resume){s->status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return 0;}
    return 1;
}

LmnKeyboardResult lmn_select_input_controller(uint8_t *memory,const LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    KeyboardState s=state(memory,registers,ports,bus);
    LmnKeyboardResult choice;
    LmnPortIoResult sample;
    uint16_t resume;
    s.r.si=SEG09A9_ControllerChoiceText4E85;
    if(!menu_text(&s,CS_ControllerMenuAfterText4A55)||!menu_swap(&s,CS_ControllerMenuAfterSwap4A58))return result(&s);
    push16(&s,CS_ControllerMenuAfterChoice4A5B);s.r.ip=CS_ChooseInputController;
    choice=lmn_choose_input_controller_adapter(memory,&s.r,ports,bus);s.r=choice.registers;
    if(choice.status){s.status=LMN_KEYBOARD_CHILD_STOP;s.child_status=choice.status;return result(&s);}
    if(s.r.cs!=s.entry_cs||s.r.ip!=CS_ControllerMenuAfterChoice4A5B){s.status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return result(&s);}
    cmp8(&s,(uint8_t)s.r.cx,2u);
    if(s.r.flags&ZF) {
        write8(&s,s.r.ds,SEG09A9_InputModeByte25A6,2u);s.r.ip=CS_MenuRefresh4401;return result(&s);
    }
    cmp8(&s,(uint8_t)s.r.cx,1u);
    if(s.r.flags&ZF){s.r.ax=CS_PollPort201ButtonsHigh;resume=CS_ControllerMenuAfterHigh4A8B;}
    else{s.r.ax=CS_PollPort201ButtonsLow;resume=CS_ControllerMenuAfterLow4A73;}
#if KEYBOARD_INPUT_MUTATION == 12
    s.r.ax=CS_PollPort201ButtonsLow;
#endif
    write16(&s,s.r.ds,SEG09A9_InputPollCallback,s.r.ax,s.r.flags);
    al(&s,1u);write8(&s,s.r.ds,SEG09A9_InputModeByte25A6,(uint8_t)s.r.ax);
    push16(&s,resume);
    s.r.ip=resume==CS_ControllerMenuAfterHigh4A8B?CS_PollPort201ButtonsHigh:CS_PollPort201ButtonsLow;
    sample=resume==CS_ControllerMenuAfterHigh4A8B ?
        lmn_poll_port201_buttons_high_adapter(memory,&s.r,ports,bus):
        lmn_poll_port201_buttons_low_adapter(memory,&s.r,ports,bus);
    s.r=sample.registers;
    if(sample.status){s.status=LMN_KEYBOARD_CHILD_STOP;s.child_status=sample.status;return result(&s);}
    if(s.r.cs!=s.entry_cs||s.r.ip!=resume){s.status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return result(&s);}
    write16(&s,s.r.ds,SEG09A9_InputAxisBaselineX25A2,s.r.bx,s.r.flags);
#if KEYBOARD_INPUT_MUTATION == 13
    write16(&s,s.r.ds,SEG09A9_InputAxisBaselineY25A4,s.r.bx,s.r.flags);
#else
    write16(&s,s.r.ds,SEG09A9_InputAxisBaselineY25A4,s.r.cx,s.r.flags);
#endif
    s.r.si=SEG09A9_ControllerScaleText4EA9;
    if(!menu_text(&s,CS_ControllerMenuAfterScaleText4A9C)||!menu_swap(&s,CS_SelectInputScale4A9F))return result(&s);
    return lmn_select_input_scale(memory,&s.r,ports,bus);
}

LmnKeyboardResult lmn_select_input_mode(uint8_t *memory,const LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    KeyboardState s=state(memory,registers,ports,bus);
    for(;;) {
        LmnKeyboardResult character;
        push16(&s,CS_InputModeAfterWait4A31);
        s.r.ip=CS_WaitForDisplayStatusBit3Cycle;
        lmn_wait_display_status_bit3_cycle_adapter(memory,&s.r,ports,bus);
        if(!ports||!ports->in_byte){s.status=LMN_KEYBOARD_CHILD_STOP;s.child_status=1u;return result(&s);}
        if(s.r.cs!=s.entry_cs||s.r.ip!=CS_InputModeAfterWait4A31){s.status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return result(&s);}
        push16(&s,CS_InputModeAfterCharacter4A34);
        s.r.ip=CS_ReadKeyboardCharacter;
        character=lmn_read_keyboard_character_adapter(memory,&s.r,bus);s.r=character.registers;
        if(s.r.cs!=s.entry_cs||s.r.ip!=CS_InputModeAfterCharacter4A34){s.status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return result(&s);}
        cmp8(&s,read8(&s,s.r.ds,SEG09A9_MouseServicesDisabledByte),0xffu);
#if KEYBOARD_INPUT_MUTATION == 14
        if(read8(&s,s.r.ds,SEG09A9_MouseServicesDisabledByte)==0u) {
#else
        if(!(s.r.flags&ZF)) {
#endif
            cmp8(&s,(uint8_t)s.r.ax,0x31u);
            if(s.r.flags&ZF){write8(&s,s.r.ds,SEG09A9_InputModeByte25A6,0u);s.r.ip=CS_MenuRefresh4401;return result(&s);}
        }
        cmp8(&s,(uint8_t)s.r.ax,0x32u);
        if(s.r.flags&ZF)return lmn_select_input_controller(memory,&s.r,ports,bus);
        cmp8(&s,(uint8_t)s.r.ax,0x33u);
        if(s.r.flags&ZF){write8(&s,s.r.ds,SEG09A9_InputModeByte25A6,2u);s.r.ip=CS_MenuRefresh4401;return result(&s);}
        cmp8(&s,(uint8_t)s.r.ax,0x1bu);
        if(s.r.flags&ZF){
#if KEYBOARD_INPUT_MUTATION == 15
            write8(&s,s.r.ds,SEG09A9_InputModeByte25A6,2u);
#endif
            s.r.ip=CS_MenuRefresh4401;return result(&s);
        }
    }
}

LmnKeyboardResult lmn_show_input_selection(uint8_t *memory,const LmnRegs *registers,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus) {
    KeyboardState s=state(memory,registers,ports,bus);
    if(!input_screen_child(&s,CS_InputScreenAfterClear4A04,CS_ClearFullDrawingPage)||
       !input_screen_child(&s,CS_InputScreenAfterLayout4A07,CS_InitializeDisplayOrigins)||
       !input_screen_child(&s,CS_InputScreenAfterPalette1_4A0A,CS_TransitionPaletteToSlot1)||
       !input_screen_child(&s,CS_InputScreenAfterBackground4A0D,CS_DrawScreenBackground))return result(&s);
    s.r.si=SEG09A9_InputChoiceText4E3A;
    if(!menu_text(&s,CS_InputScreenAfterText4A14))return result(&s);
    cmp8(&s,read8(&s,s.r.ds,SEG09A9_MouseServicesDisabledByte),0xffu);
#if KEYBOARD_INPUT_MUTATION == 16
    if(read8(&s,s.r.ds,SEG09A9_MouseServicesDisabledByte)==0u) {
#else
    if(!(s.r.flags&ZF)) {
#endif
        s.r.si=SEG09A9_MouseChoiceText4E6E;
        if(!menu_text(&s,CS_InputScreenAfterMouseText4A22))return result(&s);
    }
    if(!input_screen_child(&s,CS_InputScreenAfterCopy4A25,CS_CopyDrawingPageToAlternate))return result(&s);
    push16(&s,CS_InputScreenAfterWait4A28);s.r.ip=CS_WaitForDisplayStatusBit3Cycle;
    lmn_wait_display_status_bit3_cycle_adapter(memory,&s.r,ports,bus);
    if(!ports||!ports->in_byte){s.status=LMN_KEYBOARD_CHILD_STOP;s.child_status=1u;return result(&s);}
    if(s.r.cs!=s.entry_cs||s.r.ip!=CS_InputScreenAfterWait4A28){s.status=LMN_KEYBOARD_CHANGED_CHILD_RETURN;return result(&s);}
    if(!menu_display(&s,CS_InputScreenAfterDisplay4A2B,LMN_DISPLAY_START_ENTRY_SAVED)||
       !input_screen_child(&s,CS_SelectInputMode4A2E,CS_TransitionPaletteToSlot2))return result(&s);
    return lmn_select_input_mode(memory,&s.r,ports,bus);
}

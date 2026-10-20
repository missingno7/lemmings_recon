#include "hardware_irq.h"
#include "game_foreground_internal.h"
#ifndef HARDWARE_IRQ_MUTATION
#define HARDWARE_IRQ_MUTATION 0
#endif
LmnHardwareIrqResult lmn_deliver_hardware_irq(uint8_t *memory,const LmnRegs *registers,
    uint16_t number,const LmnHardwareIrqServices *services) {
    LmnHardwareIrqResult out={*registers,0,0,0,0};LmnRegs *r=&out.registers;
    if(number!=8&&number!=9){out.status=LMN_HARDWARE_IRQ_UNSUPPORTED;return out;}
    if(HARDWARE_IRQ_MUTATION!=1&&!(r->flags&FG_IF)){out.status=LMN_HARDWARE_IRQ_DEFERRED;return out;}
    LmnForegroundState cpu={memory,services?services->bus:0,r};
    uint16_t cs=r->cs,ip=r->ip;
    fg_push(&cpu,r->flags);r->flags&=(uint16_t)~0x300u;
    fg_push(&cpu,cs);fg_push(&cpu,HARDWARE_IRQ_MUTATION==2?(uint16_t)(ip+1u):ip);
    r->cs=fg_word(&cpu,0,(uint16_t)(number*4u+2u));
    r->ip=fg_word(&cpu,0,(uint16_t)(number*4u));
    if(!services||r->cs!=services->code_segment||
       (number==8?(r->ip!=CS_GameTimerIrqHandler&&r->ip!=CS_MenuTimerIrqHandler):r->ip!=CS_KeyboardIrqHandler)) {
        out.status=LMN_HARDWARE_IRQ_UNBOUND_VECTOR;return out;
    }
    if(number==8) {
        LmnTimerTailResult handler=(r->ip==CS_MenuTimerIrqHandler&&HARDWARE_IRQ_MUTATION!=3)?
            lmn_menu_timer_adapter(memory,r,services->mouse,services->saved_int08,services->ports,services->bus):
            lmn_game_timer_adapter(memory,r,services->mouse,
            services->int60,services->int61,services->saved_int08,services->ports,services->bus);
        *r=handler.registers;out.handler_status=handler.status;
        out.child_status=handler.child_status;out.service_status=handler.service_status;
    } else {
        LmnKeyboardResult handler=lmn_keyboard_irq_adapter(memory,r,services->ports,services->bus);
        *r=handler.registers;out.handler_status=handler.status;
        out.child_status=handler.child_status;out.service_status=handler.service_status;
    }
    if(out.handler_status)out.status=LMN_HARDWARE_IRQ_HANDLER_STOP;
    else if(r->cs!=cs||r->ip!=ip)out.status=LMN_HARDWARE_IRQ_CHANGED_RETURN;
    return out;
}

#include "protection.h"
#include "timer_restore.h"
#include "vector_restore.h"
#include "video_restore.h"
#include "lemmings_sym.h"

#ifndef PROTECTION_MUTATION
#define PROTECTION_MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,OF=2048,ARITH=0x8D5};
typedef struct Protection {
    uint8_t *mem;
    const LmnProtectionServices *services;
    LmnProtectionResult out;
    LmnRasterBus bridge_bus;
    uint16_t vector_resume;
} Protection;
static const LmnRasterBus *bus(Protection *p){return p->services?p->services->bus:0;}
static uint32_t physical(uint16_t s,uint16_t o){return (((uint32_t)s<<4)+o)&0xFFFFFu;}
static uint8_t read_at(Protection *p,uint32_t a,uint16_t f){
    const LmnRasterBus *b=bus(p);a&=0xFFFFFu;
    return b&&b->read_byte?b->read_byte(b->context,p->mem,a,f):p->mem[a];
}
static void write_at(Protection *p,uint32_t a,uint8_t v,uint16_t f){
    const LmnRasterBus *b=bus(p);a&=0xFFFFFu;
    if(b&&b->write_byte)b->write_byte(b->context,p->mem,a,v,f);else p->mem[a]=v;
}
static uint16_t word(Protection *p,uint16_t s,uint16_t o){
    uint32_t a=physical(s,o);uint16_t f=p->out.registers.flags;
    uint8_t lo=read_at(p,a,f),hi=read_at(p,a+1u,f);return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void push(Protection *p,uint16_t v){
    LmnRegs *r=&p->out.registers;r->sp=(uint16_t)(r->sp-2u);uint32_t a=physical(r->ss,r->sp);
    write_at(p,a,(uint8_t)v,r->flags);write_at(p,a+1u,(uint8_t)(v>>8),r->flags);
}
static uint16_t pop(Protection *p){LmnRegs *r=&p->out.registers;uint16_t v=word(p,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);return v;}
static void byte(Protection *p,uint16_t off,uint8_t v){LmnRegs *r=&p->out.registers;write_at(p,physical(r->ds,off),v,r->flags);}
static void ah(LmnRegs *r,uint16_t v){r->ax=(uint16_t)((r->ax&255u)|(v<<8));}
static void al(LmnRegs *r,uint8_t v){r->ax=(uint16_t)((r->ax&0xFF00u)|v);}
static uint16_t szp(uint8_t v){unsigned n,parity=0;for(n=0;n<8;n++)parity^=(v>>n)&1u;return (uint16_t)((parity?0:PF)|(v?0:ZF)|(v&128u?SF:0));}
static void logic(LmnRegs *r,uint8_t v){r->flags=(uint16_t)((r->flags&~ARITH)|szp(v));}
static void cmp(LmnRegs *r,uint8_t a,uint8_t b){uint8_t v=(uint8_t)(a-b);r->flags=(uint16_t)((r->flags&~ARITH)|szp(v)|(a<b?CF:0)|((a^b^v)&AF)|(((a^b)&(a^v)&128u)?OF:0));}
static int interrupt(Protection *p,uint16_t n,uint16_t resume){
    const LmnProtectionServices *s=p->services;
    const LmnInterruptService *service=s?(n==0x21?s->dos:n==0x10?s->bios:n==0x1A?s->clock:s->mouse):0;
    LmnInterruptResult out=lmn_interrupt_service(p->mem,&p->out.registers,n,resume,service,bus(p));
    if(out.status){p->out.status=LMN_PROTECTION_INTERRUPT_STOP;p->out.child_status=out.status;p->out.service_status=out.service_status;return 0;}return 1;
}
static int returned(Protection *p,uint16_t cs,uint16_t resume){
    LmnRegs *r=&p->out.registers;if(p->out.status)return 0;r->ip=pop(p);
    if(r->cs==cs&&r->ip==resume)return 1;
    p->out.status=LMN_PROTECTION_CHANGED_RETURN;return 0;
}
static int writer(Protection *p){
    LmnRegs *r=&p->out.registers;r->dx=SEG09A9_ProtectionCounterFilename;ah(r,0x3C);r->cx=2;
    if(!interrupt(p,0x21,0xECD))return 0;
    /* Even create failure feeds its returned AX to write/close as a handle. */
    r->bx=r->ax;ah(r,0x40);r->cx=PROTECTION_MUTATION==2?1:0x100;r->dx=SEG09A9_ProtectionRunCounterByte;
    if(!interrupt(p,0x21,0xEDA))return 0;
    ah(r,0x3E);
    if(!interrupt(p,0x21,0xEDE))return 0;
    r->ip=0xEDE;return 1;
}
static int write_child(Protection *p,uint16_t resume){uint16_t cs=p->out.registers.cs;push(p,resume);p->out.registers.ip=0xEC2;return writer(p)&&returned(p,cs,resume);}
static int probe(Protection *p,uint16_t resume){
    LmnRegs *r=&p->out.registers;uint16_t cs=r->cs;push(p,resume);r->ip=0x63E;
    if(!p->services||!p->services->probe){p->out.status=LMN_PROTECTION_PROBE_SEAM;return 0;}
    uint16_t outcome=p->services->probe(p->services->context,p->mem,r,bus(p));
    if(outcome>LMN_MEDIA_FAIL){p->out.status=LMN_PROTECTION_PROBE_SEAM;p->out.service_status=outcome;return 0;}
    /* There are no transient vector/table/code writes in this abstraction.
       Providers own their complete restored end state, including stack residue. */
#if PROTECTION_MUTATION != 3
    uint16_t segment=(uint16_t)(cs+0x98u),off=(segment&0xFFFu)>0xFDFu?0x21C:0xC;
    for(unsigned n=0;n<512;n++)write_at(p,physical(segment,(uint16_t)(off+n)),0,r->flags);
#endif
    r->flags=(uint16_t)((r->flags&~1u)|(outcome==LMN_MEDIA_FAIL));
    return returned(p,cs,resume);
}

/* Existing restore cores use logical service packets. These bridges perform
   the original INT frames at the original resume PCs, retaining all live roles.
   After a stop, suppress the old core's post-callback reads and retain the exact
   stopped packet; no synthetic POP/second service can escape that boundary. */
#define FROM_STATE(r,s) do { (r).ax=(s).value;(r).bx=(s).base_value;(r).cx=(s).count;(r).dx=(s).argument; \
    (r).si=(s).source_cursor;(r).di=(s).output_cursor;(r).bp=(s).frame_cursor;(r).ds=(s).data_segment; \
    (r).es=(s).extra_segment;(r).ss=(s).stack_segment;(r).sp=(s).stack_offset;(r).flags=(s).flags; } while(0)
#define TO_STATE(s,r) do { (s).value=(r).ax;(s).base_value=(r).bx;(s).count=(r).cx;(s).argument=(r).dx; \
    (s).source_cursor=(r).si;(s).output_cursor=(r).di;(s).frame_cursor=(r).bp;(s).data_segment=(r).ds; \
    (s).extra_segment=(r).es;(s).stack_segment=(r).ss;(s).stack_offset=(r).sp;(s).flags=(r).flags; } while(0)
static uint8_t bridge_read(void *ctx,uint8_t *m,uint32_t a,uint16_t f){Protection *p=ctx;(void)m;return p->out.status?0:read_at(p,a,f);}
static void bridge_write(void *ctx,uint8_t *m,uint32_t a,uint8_t v,uint16_t f){Protection *p=ctx;(void)m;if(!p->out.status)write_at(p,a,v,f);}
static void bridge_out(void *ctx,uint16_t port,uint8_t v,uint16_t f){Protection *p=ctx;if(!p->out.status)p->services->ports->out_byte(p->services->ports->context,p->mem,port,v,f);}
static void clock_service(void *ctx,uint8_t *m,const LmnTimerRestoreState *in,LmnTimerRestoreState *out){
    Protection *p=ctx;(void)m;*out=*in;if(p->out.status)return;FROM_STATE(p->out.registers,*in);
    if(interrupt(p,0x1A,CS_TimerRestoreReturn))TO_STATE(*out,p->out.registers);
}
static void vector_service(void *ctx,uint8_t *m,const LmnVectorRestoreState *in,LmnVectorRestoreState *out){
    Protection *p=ctx;(void)m;*out=*in;if(p->out.status)return;FROM_STATE(p->out.registers,*in);
    if(interrupt(p,0x21,p->vector_resume))TO_STATE(*out,p->out.registers);
}
static void video_service(Protection *p,const LmnVideoRestoreState *in,LmnVideoRestoreState *out,uint16_t resume){
    *out=*in;if(p->out.status)return;FROM_STATE(p->out.registers,*in);if(interrupt(p,0x10,resume))TO_STATE(*out,p->out.registers);
}
static void mode_service(void *ctx,uint8_t *m,const LmnVideoRestoreState *in,LmnVideoRestoreState *out){(void)m;video_service(ctx,in,out,0xFFF);}
static void page_service(void *ctx,uint8_t *m,const LmnVideoRestoreState *in,LmnVideoRestoreState *out){(void)m;video_service(ctx,in,out,0x1006);}
static int restore(Protection *p,unsigned kind,uint16_t entry,uint16_t resume){
    LmnRegs *r=&p->out.registers;uint16_t cs=r->cs;push(p,resume);r->ip=entry;
    if(kind==0){
        LmnTimerRestoreState in;TO_STATE(in,*r);
        LmnTimerRestoreServices svc={p,p->services&&p->services->ports&&p->services->ports->out_byte?bridge_out:0,clock_service};
        LmnTimerRestoreResult out=lmn_restore_timer_state_core(p->mem,&in,&svc,&p->bridge_bus);
        if(p->out.status)return 0;
        FROM_STATE(*r,out.state);r->ip=out.continuation;
        if(out.status){p->out.status=LMN_PROTECTION_MISSING_PORT;return 0;}
    }else if(kind==1||kind==2){
        p->vector_resume=kind==1?0x1590:0xFB0;
        LmnVectorRestoreState in;TO_STATE(in,*r);LmnVectorRestoreServices svc={p,vector_service};
        LmnVectorRestoreResult out=kind==1?lmn_restore_keyboard_vector_core(p->mem,&in,&svc,&p->bridge_bus):lmn_restore_private_vector_core(p->mem,&in,&svc,&p->bridge_bus);
        if(p->out.status)return 0;
        FROM_STATE(*r,out.state);r->ip=out.continuation;
    }else{
        LmnVideoRestoreState in;TO_STATE(in,*r);LmnVideoRestoreServices svc={p,mode_service,page_service};
        LmnVideoRestoreResult out=lmn_restore_video_mode_page_core(p->mem,&in,&svc,&p->bridge_bus);
        if(p->out.status)return 0;
        FROM_STATE(*r,out.state);r->ip=out.continuation;
    }return returned(p,cs,resume);
}
static void failure(Protection *p){
    LmnRegs *r=&p->out.registers;
    if(!restore(p,0,CS_RestoreTimerState,0xEE2)||!restore(p,1,CS_RestoreKeyboardVector,0xEE5)||
       !restore(p,2,CS_RestorePrivateVector,0xEE8)||!restore(p,3,CS_RestoreVideoModeAndPage,0xEEB))return;
    cmp(r,read_at(p,physical(r->ds,SEG09A9_MouseServicesDisabledByte),r->flags),255);
    if(!(r->flags&ZF)){r->ax=12;r->cx=0;logic(r,0);if(!interrupt(p,0x33,0xEF9))return;}
#if PROTECTION_MUTATION != 4
    if(!restore(p,1,CS_RestoreKeyboardVector,0xEFC))return;
#endif
    r->dx=0x20D4;ah(r,9);if(!interrupt(p,0x21,0xF03))return;r->ax=0x4C00;
    if(interrupt(p,0x21,0xF08))p->out.status=LMN_PROTECTION_DOS_EXIT;
}
static void counter(Protection *p){
    LmnRegs *r=&p->out.registers;r->dx=SEG09A9_ProtectionCounterFilename;r->ax=0x3D00;
    if(!interrupt(p,0x21,0xE6F))return;
    if(!(r->flags&CF)){
        r->bx=r->ax;ah(r,0x3F);r->dx=SEG09A9_ProtectionRunCounterByte;r->cx=1;
        if(!interrupt(p,0x21,0xE7E))return;
        uint8_t old=read_at(p,physical(r->ds,SEG09A9_ProtectionRunCounterByte),r->flags),v=(uint8_t)(old+1u);
        /* INC AL preserves CF, then CMP defines all arithmetic flags. */
        al(r,v);cmp(r,v,PROTECTION_MUTATION==1?9:10);if(!(r->flags&CF)){al(r,0);logic(r,0);}
        byte(p,SEG09A9_ProtectionRunCounterByte,(uint8_t)r->ax);push(p,r->ax);ah(r,0x3E);
        if(!interrupt(p,0x21,0xE91)||!write_child(p,0xE94))return;
        r->ax=pop(p);logic(r,(uint8_t)r->ax);
        if((uint8_t)r->ax){r->ip=0xEA9;return;}
        if(!probe(p,0xE9C))return;
        if(!(r->flags&CF)){r->ip=0xEA9;return;}
        byte(p,SEG09A9_ProtectionRunCounterByte,9);if(!write_child(p,0xEA6))return;
    }else{
        al(r,0);logic(r,0);byte(p,SEG09A9_ProtectionRunCounterByte,0);
        if(!write_child(p,0xEB2)||!probe(p,0xEB5))return;
        if(!(r->flags&CF)){r->ip=0xEA9;return;}
        byte(p,SEG09A9_ProtectionRunCounterByte,9);if(!write_child(p,0xEBF))return;
    }failure(p);
}
LmnProtectionResult lmn_protection_core(uint8_t *memory,const LmnRegs *registers,enum LmnProtectionEntry entry,const LmnProtectionServices *services){
    Protection p={memory,services,{*registers,0,0,0},{0},0};p.bridge_bus=(LmnRasterBus){&p,bridge_read,bridge_write,0};
    LmnRegs *r=&p.out.registers;
    if(entry==LMN_PROTECTION_WRITE)writer(&p);
    else if(entry==LMN_PROTECTION_FAILURE)failure(&p);
    else if(entry==LMN_PROTECTION_COUNTER)counter(&p);
    else{
        al(r,read_at(&p,physical(r->ds,SEG09A9_StartupFatIdByte1FDE),r->flags));cmp(r,(uint8_t)r->ax,0xF8);
        if(r->flags&ZF)counter(&p);
        else if(probe(&p,0x638)){if(r->flags&CF)failure(&p);else r->ip=0x63D;}
    }return p.out;
}
LmnProtectionResult lmn_protection_adapter(uint8_t *memory,const LmnRegs *registers,enum LmnProtectionEntry entry,const LmnProtectionServices *services){
    Protection p={memory,services,lmn_protection_core(memory,registers,entry,services),{0},0};
    if(!p.out.status)p.out.registers.ip=pop(&p);
    return p.out;
}

#include "sound_driver_init.h"
#include "lemmings_sym.h"

#ifndef MUTATION
#define MUTATION 0
#endif

/* Mutation IDs 101+ leave every existing child's numeric mutations inactive. */
enum { CF=1, PF=4, AF=16, ZF=64, SF=128, OF=2048, ARITH=0x8d5 };

static uint32_t physical(uint16_t segment,uint16_t offset) {
    return (((uint32_t)segment<<4)+offset)&0xfffffu;
}
static uint8_t read8(uint8_t *m,const LmnRasterBus *b,uint32_t p,uint16_t f) {
    p&=0xfffffu;
    return b&&b->read_byte ? b->read_byte(b->context,m,p,f):m[p];
}
static void write8(uint8_t *m,const LmnRasterBus *b,uint32_t p,uint8_t v,uint16_t f) {
    p&=0xfffffu;
    if(b&&b->write_byte)b->write_byte(b->context,m,p,v,f);else m[p]=v;
}
static uint16_t word(uint8_t *m,const LmnRasterBus *b,uint16_t s,uint16_t o,uint16_t f) {
    uint32_t p=physical(s,o);
    uint8_t lo=read8(m,b,p,f),hi=read8(m,b,p+1u,f);
    return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void push(uint8_t *m,LmnRegs *r,const LmnRasterBus *b,uint16_t v) {
    uint32_t p;r->sp=(uint16_t)(r->sp-2u);p=physical(r->ss,r->sp);
    write8(m,b,p,(uint8_t)v,r->flags);write8(m,b,p+1u,(uint8_t)(v>>8),r->flags);
}
static uint16_t pop(uint8_t *m,LmnRegs *r,const LmnRasterBus *b) {
    uint16_t v=word(m,b,r->ss,r->sp,r->flags);r->sp=(uint16_t)(r->sp+2u);return v;
}
static void store(uint8_t *m,LmnRegs *r,const LmnRasterBus *b,uint16_t o,uint8_t v) {
    write8(m,b,physical(r->ds,o),v,r->flags);
}
static uint16_t szp(uint16_t value,unsigned bits) {
    unsigned i,parity=0;uint16_t f=0,mask=bits==8?255u:65535u;
    value&=mask;
    for(i=0;i<8;++i)parity^=(value>>i)&1u;
    if(!parity)f|=PF;
    if(!value)f|=ZF;
    if(value&(bits==8?128u:32768u))f|=SF;
    return f;
}
static void logic(LmnRegs *r,uint16_t v,unsigned bits) {
    r->flags=(uint16_t)((r->flags&~ARITH)|szp(v,bits));
}
static void cmp_ff(LmnRegs *r,uint8_t value) {
    uint8_t out=(uint8_t)(value-255u);
    r->flags=(uint16_t)((r->flags&~ARITH)|szp(out,8)|
        (value<255u?CF:0)|(((value^255u^out)&16u)?AF:0)|
        (((value^255u)&(value^out)&128u)?OF:0));
}
static void ah(LmnRegs *r,uint16_t v) {r->ax=(uint16_t)((r->ax&255u)|(v<<8));}
static void al(LmnRegs *r,uint16_t v) {r->ax=(uint16_t)((r->ax&0xff00u)|v);}

static unsigned interrupt(uint8_t *m,LmnRegs *r,const LmnRasterBus *b,
    uint16_t number,uint16_t resume,const LmnInterruptService *service,
    LmnSoundDriverInitResult *out) {
    LmnInterruptResult child=lmn_interrupt_service(m,r,number,resume,service,b);
    out->service_status=child.service_status;
    out->status=child.status;
    return child.status;
}

static unsigned load_driver(uint8_t *m,LmnRegs *r,const LmnRasterBus *b,
    const LmnSoundDriverInitServices *s,uint16_t resume,LmnSoundDriverInitResult *out) {
    uint16_t cs=r->cs;
    push(m,r,b,resume);r->ip=CS_LoadDatResource;
    if(!s||!s->files||!s->files->open_readonly||!s->files->attributes||
       !s->files->retry_ui||!s->io||!s->io->query_size||!s->io->read) {
        out->status=LMN_SOUND_INIT_MISSING_DAT_SERVICE;return 1;
    }
    lmn_dat_load_adapter(m,r,s->files,s->io);
    if(r->ip==CS_DatFileErrorTransfer) {
        out->status=LMN_SOUND_INIT_DAT_FILE_ERROR;out->child_status=1;return 1;
    }
    if(r->ip==CS_DatFatalTransfer) {
        out->status=LMN_SOUND_INIT_DAT_DECODE_ERROR;out->child_status=2;return 1;
    }
    if(r->cs!=cs||r->ip!=resume) {
        out->status=LMN_SOUND_INIT_CHANGED_CHILD_RETURN;return 1;
    }
    return 0;
}

static unsigned probe_tandy(uint8_t *m,LmnRegs *r,const LmnRasterBus *b,
    const LmnSoundDriverInitServices *s,LmnSoundDriverInitResult *out) {
    uint16_t cs=r->cs;
    push(m,r,b,0x05b8);r->ip=CS_ProbeTandyVideoPage;
    ah(r,0x0f);
    if(interrupt(m,r,b,0x10,0x0610,s?s->bios:0,out))return 1;
    push(m,r,b,r->bx);r->bx=0;logic(r,0,16);r->ax=0x0580;
    if(interrupt(m,r,b,0x10,0x0618,s?s->bios:0,out))return 1;
    r->ax=pop(m,r,b);ah(r,5);r->ax=(uint16_t)((r->ax<<8)|(r->ax>>8));
    logic(r,r->bx,16);
    if(r->flags&ZF) {
        if(interrupt(m,r,b,0x10,0x0623,s?s->bios:0,out))return 1;
        al(r,0);logic(r,0,8);r->ip=0x0625;
    } else {
        if(interrupt(m,r,b,0x10,0x0628,s?s->bios:0,out))return 1;
        al(r,255);r->ip=0x062a;
    }
    r->ip=pop(m,r,b);
    if(r->cs!=cs||r->ip!=0x05b8) {
        out->status=LMN_SOUND_INIT_CHANGED_CHILD_RETURN;return 1;
    }
    return 0;
}

LmnSoundDriverInitResult lmn_initialize_sound_driver_core(uint8_t *m,LmnRegs *r,
    const LmnSoundDriverInitServices *s,const LmnRasterBus *b) {
    LmnSoundDriverInitResult out={0,0,0};
    uint8_t option=read8(m,b,physical(r->ds,SEG09A9_ExternalSoundDriverEnabled),r->flags);
    cmp_ff(r,option);
#if MUTATION == 101
    if(option==0)goto fallback;
#else
    if(r->flags&ZF)goto fallback;
#endif
    ah(r,0x48);r->bx=0x5ad8;
    if(interrupt(m,r,b,0x21,0x0560,s?s->dos:0,&out))return out;
    if(r->flags&CF)goto fallback;
    r->es=r->ax;ah(r,0x49);
    if(interrupt(m,r,b,0x21,0x056b,s?s->dos:0,&out))return out;
    ah(r,0x48);r->bx=0x0567;
    if(interrupt(m,r,b,0x21,0x0572,s?s->dos:0,&out))return out;
    /* The second allocation's carry is deliberately unchecked. */
#if MUTATION == 102
    if(r->flags&CF)goto fallback;
#endif
    push(m,r,b,r->ds);r->ds=r->ax;push(m,r,b,r->ax);
    r->ax=0x2561;r->dx=0;logic(r,0,16);
    if(interrupt(m,r,b,0x21,0x057d,s?s->dos:0,&out))return out;
    r->ax=pop(m,r,b);r->ds=pop(m,r,b);
    push(m,r,b,r->ax);push(m,r,b,r->ds);r->es=r->ax;r->cx=r->ax;
    r->di=0;logic(r,0,16);r->si=0;logic(r,0,16);r->dx=0x2573;
    if(load_driver(m,r,b,s,0x0590,&out))return out;
    r->ds=pop(m,r,b);
    store(m,r,b,SEG09A9_SoundOptionBits,1);store(m,r,b,SEG09A9_MenuSoundOptionIndex,1);
    ah(r,1);
    if(interrupt(m,r,b,0x61,0x059f,s?s->sound:0,&out))return out;
    logic(r,r->ax&255u,8);
#if MUTATION == 103
    r->ax=pop(m,r,b);logic(r,r->ax&255u,8);
#else
    r->ax=pop(m,r,b);
#endif
    if(!(r->flags&ZF)) {
        store(m,r,b,SEG09A9_ExternalSoundDriverEnabled,255);
        store(m,r,b,SEG09A9_SoundOptionBits,3);store(m,r,b,SEG09A9_MenuSoundOptionIndex,2);
        r->ip=0x05b3;return out;
    }
    push(m,r,b,r->ax);
    if(probe_tandy(m,r,b,s,&out))return out;
    logic(r,r->ax&255u,8);r->ax=pop(m,r,b);
    if(r->flags&ZF) {
        r->es=r->ax;ah(r,0x49);
        if(interrupt(m,r,b,0x21,0x05fc,s?s->dos:0,&out))return out;
        goto fallback;
    }
    push(m,r,b,r->ds);r->es=r->ax;r->cx=r->ax;
    r->di=0;logic(r,0,16);r->si=0;logic(r,0,16);r->dx=0x257d;
    if(load_driver(m,r,b,s,0x05cd,&out))return out;
    r->ds=pop(m,r,b);
    store(m,r,b,SEG09A9_ExternalSoundDriverEnabled,255);
    store(m,r,b,SEG09A9_SoundOptionBits,3);store(m,r,b,SEG09A9_MenuSoundOptionIndex,2);
    al(r,1);ah(r,3);
    if(interrupt(m,r,b,0x61,0x05e3,s?s->sound:0,&out))return out;
    ah(r,0);
    if(interrupt(m,r,b,0x61,0x05e7,s?s->sound:0,&out))return out;
    al(r,0);logic(r,0,8);ah(r,3);
#if MUTATION != 104
    if(interrupt(m,r,b,0x61,0x05ed,s?s->sound:0,&out))return out;
#endif
    ah(r,2);
    if(interrupt(m,r,b,0x61,0x05f1,s?s->sound:0,&out))return out;
    ah(r,0);
    if(interrupt(m,r,b,0x61,0x05f5,s?s->sound:0,&out))return out;
    r->ip=0x05f5;return out;

fallback:
    store(m,r,b,SEG09A9_ExternalSoundDriverEnabled,0);
    store(m,r,b,SEG09A9_SoundOptionBits,1);store(m,r,b,SEG09A9_MenuSoundOptionIndex,1);
    r->ip=0x060b;return out;
}

LmnSoundDriverInitResult lmn_initialize_sound_driver_adapter(uint8_t *m,LmnRegs *r,
    const LmnSoundDriverInitServices *s,const LmnRasterBus *b) {
    LmnSoundDriverInitResult out=lmn_initialize_sound_driver_core(m,r,s,b);
    if(!out.status)r->ip=pop(m,r,b);
    return out;
}

#include "game_prepare.h"
#include "status_initialize.h"
#include "drawing_layout.h"
#include "lemmings_sym.h"
#ifndef GAME_PREPARE_MUTATION
#define GAME_PREPARE_MUTATION 0
#endif
enum {CF=1,PF=4,AF=16,ZF=64,SF=128,DF=1024,OF=2048,ARITH=0x8D5};
typedef struct Prepare {
    uint8_t *memory;const LmnRasterBytePorts *ports;const LmnRasterBus *bus;
    LmnGamePrepareResult out;
} Prepare;
static uint32_t physical(uint16_t seg,uint16_t off){return (((uint32_t)seg<<4)+off)&0xFFFFFu;}
static uint8_t read_at(Prepare *s,uint32_t at){
    at&=0xFFFFFu;return s->bus&&s->bus->read_byte?s->bus->read_byte(s->bus->context,s->memory,at,s->out.registers.flags):s->memory[at];
}
static void write_at(Prepare *s,uint32_t at,uint8_t value){
    at&=0xFFFFFu;
    if(s->bus&&s->bus->write_byte)s->bus->write_byte(s->bus->context,s->memory,at,value,s->out.registers.flags);
    else s->memory[at]=value;
}
static uint8_t read8(Prepare *s,uint16_t seg,uint16_t off){return read_at(s,physical(seg,off));}
static void write8(Prepare *s,uint16_t seg,uint16_t off,uint8_t value){write_at(s,physical(seg,off),value);}
static uint16_t read16(Prepare *s,uint16_t seg,uint16_t off){
    uint32_t at=physical(seg,off);uint8_t lo=read_at(s,at),hi=read_at(s,at+1u);return (uint16_t)(lo|((uint16_t)hi<<8));
}
static void write16(Prepare *s,uint16_t seg,uint16_t off,uint16_t value){
    uint32_t at=physical(seg,off);write_at(s,at,(uint8_t)value);write_at(s,at+1u,(uint8_t)(value>>8));
}
static void push(Prepare *s,uint16_t value){LmnRegs *r=&s->out.registers;r->sp=(uint16_t)(r->sp-2u);write16(s,r->ss,r->sp,value);}
static uint16_t pop(Prepare *s){LmnRegs *r=&s->out.registers;uint16_t v=read16(s,r->ss,r->sp);r->sp=(uint16_t)(r->sp+2u);return v;}
static uint16_t szp(uint16_t v,int byte){
    unsigned parity=0;for(unsigned n=0;n<8;n++)parity^=(v>>n)&1u;
    return (uint16_t)((parity?0:PF)|(v?0:ZF)|(v&(byte?128u:0x8000u)?SF:0));
}
static uint16_t arithmetic(Prepare *s,uint16_t a,uint16_t b,int sub,int byte){
    uint16_t mask=byte?255u:65535u,sign=byte?128u:0x8000u,v=(uint16_t)((sub?a-b:a+b)&mask);
    s->out.registers.flags=(uint16_t)((s->out.registers.flags&~ARITH)|szp(v,byte)|
        ((sub?a<b:(uint32_t)a+b>mask)?CF:0)|((a^b^v)&AF)|(((sub?(a^b):~(a^b))&(a^v)&sign)?OF:0));return v;
}
static void logic(Prepare *s,uint16_t value,int byte){s->out.registers.flags=(uint16_t)((s->out.registers.flags&~ARITH)|szp(value,byte));}
static uint16_t incdec(Prepare *s,uint16_t value,int dec,int byte){
    uint16_t cf=s->out.registers.flags&CF;value=arithmetic(s,value,1,dec,byte);
    s->out.registers.flags=(uint16_t)((s->out.registers.flags&~CF)|cf);return value;
}
static void al(Prepare *s,uint8_t value){s->out.registers.ax=(uint16_t)((s->out.registers.ax&0xFF00u)|value);}
static int returned(Prepare *s,uint16_t cs,uint16_t resume){
    LmnRegs *r=&s->out.registers;if(s->out.status)return 0;r->ip=pop(s);
#if GAME_PREPARE_MUTATION == 5
    r->ip=resume;
#endif
    if(r->cs!=cs||r->ip!=resume){s->out.status=LMN_GAME_PREPARE_CHANGED_RETURN;return 0;}return 1;
}
static int word_out(Prepare *s,uint16_t pc){
    LmnRegs *r=&s->out.registers;
    if(!s->bus||!s->bus->out_word){r->ip=pc;s->out.status=LMN_GAME_PREPARE_MISSING_WORD_OUTPUT;return 0;}
    s->bus->out_word(s->bus->context,r->dx,r->ax,r->flags);return 1;
}
static void move_words(Prepare *s){
    LmnRegs *r=&s->out.registers;uint16_t step=(r->flags&DF)?0xFFFEu:2u;
#if GAME_PREPARE_MUTATION == 2
    step=2;
#endif
    while(r->cx){uint16_t v=read16(s,r->ds,r->si);write16(s,r->es,r->di,v);
        r->si=(uint16_t)(r->si+step);r->di=(uint16_t)(r->di+step);--r->cx;}
}
static void move_bytes(Prepare *s){
    LmnRegs *r=&s->out.registers;uint16_t step=(r->flags&DF)?0xFFFFu:1u;
    while(r->cx){uint8_t v=read8(s,r->ds,r->si);write8(s,r->es,r->di,v);
        r->si=(uint16_t)(r->si+step);r->di=(uint16_t)(r->di+step);--r->cx;}
}
static void store_bytes(Prepare *s){
    LmnRegs *r=&s->out.registers;uint16_t step=(r->flags&DF)?0xFFFFu:1u;
    while(r->cx){write8(s,r->es,r->di,(uint8_t)r->ax);r->di=(uint16_t)(r->di+step);--r->cx;}
}
static void scan_bytes(Prepare *s,int equal){
    LmnRegs *r=&s->out.registers;
    while(r->cx){
        uint8_t value=read8(s,r->es,r->di);(void)arithmetic(s,(uint8_t)r->ax,value,1,1);
        r->di=(uint16_t)(r->di+((r->flags&DF)?0xFFFFu:1u));--r->cx;
        if(((r->flags&ZF)!=0)!=equal)break;
    }
}
static void palette(Prepare *s,LmnPalettePortsEntry entry){
    LmnRegs *r=&s->out.registers;
    LmnPalettePortsState in={r->ax,r->bx,r->cx,r->dx,r->si,r->di,r->bp,r->ds,r->es,r->ss,r->sp,r->flags};
    LmnPalettePortsResult out=lmn_write_palette_ports_core(s->memory,r->cs,&in,entry,s->ports,s->bus);
    r->ax=out.state.value;r->bx=out.state.base_value;r->cx=out.state.count;r->dx=out.state.argument;
    r->si=out.state.source_cursor;r->di=out.state.output_cursor;r->bp=out.state.frame_cursor;
    r->ds=out.state.data_segment;r->es=out.state.extra_segment;r->ss=out.state.stack_segment;r->sp=out.state.stack_offset;
    r->flags=out.state.flags;r->ip=out.continuation;
    if(out.status){s->out.status=LMN_GAME_PREPARE_CHILD_STOP;s->out.child_status=(uint16_t)out.status;}
}
static void base_palette(Prepare *s){
    LmnRegs *r=&s->out.registers;(void)arithmetic(s,read16(s,r->ds,SEG09A9_PaletteDisplayModeWord),4,1,0);
    if(!(r->flags&ZF)){
        r->si=CS_PackedPalettePointerTable;r->si=read16(s,r->cs,(uint16_t)(r->si+2u));r->cx=16;
        palette(s,LMN_PALETTE_PORTS_ENTRY_ATTRIBUTE);return;
    }
    r->si=CS_RgbPalettePointerTable;r->si=read16(s,r->cs,(uint16_t)(r->si+2u));r->cx=8;
    uint16_t cs=r->cs;push(s,0x5317);palette(s,LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC);
    if(!returned(s,cs,0x5317))return;
#if GAME_PREPARE_MUTATION == 1
    r->cx=8;
#else
    r->cx=0x1008;
#endif
    palette(s,LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC);
}
static void fade_palette(Prepare *s){
    LmnRegs *r=&s->out.registers;(void)arithmetic(s,read16(s,r->ds,SEG09A9_PaletteDisplayModeWord),4,1,0);
    int rgb=(r->flags&ZF)!=0;push(s,r->ds);r->es=pop(s);
    r->si=rgb?CS_RgbPalettePointerTable:CS_PackedPalettePointerTable;
    r->di=read16(s,r->cs,(uint16_t)(r->si+12u));r->si=read16(s,r->cs,(uint16_t)(r->si+10u));
    if(rgb){r->ax=read16(s,r->ds,r->si);write16(s,r->ds,(uint16_t)(r->di+21u),r->ax);
        al(s,read8(s,r->ds,(uint16_t)(r->si+2u)));write8(s,r->ds,(uint16_t)(r->di+23u),(uint8_t)r->ax);
    }else{al(s,read8(s,r->ds,r->si));write8(s,r->ds,(uint16_t)(r->di+7u),(uint8_t)r->ax);}
    r->di=arithmetic(s,r->di,rgb?24u:8u,0,0);r->cx=rgb?12u:4u;move_words(s);
    (void)arithmetic(s,read8(s,r->ds,SEG09A9_ConfigurationOption200E),255,1,1);
    r->ip=(!rgb&&(r->flags&ZF))?0x53A0:0x53C9;
}
static void sound_id(Prepare *s){
    LmnRegs *r=&s->out.registers;(void)arithmetic(s,read8(s,r->ds,SEG09A9_ExternalSoundDriverEnabled),0,1,1);
    if(r->flags&ZF){r->ip=0x4865;return;}
    al(s,read8(s,r->ds,SEG09A9_LevelSpecialGraphicsSetByte));logic(s,(uint8_t)r->ax,1);
    if(!(r->flags&ZF)){
        al(s,(uint8_t)incdec(s,(uint8_t)r->ax,1,1));r->ax&=255u;logic(s,0,1);
        r->bx=CS_SpecialLevelSoundIds;r->bx=arithmetic(s,r->bx,r->ax,0,0);al(s,read8(s,r->cs,r->bx));
        write8(s,r->ds,SEG09A9_LevelSoundId,(uint8_t)r->ax);r->ip=0x4876;return;
    }
    (void)arithmetic(s,read8(s,r->ds,SEG09A9_LevelOutcomeSuccessByte),0,1,1);
    if(!(r->flags&ZF)){
        al(s,read8(s,r->ds,SEG09A9_LevelSoundCycleIndex));al(s,(uint8_t)incdec(s,(uint8_t)r->ax,0,1));
        (void)arithmetic(s,(uint8_t)r->ax,17,1,1);
#if GAME_PREPARE_MUTATION == 3
        if((uint8_t)r->ax>=17){al(s,0);logic(s,0,1);}
#else
        if(r->flags&ZF){al(s,0);logic(s,0,1);}
#endif
        write8(s,r->ds,SEG09A9_LevelSoundCycleIndex,(uint8_t)r->ax);
    }
    r->ax&=255u;logic(s,0,1);push(s,r->ax);r->bx=CS_LevelSoundSequenceIds;r->bx=arithmetic(s,r->bx,r->ax,0,0);
    al(s,read8(s,r->cs,r->bx));write8(s,r->ds,SEG09A9_LevelSoundId,(uint8_t)r->ax);r->ax=pop(s);r->ip=0x4865;
}
static void status_backdrop(Prepare *s){
    LmnRegs *r=&s->out.registers;r->bp=r->ds;r->di=read16(s,r->ds,SEG09A9_DrawingOrigin);
    r->di=arithmetic(s,r->di,0x2172,0,0);r->di=arithmetic(s,r->di,2,0,0);r->si=0xD320;
    r->dx=0xA000;r->es=r->dx;r->ds=r->dx;r->dx=0x3C4;r->ax=0x0F02;
    write16(s,r->ss,8,r->ax);if(!word_out(s,0x7921))return;
    r->dx=0x3CE;r->ax=0;logic(s,0,0);write16(s,r->ss,10,r->ax);if(!word_out(s,0x792B))return;
    r->ax=0x0F01;write16(s,r->ss,12,r->ax);if(!word_out(s,0x7933))return;
    r->ax=5;write16(s,r->ss,0,r->ax);if(!word_out(s,0x793B))return;
    r->ax=3;write16(s,r->ss,2,r->ax);if(!word_out(s,0x7943))return;
    r->ax=0xFF08;write16(s,r->ss,14,r->ax);if(!word_out(s,0x794B))return;
    al(s,0);logic(s,0,1);r->cx=13;store_bytes(s);r->di=arithmetic(s,r->di,31,0,0);
    r->ax=0x0105;write16(s,r->ss,0,r->ax);if(!word_out(s,0x795D))return;
    r->dx=19;
    do{r->cx=13;move_bytes(s);r->di=arithmetic(s,r->di,31,0,0);r->dx=incdec(s,r->dx,1,0);}while(r->dx);
    r->ds=r->bp;r->ip=0x796E;
}
static void dirty_rows(Prepare *s){
    LmnRegs *r=&s->out.registers;r->dx=0x3C4;r->ax=0x0F02;write16(s,r->ss,8,r->ax);if(!word_out(s,0x8107))return;
    r->dx=0x3CE;r->ax=0x0105;write16(s,r->ss,0,r->ax);if(!word_out(s,0x8112))return;
    push(s,r->ss);r->es=pop(s);r->di=read16(s,r->ds,SEG09A9_DrawingDirtyCellMapOffset);
    al(s,read8(s,r->es,r->di));logic(s,(uint8_t)r->ax,1);
    if(!(r->flags&ZF)){
        write8(s,r->es,r->di,0);r->bp=r->ds;r->di=read16(s,r->ds,SEG09A9_DrawingOrigin);
        r->di=arithmetic(s,r->di,0x2C2,0,0);r->si=0x4A40;r->ax=read16(s,r->ds,SEG09A9_LevelViewOriginBytes);
        r->si=arithmetic(s,r->si,r->ax,0,0);r->dx=0xA000;r->es=r->dx;r->ds=r->dx;r->dx=160;
        do{r->cx=44;move_bytes(s);
#if GAME_PREPARE_MUTATION == 7
            r->si=arithmetic(s,r->si,0xA3,0,0);
#else
            r->si=arithmetic(s,r->si,0xA4,0,0);
#endif
            r->dx=incdec(s,r->dx,1,0);
        }while(r->dx);
        r->ds=r->bp;r->ip=0x81CB;return;
    }
    push(s,r->ds);r->di=incdec(s,r->di,0,0);r->bp=read16(s,r->ds,SEG09A9_DrawingOrigin);
    r->bp=arithmetic(s,r->bp,0x2C2,0,0);r->si=0x4A40;r->ax=read16(s,r->ds,SEG09A9_LevelViewOriginBytes);
    r->si=arithmetic(s,r->si,r->ax,0,0);r->dx=0xA000;r->ds=r->dx;al(s,1);r->cx=20;
    do{
        push(s,r->cx);r->cx=40;
        for(;;){
            scan_bytes(s,0);
            if(!(r->flags&ZF))break;
            push(s,r->cx);scan_bytes(s,1);r->bx=pop(s);r->bx=incdec(s,r->bx,0,0);
            push(s,r->cx);push(s,r->di);push(s,r->si);push(s,r->bp);push(s,r->ax);push(s,r->es);
            r->di=r->bp;r->ax=0x28;r->ax=arithmetic(s,r->ax,r->bx,1,0);
            r->si=arithmetic(s,r->si,r->ax,0,0);r->di=arithmetic(s,r->di,r->ax,0,0);
            r->bx=arithmetic(s,r->bx,r->cx,1,0);
#if GAME_PREPARE_MUTATION == 6
            if(r->bx)--r->bx;
#endif
            r->cx=r->bx;r->dx=r->bx;r->dx=arithmetic(s,r->dx,0xFFD4,0,0);
            r->bx=arithmetic(s,r->bx,0xFF30,0,0);push(s,r->ds);r->es=pop(s);al(s,8);
            do{push(s,r->cx);move_bytes(s);r->cx=pop(s);
                r->si=arithmetic(s,r->si,r->bx,1,0);r->di=arithmetic(s,r->di,r->dx,1,0);
                al(s,(uint8_t)incdec(s,(uint8_t)r->ax,1,1));
            }while((uint8_t)r->ax);
            r->es=pop(s);r->ax=pop(s);r->bp=pop(s);r->si=pop(s);r->di=pop(s);r->cx=pop(s);
            if(!r->cx)break;
        }
        r->cx=pop(s);r->bp=arithmetic(s,r->bp,0x160,0,0);r->si=arithmetic(s,r->si,0x680,0,0);--r->cx;
    }while(r->cx);
    r->ds=pop(s);r->di=read16(s,r->ds,SEG09A9_DrawingDirtyCellMapOffset);r->di=incdec(s,r->di,0,0);
    r->cx=0x320;al(s,0);logic(s,0,1);
#if GAME_PREPARE_MUTATION != 4
    store_bytes(s);
#endif
    r->ip=0x815F;
}
static int checked_adapter_return(Prepare *s,uint16_t cs,uint16_t resume){
    if(s->out.registers.cs!=cs||s->out.registers.ip!=resume){s->out.status=LMN_GAME_PREPARE_CHANGED_RETURN;return 0;}return 1;
}
static void drawing_pages(Prepare *s){
    LmnRegs *r=&s->out.registers;uint16_t cs=r->cs;
    write16(s,r->ds,SEG09A9_DrawingOrigin,0);write16(s,r->ds,SEG09A9_AlternateDrawingOrigin,0x2520);
    write16(s,r->ds,SEG09A9_DrawingPageByteOffset,0x2C0);write16(s,r->ds,SEG09A9_DrawingDirtyCellMapOffset,0x42B2);
    write16(s,r->ds,SEG09A9_AlternateDrawingDirtyCellMapOffset,0x45D3);
    r->bx=read16(s,r->ds,SEG09A9_DrawingDirtyCellMapOffset);write8(s,r->ss,r->bx,255);
    r->bx=read16(s,r->ds,SEG09A9_AlternateDrawingDirtyCellMapOffset);write8(s,r->ss,r->bx,255);
    write8(s,r->ds,SEG09A9_DrawingDirtyCellsEnabledByte,255);
    push(s,0x8202);dirty_rows(s);if(!returned(s,cs,0x8202))return;
    r->ax=read16(s,r->ds,SEG09A9_AlternateDrawingOrigin);uint16_t old=read16(s,r->ds,SEG09A9_DrawingOrigin);
    write16(s,r->ds,SEG09A9_DrawingOrigin,r->ax);r->ax=old;write16(s,r->ds,SEG09A9_AlternateDrawingOrigin,r->ax);
    r->ax=read16(s,r->ds,SEG09A9_AlternateDrawingDirtyCellMapOffset);
#if GAME_PREPARE_MUTATION == 8
    r->ax=0x45D3;
#endif
    old=read16(s,r->ds,SEG09A9_DrawingDirtyCellMapOffset);
    write16(s,r->ds,SEG09A9_DrawingDirtyCellMapOffset,r->ax);r->ax=old;write16(s,r->ds,SEG09A9_AlternateDrawingDirtyCellMapOffset,r->ax);
    push(s,0x8219);uint16_t status=lmn_initialize_status_display_adapter(s->memory,r,s->bus);
    if(status){s->out.status=LMN_GAME_PREPARE_CHILD_STOP;s->out.child_status=status;return;}
    if(!checked_adapter_return(s,cs,0x8219))return;
    push(s,0x821C);dirty_rows(s);if(!returned(s,cs,0x821C))return;
    r->ax=0x160;r->bx=0xA0;r->dx=read16(s,r->ds,SEG09A9_DrawingOrigin);
    push(s,r->cs);push(s,0x822B);lmn_set_drawing_layout_adapter(s->memory,r,s->bus);
    if(!checked_adapter_return(s,cs,0x822B))return;
    write16(s,r->ds,SEG09A9_FixedPatternVgaOffset0008,0xD2C0);write16(s,r->ds,SEG09A9_FixedPatternVgaOffset000A,0xD2F0);r->ip=0x8237;
}
LmnGamePrepareResult lmn_game_prepare_core(uint8_t *memory,const LmnRegs *registers,LmnGamePrepareEntry entry,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus){
    Prepare s={memory,ports,bus,{*registers,0,0}};
    switch(entry){case LMN_GAME_PREPARE_BASE_PALETTE:base_palette(&s);break;case LMN_GAME_PREPARE_FADE_PALETTE:fade_palette(&s);break;
        case LMN_GAME_PREPARE_SOUND:sound_id(&s);break;case LMN_GAME_PREPARE_STATUS_BACKDROP:status_backdrop(&s);break;
        case LMN_GAME_PREPARE_DIRTY_ROWS:dirty_rows(&s);break;case LMN_GAME_PREPARE_DRAWING_PAGES:drawing_pages(&s);break;}
    return s.out;
}
LmnGamePrepareResult lmn_game_prepare_adapter(uint8_t *memory,const LmnRegs *registers,LmnGamePrepareEntry entry,
    const LmnRasterBytePorts *ports,const LmnRasterBus *bus){
    LmnGamePrepareResult out=lmn_game_prepare_core(memory,registers,entry,ports,bus);
    Prepare s={memory,ports,bus,out};if(!out.status)s.out.registers.ip=pop(&s);return s.out;
}

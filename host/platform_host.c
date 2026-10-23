#include "platform_host.h"
#include "pklite_unpack.h"
#include "lemmings_sym.h"
#include "special_setup.h"
#include "resource_retry.h"
#include "main_resources.h"
#include "adlib_engine.h"
#include "opl3.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { MASK=0xfffff, EVENT_CAP=8192, FILE_CAP=64, ARENA_CAP=32 };
typedef struct HostFile { FILE *file; uint16_t handle; const uint8_t *overlay;size_t size,position; } HostFile;
typedef struct HostArena { uint16_t segment,paragraphs; } HostArena;
struct LmnHost {
    uint8_t memory[LMN_HOST_MEMORY];
    LmnHostVga vga;
    char assets[1024],error[192];
    uint64_t now,next_irq,pit_epoch,frames,irqs,sound_requests,polls,accesses;
    uint64_t max_polls,max_accesses,max_frames,status_reads;
    uint32_t pit_reload,pit_latch;
    uint16_t pit_temp,mouse_x,mouse_y,mouse_buttons,load,ds,next_handle;
    uint8_t pit_write,pit_read,pit_latched,pit_control,port61,scan,automatic,pending08;
    uint8_t pic_mask,pic_in_service,mouse_visible;
    uint16_t mouse_min_x,mouse_max_x,mouse_min_y,mouse_max_y;
    uint16_t mouse_mickeys_x,mouse_mickeys_y,mouse_callback_mask,mouse_callback_cs,mouse_callback_ip;
    enum LmnHostMediaPolicy media_policy;
    int dos_exited;
    uint32_t bios_clock;
    LmnHostEvent events[EVENT_CAP]; size_t event_count,event_cursor;
    HostFile files[FILE_CAP]; uint16_t current_handle;
    HostArena arenas[ARENA_CAP]; size_t arena_count;
    char overlay_name[65];const uint8_t *overlay;size_t overlay_size;
    void *hook_context; LmnHostPollHook poll_hook; LmnHostObserveHook observe_hook;
    LmnRasterBus bus; LmnRasterBytePorts ports; LmnForegroundPoll poll;
    LmnVideoRestoreServices video; LmnInterruptService bios,dos,mouse,clock,mute60,mute61,chain;
    LmnInputPollService mouse_poll;
    LmnTimerRestoreServices timer_restore;LmnVectorRestoreServices vectors;
    LmnFatalCleanupServices cleanup;LmnFileErrorServices file_error;
    LmnHardwareIrqServices irq;
    LmnDatFileServices files_service; LmnDatIo io; LmnRawResourceServices raw;
    LmnResourceSelectionServices selection; LmnResourceSelectionFullServices full;
    LmnDatLoadSegments segments; LmnSpecialSetupServices special;
    LmnBriefingServices briefing; LmnLevelStartServices start;
    LmnVideoProbeServices probe; LmnLevelInitializeServices level;
    LmnGameInitializeServices initialize; LmnGameFrameServices frame;
    LmnGameSessionServices session; LmnLevelResultServices result; LmnGameLoopServices loop;
    LmnSoundDriverInitServices sound_init;
    LmnProtectionServices protection;
    LmnStartupServices startup;
    /* AdLib platform: the game-installed INT61 vector is served by the C
       driver engine over the loaded driver bytes; its OPL ports drive the
       Nuked OPL3 core (OPL2-compatible mode) and a minimal status/timer model. */
    LmnPcSpeakerBinding pc_binding; LmnSoundDriverBinding sound_binding;
    LmnOplPorts opl_ports; opl3_chip opl;
    uint8_t opl_address,opl_status,opl_control;
    FILE *audio; uint64_t audio_frames; int audio_failed;
};
static uint32_t phys(uint16_t seg,uint16_t off) { return (((uint32_t)seg<<4)+off)&MASK; }
static uint16_t word(const uint8_t *m,uint16_t seg,uint16_t off) {
    uint32_t p=phys(seg,off); return (uint16_t)(m[p]|((uint16_t)m[(p+1)&MASK]<<8));
}
static void putword(uint8_t *m,uint16_t seg,uint16_t off,uint16_t value) {
    uint32_t p=phys(seg,off);m[p]=(uint8_t)value;m[(p+1)&MASK]=(uint8_t)(value>>8);
}
static void fail(LmnHost *h,const char *message) {
    if(!h->error[0]) snprintf(h->error,sizeof(h->error),"%s",message);
}
static int access_ok(LmnHost *h) {
    if(++h->accesses>h->max_accesses) {
        /* A failed IN callback cannot unwind a native busy loop. Hard failure
           is deliberate, and is never a differential mutation witness. */
        fputs("host: platform access budget exhausted\n",stderr);exit(86);
    }
    return !h->error[0];
}
static uint8_t rotate(uint8_t v,unsigned r) { return r?(uint8_t)((v>>r)|(v<<(8-r))):v; }
static uint8_t logic(uint8_t source,uint8_t latch,unsigned op) {
    switch(op) {case 1:return source&latch;case 2:return source|latch;case 3:return source^latch;default:return source;}
}
static int aperture(LmnHost *h,uint32_t p) {
    if(p<0xa0000 || p>=0xb0000) return 0;
    if((h->vga.seq[4]&12)!=4 || (h->vga.gc[6]&13)!=5)
        fail(h,"unsupported VGA aperture (requires unchained A000 64KiB)");
    return 1;
}
static uint8_t bus_read(void *ctx,uint8_t *m,uint32_t p,uint16_t flags) {
    LmnHost *h=ctx; LmnHostVga *v=&h->vga; unsigned i;uint8_t value=255;
    (void)flags;p&=MASK;if(!access_ok(h))return 0;
    if(!aperture(h,p))return m[p];
    for(i=0;i<4;i++)v->latches[i]=v->planes[i][p-0xa0000];
    if(v->gc[5]&8) {
        for(i=0;i<4;i++)if(v->gc[7]&(1u<<i))value&=(v->gc[2]&(1u<<i))?v->latches[i]:(uint8_t)~v->latches[i];
    } else value=v->latches[v->gc[4]&3];
    m[p]=value;return value;
}
static void bus_write(void *ctx,uint8_t *m,uint32_t p,uint8_t value,uint16_t flags) {
    LmnHost *h=ctx;LmnHostVga *v=&h->vga;unsigned i,mode;uint8_t source,bits,rot;
    (void)flags;p&=MASK;if(!access_ok(h))return;
    if(aperture(h,p)) {
        mode=v->gc[5]&3;rot=rotate(value,v->gc[3]&7);bits=v->gc[8];
        if(mode==3)bits&=rot;
        for(i=0;i<4;i++)if(v->seq[2]&(1u<<i)) {
            if(mode==1) {v->planes[i][p-0xa0000]=v->latches[i];continue;}
            if(mode==2)source=(value&(1u<<i))?255:0;
            else if(mode==3 || (v->gc[1]&(1u<<i)))source=(v->gc[0]&(1u<<i))?255:0;
            else source=rot;
            source=logic(source,v->latches[i],(v->gc[3]>>3)&3);
            v->planes[i][p-0xa0000]=(uint8_t)((source&bits)|(v->latches[i]&(uint8_t)~bits));
        }
    }
    m[p]=value;
}
/* Mode 0Dh has byte-addressed planar scanout, 40 bytes/line; mode10h
   uses 80. High bit on BIOS mode requests preserves display storage. */
static void video_mode(LmnHost *h,uint8_t request) {
    LmnHostVga *v=&h->vga;unsigned i;uint8_t mode=request&127;
    if(mode!=0x0d && mode!=0x10 && mode!=3) {fail(h,"unsupported BIOS video mode");return;}
    v->mode=mode;
    if(!(request&128)) {memset(v->planes,0,sizeof(v->planes));memset(h->memory+0xa0000,0,65536);}
    memset(v->seq,0,sizeof(v->seq));memset(v->gc,0,sizeof(v->gc));
    v->seq[2]=15;v->seq[4]=6;v->gc[6]=5;v->gc[7]=15;v->gc[8]=255;
    memset(v->crtc,0,sizeof(v->crtc));v->crtc[0x13]=(mode==0x10)?40:20;v->crtc[0x17]=0xe3;
    for(i=0;i<16;i++)v->attr[i]=(uint8_t)(mode==0x0d?(i>=8?i+8:i):(i>=8?i+48:i==6?20:i));
    v->attr[0x10]=1;v->attr[0x14]=0;v->pel_mask=255;
}
static void rearm_timer(LmnHost *h) {
    if(h->vga.mode==0x0d && h->memory[phys(h->ds,0x200e)]!=255) {
        /* The measured reload expires BEFORE retrace. The game handler then
           waits through retrace and re-arms from its end. Scheduling a whole
           frame after that end would incorrectly halve the IRQ rate. */
        uint64_t deadline=(h->now/LMN_HOST_DISPLAY_TICKS)*LMN_HOST_DISPLAY_TICKS+LMN_HOST_DISPLAY_TICKS*9/10;
        if(deadline<=h->now)deadline+=LMN_HOST_DISPLAY_TICKS;
        h->next_irq=deadline;
    }else h->next_irq=h->now+h->pit_reload;
}
static void out8(void *ctx,uint8_t *m,uint16_t p,uint8_t value,uint16_t flags) {
    LmnHost *h=ctx;LmnHostVga *v=&h->vga;(void)m;(void)flags;
    if(!access_ok(h))return;
    switch(p) {
    case 0x3c4:v->si=value;break;
    case 0x3c5:if(v->si<5)v->seq[v->si]=value;else fail(h,"unsupported sequencer register");break;
    case 0x3ce:v->gi=value;break;
    case 0x3cf:if(v->gi<9)v->gc[v->gi]=value;else fail(h,"unsupported GC register");break;
    case 0x3b4:case 0x3d4:v->ci=value;break;
    case 0x3b5:case 0x3d5:if(v->ci<32)v->crtc[v->ci]=value;else fail(h,"unsupported CRTC register");break;
    case 0x3c0:
        if(!v->attr_data)v->ai=value&31;else v->attr[v->ai]=value;
        v->attr_data^=1;break;
    case 0x3c6:v->pel_mask=value;break;
    case 0x3c7:v->dac_read=value;v->dac_read_component=0;break;
    case 0x3c8:v->dac_write=value;v->dac_component=0;break;
    case 0x3c9:
        v->dac[v->dac_write][v->dac_component++]=value&63;
        if(v->dac_component==3){v->dac_component=0;v->dac_write++;}break;
    case 0x43:
        if((value&0xc0)!=0 || (value&1)) {fail(h,"unsupported PIT channel/BCD");break;}
        if(!(value&0x30)) {h->pit_latch=h->pit_reload-(uint32_t)((h->now-h->pit_epoch)%h->pit_reload);h->pit_latched=1;h->pit_read=0;}
        else {h->pit_control=value;h->pit_write=0;}break;
    case 0x40:
        if((h->pit_control&0x30)==0x10)h->pit_temp=value;
        else if((h->pit_control&0x30)==0x20)h->pit_temp=(uint16_t)(value<<8);
        else if(!h->pit_write){h->pit_temp=value;h->pit_write=1;break;}
        else {h->pit_temp|=(uint16_t)(value<<8);h->pit_write=0;}
        h->pit_reload=h->pit_temp?h->pit_temp:65536;h->pit_epoch=h->now;rearm_timer(h);break;
    case 0x20:if(value==0x20)h->pic_in_service=0;else fail(h,"unsupported PIC command");break;
    case 0x21:h->pic_mask=value;break;
    case 0x61:h->port61=value;break;
    case 0x64:if(value!=0xad && value!=0xae)fail(h,"unsupported keyboard controller command");break;
    case 0x60:break; /* controller write acknowledgement, not a scan dequeue */
    default:fail(h,"unbound output port");break;
    }
}
static uint8_t in8(void *ctx,uint8_t *m,uint16_t p,uint16_t flags) {
    LmnHost *h=ctx;LmnHostVga *v=&h->vga;uint32_t count;uint8_t value=0;(void)m;(void)flags;
    if(!access_ok(h))return 0;
    switch(p) {
    case 0x3da:case 0x3ba:
        /* Display enable is a horizontal signal, independent of vertical
           retrace. Coupling bit0 to bit3 would turn every raster row wait
           into a frame wait and lose input between briefing polls. Fixed
           54-PIT-cycle lines and a 10% vertical blank define this machine. */
        count=(uint32_t)(h->now%LMN_HOST_DISPLAY_TICKS);
        value=(uint8_t)((h->now%54>=40?1:0)|(count>=LMN_HOST_DISPLAY_TICKS*9/10?8:0));
        h->now+=8;h->status_reads++;v->attr_data=0;return value;
    case 0x3c4:return v->si;
    case 0x3c5:return v->si<5?v->seq[v->si]:0;
    case 0x3ce:return v->gi;
    case 0x3cf:return v->gi<9?v->gc[v->gi]:0;
    case 0x3b5:case 0x3d5:return v->ci<32?v->crtc[v->ci]:0;
    case 0x3c1:return v->attr[v->ai];
    case 0x3c6:return v->pel_mask;
    case 0x3c7:return 3;
    case 0x3c8:return v->dac_write;
    case 0x3c9:
        value=v->dac[v->dac_read][v->dac_read_component++];
        if(v->dac_read_component==3){v->dac_read_component=0;v->dac_read++;}return value;
    case 0x40:
        count=h->pit_latched?h->pit_latch:h->pit_reload-(uint32_t)((h->now-h->pit_epoch)%h->pit_reload);
        value=(uint8_t)(count>>(h->pit_read*8));h->pit_read^=1;
        if(!h->pit_read)h->pit_latched=0;
        return value;
    case 0x60:return h->scan;
    case 0x61:return h->port61;
    case 0x64:return 0; /* synchronous controller: input buffer empty */
    case 0x21:return h->pic_mask;
    default:fail(h,"unbound input port");return 0;
    }
}
static void out16(void *ctx,uint16_t p,uint16_t value,uint16_t flags) {
    LmnHost *h=ctx;h->vga.word_outputs++;
    out8(ctx,h->memory,p,(uint8_t)value,flags);out8(ctx,h->memory,(uint16_t)(p+1),(uint8_t)(value>>8),flags);
}
uint8_t lmn_host_read(LmnHost *h,uint32_t p){return bus_read(h,h->memory,p,0);}
void lmn_host_write(LmnHost *h,uint32_t p,uint8_t v){bus_write(h,h->memory,p,v,0);}
void lmn_host_out(LmnHost *h,uint16_t p,uint16_t v,unsigned width){if(width==2)out16(h,p,v,0);else if(width==1)out8(h,h->memory,p,(uint8_t)v,0);else fail(h,"invalid port width");}
uint8_t lmn_host_in(LmnHost *h,uint16_t p){return in8(h,h->memory,p,0);}

/* DOS path names are single components. No write/create service exists. */
static int filename(LmnHost *h,const uint8_t *m,uint16_t seg,uint16_t off,char *path) {
    char name[65];size_t i;
    for(i=0;i<64;i++) {
        unsigned c=m[phys(seg,(uint16_t)(off+i))];if(!c)break;
        if(!(isalnum(c)||c=='.'||c=='_'||c=='-'))return 0;
        name[i]=(char)tolower(c);
    }
    if(!i || i==64)return 0;
    name[i]=0;
    if(strstr(name,".."))return 0;
    return snprintf(path,1152,"%s/%s",h->assets,name)<1152;
}
static HostFile *file_handle(LmnHost *h,uint16_t handle) {
    size_t i;for(i=0;i<FILE_CAP;i++)if((h->files[i].file || h->files[i].overlay) && h->files[i].handle==handle)return &h->files[i];return NULL;
}
static uint16_t dosflags(uint16_t flags,int failed){return (uint16_t)((flags&~1u)|(failed?1:0));}
static void file_service(void *ctx,uint8_t *m,uint16_t seg,uint16_t off,uint16_t flags,LmnDatFileServiceResult *out,int attributes) {
    LmnHost *h=ctx;char path[1152];FILE *fp=NULL;size_t i;uint16_t value=2;
    if(!access_ok(h)) {out->value=5;out->flags=dosflags(flags,1);out->count=0;return;}
    if(filename(h,m,seg,off,path))fp=fopen(path,"rb");
    if(fp) {
        if(attributes){value=0;fclose(fp);}
        else {
            for(i=0;i<FILE_CAP && (h->files[i].file || h->files[i].overlay);i++){}
            if(i==FILE_CAP){fclose(fp);fp=NULL;value=4;}
            else {
                const char *name=strrchr(path,'/');value=h->next_handle++;
                h->files[i]=(HostFile){fp,value,NULL,0,0};h->current_handle=value;
                if(h->overlay && name && !strcmp(name+1,h->overlay_name)){
                    h->files[i].overlay=h->overlay;h->files[i].size=h->overlay_size;
                }
            }
        }
    }
    *out=(LmnDatFileServiceResult){value,attributes?0x20:0,dosflags(flags,!fp)};
}
static void opened(void *c,uint8_t *m,uint16_t s,uint16_t o,uint16_t f,LmnDatFileServiceResult *r){file_service(c,m,s,o,f,r,0);}
static void attributes(void *c,uint8_t *m,uint16_t s,uint16_t o,uint16_t f,LmnDatFileServiceResult *r){file_service(c,m,s,o,f,r,1);}
static void raw_open(void *c,uint8_t *m,uint16_t s,uint16_t o,uint16_t f,LmnDatDosResult *r){LmnDatFileServiceResult x;opened(c,m,s,o,f,&x);*r=(LmnDatDosResult){x.value,x.flags};}
static void read_file(void *ctx,uint8_t *m,uint16_t handle,uint16_t seg,uint16_t off,uint16_t n,uint16_t f,LmnDatDosResult *out) {
    LmnHost *h=ctx;HostFile *file=file_handle(h,handle);uint16_t i=0;int c=EOF;
    if(file && access_ok(h))for(i=0;i<n;i++){
        if(file->overlay)c=file->position<file->size?file->overlay[file->position++]:EOF;
        else c=fgetc(file->file);
        if(c==EOF)break;
        m[phys(seg,(uint16_t)(off+i))]=(uint8_t)c;
    }
    *out=(LmnDatDosResult){file?i:6,dosflags(f,!file || (c==EOF && file && ferror(file->file)))};
}
static void close_file(void *ctx,uint8_t *m,uint16_t handle,uint16_t value,uint16_t f,LmnDatDosResult *out) {
    LmnHost *h=ctx;HostFile *file=file_handle(h,handle);int bad=!file;(void)m;(void)value;
    if(file){bad=fclose(file->file)!=0;file->file=NULL;file->overlay=NULL;}
    *out=(LmnDatDosResult){bad?6:0,dosflags(f,bad)};
}
static void query_file(void *ctx,uint8_t *m,uint16_t seg,uint16_t off,uint16_t f,LmnDatDosResult *out) {
    LmnHost *h=ctx;HostFile *file=file_handle(h,h->current_handle);long size=-1,pos;
    if(file && file->overlay)size=(long)file->size;
    else if(file){pos=ftell(file->file);if(!fseek(file->file,0,SEEK_END)){size=ftell(file->file);if(fseek(file->file,pos,SEEK_SET))size=-1;}}
    if(size>=0){putword(m,seg,(uint16_t)(off+33),(uint16_t)size);putword(m,seg,(uint16_t)(off+35),(uint16_t)((unsigned long)size>>16));}
    *out=(LmnDatDosResult){size<0?0x23ff:0x2300,dosflags(f,size<0)};
}
static void retry_ui(void *ctx,uint8_t *m,const LmnDatFileCall *call,LmnDatRetryResult *out) {
    LmnHost *h=ctx;(void)m;
    /* game_loop's retry connector intercepts this callback on loop entry. A
       direct DAT caller has no resumable stop ABI: fail closed, never spin. */
    fail(h,"unconnected direct DAT retry callback");
    *out=(LmnDatRetryResult){call->value,call->handle,call->base_cursor,call->flags};
    /* A direct client must not enter this void callback in a C retry loop. */
    fputs("host: unconnected direct DAT retry callback\n",stderr);exit(86);
}
static void saved_flags(uint8_t *m,const LmnRegs *r,uint16_t flags){putword(m,r->ss,(uint16_t)(r->sp+4),flags);}
static uint16_t bios_body(void *ctx,uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnHost *h=ctx;(void)m;(void)bus;
    if(r->ax==0x1a00){r->ax=(r->ax&0xff00)|0x1a;r->bx=7;}
    else if((r->ax>>8)==0x12){r->bx&=0xff00;r->cx&=0xff00;}
    else if((r->ax>>8)==0x0f){r->ax=(uint16_t)(0x5000|h->vga.mode);r->bx&=255;}
    else if(!(r->ax>>8))video_mode(h,(uint8_t)r->ax);
    else if((r->ax>>8)==5){h->vga.crtc[12]=0;h->vga.crtc[13]=0;}
    else if((r->ax>>8)==2){/* headless text cursor; no graphics effect */}
    else fail(h,"unbound INT10 function");
    return h->error[0]?1:0;
}
static uint16_t clock_body(void *ctx,uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnHost *h=ctx;(void)m;(void)bus;
    if((r->ax>>8)==1)h->bios_clock=((uint32_t)r->cx<<16)|r->dx;
    else if(!(r->ax>>8)){r->cx=(uint16_t)(h->bios_clock>>16);r->dx=(uint16_t)h->bios_clock;r->ax&=0xff00;}
    else fail(h,"unbound INT1A function");
    return h->error[0]?1:0;
}
static uint16_t adlib_body(void *,uint8_t *,LmnRegs *,const LmnRasterBus *);
static uint16_t dos_body(void *ctx,uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnHost *h=ctx;unsigned fn=r->ax>>8,n=r->ax&255;LmnDatDosResult d;LmnDatFileServiceResult f;
    uint16_t flags=word(m,r->ss,(uint16_t)(r->sp+4));size_t i;(void)bus;
    if(fn==0x25){
        putword(m,0,(uint16_t)(n*4),r->dx);putword(m,0,(uint16_t)(n*4+2),r->ds);
        /* Explicit muted service for the installed MAIN.DAT PC-speaker entry.
           Other live vectors still have to match their bound providers. */
        if(n==0x60 && r->ds==(uint16_t)(h->load+0x842) && r->dx==0x182){h->mute60.code_segment=r->ds;h->mute60.instruction_pointer=r->dx;}
        /* 057B installs the sound driver at its allocation:0000 before loading
           it (054E). Bind that live vector to the C AdLib engine. */
        if(n==0x61 && r->dx==0){
            h->mute61=(LmnInterruptService){h,adlib_body,r->ds,0};
            h->sound_binding=(LmnSoundDriverBinding){r->ds,LMN_SOUND_DRIVER_ADLIB};
        }
    }
    else if(fn==0x35){r->bx=word(m,0,(uint16_t)(n*4));r->es=word(m,0,(uint16_t)(n*4+2));}
    else if(fn==0x1b){r->ds=0x600;r->bx=0x100;}
    else if(fn==7){fail(h,"headless startup requires preset display/options command");}
    else if(fn==0x3d || fn==0x43){file_service(h,m,r->ds,r->dx,flags,&f,fn==0x43);r->ax=f.value;if(fn==0x43)r->cx=f.count;saved_flags(m,r,f.flags);}
    else if(fn==0x3f){read_file(h,m,r->bx,r->ds,r->dx,r->cx,flags,&d);r->ax=d.value;saved_flags(m,r,d.flags);}
    else if(fn==0x3e){close_file(h,m,r->bx,r->ax,flags,&d);r->ax=d.value;saved_flags(m,r,d.flags);}
    else if(fn==0x23){query_file(h,m,r->ds,r->dx,flags,&d);r->ax=d.value;saved_flags(m,r,d.flags);}
    else if(fn==0x48){
        uint32_t end=0x3000;for(i=0;i<h->arena_count;i++)end=(uint32_t)h->arenas[i].segment+h->arenas[i].paragraphs;
        if(end<0x3000)end=0x3000;
        if(h->arena_count==ARENA_CAP || end+r->bx>0x9000){r->ax=8;r->bx=(uint16_t)(0x9000-end);saved_flags(m,r,dosflags(flags,1));}
        else {h->arenas[h->arena_count++]=(HostArena){(uint16_t)end,r->bx};r->ax=(uint16_t)end;saved_flags(m,r,dosflags(flags,0));}
    } else if(fn==0x49 || fn==0x4a){
        for(i=0;i<h->arena_count && h->arenas[i].segment!=r->es;i++){}
        if(i==h->arena_count){r->ax=9;saved_flags(m,r,dosflags(flags,1));}
        else if(fn==0x49 && i+1==h->arena_count){h->arena_count--;saved_flags(m,r,dosflags(flags,0));}
        else if(fn==0x4a && (i+1==h->arena_count?(uint32_t)r->es+r->bx<=0x9000:(uint32_t)r->es+r->bx<=h->arenas[i+1].segment)){
            h->arenas[i].paragraphs=r->bx;saved_flags(m,r,dosflags(flags,0));
        }else {r->ax=8;saved_flags(m,r,dosflags(flags,1));}
    } else if(fn==0x09 || fn==2){/* headless DOS console, no game-state effects */}
    else if(fn==0x3c || fn==0x40){r->ax=5;saved_flags(m,r,dosflags(flags,1));} /* read-only filesystem */
    else if(fn==0x4c)h->dos_exited=1;
    else fail(h,"unbound INT21 function");
    return h->error[0]?1:0;
}
static uint16_t mouse_body(void *ctx,uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnHost *h=ctx;(void)m;(void)bus;
    switch(r->ax) {
    case 0:r->ax=65535;r->bx=2;break;
    case 1:h->mouse_visible=1;break;case 2:h->mouse_visible=0;break;
    case 3:r->cx=h->mouse_x;r->dx=h->mouse_y;r->bx=h->mouse_buttons;break;
    case 4:h->mouse_x=r->cx;h->mouse_y=r->dx;break;
    case 7:h->mouse_min_x=r->cx;h->mouse_max_x=r->dx;break;
    case 8:h->mouse_min_y=r->cx;h->mouse_max_y=r->dx;break;
    case 15:h->mouse_mickeys_x=r->cx;h->mouse_mickeys_y=r->dx;break;
    case 0x0c:
        if(r->cx && (r->cx!=0x7f || r->es!=h->load || r->dx!=0xf6f))fail(h,"INT33 callback outside native RETF profile");
        else {h->mouse_callback_mask=r->cx;h->mouse_callback_cs=r->es;h->mouse_callback_ip=r->dx;}
        break;
    default:fail(h,"unbound INT33 function");break;
    }return h->error[0]?1:0;
}
enum { OPL_RATE=49716 };
/* Render OPL output up to the current PIT time (stereo 16-bit frames). */
static void render_audio(LmnHost *h) {
    uint64_t target=h->now*OPL_RATE/LMN_HOST_PIT_HZ;
    while(h->audio && !h->audio_failed && h->audio_frames<target) {
        int16_t frame[2];
        OPL3_Generate(&h->opl,frame);
        if(fwrite(frame,sizeof(frame[0]),2,h->audio)!=2)h->audio_failed=1;
        h->audio_frames++;
    }
}
/* AdLib card ports 0388 (address/status) and 0389 (data). Platform model:
   register writes go to the OPL core in call order; register 04 is the timer
   control the driver's detection uses (Nuked OPL3 has no timers). Profile
   assumption: a started, unmasked timer has expired by the next status read,
   i.e. the driver's delay loop outlasts 80us*(256-T1) as on the machines the
   detection was written for. Reads of either port return the status byte. */
static void opl_out(void *ctx,uint8_t *m,uint16_t port,uint8_t value,uint16_t flags) {
    LmnHost *h=ctx;(void)m;(void)flags;
    if(port==0x388)h->opl_address=value;
    else if(port==0x389) {
        render_audio(h);
        if(h->opl_address==4) {
            if(value&0x80)h->opl_status=0;
            else h->opl_control=value;
        } else OPL3_WriteReg(&h->opl,h->opl_address,value);
    } else fail(h,"OPL port outside 0388/0389");
}
static uint8_t opl_in(void *ctx,uint8_t *m,uint16_t port,uint16_t flags) {
    LmnHost *h=ctx;(void)m;(void)flags;
    if(port!=0x388 && port!=0x389){fail(h,"OPL port outside 0388/0389");return 0xff;}
    if((h->opl_control&1) && !(h->opl_control&0x40))h->opl_status|=0xC0;
    if((h->opl_control&2) && !(h->opl_control&0x20))h->opl_status|=0xA0;
    return h->opl_status;
}
/* INT61 at the game-installed driver segment:0000. Only the pinned AdLib image
   is served (its dispatcher prefix is checked); the Tandy engine is not
   translated, so a Tandy image there stops the host explicitly. */
static uint16_t adlib_body(void *ctx,uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    static const uint8_t prefix[14]={0x22,0xe4,0x75,0x03,0xe9,0x0e,0x01,0xfe,0xcc,0x75,0x03,0xe9,0x95,0x00};
    LmnHost *h=ctx;uint16_t status;
    if(memcmp(m+phys(r->cs,0),prefix,sizeof(prefix))){fail(h,"INT61 target is not the pinned AdLib driver");return 1;}
    h->sound_requests++;
    status=lmn_adlib_int61_core(m,r,bus,&h->opl_ports);
    if(status!=LMN_ADLIB_ENGINE_IRET) {
        char message[96];snprintf(message,sizeof(message),"AdLib engine stop %u at %04x:%04x",status,r->cs,r->ip);fail(h,message);return 1;
    }
    return 0;
}
static uint16_t muted_body(void *ctx,uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnHost *h=ctx;(void)m;(void)r;(void)bus;h->sound_requests++;return 0;
}
static uint16_t media_probe(void *ctx,uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnHost *h=ctx;(void)m;(void)bus;
    if(h->media_policy==LMN_HOST_MEDIA_UNSUPPORTED)return LMN_MEDIA_UNSUPPORTED;
    /* Named semantic profile: preserved segments/saved registers, zero drive,
       recognized first signature or early BIOS failure. No decoded body runs;
       its discarded internal stack residue is outside this host service ABI. */
    r->dx=0;r->flags=(uint16_t)((r->flags&~0xDD5u)|0x244u);
    if(h->media_policy==LMN_HOST_MEDIA_REJECT){r->ax=0;r->bx=0;r->flags|=1;r->ip=0xE3C;return LMN_MEDIA_FAIL;}
    r->ax=0x581C;r->bx=0xA9F2;r->ip=0xE49;return LMN_MEDIA_PASS;
}
static uint16_t chain_body(void *ctx,uint8_t *m,LmnRegs *r,const LmnRasterBus *bus) {
    LmnHost *h=ctx;(void)bus;h->bios_clock++;putword(m,0x40,0x6c,(uint16_t)h->bios_clock);putword(m,0x40,0x6e,(uint16_t)(h->bios_clock>>16));out8(h,m,0x20,0x20,r->flags);return 0;
}
static void set_mode(void *ctx,uint8_t *m,const LmnVideoRestoreState *in,LmnVideoRestoreState *out) {
    (void)m;*out=*in;video_mode(ctx,(uint8_t)in->value);
}
static void set_page(void *ctx,uint8_t *m,const LmnVideoRestoreState *in,LmnVideoRestoreState *out) {
    LmnHost *h=ctx;(void)m;*out=*in;h->vga.crtc[12]=0;h->vga.crtc[13]=0;
}
static void restore_out(void *ctx,uint16_t port,uint8_t value,uint16_t flags){LmnHost *h=ctx;out8(h,h->memory,port,value,flags);}
static void restore_clock(void *ctx,uint8_t *m,const LmnTimerRestoreState *in,LmnTimerRestoreState *out){LmnHost *h=ctx;(void)m;*out=*in;h->bios_clock=((uint32_t)in->count<<16)|in->argument;}
static void restore_vector(void *ctx,uint8_t *m,const LmnVectorRestoreState *in,LmnVectorRestoreState *out){(void)ctx;*out=*in;putword(m,0,(uint16_t)((in->value&255)*4),in->argument);putword(m,0,(uint16_t)((in->value&255)*4+2),in->data_segment);}
static void disable_mouse(void *ctx,uint8_t *m,const LmnFatalCleanupState *in,LmnFatalCleanupState *out){LmnHost *h=ctx;(void)m;*out=*in;h->mouse_visible=0;}
static void console(void *ctx,uint8_t *m,const LmnFatalCleanupState *in,LmnFatalCleanupState *out){(void)ctx;(void)m;*out=*in;}
static void terminate(void *ctx,uint8_t *m,const LmnFatalCleanupState *in){LmnHost *h=ctx;(void)m;(void)in;fail(h,"DOS termination requested");}
uint16_t lmn_host_deliver(LmnHost *h,LmnRegs *r,uint16_t irq,uint8_t scan) {
    LmnHardwareIrqResult out;
    if(irq!=8 && irq!=9){fail(h,"invalid hardware IRQ");return 1;}
    if((h->pic_mask&(irq==8?1:2)) || h->pic_in_service || !(r->flags&0x200))return LMN_HARDWARE_IRQ_DEFERRED;
    h->scan=scan;h->pic_in_service|=irq==8?1:2;
    out=lmn_deliver_hardware_irq(h->memory,r,irq,&h->irq);*r=out.registers;
    if(out.status==LMN_HARDWARE_IRQ_DELIVERED){if(irq==8)h->irqs++;}
    else if(out.status!=LMN_HARDWARE_IRQ_DEFERRED) {
        char message[192];snprintf(message,sizeof(message),"IRQ%u stop %u/%u/%u/%u at %04x:%04x",irq,out.status,out.handler_status,out.child_status,out.service_status,r->cs,r->ip);fail(h,message);
    }
    return out.status;
}
static uint16_t foreground(void *ctx,uint8_t *m,LmnRegs *r,uint16_t site) {
    LmnHost *h=ctx;uint16_t status=0;unsigned delivered=0;(void)m;
    if(++h->polls>h->max_polls)fail(h,"foreground poll budget exhausted");
    if(h->error[0] || (h->max_frames && h->frames>=h->max_frames))return LMN_HOST_STOP;
    if(h->poll_hook){status=h->poll_hook(h->hook_context,h,r,site);if(status)return status;}
    if(h->automatic) {
        /* A poll is a short CPU timeslice, not a whole display frame. In
           particular the 83 keyboard-byte polls must not turn a short key
           press into an unobservable press/release between scans. */
        h->now+=128;
        if(h->now>=h->next_irq)h->pending08=1;
    }
    while(h->event_cursor<h->event_count && h->events[h->event_cursor].time<=h->now) {
        LmnHostEvent *e=&h->events[h->event_cursor];
        if(e->kind==LMN_HOST_EVENT_MOUSE){
            h->mouse_x=e->x<h->mouse_min_x?h->mouse_min_x:(e->x>h->mouse_max_x?h->mouse_max_x:e->x);
            h->mouse_y=e->y<h->mouse_min_y?h->mouse_min_y:(e->y>h->mouse_max_y?h->mouse_max_y:e->y);h->mouse_buttons=e->value;
        }else {
            status=lmn_host_deliver(h,r,e->kind==LMN_HOST_EVENT_KEY?9:8,(uint8_t)e->value);
            if(status==LMN_HARDWARE_IRQ_DEFERRED)break;
            if(status)return LMN_HOST_STOP;
        }
        h->event_cursor++;if(++delivered>EVENT_CAP){fail(h,"event delivery budget exhausted");break;}
    }
    if(h->pending08) {
        uint64_t prior=h->next_irq;
        status=lmn_host_deliver(h,r,8,0);
        if(status==0){
            h->pending08=0;
            /* Preserve an actual guest reload. Otherwise the free-running
               PIT retains phase and coalesces elapsed requests into one. */
            if(h->next_irq==prior)h->next_irq=prior+((h->now-prior)/h->pit_reload+1)*h->pit_reload;
        }
        else if(status!=LMN_HARDWARE_IRQ_DEFERRED)return LMN_HOST_STOP;
    }
    return h->error[0]?LMN_HOST_STOP:0;
}
static void observe_loop(void *ctx,const uint8_t *m,const LmnRegs *r){LmnHost *h=ctx;(void)m;if(h->observe_hook)h->observe_hook(h->hook_context,h,r,0);}
static void observe_frame(void *ctx,const uint8_t *m,const LmnRegs *r){LmnHost *h=ctx;(void)m;if(r->ip==0x105)h->frames++;if(h->observe_hook)h->observe_hook(h->hook_context,h,r,1);}
static void bind(LmnHost *h) {
    h->bus=(LmnRasterBus){h,bus_read,bus_write,out16};h->ports=(LmnRasterBytePorts){h,out8,in8};h->poll=(LmnForegroundPoll){h,foreground};
    h->video=(LmnVideoRestoreServices){h,set_mode,set_page};
    h->bios=(LmnInterruptService){h,bios_body,0xb000,0x100};h->dos=(LmnInterruptService){h,dos_body,0xb000,0x200};
    h->mouse=(LmnInterruptService){h,mouse_body,0xb000,0x300};h->clock=(LmnInterruptService){h,clock_body,0xb000,0x600};
    h->mute60=(LmnInterruptService){h,muted_body,0xb000,0x400};h->mute61=(LmnInterruptService){h,muted_body,0xb000,0x500};h->chain=(LmnInterruptService){h,chain_body,0xb000,0x700};
    h->mouse_poll=(LmnInputPollService){h,mouse_body,0xb000,0x300};
    h->irq=(LmnHardwareIrqServices){&h->mouse_poll,&h->mute60,&h->mute61,&h->chain,&h->ports,&h->bus,h->load};
    h->files_service=(LmnDatFileServices){h,opened,attributes,retry_ui};h->io=(LmnDatIo){h,query_file,read_file};h->raw=(LmnRawResourceServices){h,raw_open,read_file,close_file};
    h->timer_restore=(LmnTimerRestoreServices){h,restore_out,restore_clock};h->vectors=(LmnVectorRestoreServices){h,restore_vector};
    h->cleanup=(LmnFatalCleanupServices){&h->timer_restore,&h->vectors,&h->video,h,disable_mouse,console,terminate};
    h->file_error=(LmnFileErrorServices){&h->video,&h->cleanup,h,console,console};
    h->selection=(LmnResourceSelectionServices){&h->files_service,&h->io,&h->raw};h->full=(LmnResourceSelectionFullServices){&h->selection,&h->file_error,&h->cleanup};
    h->special=(LmnSpecialSetupServices){&h->files_service,&h->io,&h->bus,h,close_file};
    h->briefing=(LmnBriefingServices){NULL,&h->ports,&h->bus};h->start=(LmnLevelStartServices){&h->segments,&h->full,&h->briefing,&h->bus,h->ds};
    h->probe=(LmnVideoProbeServices){&h->bios,&h->ports,&h->bus};h->level=(LmnLevelInitializeServices){&h->segments,&h->special,&h->bus,&h->ports};
    h->initialize=(LmnGameInitializeServices){&h->probe,&h->ports,&h->bus,&h->level,h->ds,0,&h->mouse,&h->dos,&h->poll};
    h->pc_binding=(LmnPcSpeakerBinding){(uint16_t)(h->load+0x842)};h->opl_ports=(LmnOplPorts){h,opl_out,opl_in};
    h->frame=(LmnGameFrameServices){&h->ports,&h->bus,&h->mute60,&h->mute61,&h->dos,&h->clock,&h->pc_binding,&h->sound_binding,&h->poll,h->ds};
    h->session=(LmnGameSessionServices){&h->initialize,&h->frame,h,observe_frame};
    h->result=(LmnLevelResultServices){&h->ports,&h->bus,&h->video,&h->poll,h->ds};
    h->loop=(LmnGameLoopServices){&h->video,&h->dos,&h->ports,&h->bus,&h->poll,&h->start,&h->session,&h->result,h,observe_loop,h->ds,h->load};
    h->sound_init=(LmnSoundDriverInitServices){&h->dos,&h->bios,&h->mute61,&h->files_service,&h->io};
    h->protection=(LmnProtectionServices){&h->dos,&h->bios,&h->clock,&h->mouse,&h->ports,&h->bus,h,media_probe};
    h->startup=(LmnStartupServices){&h->dos,&h->bios,&h->clock,&h->mouse,&h->ports,&h->bus,&h->files_service,&h->io,&h->sound_init,&h->protection};
}
LmnHost *lmn_host_create(const char *assets) {
    LmnHost *h=calloc(1,sizeof(*h));if(!h)return NULL;
    if(!assets || strlen(assets)>=sizeof(h->assets)){free(h);return NULL;}
    strcpy(h->assets,assets);h->load=0x1010;h->ds=0x19b9;h->next_handle=7;h->pit_reload=0x4000;h->pit_control=0x36;
    h->mouse_x=150;h->mouse_y=100;h->mouse_max_x=639;h->mouse_max_y=349;h->port61=0x15;
    h->max_polls=100000;h->max_accesses=500000000;h->automatic=1;h->next_irq=LMN_HOST_DISPLAY_TICKS;
    OPL3_Reset(&h->opl,OPL_RATE);
    bind(h);video_mode(h,0x0d);return h;
}
static void put32(uint8_t *p,uint32_t v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);}
static int write_wav_header(FILE *fp,uint64_t frames) {
    uint8_t header[44];uint64_t bytes=frames*4;uint32_t data=bytes>0xffffffd3u?0xffffffd3u:(uint32_t)bytes;
    memcpy(header,"RIFF",4);put32(header+4,36+data);memcpy(header+8,"WAVEfmt ",8);
    put32(header+16,16);header[20]=1;header[21]=0;header[22]=2;header[23]=0;
    put32(header+24,OPL_RATE);put32(header+28,OPL_RATE*4);header[32]=4;header[33]=0;header[34]=16;header[35]=0;
    memcpy(header+36,"data",4);put32(header+40,data);
    return fseek(fp,0,SEEK_SET)==0 && fwrite(header,1,44,fp)==44;
}
int lmn_host_open_audio(LmnHost *h,const char *path) {
    if(h->audio)return 0;
    h->audio=fopen(path,"wb");if(!h->audio)return 0;
    h->audio_frames=h->now*OPL_RATE/LMN_HOST_PIT_HZ;h->audio_failed=!write_wav_header(h->audio,0);
    {uint64_t silent=h->audio_frames;h->audio_frames=0;while(h->audio_frames<silent && !h->audio_failed){int16_t zero[2]={0,0};if(fwrite(zero,2,2,h->audio)!=2)h->audio_failed=1;h->audio_frames++;}}
    return !h->audio_failed;
}
int lmn_host_close_audio(LmnHost *h) {
    int ok;
    if(!h->audio)return 1;
    render_audio(h);
    ok=!h->audio_failed && write_wav_header(h->audio,h->audio_frames);
    if(fclose(h->audio))ok=0;
    h->audio=NULL;return ok;
}
uint64_t lmn_host_audio_frames(const LmnHost *h){return h->audio_frames;}
void lmn_host_destroy(LmnHost *h){size_t i;if(!h)return;if(h->audio)lmn_host_close_audio(h);for(i=0;i<FILE_CAP;i++)if(h->files[i].file)fclose(h->files[i].file);free(h);}
uint8_t *lmn_host_memory(LmnHost *h){return h->memory;}
LmnHostVga *lmn_host_vga(LmnHost *h){return &h->vga;}
const LmnGameLoopServices *lmn_host_services(LmnHost *h){return &h->loop;}
const char *lmn_host_error(const LmnHost *h){return h->error;}
uint64_t lmn_host_time(const LmnHost *h){return h->now;}
uint64_t lmn_host_frames(const LmnHost *h){return h->frames;}
uint64_t lmn_host_irqs(const LmnHost *h){return h->irqs;}
uint64_t lmn_host_sound_requests(const LmnHost *h){return h->sound_requests;}
uint64_t lmn_host_inputs(const LmnHost *h){return h->event_cursor;}
void lmn_host_set_limits(LmnHost *h,uint64_t p,uint64_t a,uint64_t f){h->max_polls=p;h->max_accesses=a;h->max_frames=f;}
void lmn_host_set_hooks(LmnHost *h,void *c,LmnHostPollHook p,LmnHostObserveHook o){h->hook_context=c;h->poll_hook=p;h->observe_hook=o;}
void lmn_host_automatic_timer(LmnHost *h,int enabled){h->automatic=enabled!=0;}
int lmn_host_set_time(LmnHost *h,uint64_t time){if(time<h->now)return 0;h->now=time;return 1;}
int lmn_host_enqueue(LmnHost *h,const LmnHostEvent *e){
    if(!e || e->kind<1 || e->kind>3 || h->event_count==EVENT_CAP || (h->event_count && e->time<h->events[h->event_count-1].time)){fail(h,"invalid/full/out-of-order input script");return 0;}
    h->events[h->event_count++]=*e;return 1;
}
int lmn_host_file_overlay(LmnHost *h,const char *name,const uint8_t *data,size_t size){
    size_t i;if(!data){h->overlay=NULL;return 1;}
    if(!name || !size || size>16*1024*1024)return 0;
    for(i=0;name[i];i++)if(i>=64 || !(isalnum((unsigned char)name[i]) || name[i]=='.' || name[i]=='_' || name[i]=='-'))return 0;
    if(strstr(name,".."))return 0;
    strcpy(h->overlay_name,name);h->overlay=data;h->overlay_size=size;return 1;
}
LmnGameLoopResult lmn_host_run(LmnHost *h,const LmnRegs *r){return lmn_game_loop_core(h->memory,r,&h->loop);}

int lmn_host_load_image(LmnHost *h,const char *path,uint16_t load) {
    uint8_t packed[32749],image[82906];uint16_t relocations[63];size_t size,count,i;FILE *fp;LmnPkliteHeader header;
    if((uint32_t)load*16+sizeof(image)>0xa0000){fail(h,"image load overlaps VGA or wraps");return 0;}
    fp=fopen(path,"rb");if(!fp){fail(h,"cannot open pinned executable");return 0;}
    i=fread(packed,1,sizeof(packed),fp);if(i!=sizeof(packed) || fgetc(fp)!=EOF){fclose(fp);fail(h,"wrong executable length");return 0;}fclose(fp);
    if(lmn_pklite_unpack(packed,sizeof(packed),image,sizeof(image),&size,relocations,63,&count,&header)!=LMN_PKLITE_OK){fail(h,"native PKLITE identity/decode failed");return 0;}
    memcpy(h->memory+(uint32_t)load*16,image,size);
    for(i=0;i<count;i++){uint32_t p=(uint32_t)load*16+relocations[i];uint16_t w=(uint16_t)(h->memory[p]|(h->memory[p+1]<<8));w=(uint16_t)(w+load);h->memory[p]=(uint8_t)w;h->memory[p+1]=(uint8_t)(w>>8);}
    h->load=load;h->ds=(uint16_t)(load+0x9a9);bind(h);return 1;
}
void lmn_host_bind_image(LmnHost *h,uint16_t load) {
    h->load=load;h->ds=(uint16_t)(load+0x9A9);
    h->segments=(LmnDatLoadSegments){word(h->memory,load,CS_CheckDatFile+0x33),word(h->memory,load,CS_SelectCachedDatFile+0x50),word(h->memory,load,CS_ReadDatBytes+8),word(h->memory,load,CS_DatReadFailure+1)};
    bind(h);
}
const LmnStartupServices *lmn_host_startup_services(LmnHost *h){return &h->startup;}
LmnStartupResult lmn_host_boot(LmnHost *h,uint16_t load,const char *command,enum LmnHostMediaPolicy policy) {
    char path[1152];LmnRegs r={0};LmnStartupResult out={0};size_t length=command?strlen(command):0;
    uint16_t psp=(uint16_t)(load-16u);unsigned i;
    out.status=LMN_STARTUP_CHILD_STOP;
    if(length>126 || (unsigned)policy>LMN_HOST_MEDIA_REJECT || load<0x100 || (uint32_t)psp+0x1911>0x3000){fail(h,"invalid DOS entry layout/command/media policy");return out;}
    memset(h->memory,0,sizeof(h->memory));snprintf(path,sizeof(path),"%s/vgalemmi.exe",h->assets);
    if(!lmn_host_load_image(h,path,load))return out;
    h->media_policy=policy;h->dos_exited=0;
    /* DOS owns one initial PSP block. ProgramEntry shrinks it via4A before
       the5571-paragraph48 request.3000 is a conventional-memory free boundary. */
    h->arenas[0]=(HostArena){psp,(uint16_t)(0x9000-psp)};h->arena_count=1;
    h->memory[phys(psp,0)]=0xCD;h->memory[phys(psp,1)]=0x20;
    putword(h->memory,psp,2,0x9000);h->memory[phys(psp,0x80)]=(uint8_t)length;
    if(length)memcpy(h->memory+phys(psp,0x81),command,length);
    h->memory[phys(psp,(uint16_t)(0x81+length))]=13;
    for(i=0;i<7;i++) {
        static const uint8_t numbers[]={0x10,0x21,0x33,0x60,0x61,0x1A,8};
        putword(h->memory,0,(uint16_t)(numbers[i]*4),(uint16_t)((i+1)*0x100));
        putword(h->memory,0,(uint16_t)(numbers[i]*4+2),0xB000);
    }
    for(i=0;i<3;i++) {
        static const uint8_t numbers[]={9,12,0x74};
        putword(h->memory,0,(uint16_t)(numbers[i]*4),(uint16_t)(0x700+numbers[i]));
        putword(h->memory,0,(uint16_t)(numbers[i]*4+2),0xB000);
    }
    putword(h->memory,0x40,0x63,0x3D4);
    putword(h->memory,0,0x78,0x100);putword(h->memory,0,0x7A,0x600);
    h->memory[phys(0x600,0x100)]=0xF8; /* DOS fixed-disk FAT profile, read-only files */
    r.cs=load;r.ds=psp;r.es=psp;r.ss=(uint16_t)(load+0x143E);r.sp=0x4AF4;r.flags=0x202;
    lmn_host_bind_image(h,load);
    out=lmn_startup_core(h->memory,&r,LMN_STARTUP_PROGRAM,&h->startup);
    if(out.status==LMN_STARTUP_READY && out.registers.ip!=0x43F2)fail(h,"startup missed menu handoff");
    return out;
}
static uint64_t hash_bytes(uint64_t value,const void *data,size_t size){const uint8_t *p=data;size_t i;for(i=0;i<size;i++){value^=p[i];value*=UINT64_C(1099511628211);}return value;}
uint64_t lmn_host_hash(const LmnHost *h){uint64_t v=UINT64_C(14695981039346656037);v=hash_bytes(v,h->memory,sizeof(h->memory));v=hash_bytes(v,h->vga.planes,sizeof(h->vga.planes));v=hash_bytes(v,h->vga.dac,sizeof(h->vga.dac));return hash_bytes(v,h->vga.crtc,sizeof(h->vga.crtc));}
int lmn_host_ppm(LmnHost *h,const char *path) {
    LmnHostVga *v=&h->vga;unsigned width=v->mode==0x10?640:320,height=v->mode==0x10?350:200;
    unsigned x,y,p,start=((unsigned)v->crtc[12]<<8)|v->crtc[13],pitch=v->crtc[0x13]*2;FILE *fp=fopen(path,"wb");
    if(!fp)return 0;
    fprintf(fp,"P6\n%u %u\n255\n",width,height);
    for(y=0;y<height;y++)for(x=0;x<width;x++) {
        unsigned at=(start+y*pitch+x/8)&65535,color=0,index;uint8_t rgb[3];
        for(p=0;p<4;p++)color|=((v->planes[p][at]>>(7-(x&7)))&1)<<p;
        index=v->attr[color]&63;
        if(v->attr[0x10]&128)index=(index&15)|((v->attr[0x14]&15)<<4);else index|=(v->attr[0x14]&12)<<4;
        index&=v->pel_mask;
        for(p=0;p<3;p++){unsigned c=v->dac[index][p];rgb[p]=(uint8_t)((c<<2)|(c>>4));}
        if(fwrite(rgb,1,3,fp)!=3){fclose(fp);return 0;}
    }
    return fclose(fp)==0;
}

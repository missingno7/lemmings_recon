/* SDL3 front end over the native host (platform_host.c).

   The game runs exactly as in the headless runner; this file only supplies
   platform devices at the host's foreground polls:
   - display: each frame the emulated beam completes (composed row by row
     with the palette of its own moment) is shown, scaled to a 4:3 window;
   - keyboard: SDL scancodes become PC set-1 make/break bytes delivered as IRQ09,
     with the E0 prefix for extended keys as a real keyboard sends it; SDL key
     repeats are typematic repeats (repeated make codes);
   - mouse: window coordinates mapped into the INT33 range the game set;
   - time: emulated PIT time is paced to the wall clock;
   - audio: OPL output streamed to an SDL audio stream at 49716 Hz.
   Scripted input (--script/--frames/--log) uses the same event path as the
   headless runner, so a scripted session is reproducible and comparable. */
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>
#include "platform_host.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { LOGICAL_W=640, LOGICAL_H=480, OPL_RATE=49716, SLICE=LMN_HOST_PIT_HZ/1000 };

typedef struct App {
    LmnHost *host;
    SDL_Window *window; SDL_Renderer *renderer; SDL_Texture *texture;
    SDL_AudioStream *audio;
    unsigned texture_w,texture_h;
    uint64_t shown_frame,next_slice,emu_base,wall_base;
    uint16_t mouse_x,mouse_y,buttons;
    int pace,quit,failed;
    FILE *log,*audio_log;
    uint64_t audio_delivered,audio_origin_pit;
    uint8_t rgb[640*350*3];
} App;

/* SDL scancode -> set-1 scan code; bit 8 marks an E0-prefixed key. */
static unsigned scan_code(SDL_Scancode s) {
    static const struct { SDL_Scancode sdl; unsigned set1; } map[]={
        {SDL_SCANCODE_ESCAPE,0x01},{SDL_SCANCODE_1,0x02},{SDL_SCANCODE_2,0x03},{SDL_SCANCODE_3,0x04},
        {SDL_SCANCODE_4,0x05},{SDL_SCANCODE_5,0x06},{SDL_SCANCODE_6,0x07},{SDL_SCANCODE_7,0x08},
        {SDL_SCANCODE_8,0x09},{SDL_SCANCODE_9,0x0A},{SDL_SCANCODE_0,0x0B},{SDL_SCANCODE_MINUS,0x0C},
        {SDL_SCANCODE_EQUALS,0x0D},{SDL_SCANCODE_BACKSPACE,0x0E},{SDL_SCANCODE_TAB,0x0F},
        {SDL_SCANCODE_Q,0x10},{SDL_SCANCODE_W,0x11},{SDL_SCANCODE_E,0x12},{SDL_SCANCODE_R,0x13},
        {SDL_SCANCODE_T,0x14},{SDL_SCANCODE_Y,0x15},{SDL_SCANCODE_U,0x16},{SDL_SCANCODE_I,0x17},
        {SDL_SCANCODE_O,0x18},{SDL_SCANCODE_P,0x19},{SDL_SCANCODE_LEFTBRACKET,0x1A},
        {SDL_SCANCODE_RIGHTBRACKET,0x1B},{SDL_SCANCODE_RETURN,0x1C},{SDL_SCANCODE_LCTRL,0x1D},
        {SDL_SCANCODE_A,0x1E},{SDL_SCANCODE_S,0x1F},{SDL_SCANCODE_D,0x20},{SDL_SCANCODE_F,0x21},
        {SDL_SCANCODE_G,0x22},{SDL_SCANCODE_H,0x23},{SDL_SCANCODE_J,0x24},{SDL_SCANCODE_K,0x25},
        {SDL_SCANCODE_L,0x26},{SDL_SCANCODE_SEMICOLON,0x27},{SDL_SCANCODE_APOSTROPHE,0x28},
        {SDL_SCANCODE_GRAVE,0x29},{SDL_SCANCODE_LSHIFT,0x2A},{SDL_SCANCODE_BACKSLASH,0x2B},
        {SDL_SCANCODE_Z,0x2C},{SDL_SCANCODE_X,0x2D},{SDL_SCANCODE_C,0x2E},{SDL_SCANCODE_V,0x2F},
        {SDL_SCANCODE_B,0x30},{SDL_SCANCODE_N,0x31},{SDL_SCANCODE_M,0x32},{SDL_SCANCODE_COMMA,0x33},
        {SDL_SCANCODE_PERIOD,0x34},{SDL_SCANCODE_SLASH,0x35},{SDL_SCANCODE_RSHIFT,0x36},
        {SDL_SCANCODE_KP_MULTIPLY,0x37},{SDL_SCANCODE_LALT,0x38},{SDL_SCANCODE_SPACE,0x39},
        {SDL_SCANCODE_CAPSLOCK,0x3A},{SDL_SCANCODE_F1,0x3B},{SDL_SCANCODE_F2,0x3C},{SDL_SCANCODE_F3,0x3D},
        {SDL_SCANCODE_F4,0x3E},{SDL_SCANCODE_F5,0x3F},{SDL_SCANCODE_F6,0x40},{SDL_SCANCODE_F7,0x41},
        {SDL_SCANCODE_F8,0x42},{SDL_SCANCODE_F9,0x43},{SDL_SCANCODE_F10,0x44},
        {SDL_SCANCODE_NUMLOCKCLEAR,0x45},{SDL_SCANCODE_SCROLLLOCK,0x46},{SDL_SCANCODE_KP_7,0x47},
        {SDL_SCANCODE_KP_8,0x48},{SDL_SCANCODE_KP_9,0x49},{SDL_SCANCODE_KP_MINUS,0x4A},
        {SDL_SCANCODE_KP_4,0x4B},{SDL_SCANCODE_KP_5,0x4C},{SDL_SCANCODE_KP_6,0x4D},
        {SDL_SCANCODE_KP_PLUS,0x4E},{SDL_SCANCODE_KP_1,0x4F},{SDL_SCANCODE_KP_2,0x50},
        {SDL_SCANCODE_KP_3,0x51},{SDL_SCANCODE_KP_0,0x52},{SDL_SCANCODE_KP_PERIOD,0x53},
        {SDL_SCANCODE_F11,0x57},{SDL_SCANCODE_F12,0x58},
        {SDL_SCANCODE_KP_ENTER,0x11C},{SDL_SCANCODE_RCTRL,0x11D},{SDL_SCANCODE_KP_DIVIDE,0x135},
        {SDL_SCANCODE_RALT,0x138},{SDL_SCANCODE_HOME,0x147},{SDL_SCANCODE_UP,0x148},
        {SDL_SCANCODE_PAGEUP,0x149},{SDL_SCANCODE_LEFT,0x14B},{SDL_SCANCODE_RIGHT,0x14D},
        {SDL_SCANCODE_END,0x14F},{SDL_SCANCODE_DOWN,0x150},{SDL_SCANCODE_PAGEDOWN,0x151},
        {SDL_SCANCODE_INSERT,0x152},{SDL_SCANCODE_DELETE,0x153}};
    size_t i;
    for(i=0;i<sizeof(map)/sizeof(map[0]);i++)if(map[i].sdl==s)return map[i].set1;
    return 0;
}

static void enqueue(App *a,uint16_t kind,uint16_t x,uint16_t y,uint16_t value) {
    LmnHostEvent e={lmn_host_time(a->host),kind,x,y,value};
    if(!lmn_host_enqueue(a->host,&e))a->failed=1;
}

static void key(App *a,SDL_Scancode s,int down) {
    unsigned code=scan_code(s);
    if(!code)return;
    if(code&0x100)enqueue(a,LMN_HOST_EVENT_KEY,0,0,0xE0);
    enqueue(a,LMN_HOST_EVENT_KEY,0,0,(uint16_t)((code&0x7F)|(down?0:0x80)));
}

static void mouse(App *a,float lx,float ly) {
    uint16_t min_x,max_x,min_y,max_y;
    lmn_host_mouse_range(a->host,&min_x,&max_x,&min_y,&max_y);
    lx=lx<0?0:(lx>LOGICAL_W-1?LOGICAL_W-1:lx);
    ly=ly<0?0:(ly>LOGICAL_H-1?LOGICAL_H-1:ly);
    a->mouse_x=(uint16_t)(min_x+(uint32_t)lx*((uint32_t)max_x-min_x+1)/LOGICAL_W);
    a->mouse_y=(uint16_t)(min_y+(uint32_t)ly*((uint32_t)max_y-min_y+1)/LOGICAL_H);
}

static void pump(App *a) {
    SDL_Event e;
    while(SDL_PollEvent(&e)) {
        switch(e.type) {
        case SDL_EVENT_QUIT:a->quit=1;break;
        case SDL_EVENT_KEY_DOWN:
            if(e.key.scancode==SDL_SCANCODE_RETURN && (e.key.mod&SDL_KMOD_ALT)) {
                if(!e.key.repeat)SDL_SetWindowFullscreen(a->window,!(SDL_GetWindowFlags(a->window)&SDL_WINDOW_FULLSCREEN));
                break;
            }
            key(a,e.key.scancode,1);break;
        case SDL_EVENT_KEY_UP:key(a,e.key.scancode,0);break;
        case SDL_EVENT_MOUSE_MOTION:
        case SDL_EVENT_MOUSE_BUTTON_DOWN:
        case SDL_EVENT_MOUSE_BUTTON_UP:
            SDL_ConvertEventToRenderCoordinates(a->renderer,&e);
            if(e.type==SDL_EVENT_MOUSE_MOTION)mouse(a,e.motion.x,e.motion.y);
            else {
                uint16_t bit=e.button.button==SDL_BUTTON_LEFT?1:e.button.button==SDL_BUTTON_RIGHT?2:0;
                mouse(a,e.button.x,e.button.y);
                if(e.type==SDL_EVENT_MOUSE_BUTTON_DOWN)a->buttons|=bit;else a->buttons&=(uint16_t)~bit;
            }
            enqueue(a,LMN_HOST_EVENT_MOUSE,a->mouse_x,a->mouse_y,a->buttons);
            break;
        default:break;
        }
    }
}

static void present(App *a) {
    unsigned w,h;
    lmn_host_render_rgb(a->host,a->rgb,&w,&h);
    if(!a->texture || a->texture_w!=w || a->texture_h!=h) {
        if(a->texture)SDL_DestroyTexture(a->texture);
        a->texture=SDL_CreateTexture(a->renderer,SDL_PIXELFORMAT_RGB24,SDL_TEXTUREACCESS_STREAMING,(int)w,(int)h);
        if(!a->texture){a->failed=1;return;}
        SDL_SetTextureScaleMode(a->texture,SDL_SCALEMODE_NEAREST);
        a->texture_w=w;a->texture_h=h;
    }
    SDL_UpdateTexture(a->texture,NULL,a->rgb,(int)(w*3));
    SDL_RenderClear(a->renderer);
    SDL_RenderTexture(a->renderer,a->texture,NULL,NULL);
    SDL_RenderPresent(a->renderer);
}

static void pace(App *a,uint64_t now) {
    uint64_t emu=(now-a->emu_base)*UINT64_C(1000000000)/LMN_HOST_PIT_HZ;
    uint64_t wall=SDL_GetTicksNS()-a->wall_base;
    if(emu>wall+UINT64_C(1000000))SDL_DelayPrecise(emu-wall);
    else if(wall>emu+UINT64_C(250000000)){a->emu_base=now;a->wall_base=SDL_GetTicksNS();}
}

static uint16_t poll_hook(void *context,LmnHost *h,LmnRegs *r,uint16_t site) {
    App *a=context;uint64_t now=lmn_host_time(h);(void)r;(void)site;
    if(now>=a->next_slice) {
        a->next_slice=now+SLICE;
        pump(a);
        if(a->pace)pace(a,now);
    }
    if(lmn_host_display_frames(h)!=a->shown_frame) {
        /* The beam completed a frame: show it, as the monitor would. */
        a->shown_frame=lmn_host_display_frames(h);
        present(a);
    }
    return (a->quit || a->failed)?LMN_HOST_STOP:0;
}

static void observe(void *context,LmnHost *h,const LmnRegs *r,uint16_t kind) {
    App *a=context;
    if(a->audio_log && kind && r->ip==0x105)
        fprintf(a->audio_log,"%" PRIu64 ",%" PRIu64 "\n",lmn_host_time(h)-a->audio_origin_pit,a->audio_delivered);
    if(a->log && kind && r->ip==0x105)
        fprintf(a->log,"%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%04x,%016" PRIx64 "\n",
            lmn_host_frames(h),lmn_host_time(h),lmn_host_irqs(h),r->ip,lmn_host_hash(h));
}

static void audio_sink(void *context,const int16_t *frames,size_t count) {
    App *a=context;
    a->audio_delivered+=count;
    if(a->audio)SDL_PutAudioStreamData(a->audio,frames,(int)(count*4));
}

static int script(LmnHost *h,const char *path) {
    FILE *fp=fopen(path,"r");char line[256],kind[24];unsigned long long time;unsigned x,y,value;
    uint64_t origin=lmn_host_time(h);
    if(!fp)return 0;
    while(fgets(line,sizeof(line),fp)) {
        LmnHostEvent e={0};int fields;
        if(line[0]=='#' || line[0]=='\n' || line[0]=='\r')continue;
        fields=sscanf(line,"%llu %23s %u %u %u",&time,kind,&x,&y,&value);
        if(fields==5 && !strcmp(kind,"mouse")){e.kind=LMN_HOST_EVENT_MOUSE;e.x=(uint16_t)x;e.y=(uint16_t)y;e.value=(uint16_t)value;}
        else if(fields==3 && !strcmp(kind,"key")){e.kind=LMN_HOST_EVENT_KEY;e.value=(uint16_t)x;}
        else {fclose(fp);return 0;}
        e.time=origin+(uint64_t)time*LMN_HOST_PIT_HZ/1000;
        if(!lmn_host_enqueue(h,&e)){fclose(fp);return 0;}
    }
    return fclose(fp)==0;
}

int main(int argc,char **argv) {
    App a;LmnStartupResult boot;LmnGameLoopResult out;LmnRegs r;
    const char *assets="assets",*script_path=NULL,*log_path=NULL,*audio_log_path=NULL;
    enum LmnHostMediaPolicy policy=LMN_HOST_MEDIA_ASSUME_ORIGINAL;
    uint64_t frames=0;int adlib=1,i,status=0;
    SDL_AudioSpec spec={SDL_AUDIO_S16,2,OPL_RATE};
    memset(&a,0,sizeof(a));a.pace=1;
    for(i=1;i<argc;i++) {
        if(!strcmp(argv[i],"--sound=adlib"))adlib=1;
        else if(!strcmp(argv[i],"--sound=speaker"))adlib=0;
        else if(!strcmp(argv[i],"--no-pace"))a.pace=0;
        else if(!strcmp(argv[i],"--media-probe=reject"))policy=LMN_HOST_MEDIA_REJECT;
        else if(!strcmp(argv[i],"--media-probe=assume-original"))policy=LMN_HOST_MEDIA_ASSUME_ORIGINAL;
        else if(!strcmp(argv[i],"--assets") && i+1<argc)assets=argv[++i];
        else if(!strcmp(argv[i],"--script") && i+1<argc)script_path=argv[++i];
        else if(!strcmp(argv[i],"--log") && i+1<argc)log_path=argv[++i];
        else if(!strcmp(argv[i],"--audio-log") && i+1<argc)audio_log_path=argv[++i];
        else if(!strcmp(argv[i],"--frames") && i+1<argc)frames=strtoull(argv[++i],NULL,10);
        else {
            fprintf(stderr,"usage: lemmings [--assets DIR] [--sound=adlib|speaker] [--media-probe=assume-original|reject]\n"
                           "                [--no-pace] [--script FILE] [--frames N] [--log FRAMES.csv]\n");
            return 2;
        }
    }
    if(!SDL_Init(SDL_INIT_VIDEO|SDL_INIT_AUDIO)){fprintf(stderr,"SDL_Init: %s\n",SDL_GetError());return 1;}
    if(!SDL_CreateWindowAndRenderer("Lemmings",LOGICAL_W*2,LOGICAL_H*2,SDL_WINDOW_RESIZABLE,&a.window,&a.renderer)) {
        fprintf(stderr,"window: %s\n",SDL_GetError());SDL_Quit();return 1;
    }
    SDL_SetRenderLogicalPresentation(a.renderer,LOGICAL_W,LOGICAL_H,SDL_LOGICAL_PRESENTATION_LETTERBOX);
    SDL_SetRenderVSync(a.renderer,0);
    SDL_HideCursor();
    a.audio=SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK,&spec,NULL,NULL);
    if(a.audio)SDL_ResumeAudioStreamDevice(a.audio);
    else fprintf(stderr,"audio unavailable: %s\n",SDL_GetError());
    a.host=lmn_host_create(assets);
    if(!a.host){fprintf(stderr,"cannot create host\n");SDL_Quit();return 1;}
    if(log_path){a.log=fopen(log_path,"w");if(!a.log){fprintf(stderr,"cannot write %s\n",log_path);status=1;goto done;}
        fputs("frame,pit_time,irq08,ip,fnv1a64_ram_planes_dac_crtc\n",a.log);}
    boot=lmn_host_boot(a.host,0x1010,adlib?"/v /o":"/v /o /a",policy);r=boot.registers;
    if(boot.status!=LMN_STARTUP_READY || (script_path && !script(a.host,script_path))) {
        fprintf(stderr,"startup failed: %s\n",lmn_host_error(a.host));status=1;goto done;
    }
    /* Audio starts at the current game time: startup ran before any live
       device existed, and its elapsed time is not queued as stale audio. */
    lmn_host_set_audio_sink(a.host,audio_sink,&a);
    if(audio_log_path){a.audio_log=fopen(audio_log_path,"w");if(!a.audio_log){status=1;goto done;}}
    lmn_host_set_limits(a.host,UINT64_MAX,UINT64_MAX,frames);
    lmn_host_set_hooks(a.host,&a,poll_hook,observe);
    a.emu_base=a.audio_origin_pit=lmn_host_time(a.host);a.wall_base=SDL_GetTicksNS();
    a.next_slice=a.emu_base;a.shown_frame=lmn_host_display_frames(a.host);
    out=lmn_host_run(a.host,&r);
    printf("stop=%u core=%04x at=%04x:%04x frames=%" PRIu64 " error=%s\n",out.status,out.core_entry,
        out.registers.cs,out.registers.ip,lmn_host_frames(a.host),lmn_host_error(a.host));
    if(a.failed || (lmn_host_error(a.host)[0] && !a.quit))status=1;
done:
    if(a.log && fclose(a.log))status=1;
    if(a.audio_log && fclose(a.audio_log))status=1;
    lmn_host_destroy(a.host);
    if(a.audio)SDL_DestroyAudioStream(a.audio);
    if(a.texture)SDL_DestroyTexture(a.texture);
    SDL_DestroyRenderer(a.renderer);SDL_DestroyWindow(a.window);SDL_Quit();
    return status;
}

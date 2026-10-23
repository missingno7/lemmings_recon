#include "platform_host.h"
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct Runner {const char *output;FILE *log;unsigned menu,briefing,gameplay;uint16_t stop_site;int failed;uint64_t gameplay_frame,shots[64];unsigned shot_count;} Runner;
static void shot(Runner *s,LmnHost *h,const char *name) {
    char path[1200];snprintf(path,sizeof(path),"%s/%s.ppm",s->output,name);
    printf("capture %s pit_time=%" PRIu64 "\n",name,lmn_host_time(h));
    printf("scanout mode=%02x start=%02x%02x pitch=%u\n",lmn_host_vga(h)->mode,lmn_host_vga(h)->crtc[12],lmn_host_vga(h)->crtc[13],lmn_host_vga(h)->crtc[0x13]*2);
    if(!lmn_host_ppm(h,path)){fprintf(stderr,"cannot write %s\n",path);s->failed=1;}
}
static uint16_t poll_hook(void *ctx,LmnHost *h,LmnRegs *r,uint16_t site) {
    Runner *s=ctx;
    if(site==0x446d && !s->menu++){shot(s,h,"menu");}
    if(site==0x4683 && !s->briefing++){shot(s,h,"briefing");}
    if(s->failed || (s->stop_site && site==s->stop_site))return LMN_HOST_STOP;
    (void)r;return 0;
}
static void observe(void *ctx,LmnHost *h,const LmnRegs *r,uint16_t kind) {
    Runner *s=ctx;
    if(kind && r->ip==0x105){
        unsigned i;
        fprintf(s->log,"%" PRIu64 ",%" PRIu64 ",%" PRIu64 ",%04x,%016" PRIx64 "\n",lmn_host_frames(h),lmn_host_time(h),lmn_host_irqs(h),r->ip,lmn_host_hash(h));
        if(!s->gameplay && lmn_host_frames(h)>=s->gameplay_frame){s->gameplay=1;shot(s,h,"gameplay");}
        for(i=0;i<s->shot_count;i++)if(s->shots[i]==lmn_host_frames(h)){
            char name[64];snprintf(name,sizeof(name),"frame-%06" PRIu64,s->shots[i]);shot(s,h,name);
        }
    }
}
static int script(LmnHost *h,const char *path) {
    FILE *fp=fopen(path,"r");char line[256],kind[24];unsigned long long time;unsigned x,y,value;unsigned n=0;
    uint64_t origin=lmn_host_time(h);
    if(!fp)return 0;
    while(fgets(line,sizeof(line),fp)) {
        LmnHostEvent e={0};int fields;n++;
        if(line[0]=='#' || line[0]=='\n' || line[0]=='\r')continue;
        fields=sscanf(line,"%llu %23s %u %u %u",&time,kind,&x,&y,&value);
        if(fields==5 && !strcmp(kind,"mouse")){e.kind=LMN_HOST_EVENT_MOUSE;e.x=(uint16_t)x;e.y=(uint16_t)y;e.value=(uint16_t)value;}
        else if(fields==3 && !strcmp(kind,"key")){e.kind=LMN_HOST_EVENT_KEY;e.value=(uint16_t)x;}
        else {fprintf(stderr,"bad script line %u\n",n);fclose(fp);return 0;}
        e.time=origin+(uint64_t)time*LMN_HOST_PIT_HZ/1000;
        if(!lmn_host_enqueue(h,&e)){fclose(fp);return 0;}
    }
    return fclose(fp)==0;
}
int main(int raw_argc,char **raw_argv) {
    LmnHost *h;LmnRegs r;LmnGameLoopResult out;LmnStartupResult boot;Runner s={0};char path[1200];uint64_t frames;char *end;
    enum LmnHostMediaPolicy policy;int argc=0,adlib=0,audio=0,i;char *argv[16];
    /* --sound=adlib selects the original AdLib driver (no /a switch, so 054E
       loads adlib.dat); --sound=speaker (default) keeps /a, the PC-speaker
       fallback. --audio writes OUTPUT_DIR/audio.wav from the OPL output. */
    for(i=0;i<raw_argc;i++) {
        if(!strcmp(raw_argv[i],"--sound=adlib"))adlib=1;
        else if(!strcmp(raw_argv[i],"--sound=speaker"))adlib=0;
        else if(!strcmp(raw_argv[i],"--audio"))audio=1;
        else if(argc<16)argv[argc++]=raw_argv[i];
    }
    if(argc<6 || argc>8){fputs("usage: lemmings-headless ASSETS SCRIPT FRAMES OUTPUT_DIR --media-probe=assume-original|reject|unsupported [STOP_POLL_HEX [SHOT_FRAMES_CSV]] [--sound=speaker|adlib] [--audio]\n",stderr);return 2;}
    if(!strcmp(argv[5],"--media-probe=assume-original"))policy=LMN_HOST_MEDIA_ASSUME_ORIGINAL;
    else if(!strcmp(argv[5],"--media-probe=reject"))policy=LMN_HOST_MEDIA_REJECT;
    else if(!strcmp(argv[5],"--media-probe=unsupported"))policy=LMN_HOST_MEDIA_UNSUPPORTED;
    else return 2;
    frames=strtoull(argv[3],&end,10);if(!frames || *end)return 2;
    s.gameplay_frame=frames<16?frames:16;
    s.output=argv[4];if(argc>=7){s.stop_site=(uint16_t)strtoul(argv[6],&end,16);if(*end)return 2;}
    if(argc==8){
        const char *cursor=argv[7];
        do {uint64_t frame=strtoull(cursor,&end,10);if(!frame || end==cursor || s.shot_count==64)return 2;
            s.shots[s.shot_count++]=frame;if(!*end)break;if(*end!=',')return 2;cursor=end+1;
        }while(*cursor);
    }
    h=lmn_host_create(argv[1]);if(!h)return 2;
    snprintf(path,sizeof(path),"%s/frames.csv",s.output);s.log=fopen(path,"w");
    if(!s.log){lmn_host_destroy(h);return 2;}
    fputs("frame,pit_time,irq08,ip,fnv1a64_ram_planes_dac_crtc\n",s.log);
    if(audio){snprintf(path,sizeof(path),"%s/audio.wav",s.output);if(!lmn_host_open_audio(h,path)){fclose(s.log);lmn_host_destroy(h);return 2;}}
    boot=lmn_host_boot(h,0x1010,adlib?"/v /o":"/v /o /a",policy);r=boot.registers;
    printf("startup=%u child=%u service=%u at=%04x:%04x media-policy=%s\n",boot.status,boot.child_status,boot.service_status,r.cs,r.ip,argv[5]);
    if(boot.status!=LMN_STARTUP_READY || !script(h,argv[2])){
        fprintf(stderr,"host setup: %s\n",lmn_host_error(h));fclose(s.log);lmn_host_destroy(h);return 1;
    }
    lmn_host_set_limits(h,100000,500000000,frames);lmn_host_set_hooks(h,&s,poll_hook,observe);
    out=lmn_host_run(h,&r);
    printf("stop=%u core=%04x child=%u service=%u at=%04x:%04x frames=%" PRIu64 " irq08=%" PRIu64 " inputs=%" PRIu64 " sound-requests=%" PRIu64 " error=%s\n",
        out.status,out.core_entry,out.child_status,out.service_status,out.registers.cs,out.registers.ip,
        lmn_host_frames(h),lmn_host_irqs(h),lmn_host_inputs(h),lmn_host_sound_requests(h),lmn_host_error(h));
    {int ok=!s.failed && !lmn_host_error(h)[0] && (lmn_host_frames(h)>=frames || (s.stop_site && out.registers.ip==s.stop_site));
     if(fclose(s.log))ok=0;
     if(audio){printf("audio frames=%" PRIu64 "\n",lmn_host_audio_frames(h));if(!lmn_host_close_audio(h))ok=0;}
     lmn_host_destroy(h);return ok?0:1;}
}

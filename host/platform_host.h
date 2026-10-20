#ifndef LMN_PLATFORM_HOST_H
#define LMN_PLATFORM_HOST_H
#include <stddef.h>
#include <stdint.h>
#include "game_loop.h"
#include "hardware_irq.h"

/* Device storage, never a second copy of game state. Aperture bytes in RAM
   retain the last CPU bus value, independently of these four display planes. */
typedef struct LmnHostVga {
    uint8_t planes[4][65536], latches[4], seq[5], gc[9];
    uint8_t si, gi, crtc[32], ci, attr[32], ai, attr_data;
    uint8_t dac[256][3], dac_read, dac_write, dac_component, dac_read_component;
    uint8_t pel_mask, mode;
    uint32_t word_outputs;
} LmnHostVga;
typedef struct LmnHost LmnHost;
enum { LMN_HOST_MEMORY=1<<20, LMN_HOST_PIT_HZ=1193182,
       LMN_HOST_DISPLAY_TICKS=17044, LMN_HOST_STOP=0xCA11 };
enum { LMN_HOST_EVENT_MOUSE=1, LMN_HOST_EVENT_KEY=2, LMN_HOST_EVENT_IRQ08=3 };
/* Timed input in PIT clock units. Explicit IRQ08 events are for exact bounded
   verification; the runner normally enables the automatic PIT scheduler. */
typedef struct LmnHostEvent {
    uint64_t time;
    uint16_t kind, x, y, value;
} LmnHostEvent;
typedef uint16_t (*LmnHostPollHook)(void *,LmnHost *,LmnRegs *,uint16_t);
typedef void (*LmnHostObserveHook)(void *,LmnHost *,const LmnRegs *,uint16_t);

LmnHost *lmn_host_create(const char *assets);
void lmn_host_destroy(LmnHost *);
uint8_t *lmn_host_memory(LmnHost *);
LmnHostVga *lmn_host_vga(LmnHost *);
const LmnGameLoopServices *lmn_host_services(LmnHost *);
const char *lmn_host_error(const LmnHost *);
uint64_t lmn_host_time(const LmnHost *);
uint64_t lmn_host_frames(const LmnHost *);
uint64_t lmn_host_irqs(const LmnHost *);
uint64_t lmn_host_sound_requests(const LmnHost *);
uint64_t lmn_host_inputs(const LmnHost *);
void lmn_host_set_limits(LmnHost *,uint64_t polls,uint64_t accesses,uint64_t frames);
void lmn_host_set_hooks(LmnHost *,void *,LmnHostPollHook,LmnHostObserveHook);
void lmn_host_automatic_timer(LmnHost *,int enabled);
int lmn_host_enqueue(LmnHost *,const LmnHostEvent *);
/* Read-only fixture input overlay. Caller retains bytes until destroy; no
   live state is patched. NULL clears it. Basename only, same path policy. */
int lmn_host_file_overlay(LmnHost *,const char *name,const uint8_t *,size_t);
int lmn_host_set_time(LmnHost *,uint64_t);
uint16_t lmn_host_deliver(LmnHost *,LmnRegs *,uint16_t irq,uint8_t scan);
/* Load only the pinned EXE with the native PKLITE decoder and fixups. */
int lmn_host_load_image(LmnHost *,const char *path,uint16_t load);
/* Construct the declared post-startup domain, not the unresolved startup or
   protection path. See host/README.md for every producer and chosen arena. */
int lmn_host_post_startup(LmnHost *,uint16_t load,LmnRegs *);
/* Replace the fixture's small isolated arenas by the complete1007 allocation
   layout, then execute the maintained58D2 MAIN.DAT producer in native C. */
int lmn_host_prepare_resources(LmnHost *,const LmnRegs *);
LmnGameLoopResult lmn_host_run(LmnHost *,const LmnRegs *);
uint8_t lmn_host_read(LmnHost *,uint32_t);
void lmn_host_write(LmnHost *,uint32_t,uint8_t);
void lmn_host_out(LmnHost *,uint16_t,uint16_t,unsigned width);
uint8_t lmn_host_in(LmnHost *,uint16_t);
int lmn_host_ppm(LmnHost *,const char *path);
uint64_t lmn_host_hash(const LmnHost *);
#endif

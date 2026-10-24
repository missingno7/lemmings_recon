#ifndef LMN_PLATFORM_HOST_H
#define LMN_PLATFORM_HOST_H
#include <stddef.h>
#include <stdint.h>
#include "game_loop.h"
#include "hardware_irq.h"
#include "startup.h"

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
       LMN_HOST_STOP=0xCA11 };
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
enum LmnHostMediaPolicy { LMN_HOST_MEDIA_UNSUPPORTED, LMN_HOST_MEDIA_ASSUME_ORIGINAL,
    LMN_HOST_MEDIA_REJECT };
/* Establish only DOS/platform inputs, then run native ProgramEntry to43F2.
   The explicit media policy is a semantic provider, not physical floppy proof.
   Commands are the PSP byte string (at most126 bytes). No asset is written. */
LmnStartupResult lmn_host_boot(LmnHost *,uint16_t load,const char *command,
    enum LmnHostMediaPolicy);
/* Read-only service/relocated-DAT binding for constructed verification inputs. */
void lmn_host_bind_image(LmnHost *,uint16_t load);
const LmnStartupServices *lmn_host_startup_services(LmnHost *);
LmnGameLoopResult lmn_host_run(LmnHost *,const LmnRegs *);
uint8_t lmn_host_read(LmnHost *,uint32_t);
void lmn_host_write(LmnHost *,uint32_t,uint8_t);
void lmn_host_out(LmnHost *,uint16_t,uint16_t,unsigned width);
uint8_t lmn_host_in(LmnHost *,uint16_t);
int lmn_host_ppm(LmnHost *,const char *path);
/* Optional stereo 16-bit WAV of the OPL output at 49716 Hz, timed by the PIT
   clock; frames before opening are written as silence. Close fixes the header. */
int lmn_host_open_audio(LmnHost *,const char *path);
/* Live audio: called with each block of rendered stereo frames (49716 Hz). */
typedef void (*LmnHostAudioSink)(void *context,const int16_t *frames,size_t count);
void lmn_host_set_audio_sink(LmnHost *,LmnHostAudioSink,void *context);
/* Current scanout as packed RGB (640x350 in mode 10, else 320x200); rgb may
   be NULL to query the size. Uses the DAC at this instant. */
int lmn_host_render_rgb(const LmnHost *,uint8_t *rgb,unsigned *width,unsigned *height);
/* INT33 coordinate range last set by the game (functions 7/8). */
void lmn_host_mouse_range(const LmnHost *,uint16_t *min_x,uint16_t *max_x,uint16_t *min_y,uint16_t *max_y);
int lmn_host_close_audio(LmnHost *);
uint64_t lmn_host_audio_frames(const LmnHost *);
/* Raster frames the emulated beam has started since the last mode set; a
   change means lmn_host_render_rgb has a newly completed frame. */
uint64_t lmn_host_display_frames(const LmnHost *);
/* PIT time of the last BIOS mode set: raster position is measured from it. */
uint64_t lmn_host_raster_epoch(const LmnHost *);
uint64_t lmn_host_hash(const LmnHost *);
#endif

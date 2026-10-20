#ifndef LEMMINGS_VIDEO_PROBE_H
#define LEMMINGS_VIDEO_PROBE_H
#include "interrupt_service.h"
#include "aligned_read_mask.h"

typedef enum LmnVideoProbeEntry {
    LMN_VIDEO_DETECT,LMN_VIDEO_DCC,LMN_VIDEO_EGA,LMN_VIDEO_COLOR,
    LMN_VIDEO_MONO,LMN_VIDEO_CRTC,LMN_VIDEO_STORE,
    LMN_VIDEO_CALIBRATE,LMN_VIDEO_MEASURE,LMN_VIDEO_GAME_SETUP
} LmnVideoProbeEntry;
typedef struct LmnVideoProbeServices {
    const LmnInterruptService *bios;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
} LmnVideoProbeServices;
typedef enum LmnVideoProbeStatus {
    LMN_VIDEO_PROBE_READY,LMN_VIDEO_PROBE_MISSING_INPUT,LMN_VIDEO_PROBE_MISSING_OUTPUT,
    LMN_VIDEO_PROBE_INTERRUPT_STOP,LMN_VIDEO_PROBE_CHANGED_RETURN,
    LMN_VIDEO_PROBE_MISSING_WORD_OUTPUT,LMN_VIDEO_PROBE_UNBOUND_TARGET
} LmnVideoProbeStatus;
typedef struct LmnVideoProbeResult {
    LmnRegs registers;
    uint16_t status,child_status,service_status;
} LmnVideoProbeResult;
_Static_assert(sizeof(LmnVideoProbeResult)==34u,"34-byte video-probe result");
/* Logical cores stop before their own actual RET. Detector callbacks execute
   only the four identified entries; other targets stop before CALL AX1407,
   with the original SI/CX saves intact. BIOS uses full live INT10/IRET frames.
   Polling has no synthetic game timeout. Bus/providers own canonical memory. */
LmnVideoProbeResult lmn_video_probe_core(uint8_t *,const LmnRegs *,LmnVideoProbeEntry,const LmnVideoProbeServices *);
LmnVideoProbeResult lmn_video_probe_adapter(uint8_t *,const LmnRegs *,LmnVideoProbeEntry,const LmnVideoProbeServices *);
#endif

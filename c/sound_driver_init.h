#ifndef LEMMINGS_SOUND_DRIVER_INIT_H
#define LEMMINGS_SOUND_DRIVER_INIT_H

#include "dat_load.h"
#include "interrupt_service.h"

typedef struct LmnSoundDriverInitServices {
    const LmnInterruptService *dos;
    const LmnInterruptService *bios;
    /* Bound to the live installed INT61 target. Driver engines remain a host
       service; the initializer never substitutes an INT60/61 vector. */
    const LmnInterruptService *sound;
    const LmnDatFileServices *files;
    const LmnDatIo *io;
} LmnSoundDriverInitServices;

enum LmnSoundDriverInitStatus {
    LMN_SOUND_INIT_RETURNED = 0,
    LMN_SOUND_INIT_UNBOUND_SERVICE = 1,
    LMN_SOUND_INIT_PROVIDER_STOP = 2,
    LMN_SOUND_INIT_CHANGED_IRET = 3,
    LMN_SOUND_INIT_CHANGED_CHILD_RETURN = 4,
    LMN_SOUND_INIT_DAT_FILE_ERROR = 5,
    LMN_SOUND_INIT_DAT_DECODE_ERROR = 6,
    LMN_SOUND_INIT_MISSING_DAT_SERVICE = 7
};

typedef struct LmnSoundDriverInitResult {
    uint16_t status, child_status, service_status;
} LmnSoundDriverInitResult;

/* Entry CS:054E, live caller stack word already present. Core stops at the
   selected original RET (05B3/05F5/060B); adapter consumes that actual word.
   Both mutate the complete live register packet and canonical memory. DAT
   child accesses use its existing direct-RAM contract (not a VGA stack).
   Its retry UI must eventually return; callers bound execution externally. */
LmnSoundDriverInitResult lmn_initialize_sound_driver_core(uint8_t *memory,
    LmnRegs *registers, const LmnSoundDriverInitServices *services,
    const LmnRasterBus *bus);
LmnSoundDriverInitResult lmn_initialize_sound_driver_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnSoundDriverInitServices *services,
    const LmnRasterBus *bus);

#endif

#ifndef LEMMINGS_PCSPEAKER_DISPATCH_H
#define LEMMINGS_PCSPEAKER_DISPATCH_H

#include <stdint.h>
#include "regs.h"
#include "special_blit.h"

typedef struct LmnPcSpeakerDispatchCall {
    uint16_t value,base_value,count,argument,source_cursor,output_cursor;
    uint16_t data_segment,driver_segment,stack_segment,stack_offset,flags;
} LmnPcSpeakerDispatchCall;

typedef struct LmnPcSpeakerDispatchResult {
    uint16_t value,base_value,count,argument,source_cursor,output_cursor;
    uint16_t data_segment,driver_segment,stack_segment,stack_offset,flags;
    uint16_t continuation,status;
} LmnPcSpeakerDispatchResult;

enum LmnPcSpeakerDispatchStatus {
    LMN_PC_SPEAKER_IRET_READY=0,
    LMN_PC_SPEAKER_UNTRANSLATED_CHILD=1,
    LMN_PC_SPEAKER_CHANGED_CHILD_RETURN=2
};

LmnPcSpeakerDispatchResult lmn_pc_speaker_dispatch_core(
    uint8_t *memory,const LmnPcSpeakerDispatchCall *call,
    const LmnRasterBus *bus);

/* The adapter performs the original IRET only when the core reaches 01A0. */
uint16_t lmn_pc_speaker_dispatch_adapter(uint8_t *memory,LmnRegs *registers,
                                         const LmnRasterBus *bus);

#endif

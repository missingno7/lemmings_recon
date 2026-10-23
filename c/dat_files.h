#ifndef LEMMINGS_DAT_FILES_H
#define LEMMINGS_DAT_FILES_H
#include "regs.h"

typedef struct LmnDatFileCall {
    uint16_t value,handle,count,filename_offset,source_cursor,output_cursor,base_cursor;
    uint16_t segment,extra_segment,stack_segment,stack_offset,flags;
} LmnDatFileCall;
typedef struct LmnDatFileResult {
    uint16_t value,handle,count,filename_offset,source_cursor,output_cursor,base_cursor;
    uint16_t segment,extra_segment,stack_offset,flags,fatal;
} LmnDatFileResult;
typedef struct LmnDatFileServiceResult {uint16_t value,count,flags;} LmnDatFileServiceResult;
typedef struct LmnDatRetryResult {uint16_t value,handle,base_cursor,flags;} LmnDatRetryResult;
typedef struct LmnDatFileServices {
    void *context;
    /* DOS services preserve registers other than AX and (for AH43) CX. */
    void (*open_readonly)(void *,uint8_t *,uint16_t segment,uint16_t filename,
        uint16_t flags,LmnDatFileServiceResult *out);
    void (*attributes)(void *,uint8_t *,uint16_t segment,uint16_t filename,
        uint16_t flags,LmnDatFileServiceResult *out);
    /* Explicit unported game-callee boundary at 4B1C. The live near-return word
       is present at call->stack_offset; it must stay intact. This verification
       seam must be connected to translated rendering/input logic for completion.
       AX and saved-register clobbers do not survive the resumed attribute loop. */
    void (*retry_ui)(void *,uint8_t *,const LmnDatFileCall *,LmnDatRetryResult *out);
} LmnDatFileServices;

/* INT24 critical-error callback (CriticalErrorHandler, main 18F8; installed by
   DOS AX=2524 at 008D). Platform contract: DOS invokes it from inside an INT21
   service (here AH3D open / AH43 attributes) that hits a device error, before
   that service returns. It stores FF to DatCriticalErrorFlag 1FDF in the game
   data segment and returns AX for DOS: AL=00 (ignore), AH=high byte of that
   segment. It never retries, aborts or touches the DOS registers otherwise.
   What DOS returns from the interrupted service after "ignore" (success, or
   CF=1/AX=53 "fail" when ignore is not allowed) is DOS behavior. CheckDatFile
   and LoadDatResource take their error route (4B1C retry screen, or 1949
   when retries are disabled) on carry OR a nonzero live flag, so both DOS
   outcomes are caught; OpenDatFile does not test it, LoadDatResource does
   after the open. 0090, 4B16 and 4B56 clear the flag. A native
   file-service provider that reports such an error must call this core during
   the service; the wrappers never set the flag themselves. */
uint16_t lmn_dat_critical_error_core(uint8_t *,uint16_t game_data_segment);
/* Original-code testing boundary: CS:IP=18F8, the DOS INT24 IRET frame at
   SS:SP. Writes the saved-DS residue at SS:SP-2, pops DS and the frame from
   live memory and leaves IRET-restored FLAGS. */
void lmn_dat_critical_error_adapter(uint8_t *,LmnRegs *);
LmnDatFileResult lmn_dat_open_file_core(uint8_t *,const LmnDatFileCall *,const LmnDatFileServices *);
LmnDatFileResult lmn_dat_check_file_core(uint8_t *,uint16_t retry_data_segment,
    uint16_t lookup_data_segment,const LmnDatFileCall *,const LmnDatFileServices *);
void lmn_dat_open_file_adapter(uint8_t *,LmnRegs *,const LmnDatFileServices *);
void lmn_dat_check_file_adapter(uint8_t *,LmnRegs *,const LmnDatFileServices *);
#endif

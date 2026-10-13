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
typedef struct LmnDatRetryResult {uint16_t handle,base_cursor,flags;} LmnDatRetryResult;
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

LmnDatFileResult lmn_dat_open_file_core(uint8_t *,const LmnDatFileCall *,const LmnDatFileServices *);
LmnDatFileResult lmn_dat_check_file_core(uint8_t *,uint16_t retry_data_segment,
    uint16_t lookup_data_segment,const LmnDatFileCall *,const LmnDatFileServices *);
void lmn_dat_open_file_adapter(uint8_t *,LmnRegs *,const LmnDatFileServices *);
void lmn_dat_check_file_adapter(uint8_t *,LmnRegs *,const LmnDatFileServices *);
#endif

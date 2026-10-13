#ifndef LEMMINGS_DAT_LOAD_H
#define LEMMINGS_DAT_LOAD_H
#include "dat_files.h"
#include "dat_section.h"

typedef struct LmnDatLoadSegments {
    uint16_t retry_data,lookup_data,read_data,decode_failure_data;
} LmnDatLoadSegments;
/* fatal: 0=near return, 1=original 1949 file error, 2=original 04D0 decoder error. */
LmnDatFileResult lmn_dat_load_core(uint8_t *,const LmnDatFileCall *,const LmnDatLoadSegments *,
    const LmnDatFileServices *,const LmnDatIo *);
LmnDatFileResult lmn_dat_decode_preserving_segment_core(uint8_t *,const LmnDatFileCall *,
    const LmnDatLoadSegments *,const LmnDatIo *);
void lmn_dat_load_adapter(uint8_t *,LmnRegs *,const LmnDatFileServices *,const LmnDatIo *);
void lmn_dat_load_after_check_adapter(uint8_t *,LmnRegs *,const LmnDatFileServices *,const LmnDatIo *);
void lmn_dat_decode_preserving_segment_adapter(uint8_t *,LmnRegs *,const LmnDatIo *);
#endif

#ifndef LEMMINGS_DAT_SECTION_H
#define LEMMINGS_DAT_SECTION_H
#include "dat_io.h"

typedef struct LmnDatSectionCall {
    uint16_t handle, source_segment, source_cursor, output_segment, output_cursor;
    uint16_t stack_segment, stack_offset, flags;
} LmnDatSectionCall;
typedef struct LmnDatSectionResult {
    uint16_t value, handle, bits_counter, stream_bytes, source_cursor, output_cursor;
    uint16_t output_start, source_segment, output_segment, stack_offset, flags;
    uint16_t failed_read;
} LmnDatSectionResult;

/* Unchecked original decoder. Malformed streams can loop indefinitely, just as
   the original can. Original near-call return words must remain intact. */
LmnDatSectionResult lmn_dat_section_core(uint8_t *mem,uint16_t data_segment,
    uint16_t failure_segment,const LmnDatSectionCall *call,const LmnDatIo *io);
void lmn_dat_section_adapter(uint8_t *mem,LmnRegs *r,const LmnDatIo *io);
#endif

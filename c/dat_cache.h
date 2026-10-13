#ifndef LEMMINGS_DAT_CACHE_H
#define LEMMINGS_DAT_CACHE_H
#include "regs.h"

typedef struct LmnDatNameCall {
    uint16_t segment, filename_offset, saved_value, saved_count, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnDatNameCall;
typedef struct LmnDatNameResult {
    uint16_t filename_offset, value, count, extra_segment, source_cursor, output_cursor;
    uint16_t stack_offset, flags;
} LmnDatNameResult;
typedef struct LmnDatLookupCall {
    uint16_t segment, source_cursor, comparison_cursor, value, count, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnDatLookupCall;
typedef struct LmnDatLookupResult {
    uint16_t segment, source_cursor, comparison_cursor, value, count, extra_segment;
    uint16_t stack_offset, flags;
} LmnDatLookupResult;
typedef struct LmnDatDisableResult {uint16_t value,flags;} LmnDatDisableResult;

/* These calls use live original stack slots. Missing filename dots can make
   preparation scan forever; no validation is added to the original behavior. */
LmnDatNameResult lmn_dat_prepare_name_core(uint8_t *mem,const LmnDatNameCall *call);
LmnDatLookupResult lmn_dat_select_cache_core(uint8_t *mem,uint16_t data_segment,
    const LmnDatLookupCall *call);
LmnDatDisableResult lmn_dat_disable_cache_core(uint8_t *mem,uint16_t segment,
    uint16_t value,uint16_t flags);
void lmn_dat_prepare_name_adapter(uint8_t *mem,LmnRegs *r);
void lmn_dat_select_cache_adapter(uint8_t *mem,LmnRegs *r);
void lmn_dat_disable_cache_adapter(uint8_t *mem,LmnRegs *r);
#endif

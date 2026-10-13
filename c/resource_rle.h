#ifndef LEMMINGS_RESOURCE_RLE_H
#define LEMMINGS_RESOURCE_RLE_H
#include "regs.h"
typedef struct LmnResourceRleResult {
    uint16_t value,count,source_cursor,output_cursor,output_segment,flags;
} LmnResourceRleResult;
/* Live byte stream, 80 terminator, incoming DF preserved. The original has no
   bounds or missing-terminator check; instruction/return words must stay intact. */
LmnResourceRleResult lmn_decode_resource_rle_core(uint8_t *mem,uint16_t source_segment,
    uint16_t source_cursor,uint16_t output_segment,uint16_t output_cursor,
    uint16_t value,uint16_t count,uint16_t flags);
void lmn_decode_resource_rle_adapter(uint8_t *mem,LmnRegs *r);
#endif

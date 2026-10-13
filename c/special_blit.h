#ifndef LEMMINGS_SPECIAL_BLIT_H
#define LEMMINGS_SPECIAL_BLIT_H
#include "regs.h"
/* RAM and VGA aperture accesses share the original physical address domain.
   A native VGA backend must own its planes/latches; callbacks preserve registers.
   flags expose CLI/STI state to the boundary, not an instruction interpreter. */
typedef struct LmnRasterBus {
    void *context;
    uint8_t (*read_byte)(void *,uint8_t *mem,uint32_t address,uint16_t flags);
    void (*write_byte)(void *,uint8_t *mem,uint32_t address,uint8_t value,uint16_t flags);
    void (*out_word)(void *,uint16_t port,uint16_t value,uint16_t flags);
} LmnRasterBus;
typedef struct LmnSpecialBlitResult {
    uint16_t value,count,source_cursor,output_cursor,vertical_offset,port;
    uint16_t source_segment,output_segment,stack_offset,flags;
} LmnSpecialBlitResult;
LmnSpecialBlitResult lmn_blit_special_strip_core(uint8_t *mem,uint16_t data_segment,
    uint16_t stack_segment,uint16_t stack_offset,uint16_t vertical_offset,
    unsigned publish_graphics_segment,uint16_t flags,const LmnRasterBus *bus);
void lmn_blit_special_strip_adapter(uint8_t *,LmnRegs *,uint16_t strip,const LmnRasterBus *);
#endif

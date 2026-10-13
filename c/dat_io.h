#ifndef LEMMINGS_DAT_IO_H
#define LEMMINGS_DAT_IO_H
#include <stdint.h>
#include "regs.h"

/* DOS boundaries preserve registers other than AX and return explicit flags.
   Services write the same live memory supplied to the translated routine. */
typedef struct LmnDatDosResult { uint16_t value, flags; } LmnDatDosResult;
typedef struct LmnDatIo {
    void *context;
    void (*query_size)(void *context,uint8_t *mem,
        uint16_t fcb_segment,uint16_t fcb_offset,uint16_t flags,LmnDatDosResult *out);
    void (*read)(void *context,uint8_t *mem,uint16_t handle,
        uint16_t segment,uint16_t offset,uint16_t count,uint16_t flags,LmnDatDosResult *out);
} LmnDatIo;

/* Transient original near-call frame inputs, not a second game-state store.
   Saved cursors are observable when a read aliases their live stack slots. */
typedef struct LmnDatReadCall {
    uint16_t handle, count, destination_segment, destination_offset;
    uint16_t saved_source_cursor, saved_destination_cursor, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnDatReadCall;
typedef struct LmnDatReadResult {
    uint16_t value, handle, count, destination_segment, destination_offset;
    uint16_t source_cursor, destination_cursor, extra_segment, stack_offset, flags;
} LmnDatReadResult;

LmnDatReadResult lmn_dat_read_core(uint8_t *mem,uint16_t data_segment,
    const LmnDatReadCall *call,const LmnDatIo *io);
void lmn_dat_read_adapter(uint8_t *mem,LmnRegs *r,const LmnDatIo *io);
#endif

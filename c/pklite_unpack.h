#ifndef LMN_PKLITE_UNPACK_H
#define LMN_PKLITE_UNPACK_H

#include <stddef.h>
#include <stdint.h>

typedef enum LmnPkliteStatus {
    LMN_PKLITE_OK = 0,
    LMN_PKLITE_WRONG_IDENTITY = 1,
    LMN_PKLITE_MALFORMED = 2,
    LMN_PKLITE_CAPACITY = 3,
    LMN_PKLITE_ARGUMENT = 4
} LmnPkliteStatus;

typedef struct LmnPkliteHeader {
    uint16_t mz[14]; /* magic through overlay, in DOS header order */
    uint16_t entry_cs, entry_ip, stack_ss, stack_sp;
    size_t relocation_stream_offset, footer_offset, consumed_bytes;
} LmnPkliteHeader;

/* Relocations are returned as image-relative linear offsets, in stream order. */
LmnPkliteStatus lmn_pklite_unpack(const uint8_t *exe, size_t size,
    uint8_t *image, size_t capacity, size_t *image_size,
    uint16_t *relocations, size_t relocation_capacity, size_t *relocation_count,
    LmnPkliteHeader *header);

#endif

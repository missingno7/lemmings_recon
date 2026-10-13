#ifndef LEMMINGS_RESOURCE_RAW_H
#define LEMMINGS_RESOURCE_RAW_H
#include "dat_io.h"
typedef struct LmnRawResourceCall {
    uint16_t filename_segment,filename_offset,destination_segment,destination_offset;
    uint16_t count,initial_handle,stack_segment,stack_offset,flags;
} LmnRawResourceCall;
typedef struct LmnRawResourceResult {
    uint16_t value,handle,count,offset,segment,extra_segment,stack_offset,flags,error_stage;
} LmnRawResourceResult;
typedef struct LmnRawResourceServices {
    void *context;
    /* These declared DOS boundaries preserve general/segment registers other
       than AX. close receives AX after the original partial AH=3E write. */
    void (*open_readonly)(void *,uint8_t *,uint16_t segment,uint16_t filename,uint16_t flags,LmnDatDosResult *out);
    void (*read)(void *,uint8_t *,uint16_t handle,uint16_t segment,uint16_t offset,uint16_t count,uint16_t flags,LmnDatDosResult *out);
    void (*close)(void *,uint8_t *,uint16_t handle,uint16_t value,uint16_t flags,LmnDatDosResult *out);
} LmnRawResourceServices;
LmnRawResourceResult lmn_read_raw_resource_core(uint8_t *,const LmnRawResourceCall *,const LmnRawResourceServices *);
void lmn_read_raw_resource_adapter(uint8_t *,LmnRegs *,const LmnRawResourceServices *);
#endif

#ifndef LEMMINGS_RESOURCE_RAW_H
#define LEMMINGS_RESOURCE_RAW_H
#include "dat_io.h"
#include "special_blit.h"
typedef struct LmnRawResourceCall {
    uint16_t filename_segment,filename_offset,destination_segment,destination_offset;
    uint16_t count,initial_handle,stack_segment,stack_offset,flags;
} LmnRawResourceCall;
typedef struct LmnRawResourceResult {
    uint16_t value,handle,count,offset,segment,extra_segment,stack_offset,flags,error_stage;
} LmnRawResourceResult;
typedef struct LmnRawResourceServices {
    void *context;
    /* DOS services mutate canonical memory, return AX and flags, and preserve
       all other GPRs, segments, and SP. close receives AX after partial AH=3E. */
    void (*open_readonly)(void *,uint8_t *,uint16_t segment,uint16_t filename,uint16_t flags,LmnDatDosResult *out);
    void (*read)(void *,uint8_t *,uint16_t handle,uint16_t segment,uint16_t offset,uint16_t count,uint16_t flags,LmnDatDosResult *out);
    void (*close)(void *,uint8_t *,uint16_t handle,uint16_t value,uint16_t flags,LmnDatDosResult *out);
} LmnRawResourceServices;
LmnRawResourceResult lmn_read_raw_resource_core(uint8_t *,const LmnRawResourceCall *,const LmnRawResourceServices *);
/* Optional bus owns every CPU stack/global byte access; DOS providers still
   mutate the supplied canonical memory directly under the contract above. */
LmnRawResourceResult lmn_read_raw_resource_bus_core(uint8_t *,const LmnRawResourceCall *,const LmnRawResourceServices *,const LmnRasterBus *);
void lmn_read_raw_resource_adapter(uint8_t *,LmnRegs *,const LmnRawResourceServices *);
void lmn_read_raw_resource_bus_adapter(uint8_t *,LmnRegs *,const LmnRawResourceServices *,const LmnRasterBus *);
#endif

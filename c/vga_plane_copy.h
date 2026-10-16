#ifndef LEMMINGS_VGA_PLANE_COPY_H
#define LEMMINGS_VGA_PLANE_COPY_H

#include "special_blit.h"

enum LmnCopyResourcePlanesVgaStatus {
    LMN_COPY_RESOURCE_PLANES_VGA_READY = 0
};

/* Live register roles at CopyResourcePlanesToVga (57D1). */
typedef struct LmnCopyResourcePlanesVgaCall {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
} LmnCopyResourcePlanesVgaCall;

typedef struct LmnCopyResourcePlanesVgaResult {
    uint16_t ax, bx, cx, dx, si, di, bp;
    uint16_t code_segment, data_segment, extra_segment;
    uint16_t stack_segment, stack_offset, flags;
    uint16_t continuation, status;
} LmnCopyResourcePlanesVgaResult;

/* Executes through the instruction immediately before RET at 5826. */
LmnCopyResourcePlanesVgaResult lmn_copy_resource_planes_vga_core(
    uint8_t *memory, const LmnCopyResourcePlanesVgaCall *call,
    const LmnRasterBus *bus);

/* Applies the result and reads the actual live near-RET word. */
uint16_t lmn_copy_resource_planes_vga_adapter(uint8_t *memory,
    LmnRegs *registers, const LmnRasterBus *bus);

#endif

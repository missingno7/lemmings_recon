#ifndef LEMMINGS_PALETTE_PORTS_H
#define LEMMINGS_PALETTE_PORTS_H
#include "video_restore.h"
#include "aligned_read_mask.h"

/* Both port writers have the same twelve live register fields as the video
   restore leaves. */
typedef LmnVideoRestoreState LmnPalettePortsState;

typedef enum LmnPalettePortsEntry {
    LMN_PALETTE_PORTS_ENTRY_ATTRIBUTE = 0,
    LMN_PALETTE_PORTS_ENTRY_MAPPED_DAC = 1
} LmnPalettePortsEntry;

typedef enum LmnPalettePortsStatus {
    LMN_PALETTE_PORTS_READY = 0,
    LMN_PALETTE_PORTS_MISSING_INPUT = 1,
    LMN_PALETTE_PORTS_MISSING_OUTPUT = 2
} LmnPalettePortsStatus;

typedef struct LmnPalettePortsResult {
    LmnPalettePortsState state;
    uint16_t continuation;
    enum LmnPalettePortsStatus status;
} LmnPalettePortsResult;

/* Covers the 34-byte 5425..5446 and 67-byte 54C4..5506 leaves on canonical
   memory. Execution stops immediately before the RET at 5446 or 5506.
   Missing byte-port operations stop at their current instruction after
   preserving preceding register, flag, stack and bus work. The optional bus
   supplies canonical physical-memory reads/writes. */
LmnPalettePortsResult lmn_write_palette_ports_core(uint8_t *memory,
    uint16_t code_segment, const LmnPalettePortsState *input,
    LmnPalettePortsEntry entry, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus);

/* Maps the result to all twelve registers and consumes the actual live near
   RET word only when the selected writer reaches its RET boundary. */
void lmn_write_palette_ports_adapter(uint8_t *memory, LmnRegs *registers,
    LmnPalettePortsEntry entry, const LmnRasterBytePorts *ports,
    const LmnRasterBus *bus);

#endif

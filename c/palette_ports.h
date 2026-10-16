#ifndef LEMMINGS_PALETTE_PORTS_H
#define LEMMINGS_PALETTE_PORTS_H
#include "video_restore.h"
#include "aligned_read_mask.h"

/* All three byte-port writers share the video-restore live-register fields. */
typedef LmnVideoRestoreState LmnPalettePortsState;

typedef enum LmnPalettePortsEntry {
    LMN_PALETTE_PORTS_ENTRY_ATTRIBUTE = 0,
    LMN_PALETTE_PORTS_ENTRY_MAPPED_DAC = 1,
    LMN_PALETTE_PORTS_ENTRY_DIRECT_DAC = 2
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

/* Covers the 34-byte 5425..5446, 56-byte 548C..54C3 and 67-byte 54C4..5506
   leaves on canonical memory. Execution stops before the selected leaf RET.
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

typedef enum LmnTimerPaletteEntry {
    LMN_TIMER_PALETTE_ENTRY_BEFORE = 0,
    LMN_TIMER_PALETTE_ENTRY_AFTER = 1,
    LMN_TIMER_PALETTE_ENTRY_DIRECT = 2
} LmnTimerPaletteEntry;

typedef enum LmnTimerPaletteStatus {
    LMN_TIMER_PALETTE_READY = 0,
    LMN_TIMER_PALETTE_MISSING_INPUT = 1,
    LMN_TIMER_PALETTE_MISSING_OUTPUT = 2,
    LMN_TIMER_PALETTE_CHANGED_CHILD_RETURN = 3
} LmnTimerPaletteStatus;

typedef struct LmnTimerPaletteResult {
    LmnRegs registers;
    uint16_t status;
} LmnTimerPaletteResult;

_Static_assert(sizeof(LmnTimerPaletteResult) == 30u,
    "LmnTimerPaletteResult must remain a 30-byte boundary result");

/* Composes the 5473 and 553D timer prefixes with the direct DAC and
   attribute byte-port leaves. Child calls and inherited tail returns use the
   live canonical stack; the adapter consumes only the active outer RET. */
LmnTimerPaletteResult lmn_timer_palette_core(uint8_t *memory,
    const LmnRegs *registers, LmnTimerPaletteEntry entry,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

LmnTimerPaletteResult lmn_timer_palette_adapter(uint8_t *memory,
    const LmnRegs *registers, LmnTimerPaletteEntry entry,
    const LmnRasterBytePorts *ports, const LmnRasterBus *bus);

#endif

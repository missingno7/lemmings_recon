#ifndef LEMMINGS_PROTECTION_H
#define LEMMINGS_PROTECTION_H
#include "interrupt_service.h"
#include "port_io.h"

enum LmnMediaProbeOutcome {
    LMN_MEDIA_PASS, LMN_MEDIA_FAIL, LMN_MEDIA_UNSUPPORTED
};
/* Called at063E with its actual near return on live SS:SP. A completed
   outcome supplies pre-RET registers and any provider/stack residue, with
   DS/ES/CX/SI/DI/BP/SS:SP preserved, DF/TF clear and result CF explicit.
   It must leave IVT0..4, the eleven-byte floppy table and encoded code restored.
   The wrapper additionally clears the CS-dependent512-byte sector buffer.
   UNSUPPORTED stops here; it is neither rejection nor admission. No INT1/INT3
   implementation or implicit pass policy is supplied by this module. */
typedef uint16_t (*LmnMediaProbe)(void *,uint8_t *,LmnRegs *,const LmnRasterBus *);
typedef struct LmnProtectionServices {
    const LmnInterruptService *dos,*bios,*clock,*mouse;
    const LmnRasterBytePorts *ports;
    const LmnRasterBus *bus;
    void *context;
    LmnMediaProbe probe;
} LmnProtectionServices;
enum LmnProtectionEntry {
    LMN_PROTECTION_CHECK, LMN_PROTECTION_COUNTER, LMN_PROTECTION_WRITE,
    LMN_PROTECTION_FAILURE
};
enum LmnProtectionStatus {
    LMN_PROTECTION_READY, LMN_PROTECTION_INTERRUPT_STOP,
    LMN_PROTECTION_CHANGED_RETURN, LMN_PROTECTION_PROBE_SEAM,
    LMN_PROTECTION_MISSING_PORT, LMN_PROTECTION_DOS_EXIT
};
typedef struct LmnProtectionResult {
    LmnRegs registers;
    uint16_t status,child_status,service_status;
} LmnProtectionResult;
/* CONDITIONAL known startup domain: pinned relocated image, disjoint ordinary
   RAM code/data/stack/table, TF/DF clear, no asynchronous observer inside probe.
   Full framed platform services retain live segments, flags and return words.
   Counter writer reads0100 bytes at live DS:252A; all DOS results except open
   CF are unchecked. Core leaves its own RET; rejection exits through0EDF.
   Contract/readiness and ASM proposals: build/worker-boot-report.md. */
LmnProtectionResult lmn_protection_core(uint8_t *,const LmnRegs *,
    enum LmnProtectionEntry,const LmnProtectionServices *);
/* Ready-only actual outer nearRET; terminal/seam packets remain untouched. */
LmnProtectionResult lmn_protection_adapter(uint8_t *,const LmnRegs *,
    enum LmnProtectionEntry,const LmnProtectionServices *);
#endif

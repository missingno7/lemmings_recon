#ifndef LEMMINGS_REGS_H
#define LEMMINGS_REGS_H
#include <stdint.h>

/* Machine state used only by bounded original-code boundary adapters. */
typedef struct LmnRegs {
    uint16_t ax, bx, cx, dx, si, di, bp, sp;
    uint16_t cs, ds, es, ss;
    uint16_t ip, flags;
} LmnRegs;
#endif

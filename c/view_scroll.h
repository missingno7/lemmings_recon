#ifndef LEMMINGS_VIEW_SCROLL_H
#define LEMMINGS_VIEW_SCROLL_H
#include "view_visibility.h"

/* The core composes the shared visibility tail and leaves its RET pending.
   The adapter consumes the inherited caller RET; rebuild adds no CALL frame.
   Decoded instruction bytes, including the relocated4137 operand, are stable
   in this domain, as required by the visibility child. */
typedef struct LmnViewScrollResult {LmnRegs registers;uint16_t status;} LmnViewScrollResult;
typedef enum LmnViewScrollEntry {LMN_VIEW_SCROLL_SELECTOR,LMN_VIEW_SCROLL_LEFT} LmnViewScrollEntry;
LmnViewScrollResult lmn_view_scroll_core(uint8_t *,const LmnRegs *,LmnViewScrollEntry,const LmnRasterBus *);
LmnViewScrollResult lmn_view_scroll_adapter(uint8_t *,const LmnRegs *,LmnViewScrollEntry,const LmnRasterBus *);
#endif

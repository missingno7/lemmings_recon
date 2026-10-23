#ifndef LEMMINGS_ADLIB_ENGINE_H
#define LEMMINGS_ADLIB_ENGINE_H
#include "regs.h"
#include "special_blit.h"

/* OPL port boundary of the AdLib driver (platform service).

   Every OUT and IN that the original driver executes is one callback, in the
   original order: WriteOplRegister 0559 performs OUT base,reg; 12 x IN base;
   OUT base+1,value; 47 x IN base+1 (base = live driver word 08A3, 0388 as
   loaded), and DetectService performs two IN 0388 status reads. The IN values
   of the delay reads are not interpreted by the driver, but the last one is
   left in AL exactly as in the original. Callbacks see canonical RAM and the
   live FLAGS word (only TF/IF/DF are meaningful: arithmetic flags inside the
   driver are not modeled because every service exit is an IRET that replaces
   them). A missing callback stops the service before that instruction with
   LMN_ADLIB_ENGINE_MISSING_PORT; no value is invented for absent hardware. */
typedef struct LmnOplPorts {
    void *context;
    void (*out_byte)(void *, uint8_t *memory, uint16_t port,
                     uint8_t value, uint16_t flags);
    uint8_t (*in_byte)(void *, uint8_t *memory, uint16_t port, uint16_t flags);
} LmnOplPorts;

enum {
    /* The service reached its IRET (core: stopped before it; adapter: after). */
    LMN_ADLIB_ENGINE_IRET=0,
    /* Stream command 88..AF (characterized corrupted-control escape at 01EA:
       the original would jump through code bytes 03FA..0449), or a command
       table word that is not one of the eight original targets. Registers
       describe the state at 01EA (before JMP [SI]) or, for a changed table
       word, IP = that word after its read. Never a supported game state. */
    LMN_ADLIB_ENGINE_STREAM_ESCAPE=1,
    /* A near RET popped a value other than its CALL's return offset (live
       stack word changed by an alias/provider). IP/SP are after that RET. */
    LMN_ADLIB_ENGINE_RETURN_CHANGED=2,
    /* No port callback for the IN/OUT at IP; nothing was executed there. */
    LMN_ADLIB_ENGINE_MISSING_PORT=3,
    /* Core entered with IP other than 0115/00A3/003A. */
    LMN_ADLIB_ENGINE_NOT_A_SERVICE=4
};

/* AH=00 update 0115, AH=01 detection 00A3 and AH=02 reset 003A over the
   canonical driver memory at regs->cs (no copy of driver state). Entry: regs
   as at the service label (after the 0000 dispatcher, interrupt frame on
   SS:SP). On LMN_ADLIB_ENGINE_IRET, regs are those at the service's IRET
   (0176, 00E8/00EC or 006C) with the defined arithmetic flags of the last
   flag-setting instruction. All stack pushes/pops, return-offset reads and
   driver data accesses go through the bus in original order. */
uint16_t lmn_adlib_service_core(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus, const LmnOplPorts *ports);

/* Core followed by the original IRET (three live stack word pops, FLAGS
   normalized with bit1 set and bits3/5/15 clear). */
uint16_t lmn_adlib_service_adapter(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus, const LmnOplPorts *ports);

/* Complete INT 61h service from driver offset 0000: the dispatcher prefix
   and latch setters of c/sound_latches.c, then for AH=0/1/2 the service
   bodies above and their IRET. Returns an LMN_ADLIB_ENGINE_* status. */
uint16_t lmn_adlib_int61_adapter(uint8_t *memory, LmnRegs *regs,
    const LmnRasterBus *bus, const LmnOplPorts *ports);

#endif

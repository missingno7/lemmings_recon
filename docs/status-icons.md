# Status icon outline and restoration

DrawStatusIconOutline780D..789D owns145 bytes/60 sites; RestoreStatusIcon
789E..78FF owns98 bytes/40 sites. They have no calls or UNKNOWN holes. Their
243-byte physical module status_icons.asm preserves exact instruction order.

The outline discards AH, doubles unsigned AL, and adds2102 plus live
DrawingOrigin to obtain DI (16-bit wrap). VGA setup uses live SS mirrors and
word ports; ES becomesA000. CLI then covers two full-width STOSB bytes,
22 pairs of side bytes selected by bit masks80/01, and two final full-width
bytes. Each store first reads ES:DI into AH to load latches. DF changes STOSB
movement; explicit ADD DI,2A remains forward. With DF clear this is a16-pixel
by24-row outline (48 ordered read/write pairs). Final STI sets IF; AH retains
the final latch-read value and AL=FF. The core stops before RET789D.

Restoration first compares AL with0A using signed JNL. Bytes00..09 and80..FF
enter its refresh reset: BL computes3*AL with byte wrapping, BH is cleared,
BX adds64, and the live word at DS:BX+1 is cleared. This write precedes PUSH DS
and can affect later aliases. No bounded selector array is established.
After PUSH DS, AX becomes2*unsignedAL; DI is saved on live SS before adding
2102 and DrawingOrigin. The routine programs VGA mode1 through live mirror
writes and OUTs, then POP SI rereads the saved word, adds2C0 andF91F, and sets
DS=ES=A000. Exactly24 pairs of MOVSB copy source to destination. Both cursors
follow DF for each byte, then receive explicit +2A. Copies remain sequential
under source/destination overlap; source rows and saved words are not cached.
Actual POP DS restores the current stack word before RET78FF. Restoration
has no CLI/STI; its incoming IF remains. The VGA device owns mode1 latches.

Both cores use canonical memory and expose all live register roles. Their
adapters fetch actual post-operation near-return words with physical20-bit
wrapping. A RAM/no-op-port leaf fallback is only for constructed callers,
not a replacement VGA implementation. Allocation, input producers, IRQ timing
and integration into3AC8 remain separate obligations; see status-display.md.

Scoped native acceptance passes512 fixtures (all256 AL values at each entry)
at core/actual-RET adapter boundaries:1,024 comparisons,100 sites,six branch
outcomes,187,432 ordered events and nine completed mutants. Independent replay
checks the48-pixel outline and all24 sequential mode1 copy rows; VGA-backed
stack cases compare the complete original/native device state. Actual return
overwrites, live POP SI mirror aliases, DS=SS, DF/IF, origin providers and
physical20-bit word wrap remain covered. The report is
build/status-icons-differential.json with matching input hashes. Only these243
leaf bytes are accepted; the untranslated caller and glyph leaves remain open.

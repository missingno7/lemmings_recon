# Complete sprite-bank transform

`GenerateEntitySpriteBanks` at 59BB..5AC0 is a 262-byte, 114-site parent.
It pushes DS before reading incoming DS:1FE6 into ES and DS:1FE4 into DS,
then clears SI and DI. Its fifteen groups each load an immediate count,
save actual CX, call the three-byte or word-bank helper, restore actual CX,
advance SI by the literal stride and execute LOOP. A final five-byte bank
call precedes ADD SI,0180h, actual POP DS and RET 5AC0.

On intact frames with disjoint source/output/code/stack and DF clear, the
groups make 336 calls, consume 50F0h source bytes and emit 180B8h output bytes.
The final call consumes another 180h bytes and emits 1400h bytes, giving source
end 5270h and output end 194B8h. These coordinates do not establish allocation
success, resource length for arbitrary inputs or initialized lifetime.

The native parent composes the three verified adapters with actual SS CALL
words. All returned registers, segments, flags and stack roles remain live.
Changed child returns stop at their actual CS:IP before assuming a parent
continuation. Parent CX/DS and outer RET words remain in canonical memory.
Word high bytes advance the physical address by one with 20-bit wrap.

The focused campaign passes 24 fixtures at both APIs: 48 comparisons, all
114 parent sites and 30 branch outcomes, 2,787,712 ordered events and ten
completed mutants. The composed domain contains 694 bytes and executes all
313 sites and 70 of 72 static branch outcomes. The two other child outcomes
are outside this enclosing campaign, not classified as dead. Child bytes
already belong to their leaf translations and are not counted again.

Separate equations check 455,752 output bytes. Both the pinned MAIN.DAT input
and a constructed input execute all 337 calls at both boundaries. Section zero
decodes in memory to exactly 21,104 bytes, SHA256
`959341d6dd9e51cfa9877f510909b417c1b4266e3a051742cddc7cf85cd7ad44`.
Its complete 103,608-byte transformed image has SHA256
`6bf0c6b5568796cf2d42daf057ca95078e79136a6ab97e7b8f829d40f464e6d6`.
No decoded asset or runtime image is committed.

Focused provider cases select one call per group through actual saved CX
words; the literal code and group boundaries stay intact. They exercise live
source/destination/stack aliases, selector changes, saved DS and caller words,
DF-sensitive word children, VGA DS/ES/SS, and changed returns for all three
child families. A zero saved parent count reaches LOOP's FFFF wrap before a
constructed second child return stops the case. VGA save providers update the
live device planes as well as their read-map RAM mirror.

Run `tools/difftest.py entity_sprite_banks` or
`tests/entity_sprite_banks.py --original-only`. Limits are 900 seconds/512 MiB
per process, 3,000,000 original hook steps and 900,000 events per invocation.
The complete normal adapter finishes in 948,293 original steps/374,878 events.
Ordered events use fixed 20-byte packed records: 7,497,560 payload bytes for
that full invocation. Time, memory or callback exhaustion fails verification
and cannot count as a completed mutant.

Behavioral input hashes retain compiled C/headers, test/model/oracle support,
pinned inputs/toolchain metadata and maintained ASM. Progress prose and the
raw symbol ledger do not feed this behavior campaign and are excluded. The generated symbol header still pins compiled names/offsets;
the independent exact verifier checks the current ledger and ASM. Updating
acceptance notes therefore does not renew or invalidate executable evidence.
Unrelated retained campaigns keep their own scopes and hash policies; this
checkpoint does not establish aggregate or complete-game acceptance.

Next audit 5CC1's live 1FEA destination and constant word-pattern sources,
then the 57D1 transform before composing LoadMainResourceSections at 58D2.
No startup or full game discovery is executed.

## Ordinary group layout

All spans are hexadecimal and end-exclusive. The final row is the ungrouped
wide call.

| Group | Calls | DX | Child | Source span | Output span |
|---|---:|---|---|---|---|
| 1 | 18 | 020A | 5B11 | 0000..02D0 | 00000..032A0 |
| 2 | 16 | 030E | 5BB0 | 02D0..0810 | 032A0..039A0 |
| 3 | 16 | 020C | 5BB0 | 0810..0B10 | 039A0..03E20 |
| 4 | 16 | 020A | 5B11 | 0B10..0D90 | 03E20..06B20 |
| 5 | 16 | 020C | 5BB0 | 0D90..1090 | 06B20..06FA0 |
| 6 | 32 | 030D | 5BB0 | 1090..1A50 | 06FA0..07CA0 |
| 7 | 64 | 030A | 5BB0 | 1A50..2950 | 07CA0..090A0 |
| 8 | 48 | 030D | 5BB0 | 2950..37F0 | 090A0..0A420 |
| 9 | 8 | 020A | 5B11 | 37F0..3930 | 0A420..0BAA0 |
| 10 | 16 | 0310 | 5BB0 | 3930..3F30 | 0BAA0..0C2A0 |
| 11 | 16 | 020A | 5B11 | 3F30..41B0 | 0C2A0..0EFA0 |
| 12 | 8 | 020D | 5BB0 | 41B0..4350 | 0EFA0..0F210 |
| 13 | 14 | 040E | 5BB0 | 4350..4970 | 0F210..0F9B8 |
| 14 | 16 | 020A | 5B11 | 4970..4BF0 | 0F9B8..126B8 |
| 15 | 32 | 020A | 5B11 | 4BF0..50F0 | 126B8..180B8 |
| 16 | 1 | fixed | 5C06 | 50F0..5270 | 180B8..194B8 |

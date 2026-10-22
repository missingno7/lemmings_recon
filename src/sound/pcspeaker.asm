; Canonical decompressed driver. No initialization/relocation patches.
; Entry offset0182 is installed as INT60; see sound-hints.json for the original install.
; UNKNOWN includes unclassified sound data; no no-code claim is implied.
;
; S13 STATIC SEMANTIC CONTRACT (hex addresses unless an ordinal says decimal).
; Ledger: pcspeaker_InterruptEntry owns producers/raw target words/writers,
; lifecycle/timer/unknowns;EffectRecords owns all23 decoded15-byte records.
; Section5 ofMAIN.DAT (758 bytes) replaces main08420..08715,then main165D
; installs relocated0842:0182. Main5967 frame and1652 frame have relocations.
; Initial stored mainzeros and this replacement are separate executable views.
; Watchdog0183/0492 reinstalls without reload;16A9 restoresINT08,notINT60.
;
; ALL RECOVERED MAIN INT60 PRODUCERS (fresh analyze() equals rawCD60 census):
;0273 AX0100 stop /0286 AX0000 tick: music-toggle key path;
;02E1 AX0100 stop /02F4 AX0000 tick: end-of-level path;
;185F AX0000 tick: newly incremented001C odd only;
;2377 AX030C,26C0 AX0313,2F8C AX0302,31F6 AX0313,3F8D AX0313:effects.
; Each site checks main2010!=FF and25A7&1;stop/tick pairs reloadAX and gates
; separately. Natural effect IDs02/0C/13 select0046/00DC/0145,all in records.
; No recovered main raw reader/setter,02/04 or05..10 command. Protected-state
; ASM has noINT60; no main direct target enters08420..08715. These negatives
; do not exclude unknown transformed code,generic segmented stores or aliases.
;
; CONDITIONAL DISPATCH CLOSURE: intact loaded section/table,ordinary separated
; DS/SS/CS and actual live frames,no external writer. Only00/01/03 ->01D4/
;024F/01B0. These helpers write active1,phase6,countdowns8/9,fields0A..18,
; and last divisor1A..1B;NONE writes001E..0027. Thus recovered requests preserve
; the original three target words. All raw quirks remain,includingzero targets.
; RawAH00..10 calls DS:[001E+2*originalAH] in currentCS;02/04 target0000 data,
;05..10 read first24 effect bytes. This is not an extended service table.
; Initial05 target0320 enters main8740 UNKNOWN;06/07 target0C80 reaches main
;90A0 renderer storage underCS0842,not mainCS0. Other initial rawtargets can
; reach data/beyondmain;ledger lists flat offsets without proving valid entries.
; RawAH11..1F reads byte0001..000F;AH20..FF writesAL to0000..00DF.
; AH3E..47 can replace ALL ten stored table bytes;48..5F changes05..10 operands.
; Both raw read/write paths retainAH=(originalAH-10h)&FF;children may changeAX.
;0196 reads target BEFORE pushing019A;actual stack can alias the table/returns.
; Allsix restored registers and IRET IP/CS/FLAGS are reread from liveSS.
;
; TIMER/INTERRUPTS: Tick has no private IRQ installer. Game17C7 calls185F at
; odd001C with the gates above.0182 STI occurs before saves,so a foreground
; LoadEffect/Stop can be preempted. Load clearsactive01BD BEFORE15 explicit
; copy stores and activates last01CF:ordinary nestedTick sees old,inactive,or
; complete neweffect. InactiveTick still incrementsphase6 and can change PIT
; cache/ports;it does not touch copy fields. Raw setters,changedsegments and
; reentrant/provider/code aliases are independent seams;no universal schedule.
; Stop only clearsactive. The following mainTick chooses quiet divisor2;
; everyTick still reads61 and writes61|3,not a physical gate-disable policy.
;
; STATE/STORED ROLES: loaded active1=0,step2=0,phase6=0,countdowns/fields=0,
; lastdivisor1A=0. Phase6+=step2 on everyTick wraps8;no later phase reader was
; identified. NamesNoiseStep/NoisePhase do not establish an audible-noise path.
; Tick consumes every copied field: fiveLEwords step/current/reset/deltaA/B,
; rotatingbytes14/15,duration16,pulse/modreload17/18. Reload0 wraps256;period
; additions wrap16;ROR carry chooses deltas/gate. No index/duration clamps.
; The raw positive indexes00..16h read23 complete records0028..0180. Natural
; producers select only02/0C/13. RawAH48..FF changes stored0028..00DF only:
; records00..0B plus first4 bytes of0C. Load does not modify stored records.
; Signed selectors wrap16 and can read header/table/code/UNKNOWN/beyondpayload;
; explicitINC copy ignoresDF,retains live source/destination overlap and reload.
;
; STORED UNKNOWN:0000,0003..0005,0007,0019,001C..001D have no identified
; regular musical field/owner. Earlier blanket0000..001D runtime hint is now
; split;raw read/write/source windows are overlays,not inferred stored roles.
;0181=90 has no recovered entry/intendedrole;rawAL17 copies it with entrybytes.
;0255..02F5 afterStopRET look like other-code fragments,but no recovered entry,
; initial dispatch target or main direct transfer establishes execution/ownership.
; No16-byte tail window matches another decoded component,unpackedmain or local
; top-level asset. No provenance/dead-code/padding inference follows that search.
; RawAL25..2F copies tail;AL2F reaches outsidepayload02F6/02F7 as well. These
; source-read overlays preserve UNKNOWN primary roles. A raw table setter can
; target0181/anytailoffset,so no global no-code claim is made.
;
; READINESS: CONDITIONAL for natural00/01/03 and separated intact memory;
; raw arbitrary targets,UNKNOWN storedroles,actualIRQ/device/provider/lifetime
; closure still block whole-imagefreeze. Existing native dispatcher exitsbefore
; Tick;helperC success does not complete Tick bus/dispatcher composition. Muted/
; unbound sound omits this original behavior;hardware equivalence is unverified.
bits 16
org 0
pcspeaker_CurrentEffect equ pcspeaker_PeriodStep
pcspeaker_EffectRecordSize equ 15
pcspeaker_sub_01B0 equ pcspeaker_LoadEffect
pcspeaker_sub_01D4 equ pcspeaker_Tick
pcspeaker_sub_024F equ pcspeaker_Stop
; UNKNOWN: stored byte0; raw setter/copy source is a separate overlap.
    db 0x00 ; @00000
pcspeaker_EffectActive:
; DATA: runtime_data
    db 0x00 ; @00001
pcspeaker_NoiseStep:
; STORED:0002 runtime_data;0003..0005 UNKNOWN (raw accessor overlap).
    db 0x00,0x01,0x00,0x00 ; @00002
pcspeaker_NoisePhase:
; STORED:0006 runtime_data;0007 UNKNOWN,not inferred padding.
    db 0x00,0x90 ; @00006
pcspeaker_PulseCountdown:
; DATA: runtime_data
    db 0x00 ; @00008
pcspeaker_ModulationCountdown:
; DATA: runtime_data
    db 0x00 ; @00009
pcspeaker_PeriodStep:
; DATA: runtime_data
    db 0x00,0x00 ; @0000A
pcspeaker_CurrentPeriod:
; DATA: runtime_data
    db 0x00,0x00 ; @0000C
pcspeaker_PulseResetPeriod:
; DATA: runtime_data
    db 0x00,0x00 ; @0000E
pcspeaker_ModulationDeltaA:
; DATA: runtime_data
    db 0x00,0x00 ; @00010
pcspeaker_ModulationDeltaB:
; DATA: runtime_data
    db 0x00,0x00 ; @00012
pcspeaker_ModulationPattern:
; DATA: runtime_data
    db 0x00 ; @00014
pcspeaker_GatePattern:
; DATA: runtime_data
    db 0x00 ; @00015
pcspeaker_EffectDuration:
; DATA: runtime_data
    db 0x00 ; @00016
pcspeaker_EffectReload:
; STORED:0017..0018 runtime reload pair;0019 UNKNOWN.
    db 0x00,0x00,0x90 ; @00017
pcspeaker_LastPitPeriod:
; STORED:001A..001B runtime last divisor;001C..001D UNKNOWN.
    db 0x00,0x00,0x00,0x00 ; @0001A
pcspeaker_DispatchTable001E:
; DATA: lookup_table
    dw pcspeaker_Tick,pcspeaker_Stop,0,pcspeaker_LoadEffect,0 ; @0001E
; RECORD LIST (index@address:step,current,reset,deltaA,deltaB;mod,gate,duration,pulse,modreload)
; 00@0028: 0320,0C80,0C80,0140,FEC0;55,00,0A,00,01
; 01@0037: 0190,0960,0960,0140,FEC0;55,00,0A,00,01
; 02@0046: FF90,08C0,08C0,FFF0,0010;37,00,0A,00,01 MAIN
; 03@0055: 0280,26C0,26C0,0560,F9C0;55,2C,0C,02,01
; 04@0064: FD20,23A0,23A0,0240,FDC0;55,00,06,00,01
; 05@0073: 0100,2080,2080,0560,FAA0;55,00,14,15,01
; 06@0082: 0100,10E0,10E0,0560,FAA0;55,00,14,15,01
; 07@0091: 0100,10E0,10E0,0240,FDC0;55,00,1B,07,01
; 08@00A0: 01A0,3020,3650,0560,FAA0;D4,44,07,03,01
; 09@00AF: 0050,0140,0140,0030,FFD0;55,00,23,00,01
; 0A@00BE: FFC0,0460,0460,0010,FFF0;55,00,0A,00,01
; 0B@00CD: 0270,0320,0320,0320,FCE0;55,00,05,00,01
; 0C@00DC: 01A0,2080,2CF0,0560,FAA0;D4,44,46,09,01 MAIN
; 0D@00EB: FF90,1F40,1F40,0010,FFF0;55,00,19,02,01
; 0E@00FA: FFD0,1900,1900,0010,FFF0;55,00,19,02,01
; 0F@0109: FFA0,1540,1540,FF40,0130;37,00,2C,00,01
; 10@0118: 0090,00A0,00B0,0A70,F590;55,00,0F,05,01
; 11@0127: 0790,2120,2120,00A0,FF60;33,00,27,06,01
; 12@0136: 0050,1F40,2BC0,0640,FA60;55,88,50,00,01
; 13@0145: 0680,0010,0010,0110,FF20;55,EC,05,00,01 MAIN
; 14@0154: 0150,0AA0,10E0,0740,F8C0;33,00,19,05,01
; 15@0163: 0001,00A0,00B0,0A70,F590;55,00,0F,05,01
; 16@0172: 0270,0050,0060,0A70,F590;55,00,07,00,01
pcspeaker_EffectRecords:
; DATA: effect_record_table
    db 0x20,0x03,0x80,0x0c,0x80,0x0c,0x40,0x01,0xc0,0xfe,0x55,0x00,0x0a,0x00,0x01,0x90 ; @00028
; DATA: effect_record_table
    db 0x01,0x60,0x09,0x60,0x09,0x40,0x01,0xc0,0xfe,0x55,0x00,0x0a,0x00,0x01,0x90,0xff ; @00038
; DATA: effect_record_table
    db 0xc0,0x08,0xc0,0x08,0xf0,0xff,0x10,0x00,0x37,0x00,0x0a,0x00,0x01,0x80,0x02,0xc0 ; @00048
; DATA: effect_record_table
    db 0x26,0xc0,0x26,0x60,0x05,0xc0,0xf9,0x55,0x2c,0x0c,0x02,0x01,0x20,0xfd,0xa0,0x23 ; @00058
; DATA: effect_record_table
    db 0xa0,0x23,0x40,0x02,0xc0,0xfd,0x55,0x00,0x06,0x00,0x01,0x00,0x01,0x80,0x20,0x80 ; @00068
; DATA: effect_record_table
    db 0x20,0x60,0x05,0xa0,0xfa,0x55,0x00,0x14,0x15,0x01,0x00,0x01,0xe0,0x10,0xe0,0x10 ; @00078
; DATA: effect_record_table
    db 0x60,0x05,0xa0,0xfa,0x55,0x00,0x14,0x15,0x01,0x00,0x01,0xe0,0x10,0xe0,0x10,0x40 ; @00088
; DATA: effect_record_table
    db 0x02,0xc0,0xfd,0x55,0x00,0x1b,0x07,0x01,0xa0,0x01,0x20,0x30,0x50,0x36,0x60,0x05 ; @00098
; DATA: effect_record_table
    db 0xa0,0xfa,0xd4,0x44,0x07,0x03,0x01,0x50,0x00,0x40,0x01,0x40,0x01,0x30,0x00,0xd0 ; @000A8
; DATA: effect_record_table
    db 0xff,0x55,0x00,0x23,0x00,0x01,0xc0,0xff,0x60,0x04,0x60,0x04,0x10,0x00,0xf0,0xff ; @000B8
; DATA: effect_record_table
    db 0x55,0x00,0x0a,0x00,0x01,0x70,0x02,0x20,0x03,0x20,0x03,0x20,0x03,0xe0,0xfc,0x55 ; @000C8
; DATA: effect_record_table
    db 0x00,0x05,0x00,0x01,0xa0,0x01,0x80,0x20,0xf0,0x2c,0x60,0x05,0xa0,0xfa,0xd4,0x44 ; @000D8
; DATA: effect_record_table
    db 0x46,0x09,0x01,0x90,0xff,0x40,0x1f,0x40,0x1f,0x10,0x00,0xf0,0xff,0x55,0x00,0x19 ; @000E8
; DATA: effect_record_table
    db 0x02,0x01,0xd0,0xff,0x00,0x19,0x00,0x19,0x10,0x00,0xf0,0xff,0x55,0x00,0x19,0x02 ; @000F8
; DATA: effect_record_table
    db 0x01,0xa0,0xff,0x40,0x15,0x40,0x15,0x40,0xff,0x30,0x01,0x37,0x00,0x2c,0x00,0x01 ; @00108
; DATA: effect_record_table
    db 0x90,0x00,0xa0,0x00,0xb0,0x00,0x70,0x0a,0x90,0xf5,0x55,0x00,0x0f,0x05,0x01,0x90 ; @00118
; DATA: effect_record_table
    db 0x07,0x20,0x21,0x20,0x21,0xa0,0x00,0x60,0xff,0x33,0x00,0x27,0x06,0x01,0x50,0x00 ; @00128
; DATA: effect_record_table
    db 0x40,0x1f,0xc0,0x2b,0x40,0x06,0x60,0xfa,0x55,0x88,0x50,0x00,0x01,0x80,0x06,0x10 ; @00138
; DATA: effect_record_table
    db 0x00,0x10,0x00,0x10,0x01,0x20,0xff,0x55,0xec,0x05,0x00,0x01,0x50,0x01,0xa0,0x0a ; @00148
; DATA: effect_record_table
    db 0xe0,0x10,0x40,0x07,0xc0,0xf8,0x33,0x00,0x19,0x05,0x01,0x01,0x00,0xa0,0x00,0xb0 ; @00158
; DATA: effect_record_table
    db 0x00,0x70,0x0a,0x90,0xf5,0x55,0x00,0x0f,0x05,0x01,0x70,0x02,0x50,0x00,0x60,0x00 ; @00168
; DATA: effect_record_table
    db 0x70,0x0a,0x90,0xf5,0x55,0x00,0x07,0x00,0x01 ; @00178
; UNKNOWN:0181 stored90;no intended role/entry. RawAL17 copies it with code.
    db 0x90 ; @00181
; INT60 dispatcher contract (0182..01AF), with quiescent asynchronous IRQs:
; STI precedes live SS saves BX/CX/DX/SI/DI/DS and PUSH CS / POP DS.
; AH 00..10 doubles original AH for an unchecked word at DS:[001E+BX].
; CALL reads that live operand before PUSH 019A; header/stack aliases can change it.
; Only five initial table words are identified: Tick, Stop, zero, LoadEffect, zero.
; Selectors 05..10 read effect-record bytes. Zero or changed targets are not dead.
; AH 11..1F reads DS:[original AH-10]; AH 20..FF writes AL to DS:[AH-20].
; Both leave AH's SUB 10 residue. Raw setters can overwrite the dispatch table.
; Child RET, six restored words and IRET reread the actual stack; none are cached.
; DS from the PUSH CS / POP DS pair is live (including device providers), never assumed CS.
pcspeaker_InterruptEntry:
    sti ; @00182
    push bx ; @00183
    push cx ; @00184
    push dx ; @00185
    push si ; @00186
    push di ; @00187
    push ds ; @00188
    push cs ; @00189
    pop ds ; @0018A
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM selects different opcode/operand width) ; @0018B
    db 0x8a,0xdc ; ENCODED: mov bl,ah (NASM selects different opcode/operand width) ; @0018D
    sub ah,0x10 ; @0018F
    ja pcspeaker_loc_01A1 ; @00192
    shl bl,1 ; @00194
    db 0xff,0x97,0x1e,0x00 ; ENCODED: call [bx+0x1e] (NASM selects different opcode/operand width) ; @00196
pcspeaker_DispatchCallReturn019A:
pcspeaker_loc_019A:
    pop ds ; @0019A
    pop di ; @0019B
    pop si ; @0019C
    pop dx ; @0019D
    pop cx ; @0019E
    pop bx ; @0019F
pcspeaker_DispatchReturn01A0:
    iret ; @001A0
pcspeaker_loc_01A1:
    sub bl,0x20 ; @001A1
    jc pcspeaker_loc_01AA ; @001A4
    mov [bx],al ; @001A6
    jmp short pcspeaker_loc_019A ; @001A8
pcspeaker_loc_01AA:
    db 0x8a,0xdc ; ENCODED: mov bl,ah (NASM selects different opcode/operand width) ; @001AA
    mov al,[bx] ; @001AC
    jmp short pcspeaker_loc_019A ; @001AE
; Signed AL*15 selects a live forward copy of 15 bytes to DS:000A..0018.
; Explicit INC ignores DF. Read reload DS:0017 after copying; write DS:0008.
; DEC DS:0001 rereads its actual byte, preserving address-add carry and recording
; entry flags on both RMW bus accesses. RET uses the post-body live SS word.
; No port output or phase/cache reset here;the first scheduledTick predecrements
; duration. PositiveN givesN-1 active computations;0 expires on256thTick.
pcspeaker_LoadEffect:
    mov cx,0xf ; @001B0
    mov bx,0x28 ; @001B3
; With installed0842 frame, unchecked signed(AL)*15+0028 reads outside the02F6 payload.
; AL=2F spans02E9..02F7, touching main8716..8717; AL=30 starts02F8 at main8718.
; Recovered main effects02/0C/13 do not establish these inputs as game-reachable.
; This raw reader does not classify main U0988716..8807 as an effect-table extension.
    imul cl ; @001B6
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM selects different opcode/operand width) ; @001B8
    mov si,0xa ; @001BA
    mov [0x1],ch ; @001BD
pcspeaker_loc_01C1:
    mov al,[bx] ; @001C1
    mov [si],al ; @001C3
    inc bx ; @001C5
    inc si ; @001C6
    loop pcspeaker_loc_01C1 ; @001C7
    mov ax,[0x17] ; @001C9
    mov [0x8],ax ; @001CC
    dec byte [0x1] ; @001CF
    ret ; @001D3
; Tick contract: phase always advances; inactive/end selects divisor2. Duration
; and both countdowns wrap;period/deltas wrap16;ROR carries select A/B and gate.
; Program PIT43/42 only on cache difference,then always port61|3. No phase
; reader feeds sound;actual device/IRQ cadence is not supplied by this helper.
pcspeaker_Tick:
    mov cx,0x2 ; @001D4
    db 0x8a,0xfd ; ENCODED: mov bh,ch (NASM selects different opcode/operand width) ; @001D7
    mov al,[0x2] ; @001D9
    add [0x6],al ; @001DC
    cmp [0x1],bh ; @001E0
    jz pcspeaker_loc_0232 ; @001E4
    dec byte [0x16] ; @001E6
    jnz pcspeaker_loc_01F2 ; @001EA
    mov [0x1],bh ; @001EC
    jmp short pcspeaker_loc_0232 ; @001F0
pcspeaker_loc_01F2:
    mov ax,[0x17] ; @001F2
    dec byte [0x9] ; @001F5
    jnz pcspeaker_loc_0211 ; @001F9
    mov [0x9],ah ; @001FB
    ror byte [0x14],1 ; @001FF
    mov dx,[0x10] ; @00203
    jc pcspeaker_loc_020D ; @00207
    mov dx,[0x12] ; @00209
pcspeaker_loc_020D:
    add [0xc],dx ; @0020D
pcspeaker_loc_0211:
    mov dx,[0xc] ; @00211
    add dx,[0xa] ; @00215
    dec byte [0x8] ; @00219
    jnz pcspeaker_loc_0226 ; @0021D
    mov [0x8],al ; @0021F
    mov dx,[0xe] ; @00222
pcspeaker_loc_0226:
    mov [0xc],dx ; @00226
    ror byte [0x15],1 ; @0022A
    jc pcspeaker_loc_0232 ; @0022E
    db 0x8b,0xca ; ENCODED: mov cx,dx (NASM selects different opcode/operand width) ; @00230
pcspeaker_loc_0232:
    cmp [0x1a],cx ; @00232
    jz pcspeaker_loc_0248 ; @00236
    mov al,0xb6 ; @00238
    out 0x43,al ; @0023A
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM selects different opcode/operand width) ; @0023C
    out 0x42,al ; @0023E
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM selects different opcode/operand width) ; @00240
    out 0x42,al ; @00242
    mov [0x1a],cx ; @00244
pcspeaker_loc_0248:
    in al,0x61 ; @00248
    or al,0x3 ; @0024A
    out 0x61,al ; @0024C
    ret ; @0024E
; Stop clears active only. Main stop/tick pairs perform the later PIT update;
; this body neither disables gate61 nor writes a divisor.
pcspeaker_Stop:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM selects different opcode/operand width) ; @0024F
    mov [0x1],al ; @00251
    ret ; @00254
; UNKNOWN:0255..02F5 code-like fragments;no established entry/frame/provenance.
; RawAL25..2F copies these bytes,but that does not prove stored record/code role.
    db 0x90,0x6b,0x83,0xc4,0x06,0x0b,0xd0,0x74,0x18,0xff,0x06,0x40,0x07,0x8b,0x46,0x04 ; @00255
; UNKNOWN: unresolved bytes
    db 0x40,0x50,0xb8,0xe8,0x07,0x50,0xe8,0xd8,0x9e,0x83,0xc4,0x04,0x8b,0xe5,0x5d,0xc3 ; @00265
; UNKNOWN: unresolved bytes
    db 0x90,0x2b,0xc0,0x50,0xb8,0x07,0x00,0x50,0xff,0x76,0x04,0xe8,0x0d,0x6b,0x83,0xc4 ; @00275
; UNKNOWN: unresolved bytes
    db 0x06,0x89,0x46,0xfc,0x89,0x56,0xfe,0x0b,0xd0,0x75,0x17,0xb8,0xff,0xff,0x50,0xb8 ; @00285
; UNKNOWN: unresolved bytes
    db 0x03,0x00,0x50,0xff,0x76,0x04,0xe8,0xf2,0x6a,0x83,0xc4,0x06,0x89,0x46,0xfc,0x89 ; @00295
; UNKNOWN: unresolved bytes
    db 0x56,0xfe,0xc4,0x5e,0xfc,0x26,0xc6,0x47,0x04,0x03,0x8b,0x46,0x08,0x26,0x89,0x47 ; @002A5
; UNKNOWN: unresolved bytes
    db 0x06,0x8b,0x46,0x0a,0x26,0x89,0x47,0x08,0x8a,0x46,0x06,0x26,0x88,0x47,0x05,0xff ; @002B5
; UNKNOWN: unresolved bytes
    db 0x06,0x98,0x07,0x26,0xc6,0x47,0x0a,0xff,0x80,0x3e,0x36,0x08,0x00,0x74,0x16,0x8b ; @002C5
; UNKNOWN: unresolved bytes
    db 0x5e,0x04,0x8a,0x07,0x2a,0xe4,0x50,0x2b,0xc0,0x50,0xff,0x36,0x60,0x27,0xff,0x36 ; @002D5
; UNKNOWN: unresolved bytes
    db 0x5e,0x27,0xe8,0x32,0x0b,0x8b,0xe5,0x5d,0xc3,0x55,0x8b,0xec,0xff,0x76,0x06,0xff ; @002E5
; UNKNOWN: unresolved bytes
    db 0x76 ; @002F5

sub_2EC0 equ ApplyEntityCellInteractions
sub_2E04 equ AdvanceEntityCountdown
loc_2E5E equ EntityCountdownSoundReturn
loc_2EB2 equ EntityCountdownMaskedSoundReturn
; Maintained image span 01F19..0368D; reconstruction module, not a historical linker claim.
; Mixed ownership remains provisional; UNKNOWN bytes and overlay storage keep their classifications.
AdvanceEntityRecords:
; RECORD LIFETIME / WRITER CONTRACT (static, all offsets below hex).
; These are observed roles in one live 2Dh slot, not a historical C struct.
; Canonical DS is relocated09A9; none of 1F19..3633 loads/restores DS itself.
; Child CALLs/INT60/INT61 and live SS saves must preserve the cursor/frame for
; the ordinary-array interpretation. Returned DS/SI are otherwise used as-is.
; Startup0031 and per-level455B clear DS globals/record storage only with DF=0:
; 0000..2011 and0000..0FC9 respectively. 03E7 does not clear records;0462 calls
; 0FB2 to reinstall nine callback slots after the per-level clear, before046B
; reads the level header. 36CD takes only header+03 into byte0047;0404's C8 is
; provisional and4013 can replace0047 with current0043 to stop further creation.
; Direct decoded0043 writer:314B INC, besides those bulk clears. Deactivation
; does not decrement0043 or free a slot. 30A6 appends, never searches for FF.
; Reuse on the known normal level-start path is the455B reset, not compaction
; or an inactive-slot free list. No decoded whole-2Dh clone/copy was found.
; 378A copies different1Ch object-graphics records at17CB;389F copies coordinate
; pairs at0E98;283B copies nine interaction bytes to SS, not another entity.
; These are scoped observations of decoded code, not exclusion of UNKNOWN code.
;
; With stable counters/cursors, byte bound n walks[0088,0088+2D*n), including
; +26==FF slots. n<=FF gives a numeric end2D5B, not an allocated entity extent.
; Creation can select indexFF (2D5B..2D87) before INC0043 wraps to00. Equality
; with0047, rather than an unsigned limit test, is its sole count stop. A fresh
; zero bound and stable limit L append indices0..L-1 without count wrap. The
; pinned120-entry order selects headers with L<=50h (80 decimal), including
; the40 selected odd overrides; the other40 odd rows contain0063h (99).
; This is a complete-read/DF0/intact-order asset bound, not a constructor check.
; Indices00..4F fit0088..0E97. Index50 starts0E98, overwriting spawn-coordinate
; storage BEFORE3100 reads it; its callback0EAC also lies in the410F visibility
; clear. Larger slots overlap visibility, loaded level, object and other data.
; Thus50h is a disjoint-prefix condition, never a clamp or inferred allocation.
; IRQ LIMIT RACE:1874 calls3E6F, whose4010/4013 snapshots0043 into0047.
; If that IRQ occurs after30D5 passes but before314B, the pending constructor
; still publishes B+1 after the IRQ installed limit B. Creation never tests
; 004B (the scan request), nor rechecks0047 before publishing. The next due
; call sees B+1!=B and appends again. At B=4F this permits index50 on the next
; due call despite a nominal header50. No CLI brackets this handoff. Thus
; L<=50 alone cannot prove count<=50 under unrestricted original IRQ timing;
; the prefix theorem also requires no such limit-write/publication race.
; The stale-limit window actually begins after30CC samples0047: an IRQ
; before30D3 still restores the old AL for comparison. After30D5 is the
; simplest witness; serialization must cover limit sampling through314B.
;
; Established field roles: width, initial producer, later writers, consumers.
; All fields start zero in30F3's explicit INC-DI clear (independent of DF).
; +00 W:30FB spawn X; movement/temp-save writers in states, read5DC6/5726/706F.
; +02 W:3100 spawn Y; state heights and live POP restores, read same parents.
; +04 W:312F=FFF8 drawing X bias; transition stores;5728/7072 and selection read.
; +06 W:3134=FFF6 drawing Y bias; transition stores;214B/5762/70ED read live.
; +08 W:310F OR0004 after clear; state/action/interaction RMW/replace;1F5E
;       first-match dispatch. No independent skill enum or exclusive-bit proof.
; +0A W:3113=0000 source cursor bias; transitions;70DF adds product low nibble.
; +0C W:3118=0A42 paragraph bias; transitions;70D6 adds shifted full product.
; +0E W:cleared;21E3=0,2A7B+=2;2A70 unchecked2698 pair cursor. DF=1 action5
;       saves also overwrite+0E..+0F; this is not permanently unused padding.
; +10 W:311D=005A frame stride; transitions;70BF/C2 unsigned full MUL.
; +12 W:3122=003C mask cursor bias; transitions;70E4 adds to source SI.
; +14 W:3140 reads live002E; word-store matrix below;365A compares live003C,
;       70F0 PUSHes target. Also byte-written by action5 with DF=1 (347F/3488).
; +16..1E B:clear, then action5 saves displaced SS cells with DF=0;283B restores
;       via three MOVSW/MOVSB pairs. DF=1 saves+16..0E instead; see3336 contract.
; +1F B:3262=08 observed store; no ordinary decoded consumer established here.
; +20 B:clear;2033/31E1=4F,2277=0,2E06 DEC wraps. Same byte is countdown at1F45
;       and strip selector at70F3/7118; do not create a second rendering field.
; +21 B:32F2=0C,271E DEC;2693 uses it as a phase limit. Not a lifetime bound.
; +22 B:2D4F/2E97=0F,2D71/2EB9 may clear; wider ownership not established here.
; +23 B:312B=03,transition resets,223A+=3;21B0/2250 use unsigned thresholds.
; +24 B:clear/310B/3147 AND01;32B3 replaces01;27DE OR80;1F54 overrides dispatch.
; +25 B:3107=0,356B=FF;21B0/355E/3E0E test it. Not another active marker.
; +26 B:clear activates only when the bound includes the slot.20E2/22EE/2339/
;       2FD1 writeFF, without erasing callback/coordinates or removing the slot.
;       1F3C/3647/3D1E skip exactFF only. No decoded field-level reactivation.
; +27 B:3103=01;NEG at2142/215F/2763/29C1/2CBB/2FA8/2FB2,25D6 writes NEG AL,
;       2273=0. Signed X delta and exact01 frame-add gate70A5 are the SAME byte.
; +28 B:3127=0; state cadences and transitions;70A2 reads frame,365F signed>=1
;       selects point drawing only when+14 equals live003C. No global frame bound.
; +29 B:3139=04; transitions replace;70AB byte addition wraps before AH clear.
; +2A B:3143=00; transitions set00/FF;70B0 exactFF suppresses eight-way scaling.
; +2B/+2C B:2EFC/2EEA save second/first SS interaction samples;actions inspect
;       nibbles. Their order and alias with saved first AX at2EFF are observable.
;
; CALLBACK PRODUCER MATRIX: physical stores in each handler, then DS source slot.
; A dash means no direct+14 store in that handler, not absence of child/alias writes.
; Dispatch first tests+26, countdown, bit80 of+24, then state bits in1F68 order.
; Entry/state       +14 stores (all are live slot reads, not target literals)
; 2047 zero        20CB:002E,21A2:0030
; 21B0 0004        21F4:003A,2282:002E,22D1:002E
; 22DF 0001        - (22EE deactivates)
; 22F5 1000        - (expiry JMP20E2)
; 2326 2000        - (2339 deactivates after INC0046)
; 2340 4000        - (expiry JMP20E2)
; 2350 0002        - (may CALL283B; expiry JMP20E2)
; 23BF 0008        - (Y/frame/bit0008 changes preserve descriptor otherwise)
; 23F3 0010        2483:002E,24FE:002E
; 254F 0020        25C6:002E;260D transition to0040 PRESERVES callback/+2A
; 2637 0040        2682:002E
; 2693 0080        2794:002E,27D3:002E
; 27E8 0100        282A:002E,then CALL283B
; 287D 0200        292C:002E,29AE:002E,29F2:002E
; 2A6D 0400        2B1A:002E
; 2B35 0800        2BCE:002E,2C63:002E,2CEC:002E
; 2D0F 8000        2D48:003C
; 2DB5 +24 bit80   2DF2:002E
; 2E04 countdown   2E40:002E,2E90:003C (only expiry replaces the descriptor)
; 2EC0 cells       2F70:0032,3030:002E,3087:003E;2FD1 deactivates
; 30A6 creation    3140:002E,after complete2Dh clear, before bound INC
; 3150 actions     325F:0038,3315:0036,3459:002E,3536:0034,360B:0036
;                 selectors2/3/4 preserve callback; action5 DF=1 overrides3459.
; Other drawing-field writers by physical handler (union of explicit DS:SI
; stores, not a claim that every branch writes the union; shared tails/children
; retain their own effects). D={04,06,0A,0C,10,12,28,29,2A};+14 is above.
; 2047:D,00,02,27,26   21B0:D,02,20,27   22DF:28,26   22F5:00,28
; 2326:28,26           2340:28           2350:28      23BF:02,28
; 23F3:D,00,02         254F:D,00,02,27   2637:D,02   2693:D,00,02,27
; 27E8:D               287D:D,00,02,27   2A6D:D,02   2B35:D,00,02,27
; 2D0F:D               2DB5:D           2E04:D,20   2EC0:D,26,27
; 30A6:all2D bytes clear,then D,00,02,27; actions:see entity_actions.asm.
; 2148 shared clamp writes02/27;20D6 writes02;20E2 writes26. 260D changes
; 0A/0C/10/12/28/29 without writing04/06/14/2A, so state alone cannot supply
; a complete drawing descriptor. Cadences update28 without rebuilding geometry.
; Under canonical relocated DS09A9 / SS143E, the SS64K window startsA950 above
; DS:0000, disjoint from byte-indexed slots through2D87 and slots002E..003F.
; This excludes direct SS-map-to-record aliases in that machine domain only;
; map writes can still corrupt SS saves/RET and thereby change later DS/SI.
; Alternate SS, returned segments, resource/VGA/provider aliases remain separate.
; Source002E/30/32/34/36/38/3A/3C/3E is initialized at0FC1..0FF1 to
; 6170/64D9/65D8/66D7/6817/6957/6A97/6BDB/6CFC respectively.
; Word stores preserve this nine-value domain only with stable initialized slots,
; genuine record cursors, nonaliasing child/map/stack/device writes and intact
; code. The creation clear transiently makes+14=0 AND+26=0 before publication;
; no known foreground draw intervenes, but general IRQ/reentrant entry is unproved.
; DF=1 action5, view-map clears, count spill and writable SS target saves are
; concrete exclusions; see3336/3634/706F. READINESS: CONDITIONAL for this explicit
; producer/preservation domain. NOT a complete715B target-domain certificate.
; Partial record schema is anchored in image_tail.asm and the symbol ledger.
; One DS record owns both simulation and sprite roles: +20 is countdown AND
; strip selector; +27 is signed horizontal step AND frame-add gate; +26==FF
; skips both update and drawing. Do not split these into independent host fields.
; +08 is a bit word with first-match priority, not an exclusive skill enum.
; Creation clears one2D-byte slot then initializes state0004. Transitions replace
; callback/source/frame roles in place; no snapshot or whole-array bound exists.
; Simulation ownership contract (docs/entity-simulation.md): DS remains live.
; [0043] bounds slots, including inactive records; [0042] is the live pass
; counter. SI starts0088 and advances2D. No array extent is established.
; Each visited slot PUSHes ES; only the shared1FEB tail POPs the live word.
; Dispatch on +08 is first-match, not an independent set of Boolean handlers.
; Actual child RETs are1F26/1F4F; outer RETs2004/203B/2046 stay distinct.
; Gate FF and zero slot bound bypass scan. Countdown zero dispatches directly;
; a nonzero countdown uses the child's returned ZF and live DS/SI/SS:SP.
    cmp byte [EntityUpdateGate-GameDataImage],0xff ; @01F19
    jnz loc_1F23 ; @01F1E
    jmp loc_1FFF ; @01F20
loc_1F23:
    call ConfigureEntityPixelReadback ; @01F23
EntityUpdateAfterReadbackCall:
    mov byte [EntityWorkGuard-GameDataImage],0xff ; @01F26
    mov si,EntityRecordsBase-GameDataImage ; @01F2B
    mov al,[EntitySlotBound-GameDataImage] ; @01F2E
    mov [EntitySlotsRemaining-GameDataImage],al ; @01F31
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @01F34
    jnz loc_1F3B ; @01F36
    jmp loc_1FFF ; @01F38
loc_1F3B:
    push es ; @01F3B
    cmp byte [si+EntityRecordInactiveMarker-EntityRecordsBase],0xff ; @01F3C
    jnz loc_1F45 ; @01F40
    jmp loc_1FEB ; @01F42
loc_1F45:
    mov al,[si+EntityRecordCountdown-EntityRecordsBase] ; @01F45
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @01F48
    jz loc_1F54 ; @01F4A
    call AdvanceEntityCountdown ; @01F4C
EntityUpdateAfterCountdownCall:
    jnz loc_1F54 ; @01F4F
    jmp loc_1FEB ; @01F51
loc_1F54:
    mov al,[si+EntityRecordBehaviorFlags-EntityRecordsBase] ; @01F54
    test al,0x80 ; @01F57
    jz loc_1F5E ; @01F59
    jmp AdvanceEntityFlag80Override ; @01F5B
loc_1F5E:
    mov ax,[si+EntityRecordStateBits-EntityRecordsBase] ; @01F5E
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @01F61
    jnz loc_1F68 ; @01F63
    jmp loc_2047 ; @01F65
loc_1F68:
    test ax,0x2 ; @01F68
    jz loc_1F70 ; @01F6B
    jmp loc_2350 ; @01F6D
loc_1F70:
    test ax,0x8000 ; @01F70
    jz loc_1F78 ; @01F73
    jmp AdvanceEntityState8000 ; @01F75
loc_1F78:
    test ax,0x4 ; @01F78
    jz loc_1F80 ; @01F7B
    jmp loc_21B0 ; @01F7D
loc_1F80:
    test ax,0x400 ; @01F80
    jz loc_1F88 ; @01F83
    jmp AdvanceEntityState0400 ; @01F85
loc_1F88:
    test ax,0x1 ; @01F88
    jz loc_1F90 ; @01F8B
    jmp loc_22DF ; @01F8D
loc_1F90:
    test ax,0x8 ; @01F90
    jz loc_1F98 ; @01F93
    jmp loc_23BF ; @01F95
loc_1F98:
    test ax,0x10 ; @01F98
    jz loc_1FA0 ; @01F9B
    jmp loc_23F3 ; @01F9D
loc_1FA0:
    test ax,0x20 ; @01FA0
    jz loc_1FA8 ; @01FA3
    jmp loc_254F ; @01FA5
loc_1FA8:
    test ax,0x40 ; @01FA8
    jz loc_1FB0 ; @01FAB
    jmp loc_2637 ; @01FAD
loc_1FB0:
    test ax,0x80 ; @01FB0
    jz loc_1FB8 ; @01FB3
    jmp AdvanceEntityState0080 ; @01FB5
loc_1FB8:
    test ax,0x100 ; @01FB8
    jz loc_1FC0 ; @01FBB
    jmp AdvanceEntityState0100 ; @01FBD
loc_1FC0:
    test ax,0x200 ; @01FC0
    jz loc_1FC8 ; @01FC3
    jmp AdvanceEntityState0200 ; @01FC5
loc_1FC8:
    test ax,0x800 ; @01FC8
    jz loc_1FD0 ; @01FCB
    jmp AdvanceEntityState0800 ; @01FCD
loc_1FD0:
    test ax,0x1000 ; @01FD0
    jz loc_1FD8 ; @01FD3
    jmp loc_22F5 ; @01FD5
loc_1FD8:
    test ax,0x2000 ; @01FD8
    jz loc_1FE0 ; @01FDB
    jmp loc_2326 ; @01FDD
loc_1FE0:
; AX remains the nonzero1F5E load. All prior one-bit tests plus4000 coverFFFF;
; taken1FE3-to1FE8 is infeasible on this direct path. Shared1FE8 remains live
; through state JMPs; this local proof does not classify any bytes as dead.
    test ax,0x4000 ; @01FE0
    jz loc_1FE8 ; @01FE3
    jmp loc_2340 ; @01FE5
FinishEntityInteractions:
loc_1FE8:
; Shared JMP entry: CALL frame is real SS:SP, returning through live word1FEB.
; The child may change DS/SI/CX/CS/SS/SP; preserve its explicit sound seams.
    call sub_2EC0 ; @01FE8
EntityIterationTail:
loc_1FEB:
; No new frame: consume the per-record ES save, then update live SI/DS:[0042].
    pop es ; @01FEB
    add si,byte +0x2d ; @01FEC
    dec byte [EntitySlotsRemaining-GameDataImage] ; @01FEF
    jz loc_1FF8 ; @01FF3
    jmp loc_1F3B ; @01FF5
loc_1FF8:
    cmp byte [EntityScanRequest-GameDataImage],0x0 ; @01FF8
    jnz loc_2005 ; @01FFD
loc_1FFF:
    mov byte [EntityWorkGuard-GameDataImage],0x0 ; @01FFF
EntityUpdateOrdinaryReturn:
    ret ; @02004
loc_2005:
    mov al,[EntityScanCursor-GameDataImage] ; @02005
    cmp al,[EntitySlotBound-GameDataImage] ; @02008
    jz loc_203C ; @0200C
    mov cx,0x2d ; @0200E
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @02011
    mul cx ; @02013
    add ax,0x88 ; @02015
    db 0x8b,0xf0 ; ENCODED: mov si,ax (NASM chooses a different encoding) ; @02018
    cmp byte [si+EntityRecordCountdown-EntityRecordsBase],0x0 ; @0201A
    jnz loc_2037 ; @0201E
    cmp byte [si+EntityRecordInactiveMarker-EntityRecordsBase],0xff ; @02020
    jnz loc_202C ; @02024
    inc byte [EntityScanCursor-GameDataImage] ; @02026
    jmp short loc_2005 ; @0202A
loc_202C:
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x3 ; @0202C
    jnz loc_2037 ; @02031
    mov byte [si+EntityRecordCountdown-EntityRecordsBase],0x4f ; @02033
loc_2037:
    inc byte [EntityScanCursor-GameDataImage] ; @02037
EntityUpdateScanCandidateReturn:
; Nonzero countdown, occupied low state bits or a new+20=4F candidate all
; return here after cursor INC, leaving the work guard and scan request live.
    ret ; @0203B
loc_203C:
    mov byte [EntityScanRequest-GameDataImage],0x0 ; @0203C
    mov byte [EntityWorkGuard-GameDataImage],0x0 ; @02041
EntityUpdateScanExhaustedReturn:
    ret ; @02046
AdvanceEntityZeroState:
loc_2047:
; JMP entry from1F65 after +08==0; no independent near RET.
; +28 increments modulo8; signed +27 adds to X, then signed[0010,0680)
; bounds select NEG+27 or actual CALL5DC6/RET206B. All row-pitch and
; record reads remain live. Shared20D6/20E2/2148 tails also serve peer states.
; C owns2047..20D5,20E9..2147,2169..21AF; tails have separate ownership.
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02047
    inc al ; @0204A
    and al,0x7 ; @0204C
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @0204E
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02051
    cbw ; @02054
    add [si+EntityRecordX-EntityRecordsBase],ax ; @02055
    cmp word [si+EntityRecordX-EntityRecordsBase],byte +0x10 ; @02057
    jnl loc_205F ; @0205A
    jmp loc_2142 ; @0205C
loc_205F:
    cmp word [si+EntityRecordX-EntityRecordsBase],0x680 ; @0205F
    jl loc_2068 ; @02063
    jmp loc_2142 ; @02065
loc_2068:
    call PrepareEntityPixelSample ; @02068
EntityZeroStateAfterPixelCall:
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @0206B
    mov al,[es:di] ; @0206E
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02071
    jnz loc_20E9 ; @02073
    inc bp ; @02075
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @02076
    mov al,[es:di] ; @0207A
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0207D
    jnz loc_20D6 ; @0207F
    inc bp ; @02081
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @02082
    mov al,[es:di] ; @02086
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02089
    jnz loc_20D6 ; @0208B
    inc bp ; @0208D
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @0208E
    mov al,[es:di] ; @02092
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02095
    jnz loc_20D6 ; @02097
    inc bp ; @02099
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x4 ; @0209A
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @0209E
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xa42 ; @020A3
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @020A8
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @020AD
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @020B2
    mov byte [si+0x23],0x3 ; @020B6
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @020BA
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @020BF
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x4 ; @020C4
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @020C8
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @020CB
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @020CE
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @020D2
StoreEntityProbeHeight:
loc_20D6:
; Shared JMP entry with BP=candidate Y. Store first, then signed compare B4.
; Peer entries:2D90/2D9F/2DAE/2DB2. No CALL frame around this continuation.
    mov [si+EntityRecordY-EntityRecordsBase],bp ; @020D6
    cmp bp,0xb4 ; @020D9
    jnl loc_20E2 ; @020DD
    jmp loc_1FE8 ; @020DF
MarkEntityInactive:
loc_20E2:
; Direct peer JMPs skip20D6 store/CMP; preserve incoming registers/FLAGS.
; +26=FF keeps the slot in [0043]'s bound and skips interactions this pass.
    mov byte [si+EntityRecordInactiveMarker-EntityRecordsBase],0xff ; @020E2
    jmp loc_1FEB ; @020E6
loc_20E9:
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @020E9
    mov al,[es:di] ; @020ED
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @020F0
    jz loc_2148 ; @020F2
    dec bp ; @020F4
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @020F5
    mov al,[es:di] ; @020F9
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @020FC
    jz loc_2148 ; @020FE
    dec bp ; @02100
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @02101
    mov al,[es:di] ; @02105
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02108
    jz loc_2148 ; @0210A
    dec bp ; @0210C
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @0210D
    mov al,[es:di] ; @02111
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02114
    jz loc_2169 ; @02116
    dec bp ; @02118
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @02119
    mov al,[es:di] ; @0211D
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02120
    jz loc_2169 ; @02122
    dec bp ; @02124
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @02125
    mov al,[es:di] ; @02129
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0212C
    jz loc_2169 ; @0212E
    dec bp ; @02130
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @02131
    mov al,[es:di] ; @02135
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02138
    jz loc_2169 ; @0213A
    test byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @0213C
    jnz loc_2179 ; @02140
loc_2142:
    neg byte [si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02142
    jmp loc_1FE8 ; @02145
FinishEntityStepHeight:
loc_2148:
; Shared JMP entry: store BP, add live +06, signed <=0A selects clamp.
; Clamp rereads +06 after BP=9, writes Y, NEGs +27 and clears state bit0008.
; Peer entries:23E1/23F0/2634/2651/2690/27A2/27E5. Continue via1FE8.
    mov [si+EntityRecordY-EntityRecordsBase],bp ; @02148
    add bp,[si+EntityRecordDrawingYBias-EntityRecordsBase] ; @0214B
    cmp bp,byte +0xa ; @0214E
    jng loc_2156 ; @02151
    jmp loc_1FE8 ; @02153
loc_2156:
    mov bp,0x9 ; @02156
    sub bp,[si+EntityRecordDrawingYBias-EntityRecordsBase] ; @02159
    mov [si+EntityRecordY-EntityRecordsBase],bp ; @0215C
    neg byte [si+EntityRecordHorizontalStep-EntityRecordsBase] ; @0215F
    and word [si+EntityRecordStateBits-EntityRecordsBase],byte -0x9 ; @02162
    jmp loc_1FE8 ; @02166
loc_2169:
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x8 ; @02169
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x8 ; @0216D
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @02171
    sub bp,byte +0x2 ; @02174
    jmp short loc_2148 ; @02177
loc_2179:
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02179
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @0217D
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x39a ; @02182
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x20 ; @02187
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x48 ; @0218B
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x30 ; @02190
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02195
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff4 ; @0219A
    mov ax,[DrawingCallbackSlots-GameDataImage+0x2] ; @0219F
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @021A2
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @021A5
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x8 ; @021A9
    jmp loc_1FE8 ; @021AD
AdvanceEntityState0004:
loc_21B0:
; State0004 JMP entry from1F7D; owns21B0..22DE (303 bytes/87 sites).
; +28 modulo4; +23<=10 and +25==0 are unsigned byte decisions.
; Real CALL5DC6 returns2205. Sample exhaustion uses signed BP versus B4;
; the first two20E2 exits skip the Y store, unlike the third exhaustion.
; Occupied sample stores Y before unsigned +23<=3C transition selection.
; Live callback/pitch/gate reads and optional INT61 frame remain explicit.
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @021B0
    inc al ; @021B3
    and al,0x3 ; @021B5
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @021B7
    cmp byte [si+0x23],0x10 ; @021BA
    jna loc_2202 ; @021BE
    cmp byte [si+0x25],0x0 ; @021C0
    jz loc_2202 ; @021C4
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x400 ; @021C6
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @021CB
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xbaa ; @021D0
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x80 ; @021D5
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x60 ; @021DA
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @021DF
    mov word [si+0xe],0x0 ; @021E3
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff0 ; @021E8
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x8 ; @021ED
    mov ax,[DrawingCallbackSlots-GameDataImage+0xc] ; @021F1
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @021F4
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @021F7
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @021FB
    jmp loc_1FE8 ; @021FF
loc_2202:
    call PrepareEntityPixelSample ; @02202
EntityState0004AfterPixelCall:
; Actual near RET target; shared20E2/1FE8 JMPs acquire no extra frames.
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @02205
    mov al,[es:di] ; @02208
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0220B
    jnz loc_224D ; @0220D
    inc bp ; @0220F
    cmp bp,0xb4 ; @02210
    jl loc_2219 ; @02214
    jmp loc_20E2 ; @02216
loc_2219:
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @02219
    mov al,[es:di] ; @0221D
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02220
    jnz loc_224D ; @02222
    inc bp ; @02224
    cmp bp,0xb4 ; @02225
    jl loc_222E ; @02229
    jmp loc_20E2 ; @0222B
loc_222E:
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @0222E
    mov al,[es:di] ; @02232
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02235
    jnz loc_224D ; @02237
    inc bp ; @02239
    add byte [si+0x23],0x3 ; @0223A
    mov [si+EntityRecordY-EntityRecordsBase],bp ; @0223E
    cmp bp,0xb4 ; @02241
    jnl loc_224A ; @02245
    jmp loc_1FE8 ; @02247
loc_224A:
    jmp loc_20E2 ; @0224A
loc_224D:
    mov [si+EntityRecordY-EntityRecordsBase],bp ; @0224D
    cmp byte [si+0x23],0x3c ; @02250
    jna loc_22A3 ; @02254
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x1 ; @02256
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @0225B
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xc2a ; @02260
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02265
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @0226A
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @0226F
    mov byte [si+EntityRecordHorizontalStep-EntityRecordsBase],0x0 ; @02273
    mov byte [si+EntityRecordCountdown-EntityRecordsBase],0x0 ; @02277
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x0 ; @0227B
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @0227F
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02282
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02285
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02289
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @0228D
    jnz loc_22A0 ; @02292
    test byte [SoundOptionBits-GameDataImage],0x3 ; @02294
    jz loc_22A0 ; @02299
    mov ax,0x408 ; @0229B
    int 0x61 ; @0229E
EntityState0004AfterSound:
loc_22A0:
; Only a matching live INT61 CS:IP resumes here; DS/AX/FLAGS flow onward.
    jmp loc_1FE8 ; @022A0
loc_22A3:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @022A3
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @022A8
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @022AD
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @022B2
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @022B7
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @022BC
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @022C0
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @022C5
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @022CA
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @022CE
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @022D1
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @022D4
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @022D8
    jmp loc_1FE8 ; @022DC
AdvanceEntityState0001:
loc_22DF:
; State0001 JMP entry: +28 modulo16; zero marks +26 inline, then1FEB.
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @022DF
    inc al ; @022E2
    and al,0xf ; @022E4
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @022E6
    jz loc_22EE ; @022E9
    jmp loc_1FEB ; @022EB
loc_22EE:
    mov byte [si+EntityRecordInactiveMarker-EntityRecordsBase],0xff ; @022EE
    jmp loc_1FEB ; @022F2
AdvanceEntityState1000:
loc_22F5:
; State1000: +28 modulo16; zero JMP20E2. Otherwise PUSH signed +27,
; scale AX by8, sample at live X+offset/Y through actual CALL6141/RET2316.
; Then POP BX from live SS (not a cached delta), test pixel and conditionally
; ADD live X,BX with entry FLAGS on RMW writes. Continue1FEB; no local RET.
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @022F5
    inc al ; @022F8
    and al,0xf ; @022FA
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @022FC
    jz loc_2323 ; @022FF
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02301
    cbw ; @02304
    push ax ; @02305
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @02306
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @02308
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @0230A
    mov cx,[si+EntityRecordX-EntityRecordsBase] ; @0230C
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @0230E
    mov bx,[si+EntityRecordY-EntityRecordsBase] ; @02310
    call PrepareCoordinatePixelSample ; @02313
EntityState1000AfterPixelCall:
; Original caller's signed-delta save is consumed only after actual child RET.
    pop bx ; @02316
    mov al,[es:di] ; @02317
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0231A
    jnz loc_2320 ; @0231C
    add [si+EntityRecordX-EntityRecordsBase],bx ; @0231E
loc_2320:
    jmp loc_1FEB ; @02320
loc_2323:
    jmp loc_20E2 ; @02323
AdvanceEntityState2000:
loc_2326:
; State2000: +28 modulo8; zero INCs live DS0046 before marking +26 inline.
; The byte INC preserves CF; its resulting FLAGS reach the mark and1FEB.
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02326
    inc al ; @02329
    and al,0x7 ; @0232B
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @0232D
    jz loc_2335 ; @02330
    jmp loc_1FEB ; @02332
loc_2335:
    inc byte [EntityCompletionCounter-GameDataImage] ; @02335
    mov byte [si+EntityRecordInactiveMarker-EntityRecordsBase],0xff ; @02339
    jmp loc_1FEB ; @0233D
AdvanceEntityState4000:
loc_2340:
; State4000: memory INC +28, then fresh AL read and CMP0E; no modulo mask.
; RMW writes observe entry FLAGS. Equality JMPs20E2; otherwise1FEB.
    inc byte [si+EntityRecordFrameSelector-EntityRecordsBase] ; @02340
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02343
    cmp al,0xe ; @02346
    jnz loc_234D ; @02348
    jmp loc_20E2 ; @0234A
loc_234D:
    jmp loc_1FEB ; @0234D
; NORMAL POINT PREFIX:2D33/2E7B start frame0 and callback003C;2353 INC exposes1..33 before2358 expiry34->20E2. With042C count50,6E83 consumes2788..4767 only in stable producer domain.365F signed>=1 permits1..7F and raw6E83 permitsall bytes;not a global frame clamp or complete-array extent. Callback/record/provider writes retain wider behavior.
AdvanceEntityState0002:
loc_2350:
; State0002: INC the full +28 byte; equality34 marks inactive via20E2.
; Only the old zero value enters the first-frame work. Optional INT60 AX030C
; returns all live registers/segments before TEST [SI+8],0100 and CALL283B.
; After actual pattern RET, reread live DS:SI coordinates; SS owns the nibble
; map. Values9/5 skip drawing; other nibbles CALL5DF8 with its live bus effects.
; Actual child return words select continuation. No outer RET or interaction
; CALL is added here; normal exits JMP1FEB. UNKNOWN2382 remains unresolved.
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02350
    inc al ; @02353
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @02355
    cmp al,0x34 ; @02358
    jnz loc_235F ; @0235A
    jmp loc_20E2 ; @0235C
loc_235F:
    dec al ; @0235F
    jz loc_2366 ; @02361
    jmp loc_1FEB ; @02363
loc_2366:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @02366
    jz loc_2379 ; @0236B
    test byte [SoundOptionBits-GameDataImage],0x1 ; @0236D
    jz loc_2379 ; @02372
    mov ax,0x30c ; @02374
    int 0x60 ; @02377
EntityState0002AfterSound:
loc_2379:
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x100 ; @02379
    jnz loc_2383 ; @0237E
    jmp short loc_2386 ; @02380
; S14 U027: [02382,02383) stored bytes remain UNKNOWN.
; Neighbours: P 02380 jmp 0x2386; N 02383 call 0x283b.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @02382
loc_2383:
    call CopyEntityPatternToInteractionMap ; @02383
EntityState0002AfterPatternCall:
loc_2386:
    mov ax,[si+EntityRecordX-EntityRecordsBase] ; @02386
    mov bx,[si+EntityRecordY-EntityRecordsBase] ; @02388
    sub bx,byte +0x10 ; @0238B
    shr ax,1 ; @0238E
    shr ax,1 ; @02390
    shr bx,1 ; @02392
    shr bx,1 ; @02394
    push ax ; @02396
    push dx ; @02397
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02398
    mov dx,0x1a0 ; @0239A
    mul dx ; @0239D
    pop dx ; @0239F
    pop bx ; @023A0
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @023A1
    add bx,byte +0x12 ; @023A3
    mov al,[ss:bx] ; @023A6
    and al,0xf ; @023A9
    cmp al,0x9 ; @023AB
    jnz loc_23B2 ; @023AD
    jmp loc_1FEB ; @023AF
loc_23B2:
    cmp al,0x5 ; @023B2
    jnz loc_23B9 ; @023B4
    jmp loc_1FEB ; @023B6
loc_23B9:
    call DrawClippedEntityMask ; @023B9
EntityState0002AfterMaskCall:
    jmp loc_1FEB ; @023BC
AdvanceEntityState0008:
loc_23BF:
; State0008: actual CALL5DC6/RET23C2, then up to two upward probes.
; Each memory DEC sees entry FLAGS; each SUB rereads live DS0004 pitch.
; MOV AL replaces the old low byte before AND AL,AH. A clear sample resets
; state bit0008 and +28, then uses live Y+1; two set samples use live Y.
; Both paths JMP2148 with BP and the flowing DS/ES/SS/FLAGS, without a frame.
    call PrepareEntityPixelSample ; @023BF
EntityState0008AfterPixelCall:
    dec word [si+EntityRecordY-EntityRecordsBase] ; @023C2
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @023C5
    mov al,[es:di] ; @023C9
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @023CC
    jz loc_23E4 ; @023CE
    dec word [si+EntityRecordY-EntityRecordsBase] ; @023D0
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @023D3
    mov al,[es:di] ; @023D7
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @023DA
    jz loc_23E4 ; @023DC
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @023DE
    jmp loc_2148 ; @023E1
loc_23E4:
    and word [si+EntityRecordStateBits-EntityRecordsBase],byte -0x9 ; @023E4
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @023E8
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @023EC
    inc bp ; @023EF
    jmp loc_2148 ; @023F0
AdvanceEntityState0010:
loc_23F3:
; State0010: raw +28==11 takes the special pixel-exchange path before INC.
; Otherwise INC/AND0F admits only0/8 to240F. Both paths preserve actual
; 5DC6/5EBA CALL frames and subsequent live SS pops; 254C joins240F once.
; CX&7 bounds each SHR BX/RCR DL loop. RCR takes SHR's CF, defines CF/OF,
; and preserves SZP/AF; LOOP preserves FLAGS. Pixel exchange retains DF/IF,
; VGA mirror/port order, returned samples and the actual near RET word.
; Collision tests select ordered state stores or an unchecked SS map nibble.
; Nibble9 may request INT61 AX040A; only CS:24D0 resumes transition stores.
; DS callback002E is read after earlier stores. All exits are direct JMPs
; to1FEB,20E2 or1FE8; no outer frame is introduced by these state entries.
    cmp byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x11 ; @023F3
    jnz loc_23FC ; @023F7
    jmp loc_250C ; @023F9
loc_23FC:
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @023FC
    inc al ; @023FF
    and al,0xf ; @02401
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @02403
    jz loc_240F ; @02406
    cmp al,0x8 ; @02408
    jz loc_240F ; @0240A
    jmp loc_1FEB ; @0240C
loc_240F:
    mov bp,[si+EntityRecordX-EntityRecordsBase] ; @0240F
    mov ax,[si+EntityRecordDrawingXBias-EntityRecordsBase] ; @02411
    add [si+EntityRecordX-EntityRecordsBase],ax ; @02414
    push word [si+EntityRecordX-EntityRecordsBase] ; @02416
    call PrepareEntityPixelSample ; @02418
EntityState0010AfterFirstPixelCall:
    mov [si+EntityRecordX-EntityRecordsBase],bp ; @0241B
    inc word [si+EntityRecordY-EntityRecordsBase] ; @0241D
    pop cx ; @02420
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @02421
    cmp bp,0xb4 ; @02424
    jl loc_242D ; @02428
    jmp loc_20E2 ; @0242A
loc_242D:
    mov bx,0xff8 ; @0242D
    mov dl,0x0 ; @02430
    and cx,byte +0x7 ; @02432
    jz loc_243D ; @02435
loc_2437:
    shr bx,1 ; @02437
    rcr dl,1 ; @02439
    loop loc_2437 ; @0243B
loc_243D:
    db 0x8a,0xca ; ENCODED: mov cl,dl (NASM chooses a different encoding) ; @0243D
    push bx ; @0243F
    push cx ; @02440
    call ExchangeThreeEntityPixelBytes ; @02441
EntityState0010AfterFirstExchange:
    pop ax ; @02444
    pop dx ; @02445
    test dx,bx ; @02446
    jnz loc_2491 ; @02448
    test ax,cx ; @0244A
    jnz loc_2491 ; @0244C
    and word [si+EntityRecordStateBits-EntityRecordsBase],byte -0x11 ; @0244E
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x4 ; @02452
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02456
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xa42 ; @0245B
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02460
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02465
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @0246A
    mov byte [si+0x23],0x3 ; @0246E
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02472
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02477
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x4 ; @0247C
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02480
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02483
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02486
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @0248A
    jmp loc_1FE8 ; @0248E
loc_2491:
    mov ax,[si+EntityRecordX-EntityRecordsBase] ; @02491
    mov bx,[si+EntityRecordY-EntityRecordsBase] ; @02493
    sub bx,byte +0x10 ; @02496
    shr ax,1 ; @02499
    shr ax,1 ; @0249B
    shr bx,1 ; @0249D
    shr bx,1 ; @0249F
    push ax ; @024A1
    push dx ; @024A2
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @024A3
    mov dx,0x1a0 ; @024A5
    mul dx ; @024A8
    pop dx ; @024AA
    pop bx ; @024AB
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @024AC
    add bx,byte +0x12 ; @024AE
    mov al,[ss:bx] ; @024B1
    and al,0xf ; @024B4
    cmp al,0x9 ; @024B6
    jz loc_24BD ; @024B8
    jmp loc_1FE8 ; @024BA
loc_24BD:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @024BD
    jnz loc_24D0 ; @024C2
    test byte [SoundOptionBits-GameDataImage],0x3 ; @024C4
    jz loc_24D0 ; @024C9
    mov ax,0x40a ; @024CB
    int 0x61 ; @024CE
EntityState0010AfterSound:
loc_24D0:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @024D0
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @024D5
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @024DA
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @024DF
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @024E4
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @024E9
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @024ED
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @024F2
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @024F7
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @024FB
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @024FE
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02501
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02505
    jmp loc_1FE8 ; @02509
loc_250C:
    push word [si+EntityRecordX-EntityRecordsBase] ; @0250C
    push word [si+EntityRecordY-EntityRecordsBase] ; @0250E
    mov ax,[si+EntityRecordDrawingXBias-EntityRecordsBase] ; @02511
    add [si+EntityRecordX-EntityRecordsBase],ax ; @02514
    sub word [si+EntityRecordY-EntityRecordsBase],byte +0x2 ; @02516
    call PrepareEntityPixelSample ; @0251A
EntityState0010AfterSpecialPixelCall:
    mov cx,[si+EntityRecordX-EntityRecordsBase] ; @0251D
    pop word [si+EntityRecordY-EntityRecordsBase] ; @0251F
    pop word [si+EntityRecordX-EntityRecordsBase] ; @02522
    mov bx,0xff8 ; @02524
    mov dl,0x0 ; @02527
    and cx,byte +0x7 ; @02529
    jz loc_2534 ; @0252C
loc_252E:
    shr bx,1 ; @0252E
    rcr dl,1 ; @02530
    loop loc_252E ; @02532
loc_2534:
    db 0x8a,0xca ; ENCODED: mov cl,dl (NASM chooses a different encoding) ; @02534
    push di ; @02536
    push cx ; @02537
    push bx ; @02538
    push bp ; @02539
    call ExchangeThreeEntityPixelBytes ; @0253A
EntityState0010AfterSpecialFirstExchange:
    pop bp ; @0253D
    pop bx ; @0253E
    pop cx ; @0253F
    pop di ; @02540
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @02541
    call ExchangeThreeEntityPixelBytes ; @02545
EntityState0010AfterSpecialSecondExchange:
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02548
    jmp loc_240F ; @0254C
AdvanceEntityState0020:
loc_254F:
; State0020: register INC/AND7 stores +28 with post-AND FLAGS. Values0..3
; use the temporary Y-7-AL probe; values4..7 decrement Y and compare the
; wrapped Y+height with0A using unsigned JNA before the upward probe.
; Both 5DC6 calls consume their own actual RET, then restore live X or Y.
; The upper probe rereads DS0004 and shifts it three times; MOV AL replaces
; residual AL before AND AL,AH. Transition stores clear bit0020, retain
; literal field order, and read callback002E late on the state0004 path.
; The state0040 path leaves callback+14 untouched and JMPs2148 with live BP.
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @0254F
    inc al ; @02552
    and al,0x7 ; @02554
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @02556
    cmp al,0x3 ; @02559
    jg loc_2560 ; @0255B
    jmp loc_25E1 ; @0255D
loc_2560:
    dec word [si+EntityRecordY-EntityRecordsBase] ; @02560
    mov ax,[si+EntityRecordY-EntityRecordsBase] ; @02563
    add ax,[si+EntityRecordDrawingYBias-EntityRecordsBase] ; @02566
    cmp ax,0xa ; @02569
    jna loc_2591 ; @0256C
    mov bp,[si+EntityRecordX-EntityRecordsBase] ; @0256E
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02570
    cbw ; @02573
    sub [si+EntityRecordX-EntityRecordsBase],ax ; @02574
    call PrepareEntityPixelSample ; @02576
EntityState0020AfterFirstPixelCall:
    mov [si+EntityRecordX-EntityRecordsBase],bp ; @02579
    mov dx,[EntityPixelRowPitchBytes-GameDataImage] ; @0257B
    shl dx,1 ; @0257F
    shl dx,1 ; @02581
    shl dx,1 ; @02583
    db 0x2b,0xfa ; ENCODED: sub di,dx (NASM chooses a different encoding) ; @02585
    mov al,[es:di] ; @02587
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0258A
    jnz loc_2591 ; @0258C
    jmp loc_1FE8 ; @0258E
loc_2591:
    and word [si+EntityRecordStateBits-EntityRecordsBase],byte -0x21 ; @02591
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x4 ; @02595
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02599
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xa42 ; @0259E
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @025A3
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @025A8
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @025AD
    mov byte [si+0x23],0x3 ; @025B1
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @025B5
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @025BA
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x4 ; @025BF
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @025C3
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @025C6
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @025C9
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @025CD
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @025D1
    neg al ; @025D4
    mov [si+EntityRecordHorizontalStep-EntityRecordsBase],al ; @025D6
    cbw ; @025D9
    add [si+EntityRecordX-EntityRecordsBase],ax ; @025DA
    add [si+EntityRecordX-EntityRecordsBase],ax ; @025DC
    jmp loc_1FE8 ; @025DE
loc_25E1:
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @025E1
    sub word [si+EntityRecordY-EntityRecordsBase],byte +0x7 ; @025E4
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @025E8
    sub [si+EntityRecordY-EntityRecordsBase],ax ; @025EA
    call PrepareEntityPixelSample ; @025ED
EntityState0020AfterSecondPixelCall:
    mov [si+EntityRecordY-EntityRecordsBase],bp ; @025F0
    mov al,[es:di] ; @025F3
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @025F6
    jz loc_25FD ; @025F8
    jmp loc_1FE8 ; @025FA
loc_25FD:
    add word [si+EntityRecordY-EntityRecordsBase],byte +0x2 ; @025FD
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02601
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @02604
    sub [si+EntityRecordY-EntityRecordsBase],ax ; @02606
    and word [si+EntityRecordStateBits-EntityRecordsBase],byte -0x21 ; @02609
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x40 ; @0260D
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02611
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x6b2 ; @02616
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x48 ; @0261B
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x30 ; @02620
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02625
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x8 ; @02629
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @0262D
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @02631
    jmp loc_2148 ; @02634
AdvanceEntityState0040:
loc_2637:
; State0040: MOV AL/+28, INC AL, AND AL,7, then one store of AL.
; Zero performs ordered transition stores and a late DS002E callback read;
; values1..4 SUB Y,2 and reread BP; values5..7 JMP1FEB without a height step.
; The first two paths JMP2148 directly, carrying live DS/ES/SS and FLAGS.
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02637
    inc al ; @0263A
    and al,0x7 ; @0263C
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @0263E
    jz loc_2654 ; @02641
    cmp al,0x5 ; @02643
    jl loc_264A ; @02645
    jmp loc_1FEB ; @02647
loc_264A:
    sub word [si+EntityRecordY-EntityRecordsBase],byte +0x2 ; @0264A
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @0264E
    jmp loc_2148 ; @02651
loc_2654:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @02654
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02659
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @0265E
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02663
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02668
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @0266D
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02671
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02676
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @0267B
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @0267F
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02682
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02685
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02689
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @0268D
    jmp loc_2148 ; @02690
; State0080 from1FB5; known2693..27E7 bytes exclude four UNKNOWN singletons.
; PhaseA reads unsigned +21<=3, saves actual AX/ES, requests PC0313 then
; rereads the live DS gates for external0412. Both POPs use returned SS:SP.
; Phase9 CALLs5F0F. Zero phase uses three5DC6 frames, fresh pitch and live
; X/AX saves; +21 DEC wraps. Third clear/in-bounds Y+height<=0A transitions
; without NEG; failed samples/bounds NEG memory+27 with entry FLAGS observed.
; Ordered transitions read callback002E late and JMP2148 without a CALL frame.
AdvanceEntityState0080:
loc_2693:
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02693
    inc al ; @02696
    and al,0xf ; @02698
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @0269A
    jnz loc_26A2 ; @0269D
    jmp short loc_26E4 ; @0269F
; S14 U028: [026A1,026A2) stored bytes remain UNKNOWN.
; Neighbours: P 0269F jmp 0x26e4; N 026A2 cmp al, 0xa.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @026A1
loc_26A2:
    cmp al,0xa ; @026A2
    jnz loc_26D7 ; @026A4
    mov al,[si+0x21] ; @026A6
    cmp al,0x3 ; @026A9
    ja loc_26D7 ; @026AB
    push ax ; @026AD
    push es ; @026AE
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @026AF
    jz loc_26C2 ; @026B4
    test byte [SoundOptionBits-GameDataImage],0x1 ; @026B6
    jz loc_26C2 ; @026BB
    mov ax,0x313 ; @026BD
    int 0x60 ; @026C0
EntityState0080AfterPcSound:
loc_26C2:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @026C2
    jnz loc_26D5 ; @026C7
    test byte [SoundOptionBits-GameDataImage],0x3 ; @026C9
    jz loc_26D5 ; @026CE
    mov ax,0x412 ; @026D0
    int 0x61 ; @026D3
EntityState0080AfterExternalSound:
loc_26D5:
    pop es ; @026D5
    pop ax ; @026D6
loc_26D7:
    cmp al,0x9 ; @026D7
    jz loc_26DE ; @026D9
    jmp loc_1FE8 ; @026DB
loc_26DE:
    call DrawEntityStroke ; @026DE
EntityState0080AfterStrokeCall:
    jmp loc_1FEB ; @026E1
loc_26E4:
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @026E4
    cbw ; @026E7
    add [si+EntityRecordX-EntityRecordsBase],ax ; @026E8
    dec word [si+EntityRecordY-EntityRecordsBase] ; @026EA
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @026ED
    cmp word [si+EntityRecordX-EntityRecordsBase],byte +0x10 ; @026EF
    jg loc_26F7 ; @026F2
    jmp short loc_2763 ; @026F4
; S14 U029: [026F6,026F7) stored bytes remain UNKNOWN.
; Neighbours: P 026F4 jmp 0x2763; N 026F7 cmp word ptr [si], 0x680.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @026F6
loc_26F7:
    cmp word [si+EntityRecordX-EntityRecordsBase],0x680 ; @026F7
    jl loc_2700 ; @026FB
    jmp short loc_2763 ; @026FD
; S14 U030: [026FF,02700) stored bytes remain UNKNOWN.
; Neighbours: P 026FD jmp 0x2763; N 02700 call 0x5dc6.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @026FF
loc_2700:
    call PrepareEntityPixelSample ; @02700
EntityState0080AfterFirstPixelCall:
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @02703
    mov al,[es:di] ; @02707
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0270A
    jnz loc_2763 ; @0270C
    add [si+EntityRecordX-EntityRecordsBase],bp ; @0270E
    call PrepareEntityPixelSample ; @02710
EntityState0080AfterSecondPixelCall:
    sub di,[EntityPixelRowPitchBytes-GameDataImage] ; @02713
    mov al,[es:di] ; @02717
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @0271A
    jnz loc_2763 ; @0271C
    dec byte [si+0x21] ; @0271E
    jnz loc_2726 ; @02721
    jmp loc_27A5 ; @02723
loc_2726:
    push word [si+EntityRecordX-EntityRecordsBase] ; @02726
    add [si+EntityRecordX-EntityRecordsBase],bp ; @02728
    add [si+EntityRecordX-EntityRecordsBase],bp ; @0272A
    call PrepareEntityPixelSample ; @0272C
EntityState0080AfterThirdPixelCall:
    pop word [si+EntityRecordX-EntityRecordsBase] ; @0272F
    push ax ; @02731
    mov ax,[EntityPixelRowPitchBytes-GameDataImage] ; @02732
    db 0x2b,0xf8 ; ENCODED: sub di,ax (NASM chooses a different encoding) ; @02735
    shl ax,1 ; @02737
    shl ax,1 ; @02739
    shl ax,1 ; @0273B
    db 0x2b,0xf8 ; ENCODED: sub di,ax (NASM chooses a different encoding) ; @0273D
    pop ax ; @0273F
    mov al,[es:di] ; @02740
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02743
    jnz loc_2763 ; @02745
    cmp word [si+EntityRecordX-EntityRecordsBase],byte +0x10 ; @02747
    jng loc_2763 ; @0274A
    cmp word [si+EntityRecordX-EntityRecordsBase],0x680 ; @0274C
    jnl loc_2763 ; @02750
    mov ax,[si+EntityRecordY-EntityRecordsBase] ; @02752
    add ax,[si+EntityRecordDrawingYBias-EntityRecordsBase] ; @02755
    cmp ax,0xa ; @02758
    jng loc_2760 ; @0275B
    jmp loc_1FE8 ; @0275D
loc_2760:
    jmp short loc_2766 ; @02760
; S14 U031: [02762,02763) stored bytes remain UNKNOWN.
; Neighbours: P 02760 jmp 0x2766; N 02763 neg byte ptr [si + 0x27].
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @02762
loc_2763:
    neg byte [si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02763
loc_2766:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @02766
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @0276B
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @02770
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02775
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @0277A
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @0277F
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02783
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02788
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @0278D
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02791
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02794
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02797
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @0279B
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @0279F
    jmp loc_2148 ; @027A2
loc_27A5:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @027A5
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x8 ; @027AA
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x126b ; @027AF
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @027B4
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @027B9
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @027BE
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @027C2
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @027C7
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x8 ; @027CC
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @027D0
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @027D3
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @027D6
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @027DA
    or byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x80 ; @027DE
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @027E2
    jmp loc_2148 ; @027E5
; State0100 from1FBD. INC/AND are separate live memory RMWs. The actual
; pixel RET27F2 precedes the ES sample; clear samples perform ordered record
; writes and a late callback002E read, then actual pattern CALL/RET2838.
; Pattern restores DS/SS-backed saves through its own contract. Both exits
; JMP1FEB; this state does not run2148 or the interaction tail.
AdvanceEntityState0100:
loc_27E8:
    inc byte [si+EntityRecordFrameSelector-EntityRecordsBase] ; @027E8
    and byte [si+EntityRecordFrameSelector-EntityRecordsBase],0xf ; @027EB
    call PrepareEntityPixelSample ; @027EF
EntityState0100AfterPixelCall:
    mov al,[es:di] ; @027F2
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @027F5
    jz loc_27FC ; @027F7
    jmp loc_1FEB ; @027F9
loc_27FC:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @027FC
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02801
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @02806
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @0280B
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02810
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02815
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02819
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @0281E
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @02823
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02827
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @0282A
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @0282D
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02831
    call CopyEntityPatternToInteractionMap ; @02835
EntityState0100AfterPatternCall:
    jmp loc_1FEB ; @02838
; 283B..287C: copy the live record pattern back to the interaction map.
; DS:SI words +0/+2 feed wrapped (x-4)>>2 and (y-6-10h)>>2;
; MUL keeps its low word, map offset = 0012h + qx + 01A0h*qy.
; Producer 3464..34C7 saves old cells at record+16h while installing
; 02/0A/03 rows. Records advance 2Dh at 1FEC; no shadow pattern exists.
; PUSH/POP use live SS:SP: map writes may change restored ES/DI/SI/RET.
; Optional bus accesses retain instruction-phase FLAGS and live PUSH SS/POP ES;
; the destination segment is the popped value, including provider changes.
; Three MOVSW/MOVSB pairs retain DF and sequential overlap. Each literal
; 019Dh adjustment follows a pair; DF=1 is not a reversed 9-byte copy.
; This is a record-to-SS-map copy, not entity cloning. With DF=1 the source
; words start at+16,+13,+10 and bytes at+14,+11,+0E (word high bytes forward).
; Thus it also READS callback low+14/mask/stride/pair-index storage in that domain.
; Destination row starts advance019A, not01A0; map/record physical aliases may
; overwrite+14 or its live saves despite the lack of an explicit [SI+14] store.
; AX=low product, BX=map offset, DX=live restored save; CX/BP/DS/SS unchanged.
; Last defined arithmetic flags are ADD DI,019Dh at 2873. See entity-pattern.md.
CopyEntityPatternToInteractionMap:
sub_283B:
    mov ax,[si+EntityRecordX-EntityRecordsBase] ; @0283B
    mov bx,[si+EntityRecordY-EntityRecordsBase] ; @0283D
    sub ax,0x4 ; @02840
    sub bx,byte +0x6 ; @02843
    sub bx,byte +0x10 ; @02846
    shr ax,1 ; @02849
    shr ax,1 ; @0284B
    shr bx,1 ; @0284D
    shr bx,1 ; @0284F
    push ax ; @02851
    push dx ; @02852
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02853
    mov dx,0x1a0 ; @02855
    mul dx ; @02858
    pop dx ; @0285A
    pop bx ; @0285B
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0285C
    add bx,byte +0x12 ; @0285E
    push si ; @02861
    push di ; @02862
    push es ; @02863
    push ss ; @02864
    pop es ; @02865
    db 0x8b,0xfb ; ENCODED: mov di,bx (NASM chooses a different encoding) ; @02866
    add si,byte +0x16 ; @02868
; S19 DF-site census movsw word ptr es:[di], word ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    movsw ; @0286B
; S19 DF-site census movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    movsb ; @0286C
    add di,0x19d ; @0286D
; S19 DF-site census movsw word ptr es:[di], word ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    movsw ; @02871
; S19 DF-site census movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    movsb ; @02872
    add di,0x19d ; @02873
; S19 DF-site census movsw word ptr es:[di], word ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    movsw ; @02877
; S19 DF-site census movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    movsb ; @02878
    pop es ; @02879
    pop di ; @0287A
    pop si ; @0287B
    ret ; @0287C
; State0200 from1FC5, known287D..2A6C with no interior external direct entry.
; Separate memory cadence RMWs precede the raw phase rereads. Four coordinate
; CALLs preserve their actual restored CX/BX/DX; later probes use fresh pitch.
; The unchecked SS map nibble is read after actual AX/DX saves and restores.
; INT61 AX040A returns2A6A before NEG+27; its live DS effects flow onward.
; Transition callback002E is read late. Shared1FE8/1FEB exits are JMPs.
; Scoped native parent/child verification is recorded in entity-simulation.md.
AdvanceEntityState0200:
loc_287D:
    inc byte [si+EntityRecordFrameSelector-EntityRecordsBase] ; @0287D
    and byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x1f ; @02880
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02884
    and al,0xf ; @02887
    cmp al,0xb ; @02889
    jl loc_2890 ; @0288B
    jmp loc_293A ; @0288D
loc_2890:
    cmp al,0x2 ; @02890
    jnl loc_2897 ; @02892
    jmp loc_1FEB ; @02894
loc_2897:
    cmp al,0x5 ; @02897
    jng loc_289E ; @02899
    jmp loc_1FEB ; @0289B
loc_289E:
    sub al,0x2 ; @0289E
    cbw ; @028A0
    call DrawTenRowEntityMask ; @028A1
EntityState0200AfterMaskCall:
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @028A4
    cmp al,0x5 ; @028A7
    jz loc_28AE ; @028A9
    jmp loc_1FEB ; @028AB
loc_28AE:
    mov cx,[si+EntityRecordX-EntityRecordsBase] ; @028AE
    mov bx,[si+EntityRecordY-EntityRecordsBase] ; @028B0
    sub bx,byte +0x6 ; @028B3
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @028B6
    cbw ; @028B9
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @028BA
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @028BC
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @028BE
    db 0x03,0xc0 ; ENCODED: add ax,ax (NASM chooses a different encoding) ; @028C0
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @028C2
    call PrepareCoordinatePixelSample ; @028C4
EntityState0200AfterFirstCoordinateCall:
    mov al,[es:di] ; @028C7
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @028CA
    jz loc_28D1 ; @028CC
    jmp loc_1FEB ; @028CE
loc_28D1:
    db 0x03,0xcd ; ENCODED: add cx,bp (NASM chooses a different encoding) ; @028D1
    call PrepareCoordinatePixelSample ; @028D3
EntityState0200AfterSecondCoordinateCall:
    mov al,[es:di] ; @028D6
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @028D9
    jz loc_28E0 ; @028DB
    jmp loc_1FEB ; @028DD
loc_28E0:
    db 0x03,0xcd ; ENCODED: add cx,bp (NASM chooses a different encoding) ; @028E0
    call PrepareCoordinatePixelSample ; @028E2
EntityState0200AfterThirdCoordinateCall:
    mov al,[es:di] ; @028E5
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @028E8
    jz loc_28EF ; @028EA
    jmp loc_1FEB ; @028EC
loc_28EF:
    db 0x03,0xcd ; ENCODED: add cx,bp (NASM chooses a different encoding) ; @028EF
    call PrepareCoordinatePixelSample ; @028F1
EntityState0200AfterFourthCoordinateCall:
    mov al,[es:di] ; @028F4
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @028F7
    jz loc_28FE ; @028F9
    jmp loc_1FEB ; @028FB
loc_28FE:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @028FE
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02903
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @02908
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @0290D
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02912
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02917
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @0291B
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02920
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @02925
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02929
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @0292C
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @0292F
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02933
    jmp loc_1FEB ; @02937
loc_293A:
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @0293A
    cbw ; @0293D
    add [si+EntityRecordX-EntityRecordsBase],ax ; @0293E
    cmp word [si+EntityRecordX-EntityRecordsBase],byte +0x10 ; @02940
    jl loc_29C1 ; @02943
    cmp word [si+EntityRecordX-EntityRecordsBase],0x680 ; @02945
    jnl loc_29C1 ; @02949
    call PrepareEntityPixelSample ; @0294B
EntityState0200AfterPixelCall:
    mov al,[es:di] ; @0294E
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02951
    jz loc_2958 ; @02953
    jmp loc_2A00 ; @02955
loc_2958:
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02958
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @0295B
    mov al,[es:di] ; @0295F
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02962
    jz loc_2969 ; @02964
    jmp loc_2A00 ; @02966
loc_2969:
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02969
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @0296C
    mov al,[es:di] ; @02970
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02973
    jz loc_297A ; @02975
    jmp loc_2A00 ; @02977
loc_297A:
    inc word [si+EntityRecordY-EntityRecordsBase] ; @0297A
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x4 ; @0297D
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02981
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xa42 ; @02986
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @0298B
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02990
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02995
    mov byte [si+0x23],0x3 ; @02999
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @0299D
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @029A2
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x4 ; @029A7
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @029AB
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @029AE
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @029B1
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @029B5
    and word [si+EntityRecordStateBits-EntityRecordsBase],0xfdff ; @029B9
    jmp loc_1FE8 ; @029BE
loc_29C1:
    neg byte [si+EntityRecordHorizontalStep-EntityRecordsBase] ; @029C1
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @029C4
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @029C9
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @029CE
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @029D3
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @029D8
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @029DD
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @029E1
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @029E6
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @029EB
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @029EF
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @029F2
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @029F5
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @029F9
    jmp loc_1FE8 ; @029FD
loc_2A00:
    mov ax,[si+EntityRecordX-EntityRecordsBase] ; @02A00
    mov bx,[si+EntityRecordY-EntityRecordsBase] ; @02A02
    sub bx,byte +0x10 ; @02A05
    shr ax,1 ; @02A08
    shr ax,1 ; @02A0A
    shr bx,1 ; @02A0C
    shr bx,1 ; @02A0E
    push ax ; @02A10
    push dx ; @02A11
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02A12
    mov dx,0x1a0 ; @02A14
    mul dx ; @02A17
    pop dx ; @02A19
    pop bx ; @02A1A
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02A1B
    add bx,byte +0x12 ; @02A1D
    sub bx,0x340 ; @02A20
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02A24
    cbw ; @02A27
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02A28
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02A2A
    mov al,[ss:bx] ; @02A2C
    and al,0xf ; @02A2F
    cmp al,0x9 ; @02A31
    jz loc_2A57 ; @02A33
    cmp al,0x7 ; @02A35
    jnz loc_2A43 ; @02A37
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02A39
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02A3C
    jns loc_29C1 ; @02A3E
    jmp loc_1FE8 ; @02A40
loc_2A43:
    cmp al,0x8 ; @02A43
    jz loc_2A4A ; @02A45
    jmp loc_1FE8 ; @02A47
loc_2A4A:
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02A4A
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02A4D
    jns loc_2A54 ; @02A4F
    jmp loc_29C1 ; @02A51
loc_2A54:
    jmp loc_1FE8 ; @02A54
loc_2A57:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @02A57
    jnz loc_2A6A ; @02A5C
    test byte [SoundOptionBits-GameDataImage],0x3 ; @02A5E
    jz loc_2A6A ; @02A63
    mov ax,0x40a ; @02A65
    int 0x61 ; @02A68
EntityState0200AfterSound:
loc_2A6A:
    jmp loc_29C1 ; @02A6A
; S16 terminal is NOT a pair count:21E3 seeds+0E=0;2A7B adds2 modulo16 without sentinel. Frame store2A75 precedes second-byte read2A78,so record/table aliases are observable. Collision2AEC changes state;otherwise2B28 signedY>=B4 deactivates via20E2.21C6 leavesY unchanged. Candidate112 pairs gains221 decimal Y with stable nonwrapping no-collision state;Y0=-42 decimal reaches cursorE0/Y179 then reads2778 colors,Y0=-41 stops at112. Static conditional arithmetic only,not game reachability/native-domain expansion. No proven total pair extent;keep base size0.
; PAIR SCHEMA: DS2698+liveWord0E wraps;21E3=0,2A7B+=2.2A73->2A75 frame+28 store precedes2A78 signed Y/probe-action read, so a record/table alias can change the second byte. Candidate2698..2777 contains8 lead pairs then13 repetitions of8 pairs;112 is not a code bound. Height check2B28 and field initialization do not prove a total table extent;large records/GROUND/cache/aliases remain. See entity_points.asm and build/static/s7-tables.md; keep UNKNOWN extent.
; State0400 from1F85. Sparse known2A6D..2B34 excludes three UNKNOWN bytes.
; Pair index+0E is unchecked;21E3 initializes one observed path to zero.
; Store first pair byte to+28 before fetching the second, then ADD+0E,2.
; Second byte CBW dispatches3/2/1 probes or a signed direct Y addition.
; Clear probes INC live Y and reread pitch between samples; occupied probes
; keep prior increments and transition through a late callback002E read.
; Signed Y>=B4 JMPs20E2 without a height store; other finishes JMP1FE8.
; The pair base is named only as a reference: its extent and bytes stay UNKNOWN.
AdvanceEntityState0400:
loc_2A6D:
    mov bx,EntityState0400PairBase-GameDataImage ; @02A6D
    add bx,[si+0xe] ; @02A70
    mov al,[bx] ; @02A73
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @02A75
    mov al,[bx+0x1] ; @02A78
    add word [si+0xe],byte +0x2 ; @02A7B
    cbw ; @02A7F
    cmp al,0x3 ; @02A80
    jz loc_2A92 ; @02A82
    cmp al,0x2 ; @02A84
    jz loc_2ABE ; @02A86
    cmp al,0x1 ; @02A88
    jz loc_2ADC ; @02A8A
    add [si+EntityRecordY-EntityRecordsBase],ax ; @02A8C
    jmp loc_2B28 ; @02A8F
loc_2A92:
    call PrepareEntityPixelSample ; @02A92
EntityState0400AfterThreeProbePixelCall:
    mov al,[es:di] ; @02A95
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02A98
    jnz loc_2AEC ; @02A9A
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02A9C
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @02A9F
    mov al,[es:di] ; @02AA3
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AA6
    jnz loc_2AEC ; @02AA8
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02AAA
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @02AAD
    mov al,[es:di] ; @02AB1
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AB4
    jnz loc_2AEC ; @02AB6
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02AB8
    jmp short loc_2B28 ; @02ABB
; S14 U032: [02ABD,02ABE) stored bytes remain UNKNOWN.
; Neighbours: P 02ABB jmp 0x2b28; N 02ABE call 0x5dc6.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @02ABD
loc_2ABE:
    call PrepareEntityPixelSample ; @02ABE
EntityState0400AfterTwoProbePixelCall:
    mov al,[es:di] ; @02AC1
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AC4
    jnz loc_2AEC ; @02AC6
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02AC8
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @02ACB
    mov al,[es:di] ; @02ACF
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AD2
    jnz loc_2AEC ; @02AD4
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02AD6
    jmp short loc_2B28 ; @02AD9
; S14 U033: [02ADB,02ADC) stored bytes remain UNKNOWN.
; Neighbours: P 02AD9 jmp 0x2b28; N 02ADC call 0x5dc6.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @02ADB
loc_2ADC:
    call PrepareEntityPixelSample ; @02ADC
EntityState0400AfterOneProbePixelCall:
    mov al,[es:di] ; @02ADF
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02AE2
    jnz loc_2AEC ; @02AE4
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02AE6
    jmp short loc_2B28 ; @02AE9
; S14 U034: [02AEB,02AEC) stored bytes remain UNKNOWN.
; Neighbours: P 02AE9 jmp 0x2b28; N 02AEC mov word ptr [si + 8], 0.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @02AEB
loc_2AEC:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @02AEC
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02AF1
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @02AF6
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02AFB
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02B00
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02B05
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02B09
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02B0E
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @02B13
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02B17
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02B1A
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02B1D
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02B21
    jmp loc_1FE8 ; @02B25
loc_2B28:
    cmp word [si+EntityRecordY-EntityRecordsBase],0xb4 ; @02B28
    jnl loc_2B32 ; @02B2D
    jmp loc_1FE8 ; @02B2F
loc_2B32:
    jmp loc_20E2 ; @02B32
; State0800 from1FCD;473 known bytes/157 sites,UNKNOWN2B50 excluded.
; INC AL wraps as a byte; only exact AL18 resets to zero. Signed JL after
; CMP AL,3 admits updated1,2,80..FF:130 unchecked thirteen-row selectors
; after DEC/CBW. Actual mask RET2B63 and pixel RETs2B93/2C2B remain live.
; Cadence3/0F move X twice with signed bounds;3 also INCs Y before sampling.
; The SS nibble follows actual AX/DX saves. Nibble8 always reaches NEG+27,
; but its fresh direction read/AND flags survive same-target JNS2CB9.
; Optional INT61 AX040A returns2D0D; returned DS owns NEG and late callback.
AdvanceEntityState0800:
loc_2B35:
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02B35
    inc al ; @02B38
    cmp al,0x18 ; @02B3A
    jnz loc_2B40 ; @02B3C
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @02B3E
loc_2B40:
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @02B40
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02B43
    jnz loc_2B4A ; @02B45
    jmp loc_2BE1 ; @02B47
loc_2B4A:
    cmp al,0xf ; @02B4A
    jnz loc_2B51 ; @02B4C
    jmp short loc_2B66 ; @02B4E
; S14 U035: [02B50,02B51) stored bytes remain UNKNOWN.
; Neighbours: P 02B4E jmp 0x2b66; N 02B51 cmp al, 3.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @02B50
loc_2B51:
    cmp al,0x3 ; @02B51
    jnz loc_2B58 ; @02B53
    jmp loc_2BF1 ; @02B55
loc_2B58:
    jl loc_2B5D ; @02B58
    jmp loc_1FEB ; @02B5A
loc_2B5D:
    dec al ; @02B5D
    cbw ; @02B5F
    call DrawThirteenRowEntityMask ; @02B60
EntityState0800AfterMaskCall:
    jmp loc_1FEB ; @02B63
loc_2B66:
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02B66
    cbw ; @02B69
    add [si+EntityRecordX-EntityRecordsBase],ax ; @02B6A
    cmp word [si+EntityRecordX-EntityRecordsBase],byte +0x10 ; @02B6C
    jnl loc_2B74 ; @02B6F
    jmp loc_2CBB ; @02B71
loc_2B74:
    cmp word [si+EntityRecordX-EntityRecordsBase],0x680 ; @02B74
    jl loc_2B7D ; @02B78
    jmp loc_2CBB ; @02B7A
loc_2B7D:
    add [si+EntityRecordX-EntityRecordsBase],ax ; @02B7D
    cmp word [si+EntityRecordX-EntityRecordsBase],byte +0x10 ; @02B7F
    jnl loc_2B87 ; @02B82
    jmp loc_2CBB ; @02B84
loc_2B87:
    cmp word [si+EntityRecordX-EntityRecordsBase],0x680 ; @02B87
    jl loc_2B90 ; @02B8B
    jmp loc_2CBB ; @02B8D
loc_2B90:
    call PrepareEntityPixelSample ; @02B90
EntityState0800AfterFirstPixelCall:
    mov al,[es:di] ; @02B93
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02B96
    jz loc_2B9D ; @02B98
    jmp loc_2C76 ; @02B9A
loc_2B9D:
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x4 ; @02B9D
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02BA1
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xa42 ; @02BA6
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02BAB
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02BB0
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02BB5
    mov byte [si+0x23],0x3 ; @02BB9
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02BBD
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02BC2
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x4 ; @02BC7
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02BCB
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02BCE
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02BD1
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02BD5
    and word [si+EntityRecordStateBits-EntityRecordsBase],0xf7ff ; @02BD9
    jmp loc_1FE8 ; @02BDE
loc_2BE1:
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02BE1
    cmp word [si+EntityRecordY-EntityRecordsBase],0xb4 ; @02BE4
    jl loc_2BEE ; @02BE9
    jmp loc_20E2 ; @02BEB
loc_2BEE:
    jmp loc_1FE8 ; @02BEE
loc_2BF1:
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02BF1
    cbw ; @02BF4
    add [si+EntityRecordX-EntityRecordsBase],ax ; @02BF5
    cmp word [si+EntityRecordX-EntityRecordsBase],byte +0x10 ; @02BF7
    jnl loc_2BFF ; @02BFA
    jmp loc_2CBB ; @02BFC
loc_2BFF:
    cmp word [si+EntityRecordX-EntityRecordsBase],0x680 ; @02BFF
    jl loc_2C08 ; @02C03
    jmp loc_2CBB ; @02C05
loc_2C08:
    add [si+EntityRecordX-EntityRecordsBase],ax ; @02C08
    cmp word [si+EntityRecordX-EntityRecordsBase],byte +0x10 ; @02C0A
    jnl loc_2C12 ; @02C0D
    jmp loc_2CBB ; @02C0F
loc_2C12:
    cmp word [si+EntityRecordX-EntityRecordsBase],0x680 ; @02C12
    jl loc_2C1B ; @02C16
    jmp loc_2CBB ; @02C18
loc_2C1B:
    inc word [si+EntityRecordY-EntityRecordsBase] ; @02C1B
    cmp word [si+EntityRecordY-EntityRecordsBase],0xb4 ; @02C1E
    jl loc_2C28 ; @02C23
    jmp loc_20E2 ; @02C25
loc_2C28:
    call PrepareEntityPixelSample ; @02C28
EntityState0800AfterSecondPixelCall:
    mov al,[es:di] ; @02C2B
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02C2E
    jnz loc_2C76 ; @02C30
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x4 ; @02C32
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02C36
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xa42 ; @02C3B
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02C40
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02C45
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02C4A
    mov byte [si+0x23],0x3 ; @02C4E
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02C52
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02C57
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x4 ; @02C5C
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02C60
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02C63
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02C66
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02C6A
    and word [si+EntityRecordStateBits-EntityRecordsBase],0xf7ff ; @02C6E
    jmp loc_1FE8 ; @02C73
loc_2C76:
    mov ax,[si+EntityRecordX-EntityRecordsBase] ; @02C76
    mov bx,[si+EntityRecordY-EntityRecordsBase] ; @02C78
    sub bx,byte +0x10 ; @02C7B
    shr ax,1 ; @02C7E
    shr ax,1 ; @02C80
    shr bx,1 ; @02C82
    shr bx,1 ; @02C84
    push ax ; @02C86
    push dx ; @02C87
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02C88
    mov dx,0x1a0 ; @02C8A
    mul dx ; @02C8D
    pop dx ; @02C8F
    pop bx ; @02C90
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02C91
    add bx,byte +0x12 ; @02C93
    mov al,[ss:bx] ; @02C96
    and al,0xf ; @02C99
    cmp al,0x9 ; @02C9B
    jz loc_2CFA ; @02C9D
    cmp al,0x7 ; @02C9F
    jnz loc_2CAD ; @02CA1
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02CA3
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02CA6
    jns loc_2CBB ; @02CA8
    jmp loc_1FE8 ; @02CAA
loc_2CAD:
    cmp al,0x8 ; @02CAD
    jz loc_2CB4 ; @02CAF
    jmp loc_1FE8 ; @02CB1
loc_2CB4:
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02CB4
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02CB7
    jns loc_2CBB ; @02CB9
loc_2CBB:
    neg byte [si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02CBB
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @02CBE
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02CC3
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @02CC8
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02CCD
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02CD2
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02CD7
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02CDB
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02CE0
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @02CE5
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02CE9
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02CEC
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02CEF
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02CF3
    jmp loc_1FE8 ; @02CF7
loc_2CFA:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @02CFA
    jnz loc_2D0D ; @02CFF
    test byte [SoundOptionBits-GameDataImage],0x3 ; @02D01
    jz loc_2D0D ; @02D06
    mov ax,0x40a ; @02D08
    int 0x61 ; @02D0B
EntityState0800AfterSound:
loc_2D0D:
    jmp short loc_2CBB ; @02D0D
; State8000 from1F75:166 known bytes/53 sites. Register cadence modulo16;
; zero transitions through late slot003C and optional INT61 AX040C, then
; rereads live state bit0004 after the returned DS before deciding+22.
; Nonzero cadence5 reads live EntityScanRequest. JNZ2D81 has identical target
; and fallthrough; preserve the read/CMP/flags. Actual pixel RET2D86 precedes
; three samples; clear probes INC BP, then JMP20D6 stores the live height.
AdvanceEntityState8000:
loc_2D0F:
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02D0F
    inc al ; @02D12
    and al,0xf ; @02D14
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @02D16
    jnz loc_2D78 ; @02D19
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x2 ; @02D1B
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x8 ; @02D1F
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x180b ; @02D24
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x280 ; @02D29
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x1e0 ; @02D2E
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02D33
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xffe7 ; @02D37
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff0 ; @02D3C
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x0 ; @02D41
    mov ax,[DrawingCallbackSlots-GameDataImage+0xe] ; @02D45
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02D48
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02D4B
    mov byte [si+0x22],0xf ; @02D4F
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02D53
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @02D57
    jnz loc_2D6A ; @02D5C
    test byte [SoundOptionBits-GameDataImage],0x3 ; @02D5E
    jz loc_2D6A ; @02D63
    mov ax,0x40c ; @02D65
    int 0x61 ; @02D68
EntityState8000AfterSound:
loc_2D6A:
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x4 ; @02D6A
    jz loc_2D75 ; @02D6F
    mov byte [si+0x22],0x0 ; @02D71
loc_2D75:
    jmp loc_1FEB ; @02D75
loc_2D78:
    cmp al,0x5 ; @02D78
    jnz loc_2D83 ; @02D7A
    cmp byte [EntityScanRequest-GameDataImage],0xff ; @02D7C
    jnz loc_2D83 ; @02D81
loc_2D83:
    call PrepareEntityPixelSample ; @02D83
EntityState8000AfterPixelCall:
    mov bp,[si+EntityRecordY-EntityRecordsBase] ; @02D86
    mov al,[es:di] ; @02D89
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02D8C
    jz loc_2D93 ; @02D8E
    jmp loc_20D6 ; @02D90
loc_2D93:
    inc bp ; @02D93
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @02D94
    mov al,[es:di] ; @02D98
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02D9B
    jz loc_2DA2 ; @02D9D
    jmp loc_20D6 ; @02D9F
loc_2DA2:
    inc bp ; @02DA2
    add di,[EntityPixelRowPitchBytes-GameDataImage] ; @02DA3
    mov al,[es:di] ; @02DA7
    db 0x22,0xc4 ; ENCODED: and al,ah (NASM chooses a different encoding) ; @02DAA
    jz loc_2DB1 ; @02DAC
    jmp loc_20D6 ; @02DAE
loc_2DB1:
    inc bp ; @02DB1
    jmp loc_20D6 ; @02DB2
; +24 bit80 override from1F5B precedes state-word dispatch:79 known bytes/
; 21 sites. Register modulo8 cadence; zero performs ordered callback002E
; transition then separate memory AND+24,1 / AND+24,7F before JMP1FE8.
; Nonzero JMPs1FEB. No new frame is added for either original JMP tail.
AdvanceEntityFlag80Override:
loc_2DB5:
    mov al,[si+EntityRecordFrameSelector-EntityRecordsBase] ; @02DB5
    inc al ; @02DB8
    and al,0x7 ; @02DBA
    mov [si+EntityRecordFrameSelector-EntityRecordsBase],al ; @02DBC
    jz loc_2DC4 ; @02DBF
    jmp loc_1FEB ; @02DC1
loc_2DC4:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x0 ; @02DC4
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02DC9
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x0 ; @02DCE
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02DD3
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02DD8
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02DDD
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02DE1
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02DE6
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x9 ; @02DEB
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02DEF
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02DF2
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02DF5
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02DF9
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x7f ; @02DFD
    jmp loc_1FE8 ; @02E01
; Countdown/transition contract (188 bytes/52 sites), scoped TESTED C.
; Live DS:SI points at a 2Dh record. DEC byte +20 wraps; its RMW callbacks
; observe entry flags. Nonzero -> shared AND AL,AL/RET returns AL1/ZF0,
; retaining incoming AH. Caller1F45 checks +20 before CALL1F4C; do not cache
; across the CALL save, which may alias the record. Direct zero input wraps FF.
; Expiry tests +8 &5404: clear -> OR8000 and slot002E, set -> OR2 and slot003C.
; Layout/cursor/state stores and live callback-slot reads remain in byte order.
; AND byte +24,1 retains only bit0. Sound gates reread DS2010/25A7; AH4
; requests AL05/0C at2E5C/2EB0. Native driver prefixes/setters are scoped in
; sound-latches.md. C models the declared live INT frame/vector boundary;
; unbound vectors and changed IRET targets stop at their actual CS:IP.
; 2EB2 rereads +8 AFTER the sound call; bit2 clears +22. Live DS/SS/record/RET
; aliases remain observable. Expiry AL0/ZF1 does not generally mean AX0:
; with no sound AH retains the callback high byte; normal AH4 sound returns AH0.
; Shared tail2E60 belongs to both non-expiry and mask-clear expiry paths.
; Verified430 core/adapter fixtures +20 auxiliary INT calls,14 completed mutants.
; Field producers and platform/code-alias limits: entity-countdown.md.
AdvanceEntityCountdown:
    mov al,0x1 ; @02E04
    dec byte [si+EntityRecordCountdown-EntityRecordsBase] ; @02E06
    jnz loc_2E60 ; @02E09
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x5404 ; @02E0B
    jnz loc_2E63 ; @02E10
    or word [si+EntityRecordStateBits-EntityRecordsBase],0x8000 ; @02E12
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x8 ; @02E17
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x153b ; @02E1C
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @02E21
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @02E26
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02E2B
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02E2F
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @02E34
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x0 ; @02E39
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @02E3D
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02E40
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02E43
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02E47
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @02E4B
    jnz loc_2E5E ; @02E50
    test byte [SoundOptionBits-GameDataImage],0x3 ; @02E52
    jz loc_2E5E ; @02E57
    mov ax,0x405 ; @02E59
    int 0x61 ; @02E5C
EntityCountdownSoundReturn:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @02E5E
loc_2E60:
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02E60
EntityCountdownReturn:
    ret ; @02E62
loc_2E63:
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x2 ; @02E63
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x8 ; @02E67
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x180b ; @02E6C
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x280 ; @02E71
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x1e0 ; @02E76
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02E7B
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xffe7 ; @02E7F
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff0 ; @02E84
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x0 ; @02E89
    mov ax,[DrawingCallbackSlots-GameDataImage+0xe] ; @02E8D
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02E90
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @02E93
    mov byte [si+0x22],0xf ; @02E97
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02E9B
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @02E9F
    jnz loc_2EB2 ; @02EA4
    test byte [SoundOptionBits-GameDataImage],0x3 ; @02EA6
    jz loc_2EB2 ; @02EAB
    mov ax,0x40c ; @02EAD
    int 0x61 ; @02EB0
EntityCountdownMaskedSoundReturn:
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x4 ; @02EB2
    jz loc_2EBD ; @02EB7
    mov byte [si+0x22],0x0 ; @02EB9
loc_2EBD:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @02EBD
EntityCountdownMaskedReturn:
    ret ; @02EBF
; Live SS interaction-cell contract: coordinate words are not clamped below B0.
; Y-10 wraps then shifts logically; MUL keeps only its low product for the map.
; Actual stack pops supply DX, map base and AX; record/map/stack aliases are live.
; First cell is stored at record+2C, second at +2B. Nibbles dispatch from popped
; AL, which may differ from that first cell after intervening record writes.
; Low nibble1/5/6 initializes distinct transitions;2/3 conditionally NEG +27;
;4 tests/sets the indexed object word then reads its live sound byte at+1B.
; Preserve store/RMW flag phases, live0032/002E/003E callbacks, both sound-gate
; rereads, all returned INT registers and actual RET. UNKNOWN targets stay open.
ApplyEntityCellInteractions:
; Sample order is part of the contract: first SS cell -> +2C, then cursor
; -0340+2*signed(+27) -> second SS cell -> +2B, then POP the saved first AX.
; Record stores may alias that save; the popped dispatch value can change.
    mov ax,[si+EntityRecordX-EntityRecordsBase] ; @02EC0
    mov bx,[si+EntityRecordY-EntityRecordsBase] ; @02EC2
    cmp bx,0xb0 ; @02EC5
    jnl loc_2F3A ; @02EC9
    sub bx,byte +0x10 ; @02ECB
    shr ax,1 ; @02ECE
    shr ax,1 ; @02ED0
    shr bx,1 ; @02ED2
    shr bx,1 ; @02ED4
    push ax ; @02ED6
    push dx ; @02ED7
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @02ED8
    mov dx,0x1a0 ; @02EDA
    mul dx ; @02EDD
    pop dx ; @02EDF
    pop bx ; @02EE0
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02EE1
    add bx,byte +0x12 ; @02EE3
    mov al,[ss:bx] ; @02EE6
    push ax ; @02EE9
    mov [si+EntityRecordFirstInteractionCell-EntityRecordsBase],al ; @02EEA
    mov al,[si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02EED
    cbw ; @02EF0
    sub bx,0x340 ; @02EF1
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02EF5
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @02EF7
    mov al,[ss:bx] ; @02EF9
    mov [si+EntityRecordSecondInteractionCell-EntityRecordsBase],al ; @02EFC
    pop ax ; @02EFF
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @02F00
    and al,0xf ; @02F02
    shr ah,1 ; @02F04
    shr ah,1 ; @02F06
    shr ah,1 ; @02F08
    shr ah,1 ; @02F0A
    and ah,0xf ; @02F0C
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02F0F
    jz loc_2F3A ; @02F11
    dec al ; @02F13
    jz loc_2F3B ; @02F15
    dec al ; @02F17
    jnz loc_2F1E ; @02F19
    jmp loc_2FA2 ; @02F1B
loc_2F1E:
    dec al ; @02F1E
    jnz loc_2F25 ; @02F20
    jmp loc_2FAC ; @02F22
loc_2F25:
    dec al ; @02F25
    jnz loc_2F2C ; @02F27
    jmp loc_2FB6 ; @02F29
loc_2F2C:
    dec al ; @02F2C
    jnz loc_2F33 ; @02F2E
    jmp loc_2FF8 ; @02F30
loc_2F33:
    dec al ; @02F33
    jnz loc_2F3A ; @02F35
    jmp loc_304F ; @02F37
loc_2F3A:
    ret ; @02F3A
loc_2F3B:
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x4 ; @02F3B
    jnz loc_2F3A ; @02F40
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x2000 ; @02F42
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @02F47
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xefa ; @02F4C
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x4e ; @02F51
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x34 ; @02F56
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @02F5B
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @02F5F
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff3 ; @02F64
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x0 ; @02F69
    mov ax,[DrawingCallbackSlots-GameDataImage+0x4] ; @02F6D
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @02F70
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @02F73
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @02F77
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @02F7B
    jz loc_2F8E ; @02F80
    test byte [SoundOptionBits-GameDataImage],0x1 ; @02F82
    jz loc_2F8E ; @02F87
    mov ax,0x302 ; @02F89
    int 0x60 ; @02F8C
EntityInteractionPcSoundReturn:
loc_2F8E:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @02F8E
    jnz loc_2FA1 ; @02F93
    test byte [SoundOptionBits-GameDataImage],0x3 ; @02F95
    jz loc_2FA1 ; @02F9A
    mov ax,0x410 ; @02F9C
    int 0x61 ; @02F9F
EntityInteractionFirstSoundReturn:
loc_2FA1:
    ret ; @02FA1
loc_2FA2:
    cmp byte [si+EntityRecordHorizontalStep-EntityRecordsBase],0xff ; @02FA2
    jz loc_2F3A ; @02FA6
    neg byte [si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02FA8
    ret ; @02FAB
loc_2FAC:
    cmp byte [si+EntityRecordHorizontalStep-EntityRecordsBase],0x1 ; @02FAC
    jz loc_2F3A ; @02FB0
    neg byte [si+EntityRecordHorizontalStep-EntityRecordsBase] ; @02FB2
    ret ; @02FB5
loc_2FB6:
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @02FB6
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @02FB8
    mov dx,0x1c ; @02FBA
    mul dx ; @02FBD
    db 0x8b,0xf8 ; ENCODED: mov di,ax (NASM chooses a different encoding) ; @02FBF
    add di,LevelObjectGraphicsRecords-GameDataImage ; @02FC1
    test word [di],0x2 ; @02FC5
    jz loc_2FCE ; @02FC9
    jmp loc_2F3A ; @02FCB
loc_2FCE:
    or word [di],byte +0x2 ; @02FCE
    mov byte [si+EntityRecordInactiveMarker-EntityRecordsBase],0xff ; @02FD1
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @02FD5
    jz loc_2FDF ; @02FDA
    jmp loc_2F3A ; @02FDC
loc_2FDF:
    test byte [SoundOptionBits-GameDataImage],0x3 ; @02FDF
    jnz loc_2FE9 ; @02FE4
    jmp loc_2F3A ; @02FE6
; S13: +1B is a BYTE effect ID,then AH04.378A copies28-byte GROUND templates to17CB+1C*ordinal,with unchecked type,DF and stale skipped records. Supplied first16 GROUND union06/07/09/0E/0F plus fixedrequests cover01..0A/0C..12;0B has no established ordinary producer in that sample,but remains accepted by AdLib. Raw nonzero01..FF object bytes are not clamped;051C rejects>=13 without adding stream roots. Do not confuse mutable/stale IDs with stream bytes.
loc_2FE9:
    mov al,[di+0x1b] ; @02FE9
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @02FEC
    jnz loc_2FF3 ; @02FEE
    jmp loc_2F3A ; @02FF0
loc_2FF3:
    mov ah,0x4 ; @02FF3
; AL from live object+1B is an effect ID, passed unchanged to AH04. AdLib accepts01..12 only when one of records064C/0638/0624/0610 is inactive; invalid or full retains pendingF0. GROUND sample-ID union is not a universal bound on mutable/unchecked object records.
    int 0x61 ; @02FF5
EntityInteractionObjectSoundReturn:
    ret ; @02FF7
loc_2FF8:
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x1000 ; @02FF8
    jz loc_3002 ; @02FFD
    jmp loc_2F3A ; @02FFF
loc_3002:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x1000 ; @03002
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @03007
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x3e2 ; @0300C
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @03011
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @03016
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @0301B
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @0301F
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @03024
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x0 ; @03029
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @0302D
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @03030
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @03033
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @03037
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @0303B
    jnz loc_304E ; @03040
    test byte [SoundOptionBits-GameDataImage],0x3 ; @03042
    jz loc_304E ; @03047
    mov ax,0x411 ; @03049
    int 0x61 ; @0304C
EntityInteractionSecondSoundReturn:
loc_304E:
    ret ; @0304E
loc_304F:
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x4000 ; @0304F
    jz loc_3059 ; @03054
    jmp loc_2F3A ; @03056
loc_3059:
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x4000 ; @03059
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @0305E
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xf21 ; @03063
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x8c ; @03068
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x70 ; @0306D
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @03072
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @03076
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff2 ; @0307B
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x0 ; @03080
    mov ax,[DrawingCallbackSlots-GameDataImage+0x10] ; @03084
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @03087
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @0308A
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @0308E
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @03092
    jnz loc_30A5 ; @03097
    test byte [SoundOptionBits-GameDataImage],0x3 ; @03099
    jz loc_30A5 ; @0309E
    mov ax,0x40d ; @030A0
    int 0x61 ; @030A3
EntityInteractionThirdSoundReturn:
loc_30A5:
    ret ; @030A5
; R3 primary configuration does not close capacity:DATA-A nominal headers<=50
; imply0088..0E97 only with stable counters/cursors and serialization of30CC
; limit sample through314B publication against1874->4013. PROFILE preserves
; services,not this original race; later spill survival remains UNRESOLVED.
; SlotB3 numerically overlaps probe records;slotD3 overlaps25A0 and mode25A6.
; Do not infer these indices are reached,or clamp the original equality-only gate.
CreateEntityRecordIfDue:
; Record producer for the update and drawing consumers above.
; Gate002B must differ from FF;0055 must equal FF. Byte DEC0048 wraps and
; only zero reloads0048 from live0049. Equality0047==0043 prevents creation;
; there is no upper-bound clamp. SI=0088+45*unsigned(bound), BX=0E98+4*(bound&3).
; The45-byte clear advances DI with INC, independently of DF. Coordinates are
; fetched only after the clear: bound50h makes SI=0E98 and destroys their source.
; Ordered record stores and the late callback002E read precede live INC0043.
; No array extent, coordinate cache, host record or corrected bound is implied.
; Publication is INC0043 after3147, not the earlier+26 clear. An old inactive
; record within the bound is never chosen by this routine. The clear writes
; DS:[SI..SI+2C], followed by initialization, so after a reset the retained old
; bytes of later slots are irrelevant until appended and individually cleared.
; Known byte bound alone permits index00..FF (last slot2D5B..2D87); the walk
; after INC-to00 then ignores all slots. No DOS allocation is performed here.
; Coordinate source BX=0E98+4*(index&3) is read live AFTER the clear. Index50
; clears all four source pairs; it also overlaps the visibility map at0EA8.
; CAPACITY DOMAIN: complete pinned LEVEL reads plus forward selected odd copies
; give header low-byte limits01..50h; all80 base headers have high byte00.
; The40 selected overrides also have high00 and limit<=50; unselected dummy
; rows have0063.36CD discards the high byte, so arbitrary headers permit00..FF.
; 0404's C8 is overwritten before the known first creation0483.4013 normally
; stops at the current bound, but its IRQ race above can step past that limit.
; With serialized limit changes, reset bound0 and L<=50, no creation can
; cross0088..0E97. A stable starting bound B and limit L permit (L-B)&FF
; successful publications before equality; B>L wraps. Starting0 never wraps
; for a stable byte L, whereas FF!=L permits indexFF then INC-to00. Mutable
; limits avoiding equality have no finite publication-count bound. These are
; byte arithmetic contracts, not evidence of gameplay reaching every index.
    cmp byte [EntityUpdateGate-GameDataImage],0xff ; @030A6
    jnz loc_30B0 ; @030AB
    jmp loc_314F ; @030AD
loc_30B0:
    cmp byte [EntityCreationGate-GameDataImage],0xff ; @030B0
    jz loc_30BA ; @030B5
    jmp loc_314F ; @030B7
loc_30BA:
    dec byte [EntityCreationCountdown-GameDataImage] ; @030BA
    jz loc_30C3 ; @030BE
    jmp loc_314F ; @030C0
loc_30C3:
    mov al,[EntityCreationReload-GameDataImage] ; @030C3
    mov [EntityCreationCountdown-GameDataImage],al ; @030C6
    mov si,EntityRecordsBase-GameDataImage ; @030C9
; S19 creation-race: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; Original order permits IRQ1874->4013 between30CC limit sampling and314B publication,stepping
; count past the new limit. Loader IF1/profile preservation does not serialize it.
; Dependencies: Witness inputs: live unmasked pending game IRQ and qualifying command; later
; corrupted-state survival remains unresolved.
; S17 flow-state: From30A6 entry, IF is inherited at30CC,30D5 and314B; no local
; CLI/POPF/IRET/SS load serializes limit sampling through publication. Thus entryIF1 with
; an installed/unmasked game timer admits the S12 command4013 interleaving. The after30D5
; case is sufficient; the full stale sampled-limit window begins after30CC. This analyzer
; does not infer PIC masks, pending IRQ delivery, command eligibility, or survival of
; later corrupted records from IF alone.
    mov al,[LevelCreationLimit-GameDataImage] ; @030CC
    mov ah,[EntitySlotBound-GameDataImage] ; @030CF
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @030D3
    jz loc_314F ; @030D5
    db 0x8a,0xdc ; ENCODED: mov bl,ah (NASM chooses a different encoding) ; @030D7
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @030D9
    and bx,byte +0x3 ; @030DB
    shl bx,1 ; @030DE
    shl bx,1 ; @030E0
    add bx,TypeOneObjectCoordinates-GameDataImage ; @030E2
    mov cl,0x2d ; @030E6
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @030E8
    mul cl ; @030EA
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @030EC
    mov cx,0x2d ; @030EE
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @030F1
; [030F3] Unchecked producer witness, not a startup-reachability claim: slot byte179(decimal) yields SI1FFF and clear1FFF..202B, overlapping2011/2012 and four probe records;3140 writes record+14 at2013/2014. Slot211 gives SI259F, clear259F..25CB, then30FB/3100 straddle InputPollCallback25A0/25A1 with X-high/Y-low. Equality with mutable0047 is not a range bound. A closed target lifetime needs actual record/counter bounds or later reinitialization, including earlier overlapping globals.
loc_30F3:
    mov byte [di],0x0 ; @030F3
    inc di ; @030F6
    loop loc_30F3 ; @030F7
    mov ax,[bx] ; @030F9
    mov [si+EntityRecordX-EntityRecordsBase],ax ; @030FB
    mov ax,[bx+0x2] ; @030FD
    mov [si+EntityRecordY-EntityRecordsBase],ax ; @03100
    mov byte [si+EntityRecordHorizontalStep-EntityRecordsBase],0x1 ; @03103
    mov byte [si+0x25],0x0 ; @03107
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @0310B
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x4 ; @0310F
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @03113
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xa42 ; @03118
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @0311D
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @03122
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @03127
    mov byte [si+0x23],0x3 ; @0312B
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @0312F
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @03134
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x4 ; @03139
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @0313D
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @03140
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @03143
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @03147
    inc byte [EntitySlotBound-GameDataImage] ; @0314B
EntityCreationReturn:
loc_314F:
    ret ; @0314F

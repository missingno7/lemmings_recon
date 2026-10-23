; Maintained 3150..3633 action block; UNKNOWN bytes remain explicit.
; Logical ownership and native domains:docs/entity-actions.md.
times -(($-$$) != 0x3150) db 0 ; module start assertion
DispatchEntityAction:
sub_3150:
; T2 UNCONDITIONAL producer invariant with intact forward level reset and no
; unrelated cursor writer:0058/005A/005C are0 or0088+2D*k,k=00..FE.3CDE can
; scan at mostFF slots,so FF is never selected. Nonzero candidate count0063
; validates a prior hit,not current liveness:01AD precedes update/selection,
; and01C5 follows them. Update can deactivate the old selection between scans;
; count wrap makes3CDE return without refreshing0063,indices or pointers.
; Consequently stale pointers may be outside the NEW bound but stay aligned
; in this domain. No action rechecks+26. A forward455B reset clears cursors
; AND0063,so stale selection alone cannot cross that reset or alias002E slots.
; DF0 action word stores keep nine membership if source slots survive,even
; on stale/inactive records. DF1 action5 still writes+15 at347F,+14 at3488:
; callback=old_row0_cell2 OR(old_row0_cell1<<8),including0000 for empty cells.
; The map/source/save alias premises and actual foreground DF remain UNRESOLVED;
; the platform profile cannot validate a cursor or remove this byte writer.
; V1 spilled-record actions use the SAME predicates and stores as prefix
; records: pointer publication does not create a separate allocation. Each
; successful state/descriptor store also writes its overlapped owner at S+f;
; selectors2/3/4 affect24/25/20 even if+14 remains unchanged. Canonical
; cursor range excludesFF selection but not above-new-count stale pointers.
; On DF1 action5,copy old cells in original interleaved order: a prior SS
; replacement or aliased save can alter later source bytes. The simplified
; target=cell2|(cell1<<8) requires disjoint DS/SS/stack/source lifetimes.
; Actual foregroundDF1 producer remains UNRESOLVED; this byte rule is PROVEN
; conditional instruction behavior,not a new real-session DF1 schedule.
; RECORD POINTER DOMAIN:317C loads live DS:0058, with no alignment or0043 range
; check. The normal producer3CDE scans0088+k*2D, skips exact+26=FF and stores
; bucket pointers at3D8E/3D9C, then chosen0058 at3DC6/3DDA. Zero bound returns
; without resetting buckets; a nonzero scan resets indices, not pointer words.
; The action guard tests candidate count0063, not005E/001A or+26 again. Fallback
; SI comes from live005A after005F!=FF, followed by a fresh eligibility test;
; selectors9/6/7/8 can use it. No host record validation or lifetime pin exists.
; Direct+14 stores by selector:2/3/4 none;5 3459<-002E;6 3315<-0036;
; 7 3536<-0034;8 360B<-0036;9 325F<-0038. Source words are read after preceding
; stores; e.g. a raw SI002A can alias slot002E through+04. Nine literals from
; setup0FC1..0FF1 cannot replace these live reads in the unrestricted contract.
; No action allocates/compacts2Dh slots or writes+26 to reactivate an old slot.
; Callback preservation additionally requires the DF/map/stack conditions below.
; Direct drawing-field writes: selectors5/6/7/8/9 each write04/06/0A/0C/10/12/
; 14/28/29/2A;8 also INCs02. Selectors2/3/4 write24/25/20 respectively and
; preserve those drawing fields. Selector5's later STOSB footprint is additional.
; DS:SI selects the same mutable2D-byte record used by simulation and drawing.
; Selectors2..9 index the eight live action inventories; they are not +08 state
; values. Assignment may change state bits, sprite callback/geometry and cadence
; together. +20 countdown/strip and +27 direction/frame gate remain shared roles.
; Field anchors name observed accesses only; +1F/+21/+23/+25 meanings vary by
; state and remain numeric rather than inventing a complete historical struct.
; Action ownership:docs/entity-actions.md.1,221 known bytes/402 sites;
;31 UNKNOWN bytes remain unresolved. Gate002B/work guard0050/candidate0063
; failures leave the press latch untouched. Input bit0 clear reaches31BE;
; otherwise latchFF suppresses, then3177 setsFF before signed selector tests.
; Selected SI and fallback SI are live DS words; counts remain ordinal0..7.
; Native shared feedback tails31E5/3287 retain real INT/RET and segment seams.
    cmp byte [EntityUpdateGate-GameDataImage],0xff ; @03150
    jz loc_31BD ; @03155
    cmp byte [EntityWorkGuard-GameDataImage],0xff ; @03157
    jnz loc_3161 ; @0315C
    jmp short EntityActionDispatchReturn ; @0315E
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @03160
loc_3161:
    cmp byte [EntityCandidateCount-GameDataImage],0x0 ; @03161
    jz loc_31BD ; @03166
    mov ax,[InputButtonsWord-GameDataImage] ; @03168
    and ax,0x1 ; @0316B
    jz loc_31BE ; @0316E
    cmp byte [EntityActionPressLatch-GameDataImage],0xff ; @03170
    jz loc_31BD ; @03175
    mov byte [EntityActionPressLatch-GameDataImage],0xff ; @03177
    mov si,[EntitySelectedRecordOffset-GameDataImage] ; @0317C
    mov al,[EntityActionSelector-GameDataImage] ; @03180
    cmp al,0x2 ; @03183
    jl loc_31BD ; @03185
    jnz loc_318C ; @03187
    jmp ApplyEntityAction2 ; @03189
loc_318C:
    cmp al,0x3 ; @0318C
    jnz loc_3193 ; @0318E
    jmp ApplyEntityAction3 ; @03190
loc_3193:
    cmp al,0x4 ; @03193
    jnz loc_319A ; @03195
    jmp short ApplyEntityAction4 ; @03197
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @03199
loc_319A:
    cmp al,0x5 ; @0319A
    jnz loc_31A1 ; @0319C
    jmp ApplyEntityAction5 ; @0319E
loc_31A1:
    cmp al,0x6 ; @031A1
    jnz loc_31A8 ; @031A3
    jmp ApplyEntityAction6 ; @031A5
loc_31A8:
    cmp al,0x7 ; @031A8
    jnz loc_31AF ; @031AA
    jmp ApplyEntityAction7 ; @031AC
loc_31AF:
    cmp al,0x8 ; @031AF
    jnz loc_31B6 ; @031B1
    jmp ApplyEntityAction8 ; @031B3
loc_31B6:
    cmp al,0x9 ; @031B6
    jnz loc_31BD ; @031B8
    jmp short ApplyEntityAction9 ; @031BA
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @031BC
EntityActionDispatchReturn:
loc_31BD:
    ret ; @031BD
loc_31BE:
    mov byte [EntityActionPressLatch-GameDataImage],0x0 ; @031BE
EntityActionReleasedReturn:
    ret ; @031C3
ApplyEntityAction4:
; Selector4,33 bytes/9 sites/6 outcomes. Live count70,+20==0 and maskC003
; gate. DEC70,clear refresh counter72,then store+20=4F in that order.
; Field/global aliasing is permitted; fallthrough31E5 adds no CALL frame.
loc_31C4:
    cmp byte [LevelActionCount2-GameDataImage],0x0 ; @031C4
    jz loc_320C ; @031C9
    cmp byte [si+EntityRecordCountdown-EntityRecordsBase],0x0 ; @031CB
    jnz loc_320C ; @031CF
    test word [si+EntityRecordStateBits-EntityRecordsBase],0xc003 ; @031D1
    jnz loc_320C ; @031D6
    dec byte [LevelActionCount2-GameDataImage] ; @031D8
    mov byte [LevelActionCountRefreshCounter2-GameDataImage],0x0 ; @031DC
    mov byte [si+EntityRecordCountdown-EntityRecordsBase],0x4f ; @031E1
RequestEntityActionFeedback:
; Shared JMP/fallthrough entry,39 bytes/13 sites. No new nearCALL frame.
; PC gate is enabled!=FF/options&1; INT60 AX0313 returns31F8 with all live
; register/segment/stack/FLAGS effects. The second gate rereads returned DS
; and requires enabled==FF/options&3 before INT61 AX0404,return320B.
; Core stops before the actual nearRET; outer return word stays live SS:SP.
loc_31E5:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @031E5
    jz loc_31F8 ; @031EA
    test byte [SoundOptionBits-GameDataImage],0x1 ; @031EC
    jz loc_31F8 ; @031F1
    mov ax,0x313 ; @031F3
    int 0x60 ; @031F6
EntityActionAfterPcFeedback:
loc_31F8:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @031F8
    jnz loc_320B ; @031FD
    test byte [SoundOptionBits-GameDataImage],0x3 ; @031FF
    jz loc_320B ; @03204
    mov ax,0x404 ; @03206
    int 0x61 ; @03209
EntityActionFeedbackReturn:
loc_320B:
    ret ; @0320B
EntityActionFailureReturn:
; Shared actual nearRET,one byte. All failed action entries retain live SS:SP.
loc_320C:
    ret ; @0320C
ApplyEntityAction9:
;122 known bytes/33 sites/13 owned outcomes. Selected+2C nibble9 rejects
; before F57F eligibility. Alternate SI joins3224 after just its fresh mask
; check,bypassing count/nibble checks. Callback+0A read precedes+1F/+2A.
loc_320D:
    cmp byte [LevelActionCount7-GameDataImage],0x0 ; @0320D
    jz loc_3285 ; @03212
    mov al,[si+EntityRecordFirstInteractionCell-EntityRecordsBase] ; @03214
    and al,0xf ; @03217
    cmp al,0x9 ; @03219
    jz loc_3285 ; @0321B
    test word [si+EntityRecordStateBits-EntityRecordsBase],0xf57f ; @0321D
    jnz loc_3271 ; @03222
loc_3224:
    dec byte [LevelActionCount7-GameDataImage] ; @03224
    mov byte [LevelActionCountRefreshCounter7-GameDataImage],0x0 ; @03228
    and word [si+EntityRecordStateBits-EntityRecordsBase],0xf57f ; @0322D
    or word [si+EntityRecordStateBits-EntityRecordsBase],byte +0x10 ; @03232
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @03236
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x32a ; @0323B
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x70 ; @03240
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x54 ; @03245
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x11 ; @0324A
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @0324E
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff4 ; @03253
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x0 ; @03258
    mov ax,[DrawingCallbackSlots-GameDataImage+0xa] ; @0325C
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @0325F
    mov byte [si+0x1f],0x8 ; @03262
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @03266
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @0326A
    jmp RequestEntityActionFeedback ; @0326E
loc_3271:
    cmp byte [EntityAlternateSlotIndex-GameDataImage],0xff ; @03271
    jz loc_3285 ; @03276
    mov si,[EntityAlternateRecordOffset-GameDataImage] ; @03278
    test word [si+EntityRecordStateBits-EntityRecordsBase],0xf57f ; @0327C
    jnz loc_3285 ; @03281
    jmp short loc_3224 ; @03283
loc_3285:
    jmp short EntityActionFailureReturn ; @03285
RequestEntityActionService0412:
; Shared JMP entry,20 bytes/7 sites. Enabled==FF/options&3 requests INT61
; AX0412 through actual continuation329A. No nearCALL frame is introduced.
loc_3287:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @03287
    jnz loc_329A ; @0328C
    test byte [SoundOptionBits-GameDataImage],0x3 ; @0328E
    jz loc_329A ; @03293
    mov ax,0x412 ; @03295
    int 0x61 ; @03298
EntityActionService0412Return:
loc_329A:
    ret ; @0329A
ApplyEntityAction2:
; Selector2,34 bytes/10 sites/6 outcomes. Live count6A,flag+24 bit0 and
; state+08 mask0103 gate. DEC6A then replace ALL+24 bits with01; no reset6C.
; JMP31E5 shares the existing outer near-return word; failure JMP320C.
loc_329B:
    cmp byte [LevelActionCount0-GameDataImage],0x0 ; @0329B
    jz loc_32BA ; @032A0
    test byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @032A2
    jnz loc_32BA ; @032A6
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x103 ; @032A8
    jnz loc_32BA ; @032AD
    dec byte [LevelActionCount0-GameDataImage] ; @032AF
    mov byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @032B3
    jmp RequestEntityActionFeedback ; @032B7
loc_32BA:
    jmp EntityActionFailureReturn ; @032BA
ApplyEntityAction6:
;121 known bytes/32 sites/13 owned outcomes. Unsigned wrapped +2/+6 sum
; must exceed10 before initial F5EF test. Alternate SI only rechecks F5EF;
; it does not repeat sum/count gates. Ordered transition32D6 reads slot+8
; before+2A=FF; shared31E5/320C tails add no CALL frame.
loc_32BD:
    cmp byte [LevelActionCount4-GameDataImage],0x0 ; @032BD
    jz loc_331F ; @032C2
    mov ax,[si+EntityRecordY-EntityRecordsBase] ; @032C4
    add ax,[si+EntityRecordDrawingYBias-EntityRecordsBase] ; @032C7
    cmp ax,0xa ; @032CA
    jna loc_331F ; @032CD
    test word [si+EntityRecordStateBits-EntityRecordsBase],0xf5ef ; @032CF
    jnz loc_3322 ; @032D4
loc_32D6:
    dec byte [LevelActionCount4-GameDataImage] ; @032D6
    mov byte [LevelActionCountRefreshCounter4-GameDataImage],0x0 ; @032DA
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x80 ; @032DF
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @032E4
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff3 ; @032E9
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @032EE
    mov byte [si+0x21],0xc ; @032F2
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @032F6
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x6fa ; @032FB
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x68 ; @03300
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x4e ; @03305
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x10 ; @0330A
    mov ax,[DrawingCallbackSlots-GameDataImage+0x8] ; @0330E
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @03311
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @03315
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @03318
    jmp RequestEntityActionFeedback ; @0331C
loc_331F:
    jmp EntityActionFailureReturn ; @0331F
loc_3322:
    cmp byte [EntityAlternateSlotIndex-GameDataImage],0xff ; @03322
    jz loc_331F ; @03327
    mov si,[EntityAlternateRecordOffset-GameDataImage] ; @03329
    test word [si+EntityRecordStateBits-EntityRecordsBase],0xf5ef ; @0332D
    jnz loc_331F ; @03332
    jmp short loc_32D6 ; @03334
; S17 flow-state: For entry3336, fixed known edges, intact saves and no asynchronous IRQ,
; DF at347F/3488 is exactly incoming DF and ES is incoming DS; the path does not
; normalize DF. With DF1 the displaced saves can replace callback high/low (+15/+14),
; while DF0 uses +16..+1E. These are conditional writers; neither a real foreground DF1
; origin nor global DF0 exclusion follows. Known target lists stay incomplete.
ApplyEntityAction5:
;408 known bytes/158 sites/73 owned outcomes. Word MUL map geometry uses
; actual SS AX/DX saves and restores,then nine ordered SS probes reject2/A/3.
; Transition3422 precedes fresh map reads/saves: PUSH DS/POP ES is live and
; not restored. Explicit map INCs stay forward while STOSB follows DF.
; Map/record/stack aliases can change both saved bytes and final POP SI.
; CALLBACK-DOMAIN EXCEPTION: with stable ES=DS and DF=1, the nine STOSB stores
; go to record+16,+15,+14,+13,+12,+11,+10,+0F,+0E. 347F overwrites callback high
; byte+15 with the old second map cell;3488 overwrites low+14 with the old third.
; The callback just installed at3459 is therefore NOT preserved in this domain.
; With disjoint map/record/stack, final+14=old_cell2 | (old_cell1<<8), where cells
; 0/1/2 are the first row's three pre-replacement bytes. Earlier checks reject
; exact02/0A/03, not arbitrary bytes or near targets. Wider aliases may change
; even that formula; source reads and SS writes remain interleaved and live.
; DF=1 also overwrites mask+12/+13, stride+10/+11 and pair index+0E/+0F.
; DF=0 saves only+16..1E but SS map writes can still physically alias records,
; globals or PUSH DS/POP ES/POP SI saves. No CLD or segment-range check occurs.
; READINESS: direct writer semantics known; nine-target preservation CONDITIONAL
; on DF=0 and genuine stable record/frame plus disjoint map/stack/service writes.
; Shared31E5 feedback and320C RET retain the existing outer return word.
; CALLER DF: only decoded3150 callers are foreground01AD and01C5;319E JMPs
; here with their DF unchanged.3150..3488 has no CLD/POPF/INT on this path.
; The first dispatch follows transition sound calls and rendering; the second
; follows update/drawing/status. None is a DF0 barrier. Both can carry DF1
; if their foreground input/service/saved-FLAGS domain supplies it. This is
; an exposed caller contract, not proof that an ordinary BIOS/mouse sets DF.
; Main STD1BB0 is NOT such a return source:its read child CLDs at1D34 and
; normal decoder exit CLDs at1C78. Known game loading precedes IRQ install0492;
; no decoded frame-to-DAT call supplies a returning STD path. IRQ-local DF
; changes are restored by intact outer IRET; they need not reach these calls.
; Concrete conditional writer witness: genuine walking record+08=0, positive
; inventory and nine empty SS cells (00) pass every2/A/3 rejection. With DF1,
; stable disjoint saves/segments,347F/3488 replace the installed callback with
; 0000. Empty cells are allowed by03E7's forward map clear; a full map grammar
; is unnecessary to disprove nine-value preservation for this entry domain.
; No original foreground producer of DF1 is thereby established, and no new
; executable target/edge is inferred from the resulting RAM word.
loc_3336:
    cmp byte [LevelActionCount3-GameDataImage],0x0 ; @03336
    jz loc_3345 ; @0333B
    mov ax,[si+EntityRecordStateBits-EntityRecordsBase] ; @0333D
    and ax,0xf56f ; @03340
    jz loc_3348 ; @03343
loc_3345:
    jmp EntityActionFailureReturn ; @03345
loc_3348:
    mov ax,[si+EntityRecordX-EntityRecordsBase] ; @03348
    mov bx,[si+EntityRecordY-EntityRecordsBase] ; @0334A
    sub ax,0x4 ; @0334D
    sub bx,byte +0x6 ; @03350
    sub bx,byte +0x10 ; @03353
    shr ax,1 ; @03356
    shr ax,1 ; @03358
    shr bx,1 ; @0335A
    shr bx,1 ; @0335C
    push ax ; @0335E
    push dx ; @0335F
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @03360
    mov dx,0x1a0 ; @03362
    mul dx ; @03365
    pop dx ; @03367
    pop bx ; @03368
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @03369
    add bx,byte +0x12 ; @0336B
    mov ax,[ss:bx] ; @0336E
    cmp al,0x2 ; @03371
    jz loc_3345 ; @03373
    cmp al,0xa ; @03375
    jz loc_3345 ; @03377
    cmp al,0x3 ; @03379
    jz loc_3345 ; @0337B
    cmp ah,0x2 ; @0337D
    jz loc_3345 ; @03380
    cmp ah,0xa ; @03382
    jz loc_3345 ; @03385
    cmp ah,0x3 ; @03387
    jz loc_3345 ; @0338A
    mov al,[ss:bx+0x2] ; @0338C
    cmp al,0x2 ; @03390
    jz loc_3345 ; @03392
    cmp al,0xa ; @03394
    jz loc_3345 ; @03396
    cmp al,0x3 ; @03398
    jz loc_3345 ; @0339A
    mov ax,[ss:bx+0x1a0] ; @0339C
    cmp al,0x2 ; @033A1
    jz loc_3345 ; @033A3
    cmp al,0xa ; @033A5
    jz loc_3345 ; @033A7
    cmp al,0x3 ; @033A9
    jz loc_3345 ; @033AB
    cmp ah,0x2 ; @033AD
    jz loc_3345 ; @033B0
    cmp ah,0xa ; @033B2
    jz loc_3345 ; @033B5
    cmp ah,0x3 ; @033B7
    jz loc_3345 ; @033BA
    mov al,[ss:bx+0x1a2] ; @033BC
    cmp al,0x2 ; @033C1
    jnz loc_33C8 ; @033C3
    jmp loc_3345 ; @033C5
loc_33C8:
    cmp al,0xa ; @033C8
    jnz loc_33CF ; @033CA
    jmp loc_34CB ; @033CC
loc_33CF:
    cmp al,0x3 ; @033CF
    jnz loc_33D6 ; @033D1
    jmp loc_34CB ; @033D3
loc_33D6:
    mov ax,[ss:bx+0x340] ; @033D6
    cmp al,0x2 ; @033DB
    jnz loc_33E2 ; @033DD
    jmp loc_34CB ; @033DF
loc_33E2:
    cmp al,0xa ; @033E2
    jnz loc_33E9 ; @033E4
    jmp loc_34CB ; @033E6
loc_33E9:
    cmp al,0x3 ; @033E9
    jnz loc_33F0 ; @033EB
    jmp loc_34CB ; @033ED
loc_33F0:
    cmp ah,0x2 ; @033F0
    jnz loc_33F8 ; @033F3
    jmp loc_34CB ; @033F5
loc_33F8:
    cmp ah,0xa ; @033F8
    jnz loc_3400 ; @033FB
    jmp loc_34CB ; @033FD
loc_3400:
    cmp ah,0x3 ; @03400
    jnz loc_3408 ; @03403
    jmp loc_34CB ; @03405
loc_3408:
    mov al,[ss:bx+0x342] ; @03408
    cmp al,0x2 ; @0340D
    jnz loc_3414 ; @0340F
    jmp loc_34CB ; @03411
loc_3414:
    cmp al,0xa ; @03414
    jnz loc_341B ; @03416
    jmp loc_34CB ; @03418
loc_341B:
    cmp al,0x3 ; @0341B
    jnz loc_3422 ; @0341D
    jmp loc_34CB ; @0341F
loc_3422:
    dec byte [LevelActionCount3-GameDataImage] ; @03422
    mov byte [LevelActionCountRefreshCounter3-GameDataImage],0x0 ; @03426
    mov word [si+EntityRecordStateBits-EntityRecordsBase],0x100 ; @0342B
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @03430
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x8 ; @03434
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0xf9b ; @03439
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x5a ; @0343E
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @03443
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x0 ; @03448
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @0344C
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @03451
    mov ax,[DrawingCallbackSlots-GameDataImage+0x0] ; @03456
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @03459
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0x0 ; @0345C
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @03460
; Save replaced interaction cells in this live record. BX is the candidate
; SS map offset checked at 3348..341F; ES becomes DS for STOSB below.
; DF=0 saves nine bytes at +16h..+1Eh; DF=1 decrements only the destination
; while explicit INC SI still scans map rows forwards. Restore is 283B.
    push si ; @03464
    push ds ; @03465
    pop es ; @03466
    db 0x8b,0xfb ; ENCODED: mov di,bx (NASM chooses a different encoding) ; @03467
    add si,byte +0x16 ; @03469
    xchg si,di ; @0346C
    mov al,[ss:si] ; @0346E
    mov byte [ss:si],0x2 ; @03471
    inc si ; @03475
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @03476
    mov al,[ss:si] ; @03477
    mov byte [ss:si],0xa ; @0347A
    inc si ; @0347E
; R1:3336/action5 stores inherit the DF supplied at foreground calls01AD/01C5. No local CLD,
; POPF or service precedes them. DF1 makes347F write callback high+15 and3488 low+14; DF0
; stores nine cells at+16..1E. Actual root DF is UNRESOLVED in both modes. Driver IRET is
; DF-preserving, not DF-clearing; an intact outer IRQ frame prevents local DF leakage only.
; S19 action5-byte-effects: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; With DF1 and stable record/map,347F stores callback high at+15,3488 low at+14: old cell2 OR old
; cell1<<8. With DF0 the nine cells write+16..1E instead.
; Dependencies: Explicit DF and stable live record/map/segments/saves are input premises, not
; game reachability.
; S19 action5-actual-df: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; Loader DF0 excludes DOS entry DF1 as an origin. Actual DF0 at both foreground action calls is
; still unproved.
; Dependencies: Foreground service/driver/return-frame composition; IRQ/code/stack aliases;
; callback/record/index/resource writer closure.
    stosb ; @0347F
    mov al,[ss:si] ; @03480
    mov byte [ss:si],0x3 ; @03483
    inc si ; @03487
; S19 action5-byte-effects: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; With DF1 and stable record/map,347F stores callback high at+15,3488 low at+14: old cell2 OR old
; cell1<<8. With DF0 the nine cells write+16..1E instead.
; Dependencies: Explicit DF and stable live record/map/segments/saves are input premises, not
; game reachability.
; S19 action5-actual-df: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; Loader DF0 excludes DOS entry DF1 as an origin. Actual DF0 at both foreground action calls is
; still unproved.
; Dependencies: Foreground service/driver/return-frame composition; IRQ/code/stack aliases;
; callback/record/index/resource writer closure.
    stosb ; @03488
    add si,0x19d ; @03489
    mov al,[ss:si] ; @0348D
    mov byte [ss:si],0x2 ; @03490
    inc si ; @03494
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @03495
    mov al,[ss:si] ; @03496
    mov byte [ss:si],0xa ; @03499
    inc si ; @0349D
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @0349E
    mov al,[ss:si] ; @0349F
    mov byte [ss:si],0x3 ; @034A2
    inc si ; @034A6
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @034A7
    add si,0x19d ; @034A8
    mov al,[ss:si] ; @034AC
    mov byte [ss:si],0x2 ; @034AF
    inc si ; @034B3
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @034B4
    mov al,[ss:si] ; @034B5
    mov byte [ss:si],0xa ; @034B8
    inc si ; @034BC
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @034BD
    mov al,[ss:si] ; @034BE
    mov byte [ss:si],0x3 ; @034C1
    inc si ; @034C5
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @034C6
    pop si ; @034C7
    jmp RequestEntityActionFeedback ; @034C8
loc_34CB:
    jmp EntityActionFailureReturn ; @034CB
ApplyEntityAction7:
;137 known bytes/39 sites/18 owned outcomes. Eligibility F76F differs
; from transition AND F56F. Alternate SI rejoins active nibble checks34DC.
; Direction nibble9 uses0412 tail3287 without consuming count; normal path
; sets+2A before callback+6 read. No local stack/segment change.
loc_34CE:
    cmp byte [LevelActionCount5-GameDataImage],0x0 ; @034CE
    jz loc_3540 ; @034D3
    test word [si+EntityRecordStateBits-EntityRecordsBase],0xf76f ; @034D5
    jnz loc_3543 ; @034DA
loc_34DC:
    mov al,[si+EntityRecordSecondInteractionCell-EntityRecordsBase] ; @034DC
    and al,0xf ; @034DF
    mov ah,0x7 ; @034E1
    cmp byte [si+EntityRecordHorizontalStep-EntityRecordsBase],0x1 ; @034E3
    jz loc_34EB ; @034E7
    mov ah,0x8 ; @034E9
loc_34EB:
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @034EB
    jz loc_3540 ; @034ED
    cmp al,0x9 ; @034EF
    jnz loc_34F6 ; @034F1
    jmp RequestEntityActionService0412 ; @034F3
loc_34F6:
    dec byte [LevelActionCount5-GameDataImage] ; @034F6
    mov byte [LevelActionCountRefreshCounter5-GameDataImage],0x0 ; @034FA
    and word [si+EntityRecordStateBits-EntityRecordsBase],0xf56f ; @034FF
    or word [si+EntityRecordStateBits-EntityRecordsBase],0x200 ; @03504
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @03509
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff6 ; @0350E
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @03513
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @03517
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x7ca ; @0351C
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x50 ; @03521
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x3c ; @03526
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x20 ; @0352B
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @0352F
    mov ax,[DrawingCallbackSlots-GameDataImage+0x6] ; @03533
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @03536
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @03539
    jmp RequestEntityActionFeedback ; @0353D
loc_3540:
    jmp EntityActionFailureReturn ; @03540
loc_3543:
    cmp byte [EntityAlternateSlotIndex-GameDataImage],0xff ; @03543
    jz loc_3540 ; @03548
    mov si,[EntityAlternateRecordOffset-GameDataImage] ; @0354A
    test word [si+EntityRecordStateBits-EntityRecordsBase],0xf76f ; @0354E
    jnz loc_3540 ; @03553
    jmp short loc_34DC ; @03555
ApplyEntityAction3:
; Selector3,39 bytes/11 sites/6 outcomes. Live count6D,+25==0 and mask0103
; gate. Store+25=FF BEFORE fresh DEC6D,then reset refresh counter6F.
; If+25 aliases6D this store changes DEC input. JMP31E5 adds no CALL frame.
loc_3557:
    cmp byte [LevelActionCount1-GameDataImage],0x0 ; @03557
    jz loc_357B ; @0355C
    cmp byte [si+0x25],0x0 ; @0355E
    jnz loc_357B ; @03562
    test word [si+EntityRecordStateBits-EntityRecordsBase],0x103 ; @03564
    jnz loc_357B ; @03569
    mov byte [si+0x25],0xff ; @0356B
    dec byte [LevelActionCount1-GameDataImage] ; @0356F
    mov byte [LevelActionCountRefreshCounter1-GameDataImage],0x0 ; @03573
    jmp RequestEntityActionFeedback ; @03578
loc_357B:
    jmp EntityActionFailureReturn ; @0357B
; No incoming edge identified for 357E..3597: no direct, table, vector, relocated or
; protected-view reference reaches it and no data reader uses it, so the bytes
; stay UNKNOWN (code-looking). Recovered paths bypass it; translators of the
; neighbouring routines need nothing from it.
; Read as code: another assignment attempt. It requires 005F!=FF, takes SI
; from 005A, requires record+25=0 and (record+08 & 0103)=0, failing through
; 357B (JMP 320C); on success it jumps to 356B, which sets record+25=FF and
; decrements the action count. No recovered selector dispatches here.
; UNKNOWN: unresolved bytes
    db 0x80,0x3e,0x5f,0x00,0xff,0x74,0xf6,0x8b,0x36,0x5a,0x00,0x80,0x7c,0x25,0x00,0x75 ; @0357E
; UNKNOWN: unresolved bytes
    db 0xec,0xf7,0x44,0x08,0x03,0x01,0x75,0xe5,0xeb,0xd3 ; @0358E
ApplyEntityAction8:
;154 known bytes/46 sites/22 owned outcomes;35A1/35AB stay UNKNOWN.
; Alternate SI rejoins35AC,then+2C and direction nibble checks still run.
; Early nibble9 uses0412; normal transition ends with live word INC[SI+2].
loc_3598:
    cmp byte [LevelActionCount6-GameDataImage],0x0 ; @03598
    jnz loc_35A2 ; @0359D
    jmp short loc_361C ; @0359F
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @035A1
loc_35A2:
    test word [si+EntityRecordStateBits-EntityRecordsBase],0xfd6f ; @035A2
    jz loc_35AC ; @035A7
    jmp short loc_361F ; @035A9
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @035AB
loc_35AC:
    mov al,[si+EntityRecordFirstInteractionCell-EntityRecordsBase] ; @035AC
    and al,0xf ; @035AF
    cmp al,0x9 ; @035B1
    jz loc_361C ; @035B3
    mov al,[si+EntityRecordSecondInteractionCell-EntityRecordsBase] ; @035B5
    and al,0xf ; @035B8
    mov ah,0x7 ; @035BA
    cmp byte [si+EntityRecordHorizontalStep-EntityRecordsBase],0x1 ; @035BC
    jz loc_35C4 ; @035C0
    mov ah,0x8 ; @035C2
loc_35C4:
    db 0x3a,0xc4 ; ENCODED: cmp al,ah (NASM chooses a different encoding) ; @035C4
    jz loc_361C ; @035C6
    cmp al,0x9 ; @035C8
    jnz loc_35CF ; @035CA
    jmp RequestEntityActionService0412 ; @035CC
loc_35CF:
    dec byte [LevelActionCount6-GameDataImage] ; @035CF
    mov byte [LevelActionCountRefreshCounter6-GameDataImage],0x0 ; @035D3
    and word [si+EntityRecordStateBits-EntityRecordsBase],0xfd6f ; @035D8
    or word [si+EntityRecordStateBits-EntityRecordsBase],0x800 ; @035DD
    mov word [si+EntityRecordDrawingXBias-EntityRecordsBase],0xfff8 ; @035E2
    mov word [si+EntityRecordDrawingYBias-EntityRecordsBase],0xfff3 ; @035E7
    mov byte [si+EntityRecordFrameSelector-EntityRecordsBase],0x0 ; @035EC
    mov word [si+EntityRecordSpriteSourceOffset-EntityRecordsBase],0x0 ; @035F0
    mov word [si+EntityRecordSpriteParagraphOffset-EntityRecordsBase],0x90a ; @035F5
    mov word [si+EntityRecordSpriteFrameStride-EntityRecordsBase],0x68 ; @035FA
    mov word [si+EntityRecordSpriteMaskOffset-EntityRecordsBase],0x4e ; @035FF
    mov byte [si+EntityRecordFrameAddend-EntityRecordsBase],0x18 ; @03604
    mov ax,[DrawingCallbackSlots-GameDataImage+0x8] ; @03608
    mov [si+EntityRecordSpriteCallback-EntityRecordsBase],ax ; @0360B
    mov byte [si+EntityRecordAlignmentGate-EntityRecordsBase],0xff ; @0360E
    and byte [si+EntityRecordBehaviorFlags-EntityRecordsBase],0x1 ; @03612
    inc word [si+EntityRecordY-EntityRecordsBase] ; @03616
    jmp RequestEntityActionFeedback ; @03619
loc_361C:
    jmp EntityActionFailureReturn ; @0361C
loc_361F:
    cmp byte [EntityAlternateSlotIndex-GameDataImage],0xff ; @0361F
    jz loc_361C ; @03624
    mov si,[EntityAlternateRecordOffset-GameDataImage] ; @03626
    test word [si+EntityRecordStateBits-EntityRecordsBase],0xfd6f ; @0362A
    jnz loc_361C ; @0362F
    jmp loc_35AC ; @03631
times -(($-$$) != 0x3634) db 0 ; module end assertion

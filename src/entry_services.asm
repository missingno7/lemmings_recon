; S19 loader: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; Original PKLITE supplies DF0/IF1 for every DOS DF/IF at ProgramEntry. This is an entry boundary
; fact, not exclusion of a later IRQ.
; S17 flow-state: The pinned footer establishes CS=load, SS=load+143E, SP=4AF4;
; DOS/unpacker entry gives DS=ES=PSP. The footer encodes no DF/IF. Do not import
; check_unpack fixture FLAGS=0002 as a DOS/startup guarantee. 0003 installs relocated09A9
; as DS, but the first undeclared service at0016 already prevents a whole-program
; DF/DS/SS guarantee. The decoded-edge analyzer leaves those service returns unknown;
; protected views, code/stack aliases and unrestricted IRQs remain separate obligations.
; Maintained image span 00000..01915; reconstruction module, not a historical linker claim.
; Static code frame 0000; semantic module boundaries remain under investigation.
; DOS entry: establishes relocated DATA; integrity checks precede initialization.
ProgramEntry:
; ENTRY FLAGS (original-code evidence, tools/check_unpack.py): the PKLITE stub
; executes CLD/STD/CLD and STI before RETF, so this entry receives DF=0, IF=1
; whatever DOS supplied. The 0000..2011 clear therefore runs forward here; the
; instruction itself stays DF-sensitive for any other entry.
; READINESS CONDITIONAL (c/startup.c): ES=PSP; 1A clock words 259C/259E survive
; the clear 0000..2011; AH1B pointer is read before POP DS (1FDE).
; BIOS 0F saves AL/BH after the option screen set mode 3. Protection at 00E0 is
; an explicit seam; JMP 43F2 enters the menu with no invented outer RET.
    mov dx,0x9a9 ; @00000
    mov ds,dx ; @00003
    push es ; @00005
    call InitializeCodeChecksum ; @00006
    mov [cs:0x83b8],al ; @00009
    call InitializeCodeChecksum ; @0000D
    mov [cs:0x83bd],al ; @00010
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @00014
    int 0x1a ; @00016
    mov [SavedBiosClockLow-GameDataImage],dx ; @00018
    mov [SavedBiosClockHigh-GameDataImage],cx ; @0001C
    mov ah,0x4a ; @00020
    mov bx,0x1911 ; @00022
    int 0x21 ; @00025
    push ds ; @00027
    pop es ; @00028
    mov di,0x0 ; @00029
    mov cx,0x2012 ; @0002C
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0002F
; S19 startup-clear: CONSERVATIVE=UNRESOLVED; PROFILE=PLATFORM-CONDITIONAL.
; Forward clear includes game DS:0000..2011. PROFILE serial projection has DF0; CONSERVATIVE
; loses DF after early services.
; Profile entries: 1A:AH=0000, 21:AH=004A.
; Dependencies: Fixed checksum/setup paths; no asynchronous interference; intact saves and
; ES=gameDS handoff.
    rep stosb ; @00031
    pop ax ; @00033
    mov [StartupPspSegment1FF6-GameDataImage],ax ; @00034
    call InitializeVgaRegisterMirrors ; @00037
    mov word [0x1f7c],0xff ; @0003A
    mov byte [PrivateVectorNumber-GameDataImage],0xc ; @00040
    mov byte [StartupOption200F-GameDataImage],0xff ; @00045
    call ParsePspCommandLine ; @0004A
    call SelectStartupDisplayAndOptions ; @0004D
    mov ax,0x3509 ; @00050
    int 0x21 ; @00053
    mov [SavedKeyboardVector-GameDataImage+2],es ; @00055
    mov [SavedKeyboardVector-GameDataImage],bx ; @00059
    mov ax,0x3508 ; @0005D
    int 0x21 ; @00060
    mov [SavedTimerVector-GameDataImage],bx ; @00062
    mov [SavedTimerVector-GameDataImage+2],es ; @00066
    mov ah,0x35 ; @0006A
    mov al,[PrivateVectorNumber-GameDataImage] ; @0006C
    int 0x21 ; @0006F
    mov [SavedPrivateVector-GameDataImage],bx ; @00071
    mov [SavedPrivateVector-GameDataImage+2],es ; @00075
    mov ax,0x2562 ; @00079
    push ds ; @0007C
    push es ; @0007D
    pop ds ; @0007E
    db 0x8b,0xd3 ; ENCODED: mov dx,bx (NASM chooses a different encoding) ; @0007F
    int 0x21 ; @00081
    pop ds ; @00083
    push ds ; @00084
    mov ax,0x2524 ; @00085
    push cs ; @00088
    pop ds ; @00089
    mov dx,0x18f8 ; @0008A
    int 0x21 ; @0008D
    pop ds ; @0008F
    mov byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @00090
    push ds ; @00095
    mov ah,0x1b ; @00096
    int 0x21 ; @00098
    mov al,[bx] ; @0009A
    pop ds ; @0009C
    mov [StartupFatIdByte1FDE-GameDataImage],al ; @0009D
    mov ah,0xf ; @000A0
    int 0x10 ; @000A2
    mov [SavedVideoMode-GameDataImage],al ; @000A4
    mov [SavedVideoPage-GameDataImage],bh ; @000A7
    call InitializeSoundDriver ; @000AB
    call AllocateStartupGraphicsArena ; @000AE
    call InitializeMouseDriverHooks ; @000B1
    mov byte [cs:MouseIrqMirrorGate83BE],0xff ; @000B4
    nop ; @000BA
    mov ax,0xd ; @000BB
    int 0x10 ; @000BE
    mov ah,0x9 ; @000C0
    lea dx,[0x2200] ; @000C2
    int 0x21 ; @000C6
    call CalibrateGameTimerReload ; @000C8
    mov al,0x36 ; @000CB
    out 0x43,al ; @000CD
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @000CF
    out 0x40,al ; @000D1
    out 0x40,al ; @000D3
    call LoadMainResourceSections ; @000D5
FinalizeStartupServicesAndEnterMenu:
; Disable DAT cache, enable retry, protection 062B (seam), keyboard IRQ09,
; CLI + PIT 36 reload from 1FC9, STI, JMP EnterMainMenu.
    call DisableDatCache ; @000D8
    mov byte [DatRetryEnabled-GameDataImage],0xff ; @000DB
    call CheckStartupProtection ; @000E0
    call InstallKeyboardVector ; @000E3
    cli ; @000E6
    mov cx,[0x1fc9] ; @000E7
    mov al,0x36 ; @000EB
    out 0x43,al ; @000ED
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @000EF
    out 0x40,al ; @000F1
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @000F3
    out 0x40,al ; @000F5
    sti ; @000F7
    jmp EnterMainMenu ; @000F8
loc_00FB:
EnterLoadedLevelGame:
; Session entry after resource loading/briefing: JMP target from the level-start
; path (454C/4551), never RETs. Its only exit is 02CD..0311 -> JMP 46EB.
; LIFETIMES: startup clears DS:0000..2011 once; every level start (4551) clears
; DS:0000..0FC9 and loads LEVEL at 0FCB; 03E7 resets session fields and the SS
; cell/dirty maps; 36B6 then replaces origin, creation limit and minutes digit.
; FRAME: 0105 swap -> pace/wait -> 0186 gate -> tick -> end/time tests ->
; countdown -> key-mask commands -> JMP 0105. Tick CALL order: 031E fades/cues,
; 4085 selector keys/edge scroll, 80FD dirty rows, 7900 status backdrop, 3150
; action #1, 30A6 create, 1F19 simulate, 3944 object animation, 7BB8 object
; draw, 3634 entity draw, 3CDE selection, 3AC8 status, 3150 action #2.
; TIMER HANDSHAKE: INT08 17C7 (PIT reload 1FC9 from 15AD; chains to BIOS every
; fourth IRQ) runs input poll 418C and key commands 3E6F, then sets 1FCF=FF and
; INC 1FCD. The foreground clears 1FCF, polls it (watchdog 0183), and ticks
; only when 1FCD>4 signed, then zeroes 1FCD: overrun IRQs are dropped, never
; replayed; a count that reached 80..FF must wrap through 00 before 05.
; Buttons/pointer/key mask/pause gate 002B/scan byte are IRQ-produced and may
; change between any two foreground instructions executed with IF=1.
; DOUBLE DISPATCH: both 3150 calls share press latch 0061. #1 uses the previous
; frame's candidate/selection (the highlighted creature on screen) and normally
; consumes a press made during the wait; #2 sees this frame's fresh selection,
; catching presses gated at #1 (no candidate) or delivered mid-frame. A press
; applies at most once until release reaches 31BE and clears the latch.
; REGISTERS: the controller reads only its own loads, the fade steps' AL/ZF,
; and AX after INT61 0200 at 02A1. Children get full predecessor state.
; READINESS (0105..03E6 + 4085..417A): READY and translated (c/game_frame.c,
; game_transition.c, view_scroll.c) where IRQs arrive only at polls 0131/0179/
; 01DF; INT60/61 via providers; children keep their scoped domains (3634 715B
; callbacks, sound bodies). Open: 004A FF producer, preemption interleavings.
    call InitializeGameSession ; @000FB
    mov byte [cs:MouseIrqMirrorGate83BE],0x0 ; @000FE
    nop ; @00104
GameFrameSwapAndPace:
; Swap the two drawing origins and their dirty-map offsets together. Option FF
; additionally drives CRTC start-address writes and retrace polling here; the
; timer handler owns the alternative display path. Do not merge the two owners.
    mov ax,[AlternateDrawingOrigin-GameDataImage] ; @00105
    xchg [DrawingOrigin-GameDataImage],ax ; @00108
    mov [AlternateDrawingOrigin-GameDataImage],ax ; @0010C
    mov ax,[AlternateDrawingDirtyCellMapOffset-GameDataImage] ; @0010F
    xchg [DrawingDirtyCellMapOffset-GameDataImage],ax ; @00112
    mov [AlternateDrawingDirtyCellMapOffset-GameDataImage],ax ; @00116
    cmp byte [ConfigurationOption200E-GameDataImage],0xff ; @00119
    jnz GameFrameWaitForTimer ; @0011E
GameFrameRetryRasterSync:
    mov byte [TimerChainFlag1FCF-GameDataImage],0x0 ; @00120
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @00125
    add dl,0x6 ; @00129
loc_012C:
GameFrameWaitRetraceEnd:
    in al,dx ; @0012C
    test al,0x8 ; @0012D
    jnz loc_012C ; @0012F
    cmp byte [TimerChainFlag1FCF-GameDataImage],0xff ; @00131
    jnz loc_013F ; @00136
loc_0138:
GameFrameRetraceAfterTimerEdge:
    in al,dx ; @00138
    test al,0x8 ; @00139
    jz loc_0138 ; @0013B
    jmp short GameFrameRetryRasterSync ; @0013D
loc_013F:
GameFrameProgramDisplayStart:
    sub dl,0x6 ; @0013F
    cli ; @00142
    mov bx,[AlternateDrawingOrigin-GameDataImage] ; @00143
    add bx,[DrawingPageByteOffset-GameDataImage] ; @00147
    add bx,byte +0x2 ; @0014B
    db 0x8a,0xe7 ; ENCODED: mov ah,bh (NASM chooses a different encoding) ; @0014E
    mov al,0xc ; @00150
    out dx,ax ; @00152
    db 0x8a,0xe3 ; ENCODED: mov ah,bl (NASM chooses a different encoding) ; @00153
    inc al ; @00155
    out dx,ax ; @00157
    sti ; @00158
    add dl,0x6 ; @00159
loc_015C:
GameFrameWaitRetraceStart:
    in al,dx ; @0015C
    test al,0x8 ; @0015D
    jz loc_015C ; @0015F
    call UpdateFixedWordPattern ; @00161
GameFrameWaitForTimer:
; Budget produced by InitializeGameSession. DEC CX only borrows into DX at CX=0;
; a zero DX at that point reinstalls INT08. A live timer FF flag ends polling.
; This is the literal split-word loop, not a host timeout or a 32-bit decrement.
    mov cx,[ForegroundWaitLowWord-GameDataImage] ; @00164
    mov dx,[ForegroundWaitHighWord-GameDataImage] ; @00168
    mov byte [TimerChainFlag1FCF-GameDataImage],0x0 ; @0016C
loc_0171:
GameFrameWaitPoll:
    dec cx ; @00171
    jnz loc_0179 ; @00172
    db 0x23,0xd2 ; ENCODED: and dx,dx (NASM chooses a different encoding) ; @00174
    jz loc_0183 ; @00176
    dec dx ; @00178
loc_0179:
GameFrameWaitCheckTimerFlag:
    cmp byte [TimerChainFlag1FCF-GameDataImage],0xff ; @00179
    jnz loc_0171 ; @0017E
    jmp short GameFrameTickGate ; @00180
; S14 U001: [00182,00183) stored bytes remain UNKNOWN.
; Neighbours: P 00180 jmp 0x186; N 00183 call 0x1644.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @00182
loc_0183:
GameFrameWatchdogReinstallTimer:
    call InstallGameTimerVector ; @00183
GameFrameTickGate:
; JNG below compares AL as signed against4. IRQ17C7 increments the shared byte;
; at an accepted tick the foreground clears it and the keyboard scan snapshot.
; 0194 clears KeyboardScanCodeByte before 4085 reads it: 4085's selector keys
; see only a make code IRQ09 (1707) stores during 031E. 1FD3 counts accepted
; ticks; 0052 is incremented after 031E, so cues compare the previous count.
    mov al,[TimerForegroundCounter1FCD-GameDataImage] ; @00186
    mov cl,0x4 ; @00189
    db 0x3a,0xc1 ; ENCODED: cmp al,cl (NASM chooses a different encoding) ; @0018B
    jng GameFrameWaitForTimer ; @0018D
    mov byte [TimerForegroundCounter1FCD-GameDataImage],0x0 ; @0018F
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @00194
    inc byte [ForegroundCounter1FD3-GameDataImage] ; @00199
    call AdvanceGameTransitionEffects ; @0019D
GameFrameAfterTransition:
    call HandleSelectorKeysAndEdgeScroll ; @001A0
GameFrameAfterSelectorScroll:
    inc byte [ForegroundCounter0052-GameDataImage] ; @001A3
    call CopyDirtyLevelRowsToDrawingPage ; @001A7
GameFrameAfterDirtyRows:
    call CopyStatusBackdropToDrawingPage ; @001AA
; R1: both3150 calls inherit live foreground DF. Loader0 and decoder normal-return0 are
; proven boundary facts, not a certificate through all preceding services/protected views/
; callbacks. PROFILE does not bind INT61 or close715B. Keep actual DF at01AD/01C5 unresolved
; pending that composition, separately from IRQ/stack/record/resource writer obligations.
; S19 action5-actual-df: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; Loader DF0 excludes DOS entry DF1 as an origin. Actual DF0 at both foreground action calls is
; still unproved.
; Dependencies: Foreground service/driver/return-frame composition; IRQ/code/stack aliases;
; callback/record/index/resource writer closure.
; ACTION DF: both01AD and01C5 call3150 with live foreground DF;319E->3336 has no CLD/POPF/INT before347F/3488. Main STD1BB0 has read-child CLD1D34 and normal decoder CLD1C78, so it is not a proved returning DF1 source. Known foreground/service/saved-frame DF and separate IRQ-local visibility DF contracts remain required. IRQ-at-poll scheduling does not exclude the original4013/constructor publication race.
GameFrameAfterStatusBackdrop:
    call DispatchEntityAction ; @001AD
; T2 UNCONDITIONAL handoffs:create01B0,update01B3,animation01B6,object draw01B9,entity draw01BC,selection01BF,action01C5. Spill owners can alter+14 before draw. Zero-bound selection after wrap retains0063/cursors.01AD uses previous selection. Pending IRQ and live saves remain separate.
CreateAndAdvanceEntityRecords:
; Scoped two-CALL prefix:actual returns01B3/01B6 remain live SS words.
; Newly created canonical record is consumed immediately by1F19; its byte
; bound wrap is original. Stop01B6 before3944,not an outerRET or full tick.
    call CreateEntityRecordIfDue ; @001B0
EntityBatchAfterCreateCall:
    call AdvanceEntityRecords ; @001B3
EntityBatchNextCaller:
    call AdvanceLevelObjectAnimations ; @001B6
GameFrameAfterObjectAnimations:
    call DrawLevelObjectGraphics ; @001B9
GameFrameAfterObjectGraphics:
    call DrawEntityRecords ; @001BC
GameFrameAfterEntityDrawing:
    call SelectEntityCandidate ; @001BF
GameFrameAfterSelection:
    call UpdateStatusDisplay ; @001C2
; S19 action5-actual-df: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; Loader DF0 excludes DOS entry DF1 as an origin. Actual DF0 at both foreground action calls is
; still unproved.
; Dependencies: Foreground service/driver/return-frame composition; IRQ/code/stack aliases;
; callback/record/index/resource writer closure.
GameFrameAfterStatusDisplay:
    call DispatchEntityAction ; @001C5
GameFrameAfterSecondDispatch:
    cmp byte [GameEndRequested-GameDataImage],0xff ; @001C8
    jnz loc_01D2 ; @001CD
    jmp GameEndWaitForFade ; @001CF
; S19 double-wait-004a: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; 004A stored/startup/session zero producers are known; actual-game FF producer remains
; unknown.01D2 on exactFF waits for two observed1FCD changes without local STI/timeout.
; Dependencies: Indexed/string/word/stack/provider writer domains; timer delivery and
; wrap/coalescing; raw FF alias witnesses do not prove a game producer.
; S14 WRITER SEARCH: no dedicated actual-game FF producer identified.
; Stored DS004A=00; startup0031/level455B clear it only with forward game-DS
; footprints; their DF1 ranges miss004A. Session0409 resets00 directly.
; Main absolute/word-overlap census: reader01D2 and zero writer0409 only.
; Protected TF-on/TF-off + activeINT1 have no absolute004A access. This is
; not a global no-writer proof:1130 indexed main writes,strings,implicit SS
; frames,resource/returned segments and protected far aliases remain live.
; Raw1C82 with ES=game DS,DI004B,ALFF storesFF at004A via1C83; raw20E2
; with DS=game DS,SI0024 also setsFF. Neither proves a game-path producer.
; Pinned LEVEL0FCB..17CA,GROUND request1B4B..2B4A,override5566..66E5 miss
;004A under intact segments. Malformed lengths/cache/stack aliases unchecked.
; Tandy AH03 writes driver-CS004A after PUSH CS/POP DS,not this field.
; ExactFF samples1FCD twice and spins for each inequality. Changes before
; resampling may coalesce; FF->00 counts;256 unseen increments alias equality.
; No local timeout/CLD/STI. Other values bypass; retain FF branch/poll seam.
; game_frame double-wait fixtures seedFF externally,not an original producer.
; READINESS remains CONDITIONAL on producer/alias and IRQ scheduling domains.
loc_01D2:
GameFrameDoubleWaitCheck:
    cmp byte [FrameDoubleWaitFlag004A-GameDataImage],0xff ; @001D2
    jnz loc_01E7 ; @001D7
    mov cx,0x2 ; @001D9
loc_01DC:
GameFrameDoubleWaitSample:
    mov al,[TimerForegroundCounter1FCD-GameDataImage] ; @001DC
loc_01DF:
GameFrameDoubleWaitSpin:
    cmp [TimerForegroundCounter1FCD-GameDataImage],al ; @001DF
    jz loc_01DF ; @001E3
    loop loc_01DC ; @001E5
loc_01E7:
GameFrameCheckAllAccounted:
    mov al,[EntitySlotBound-GameDataImage] ; @001E7
    cmp al,[LevelCreationLimit-GameDataImage] ; @001EA
    jnz loc_01FA ; @001EE
    mov al,[EntityDrawingPassCount-GameDataImage] ; @001F0
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @001F3
    jnz loc_01FA ; @001F5
    jmp RequestGameFadeOut ; @001F7
loc_01FA:
GameFrameCheckTimeExpired:
    mov al,[LevelCountdownHighDigit-GameDataImage] ; @001FA
    or al,[LevelCountdownTensDigit-GameDataImage] ; @001FD
    or al,[LevelCountdownOnesDigit-GameDataImage] ; @00201
    cmp al,0x30 ; @00205
    jnz GameCountdownTick ; @00207
    jmp RequestGameFadeOut ; @00209
GameCountdownTick:
; Pausing (update gate FF) preserves the countdown divider. Otherwise byte DEC
; wraps; only zero reloads it and decrements the three ASCII time digits. The
; word at20A9 packs tens in BL and ones in BH. Borrow resets to5/9, then0:00.
    cmp byte [EntityUpdateGate-GameDataImage],0xff ; @0020C
    jz GameFrameCommands ; @00211
    dec byte [GameCountdownTickCounter-GameDataImage] ; @00213
    jnz GameFrameCommands ; @00217
    mov al,[GameCountdownTickReload-GameDataImage] ; @00219
    mov [GameCountdownTickCounter-GameDataImage],al ; @0021C
    mov al,[LevelCountdownHighDigit-GameDataImage] ; @0021F
    mov bx,[LevelCountdownTensDigit-GameDataImage] ; @00222
    dec bh ; @00226
    cmp bh,0x2f ; @00228
    jnz loc_0243 ; @0022B
    mov bh,0x39 ; @0022D
    dec bl ; @0022F
    cmp bl,0x2f ; @00231
    jnz loc_0243 ; @00234
    mov bl,0x35 ; @00236
    dec al ; @00238
    cmp al,0x2f ; @0023A
    jnz loc_0243 ; @0023C
    mov al,0x30 ; @0023E
    mov bx,0x3030 ; @00240
loc_0243:
GameCountdownStoreDigits:
    mov [LevelCountdownHighDigit-GameDataImage],al ; @00243
    mov [LevelCountdownTensDigit-GameDataImage],bx ; @00246
GameFrameCommands:
    mov ax,[InputKeyMask1FC7-GameDataImage] ; @0024A
    cmp byte [SpecialLevelCodeLatch-GameDataImage],0xff ; @0024D
    jnz loc_025C ; @00252
    test ax,0x8000 ; @00254
    jz loc_025C ; @00257
    jmp loc_0314 ; @00259
loc_025C:
GameFrameMusicToggleCheck:
; Key mask from IRQ09 (1FC7). 0289 clears SoundOptionBits before 0295 tests it,
; so INT61 0200 at 029C needs an asynchronous writer between them; only then
; does 02A1 test the INT61-returned AX instead of the restored key mask.
    test ax,0x80 ; @0025C
    jz loc_02A1 ; @0025F
    push ax ; @00261
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @00262
    jz loc_0275 ; @00267
    test byte [SoundOptionBits-GameDataImage],0x1 ; @00269
    jz loc_0275 ; @0026E
    mov ax,0x100 ; @00270
    int 0x60 ; @00273
loc_0275:
GameFrameMusicToggleAfterInt60Stop:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @00275
    jz loc_0288 ; @0027A
    test byte [SoundOptionBits-GameDataImage],0x1 ; @0027C
    jz loc_0288 ; @00281
    mov ax,0x0 ; @00283
    int 0x60 ; @00286
loc_0288:
GameFrameMusicToggleRestore:
    pop ax ; @00288
    mov byte [SoundOptionBits-GameDataImage],0x0 ; @00289
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @0028E
    jnz loc_02A1 ; @00293
    test byte [SoundOptionBits-GameDataImage],0x3 ; @00295
    jz loc_02A1 ; @0029A
    mov ax,0x200 ; @0029C
    int 0x61 ; @0029F
loc_02A1:
GameFrameSoundEnableCheck:
    test ax,0x100 ; @002A1
    jz loc_02AB ; @002A4
    mov byte [SoundOptionBits-GameDataImage],0x3 ; @002A6
loc_02AB:
GameFrameQuitCheck:
    test ax,0x20 ; @002AB
    jnz RequestGameFadeOut ; @002AE
    jmp GameFrameSwapAndPace ; @002B0
RequestGameFadeOut:
; Latch end request and closing bit02. Frames continue until transition work
; clears that bit; then timer cleanup and the result-screen JMP execute.
    mov byte [GameEndRequested-GameDataImage],0xff ; @002B3
    mov al,[GameTransitionFlags-GameDataImage] ; @002B8
    or al,0x2 ; @002BB
    mov [GameTransitionFlags-GameDataImage],al ; @002BD
    jmp GameFrameSwapAndPace ; @002C0
GameEndWaitForFade:
    mov al,[GameTransitionFlags-GameDataImage] ; @002C3
    test al,0x2 ; @002C6
    jz loc_02CD ; @002C8
    jmp GameFrameSwapAndPace ; @002CA
loc_02CD:
GameEndAfterFade:
    call PublishBasePaletteBothBanks ; @002CD
GameEndAfterBasePalette:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @002D0
    jz loc_02E3 ; @002D5
    test byte [SoundOptionBits-GameDataImage],0x1 ; @002D7
    jz loc_02E3 ; @002DC
    mov ax,0x100 ; @002DE
    int 0x60 ; @002E1
loc_02E3:
GameEndAfterInt60Stop:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @002E3
    jz loc_02F6 ; @002E8
    test byte [SoundOptionBits-GameDataImage],0x1 ; @002EA
    jz loc_02F6 ; @002EF
    mov ax,0x0 ; @002F1
    int 0x60 ; @002F4
loc_02F6:
GameEndDisableDirtyCells:
    mov byte [DrawingDirtyCellsEnabledByte-GameDataImage],0x0 ; @002F6
    call RestoreTimerState ; @002FB
GameEndAfterTimerRestore:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @002FE
    jnz loc_0311 ; @00303
    test byte [SoundOptionBits-GameDataImage],0x3 ; @00305
    jz loc_0311 ; @0030A
    mov ax,0x200 ; @0030C
; R2:02FB restored timer08 before this guardedAX0200 reset. It clears selected driver state/modes,not the allocation/vector or a fresh level object;25A7&3==0 skips it. PROFILE1A:AH=0001 plus intact actual saves supplies nominal16A9 return preservation,not a global DS/SS/IRQ theorem.
    int 0x61 ; @0030F
loc_0311:
GameEndToResultScreen:
    jmp loc_46EB ; @00311
loc_0314:
GameLevelSkipCheat:
    mov byte [StatusCompletionDisplayValue-GameDataImage],0x64 ; @00314
    call PublishBasePaletteBothBanks ; @00319
GameLevelSkipAfterPalette:
    jmp short GameEndWaitForFade ; @0031C
AdvanceGameTransitionEffects:
; GameTransitionFlags:01 opening fade,02 closing fade,04 delayed opening sound
; sequence. Only the ordinary037C path publishes AL back to the shared byte.
; Opening takes precedence if both fade bits are set. Option FF repeats a
; palette step with raster/timer updates; other options perform one step/tick.
; Delayed sound thresholds use live ForegroundCounter0052 (0F/23/37). Sound
; branches can RET early with service-returned AX; do not promise AL=flags.
    mov al,[GameTransitionFlags-GameDataImage] ; @0031E
    test al,0x1 ; @00321
    jz loc_0342 ; @00323
    cmp byte [ConfigurationOption200E-GameDataImage],0xff ; @00325
    jnz loc_033D ; @0032A
loc_032C:
TransitionOpeningRasterLoop:
    call StepGameOpeningFade ; @0032C
TransitionOpeningRasterAfterStep:
    push ax ; @0032F
    call WaitForDisplayStatusBit3Cycle ; @00330
TransitionOpeningRasterAfterStatus:
    call UpdateTimerPaletteAfter553D ; @00333
TransitionOpeningRasterAfterTimerPalette:
    pop ax ; @00336
    test al,0x1 ; @00337
    jnz loc_032C ; @00339
    jmp short loc_0361 ; @0033B
loc_033D:
TransitionOpeningStep:
    call StepGameOpeningFade ; @0033D
TransitionOpeningAfterStep:
    jmp short loc_0361 ; @00340
loc_0342:
TransitionClosingCheck:
    test al,0x2 ; @00342
    jz loc_0361 ; @00344
    cmp byte [ConfigurationOption200E-GameDataImage],0xff ; @00346
    jnz loc_035E ; @0034B
loc_034D:
TransitionClosingRasterLoop:
    call StepGameClosingFade ; @0034D
TransitionClosingRasterAfterStep:
    push ax ; @00350
    call WaitForDisplayStatusBit3Cycle ; @00351
TransitionClosingRasterAfterStatus:
    call UpdateTimerPaletteAfter553D ; @00354
TransitionClosingRasterAfterTimerPalette:
    pop ax ; @00357
    test al,0x2 ; @00358
    jnz loc_034D ; @0035A
    jmp short loc_0361 ; @0035C
loc_035E:
TransitionClosingStep:
    call StepGameClosingFade ; @0035E
loc_0361:
TransitionDelayedCueCheck:
    test al,0x4 ; @00361
    jz loc_037C ; @00363
    mov dl,[ForegroundCounter0052-GameDataImage] ; @00365
    cmp dl,0xf ; @00369
    jz loc_0380 ; @0036C
    cmp dl,0x23 ; @0036E
    jz loc_0394 ; @00371
    cmp dl,0x37 ; @00373
    jz loc_03AD ; @00376
    jc loc_037C ; @00378
    and al,0xfb ; @0037A
loc_037C:
TransitionPublishFlags:
    mov [GameTransitionFlags-GameDataImage],al ; @0037C
    ret ; @0037F
loc_0380:
TransitionCue0F:
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @00380
    jnz loc_0393 ; @00385
    test byte [SoundOptionBits-GameDataImage],0x3 ; @00387
    jz loc_0393 ; @0038C
    mov ax,0x403 ; @0038E
    int 0x61 ; @00391
loc_0393:
TransitionCue0FReturn:
    ret ; @00393
loc_0394:
TransitionCue23ReleaseStart:
    mov byte [EntityCreationGate-GameDataImage],0xff ; @00394
    cmp byte [ExternalSoundDriverEnabled-GameDataImage],0xff ; @00399
    jnz loc_03AC ; @0039E
    test byte [SoundOptionBits-GameDataImage],0x3 ; @003A0
    jz loc_03AC ; @003A5
    mov ax,0x402 ; @003A7
    int 0x61 ; @003AA
loc_03AC:
TransitionCue23Return:
    ret ; @003AC
loc_03AD:
TransitionCue37LevelMusic:
    test byte [SoundOptionBits-GameDataImage],0x2 ; @003AD
    jz loc_03D6 ; @003B2
; S13: BYTE0054 ->AL,then AH03; never a word OR with neighboring0055.0457 accepts only01..15 before a stream-root lookup,so unchecked main song-index values cannot add roots under its serial initialized DF0/nonalias/live-image contract.03B9/03BE test music bit2 only;2010 is not checked.05FA can free without restoringINT61,and02A6 can later set25A7=3;music enabled does not prove live driver ownership. See adlib_StreamCommandTargets.producer_domain.
    mov al,[LevelSoundId-GameDataImage] ; @003B4
    mov ah,0x3 ; @003B7
; R2 UNCONDITIONAL recovered-engine implication: each INT61 clearsIF and AdLib neverSTIs,so timer1872 cannot interleave inside this setter/update. It CAN run after03B9 IRET and before03BE,consumeED and advance once;03BE then advances again. No queue or combined atomic request+update. D/E/SS stay caller-owned and restored through actual nonalias saves;global main segment/DF and escaped01EA domains remain UNRESOLVED.
; AH03 latches a song request only; AdLib0457 normally copies ED only while current-song gateEE==0. Immediate AH00 at03BE performs processing. Stop/reset/stream83 clear ED andEE together; a queued ID is not guaranteed to survive completion.
    int 0x61 ; @003B9
TransitionCue37AfterSelect:
    mov ax,0x0 ; @003BB
    int 0x61 ; @003BE
TransitionCue37Return:
    ret ; @003C0
StepGameOpeningFade:
; AL carries transition flags. Set04 before saving AX; palette child's ZF must
; survive POP AX. Clear01 only on completed palette change.03D6 is a shared RET,
; also entered by the sound guard at03B2 without a new stack save.
    or al,0x4 ; @003C1
    push ax ; @003C3
    mov bx,0x604 ; @003C4
    nop ; @003C7
    mov cx,0x10 ; @003C8
    mov dx,0x8 ; @003CB
    call StepSplitPaletteToTargets ; @003CE
OpeningFadeAfterPaletteStep:
    pop ax ; @003D1
    jnz loc_03D6 ; @003D2
    and al,0xfe ; @003D4
loc_03D6:
TransitionSharedReturn:
    ret ; @003D6
StepGameClosingFade:
; Preserve AL around the palette step and consume its returned ZF after POP AX;
; clear02 on completion. No independent IRQ or complete fade scheduler here.
    push ax ; @003D7
    mov cx,0x10 ; @003D8
    mov dx,0x8 ; @003DB
    call StepSplitPaletteToSlot1 ; @003DE
ClosingFadeAfterPaletteStep:
    pop ax ; @003E1
    jnz loc_03D6 ; @003E2
    and al,0xfd ; @003E4
    ret ; @003E6
InitializeGameSession:
; Session state producer: initial transition01/end00, countdown divider11,
; pointer150/100 and action selector2. Level-record initialization later replaces
; the provisional view origin and creation limit from the loaded header.
; Earlier4551 clears DS:0000..0FC9 (DF clear) before loading the level at0FCB;
; it resets slot/count/record storage. This entry does not clear that array.
; Startup's0000..2011 clear is a third, process-wide initialization lifetime.
    mov word [LevelViewOriginPixels-GameDataImage],0x218 ; @003E7
    mov word [LevelViewOriginBytes-GameDataImage],0x43 ; @003ED
    mov byte [0x1a],0x0 ; @003F3
    mov word [PointerX-GameDataImage],0x96 ; @003F8
    mov word [PointerY-GameDataImage],0x64 ; @003FE
    mov byte [LevelCreationLimit-GameDataImage],0xc8 ; @00404
; S19 double-wait-004a: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; 004A stored/startup/session zero producers are known; actual-game FF producer remains
; unknown.01D2 on exactFF waits for two observed1FCD changes without local STI/timeout.
; Dependencies: Indexed/string/word/stack/provider writer domains; timer delivery and
; wrap/coalescing; raw FF alias witnesses do not prove a game producer.
; S14: dedicated session writer resets DS004A=00 after level4551. No
; dedicated actual-game FF producer identified; indexed/decoder/segment alias
; writers can setFF,so this clear does not prove a persistent zero invariant.
    mov byte [FrameDoubleWaitFlag004A-GameDataImage],0x0 ; @00409
    mov byte [LevelCountdownTensDigit-GameDataImage],0x30 ; @0040E
    mov byte [LevelCountdownOnesDigit-GameDataImage],0x30 ; @00413
    mov byte [GameCountdownTickCounter-GameDataImage],0x11 ; @00418
    mov byte [GameCountdownTickReload-GameDataImage],0x11 ; @0041D
    mov byte [EntityActionSelector-GameDataImage],0x2 ; @00422
    mov byte [StatusIconDisplaySnapshot-GameDataImage],0x3 ; @00427
    mov byte [EntityPointCount-GameDataImage],0x50 ; @0042C
    mov byte [GameTransitionFlags-GameDataImage],0x1 ; @00431
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @00436
    mov [InputActionSnapshot1FD4-GameDataImage],al ; @00438
    mov [ForegroundCounter1FD3-GameDataImage],al ; @0043B
    mov [GameEndRequested-GameDataImage],al ; @0043E
    mov [DrawingDirtyCellsEnabledByte-GameDataImage],al ; @00441
    mov [ForegroundCounter0052-GameDataImage],al ; @00444
    mov [EntityCreationGate-GameDataImage],al ; @00447
; UNCONDITIONAL loader/arithmetic: SS=load+143E,initialSP4AF4. Forward clears end48F3,so only512 bytes lie above them; depth512 reaches48F4,514 writes48F2..48F3. This is not an exclusively owned stack allocation. DATA-CONDITIONAL original level007.dat section1 object10 +ground3o.dat type5 writes A5 at4816..4825 and49B6..49C5; depth304 already intersects the second row. Whole-program saved-frame survival and IRQ/provider depth remain UNRESOLVED.
    push ss ; @0044A
    pop es ; @0044B
    mov di,0x12 ; @0044C
    mov cx,0x42a0 ; @0044F
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @00452
; S19 DF-site census rep stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED
; for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep stosb ; @00454
    push ss ; @00456
    pop es ; @00457
    mov di,0x42b2 ; @00458
    mov cx,0x642 ; @0045B
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @0045E
; S19 DF-site census rep stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED
; for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep stosb ; @00460
; [00462] The0FB2 child reinstalls all nine drawing callback words after the level455B clear and before046B initialization/header copy. This ordering is needed for first3140 publication and the conditional nine-value preservation proof; it does not close service/IRQ/alias writers.
; CONTRACT: 03E7..0461 initializes live DS fields, then clears SS:0012..42B1
; and SS:42B2..48F3 using the original DF-sensitive REP STOSB loops. The
; native parent composes every actual CALL/RET through the 04CF outer RET with
; live child services, flags, segments and changed returns. READINESS: READY in
; the normal-level domain; IRQ edges enter only at 04AA/04BA. Special-resource
; 1A7B, dynamic probe 1407 and general preemption stay explicit boundaries.
InitializeGameAfterStateClear:
    call SetupGameVideoAndSpriteCallbacks ; @00462
InitializeGameAfterVideoSetup:
    call PublishGameBasePalette ; @00465
; T3 session boundary:0468 runs after455D resources/briefing and0462 video/0465 palette, but
; before046B header initialization/0492 game IRQ install. It inherits previous calibration
; probe enables/pointers;455B and03E7 did not restore them. If the dynamic gate applies,13DC
; rearms later flags again even with nonzero old reload. If bypassed, prior flags/pairs
; remain. DATA-CONDITIONAL supplied ground0o..ground4o.dat, each0420, excludes GROUND table
; overwrite only; global writer/alias/IRQ closure is UNRESOLVED.
InitializeGameAfterPalette:
    call CalibrateGameTimerReload ; @00468
InitializeGameAfterTimerCalibration:
    call InitializeLevelFromRecord ; @0046B
InitializeGameAfterLevelInitialization:
    cmp byte [MouseServicesDisabledByte-GameDataImage],0xff ; @0046E
    jz InitializeGameVisibilityAndStatus ; @00473
    mov ax,0x4 ; @00475
    mov cx,0x96 ; @00478
    mov dx,0x64 ; @0047B
    int 0x33 ; @0047E
; VISIBILITY DF: INT33 at047E can affect live flags before0480; no local CLD. The preceding normal DAT decode CLDs, but later platform returns and saved frames retain their own contract. This call and foreground/IRQ scroll callers must each establish DF0 for the nominal<=50 callback-preservation domain.
InitializeGameVisibilityAndStatus:
; Child sequence: visibility/first create/fade seed/sound id/pages/status ->
; install IRQ08 -> object animation/draw, status backdrop/display (first frame).
; The following calibration needs two scheduled INT08 flag publications.
    call RebuildViewVisibilityMap ; @00480
InitializeGameAfterVisibility:
    call CreateEntityRecordIfDue ; @00483
InitializeGameAfterFirstCreate:
    call SeedGameFadePalette ; @00486
InitializeGameAfterFadeSeed:
    call SelectLevelSoundId ; @00489
InitializeGameAfterSoundSelect:
    call InitializeGameDrawingPages ; @0048C
InitializeGameAfterDrawingPages:
    call InitializeStatusDisplay ; @0048F
InitializeGameAfterStatusInit:
    call InstallGameTimerVector ; @00492
InitializeGameAfterTimerInstall:
    call AdvanceLevelObjectAnimations ; @00495
InitializeGameAfterObjectAnimations:
    call DrawLevelObjectGraphics ; @00498
InitializeGameAfterObjectGraphics:
    call CopyStatusBackdropToDrawingPage ; @0049B
InitializeGameAfterStatusBackdrop:
    call UpdateStatusDisplay ; @0049E
InitializeGameAfterStatusDisplay:
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @004A1
    db 0x33,0xd2 ; ENCODED: xor dx,dx (NASM chooses a different encoding) ; @004A3
    mov byte [TimerChainFlag1FCF-GameDataImage],0x0 ; @004A5
GameWaitCalibrationFirstEdge:
; First edge aligns the measurement; second edge terminates the decrement loop.
; Timer tail183E writes exactFF to live DS:1FCF. An unbound IRQ schedule hangs
; the original too; verification must bound its fixture, not change this code.
    cmp byte [TimerChainFlag1FCF-GameDataImage],0xff ; @004AA
    jnz GameWaitCalibrationFirstEdge ; @004AF
    mov byte [TimerChainFlag1FCF-GameDataImage],0x0 ; @004B1
GameMeasureForegroundWait:
    dec cx ; @004B6
    jnz GameCheckCalibrationSecondEdge ; @004B7
    dec dx ; @004B9
GameCheckCalibrationSecondEdge:
    cmp byte [TimerChainFlag1FCF-GameDataImage],0xff ; @004BA
    jnz GameMeasureForegroundWait ; @004BF
; Literal result: ADD CX,CX, ADC DX,DX, NEG DX. There is no low-word NEG and no
; carry propagation after NEG DX; preserve this producer with its0164 consumer.
    db 0x03,0xc9 ; ENCODED: add cx,cx (NASM chooses a different encoding) ; @004C1
    db 0x13,0xd2 ; ENCODED: adc dx,dx (NASM chooses a different encoding) ; @004C3
    neg dx ; @004C5
    mov [ForegroundWaitLowWord-GameDataImage],cx ; @004C7
    mov [ForegroundWaitHighWord-GameDataImage],dx ; @004CB
    ret ; @004CF
; R2 UNCONDITIONAL recovered cleanup census:04D0/04EA do not save/restore61,reset AdLib or explicitly free its block.16A9 restores08 only. DOS4C ends the process;ordinary DOS reclamation ends live allocation ownership,leaving no game-code61 restoration. Private restore0FAE uses mutable1FC6;external/selector/physical aliases remain UNRESOLVED.
loc_04D0:
; Nonreturning cleanup continuation. Keep each child CALL/actual RET word live.
; Video-returned DS selects the mouse gate;04EA is also reached by JMP106B.
; DOS4C terminates; its next numerical IP is not an executable cleanup exit.
DatFatalTransfer:
    call RestoreTimerState ; @004D0
CleanupAfterTimer:
    call RestoreKeyboardVector ; @004D3
CleanupAfterKeyboard:
    call RestorePrivateVector ; @004D6
CleanupAfterPrivate:
    call RestoreVideoModeAndPage ; @004D9
CleanupAfterVideo:
    cmp byte [MouseServicesDisabledByte-GameDataImage],0xff ; @004DC
    jz ExitAfterKeyboardRestore ; @004E1
    mov ax,0xc ; @004E3
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @004E6
CleanupMouseInterrupt:
    int 0x33 ; @004E8
ExitAfterKeyboardRestore:
    call RestoreKeyboardVector ; @004EA
CleanupAfterFinalKeyboard:
    mov dx,CleanupExitMessage-GameDataImage ; @004ED
    mov ah,0x9 ; @004F0
CleanupMessageInterrupt:
    int 0x21 ; @004F2
    mov ax,0x4c00 ; @004F4
CleanupTerminateInterrupt:
    int 0x21 ; @004F7
InitializeVgaRegisterMirrors:
CleanupAfterTerminate:
; CONTRACT: read BIOS0040:0063, store CRTC base at live DS:1FDA, then add6
; to DL alone before storing DS:1FDC. Preserve byte carry/overflow/flags.
; Nine literal live-SS word stores include two writes to0010, endingFF08;
; offset000E remains untouched. No local CLI/STI or register save frame.
; Core precedes actual RET054D; aliases and original startup quirk retained.
    mov ax,0x40 ; @004F9
    mov es,ax ; @004FC
    mov dx,[es:0x63] ; @004FE
    mov [DisplayControllerBasePort-GameDataImage],dx ; @00503
    add dl,0x6 ; @00507
    mov [DisplayStatusPort1FDC-GameDataImage],dx ; @0050A
    mov ax,0x2 ; @0050E
    mov [ss:VgaMapMaskMirror-RuntimeStackFrame],ax ; @00511
    mov ax,0x0 ; @00515
    mov [ss:VgaSetResetMirror-RuntimeStackFrame],ax ; @00518
    mov ax,0x1 ; @0051C
    mov [ss:VgaEnableSetResetMirror-RuntimeStackFrame],ax ; @0051F
    mov ax,0x2 ; @00523
    mov [ss:VgaColorCompareMirror-RuntimeStackFrame],ax ; @00526
    mov ax,0x3 ; @0052A
    mov [ss:VgaDataRotateMirror-RuntimeStackFrame],ax ; @0052D
    mov ax,0x4 ; @00531
    mov [ss:VgaReadMapMirror-RuntimeStackFrame],ax ; @00534
    mov ax,0x5 ; @00538
    mov [ss:VgaGraphicsModeMirror-RuntimeStackFrame],ax ; @0053B
    mov ax,0xf07 ; @0053F
    mov [ss:VgaColorCareMirror-RuntimeStackFrame],ax ; @00542
    mov ax,0xff08 ; @00546
    mov [ss:VgaReadMapMirror-RuntimeStackFrame],ax ; @00549
VgaMirrorInitializeReturn:
    ret ; @0054D
; R2: successful AdLib05A4..05B3 returns before Tandy05CA/free05FA.00AB is the sole decoded caller;0570 allocation CF is unchecked,057B installs before058D load. Process-lived A/vector binding is PLATFORM-CONDITIONAL on profile21:AH=0025/0048/0049/003D/003F/0043(AL00),successful services/full pinned cache-off reads,intact saves/returns,separated allocations and no external/alias/unclosed-control writer. Menu/level/session paths do not explicitly reload/free it. Sound bits alone do not prove ownership. See src/sound/adlib.asm R2 and build/static/r2-adlib-life.md.
; S18 SOUND-SELECTION INVENTORY (all paths retained):
; 054E input2010==FF (/a),or initial5AD8-paragraph DOS48 failure055E,
; ->05FC sets2010=0,25A7=1,menu1F71=1: PC speaker. Otherwise free probe
; block,allocate0567 paragraphs (second CF unchecked),installINT61 AX:0,
; decode ADLIB.DAT at058D,initialize speaker defaults0591/0596,queryAH1.
; AL!=0 ->05A4 sets2010=FF,25A7=3,1F71=2 (AdLib).
; AL==0 ->060C BIOS Tandy-page test via05B5. ReturnedBX==0 ->AL0 ->free
; allocation05FA ->05FC speaker. NonzeroBX ->ALFF ->decodeTANDYSND.DAT
; over same block05CA,setFF/3/2,INT61 sequence0301,00xx,0300,02xx,00xx.
; xx is live returnedAL,not forced0. Both page-test branches restore with
; AX=(savedBL<<8)|05,discarding savedBH; BIOS semantics remain a seam.
; Tandy has no second presence query. Its image54C6 retains AdLib54C6..566C;
; word5630 and byte5958 have distinct in/out-of-allocation roles (see drivers).
; Fallback frees block WITHOUT restoringINT61. Saved/changed DOS allocation
; state and INT61 lifetime remain obligations; later sound bits alone do not
; prove live driver ownership. Failed resource paths retain retry/fatal edges.
; MAIN.DAT section5 is ALWAYS decoded5972 over main8420..8715,even with
; external sound.1644 installsINT60 at relocated0842:0182 along withINT08;
; watchdog can reinstall without reload.16A9 restoresINT08,notINT60/61.
; Timer185F selectsINT60 tick on odd phase when2010!=FF and25A7&1;
; timer1872 selectsINT61 every enabled IRQ when2010==FF and25A7&3.
; 1F71 menu ordinal maps through CS44E9 to nominal25A7 bits0/1/3; toggles
; and separate music/effect gates remain original behavior,not driver unload.
; Muted services omit original PIT/PSG/OPL behavior. Device/IRQ equivalence
; and external-driver installation/free lifetime are not closed by native stubs.
InitializeSoundDriver:
; READINESS CONDITIONAL (c/sound_driver_init.c): 2010=FF (switch a) skips to
; the 060B fallback. Else probe-allocate 5AD8, free, allocate 0567 (CF ignored),
; install INT61 at AX:0000 before loading adlib.dat; writes 25A7=1/1F71=1
; before INT61 AH=1 detection; success 2010=FF, 25A7=3, 1F71=2. Failed AdLib
; tries the BIOS page probe 060C for Tandy (tandysnd.dat); negative frees the
; block and leaves 2010=0, 25A7=1, 1F71=1. INT61 vector stays installed.
    cmp byte [0x2010],0xff ; @0054E
    jnz loc_0558 ; @00553
    jmp loc_05FC ; @00555
loc_0558:
    mov ah,0x48 ; @00558
    mov bx,0x5ad8 ; @0055A
    nop ; @0055D
    int 0x21 ; @0055E
    jnc loc_0565 ; @00560
    jmp loc_05FC ; @00562
loc_0565:
    mov es,ax ; @00565
    mov ah,0x49 ; @00567
    int 0x21 ; @00569
    mov ah,0x48 ; @0056B
; TANDYSND state extent:allocation0567 paragraphs ends5670;driver image54C6;01A5 writes5630 inside allocation/residual AdLib suffix,01D5/0629 use5958 outside it (extent5959,2E9 extra bytes). Preserve unchecked second allocation CF,real segment adjacency and selective reset;do not enlarge allocation/shadow transpose to hide original effect.
    mov bx,0x567 ; @0056D
    int 0x21 ; @00570
    push ds ; @00572
    mov ds,ax ; @00573
    push ax ; @00575
    mov ax,0x2561 ; @00576
    db 0x33,0xd2 ; ENCODED: xor dx,dx (NASM chooses a different encoding) ; @00579
    int 0x21 ; @0057B
    pop ax ; @0057D
    pop ds ; @0057E
    push ax ; @0057F
    push ds ; @00580
    mov es,ax ; @00581
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @00583
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @00585
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @00587
    lea dx,[0x2573] ; @00589
; Executable DAT input uses allocated0567h-paragraph block, not main DS.
; AdLib reads000Ah header then32B2h payload at0, output566Dh; Tandy05CA
; reads000Ah then3065h, output54C6h into same block. Sizes are file facts,
; not validated. INT61 installed before loading; failed AdLib can be replaced
; by Tandy, negative fallback frees block without restoring INT61. Process
; driver lifetime and platform/IRQ seams remain original obligations.
    call LoadDatResource ; @0058D
    pop ds ; @00590
    mov byte [0x25a7],0x1 ; @00591
    mov byte [0x1f71],0x1 ; @00596
    mov ah,0x1 ; @0059B
    int 0x61 ; @0059D
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @0059F
    pop ax ; @005A1
    jz loc_05B4 ; @005A2
    mov byte [0x2010],0xff ; @005A4
    mov byte [0x25a7],0x3 ; @005A9
    mov byte [0x1f71],0x2 ; @005AE
    ret ; @005B3
loc_05B4:
    push ax ; @005B4
    call ProbeTandyVideoPage ; @005B5
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @005B8
    pop ax ; @005BA
    jz loc_05F6 ; @005BB
    push ds ; @005BD
    mov es,ax ; @005BE
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @005C0
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @005C2
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @005C4
    lea dx,[0x257d] ; @005C6
    call LoadDatResource ; @005CA
    pop ds ; @005CD
    mov byte [0x2010],0xff ; @005CE
    mov byte [0x25a7],0x3 ; @005D3
    mov byte [0x1f71],0x2 ; @005D8
    mov al,0x1 ; @005DD
    mov ah,0x3 ; @005DF
    int 0x61 ; @005E1
    mov ah,0x0 ; @005E3
    int 0x61 ; @005E5
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @005E7
    mov ah,0x3 ; @005E9
    int 0x61 ; @005EB
    mov ah,0x2 ; @005ED
    int 0x61 ; @005EF
    mov ah,0x0 ; @005F1
    int 0x61 ; @005F3
    ret ; @005F5
loc_05F6:
    mov es,ax ; @005F6
    mov ah,0x49 ; @005F8
    int 0x21 ; @005FA
loc_05FC:
    mov byte [0x2010],0x0 ; @005FC
    mov byte [0x25a7],0x1 ; @00601
    mov byte [0x1f71],0x1 ; @00606
    ret ; @0060B
ProbeTandyVideoPage:
; AH0F, save BX, AX=0580 BX=0; POP AX/MOV AH,05/XCHG gives AX=(saved BL<<8)|05,
; discarding BH (quirk). Returned BX zero -> AL=0, else AL=FF.
    mov ah,0xf ; @0060C
    int 0x10 ; @0060E
    push bx ; @00610
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @00611
    mov ax,0x580 ; @00613
    int 0x10 ; @00616
    pop ax ; @00618
    mov ah,0x5 ; @00619
    xchg al,ah ; @0061B
    db 0x0b,0xdb ; ENCODED: or bx,bx (NASM chooses a different encoding) ; @0061D
    jnz loc_0626 ; @0061F
; S19 dynamic-bios-restore: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; 060E savesBX;0618 POP AX,0619 AH05,061B XCHG AL,AH yields AX=(savedBL<<8)|05. AH is saved
; undocumented BL,not fixed05.
; Dependencies: Need actual BL convention/provenance through060E and earlier detector; no
; function/results fabricated.
    int 0x10 ; @00621
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @00623
    ret ; @00625
; S19 dynamic-bios-restore: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; 060E savesBX;0618 POP AX,0619 AH05,061B XCHG AL,AH yields AX=(savedBL<<8)|05. AH is saved
; undocumented BL,not fixed05.
; Dependencies: Need actual BL convention/provenance through060E and earlier detector; no
; function/results fabricated.
loc_0626:
    int 0x10 ; @00626
    mov al,0xff ; @00628
    ret ; @0062A
CheckStartupProtection:
; Startup admission check. FAT id 1FDE != F8 probes original floppy media
; (063E); F8 uses the russell.dat run counter (0E66): media checked only when
; the incremented counter wraps to 0 (every tenth run) or the file can't be
; opened. 0EC2 writes 0100 live DS bytes from 252A, results unchecked. 063E
; forces DL=0, uses restored INT3/INT1 protection and a CS-relative sector
; buffer; a completed probe zeroes only its chosen 512 bytes. Failure -> 0EDF
; cleanup/exit; success RET 00E3. No pass latch. READINESS: wrapper READY and
; translated (c/protection.c, 0EDF via framed restore cores); 063E is an explicit
; PASS/FAIL/UNSUPPORTED provider that must reproduce buffer/IVT/table restoration,
; assuming TF/DF clear, disjoint memory and no asynchronous observer.
    mov al,[StartupFatIdByte1FDE-GameDataImage] ; @0062B
    cmp al,0xf8 ; @0062E
    jnz loc_0635 ; @00630
    jmp loc_0E66 ; @00632
loc_0635:
    call ProbeOriginalFloppyMedia ; @00635
    jnc loc_063D ; @00638
    jmp loc_0EDF ; @0063A
loc_063D:
    ret ; @0063D
ProbeOriginalFloppyMedia:
; CONDITIONAL: known 0635/0E99/0EB2 calls enter with TF clear and ordinary
; disjoint code, IVT, SS stack, game DS and floppy-table storage. DL is forced
; to 0; 0698's DL>=2 absolute-disk arm is not selected in this domain. Other
; entries/aliases remain obligations, including the decoded INT25/26 gates.
; Saves DS/ES/CX/SI/DI/BP and IVT0..4 (20 bytes); DS becomes SS at 066A.
; Protected 066D allocates 22h bytes at SS:BP. Normal completion clears the
; selected 512-byte CS buffer, restores the saved 11-byte floppy table, IVT0..4,
; encoded stream/INT1 and saved registers, then 0E3A returns admission CF.
; AX/BX carry the CRC pair (early failure: both 0); DL is the selected drive.
; DX otherwise follows the original arithmetic/services; DF is cleared at 08D2.
; Saved TF/IF are toggled together at each INT3, not forced to constants.
; With TF-clear, IF-preserving disk returns and matched toggles, exit TF=0 and
; IF=entry IF. INT1's STI still permits IRQ observation inside the transport.
;
; Smallest instruction-level service domain for this entry: BIOS tick byte
; 0000:046C (or DH if CX=9299), the INT1E table, and INT13 AH=00/02. Carry actual
; service registers, saved FLAGS/segments and sector bytes; signature sectors
; can be inspected despite BIOS error, so read failure is not a uniform rule.
; The transport below and src/protection/*.asm owns instruction-word mutation.
; A coarser 063E outcome substitution may hide transient vector/code/table
; writes only at a quiescent boundary. It must supply the actual pre-RET state,
; stack residue if observed, any critical-error/device events and admission;
; clear exactly the selected buffer and retain the other buffer/gap/seed bytes.
; Current c/protection.c exposes this media seam, not an INT1/INT3 translation.
; Equivalence to unrestricted media/IRQ/alias behavior is unverified; PASS is
; not a fabricated BIOS success. Unsupported service is distinct from CF fail.
    db 0x32,0xd2 ; ENCODED: xor dl,dl (NASM chooses a different encoding) ; @0063E
    push ds ; @00640
    push es ; @00641
    push cx ; @00642
    push si ; @00643
    push di ; @00644
    push bp ; @00645
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @00646
    mov ds,si ; @00648
loc_064A:
    push word [si] ; @0064A
    add si,byte +0x2 ; @0064C
    cmp si,byte +0x14 ; @0064F
    jnz loc_064A ; @00652
    pushf ; @00654
    cli ; @00655
    call InstallProtectionInt3FromReturnAddress ; @00656
InstallProtectionInt3FromReturnAddress:
; CALL-next, not a leaf RET: consume 0659, add 075A -> CS:0DB3 in IVT3.
; CLI protects installation; POPF restores the flags saved at 0654. SI=CS,
; DS=SS at 066C; INT3 enables the tf_on view at saved return CS:066D.
    pop word [0xc] ; @00659
    add word [0xc],0x75a ; @0065D
    push cs ; @00663
    pop si ; @00664
    mov [0xe],si ; @00665
    popf ; @00669
    push ss ; @0066A
    pop ds ; @0066B
    int3 ; @0066C
ProtectionEncodedDiskEntry:
; Stored encoding is not the executed stream. src/protection/stream.asm lists
; each instruction in tf_on/tf_off state; src/protection/int1.asm is the whole
; negated-handler view. A two-byte patch can overlap the following instruction:
; exposing 066D gives 50 E9, but restoring it before 066E exposes E8 00 00.
; These stitched views are inventories, never replacement runtime images.
; CODE: stored state_specific_code; execution views in src/protection
    db 0x90,0x8e,0xde,0x00,0x1b,0xfa,0xd2,0x03,0xcb,0xa8,0xd9,0xaa,0x9f,0x42,0xc2,0x8a ; @0066D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x25,0x68,0x53,0x0f,0xd2,0x27,0x7e,0x4f,0x0f,0x5c,0x3e,0x0f,0xf5,0xe5,0x95,0xf3 ; @0067D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x10,0x02,0x87,0x79,0x1d,0x22,0x4e,0x57,0x8b,0xbf,0x00,0x01,0x04,0x02,0x84,0xc1 ; @0068D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x4d,0x7e,0x0c,0xeb,0x97,0x02,0x39,0xe2,0x02,0xd3,0x8f,0x00,0x92,0xe8,0x5a,0x50 ; @0069D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x02,0x0c,0x8f,0xbf,0x6a,0xc6,0x03,0x57,0xfb,0xae,0xc9,0x2a,0x2a,0x03,0x97,0xfd ; @006AD
; CODE: stored state_specific_code; execution views in src/protection
    db 0xa5,0xe3,0xc0,0x70,0xbb,0x68,0x0a,0x97,0x6c,0x00,0xcf,0xf2,0x02,0x88,0x3e,0x99 ; @006BD
; CODE: stored state_specific_code; execution views in src/protection
    db 0x0a,0x75,0xa4,0x00,0x5f,0xfd,0x02,0xfd,0x89,0x32,0x05,0x04,0x01,0x33,0x8b,0x0a ; @006CD
; CODE: stored state_specific_code; execution views in src/protection
    db 0x51,0x14,0x00,0x3f,0x0b,0x01,0xcf,0xc6,0x04,0x06,0xd7,0x35,0x17,0x20,0xe0,0xff ; @006DD
; CODE: stored state_specific_code; execution views in src/protection
    db 0xfa,0x76,0x1e,0x20,0x35,0x07,0x95,0x02,0x3d,0x25,0x01,0x3e,0x25,0x47,0xc3,0x0a ; @006ED
; CODE: stored state_specific_code; execution views in src/protection
    db 0x5f,0xd9,0x84,0xfa,0x00,0x2d,0xcd,0x9c,0xfc,0x00,0x74,0xfb,0x25,0xc9,0x87,0xb6 ; @006FD
; CODE: stored state_specific_code; execution views in src/protection
    db 0x09,0x0f,0x05,0xd9,0x02,0xc7,0xac,0x00,0x24,0x3b,0x22,0x14,0x30,0x32,0x76,0xca ; @0070D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x02,0xd2,0xf9,0x00,0xcb,0xb8,0x02,0x01,0x13,0x72,0x00,0x69,0xf6,0xea,0x55,0x02 ; @0071D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x0c,0x13,0x61,0x00,0x4e,0xe0,0xd2,0x3e,0x71,0xc4,0x00,0x05,0xba,0x7c,0xcd,0x00 ; @0072D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x8d,0x80,0x01,0x39,0xba,0x02,0x01,0x13,0x8d,0x00,0x97,0xcb,0x16,0x2e,0x02,0x0c ; @0073D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x13,0x80,0x00,0x8d,0xd2,0x6d,0x1c,0x1e,0x01,0x85,0x02,0x0b,0x13,0xb2,0x00,0xe9 ; @0074D
; CODE: stored state_specific_code; execution views in src/protection
    db 0xde,0x2f,0x04,0x1e,0xca,0x97,0x00,0xa2,0xe2,0x3a,0x44,0x03,0x02,0x8d,0xf6,0x64 ; @0075D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x6c,0x03,0x03,0x8d,0xfe,0x5b,0x0e,0x00,0xd8,0x07,0x3c,0xf9,0xcf,0x78,0x62,0xe4 ; @0076D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x98,0x8e,0x31,0xff,0x65,0x88,0x72,0x1e,0xd8,0x4b,0x09,0x04,0x64,0xa9,0x06,0x25 ; @0077D
; CODE: stored state_specific_code; execution views in src/protection
    db 0xa4,0x00,0x3e,0x80,0x0a,0x76,0x9c,0x0c,0x00,0xa0,0x20,0x00,0x00,0x7e,0x06,0x99 ; @0078D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x92,0xb8,0xd2,0x4a,0x04,0x1e,0xd1,0x49,0x36,0x6c,0x04,0x75,0x77,0xf3,0x04,0x91 ; @0079D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x80,0x03,0xa5,0x78,0x53,0x01,0xd1,0x8b,0x01,0x2a,0xac,0x13,0xa4,0x00,0x0f,0xca ; @007AD
; CODE: stored state_specific_code; execution views in src/protection
    db 0x12,0x83,0xd0,0x01,0xb7,0x7f,0x00,0x81,0x03,0x80,0x8c,0x84,0x66,0x88,0x02,0x01 ; @007BD
; CODE: stored state_specific_code; execution views in src/protection
    db 0x8e,0xfb,0xe8,0xec,0x5a,0x54,0x3e,0x31,0x47,0xeb,0x0a,0x96,0x7d,0xd5,0xbc,0x75 ; @007CD
; CODE: stored state_specific_code; execution views in src/protection
    db 0x00,0x95,0x81,0x02,0x0c,0x8f,0xd7,0x6a,0x16,0x03,0xf5,0xc9,0x44,0x38,0x02,0xc1 ; @007DD
; CODE: stored state_specific_code; execution views in src/protection
    db 0x70,0x3b,0x01,0xaf,0xcd,0x44,0x39,0x02,0xc8,0x42,0xd3,0x33,0x7f,0x11,0x44,0x3c ; @007ED
; CODE: stored state_specific_code; execution views in src/protection
    db 0xcf,0xc1,0x00,0x95,0x2a,0x00,0x96,0x9d,0x6e,0xb0,0x11,0x5b,0xaa,0x0a,0x28,0x2c ; @007FD
; CODE: stored state_specific_code; execution views in src/protection
    db 0x4e,0x18,0x03,0xbf,0x40,0xb8,0x00,0x67,0x3e,0x00,0xb8,0x38,0xfa,0xae,0xce,0xd4 ; @0080D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x0a,0xd7,0x94,0x02,0x0c,0x8f,0xe4,0x63,0xf0,0x66,0xa7,0x1a,0x00,0xe1,0xb9,0x03 ; @0081D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x8f,0xbe,0x01,0x80,0x0c,0x47,0xe0,0x00,0xd7,0x3a,0x00,0x73,0x8c,0x13,0x0f,0x58 ; @0082D
; CODE: stored state_specific_code; execution views in src/protection
    db 0x00,0x06,0x8b,0xf0,0x01,0x69,0xff,0xd5,0x59,0x96,0x8a,0x95,0x0e,0x02,0x08,0xfe ; @0083D
; S14 U002: [0084D,00852) stored bytes remain UNKNOWN.
; Neighbours: P 0084B jmp 0x852 [tf_on]; N 00852 push cx [tf_on].
; Known key data 0850..0851=030E for next0852/0853 supplies word[-2] bytes read by plaintextINT1 0E20 and previous-patch restoration0E0B. Existing overlay is not repeated. First three stored bytes retain unknown structural role; no state-CFG edge enters this run. Stored motif is not decoded active stream.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; TF-on JMP084B skips 084D..0851. Decoder0E20 at target0852 reads the last
; two as key word030E; target0853 also reads0851. First three remain unexplained;
; no incoming write entry or padding role is proved. Keep canonical UNKNOWN.
; UNKNOWN: unresolved bytes
    db 0x7e,0xc5,0x44 ; @0084D
ProtectionBiosReadDecodeSeed:
    db 0x0e,0x03 ; @00850
; CODE: stored state_specific_code; execution views in src/protection
    db 0xb2,0x41,0x98,0x00,0x9e,0xab,0x72,0xa9,0x90,0xcb,0x0e,0xad,0xbc,0x0a,0x0c,0xa4 ; @00852
; CODE: stored state_specific_code; execution views in src/protection
    db 0x02,0x3c,0xac,0x00,0x4f,0xcb,0x05,0x34,0xac,0xe5,0xae,0xb4,0xdc,0x0e,0x02,0x1a ; @00862
; CODE: stored state_specific_code; execution views in src/protection
    db 0x8f,0xc9,0x02,0x8c,0xa3,0x25,0x7f,0xf2,0x0e,0x25,0x08,0xb0 ; @00872
; S14 U003: [0087E,00883) stored bytes remain UNKNOWN.
; Neighbours: P 0087C jmp 0x883 [tf_on]; N 00883 push cx [tf_on].
; Known key data 0881..0882=260E for next0883/0884 supplies word[-2] bytes read by plaintextINT1 0E20 and previous-patch restoration0E0B. Existing overlay is not repeated. First three stored bytes retain unknown structural role; no state-CFG edge enters this run. Stored motif is not decoded active stream.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; TF-on JMP087C skips 087E..0882. Target0883 reads0881..0882 as key word260E;
; target0884 also reads0882. First three remain unexplained; stored26 does not
; prove an executed INT26 selector producer. Key-data overlay, UNKNOWN retained.
; UNKNOWN: unresolved bytes
    db 0x7e,0x59,0x44 ; @0087E
ProtectionAbsoluteReadDecodeSeed:
    db 0x0e,0x26 ; @00881
; CODE: stored state_specific_code; execution views in src/protection
    db 0xb2,0x0b,0x98,0x00,0x9e,0xab,0x48,0xee,0x00,0xe4,0xb8,0x08,0x01,0x00,0x76,0x22 ; @00883
; CODE: stored state_specific_code; execution views in src/protection
    db 0x90,0x78,0x04,0xb6,0x08,0xff,0xd7,0x4f,0x06,0x14,0xfa,0x13,0x55,0x0a,0xec,0xea ; @00893
; CODE: stored state_specific_code; execution views in src/protection
    db 0x00,0xa0,0xa8,0x04,0x47,0xfe,0x00,0x5e,0xa6,0x31,0xb1,0x7e,0x4a,0x5a,0xa8,0xca ; @008A3
; CODE: stored state_specific_code; execution views in src/protection
    db 0xd1,0x0e,0x26,0x97,0xb0,0x39,0x76,0x04,0xfa,0x1a,0x04,0x9a,0xa3,0x40,0xfe,0x00 ; @008B3
; CODE: stored state_specific_code; execution views in src/protection
    db 0x31,0x1a,0x75,0x1d,0x04,0x98,0xaf,0x0d,0xf0,0x20,0x61,0x0a,0x84,0xeb,0x01,0xd5 ; @008C3
; CODE: stored state_specific_code; execution views in src/protection
    db 0x0f,0xfe,0xb9,0xc1,0xdf,0x2d,0xd3,0x1c,0x85,0x0e,0xd3,0x68,0x3c,0x69,0xb5,0xf6 ; @008D3
; CODE: stored state_specific_code; execution views in src/protection
    db 0xa7,0xd1,0x09,0x54,0x00,0xdc,0x27,0x96,0x63,0xa0,0x3c,0x8a,0x96,0x08,0x2a,0x3e ; @008E3
; CODE: stored state_specific_code; execution views in src/protection
    db 0x7b,0x61,0xfb,0x76,0x7c,0xf6,0x5f,0x48,0x82,0x3f,0x69,0xb2,0xed,0xbc,0xae,0x1c ; @008F3
; CODE: stored state_specific_code; execution views in src/protection
    db 0xe5,0x7f,0x3d,0x00,0x55,0x2c,0x26,0xa6,0xf2,0x50,0xe3,0x14,0x4c,0x39,0x3e,0x4e ; @00903
; CODE: stored state_specific_code; execution views in src/protection
    db 0x03,0x1d,0x00,0x02,0x8c,0xcb,0x21,0x2e,0x20,0x00,0x00,0x3b,0x89,0x1e,0xcb,0x63 ; @00913
; CODE: stored state_specific_code; execution views in src/protection
    db 0x78,0x00,0x86,0xb9,0x0f,0xab,0x41,0x7a,0x00,0x82,0xb9,0x11,0x49,0xaa,0x0f,0x20 ; @00923
; CODE: stored state_specific_code; execution views in src/protection
    db 0x1d,0x06,0xce,0x00,0x45,0x74,0x04,0x21,0x7f,0x45,0x13,0x33,0x9e,0x7a,0x36,0xcf ; @00933
; CODE: stored state_specific_code; execution views in src/protection
    db 0xe5,0x0f,0x13,0x69,0x5c,0x03,0x84,0x64,0xa7,0x05,0x71,0x1d,0x67,0xff,0xb0,0x7f ; @00943
; CODE: stored state_specific_code; execution views in src/protection
    db 0x00,0x02,0x8c,0xee,0x22,0x54,0x0f,0xdc,0x1c,0x16,0x7e,0xd8,0x00,0x79,0x74,0x45 ; @00953
; CODE: stored state_specific_code; execution views in src/protection
    db 0x13,0x53,0x51,0x04,0x1b,0xb0,0x2a,0x6a,0xf2,0x72,0x86,0xd9,0x3e,0x9c,0x59,0x33 ; @00963
; CODE: stored state_specific_code; execution views in src/protection
    db 0xf6,0x8e,0xde,0x8f,0x44,0x12,0x83,0xee,0x02,0x83,0xfe,0xec,0x75,0xf5,0x51,0x9d ; @00973
; CODE: stored state_specific_code; execution views in src/protection
    db 0x5d,0x5f,0x5e,0x59,0x07,0x1f,0xe9,0xae,0x04 ; @00983
; S18 stored-role audit: retain UNKNOWN098C..0D9B and084D..084F/087E..0880.
; Owned stream.asm records an initial-byte reader on the DL>=2 absolute arm:
; 06D7 calls0878 without prefill,ignores returnedCF,CRC06E0 reads selected
; offsets00..FD andCMP06E3 reads+FE. An unchanged failing DOS read therefore
; consumes initial first256 bytes; initial CRC90AA vs EFFE(primary),0508 vs
;45D0(fallback) rejects them. Ordinary startup forcesDL0;floppy07BE fills
;1234 first.094A zeros selected512;unselected512/gap16 retain entry bytes.
; INT3 negates handler0DFF..0E39 only;INT1 patches actual interrupted farIP,
; not a linear storage decrypt. No recovered edge/fixup enters1040 bytes.
; 8363 reset/advance can checksum every byte here (8397);caller unresolved.
; These roles neither identify initial meaning nor prove no executable view.
; Same actual first-word transform at084D/084E yields90;C6460E03 and at
;087E/087F yields90;C6460E26: candidateNOP/write-selector sequences sharing
;0852/0883. No recovered incoming edge proves either producer. Key-data
;0850/0851,0881/0882 overlap candidate operands; no classification expansion.
; Absolute gate0DA6 ADD SP,2 changes CF before08AC retry test; returned
; flags are not transparent DOS flags.06DA still consumes buffer regardless.
; Protected storage inventory, inclusive ranges (canonical bytes stay UNKNOWN):
; 098C..0B8B: 512-byte primary sector-buffer overlay.
; 0B8C..0B9B: 16 bytes outside both buffers; no specific protection role proved.
; 0B9C..0D9B: 512-byte DMA-fallback sector-buffer overlay.
; 0D9C..0D9D: retained decode seed for protected 0D9E, not buffer storage.
; CALL-next 066E supplies 0671; +031B=098C. At 067B SI=(CS+0098) mod 10000,
; DI=000C; low12(SI)>0FDF selects DI=021C, equivalent to CS:0B9C. Either
; 512-byte transfer stays in one physical 64 KiB DMA page, including wrap.
; SS:BP+0A/+0C owns the selected offset/segment for this call only. 08CB fills
; 0100 words (CLD); 07BB supplies 1234 before BIOS reads, 07E7/07F0/07F9 mutate
; signature bytes, CRC/bit-count readers inspect them; 094A fills with zero on
; both success/failure cleanup. The unselected buffer is unchanged in the
; disjoint domain. Initial stored buffer contents remain unexplained; neither
; overwrite nor absent graph edges proves no alternate executable role.
; Thus 1024 bytes have a runtime buffer role, 2 a seed role, and 16 no specific
; protection role; all 1042 stored bytes retain canonical UNKNOWN accounting.
; AdvanceCodeChecksum's live CS cursor can read these bytes; its caller remains
; unresolved. Preserve final buffer clear and untouched originals, not new BSS.
; UNKNOWN: unresolved bytes
ProtectionSectorBufferPrimary:
    db 0xb5,0xa2,0x6b,0x88,0xd7,0x53,0xae,0xea,0x5c,0x18,0xb9,0x73,0x72,0x2a,0xe4,0x97 ; @0098C
; UNKNOWN: unresolved bytes
    db 0xc9,0x72,0x92,0x28,0x24,0x94,0x49,0x6b,0x93,0x19,0x26,0x76,0x4d,0x2f,0x9a,0xa1 ; @0099C
; UNKNOWN: unresolved bytes
    db 0x34,0x86,0x68,0x4f,0xd1,0xe1,0xa3,0x06,0x47,0x50,0x8e,0xe3,0x1c,0x0a,0x38,0x57 ; @009AC
; UNKNOWN: unresolved bytes
    db 0x71,0xf1,0xe2,0x25,0xc4,0x8e,0x89,0x60,0x13,0x04,0x27,0x4b,0x4f,0xd9,0x9e,0xf5 ; @009BC
; UNKNOWN: unresolved bytes
    db 0x3d,0x2e,0x7b,0x9f,0xf7,0x81,0xef,0x46,0xdf,0xd0,0xbe,0xe4,0x7c,0x0c,0xf8,0x5b ; @009CC
; UNKNOWN: unresolved bytes
    db 0xf1,0xfa,0xe2,0x38,0xc5,0xb4,0x8a,0xac,0x14,0x9c,0x29,0x7b,0x52,0x39,0xa5,0xb5 ; @009DC
; UNKNOWN: unresolved bytes
    db 0x4a,0xae,0x94,0x9f,0x28,0x82,0x50,0x47,0xa0,0xd1,0x41,0xe6,0x83,0x0f,0x06,0x62 ; @009EC
; UNKNOWN: unresolved bytes
    db 0x0c,0x07,0x18,0x51,0x31,0xe5,0x63,0x0d,0xc7,0x5d,0x8e,0xfe,0x1c,0x40,0x38,0xc3 ; @009FC
; UNKNOWN: unresolved bytes
    db 0x70,0xc9,0xe0,0xd5,0xc1,0xee,0x82,0x20,0x04,0x84,0x08,0x4b,0x10,0xd9,0x21,0xf5 ; @00A0C
; UNKNOWN: unresolved bytes
    db 0x42,0x2d,0x84,0x9d,0x09,0x7e,0x12,0x3f,0x24,0xc1,0x48,0xc5,0x90,0xcd,0x20,0xde ; @00A1C
; UNKNOWN: unresolved bytes
    db 0x41,0xff,0x83,0x41,0x07,0xc6,0x0f,0xcf,0x1e,0xe1,0x3c,0x05,0x78,0x4d,0xf0,0xdd ; @00A2C
; UNKNOWN: unresolved bytes
    db 0xe1,0xfe,0xc3,0x40,0x87,0xc4,0x0f,0xcc,0x1f,0xdb,0x3e,0xf9,0x7d,0x35,0xfa,0xad ; @00A3C
; UNKNOWN: unresolved bytes
    db 0xf4,0x9e,0xe8,0x80,0xd0,0x44,0xa0,0xcc,0x40,0xdc,0x81,0xfb,0x02,0x3a,0x05,0xb7 ; @00A4C
; UNKNOWN: unresolved bytes
    db 0x0a,0xb1,0x15,0xa5,0x2b,0x8d,0x57,0x5d,0xae,0xfd,0x5d,0x3e,0xba,0xbf,0x74,0xc2 ; @00A5C
; UNKNOWN: unresolved bytes
    db 0xe8,0xc7,0xd0,0xd2,0xa1,0xe8,0x43,0x14,0x86,0x6b,0x0c,0x1a,0x19,0x77,0x32,0x31 ; @00A6C
; UNKNOWN: unresolved bytes
    db 0x65,0xa5,0xcb,0x8d,0x97,0x5e,0x2f,0x00,0x5f,0x43,0xbf,0xc9,0x7f,0xd6,0xfe,0xef ; @00A7C
; UNKNOWN: unresolved bytes
    db 0xfd,0x22,0xfb,0x88,0xf7,0x54,0xee,0xec,0xdc,0x1c,0xb9,0x7c,0x72,0x3c,0xe5,0xbb ; @00A8C
; UNKNOWN: unresolved bytes
    db 0xca,0xba,0x95,0xb8,0x2a,0xb4,0x55,0xab,0xab,0x99,0x56,0x76,0xad,0x2f,0x5a,0xa2 ; @00A9C
; UNKNOWN: unresolved bytes
    db 0xb4,0x87,0x68,0x52,0xd1,0xe7,0xa3,0x12,0x46,0x68,0x8c,0x13,0x19,0x6a,0x33,0x17 ; @00AAC
; UNKNOWN: unresolved bytes
    db 0x66,0x71,0xcd,0x25,0x9b,0x8e,0x36,0x60,0x6c,0x03,0xd8,0x49,0xb0,0xd6,0x61,0xf0 ; @00ABC
; UNKNOWN: unresolved bytes
    db 0xc2,0x23,0x84,0x8a,0x08,0x58,0x11,0xf3,0x22,0x29,0x44,0x95,0x89,0x6d,0x13,0x1e ; @00ACC
; UNKNOWN: unresolved bytes
    db 0x26,0x7f,0x4c,0x41,0x98,0xc5,0x30,0xce,0x60,0xdf,0xc0,0x01,0x80,0x46,0x00,0xd0 ; @00ADC
; UNKNOWN: unresolved bytes
    db 0x01,0xe3,0x03,0x09,0x07,0x55,0x0e,0xed,0x1c,0x1d,0x39,0x7d,0x72,0x3d,0xe5,0xbd ; @00AEC
; UNKNOWN: unresolved bytes
    db 0xca,0xbe,0x94,0xc0,0x28,0xc4,0x50,0xcb,0xa0,0xd9,0x41,0xf6,0x82,0x2f,0x05,0xa2 ; @00AFC
; UNKNOWN: unresolved bytes
    db 0x0b,0x87,0x17,0x51,0x2e,0xe5,0x5c,0x0d,0xb8,0x5d,0x71,0xfe,0xe2,0x3f,0xc4,0xc2 ; @00B0C
; UNKNOWN: unresolved bytes
    db 0x88,0xc8,0x10,0xd4,0x21,0xeb,0x43,0x19,0x86,0x75,0x0d,0x2e,0x1b,0x9f,0x37,0x81 ; @00B1C
; UNKNOWN: unresolved bytes
    db 0x6f,0x45,0xdf,0xcd,0xbf,0xde,0x7f,0x00,0xff,0x43,0xff,0xca,0xff,0xd8,0xfe,0xf4 ; @00B2C
; UNKNOWN: unresolved bytes
    db 0xfd,0x2c,0xfb,0x9c,0xf6,0x7c,0xed,0x3c,0xda,0xbc,0xb5,0xbc,0x6a,0xbc,0xd5,0xbb ; @00B3C
; UNKNOWN: unresolved bytes
    db 0xaa,0xba,0x55,0xb8,0xaa,0xb3,0x55,0xaa,0xab,0x97,0x56,0x72,0xad,0x27,0x5b,0x92 ; @00B4C
; UNKNOWN: unresolved bytes
    db 0xb6,0x67,0x6c,0x12,0xd9,0x67,0xb3,0x12,0x66,0x68,0xcc,0x13,0x99,0x6a,0x33,0x18 ; @00B5C
; UNKNOWN: unresolved bytes
    db 0x66,0x73,0xcd,0x29,0x9b,0x96,0x36,0x70,0x6d,0x23,0xdb,0x89,0xb7,0x56,0x6e,0xf0 ; @00B6C
; UNKNOWN: unresolved bytes
    db 0xdd,0x23,0xbb,0x8a,0x77,0x58,0xee,0xf3,0xdd,0x2a,0xbb,0x98,0x76,0x74,0xed,0x2b ; @00B7C
; 0B8C..0B9B is outside both REP STOSW windows. Retain UNKNOWN, not padding.
; UNKNOWN: unresolved bytes
    db 0xdb,0x9a,0xb6,0x78,0x6d,0x34,0xda,0xab,0xb4,0x9a,0x69,0x78,0xd2,0x33,0xa5,0xaa ; @00B8C
; DMA fallback: the same selected-buffer lifetime as 098C, not extra capacity.
; UNKNOWN: unresolved bytes
ProtectionSectorBufferDmaFallback:
    db 0x4b,0x98,0x96,0x73,0x2d,0x2a,0x5b,0x97,0xb6,0x71,0x6d,0x26,0xdb,0x8f,0xb6,0x62 ; @00B9C
; UNKNOWN: unresolved bytes
    db 0x6c,0x08,0xd8,0x53,0xb1,0xea,0x63,0x18,0xc6,0x73,0x8d,0x2a,0x1b,0x98,0x36,0x73 ; @00BAC
; UNKNOWN: unresolved bytes
    db 0x6d,0x29,0xdb,0x95,0xb6,0x6e,0x6d,0x20,0xdb,0x83,0xb7,0x4a,0x6f,0xd8,0xde,0xf3 ; @00BBC
; UNKNOWN: unresolved bytes
    db 0xbd,0x2a,0x7b,0x98,0xf6,0x73,0xed,0x2a,0xdb,0x98,0xb6,0x74,0x6d,0x2c,0xdb,0x9b ; @00BCC
; UNKNOWN: unresolved bytes
    db 0xb6,0x7a,0x6d,0x38,0xda,0xb3,0xb5,0xaa,0x6b,0x98,0xd6,0x73,0xad,0x2a,0x5b,0x98 ; @00BDC
; UNKNOWN: unresolved bytes
    db 0xb6,0x73,0x6d,0x2a,0xdb,0x97,0xb6,0x72,0x6d,0x28,0xdb,0x93,0xb6,0x6a,0x6c,0x18 ; @00BEC
; UNKNOWN: unresolved bytes
    db 0xd9,0x73,0xb2,0x2a,0x64,0x98,0xc9,0x73,0x92,0x2a,0x24,0x98,0x49,0x73,0x92,0x29 ; @00BFC
; UNKNOWN: unresolved bytes
    db 0x24,0x96,0x49,0x6f,0x92,0x21,0x24,0x86,0x48,0x4f,0x91,0xe1,0x23,0x06,0x47,0x4f ; @00C0C
; UNKNOWN: unresolved bytes
    db 0x8e,0xe1,0x1c,0x06,0x38,0x4f,0x71,0xe1,0xe3,0x05,0xc7,0x4e,0x8e,0xe0,0x1c,0x04 ; @00C1C
; UNKNOWN: unresolved bytes
    db 0x38,0x4b,0x70,0xd9,0xe1,0xf5,0xc2,0x2e,0x85,0xa0,0x0b,0x84,0x17,0x4b,0x2f,0xd9 ; @00C2C
; UNKNOWN: unresolved bytes
    db 0x5e,0xf5,0xbd,0x2d,0x7b,0x9e,0xf6,0x7f,0xec,0x42,0xd8,0xc8,0xb0,0xd4,0x61,0xec ; @00C3C
; UNKNOWN: unresolved bytes
    db 0xc3,0x1b,0x86,0x7a,0x0d,0x38,0x1a,0xb3,0x35,0xa9,0x6b,0x95,0xd6,0x6d,0xac,0x1e ; @00C4C
; UNKNOWN: unresolved bytes
    db 0x58,0x80,0xb0,0x43,0x60,0xca,0xc0,0xd7,0x81,0xf2,0x02,0x28,0x04,0x93,0x09,0x69 ; @00C5C
; UNKNOWN: unresolved bytes
    db 0x13,0x15,0x26,0x6d,0x4c,0x1d,0x99,0x7d,0x32,0x3e,0x65,0xbf,0xcb,0xc1,0x97,0xc6 ; @00C6C
; UNKNOWN: unresolved bytes
    db 0x2f,0xd0,0x5e,0xe3,0xbc,0x09,0x78,0x56,0xf1,0xef,0xe2,0x22,0xc4,0x88,0x88,0x54 ; @00C7C
; UNKNOWN: unresolved bytes
    db 0x11,0xec,0x23,0x1b,0x46,0x79,0x8d,0x35,0x1a,0xae,0x34,0x9f,0x68,0x81,0xd0,0x45 ; @00C8C
; UNKNOWN: unresolved bytes
    db 0xa0,0xce,0x41,0xe0,0x83,0x03,0x07,0x4a,0x0f,0xd7,0x1e,0xf1,0x3d,0x25,0x7b,0x8d ; @00C9C
; UNKNOWN: unresolved bytes
    db 0xf7,0x5d,0xee,0xfe,0xdc,0x40,0xb8,0xc4,0x70,0xcc,0xe0,0xdb,0xc1,0xfa,0x82,0x38 ; @00CAC
; UNKNOWN: unresolved bytes
    db 0x05,0xb4,0x0a,0xab,0x14,0x99,0x29,0x75,0x52,0x2d,0xa4,0x9d,0x49,0x7e,0x92,0x3f ; @00CBC
; UNKNOWN: unresolved bytes
    db 0x24,0xc2,0x48,0xc7,0x90,0xd1,0x21,0xe6,0x43,0x0f,0x86,0x61,0x0c,0x06,0x18,0x4f ; @00CCC
; UNKNOWN: unresolved bytes
    db 0x31,0xe1,0x63,0x05,0xc7,0x4d,0x8f,0xde,0x1f,0x00,0x3f,0x43,0x7f,0xc9,0xff,0xd5 ; @00CDC
; UNKNOWN: unresolved bytes
    db 0xfe,0xee,0xfd,0x20,0xfb,0x84,0xf7,0x4c,0xef,0xdc,0xde,0xfc,0xbd,0x3c,0x7a,0xbc ; @00CEC
; UNKNOWN: unresolved bytes
    db 0xf5,0xbb,0xea,0xba,0xd5,0xb8,0xaa,0xb4,0x55,0xac,0xab,0x9b,0x56,0x7a,0xad,0x37 ; @00CFC
; UNKNOWN: unresolved bytes
    db 0x5a,0xb2,0xb5,0xa7,0x6b,0x92,0xd6,0x67,0xac,0x12,0x59,0x68,0xb3,0x13,0x66,0x6a ; @00D0C
; UNKNOWN: unresolved bytes
    db 0xcc,0x17,0x99,0x72,0x32,0x28,0x64,0x93,0xc9,0x69,0x93,0x16,0x26,0x70,0x4d,0x23 ; @00D1C
; UNKNOWN: unresolved bytes
    db 0x9b,0x89,0x37,0x56,0x6e,0xef,0xdd,0x21,0xbb,0x86,0x77,0x50,0xee,0xe3,0xdc,0x0a ; @00D2C
; UNKNOWN: unresolved bytes
    db 0xb8,0x58,0x71,0xf4,0xe2,0x2b,0xc4,0x9a,0x89,0x78,0x12,0x34,0x25,0xab,0x4b,0x99 ; @00D3C
; UNKNOWN: unresolved bytes
    db 0x96,0x75,0x2d,0x2e,0x5b,0x9f,0xb7,0x81,0x6f,0x46,0xdf,0xcf,0xbe,0xe2,0x7c,0x08 ; @00D4C
; UNKNOWN: unresolved bytes
    db 0xf8,0x53,0xf1,0xea,0xe3,0x18,0xc6,0x74,0x8d,0x2c,0x1b,0x9c,0x36,0x7b,0x6d,0x39 ; @00D5C
; UNKNOWN: unresolved bytes
    db 0xda,0xb5,0xb5,0xae,0x6a,0xa0,0xd4,0x83,0xa8,0x4a,0x50,0xd8,0xa1,0xf3,0x42,0x2a ; @00D6C
; UNKNOWN: unresolved bytes
    db 0x84,0x97,0x09,0x72,0x12,0x27,0x24,0x91,0x49,0x65,0x93,0x0d,0x27,0x5e,0x4e,0xff ; @00D7C
; UNKNOWN: unresolved bytes
    db 0x9c,0x41,0x38,0xc6,0x70,0xcf,0xe1,0xe1,0xc3,0x06,0x87,0x50,0x0e,0xe4,0x1c,0x0b ; @00D8C
; Known data-use overlay: 0E20 reads this word when interrupted IP=0D9E.
; ROL16(NOT 9090,1)=DEDE; stored word CD12 XOR DEDE=13CC (bytes CC 13).
; Neither buffer reaches this seed; no execution of these two 90 bytes is
; established. Canonical UNKNOWN retains possible additional interpretations.
; UNKNOWN: unresolved bytes
ProtectionInt13DecodeSeed:
    db 0x90,0x90 ; @00D9C
; CODE: stored state_specific_code; execution views in src/protection
    db 0x12,0xcd,0x13,0xcc,0x1b,0xab,0xcd,0x25,0x83,0xc4,0x02,0xcc,0x39,0xab,0xcd,0x26 ; @00D9E
; CODE: stored state_specific_code; execution views in src/protection
    db 0x83,0xc4,0x02,0xcc,0x39 ; @00DAE
ProtectionInt3Handler:
; Plain stored INT3 body; live hardware frame at entry SS:S is IP,CS,FLAGS.
; PUSH AX/SI/DS leaves T=S-6; saved IP/CS/FLAGS are T+6/+8/+A. No new stack
; or data frame is installed. Saved registers and IRET words remain live RAM;
; an alias may change subsequent loads, so the disjoint-domain rule matters.
    push ax ; @00DB3
    push si ; @00DB4
    push ds ; @00DB5
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @00DB6
    mov ds,ax ; @00DB8
    call InstallProtectionInt1FromReturnAddress ; @00DBA
InstallProtectionInt1FromReturnAddress:
; CALL-next consumes 0DBD; +0042 installs CS:0DFF as IVT1. Every INT3 negates
; exactly 003B bytes 0DFF..0E39 (byte NEG, not NOT). Even invocations restore
; stored bytes. First TF-clear entry exposes src/protection/int1.asm; enabling
; branch 0DE6 enters its shared tail 0E1C, skipping INT1's STI/old-word restore.
    pop word [0x4] ; @00DBD
    add word [0x4],0x42 ; @00DC1
    push cs ; @00DC7
    pop word [0x6] ; @00DC8
    mov si,[0x4] ; @00DCC
    mov ax,0x3b ; @00DD0
loc_0DD3:
    neg byte [cs:si] ; @00DD3
    inc si ; @00DD6
    dec ax ; @00DD7
    jnz loc_0DD3 ; @00DD8
; SI=T. XOR high saved FLAGS byte by 03 toggles TF and IF simultaneously;
; branch uses the new TF. No fixed callback address is supplied to 0E1C:
; LDS there takes interrupted CS:IP from SS:[T+6], including CALL/RET targets.
    db 0x8b,0xf4 ; ENCODED: mov si,sp (NASM chooses a different encoding) ; @00DDA
    xor byte [ss:si+0xb],0x3 ; @00DDC
    test byte [ss:si+0xb],0x1 ; @00DE1
    jnz $+(54) ; @00DE6
; Disabling: IVT0 is the previous patch's far pointer, not an active divide
; handler. Compute candidate ciphertext from current memory using its prior
; word. Here CC guard tests candidate AL BEFORE XCHG; INT1 tests displaced
; plaintext AL AFTER XCHG. A skipped swap is an observable distinction.
    lds si,[0x0] ; @00DE8
    mov ax,[si-0x2] ; @00DEC
    not ax ; @00DEF
    rol ax,1 ; @00DF1
    xor ax,[si] ; @00DF3
    cmp al,0xcc ; @00DF5
    jz loc_0DFB ; @00DF7
    xchg [si],ax ; @00DF9
loc_0DFB:
    pop ds ; @00DFB
    pop si ; @00DFC
    pop ax ; @00DFD
    iret ; @00DFE
ProtectionEncodedInt1:
; Entire 59-byte stored/negated pair; only the plaintext view is executable
; as the installed INT1 handler. Shared 0E1C reads the live interrupted frame,
; never a fixed near target. See src/protection/int1.asm for wrap/alias/order.
; CODE: stored runtime_modified_code; execution views in src/protection
    db 0x05,0xb0,0xaa,0xe2,0xcd,0x40,0x72,0x28,0x3b,0xca,0x00,0x00,0x75,0xbc,0x02,0x09 ; @00DFF
; CODE: stored runtime_modified_code; execution views in src/protection
    db 0x30,0x2f,0x40,0xcd,0xfc,0x79,0xfc,0xc4,0x34,0x8c,0xe4,0x75,0x0c,0xca,0x3b,0x8c ; @00E0F
; CODE: stored runtime_modified_code; execution views in src/protection
    db 0xfa,0x75,0xbc,0x02,0x09,0x30,0x2f,0x40,0xcf,0xfc,0xe2,0xcd,0x40,0x72,0x28,0x77 ; @00E1F
; CODE: stored runtime_modified_code; execution views in src/protection
    db 0xca,0x00,0x00,0x71,0xfa,0xfe,0x00,0xe1,0xa2,0xa8,0x31 ; @00E2F
; CODE: stored state_specific_code; execution views in src/protection
    db 0x73,0x01,0xc3,0x3d,0x1c,0x58,0x75,0x08,0x81,0xfb,0xf2,0xa9,0x75,0x02,0xf8,0xc3 ; @00E3A
; CODE: stored state_specific_code; execution views in src/protection
    db 0x3d,0x50,0xd9,0x75,0x08,0x81,0xfb,0x0a,0x27,0x75,0x02,0xf8,0xc3,0x3d,0xf8,0x9c ; @00E4A
; CODE: stored state_specific_code; execution views in src/protection
    db 0x75,0x08,0x81,0xfb,0x8c,0x1a,0x75,0x02,0xf8,0xc3,0xf9,0xc3 ; @00E5A
loc_0E66:
CheckProtectionRunCounter:
    lea dx,[ProtectionCounterFilename-GameDataImage] ; @00E66
    mov ax,0x3d00 ; @00E6A
    int 0x21 ; @00E6D
    jc loc_0EAA ; @00E6F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @00E71
    mov ah,0x3f ; @00E73
; Separate file input0E7C reads at mostone russell.dat byte toDS252A.
; Startup/per-level clears exclude it; missing-open0EAC zeros, short read
; retains prior value before increment.0ED8 writes100h bytes FROM252A..2629
; tofile (filenames, clocks, callback/options and palette prefix2608..2629),
; not intoRAM. This is process-protection state with file persistence.
    lea dx,[ProtectionRunCounterByte-GameDataImage] ; @00E75
    mov cx,0x1 ; @00E79
    int 0x21 ; @00E7C
    mov al,[ProtectionRunCounterByte-GameDataImage] ; @00E7E
    inc al ; @00E81
    cmp al,0xa ; @00E83
    jc loc_0E89 ; @00E85
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @00E87
loc_0E89:
    mov [ProtectionRunCounterByte-GameDataImage],al ; @00E89
    push ax ; @00E8C
    mov ah,0x3e ; @00E8D
    int 0x21 ; @00E8F
    call WriteProtectionCounterFile ; @00E91
    pop ax ; @00E94
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @00E95
    jnz loc_0EA9 ; @00E97
    call ProbeOriginalFloppyMedia ; @00E99
    jnc loc_0EA9 ; @00E9C
    mov byte [ProtectionRunCounterByte-GameDataImage],0x9 ; @00E9E
    call WriteProtectionCounterFile ; @00EA3
    jmp short loc_0EDF ; @00EA6
; S14 U005: [00EA8,00EA9) stored bytes remain UNKNOWN.
; Neighbours: P 00EA6 jmp 0xedf; N 00EA9 ret.
; Stored90 bypassed by0EA6 JMP0EDF;0EA9 RET is separate. Numeric4113/4127/5739/7083 constructions refer to DS0EA8 visibility map, not CS0EA8; LEA does not access memory. No specific CS reader/writer identified beyond checksum/general unchecked aliases.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @00EA8
loc_0EA9:
    ret ; @00EA9
loc_0EAA:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @00EAA
    mov [ProtectionRunCounterByte-GameDataImage],al ; @00EAC
    call WriteProtectionCounterFile ; @00EAF
    call ProbeOriginalFloppyMedia ; @00EB2
    jnc loc_0EA9 ; @00EB5
    mov byte [ProtectionRunCounterByte-GameDataImage],0x9 ; @00EB7
    call WriteProtectionCounterFile ; @00EBC
    jmp short loc_0EDF ; @00EBF
; S14 U006: [00EC1,00EC2) stored bytes remain UNKNOWN.
; Neighbours: P 00EBF jmp 0xedf; N 00EC2 lea dx, [0x258a].
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @00EC1
WriteProtectionCounterFile:
    lea dx,[ProtectionCounterFilename-GameDataImage] ; @00EC2
    mov ah,0x3c ; @00EC6
    mov cx,0x2 ; @00EC8
    int 0x21 ; @00ECB
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @00ECD
    mov ah,0x40 ; @00ECF
    mov cx,0x100 ; @00ED1
    lea dx,[ProtectionRunCounterByte-GameDataImage] ; @00ED4
    int 0x21 ; @00ED8
    mov ah,0x3e ; @00EDA
    int 0x21 ; @00EDC
    ret ; @00EDE
loc_0EDF:
StartupProtectionFailure:
    call RestoreTimerState ; @00EDF
    call RestoreKeyboardVector ; @00EE2
    call RestorePrivateVector ; @00EE5
    call RestoreVideoModeAndPage ; @00EE8
    cmp byte [MouseServicesDisabledByte-GameDataImage],0xff ; @00EEB
    jz loc_0EF9 ; @00EF0
    mov ax,0xc ; @00EF2
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @00EF5
    int 0x33 ; @00EF7
loc_0EF9:
    call RestoreKeyboardVector ; @00EF9
    mov dx,0x20d4 ; @00EFC
    mov ah,0x9 ; @00EFF
    int 0x21 ; @00F01
    mov ax,0x4c00 ; @00F03
    int 0x21 ; @00F06
InitializeMouseDriverHooks:
; FF in 1F73 bypasses. Reset AX=0 returning 0 sets 25A6=2 and 1F73=FF.
; Present: AX 15/7/8/4/2, callback 12 mask 007F at CS:0F6F, then DOS 25 hooks
; vector [1FC6] to CS:0F70 with DS saved through the actual stack.
    cmp byte [MouseServicesDisabledByte-GameDataImage],0xff ; @00F08
    jz loc_0F64 ; @00F0D
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @00F0F
    int 0x33 ; @00F11
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @00F13
    jz loc_0F64 ; @00F15
    mov ax,0xf ; @00F17
    mov cx,0x10 ; @00F1A
    mov dx,0x10 ; @00F1D
    int 0x33 ; @00F20
    mov ax,0x7 ; @00F22
    mov cx,0x8 ; @00F25
    mov dx,0x148 ; @00F28
    int 0x33 ; @00F2B
    mov ax,0x8 ; @00F2D
    mov cx,0x8 ; @00F30
    mov dx,0xc8 ; @00F33
    int 0x33 ; @00F36
    mov ax,0x4 ; @00F38
    mov cx,0x96 ; @00F3B
    mov dx,0x64 ; @00F3E
    int 0x33 ; @00F41
    mov ax,0x2 ; @00F43
    int 0x33 ; @00F46
    mov ax,0xc ; @00F48
    mov cx,0x7f ; @00F4B
    push cs ; @00F4E
    pop es ; @00F4F
    mov dx,0xf6f ; @00F50
    int 0x33 ; @00F53
    mov ah,0x25 ; @00F55
    mov al,[PrivateVectorNumber-GameDataImage] ; @00F57
    push ds ; @00F5A
    push cs ; @00F5B
    pop ds ; @00F5C
    mov dx,0xf70 ; @00F5D
    int 0x21 ; @00F60
    pop ds ; @00F62
    ret ; @00F63
loc_0F64:
    mov byte [InputModeByte25A6-GameDataImage],0x2 ; @00F64
    mov byte [MouseServicesDisabledByte-GameDataImage],0xff ; @00F69
    ret ; @00F6E
MouseEventReturn:
    retf ; @00F6F
; U1 private wrapper has noEOI:CPU6+DS/AX4+INT62 frame6 gives16+B62 at provider entry. Restore arm peaks16 locally;58D0 STI shadows itsRET, reopening at0F9C with12 resident (then10/8/6). EOI of IRQ4/vector0C or configuredIRQ12/vector74 belongs to the external provider; self-nesting needs that release plusIF1 and a new request. INT62's own stack switching/high-water mark and IF/PIC behavior are unknown; normal returnedSS:SP cannot bound its transient use.
; UNCONDITIONAL local costs: CPU6 +DS/AX4;INT62 adds CPU6,so16 bytes before its unknown internal use. Restore arm PUSH DX/CALL587F and587F savedCX (ES uses CX) also peaks16 including outer frame. UNRESOLVED INT62 returned SS:SP and nested/provider stack use. RETF callback0F6F has zero local pushes;its external far caller owns the4-byte frame and choice of stack.
MouseIrqBridge:
; 48 bytes/20 sites. See docs/mouse-irq-bridge.md for installed INT62 provenance.
; Live SS pushes precede the relocated immediate; external INT62 may return new
; DS/ES/SS/SP/FLAGS. Both decrements and gates use returned DS; no shadow state.
; PUSH DX/CALL/POP DX and final POP AX/DS/IRET consume actual returned-stack words.
; The 587F child sets IF before its RET; asynchronous IRQ/nesting stays a seam.
    push ds ; @00F70
    push ax ; @00F71
MouseIrqDataFrameOperand0F73 equ $+1
    mov ax,0x9a9 ; @00F72
    mov ds,ax ; @00F75
    inc byte [PrivateIrqCounter2002-GameDataImage] ; @00F77
    inc byte [PrivateIrqCounter2003-GameDataImage] ; @00F7B
MouseIrqInt62:
    int 0x62 ; @00F7F
MouseIrqInt62Return:
    dec byte [PrivateIrqCounter2003-GameDataImage] ; @00F81
    dec byte [PrivateIrqCounter2002-GameDataImage] ; @00F85
    mov al,[cs:MouseIrqMirrorGate83BE] ; @00F89
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @00F8D
    jnz loc_0F9D ; @00F8F
    cmp byte [PrivateIrqCounter2002-GameDataImage],0x0 ; @00F91
    jnz loc_0F9D ; @00F96
    push dx ; @00F98
MouseIrqRestoreCall:
    call RestoreVgaRegisterMirrors ; @00F99
MouseIrqRestoreReturn:
    pop dx ; @00F9C
loc_0F9D:
    pop ax ; @00F9D
    pop ds ; @00F9E
MouseIrqOuterIret:
    iret ; @00F9F
RestorePrivateVector:
; CONTRACT: PUSH liveDS before pointer reads; DOS25 with mutable vector byte.
; ReturnedSS:SP owns the POPDS and nearRET; no cached entryDS restoration.
; Optional bus/provider and alias domain: docs/vector-restore.md.
    push ds ; @00FA0
    mov ah,0x25 ; @00FA1
    mov al,[PrivateVectorNumber-GameDataImage] ; @00FA3
    mov dx,[SavedPrivateVector-GameDataImage] ; @00FA6
    mov ds,[SavedPrivateVector-GameDataImage+2] ; @00FAA
; R2:dedicated1FC6 writers supply0C/74,not61;no old61 was saved. This dynamicDOS25 can still replace61 if selector/DS/frame aliases corrupt that domain. Thus absence of literal2561 after057B is not a whole-machine vector-immutability proof.
RestorePrivateVectorInterrupt:
    int 0x21 ; @00FAE
    pop ds ; @00FB0
RestorePrivateVectorReturn:
    ret ; @00FB1
; GAME VIDEO: CLI,full bound INT10 mode008D,live returned DS/SS,word OUT1613,STI.
; Nine literal MOV words initialize canonical DrawingCallbackSlots for native sprites.
; No mode/DS restore or invented RET; docs/video-probe.md.
SetupGameVideoAndSpriteCallbacks:
    cli ; @00FB2
    mov ax,0x8d ; @00FB3
    int 0x10 ; @00FB6
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @00FB8
    mov ax,0x1613 ; @00FBC
    out dx,ax ; @00FBF
    sti ; @00FC0
    mov word [DrawingCallbackSlots-GameDataImage+0x0],0x6170 ; @00FC1
    mov word [DrawingCallbackSlots-GameDataImage+0x2],0x64d9 ; @00FC7
    mov word [DrawingCallbackSlots-GameDataImage+0x4],0x65d8 ; @00FCD
    mov word [DrawingCallbackSlots-GameDataImage+0x6],0x66d7 ; @00FD3
    mov word [DrawingCallbackSlots-GameDataImage+0x8],0x6817 ; @00FD9
    mov word [DrawingCallbackSlots-GameDataImage+0xa],0x6957 ; @00FDF
    mov word [DrawingCallbackSlots-GameDataImage+0xc],0x6a97 ; @00FE5
    mov word [DrawingCallbackSlots-GameDataImage+0xe],0x6bdb ; @00FEB
    mov word [DrawingCallbackSlots-GameDataImage+0x10],0x6cfc ; @00FF1
    ret ; @00FF7
RestoreVideoModeAndPage:
; CONTRACT: read saved mode, AH00 INT10, then AH05 with page from live returnedDS.
; Neither BIOS call has a synthetic save frame; returned registers/flags stay live.
; Actual nearRET uses provider-returnedSS:SP. No assumptions about restored DS.
; Provider and byte-bus domain: docs/video-restore.md.
    mov al,[SavedVideoMode-GameDataImage] ; @00FF8
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @00FFB
RestoreVideoModeInterrupt:
    int 0x10 ; @00FFD
RestoreVideoAfterMode:
    mov ah,0x5 ; @00FFF
    mov al,[SavedVideoPage-GameDataImage] ; @01001
RestoreVideoPageInterrupt:
    int 0x10 ; @01004
RestoreVideoReturn:
    ret ; @01006
AllocateStartupGraphicsArena:
; One 5571-paragraph DOS block: base->1FE4/1FF0, +1000 1FE6, +2D0C 1FE8,
; +2E72 1FEA, +2F02 1FEC, +2F7E 1FEE, +4771 1FF2, +4971 1FF4 (wrapping ADDs).
; Failure writes four hex digits through the uninitialized live DS:SI (1228),
; prints ':' and 21C8 (error 7) or 21EA, then exits via 04EA.
    mov ah,0x48 ; @01007
    mov bx,0x5571 ; @01009
    int 0x21 ; @0100C
    jc loc_1044 ; @0100E
    mov [0x1fe4],ax ; @01010
    mov [0x1ff0],ax ; @01013
    add ax,0x1000 ; @01016
    mov [EntitySpriteBufferSegment-GameDataImage],ax ; @01019
    add ax,0x1d0c ; @0101C
    mov [GeneratedGraphicsBufferSegment-GameDataImage],ax ; @0101F
    add ax,0x166 ; @01022
    mov [GeneratedWordPatternBufferSegment-GameDataImage],ax ; @01025
    add ax,0x90 ; @01028
    mov [StatusGlyphBufferSegment-GameDataImage],ax ; @0102B
    add ax,0x7c ; @0102E
    mov [UiGraphicsBufferSegment-GameDataImage],ax ; @01031
    add ax,0x17f3 ; @01034
    mov [StartupArenaTailSegment1FF2-GameDataImage],ax ; @01037
    add ax,0x200 ; @0103A
    mov [0x1ff4],ax ; @0103D
    add ax,0xc00 ; @01040
    ret ; @01043
loc_1044:
    push ax ; @01044
    push bx ; @01045
    call RestoreVideoModeAndPage ; @01046
    pop bx ; @01049
    db 0x8b,0xc3 ; ENCODED: mov ax,bx (NASM chooses a different encoding) ; @0104A
    call WriteHexWordAtLiveCursor ; @0104C
    mov dl,0x3a ; @0104F
    mov ah,0x2 ; @01051
    int 0x21 ; @01053
    mov dl,0x20 ; @01055
    mov ah,0x2 ; @01057
    int 0x21 ; @01059
    pop ax ; @0105B
    mov dx,0x21c8 ; @0105C
    cmp ax,0x7 ; @0105F
    jz loc_1067 ; @01062
    mov dx,0x21ea ; @01064
loc_1067:
    mov ah,0x9 ; @01067
    int 0x21 ; @01069
    jmp ExitAfterKeyboardRestore ; @0106B
SelectStartupDisplayAndOptions:
; Mode 3 first; preset 1F7C plus any FF in 200A/200B/200D/200C returns at
; once. Palette prompt 22E1 (1->4, 2->2, ESC exits). A/B/D flags tail-enter
; 1194 with the caller's SI/DI unchanged (quirk: may overwrite parser rows).
; Menu rows 0..4 by arrows; commit row 0:200E+200C 1:none 2:200A/IRQ74/3468
; 3:200B+200E 4:exit. DOS 4C is terminal.
    mov ax,0x3 ; @0106E
    int 0x10 ; @01071
    cmp word [0x1f7c],0xff ; @01073
    jz loc_10A3 ; @01079
    cmp byte [0x200a],0xff ; @0107B
    jnz loc_1085 ; @01080
    jmp loc_1227 ; @01082
loc_1085:
    cmp byte [0x200b],0xff ; @01085
    jnz loc_108F ; @0108A
    jmp loc_1227 ; @0108C
loc_108F:
    cmp byte [StartupOptionSelectionBypass200D-GameDataImage],0xff ; @0108F
    jnz loc_1099 ; @01094
    jmp loc_1227 ; @01096
loc_1099:
    cmp byte [0x200c],0xff ; @01099
    jnz loc_10A3 ; @0109E
    jmp loc_1227 ; @010A0
loc_10A3:
    lea bx,[0x2260] ; @010A3
    call WriteZeroTerminatedDosText ; @010A7
    cmp word [0x1f7c],0xff ; @010AA
    jnz loc_10DB ; @010B0
    mov bx,0x22e1 ; @010B2
    call WriteZeroTerminatedDosText ; @010B5
loc_10B8:
    mov ah,0x7 ; @010B8
    int 0x21 ; @010BA
    cmp al,0x1b ; @010BC
    jnz loc_10C3 ; @010BE
    jmp loc_120C ; @010C0
loc_10C3:
    mov cx,0x4 ; @010C3
    cmp al,0x31 ; @010C6
    jz loc_10D1 ; @010C8
    mov cx,0x2 ; @010CA
    cmp al,0x32 ; @010CD
    jnz loc_10B8 ; @010CF
loc_10D1:
    mov [0x1f7c],cx ; @010D1
    db 0x8a,0xd0 ; ENCODED: mov dl,al (NASM chooses a different encoding) ; @010D5
    mov ah,0x2 ; @010D7
    int 0x21 ; @010D9
loc_10DB:
    cmp byte [0x200a],0xff ; @010DB
    jnz loc_10E5 ; @010E0
    jmp MarkStartupOptionAndRedraw ; @010E2
loc_10E5:
    cmp byte [0x200b],0xff ; @010E5
    jnz loc_10EF ; @010EA
    jmp MarkStartupOptionAndRedraw ; @010EC
loc_10EF:
    cmp byte [StartupOptionSelectionBypass200D-GameDataImage],0xff ; @010EF
    jnz loc_10F9 ; @010F4
    jmp MarkStartupOptionAndRedraw ; @010F6
loc_10F9:
    mov ah,0xf ; @010F9
    int 0x10 ; @010FB
    mov ah,0x2 ; @010FD
    mov dx,0x100 ; @010FF
    int 0x10 ; @01102
    mov bx,0x2384 ; @01104
    call WriteZeroTerminatedDosText ; @01107
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @0110A
    lea di,[0x239f] ; @0110C
loc_1110:
    call WaitForDisplayStatusBit3Cycle ; @01110
    push bx ; @01113
    mov ah,0x7 ; @01114
    int 0x21 ; @01116
    pop bx ; @01118
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @01119
    jnz loc_113E ; @0111B
    push bx ; @0111D
    mov ah,0x7 ; @0111E
    int 0x21 ; @01120
    pop bx ; @01122
    cmp al,0x48 ; @01123
    jnz loc_1130 ; @01125
    db 0x22,0xdb ; ENCODED: and bl,bl (NASM chooses a different encoding) ; @01127
    jz loc_1110 ; @01129
    dec bl ; @0112B
    jmp loc_11B5 ; @0112D
loc_1130:
    cmp al,0x50 ; @01130
    jnz loc_1110 ; @01132
    cmp bl,0x4 ; @01134
    jz loc_1110 ; @01137
    inc bl ; @01139
    jmp short loc_11B5 ; @0113B
; S14 U007: [0113D,0113E) stored bytes remain UNKNOWN.
; Neighbours: P 0113B jmp 0x11b5; N 0113E cmp al, 0x1b.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @0113D
loc_113E:
    cmp al,0x1b ; @0113E
    jnz loc_1145 ; @01140
    jmp loc_120C ; @01142
loc_1145:
    cmp al,0xd ; @01145
    jz loc_116B ; @01147
    cmp al,0xa ; @01149
    jz loc_116B ; @0114B
    cmp al,0x31 ; @0114D
    jnz loc_1155 ; @0114F
    db 0x32,0xdb ; ENCODED: xor bl,bl (NASM chooses a different encoding) ; @01151
    jmp short loc_116B ; @01153
loc_1155:
    cmp al,0x32 ; @01155
    jnz loc_115D ; @01157
    mov bl,0x1 ; @01159
    jmp short loc_116B ; @0115B
loc_115D:
    cmp al,0x33 ; @0115D
    jnz loc_1165 ; @0115F
    mov bl,0x2 ; @01161
    jmp short loc_116B ; @01163
loc_1165:
    cmp al,0x34 ; @01165
    jnz loc_1110 ; @01167
    mov bl,0x3 ; @01169
loc_116B:
    lea si,[0x239f] ; @0116B
    db 0x22,0xdb ; ENCODED: and bl,bl (NASM chooses a different encoding) ; @0116F
    jnz loc_1176 ; @01171
    jmp loc_1200 ; @01173
loc_1176:
    lea si,[0x240b] ; @01176
    cmp bl,0x2 ; @0117A
    jz loc_11E2 ; @0117D
    lea si,[0x2442] ; @0117F
    cmp bl,0x3 ; @01183
    jz loc_11F4 ; @01186
    lea si,[0x23d2] ; @01188
    cmp bl,0x1 ; @0118C
    jz MarkStartupOptionAndRedraw ; @0118F
    jmp short loc_120C ; @01191
; S14 U008: [01193,01194) stored bytes remain UNKNOWN.
; Neighbours: P 01191 jmp 0x120c; N 01194 mov word ptr [di], 0x2020.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @01193
; T3 PLATFORM-CONDITIONAL startup composition:0031 forward leaves DI2012;1293 never assigns
; DI; early10E2/10EC/10F6 reaches the first store before interactive DI239F. Store2020
; sets2012=20/e0=20 but not target words; the next store uses DS:SI, not ES:PSP. Exact prefix
; profile:1A:AH=0000,21:AH=004A,10:AH=0000,21:AH=0002, optional21:AH=0007. Carrying state
; through marker BIOS additionally needs10:AH=000F/0002 plus intact saves/no interference. e0
; persists across sessions; ordinary row cursors miss probe/pointer words. Raw
; cursor/segment/IRQ writers remain UNRESOLVED.
; R3 startup marker: forward0031 leavesDI2012;1293 does not assignDI. Early
;10E2/10EC/10F6 may therefore store2012=20 and enable2013=20, not a target byte.
; PROFILE composition needs1A:AH=0000,21:AH=004A,10:AH=0000,21:AH=0002 and
; optional palette-prompt21:AH=0007, plus intact code/saves/no interference.
; Normal interactive row cursors239F/23D2/240B/2442/248A miss the pointer words;
; raw/altered cursors remain unchecked. LoaderDF0 is original evidence.
; [01194] DI/SI are unchecked marker cursors. If startup0031 ran forward and services preserved DI, DI=2012 here via10E2/10EC/10F6: word2020 changes RasterMeasurementMode2011 high byte2012 and first DisplayProbeRecords enable2013. Parser1293 changes SI but not DI. This is an original startup-option overlap, not a separate high-byte flag. Arbitrary incoming cursors may hit25A0 or other state; do not replace these stores with fixed menu-row writes.
MarkStartupOptionAndRedraw:
    mov word [di],0x2020 ; @01194
    mov word [si],0x3e2d ; @01198
    db 0x8b,0xfe ; ENCODED: mov di,si (NASM chooses a different encoding) ; @0119C
    push di ; @0119E
    push bx ; @0119F
    mov ah,0xf ; @011A0
    int 0x10 ; @011A2
    mov ah,0x2 ; @011A4
    mov dx,0x100 ; @011A6
    int 0x10 ; @011A9
    lea bx,[0x2384] ; @011AB
    call WriteZeroTerminatedDosText ; @011AF
    pop bx ; @011B2
    pop di ; @011B3
    ret ; @011B4
loc_11B5:
    lea si,[0x239f] ; @011B5
    db 0x22,0xdb ; ENCODED: and bl,bl (NASM chooses a different encoding) ; @011B9
    jz loc_11DC ; @011BB
    lea si,[0x240b] ; @011BD
    cmp bl,0x2 ; @011C1
    jz loc_11DC ; @011C4
    lea si,[0x2442] ; @011C6
    cmp bl,0x3 ; @011CA
    jz loc_11DC ; @011CD
    lea si,[0x23d2] ; @011CF
    cmp bl,0x1 ; @011D3
    jz loc_11DC ; @011D6
    lea si,[0x248a] ; @011D8
loc_11DC:
    call MarkStartupOptionAndRedraw ; @011DC
    jmp loc_1110 ; @011DF
loc_11E2:
    mov byte [0x200a],0xff ; @011E2
    mov byte [PrivateVectorNumber-GameDataImage],0x74 ; @011E7
    mov word [0x1fc9],0x3468 ; @011EC
    jmp short MarkStartupOptionAndRedraw ; @011F2
loc_11F4:
    mov byte [0x200b],0xff ; @011F4
    mov byte [ConfigurationOption200E-GameDataImage],0xff ; @011F9
    jmp short MarkStartupOptionAndRedraw ; @011FE
loc_1200:
    mov byte [ConfigurationOption200E-GameDataImage],0xff ; @01200
    mov byte [0x200c],0xff ; @01205
    jmp short MarkStartupOptionAndRedraw ; @0120A
loc_120C:
    lea si,[0x248a] ; @0120C
    call MarkStartupOptionAndRedraw ; @01210
    mov ax,0x4c00 ; @01213
    int 0x21 ; @01216
WriteZeroTerminatedDosText:
    mov dl,[bx] ; @01218
    inc bx ; @0121A
    db 0x22,0xd2 ; ENCODED: and dl,dl (NASM chooses a different encoding) ; @0121B
    jz loc_1227 ; @0121D
    push bx ; @0121F
    mov ah,0x2 ; @01220
    int 0x21 ; @01222
    pop bx ; @01224
    jmp short WriteZeroTerminatedDosText ; @01225
loc_1227:
    ret ; @01227
WriteHexWordAtLiveCursor:
    push ax ; @01228
    mov cl,0x4 ; @01229
    shr ah,cl ; @0122B
    call WriteHexHighNibbleAtLiveCursor ; @0122D
    pop ax ; @01230
    call WriteHexHighNibbleAtLiveCursor ; @01231
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @01234
    push ax ; @01236
    mov cl,0x4 ; @01237
    shr ah,cl ; @01239
    call WriteHexHighNibbleAtLiveCursor ; @0123B
    pop ax ; @0123E
WriteHexHighNibbleAtLiveCursor:
    and ah,0xf ; @0123F
    db 0x8a,0xdc ; ENCODED: mov bl,ah (NASM chooses a different encoding) ; @01242
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @01244
    add bx,0x224f ; @01246
    mov dl,[bx] ; @0124A
    mov [si],dl ; @0124C
    inc si ; @0124E
    ret ; @0124F
; S14 U009: [01250,01293) stored bytes remain UNKNOWN.
; Neighbours: P 0124F ret; N 01293 mov es, word ptr [0x1ff6].
; Candidate decimal formatter1250 saves/restores AX, clears DH (leading-digit latch), calls1271 with divisors2710/03E8/0064/000A; writes four leading-space/digit bytes and final ones to DS:SI. SI advances four times, not after final byte.1271 INC DL/SUB AX,CX loops while unsigned no-borrow, adds divisor back, converts quotient to ASCII. First nonzero quotient sets DH=FF; preceding zero quotients emit20. CX/DX/flags clobber; DS/DF unchanged; SS saves/returns live. Relative calls1256/125C/1262/1268->1271, branches1277->1273,1281->128B,1286->128F,1291->128B are internal candidate evidence, not a proved entry.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x50,0x32,0xf6,0xb9,0x10,0x27,0xe8,0x18,0x00,0xb9,0xe8,0x03,0xe8,0x12,0x00,0xb9 ; @01250
; UNKNOWN: unresolved bytes
    db 0x64,0x00,0xe8,0x0c,0x00,0xb9,0x0a,0x00,0xe8,0x06,0x00,0x04,0x30,0x88,0x04,0x58 ; @01260
; UNKNOWN: unresolved bytes
    db 0xc3,0x32,0xd2,0xfe,0xc2,0x2b,0xc1,0x73,0xfa,0x03,0xc1,0x80,0xc2,0x2f,0xf6,0xc6 ; @01270
; UNKNOWN: unresolved bytes
    db 0xff,0x75,0x08,0x80,0xfa,0x30,0x74,0x07,0x80,0xce,0xff,0x88,0x14,0x46,0xc3,0xb2 ; @01280
; UNKNOWN: unresolved bytes
    db 0x20,0xeb,0xf8 ; @01290
; S18 executable option paths: switches are one-byte case-folded selectors
; after '-' or '/', not validated whole tokens. /e ->1F7C=2 attribute palette;
; /v ->4 DAC palette.106E prompt key1 chooses4,key2 chooses2; no independent
; display-renderer image is selected. Candidate131A/1322 store8/0 but have
; no recovered incoming option branch; retain UNKNOWN and do not invent keys.
; /2 writes word2011=00C8 (A0 raster cycles); /4 writes0190 (140 cycles).
; /x ->200E=FF; /d ->200B=200E=FF; /o ->200D=200C=FF;
; /p ->200A=FF,private vector74,reload3468,CRTC3D4,status3DA;
; /m ->200F=FF,CRTC3D4,status3DA (200F alreadyFF at startup0045).
; /i consumes following decimal into wrapped16 BX,only nonzero replaces1FC9.
; 200B suppresses mouse button publication and changes keyboard controller
; handling;200A gates keyboard controller acknowledgments;200C controls
; palette sequencer blanking;200D bypasses startup options. Exact200E=FF
; changes reload calibration,foreground/IRQ raster timing,palette transitions
; and loads MAIN.DAT section6 at597D; not merely a display-name preference.
; Menu row0 sets200E/200C,row1 no flags,row2 takes11E2 (/p state except
; no explicit CRTC stores),row3 takes11F4 (/d),row4 exitsDOS4C. SI/DI marker
; quirks1194 remain live; these are not proof of immutable display-probe rows.
; /a premarks2010=FF but054E then FALLS BACK to speaker state2010=0,
;25A7=1,1F71=1. /n disables mouse via1F73=FF and0F64 selects keyboard2.
; Options change services/state within this executable, not asset variants.
ParsePspCommandLine:
; READY: PSP length byte at ES:80, scan for '-'/'/', one switch byte, signed
; A..Z fold only. a:2010=FF e/v:1F7C=2/4 n:1F73=FF d:200B=200E=FF p:200A=FF,
; private IRQ 74, reload 3468, ports 3D4/3DA o:200D=200C=FF x:200E=FF m:200F=FF,
; ports 3D4/3DA 2/4:word 2011=200/400 (writes 2012 past the clear). No token
; validation; unknown switches fall through the final CMP 'x'.
    mov es,[StartupPspSegment1FF6-GameDataImage] ; @01293
    mov si,0x80 ; @01297
    mov cl,[es:si] ; @0129A
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @0129D
    jcxz loc_12B0 ; @0129F
    inc si ; @012A1
loc_12A2:
    mov al,[es:si] ; @012A2
    inc si ; @012A5
    cmp al,0x2d ; @012A6
    jz loc_12B1 ; @012A8
    cmp al,0x2f ; @012AA
    jz loc_12B1 ; @012AC
loc_12AE:
    loop loc_12A2 ; @012AE
loc_12B0:
    ret ; @012B0
loc_12B1:
    dec cx ; @012B1
    jcxz loc_12B0 ; @012B2
    mov al,[es:si] ; @012B4
    inc si ; @012B7
    cmp al,0x41 ; @012B8
    jl loc_12C2 ; @012BA
    cmp al,0x5a ; @012BC
    jg loc_12C2 ; @012BE
    or al,0x20 ; @012C0
loc_12C2:
    cmp al,0x61 ; @012C2
    jz loc_1303 ; @012C4
    cmp al,0x6d ; @012C6
    jnz loc_12CD ; @012C8
    jmp loc_1377 ; @012CA
loc_12CD:
    cmp al,0x6e ; @012CD
    jnz loc_12D4 ; @012CF
    jmp loc_138B ; @012D1
loc_12D4:
    cmp al,0x64 ; @012D4
    jnz loc_12DB ; @012D6
    jmp short loc_1358 ; @012D8
; S14 U010: [012DA,012DB) stored bytes remain UNKNOWN.
; Neighbours: P 012D8 jmp 0x1358; N 012DB cmp al, 0x65.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @012DA
loc_12DB:
    cmp al,0x65 ; @012DB
    jz loc_130A ; @012DD
    cmp al,0x70 ; @012DF
    jz loc_133A ; @012E1
    cmp al,0x6f ; @012E3
    jnz loc_12EA ; @012E5
    jmp short loc_1364 ; @012E7
; S14 U011: [012E9,012EA) stored bytes remain UNKNOWN.
; Neighbours: P 012E7 jmp 0x1364; N 012EA cmp al, 0x76.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @012E9
loc_12EA:
    cmp al,0x76 ; @012EA
    jz loc_1312 ; @012EC
    cmp al,0x32 ; @012EE
    jz loc_132A ; @012F0
    cmp al,0x34 ; @012F2
    jz loc_1332 ; @012F4
    cmp al,0x69 ; @012F6
    jnz loc_12FD ; @012F8
    jmp loc_1393 ; @012FA
loc_12FD:
    cmp al,0x78 ; @012FD
    jz loc_1370 ; @012FF
loc_1301:
    jmp short loc_12AE ; @01301
loc_1303:
    mov byte [0x2010],0xff ; @01303
    jmp short loc_1301 ; @01308
loc_130A:
    mov word [0x1f7c],0x2 ; @0130A
    jmp short loc_1301 ; @01310
loc_1312:
    mov word [0x1f7c],0x4 ; @01312
    jmp short loc_1301 ; @01318
; S14 U012: [0131A,0132A) stored bytes remain UNKNOWN.
; Neighbours: P 01318 jmp 0x1301; N 0132A mov word ptr [0x2011], 0xc8.
; Candidate parser arms131A/1322 store word DS:1F7C=0008/0000, then1320/1328 jump known parser continuation1301. Outgoing shared tails do not prove incoming entries or original option keys. No004A FF store.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0xc7,0x06,0x7c,0x1f,0x08,0x00,0xeb,0xdf,0xc7,0x06,0x7c,0x1f,0x00,0x00,0xeb,0xd7 ; @0131A
loc_132A:
; WORD OWNERSHIP:2011 low/2012 high are one little-endian measurement selector.
;132A writes00C8;1332 writes0190;15C2 reads BOTH bytes. Stored word is0000.
; DF-clear startup0031 clears only its low byte2011:2012 retains stored00
; unless another writer intervenes. Neither a separate flag nor an unused gap.
; Concrete indexed writer:0031 leaves DI2012;parser1293 does not change DI.
; With services preserving DI, option-marker tail10E2/10EC/10F6 ->1194 stores
;2020 at2012/2013 (mode high byte and first probe enable). No zero-high-byte
; invariant follows from omitting /2 or /4 on those paths; keep the marker bug.
    mov word [RasterMeasurementMode2011-GameDataImage],0xc8 ; @0132A
    jmp short loc_1301 ; @01330
loc_1332:
    mov word [RasterMeasurementMode2011-GameDataImage],0x190 ; @01332
    jmp short loc_1301 ; @01338
loc_133A:
    mov byte [0x200a],0xff ; @0133A
    mov byte [PrivateVectorNumber-GameDataImage],0x74 ; @0133F
    mov word [0x1fc9],0x3468 ; @01344
    mov word [DisplayControllerBasePort-GameDataImage],0x3d4 ; @0134A
    mov word [0x1fdc],0x3da ; @01350
    jmp short loc_1301 ; @01356
loc_1358:
    mov byte [0x200b],0xff ; @01358
    mov byte [ConfigurationOption200E-GameDataImage],0xff ; @0135D
    jmp short loc_1301 ; @01362
loc_1364:
    mov byte [StartupOptionSelectionBypass200D-GameDataImage],0xff ; @01364
    mov byte [0x200c],0xff ; @01369
    jmp short loc_1301 ; @0136E
loc_1370:
    mov byte [ConfigurationOption200E-GameDataImage],0xff ; @01370
    jmp short loc_1301 ; @01375
loc_1377:
    mov byte [StartupOption200F-GameDataImage],0xff ; @01377
    mov word [DisplayControllerBasePort-GameDataImage],0x3d4 ; @0137C
    mov word [0x1fdc],0x3da ; @01382
    jmp loc_1301 ; @01388
loc_138B:
    mov byte [MouseServicesDisabledByte-GameDataImage],0xff ; @0138B
    jmp loc_1301 ; @01390
loc_1393:
    call ParsePspTimerReloadDecimal ; @01393
    db 0x23,0xdb ; ENCODED: and bx,bx (NASM chooses a different encoding) ; @01396
    jz loc_139E ; @01398
    mov [0x1fc9],bx ; @0139A
loc_139E:
    db 0x23,0xc9 ; ENCODED: and cx,cx (NASM chooses a different encoding) ; @0139E
    jnz loc_13A5 ; @013A0
    jmp loc_12B0 ; @013A2
loc_13A5:
    jmp loc_12AE ; @013A5
ParsePspTimerReloadDecimal:
; READY: decrements/tests CX after loading a byte, so the last byte may be
; read and discarded; BX=BX*10+digit mod 65536; first non-digit consumed;
; only nonzero BX replaces reload 1FC9. Distinct returns 12B0/13DB.
    db 0x33,0xdb ; ENCODED: xor bx,bx (NASM chooses a different encoding) ; @013A8
    mov al,[es:si] ; @013AA
    inc si ; @013AD
    dec cx ; @013AE
    db 0x23,0xc9 ; ENCODED: and cx,cx (NASM chooses a different encoding) ; @013AF
    jnz loc_13B6 ; @013B1
    jmp loc_12B0 ; @013B3
loc_13B6:
    cmp al,0x20 ; @013B6
    jz ParsePspTimerReloadDecimal ; @013B8
loc_13BA:
    cmp al,0x30 ; @013BA
    jl loc_13DB ; @013BC
    cmp al,0x39 ; @013BE
    jg loc_13DB ; @013C0
    sub al,0x30 ; @013C2
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @013C4
    shl bx,1 ; @013C6
    db 0x8b,0xd3 ; ENCODED: mov dx,bx (NASM chooses a different encoding) ; @013C8
    shl bx,1 ; @013CA
    shl bx,1 ; @013CC
    db 0x03,0xda ; ENCODED: add bx,dx (NASM chooses a different encoding) ; @013CE
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @013D0
    dec cx ; @013D2
    jcxz loc_13DB ; @013D3
    mov al,[es:si] ; @013D5
    inc si ; @013D8
    jmp short loc_13BA ; @013D9
loc_13DB:
    ret ; @013DB
; T3 per-call recurrence (UNCONDITIONAL instruction implication; BIOS traversal
; PLATFORM-CONDITIONAL): preserve e0=2013 and all four pointer words; clear adapter pairs;
; replace later enables with FF on EACH detector call. Successful1410 clears later flags,
; then rearms mono iff a pair with low1 was removed. Otherwise1462 leaves all FF if BL10;
; recognized lookup high1 clears mono, other high clears color. CRTC/final swap do not change
; enables. Prior suppression never suppresses the next executed detector.
; Recurrence requires game DS, DF0 at every LODS, intact targets/SI/CX/returns, DI2006 and no
; other writer. Exact profile:10:AX=1A00,10:AH=0012(BL10), conditional10:AH=000F.
; CONSERVATIVE preservation is unknown; PROFILE does not fix BIOS results or close
; IRQ/frame/alias/writers. VGA alone does not enable e0. If e0!=0 and AL1A/BL07-or08/BH00,
; only1410 runs and later flags end0; these are additional actual-result premises.
; R3 conditional table lifetime: DATA-A five0420-byte ground files stop1F6A,
; excluding their overwrite of2013..201E; request1000 could still replace them.
; First00C8 measurement precedes GROUND; session0468 follows455D resource load.
;455B and03E7 do not restore the probe records. VGA alone does not enable2013.
; With enabled row0,AL1A/active07-or08/alternate00 at1413 disables later rows:
; only1410 is called, conditional on these actual BIOS results/intact traversal.
; Preserve broader BIOS/alternative rows; profile preservation fixes no results.
; S18 ALTERNATE DISPLAY INVENTORY (main image, not separate CGA/EGA builds).
; READINESS CONDITIONAL: original port/BIOS operations are understood locally;
; hardware results, DS/DF/DI, live records/saves and writer closure stay open.
; 1410 runs iff live2013 enable !=0 (stored0; detector does not set it).
; INT10 AX1A00 must return AL1A; else no state store. Success maps BL/BH
; through unchecked CS1536 word indexes into pairs2006/2008, clears later
; enables2016/2019/201C, removes any pair with type-low1 and reenables201C.
; 1462 runs iff current2016!=0 (13EE setsFF before traversal). INT10 AH12,
; BL10 unchanged means absent. Otherwise CS1530[(CL>>1)] supplies high byte,
; low3;1523 stores pair. High1 disables mono201C, others disable color2019.
; 1490 runs iff current2019!=0 (13E9 setsFF). Probe14E0 writes/readbacks66
; in CRTC0F at3D4/3D5, restores sampled old value; CF0 stores0202, CF1 none.
; 14A0 runs iff current201C!=0 (13F3 setsFF). Same probe at3B4/3B5 must
; pass.3BA bit7 sampled then <=8000h transition polls: no transition stores
; 0101; transition reads status&70:10 ->0181,50 ->0382,other ->0180.
; These raw mono/extended-mono types are retained, not discarded as non-VGA.
; 1523 fills primary if its low byte0, otherwise overwrites secondary.14FA
; may swap pairs: secondary nonzero,both signed type-low<4,and BIOS0F mode
; low3==7 OR (mode!=7 and primary high==1). Lookup results are not validated.
; Detector does not select a new video mode or rewrite1FDA from its pair.
; 15AD uses primary high signed<3 for A0 measurement cycles,else140; /2
; forcesA0,/4 forces140; exact200E=FF bypasses detector with reload4000.
; BIOS/ports may change segments,flags,DI and live saves; no generic hardware
; auto-adapter translation or provider success is implied by these branches.
; 000BB uses BIOS000D,0FB2 uses008D (preserve-video-memory bit),4BE7 uses
; 0090 (same bit plus mode10);106E uses0003. They are literal calls,not
; alternate CGA/Hercules renderers.0FF8 restores saved mode then saved page.
; Recovered BIOS/DCC/CRTC alternatives remain executable inventory even in
; the primary VGA+AdLib configuration. Native provider lookup/timed-port
; substitutions have unverified equivalence outside their declared domain.
; VIDEO PROBES /1407 TARGET CONTRACT:conditional four-record traversal.
; DS=relocated09A9,DF=0 at EVERY LODS, preserved loop saves and intact pointer
; bytes give rows2013:{enable,1410},2016:{enable,1462},2019:{enable,1490},
;201C:{enable,14A0}; final SI=201F,CX=0. Entry assigns SI/CX/DI but NOT DS/DF.
; Stored enables are all00;13E9/13EE/13F3 set the last three toFF on each call.
;2013 is neither set nor cleared here:it is a live input retained from its owner.
; Startup1194 can set2013=20 via a word store with DI2012,also changing2012.
; In an intact initial table1410 is skipped,so normally only three targets may
; run; the four-target set includes an explicitly enabled first row.
; Each byte TEST precedes LODSW;LODSW leaves ZF unchanged, even for disabled rows.
; Word is sampled BEFORE PUSH SI/CX/CALL;their aliases cannot change current AX
; but can corrupt subsequent records/saves. If Q=SP at13DC, savedSI is Q-2,
; savedCX Q-4 and callback return1409 Q-6. Nominal children balance their CALLs;
; BIOS INT10 adds FLAGS/CS/IP and IRET must restore the actual current frame.
; SI/CX are reread at1409/140A;DS,DI,DF are NOT saved by the loop. Require BIOS
; to preserve game DS,DI=2006 and DF0, return same SS:SP and preserve loop words.
; Known callbacks' indexed stores142A/1438/1458/152D (and final151D/1520)
; then affect only pairs2006..2009,not pointer bytes. A changed BIOS DI/DS
; makes those stores additional possible table writers. Lookup indexes into
; CS1530/1536 are unchecked; returned BL/CL are not normalized.
; Enable writers:143A/143F/1444 clear2019/2016/201C;145C sets201C=FF;
;1483 or148A clears2019 or201C. These writes gate later live iterations.
; No decoded absolute store writes the four pointer words. That is NOT a
; whole writer proof:GROUND1A18 can overwrite2013..201E (file04C8..04D3),
; unchecked30F3 slot179(decimal),SI1FFF,clears1FFF..202B and3140 writes
; record+14=2013/2014;1194/1198 marker cursors,ES strings,SS aliases,external
; services and UNKNOWN paths remain. Supplied GROUND420 bytes stop at1F6A.
; DF=1 with no callbacks changing state reads (enable,pointer-address) pairs
;(2013,2012),(2010,200F),(200D,200C),(200A,2009),ending SI2007. These are NOT
; the four records;nonzero options can dispatch arbitrary words. No local CLD.
; READINESS CONDITIONAL:known set closed only for intact row words,DS/DF/DI,
; stack and provider ownership above;unrestricted writer/lifetime closure open.
; Native unbound-target stops are transport limits at1407,not original behavior.
; BIOS/CRTC timing and asynchronous IRQ memory effects stay platform seams.
; See docs/video-probe.md and s4 integration report for the precise residue.
DetectVideoAdapters:
    lea di,[PrimaryDetectedAdapterPair-GameDataImage] ; @013DC
    mov word [di],0x0 ; @013E0
    mov word [di+0x2],0x0 ; @013E4
    mov byte [ColorCrtcProbeEnableByte-GameDataImage],0xff ; @013E9
    mov byte [EgaProbeEnableByte-GameDataImage],0xff ; @013EE
    mov byte [MonoCrtcProbeEnableByte-GameDataImage],0xff ; @013F3
    mov cx,0x4 ; @013F8
    lea si,[DisplayProbeRecords-GameDataImage] ; @013FB
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_13FF:
    lodsb ; @013FF
    test al,al ; @01400
; S19 DF-site census lodsw ax, word ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsw ; @01402
    jz loc_140B ; @01403
    push si ; @01405
    push cx ; @01406
; R3 global1407 closure remains UNRESOLVED in CONSERVATIVE and PROFILE. Local
; forward four-row theorem requires intact target words,DF0 on everyLODS,gameDS,
; DS/DI2006 preservation and actual savedSI/CX/returns surviving. PROFILE service
; entries10:AX=1A00,10:AH=0012(BL10),10:AH=000F prove local preservation only.
; Numeric indexed witness:slotB3 starts1FFF;3140 at2013 writes6170 across enable
; and target-low, leaving target2014=0061 after30F3 clear. Actual arrival/survival
; toB3 and IRQ/alias/provider writer domains remain open; no new edge is asserted.
; S19 probe-sufficient-df-domain: CONSERVATIVE=UNRESOLVED; PROFILE=PLATFORM-CONDITIONAL.
; Explicit entry13DC DF0/gameDS retains DF0/gameDS at1407 under declared BIOS functions in the
; serial intact-save domain. This does not prove traversal bounds or pointer writers.
; Profile entries: 10:AX=1A00, 10:AH=0012, 10:AH=000F.
; Dependencies: Entry13DC DF0/gameDS; fixed decoded edges; no IRQ; intact saves;
; pointer-byte/four-row lifetime remains separate.
; S19 probe-global-traversal: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; Global traversal remains open despite the sufficient BIOS-preserving domain. Stored
; enables/targets are mutable and four-row progression is not certified.
; Dependencies: 2011/2012 marker overlap at2013; long GROUND/request and indexed/string/alias
; writers; actual DF/DS and saves.
; S17 flow-state: No caller-independent DF/DS/SS invariant was proved. Undeclared
; BIOS1413/1466 makes later loop iterations unknown even in serial intact-save analysis.
; In the explicit sufficient domain (entry13DC DF0/game DS, fixed known edges, intact
; saves, no IRQ; BIOS1413/1466/150D preserves DS/DI/caller stack and returns through
; intact FLAGS/CS/IP), DF0 and game DS hold at every modeled1407 visit. This is a
; conditional service declaration, not a verified BIOS ABI. Pointer-byte lifetime and
; four-row traversal bounds remain S4 obligations; target_domain_complete=false.
    call ax ; @01407
    pop cx ; @01409
    pop si ; @0140A
loc_140B:
    loop loc_13FF ; @0140B
    jmp loc_14FA ; @0140D
ProbeDisplayCombination:
    mov ax,0x1a00 ; @01410
    int 0x10 ; @01413
    cmp al,0x1a ; @01415
    jnz loc_1461 ; @01417
    db 0x8b,0xcb ; ENCODED: mov cx,bx (NASM chooses a different encoding) ; @01419
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @0141B
    db 0x0a,0xed ; ENCODED: or ch,ch (NASM chooses a different encoding) ; @0141D
    jz loc_1431 ; @0141F
    db 0x8a,0xdd ; ENCODED: mov bl,ch (NASM chooses a different encoding) ; @01421
    db 0x03,0xdb ; ENCODED: add bx,bx (NASM chooses a different encoding) ; @01423
    mov ax,[cs:bx+BiosDisplayPairLookup] ; @01425
    mov [di+0x2],ax ; @0142A
    db 0x8a,0xd9 ; ENCODED: mov bl,cl (NASM chooses a different encoding) ; @0142D
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @0142F
loc_1431:
    db 0x03,0xdb ; ENCODED: add bx,bx (NASM chooses a different encoding) ; @01431
    mov ax,[cs:bx+BiosDisplayPairLookup] ; @01433
    mov [di],ax ; @01438
    mov byte [ColorCrtcProbeEnableByte-GameDataImage],0x0 ; @0143A
    mov byte [EgaProbeEnableByte-GameDataImage],0x0 ; @0143F
    mov byte [MonoCrtcProbeEnableByte-GameDataImage],0x0 ; @01444
    lea bx,[di] ; @01449
    cmp byte [bx],0x1 ; @0144B
    jz loc_1458 ; @0144E
    lea bx,[di+0x2] ; @01450
    cmp byte [bx],0x1 ; @01453
    jnz loc_1461 ; @01456
loc_1458:
    mov word [bx],0x0 ; @01458
    mov byte [MonoCrtcProbeEnableByte-GameDataImage],0xff ; @0145C
loc_1461:
    ret ; @01461
ProbeEgaConfiguration:
    mov bl,0x10 ; @01462
    mov ah,0x12 ; @01464
    int 0x10 ; @01466
    cmp bl,0x10 ; @01468
    jz loc_148F ; @0146B
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0146D
    shr al,1 ; @0146F
    lea bx,[DisplayConfigLookup] ; @01471
    cs xlatb ; @01475
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @01477
    mov al,0x3 ; @01479
    call StoreDetectedAdapterPair ; @0147B
    cmp ah,0x1 ; @0147E
    jz loc_148A ; @01481
    mov byte [ColorCrtcProbeEnableByte-GameDataImage],0x0 ; @01483
    jmp short loc_148F ; @01488
loc_148A:
    mov byte [MonoCrtcProbeEnableByte-GameDataImage],0x0 ; @0148A
loc_148F:
    ret ; @0148F
ProbeColorCrtc:
    mov dx,0x3d4 ; @01490
    call ProbeCrtcRegister0F ; @01493
    jc loc_149F ; @01496
    mov al,0x2 ; @01498
    mov ah,0x2 ; @0149A
    call StoreDetectedAdapterPair ; @0149C
loc_149F:
    ret ; @0149F
ProbeMonochromeCrtc:
    mov dx,0x3b4 ; @014A0
    call ProbeCrtcRegister0F ; @014A3
    jc loc_14DF ; @014A6
    mov dl,0xba ; @014A8
    in al,dx ; @014AA
    and al,0x80 ; @014AB
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @014AD
    mov cx,0x8000 ; @014AF
loc_14B2:
    in al,dx ; @014B2
    and al,0x80 ; @014B3
    db 0x3a,0xe0 ; ENCODED: cmp ah,al (NASM chooses a different encoding) ; @014B5
    loope loc_14B2 ; @014B7
    jnz loc_14C2 ; @014B9
    mov al,0x1 ; @014BB
    mov ah,0x1 ; @014BD
    jmp short StoreDetectedAdapterPair ; @014BF
; S14 U013: [014C1,014C2) stored bytes remain UNKNOWN.
; Neighbours: P 014BF jmp 0x1523; N 014C2 in al, dx.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @014C1
loc_14C2:
    in al,dx ; @014C2
    db 0x8a,0xd0 ; ENCODED: mov dl,al (NASM chooses a different encoding) ; @014C3
    and dl,0x70 ; @014C5
    mov ah,0x1 ; @014C8
    mov al,0x81 ; @014CA
    cmp dl,0x10 ; @014CC
    jz loc_14DC ; @014CF
    mov al,0x80 ; @014D1
    cmp dl,0x50 ; @014D3
    jnz loc_14DC ; @014D6
    mov al,0x82 ; @014D8
    mov ah,0x3 ; @014DA
loc_14DC:
    call StoreDetectedAdapterPair ; @014DC
loc_14DF:
    ret ; @014DF
ProbeCrtcRegister0F:
    mov al,0xf ; @014E0
    out dx,al ; @014E2
    inc dx ; @014E3
    in al,dx ; @014E4
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @014E5
    mov al,0x66 ; @014E7
    out dx,al ; @014E9
    mov cx,0x100 ; @014EA
loc_14ED:
    loop loc_14ED ; @014ED
    in al,dx ; @014EF
    xchg al,ah ; @014F0
    out dx,al ; @014F2
    cmp ah,0x66 ; @014F3
    jz loc_14F9 ; @014F6
    stc ; @014F8
loc_14F9:
    ret ; @014F9
loc_14FA:
    cmp word [di+0x2],byte +0x0 ; @014FA
    jz loc_1522 ; @014FE
    cmp byte [di],0x4 ; @01500
    jnl loc_1522 ; @01503
    cmp byte [di+0x2],0x4 ; @01505
    jnl loc_1522 ; @01509
    mov ah,0xf ; @0150B
    int 0x10 ; @0150D
    and al,0x7 ; @0150F
    cmp al,0x7 ; @01511
    jz loc_1519 ; @01513
    cmp byte [di+0x1],0x1 ; @01515
loc_1519:
    jnz loc_1522 ; @01519
    mov ax,[di] ; @0151B
    xchg [di+0x2],ax ; @0151D
    mov [di],ax ; @01520
loc_1522:
    ret ; @01522
StoreDetectedAdapterPair:
    lea bx,[di] ; @01523
    cmp byte [bx],0x0 ; @01525
    jz loc_152D ; @01528
    lea bx,[di+0x2] ; @0152A
loc_152D:
    mov [bx],ax ; @0152D
    ret ; @0152F
DisplayConfigLookup:
; DATA: lookup_table
    db 0x02,0x03,0x01,0x02,0x03,0x01 ; @01530
BiosDisplayPairLookup:
; DATA: lookup_table
    db 0x00,0x00,0x01,0x01,0x02,0x02,0x00,0x00,0x03,0x03,0x03,0x01,0x00,0x00,0x05,0x04 ; @01536
; DATA: lookup_table
    db 0x05,0x05,0x00,0x00,0x04,0x03,0x04,0x04,0x04,0x05 ; @01546
; CONTRACT: liveDS controller base is read once. ADD DL,6 keeps DH unchanged.
; IN byte polling waits forbit3set thenbit3clear; no native game timeout.
; AX highbyte and all other CPUfields remainlive; providers may changeRAM/RET.
; Logical/bus/finite-provider evidence: docs/display-status.md.
WaitForDisplayStatusBit3Cycle:
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @01550
    add dl,0x6 ; @01554
loc_1557:
DisplayStatusWaitSet:
    in al,dx ; @01557
    test al,0x8 ; @01558
    jz loc_1557 ; @0155A
loc_155C:
DisplayStatusWaitClear:
    in al,dx ; @0155C
    test al,0x8 ; @0155D
    jnz loc_155C ; @0155F
DisplayStatusReturn:
    ret ; @01561
; Query DOS3509, save ES then BX through returnedDS; caller saves remain live.
; Set DOS2509 to currentCS:16D4; returnedSS:SP owns POPES/POPDS/nearRET.
; Both INTs use full register/IRET contracts; STI is unconditional.
; See docs/keyboard-input.md for alias and provider boundaries.
InstallKeyboardVector:
    cli ; @01562
    push ds ; @01563
    push es ; @01564
    mov ax,0x3509 ; @01565
    int 0x21 ; @01568
KeyboardInstallAfterQuery156A:
    mov [SavedKeyboardVector-GameDataImage+2],es ; @0156A
    mov [SavedKeyboardVector-GameDataImage],bx ; @0156E
    mov dx,cs ; @01572
    mov ds,dx ; @01574
    mov dx,0x16d4 ; @01576
    mov ax,0x2509 ; @01579
    int 0x21 ; @0157C
KeyboardInstallAfterSet157E:
    pop es ; @0157E
    pop ds ; @0157F
    sti ; @01580
KeyboardInstallReturn1581:
    ret ; @01581
RestoreKeyboardVector:
; CONTRACT: actualPUSHDS may alter saved pointer fields before they are read.
; DOS2509 returns live general/segment/stack/flags; POPDS consumes returnedSS:SP.
    push ds ; @01582
    mov ax,0x2509 ; @01583
    mov dx,[SavedKeyboardVector-GameDataImage] ; @01586
    mov ds,[SavedKeyboardVector-GameDataImage+2] ; @0158A
RestoreKeyboardVectorInterrupt:
    int 0x21 ; @0158E
    pop ds ; @01590
RestoreKeyboardVectorReturn:
    ret ; @01591
; S14 U014: [01592,015AD) stored bytes remain UNKNOWN.
; Neighbours: P 01591 ret; N 015AD cmp byte ptr [0x200e], 0xff.
; Candidate1592 saves DS, sets DS=0, writes IVT09 offset16D4/segmentCS and IVT08 offset17C7/segmentCS, restores DS,RET. AX=0; no CLI/STI surrounds four vector-word writes, so IF-enabled delivery may observe partial installation. Handler identities make interpretation coherent but supply no incoming entry. Canonical IVT is distinct from game DS004A; aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x1e,0x33,0xc0,0x8e,0xd8,0xc7,0x06,0x24,0x00,0xd4,0x16,0x8c,0x0e,0x26,0x00,0xc7 ; @01592
; UNKNOWN: unresolved bytes
    db 0x06,0x20,0x00,0xc7,0x17,0x8c,0x0e,0x22,0x00,0x1f,0xc3 ; @015A2
; T3 UNCONDITIONAL call/lifetime: only decoded calls00C8 at startup and0468 every entered
; session; only detector call15D5.200E==FF skips detector; else exact2011=00C8/0190 skips it;
; ALL other words call13DC even if old1FC9!=0.15F8..15FD old-reload override happens AFTER
; detection/measurement, not as a probe cache. Bypasses preserve all records/pairs; detector
; rearms only later enables. Neither entry nor4551/03E7 restores pointer words/e0.
; Early1194 at DI2012 can replace selector high with20, turning /2 or /4 values into20C8/2090
; and enabling first probe20.200E=FF still wins the outer gate.
; Menu/input/code/result/aborted briefing do not call this routine; retry/next level
; reaching00FB calls0468 again. Actual records across
; resource/renderer/indexed/frame/provider writers remain UNRESOLVED.
; CALIBRATION: only full option byteFF chooses4000. Word2011 selects200/400
; or real detector output;signed primary high byte selects160/320 scanlines.
; CLI measurement yields BP=FFFF-CX;stored reload is then overridden by actual
; popped nonzero old word,followed by unconditional STI. No host-clock estimate.
CalibrateGameTimerReload:
    cmp byte [ConfigurationOption200E-GameDataImage],0xff ; @015AD
    jnz loc_15BB ; @015B2
    mov word [0x1fc9],0x4000 ; @015B4
    ret ; @015BA
loc_15BB:
; Neither calibration nor its sole decoded caller to13DC at15D5 establishes
; DF/game DS. A nonzero2011 word other than00C8/0190 ALSO falls into detection.
    mov ax,[0x1fc9] ; @015BB
    push ax ; @015BE
    mov bx,0x140 ; @015BF
    mov ax,[RasterMeasurementMode2011-GameDataImage] ; @015C2
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @015C5
    jz loc_15D5 ; @015C7
    cmp ax,0x190 ; @015C9
    jz loc_15E9 ; @015CC
    shr bx,1 ; @015CE
    cmp ax,0xc8 ; @015D0
    jz loc_15E9 ; @015D3
loc_15D5:
    call DetectVideoAdapters ; @015D5
    mov bx,0x140 ; @015D8
    lea di,[PrimaryDetectedAdapterPair-GameDataImage] ; @015DB
    mov al,[di+0x1] ; @015DF
    cmp al,0x3 ; @015E2
    jnl loc_15E9 ; @015E4
    mov bx,0xa0 ; @015E6
loc_15E9:
    cli ; @015E9
    call MeasureRasterPitCounter ; @015EA
    mov ax,0xffff ; @015ED
    db 0x2b,0xc1 ; ENCODED: sub ax,cx (NASM chooses a different encoding) ; @015F0
    db 0x8b,0xe8 ; ENCODED: mov bp,ax (NASM chooses a different encoding) ; @015F2
    mov [0x1fc9],bp ; @015F4
    pop ax ; @015F8
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @015F9
    jz loc_1600 ; @015FB
    mov [0x1fc9],ax ; @015FD
loc_1600:
    sti ; @01600
    ret ; @01601
; PIT MEASUREMENT: ADD DL,6 wraps only low byte;bit3 set/clear precedes PIT
; programming30/FFFF,then BX raster bit0 clear/set cycles (zero means65536).
; Commands06/36 precede two counter reads;LOOPs retain TEST flags.
; Native polling has no game timeout;only verification workers have limits.
MeasureRasterPitCounter:
    mov cx,0xffff ; @01602
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @01605
    add dl,0x6 ; @01609
loc_160C:
    in al,dx ; @0160C
    test al,0x8 ; @0160D
    jz loc_160C ; @0160F
loc_1611:
    in al,dx ; @01611
    test al,0x8 ; @01612
    jnz loc_1611 ; @01614
    mov al,0x30 ; @01616
    out 0x43,al ; @01618
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @0161A
    out 0x40,al ; @0161C
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0161E
    out 0x40,al ; @01620
    db 0x8b,0xcb ; ENCODED: mov cx,bx (NASM chooses a different encoding) ; @01622
loc_1624:
    in al,dx ; @01624
    test al,0x1 ; @01625
    jnz loc_1624 ; @01627
loc_1629:
    in al,dx ; @01629
    test al,0x1 ; @0162A
    jz loc_1629 ; @0162C
    loop loc_1624 ; @0162E
    mov al,0x6 ; @01630
    out 0x43,al ; @01632
    mov al,0x36 ; @01634
    out 0x43,al ; @01636
    nop ; @01638
    nop ; @01639
    nop ; @0163A
    in al,0x40 ; @0163B
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @0163D
    in al,0x40 ; @0163F
    db 0x8a,0xe8 ; ENCODED: mov ch,al (NASM chooses a different encoding) ; @01641
    ret ; @01643
; DOS21 owns all returned registers and the actual SS:SP IRET frame.
; Both POPDS are live. Sound segment1653 is a relocated instruction operand.
; ADD DL wraps without carrying into DH; status port stays fixed across polls.
; Reload1FC9 is read after polling. STI is unconditional; nearRET stays live.
; See docs/timer-install.md for lifecycle boundaries and bounded evidence.
InstallGameTimerVector:
    cli ; @01644
    push ds ; @01645
    mov ax,0x2508 ; @01646
    push cs ; @01649
    pop ds ; @0164A
    mov dx,0x17c7 ; @0164B
    int 0x21 ; @0164E
GameTimerInstallAfterVector08:
    pop ds ; @01650
    push ds ; @01651
GameTimerSoundSegmentOperand equ $+1
    mov ax,0x842 ; @01652
    mov ds,ax ; @01655
    mov ax,0x2560 ; @01657
    mov dx,0x182 ; @0165A
; S13: MAIN.DAT5 was decoded at5972 to relocated0842:0000 (758 bytes,08420..08715);INT60 enters0182.0492/0183 may reinstall without reloading,so live PC fields/table persist.16A9 restoresINT08 only;no recovered INT60 restore. Natural00/01/03 targets stay01D4/024F/01B0 only under intact separated image/stack;rawAH3E..47 can rewrite every table byte.
    int 0x21 ; @0165D
GameTimerInstallAfterVector60:
    pop ds ; @0165F
    mov dx,[DisplayControllerBasePort-GameDataImage] ; @01660
    add dl,0x6 ; @01664
loc_1667:
    in al,dx ; @01667
    test al,0x8 ; @01668
    jz loc_1667 ; @0166A
loc_166C:
    in al,dx ; @0166C
    test al,0x8 ; @0166D
    jnz loc_166C ; @0166F
    cli ; @01671
    mov cx,[TimerPitReload1FC9-GameDataImage] ; @01672
    mov al,0x36 ; @01676
    out 0x43,al ; @01678
    jmp short loc_167C ; @0167A
loc_167C:
    jmp short loc_167E ; @0167C
loc_167E:
    jmp short loc_1680 ; @0167E
loc_1680:
    db 0x8a,0xc1 ; ENCODED: mov al,cl (NASM chooses a different encoding) ; @01680
    out 0x40,al ; @01682
    jmp short loc_1686 ; @01684
loc_1686:
    jmp short loc_1688 ; @01686
loc_1688:
    jmp short loc_168A ; @01688
loc_168A:
    db 0x8a,0xc5 ; ENCODED: mov al,ch (NASM chooses a different encoding) ; @0168A
    out 0x40,al ; @0168C
    jmp short loc_1690 ; @0168E
loc_1690:
    jmp short loc_1692 ; @01690
loc_1692:
    jmp short loc_1694 ; @01692
loc_1694:
    sti ; @01694
GameTimerInstallReturn:
    ret ; @01695
; S14 U015: [01696,016A9) stored bytes remain UNKNOWN.
; Neighbours: P 01695 ret; N 016A9 push ds.
; Candidate1696 CLI,AL36/OUT43,CX=live DS1FC9,low then high reload bytes OUT40,STI,RET. Forces IF=1; DF/segments unchanged; AX/CX clobber. No data-memory write. Entry/device lifetime unproved.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0xfa,0xb0,0x36,0xe6,0x43,0x8b,0x0e,0xc9,0x1f,0x8a,0xc1,0xe6,0x40,0x8a,0xc5,0xe6 ; @01696
; UNKNOWN: unresolved bytes
    db 0x40,0xfb,0xc3 ; @016A6
; Restore PIT, IVT08, then startup BIOS clock; no IRQ scheduling is inferred.
; PUSHDS precedes live LES. IVT writes may replace the saved DS/outer RET.
; STI always enables IF; POPDS then selects both clock reads. BIOS owns returned state.
RestoreTimerState:
    push ds ; @016A9
    cli ; @016AA
    mov al,0x36 ; @016AB
TimerRestoreControlPort:
    out 0x43,al ; @016AD
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @016AF
TimerRestoreCounterLowPort:
    out 0x40,al ; @016B1
TimerRestoreCounterHighPort:
    out 0x40,al ; @016B3
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @016B5
    les bx,[SavedTimerVector-GameDataImage] ; @016B7
    mov ds,ax ; @016BB
    mov [0x20],bx ; @016BD
    mov [0x22],es ; @016C1
    sti ; @016C5
    pop ds ; @016C6
    mov cx,[SavedBiosClockHigh-GameDataImage] ; @016C7
    mov dx,[SavedBiosClockLow-GameDataImage] ; @016CB
    mov ah,0x1 ; @016CF
TimerRestoreClockInterrupt:
    int 0x1a ; @016D1
TimerRestoreReturn:
    ret ; @016D3
; U1 keyboard costs include CPU6:200A0 gives peak16 and no STI;200A!=0 gives peak20, but helper wait17BE runs IF0. First helper16E6 ends STI17BC/shadowed RET, exposing scan-save depth16 before EOI; IRQ0 may preempt, IRQ1/lower remain PIC-blocked. After EOI17A0->18B4, IF is already1: same/lower admitted requests may enter at18B6 with16 resident. Second helper17AC/PUSH AX17B4 leaves18 resident at17B5 beforeCLI, permitting a late fresh IRQ1 or IRQ0 there. This18-byte recurrent window is not the IF0 controller wait; after STI/shadowed RET17BD,17AF retains14. Each recurrence needs a new request and the appropriate PIC priority/IF boundary; physical arrival bounds unresolved.
; UNCONDITIONAL intact-control serial stack cost: CPU6 +four register saves8 +CALL17B4/its PUSH AX/CALL17BE6 =20 bytes. Scan AX temporary is popped before later calls. No polling iteration adds words. EOI17A0 precedes optional17AC helper;17BC STI shadow covers17BD RET,then an eligible IRQ can precede outer POPs. UNRESOLVED physical nesting and provider/frame aliases;do not assume this handler can occur only once over a timer.
; R1 UNCONDITIONAL local return implication: IRQ09 inherits DF; no CLD or STD occurs in
; its decoded body.17B3 IRET restores actual interrupted FLAGS. Handler-local DF is not a
; foreground normalization service. Keep keyboard frame/buffer aliases and nesting separate.
; S19 external-08-09: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; Two INT08 far chains have caller-built FLAGS/CS/IP and external IRET edges. Undocumented
; provider segments/registers and frame aliases remain open. IRQ09 owns IRET;old09 is
; restored,not an invented chain.
; Dependencies: Provider/frame preservation; vector/PIC/pending/nesting phases; keyboard
; buffer/save aliases.
; Four actual saves DS/AX/BX/CX. Relocated16D9 supplies the live game frame.
; Special7D/7E paths zeroAX before binding lookup, including releases.
; The separately popped raw scan owns the83-byte0F78 key-state array.
; Both controller gates are fresh reads; EOI and helper returns stay live.
; See docs/keyboard-input.md; no keyboard IRQ scheduling is inferred.
KeyboardIrqHandler:
    push ds ; @016D4
    push ax ; @016D5
    push bx ; @016D6
    push cx ; @016D7
KeyboardDataSegmentOperand16D9 equ $+1
    mov ax,0x9a9 ; @016D8
    mov ds,ax ; @016DB
    mov al,[KeyboardControllerGate200A-GameDataImage] ; @016DD
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @016E0
    jz loc_16E9 ; @016E2
    mov al,0xad ; @016E4
    call SendKeyboardControllerCommand ; @016E6
loc_16E9:
KeyboardAfterDisable16E9:
    in al,0x60 ; @016E9
    push ax ; @016EB
    in al,0x61 ; @016EC
    or al,0x80 ; @016EE
    out 0x61,al ; @016F0
    and al,0x7f ; @016F2
    out 0x61,al ; @016F4
    pop ax ; @016F6
    push ax ; @016F7
    mov bx,KeyboardBindings201F-GameDataImage ; @016F8
    mov cx,0x1 ; @016FB
    db 0x8a,0xe0 ; ENCODED: mov ah,al (NASM chooses a different encoding) ; @016FE
    and ah,0x7f ; @01700
    test al,0x80 ; @01703
    jnz loc_1736 ; @01705
    mov [KeyboardScanCodeByte-GameDataImage],ah ; @01707
    cmp byte [0x200b],0xff ; @0170B
    jnz loc_175A ; @01710
    cmp ah,0x7d ; @01712
    jnz loc_1723 ; @01715
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @01717
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0171C
    or word [InputButtonsWord-GameDataImage],byte +0x2 ; @0171E
loc_1723:
    cmp ah,0x7e ; @01723
    jnz loc_1734 ; @01726
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @01728
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @0172D
    or word [InputButtonsWord-GameDataImage],byte +0x1 ; @0172F
loc_1734:
    jmp short loc_175A ; @01734
loc_1736:
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @01736
    cmp byte [0x200b],0xff ; @0173B
    jnz loc_175A ; @01740
    cmp ah,0x7d ; @01742
    jnz loc_174E ; @01745
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @01747
    and word [InputButtonsWord-GameDataImage],byte -0x3 ; @01749
loc_174E:
    cmp ah,0x7e ; @0174E
    jnz loc_175A ; @01751
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @01753
    and word [InputButtonsWord-GameDataImage],byte -0x2 ; @01755
loc_175A:
    cmp byte [bx],0xff ; @0175A
    jz loc_1763 ; @0175D
    cmp ah,[bx] ; @0175F
    jz loc_176A ; @01761
loc_1763:
    inc bx ; @01763
    shl cx,1 ; @01764
    jnc loc_175A ; @01766
    jmp short loc_177F ; @01768
loc_176A:
    test al,0x80 ; @0176A
    jnz loc_1774 ; @0176C
    or [InputKeyMask1FC7-GameDataImage],cx ; @0176E
    jmp short loc_177F ; @01772
loc_1774:
    not cx ; @01774
    and [InputKeyMask1FC7-GameDataImage],cx ; @01776
    mov byte [KeyboardScanCodeByte-GameDataImage],0x0 ; @0177A
loc_177F:
    pop ax ; @0177F
    lea bx,[KeyboardStateBytes0F78-GameDataImage] ; @01780
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @01784
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @01786
    and al,0x7f ; @01788
    cmp al,0x53 ; @0178A
    jnl loc_17A0 ; @0178C
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0178E
    and cl,0x80 ; @01790
    xor cl,0x80 ; @01793
    test cl,0x80 ; @01796
    jz loc_179E ; @01799
    or cl,0x14 ; @0179B
; T2 UNCONDITIONAL:scan15 maps0F8D(slot55 callback low),scan42 maps0FBA(slot56 callback low);accepted make/break writes94/00,next scans affect high bytes.4D3A repeat handling also writes these bytes. Spill retains keyboard ownership;no membership guard.
loc_179E:
    mov [bx],cl ; @0179E
loc_17A0:
    call SendMasterPicEoi ; @017A0
KeyboardAfterEoi17A3:
    mov al,[KeyboardControllerGate200A-GameDataImage] ; @017A3
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @017A6
    jz loc_17AF ; @017A8
    mov al,0xae ; @017AA
    call SendKeyboardControllerCommand ; @017AC
loc_17AF:
KeyboardAfterEnable17AF:
    pop cx ; @017AF
    pop bx ; @017B0
    pop ax ; @017B1
    pop ds ; @017B2
KeyboardOuterIret17B3:
    iret ; @017B3
; Actual AX/CALL saves, CLI, bounded-by-CX wait, POPAX, OUT64, unconditionalSTI.
SendKeyboardControllerCommand:
    push ax ; @017B4
    cli ; @017B5
    call WaitKeyboardControllerClear ; @017B6
KeyboardCommandAfterWait17B9:
    pop ax ; @017B9
    out 0x64,al ; @017BA
    sti ; @017BC
KeyboardCommandReturn17BD:
    ret ; @017BD
; CX=0 then LOOPNE:65,536 busy samples, or stop after a bit1-clear sample.
; Leaves the last sample in AL and the decremented CX; no flags from LOOPNE.
WaitKeyboardControllerClear:
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @017BE
loc_17C0:
    in al,0x64 ; @017C0
    test al,0x2 ; @017C2
    loopne loc_17C0 ; @017C4
KeyboardWaitReturn17C6:
    ret ; @017C6
times -(($-$$) != 0x17c7) db 0

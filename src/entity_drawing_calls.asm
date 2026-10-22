; Maintained 3634..368D entity draw-call loop; IRQ/provider seams remain open.
times -(($-$$) != 0x3634) db 0 ; module start assertion
; CONTRACT: zero EntitySlotBound returns without clearing the count or formatting.
; Otherwise each live SS frame preserves CX/DI for a 2Dh-stride record. +26==FF
; skips drawing; the byte pass count increments before either drawing path.
; Children return live DS/ES. The callback comparison and signed +28>=1 select
; the point path; the sprite path brackets 706F with DS:0050 guard FF/00.
; The actual POP DI/CX controls the next record and LOOP, including aliases.
; 368A JMPs to the decimal field tail without a CALL frame; its RET consumes
; this routine's original caller word. UNKNOWN 366F is outside the known body.
; LIFETIME: creation30A6 clears/initializes a new0088+k*2D slot, then publishes
; it by INC0043. +26 starts00;20E2/22EE/2339/2FD1 markFF without reclaiming it.
; There is no separate drawing-active allocation or callback list. After a
; successful creation with unchanged bound/cursors, this loop includes that
; slot; all inactive predecessors still consume iterations. Per-level455B
; resets0043/storage with DF=0;03E7 reinstalls slots via0462->0FB2.
; CL's entry bound is at mostFF, so stable saved CX/DI yield numeric footprint
; [0088,2D5B) at boundFF, not a proven writable array. Slot50 begins0E98 and
; callback0EAC aliases the visibility clear4119 even with DF=0. No bound clamp
; protects spawn/visibility/loaded-level storage; corrupted saved CX/DI can
; widen this walk beyond the original byte-bound footprint.
; All four children use live segments; no DS/ES save surrounds them. Minimap
; and dirty/point children write SS maps/mirrors, which may alias records and
; actual saved loop words. The comparison365A is against LIVE DS:003C, not a
; fixed6BDB test. A changed slot003C can reroute the point path without a CALL
; through that slot. Under initialized slots,6BDB reaches706F only if signed
; frame+28<1; otherwise6E83 is a direct CALL. No target may be removed globally.
; Global nine-target closure remains open: DF=1 action5 byte-writes+14/+15,
; visibility and count spill write into slots, and706F uses a writable SS save.
; BOUNDED PREFIX: pinned nominal120 selections give header limit<=50h, so
; reset bound0 plus serialized limit writes/creation publication confines
; records to0088..0E97. This is conditional asset/lifetime evidence, not an
; array check. IRQ1874->4013 can lower the limit to B after30D5 passes and
; before314B increments to B+1; equality-only creation may then spill past50.
; Visibility DF0 cannot touch the prefix:4119 clears0EA8..0F77 and4131 starts
; at0EA6+(unsigned(origin)>>3), always above0E97. DF1 clears0DDA..0EA9,
; zeroing BOTH callback bytes of slots4C..4F (0DF8/0E25/0E52/0E7F). Its
; following29h-byte marker cannot reach the first three words; at slot4F it
; leaves0101 for origin>>3=0/1,0100 for2,0000 for>=3, absent other writers.
; Thus even a count50 is not callback-safe if visibility itself runs DF1.
; DF1 may be IRQ-local:1840 polls mouse before1874 commands/3FDE->410F,
; and18A7/18B1 restore foreground flags only AFTER that writer. Foreground
; DF0 alone is insufficient; require DF0 at each visibility invocation too.
; Minimap6FE2,dirty5726,point6E83 do not assign DS.706F likewise inherits DS;
; its optional6F7B and nine known callbacks restore DS from actual SS saves.
; With those saves intact the loop keeps main DS; ES is live (often A000),
; never an invariant record segment. Damaged saves/services remove the claim.
DrawEntityRecords:
; T2 UNCONDITIONAL index handoff: after publication of slotk<=FE,this loop
; and1F19/3CDE include it whenever live count>k and their saves survive; none
; checks that k<=4F or distinguishes a spill. FF construction publishes00,
; so normal update/draw/select never enumerate indexFF. Stale2005 scan may.
; Visibility-miss7086,exact+26=FF,and point-path365A are gates,not proofs that
; a corrupt callback can never reach715B. Visibility clears+26 too and can
; reactivate spilled or backward-overlapped records without a constructor.
; UNCONDITIONAL DF0 visibility with valid origin0010..0500 (multiple8):
; zero0EA8..0F77 then marker0EA6+t..0ECE+t,t=origin>>3 in2..A0. For slots
; 50..54 the callback is0000/0001/0100/0101 depending on marker intersection,
; all outside the nine. DF1 zeros4C..4E callbacks;4F is0100 at t2,else0000
; for t>=3. Actual origin/DF/record survival is a separate UNRESOLVED domain;
; nominal header origin bounds are DATA-CONDITIONAL,not granted by VGA/profile.
    mov di,EntityRecordsBase-GameDataImage ; @03634
    mov cl,[EntitySlotBound-GameDataImage] ; @03637
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @0363B
    jz EntityDrawingEarlyReturn ; @0363D
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @0363F
    mov [EntityDrawingPassCount-GameDataImage],ch ; @03641
EntityDrawingLoop:
    push cx ; @03645
    push di ; @03646
    cmp byte [di+EntityRecordDrawingSkipGate-EntityRecordsBase],0xff ; @03647
    jz EntityDrawingRestoreRecord ; @0364B
    inc byte [EntityDrawingPassCount-GameDataImage] ; @0364D
    call DrawEntityMinimapPixel ; @03651
EntityDrawingAfterMinimap:
    call MarkEntityDrawingDirty ; @03654
EntityDrawingAfterDirty:
    mov ax,[DrawingCallbackSlots-GameDataImage+0xe] ; @03657
    cmp ax,[di+EntityRecordSpriteCallback-EntityRecordsBase] ; @0365A
    jnz loc_3670 ; @0365D
    mov al,[di+EntityRecordFrameSelector-EntityRecordsBase] ; @0365F
    cmp al,0x1 ; @03662
    jl loc_3670 ; @03664
    push di ; @03666
    xchg si,di ; @03667
    call DrawEntityPointCloud ; @03669
EntityDrawingAfterPoints:
    pop di ; @0366C
    jmp short EntityDrawingRestoreRecord ; @0366D
; S14 U042: [0366F,03670) stored bytes remain UNKNOWN.
; Neighbours: P 0366D jmp 0x367d; N 03670 mov byte ptr [0x50], 0xff.
; Stored90; adjacent bypassing JMP is not proof of NOP execution,assembler padding,alignment or an unused lifetime. Unknown computed/return/IRQ entries and segment/index aliases remain.
; Checksum8397 reads this run in reset/advance domain below83B7; caller unresolved; no structural classification follows.
; No resolved incoming execution edge or relocation fixup intersects this run. Numeric word/address matches are not proved code pointers; computed/stack/provider aliases remain open.
; UNKNOWN: unresolved bytes
    db 0x90 ; @0366F
loc_3670:
    mov byte [EntityWorkGuard-GameDataImage],0xff ; @03670
    call DrawObjectSprite ; @03675
EntityDrawingSpriteResume:
    mov byte [EntityWorkGuard-GameDataImage],0x0 ; @03678
EntityDrawingRestoreRecord:
    pop di ; @0367D
    pop cx ; @0367E
    add di,byte +0x2d ; @0367F
    loop EntityDrawingLoop ; @03682
EntityDrawingDecimalTail:
    mov al,[EntityDrawingPassCount-GameDataImage] ; @03684
    mov si,StatusEntityCountField-GameDataImage ; @03687
EntityDrawingDecimalJump:
    jmp WriteDecimalByteField ; @0368A
EntityDrawingEarlyReturn:
    ret ; @0368D
times -(($-$$) != 0x368e) db 0 ; module end assertion

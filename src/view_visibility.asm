; Maintained 410F..414E leaf.
times -(($-$$) != 0x410f) db 0 ; module start assertion
; CONTRACT: shared JMP/fallthrough/CALL target adds no frame of its own.
; PUSH DS/POP ES and both DF-sensitive REP stores remain live. No map extent
; is inferred. The143E operand is relocated separately from liveSS; DS0026/28
; select marker offsets in that frame. Restore actual prior ES via AX, then STI.
RebuildViewVisibilityMap:
    push ds ; @0410F
    pop es ; @04110
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @04111
    mov di,ViewVisibilityMapBase-GameDataImage ; @04113
    mov cx,0x68 ; @04116
; R1: visibility4119/4131 retain entry DF; foreground0480 and IRQ3FDE are distinct callers.
; In the sufficient serial/intact mouse-mode0/live-AdLib domain, INT33 AX0003 profile plus
; original driver IRET preserve interrupted d before1840/1872/1874 ->3FDE; visibility sees d.
; 18A7 POPF and18B1 outer IRET happen afterward. Neither corrects prior DF1 memory writes.
; This conditional result closes a local handoff only; actual root inputs remain unresolved.
; S19 visibility-byte-effects: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; Stable DS=ES:4119 zeroes0EA8..0F77 at DF0 or0DDA..0EA9 at DF1. DF1 destroys callback words
; slots4C..4F;4131 writes01 at[0E7E+t,0EA6+t],t=unsigned(origin)>>3.
; Dependencies: Exact conditional-input footprint; stable count/cursors/segments and no other
; writers.
; S19 visibility-actual-df: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; IRQ1874->3FDE visibility observes1840 input and185F/1872 sound flags before outer
; POPF18A7/IRET18B1. Foreground DF0 alone does not settle this writer.
; Profile entries: 33:AX=0003.
; Dependencies: Input INT33 AX0003 if selected; original sound image/vector/dispatch lifetime;
; live42A5 callback; nesting and saved-frame writers.
; S17 flow-state: Entry410F retains incoming DF and SS through both4119 and4131 and sets
; ES from incoming DS. 4119 has AX0,CX0068,DI0EA8: DF0 clears0EA8..0F77; DF1
; clears0DDA..0EA9. The following29-byte fill4131 also retains DF. Timer-local service
; changes to DF can affect this body before outer saved FLAGS are restored; an intact
; outer IRET does not export that change to foreground FLAGS. Global DF and writer
; closure remain open.
; CALLBACK FOOTPRINT: DF0 zero0EA8..0F77 and marker01 from0EA6+(unsigned(origin)>>3) cannot touch nominal entity prefix0088..0E97, but index50+14=0EAC overlaps. DF1 clear0DDA..0EA9 zeros callback words of slots4C..4F; following29h marker cannot reach4C..4E (remain0000), and4F becomes0101 for origin>>3=0/1,0100 for2,0000 for>=3. Nominal header50 does not protect against DF1 or4013 publication race. These are RAM values, not asserted executable targets.
; With stable ES=DS and AX=0,104 STOSW write0EA8..0F77 for DF=0 or0DDA..0EA9 for DF=1. The backward range includes record indices4C..4F callbacks (0DF8/0E25/0E52/0E7F); forward range includes index50 callback0EAC if that unchecked slot exists. No CLD here.4131 writes29 bytes from0EA8+(unsigned(view_origin)>>3)-2 following DF, with16-bit cursor wrap. Do not infer record noninterference from a visibility-only name.
    rep stosw ; @04119
    mov di,[LevelViewOriginPixels-GameDataImage] ; @0411B
    shr di,1 ; @0411F
    shr di,1 ; @04121
    shr di,1 ; @04123
    dec di ; @04125
    dec di ; @04126
    add di,ViewVisibilityMapBase-GameDataImage ; @04127
    mov cx,0x29 ; @0412B
    mov ax,0x101 ; @0412E
; R3 UNCONDITIONAL footprint:marker start0EA6+t,t=unsigned(origin)>>3,29 bytes
; followingDF. DATA-A nominal headers produce0010..04A0 aligned10h; normal
; minimap/scroll producers preserve0010..0500 aligned8. With intact producers,
; t2..A0 gives DF0 union0EA8..0F6E orDF1 union0E80..0F46, missing2013/25A0.
; Corrupted origin can hit them:DF0 t1145..116D for2013,16D2..16FA for25A0;
; DF1 t116D..1195/16FA..1722. These are numeric witnesses,not normal reachability
; or a general origin clamp. Record overlap/DF1/race obligations remain separate.
; S19 visibility-byte-effects: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; Stable DS=ES:4119 zeroes0EA8..0F77 at DF0 or0DDA..0EA9 at DF1. DF1 destroys callback words
; slots4C..4F;4131 writes01 at[0E7E+t,0EA6+t],t=unsigned(origin)>>3.
; Dependencies: Exact conditional-input footprint; stable count/cursors/segments and no other
; writers.
; S19 visibility-actual-df: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; IRQ1874->3FDE visibility observes1840 input and185F/1872 sound flags before outer
; POPF18A7/IRET18B1. Foreground DF0 alone does not settle this writer.
; Profile entries: 33:AX=0003.
; Dependencies: Input INT33 AX0003 if selected; original sound image/vector/dispatch lifetime;
; live42A5 callback; nesting and saved-frame writers.
    rep stosb ; @04131
    cli ; @04133
    mov ax,es ; @04134
ViewVisibilityStackSegmentOperand equ $+1 ; relocated immediate in MOV CX
    mov cx,0x143e ; @04136
    mov es,cx ; @04139
    mov bx,[DrawingDirtyCellMapOffset-GameDataImage] ; @0413B
    mov byte [es:bx],0xff ; @0413F
    mov bx,[AlternateDrawingDirtyCellMapOffset-GameDataImage] ; @04143
    mov byte [es:bx],0xff ; @04147
    mov es,ax ; @0414B
    sti ; @0414D
ViewVisibilityReturn:
    ret ; @0414E
times -(($-$$) != 0x414f) db 0 ; module end assertion

; Maintained image span 0378A..03943; live level-object helpers.
; Reconstruction module, not a historical linker claim. See docs/object-records.md.
%if ($-$$) != 0x378a
    %error "level_objects start moved"
%endif
; V4 SOURCE/WORKING SCHEMA; words are LE, B denotes byte:
; +00 flagsW,+02 frameB,+03 limitB,+04 widthB,+05 heightB,+06 strideW,
; +08 maskDeltaW,+0A..0D opaque,+0E cellXW,+10 cellYW,+12 cellWidthB,
; +13 cellHeightB,+14 kindB,+15 animationBaseW,+17 currentSourceW,
; +19..1A opaque,+1B soundB. Opaque field roles remain UNRESOLVED.
; 37C2 reads GROUND directly; tick/draw reads working17CB+1C*j.397A recopy
; resets active slots, unlike tick animation. Source=(1B4B+1C*BEtype)&FFFF;
; every start congruent3 mod4 is possible. Type0024 reads known RGB row1F3B:
; flags=LE[R0,G0],frame=B0,limit=R1,width=G1,height=B1,stride=LE[R2,G2],
; mask=LE[B2,R3],base=LE[R7,G7],source=LE[B7,R8],sound=R9.
; Its cell fields read Xoff=LE[B4,R5],Yoff=LE[G5,B5],width=R6,height=G6,
; kind=B6. R/G/B are current slot3 color components. No invalid-type branch.
; Type002A selects1FE3 timer/selectors, but source LE1FFA reads unowned
; bytes: this partial map does not close their provenance. Zero-X copy skips
; all bytes; animation instead stores stale BX in flags. DF1 copies backward
; from each source/destination record start.
; R1 UNCONDITIONAL input implication: all37B4 copies inherit entry DF. Each copies1C bytes
; from its wrapped unchecked type*1C source. SavedSI/CX/DI restore after the REP, while outer
; DI adds1C even if REP ran backward. PROFILE supplies no missing entry DF or allocation bound;
; actual ProgramEntry-to-copy DF remains UNRESOLVED in both modes.
; S19 level-clear-and-copies: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; Level clear,odd-header and28-byte object copies use live DF/segments. Loader and service
; declarations do not certify complete actual entry/ownership domains.
; Dependencies: Saved segments and actual DF; complete reads; unchecked selectors/counts; IRQ and
; alias writers.
; [0378A] This is a1Ch ground-template-to-object copy at17CB, not a2Dh entity clone. Under intact counters/saves its32 destination starts advance1Ch and incoming DF moves each28-byte copy. Entity indices50 and above overlap neighboring owners; altered saves/segments are separate aliases.
; RECORD HANDOFF: main DS is also copied to ES.32 eight-byte definitions at0FEB
; select28-byte ground records by their big-endian word at+4. Low16-bit MUL/add
; chooses the live source; no type-index check. Destination17CB..1B4A is32 slots.
; A zero first definition word skips the copy, leaving stale destination bytes.
; Incoming DF controls REP MOVSB; SI/DI/CX restores read the original live stack.
; This working array adjoins the ground load at1B4B; it is not separate C state.
; Native core and bounded live saves/return aliases: c/object_graphics.c.
CopyLevelObjectGraphicsRecords:
; T2 UNCONDITIONAL live-overlay obligation: object slots17CB..1B4A overlap
; entity indices84..98. This copier runs at level setup (376A/397A); it is
; not normally interleaved with entity construction. The recurring3944->7C0A
; animation step IS between update01B3 and drawing01BC,writing object+00 word,
; +02 byte,+17 word (7C5C/7C4C/7C59). Exact entity+14 intersections:
; index85:17FE high;87:1857/1858;8A:18DE/18DF;8C:1938/1939 (two stores);
; 8F:19BF low;91:1A19 low. Animation has definition/flag/frame gates and a
; staleBX store at7C5C; no callback-membership test protects these aliases.
; Frame-offset arithmetic can produce non-nine words in this conditional
; writer domain. Actual survival/reachability of those spills is UNRESOLVED.
; 7BB8/394F subsequently consume the same definitions/graphics fields; writing
; a spilled entity can therefore alter renderer sizes/segments/control inputs.
; DATA-CONDITIONAL original GROUND files0420 bytes cover1B4B..1F6A; the1000
; raw-read request is larger and is not an allocation/ownership certificate.
; Neither short-file exclusion nor PROFILE closes these record/renderer aliases.
; V1 RECURRING MIXED GRAMMAR (G.7 CHARACTERIZED NONDETERMINISM under stated
; spill/entry premises):7C0A still walks32 recordsG_j=17CB+1C*j,definitions
; D_j=0FEB+8*j,using LIVE bytes after the entity update,not file templates.
; For BEword(D_j)==0,store incoming/staleBX atG_j+00 without loading flags.
; Otherwise typeLow==1 with0055!=FF skips ALL stores and retainsBX.
; Other nonzero definitions loadB=LEword(G_j);ifB&2,increment byteframe,
; wrap it to0 only on equality with byte limit,and clearB bit1 only when
; that equality AND B bit0 hold. StoreF at+02 before reading stride+06 and
; base+15,then storeO=wrap16(F*stride+base) at+17;finally storeB at+00.
; IfB&2==0,only+00 is stored. StaleBX flows across zero/skip records and
; initially comes from3944's caller; no invented zero seed. Exact stores
; intersect callbacks85(high),87(both),8A(both),8C(low flag-high/high frame),
;8F(low offset-high),91(low frame). V1 report gives every other field hit.
; State+08 is also overlapped in86(high flags),8B(flags),8E(offset),
;90(flag-high/frame),93(offset-high),95(frame);dispatch uses first-match bits.
; For an unchanged freshly constructed8A descriptor,G09 stride=F800|Y-high,
; base=003C;an enabled update therefore writesO09=F09*stride+003C,not the
; arbitrary base0/stride0 witness.85 similarly getsO01=F01*FFF8+7000
; and target70|(lo8(O01)<<8) when its constructor descriptor is retained.
; These formulas characterize mixed bytes without asserting that the needed
; definition/animation gates or high spill actually survive in a full session.
; Reciprocal corruption: entity stores also replace object widths/heights,
; masks/offsets and BE definitions. Frame01B9 draws objects BEFORE01BC entities;
; its unchecked8822 path may change saves/control first. Zero dimensions keep
; original decrement/wrap behavior; no resource bounds or frame survival added.
    push ds ; @0378A
    pop es ; @0378B
    lea bx,[LevelObjectDefinitions-GameDataImage] ; @0378C
    lea si,[GroundResourceBuffer-GameDataImage] ; @03790
    lea di,[LevelObjectGraphicsRecords-GameDataImage] ; @03794
    mov cx,0x20 ; @03798
loc_379B:
    mov ah,[bx] ; @0379B
    mov al,[bx+0x1] ; @0379D
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @037A0
    jz loc_37B9 ; @037A2
    mov ah,[bx+0x4] ; @037A4
    mov al,[bx+0x5] ; @037A7
    push si ; @037AA
    push cx ; @037AB
    push di ; @037AC
    mov cx,0x1c ; @037AD
    mul cx ; @037B0
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @037B2
; S19 DF-site census rep movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsb ; @037B4
    pop di ; @037B6
    pop cx ; @037B7
    pop si ; @037B8
loc_37B9:
    add bx,byte +0x8 ; @037B9
    add di,byte +0x1c ; @037BC
    loop loc_379B ; @037BF
    ret ; @037C1
; V4 CELL KIND is ORed without a nibble mask; high kind bits may change the
; ordinal.2F00..2F0C splits the cell byte; kind4 ->2FB6 selects a working record
; by its high nibble. Zero dimensions mean100h steps with intact row saves;
; explicit stores ignore DF. If cells alias pushed BX/DX, later rows use the
; actual POP values. Named LEVEL007 section1/object10 decimal +GROUND3o type5
; writes A5 atSS:4816..4825 and49B6..49C5. This data fact neither bounds the
; stack nor proves later read/survival of that upper row.
; U1 Level7 row headroom:depth302 ends49C6 without touching49B6..49C5;304 first writes49C4..49C5. For frame depth32, nine timer levels with eight26-byte tails and deepest62 end exactly49C6;ten cross. Initialization0498 depth34 plus nine gives304, with AdLib0559 PUSH DX writingDL/DH at49C4/49C5 if the active channel takes0349/038A. One retained keyboard scan frame16 plus frame32,eight timer tails26 and deepest62 gives318/SP49B6. This is conditional timing/stack arithmetic, not evidence those arrivals happen or that a later game reader observes the row; see U1 report.
; DATA-CONDITIONAL supplied-record footprint: level007.dat zero-based section1/object ordinal10,section0070 bytes021000AC0005000F (loaded DS103B),ground3o.dat type5 template008C has xoff0,yoff2,width16,height2,kind05. Original wrapped formula yields SS4816..4825 then49B6..49C5,valueA5. Thus interaction cells extend into dirty storage and above48F3 even without altered inputs. No interval-wide allocation/classification follows. UNCONDITIONAL row PUSH DX/BX atS-2/S-4 and POPs are live; writer/frame separation remains UNRESOLVED.
; UNCONDITIONAL lifetime implication:046B/376D/3770 precede game-vector install0492. Nominal DF0 second dirty-copy8219 clears4816..4825;00454/00460 neither DF clears49B6..49C5. The upper row can persist into later levels/stack traffic;actual read/survival and eligible-provider nesting remain UNRESOLVED.
; OBJECT INTERACTION CELLS: first16 eight-byte definitions, no type bounds check.
; BE type*28 selects ground metadata; zero BE X skips the rectangle. Base SS offset
; =12h+((X>>2)+LEtemplate[0E])+416*((Y>>2)+LEtemplate[10]-1), wrapped16.
; Cell value=(definition ordinal<<4)|template[14]. Byte dimensions[12]/[13]
; are decrement loops: zero means256 writes/rows. Row-save words remain live inSS.
; SS is also the stack and VGA-register cache; don't substitute a separate map.
; Native core/finite aliases: c/object_cells.c; docs/interaction-cells.md.
WriteObjectInteractionCells:
    lea di,[LevelObjectDefinitions-GameDataImage] ; @037C2
    mov cx,0x10 ; @037C6
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @037C9
loc_37CB:
    mov ah,[di+0x4] ; @037CB
    mov al,[di+0x5] ; @037CE
    mov dx,0x1c ; @037D1
    mul dx ; @037D4
    lea si,[GroundResourceBuffer-GameDataImage] ; @037D6
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @037DA
    mov ah,[di] ; @037DC
    mov al,[di+0x1] ; @037DE
    db 0x23,0xc0 ; ENCODED: and ax,ax (NASM chooses a different encoding) ; @037E1
    jz loc_382F ; @037E3
    shr ax,1 ; @037E5
    shr ax,1 ; @037E7
    add ax,[si+0xe] ; @037E9
    mov bh,[di+0x2] ; @037EC
    mov bl,[di+0x3] ; @037EF
    shr bx,1 ; @037F2
    shr bx,1 ; @037F4
    add bx,[si+0x10] ; @037F6
    dec bx ; @037F9
    push ax ; @037FA
    mov ax,0x1a0 ; @037FB
    mul bx ; @037FE
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @03800
    pop ax ; @03802
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @03803
    add bx,byte InteractionCellMapBase-RuntimeStackFrame ; @03805
    db 0x8b,0xc5 ; ENCODED: mov ax,bp (NASM chooses a different encoding) ; @03808
    shl ax,1 ; @0380A
    shl ax,1 ; @0380C
    shl ax,1 ; @0380E
    shl ax,1 ; @03810
    or al,[si+0x14] ; @03812
    mov dh,[si+0x12] ; @03815
    mov dl,[si+0x13] ; @03818
loc_381B:
    push dx ; @0381B
    push bx ; @0381C
loc_381D:
    mov [ss:bx],al ; @0381D
    inc bx ; @03820
    dec dh ; @03821
    jnz loc_381D ; @03823
    pop bx ; @03825
    pop dx ; @03826
    add bx,0x1a0 ; @03827
    dec dl ; @0382B
    jnz loc_381B ; @0382D
loc_382F:
    add di,byte +0x8 ; @0382F
    inc bp ; @03832
    dec cx ; @03833
    jz loc_3838 ; @03834
    jmp short loc_37CB ; @03836
loc_3838:
    ret ; @03838
; V4 STEEL +3 only participates in the all-zero test; nonzero+3 alone activates
; one cell atSS:0012. Characterized return alias: entrySP4AF2 contains3770,
; main DS and a stable distinct SS, first record10 2E 00 00, others zero.
; X20,row2E,one byte09 atSS:4AF2; RET389E consumes3709. Row frames lie below
; that cell. No bounds fix or repaired return is equivalent. Subsequent execution
; at3709 is not asserted here.
; UNCONDITIONAL raw-input alias witness: steel bytes10 2E 00 00 give x32,row46,width1,height1 and write09 atSS4AF2. This can replace a near caller word there. DATA-CONDITIONAL all80 supplied unmodified LEVEL steel spans stay within00A7..41CB under intact row saves; this is not an unchecked-input bound or a global stack theorem.
; STEEL INTERACTION CELLS:32 four-byte records atDS172B, skip only if both words0.
; X coordinate combines AH and AL bit7; row is AL&7F. DH high/low nibbles encode
; width/height minus1 (each1..16). Record byte3 participates only in the zero check.
; Writes byte9 at liveSS cells with416-byte row stride, using live stack row saves.
; Native core/packed dimensions/finite aliases: c/steel_cells.c.
WriteSteelInteractionCells:
    lea di,[LevelSteelDefinitions-GameDataImage] ; @03839
    mov cx,0x20 ; @0383D
loc_3840:
    mov ah,[di] ; @03840
    mov al,[di+0x1] ; @03842
    mov dh,[di+0x2] ; @03845
    mov dl,[di+0x3] ; @03848
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @0384B
    db 0x0b,0xda ; ENCODED: or bx,dx (NASM chooses a different encoding) ; @0384D
    jz loc_3899 ; @0384F
    db 0x8a,0xd6 ; ENCODED: mov dl,dh (NASM chooses a different encoding) ; @03851
    and dl,0xf ; @03853
    shr dh,1 ; @03856
    shr dh,1 ; @03858
    shr dh,1 ; @0385A
    shr dh,1 ; @0385C
    and dh,0xf ; @0385E
    push dx ; @03861
    db 0x8a,0xd8 ; ENCODED: mov bl,al (NASM chooses a different encoding) ; @03862
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @03864
    and bl,0x7f ; @03866
    db 0x8a,0xd0 ; ENCODED: mov dl,al (NASM chooses a different encoding) ; @03869
    db 0x8a,0xc4 ; ENCODED: mov al,ah (NASM chooses a different encoding) ; @0386B
    db 0x32,0xe4 ; ENCODED: xor ah,ah (NASM chooses a different encoding) ; @0386D
    rol dl,1 ; @0386F
    rcl ax,1 ; @03871
    push ax ; @03873
    mov ax,0x1a0 ; @03874
    mul bx ; @03877
    pop bx ; @03879
    db 0x03,0xd8 ; ENCODED: add bx,ax (NASM chooses a different encoding) ; @0387A
    add bx,byte InteractionCellMapBase-RuntimeStackFrame ; @0387C
    pop dx ; @0387F
    add dx,0x101 ; @03880
loc_3884:
    push dx ; @03884
    push bx ; @03885
loc_3886:
    mov byte [ss:bx],0x9 ; @03886
    inc bx ; @0388A
    dec dh ; @0388B
    jnz loc_3886 ; @0388D
    pop bx ; @0388F
    pop dx ; @03890
    add bx,0x1a0 ; @03891
    dec dl ; @03895
    jnz loc_3884 ; @03897
loc_3899:
    add di,byte +0x4 ; @03899
    loop loc_3840 ; @0389C
    ret ; @0389E
; [0389F] Coordinates at0E98..0F17 are a maximum32-pair write footprint, not a capacity guarantee. The first16 bytes also equal the start of hypothetical entity slot50;30F3 clears that slot before reading the four spawn pairs. Collector count>=4 is unclamped; do not call entity prefix80 an allocated limit.
; TYPE-ONE COORDINATES: scans32 big-endian definitions, compares full type word+4
; to1 (no first-word presence check). Writes wrapped X+24,Y+30 pairs atDS:0E98.
; Counts0..3 fill four slots with original patterns; counts>=4 are not clamped.
; Default BUG:393A storesY at+0A,393D overwrites it withX at+0A; +0C stays stale.
; Spawn consumer30DB..3100 indexes only four pairs, but that is not a producer bound.
; Native core/default-bug/full-count comparisons: c/object_coordinates.c.
; ENTITY CAPACITY CROSS-CONTRACT: nominal pinned120 level selections (80 base
; sections plus40 forward odd overrides) have maximum count50h=80 decimal;
; reset/serialized creation then fills exactly through0E97, before this base.
; This boundary follows header producers36CD/19F5 and constructor30A6, not
; this collector's32 definitions. Forty unselected odd rows instead hold0063.
; Raw limits, altered selectors or4013 racing30D5..314B can exceed the prefix.
; Index50 clear0E98..0EC4 destroys all four spawn pairs before30F9/30FD read
; them, including aliases with visibility at0EA8. No capacity clamp prevents it.
CollectTypeOneObjectCoordinates:
    lea si,[LevelObjectDefinitions-GameDataImage] ; @0389F
    lea bx,[TypeOneObjectCoordinates-GameDataImage] ; @038A3
    mov cx,0x20 ; @038A7
    db 0x33,0xed ; ENCODED: xor bp,bp (NASM chooses a different encoding) ; @038AA
loc_38AC:
    mov ah,[si+0x4] ; @038AC
    mov al,[si+0x5] ; @038AF
    cmp ax,0x1 ; @038B2
    jnz loc_38D1 ; @038B5
    mov ah,[si] ; @038B7
    mov al,[si+0x1] ; @038B9
    add ax,0x18 ; @038BC
    mov [bx],ax ; @038BF
    mov ah,[si+0x2] ; @038C1
    mov al,[si+0x3] ; @038C4
    add ax,0x1e ; @038C7
    mov [bx+0x2],ax ; @038CA
    add bx,byte +0x4 ; @038CD
    inc bp ; @038D0
loc_38D1:
    add si,byte +0x8 ; @038D1
    loop loc_38AC ; @038D4
    db 0x23,0xed ; ENCODED: and bp,bp (NASM chooses a different encoding) ; @038D6
    jz loc_3926 ; @038D8
    cmp bp,byte +0x1 ; @038DA
    jz loc_38EA ; @038DD
    cmp bp,byte +0x2 ; @038DF
    jz loc_3902 ; @038E2
    cmp bp,byte +0x3 ; @038E4
    jz loc_391A ; @038E7
    ret ; @038E9
loc_38EA:
    mov ax,[bx-0x4] ; @038EA
    mov cx,[bx-0x2] ; @038ED
    mov [bx],ax ; @038F0
    mov [bx+0x2],cx ; @038F2
    mov [bx+0x4],ax ; @038F5
    mov [bx+0x6],cx ; @038F8
    mov [bx+0x8],ax ; @038FB
    mov [bx+0xa],cx ; @038FE
    ret ; @03901
loc_3902:
    mov ax,[bx-0x4] ; @03902
    mov cx,[bx-0x2] ; @03905
    mov [bx],ax ; @03908
    mov [bx+0x2],cx ; @0390A
    mov ax,[bx-0x8] ; @0390D
    mov cx,[bx-0x6] ; @03910
    mov [bx+0x4],ax ; @03913
    mov [bx+0x6],cx ; @03916
    ret ; @03919
loc_391A:
    mov ax,[bx-0x8] ; @0391A
    mov cx,[bx-0x6] ; @0391D
    mov [bx],ax ; @03920
    mov [bx+0x2],cx ; @03922
    ret ; @03925
loc_3926:
    mov ax,0x100 ; @03926
    mov cx,0x10 ; @03929
    mov [bx],ax ; @0392C
    mov [bx+0x2],cx ; @0392E
    mov [bx+0x4],ax ; @03931
    mov [bx+0x6],cx ; @03934
    mov [bx+0x8],ax ; @03937
    mov [bx+0xa],cx ; @0393A
    ; Original repeated offset: do not repair to+0C.
    mov [bx+0xa],ax ; @0393D
    mov [bx+0xe],cx ; @03940
    ret ; @03943
%if ($-$$) != 0x3944
    %error "level_objects end moved"
%endif

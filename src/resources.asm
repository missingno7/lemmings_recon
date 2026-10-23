; Maintained image span 01916..01F18; reconstruction module, not a historical linker claim.
; CONTRACT: DS:DX filename, ES:AX destination, CX maximum byte count.
; Open/read/close preserve live save frames; short reads are accepted.
; SIZE CONTRACT: CX is a DOS request ceiling, not a reserved object extent.
; AH=3F's returned AX is never compared with CX and is replaced by the close
; result. A successful short read leaves the destination suffix unchanged;
; there is no zero-fill, checksum or retry for a short count. Ordinary DOS
; transfers advance through bytes independently of DF; arbitrary DOS segment,
; stack or write effects remain a platform seam, not a preservation proof.
; The two decoded callers request 1180h at DS:5566 and 1000h at DS:1B4B.
; Destination/save-frame aliases are live: POP ES/DS at1937/1938 can observe
; written bytes. Error tails do not unwind the partially consumed save frame.
; Failures transfer to the shared error printer with stage-specific message.
; Raw-only andfull fatal contracts: docs/resource-raw.md/resource-raw-full.md.
; Bus CPU words keep physical+1/A20 wrap; errors tail into1949 without unwind.
ReadRawResourceFile:
    push ds ; @01916
    push es ; @01917
    push ax ; @01918
    push es ; @01919
    push cx ; @0191A
    mov [LastResourceFilenameOffset-GameDataImage],dx ; @0191B
    mov ax,0x3d00 ; @0191F
    int 0x21 ; @01922
    jc loc_193A ; @01924
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01926
    mov ah,0x3f ; @01928
    pop cx ; @0192A
    pop ds ; @0192B
    pop dx ; @0192C
    int 0x21 ; @0192D
    jc loc_1940 ; @0192F
    mov ah,0x3e ; @01931
    int 0x21 ; @01933
    jc loc_1946 ; @01935
    pop es ; @01937
    pop ds ; @01938
RawResourceReturn:
    ret ; @01939
loc_193A:
    mov dx,DatFileErrorMessage-GameDataImage ; @0193A
    jmp short loc_1949 ; @0193D
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @0193F
loc_1940:
    mov dx,ResourceReadErrorMessage-GameDataImage ; @01940
    jmp short loc_1949 ; @01943
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @01945
loc_1946:
    mov dx,ResourceCloseErrorMessage-GameDataImage ; @01946
loc_1949:
; Error continuation: incomingDX is pushed before selecting relocated mainDS.
; Video returns through liveSSSP, then POPDX selects the DOS09 pointer.
; DOS02 may changeDSBX between filename bytes; no length clamp or cached copy.
; CR/LF flow into04EA byJMP, preserving all existing caller stack residue.
DatFileErrorTransfer:
    push dx ; @01949
FileErrorDataSegmentOperand equ $+1
    mov dx,0x9a9 ; @0194A
    mov ds,dx ; @0194D
    call RestoreVideoModeAndPage ; @0194F
FileErrorAfterVideo:
    pop dx ; @01952
    mov ah,0x9 ; @01953
FileErrorMessageInterrupt:
    int 0x21 ; @01955
    mov ah,0x2 ; @01957
    mov dl,0x20 ; @01959
FileErrorSpaceInterrupt:
    int 0x21 ; @0195B
    mov bx,[LastResourceFilenameOffset-GameDataImage] ; @0195D
loc_1961:
FileErrorFilenameLoop:
    mov dl,[bx] ; @01961
    db 0x22,0xd2 ; ENCODED: and dl,dl (NASM chooses a different encoding) ; @01963
    jz loc_196E ; @01965
    inc bx ; @01967
    mov ah,0x2 ; @01968
FileErrorCharacterInterrupt:
    int 0x21 ; @0196A
    jmp short loc_1961 ; @0196C
loc_196E:
    mov dl,0xd ; @0196E
    mov ah,0x2 ; @01970
FileErrorCrInterrupt:
    int 0x21 ; @01972
    mov dl,0xa ; @01974
    mov ah,0x2 ; @01976
FileErrorLfInterrupt:
    int 0x21 ; @01978
FileErrorCleanupTail:
    jmp ExitAfterKeyboardRestore ; @0197A
; CONTRACT: incoming DS is the live main-data frame; no bounds checks on selector.
; Order byte minus1 wraps; bit0 selects an odd-table override. Group=(value>>4),
; section=(value>>1)&7. The decimal leaf changes SI; selected DAT sections overwrite
; LoadedLevelRecord. Odd overrides copy24 header bytes and32 footer bytes.
; Ground/VGAGR selectors come from the resulting record; special value0 uses
; two VGAGR sections, nonzero loads VGASPEC first section. Close carry is ignored.
; Native decimal/raw/file/cache/decoder composition: c/resource_select.c.
; Bounded live ES/DS/stack, DF and fatal contracts: docs/resource-select.md.
; DOS and4B1C retry UI remain open.1949 error printing and04D0/04EA cleanup
; now connect through c/resource_select_full.c with original live fatal frames.
; The execution API consumes all8 immediatechildRETs and surfaces changedtargets;
; normal VGAGR/VGASPEC cores stop before their separate1A59/1A7A outerRETs.
; Selector-own bus observes XOR BH/CH before reads/saves,decimal ADD store flags,
; separate live DS:1FF0 reads and each immediate-child CALL/RET word.
; DAT/raw descendants retain their ordinary-RAM/intact-internal-return domains.
; READINESS: CONDITIONAL for resource-image replacement. Extents below describe
; canonical main DS, intact selectors/saves and complete pinned files; they do
; not bound unchecked indices, malformed DAT output or arbitrary DOS effects.
; LIFETIME: startup's DF-clear0000..2011 initializes LEVEL/working-object/GROUND
; storage once. The per-level clear4551 stops at0FC9 (0FCA untouched), so it
; initializes none of those resource images. Each selected LEVEL section reuses
; 0FCB..17CA; object working slots17CB..1B4A are later copied by378A (zero-X
; slots remain stale). GROUND1B4B..1F6A is replaced next; special setup1A7B can
; replace parts of its trailing metadata. There is no independent C copy.
; ORDER: initial54EE..5565 contains120 one-based selectors (four groups of30,
; see4515/4545, result473E). This is a stored/nominal domain, not a loader check:
; BL may be00..FF, so1987 reads54EE..55ED, including5566..55ED override storage.
; Decrement00->FF gives group15/section7/odd override127. The pinned120 bytes
; are01..A0, select LEVEL000..009 and contain40 odd overrides (indices6..79).
; 5205 publishes a decoded byte before validation; neither local producers nor
; the table's initial bytes prove a closed live index/writer domain.
; TYPED SELECTIONS 78..FF: an accepted code can store any selection, so index
; 78+k reads override-buffer byte 5566+k (k 0..87h). That buffer is stored zero
; until the first odd override load, and afterwards holds oddtable.dat (the 19DC
; full read is the only identified writer). Zero gives FF: level015.dat is not
; supplied, so the 1CD9 attribute check repeats the 4B1C insert-disk screen on
; every key until such a file appears. After a load, bytes 0..87h are rows 0..2 of the
; unused-duplicate entries: header words 0063 (even k -> 00 -> retry; odd k ->
; 63 -> level006 section1 direct) and the title text, whose characters select
; real level001/002/005/006/007 sections; 'n' (6E) selects odd row 54, whose
; header gives population, required, rate, time and skills 99.
LoadSelectedLevelResources:
    mov bl,[LevelResourceSelectionByte-GameDataImage] ; @0197D
    db 0x32,0xff ; ENCODED: xor bh,bh (NASM chooses a different encoding) ; @01981
    lea si,[LevelResourceOrderBytes-GameDataImage] ; @01983
    mov cl,[bx+si] ; @01987
    dec cl ; @01989
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @0198B
    push cx ; @0198D
    shr cx,1 ; @0198E
    db 0x8b,0xc1 ; ENCODED: mov ax,cx (NASM chooses a different encoding) ; @01990
    shr ax,1 ; @01992
    shr ax,1 ; @01994
    shr ax,1 ; @01996
    and cx,byte +0x7 ; @01998
    lea si,[LevelResourceFilenameDigits-GameDataImage] ; @0199B
    push cx ; @0199F
    call WriteDecimalByteDigits ; @019A0
SelectionAfterDecimal:
    pop cx ; @019A3
    lea dx,[LevelResourceFilename-GameDataImage] ; @019A4
    push ds ; @019A8
    pop es ; @019A9
; LEVEL I/O: header request000A at0FCB, then packed-lowword-000A at the same
; source start; the latter is06C4 at most across the80 pinned sections, reaching
;168E. Full decoded output is0800 bytes,0FCB..17CA, for every supplied section.
; Header0FCB..0FEA, objects0FEB..10EA, terrain10EB..172A, steel172B..17AA,
; footer17AB..17CA are replaced, including skipped sections, not appended.
; No literal0800 limit exists in the decoder. Successful pinned decode leaves
; SI at its input start;19BA resets only DI for the next section, not SI/DS/ES.
    lea di,[LoadedLevelRecord-GameDataImage] ; @019AA
    push cx ; @019AE
    mov cx,es ; @019AF
    db 0x8b,0xf7 ; ENCODED: mov si,di (NASM chooses a different encoding) ; @019B1
    call LoadDatResource ; @019B3
SelectionAfterFirstLevelSection:
    pop cx ; @019B6
    jcxz loc_19C4 ; @019B7
loc_19B9:
    push cx ; @019B9
    lea di,[LoadedLevelRecord-GameDataImage] ; @019BA
    call DecodeDatPreservingSegment ; @019BE
SelectionAfterNextLevelSection:
    pop cx ; @019C1
    loop loc_19B9 ; @019C2
loc_19C4:
    mov ah,0x3e ; @019C4
    int 0x21 ; @019C6
    pop ax ; @019C8
    test ax,0x1 ; @019C9
    jz loc_1A00 ; @019CC
    push ax ; @019CE
    push ds ; @019CF
    pop es ; @019D0
    lea dx,[OddLevelOverrideFilename-GameDataImage] ; @019D1
; RAW OVERRIDE: request=supplied file size1180h ->5566..66E5 (80*38h bytes).
; A short read leaves old bytes, including old level data, in the missing suffix.
; The next named renderer word is66F0;66E6..66EF is outside this write, with no
; ownership inference. Forward slice n=(popped AL>>1) starts5566+38h*n;
; n=79 ends66E5, n=80 first exceeds the load, n=127 reads712E..7165.
; Incoming AH is discarded by MUL DH. SI ADD and string cursors wrap at16 bits.
    lea ax,[OddLevelOverrideBuffer-GameDataImage] ; @019D5
    mov cx,0x1180 ; @019D9
    call ReadRawResourceFile ; @019DC
; V4 OVERRIDE HANDOFF: POP AX rereads the saved decremented order; SHR AL,1;
; MUL DH(38) ignores original AH and permits0..127 slices. DF0 copies18h header
; bytes and20h footer bytes; camera/graphics0FE3..0FEA stay from LEVEL.
; DF1 copies words at0FCB,0FC9,..0FB5 then17AB,17A9,..178D.
; Each word's high byte is physical+1; source likewise runs backward. No CLD.
; A short oddtable read keeps the old suffix. An invalid slice reads following
; live storage; no blank/default/header-validation branch exists.
SelectionAfterOddOverrideRead:
    pop ax ; @019DF
    shr al,1 ; @019E0
    mov dh,0x38 ; @019E2
    mul dh ; @019E4
    lea di,[LoadedLevelRecord-GameDataImage] ; @019E6
    lea si,[OddLevelOverrideBuffer-GameDataImage] ; @019EA
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @019EE
    mov cx,0xc ; @019F0
    push ds ; @019F3
    pop es ; @019F4
; R1 PLATFORM-CONDITIONAL: on the normal197D resource call chain these two copies use DF0,
; independently of197D entry DF.1B79/1BA9 return via1C78 CLD;19C6 close and19DC raw read
; preserve it under21:AH=003D/003F/003E of dos-vga-adlib. Normal intact continuations required.
; 19F5 copies12 forward words to0FCB,19FE16 to17AB; source advances38 bytes altogether.
; Index/short-read/segment/alias/reentry obligations remain; CONSERVATIVE actual DF is unresolved.
; Coarse flowstate TOP from return-word widening is not evidence against this local reset proof.
; S19 level-clear-and-copies: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED.
; Level clear,odd-header and28-byte object copies use live DF/segments. Loader and service
; declarations do not certify complete actual entry/ownership domains.
; Dependencies: Saved segments and actual DF; complete reads; unchecked selectors/counts; IRQ and
; alias writers.
; POPULATION HEADER: all80 pinned LEVEL section headers have high00/count<=0050. The nominal120 stored order bytes select40 forward odd rows, also high00/count<=0050; other40 supplied odd rows contain twelve0063 words in the18h-byte header. Forward complete copy is needed for this bound. Do not replace unchecked selectors/short reads/backward copies with a universal50h limit;4013 can race constructor publication even with nominal headers.
; With DF=0, copies24 bytes to0FCB..0FE2 and32 to17AB..17CA. Bytes0FE3..0FEA
; (including graphics selectors0FE6/0FE8) stay from LEVEL. With DF=1 the word
; footprints are0FB5..0FCC and178D..17AC; source is[slice-36h,slice+1], not
; the forward56-byte record. Word high bytes are physical+1. DOS close/read
; can supply DF; no CLD here. Live overlap/saves may change following reads.
    rep movsw ; @019F5
    lea di,[LoadedLevelFooterBytes-GameDataImage] ; @019F7
    mov cx,0x10 ; @019FB
; S19 DF-site census rep movsw word ptr es:[di], word ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsw ; @019FE
; V4 GROUND:1A18 requests1000 ->DS:1B4B..2B4A; returned AX count is untested.
; Named ground0o..ground4o.dat each have0420 bytes:16*1C templates,64*8 terrain,
; 60 palette bytes. For a preserving forward DOS read of N bytes, only prefix N
; is replaced; the suffix retains pre-call bytes. Larger files cross config,
; cache, vector, selector, input and palette owners. N04A7 replaces1FF0;
; N04AB replaces1FF4.1A35/1A49/1A4D/1A67 immediately use the new values.
; Graphics byte0FE6 is reread after GROUND; ground/VGAGR names need not agree.
; These are characterized state effects, not an invented invalid-file failure.
loc_1A00:
    mov al,[LevelGraphicsSetByte-GameDataImage] ; @01A00
    lea si,[GroundFilenameSelector-GameDataImage] ; @01A03
    add al,0x30 ; @01A07
    mov [si],al ; @01A09
    lea dx,[GroundResourceFilename-GameDataImage] ; @01A0B
    push ds ; @01A0F
    pop es ; @01A10
; GROUND request1000h ->1B4B..2B4A, image0B5DB..0C5DA. All five supplied
; files are0420h ->1B4B..1F6A only:16*1Ch object templates1B4B..1D0A,
; 64*8 terrain records1D0B..1F0A, trailing metadata1F0B..1F6A. Consumers378A/
;37C2 use unchecked BE object-type*1Ch;7C67 masks terrain index to six bits.
; Palette slots3/5 at CS52D4/52E4 consume the trailing packed/RGB rows.
; A full1000h read also replaces selection/cache/IRQ/video/allocation fields
;1F6B..2010, both bytes of2011, display-probe records2013..201E, all U112
;201F..259F (keyboard/status/text/filenames/saved clocks), callback25A0..25A1,
; and U11325A2..2B4A (input/options, palette rows25A8/2608/2638/2650/2668,
; pair base2698, point colors2778 and prefix2788..2B4A of the point stream).
; These are possible cross-owner writes, not ordinary pinned-file overwrites
; or evidence classifying a whole UNKNOWN run. At leastC2Eh/C3Eh supplied
; bytes would reach2778/2788; the actual0420h files cannot. Short reads can
; leave even intended GROUND metadata stale. No requested count is clamped.
    lea ax,[GroundResourceBuffer-GameDataImage] ; @01A11
    mov cx,0x1000 ; @01A15
; R3 separate DATA assumption:ground0o.dat,ground1o.dat,ground2o.dat,ground3o.dat,
; ground4o.dat are each0420 bytes,so ordinary returned data ends1F6A. Original
; request1000 still permits2013..201E and25A0/25A1 overlap for longer inputs.
; Short reads retain suffixes. This exclusion needs intact destination saves and
; DOS bounded-buffer effects;platform-profile preservation alone is not a file
; length/content or allocation/alias proof. See r3-writers.md named input hashes.
; Cross-lifetime control storage: GROUND request1000 at DS1B4B reaches2B4A. Returned file offsets04C6/04C7 overwrite word2011,04C8..04D3 overwrite probe records2013..201E,0A55/0A56 overwrite input callback25A0/25A1. Supplied420-byte files end1F6A and do not touch these fields. Short reads preserve suffix; longer/changed provider reads invalidate the intact-table/callback target domains; preserve request1000 and live returned segment/save effects.
    call ReadRawResourceFile ; @01A18
SelectionAfterGroundRead:
    mov al,[LevelGraphicsSetByte-GameDataImage] ; @01A1B
    lea si,[GraphicsFilenameSelector-GameDataImage] ; @01A1E
    add al,0x30 ; @01A22
    mov [si],al ; @01A24
    mov al,[LevelSpecialGraphicsSetByte-GameDataImage] ; @01A26
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @01A29
    jz loc_1A30 ; @01A2B
    jmp short loc_1A5A ; @01A2D
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @01A2F
loc_1A30:
    push ds ; @01A30
    lea dx,[GraphicsDatFilename-GameDataImage] ; @01A31
    mov es,[GraphicsResourceInputSegment-GameDataImage] ; @01A35
    mov di,0x10 ; @01A39
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01A3C
    mov cx,es ; @01A3E
    call LoadDatResource ; @01A40
SelectionAfterGraphicsLoad:
    pop ds ; @01A43
    push ds ; @01A44
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @01A45
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01A47
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01A49
    mov ds,[LevelGraphicsSegment-GameDataImage] ; @01A4D
    call DecodeDatPreservingSegment ; @01A51
SelectionAfterGraphicsDecode:
    pop ds ; @01A54
    mov ah,0x3e ; @01A55
    int 0x21 ; @01A57
SelectionNormalReturn:
    ret ; @01A59
loc_1A5A:
    lea si,[SpecialFilenameSelector-GameDataImage] ; @01A5A
    add al,0x2f ; @01A5E
    mov [si],al ; @01A60
    push ds ; @01A62
    lea dx,[SpecialResourceFilename-GameDataImage] ; @01A63
    mov es,[GraphicsResourceInputSegment-GameDataImage] ; @01A67
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01A6B
    mov di,0x10 ; @01A6D
    mov cx,es ; @01A70
    call LoadDatResource ; @01A72
SelectionAfterSpecialLoad:
    pop ds ; @01A75
    mov ah,0x3e ; @01A76
    int 0x21 ; @01A78
SelectionSpecialReturn:
    ret ; @01A7A
; V4 PALETTE PREFIX under DF0: decoded VGASPEC+00..17 ->1F23..1F3A
; (first three forced1F,1F,00) and1F53..1F6A (unmodified duplicate);
; +18..1F ->1F1B..1F22; +20..27 ->1F0B..1F12 (first forced06).
; CS slot3 rows1F13(full10 packed)/1F3B(full30 RGB) retain their first halves;
; slot5 rows1F0B(8)/1F23(18) seed the UI/game palette. All sizes are hex.
; RLE starts at input:0038. Four strips reuse level:8000..CAFF; then VGAGR
; replaces the heap. DF, saves, source and output are live, without staging.
; CONTRACT: loaded VGASPEC input atsegment[1FF4]:0010; main DS owns metadata.
; Prefix40 bytes ->four live metadata destinations; four RLE/strip pairs consume
; input from0038 and reuse heap[1FF0]:8000. Re-read pointers after saved-DS pushes.
; VGAGR reload follows drawing; final close exposes AX/flags without checking CF.
; Native bounded contract: docs/special-setup.md; VGA/IRQ/platform seams remain.
; RESOURCE OWNERSHIP (forward DF): VGASPEC at input[1FF4]:0010 supplies40-byte
; prefix0010..0037. Copy/write windows in main DS are1F23..1F3A (first3 become
;1F,1F,00),1F53..1F6A,1F1B..1F22 and1F0B..1F12 (first becomes06). They
; overlap the GROUND tail, not new persistent arrays. Bases1F13/1F3B themselves
; are not the second/third copy destinations: the instructions add08/18.
; Input from0038 holds four terminated RLE streams; each pinned stream writes
;3840h bytes at heap[1FF0]:8000..B83F, reused for the next strip. Strip code
; constructs its mask at B840..CAFF, then draws before the next reuse.
; After strip3 the same heap is reused for VGAGR section0 at0010, then section1
; at0000; input[1FF4] survives only until next resource load. All segment slots
; and DS saves stay live. DF=1 reverses strings; missing RLE terminator has no
; output bound, and neither DAT nor RLE asserts these asset-derived extents.
SetupSpecialGraphicsResource:
    push ds ; @01A7B
    mov cx,0x18 ; @01A7C
    lea di,[SpecialMetadata24-GameDataImage] ; @01A7F
    mov si,0x10 ; @01A83
    push ds ; @01A86
    pop es ; @01A87
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01A88
    push di ; @01A8C
; S19 DF-site census rep movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsb ; @01A8D
    pop di ; @01A8F
    mov al,0x1f ; @01A90
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @01A92
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @01A93
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @01A94
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @01A96
    mov cx,0x18 ; @01A97
    lea di,[SpecialMetadataDuplicateBase-GameDataImage] ; @01A9A
    add di,byte +0x18 ; @01A9E
    mov si,0x10 ; @01AA1
; S19 DF-site census rep movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsb ; @01AA4
    mov cx,0x8 ; @01AA6
    lea di,[SpecialMetadata8Base-GameDataImage] ; @01AA9
    add di,byte +0x8 ; @01AAD
; S19 DF-site census rep movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsb ; @01AB0
    mov cx,0x8 ; @01AB2
    lea di,[SpecialMetadataRemap8-GameDataImage] ; @01AB5
    push di ; @01AB9
; S19 DF-site census rep movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsb ; @01ABA
    pop di ; @01ABC
    mov al,0x6 ; @01ABD
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @01ABF
    pop ds ; @01AC0
    push ds ; @01AC1
    mov di,0x8000 ; @01AC2
    mov si,0x38 ; @01AC5
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01AC8
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01ACC
    call DecodeResourceRle ; @01AD0
SpecialAfterRle0:
    pop ds ; @01AD3
    push si ; @01AD4
    call BlitSpecialResourceStrip0 ; @01AD5
SpecialAfterStrip0:
    pop si ; @01AD8
    push ds ; @01AD9
    mov di,0x8000 ; @01ADA
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01ADD
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01AE1
    call DecodeResourceRle ; @01AE5
SpecialAfterRle1:
    pop ds ; @01AE8
    push si ; @01AE9
    call BlitSpecialResourceStrip1 ; @01AEA
SpecialAfterStrip1:
    pop si ; @01AED
    push ds ; @01AEE
    mov di,0x8000 ; @01AEF
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01AF2
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01AF6
    call DecodeResourceRle ; @01AFA
SpecialAfterRle2:
    pop ds ; @01AFD
    push si ; @01AFE
    call BlitSpecialResourceStrip2 ; @01AFF
SpecialAfterStrip2:
    pop si ; @01B02
    push ds ; @01B03
    mov di,0x8000 ; @01B04
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01B07
    mov ds,[GraphicsResourceInputSegment-GameDataImage] ; @01B0B
    call DecodeResourceRle ; @01B0F
SpecialAfterRle3:
    pop ds ; @01B12
    push si ; @01B13
    call BlitSpecialResourceStrip3 ; @01B14
SpecialAfterStrip3:
    pop si ; @01B17
    push ds ; @01B18
    lea dx,[GraphicsDatFilename-GameDataImage] ; @01B19
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01B1D
    mov di,0x10 ; @01B21
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01B24
    mov cx,es ; @01B26
    call LoadDatResource ; @01B28
SpecialAfterDatLoad:
    pop ds ; @01B2B
    push ds ; @01B2C
    db 0x33,0xff ; ENCODED: xor di,di (NASM chooses a different encoding) ; @01B2D
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01B2F
    mov es,[LevelGraphicsSegment-GameDataImage] ; @01B31
    mov ds,[LevelGraphicsSegment-GameDataImage] ; @01B35
    call DecodeDatPreservingSegment ; @01B39
SpecialAfterDatDecode:
    pop ds ; @01B3C
    mov ah,0x3e ; @01B3D
    int 0x21 ; @01B3F
    ret ; @01B41
; V4 MALFORMED RLE:80 terminates;00..7F copies n+1 bytes;81..FF repeats
; 257-n times. There is no output/source-end guard. LODSB/MOVSB/STOSB follow
; live DF; SI wrap does not adjust DS. DI==0 after a write advances ES by1000,
; even under DF1. Repeat rollover MOV AX,ES changes AL for remaining repeats.
; Missing80 reads stale input and writes further segments. Unknown code/frame/
; provider aftermath stays unresolved; no fabricated failure or image bound.
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
DecodeResourceRle:
    lodsb ; @01B42
    cmp al,0x80 ; @01B43
    jz loc_1B78 ; @01B45
    jc loc_1B62 ; @01B47
    neg al ; @01B49
    inc al ; @01B4B
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @01B4D
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @01B4F
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    lodsb ; @01B51
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_1B52:
    stosb ; @01B52
    db 0x23,0xff ; ENCODED: and di,di (NASM chooses a different encoding) ; @01B53
    jnz loc_1B5E ; @01B55
    mov ax,es ; @01B57
    add ax,0x1000 ; @01B59
    mov es,ax ; @01B5C
loc_1B5E:
    loop loc_1B52 ; @01B5E
    jmp short DecodeResourceRle ; @01B60
loc_1B62:
    inc al ; @01B62
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @01B64
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @01B66
; S19 DF-site census movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_1B68:
    movsb ; @01B68
    db 0x23,0xff ; ENCODED: and di,di (NASM chooses a different encoding) ; @01B69
    jnz loc_1B74 ; @01B6B
    mov ax,es ; @01B6D
    add ax,0x1000 ; @01B6F
    mov es,ax ; @01B72
loc_1B74:
    loop loc_1B68 ; @01B74
    jmp short DecodeResourceRle ; @01B76
loc_1B78:
    ret ; @01B78
; CONTRACT: DS:DX filename, CX decoder source segment, ES:DI output, SI source offset.
; Connect check/open/decode; ignored open carry and both fatal frames are original.
; Shared tail DecodeDatPreservingSegment keeps DS through a live stack restore.
; Native/provider domain: docs/dat-load.md.
LoadDatResource:
    push cx ; @01B79
    call CheckDatFile ; @01B7A
DatAfterResourceCheck:
    pop cx ; @01B7D
    jc loc_1B98 ; @01B7E
    cmp byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @01B80
    jnz loc_1B98 ; @01B85
    call OpenDatFile ; @01B87
DatAfterResourceOpen:
    cmp byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @01B8A
    jnz loc_1B98 ; @01B8F
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01B91
    mov ds,cx ; @01B93
    jmp short DecodeDatPreservingSegment ; @01B95
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @01B97
loc_1B98:
    push dx ; @01B98
    push cx ; @01B99
    push es ; @01B9A
    push ds ; @01B9B
    push di ; @01B9C
    push si ; @01B9D
    call ShowResourceRetryScreen ; @01B9E
DatAfterResourceRetry:
    pop si ; @01BA1
    pop di ; @01BA2
    pop ds ; @01BA3
    pop es ; @01BA4
    pop cx ; @01BA5
    pop dx ; @01BA6
    jmp short LoadDatResource ; @01BA7
DecodeDatPreservingSegment:
    push ds ; @01BA9
    call DecodeDatSection ; @01BAA
; Return point of CALL 1BAA (legacy lifter split, not an entry): POP DS rereads
; the caller DS saved at 1BA9 from the live stack, then RET. POP/RET keep the
; decoder's exit flags (CF=0, ZF=checksum zero, DF=0). c/dat_load.c pushes this
; address as the decoder's return word; covered with DecodeDatPreservingSegment.
DecodeDatPreservingSegmentReturn:
    pop ds ; @01BAD
    ret ; @01BAE
; V4 DAT HEADER: byte0+1 wraps CH; byte1 supplies XOR checksum; BE+2/+3 is
; read then POPped over; BE+4/+5 alone determines the wrapped output end.
; +6/+7 is not read by this decoder; BE+8/+9 minus A determines payload count
; (9 ->FFFF). Both reads ignore actual AX count. A short header overlays prior
; buffer bytes; a short payload overlays the current header/suffix. Later bits
; and lengths use that mix. Output size0 still executes a token before DI<=BP.
; LEVEL start0FCB,size0,literal1 writes0FCA; literal264 writes0EC3..0FCA.
; Checksum AND only returns flags. Errors jump04D0 without unwind; normal CLD.
; Static extractor validation and host allocation bounds are not original checks.
; CONTRACT: BX handle, DS:SI source buffer, ES:DI output; incoming ES may change
; inside ReadDatBytes. Sizes use low16-bit header words, with original wrap.
; Header bit count0 is valid:seed DL joins checksum, first read refills backwards.
; Short reads/malformed lengths are unchecked; normal exit clears DF, error exits
; preserve the live frame at04D0. Native bounded contract: docs/dat-section.md.
; WRITE BOUNDS: BP=initial DI, end=(DI+BEword[SI+4]) modulo65536; the apparent
; high output word[SI+2] is discarded. Read000A header bytes atDS:SI, then
; CX=(BEword[SI+8]-000A) modulo65536 payload bytes at that same start (header
; overwritten). Maximum requestFFFF is possible; returned AX counts are unused.
; Header+6/+7 do not bound the payload. Cache copies obey provider-returned DF,
; wrap16-bit offsets without segment advance, and set ES to the caller DS;
; direct DOS reads keep provider ES. Thus input/output separation is not assured.
; Tokens decrement DI and write live ES even with zero declared output. The
; unsigned DI<=BP check is after a complete token (up to264 literal bytes);
; there is no strict output allocation/length guard or checksum error transfer.
; A malformed/short input may read stale bytes, cross below BP or wrap DI. No
; universal small destination span follows from a header or one named consumer.
; Normal CLD1C78 establishes forward DF only after successful local completion;
; saved BX/DS/return words remain ordinary writable memory, not cached values.
DecodeDatSection:
    push bx ; @01BAF
; R1 UNCONDITIONAL (fixed original serial stream): the only decoded STD across main/protected/three drivers.
; Its CALL1BB9 reaches six saves1D2E..1D33 then CLD1D34 before any string/service/branch.
; Normal decoder RET1C79 is immediately preceded by CLD1C78. Reverse tokens use explicit DEC.
; Failure1BBE/1BED ->1C7A ->04D0 requests DOS termination, not a DF1 returning decoder path.
; An IRQ can inherit DF1 in the transient window; neither a profile nor this barrier excludes it.
; S19 decoder-reset-barriers: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; STD1BB0 is transient:1BB9 calls1D2E,CLD1D34 before DOS/cache selection;normal decoder return
; CLD1C78. This is not a demonstrated returning foreground DF1 origin.
; Dependencies: Instruction-order fact; IRQ in transient STD window remains separate.
; S17 flow-state: In the fixed decoded stream, STD reaches CALL1BB9 with DF=1. Its
; child1D2E executes CLD1D34 before DOS/cache selection, and the ordinary decoder exit
; CLD1C78 precedes RET1C79. Thus this STD alone is not a demonstrated returning
; foreground DF1 producer. Undeclared services, modified returns, protected views and
; asynchronous entry still prevent a global DF0 theorem. No timer-installation lifetime
; is inferred by the flow-state tool.
; S13 AdLib DF residual: STD remains set until the first ReadDatBytes1D34 CLD reached via1BB9;reverse decoder later uses explicit DECs. INT retainsDF;game17C7 ->1872 never clears interruptedDF. A valid song start withDF1 reverses headerLODS (H,H-2,H-4,H-5,H-6-2k),escaping pinned grammar. No whole-program IRQ/provider proof here establishes such a schedule or excludes it.
    std ; @01BB0
    push bx ; @01BB1
    db 0x8b,0xef ; ENCODED: mov bp,di (NASM chooses a different encoding) ; @01BB2
    mov cx,0xa ; @01BB4
    db 0x8b,0xd6 ; ENCODED: mov dx,si (NASM chooses a different encoding) ; @01BB7
    call ReadDatBytes ; @01BB9
DatAfterHeaderRead:
    jnc loc_1BC1 ; @01BBC
    jmp loc_1C7A ; @01BBE
loc_1BC1:
    mov ch,[si] ; @01BC1
    inc ch ; @01BC3
    mov dh,[si+0x1] ; @01BC5
    mov ah,[si+0x2] ; @01BC8
    mov al,[si+0x3] ; @01BCB
    mov bh,[si+0x4] ; @01BCE
    mov bl,[si+0x5] ; @01BD1
    db 0x03,0xfb ; ENCODED: add di,bx (NASM chooses a different encoding) ; @01BD4
    pop ax ; @01BD6
    push cx ; @01BD7
    push dx ; @01BD8
    mov ch,[si+0x8] ; @01BD9
    mov cl,[si+0x9] ; @01BDC
    sub cx,byte +0xa ; @01BDF
    db 0x8b,0xd6 ; ENCODED: mov dx,si (NASM chooses a different encoding) ; @01BE2
    db 0x03,0xf1 ; ENCODED: add si,cx (NASM chooses a different encoding) ; @01BE4
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01BE6
    call ReadDatBytes ; @01BE8
DatAfterPayloadRead:
    jnc loc_1BF0 ; @01BEB
    jmp loc_1C7A ; @01BED
loc_1BF0:
    pop dx ; @01BF0
    pop cx ; @01BF1
    dec si ; @01BF2
    mov dl,[si] ; @01BF3
    db 0x32,0xf2 ; ENCODED: xor dh,dl (NASM chooses a different encoding) ; @01BF5
; TOKEN LOOP HEAD of DecodeDatSection. This and the labels down to 1C75 are
; interior blocks of one routine (legacy lifter splits), not entries: their
; only predecessors are local branches, fall-throughs and the 1C56 call return.
; Loop state: SI = byte cursor moving down through the payload, DL = current
; byte, CH = bits left in DL (header byte0+1 initially, wraps from FF to 0),
; DH = running XOR checksum (header byte1 ^ every payload byte loaded),
; DI = output cursor (pre-decremented per byte), BP = output start, ES = output.
; ReadReverseBits takes bits from the low end of DL and bytes backwards; the
; first bit read is the most significant bit of each field. Token grammar:
;   0 0 nnn          literal run, n+1 bytes (1..8)               -> 1C5C
;   0 1 d8           2-byte match, 8-bit distance                -> 1C51
;   1 00 d9          3-byte match, 9-bit distance                -> 1C0B
;   1 01 d10         4-byte match, 10-bit distance               -> 1C0B
;   1 10 l8 d12      (l+1)-byte match (1..256), 12-bit distance  -> 1C38
;   1 11 n8          literal run, n+9 bytes (9..264)             -> 1C20
; Literal bytes are 8-bit fields stored by WriteReverseLiteral (DEC DI, store).
; Match bytes copy from ES:DI+d+1 after each DEC DI, so runs may overlap.
; Every token tail joins the end test 1C6F. C: c/dat_section.c.
DatTokenLoop:
    mov cl,0x1 ; @01BF7
    call ReadReverseBits ; @01BF9
DatAfterTokenBit:
    cmp ax,0x1 ; @01BFC
    jnz DatTokenPrefixZero ; @01BFF
; First token bit 1: read the 2-bit kind; kinds 0/1 fall through to 1C0B.
DatTokenPrefixOne:
    mov cl,0x2 ; @01C01
    call ReadReverseBits ; @01C03
DatAfterKindBits:
    cmp ax,0x2 ; @01C06
    jnc DatKindTwoOrThree ; @01C09
; Kind 0/1 match: BX=kind+2 (copy count kind+3), CL=kind+9 distance bits.
DatShortMatch:
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01C0B
    add bx,byte +0x2 ; @01C0D
    db 0x8a,0xc8 ; ENCODED: mov cl,al (NASM chooses a different encoding) ; @01C10
    add cl,0x9 ; @01C12
    call ReadAndCopyReverseMatch ; @01C15
DatAfterShortMatch:
    jmp short DatTokenEndCheck ; @01C18
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @01C1A
; Kind 2/3 select: 3 falls through to the long literal, 2 goes to 1C38.
DatKindTwoOrThree:
    cmp ax,0x3 ; @01C1B
    jnz DatVariableMatch ; @01C1E
; Long literal: 8-bit count n, then n+9 literal bytes. The remaining count is
; kept on the stack around each ReadReverseBits (which returns in AX).
DatLongLiteral:
    mov cl,0x8 ; @01C20
    call ReadReverseBits ; @01C22
DatAfterLongLiteralLength:
    add ax,0x9 ; @01C25
loc_1C28:
    push ax ; @01C28
    mov cl,0x8 ; @01C29
    call ReadReverseBits ; @01C2B
DatAfterLongLiteralByte:
    call WriteReverseLiteral ; @01C2E
DatAfterLongLiteralWrite:
    pop ax ; @01C31
    dec ax ; @01C32
    jnz loc_1C28 ; @01C33
; Long-literal tail: jump to the end test.
DatLongLiteralDone:
    jmp short DatTokenEndCheck ; @01C35
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @01C37
; Kind 2 variable match: 8-bit length l into BX, then a 12-bit distance;
; copies l+1 bytes (l=0 copies one byte).
DatVariableMatch:
    mov cl,0x8 ; @01C38
    call ReadReverseBits ; @01C3A
DatAfterMatchLength:
    db 0x8b,0xd8 ; ENCODED: mov bx,ax (NASM chooses a different encoding) ; @01C3D
    mov cl,0xc ; @01C3F
    call ReadAndCopyReverseMatch ; @01C41
DatAfterVariableMatch:
    jmp short DatTokenEndCheck ; @01C44
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @01C46
; First token bit 0: read a second bit; 1 = 2-byte match, 0 = short literal.
DatTokenPrefixZero:
    mov cl,0x1 ; @01C47
    call ReadReverseBits ; @01C49
DatAfterSecondTokenBit:
    cmp ax,0x1 ; @01C4C
    jnz DatShortLiteral ; @01C4F
; 2-byte match: BX=1 (copy count 2), 8-bit distance.
DatTwoByteMatch:
    mov bx,0x1 ; @01C51
    mov cl,0x8 ; @01C54
    call ReadAndCopyReverseMatch ; @01C56
; Return address of the 2-byte match call (c/dat_section.c pushes it); jumps to
; the end test.
DatAfterTwoByteMatch:
    jmp short DatTokenEndCheck ; @01C59
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @01C5B
; Short literal: 3-bit count n, then n+1 literal bytes (count kept on stack).
DatShortLiteral:
    mov cl,0x3 ; @01C5C
    call ReadReverseBits ; @01C5E
DatAfterShortLiteralLength:
    inc ax ; @01C61
loc_1C62:
    push ax ; @01C62
    mov cl,0x8 ; @01C63
    call ReadReverseBits ; @01C65
DatAfterShortLiteralByte:
    call WriteReverseLiteral ; @01C68
DatAfterShortLiteralWrite:
    pop ax ; @01C6B
    dec ax ; @01C6C
    jnz loc_1C62 ; @01C6D
; END TEST, shared by all five token tails: continue while DI > BP (unsigned).
; Checked only after a complete token, so the last token may write below BP;
; a wrapped DI or output end is not detected.
DatTokenEndCheck:
    db 0x3b,0xfd ; ENCODED: cmp di,bp (NASM chooses a different encoding) ; @01C6F
    jna DatDecodeFinish ; @01C71
; Back edge to the token loop head.
DatNextToken:
    jmp short DatTokenLoop ; @01C73
; NORMAL EXIT: AND DH,DH gives ZF=1 iff the XOR checksum is zero (and CF=0);
; no caller tests it. POP BX restores the BX saved at 1BAF, CLD, RET.
DatDecodeFinish:
    db 0x22,0xf6 ; ENCODED: and dh,dh (NASM chooses a different encoding) ; @01C75
    pop bx ; @01C77
; S19 decoder-reset-barriers: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; STD1BB0 is transient:1BB9 calls1D2E,CLD1D34 before DOS/cache selection;normal decoder return
; CLD1C78. This is not a demonstrated returning foreground DF1 origin.
; Dependencies: Instruction-order fact; IRQ in transient STD window remains separate.
    cld ; @01C78
    ret ; @01C79
loc_1C7A:
DatReadFailure:
    mov ax,0x9a9 ; @01C7A
    mov ds,ax ; @01C7D
    jmp loc_04D0 ; @01C7F
; V2/U02 malformed/partial output recurrence:BP=initialDI;endDI=BP+low16(BEsize),wrapped.
; Each literal predecrementsDI then writesAL; match predecrementsDI,readsES:DI+distance+1,
; then writes1C9A. Only after a complete token does unsignedDI<=BP stop. Ignored short counts
; at1E17 leave old header/payload bytes; pinned0800 LEVEL output is not a universal bound.
; With nonwrapped BP0FCB, size>=1049 includes2013,>=15D6 includes25A0;>=E462 can reach
; nominal editor saveG:F42C if invoked while it is live. Actual byte order,token overshoot,
; segment/saves and continuation decide other cases. No editor-loop file call is decoded.
; S14 raw alias witness: ES=game DS,DI004B,ALFF makes DEC DI/store1C83
; set DS004A=FF. This original leaf does not validate destination ownership.
; Pinned LEVEL starts0FCB; witness does not establish a game-path004A producer
; or justify expanding an artificial native/provider domain.
WriteReverseLiteral:
    dec di ; @01C82
    mov [es:di],al ; @01C83
    ret ; @01C86
ReadAndCopyReverseMatch:
    call ReadReverseBits ; @01C87
CopyReverseMatch:
    inc bx ; @01C8A
    push si ; @01C8B
    push ds ; @01C8C
    push cx ; @01C8D
    push es ; @01C8E
    pop ds ; @01C8F
    db 0x8b,0xcb ; ENCODED: mov cx,bx (NASM chooses a different encoding) ; @01C90
loc_1C92:
    dec di ; @01C92
    db 0x8b,0xf7 ; ENCODED: mov si,di (NASM chooses a different encoding) ; @01C93
    db 0x03,0xf0 ; ENCODED: add si,ax (NASM chooses a different encoding) ; @01C95
    inc si ; @01C97
    mov bl,[si] ; @01C98
    mov [es:di],bl ; @01C9A
    loop loc_1C92 ; @01C9D
; Exit of the CopyReverseMatch byte loop (fall-through after LOOP; not an entry).
; Restores CX/DS/SI saved at 1C8B..1C8D from the live stack and RETs. BL keeps
; the last copied byte; DI points at it. Covered by c/dat.c with its parent.
CopyReverseMatchReturn:
    pop cx ; @01C9F
    pop ds ; @01CA0
    pop si ; @01CA1
    ret ; @01CA2
ReadReverseBits:
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @01CA3
loc_1CA5:
    dec ch ; @01CA5
    jnz loc_1CB0 ; @01CA7
    dec si ; @01CA9
    mov dl,[si] ; @01CAA
    db 0x32,0xf2 ; ENCODED: xor dh,dl (NASM chooses a different encoding) ; @01CAC
    mov ch,0x8 ; @01CAE
loc_1CB0:
    shr dl,1 ; @01CB0
    rcl ax,1 ; @01CB2
    dec cl ; @01CB4
    jnz loc_1CA5 ; @01CB6
    ret ; @01CB8
OpenDatFile:
    push ds ; @01CB9
    push dx ; @01CBA
    push es ; @01CBB
    push di ; @01CBC
    push cx ; @01CBD
    push si ; @01CBE
    cmp byte [DatCacheEnabled-GameDataImage],0xff ; @01CBF
    jnz loc_1CCD ; @01CC4
    cmp byte [DatCacheSelected-GameDataImage],0xff ; @01CC6
    jz loc_1CD2 ; @01CCB
loc_1CCD:
    mov ax,0x3d00 ; @01CCD
    int 0x21 ; @01CD0
loc_1CD2:
    pop si ; @01CD2
    pop cx ; @01CD3
    pop di ; @01CD4
    pop es ; @01CD5
    pop dx ; @01CD6
    pop ds ; @01CD7
    ret ; @01CD8
CheckDatFile:
    push ds ; @01CD9
    push dx ; @01CDA
    push es ; @01CDB
    push di ; @01CDC
    push cx ; @01CDD
    push si ; @01CDE
    cmp byte [DatCacheEnabled-GameDataImage],0xff ; @01CDF
    jnz loc_1CEE ; @01CE4
    call PrepareDatCacheName ; @01CE6
DatAfterNamePreparation:
    call SelectCachedDatFile ; @01CE9
DatAfterCacheSelection:
    jnc loc_1CFE ; @01CEC
loc_1CEE:
    mov ax,0x4300 ; @01CEE
    db 0x33,0xc9 ; ENCODED: xor cx,cx (NASM chooses a different encoding) ; @01CF1
    int 0x21 ; @01CF3
    jc loc_1D05 ; @01CF5
    cmp byte [DatCriticalErrorFlag-GameDataImage],0x0 ; @01CF7
    jnz loc_1D05 ; @01CFC
loc_1CFE:
    pop si ; @01CFE
    pop cx ; @01CFF
    pop di ; @01D00
    pop es ; @01D01
    pop dx ; @01D02
    pop ds ; @01D03
    ret ; @01D04
loc_1D05:
    push dx ; @01D05
    push cx ; @01D06
    push es ; @01D07
    push ds ; @01D08
    push di ; @01D09
    push si ; @01D0A
    mov ax,0x9a9 ; @01D0B
    mov ds,ax ; @01D0E
    cmp byte [DatRetryEnabled-GameDataImage],0x0 ; @01D10
    jz loc_1D22 ; @01D15
    call ShowResourceRetryScreen ; @01D17
DatAfterFileRetry:
    pop si ; @01D1A
    pop di ; @01D1B
    pop ds ; @01D1C
    pop es ; @01D1D
    pop cx ; @01D1E
    pop dx ; @01D1F
    jmp short loc_1CEE ; @01D20
loc_1D22:
    pop si ; @01D22
    pop di ; @01D23
    pop ds ; @01D24
    pop es ; @01D25
    pop cx ; @01D26
    pop dx ; @01D27
; S8 filename-error alias: Only identified ordinary2528 store is191B in raw-file entry1916. DAT
; attribute failure1D22..1D2B restores DX then replaces it with2194 and tails1949 without
; updating2528.195D therefore prints the prior raw filename pointer, or initial stored0000
; before a raw read; do not silently replace it with the failing DAT filename. Generic aliases
; remain open.
    mov dx,DatFileErrorMessage-GameDataImage ; @01D28
    jmp loc_1949 ; @01D2B
; R1: CLD1D34 is a local reset before cache/direct reads. PROFILE21:AH=0023/003F
; keeps DF0 through1DEF/1E00 and normal returns1E10/1E1B; CONSERVATIVE provider DF is unknown.
; Name/cache-selection strings1E1C..1ECF precede this reset and retain their own input contract.
; No allocation/read-completeness or uninterrupted-lifetime invariant follows.
ReadDatBytes:
; RESOURCE FOOTPRINT SEAM: a cache hit copies requested CX bytes even beyond
; the descriptor's stored supplied length. A cache miss may requestFFFF bytes
; at cache-free segment:(offset+0D), publishing AX as length even on CF error.
; FCB AH23 uses main1F95 (37-byte FCB; size DWORD1FB6..1FB9); ordinary file
; checks do not populate resource destinations. PrepareDatCacheName1E1C can
; wrap padding counts toFFFF and then overwrite almost an entire DS frame;
; table/state immutability cannot be deduced solely from absolute store xrefs.
; Startup clears enabled1F93 then explicitly disables it at00D8. Allocation
; candidate1ED7 has no known incoming edge; broader cache reachability/aliases
; remain unresolved, not dead. Cache images, if enabled, outlive a level until
; overwritten/freed; per-read cursor/descriptor updates are not level resets.
    push di ; @01D2E
    push si ; @01D2F
    push ds ; @01D30
    push bx ; @01D31
    push cx ; @01D32
    push dx ; @01D33
; S19 decoder-reset-barriers: CONSERVATIVE=UNCONDITIONAL; PROFILE=UNCONDITIONAL.
; STD1BB0 is transient:1BB9 calls1D2E,CLD1D34 before DOS/cache selection;normal decoder return
; CLD1C78. This is not a demonstrated returning foreground DF1 origin.
; Dependencies: Instruction-order fact; IRQ in transient STD window remains separate.
    cld ; @01D34
    mov ax,0x9a9 ; @01D35
    mov ds,ax ; @01D38
    cmp byte [DatCacheEnabled-GameDataImage],0xff ; @01D3A
    jz loc_1D44 ; @01D3F
    jmp loc_1E11 ; @01D41
loc_1D44:
    cmp byte [DatCacheSelected-GameDataImage],0xff ; @01D44
    jnz loc_1D4E ; @01D49
    jmp loc_1DF1 ; @01D4B
loc_1D4E:
    mov ah,0x23 ; @01D4E
    lea dx,[DatCacheFcb-GameDataImage] ; @01D50
    mov word [0x1fa3],0x1 ; @01D54
    int 0x21 ; @01D5A
    mov dx,[0x1fb6] ; @01D5C
    mov ax,[0x1fb8] ; @01D60
    push dx ; @01D63
    shr ax,1 ; @01D64
    rcr dx,1 ; @01D66
    shr ax,1 ; @01D68
    rcr dx,1 ; @01D6A
    shr ax,1 ; @01D6C
    rcr dx,1 ; @01D6E
    shr ax,1 ; @01D70
    rcr dx,1 ; @01D72
    pop ax ; @01D74
    and ax,0xf ; @01D75
    jnz loc_1D7D ; @01D78
    jmp short loc_1D7E ; @01D7A
; Jump-shortening filler: NOP after a short forward JMP; no incoming edge or reader identified.
; DATA: padding
    db 0x90 ; @01D7C
loc_1D7D:
    inc dx ; @01D7D
loc_1D7E:
    cmp dx,[DatCacheRemainingParagraphs-GameDataImage] ; @01D7E
    jna loc_1D87 ; @01D82
    jmp loc_1E11 ; @01D84
loc_1D87:
    inc byte [DatCacheRecordCount-GameDataImage] ; @01D87
    sub [DatCacheRemainingParagraphs-GameDataImage],dx ; @01D8B
    push ds ; @01D8F
    mov cx,0xffff ; @01D90
    mov dx,[DatCacheFreeOffset-GameDataImage] ; @01D93
    mov ax,[DatCacheFreeSegment-GameDataImage] ; @01D97
    mov [DatCacheRecordOffset-GameDataImage],dx ; @01D9A
    mov [DatCacheRecordSegment-GameDataImage],ax ; @01D9E
    mov byte [DatCacheSelected-GameDataImage],0xff ; @01DA1
    add dx,byte +0xd ; @01DA6
    mov [DatCacheReadOffset-GameDataImage],dx ; @01DA9
    mov [DatCacheReadSegment-GameDataImage],ax ; @01DAD
    push ax ; @01DB0
    push dx ; @01DB1
    mov ds,ax ; @01DB2
    mov ah,0x3f ; @01DB4
    int 0x21 ; @01DB6
    db 0x8b,0xc8 ; ENCODED: mov cx,ax (NASM chooses a different encoding) ; @01DB8
    pop dx ; @01DBA
    pop ax ; @01DBB
    pop ds ; @01DBC
    db 0x03,0xd1 ; ENCODED: add dx,cx (NASM chooses a different encoding) ; @01DBD
    push dx ; @01DBF
    shr dx,1 ; @01DC0
    shr dx,1 ; @01DC2
    shr dx,1 ; @01DC4
    shr dx,1 ; @01DC6
    db 0x03,0xc2 ; ENCODED: add ax,dx (NASM chooses a different encoding) ; @01DC8
    pop dx ; @01DCA
    and dx,byte +0xf ; @01DCB
    mov [DatCacheFreeOffset-GameDataImage],dx ; @01DCE
    mov [DatCacheFreeSegment-GameDataImage],ax ; @01DD2
    mov di,[DatCacheRecordOffset-GameDataImage] ; @01DD5
    mov es,[DatCacheRecordSegment-GameDataImage] ; @01DD9
    mov dx,[0x1fb8] ; @01DDD
    mov [es:di+0xb],cx ; @01DE1
    lea si,[0x1f96] ; @01DE5
    add di,byte +0x0 ; @01DE9
    mov cx,0xb ; @01DEC
; S19 DF-site census rep movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsb ; @01DEF
loc_1DF1:
    pop di ; @01DF1
    pop cx ; @01DF2
    pop bx ; @01DF3
    pop es ; @01DF4
    push es ; @01DF5
    push di ; @01DF6
    push ds ; @01DF7
    mov si,[DatCacheReadOffset-GameDataImage] ; @01DF8
    mov ds,[DatCacheReadSegment-GameDataImage] ; @01DFC
; S19 DF-site census rep movsb byte ptr es:[di], byte ptr [si]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep movsb ; @01E00
    mov ax,ds ; @01E02
    pop ds ; @01E04
    mov [DatCacheReadSegment-GameDataImage],ax ; @01E05
    mov [DatCacheReadOffset-GameDataImage],si ; @01E08
    pop dx ; @01E0C
    pop ds ; @01E0D
    pop si ; @01E0E
    pop di ; @01E0F
    ret ; @01E10
loc_1E11:
    pop dx ; @01E11
    pop cx ; @01E12
    pop bx ; @01E13
    pop ds ; @01E14
    mov ah,0x3f ; @01E15
    int 0x21 ; @01E17
    pop si ; @01E19
    pop di ; @01E1A
    ret ; @01E1B
PrepareDatCacheName:
    push dx ; @01E1C
    push es ; @01E1D
    push ax ; @01E1E
    push cx ; @01E1F
    push ds ; @01E20
    pop es ; @01E21
    db 0x8b,0xf2 ; ENCODED: mov si,dx (NASM chooses a different encoding) ; @01E22
    mov cx,0x8 ; @01E24
    lea di,[0x1f96] ; @01E27
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_1E2B:
    lodsb ; @01E2B
    cmp al,0x2e ; @01E2C
    jz loc_1E58 ; @01E2E
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @01E30
    loop loc_1E2B ; @01E31
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_1E33:
    lodsb ; @01E33
    cmp al,0x2e ; @01E34
    jnz loc_1E33 ; @01E36
loc_1E38:
    mov cx,0x3 ; @01E38
    lea di,[0x1f9e] ; @01E3B
; S19 DF-site census lodsb al, byte ptr [si]: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
loc_1E3F:
    lodsb ; @01E3F
    db 0x22,0xc0 ; ENCODED: and al,al (NASM chooses a different encoding) ; @01E40
    jz loc_1E49 ; @01E42
; S19 DF-site census stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED for
; actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    stosb ; @01E44
    loop loc_1E3F ; @01E45
    jmp short loc_1E53 ; @01E47
loc_1E49:
    mov ax,0x2 ; @01E49
    db 0x2b,0xc1 ; ENCODED: sub ax,cx (NASM chooses a different encoding) ; @01E4C
    xchg ax,cx ; @01E4E
    mov al,0x20 ; @01E4F
; S19 DF-site census rep stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED
; for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep stosb ; @01E51
loc_1E53:
    pop cx ; @01E53
    pop ax ; @01E54
    pop es ; @01E55
    pop dx ; @01E56
    ret ; @01E57
; V2/U02 name writer domain:dot after k<8 basename bytes gives1E60 count(k-1)&FFFF,
; start1F96+DFsign*k. k0 writesFFFF spaces:DF0 misses only1F95,DF1 only1F97. Extension
; NUL after j<3 bytes gives1E51 count(j-1)&FFFF,start1F9E+DFsign*j; j0 misses1F9D/1F9F.
; Both underflows cover2013..201E,25A0..25A6,and ordinary stack saves atG:F42C/F436,
; setting bytes20 before actual POPs. Known code filename literals/digit edits have basename
; length4..8,extension3,so exclude these underflows while names are intact. Optional cache
; 1F93 must actually be enabled;1ED7's missing decoded caller is not a dead-code proof.
; Miss1DE1 descriptor+0B,1DEF name copy and1E00 requested-length hit/output use actual
; cache cursors/ES/DI;13-byte descriptor is not included in reserved file-size paragraphs.
; Canonical separate DOS-owned blocks plus pinned lengths exclude low-table writes only
; for their bounded extents; padding corruption,mis-sized descriptors and changed saves
; follow these concrete writes rather than an arbitrary cache-alias exemption.
loc_1E58:
    mov ax,0x7 ; @01E58
    db 0x2b,0xc1 ; ENCODED: sub ax,cx (NASM chooses a different encoding) ; @01E5B
    xchg ax,cx ; @01E5D
    mov al,0x20 ; @01E5E
; S19 DF-site census rep stosb byte ptr es:[di], al: CONSERVATIVE=UNRESOLVED; PROFILE=UNRESOLVED
; for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    rep stosb ; @01E60
    jmp short loc_1E38 ; @01E62
SelectCachedDatFile:
    push ds ; @01E64
    mov cl,[DatCacheRecordCount-GameDataImage] ; @01E65
    db 0x22,0xc9 ; ENCODED: and cl,cl (NASM chooses a different encoding) ; @01E69
    jz loc_1EA7 ; @01E6B
    db 0x32,0xed ; ENCODED: xor ch,ch (NASM chooses a different encoding) ; @01E6D
    push ds ; @01E6F
    pop es ; @01E70
    mov ds,[DatCacheBaseSegment-GameDataImage] ; @01E71
    db 0x33,0xf6 ; ENCODED: xor si,si (NASM chooses a different encoding) ; @01E75
    lea di,[0x1f96] ; @01E77
loc_1E7B:
    push cx ; @01E7B
    push ds ; @01E7C
    push si ; @01E7D
    push di ; @01E7E
    mov cx,0xb ; @01E7F
; S19 DF-site census repe cmpsb byte ptr [si], byte ptr es:[di]: CONSERVATIVE=UNRESOLVED;
; PROFILE=UNRESOLVED for actual whole-machine DF/segment inputs.
; Use live DF/segments and saves. Local decoded effects remain in s19-platform.json; IRQ,frame
; alias,writer/vector and protected-view composition stay separate. No boundary CLD assumed.
    repe cmpsb ; @01E82
    pop di ; @01E84
    pop si ; @01E85
    db 0x23,0xc9 ; ENCODED: and cx,cx (NASM chooses a different encoding) ; @01E86
    jz loc_1EAF ; @01E88
    pop ds ; @01E8A
    add si,[si+0xb] ; @01E8B
    add si,byte +0xd ; @01E8E
    db 0x8b,0xc6 ; ENCODED: mov ax,si (NASM chooses a different encoding) ; @01E91
    shr ax,1 ; @01E93
    shr ax,1 ; @01E95
    shr ax,1 ; @01E97
    shr ax,1 ; @01E99
    mov cx,ds ; @01E9B
    db 0x03,0xc8 ; ENCODED: add cx,ax (NASM chooses a different encoding) ; @01E9D
    mov ds,cx ; @01E9F
    and si,byte +0xf ; @01EA1
    pop cx ; @01EA4
    loop loc_1E7B ; @01EA5
loc_1EA7:
    pop ds ; @01EA7
    mov byte [DatCacheSelected-GameDataImage],0x0 ; @01EA8
    stc ; @01EAD
    ret ; @01EAE
loc_1EAF:
    mov ax,ds ; @01EAF
    pop ds ; @01EB1
    pop cx ; @01EB2
    mov cx,0x9a9 ; @01EB3
    mov ds,cx ; @01EB6
    mov [DatCacheRecordOffset-GameDataImage],si ; @01EB8
    mov [DatCacheRecordSegment-GameDataImage],ax ; @01EBC
    add si,byte +0xd ; @01EBF
    mov [DatCacheReadOffset-GameDataImage],si ; @01EC2
    mov [DatCacheReadSegment-GameDataImage],ax ; @01EC6
    mov byte [DatCacheSelected-GameDataImage],0xff ; @01EC9
    pop ds ; @01ECE
    clc ; @01ECF
    ret ; @01ED0
DisableDatCache:
    db 0x32,0xc0 ; ENCODED: xor al,al (NASM chooses a different encoding) ; @01ED1
    mov [DatCacheEnabled-GameDataImage],al ; @01ED3
    ret ; @01ED6
; Recovered allocation candidate; no known incoming execution edge.
; CONTRACT: live DS cache fields, SS:SP near return; DOS AH48 provider seam.
; First returned BX alone selects the unsigned >=0C80 paragraph path.
; Neither carry result is tested: even second AX=0008 is published as a segment.
; Low path clears AL/enabled only; all other cache fields and AH stay live.
; See docs/cache-allocation.md and the separate original-only contract gate.
AllocateDatCache:
    mov ah,0x48 ; @01ED7
    mov bx,0xffff ; @01ED9
DatCacheAllocationRequest:
    int 0x21 ; @01EDC
    cmp bx,0xc80 ; @01EDE
    jb DatCacheAllocationBelowThreshold ; @01EE2
    mov [DatCacheRequestedParagraphs-GameDataImage],bx ; @01EE4
    mov [DatCacheRemainingParagraphs-GameDataImage],bx ; @01EE8
    mov ah,0x48 ; @01EEC
    int 0x21 ; @01EEE
    mov [DatCacheBaseSegment-GameDataImage],ax ; @01EF0
    mov [DatCacheRecordSegment-GameDataImage],ax ; @01EF3
    mov [DatCacheReadSegment-GameDataImage],ax ; @01EF6
    mov [DatCacheFreeSegment-GameDataImage],ax ; @01EF9
    db 0x33,0xc0 ; ENCODED: xor ax,ax (register destination opcode33; NASM chooses31) ; @01EFC
    mov [DatCacheRecordOffset-GameDataImage],ax ; @01EFE
    mov [DatCacheReadOffset-GameDataImage],ax ; @01F01
    mov [DatCacheFreeOffset-GameDataImage],ax ; @01F04
    mov [DatCacheRecordCount-GameDataImage],al ; @01F07
    mov [DatCacheSelected-GameDataImage],al ; @01F0A
    mov al,0xff ; @01F0D
    mov [DatCacheEnabled-GameDataImage],al ; @01F0F
DatCacheAllocationReadyReturn:
    ret ; @01F12
DatCacheAllocationBelowThreshold:
    db 0x32,0xc0 ; ENCODED: xor al,al (register destination opcode32; NASM chooses30) ; @01F13
    mov [DatCacheEnabled-GameDataImage],al ; @01F15
DatCacheAllocationDisabledReturn:
    ret ; @01F18

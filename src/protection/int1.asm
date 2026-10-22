; Derived execution view. Canonical load bytes are in src/program.asm.
; Stream instructions show bytes visible while TF is on/off; first-word patches can overlap.
; Bytes outside this view retain stored encoding and canonical region classifications.
bits 16
org 0x0dff
; Contract: active INT1 plaintext exists only after INT3 has byte-negated all
; 0DFF..0E39 and installed CS:0DFF in IVT1. Do not load this view as canonical
; code. Ordinary stream entry is TF-clear 066C; raw arbitrary frames are wider.
; Interrupt entry SS:S holds IP,CS,FLAGS. Three pushes make T=S-6; saved AX,
; SI,DS are restored from live SS and IRET consumes the live far return frame.
; AX/SI/DS are scratch, other general/segment registers are untouched; DF is
; not read or changed. STI permits IRQs inside INT1, even if saved IF is clear.
; Without aliases/intervening writers, IRET preserves interrupted FLAGS. Stack
; offsets and SI arithmetic wrap at 16 bits; far memory uses the loaded DS,
; not necessarily this handler's CS. Do not suppress below-SP residue or aliases.
ProtectionInt1Handler:
    sti ; @00DFF int1_plaintext
    push ax ; @00E00 int1_plaintext
    push si ; @00E01 int1_plaintext
    push ds ; @00E02 int1_plaintext
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @00E03 int1_plaintext
    mov ds,ax ; @00E05 int1_plaintext
; IVT0 (physical 00000..00003) owns previous patched offset:segment until
; 0976 restores saved vectors. Read old[-2], NOT/ROL16 by 1, XOR current old
; word, then XCHG restores it. AX now contains the displaced PLAINTEXT word.
; CC guard skips the next patch only when that displaced low byte is CC.
; INT3 disable instead tests candidate ciphertext before its conditional swap.
    lds si,[0x0] ; @00E07 int1_plaintext
    mov ax,[si-0x2] ; @00E0B int1_plaintext
    not ax ; @00E0E int1_plaintext
    rol ax,1 ; @00E10 int1_plaintext
    xor ax,[si] ; @00E12 int1_plaintext
    xchg [si],ax ; @00E14 int1_plaintext
    cmp al,0xcc ; @00E16 int1_plaintext
    jz protected_loc_0E36 ; @00E18 int1_plaintext
    db 0x8b,0xf4 ; ENCODED: mov si,sp (NASM chooses a different encoding) ; @00E1A int1_plaintext
ProtectionDecodeNextWord:
; Shared tail: SI must be T, the post-three-push SP. INT1 supplies it at 0E1A;
; enabling INT3 supplies it at 0DDA and enters from 0DE6 after toggling saved
; TF/IF. SS:[T+6] is interrupted IP followed by CS, so LDS makes DS:SI the
; dynamic next instruction, including taken branches, CALLs and returned IPs.
; It is not an LDS through a fixed table and is not bounded by the code segment.
; Patch current word using ROL16(NOT word(DS,(SI-2) mod 10000),1), then publish
; this new far pointer in IVT0. Old restoration MUST precede these reads for
; adjacent one-byte instructions: overlapping patches otherwise change keys.
; Reads/writes are ordered and unchecked. Stack/IVT/code aliases or a provider
; changing an interrupted frame can select different memory; the static stream
; inventories known points, not every possible raw return or disk-body path.
    lds si,[ss:si+0x6] ; @00E1C int1_plaintext
    mov ax,[si-0x2] ; @00E20 int1_plaintext
    not ax ; @00E23 int1_plaintext
    rol ax,1 ; @00E25 int1_plaintext
    xor [si],ax ; @00E27 int1_plaintext
; For known next IPs: 0852 reads 0850..0851 (030E); 0853 also reads 0851.
; 0883 reads 0881..0882 (260E); 0884 also reads 0882. Thus the last two bytes
; of each skipped five-byte gap are key data even though not executed here.
; 0D9E reads 0D9C..0D9D (9090): key DEDE exposes CC13 from stored 12 CD.
; These data roles do not classify the other gap bytes or prove write entries.
    push ds ; @00E29 int1_plaintext
    db 0x33,0xc0 ; ENCODED: xor ax,ax (NASM chooses a different encoding) ; @00E2A int1_plaintext
    mov ds,ax ; @00E2C int1_plaintext
    mov [0x0],si ; @00E2E int1_plaintext
    pop word [0x2] ; @00E32 int1_plaintext
protected_loc_0E36:
    pop ds ; @00E36 int1_plaintext
    pop si ; @00E37 int1_plaintext
    pop ax ; @00E38 int1_plaintext
    iret ; @00E39 int1_plaintext

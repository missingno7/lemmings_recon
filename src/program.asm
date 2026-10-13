bits 16
org 0
ChecksumWindow equ $$ + 0x188F ; overlay inside instruction
%include "code.asm"
%include "image_tail.asm"

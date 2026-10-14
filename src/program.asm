bits 16
org 0
ChecksumWindow equ $$ + 0x188F ; overlay inside instruction
%include "entry_services.asm"
times -(($-$$) != 0x1916) db 0 ; module end assertion
%include "resources.asm"
times -(($-$$) != 0x1ed7) db 0 ; module end assertion
%include "game_code.asm"
times -(($-$$) != 0x378a) db 0 ; module end assertion
%include "level_objects.asm"
times -(($-$$) != 0x3944) db 0 ; module end assertion
%include "game_code_late.asm"
times -(($-$$) != 0x8238) db 0 ; module end assertion
%include "special_graphics.asm"
times -(($-$$) != 0x8343) db 0 ; module end assertion
%include "checksum.asm"
times -(($-$$) != 0x83bf) db 0 ; module end assertion
%include "code_tail.asm"
times -(($-$$) != 0x9a90) db 0 ; module end assertion
%include "image_tail.asm"

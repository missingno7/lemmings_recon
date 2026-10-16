bits 16
org 0
ChecksumWindow equ $$ + 0x188F ; overlay inside instruction
%include "entry_services.asm"
times -(($-$$) != 0x1916) db 0 ; module end assertion
%include "resources.asm"
times -(($-$$) != 0x1f19) db 0 ; module end assertion
%include "game_code.asm"
times -(($-$$) != 0x3150) db 0 ; module end assertion
%include "entity_actions.asm"
times -(($-$$) != 0x3634) db 0 ; module end assertion
%include "entity_drawing_calls.asm"
times -(($-$$) != 0x368e) db 0 ; module end assertion
%include "level_initialize.asm"
times -(($-$$) != 0x378a) db 0 ; module end assertion
%include "level_objects.asm"
times -(($-$$) != 0x3944) db 0 ; module end assertion
%include "game_code_late.asm"
times -(($-$$) != 0x52d4) db 0 ; module end assertion
%include "palette_frontends.asm"
times -(($-$$) != 0x563e) db 0 ; module end assertion
%include "palette_steps.asm"
times -(($-$$) != 0x5726) db 0 ; module end assertion
%include "game_code_late_after_palette.asm"
times -(($-$$) != 0x5d66) db 0 ; module end assertion
%include "entity_graphics.asm"
times -(($-$$) != 0x6170) db 0 ; module end assertion
%include "game_code_late_after_entities.asm"
times -(($-$$) != 0x796f) db 0 ; module end assertion
%include "minimap.asm"
times -(($-$$) != 0x7a5a) db 0 ; module end assertion
%include "game_code_late_tail.asm"
times -(($-$$) != 0x8238) db 0 ; module end assertion
%include "special_graphics.asm"
times -(($-$$) != 0x8343) db 0 ; module end assertion
%include "checksum.asm"
times -(($-$$) != 0x83bf) db 0 ; module end assertion
%include "code_tail.asm"
times -(($-$$) != 0x8822) db 0 ; module end assertion
%include "planar_drawing.asm"
times -(($-$$) != 0x9a90) db 0 ; module end assertion
%include "image_tail.asm"

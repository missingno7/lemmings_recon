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
times -(($-$$) != 0x39ce) db 0 ; module end assertion
%include "status_initialize.asm"
times -(($-$$) != 0x3ac8) db 0 ; module end assertion
%include "status_display.asm"
times -(($-$$) != 0x3cde) db 0 ; module end assertion
%include "entity_selection.asm"
times -(($-$$) != 0x3e6f) db 0 ; module end assertion
%include "game_code_late_after_selection.asm"
%include "view_visibility.asm"
%include "game_code_after_view_visibility.asm"
%include "input_poll.asm"
%include "port201_input.asm"
%include "input_menu_and_retry.asm"
times -(($-$$) != 0x4b5c) db 0 ; module end assertion
%include "decimal_fields.asm"
times -(($-$$) != 0x4be7) db 0 ; module end assertion
%include "game_code_late_after_decimal.asm"
times -(($-$$) != 0x52d4) db 0 ; module end assertion
%include "palette_frontends.asm"
times -(($-$$) != 0x563e) db 0 ; module end assertion
%include "palette_steps.asm"
times -(($-$$) != 0x5726) db 0 ; module end assertion
%include "entity_dirty.asm"
%include "game_code_late_after_palette.asm"
times -(($-$$) != 0x5b11) db 0 ; module end assertion
%include "sprite_banks.asm"
times -(($-$$) != 0x5cc1) db 0 ; module end assertion
%include "game_code_after_sprite_banks.asm"
times -(($-$$) != 0x5d66) db 0 ; module end assertion
%include "entity_graphics.asm"
times -(($-$$) != 0x6170) db 0 ; module end assertion
%include "entity_sprite_aligned.asm"
%include "entity_sprite_shifted.asm"
%include "entity_sprite_planes.asm"
%include "entity_sprite_wide.asm"
%include "entity_sprite_four_planes.asm"
%include "entity_points.asm"
%include "entity_strip.asm"
%include "entity_minimap.asm"
%include "entity_sprite_dispatch.asm"
%include "fixed_pattern_drawing.asm"
times -(($-$$) != 0x75ef) db 0 ; module end assertion
%include "status_copy.asm"
times -(($-$$) != 0x762a) db 0 ; module end assertion
%include "status_glyphs.asm"
times -(($-$$) != 0x780d) db 0 ; module end assertion
%include "status_icons.asm"
times -(($-$$) != 0x7900) db 0 ; module end assertion
%include "game_code_before_minimap.asm"
times -(($-$$) != 0x796f) db 0 ; module end assertion
%include "minimap.asm"
times -(($-$$) != 0x7a5a) db 0 ; module end assertion
%include "minimap_viewport.asm"
times -(($-$$) != 0x7bb8) db 0 ; module end assertion
%include "object_graphics_tick.asm"
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

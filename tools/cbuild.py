"""Build a portable C11 translation cluster for bounded native verification."""
import os
from pathlib import Path
import shutil
from bounded_process import run_bounded

ROOT = Path(__file__).resolve().parents[1]
CC = Path(os.environ.get("LEMMINGS_CC", r"C:\msys64\mingw64\bin\gcc.exe"))

def compiler():
    if CC.is_file():
        return str(CC)
    found = shutil.which("gcc")
    if found:
        return found
    raise RuntimeError("GCC not found; set LEMMINGS_CC to gcc.exe")

def build(output=None, mutation=0, cluster="checksum"):
    if cluster not in ("main_menu","menu_scroll","menu_cache","menu_animation","keyboard_input","timer_install","menu_timer","game_timer","palette_timer","timer_tail","ui_commands","input_poll","port_io","mouse_irq_bridge","vga_mirrors","fixed_pattern_copy","fixed_pattern_draw","fixed_pattern_update","main_resources","fixed_word_banks","vga_plane_copy","entity_sprite_banks","sprite_wide_banks","sprite_shift_banks","sprite_bank","entity_drawing","entity_sprite_dispatch","entity_sprite_planes","entity_sprite_wide","entity_sprite_aligned","entity_sprite_shifted","entity_points","entity_strip","entity_minimap","view_visibility","entity_dirty","status_copy","status_initialize","object_drawing_tick","object_animation","status_display","status_display_full","status_text","status_count","status_glyph","status_icons","minimap_viewport","minimap_status","decimal_field","entity_select","entity_actions_advanced","entity_action_map","entity_actions_basic","entity_action_dispatch","entity_batch","entity_action_sound","entity_create","entity_update","entity_state800","entity_late_states","entity_state400","entity_state200","entity_state80","entity_state100","entity_state10","entity_state20","entity_state40","entity_state2","entity_state8","entity_pattern_bus","entity_state4","entity_cadence","entity_finish","entity_zero_state","pcspeaker_interrupt","entity_interactions","pcspeaker_bus","pcspeaker_dispatch","entity_countdown","sound_interrupt","sound_latches","coordinate_pixel","entity_mask_rows","entity_mask","mask_generators","generated_graphics","entity_stroke","entity_vga","entity_pixel","entity_pattern","checksum","pcspeaker","dat","dat_io","dat_section","dat_cache","cache_allocation","display_status","display_start","display_setup","display_pages","background_drawing","palette_channels","palette_rows","palette_ports","palette_row_select","palette_transition","retry_input","retry_ui","text_glyph","text_stream","video_restore","vector_restore","timer_restore","fatal_cleanup","file_error","resource_raw_full","resource_select_full","dat_files","dat_load","resource_raw","resource_rle","special_blit","special_setup","decimal_digits","resource_select","object_graphics","object_coordinates","object_cells","steel_cells","object_state","vga_clear","drawing_layout","level_drawing","level_header","level_finish","level_initialize","minimap_sample","minimap_row","minimap_column","drawing_clip","drawing_dirty","drawing_inputs","drawing_dispatch","drawing_source","drawing_plan","aligned_opaque","drawing_render","aligned_masked","aligned_mask_effects","aligned_protected","aligned_read_mask","shifted_mask_effects","shifted_opaque","shifted_masked","shifted_protected","shifted_read_mask","terrain_drawing","terrain_stream","object_drawing","level_redraw"):
        raise ValueError("Unknown C cluster")
    out = Path(output) if output else ROOT / "build" / (cluster+".dll")
    out.parent.mkdir(parents=True, exist_ok=True)
    sources=[ROOT/"c"/(cluster+".c")]
    if cluster in ("menu_scroll","menu_cache"):sources += [ROOT/"c/display_start.c"]
    if cluster=="main_menu":sources += [ROOT/"c"/(n+".c") for n in ("keyboard_input","menu_scroll","menu_animation","menu_cache")]
    if cluster in ("keyboard_input","main_menu"):sources += [ROOT/"c/port_io.c",ROOT/"c/interrupt_service.c",ROOT/"c/input_poll.c",ROOT/"c/display_status.c"]
    if cluster in ("keyboard_input","main_menu"):sources += [ROOT/"c"/(n+".c") for n in ('background_drawing', 'display_setup', 'drawing_layout', 'display_pages', 'vga_clear', 'palette_transition', 'palette_rows', 'palette_channels', 'palette_ports', 'text_stream', 'text_glyph', 'display_start', 'drawing_render', 'drawing_plan', 'drawing_inputs', 'drawing_clip', 'drawing_dirty', 'drawing_dispatch', 'drawing_source', 'aligned_opaque', 'aligned_masked', 'aligned_mask_effects', 'aligned_protected', 'aligned_read_mask', 'shifted_mask_effects', 'shifted_opaque', 'shifted_masked', 'shifted_protected', 'shifted_read_mask')]
    if cluster=="mouse_irq_bridge":sources += [ROOT/"c/vga_mirrors.c"]
    if cluster=="fixed_pattern_draw":sources += [ROOT/"c/fixed_word_banks.c",ROOT/"c/mask_generators.c"]
    if cluster=="fixed_pattern_update":sources += [ROOT/"c"/(n+".c") for n in ("fixed_pattern_copy","fixed_pattern_draw","fixed_word_banks","mask_generators")]
    if cluster=="main_resources":sources += [ROOT/"c"/(n+".c") for n in ("dat_load","dat_files","dat_cache","dat_section","dat_io","dat","entity_sprite_banks","sprite_shift_banks","sprite_bank","sprite_wide_banks","fixed_word_banks","generated_graphics","mask_generators","vga_plane_copy")]
    if cluster=="fixed_word_banks":sources += [ROOT/"c/mask_generators.c"]
    if cluster=="entity_sprite_banks":sources += [ROOT/"c"/(name+".c") for name in ("sprite_shift_banks","sprite_bank","sprite_wide_banks")]
    if cluster=="entity_sprite_planes":sources=[ROOT/"c/entity_sprite_shifted.c"]
    if cluster=="entity_drawing":sources += [ROOT/"c"/(name+".c") for name in ("entity_minimap","entity_dirty","entity_points","entity_sprite_dispatch","entity_sprite_aligned","entity_sprite_shifted","entity_sprite_wide","entity_strip","decimal_field")]
    if cluster=="entity_sprite_dispatch":sources += [ROOT/"c"/(name+".c") for name in ("entity_sprite_aligned","entity_sprite_shifted","entity_sprite_wide","entity_strip")]
    if cluster=="entity_dirty":sources += [ROOT/"c/view_visibility.c"]
    if cluster=="status_initialize":sources += [ROOT/"c"/(n+".c") for n in ("status_copy","status_count","decimal_field","status_icons")]
    if cluster in ("status_display","status_display_full"):sources += [ROOT/"c"/(n+".c") for n in ("status_text","status_glyph","status_count","status_icons")]
    if cluster=="status_display_full":sources += [ROOT/"c"/(n+".c") for n in ("status_display","minimap_status","minimap_viewport","minimap_column","minimap_row","minimap_sample")]
    if cluster=="status_text":sources += [ROOT/"c/status_glyph.c"]
    if cluster=="minimap_status":sources += [ROOT/"c"/(n+".c") for n in ("minimap_viewport","minimap_column","minimap_row","minimap_sample")]
    if cluster=="entity_select":sources += [ROOT/"c/decimal_field.c"]
    if cluster in ("entity_actions_basic","entity_actions_advanced","entity_action_map","entity_action_dispatch"):sources += [ROOT/"c/entity_action_sound.c"]
    if cluster=="entity_action_dispatch":sources += [ROOT/"c/entity_actions_basic.c",ROOT/"c/entity_actions_advanced.c",ROOT/"c/entity_action_map.c"]
    if cluster in ("entity_action_sound","entity_actions_basic","entity_actions_advanced","entity_action_map","entity_action_dispatch"):sources += [ROOT/"c"/(n+".c") for n in ("pcspeaker_interrupt","pcspeaker_dispatch","pcspeaker","sound_interrupt","sound_latches")]
    if cluster=="entity_batch":sources += [ROOT/"c/entity_create.c",ROOT/"c/entity_update.c"]
    if cluster in ("entity_update","entity_batch"):sources += [ROOT/"c"/(n+".c") for n in ('entity_vga', 'entity_countdown', 'entity_zero_state', 'entity_state2', 'entity_state4', 'entity_cadence', 'entity_state8', 'entity_state10', 'entity_state20', 'entity_state40', 'entity_state80', 'entity_state100', 'entity_state200', 'entity_state400', 'entity_state800', 'entity_late_states', 'entity_finish', 'entity_pixel', 'entity_stroke', 'entity_mask', 'entity_mask_rows', 'coordinate_pixel', 'entity_pattern', 'entity_interactions', 'pcspeaker_interrupt', 'pcspeaker_dispatch', 'pcspeaker', 'sound_interrupt', 'sound_latches')]
    if cluster=="entity_state800":sources += [ROOT/"c"/(n+".c") for n in ("entity_finish","entity_pixel","entity_mask_rows","entity_interactions","pcspeaker_interrupt","pcspeaker_dispatch","pcspeaker","sound_interrupt","sound_latches")]
    if cluster=="entity_late_states":sources += [ROOT/"c"/(n+".c") for n in ("entity_finish","entity_pixel","entity_interactions","pcspeaker_interrupt","pcspeaker_dispatch","pcspeaker","sound_interrupt","sound_latches")]
    if cluster=="entity_state400":sources += [ROOT/"c"/(n+".c") for n in ("entity_finish","entity_pixel","entity_interactions","pcspeaker_interrupt","pcspeaker_dispatch","pcspeaker","sound_interrupt","sound_latches")]
    if cluster=="entity_state200":sources += [ROOT/"c"/(n+".c") for n in ("entity_finish","entity_pixel","entity_mask_rows","coordinate_pixel","entity_interactions","pcspeaker_interrupt","pcspeaker_dispatch","pcspeaker","sound_interrupt","sound_latches")]
    if cluster=="entity_state80":sources += [ROOT/"c"/(n+".c") for n in ("entity_finish","entity_pixel","entity_stroke","entity_interactions","pcspeaker_interrupt","pcspeaker_dispatch","pcspeaker","sound_interrupt","sound_latches")]
    if cluster=="entity_state100":sources += [ROOT/"c/entity_pixel.c",ROOT/"c/entity_pattern.c"]
    if cluster=="pcspeaker_interrupt":sources += [ROOT/"c/pcspeaker_dispatch.c",ROOT/"c/pcspeaker.c"]
    if cluster=="entity_interactions":sources += [ROOT/"c"/(n+".c") for n in ("pcspeaker_interrupt","pcspeaker_dispatch","pcspeaker","sound_interrupt","sound_latches")]
    if cluster in ("entity_finish","entity_zero_state","entity_state4","entity_cadence","entity_state8","entity_state2","entity_state10","entity_state20","entity_state40"):sources += [ROOT/"c"/(n+".c") for n in ("entity_interactions","pcspeaker_interrupt","pcspeaker_dispatch","pcspeaker","sound_interrupt","sound_latches")]
    if cluster=="entity_zero_state":sources += [ROOT/"c/entity_finish.c",ROOT/"c/entity_pixel.c"]
    if cluster=="entity_state10":sources += [ROOT/"c/entity_finish.c",ROOT/"c/entity_pixel.c",ROOT/"c/entity_vga.c"]
    if cluster=="entity_state20":sources += [ROOT/"c/entity_finish.c",ROOT/"c/entity_pixel.c"]
    if cluster=="entity_state40":sources += [ROOT/"c/entity_finish.c"]
    if cluster=="entity_state8":sources += [ROOT/"c/entity_finish.c",ROOT/"c/entity_pixel.c"]
    if cluster=="entity_state2":sources += [ROOT/"c/entity_finish.c",ROOT/"c/entity_pattern.c",ROOT/"c/entity_mask.c"]
    if cluster=="entity_pattern_bus":sources = [ROOT/"c/entity_pattern.c"]
    if cluster=="entity_state4":sources += [ROOT/"c/entity_finish.c",ROOT/"c/entity_pixel.c"]
    if cluster=="entity_cadence":sources += [ROOT/"c/entity_finish.c",ROOT/"c/coordinate_pixel.c"]
    if cluster=="pcspeaker_bus":sources=[ROOT/"c/pcspeaker.c"]
    if cluster=="pcspeaker_dispatch":sources += [ROOT/"c/pcspeaker.c"]
    if cluster=="entity_countdown":sources += [ROOT/"c/sound_interrupt.c",ROOT/"c/sound_latches.c"]
    if cluster=="sound_interrupt":sources += [ROOT/"c/sound_latches.c"]
    if cluster=="generated_graphics":sources += [ROOT/"c/mask_generators.c"]
    if cluster=="entity_stroke":sources += [ROOT/"c/entity_pixel.c"]
    if cluster=="retry_ui":sources += [ROOT/"c"/(n+".c") for n in ("display_setup","drawing_layout","palette_transition","palette_ports","palette_rows","palette_channels","display_pages","vga_clear","background_drawing","text_stream","text_glyph","display_status","display_start","retry_input")]
    if cluster=="display_setup":sources += [ROOT/"c/drawing_layout.c"]
    if cluster=="display_pages":sources += [ROOT/"c/vga_clear.c"]
    if cluster=="palette_rows":sources += [ROOT/"c/palette_channels.c"]
    if cluster=="palette_row_select":sources += [ROOT/"c/palette_rows.c",ROOT/"c/palette_channels.c"]
    if cluster=="palette_transition":sources += [ROOT/"c"/(n+".c") for n in ("palette_ports","palette_rows","palette_channels","display_status")]
    if cluster=="text_stream":sources += [ROOT/"c/text_glyph.c"]
    if cluster=="fatal_cleanup":sources += [ROOT/"c"/(n+".c") for n in ("timer_restore","vector_restore","video_restore")]
    if cluster=="file_error":sources += [ROOT/"c"/(n+".c") for n in ("fatal_cleanup","timer_restore","vector_restore","video_restore")]
    if cluster=="resource_raw_full":sources += [ROOT/"c"/(n+".c") for n in ("resource_raw","file_error","fatal_cleanup","timer_restore","vector_restore","video_restore")]
    if cluster=="dat_section":sources += [ROOT/"c/dat.c",ROOT/"c/dat_io.c"]
    if cluster=="dat_files":sources += [ROOT/"c/dat_cache.c"]
    if cluster=="dat_load":sources += [ROOT/"c"/(n+".c") for n in ('dat','dat_io','dat_section','dat_cache','dat_files')]
    if cluster=="special_setup":sources += [ROOT/"c"/(n+".c") for n in ('dat','dat_io','dat_section','dat_cache','dat_files','dat_load','resource_rle','special_blit')]
    if cluster=="resource_select":sources += [ROOT/"c"/(n+".c") for n in ('decimal_digits','resource_raw','dat','dat_io','dat_section','dat_cache','dat_files','dat_load')]
    if cluster=="resource_select_full":sources += [ROOT/"c"/(n+".c") for n in ("resource_select","decimal_digits","resource_raw","dat","dat_io","dat_section","dat_cache","dat_files","dat_load","file_error","fatal_cleanup","timer_restore","vector_restore","video_restore")]
    if cluster=="object_state":sources += [ROOT/"c"/(n+".c") for n in ('object_graphics','steel_cells','object_cells','object_coordinates')]
    if cluster=="level_drawing":sources += [ROOT/"c"/(n+".c") for n in ('vga_clear','drawing_layout')]
    if cluster=="level_finish":sources += [ROOT/"c"/(n+".c") for n in ('vga_clear','minimap_column','minimap_row','minimap_sample')]
    if cluster=="minimap_row":sources += [ROOT/'c/minimap_sample.c']
    if cluster=="minimap_column":sources += [ROOT/'c/minimap_row.c',ROOT/'c/minimap_sample.c']
    if cluster=="drawing_inputs":sources += [ROOT/'c/drawing_clip.c',ROOT/'c/drawing_dirty.c']
    if cluster=='drawing_plan':sources += [ROOT/'c'/(n+'.c') for n in ('drawing_inputs','drawing_clip','drawing_dirty','drawing_dispatch','drawing_source')]
    if cluster in ('drawing_render','terrain_drawing','terrain_stream','text_glyph','text_stream','background_drawing','retry_ui','menu_animation','menu_cache','menu_scroll'):
        if cluster in ('terrain_drawing','terrain_stream','text_glyph','text_stream','background_drawing','retry_ui','menu_animation','menu_cache','menu_scroll'):sources += [ROOT/'c/drawing_render.c']
        if cluster=='terrain_stream':sources += [ROOT/'c/terrain_drawing.c']
        sources += [ROOT/'c'/(n+'.c') for n in ('drawing_plan','drawing_inputs','drawing_clip','drawing_dirty','drawing_dispatch','drawing_source','aligned_opaque','aligned_masked','aligned_mask_effects','aligned_protected','aligned_read_mask','shifted_mask_effects','shifted_opaque','shifted_masked','shifted_protected','shifted_read_mask')]
    if cluster == "object_drawing_tick":sources += [ROOT/"c/object_animation.c"]
    if cluster in ("object_drawing", "object_drawing_tick"):
        sources += [ROOT/"c"/(n+".c") for n in (
            "drawing_render", "drawing_plan", "drawing_inputs", "drawing_clip",
            "drawing_dirty", "drawing_dispatch", "drawing_source",
            "aligned_opaque", "aligned_masked", "aligned_mask_effects",
            "aligned_protected", "aligned_read_mask", "shifted_mask_effects",
            "shifted_opaque", "shifted_masked", "shifted_protected",
            "shifted_read_mask")]
    if cluster in ("level_redraw", "level_initialize"):
        sources += [ROOT/"c"/(n+".c") for n in (
            "level_drawing", "vga_clear", "drawing_layout", "terrain_stream",
            "terrain_drawing", "object_graphics", "object_drawing",
            "drawing_render", "drawing_plan", "drawing_inputs", "drawing_clip",
            "drawing_dirty", "drawing_dispatch", "drawing_source",
            "aligned_opaque", "aligned_masked", "aligned_mask_effects",
            "aligned_protected", "aligned_read_mask", "shifted_mask_effects",
            "shifted_opaque", "shifted_masked", "shifted_protected",
            "shifted_read_mask", "special_setup", "resource_rle",
            "special_blit", "dat_load", "dat_files", "dat_cache",
            "dat_section", "dat_io", "dat")]
    if cluster == "level_initialize":
        sources += [ROOT/"c"/(n+".c") for n in (
            "level_header", "object_state_bus", "object_cells_bus",
            "steel_cells_bus", "object_coordinates_bus", "level_finish",
            "minimap_column", "minimap_row", "minimap_sample")]
    defines=["-DMUTATION="+str(mutation)] if cluster!="dat_section" else ["-DMUTATION=0","-DSECTION_MUTATION="+str(mutation)]
    if cluster=="pcspeaker_interrupt":defines=["-DMUTATION=0","-DPC_INTERRUPT_MUTATION="+str(mutation)]
    if cluster=="entity_interactions":defines=["-DMUTATION=0","-DENTITY_INTERACTIONS_MUTATION="+str(mutation)]
    if cluster=="entity_finish":defines=["-DMUTATION=0","-DENTITY_FINISH_MUTATION="+str(mutation)]
    if cluster=="entity_zero_state":defines=["-DMUTATION=0","-DENTITY_ZERO_STATE_MUTATION="+str(mutation)]
    if cluster in ("entity_state10","entity_state20","entity_state40","entity_state80","entity_state100","entity_state200","entity_state400","entity_late_states","entity_state800"):defines=["-DMUTATION=0","-D"+cluster.upper()+"_MUTATION="+str(mutation)]
    if cluster in ("entity_actions_basic","entity_actions_advanced","entity_action_map","entity_action_dispatch"):defines=["-DMUTATION=0","-D"+cluster.upper()+"_MUTATION="+str(mutation)]
    if cluster=="entity_batch":defines=["-DMUTATION=0","-DENTITY_BATCH_MUTATION="+str(mutation)]
    if cluster=="entity_action_sound":defines=["-DMUTATION=0","-DENTITY_ACTION_SOUND_MUTATION="+str(mutation)]
    if cluster=="entity_create":defines=["-DMUTATION=0","-DENTITY_CREATE_MUTATION="+str(mutation)]
    if cluster=="entity_update":defines=["-DMUTATION=0","-DENTITY_UPDATE_MUTATION="+str(mutation)]
    if cluster=="entity_state2":defines=["-DMUTATION=0","-DENTITY_STATE2_MUTATION="+str(mutation)]
    if cluster=="entity_state8":defines=["-DMUTATION=0","-DENTITY_STATE8_MUTATION="+str(mutation)]
    if cluster=="entity_pattern_bus":defines=["-DMUTATION=0","-DENTITY_PATTERN_BUS_MUTATION="+str(mutation)]
    if cluster=="entity_state4":defines=["-DMUTATION=0","-DENTITY_STATE4_MUTATION="+str(mutation)]
    if cluster=="entity_cadence":defines=["-DMUTATION=0","-DENTITY_CADENCE_MUTATION="+str(mutation)]
    if cluster=="pcspeaker_bus":defines=["-DMUTATION=0","-DEFFECT_BUS_MUTATION="+str(mutation)]
    if cluster=="pcspeaker_dispatch":defines=["-DMUTATION=0","-DPC_DISPATCH_MUTATION="+str(mutation)]
    if cluster=="entity_countdown":defines=["-DENTITY_COUNTDOWN_MUTATION="+str(mutation)]
    if cluster=="sound_interrupt":defines=["-DSOUND_INTERRUPT_MUTATION="+str(mutation)]
    if cluster=="sound_latches":defines=["-DSOUND_LATCH_MUTATION="+str(mutation)]
    if cluster=="generated_graphics":defines=["-DMUTATION=0","-DGENERATED_GRAPHICS_MUTATION="+str(mutation)]
    if cluster=="entity_stroke":defines=["-DMUTATION=0","-DSTROKE_MUTATION="+str(mutation)]
    if cluster=="keyboard_input":defines=["-DKEYBOARD_INPUT_MUTATION="+str(mutation),"-DKEYBOARD_PORT_MUTATION="+str(mutation),"-DPORT_IO_MUTATION=0","-DINPUT_POLL_MUTATION=0","-DINTERRUPT_SERVICE_MUTATION=0","-DDISPLAY_STATUS_MUTATION=0"]
    if cluster=="vector_restore":defines=["-DVECTOR_RESTORE_MUTATION="+str(mutation)]
    if cluster=="timer_restore":defines=["-DTIMER_RESTORE_MUTATION="+str(mutation)]
    if cluster=="fatal_cleanup":defines=["-DFATAL_CLEANUP_MUTATION="+str(mutation)]
    if cluster=="file_error":defines=["-DFILE_ERROR_MUTATION="+str(mutation)]
    if cluster=="resource_raw_full":defines=["-DMUTATION=0","-DRAW_BUS_MUTATION="+str(mutation),"-DRAW_FULL_MUTATION="+str(mutation)]
    if cluster=="display_status":defines=["-DDISPLAY_STATUS_MUTATION="+str(mutation)]
    if cluster=="display_start":defines=["-DDISPLAY_START_MUTATION="+str(mutation)]
    if cluster=="display_setup":defines=["-DDISPLAY_SETUP_MUTATION="+str(mutation)]
    if cluster=="display_pages":defines=["-DDISPLAY_PAGES_MUTATION="+str(mutation)]
    if cluster=="retry_ui":defines=["-DRETRY_UI_MUTATION="+str(mutation)]
    if cluster=="retry_input":defines=["-DRETRY_INPUT_MUTATION="+str(mutation)]
    if cluster=="palette_transition":defines=["-DPALETTE_TRANSITION_MUTATION="+str(mutation)]
    if cluster=="palette_row_select":defines=["-DPALETTE_ROW_SELECT_MUTATION="+str(mutation)]
    if cluster=="palette_ports":defines=["-DPALETTE_PORTS_MUTATION="+str(mutation)]
    if cluster=="palette_rows":defines=["-DPALETTE_ROWS_MUTATION="+str(mutation)]
    if cluster=="palette_channels":defines=["-DPALETTE_CHANNELS_MUTATION="+str(mutation)]
    if cluster=="main_menu":defines=["-DMAIN_MENU_MUTATION="+str(mutation)]
    if cluster=="menu_scroll":defines=["-DMENU_SCROLL_MUTATION="+str(mutation)]
    if cluster=="menu_cache":defines=["-DMENU_CACHE_MUTATION="+str(mutation)]
    if cluster=="menu_animation":defines=["-DMENU_ANIMATION_MUTATION="+str(mutation)]
    if cluster=="background_drawing":defines=["-DBACKGROUND_DRAWING_MUTATION="+str(mutation)]
    if cluster=="text_glyph":defines=["-DTEXT_GLYPH_MUTATION="+str(mutation)]
    if cluster=="text_stream":defines=["-DTEXT_STREAM_MUTATION="+str(mutation)]
    if cluster=="video_restore":defines=["-DVIDEO_RESTORE_MUTATION="+str(mutation)]
    if cluster=="cache_allocation":defines=["-DCACHE_ALLOCATION_MUTATION="+str(mutation)]
    if cluster=="dat_files":defines=["-DMUTATION=0","-DFILE_MUTATION="+str(mutation)]
    if cluster=="dat_load":defines=["-DMUTATION=0","-DLOAD_MUTATION="+str(mutation)]
    if cluster=="special_setup":defines=["-DMUTATION=0","-DSETUP_MUTATION="+str(mutation)]
    if cluster=="entity_sprite_aligned":defines=["-DENTITY_SPRITE_ALIGNED_MUTATION="+str(mutation)]
    if cluster=="entity_sprite_shifted":defines=["-DENTITY_SPRITE_SHIFTED_MUTATION="+str(mutation),"-DENTITY_SPRITE_PLANES_MUTATION=0"]
    if cluster=="entity_sprite_planes":defines=["-DENTITY_SPRITE_SHIFTED_MUTATION=0","-DENTITY_SPRITE_PLANES_MUTATION="+str(mutation)]
    if cluster=="entity_sprite_wide":defines=["-DENTITY_SPRITE_WIDE_MUTATION="+str(mutation)]
    if cluster=="entity_sprite_banks":defines=["-DENTITY_SPRITE_BANKS_MUTATION="+str(mutation)]
    if cluster=="palette_timer":
        sources=[ROOT/"c/palette_ports.c"]
        defines=["-DPALETTE_PORTS_MUTATION=0","-DPALETTE_TIMER_MUTATION="+str(mutation)]
    if cluster in ("game_timer","menu_timer","timer_install"):
        sources=[ROOT/("c/"+name+".c") for name in ("timer_tail","input_poll","ui_commands","view_visibility","vga_mirrors","port_io","interrupt_service","palette_ports","fixed_pattern_update","fixed_pattern_copy","fixed_pattern_draw")]
        defines=["-D"+name+"=0" for name in ("TIMER_TAIL_MUTATION","INPUT_POLL_MUTATION","UI_COMMANDS_MUTATION","VIEW_VISIBILITY_MUTATION","VGA_MIRRORS_MUTATION","PORT_IO_MUTATION","INTERRUPT_SERVICE_MUTATION","PALETTE_PORTS_MUTATION","PALETTE_TIMER_MUTATION","FIXED_PATTERN_UPDATE_MUTATION","FIXED_PATTERN_COPY_MUTATION","FIXED_PATTERN_DRAW_MUTATION")]+["-DGAME_TIMER_MUTATION="+str(mutation if cluster=="game_timer" else 0),"-DMENU_TIMER_MUTATION="+str(mutation if cluster=="menu_timer" else 0),"-DTIMER_INSTALL_MUTATION="+str(mutation if cluster=="timer_install" else 0)]
    if cluster=="timer_tail":
        sources=[ROOT/("c/"+name+".c") for name in ("timer_tail","input_poll","ui_commands","view_visibility","vga_mirrors","port_io","interrupt_service","palette_ports","fixed_pattern_update","fixed_pattern_copy","fixed_pattern_draw")]
        defines=["-D"+name+"=0" for name in ("INPUT_POLL_MUTATION","UI_COMMANDS_MUTATION","VIEW_VISIBILITY_MUTATION","VGA_MIRRORS_MUTATION","PORT_IO_MUTATION","INTERRUPT_SERVICE_MUTATION")]+["-DTIMER_TAIL_MUTATION="+str(mutation)]
    if cluster=="ui_commands":
        sources=[ROOT/"c/ui_commands.c",ROOT/"c/view_visibility.c",ROOT/"c/interrupt_service.c"]
        defines=["-DVIEW_VISIBILITY_MUTATION=0","-DINTERRUPT_SERVICE_MUTATION=0","-DUI_COMMANDS_MUTATION="+str(mutation)]
    if cluster=="input_poll":
        sources=[ROOT/"c/input_poll.c",ROOT/"c/port_io.c",ROOT/"c/interrupt_service.c"]
        defines=["-DPORT_IO_MUTATION=0","-DINPUT_POLL_MUTATION="+str(mutation),"-DINTERRUPT_SERVICE_MUTATION="+str(mutation if mutation in (1,2,3) else 0)]
    if cluster=="port_io":defines=["-DPORT_IO_MUTATION="+str(mutation)]
    if cluster=="mouse_irq_bridge":defines=["-DVGA_MIRRORS_MUTATION=0","-DMOUSE_IRQ_BRIDGE_MUTATION="+str(mutation)]
    if cluster=="vga_mirrors":defines=["-DVGA_MIRRORS_MUTATION="+str(mutation)]
    if cluster=="fixed_pattern_copy":defines=["-DMUTATION=0","-DFIXED_PATTERN_COPY_MUTATION="+str(mutation)]
    if cluster=="fixed_pattern_draw":defines=["-DMUTATION=0","-DFIXED_PATTERN_DRAW_MUTATION="+str(mutation)]
    if cluster=="fixed_pattern_update":defines=["-DMUTATION=0","-DFIXED_PATTERN_UPDATE_MUTATION="+str(mutation)]
    if cluster=="main_resources":defines=["-DMUTATION=0","-DMAIN_RESOURCES_MUTATION="+str(mutation)]
    if cluster=="fixed_word_banks":defines=["-DMUTATION=0","-DFIXED_WORD_BANKS_MUTATION="+str(mutation)]
    if cluster=="vga_plane_copy":defines=["-DVGA_PLANE_COPY_MUTATION="+str(mutation)]
    if cluster=="sprite_wide_banks":defines=["-DSPRITE_WIDE_BANKS_MUTATION="+str(mutation)]
    if cluster=="sprite_shift_banks":defines=["-DSPRITE_SHIFT_BANKS_MUTATION="+str(mutation)]
    if cluster=="sprite_bank":defines=["-DSPRITE_BANK_MUTATION="+str(mutation)]
    if cluster=="entity_drawing":defines=["-D"+name+"=0" for name in ("ENTITY_MINIMAP_MUTATION","ENTITY_DIRTY_MUTATION","ENTITY_POINTS_MUTATION","ENTITY_SPRITE_DISPATCH_MUTATION","ENTITY_SPRITE_ALIGNED_MUTATION","ENTITY_SPRITE_SHIFTED_MUTATION","ENTITY_SPRITE_PLANES_MUTATION","ENTITY_SPRITE_WIDE_MUTATION","ENTITY_STRIP_MUTATION","DECIMAL_FIELD_MUTATION")]+["-DENTITY_DRAWING_MUTATION="+str(mutation)]
    if cluster=="entity_sprite_dispatch":defines=["-DENTITY_SPRITE_ALIGNED_MUTATION=0","-DENTITY_SPRITE_SHIFTED_MUTATION=0","-DENTITY_SPRITE_PLANES_MUTATION=0","-DENTITY_SPRITE_WIDE_MUTATION=0","-DENTITY_STRIP_MUTATION=0","-DENTITY_SPRITE_DISPATCH_MUTATION="+str(mutation)]
    if cluster=="entity_points":defines=["-DENTITY_POINTS_MUTATION="+str(mutation)]
    if cluster=="entity_strip":defines=["-DENTITY_STRIP_MUTATION="+str(mutation)]
    if cluster=="entity_minimap":defines=["-DENTITY_MINIMAP_MUTATION="+str(mutation)]
    if cluster=="view_visibility":defines=["-DVIEW_VISIBILITY_MUTATION="+str(mutation)]
    if cluster=="entity_dirty":defines=["-DVIEW_VISIBILITY_MUTATION=0","-DENTITY_DIRTY_MUTATION="+str(mutation)]
    if cluster=="status_copy":defines=["-DSTATUS_COPY_MUTATION="+str(mutation)]
    if cluster=="status_initialize":defines=["-DSTATUS_COPY_MUTATION=0","-DSTATUS_COUNT_MUTATION=0","-DDECIMAL_FIELD_MUTATION=0","-DSTATUS_ICONS_MUTATION=0","-DSTATUS_INITIALIZE_MUTATION="+str(mutation)]
    if cluster=="object_animation":defines=["-DOBJECT_ANIMATION_MUTATION="+str(mutation)]
    if cluster=="status_display":defines=["-DSTATUS_TEXT_MUTATION=0","-DSTATUS_GLYPH_MUTATION=0","-DSTATUS_COUNT_MUTATION=0","-DSTATUS_ICONS_MUTATION=0","-DSTATUS_DISPLAY_MUTATION="+str(mutation)]
    if cluster=="status_display_full":defines=["-DSTATUS_TEXT_MUTATION=0","-DSTATUS_GLYPH_MUTATION=0","-DSTATUS_COUNT_MUTATION=0","-DSTATUS_ICONS_MUTATION=0","-DSTATUS_DISPLAY_MUTATION=0","-DMINIMAP_STATUS_MUTATION=0","-DMINIMAP_VIEWPORT_MUTATION=0","-DCOLUMN_MUTATION=0","-DROW_MUTATION=0","-DSAMPLE_MUTATION=0","-DSTATUS_DISPLAY_FULL_MUTATION="+str(mutation)]
    if cluster=="status_text":defines=["-DSTATUS_GLYPH_MUTATION=0","-DSTATUS_TEXT_MUTATION="+str(mutation)]
    if cluster=="status_count":defines=["-DSTATUS_COUNT_MUTATION="+str(mutation)]
    if cluster=="status_glyph":defines=["-DSTATUS_GLYPH_MUTATION="+str(mutation)]
    if cluster=="status_icons":defines=["-DSTATUS_ICONS_MUTATION="+str(mutation)]
    if cluster=="minimap_viewport":defines=["-DMINIMAP_VIEWPORT_MUTATION="+str(mutation)]
    if cluster=="minimap_status":defines=["-DMINIMAP_VIEWPORT_MUTATION=0","-DCOLUMN_MUTATION=0","-DROW_MUTATION=0","-DSAMPLE_MUTATION=0","-DMINIMAP_STATUS_MUTATION="+str(mutation)]
    if cluster=="decimal_field":defines=["-DDECIMAL_FIELD_MUTATION="+str(mutation)]
    if cluster=="entity_select":defines=["-DDECIMAL_FIELD_MUTATION=0","-DENTITY_SELECT_MUTATION="+str(mutation)]
    if cluster=="decimal_digits":defines=["-DMUTATION=0","-DDECIMAL_MUTATION="+str(mutation)]
    if cluster=="resource_select":defines=["-DMUTATION=0","-DDECIMAL_MUTATION=0","-DSELECT_MUTATION="+str(mutation)]
    if cluster=="resource_select_full":defines=["-DMUTATION=0","-DSELECT_RETURN_MUTATION="+str(mutation),"-DSELECT_FULL_MUTATION="+str(mutation)]
    if cluster=="object_graphics":defines=["-DMUTATION=0","-DOBJECT_MUTATION="+str(mutation)]
    if cluster=="object_coordinates":defines=["-DMUTATION=0","-DCOORD_MUTATION="+str(mutation)]
    if cluster=="object_cells":defines=["-DMUTATION=0","-DCELL_MUTATION="+str(mutation)]
    if cluster=="steel_cells":defines=["-DMUTATION=0","-DSTEEL_MUTATION="+str(mutation)]
    if cluster=="object_state":defines=["-DMUTATION=0","-DSTATE_MUTATION="+str(mutation)]
    if cluster=="vga_clear":defines=["-DCLEAR_MUTATION="+str(mutation)]
    if cluster=="drawing_layout":defines=["-DLAYOUT_MUTATION="+str(mutation)]
    if cluster=="level_drawing":defines=["-DDRAWING_MUTATION="+str(mutation)]
    if cluster=="level_header":defines=["-DLEVEL_HEADER_MUTATION="+str(mutation)]
    if cluster=="level_finish":defines=["-DLEVEL_FINISH_MUTATION="+str(mutation)]
    if cluster=="level_initialize":defines=["-DMUTATION=0","-DLEVEL_INITIALIZE_MUTATION="+str(mutation)]
    if cluster=="minimap_sample":defines=["-DSAMPLE_MUTATION="+str(mutation)]
    if cluster=="minimap_row":defines=["-DROW_MUTATION="+str(mutation)]
    if cluster=="minimap_column":defines=["-DCOLUMN_MUTATION="+str(mutation)]
    if cluster=="drawing_clip":defines=["-DCLIP_MUTATION="+str(mutation)]
    if cluster=="drawing_dirty":defines=["-DDIRTY_MUTATION="+str(mutation)]
    if cluster=="drawing_inputs":defines=["-DINPUTS_MUTATION="+str(mutation)]
    if cluster=='drawing_dispatch':defines=['-DDISPATCH_MUTATION='+str(mutation)]
    if cluster=='drawing_source':defines=['-DSOURCE_MUTATION='+str(mutation)]
    if cluster=='drawing_plan':defines=['-DPLAN_MUTATION='+str(mutation)]
    if cluster=='aligned_opaque':defines=['-DOPAQUE_MUTATION='+str(mutation)]
    if cluster=='aligned_masked':defines=['-DMASKED_MUTATION='+str(mutation)]
    if cluster=='aligned_mask_effects':defines=['-DEFFECT_MUTATION='+str(mutation)]
    if cluster=='aligned_protected':defines=['-DPROTECTED_MUTATION='+str(mutation)]
    if cluster=='aligned_read_mask':defines=['-DREAD_MASK_MUTATION='+str(mutation)]
    if cluster=='shifted_mask_effects':defines=['-DSHIFTED_EFFECT_MUTATION='+str(mutation)]
    if cluster=='shifted_opaque':defines=['-DSHIFTED_OPAQUE_MUTATION='+str(mutation)]
    if cluster=='shifted_masked':defines=['-DSHIFTED_MASKED_MUTATION='+str(mutation)]
    if cluster=='shifted_protected':defines=['-DSHIFTED_PROTECTED_MUTATION='+str(mutation)]
    if cluster=='shifted_read_mask':defines=['-DSHIFTED_READ_MASK_MUTATION='+str(mutation)]
    if cluster=='drawing_render':defines=['-DRENDER_MUTATION='+str(mutation)]
    if cluster=='terrain_drawing':defines=['-DMUTATION=0','-DTERRAIN_MUTATION='+str(mutation)]
    if cluster=='terrain_stream':defines=['-DMUTATION=0','-DTERRAIN_STREAM_MUTATION='+str(mutation)]
    if cluster=='object_drawing_tick':defines=['-DMUTATION=0','-DOBJECT_ANIMATION_MUTATION=0','-DOBJECT_DRAWING_TICK_MUTATION='+str(mutation)]
    if cluster=='object_drawing':defines=['-DMUTATION=0','-DOBJECT_DRAWING_MUTATION='+str(mutation)]
    if cluster=='level_redraw':defines=['-DMUTATION=0','-DLEVEL_REDRAW_MUTATION='+str(mutation)]
    run_bounded([
        compiler(), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-shared", *defines,
        "-I", str(ROOT / "c"), *map(str,sources),
        "-o", str(out),
    ], check=True, timeout=60, memory_mib=256)
    return out

if __name__ == "__main__":
    print(build())

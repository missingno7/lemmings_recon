"""Run selected native differential suites, or the explicit full --all campaign."""
import argparse
import sys
import time
from pathlib import Path
from typing import NamedTuple

from bounded_process import run_bounded

ROOT = Path(__file__).resolve().parents[1]


class Suite(NamedTuple):
    name: str
    timeout: int
    memory_mib: int


# Preserve the complete campaign's order and existing process/tree limits.
SUITES = (
    Suite('host_vga', 210, 512),
    Suite('host_journey', 2400, 768),
    Suite('level_result', 2100, 512),
    Suite('game_initialize_prefix', 180, 384),
    Suite('game_initialize', 420, 384),
    Suite('game_prepare', 960, 384),
    Suite('video_probe', 660, 384),
    Suite('level_start', 660, 384),
    Suite('level_briefing', 960, 384),
    Suite('level_preview', 630, 384),
    Suite('main_menu', 1260, 384),
    Suite('menu_scroll', 600, 384),
    Suite('menu_cache', 270, 384),
    Suite('menu_animation', 600, 384),
    Suite('keyboard_input', 420, 384),
    Suite('timer_install', 420, 384),
    Suite('menu_timer', 420, 384),
    Suite('game_timer', 420, 384),
    Suite('palette_timer', 420, 384),
    Suite('timer_tail', 420, 384),
    Suite('ui_commands', 420, 384),
    Suite('input_poll', 420, 384),
    Suite('port_io', 420, 384),
    Suite('mouse_irq_bridge', 420, 384),
    Suite('vga_mirrors', 420, 384),
    Suite('fixed_pattern_copy', 420, 384),
    Suite('fixed_pattern_draw', 420, 384),
    Suite('fixed_pattern_update', 420, 384),
    Suite('main_resources', 1500, 512),
    Suite('fixed_word_banks', 420, 384),
    Suite('vga_plane_copy', 420, 384),
    Suite('entity_sprite_banks', 900, 512),
    Suite('sprite_wide_banks', 420, 384),
    Suite('sprite_shift_banks', 420, 384),
    Suite('sprite_bank', 360, 384),
    Suite('entity_drawing', 420, 384),
    Suite('entity_sprite_dispatch', 420, 384),
    Suite('entity_sprite_planes', 420, 384),
    Suite('entity_sprite_wide', 300, 384),
    Suite('entity_sprite_aligned', 240, 384),
    Suite('entity_sprite_shifted', 360, 384),
    Suite('entity_points', 300, 384),
    Suite('entity_strip', 180, 384),
    Suite('entity_minimap', 180, 384),
    Suite('view_visibility', 180, 384),
    Suite('entity_dirty', 240, 384),
    Suite('status_copy', 180, 384),
    Suite('status_initialize', 240, 384),
    Suite('display_status', 180, 384),
    Suite('display_start', 180, 384),
    Suite('display_setup', 180, 384),
    Suite('text_glyph', 180, 384),
    Suite('text_stream', 180, 384),
    Suite('display_pages', 180, 384),
    Suite('background_drawing', 210, 384),
    Suite('palette_channels', 360, 384),
    Suite('palette_rows', 660, 384),
    Suite('palette_ports', 390, 384),
    Suite('palette_row_select', 720, 384),
    Suite('palette_transition', 1440, 384),
    Suite('retry_input', 180, 384),
    Suite('cache_allocation', 180, 384),
    Suite('video_restore', 180, 384),
    Suite('vector_restore', 180, 384),
    Suite('timer_restore', 180, 384),
    Suite('fatal_cleanup', 180, 384),
    Suite('file_error', 180, 384),
    Suite('resource_raw_full', 180, 384),
    Suite('decimal_digits_c', 120, 512),
    Suite('decimal_field', 240, 384),
    Suite('entity_select', 240, 384),
    Suite('entity_select_actions', 240, 384),
    Suite('minimap_viewport', 240, 384),
    Suite('minimap_status', 240, 384),
    Suite('status_icons', 240, 384),
    Suite('status_count', 240, 384),
    Suite('status_glyph', 240, 384),
    Suite('status_text', 240, 384),
    Suite('status_display', 240, 384),
    Suite('status_display_full', 240, 384),
    Suite('object_animation', 180, 384),
    Suite('object_drawing_tick', 360, 512),
    Suite('checksum', 120, 512),
    Suite('pcspeaker', 120, 512),
    Suite('pcspeaker_bus', 180, 384),
    Suite('pcspeaker_dispatch', 180, 384),
    Suite('pcspeaker_interrupt', 180, 384),
    Suite('entity_interactions', 180, 384),
    Suite('entity_finish', 180, 384),
    Suite('entity_zero_state', 180, 384),
    Suite('entity_state4', 180, 384),
    Suite('entity_cadence', 180, 384),
    Suite('entity_pattern_bus', 180, 384),
    Suite('entity_state8', 180, 384),
    Suite('entity_state2', 180, 384),
    Suite('entity_state10', 180, 384),
    Suite('entity_state20', 180, 384),
    Suite('entity_state40', 180, 384),
    Suite('entity_state80', 180, 384),
    Suite('entity_state100', 180, 384),
    Suite('entity_state200', 180, 384),
    Suite('entity_state400', 180, 384),
    Suite('entity_late_states', 180, 384),
    Suite('entity_state800', 180, 384),
    Suite('entity_update', 240, 384),
    Suite('entity_create', 180, 384),
    Suite('entity_action_sound', 180, 384),
    Suite('entity_actions_basic', 180, 384),
    Suite('entity_actions_advanced', 240, 384),
    Suite('entity_action_map', 240, 384),
    Suite('entity_action_dispatch', 240, 384),
    Suite('entity_batch', 240, 384),
    Suite('dat', 120, 512),
    Suite('dat_io_c', 120, 512),
    Suite('dat_section', 120, 512),
    Suite('dat_cache', 120, 512),
    Suite('dat_files', 120, 512),
    Suite('dat_load', 120, 512),
    Suite('resource_raw', 120, 512),
    Suite('resource_rle', 120, 512),
    Suite('special_blit', 120, 512),
    Suite('special_setup', 120, 512),
    Suite('resource_select', 120, 512),
    Suite('resource_select_full', 6600, 384),
    Suite('object_graphics', 120, 512),
    Suite('object_coordinates', 120, 512),
    Suite('object_cells', 120, 512),
    Suite('steel_cells', 120, 512),
    Suite('object_state', 120, 512),
    Suite('object_cells_bus', 420, 512),
    Suite('steel_cells_bus', 420, 512),
    Suite('object_coordinates_bus', 420, 512),
    Suite('object_state_bus', 420, 512),
    Suite('vga_clear', 120, 512),
    Suite('drawing_layout', 120, 512),
    Suite('level_drawing', 120, 512),
    Suite('level_header', 120, 512),
    Suite('minimap_sample', 120, 512),
    Suite('minimap_row', 120, 512),
    Suite('minimap_column', 120, 512),
    Suite('level_finish', 420, 512),
    Suite('level_initialize', 7260, 512),
    Suite('drawing_clip', 120, 512),
    Suite('drawing_dirty', 120, 512),
    Suite('drawing_inputs', 120, 512),
    Suite('drawing_dispatch', 120, 512),
    Suite('drawing_source', 120, 512),
    Suite('drawing_plan', 120, 512),
    Suite('aligned_opaque', 180, 512),
    Suite('drawing_render', 180, 512),
    Suite('aligned_masked', 180, 512),
    Suite('drawing_masked_render', 180, 512),
    Suite('aligned_protected', 180, 512),
    Suite('aligned_mask_effects', 180, 512),
    Suite('aligned_read_mask', 180, 512),
    Suite('drawing_aligned_render', 180, 512),
    Suite('shifted_mask_effects', 180, 512),
    Suite('drawing_shifted_render', 180, 512),
    Suite('shifted_opaque', 180, 512),
    Suite('shifted_masked', 180, 512),
    Suite('shifted_protected', 180, 512),
    Suite('shifted_read_mask', 180, 512),
    Suite('drawing_bitmap', 180, 512),
    Suite('terrain_inputs', 180, 512),
    Suite('terrain_drawing', 180, 512),
    Suite('terrain_commands', 180, 512),
    Suite('object_drawing', 360, 512),
    Suite('level_redraw', 15660, 512),
    Suite('terrain_stream', 14460, 512),
    Suite('entity_pattern', 180, 384),
    Suite('entity_pixel', 180, 384),
    Suite('entity_pixel_bus', 180, 384),
    Suite('entity_vga', 180, 384),
    Suite('entity_stroke', 180, 384),
    Suite('mask_generators', 180, 384),
    Suite('generated_graphics', 180, 384),
    Suite('entity_mask', 180, 384),
    Suite('entity_mask_rows', 180, 384),
    Suite('coordinate_pixel', 180, 384),
    Suite('sound_latches', 180, 384),
    Suite('entity_countdown', 180, 384),
    Suite('game_transition', 240, 384),
    Suite('view_scroll', 180, 384),
    Suite('game_frame', 600, 512),
    Suite('game_session', 1800, 768),
    Suite('game_loop', 3600, 768),
    Suite('resource_retry', 300, 512),
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suites', nargs='*', help='Suite names, e.g. drawing_clip display_status')
    parser.add_argument('--all', action='store_true', help='Run the complete acceptance campaign')
    parser.add_argument('--list', action='store_true', help='List available suites and their limits')
    parser.add_argument('--plan', action='store_true', help='Print the selected schedule without executing it')
    args = parser.parse_args(argv)
    registry = {suite.name: suite for suite in SUITES}
    if args.list:
        if args.suites or args.all or args.plan:
            parser.error('--list cannot be combined with a selection or --plan')
        selected = SUITES
    else:
        if args.all and args.suites:
            parser.error('Choose suite names or --all, not both')
        if not args.all and not args.suites:
            parser.error('Select suite names or --all; --list shows the available suites')
        unknown = sorted(set(args.suites) - registry.keys())
        if unknown:
            parser.error('Unknown suites: ' + ', '.join(unknown))
        selected = SUITES if args.all else tuple(registry[name] for name in dict.fromkeys(args.suites))
    if args.list or args.plan:
        for suite in selected:
            print(f'{suite.name}: timeout={suite.timeout}s process_commit={suite.memory_mib}MiB')
        return 0
    # Validate the entire selection before starting the first native worker.
    for suite in selected:
        if not (ROOT / 'tests' / (suite.name + '.py')).is_file():
            parser.error('Missing suite file: ' + suite.name)
    started = time.perf_counter()
    for suite in selected:
        print(f'RUN {suite.name}: timeout={suite.timeout}s process_commit={suite.memory_mib}MiB', flush=True)
        run_bounded([sys.executable, str(ROOT / 'tests' / (suite.name + '.py'))],
                    cwd=ROOT, timeout=suite.timeout, memory_mib=suite.memory_mib, check=True)
        print('PASS suite ' + suite.name, flush=True)
    print(f'PASS {len(selected)} selected suites in {time.perf_counter()-started:.2f}s', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

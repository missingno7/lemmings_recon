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
    report_path: str
    accounting_role: str


# All receipts are required for aggregate acceptance. Roles describe evidence,
# never additive byte credit: main/component sites are unioned in their view;
# composition and protected receipts do not create canonical instruction bytes.
# Preserve the complete campaign's order and existing process/tree limits.
SUITES = (
    Suite('protection', 1260, 768, 'protection-differential.json', 'protected'),
    Suite('startup', 1500, 768, 'startup-differential.json', 'instruction'),
    Suite('sound_driver_init', 600, 512, 'sound-driver-init-differential.json', 'instruction'),
    Suite('host_vga', 210, 512, 'host-vga.json', 'composition'),
    Suite('host_journey', 2400, 768, 'host-journey.json', 'composition'),
    Suite('level_result', 2100, 512, 'level-result-differential.json', 'instruction'),
    Suite('game_initialize_prefix', 180, 384, 'game-initialize-prefix-differential.json', 'instruction'),
    Suite('game_initialize', 420, 384, 'game-initialize-differential.json', 'instruction'),
    Suite('game_prepare', 960, 384, 'game-prepare-differential.json', 'instruction'),
    Suite('video_probe', 660, 384, 'video-probe-differential.json', 'instruction'),
    Suite('level_start', 660, 384, 'level-start-differential.json', 'instruction'),
    Suite('level_briefing', 960, 384, 'level-briefing-differential.json', 'instruction'),
    Suite('level_preview', 630, 384, 'level-preview-differential.json', 'instruction'),
    Suite('main_menu', 1260, 384, 'main-menu-differential.json', 'instruction'),
    Suite('menu_scroll', 600, 384, 'menu-scroll-differential.json', 'instruction'),
    Suite('menu_cache', 270, 384, 'menu-cache-differential.json', 'instruction'),
    Suite('menu_animation', 600, 384, 'menu-animation-differential.json', 'instruction'),
    Suite('keyboard_input', 420, 384, 'keyboard-input-differential.json', 'instruction'),
    Suite('timer_install', 420, 384, 'timer-install-differential.json', 'instruction'),
    Suite('menu_timer', 420, 384, 'menu-timer-differential.json', 'instruction'),
    Suite('game_timer', 420, 384, 'game-timer-differential.json', 'instruction'),
    Suite('palette_timer', 420, 384, 'palette-timer-differential.json', 'instruction'),
    Suite('timer_tail', 420, 384, 'timer-tail-differential.json', 'instruction'),
    Suite('ui_commands', 420, 384, 'ui-commands-differential.json', 'instruction'),
    Suite('input_poll', 420, 384, 'input-poll-differential.json', 'instruction'),
    Suite('port_io', 420, 384, 'port-io-differential.json', 'instruction'),
    Suite('mouse_irq_bridge', 420, 384, 'mouse-irq-bridge-differential.json', 'instruction'),
    Suite('vga_mirrors', 420, 384, 'vga-mirrors-differential.json', 'instruction'),
    Suite('fixed_pattern_copy', 420, 384, 'fixed-pattern-copy-differential.json', 'instruction'),
    Suite('fixed_pattern_draw', 420, 384, 'fixed-pattern-draw-differential.json', 'instruction'),
    Suite('fixed_pattern_update', 420, 384, 'fixed-pattern-update-differential.json', 'instruction'),
    Suite('main_resources', 1500, 512, 'main-resources-differential.json', 'instruction'),
    Suite('fixed_word_banks', 420, 384, 'fixed-word-banks-differential.json', 'instruction'),
    Suite('vga_plane_copy', 420, 384, 'vga-plane-copy-differential.json', 'instruction'),
    Suite('entity_sprite_banks', 900, 512, 'entity-sprite-banks-differential.json', 'instruction'),
    Suite('sprite_wide_banks', 420, 384, 'sprite-wide-banks-differential.json', 'instruction'),
    Suite('sprite_shift_banks', 420, 384, 'sprite-shift-banks-differential.json', 'instruction'),
    Suite('sprite_bank', 360, 384, 'sprite-bank-differential.json', 'instruction'),
    Suite('entity_drawing', 420, 384, 'entity-drawing-differential.json', 'instruction'),
    Suite('entity_sprite_dispatch', 420, 384, 'entity-sprite-dispatch-differential.json', 'instruction'),
    Suite('entity_sprite_planes', 420, 384, 'entity-sprite-planes-differential.json', 'instruction'),
    Suite('entity_sprite_wide', 300, 384, 'entity-sprite-wide-differential.json', 'instruction'),
    Suite('entity_sprite_aligned', 240, 384, 'entity-sprite-aligned-differential.json', 'instruction'),
    Suite('entity_sprite_shifted', 360, 384, 'entity-sprite-shifted-differential.json', 'instruction'),
    Suite('entity_points', 300, 384, 'entity-points-differential.json', 'instruction'),
    Suite('entity_strip', 180, 384, 'entity-strip-differential.json', 'instruction'),
    Suite('entity_minimap', 180, 384, 'entity-minimap-differential.json', 'instruction'),
    Suite('view_visibility', 180, 384, 'view-visibility-differential.json', 'instruction'),
    Suite('entity_dirty', 240, 384, 'entity-dirty-differential.json', 'instruction'),
    Suite('status_copy', 180, 384, 'status-copy-differential.json', 'instruction'),
    Suite('status_initialize', 240, 384, 'status-initialize-differential.json', 'instruction'),
    Suite('display_status', 180, 384, 'display-status-differential.json', 'instruction'),
    Suite('display_start', 180, 384, 'display-start-differential.json', 'instruction'),
    Suite('display_setup', 180, 384, 'display-setup-differential.json', 'instruction'),
    Suite('text_glyph', 180, 384, 'text-glyph-differential.json', 'instruction'),
    Suite('text_stream', 180, 384, 'text-stream-differential.json', 'instruction'),
    Suite('display_pages', 180, 384, 'display-pages-differential.json', 'instruction'),
    Suite('background_drawing', 210, 384, 'background-drawing-differential.json', 'instruction'),
    Suite('palette_channels', 360, 384, 'palette-channels-differential.json', 'instruction'),
    Suite('palette_rows', 660, 384, 'palette-rows-differential.json', 'instruction'),
    Suite('palette_ports', 390, 384, 'palette-ports-differential.json', 'instruction'),
    Suite('palette_row_select', 720, 384, 'palette-row-select-differential.json', 'instruction'),
    Suite('palette_transition', 1440, 384, 'palette-transition-differential.json', 'instruction'),
    Suite('retry_input', 180, 384, 'retry-input-differential.json', 'instruction'),
    Suite('cache_allocation', 180, 384, 'cache-allocation-differential.json', 'instruction'),
    Suite('video_restore', 180, 384, 'video-restore-differential.json', 'instruction'),
    Suite('vector_restore', 180, 384, 'vector-restore-differential.json', 'instruction'),
    Suite('timer_restore', 180, 384, 'timer-restore-differential.json', 'instruction'),
    Suite('fatal_cleanup', 180, 384, 'fatal-cleanup-differential.json', 'instruction'),
    Suite('file_error', 180, 384, 'file-error-differential.json', 'instruction'),
    Suite('resource_raw_full', 180, 384, 'resource-raw-full-differential.json', 'instruction'),
    Suite('decimal_digits_c', 120, 512, 'decimal-digits-c-differential.json', 'instruction'),
    Suite('decimal_field', 240, 384, 'decimal-field-differential.json', 'instruction'),
    Suite('entity_select', 240, 384, 'entity-select-differential.json', 'instruction'),
    Suite('entity_select_actions', 240, 384, 'entity-select-actions-differential.json', 'composition'),
    Suite('minimap_viewport', 240, 384, 'minimap-viewport-differential.json', 'instruction'),
    Suite('minimap_status', 240, 384, 'minimap-status-differential.json', 'instruction'),
    Suite('status_icons', 240, 384, 'status-icons-differential.json', 'instruction'),
    Suite('status_count', 240, 384, 'status-count-differential.json', 'instruction'),
    Suite('status_glyph', 240, 384, 'status-glyph-differential.json', 'instruction'),
    Suite('status_text', 240, 384, 'status-text-differential.json', 'instruction'),
    Suite('status_display', 240, 384, 'status-display-differential.json', 'instruction'),
    Suite('status_display_full', 240, 384, 'status-display-full-differential.json', 'instruction'),
    Suite('object_animation', 180, 384, 'object-animation-differential.json', 'instruction'),
    Suite('object_drawing_tick', 360, 512, 'object-drawing-tick-differential.json', 'instruction'),
    Suite('checksum', 120, 512, 'differential.json', 'instruction'),
    Suite('pcspeaker', 120, 512, 'pcspeaker-differential.json', 'component'),
    Suite('pcspeaker_bus', 180, 384, 'pcspeaker-bus-differential.json', 'component'),
    Suite('pcspeaker_dispatch', 180, 384, 'pcspeaker-dispatch-differential.json', 'component'),
    Suite('pcspeaker_interrupt', 180, 384, 'pcspeaker-interrupt-differential.json', 'component'),
    Suite('entity_interactions', 180, 384, 'entity-interactions-differential.json', 'instruction'),
    Suite('entity_finish', 180, 384, 'entity-finish-differential.json', 'instruction'),
    Suite('entity_zero_state', 180, 384, 'entity-zero-state-differential.json', 'instruction'),
    Suite('entity_state4', 180, 384, 'entity-state4-differential.json', 'instruction'),
    Suite('entity_cadence', 180, 384, 'entity-cadence-differential.json', 'instruction'),
    Suite('entity_pattern_bus', 180, 384, 'entity-pattern-bus-differential.json', 'instruction'),
    Suite('entity_state8', 180, 384, 'entity-state8-differential.json', 'instruction'),
    Suite('entity_state2', 180, 384, 'entity-state2-differential.json', 'instruction'),
    Suite('entity_state10', 180, 384, 'entity-state10-differential.json', 'instruction'),
    Suite('entity_state20', 180, 384, 'entity-state20-differential.json', 'instruction'),
    Suite('entity_state40', 180, 384, 'entity-state40-differential.json', 'instruction'),
    Suite('entity_state80', 180, 384, 'entity-state80-differential.json', 'instruction'),
    Suite('entity_state100', 180, 384, 'entity-state100-differential.json', 'instruction'),
    Suite('entity_state200', 180, 384, 'entity-state200-differential.json', 'instruction'),
    Suite('entity_state400', 180, 384, 'entity-state400-differential.json', 'instruction'),
    Suite('entity_late_states', 180, 384, 'entity-late-states-differential.json', 'instruction'),
    Suite('entity_state800', 180, 384, 'entity-state800-differential.json', 'instruction'),
    Suite('entity_update', 240, 384, 'entity-update-differential.json', 'instruction'),
    Suite('entity_create', 180, 384, 'entity-create-differential.json', 'instruction'),
    Suite('entity_action_sound', 180, 384, 'entity-action-sound-differential.json', 'instruction'),
    Suite('entity_actions_basic', 180, 384, 'entity-actions-basic-differential.json', 'instruction'),
    Suite('entity_actions_advanced', 240, 384, 'entity-actions-advanced-differential.json', 'instruction'),
    Suite('entity_action_map', 240, 384, 'entity-action-map-differential.json', 'instruction'),
    Suite('entity_action_dispatch', 240, 384, 'entity-action-dispatch-differential.json', 'instruction'),
    Suite('entity_batch', 240, 384, 'entity-batch-differential.json', 'instruction'),
    Suite('dat', 120, 512, 'dat-differential.json', 'instruction'),
    Suite('dat_io_c', 120, 512, 'dat-io-differential.json', 'instruction'),
    Suite('dat_section', 120, 512, 'dat-section-differential.json', 'instruction'),
    Suite('dat_cache', 120, 512, 'dat-cache-differential.json', 'instruction'),
    Suite('dat_files', 120, 512, 'dat-files-differential.json', 'instruction'),
    Suite('dat_load', 120, 512, 'dat-load-differential.json', 'instruction'),
    Suite('resource_raw', 120, 512, 'resource-raw-differential.json', 'instruction'),
    Suite('resource_rle', 120, 512, 'resource-rle-differential.json', 'instruction'),
    Suite('special_blit', 120, 512, 'special-blit-differential.json', 'instruction'),
    Suite('special_setup', 120, 512, 'special-setup-differential.json', 'instruction'),
    Suite('resource_select', 120, 512, 'resource-select-differential.json', 'instruction'),
    Suite('resource_select_full', 6600, 384, 'resource-select-full-differential.json', 'instruction'),
    Suite('object_graphics', 120, 512, 'object-graphics-differential.json', 'instruction'),
    Suite('object_coordinates', 120, 512, 'object-coordinates-differential.json', 'instruction'),
    Suite('object_cells', 120, 512, 'object-cells-differential.json', 'instruction'),
    Suite('steel_cells', 120, 512, 'steel-cells-differential.json', 'instruction'),
    Suite('object_state', 120, 512, 'object-state-differential.json', 'instruction'),
    Suite('object_cells_bus', 420, 512, 'object-cells-bus-differential.json', 'instruction'),
    Suite('steel_cells_bus', 420, 512, 'steel-cells-bus-differential.json', 'instruction'),
    Suite('object_coordinates_bus', 420, 512, 'object-coordinates-bus-differential.json', 'instruction'),
    Suite('object_state_bus', 420, 512, 'object-state-bus-differential.json', 'instruction'),
    Suite('vga_clear', 120, 512, 'vga-clear-differential.json', 'instruction'),
    Suite('drawing_layout', 120, 512, 'drawing-layout-differential.json', 'instruction'),
    Suite('level_drawing', 120, 512, 'level-drawing-differential.json', 'instruction'),
    Suite('level_header', 120, 512, 'level-header-differential.json', 'instruction'),
    Suite('minimap_sample', 120, 512, 'minimap-sample-differential.json', 'instruction'),
    Suite('minimap_row', 120, 512, 'minimap-row-differential.json', 'instruction'),
    Suite('minimap_column', 120, 512, 'minimap-column-differential.json', 'instruction'),
    Suite('level_finish', 420, 512, 'level-finish-differential.json', 'instruction'),
    Suite('level_initialize', 7260, 512, 'level-initialize-differential.json', 'instruction'),
    Suite('drawing_clip', 120, 512, 'drawing-clip-differential.json', 'instruction'),
    Suite('drawing_dirty', 120, 512, 'drawing-dirty-differential.json', 'instruction'),
    Suite('drawing_inputs', 120, 512, 'drawing-inputs-differential.json', 'instruction'),
    Suite('drawing_dispatch', 120, 512, 'drawing-dispatch-differential.json', 'instruction'),
    Suite('drawing_source', 120, 512, 'drawing-source-differential.json', 'instruction'),
    Suite('drawing_plan', 120, 512, 'drawing-plan-differential.json', 'composition'),
    Suite('aligned_opaque', 180, 512, 'aligned-opaque-differential.json', 'instruction'),
    Suite('drawing_render', 180, 512, 'drawing-render-differential.json', 'composition'),
    Suite('aligned_masked', 180, 512, 'aligned-masked-differential.json', 'instruction'),
    Suite('drawing_masked_render', 180, 512, 'drawing-masked-render-differential.json', 'composition'),
    Suite('aligned_protected', 180, 512, 'aligned-protected-differential.json', 'instruction'),
    Suite('aligned_mask_effects', 180, 512, 'aligned-mask-effects-differential.json', 'instruction'),
    Suite('aligned_read_mask', 180, 512, 'aligned-read-mask-differential.json', 'instruction'),
    Suite('drawing_aligned_render', 180, 512, 'drawing-aligned-render-differential.json', 'composition'),
    Suite('shifted_mask_effects', 180, 512, 'shifted-mask-effects-differential.json', 'instruction'),
    Suite('drawing_shifted_render', 180, 512, 'drawing-shifted-render-differential.json', 'composition'),
    Suite('shifted_opaque', 180, 512, 'shifted-opaque-differential.json', 'instruction'),
    Suite('shifted_masked', 180, 512, 'shifted-masked-differential.json', 'instruction'),
    Suite('shifted_protected', 180, 512, 'shifted-protected-differential.json', 'instruction'),
    Suite('shifted_read_mask', 180, 512, 'shifted-read-mask-differential.json', 'instruction'),
    Suite('drawing_bitmap', 180, 512, 'drawing-bitmap-differential.json', 'instruction'),
    Suite('terrain_inputs', 180, 512, 'terrain-inputs-differential.json', 'instruction'),
    Suite('terrain_drawing', 180, 512, 'terrain-drawing-differential.json', 'instruction'),
    Suite('terrain_commands', 180, 512, 'terrain-commands-differential.json', 'instruction'),
    Suite('object_drawing', 360, 512, 'object-drawing-differential.json', 'instruction'),
    Suite('level_redraw', 15660, 512, 'level-redraw-differential.json', 'instruction'),
    Suite('terrain_stream', 14460, 512, 'terrain-stream-differential.json', 'instruction'),
    Suite('entity_pattern', 180, 384, 'entity-pattern-differential.json', 'instruction'),
    Suite('entity_pixel', 180, 384, 'entity-pixel-differential.json', 'instruction'),
    Suite('entity_pixel_bus', 180, 384, 'entity-pixel-bus-differential.json', 'instruction'),
    Suite('entity_vga', 180, 384, 'entity-vga-differential.json', 'instruction'),
    Suite('entity_stroke', 180, 384, 'entity-stroke-differential.json', 'instruction'),
    Suite('mask_generators', 180, 384, 'mask-generators-differential.json', 'instruction'),
    Suite('generated_graphics', 180, 384, 'generated-graphics-differential.json', 'instruction'),
    Suite('entity_mask', 180, 384, 'entity-mask-differential.json', 'instruction'),
    Suite('entity_mask_rows', 180, 384, 'entity-mask-rows-differential.json', 'instruction'),
    Suite('coordinate_pixel', 180, 384, 'coordinate-pixel-differential.json', 'instruction'),
    Suite('sound_latches', 180, 384, 'sound-latches-differential.json', 'component'),
    Suite('entity_countdown', 180, 384, 'entity-countdown-differential.json', 'instruction'),
    Suite('game_transition', 240, 384, 'game-transition-differential.json', 'instruction'),
    Suite('view_scroll', 180, 384, 'view-scroll-differential.json', 'instruction'),
    Suite('game_frame', 600, 512, 'game-frame-differential.json', 'instruction'),
    Suite('game_session', 1800, 768, 'game-session-differential.json', 'instruction'),
    Suite('game_loop', 3600, 768, 'game-loop-differential.json', 'composition'),
    Suite('resource_retry', 300, 512, 'resource-retry-differential.json', 'composition'),
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

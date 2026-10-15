"""Run the bounded native C-versus-original instruction suites."""
from pathlib import Path
import sys
from bounded_process import run_bounded

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    for suite in ('display_status','display_start','display_setup','text_glyph','text_stream','display_pages','background_drawing','palette_channels','palette_rows','palette_ports','palette_row_select','palette_transition','retry_input'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],
                    cwd=ROOT,timeout=180 if suite=='retry_input' else 720 if suite in ('palette_row_select','palette_transition') else 390 if suite=='palette_ports' else 660 if suite=='palette_rows' else 360 if suite=='palette_channels' else 210 if suite=='background_drawing' else 180,memory_mib=384)
    run_bounded([sys.executable, str(ROOT / 'tests/cache_allocation.py')],
                cwd=ROOT, timeout=180, memory_mib=384)
    run_bounded([sys.executable, str(ROOT / 'tests/video_restore.py')],
                cwd=ROOT, timeout=180, memory_mib=384)
    run_bounded([sys.executable, str(ROOT / 'tests/vector_restore.py')],
                cwd=ROOT, timeout=180, memory_mib=384)
    run_bounded([sys.executable, str(ROOT / 'tests/timer_restore.py')],
                cwd=ROOT, timeout=180, memory_mib=384)
    run_bounded([sys.executable, str(ROOT / 'tests/fatal_cleanup.py')],
                cwd=ROOT, timeout=180, memory_mib=384)
    run_bounded([sys.executable, str(ROOT / 'tests/file_error.py')],
                cwd=ROOT, timeout=180, memory_mib=384)
    run_bounded([sys.executable, str(ROOT / 'tests/resource_raw_full.py')],
                cwd=ROOT, timeout=180, memory_mib=384)
    run_bounded([sys.executable, str(ROOT / "tests" / "decimal_digits_c.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "checksum.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "pcspeaker.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "dat.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "dat_io_c.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "dat_section.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "dat_cache.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "dat_files.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "dat_load.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "resource_raw.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "resource_rle.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "special_blit.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "special_setup.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "resource_select.py")],
                   cwd=ROOT, check=True, timeout=120)
    # Single serial campaign: every real-input boundary gets its own bounded
    # 120-second / 384-MiB worker; temporary DLL ownership stays in the parent.
    run_bounded([sys.executable, str(ROOT / 'tests/resource_select_full.py')],
                cwd=ROOT, timeout=6600, memory_mib=384)
    run_bounded([sys.executable, str(ROOT / "tests" / "object_graphics.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "object_coordinates.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "object_cells.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "steel_cells.py")],
                   cwd=ROOT, check=True, timeout=120)
    run_bounded([sys.executable, str(ROOT / "tests" / "object_state.py")],
                   cwd=ROOT, check=True, timeout=120)
    for suite in ('object_cells_bus','steel_cells_bus','object_coordinates_bus','object_state_bus'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=420)
    for suite in ('vga_clear','drawing_layout','level_drawing'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=120)
    run_bounded([sys.executable,str(ROOT/'tests/level_header.py')],cwd=ROOT,check=True,timeout=120)
    for suite in ('minimap_sample','minimap_row','minimap_column'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=120)
    run_bounded([sys.executable,str(ROOT/'tests/level_finish.py')],cwd=ROOT,check=True,timeout=420)
    run_bounded([sys.executable,str(ROOT/'tests/level_initialize.py')],cwd=ROOT,check=True,timeout=7260)
    for suite in ('drawing_clip','drawing_dirty','drawing_inputs'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=120)
    for suite in ('drawing_dispatch','drawing_source','drawing_plan'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=120)
    for suite in ('aligned_opaque','drawing_render','aligned_masked','drawing_masked_render'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=180)
    for suite in ('aligned_protected','aligned_mask_effects','aligned_read_mask','drawing_aligned_render'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=180)
    for suite in ('shifted_mask_effects','drawing_shifted_render'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=180)
    for suite in ('shifted_opaque','shifted_masked','shifted_protected','shifted_read_mask','drawing_bitmap'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=180)
    for suite in ('terrain_inputs','terrain_drawing'):
        run_bounded([sys.executable,str(ROOT/'tests'/(suite+'.py'))],cwd=ROOT,check=True,timeout=180)
    run_bounded([sys.executable,str(ROOT/'tests/terrain_commands.py')],cwd=ROOT,check=True,timeout=180)
    run_bounded([sys.executable,str(ROOT/'tests/object_drawing.py')],cwd=ROOT,check=True,timeout=360)
    run_bounded([sys.executable,str(ROOT/'tests/level_redraw.py')],cwd=ROOT,check=True,timeout=15660)
    # Complete cases share a globally capped two-worker campaign, with a
    # separate300-second bound on every complete pinned terrain stream.
    run_bounded([sys.executable,str(ROOT/'tests/terrain_stream.py')],cwd=ROOT,check=True,timeout=14460)

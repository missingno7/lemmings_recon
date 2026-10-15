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
    if cluster not in ("entity_stroke","entity_vga","entity_pixel","entity_pattern","checksum","pcspeaker","dat","dat_io","dat_section","dat_cache","cache_allocation","display_status","display_start","display_setup","display_pages","background_drawing","palette_channels","palette_rows","palette_ports","palette_row_select","palette_transition","retry_input","retry_ui","text_glyph","text_stream","video_restore","vector_restore","timer_restore","fatal_cleanup","file_error","resource_raw_full","resource_select_full","dat_files","dat_load","resource_raw","resource_rle","special_blit","special_setup","decimal_digits","resource_select","object_graphics","object_coordinates","object_cells","steel_cells","object_state","vga_clear","drawing_layout","level_drawing","level_header","level_finish","level_initialize","minimap_sample","minimap_row","minimap_column","drawing_clip","drawing_dirty","drawing_inputs","drawing_dispatch","drawing_source","drawing_plan","aligned_opaque","drawing_render","aligned_masked","aligned_mask_effects","aligned_protected","aligned_read_mask","shifted_mask_effects","shifted_opaque","shifted_masked","shifted_protected","shifted_read_mask","terrain_drawing","terrain_stream","object_drawing","level_redraw"):
        raise ValueError("Unknown C cluster")
    out = Path(output) if output else ROOT / "build" / (cluster+".dll")
    out.parent.mkdir(parents=True, exist_ok=True)
    sources=[ROOT/"c"/(cluster+".c")]
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
    if cluster in ('drawing_render','terrain_drawing','terrain_stream','text_glyph','text_stream','background_drawing','retry_ui'):
        if cluster in ('terrain_drawing','terrain_stream','text_glyph','text_stream','background_drawing','retry_ui'):sources += [ROOT/'c/drawing_render.c']
        if cluster=='terrain_stream':sources += [ROOT/'c/terrain_drawing.c']
        sources += [ROOT/'c'/(n+'.c') for n in ('drawing_plan','drawing_inputs','drawing_clip','drawing_dirty','drawing_dispatch','drawing_source','aligned_opaque','aligned_masked','aligned_mask_effects','aligned_protected','aligned_read_mask','shifted_mask_effects','shifted_opaque','shifted_masked','shifted_protected','shifted_read_mask')]
    if cluster == "object_drawing":
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
    if cluster=="entity_stroke":defines=["-DMUTATION=0","-DSTROKE_MUTATION="+str(mutation)]
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
    if cluster=="background_drawing":defines=["-DBACKGROUND_DRAWING_MUTATION="+str(mutation)]
    if cluster=="text_glyph":defines=["-DTEXT_GLYPH_MUTATION="+str(mutation)]
    if cluster=="text_stream":defines=["-DTEXT_STREAM_MUTATION="+str(mutation)]
    if cluster=="video_restore":defines=["-DVIDEO_RESTORE_MUTATION="+str(mutation)]
    if cluster=="cache_allocation":defines=["-DCACHE_ALLOCATION_MUTATION="+str(mutation)]
    if cluster=="dat_files":defines=["-DMUTATION=0","-DFILE_MUTATION="+str(mutation)]
    if cluster=="dat_load":defines=["-DMUTATION=0","-DLOAD_MUTATION="+str(mutation)]
    if cluster=="special_setup":defines=["-DMUTATION=0","-DSETUP_MUTATION="+str(mutation)]
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

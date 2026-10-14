"""Build a portable C11 translation cluster for bounded native verification."""
import os
from pathlib import Path
import shutil
import subprocess

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
    if cluster not in ("checksum","pcspeaker","dat","dat_io","dat_section","dat_cache","dat_files","dat_load","resource_raw","resource_rle","special_blit","special_setup","decimal_digits","resource_select","object_graphics","object_coordinates","object_cells","steel_cells","object_state","vga_clear","drawing_layout","level_drawing","minimap_sample","minimap_row","minimap_column","drawing_clip","drawing_dirty","drawing_inputs","drawing_dispatch","drawing_source","drawing_plan","aligned_opaque","drawing_render","aligned_masked","aligned_mask_effects","aligned_protected","aligned_read_mask","shifted_mask_effects","shifted_opaque","shifted_masked","shifted_protected","shifted_read_mask","terrain_drawing"):
        raise ValueError("Unknown C cluster")
    out = Path(output) if output else ROOT / "build" / (cluster+".dll")
    out.parent.mkdir(parents=True, exist_ok=True)
    sources=[ROOT/"c"/(cluster+".c")]
    if cluster=="dat_section":sources += [ROOT/"c/dat.c",ROOT/"c/dat_io.c"]
    if cluster=="dat_files":sources += [ROOT/"c/dat_cache.c"]
    if cluster=="dat_load":sources += [ROOT/"c"/(n+".c") for n in ('dat','dat_io','dat_section','dat_cache','dat_files')]
    if cluster=="special_setup":sources += [ROOT/"c"/(n+".c") for n in ('dat','dat_io','dat_section','dat_cache','dat_files','dat_load','resource_rle','special_blit')]
    if cluster=="resource_select":sources += [ROOT/"c"/(n+".c") for n in ('decimal_digits','resource_raw','dat','dat_io','dat_section','dat_cache','dat_files','dat_load')]
    if cluster=="object_state":sources += [ROOT/"c"/(n+".c") for n in ('object_graphics','steel_cells','object_cells','object_coordinates')]
    if cluster=="level_drawing":sources += [ROOT/"c"/(n+".c") for n in ('vga_clear','drawing_layout')]
    if cluster=="minimap_row":sources += [ROOT/'c/minimap_sample.c']
    if cluster=="minimap_column":sources += [ROOT/'c/minimap_row.c',ROOT/'c/minimap_sample.c']
    if cluster=="drawing_inputs":sources += [ROOT/'c/drawing_clip.c',ROOT/'c/drawing_dirty.c']
    if cluster=='drawing_plan':sources += [ROOT/'c'/(n+'.c') for n in ('drawing_inputs','drawing_clip','drawing_dirty','drawing_dispatch','drawing_source')]
    if cluster in ('drawing_render','terrain_drawing'):
        if cluster=='terrain_drawing':sources += [ROOT/'c/drawing_render.c']
        sources += [ROOT/'c'/(n+'.c') for n in ('drawing_plan','drawing_inputs','drawing_clip','drawing_dirty','drawing_dispatch','drawing_source','aligned_opaque','aligned_masked','aligned_mask_effects','aligned_protected','aligned_read_mask','shifted_mask_effects','shifted_opaque','shifted_masked','shifted_protected','shifted_read_mask')]
    defines=["-DMUTATION="+str(mutation)] if cluster!="dat_section" else ["-DMUTATION=0","-DSECTION_MUTATION="+str(mutation)]
    if cluster=="dat_files":defines=["-DMUTATION=0","-DFILE_MUTATION="+str(mutation)]
    if cluster=="dat_load":defines=["-DMUTATION=0","-DLOAD_MUTATION="+str(mutation)]
    if cluster=="special_setup":defines=["-DMUTATION=0","-DSETUP_MUTATION="+str(mutation)]
    if cluster=="decimal_digits":defines=["-DMUTATION=0","-DDECIMAL_MUTATION="+str(mutation)]
    if cluster=="resource_select":defines=["-DMUTATION=0","-DDECIMAL_MUTATION=0","-DSELECT_MUTATION="+str(mutation)]
    if cluster=="object_graphics":defines=["-DMUTATION=0","-DOBJECT_MUTATION="+str(mutation)]
    if cluster=="object_coordinates":defines=["-DMUTATION=0","-DCOORD_MUTATION="+str(mutation)]
    if cluster=="object_cells":defines=["-DMUTATION=0","-DCELL_MUTATION="+str(mutation)]
    if cluster=="steel_cells":defines=["-DMUTATION=0","-DSTEEL_MUTATION="+str(mutation)]
    if cluster=="object_state":defines=["-DMUTATION=0","-DSTATE_MUTATION="+str(mutation)]
    if cluster=="vga_clear":defines=["-DCLEAR_MUTATION="+str(mutation)]
    if cluster=="drawing_layout":defines=["-DLAYOUT_MUTATION="+str(mutation)]
    if cluster=="level_drawing":defines=["-DDRAWING_MUTATION="+str(mutation)]
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
    subprocess.run([
        compiler(), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-shared", *defines,
        "-I", str(ROOT / "c"), *map(str,sources),
        "-o", str(out),
    ], check=True)
    return out

if __name__ == "__main__":
    print(build())

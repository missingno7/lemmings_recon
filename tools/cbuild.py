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
    if cluster not in ("checksum","pcspeaker","dat","dat_io","dat_section","dat_cache","dat_files","dat_load","resource_raw","resource_rle","special_blit"):
        raise ValueError("Unknown C cluster")
    out = Path(output) if output else ROOT / "build" / (cluster+".dll")
    out.parent.mkdir(parents=True, exist_ok=True)
    sources=[ROOT/"c"/(cluster+".c")]
    if cluster=="dat_section":sources += [ROOT/"c/dat.c",ROOT/"c/dat_io.c"]
    if cluster=="dat_files":sources += [ROOT/"c/dat_cache.c"]
    if cluster=="dat_load":sources += [ROOT/"c"/(n+".c") for n in ('dat','dat_io','dat_section','dat_cache','dat_files')]
    defines=["-DMUTATION="+str(mutation)] if cluster!="dat_section" else ["-DMUTATION=0","-DSECTION_MUTATION="+str(mutation)]
    if cluster=="dat_files":defines=["-DMUTATION=0","-DFILE_MUTATION="+str(mutation)]
    if cluster=="dat_load":defines=["-DMUTATION=0","-DLOAD_MUTATION="+str(mutation)]
    subprocess.run([
        compiler(), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-shared", *defines,
        "-I", str(ROOT / "c"), *map(str,sources),
        "-o", str(out),
    ], check=True)
    return out

if __name__ == "__main__":
    print(build())

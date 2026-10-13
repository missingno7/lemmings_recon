"""Build the native Windows C translation of the checksum cluster."""
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
    if cluster not in ("checksum","pcspeaker","dat"):
        raise ValueError("Unknown C cluster")
    out = Path(output) if output else ROOT / "build" / (cluster+".dll")
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        compiler(), "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
        "-shared", "-DMUTATION=" + str(mutation),
        "-I", str(ROOT / "c"), str(ROOT / "c" / (cluster+".c")),
        "-o", str(out),
    ], check=True)
    return out

if __name__ == "__main__":
    print(build())

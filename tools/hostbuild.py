"""Build the headless C11 host or the SDL3 front end; Python is only a build/test dependency."""
import argparse
from pathlib import Path
from bounded_process import run_bounded
from cbuild import ROOT,compiler,source_files

def sources():
    return tuple(dict.fromkeys((ROOT/'host/platform_host.c',ROOT/'c/pklite_unpack.c',
        *source_files('game_loop'),*source_files('resource_retry'),*source_files('main_resources'),*source_files('startup'),
        *source_files('adlib_engine'),OPL3/'opl3.c')))

# Nuked OPL3 (LGPL-2.1) is a pinned git submodule, compiled unmodified.
OPL3=ROOT/'third_party/Nuked-OPL3'

def build_host(output,*,dll=False):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    argv=[compiler(),'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wundef',
        '-I',str(ROOT/'c'),'-I',str(ROOT/'host'),'-I',str(OPL3)]
    if dll:argv+=['-shared']
    else:argv+=[str(ROOT/'host/main.c')]
    argv += [*map(str,sources()),'-o',str(output)]
    run_bounded(argv,cwd=ROOT,timeout=120,memory_mib=384,check=True)
    return output

def build_sdl(output):
    """SDL3 front end (host/sdl_main.c) over the same host and game sources.
    SDL3 is the pinned release from metadata/sdl3.json (tools/fetch_sdl3.py);
    its SDL3.dll is copied next to the executable."""
    import shutil
    from fetch_sdl3 import fetch
    sdl=fetch();output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    argv=[compiler(),'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wundef',
        '-I',str(ROOT/'c'),'-I',str(ROOT/'host'),'-I',str(OPL3),'-I',str(sdl/'include'),
        str(ROOT/'host/sdl_main.c'),*map(str,sources()),
        '-L',str(sdl/'lib'),'-lSDL3','-o',str(output)]
    run_bounded(argv,cwd=ROOT,timeout=180,memory_mib=512,check=True)
    shutil.copy2(sdl/'bin/SDL3.dll',output.parent/'SDL3.dll')
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dll',action='store_true')
    p.add_argument('--sdl',action='store_true',help='build the SDL3 front end (build/lemmings.exe)')
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    if a.sdl:print(build_sdl(a.out or ROOT/'build/lemmings.exe'))
    else:print(build_host(a.out or ROOT/'build'/('host.dll' if a.dll else 'lemmings-headless.exe'),dll=a.dll))

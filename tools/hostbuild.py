"""Build the headless C11 host; Python is only a build/test dependency."""
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

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dll',action='store_true')
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    print(build_host(a.out or ROOT/'build'/('host.dll' if a.dll else 'lemmings-headless.exe'),dll=a.dll))

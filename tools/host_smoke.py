"""Bounded real-asset headless smoke and frame/cadence artifact checks."""
import argparse
import csv
import subprocess
import time
from pathlib import Path
from bounded_process import run_bounded
from common import ROOT,BUILD,sha,write_json
from hostbuild import build_host,sources

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--existing',action='store_true',help='Use the already built release executable')
    a=p.parse_args();output=BUILD/'host-smoke';output.mkdir(exist_ok=True)
    exe=BUILD/'lemmings-headless.exe'
    if not a.existing:build_host(exe)
    paths={*sources(),*(ROOT/'c').glob('*.h'),ROOT/'host/main.c',ROOT/'host/platform_host.h',
        ROOT/'host/smoke.script',ROOT/'tools/hostbuild.py',Path(__file__),ROOT/'tools/bounded_process.py',
        *(ROOT/'assets').iterdir()}
    before={q.relative_to(ROOT).as_posix():sha(q.read_bytes()) for q in sorted(paths) if q.is_file()}
    began=time.perf_counter()
    result=run_bounded([str(exe),str(ROOT/'assets'),str(ROOT/'host/smoke.script'),'20',str(output)],
        cwd=ROOT,timeout=60,memory_mib=256,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    seconds=time.perf_counter()-began
    (output/'runner.log').write_text(result.stdout,encoding='utf-8')
    rows=list(csv.DictReader((output/'frames.csv').open(newline='')))
    assert len(rows)==20 and len({row['fnv1a64_ram_planes_dac_crtc'] for row in rows})==20
    for left,right in zip(rows[-10:],rows[-9:]):
        assert int(right['irq08'])-int(left['irq08'])==5
        assert abs(int(right['pit_time'])-int(left['pit_time'])-5*17044)<=8
    images=[]
    for name,geometry in (('menu',(640,350)),('briefing',(640,350)),('gameplay',(320,200))):
        q=output/(name+'.ppm');header=q.read_bytes().split(b'\n',3)
        assert header[0]==b'P6' and tuple(map(int,header[1].split()))==geometry and header[2]==b'255'
        pixels=header[3];assert len(pixels)==geometry[0]*geometry[1]*3
        colors=len(set(zip(pixels[::3],pixels[1::3],pixels[2::3])));assert colors>=8
        images.append(dict(path=q.relative_to(ROOT).as_posix(),geometry=geometry,colors=colors,sha256=sha(q.read_bytes())))
    assert before=={q:sha((ROOT/q).read_bytes()) for q in before},'smoke inputs changed'
    write_json(output/'smoke.json',dict(accepted=True,seconds=seconds,frames=20,
        cadence='five IRQ08 per game tick; five17044-unit display periods within8 units',
        ppm=images,input_hashes=before,executable_sha256=sha(exe.read_bytes()),stdout=result.stdout,
        limits=dict(seconds=60,process_commit_mib=256,polls=100000,accesses=500000000)))
    print(result.stdout,end='');print(f'PASS host smoke: {seconds:.3f}s,20 frames,3 PPMs; display-locked cadence checked')
if __name__=='__main__':main()

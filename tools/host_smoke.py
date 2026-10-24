"""Bounded real-asset headless smoke and frame/cadence artifact checks."""
import argparse
import csv
import subprocess
import time
from pathlib import Path
from bounded_process import run_bounded
from common import ROOT,BUILD,sha,write_json
from hostbuild import build_host,sources

FRAME_PIT=449*800*1193182/25175000

def adlib_smoke(exe):
    """Original AdLib driver path: native startup loads adlib.dat, the game-installed
    INT61 runs the C engine, and its OPL writes drive Nuked OPL3 into audio.wav."""
    import array,math,re,wave
    output=BUILD/'host-smoke-adlib';output.mkdir(exist_ok=True)
    result=run_bounded([str(exe),str(ROOT/'assets'),str(ROOT/'host/smoke.script'),'130',str(output),
        '--media-probe=assume-original','--sound=adlib','--audio'],
        cwd=ROOT,timeout=60,memory_mib=256,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (output/'runner.log').write_text(result.stdout,encoding='utf-8')
    requests=int(re.search(r'sound-requests=(\d+)',result.stdout)[1])
    rows=list(csv.DictReader((output/'frames.csv').open(newline='')))
    assert len(rows)==130 and requests>=len(rows)
    with wave.open(str(output/'audio.wav')) as w:
        assert (w.getframerate(),w.getnchannels(),w.getsampwidth())==(49716,2,2)
        frames=w.getnframes();samples=array.array('h',w.readframes(frames))
    # Audio length follows the PIT clock of the run (rendered up to the final time).
    assert frames>=int(rows[-1]['pit_time'])*49716//1193182
    gameplay=int(re.search(r'capture gameplay pit_time=(\d+)',result.stdout)[1])*49716//1193182
    tail=samples[gameplay*2:]
    rms=math.sqrt(sum(x*x for x in tail)/max(1,len(tail)))
    assert rms>100,'no OPL output after gameplay start'
    # Song 06 starts about 3 s into gameplay. Every music note is written as
    # key-off, frequency, key-on in one update; with the OPL bus clock each one
    # restarts its envelope. If writes collapse to one instant, notes stop
    # retriggering and both the level and the onset count drop sharply.
    music=samples[(gameplay+3*49716)*2::2];window=49716//50
    levels=[math.sqrt(sum(x*x for x in music[i:i+window])/window) for i in range(0,len(music)-window,window)]
    onsets=sum(1 for a,b in zip(levels,levels[1:]) if b>2*a+200)
    music_rms=math.sqrt(sum(x*x for x in music)/max(1,len(music)))
    assert music_rms>2000 and onsets>=6,f'music notes not retriggering: rms {music_rms:.0f}, onsets {onsets}'
    return dict(frames=len(rows),int61_requests=requests,audio_frames=frames,gameplay_rms=round(rms,1),
        music_rms=round(music_rms,1),music_onsets=onsets,
        wav_sha256=sha((output/'audio.wav').read_bytes()))

def special_smoke(exe):
    """Fun 22 uses special graphics (vgaspec): the briefing redraw must reach
    SetupSpecialGraphicsResource 1A7B through bound services and play on."""
    output=BUILD/'host-smoke-special';output.mkdir(exist_ok=True)
    result=run_bounded([str(exe),str(ROOT/'assets'),str(ROOT/'host/fun22.script'),'40',str(output),
        '--media-probe=assume-original','--sound=adlib'],
        cwd=ROOT,timeout=60,memory_mib=256,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (output/'runner.log').write_text(result.stdout,encoding='utf-8')
    rows=list(csv.DictReader((output/'frames.csv').open(newline='')))
    assert len(rows)==40 and (output/'briefing.ppm').is_file()
    return dict(frames=len(rows),briefing_sha256=sha((output/'briefing.ppm').read_bytes()))

def sdl_smoke(reference):
    """SDL3 front end under the offscreen video and dummy audio drivers must
    reproduce the headless AdLib run frame for frame (same scripted input)."""
    import os
    from hostbuild import build_sdl
    exe=build_sdl(BUILD/'lemmings.exe');output=BUILD/'host-smoke-sdl';output.mkdir(exist_ok=True)
    env=dict(os.environ,SDL_VIDEO_DRIVER='offscreen',SDL_AUDIO_DRIVER='dummy')
    run_bounded([str(exe),'--assets',str(ROOT/'assets'),'--script',str(ROOT/'host/smoke.script'),'--frames','130',
        '--no-pace','--log',str(output/'frames.csv'),'--audio-log',str(output/'audio.csv')],cwd=ROOT,timeout=120,
        memory_mib=512,check=True,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    rows=list(csv.DictReader((output/'frames.csv').open(newline='')))
    assert rows==reference,'SDL front end diverges from the headless runner'
    # A live device consumes audio as it is produced: the samples delivered to
    # the SDL stream must track game time, never a backlog of earlier silence.
    lags=[int(t)*49716//1193182-int(d) for t,d in csv.reader((output/'audio.csv').open(newline=''))]
    assert len(lags)==len(rows) and max(abs(x) for x in lags)<710,f'audio delivery lag {max(lags)}..{min(lags)} samples'
    return dict(frames=len(rows),audio_lag_samples=[min(lags),max(lags)])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--existing',action='store_true',help='Use the already built release executable')
    p.add_argument('--sdl',action='store_true',help='Also build the SDL3 front end and compare it offscreen')
    a=p.parse_args();output=BUILD/'host-smoke';output.mkdir(exist_ok=True)
    exe=BUILD/'lemmings-headless.exe'
    if not a.existing:build_host(exe)
    paths={*sources(),*(ROOT/'c').glob('*.h'),ROOT/'host/main.c',ROOT/'host/platform_host.h',
        ROOT/'host/smoke.script',ROOT/'host/fun22.script',ROOT/'tools/hostbuild.py',Path(__file__),ROOT/'tools/bounded_process.py',
        *(ROOT/'assets').iterdir()}
    before={q.relative_to(ROOT).as_posix():sha(q.read_bytes()) for q in sorted(paths) if q.is_file()}
    began=time.perf_counter()
    result=run_bounded([str(exe),str(ROOT/'assets'),str(ROOT/'host/smoke.script'),'20',str(output),'--media-probe=assume-original'],
        cwd=ROOT,timeout=60,memory_mib=256,check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    seconds=time.perf_counter()-began
    (output/'runner.log').write_text(result.stdout,encoding='utf-8')
    rows=list(csv.DictReader((output/'frames.csv').open(newline='')))
    assert len(rows)==20 and len({row['fnv1a64_ram_planes_dac_crtc'] for row in rows})==20
    for left,right in zip(rows[-10:],rows[-9:]):
        assert int(right['irq08'])-int(left['irq08'])==5
        # Mode 0Dh raster from the standard VGA CRTC table: 449 lines of 800
        # clocks at 25.175 MHz (70.09 Hz); the game ticks every fifth frame.
        # Retrace is observed by 4-unit status polls, so a boundary carries up
        # to one poll quantum of phase.
        assert abs(int(right['pit_time'])-int(left['pit_time'])-5*FRAME_PIT)<=4
    images=[]
    for name,geometry in (('menu',(640,350)),('briefing',(640,350)),('gameplay',(320,200))):
        q=output/(name+'.ppm');header=q.read_bytes().split(b'\n',3)
        assert header[0]==b'P6' and tuple(map(int,header[1].split()))==geometry and header[2]==b'255'
        pixels=header[3];assert len(pixels)==geometry[0]*geometry[1]*3
        colors=len(set(zip(pixels[::3],pixels[1::3],pixels[2::3])));assert colors>=8
        images.append(dict(path=q.relative_to(ROOT).as_posix(),geometry=geometry,colors=colors,sha256=sha(q.read_bytes())))
    adlib=adlib_smoke(exe)
    special=special_smoke(exe)
    sdl=sdl_smoke(list(csv.DictReader((BUILD/'host-smoke-adlib/frames.csv').open(newline='')))) if a.sdl else None
    assert before=={q:sha((ROOT/q).read_bytes()) for q in before},'smoke inputs changed'
    write_json(output/'smoke.json',dict(accepted=True,seconds=seconds,frames=20,adlib=adlib,special=special,sdl=sdl,
        cadence='five IRQ08 per game tick; five VGA frames (449x800 clocks at 25.175 MHz) within one 4-unit status poll',
        ppm=images,input_hashes=before,executable_sha256=sha(exe.read_bytes()),stdout=result.stdout,
        limits=dict(seconds=60,process_commit_mib=256,polls=100000,accesses=500000000)))
    print(result.stdout,end='');print(f'PASS host smoke: {seconds:.3f}s,20 frames,3 PPMs; display-locked cadence checked')
    if sdl:print(f"PASS SDL3 front end: {sdl['frames']} frames identical to the headless runner")
    print(f"PASS special-graphics smoke: Fun 22 briefing and {special['frames']} frames")
    print(f"PASS AdLib smoke: {adlib['frames']} frames, {adlib['int61_requests']} INT61 requests, {adlib['audio_frames']} audio frames, music RMS {adlib['music_rms']}, {adlib['music_onsets']} note onsets")
if __name__=='__main__':main()

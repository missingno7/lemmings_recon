"""Whole-level lockstep against the original: record once, check natively, diagnose one frame.

Verification, not discovery (AGENTS.md, Execution policy). Input is a fixed
solution script, never generated or adapted against the original.

  --record    Run the exact reference (host_journey's: constructed menu entry
              state, original instructions in the shared OriginalMachine, the
              independent Python platform provider) beside the native host,
              comparing every poll and loop boundary. At each frame-wait poll
              0179 store one hash of the agreed state. The log is a few KB per
              level, cached under build/lockstep/ and keyed by executable,
              script and SCHEDULE; it is regenerated, never edited.
  (default)   Native host only, same script and tick schedule, same hash per
              frame; report the first frame whose hash differs from the log.
              Seconds per level. This is the difftest receipt.
  --diagnose F
              Native host only up to the 0179 poll before frame F (whose hash
              matched, so native and original agree there), then seed the exact
              reference from that native state and compare every poll and
              boundary through frame F+2. Prints the first differing memory.

Hash: canonical RAM, defined CPU registers except FLAGS (only masked flags are
compared), VGA planes/latches/sequencer/graphics registers and indices, CRTC,
attribute registers, DAC and the virtual clock: the fields the exact comparison
covers. Hash index i is the state at the i-th 0179 poll, before its five IRQ08.

Script format (external "lemdev --record-input" text): per level frame
`F move X Y` (screen pixels; the INT33 AX=3 answer is X+8, Y+8, which
0426D/0282 store in ds:0010/0012), `F down|up|rdown|rup`, `F key|keyup S`.
Frame 0 is the first frame of the session.

Tick schedule (SCHEDULE): the game_loop convention, five IRQ08 at the frame
wait poll 0179 and one at the other waits. Frame F's input is in force for the
ticks delivered at the 0179 poll before frame F's work (018F). The script's
recorder froze one INT33 answer from 018F of F to 018F of F+1, so panel ticks
see a frame's input one frame earlier here; both machines receive the same.

Usage: tools/difftest.py host_lockstep, or
  python tests/host_lockstep.py [SOLUTION.txt] [--record|--diagnose F] [--frames N] [--mutate NAME_MUTATION=N]
--mutate builds the native host with one existing mutation switch, to confirm
that check and diagnose locate a native fault; it never records or passes.
Default solution: build/solutions/fun01.txt (external input, not committed).
"""
import copy
import ctypes as ct
import gc
import hashlib
import json
import re
import sys
import time
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,write_json,sha
from host_support import Host,Event,POLL,OBSERVE,ROOT,v,loop as g
import host_journey as j

DEFAULT=BUILD/'solutions'/'fun01.txt'
LOGS=BUILD/'lockstep'
SCHEDULE='game_loop-5x0179-v1'   # bump when the driver, tick schedule or state_hash changes
SAVED,NEEDED=0x40,0x41
RENEW_FRAMES=100
DIAGNOSE_SPAN=3

def rss():
    """Private commit in MiB (Windows), the quantity the job limit bounds."""
    try:
        class C(ct.Structure):
            _fields_=[('cb',ct.c_uint32),('faults',ct.c_uint32)]+[(n,ct.c_size_t) for n in
                ('peak_ws','ws','qpp','qp','qnpp','qnp','pagefile','peak_pagefile','private')]
        c=C();c.cb=ct.sizeof(C)
        k=ct.windll.kernel32;k.GetCurrentProcess.restype=ct.c_void_p
        f=k.K32GetProcessMemoryInfo;f.argtypes=[ct.c_void_p,ct.c_void_p,ct.c_uint32];f.restype=ct.c_int
        if not f(k.GetCurrentProcess(),ct.byref(c),c.cb):return -1
        return c.private>>20
    except (AttributeError,OSError):return -1

def renew(m):
    """Replace OriginalMachine's Unicorn instance at a stop; execution is unchanged.

    Pinned Unicorn 2.1.4 grows native memory by 1-3 KB per emu_start while a
    code hook is installed, and the machine restarts emulation after every
    resumed RET, so a whole level (~0.8 MiB per frame) exhausts the commit
    limit. 16-bit real-mode CPU state is exactly the mapped memory (canonical
    and wrap mirror) plus REG_NAMES; all other machine state is Python-side and
    kept. The hook list must match OriginalMachine.__init__ (tests/verification.py).
    Kept here so the shared engine and its receipts stay untouched.
    """
    from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INSN,UC_HOOK_INTR
    from unicorn import x86_const as x
    v.check(m.stopped and m.pending_hardware is None and m.pending_fetch is None
            and m.pending_movsb is None and not m.executing_boundary,'renew outside a stop')
    image=bytes(m.cpu.mem_read(0,v.SIZE*2));registers=m.state()
    m.cpu=cpu=Uc(UC_ARCH_X86,UC_MODE_16);cpu.mem_map(0,v.SIZE*2);cpu.mem_write(0,image)
    m.access.sync=cpu.mem_write
    cpu.hook_add(UC_HOOK_CODE,m.code)
    m.read_hook=cpu.hook_add(UC_HOOK_MEM_READ,m.read)
    m.write_hook=cpu.hook_add(UC_HOOK_MEM_WRITE,m.write)
    cpu.hook_add(UC_HOOK_INSN,m.inp,None,1,0,x.UC_X86_INS_IN)
    cpu.hook_add(UC_HOOK_INSN,m.out,None,1,0,x.UC_X86_INS_OUT)
    cpu.hook_add(UC_HOOK_INTR,m.on_interrupt)
    m.set_state(registers)
    gc.collect()  # the old instance is only released once its hook cycle is collected

def parse(path):
    """Per-frame (x, y, buttons) and key events from a solution script."""
    moves={};buttons={};keys={};level=rating=None;last_frame=0
    for line in Path(path).read_text().splitlines():
        m=re.match(r'#\s*level\s+(\d+)\s+rating\s+(\d+)',line)
        if m:level,rating=int(m[1]),int(m[2])
        if not line.strip() or line.startswith('#'):continue
        f,kind,*rest=line.split();f=int(f);last_frame=max(last_frame,f)
        if kind=='move':moves[f]=(int(rest[0]),int(rest[1]))
        elif kind in ('down','up','rdown','rup'):buttons.setdefault(f,[]).append(kind)
        elif kind in ('key','keyup'):keys.setdefault(f,[]).append(int(rest[0])|(0 if kind=='key' else 0x80))
        else:raise SystemExit(f'{path}: unknown event {line!r}')
    x,y,b=150-8,100-8,0;frames=[]
    for f in range(last_frame+1):
        if f in moves:x,y=moves[f]
        for kind in buttons.get(f,()):
            bit=1 if kind in ('down','up') else 2
            b=b|bit if kind in ('down','rdown') else b&~bit
        frames.append((x+8,y+8,b))
    return dict(level=level,rating=rating,frames=frames,keys=keys)

DRIVER_FIELDS=('screen','menu_count','sessions','results','typed','cheated','frame','raster_delivered',
    'mouse','scan','last_scan','started','done')

class Access(j.Access):
    """host_journey platform; menu -> F1 -> briefing -> one session -> result.

    Also used without a reference, as the native-only script driver."""
    solution=None;frame_limit=None
    def __init__(self,*args):
        super().__init__(*args);self.started=False;self.done=False
    def script(self,r,site):
        self.polls.append((site,r['flags']));v.check(len(self.polls)<200_000,'lockstep poll budget exhausted')
        scans=[];ticks=0;s=self.solution
        if site==0x4453:
            if self.results:return None
            if not self.sessions:self.mouse=(150,100,0)
            ticks=1
        elif site==0x446D:self.mouse=(150,100,0);ticks=1
        elif site==0x4D23 and r['bx']==0:
            if self.last_scan is not None:scans.append(self.last_scan|0x80);self.last_scan=None
            if self.screen=='menu' and not self.started:scans.append(0x3B);self.last_scan=0x3B;self.started=True  # F1
        elif site==0x4660:self.mouse=(150,100,0);ticks=1
        elif site==0x4683:self.mouse=(150,100,1);ticks=1
        elif site in (0x04AA,0x04BA):ticks=1
        elif site==0x0131:
            ticks=0 if self.raster_delivered else 1;self.raster_delivered=True
        elif site==0x0179:
            self.frame+=1;ticks=5
            if self.frame_limit is not None and self.frame>=self.frame_limit:self.done=True;return None
            f=min(self.frame,len(s['frames'])-1);self.mouse=s['frames'][f]
            scans+=s['keys'].get(self.frame,[])
        elif site==0x01DF:ticks=1
        elif site in (0x47A9,0x47B1,0x47BE,0x480A,0x4812):
            self.done=True;return None
        self.queue=[(9,scan,site) for scan in scans]+[(8,0,site)]*ticks
        return list(self.queue)

def state_hash(h,regs):
    d=hashlib.blake2b(digest_size=16);x=h.vga
    d.update(bytes(h.memory))
    for p in x.planes:d.update(bytes(p))
    d.update(bytes(x.latches)+bytes(x.seq)+bytes(x.gc)+bytes((x.si,x.gi)))
    d.update(bytes(x.crtc)+bytes(x.attr)+bytes(x.dac))
    d.update(b''.join(regs[n].to_bytes(2,'little') for n in v.REG_NAMES if n!='flags'))
    d.update(h.call('time').to_bytes(8,'little'))
    return d.hexdigest()

def log_path(solution):
    key=sha((sha((ROOT/'assets/vgalemmi.exe').read_bytes())+sha(Path(solution).read_bytes())+SCHEDULE).encode())[:16]
    return LOGS/f'{Path(solution).stem}-{key}.json'

def provenance(solution):
    hashes=g.input_hashes()
    extra=set(j.sources())|set((ROOT/'c').glob('*.h'))|{ROOT/'host/platform_host.h',Path(__file__),
        ROOT/'tests/host_journey.py',ROOT/'tests/host_support.py',ROOT/'tools/hostbuild.py',Path(solution)}
    hashes.update({p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in extra})
    return hashes

def seed_reference(h,regs,driver):
    """Exact reference from the native machine state at a matched 0179 poll.

    Platform state comes from the host: virtual clock, raster epoch, CRTC,
    attribute and DAC registers with their indices, the BIOS tick count in RAM.
    The PIT counter phase is not exposed by the host and is declared unknown:
    a port 40h read during diagnosis fails instead of guessing it."""
    c=g.setup()[0];memory=bytearray(h.memory);d=v.new_device(0)
    for i in range(4):d.planes[i][:]=h.vga.planes[i]
    for name in ('latches','seq','gc'):getattr(d,name)[:]=getattr(h.vga,name)
    d.si=h.vga.si;d.gi=h.vga.gi
    reference=g.Reference(c,memory,dict(regs),copy.deepcopy(d));a=reference.access;p=a.platform
    for name in DRIVER_FIELDS:setattr(a,name,copy.copy(getattr(driver,name)))
    p.now=h.call('time');p.raster_epoch=h.call('raster_epoch');p.misc=h.call('in',0x3cc)
    p.reload=v.get16(memory,regs['ds'],0x1FC9) or 65536
    p.crtc[:]=h.vga.crtc;p.ci=h.vga.ci;p.attr[:]=h.vga.attr;p.ai=h.vga.ai;p.attr_data=bool(h.vga.attr_data)
    p.dac[:]=bytes(h.vga.dac);p.mode=h.vga.mode;p.mask=h.vga.pel_mask
    p.dw=h.vga.dac_write;p.dr=h.vga.dac_read;p.dc=h.vga.dac_component;p.rc=h.vga.dac_read_component
    p.clock=v.get16(memory,0x40,0x6c)|(v.get16(memory,0x40,0x6e)<<16)
    unknown=p.input
    def guarded(port):
        v.check(port!=0x40,'PIT counter phase was not seeded (host does not expose it)')
        return unknown(port)
    p.input=guarded
    return reference

def mutated_host(directory,define):
    """Host DLL with one -DNAME=N mutation switch, for checking that check and
    diagnose locate a native fault. Same argv as hostbuild.build_host(dll=True)."""
    import hostbuild
    v.check(re.fullmatch(r'[A-Z0-9_]+_MUTATION=[0-9]+',define) is not None,'--mutate takes NAME_MUTATION=N')
    output=Path(directory)/'host-mutant.dll'
    argv=[hostbuild.compiler(),'-std=c11','-O2','-Wall','-Wextra','-Werror','-Wundef','-D'+define,
        '-I',str(ROOT/'c'),'-I',str(ROOT/'host'),'-I',str(hostbuild.OPL3),'-shared',*map(str,hostbuild.sources()),'-o',str(output)]
    run_bounded(argv,cwd=ROOT,timeout=120,memory_mib=384,check=True)
    return ct.CDLL(str(output))

def worker(mode,directory,solution,frame_limit,target,define=None):
    g.MAX_STEPS=4_000_000_000
    began=time.perf_counter()
    s=parse(solution);Access.solution=s;Access.frame_limit=frame_limit
    v.check(s['level']==0 and s['rating']==0,'only selection 0 (Fun 1) is reached from the constructed menu')
    before=provenance(solution);path=log_path(solution)
    expected=None
    if mode!='record':
        v.check(path.exists(),f'{path.name}: no recorded log; run tests/host_lockstep.py --record first')
        expected=json.loads(path.read_text())['hashes']
    v.check(define is None or mode!='record','a mutated host never records the reference log')
    h=Host(directory,mutated_host(directory,define) if define else None)
    c,memory,r,device=g.setup();h.memory[:]=memory
    for i in range(4):h.vga.planes[i][:]=device.planes[i]
    for name in ('latches','seq','gc'):getattr(h.vga,name)[:]=getattr(device,name)
    h.vga.si=device.si;h.vga.gi=device.gi
    h.call('bind_image',r['cs'])
    h.call('automatic_timer',0);h.call('set_limits',200_000,40_000_000_000,0)
    saved=g.Access,g.Provider,g.provider,g.menu.video_provider
    def video(a,incoming):a.platform.mode_set(incoming['ax']);return dict(incoming)
    g.Access,g.Provider,g.provider,g.menu.video_provider=Access,j.Provider,j.provider,video
    hashes=[];errors=[];last=dict(t=time.perf_counter())
    run=dict(reference=None,a=None,exact_until=None)
    if mode=='record':
        run['reference']=g.Reference(c,bytearray(memory),dict(r),copy.deepcopy(device));run['a']=run['reference'].access
    else:
        run['a']=Access(c,bytearray(memory),dict(r),copy.deepcopy(device))
    def where(i):
        ds=v.physical(r['ds'],0)
        return f'ds:{i-ds:04X}' if 0<=i-ds<0x10000 else f'{i>>4:04X}:{i&15:X}'
    def compare(q,kind):
        reference=run['reference'];a=run['a'];ref=reference.advance()
        if any(ref['regs'][n]!=q[n] for n in v.REG_NAMES if n!='flags'):
            print('LOCKSTEP REG DIFF native/original',{n:(q[n],ref['regs'][n]) for n in v.REG_NAMES if n!='flags' and q[n]!=ref['regs'][n]},flush=True)
        if bytes(h.memory)!=ref['memory']:
            diffs=[(where(i),x,y) for i,(x,y) in enumerate(zip(bytes(h.memory),ref['memory'])) if x!=y]
            print(f'LOCKSTEP RAM DIFF hash={len(hashes)-1} site={q["ip"]:04x} count={len(diffs)} native/original first={diffs[:32]}',flush=True)
        checkpoint=dict(regs=ref['regs'],memory=ref['memory'],status=0,events=(),device=j.CheckpointVga(a.device),mask=ref['mask'])
        actual=dict(regs=q,memory=bytes(h.memory),status=0,events=(),device=j.CheckpointVga(h.vga))
        v.compare_states(f'lockstep {a.screen} hash {len(hashes)-1} {kind} {q["ip"]:04x}',actual,checkpoint)
        v.require(bytes(h.vga.crtc)==a.platform.crtc,'CRTC differs')
        v.require(bytes(h.vga.dac)==a.platform.dac,'DAC differs')
        v.require(bytes(h.vga.attr)==a.platform.attr,'attribute registers differ')
        v.require(h.call('time')==a.platform.now,'virtual clock differs')
        a.reset_observations();reference.provider.trace=[]
        return ref['status']
    def progress(q,kind):
        a=run['a']
        if kind=='boundary' or (q['ip']==0x0179 and a.frame%50==0):
            now=time.perf_counter()
            print(f'LOCKSTEP {mode} {kind} {q["ip"]:04x} {a.screen} frame={a.frame} '
                  f'+{now-last["t"]:.1f}s total={now-began:.1f}s commit={rss()}MiB',flush=True);last['t']=now
    def state(regs):return {n:getattr(regs.contents,n) for n in v.REG_NAMES}
    @POLL
    def poll(_,host,registers,site):
        try:
            q=state(registers)
            if site==0x0179:
                k=len(hashes);hashes.append(state_hash(h,q))
                if mode=='diagnose' and run['reference'] is None and k==target-1:
                    run['reference']=seed_reference(h,q,run['a']);run['a']=run['reference'].access
                    run['exact_until']=target+DIAGNOSE_SPAN
                    print(f'DIAGNOSE seeded the exact reference from native state at hash {k} (frame {k})',flush=True)
                if mode=='check' and k<len(expected) and hashes[k]!=expected[k]:
                    errors.append(f'first divergence at hash {k}: the state entering frame {k} differs; '
                                  f'run tests/host_lockstep.py --diagnose {k}');return 0xca11
            if run['reference'] is not None:
                v.require(compare(q,'poll')==g.CHECKPOINT,'original missed poll')
                if site==0x0179 and run['exact_until'] is not None and len(hashes)>run['exact_until']:
                    errors.append(f'no divergence reproduced through hash {len(hashes)-1}');return 0xca11
            a=run['a'];progress(q,'poll')
            events=a.script(q,site)
            if run['reference'] is not None:run['reference'].resume_poll=True
            if events is None:return 0xca11
            mouse=Event(h.call('time'),1,a.mouse[0],a.mouse[1],a.mouse[2]);v.check(h.call('enqueue',ct.byref(mouse)),'mouse queue')
            for number,scan,_ in events:
                e=Event(h.call('time'),2 if number==9 else 3,0,0,scan)
                v.check(h.call('enqueue',ct.byref(e)),'IRQ queue')
            if run['reference'] is not None and site==0x0179 and a.frame%RENEW_FRAMES==0:renew(run['reference'].machine)
            return 0
        except v.Mismatch as error:errors.append(str(error));return 0xca11
        except BaseException as error:
            import traceback;traceback.print_exc();v.callback_failure(error)
    @OBSERVE
    def observe(_,host,registers,kind):
        if errors or kind:return
        try:
            q=state(registers)
            if run['reference'] is not None:
                v.require(compare(q,'boundary')==g.BOUNDARY,'original missed boundary');run['reference'].resume_boundary=True
            run['a'].memory=h.memory if run['reference'] is None else run['a'].memory
            run['a'].boundary(q);progress(q,'boundary')
        except v.Mismatch as error:errors.append(str(error))
        except BaseException as error:
            import traceback;traceback.print_exc();v.callback_failure(error)
    h.call('set_hooks',None,poll,observe)
    report=dict(accepted=False,scope='whole-level-lockstep',mode=mode,schedule=SCHEDULE,solution=str(solution),
        solution_sha256=sha(Path(solution).read_bytes()),log=path.name,frame_limit=frame_limit)
    try:
        out=h.call('run',ct.byref(v.Regs(**r)));a=run['a'];ds=r['ds']
        report.update(hashes=len(hashes),seconds=time.perf_counter()-began,
            saved=h.memory[v.physical(ds,SAVED)],needed=h.memory[v.physical(ds,NEEDED)])
        if mode=='diagnose':
            v.require(not errors,errors[0] if errors else '')
            return
        v.require(not errors,errors[0] if errors else '')
        h.check()
        v.require(a.done,f'lockstep stopped early at {out.registers.ip:04x} status {out.status}')
        v.check(before==provenance(solution),'lockstep inputs changed during the run')
        if mode=='record':
            v.require(h.call('irqs')==sum(n==8 for n,_,_ in a.deliveries),'IRQ08 delivery count differs')
            LOGS.mkdir(parents=True,exist_ok=True)
            write_json(path,dict(schedule=SCHEDULE,solution=Path(solution).name,solution_sha256=report['solution_sha256'],
                frame_limit=frame_limit,saved=report['saved'],needed=report['needed'],
                original_instructions=run['reference'].machine.steps,reference_inputs=before,hashes=hashes))
            print(f'RECORDED {path.relative_to(ROOT)}: {len(hashes)} frame hashes, {run["reference"].machine.steps} original instructions, '
                  f'saved {report["saved"]} needed {report["needed"]}, {report["seconds"]:.0f}s',flush=True)
            return
        v.require(len(hashes)==len(expected),f'native ended after {len(hashes)} frame hashes, the original after {len(expected)}')
        v.check(define is None,'a mutated host passed: the mutation is not observable on this script')
        report.update(accepted=True,input_hashes=before|{path.relative_to(ROOT).as_posix():sha(path.read_bytes())})
        write_json(BUILD/'host-lockstep.json',report)
        print(f'PASS host_lockstep: {len(hashes)} frame hashes match {path.name}, saved {report["saved"]} '
              f'needed {report["needed"]}, {report["seconds"]:.1f}s',flush=True)
    except BaseException as error:
        report.update(error=str(error),seconds=time.perf_counter()-began)
        if mode=='check' and define is None:write_json(BUILD/'host-lockstep-failure.json',report)
        raise
    finally:
        g.Access,g.Provider,g.provider,g.menu.video_provider=saved
        h.close();del h;gc.collect()

def main():
    args=sys.argv[1:]
    if args[:1]==['--worker']:
        _,mode,directory,solution,frames,target,define=args
        worker(mode,directory,solution,None if frames=='-' else int(frames),None if target=='-' else int(target),
            None if define=='-' else define);return
    frames=target=define=None;mode='check'
    if '--mutate' in args:i=args.index('--mutate');define=args[i+1];del args[i:i+2]
    if '--frames' in args:i=args.index('--frames');frames=int(args[i+1]);del args[i:i+2]
    if '--record' in args:args.remove('--record');mode='record'
    if '--diagnose' in args:i=args.index('--diagnose');mode='diagnose';target=int(args[i+1]);del args[i:i+2]
    v.check(mode!='diagnose' or target>=1,'--diagnose F needs F >= 1 (frame F-1 must have matched)')
    solution=Path(args[0]) if args else DEFAULT
    v.check(solution.exists(),f'{solution}: solution script missing (external input, see module docstring)')
    timeout,memory=(5340,1280) if mode=='record' else (600,768)
    with temporary_build_directory(prefix='host-lockstep-',parent=BUILD) as directory:
        run_bounded([sys.executable,__file__,'--worker',mode,directory,str(solution.resolve()),
            '-' if frames is None else str(frames),'-' if target is None else str(target),define or '-'],
            cwd=ROOT,timeout=timeout,memory_mib=memory,check=True)
if __name__=='__main__':main()

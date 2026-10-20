"""Host service graph versus the existing game_loop original journey.

Reuses game_loop.setup/Reference/Access.script and verification.OriginalMachine.
Only the independent platform provider profile changes: real register devices,
read-only host DOS results and BIOS tick memory replace the older finite raw
port/opaque DOS fixtures. Every loop boundary AND foreground poll compares RAM,
defined registers, planes, latches, DAC and CRTC. No instruction engine here.
"""
import copy
import ctypes as ct
import gc
import sys
import time
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools')]
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,write_json,sha
from host_support import Host,Event,POLL,OBSERVE,ROOT,v,loop as g,sources

DISPLAY=17044

class CheckpointVga:
    """State-only projection for the shared comparator, with no bus trace.

    C host traffic is not recorded. Empty traces on BOTH projections explicitly
    declare that narrower observation; no reference event is passed as C output.
    DAC/CRTC/attributes are compared separately below.
    """
    trace=()
    def __init__(self,device):self.device=device
    def state(self):
        d=self.device
        return (tuple(bytes(p) for p in d.planes),tuple(d.latches),tuple(d.seq),tuple(d.gc),d.si,d.gi)

class Platform:
    """Independent Python device provider; original execution stays shared."""
    def __init__(self,a):
        self.a=a;self.now=0;self.reload=0x4000;self.control=0x36;self.low=None
        self.pit_reads=0;self.latch=None;self.port61=0x15;self.epoch=0
        self.crtc=bytearray(32);self.crtc[0x13]=20;self.crtc[0x17]=0xe3;self.ci=0
        self.attr=bytearray(32);self.attr[:16]=bytes([0,1,2,3,4,5,6,7,16,17,18,19,20,21,22,23]);self.attr[0x10]=1;self.ai=0;self.attr_data=False
        self.dac=bytearray(768);self.dw=0;self.dr=0;self.dc=0;self.rc=0;self.mask=255;self.mode=0x0d
        self.clock=0
    def mode_set(self,request):
        d=self.a.device;self.mode=request&127
        if not request&128:
            for p in d.planes:p[:]=bytes(65536)
            self.a.memory[0xa0000:0xb0000]=bytes(65536)
        d.seq[:]=[0,0,15,0,6];d.gc[:]=[0,0,0,0,0,0,5,15,255]
        self.crtc[:]=bytes(32);self.crtc[0x13]=40 if self.mode==0x10 else 20;self.crtc[0x17]=0xe3
        self.attr[:16]=bytes([0,1,2,3,4,5,6,7,16,17,18,19,20,21,22,23] if self.mode==0x0d else [0,1,2,3,4,5,20,7,56,57,58,59,60,61,62,63]);self.attr[0x10]=1;self.attr[0x14]=0;self.mask=255
    def output(self,port,value):
        d=self.a.device
        if port==0x3c4:d.si=value
        elif port==0x3c5:d.seq[d.si]=value
        elif port==0x3ce:d.gi=value
        elif port==0x3cf:d.gc[d.gi]=value
        elif port in (0x3b4,0x3d4):self.ci=value
        elif port in (0x3b5,0x3d5):self.crtc[self.ci]=value
        elif port==0x3c0:
            if self.attr_data:self.attr[self.ai]=value
            else:self.ai=value&31
            self.attr_data=not self.attr_data
        elif port==0x3c8:self.dw=value;self.dc=0
        elif port==0x3c9:
            self.dac[self.dw*3+self.dc]=value&63;self.dc+=1
            if self.dc==3:self.dc=0;self.dw=(self.dw+1)&255
        elif port==0x43:
            if not value&0x30:self.latch=self.reload-(self.now-self.epoch)%self.reload;self.pit_reads=0
            else:self.control=value;self.low=None
        elif port==0x40:
            if self.low is None:self.low=value
            else:self.reload=(self.low|(value<<8)) or 65536;self.low=None;self.epoch=self.now
        elif port==0x61:self.port61=value
        else:v.check(port in (0x20,0x60,0x64),'unbound reference output')
    def input(self,port):
        if port in (0x3da,0x3ba):
            value=int(self.now%54>=40)|(8 if self.now%DISPLAY>=DISPLAY*9//10 else 0)
            self.now+=8;self.attr_data=False;return value
        if port==0x3c5:return self.a.device.seq[self.a.device.si]
        if port in (0x3b5,0x3d5):return self.crtc[self.ci]
        if port==0x60:return self.a.scan
        if port==0x61:return self.port61
        if port==0x64:return 0
        if port==0x40:
            count=self.latch if self.latch is not None else self.reload-(self.now-self.epoch)%self.reload
            value=(count>>(self.pit_reads*8))&255;self.pit_reads^=1
            if not self.pit_reads:self.latch=None
            return value
        raise v.OracleFailure(f'unbound reference input {port:04x}')

class Access(g.Access):
    def __init__(self,*args):super().__init__(*args);self.platform=Platform(self)
    def inp(self,port,flags,mask=v.FLAGS):
        value=self.platform.input(port);self.cursor+=1;self.emit('in',port,value,flags,mask);return value
    def out(self,port,value,flags,mask=v.FLAGS):
        self.platform.output(port,value);self.emit('out8',port,value,flags,mask)
    def out_word(self,port,value,flags,mask=v.FLAGS):
        self.platform.output(port,value&255);self.platform.output(port+1,value>>8)
        self.emit('out',port,value,flags,mask)

class Provider(g.Provider):
    def flags(self,flags,failed=False):return (flags&~1)|int(failed)
    def file(self,function,seg,off,flags):
        name=self.filename(seg,off).decode().lower();kind=self.kind(name.encode())
        value,count,returned=super().file(function,seg,off,flags)
        if not (kind=='level' and self.mem[v.physical(self.data,0x1f6b)]==1):self.payloads[kind]=g.asset(name)
        return value,0x20 if function==0x43 else count,returned
    def close(self,handle,value,flags):
        _,f=super().close(handle,value,flags);return 0,f

def provider(number):
    base=g.session.provider(number)
    def execute(a,r):
        p=a.platform
        if number==0x10:
            if r['ax']>>8==0x0f:r['ax']=0x5000|p.mode;r['bx']&=255;return 0
            if r['ax'] in (0x8d,0x90):p.mode_set(r['ax']);return 0
        if number==0x1a:
            p.clock=(r['cx']<<16)|r['dx'];return 0
        if number=='chain':
            p.clock+=1;a.word_write(0x40,0x6c,p.clock&65535,r['flags']);a.word_write(0x40,0x6e,p.clock>>16,r['flags'])
            a.out(0x20,0x20,r['flags']);return 0
        return base(a,r)
    return execute

def worker(directory):
    began=time.perf_counter()
    before=g.input_hashes()
    extra=set(sources())|set((ROOT/'c').glob('*.h'))|{ROOT/'host/platform_host.h',Path(__file__),ROOT/'tests/host_support.py',ROOT/'tools/hostbuild.py'}
    before.update({p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in extra})
    h=Host(directory)
    c,memory,r,device=g.setup();h.memory[:]=memory
    for i in range(4):h.vga.planes[i][:]=device.planes[i]
    for name in ('latches','seq','gc'):getattr(h.vga,name)[:]=getattr(device,name)
    h.vga.si=device.si;h.vga.gi=device.gi
    # Production constructor supplies the relocated DAT segment packet. Keep
    # all seeded fixture RAM for the actual comparison, including stack poison.
    seeded=bytes(memory);regs=v.Regs();assert h.call('post_startup',0x1010,ct.byref(regs)),h.call('error')
    h.memory[:]=seeded
    for i in range(4):h.vga.planes[i][:]=device.planes[i]
    for name in ('latches','seq','gc'):getattr(h.vga,name)[:]=getattr(device,name)
    h.vga.si=device.si;h.vga.gi=device.gi
    h.call('automatic_timer',0);h.call('set_limits',2500,500_000_000,0)
    original_access,original_provider,original_factory,original_video=g.Access,g.Provider,g.provider,g.menu.video_provider
    def video(a,incoming):a.platform.mode_set(incoming['ax']);return dict(incoming)
    g.Access,g.Provider,g.provider,g.menu.video_provider=Access,Provider,provider,video
    reference=g.Reference(c,bytearray(memory),dict(r),copy.deepcopy(device))
    rows=[];errors=[];overlays=[];last_overlay=None
    def compare(state,kind):
        ref=reference.advance();expected_status=ref['status'];a=reference.access
        # Shared comparator covers defined FLAGS and every canonical RAM byte.
        actual=dict(regs=state,memory=bytes(h.memory),status=0,events=(),device=CheckpointVga(h.vga))
        if actual['memory']!=ref['memory']:
            differences=[]
            for i,(x,y) in enumerate(zip(actual['memory'],ref['memory'])):
                if x!=y:differences.append((i,x,y))
                if len(differences)==40:break
            print('HOST RAM DIFF',differences,'DOS',reference.provider.trace,flush=True)
        checkpoint=dict(regs=ref['regs'],memory=ref['memory'],status=0,events=(),
            device=CheckpointVga(a.device),mask=ref['mask'])
        v.compare_states(f'host {kind} {state["ip"]:04x}',actual,checkpoint)
        v.require(bytes(h.vga.crtc)==a.platform.crtc,'CRTC differs')
        v.require(bytes(h.vga.dac)==a.platform.dac,'DAC differs')
        v.require(bytes(h.vga.attr)==a.platform.attr,'attribute registers differ')
        v.require(h.call('time')==a.platform.now,'virtual clock differs')
        if kind=='boundary':
            rows.append(dict(site=state['ip'],steps=ref['steps'],ram_sha256=sha(bytes(h.memory)),
                planes_sha256=sha(b''.join(bytes(p) for p in h.vga.planes)),dac_sha256=sha(bytes(h.vga.dac)),crtc=bytes(h.vga.crtc).hex()))
            print(f'HOST BOUNDARY {state["ip"]:04x} original_steps={ref["steps"]}',flush=True)
            write_json(BUILD/'host-journey-progress.json',dict(accepted=False,boundaries=rows,
                steps=ref['steps'],seconds=time.perf_counter()-began,input_hashes=before))
        a.reset_observations();reference.provider.trace=[]
        return expected_status
    def state(regs):return {n:getattr(regs.contents,n) for n in v.REG_NAMES}
    def overlay(q):
        nonlocal last_overlay
        if h.memory[v.physical(q['ds'],0x1f6b)]!=1 or last_overlay:return
        # Same pre-loader zero-minute input as game_loop.Provider. The file is
        # never modified; C DOS reads an explicit read-only input overlay.
        case=next(case for case in g.resources.cases() if case['name']=='real-selection-1')
        name=next(Path(path).name for path in g.resources.prepare(case)[-1] if Path(path).name.startswith('level'))
        payload=g.asset(name)
        records=[bytearray(g.resources.decode_section(payload[a:b])[0]) for a,b in g.resources.section_spans(payload)]
        for record in records:record[6:8]=b'\0\0'
        payload=b''.join(g.start.packed(bytes(record)) for record in records)
        data=(ct.c_uint8*len(payload)).from_buffer_copy(payload);overlays.append(data)
        v.check(h.call('file_overlay',name.encode(),data,len(payload)),'overlay rejected');last_overlay=True
    @POLL
    def poll(_,host,registers,site):
        try:
            q=state(registers);v.require(compare(q,'poll')==g.CHECKPOINT,'original missed poll')
            a=reference.access;events=a.script(q,site);reference.resume_poll=True
            if events is None:return 0xca11
            # Timed script events are ordered at the current PIT-clock instant;
            # no CPU-state or RAM input patch is used by the native platform.
            mouse=Event(h.call('time'),1,a.mouse[0],a.mouse[1],a.mouse[2]);v.check(h.call('enqueue',ct.byref(mouse)),'mouse queue')
            for number,scan,where in events:
                e=Event(h.call('time'),2 if number==9 else 3,0,0,scan)
                v.check(h.call('enqueue',ct.byref(e)),'IRQ queue')
            return 0
        except v.Mismatch as error:errors.append(str(error));return 0xca11
        except BaseException as error:
            import traceback;traceback.print_exc();v.callback_failure(error)
    @OBSERVE
    def observe(_,host,registers,kind):
        if errors or kind:return
        try:
            q=state(registers);v.require(compare(q,'boundary')==g.BOUNDARY,'original missed boundary')
            reference.access.boundary(q);reference.resume_boundary=True;overlay(q)
        except v.Mismatch as error:errors.append(str(error))
        except BaseException as error:
            import traceback;traceback.print_exc();v.callback_failure(error)
    h.call('set_hooks',None,poll,observe)
    try:
        out=h.call('run',ct.byref(v.Regs(**r)))
        v.require(not errors,errors[0] if errors else '')
        h.check();a=reference.access
        v.require(out.status==0 and out.registers.ip==0x4453,'journey final stop differs')
        v.require(a.sessions==3 and a.results==3 and a.typed==11,'journey incomplete')
        v.require([(ip,selection,success) for ip,selection,success in a.screens if ip in (0x454c,0x4551)]==
            [(0x454c,0,0),(0x4551,1,255),(0x4551,1,0)],'next/retry/outcome ownership differs')
        v.require(h.call('irqs')==sum(number==8 for number,_,_ in a.deliveries),'IRQ08 delivery count differs')
        m=reference.machine
        report=dict(accepted=True,scope='game-loop-host-platform-profile',boundaries=rows,steps=m.steps,
            polls=len(a.polls),sessions=a.sessions,results=a.results,seconds=time.perf_counter()-began,
            input_hashes=before,limits=dict(worker_seconds=2340,process_commit_mib=768,
                original_instructions=g.MAX_STEPS,original_events=g.MAX_EVENTS,polls=2500,host_accesses=500_000_000))
        v.check(before=={p:sha((ROOT/p).read_bytes()) for p in before},'host journey inputs changed during campaign')
        v.check({p.relative_to(ROOT).as_posix() for p in g.ASSETS}<=set(before),'unhashed journey asset')
        write_json(BUILD/'host-journey.json',report)
        print(f'PASS host_journey: {len(rows)} boundaries, {len(a.polls)} polls, {m.steps} original instructions',flush=True)
    except BaseException as error:
        write_json(BUILD/'host-journey-failure.json',dict(accepted=False,error=str(error),boundaries=rows,
            steps=reference.machine.steps,seconds=time.perf_counter()-began,input_hashes=before))
        raise
    finally:
        g.Access,g.Provider,g.provider,g.menu.video_provider=original_access,original_provider,original_factory,original_video
        h.close();del h;gc.collect()

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    with temporary_build_directory(prefix='host-journey-',parent=BUILD) as directory:
        run_bounded([sys.executable,__file__,'--worker',directory],cwd=ROOT,timeout=2340,memory_mib=768,check=True)
if __name__=='__main__':main()

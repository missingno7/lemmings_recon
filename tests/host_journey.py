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

PIT_HZ=1193182
# Standard IBM VGA BIOS CRTC tables (registers 00..18h), as host/platform_host.c.
CRTC={0x03:bytes([0x5f,0x4f,0x50,0x82,0x55,0x81,0xbf,0x1f,0x00,0x4f,0x0d,0x0e,0,0,0,0,0x9c,0x8e,0x8f,0x28,0x1f,0x96,0xb9,0xa3,0xff]),
      0x0d:bytes([0x2d,0x27,0x28,0x90,0x2b,0x80,0xbf,0x1f,0x00,0xc0,0,0,0,0,0,0,0x9c,0x8e,0x8f,0x14,0x00,0x96,0xb9,0xe3,0xff]),
      0x10:bytes([0x5f,0x4f,0x50,0x82,0x54,0x80,0xbf,0x1f,0x00,0x40,0,0,0,0,0,0,0x83,0x85,0x5d,0x28,0x0f,0x63,0xba,0xe3,0xff])}
SEQ1={0x03:0x00,0x0d:0x09,0x10:0x01}
MISC={0x03:0x67,0x0d:0x63,0x10:0xa3}

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
        self.a=a;self.now=0;self.reload=65536;self.control=0x36;self.low=None
        self.pit_reads=0;self.latch=None;self.port61=0x15;self.epoch=0
        self.crtc=bytearray(32);self.crtc[:25]=CRTC[0x0d];self.ci=0
        self.misc=MISC[0x0d];self.raster_epoch=0
        self.attr=bytearray(32);self.attr[:16]=bytes([0,1,2,3,4,5,6,7,16,17,18,19,20,21,22,23]);self.attr[0x10]=1;self.ai=0;self.attr_data=False
        self.dac=bytearray(768);self.dw=0;self.dr=0;self.dc=0;self.rc=0;self.mask=255;self.mode=0x0d
        self.clock=0
    def mode_set(self,request):
        d=self.a.device;self.mode=request&127
        if not request&128:
            for p in d.planes:p[:]=bytes(65536)
            self.a.memory[0xa0000:0xb0000]=bytes(65536)
        d.seq[:]=[0,SEQ1[self.mode],15,0,6];d.gc[:]=[0,0,0,0,0,0,5,15,255]
        self.crtc[:]=bytes(32);self.crtc[:25]=CRTC[self.mode];self.misc=MISC[self.mode];self.raster_epoch=self.now
        self.attr[:16]=bytes([0,1,2,3,4,5,6,7,16,17,18,19,20,21,22,23] if self.mode==0x0d else [0,1,2,3,4,5,20,7,56,57,58,59,60,61,62,63]);self.attr[0x10]=1;self.attr[0x14]=0;self.mask=255
    def output(self,port,value):
        d=self.a.device
        if port==0x3c4:d.si=value
        elif port==0x3c5:d.seq[d.si]=value
        elif port==0x3ce:d.gi=value
        elif port==0x3cf:d.gc[d.gi]=value
        elif port in (0x3b4,0x3b5,0x3ba,0x3d4,0x3d5):
            if (port<0x3c0)==bool(self.misc&1):return  # other addressing: not decoded
            if port in (0x3b4,0x3d4):self.ci=value
            elif port!=0x3ba:self.crtc[self.ci]=value
        elif port==0x3c2:self.misc=value
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
    def status(self):
        """Input status 1 from the CRTC raster, the same formula as the C host."""
        c=self.crtc;ov=c[7];seq1=self.a.device.seq[1]
        clock=28322000 if (self.misc>>2)&3==1 else 25175000
        width=8 if seq1&1 else 9;pixel=clock//2 if seq1&8 else clock
        line_px=(c[0]+5)*width;display_px=(c[1]+1)*width
        total=(c[6]|((ov&1)<<8)|((ov&0x20)<<4))+2
        display_lines=(c[0x12]|((ov&2)<<7)|((ov&0x40)<<3))+1
        start=c[0x10]|((ov&4)<<6)|((ov&0x80)<<2);span=((c[0x11]&15)-start)&15
        end=start+(span or 16)
        dt=self.now-self.raster_epoch;px=(dt//PIT_HZ)*pixel+((dt%PIT_HZ)*pixel)//PIT_HZ
        inside=px%(line_px*total);line=inside//line_px;x=inside%line_px
        return (0 if line<display_lines and x<display_px else 1)|(8 if start<=line<end else 0)
    def input(self,port):
        if port in (0x3da,0x3ba):
            if (port==0x3ba)==bool(self.misc&1):return 0xff
            value=self.status();self.now+=4;self.attr_data=False;return value
        if port==0x3c5:return self.a.device.seq[self.a.device.si]
        if port in (0x3b5,0x3d5):return 0xff if (port==0x3b5)==bool(self.misc&1) else self.crtc[self.ci]
        if port==0x3cc:return self.misc
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
            # Declared machine (host/README.md): colour VGA BIOS answers.
            if r['ax']==0x1a00:r['ax']=(r['ax']&0xff00)|0x1a;r['bx']=8;return 0
            if r['ax']>>8==0x12 and r['bx']&255==0x10:r['bx']=0x0003;r['cx']=0x0f09;return 0
            if r['ax'] in (0x8d,0x90):p.mode_set(r['ax']);return 0
        if number==0x1a:
            p.clock=(r['cx']<<16)|r['dx'];return 0
        if number=='chain':
            p.clock+=1;a.word_write(0x40,0x6c,p.clock&65535,r['flags']);a.word_write(0x40,0x6e,p.clock>>16,r['flags'])
            a.out(0x20,0x20,r['flags']);return 0
        return base(a,r)
    return execute

def startup_menu(directory,library):
    """Handoff check: native DOS startup state -> original and native menu.

    Full entry parity belongs to startup.py. This parent checks the returned
    state/stack, generated banks, sound fallback and later menu consumers.
    """
    h=Host(directory,library);rows=[];errors=[]
    try:
        boot=h.call('boot',0x1010,b'/v /o /a',1)
        v.check(boot.status==0,'host native startup stopped: '+str(h.call('error')))
        r={n:getattr(boot.registers,n) for n in v.REG_NAMES};ds=r['ds']
        v.check(h.memory[v.physical(ds,0x25A7)]==h.memory[v.physical(ds,0x1F71)]==1,'sound fallback producer differs')
        c=g.setup()[0]|dict(name='host-native-startup-menu',game_data_segment=ds)
        memory=bytearray(h.memory);d=v.new_device(0)
        for i in range(4):d.planes[i][:]=h.vga.planes[i]
        for name in ('latches','seq','gc'):getattr(d,name)[:]=getattr(h.vga,name)
        d.si=h.vga.si;d.gi=h.vga.gi
        reference=g.Reference(c,memory,r,copy.deepcopy(d));a=reference.access;p=a.platform
        p.now=h.call('time');p.reload=v.get16(h.memory,ds,0x1FC9) or 65536;p.epoch=p.now
        p.raster_epoch=h.call('raster_epoch');p.misc=h.call('in',0x3cc)
        p.crtc[:]=h.vga.crtc;p.ci=h.vga.ci;p.attr[:]=h.vga.attr;p.ai=h.vga.ai;p.attr_data=bool(h.vga.attr_data)
        p.dac[:]=bytes(h.vga.dac);p.mode=h.vga.mode;p.mask=h.vga.pel_mask
        p.dw=h.vga.dac_write;p.dr=h.vga.dac_read;p.dc=h.vga.dac_component;p.rc=h.vga.dac_read_component
        h.call('automatic_timer',0);h.call('set_limits',500,500_000_000,0)
        def compare(registers,kind):
            state={n:getattr(registers.contents,n) for n in v.REG_NAMES};ref=reference.advance()
            actual=dict(regs=state,memory=bytes(h.memory),status=0,events=(),device=CheckpointVga(h.vga))
            checkpoint=dict(regs=ref['regs'],memory=ref['memory'],status=0,events=(),device=CheckpointVga(a.device),mask=ref['mask'])
            v.compare_states('startup->menu '+kind,actual,checkpoint)
            v.require(bytes(h.vga.crtc)==p.crtc and bytes(h.vga.dac)==p.dac and bytes(h.vga.attr)==p.attr,'startup menu display differs')
            v.require(h.call('time')==p.now,'startup menu clock differs')
            rows.append(dict(kind=kind,site=state['ip'],steps=ref['steps'],ram_sha256=sha(bytes(h.memory)),planes_sha256=sha(b''.join(bytes(p) for p in h.vga.planes))))
            a.reset_observations();reference.provider.trace=[]
            return state,ref['status']
        @POLL
        def poll(_,host,registers,site):
            try:
                state,status=compare(registers,'poll');v.require(status==g.CHECKPOINT,'startup menu missed poll')
                reference.resume_poll=True
                return 0xCA11 if site==0x446D else 0
            except v.Mismatch as error:errors.append(str(error));return 0xCA11
            except BaseException as error:v.callback_failure(error)
        @OBSERVE
        def observe(_,host,registers,kind):
            if kind or errors:return
            try:
                state,status=compare(registers,'boundary');v.require(status==g.BOUNDARY,'startup menu missed boundary');reference.resume_boundary=True
            except v.Mismatch as error:errors.append(str(error))
            except BaseException as error:v.callback_failure(error)
        h.call('set_hooks',None,poll,observe)
        out=h.call('run',ct.byref(boot.registers))
        v.require(not errors,errors[0] if errors else '')
        v.check(out.registers.ip==0x446D,'startup menu handoff incomplete');h.check()
        return dict(accepted=True,rows=rows,steps=reference.machine.steps,sound_option=1,sound_index=1)
    finally:h.close()

def worker(directory):
    # Raster waits poll the status port as on the declared 286-class machine, so
    # the journey executes more original instructions than the shared default.
    g.MAX_STEPS=200_000_000
    began=time.perf_counter()
    before=g.input_hashes()
    extra=set(sources())|set((ROOT/'c').glob('*.h'))|{ROOT/'host/platform_host.h',Path(__file__),ROOT/'tests/host_support.py',ROOT/'tools/hostbuild.py',ROOT/'assets/russell.dat'}
    before.update({p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in extra})
    h=Host(directory)
    c,memory,r,device=g.setup();h.memory[:]=memory
    for i in range(4):h.vga.planes[i][:]=device.planes[i]
    for name in ('latches','seq','gc'):getattr(h.vga,name)[:]=getattr(device,name)
    h.vga.si=device.si;h.vga.gi=device.gi
    # Bind relocated DAT selectors without touching the constructed reference.
    h.call('bind_image',r['cs'])
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
        boot_menu=startup_menu(directory,h.dll)
        report=dict(accepted=True,scope='game-loop-host-platform-profile',boundaries=rows,steps=m.steps,startup_menu=boot_menu,
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
    if len(sys.argv)==3 and sys.argv[1]=='--menu-worker':
        original_access,original_provider,original_factory,original_video=g.Access,g.Provider,g.provider,g.menu.video_provider
        g.Access,g.Provider,g.provider=Access,Provider,provider
        g.menu.video_provider=lambda a,incoming:(a.platform.mode_set(incoming['ax']) or dict(incoming))
        try:
            h=Host(sys.argv[2]);h.close()
            print(startup_menu(sys.argv[2],h.dll),flush=True)
        finally:g.Access,g.Provider,g.provider,g.menu.video_provider=original_access,original_provider,original_factory,original_video
        return
    if sys.argv[1:]==['--focus-menu']:
        with temporary_build_directory(prefix='host-menu-',parent=BUILD) as directory:
            run_bounded([sys.executable,__file__,'--menu-worker',directory],cwd=ROOT,timeout=180,memory_mib=768,check=True)
        return
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    with temporary_build_directory(prefix='host-journey-',parent=BUILD) as directory:
        run_bounded([sys.executable,__file__,'--worker',directory],cwd=ROOT,timeout=3540,memory_mib=768,check=True)
if __name__=='__main__':main()

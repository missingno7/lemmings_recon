"""Connected display detection, PIT calibration and sprite-slot initialization."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
from cbuild import build,source_files
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,sha,write_json

RANGES=((0xFB2,0xFF8),(0x13DC,0x14C1),(0x14C2,0x1530),(0x15AD,0x1644))
INS={i.address:i for a,b in RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
EDGES=v.direct_jump_edges(INS)
ENTRIES=(0x13DC,0x1410,0x1462,0x1490,0x14A0,0x14E0,0x1523,0x15AD,0x1602,0xFB2)
TARGETS=(0x1410,0x1462,0x1490,0x14A0)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=600,384,2_000_000,1_000_000
REPORT=BUILD/'video-probe-differential.json'
class Services(ct.Structure):
    _fields_=[('bios',ct.POINTER(v.InterruptService)),('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus))]
class Result(ct.Structure):
    _fields_=[('registers',v.Regs),('status',ct.c_uint16),('child_status',ct.c_uint16),('service_status',ct.c_uint16)]

def cases():
    rows=[]
    def add(name,entry,**kw):rows.append(dict(name=name,entry=entry,**kw))
    for load in v.LOADS:
        for entry in (0,7,9):add(f'connected-{entry}-{load:04x}',entry,load=load,probe_first=True)
    for name,kw in (('absent',dict(dcc=False,ega=False,color=False,mono=False)),
                    ('ega-color',dict(dcc=False,ega_config=0)),('ega-mono',dict(dcc=False,ega_config=4)),
                    ('color-only',dict(dcc=False,ega=False,mono=False)),
                    ('mono-basic',dict(dcc=False,ega=False,color=False,mono_constant=True)),
                    ('mono-81',dict(dcc=False,ega=False,color=False,mono_id=0x10)),
                    ('mono-80',dict(dcc=False,ega=False,color=False,mono_id=0x20)),
                    ('mono-82',dict(dcc=False,ega=False,color=False,mono_id=0x50)),
                    ('swap-mono',dict(dcc=False,ega=False,mono_constant=True,video_mode=7)),
                    ('keep-color',dict(dcc=False,ega=False,mono_constant=True,video_mode=3)),
                    ('df',dict(flags=0x6D7,backward=True)),
                    ('unbound',dict(probe_first=True,unknown=True,expected=6)),
                    ('live-saved-loop',dict(probe_first=True,patch='saved-loop')),
                    ('changed-return',dict(probe_first=True,patch='probe-return',expected=4))):
        add('detect-'+name,0,**kw)
    for primary,secondary in ((0,0),(1,0),(2,1),(5,2),(7,0),(0,1),(255,254)):
        add(f'dcc-{primary}-{secondary}',1,primary=primary,secondary=secondary)
    add('detect-high-primary',0,probe_first=True,primary=7,secondary=2)
    add('detect-high-secondary',0,probe_first=True,primary=2,secondary=7)
    add('dcc-absent',1,dcc=False)
    for cfg in (0,2,4,6,8,10,254):add('ega-'+str(cfg),2,ega_config=cfg)
    add('ega-absent',2,ega=False)
    for entry in (3,4,5):
        add(f'crtc-{entry}-present',entry)
        add(f'crtc-{entry}-absent',entry,color=False,mono=False)
    for entry in (6,):
        add('pair-first',entry,pair_first=0)
        add('pair-second',entry,pair_first=1)
    for mode in (0,200,400,1234):
        for old in (0,0x4567):add(f'calibrate-{mode}-{old}',7,mode=mode,old=old,probe_first=True)
    add('calibrate-slow-color',7,mode=0,probe_first=True,primary=2)
    add('calibrate-signed-type',7,mode=0,dcc=False,ega_config=64)
    for name,kw in (('fixed',dict(option=255)),('byte-equality',dict(option=254)),
                    ('saved-live',dict(old=0x4321,patch='old-reload')),
                    ('detect-return',dict(mode=0,probe_first=True,patch='detect-return',expected=4)),
                    ('measure-return',dict(patch='measure-return',expected=4)),
                    ('underflow-count',dict(pit=0xFFFF)),('zero-count',dict(pit=0))):
        add('calibrate-'+name,7,**kw)
    for count in (1,2,0):add(f'measure-{count}',8,count=count)
    add('measure-dl-wrap',8,base=0xFFFF)
    add('measure-stalls',8,waits=True)
    for entry in (1,9):
        for name,kw in (('unbound',dict(no_bios=True,expected=3,child_status=1)),
                        ('stop',dict(provider_stop=77,expected=3,child_status=2,service_status=77)),
                        ('changed-iret',dict(iret_ip=0xD234,expected=3,child_status=3)),
                        ('returned-state',dict(returned_state=True))):
            add(f'bios-{entry}-{name}',entry,**kw)
        add(f'bios-{entry}-returned-stack',entry,returned_stack=True)
        add(f'bios-{entry}-returned-flags',entry,returned_flags=True)
    add('bios-live-vector',9,wrong_vector=True,expected=3,child_status=1)
    for name,kw in (('stack-wrap',dict(sp=1)),('physical-wrap',dict(ss=0xFFFF,sp=0xF)),
                    ('stack-slot-alias',dict(ss=0x6000,sp=0x2E)),
                    ('outer-live',dict(patch='outer-return')),('missing-word',dict(missing_word_out=True,expected=5))):
        add('video-'+name,9,**kw)
    for entry in (5,8):
        add(f'ports-{entry}-in',entry,missing_in=True,expected=1)
        add(f'ports-{entry}-out',entry,missing_out=True,expected=2)
    return [dict(load=v.LOADS[0],seed=0x15AD+i,flags=0xAD7,mode=400,old=0,option=0,
                 pit=0x1234,count=2,base=0x3D4,primary=7,secondary=0,dcc=True,ega=True,
                 ega_config=0,color=True,mono=True,mono_id=0x50,pair_first=0,expected=0,
                 child_status=0,service_status=0)|c for i,c in enumerate(rows)]

def setup(c):
    memory,device=v.initial_memory(c);r=v.default_regs(c['load'],c['seed'],ss=c.get('ss',0x9000),sp=c.get('sp',0x8000),ds=0x6000,flags=c['flags'])
    r.update(ip=ENTRIES[c['entry']],di=0x2006,bx=c['count'],dx=0x3D4,ax=0xA103)
    ds=r['ds']
    for seg in (ds,0x7000):
        for off,value in ((0x1FDA,c['base']),(0x1FC9,c['old']),(0x2011,c['mode']),
                          (0x2006,c['pair_first']),(0x2008,0)):
            v.put16(memory,seg,off,value)
        v.put8(memory,seg,0x200E,c['option'])
        # Native data records remain live; the first flag is not set by Detect.
        for n,target in enumerate(TARGETS):
            v.put8(memory,seg,0x2013+3*n,255 if n==0 and c.get('probe_first') else 0)
            v.put16(memory,seg,0x2014+3*n,0xD234 if n==0 and c.get('unknown') else target)
    if c.get('backward'):
        v.put8(memory,ds,0x2013,0x14);v.put8(memory,ds,0x2012,0x10)
        for off in (0x2010,0x200D,0x200A):v.put8(memory,ds,off,0)
    v.put16(memory,r['ss'],r['sp'],0xD00D)
    v.put16(memory,0,0x40,0x101 if c.get('wrong_vector') else 0x100);v.put16(memory,0,0x42,0xB000)
    return memory,r,device

class Access(v.BusAccess):
    def __init__(self,*args):
        super().__init__(*args,max_events=MAX_EVENTS,packed_events=True)
        self.crtc={0x3B5:0xA5,0x3D5:0xA5};self.status_reads=0;self.mono_reads=0;self.pit_reads=0
        self.outputs=[]
    def access(self,kind,address,flags,mask=v.FLAGS,value=None):
        got=super().access(kind,address,flags,mask,value);patch=self.c.get('patch');sp=self.r['sp'];ss=self.r['ss']
        if patch not in self.providers:
            if patch=='outer-return' and kind=='write' and address==v.physical(self.r['ds'],0x2E):self.patch(ss,sp,0xBEAD,patch)
            if patch=='old-reload' and kind=='write' and address==v.physical(self.r['ds'],0x1FC9):self.patch(ss,(sp-2)&65535,0x4567,patch)
        return got
    def inp(self,port,flags,mask=v.FLAGS):
        c=self.c
        if port in (0x3B5,0x3D5):value=self.crtc[port] if c['mono' if port==0x3B5 else 'color'] else 0xFF
        elif port==0x3BA:
            self.mono_reads+=1
            value=0 if c.get('mono_constant') or self.mono_reads==1 else 128 if self.mono_reads==2 else c['mono_id']
        elif port==((c['base']&0xFF00)|((c['base']+6)&255)):
            self.status_reads+=1
            if c.get('waits'):
                value=(0,0,8,8,8,0)[self.status_reads-1] if self.status_reads<=6 else (1,1,0,0,0,1)[(self.status_reads-7)%6]
            else:value=8 if self.status_reads==1 else 0 if self.status_reads==2 else (self.status_reads-3)%2
        elif port==0x40:
            value=(c['pit']>>(8*self.pit_reads))&255;self.pit_reads+=1;v.check(self.pit_reads<=2,'PIT read budget exhausted')
        else:raise v.OracleFailure(f'undeclared input {port:04X}')
        self.cursor+=1;self.emit('in',port,value,flags,mask)
        patch=c.get('patch')
        if patch=='measure-return' and patch not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-4)&65535,0xD234,patch)
        return value
    def out(self,port,value,flags,mask=v.FLAGS):
        v.check(port in (0x3B4,0x3B5,0x3D4,0x3D5,0x43,0x40),'undeclared byte output')
        self.emit('out8',port,value,flags,mask);self.outputs.append((port,value))
        if port in self.crtc:self.crtc[port]=value
    def out_word(self,port,value,flags,mask=v.FLAGS):
        v.check(value==0x1613,'unexpected setup CRTC word');self.emit('out',port,value,flags,mask)

def bios_provider(access,r):
    c=access.c;entry=dict(r);ax=r['ax'];v.check(len(access.service_events)<16,'BIOS service budget exhausted')
    if ax==0x1A00:
        r['ax']=(r['ax']&0xFF00)|(0x1A if c['dcc'] else 0)
        r['bx']=c['primary']|(c['secondary']<<8)
    elif ax>>8==0x12:
        r['bx']=(r['bx']&0xFF00)|(0 if c['ega'] else 0x10);r['cx']=(r['cx']&0xFF00)|c['ega_config']
    elif ax>>8==0xF:r['ax']=(r['ax']&0xFF00)|c.get('video_mode',3)
    else:v.check(ax==0x8D,'undeclared BIOS mode request')
    if c.get('returned_state'):
        r.update(ds=0x7000,es=0x7100,di=0x2200,bp=0xABCD)
        access.word_write(0x7000,0x2200,0,r['flags']);access.word_write(0x7000,0x2202,0,r['flags'])
    for name,bias in (('probe-return',6),('detect-return',4)):
        if c.get('patch')==name:access.patch(access.r['ss'],(access.r['sp']-bias)&65535,0xD234,name)
    if c.get('patch')=='saved-loop':access.patch(access.r['ss'],(access.r['sp']-4)&65535,1,'saved-loop')
    if 'iret_ip' in c:access.word_write(r['ss'],r['sp'],c['iret_ip'],r['flags'])
    if c.get('returned_stack'):
        values=[access.word_read(r['ss'],(r['sp']+2*n)&65535,r['flags']) for n in range(4)]
        for n,value in enumerate(values):access.word_write(0x8800,0x4000+2*n,value,r['flags'])
        r.update(ss=0x8800,sp=0x4000)
    if c.get('returned_flags'):access.word_write(r['ss'],(r['sp']+4)&65535,0x6D7,r['flags'])
    access.service_events.append(dict(entry=entry,returned=dict(r)))
    return c.get('provider_stop',0)

class Machine(v.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        frames=[];failed=[];self.child_status=0
        access=Access(c,memory,r,device)
        def before(m,i):
            if i.mnemonic in ('in','out') and c.get('missing_in' if i.mnemonic=='in' else 'missing_out'):
                m.stop(1 if i.mnemonic=='in' else 2);return True
            if i.address==0x1407 and m.state()['ax'] not in TARGETS:m.stop(6);return True
            if c.get('missing_word_out') and i.address==0xFBF:m.stop(5);return True
            if i.mnemonic=='call':frames.append((i.address,i.address+i.size))
            return False
        def expected(m,off):
            v.check(bool(frames),'undeclared probe child return');failed[:]=[frames.pop()];return {failed[-1][1]}
        def interrupt(m,number):
            v.check(number==0x10,'undeclared BIOS interrupt')
            m.software_interrupt(0x10,m.state()['ip'],(0xB000,0x100),None if c.get('no_bios') else bios_provider)
            if m.stopped:m.child_status=m.status;m.status=3
        super().__init__(c,memory,r,device,core,instructions=INS,access=access,
            outer_returns=lambda m,off:not frames,
            child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            before=before,interrupt=interrupt,changed_return_status=4,max_steps=MAX_STEPS)
    def run(self):
        out=super().run();out['child_status']=self.child_status;out['service_status']=self.service_status;out['services']=self.access.service_events
        out['hardware']=(self.access.crtc,self.access.outputs);return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'video-probe-{mutation}.dll',mutation,'video_probe')))
        self.fns={}
        for core in (True,False):
            fn=getattr(self.lib,'lmn_video_probe_'+('core' if core else 'adapter'))
            fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_int,ct.POINTER(Services)];fn.restype=Result;self.fns[core]=fn
    def run(self,c,memory,r,device,core):
        memory,device=bytearray(memory),copy.deepcopy(device);access=Access(c,memory,r,device)
        cb=v.NativeCallbacks(access,missing_in=c.get('missing_in'),missing_out=c.get('missing_out'))
        if c.get('missing_word_out'):cb.bus.out_word=v.OUT()
        handler=cb.interrupt(bios_provider);binding=v.InterruptService(None,handler,0xB000,0x100)
        services=Services(None if c.get('no_bios') else ct.pointer(binding),ct.pointer(cb.ports),ct.pointer(cb.bus))
        regs=v.Regs(**r);out=self.fns[core]((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(regs),c['entry'],ct.byref(services))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,child_status=out.child_status,
            service_status=out.service_status,memory=memory,device=device,events=access.events,providers=access.providers,
            cursor=access.cursor,services=access.service_events,hardware=(access.crtc,access.outputs))

def compare(native,c,core):
    memory,r,device=setup(c);ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    v.check((ref['status'],ref['child_status'],ref['service_status'])==(c['expected'],c['child_status'],c['service_status']),c['name']+': unexpected stop')
    actual=native.run(c,memory,r,device,core);v.compare_states(c['name'],actual,ref)
    v.require(actual['hardware']==ref['hardware'],c['name']+': device model differs')
    if c['entry']==9 and not ref['status']:
        expected=(0x6170,0x64D9,0x65D8,0x66D7,0x6817,0x6957,0x6A97,0x6BDB,0x6CFC)
        v.check(tuple(v.get16(ref['memory'],ref['regs']['ds'],0x2E+2*n) for n in range(9))==expected,'sprite callbacks differ')
    if c['entry']==7 and not ref['status'] and not c.get('patch'):
        expected=0x4000 if c['option']==255 else c['old'] or (0xFFFF-c['pit'])
        v.check(v.get16(ref['memory'],ref['regs']['ds'],0x1FC9)==expected,'independent reload differs')
    if c.get('patch'):v.check(c['patch'] in ref['providers'],'unused live-word fixture')
    return ref

def hashes():
    paths={'tests/video_probe.py','tests/verification.py','tests/minimap_vga.py','tools/cbuild.py',
        'tools/difftest.py','tools/bounded_process.py','tools/common.py','tools/unpack.py',
        'metadata/oracle.json','metadata/toolchain-lock.json','assets/vgalemmi.exe',
        'c/lemmings_sym.h','c/regs.h','c/special_blit.h','c/aligned_read_mask.h','src/entry_services.asm','src/image_tail.asm'}
    for path in source_files('video_probe'):paths|={path.relative_to(ROOT).as_posix(),path.with_suffix('.h').relative_to(ROOT).as_posix()}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

MUTANTS=((1,'connected-9-1010'),(2,'detect-df'),(3,'calibrate-signed-type'),
         (4,'calibrate-400-17767'),(5,'detect-changed-return'),(6,'crtc-5-present'),
         (7,'calibrate-400-0'),(8,'calibrate-byte-equality'))
def worker(directory,snapshot,selected):
    before=hashes();v.check(before==json.loads(Path(snapshot).read_text()),'probe inputs changed')
    native=Native(directory);rows=[];sites=set();edges=set()
    for c in cases():
        if selected and c['name'] not in selected:continue
        for core in (True,False):
            ref=compare(native,c,core);sites.update(ref['sites']);edges.update(ref['edges'])
            rows.append(dict(case=c['name'],core=core,steps=ref['steps'],events=len(ref['events']),status=ref['status']))
            del ref;gc.collect()
        print('CHECKED '+c['name'],flush=True)
    if selected:return
    v.check(set(INS)<=sites,'missing probe sites: '+str(sorted(set(INS)-sites)))
    v.check(EDGES<=edges,'missing probe outcomes: '+str(sorted(EDGES-edges)))
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in MUTANTS:
        try:compare(Native(directory,mutation),lookup[name],True)
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise v.OracleFailure('surviving probe mutant')
    v.check(before==hashes(),'probe inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(v.IMAGE),case_count=len(cases()),comparison_count=len(rows),
        native_code_ranges=[list(p) for p in RANGES],known_connected_bytes=sum(i.size for i in INS.values()),
        executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),mutation_count=len(mutants),mutations=mutants,
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),rows=rows,input_hashes=before,
        limits=dict(worker_seconds=SECONDS,windows_process_mib=MEMORY_MIB,windows_tree_mib=MEMORY_MIB+256,instructions_each=MAX_STEPS,events_each=MAX_EVENTS),
        domain='Video probes13DC..1530(excludingUNKNOWN14C1),calibration15AD/1602 and game-video0FB2. Four native probe callbacks,live DS/SS/flags/RET,full bound INT10/IRET,canonical RAM,VGA-independent finite CRTC/raster/PIT providers. Unknown callbacks stop before CALL1407. Quiescent external IRQ/TFclear;device timing,03E7/game and native platform remain open.'))
    print(f'PASS video probe: {len(rows)} comparisons,{len(sites)} sites,{len(EDGES)} outcomes,{len(mutants)} mutants',flush=True)
def main():
    if len(sys.argv)>=4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3],sys.argv[4:]);return
    selected=sys.argv[2:] if len(sys.argv)>1 and sys.argv[1]=='--focus' else []
    if sys.argv[1:] and not selected:raise SystemExit('usage: video_probe.py [--focus CASE ...]')
    if not selected:REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='video-probe-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot),*selected],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

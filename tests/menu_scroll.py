"""Connected menu scroll/copy entries using the shared bounded verifier."""
import copy
import ctypes as ct
import gc
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
import menu_animation as fixtures
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import BUILD,sha,write_json
check=base.check
physical,put16,get16=base.physical,base.put16,base.get16
State,FIELDS=fixtures.State,fixtures.FIELDS
ENTRIES=(0x7CBC,0x7CE6,0x7D0D,0x7D8D,0x7DB7,0x7E65)
RANGES=((0x7CBC,0x7E76),)
OWN={i.address:i for i in base.MD.disasm(base.IMAGE[0x7CBC:0x7E76],0x7CBC)}
SWAP={i.address:i for i in base.MD.disasm(base.IMAGE[0x4C20:0x4C47],0x4C20)}
INS=OWN|fixtures.RENDER|SWAP
EDGES=base.direct_jump_edges(OWN)
RETURNS=({0x7E75},{0x7E75},{0x7D1B,0x7D8C},{0x7DB6},{0x7E2E},{0x7E75})
CHILD={0x99E7:{0x884F},0x9A0B:{0x884F},0x9A14:{0x884F},0x9A8E:{0x885E},
       0x7DB6:{0x7CE0,0x7D33},0x7E2E:{0x7D54},0x7E75:{0x7D10,0x7E49},0x4C46:{0x4C27}}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=570,384,600_000,220_000
REPORT=BUILD/'menu-scroll-differential.json'
FIXTURES=set()
for module in tuple(sys.modules.values()):
    name=getattr(module,'__file__',None)
    if not name:continue
    path=Path(name).resolve()
    if path.suffix=='.py' and path.is_relative_to(ROOT) and path.parts[-2] in ('tests','tools'):
        FIXTURES.add(path.relative_to(ROOT).as_posix())
class Result(ct.Structure):
    _fields_=[('state',State),('code_segment',ct.c_uint16),('continuation',ct.c_uint16),('status',ct.c_int)]

def cases():
    rows=[]
    for entry in range(6):
        rows.append(dict(name=f'e{entry}-ordinary',entry=entry))
        for load in base.LOADS:rows.append(dict(name=f'e{entry}-load-{load:04x}',entry=entry,load=load,pinned=True))
        for name,kw in (('df',dict(flags=0x6D7)),('stack-wrap',dict(sp=0)),
                        ('stack-physical-wrap',dict(ss=0xFFFF,sp=0xF,expected=2 if entry in (0,1,2,5) else 0))):
            rows.append(dict(name=f'e{entry}-{name}',entry=entry,**kw))
    for char in (0,0x0D,0x1F,0x20,0x21,0x22,0x41,0x7F,0xFF):
        rows.append(dict(name=f'glyph-{char:02x}',entry=4,char=char))
    for column in (0,1,34,35,127,255):rows.append(dict(name=f'tile-{column}',entry=3,char=column))
    for phase in (0,1,8,12,0xFFFC,0xFFFF):rows.append(dict(name=f'tick-phase-{phase:04x}',entry=2,phase=phase))
    for name,kw in (('space',dict(text=b' ')),('ordinary',dict(text=b'A')),
                    ('ff',dict(text=b'\xffB')),('cr',dict(text=b'\r',restart=b'C')),
                    ('ff-cr',dict(text=b'\xff\r')),('ff-ff',dict(text=b'\xff\xff')),
                    ('cr-ff',dict(text=b'\r',restart=b'\xff')),
                    ('df-text',dict(text=b'A',flags=0x6D7))):
        rows.append(dict(name='tick-text-'+name,entry=2,phase=12,**kw))
    for pause in (1,2,100,0x8000,0xFFFF):rows.append(dict(name=f'pause-{pause}',entry=2,pause=pause))
    for entry in (0,1,2,5):
        for patch,status in (('far-ip',2),('far-cs',2),('inner-near',1)):
            rows.append(dict(name=f'e{entry}-{patch}',entry=entry,patch=patch,expected=status,dirty=0xFF))
    rows += [dict(name='draw-live-phase',entry=1,patch='phase'),
             dict(name='tick-live-pause',entry=2,pause=2,patch='pause'),
             dict(name='initialize-live-saved-ax',entry=0,patch='saved-ax'),
             dict(name='initialize-changed-near',entry=0,patch='near-ip',expected=2),
             dict(name='tile-live-saved-ds',entry=3,patch='saved-ds'),
             dict(name='glyph-live-saved-ds',entry=4,patch='saved-ds'),
             dict(name='tile-word-ffff',entry=3,sp=0xFFFF),
             dict(name='glyph-word-ffff',entry=4,sp=0xFFFF),
             dict(name='tile-destination-wrap',entry=3,es=0xFFFF),
             dict(name='tile-destination-vga',entry=3,es=0xA000),
             dict(name='glyph-destination-vga',entry=4,es=0xA000)]
    return [dict(load=0x1010,seed=0x7CBC+i,entry=0,flags=0xD7,phase=4,pause=0,char=0x41)|c for i,c in enumerate(rows)]

def setup(c):
    memory,device=base.initial_memory(c);ds=c.get('ds',(c['load']+0x9A9)&0xFFFF)
    r=base.default_regs(c['load'],c['seed'],ds=ds,ss=c.get('ss',0x6000),sp=c.get('sp',0x9000),es=c.get('es',0x7000),flags=c['flags'])
    r.update(ip=ENTRIES[c['entry']],ax=0 if c['entry']==5 else 0xBE00|c['char'],si=0x1C10,dx=48,cx=0x410,bp=0)
    for frame in dict.fromkeys((ds,(c['load']+0x9A9)&0xFFFF)):
        for off,value in ((0x1FEE,0x4000),(0x1FF0,0x7000),(0x1FE4,0x5000),(0x1F76,0),(0x1F78,0x6D60),
                          (0x1F7A,0),(0x1FDA,0x3D4),
                          (0x66F0,350),(0x66F2,640),(0x66F4,80),(0x26,0x2000),
                          (0x1D,0x5900),(0x1F,0x5800),(0x21,c['phase']),(0x23,c['pause'])):
            put16(memory,frame,off,value,device)
        base.sync_memory_byte(memory,device,frame,0x2A,c.get('dirty',0))
    for offset,key,default in ((0x5800,'text',b'A'),(0x5900,'restart',b'B')):
        for i,v in enumerate(c.get(key,default)):base.sync_memory_byte(memory,device,ds,offset+i,v)
    if c.get('pinned'):
        for segment,data in zip((0x4000,0x4F21),fixtures.resource_banks()):
            for i,v in enumerate(data):base.sync_memory_byte(memory,device,segment,i,v)
    put16(memory,r['ss'],r['sp'],0xD00D,device)
    return memory,r,device

class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):super().__init__(c,memory,r,device,max_events=MAX_EVENTS,packed_events=True)
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        got=super().access(kind,address,flags,mask,value);patch=self.c.get('patch')
        if self.c.get('swap'):return got
        if patch in self.providers:return got
        if kind=='read' and address==physical(self.r['ds'],0x26) and patch=='inner-near':
            # The first dirty call's actual near frame is below the renderer's far frame.
            depth={0:6,1:6,2:8,5:6}[self.c['entry']]
            self.patch(self.r['ss'],(self.r['sp']-depth)&0xFFFF,0xD234,patch)
        if kind=='read' and address==physical(0x5000,0x4C10) and patch in ('saved-ax','near-ip','saved-ds'):
            depth=4 if patch=='saved-ax' else 6 if patch=='near-ip' else 2
            self.patch(self.r['ss'],(self.r['sp']-depth)&0xFFFF,0xD234 if patch=='near-ip' else 0x0034 if patch=='saved-ax' else 0x6100,patch)
        # Glyph reads start at5BC0+96*(AL-21), independent of the tile source.
        if kind=='read' and self.c['entry']==4 and patch=='saved-ds' and address==physical(0x5000,(0x5BC0+96*((self.c['char']-0x21)&255)+0x40)&65535):
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,0x6100,patch)
        if kind=='read' and patch=='phase' and address==physical(0x5000,0x1C10+((self.c['phase']>>2)&15)*384):
            self.patch(self.r['ds'],0x21,40,patch)
        return got
    def out_word(self,port,value,flags,mask=base.FLAGS):
        self.emit('out',port,value,flags,mask)
        if port in (0x3C4,0x3CE):self.device.out(port,value,flags)
        else:check(port==0x3D4,'unexpected scroll port')
        patch=self.c.get('patch')
        if patch in self.providers:return
        if patch=='pause':self.patch(self.r['ds'],0x23,5,patch)
        if patch in ('far-ip','far-cs'):
            depth=2 if self.c['entry']==2 else 0
            self.patch(self.r['ss'],(self.r['sp']-depth-(4 if patch=='far-ip' else 2))&65535,0xD234 if patch=='far-ip' else 0x4321,patch)

    def inp(self,*args):raise base.OracleFailure('unexpected scroll IN')
    def out(self,*args):raise base.OracleFailure('unexpected scroll byte OUT')

class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        self.requests=[];far_frames=[];near_frames=[]
        def before(m,i):
            if i.mnemonic=='lcall':far_frames.append(i.address+i.size)
            if i.address in OWN and i.mnemonic=='call':near_frames.append(i.address+i.size)
            if i.address==0x8822:
                live=m.state();self.requests.append(tuple(live[n] for n in ('ax','bx','cx','dx','si','bp')))
            return False
        def expected(m,off):
            check(bool(far_frames),'undeclared scroll far return');return {(c['load'],far_frames.pop())}
        def near_expected(m,off):
            check(bool(near_frames),'undeclared scroll near return');return {near_frames.pop()}
        children=CHILD|{p:near_expected for p in (0x7DB6,0x7E2E,0x7E75)}
        super().__init__(c,memory,r,device,core,instructions=INS,access=Access(c,memory,r,device),
            outer_returns=lambda m,off:off in ({0x4C31} if c.get('swap') else RETURNS[c['entry']]) and not near_frames,max_steps=MAX_STEPS,before=before,child_returns=children,
            far_returns={p:expected for p,i in fixtures.RENDER.items() if i.mnemonic=='retf'},
            changed_return_status=lambda m,off:1 if off in fixtures.RENDER and fixtures.RENDER[off].mnemonic!='retf' else 2)
    def run(self):
        out=super().run();out['requests']=self.requests;return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'menu-scroll-{mutation}.dll',mutation,'menu_scroll')))
        self.core=self.lib.lmn_menu_scroll_core;self.core.restype=Result
        self.core.argtypes=[base.MEM,ct.c_uint16,ct.c_uint16,ct.POINTER(State),ct.c_int,ct.POINTER(base.Bus),ct.POINTER(base.Ports)]
        self.adapter=self.lib.lmn_menu_scroll_adapter;self.adapter.restype=Result
        self.adapter.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_uint16,ct.c_int,ct.POINTER(base.Bus),ct.POINTER(base.Ports)]
        self.swap=self.lib.lmn_program_display_start_adapter;self.swap.restype=None
        self.swap.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_int,ct.POINTER(base.Bus)]
    def run(self,c,memory,r,device,core,*,copy_state=True):
        if copy_state:memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,r,device);cb=base.NativeCallbacks(access);mem=(ct.c_uint8*base.SIZE).from_buffer(memory)
        if c.get('swap'):
            regs=base.Regs(**r);self.swap(mem,ct.byref(regs),2,ct.byref(cb.bus))
            registers={n:getattr(regs,n) for n in base.REG_NAMES}
            check(registers['ip']==0xD00D and registers['sp']==((r['sp']+2)&65535),'scroll swap escaped its declared normal boundary')
            return dict(regs=registers,status=0,memory=memory,device=access.device,events=access.events,providers=access.providers,cursor=access.cursor)
        tail=[c['entry'],ct.byref(cb.bus),ct.byref(cb.ports)];game_ds=(c['load']+0x9A9)&65535
        out=self.core(mem,r['cs'],game_ds,ct.byref(State(**{n:r[n] for n in FIELDS})),*tail) if core else self.adapter(mem,ct.byref(base.Regs(**r)),game_ds,*tail)
        return dict(regs={n:getattr(out.state,n) for n in FIELDS}|dict(cs=out.code_segment,ip=out.continuation),status=out.status,
                    memory=memory,device=access.device,events=access.events,providers=access.providers,cursor=access.cursor)

def independent(c,memory,r,ref):
    check(ref['status']==c.get('expected',0),c['name']+': unexpected stop')
    if ref['status'] or c.get('patch') or c['flags']&1024:return
    if c['entry'] in (0,1,2):
        phase=4 if c['entry']==0 else c['phase'];frame=((phase>>2)&15)*384
        check(ref['requests']==[(48,334,0x410,560,0,0),(0,334,0x410,48,0x1C10+frame,0),(592,334,0x410,48,0x3410+frame,0)],'scroll drawing geometry differs')
    if c['entry']==3:
        start=2*c['char'];want=bytearray(memory)
        for plane in range(4):
            for row in range(16):
                source=physical(0x5000,0x4C10+plane*32+row*2)
                dest=physical(r['es'],start+plane*1120+row*70)
                for byte in range(2):want[(dest+byte)&base.MASK]=memory[(source+byte)&base.MASK]
        if r['es']!=0xA000:
            # Include original stack writes separately; check only copied cells.
            for plane in range(4):
                for row in range(16):
                    dest=physical(r['es'],start+plane*1120+row*70)
                    check(ref['memory'][dest:dest+2]==want[dest:dest+2],'independent tile pixels differ')
    if c['entry']==2 and c['pause']:
        check(get16(ref['memory'],r['ds'],0x23)==((c['pause']-1)&65535),'pause decrement differs')
        check(get16(ref['memory'],r['ds'],0x21)==c['phase'],'pause changed phase')
    if c['entry']==2 and not c['pause'] and (c['phase']+4)&15:
        for plane in range(4):
            for row in range(16):
                at=physical(0x7000,plane*1120+row*70)
                old=memory[at:at+70]
                want=bytes(((v<<4)&255)|((old[n+1]>>4) if n<69 else 0) for n,v in enumerate(old))
                check(ref['memory'][at:at+70]==want,'independent four-bit scroll differs')
    if c['entry']==4 and c['char']!=0x20 and r['es']==0x7000:
        source=(0x5BC0+96*((c['char']-0x21)&255))&65535
        for plane in range(4):
            for row in range(16):
                for byte in range(2):
                    dest=physical(r['es'],plane*1120+row*70+68+byte)
                    mask=memory[physical(0x5000,(source+64+row*2+byte)&65535)]
                    color=memory[physical(0x5000,(source+plane*32+row*2+byte)&65535)] if plane<3 else 0
                    check(ref['memory'][dest]==((memory[dest]&~mask)|color),'independent glyph/mask differs')

def compare(native,c,core):
    memory,r,device=setup(c);ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    independent(c,memory,r,ref)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref

def hashes():
    paths=FIXTURES|{'tests/menu_scroll.py','tools/cbuild.py','tools/difftest.py','tools/bounded_process.py','c/menu_scroll.c','c/menu_scroll.h',
        'c/lemmings_sym.h','c/video_restore.h','c/regs.h','c/special_blit.h','c/display_start.c','c/display_start.h','c/display_status.h','metadata/oracle.json','metadata/toolchain-lock.json',
        'assets/main.dat','src/game_code_late_tail.asm','src/planar_drawing.asm'}
    paths|={'c/'+n+ext for n in fixtures.glyph.SOURCES[1:] for ext in ('.c','.h')}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

def handoff(native,load,record):
    c=dict(name=f'handoff-{load:04x}',load=load,seed=load,entry=0,flags=0xD7,phase=4,pause=0,char=0x41,pinned=True)
    memory,r,device=setup(c)
    # One constructed stream reaches FF, its complete100-tick pause and CR.
    # Other loads consume the pinned credit stream, without host text conversion.
    if load==base.LOADS[0]:
        for i,v in enumerate(b'A\xffB\r'):base.sync_memory_byte(memory,device,r['ds'],0x49CE+i,v)
    actual_memory,actual_device=bytearray(memory),copy.deepcopy(device);actual_regs=dict(r)
    pause_decrements=0;restart_seen=False
    for turn in range(113 if load==base.LOADS[0] else 19):
        if turn:
            c=dict(c,entry=2)
            for regs in (r,actual_regs):regs.update(sp=(regs['sp']-2)&65535,ip=0x7D0D)
            for mem,regs,dev in ((memory,r,device),(actual_memory,actual_regs,actual_device)):put16(mem,regs['ss'],regs['sp'],0xD00D,dev)
        prior_pause=get16(memory,r['ds'],0x23);prior_phase=get16(memory,r['ds'],0x21);prior_cursor=get16(memory,r['ds'],0x1F)
        ref=Machine(c,memory,dict(r),device,False).run();check(ref['status']==0,'handoff stopped')
        actual=native.run(c,actual_memory,actual_regs,actual_device,False,copy_state=False)
        base.compare_states(c['name']+f'-{turn}',actual,ref)
        actual_memory,actual_regs,actual_device=actual['memory'],actual['regs'],actual['device']
        memory,r,device=ref['memory'],ref['regs'],ref['device'];record(c['name']+f'-{turn}',False,ref)
        if turn and prior_pause:
            pause_decrements+=1
            check(get16(memory,r['ds'],0x23)==prior_pause-1,'handoff pause differs')
            check(get16(memory,r['ds'],0x21)==prior_phase,'handoff paused phase changed')
        if turn and prior_cursor==0x49D1 and get16(memory,r['ds'],0x1F)==0x49CF:restart_seen=True
        if not turn:
            check(get16(memory,r['ds'],0x1D)==0x49CE and get16(memory,r['ds'],0x1F)==0x49CE,'initializer text ownership differs')
            check(get16(memory,r['ds'],0x21)==4 and get16(memory,r['ds'],0x23)==0,'initializer phase/pause differs')
        # Observation histories are consumed after full comparison. Device
        # latches/registers/planes/counters and canonical RAM remain live.
        for dev in (device,actual_device):
            check(len(dev.trace)<=MAX_EVENTS,'VGA trace exceeded per-stage bus cap');dev.trace.clear()
        swap=dict(c,swap=True)
        for regs in (r,actual_regs):regs.update(sp=(regs['sp']-2)&65535,ip=0x4C20)
        for mem,regs,dev in ((memory,r,device),(actual_memory,actual_regs,actual_device)):put16(mem,regs['ss'],regs['sp'],0xD00D,dev)
        ref=Machine(swap,memory,dict(r),device,False).run()
        actual=native.run(swap,actual_memory,actual_regs,actual_device,False,copy_state=False)
        base.compare_states(c['name']+f'-swap{turn}',actual,ref)
        actual_memory,actual_regs,actual_device=actual['memory'],actual['regs'],actual['device']
        memory,r,device=ref['memory'],ref['regs'],ref['device'];record(c['name']+f'-swap{turn}',False,ref)
        for dev in (device,actual_device):dev.trace.clear()
        gc.collect()
    if load==base.LOADS[0]:check(pause_decrements==100 and restart_seen,'full pause/restart not reached')
    print(f'CHECKED connected scroll handoff{load:04x}',flush=True)

def worker(directory,snapshot):
    before=hashes();check(before==json.loads(Path(snapshot).read_text()),'scroll inputs changed');native=Native(directory)
    sites=set();edges=set();rows=[]
    def record(name,core,ref):
        sites.update(ref['sites']);edges.update(ref['edges']);rows.append(dict(case=name,core=core,steps=ref['steps'],events=len(ref['events']),far_return_events=ref['far_return_events']))
    for c in cases():
        for core in (True,False):record(c['name'],core,compare(native,c,core))
        gc.collect();print('CHECKED '+c['name'],flush=True)
    for load in base.LOADS:handoff(native,load,record)
    check(set(OWN)<=sites,'scroll sites missing: '+str(sorted(set(OWN)-sites)))
    check(EDGES<=edges,'scroll outcomes missing: '+str(sorted(EDGES-edges)))
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in ((1,'e3-df'),(2,'e3-ordinary'),(3,'glyph-41'),(4,'tick-text-ff'),(5,'tick-phase-0000'),(6,'tick-phase-0000'),(7,'initialize-changed-near'),(8,'draw-live-phase'),(9,'pause-1')):
        try:compare(Native(directory,mutation),lookup[name],True)
        except base.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise base.OracleFailure(f'scroll mutant{mutation} survived')
        gc.collect()
    check(before==hashes(),'scroll inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(base.IMAGE),own_known_bytes=sum(i.size for i in OWN.values()),known_connected_bytes=sum(i.size for i in INS.values()),
        entry_code_ranges=[list(r) for r in RANGES],case_count=len(cases())+3,comparison_count=len(rows),handoff_count=3,
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),declared_far_return_events=sum(r['far_return_events'] for r in rows),
        mutation_count=len(mutants),mutations=mutants,input_hashes=before,rows=rows,
        limits=dict(timeout_seconds=SECONDS,outer_timeout_seconds=600,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS),
        scope='Six connected7CBC..7E75 scroll/copy entries and native8822 renderer. Constructed state and pinned resource3/4 banks; loader/controller/scheduling remain open. Inherited RETF selector-EA and VGA-stack reference limits remain unverified.'))
    print(f'PASS menu scroll: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(EDGES)} outcomes,{len(mutants)} mutants',flush=True)
def main():
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]:raise SystemExit('usage: menu_scroll.py')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='menu-scroll-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

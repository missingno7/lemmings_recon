"""Two-page menu cache parents over shared original/native verification."""
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
RANGES=((0x4E37,0x4EA2),(0x4EA2,0x4EE7))
OWN={i.address:i for a,b in RANGES for i in base.MD.disasm(base.IMAGE[a:b],a)}
SWAP={i.address:i for i in base.MD.disasm(base.IMAGE[0x4C20:0x4C47],0x4C20)}
INS=OWN|fixtures.RENDER|SWAP
EDGES=base.direct_jump_edges(OWN)
RETURNS=({0x4E83,0x4EA1},{0x4EE6})
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=240,384,500_000,200_000
REPORT=BUILD/'menu-cache-differential.json'
FIXTURES=set()
for module in tuple(sys.modules.values()):
    name=getattr(module,'__file__',None)
    if not name:continue
    path=Path(name).resolve()
    if path.suffix=='.py' and path.is_relative_to(ROOT):
        rel=path.relative_to(ROOT)
        if rel.parts[0] in ('tests','tools'):FIXTURES.add(rel.as_posix())

class Result(ct.Structure):
    _fields_=[('state',State),('code_segment',ct.c_uint16),('continuation',ct.c_uint16),('status',ct.c_int)]

def cases():
    rows=[]
    for entry,marker in enumerate((2,4)):
        rows += [dict(name=f'e{entry}-equal-{value:02x}',entry=entry,cached=value,current=value) for value in range(256)]
        rows += [dict(name=f'e{entry}-'+n,entry=entry,**kw) for n,kw in (
            ('dirty',{'cached':0xFF,'current':1}),('marker',{'cached':marker,'current':1}),
            ('pinned',{'cached':marker,'current':1,'pinned_banks':True}),
            ('changed-far-ip',{'cached':marker,'current':1,'patch':'far-ip','expected':2}),
            ('changed-far-cs',{'cached':marker,'current':1,'patch':'far-cs','expected':2}),
            ('stack-wrap',{'cached':marker,'current':1,'sp':1}),
            ('stack-physical-wrap',{'cached':0,'current':0,'ss':0xFFFF,'sp':0xF}),
            ('word-ffff',{'cached':marker,'current':1,'sp':0xFFFF}),
            ('distinct-ds-hit',{'cached':1,'current':1,'ds':0x3000}),
            ('data-a20-hit',{'cached':1,'current':1,'ds':0xFFFF}),
            ('data-vga-hit',{'cached':1,'current':1,'ds':0xA000}),
            ('df',{'cached':marker,'current':1,'flags':0x6D7}),
            ('dirty-enabled',{'cached':marker,'current':1,'dirty':0xFF}),
            ('changed-inner-near',{'cached':marker,'current':1,'dirty':0xFF,'patch':'inner-near','expected':1}),
            ('cache-return-alias',{'cached':marker,'current':1,'ss_ds':True,'alias':True}),
        )]
        for load in base.LOADS:rows.append(dict(name=f'e{entry}-load-{load:04x}',entry=entry,load=load,cached=marker,current=1))
    rows += [dict(name='sound-'+n,entry=0,**kw) for n,kw in (
        ('off-background',{'cached':2,'current':0,'bits':0}),
        ('off-pinned',{'cached':2,'current':0,'bits':0,'pinned_banks':True}),
        ('driver-ff',{'bits':2,'driver':0xFF}),('driver-fe',{'bits':2,'driver':0xFE}),
        ('driver-zero',{'bits':3,'driver':0}),('high-bits-only',{'bits':0xFC}),
        ('high-and-low',{'bits':0xFE,'driver':0xFF}),
        ('live-current',{'cached':2,'current':0,'late_current':0xFF}),
        ('late-bits',{'cached':2,'current':0,'late_bits':0}),
    )]
    rows += [dict(name='group-'+n,entry=1,**kw) for n,kw in (
        ('zero',{'current':0}),('two',{'current':2}),('three',{'current':3}),
        ('unchecked-four',{'current':4}),('unchecked-127',{'current':127}),('unchecked-255',{'current':255}),
        ('live-index',{'cached':4,'current':1,'late_current':2}),
        ('live-table',{'cached':4,'current':1,'patch':'table'}),
    )]
    return [dict(load=0x1010,seed=0x4E37+i,flags=0xD7,cached=0xFF,current=1,bits=3,driver=0xFF)|c for i,c in enumerate(rows)]

def offsets(c):return (0x1F70,0x1F72) if c['entry']==0 else (0x1F6E,0x1F6F)

def setup(c):
    memory,device=base.initial_memory(c);ds=c.get('ds',(c['load']+0x9A9)&0xFFFF)
    current,cached=offsets(c)
    r=base.default_regs(c['load'],c['seed'],ds=ds,ss=c.get('ss',0x6000),sp=c.get('sp',0x9000),flags=c['flags'])
    r.update(ip=RANGES[c['entry']][0],ax=0xBE91,bx=0xAD75)
    if c.get('ss_ds'):r.update(ss=ds,sp=cached)
    for frame in dict.fromkeys((ds,(c['load']+0x9A9)&0xFFFF)):
        base.sync_memory_byte(memory,device,frame,current,c['current'])
        base.sync_memory_byte(memory,device,frame,cached,c['cached'])
        base.sync_memory_byte(memory,device,frame,0x25A7,c['bits'])
        base.sync_memory_byte(memory,device,frame,0x2010,c['driver'])
        for off,value in ((0x1FEE,0x4000),(0x1FE4,0xDEAD),(0x1F76,0),(0x1F78,0x6D60),(0x1F7A,0),
                          (0x1FDA,0x3D4),(0x66F0,350),(0x66F2,640),(0x66F4,80),(0x26,0x2000)):
            put16(memory,frame,off,value,device)
        base.sync_memory_byte(memory,device,frame,0x2A,c.get('dirty',0))
    if c.get('clear_planes'):
        for plane in device.planes:plane[:]=bytes(65536)
        memory[0xA0000:0xB0000]=bytes(65536)
    if c.get('pinned_banks'):
        for segment,data in zip((0x4000,0x4F21),fixtures.resource_banks()):
            for i,v in enumerate(data):base.sync_memory_byte(memory,device,segment,i,v)
    if c.get('alias'):
        # The outer frame's low byte is the cache, so construct its marker
        # after writing the caller word; no shadow copy repairs that alias.
        put16(memory,r['ss'],r['sp'],0xD000|c['cached'],device)
    else:put16(memory,r['ss'],r['sp'],0xD00D,device)
    return memory,r,device

class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):super().__init__(c,memory,r,device,max_events=MAX_EVENTS,packed_events=True)
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        got=super().access(kind,address,flags,mask,value)
        if self.c.get('swap'):return got
        current,cached=offsets(self.c)
        if kind=='write' and address==physical(self.r['ds'],cached) and 'late_current' in self.c and 'current' not in self.providers:
            self.patch(self.r['ds'],current,self.c['late_current'],'current',word=False)
        if kind=='read' and address==physical(self.r['ds'],0x26) and self.c.get('patch')=='inner-near' and 'inner-near' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-6)&0xFFFF,0xD234,'inner-near')
        if kind=='write' and address==physical(self.r['ds'],0x1FE4) and 'late_bits' in self.c and 'bits' not in self.providers:
            self.patch(self.r['ds'],0x25A7,self.c['late_bits'],'bits',word=False)
        if kind=='read' and address==physical(self.r['ds'],current) and self.c.get('patch')=='table' and 'table' not in self.providers:
            self.patch(self.c['load'],0x4EE7+2*self.c['current'],0x4C90,'table')
        return got
    def out_word(self,port,value,flags,mask=base.FLAGS):
        self.emit('out',port,value,flags,mask)
        if port in (0x3C4,0x3CE):self.device.out(port,value,flags)
        else:check(port==0x3D4,'unexpected menu-cache word port')
        phase=self.c.get('patch')
        if phase in ('far-ip','far-cs') and phase not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']+(-4 if phase=='far-ip' else -2))&0xFFFF,
                       0xD234 if phase=='far-ip' else 0x4321,phase)
    def inp(self,*args):raise base.OracleFailure('unexpected menu-cache IN')
    def out(self,*args):raise base.OracleFailure('unexpected menu-cache byte OUT')

class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        self.requests=[];far_frames=[]
        def before(m,i):
            if i.mnemonic=='lcall':far_frames.append(i.address+i.size)
            if i.address==0x8822:
                live=m.state();self.requests.append(tuple(live[n] for n in ('ax','bx','cx','dx','si','di','bp')))
            return False
        def expected(m,off):
            check(bool(far_frames),'undeclared cache far return');return {(c['load'],far_frames.pop())}
        super().__init__(c,memory,r,device,core,instructions=INS,access=Access(c,memory,r,device),
            outer_returns={0x4C31} if c.get('swap') else RETURNS[c['entry']],max_steps=MAX_STEPS,before=before,
            child_returns={0x99E7:{0x884F},0x9A0B:{0x884F},0x9A14:{0x884F},0x9A8E:{0x885E},0x4C46:{0x4C27}},
            far_returns={p:expected for p,i in fixtures.RENDER.items() if i.mnemonic=='retf'},
            changed_return_status=lambda m,off:2 if off in fixtures.RENDER and fixtures.RENDER[off].mnemonic=='retf' else 1)
    def run(self):
        out=super().run();out['requests']=self.requests;return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'menu-cache-{mutation}.dll',mutation,'menu_cache')))
        self.core=self.lib.lmn_menu_cache_core
        self.core.argtypes=[base.MEM,ct.c_uint16,ct.c_uint16,ct.POINTER(State),ct.c_int,ct.POINTER(base.Bus),ct.POINTER(base.Ports)]
        self.core.restype=Result
        self.adapter=self.lib.lmn_menu_cache_adapter
        self.adapter.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_uint16,ct.c_int,ct.POINTER(base.Bus),ct.POINTER(base.Ports)]
        self.adapter.restype=Result
        self.swap=self.lib.lmn_program_display_start_adapter
        self.swap.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_int,ct.POINTER(base.Bus)];self.swap.restype=None
    def run(self,c,memory,r,device,core,*,copy_state=True):
        if copy_state:memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,r,device);cb=base.NativeCallbacks(access)
        mem=(ct.c_uint8*base.SIZE).from_buffer(memory)
        if c.get('swap'):
            registers=base.Regs(**r);self.swap(mem,ct.byref(registers),2,ct.byref(cb.bus))
            regs={n:getattr(registers,n) for n in base.REG_NAMES};status=0
            check(regs['ip']==0xD00D and regs['sp']==((r['sp']+2)&0xFFFF),'swap did not reach its declared normal return')
        else:
            tail=[c['entry'],ct.byref(cb.bus),ct.byref(cb.ports)];game_ds=(c['load']+0x9A9)&0xFFFF
            if core:out=self.core(mem,r['cs'],game_ds,ct.byref(State(**{n:r[n] for n in FIELDS})),*tail)
            else:out=self.adapter(mem,ct.byref(base.Regs(**r)),game_ds,*tail)
            regs={n:getattr(out.state,n) for n in FIELDS}|dict(cs=out.code_segment,ip=out.continuation);status=out.status
        return dict(regs=regs,status=status,memory=memory,device=access.device,events=access.events,providers=access.providers,cursor=access.cursor)

def independent(c,memory,r,ref,core):
    check(ref['status']==c.get('expected',0),c['name']+': unexpected stop')
    if ref['status'] or c.get('alias'):return
    current,cached=offsets(c);marker=(2,4)[c['entry']]
    draw=c['cached']==marker or c['cached']!=c['current']
    expected_cache=c['current'] if c['cached']==marker else marker if draw else c['cached']
    check(ref['memory'][physical(r['ds'],cached)]==expected_cache,'cache handshake differs')
    check(len(ref['requests'])==int(draw),'cache draw count differs')
    if not draw:
        check(ref['regs']['ax']==((r['ax']&0xFF00)|c['cached']),'no-draw AH/AL differs');return
    if c.get('patch') or 'late_current' in c or 'late_bits' in c:return
    if c['entry']==0:
        if not(c['bits']&3):want=(324,120,0x43D,120,0xB120,0xBBD9,3)
        else:want=(351,146,0x41F,64,0xEA50 if c['bits']&2 and c['driver']==0xFF else 0xEE30,r['di'],1)
        selector=0x4000
    else:
        want=(486,145,0x41B,72,get16(memory,r['cs'],0x4EE7+2*c['current']),r['di'],1);selector=0x5000
    check(ref['requests']==[want],'independent cached graphic request differs')
    check(get16(ref['memory'],r['ds'],0x1FE4)==selector,'cached graphic selector differs')

def compare(native,c,core):
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    independent(c,memory,r,ref,core)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref

def hashes():
    paths=FIXTURES|{'tests/menu_cache.py','tools/cbuild.py','tools/difftest.py','tools/bounded_process.py',
        'c/menu_cache.c','c/menu_cache.h','c/lemmings_sym.h','c/video_restore.h','c/regs.h','c/special_blit.h',
        'c/display_start.c','c/display_start.h','c/display_status.h','assets/main.dat',
        'metadata/oracle.json','metadata/toolchain-lock.json','src/game_code_late_after_decimal.asm','src/planar_drawing.asm'}
    paths|={'c/'+n+ext for n in fixtures.glyph.SOURCES[1:] for ext in ('.c','.h')}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

def handoff(native,entry,load):
    c=dict(name=f'handoff-e{entry}-{load:04x}',entry=entry,load=load,seed=load,flags=0xD7,
           cached=0xFF,current=0 if entry==0 else 1,bits=3,driver=0xFF,pinned_banks=True,clear_planes=True)
    memory,r,device=setup(c);actual_memory,actual_device=bytearray(memory),copy.deepcopy(device)
    actual_regs=dict(r);rows=[];ds=r['ds'];current,cached=offsets(c)
    wanted=(2,0,0,2,0xFF,0xFF) if entry==0 else (4,1,1,4,2,2)
    for turn in range(6):
        if turn==3:
            c=dict(c,current=0xFF if entry==0 else 2,bits=1)
            for mem,dev in ((memory,device),(actual_memory,actual_device)):
                base.sync_memory_byte(mem,dev,ds,current,c['current']);base.sync_memory_byte(mem,dev,ds,0x25A7,c['bits'])
        # Entries use actual prior registers and RAM. Only the caller's new
        # near frame is constructed; produced cache bytes are never repaired.
        if turn:r=dict(r,sp=(r['sp']-2)&0xFFFF,ip=RANGES[entry][0])
        if turn:actual_regs=dict(actual_regs,sp=(actual_regs['sp']-2)&0xFFFF,ip=RANGES[entry][0])
        for mem,regs,dev in ((memory,r,device),(actual_memory,actual_regs,actual_device)):put16(mem,regs['ss'],regs['sp'],0xD00D,dev)
        call=dict(c,cached=memory[physical(ds,cached)])
        before=bytearray(memory);ref=Machine(call,memory,dict(r),device,False).run()
        independent(call,before,r,ref,False)
        if native:
            actual=native.run(call,actual_memory,actual_regs,actual_device,False,copy_state=False)
            base.compare_states(c['name']+f'-draw{turn}',actual,ref)
            actual_memory,actual_regs,actual_device=actual['memory'],actual['regs'],actual['device']
        memory,r,device=ref['memory'],ref['regs'],ref['device']
        check(memory[physical(ds,cached)]==wanted[turn],'two-page cache phase differs')
        rows.append((c['name']+f'-draw{turn}',summary(ref)))
        if turn in (1,4):check(all(p[:0x6D60]==p[0x6D60:0xDAC0] for p in device.planes),'two cached pages differ after second update')
        swap=dict(c,swap=True);r=dict(r,sp=(r['sp']-2)&0xFFFF,ip=0x4C20)
        put16(memory,r['ss'],r['sp'],0xD00D,device)
        ref=Machine(swap,memory,dict(r),device,False).run()
        if native:
            actual_regs=dict(actual_regs,sp=(actual_regs['sp']-2)&0xFFFF,ip=0x4C20)
            put16(actual_memory,actual_regs['ss'],actual_regs['sp'],0xD00D,actual_device)
            actual=native.run(swap,actual_memory,actual_regs,actual_device,False,copy_state=False)
            base.compare_states(c['name']+f'-swap{turn}',actual,ref)
            actual_memory,actual_regs,actual_device=actual['memory'],actual['regs'],actual['device']
        memory,r,device=ref['memory'],ref['regs'],ref['device']
        rows.append((c['name']+f'-swap{turn}',summary(ref)));gc.collect()
    return rows

def summary(ref):return dict(steps=ref['steps'],sites=ref['sites'],edges=ref['edges'],events=len(ref['events']),far_return_events=ref['far_return_events'])

def worker(directory,snapshot):
    before=hashes();check(before==json.loads(Path(snapshot).read_text()),'menu cache snapshot changed')
    native=Native(directory);rows=[];sites=set();edges=set()
    def record(name,core,ref):
        sites.update(ref['sites']);edges.update(ref['edges'])
        rows.append(dict(case=name,core=core,steps=ref['steps'],events=ref['events'] if isinstance(ref['events'],int) else len(ref['events']),far_return_events=ref['far_return_events']))
    for c in cases():
        for core in (True,False):record(c['name'],core,compare(native,c,core))
        gc.collect()
        if '-equal-' not in c['name'] or int(c['name'][-2:],16)%64==0:print('CHECKED '+c['name'],flush=True)
    for load in base.LOADS:
        for entry in (0,1):
            for name,ref in handoff(native,entry,load):record(name,False,ref)
        print(f'CHECKED two-page handoffs{load:04x}',flush=True)
    check(set(OWN)<=sites,'cache sites missing: '+str(sorted(set(OWN)-sites)))
    check(EDGES<=edges,'cache outcomes missing: '+str(sorted(EDGES-edges)))
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in ((1,'e0-equal-01'),(2,'e0-marker'),(3,'sound-driver-fe'),(4,'group-live-index'),(5,'group-two'),(6,'group-zero'),(7,'e1-changed-far-ip')):
        try:compare(Native(directory,mutation),lookup[name],True)
        except base.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise base.OracleFailure(f'menu cache mutant{mutation} survived')
        gc.collect()
    check(before==hashes(),'menu cache inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(base.IMAGE),own_known_bytes=sum(i.size for i in OWN.values()),
        known_connected_bytes=sum(i.size for i in INS.values()),entry_code_ranges=[list(r) for r in RANGES],
        case_count=len(cases())+6,comparison_count=len(rows),handoff_count=6,
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),instruction_steps=sum(r['steps'] for r in rows),
        ordered_bus_events=sum(r['events'] for r in rows),declared_far_return_events=sum(r['far_return_events'] for r in rows),
        mutation_count=len(mutants),mutations=mutants,input_hashes=before,rows=rows,
        limits=dict(timeout_seconds=SECONDS,outer_timeout_seconds=270,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS),
        reference_limits=dict(retf_selector_ea_wrap_sp=[0xFFFE,0xFFFF],vga_stack_masked_loop_unverified=True),
        scope='4E37/4EA2 two-page cache parents with native renderer and actual display swap handoffs. Live byte caches,AH,CS table,late rereads,segments/flags/frames. Constructed and pinned decoded resource banks; upstream menu controller,loader execution,scheduling and unsupported reference domains remain open.'))
    print(f'PASS menu cache: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(EDGES)} outcomes,{len(mutants)} mutants',flush=True)

def main():
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]:raise SystemExit('usage: menu_cache.py')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='menu-cache-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

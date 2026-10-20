"""Ten-record initialization -> countdown -> native bitmap composition.

Execution, canonical memory, callback guards and comparison use verification.py.
Only instruction maps/source lists are reused from the glyph fixture provider.
"""
import copy
import ctypes as ct
import gc
import json
from functools import lru_cache
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
import text_glyph as glyph
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import BUILD,sha,write_json
from resources import decode_section,section_spans

check=base.check
physical,put16,get16=base.physical,base.put16,base.get16
RANGES=((0x4F96,0x4FF8),(0x4FF8,0x5017),(0x4EEF,0x4F8A))
OWN={i.address:i for a,b in RANGES for i in base.MD.disasm(base.IMAGE[a:b],a)}
RENDER={p:i for p,i in glyph.INS.items() if p>=0x8822}
INS=OWN|RENDER
EDGES=base.direct_jump_edges(OWN)
RETURNS=(0x5016,0x4FF7)
DRAW_ENTRIES=(0x4EEF,0x4F2B,0x4F4A,0x4F6E)
DRAW_RETURNS=(0x4F2A,0x4F6D,0x4F6D,0x4F89)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=570,384,200_000,100_000
DRAW_STEPS,DRAW_EVENTS=1_500_000,750_000
REPORT=BUILD/'menu-animation-differential.json'
FIELDS=('ax','bx','cx','dx','si','di','bp','ds','es','ss','sp','flags')
UNVERIFIED_CASES=({'load': 4112, 'seed': 20480, 'flags': 215, 'name': 'drawing-bitmap-vga-stack', 'kind': 'drawing', 'entry': 3, 'ss': 40960},)
PINNED=base.IMAGE[0x9A90+0x4960:0x9A90+0x49CE]
FIXTURES=set()
for module in tuple(sys.modules.values()):
    name=getattr(module,'__file__',None)
    if not name:continue
    path=Path(name).resolve()
    if path.suffix=='.py' and path.is_relative_to(ROOT):
        rel=path.relative_to(ROOT)
        if rel.parts[0] in ('tests','tools'):FIXTURES.add(rel.as_posix())

class State(ct.Structure):
    _fields_=[(n,ct.c_uint16) for n in FIELDS]
class Result(ct.Structure):
    _fields_=[('state',State),('code_segment',ct.c_uint16),('continuation',ct.c_uint16),('status',ct.c_int)]

def cases():
    rows=[dict(name='initialize-'+n,entry=0,**kw) for n,kw in (
        ('pinned',{'pinned':True}),('enabled',{'resets':dict.fromkeys(range(10),0)}),
        ('disabled',{}),('alternating',{'resets':{i:17 for i in range(0,10,2)}}),
        ('outer-return-alias',{'ss':0x3000,'ds':0x3000,'sp':0x4960,'alias':True}),
    )]
    for v in (0,1,2,0x7FFF,0x8000,0x8001,0xFFEE,0xFFEF,*range(0xFFF0,0x10000)):
        rows.append(dict(name=f'tick-counter-{v:04x}',entry=1,counters={0:v}))
    rows += [dict(name='tick-'+n,entry=1,**kw) for n,kw in (
        ('pinned',{'pinned':True}),('all-disabled',{}),
        ('ten-draws',{'counters':dict.fromkeys(range(10),0)}),
        ('reset-disabled',{'counters':{0:0xFFF0},'resets':{0:0x8000}}),
        ('reset-zero',{'counters':{0:0xFFF0},'resets':{0:0}}),
        ('negative-left',{'counters':{0:0},'left':0xFFF0}),
        ('right-edge',{'counters':{0:0},'left':639}),
        ('bottom-edge',{'counters':{0:0},'top':349}),
        ('outside-height',{'counters':{0:0},'top':350}),
        ('source-wrap',{'counters':{0:0xFFF1},'source':0xFF80}),
        ('selector-wrap',{'counters':{0:0},'bank':0xFC00}),
        ('live-count',{'counters':{0:0},'patch':'count'}),
        ('live-si',{'counters':{0:0},'patch':'si'}),
        ('far-ip-changed',{'counters':{0:0},'patch':'far-ip','expected':2}),
        ('far-cs-changed',{'counters':{0:0},'patch':'far-cs','expected':2}),
        ('dirty-enabled',{'counters':{0:0},'dirty':0xFF}),
        ('near-return-changed',{'counters':{0:0},'dirty':0xFF,'patch':'near','expected':1}),
        ('saved-count-record-alias',{'ss':0x3000,'ds':0x3000,'sp':0x4962,'alias':True}),
    )]
    for entry in (0,1):
        for n,kw in (
            ('ds-distinct',{'ds':0x3000,'counters':{0:0}}),
            ('ds-a20',{'ds':0xFFFF}),('ds-vga',{'ds':0xA000}),
            ('stack-wrap',{'sp':1,'counters':{0:0}}),
            ('stack-a20',{'ss':0xFFFF,'sp':0xF}),
            ('word-ffff',{'sp':0xFFFF}),('df',{'flags':0x6D7,'counters':{0:0}}),
        ):rows.append(dict(name=f'e{entry}-'+n,entry=entry,**kw))
        for load in base.LOADS:rows.append(dict(name=f'e{entry}-load-{load:04x}',entry=entry,load=load,counters={0:0}))
    for entry,name in enumerate(('backdrop','rows','row','bitmap')):
        rows += [dict(name='drawing-'+name+'-'+n,kind='drawing',entry=entry,**kw) for n,kw in (
            ('ordinary',{}),('pinned-banks',{'pinned_banks':True}),
            ('stack-wrap',{'sp':1}),('df',{'flags':0x6D7}),
        )]
        for load in base.LOADS:rows.append(dict(name=f'drawing-{name}-load-{load:04x}',kind='drawing',entry=entry,load=load))
    rows += [dict(name='drawing-'+n,kind='drawing',**kw) for n,kw in (
        ('row-one',{'entry':2,'count':1}),
        ('row-zero-live-count',{'entry':2,'count':0,'draw_patch':'row-count'}),
        ('row-live-table',{'entry':2,'draw_patch':'table-next'}),
        ('row-table-word-ffff',{'entry':2,'count':1,'table':0xFFFF}),
        ('bitmap-live-ax',{'entry':3,'draw_patch':'saved-ax'}),
        ('row-live-ax',{'entry':2,'count':1,'draw_patch':'row-ax'}),
        ('bitmap-far-ip',{'entry':3,'draw_patch':'far-ip','expected':2}),
        ('row-wrapper-near',{'entry':2,'count':1,'draw_patch':'wrapper-near','expected':3}),
        ('rows-parent-near',{'entry':1,'draw_patch':'parent-near','expected':3}),
        ('backdrop-far-ip',{'entry':0,'draw_patch':'far-ip','expected':2}),
        ('bitmap-physical-wrap',{'entry':3,'ss':0xFFFF,'sp':0x1F}),
        ('bitmap-data-segment',{'entry':3,'ds':0x3000,'long_shift':True,'reference_steps':20_000_000,'reference_events':5_000_000}),
        ('bitmap-data-aligned',{'entry':3,'ds':0x3000,'left':64}),
        ('rows-selector-wrap',{'entry':1,'bank':0xFC00}),
    )]
    return [dict(load=0x1010,seed=0x4F96+i,flags=0xD7)|c for i,c in enumerate(rows)]

def setup(c):
    memory,device=base.initial_memory(c);game_ds=(c['load']+0x9A9)&0xFFFF
    ds=c.get('ds',game_ds)
    r=base.default_regs(c['load'],c['seed'],ds=ds,ss=c.get('ss',0x6000),sp=c.get('sp',0x9000),flags=c['flags'])
    drawing=c.get('kind')=='drawing'
    r['ip']=DRAW_ENTRIES[c['entry']] if drawing else RANGES[1-c['entry']][0]
    if drawing:r.update(ax=c.get('left',68),bx=c.get('top',120),cx=c.get('count',2),si=c.get('source',0x9488),di=c.get('table',0x4F8A),bp=3)
    for frame in dict.fromkeys((ds,game_ds)):
        for i in range(10):
            start=0x4960+11*i
            if c.get('pinned'):
                for j,v in enumerate(PINNED[11*i:11*(i+1)]):base.sync_memory_byte(memory,device,frame,start+j,v)
            else:
                words=(c.get('counters',{}).get(i,0x8000),c.get('resets',{}).get(i,0x8000),c.get('left',32+32*i),c.get('top',40),c.get('source',0x100))
                for j,v in enumerate(words):put16(memory,frame,start+2*j,v,device)
                base.sync_memory_byte(memory,device,frame,start+10,(0x51+i)&255)
        for off,v in ((0x1FEE,c.get('bank',0x4000)),(0x1FE4,0xDEAD),(0x1F76,0x1000),
                      (0x66F0,350),(0x66F2,640),(0x66F4,80),(0x26,0x2000)):
            put16(memory,frame,off,v,device)
        base.sync_memory_byte(memory,device,frame,0x2A,c.get('dirty',0))
    if drawing:
        for frame in dict.fromkeys((ds,game_ds)):
            put16(memory,frame,0x1F7A,0,device)
            if c['entry']>=2:put16(memory,frame,0x1FE4,c.get('bank',0x4000),device)
        if 'table' in c:put16(memory,c['load'],c['table'],0x9488,device)
    if c.get('pinned_banks'):
        for segment,data in zip((c.get('bank',0x4000),(c.get('bank',0x4000)+0xF21)&0xFFFF),resource_banks()):
            for i,v in enumerate(data):base.sync_memory_byte(memory,device,segment,i,v)
    put16(memory,r['ss'],r['sp'],0xD00D,device)
    return memory,r,device

@lru_cache(maxsize=1)
def resource_banks():
    data=(ROOT/'assets/main.dat').read_bytes();spans=section_spans(data)
    result=tuple(decode_section(data[a:b])[0] for a,b in spans[3:5])
    check(tuple(map(len,result))==(0xF210,0x8CF0),'pinned UI section sizes differ')
    check(tuple(sha(b) for b in result)==('05fa1758775e601d38b00c6120cc597ffae6c598b04caac921bb59d76a80c805','6880c756be51fd97314e8f2c615baef9218134c58e66eff25a6e3dbab6f0a5f7'),'pinned UI sections differ')
    return result

class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):super().__init__(c,memory,r,device,max_events=c.get('reference_events',DRAW_EVENTS if c.get('kind')=='drawing' else MAX_EVENTS),packed_events=c.get('kind')=='drawing')
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        v=super().access(kind,address,flags,mask,value)
        phase=self.c.get('patch')
        if phase=='count' and kind=='read' and address==physical(self.r['ds'],0x4960) and 'count' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&0xFFFF,1,'count')
        if phase=='near' and kind=='read' and address==physical((self.c['load']+0x9A9)&0xFFFF,0x26) and 'near' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-10)&0xFFFF,0xD234,'near')
        return v
    def out_word(self,port,value,flags,mask=base.FLAGS):
        self.emit('out',port,value,flags,mask);self.device.out(port,value,flags)
        draw=self.c.get('draw_patch')
        if draw and draw not in self.providers:
            entry=self.c['entry']
            if draw=='table-next':self.patch(self.c['load'],0x4F8C,0xB120,draw)
            else:
                delta,value={'saved-ax':(-2,0x1234),'row-ax':(-4,0x1234),'row-count':(-2,1),
                    'wrapper-near':(-8,0xD234),'parent-near':(-2,0xD234),
                    'far-ip':(-4 if entry==0 else -14,0xD234)}[draw]
                self.patch(self.r['ss'],(self.r['sp']+delta)&0xFFFF,value,draw)
        phase=self.c.get('patch')
        if phase in ('si','far-ip','far-cs') and phase not in self.providers:
            delta,value={'si':(-4,0x4960-11),'far-ip':(-8,0xD234),'far-cs':(-6,0x4321)}[phase]
            self.patch(self.r['ss'],(self.r['sp']+delta)&0xFFFF,value,phase)
    def inp(self,*args):raise base.OracleFailure('unexpected menu-animation IN')
    def out(self,*args):raise base.OracleFailure('unexpected menu-animation byte OUT')

class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        self.requests=[];far_frames=[]
        def expected_far(m,off):
            check(bool(far_frames),'undeclared far caller');return {(c['load'],far_frames.pop())}
        def outer(m,off):
            return off==DRAW_RETURNS[c['entry']] and m.state()['sp']==r['sp']
        def before(m,i):
            if i.mnemonic=='lcall':far_frames.append(i.address+i.size)
            if i.address==0x8822:
                live=m.state();m.requests.append(tuple(live[n] for n in ('ax','bx','cx','dx','si','di','bp')))
            return False
        super().__init__(c,memory,r,device,core,instructions=INS,access=Access(c,memory,r,device),
            outer_returns=outer if c.get('kind')=='drawing' else {RETURNS[c['entry']]},max_steps=c.get('reference_steps',DRAW_STEPS if c.get('kind')=='drawing' else MAX_STEPS),before=before,
            child_returns={0x99E7:{0x884F},0x9A0B:{0x884F},0x9A14:{0x884F},0x9A8E:{0x885E},0x4F89:{0x4F5F,0x4F67},0x4F6D:{0x4F41}},
            far_returns={p:expected_far for p,i in RENDER.items() if i.mnemonic=='retf'},
            changed_return_status=lambda m,off:3 if off in (0x4F89,0x4F6D) else 2 if off in RENDER and RENDER[off].mnemonic=='retf' else 1)

    def run(self):
        out=super().run();out['requests']=self.requests;return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'animation-{mutation}.dll',mutation,'menu_animation')))
        self.core=self.lib.lmn_menu_animation_core
        self.core.argtypes=[base.MEM,ct.c_uint16,ct.c_uint16,ct.POINTER(State),ct.c_int,ct.POINTER(base.Bus),ct.POINTER(base.Ports)]
        self.core.restype=Result
        self.adapter=self.lib.lmn_menu_animation_adapter
        self.adapter.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_uint16,ct.c_int,ct.POINTER(base.Bus),ct.POINTER(base.Ports)]
        self.adapter.restype=Result
        self.draw_core=self.lib.lmn_menu_drawing_core;self.draw_core.argtypes=self.core.argtypes;self.draw_core.restype=Result
        self.draw_adapter=self.lib.lmn_menu_drawing_adapter;self.draw_adapter.argtypes=self.adapter.argtypes;self.draw_adapter.restype=Result
    def run(self,c,memory,r,device,core,*,copy_state=True):
        if copy_state:memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,r,device);cb=base.NativeCallbacks(access)
        game_ds=(c['load']+0x9A9)&0xFFFF;mem=(ct.c_uint8*base.SIZE).from_buffer(memory)
        tail=[c['entry'],ct.byref(cb.bus),ct.byref(cb.ports)]
        core_fn=self.draw_core if c.get('kind')=='drawing' else self.core
        adapter_fn=self.draw_adapter if c.get('kind')=='drawing' else self.adapter
        if core:out=core_fn(mem,r['cs'],game_ds,ct.byref(State(**{n:r[n] for n in FIELDS})),*tail)
        else:out=adapter_fn(mem,ct.byref(base.Regs(**r)),game_ds,*tail)
        regs={n:getattr(out.state,n) for n in FIELDS}|dict(cs=out.code_segment,ip=out.continuation)
        return dict(regs=regs,status=out.status,memory=memory,device=access.device,events=access.events,
                    providers=access.providers,cursor=access.cursor)

def independent_drawing(c,memory,r,ref):
    if ref['status'] or c.get('draw_patch'):return
    expected=[]
    def request(x,y,source,control):
        expected.append((x&0xFFFF,y&0xFFFF,0x43D,0x78,source,(source+0xAB9)&0xFFFF,control))
    entry=c['entry']
    if entry==0:
        expected=[(0,20,0x45E,0x278,0x2080,0x7786,0xF42),(8,10,0x45E,0x278,0x2080,0x7786,2)]
    elif entry==3:request(r['ax'],r['bx'],r['si'],r['bp'])
    else:
        table=r['di'] if entry==2 else 0x4F8A
        groups=((r['ax'],r['bx'],r['cx']),) if entry==2 else ((68,120,4),(196,197,2))
        for x,y,count in groups:
            for i in range(count):
                source=get16(memory,r['cs'],table)
                request(x-8,y+8,source,0xF43);request(x,y,source,3)
                x=(x+128)&0xFFFF;table=(table+2)&0xFFFF
    check(ref['requests']==expected,c['name']+': independent menu drawing requests differ')
    if entry<=1:
        check(get16(ref['memory'],r['ds'],0x1FE4)==get16(memory,r['ds'],0x1FEE),'menu UI selector publication differs')


def independent(c,memory,r,ref):
    check(ref['status']==c.get('expected',0),c['name']+': unexpected stop')
    if c.get('kind')=='drawing':
        independent_drawing(c,memory,r,ref);return
    if ref['status'] or c.get('alias') or c.get('patch') or r['ds']!=((c['load']+0x9A9)&0xFFFF):return
    ds=r['ds'];got=ref['memory']
    expected_requests=[]
    for i in range(10):
        at=0x4960+11*i;old=get16(memory,ds,at);reset=get16(memory,ds,at+2)
        if c['entry']==0:expected=0x8000 if reset==0x8000 else 40*(i+1)
        else:expected=old if old==0x8000 else reset if old==0xFFF0 else (old-1)&0xFFFF
        if c['entry']==1 and old!=0x8000 and old!=0xFFF0 and expected&0x8000:
            q=(((-expected-1)&0xFFFF)>>1);swapped=((q&255)<<8)|(q>>8)
            source=(get16(memory,ds,at+8)+(swapped>>1)+(swapped>>2))&0xFFFF
            expected_requests.append((get16(memory,ds,at+4),get16(memory,ds,at+6),0x40C,32,source,(source+0x90)&0xFFFF,1))
        check(get16(got,ds,at)==expected,c['name']+': independent countdown differs')
        check(bytes(got[physical(ds,at+2):physical(ds,at+2)+9])==bytes(memory[physical(ds,at+2):physical(ds,at+2)+9]),c['name']+': immutable record fields differ')
    check(ref['requests']==expected_requests,'independent bitmap requests differ')
    if c['entry']==1:check(get16(got,ds,0x1FE4)==((get16(memory,ds,0x1FEE)+0x800)&0xFFFF),'graphics selector differs')

def compare(native,c,core):
    memory,r,device=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    independent(c,memory,r,ref)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref

def hashes():
    paths=FIXTURES|{'tests/menu_animation.py','tools/cbuild.py','tools/bounded_process.py','tools/difftest.py',
        'c/menu_animation.c','c/menu_animation.h','c/lemmings_sym.h','c/video_restore.h','c/regs.h',
        'c/special_blit.h','metadata/oracle.json','metadata/toolchain-lock.json',
        'src/game_code_late_after_decimal.asm','src/planar_drawing.asm','assets/main.dat'}
    paths|={'c/'+n+ext for n in glyph.SOURCES[1:] for ext in ('.c','.h')}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

def handoff(native,load):
    c=next(c for c in cases() if c['name']=='initialize-pinned')|dict(load=load)
    memory,r,device=setup(c);ref=None;actual=None;stages=[]
    for tick in range(219):
        if tick:
            c=dict(c,entry=1);r=dict(ref['regs'],ip=0x4F96,sp=(ref['regs']['sp']-2)&0xFFFF)
            put16(memory,r['ss'],r['sp'],0xD00D,device)
            if actual:
                nr=dict(actual['regs'],ip=0x4F96,sp=(actual['regs']['sp']-2)&0xFFFF)
                put16(actual['memory'],nr['ss'],nr['sp'],0xD00D,actual['device'])
        before=bytearray(memory)
        ref=Machine(c,memory,dict(r),device,False).run()
        independent(c,before,r,ref)
        if native:
            actual=native.run(c,before if tick==0 else actual['memory'],r if tick==0 else nr,
                copy.deepcopy(setup(c)[2]) if tick==0 else actual['device'],False,copy_state=tick==0)
            base.compare_states(c['name']+f'-tick{tick}',actual,ref)
        stages.append((c['name']+f'-{load:04x}-tick{tick}',ref))
        # Trace/state snapshots are returned for accounting; do not retain VGA
        # planes, RAM or event arrays per frame across the animation cycle.
        stages[-1]=(stages[-1][0],{n:ref[n] for n in ('steps','sites','edges') }|dict(events=len(ref['events']),far_return_events=ref['far_return_events']))
        memory,device=ref['memory'],ref['device']
        if tick%8==0:gc.collect()
    ds=(load+0x9A9)&0xFFFF
    check([get16(memory,ds,0x4960+11*i) for i in range(10)]==[239,319,399,479,559]+[0x8000]*5,'staggered cycle did not reach independent reset counters')
    return stages

def worker(directory,snapshot):
    before=hashes();check(before==json.loads(Path(snapshot).read_text()),'animation input snapshot changed')
    native=Native(directory);rows=[];sites=set();edges=set()
    def record(name,core,ref):
        sites.update(ref['sites']);edges.update(ref['edges'])
        rows.append(dict(case=name,core=core,steps=ref['steps'],events=len(ref['events']) if not isinstance(ref['events'],int) else ref['events'],far_return_events=ref['far_return_events']))
    for c in cases():
        for core in ((True,False) if c.get('kind')!='drawing' or c['name'].endswith('ordinary') or c.get('expected',0) else (False,)):record(c['name'],core,compare(native,c,core))
        gc.collect();print('CHECKED '+c['name'],flush=True)
    for load in base.LOADS:
        for name,ref in handoff(native,load):record(name,False,ref)
        gc.collect();print(f'CHECKED same-RAM animation cycle{load:04x}',flush=True)
    check(set(OWN)<=sites,'animation sites missing: '+str(sorted(set(OWN)-sites)))
    check(EDGES<=edges,'animation outcomes missing: '+str(sorted(EDGES-edges)))
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in ((1,'initialize-pinned'),(2,'tick-counter-fff1'),(3,'tick-counter-0000'),(4,'tick-live-count'),(5,'tick-far-ip-changed'),(6,'drawing-bitmap-live-ax'),(7,'drawing-row-ordinary'),(8,'drawing-rows-ordinary'),(9,'drawing-backdrop-ordinary')):
        try:compare(Native(directory,mutation),lookup[name],True)
        except base.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise base.OracleFailure(f'animation mutant{mutation} survived')
        gc.collect()
    check(before==hashes(),'animation inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(base.IMAGE),own_known_bytes=sum(i.size for i in OWN.values()),
        known_connected_bytes=sum(i.size for i in INS.values()),entry_code_ranges=[list(r) for r in RANGES],
        case_count=len(cases())+len(base.LOADS),comparison_count=len(rows),handoff_count=len(base.LOADS),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),instruction_steps=sum(r['steps'] for r in rows),
        ordered_bus_events=sum(r['events'] for r in rows),declared_far_return_events=sum(r['far_return_events'] for r in rows),
        mutation_count=len(mutants),mutations=mutants,input_hashes=before,rows=rows,
        limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS,drawing_instructions=DRAW_STEPS,drawing_events=DRAW_EVENTS,long_shift_instructions=20_000_000,long_shift_events=5_000_000),
        unverified_fixture_domains=[dict(case=c,reason='Original instruction budget exhausted with VGA stack; no completed differential or mutation credit') for c in UNVERIFIED_CASES],
        entry_offsets=dict(initialize=0x4FF8,tick=0x4F96,backdrop=0x4EEF,rows=0x4F2B,row=0x4F4A,bitmap=0x4F6E),
        pinned_ui_sections=[dict(index=i,decoded_bytes=len(b),sha256=sha(b)) for i,b in zip((3,4),resource_banks())],
        scope='4EEF/4F2B/4F4A/4F6E connected menu drawing,4FF8 initializer and4F96 countdown/renderer parent, actual frame/segment/flag effects and three same-RAM218-tick cycles. Constructed and pinned decoded graphics banks; no upstream allocation/loader execution, selector-EA wrap at SPFFFE/FFFF, scheduling or whole-menu proof.'))
    print(f'PASS menu animation: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(EDGES)} outcomes,{len(mutants)} mutants',flush=True)

def main():
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]:raise SystemExit('usage: menu_animation.py')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='menu-animation-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

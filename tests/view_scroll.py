"""4085 selector/edge scroll and414F left scroll, shared-engine differential.

The complete adapter tail-enters the existing410F visibility core. No IRQ
delivery is modelled. Signed guards and the exact right-limit equality are
tested in raw-entry states as well as the ordinary view-origin domain.
"""
import copy
import ctypes as ct
import gc
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
import view_visibility as visibility
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json
OWN_RANGES=((0x4085,0x408E),(0x408F,0x4095),(0x4096,0x40B3),(0x40B4,0x410F),(0x414F,0x417B))
OWN={i.address:i for a,b in OWN_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
INS=OWN|visibility.VIS_INS;EDGES=v.direct_jump_edges(OWN)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=180,384,1000,3000
REPORT=BUILD/'view-scroll-differential.json'
class Result(ct.Structure):_fields_=[('registers',v.Regs),('status',ct.c_uint16)]
class Access(v.BusAccess):
    def __init__(self,c,memory,r,device):super().__init__(c,memory,r,device,max_events=MAX_EVENTS)

def cases():
    rows=[]
    for scan in (0x2C,0x2D):
        for selector in (0,1,2,3,8,9,10,255):
            for refresh in (0,1,255):rows.append(dict(name=f'key-{scan}-{selector}-{refresh}',scan=scan,selector=selector,refresh=refresh))
    for origin in (0,8,0x10,0x18,0x20,0x4F0,0x4F8,0x500,0x508,0x7FFF,0x8000,0xFFF8):
        for x in (8,0x148):
            for button in (0,2):rows.append(dict(name=f'edge-{origin}-{x}-{button}',origin=origin,x=x,buttons=button))
    for y in (0xB7,0xB8,0x7FF7,0x7FF8,0x8000,0xFFF8):rows.append(dict(name=f'signed-y-{y}',y=y,x=0x148))
    rows += [dict(name='no-edge',x=9),dict(name='direct-left',entry=1,x=0),
        dict(name='df-tail',entry=1,flags=0x6D7),dict(name='live-marker-segment',entry=1,ss=0x8400),
        dict(name='caller-word-overwritten-by-map',ss=0x6000,sp=0x0EAA),
        dict(name='wrapped-caller-word',ss=0xFFF0,sp=0xFF)]
    return [dict(load=v.LOADS[i%3],seed=0x4085+i,entry=0,scan=0,selector=2,refresh=0,
        origin=0x180,x=8,y=20,buttons=0,ss=0x7000,sp=0x8000,flags=0xAD7)|c for i,c in enumerate(rows)]
def setup(c):
    memory,device=v.initial_memory(c)
    r=v.default_regs(c['load'],c['seed'],ds=0x6000,ss=c['ss'],sp=c['sp'],flags=c['flags'])
    r['ip']=0x414F if c['entry'] else 0x4085
    for off,value in ((0,c['origin']),(2,c['origin']//8),(0x10,c['x']),(0x12,c['y']),
                      (0x14,c['buttons']),(0x26,0x42),(0x28,0x57)):v.put16(memory,r['ds'],off,value,device)
    for off,value in ((0x1FD0,c['scan']),(0x82,c['selector']),(0x84,c['refresh'])):v.sync_memory_byte(memory,device,r['ds'],off,value)
    v.put16(memory,r['ss'],r['sp'],0xEED1,device);device.trace=v.PackedDeviceTrace(MAX_EVENTS)
    return memory,r,device
def original(c,memory,r,device,core=False):
    access=Access(c,memory,r,device)
    return v.OriginalMachine(c,memory,r,device,core,instructions=INS,access=access,
        outer_returns={p for p,i in INS.items() if i.mnemonic=='ret'},max_steps=MAX_STEPS).run()
class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'scroll-{mutation}.dll',mutation,'view_scroll')))
        self.fn=self.lib.lmn_view_scroll_adapter;self.fn.restype=Result
        self.fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_int,ct.POINTER(v.Bus)]
    def run(self,c,memory,r,device,core=False):
        memory,device=bytearray(memory),copy.deepcopy(device);a=Access(c,memory,r,device);cb=v.NativeCallbacks(a)
        fn=getattr(self.lib,'lmn_view_scroll_'+('core' if core else 'adapter'))
        fn.restype=Result;fn.argtypes=self.fn.argtypes
        out=fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(v.Regs(**r)),c['entry'],ct.byref(cb.bus))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,
            memory=memory,device=device,events=a.events,providers=a.providers,cursor=a.cursor)
def compare(native,c,core=False):
    memory,r,device=setup(c);reference=original(c,bytearray(memory),dict(r),copy.deepcopy(device),core)
    actual=native.run(c,memory,r,device,core);v.compare_states(c['name'],actual,reference);return reference
def hashes():
    paths=set(source_files('view_scroll'))|set((ROOT/'c').glob('*.h'))
    paths.update(ROOT/p for p in ('tests/view_scroll.py','tests/verification.py','tests/view_visibility.py',
        'tools/cbuild.py','tools/bounded_process.py','metadata/symbols.json','assets/vgalemmi.exe',
        'src/game_code_late_after_selection.asm','src/game_code_after_view_visibility.asm','src/view_visibility.asm'))
    return {str(p.relative_to(ROOT)).replace('\\','/'):sha(p.read_bytes()) for p in sorted(paths)}
def worker(directory):
    started=time.monotonic();before=hashes();native=Native(directory);sites=set();edges=set();rows=[]
    for c in cases():
        for core in (True,False):
            out=compare(native,c,core);sites|=out['sites'];edges|=out['edges'];rows.append(dict(name=c['name'],core=core,steps=out['steps'],events=len(out['events'])))
        gc.collect()
    v.check(set(OWN)<=sites,f'missing scroll sites {sorted(set(OWN)-sites)}')
    v.check(EDGES<=edges,f'missing scroll outcomes {sorted(EDGES-edges)}')
    lookup={c['name']:c for c in cases()};mutants=[]
    witnesses={1:'key-44-2-0',2:'signed-y-32760',3:'edge-1288-328-0',4:'edge-24-8-2'}
    for mutation,name in witnesses.items():
        try:compare(Native(directory,mutation),lookup[name])
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,mismatch=str(error),completed=True))
        else:raise v.OracleFailure(f'scroll mutant {mutation} survived')
    v.check(before==hashes(),'scroll inputs changed during campaign')
    write_json(REPORT,dict(code_ranges=OWN_RANGES,own_bytes=sum(i.size for i in OWN.values()),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(edges&EDGES),cases=rows,mutations=mutants,
        runtime_seconds=time.monotonic()-started,input_hashes=before,
        limits=dict(seconds=SECONDS,memory_mib=MEMORY_MIB,steps=MAX_STEPS,events=MAX_EVENTS)))
    print(f'PASS view scroll: {len(rows)} comparisons, {len(set(OWN)&sites)} sites, {len(EDGES)} outcomes, {len(mutants)} mutants',flush=True)
def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    with temporary_build_directory(prefix='view-scroll-',parent=BUILD) as directory:
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',str(directory)],cwd=ROOT,
            timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

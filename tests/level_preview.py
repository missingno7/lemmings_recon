"""7EB2 preview sampling on the shared bounded original/native verifier."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import BUILD,sha,write_json

ENTRY,RETURN,END=0x7EB2,0x80FC,0x80FD
INS={i.address:i for i in base.MD.disasm(base.IMAGE[ENTRY:END],ENTRY)}
EDGES=base.direct_jump_edges(INS)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=600,384,1_000_000,250_000
REPORT=BUILD/'level-preview-differential.json'
FIELDS=('ax','bx','cx','dx','si','di','bp','ds','es','ss','sp','flags')
class State(ct.Structure):
    _fields_=[(n,ct.c_uint16) for n in FIELDS]
class Result(ct.Structure):
    _fields_=[('state',State),('code_segment',ct.c_uint16),('continuation',ct.c_uint16),('status',ct.c_int)]

def cases():
    rows=[dict(name=f'full-{load:04x}',load=load,full=True) for load in base.LOADS]
    rows += [dict(name='full-df',flags=0x6D7,full=True),
             dict(name='full-if-clear',flags=0xD7,full=True),
             dict(name='full-overlap',origin=0x4F22-0x64F,full=True),
             dict(name='full-forward-overlap',origin=0x4F23-0x64F,full=True),
             dict(name='full-destination-wrap',origin=0xFFF0-0x64F,full=True),
             dict(name='full-coordinate-wrap',origin=0xFFFF,page=0xFFFF,full=True)]
    rows += [dict(name='short'),dict(name='short-df',flags=0x6D7),
             dict(name='short-saved-ds',patch='ds'),dict(name='short-saved-source',patch='si'),
             dict(name='short-saved-destination',patch='di'),dict(name='short-saved-port',patch='dx'),
             dict(name='short-live-page',patch='page'),dict(name='short-live-plane',patch='plane'),
             dict(name='short-outer-return',patch='ret'),dict(name='short-stack-wrap',sp=0),
             dict(name='short-stack-word-ffff',sp=0xFFFF),
             dict(name='short-stack-physical-wrap',ss=0xFFFE,sp=0x21),
             dict(name='short-data-physical-wrap',ds=0xFFFF),
             dict(name='short-coordinate-stack-alias',ss=0x3000,sp=0x1F78),
             dict(name='short-mirror-stack-alias',sp=0x16),
             dict(name='missing-word-output',missing_word_out=True,expected=1)]
    return [dict(load=base.LOADS[0],seed=0x7EB2+i,flags=0xAD7,origin=0,page=0)|r
            for i,r in enumerate(rows)]

def setup(c):
    memory,device=base.initial_memory(c)
    r=base.default_regs(c['load'],c['seed'],ds=c.get('ds',0x3000),
        ss=c.get('ss',0x5000),sp=c.get('sp',0x9000),flags=c['flags'])
    r['ip']=ENTRY
    base.put16(memory,r['ds'],0x1F76,c['origin'],device)
    base.put16(memory,r['ds'],0x1F7A,c['page'],device)
    if r['ss']==0xA000:
        for plane in device.planes:plane[0x8FC0:0x9020]=bytes(0x60)
    # Each source lane/plane sees every byte value in an ordinary full run.
    for plane,values in enumerate(device.planes):
        for y in range(39):
            for x in range(52):
                for lane in range(4):
                    values[0x4F22+y*832+x*4+lane]=(y*52+x+lane*67+plane*13)&255
    base.put16(memory,r['ss'],r['sp'],0xD00D,device)
    return memory,r,device

class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=MAX_EVENTS,packed_events=True)
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        got=super().access(kind,address,flags,mask,value)
        ss,sp=self.r['ss'],self.r['sp'];patch=self.c.get('patch')
        if not self.c.get('full'):
            # Finite fixture providers alter the actual completed saved word.
            # Only the initial52/39 is shortened; a later saved1 must stay1.
            for delta,initial,new,name in ((4,39,self.c.get('rows',2),'rows'),
                                            (10,52,self.c.get('columns',2),'columns')):
                off=(sp-delta)&65535
                if kind=='write' and address==(base.physical(ss,off)+1)&base.MASK:
                    if base.get16(self.memory,ss,off)==initial:
                        self.patch(ss,off,new,name)
        if patch and patch not in self.providers:
            saved={'ds':(2,0x4567),'si':(6,0xFEFE),'di':(8,0xFFFF),'dx':(12,0x3CA)}
            if patch in saved:
                delta,new=saved[patch];off=(sp-delta)&65535
                if kind=='write' and address==(base.physical(ss,off)+1)&base.MASK:
                    self.patch(ss,off,new,patch)
            elif patch=='page' and kind=='read' and address==base.physical(self.r['ds'],0x1F77):
                self.patch(self.r['ds'],0x1F7A,0xFFF0,patch)
            elif patch=='plane' and kind=='read' and address==0xA064F:
                # Plane3 has not yet been sampled. Do not prefetch all planes.
                self.device.planes[3][0x4F22]^=0x22;self.providers.add(patch)
        return got
    def out_word(self,port,value,flags,mask=base.FLAGS):
        self.emit('out_word',port,value,flags,mask)
        if port in (0x3C4,0x3CE):self.device.out(port,value,flags)
        else:base.check(port==0x3CA,'undeclared preview port')
        if self.c.get('patch')=='ret' and 'ret' not in self.providers:
            self.patch(self.r['ss'],self.r['sp'],0xBEAD,'ret')

def reference(c,memory,r,device,core):
    memory,device=bytearray(memory),copy.deepcopy(device)
    return base.OriginalMachine(c,memory,dict(r),device,core,instructions=INS,
        access=Access(c,memory,dict(r),device),outer_returns={RETURN},max_steps=MAX_STEPS).run()

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'level-preview-{mutation}.dll',mutation,'level_preview')))
        self.core=self.lib.lmn_draw_level_preview_core;self.core.restype=Result
        self.core.argtypes=[base.MEM,ct.c_uint16,ct.POINTER(State),ct.POINTER(base.Bus)]
        self.adapter=self.lib.lmn_draw_level_preview_adapter;self.adapter.restype=Result
        self.adapter.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Bus)]
    def run(self,c,memory,r,device,core):
        memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,r,device);callbacks=base.NativeCallbacks(access)
        if c.get('missing_word_out'):callbacks.bus.out_word=base.OUT()
        mem=(ct.c_uint8*base.SIZE).from_buffer(memory)
        if core:
            state=State(**{n:r[n] for n in FIELDS})
            out=self.core(mem,r['cs'],ct.byref(state),ct.byref(callbacks.bus))
        else:
            regs=base.Regs(**r);out=self.adapter(mem,ct.byref(regs),ct.byref(callbacks.bus))
        return dict(regs={n:getattr(out.state,n) for n in FIELDS}|dict(cs=out.code_segment,ip=out.continuation),
            status=out.status,memory=memory,device=device,events=access.events,providers=access.providers,cursor=access.cursor)

def independent(c,memory,r,device,ref):
    base.check(ref['status']==c.get('expected',0),c['name']+': unexpected preview stop')
    if c.get('patch'):base.check(c['patch'] in ref['providers'],c['name']+': provider unused')
    if not c.get('full'):return
    # Pixel-index model, independent from the C mask/shift expression. It uses
    # live mutable planes so source/destination overlap retains original order.
    expected=[bytearray(p) for p in device.planes];seen=[[set() for _ in range(4)] for _ in range(4)]
    origin=(base.get16(memory,r['ds'],0x1F76)+base.get16(memory,r['ds'],0x1F7A)+0x64F)&65535
    for y in range(39):
        for x in range(52):
            for plane in range(4):
                output=0
                for bit in range(8):
                    lane=bit//2;source=(0x4F22+y*832+x*4+lane)&65535
                    byte=expected[plane][source];seen[plane][lane].add(byte)
                    if byte&(1<<(5 if bit%2==0 else 1)):output|=1<<(7-bit)
                dest=(origin+y*80+x)&65535
                expected[plane][dest]|=output
    base.check(tuple(bytes(p) for p in expected)==tuple(bytes(p) for p in ref['device'].planes),c['name']+': independent plane footprint differs')
    if c['name'].startswith('full-') and c['name'][5:] in ('1010','1213','2345'):
        base.check(all(len(s)==256 for plane in seen for s in plane),'byte-lane truth table incomplete')
    base.check(ref['regs']['ds']==r['ds'] and ref['regs']['es']==0xA000,'preview returned segment contract differs')
    base.check(ref['regs']['flags']&0x200,'preview must finish STI')

def compare(native,c,core):
    memory,r,device=setup(c);ref=reference(c,memory,r,device,core)
    independent(c,memory,r,device,ref)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref

def hashes():
    paths={'tests/level_preview.py','tests/verification.py','tests/minimap_vga.py',
        'tools/cbuild.py','tools/difftest.py','tools/bounded_process.py','tools/common.py','tools/unpack.py',
        'c/level_preview.c','c/level_preview.h','c/video_restore.h','c/special_blit.h','c/regs.h',
        'c/lemmings_sym.h','src/level_preview.asm','metadata/oracle.json','metadata/toolchain-lock.json',
        'assets/vgalemmi.exe'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

MUTANTS=((1,'short'),(2,'short'),(3,'short'),(4,'short'),(5,'short'),
         (6,'short'),(7,'short'),(8,'short-saved-ds'),(9,'short'))
def worker(directory,snapshot,selected):
    before=hashes();base.check(before==json.loads(Path(snapshot).read_text()),'preview inputs changed')
    native=Native(directory);sites=set();edges=set();rows=[]
    for c in cases():
        if selected and c['name'] not in selected:continue
        for core in (True,False):
            ref=compare(native,c,core);sites.update(ref['sites']);edges.update(ref['edges'])
            rows.append(dict(case=c['name'],core=core,steps=ref['steps'],events=len(ref['events'])))
            del ref;gc.collect()
        print('CHECKED '+c['name'],flush=True)
    base.check(bool(rows),'unknown preview selection')
    if selected:return
    base.check(set(INS)<=sites,'preview instruction sites missing')
    base.check(EDGES<=edges,'preview branch outcomes missing')
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in MUTANTS:
        try:compare(Native(directory,mutation),lookup[name],True)
        except base.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise base.OracleFailure(f'preview mutant{mutation} survived')
        gc.collect()
    base.check(before==hashes(),'preview inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(base.IMAGE),case_count=len(cases()),comparison_count=len(rows),
        own_known_bytes=END-ENTRY,known_connected_bytes=END-ENTRY,native_code_ranges=[[ENTRY,END]],
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),
        mutation_count=len(mutants),mutations=mutants,input_hashes=before,rows=rows,
        limits=dict(worker_seconds=SECONDS,process_tree_commit_mib=MEMORY_MIB,instructions_each=MAX_STEPS,events_each=MAX_EVENTS),
        domain='Native7EB2..80FC four-plane source sampling and OR-latch publication. Full ordinary geometry/overlap at core and actual nearRET; live finite saved-word/provider aliases. Intact code,quiescent IRQ and unchained VGA fixture; arbitrary nonterminating aliases and full briefing/platform integration remain open.'))
    print(f'PASS level preview: {len(rows)} comparisons,{len(sites)} sites,{len(edges)} outcomes,{len(mutants)} mutants',flush=True)

def main():
    if len(sys.argv)>=4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3],sys.argv[4:]);return
    selected=sys.argv[2:] if len(sys.argv)>1 and sys.argv[1]=='--focus' else []
    if sys.argv[1:] and not selected:raise SystemExit('usage: level_preview.py [--focus CASE ...]')
    if not selected:REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='level-preview-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot),*selected],
            cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

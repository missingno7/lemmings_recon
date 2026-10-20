"""Shared-engine palette/sound/dirty-page setup through native status/layout."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
from cbuild import build,source_files
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,sha,write_json

OWN_RANGES=((0x482F,0x483F),(0x4840,0x4877),(0x52F4,0x531D),(0x5377,0x53CA),
            (0x7900,0x796F),(0x80FD,0x8122),(0x8123,0x8238))
CHILD_RANGES=((0x39CE,0x3AC8),(0x4B68,0x4BBE),(0x5425,0x5447),(0x548C,0x54C4),
              (0x75EF,0x7708),(0x780D,0x789E),(0x8808,0x8822))
OWN={i.address:i for a,b in OWN_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
INS=OWN|{i.address:i for a,b in CHILD_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
EDGES=v.direct_jump_edges(OWN)
ENTRIES=(0x52F4,0x5377,0x482F,0x7900,0x80FD,0x81CC)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=900,384,2_000_000,1_000_000
REPORT=BUILD/'game-prepare-differential.json'
class Result(ct.Structure):
    _fields_=[('registers',v.Regs),('status',ct.c_uint16),('child_status',ct.c_uint16)]

def cases():
    rows=[]
    def add(name,entry,**kw):rows.append(dict(name=name,entry=entry,**kw))
    for mode in (0,2,4,0x104,0xFFFF):
        add(f'base-{mode}',0,mode=mode)
        for option in (0,255):add(f'fade-{mode}-{option}',1,mode=mode,option=option)
    for mode in (2,4):
        for name,kw in (('df',dict(flags=0x6D7)),('saved-es',dict(patch='saved-es')),
                        ('table-live',dict(patch='fade-table')),('source-wrap',dict(source_wrap=True))):
            add(f'fade-{mode}-{name}',1,mode=mode,**kw)
    add('base-live-child-return',0,mode=4,patch='palette-return',expected=2)
    add('base-blanking',0,mode=4,blanking=0)
    add('base-missing-output',0,mode=4,missing_out=True,expected=1,child_status=2)
    add('base-missing-input',0,mode=2,missing_in=True,expected=1,child_status=1)
    for n in range(256):
        add(f'sound-special-{n}',2,special=n)
        add(f'sound-cycle-{n}',2,cycle=n,outcome=1)
    for name,kw in (('disabled',dict(enabled=0)),('enabled-one',dict(enabled=1)),
                    ('outcome-ff',dict(outcome=255,cycle=16)),('stale-cycle',dict(cycle=31)),
                    ('stack-alias',dict(ss=0x6000,sp=0x56)),('stack-wrap',dict(sp=1)),
                    ('physical-wrap',dict(ss=0xFFFF,sp=0xF)),('outer-live',dict(patch='sound-outer'))):
        add('sound-'+name,2,**kw)
    for entry in (3,4,5):
        for load in v.LOADS:add(f'drawing-{entry}-{load:04x}',entry,load=load)
    for name,kw in (('empty',dict(pattern='empty',full=0)),('isolated',dict(pattern='isolated',full=0)),
                    ('last',dict(pattern='last',full=0)),('all',dict(pattern='all',full=0)),
                    ('ignored-two',dict(pattern='two',full=0)),('df-full',dict(flags=0x6D7)),
                    ('df-scan',dict(flags=0x6D7,full=0,pattern='empty')),
                    ('live-count',dict(full=0,pattern='isolated',patch='inner-count')),
                    ('origin-wrap',dict(origin=0xFFFF)),('source-wrap',dict(scroll=0xFFFF))):
        add('dirty-'+name,4,**kw)
    for entry in (3,4,5):
        add(f'drawing-{entry}-missing-word',entry,missing_word_out=True,expected=3)
    add('backdrop-df',3,flags=0x6D7)
    add('backdrop-stack-mirror-alias',3,sp=0xA)
    add('backdrop-source-overlap',3,origin=0xB1AC)
    add('pages-live-map',5,patch='page-map')
    add('pages-changed-dirty-return',5,patch='dirty-return',expected=2)
    add('pages-changed-layout-cs',5,patch='layout-cs',expected=2)
    add('pages-status-child-stop',5,patch='status-return',expected=1,child_status=2)
    add('pages-stack-wrap',5,sp=0)
    return [dict(load=v.LOADS[0],seed=0x81CC+i,flags=0xAD7,mode=2,option=0,
                 enabled=255,special=0,outcome=0,cycle=0,full=255,pattern='isolated',
                 origin=0,scroll=3,blanking=255,expected=0,child_status=0)|c for i,c in enumerate(rows)]

def setup(c):
    memory,device=v.initial_memory(c);r=v.default_regs(c['load'],c['seed'],ds=0x6000,
        ss=c.get('ss',0x9000),sp=c.get('sp',0x8000),flags=c['flags'])
    r.update(ip=ENTRIES[c['entry']],ax=0xB543)
    ds=r['ds']
    for seg in (ds,0x7000):
        for off,value in ((0x1F7C,c['mode']),(0x1F76,c['origin']),(0x1F78,0x2520),(0x1F7A,0x2C0),
                          (0x1FDA,0x3D4),(0x1FDC,0x3DA),(0x26,0x42B2),(0x28,0x45D3),(2,c['scroll'])):v.put16(memory,seg,off,value)
        for off,value in ((0x200E,c['option']),(0x200C,c['blanking']),(0x2010,c['enabled']),(0xFE8,c['special']),
                          (0x1F6D,c['outcome']),(0x1F6C,c['cycle']),(0x45,7),(0x64,1),(0x67,99),(0x82,2)):
            v.put8(memory,seg,off,value)
        for off in (0x6A,0x6D,0x70,0x73,0x76,0x79,0x7C,0x7F):v.put8(memory,seg,off,0)
    # Both dirty maps and the live row buffers belong to SS, separate from DS.
    for off in range(0x4200,0x4E00):v.put8(memory,r['ss'],off,0)
    for base in (0x42B2,0x45D3):v.put8(memory,r['ss'],base,c['full'])
    pattern=c['pattern']
    for y in range(20):
        cols=range(40) if pattern=='all' else (39,) if pattern=='last' else (0,5,6,19,38) if pattern=='isolated' else (3,) if pattern=='two' else ()
        for x in cols:
            off=(0x42B3+(-1 if c['flags']&0x400 else 1)*(y*40+x))&65535
            v.put8(memory,r['ss'],off,2 if pattern=='two' else 1)
    # Parent initialization deliberately replaces these leading flags itself.
    if c['entry']==5:
        v.put8(memory,r['ss'],0x42B2,0);v.put8(memory,r['ss'],0x45D3,0)
    if c.get('source_wrap'):
        v.put16(memory,c['load'],(0x52E4 if c['mode']==4 else 0x52D4)+10,0xFFFF)
    for i in range(48):v.put8(memory,ds,0x2608+i,(i*7+3)&63)
    v.put16(memory,r['ss'],r['sp'],0xD00D)
    device.trace=v.PackedDeviceTrace(MAX_EVENTS)
    return memory,r,device

class Access(v.BusAccess):
    def __init__(self,*args):super().__init__(*args,max_events=MAX_EVENTS,packed_events=True);self.input_count=0
    def access(self,kind,address,flags,mask=v.FLAGS,value=None):
        c=self.c;patch=c.get('patch');ds=self.r['ds'];ss=self.r['ss'];sp=self.r['sp']
        if patch not in self.providers:
            if patch=='saved-es' and kind=='read' and address==v.physical(ss,(sp-2)&65535):self.patch(ss,(sp-2)&65535,0x7000,patch)
            if patch=='fade-table' and kind=='read' and address==v.physical(c['load'],(0x52E4 if c['mode']==4 else 0x52D4)+12):
                self.patch(c['load'],(0x52E4 if c['mode']==4 else 0x52D4)+12,0x6200,patch)
        got=super().access(kind,address,flags,mask,value)
        if patch not in self.providers and kind=='write':
            if patch=='sound-outer' and address==v.physical(ds,0x54):self.patch(ss,sp,0xBEAD,patch)
            if patch=='inner-count' and v.VGA_BASE<=address<v.VGA_END:self.patch(ss,(sp-18)&65535,1,patch)
            if patch=='page-map' and address==v.physical(ds,0x1F76) and value==0x20:self.patch(ds,0x28,0x4900,patch)
            if patch=='dirty-return' and address==v.physical(ss,0x42B2) and value==0:self.patch(ss,(sp-2)&65535,0xD234,patch)
            if patch=='layout-cs' and address==v.physical(ds,0x66F2):self.patch(ss,(sp-2)&65535,0xD234,patch)
        return got
    def inp(self,port,flags,mask=v.FLAGS):
        v.check(port in (0x3DA,0x3C5),'undeclared setup input');value=0x93 if port==0x3C5 else 0;self.input_count+=1;self.cursor+=1
        v.check(self.input_count<=2,'attribute input budget exhausted');self.emit('in',port,value,flags,mask);return value
    def out(self,port,value,flags,mask=v.FLAGS):
        v.check(port in (0x3C0,0x3C4,0x3C5,0x3C8,0x3C9),'undeclared byte output');self.emit('out8',port,value,flags,mask)
        if self.c.get('patch')=='palette-return' and 'palette-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,'palette-return')
    def out_word(self,port,value,flags,mask=v.FLAGS):
        self.emit('out',port,value,flags,mask);self.device.out(port,value,flags)
        if self.c.get('patch')=='status-return' and 'status-return' not in self.providers:
            ss=self.r['ss'];off=(self.r['sp']-4)&65535
            if v.get16(self.memory,ss,off)==0x39D1:self.patch(ss,off,0xD234,'status-return')

class Machine(v.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        frames=[];failed=[];self.child_status=0
        def before(m,i):
            if i.mnemonic in ('in','out'):
                if i.mnemonic=='out' and i.operands[-1].size==2 and c.get('missing_word_out'):m.stop(3);return True
                if c.get('missing_in' if i.mnemonic=='in' else 'missing_out'):
                    m.child_status=1 if i.mnemonic=='in' else 2;m.stop(1);return True
            if i.mnemonic in ('call','lcall'):frames.append((i.address,i.address+i.size,i.mnemonic=='lcall'))
            return False
        def expected(m,off):
            v.check(bool(frames),'undeclared preparation child return');failed[:]=[frames.pop()];owner,resume,far=failed[-1]
            return {(c['load'],resume)} if far else {resume}
        def changed(m,off):
            if failed[-1][0]==0x39CE:m.child_status=2;return 1
            v.check(failed[-1][0] in OWN,'changed return outside inherited status domain');return 2
        super().__init__(c,memory,r,device,core,instructions=INS,access=Access(c,memory,r,device),
            outer_returns=lambda m,off:not frames,child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            far_returns={p:expected for p,i in INS.items() if i.mnemonic=='retf'},
            before=before,changed_return_status=changed,max_steps=MAX_STEPS)
    def run(self):out=super().run();out['child_status']=self.child_status;return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'game-prepare-{mutation}.dll',mutation,'game_prepare')));self.functions={}
        for core in (True,False):
            fn=getattr(self.lib,'lmn_game_prepare_'+('core' if core else 'adapter'));fn.restype=Result
            fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_int,ct.POINTER(v.Ports),ct.POINTER(v.Bus)];self.functions[core]=fn
    def run(self,c,memory,r,device,core):
        memory,device=bytearray(memory),copy.deepcopy(device);access=Access(c,memory,r,device)
        cb=v.NativeCallbacks(access,missing_in=c.get('missing_in'),missing_out=c.get('missing_out'))
        if c.get('missing_word_out'):cb.bus.out_word=v.OUT()
        regs=v.Regs(**r);out=self.functions[core]((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(regs),c['entry'],ct.byref(cb.ports),ct.byref(cb.bus))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,child_status=out.child_status,
            memory=memory,device=device,events=access.events,providers=access.providers,cursor=access.cursor)

def independent(c,memory,r,device,ref,core):
    if c.get('patch') or ref['status']:return
    if c['entry']==2:
        if c['enabled']:
            idx=(c['special']-1)&255 if c['special'] else ((c['cycle']+1)&255) if c['outcome'] else 0
            if not c['special'] and c['outcome'] and idx==17:idx=0
            at=(0x4888 if c['special'] else 0x4877)+idx
            v.check(ref['memory'][v.physical(r['ds'],0x54)]==v.IMAGE[at],'independent sound ID differs')
    if c['entry']==0 and c['mode']==4:
        banks=[e[2] for e in ref['events'] if e[:2]==('out8',0x3C8)]
        v.check(banks==[0,16],'base palette bank starts differ')
        colors=[e[2] for e in ref['events'] if e[:2]==('out8',0x3C9)]
        v.check(colors==[(i*7+3)&63 for i in range(48)],'base palette source continuation differs')
    if c['entry']==4 and c['full'] and not (c['flags']&0x400):
        expected=[bytearray(p) for p in device.planes]
        for y in range(160):
            for x in range(44):
                src=(0x4A40+c['scroll']+y*208+x)&65535;dst=(c['origin']+0x2C2+y*44+x)&65535
                for plane in expected:plane[dst]=plane[src]
        v.check(expected==ref['device'].planes,'independent full-page plane copy differs')
    if c['entry']==3 and not (c['flags']&0x400):
        expected=[bytearray(p) for p in device.planes];start=(c['origin']+0x2174)&65535
        for plane in expected:
            for x in range(13):plane[(start+x)&65535]=0
            for y in range(19):
                for x in range(13):plane[(start+44+y*44+x)&65535]=plane[(0xD320+y*13+x)&65535]
        v.check(expected==ref['device'].planes,'independent status backdrop differs')
    if c['entry']==4 and not c['full']:
        for n in range(800):
            off=(0x42B3+(-1 if c['flags']&0x400 else 1)*n)&65535
            v.check(ref['memory'][v.physical(r['ss'],off)]==0,'partial map clear differs')
        if not (c['flags']&0x400):
            expected=[bytearray(p) for p in device.planes]
            for y in range(20):
                cells=[memory[v.physical(r['ss'],0x42B3+y*40+x)] for x in range(40)];x=0
                while x<40:
                    if cells[x]!=1:x+=1;continue
                    end=x+1
                    while end<40 and cells[end]==1:end+=1
                    if end<40:end+=1 # REPE consumes the first nonmatching byte too.
                    for row in range(8):
                        for col in range(x,end):
                            src=(0x4A40+c['scroll']+(y*8+row)*208+col)&65535
                            dst=(c['origin']+0x2C2+(y*8+row)*44+col)&65535
                            for plane in expected:plane[dst]=plane[src]
                    x=end
            v.check(expected==ref['device'].planes,'independent partial rectangles differ')

def compare(native,c,core):
    memory,r,device=setup(c);ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    v.check((ref['status'],ref['child_status'])==(c['expected'],c['child_status']),c['name']+': unexpected stop')
    actual=native.run(c,memory,r,device,core);v.compare_states(c['name'],actual,ref)
    if c.get('patch'):v.check(c['patch'] in ref['providers'],c['name']+': unused live-word fixture')
    independent(c,memory,r,device,ref,core);return ref

def hashes():
    paths={'tests/game_prepare.py','tests/verification.py','tests/minimap_vga.py','tools/cbuild.py','tools/difftest.py',
        'tools/bounded_process.py','tools/common.py','tools/unpack.py','metadata/oracle.json','metadata/toolchain-lock.json',
        'assets/vgalemmi.exe','src/palette_frontends.asm','src/input_menu_and_retry.asm','src/game_code_before_minimap.asm',
        'src/game_code_after_level_preview.asm','src/status_initialize.asm','src/status_copy.asm','src/status_glyphs.asm',
        'src/status_icons.asm','src/decimal_fields.asm','src/code_tail.asm'}
    pending=list(source_files('game_prepare'))
    while pending:
        p=pending.pop();name=p.relative_to(ROOT).as_posix()
        if name in paths:continue
        paths.add(name)
        pending.extend(p.parent/name for name in re.findall(r'#include\s+"([^"]+)"',p.read_text()))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

MUTANTS=((1,'base-4'),(2,'fade-4-df'),(3,'sound-cycle-32'),(4,'dirty-empty'),(5,'base-live-child-return'),
         (6,'dirty-isolated'),(7,'drawing-4-1010'),(8,'pages-live-map'))
def worker(directory,snapshot,selected):
    before=hashes();v.check(before==json.loads(Path(snapshot).read_text()),'preparation inputs changed')
    native=Native(directory);rows=[];sites=set();edges=set()
    for c in cases():
        if selected and c['name'] not in selected:continue
        for core in (True,False):
            ref=compare(native,c,core);sites.update(ref['sites']);edges.update(ref['edges'])
            rows.append(dict(case=c['name'],core=core,steps=ref['steps'],events=len(ref['events']),status=ref['status']))
            del ref;gc.collect()
        print('CHECKED '+c['name'],flush=True)
    v.check(bool(rows),'empty preparation selection')
    if selected:return
    v.check(set(OWN)<=sites,'missing preparation sites: '+str(sorted(set(OWN)-sites)))
    v.check(EDGES<=edges,'missing preparation outcomes: '+str(sorted(EDGES-edges)))
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in MUTANTS:
        try:compare(Native(directory,mutation),lookup[name],True)
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise v.OracleFailure('surviving preparation mutant')
    v.check(before==hashes(),'preparation inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(v.IMAGE),case_count=len(cases()),comparison_count=len(rows),
        native_code_ranges=[list(p) for p in OWN_RANGES],own_known_bytes=sum(i.size for i in OWN.values()),known_connected_bytes=sum(i.size for i in INS.values()),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),
        mutation_count=len(mutants),mutations=mutants,instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),rows=rows,input_hashes=before,
        limits=dict(worker_seconds=SECONDS,windows_process_mib=MEMORY_MIB,windows_tree_mib=MEMORY_MIB+256,instructions_each=MAX_STEPS,events_each=MAX_EVENTS),
        domain='Six connected game setup entries,palette/status/layout native children,canonical DS/ES/SS fields,VGA planes/latches,DF strings and SCAS flags,actual near/far frames and unchecked sound IDs. Original instructions remain pinned;UNKNOWN483F/531D/8122 excluded. Child/provider/IRQ and RETF selector-EA-wrap scopes retained;03E7/game/platform/aggregate acceptance remains open.'))
    print(f'PASS game preparation: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(EDGES)} outcomes,{len(mutants)} mutants',flush=True)
def main():
    if len(sys.argv)>=4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3],sys.argv[4:]);return
    selected=sys.argv[2:] if len(sys.argv)>1 and sys.argv[1]=='--focus' else []
    if sys.argv[1:] and not selected:raise SystemExit('usage: game_prepare.py [--focus CASE ...]')
    if not selected:REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='game-prepare-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot),*selected],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

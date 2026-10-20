"""Connected main menu over shared original execution and native callbacks."""
import copy
import ctypes as ct
import gc
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
import keyboard_input as keyboard
import menu_scroll as scroll
import menu_animation as animation
import menu_cache as cache
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import BUILD,sha,write_json
check=base.check
physical,put16,get16=base.physical,base.put16,base.get16
ENTRIES=(0x4401,0x4453,0x445B,0x4478)
RANGES=((0x4401,0x44A3),(0x44A4,0x44AA),(0x44AB,0x44E9),(0x44EC,0x454C))
OWN={i.address:i for a,b in RANGES for i in base.MD.disasm(base.IMAGE[a:b],a)}
EXITS=(0x4D0,0x4967,0x4A01,0x454C)
BOUNDARY={p:next(base.MD.disasm(base.IMAGE[p:p+16],p)) for p in EXITS}
PAGES={i.address:i for a,b in ((0x4DC2,0x4DF7),(0x4DF8,0x4E37)) for i in base.MD.disasm(base.IMAGE[a:b],a)}
INS=keyboard.DOMAINS['reader']|keyboard.DISPLAY|keyboard.SWAP|PAGES|keyboard.text.INS|keyboard.background.INS|keyboard.palette.INS|scroll.INS|animation.INS|cache.INS|OWN|BOUNDARY
EDGES=base.direct_jump_edges(OWN)
REPORT=BUILD/'main-menu-differential.json'
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=480,384,4_000_000,2_000_000
FIXTURES=set()
for module in tuple(sys.modules.values()):
    name=getattr(module,'__file__',None)
    if not name:continue
    path=Path(name).resolve()
    if path.suffix=='.py' and path.is_relative_to(ROOT) and path.parts[-2] in ('tests','tools'):FIXTURES.add(path.relative_to(ROOT).as_posix())
class Result(ct.Structure):
    _fields_=[('registers',base.Regs),('status',ct.c_uint16),('child_status',ct.c_uint16)]

def cases():
    rows=[dict(name='frame-button',entry=2,keys=(None,)),dict(name='release-waits',entry=1,keys=(None,),release_samples=(1,3,8))]
    for key in (0x80,0x81,0x83,0x1B,0,0x42,0x8A,0x60,0x8B,0x2D,0x82):
        rows.append(dict(name=f'key-{key:02x}',keys=(key,0x80)))
    for name,kw in (
        ('blocked',dict(sound_cache=2)),('driver-ff',dict(driver=0xFF,option=2)),
        ('driver-fe',dict(driver=0xFE,option=1)),('driver-zero',dict(driver=0,option=1)),
        ('unexpected-index',dict(option=7)),('index-wrap',dict(option=255)),
        ('toggle-byte',dict(toggle=0x35)),('live-table',dict(patch='table'))):
        rows.append(dict(name='sound-'+name,keys=(0x82,0x80),**kw))
    for key in (0x8A,0x8B):
        for name,kw in (('blocked',dict(group_cache=4)),('zero',dict(group=0)),('three',dict(group=3)),('unexpected',dict(group=7)),('wrap',dict(group=255))):
            rows.append(dict(name=f'group-{key:02x}-'+name,keys=(key,0x80),**kw))
    for load in base.LOADS:
        rows.append(dict(name=f'refresh-{load:04x}',entry=0,keys=(None,),load=load,pinned=True))
        rows.append(dict(name=f'connected-input-{load:04x}',entry=2,load=load,pinned=True,group=1,
                         keys=(0x8A,0x8B,0x82,0x42,0x80)))
    rows += [dict(name='frame-if-df',entry=2,keys=(None,),flags=0x6D7),
             dict(name='frame-stack-wrap',entry=2,keys=(None,),sp=0),
             dict(name='keyboard-word-ffff',entry=3,keys=(0x80,),sp=1),
             dict(name='wait-return',entry=2,keys=(None,),patch='wait-return',expected=2),
             dict(name='scroll-far-return',entry=2,keys=(None,),patch='scroll-far',expected=1,child_status=2),
             dict(name='keyboard-return',entry=3,keys=(0x80,),patch='keyboard-return',expected=2),
             dict(name='missing-status-input',entry=2,keys=(None,),missing_in=True,expected=1,child_status=1),
             dict(name='refresh-display-return',entry=0,keys=(None,),patch='display-return',expected=2),
             dict(name='late-group',keys=(0x8A,0x80),patch='group'),
             dict(name='frame-both-caches',entry=2,keys=(0x80,),sound_cache=2,group_cache=4)]
    return [dict(name='case',entry=3,load=0x1010,seed=0x4401+i,flags=0xD7,group=1,option=0,toggle=0,driver=0xFF)|c for i,c in enumerate(rows)]

def setup(c):
    memory,device=base.initial_memory(c);ds=(c['load']+0x9A9)&65535
    r=base.default_regs(c['load'],c['seed'],ds=ds,ss=c.get('ss',0x6000),sp=c.get('sp',0x9000),flags=c['flags']);r['ip']=ENTRIES[c['entry']]
    for off,value in ((0x1FEE,0x4000),(0x1FF0,0x7000),(0x1FE4,0x5000),(0x1F76,0),(0x1F78,0x6D60),(0x1F7A,0),
                      (0x1FDA,0x3D4),(0x66F0,350),(0x66F2,640),(0x66F4,80),(0x26,0x2000),
                      (0x1D,0x49CE),(0x1F,0x49CE),(0x21,4),(0x23,100),(0x1F7C,2),(0x14,0)):
        put16(memory,ds,off,value,device)
    for off,value in ((0x2A,0),(0x1F6E,c['group']),(0x1F6F,c.get('group_cache',c['group'])),(0x1F70,c['toggle']),
                      (0x1F71,c['option']),(0x1F72,c.get('sound_cache',c['toggle'])),(0x2010,c['driver']),(0x25A7,3),(0x200C,0xFF),(0x1F73,0)):
        base.sync_memory_byte(memory,device,ds,off,value)
    for start,value in ((0x2638,0),(0x2608,1),(0x4920,2)):
        for i in range(64):base.sync_memory_byte(memory,device,ds,start+i,value)
    for i in range(83):base.sync_memory_byte(memory,device,ds,0xF78+i,0)
    for i,v in enumerate(keyboard.PINNED_CHARACTERS):base.sync_memory_byte(memory,device,ds,0x202E+i,v)
    if c['entry']==3:
        base.sync_memory_byte(memory,device,ds,0xF79,0x94);base.sync_memory_byte(memory,device,ds,0x202F,c['keys'][0])
    for i in range(10):
        for j,v in enumerate((0xFFFF if i==0 else 0x8000,0x8000,64+32*i,80,0x100)):
            put16(memory,ds,0x4960+11*i+2*j,v,device)
    if c.get('pinned'):
        for segment,data in zip((0x4000,0x4F21),animation.resource_banks()):
            for i,v in enumerate(data):base.sync_memory_byte(memory,device,segment,i,v)
    else:base.sync_memory_byte(memory,device,ds,0x4AD9,0)
    put16(memory,r['ss'],r['sp'],0xD00D,device)
    return memory,r,device

class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=MAX_EVENTS,packed_events=True)
        self.display_cursor=0;self.input_index=int(c['entry']==3);self.release_cursor=0
    def access(self,kind,address,flags,mask=base.FLAGS,value=None):
        phase=self.c.get('patch')
        if kind=='read' and address==physical(self.r['ds'],0x14) and self.release_cursor<len(self.c.get('release_samples',())):
            v=self.c['release_samples'][self.release_cursor];self.release_cursor+=1
            self.patch(self.r['ds'],0x14,v,'release-'+str(self.release_cursor))
        got=super().access(kind,address,flags,mask,value)
        if phase in self.providers:return got
        if phase=='keyboard-return' and kind=='read' and address==physical(self.r['ds'],0xF78):
            self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,phase)
        if phase=='group' and kind=='read' and address==physical(self.r['ds'],0xF79):self.patch(self.r['ds'],0x1F6E,7,phase,word=False)
        if phase=='table' and kind=='write' and address==physical(self.r['ds'],0x1F71):self.patch(self.c['load'],0x44E9+value,0x55,phase,word=False)
        return got
    def inp(self,port,flags,mask=base.FLAGS):
        check(port==0x3DA,'unexpected main-menu byte input')
        v=(0,8,8,0)[self.display_cursor%4];self.display_cursor+=1;self.cursor+=1
        check(self.display_cursor<=4096,'finite display input schedule exhausted')
        self.emit('in',port,v,flags,mask)
        root=get16(self.memory,self.r['ss'],(self.r['sp']-2)&65535)
        if self.c.get('patch')=='wait-return' and 'wait-return' not in self.providers:
            self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,'wait-return')
        if self.display_cursor%4==0 and root==0x445E:
            check(self.input_index<len(self.c['keys']),'finite menu key schedule exhausted')
            key=self.c['keys'][self.input_index];self.input_index+=1
            self.patch(self.r['ds'],0x14,1 if key is None else 0,'buttons-'+str(self.input_index))
            self.patch(self.r['ds'],0xF79,0 if key is None else 0x94,'key-state-'+str(self.input_index),word=False)
            if key is not None:self.patch(self.r['ds'],0x202F,key,'key-char-'+str(self.input_index),word=False)
        return v
    def out(self,port,value,flags,mask=base.FLAGS):
        check(port in (0x3C0,0x3C8,0x3C9),'unexpected main-menu byte output');self.emit('out8',port,value,flags,mask)
    def out_word(self,port,value,flags,mask=base.FLAGS):
        self.emit('out',port,value,flags,mask)
        if port in (0x3C4,0x3CE):self.device.out(port,value,flags)
        else:check(port==0x3D4,'unexpected main-menu word output')
        phase=self.c.get('patch')
        if phase in self.providers:return
        if phase=='display-return' and port==0x3D4:self.patch(self.r['ss'],(self.r['sp']-2)&65535,0xD234,phase)
        if phase=='scroll-far' and port in (0x3C4,0x3CE):self.patch(self.r['ss'],(self.r['sp']-6)&65535,0xD234,phase)

class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device):
        self.child_status=0;frames=[];failed=[];self.calls=[]
        def before(m,i):
            if i.address in EXITS:m.stop(0);return True
            if i.mnemonic in ('call','lcall'):
                own=i.address in OWN;root=i.operands[0].imm if own else frames[-1]['root'] if frames else None
                frames.append(dict(owner=i.address,root=root,resume=i.address+i.size,far=i.mnemonic=='lcall'))
                if own:self.calls.append((i.address,root))
            return False
        def expected(m,off):
            check(bool(frames),'undeclared main-menu return');frame=frames.pop();failed[:]=[frame]
            return {(c['load'],frame['resume'])} if frame['far'] else {frame['resume']}
        def changed(m,off):
            frame=failed[-1]
            if frame['owner'] in OWN:self.child_status=0;return 2
            if off in animation.RENDER and animation.RENDER[off].mnemonic!='retf':self.child_status=1
            elif frame['root'] in (0x4F96,0x4FF8,0x4EEF,0x4F2B):self.child_status=2 if INS[off].mnemonic=='retf' else 3
            else:self.child_status=2
            return 1
        super().__init__(c,memory,r,device,False,instructions=INS,access=Access(c,memory,r,device),outer_returns=set(),max_steps=MAX_STEPS,
            before=before,child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            far_returns={p:expected for p,i in INS.items() if i.mnemonic=='retf'},changed_return_status=changed)
    def run(self):
        out=super().run();out['child_status']=self.child_status or self.service_status;out['service_status']=0;out['calls']=self.calls;return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'main-menu-{mutation}.dll',mutation,'main_menu')))
        self.run_menu=self.lib.lmn_run_main_menu;self.run_menu.restype=Result
        self.run_menu.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.c_uint16,ct.c_int,ct.POINTER(base.Ports),ct.POINTER(base.Bus)]
    def run(self,c,memory,r,device,*,copy_state=True):
        if copy_state:memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(c,memory,r,device)
        cb=base.NativeCallbacks(access,missing_in=c.get('missing_in',False));mem=(ct.c_uint8*base.SIZE).from_buffer(memory)
        out=self.run_menu(mem,ct.byref(base.Regs(**r)),(c['load']+0x9A9)&65535,c['entry'],ct.byref(cb.ports),ct.byref(cb.bus))
        return dict(regs={n:getattr(out.registers,n) for n in base.REG_NAMES},status=out.status,child_status=out.child_status,service_status=0,
                    memory=memory,device=access.device,events=access.events,providers=access.providers,cursor=access.cursor)

def independent(c,r,ref):
    check(ref['status']==c.get('expected',0) and ref['child_status']==c.get('child_status',0),c['name']+': unexpected stop')
    if ref['status']:return
    first=c['keys'][0];dest={0x80:0x454C,0x81:0x4967,0x83:0x4A01,0x1B:0x4D0}.get(first,0x454C)
    check(ref['regs']['ip']==dest,'menu destination differs')
    if c['entry']==3 and first==0x82 and c.get('sound_cache',c['toggle'])!=2:
        index=(c['option']+1)&255
        if index==(3 if c['driver']==255 else 2):index=0
        check(ref['memory'][physical(r['ds'],0x1F71)]==index,'sound option exact wrap differs')
        check(ref['memory'][physical(r['ds'],0x1F70)]==(c['toggle']^255),'sound toggle full byte differs')
        value=0x55 if c.get('patch')=='table' else base.IMAGE[0x44E9+index]
        check(ref['memory'][physical(r['ds'],0x25A7)]==value,'live CS sound option value differs')
    if c['entry']==3 and first==0x82 and c.get('sound_cache',c['toggle'])==2:
        check(ref['memory'][physical(r['ds'],0x1F70)]==c['toggle'] and ref['memory'][physical(r['ds'],0x1F71)]==c['option'],'blocked sound action changed state')
    if c['entry']==3 and first in (0x8A,0x60,0x8B,0x2D):
        group=7 if c.get('patch')=='group' else c['group']
        if c.get('group_cache',c['group'])!=4:
            changed=False
            if first in (0x8A,0x60) and group!=3:group=(group+1)&255;changed=True
            if first in (0x8B,0x2D) and group!=0:group=(group-1)&255;changed=True
            if changed:
                check(ref['memory'][physical(r['ds'],0x1F6B)]==((30*group)&255),'group-to-resource selection differs')
        check(ref['memory'][physical(r['ds'],0x1F6E)]==group,'group byte guard/wrap differs')
    if c['entry'] in (1,2):check(ref['calls'][:6]==[(0x445B,0x1550),(0x445E,0x7D0D),(0x4461,0x4F96),(0x4464,0x4EA2),(0x4467,0x4E37),(0x446A,0x4C20)],'menu child order differs')
    if c['entry']==0:
        check([p for p,_ in ref['calls'][:15]]==[0x4413,0x4425,0x4428,0x442B,0x442E,0x4431,0x4434,0x4437,0x443E,0x4441,0x4444,0x4447,0x444A,0x444D,0x4450],'menu refresh child order differs')
        check((get16(ref['memory'],r['ds'],0x1F76),get16(ref['memory'],r['ds'],0x1F78),get16(ref['memory'],r['ds'],0x1F7A))==(0x6D60,0,0),'refresh/display page ownership differs')

def compare(native,c):
    memory,r,device=setup(c)
    case=c|dict(missing_port_status=1,missing_service_status=1)
    ref=Machine(case,bytearray(memory),dict(r),copy.deepcopy(device)).run();independent(c,r,ref)
    if native:base.compare_states(c['name'],native.run(c,memory,r,device),ref)
    return ref

def hashes():
    paths=set(keyboard.hashes())|set(scroll.hashes())|set(animation.hashes())|set(cache.hashes())|FIXTURES
    paths|={'c/main_menu.c','c/main_menu.h','tests/main_menu.py','src/input_menu_and_retry.asm','tools/cbuild.py','tools/difftest.py'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

def input_handoff(native,record):
    c=next(c for c in cases() if c['name']=='key-83')|dict(pinned=True)
    memory,r,device=setup(c);actual_memory,actual_device=bytearray(memory),copy.deepcopy(device);actual_regs=dict(r)
    ref=Machine(c,memory,dict(r),device).run();independent(c,r,ref)
    actual=native.run(c,actual_memory,actual_regs,actual_device,copy_state=False);base.compare_states('handoff-to-input',actual,ref)
    record('handoff-to-input',ref)
    memory,r,device=ref['memory'],ref['regs'],ref['device'];actual_memory,actual_regs,actual_device=actual['memory'],actual['regs'],actual['device']
    for dev in (device,actual_device):dev.trace.clear()
    del ref,actual
    gc.collect()
    # This is the actual JMP4A01, not a constructed CALL/RET. Reuse the existing
    # shared-verifier input-screen fixture provider and the compiled C core.
    screen=dict(c,name='handoff-input-screen',entry='screen',selection_chars=(0x33,),crtc=0x3D4)
    ref=keyboard.Machine(screen,memory,dict(r),device,False).run()
    fn=native.lib.lmn_show_input_selection;fn.restype=keyboard.Result
    fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(base.Ports),ct.POINTER(base.Bus)]
    access=keyboard.Access(screen,actual_memory,actual_regs,actual_device);cb=base.NativeCallbacks(access)
    result=fn((ct.c_uint8*base.SIZE).from_buffer(actual_memory),ct.byref(base.Regs(**actual_regs)),ct.byref(cb.ports),ct.byref(cb.bus))
    actual=dict(regs={n:getattr(result.registers,n) for n in base.REG_NAMES},status=result.status,child_status=result.child_status,service_status=result.service_status,
                memory=actual_memory,device=access.device,events=access.events,providers=access.providers,cursor=access.cursor,services=access.service_events)
    base.compare_states('handoff-input-screen',actual,ref)
    check(ref['status']==0 and ref['regs']['ip']==0x4401 and ref['memory'][physical(r['ds'],0x25A6)]==2,'input selection did not reach refresh')
    record('handoff-input-screen',ref)
    memory,r,device=ref['memory'],ref['regs'],ref['device'];actual_memory,actual_regs,actual_device=actual['memory'],actual['regs'],actual['device']
    for dev in (device,actual_device):dev.trace.clear()
    del ref,actual,access,cb,result
    gc.collect()
    c=dict(c,name='handoff-menu-refresh',entry=0,keys=(None,))
    ref=Machine(c,memory,dict(r),device).run();independent(c,r,ref)
    actual=native.run(c,actual_memory,actual_regs,actual_device,copy_state=False);base.compare_states('handoff-menu-refresh',actual,ref)
    check(ref['regs']['ip']==0x454C and ref['memory'][physical(r['ds'],0x25A6)]==2,'configured mode did not reach level transition')
    record('handoff-menu-refresh',ref);gc.collect()
    print('CHECKED menu/input/refresh handoff',flush=True)

def worker(directory,snapshot):
    before=hashes();check(before==json.loads(Path(snapshot).read_text()),'main menu snapshot changed');native=Native(directory)
    sites=set();edges=set();rows=[]
    def record(name,ref):
        sites.update(ref['sites']);edges.update(ref['edges'])
        rows.append(dict(case=name,steps=ref['steps'],events=len(ref['events']),far_return_events=ref['far_return_events']))
    for c in cases():
        ref=compare(native,c);record(c['name'],ref)
        gc.collect();print('CHECKED '+c['name'],flush=True)
    input_handoff(native,record)
    check(set(OWN)<=sites,'main menu sites missing: '+str(sorted(set(OWN)-sites)))
    check(EDGES<=edges,'main menu outcomes missing: '+str(sorted(EDGES-edges)))
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in ((1,'sound-blocked'),(2,'sound-driver-fe'),(3,'sound-unexpected-index'),(4,'key-82'),(5,'group-8a-unexpected'),(6,'key-8a'),(7,'key-80'),(8,'wait-return'),(9,'key-82')):
        try:compare(Native(directory,mutation),lookup[name])
        except base.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise base.OracleFailure(f'main menu mutant{mutation} survived')
        gc.collect()
    check(before==hashes(),'main menu inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(base.IMAGE),own_known_bytes=sum(i.size for i in OWN.values()),known_connected_bytes=sum(i.size for p,i in INS.items() if p not in BOUNDARY),
        entry_code_ranges=[list(r) for r in RANGES],case_count=len(cases())+1,comparison_count=len(rows),handoff_count=1,
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),declared_far_return_events=sum(r['far_return_events'] for r in rows),
        mutation_count=len(mutants),mutations=mutants,input_hashes=before,rows=rows,
        limits=dict(timeout_seconds=SECONDS,outer_timeout_seconds=540,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,events=MAX_EVENTS),
        scope='4401 refresh,4453 release wait,445B active frame,4478 keyboard through actual JMP exits. Connected native children on canonical RAM;43F2 startup,destination bodies,scheduling and inherited reference limits remain open.'))
    print(f'PASS main menu: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(EDGES)} outcomes,{len(mutants)} mutants',flush=True)
def main():
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]:raise SystemExit('usage: main_menu.py')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='main-menu-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

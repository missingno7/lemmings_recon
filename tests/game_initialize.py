"""Full session initializer, exact instructions and declared two-edge IRQ fixture."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
import game_initialize_prefix as prefix
import game_prepare as prepare
import status_display_full as display
from bounded_process import run_bounded,temporary_build_directory
from common import BUILD,sha,write_json

OWN_RANGES=((0x03E7,0x04D0),)
OWN={i.address:i for i in v.MD.disasm(v.IMAGE[0x03E7:0x04D0],0x03E7)}
INS=prefix.INS|prepare.INS|display.FULL_INS|OWN
for a,b in ((0x410F,0x414F),(0x30A6,0x3150),(0x1644,0x1696),
            (0x3944,0x394F),(0x7BB8,0x7C67)):
    INS.update({i.address:i for i in v.MD.disasm(v.IMAGE[a:b],a)})
EDGES=v.direct_jump_edges(OWN)
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=420,384,2_000_000,1_000_000
REPORT=BUILD/'game-initialize-differential.json'
BINDINGS={0x10:(0xB000,0x100),0x21:(0x7100,0x210),0x33:(0x7200,0x330)}

def cases():
    base=next(c for c in prefix.cases() if c['name']=='level-normal-return')
    rows=(
        dict(name='carry-neg-nonzero',mouse=0,first=3,second=1,words=(0xFFFE,0xFFFF)),
        dict(name='no-carry-neg-zero',mouse=255,first=1,second=32769,words=(0xFFFE,0)),
        dict(name='cx-zero-dx-decrement',mouse=1,first=2,second=65536,words=(0,2)),
        dict(name='cx-wrap-after-dx',mouse=254,first=2,second=65537,words=(0xFFFE,1)),
        dict(name='no-poll',mouse=255,no_poll=True,expected=4),
        dict(name='poll-stop-first',mouse=255,poll_stop=0x04AA,expected=5,service_status=0x4321),
        dict(name='poll-stop-second',mouse=255,poll_stop=0x04BA,expected=5,service_status=0x4321),
        dict(name='timer-child-stop',mouse=255,dos_stop=True,expected=1,child_status=2,service_status=0x7788),
        dict(name='visibility-return-changed',mouse=255,tail_return=True,expected=2),
        dict(name='timer-return-changed',mouse=0,dos_return=True,expected=2),
        dict(name='mouse-unbound',mouse=0,no_mouse=True,expected=1,child_status=1),
    )
    return [base|dict(expected=3,child_status=0,service_status=0,first=1,second=1)|c for c in rows]

def setup(c):
    memory,r,device=prefix.setup(c)
    # Earlier4551's per-level clear is a declared precondition, independent of
    # the terrain-only resource fixture;03E7 does not clear entity storage.
    start=v.physical(r['ds'],0);memory[start:start+0x0FCB]=bytes(0x0FCB)
    v.put8(memory,r['ds'],0x1F73,c['mouse'])
    for number,(cs,ip) in BINDINGS.items():
        v.put16(memory,0,number*4,ip);v.put16(memory,0,number*4+2,cs)
    v.put16(memory,r['ss'],r['sp'],0xD00D)
    return memory,r,device

class Access(prefix.Access):
    def __init__(self,*args):
        super().__init__(*args);self.tail=False;self.install=False
        self.install_reads=0;self.polls={0x04AA:0,0x04BA:0};self.poll_events=[]
    def access(self,kind,address,flags,mask=v.FLAGS,value=None):
        got=super().access(kind,address,flags,mask,value)
        if kind=='write' and address==v.physical(self.r['ss'],self.r['sp']-2) and value==0x83:
            self.tail=True
        if (self.tail and self.c.get('tail_return') and kind=='write' and value==4 and
                address==v.physical(self.r['ss'],self.r['sp']-1) and
                'tail-return' not in self.providers):
            self.patch(self.r['ss'],self.r['sp']-2,0xD234,'tail-return')
        return got
    def inp(self,port,flags,mask=v.FLAGS):
        if self.install:
            samples=(0,8,8,0)
            v.check(self.install_reads<len(samples),'installer status budget exhausted')
            value=samples[self.install_reads];self.install_reads+=1
            self.cursor+=1;self.emit('in',port,value,flags,mask);return value
        if self.tail:
            v.check(port in (0x3DA,0x3C5),'undeclared tail palette input')
            value=0x93 if port==0x3C5 else 0
            self.cursor+=1;self.emit('in',port,value,flags,mask);return value
        return super().inp(port,flags,mask)
    def out(self,port,value,flags,mask=v.FLAGS):
        if self.tail:
            v.check(port in (0x3C0,0x3C4,0x3C5,0x3C8,0x3C9,0x43,0x40),'undeclared tail output')
            self.emit('out8',port,value,flags,mask);return
        return super().out(port,value,flags,mask)

def provider(number):
    if number==0x10:return prefix.bios_provider
    def execute(access,r):
        entry=dict(r)
        if number==0x33:
            v.check((r['ax'],r['cx'],r['dx'])==(4,150,100),'mouse positioning inputs differ')
            # A visible predecessor state handoff into410F; service transport
            # still owns the actual IRET frame, including IF restoration.
            r.update(bx=0xA123,si=0xB234,di=0xC345,bp=0xD456)
        else:
            access.install=True
            v.check(r['ax'] in (0x2508,0x2560),'undeclared DOS vector request')
            access.word_write(0,(r['ax']&255)*4,r['dx'],r['flags'])
            access.word_write(0,(r['ax']&255)*4+2,r['ds'],r['flags'])
            if access.c.get('dos_return'):
                access.patch(r['ss'],(r['sp']+8)&65535,0xD234,'timer-parent-return')
        status=0x7788 if number==0x21 and access.c.get('dos_stop') else 0
        access.service_events.append(dict(number=number,entry=entry,returned=dict(r),status=status))
        return status
    return execute

def poll(access,r,site):
    v.check(site in access.polls and r['ip']==site,'undeclared poll')
    access.polls[site]+=1;n=access.polls[site]
    edge=access.c['first' if site==0x04AA else 'second']
    v.check(n<=edge,'declared poll delivery budget exhausted')
    v.check(r['flags']&0x200,'IRQ delivery requires IF')
    status=0x4321 if access.c.get('poll_stop')==site else 0
    if n==edge and not status:
        # Minimal declared IRQ projection: original189E's foreground-visible
        # store. No handler execution or general scheduler coverage is claimed.
        access.patch(r['ds'],0x1FCF,255,f'irq-{site:04x}',word=False)
    elif n==1:
        access.patch(r['ds'],0x1FCF,1,f'non-ff-{site:04x}',word=False)
    if n in (1,edge) or status:
        access.poll_events.append(dict(site=site,iteration=n,registers=dict(r),status=status))
    return status

def original(c,memory,r,device):
    access=Access(c,memory,r,device);frames=[];state=dict(child_status=0,service_status=0)
    def before(m,i):
        if i.address in (0x04AA,0x04BA):
            if c.get('no_poll'):m.stop(4);return True
            status=poll(access,m.state(),i.address)
            if status:state['service_status']=status;m.stop(5);return True
        if i.mnemonic in ('call','lcall'):
            frames.append((i.address+i.size,i.mnemonic=='lcall'))
        return False
    def expected(m,off):
        v.check(bool(frames),'undeclared child return');resume,far=frames.pop()
        v.check(not far,'near return from far frame');return {resume}
    def expected_far(m,off):
        v.check(bool(frames),'undeclared far return');resume,far=frames.pop()
        v.check(far,'far return from near frame');return {(c['load'],resume)}
    def interrupt(m,number):
        v.check(number in BINDINGS,'undeclared interrupt')
        fn=None if number==0x33 and c.get('no_mouse') else provider(number)
        m.software_interrupt(number,m.state()['ip'],BINDINGS[number],fn)
        if m.stopped:
            state['child_status']=m.status;state['service_status']=m.service_status
            m.status=2 if m.status==3 else 1
    m=v.OriginalMachine(c,memory,r,device,False,instructions=INS,access=access,
        outer_returns={0x04CF},child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
        far_returns={p:expected_far for p,i in INS.items() if i.mnemonic=='retf'},
        before=before,interrupt=interrupt,changed_return_status=2,max_steps=MAX_STEPS)
    out=m.run();out.update(state)
    if out['status']==0:out['status']=3
    out.update(services=access.service_events,hardware=access.outputs,polls=access.polls,poll_events=access.poll_events)
    return out

class Native(prefix.Native):
    def run(self,c,memory,r,device):
        memory,device=bytearray(memory),copy.deepcopy(device);access=Access(c,memory,r,device)
        cb=v.NativeCallbacks(access)
        handlers={n:cb.interrupt(provider(n)) for n in BINDINGS}
        bindings={n:v.InterruptService(None,handlers[n],*BINDINGS[n]) for n in BINDINGS}
        video=prefix.VideoServices(ct.pointer(bindings[0x10]),ct.pointer(cb.ports),ct.pointer(cb.bus))
        level=prefix.LevelServices(None,None,ct.pointer(cb.bus),ct.pointer(cb.ports))
        callback=cb.foreground(poll);foreground=v.ForegroundPoll(None,callback)
        services=prefix.GameServices(ct.pointer(video),ct.pointer(cb.ports),ct.pointer(cb.bus),ct.pointer(level),
            c['game_data_segment'],0,None if c.get('no_mouse') else ct.pointer(bindings[0x33]),
            ct.pointer(bindings[0x21]),None if c.get('no_poll') else ct.cast(ct.pointer(foreground),ct.c_void_p))
        regs=v.Regs(**r)
        out=self.fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(regs),ct.byref(services))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,
            child_status=out.child_status,service_status=out.service_status,memory=memory,device=device,
            events=access.events,providers=access.providers,cursor=access.cursor,services=access.service_events,
            hardware=access.outputs,polls=access.polls,poll_events=access.poll_events)

def compare(native,c):
    memory,r,device=setup(c)
    ref=original(c,bytearray(memory),dict(r),copy.deepcopy(device))
    v.check((ref['status'],ref['child_status'],ref['service_status'])==
        (c['expected'],c['child_status'],c['service_status']),f"{c['name']}: unexpected stop {ref['status'],ref['child_status'],ref['service_status']}")
    actual=native.run(c,memory,r,device);v.compare_states(c['name'],actual,ref)
    for name in ('hardware','polls','poll_events'):v.require(actual[name]==ref[name],c['name']+': '+name+' differs')
    if ref['status']==3:
        v.check(ref['regs']['ip']==0xD00D and ref['regs']['sp']==r['sp']+2,'actual outer RET differs')
        words=tuple(v.get16(ref['memory'],ref['regs']['ds'],off) for off in (0x1FFE,0x2000))
        v.check(words==c['words'],f"{c['name']}: independent wait words {words}")
        v.check(ref['polls']=={0x04AA:c['first'],0x04BA:c['second']},'IRQ schedule differs')
        v.check(bool(ref['regs']['flags']&0x40)==(words[1]==0),'NEG ZF differs')
        v.check(bool(ref['regs']['flags']&1)==(words[1]!=0),'NEG CF differs')
    return ref

MUTANTS=((9,'cx-zero-dx-decrement'),(10,'timer-child-stop'),(11,'visibility-return-changed'),
         (12,'cx-zero-dx-decrement'),(13,'carry-neg-nonzero'),(14,'carry-neg-nonzero'))

def hashes():
    paths=prefix.hashes()
    paths.update({name:value for name,value in display.input_hashes().items() if name.startswith('tests/')})
    for name in ('tests/game_initialize.py','tests/game_prepare.py','tests/status_display_full.py'):
        paths[name]=sha((ROOT/name).read_bytes())
    return paths

def worker(directory,snapshot):
    started=time.monotonic();before=hashes()
    v.check(before==json.loads(Path(snapshot).read_text()),'initializer inputs changed')
    native=Native(directory);rows=[];sites=set();edges=set()
    for c in cases():
        ref=compare(native,c);sites.update(ref['sites']);edges.update(ref['edges'])
        rows.append(dict(case=c['name'],steps=ref['steps'],events=len(ref['events']),status=ref['status'],
            registers=ref['regs'],polls=ref['polls'],poll_events=ref['poll_events']))
        print('PASS '+c['name'],flush=True);del ref;gc.collect()
    v.check(set(OWN)<=sites,'unexecuted own sites '+str(sorted(set(OWN)-sites)))
    v.check(EDGES<=edges,'unexecuted own outcomes '+str(sorted(EDGES-edges)))
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in MUTANTS:
        try:compare(Native(directory,mutation),lookup[name])
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise v.OracleFailure('surviving initializer mutant '+str(mutation))
    after=hashes()
    v.check(before==after,'initializer inputs changed during run: '+
        str([name for name in before if before[name]!=after.get(name)]))
    write_json(REPORT,dict(image='main',image_sha256=sha(v.IMAGE),input_hashes=before,
        native_code_ranges=[list(r) for r in OWN_RANGES],own_known_bytes=sum(i.size for i in OWN.values()),
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(EDGES&edges),case_count=len(rows),comparison_count=len(rows),
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),
        mutation_count=len(mutants),mutations=mutants,rows=rows,runtime_seconds=time.monotonic()-started,
        irq_model='Declared minimal189E projection: store exactFF to liveDS:1FCF immediately before04AA/04BA reads, IF required; no whole-handler or general-preemption claim.',
        limits=dict(worker_seconds=SECONDS,windows_process_mib=MEMORY_MIB,windows_tree_mib=MEMORY_MIB+256,
                    instructions_each=MAX_STEPS,events_each=MAX_EVENTS),
        domain='Full03E7..04CF on normal terrain-only level fixture, earlier4551 clear precondition, both mouse paths, all11 ordered tail children and actual outerRET; explicit child/service/changed-return and absent/stopping poll seams. Other child domains remain scoped.'))
    print(f'PASS full initializer: {len(rows)} cases, {len(OWN)} own sites, {len(mutants)} mutants',flush=True)

def main():
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='game-initialize-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot)],cwd=ROOT,
            timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)

if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3])
    else:main()

"""Bounded wrapper parity; media outcomes are exact, declared original fixtures."""
import copy
import ctypes as ct
import gc
import re
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
import protection_fixture as media
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json

RANGES=((0x62B,0x63E),(0xE66,0xEA8),(0xEA9,0xEC1),(0xEC2,0xF08))
OWN={p:i for a,b in RANGES for p,i in media.decoded(a,b).items()}
INS=OWN|media.decoded(0xFA0,0xFB2)|media.decoded(0xFF8,0x1007)|media.decoded(0x1582,0x1592)|media.decoded(0x16A9,0x16D4)
INS[0x63E]=next(v.MD.disasm(v.IMAGE[0x63E:0x646],0x63E))
ENTRY=(0x62B,0xE66,0xEC2,0xEDF)
BINDINGS={0x10:(0xB000,0x100),0x21:(0xB000,0x200),0x1A:(0xB000,0x600),0x33:(0xB000,0x300)}
PROBE=ct.CFUNCTYPE(ct.c_uint16,ct.c_void_p,v.MEM,ct.POINTER(v.Regs),ct.c_void_p)
class Services(ct.Structure):
    _fields_=[(n,ct.POINTER(v.InterruptService)) for n in ('dos','bios','clock','mouse')]+[
        ('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus)),('context',ct.c_void_p),('probe',PROBE)]
class Result(ct.Structure):
    _fields_=[('registers',v.Regs)]+[(n,ct.c_uint16) for n in ('status','child_status','service_status')]
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=1200,768,10000,100000

def cases():
    rows=[]
    def add(name,**kw):rows.append(dict(name=name,**kw))
    for count in (*range(11),0xFE,0xFF):add(f'counter-{count:02x}',counter=count)
    for fat in (0,0xFD,0xFF):
        for outcome in (0,1):add(f'media-{fat:02x}-{outcome}',fat=fat,outcome=outcome)
    add('dma-pass',load=0x1F50,fat=0xFD)
    add('dma-fail',load=0x1F50,fat=0xFD,outcome=1)
    add('counter-fail',counter=9,outcome=1)
    for outcome in (0,1):add(f'open-fail-{outcome}',open_error=True,outcome=outcome)
    add('read-error-stale',read_error=True,stale=7)
    add('read-empty-stale',short_read=True,stale=8)
    add('create-error',entry=2,create_error=True)
    add('writer-errors',entry=2,write_error=True,close_error=True)
    add('counter-create-error',counter=0,create_error=True)
    add('counter-read-error-probe',read_error=True,stale=0xFF)
    add('critical-error',fat=0xFD,critical=True)
    add('failure-mouse-disabled',entry=3,disabled=True)
    add('failure-mouse-present',entry=3)
    add('failure-private-vector-09',entry=3,private=9)
    add('failure-clock-stop',entry=3,stop_service=(0x1A,1))
    add('probe-unbound',fat=0xFD,unbound=True)
    add('probe-unsupported',fat=0xFD,outcome=2)
    return [dict(load=0x1010,seed=0xB007,entry=0,flags=0x202,counter=0,stale=0,
        fat=0xF8,outcome=0,open_error=False,read_error=False,short_read=False,create_error=False,
        write_error=False,close_error=False,disabled=False,critical=False,private=12,adapter=True)|c for c in rows]

def setup(c):
    m,d=v.initial_memory(c);ds=c['load']+0x9A9
    r=v.default_regs(c['load'],c['seed'],ds=ds,ss=0x7000,sp=0x9000,flags=c['flags']);r['ip']=ENTRY[c['entry']]
    for n,(seg,off) in BINDINGS.items():v.put16(m,0,n*4,off);v.put16(m,0,n*4+2,seg)
    for off,value in ((0x1FBE,0x700),(0x1FC0,0xB000),(0x1FBA,0x709),(0x1FBC,0xB000),(0x1FC2,0x70C),(0x1FC4,0xB000),(0x259C,0x1234),(0x259E,0x5678)):
        v.put16(m,ds,off,value)
    for off,value in ((0x1FC6,c['private']),(0x1FDE,c['fat']),(0x1FDF,0),(0x1F73,255 if c['disabled'] else 0),(0x252A,c['stale'])):v.put8(m,ds,off,value)
    v.put16(m,r['ss'],r['sp'],0xF000)
    v.put16(m,0,0x78,0x100);v.put16(m,0,0x7A,0x600);v.put8(m,0,0x46C,0)
    return m,r,d

class Access(v.BusAccess):
    def __init__(self,c,m,r,d):
        super().__init__(c,m,r,d,max_events=MAX_EVENTS,packed_events=True)
        self.fixtures=[];self.fixture_calls=[];self.writes=[]
    def out(self,port,value,flags,mask=v.FLAGS):self.emit('out8',port,value,flags,mask)

def provider(number):
    def execute(a,r):
        c=a.c;entry=dict(r);fn=r['ax']>>8;failed=False;payload=None
        v.check(len(a.service_events)<100,'protection service budget exhausted')
        if c.get('stop_service')==(number,fn):return 77
        if number==0x21:
            if fn==0x3D:r['ax']=2 if c['open_error'] else 7;failed=c['open_error']
            elif fn==0x3F:
                failed=c['read_error'];r['ax']=5 if failed else 0 if c['short_read'] else 1
                if not failed and not c['short_read']:a.patch(r['ds'],r['dx'],c['counter'],'counter-file',word=False)
            elif fn==0x3C:r['ax']=5 if c['create_error'] else 8;failed=c['create_error']
            elif fn==0x40:
                payload=bytes(a.access('read',v.physical(r['ds'],r['dx']+n),r['flags']) for n in range(r['cx']))
                a.writes.append(dict(handle=r['bx'],payload=payload.hex()))
                r['ax']=5 if c['write_error'] else r['cx'];failed=c['write_error']
            elif fn==0x3E:r['ax']=6 if c['close_error'] else 0;failed=c['close_error']
            elif fn==0x25:
                n=r['ax']&255;a.patch(0,n*4,r['dx'],'dos-vector');a.patch(0,n*4+2,r['ds'],'dos-vector')
            else:v.check(fn in (9,0x4C),'unexpected protection DOS')
            if fn in (0x3D,0x3F,0x3C,0x40,0x3E):
                f=v.get16(a.memory,r['ss'],r['sp']+4);a.word_write(r['ss'],r['sp']+4,(f&~1)|int(failed),r['flags'])
        elif number==0x1A:v.check(fn==1,'unexpected protection clock')
        elif number==0x10:v.check(fn in (0,5),'unexpected protection BIOS')
        elif number==0x33:v.check(r['ax']==12 and r['cx']==0,'unexpected protection mouse')
        a.service_events.append(dict(number=number,entry=entry,returned=dict(r),payload=payload.hex() if payload is not None else None))
        return 0
    return execute

def outcome(a,r,*,original):
    v.check(len(a.fixture_calls)<2,'media outcome budget exhausted')
    if a.c['outcome']==2:a.fixture_calls.append('UNSUPPORTED');return 2
    if original:
        fixture=media.Fixture(a.memory,r,a.c['outcome']);a.fixtures.append(fixture)
    else:
        # A control-flow mutant may request an otherwise skipped probe. Supply
        # the same declared original-built provider domain, so a completed
        # mismatch (never a callback exception) earns mutation credit.
        if len(a.fixtures)==len(a.fixture_calls):a.fixtures.append(media.Fixture(a.memory,r,a.c['outcome']))
        fixture=a.fixtures[len(a.fixture_calls)]
    result=fixture.apply(a,r,clear=original)
    if a.c.get('critical'):a.patch(r['ds'],0x1FDF,255,'critical-error',word=False)
    a.fixture_calls.append(dict(outcome=result,entry=fixture.entry,returned=dict(r)))
    return result

class Machine(v.OriginalMachine):
    def __init__(self,c,m,r,d):
        a=Access(c,m,r,d);frames=[]
        def before(machine,i):
            if i.address==0x63E:
                q=machine.state()
                if c.get('unbound'):machine.stop(3);return True
                result=outcome(a,q,original=True)
                if result==2:machine.set_state(q);machine.service_status=2;machine.stop(3);return True
                q['ip']=a.word_read(q['ss'],q['sp'],q['flags']);q['sp']=(q['sp']+2)&65535
                frames.pop();machine.set_state(q);machine.previous=None;machine.mask=v.FLAGS;return True
            if i.mnemonic=='call':frames.append(i.address+i.size)
            return False
        def expected(machine,off):return {frames.pop()}
        def interrupt(machine,n):
            q=machine.state();fn=q['ax']>>8
            machine.software_interrupt(n,q['ip'],BINDINGS[n],provider(n))
            if machine.stopped:machine.child_status=machine.status;machine.status=1
            elif n==0x21 and fn==0x4C:machine.stop(5)
        super().__init__(c,m,r,d,not c['adapter'],instructions=INS,access=a,outer_returns=lambda m,off:not frames,
            child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},before=before,interrupt=interrupt,
            changed_return_status=2,max_steps=MAX_STEPS)
        self.child_status=0
    def run(self):
        out=super().run();out.update(child_status=self.child_status,service_status=self.service_status,
            services=self.access.service_events,fixtures=self.access.fixture_calls,writes=self.access.writes)
        return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'protection-{mutation}.dll',mutation,'protection')))
        self.functions={}
        for name in ('core','adapter'):
            fn=getattr(self.lib,'lmn_protection_'+name);fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_int,ct.POINTER(Services)];fn.restype=Result;self.functions[name]=fn
    def run(self,c,m,r,d,fixtures):
        m,d=bytearray(m),copy.deepcopy(d);a=Access(c,m,r,d);a.fixtures=fixtures
        cb=v.NativeCallbacks(a);callbacks={n:cb.interrupt(provider(n)) for n in BINDINGS}
        bindings={n:v.InterruptService(None,callbacks[n],*BINDINGS[n]) for n in BINDINGS}
        probe=PROBE(cb.interrupt(lambda a,r:outcome(a,r,original=False)))
        services=Services(*(ct.pointer(bindings[n]) for n in (0x21,0x10,0x1A,0x33)),ct.pointer(cb.ports),ct.pointer(cb.bus),None,PROBE() if c.get('unbound') else probe)
        regs=v.Regs(**r);out=self.functions['adapter' if c['adapter'] else 'core']((ct.c_uint8*v.SIZE).from_buffer(m),ct.byref(regs),c['entry'],ct.byref(services))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,child_status=out.child_status,
            service_status=out.service_status,memory=m,device=d,events=a.events,providers=a.providers,cursor=a.cursor,
            services=a.service_events,fixtures=a.fixture_calls,writes=a.writes)

def compare(native,c):
    m,r,d=setup(c);machine=Machine(c,bytearray(m),dict(r),copy.deepcopy(d));ref=machine.run()
    actual=native.run(c,m,r,d,machine.access.fixtures)
    if actual['memory']!=ref['memory']:
        diffs=[(p,actual['memory'][p],ref['memory'][p]) for p in range(v.SIZE) if actual['memory'][p]!=ref['memory'][p]]
        raise v.Mismatch(c['name']+': RAM differs '+str(diffs[:15]))
    v.compare_states(c['name'],actual,ref)
    for n in ('fixtures','writes'):v.require(actual[n]==ref[n],c['name']+': '+n+' differs')
    count=ref['memory'][v.physical(r['ds'],0x252A)]
    if c['entry']==0 and c['fat']==0xF8 and not c['open_error'] and not c['read_error'] and not c['short_read']:
        expected=(c['counter']+1)&255;expected=expected if expected<10 else 0
        if expected==0 and c['outcome']==1:expected=9
        v.check(count==expected,'independent counter expectation differs')
    return ref,[f.evidence() for f in machine.access.fixtures]

def hashes():
    paths={Path(__file__),ROOT/'tests/protection.py',ROOT/'tests/protection_fixture.py',ROOT/'tests/verification.py',
        ROOT/'tests/minimap_vga.py',ROOT/'tools/protection.py',ROOT/'tools/unpack.py',ROOT/'tools/cbuild.py',
        ROOT/'tools/bounded_process.py',ROOT/'tools/difftest.py',ROOT/'assets/vgalemmi.exe',ROOT/'metadata/toolchain-lock.json',
        ROOT/'metadata/symbols.json',ROOT/'src/entry_services.asm',ROOT/'c/lemmings_sym.h',ROOT/'tools/common.py'}
    for p in source_files('protection'):paths|={p,p.with_suffix('.h')}
    pending=list(source_files('protection'));seen=set()
    while pending:
        p=pending.pop()
        if p in seen:continue
        seen.add(p)
        for name in re.findall(r'^#include "([^"]+)"',p.read_text(),re.M):
            header=ROOT/'c'/name;paths.add(header);pending.append(header)
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(paths)}

def worker(directory,selected):
    start=time.perf_counter();before=hashes();native=Native(directory);rows=[];sites=set();edges=set();evidence=[]
    for c in cases():
        if selected and c['name'] not in selected:continue
        ref,probes=compare(native,c);sites|=ref['sites'];edges|=ref['edges'];evidence+=probes
        rows.append(dict(case=c['name'],steps=ref['steps'],events=len(ref['events']),status=ref['status']))
        print('CHECKED '+c['name'],flush=True);del ref;gc.collect()
    if selected:return
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in ((1,'counter-08'),(2,'create-error'),(3,'media-fd-0'),(4,'failure-mouse-present')):
        try:compare(Native(directory,mutation),lookup[name])
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise v.OracleFailure('surviving protection mutant')
    v.check(before==hashes(),'protection inputs changed during campaign')
    v.check(set(OWN)<=sites,'missing own protection sites: '+str(sorted(set(OWN)-sites)))
    v.check(v.direct_jump_edges(OWN)<=edges,'missing own protection outcomes')
    write_json(BUILD/'protection-differential.json',dict(accepted=True,case_count=len(rows),comparison_count=len(rows),
        native_code_ranges=RANGES,executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),
        own_executed_sites=sorted(set(OWN)&sites),own_observed_outcomes=sorted(e for e in edges if e[0] in OWN),
        rows=rows,probe_fixtures=evidence,mutations=mutants,mutation_count=len(mutants),input_hashes=before,
        runtime_seconds=time.perf_counter()-start,limits=dict(seconds=SECONDS,memory_mib=MEMORY_MIB,instructions_each=MAX_STEPS,events_each=MAX_EVENTS,
            probe_instructions=3_000_000,probe_events=8_000_000),
        domain='Full original wrapper vs C, framed services. Probe fixtures generated by original encoded063E+handlers, CRC-constrained sectors PASS / finite BIOS failure FAIL; no plaintext loaded. Internal probe traffic is opaque in wrapper parity; whole RAM and registers compare.'))
    print(f'PASS protection: {len(rows)} cases,{len(set(OWN)&sites)} own sites,{len(mutants)} mutants',flush=True)

def main():
    if len(sys.argv)>=3 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3:]);return
    selected=sys.argv[2:] if len(sys.argv)>1 and sys.argv[1]=='--focus' else []
    with temporary_build_directory(prefix='protection-',parent=BUILD) as directory:
        run_bounded([sys.executable,__file__,'--worker',str(directory),*selected],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

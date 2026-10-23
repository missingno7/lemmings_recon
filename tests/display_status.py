"""1550 byte-port polling: independent model, original instructions, C core."""
import ctypes
import gc
import random
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INSN
from unicorn import x86_const as x
import video_restore as common
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import ROOT,BUILD,sha,read_json,write_json
from unpack import ASSET,unpack,relocated

IMAGE,ORACLE=unpack(ASSET.read_bytes());START,END=0x1550,0x1562
CODE=bytes.fromhex('8b16da1f80c206eca80874fbeca80875fbc3')
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for i in MD.disasm(CODE,START)}
EDGES={(0x155a,0x1557),(0x155a,0x155c),(0x155f,0x155c),(0x155f,0x1561)}
FULL,LOGIC=common.FULL,common.LOGIC
State,Result,MEM,Regs=common.State,common.Result,common.MEM,common.Regs
PORT_IN=ctypes.CFUNCTYPE(ctypes.c_uint8,ctypes.c_void_p,MEM,ctypes.c_uint16,ctypes.c_uint16)
PORT_OUT=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,ctypes.c_uint16,ctypes.c_uint8,ctypes.c_uint16)
class Ports(ctypes.Structure):_fields_=[('context',ctypes.c_void_p),('out_byte',PORT_OUT),('in_byte',PORT_IN)]
REPORT=BUILD/'display-status-differential.json';ORIGINAL_REPORT=BUILD/'display-status-contract-original.json'
class NativeMismatch(AssertionError):pass
def fail(message):raise common.fixture.VerificationFailure(message)
def mismatch(message):raise NativeMismatch(message)


def cases():
    rows=[]
    def add(name,**kw):
        row=dict(name=name,seed=len(rows),**kw);row.setdefault('base',0x3d4)
        row.setdefault('sequence',[0,8,0]);row.setdefault('load',common.LOADS[row['seed']%3]);rows.append(row)
    for n in range(256):
        seq=[n,n&~8] if n&8 else [n,n|8,n&~8]
        add(f'byte-and-port-low-{n:02x}',base=0x3d00|n,sequence=seq,ah=n)
    for name,sequence in (('already-set',[8,0]),('both-poll-loops',[0,0x80,0xff,0x88,0xf8,0xc0]),
                          ('long-set-poll',[0]*23+[8,0]),('long-clear-poll',[8]+[0xf8]*23+[0xf0]),
                          ('all-other-bits',[0xf7,0xff,0xf7])):add(name,sequence=sequence)
    for kind in ('base-ret-alias','base-low-mutates-high','ret-low-mutates-high','return-write',
                 'rewrite-base','ret-sp-ffff','ret-sp-zero','ret-sp-one','ret-a20','ds-a20',
                 'vga-base','vga-return','vga-base-and-return'):
        add(kind,kind=kind,bus_effect=kind in ('base-low-mutates-high','ret-low-mutates-high'),vga=kind.startswith('vga-'))
    for load in common.LOADS:
        for missing in ('no-ports','no-input'):add(f'{missing}-{load:04x}',load=load,missing=missing,base=0x3dfa)
    return rows


def prepare(case):
    rng=random.Random(0x155000+case['seed']);memory=bytearray(rng.randbytes(1<<20))
    loaded=relocated(IMAGE,ORACLE['relocations'],case['load']);start=case['load']<<4
    memory[start:start+len(loaded)]=loaded
    initial={k:rng.randrange(65536) for k in common.REGS}
    initial.update(ds=0x3000,ss=0x7000,sp=0x8000,flags=2|((case['seed']*0x95)&0xed5))
    initial['ax']=((case.get('ah',rng.randrange(256)))<<8)|(initial['ax']&255)
    kind=case.get('kind')
    if kind=='base-ret-alias':initial.update(ss=initial['ds'],sp=0x1fda)
    if kind=='ds-a20':initial['ds']=0xffff
    if kind=='ret-sp-ffff':initial['sp']=0xffff
    if kind=='ret-sp-zero':initial['sp']=0
    if kind=='ret-sp-one':initial['sp']=1
    if kind=='ret-a20':initial.update(ss=0xffff,sp=0xf)
    if kind in ('vga-base','vga-base-and-return'):initial['ds']=0xa000
    if kind in ('vga-return','vga-base-and-return'):initial.update(ss=0xa000,sp=0x8800)
    common.putword(memory,initial['ss'],initial['sp'],0xbeef)
    common.putword(memory,initial['ds'],0x1fda,case['base'])
    return memory,initial


class Backend:
    def __init__(self,memory,case,initial,*,native=False):
        self.memory=bytearray(memory);self.case=case;self.initial=initial;self.native=native
        self.events=[];self.inputs=0;self.read_effect=False
        self.vga=common.fixture.MinimapVga(0x155000+case['seed'],2);self.vga.seq[2]=1
        common.putword(self.vga.planes[2],0,0x1fda,case['base'])
        common.putword(self.vga.planes[2],0,0x8800,0xbeef)
        self.mask=FULL
    def guard(self,message):
        if self.native:common.fixture.exit_worker(86,message)
        fail(message)
    def add(self,kind,address,value,flags,mask):
        if len(self.events)>=128:self.guard('Display status event budget exhausted')
        self.events.append((kind,address,value,flags,mask))
    def provider_word(self,segment,offset,value):
        p=common.physical(segment,offset);changed=[]
        for n in range(2):
            at=(p+n)&0xfffff;byte=(value>>(n*8))&255
            # Explicit provider device-context mutation, not a CPU bus write.
            if 0xa0000<=at<0xb0000:self.vga.planes[2][at-0xa0000]=byte
            else:self.memory[at]=byte;changed.append(at)
        return changed
    def read(self,address,flags,mask):
        address&=0xfffff;value=self.vga.read(self.memory,address,flags)
        self.add('read',address,value,flags,mask)
        kind=self.case.get('kind');i=self.initial
        target=(common.physical(i['ds'],0x1fda) if kind=='base-low-mutates-high' else
                common.physical(i['ss'],i['sp']) if kind=='ret-low-mutates-high' else None)
        if not self.read_effect and address==target:
            self.memory[(address+1)&0xfffff]^=0x55;self.read_effect=True
        return value
    def port(self,port,flags,mask):
        if self.inputs>=64:self.guard('Display status input budget exhausted')
        sequence=self.case['sequence']
        if self.inputs>=len(sequence):self.guard('Display status finite provider sequence exhausted')
        value=sequence[self.inputs];self.inputs+=1;self.add('in',port,value,flags,mask)
        if self.inputs==1:
            kind=self.case.get('kind');i=self.initial
            if kind=='rewrite-base':self.provider_word(i['ds'],0x1fda,0x27ff)
            if kind in ('return-write','vga-return','vga-base-and-return'):
                self.provider_word(i['ss'],i['sp'],0x5aa5)
        return value
    def bus(self):
        @common.fixture.READ
        def read(_ctx,_mem,address,flags):
            try:return self.read(address,flags,FULL if self.inputs==0 else LOGIC)
            except BaseException as error:common.fixture.exit_worker(87,f'Display status read:{error}')
        @common.fixture.WRITE
        def write(*_args):common.fixture.exit_worker(87,'Unexpected display status CPU write')
        self.callbacks=(read,write)
        return common.fixture.RasterBus(None,read,write,common.fixture.OUT())
    def ports(self):
        @PORT_IN
        def inp(_ctx,_mem,port,flags):
            try:return self.port(port,flags,FULL if self.inputs==0 else LOGIC)
            except BaseException as error:common.fixture.exit_worker(87,f'Display status input:{error}')
        @PORT_OUT
        def out(*_args):common.fixture.exit_worker(87,'Unexpected display status output')
        self.port_callbacks=(inp,out)
        missing=self.case.get('missing')
        return None if missing=='no-ports' else Ports(None,out,PORT_IN() if missing=='no-input' else inp)


def model(case,memory,initial,*,core):
    backend=Backend(memory,case,initial);s=dict(initial);sites={0x1550,0x1554};edges=set();mask=FULL
    def word(segment,offset):
        p=common.physical(segment,offset);low=backend.read(p,s['flags'],mask);high=backend.read(p+1,s['flags'],mask)
        return low|(high<<8)
    s['dx']=word(s['ds'],0x1fda);a=s['dx']&255;v=(a+6)&255
    f=(4 if not v.bit_count()&1 else 0)|(0x40 if not v else 0)|(0x80 if v&128 else 0)
    f|=(1 if a+6>255 else 0)|(0x10 if (a^6^v)&16 else 0)|(0x800 if (~(a^6)&(a^v)&128) else 0)
    s['flags']=(s['flags']&~0x8d5)|f;s['dx']=(s['dx']&0xff00)|v
    if case.get('missing'):return backend,s,0x1557,1,mask,sites,edges
    for set_phase in (True,False):
        inp,test,jump=(0x1557,0x1558,0x155a) if set_phase else (0x155c,0x155d,0x155f)
        while True:
            sites.update((inp,test,jump));value=backend.port(s['dx'],s['flags'],mask)
            s['ax']=(s['ax']&0xff00)|value
            s['flags']=(s['flags']&~0x8d5)|(0 if value&8 else 0x44);mask=LOGIC
            again=not(value&8) if set_phase else bool(value&8)
            edges.add((jump,inp if again else 0x155c if set_phase else 0x1561))
            if not again:break
    if core:return backend,s,0x1561,0,mask,sites,edges
    sites.add(0x1561);target=word(s['ss'],s['sp']);s['sp']=(s['sp']+2)&65535
    return backend,s,target,0,mask,sites,edges


def original(case,memory,initial,*,core):
    backend=Backend(memory,case,initial);cpu=Uc(UC_ARCH_X86,UC_MODE_16);cpu.mem_map(0,2<<20)
    cpu.mem_write(0,bytes(backend.memory)*2)
    for k,v in dict(initial,cs=case['load'],ip=START).items():cpu.reg_write(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k],v)
    loaded=relocated(IMAGE,ORACLE['relocations'],case['load']);values={(case['load']<<4)+p+n:loaded[p+n] for p,i in INS.items() for n in range(i.size)}
    if any(backend.memory[p]!=v for p,v in values.items()):fail('Display status entered modified code')
    previous=None;mask=FULL;event_flags=initial['flags'];sites=set();edges=set();failure=[];done=False;steps=0
    def error(exc):
        if not failure:failure.append(str(exc))
        cpu.emu_stop()
    def code(uc,_pc,_size,_user):
        nonlocal previous,mask,event_flags,done,steps
        off=uc.reg_read(x.UC_X86_REG_IP)
        if previous in (0x1558,0x155d):mask=LOGIC
        if previous==0x1561:done=True;uc.emu_stop();return
        if previous in (0x155a,0x155f):edges.add((previous,off))
        if (core and off==0x1561) or (case.get('missing') and off==0x1557):done=True;uc.emu_stop();return
        if uc.reg_read(x.UC_X86_REG_CS)!=case['load'] or off not in INS:error('Display status escaped');return
        steps+=1
        if steps>256:error('Display status instruction budget exhausted');return
        event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS);previous=off;sites.add(off)
    def read(uc,_access,address,size,_v,_user):
        try:
            for n in range(size):uc.mem_write(address+n,bytes((backend.read(address+n,event_flags,mask),)))
        except BaseException as exc:error(exc)
    def write(*_args):error('Unexpected display status original CPU write')
    def inp(uc,port,size,_user):
        try:
            if size!=1:fail('Wrong display status IN width')
            value=backend.port(port,event_flags,mask)
            if any(backend.memory[p]!=v for p,v in values.items()):fail('Display provider modified code')
            uc.mem_write(0,bytes(backend.memory));uc.mem_write(1<<20,bytes(backend.memory))
            return value
        except BaseException as exc:error(exc);return 0
    cpu.hook_add(UC_HOOK_CODE,code);cpu.hook_add(UC_HOOK_MEM_READ,read);cpu.hook_add(UC_HOOK_MEM_WRITE,write)
    cpu.hook_add(UC_HOOK_INSN,inp,None,1,0,x.UC_X86_INS_IN)
    cpu.emu_start((case['load']<<4)+START,0,count=257)
    if failure:fail(case['name']+': '+failure[0])
    if not done:fail('Display status original did not finish')
    regs={k:cpu.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in (*common.REGS,'cs','ip')}
    return backend,regs,mask,sites,edges


def equal(actual,expected,error,label,*,events=True):
    if actual.memory!=expected.memory:error(label+' RAM differs')
    if actual.vga.state()!=expected.vga.state():error(label+' VGA differs')
    if actual.inputs!=expected.inputs or actual.read_effect!=expected.read_effect:error(label+' provider/read effects differ')
    got=actual.events if events else [e for e in actual.events if e[0]=='in']
    want=expected.events if events else [e for e in expected.events if e[0]=='in']
    if len(got)!=len(want):error(label+' ordered event count differs')
    for n,(a,b) in enumerate(zip(got,want)):
        if a[:3]!=b[:3] or (a[3]^b[3])&b[4]:error(label+f' event{n} differs {a}/{b}')


def original_case(case,*,core):
    memory,initial=prepare(case);expected,s,target,status,mask,sites,edges=model(case,memory,initial,core=core)
    backend,regs,actual_mask,seen,branch=original(case,memory,initial,core=core)
    common.equal_state(regs,s,mask,fail,case['name']+' model');equal(backend,expected,fail,case['name']+' model')
    if (regs['cs'],regs['ip'],actual_mask,seen,branch)!=(case['load'],target,mask,sites,edges):fail(case['name']+' original control/site domain differs')
    if status and backend.inputs:fail('Missing provider executed IN')
    return memory,initial,backend,regs,target,status,mask,sites,edges


class Native:
    def __init__(self,directory,mutation=0):
        self.library=ctypes.CDLL(str(build(Path(directory)/f'display-status-m{mutation}.dll',mutation,'display_status')))
        self.core=self.library.lmn_wait_display_status_bit3_cycle_core
        self.core.argtypes=[MEM,ctypes.POINTER(State),ctypes.POINTER(Ports),ctypes.POINTER(common.fixture.RasterBus)];self.core.restype=Result
        self.adapter=self.library.lmn_wait_display_status_bit3_cycle_adapter
        self.adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Ports),ctypes.POINTER(common.fixture.RasterBus)];self.adapter.restype=None


def compare(native,case):
    seen=set();edges=set()
    for core in (False,True):
        memory,initial,expected,regs,target,status,mask,sites,branch=original_case(case,core=core);seen|=sites;edges|=branch
        if native is None:continue
        for null in ((False,) if case.get('vga') or case.get('bus_effect') else (False,True)):
            backend=Backend(memory,case,initial,native=True);bus=backend.bus();ports=backend.ports()
            if core:
                result=native.core(common.buffer(backend.memory),ctypes.byref(common.to_state(initial)),common.pointer(ports),None if null else ctypes.byref(bus))
                got=common.state_dict(result.state)
                if (result.continuation,result.status)!=(target,status):mismatch(case['name']+' core boundary differs')
            else:
                r=Regs(**initial,cs=case['load'],ip=START)
                native.adapter(common.buffer(backend.memory),ctypes.byref(r),common.pointer(ports),None if null else ctypes.byref(bus))
                got={k:getattr(r,k) for k in common.REGS}
                if (r.cs,r.ip)!=(case['load'],target):mismatch(case['name']+' adapter boundary differs')
            common.equal_state(got,regs,mask,mismatch,case['name']);equal(backend,expected,mismatch,case['name'],events=not null)
    return dict(name=case['name'],sites=sorted(seen),edges=sorted(edges),vga=case.get('vga',False),null_repeat=not(case.get('vga') or case.get('bus_effect')))


def input_hashes(native=False):
    paths=set(common.input_hashes(False));paths.update(('tests/display_status.py','metadata/inputs.json'))
    if native:paths.update(('c/display_status.c','c/display_status.h','c/aligned_read_mask.h','c/lemmings_sym.h','c/regs.h','c/special_blit.h','tools/cbuild.py','tools/difftest.py','tools/coverage.py'))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def original_phase():
    before=input_hashes();rows=[];sites=set();edges=set()
    if IMAGE[START:END]!=CODE or sha(IMAGE)!='b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e':fail('Display original bytes differ')
    if sha(ASSET.read_bytes())!='5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d':fail('Pinned EXE differs')
    for case in cases():
        for core in (False,True):
            result=original_case(case,core=core);sites|=result[-2];edges|=result[-1]
        rows.append(case['name']);gc.collect()
    if sites!=set(INS) or edges!=EDGES:fail('Incomplete original display status coverage')
    if before!=input_hashes():fail('Display original inputs changed')
    write_json(ORIGINAL_REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),auxiliary_core_cases=len(rows),cases=rows,executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),c_coverage_claimed=False,input_hashes=before))
    print(f'PASS display status original: {len(rows)} cases x2 boundaries,9 sites,4 edges;no C coverage',flush=True)


def worker(directory=None):
    before=input_hashes(directory is not None);original_phase()
    if directory is None:return
    native=Native(directory);rows=[]
    for case in cases():rows.append(compare(native,case));gc.collect()
    mutants=[]
    for mutation,name in ((1,'byte-and-port-low-fa'),(2,'both-poll-loops'),(3,'rewrite-base'),(4,'return-write')):
        native=Native(directory,mutation);case=next(c for c in cases() if c['name']==name)
        try:compare(native,case)
        except NativeMismatch:mutants.append(dict(mutation=mutation,case=name))
        else:fail(f'Display status mutant{mutation} survived')
    if before!=input_hashes(True):fail('Display native inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),auxiliary_core_cases=len(rows),null_bus_cases_each_boundary=sum(r['null_repeat'] for r in rows),cases=rows,mutation_count=4,mutations_detected=mutants,translated_code_bytes=18,native_code_ranges=[[START,END]],executed_instruction_addresses=sorted({p for r in rows for p in r['sites']}),branch_edges=sorted(EDGES),input_hashes=before,limits=dict(worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,original_instructions=256,port_inputs=64,events=128),domain='1550 two-phase bit3 wait with original unbounded loops; finite constructed byte-port providers; RAM/VGA base and liveRET; all12CPUfields/definedflags/order; intactcode/sameCS/TFclear/quiescentIRQ.'))
    print(f'PASS display status C: {len(rows)} adapter +{len(rows)} core cases,9 sites,4 edges;4 completed mutants',flush=True)


def budget_probe(directory):
    case=dict(name='budget-probe',seed=0,load=0x1010,base=0x3d4,sequence=[0]*65)
    memory,initial=prepare(case);backend=Backend(memory,case,initial,native=True);ports=backend.ports();native=Native(directory)
    native.core(common.buffer(backend.memory),ctypes.byref(common.to_state(initial)),common.pointer(ports),None)
    fail('Expected input-budget exhaustion did not occur')


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if len(sys.argv)==3 and sys.argv[1]=='--budget-probe':budget_probe(sys.argv[2]);return
    if sys.argv[1:]==['--original-worker']:worker();return
    if sys.argv[1:]==['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True);run_bounded([sys.executable,str(Path(__file__).resolve()),'--original-worker'],cwd=ROOT,timeout=120,memory_mib=384);return
    if len(sys.argv)!=1:raise SystemExit('Unexpected display status arguments')
    BUILD.mkdir(exist_ok=True);REPORT.unlink(missing_ok=True)
    try:
        with temporary_build_directory(prefix='display-status-',parent=BUILD) as directory:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=120,memory_mib=384)
        with temporary_build_directory(prefix='display-status-budget-',parent=BUILD) as directory:
            result=run_bounded([sys.executable,str(Path(__file__).resolve()),'--budget-probe',directory],cwd=ROOT,timeout=30,memory_mib=384,check=False)
            if result.returncode!=86:fail(f'Expected budget exit86,got{result.returncode}')
        report=read_json(REPORT);report['budget_probe_exit']=86;write_json(REPORT,report)
    except BaseException:
        REPORT.unlink(missing_ok=True);raise
if __name__=='__main__':main()

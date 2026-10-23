"""4C20/4C32/4C36 display outputs with original live origin/return aliases."""
import ctypes
import gc
import random
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INSN
from unicorn import x86_const as x
import display_status as status
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import ROOT,BUILD,sha,write_json

common=status.common;IMAGE,ORACLE=status.IMAGE,status.ORACLE
CODE=bytes.fromhex('8b1e761fe80f00a1761f8706781fa3761fc38b1e781ffa8b16da1f8ae7b00cef8ae3fec0effbc3')
START,END=0x4c20,0x4c47
INS={i.address:i for i in status.MD.disasm(CODE,START)}
ENTRIES={0:0x4c32,1:0x4c36,2:0x4c20};RETURNS={0:0x4c46,1:0x4c46,2:0x4c31}
REPORT=BUILD/'display-start-differential.json';ORIGINAL_REPORT=BUILD/'display-start-contract-original.json'
FULL=common.FULL
class NativeMismatch(AssertionError):pass
def fail(message):raise common.fixture.VerificationFailure(message)
def mismatch(message):raise NativeMismatch(message)


def cases():
    rows=[]
    def add(name,**kw):
        row=dict(name=name,seed=len(rows),**kw);row.setdefault('primary',0x1234);row.setdefault('alternate',0x6d60)
        row.setdefault('load',common.LOADS[row['seed']%3]);rows.append(row)
    for n in range(256):add(f'origin-byte-{n:02x}',primary=(n<<8)|(255-n),alternate=(255-n)<<8|n,bx=n<<8|n)
    for kind in ('origins-write','base-write','return-write','child-return-write','ss-primary','ss-alternate',
                 'ss-base','sp-ffff','sp-zero','sp-one','ret-a20','ds-a20','vga-origins','vga-stack','vga-both'):
        add(kind,kind=kind,vga=kind.startswith('vga-'))
    for load in common.LOADS:
        for missing in ('no-bus','no-output'):add(f'{missing}-{load:04x}',missing=missing,load=load)
    return rows


def prepare(case):
    rng=random.Random(0x4c2000+case['seed']);memory=bytearray(rng.randbytes(1<<20))
    loaded=status.relocated(IMAGE,ORACLE['relocations'],case['load']);start=case['load']<<4
    memory[start:start+len(loaded)]=loaded
    s={k:rng.randrange(65536) for k in common.REGS}
    s.update(ds=0x3000,ss=0x7000,sp=0x8000,bx=case.get('bx',0x8734),flags=2|((case['seed']*0x95)&0xed5))
    kind=case.get('kind')
    if kind=='ds-a20':s['ds']=0xffff
    if kind in ('ss-primary','ss-alternate','ss-base'):
        s.update(ss=s['ds'],sp={'ss-primary':0x1f78,'ss-alternate':0x1f7a,'ss-base':0x1fdc}[kind])
    if kind=='sp-ffff':s['sp']=0xffff
    if kind=='sp-zero':s['sp']=0
    if kind=='sp-one':s['sp']=1
    if kind=='ret-a20':s.update(ss=0xffff,sp=0xf)
    if kind in ('vga-origins','vga-both'):s['ds']=0xa000
    if kind in ('vga-stack','vga-both'):s.update(ss=0xa000,sp=0x8800)
    common.putword(memory,s['ss'],s['sp'],0xbeef)
    for off,value in ((0x1f76,case['primary']),(0x1f78,case['alternate']),(0x1fda,0x3d4)):
        common.putword(memory,s['ds'],off,value)
    return memory,s


class Backend(status.Backend):
    def __init__(self,memory,case,initial,*,native=False):
        super().__init__(memory,dict(case,base=0x3d4),initial,native=native);self.outputs=0
        for index,value in ((0,0),(1,0),(3,0),(5,0),(8,255)):self.vga.gc[index]=value
        common.putword(self.vga.planes[2],0,0x1f76,case['primary'])
        common.putword(self.vga.planes[2],0,0x1f78,case['alternate'])
        common.putword(self.vga.planes[2],0,0x87fe,0x4c27)
    def write(self,address,value,flags):
        address&=0xfffff;self.vga.write(self.memory,address,value,flags)
        self.add('write',address,value,flags,FULL)
    def out(self,port,value,flags):
        if self.outputs>=2:self.guard('Display start output budget exhausted')
        self.add('out',port,value,flags,FULL);self.outputs+=1
        if self.outputs==1:
            kind=self.case.get('kind');s=self.initial
            if kind=='origins-write':
                self.provider_word(s['ds'],0x1f76,0xabcd);self.provider_word(s['ds'],0x1f78,0x789a)
            if kind=='base-write':self.provider_word(s['ds'],0x1fda,0x7788)
            if kind=='return-write':self.provider_word(s['ss'],s['sp'],0x5aa5)
            if kind=='child-return-write':self.provider_word(s['ss'],(s['sp']-2)&65535,0xdead)
    def bus(self,*,fallback=False):
        @common.fixture.READ
        def read(_ctx,_mem,address,flags):
            try:return self.read(address,flags,FULL)
            except BaseException as error:common.fixture.exit_worker(87,f'Display start read:{error}')
        @common.fixture.WRITE
        def write(_ctx,_mem,address,value,flags):
            try:self.write(address,value,flags)
            except BaseException as error:common.fixture.exit_worker(87,f'Display start write:{error}')
        @common.fixture.OUT
        def out(_ctx,port,value,flags):
            try:self.out(port,value,flags)
            except BaseException as error:common.fixture.exit_worker(87,f'Display start output:{error}')
        self.callbacks=(read,write,out)
        missing=self.case.get('missing')
        if missing=='no-bus':return None
        return common.fixture.RasterBus(None,common.fixture.READ() if fallback else read,
            common.fixture.WRITE() if fallback else write,common.fixture.OUT() if missing=='no-output' else out)


def model(case,memory,initial,*,entry,core):
    b=Backend(memory,case,initial);s=dict(initial);sites=set()
    def mark(pc):sites.add(pc)
    def word(seg,off):
        p=common.physical(seg,off);low=b.read(p,s['flags'],FULL);high=b.read(p+1,s['flags'],FULL);return low|high<<8
    def put(seg,off,value):
        p=common.physical(seg,off);b.write(p,value&255,s['flags']);b.write(p+1,value>>8,s['flags'])
    def pop():value=word(s['ss'],s['sp']);s['sp']=(s['sp']+2)&65535;return value
    if entry==2:
        mark(0x4c20);s['bx']=word(s['ds'],0x1f76);mark(0x4c24);s['sp']=(s['sp']-2)&65535;put(s['ss'],s['sp'],0x4c27)
    elif entry==0:mark(0x4c32);s['bx']=word(s['ds'],0x1f78)
    mark(0x4c36);s['flags']&=~0x200;mark(0x4c37);s['dx']=word(s['ds'],0x1fda)
    mark(0x4c3b);s['ax']=(s['ax']&255)|(s['bx']&0xff00);mark(0x4c3d);s['ax']=(s['ax']&0xff00)|12
    if case.get('missing'):return b,s,0x4c3f,1,sites
    mark(0x4c3f);b.out(s['dx'],s['ax'],s['flags']);mark(0x4c40);s['ax']=(s['ax']&255)|((s['bx']&255)<<8)
    mark(0x4c42);s['ax']=(s['ax']&0xff00)|13;s['flags']&=~0x8d4
    mark(0x4c44);b.out(s['dx'],s['ax'],s['flags']);mark(0x4c45);s['flags']|=0x200
    if entry==2:
        mark(0x4c46);target=pop()
        if target!=0x4c27:return b,s,target,2,sites
        mark(0x4c27);s['ax']=word(s['ds'],0x1f76);mark(0x4c2a);alternate=word(s['ds'],0x1f78)
        put(s['ds'],0x1f78,s['ax']);s['ax']=alternate;mark(0x4c2e);put(s['ds'],0x1f76,s['ax'])
    if core:return b,s,RETURNS[entry],0,sites
    mark(RETURNS[entry]);target=pop();return b,s,target,0,sites


def original(case,memory,initial,*,entry,core):
    b=Backend(memory,case,initial);cpu=Uc(UC_ARCH_X86,UC_MODE_16);cpu.mem_map(0,2<<20);cpu.mem_write(0,bytes(memory)*2)
    for k,v in dict(initial,cs=case['load'],ip=ENTRIES[entry]).items():cpu.reg_write(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k],v)
    loaded=status.relocated(IMAGE,ORACLE['relocations'],case['load']);values={(case['load']<<4)+pc+n:loaded[pc+n] for pc,i in INS.items() for n in range(i.size)}
    if any(b.memory[p]!=v for p,v in values.items()):fail('Display start entered modified code')
    sites=set();previous=None;pending=None;done=False;result_status=None;event_flags=initial['flags'];failure=[]
    def error(exc):
        if not failure:failure.append(str(exc))
        cpu.emu_stop()
    def sync(addresses):
        for p in addresses:
            if p in values and b.memory[p]!=values[p]:fail('Display start modified code')
            value=bytes((b.memory[p],));cpu.mem_write(p,value);cpu.mem_write(p+(1<<20),value)
    def code(uc,_pc,_size,_user):
        nonlocal previous,pending,done,result_status,event_flags
        off=uc.reg_read(x.UC_X86_REG_IP)
        if pending is not None:
            expected=pending;pending=None
            if expected is False:done,result_status=True,0;uc.emu_stop();return
            if off!=expected:done,result_status=True,2;uc.emu_stop();return
        if uc.reg_read(x.UC_X86_REG_CS)!=case['load'] or off not in INS:error('Display start escaped');return
        if (core and off==RETURNS[entry]) or (case.get('missing') and off==0x4c3f):
            done,result_status=True,1 if case.get('missing') else 0;uc.emu_stop();return
        if len(sites)>=17:error('Display start instruction budget exhausted');return
        sites.add(off);previous=off;event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        if off in (0x4c31,0x4c46):pending=0x4c27 if entry==2 and off==0x4c46 else False
    def read(uc,_access,address,size,_v,_user):
        try:
            for n in range(size):uc.mem_write(address+n,bytes((b.read(address+n,event_flags,FULL),)))
        except BaseException as exc:error(exc)
    def write(_uc,_access,address,size,value,_user):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;b.write(p,(value>>(8*n))&255,event_flags);sync((p,))
        except BaseException as exc:error(exc)
    def out(uc,port,size,value,_user):
        try:
            if size!=2:fail('Unexpected display start port width')
            b.out(port,value,event_flags)
            if any(b.memory[p]!=v for p,v in values.items()):fail('Display provider modified code')
            uc.mem_write(0,bytes(b.memory));uc.mem_write(1<<20,bytes(b.memory))
        except BaseException as exc:error(exc)
    cpu.hook_add(UC_HOOK_CODE,code);cpu.hook_add(UC_HOOK_MEM_READ,read);cpu.hook_add(UC_HOOK_MEM_WRITE,write)
    cpu.hook_add(UC_HOOK_INSN,out,None,1,0,x.UC_X86_INS_OUT)
    cpu.emu_start((case['load']<<4)+ENTRIES[entry],0,count=32)
    if failure:fail(case['name']+': '+failure[0])
    if not done:fail('Display start original did not reach a boundary')
    regs={k:cpu.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in (*common.REGS,'cs','ip')}
    return b,regs,result_status,sites


def equal(actual,expected,error,label,*,events=True):
    if actual.memory!=expected.memory:error(label+' RAM differs')
    if actual.vga.state()!=expected.vga.state():error(label+' VGA differs')
    if actual.outputs!=expected.outputs:error(label+' output count differs')
    got=actual.events if events else [e for e in actual.events if e[0]=='out']
    want=expected.events if events else [e for e in expected.events if e[0]=='out']
    if len(got)!=len(want):error(label+f' event count differs {len(got)}/{len(want)}')
    for n,(a,b) in enumerate(zip(got,want)):
        if a[:3]!=b[:3] or (a[3]^b[3])&b[4]:error(label+f' event{n} differs {a}/{b}')


def original_case(case,*,entry,core):
    memory,initial=prepare(case);expected,s,target,expected_status,sites=model(case,memory,initial,entry=entry,core=core)
    b,regs,st,seen=original(case,memory,initial,entry=entry,core=core)
    label=case['name']+f' entry{entry}/core{core}'
    common.equal_state(regs,s,FULL,fail,label+' model');equal(b,expected,fail,label+' model')
    if (regs['cs'],regs['ip'],st,seen)!=(case['load'],target,expected_status,sites):fail(label+' original control/site mismatch')
    if case.get('kind')=='child-return-write' and entry==2 and (target,st)!=(0xdead,2):fail('Changed child return was not exercised')
    return memory,initial,b,regs,target,st,seen


class Native:
    def __init__(self,directory,mutation=0):
        self.library=ctypes.CDLL(str(build(Path(directory)/f'display-start-m{mutation}.dll',mutation,'display_start')))
        self.core=self.library.lmn_program_display_start_core
        self.core.argtypes=[status.MEM,ctypes.POINTER(common.State),ctypes.c_int,ctypes.POINTER(common.fixture.RasterBus)];self.core.restype=common.Result
        self.adapter=self.library.lmn_program_display_start_adapter
        self.adapter.argtypes=[status.MEM,ctypes.POINTER(common.Regs),ctypes.c_int,ctypes.POINTER(common.fixture.RasterBus)];self.adapter.restype=None


def compare(native,case):
    sites=set()
    for entry in ENTRIES:
        for core in (False,True):
            memory,initial,expected,regs,target,st,seen=original_case(case,entry=entry,core=core);sites|=seen
            if native is None:continue
            for fallback in ((False,) if case.get('vga') else (False,True)):
                b=Backend(memory,case,initial,native=True);bus=b.bus(fallback=fallback)
                if core:
                    result=native.core(common.buffer(b.memory),ctypes.byref(common.to_state(initial)),entry,common.pointer(bus));got=common.state_dict(result.state)
                    if (result.continuation,result.status)!=(target,st):mismatch(case['name']+' core control differs')
                else:
                    r=common.Regs(**initial,cs=case['load'],ip=ENTRIES[entry]);native.adapter(common.buffer(b.memory),ctypes.byref(r),entry,common.pointer(bus))
                    got={k:getattr(r,k) for k in common.REGS}
                    if (r.cs,r.ip)!=(case['load'],target):mismatch(case['name']+' adapter control differs')
                label=case['name']+f' entry{entry}/core{core}/fallback{fallback}'
                common.equal_state(got,regs,FULL,mismatch,label);equal(b,expected,mismatch,label,events=not(fallback or case.get('missing')=='no-bus'))
    return dict(name=case['name'],sites=sorted(sites),vga=case.get('vga',False))


def input_hashes(native=False):
    paths=set(status.input_hashes(native));paths.update(('tests/display_start.py',))
    if native:paths.update(('c/display_start.c','c/display_start.h'))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def original_phase():
    before=input_hashes();rows=[];sites=set()
    if IMAGE[START:END]!=CODE:fail('Display start bytes differ')
    if sha(IMAGE)!='b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e' or sha(status.ASSET.read_bytes())!='5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d':fail('Pinned display image differs')
    for case in cases():
        row=compare(None,case);rows.append(row);sites.update(row['sites']);gc.collect()
    if sites!=set(INS):fail('Incomplete display start original coverage')
    if before!=input_hashes():fail('Display start original inputs changed')
    write_json(ORIGINAL_REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),entries_each=3,boundaries_each_entry=2,executed_instruction_addresses=sorted(sites),branch_edges=[],cases=rows,input_hashes=before,c_coverage_claimed=False))
    print(f'PASS display start original: {len(rows)} cases x3 entries x2 boundaries,17 sites;no C coverage',flush=True)


def worker(directory=None):
    before=input_hashes(directory is not None);original_phase()
    if directory is None:return
    native=Native(directory);rows=[]
    for case in cases():rows.append(compare(native,case));gc.collect()
    mutants=[]
    for mutation,name in ((1,'origin-byte-00'),(2,'origins-write'),(3,'origins-write'),(4,'child-return-write')):
        native=Native(directory,mutation);case=next(c for c in cases() if c['name']==name)
        try:compare(native,case)
        except NativeMismatch:mutants.append(dict(mutation=mutation,case=name))
        else:fail(f'Display start mutant{mutation} survived')
    if before!=input_hashes(True):fail('Display start native inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),entries_each=3,boundaries_each_entry=2,ram_fallback_cases_each_entry_boundary=sum(not r['vga'] for r in rows),mutation_count=4,mutations_detected=mutants,cases=rows,translated_code_bytes=39,native_code_ranges=[[START,END]],executed_instruction_addresses=sorted({p for r in rows for p in r['sites']}),branch_edges=[],input_hashes=before,limits=dict(worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,original_instructions=32,word_outputs=2,events=128),domain='4C20 live swap calling4C36;4C32 alternate-page entry; explicit wordOUT memory/device effects,unconditionalSTI,actualchild/outerRET andoptionalCPUbus;sameCS/intactcode/TFclear/quiescentIRQ.'))
    print(f'PASS display start C: {len(rows)} cases x3 entries x2 boundaries,17 sites;4 completed mutants',flush=True)


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if sys.argv[1:]==['--original-worker']:worker();return
    if sys.argv[1:]==['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True);run_bounded([sys.executable,str(Path(__file__).resolve()),'--original-worker'],cwd=ROOT,timeout=120,memory_mib=384);return
    if len(sys.argv)!=1:raise SystemExit('Unexpected display start arguments')
    BUILD.mkdir(exist_ok=True);REPORT.unlink(missing_ok=True)
    try:
        with temporary_build_directory(prefix='display-start-',parent=BUILD) as directory:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=120,memory_mib=384)
    except BaseException:
        REPORT.unlink(missing_ok=True);raise
if __name__=='__main__':main()

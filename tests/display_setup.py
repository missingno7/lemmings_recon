"""4BE7 display setup: live BIOS state, shared entries and real layout far frame."""
import ctypes
import gc
import random
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INTR
from unicorn import x86_const as x
import video_restore as common
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import ROOT,BUILD,read_json,sha,write_json
from unpack import ASSET,unpack,relocated

IMAGE,ORACLE=unpack(ASSET.read_bytes());START,END=0x4be7,0x4c17
CODE=bytes.fromhex('2ec606be83ff90fab89000cd10fbc706761f0000c706781f606dc7067a1f0000b88002bb5e018b16761f9a08880000c3')
MD=common.capstone.Cs(common.capstone.CS_ARCH_X86,common.capstone.CS_MODE_16);MD.detail=True
LOCAL={i.address:i for i in MD.disasm(CODE,START)}
INS=LOCAL|{i.address:i for i in MD.disasm(IMAGE[0x8808:0x8822],0x8808)}
SYMS={r['symbol_name']:r for r in read_json(ROOT/'metadata/symbols.json')}
FIELDS={name:SYMS[name]['address'] for name in ('DrawingOrigin','AlternateDrawingOrigin','DrawingPageByteOffset','DrawingWidthPixels','DrawingHeight','DrawingPitchBytes','DrawingExtentBytes')}
ENTRIES={0:0x4be7,1:0x4bf5,2:0x4c07};FULL,SHIFT,MUL=common.FULL,common.LOGIC,0xf03
REPORT=BUILD/'display-setup-differential.json';ORIGINAL_REPORT=BUILD/'display-setup-contract-original.json'
class Result(ctypes.Structure):
    _fields_=[('state',common.State),('code_segment',ctypes.c_uint16),('continuation',ctypes.c_uint16),('status',ctypes.c_int)]
class NativeMismatch(AssertionError):pass
def fail(message):raise common.fixture.VerificationFailure(message)
def mismatch(message):raise NativeMismatch(message)


def cases():
    rows=[]
    def add(name,**kw):
        row=dict(name=name,seed=len(rows),**kw);row.setdefault('load',common.LOADS[row['seed']%3]);rows.append(row)
    for n in range(32):add(f'bios-state-{n:02x}')
    for kind in ('keep-frame','returned-ds-a20','returned-ss-a20','outer-return-write','width-ip-alias',
                 'width-cs-alias','origin-ip-alias','origin-cs-alias','initialize-return-alias',
                 'origin-read-modifies-high','vga-data','vga-stack','vga-both','sp-zero','sp-one',
                 'far-sp-ffff-equal-CS','far-sp-fffe-equal-CS'):
        add(kind,kind=kind,vga=kind.startswith('vga-'),read_effect=kind=='origin-read-modifies-high',retf_seam=kind.startswith('far-sp-'))
    for load in common.LOADS:
        for missing in ('no-services','no-mode'):add(f'{missing}-{load:04x}',missing=missing,load=load)
    return rows


def prepare(case):
    rng=random.Random(0x4be700+case['seed']);memory=bytearray(rng.randbytes(1<<20))
    loaded=relocated(IMAGE,ORACLE['relocations'],case['load']);start=case['load']<<4
    memory[start:start+len(loaded)]=loaded
    initial={k:rng.randrange(65536) for k in common.REGS};returned={k:rng.randrange(65536) for k in common.REGS}
    for index,s in enumerate((initial,returned)):
        s.update(ds=0x3000+index*0x500,ss=0x7000+index*0x400,sp=0x8000+index*0x100,
                 flags=2|((case['seed']*(0x95+index*8))&0xed5))
    kind=case.get('kind')
    if kind=='keep-frame':returned.update(ds=initial['ds'],ss=initial['ss'],sp=initial['sp'])
    for s in (initial,returned):
        if kind=='returned-ds-a20':s['ds']=0xffff
        if kind=='returned-ss-a20':s.update(ss=0xffff,sp=0xf)
        if kind in ('vga-data','vga-both'):s['ds']=0xa000
        if kind in ('vga-stack','vga-both'):s.update(ss=0xa000,sp=0x8800)
        if kind=='sp-zero':s['sp']=0
        if kind=='sp-one':s['sp']=1
        if kind=='far-sp-ffff-equal-CS':s['sp']=3
        if kind=='far-sp-fffe-equal-CS':s['sp']=2
        if kind in ('width-ip-alias','width-cs-alias','origin-ip-alias','origin-cs-alias'):
            name='DrawingWidthPixels' if kind.startswith('width') else 'DrawingOrigin'
            s.update(ss=s['ds'],sp=FIELDS[name]+(4 if '-ip-' in kind else 2))
        if kind=='initialize-return-alias':s.update(ss=s['ds'],sp=FIELDS['AlternateDrawingOrigin'])
        common.putword(memory,s['ss'],s['sp'],0xbeef)
        common.putword(memory,s['ds'],FIELDS['DrawingOrigin'],0x4321)
        common.putword(memory,s['ds'],FIELDS['AlternateDrawingOrigin'],0x5678)
        common.putword(memory,s['ds'],FIELDS['DrawingPageByteOffset'],0x9abc)
        if case.get('retf_seam'):
            # Unicorn's unhooked RETF batch read and the permissive two-POP
            # model have different CS byte addresses at these segment limits.
            # Give both candidates the same CS; no address-choice claim follows.
            p=((s['ss']<<4)+((s['sp']-4)&65535)+2)&0xfffff
            memory[p]=case['load']&255;memory[(p+1)&0xfffff]=case['load']>>8
    return memory,initial,returned


class Backend:
    def __init__(self,memory,case,initial,returned,*,native=False):
        self.memory=bytearray(memory);self.case=case;self.initial=initial;self.returned=returned;self.native=native
        self.events=[];self.calls=[];self.changed_read=False
        self.vga=common.fixture.MinimapVga(0x4be700+case['seed'],2);self.vga.seq[2]=1
        for index,value in ((0,0),(1,0),(3,0),(5,0),(8,255)):self.vga.gc[index]=value
        common.putword(self.vga.planes[2],0,FIELDS['DrawingOrigin'],0x4321)
        for s in (initial,returned):
            if s['ss']==0xa000:
                common.putword(self.vga.planes[2],0,s['sp'],0xbeef)
                common.putword(self.vga.planes[2],0,(s['sp']-2)&65535,case['load'])
                common.putword(self.vga.planes[2],0,(s['sp']-4)&65535,0x4c16)
    def guard(self,message):
        if self.native:common.fixture.exit_worker(86,message)
        fail(message)
    def add(self,kind,address,value,flags,mask):
        if len(self.events)>=128:self.guard('Display setup access budget exhausted')
        self.events.append((kind,address&0xfffff,value,flags,mask))
    def read(self,address,flags,mask):
        address&=0xfffff;value=self.vga.read(self.memory,address,flags);self.add('read',address,value,flags,mask)
        if self.case.get('read_effect') and not self.changed_read:
            candidates={common.physical(s['ds'],FIELDS['DrawingOrigin']) for s in (self.initial,self.returned)}
            if address in candidates:
                self.memory[(address+1)&0xfffff]^=0x55;self.changed_read=True
        return value
    def write(self,address,value,flags,mask):
        address&=0xfffff;self.vga.write(self.memory,address,value,flags);self.add('write',address,value,flags,mask)
    def provider_word(self,segment,offset,value):
        p=common.physical(segment,offset)
        for n in range(2):
            at=(p+n)&0xfffff;byte=(value>>(8*n))&255
            if 0xa0000<=at<0xb0000:self.vga.planes[2][at-0xa0000]=byte
            else:self.memory[at]=byte
    def mode(self,incoming):
        if self.calls:self.guard('Display setup BIOS service budget exhausted')
        marker=self.memory[common.physical(self.case['load'],0x83be)]
        self.calls.append((dict(incoming),dict(self.returned),marker))
        if self.case.get('kind')=='outer-return-write':self.provider_word(self.returned['ss'],self.returned['sp'],0x5aa5)
        return dict(self.returned)
    def bus(self):
        @common.fixture.READ
        def read(_ctx,_memory,address,flags):
            try:return self.read(address,flags,FULL)
            except BaseException as error:common.fixture.exit_worker(87,f'Display setup read:{error}')
        @common.fixture.WRITE
        def write(_ctx,_memory,address,value,flags):
            try:self.write(address,value,flags,FULL)
            except BaseException as error:common.fixture.exit_worker(87,f'Display setup write:{error}')
        self.bus_refs=(read,write);return common.fixture.RasterBus(None,read,write,common.fixture.OUT())
    def services(self):
        @common.VIDEO
        def mode(_ctx,_memory,incoming,outgoing):
            try:
                result=self.mode(common.state_dict(incoming[0]))
                for name,k in zip(common.FIELDS,common.REGS):setattr(outgoing[0],name,result[k])
            except BaseException as error:common.fixture.exit_worker(87,f'Display setup BIOS:{error}')
        @common.VIDEO
        def page(*_args):common.fixture.exit_worker(87,'Unexpected display setup page service')
        self.service_refs=(mode,page)
        if self.case.get('missing')=='no-services':return None
        return common.Services(None,common.VIDEO() if self.case.get('missing')=='no-mode' else mode,page)


def shifted(flags,before):
    after=before>>1
    set_flags=(1 if before&1 else 0)|(4 if not (after&255).bit_count()&1 else 0)|(0x40 if not after else 0)|(0x800 if before&0x8000 else 0)
    return (flags&~0x8c5)|set_flags


def model(case,memory,initial,returned,*,entry,core):
    b=Backend(memory,case,initial,returned);s=dict(initial);cs=case['load'];mask=FULL;sites=set()
    def mark(pc):sites.add(pc)
    def put(seg,off,value):
        p=common.physical(seg,off);b.write(p,value&255,s['flags'],mask);b.write(p+1,value>>8,s['flags'],mask)
    def word(seg,off):
        p=common.physical(seg,off);low=b.read(p,s['flags'],mask);high=b.read(p+1,s['flags'],mask);return low|high<<8
    def push(value):s['sp']=(s['sp']-2)&65535;put(s['ss'],s['sp'],value)
    def pop():value=word(s['ss'],s['sp']);s['sp']=(s['sp']+2)&65535;return value
    if entry==0:
        mark(0x4be7);b.write(common.physical(cs,0x83be),255,s['flags'],mask);mark(0x4bed)
        mark(0x4bee);s['flags']&=~0x200;mark(0x4bef);s['ax']=0x90
        if case.get('missing'):return b,s,cs,0x4bf2,1,mask,sites
        mark(0x4bf2);s=b.mode(s);mark(0x4bf4);s['flags']|=0x200
    if entry!=2:
        for pc,name,value in ((0x4bf5,'DrawingOrigin',0),(0x4bfb,'AlternateDrawingOrigin',0x6d60),(0x4c01,'DrawingPageByteOffset',0)):
            mark(pc);put(s['ds'],FIELDS[name],value)
    mark(0x4c07);s['ax']=0x280;mark(0x4c0a);s['bx']=0x15e
    mark(0x4c0d);s['dx']=word(s['ds'],FIELDS['DrawingOrigin']);mark(0x4c11);push(cs);push(0x4c16)
    for pc,name,k in ((0x8808,'DrawingWidthPixels','ax'),(0x880b,'DrawingHeight','bx'),(0x880f,'DrawingOrigin','dx')):
        mark(pc);put(s['ds'],FIELDS[name],s[k])
    for pc in (0x8813,0x8815,0x8817):mark(pc);s['flags']=shifted(s['flags'],s['ax']);s['ax']>>=1;mask=SHIFT
    mark(0x8819);put(s['ds'],FIELDS['DrawingPitchBytes'],s['ax'])
    mark(0x881c);product=s['ax']*s['bx'];s['ax']=product&65535;s['dx']=product>>16
    s['flags']=(s['flags']&~0x801)|(0x801 if s['dx'] else 0);mask=MUL
    mark(0x881e);put(s['ds'],FIELDS['DrawingExtentBytes'],s['ax']);mark(0x8821)
    target=pop();target_cs=pop()
    if (target_cs,target)!=(cs,0x4c16):return b,s,target_cs,target,2,mask,sites
    if core:return b,s,cs,0x4c16,0,mask,sites
    mark(0x4c16);return b,s,cs,pop(),0,mask,sites


def original(case,memory,initial,returned,*,entry,core):
    b=Backend(memory,case,initial,returned);cpu=Uc(UC_ARCH_X86,UC_MODE_16);cpu.mem_map(0,2<<20);cpu.mem_write(0,bytes(memory)*2)
    for k,v in dict(initial,cs=case['load'],ip=ENTRIES[entry]).items():cpu.reg_write(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k],v)
    loaded=relocated(IMAGE,ORACLE['relocations'],case['load']);pinned={(case['load']<<4)+p+n:loaded[p+n] for p,i in INS.items() for n in range(i.size)}
    if any(b.memory[p]!=v for p,v in pinned.items()):fail('Display setup entered modified code')
    sites=set();mask=FULL;event_flags=initial['flags'];previous=None;done=False;pause=False;actual_status=None;failure=[];steps=0
    def error(exc):
        if not failure:failure.append(str(exc))
        cpu.emu_stop()
    def sync(addresses):
        for p in addresses:
            if p in pinned and b.memory[p]!=pinned[p]:fail('Display setup modified instruction bytes')
            value=bytes((b.memory[p],));cpu.mem_write(p,value);cpu.mem_write(p+(1<<20),value)
    def code(uc,_pc,_size,_user):
        nonlocal previous,mask,event_flags,done,pause,actual_status,steps
        if previous in (0x8813,0x8815,0x8817):mask=SHIFT
        if previous==0x881c:mask=MUL
        if previous==0x4c16:done,actual_status=True,0;uc.emu_stop();return
        off=uc.reg_read(x.UC_X86_REG_IP)
        if uc.reg_read(x.UC_X86_REG_CS)!=case['load'] or off not in INS:error('Display setup escaped');return
        if (entry==0 and case.get('missing') and off==0x4bf2) or (core and off==0x4c16):
            done,actual_status=True,1 if off==0x4bf2 else 0;uc.emu_stop();return
        steps+=1
        if steps>32:error('Display setup instruction budget exhausted');return
        event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS);previous=off;sites.add(off)
        if off==0x8821:pause=True;uc.emu_stop()
    def read(uc,_access,address,size,_value,_user):
        try:
            for n in range(size):uc.mem_write(address+n,bytes((b.read(address+n,event_flags,mask),)))
        except BaseException as exc:error(exc)
    def write(_uc,_access,address,size,value,_user):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;byte=(value>>(8*n))&255
                if p in pinned and byte!=pinned[p]:fail('Display setup wrote instruction bytes')
                b.write(p,byte,event_flags,mask);sync((p,))
        except BaseException as exc:error(exc)
    def interrupt(uc,number,_user):
        nonlocal mask
        try:
            if number!=0x10 or previous!=0x4bf2:fail('Unexpected display setup interrupt')
            incoming={k:uc.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in common.REGS}
            out=b.mode(incoming)
            if any(b.memory[p]!=v for p,v in pinned.items()):fail('BIOS fixture modified code')
            uc.mem_write(0,bytes(b.memory));uc.mem_write(1<<20,bytes(b.memory))
            for k,v in out.items():uc.reg_write(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k],v)
            mask=FULL
        except BaseException as exc:error(exc)
    code_hook=cpu.hook_add(UC_HOOK_CODE,code);read_hook=cpu.hook_add(UC_HOOK_MEM_READ,read)
    cpu.hook_add(UC_HOOK_MEM_WRITE,write);cpu.hook_add(UC_HOOK_INTR,interrupt)
    cpu.emu_start((case['load']<<4)+ENTRIES[entry],0,count=33)
    if pause and not failure:
        # Execute the original RETF without Unicorn's read-hook IP artifact.
        # Record its two logical word reads first, as in the existing layout gate.
        cpu.hook_del(code_hook);cpu.hook_del(read_hook)
        ss=cpu.reg_read(x.UC_X86_REG_SS);sp=cpu.reg_read(x.UC_X86_REG_SP);flags=cpu.reg_read(x.UC_X86_REG_EFLAGS)
        for delta in (0,2):
            raw=(ss<<4)+((sp+delta)&65535)
            for n in range(2):cpu.mem_write(raw+n,bytes((b.read(raw+n,flags,mask),)))
        cpu.ctl_remove_cache(0,2<<20);cpu.emu_start((case['load']<<4)+0x8821,0,count=1)
        actual=(cpu.reg_read(x.UC_X86_REG_CS),cpu.reg_read(x.UC_X86_REG_IP))
        if actual!=(case['load'],0x4c16):done,actual_status=True,2
        else:
            code_hook=cpu.hook_add(UC_HOOK_CODE,code);read_hook=cpu.hook_add(UC_HOOK_MEM_READ,read)
            previous=None;cpu.ctl_remove_cache(0,2<<20);cpu.emu_start((case['load']<<4)+0x4c16,0,count=2)
    if failure:fail(case['name']+': '+failure[0])
    if not done:fail('Display setup original did not reach a boundary')
    regs={k:cpu.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else common.drawing.oracle.REG[k])&65535 for k in (*common.REGS,'cs','ip')}
    return b,regs,actual_status,mask,sites


def equal(actual,expected,error,label,*,events=True):
    if actual.memory!=expected.memory:error(label+' RAM differs')
    if actual.vga.state()!=expected.vga.state():error(label+' VGA differs')
    if len(actual.calls)!=len(expected.calls):error(label+' BIOS call count differs')
    for a,b in zip(actual.calls,expected.calls):
        common.equal_state(a[0],b[0],FULL,error,label+' BIOS input');common.equal_state(a[1],b[1],FULL,error,label+' BIOS output')
        if a[2]!=255 or a[2]!=b[2]:error(label+' CS marker store/order differs')
    if actual.changed_read!=expected.changed_read:error(label+' read effect differs')
    if events:
        if len(actual.events)!=len(expected.events):error(label+' ordered access count differs')
        for n,(a,b) in enumerate(zip(actual.events,expected.events)):
            if a[:3]!=b[:3] or (a[3]^b[3])&b[4]:error(label+f' event{n} differs {a}/{b}')


def original_case(case,*,entry,core):
    memory,initial,returned=prepare(case);expected,s,cs,target,st,mask,sites=model(case,memory,initial,returned,entry=entry,core=core)
    b,regs,actual_status,actual_mask,seen=original(case,memory,initial,returned,entry=entry,core=core)
    label=case['name']+f' entry{entry}/core{core}'
    common.equal_state(regs,s,mask,fail,label+' model');equal(b,expected,fail,label+' model')
    if (regs['cs'],regs['ip'],actual_status,actual_mask,seen)!=(cs,target,st,mask,sites):fail(label+f' original control differs {(regs["cs"],regs["ip"],actual_status)}/{(cs,target,st)}')
    if case.get('kind') in ('width-ip-alias','width-cs-alias','origin-ip-alias','origin-cs-alias') and st!=2:fail('Far return alias not exercised')
    return memory,initial,returned,b,regs,st,mask,seen


class Native:
    def __init__(self,directory,mutation=0):
        self.library=ctypes.CDLL(str(build(Path(directory)/f'display-setup-m{mutation}.dll',mutation,'display_setup')))
        self.core=self.library.lmn_setup_display_core
        self.core.argtypes=[common.MEM,ctypes.c_uint16,ctypes.POINTER(common.State),ctypes.c_int,ctypes.POINTER(common.Services),ctypes.POINTER(common.fixture.RasterBus)];self.core.restype=Result
        self.adapter=self.library.lmn_setup_display_adapter
        self.adapter.argtypes=[common.MEM,ctypes.POINTER(common.Regs),ctypes.c_int,ctypes.POINTER(common.Services),ctypes.POINTER(common.fixture.RasterBus)];self.adapter.restype=None


def compare(native,case):
    sites=set()
    for entry in ENTRIES:
        for core in (False,True):
            memory,initial,returned,expected,regs,st,mask,seen=original_case(case,entry=entry,core=core);sites|=seen
            if native is None:continue
            for null in ((False,) if case.get('vga') or case.get('read_effect') else (False,True)):
                b=Backend(memory,case,initial,returned,native=True);bus=b.bus();services=b.services()
                if core:
                    result=native.core(common.buffer(b.memory),case['load'],ctypes.byref(common.to_state(initial)),entry,common.pointer(services),None if null else ctypes.byref(bus))
                    got=common.state_dict(result.state)
                    if (result.code_segment,result.continuation,result.status)!=(regs['cs'],regs['ip'],st):mismatch(case['name']+' core control differs')
                else:
                    r=common.Regs(**initial,cs=case['load'],ip=ENTRIES[entry]);native.adapter(common.buffer(b.memory),ctypes.byref(r),entry,common.pointer(services),None if null else ctypes.byref(bus))
                    got={k:getattr(r,k) for k in common.REGS}
                    if (r.cs,r.ip)!=(regs['cs'],regs['ip']):mismatch(case['name']+' adapter control differs')
                label=case['name']+f' entry{entry}/core{core}/null{null}'
                common.equal_state(got,regs,mask,mismatch,label);equal(b,expected,mismatch,label,events=not null)
    return dict(name=case['name'],sites=sorted(sites),vga=case.get('vga',False),null_repeat=not(case.get('vga') or case.get('read_effect')),retf_segment_limit_equal_cs=case.get('retf_seam',False))


def input_hashes(native=False):
    paths=set(common.input_hashes(False));paths.update(('tests/display_setup.py','docs/display-setup.md','docs/drawing-layout.md'))
    if native:paths.update(('c/display_setup.c','c/display_setup.h','c/drawing_layout.c','c/drawing_layout.h','c/video_restore.h','c/regs.h','c/special_blit.h','c/lemmings_sym.h','tools/cbuild.py','tools/difftest.py','tools/coverage.py'))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def original_phase():
    before=input_hashes();rows=[];sites=set()
    if IMAGE[START:END]!=CODE or sha(IMAGE)!='b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e' or sha(ASSET.read_bytes())!='5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d':fail('Pinned display setup bytes differ')
    if not any(r['linear']==0x4c14 for r in ORACLE['relocations']):fail('Layout call relocation not present')
    for case in cases():
        row=compare(None,case);rows.append(row);sites.update(row['sites']);gc.collect()
    if sites!=set(INS):fail('Display setup original coverage incomplete')
    if before!=input_hashes():fail('Display setup original inputs changed')
    write_json(ORIGINAL_REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),entries_each=3,boundaries_each_entry=2,caller_sites=14,integrated_sites=24,caller_bytes=48,integrated_bytes=74,executed_instruction_addresses=sorted(sites),branch_edges=[],cases=rows,c_coverage_claimed=False,input_hashes=before))
    print(f'PASS display setup original: {len(rows)} cases x3entries x2boundaries,14 caller/24 integrated sites;no C coverage',flush=True)


def worker(directory=None):
    before=input_hashes(directory is not None);original_phase()
    if directory is None:return
    native=Native(directory);rows=[]
    for case in cases():rows.append(compare(native,case));gc.collect()
    mutants=[]
    for mutation,name in ((1,'bios-state-00'),(2,'bios-state-00'),(3,'origin-cs-alias'),(4,'bios-state-00')):
        native=Native(directory,mutation);case=next(c for c in cases() if c['name']==name)
        try:compare(native,case)
        except NativeMismatch:mutants.append(dict(mutation=mutation,case=name))
        else:fail(f'Display setup mutant{mutation} survived')
    if before!=input_hashes(True):fail('Display setup native inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),entries_each=3,boundaries_each_entry=2,null_bus_cases_each_entry_boundary=sum(r['null_repeat'] for r in rows),cases=rows,mutation_count=4,mutations_detected=mutants,translated_code_bytes=48,native_code_ranges=[[START,END]],executed_instruction_addresses=sorted({p for r in rows for p in r['sites']}),branch_edges=[],input_hashes=before,limits=dict(worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,original_instructions=32,bus_events=128,bios_calls=1),domain='4BE7 all-stateBIOS/4BF5 origins/4C07 layout sharedentries; direct8808logicalcore,actualfar+nearreturns; RAM/VGA/order/definedflags;equalCSsegmentlimitprobesdo notsettlehardwarestacklimits;intactloadedcode/sameCSBIOS/TFclear/quiescentIRQ.'))
    print(f'PASS display setup C: {len(rows)} cases x3entries x2boundaries,14 caller/24 integrated sites;4 completed mutants',flush=True)


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if sys.argv[1:]==['--original-worker']:worker();return
    if sys.argv[1:]==['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True);run_bounded([sys.executable,str(Path(__file__).resolve()),'--original-worker'],cwd=ROOT,timeout=120,memory_mib=384);return
    if len(sys.argv)!=1:raise SystemExit('Unexpected display setup arguments')
    BUILD.mkdir(exist_ok=True);REPORT.unlink(missing_ok=True)
    try:
        with temporary_build_directory(prefix='display-setup-',parent=BUILD) as directory:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=120,memory_mib=384)
    except BaseException:
        REPORT.unlink(missing_ok=True);raise
if __name__=='__main__':main()

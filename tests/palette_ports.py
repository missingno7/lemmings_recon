"""Pinned 5425/54C4 byte-port leaves; live memory, stack and provider seams."""
import ctypes
import gc
import hashlib
import random
import struct
import subprocess
import sys
import time
from array import array
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'), str(Path(__file__).resolve().parent)]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN
from unicorn import x86_const as x
import display_status as status
import video_restore as video
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json, read_json
from unpack import relocated

IMAGE, ORACLE = status.IMAGE, status.ORACLE
STARTS, ENDS, RETS = (0x5425, 0x54c4), (0x5447, 0x5507), (0x5446, 0x5506)
BLOCKS = ((0x5425, bytes.fromhex('fa8add32ed8b16da1f80c206ec52b2c08ac3eeaceefec3e2f75aecb2c0b020eefbc3')),
          (0x54c4, bytes.fromhex('57fa803e0c20ff740dba c403b001ee42ec0c20ee5052bac8038ac532e48d3e075503f832ed2e8a0547ee42aceeaceeacee4ae2f1803e0c20ff74055a5824dfeefb5fc3'.replace(' ',''))))
MD=video.MD
INS={i.address:i for p,b in BLOCKS for i in MD.disasm(b,p)}
BRANCHES={p for p,i in INS.items() if i.group(video.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(p,i.operands[0].imm&65535) for p,i in INS.items() if p in BRANCHES}
EDGES|={(p,p+i.size) for p,i in INS.items() if p in BRANCHES}
FULL, LOGIC = video.FULL, video.LOGIC
REPORT=BUILD/'palette-ports-differential.json'
ORIGINAL_REPORT=BUILD/'palette-ports-contract-original.json'


def fail(message): raise video.fixture.VerificationFailure(message)
def require(condition,message): video.require(condition,message)


class Trace:
    """Constant metadata, bounded packed flags; no per-instruction history."""
    def __init__(self,limit,native=False):
        self.limit,self.native,self.count=limit,native,0
        self.digest=hashlib.sha256();self.flags=array('H');self.masks=array('H');self.prefix=[]
    def add(self,kind,address,value,flags,mask):
        if self.count>=self.limit:
            if self.native: video.fixture.exit_worker(86,'Palette ports access budget exhausted')
            fail('Palette ports original access budget exhausted')
        self.count+=1;self.digest.update(struct.pack('<BIH',{'read':0,'write':1,'in':2,'out':3}[kind],address,value))
        self.flags.append(flags&65535);self.masks.append(mask)
        if len(self.prefix)<12:self.prefix.append((kind,address,value,flags,mask))


def cases():
    rows=[]
    def add(name,entry,**kw):
        rows.append(dict(name=name,entry=entry,seed=len(rows),**kw))
    for entry in (0,1):
        for index in range(256):
            add(f'e{entry}-index-{index:02x}',entry,index=index,count=1,df=index&1,
                base=0x3d00|index,control=0xff if index&2 else 0)
        for count in (2,3,8,16,255):
            for df in (0,1):add(f'e{entry}-n{count}-df{df}',entry,count=count,df=df,index=0xf8)
        for kind in ('sp-zero','sp-one','sp-ffff','stack-a20','source-a20','si-wrap','source-stack',
                     'provider-source','provider-stack','provider-return','ret-high-live',
                     'vga-source','vga-stack','vga-both'):
            add(f'e{entry}-{kind}',entry,kind=kind,count=2,df=1)
    for kind in ('control-ff-to-zero','control-zero-to-ff','push-before-control','table-live','table-source'):
        add(kind,1,kind=kind,count=2,control=0xff if kind=='control-ff-to-zero' else 0)
    for entry in (0,1):
        for missing in ('no-ports','no-input','no-output'):
            for control in (0,255):add(f'e{entry}-{missing}-{control}',entry,missing=missing,control=control,count=1)
    for row in rows:row.setdefault('load',video.LOADS[row['seed']%3])
    return rows


def zero_case(entry):
    return dict(name=f'e{entry}-full-zero-count',entry=entry,seed=900+entry,load=0x1010,
                count=0,index=0,control=255,df=entry,slow=True)


def prepare(case):
    rng=random.Random(0x542500+case['seed']);memory=bytearray(rng.randbytes(1<<20))
    data=relocated(IMAGE,ORACLE['relocations'],case['load']);base=case['load']<<4
    memory[base:base+len(data)]=data
    s={k:rng.randrange(65536) for k in video.REGS}
    s.update(ds=0x4000,es=0x6200,ss=0x7000,sp=0x8000,si=0x9000,
             cx=(case.get('index',7)<<8)|case.get('count',2),flags=2|((case['seed']*0x95)&0x8d5)|(((case['seed']>>1)&1)<<9)|(case.get('df',0)<<10))
    kind=case.get('kind','')
    if kind.startswith('sp-'):s['sp']={'sp-zero':0,'sp-one':1,'sp-ffff':65535}[kind]
    if kind=='stack-a20':s.update(ss=0xffff,sp=0x11)
    if kind=='source-a20':s.update(ds=0xffff,si=0xf)
    if kind=='si-wrap':s['si']=0
    if kind=='source-stack':s.update(ds=s['ss'],si=0x7ffe)
    if kind=='push-before-control':s.update(ss=s['ds'],sp=0x200e,di=0x12ff)
    if kind=='table-source':s.update(ds=case['load'],si=0x5507)
    if kind in ('vga-source','vga-both'):s['ds']=0xa000
    if kind in ('vga-stack','vga-both'):s['ss']=0xa000
    video.putword(memory,s['ss'],s['sp'],0xeed1)
    # Extra words make either direction of the live-control POP imbalance finite.
    video.putword(memory,s['ss'],(s['sp']+2)&65535,0x5aa5)
    video.putword(memory,s['ds'],0x1fda,case.get('base',0x3d4))
    memory[video.physical(s['ds'],0x200c)]=case.get('control',0)
    return memory,s


class Backend:
    def __init__(self,memory,case,initial,native=False):
        self.memory=bytearray(memory);self.case=case;self.initial=initial;self.native=native
        self.trace=Trace(600000 if case.get('slow') else 10000,native)
        self.vga=video.fixture.MinimapVga(0x542500+case['seed'],2)
        self.vga.trace=video.drawing.DeviceTrace();self.vga.seq[2]=15
        self.vga.gc[0]=self.vga.gc[1]=self.vga.gc[3]=self.vga.gc[5]=0;self.vga.gc[8]=255
        # Identical starting device bytes make RAM/VGA alias effects independently visible.
        for plane in self.vga.planes:plane[:]=self.memory[0xa0000:0xb0000]
        self.inputs=self.outputs=0;self.io=hashlib.sha256();self.changed=set();self.effect=False
        self.port_rows=[];self.mask=FULL
    def store(self,address,value):
        p=address&0xfffff;self.memory[p]=value&255;self.changed.add(p)
        if 0xa0000<=p<0xb0000:
            for plane in self.vga.planes:plane[p-0xa0000]=value&255
    def word_effect(self,seg,off,value):
        p=video.physical(seg,off);self.store(p,value);self.store(p+1,value>>8)
    def read(self,address,flags,mask):
        p=address&0xfffff;value=self.vga.read(self.memory,p,flags)
        self.trace.add('read',p,value,flags,mask)
        i=self.initial
        if self.case.get('kind')=='ret-high-live' and p==video.physical(i['ss'],i['sp']) and not self.effect:
            self.store(p+1,0x5a);self.effect=True
        return value
    def write(self,address,value,flags,mask):
        p=address&0xfffff;self.trace.add('write',p,value,flags,mask)
        self.vga.write(self.memory,p,value,flags);self.changed.add(p)
    def port(self,kind,port,value,flags,mask):
        if kind=='in':
            value=(0x93+37*self.inputs+self.case['seed'])&255;self.inputs+=1
        else:self.outputs+=1
        self.trace.add(kind,port,value,flags,mask);self.io.update(struct.pack('<BHB',kind=='out',port,value))
        if not self.case.get('slow'):self.port_rows.append((kind,port,value))
        if kind=='out':
            i=self.initial;k=self.case.get('kind')
            if self.outputs==1:
                if k=='provider-source':self.store(video.physical(i['ds'],i['si']),0xa5)
                if k=='provider-stack':
                    off=(i['sp']-2)&65535;self.word_effect(i['ss'],off,0x1234)
                if k=='provider-return':self.word_effect(i['ss'],i['sp'],0x5aa5)
                if k=='table-live':self.store(video.physical(self.case['load'],0x5507+(i['cx']>>8)+1),0xab)
            if port==0x3c9 and not self.effect:
                if k=='control-ff-to-zero':self.store(video.physical(i['ds'],0x200c),0);self.effect=True
                if k=='control-zero-to-ff':self.store(video.physical(i['ds'],0x200c),255);self.effect=True
        return value
    def bus(self):
        @video.fixture.READ
        def read(_c,_m,p,f):
            try:return self.read(p,f,FULL)
            except BaseException as e:video.fixture.exit_worker(87,f'Palette read callback:{e}')
        @video.fixture.WRITE
        def write(_c,_m,p,v,f):
            try:self.write(p,v,f,FULL)
            except BaseException as e:video.fixture.exit_worker(87,f'Palette write callback:{e}')
        self.bus_callbacks=(read,write)
        return video.fixture.RasterBus(None,read,write,video.fixture.OUT())
    def ports(self):
        @status.PORT_IN
        def inp(_c,_m,p,f):
            try:return self.port('in',p,0,f,FULL)
            except BaseException as e:video.fixture.exit_worker(87,f'Palette input callback:{e}')
        @status.PORT_OUT
        def out(_c,_m,p,v,f):
            try:self.port('out',p,v,f,FULL)
            except BaseException as e:video.fixture.exit_worker(87,f'Palette output callback:{e}')
        self.port_callbacks=(inp,out);missing=self.case.get('missing')
        return None if missing=='no-ports' else status.Ports(None,status.PORT_OUT() if missing=='no-output' else out,status.PORT_IN() if missing=='no-input' else inp)


def missing_at(case,pc):
    kind=case.get('missing')
    if not kind:return 0
    mnemonic=INS[pc].mnemonic
    if mnemonic=='in' and kind in ('no-ports','no-input'):return 1
    if mnemonic=='out' and kind in ('no-ports','no-output'):return 2
    return 0


def original(case,memory,initial,core):
    b=Backend(memory,case,initial);u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,2<<20);u.mem_write(0,bytes(memory)*2)
    entry=case['entry'];start=STARTS[entry];code_seg=case['load'];ret=RETS[entry]
    for k,v in dict(initial,cs=code_seg,ip=start).items():u.reg_write(x.UC_X86_REG_EFLAGS if k=='flags' else video.drawing.oracle.REG[k],v)
    values={video.physical(code_seg,p+n):IMAGE[p+n] for p,i in INS.items() for n in range(i.size)}
    if any(memory[p]!=v for p,v in values.items()):fail('Palette writer entered modified decoded code')
    mask=FULL;event_flags=initial['flags'];previous=None;done=False;st=0;steps=loops=0;sites=set();edges=set();errors=[]
    def error(e):
        if not errors:errors.append(str(e))
        u.emu_stop()
    def sync():
        for p in b.changed:
            if p in values and b.memory[p]!=values[p]:fail('Palette provider modified decoded instructions')
            byte=bytes((b.memory[p],));u.mem_write(p,byte);u.mem_write(p+(1<<20),byte)
        b.changed.clear()
    def code(uc,_p,_size,_c):
        nonlocal previous,mask,event_flags,done,st,steps,loops
        off=uc.reg_read(x.UC_X86_REG_IP)
        if previous is not None:mask=video.drawing.render._defined_mask(INS[previous].mnemonic,mask)
        if previous==ret:done=True;uc.emu_stop();return
        if previous in BRANCHES:edges.add((previous,off))
        if uc.reg_read(x.UC_X86_REG_CS)!=code_seg or not start<=off<ENDS[entry] or off not in INS:error('Palette writer escaped');return
        st=missing_at(case,off)
        if st or (core and off==ret):done=True;uc.emu_stop();return
        steps+=1
        if steps>(1200000 if case.get('slow') else 10000):error('Palette instruction budget exhausted');return
        if off in (0x543c,0x54f6):loops+=1
        sites.add(off);previous=off;event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS)
    def read(uc,_a,address,size,_v,_c):
        try:
            for n in range(size):uc.mem_write(address+n,bytes((b.read(address+n,event_flags,mask),)))
            sync()
        except BaseException as e:error(e)
    def write(_uc,_a,address,size,value,_c):
        try:
            for n in range(size):b.write(address+n,(value>>(8*n))&255,event_flags,mask)
            sync()
        except BaseException as e:error(e)
    def inp(_uc,port,size,_c):
        try:
            if size!=1:fail('Palette input width differs')
            v=b.port('in',port,0,event_flags,mask);sync();return v
        except BaseException as e:error(e);return 0
    def out(_uc,port,size,value,_c):
        try:
            if size!=1:fail('Palette output width differs')
            b.port('out',port,value,event_flags,mask);sync()
        except BaseException as e:error(e)
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,read);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.hook_add(UC_HOOK_INSN,inp,None,1,0,x.UC_X86_INS_IN);u.hook_add(UC_HOOK_INSN,out,None,1,0,x.UC_X86_INS_OUT)
    u.emu_start((code_seg<<4)+start,0,count=1200001 if case.get('slow') else 10001)
    if errors:fail(case['name']+': '+errors[0])
    if not done:fail(case['name']+': original did not finish')
    regs={k:u.reg_read(x.UC_X86_REG_EFLAGS if k=='flags' else video.drawing.oracle.REG[k])&65535 for k in (*video.REGS,'cs','ip')}
    return b,regs,mask,st,sites,edges,loops


def independent(case,memory,s,b,r,core):
    """Normal disjoint RAM cases: closed-form stream, counters, saves and cursor."""
    def check(condition,message):
        if not condition:fail(message)
    if case.get('kind') or case.get('missing'):return
    entry=case['entry'];n=case.get('count',2) or 65536;index=s['cx']>>8;direction=-1 if s['flags']&0x400 else 1
    expected=hashlib.sha256();inputs=outputs=0
    def emit(kind,p,v):
        nonlocal inputs,outputs
        expected.update(struct.pack('<BHB',kind=='out',p,v))
        if kind=='in':inputs+=1
        else:outputs+=1
    def inp(p):
        v=(0x93+37*inputs+case['seed'])&255;emit('in',p,v);return v
    work=bytearray(memory);sp=s['sp']
    if entry==0:
        base=case.get('base',0x3d4);status_port=(base&0xff00)|((base+6)&255);port=(base&0xff00)|0xc0
        inp(status_port);video.putword(work,s['ss'],(sp-2)&65535,status_port)
        for k in range(n):
            emit('out',port,(index+k)&255);emit('out',port,memory[video.physical(s['ds'],(s['si']+direction*k)&65535)])
        inp(status_port);emit('out',port,0x20)
        check(r['ax']==((s['ax']&0xff00)|0x20) and r['bx']==((s['bx']&0xff00)|((index+n)&255)) and r['dx']==port,'Independent attribute registers differ')
    else:
        video.putword(work,s['ss'],(sp-2)&65535,s['di'])
        if case.get('control',0)!=255:
            emit('out',0x3c4,1);saved=(s['ax']&0xff00)|(inp(0x3c5)|0x20);emit('out',0x3c5,saved&255)
            video.putword(work,s['ss'],(sp-4)&65535,saved);video.putword(work,s['ss'],(sp-6)&65535,0x3c5)
        for k in range(n):
            emit('out',0x3c8,memory[video.physical(case['load'],(0x5507+index+k)&65535)])
            for j in range(3):emit('out',0x3c9,memory[video.physical(s['ds'],(s['si']+direction*(3*k+j))&65535)])
        if case.get('control',0)!=255:emit('out',0x3c5,(saved&255)&0xdf)
        check(r['di']==s['di'] and r['bx']==s['bx'],'Independent DAC registers differ')
    check((b.inputs,b.outputs,b.io.hexdigest())==(inputs,outputs,expected.hexdigest()),'Independent port stream differs')
    check(b.memory==work,'Independent stack memory differs')
    check(r['si']==(s['si']+direction*n*(1 if entry==0 else 3))&65535 and r['cx']==0,'Independent count/cursor differs')
    check(r['sp']==(sp+(0 if core else 2))&65535 and r['flags']&0x200,'Independent SP/STI differs')


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ctypes.CDLL(str(build(Path(directory)/f'palette-ports-m{mutation}.dll',mutation,'palette_ports')))
        self.core=self.lib.lmn_write_palette_ports_core
        self.core.argtypes=[video.MEM,ctypes.c_uint16,ctypes.POINTER(video.State),ctypes.c_int,ctypes.POINTER(status.Ports),ctypes.POINTER(video.fixture.RasterBus)];self.core.restype=video.Result
        self.adapter=self.lib.lmn_write_palette_ports_adapter
        self.adapter.argtypes=[video.MEM,ctypes.POINTER(video.Regs),ctypes.c_int,ctypes.POINTER(status.Ports),ctypes.POINTER(video.fixture.RasterBus)];self.adapter.restype=None


def compare(native,case):
    rows=[]
    for core in ((True,) if case.get('slow') else (False,True)):
        memory,s=prepare(case);b,r,mask,st,sites,edges,loops=original(case,memory,s,core)
        independent(case,memory,s,b,r,core)
        if not st and loops!=(case.get('count',2) or 65536):fail('Original LOOP count differs')
        kind=case.get('kind')
        if kind in ('control-ff-to-zero','control-zero-to-ff'):
            delta=4 if kind=='control-ff-to-zero' else -4
            expected_sp=(s['sp']+delta+(0 if core else 2))&65535
            if not b.effect or r['sp']!=expected_sp:fail('Live control stack imbalance was not exercised')
        if kind=='provider-stack' and case['entry']==1 and r['di']!=0x1234:fail('Live savedDI was not exercised')
        if kind=='table-live' and not any(k=='out' and p==0x3c8 and v==0xab for k,p,v in b.port_rows):fail('Live second table byte was not exercised')
        if native:
            null_ok=not(case.get('kind') in ('ret-high-live','vga-source','vga-stack','vga-both'))
            for null in ((False,) if case.get('slow') or not null_ok else (False,True)):
                d=Backend(memory,case,s,True);bus=d.bus();ports=d.ports()
                if core:
                    out=native.core(video.buffer(d.memory),case['load'],ctypes.byref(video.to_state(s)),case['entry'],video.pointer(ports),None if null else ctypes.byref(bus))
                    got=dict(video.state_dict(out.state),cs=case['load'],ip=out.continuation)
                    require(out.status==st,case['name']+': status differs')
                else:
                    regs=video.Regs(**s,cs=case['load'],ip=STARTS[case['entry']]);native.adapter(video.buffer(d.memory),ctypes.byref(regs),case['entry'],video.pointer(ports),None if null else ctypes.byref(bus))
                    got={k:getattr(regs,k) for k in (*video.REGS,'cs','ip')}
                require(all(got[k]==r[k] for k in (*video.REGS[:-1],'cs','ip')) and not((got['flags']^r['flags'])&mask),case['name']+': CPU/flags differ')
                require(d.memory==b.memory and d.vga.state()==b.vga.state(),case['name']+': RAM/VGA differs')
                require((d.inputs,d.outputs,d.io.hexdigest())==(b.inputs,b.outputs,b.io.hexdigest()),case['name']+': port stream differs')
                if not null:
                    require(d.trace.count==b.trace.count and d.trace.digest.digest()==b.trace.digest.digest(),case['name']+': bus order differs')
                    require(not any((a^v)&m for a,v,m in zip(d.trace.flags,b.trace.flags,b.trace.masks)),case['name']+': phase flags differ')
        rows.append(dict(core=core,loops=loops,sites=sorted(sites),edges=sorted(edges),events=b.trace.count,inputs=b.inputs,outputs=b.outputs,status=st))
    return dict(name=case['name'],boundaries=rows)


def input_hashes(native=False):
    paths=set(video.input_hashes(False))|{'tests/palette_ports.py','tests/display_status.py','docs/palette-ports.md','docs/palette-pointer-frontier.md','c/aligned_read_mask.h'}
    if native:paths|={'c/palette_ports.c','c/palette_ports.h','c/lemmings_sym.h','tools/cbuild.py','tools/difftest.py','tools/coverage.py'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def worker(directory=None,zero=None):
    video.fixture.MAX_VGA_EVENTS=10000
    if any(IMAGE[p:p+len(code)]!=code for p,code in BLOCKS) or len(INS)!=61:fail('Pinned palette port bytes/boundaries differ')
    before=input_hashes(directory is not None);native=Native(directory) if directory else None
    rows=[]
    for case in ([zero_case(zero)] if zero is not None else cases()):
        rows.append(compare(native,case));gc.collect()
    sites={p for r in rows for b in r['boundaries'] for p in b['sites']};edges={tuple(e) for r in rows for b in r['boundaries'] for e in b['edges']}
    mutants=[]
    if zero is None:
        if sites!=set(INS) or edges!=EDGES:fail(f'Palette coverage incomplete {set(INS)-sites}/{EDGES-edges}')
        if native:
            for mutation,name in ((1,'e0-index-fa'),(2,'e0-n2-df1'),(3,'control-zero-to-ff'),(4,'provider-stack'),(5,'e0-index-00'),(6,'e1-index-10')):
                # Mutant4 applies only to mappedDAC, and the savedDI must change.
                case=next(c for c in cases() if c['name']==('e1-provider-stack' if mutation==4 else name))
                try:compare(Native(directory,mutation),case)
                except video.NativeMismatch as error:mutants.append(dict(mutation=mutation,case=case['name'],reason=str(error),completed=True))
                else:fail(f'Palette port mutant{mutation} survived')
    if before!=input_hashes(directory is not None):fail('Palette port inputs changed')
    name='normal' if zero is None else f'zero-{zero}'
    path=Path(directory)/(name+'.json') if directory else BUILD/f'palette-ports-original-{name}.json'
    write_json(path,dict(cases=rows,sites=sorted(sites),edges=sorted(edges),mutants=mutants,input_hashes=before))
    print(f'PASS palette ports {name}: {len(rows)} fixtures,{len(mutants)} mutants',flush=True)


def run(original_only=False):
    report=ORIGINAL_REPORT if original_only else REPORT;report.unlink(missing_ok=True);before=input_hashes(not original_only);deadline=time.monotonic()+330
    try:
        with temporary_build_directory(prefix='palette-ports-',parent=BUILD) as directory:
            reports=[]
            for zero in (None,0,1):
                remain=deadline-time.monotonic()-10
                if remain<=0:fail('Palette port campaign deadline exhausted')
                run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker','-' if original_only else directory,'-' if zero is None else str(zero)],cwd=ROOT,timeout=min(150,remain),memory_mib=384)
                name='normal' if zero is None else f'zero-{zero}'
                reports.append(read_json(BUILD/f'palette-ports-original-{name}.json' if original_only else Path(directory)/(name+'.json')))
        if any(r['input_hashes']!=before for r in reports) or input_hashes(not original_only)!=before:fail('Palette port report stale')
        write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(cases())+2,boundary_fixtures=len(cases()),zero_count_core_cases=2,
            cases=[c for r in reports for c in r['cases']],executed_instruction_addresses=reports[0]['sites'],branch_edges=reports[0]['edges'],
            mutation_count=len(reports[0]['mutants']),mutations_detected=reports[0]['mutants'],translated_code_bytes=0 if original_only else 101,
            native_code_ranges=[] if original_only else [[a,z] for a,z in zip(STARTS,ENDS)],c_coverage_claimed=not original_only,input_hashes=before,
            limits=dict(campaign_seconds=330,worker_seconds=150,windows_process_mib=384,windows_tree_mib=640,zero_instruction_budget=1200000,bus_events=600000),
            domain='Two byte-port leaves, canonical RAM/VGA bus, allCH values, DF/LOOP/live saves/control reread/provider effects, fullRAM/allCPU/phaseflags/orderedevents; intact decoded instructions, sameCS, TFclear and quiescentIRQs; no hardware timing, palette register model or segment-limit claim. Unknown CS index bytes remain unresolved.'))
        print(f'PASS palette ports {"original" if original_only else "C"}: {len(cases())} x2 fixtures +2 fullzeroCL corecases,61sites,{len(EDGES)}edges,{len(reports[0]["mutants"])}mutants',flush=True)
    except BaseException:report.unlink(missing_ok=True);raise


if __name__=='__main__':
    args=sys.argv[1:]
    if len(args)==3 and args[0]=='--worker':worker(None if args[1]=='-' else args[1],None if args[2]=='-' else int(args[2]))
    elif args==['--original-only']:run(True)
    elif not args:run()
    else:raise SystemExit('Unexpected palette port arguments')

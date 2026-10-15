"""5569 live pointer prefix, exact tail connection to native palette rows."""
import ctypes
import gc
import random
import subprocess
import sys
import time
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
import palette_rows as rows
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import ROOT,BUILD,sha,write_json,read_json
from unpack import relocated

channels,common,video,oracle=rows.channels,rows.common,rows.video,rows.oracle
IMAGE,ORACLE=rows.IMAGE,rows.ORACLE
START,END=0x5569,0x55b6
CODE=bytes.fromhex('833e7c1f0474231e078ac332e403c08d36d45203f02e8b348ac732e403c08d3ed45203f82e8b3de9ab001e078ac332e403c08d36e45203f02e8b348ac732e403c08d3ee45203f82e8b3de92c01')
LOCAL={i.address:i for i in video.MD.disasm(CODE,START)}
INS=LOCAL|rows.INS
BRANCHES={p for p,i in INS.items() if i.group(video.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
LOCAL_EDGES={(p,i.operands[0].imm&65535) for p,i in LOCAL.items() if p in BRANCHES}
LOCAL_EDGES|={(p,p+i.size) for p,i in LOCAL.items() if p in BRANCHES and i.mnemonic!='jmp'}
REPORT=BUILD/'palette-row-select-differential.json';ORIGINAL_REPORT=BUILD/'palette-row-select-contract-original.json'


def fail(message):raise common.VerificationFailure(message)


def cases():
    specs=[]
    def add(name,mode=2,**kw):specs.append(dict(name=name,mode=mode,seed=len(specs),**kw))
    for mode in (2,4):
        for index in range(256):add(f'm{mode}-raw-index-{index:02x}',mode,bl=index,bh=(index*73+19)&255,count=1,raw=True,independent=True,df=index&1)
        for count in (2,3,16,255):
            for df in (0,1):add(f'm{mode}-n{count}-df{df}',mode,count=count,df=df,independent=True)
        for kind in ('sp-zero','sp-one','sp-ffff','stack-a20','data-a20','cursor-wrap',
                     'vga-data','vga-stack','vga-both','pop-es','pop-es-low-high',
                     'source-word-high','target-word-high','source-read-target-write',
                     'push-source-alias','push-target-alias','outer-ret-high','source-return-alias'):
            add(f'm{mode}-{kind}',mode,kind=kind,count=2)
    for mode in (0,1,3,5,0x104,0xff04,0x400,0xffff,0x7fff,0x8000,0x8003,0x8004):add(f'mode-{mode:04x}',mode,independent=True,count=1)
    add('mode-low-high',4,kind='mode-low-high',count=1)
    add('zero-live-counter',2,kind='zero-live-counter',count=0)
    for mode,ret,delta,st in ((2,0x564e,-4,2),(2,0x5657,-4,2),(2,0x5660,-4,2),
            (2,0x567c,-6,1),(2,0x5691,-6,1),(4,0x56ed,-2,2),(4,0x56f8,-2,2),(4,0x5703,-2,2)):
        add(f'changed-{ret:04x}',mode,change_frame=(ret,delta),status=st,kind='vga-stack',count=1)
    return specs


def zero_case(mode):
    return dict(name=f'm{mode}-full-zero-count',mode=mode,seed=900+mode,count=0,zero=True,independent=True,df=mode==4)


def prepare(case):
    rng=random.Random(0x556900+case['seed']);load=video.LOADS[case['seed']%3]
    memory=bytearray(rng.randbytes(1<<20));loaded=relocated(IMAGE,ORACLE['relocations'],load)
    memory[load<<4:(load<<4)+len(loaded)]=loaded
    regs={k:rng.randrange(65536) for k in oracle.REG_NAMES}
    regs.update(cs=load,ip=START,ds=0x3000 if case.get('zero') else 0x4000,es=0x6000,
                ss=0x7000,sp=0x8000,bx=(case.get('bh',1)<<8)|case.get('bl',0),cx=0xa500|case.get('count',2))
    flags=2|((case['seed']*0x95^0xad5)&0xad5)|(0x400 if case.get('df') else 0)
    kind=case.get('kind')
    if kind in ('sp-zero','sp-one','sp-ffff'):regs['sp']={'sp-zero':0,'sp-one':1,'sp-ffff':65535}[kind]
    if kind=='stack-a20':regs.update(ss=0xffff,sp=0xf)
    if kind=='data-a20':regs['ds']=0xffff
    if kind in ('vga-data','vga-both'):regs['ds']=0xa000
    if kind in ('vga-stack','vga-both'):regs['ss']=0xa000
    if kind in ('source-return-alias','zero-live-counter'):regs.update(ds=0x4000,ss=0x4000)
    base=0x52e4 if case['mode']==4 else 0x52d4
    if kind in ('push-source-alias','push-target-alias'):regs.update(ss=load,sp=base+(2 if kind=='push-source-alias' else 4))
    source,target=(0x1000,0x1000) if case.get('zero') else (0x1000,0x2000)
    if kind=='cursor-wrap':source,target=0xffff,0xfffd
    if kind=='data-a20':source,target=0xf,0x21
    if kind=='source-return-alias':source=regs['sp']
    if kind=='zero-live-counter':source=(regs['sp']-2)&65535
    if case.get('zero'):
        for n in range(65536):memory[video.physical(regs['ds'],n)]=0
    if not case.get('raw'):
        for table in (0x52d4,0x52e4):
            video.putword(memory,load,table,source);video.putword(memory,load,table+2,target)
    video.putword(memory,regs['ds'],0x1f7c,case['mode'])
    if kind=='source-return-alias':
        for n in range(6):memory[video.physical(regs['ds'],target+n)]=0
    if kind=='zero-live-counter':
        for n in range(8):memory[video.physical(regs['ds'],target+n)]=9 if n==0 else 0
    video.putword(memory,regs['ss'],regs['sp'],0xeed1)
    return memory,regs,flags


class Device(common.TraceDevice):
    def __init__(self,memory,case,regs):
        super().__init__(bytearray(memory),0x556900+case['seed'])
        self.changed=set();self.effect=False;self.frame_hits=0
        for plane in self.vga.planes:plane[:]=self.memory[0xa0000:0xb0000]
        original_read,original_write=self.vga.read,self.vga.write
        source_word=video.physical(regs['cs'],(0x52e4 if case['mode']==4 else 0x52d4)+2*(regs['bx']&255))
        target_word=video.physical(regs['cs'],(0x52e4 if case['mode']==4 else 0x52d4)+2*(regs['bx']>>8))
        saved=video.physical(regs['ss'],(regs['sp']-2)&65535);outer=video.physical(regs['ss'],regs['sp'])
        def put(p,v):
            p&=0xfffff;self.memory[p]=v&255;self.changed.add(p)
            if 0xa0000<=p<0xb0000:
                for plane in self.vga.planes:plane[p-0xa0000]=v&255
        def read(mem,p,f):
            kind=case.get('kind');p&=0xfffff
            if not self.effect and kind=='pop-es' and p==saved and oracle.get16(self.memory,regs['ss'],(regs['sp']-2)&65535)==regs['ds']:
                put(p,0x34);put(p+1,0x12);self.effect=True
            value=original_read(mem,p,f)
            if not self.effect:
                target=(video.physical(regs['ds'],0x1f7c) if kind=='mode-low-high' else
                        source_word if kind in ('source-word-high','source-read-target-write') else
                        target_word if kind=='target-word-high' else saved if kind=='pop-es-low-high' else
                        outer if kind=='outer-ret-high' else None)
                if p==target:
                    if kind=='source-read-target-write':put(target_word,0);put(target_word+1,0x30)
                    else:put(p+1,{'mode-low-high':1,'source-word-high':0x11,'target-word-high':0x21,'pop-es-low-high':0x12,'outer-ret-high':0x5a}[kind])
                    self.effect=True
            return value
        def write(mem,p,v,f):
            original_write(mem,p,v,f);self.changed.add(p&0xfffff)
            if case.get('change_frame'):
                ret,delta=case['change_frame'];at=video.physical(regs['ss'],(regs['sp']+delta)&65535)
                if p==at and v==(ret&255):put(p,1);self.frame_hits+=1
        self.vga.read,self.vga.write=read,write
        # This fixture deliberately supplies effects on ordinary RAM as well
        # as VGA. TraceDevice's default fast RAM path bypasses vga.read/write.
        def guard():
            if self.events.exhausted or len(self.vga.trace)>common.MAX_VGA_EVENTS:
                common.exit_worker(86,f'{case["name"]}: pointer access/VGA budget exhausted events={self.events.count}')
        @common.READ
        def bus_read(_c,_m,p,f):
            try:
                p&=0xfffff;value=self.vga.read(self.memory,p,f)
                self.events.add('read',p,value,f);guard();return value
            except BaseException as e:common.exit_worker(87,f'Pointer read callback:{e}')
        @common.WRITE
        def bus_write(_c,_m,p,v,f):
            try:
                p&=0xfffff;self.vga.write(self.memory,p,v,f)
                self.events.add('write',p,v,f);guard()
            except BaseException as e:common.exit_worker(87,f'Pointer write callback:{e}')
        self.pointer_callbacks=(bus_read,bus_write)
        self.bus=common.RasterBus(None,bus_read,bus_write,common.OUT())


def defined_after(pc,mask):
    if pc not in LOCAL:return rows.defined_after(pc,mask)
    return channels.LOGIC if LOCAL[pc].mnemonic=='xor' else channels.FULL if LOCAL[pc].mnemonic in ('cmp','add') else mask


def original(case,device,regs,flags,core):
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,2<<20);u.mem_write(0,bytes(device.memory)*2)
    for n,r in oracle.REG.items():u.reg_write(r,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags)
    loaded=relocated(IMAGE,ORACLE['relocations'],regs['cs'])
    values={video.physical(regs['cs'],p+n):loaded[p+n] for p,i in INS.items() for n in range(i.size)}
    if any(device.memory[p]!=v for p,v in values.items()):fail('Pointer prefix entered modified code')
    previous=None;mask=channels.FULL;event_flags=flags;frames=[];pending=None;boundary=None;errors=[]
    sites=set();edges=set();steps=loops=0;first_pop=None;prefix=None;prefix_memory=None
    def error(e):
        if not errors:errors.append(str(e))
        u.emu_stop()
    def sync():
        for p in device.changed:
            if p in values and device.memory[p]!=values[p]:fail('Pointer fixture changed decoded instructions')
            b=bytes((device.memory[p],));u.mem_write(p,b);u.mem_write(p+(1<<20),b)
        device.changed.clear()
    def code(uc,_p,_s,_c):
        nonlocal previous,mask,event_flags,pending,boundary,steps,loops,first_pop,prefix,prefix_memory
        off=uc.reg_read(x.UC_X86_REG_IP);cs=uc.reg_read(x.UC_X86_REG_CS)
        if previous is not None:mask=defined_after(previous,mask)
        if pending is not None:
            expected=pending;pending=None
            if expected is False:boundary=('outer-return',cs,off);uc.emu_stop();return
            frames.pop()
            if (cs,off)!=expected:boundary=('changed-child-near',cs,off);uc.emu_stop();return
        if previous in BRANCHES:edges.add((previous,off))
        if cs!=regs['cs'] or off not in INS:error('Pointer caller escaped');return
        if core and off in rows.RETURNS:boundary=('ready-return',cs,off);uc.emu_stop();return
        steps+=1
        if steps>(12000000 if case.get('zero') else 100000):error('Pointer instruction budget exhausted');return
        if off in rows.ENTRIES and prefix is None:
            prefix={n:uc.reg_read(r) for n,r in oracle.REG.items()};prefix['flags']=uc.reg_read(x.UC_X86_REG_EFLAGS)
            prefix_memory=bytes(device.memory)
        if off in (0x5642,0x56e6):loops+=1
        if off==0x5665 and first_pop is None:first_pop=uc.reg_read(x.UC_X86_REG_CX)
        i=INS[off];sites.add(off);previous=off;event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        if i.mnemonic=='call':frames.append((cs,off+i.size))
        if i.mnemonic=='ret':pending=frames[-1] if frames else False
    def read(uc,_a,address,size,_v,_c):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;value=device.vga.read(device.memory,p,event_flags)
                device.events.add('read',p,value,event_flags,mask);uc.mem_write(address+n,bytes((value,)));sync()
            device.check('Pointer original read')
        except BaseException as e:error(e)
    def write(_uc,_a,address,size,value,_c):
        try:
            for n in range(size):
                p=(address+n)&0xfffff;v=(value>>(8*n))&255
                if p in values and v!=values[p]:fail('Pointer stack changed decoded code')
                device.vga.write(device.memory,p,v,event_flags);device.events.add('write',p,v,event_flags,mask);sync()
            device.check('Pointer original write')
        except BaseException as e:error(e)
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,read);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.emu_start((regs['cs']<<4)+START,0,count=12000001 if case.get('zero') else 100001)
    if errors:fail(case['name']+': '+errors[0])
    if boundary is None or prefix is None:fail('Pointer original did not reach a declared boundary')
    result={n:u.reg_read(r) for n,r in oracle.REG.items()};result['flags']=u.reg_read(x.UC_X86_REG_EFLAGS)
    return result,mask,sites,edges,boundary,loops,first_pop,prefix,prefix_memory


def independent(case,memory,regs,flags,result,prefix,prefix_memory,device,core):
    if not case.get('independent'):return
    expected=bytearray(memory);mode=oracle.get16(memory,regs['ds'],0x1f7c);base=0x52e4 if mode==4 else 0x52d4
    before=dict(regs,flags=flags);video.putword(expected,regs['ss'],(regs['sp']-2)&65535,regs['ds'])
    before.update(es=regs['ds'],ax=2*(regs['bx']>>8),si=oracle.get16(memory,regs['cs'],base+2*(regs['bx']&255)),
                  di=oracle.get16(memory,regs['cs'],base+2*(regs['bx']>>8)),ip=rows.ENTRIES[mode==4])
    left,right=base,before['ax'];v=(left+right)&65535
    f=(4 if (v&255).bit_count()%2==0 else 0)|(0x40 if not v else 0)|(0x80 if v&0x8000 else 0)
    f|=(1 if left+right>65535 else 0)|(0x10 if (left^right^v)&16 else 0)|(0x800 if (~(left^right)&(left^v)&0x8000) else 0)
    before['flags']=(flags&~channels.ARITH)|f
    if any(before[n]!=prefix[n] for n in oracle.REG_NAMES) or (before['flags']^prefix['flags'])&channels.FULL or expected!=prefix_memory:
        fail(case['name']+': independent pointer prefix differs')
    child=dict(case,entry=int(mode==4));expected,state,iterations=rows.independent(child,bytearray(prefix_memory),{n:prefix[n] for n in oracle.REG_NAMES},prefix['flags'])
    if not core:state.update(sp=(regs['sp']+2)&65535,ip=oracle.get16(device.memory,regs['ss'],regs['sp']))
    if expected!=device.memory or any(state[n]!=result[n] for n in oracle.REG_NAMES) or (state['flags']^result['flags'])&channels.LOGIC:
        fail(case['name']+': independent row composition differs')
    return iterations


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ctypes.CDLL(str(build(Path(directory)/f'palette-row-select-m{mutation}.dll',mutation,'palette_row_select')))
        self.core=self.lib.lmn_select_and_step_palette_row_core
        self.core.argtypes=[video.MEM,ctypes.c_uint16,ctypes.POINTER(video.State),ctypes.POINTER(common.RasterBus)];self.core.restype=channels.Result
        self.adapter=self.lib.lmn_select_and_step_palette_row_adapter
        self.adapter.argtypes=[video.MEM,ctypes.POINTER(video.Regs),ctypes.POINTER(common.RasterBus)];self.adapter.restype=None


def compare(native,case,core):
    memory,regs,flags=prepare(case);b=Device(memory,case,regs)
    actual,mask,sites,edges,boundary,loops,first_pop,prefix,prefix_memory=original(case,b,regs,flags,core)
    independent(case,memory,regs,flags,actual,prefix,prefix_memory,b,core)
    kind=case.get('kind')
    if case.get('change_frame'):
        if boundary!=('changed-child-near',regs['cs'],(case['change_frame'][0]&0xff00)|1) or b.frame_hits!=1:fail('Changed child frame was not exercised')
    elif kind=='zero-live-counter':
        if (loops,first_pop)!=(8,8):fail('Zero savedCX alias was not exercised')
    elif loops!=(case.get('count',2) or 65536):fail('Pointer LOOP count differs')
    expected_prefix={'pop-es':('es',0x1234),'pop-es-low-high':('es',0x1200),'source-word-high':('si',0x1100),
                     'target-word-high':('di',0x2100),'source-read-target-write':('di',0x3000),'mode-low-high':('ip',rows.ENTRIES[0]),
                     'push-source-alias':('si',regs['ds']),'push-target-alias':('di',regs['ds'])}
    if kind in expected_prefix:
        k,v=expected_prefix[kind]
        if prefix[k]!=v:fail(case['name']+': live prefix witness absent '+str((k,prefix[k],v)))
    if kind=='outer-ret-high' and not core and actual['ip']!=0x5ad1:fail('Live outerRET high byte not exercised')
    if kind=='source-return-alias' and not core and actual['ip']==0xeed1:fail('Row store did not change outerRET')
    if native:
        fallback=not(kind in ('vga-data','vga-stack','vga-both','pop-es','pop-es-low-high','source-word-high','target-word-high','source-read-target-write','mode-low-high','outer-ret-high') or case.get('change_frame'))
        for null in ((False,) if case.get('zero') or not fallback else (False,True)):
            d=Device(memory,case,regs);bus=None if null else ctypes.byref(d.bus)
            if core:
                out=native.core(video.buffer(d.memory),regs['cs'],ctypes.byref(video.to_state(dict(regs,flags=flags))),bus)
                got=dict(video.state_dict(out.state),cs=out.code_segment,ip=out.continuation)
                common.require(out.status==case.get('status',0),case['name']+': status differs')
            else:
                r=video.Regs(**regs,flags=flags);native.adapter(video.buffer(d.memory),ctypes.byref(r),bus)
                got={n:getattr(r,n) for n in (*oracle.REG_NAMES,'flags')}
            common.require(all(got[n]==actual[n] for n in oracle.REG_NAMES) and not((got['flags']^actual['flags'])&mask),case['name']+': CPU/flags differ '+str({n:(got[n],actual[n]) for n in (*oracle.REG_NAMES,'flags') if got[n]!=actual[n]})+f' core={core} null={null}')
            common.require(d.memory==b.memory and d.vga.state()==b.vga.state(),case['name']+': RAM/VGA differs')
            if not null:common.compare_event_traces(d.events,b.events,case['name'])
    return dict(name=case['name'],core=core,loops=loops,sites=sorted(sites),edges=sorted(edges),boundary=boundary,events=b.events.count)


def input_hashes(native=False):
    paths=set(rows.input_hashes(native))|{'tests/palette_row_select.py','docs/palette-row-select.md','docs/palette-pointer-frontier.md'}
    if native:paths|={'c/palette_row_select.c','c/palette_row_select.h'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def worker(directory=None,zero=None):
    common.MAX_BUS_EVENTS=2000000 if zero is not None else 25000;common.MAX_VGA_EVENTS=10000
    channels.identity()
    if IMAGE[START:END]!=CODE or len(LOCAL)!=32:fail('Pinned pointer prefix bytes/boundaries differ')
    before=input_hashes(directory is not None);native=Native(directory) if directory else None;results=[]
    for case in ([zero_case(zero)] if zero is not None else cases()):
        for core in ((True,) if zero is not None else (False,True)):results.append(compare(native,case,core))
        gc.collect()
    sites={p for r in results for p in r['sites']};edges={tuple(e) for r in results for e in r['edges']};mutants=[]
    if zero is None:
        if sites!=set(INS) or not (LOCAL_EDGES|rows.EDGES|channels.EDGES)<=edges:fail(f'Pointer coverage incomplete {set(INS)-sites}/{(LOCAL_EDGES|rows.EDGES|channels.EDGES)-edges}')
        if native:
            for mutation,name,core in ((1,'mode-0104',True),(2,'m2-raw-index-08',True),(3,'m4-n2-df0',True),
                    (4,'m2-pop-es',True),(5,'m2-push-target-alias',True),(6,'m4-source-return-alias',False),(7,'changed-564e',True)):
                case=next(c for c in cases() if c['name']==name)
                try:compare(Native(directory,mutation),case,core)
                except common.Mismatch as e:mutants.append(dict(mutation=mutation,case=name,reason=str(e),completed=True))
                else:fail(f'Palette row select mutant{mutation} survived')
    if before!=input_hashes(directory is not None):fail('Pointer verification inputs changed')
    name='normal' if zero is None else f'zero-{zero}'
    path=Path(directory)/(name+'.json') if directory else BUILD/f'palette-row-select-original-{name}.json'
    write_json(path,dict(cases=results,sites=sorted(sites),edges=sorted(edges),mutants=mutants,input_hashes=before))
    print(f'PASS palette row select {name}: {len(results)} boundaries,{len(mutants)}mutants',flush=True)


def run(original_only=False):
    report=ORIGINAL_REPORT if original_only else REPORT;report.unlink(missing_ok=True);before=input_hashes(not original_only);deadline=time.monotonic()+660
    try:
        with temporary_build_directory(prefix='palette-row-select-',parent=BUILD) as directory:
            reports=[]
            for zero in (None,2,4):
                remain=deadline-time.monotonic()-10
                if remain<=0:fail('Pointer campaign deadline exhausted')
                run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker','-' if original_only else directory,'-' if zero is None else str(zero)],cwd=ROOT,timeout=min(240,remain),memory_mib=384)
                name='normal' if zero is None else f'zero-{zero}'
                reports.append(read_json(BUILD/f'palette-row-select-original-{name}.json' if original_only else Path(directory)/(name+'.json')))
        if input_hashes(not original_only)!=before or any(r['input_hashes']!=before for r in reports):fail('Pointer reports stale')
        write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(cases())+2,boundary_fixtures=len(cases()),zero_count_core_cases=2,
            cases=[c for r in reports for c in r['cases']],caller_sites=32,caller_bytes=77,translated_code_bytes=0 if original_only else 77,
            native_code_ranges=[] if original_only else [[START,END]],caller_instruction_addresses=sorted(LOCAL),executed_instruction_addresses=reports[0]['sites'],
            caller_branch_edges=sorted(LOCAL_EDGES),branch_edges=reports[0]['edges'],mutation_count=len(reports[0]['mutants']),mutations_detected=reports[0]['mutants'],input_hashes=before,c_coverage_claimed=not original_only,
            limits=dict(campaign_seconds=660,worker_seconds=240,windows_process_mib=384,windows_tree_mib=640,zero_instructions=12000000,zero_bus_events=2000000),
            domain='5569..55B5 prefix and direct row/channel tails: independent prefix/fullRAM/data/marker model, allBL/BHvalues, fullwordmode, livePUSHDS/POPES/tablewordeffects, actualRET/status/flags andRAM/VGA; two full65536iterationzeroCL cores. Intactdecodedinstructions/sameCS/TFclear/quiescentIRQ; UNKNOWN tables and buffer ownership remain open.'))
        print(f'PASS palette row select {"original" if original_only else "C"}: {len(cases())} x2fixtures +2fullzeroCLcores,32caller/{len(reports[0]["sites"])}integratedsites,{len(reports[0]["mutants"])}mutants',flush=True)
    except BaseException:report.unlink(missing_ok=True);raise


if __name__=='__main__':
    args=sys.argv[1:]
    if len(args)==3 and args[0]=='--worker':worker(None if args[1]=='-' else args[1],None if args[2]=='-' else int(args[2]))
    elif args==['--original-only']:run(True)
    elif not args:run()
    else:raise SystemExit('Unexpected palette row select arguments')

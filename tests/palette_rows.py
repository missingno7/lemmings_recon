"""Live packed/RGB palette rows, native channel composition and bounded zero loops."""
import ctypes
import gc
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'tools'), str(Path(__file__).resolve().parent)]
import palette_channels as channels
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
from unpack import relocated

common, caller, video, oracle = channels.common, channels.caller, channels.video, channels.oracle
IMAGE, ORACLE = channels.IMAGE, channels.ORACLE
ENTRIES, RETURNS = (0x563e,0x56e2),(0x566b,0x570b)
BLOCKS = ((0x563e,bytes.fromhex('33ed32ed518a148a0d8ad98ac2e81e008af08ac28ad9e82e000af08ac28ad9e836000af08834594647e2d923edc3')),
    (0x56e2,bytes.fromhex('32db32ed8a048a25e81f00880446478a048a25e81400880446478a048a25e8090088044647e2dd22dbc3')))
LOCAL = {i.address:i for p,b in BLOCKS for i in video.MD.disasm(b,p)}
INS = LOCAL | channels.INS
EDGES = {(0x5667,0x5642),(0x5667,0x5669),(0x5707,0x56e6),(0x5707,0x5709)}
REPORT, ORIGINAL_REPORT = BUILD/'palette-rows-differential.json',BUILD/'palette-rows-contract-original.json'


def fail(message): raise common.VerificationFailure(message)


def defined_after(pc,mask):
    if pc in channels.INS:return channels.mask_after(pc,mask)
    mnemonic=LOCAL[pc].mnemonic
    if mnemonic in ('xor','or','and'):return channels.LOGIC
    if mnemonic=='inc':return (mask&1)|(channels.FULL&~1)
    return mask


def cases():
    rows=[]
    def add(name,entry=0,**kw):rows.append(dict(name=name,entry=entry,seed=len(rows),**kw))
    for entry in (0,1):
        for count in (1,2,3,16,255):
            for df in (0,1):add(f'e{entry}-n{count}-df{df}',entry,count=count,df=df,independent=True)
        for value in (0,1,9,63,127,128,255):add(f'e{entry}-equal-{value}',entry,count=2,equal=value,independent=True)
        for delta in (-3,-1,0,1,3):add(f'e{entry}-overlap-{delta}',entry,count=3,di=0x2000,si=(0x2000+delta)&65535,independent=True)
        for cursor in (0,1,0xfffd,0xffff):add(f'e{entry}-cursor-{cursor:04x}',entry,count=3,si=cursor,di=(cursor+0x1234)&65535,independent=True)
        add(f'e{entry}-INC-lowbyte-zero',entry,count=2,si=0x10ff,di=0x20ff,independent=True)
        for sp in (0,1,0xfffe,0xffff):add(f'e{entry}-sp-{sp:04x}',entry,count=2,sp=sp,independent=True)
        add(f'e{entry}-stack-A20',entry,count=2,ss=0xffff,sp=0xf,independent=True)
        add(f'e{entry}-data-A20',entry,count=3,ds=0xffff,si=0xc,di=0x20,independent=True)
        add(f'e{entry}-data-VGA',entry,count=2,ds=0xa000,vga=True)
        add(f'e{entry}-stack-VGA',entry,count=2,ss=0xa000,vga=True)
        add(f'e{entry}-both-VGA',entry,count=2,ds=0xa000,ss=0xa000,vga=True)
        add(f'e{entry}-return-alias',entry,count=1,ds=0x7000,ss=0x7000,si=0x8000,outer_changed=True)
    add('live-counter-one',count=1,ds=0x7000,ss=0x7000,si=0x7ffe,di=0x3000,counter_alias=True,target_first=0)
    add('live-counter-zero',count=0,ds=0x7000,ss=0x7000,si=0x7ffe,di=0x3000,counter_alias=True,target_first=9)
    add('push-before-target',count=1,ds=0x7000,ss=0x7000,di=0x7ffe)
    add('rgb-live-target-triple',1,count=1,si=0x2001,di=0x2000,overlap_witness=True,independent=True)
    add('rgb-sticky-marker',1,count=1,source=[5,7,9],target=[0,7,9],independent=True)
    for entry,ret,delta,status in ((0,0x564e,-4,2),(0,0x5657,-4,2),(0,0x5660,-4,2),
            (0,0x567c,-6,1),(0,0x5691,-6,1),(1,0x56ed,-2,2),(1,0x56f8,-2,2),(1,0x5703,-2,2)):
        add(f'changed-{ret:04x}',entry,count=1,ss=0xa000,vga=True,change_frame=(ret,delta),status=status)
    for entry in (0,1):add(f'fast-sanity-{entry}',entry,count=3,zero_data=True,si=0x1000,di=0x1000,independent=True,fast_sanity=True)
    return rows


def zero_case(entry):
    return dict(name=f'zero-full-{entry}',entry=entry,seed=500+entry,count=0,zero_data=True,
        si=0x1000,di=0x1000,df=entry,independent=True,slow=True)


def prepare(case):
    rng=random.Random(0x563e+case['seed'])
    load=(0x1010,0x1213,0x2345)[case['seed']%3]
    memory=bytearray(rng.randbytes(1<<20))
    loaded=relocated(IMAGE,ORACLE['relocations'],load)
    memory[load<<4:(load<<4)+len(loaded)]=loaded
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRIES[case['entry']],ds=case.get('ds',0x3000),es=0x6000,
        ss=case.get('ss',0x7000),sp=case.get('sp',0x8000),si=case.get('si',0x1000),di=case.get('di',0x2000),
        cx=0xa500|case.get('count',3))
    flags=2|((case['seed']*0x95^0xad5)&0xad5)|(0x400 if case.get('df') else 0)
    if case.get('zero_data'):
        # Only the special fixed-machine path uses this disjoint RAM layout.
        for n in range(65536):memory[video.physical(regs['ds'],n)]=0
    elif 'equal' in case:
        for cursor in (regs['si'],regs['di']):
            for n in range(6):memory[video.physical(regs['ds'],(cursor+n)&65535)]=case['equal']
    if case.get('counter_alias'):
        for n in range(8):memory[video.physical(regs['ds'],regs['di']+n)]=case['target_first'] if n==0 else 0
    if case.get('overlap_witness'):
        for n,v in enumerate((0,2,3,4)):memory[video.physical(regs['ds'],0x2000+n)]=v
    for key,cursor in (('source',regs['si']),('target',regs['di'])):
        for n,v in enumerate(case.get(key,[])):memory[video.physical(regs['ds'],(cursor+n)&65535)]=v
    video.putword(memory,regs['ss'],regs['sp'],0xeed1)
    return memory,regs,flags


def device_for(memory,case,regs):
    device=common.TraceDevice(bytearray(memory),0x563e+case['seed'])
    if case.get('change_frame'):
        ret,delta=case['change_frame'];target=video.physical(regs['ss'],(regs['sp']+delta)&65535)
        write=device.vga.write
        device.changed_frame_hits=0
        def replace_frame(mem,p,value,flags):
            write(mem,p,value,flags)
            if p==target and value==(ret&255):
                device.changed_frame_hits+=1
                mem[p]=1
                for plane in device.vga.planes:plane[p-0xa0000]=1
        device.vga.write=replace_frame
    return device


def independent(case,memory,regs,flags):
    """Sequential scalar data/marker model using the independent channel math."""
    expected=bytearray(memory);state=dict(regs,flags=flags)
    count=regs['cx']&255;iterations=count or 65536
    state['cx']=count
    if case['entry']==0:state['bp']=0
    else:state['bx']&=0xff00
    for _ in range(iterations):
        if case['entry']==0:
            source=expected[video.physical(state['ds'],state['si'])]
            target=expected[video.physical(state['ds'],state['di'])]
            state['dx']=(state['dx']&0xff00)|source
            saved=state['cx'];state['cx']=(state['cx']&0xff00)|target
            composed=0
            for entry in (0,1,2):
                state['ax']=(state['ax']&0xff00)|source
                state['bx']=(state['bx']&0xff00)|target
                state,_mask=channels.mathematical(state,state['flags'],entry)
                composed|=state['ax']&255
            state['dx']=(composed<<8)|source
            expected[video.physical(state['ds'],state['si'])]=composed
            state['cx']=saved
            state['si']=(state['si']+1)&65535;state['di']=(state['di']+1)&65535
        else:
            for _component in range(3):
                source=expected[video.physical(state['ds'],state['si'])]
                target=expected[video.physical(state['ds'],state['di'])]
                state['ax']=(target<<8)|source
                state,_mask=channels.mathematical(state,state['flags'],4)
                expected[video.physical(state['ds'],state['si'])]=state['ax']&255
                state['si']=(state['si']+1)&65535;state['di']=(state['di']+1)&65535
        state['cx']=(state['cx']-1)&65535
    marker=state['bp'] if case['entry']==0 else state['bx']&255
    changed=(4 if (marker&255).bit_count()%2==0 else 0)|(0x40 if marker==0 else 0)|(0x80 if marker&(0x8000 if case['entry']==0 else 0x80) else 0)
    state['flags']=(flags&~channels.ARITH)|changed;state['ip']=RETURNS[case['entry']]
    if case['entry']==0:
        for delta,value in ((-6,0x5691),(-4,0x5660),(-2,1)):
            video.putword(expected,regs['ss'],(regs['sp']+delta)&65535,value)
    else:video.putword(expected,regs['ss'],(regs['sp']-2)&65535,0x5703)
    return expected,state,iterations


def original_generic(case,device,regs,flags,core):
    loops,pops=[],[]
    def observe(pc,uc,_device):
        if pc in (0x5642,0x56e6):loops.append(uc.reg_read(oracle.REG['cx']))
        if pc==0x5665:pops.append(uc.reg_read(oracle.REG['cx']))
    result=caller.original(case,device,regs,flags,instructions=INS,far_calls=set(),
        continuations=(RETURNS[case['entry']],) if core else (),observe=observe,max_steps=100000,
        defined_mask_after=defined_after)
    return result,len(loops),pops


def original_fast(case,device,regs,flags):
    """No aliases/providers: observe caller/frame instructions, not every ALU op.

    Channel bodies were exhaustively checked separately. Every data access still
    has ordered byte/phase-flag observation and the complete execution is bounded.
    Small fast-sanity cases require exact equality with the full instruction hook.
    """
    if not case.get('zero_data') or regs['ds']!=0x3000 or regs['ss']!=0x7000 or regs['si']!=regs['di']:
        fail('Fast original requires the declared disjoint zero RAM domain')
    loaded=relocated(IMAGE,ORACLE['relocations'],regs['cs'])
    if any(device.memory[video.physical(regs['cs'],p+n)]!=loaded[p+n] for p,i in INS.items() for n in range(i.size)):
        fail('Fast original entered with modified decoded code')
    stack=video.physical(regs['ss'],regs['sp'])
    data_lo=regs['ds']<<4
    def permitted(p):return data_lo<=p<data_lo+65536 or stack-6<=p<stack
    uc=Uc(UC_ARCH_X86,UC_MODE_16);uc.mem_map(0,2<<20);uc.mem_write(0,bytes(device.memory)*2)
    for n,r in oracle.REG.items():uc.reg_write(r,regs[n])
    uc.reg_write(x.UC_X86_REG_EFLAGS,flags)
    loops=0;stopped=False;event_flags=flags;mask=channels.LOGIC;failures=[];seen=set()
    def code(machine,_p,_size,_):
        nonlocal loops,stopped,event_flags,mask
        pc=machine.reg_read(oracle.REG['ip'])
        if pc==RETURNS[case['entry']]:stopped=True;machine.emu_stop();return
        seen.add(pc)
        if pc==(0x5642 if case['entry']==0 else 0x56e6):loops+=1
        event_flags=machine.reg_read(x.UC_X86_REG_EFLAGS)
        if case['entry']==0:
            mask=channels.FULL if loops>1 and pc in (0x5642,0x5643,0x5645,0x564b) else channels.LOGIC
        else:
            mask=channels.LOGIC if loops==1 and pc in (0x56e6,0x56e8,0x56ea) else channels.FULL
    lo,hi=(0x563e,0x566b) if case['entry']==0 else (0x56e2,0x570b)
    uc.hook_add(UC_HOOK_CODE,code,begin=(regs['cs']<<4)+lo,end=(regs['cs']<<4)+hi)
    for pc in ((0x5679,0x568e,0x5684,0x5695,0x56e1) if case['entry']==0 else (0x571e,0x5725)):
        uc.hook_add(UC_HOOK_CODE,code,begin=(regs['cs']<<4)+pc,end=(regs['cs']<<4)+pc)
    code_addresses={video.physical(regs['cs'],p+n) for p,i in INS.items() for n in range(i.size)}
    def read(machine,_access,address,size,_value,_):
        for n in range(size):
            p=address+n
            if not 0<=p<1<<20 or not permitted(p):failures.append('fast read escaped declared data/frame domain');machine.emu_stop();return
            device.events.add('read',p,device.memory[p],event_flags,mask)
        device.check('fast original read')
    def write(machine,_access,address,size,value,_):
        for n in range(size):
            p=address+n
            if not 0<=p<1<<20 or p in code_addresses or not permitted(p):failures.append('fast write changed code/escaped data/frame domain');machine.emu_stop();return
            byte=(value>>(8*n))&255;device.memory[p]=byte
            device.events.add('write',p,byte,event_flags,mask)
        device.check('fast original write')
    uc.hook_add(UC_HOOK_MEM_READ,read);uc.hook_add(UC_HOOK_MEM_WRITE,write)
    uc.emu_start((regs['cs']<<4)+regs['ip'],0,count=12000000)
    if failures or not stopped:fail('Fast original control/instruction budget failed '+str(failures))
    actual={n:uc.reg_read(r) for n,r in oracle.REG.items()};actual['flags']=uc.reg_read(x.UC_X86_REG_EFLAGS)
    actual_mask=channels.LOGIC
    return (actual,actual_mask,seen,set(),('continuation',regs['cs'],RETURNS[case['entry']]),None,None),loops,[]


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ctypes.CDLL(str(build(Path(directory)/f'palette-rows-m{mutation}.dll',mutation,'palette_rows')))
        self.core=self.lib.lmn_step_palette_row_core
        self.core.argtypes=[video.MEM,ctypes.c_uint16,ctypes.POINTER(video.State),ctypes.c_int,ctypes.POINTER(common.RasterBus)]
        self.core.restype=channels.Result
        self.adapter=self.lib.lmn_step_palette_row_adapter
        self.adapter.argtypes=[video.MEM,ctypes.POINTER(video.Regs),ctypes.c_int,ctypes.POINTER(common.RasterBus)]
        self.adapter.restype=None


def compare(native,case,core):
    memory,regs,flags=prepare(case);original=device_for(memory,case,regs)
    result,loops,pops=(original_fast(case,original,regs,flags) if case.get('slow') else original_generic(case,original,regs,flags,core))
    actual,mask,sites,edges,boundary,_child,_body=result
    if case.get('fast_sanity'):
        fast=device_for(memory,case,regs);fr,fl,_=original_fast(case,fast,regs,flags)
        if core:
            if fl!=loops or fr[0]!=actual or fast.memory!=original.memory:fail('Fast/full original state/RAM mismatch')
            if fast.events.mask_bytes!=original.events.mask_bytes:fail('Fast/full original phase masks differ')
            try:common.compare_event_traces(fast.events,original.events,'fast/full sanity')
            except common.Mismatch as error:fail(str(error))
    if case.get('change_frame'):
        target=(case['change_frame'][0]&0xff00)|1
        if boundary!=('changed-child-near',regs['cs'],target) or original.changed_frame_hits!=1:fail(case['name']+': changed frame not exercised '+str(boundary))
    elif case.get('counter_alias'):
        if loops!=8 or not pops or pops[0]!=8:fail(case['name']+': savedCX alias did not produce8iterations '+str((loops,pops)))
    elif case.get('independent'):
        expected,model,iterations=independent(case,memory,regs,flags)
        if not core:model.update(ip=oracle.get16(original.memory,regs['ss'],regs['sp']),sp=(regs['sp']+2)&65535)
        if expected!=original.memory or loops!=iterations or any(model[n]!=actual[n] for n in oracle.REG_NAMES) or (model['flags']^actual['flags'])&channels.LOGIC:
            fail(case['name']+': independent row model differs')
    if case.get('outer_changed') and not core and actual['ip']==0xeed1:fail('Outer return alias was not exercised')
    if case.get('slow') and loops!=65536:fail('Original zeroCL loop did not execute65536iterations')
    if native:
        null_modes=(False,) if case.get('slow') or case.get('vga') else (False,True)
        for null in null_modes:
            device=device_for(memory,case,regs);bus=None if null else ctypes.byref(device.bus)
            if core:
                out=native.core(video.buffer(device.memory),regs['cs'],ctypes.byref(video.to_state(dict(regs,flags=flags))),case['entry'],bus)
                got=dict(video.state_dict(out.state),cs=out.code_segment,ip=out.continuation)
                common.require(out.status==case.get('status',0),case['name']+': native status differs')
            else:
                r=video.Regs(**regs,flags=flags);native.adapter(video.buffer(device.memory),ctypes.byref(r),case['entry'],bus)
                got={n:getattr(r,n) for n in (*oracle.REG_NAMES,'flags')}
            common.require(all(got[n]==actual[n] for n in oracle.REG_NAMES) and not ((got['flags']^actual['flags'])&mask),case['name']+': native CPU/flags differ')
            common.require(device.memory==original.memory,case['name']+': fullRAM differs')
            common.compare_event_traces(device.events,original.events,case['name']) if not null else None
            common.require(device.vga.state()==original.vga.state(),case['name']+': VGA differs')
    return dict(name=case['name'],core=core,loops=loops,boundary=boundary,sites=sorted(sites),edges=sorted(edges),bus_events=original.events.count)


def input_hashes(native=False):
    paths=set(channels.input_hashes(native))|{'tests/palette_rows.py','docs/palette-rows.md'}
    if native:paths|={'c/palette_rows.c','c/palette_rows.h'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def worker(directory=None,zero=None):
    common.MAX_BUS_EVENTS=2000000 if zero is not None else 25000
    common.MAX_VGA_EVENTS=10000
    channels.identity()
    if any(IMAGE[p:p+len(b)]!=b for p,b in BLOCKS) or len(LOCAL)!=47:fail('Pinned row bytes/boundaries differ')
    before=input_hashes(directory is not None)
    native=Native(directory) if directory is not None else None
    if zero is not None:
        rows=[compare(native,zero_case(zero),True)];mutants=[]
    else:
        rows=[]
        for case in cases():
            for core in (False,True):rows.append(compare(native,case,core))
            gc.collect()
        sites={p for r in rows for p in r['sites']};edges={tuple(e) for r in rows for e in r['edges']}
        if sites!=set(INS) or not (EDGES|channels.EDGES)<=edges:fail(f'Row sites/edges incomplete {set(INS)-sites}/{(EDGES|channels.EDGES)-edges}')
        mutants=[]
        if native:
            for mutation,name in ((1,'live-counter-one'),(2,'e0-n2-df1'),(3,'rgb-live-target-triple'),(4,'rgb-sticky-marker'),(5,'changed-564e'),(6,'live-counter-zero')):
                lib=Native(directory,mutation);case=next(c for c in cases() if c['name']==name)
                try:compare(lib,case,True)
                except common.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,reason=str(error)))
                else:fail(f'PALETTE_ROWS_MUTATION={mutation} survived')
                gc.collect()
    if before!=input_hashes(native is not None):fail('Row verification inputs changed')
    report=dict(cases=rows,input_hashes=before,mutants=mutants)
    name='normal' if zero is None else f'zero-{zero}'
    if directory is not None:write_json(Path(directory)/(name+'.json'),report)
    else:write_json(BUILD/('palette-rows-original-'+name+'.json'),report)
    print(f'PASS palette rows {name} {"C" if native else "original"}: {len(rows)} boundaries, {len(mutants)} mutants',flush=True)


def run(original=False):
    report=ORIGINAL_REPORT if original else REPORT;report.unlink(missing_ok=True)
    before=input_hashes(not original);deadline=time.monotonic()+600
    try:
        with temporary_build_directory(prefix='palette-rows-',parent=BUILD) as directory:
            for zero in (None,0,1):
                remaining=deadline-time.monotonic()-10
                if remaining<=0:fail('Row campaign deadline exhausted')
                args=['--worker',directory if not original else '-','-' if zero is None else str(zero)]
                run_bounded([sys.executable,str(Path(__file__).resolve()),*args],cwd=ROOT,timeout=min(240,remaining),memory_mib=384)
            reports=[channels.read_json((BUILD/f'palette-rows-original-{name}.json') if original else Path(directory)/(name+'.json')) for name in ('normal','zero-0','zero-1')]
        if any(r['input_hashes']!=before for r in reports) or before!=input_hashes(not original):fail('Row campaign inputs stale')
        cases_all=[c for r in reports for c in r['cases']];sites={p for c in reports[0]['cases'] for p in c['sites']};edges={tuple(e) for c in reports[0]['cases'] for e in c['edges']}
        write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(cases())+2,boundary_fixtures=len(cases()),zero_count_core_cases=2,
            caller_sites=47,caller_bytes=88,translated_code_bytes=0 if original else 88,native_code_ranges=[] if original else [[0x563e,0x566c],[0x56e2,0x570c]],
            caller_instruction_addresses=sorted(LOCAL),executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),caller_branch_edges=sorted(EDGES),
            cases=cases_all,mutation_count=len(reports[0]['mutants']),mutations_detected=reports[0]['mutants'],input_hashes=before,c_coverage_claimed=not original,
            limits=dict(campaign_seconds=600,worker_seconds=240,windows_process_mib=384,windows_tree_mib=640,normal_instruction_budget=100000,zero_instruction_budget=12000000,zero_bus_events=2000000),
            domain='563E/56E2 rows connected to five native channel entries; sequential scalar data model, fullRAM/allCPU/definedflags/orderedbus/VGA, overlap and actual child/outer returns. ZeroCL executes65536iterations at both core entries with validated selective caller/frame tracing. Native devices, IRQ scheduling, hardware stack segment limits and palette pointer/buffer ownership remain open.'))
        print(f'PASS palette rows {"original" if original else "C"}: {len(cases())} x2 fixtures +2 fullzeroCL core cases,47 caller/{len(sites)} integrated sites,{len(reports[0]["mutants"])} mutants',flush=True)
    except BaseException:report.unlink(missing_ok=True);raise


if __name__=='__main__':
    args=sys.argv[1:]
    if len(args)==3 and args[0]=='--worker':worker(None if args[1]=='-' else args[1],None if args[2]=='-' else int(args[2]))
    elif args==['--original-only']:run(True)
    elif not args:run()
    else:raise SystemExit('Unexpected palette row arguments')

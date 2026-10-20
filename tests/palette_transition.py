"""531E/536C transition callers composed against bounded pinned instructions."""
import ctypes
import gc
import random
import subprocess
import sys
import time
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools'),str(Path(__file__).resolve().parent)]
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_HOOK_INSN
from unicorn import x86_const as x
import palette_rows as rows
import palette_ports as ports
import display_status as status
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
import verification as shared
from common import ROOT,BUILD,sha,write_json,read_json
from unpack import relocated

channels,common,video,oracle=rows.channels,rows.common,rows.video,rows.oracle
IMAGE,ORACLE=rows.IMAGE,rows.ORACLE
ENTRIES=(0x531e,0x536c);RETURNS=(0x5600,0x563d)
BLOCKS=((0x531e,bytes.fromhex('32c0b91000bb0001e98e02')),
 (0x536c,bytes.fromhex('32c0b91000bb0002e94002')),
 (0x55b7,bytes.fromhex('833e7c1f047443061e078ac332e403c08d36d45203f02e8b348ac732e403c08d3ed45203f82e8b3d5156e841fe5e59515657e85200740ee85fbfe85cbfe859bf5f5e59ebe35f5e5907c3061e078ac332e403c08d36e45203f02e8b348ac732e403c08d3ee45203f82e8b3d5156e89dfe5e59515657e8b3007408e81cbf5f5e59ebe95f5e5907c3')))
LOCAL={i.address:i for p,b in BLOCKS for i in video.MD.disasm(b,p)}
INS=LOCAL|rows.INS|ports.INS|status.INS
BRANCHES={p for p,i in INS.items() if i.group(video.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(p,i.operands[0].imm&65535) for p,i in INS.items() if p in BRANCHES}
EDGES|={(p,p+i.size) for p,i in INS.items() if p in BRANCHES and i.mnemonic!='jmp'}
LOCAL_EDGES={e for e in EDGES if e[0] in LOCAL}
CALL_RETURNS={0x55e4,0x55ec,0x55f1,0x55f4,0x55f7,0x5627,0x562f,0x5634}
REPORT=BUILD/'palette-transition-differential.json';ORIGINAL_REPORT=BUILD/'palette-transition-contract-original.json'


def fail(message):raise common.VerificationFailure(message)


def cases():
    specs=[]
    def add(name,entry=0,mode=2,**kw):specs.append(dict(name=name,entry=entry,mode=mode,seed=len(specs),**kw))
    for entry in (0,1):
        for mode in (2,4):
            for value in range(256):add(f'e{entry}-m{mode}-value-{value:02x}',entry,mode,source=value,target=(value+1)&255,df=value&1,control=255 if value&2 else 0,independent=True)
            for source,target in ((0,9),(9,0),(0x80,0x7f),(0x7f,0x80),(0xff,0),(0x40,0x40)):
                add(f'e{entry}-m{mode}-pair-{source:02x}-{target:02x}',entry,mode,source=source,target=target,independent=True)
            for kind in ('sp-zero','sp-one','sp-ffff','stack-a20','data-a20','vga-data','vga-stack',
                         'saved-es','saved-cx','saved-si','saved-step-di','saved-step-si','saved-step-cx',
                         'mode-flip','provider-source','provider-base','outer-ret-high','source-word-high','pop-es'):
                add(f'e{entry}-m{mode}-{kind}',entry,mode,kind=kind,source=0,target=9)
            add(f'e{entry}-m{mode}-long-poll',entry,mode,sequence=[0,0,8,8,0],source=0,target=9,independent=True)
            add(f'e{entry}-m{mode}-static',entry,mode,static=True,independent=True)
            for missing in ('no-ports','no-input','no-output'):
                for control in (0,255):add(f'e{entry}-m{mode}-{missing}-{control}',entry,mode,missing=missing,control=control,source=0,target=9)
    for mode in (0,1,3,5,0x104,0xff04,0x7fff,0x8000,0x8003,0x8004,0xffff):add(f'mode-{mode:04x}',mode=mode,source=0,target=9,independent=True)
    for mode in (2,4):
        for delta in (-1,0,1):add(f'm{mode}-overlap-{delta}',mode=mode,delta=delta,source=0,target=9,independent=True)
    for mode,ret,delta in ((2,0x55e4,-8),(2,0x55ec,-10),(2,0x55f1,-10),(2,0x55f4,-10),(2,0x55f7,-10),
                           (4,0x5627,-8),(4,0x562f,-10),(4,0x5634,-10)):
        add(f'changed-{ret:04x}',mode=mode,change_frame=(ret,delta),want_status=5,source=0,target=9)
    for mode,ret,delta,want in ((2,0x564e,-14,4),(2,0x5657,-14,4),(2,0x5660,-14,4),
                               (2,0x567c,-16,3),(2,0x5691,-16,3),(4,0x56ed,-12,4),(4,0x56f8,-12,4),(4,0x5703,-12,4)):
        add(f'changed-{ret:04x}',mode=mode,change_frame=(ret,delta),want_status=want,source=0,target=9)
    for kind in ('control-zero-to-ff','control-ff-to-zero'):
        add(kind,mode=4,kind=kind,source=0,target=9,control=255 if kind=='control-ff-to-zero' else 0,want_status=5)
    return specs


def prepare(case):
    rng=random.Random(0x531e00+case['seed']);load=video.LOADS[case['seed']%3]
    memory=bytearray(rng.randbytes(1<<20));loaded=relocated(IMAGE,ORACLE['relocations'],load)
    memory[load<<4:(load<<4)+len(loaded)]=loaded
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRIES[case['entry']],ds=(load+0x9a9)&65535 if case.get('static') else 0x4000,es=0x6000,ss=0x7000,sp=0x8000)
    flags=2|((case['seed']*0x95^0xad5)&0xad5)|(0x400 if case.get('df') else 0)
    kind=case.get('kind')
    if kind in ('sp-zero','sp-one','sp-ffff'):regs['sp']={'sp-zero':0,'sp-one':1,'sp-ffff':65535}[kind]
    if kind=='stack-a20':regs.update(ss=0xffff,sp=0xf)
    if kind=='data-a20':regs['ds']=0xffff
    if kind=='vga-data':regs['ds']=0xa000
    if kind=='vga-stack':regs['ss']=0xa000
    if not case.get('static'):
        for table in (0x52d4,0x52e4):
            for slot,pointer in enumerate((0x1000,0x2000,0x3000)):video.putword(memory,load,table+2*slot,pointer)
        for cursor,value in ((0x1000,case.get('source',0)),(0x2000,case.get('target',9)),(0x3000,case.get('target',9)),(0x4000,0),(0x5000,0),(0x1100,0)):
            for n in range(-48,96):memory[video.physical(regs['ds'],(cursor+n)&65535)]=value
    if 'delta' in case:
        pattern=(0,2,3,4) if case['mode']==4 else (0,9,8,1)
        for n in range(48):memory[video.physical(regs['ds'],0x1000+n)]=pattern[n%4]
        for table in (0x52d4,0x52e4):video.putword(memory,load,table+2*(case['entry']+1),0x1000+case['delta'])
    video.putword(memory,regs['ds'],0x1f7c,case['mode']);video.putword(memory,regs['ds'],0x1fda,0x3d4)
    memory[video.physical(regs['ds'],0x200c)]=case.get('control',255)
    video.putword(memory,regs['ss'],regs['sp'],0xeed1)
    return memory,regs,flags


class Backend(ports.Backend):
    def __init__(self,memory,case,regs,native=False):
        super().__init__(memory,case,regs,native=native)
        self.trace=ports.Trace(600000,native);self.io_trace=ports.Trace(100000,native)
        self.status_inputs=0;self.first_effect=False;self.step_effect=False;self.frame_hits=0
    def read(self,p,f,mask):
        p&=0xfffff;i=self.initial;kind=self.case.get('kind')
        saved=video.physical(i['ss'],(i['sp']-4)&65535)
        if kind=='pop-es' and not self.effect and p==saved and oracle.get16(self.memory,i['ss'],(i['sp']-4)&65535)==i['ds']:
            self.word_effect(i['ss'],(i['sp']-4)&65535,0x1234);self.effect=True
        value=self.vga.read(self.memory,p,f);self.trace.add('read',p,value,f,mask)
        if not self.effect:
            if kind=='outer-ret-high' and p==video.physical(i['ss'],i['sp']):self.store(p+1,0x5a);self.effect=True
            if kind=='source-word-high' and p==video.physical(i['cs'],0x52e4 if self.case['mode']==4 else 0x52d4):self.store(p+1,0x11);self.effect=True
        return value
    def write(self,p,v,f,mask):
        super().write(p,v,f,mask);i=self.initial;p&=0xfffff
        if self.case.get('change_frame') and not self.frame_hits:
            ret,delta=self.case['change_frame'];at=video.physical(i['ss'],(i['sp']+delta)&65535)
            if p==at and v==(ret&255):self.store(p,1);self.frame_hits+=1
        kind=self.case.get('kind')
        wait_ret=0x5634 if self.case['mode']==4 else 0x55f1
        if not self.step_effect and p==video.physical(i['ss'],(i['sp']-10)&65535) and v==(wait_ret&255):
            if kind in ('saved-step-di','saved-step-si','saved-step-cx'):
                delta,value={'saved-step-di':(-8,0x5000),'saved-step-si':(-6,0x4000),'saved-step-cx':(-4,1)}[kind]
                self.word_effect(i['ss'],(i['sp']+delta)&65535,value);self.step_effect=True
    def port(self,kind,p,v,f,mask):
        if kind=='in':
            if p==0x3c5:v=0x93
            else:
                seq=self.case.get('sequence',[8,0]);v=seq[self.status_inputs%len(seq)];self.status_inputs+=1
            self.inputs+=1
        else:self.outputs+=1
        self.trace.add(kind,p,v,f,mask);self.io_trace.add(kind,p,v,f,mask);self.port_rows.append((kind,p,v))
        if kind=='out' and not self.first_effect:
            self.first_effect=True;i=self.initial;k=self.case.get('kind')
            if k in ('saved-es','saved-cx','saved-si'):
                delta,value={'saved-es':(-2,0x4567),'saved-cx':(-4,1),'saved-si':(-6,0x4000)}[k]
                self.word_effect(i['ss'],(i['sp']+delta)&65535,value)
            if k=='mode-flip':self.word_effect(i['ds'],0x1f7c,2 if self.case['mode']==4 else 4)
            if k=='provider-source':self.store(video.physical(i['ds'],0x1000),9)
            if k=='provider-base':self.word_effect(i['ds'],0x1fda,0x3b4)
            if k in ('control-zero-to-ff','control-ff-to-zero'):self.store(video.physical(i['ds'],0x200c),255 if k=='control-zero-to-ff' else 0)
        return v


def defined_after(pc,mask):
    if pc in rows.INS:return rows.defined_after(pc,mask)
    mnemonic=INS[pc].mnemonic
    if mnemonic in ('xor','or','and','test'):return channels.LOGIC
    if mnemonic in ('inc','dec'):return (mask&1)|(channels.FULL&~1)
    if mnemonic in ('add','cmp'):return channels.FULL
    return mask


def missing_at(case,pc):
    missing=case.get('missing');mnemonic=INS[pc].mnemonic
    if mnemonic=='in' and missing in ('no-ports','no-input'):return 1
    if mnemonic=='out' and missing in ('no-ports','no-output'):return 2
    return 0


def original(case,memory,regs,flags,core):
    b=Backend(memory,case,regs);u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,2<<20);u.mem_write(0,bytes(memory)*2)
    for n,r in oracle.REG.items():u.reg_write(r,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags)
    loaded=relocated(IMAGE,ORACLE['relocations'],regs['cs'])
    values={video.physical(regs['cs'],p+n):loaded[p+n] for p,i in INS.items() for n in range(i.size)}
    if any(b.memory[p]!=v for p,v in values.items()):fail('Transition entered modified instructions')
    previous=None;mask=channels.FULL;event_flags=flags;frames=[];pending=None;boundary=None;st=0;steps=0
    sites=set();edges=set();calls={};prefix=None
    def error(e):
        if not errors:errors.append(str(e))
        u.emu_stop()
    errors=[]
    def sync():
        for p in b.changed:
            if p in values and b.memory[p]!=values[p]:fail('Transition provider changed decoded instructions')
            byte=bytes((b.memory[p],));u.mem_write(p,byte);u.mem_write(p+(1<<20),byte)
        b.changed.clear()
    def code(uc,_p,_size,_ctx):
        nonlocal previous,mask,event_flags,pending,boundary,st,steps,prefix
        off=uc.reg_read(x.UC_X86_REG_IP);cs=uc.reg_read(x.UC_X86_REG_CS)
        if previous is not None:mask=defined_after(previous,mask)
        if pending is not None:
            expected=pending;pending=None
            if expected is False:boundary=('outer-return',cs,off);uc.emu_stop();return
            frames.pop()
            if (cs,off)!=expected:
                st=5 if expected[1] in CALL_RETURNS else 3 if expected[1] in (0x567c,0x5691) else 4
                boundary=('changed-child-near',cs,off);uc.emu_stop();return
        if previous in BRANCHES:edges.add((previous,off))
        if cs!=regs['cs'] or off not in INS:error(f'Transition escaped at{cs:04x}:{off:04x}');return
        st=missing_at(case,off)
        if st:boundary=('missing-provider',cs,off);uc.emu_stop();return
        if core and off in RETURNS:boundary=('ready-return',cs,off);uc.emu_stop();return
        if off in ports.STARTS and prefix is None:
            prefix={n:uc.reg_read(r) for n,r in oracle.REG.items()};prefix['flags']=uc.reg_read(x.UC_X86_REG_EFLAGS)
        steps+=1
        if steps>2000000:error('Transition original instruction budget exhausted');return
        i=INS[off];sites.add(off);previous=off;event_flags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        if i.mnemonic=='call':
            frames.append((cs,off+i.size));calls[off]=calls.get(off,0)+1
        if i.mnemonic=='ret':pending=frames[-1] if frames else False
    def read(uc,_a,address,size,_v,_ctx):
        try:
            for n in range(size):uc.mem_write(address+n,bytes((b.read(address+n,event_flags,mask),)));sync()
        except BaseException as e:error(e)
    def write(_uc,_a,address,size,value,_ctx):
        try:
            for n in range(size):b.write(address+n,(value>>(8*n))&255,event_flags,mask);sync()
        except BaseException as e:error(e)
    def inp(_uc,p,size,_ctx):
        try:
            if size!=1:fail('Transition input is not byte width')
            v=b.port('in',p,0,event_flags,mask);sync();return v
        except BaseException as e:error(e);return 0
    def out(_uc,p,size,v,_ctx):
        try:
            if size!=1:fail('Transition output is not byte width')
            b.port('out',p,v,event_flags,mask);sync()
        except BaseException as e:error(e)
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_MEM_READ,read);u.hook_add(UC_HOOK_MEM_WRITE,write)
    u.hook_add(UC_HOOK_INSN,inp,None,1,0,x.UC_X86_INS_IN);u.hook_add(UC_HOOK_INSN,out,None,1,0,x.UC_X86_INS_OUT)
    u.emu_start((regs['cs']<<4)+ENTRIES[case['entry']],0,count=2000001)
    if errors:fail(case['name']+': '+errors[0])
    if boundary is None:fail('Transition original did not finish')
    result={n:u.reg_read(r) for n,r in oracle.REG.items()};result['flags']=u.reg_read(x.UC_X86_REG_EFLAGS)
    return b,result,mask,st,sites,edges,boundary,calls,prefix


def independent(case,memory,regs,flags,b,result,calls,prefix):
    if not case.get('independent'):return
    rgb=case['mode']==4;table=0x52e4 if rgb else 0x52d4
    source=oracle.get16(memory,regs['cs'],table);target=oracle.get16(memory,regs['cs'],table+2*(case['entry']+1))
    if prefix is None or (prefix['si'],prefix['di'],prefix['cx'],prefix['bx'],prefix['es'],prefix['sp'])!=(source,target,16,(case['entry']+1)<<8,regs['ds'],(regs['sp']-8)&65535):fail('Independent transition prefix differs')
    work=bytearray(memory);events=[];reads=0;passes=0
    def emit(kind,p,v):events.append((kind,p,v))
    def inp(p):
        nonlocal reads
        if p==0x3c5:v=0x93
        else:seq=case.get('sequence',[8,0]);v=seq[reads%len(seq)];reads+=1
        emit('in',p,v);return v
    def wait():
        while not inp(0x3da)&8:pass
        while inp(0x3da)&8:pass
    while True:
        passes+=1
        if passes>512:fail('Independent transition convergence budget exhausted')
        cursor=source;direction=-1 if flags&0x400 else 1
        if rgb:
            if case.get('control',255)!=255:emit('out',0x3c4,1);emit('out',0x3c5,inp(0x3c5)|0x20)
            for n in range(16):
                emit('out',0x3c8,work[video.physical(regs['cs'],0x5507+n)])
                for _ in range(3):emit('out',0x3c9,work[video.physical(regs['ds'],cursor)]);cursor=(cursor+direction)&65535
            if case.get('control',255)!=255:emit('out',0x3c5,0x93&0xdf)
        else:
            inp(0x3da)
            for n in range(16):emit('out',0x3c0,n);emit('out',0x3c0,work[video.physical(regs['ds'],cursor)]);cursor=(cursor+direction)&65535
            inp(0x3da);emit('out',0x3c0,0x20)
        changed=False
        for n in range(48 if rgb else 16):
            p=video.physical(regs['ds'],(source+n)&65535);q=video.physical(regs['ds'],(target+n)&65535)
            current,wanted=work[p],work[q]
            if rgb:
                a=current if current<128 else current-256;c=wanted if wanted<128 else wanted-256
                changed|=a!=c;work[p]=(a+(1 if c>a else -1)*min(2,abs(c-a)))&255
            else:
                s=dict(ax=current,bx=wanted,bp=0,flags=2);value=0
                for channel in (0,1,2):
                    s.update(ax=(s['ax']&0xff00)|current,bx=(s['bx']&0xff00)|wanted)
                    s,_=channels.mathematical(s,s['flags'],channel);value|=s['ax']&255
                changed|=bool(s['bp']);work[p]=value
        if not changed:break
        for _ in range(1 if rgb else 3):wait()
    if events!=b.port_rows:fail(case['name']+': independent output/status stream differs')
    writer,row=(0x5624,0x562c) if rgb else (0x55e1,0x55e9)
    waits=(0x5631,) if rgb else (0x55ee,0x55f1,0x55f4)
    if calls.get(writer)!=passes or calls.get(row)!=passes or any(calls.get(p,0)!=passes-1 for p in waits):fail('Independent pass/wait counts differ')
    # The independent model owns palette data/I/O; every stack byte is still
    # compared without masking in the separate full original/native check.
    for delta in range(-16,0):
        p=video.physical(regs['ss'],(regs['sp']+delta)&65535);work[p]=b.memory[p]
    if work!=b.memory:fail(case['name']+': independent palette/data footprint differs')
    if result['es']!=regs['es'] or result['si']!=source or result['di']!=target or result['cx']!=16:fail('Independent final saved fields differ')
    return passes


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ctypes.CDLL(str(build(Path(directory)/f'palette-transition-m{mutation}.dll',mutation,'palette_transition')))
        self.core=self.lib.lmn_transition_palette_core
        self.core.argtypes=[video.MEM,ctypes.c_uint16,ctypes.POINTER(video.State),ctypes.c_int,ctypes.POINTER(status.Ports),ctypes.POINTER(common.RasterBus)];self.core.restype=channels.Result
        self.adapter=self.lib.lmn_transition_palette_adapter
        self.adapter.argtypes=[video.MEM,ctypes.POINTER(video.Regs),ctypes.c_int,ctypes.POINTER(status.Ports),ctypes.POINTER(common.RasterBus)];self.adapter.restype=None


def equal_trace(a,b,label):
    common.require(a.count==b.count and a.digest.digest()==b.digest.digest(),label+': event order differs')
    common.require(not any((x^y)&m for x,y,m in zip(a.flags,b.flags,b.masks)),label+': event flags differ')


def compare(native,case,core):
    memory,regs,flags=prepare(case);b,result,mask,st,sites,edges,boundary,calls,prefix=original(case,memory,regs,flags,core)
    passes=independent(case,memory,regs,flags,b,result,calls,prefix)
    kind=case.get('kind')
    if case.get('change_frame'):
        if b.frame_hits!=1 or (st,result['ip'])!=(case['want_status'],(case['change_frame'][0]&0xff00)|1):fail('Changed transition child frame not exercised')
    if 'want_status' in case and st!=case['want_status']:fail('Expected transition stop not exercised')
    if kind=='saved-es' and result['es']!=0x4567:fail('Live savedES not exercised')
    if kind=='saved-cx' and result['cx']!=1:fail('Live savedCX not exercised')
    if kind=='saved-si' and result['si']!=0x4000:fail('Live savedSI not exercised')
    if kind=='saved-step-di' and (not b.step_effect or result['di']!=0x5000):fail('Live step savedDI not exercised')
    if kind=='saved-step-si' and (not b.step_effect or result['si']!=0x4000):fail('Live step savedSI not exercised')
    if kind=='saved-step-cx' and (not b.step_effect or result['cx']!=1):fail('Live step savedCX not exercised')
    if kind=='mode-flip' and not st and core and result['ip']!=RETURNS[case['mode']==4]:fail('Mode was not selected once')
    if kind=='outer-ret-high' and not core and result['ip']!=0x5ad1:fail('Live outerRET not exercised')
    if kind=='source-word-high' and (prefix is None or prefix['si']!=0x1100):fail('Live source word high byte not exercised')
    if kind=='pop-es' and result['es']!=regs['es']:fail('Actual outer savedES not restored')
    if native:
        fallback=not(case.get('change_frame') or kind in ('vga-data','vga-stack','outer-ret-high','source-word-high','pop-es','saved-step-di','saved-step-si','saved-step-cx'))
        for null in ((False,True) if fallback else (False,)):
            d=Backend(memory,case,regs,True);bus=d.bus();service=d.ports()
            if core:
                out=native.core(video.buffer(d.memory),regs['cs'],ctypes.byref(video.to_state(dict(regs,flags=flags))),case['entry'],video.pointer(service),None if null else ctypes.byref(bus))
                actual=dict(video.state_dict(out.state),cs=out.code_segment,ip=out.continuation)
                common.require(out.status==st,case['name']+': status differs')
            else:
                r=video.Regs(**regs,flags=flags);native.adapter(video.buffer(d.memory),ctypes.byref(r),case['entry'],video.pointer(service),None if null else ctypes.byref(bus))
                actual={n:getattr(r,n) for n in (*oracle.REG_NAMES,'flags')}
            common.require(all(actual[n]==result[n] for n in oracle.REG_NAMES) and not((actual['flags']^result['flags'])&mask),case['name']+': CPU/flags differ '+str({n:(actual[n],result[n]) for n in (*oracle.REG_NAMES,'flags') if actual[n]!=result[n]}))
            common.require(d.memory==b.memory and d.vga.state()==b.vga.state(),case['name']+': fullRAM/VGA differs')
            equal_trace(d.io_trace,b.io_trace,case['name']+' ports')
            if not null:equal_trace(d.trace,b.trace,case['name']+' bus')
    return dict(name=case['name'],core=core,passes=passes,status=st,boundary=boundary,sites=sorted(sites),edges=sorted(edges),calls={f'{p:04X}':n for p,n in calls.items()},events=b.trace.count)


def input_hashes(native=False):
    paths=set(rows.input_hashes(native))|set(ports.input_hashes(native))|{'tests/palette_transition.py','docs/palette-transition.md'}
    paths|={'tests/verification.py','tests/minimap_vga.py','tools/difftest.py','src/input_menu_and_retry.asm','src/palette_frontends.asm','c/lemmings_sym.h','c/regs.h'}
    if native:
        for source in source_files('palette_transition'):
            paths.add(source.relative_to(ROOT).as_posix())
            if source.with_suffix('.h').is_file():paths.add(source.with_suffix('.h').relative_to(ROOT).as_posix())
    if native:paths|={'c/palette_transition.c','c/palette_transition.h','c/display_status.c','c/display_status.h'}
    # Palette domains/fixtures use literal instruction ranges and generated C
    # offsets. Imported drawing fixtures load unused symbol dictionaries, but
    # no palette behavior consumes their ledger annotations. Keep the actual
    # header/ASM/oracle dependencies; status-only acceptance must not stale it.
    paths.discard('metadata/symbols.json')
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def worker(directory=None,part=0):
    common.MAX_VGA_EVENTS=100000
    channels.identity()
    if any(IMAGE[p:p+len(code)]!=code for p,code in BLOCKS) or len(LOCAL)!=82:fail('Pinned transition bytes/boundaries differ')
    before=input_hashes(directory is not None);native=Native(directory) if directory else None;results=[]
    for case in cases():
        if case['seed']%2!=part:continue
        for core in (False,True):results.append(compare(native,case,core))
        gc.collect()
    mutants=[]
    if native and part==0:
        for mutation,name in ((1,'e0-m2-pair-00-09'),(2,'e0-m4-pair-80-7f'),(3,'e0-m2-mode-flip'),
                              (4,'e0-m2-saved-cx'),(5,'e0-m4-saved-es'),(6,'changed-55e4')):
            case=next(c for c in cases() if c['name']==name)
            try:compare(Native(directory,mutation),case,True)
            except common.Mismatch as e:mutants.append(dict(mutation=mutation,case=name,reason=str(e),completed=True))
            else:fail(f'Palette transition mutant{mutation} survived')
    if before!=input_hashes(directory is not None):fail('Transition inputs changed')
    path=Path(directory)/f'part-{part}.json' if directory else BUILD/f'palette-transition-original-part-{part}.json'
    write_json(path,dict(cases=results,mutants=mutants,input_hashes=before))
    print(f'PASS palette transition part{part}: {len(results)}boundaries,{len(mutants)}mutants',flush=True)


def run(original_only=False):
    if not original_only:SPLIT_REPORT.unlink(missing_ok=True)
    report=ORIGINAL_REPORT if original_only else REPORT;report.unlink(missing_ok=True);before=input_hashes(not original_only);deadline=time.monotonic()+660
    try:
        with temporary_build_directory(prefix='palette-transition-',parent=BUILD) as directory:
            reports=[]
            for part in (0,1):
                remain=deadline-time.monotonic()-10
                if remain<=0:fail('Transition campaign deadline exhausted')
                run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker','-' if original_only else directory,str(part)],cwd=ROOT,timeout=min(240,remain),memory_mib=384)
                reports.append(read_json(BUILD/f'palette-transition-original-part-{part}.json' if original_only else Path(directory)/f'part-{part}.json'))
            if not original_only:
                run_bounded([sys.executable,str(Path(__file__).resolve()),'--split-worker',directory],cwd=ROOT,timeout=720,memory_mib=384,check=True)
        if input_hashes(not original_only)!=before or any(r['input_hashes']!=before for r in reports):fail('Transition reports stale')
        results=[c for r in reports for c in r['cases']];sites={p for c in results for p in c['sites']};edges={tuple(e) for c in results for e in c['edges']};mutants=[m for r in reports for m in r['mutants']]
        if sites!=set(INS) or edges!=EDGES:fail(f'Transition coverage incomplete {set(INS)-sites}/{EDGES-edges}')
        write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(cases()),boundary_fixtures=len(cases()),cases=results,caller_bytes=157,caller_sites=82,
            translated_code_bytes=0 if original_only else 157,native_code_ranges=[] if original_only else [[p,p+len(code)] for p,code in BLOCKS],caller_instruction_addresses=sorted(LOCAL),
            executed_instruction_addresses=sorted(sites),caller_branch_edges=sorted(LOCAL_EDGES),branch_edges=sorted(edges),mutation_count=len(mutants),mutations_detected=mutants,input_hashes=before,c_coverage_claimed=not original_only,
            limits=dict(campaign_seconds=660,worker_seconds=240,windows_process_mib=384,windows_tree_mib=640,instructions_each=2000000,events_each=600000,io_events_each=100000),
            domain='531E/536C full output/step/status transitions, independent palette/IObehavior model and full native/original RAM/CPU/phaseflags/orderedbus/VGA; live saves, child returns/status, once-selected mode and before-wait JZ. Intact decoded instructions/sameCS/TFclear/quiescentIRQ; opaque finite byte providers, no hardware timing or segment-limit claim; arbitrary nonconvergence stays unbounded.'))
        print(f'PASS palette transition {"original" if original_only else "C"}: {len(cases())}x2fixtures,82caller/{len(sites)}integratedsites,{len(edges)}edges,{len(mutants)}mutants',flush=True)
    except BaseException:report.unlink(missing_ok=True);raise


# Incremental migration: the added briefing cluster uses the shared executor,
# canonical bus, guarded native callbacks and comparator. Existing legacy cases
# remain as their unchanged regression campaign; no new CPU engine is added.
SPLIT_RANGES=((0x46A2,0x46EB),(0x5329,0x536C),(0x53CA,0x53E6),(0x53E7,0x53F6))
SPLIT_OWN={i.address:i for a,b in SPLIT_RANGES for i in shared.MD.disasm(IMAGE[a:b],a)}
SPLIT_EXTRA=((0x5569,0x55B6),(0x53F6,0x53FB),(0x5401,0x5417),(0x5418,0x5424),(0x4DEF,0x4DF7),(0x4DF8,0x4E37))
SPLIT_INS=SPLIT_OWN|rows.INS|ports.INS|{i.address:i for a,b in SPLIT_EXTRA for i in shared.MD.disasm(IMAGE[a:b],a)}
SPLIT_EDGES=shared.direct_jump_edges(SPLIT_OWN)
SPLIT_REPORT=BUILD/'split-palette-differential.json'

def split_cases():
    specs=[]
    for entry in (0,1):
        for mode in (2,4,0x104):
            for first,second in ((0,0),(0,1),(1,0),(1,1)):
                for count in (1,7,16):specs.append(dict(name=f'pair-e{entry}-m{mode}-{first}{second}-n{count}',kind='pair',entry=entry,mode=mode,first=first,second=second,count=count))
    for kind in ('pair','upper','refresh','fade'):
        for mode in (2,4,0x104):
            for patch in ('none','sp-zero','sp-ffff','data-a20','df'):
                specs.append(dict(name=f'{kind}-m{mode}-'+patch,kind=kind,entry=0,mode=mode,patch=patch))
    for entry in (0,1):
        for patch in ('saved-marker','mode-flip','stack-alias','table-high'):
            specs.append(dict(name=f'pair-e{entry}-'+patch,kind='pair',entry=entry,patch=patch))
    specs += [dict(name='pair-frame-alias',kind='pair',entry=0,patch='frame-alias',expected=5),dict(name='pair-saved-count',kind='pair',entry=1,patch='saved-count',second=1),
        dict(name='pair-unchecked-target',kind='pair',entry=1,bx=0xFF01),
        dict(name='pair-unchecked-second-target',kind='pair',entry=1,bx=0x01FF,second=1),
        dict(name='refresh-saved-port',kind='refresh',patch='saved-port'),
        dict(name='refresh-low-wrap',kind='refresh',base_port=0x3FC),
        dict(name='refresh-base-flip',kind='refresh',patch='base-flip')]
    for mode in (2,4):
        for first,second in ((0,0),(0,1),(1,0),(1,1)):
            specs.append(dict(name=f'fade-m{mode}-{first}{second}',kind='fade',mode=mode,first=first,second=second))
        for kind in ('upper','refresh','fade'):
            specs.append(dict(name=f'{kind}-m{mode}-no-input',kind=kind,mode=mode,missing_in=True,control=0,expected=1))
            specs.append(dict(name=f'{kind}-m{mode}-no-output',kind=kind,mode=mode,missing_out=True,expected=2))
        specs.append(dict(name=f'fade-m{mode}-no-clear-bus',kind='fade',mode=mode,missing_clear=True,expected=7))
    for kind,entry,ret,depth in (('pair',0,0x5330,4),('pair',0,0x5341,4),('pair',1,0x5352,6),('pair',1,0x5362,4),
             ('refresh',0,0x46D2,4),('refresh',0,0x46E9,2),('fade',0,0x46A5,2),('fade',0,0x46AB,2),('fade',0,0x46B4,2)):
        specs.append(dict(name=f'split-changed-{ret:04x}',kind=kind,entry=entry,frame=(ret,depth),expected=5))
    for mode,ret,depth,expected in ((2,0x564E,8,4),(2,0x567C,10,3),(4,0x56ED,6,4)):
        specs.append(dict(name=f'split-inner-{ret:04x}',kind='pair',mode=mode,frame=(ret,depth),expected=expected))
    # Full zero-count witnesses exercise first-count forwarding and actual saved
    # DX->CX forwarding. Only core repeats: ordinary cases test the outer RET.
    for mode in (2,4):
        specs += [dict(name=f'pair-m{mode}-zero-first',kind='pair',mode=mode,entry=0,count=0,zero=True),
                  dict(name=f'pair-m{mode}-zero-second',kind='pair',mode=mode,entry=1,count=1,dx=0,zero=True)]
    return [dict(entry=0,mode=2,first=0,second=0,count=2,dx=2,load=shared.LOADS[n%3],seed=0x532900+n,patch='none',flags=0x2D7)|c for n,c in enumerate(specs)]

def split_setup(c):
    memory,device=shared.initial_memory(c);ds=0xFFFF if c['patch']=='data-a20' else 0x4000
    start=shared.physical(ds,0);end=start+65536
    if end<=shared.SIZE:memory[start:end]=bytes(65536)
    else:memory[start:]=bytes(shared.SIZE-start);memory[:end-shared.SIZE]=bytes(end-shared.SIZE)
    r=shared.default_regs(c['load'],c['seed'],ds=ds,ss=0x7000,sp=0 if c['patch']=='sp-zero' else 65535 if c['patch']=='sp-ffff' else 0x8000,flags=c['flags']|(0x400 if c['patch']=='df' else 0))
    r.update(ip={'pair':0x5329 if c['entry']==0 else 0x534B,'upper':0x53CA,'refresh':0x46B9,'fade':0x46A2}[c['kind']],cx=c['count'],dx=c['dx'],bx=c.get('bx',0x0201),ax=0xB000)
    ptrs=(0x3000,0x4000,0x5000,0x6000,0x6100,0x6200,0x6300,0x7000)
    for table in (0x52D4,0x52E4):
        for slot,ptr in enumerate(ptrs):shared.put16(memory,r['cs'],table+2*slot,ptr,device)
    for ptr,value in ((0x3000,c['first']),(0x3100,c['first']),(0x7000,c['second'])):
        for n in range(128):shared.sync_memory_byte(memory,device,ds,ptr+n,value)
    shared.put16(memory,ds,0x1F7C,c['mode'],device);shared.put16(memory,ds,0x1FDA,c.get('base_port',0x3D4),device)
    shared.sync_memory_byte(memory,device,ds,0x200C,c.get('control',255))
    if c['patch'] in ('stack-alias','frame-alias'):r.update(ss=ds,sp=0x3004 if c['patch']=='frame-alias' else 0x7002)
    shared.put16(memory,r['ss'],r['sp'],0xEED1,device)
    return memory,r,device

class SplitAccess(shared.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=6_000_000 if c.get('zero') else 500_000,packed_events=True)
        self.port_index=0;self.slot_reads=0;self.first_output=False
    def access(self,kind,address,flags,mask=shared.FLAGS,value=None):
        c=self.c;r=self.r;patch=c['patch'];slot=shared.physical(r['ss'],(r['sp']-2)&65535)
        if kind=='read' and address==slot and patch=='saved-marker':
            self.slot_reads+=1
            if self.slot_reads==2:self.patch(r['ss'],(r['sp']-2)&65535,0x357E,'saved-marker')
        if kind=='read' and address==shared.physical(r['ss'],(r['sp']-4)&65535) and patch=='saved-count' and patch not in self.providers:
            self.patch(r['ss'],(r['sp']-4)&65535,1,'saved-count')
        if kind=='read' and patch=='mode-flip' and patch not in self.providers and address==shared.physical(r['ss'],(r['sp']-(4 if c['entry']==0 else 6))&65535):
            self.patch(r['ds'],0x1F7C,4 if c['mode']!=4 else 2,patch)
        got=super().access(kind,address,flags,mask,value)
        if c.get('frame') and 'frame' not in self.providers:
            expected,depth=c['frame'];at=shared.physical(r['ss'],(r['sp']-depth)&65535)
            if kind=='write' and address==at and value==(expected&255):self.patch(r['ss'],(r['sp']-depth)&65535,(expected&0xFF00)|1,'frame')
        if kind=='read' and patch=='table-high' and patch not in self.providers and address==shared.physical(r['cs'],0x52E4 if c['mode']==4 else 0x52D4):
            self.patch(r['cs'],(0x52E4 if c['mode']==4 else 0x52D4)+1,0x31,patch,word=False)
        return got
    def inp(self,port,flags,mask=shared.FLAGS):
        if port==0x3C5:value=0x93
        else:
            shared.check(self.port_index<24000,'finite split palette status schedule exhausted')
            value=(0,9,9,0)[self.port_index%4];self.port_index+=1
        self.cursor+=1;self.emit('in',port,value,flags,mask);return value
    def out(self,port,value,flags,mask=shared.FLAGS):
        self.emit('out8',port,value,flags,mask)
        if not self.first_output:
            self.first_output=True
            if self.c['patch']=='saved-port':self.patch(self.r['ss'],(self.r['sp']-2)&65535,0x3BA,'saved-port')
            if self.c['patch']=='base-flip':self.patch(self.r['ds'],0x1FDA,0x3B4,'base-flip')
    def out_word(self,port,value,flags,mask=shared.FLAGS):
        shared.check(port in (0x3C4,0x3CE),'unexpected split palette word output')
        self.emit('out',port,value,flags,mask);self.device.out(port,value,flags)

class SplitMachine(shared.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        frames=[];failed=[]
        def before(m,i):
            if c.get('missing_clear') and i.address==0x4DF8:m.stop(7);return True
            if i.mnemonic=='in' and c.get('missing_in'):m.stop(1);return True
            if i.mnemonic=='out' and i.operands[-1].size==1 and c.get('missing_out'):m.stop(2);return True
            if i.mnemonic=='call':frames.append((i.address,(i.address+i.size)&65535))
            return False
        def expected(m,off):
            shared.check(bool(frames),'undeclared split-palette child return');f=frames.pop();failed[:]=[f];return {f[1]}
        def changed(m,off):
            owner=failed[-1][0]
            return 5 if owner in SPLIT_OWN else 4 if owner in rows.LOCAL else 3
        ends={'pair':{0x534A,0x536B},'upper':{0x5446,0x5506},'refresh':{0x46EA},'fade':{0x4E36}}
        super().__init__(c,memory,r,device,core,instructions=SPLIT_INS,access=SplitAccess(c,memory,r,device),
            outer_returns=lambda m,p:p in ends[c['kind']] and not frames,
            child_returns={p:expected for p,i in SPLIT_INS.items() if i.mnemonic=='ret'},changed_return_status=changed,
            before=before,max_steps=30_000_000 if c.get('zero') else 2_000_000)

class SplitPublishResult(ctypes.Structure):
    _fields_=[('registers',shared.Regs),('status',ctypes.c_uint16)]

class SplitNative:
    def __init__(self,directory,mutation=0):
        self.lib=ctypes.CDLL(str(build(Path(directory)/f'split-palette-m{mutation}.dll',mutation,'palette_transition')))
        self.functions={}
        for kind,name in (('pair','step_split_palette'),('refresh','refresh_split_palette'),('fade','fade_split_palette')):
            for core,suffix in ((True,'core'),(False,'adapter')):
                fn=getattr(self.lib,'lmn_'+name+'_'+suffix);fn.restype=channels.Result
                if core:fn.argtypes=[shared.MEM,ctypes.c_uint16,ctypes.POINTER(video.State)]+([ctypes.c_int] if kind=='pair' else [ctypes.POINTER(shared.Ports)])+[ctypes.POINTER(shared.Bus)]
                else:fn.argtypes=[shared.MEM,ctypes.POINTER(shared.Regs)]+([ctypes.c_int] if kind=='pair' else [ctypes.POINTER(shared.Ports)])+[ctypes.POINTER(shared.Bus)]
                self.functions[kind,core]=fn
        for core,suffix in ((True,'core'),(False,'adapter')):
            fn=getattr(self.lib,'lmn_publish_palette_'+suffix);fn.restype=SplitPublishResult
            # Explicit 30-byte register/status API; shared provides the CPU packet.
            self.functions['upper',core]=fn
    def run(self,c,memory,r,device,core):
        import copy
        memory,device=bytearray(memory),copy.deepcopy(device);access=SplitAccess(c,memory,r,device);cb=shared.NativeCallbacks(access,missing_in=c.get('missing_in'),missing_out=c.get('missing_out'))
        if c.get('missing_clear'):cb.bus.out_word=shared.OUT()
        mem=(ctypes.c_uint8*shared.SIZE).from_buffer(memory);regs=shared.Regs(**r)
        if c['kind']=='upper':
            fn=self.functions['upper',core];fn.argtypes=[shared.MEM,ctypes.POINTER(shared.Regs),ctypes.c_int,ctypes.POINTER(shared.Ports),ctypes.POINTER(shared.Bus)]
            out=fn(mem,ctypes.byref(regs),4,ctypes.byref(cb.ports),ctypes.byref(cb.bus));actual={n:getattr(out.registers,n) for n in shared.REG_NAMES}
        else:
            fn=self.functions[c['kind'],core];arg=c['entry'] if c['kind']=='pair' else ctypes.byref(cb.ports)
            if core:out=fn(mem,r['cs'],ctypes.byref(video.to_state(r)),arg,ctypes.byref(cb.bus));actual=dict(video.state_dict(out.state),cs=out.code_segment,ip=out.continuation)
            else:out=fn(mem,ctypes.byref(regs),arg,ctypes.byref(cb.bus));actual={n:getattr(regs,n) for n in shared.REG_NAMES}
        return dict(regs=actual,status=out.status,memory=memory,device=device,events=access.events,providers=access.providers,cursor=access.cursor)

def split_compare(native,c,core):
    import copy
    memory,r,device=split_setup(c);ref=SplitMachine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    shared.check(ref['status']==c.get('expected',0),c['name']+': unexpected split status')
    if not ref['status'] and c['kind']=='pair' and c['patch']=='none' and not c.get('zero') and 'bx' not in c:
        changed=bool(c['first'] or c['second']);shared.check(bool(ref['regs']['flags']&64)!=changed,'split pair OR/ZF differs')
        shared.check((ref['regs']['ax']&255)==int(changed),'split pair AL marker differs')
    if c['patch']=='saved-marker':shared.check(ref['regs']['bx']==0x357E,'split final POP BX not live')
    if c.get('frame'):shared.check('frame' in ref['providers'],'split frame mutation not exercised')
    if native:shared.compare_states(c['name'],native.run(c,memory,r,device,core),ref)
    return ref

SPLIT_MUTANTS=((101,'split-changed-5330'),(102,'pair-e0-saved-marker'),(103,'pair-saved-count'),
    (104,'pair-e1-m2-00-n1'),(105,'refresh-saved-port'),(106,'refresh-low-wrap'),(107,'refresh-m2-none'),
    (108,'upper-m4-none'),(109,'upper-m2-none'),(110,'fade-m2-11'),(111,'refresh-m2-none'),
    (112,'pair-unchecked-second-target'),(113,'fade-m2-none'))

def split_worker(directory):
    before=input_hashes(True);native=SplitNative(directory);sites=set();edges=set();observations=[]
    for c in split_cases():
        for core in ((True,) if c.get('zero') else (False,True)):
            ref=split_compare(native,c,core);sites.update(ref['sites']);edges.update(ref['edges'])
            observations.append(dict(case=c['name'],core=core,steps=ref['steps'],events=len(ref['events']),status=ref['status']))
            del ref;gc.collect()
        print('CHECKED '+c['name'],flush=True)
    shared.check(set(SPLIT_OWN)<=sites,'split palette sites missing')
    shared.check(SPLIT_EDGES<=edges,'split palette outcomes missing')
    mutants=[];lookup={c['name']:c for c in split_cases()}
    for mutation,name in SPLIT_MUTANTS:
        try:split_compare(SplitNative(directory,mutation),lookup[name],True)
        except shared.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise shared.OracleFailure(f'split palette mutant{mutation} survived')
        gc.collect()
    shared.check(before==input_hashes(True),'split palette inputs changed')
    write_json(SPLIT_REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(split_cases()),comparison_count=len(observations),
        own_known_bytes=sum(i.size for i in SPLIT_OWN.values()),known_connected_bytes=sum(i.size for i in SPLIT_INS.values()),
        native_code_ranges=[list(r) for r in SPLIT_RANGES],executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(SPLIT_OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(SPLIT_EDGES),instruction_steps=sum(r['steps'] for r in observations),ordered_bus_events=sum(r['events'] for r in observations),
        mutation_count=len(mutants),mutations=mutants,input_hashes=before,rows=observations,
        limits=dict(worker_seconds=720,process_tree_commit_mib=384,instructions_each=2_000_000,events_each=500_000,zero_instructions_each=30_000_000,zero_events_each=6_000_000,status_inputs_each=24000),
        domain='Native5329/534B row pairs,53CA upper-eight writer,46B9 raster split and46A2 fade->clear tail; shared verification.py exact original execution/bus/callback/comparison. Full zero-count forwarding,live DS/ES/SS/flags/actual RET,changed frames,opaque finite ports and explicit clear-bus seam. No hardware timing,IRQ or complete level-start claim.'))
    print(f'PASS split palette: {len(observations)} comparisons,{len(set(SPLIT_OWN)&sites)} own sites,{len(SPLIT_EDGES)} outcomes,{len(mutants)} mutants',flush=True)

if __name__=='__main__':
    args=sys.argv[1:]
    if len(args)==2 and args[0]=='--split-worker':split_worker(args[1])
    elif len(args)==3 and args[0]=='--worker':worker(None if args[1]=='-' else args[1],int(args[2]))
    elif args==['--original-only']:run(True)
    elif not args:run()
    else:raise SystemExit('Unexpected palette transition arguments')

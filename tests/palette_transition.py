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
from cbuild import build
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
    if native:paths|={'c/palette_transition.c','c/palette_transition.h','c/display_status.c','c/display_status.h'}
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
    report=ORIGINAL_REPORT if original_only else REPORT;report.unlink(missing_ok=True);before=input_hashes(not original_only);deadline=time.monotonic()+660
    try:
        with temporary_build_directory(prefix='palette-transition-',parent=BUILD) as directory:
            reports=[]
            for part in (0,1):
                remain=deadline-time.monotonic()-10
                if remain<=0:fail('Transition campaign deadline exhausted')
                run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker','-' if original_only else directory,str(part)],cwd=ROOT,timeout=min(240,remain),memory_mib=384)
                reports.append(read_json(BUILD/f'palette-transition-original-part-{part}.json' if original_only else Path(directory)/f'part-{part}.json'))
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


if __name__=='__main__':
    args=sys.argv[1:]
    if len(args)==3 and args[0]=='--worker':worker(None if args[1]=='-' else args[1],int(args[2]))
    elif args==['--original-only']:run(True)
    elif not args:run()
    else:raise SystemExit('Unexpected palette transition arguments')

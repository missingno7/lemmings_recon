"""Bounded bridge composition; INT62 is an explicit external pre-IRET provider."""
import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tests'), str(ROOT/'tools')]
import vga_mirrors as leaf
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from unicorn import UC_HOOK_INTR

IMAGE, MASK, SIZE, FLAGS = leaf.IMAGE, leaf.MASK, leaf.SIZE, leaf.FLAGS
REGS, IDS, Regs, Bus, MEM = leaf.REG_NAMES, leaf.REG_IDS, leaf.Regs, leaf.Bus, leaf.MEM
IF, TF, AF, ARITH = 0x200, 0x100, 0x10, 0x8D5
START, IRET, END = 0xF70, 0xF9F, 0xFA0
PARENT = {i.address:i for i in leaf.MD.disasm(IMAGE[START:END], START)}
INS = PARENT | leaf.RESTORE_INS
EDGES = {(0xF8F,0xF91),(0xF8F,0xF9D),(0xF96,0xF98),(0xF96,0xF9D)}
REPORT = BUILD/'mouse-irq-bridge-differential.json'
ORIGINAL = BUILD/'mouse-irq-bridge-original-differential.json'
MAX_STEPS, MAX_EVENTS, SECONDS, MEMORY_MIB = 192, 256, 420, 384
require, check, Mismatch, Failure = leaf.require, leaf.check, leaf.Mismatch, leaf.OracleFailure
physical, put16, get16 = leaf.physical, leaf.put16, leaf.get16


class Result(ct.Structure):
    _fields_ = [('registers',Regs),('status',ct.c_uint16),('service_status',ct.c_uint16)]


CALLBACK = ct.CFUNCTYPE(ct.c_uint16,ct.c_void_p,MEM,ct.POINTER(Regs),ct.POINTER(Bus))


class Service(ct.Structure):
    _fields_ = [('context',ct.c_void_p),('interrupt62',CALLBACK),
                ('code_segment',ct.c_uint16),('instruction_pointer',ct.c_uint16)]


def inc8(flags, before, delta):
    after = (before+delta)&255
    bits = (4 if after.bit_count()%2==0 else 0) | (0x40 if after==0 else 0) | (after&0x80)
    if delta==1:
        bits |= (0x10 if (before&15)==15 else 0) | (0x800 if before==0x7F else 0)
    else:
        bits |= (0x10 if (before&15)==0 else 0) | (0x800 if before==0x80 else 0)
    return (flags&~0x8D4)|bits


def cases():
    out = [dict(name=f'load-{load:04x}',load=load) for load in leaf.LOADS]
    out += [dict(name=f'counter-{a:02x}-{b:02x}',count=a,second=b)
            for a,b in ((0,0x7F),(0xFF,0xFF),(0x80,0x80),(1,1))]
    out += [dict(name='gate-ff',gate=0xFF),dict(name='gate-one',gate=1),
            dict(name='returned-ds',returned_ds=0x4100,other_count=1,other_second=0x80),
            dict(name='returned-ds-gate',returned_ds=0x4100,other_count=3),
            dict(name='returned-es',returned_es=0x6C32),
            dict(name='new-stack',new_stack=(0x6500,0x6000),saved_ax=0xBEEF,saved_ds=0x7132),
            dict(name='new-stack-a20',new_stack=(0xFFFF,0x000F),saved_ax=0xCAFE),
            dict(name='sp-two',sp=2),dict(name='sp-ffff',sp=0xFFFF),
            dict(name='stack-a20',ss=0xFFFF,sp=0x0011),
            dict(name='vga-stack',ss=0xA000,sp=0x8000,seed=0xF711,expected=4),
            dict(name='saved-ax',saved_ax=0xBE31),dict(name='saved-ds',saved_ds=0x4212),
            dict(name='changed-nested-ip',nested_ip=0xD123,expected=3),
            dict(name='changed-nested-cs',nested_cs=0x7123,expected=3),
            dict(name='changed-child-ret',provider='child-ret',expected=4),
            dict(name='changed-outer-frame',outer_patch=(0xB123,0x3123,0x0FD7)),
            dict(name='outer-reserved-flags',outer_patch=(0xB123,0x3123,0xF02A)),
            dict(name='service-stop',service_status=0x1234,expected=2),
            dict(name='no-service',no_service=True,expected=1),
            dict(name='unbound-segment',vector_cs=0x7101,expected=1),
            dict(name='unbound-offset',vector_ip=0x0222,expected=1),
            dict(name='vector-frame-alias',ss=0,sp=0x190,live_flags=3,post_vector=True),
            dict(name='late-data-operand',provider='data-operand',operand_segment=0x4200),
            dict(name='if-df',live_flags=0x6D7,nested_flags=0x6D7),
            dict(name='provider-live-flags',provider_flags=0x06D7,provider_cs=0x7B00,provider_ip=0x1111),
            dict(name='provider-gate',provider_gate=0xFF),
            dict(name='native-initializer-chain',initialize=True,ss_fixed=True)]
    return [dict(load=0x1010,seed=0xF700+i)|c for i,c in enumerate(out)]


def setup(case):
    mem,device = leaf.initial_memory(case)
    load = case['load']; game = (load+0x9A9)&0xFFFF
    fixed = leaf.fixed_segment(load)
    ss = fixed if case.get('ss_fixed') else case.get('ss',0x5000)
    regs = leaf.default_regs(load,case['seed'],ss=ss,sp=case.get('sp',0x9000),
                             flags=case.get('live_flags',0x00D7))
    regs.update(ip=START)
    regs['flags'] = (regs['flags']&0x7ED5)|2  # hardware-entry domain: TF clear
    leaf.seed_mirrors(mem,device,fixed,case['seed'])
    outer = (0xD00D,0x3210,0x0ED7)
    for n,value in enumerate(outer): put16(mem,ss,(regs['sp']+2*n)&0xFFFF,value,device)
    mem[physical(load,0x83BE)] = case.get('gate',0)
    data = case.get('operand_segment',game)
    mem[physical(data,0x2002)] = case.get('count',0)
    mem[physical(data,0x2003)] = case.get('second',0)
    if 'returned_ds' in case:
        mem[physical(case['returned_ds'],0x2002)] = case.get('other_count',1)
        mem[physical(case['returned_ds'],0x2003)] = case.get('other_second',0x80)
    put16(mem,0,0x188,case.get('vector_ip',0x0200))
    put16(mem,0,0x18A,case.get('vector_cs',0x7100))
    binding = (0x7100,0x0200)
    if case.get('post_vector'):
        f = inc8(regs['flags'],case.get('count',0),1)
        f = inc8(f,case.get('second',0),1)
        binding = (f,load)
    if case.get('initialize'):
        put16(mem,0x40,0x63,0x03D4)
        put16(mem,fixed,0xE,0xC35A)
        put16(mem,fixed,0x8000,0xB001)
    return mem,regs,device,binding


class Access(leaf.Access):
    def __init__(self,case,memory,regs,device):
        super().__init__(case,memory,regs,device)
        self.service_events=[]; self.bridge_stack=None
        self.external_events=0;self.transport_events=0

    def access(self,kind,address,flags,mask=FLAGS,value=None):
        if len(self.events)>=MAX_EVENTS: raise Failure('mouse bridge event budget exhausted')
        # The inherited budget is lower and also remains a strict fail-stop guard.
        result=super().access(kind,address,flags,mask,value)
        if (kind=='write' and self.case.get('provider')=='data-operand' and
            address==((physical(self.regs['ss'],(self.regs['sp']-4)&0xFFFF)+1)&MASK) and
            'data-operand' not in self.providers):
            self._provider_word(self.regs['cs'],0xF73,self.case['operand_segment'],'data-operand')
        return result

    def out_word(self,port,value,flags,mask=FLAGS):
        # Override the leaf-specific provider dispatcher; only declared bridge writes.
        if len(self.events)>=MAX_EVENTS: raise Failure('mouse bridge event budget exhausted')
        self.device.out(port,value,flags)
        self.events.append(('out',port,value,flags,mask))
        if self.case.get('provider')=='child-ret' and 'child-ret' not in self.providers:
            ss,sp=self.bridge_stack
            self._provider_word(ss,(sp-4)&0xFFFF,0xD234,'child-ret')

    def word_read(self,ss,sp,flags,mask=FLAGS):
        at=physical(ss,sp)
        lo=self.access('read',at,flags,mask)
        hi=self.access('read',(at+1)&MASK,flags,mask)
        return lo|(hi<<8)

    def word_write(self,ss,sp,value,flags,mask=FLAGS):
        at=physical(ss,sp)
        self.access('write',at,flags,mask,value&255)
        self.access('write',(at+1)&MASK,flags,mask,value>>8)
        self._sync(at,self.memory[at]);self._sync((at+1)&MASK,self.memory[(at+1)&MASK])


def external(access,r):
    """Constructed external body, stops before IRET; no original body is claimed."""
    case=access.case;event_start=len(access.events)
    access.service_events.append(dict(entry=dict(r),frame=[
        get16(access.memory,r['ss'],(r['sp']+i)&0xFFFF) for i in range(0,16,2)]))
    r.update(ax=0xA1B2,bx=0xB3C4,cx=0xC5D6,dx=0xD7E8,si=0x1A2B,di=0x3C4D,bp=0x5E6F,
             ds=case.get('returned_ds',r['ds']),es=case.get('returned_es',0x4567))
    for n,key in (('flags','provider_flags'),('cs','provider_cs'),('ip','provider_ip')):
        if key in case:r[n]=case[key]
    if 'provider_gate' in case:
        address=physical(access.regs['cs'],0x83BE)
        access.memory[address]=case['provider_gate'];access._sync(address,case['provider_gate'])
        access.providers.add('service-gate')
    if 'new_stack' in case:
        old_ss,old_sp=r['ss'],r['sp']
        words=[access.word_read(old_ss,(old_sp+i)&0xFFFF,r['flags']) for i in range(0,16,2)]
        r['ss'],r['sp']=case['new_stack']
        for i,value in enumerate(words):access.word_write(r['ss'],(r['sp']+2*i)&0xFFFF,value,r['flags'])
    changes={0:case.get('nested_ip'),2:case.get('nested_cs'),4:case.get('nested_flags'),
             6:case.get('saved_ax'),8:case.get('saved_ds')}
    if 'outer_patch' in case:
        changes.update(dict(zip((10,12,14),case['outer_patch'])))
    for offset,value in changes.items():
        if value is not None: access.word_write(r['ss'],(r['sp']+offset)&0xFFFF,value,r['flags'])
    access.bridge_stack=(r['ss'],(r['sp']+6)&0xFFFF)
    status=case.get('service_status',0)
    access.service_events[-1].update(before_iret=dict(r),status=status)
    access.external_events+=len(access.events)-event_start
    return status


class OriginalMachine(leaf.Original):
    def __init__(self,memory,device):
        super().__init__(memory,device)
        self.cpu.hook_add(UC_HOOK_INTR,self._interrupt)

    def state(self):return {n:self.cpu.reg_read(IDS[n])&0xFFFF for n in REGS}
    def set_state(self,r):
        for n in REGS:self.cpu.reg_write(IDS[n],r[n])

    def _code(self,cpu,address,size,_):
        cur=self.current; r=self.state(); off=r['ip']
        if self.previous:
            at,ins=self.previous
            if at==0x58D1 and (r['cs']!=cur['load'] or off!=0xF9C):
                cur['status']=4;self.stopped=True;cpu.emu_stop();return
            if at in (0xF8F,0xF96):cur['edges'].add((at,off))
            if ins.mnemonic.lower() in ('inc','dec'):cur['mask']|=0x8D4
            else:cur['mask']=self._after_mask(ins,cur['mask'])
        if r['cs']!=cur['load'] or off not in INS:
            self._fail(f"escaped identified bridge domain {r['cs']:04X}:{off:04X}");return
        if cur['core'] and off==IRET:
            self.stopped=True;cpu.emu_stop();return
        ins=INS[off]
        expected=bytearray(cur['loaded'][off:off+ins.size])
        if off==0xF72 and cur['case'].get('provider')=='data-operand':
            expected[1:3]=cur['case']['operand_segment'].to_bytes(2,'little')
        check(bytes(cpu.mem_read(physical(r['cs'],off),ins.size))==expected,
              f'{cur["case"]["name"]}: original code guard {off:04X}')
        cur['flags']=r['flags'];cur['access'].current_flags=r['flags']
        cur['access'].current_mask=cur['mask']
        self.previous=(off,ins);cur['sites'].add(off);cur['steps']+=1
        if cur['steps']>MAX_STEPS:self._fail('mouse original step budget exhausted')

    def _interrupt(self,cpu,number,_):
        cur=self.current; access=cur['access']; r=self.state()
        if number==1 and self.previous and self.previous[0]==IRET:
            self.stopped=True;return
        check(number==0x62,'unexpected debug/external interrupt in bridge body')
        check(r['ip']==0xF81,'original INT62 resume differs')
        old_cs=r['cs']; entry_flags=r['flags']
        transport_start=len(access.events)
        for i,value in enumerate((entry_flags,old_cs,0xF81)):
            r['sp']=(r['sp']-2)&0xFFFF
            access.word_write(r['ss'],r['sp'],value,r['flags'],cur['mask'])
            if i==0:r['flags']&=~(IF|TF)
        r['cs']=access.word_read(0,0x18A,r['flags'])
        r['ip']=access.word_read(0,0x188,r['flags'])
        access.transport_events+=len(access.events)-transport_start
        if cur['case'].get('no_service') or (r['cs'],r['ip'])!=cur['binding']:
            cur['status']=1;self.set_state(r);self.stopped=True;cpu.emu_stop();return
        cur['service_status']=external(access,r)
        if cur['service_status']:
            cur['status']=2;self.set_state(r);self.stopped=True;cpu.emu_stop();return
        values=[];transport_start=len(access.events)
        for _ in range(3):
            values.append(access.word_read(r['ss'],r['sp'],r['flags']))
            r['sp']=(r['sp']+2)&0xFFFF
        access.transport_events+=len(access.events)-transport_start
        r['ip'],r['cs']=values[:2];r['flags']=(values[2]&0x7FD5)|2
        cur['mask']=FLAGS;cur['flags']=r['flags']
        self.set_state(r)
        if (r['cs'],r['ip'])!=(old_cs,0xF81):
            cur['status']=3;self.stopped=True;cpu.emu_stop()

    def run_bridge(self,case,memory,regs,device,binding,core):
        self.previous=None;self.stopped=False;self.failure=None
        access=Access(case,memory,regs,device);access.sync_uc=self._sync
        cur=dict(case=case,load=case['load'],loaded=leaf.loaded_image(case['load']),
                 kind='bridge',core=core,mask=FLAGS,flags=regs['flags'],access=access,
                 code_bytes={physical(case['load'],at+i) for at,ins in INS.items() for i in range(ins.size)},
                 steps=0,sites=set(),edges=set(),binding=binding,status=0,service_status=0)
        self.current=cur;self.set_state(regs)
        for _ in range(MAX_STEPS+3):
            if self.stopped:break
            r=self.state();self.cpu.emu_start(physical(r['cs'],r['ip']),0,count=1)
            self.cpu.ctl_remove_cache(0,SIZE*2)
            if self.previous and self.previous[0]==0x58D1:
                returned=self.state()
                if (returned['cs'],returned['ip'])!=(case['load'],0xF9C):
                    cur['status']=4;self.stopped=True
            if self.previous and self.previous[0]==IRET and not core:
                self.stopped=True;cur['mask']=0xFFFF
        check(self.stopped and self.failure is None,self.failure or 'original did not stop')
        check(bytes(self.cpu.mem_read(0,SIZE))==bytes(memory),'canonical original RAM diverged')
        return dict(regs=self.state(),status=cur['status'],service_status=cur['service_status'],
                    memory=bytearray(memory),device=copy.deepcopy(device),events=access.events,
                    services=access.service_events,providers=access.providers,mask=cur['mask'],
                    external_events=access.external_events,transport_events=access.transport_events,
                    sites=cur['sites'],edges=cur['edges'],steps=cur['steps'])


def die(error):
    try:os.write(2,(str(error)+'\n').encode('utf8',errors='backslashreplace'))
    finally:os._exit(86 if 'budget' in str(error) else 87)


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'mouse-{mutation}.dll',mutation,'mouse_irq_bridge')))
        self.functions=[]
        for name in ('core','adapter'):
            fn=getattr(self.lib,'lmn_mouse_irq_bridge_'+name)
            fn.argtypes=[MEM,ct.POINTER(Regs),ct.POINTER(Service),ct.POINTER(Bus)]
            fn.restype=Result;self.functions.append(fn)
        self.init=self.lib.lmn_initialize_vga_register_mirrors_adapter
        self.init.argtypes=[MEM,ct.POINTER(Regs),ct.POINTER(Bus)];self.init.restype=ct.c_uint16

    def run(self,case,memory,regs,device,binding,core):
        access=Access(case,memory,regs,device)
        def read(_,mem,address,flags):
            try:return access.access('read',address,flags)
            except BaseException as e:die(e)
        def write(_,mem,address,value,flags):
            try:access.access('write',address,flags,value=value)
            except BaseException as e:die(e)
        def out(_,port,value,flags):
            try:access.out_word(port,value,flags)
            except BaseException as e:die(e)
        def service(_,mem,pregs,pbus):
            try:
                r={n:getattr(pregs.contents,n) for n in REGS};status=external(access,r)
                for n in REGS:setattr(pregs.contents,n,r[n])
                return status
            except BaseException as e:die(e)
        callbacks=(leaf.READ(read),leaf.WRITE(write),leaf.OUT(out),CALLBACK(service))
        bus=Bus(None,*callbacks[:3]);bound=Service(None,callbacks[3],*binding)
        ram=(ct.c_uint8*SIZE).from_buffer(memory);r=Regs(**regs)
        value=self.functions[0 if core else 1](ram,ct.byref(r),None if case.get('no_service') else ct.byref(bound),ct.byref(bus))
        return dict(regs={n:getattr(value.registers,n) for n in REGS},status=value.status,
                    service_status=value.service_status,memory=bytearray(memory),device=copy.deepcopy(device),
                    events=access.events,services=access.service_events,providers=access.providers)


def prepare_initializer(case,memory,device,native=None):
    regs=leaf.default_regs(case['load'],0x04F9,ss=leaf.fixed_segment(case['load']),sp=0x8000,
                           ds=(case['load']+0x9A9)&0xFFFF,es=0x40,flags=0x6D7)
    regs['ip']=leaf.INIT
    if native is None:
        access=leaf.Access(case,memory,regs,device)
        result=leaf.Original(memory,device).run(case,'initialize',regs,access,core=False)
        return result['regs'],result['events'],result['sites'],result['steps']
    access=Access(case,memory,regs,device)
    def read(_,mem,address,flags):
        try:return access.access('read',address,flags)
        except BaseException as e:die(e)
    def write(_,mem,address,value,flags):
        try:access.access('write',address,flags,value=value)
        except BaseException as e:die(e)
    def out(_,port,value,flags):
        try:access.out_word(port,value,flags)
        except BaseException as e:die(e)
    cb=(leaf.READ(read),leaf.WRITE(write),leaf.OUT(out));bus=Bus(None,*cb)
    ram=(ct.c_uint8*SIZE).from_buffer(memory);r=Regs(**regs)
    check(native.init(ram,ct.byref(r),ct.byref(bus))==0,'initializer status')
    return {n:getattr(r,n) for n in REGS},access.events,set(),0


def compare_state(got,want,label):
    require(got['status']==want['status'],label+': status differs')
    require(got['service_status']==want['service_status'],label+': service status differs')
    require(got['memory']==want['memory'],label+': RAM differs')
    for n in REGS:
        mask=want['mask'] if n=='flags' else 0xFFFF
        require(((got['regs'][n]^want['regs'][n])&mask)==0,f'{label}: {n} {got["regs"][n]:04X}/{want["regs"][n]:04X}')
    require(len(got['events'])==len(want['events']),label+': bus count differs')
    for i,(a,b) in enumerate(zip(got['events'],want['events'])):
        require(a[:3]==b[:3] and ((a[3]^b[3])&b[4])==0,f'{label}: event{i} {a}/{b}')
    require(got['services']==want['services'],label+': full external service boundary differs')
    require(got['providers']==want['providers'],label+': provider effects differ')
    require(got['device'].state()==want['device'].state(),label+': VGA state differs')
    require([e[:3] for e in got['device'].trace]==[e[:3] for e in want['device'].trace],label+': VGA trace differs')


def independent_transport(case,regs,expected,binding):
    flags=inc8(inc8(regs['flags'],case.get('count',0),1),case.get('second',0),1)
    words=(flags,regs['cs'],0xF81)
    expected_pushes=[]
    sp=(regs['sp']-4)&0xFFFF
    for word in words:
        sp=(sp-2)&0xFFFF;at=physical(regs['ss'],sp)
        expected_pushes.extend((('write',at,word&255),('write',(at+1)&MASK,word>>8)))
    check([e[:3] for e in expected['events'][8:14]]==expected_pushes,
          case['name']+': independently predicted INT frame writes differ')
    check([e[:2] for e in expected['events'][14:18]]==[
        ('read',0x18A),('read',0x18B),('read',0x188),('read',0x189)],
        case['name']+': current IVT must be sampled CS-before-IP after the frame')
    if expected['services']:
        service=expected['services'][0];entry=service['entry']
        desired=dict(regs,ax=case.get('operand_segment',(case['load']+0x9A9)&0xFFFF),
                     ds=case.get('operand_segment',(case['load']+0x9A9)&0xFFFF),
                     ss=regs['ss'],sp=sp,cs=binding[0],ip=binding[1],flags=flags&~(IF|TF))
        check(entry==desired,case['name']+': full service entry state differs from independent prediction')
        check(service['frame']==[0xF81,regs['cs'],flags,regs['ax'],regs['ds'],0xD00D,0x3210,0x0ED7],
              case['name']+': independent nested/saved/outer frame layout differs')


def compare(native,case,core):
    memory,regs,device,binding=setup(case)
    original_memory=bytearray(memory);original_device=copy.deepcopy(device)
    actual_memory=bytearray(memory);actual_device=copy.deepcopy(device)
    prelude_sites=set();prelude_steps=0;prelude_events=0
    if case.get('initialize'):
        ref_regs,ref_events,prelude_sites,prelude_steps=prepare_initializer(case,original_memory,original_device)
        prelude_events=len(ref_events)
        if native:
            got_regs,got_events,_,_=prepare_initializer(case,actual_memory,actual_device,native)
            require(actual_memory==original_memory and actual_device.state()==original_device.state(),'direct initializer handoff differs')
            require(got_regs==ref_regs and got_events==ref_events,'initializer boundary differs')
        fixed=leaf.fixed_segment(case['load'])
        check(get16(original_memory,fixed,0x10)==0xFF08 and get16(original_memory,fixed,0xE)==0xC35A,'literal initializer gap/overwrite lost')
    expected=OriginalMachine(original_memory,original_device).run_bridge(case,original_memory,regs,original_device,binding,core)
    check(expected['status']==case.get('expected',0),case['name']+': declared original stop differs')
    independent_transport(case,regs,expected,binding)
    if case['name']=='vga-stack':
        gc_regs=expected['device'].gc
        care=gc_regs[7]&15
        check(gc_regs[5]&8 and care and not(gc_regs[2]&care),
              'VGA return witness must compare cared planes against zero')
        at=physical(regs['ss'],(regs['sp']-8)&0xFFFF)-0xA0000
        check(all(p[at:at+2]==bytes((0x9C,0x0F)) for p in expected['device'].planes),
              'VGA child CALL word is not the literal 0F9C in every plane')
        check(expected['regs']['ip']==((~0x0F9C)&0xFFFF),
              'Read-mode-one must invert the actual 0F9C child return')
    if native:
        actual=native.run(case,actual_memory,regs,actual_device,binding,core)
        compare_state(actual,expected,case['name'])
    bridge_steps=expected['steps']
    expected['sites']|=prelude_sites;expected['steps']+=prelude_steps
    return (dict(case=case['name'],boundary='core' if core else 'adapter',status=expected['status'],
                sites=sorted(expected['sites']),edges=sorted(expected['edges']),events=len(expected['events']),
                steps=expected['steps'],service_count=len(expected['services']),prelude_sites=sorted(prelude_sites))
                |dict(bridge_instruction_steps=bridge_steps,initializer_instruction_steps=prelude_steps,
                      initializer_events=prelude_events,declared_int62_transport_events=expected['transport_events'],
                      declared_external_provider_events=expected['external_events']))


def hashes():
    paths=set(leaf.hash_inputs())|{'tests/mouse_irq_bridge.py','c/mouse_irq_bridge.c','c/mouse_irq_bridge.h'}
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def publish(path,before,rows,mutations=None):
    sites={p for r in rows for p in r['sites']};edges={tuple(e) for r in rows for e in r['edges']}
    check(set(PARENT)<=sites and edges==EDGES,'parent sites/branch outcomes incomplete')
    check(set(leaf.RESTORE_INS)<=sites,'actual mirror child incomplete')
    report=dict(image='main',image_sha256=sha(IMAGE),entry=START,end=END,
                translated_parent_bytes=48,parent_instruction_sites=20,
                case_count=len(cases()),comparison_count=len(rows),ordered_events=sum(r['events'] for r in rows),
                initializer_comparison_count=sum(bool(r['prelude_sites']) for r in rows),
                native_mirror_call_count=sum(leaf.RESTORE in r['sites'] for r in rows) if mutations is not None else 0,
                parent_executed_instruction_addresses=sorted(sites&set(PARENT)),
                mirror_executed_instruction_addresses=sorted(sites&set(leaf.RESTORE_INS)),
                initializer_executed_instruction_addresses=sorted(sites&set(leaf.INIT_INS)),
                initializer_ordered_events=sum(r['initializer_events'] for r in rows),
                declared_int62_transport_events=sum(r['declared_int62_transport_events'] for r in rows),
                declared_external_provider_events=sum(r['declared_external_provider_events'] for r in rows),
                identified_body_bus_events=sum(r['events']-r['declared_int62_transport_events']-
                                               r['declared_external_provider_events'] for r in rows),
                executed_instruction_addresses=sorted(sites),instruction_steps=sum(r['steps'] for r in rows),
                parent_branch_edges=sorted(edges),parent_branch_edge_count=len(edges),
                original_only=mutations is None,mutation_count=len(mutations or []),mutations=mutations or [],
                rows=rows,input_hashes=before,
                limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,instructions=MAX_STEPS,bus_events=MAX_EVENTS),
                scope='Identified bridge, native mirror child and optional initializer; INT62 frame transport/provider is declared, no external body/IRQ/debug timing coverage')
    write_json(path,report)
    print(f'PASS mouse bridge: {len(rows)} boundaries, {len(sites)} integrated sites, {len(edges)} edges, {len(mutations or [])} mutants',flush=True)


def worker(directory=None,snapshot=None):
    before=hashes()
    if snapshot:check(before==json.loads(Path(snapshot).read_text()),'input snapshot differs')
    native=Native(directory) if directory else None
    rows=[]
    for case in cases():
        for core in (True,False):rows.append(compare(native,case,core))
        gc.collect();print('CHECKED '+case['name'],flush=True)
    mutations=None
    if native:
        mutations=[];by_name={c['name']:c for c in cases()}
        witnesses=((1,'vector-frame-alias',True),(2,'load-1010',True),(3,'unbound-segment',True),
                   (4,'returned-ds',True),(5,'returned-es',True),(6,'new-stack',True),
                   (7,'saved-ax',True),(8,'gate-ff',True),(9,'changed-child-ret',True),(10,'new-stack',False))
        for number,name,core in witnesses:
            try:compare(Native(directory,number),by_name[name],core)
            except Mismatch as error:mutations.append(dict(mutation=number,case=name,core=core,completed=True,mismatch=str(error)))
            else:raise Failure(f'mutant {number} survived')
            gc.collect()
    check(before==hashes(),'campaign inputs changed')
    publish(REPORT if native else ORIGINAL,before,rows,mutations)


def main():
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3]);return
    if sys.argv[1:]==['--original-only']:
        run_bounded([sys.executable,__file__,'--original-worker'],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True);return
    if sys.argv[1:]:raise SystemExit('usage: mouse_irq_bridge.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='mouse-irq-bridge-',parent=BUILD) as directory:
        snapshot=Path(directory)/'input-hashes.json';snapshot.write_text(json.dumps(hashes(),sort_keys=True))
        run_bounded([sys.executable,__file__,'--worker',directory,str(snapshot)],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()

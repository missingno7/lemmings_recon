"""Bounded 2E04 C/ASM comparison with composed pinned INT61 handlers.

Unicorn exposes INT as a hook. Frame/IVT transport is an explicit architecture
boundary (documented in entity-countdown.md), not executed CPU microcode.
The main routine and installed driver instructions execute independently.
"""
import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tests')]
import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from unpack import ASSET, unpack, relocated
import sound_latches as sound
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_16
from unicorn import UC_HOOK_CODE, UC_HOOK_INTR, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE

SIZE, MASK, FLAGS = sound.SIZE, sound.MASK, sound.FLAGS
LOGIC = FLAGS & ~0x10
ENTRY, END = 0x2E04, 0x2EC0
RETURNS = {0x2E62, 0x2EBF}
RESUMES = {0x2E5E, 0x2EB2}
CAP, STEPS = 256, 180
IMAGE, ORACLE = unpack(ASSET.read_bytes())
REPORT = BUILD/'entity-countdown-differential.json'
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {i.address:i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
DRIVER_INS = {n:{i.address:i for i in MD.disasm(image[:0x3A], 0)}
              for n,(image,_) in sound.IMAGES.items() if n in sound.TAILS}

class Call(ct.Structure):
    _fields_ = [(n,ct.c_uint16) for n in ('value','data_segment','code_segment',
        'stack_segment','stack_offset','record_cursor','flags')]

class Result(ct.Structure):
    _fields_ = [(n,ct.c_uint16) for n in ('value','data_segment','code_segment',
        'stack_offset','record_cursor','flags','continuation','status')]

class InterruptCall(ct.Structure):
    _fields_ = [(n,ct.c_uint16) for n in ('value','data_segment','code_segment',
        'stack_segment','stack_offset','flags','return_offset')]

class InterruptResult(ct.Structure):
    _fields_ = [(n,ct.c_uint16) for n in ('value','data_segment','code_segment',
        'stack_offset','flags','continuation','status')]

class Binding(ct.Structure):
    _fields_ = [('driver_segment',ct.c_uint16),('driver_kind',ct.c_uint16)]

def p(seg, off):
    return sound.physical(seg,off)

def put(memory, seg, off, value):
    sound.word(memory,p(seg,off),value & 0xFFFF)

def get(memory, seg, off):
    address=p(seg,off)
    return memory[address] | memory[(address+1)&MASK]<<8

def cases():
    rows=[dict(name=f'countdown-{n:02x}',count=n) for n in range(256)]
    for driver in sound.TAILS:
        for bits in (0,*[1<<n for n in range(16)],0x5404,0xFFFF):
            rows.append(dict(name=f'{driver}-flags-{bits:04x}',count=1,bits=bits,driver=driver))
        for bits in (0,4):
            for flags in (2,3,0x202,0x402,0x602,0xED7):
                rows.append(dict(name=f'{driver}-flags-{bits:04x}-incoming-{flags:04x}',
                                 count=1,bits=bits,driver=driver,flags=flags))
            for enabled,options in ((0,3),(1,3),(0x7F,3),(0xFF,0),(0xFF,4),
                                    (0xFF,1),(0xFF,2),(0xFF,0x80),(0xFF,0xFF)):
                rows.append(dict(name=f'{driver}-gate-{bits}-{enabled}-{options}',
                                 count=1,bits=bits,driver=driver,enabled=enabled,options=options))
            latch=sound.TAILS[driver][4][1]
            for delta,variant in ((8,'saved-ds-low'),(7,'saved-ds-high'),
                                  (6,'interrupt-ip'),(4,'interrupt-cs'),
                                  (2,'interrupt-flags'),(0,'outer-ret')):
                rows.append(dict(name=f'{driver}-{bits}-latch-{variant}',count=1,
                                 bits=bits,driver=driver,ss=0x7000,sp=latch+delta))
    for bits in (0,4):
        for name,values in (
            ('slot-self-alias',dict(si=0x2A if bits==0 else 0x38,enabled=0)),
            ('slot-read-provider',dict(effect='slot',enabled=0)),
            ('slot-ret-provider',dict(effect='outer-ret',enabled=0)),
            ('gate-live-provider',dict(effect='enable',enabled=0)),
            ('options-live-provider',dict(effect='options',options=0)),
            ('post-sound-record',dict(effect='record')),
            ('post-sound-ds',dict(effect='saved-ds')),
            ('changed-iret',dict(effect='iret')),
            ('iret-live-flags',dict(effect='flags')),
            ('late-vector',dict(effect='vector')),
            ('unbound-offset',dict(vector_ip=0x1234)),
            ('unbound-segment',dict(vector_cs=0x7100)),
            ('missing-binding',dict(binding=False)),
            ('invalid-binding',dict(binding_kind=3)),
            ('ivt-stack-alias',dict(ss=0,sp=0x18A)),
            ('sp-zero',dict(sp=0)),('sp-one',dict(sp=1)),
            ('sp-ffff',dict(sp=0xFFFF)),
            ('physical-word-wrap',dict(ss=0xFFFF,sp=0x17)),
            ('record-offset-wrap',dict(si=0xFFF9)),
            ('record-physical-wrap',dict(ds=0xFFFF,si=0x7)),
            ('record-gate-alias',dict(si=0x1FEC,enabled=0)),
            ('record-option-alias',dict(si=0x2583,options=0xFF)),
            ('vga-record',dict(ds=0xA000,vga='record')),
            ('vga-stack',dict(ss=0xA000,vga='stack')),
            ('vga-stack-live-read',dict(ss=0xA000,vga='stack-map-zero')),
        ):
            rows.append(dict(name=f'{bits}-{name}',count=1,bits=bits,**values))
    return rows

def transport_cases():
    rows=[]
    for driver in sound.TAILS:
        for command in (0,1,2,3,4,5,6,0x84,0xFF):
            rows.append(dict(name=f'transport-{driver}-{command:02x}',driver=driver,
                             transport=True,command=command,count=1,bits=4))
        rows.append(dict(name=f'transport-{driver}-trap-clear',driver=driver,
                         transport=True,command=4,count=1,bits=4,flags=0x703))
    return rows

def setup(case):
    rng=random.Random(0x2E0400+case.get('count',1))
    memory=bytearray(rng.randbytes(SIZE))
    load=case.get('load',0x1010)
    loaded=relocated(IMAGE,ORACLE['relocations'],load)
    base=(load<<4)&MASK
    first=min(len(loaded),SIZE-base)
    memory[base:base+first]=loaded[:first]
    memory[:len(loaded)-first]=loaded[first:]
    driver=case.get('driver','adlib')
    driver_image=sound.IMAGES[driver][0]
    memory[0x70000:0x70000+len(driver_image)]=driver_image
    regs={n:rng.randrange(65536) for n in sound.NAMES}
    regs.update(ax=0xA537,cs=load,ds=case.get('ds',0x3800),ss=case.get('ss',0x5000),
                sp=case.get('sp',0x8200),si=case.get('si',0x410),ip=ENTRY,
                flags=case.get('flags',2|(case['count']*0x95&0xED5)))
    if case.get('transport'):
        regs['ax']=case['command']<<8|0x0C
        regs['ip']=0x7002
    ds,si=regs['ds'],regs['si']
    put(memory,ds,0x2E,0x6170);put(memory,ds,0x3C,0x6BDB)
    put(memory,ds,si+8,case.get('bits',0))
    memory[p(ds,si+0x20)]=case['count']
    memory[p(ds,si+0x22)]=0xA9
    memory[p(ds,si+0x24)]=0xD7
    memory[p(ds,0x2010)]=case.get('enabled',0xFF)
    memory[p(ds,0x25A7)]=case.get('options',3)
    put(memory,0x6300,si+8,4)
    memory[p(0x6300,si+0x22)]=0xE3
    put(memory,0,0x184,case.get('vector_ip',0))
    put(memory,0,0x186,case.get('vector_cs',0x7000))
    put(memory,regs['ss'],regs['sp'],0xE123)
    device=None
    if case.get('vga'):
        device=MinimapVga(0x2E04,read_map=3)
        device.seq[2]=0 if case['vga']=='stack-map-zero' else 0x0F
        device.gc[0]=device.gc[1]=device.gc[3]=device.gc[5]=0
        device.gc[8]=0xFF
        for plane in device.planes:
            plane[:]=memory[VGA_BASE:VGA_END]
        if case['vga']=='stack-map-zero':
            resume=0x2EB2 if case['bits'] else 0x2E5E
            for delta,value in ((-10,0x7000),(-8,0x6300),(-6,resume),
                                (-4,load),(-2,0x642),(0,0xE123)):
                sound.word(device.planes[3],(regs['sp']+delta)&0xFFFF,value)
    binding=None if case.get('binding') is False else Binding(0x7000,
        case.get('binding_kind',1 if driver=='adlib' else 2))
    return memory,regs,device,binding

class Access:
    def __init__(self,case,memory,regs,device):
        self.case,self.memory,self.regs,self.device=case,memory,regs,device
        self.events,self.used=[],False
        self.mirror=None

    def store(self,address,value):
        address&=MASK
        self.memory[address]=value
        if self.mirror:self.mirror(address,value)

    def modify_word(self,seg,off,value):
        address=p(seg,off)
        self.store(address,value&255);self.store(address+1,value>>8)

    def effect(self,kind,address):
        if self.used:return
        r,c=self.regs,self.case
        ds,si,ss,sp=r['ds'],r['si'],r['ss'],r['sp']
        effect=c.get('effect')
        slot=0x3C if c.get('bits',0)&0x5404 else 0x2E
        if effect in ('slot','vector') and kind=='write' and address==p(ds,si+8):
            if effect=='slot':self.modify_word(ds,slot,0xA5E7)
            else:self.modify_word(0,0x186,0x7100)
        elif effect in ('outer-ret','enable') and kind=='read' and address==p(ds,slot):
            if effect=='outer-ret':self.modify_word(ss,sp,0xE532)
            else:self.store(p(ds,0x2010),255);self.store(p(ds,0x25A7),2)
        elif effect=='options' and kind=='read' and address==p(ds,0x2010):
            self.store(p(ds,0x25A7),2)
        elif effect in ('record','saved-ds','iret','flags') and kind=='write' and address==p(0x7000,sound.TAILS[c.get('driver','adlib')][4][1]):
            if effect=='record':self.modify_word(ds,si+8,c.get('bits',0)^4)
            elif effect=='saved-ds':self.modify_word(ss,sp-8,0x6300)
            elif effect=='iret':self.modify_word(ss,sp-6,0x3456)
            else:self.modify_word(ss,sp-2,0x642)
        else:return
        self.used=True

    def access(self,kind,address,flags,mask=FLAGS,value=None):
        if len(self.events)>=CAP:raise RuntimeError('countdown callback budget exhausted')
        address&=MASK
        if kind=='read':
            self.effect(kind,address)
            value=(self.device.read(self.memory,address,flags) if self.device and
                   VGA_BASE<=address<VGA_END else self.memory[address])
            self.store(address,value)
        else:
            if self.device and VGA_BASE<=address<VGA_END:self.device.write(self.memory,address,value,flags)
            self.store(address,value)
        self.events.append((kind,address,value,flags&0xFFFF,mask))
        if kind=='write':self.effect(kind,address)
        return value

def defined_after(ins,mask):
    if ins.mnemonic in ('test','and','or','xor'):return LOGIC
    if ins.mnemonic=='cmp':return FLAGS
    if ins.mnemonic=='dec':return (FLAGS&~1)|(mask&1)
    if ins.mnemonic=='iret':return FLAGS
    return mask

def original(case,memory,regs,device,binding,core):
    cpu=Uc(UC_ARCH_X86,UC_MODE_16);cpu.mem_map(0,SIZE*2)
    cpu.mem_write(0,bytes(memory));cpu.mem_write(SIZE,bytes(memory))
    for n,v in regs.items():cpu.reg_write(sound.IDS[n],v)
    access=Access(case,memory,regs,device)
    def mirror(address,value):
        cpu.mem_write(address,bytes((value,)));cpu.mem_write(address+SIZE,bytes((value,)))
    access.mirror=mirror
    driver=case.get('driver','adlib')
    current_flags,current_mask=regs['flags'],FLAGS
    previous=None;stopped=False;status=0
    sites=set();child_sites=set();edges=set();child_edges=set();interrupts=[]
    expected_resume=0x7002 if case.get('transport') else None
    current_ins=None

    def read_word(seg,off):
        address=p(seg,off)
        low=access.access('read',address,current_flags,current_mask)
        high=access.access('read',address+1,current_flags,current_mask)
        return low|high<<8

    def interrupt(u,number,_):
        nonlocal current_flags,current_mask,status,stopped,expected_resume
        assert number==0x61, f'Unexpected original interrupt{number:02x}'
        resume=u.reg_read(sound.IDS['ip'])&65535
        expected_resume=resume
        ss,sp=regs['ss'],u.reg_read(sound.IDS['sp'])&65535
        f=u.reg_read(sound.IDS['flags'])&65535
        cs=u.reg_read(sound.IDS['cs'])&65535
        interrupts.append(dict(value=u.reg_read(sound.IDS['ax']),flags=f,sp=sp,resume=resume))
        def push(value):
            nonlocal sp
            sp=(sp-2)&65535;address=p(ss,sp)
            access.access('write',address,current_flags,current_mask,value&255)
            access.access('write',address+1,current_flags,current_mask,value>>8)
        current_flags=f;push(f)
        current_flags=f&~0x300
        u.reg_write(sound.IDS['flags'],current_flags)
        push(cs);push(resume)
        u.reg_write(sound.IDS['sp'],sp)
        # Explicit platform contract; see Intel INT real-address pseudocode.
        target_cs=read_word(0,0x186);target_ip=read_word(0,0x184)
        u.reg_write(sound.IDS['cs'],target_cs);u.reg_write(sound.IDS['ip'],target_ip)
        if (binding is None or binding.driver_kind not in (1,2) or
            target_cs!=binding.driver_segment or target_ip!=0):
            status=1;stopped=True;u.emu_stop()

    def code(u,_address,_size,_):
        nonlocal previous,current_flags,current_mask,current_ins,status,stopped
        cs,off=u.reg_read(sound.IDS['cs']),u.reg_read(sound.IDS['ip'])
        if previous:
            source,pc,ins=previous
            if ins.mnemonic=='ret':
                status=0;stopped=True;u.emu_stop();return
            if ins.mnemonic=='iret':
                if cs!=regs['cs'] or off!=expected_resume:
                    status=3;stopped=True;u.emu_stop();return
                if case.get('transport'):
                    status=0;stopped=True;u.emu_stop();return
            if ins.group(capstone.CS_GRP_JUMP):
                (edges if source=='main' else child_edges).add((pc,off))
            current_mask=defined_after(ins,current_mask)
        current_flags=u.reg_read(sound.IDS['flags'])&65535
        if cs==regs['cs'] and off in INS and not case.get('transport'):
            if core and off in RETURNS:
                status=0;stopped=True;u.emu_stop();return
            ins=INS[off];source='main';sites.add(off)
            expected=IMAGE[off:off+ins.size]
        elif cs==0x7000:
            if off in ({'adlib':(0x115,0xA3,0x3A),'tandysnd':(0x72,0x43,0x31)}[driver]):
                status=2;stopped=True;u.emu_stop();return
            assert off in DRIVER_INS[driver],f'Driver escaped{off:04x}'
            ins=DRIVER_INS[driver][off];source=driver;child_sites.add(off)
            expected=sound.IMAGES[driver][0][off:off+ins.size]
        else:
            raise AssertionError(f'Original escaped{cs:04x}:{off:04x}')
        actual=bytes(u.mem_read((cs<<4)+off,ins.size))
        assert actual==expected,(case['name']+f': forthcoming code {cs:04x}:{off:04x} '
                                 f'{actual.hex()}/{expected.hex()} is outside native scope')
        previous=(source,off,ins);current_ins=ins

    def read(u,_kind,address,size,_value,_):
        for i in range(size):access.access('read',address+i,current_flags,current_mask)

    def write(u,_kind,address,size,value,_):
        for i in range(size):access.access('write',address+i,current_flags,current_mask,(value>>(8*i))&255)

    cpu.hook_add(UC_HOOK_CODE,code);cpu.hook_add(UC_HOOK_INTR,interrupt)
    cpu.hook_add(UC_HOOK_MEM_READ,read);cpu.hook_add(UC_HOOK_MEM_WRITE,write)
    if case.get('transport'):
        # Auxiliary transport call starts at the declared INT boundary. It
        # contributes no synthetic caller instruction to original coverage.
        interrupt(cpu,0x61,None)
    try:
        if not stopped:
            cpu.emu_start((cpu.reg_read(sound.IDS['cs'])<<4)+cpu.reg_read(sound.IDS['ip']),0,count=STEPS)
    except UcError as error:
        raise AssertionError(case['name']+': bounded original failed') from error
    assert stopped,case['name']+': instruction budget/escape failure'
    state={n:cpu.reg_read(sound.IDS[n])&65535 for n in sound.NAMES}
    assert bytes(cpu.mem_read(0,SIZE))==bytes(memory),'Original RAM mirror diverged'
    return dict(memory=bytes(memory),regs=state,device=device,events=access.events,
                status=status,sites=sites,child_sites=child_sites,edges=edges,
                child_edges=child_edges,used=access.used,mask=current_mask,interrupts=interrupts)

class Native:
    def __init__(self,directory,mutation=0,transport_mutation=False):
        cluster='sound_interrupt' if transport_mutation else 'entity_countdown'
        self.lib=ct.CDLL(str(build(Path(directory)/f'{cluster}-{mutation}.dll',mutation,cluster)))
        if not transport_mutation:
            self.lib.lmn_advance_entity_countdown_core.argtypes=[sound.MEM,ct.POINTER(Call),ct.POINTER(Binding),ct.POINTER(sound.Bus)]
            self.lib.lmn_advance_entity_countdown_core.restype=Result
            self.lib.lmn_advance_entity_countdown_adapter.argtypes=[sound.MEM,ct.POINTER(sound.Regs),ct.POINTER(Binding),ct.POINTER(sound.Bus)]
            self.lib.lmn_advance_entity_countdown_adapter.restype=ct.c_uint16
        self.lib.lmn_sound_interrupt61_core.argtypes=[sound.MEM,ct.POINTER(InterruptCall),ct.POINTER(Binding),ct.POINTER(sound.Bus)]
        self.lib.lmn_sound_interrupt61_core.restype=InterruptResult

    def run(self,case,memory,regs,device,binding,core,null=False):
        access=Access(case,memory,regs,device)
        def die(error):
            os.write(2,(str(error)+'\n').encode());os._exit(86)
        def read(_ctx,_mem,address,flags):
            try:return access.access('read',address,flags)
            except BaseException as error:die(error)
        def write(_ctx,_mem,address,value,flags):
            try:access.access('write',address,flags,value=value)
            except BaseException as error:die(error)
        def out(*_args):die('Unexpected countdown port operation')
        callbacks=sound.READ(read),sound.WRITE(write),sound.OUT(out)
        bus=sound.Bus(None,*callbacks)
        ram=(ct.c_uint8*SIZE).from_buffer(memory)
        bind=ct.byref(binding) if binding is not None else None
        r=sound.Regs(**regs)
        if case.get('transport'):
            call=InterruptCall(regs['ax'],regs['ds'],regs['cs'],regs['ss'],regs['sp'],regs['flags'],0x7002)
            result=self.lib.lmn_sound_interrupt61_core(ram,ct.byref(call),bind,None if null else ct.byref(bus))
            r.ax,r.ds,r.cs,r.sp,r.flags,r.ip=result.value,result.data_segment,result.code_segment,result.stack_offset,result.flags,result.continuation
            status=result.status
        elif core:
            call=Call(regs['ax'],regs['ds'],regs['cs'],regs['ss'],regs['sp'],regs['si'],regs['flags'])
            result=self.lib.lmn_advance_entity_countdown_core(ram,ct.byref(call),bind,None if null else ct.byref(bus))
            r.ax,r.ds,r.cs,r.sp,r.si,r.flags,r.ip=result.value,result.data_segment,result.code_segment,result.stack_offset,result.record_cursor,result.flags,result.continuation
            status=result.status
        else:
            status=self.lib.lmn_advance_entity_countdown_adapter(ram,ct.byref(r),bind,None if null else ct.byref(bus))
        return dict(memory=bytes(memory),regs={n:getattr(r,n) for n in sound.NAMES},
                    device=device,events=access.events,status=status,used=access.used)

def compare(native,case,core=True,null=False):
    memory,regs,device,binding=setup(case)
    ref=original(case,bytearray(memory),dict(regs),copy.deepcopy(device),binding,core)
    got=native.run(case,bytearray(memory),dict(regs),copy.deepcopy(device),binding,core,null)
    sound.require(got['status']==ref['status'],case['name']+f': status {got["status"]}/{ref["status"]}')
    if got['memory']!=ref['memory']:
        where=next(i for i,(a,b) in enumerate(zip(got['memory'],ref['memory'])) if a!=b)
        raise sound.Mismatch(case['name']+f': memory {where:05x} {got["memory"][where]:02x}/{ref["memory"][where]:02x}')
    for name in sound.NAMES:
        mask=ref['mask'] if name=='flags' else 65535
        sound.require(((got['regs'][name]^ref['regs'][name])&mask)==0,
                      case['name']+f': {name} {got["regs"][name]:04x}/{ref["regs"][name]:04x}')
    if not null:
        sound.require(len(got['events'])==len(ref['events']),case['name']+': event count differs')
        for a,b in zip(got['events'],ref['events']):
            sound.require(a[:3]==b[:3] and ((a[3]^b[3])&b[4])==0,
                          case['name']+f': event {a}/{b}')
        sound.require(got['used']==ref['used'],case['name']+': provider trigger differs')
    if device:
        sound.require(got['device'].state()==ref['device'].state(),case['name']+': VGA state differs')
        sound.require([(a,b,c) for a,b,c,_ in got['device'].trace]==
                      [(a,b,c) for a,b,c,_ in ref['device'].trace],case['name']+': VGA trace differs')
    if case['name'].startswith('countdown-') and case['count']!=1:
        expected=bytearray(memory);expected[p(regs['ds'],regs['si']+0x20)]=(case['count']-1)&255
        assert bytes(expected)==ref['memory'],'Independent countdown byte expectation differs'
        assert ref['regs']['ax']==((regs['ax']&0xFF00)|1)
        assert not ref['regs']['flags']&0x40
    if '-flags-' in case['name'] and not case.get('transport'):
        # Independent final record/frame layout for the ordinary sound path.
        # The ordered instruction-phase comparison above remains separate.
        expected=bytearray(memory)
        ds,si,ss,sp=regs['ds'],regs['si'],regs['ss'],regs['sp']
        bits=case['bits'];second=bool(bits&0x5404)
        expected[p(ds,si+0x20)]=0
        fields={8:bits|(2 if second else 0x8000),0xA:8,
                0xC:0x180B if second else 0x153B,
                0x10:0x280 if second else 0x5A,
                0x12:0x1E0 if second else 0x3C,
                4:0xFFF0 if second else 0xFFF8,
                6:0xFFE7 if second else 0xFFF6,
                0x14:0x6BDB if second else 0x6170}
        for off,value in fields.items():put(expected,ds,si+off,value)
        for off in (0x28,0x29,0x2A):expected[p(ds,si+off)]=0
        expected[p(ds,si+0x24)]=1
        if second:expected[p(ds,si+0x22)]=0 if bits&4 else 15
        request=12 if second else 5
        expected[p(0x7000,sound.TAILS[case['driver']][4][1])]=request
        pushed_flags=(regs['flags']&~0x8D5)|4
        for off,value in ((-2,pushed_flags),(-4,regs['cs']),
                          (-6,0x2EB2 if second else 0x2E5E),(-8,ds),(-10,0x7000)):
            put(expected,ss,sp+off,value)
        assert bytes(expected)==ref['memory'],'Independent record/interrupt-frame layout differs'
        assert ref['regs']['ax']==0 and ref['regs']['flags']&0x40
    return ref

def input_hashes():
    paths=['c/entity_countdown.c','c/entity_countdown.h','c/sound_interrupt.c','c/sound_interrupt.h',
           'c/sound_latches.c','c/sound_latches.h','c/sound_latches_sym.h','c/regs.h',
           'c/lemmings_sym.h','c/special_blit.h','tools/cbuild.py','tools/difftest.py',
           'tools/bounded_process.py','tools/unpack.py','tools/resources.py','tools/common.py',
           'tests/entity_countdown.py','tests/sound_latches.py','tests/minimap_vga.py',
           'metadata/symbols.json','metadata/oracle.json','metadata/toolchain-lock.json',
           'metadata/sound-oracle.json','src/game_code.asm','src/image_tail.asm',
           'docs/entity-countdown.md','assets/vgalemmi.exe','assets/main.dat']
    for driver in sound.TAILS:
        paths += [f'metadata/{driver}-symbols.json',f'src/sound/{driver}.asm',f'assets/{driver}.dat']
    return {name:sha((ROOT/name).read_bytes()) for name in paths}

def worker(directory):
    before=input_hashes();baseline=Native(directory)
    assert ORACLE==json.loads((ROOT/'metadata/oracle.json').read_text())
    specs=cases();aux=transport_cases();rows=[];sites=set();edges=set();events=0
    child_sites={n:set() for n in sound.TAILS}
    for case in specs:
        for core in (True,False):
            result=compare(baseline,case,core)
            sites.update(result['sites']);edges.update(result['edges'])
            child_sites[case.get('driver','adlib')].update(result['child_sites'])
            events+=len(result['events'])
        rows.append(dict(name=case['name'],status=result['status'],core_and_adapter=True,
                         driver=case.get('driver','adlib'),effect=case.get('effect')))
        gc.collect()
    for case in aux:
        result=compare(baseline,case)
        events+=len(result['events'])
    expected_edges=set()
    for ins in INS.values():
        if ins.group(capstone.CS_GRP_JUMP):
            expected_edges.add((ins.address,ins.operands[0].imm&65535))
            expected_edges.add((ins.address,ins.address+ins.size))
    assert sites==set(INS),(sites^set(INS))
    assert edges==expected_edges,(edges^expected_edges)
    for name in ('countdown-00','countdown-01','countdown-ff','adlib-flags-0004'):
        case=next(c for c in specs if c['name']==name)
        for core in (True,False):compare(baseline,case,core,null=True)
    mutations=[]
    witnesses=[(1,'countdown-00',True),(2,'adlib-flags-0400',True),
               (3,'0-slot-self-alias',True),(4,'4-post-sound-record',True),
               (5,'adlib-gate-0-0-3',True),(6,'countdown-01',True),
               (7,'0-slot-ret-provider',False),(8,'adlib-flags-0000',True)]
    for number,name,core in witnesses:
        mutant=Native(directory,number)
        case=next(c for c in specs if c['name']==name)
        try:compare(mutant,case,core)
        except sound.Mismatch as error:
            mutations.append(dict(kind='countdown',mutation=number,case=name,completed=True,mismatch=str(error)))
        else:raise AssertionError(f'Countdown mutant{number} survived')
        gc.collect()
    int_witnesses=[(1,dict(ss=0,sp=0x18A)),(2,dict(flags=0x602)),
                   (3,dict(effect='iret')),(4,dict(effect='iret')),
                   (5,{}),(6,dict(effect='saved-ds'))]
    for number,values in int_witnesses:
        mutant=Native(directory,number,transport_mutation=True)
        case=dict(name=f'interrupt-mutation-{number}',driver='adlib',transport=True,
                  command=4,count=1,bits=4,**values)
        try:compare(mutant,case)
        except sound.Mismatch as error:
            mutations.append(dict(kind='interrupt',mutation=number,case=case['name'],completed=True,mismatch=str(error)))
        else:raise AssertionError(f'Interrupt mutant{number} survived')
        gc.collect()
    assert before==input_hashes(),'Inputs changed during bounded countdown campaign'
    write_json(REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),
        cases=rows,auxiliary_transport_cases=len(aux),mutation_count=len(mutations),mutations=mutations,
        translated_code_bytes=188,native_code_ranges=[[ENTRY,END]],
        executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),
        child_instruction_addresses={n:sorted(v) for n,v in child_sites.items()},
        total_bus_events=events,input_hashes=before,
        limits=dict(worker_seconds=180,windows_process_mib=384,windows_tree_mib=640,
                    original_instruction_limit=STEPS,native_callback_budget=CAP),
        scope='2E04 and native INT61 driver composition; INT transport declared architecture boundary; no IRQ timing or mutable-code claim'))
    print(f'PASS entity countdown: {len(rows)} core/adapter fixtures, {len(aux)} auxiliary transport calls; '
          f'188 bytes/{len(sites)} sites/{len(edges)} edges; {events} events; {len(mutations)} completed mutants',flush=True)

def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if sys.argv[1:]:raise SystemExit('Unexpected countdown arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-countdown-',parent=BUILD) as directory:
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],
                    cwd=ROOT,timeout=180,memory_mib=384)

if __name__=='__main__':main()

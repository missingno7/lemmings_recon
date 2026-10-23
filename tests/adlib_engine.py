"""Bounded AdLib engine differential: original ADLIB.DAT 0000..059F against
c/adlib_engine.c over one canonical 1 MiB RAM image.

Every INT 61h call enters the driver at offset 0000 with a live interrupt
frame, runs to its actual IRET (or a declared stop) in the shared
verification engine, and the native lmn_adlib_int61_adapter runs the same call
on an identical copy. Compared per call: full RAM, every ordered RAM access
(including stack and return words), every OPL OUT/IN with its port and value,
all registers after IRET (or at the declared stop), status and provider use.

Declared domain: shipped songs/effects through the main program's request
pattern (AH=03 then AH=00 updates, AH=04 effects, AH=02 reset, AH=01
detection), the effect allocator under load, stop/start sequences, and a few
constructed stream states for grammar members no shipped stream contains
(83 STOP) and for the 88..AF corrupted-control escape. A finite OPL provider
supplies IN values (status model for detection, seeded values for delay
reads). Arithmetic flags inside the driver are not part of the bus/port
contract (masked on events; every exit is IRET or a declared stop).
Long songs are advanced by real original/native-compared updates only; no
state is fast-forwarded by a model.
"""
import copy
import ctypes as ct
import functools
import gc
import json
import os
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build
from common import BUILD,sha,write_json
from resources import sound_images

SIZE,MASK,FLAGS=base.SIZE,base.MASK,base.FLAGS
Regs,MEM,REGS=base.Regs,base.MEM,base.REG_NAMES
check,require,Failure,Mismatch=base.check,base.require,base.OracleFailure,base.Mismatch
put16,get16,physical=base.put16,base.get16,base.physical
REPORT=BUILD/'adlib-engine-differential.json'
SECONDS,MEMORY_MIB=1500,768
MAX_STEPS,MAX_EVENTS=400_000,400_000
CONTROL=0x0700            # TF/IF/DF: the only FLAGS bits the bus/port contract carries
LOAD,STACK_SEGMENT,STACK_TOP=0x2911,0x4800,0x7FF0
CALLER_CS,CALLER_IP=0x1010,0x03C1
ESCAPE,RETURN_CHANGED,MISSING_PORT=1,2,3

IMAGE,PIN=sound_images()['adlib']
CODE_RANGES=((0x0000,0x0014),(0x0015,0x006D),(0x00A3,0x00ED),(0x0115,0x03EA),(0x03FA,0x05A0))
TRANSLATED_BYTES=sum(b-a for a,b in CODE_RANGES)
INS={}
for start,end in CODE_RANGES:
    decoded=list(base.MD.disasm(IMAGE[start:end],start))
    check(decoded and decoded[-1].address+decoded[-1].size==end and
          sum(i.size for i in decoded)==end-start,'code range is not whole instructions')
    INS.update((i.address,i) for i in decoded)
VIEWS={p:bytes(IMAGE[p:p+i.size]) for p,i in INS.items()}
RESUMES={(p+i.size)&0xFFFF for p,i in INS.items() if i.mnemonic=='call'}
IRETS={p for p,i in INS.items() if i.mnemonic=='iret'}
CHILD_RETURNS={p:RESUMES for p,i in INS.items() if i.mnemonic=='ret'}
TABLE=[IMAGE[0x3EA+2*k]|IMAGE[0x3EB+2*k]<<8 for k in range(8)]
EDGES=base.direct_jump_edges(INS,external_transfers={0x01EA})|{(0x01EA,t) for t in TABLE}
SITES=set(INS)
# Original identical relocation of the unused main image is cached; every
# driver instruction is checked against its own execution view.
base.loaded_image=functools.lru_cache(maxsize=4)(base.loaded_image)


def word(offset):return IMAGE[offset]|IMAGE[offset+1]<<8


class Opl:
    """Finite OPL2 status provider. 'present' raises T1/IRQ (C0) when timer 1
    is started unmasked and clears on IRQ reset; 'absent' floats at FF;
    'slow' never expires; 'busy' has a stuck IRQ bit (80) before the timer
    test and still reports C0 after it.
    Delay reads return seeded bytes (the driver discards them)."""
    def __init__(self,kind,seed):
        self.kind=kind;self.rng=random.Random(seed);self.index=0
        self.status=0x80 if kind=='busy' else 0
        self.registers=[None]*256
    def out(self,port,value):
        if port==0x388:self.index=value
        elif port==0x389:
            self.registers[self.index]=value
            if self.index==4:
                if value&0x80:self.status=0x80 if self.kind=='busy' else 0
                elif value&1 and not value&0x40 and self.kind in ('present','busy'):self.status=0xC0
    def inp(self,port):
        noise=self.rng.randrange(256)
        if self.kind=='absent':return 0xFF
        if port==0x388:return self.status|(noise&0x1F)
        return noise


class Access(base.BusAccess):
    def __init__(self,c,memory,r,device,opl):
        super().__init__(c,memory,r,device,max_events=MAX_EVENTS,packed_events=True)
        self.opl=opl
    def emit(self,kind,address,value,flags,mask=FLAGS):
        super().emit(kind,address,value,flags,mask&CONTROL)
    def out(self,port,value,flags,mask=FLAGS):
        self.emit('out8',port,value,flags,mask);self.opl.out(port,value)
        if self.c.get('corrupt_return') and 'return' not in self.providers:
            # Detection: frame, PUSH DS, CALL 0559 return word at frame-4.
            self.patch(STACK_SEGMENT,(self.c['sp']-4)&0xFFFF,0xBEEF,'return')
    def inp(self,port,flags,mask=FLAGS):
        value=self.opl.inp(port);self.cursor+=1
        self.emit('in8',port,value,flags,mask);return value


def stop_escape(machine,ins):
    if ins.address==0x01EA and machine.state()['si']>=0x03FA:
        machine.stop(ESCAPE);return True
    return False


class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,opl,core):
        super().__init__(c,memory,r,device,core,instructions=INS,
                         access=Access(c,memory,r,device,opl),outer_returns=IRETS,
                         child_returns=CHILD_RETURNS,max_steps=MAX_STEPS,
                         changed_return_status=RETURN_CHANGED,before=stop_escape,
                         execution_views=VIEWS)


class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'adlib-engine-{mutation}.dll',mutation,'adlib_engine')))
        self.functions={}
        for name in ('int61_adapter','service_core','service_adapter'):
            fn=getattr(self.lib,'lmn_adlib_'+name)
            fn.argtypes=[MEM,ct.POINTER(Regs),ct.POINTER(base.Bus),ct.POINTER(base.Ports)]
            fn.restype=ct.c_uint16
            self.functions[name]=fn
    def run(self,c,memory,r,device,opl,entry):
        access=Access(c,memory,r,device,opl)
        callbacks=base.NativeCallbacks(access,missing_in=c.get('missing_in'),missing_out=c.get('missing_out'))
        ram=(ct.c_uint8*SIZE).from_buffer(memory);reg=Regs(**r)
        status=self.functions[entry](ram,ct.byref(reg),ct.byref(callbacks.bus),ct.byref(callbacks.ports))
        del ram
        return dict(regs={n:getattr(reg,n) for n in REGS},status=status,memory=memory,device=device,
                    events=access.events,providers=access.providers,cursor=access.cursor,opl=access.opl)


# ---------------------------------------------------------------------------
# Fixtures and independent expectations
# ---------------------------------------------------------------------------

def fresh_memory(seed):
    rng=random.Random(seed)
    memory=bytearray(rng.randbytes(SIZE))
    base_address=LOAD<<4
    memory[base_address:base_address+len(IMAGE)]=IMAGE
    return memory


def caller_registers(rng,ax,flags):
    return dict(ax=ax,bx=rng.randrange(0x10000),cx=rng.randrange(0x10000),dx=rng.randrange(0x10000),
                si=rng.randrange(0x10000),di=rng.randrange(0x10000),bp=rng.randrange(0x10000),
                ds=rng.choice((0x3000,0x5A10,0x7123)),es=rng.choice((0x6400,0x3000)),flags=flags)


def interrupt_entry(memory,caller,entry=0):
    """State after INT 61h: frame IP/CS/FLAGS on SS:SP, IF/TF cleared."""
    sp=(STACK_TOP-6)&0xFFFF
    put16(memory,STACK_SEGMENT,sp,CALLER_IP);put16(memory,STACK_SEGMENT,sp+2,CALLER_CS)
    put16(memory,STACK_SEGMENT,sp+4,caller['flags'])
    r=dict(caller);r.update(cs=LOAD,ip=entry,ss=STACK_SEGMENT,sp=sp,flags=caller['flags']&~0x0300)
    return r


def opl_writes(events,status_reads=0):
    """Independent decoding of the port protocol of 0559 and detection."""
    ports=[e for e in events if e[0] in ('out8','in8')]
    writes,reads,i=[],[],0
    while i<len(ports):
        kind,port,value=ports[i][:3]
        if kind=='in8':
            check(port==0x388 and len(reads)<status_reads,'unexpected status read')
            reads.append(value);i+=1;continue
        check(port==0x388 and i+61<=len(ports),'OPL write does not start with OUT 0388')
        delay=ports[i+1:i+13];data=ports[i+13];tail=ports[i+14:i+61]
        check(all(e[0]=='in8' and e[1]==0x388 for e in delay),'address delay is not 12 x IN 0388')
        check(data[0]=='out8' and data[1]==0x389,'data OUT is not port 0389')
        check(all(e[0]=='in8' and e[1]==0x389 for e in tail),'data delay is not 47 x IN 0389')
        writes.append((value,data[2]));i+=61
    return writes,reads


def record(memory,index,field,width=1):
    at=physical(LOAD,0x5AC+0x14*index+field)
    return memory[at] if width==1 else memory[at]|memory[at+1]<<8


def driver_byte(memory,offset):return memory[physical(LOAD,offset)]


def independent(label,before,call,caller,ref,expected_status=0,core=False):
    """Expectations derived from the specification, not from either run."""
    check(ref['status']==expected_status,f'{label}: status {ref["status"]} not {expected_status}')
    if expected_status:return
    out,ah,al=ref['regs'],call>>8,call&255;memory=ref['memory']
    if core:
        check(out['cs']==LOAD and out['ip'] in IRETS and out['sp']==(STACK_TOP-6)&0xFFFF,label+': core IRET boundary')
        check(out['flags']&CONTROL==caller['flags']&CONTROL&~0x0300,label+': core control flags')
    else:
        check((out['cs'],out['ip'],out['sp'])==(CALLER_CS,CALLER_IP,STACK_TOP),label+': IRET frame differs')
        check(out['flags']==(caller['flags']&0x7FD5)|2,label+': IRET flags differ')
    for name in ('bp','ds','es','si','di'):
        check(out[name]==caller[name],f'{label}: {name} not preserved')
    writes,reads=opl_writes(ref['events'],2 if ah==1 else 0)
    if ah==0:
        for name in ('ax','bx','cx','dx'):check(out[name]==caller[name],f'{label}: {name} not preserved')
        check(driver_byte(memory,0xEF)==0,label+': EF left nonzero')
        song=driver_byte(before,0xED)
        if driver_byte(before,0xEE)==0 and 1<=song<=0x15:
            header=word(0xB6C+2*song)
            check(driver_byte(memory,0xEE)==song and driver_byte(memory,0xED)==0,label+': song latches')
            check(driver_byte(memory,0xB6A)==IMAGE[header+4] and get16(memory,LOAD,0xB6C)==IMAGE[header+5],label+': tempo/count')
            packets=[(record(before,k,8),record(before,k,9)) for k in range(9)]
            check(writes[:13]==packets+[(1,0x20),(0xBD,0xC0),(8,0),(4,0x21)],label+': song start OPL sequence')
            for k in range(9):
                mode=record(memory,k,0x10)
                check(mode in (0,1,2) and (k<IMAGE[header+5])==(mode==1),label+': song start modes')
        elif driver_byte(before,0xEE)==0 and song>=0x16:
            check(get16(memory,LOAD,0xED)==0,label+': invalid song did not stop music')
        effect=driver_byte(before,0xF0)
        if 1<=effect<=0x12:
            free=[k for k in (8,7,6,5) if record(before,k,0x10)==0]
            if driver_byte(before,0xEE)==0 and 1<=song<=0x15:free=[8,7,6,5]
            if free:
                check(driver_byte(memory,0xF0)==0 and record(memory,free[0],0x10) in (0,2),label+': effect grant record')
            else:check(driver_byte(memory,0xF0)==effect,label+': unservable effect not latched')
        elif effect:check(driver_byte(memory,0xF0)==effect,label+': invalid effect not latched')
    elif ah==1:
        s1,s2=reads[0]&0xE0,reads[1]&0xE0
        check(out['ax']==0x2100|(1 if s1==0 and s2==0xC0 else 0),label+': detection AX')
        check((out['bx'],out['cx'],out['dx'])==(0x8000|s1,0,0x388),label+': detection BX/CX/DX')
        check(writes==[(4,0x60),(4,0x80),(2,0xFF),(4,0x21),(4,0x60),(4,0x80)],label+': detection writes')
    elif ah==2:
        check(out['ax']==al,label+': reset AX is not the dispatcher-reduced AX')
        for name in ('bx','cx','dx'):check(out[name]==caller[name],f'{label}: {name} not preserved')
        count=get16(before,LOAD,0xB6C)
        packets=[(record(before,k,8),record(before,k,9)) for k in range(count)]
        table=[(IMAGE[0x6D+2*k],IMAGE[0x6E+2*k]) for k in range(27)]
        check(writes==packets+table,label+': reset OPL sequence')
        check(all(record(memory,k,0x10)==0 for k in range(9)),label+': reset modes')
        check(get16(memory,LOAD,0xED)==0 and driver_byte(memory,0xF0)==driver_byte(before,0xF0),label+': reset latches')
    else:
        check(not writes and out['ax']==((call-0x500) if ah>5 else al),label+': latch AX')
        for name in ('bx','cx','dx'):check(out[name]==caller[name],f'{label}: {name} not preserved')
        if ah in (3,4,5):
            check(driver_byte(memory,{3:0xED,4:0xF0,5:0xEE}[ah])==al,label+': latch byte')


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def updates(count):return [0x0000]*count

SERVICE={0:0x0115,1:0x00A3,2:0x003A}
STREAM=0x6000   # constructed bytes beyond the 5670h allocation, same segment


def effect_record(index,stream,instrument=None,countdown=1):
    """Constructed effect-channel state (not produced by any request)."""
    fields=[('record',index,0x10,2,1),('record',index,0x01,countdown,1),
            ('record',index,0x0C,stream,2),('record',index,0x13,0,1)]
    if instrument is not None:fields.append(('record',index,0x02,instrument,2))
    return fields


def cases():
    detect=[0x0100]
    rows=[
        dict(name='detect-present',calls=[0x0100],opl='present'),
        dict(name='detect-absent',calls=[0x0100],opl='absent'),
        dict(name='detect-slow-timer',calls=[0x0100],opl='slow'),
        dict(name='detect-pending-irq',calls=[0x0100],opl='busy'),
        dict(name='detect-missing-in',calls=[0x0100],opl='present',missing_in=True,stop=MISSING_PORT),
        dict(name='detect-missing-out',calls=[0x0100],opl='present',missing_out=True,stop=MISSING_PORT),
        dict(name='reset-fresh-image',calls=[0x0200,0x0000,0x0000]),
        dict(name='latches-and-unknown-services',calls=[0x0305,0x0408,0x0501,0x0677,0x0500,0x0000,0x05FF,0xFF00]),
        # Direct service entries (dispatcher-reduced AH=0): the core stops
        # before the IRET, the service adapter consumes it.
        dict(name='service-cores',entry='service_core',
             calls=[0x0100,0x0200,0x0000,('poke',0xED,0x0B)]+updates(30)+[0x0200]),
        dict(name='service-adapters',entry='service_adapter',
             calls=[0x0100,0x0200,('poke',0xED,0x04)]+updates(30)+[0x0200]),
        # A provider rewrites the live CALL return word of the first 0559 call
        # (stack-alias contract: RET consumes the live word).
        dict(name='provider-changed-return',calls=[0x0100],opl='present',corrupt_return=True,stop=RETURN_CHANGED),
        # Main request pattern: song request then immediate update; effects
        # over the music, five at once to exhaust records 8..5; effect 0F
        # reaches wrapped pitch index F8 (octave byte 0), 02/03 slide 86/87;
        # song 05 reaches wrapped F7/FC; invalid effect 13 stays latched.
        dict(name='song05-effects-over-music',
             calls=detect+[0x0305]+updates(40)+[0x040F]+updates(6)+
                   [0x0402,0x0000,0x0403,0x0000,0x0409,0x0000,0x040B,0x0000,0x0401]+updates(60)+
                   [0x0413,0x0000,0x0400]+updates(20)+[0x0405]+updates(260)),
        # Stop/start: a request while a song is current waits in ED and is
        # discarded by reset; the next song starts from retained records
        # (key-off packets, notes, transposes); an invalid ID stops music.
        dict(name='song-change-retained-fields',
             calls=detect+[0x0301]+updates(70)+[0x030D,0x0000,0x0000,0x0200,0x0000,0x030D]+
                   updates(80)+[0x0316,0x0000,0x0200,0x0316,0x0000,0x0000,0x030A]+updates(60)+
                   [0x0200,0x040F]+updates(30)+[0x0314]+updates(40)),
        # Every effect alone on an idle engine, to its END.
        dict(name='all-effects',calls=detect+[x for e in range(1,0x13) for x in [0x0400|e]+updates(12)]+updates(90)),
        # Whole songs: order lists wrap through the redirect word (command 80
        # at a zero order word), with effects allocated over the music.
        dict(name='song05-order-wrap',calls=detect+[0x0305]+
             [x for k in range(8) for x in [0x0400|(1+2*k)]+updates(410)]),
        dict(name='song0A-order-wrap-4-channels',calls=detect+[0x030A]+updates(3880)),
        # Song 07 ch0 pattern 2179 holds the only shipped level token (B0 6F,
        # after C1 in the same fetch) near update 3072.
        dict(name='song07-level-token',calls=detect+[0x0307]+updates(3140)),
        # Constructed stream states (not game states) for grammar members no
        # shipped stream contains, and for the corrupted-control escape.
        dict(name='constructed-stop-command-83',calls=detect+[0x0305]+updates(12)+
             effect_record(8,STREAM)+[('bytes',STREAM,b'\x83')]+updates(4)),
        dict(name='constructed-escape-88',calls=detect+[0x0305]+updates(5)+
             effect_record(8,STREAM)+[('bytes',STREAM,b'\xe1\x88'),0x0000],stop=ESCAPE),
        dict(name='constructed-escape-af',calls=detect+
             effect_record(6,STREAM)+[('bytes',STREAM,b'\xaf'),0x0000],stop=ESCAPE),
        # Level token first in its fetch: the live caller DX selects the
        # operator registers; instrument pointer 0000 reads driver bytes
        # 000A/000C (level) and 000E (release comparator, FEh).
        dict(name='constructed-level-caller-dx-null-instrument',calls=detect+
             effect_record(7,STREAM,instrument=0)+
             [('bytes',STREAM,bytes((0xB5,0x40,0xE3,0x30,0x82,0x81,0xE2,0x31,0x85)))]+updates(14)),
        # Nonzero instrument release point (+0E); no shipped instrument that
        # is read has one. Effect 09 uses effect instrument 8.
        dict(name='constructed-release-point',calls=detect+
             [('poke',0x54E3+16*7+0x0E,5),0x0409]+updates(60)),
    ]
    return rows


def apply_patch(memory,item):
    if item[0]=='record':
        _,index,field,value,width=item
        at=physical(LOAD,0x5AC+0x14*index+field)
        memory[at]=value&255
        if width==2:memory[(at+1)&MASK]=value>>8
    elif item[0]=='bytes':
        _,offset,data=item
        for k,b in enumerate(data):memory[physical(LOAD,offset+k)]=b
    else:
        _,offset,value=item;memory[physical(LOAD,offset)]=value


def run_case(native,c):
    """Run every call of a case on both sides; returns coverage."""
    rng=random.Random(sha(c['name'].encode()))
    memory=fresh_memory(rng.randrange(1<<30))
    opl=Opl(c.get('opl','present'),rng.randrange(1<<30))
    entry=c.get('entry','int61_adapter')
    core=entry=='service_core'
    sites,edges,steps,events,calls=set(),set(),0,0,0
    last=max(i for i,call in enumerate(c['calls']) if not isinstance(call,tuple))
    for index,call in enumerate(c['calls']):
        if isinstance(call,tuple):
            apply_patch(memory,call);continue
        calls+=1
        flags=rng.choice((0x0202,0x0A93,0x0246,0x0003))
        caller=caller_registers(rng,call,flags)
        if entry!='int61_adapter':caller['ax']=call&0xFF
        r=interrupt_entry(memory,caller,SERVICE[call>>8] if entry!='int61_adapter' else 0)
        device=base.new_device(index)
        start_opl=copy.deepcopy(opl)
        machine=Machine(c|dict(load=LOAD,missing_port_status=MISSING_PORT,sp=r['sp']),bytearray(memory),r,
                        copy.deepcopy(device),copy.deepcopy(start_opl),core)
        ref=machine.run()
        independent(f"{c['name']}#{index}",memory,call,caller,ref,c.get('stop',0) if index==last else 0,core)
        if native:
            actual=native.run(c|dict(sp=r['sp']),bytearray(memory),r,copy.deepcopy(device),
                              copy.deepcopy(start_opl),entry)
            # IRET exits compare every FLAGS bit; core/escape exits the defined
            # flags of the last flag-setting instruction; other stops TF/IF/DF.
            if ref['status']==0 and not core:ref['mask']=FLAGS
            elif ref['status'] not in (0,ESCAPE):ref['mask']&=CONTROL
            base.compare_states(f"{c['name']}#{index} AX={call:04X}",actual,ref)
            require(actual['opl'].registers==machine.access.opl.registers,c['name']+': OPL register image differs')
        sites|=ref['sites'];edges|=ref['edges'];steps+=ref['steps'];events+=len(ref['events'])
        memory=ref['memory'];opl=machine.access.opl
        if ref['status']:break
    return dict(sites=sites,edges=edges,steps=steps,events=events,calls=calls)


def hashes():
    paths=['c/adlib_engine.c','c/adlib_engine.h','c/sound_latches.c','c/sound_latches.h',
           'c/sound_latches_sym.h','c/regs.h','c/special_blit.h','tests/adlib_engine.py',
           'tests/verification.py','tests/minimap_vga.py','tools/cbuild.py','tools/difftest.py',
           'tools/bounded_process.py','tools/resources.py','tools/common.py','tools/unpack.py',
           'tools/sound_latch_symtab.py','src/sound/adlib.asm','metadata/adlib-symbols.json',
           'metadata/sound-oracle.json','metadata/toolchain-lock.json','assets/adlib.dat']
    return {p:sha((ROOT/p).read_bytes()) for p in paths}


# Mutation witnesses, one per distinct contract risk.
WITNESSES=(
    (1,'song05-effects-over-music','OPL register write order of an instrument'),
    (2,'song05-effects-over-music','tempo phase decrement/reload placement'),
    (3,'song05-order-wrap','order-list redirect stores list+2 in +0A'),
    (4,'song05-effects-over-music','effect channel search from 064C downward'),
    (5,'detect-present','47 data-delay reads per OPL write'),
    (6,'song-change-retained-fields','song start sends retained key-off packets'),
    (7,'all-effects','granted effect fetched in its grant update'),
    (8,'constructed-escape-88','tokens 88..AF stop as an explicit escape'),
    (9,'constructed-level-caller-dx-null-instrument','level token uses the live DX'),
    (10,'detect-pending-irq','detection requires status1 & E0 == 0'),
    (11,'constructed-level-caller-dx-null-instrument','null instrument pointer reads driver byte 000E'),
)


def worker(directory):
    before=hashes()
    pins=json.loads((ROOT/'metadata/sound-oracle.json').read_text())
    check(PIN==pins['adlib'],'AdLib executable identity changed')
    native=Native(directory)
    rows=[];sites=set();edges=set();started=time.time()
    only=[n for n in os.environ.get('ADLIB_ENGINE_ONLY','').split(',') if n]
    lookup={c['name']:c for c in cases()}
    for c in cases():
        if only and c['name'] not in only:continue
        t=time.time();result=run_case(native,c)
        sites|=result['sites'];edges|=result['edges']
        rows.append(dict(name=c['name'],calls=result['calls'],original_instructions=result['steps'],
                         ordered_events=result['events'],stop=c.get('stop',0),
                         constructed=c['name'].startswith('constructed-')))
        print(f"CHECKED {c['name']}: {result['calls']} calls, {result['steps']} instructions, {time.time()-t:.1f}s",flush=True)
        gc.collect()
    mutations=[]
    for number,name,risk in WITNESSES:
        if only and name not in only:continue
        mutant=Native(directory,number)
        try:run_case(mutant,lookup[name])
        except Mismatch as error:
            mutations.append(dict(mutation=number,case=name,risk=risk,completed=True,mismatch=str(error)[:300]))
        else:raise Failure(f'adlib engine mutant {number} survived')
        print(f'MUTANT {number} detected by {name}',flush=True)
        del mutant;gc.collect()
    missing_sites=SITES-sites;missing_edges=EDGES-edges
    if only:
        print('partial run; missing sites',sorted(hex(p) for p in missing_sites))
        print('missing edges',sorted((hex(a),hex(b)) for a,b in missing_edges))
        return
    check(not missing_sites and not missing_edges,
          f'engine coverage incomplete: {sorted(missing_sites)} {sorted(missing_edges)}')
    check(before==hashes(),'campaign inputs changed')
    report=dict(image='adlib',image_sha256=PIN['image_sha256'],load_segment=f'{LOAD:04X}',
                translated_code_bytes=TRANSLATED_BYTES,native_code_ranges=[list(r) for r in CODE_RANGES],
                case_count=len(rows),interrupt_calls=sum(r['calls'] for r in rows),cases=rows,
                executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),
                original_instructions=sum(r['original_instructions'] for r in rows),
                ordered_events=sum(r['ordered_events'] for r in rows),
                mutation_count=len(mutations),mutations=mutations,
                seconds=round(time.time()-started,1),input_hashes=before,
                limits=dict(timeout_seconds=SECONDS,process_commit_mib=MEMORY_MIB,
                            instructions_per_call=MAX_STEPS,events_per_call=MAX_EVENTS),
                contract=dict(events='kind/address/value exact; FLAGS on events masked to TF/IF/DF',
                              registers='all after IRET; core and escape exits with defined flags of the last flag-setting instruction',
                              ports='every OUT/IN of 0559 and detection in order, finite OPL provider'),
                scope=('AdLib INT 61h services 0000..059F (UNKNOWN 0014 and 05A0..05A7 excluded) from the '
                       'dispatcher through IRET on shipped songs/effects, main request pattern, detection, '
                       'reset and constructed stream states for 83 STOP, release points, live-DX level '
                       'tokens and the 88..AF escape; no game boot, no timing or OPL synthesis claim'))
    write_json(REPORT,report)
    print(f'PASS adlib engine: {len(rows)} cases, {report["interrupt_calls"]} INT61 calls, '
          f'{len(sites)} sites, {len(edges)} edges, {len(mutations)} mutants, '
          f'{report["seconds"]}s',flush=True)


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if sys.argv[1:]:raise SystemExit('usage: adlib_engine.py')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='adlib-engine-',parent=BUILD) as directory:
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],
                    cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)


if __name__=='__main__':main()

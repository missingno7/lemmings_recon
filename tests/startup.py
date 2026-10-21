"""Bounded DOS-entry orchestration through the native protection wrapper.

No original game loop executes. Media fixtures run the original encoded probe
separately; all wrapper/parent instructions execute continuously. DAT/checksum
direct-RAM APIs retain their old bus projection. Full RAM, CPU, ordered observed
bus, ports and service calls compare.
"""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
import video_probe as video
import main_resources as resources
import dat_files as files
import dat_io_c as io
import protection_native as protection
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json

RANGES=((0,0xFB),(0x4EA,0x4F9),(0xF08,0xF6F),(0xFF8,0x113D),
    (0x113E,0x1193),(0x1194,0x1250),(0x1293,0x12DA),(0x12DB,0x12E9),
    (0x12EA,0x131A),(0x132A,0x13DC))
OWN={i.address:i for a,b in RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
def decoded(a,b):return {i.address:i for i in v.MD.disasm(v.IMAGE[a:b],a)}
INS=(OWN|resources.MAIN_INS|video.INS|decoded(0x4F9,0x54E)|decoded(0x54E,0x62B)|
    decoded(0x8343,0x8363)|decoded(0x1550,0x1592)|decoded(0x1ED1,0x1ED7)|protection.INS)
INS[0x43F2]=next(v.MD.disasm(v.IMAGE[0x43F2:0x43FA],0x43F2))
# Direct-RAM children: their original instructions and final RAM still compare.
# A core's caller RET is bus-observed; older adapters consume it directly.
DIRECT_ADAPTERS={0x6,0xD,0xD8}
DAT_CALLS={0x58E0,0x58F9,0x590F,0x594D,0x5960,0x5972,0x598A}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=1440,768,20_000_000,3_000_000
REPORT=BUILD/'startup-differential.json'
ENTRY=(0,0x1293,0x106E,0x1007,0xF08)
class SoundServices(ct.Structure):
    _fields_=[('dos',ct.POINTER(v.InterruptService)),('bios',ct.POINTER(v.InterruptService)),
        ('sound',ct.POINTER(v.InterruptService)),('files',ct.POINTER(files.Services)),('io',ct.POINTER(io.Io))]
class Services(ct.Structure):
    _fields_=[(n,ct.POINTER(v.InterruptService)) for n in ('dos','bios','clock','mouse')]+[
        ('ports',ct.POINTER(v.Ports)),('bus',ct.POINTER(v.Bus)),
        ('files',ct.POINTER(files.Services)),('io',ct.POINTER(io.Io)),
        ('sound',ct.POINTER(SoundServices)),('protection',ct.POINTER(protection.Services))]
class Result(ct.Structure):
    _fields_=[('registers',v.Regs)]+[(n,ct.c_uint16) for n in ('status','child_entry','child_status','service_status')]
BINDINGS={0x10:(0xB000,0x100),0x21:(0xB000,0x200),0x1A:(0xB000,0x600),0x33:(0xB000,0x300)}

def cases():
    rows=[]
    def add(name,**kw):rows.append(dict(name=name,**kw))
    for load in v.LOADS:
        add(f'program-menu-{load:04x}',load=load,full=True,protection=True,command=b'/v /o /a /4')
    add('program-protection-fail',full=True,protection=True,outcome=1,command=b'/v /o /a')
    add('program-counter-skip',full=True,protection=True,counter=0,command=b'/v /o /a')
    add('program-protection-seam',full=True,command=b'/e /d /n /a /i 12345 ')
    add('program-mouse-absent',full=True,protection=True,mouse=False,command=b'/v /o /a /2')
    for command in (b'',b'hello',b'/',b'/V /E /A /M /N /D /P /O /X /2 /4',
                    b'-v -o',b'/z /\x80 /[',b'/i 0 ',b'/i 65536 ',b'/i 123',b'/i',b'/i  ',b'/i : '):
        add('command-'+command.hex(),entry=1,command=command)
    for command in (b'/v /o',b'/e /d',b'/v /p',b'/v /m /n /i 555 ',b'/v /x',b''):
        add('prefix-'+command.hex(),command=command,keys=(ord('1'),ord('2')))
    for mode in (2,4,255):
        for flag in (0x200A,0x200B,0x200D,0x200C):
            add(f'options-{mode}-{flag:x}',entry=2,mode=mode,option_flag=flag,keys=(ord('2'),ord('2')))
    for key in (ord('1'),ord('2'),ord('3'),ord('4'),13,10,27):
        add(f'options-choice-{key}',entry=2,mode=255,keys=(ord('x'),ord('1'),ord('q'),key))
    add('options-arrows',entry=2,mode=4,keys=(0,0x48,0,0x50,0,0x50,0,0x50,0,0x50,0,0x50,0,0x48,13))
    add('options-return-to-first',entry=2,mode=4,keys=(0,0x4B,0,0x50,0,0x48,13))
    add('options-exit-row',entry=2,mode=4,keys=(0,0x50,0,0x50,0,0x50,0,0x50,13))
    add('options-adapter-escape',entry=2,mode=255,keys=(27,))
    add('options-missing-input',entry=2,mode=4,missing_in=True,missing_port_status=6)
    add('program-calibration-stop',sound=True,command=b'/v /o /a',stop_video=True)
    add('allocate-layout',entry=3)
    for error in (7,8):add(f'program-alloc-failure-{error}',sound=True,command=b'/v /o /a',alloc_error=error)
    for present in (False,True):
        add(f'mouse-{present}',entry=4,mouse=present)
    add('mouse-disabled',entry=4,disabled=255)
    add('mouse-iret-change',entry=4,iret_change=True)
    add('prefix-provider-stop',command=b'/v /o',provider_stop=True)
    return [dict(load=0x1010,seed=0xB000+i,entry=0,flags=0x202,command=b'/v /o /a',
        mode=4,keys=(),mouse=True,disabled=0,full=False,sound=False,protection=False,
        counter=9,stale=0,outcome=0,fat=0xF8,open_error=False,read_error=False,short_read=False,create_error=False,write_error=False,close_error=False,critical=False,
        alloc_error=0,pit=0x1234,base=0x3D4,dcc=True,primary=7,secondary=0,
        ega=True,ega_config=0,color=True,mono=False,mono_id=0,option=0)|c for i,c in enumerate(rows)]

def setup(c):
    memory,device=v.initial_memory(c);load=c['load'];ds=(load+0x9A9)&65535
    r=v.default_regs(load,c['seed'],ss=(load+0x143E)&65535,sp=0x4AF4,ds=load-16,es=load-16,flags=c['flags'])
    r['ip']=ENTRY[c['entry']]
    c['allocation']=0x4000 if load==0x2345 else 0x3000
    command=c['command'];v.check(len(command)<256,'command too long')
    p=v.physical(load-16,0x80);memory[p:p+len(command)+2]=bytes((len(command),))+command+b'\r'
    for number,(seg,off) in BINDINGS.items():v.put16(memory,0,number*4,off);v.put16(memory,0,number*4+2,seg)
    for number in (8,9,12,0x74):v.put16(memory,0,number*4,0x700+number);v.put16(memory,0,number*4+2,0xB000)
    v.put16(memory,0x40,0x63,0x3D4)
    v.put8(memory,0x600,0x100,c['fat'])
    v.put16(memory,0,0x78,0x120);v.put16(memory,0,0x7A,0x600);v.put8(memory,0,0x46C,0)
    if c['entry']:
        r['ds']=ds
        for off,value in ((0x1FF6,load-16),(0x1F7C,c['mode']),(0x1FDA,0x3D4),(0x1FC9,0),(0x1FC6,12)):
            v.put16(memory,ds,off,value)
        for off in (0x200A,0x200B,0x200C,0x200D,0x200E):v.put8(memory,ds,off,0)
        v.put8(memory,ds,0x1F73,c['disabled'])
        if c.get('option_flag'):v.put8(memory,ds,c['option_flag'],255)
        r.update(si=0x2490,di=0x2492)
    device.trace=v.PackedDeviceTrace(MAX_EVENTS)
    return memory,r,device

class Access(video.Access):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device);self.max_events=MAX_EVENTS
        self.quiet=False;self.omitted=0;self.keys=0;self.outputs=[];self.fixture_calls=[];self.fixtures=[];self.writes=[]
        self.dos=resources.DosProvider(dict(load_segment=c['load']),memory,r)
    def emit(self,kind,address,value,flags,mask=v.FLAGS):
        if self.quiet and kind in ('read','write'):
            v.check(not v.VGA_BASE<=address<v.VGA_END,'direct-RAM child reached VGA')
            self.omitted+=1;v.check(self.omitted<60_000_000,'direct RAM access budget exhausted');return
        v.BusAccess.emit(self,kind,address,value,flags,mask)
    def inp(self,port,flags,mask=v.FLAGS):
        if port in (0x3DA,0x3BA):
            # Bounded status cycle also supports the interactive text selector.
            self.status_reads+=1;v.check(self.status_reads<100_000,'status input budget exhausted')
            value=(8,0,1,0)[(self.status_reads-1)%4];self.cursor+=1;self.emit('in',port,value,flags,mask);return value
        return super().inp(port,flags,mask)
    def out_word(self,port,value,flags,mask=v.FLAGS):
        self.device.out(port,value,flags);self.emit('out',port,value,flags,mask)

def provider(number):
    def execute(a,r):
        entry=dict(r);fn=r['ax']>>8;c=a.c
        v.check(len(a.service_events)<6000,'startup service budget exhausted')
        if number==0x1A:
            v.check(fn in (0,1),'clock function differs')
            if fn==0:r.update(cx=0x1234,dx=0x5678)
        elif number==0x10:
            if fn==15:r['ax']=(r['ax']&0xFF00)|3;r['bx']=(r['bx']&255)|0x100
            elif fn in (0,2,5):pass
            elif r['ax']==0x1A00:r.update(ax=0x1A,bx=7)
            elif fn==0x12:r['bx']&=0xFF00;r['cx']&=0xFF00
            else:raise v.OracleFailure(f'undeclared startup BIOS {r["ax"]:04x}')
        elif number==0x33:
            if r['ax']==0:r['ax']=65535 if c['mouse'] else 0;r['bx']=2
            else:v.check(r['ax'] in (2,4,7,8,12,15),'mouse function differs')
            if c.get('iret_change'):a.word_write(r['ss'],r['sp'],0xD234,r['flags'])
        elif number==0x21:
            if fn in (0x3D,0x3F,0x3C,0x40,0x3E):return protection.provider(number)(a,r)
            if fn==0x35:
                n=r['ax']&255;r['bx']=v.get16(a.memory,0,4*n);r['es']=v.get16(a.memory,0,4*n+2)
            elif fn==0x25:
                n=r['ax']&255;a.patch(0,4*n,r['dx'],'dos-vector');a.patch(0,4*n+2,r['ds'],'dos-vector')
            elif fn==0x1B:r.update(ds=0x600,bx=0x100)
            elif fn==0x4A:v.check(r['bx']==0x1911,'resize paragraphs differ')
            elif fn==0x48:
                v.check(r['bx']==0x5571,'arena paragraphs differ')
                a.word_write(r['ss'],(r['sp']+4)&65535,((v.get16(a.memory,r['ss'],r['sp']+4)&~1)|bool(c['alloc_error'])),r['flags'])
                r['ax']=c['alloc_error'] or c['allocation'];r['bx']=0x4321 if c['alloc_error'] else r['bx']
            elif fn==7:
                v.check(a.keys<len(c['keys']),'keyboard input budget exhausted')
                r['ax']=(r['ax']&0xFF00)|c['keys'][a.keys];a.keys+=1
            elif fn in (2,9,0x4C):pass
            else:raise v.OracleFailure(f'undeclared startup DOS {fn:02x}')
        a.service_events.append(dict(number=number,entry=entry,returned=dict(r)))
        resume=v.get16(a.memory,entry['ss'],entry['sp'])
        return 77 if c.get('provider_stop') or (c.get('stop_video') and number==0x10 and 0x13DC<=resume<0x1530) else 0
    return execute

class Machine(v.OriginalMachine):
    def __init__(self,c,memory,r,device):
        a=Access(c,memory,r,device);frames=[];self.frames=frames;self.child_status=0
        def before(m,i):
            if i.address==0x43F2:m.stop(0);return True
            if i.address==0xAB and not(c['full'] or c['sound']):m.stop(5);return True
            if i.address==0xE0:
                if not c['protection']:m.stop(4);return True
            # DAT cores leave the final RET to the bus-aware parent. Older
            # checksum/cache adapters include their RET in direct-RAM scope.
            bus_ret=i.address==0x1BAE and frames and frames[-1][0] in {p+3 for p in DAT_CALLS}
            a.quiet=any(f[1] for f in frames) and not bus_ret
            if i.mnemonic=='call':
                frames.append((i.address+i.size,i.address in DIRECT_ADAPTERS or i.address in DAT_CALLS))
            return False
        def expected(m,off):
            v.check(bool(frames),'undeclared startup return');resume,quiet=frames.pop()
            if quiet:a.quiet=any(f[1] for f in frames)
            return {resume}
        def interrupt(m,number):
            q=m.state();fn=q['ax']>>8
            if number==0x21 and fn in (0x43,0x3D,0x3F,0x23) and not 0xE66<=q['ip']<0xF08:
                d=a.dos
                if fn==0x23:
                    v.put16(memory,q['ds'],q['dx']+33,len(resources.MAIN_DATA));v.put16(memory,q['ds'],q['dx']+35,0)
                    q['ax']=0;q['flags']=(q['flags']&~0x8D5)|0x894
                else:
                    start=d.position;value,count,flags,failed=d.file_service(fn,q['ds'],q['dx'],q['flags'],count=q['cx'] if fn==0x3F else 0,handle=q['bx'] if fn==0x3F else None)
                    if fn==0x3F and not failed:
                        base=v.physical(q['ds'],q['dx']);memory[base:base+count]=resources.MAIN_DATA[start:start+count]
                    q['ax']=value;q['flags']=flags
                    if fn==0x43:q['cx']=count
                m.cpu.mem_write(0,bytes(memory));m.cpu.mem_write(v.SIZE,bytes(memory));m.set_state(q);m.flags=q['flags'];m.mask=v.FLAGS;return
            m.software_interrupt(number,q['ip'],BINDINGS[number],provider(number))
            if m.stopped:
                if c.get('stop_video') and number==0x10 and 0x13DC<=q['ip']<0x1530:m.child_status=3;m.status=3
                else:m.child_status=m.status;m.status=1
            elif number==0x21 and fn==0x4C:m.stop(7)
        # The entire wrapper is original; only063E is an opaque media fixture.
        original_before=before
        def with_outcome(m,i):
            if i.address==0x63E:
                q=m.state();protection.outcome(a,q,original=True)
                # External child returns through its actual live near word.
                q['ip']=a.word_read(q['ss'],q['sp'],q['flags'],m.mask);q['sp']=(q['sp']+2)&65535
                frames.pop();m.set_state(q);m.previous=None;m.mask=v.FLAGS;return True
            return original_before(m,i)
        super().__init__(c,memory,r,device,c['entry']!=0,instructions=INS,access=a,
            outer_returns=lambda m,off:not frames,child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            before=with_outcome,interrupt=interrupt,changed_return_status=2,max_steps=MAX_STEPS)
        # Recognize063E as the explicit provider boundary.
        self.instructions=dict(self.instructions);self.instructions[0x63E]=next(v.MD.disasm(v.IMAGE[0x63E:0x646],0x63E))
    def run(self):
        out=super().run();out.update(child_status=self.child_status,service_status=self.service_status,
            services=self.access.service_events,dos=self.access.dos.events,fixtures=self.access.fixture_calls)
        return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'startup-{mutation}.dll',mutation,'startup')))
        self.fn=self.lib.lmn_startup_core;self.fn.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_int,ct.POINTER(Services)];self.fn.restype=Result
    def run(self,c,memory,r,device,fixtures):
        memory,device=bytearray(memory),copy.deepcopy(device);a=Access(c,memory,r,device);a.fixtures=fixtures
        cb=v.NativeCallbacks(a,missing_in=c.get('missing_in'))
        handlers={n:cb.interrupt(provider(n)) for n in BINDINGS}
        bindings={n:v.InterruptService(None,handlers[n],*BINDINGS[n]) for n in BINDINGS}
        def guarded(fn):
            def call(*args):
                try:return fn(*args)
                except BaseException as error:v.callback_failure(error)
            return call
        def file(fn,seg,off,flags,out):
            value,count,flags,failed=a.dos.file_service(fn,seg,off,flags)
            out.contents.value=value;out.contents.count=count;out.contents.flags=flags
        opened=files.FILE(guarded(lambda _,m,s,o,f,out:file(0x3D,s,o,f,out)))
        attributes=files.FILE(guarded(lambda _,m,s,o,f,out:file(0x43,s,o,f,out)))
        retry=files.RETRY_FN(guarded(lambda *args:(_ for _ in ()).throw(v.OracleFailure('unexpected retry'))))
        file_services=files.Services(None,opened,attributes,retry)
        def query(_,m,seg,off,flags,out):
            v.put16(memory,seg,off+33,len(resources.MAIN_DATA));v.put16(memory,seg,off+35,0)
            out.contents.value=0;out.contents.flags=(flags&~0x8D5)|0x894
        def read(_,m,handle,seg,off,count,flags,out):
            start=a.dos.position;value,amount,flags,failed=a.dos.file_service(0x3F,seg,off,flags,count=count,handle=handle)
            if not failed:
                base=v.physical(seg,off);memory[base:base+amount]=resources.MAIN_DATA[start:start+amount]
            out.contents.value=value;out.contents.flags=flags
        query_cb=io.QUERY(guarded(query));read_cb=io.READ(guarded(read));io_services=io.Io(None,query_cb,read_cb)
        sound=SoundServices(ct.pointer(bindings[0x21]),ct.pointer(bindings[0x10]),None,ct.pointer(file_services),ct.pointer(io_services))
        # The same original-built media fixture supplies pre-RET state.
        fixture=protection.PROBE(cb.interrupt(lambda a,r:protection.outcome(a,r,original=False)))
        protect=protection.Services(*(ct.pointer(bindings[n]) for n in (0x21,0x10,0x1A,0x33)),ct.pointer(cb.ports),ct.pointer(cb.bus),None,fixture)
        services=Services(*(ct.pointer(bindings[n]) for n in (0x21,0x10,0x1A,0x33)),ct.pointer(cb.ports),ct.pointer(cb.bus),
            ct.pointer(file_services),ct.pointer(io_services),ct.pointer(sound) if c['full'] or c['sound'] else None,
            ct.pointer(protect) if c['protection'] else None)
        regs=v.Regs(**r);out=self.fn((ct.c_uint8*v.SIZE).from_buffer(memory),ct.byref(regs),c['entry'],ct.byref(services))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,child_status=out.child_status,
            service_status=out.service_status,memory=memory,device=device,events=a.events,providers=a.providers,cursor=a.cursor,
            services=a.service_events,dos=a.dos.events,fixtures=a.fixture_calls,child_entry=out.child_entry)

def compare(native,c):
    memory,r,device=setup(c);machine=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device));ref=machine.run()
    actual=native.run(c,memory,r,device,machine.access.fixtures)
    if actual['memory']!=ref['memory']:
        diffs=[(p,actual['memory'][p],ref['memory'][p]) for p in range(v.SIZE) if actual['memory'][p]!=ref['memory'][p]]
        raise v.Mismatch(c['name']+': RAM differs '+str(diffs[:15]))
    v.compare_states(c['name'],actual,ref)
    v.require(actual['dos']==ref['dos'],c['name']+': DAT service trace differs')
    v.require(actual['fixtures']==ref['fixtures'],c['name']+': protection outcome differs')
    if c.get('stop_video'):
        v.check((ref['status'],ref['child_status'],ref['service_status'])==(3,3,77),'calibration stop profile differs')
        v.require(actual['child_entry']==0x15AD,'calibration stop child entry differs')
    return ref

def hashes():
    paths={'tests/startup.py','tests/verification.py','tests/video_probe.py','tests/main_resources.py','tests/main_resources_oracle.py',
        'tests/dat_files.py','tests/dat_io_c.py','tests/minimap_vga.py','tools/cbuild.py','tools/difftest.py','tools/bounded_process.py',
        'tools/unpack.py','metadata/oracle.json','metadata/symbols.json','metadata/toolchain-lock.json','assets/vgalemmi.exe','assets/main.dat','c/lemmings_sym.h',
        'c/regs.h','c/special_blit.h','src/entry_services.asm','host/platform_host.c'}
    for p in source_files('startup'):paths|={p.relative_to(ROOT).as_posix(),p.with_suffix('.h').relative_to(ROOT).as_posix()}
    for module in tuple(sys.modules.values()):
        p=Path(getattr(module,'__file__','') or '.')
        if p.is_file() and p.resolve().is_relative_to(ROOT):
            relative=p.resolve().relative_to(ROOT)
            if relative.parts[0] in ('tests','tools'):paths.add(relative.as_posix())
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths) if (ROOT/p).is_file()}

def worker(directory,selected):
    start=time.perf_counter();before=hashes();native=Native(directory);rows=[];sites=set();edges=set();overlaps=[]
    for c in cases():
        if selected and c['name'] not in selected:continue
        ref=compare(native,c);sites|=ref['sites'];edges|=ref['edges']
        rows.append(dict(case=c['name'],steps=ref['steps'],events=len(ref['events']),status=ref['status']))
        if c['full'] and c['protection'] and c['outcome']==0:
            ds=(c['load']+0x9A9)&65535;m=ref['memory']
            overlaps.append(dict(case=c['name'],allocation=c['allocation'],fields={f'{off:04x}':v.get16(m,ds,off) for off in
                (0x1FE4,0x1FE6,0x1FE8,0x1FEA,0x1FEC,0x1FEE,0x1FF0,0x1FF2,0x1FF4,0x1FC9,0x1FDA,0x1F7C)}))
            v.check(ref['regs']['ip']==0x43F2,'startup did not reach menu')
            v.check(v.get16(m,ds,0x259C)==0x1234 and v.get16(m,ds,0x259E)==0x5678,'clock producer differs')
        print('CHECKED '+c['name'],flush=True);del ref;gc.collect()
    if selected:return
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in ((1,'prefix-2f76202f6f'),
            (2,'command-2f56202f45202f41202f4d202f4e202f44202f50202f4f202f58202f32202f34'),
            (3,'allocate-layout'),(4,'mouse-True'),(5,'options-255-200d'),(6,'command-2f6920313233')):
        try:compare(Native(directory,mutation),lookup[name])
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise v.OracleFailure('surviving startup mutant')
    after=hashes()
    v.check(before==after,'startup inputs changed during campaign: '+str(sorted(p for p in before.keys()|after.keys() if before.get(p)!=after.get(p))))
    v.check(set(OWN)<=sites,'missing own startup sites')
    v.check(v.direct_jump_edges(OWN)<=edges,'missing own startup branch outcomes')
    write_json(REPORT,dict(image='main',image_sha256=sha(v.IMAGE),case_count=len(rows),comparison_count=len(rows),
        native_code_ranges=[list(p) for p in RANGES],executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),
        own_executed_sites=sorted(set(OWN)&sites),own_observed_outcomes=sorted(e for e in edges if e[0] in OWN),
        mutation_count=len(mutants),mutations=mutants,rows=rows,host_overlap=overlaps,input_hashes=before,
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),runtime_seconds=time.perf_counter()-start,
        limits=dict(seconds=SECONDS,memory_mib=MEMORY_MIB,instructions_each=MAX_STEPS,events_each=MAX_EVENTS),
        domain='Constructed DOS entry to protection seam or JMP43F2; native protection wrapper with explicit original-built media outcome fixtures; sound fallback with /a. Command/options prefix and raw focused leaves. Quiescent IRQs,TFclear,DFclear,ordinary RAM DAT/checksum children; typed DAT transport retains its prior ABI.'))
    print(f'PASS startup: {len(rows)} comparisons,{len(sites&set(OWN))} own sites,{len(mutants)} mutants',flush=True)
def main():
    if len(sys.argv)>=3 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3:]);return
    selected=sys.argv[2:] if len(sys.argv)>1 and sys.argv[1]=='--focus' else []
    if sys.argv[1:] and not selected:raise SystemExit('usage: startup.py [--focus CASE ...]')
    with temporary_build_directory(prefix='startup-',parent=BUILD) as directory:
        run_bounded([sys.executable,__file__,'--worker',str(directory),*selected],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

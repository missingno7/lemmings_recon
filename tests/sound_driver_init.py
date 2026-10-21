"""054E..062A composition; original execution uses the shared bounded engine.

DAT children retain their established direct-RAM/preserving-DOS contract. Their
internal accesses are counted and full RAM is compared, but are not bus events:
only initializer/probe and real interrupt transport use the parent's byte bus.
Pinned sound images are decoded as data; no driver instruction is executed.
"""
import copy
import ctypes as ct
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as base
import dat_load as dat
from dat_files import Services as Files,FILE,RETRY_FN,MAPPING
from dat_io_c import Io,QUERY,READ
from resources import decode_section
from cbuild import build,source_files
from common import BUILD,sha,write_json
from bounded_process import run_bounded,temporary_build_directory

check=base.check
PARENT={i.address:i for i in base.MD.disasm(base.IMAGE[0x054e:0x062b],0x054e)}
INS=PARENT|dat.INS
for start in (0x04d0,0x1949,0x4b1c):
    i=next(base.MD.disasm(base.IMAGE[start:start+8],start));INS[start]=i
EDGES=base.direct_jump_edges(PARENT)
RETURNS={0x05b3,0x05f5,0x060b}
RESUMES={p+i.size for p,i in INS.items() if i.mnemonic=='call'}
CHILD_RETURNS={p:RESUMES for p,i in INS.items() if i.mnemonic=='ret' and p not in RETURNS}
BINDINGS={0x21:(0x7100,0x210),0x10:(0x7200,0x100),0x61:(0x4800,0)}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_ACCESSES=580,512,3000000,8000000
REPORT=BUILD/'sound-driver-init-differential.json'
PACKET=dat.decoder.section([('literal',b'\xc3\x90\x5a\xa5')])

class Services(ct.Structure):
    _fields_=[(n,ct.POINTER(t)) for n,t in (
        ('dos',base.InterruptService),('bios',base.InterruptService),
        ('sound',base.InterruptService),('files',Files),('io',Io))]
class Result(ct.Structure):
    _fields_=[(n,ct.c_uint16) for n in ('status','child_status','service_status')]

def cases():
    rows=[dict(name='disabled-none',option=255),dict(name='pcspeaker-fallback',detect=0),
          dict(name='adlib',detect=1),dict(name='tandy',detect=0,tandy=True),
          dict(name='external-vector-untouched',option=255,external=True)]
    rows += [dict(name=f'option-{n:02x}',option=n,detect=1) for n in range(256)]
    rows += [dict(name=n,**kw) for n,kw in (
        ('probe-allocation-fails',{'allocation_fail':True}),
        ('unchecked-second-allocation',{'second_fail':True}),
        ('free-error-ignored',{'free_fail':True,'detect':0}),
        ('missing-file-retry',{'attribute_errors':1}),
        ('missing-file-fatal',{'attribute_errors':1,'retry_enabled':0,'expected':5,'child_status':1}),
        ('open-carry-ignored',{'open_fail':True}),
        ('adlib-header-read-failure',{'read_error':0,'expected':6,'child_status':2}),
        ('adlib-payload-read-failure',{'read_error':1,'expected':6,'child_status':2}),
        ('tandy-header-read-failure',{'detect':0,'tandy':True,'read_error':2,'expected':6,'child_status':2}),
        ('tandy-payload-read-failure',{'detect':0,'tandy':True,'read_error':3,'expected':6,'child_status':2}),
        ('bios-restores-page',{'detect':0,'tandy':True,'page':0xa7}),
        ('sound-returns-registers',{'sound_regs':{'ds':0x3600,'es':0x4567,'bx':0xabcd,'cx':0x9876,'si':0x5432,'di':0x2345,'bp':0x8765}}),
        ('bios-returns-live-ds',{'detect':0,'tandy':True,'bios_ds':0x3600}),
        ('dos-returns-live-ds',{'dos_ds':0x3600}),
        ('vector-saved-ds-changed',{'saved_ds':0x3600}),
        ('sound-relocates-stack',{'sound_stack':True}),
        ('outer-return-changed',{'outer_ip':0xbeef}),
        ('dos-stop',{'stop_number':0x21,'expected':2,'service_status':0x1234}),
        ('bios-stop',{'detect':0,'stop_number':0x10,'expected':2,'service_status':0x1234}),
        ('sound-stop',{'stop_number':0x61,'expected':2,'service_status':0x1234}),
        ('changed-iret',{'changed_iret':True,'expected':3}),
        ('changed-probe-ret',{'detect':0,'probe_ret':True,'expected':4}),
        ('changed-dat-ret',{'dat_ret':True,'expected':4}),
        ('missing-dat-services',{'no_dat':True,'expected':7}),
        ('unbound-dos',{'unbound':0x21,'expected':1}),
        ('unbound-sound',{'unbound':0x61,'expected':1}),
        ('unbound-bios',{'detect':0,'unbound':0x10,'expected':1}),
        ('stack-wrap',{'sp':1}),('outer-word-ffff',{'sp':65535}),
        ('physical-wrap',{'ss':65535,'sp':0x11}),
        ('df-if-set',{'flags':0x06d7}),
        ('pinned-tandy-images',{'assets':True,'detect':0,'tandy':True}),
    )]
    rows += [dict(name=f'load-{load:04x}',load=load,detect=0,tandy=True) for load in base.LOADS]
    return [dict(load=0x1010,seed=0x54e+i,option=0,detect=1,flags=0x0ad7)|c for i,c in enumerate(rows)]

def setup(c):
    memory,device=base.initial_memory(c);ds=c['load']+0x9a9
    r=base.default_regs(c['load'],c['seed'],ds=ds,ss=c.get('ss',0x6000),sp=c.get('sp',0x9000),flags=c['flags'])
    r['ip']=0x54e
    for frame in (ds,0x3600):
        for name,value in dict(DatCacheEnabled=0,DatCacheSelected=0,DatCriticalErrorFlag=0,
                               DatRetryEnabled=c.get('retry_enabled',255)).items():
            memory[base.physical(frame,dat.field(name))]=value
        memory[base.physical(frame,0x2010)]=c['option']
        memory[base.physical(frame,0x2573):base.physical(frame,0x2573)+10]=b'adlib.dat\0'
        memory[base.physical(frame,0x257d):base.physical(frame,0x257d)+13]=b'tandysnd.dat\0'
    for num,(cs,ip) in BINDINGS.items():
        base.put16(memory,0,num*4,ip);base.put16(memory,0,num*4+2,cs)
    base.put16(memory,0,0x180,0xff53 if c.get('external') else 0x0182)
    base.put16(memory,0,0x182,0xf000 if c.get('external') else c['load']+0x842)
    base.put16(memory,r['ss'],r['sp'],0xd00d)
    return memory,r,device

class Access(base.BusAccess):
    def __init__(self,c,memory,r,device):
        super().__init__(c,memory,r,device,max_events=20000)
        self.silent=False;self.accesses=0;self.files=[];self.position=0;self.reads=0;self.attributes=0;self.current='adlib'
        self.sound_calls=0;self.bios_calls=0
    def emit(self,*args,**kw):
        self.accesses+=1;check(self.accesses<=MAX_ACCESSES,'access budget exhausted')
        if not self.silent:super().emit(*args,**kw)
    def packet(self):return (ROOT/'assets'/f'{self.current}.dat').read_bytes() if self.c.get('assets') else PACKET
    def file(self,function,seg,off,flags):
        check(len(self.files)<50,'file callback budget exhausted')
        failed=False
        if function==0x43:
            failed=self.attributes<self.c.get('attribute_errors',0);self.attributes+=1
            value,count=(5 if failed else 0),0x1234
        else:
            self.current='tandysnd' if off==0x257d else 'adlib';self.position=0
            failed=self.c.get('open_fail',False);value,count=(5 if failed else 7),0
        self.files.append((function,seg,off,flags&(0xfc7 if function==0x43 else 0xfd7),failed))
        return value,count,(flags&~0x8d5)|0x894|int(failed)
    def read_file(self,handle,seg,off,count,flags):
        check(self.reads<6,'read callback budget exhausted')
        failed=self.reads==self.c.get('read_error',-1);self.reads+=1
        data=self.packet()[self.position:self.position+count]
        if not failed:
            for n,v in enumerate(data):self.patch(seg,(off+n)&65535,v,'file-data',word=False)
            self.position+=len(data)
        if self.c.get('dat_ret') and self.reads==2:
            self.patch(self.r['ss'],(self.r['sp']-6)&65535,0xbeef,'changed-dat-return')
        self.files.append((0x3f,handle,seg,off,count,flags&0xfd7,failed))
        return (5 if failed else len(data)),(flags&~0x8d5)|0x894|int(failed)
    def retry(self,view):
        self.files.append(('retry',view))
        check(sum(e[0]=='retry' for e in self.files)<=2,'retry budget exhausted')
        return 0x1111,0x4567,0x6789,(view['flags']&~0x8d5)|0x891

def provider(number,c):
    if c.get('unbound')==number:return None
    def execute(a,r):
        check(len(a.service_events)<20,'interrupt callback budget exhausted')
        event=dict(number=number,entry=dict(r))
        a.service_events.append(event)
        if c.get('stop_number')==number:return 0x1234
        if number==0x21:
            function=r['ax']>>8
            if function==0x48:
                second=r['bx']==0x567
                check(second or r['bx']==0x5ad8,'allocation request differs')
                fail=c.get('second_fail' if second else 'allocation_fail',False)
                r['ax']=0x4800 if second else 0x7000
                flags=(c['flags']&~0x8d5)|0x894|int(fail)
                a.word_write(r['ss'],(r['sp']+4)&65535,flags,r['flags'])
                if c.get('dos_ds'):r['ds']=c['dos_ds']
            elif function==0x49:
                a.word_write(r['ss'],(r['sp']+4)&65535,(c['flags']&~0x8d5)|0x894|int(c.get('free_fail',False)),r['flags'])
            elif r['ax']==0x2561:
                check(r['dx']==0,'INT61 entry offset differs')
                a.word_write(0,0x184,r['dx'],r['flags']);a.word_write(0,0x186,r['ds'],r['flags'])
                if 'saved_ds' in c:a.word_write(r['ss'],(r['sp']+8)&65535,c['saved_ds'],r['flags'])
            else:raise base.OracleFailure('unexpected initializer DOS function')
        elif number==0x10:
            a.bios_calls+=1
            if a.bios_calls==1:
                check(r['ax']>>8==15,'BIOS query differs');r['ax']=0x5003;r['bx']=(c.get('page',3)<<8)|0x55
            elif a.bios_calls==2:
                check((r['ax'],r['bx'])==(0x580,0),'BIOS detection request differs');r['bx']=0xbeef if c.get('tandy') else 0
            else:
                check(r['ax']==0x5505,'BIOS saved BL / AL=05 quirk differs')
                if c.get('probe_ret'):a.word_write(r['ss'],(r['sp']+6)&65535,0xbeef,r['flags'])
            if c.get('bios_ds'):r['ds']=c['bios_ds']
        else:
            a.sound_calls+=1
            if a.sound_calls==1:
                check(r['ax']>>8==1,'AdLib detection service differs')
                if c.get('assets'):
                    image,_=decode_section((ROOT/'assets/adlib.dat').read_bytes())
                    check(a.memory[0x48000:0x48000+len(image)]==image,'pinned AdLib image differs before detection')
                r['ax']=(r['ax']&0xff00)|c['detect']
            for name,v in c.get('sound_regs',{}).items():r[name]=v
            if c.get('sound_stack') and a.sound_calls==1:
                words=[a.word_read(r['ss'],(r['sp']+2*i)&65535,r['flags']) for i in range(5)]
                r['ss'],r['sp']=0x6800,0x7000
                for i,v in enumerate(words):a.word_write(r['ss'],r['sp']+2*i,v,r['flags'])
            if 'outer_ip' in c:a.word_write(r['ss'],(r['sp']+8)&65535,c['outer_ip'],r['flags'])
        if c.get('changed_iret'):a.word_write(r['ss'],r['sp'],0xbeef,r['flags'])
        return 0
    return execute

class Machine(base.OriginalMachine):
    def __init__(self,c,memory,r,device,core):
        access=Access(c,memory,r,device)
        def before(m,i):
            access.silent=i.address not in PARENT
            if i.address==0x1b79 and c.get('no_dat'):m.stop(7);return True
            if i.address in (0x4d0,0x1949):m.stop(6 if i.address==0x4d0 else 5);return True
            if i.address==0x4b1c:
                state=m.state();view={n:v for n,v in state.items() if n not in ('cs','ip')}
                state['ax'],state['bx'],state['bp'],state['flags']=access.retry(view)
                state['ip']=base.get16(memory,state['ss'],state['sp']);state['sp']=(state['sp']+2)&65535
                m.set_state(state);m.previous=None;return True
            return False
        def interrupt(m,number):
            state=m.state()
            if state['ip'] in {p+i.size for p,i in dat.INS.items() if i.mnemonic=='int'}:
                # DAT provider boundaries deliberately preserve its historical
                # raw service contract; no invented hardware INT stack words.
                check(number==0x21,'unexpected DAT interrupt')
                function=state['ax']>>8
                if function in (0x43,0x3d):
                    state['ax'],count,state['flags']=access.file(function,state['ds'],state['dx'],state['flags'])
                    if function==0x43:state['cx']=count
                elif function==0x3f:state['ax'],state['flags']=access.read_file(state['bx'],state['ds'],state['dx'],state['cx'],state['flags'])
                else:raise base.OracleFailure(f'unexpected DAT service {function:x}')
                m.set_state(state);return
            check(number in BINDINGS,'unexpected parent interrupt')
            m.software_interrupt(number,state['ip'],BINDINGS[number],provider(number,c))
        super().__init__(c,memory,r,device,core,instructions=INS,access=access,outer_returns=RETURNS,
            child_returns=CHILD_RETURNS,max_steps=MAX_STEPS,before=before,interrupt=interrupt)
    def run(self):
        out=super().run();out.update(child_status=1 if self.status==5 else 2 if self.status==6 else 0,
            service_status=self.service_status,services=self.access.service_events,files=self.access.files)
        return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'sndinit-{mutation}.dll',mutation,'sound_driver_init')))
        self.functions={}
        for core in (True,False):
            fn=getattr(self.lib,'lmn_initialize_sound_driver_'+('core' if core else 'adapter'))
            fn.argtypes=[base.MEM,ct.POINTER(base.Regs),ct.POINTER(Services),ct.POINTER(base.Bus)];fn.restype=Result
            self.functions[core]=fn
    def run(self,c,memory,r,device,core):
        memory=bytearray(memory);device=copy.deepcopy(device);a=Access(c,memory,r,device);cb=base.NativeCallbacks(a)
        callbacks=[];services=[];pointers=[]
        for number in BINDINGS:
            body=provider(number,c)
            if body:
                fn=cb.interrupt(body);s=base.InterruptService(None,fn,*BINDINGS[number]);callbacks.append(fn);services.append(s);pointers.append(ct.pointer(s))
            else:pointers.append(ct.POINTER(base.InterruptService)())
        def guarded(fn):
            def call(*args):
                try:fn(*args)
                except BaseException as error:base.callback_failure(error)
            return call
        def file(function,seg,off,flags,out):out.contents.value,out.contents.count,out.contents.flags=a.file(function,seg,off,flags)
        opened=FILE(guarded(lambda _,m,s,o,f,out:file(0x3d,s,o,f,out)))
        attrs=FILE(guarded(lambda _,m,s,o,f,out:file(0x43,s,o,f,out)))
        def retry(_,m,call,out):
            view={reg:getattr(call.contents,n) for n,reg in MAPPING.items()}
            out.contents.value,out.contents.handle,out.contents.base_cursor,out.contents.flags=a.retry(view)
        retried=RETRY_FN(guarded(retry))
        def read(_,m,h,s,o,n,f,out):out.contents.value,out.contents.flags=a.read_file(h,s,o,n,f)
        reader=READ(guarded(read))
        query=QUERY(guarded(lambda *args:check(False,'unexpected FCB query')))
        files=Files(None,opened,attrs,retried);io=Io(None,query,reader)
        service=Services(*pointers,ct.POINTER(Files)() if c.get('no_dat') else ct.pointer(files),ct.pointer(io));regs=base.Regs(**r)
        result=self.functions[core]((ct.c_uint8*base.SIZE).from_buffer(memory),ct.byref(regs),ct.byref(service),ct.byref(cb.bus))
        return dict(regs={n:getattr(regs,n) for n in base.REG_NAMES},status=result.status,child_status=result.child_status,
            service_status=result.service_status,memory=memory,device=device,events=a.events,providers=a.providers,
            services=a.service_events,files=a.files,cursor=a.cursor)

def independent(c,memory,r,out,core):
    if out['status']:return
    enabled=c['option']!=255 and not c.get('allocation_fail') and (c['detect'] or c.get('tandy'))
    ds=out['regs']['ds']
    check(tuple(out['memory'][base.physical(ds,o)] for o in (0x2010,0x25a7,0x1f71))==
          ((255,3,2) if enabled else (0,1,1)),c['name']+': independent sound state differs')
    check(out['memory'][0x180:0x184]==memory[0x180:0x184],'INT60 must remain unchanged')
    if c['option']!=255 and not c.get('allocation_fail'):
        check((base.get16(out['memory'],0,0x184),base.get16(out['memory'],0,0x186))==(0,0x4800),'INT61 installed target differs')
    if c.get('tandy') and not c['detect']:
        sound=[e['entry']['ax']>>8 for e in out['services'] if e['number']==0x61]
        check(sound==[1,3,0,3,2,0],'Tandy initialization command order differs')
    if c.get('assets'):
        image,_=decode_section((ROOT/'assets/tandysnd.dat').read_bytes())
        check(out['memory'][0x48000:0x48000+len(image)]==image,'pinned Tandy image differs')
    if not core:check(out['regs']['ip']==c.get('outer_ip',0xd00d),'actual outer RET differs')

def compare(native,c,core,reference=None):
    memory,r,device=setup(c)
    ref=reference or Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),core).run()
    check((ref['status'],ref['child_status'],ref['service_status'])==
        (c.get('expected',0),c.get('child_status',0),c.get('service_status',0)),c['name']+': boundary differs')
    independent(c,memory,r,ref,core)
    actual=native.run(c,memory,r,device,core)
    base.compare_states(c['name'],actual,ref)
    base.require(actual['files']==ref['files'],c['name']+': DAT service trace differs')
    return ref

def main(directory):
    started=time.perf_counter();REPORT.unlink(missing_ok=True);native=Native(directory)
    rows=cases();seen=set();edges=set();cached={};outcomes={};steps=0
    for index,c in enumerate(rows):
        ref=compare(native,c,False);seen|=ref['sites'];edges|=ref['edges'];steps+=ref['steps']
        outcomes[c['name']]=dict(status=ref['status'],sites=len(ref['sites']),steps=ref['steps'])
        if c['name'] in ('adlib','tandy','disabled-none','pcspeaker-fallback','unchecked-second-allocation'):cached[c['name']]=ref
        if index%64==0:print(f'checked {index+1}/{len(rows)}',flush=True)
    for c in rows[:5]:
        ref=compare(native,c,True);seen|=ref['sites'];edges|=ref['edges'];steps+=ref['steps']
    check(set(PARENT)<=seen,f'missing parent sites {set(PARENT)-seen}')
    check(EDGES<=edges,f'missing parent outcomes {EDGES-edges}')
    mutants=[]
    for mutation,name,risk in ((101,'disabled-none','disable latch'),(102,'unchecked-second-allocation','unchecked CF'),
                               (103,'adlib','test before POP AX'),(104,'tandy','Tandy command handshake')):
        mutant=Native(directory,mutation);c=next(c for c in rows if c['name']==name)
        try:compare(mutant,c,False,cached[name])
        except base.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,risk=risk,mismatch=str(error)))
        else:raise AssertionError(f'mutant {mutation} survived')
    paths={str(p.relative_to(ROOT)).replace('\\','/') for p in source_files('sound_driver_init')}
    paths|={str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'c').glob('*.h') if p.name in
             ('sound_driver_init.h','dat_load.h','dat_files.h','dat_section.h','dat_io.h','dat.h','dat_cache.h','interrupt_service.h','special_blit.h','regs.h','lemmings_sym.h')}
    paths|={'tests/sound_driver_init.py','tests/verification.py','tests/dat_load.py','tests/dat_files.py',
            'tests/dat_section.py','tests/dat_io_c.py','tests/dat_io.py','tools/cbuild.py','tools/difftest.py',
            'tools/bounded_process.py','tools/resources.py','metadata/symbols.json','src/entry_services.asm',
            'assets/vgalemmi.exe','assets/adlib.dat','assets/tandysnd.dat','assets/main.dat'}
    report=dict(image='main',image_sha256=sha(base.IMAGE),case_count=len(rows)+5,mutation_count=len(mutants),
        cases=outcomes,mutations_detected=mutants,executed_instruction_addresses=sorted(seen),branch_edges=sorted(edges),
        translated_instruction_addresses=sorted(PARENT),translated_code_bytes=sum(i.size for i in PARENT.values()),
        parent_branch_edges=sorted(EDGES),executed_steps=steps,runtime_seconds=time.perf_counter()-started,
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in sorted(paths)},
        domain='054E..062A with live CALL/RET and bound DOS/BIOS/INT61 IRET; DAT existing direct-RAM finite retry/valid-stream contract; driver images data only; no engines/INT60 installation')
    write_json(REPORT,report)
    print(f"PASS sound driver init: {report['case_count']} cases, {len(PARENT)} translated sites, {len(EDGES)} branch outcomes, {len(mutants)} mutants; {report['runtime_seconds']:.2f}s",flush=True)

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--worker':main(Path(sys.argv[2]))
    elif len(sys.argv)==1:
        BUILD.mkdir(exist_ok=True);REPORT.unlink(missing_ok=True)
        with temporary_build_directory(prefix='sound-driver-init-',parent=BUILD) as directory:
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
    else:raise SystemExit('unexpected sound_driver_init arguments')

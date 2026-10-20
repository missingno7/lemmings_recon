"""Level selection -> real native loaders -> briefing, on the shared engine.

DAT/raw descendants retain their previously declared ordinary-RAM, preserving
DOS ABI and intact internal-return scope. Their original instructions still run;
only their RAM event projection is omitted, matching the legacy C APIs. Selector
CALL/RET words, decimal stores and every parent/briefing bus event are compared.
"""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools')]
import verification as v
import level_briefing as briefing
import resource_select as resources
from bounded_process import run_bounded,temporary_build_directory
from cbuild import build,source_files
from common import BUILD,sha,write_json

OWN_RANGES=((0x454C,0x4566),)
OWN={i.address:i for a,b in OWN_RANGES for i in v.MD.disasm(v.IMAGE[a:b],a)}
INS=briefing.INS|resources.INS|OWN
INS|={p:next(v.MD.disasm(v.IMAGE[p:p+16],p)) for p in (0xFB,0x197D)}
EDGES=v.direct_jump_edges(OWN)
LEGACY_CALLS={0x19B3,0x19BE,0x19DC,0x1A18,0x1A40,0x1A51,0x1A72}
SECONDS,MEMORY_MIB,MAX_STEPS,MAX_EVENTS=600,384,4_000_000,2_000_000
REPORT=BUILD/'level-start-differential.json'
class Segments(ct.Structure):
    _fields_=[(n,ct.c_uint16) for n in ('retry','lookup','read','failure')]
class FullServices(ct.Structure):
    _fields_=[('selection',ct.POINTER(resources.SelectionServices)),('error',ct.c_void_p),('cleanup',ct.c_void_p)]
class Services(ct.Structure):
    _fields_=[('segments',ct.POINTER(Segments)),('resources',ct.POINTER(FullServices)),
              ('briefing',ct.POINTER(briefing.Services)),('bus',ct.POINTER(v.Bus)),('error_ds',ct.c_uint16)]
class Result(ct.Structure):
    _fields_=[('registers',v.Regs),('status',ct.c_uint16),('child_status',ct.c_uint16),('detail',ct.c_uint16)]
class DigitsResult(ct.Structure):
    _fields_=[(n,ct.c_uint16) for n in ('value','cursor','flags')]

def cases():
    rows=[]
    def add(name,**kw):rows.append(dict(name=name,**kw))
    for name,kw in (('menu',{}),('common',dict(entry=1)),('df',dict(flags=0x6D7)),
                    ('stack-wrap',dict(sp=0)),('stack-word-ffff',dict(sp=1)),
                    ('physical-wrap',dict(ss=0xFFFF,sp=0x11)),
                    ('live-es',dict(patch='saved-ds')),('vga-es',dict(patch='saved-vga'))):
        add('prefix-'+name,kind='prefix',expected=1,**kw)
    for order in (1,2,3,16,0):add('resources-order-'+str(order),kind='resources',order=order,expected=5)
    for name,kw in (('special',dict(special=1)),('cache-miss',dict(path='miss')),
                    ('parent-ret',dict(patch='resource-ret',expected=3)),
                    ('decimal-ret',dict(patch='decimal-ret',expected=2,child_status=3)),
                    ('decimal-fatal-target',dict(patch='decimal-ret',target=0x1949,expected=2,child_status=3))):
        add('resources-'+name,kind='resources',**(dict(expected=5)|kw))
    for load in v.LOADS:
        add(f'connected-{load:04x}',load=load)
        add(f'cancel-{load:04x}',load=load,leave=0x20)
    add('connected-common',entry=1)
    add('briefing-division-stop',total=0,expected=4,child_status=3)
    add('briefing-changed-return',patch='briefing-ret',expected=3)
    for value in range(256):add('digits-'+str(value),kind='digits',value=value)
    for name,kw in (('df',dict(flags=0x6D7)),('cursor-wrap',dict(si=0xFFFF)),
                    ('physical-wrap',dict(ds=0xFFFF,si=0xF))):
        add('digits-'+name,kind='digits',value=255,**kw)
    return [dict(load=v.LOADS[0],seed=0x4551+i,flags=0xAD7,group=1,selection=37,mode=2,
                 total=80,required=40,minutes=5,leave=0x40,input_mode=0,entry=0,kind='connected',order=1,
                 expected=0,child_status=0)|c for i,c in enumerate(rows)]

def packed(payload):
    # Independent backwards-output RLE fixture, verified by the asset decoder.
    data=payload[::-1];tokens=[];cursor=0
    while cursor<len(data):
        run=0
        if cursor:
            while cursor+run<len(data) and data[cursor+run]==data[cursor-1] and run<256:run+=1
        if run>=2:tokens.append(('match',(run,1)));cursor+=run
        else:
            end=cursor+1
            while end<len(data) and end-cursor<8:
                if end+1<len(data) and data[end]==data[end-1]==data[end+1]:break
                end+=1
            tokens.append(('literal',data[cursor:end]));cursor=end
    packet=resources.decoder.section(tokens)
    v.check(resources.decode_section(packet)[0]==payload,'constructed record encoding differs')
    return packet

def setup(c):
    if c['kind']=='digits':
        memory,device=v.initial_memory(c)
        r=v.default_regs(c['load'],c['seed'],flags=c['flags'],ds=c.get('ds',0x3000))
        r.update(ip=0x4BC2,ax=0xB000|c['value'],si=c.get('si',0x6000))
        return memory,r,device,{},b''
    memory,r,device=briefing.setup(dict(c,kind='briefing'))
    r.update(ip=0x4551 if c['entry'] else 0x454C,ss=c.get('ss',0x9000),sp=c.get('sp',0x8000))
    ds=r['ds'];v.sync_memory_byte(memory,device,ds,0x1F6D,0xA7)
    for off,value in ((0x1FF4,0x6FFF),(0x1FF0,0x8000)):
        v.put16(memory,ds,off,value,device)
    # Use ledger-owned cache offsets rather than guessing adjacent state fields.
    for name,value in dict(DatCacheBaseSegment=0x8800,DatCacheFreeSegment=0x8800,
                           DatCacheFreeOffset=0,DatCacheRemainingParagraphs=0x1000).items():
        v.put16(memory,ds,resources.field(name),value,device)
    for name,value in dict(DatCacheEnabled=255 if c.get('path') else 0,DatCacheSelected=0,
                           DatCacheRecordCount=0,DatCriticalErrorFlag=0,DatRetryEnabled=0).items():
        v.sync_memory_byte(memory,device,ds,resources.field(name),value)
    v.sync_memory_byte(memory,device,ds,0x54EE+c['selection'],c['order'])
    record=bytearray(2048);record[1]=99;record[3]=c['total'];record[5]=c['required'];record[7]=c['minutes']
    record[29]=c.get('special',0);record[0x120:0x124]=b'\xff\xff\x57\xad'
    record[-32:]=b'CONNECTED NATIVE LEVEL START'.ljust(32,b' ')
    v.check(len(record)==2048,'record title length differs')
    ground=bytes(1056);odd=bytearray(0x1180)
    for at in range(0,0x1180-55,56):odd[at:at+24]=record[:24];odd[at+24:at+56]=record[-32:]
    payloads=dict(level=packed(bytes(record))*8,ground=ground,odd=bytes(odd),
                  graphics=packed(bytes((255,))*128)+packed(bytes(32)),special=packed(bytes(128)))
    device.trace=briefing.menus.PackedVgaTrace(MAX_EVENTS)
    return memory,r,device,payloads,bytes(record)

class Access(briefing.Access):
    def __init__(self,*args):
        super().__init__(*args);self.quiet=False;self.omitted=0
    def emit(self,kind,address,value,flags,mask=v.FLAGS):
        if self.quiet and kind in ('read','write'):
            v.check(not v.VGA_BASE<=address<v.VGA_END,'legacy RAM child reached VGA')
            self.omitted+=1;v.check(self.omitted<=MAX_EVENTS,'legacy RAM access budget exhausted');return
        super().emit(kind,address,value,flags,mask)
    def access(self,kind,address,flags,mask=v.FLAGS,value=None):
        patch=self.c.get('patch');ds=self.r['ds'];sp=self.r['sp'];ss=self.r['ss']
        if patch not in self.providers:
            if patch in ('saved-ds','saved-vga') and kind=='read' and address==v.physical(ss,(sp-2)&65535):
                self.patch(ss,(sp-2)&65535,0xA000 if patch=='saved-vga' else 0x5000,patch)
            if patch=='decimal-ret' and kind=='write' and address==v.physical(ds,0x2551):
                self.patch(ss,(sp-8)&65535,self.c.get('target',0xD234),patch)
            if patch=='briefing-ret' and kind=='write' and address==v.physical(ss,(sp-2)&65535) and value==0x63:
                got=super().access(kind,address,flags,mask,value)
                self.patch(ss,(sp-2)&65535,0xD234,patch);return got
        return super().access(kind,address,flags,mask,value)

class Provider(resources.Provider):
    def read(self,*args):
        out=super().read(*args)
        if self.case.get('patch')=='resource-ret':
            v.put16(self.mem,self.regs['ss'],self.regs['sp'],0xD234)
        return out

def provider(c,memory,r,payloads,record):
    return Provider(c,memory,dict(r,sp=(r['sp']-2)&65535),r['ds'],payloads,record)

class Machine(v.OriginalMachine):
    def __init__(self,c,memory,r,device,payloads,record):
        frames=[];failed=[];self.child_status=0;self.detail=0
        self.provider=provider(c,memory,r,payloads,record)
        access=Access(dict(c,kind='briefing'),memory,r,device)
        def before(m,i):
            if i.address in (0xFB,0x4401):m.stop(0);return True
            if i.address==0x197D and c['kind']=='prefix':m.stop(1);return True
            if i.address==0x4566 and c['kind']=='resources':m.stop(5);return True
            if i.address==0x459C:
                q=m.state();divisor=q['cx']&255
                if not divisor or q['ax']//divisor>255:m.child_status=3;m.stop(4);return True
            access.quiet=any(f['legacy'] for f in frames)
            if i.mnemonic=='ret' and frames and frames[-1]['legacy']:access.quiet=False
            if i.mnemonic in ('call','lcall'):
                frames.append(dict(owner=i.address,resume=i.address+i.size,legacy=i.address in LEGACY_CALLS,far=i.mnemonic=='lcall'))
            return False
        def expected(m,off):
            v.check(bool(frames),'undeclared level-start return');frame=frames.pop();failed[:]=[frame]
            access.quiet=any(f['legacy'] for f in frames)
            return {(c['load'],frame['resume'])} if frame['far'] else {frame['resume']}
        def changed(m,off):
            owner=failed[-1]['owner']
            if owner in OWN:return 3
            if owner==0x19A0 or owner in LEGACY_CALLS:m.child_status=3;return 2
            raise v.OracleFailure('changed return outside inherited child contract')
        def interrupt(m,number):
            v.check(number==0x21,'undeclared loader interrupt');q=m.state();fn=q['ax']>>8;p=m.provider
            v.check(len(p.trace)<512,'DOS service budget exhausted')
            if fn in (0x3D,0x43):q['ax'],count,q['flags']=p.file(fn,q['ds'],q['dx'],q['flags']);q['cx']=count if fn==0x43 else q['cx']
            elif fn==0x23:q['ax'],q['flags']=p.query(q['ds'],q['dx'],q['flags'])
            elif fn==0x3F:q['ax'],q['flags']=p.read(q['bx'],q['ds'],q['dx'],q['cx'],q['flags'])
            elif fn==0x3E:q['ax'],q['flags']=p.close(q['bx'],q['ax'],q['flags'])
            else:raise v.OracleFailure('undeclared DOS function')
            m.cpu.mem_write(0,bytes(memory));m.cpu.mem_write(v.SIZE,bytes(memory));m.set_state(q)
            # The typed DOS ABI supplies all arithmetic flags; no IRQ transport is claimed.
            m.mask=v.FLAGS
        super().__init__(c,memory,r,device,c['kind']=='digits',instructions=INS,access=access,
            outer_returns=(0x4BE6,) if c['kind']=='digits' else (),
            child_returns={p:expected for p,i in INS.items() if i.mnemonic=='ret'},
            far_returns={p:expected for p,i in INS.items() if i.mnemonic=='retf'},
            before=before,interrupt=interrupt,changed_return_status=changed,max_steps=MAX_STEPS)
    def run(self):
        try:out=super().run()
        except v.OracleFailure as error:
            raise v.OracleFailure(f'{error}; state={self.state()}') from error
        out.update(child_status=self.child_status,detail=self.detail,
            services=self.provider.trace,omitted_ram_events=self.access.omitted);return out

class Native:
    def __init__(self,directory,mutation=0):
        self.lib=ct.CDLL(str(build(Path(directory)/f'level-start-{mutation}.dll',mutation,'level_start')))
        self.call=self.lib.lmn_start_selected_level;self.call.restype=Result
        self.call.argtypes=[v.MEM,ct.POINTER(v.Regs),ct.c_uint16,ct.c_int,ct.POINTER(Services)]
        self.digits=self.lib.lmn_write_decimal_digits_bus_core;self.digits.restype=DigitsResult
        self.digits.argtypes=[v.MEM,*([ct.c_uint16]*2),ct.c_uint8,ct.c_uint16,ct.POINTER(v.Bus)]
    def run(self,c,memory,r,device,payloads,record):
        memory,device=bytearray(memory),copy.deepcopy(device)
        access=Access(dict(c,kind='briefing'),memory,r,device);cb=v.NativeCallbacks(access)
        if c['kind']=='digits':
            out=self.digits((ct.c_uint8*v.SIZE).from_buffer(memory),r['ds'],r['si'],c['value'],r['flags'],ct.byref(cb.bus))
            return dict(regs=dict(r,ax=out.value,si=out.cursor,flags=out.flags,ip=0x4BE6),status=0,
                child_status=0,detail=0,memory=memory,device=device,events=access.events,
                providers=access.providers,cursor=access.cursor,services=[])
        p=provider(c,memory,r,payloads,record)
        def guarded(fn,out,*args):
            try:
                v.check(len(p.trace)<512,'DOS service budget exhausted')
                for (name,_),value in zip(out.contents._fields_,fn(*args)):setattr(out.contents,name,value)
            except BaseException as error:v.callback_failure(error)
        @resources.FILE
        def opened(_,m,seg,off,flags,out):guarded(p.file,out,0x3D,seg,off,flags)
        @resources.FILE
        def attributes(_,m,seg,off,flags,out):guarded(p.file,out,0x43,seg,off,flags)
        @resources.QUERY
        def query(_,m,seg,off,flags,out):guarded(p.query,out,seg,off,flags)
        @resources.READ
        def read(_,m,h,seg,off,count,flags,out):guarded(p.read,out,h,seg,off,count,flags)
        @resources.RETRY_FN
        def retry(*args):v.callback_failure(v.OracleFailure('retry UI outside selected domain'))
        @resources.OPEN
        def raw_open(_,m,seg,off,flags,out):
            def op(*args):a,b,f=p.file(0x3D,*args);return a,f
            guarded(op,out,seg,off,flags)
        @resources.OPEN
        def close(_,m,h,value,flags,out):guarded(p.close,out,h,value,flags)
        files=resources.Services(None,opened,attributes,retry);io=resources.Io(None,query,read)
        raw=resources.RawServices(None,raw_open,read,close)
        selection=resources.SelectionServices(ct.pointer(files),ct.pointer(io),ct.pointer(raw))
        full=FullServices(ct.pointer(selection),None,None)
        segments=Segments(*(v.get16(memory,r['cs'],resources.SYMS[name]['address']+delta) for name,delta in
            (('CheckDatFile',0x33),('SelectCachedDatFile',0x50),('ReadDatBytes',8),('DatReadFailure',1))))
        brief=briefing.Services(None,ct.pointer(cb.ports),ct.pointer(cb.bus))
        services=Services(ct.pointer(segments),ct.pointer(full) if c['kind']!='prefix' else None,
            ct.pointer(brief) if c['kind']=='connected' else None,ct.pointer(cb.bus),r['ds'])
        regs=v.Regs(**r);mem=(ct.c_uint8*v.SIZE).from_buffer(memory)
        out=self.call(mem,ct.byref(regs),(c['load']+0x9A9)&65535,c['entry'],ct.byref(services))
        return dict(regs={n:getattr(out.registers,n) for n in v.REG_NAMES},status=out.status,
            child_status=out.child_status,detail=out.detail,memory=memory,device=device,
            events=access.events,providers=access.providers,cursor=access.cursor,services=p.trace)

def compare(native,c):
    memory,r,device,payloads,record=setup(c)
    ref=Machine(c,bytearray(memory),dict(r),copy.deepcopy(device),payloads,record).run()
    v.check((ref['status'],ref['child_status'])==(c['expected'],c['child_status']),c['name']+': unexpected stop')
    actual=native.run(c,memory,r,device,payloads,record)
    v.compare_states(c['name'],actual,ref);v.require(actual['detail']==ref['detail'],'detail differs')
    if c.get('patch') and c['patch']!='resource-ret':v.check(c['patch'] in ref['providers'],'unused live-word fixture')
    if c['kind']=='digits':
        expected=f"{c['value']:03d}".encode()
        v.check(bytes(ref['memory'][v.physical(r['ds'],(r['si']+i)&65535)] for i in range(3))==expected,'independent decimal digits differ')
    if c['kind']=='connected' and not ref['status']:
        v.check(ref['regs']['ip']==(0x4401 if c['leave']==0x20 else 0xFB),'wrong game/menu jump')
        v.check(ref['regs']['sp']==r['sp'],'invented outer return')
        if c['leave']==0x20:v.check(ref['regs']['ax']==0x4563,'cancel did not consume its actual caller word')
        v.check(ref['memory'][v.physical(r['ds'],0x1F6D)]==(0xA7 if c['entry'] else 0),'wrong outcome reset ownership')
        v.check(ref['memory'][v.physical(r['ds'],0x41)]==50,'loaded header percentage differs')
        v.check(bytes(ref['memory'][v.physical(r['ds'],0xFCB+i)] for i in range(2048))==record,'loaded record differs')
    return ref

def hashes():
    paths={'metadata/symbols.json','metadata/oracle.json','metadata/toolchain-lock.json','assets/vgalemmi.exe',
           'assets/main.dat','c/lemmings_sym.h','c/regs.h','src/input_menu_and_retry.asm','src/resources.asm',
           'src/decimal_fields.asm','tools/difftest.py','tools/cbuild.py','tools/bounded_process.py'}
    for module in tuple(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            path=Path(name).resolve()
            if path.is_relative_to(ROOT) and path.suffix=='.py' and path.parts[-2] in ('tests','tools'):paths.add(path.relative_to(ROOT).as_posix())
    for path in source_files('level_start'):
        paths.add(path.relative_to(ROOT).as_posix());paths.add(path.with_suffix('.h').relative_to(ROOT).as_posix())
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}

MUTANTS=((1,'prefix-menu'),(2,'prefix-df'),(3,'resources-parent-ret'),(4,'cancel-1010'))
def worker(directory,snapshot,selected):
    before=hashes();v.check(before==json.loads(Path(snapshot).read_text()),'level-start inputs changed')
    native=Native(directory);rows=[];sites=set();edges=set()
    for c in cases():
        if selected and c['name'] not in selected:continue
        ref=compare(native,c);sites.update(ref['sites']);edges.update(ref['edges'])
        rows.append(dict(case=c['name'],steps=ref['steps'],events=len(ref['events']),omitted_ram_events=ref['omitted_ram_events'],status=ref['status']))
        del ref;gc.collect();print('CHECKED '+c['name'],flush=True)
    v.check(bool(rows),'empty level-start selection')
    if selected:return
    v.check(set(OWN)<=sites,'missing parent instruction sites')
    v.check(EDGES<=edges,'missing parent jump outcomes')
    mutants=[];lookup={c['name']:c for c in cases()}
    for mutation,name in MUTANTS:
        try:compare(Native(directory,mutation),lookup[name])
        except v.Mismatch as error:mutants.append(dict(mutation=mutation,case=name,completed=True,mismatch=str(error)))
        else:raise v.OracleFailure(f'level-start mutant{mutation} survived')
        gc.collect()
    v.check(before==hashes(),'level-start inputs changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(v.IMAGE),case_count=len(rows),comparison_count=len(rows),
        own_known_bytes=sum(i.size for i in OWN.values()),native_code_ranges=[list(p) for p in OWN_RANGES],
        executed_instruction_addresses=sorted(sites),own_executed_instruction_addresses=sorted(set(OWN)&sites),
        branch_edges=sorted(edges),own_branch_edges=sorted(EDGES),mutation_count=len(mutants),mutations=mutants,
        instruction_steps=sum(r['steps'] for r in rows),ordered_bus_events=sum(r['events'] for r in rows),rows=rows,input_hashes=before,
        limits=dict(worker_seconds=SECONDS,windows_process_mib=MEMORY_MIB,windows_tree_mib=MEMORY_MIB+256,
                    instructions_each=MAX_STEPS,events_each=MAX_EVENTS,legacy_ram_events_each=MAX_EVENTS),
        domain='454C/4551 -> native197D loader -> native4566 briefing -> JMP00FB or4401. Selector-own bus and full parent/briefing bus; original DAT/raw child instructions executed with explicit RAM-event projection under their existing ordinary-RAM/preserving-DOS/intact-internal-return contracts. Constructed valid files, pinned UI/fonts, quiescent IRQ, bounded device/input schedules. Gameplay00FB, retry UI, real platform and widened loader domains remain open.'))
    print(f'PASS level start: {len(rows)} comparisons,{len(set(OWN)&sites)} own sites,{len(EDGES)} outcomes,{len(mutants)} mutants',flush=True)

def main():
    if len(sys.argv)>=4 and sys.argv[1]=='--worker':worker(sys.argv[2],sys.argv[3],sys.argv[4:]);return
    selected=sys.argv[2:] if len(sys.argv)>1 and sys.argv[1]=='--focus' else []
    if sys.argv[1:] and not selected:raise SystemExit('usage: level_start.py [--focus CASE ...]')
    if not selected:REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='level-start-',parent=BUILD) as directory:
        snapshot=Path(directory)/'inputs.json';write_json(snapshot,hashes())
        run_bounded([sys.executable,__file__,'--worker',str(directory),str(snapshot),*selected],cwd=ROOT,timeout=SECONDS,memory_mib=MEMORY_MIB,check=True)
if __name__=='__main__':main()

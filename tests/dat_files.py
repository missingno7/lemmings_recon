"""Original file wrappers/native cache calls with declared DOS and retry seams."""
import ctypes
import random
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x
from dat_io_c import Regs,MEM
import dat_io as oracle
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build
from unpack import ASSET,unpack,relocated

IMAGE,ORACLE=unpack(ASSET.read_bytes())
SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ROOTS={k:SYMS[n] for k,n in (('open_file','OpenDatFile'),('check_file','CheckDatFile'))}
FATAL=SYMS['DatFileErrorTransfer']['address'];RETRY=SYMS['ShowResourceRetryScreen']['address']
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
LOCAL={i.address:i for s in ROOTS.values() for i in MD.disasm(IMAGE[s['address']:s['address']+s['size']],s['address'])}
HELPERS={i.address:i for n in ('PrepareDatCacheName','SelectCachedDatFile') for i in MD.disasm(
    IMAGE[SYMS[n]['address']:SYMS[n]['address']+SYMS[n]['size']],SYMS[n]['address'])}
INS=LOCAL|HELPERS
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}
CALL_FIELDS=('value','handle','count','filename_offset','source_cursor','output_cursor','base_cursor',
             'segment','extra_segment','stack_segment','stack_offset','flags')
MAPPING=dict(zip(CALL_FIELDS,('ax','bx','cx','dx','si','di','bp','ds','es','ss','sp','flags')))
class Call(ctypes.Structure):_fields_=[(n,ctypes.c_uint16) for n in CALL_FIELDS]
class ServiceResult(ctypes.Structure):_fields_=[(n,ctypes.c_uint16) for n in ('value','count','flags')]
class RetryResult(ctypes.Structure):_fields_=[(n,ctypes.c_uint16) for n in ('value','handle','base_cursor','flags')]
FILE=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,*([ctypes.c_uint16]*3),ctypes.POINTER(ServiceResult))
RETRY_FN=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,ctypes.POINTER(Call),ctypes.POINTER(RetryResult))
class Services(ctypes.Structure):_fields_=[('context',ctypes.c_void_p),('open',FILE),('attributes',FILE),('retry',RETRY_FN)]

def field(name):return SYMS[name]['address']
def prepare(case):
    rng=random.Random(0x1cb9+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ROOTS[case['kind']]['address'],ds=0x5000,dx=0x100,ss=0x7000,sp=case.get('sp',0x8000))
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    data=load+0x9a9
    filename=b'TESTFILE.DAT\0'
    mem[oracle.at(regs['ds'],regs['dx']):oracle.at(regs['ds'],regs['dx'])+len(filename)]=filename
    mem[oracle.at(regs['ds'],field('DatCacheEnabled'))]=case.get('enabled',0)
    mem[oracle.at(regs['ds'],field('DatCacheSelected'))]=case.get('selected',0)
    mem[oracle.at(regs['ds'],field('DatCriticalErrorFlag'))]=case.get('critical',0)
    mem[oracle.at(data,field('DatRetryEnabled'))]=case.get('retry_enabled',0)
    mem[oracle.at(regs['ds'],field('DatCacheRecordCount'))]=case.get('records',0)
    oracle.put16(mem,regs['ds'],field('DatCacheBaseSegment'),0x6000)
    mem[0x60000:0x6000b]=b'TESTFILEDAT' if case.get('hit') else b'NOTAFILEDAT'
    oracle.put16(mem,0x6000,11,0x20)
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    return mem,regs,flags,data

def provider(case,mem,data,caller_segment,stack_segment):
    attrs=0;retried=0;trace=[]
    def file(function,seg,off,inflags):
        nonlocal attrs
        failed=case.get('error',False) if function==0x3d else attrs<case.get('failures',0)
        if function==0x43:attrs+=1
        if case.get('service_save_alias'):
            # Outermost saved SI is at SP-12; its return word remains intact.
            oracle.put16(mem,stack_segment,(case.get('sp',0x8000)-12)&65535,0xbeef)
        value=5 if failed else (0x27 if function==0x3d else 0)
        outflags=(inflags&~0x8d5)|0x894|(1 if failed else 0)
        trace.append(dict(function=function,segment=seg,offset=off,flags=inflags&(0xfd7 if function==0x3d else 0xfc7),failed=failed))
        return value,0x1234 if function==0x43 else 0,outflags
    def retry(view):
        nonlocal retried
        retried+=1
        if oracle.get16(mem,view['ss'],view['sp'])!=field('DatAfterFileRetry'):raise AssertionError('Wrong retry return word')
        trace.append(dict(function='retry',view=view.copy()))
        mem[oracle.at(caller_segment,field('DatCriticalErrorFlag'))]=0
        if case.get('disable_retry'):mem[oracle.at(data,field('DatRetryEnabled'))]=0
        if case.get('retry_save_alias'):oracle.put16(mem,view['ss'],view['sp']+2,0xabcd)
        return 0x4567,0x6789,(view['flags']&~0x8d5)|0x891
    return file,retry,trace

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'dat_files-m{mutation}.dll',mutation,'dat_files')))
    for k in ROOTS:
        fn=getattr(lib,'lmn_dat_'+k+'_adapter');fn.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Services)];fn.restype=None
    return lib

def compare(lib,case):
    mem,regs,flags,data=prepare(case);c_mem=bytearray(mem);c_r=Regs(**regs,flags=flags)
    c_file,c_retry,c_trace=provider(case,c_mem,data,regs['ds'],regs['ss']);errors=[]
    def file(function,seg,off,inflags,out):
        try:out.contents.value,out.contents.count,out.contents.flags=c_file(function,seg,off,inflags)
        except Exception as e:errors.append(e)
    @FILE
    def opened(ctx,memory,seg,off,inflags,out):file(0x3d,seg,off,inflags,out)
    @FILE
    def attributes(ctx,memory,seg,off,inflags,out):file(0x43,seg,off,inflags,out)
    @RETRY_FN
    def retry(ctx,memory,call,out):
        try:
            view={reg:getattr(call.contents,n) for n,reg in MAPPING.items()}
            out.contents.value=0x1111
            out.contents.handle,out.contents.base_cursor,out.contents.flags=c_retry(view)
        except Exception as e:errors.append(e)
    services=Services(None,opened,attributes,retry)
    getattr(lib,'lmn_dat_'+case['kind']+'_adapter')((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(c_r),ctypes.byref(services))
    if errors:raise errors[0]
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);sites=set();edges=set();previous=None;done=False
    u_file,u_retry,u_trace=provider(case,mem,data,regs['ds'],regs['ss'])
    def interrupt(uc,num,_):
        if num!=0x21:raise AssertionError('Unexpected interrupt')
        mem[:]=uc.mem_read(0,1<<20)
        function=uc.reg_read(oracle.REG['ax'])>>8
        if function not in (0x3d,0x43):raise AssertionError('Wrong DOS function')
        if function==0x43 and uc.reg_read(oracle.REG['cx'])!=0:raise AssertionError('AH43 input CX not cleared')
        value,count,outflags=u_file(function,uc.reg_read(oracle.REG['ds']),uc.reg_read(oracle.REG['dx']),uc.reg_read(x.UC_X86_REG_EFLAGS))
        uc.mem_write(0,bytes(mem));uc.reg_write(oracle.REG['ax'],value)
        if function==0x43:uc.reg_write(oracle.REG['cx'],count)
        uc.reg_write(x.UC_X86_REG_EFLAGS,outflags)
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off in (0xff00,FATAL):done=True;uc.emu_stop();return
        if off==RETRY:
            mem[:]=uc.mem_read(0,1<<20)
            view={n:uc.reg_read(reg) for n,reg in oracle.REG.items() if n not in ('cs','ip')}
            view['flags']=uc.reg_read(x.UC_X86_REG_EFLAGS)&65535
            bx,bp,outflags=u_retry(view);uc.mem_write(0,bytes(mem))
            # Deliberate callee clobbers of saved registers should disappear on POP.
            for n,value in dict(ax=0x1111,bx=bx,bp=bp,si=0x2222,di=0x3333,ds=0x4444,es=0x5555,cx=0x6666,dx=0x7777).items():uc.reg_write(oracle.REG[n],value)
            sp=uc.reg_read(oracle.REG['sp']);uc.reg_write(oracle.REG['ip'],oracle.get16(mem,regs['ss'],sp));uc.reg_write(oracle.REG['sp'],(sp+2)&65535)
            uc.reg_write(x.UC_X86_REG_EFLAGS,outflags);previous=None;return
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in INS:raise AssertionError(f'Escaped file wrappers at {off:x}')
        sites.add(off);previous=off
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,interrupt)
    u.emu_start(oracle.at(regs['cs'],regs['ip']),0,count=1000000)
    if not done:raise AssertionError('File wrappers exceeded budget')
    for n,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(c_r,n):raise AssertionError(f'{case["name"]}: {n} C={getattr(c_r,n):04x}/original={u.reg_read(reg):04x}')
    if (c_r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&0xfd7:raise AssertionError(f'{case["name"]}: flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: memory differs at {p:05x}')
    if u_trace!=c_trace:raise AssertionError(f'{case["name"]}: service/callee trace differs {u_trace}/{c_trace}')
    return sites,edges

def cases():
    result=[]
    def add(name,kind,**kw):result.append(dict(name=name,kind=kind,seed=len(result),**kw))
    for enabled in (0,1,255):
        for selected in (0,1,255):
            for df in (False,True):add(f'open-{enabled}-{selected}-{df}','open_file',enabled=enabled,selected=selected,df=df)
    add('open-error','open_file',error=True)
    add('open-save-alias','open_file',service_save_alias=True)
    add('check-direct','check_file')
    add('check-critical-fatal','check_file',critical=255)
    add('check-dos-fatal','check_file',failures=1)
    add('check-one-retry','check_file',failures=1,retry_enabled=255)
    add('check-two-retries','check_file',failures=2,retry_enabled=255)
    add('check-critical-retry','check_file',critical=255,retry_enabled=255)
    add('check-retry-disabled-after-callee','check_file',failures=2,retry_enabled=255,disable_retry=True)
    add('check-retry-saved-slot-alias','check_file',failures=1,retry_enabled=255,retry_save_alias=True)
    add('check-two-retries-saved-slot-alias','check_file',failures=2,retry_enabled=255,retry_save_alias=True)
    add('check-cache-hit','check_file',enabled=255,records=1,hit=True)
    add('check-cache-miss','check_file',enabled=255,records=1)
    add('check-empty-cache','check_file',enabled=255)
    add('check-service-save-alias','check_file',service_save_alias=True)
    add('check-df-direct','check_file',df=True)
    for kind in ROOTS:
        for sp in (0,1,65535):add(f'{kind}-stack-{sp}',kind,sp=sp,failures=1 if kind=='check_file' else 0,retry_enabled=255)
    return result

def main():
    report=BUILD/'dat-files-differential.json';report.unlink(missing_ok=True)
    baseline=cases();lib=library();sites=set();edges=set()
    for case in baseline:
        a,b=compare(lib,case);sites|=a;edges|=b
    if not set(LOCAL)<=sites:raise AssertionError(f'Missing wrapper instructions {set(LOCAL)-sites}')
    required={e for e in EDGES if e[0] in LOCAL}
    if not required<=edges:raise AssertionError(f'Missing wrapper branch edges {required-edges}')
    mutations=[]
    for mutation in (1,2,3):
        lib=library(mutation);hit=None
        for case in baseline:
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if hit is None:raise AssertionError(f'File mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=('c/dat_files.c','c/dat_files.h','c/dat_cache.c','c/dat_cache.h','c/lemmings_sym.h','c/regs.h',
           'tests/dat_files.py','tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','metadata/symbols.json')
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=3,
        mutations_detected=mutations,cases=baseline,translated_code_bytes=sum(i.size for i in LOCAL.values()),
        executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),wrapper_instruction_addresses=sorted(LOCAL),
        wrapper_branch_edges=sorted(required),input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Constructed DOS AH3D/AH43 and declared 4B1C game-callee seam; original wrappers/cache helpers only; 1949 fatal exit explicit'))
    print(f'PASS DAT file C: {len(baseline)} cases, {len(LOCAL)} wrapper sites, {len(required)} wrapper edges; 3 compiled mutations detected')

if __name__=='__main__':main()

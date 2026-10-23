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
HANDLER=SYMS['CriticalErrorHandler']['address']
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
LOCAL={i.address:i for s in ROOTS.values() for i in MD.disasm(IMAGE[s['address']:s['address']+s['size']],s['address'])}
HELPERS={i.address:i for n in ('PrepareDatCacheName','SelectCachedDatFile') for i in MD.disasm(
    IMAGE[SYMS[n]['address']:SYMS[n]['address']+SYMS[n]['size']],SYMS[n]['address'])}
INS=LOCAL|HELPERS
HANDLER_INS={i.address:i for i in MD.disasm(IMAGE[HANDLER:HANDLER+SYMS['CriticalErrorHandler']['reachable_instruction_bytes']],HANDLER)}
# Constructed DOS side of an INT24 delivery: DOS's own code/data/stack segments.
DOS_CS,DOS_RESUME,DOS_DS,DOS_SS,DOS_SP=0x0070,0x4321,0x0080,0x0300,0x0800
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
    data=load+0x9a9
    # Connected INT24 cases call with the real game DS, where the handler stores.
    regs.update(cs=load,ip=ROOTS[case['kind']]['address'],ds=data if case.get('game_ds') else 0x5000,
                dx=0x100,ss=0x7000,sp=case.get('sp',0x8000))
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
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

HANDLER_REGS=('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip')
def handler_entry(mem,load,seed,*,ds,ax,frame_flags,entry_flags,ss=DOS_SS,sp=DOS_SP):
    """DOS-side INT24 delivery fixture: frame at SS:SP, CPU-cleared IF/TF."""
    rng=random.Random(0x18f8+seed)
    r={n:rng.randrange(65536) for n in HANDLER_REGS}
    r.update(ax=ax,ds=ds,ss=ss,sp=sp,cs=load,ip=HANDLER,flags=(entry_flags&~0x300)|2)
    oracle.put16(mem,ss,sp,DOS_RESUME);oracle.put16(mem,ss,sp+2,DOS_CS);oracle.put16(mem,ss,sp+4,frame_flags)
    return r

def original_handler(mem,r):
    """Execute the original 18F8..IRET on canonical memory until the frame's return."""
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n in HANDLER_REGS:u.reg_write(oracle.REG[n],r[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,r['flags'])
    target=oracle.at(oracle.get16(mem,r['ss'],r['sp']+2),oracle.get16(mem,r['ss'],r['sp']));sites=[];done=False
    def code(uc,pc,size,_):
        nonlocal done
        if pc==target and sites and sites[-1]==HANDLER+15:done=True;uc.emu_stop();return
        off=pc-(r['cs']<<4)
        if uc.reg_read(oracle.REG['cs'])!=r['cs'] or off not in HANDLER_INS:raise AssertionError(f'Escaped INT24 handler at {pc:05x}')
        sites.append(off)
    def interrupt(uc,num,_):raise AssertionError('Unexpected interrupt in INT24 handler')
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,interrupt)
    u.emu_start(oracle.at(r['cs'],r['ip']),0,count=64)
    if not done:raise AssertionError('INT24 handler did not return to its frame')
    mem[:]=u.mem_read(0,1<<20)
    out={n:u.reg_read(oracle.REG[n]) for n in HANDLER_REGS};out['flags']=u.reg_read(x.UC_X86_REG_EFLAGS)&65535
    return out,set(sites)

def native_handler(lib):
    def run(mem,r):
        regs=Regs(**r);lib.lmn_dat_critical_error_adapter((ctypes.c_uint8*(1<<20)).from_buffer(mem),ctypes.byref(regs))
        return {n:getattr(regs,n) for n in HANDLER_REGS+('flags',)},set()
    return run

def provider(case,mem,data,caller_segment,stack_segment,handler=None):
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
        if failed and case.get('int24'):
            # DOS hits a device error inside this service and calls the
            # installed INT24 vector before the service returns. AH=1A/AL=drive,
            # DS=DOS; the handler ignores them. Only "ignore" (AL=00) is a
            # supported DOS continuation in this domain.
            r=handler_entry(mem,data-0x9a9,case['seed'],ds=DOS_DS,ax=0x1a00|(case['seed']&3),
                            frame_flags=0x7002|(inflags&0x4d5),entry_flags=0x0046)
            out,_=handler(mem,r)
            trace.append(dict(function='int24',regs=out))
            if out['ax']&255:raise AssertionError(f'INT24 handler requested DOS action {out["ax"]&255:02x}')
            if (out['cs'],out['ip'],out['ss'],out['sp'])!=(DOS_CS,DOS_RESUME,DOS_SS,DOS_SP+6):raise AssertionError('INT24 handler did not IRET to DOS')
            if case['int24']=='ignored':value,outflags=(0x27 if function==0x3d else 0),outflags&~1
            else:value=0x53  # DOS 3.1+ converts a disallowed ignore into fail.
            failed=bool(outflags&1)
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
    lib.lmn_dat_critical_error_adapter.argtypes=[MEM,ctypes.POINTER(Regs)];lib.lmn_dat_critical_error_adapter.restype=None
    return lib

def compare_handler(lib,case):
    """Direct INT24 entry: original 18F8..IRET versus the C adapter."""
    rng=random.Random(0x24+case['seed']);load=case['load']
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    ds={'dos':DOS_DS,'game':load+0x9a9,'top':0xffff,'zero':0}[case['ds']]
    mem[oracle.at(load+0x9a9,field('DatCriticalErrorFlag'))]=case.get('flag',0)
    r=handler_entry(mem,load,case['seed'],ds=ds,ax=case['ax'],frame_flags=case['frame_flags'],
                    entry_flags=case['entry_flags'],sp=case.get('sp',DOS_SP))
    c_mem=bytearray(mem);c_out,_=native_handler(lib)(c_mem,r)
    u_out,sites=original_handler(mem,r)
    for n in HANDLER_REGS:
        if c_out[n]!=u_out[n]:raise AssertionError(f'{case["name"]}: {n} C={c_out[n]:04x}/original={u_out[n]:04x}')
    if c_out['flags']!=u_out['flags']:raise AssertionError(f'{case["name"]}: flags C={c_out["flags"]:04x}/original={u_out["flags"]:04x}')
    if mem!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(mem,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: memory differs at {p:05x}')
    return sites

def compare(lib,case):
    mem,regs,flags,data=prepare(case);c_mem=bytearray(mem);c_r=Regs(**regs,flags=flags)
    c_file,c_retry,c_trace=provider(case,c_mem,data,regs['ds'],regs['ss'],native_handler(lib));errors=[]
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
    handler_sites=set()
    def original(m,r):
        out,s=original_handler(m,r);handler_sites.update(s);return out,s
    u_file,u_retry,u_trace=provider(case,mem,data,regs['ds'],regs['ss'],original)
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
    if case.get('expect_retries') is not None and sum(t['function']=='retry' for t in u_trace)!=case['expect_retries']:
        raise AssertionError(f'{case["name"]}: retry route not taken as declared')
    if case.get('expect_flag') is not None and actual[oracle.at(data,field('DatCriticalErrorFlag'))]!=case['expect_flag']:
        raise AssertionError(f'{case["name"]}: final critical flag differs from declared route')
    return sites|handler_sites,edges

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
    # Connected INT24: DOS calls the installed handler inside AH43/AH3D.
    # "ignored" returns success, so only the live 1FDF byte selects the retry.
    add('check-int24-ignored-retry','check_file',game_ds=True,failures=1,int24='ignored',retry_enabled=255,expect_retries=1,expect_flag=0)
    add('check-int24-fail-retry','check_file',game_ds=True,failures=1,int24='fail',retry_enabled=255,expect_retries=1,expect_flag=0)
    add('check-int24-twice-retry','check_file',game_ds=True,failures=2,int24='ignored',retry_enabled=255,expect_retries=2,expect_flag=0)
    add('check-int24-ignored-fatal','check_file',game_ds=True,failures=1,int24='ignored',expect_retries=0,expect_flag=0xff)
    add('open-int24-ignored','open_file',game_ds=True,error=True,int24='ignored',expect_flag=0xff)
    add('open-int24-fail','open_file',game_ds=True,error=True,int24='fail',df=True,expect_flag=0xff)
    return result

def handler_cases():
    result=[]
    def add(name,**kw):result.append(dict(name=name,seed=len(result),**kw))
    for load in (0x1010,0x1213,0x2345):
        for ds in ('dos','game','top','zero'):
            add(f'int24-{load:04x}-{ds}',load=load,ds=ds,ax=0x1a00|len(result),frame_flags=0x7202|(len(result)*0x95&0x4d5),entry_flags=0x0ad7)
    add('int24-frame-if-clear-df',load=0x1010,ds='dos',ax=0xffff,frame_flags=0x0402,entry_flags=0x0002)
    add('int24-entry-df-frame-clear',load=0x1213,ds='dos',ax=0x0000,frame_flags=0x08d7,entry_flags=0x0402)
    add('int24-flag-already-set',load=0x2345,ds='dos',ax=0x1234,frame_flags=0x0202,entry_flags=0x0046,flag=0xff)
    add('int24-flag-other-value',load=0x1010,ds='game',ax=0x00ff,frame_flags=0x0282,entry_flags=0x0881,flag=0x5a)
    add('int24-sp-zero',load=0x1213,ds='dos',ax=0x3c02,frame_flags=0x0246,entry_flags=0x0002,sp=0)
    add('int24-sp-wrap',load=0x2345,ds='top',ax=0x3c02,frame_flags=0x0a93,entry_flags=0x0004,sp=0xfffc)
    add('int24-frame-reserved-bits',load=0x1010,ds='dos',ax=0x0e01,frame_flags=0xf6d7,entry_flags=0x0fd7)
    return result

def main():
    report=BUILD/'dat-files-differential.json';report.unlink(missing_ok=True)
    baseline=cases();handlers=handler_cases();lib=library();sites=set();edges=set();handler_sites=set()
    for case in baseline:
        a,b=compare(lib,case);sites|=a;edges|=b
    for case in handlers:handler_sites|=compare_handler(lib,case)
    if set(HANDLER_INS)-sites:raise AssertionError(f'Connected INT24 cases missed {set(HANDLER_INS)-sites}')
    if set(HANDLER_INS)-handler_sites:raise AssertionError(f'Direct INT24 cases missed {set(HANDLER_INS)-handler_sites}')
    if not set(LOCAL)<=sites:raise AssertionError(f'Missing wrapper instructions {set(LOCAL)-sites}')
    required={e for e in EDGES if e[0] in LOCAL}
    if not required<=edges:raise AssertionError(f'Missing wrapper branch edges {required-edges}')
    mutations=[]
    # 1-3 wrappers; 4 AL left nonzero (not ignore); 5 flag stored through the
    # incoming DOS DS; 6 DS not restored; 7 IRET leaves handler flags.
    for mutation in (1,2,3,4,5,6,7):
        lib=library(mutation);hit=None
        for case in baseline+handlers:
            try:compare_handler(lib,case) if 'load' in case else compare(lib,case)
            except AssertionError:hit=case['name'];break
        if hit is None:raise AssertionError(f'File mutation {mutation} survived')
        found=dict(mutation=mutation,case=hit)
        if mutation>=4:
            # Handler mutants must also fail a direct INT24 entry, not only the
            # connected retry route.
            for case in handlers:
                try:compare_handler(lib,case)
                except AssertionError:found['direct_case']=case['name'];break
            else:raise AssertionError(f'Handler mutation {mutation} survived direct INT24 entries')
        mutations.append(found)
    paths=('c/dat_files.c','c/dat_files.h','c/dat_cache.c','c/dat_cache.h','c/lemmings_sym.h','c/regs.h',
           'tests/dat_files.py','tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','metadata/symbols.json')
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline)+len(handlers),mutation_count=len(mutations),
        mutations_detected=mutations,cases=baseline,handler_cases=handlers,
        translated_code_bytes=sum(i.size for i in LOCAL.values())+sum(i.size for i in HANDLER_INS.values()),
        executed_instruction_addresses=sorted(sites|handler_sites),branch_edges=sorted(edges),wrapper_instruction_addresses=sorted(LOCAL),
        handler_instruction_addresses=sorted(HANDLER_INS),
        wrapper_branch_edges=sorted(required),input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Constructed DOS AH3D/AH43, DOS-delivered INT24 to original/native 18F8 (ignore only), and declared 4B1C game-callee seam; original wrappers/cache helpers only; 1949 fatal exit explicit'))
    print(f'PASS DAT file C: {len(baseline)} wrapper + {len(handlers)} INT24 cases, {len(LOCAL)} wrapper sites, {len(required)} wrapper edges, '
          f'{len(HANDLER_INS)} handler sites; {len(mutations)} compiled mutations detected')

if __name__=='__main__':main()

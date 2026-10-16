"""Resource load pipeline: original callers versus direct native C core calls."""
import ctypes
import random
from dat_files import Services,FILE,RETRY_FN,Call,MAPPING,ServiceResult,RetryResult
from dat_io_c import Regs,Io,QUERY,READ,MEM
import dat_section as decoder
import dat_io as oracle
from common import ROOT,BUILD,sha,write_json,read_json
from cbuild import build
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x

SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ENTRY=SYMS['LoadDatResource']['address'];TAIL=SYMS['DecodeDatPreservingSegment']['address']
AFTER=SYMS['DatAfterResourceCheck']['address'];RETRY=SYMS['ShowResourceRetryScreen']['address']
FATALS=(SYMS['DatFileErrorTransfer']['address'],SYMS['DatFatalTransfer']['address'])
LOCAL={i.address:i for i in decoder.MD.disasm(decoder.IMAGE[ENTRY:decoder.ENTRY],ENTRY) if i.mnemonic!='nop'}
from dat_files import INS as FILE_INS
INS=LOCAL|decoder.INS|FILE_INS
BRANCHES={pc for pc,i in INS.items() if i.group(decoder.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in LOCAL.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in LOCAL.items() if pc in BRANCHES and i.mnemonic!='jmp'}
def field(name):return SYMS[name]['address']

def cases():
    out=[]
    def add(name,data,**kw):out.append(dict(name=name,data=data,seed=len(out),**kw))
    for case in decoder.cases()[:9]:add(case['name'],case['data'],path=case['path'])
    packet=decoder.section([('literal',b'Q')])
    add('open-carry-ignored',packet,open_errors=1)
    add('open-critical-retry',packet,open_critical=True)
    add('check-file-retry',packet,attribute_errors=1)
    add('check-file-fatal',packet,attribute_errors=1,retry_enabled=0)
    add('decoder-header-fatal',packet,read_error=0)
    add('decoder-payload-fatal',packet,read_error=1)
    add('after-check-carry-retry',packet,after_check=True,carry=True)
    add('after-check-critical-retry',packet,after_check=True,critical=True)
    add('saved-ds-alias',decoder.section([('literal',b'\x12')]),output_segment=0x7000,output=0x7fff)
    add('shared-tail',packet,tail=True)
    add('shared-tail-saved-ds-alias',decoder.section([('literal',b'\x12')]),tail=True,output_segment=0x7000,output=0x7fff)
    add('shared-tail-fatal',packet,tail=True,read_error=0)
    for sp in (0,1,65535):add(f'stack-{sp}',packet,sp=sp)
    return out

def prepare(case):
    rng=random.Random(0x1b79+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(decoder.IMAGE)]=decoder.relocated(decoder.IMAGE,decoder.ORACLE['relocations'],load)
    data=load+0x9a9;regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=TAIL if case.get('tail') else AFTER if case.get('after_check') else ENTRY,
        ds=0x5000 if case.get('tail') else data,cx=0x5000,es=case.get('output_segment',0x6000),si=0,
        di=case.get('output',0),dx=0x2200,ss=0x7000,sp=case.get('sp',0x8000),bx=7)
    flags=2|((case['seed']*0x95)&0xad4)|(1 if case.get('carry') else 0)
    mem[oracle.at(data,0x2200):oracle.at(data,0x2200)+13]=b'TESTFILE.DAT\0'
    path=case.get('path','direct')
    for name,value in dict(DatCacheEnabled=0 if path=='direct' else 255,DatCacheSelected=0,
        DatCacheRecordCount=1 if path=='hit' else 0,DatCriticalErrorFlag=255 if case.get('critical') else 0,
        DatRetryEnabled=case.get('retry_enabled',255)).items():mem[oracle.at(data,field(name))]=value
    for name,value in dict(DatCacheBaseSegment=0x6000,DatCacheFreeSegment=0x6000,
        DatCacheFreeOffset=0,DatCacheRemainingParagraphs=0x1000).items():oracle.put16(mem,data,field(name),value)
    if path=='hit':
        mem[0x60000:0x6000b]=b'TESTFILEDAT';oracle.put16(mem,0x6000,11,len(case['data']))
        mem[0x6000d:0x6000d+len(case['data'])]=case['data']
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    if case.get('after_check'):
        regs['sp']=(regs['sp']-2)&65535;oracle.put16(mem,regs['ss'],regs['sp'],0x5000)
    return mem,regs,flags,data

def providers(case,mem,data):
    trace=[];position=0;opens=0;attributes=0;reads=0
    def file(function,seg,offset,flags):
        nonlocal opens,attributes,position
        if function==0x3d:
            failed=opens<case.get('open_errors',0)
            if case.get('open_critical') and opens==0:mem[oracle.at(data,field('DatCriticalErrorFlag'))]=255
            opens+=1;position=0;value=5 if failed else 7;count=0
        else:
            failed=attributes<case.get('attribute_errors',0);attributes+=1;value=5 if failed else 0;count=0x1234
        trace.append(dict(function=function,segment=seg,offset=offset,flags=flags&(0xfd7 if function==0x3d else 0xfc7)))
        return value,count,(flags&~0x8d5)|0x894|(1 if failed else 0)
    def query(seg,offset,flags):
        oracle.put16(mem,seg,offset+33,len(case['data']));oracle.put16(mem,seg,offset+35,0)
        trace.append(dict(function=0x23,segment=seg,offset=offset,flags=flags&0xfd7))
        return 0x2300,(flags&~0x8d5)|0x894
    def read(handle,seg,offset,count,flags):
        nonlocal position,reads
        failed=reads==case.get('read_error',-1);reads+=1
        part=case['data'][position:position+count]
        if not failed:
            for n,value in enumerate(part):mem[oracle.at(seg,offset+n)]=value
            position+=len(part)
        trace.append(dict(function=0x3f,handle=handle,segment=seg,offset=offset,count=count,flags=flags&0xfd7))
        return 5 if failed else len(part),(flags&~0x8d5)|0x894|(1 if failed else 0)
    def retry(view):
        trace.append(dict(function='retry',view=view.copy()))
        mem[oracle.at(data,field('DatCriticalErrorFlag'))]=0
        return 0x1111,0x4567,0x6789,(view['flags']&~0x8d5)|0x891
    return file,query,read,retry,trace

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'dat_load-m{mutation}.dll',mutation,'dat_load')))
    for n in ('load','load_after_check'):getattr(lib,'lmn_dat_'+n+'_adapter').argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Services),ctypes.POINTER(Io)]
    lib.lmn_dat_decode_preserving_segment_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Io)]
    return lib

def compare(lib,case):
    mem,regs,flags,data=prepare(case);c_mem=bytearray(mem);r=Regs(**regs,flags=flags)
    cfile,cquery,cread,cretry,ctrace=providers(case,c_mem,data);errors=[]
    def guarded(fn,out,*args):
        try:
            values=fn(*args)
            for (n,_),v in zip(out.contents._fields_,values):setattr(out.contents,n,v)
        except Exception as e:errors.append(e)
    @FILE
    def opened(ctx,memory,seg,offset,inflags,out):guarded(cfile,out,0x3d,seg,offset,inflags)
    @FILE
    def attributes(ctx,memory,seg,offset,inflags,out):guarded(cfile,out,0x43,seg,offset,inflags)
    @QUERY
    def query(ctx,memory,seg,offset,inflags,out):guarded(cquery,out,seg,offset,inflags)
    @READ
    def read(ctx,memory,handle,seg,offset,count,inflags,out):guarded(cread,out,handle,seg,offset,count,inflags)
    @RETRY_FN
    def retry(ctx,memory,call,out):guarded(cretry,out,{reg:getattr(call.contents,n) for n,reg in MAPPING.items()})
    services=Services(None,opened,attributes,retry);io=Io(None,query,read)
    if case.get('tail'):lib.lmn_dat_decode_preserving_segment_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r),ctypes.byref(io))
    else:getattr(lib,'lmn_dat_load_after_check_adapter' if case.get('after_check') else 'lmn_dat_load_adapter')((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r),ctypes.byref(services),ctypes.byref(io))
    if errors:raise errors[0]
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();previous=None;done=False
    uf,uq,ur,ut,trace=providers(case,mem,data)
    def interrupt(uc,num,_):
        if num!=0x21:raise AssertionError('Unexpected interrupt')
        mem[:]=uc.mem_read(0,1<<20);function=uc.reg_read(oracle.REG['ax'])>>8;seg=uc.reg_read(oracle.REG['ds']);offset=uc.reg_read(oracle.REG['dx']);inflags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        if function in (0x3d,0x43):value,count,outflags=uf(function,seg,offset,inflags)
        elif function==0x23:value,outflags=uq(seg,offset,inflags)
        elif function==0x3f:value,outflags=ur(uc.reg_read(oracle.REG['bx']),seg,offset,uc.reg_read(oracle.REG['cx']),inflags)
        else:raise AssertionError('Wrong service')
        uc.mem_write(0,bytes(mem));uc.reg_write(oracle.REG['ax'],value)
        if function==0x43:uc.reg_write(oracle.REG['cx'],count)
        uc.reg_write(x.UC_X86_REG_EFLAGS,outflags)
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off in (0xff00,*FATALS):done=True;uc.emu_stop();return
        if off==RETRY:
            mem[:]=uc.mem_read(0,1<<20);view={n:uc.reg_read(reg) for n,reg in oracle.REG.items() if n not in ('cs','ip')};view['flags']=uc.reg_read(x.UC_X86_REG_EFLAGS)&65535
            value,bx,bp,outflags=ut(view);uc.mem_write(0,bytes(mem))
            for n,v in dict(ax=value,bx=bx,bp=bp,si=0x2222,di=0x3333,ds=0x4444,es=0x5555,cx=0x6666,dx=0x7777).items():uc.reg_write(oracle.REG[n],v)
            sp=uc.reg_read(oracle.REG['sp']);uc.reg_write(oracle.REG['ip'],oracle.get16(mem,regs['ss'],sp));uc.reg_write(oracle.REG['sp'],(sp+2)&65535);uc.reg_write(x.UC_X86_REG_EFLAGS,outflags);previous=None;return
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in INS:raise AssertionError(f'Escaped loader at {off:x}')
        seen.add(off);previous=off
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,interrupt);u.emu_start(oracle.at(regs['cs'],regs['ip']),0,count=5000000)
    if not done:raise AssertionError('Loader exceeded budget')
    for n,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(r,n):raise AssertionError(f'{case["name"]}: {n} C={getattr(r,n):04x}/original={u.reg_read(reg):04x}')
    mask=0xfd7 if u.reg_read(oracle.REG['ip']) in FATALS else 0xfc7
    if (r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&mask:raise AssertionError('Exit flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: memory differs at {p:05x}')
    if trace!=ctrace:raise AssertionError(f'{case["name"]}: service trace differs {trace}/{ctrace}')
    return seen,edges

def main():
    report=BUILD/'dat-load-differential.json';report.unlink(missing_ok=True);baseline=cases();lib=library();seen=set();edges=set()
    for case in baseline:
        a,b=compare(lib,case);seen|=a;edges|=b
    if not set(LOCAL)<=seen or not EDGES<=edges:raise AssertionError(f'Missing caller sites/edges {set(LOCAL)-seen}/{EDGES-edges}')
    mutations=[]
    for mutation in (1,2,3):
        lib=library(mutation);hit=None
        for case in baseline:
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if not hit:raise AssertionError(f'Loader mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=tuple('c/'+n for n in ('dat_load.c','dat_load.h','dat_files.c','dat_files.h','dat_cache.c','dat_cache.h','dat_section.c','dat_section.h','dat_io.c','dat_io.h','dat.c','dat.h','regs.h','lemmings_sym.h'))
    paths+=('tests/dat_load.py','tests/dat_files.py','tests/dat_section.py','tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','metadata/symbols.json','assets/vgalemmi.exe','assets/adlib.dat','assets/tandysnd.dat','assets/main.dat')
    public=[{k:v for k,v in c.items() if k!='data'}|dict(input_sha256=sha(c['data'])) for c in baseline]
    write_json(report,dict(image='main',image_sha256=sha(decoder.IMAGE),case_count=len(baseline),mutation_count=3,mutations_detected=mutations,cases=public,
        executed_instruction_addresses=sorted(seen),caller_instruction_addresses=sorted(LOCAL),caller_branch_edges=sorted(EDGES),branch_edges=sorted(edges),
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},domain='Integrated native file/cache/read/decoder pipeline; declared DOS and4B1C seams; two constructed post-check caller states; fatal exits explicit'))
    print(f'PASS DAT resource C: {len(baseline)} cases, {len(LOCAL)} caller sites, {len(EDGES)} caller edges; 3 compiled mutations detected')
if __name__=='__main__':main()

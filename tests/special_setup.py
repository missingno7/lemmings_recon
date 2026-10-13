"""Connected original metadata/RLE/VGA/DAT setup versus direct native cores."""
import ctypes
import random
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR,UC_HOOK_INSN,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
from dat_io_c import Regs,Io,QUERY,READ,MEM,Result
from dat_files import Services,FILE,RETRY_FN,MAPPING
import dat_io as oracle
import dat_load as loader
import dat_section as decoder
import resource_rle as rle
import special_blit as blit
from resources import decode_section,section_spans
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build

SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ROUTINE=SYMS['SetupSpecialGraphicsResource'];ENTRY=ROUTINE['address'];END=ENTRY+ROUTINE['size']
LOCAL={i.address:i for i in decoder.MD.disasm(decoder.IMAGE[ENTRY:END],ENTRY)}
INS=LOCAL|loader.INS|rle.INS|blit.INS
BRANCHES={pc for pc,i in INS.items() if i.group(decoder.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
CLOSE=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,*([ctypes.c_uint16]*3),ctypes.POINTER(Result))
class SetupServices(ctypes.Structure):
    _fields_=[('files',ctypes.POINTER(Services)),('io',ctypes.POINTER(Io)),('raster',ctypes.POINTER(blit.Bus)),('context',ctypes.c_void_p),('close',CLOSE)]

def field(name):return SYMS[name]['address']
def constructed_special(df=False):
    prefix=bytes((n*17+3)&255 for n in range(40))
    if df:return prefix,b'\x80'*4
    streams=[]
    for n in range(4):
        # Three distinct plane banks, exactly4800 bytes per bank. Control81=128.
        streams.append(b''.join(bytes([0x81,0x11*(n+1)+plane])*37+bytes([0xc1,0x11*(n+1)+plane]) for plane in range(3))+b'\x80')
    return prefix,b''.join(streams)

def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for path in ('direct','hit','miss'):add(f'connected-{path}',path=path)
    add('incoming-df-set',df=True)
    add('close-carry-ignored',close_error=True)
    add('close-provider-df',close_df=True)
    add('attribute-retry',attribute_errors=1)
    add('attribute-fatal',attribute_errors=1,retry_enabled=0)
    add('first-header-fatal',read_error=0)
    add('first-payload-fatal',read_error=1)
    add('second-header-fatal',read_error=2)
    add('second-payload-fatal',read_error=3)
    add('open-carry-ignored',open_errors=1)
    add('stack-word-crosses-ffff',sp=65535)
    add('saved-outer-ds-provider-alias',saved_ds_alias=True)
    add('resource-heap-alias',heap_alias=True)
    for number in range(4):
        asset=f'assets/vgaspec{number}.dat';source=(ROOT/asset).read_bytes();start,end=section_spans(source)[0]
        image,_=decode_section(source[start:end])
        graphics=f'assets/vgagr{number}.dat';packet=(ROOT/graphics).read_bytes();spans=section_spans(packet)
        add(f'vgaspec-{number}-with-vgagr-{number}',special=image,data=packet[:spans[1][1]],graphics_number=number,assets=(asset,graphics))
    return out

def prepare(case):
    rng=random.Random(0x1a7b+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(decoder.IMAGE)]=decoder.relocated(decoder.IMAGE,decoder.ORACLE['relocations'],load)
    data=load+0x9a9;source_segment=0x5000 if case.get('heap_alias') else 0x4000
    mem[source_segment<<4:(source_segment<<4)+65536]=b'\x80'*65536
    prefix,streams=constructed_special(case.get('df',False));special=case.get('special',prefix+streams)
    mem[oracle.at(source_segment,0x10):oracle.at(source_segment,0x10)+len(special)]=special
    if case.get('df'):mem[oracle.at(source_segment,0x35):oracle.at(source_segment,0x39)]=streams
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRY,ds=data,ss=0x7000,sp=case.get('sp',0x8000))
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    oracle.put16(mem,data,field('GraphicsResourceInputSegment'),source_segment)
    oracle.put16(mem,data,field('LevelGraphicsSegment'),0x5000)
    # Upstream1A24 supplies this live filename selector; this caller uses it.
    mem[oracle.at(data,field('GraphicsDatFilename')+5)]=ord(str(case.get('graphics_number',0)))
    if case.get('saved_ds_alias'):oracle.put16(mem,0x6000,field('LevelGraphicsSegment'),0x5000)
    path=case.get('path','direct');packet=case.get('data',decoder.section([('literal',b'GRAPHICS')])+decoder.section([('literal',b'OBJECTS')]))
    for name,value in dict(DatCacheEnabled=0 if path=='direct' else 255,DatCacheSelected=0,
        DatCacheRecordCount=1 if path=='hit' else 0,DatCriticalErrorFlag=0,DatRetryEnabled=case.get('retry_enabled',255)).items():mem[oracle.at(data,field(name))]=value
    for name,value in dict(DatCacheBaseSegment=0x8000,DatCacheFreeSegment=0x8000,DatCacheFreeOffset=0,DatCacheRemainingParagraphs=0x1000).items():oracle.put16(mem,data,field(name),value)
    if path=='hit':
        mem[0x80000:0x8000b]=b'vgagr0  dat';oracle.put16(mem,0x8000,11,len(packet));mem[0x8000d:0x8000d+len(packet)]=packet
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    return mem,regs,flags,data,case|dict(data=packet)

def providers(case,mem,data):
    file,query,read,retry,trace=loader.providers(case,mem,data);first=True
    def wrapped_file(function,seg,offset,flags):
        expected=f'vgagr{case.get("graphics_number",0)}.dat'.encode()+b'\0'
        if bytes(mem[oracle.at(seg,offset):oracle.at(seg,offset)+len(expected)])!=expected:raise AssertionError('Wrong graphics filename')
        return file(function,seg,offset,flags)
    def wrapped_read(*args):
        nonlocal first
        out=read(*args)
        if first and case.get('saved_ds_alias'):oracle.put16(mem,0x7000,0x7ffe,0x6000)
        first=False;return out
    def close(handle,value,flags):
        trace.append(dict(function=0x3e,handle=handle,value=value,flags=flags&0xfc7))
        return (6 if case.get('close_error') else 0x3e9a),(flags&~0x8d5)|0x894|(1 if case.get('close_error') else 0)|(0x400 if case.get('close_df') else 0)
    return wrapped_file,query,wrapped_read,retry,close,trace

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'special_setup-m{mutation}.dll',mutation,'special_setup')))
    lib.lmn_setup_special_graphics_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(SetupServices)]
    lib.lmn_setup_special_graphics_adapter.restype=None;return lib

def compare(lib,case):
    mem,regs,flags,data,case=prepare(case);c_mem=bytearray(mem);r=Regs(**regs,flags=flags)
    uv=blit.Vga(case['seed']+0x1a7b,case['seed']%4);cv=blit.Vga(case['seed']+0x1a7b,case['seed']%4);errors=[]
    expected_planes=None;special=case.get('special',b''.join(constructed_special(case.get('df',False))))
    if not case.get('df'):
        expected_planes=[bytearray(p) for p in uv.planes];cursor=40
        for strip in range(4):
            first=cursor
            while True:
                control=special[cursor];cursor+=1
                if control==128:break
                cursor+=1 if control>128 else control+1
            decoded=blit.unpack_rle(special[first:cursor])
            for row in range(40):
                for column in range(120):
                    at=row*120+column;target=0x4a68+strip*8320+row*208+column
                    colors=[decoded[at+n*4800] for n in range(3)]
                    for n,value in enumerate(colors+[colors[0]|colors[1]|colors[2]]):expected_planes[n][target]=value
    cf,cq,cr,ct,cc,ctrace=providers(case,c_mem,data)
    def guarded(fn,out,*args):
        try:
            values=fn(*args)
            for (name,_),value in zip(out.contents._fields_,values):setattr(out.contents,name,value)
        except Exception as e:errors.append(e)
    @FILE
    def opened(ctx,memory,seg,offset,inflags,out):guarded(cf,out,0x3d,seg,offset,inflags)
    @FILE
    def attributes(ctx,memory,seg,offset,inflags,out):guarded(cf,out,0x43,seg,offset,inflags)
    @QUERY
    def query(ctx,memory,seg,offset,inflags,out):guarded(cq,out,seg,offset,inflags)
    @READ
    def read(ctx,memory,handle,seg,offset,count,inflags,out):guarded(cr,out,handle,seg,offset,count,inflags)
    @RETRY_FN
    def retry(ctx,memory,call,out):guarded(ct,out,{reg:getattr(call.contents,name) for name,reg in MAPPING.items()})
    @CLOSE
    def close(ctx,memory,handle,value,inflags,out):guarded(cc,out,handle,value,inflags)
    @blit.READ
    def video_read(ctx,memory,p,inflags):
        try:return cv.read(c_mem,p,inflags)
        except Exception as e:errors.append(e);return 0
    @blit.WRITE
    def video_write(ctx,memory,p,value,inflags):
        try:cv.write(c_mem,p,value,inflags)
        except Exception as e:errors.append(e)
    @blit.OUT
    def video_out(ctx,port,value,inflags):
        try:
            if value==0x0f02 and port==0x3c4:cv.outputs=0
            cv.out(port,value,inflags)
        except Exception as e:errors.append(e)
    files=Services(None,opened,attributes,retry);io=Io(None,query,read);bus=blit.Bus(None,video_read,video_write,video_out)
    services=SetupServices(ctypes.pointer(files),ctypes.pointer(io),ctypes.pointer(bus),None,close)
    lib.lmn_setup_special_graphics_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r),ctypes.byref(services))
    if errors:raise errors[0]
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();previous=None;done=False
    uf,uq,ur,ut,uc_close,trace=providers(case,mem,data)
    def interrupt(uc,num,_):
        if num!=0x21:raise AssertionError('Unexpected interrupt')
        mem[:]=uc.mem_read(0,1<<20);value=uc.reg_read(oracle.REG['ax']);function=value>>8
        seg=uc.reg_read(oracle.REG['ds']);offset=uc.reg_read(oracle.REG['dx']);inflags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        if function in (0x3d,0x43):out,count,outflags=uf(function,seg,offset,inflags)
        elif function==0x23:out,outflags=uq(seg,offset,inflags)
        elif function==0x3f:out,outflags=ur(uc.reg_read(oracle.REG['bx']),seg,offset,uc.reg_read(oracle.REG['cx']),inflags)
        elif function==0x3e:out,outflags=uc_close(uc.reg_read(oracle.REG['bx']),value,inflags)
        else:raise AssertionError(f'Unexpected service {function:x}')
        uc.mem_write(0,bytes(mem));uc.reg_write(oracle.REG['ax'],out)
        if function==0x43:uc.reg_write(oracle.REG['cx'],count)
        uc.reg_write(x.UC_X86_REG_EFLAGS,outflags)
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off in (0xff00,*loader.FATALS):done=True;uc.emu_stop();return
        if off==loader.RETRY:
            mem[:]=uc.mem_read(0,1<<20);view={n:uc.reg_read(reg) for n,reg in oracle.REG.items() if n not in ('cs','ip')};view['flags']=uc.reg_read(x.UC_X86_REG_EFLAGS)&65535
            value,bx,bp,outflags=ut(view);uc.mem_write(0,bytes(mem))
            for n,v in dict(ax=value,bx=bx,bp=bp,si=0x2222,di=0x3333,ds=0x4444,es=0x5555,cx=0x6666,dx=0x7777).items():uc.reg_write(oracle.REG[n],v)
            sp=uc.reg_read(oracle.REG['sp']);uc.reg_write(oracle.REG['ip'],oracle.get16(mem,regs['ss'],sp));uc.reg_write(oracle.REG['sp'],(sp+2)&65535);uc.reg_write(x.UC_X86_REG_EFLAGS,outflags);previous=None;return
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in INS:raise AssertionError(f'Setup escaped at {off:x}')
        seen.add(off);previous=off
    def output(uc,port,size,value,_):
        if size!=2:raise AssertionError('Wrong VGA output width')
        # Each strip starts the same setup sequence, with XOR-defined AF exclusions.
        if value==0x0f02 and port==0x3c4:uv.outputs=0
        uv.out(port,value,uc.reg_read(x.UC_X86_REG_EFLAGS))
    def memory_read(uc,access,p,size,value,_):
        for i in range(size):uc.mem_write(p+i,bytes([uv.read(mem,p+i,uc.reg_read(x.UC_X86_REG_EFLAGS))]))
    def memory_write(uc,access,p,size,value,_):
        for i in range(size):uv.write(mem,p+i,(value>>(8*i))&255,uc.reg_read(x.UC_X86_REG_EFLAGS))
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,interrupt);u.hook_add(UC_HOOK_INSN,output,None,1,0,x.UC_X86_INS_OUT)
    u.hook_add(UC_HOOK_MEM_READ,memory_read,None,0xa0000,0xaffff);u.hook_add(UC_HOOK_MEM_WRITE,memory_write,None,0xa0000,0xaffff)
    u.emu_start(oracle.at(regs['cs'],regs['ip']),0,count=10000000)
    if not done:raise AssertionError('Setup exceeded budget')
    for n,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(r,n):raise AssertionError(f'{case["name"]}: {n} C={getattr(r,n):04x}/original={u.reg_read(reg):04x}')
    if (r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&0xfd7:raise AssertionError(f'{case["name"]}: exit flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: memory differs at {p:05x}')
    if cv.state()!=uv.state():raise AssertionError(f'{case["name"]}: VGA device state differs')
    if expected_planes is not None:
        if uv.planes!=expected_planes:raise AssertionError(f'{case["name"]}: independent full-strip plane result differs')
        expected=((field('SpecialMetadata24'),b'\x1f\x1f\0'+special[3:24]),
            (field('SpecialMetadataDuplicateBase')+24,special[:24]),(field('SpecialMetadata8Base')+8,special[24:32]),
            (field('SpecialMetadataRemap8'),b'\6'+special[33:40]))
        for off,values in expected:
            if actual[oracle.at(data,off):oracle.at(data,off)+len(values)]!=values:raise AssertionError(f'{case["name"]}: independent metadata result differs')
    if cv.trace!=uv.trace:raise AssertionError(f'{case["name"]}: VGA trace differs')
    if ctrace!=trace:raise AssertionError(f'{case["name"]}: service trace differs {ctrace}/{trace}')
    return seen,edges

def main():
    report=BUILD/'special-setup-differential.json';report.unlink(missing_ok=True);baseline=cases();lib=library();seen=set();edges=set()
    for case in baseline:
        a,b=compare(lib,case);seen|=a;edges|=b
    if not set(LOCAL)<=seen:raise AssertionError(f'Missing setup sites {set(LOCAL)-seen}')
    mutations=[]
    for mutation in (1,2,3):
        lib=library(mutation);hit=None
        for case in baseline:
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if not hit:raise AssertionError(f'Setup mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=tuple('c/'+n for n in ('special_setup.c','special_setup.h','special_blit.c','special_blit.h','resource_rle.c','resource_rle.h',
        'dat_load.c','dat_load.h','dat_files.c','dat_files.h','dat_cache.c','dat_cache.h','dat_section.c','dat_section.h','dat_io.c','dat_io.h','dat.c','dat.h','regs.h','lemmings_sym.h'))
    paths+=('tests/special_setup.py','tests/special_blit.py','tests/resource_rle.py','tests/dat_load.py','tests/dat_files.py','tests/dat_section.py',
        'tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','metadata/symbols.json','tools/resources.py')
    paths+=tuple(sorted({a for c in baseline for a in c.get('assets',())}))
    public=[{k:v for k,v in c.items() if k not in ('special','data')}|({'special_sha256':sha(c['special']),'dat_sha256':sha(c['data'])} if 'special' in c else {}) for c in baseline]
    write_json(report,dict(image='main',image_sha256=sha(decoder.IMAGE),case_count=len(baseline),mutation_count=3,mutations_detected=mutations,cases=public,
        executed_instruction_addresses=sorted(seen),caller_instruction_addresses=sorted(LOCAL),branch_edges=sorted(edges),
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},domain='Connected metadata/RLE/strip/DAT cores; declared DOS,4B1C and quiescent VGA seams; intact instructions/active returns'))
    print(f'PASS special graphics setup C: {len(baseline)} cases, {len(LOCAL)} caller sites, {len(seen)} integrated sites; 3 compiled mutations detected')
if __name__=='__main__':main()

"""Complete original DAT section path versus native C-to-C decoding."""
import ctypes
import random
import capstone
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x
from dat_io_c import Regs,Io,QUERY,READ,MEM
import dat_io as io_oracle
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import ASSET,unpack,relocated
from resources import sound_images
from cbuild import build

IMAGE,ORACLE=unpack(ASSET.read_bytes())
SYMBOLS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ENTRY=SYMBOLS['DecodeDatSection']['address'];FATAL=SYMBOLS['DatFatalTransfer']['address']
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
LOCAL_END=SYMBOLS['sub_1CB9']['address']
LOCAL={i.address:i for i in MD.disasm(IMAGE[ENTRY:LOCAL_END],ENTRY) if i.mnemonic!='nop'}
INS={**LOCAL,**io_oracle.INS}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}
REG=io_oracle.REG

def section(tokens,**changes):
    bits=[];size=0
    def emit(value,width):bits.extend((value>>i)&1 for i in range(width-1,-1,-1))
    for kind,data in tokens:
        if kind=='literal':
            count=len(data);size+=count
            if count<=8:emit(0,2);emit(count-1,3)
            else:emit(1,1);emit(3,2);emit(count-9,8)
            for byte in data:emit(byte,8)
        else:
            count,distance=data;size+=count
            if count==2:emit(1,2);emit(distance-1,8)
            elif count in (3,4):emit(1,1);emit(count-3,2);emit(distance-1,count+6)
            else:emit(1,1);emit(2,2);emit(count-1,8);emit(distance-1,12)
    valid=len(bits)%8 or 8;chunks=[];cursor=0;take=valid
    while cursor<len(bits):
        chunks.append(sum(bit<<i for i,bit in enumerate(bits[cursor:cursor+take])));cursor+=take;take=8
    payload=bytes(reversed(chunks));checksum=0
    for byte in payload:checksum^=byte
    header=bytes([valid,checksum])+size.to_bytes(4,'big')+(len(payload)+10).to_bytes(4,'big')
    data=bytearray(header+payload)
    if 'size' in changes:data[2:6]=changes['size'].to_bytes(4,'big')
    if 'packed_high' in changes:data[6:8]=changes['packed_high'].to_bytes(2,'big')
    if 'valid' in changes:data[0]=changes['valid']
    if changes.get('bad_checksum'):data[1]^=0xa5
    return bytes(data)

def cases():
    out=[]
    def add(name,data,**kw):out.append(dict(name=name,data=data,seed=len(out),**kw))
    for name,(_,meta) in sound_images().items():
        source=(ROOT/meta['source']).read_bytes();start=meta.get('section_offset',0)
        packet=source[start:start+meta['packed_size']]
        for path in ('direct','hit','miss'):add(f'{name}-{path}',packet,path=path,in_place=True)
    for count in (1,2,8,9,264):add(f'literals-{count}',section([('literal',bytes((n*37)&255 for n in range(count)))]))
    for count in (1,2,3,4,5,256):
        for distance in (1,256):add(f'match-{count}-{distance}',section([('match',(count,distance))]))
    add('mixed',section([('literal',b'ABCDEFGH'),('match',(3,1)),('match',(4,2)),('match',(2,3)),
        ('match',(12,1)),('literal',b'012345678'),('literal',b'X')]))
    packet=section([('literal',b'Q')])
    add('checksum-failure',section([('literal',b'Q')],bad_checksum=True))
    add('high-output-word-discarded',section([('literal',b'Q')],size=0xabcd0001))
    add('high-packed-word-discarded',section([('literal',b'Q')],packed_high=0xabcd))
    add('zero-size-still-decodes',section([('literal',b'Q')],size=0),output=65535)
    add('unsigned-output-wrap',section([('literal',b'Q')],size=32),output=0xfff0)
    add('token-crosses-output-start',section([('literal',b'XY')],size=1),output=0x100)
    add('invalid-bit-count-255',section([('literal',b'\0')],valid=255))
    zero=bytearray(section([('literal',b'\0')]));zero[0]=0;zero[6:10]=(13).to_bytes(4,'big');zero+=b'\0'
    add('invalid-bit-count-zero',bytes(zero))
    add('short-header-accepted',packet,short_header=3)
    add('short-payload-accepted',section([('literal',b'\0')]),short_payload=1)
    add('header-read-error',packet,error_read=0)
    add('payload-read-error',packet,error_read=1)
    add('cache-provider-df',packet,path='miss',provider_df=True)
    for sp in (0,1,65535):add(f'stack-{sp}',packet,sp=sp)
    for source in (0xfff8,65535):add(f'source-{source}',packet,source=source)
    add('distinct-cache-es',packet,path='hit')
    add('cache-budget-fallback',packet,path='miss',budget=0)
    add('cache-aligned-file',section([('literal',b'ABCDE')]),path='miss')
    return out

def prepare(case):
    rng=random.Random(0x1baf+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    data_seg=load+0x9a9;source=case.get('source',0)
    regs={n:rng.randrange(65536) for n in io_oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRY,ds=0x3000,es=0x3000 if case.get('in_place') else 0x4000,
                si=source,di=case.get('output',0),ss=0x7000,sp=case.get('sp',0x8000),bx=7)
    flags=2|((case['seed']*0x95)&0xed5)
    io_oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    # A short header fixture retains pre-existing trailing header bytes.
    for n,value in enumerate(case['data'][:10]):mem[io_oracle.at(regs['ds'],source+n)]=value
    path=case.get('path','direct');fields=io_oracle.FIELDS
    mem[io_oracle.at(data_seg,fields['Enabled'])]=0 if path=='direct' else 255
    mem[io_oracle.at(data_seg,fields['Selected'])]=255 if path=='hit' else 0
    for name,value in dict(ReadOffset=0x100,ReadSegment=0x5000,FreeOffset=0,FreeSegment=0x5000,
                          RemainingParagraphs=case.get('budget',0x1000)).items():io_oracle.store(mem,data_seg,name,value)
    mem[io_oracle.at(data_seg,fields['RecordCount'])]=0
    mem[io_oracle.at(data_seg,fields['Fcb']+1):io_oracle.at(data_seg,fields['Fcb']+1)+11]=b'TESTFILEDAT'
    if path=='hit':mem[0x50100:0x50100+len(case['data'])]=case['data']
    return mem,regs,flags,data_seg

def provider(case,mem,data_seg):
    position=0;reads=0;trace=[]
    def service(function,segment,offset,count,handle,flags):
        nonlocal position,reads
        if function==0x23:
            if (segment,offset)!=(data_seg,io_oracle.FIELDS['Fcb']):raise AssertionError('Wrong FCB')
            io_oracle.put16(mem,segment,offset+33,len(case['data']));io_oracle.put16(mem,segment,offset+35,0)
            value=0x2300;failed=False
        else:
            if handle!=7:raise AssertionError('Wrong handle')
            failed=reads==case.get('error_read',-1)
            short=case.get('short_header' if reads==0 else 'short_payload',count)
            part=case['data'][position:position+min(count,short)]
            value=5 if failed else len(part)
            if not failed:
                for n,byte in enumerate(part):mem[io_oracle.at(segment,offset+n)]=byte
                position+=len(part)
            reads+=1
        trace.append(dict(function=function,segment=segment,offset=offset,count=count,handle=handle,
                          value=value,error=failed,flags=flags&0xfd7))
        return value,(flags&~0x8d5)|0x894|(1 if failed else 0)|(0x400 if case.get('provider_df') else 0)
    return service,trace

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'dat_section-m{mutation}.dll',mutation,'dat_section')))
    lib.lmn_dat_section_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Io)]
    lib.lmn_dat_section_adapter.restype=None;return lib

def compare(lib,case):
    mem,regs,flags,data_seg=prepare(case);c_mem=bytearray(mem);c_r=Regs(**regs,flags=flags)
    c_service,c_trace=provider(case,c_mem,data_seg);errors=[]
    def invoke(function,segment,offset,count,handle,inflags,out):
        try:out.contents.value,out.contents.flags=c_service(function,segment,offset,count,handle,inflags)
        except Exception as e:errors.append(e)
    @QUERY
    def query(context,memory,segment,offset,inflags,out):invoke(0x23,segment,offset,0,0,inflags,out)
    @READ
    def read(context,memory,handle,segment,offset,count,inflags,out):invoke(0x3f,segment,offset,count,handle,inflags,out)
    io=Io(None,query,read)
    lib.lmn_dat_section_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(c_r),ctypes.byref(io))
    if errors:raise errors[0]
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for name,reg in REG.items():u.reg_write(reg,regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);sites=set();edges=set();previous=None;done=False
    u_service,u_trace=provider(case,mem,data_seg)
    def interrupt(uc,num,_):
        if num!=0x21:raise AssertionError('Unexpected interrupt')
        mem[:]=uc.mem_read(0,1<<20)
        value,outflags=u_service(uc.reg_read(REG['ax'])>>8,uc.reg_read(REG['ds']),uc.reg_read(REG['dx']),
            uc.reg_read(REG['cx']) if uc.reg_read(REG['ax'])>>8==0x3f else 0,
            uc.reg_read(REG['bx']) if uc.reg_read(REG['ax'])>>8==0x3f else 0,uc.reg_read(x.UC_X86_REG_EFLAGS))
        uc.mem_write(0,bytes(mem));uc.reg_write(REG['ax'],value);uc.reg_write(x.UC_X86_REG_EFLAGS,outflags)
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off in (0xff00,FATAL):done=True;uc.emu_stop();return
        if uc.reg_read(REG['cs'])!=regs['cs'] or off not in INS:raise AssertionError(f'Escaped decoder at {off:x}')
        sites.add(off);previous=off
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,interrupt)
    u.emu_start(io_oracle.at(regs['cs'],ENTRY),0,count=5_000_000)
    if not done:raise AssertionError('Decoder exceeded budget')
    for name,reg in REG.items():
        if u.reg_read(reg)!=getattr(c_r,name):raise AssertionError(f'{case["name"]}: {name} C={getattr(c_r,name):04x}/original={u.reg_read(reg):04x}')
    mask=0xfd7 if u.reg_read(REG['ip'])==FATAL else 0xfc7
    if (u.reg_read(x.UC_X86_REG_EFLAGS)^c_r.flags)&mask:raise AssertionError(f'{case["name"]}: defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b)
        raise AssertionError(f'{case["name"]}: memory differs at {p:05x}: original={actual[p]:02x}/C={c_mem[p]:02x}')
    if u_trace!=c_trace:raise AssertionError(f'{case["name"]}: service trace differs {u_trace}/{c_trace}')
    return sites,edges

def main():
    report=BUILD/'dat-section-differential.json';report.unlink(missing_ok=True)
    lib=library();baseline=cases();sites=set();edges=set()
    for case in baseline:
        seen,branches=compare(lib,case);sites|=seen;edges|=branches
    if sites!=set(INS):raise AssertionError(f'Missing instructions {set(INS)-sites}')
    # Cache-budget fallback branches are independently covered by dat_io_c.py.
    local_edges={e for e in EDGES if e[0] in LOCAL}
    if not local_edges<=edges:raise AssertionError(f'Missing decoder branches {local_edges-edges}')
    mutations=[]
    for mutation in (1,2,3):
        lib=library(mutation);hit=None
        for case in baseline:
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if hit is None:raise AssertionError(f'Section mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=('c/dat_section.c','c/dat_section.h','c/dat.c','c/dat.h','c/dat_io.c','c/dat_io.h','c/regs.h',
           'c/lemmings_sym.h','tests/dat_section.py','tests/dat_io.py','tests/dat_io_c.py',
           'tools/cbuild.py','tools/difftest.py','metadata/symbols.json','metadata/inputs.json')
    paths += ('assets/vgalemmi.exe','assets/adlib.dat','assets/tandysnd.dat','assets/main.dat')
    public_cases=[{k:v for k,v in c.items() if k!='data'}|dict(input_sha256=sha(c['data'])) for c in baseline]
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=3,
        mutations_detected=mutations,cases=public_cases,executed_instruction_addresses=sorted(sites),
        branch_edges=sorted(edges),decoder_branch_edges=sorted(local_edges),
        translated_code_bytes=sum(i.size for i in LOCAL.values()),
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Original decoder/read helpers only; constructed preserving DOS services; intact code/near return words; full memory; fatal transfer is an explicit exit',
        flags_note='AF excluded only after final AND DH,DH; fatal read exits compare all defined arithmetic flags'))
    print(f'PASS DAT section C: {len(baseline)} cases, {len(sites)} original sites, {len(local_edges)} decoder edges; 3 compiled mutations detected')

if __name__=='__main__':main()

"""Original complete DAT read wrapper against constructed DOS/cache contracts."""
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import capstone
from common import ROOT,BUILD,read_json,write_json,sha
from unpack import ASSET,unpack,relocated
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x

IMAGE,ORACLE=unpack(ASSET.read_bytes())
LEDGER={r['symbol_name']:r for r in read_json(ROOT/'metadata/symbols.json')}
ENTRY=LEDGER['ReadDatBytes']['address'];END=ENTRY+LEDGER['ReadDatBytes']['size']
FIELDS={n:LEDGER['DatCache'+n]['address'] for n in
    ('RecordOffset','RecordSegment','ReadOffset','ReadSegment','FreeOffset','FreeSegment',
     'RemainingParagraphs','RecordCount','Enabled','Selected','Fcb')}
REG_NAMES=('ax','bx','cx','dx','si','di','bp','sp','cs','ds','es','ss','ip')
REG={n:getattr(x,'UC_X86_REG_'+n.upper()) for n in REG_NAMES}
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for i in MD.disasm(IMAGE[ENTRY:END],ENTRY) if i.mnemonic!='nop'}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP)}
EDGES={(pc,i.operands[0].imm&0xffff) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}

def at(seg,off):return ((seg<<4)+(off&65535))&0xfffff
def get16(mem,seg,off):
    p=at(seg,off);return mem[p]|(mem[(p+1)&0xfffff]<<8)
def put16(mem,seg,off,value):
    p=at(seg,off);mem[p]=value&255;mem[(p+1)&0xfffff]=(value>>8)&255
def field(mem,ds,name):return get16(mem,ds,FIELDS[name])
def store(mem,ds,name,value):put16(mem,ds,FIELDS[name],value)
def byte(mem,ds,name):return mem[at(ds,FIELDS[name])]
def szp(value):return (0x40 if value==0 else 0)|(0x80 if value&0x8000 else 0)|(4 if (value&255).bit_count()%2==0 else 0)
def arithmetic(flags,a,b,width=16,add=False):
    mask=(1<<width)-1;sign=1<<(width-1);value=(a+b if add else a-b)&mask
    parity=4 if (value&255).bit_count()%2==0 else 0
    common=(0x40 if not value else 0)|(0x80 if value&sign else 0)|parity|((a^b^value)&16)
    carry=(a+b>mask) if add else a<b
    overflow=(~(a^b)&(a^value)&sign) if add else ((a^b)&(a^value)&sign)
    return (flags&~0x8d5)|common|(1 if carry else 0)|(0x800 if overflow else 0)
def copy_live(mem,source_seg,source,dest_seg,dest,count,flags=0):
    step=-1 if flags&0x400 else 1
    for _ in range(count):
        mem[at(dest_seg,dest)]=mem[at(source_seg,source)]
        source=(source+step)&65535;dest=(dest+step)&65535
    return source,dest

def prepare(case):
    rng=random.Random(0x1d2e+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    ds=load+0x9a9
    r={n:rng.randrange(65536) for n in REG_NAMES}
    r.update(cs=load,ip=ENTRY,ss=0x7000,sp=case.get('sp',0x8000),ds=0x3000,es=0x6000,
             dx=case.get('dest',0x100),cx=case.get('count',10),bx=7)
    if case.get('stack_alias'):r.update(ds=r['ss'],dx=r['sp']-12,cx=12 if case['path']=='direct' else 8)
    flags=2|((case['seed']*0x95)&0xed5)|0x400
    for name,value in dict(RecordOffset=0,RecordSegment=0x5000,ReadOffset=case.get('source',0x200),
        ReadSegment=case.get('source_seg',0x5000),FreeOffset=case.get('free',0),FreeSegment=0x5000,
        RemainingParagraphs=case.get('budget',0x200),RecordCount=case.get('records',5)).items():
        if name=='RecordCount':mem[at(ds,FIELDS[name])]=value
        else:store(mem,ds,name,value)
    mem[at(ds,FIELDS['Enabled'])]=0 if case['path']=='direct' else 255
    mem[at(ds,FIELDS['Selected'])]=255 if case['path']=='hit' else 0
    fcb=FIELDS['Fcb']
    mem[at(ds,fcb+1):at(ds,fcb+1)+11]=b'TESTFILEDAT'
    # Filesize bytes are set by the declared AH=23 service, not fixture pre-state.
    put16(mem,r['ss'],r['sp'],0xff00)
    return mem,r,flags,ds

def services(case,mem,r,flags,trace,data_seg):
    function=r['ax']>>8
    if function==0x23:
        if (r['ds'],r['dx'])!=(data_seg,FIELDS['Fcb']):raise AssertionError('Wrong FCB request')
        if get16(mem,data_seg,FIELDS['Fcb']+14)!=1:raise AssertionError('Wrong FCB record size')
        size=case.get('size',0x21)
        put16(mem,data_seg,FIELDS['Fcb']+33,size)
        put16(mem,data_seg,FIELDS['Fcb']+35,size>>16)
        trace.append(dict(function=0x23,segment=r['ds'],offset=r['dx'],size=size,flags=flags&0xfd7))
        r['ax']=(r['ax']&0xff00)|case.get('fcb_status',0)
    elif function==0x3f:
        if r['bx']!=7:raise AssertionError('Wrong file handle')
        count=r['cx'];returned=min(count,case.get('returned',count))
        trace.append(dict(function=0x3f,segment=r['ds'],offset=r['dx'],count=count,
                          returned=returned,error=case.get('error',False),flags=flags&0xfd7))
        if case.get('error'):r['ax']=case.get('error_code',5)
        else:
            for i in range(returned):mem[at(r['ds'],r['dx']+i)]=(i*29+0x51)&255
            r['ax']=returned
    else:raise AssertionError(f'Unexpected DOS function {function:02x}')
    return (flags&~0x8d5)|case.get('service_arith',0x894)|(1 if case.get('error') and function==0x3f else 0)|(0x400 if case.get('provider_df') else 0)

def expected(case,mem,r,flags,data_seg):
    """Functional cache model with explicit observable save-frame writes."""
    mem=bytearray(mem);r=dict(r);trace=[]
    def push(value):r['sp']=(r['sp']-2)&65535;put16(mem,r['ss'],r['sp'],value)
    def pop():
        value=get16(mem,r['ss'],r['sp']);r['sp']=(r['sp']+2)&65535;return value
    for n in ('di','si','ds','bx','cx','dx'):push(r[n])
    flags&=~0x400;r['ds']=data_seg;r['ax']=0x9a9
    enabled=byte(mem,data_seg,'Enabled')==255;selected=byte(mem,data_seg,'Selected')==255
    flags=arithmetic(flags,byte(mem,data_seg,'Enabled'),255,8)
    if enabled:flags=arithmetic(flags,byte(mem,data_seg,'Selected'),255,8)
    cached=enabled and selected
    if enabled and not selected:
        r['ax']=0x23a9;r['dx']=FIELDS['Fcb']
        put16(mem,data_seg,FIELDS['Fcb']+14,1)
        flags=services(case,mem,r,flags,trace,data_seg)
        size=get16(mem,data_seg,FIELDS['Fcb']+33)|(get16(mem,data_seg,FIELDS['Fcb']+35)<<16)
        push(size&65535);r['ax']=pop()&15
        paragraphs=((size>>4)+(1 if size&15 else 0))&65535
        flags=arithmetic(flags,paragraphs,field(mem,data_seg,'RemainingParagraphs'))
        if paragraphs<=field(mem,data_seg,'RemainingParagraphs'):
            cached=True
            mem[at(data_seg,FIELDS['RecordCount'])]=(byte(mem,data_seg,'RecordCount')+1)&255
            store(mem,data_seg,'RemainingParagraphs',field(mem,data_seg,'RemainingParagraphs')-paragraphs)
            push(data_seg);r['cx']=65535
            r['dx']=field(mem,data_seg,'FreeOffset');r['ax']=field(mem,data_seg,'FreeSegment')
            store(mem,data_seg,'RecordOffset',r['dx']);store(mem,data_seg,'RecordSegment',r['ax'])
            mem[at(data_seg,FIELDS['Selected'])]=255
            flags=arithmetic(flags,r['dx'],13,add=True);r['dx']=(r['dx']+13)&65535
            store(mem,data_seg,'ReadOffset',r['dx']);store(mem,data_seg,'ReadSegment',r['ax'])
            push(r['ax']);push(r['dx']);r['ds']=r['ax'];r['ax']=(r['ax']&255)|0x3f00
            flags=services(case,mem,r,flags,trace,data_seg);r['cx']=r['ax']
            r['dx']=pop();r['ax']=pop();r['ds']=pop()
            total=(r['dx']+r['cx'])&65535;push(total)
            r['ax']=(r['ax']+(total>>4))&65535;r['dx']=pop()&15
            store(mem,r['ds'],'FreeOffset',r['dx']);store(mem,r['ds'],'FreeSegment',r['ax'])
            r['di']=field(mem,r['ds'],'RecordOffset');r['es']=field(mem,r['ds'],'RecordSegment')
            r['dx']=get16(mem,r['ds'],FIELDS['Fcb']+35)
            put16(mem,r['es'],r['di']+11,r['cx'])
            flags=(flags&~0x8d5)|szp(r['di'])
            r['si'],r['di']=copy_live(mem,r['ds'],FIELDS['Fcb']+1,r['es'],r['di'],11,flags);r['cx']=0
    elif cached:
        flags=(flags&~0x8d5)|0x44 # CMP selected,FF equal
    if cached:
        for n in ('di','cx','bx','es'):r[n]=pop()
        push(r['es']);push(r['di']);push(r['ds'])
        r['si']=field(mem,r['ds'],'ReadOffset');r['ds']=field(mem,r['ds'],'ReadSegment')
        r['si'],r['di']=copy_live(mem,r['ds'],r['si'],r['es'],r['di'],r['cx'],flags);r['cx']=0
        r['ax']=r['ds'];r['ds']=pop()
        store(mem,r['ds'],'ReadSegment',r['ax']);store(mem,r['ds'],'ReadOffset',r['si'])
        for n in ('dx','ds','si','di'):r[n]=pop()
    else:
        for n in ('dx','cx','bx','ds'):r[n]=pop()
        r['ax']=(r['ax']&255)|0x3f00
        flags=services(case,mem,r,flags,trace,data_seg)
        for n in ('si','di'):r[n]=pop()
    r['ip']=pop()
    return mem,r,flags,trace

def run(case,native=None):
    mem,r,flags,data_seg=prepare(case)
    want,regs,wantflags,trace=(native if native else expected)(case,mem,r,flags,data_seg)
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,v in r.items():u.reg_write(REG[n],v)
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();last=None;done=False;actualtrace=[]
    def code(uc,pc,size,_):
        nonlocal last,done
        off=pc-(r['cs']<<4)
        if last in BRANCHES:edges.add((last,off))
        if pc==at(r['cs'],0xff00):done=True;uc.emu_stop();return
        if uc.reg_read(REG['cs'])!=r['cs'] or off not in INS:raise AssertionError(f'Escaped read wrapper at {off:x}')
        seen.add(off);last=off
    def intr(uc,num,_):
        if num!=0x21:raise AssertionError('Unexpected interrupt')
        state={n:uc.reg_read(reg) for n,reg in REG.items()};ram=bytearray(uc.mem_read(0,1<<20))
        outflags=services(case,ram,state,uc.reg_read(x.UC_X86_REG_EFLAGS),actualtrace,data_seg)
        uc.mem_write(0,bytes(ram));uc.reg_write(REG['ax'],state['ax']);uc.reg_write(x.UC_X86_REG_EFLAGS,outflags)
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,intr)
    u.emu_start(at(r['cs'],ENTRY),0,count=300000)
    if not done:raise AssertionError('Read wrapper exceeded budget')
    for n,reg in REG.items():
        if u.reg_read(reg)!=regs[n]:raise AssertionError(f'{case["name"]}: {n} {u.reg_read(reg):04x}/{regs[n]:04x}')
    if (u.reg_read(x.UC_X86_REG_EFLAGS)^wantflags)&0xfd7:raise AssertionError(f'{case["name"]}: flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=want:
        p=next(i for i,(a,b) in enumerate(zip(actual,want)) if a!=b)
        raise AssertionError(f'{case["name"]}: memory differs at {p:05x}: {actual[p]:02x}/{want[p]:02x}')
    if actualtrace!=trace:raise AssertionError(f'{case["name"]}: service trace differs')
    return seen,edges,actualtrace

def cases():
    cases=[]
    def add(name,path,**kw):cases.append(dict(name=name,path=path,seed=len(cases),**kw))
    for path in ('direct','hit','miss'):
        for count in (0,1,10,255):add(f'{path}-count-{count}',path,count=count,returned=33)
        for sp in (0,1,65535):add(f'{path}-stack-{sp}',path,sp=sp,returned=33)
    add('direct-short','direct',count=10,returned=3)
    add('direct-error','direct',error=True)
    add('direct-empty','direct',returned=0)
    add('cache-error-ignored','miss',error=True)
    add('cache-short','miss',returned=3)
    add('cache-fcb-failure-ignored','miss',fcb_status=255,returned=33)
    add('cache-over-budget','miss',budget=1,size=33,returned=3)
    add('cache-exact-budget','miss',budget=3,size=33,returned=33)
    add('cache-size-aligned','miss',size=32,returned=32)
    add('cache-zero-size','miss',size=0,returned=0,count=0)
    add('cache-paragraph-wrap','miss',size=0xfffff,returned=3)
    add('cache-high-size','miss',size=0x100021,returned=33)
    add('cache-count-wrap','miss',records=255,returned=33)
    add('cache-pointer-add-wrap','miss',free=0xfff0,returned=33)
    add('cache-header-offset-wrap','miss',free=0xfff8,returned=33)
    add('cache-hit-source-wrap','hit',source=65530,count=16)
    add('cache-hit-dest-wrap','hit',dest=65530,count=16)
    add('cache-hit-live-overlap','hit',source_seg=0x3000,source=0x100,dest=0x101,count=12)
    add('cache-hit-saved-frame-alias','hit',stack_alias=True)
    add('direct-saved-frame-alias','direct',stack_alias=True)
    add('cache-full-fill','miss',returned=65535)
    add('cache-full-copy','hit',count=65535)
    add('cache-provider-sets-df','miss',provider_df=True,returned=33)
    add('direct-provider-sets-df','direct',provider_df=True)
    return cases

def check():
    baseline=cases()
    coverage=set();edges=set();results=[]
    for case in baseline:
        sites,branches,trace=run(case);coverage|=sites;edges|=branches
        results.append(dict(case=case,services=trace))
    if coverage!=set(INS):raise AssertionError(f'Missing instructions {set(INS)-coverage}')
    if edges!=EDGES:raise AssertionError(f'Missing/extra edges {EDGES-edges}/{edges-EDGES}')
    report=dict(case_count=len(baseline),original_instruction_sites=sorted(coverage),branch_edges=sorted(edges),
        cases=results,image_sha256=sha(IMAGE),domain='Constructed DOS AH23/AH3F; original wrapper only; full mapped memory; quiescent interrupts',
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in ('tests/dat_io.py','metadata/symbols.json')})
    write_json(BUILD/'dat-io-tests.json',report)
    print(f'PASS DAT read contracts: {len(baseline)} cases, {len(coverage)} original sites, {len(edges)} branch edges; no C coverage claimed')
    return report

if __name__=='__main__':check()

"""Original DAT filename/cache helpers versus portable C, with original bugs."""
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
SYMBOLS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ROUTINES={k:SYMBOLS[n] for k,n in (('prepare_name','PrepareDatCacheName'),
    ('select_cache','SelectCachedDatFile'),('disable_cache','DisableDatCache'))}
FIELDS={n:SYMBOLS['DatCache'+n]['address'] for n in
    ('BaseSegment','RecordCount','Selected','Enabled','Fcb')}
MD=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_16);MD.detail=True
INS={i.address:i for s in ROUTINES.values() for i in MD.disasm(IMAGE[s['address']:s['address']+s['size']],s['address'])}
BRANCHES={pc for pc,i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in INS.items() if pc in BRANCHES}
EDGES|={(pc,i.address+i.size) for pc,i in INS.items() if pc in BRANCHES and i.mnemonic!='jmp'}

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'dat_cache-m{mutation}.dll',mutation,'dat_cache')))
    for k in ROUTINES:
        fn=getattr(lib,'lmn_dat_'+k+'_adapter');fn.argtypes=[MEM,ctypes.POINTER(Regs)];fn.restype=None
    return lib

def prepare(case):
    rng=random.Random(0x1e1c+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3]
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(IMAGE)]=relocated(IMAGE,ORACLE['relocations'],load)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ROUTINES[case['kind']]['address'],ds=0x5000,ss=0x7000,
                sp=case.get('sp',0x8000),dx=case.get('source',0x100))
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    if case['kind']=='prepare_name':
        if case.get('stack_alias'):regs.update(ss=regs['ds'],sp=0x1fa6)
        step=-1 if case.get('df') else 1
        for n,value in enumerate(case['filename']):mem[oracle.at(regs['ds'],regs['dx']+step*n)]=value
    elif case['kind']=='select_cache':
        regs['ds']=0x3000;cache=case.get('cache_segment',0x5000)
        oracle.put16(mem,regs['ds'],FIELDS['BaseSegment'],cache)
        mem[oracle.at(regs['ds'],FIELDS['RecordCount'])]=case.get('records',1)
        mem[oracle.at(regs['ds'],FIELDS['Selected'])]=0x66
        step=-1 if case.get('df') else 1
        target=case.get('target',b'TESTFILEDAT')
        for n,value in enumerate(target):mem[oracle.at(regs['ds'],FIELDS['Fcb']+1+step*n)]=value
        # DF-set target bytes alias cache flags/count; use the resulting live name.
        mem[oracle.at(regs['ds'],FIELDS['RecordCount'])]=case.get('records',1)
        live=bytes(mem[oracle.at(regs['ds'],FIELDS['Fcb']+1+step*n)] for n in range(11))
        cursor=0;segment=cache
        for index in range(case.get('records',1)):
            name=bytearray(live)
            mismatch=case.get('mismatch')
            if case.get('hit_index',0)!=index or mismatch is not None:
                name[0 if mismatch is None else mismatch]^=0x55
            for n,value in enumerate(name):mem[oracle.at(segment,cursor+step*n)]=value
            length=case.get('length',0x23)
            oracle.put16(mem,segment,cursor+11,length)
            total=(cursor+length+13)&65535;segment=(segment+(total>>4))&65535;cursor=total&15
        if case.get('length_wrap'):
            # Record zero's FFFF length aliases the next record's first FF byte.
            target=b'\xffABCDEFGHIJ'
            for n,value in enumerate(target):mem[oracle.at(regs['ds'],FIELDS['Fcb']+1+n)]=value
            mem[oracle.at(cache,0)]=0
            oracle.put16(mem,cache,11,65535)
            for n,value in enumerate(target):mem[oracle.at(cache,12+n)]=value
        if case.get('saved_ds_alias'):regs.update(ss=load+0x9a9,sp=0x1f8a)
    else:
        regs['ax']=(regs['ax']&0xff00)|case['low_byte']
        mem[oracle.at(regs['ds'],FIELDS['Enabled'])]=255
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    return mem,regs,flags

def compare(lib,case):
    mem,regs,flags=prepare(case);c_mem=bytearray(mem);c_r=Regs(**regs,flags=flags)
    getattr(lib,'lmn_dat_'+case['kind']+'_adapter')((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(c_r))
    u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for name,reg in oracle.REG.items():u.reg_write(reg,regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);sites=set();edges=set();previous=None;done=False;last_flags=''
    routine=ROUTINES[case['kind']];start=routine['address'];end=start+routine['size']
    def code(uc,pc,size,_):
        nonlocal previous,done,last_flags
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off==0xff00:done=True;uc.emu_stop();return
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or not start<=off<end:raise AssertionError(f'Escaped cache helper at {off:x}')
        sites.add(off);previous=off
        mnemonic=INS[off].mnemonic.split()[-1]
        if mnemonic in ('add','sub','and','xor','cmp','cmpsb'):last_flags=mnemonic
    def intr(uc,num,_):raise AssertionError(f'Unexpected interrupt {num}')
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,intr)
    u.emu_start(oracle.at(regs['cs'],start),0,count=600000)
    if not done:raise AssertionError('Cache helper exceeded budget')
    for name,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(c_r,name):raise AssertionError(f'{case["name"]}: {name} C={getattr(c_r,name):04x}/original={u.reg_read(reg):04x}')
    mask=0xfc7 if last_flags in ('and','xor') else 0xfd7
    if (c_r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&mask:raise AssertionError(f'{case["name"]}: defined flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b)
        raise AssertionError(f'{case["name"]}: memory differs at {p:05x}: original={actual[p]:02x}/C={c_mem[p]:02x}')
    return sites,edges

def cases():
    result=[]
    def add(name,kind,**kw):result.append(dict(name=name,kind=kind,seed=len(result),**kw))
    names=(b'A.XYZ',b'ABC.XYZ',b'ABCDEFGH.XYZ',b'LONGFILENAME.XYZ',b'.XYZ',
           b'ABCDEFGH.\0',b'ABCDEFGH.X\0',b'ABCDEFGH.XY\0',b'ABCDEFGH.XYZQ')
    for n,name in enumerate(names):
        for df in (False,True):add(f'name-{n}-df-{df}','prepare_name',filename=name,df=df)
    for source in (0,1,65535,0xfff8):add(f'name-wrap-{source}','prepare_name',filename=b'ABCDEFGH.XYZ',source=source)
    for sp in (0,1,65535):add(f'name-stack-{sp}','prepare_name',filename=b'ABCDEFGH.XYZ',sp=sp)
    add('name-saved-register-alias','prepare_name',filename=b'ABCDEFGH.XYZ',stack_alias=True)
    add('cache-empty','select_cache',records=0)
    for n in range(11):add(f'cache-mismatch-{n}','select_cache',mismatch=n)
    add('cache-first-hit','select_cache')
    add('cache-second-hit','select_cache',records=2,hit_index=1)
    add('cache-all-miss','select_cache',records=3,hit_index=4)
    add('cache-df-hit','select_cache',df=True)
    add('cache-df-miss','select_cache',df=True,mismatch=0)
    add('cache-length-wrap','select_cache',records=2,length_wrap=True)
    add('cache-segment-wrap','select_cache',records=2,hit_index=1,cache_segment=65535,length=19)
    add('cache-published-fields-alias-saved-ds','select_cache',saved_ds_alias=True)
    for sp in (0,1,65535):add(f'cache-stack-{sp}','select_cache',sp=sp)
    for n in range(256):add(f'disable-{n}','disable_cache',low_byte=n,df=bool(n&1))
    return result

def main():
    report=BUILD/'dat-cache-differential.json';report.unlink(missing_ok=True)
    lib=library();baseline=cases();sites=set();edges=set()
    for case in baseline:
        a,b=compare(lib,case);sites|=a;edges|=b
    if sites!=set(INS):raise AssertionError(f'Missing instructions {set(INS)-sites}')
    if edges!=EDGES:raise AssertionError(f'Missing/extra branch edges {EDGES-edges}/{edges-EDGES}')
    mutations=[]
    for mutation,kind in ((1,'prepare_name'),(2,'select_cache'),(3,'select_cache')):
        lib=library(mutation);hit=None
        for case in baseline:
            if case['kind']!=kind:continue
            try:compare(lib,case)
            except AssertionError:hit=case['name'];break
        if hit is None:raise AssertionError(f'Mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=('c/dat_cache.c','c/dat_cache.h','c/regs.h','c/lemmings_sym.h','tests/dat_cache.py',
           'tests/dat_io.py','tests/dat_io_c.py','tools/cbuild.py','tools/difftest.py','metadata/symbols.json')
    public=[{k:(v.hex() if isinstance(v,bytes) else v) for k,v in case.items()} for case in baseline]
    write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=len(baseline),mutation_count=3,
        mutations_detected=mutations,cases=public,translated_code_bytes=sum(i.size for i in INS.values()),
        executed_instruction_addresses=sorted(sites),branch_edges=sorted(edges),
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Quiescent mapped memory; filenames reach dot; intact instruction/return words; DF and live saved-data aliases included',
        flags_note='AF excluded only when final producer is AND/XOR; defined SUB/ADD flags compared'))
    print(f'PASS DAT cache C: {len(baseline)} cases, {len(sites)} sites, {len(edges)} branch edges, 3 compiled mutations detected')

if __name__=='__main__':main()

"""Selected resources: original caller versus connected native decimal/file cores."""
import ctypes
import random
from unicorn import Uc,UC_ARCH_X86,UC_MODE_16,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn import x86_const as x
from dat_io_c import Regs,Io,QUERY,READ,MEM,Result
from dat_files import Services,FILE,RETRY_FN,MAPPING
from resource_raw import Services as RawServices,OPEN
import dat_io as oracle
import dat_load as loader
import dat_section as decoder
import resource_raw as raw
import decimal_digits_c as decimal
from resources import section_spans,decode_section
from common import ROOT,BUILD,read_json,write_json,sha
from cbuild import build

SYMS={s['symbol_name']:s for s in read_json(ROOT/'metadata/symbols.json')}
ROUTINE=SYMS['LoadSelectedLevelResources'];ENTRY=ROUTINE['address'];END=ENTRY+ROUTINE['size']
LOCAL={i.address:i for i in decoder.MD.disasm(decoder.IMAGE[ENTRY:END],ENTRY) if i.mnemonic!='nop'}
INS=LOCAL|loader.INS|raw.INS|decimal.INS
BRANCHES={pc for pc,i in INS.items() if i.group(decoder.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES={(pc,i.operands[0].imm&65535) for pc,i in LOCAL.items() if pc in BRANCHES}
EDGES|={(pc,pc+i.size) for pc,i in LOCAL.items() if pc in BRANCHES and i.mnemonic!='jmp'}
class SelectionServices(ctypes.Structure):
    _fields_=[('files',ctypes.POINTER(Services)),('io',ctypes.POINTER(Io)),('raw',ctypes.POINTER(RawServices))]

def field(name):return SYMS[name]['address']
def record_packet(number,graphics=0,special=0):
    record=bytearray(2048);record[0]=0xa0+number;record[27]=graphics;record[29]=special
    # Keep the compressed prefix behind the expanding output, as the original
    # caller decodes in place. A long final literal can overwrite unread bits.
    packet=decoder.section([('literal',b'\0'*8)]+[('match',(256,1))]*7+
        [('match',(218,1)),('literal',bytes((special,0,graphics,0))),
         ('match',(25,1)),('literal',bytes((record[0],)))])
    if decode_section(packet)[0]!=record:raise AssertionError('Wrong constructed record encoder')
    return packet,bytes(record)

def cases():
    out=[]
    def add(name,**kw):out.append(dict(name=name,seed=len(out),**kw))
    for section in range(8):
        for odd in (False,True):add(f'section-{section}-odd-{odd}',order=2*section+int(odd)+1)
    add('zero-order-byte-wrap',order=0,selector=255)
    add('past-order-domain',order=1,selector=120)
    add('special-resource-path',order=1,special=1)
    add('graphics-selector-byte-wrap',order=1,graphics=0xf1)
    add('special-selector-byte-wrap',order=1,special=0xd1)
    for path in ('hit','miss'):add(f'cache-{path}',order=1,path=path)
    add('incoming-df-set',order=1,df=True)
    add('odd-copy-incoming-df',order=2,odd_df=True)
    add('level-close-carry-ignored',order=1,close_error='level')
    add('final-close-carry-exposed',order=1,close_error='graphics')
    add('final-close-df-exposed',order=1,final_df=True)
    add('read-overwrites-section-counter',order=1,counter_alias=2)
    add('close-overwrites-odd-selector',order=1,order_alias=0xab03)
    add('odd-read-overwrites-selector',order=2,odd_order_alias=0xab05)
    add('ground-read-overwrites-saved-ds',order=1,ground_alias=True)
    add('ground-empty-read',order=1,ground_short=0)
    add('ground-long-request',order=1,ground_long=True)
    add('stack-ffff',order=1,sp=65535)
    add('stack-underflow',order=1,sp=1)
    add('attributes-retry',order=1,attribute_errors=1)
    add('attributes-fatal',order=1,attribute_errors=1,retry_enabled=0)
    add('level-header-fatal',order=1,read_error=('level',0))
    add('later-level-payload-fatal',order=3,read_error=('level',3))
    add('graphics-header-fatal',order=1,read_error=('graphics',0))
    add('graphics-next-payload-fatal',order=1,read_error=('graphics',3))
    for stage in ('open','read','close'):add(f'ground-{stage}-fatal',order=1,raw_error=('ground',stage))
    for stage in ('open','read','close'):add(f'odd-{stage}-fatal',order=2,raw_error=('odd',stage))
    add('special-payload-fatal',order=1,special=1,read_error=('special',1))
    # Paired real inputs are selected from their original order bytes/record fields.
    order=decoder.IMAGE[0x9a90+field('LevelResourceOrderBytes'):0x9a90+field('LevelResourceOrderBytes')+120]
    seen=set();real_odd=None
    for selector,value in enumerate(order):
        n=(value-1)&255;group=n>>4;section=(n>>1)&7
        asset=f'assets/level{group:03d}.dat'
        if not (ROOT/asset).exists():continue
        packed=(ROOT/asset).read_bytes();a,b=section_spans(packed)[section];record,_=decode_section(packed[a:b])
        kind=(record[27],record[29])
        if n&1 and real_odd is None:real_odd=(selector,value)
        if kind not in seen:
            seen.add(kind);add(f'real-selection-{selector}',order=value,selector=selector,real=True)
    if real_odd is None:raise AssertionError('No pinned real odd override selection found')
    selector,value=real_odd
    add(f'real-odd-selection-{selector}',order=value,selector=selector,real=True)
    return out

def prepare(case):
    rng=random.Random(0x197d+case['seed']);load=(0x1010,0x1213,0x2345)[case['seed']%3];data=load+0x9a9
    mem=bytearray(rng.randbytes(1<<20));mem[load<<4:(load<<4)+len(decoder.IMAGE)]=decoder.relocated(decoder.IMAGE,decoder.ORACLE['relocations'],load)
    regs={n:rng.randrange(65536) for n in oracle.REG_NAMES};regs.update(cs=load,ip=ENTRY,ds=data,ss=0x7000,sp=case.get('sp',0x8000))
    if case.get('ground_alias'):regs.update(ss=data,sp=0x1f6d)
    flags=2|((case['seed']*0x95)&0xad5)|(0x400 if case.get('df') else 0)
    mem[oracle.at(data,field('LevelResourceSelectionByte'))]=case.get('selector',0)
    mem[oracle.at(data,field('LevelResourceOrderBytes')+case.get('selector',0))]=case['order']
    # Ground can replace DS through the original saved word. Alternate frame
    # configuration keeps the subsequent observed path bounded without restoring DS.
    for seg in (data,0x6000):
        oracle.put16(mem,seg,field('GraphicsResourceInputSegment'),0x4000);oracle.put16(mem,seg,field('LevelGraphicsSegment'),0x5000)
        for name,value in dict(DatCacheEnabled=0 if case.get('path','direct')=='direct' else 255,DatCacheSelected=0,
            DatCacheRecordCount=0,DatCriticalErrorFlag=0,DatRetryEnabled=case.get('retry_enabled',255)).items():mem[oracle.at(seg,field(name))]=value
        if seg!=data:
            mem[oracle.at(seg,field('GraphicsDatFilename')):oracle.at(seg,field('GraphicsDatFilename'))+11]=b'vgagr0.dat\0'
            mem[oracle.at(seg,field('LevelGraphicsSetByte'))]=0
            mem[oracle.at(seg,field('LevelSpecialGraphicsSetByte'))]=0
    for name,value in dict(DatCacheBaseSegment=0x8000,DatCacheFreeSegment=0x8000,DatCacheFreeOffset=0,DatCacheRemainingParagraphs=0x1000).items():oracle.put16(mem,data,field(name),value)
    oracle.put16(mem,regs['ss'],regs['sp'],0xff00)
    records=[];packets=[]
    for number in range(8):
        packet,record=record_packet(number,case.get('graphics',0),case.get('special',0));packets.append(packet);records.append(record)
    assets=[]
    n=(case['order']-1)&255;group=n>>4;section=(n>>1)&7
    level=b''.join(packets)
    if case.get('real'):
        asset=f'assets/level{group:03d}.dat';level=(ROOT/asset).read_bytes();assets.append(asset)
        records=[decode_section(level[a:b])[0] for a,b in section_spans(level)]
    chosen=records[case.get('counter_alias',section)];graphics=chosen[27];special=chosen[29]
    ground=bytes((i*17+3)&255 for i in range(1056));odd=bytes((i*29+7)&255 for i in range(0x1180))
    gfx=decoder.section([('literal',b'GRAPHICS')])+decoder.section([('literal',b'OBJECTS')]);spec=decoder.section([('literal',b'SPECIAL')])
    if case.get('real'):
        ground_asset=f'assets/ground{graphics}o.dat';ground=(ROOT/ground_asset).read_bytes();assets.append(ground_asset)
        odd=(ROOT/'assets/oddtable.dat').read_bytes();assets.append('assets/oddtable.dat')
        if special:
            special_asset=f'assets/vgaspec{special-1}.dat';packed=(ROOT/special_asset).read_bytes();a,b=section_spans(packed)[0];spec=packed[a:b];assets.append(special_asset)
        else:
            graphics_asset=f'assets/vgagr{graphics}.dat';packed=(ROOT/graphics_asset).read_bytes();gfx=packed[:section_spans(packed)[1][1]];assets.append(graphics_asset)
    if case.get('ground_alias'):ground=ground[:-4]+b'\0\x60\0\x60'
    if case.get('ground_long'):
        p=oracle.at(data,field('GroundResourceBuffer'));ground=bytes(mem[p:p+0x1000])
    if case.get('ground_short') is not None:ground=ground[:case['ground_short']]
    payloads=dict(level=level,ground=ground,odd=odd,graphics=gfx,special=spec)
    if case.get('path')=='hit':
        cursor=0
        for name,payload in ((b'level000dat',level),(b'vgagr0  dat',gfx)):
            mem[0x80000+cursor:0x80000+cursor+11]=name;oracle.put16(mem,0x8000,cursor+11,len(payload))
            mem[0x80000+cursor+13:0x80000+cursor+13+len(payload)]=payload;cursor+=13+len(payload)
        mem[oracle.at(data,field('DatCacheRecordCount'))]=2
    return mem,regs,flags,data,payloads,chosen,assets

class Provider:
    def __init__(self,case,mem,regs,data,payloads,chosen):
        self.case=case;self.mem=mem;self.regs=regs;self.data=data;self.payloads=payloads;self.trace=[];self.handles={};self.next=7
        self.attributes=0;self.expected=bytearray(chosen);self.calls={};self.positions={};self.current=None
    def filename(self,seg,off):
        out=bytearray()
        for i in range(64):
            value=self.mem[oracle.at(seg,off+i)]
            if not value:break
            out.append(value)
        else:raise AssertionError('Unterminated fixture filename')
        return bytes(out)
    def kind(self,name):
        for prefix,kind in ((b'level','level'),(b'ground','ground'),(b'oddtable','odd'),(b'vgagr','graphics'),(b'vgaspec','special')):
            if name.startswith(prefix):return kind
        raise AssertionError(f'Unexpected filename {name!r}')
    def flags(self,flags,failed=False):return (flags&~0x8d5)|0x894|int(failed)
    def file(self,function,seg,off,flags):
        name=self.filename(seg,off);kind=self.kind(name);failed=False
        if function==0x43:
            failed=self.attributes<self.case.get('attribute_errors',0);self.attributes+=1;value=5 if failed else 0;count=0x1234
        else:
            failed=self.case.get('raw_error')==(kind,'open');value=5 if failed else self.next;count=0
            if not failed:
                self.handles[value]=kind;self.positions[value]=0;self.calls[value]=0;self.next+=1;self.current=kind
        # Attribute setup ends in XOR CX,CX (undefined AF); open setup retains
        # the defined arithmetic flags from the preceding CMP/ADD/provider.
        mask=0xfc7 if function==0x43 else 0xfd7
        self.trace.append(dict(function=function,filename=name.hex(),segment=seg,offset=off,flags=flags&mask))
        return value,count,self.flags(flags,failed)
    def query(self,seg,off,flags):
        size=len(self.payloads[self.current]);oracle.put16(self.mem,seg,off+33,size);oracle.put16(self.mem,seg,off+35,0)
        self.trace.append(dict(function=0x23,segment=seg,offset=off,flags=flags&0xfd7));return 0x2300,self.flags(flags)
    def read(self,handle,seg,off,count,flags):
        kind=self.handles[handle];index=self.calls[handle];self.calls[handle]+=1
        failed=self.case.get('raw_error')==(kind,'read') or self.case.get('read_error')==(kind,index)
        position=self.positions[handle];part=self.payloads[kind][position:position+count]
        if not failed:
            for i,value in enumerate(part):self.mem[oracle.at(seg,off+i)]=value
            self.positions[handle]+=len(part)
            if kind=='level' and index==0 and 'counter_alias' in self.case:oracle.put16(self.mem,self.regs['ss'],(self.regs['sp']-4)&65535,self.case['counter_alias'])
            if kind=='odd':
                if 'odd_order_alias' in self.case:oracle.put16(self.mem,self.regs['ss'],(self.regs['sp']-2)&65535,self.case['odd_order_alias'])
                value=oracle.get16(self.mem,self.regs['ss'],(self.regs['sp']-2)&65535);source=field('OddLevelOverrideBuffer')+((value&255)>>1)*56
                step=-2 if self.case.get('odd_df') else 2
                for dest,n in ((field('LoadedLevelRecord'),12),(field('LoadedLevelFooterBytes'),16)):
                    for _ in range(n):
                        for b in range(2):
                            relative=dest+b-field('LoadedLevelRecord')
                            if 0<=relative<2048:self.expected[relative]=self.mem[oracle.at(self.data,source+b)]
                        dest+=step;source+=step
        self.trace.append(dict(function=0x3f,kind=kind,handle=handle,segment=seg,offset=off,count=count,flags=flags&0xfd7))
        return 5 if failed else len(part),self.flags(flags,failed)
    def close(self,handle,value,flags):
        kind=self.handles.get(handle,'cached');failed=self.case.get('raw_error')==(kind,'close') or self.case.get('close_error')==kind
        if kind=='level' and 'order_alias' in self.case:oracle.put16(self.mem,self.regs['ss'],(self.regs['sp']-2)&65535,self.case['order_alias'])
        outflags=self.flags(flags,failed)
        if kind=='odd' and self.case.get('odd_df'):outflags|=0x400
        if kind in ('graphics','special') and self.case.get('final_df'):outflags|=0x400
        mask=0xfd7 if kind in ('ground','odd') else 0xfc7 # Decoder's AND leaves AF undefined.
        self.trace.append(dict(function=0x3e,kind=kind,handle=handle,value=value,flags=flags&mask))
        return 5 if failed else 0x6bad,outflags
    def retry(self,view):
        self.trace.append(dict(function='retry',view=view.copy()));return 0x1111,0x4567,0x6789,self.flags(view['flags'])

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'resource_select-m{mutation}.dll',mutation,'resource_select')))
    lib.lmn_load_selected_resources_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(SelectionServices)]
    lib.lmn_load_selected_resources_adapter.restype=None;return lib

def compare(lib,case):
    mem,regs,flags,data,payloads,chosen,assets=prepare(case);c_mem=bytearray(mem);r=Regs(**regs,flags=flags)
    cp=Provider(case,c_mem,regs,data,payloads,chosen);errors=[]
    def guarded(fn,out,*args):
        try:
            values=fn(*args)
            for (name,_),value in zip(out.contents._fields_,values):setattr(out.contents,name,value)
        except Exception as e:
            errors.append(e);out.contents.value=5;out.contents.flags=1
    @FILE
    def opened(ctx,memory,seg,off,inflags,out):guarded(cp.file,out,0x3d,seg,off,inflags)
    @FILE
    def attributes(ctx,memory,seg,off,inflags,out):guarded(cp.file,out,0x43,seg,off,inflags)
    @QUERY
    def query(ctx,memory,seg,off,inflags,out):guarded(cp.query,out,seg,off,inflags)
    @READ
    def read(ctx,memory,handle,seg,off,count,inflags,out):guarded(cp.read,out,handle,seg,off,count,inflags)
    @RETRY_FN
    def retry(ctx,memory,call,out):guarded(cp.retry,out,{reg:getattr(call.contents,name) for name,reg in MAPPING.items()})
    @OPEN
    def raw_open(ctx,memory,seg,off,inflags,out):
        def call(*args):value,count,outflags=cp.file(0x3d,*args);return value,outflags
        guarded(call,out,seg,off,inflags)
    @OPEN
    def close(ctx,memory,handle,value,inflags,out):guarded(cp.close,out,handle,value,inflags)
    files=Services(None,opened,attributes,retry);io=Io(None,query,read);raw_services=RawServices(None,raw_open,read,close)
    services=SelectionServices(ctypes.pointer(files),ctypes.pointer(io),ctypes.pointer(raw_services))
    lib.lmn_load_selected_resources_adapter((ctypes.c_uint8*(1<<20)).from_buffer(c_mem),ctypes.byref(r),ctypes.byref(services))
    if errors:raise errors[0]
    up=Provider(case,mem,regs,data,payloads,chosen);u=Uc(UC_ARCH_X86,UC_MODE_16);u.mem_map(0,1<<20);u.mem_write(0,bytes(mem))
    for n,reg in oracle.REG.items():u.reg_write(reg,regs[n])
    u.reg_write(x.UC_X86_REG_EFLAGS,flags);seen=set();edges=set();previous=None;done=False
    def interrupt(uc,num,_):
        if num!=0x21:raise AssertionError('Unexpected interrupt')
        mem[:]=uc.mem_read(0,1<<20);ax=uc.reg_read(oracle.REG['ax']);fn=ax>>8;seg=uc.reg_read(oracle.REG['ds']);off=uc.reg_read(oracle.REG['dx']);inflags=uc.reg_read(x.UC_X86_REG_EFLAGS)
        if fn in (0x3d,0x43):value,count,outflags=up.file(fn,seg,off,inflags)
        elif fn==0x23:value,outflags=up.query(seg,off,inflags)
        elif fn==0x3f:value,outflags=up.read(uc.reg_read(oracle.REG['bx']),seg,off,uc.reg_read(oracle.REG['cx']),inflags)
        elif fn==0x3e:value,outflags=up.close(uc.reg_read(oracle.REG['bx']),ax,inflags)
        else:raise AssertionError(f'Unexpected DOS function{fn:x}')
        uc.mem_write(0,bytes(mem));uc.reg_write(oracle.REG['ax'],value)
        if fn==0x43:uc.reg_write(oracle.REG['cx'],count)
        uc.reg_write(x.UC_X86_REG_EFLAGS,outflags)
    def code(uc,pc,size,_):
        nonlocal previous,done
        off=pc-(regs['cs']<<4)
        if previous in BRANCHES:edges.add((previous,off))
        if off in (0xff00,*loader.FATALS):done=True;uc.emu_stop();return
        if off==loader.RETRY:
            mem[:]=uc.mem_read(0,1<<20);view={n:uc.reg_read(reg) for n,reg in oracle.REG.items() if n not in ('cs','ip')};view['flags']=uc.reg_read(x.UC_X86_REG_EFLAGS)&65535
            value,bx,bp,outflags=up.retry(view);uc.mem_write(0,bytes(mem))
            for n,value in dict(ax=value,bx=bx,bp=bp,si=0x2222,di=0x3333,ds=0x4444,es=0x5555,cx=0x6666,dx=0x7777).items():uc.reg_write(oracle.REG[n],value)
            sp=uc.reg_read(oracle.REG['sp']);uc.reg_write(oracle.REG['ip'],oracle.get16(mem,regs['ss'],sp));uc.reg_write(oracle.REG['sp'],(sp+2)&65535);uc.reg_write(x.UC_X86_REG_EFLAGS,outflags);previous=None;return
        if uc.reg_read(oracle.REG['cs'])!=regs['cs'] or off not in INS:raise AssertionError(f'Selection escaped at{off:x}')
        seen.add(off);previous=off
    u.hook_add(UC_HOOK_CODE,code);u.hook_add(UC_HOOK_INTR,interrupt);u.emu_start(oracle.at(regs['cs'],ENTRY),0,count=10000000)
    if not done:raise AssertionError('Resource selection exceeded budget')
    for name,reg in oracle.REG.items():
        if u.reg_read(reg)!=getattr(r,name):raise AssertionError(f'{case["name"]}: {name} C={getattr(r,name):04x}/original={u.reg_read(reg):04x}')
    if (r.flags^u.reg_read(x.UC_X86_REG_EFLAGS))&0xfd7:raise AssertionError(f'{case["name"]}: defined exit flags differ')
    actual=bytes(u.mem_read(0,1<<20))
    if actual!=c_mem:
        p=next(i for i,(a,b) in enumerate(zip(actual,c_mem)) if a!=b);raise AssertionError(f'{case["name"]}: RAM differs at{p:05x}')
    if cp.trace!=up.trace:raise AssertionError(f'{case["name"]}: service trace differs {cp.trace}/{up.trace}')
    if case['name'].startswith('real-odd-') and not any(t.get('kind')=='odd' and t['function']==0x3f for t in up.trace):
        raise AssertionError('Pinned odd override was not read')
    if u.reg_read(oracle.REG['ip'])==0xff00:
        p=oracle.at(data,field('LoadedLevelRecord'))
        if actual[p:p+2048]!=up.expected:
            differences=[(i,a,b) for i,(a,b) in enumerate(zip(actual[p:p+2048],up.expected)) if a!=b]
            raise AssertionError(f'{case["name"]}: selected/overridden record differs from independent expected bytes {differences[:12]}')
    return seen,edges,assets

def main():
    report=BUILD/'resource-select-differential.json';report.unlink(missing_ok=True);baseline=cases();lib=library();seen=set();edges=set();assets=set()
    for case in baseline:
        a,b,c=compare(lib,case);seen|=a;edges|=b;assets.update(c)
    if not set(LOCAL)<=seen or not EDGES<=edges:raise AssertionError(f'Missing caller sites/edges {set(LOCAL)-seen}/{EDGES-edges}')
    mutations=[]
    for mutation,name in ((1,'zero-order-byte-wrap'),(2,'ground-read-overwrites-saved-ds'),(3,'level-close-carry-ignored')):
        lib=library(mutation);case=next(c for c in baseline if c['name']==name)
        try:compare(lib,case)
        except AssertionError:mutations.append(dict(mutation=mutation,case=name))
        else:raise AssertionError(f'Select mutation{mutation} survived')
    paths=tuple('c/'+name for name in ('resource_select.c','resource_select.h','decimal_digits.c','decimal_digits.h','resource_raw.c','resource_raw.h',
        'dat_load.c','dat_load.h','dat_files.c','dat_files.h','dat_cache.c','dat_cache.h','dat_section.c','dat_section.h','dat_io.c','dat_io.h','dat.c','dat.h','regs.h','lemmings_sym.h'))
    paths+=('tests/resource_select.py','tests/decimal_digits_c.py','tests/resource_raw.py','tests/dat_load.py','tests/dat_files.py','tests/dat_section.py','tests/dat_io.py','tests/dat_io_c.py',
        'tools/cbuild.py','tools/difftest.py','tools/resources.py','metadata/symbols.json','metadata/inputs.json')+tuple(sorted(assets))
    write_json(report,dict(image='main',image_sha256=sha(decoder.IMAGE),case_count=len(baseline),mutation_count=3,cases=baseline,mutations_detected=mutations,
        executed_instruction_addresses=sorted(seen),caller_instruction_addresses=sorted(LOCAL),caller_branch_edges=sorted(EDGES),branch_edges=sorted(edges),
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},domain='Connected native decimal/raw/file/cache/decoder cores; declared DOS and4B1C seams; intact active returns; explicit1949/04D0 exits'))
    print(f'PASS resource selection C: {len(baseline)} cases,{len(LOCAL)} caller sites,{len(seen)} integrated sites,{len(EDGES)} caller edges;3 compiled mutations detected')
if __name__=='__main__':main()

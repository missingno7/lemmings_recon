"""Native DAT read/cache wrapper versus its complete original closed interval."""
import ctypes
import dat_io as oracle
from common import ROOT,BUILD,sha,write_json
from cbuild import build

NAMES=oracle.REG_NAMES+('flags',)
class Regs(ctypes.Structure):_fields_=[(n,ctypes.c_uint16) for n in NAMES]
class Result(ctypes.Structure):_fields_=[('value',ctypes.c_uint16),('flags',ctypes.c_uint16)]
MEM=ctypes.POINTER(ctypes.c_uint8)
QUERY=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,ctypes.c_uint16,ctypes.c_uint16,ctypes.c_uint16,ctypes.POINTER(Result))
READ=ctypes.CFUNCTYPE(None,ctypes.c_void_p,MEM,*([ctypes.c_uint16]*5),ctypes.POINTER(Result))
class Io(ctypes.Structure):_fields_=[('context',ctypes.c_void_p),('query',QUERY),('read',READ)]

def library(mutation=0):
    lib=ctypes.CDLL(str(build(BUILD/f'dat_io-m{mutation}.dll',mutation,'dat_io')))
    lib.lmn_dat_read_adapter.argtypes=[MEM,ctypes.POINTER(Regs),ctypes.POINTER(Io)]
    lib.lmn_dat_read_adapter.restype=None
    return lib

def native(lib):
    def execute(case,mem,regs,flags,data_segment):
        mem=bytearray(mem);r=Regs(**regs,flags=flags);trace=[];errors=[]
        def service(memory,state,inflags,out):
            try:
                ram=bytearray(memory[:1<<20])
                outflags=oracle.services(case,ram,state,inflags,trace,data_segment)
                ctypes.memmove(memory,bytes(ram),len(ram))
                out.contents.value=state['ax'];out.contents.flags=outflags
            except Exception as e:errors.append(e)
        @QUERY
        def query(context,memory,segment,offset,inflags,out):
            service(memory,dict(ax=0x2300,ds=segment,dx=offset),inflags,out)
        @READ
        def read(context,memory,handle,segment,offset,count,inflags,out):
            service(memory,dict(ax=0x3f00,bx=handle,ds=segment,dx=offset,cx=count),inflags,out)
        io=Io(None,query,read)
        lib.lmn_dat_read_adapter((ctypes.c_uint8*(1<<20)).from_buffer(mem),ctypes.byref(r),ctypes.byref(io))
        if errors:raise errors[0]
        return mem,{n:getattr(r,n) for n in oracle.REG_NAMES},r.flags,trace
    return execute

def main():
    report=BUILD/'dat-io-differential.json';report.unlink(missing_ok=True)
    baseline=oracle.cases();lib=library();coverage=set();edges=set()
    for case in baseline:
        sites,branches,_=oracle.run(case,native(lib));coverage|=sites;edges|=branches
    if coverage!=set(oracle.INS) or edges!=oracle.EDGES:raise AssertionError('Incomplete native read-wrapper coverage')
    mutations=[]
    for mutation in (1,2,3):
        lib=library(mutation);hit=None
        for case in baseline:
            try:oracle.run(case,native(lib))
            except AssertionError:hit=case['name'];break
        if hit is None:raise AssertionError(f'Mutation {mutation} survived')
        mutations.append(dict(mutation=mutation,case=hit))
    paths=('c/dat_io.c','c/dat_io.h','c/regs.h','c/lemmings_sym.h','tools/cbuild.py','tools/difftest.py',
           'tests/dat_io.py','tests/dat_io_c.py','metadata/symbols.json')
    write_json(report,dict(image='main',image_sha256=sha(oracle.IMAGE),case_count=len(baseline),
        mutation_count=len(mutations),mutations_detected=mutations,cases=baseline,
        translated_code_bytes=sum(i.size for i in oracle.INS.values()),
        executed_instruction_addresses=sorted(coverage),branch_edges=sorted(edges),
        routines=[dict(name='ReadDatBytes',start=oracle.ENTRY,end=oracle.END,instruction_addresses=sorted(coverage))],
        input_hashes={p:sha((ROOT/p).read_bytes()) for p in paths},
        domain='Preserving DOS AH23/AH3F callbacks; full mapped memory; quiescent near calls; live saved-frame aliases'))
    print(f'PASS DAT read C: {len(baseline)} cases, {len(coverage)} instruction sites, {len(edges)} branch edges, 3 compiled mutations detected')

if __name__=='__main__':main()

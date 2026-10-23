"""Independent push/vector/provider/pop models and bounded native comparisons."""
import ctypes
import gc
import random
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import capstone
import video_restore as common
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, sha, write_json
from dat_io_c import MEM, Regs
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
FIELDS, REGS, FULL = common.FIELDS, common.REGS, common.FULL
State, StatePointer = common.State, ctypes.POINTER(common.State)
VECTOR = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, StatePointer, StatePointer)
ROUTINES = {
    'private': dict(start=0xfa0, end=0xfb2, interrupt=0xfae, ret=0xfb1,
                    pointer=0x1fc2, code=bytes.fromhex('1eb425a0c61f8b16c21f8e1ec41fcd211fc3')),
    'keyboard': dict(start=0x1582, end=0x1592, interrupt=0x158e, ret=0x1591,
                     pointer=0x1fba, code=bytes.fromhex('1eb809258b16ba1f8e1ebc1fcd211fc3')),
}
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {i.address: i for r in ROUTINES.values() for i in MD.disasm(r['code'], r['start'])}
REPORT = BUILD / 'vector-restore-differential.json'
ORIGINAL_REPORT = BUILD / 'vector-restore-contract-original.json'


class Services(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('set_vector', VECTOR)]


class Result(ctypes.Structure):
    _fields_ = [('state', State), ('continuation', ctypes.c_uint16), ('status', ctypes.c_int)]


class NativeMismatch(AssertionError):
    pass


def native_fail(message): raise NativeMismatch(message)
def oracle_fail(message): raise common.fixture.VerificationFailure(message)


def cases():
    rows = []
    for routine, count in [('private', 256), ('keyboard', 32)]:
        for n in range(count):
            rows.append(dict(routine=routine, seed=len(rows), vector=n,
                             name=f'{routine}-normal-{n:02x}'))
    kinds = ('save-offset', 'save-segment', 'save-selector-high', 'provider-save-write',
             'provider-return-write', 'provider-switch-stack', 'push-sp-zero',
             'push-sp-one', 'pop-a20', 'pop-sp-ffff', 'vga-pointers', 'vga-stack',
             'provider-ivt-write', 'ds-a20')
    for routine in ROUTINES:
        for kind in kinds:
            rows.append(dict(routine=routine, seed=len(rows), vector=0x74,
                             name=routine + '-' + kind, kind=kind))
        for load in common.LOADS:
            for missing in ('no-services', 'null-function'):
                rows.append(dict(routine=routine, seed=len(rows), vector=0xc,
                                 name=f'{routine}-{missing}-{load:04x}',
                                 missing=missing, load=load))
    for case in rows: case.setdefault('load', common.LOADS[case['seed'] % 3])
    return rows


def prepare(case):
    rng = random.Random(0x15820fa0 + case['seed'])
    memory = bytearray(rng.randbytes(1 << 20))
    loaded = relocated(IMAGE, ORACLE['relocations'], case['load'])
    memory[case['load'] << 4:(case['load'] << 4) + len(loaded)] = loaded
    initial = {k: rng.randrange(65536) for k in REGS}
    output = {k: rng.randrange(65536) for k in REGS}
    initial.update(ds=0x3000, es=0x6200, ss=0x7000, sp=0x8000,
                   flags=2 | ((case['seed'] * 0x95) & 0xed5))
    output.update(ds=0x5100, es=0x6300, ss=0x7300, sp=0x8200,
                  flags=2 | ((case['seed'] * 0x59 + 0x4d) & 0xed5))
    r = ROUTINES[case['routine']]
    kind = case.get('kind')
    if kind == 'save-offset': initial.update(ss=initial['ds'], sp=r['pointer'] + 2)
    if kind == 'save-segment': initial.update(ss=initial['ds'], sp=r['pointer'] + 4)
    if kind == 'save-selector-high':
        initial.update(ss=initial['ds'], sp=0x1fc8 if case['routine']=='private' else r['pointer'] + 3)
    if kind == 'push-sp-zero': initial['sp'] = 0
    if kind == 'push-sp-one': initial['sp'] = 1
    if kind == 'ds-a20': initial['ds'] = 0xffff
    if kind == 'vga-pointers': initial['ds'] = 0xa000
    if kind == 'vga-stack': initial['ss'] = 0xa000
    if kind == 'provider-ivt-write':
        vector = case['vector'] if case['routine']=='private' else 9
        initial.update(ss=0, sp=vector * 4 + 2)
    preserve = not (case['seed'] & 1) or kind in (
        'save-offset','save-segment','save-selector-high','provider-save-write',
        'provider-return-write','push-sp-zero','push-sp-one','vga-stack','provider-ivt-write')
    if preserve: output.update(ss=initial['ss'], sp=(initial['sp'] - 2) & 65535)
    if kind == 'provider-switch-stack': output.update(ss=0x7500, sp=0x9000)
    if kind == 'pop-a20': output.update(ss=0xffff, sp=0xf)
    if kind == 'pop-sp-ffff': output.update(ss=0x7000, sp=0xffff)
    common.putword(memory, initial['ss'], initial['sp'], (0xee00 + case['seed']) & 65535)
    if (output['ss'], output['sp']) != (initial['ss'], (initial['sp'] - 2) & 65535):
        common.putword(memory, output['ss'], output['sp'], (0x6000 + case['seed']) & 65535)
        common.putword(memory, output['ss'], (output['sp'] + 2) & 65535,
                       (0xe200 + case['seed']) & 65535)
    pointer = (0x12ef + case['seed'] * 0x101) & 65535
    segment = (0x4400 + case['seed'] * 0x81) & 65535
    common.putword(memory, initial['ds'], r['pointer'], pointer)
    common.putword(memory, initial['ds'], r['pointer'] + 2, segment)
    memory[common.physical(initial['ds'], 0x1fc6)] = case['vector']
    return memory, initial, output


def device(memory, case):
    result = common.fixture.TraceDevice(bytearray(memory), 0x158200 + case['seed'], read_map=2)
    result.vga.seq[2] = 1
    p = ROUTINES[case['routine']]['pointer']
    pointer = (0x12ef + case['seed'] * 0x101) & 65535
    segment = (0x4400 + case['seed'] * 0x81) & 65535
    common.putword(result.vga.planes[2], 0, p, pointer)
    common.putword(result.vga.planes[2], 0, p + 2, segment)
    result.vga.planes[2][0x1fc6] = case['vector']
    if case.get('kind') == 'vga-stack':
        common.putword(result.vga.planes[2], 0, 0x7ffe, 0x55a5)
        common.putword(result.vga.planes[2], 0, 0x8000, 0xaa55)
    return result


def provider_effect(case, incoming, output, memory):
    writes = []
    kind = case.get('kind')
    if kind == 'provider-save-write':
        writes.append((output['ss'], output['sp'], 0x5aa5))
    if kind == 'provider-return-write':
        writes.append((output['ss'], (output['sp'] + 2) & 65535, 0x55cc))
    if kind == 'provider-ivt-write':
        offset = (incoming['ax'] & 255) * 4
        writes.extend(((0, offset, incoming['dx']), (0, offset + 2, incoming['ds'])))
    changed = []
    for segment, offset, value in writes:
        common.putword(memory, segment, offset, value)
        p = common.physical(segment, offset)
        changed.extend((p, (p + 1) & 0xfffff))
    return changed


def model(case, memory, initial, output, *, core):
    backend, state, calls = device(memory, case), dict(initial), []
    def read(address):
        address &= 0xfffff
        value = backend.vga.read(backend.memory, address, state['flags'])
        backend.events.add('read', address, value, state['flags'], FULL)
        return value
    def word(segment, offset):
        p = common.physical(segment, offset)
        low, high = read(p), read(p + 1)
        return low | (high << 8)
    state['sp'] = (state['sp'] - 2) & 65535
    p = common.physical(state['ss'], state['sp'])
    for address, value in ((p, state['ds'] & 255), ((p + 1) & 0xfffff, state['ds'] >> 8)):
        backend.vga.write(backend.memory, address, value, state['flags'])
        backend.events.add('write', address, value, state['flags'], FULL)
    r = ROUTINES[case['routine']]
    vector = read(common.physical(state['ds'], 0x1fc6)) if case['routine']=='private' else 9
    state['ax'] = 0x2500 | vector
    state['dx'] = word(state['ds'], r['pointer'])
    state['ds'] = word(state['ds'], r['pointer'] + 2)
    if case.get('missing'):
        return backend, state, calls, r['interrupt'], 1
    calls.append((0, dict(state), dict(output), FULL))
    provider_effect(case, state, output, backend.memory)
    state = dict(output)
    state['ds'] = word(state['ss'], state['sp'])
    state['sp'] = (state['sp'] + 2) & 65535
    if core: return backend, state, calls, r['ret'], 0
    target = word(state['ss'], state['sp'])
    state['sp'] = (state['sp'] + 2) & 65535
    return backend, state, calls, target, 0


def original_case(case, *, core):
    memory, initial, output = prepare(case)
    expected, wanted_state, wanted_calls, target, status = model(case, memory, initial, output, core=core)
    backend, calls = device(memory, case), []
    registers = {k: initial[k] for k in REGS if k != 'flags'}
    r = ROUTINES[case['routine']]
    registers.update(cs=case['load'], ip=r['start'])
    def interrupt(cpu, number, current):
        if number != 0x21 or calls: oracle_fail('Unexpected vector restore interrupt')
        incoming = {k: cpu.reg_read(common.drawing.oracle.REG[k]) for k in REGS if k != 'flags'}
        incoming['flags'] = cpu.reg_read(common.drawing.x.UC_X86_REG_EFLAGS) & 65535
        calls.append((0, incoming, dict(output), FULL))
        for p in provider_effect(case, incoming, output, current.memory):
            value = bytes((current.memory[p],))
            cpu.mem_write(p, value)
            cpu.mem_write(p + (1 << 20), value)
        for k in REGS:
            reg = common.drawing.x.UC_X86_REG_EFLAGS if k == 'flags' else common.drawing.oracle.REG[k]
            cpu.reg_write(reg, output[k])
    stop = r['interrupt'] if status else r['ret'] if core else None
    observed = common.drawing.original(case, backend, registers, initial['flags'],
        instructions=INS, far_calls=set(), stop_before=stop, interrupt=interrupt, max_steps=20)
    regs, mask, sites, edges, boundary, *_ = observed
    common.equal_state(regs, wanted_state, FULL, oracle_fail, case['name'] + ' model')
    common.equal_calls(calls, wanted_calls, oracle_fail, case['name'] + ' model')
    common.equal_device(backend, expected, oracle_fail, case['name'] + ' model')
    if (regs['cs'], regs['ip'], mask, bool(edges)) != (case['load'], target, FULL, False):
        oracle_fail(case['name'] + ' original control/flags differ')
    if boundary[0] != ('ready-return' if core or status else 'outer-return'):
        oracle_fail(case['name'] + ' original boundary differs')
    return memory, initial, output, backend, regs, calls, target, status, sites


def native_services(case, backend, output):
    calls = []
    @VECTOR
    def provider(_context, _memory, incoming, outgoing):
        if calls: common.fixture.exit_worker(86, 'Vector provider-call budget exhausted')
        try:
            entry = common.state_dict(incoming[0])
            calls.append((0, entry, dict(output), FULL))
            provider_effect(case, entry, output, backend.memory)
            for field, reg in zip(FIELDS, REGS): setattr(outgoing[0], field, output[reg])
        except BaseException as error:
            common.fixture.exit_worker(87, f'Vector provider failed: {error}')
    service = (None if case.get('missing')=='no-services' else
               Services(None, VECTOR() if case.get('missing') else provider))
    return service, calls, provider


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'vector-restore-m{mutation}.dll', mutation, 'vector_restore')
        self.library = ctypes.CDLL(str(path))
        self.cores, self.adapters = {}, {}
        for kind in ROUTINES:
            stem = 'lmn_restore_' + kind + '_vector'
            self.cores[kind] = getattr(self.library, stem + '_core')
            self.cores[kind].argtypes = [MEM, StatePointer, ctypes.POINTER(Services), ctypes.POINTER(common.fixture.RasterBus)]
            self.cores[kind].restype = Result
            self.adapters[kind] = getattr(self.library, stem + '_adapter')
            self.adapters[kind].argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(Services), ctypes.POINTER(common.fixture.RasterBus)]
            self.adapters[kind].restype = None


def compare(native, case):
    sites = set()
    for core in (False, True):
        memory, initial, output, expected, regs, expected_calls, target, status, observed = original_case(case, core=core)
        sites.update(observed)
        for null in (False, True):
            if null and case.get('kind','').startswith('vga-'): continue
            backend = device(memory, case)
            service, calls, callback = native_services(case, backend, output)
            bus = None if null else ctypes.byref(backend.bus)
            if core:
                state = common.to_state(initial)
                result = native.cores[case['routine']](common.buffer(backend.memory), ctypes.byref(state), common.pointer(service), bus)
                actual = common.state_dict(result.state)
                if (result.continuation, result.status) != (target, status): native_fail(case['name'] + ' core continuation differs')
            else:
                state = Regs(**{k:v for k,v in initial.items() if k!='flags'}, flags=initial['flags'],
                             cs=case['load'], ip=ROUTINES[case['routine']]['start'])
                native.adapters[case['routine']](common.buffer(backend.memory), ctypes.byref(state), common.pointer(service), bus)
                actual = {k:getattr(state,k) for k in REGS}
                if (state.cs,state.ip)!=(case['load'],target): native_fail(case['name'] + ' adapter ip/cs differs')
            common.equal_state(actual, regs, FULL, native_fail, case['name'])
            common.equal_calls(calls, expected_calls, native_fail, case['name'])
            if null:
                if backend.memory!=expected.memory: native_fail(case['name'] + ' null RAM differs')
            else:
                common.equal_device(backend, expected, native_fail, case['name'])
    return dict(name=case['name'], routine=case['routine'], missing=case.get('missing'),
                sites=sorted(sites), vga=case.get('kind','').startswith('vga-'))


def input_hashes(native=False):
    paths = set(common.input_hashes()) | {'tests/vector_restore.py'}
    if native: paths.update(('c/vector_restore.c','c/vector_restore.h','c/regs.h',
                            'c/special_blit.h','c/lemmings_sym.h','tools/coverage.py','tools/difftest.py'))
    return {p:sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def original_phase():
    before = input_hashes()
    if (sha(IMAGE) != 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e' or
            sha(ASSET.read_bytes()) != '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d' or
            ORACLE != read_json(ROOT/'metadata/oracle.json')): oracle_fail('Vector executable identity differs')
    if any(IMAGE[r['start']:r['end']]!=r['code'] for r in ROUTINES.values()): oracle_fail('Vector bytes differ')
    sites, rows = set(), []
    for case in cases():
        phases = {}
        for core in (False, True):
            result = original_case(case, core=core)
            sites.update(result[-1]);phases['core_sites' if core else 'adapter_sites'] = sorted(result[-1])
        rows.append(dict(name=case['name'],routine=case['routine'],**phases))
        gc.collect()
    if sites!=set(INS) or len(sites)!=15: oracle_fail('Vector site coverage incomplete')
    if before!=input_hashes(): oracle_fail('Vector original inputs changed')
    write_json(ORIGINAL_REPORT,dict(case_count=len(rows),auxiliary_core_cases=len(rows),
        image_sha256=sha(IMAGE),executed_instruction_addresses=sorted(sites),branch_edges=[],
        cases=rows,c_coverage_claimed=False,input_hashes=before,
        routine_bytes={k:r['code'].hex() for k,r in ROUTINES.items()}))
    print(f'PASS vector restore original: {len(rows)} cases,15 sites;no C coverage')


def worker(directory=None):
    common.fixture.MAX_BUS_EVENTS = 64
    common.fixture.MAX_VGA_EVENTS = 64
    common.drawing.common.MAX_VGA_EVENTS = 64
    before = input_hashes(directory is not None)
    original_phase()
    if directory is None:return
    native, rows, specs = Native(directory), [], cases()
    for case in specs:
        rows.append(compare(native,case));gc.collect()
    mutants = []
    variants = {number:Native(directory,number) for number in range(1,5)}
    for kind in ROUTINES:
        for mutation,witness in [(1,'save-offset'),(2,'provider-switch-stack'),
                                 (3,'provider-save-write'),(4,'provider-return-write')]:
            case=next(c for c in specs if c['routine']==kind and c.get('kind')==witness)
            try:compare(variants[mutation],case)
            except NativeMismatch as error:
                if mutation==4 and 'adapter ip/cs differs' not in str(error):oracle_fail('Need actual RET witness')
                mutants.append(dict(routine=kind,mutation=mutation,case=case['name'],mismatch=str(error),completed=True))
            else:raise AssertionError(f'Vector mutant{kind}/{mutation} survived')
            gc.collect()
    if before!=input_hashes(True):oracle_fail('Vector native inputs changed')
    if len(rows)!=328:oracle_fail('Vector matrix changed')
    write_json(REPORT,dict(image='main',image_sha256=sha(IMAGE),case_count=len(rows),
        auxiliary_core_cases=len(rows),null_bus_adapter_cases=sum(not r['vga'] for r in rows),
        cases=rows,mutation_count=4,mutation_observations=len(mutants),mutations=mutants,
        executed_instruction_addresses=sorted({p for r in rows for p in r['sites']}),branch_edges=[],
        translated_code_bytes=34,native_code_ranges=[[r['start'],r['end']] for r in ROUTINES.values()],
        routine_bytes={k:r['code'].hex() for k,r in ROUTINES.items()},input_hashes=before,
        limits=dict(worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,
                    instructions_per_original=20,bus_events=64,provider_calls=1),
        domain='Two explicit returning DOS25 providers;allGPR/DS/ES/SS/SP/flags andcanonical-memory '
               'effects;livePUSH/POP/RET aliases,RAM/VGA;intactcode/sameCS/TFclear/quiescentIRQs.'))
    print(f'PASS vector restore C: {len(rows)} cases,15 sites,4 mutants at both entries')


def main():
    BUILD.mkdir(exist_ok=True)
    if sys.argv[1:]==['--original-worker']:worker();return
    if len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2]);return
    if sys.argv[1:]==['--original-only']:
        ORIGINAL_REPORT.unlink(missing_ok=True)
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--original-worker'],cwd=ROOT,timeout=120,memory_mib=384);return
    if len(sys.argv)!=1:raise SystemExit('Unexpected vector restore arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='vector-restore-',parent=BUILD) as directory:
        run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory],cwd=ROOT,timeout=120,memory_mib=384)


if __name__=='__main__':main()

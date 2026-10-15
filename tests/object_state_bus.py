"""Bounded original/native checks for the observable four-call object span."""
import copy
import ctypes
import gc
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import object_state as fixtures
import object_cells_bus as bus_fixture
from bounded_process import run_bounded, temporary_build_directory
from cbuild import compiler
from common import ROOT, BUILD, sha, read_json, write_json
from dat_io_c import MEM, Regs
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INTR)
from unicorn import x86_const as x

REPORT = BUILD / 'object-state-bus-differential.json'
MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
DEFINED = 0x0fd7
ARITH, AF, CF, OF = 0x8d5, 0x10, 1, 0x800
EVENT_LIMIT = 150_000
INSTRUCTION_LIMIT = 2_000_000
CONTINUATIONS = {0x376a: 0x376d, 0x376d: 0x3770,
                 0x3770: 0x3773, 0x3773: 0x3776}
SOURCES = ('object_state', 'object_state_bus', 'object_graphics', 'steel_cells',
           'steel_cells_bus', 'object_cells', 'object_cells_bus',
           'object_coordinates', 'object_coordinates_bus')


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'data_segment', 'stack_segment', 'stack_offset', 'product_high',
        'base_cursor', 'flags')]


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'value', 'cell_cursor', 'remaining_records', 'dimension_state',
        'source_cursor', 'definition_cursor', 'base_cursor', 'extra_segment',
        'stack_offset', 'flags', 'continuation', 'changed_return')]


class VerificationFailure(RuntimeError):
    """An oracle/provider/budget failure, never a detected mutant."""


class Mismatch(AssertionError):
    """A completed comparison disagrees."""


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def hashes():
    paths = {'AGENTS.md', 'docs/executable.md', 'docs/object-state-bus.md',
             'metadata/symbols.json', 'metadata/inputs.json',
             'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
             'assets/vgalemmi.exe', 'tests/object_state_bus.py',
             'tests/object_graphics_bus.py'}
    paths.update(f'c/{source}.{suffix}' for source in SOURCES for suffix in ('c', 'h'))
    paths.update(f'assets/level{i:03d}.dat' for i in range(10))
    paths.update(f'assets/ground{i}o.dat' for i in range(5))
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'src').glob('*.asm'))
    paths.update(bus_fixture.local_python_import_paths())
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def check_hashes(expected):
    actual = hashes()
    if actual != expected:
        changed = [p for p in set(actual) | set(expected)
                   if actual.get(p) != expected.get(p)]
        raise VerificationFailure('Inputs changed during build/run: ' + ', '.join(sorted(changed)))


def advance_mask(pc, known):
    ins = fixtures.INS[pc]
    if ins.mnemonic in ('add', 'sub', 'cmp', 'neg'):
        return known | ARITH
    if ins.mnemonic in ('and', 'or', 'xor', 'test', 'shl', 'shr'):
        return (known | ARITH) & ~AF
    if ins.mnemonic == 'mul':
        return (known & ~ARITH) | CF | OF
    if ins.mnemonic in ('inc', 'dec'):
        return known | (ARITH & ~CF)
    if ins.mnemonic in ('rol', 'rcl'):
        return known | CF | OF
    return known


def original(case, memory, registers, flags, device):
    """Run only pinned instructions; observe all byte accesses and live frames."""
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 1 << 21)
    uc.mem_write(0, bytes(memory) * 2)
    for name, register in fixtures.oracle.REG.items():
        uc.reg_write(register, registers[name])
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    relocated = fixtures.relocated(fixtures.IMAGE, fixtures.ORACLE['relocations'], registers['cs'])
    code_bytes = {fixtures.at(registers['cs'], pc + n): relocated[pc + n]
                  for pc, ins in fixtures.INS.items() for n in range(ins.size)}
    if any(memory[p] != value for p, value in code_bytes.items()):
        raise VerificationFailure(case['name'] + ': constructed state changed pinned instructions')
    state = dict(previous=None, pc=None, flags=flags, mask=DEFINED,
                 expected_return=None, done=False, failure=None, steps=0,
                 rep_flags=None, rep_corrections=0)
    events, sites, edges, calls = [], set(), set(), []

    def fail(message):
        state['failure'] = message
        uc.emu_stop()

    def code(cpu, address, size, _):
        pc = (address - (registers['cs'] << 4)) & 0xffff
        previous = state['previous']
        if previous is not None:
            state['mask'] = advance_mask(previous, state['mask'])
        if previous in fixtures.RETS and pc != state['expected_return']:
            state['done'] = True
            cpu.emu_stop()
            return
        if previous in fixtures.BRANCHES:
            edges.add((previous, pc))
        if pc == fixtures.END:
            state['done'] = True
            cpu.emu_stop()
            return
        if cpu.reg_read(fixtures.oracle.REG['cs']) != registers['cs'] or pc not in fixtures.INS:
            fail(f'{case["name"]}: original escaped at {pc:04x}')
            return
        state['steps'] += 1
        if state['steps'] > INSTRUCTION_LIMIT:
            fail('Original instruction budget exhausted')
            return
        raw_flags = cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
        # Unicorn's repeated MOVSB code hooks can clear AF although REP and
        # the following POPs preserve flags. Retain the original ADD SI,AX
        # result through precisely those sites, as independently probed by
        # object_graphics_bus.py. ADD BX at37B9 establishes fresh arithmetic.
        if pc == 0x37b4:
            if previous != pc:
                state['rep_flags'] = raw_flags
            state['flags'] = state['rep_flags']
        elif pc in (0x37b6, 0x37b7, 0x37b8) and state['rep_flags'] is not None:
            state['flags'] = state['rep_flags']
        else:
            state['flags'] = raw_flags
        if pc in (0x37b4, 0x37b6, 0x37b7, 0x37b8):
            if (raw_flags ^ state['flags']) & (DEFINED & ~AF):
                fail('Unexpected REP artifact beyond independently identified AF')
                return
            state['rep_corrections'] += int(raw_flags != state['flags'])
        if pc in CONTINUATIONS:
            state['expected_return'] = CONTINUATIONS[pc]
            calls.append(pc)
        state.update(pc=pc, previous=pc)
        sites.add(pc)

    def mirror(raw, p, value):
        for at in (raw, p, p + MEMORY_SIZE):
            if 0 <= at < 1 << 21:
                uc.mem_write(at, bytes((value,)))

    def access(kind, address, size, value=0):
        try:
            if not 0 <= address < address + size <= 1 << 21:
                fail('Original memory access outside mapped domain')
                return
            for n in range(size):
                if len(events) >= EVENT_LIMIT:
                    fail('Original event budget exhausted')
                    return
                p = (address + n) & MEMORY_MASK
                if kind == 'read':
                    byte = device.read(memory, p, state['flags']) if device else memory[p]
                else:
                    byte = (value >> (8 * n)) & 255
                    if p in code_bytes and byte != code_bytes[p]:
                        fail('Original write modifies executing code')
                        return
                    if device:
                        device.write(memory, p, byte, state['flags'])
                    else:
                        memory[p] = byte
                events.append((kind, p, byte, state['flags'], state['mask'], state['pc']))
                mirror(address + n, p, byte)
        except BaseException as error:
            fail(f'Original provider failure: {type(error).__name__}: {error}')

    def read(cpu, access_type, address, size, value, _):
        access('read', address, size)

    def write(cpu, access_type, address, size, value, _):
        access('write', address, size, value)

    def interrupt(cpu, number, _):
        fail(f'Unexpected original interrupt {number:02x}')

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, read)
    uc.hook_add(UC_HOOK_MEM_WRITE, write)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    uc.emu_start(fixtures.at(registers['cs'], fixtures.ENTRY), 0, count=INSTRUCTION_LIMIT)
    if state['failure'] or not state['done']:
        raise VerificationFailure(state['failure'] or 'Original instruction budget exhausted')
    if bytes(uc.mem_read(0, MEMORY_SIZE)) != bytes(memory):
        raise VerificationFailure('Original canonical memory and emulator mirror disagree')
    return dict(memory=bytes(memory), regs={n: uc.reg_read(r) for n, r in fixtures.oracle.REG.items()},
                flags=uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff, mask=state['mask'],
                events=events, sites=sites, edges=edges, calls=calls, device=device,
                rep_corrections=state['rep_corrections'])


def load_library(directory, mutation=0):
    lib = ctypes.CDLL(str(Path(directory) / f'object-state-bus-m{mutation}.dll'))
    lib.lmn_prepare_level_object_state_bus_core.argtypes = [MEM, ctypes.POINTER(Call), ctypes.POINTER(bus_fixture.RasterBus)]
    lib.lmn_prepare_level_object_state_bus_core.restype = Result
    lib.lmn_prepare_level_object_state_bus_adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(bus_fixture.RasterBus)]
    lib.lmn_prepare_level_object_state_bus_adapter.restype = None
    lib.lmn_prepare_level_object_state_adapter.argtypes = [MEM, ctypes.POINTER(Regs)]
    lib.lmn_prepare_level_object_state_adapter.restype = None
    return lib


def compare(lib, case, initial, registers, flags, device, *, baseline=True):
    expected = original(case, bytearray(initial), registers, flags, copy.deepcopy(device))
    for mode in ('adapter', 'core', 'null') if baseline else ('adapter',):
        if mode == 'null' and device is not None:
            continue
        memory = bytearray(initial)
        native_device = copy.deepcopy(device)
        callbacks = bus_fixture.CallbackBus(memory, native_device)
        bus = None if mode == 'null' else ctypes.byref(callbacks.bus)
        regs = Regs(**registers, flags=flags)
        view = (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(memory)
        if mode == 'core':
            call = Call(registers['ds'], registers['ss'], registers['sp'], registers['dx'], registers['bp'], flags)
            result = lib.lmn_prepare_level_object_state_bus_core(view, ctypes.byref(call), bus)
            for field, register in (('value', 'ax'), ('cell_cursor', 'bx'), ('remaining_records', 'cx'),
                    ('dimension_state', 'dx'), ('source_cursor', 'si'), ('definition_cursor', 'di'),
                    ('base_cursor', 'bp'), ('extra_segment', 'es'), ('stack_offset', 'sp'),
                    ('continuation', 'ip'), ('flags', 'flags')):
                setattr(regs, register, getattr(result, field))
            require(bool(result.changed_return) ==
                    (result.continuation != CONTINUATIONS[expected['calls'][-1]]),
                    case['name'] + ': changed-return result differs')
        else:
            lib.lmn_prepare_level_object_state_bus_adapter(view, ctypes.byref(regs), bus)
        require(bytes(memory) == expected['memory'], f'{case["name"]}/{mode}: whole RAM differs')
        require(bus_fixture.device_snapshot(native_device) == bus_fixture.device_snapshot(expected['device']),
                f'{case["name"]}/{mode}: device state differs')
        for name, value in expected['regs'].items():
            require(getattr(regs, name) == value,
                    f'{case["name"]}/{mode}: {name} {getattr(regs,name):04x} != {value:04x}')
        require(((regs.flags ^ expected['flags']) & expected['mask']) == 0,
                f'{case["name"]}/{mode}: final defined flags differ')
        if mode != 'null':
            require(len(callbacks.events) == len(expected['events']),
                    f'{case["name"]}/{mode}: event count {len(callbacks.events)} != {len(expected["events"])}')
            for index, (actual, wanted) in enumerate(zip(callbacks.events, expected['events'])):
                kind, address, value, event_flags, mask, pc = wanted
                require(actual[:3] == (kind, address, value),
                        f'{case["name"]}/{mode}: event {index} at {pc:04x}: {actual[:3]} != {wanted[:3]}')
                require(((actual[3] ^ event_flags) & mask) == 0,
                        f'{case["name"]}/{mode}: flags at event {index}/{pc:04x}: {actual[3]:04x} != {event_flags:04x}, mask={mask:04x}')
        elif device is None:
            old_mem = bytearray(initial)
            old_regs = Regs(**registers, flags=flags)
            lib.lmn_prepare_level_object_state_adapter((ctypes.c_uint8 * MEMORY_SIZE).from_buffer(old_mem), ctypes.byref(old_regs))
            require(old_mem == memory, case['name'] + ': previous RAM API memory differs')
            for name, _type in Regs._fields_:
                mask = expected['mask'] if name == 'flags' else 0xffff
                require(((getattr(old_regs, name) ^ getattr(regs, name)) & mask) == 0,
                        case['name'] + ': previous RAM API ' + name + ' differs')
    return expected


def extra_cases():
    entries = []
    def add(name, *, count=1, ss=None, sp=None, vga_source=False, vga_stack=False, df=False):
        case = dict(name=name, seed=1000 + len(entries), count=count, df=df)
        if ss is not None:
            case['ss'] = ss
        if sp is not None:
            case['sp'] = sp
        memory, regs, flags, _ = fixtures.prepare(case)
        if vga_source:
            source = bytes(memory[regs['ds'] << 4:(regs['ds'] << 4) + 65536])
            regs['ds'] = 0xa000
            memory[0xa0000:0xb0000] = source
        device = bus_fixture.configure_vga(memory, case['seed'], read_plane=2,
                                           write_mask=0x0f if vga_stack else 0x05)
        # Plane2 supplies CPU reads. Other planes differ at a known source,
        # so agreement must use the provider rather than canonical RAM alone.
        if vga_source:
            device.planes[0][fixtures.field('GroundResourceBuffer')] ^= 0x5a
        entries.append((case, memory, regs, flags, device))
    add('vga-source-copy-cells-and-coordinates', count=3, vga_source=True)
    add('vga-stack-all-call-frames', ss=0xa000, sp=0x9000, vga_stack=True)
    add('vga-stack-df-copy', count=2, ss=0xa000, sp=0x9000, vga_stack=True, df=True)
    add('vga-stack-sp-wrap', count=0, ss=0xa000, sp=1, vga_stack=True)
    add('call-word-physical-fffff', count=0, ss=0xffff, sp=0x11)
    add('call-word-offset-ffff', count=0, ss=0x7000, sp=1)
    for name, return_ip in (('provider-preserves-stale-es-and-return', 0x5000),
                            ('changed-first-return-to-normal-span-end', 0x3776)):
        add(name, count=0, ss=0xa000, sp=0x9000, vga_stack=True)
        _case, _memory, _regs, _flags, provider = entries[-1]
        provider.seq[2] = 1  # CALL/PUSH writes cannot change read plane2.
        provider.planes[2][0x8ffc:0x8ffe] = (0x6000).to_bytes(2, 'little')
        provider.planes[2][0x8ffe:0x9000] = return_ip.to_bytes(2, 'little')
    return entries


def compile_library(directory, mutation):
    output = Path(directory) / f'object-state-bus-m{mutation}.dll'
    command = [compiler(), '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-shared',
               '-DSTATE_MUTATION=0', f'-DSTATE_BUS_MUTATION={mutation}', '-I', str(ROOT / 'c')]
    command.extend(str(ROOT / f'c/{source}.c') for source in SOURCES)
    command.extend(['-o', str(output)])
    run_bounded(command, cwd=ROOT, timeout=60, memory_mib=256)


def worker(directory, hash_file):
    before = read_json(hash_file)
    lib = load_library(directory)
    baseline = fixtures.cases()
    extras = extra_cases()
    if (len(baseline), len(extras), len(fixtures.INS), len(fixtures.EDGES)) != (105, 8, 194, 33):
        raise VerificationFailure('Pinned fixture/site/edge counts changed')
    seen, edges, cases = set(), set(), []
    for case in baseline:
        memory, regs, flags, _ = fixtures.prepare(case)
        result = compare(lib, case, memory, regs, flags, None)
        seen.update(result['sites']); edges.update(result['edges'])
        cases.append(dict(name=case['name'], event_count=len(result['events']), calls=result['calls'],
                          continuation=result['regs']['ip'], rep_corrections=result['rep_corrections']))
        del result
        gc.collect()
    for case, memory, regs, flags, device in extras:
        result = compare(lib, case, memory, regs, flags, device)
        if case['name'] in ('provider-preserves-stale-es-and-return',
                            'changed-first-return-to-normal-span-end'):
            return_ip = 0x5000 if case['name'] == 'provider-preserves-stale-es-and-return' else 0x3776
            require(result['calls'] == [0x376a] and result['regs']['ip'] == return_ip
                    and result['regs']['es'] == 0x6000 and result['regs']['sp'] == regs['sp'],
                    'Provider must supply live ES and changed return before the second CALL')
        seen.update(result['sites']); edges.update(result['edges'])
        cases.append(dict(name=case['name'], event_count=len(result['events']), calls=result['calls'],
                          continuation=result['regs']['ip'], rep_corrections=result['rep_corrections']))
        del result
        gc.collect()
    require(seen == set(fixtures.INS), f'Integrated site mismatch: missing={set(fixtures.INS)-seen}, extra={seen-set(fixtures.INS)}')
    require(edges == fixtures.EDGES, f'Integrated edge mismatch: missing={fixtures.EDGES-edges}, extra={edges-fixtures.EDGES}')
    mutations = []
    for mutation, name in ((1, 'object-overwrites-steel'), (2, 'graphics-return-word-changed'),
                           (3, 'count-0-df-False'), (4, 'count-0-df-False')):
        case = next(c for c in baseline if c['name'] == name)
        memory, regs, flags, _ = fixtures.prepare(case)
        try:
            compare(load_library(directory, mutation), case, memory, regs, flags, None, baseline=False)
        except Mismatch:
            mutations.append(dict(mutation=mutation, case=name))
        else:
            raise VerificationFailure(f'Completed mutation {mutation} survived')
        gc.collect()
    check_hashes(before)
    write_json(REPORT, dict(image='main', image_sha256=sha(fixtures.IMAGE), case_count=len(cases),
        adapter_case_count=len(cases), core_boundary_case_count=len(cases),
        previous_ram_case_count=len(baseline), provider_case_count=len(extras), null_bus_case_count=len(baseline),
        cases=cases, mutation_count=len(mutations), mutations_detected=mutations,
        caller_instruction_addresses=sorted(fixtures.LOCAL), executed_instruction_addresses=sorted(seen),
        branch_edges=sorted(edges), translated_code_bytes=12, existing_translation_overlap_bytes=12,
        native_code_ranges=[[fixtures.ENTRY, fixtures.END]], input_hashes=before,
        limits=dict(worker_seconds=120, process_commit_mib=512, tree_commit_mib=768,
                    events_per_call=EVENT_LIMIT, original_instructions=INSTRUCTION_LIMIT),
        domain='Four bus-aware logical children, live CALL/RET/SS/device ordering; normal3776 or changed-return stop; intact code and quiescent IRQ. Core probes are auxiliary, bytes/sites are overlapping unions.'))
    print(f'PASS object state bus: {len(baseline)} RAM + {len(extras)} provider cases, '
          f'{len(seen)} integrated sites, {len(edges)} edges, {len(mutations)} completed mutants')


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if len(sys.argv) != 1:
        raise SystemExit('Unexpected arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    before = hashes()
    try:
        with temporary_build_directory(prefix='object-state-bus-', parent=BUILD) as directory:
            hash_file = Path(directory) / 'inputs.json'
            write_json(hash_file, before)
            for mutation in range(5):
                compile_library(directory, mutation)
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory, str(hash_file)],
                        cwd=ROOT, timeout=120, memory_mib=512)
    finally:
        check_hashes(before)


if __name__ == '__main__':
    main()

"""Bounded native allocation leaf versus original instructions and provider model."""
import ctypes
import gc
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import aligned_masked as fixture
import cache_allocation_contract as contract
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, sha, write_json
from dat_io_c import MEM, Regs

REPORT = BUILD / 'cache-allocation-differential.json'
LIMIT = 128


class NativeMismatch(AssertionError):
    """Completed native and original executions disagree; guards are separate."""


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


class ServiceResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in ('value', 'paragraphs', 'flags')]


ALLOCATE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, MEM, ctypes.c_uint16,
                           ctypes.c_uint16, ctypes.c_uint16,
                           ctypes.POINTER(ServiceResult))


class Services(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('allocate', ALLOCATE)]


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('value', 'paragraphs', 'flags', 'continuation')] + [
                    ('status', ctypes.c_int)]


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'cache-allocation-m{mutation}.dll',
                     mutation, 'cache_allocation')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_allocate_dat_cache_core
        self.core.argtypes = [MEM, ctypes.c_uint16, ctypes.c_uint16,
                              ctypes.c_uint16, ctypes.POINTER(Services),
                              ctypes.POINTER(fixture.RasterBus)]
        self.core.restype = Result
        self.adapter = self.library.lmn_allocate_dat_cache_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs),
                                 ctypes.POINTER(Services),
                                 ctypes.POINTER(fixture.RasterBus)]
        self.adapter.restype = None


def buffer(memory):
    return (ctypes.c_uint8 * len(memory)).from_buffer(memory)


def cases():
    ready = [contract.case_with_load(spec, load)
             for spec in contract.scenarios() for load in contract.LOADS]
    high = next(c for c in ready if c['returned_bx'] == 0x0c80 and
                c['first_cf'] == 1 and c['second_cf'] == 1 and c['second_ax'] == 8)
    low = next(c for c in ready if c['returned_bx'] == 0x0c7f)
    extras = []
    specs = [
        (high, 'vga-output', dict(ds=0xa000, vga=True)),
        (low, 'vga-low-enable', dict(ds=0xa000, vga=True)),
        (high, 'vga-stack-read-plane2-write-plane0',
         dict(ds=0xa000, ss=0xa000, sp=0x1f80, vga=True)),
        (high, 'provider-first-changes-return', dict(provider_effect='first-ret')),
        (high, 'provider-second-changes-request-field',
         dict(provider_effect='second-request')),
        (low, 'provider-low-changes-stale-field-and-return',
         dict(provider_effect='low-stale-ret')),
        (low, 'provider-first-ffff-preserves-high-byte', dict(first_override=0xffff)),
        (high, 'provider-first-0008-reaches-second-request', dict(first_override=8)),
        (high, 'provider-first-0000-second-ffff', dict(first_override=0, second_ax=0xffff)),
    ]
    for index, (base, name, updates) in enumerate(specs):
        spec = dict(base, seed=89 + index, name=name)
        spec.update(updates)
        value = contract.case_with_load(spec, contract.LOADS[index % 3])
        if 'first_override' in value:
            value['first_return_ax'] = value['first_override']
        extras.append(value)
    return ready + extras


def device(memory, case):
    result = fixture.TraceDevice(bytearray(memory), 0xca110c + case['seed'], read_map=2)
    if case.get('vga'):
        result.vga.seq[2] = 1
    return result


def effect(case, stage, memory, registers):
    mode = case.get('provider_effect')
    words = []
    if stage == 0 and mode in ('first-ret', 'low-stale-ret'):
        words.append((registers['ss'], registers['sp'], 0x55aa))
    if stage == 0 and mode == 'low-stale-ret':
        words.append((registers['ds'], 0x1f80, 0xbeef))
    if stage == 1 and mode == 'second-request':
        words.append((registers['ds'], 0x1f8e, 0x4321))
    changed = []
    for segment, offset, value in words:
        contract.write_word(memory, segment, offset, value)
        low = contract.physical(segment, offset)
        changed.extend((low, (low + 1) & 0xfffff))
    return changed


def service_values(case, stage):
    if stage == 0:
        return case['first_return_ax'], case['returned_bx'], contract.provider_flags(case, 0)
    return (case['second_ax'], (0x9c37 + case['seed'] * 11) & 65535,
            contract.provider_flags(case, 1))


def native_service(case, memory, registers):
    calls = []

    @ALLOCATE
    def allocate(_context, _memory, value, paragraphs, flags, out):
        if len(calls) >= 2:
            fixture.exit_worker(86, 'cache allocation provider-call budget exhausted')
        try:
            stage = len(calls)
            values = service_values(case, stage)
            calls.append((value, paragraphs, flags, *values))
            effect(case, stage, memory, registers)
            out[0].value, out[0].paragraphs, out[0].flags = values
        except BaseException as error:
            fixture.exit_worker(87, f'cache allocation provider failed: {error}')
    return Services(None, allocate), calls, allocate


def original(case, memory, registers, flags, instructions, *, stop=None):
    state = device(memory, case)
    calls = []
    base = contract.dos_provider(case, [])

    def interrupt(cpu, number, backend):
        stage = len(calls)
        value = cpu.reg_read(contract.piece.oracle.REG['ax'])
        paragraphs = cpu.reg_read(contract.piece.oracle.REG['bx'])
        incoming_flags = cpu.reg_read(contract.piece.x.UC_X86_REG_EFLAGS) & 65535
        base(cpu, number, backend)
        values = service_values(case, stage)
        # Additional first-result probes retain the shared fixture's routing
        # checks but supply AX=0000/0008/FFFF as their explicit provider output.
        cpu.reg_write(contract.piece.oracle.REG['ax'], values[0])
        calls.append((value, paragraphs, incoming_flags, *values))
        # This provider, rather than a CPU store, owns these writes. Keep both
        # Unicorn mappings synchronized with canonical RAM without bus events.
        for address in effect(case, stage, backend.memory, registers):
            data = bytes((backend.memory[address],))
            cpu.mem_write(address, data)
            cpu.mem_write(address + (1 << 20), data)

    result = contract.original_caller.original(
        case, state, registers, flags, instructions=instructions, far_calls=set(),
        max_steps=100, stop_before=stop, interrupt=interrupt)
    return state, calls, result


def check_device(actual, expected, label):
    actual.check(label)
    expected.check(label)
    require(actual.memory == expected.memory, label + ' whole RAM differs')
    require(actual.vga.state() == expected.vga.state(), label + ' VGA state differs')
    try:
        fixture.compare_event_traces(actual.events, expected.events, label)
    except fixture.Mismatch as error:
        raise NativeMismatch(str(error)) from error


def compare(native, case, instructions, *, null=True):
    memory, registers, flags, initial_return = contract.prepare(case, case['load'])
    ret = 0x1f18 if case['returned_bx'] < contract.THRESHOLD else 0x1f12
    expected_device, expected_calls, expected = original(
        case, memory, registers, flags, instructions)
    expected_regs, mask, sites, edges, boundary, *_ = expected
    if boundary[0] != 'outer-return':
        raise fixture.VerificationFailure('Original allocation did not execute its actual RET')
    core_device, core_calls, core_expected = original(
        case, memory, registers, flags, instructions, stop=ret)
    core_regs, core_mask, *_ = core_expected

    actual_device = device(memory, case)
    services, calls, callback = native_service(case, actual_device.memory, registers)
    actual_regs = Regs(**registers, flags=flags)
    native.adapter(buffer(actual_device.memory), ctypes.byref(actual_regs),
                   ctypes.byref(services), ctypes.byref(actual_device.bus))
    # Compare completed returns before testing any mutation's logical output.
    for name in contract.piece.oracle.REG_NAMES:
        require(getattr(actual_regs, name) == expected_regs[name],
                case['name'] + f' adapter {name} differs: '
                f'{getattr(actual_regs, name):04x}/{expected_regs[name]:04x}')
    require(not ((actual_regs.flags ^ expected_regs['flags']) & mask),
            case['name'] + ' adapter defined flags differ')
    require(calls == expected_calls, case['name'] + ' adapter provider inputs/outputs differ')
    check_device(actual_device, expected_device, case['name'] + ' adapter')

    core_actual = device(memory, case)
    core_services, actual_core_calls, core_callback = native_service(
        case, core_actual.memory, registers)
    output = native.core(buffer(core_actual.memory), registers['ds'], registers['ax'],
                         flags, ctypes.byref(core_services), ctypes.byref(core_actual.bus))
    require((output.value, output.paragraphs, output.continuation, output.status) ==
            (core_regs['ax'], core_regs['bx'], ret, 0),
            case['name'] + ' core logical result differs')
    require(not ((output.flags ^ core_regs['flags']) & core_mask),
            case['name'] + ' core defined flags differ')
    require(actual_core_calls == core_calls, case['name'] + ' core provider inputs/outputs differ')
    check_device(core_actual, core_device, case['name'] + ' core')

    if (not case.get('vga') and not case.get('provider_effect') and
            'first_override' not in case):
        formula = contract.logical_expected(case, memory, registers, flags, initial_return)
        if (expected_device.memory != formula['memory'] or
                any(expected_regs[n] != formula['registers'][n]
                    for n in contract.piece.oracle.REG_NAMES) or
                (expected_regs['flags'] ^ formula['flags']) & mask):
            raise fixture.VerificationFailure('Original differs from independent allocation model')

    null_checked = null and not case.get('vga')
    if null_checked:
        plain = bytearray(memory)
        plain_services, plain_calls, plain_callback = native_service(case, plain, registers)
        plain_regs = Regs(**registers, flags=flags)
        native.adapter(buffer(plain), ctypes.byref(plain_regs), ctypes.byref(plain_services), None)
        require(plain == expected_device.memory and plain_calls == expected_calls,
                case['name'] + ' null-bus RAM/provider differs')
        for name in contract.piece.oracle.REG_NAMES:
            require(getattr(plain_regs, name) == expected_regs[name],
                    case['name'] + f' null-bus {name} differs')
        require(not ((plain_regs.flags ^ expected_regs['flags']) & mask),
                case['name'] + ' null-bus flags differ')
    return dict(name=case['name'], null_bus=null_checked, bus_events=actual_device.events.count,
                core_bus_events=core_actual.events.count, vga=bool(case.get('vga')),
                provider_effect=case.get('provider_effect'), sites=sorted(sites),
                edges=sorted(edges), return_changed=actual_regs.ip != initial_return)


def missing_provider(native, instructions):
    results = []
    base = contract.scenarios()[0]
    for load in contract.LOADS:
        for mode in ('none', 'null-function'):
            case = contract.case_with_load(dict(base, name='missing-provider-' + mode), load)
            memory, registers, flags, _ = contract.prepare(case, load)
            expected_device, calls, expected = original(
                case, memory, registers, flags, instructions, stop=0x1edc)
            expected_regs, mask, sites, edges, *_ = expected
            services = Services(None, ALLOCATE()) if mode == 'null-function' else None
            pointer = ctypes.byref(services) if services is not None else None
            actual = device(memory, case)
            regs = Regs(**registers, flags=flags)
            native.adapter(buffer(actual.memory), ctypes.byref(regs), pointer,
                           ctypes.byref(actual.bus))
            for name in contract.piece.oracle.REG_NAMES:
                require(getattr(regs, name) == expected_regs[name],
                        case['name'] + f' missing-provider {name} differs')
            require(not ((regs.flags ^ flags) & mask), 'Missing provider changed flags')
            check_device(actual, expected_device, case['name'])
            out = native.core(buffer(actual.memory), registers['ds'], registers['ax'],
                              flags, pointer, ctypes.byref(actual.bus))
            require((out.value, out.paragraphs, out.continuation, out.status) ==
                    (expected_regs['ax'], 0xffff, 0x1edc, 1), 'Missing provider core differs')
            require(out.flags == flags and not calls, 'Missing provider did work')
            results.append(dict(name=case['name'], sites=sorted(sites), edges=sorted(edges)))
    return results


def input_hashes():
    paths = set(contract.loaded_input_paths()) | {
        'tests/cache_allocation.py', 'c/cache_allocation.c', 'c/cache_allocation.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'tools/cbuild.py', 'tools/difftest.py', 'tools/coverage.py',
        'metadata/hints.json', 'metadata/regions.json', 'metadata/encoding-exceptions.json',
    }
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def worker(directory):
    fixture.MAX_BUS_EVENTS = LIMIT
    fixture.MAX_VGA_EVENTS = LIMIT
    contract.piece.common.MAX_VGA_EVENTS = LIMIT
    instructions, branch_edges = contract.static_instructions()
    before = input_hashes()
    native = Native(directory)
    specs = cases()
    rows = []
    for case in specs:
        rows.append(compare(native, case, instructions))
        gc.collect()
    missing = missing_provider(native, instructions)
    rows.extend(missing)
    sites = {site for row in rows for site in row['sites']}
    edges = {tuple(edge) for row in rows for edge in row['edges']}
    if sites != set(instructions) or edges != branch_edges:
        raise fixture.VerificationFailure('Allocation site/branch coverage incomplete')
    witnesses = {
        1: next(c for c in specs if c['returned_bx'] >= contract.THRESHOLD and c['first_cf']),
        2: next(c for c in specs if c['returned_bx'] >= contract.THRESHOLD and
                c['second_cf'] and c['second_ax'] == 8),
        3: next(c for c in specs if c['returned_bx'] < contract.THRESHOLD),
        4: next(c for c in specs if c['ss'] == c['ds'] and c['sp'] == 0x1f80),
    }
    mutants = []
    for mutation, case in witnesses.items():
        mutant = Native(directory, mutation)
        try:
            compare(mutant, case, instructions, null=False)
        except NativeMismatch as error:
            if mutation == 4:
                require('adapter ip differs' in str(error), 'Stale-return mutant needs an IP witness')
            mutants.append(dict(mutation=mutation, case=case['name'], mismatch=str(error),
                                completed_native_and_original=True))
        else:
            raise AssertionError(f'Allocation mutant{mutation} survived')
        gc.collect()
    if before != input_hashes():
        raise fixture.VerificationFailure('Allocation inputs changed during execution')
    if len(rows) != 282:
        raise fixture.VerificationFailure(f'Expected282 cases, got{len(rows)}')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(contract.IMAGE), case_count=len(rows),
        adapter_case_count=len(rows), core_boundary_case_count=len(rows),
        ready_cases=len(specs), missing_provider_cases=len(missing),
        null_bus_cases=sum(row.get('null_bus', False) for row in rows),
        cases=rows, mutation_count=len(mutants), mutations=mutants,
        executed_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
        translated_code_bytes=66, native_code_ranges=[[contract.START, contract.END]],
        routine_bytes=contract.PINNED_CODE.hex(), input_hashes=before,
        domain='Identified allocation leaf, quiescent interrupts/TFclear, intact decoded code; '
               'constructed DOS AX/BX/flags provider, canonical memory effects, RAM/VGA bus '
               'and real near-return aliases. No boot or global reachability proof.',
        limits=dict(worker_seconds=120, windows_process_mib=384, windows_tree_mib=640,
                    instructions_per_original=100, bus_events=LIMIT, provider_calls=2)))
    print(f'PASS cache allocation C: {len(rows)} cases, {len(sites)} sites, '
          f'{len(edges)} edges; {len(mutants)} completed mutants')


def main():
    BUILD.mkdir(exist_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if len(sys.argv) != 1:
        raise SystemExit('Unexpected cache allocation arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='cache-allocation-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=120, memory_mib=384)


if __name__ == '__main__':
    main()

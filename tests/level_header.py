"""Native checks for the reconstructed 36B9..3741 level-header prefix."""
import ctypes
import ast
import gc
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import aligned_masked as fixture
import level_header_contract as contract
from bounded_process import run_bounded, temporary_build_directory
from common import BUILD, ROOT, read_json, sha, write_json
from cbuild import build
from dat_io_c import MEM, Regs
from minimap_vga import VGA_BASE, VGA_END


CALLBACK_LIMIT = 86
REPORT = BUILD / 'level-header-differential.json'
INPUTS = (
    'tests/level_header.py',
    'c/level_header.c', 'c/level_header.h', 'c/lemmings_sym.h',
    'c/regs.h', 'c/special_blit.h',
    'tools/cbuild.py',
    'metadata/symbols.json', 'src/game_code.asm', 'src/level_initialize.asm',
    'docs/level-header.md', 'docs/level-header-contract.md',
    'docs/level-header-ownership.md',
)


def require(condition, message):
    if not condition:
        raise fixture.Mismatch(message)


def dependency_paths():
    paths = set(contract.dependency_paths()) | set(INPUTS)
    pending = [ROOT / path for path in paths if path.endswith('.py')]
    while pending:
        path = pending.pop()
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module else []
            else:
                continue
            for name in names:
                for directory in ('tests', 'tools'):
                    candidate = ROOT / directory / (name.split('.')[0] + '.py')
                    if candidate.is_file():
                        relative = candidate.relative_to(ROOT).as_posix()
                        if relative not in paths:
                            paths.add(relative)
                            pending.append(candidate)
    return sorted(paths)


class NativeResult(ctypes.Structure):
    _fields_ = [('value', ctypes.c_uint16),
                ('header_cursor', ctypes.c_uint16),
                ('flags', ctypes.c_uint16)]


class NativeMismatch(AssertionError):
    """A completed native/original comparison found different behavior."""


def native_require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def compare_native_events(native_trace, original_trace, label):
    try:
        fixture.compare_event_traces(native_trace, original_trace, label)
    except fixture.Mismatch as error:
        raise NativeMismatch(str(error)) from error


def compare_native_vga(case, expected_events, device):
    try:
        contract.check_vga_trace(case, expected_events, device)
    except AssertionError as error:
        raise NativeMismatch(str(error)) from error


class Native:
    def __init__(self, directory, mutation=0):
        path = Path(directory) / f'level-header-m{mutation}.dll'
        build(path, mutation, 'level_header')
        self.library = ctypes.CDLL(str(path))
        self.core = self.library.lmn_apply_level_header_core
        self.core.argtypes = [MEM, ctypes.c_uint16, ctypes.c_uint16,
                              ctypes.POINTER(fixture.RasterBus)]
        self.core.restype = NativeResult
        self.adapter = self.library.lmn_apply_level_header_adapter
        self.adapter.argtypes = [MEM, ctypes.POINTER(Regs),
                                 ctypes.POINTER(fixture.RasterBus)]
        self.adapter.restype = None

    def release(self):
        self.core = None
        self.adapter = None
        self.library = None
        gc.collect()


class NativeBus:
    """Raster callback bridge with an 86-event hard cap (87th call fails)."""
    def __init__(self, device, label):
        self.device = device
        self.label = label
        self.calls = 0

        def guard():
            if self.calls >= CALLBACK_LIMIT:
                fixture.exit_worker(fixture.NATIVE_GUARD_EXIT,
                                    f'{label}: callback cap {CALLBACK_LIMIT} exhausted')
            self.calls += 1

        def fail(error, operation):
            fixture.exit_worker(fixture.NATIVE_CALLBACK_EXIT,
                f'{label}: {operation} callback failed: {type(error).__name__}: {error}')

        @fixture.READ
        def read(_context, _memory, address, flags):
            guard()
            try:
                address &= 0xfffff
                value = self.device.vga.read(self.device.memory, address, flags)
                self.device.events.add('read', address, value, flags)
                if len(self.device.vga.trace) > CALLBACK_LIMIT:
                    fixture.exit_worker(fixture.NATIVE_GUARD_EXIT,
                                        f'{label}: VGA trace cap exhausted')
                self.device.check(label + ' read')
                return value
            except BaseException as error:
                fail(error, 'read')
                return 0

        @fixture.WRITE
        def write(_context, _memory, address, value, flags):
            guard()
            try:
                address &= 0xfffff
                self.device.vga.write(self.device.memory, address, value, flags)
                self.device.events.add('write', address, value, flags)
                if len(self.device.vga.trace) > CALLBACK_LIMIT:
                    fixture.exit_worker(fixture.NATIVE_GUARD_EXIT,
                                        f'{label}: VGA trace cap exhausted')
                self.device.check(label + ' write')
            except BaseException as error:
                fail(error, 'write')

        @fixture.OUT
        def out(_context, port, value, flags):
            guard()
            try:
                self.device.vga.out(port, value, flags)
                self.device.events.add('out', port, value, flags)
                if len(self.device.vga.trace) > CALLBACK_LIMIT:
                    fixture.exit_worker(fixture.NATIVE_GUARD_EXIT,
                                        f'{label}: VGA trace cap exhausted')
                self.device.check(label + ' out')
            except BaseException as error:
                fail(error, 'out')

        self.read_callback = read
        self.write_callback = write
        self.out_callback = out
        self.bus = fixture.RasterBus(None, read, write, out)


def memory_buffer(memory):
    return (ctypes.c_uint8 * (1 << 20)).from_buffer(memory)


def make_device(memory, case):
    device = contract.TraceDevice(bytearray(memory), 0xA000 + case['seed'],
                                  read_map=0)
    contract.prime_vga_source(device, case)
    return device


def compare_case(native, case, *, check_null=True):
    memory, registers, flags = contract.prepare(case)
    model_device = make_device(memory, case)
    original_device = make_device(memory, case)
    expected_registers, expected_flags, expected_mask, events, view, _shifts = \
        contract.model(case, model_device, registers, flags)

    actual, mask, sites, edges, boundary, _child, _body = contract.original(
        case, original_device, registers, flags, instructions=contract.INS,
        far_calls=set(), continuations=(contract.END,), max_steps=64)
    require(boundary == ('continuation', registers['cs'], contract.END),
            f"{case['name']}: original boundary differs: {boundary!r}")
    require(mask == expected_mask == contract.SHIFT_FLAGS,
            f"{case['name']}: original final flag mask differs")
    require(sites == set(contract.INS),
            f"{case['name']}: original instruction-site set differs")
    require(not edges, f"{case['name']}: unexpected original edges {edges!r}")
    for name, value in expected_registers.items():
        require(actual[name] == value,
                f"{case['name']}: original {name.upper()} differs from model")
    require(((actual['flags'] ^ expected_flags) & expected_mask) == 0,
            f"{case['name']}: original defined flags differ from model")
    require(original_device.memory == model_device.memory,
            f"{case['name']}: original RAM differs from field model")
    require(original_device.vga.state() == model_device.vga.state(),
            f"{case['name']}: original VGA state differs from field model")
    contract.check_bus_trace(case, events, original_device)
    contract.check_vga_trace(case, events, original_device)

    core_device = make_device(memory, case)
    core_bus = NativeBus(core_device, case['name'] + ' core')
    core_result = native.core(memory_buffer(core_device.memory), registers['ds'],
                              flags, ctypes.byref(core_bus.bus))
    core_device.check(case['name'] + ' core')
    native_require(core_result.value == expected_registers['ax'],
            f"{case['name']}: core AX differs")
    native_require(core_result.header_cursor == expected_registers['di'],
            f"{case['name']}: core DI differs")
    native_require(((core_result.flags ^ expected_flags) & expected_mask) == 0,
            f"{case['name']}: core defined flags differ")
    native_require(core_device.memory == original_device.memory,
            f"{case['name']}: core whole RAM differs from original")
    native_require(core_device.vga.state() == original_device.vga.state(),
            f"{case['name']}: core VGA state differs from original")
    compare_native_events(core_device.events, original_device.events,
                          case['name'] + ' core')
    compare_native_vga(case, events, core_device)

    adapter_device = make_device(memory, case)
    adapter_bus = NativeBus(adapter_device, case['name'] + ' adapter')
    state = Regs(**registers, flags=flags)
    native.adapter(memory_buffer(adapter_device.memory), ctypes.byref(state),
                   ctypes.byref(adapter_bus.bus))
    adapter_device.check(case['name'] + ' adapter')
    for name, value in expected_registers.items():
        native_require(getattr(state, name) == value,
                f"{case['name']}: adapter {name.upper()} differs")
    native_require(((state.flags ^ expected_flags) & expected_mask) == 0,
            f"{case['name']}: adapter defined flags differ")
    native_require(adapter_device.memory == original_device.memory,
            f"{case['name']}: adapter whole RAM differs from original")
    native_require(adapter_device.vga.state() == original_device.vga.state(),
            f"{case['name']}: adapter VGA state differs from original")
    compare_native_events(adapter_device.events, original_device.events,
                          case['name'] + ' adapter')
    compare_native_vga(case, events, adapter_device)

    null_checked = False
    if check_null and not (VGA_BASE <= (registers['ds'] << 4) < VGA_END):
        null_memory = bytearray(memory)
        null_result = native.core(memory_buffer(null_memory), registers['ds'],
                                  flags, None)
        native_require(null_result.value == core_result.value and
                null_result.header_cursor == core_result.header_cursor and
                ((null_result.flags ^ core_result.flags) & expected_mask) == 0,
                f"{case['name']}: null-bus core result differs")
        native_require(null_memory == core_device.memory,
                f"{case['name']}: null-bus RAM differs from raster-bus RAM")
        null_checked = True

    return dict(name=case['name'], sites=len(sites), bus_events=len(events),
                vga_events=len(original_device.vga.trace),
                null_ram_path=null_checked, ds=registers['ds'],
                df=case['df'], iff=case['iff'], final_ax=view,
                final_flags=core_result.flags & expected_mask)


def validate_symbols():
    symbols = {row['symbol_name']: row
               for row in read_json(ROOT / 'metadata/symbols.json')}
    expected = {
        'ApplyLevelHeader': contract.START,
        'LevelAfterHeader': contract.END,
        'LoadedLevelRecord': contract.HEADER_OFF,
        'LevelHeaderReleaseSettingWord': 0x0FCB,
        'LevelHeaderCreationLimitWord': 0x0FCD,
        'LevelHeaderWord04': 0x0FCF,
        'LevelHeaderCountdownWord': 0x0FD1,
        'LevelHeaderActionCountWords': 0x0FD3,
        'LevelHeaderViewOriginWord': 0x0FE3,
        'LevelReleaseSettingMinimum': 0x0064,
        'LevelReleaseSetting': 0x0067,
        'LevelCreationLimit': 0x0047,
        'LevelHeaderWord04LowByte': 0x0044,
        'LevelCountdownHighDigit': 0x20A7,
        'LevelViewOriginPixels': 0x0000,
        'LevelViewOriginBytes': 0x0002,
    }
    expected.update({f'LevelActionCount{index}': offset
                     for index, offset in enumerate(
                         (0x006A, 0x006D, 0x0070, 0x0073,
                          0x0076, 0x0079, 0x007C, 0x007F))})
    for name, address in expected.items():
        require(name in symbols and symbols[name]['address'] == address,
                f"symbol ledger {name} address differs from header contract")


def worker(directory):
    REPORT.unlink(missing_ok=True)
    contract.validate_static_extent()
    validate_symbols()
    paths = dependency_paths()
    hashes = {path: sha((ROOT / path).read_bytes()) for path in paths}
    results = []
    mutant_results = []

    baseline = Native(directory)
    try:
        for case in contract.all_cases():
            results.append(compare_case(baseline, case))
            gc.collect()
    finally:
        baseline.release()

    mutation_cases = contract.all_cases()
    for mutation in range(1, 5):
        mutant = Native(directory, mutation)
        detected = None
        try:
            for case in mutation_cases:
                try:
                    compare_case(mutant, case)
                except NativeMismatch as error:
                    detected = dict(case=case['name'],
                                    mismatch=f'{type(error).__name__}: {error}')
                    break
            require(detected is not None,
                    f'mutation {mutation} escaped all completed comparisons')
            mutant_results.append(dict(mutation=mutation,
                                       caught_by_completed_mismatch=detected))
        finally:
            mutant.release()
            gc.collect()

    final_hashes = {path: sha((ROOT / path).read_bytes()) for path in paths}
    require(hashes == final_hashes,
            'level-header test dependency closure changed during execution')
    write_json(REPORT, dict(
        evidence_kind='native-level-header-prefix',
        image='main',
        image_sha256=sha(contract.piece.IMAGE),
        region=dict(start=f'{contract.START:04X}',
                    end_exclusive=f'{contract.END:04X}',
                    decoded_bytes=contract.PREFIX_BYTES,
                    decoded_sites=len(contract.INS),
                    byte_sha256=sha(contract.piece.IMAGE[contract.START:contract.END])),
        case_count=len(results), adapter_case_count=len(results),
        core_boundary_case_count=len(results), cases=results,
        executed_instruction_addresses=sorted(contract.INS),
        translated_code_bytes=contract.PREFIX_BYTES,
        native_code_ranges=[[contract.START, contract.END]],
        branch_edges=[],
        null_ram_case_count=sum(row['null_ram_path'] for row in results),
        callback_limit=CALLBACK_LIMIT,
        mutation_count=len(mutant_results), mutations=mutant_results,
        input_hashes=hashes))
    print(f"native level-header prefix: {len(results)} cases, "
          f"{sum(row['null_ram_path'] for row in results)} null-RAM paths, "
          f"{len(mutant_results)} caught mutations")


def main():
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    if '--worker' in sys.argv:
        worker(sys.argv[sys.argv.index('--worker') + 1])
        return
    with temporary_build_directory(prefix='level-header-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()),
                     '--worker', directory], cwd=ROOT, check=True, timeout=120,
                    memory_mib=512)


if __name__ == '__main__':
    main()

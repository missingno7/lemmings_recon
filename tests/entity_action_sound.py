"""Bounded original-versus-native checks for the two entity sound tails."""
import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
import entity_interactions as interactions
import sound_latches as sound
from minimap_vga import MinimapVga, VGA_BASE

SIZE, MASK = interactions.SIZE, interactions.MASK
FLAGS = interactions.FLAGS
DUAL, EXTERNAL = 0, 1
DUAL_ENTRY, EXTERNAL_ENTRY = 0x31E5, 0x3287
DUAL_STOP, EXTERNAL_STOP = 0x320B, 0x329A
LOW, DUAL_END, EXTERNAL_END = 0x31E5, 0x320C, 0x329B
EVENT_LIMIT, INSTRUCTION_LIMIT = 2048, 512
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 180, 384, 640
GUARD_EXIT, CALLBACK_EXIT = 86, 87
REPORT = BUILD / 'entity-action-sound-differential.json'

IMAGE = interactions.IMAGE
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
OWN_INS = {}
for start, end in ((LOW, DUAL_END), (EXTERNAL_ENTRY, EXTERNAL_END)):
    OWN_INS.update({ins.address: ins for ins in MD.disasm(IMAGE[start:end], start)})
OWN_EDGES = set()
for address, ins in OWN_INS.items():
    if ins.group(capstone.CS_GRP_JUMP) and ins.mnemonic.lower() != 'jmp':
        OWN_EDGES.add((address, ins.operands[0].imm & 0xFFFF))
        OWN_EDGES.add((address, (address + ins.size) & 0xFFFF))
OWN_BYTES = (DUAL_END - LOW) + (EXTERNAL_END - EXTERNAL_ENTRY)
OWN_SITES = len(OWN_INS)
ENTRY_OFFSETS = {DUAL: DUAL_ENTRY, EXTERNAL: EXTERNAL_ENTRY}
STOP_OFFSETS = {DUAL_STOP: 0, EXTERNAL_STOP: 0}

assert OWN_BYTES == 59 and OWN_SITES == 20
assert len(OWN_EDGES) == 12


class ActionCall(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('entry', 'value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags')]


class ActionResult(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in
                ('value', 'map_cursor', 'count', 'auxiliary_value',
                 'record_cursor', 'object_cursor', 'candidate_y',
                 'code_segment', 'data_segment', 'extra_segment',
                 'stack_segment', 'stack_offset', 'flags', 'continuation',
                 'status')]


class ActionAccess(interactions.Access):
    event_limit = EVENT_LIMIT

    def out_word(self, port, value, flags, mask):
        if len(self.events) >= self.event_limit:
            raise interactions.OracleFailure(
                'entity-action-sound callback event budget exhausted')
        if self.device is None or port not in (0x3C4, 0x3CE):
            raise interactions.OracleFailure(
                f'entity-action-sound unexpected OUT {port:04X}')
        self.device.out(port, value, flags)
        self.events.append(('out', port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))


def original(case, memory, regs, device, *, core):
    entry = ENTRY_OFFSETS[case['entry']]
    regs['ip'] = entry
    return interactions.original(
        case, memory, regs, device, False,
        entry_flag_mask=FLAGS,
        main_instructions=OWN_INS,
        stop_offsets=STOP_OFFSETS if core else None,
        access_factory=ActionAccess,
        instruction_limit=INSTRUCTION_LIMIT)


def setup(case):
    memory, regs, device, pc_binding, sound_binding, _ = interactions.setup(case)
    regs['ip'] = ENTRY_OFFSETS[case['entry']]
    if case.get('vga'):
        # Put the live caller RET word into the selected VGA read plane. The
        # interrupt frame and any nested saves then use the same device path.
        if device is None or regs['ss'] != 0xA000:
            raise AssertionError(case['name'] + ': invalid VGA stack fixture')
        device.seq[2] = 0x0F
        device.gc[0] = device.gc[1] = device.gc[3] = device.gc[5] = 0
        device.gc[8] = 0xFF
        address = interactions.physical(regs['ss'], regs['sp'])
        offset = (address - VGA_BASE) & 0xFFFF
        ret = case.get('outer_return', interactions.OUTER_RETURN)
        device.planes[0][offset] = ret & 0xFF
        device.planes[0][(offset + 1) & 0xFFFF] = ret >> 8
    return memory, regs, device, pc_binding, sound_binding


def _matrix_rows():
    rows = []
    options = (0x00, 0x01, 0x02, 0x03, 0x80, 0xFF)
    enabled_values = (0x00, 0x01, 0xFE, 0xFF)
    for entry, label in ((DUAL, 'dual'), (EXTERNAL, 'external')):
        for enabled in enabled_values:
            for option in options:
                rows.append(dict(
                    name=f'{label}-matrix-enabled-{enabled:02x}-options-{option:02x}',
                    entry=entry, enabled=enabled, options=option))
    return rows


def cases():
    rows = _matrix_rows()
    rows.extend([
        dict(name='dual-live-returned-ds-registers', entry=DUAL,
             enabled=0, options=1, provider='pc-registers',
             provider_ds=0x6200, provider_si=0x7070, provider_cx=0x3131,
             provider_enabled=0xFF, provider_options=3),
        dict(name='dual-pc-changed-iret-to-external-ret', entry=DUAL,
             enabled=0, options=1, provider='pc-interrupt-return',
             provider_return=EXTERNAL_STOP),
        dict(name='dual-sound-changed-iret-to-external-ret', entry=DUAL,
             enabled=0xFF, options=3, provider='sound-interrupt-return',
             provider_return=EXTERNAL_STOP),
        dict(name='external-sound-changed-iret-to-dual-ret', entry=EXTERNAL,
             enabled=0xFF, options=3, provider='sound-interrupt-return',
             provider_return=DUAL_STOP),
        dict(name='dual-pc-changed-child-ret', entry=DUAL,
             enabled=0, options=1, provider='pc-child-return',
             provider_return=EXTERNAL_STOP),
        dict(name='dual-pc-unbound-vector', entry=DUAL,
             enabled=0, options=1, pc_vector=(0x0182, 0x6200)),
        dict(name='dual-pc-unbound-binding', entry=DUAL,
             enabled=0, options=1, pc_binding=False),
        dict(name='dual-pc-untranslated-target', entry=DUAL,
             enabled=0, options=1, pc_table_target=0x01B3),
        dict(name='dual-sound-unbound-vector', entry=DUAL,
             enabled=0xFF, options=3, sound_vector=(0, 0x6200)),
        dict(name='external-sound-unbound-binding', entry=EXTERNAL,
             enabled=0xFF, options=3, sound_binding=False),
        dict(name='external-tandy-service', entry=EXTERNAL,
             enabled=0xFF, options=3, driver='tandysnd'),
        dict(name='dual-pc-df-set', entry=DUAL, enabled=0, options=1,
             flags=0x04D7),
        dict(name='dual-sound-df-set', entry=DUAL, enabled=0xFF, options=3,
             flags=0x04D7),
        dict(name='dual-nonzero-load-segment', entry=DUAL,
             enabled=0xFF, options=0, load=0x1213),
        dict(name='external-physical-stack-word-wrap', entry=EXTERNAL,
             enabled=0x01, options=0, ss=0xFFFF, sp=0x000F),
        dict(name='dual-pc-wrapped-stack-segment', entry=DUAL,
             enabled=0, options=1, ss=0xFFFF, sp=0x000F),
        dict(name='dual-vga-interrupt-stack', entry=DUAL,
             enabled=0, options=3, ss=0xA000, sp=0x0800, vga=True),
        dict(name='external-vga-ret-stack', entry=EXTERNAL,
             enabled=0xFF, options=0, ss=0xA000, sp=0x0400, vga=True),
        dict(name='dual-ds-global-stack-alias', entry=DUAL,
             enabled=0, options=0, ds=0x5000, ss=0x5000, sp=0x2010,
             outer_return=0x0000),
        dict(name='dual-entry-segment-wrap', entry=DUAL,
             enabled=0xFF, options=0, load=0xFFFF),
    ])
    return rows


def expected_calls(case, observed):
    entry = case['entry']
    enabled = case.get('enabled', 0)
    options = case.get('options', 0)
    pc_call = entry == DUAL and enabled != 0xFF and bool(options & 1)
    second_enabled = enabled
    second_options = options
    if case.get('provider') == 'pc-registers':
        second_enabled = case.get('provider_enabled', 0xFF)
        second_options = case.get('provider_options', 3)
    sound_call = second_enabled == 0xFF and bool(second_options & 3)
    if case.get('provider') == 'pc-interrupt-return':
        # The changed IRET target terminates at the PC return seam before the
        # dual tail evaluates its second gate.
        sound_call = False
    return pc_call, sound_call


def expected_status(case):
    if case.get('provider') == 'pc-child-return':
        return 3
    if case.get('provider') in ('pc-interrupt-return',
                                'sound-interrupt-return'):
        return 4
    if (case.get('pc_binding') is False or case.get('sound_binding') is False or
            case.get('pc_vector') is not None or case.get('sound_vector') is not None):
        return 1
    if case.get('pc_table_target') is not None:
        return 2
    return 0


def case_record(case, expected, core):
    own_sites = {address for source, address in expected['sites']
                 if source == 'main' and address in OWN_INS}
    own_edges = {(source_ip, target)
                 for source, source_ip, target in expected['edges']
                 if source == 'main' and source_ip in OWN_INS}
    return dict(name=case['name'], entry=case['entry'], core=core,
                status=expected['status'], continuation=expected['continuation'],
                sites=sorted(own_sites), edges=[list(e) for e in sorted(own_edges)],
                event_count=len(expected['events']), steps=expected['steps'],
                providers=sorted(expected['used']))


def original_only():
    before = input_hashes()
    cases_seen, all_sites, all_edges = [], set(), set()
    for case in cases():
        memory, regs, device, _, _ = setup(case)
        pc_call, sound_call = expected_calls(case, {})
        for core in (True, False):
            expected = original(case, bytearray(memory), dict(regs),
                                copy.deepcopy(device), core=core)
            want = expected_status(case)
            interactions.oracle_require(expected['status'] == want,
                f"{case['name']}: original status {expected['status']} != {want}")
            pc_seen = ('main', 0x31F6) in expected['sites']
            sound_site = 0x3209 if case['entry'] == DUAL else 0x3298
            sound_seen = ('main', sound_site) in expected['sites']
            interactions.oracle_require(pc_seen == pc_call,
                case['name'] + ': PC gate did not take its planned path')
            interactions.oracle_require(sound_seen == sound_call,
                case['name'] + ': external gate did not take its planned path')
            if case.get('provider'):
                provider_key = ('pc' if case['provider'] in
                                ('pc-registers', 'pc-child-return',
                                 'pc-interrupt-return') else 'sound')
                interactions.oracle_require(provider_key in expected['used'],
                    case['name'] + ': requested live provider did not fire')
            row = case_record(case, expected, core)
            cases_seen.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
    interactions.oracle_require(all_sites == set(OWN_INS),
        f'original sound-tail site coverage {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'original sound-tail edge coverage {len(all_edges)}/{len(OWN_EDGES)}')
    interactions.oracle_require(before == input_hashes(),
                                'sound-tail inputs changed during original preflight')
    print(f'PASS original entity action sound: {len(cases())} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} edges', flush=True)


def worker_fail(code, error):
    try:
        os.write(2, (str(error) + '\n').encode('utf-8', errors='backslashreplace'))
    finally:
        os._exit(code)


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'entity-action-sound-m{mutation}.dll',
                     mutation, 'entity_action_sound')
        self.lib = ct.CDLL(str(path))
        self.core = self.lib.lmn_entity_action_sound_core
        self.core.argtypes = [interactions.MEM, ct.POINTER(ActionCall),
                              ct.POINTER(interactions.PcBinding),
                              ct.POINTER(interactions.SoundBinding),
                              ct.POINTER(interactions.Bus)]
        self.core.restype = ActionResult
        self.adapter = self.lib.lmn_entity_action_sound_adapter
        self.adapter.argtypes = [interactions.MEM,
                                 ct.POINTER(interactions.Regs), ct.c_uint16,
                                 ct.POINTER(interactions.PcBinding),
                                 ct.POINTER(interactions.SoundBinding),
                                 ct.POINTER(interactions.Bus)]
        self.adapter.restype = ct.c_uint16

    def run(self, case, initial, initial_regs, initial_device,
            pc_binding, sound_binding, *, core):
        memory = bytearray(initial)
        device = copy.deepcopy(initial_device)
        access = ActionAccess(case, memory, dict(initial_regs), device)

        def read(_context, _memory, address, flags):
            try:
                return access.access('read', address, flags, FLAGS)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access('write', address, flags, FLAGS, value)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags, FLAGS)
            except BaseException as error:
                worker_fail(GUARD_EXIT if 'budget' in str(error) else CALLBACK_EXIT,
                            error)

        callbacks = (interactions.READ(read), interactions.WRITE(write),
                     interactions.OUT(out))
        bus = interactions.Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        regs = interactions.Regs(**initial_regs)
        pc = ct.byref(pc_binding) if pc_binding is not None else None
        sound_binding_ptr = (ct.byref(sound_binding)
                             if sound_binding is not None else None)
        if core:
            call = ActionCall(
                case['entry'], initial_regs['ax'], initial_regs['bx'],
                initial_regs['cx'], initial_regs['dx'], initial_regs['si'],
                initial_regs['di'], initial_regs['bp'], initial_regs['cs'],
                initial_regs['ds'], initial_regs['es'], initial_regs['ss'],
                initial_regs['sp'], initial_regs['flags'])
            result = self.core(ram, ct.byref(call), pc, sound_binding_ptr,
                               ct.byref(bus))
            regs.ax, regs.bx, regs.cx, regs.dx = (
                result.value, result.map_cursor, result.count,
                result.auxiliary_value)
            regs.si, regs.di, regs.bp = (result.record_cursor,
                                         result.object_cursor,
                                         result.candidate_y)
            regs.cs, regs.ds, regs.es = (result.code_segment,
                                         result.data_segment,
                                         result.extra_segment)
            regs.ss, regs.sp, regs.flags, regs.ip = (
                result.stack_segment, result.stack_offset, result.flags,
                result.continuation)
            status = result.status
        else:
            status = self.adapter(ram, ct.byref(regs), case['entry'], pc,
                                  sound_binding_ptr, ct.byref(bus))
        return dict(memory=bytes(memory),
                    regs={name: getattr(regs, name)
                          for name in interactions.REG_NAMES},
                    device=device, events=access.events,
                    providers=set(access.used), status=status,
                    continuation=regs.ip)


def compare_events(label, actual, expected):
    interactions.require(len(actual) == len(expected),
        f'{label}: ordered bus events {len(actual)}/{len(expected)}')
    for index, (got, ref) in enumerate(zip(actual, expected)):
        interactions.require(got[:3] == ref[:3],
            f'{label}: event {index} {got[:3]!r}/{ref[:3]!r}')
        interactions.require(((got[3] ^ ref[3]) & ref[4]) == 0,
            f'{label}: event {index} FLAGS {got[3]:04X}/{ref[3]:04X} '
            f'under {ref[4]:04X}')


def compare_case(native, case, *, core):
    memory, regs, device, pc_binding, sound_binding = setup(case)
    label = case['name'] + (' core' if core else ' adapter')
    expected = original(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    actual = native.run(case, bytearray(memory), dict(regs),
                        copy.deepcopy(device), pc_binding, sound_binding,
                        core=core)
    interactions.require(actual['status'] == expected['status'],
        f'{label}: status {actual["status"]}/{expected["status"]}')
    interactions.require(actual['continuation'] == expected['continuation'],
        f'{label}: continuation {actual["continuation"]:04X}/'
        f'{expected["continuation"]:04X}')
    for name in interactions.REG_NAMES:
        if name == 'flags':
            continue
        interactions.require(actual['regs'][name] == expected['regs'][name],
            f'{label}: {name} {actual["regs"][name]:04X}/'
            f'{expected["regs"][name]:04X}')
    flag_mask = expected['flag_mask']
    interactions.require(((actual['regs']['flags'] ^ expected['regs']['flags']) &
                          flag_mask) == 0,
        f'{label}: FLAGS {actual["regs"]["flags"]:04X}/'
        f'{expected["regs"]["flags"]:04X} under {flag_mask:04X}')
    interactions.require(actual['memory'] == expected['memory'],
                         label + ': full 1 MiB RAM differs')
    compare_events(label, actual['events'], expected['events'])
    interactions.require(actual['providers'] == expected['used'],
        f'{label}: provider effects {actual["providers"]}/{expected["used"]}')
    if expected['device'] is not None:
        interactions.require(actual['device'].state() == expected['device'].state(),
                              label + ': VGA registers/planes/latches differ')
        got_trace = [(a, b, c) for a, b, c, _ in actual['device'].trace]
        ref_trace = [(a, b, c) for a, b, c, _ in expected['device'].trace]
        interactions.require(got_trace == ref_trace, label + ': VGA trace differs')
    return case_record(case, expected, core)


MUTATION_WITNESSES = {
    1: ('dual-matrix-enabled-00-options-01', True),
    2: ('dual-matrix-enabled-00-options-02', True),
    3: ('dual-live-returned-ds-registers', True),
    4: ('dual-matrix-enabled-ff-options-03', True),
    5: ('external-matrix-enabled-ff-options-02', True),
    6: ('dual-live-returned-ds-registers', True),
    7: ('dual-pc-changed-iret-to-external-ret', True),
    8: ('dual-matrix-enabled-ff-options-00', False),
}


def input_hashes():
    paths = [
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/entity-actions.md',
        'src/game_code.asm', 'src/program.asm',
        'src/sound/pcspeaker.asm', 'src/sound/adlib.asm',
        'src/sound/tandysnd.asm', 'assets/vgalemmi.exe', 'assets/main.dat',
        'assets/adlib.dat', 'assets/tandysnd.dat', 'metadata/oracle.json',
        'metadata/symbols.json', 'metadata/inputs.json', 'metadata/regions.json',
        'metadata/hints.json', 'metadata/toolchain-lock.json',
        'metadata/sound-oracle.json', 'metadata/pcspeaker-encodings.json',
        'metadata/pcspeaker-producers.json', 'metadata/pcspeaker-regions.json',
        'metadata/pcspeaker-symbols.json', 'metadata/adlib-symbols.json',
        'metadata/tandysnd-symbols.json', 'requirements.txt',
        'c/entity_action_sound.c', 'c/entity_action_sound.h',
        'c/pcspeaker_interrupt.c', 'c/pcspeaker_interrupt.h',
        'c/pcspeaker_dispatch.c', 'c/pcspeaker_dispatch.h',
        'c/pcspeaker.c', 'c/pcspeaker.h', 'c/sound_interrupt.c',
        'c/sound_interrupt.h', 'c/sound_latches.c', 'c/sound_latches.h',
        'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h',
        'c/pcspeaker_sym.h', 'c/sound_latches_sym.h',
        'tests/entity_action_sound.py', 'tests/entity_interactions.py',
        'tests/pcspeaker_dispatch.py', 'tests/sound_latches.py',
        'tests/minimap_vga.py', 'tests/pcspeaker_interrupt.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/common.py',
        'tools/coverage.py',
        'tools/resources.py', 'tools/unpack.py', 'tools/difftest.py',
    ]
    return {name: sha((ROOT / name).read_bytes()) for name in sorted(set(paths))}


def worker(directory):
    before = input_hashes()
    specs = cases()
    by_name = {case['name']: case for case in specs}
    baseline = Native(directory, 0)
    rows, all_sites, all_edges = [], set(), set()
    total_events = total_steps = 0
    for case in specs:
        for core in (True, False):
            row = compare_case(baseline, case, core=core)
            rows.append(row)
            all_sites.update(row['sites'])
            all_edges.update(tuple(edge) for edge in row['edges'])
            total_events += row['event_count']
            total_steps += row['steps']
    interactions.oracle_require(all_sites == set(OWN_INS),
        f'native entity-action-sound site coverage {len(all_sites)}/{len(OWN_INS)}')
    interactions.oracle_require(all_edges == OWN_EDGES,
        f'native entity-action-sound edge coverage {len(all_edges)}/{len(OWN_EDGES)}')
    del baseline
    gc.collect()

    mutations = []
    for mutation, (name, core) in MUTATION_WITNESSES.items():
        mutant = Native(directory, mutation)
        case = by_name[name]
        try:
            compare_case(mutant, case, core=core)
        except interactions.Mismatch as error:
            mutations.append(dict(id=mutation, witness=name, core=core,
                                  mismatch=str(error), completed=True))
        else:
            raise AssertionError(f'entity-action-sound mutant {mutation} survived')
        del mutant
        gc.collect()
    interactions.oracle_require(len(mutations) == 8,
                                'entity-action-sound mutation witness count changed')
    interactions.oracle_require(before == input_hashes(),
        'entity-action-sound inputs changed during bounded native campaign')
    write_json(REPORT, dict(
        image='main', image_sha256=sha(IMAGE),
        code_ranges=[[LOW, DUAL_END], [EXTERNAL_ENTRY, EXTERNAL_END]],
        translated_code_bytes=OWN_BYTES, instruction_sites=OWN_SITES,
        own_static_branch_edges=len(OWN_EDGES),
        parent_feasible_branch_edges=len(all_edges), case_count=len(specs),
        core_adapter_comparisons=len(rows), mutation_count=len(mutations),
        mutations=mutations, executed_instruction_addresses=sorted(all_sites),
        static_instruction_addresses=sorted(OWN_INS),
        branch_edges=[list(edge) for edge in sorted(all_edges)],
        static_branch_edges=[list(edge) for edge in sorted(OWN_EDGES)],
        total_bus_events=total_events, original_instruction_hook_steps=total_steps,
        cases=rows, input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    original_instruction_limit=INSTRUCTION_LIMIT,
                    ordered_bus_event_limit=EVENT_LIMIT,
                    callback_budget_exit=GUARD_EXIT, callback_error_exit=CALLBACK_EXIT),
        domain='The 31E5 dual PC/external feedback gate and 3287 external-only '
               '0412 service tail. Original execution compares the complete 1 MiB '
               'RAM, all registers, defined FLAGS, ordered bus events, live vector '
               'and interrupt return words, and VGA device state where a stack frame '
               'uses the VGA aperture. Core checks stop before 320B/329A; adapter '
               'checks execute the live outer RET. The 48-case matrix uses enable '
               'bytes 00/01/FE/FF and option bytes 00/01/02/03/80/FF at each entry; '
               'additional fixtures cover returned DS/registers, changed returns, '
               'unbound and untranslated child paths, DF, stack wrapping and VGA.' ))
    print(f'PASS entity action sound: {len(specs)} fixtures x core/adapter, '
          f'{len(all_sites)} sites/{len(all_edges)} edges, {total_events} events, '
          f'{len(mutations)} completed mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        result = run_bounded([sys.executable, str(Path(__file__).resolve()),
                              '--original-worker'], cwd=ROOT,
                             timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB,
                             check=True)
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        return
    if sys.argv[1:] == ['--original-worker']:
        original_only()
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_action_sound.py [--original-only | --worker DLL_DIRECTORY]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-action-sound-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()

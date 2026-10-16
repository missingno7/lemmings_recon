"""Focused SelectEntityCandidate-to-DispatchEntityAction handoff checks.

The producer is executed through its real adapter RET. Its resulting RAM and
registers are then passed directly to the dispatcher, with the call at 01C5
represented by its actual return word 01C8. The intervening 3AC8 routine is
outside this handoff domain; this is not full main-loop acceptance.
"""
from __future__ import annotations

import copy
import gc
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
from bounded_process import run_bounded, temporary_build_directory
from common import BUILD, sha, write_json
import entity_action_dispatch as dispatch
import entity_interactions as interactions
import entity_select as selection

SIZE, MASK = interactions.SIZE, interactions.MASK
FLAGS = interactions.FLAGS
ENTRY, MAIN_CALL_RETURN = dispatch.ENTRY, 0x01C8
PRODUCER_CALL_RETURN = 0x01C2
WORKER_SECONDS, PROCESS_MIB, TREE_MIB = 240, 384, 640
REPORT = BUILD / 'entity-select-actions-differential.json'
ORIGINAL_REPORT = BUILD / 'entity-select-actions-original-differential.json'


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def get16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MASK] << 8)


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def put16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & MASK] = (value >> 8) & 0xFF


def cases():
    rows = [
        dict(name='preferred-selector-2', selector=2, button=1,
             preferred_index=0),
        dict(name='forced-alternate-selector-2', selector=2, button=3,
             preferred_index=0),
        dict(name='preferred-selector-3', selector=3, button=1,
             preferred_index=0),
        dict(name='forced-alternate-selector-4', selector=4, button=3,
             preferred_index=0),
    ]
    for index, case in enumerate(rows):
        case.update(bound=2, x=0x20, xdelta=0x70, y=0x78,
                    screen_x=0x80, screen_y=0x80,
                    hits={0: {'entity_flags': 0x80, 'state': 0,
                              'byte25': 0},
                          1: {'entity_flags': 0, 'state': 0,
                              'byte25': 0}},
                    extra_records={}, outer_return=PRODUCER_CALL_RETURN,
                    seed=0xA3150000 + index * 701,
                    flags=0x02D7, enabled=0, options=0,
                    update_gate=0, work_guard=0, latch=0,
                    candidate_count=2, input_word=case['button'])
        case.update(ds=selection.DATA_SEG, es=0x6200, ss=0x5000, sp=0xD000,
                    selected=0x7777, selected_index=0x66,
                    preferred=0x8888, preferred_index=0x55,
                    alternate=0x9999, alternate_index=0x44,
                    count=0x22, present=0x7E, output=b'KEEP-THIS!!',
                    extra_records={})
    return rows


def seed_action_state(memory, regs, case):
    """Make both possible producer results eligible for the chosen action."""
    ds = regs['ds']
    for selector, offset in dispatch.ACTION_COUNT_OFFSETS.items():
        put8(memory, ds, offset, int(selector == case['selector']))
    for offset in (0x6C, 0x6F, 0x72):
        put8(memory, ds, offset, 0x5A)
    put8(memory, ds, 0x2B, case['update_gate'])
    put8(memory, ds, 0x50, case['work_guard'])
    put8(memory, ds, 0x61, case['latch'])
    put8(memory, ds, 0x82, case['selector'])

    # These fields are read only after the producer has selected a live SI.
    # Preserve the high flag bit which determines the preferred bucket while
    # keeping selector 2's tested low bit clear.
    for index, pointer in enumerate((selection.record_offset(0),
                                     selection.record_offset(1))):
        put16(memory, ds, pointer + 8, 0)
        put8(memory, ds, pointer + 0x24, 0x80 if index == 0 else 0)
        put8(memory, ds, pointer + 0x25, 0)
        put8(memory, ds, pointer + 0x20, 0)


def action_call_frame(memory, regs):
    """Set the real 01C5 near-CALL frame before entering 3150h."""
    out_memory = bytearray(memory)
    out_regs = dict(regs)
    sp = (out_regs['sp'] - 2) & 0xFFFF
    put16(out_memory, out_regs['ss'], sp, MAIN_CALL_RETURN)
    out_regs['sp'] = sp
    out_regs['ip'] = ENTRY
    return out_memory, out_regs


def check_regs(label, actual, expected, flag_mask):
    for name in interactions.REG_NAMES:
        if name == 'flags':
            continue
        interactions.require(actual[name] == expected[name],
            f'{label}: {name} {actual[name]:04X}/{expected[name]:04X}')
    interactions.require(((actual['flags'] ^ expected['flags']) & flag_mask) == 0,
        f'{label}: FLAGS {actual["flags"]:04X}/{expected["flags"]:04X} '
        f'under {flag_mask:04X}')


def compare_completed(label, actual, expected, flag_mask):
    interactions.require(actual['status'] == expected['status'],
        f'{label}: status {actual["status"]}/{expected["status"]}')
    interactions.require(actual['continuation'] == expected['continuation'],
        f'{label}: continuation {actual["continuation"]:04X}/'
        f'{expected["continuation"]:04X}')
    check_regs(label, actual['regs'], expected['regs'], flag_mask)
    interactions.require(actual['memory'] == expected['memory'],
                         label + ': full 1 MiB RAM differs')
    dispatch.compare_events(label, actual['events'], expected['events'])
    interactions.require(actual.get('providers', actual.get('used', set())) ==
                         expected['used'],
                         label + ': provider effects differ')
    interactions.require(actual['device'] is None and expected['device'] is None,
                         label + ': unexpected VGA device in this RAM domain')


def prepare_original(case, producer):
    memory, regs = action_call_frame(producer['memory'], producer['regs'])
    dispatch_case = dict(case, outer_return=MAIN_CALL_RETURN,
                         input_word=case['button'], candidate_count=2)
    return dispatch_case, memory, regs


def run_dispatch_original(case, producer, *, core):
    dispatch_case, memory, regs = prepare_original(case, producer)
    observed = interactions.original(
        dispatch_case, memory, regs, None, core,
        entry_flag_mask=producer['flag_mask'],
        main_instructions=dispatch.COMPOSED_INS,
        access_factory=dispatch.DispatchAccess,
        instruction_limit=dispatch.INSTRUCTION_LIMIT)
    dispatch.assert_original_path(dispatch_case, observed, core=core)
    dispatch.assert_prefix_effects(dispatch_case, regs, observed)
    return observed, bytes(memory)


def expected_record_pointer(case):
    return selection.record_offset(0 if case['button'] & 2 == 0 else 1)


def assert_handoff_contract(case, producer):
    ds = producer['regs']['ds']
    pointer = expected_record_pointer(case)
    index = 0 if case['button'] & 2 == 0 else 1
    interactions.oracle_require(get8(producer['memory'], ds, 0x0063) == 2,
        case['name'] + ': producer did not expose both live candidates')
    interactions.oracle_require(get8(producer['memory'], ds, 0x005E) == index and
                                get16(producer['memory'], ds, 0x0058) == pointer,
        case['name'] + ': producer selected the wrong bucket record')
    interactions.oracle_require(get8(producer['memory'], ds, 0x001A) == 0xFF,
        case['name'] + ': producer did not publish a selected candidate')


def assert_action_contract(case, observed, before_memory, *, core):
    ds = observed['regs']['ds']
    pointer = expected_record_pointer(case)
    other = selection.record_offset(1 if pointer == selection.record_offset(0) else 0)
    selector = case['selector']
    interactions.oracle_require(observed['status'] == 0,
        case['name'] + ': dispatcher did not complete basic action')
    if core:
        interactions.oracle_require(observed['continuation'] in dispatch.MAIN_RETURNS,
            case['name'] + ': dispatcher core did not stop before a known RET')
    else:
        interactions.oracle_require(observed['continuation'] == MAIN_CALL_RETURN,
            case['name'] + ': actual dispatcher CALL did not return to 01C8')
    interactions.oracle_require(get8(observed['memory'], ds,
                                      dispatch.ACTION_COUNT_OFFSETS[selector]) == 0,
        case['name'] + ': selected action counter was not decremented')
    if selector == 2:
        interactions.oracle_require(get8(observed['memory'], ds, pointer + 0x24) == 1,
                                    case['name'] + ': selector 2 latch was not replaced')
    elif selector == 3:
        interactions.oracle_require(get8(observed['memory'], ds, pointer + 0x25) == 0xFF and
                                    get8(observed['memory'], ds, 0x6F) == 0,
            f'{case["name"]}: selector 3 marker/refresh not updated '
            f'(ptr={pointer:04X}, marker={get8(observed["memory"], ds, pointer + 0x25):02X}, '
            f'refresh={get8(observed["memory"], ds, 0x6F):02X}, '
            f'action_count={get8(observed["memory"], ds, 0x6D):02X})')
    else:
        interactions.oracle_require(get8(observed['memory'], ds, pointer + 0x20) == 0x4F and
                                    get8(observed['memory'], ds, 0x72) == 0,
                                    case['name'] + ': selector 4 flag/refresh not updated')
    interactions.oracle_require(
        observed['memory'][physical(ds, other):physical(ds, other) + 0x2D] ==
        before_memory[physical(ds, other):physical(ds, other) + 0x2D],
        case['name'] + ': action changed the unselected record')


def producer_oracle(case, initial, regs, device):
    expected = selection.original(case, bytearray(initial), dict(regs),
                                  copy.deepcopy(device), core=False)
    selection.assert_independent(case, initial, regs, expected, core=False)
    interactions.oracle_require(expected['status'] == 0 and
                                expected['continuation'] == PRODUCER_CALL_RETURN,
        case['name'] + ': producer adapter missed its actual caller return')
    assert_handoff_contract(case, expected)
    return expected


def compare_producer(label, actual, expected):
    interactions.require(actual['status'] == expected['status'],
        f'{label}: producer status {actual["status"]}/{expected["status"]}')
    interactions.require(actual['continuation'] == expected['continuation'],
        f'{label}: producer continuation {actual["continuation"]:04X}/'
        f'{expected["continuation"]:04X}')
    check_regs(label + ' producer', actual['regs'], expected['regs'],
               expected['flag_mask'])
    interactions.require(actual['memory'] == expected['memory'],
                         label + ': producer full RAM differs')
    selection.compare_events(label + ' producer', actual['events'],
                             expected['events'])
    interactions.require(actual['used'] == expected['used'],
                         label + ': producer providers differ')
    interactions.require(actual['device'] is None and expected['device'] is None,
                         label + ': unexpected producer VGA device')


def dispatch_original_row(case, observed, core):
    sites = {address for source, address in observed['sites']
             if source == 'main' and address in dispatch.COMPOSED_INS}
    edges = {(source_ip, target) for source, source_ip, target in observed['edges']
             if source == 'main' and source_ip in dispatch.COMPOSED_CONDITIONALS}
    return dict(name=case['name'], core=core,
                sites=sorted(sites), edges=[list(edge) for edge in sorted(edges)],
                status=observed['status'], continuation=observed['continuation'],
                events=len(observed['events']), steps=observed['steps'])


def case_execution(case, selection_native=None, dispatch_native=None, *, native=False):
    initial, initial_regs, device = selection.setup(case)
    seed_action_state(initial, initial_regs, case)
    expected_producer = producer_oracle(case, initial, initial_regs, device)
    if native:
        actual_producer = selection_native.run(case, initial, initial_regs,
                                               device, core=False)
        compare_producer(case['name'], actual_producer, expected_producer)
        assert_handoff_contract(case, actual_producer)
        producer_for_native = actual_producer
    else:
        actual_producer = None
        producer_for_native = None

    rows = []
    expected_outcomes = []
    for core in (True, False):
        expected, expected_pre_memory = run_dispatch_original(
            case, expected_producer, core=core)
        assert_action_contract(case, expected, expected_pre_memory, core=core)
        row = dispatch_original_row(case, expected, core)
        expected_outcomes.append(expected)
        if native:
            dispatch_case, mem, regs = prepare_original(case, producer_for_native)
            actual = dispatch_native.run(dispatch_case, bytearray(mem), dict(regs),
                None, None, None, core=core)
            compare_completed(case['name'] + (' core' if core else ' adapter'),
                              actual, expected, expected['flag_mask'])
            assert_action_contract(case, actual, bytes(mem), core=core)
            if core:
                entry, child_status = dispatch.expected_child(dispatch_case, expected)
                interactions.require(actual['child_entry'] == entry,
                    case['name'] + ': native dispatcher child entry differs')
                interactions.require(actual['child_status'] == child_status,
                    case['name'] + ': native dispatcher child status differs')
                interactions.oracle_require(entry == dispatch.ACTION_ENTRIES[
                    case['selector']] and child_status == 0,
                    case['name'] + ': original selected an unexpected child')
            row['native_events'] = len(actual['events'])
        rows.append(row)
    return dict(producer=expected_producer, actual_producer=actual_producer,
                dispatch_rows=rows, dispatch_outcomes=expected_outcomes)


def input_hashes():
    paths = set(selection.input_hashes()) | set(dispatch.input_hashes())
    paths.update(('src/entry_services.asm', 'tests/entity_select_actions.py'))
    missing = sorted(path for path in paths if not (ROOT / path).is_file())
    interactions.oracle_require(not missing,
        'entity-select-actions hash inputs missing: ' + repr(missing))
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def original_campaign(before):
    interactions.oracle_require(before == input_hashes(),
        'entity-select-actions inputs changed before original preflight')
    rows, sites, edges = [], set(), set()
    producer_sites, producer_edges = set(), set()
    for case in cases():
        outcome = case_execution(case, native=False)
        producer = outcome['producer']
        producer_sites.update(address for source, address in producer['sites']
                              if source == 'main')
        producer_edges.update((src, dst) for source, src, dst in producer['edges']
                              if source == 'main')
        for row in outcome['dispatch_rows']:
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
    interactions.oracle_require(before == input_hashes(),
        'entity-select-actions inputs changed during original preflight')
    print(f'PASS original SelectEntityCandidate->DispatchEntityAction handoff: '
          f'{len(cases())} fixtures, {len(producer_sites)} producer sites, '
          f'{len(sites)} dispatcher sites/{len(edges)} observed outcomes', flush=True)
    return dict(rows=rows, sites=sites, edges=edges,
                producer_sites=producer_sites, producer_edges=producer_edges)


def worker(directory, before):
    interactions.oracle_require(before == input_hashes(),
        'entity-select-actions inputs changed before native campaign')
    selection_native = selection.Native(directory, 0)
    dispatch_native = dispatch.Native(directory, 0)
    rows, sites, edges = [], set(), set()
    producer_sites, producer_edges = set(), set()
    integrated_sites, integrated_edges = set(), set()
    total_events = total_steps = 0
    for case in cases():
        outcome = case_execution(case, selection_native, dispatch_native, native=True)
        producer = outcome['producer']
        producer_sites.update(address for source, address in producer['sites']
                              if source == 'main')
        producer_edges.update((src, dst) for source, src, dst in producer['edges']
                              if source == 'main')
        for expected, row in zip(outcome['dispatch_outcomes'],
                                  outcome['dispatch_rows']):
            rows.append(row)
            sites.update(row['sites'])
            edges.update(tuple(edge) for edge in row['edges'])
            integrated_sites.update(address for source, address in expected['sites']
                                    if source == 'main')
            integrated_edges.update((src, dst) for source, src, dst in expected['edges']
                                    if source == 'main')
            total_events += len(expected['events'])
            total_steps += expected['steps']
        total_events += len(producer['events'])
        total_steps += producer['steps']
    del selection_native, dispatch_native
    gc.collect()
    interactions.oracle_require(before == input_hashes(),
        'entity-select-actions inputs changed during native campaign')
    all_executed = producer_sites | integrated_sites
    image_sha256 = sha(selection.IMAGE)
    write_json(REPORT, dict(
        image='main', image_sha256=image_sha256,
        code_ranges=[], translated_code_bytes=0, instruction_sites=0,
        own_static_branch_edges=0, case_count=len(cases()),
        producer_adapter_comparisons=len(cases()),
        dispatcher_core_adapter_comparisons=2 * len(cases()),
        mutation_count=0, mutations=[],
        executed_instruction_addresses=sorted(all_executed),
        producer_instruction_addresses=sorted(producer_sites),
        dispatcher_instruction_addresses=sorted(integrated_sites),
        producer_observed_branch_edges=[list(edge)
                                        for edge in sorted(producer_edges)],
        dispatcher_observed_branch_edges=[list(edge) for edge in sorted(edges)],
        integrated_instruction_sites=len(all_executed),
        integrated_dispatcher_branch_edges=[list(edge)
                                            for edge in sorted(integrated_edges)],
        total_bus_events=total_events, original_instruction_hook_steps=total_steps,
        cases=rows, input_hashes=before,
        limits=dict(worker_seconds=WORKER_SECONDS, process_memory_mib=PROCESS_MIB,
                    windows_tree_memory_mib=TREE_MIB,
                    producer_instruction_limit=selection.MAX_INSTRUCTIONS,
                    dispatcher_instruction_limit=dispatch.INSTRUCTION_LIMIT,
                    producer_ordered_bus_event_limit=selection.MAX_EVENTS,
                    dispatcher_ordered_bus_event_limit=dispatch.EVENT_LIMIT,
                    mutation_count=0),
        domain=('Four focused native handoffs run SelectEntityCandidate at 3CDE '
                'through its adapter RET to 01C2, then pass that exact final RAM and '
                'register state into DispatchEntityAction at 3150. The test skips '
                'the intervening 3AC8 routine and creates the actual near-CALL frame '
                'for the dispatch call site 01C5 with return 01C8. Preferred and '
                'forced-alternate buckets reach basic selectors 2, 3 and 4. Full '
                'RAM, all registers, defined FLAGS, ordered callbacks, selected '
                'record mutations and the unselected record are checked. This adds '
                'zero owned code bytes and does not claim full main-loop coverage.')))
    print(f'PASS native SelectEntityCandidate->DispatchEntityAction handoff: '
          f'{len(cases())} fixtures, {len(producer_sites)} producer sites, '
          f'{len(sites)} dispatcher sites/{len(edges)} observed outcomes, '
          f'{total_events} events, {len(all_executed)} integrated sites', flush=True)


def main():
    if sys.argv[1:] == ['--original-only']:
        BUILD.mkdir(exist_ok=True)
        with temporary_build_directory(prefix='entity-select-actions-original-',
                                       parent=BUILD) as directory:
            hash_path = Path(directory) / 'input-hashes.json'
            write_json(hash_path, input_hashes())
            run_bounded([sys.executable, str(Path(__file__).resolve()),
                         '--original-worker', str(hash_path)], cwd=ROOT,
                        timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)
        return
    if len(sys.argv) == 3 and sys.argv[1] == '--original-worker':
        before = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
        original_campaign(before)
        return
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        before = json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))
        worker(sys.argv[2], before)
        return
    if sys.argv[1:]:
        raise SystemExit('usage: entity_select_actions.py [--original-only | --worker DIR HASHFILE]')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-select-actions-', parent=BUILD) as directory:
        hash_path = Path(directory) / 'input-hashes.json'
        before = input_hashes()
        write_json(hash_path, before)
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     str(directory), str(hash_path)], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=PROCESS_MIB, check=True)


if __name__ == '__main__':
    main()

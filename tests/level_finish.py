"""Bounded clear/minimap tail: live saved CX, DS and near-return frames."""
import copy
import ctypes
import gc
import os
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import capstone
import dat_io as oracle
import object_cells_bus as bus_support
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, read_json, write_json
from dat_io_c import MEM, Regs
from minimap_vga import MinimapVga
from unpack import ASSET, unpack, relocated
from unicorn import (Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN, UC_HOOK_INTR)
from unicorn import x86_const as x

IMAGE, META = unpack(ASSET.read_bytes())
SYMS = {r['symbol_name']: r for r in read_json(ROOT / 'metadata/symbols.json')}
ENTRY, END, OWN_RET = 0x3776, 0x378a, 0x3789
DEFINED, ARITH, AF, CF = 0x0fd7, 0x8d5, 16, 1
EVENT_LIMIT, STEP_LIMIT = 200_000, 2_000_000
REPORT = BUILD / 'level-finish-differential.json'
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {i.address: i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
LOCAL = set(INS)
for name in ('ClearLevelDrawingTail', 'ClearVgaBytes', 'UpdateMinimapColumn',
             'AccumulateMinimapRow', 'AccumulateMinimapSample'):
    r = SYMS[name]
    INS.update({i.address: i for i in MD.disasm(IMAGE[r['address']:r['address']+r['size']], r['address'])})
CALLS = {pc: pc + i.size for pc, i in INS.items() if i.mnemonic == 'call'}
RETS = {pc for pc, i in INS.items() if i.mnemonic == 'ret'}
BRANCHES = {pc for pc, i in INS.items() if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
EDGES = {(pc, i.operands[0].imm & 65535) for pc, i in INS.items() if pc in BRANCHES}
EDGES |= {(pc, pc+i.size) for pc, i in INS.items() if pc in BRANCHES and i.mnemonic != 'jmp'}
SOURCES = ('level_finish', 'vga_clear', 'minimap_column', 'minimap_row', 'minimap_sample')


class VerificationFailure(RuntimeError):
    """An original/provider/budget failure must not count as a mutant hit."""


class Mismatch(AssertionError):
    """Only completed comparisons can detect a mutant."""


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in ('code_segment',
        'data_segment', 'stack_segment', 'stack_offset', 'height_state',
        'source_cursor', 'flags')]


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in ('value', 'target_cursor',
        'count', 'port_or_population', 'source_cursor', 'output_cursor',
        'data_segment', 'extra_segment', 'stack_offset', 'flags',
        'continuation', 'changed_return')]


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def field(name):
    return SYMS[name]['address']


def physical(segment, offset):
    return ((segment << 4) + (offset & 65535)) & 0xfffff


def put_word(memory, segment, offset, value):
    p = physical(segment, offset)
    memory[p] = value & 255
    memory[(p+1) & 0xfffff] = value >> 8


def input_hashes():
    paths = {'metadata/symbols.json', 'metadata/oracle.json', 'metadata/toolchain-lock.json',
             'assets/vgalemmi.exe', 'tests/level_finish.py', 'c/lemmings_sym.h',
             'c/minimap_helpers.h', 'c/special_blit.h', 'c/regs.h'}
    paths.update(f'c/{name}.{suffix}' for name in SOURCES for suffix in ('c', 'h'))
    paths.update(bus_support.local_python_import_paths())
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'src').glob('*.asm'))
    return {p: sha((ROOT/p).read_bytes()) for p in sorted(paths)}


def check_hashes(before):
    after = input_hashes()
    if before != after:
        changed = [p for p in set(before)|set(after) if before.get(p) != after.get(p)]
        raise VerificationFailure('Inputs changed during bounded run: '+', '.join(sorted(changed)))


def hard_exit(code, message):
    os.write(2, (message+'\n').encode('utf-8', errors='backslashreplace'))
    os._exit(code)


class NativeBus:
    def __init__(self, memory, device):
        self.events = []
        def record(kind, address, value, flags):
            if len(self.events) >= EVENT_LIMIT:
                hard_exit(86, 'level_finish: native event budget exhausted')
            self.events.append((kind, address, value, flags))
        def read(context, mem, address, flags):
            try:
                address &= 0xfffff
                value = device.read(memory, address, flags)
                record('read', address, value, flags)
                return value
            except BaseException as error:
                hard_exit(87, 'level_finish native read: '+repr(error))
                return 0
        def write(context, mem, address, value, flags):
            try:
                address &= 0xfffff
                device.write(memory, address, value, flags)
                record('write', address, value, flags)
            except BaseException as error:
                hard_exit(87, 'level_finish native write: '+repr(error))
        def output(context, port, value, flags):
            try:
                device.out(port, value, flags)
                record('out', port, value, flags)
            except BaseException as error:
                hard_exit(87, 'level_finish native out: '+repr(error))
        self.callbacks = (bus_support.READ(read), bus_support.WRITE(write), bus_support.OUT(output))
        self.bus = bus_support.RasterBus(None, *self.callbacks)


def next_mask(previous, mask):
    mnemonic = INS[previous].mnemonic
    if mnemonic in ('add', 'sub', 'cmp', 'neg'):
        return mask | ARITH
    if mnemonic in ('and', 'or', 'xor', 'test', 'shl', 'shr'):
        return (mask | ARITH) & ~AF
    if mnemonic in ('inc', 'dec'):
        return mask | (ARITH & ~CF)
    return mask


def original(case, memory, regs, flags, device):
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 1 << 21)
    uc.mem_write(0, bytes(memory)*2)
    for name, register in oracle.REG.items():
        uc.reg_write(register, regs[name])
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    loaded = relocated(IMAGE, META['relocations'], regs['cs'])
    code_values = {physical(regs['cs'], pc+n): loaded[pc+n]
                   for pc, instruction in INS.items() for n in range(instruction.size)}
    if any(memory[p] != value for p, value in code_values.items()):
        raise VerificationFailure(case['name']+': constructed state changed pinned code')
    events, seen, edges, frames = [], set(), set(), []
    state = dict(previous=None, pc=None, flags=flags, mask=DEFINED, done=False,
                 failure=None, steps=0, columns=0, samples=0, boundary=None,
                 changed=False)

    def fail(message):
        state['failure'] = message
        uc.emu_stop()

    def code(cpu, address, size, context):
        pc = (address-(regs['cs'] << 4)) & 65535
        previous = state['previous']
        if previous is not None:
            state['mask'] = next_mask(previous, state['mask'])
        if previous in RETS:
            if not frames and previous != OWN_RET:
                fail(f'Untracked original RET at {previous:04x}')
                return
            expected = frames.pop() if frames else None
            if expected is None or pc != expected:
                state['changed'] = expected is not None
                state['done'] = True
                cpu.emu_stop()
                return
        if previous in BRANCHES:
            edges.add((previous, pc))
        if cpu.reg_read(oracle.REG['cs']) != regs['cs'] or pc not in INS:
            fail(f'{case["name"]}: escaped identified code at {pc:04x}')
            return
        state['steps'] += 1
        if state['steps'] > STEP_LIMIT:
            fail('Original instruction budget exhausted')
            return
        state.update(pc=pc, previous=pc, flags=cpu.reg_read(x.UC_X86_REG_EFLAGS)&65535)
        if pc in CALLS:
            frames.append(CALLS[pc])
        if pc == field('UpdateMinimapColumn'):
            state['columns'] += 1
        if pc == field('AccumulateMinimapSample'):
            state['samples'] += 1
        if pc == OWN_RET:
            if frames:
                fail('Original reached own RET with unconsumed child frames')
                return
            state['boundary'] = dict(memory=bytes(memory), device=device.state(),
                regs={n: cpu.reg_read(r) for n, r in oracle.REG.items()},
                flags=state['flags'], mask=state['mask'], event_count=len(events))
        seen.add(pc)

    def record(kind, address, value):
        if len(events) >= EVENT_LIMIT:
            fail('Original event budget exhausted')
            return False
        events.append((kind, address, value, state['flags'], state['mask'], state['pc']))
        return True

    def access(kind, address, size, value=0):
        try:
            if not 0 <= address < address+size <= 1 << 21:
                fail('Original access escaped mapped memory')
                return
            for n in range(size):
                p = (address+n) & 0xfffff
                if kind == 'read':
                    byte = device.read(memory, p, state['flags'])
                else:
                    byte = (value >> (8*n)) & 255
                    if p in code_values and byte != code_values[p]:
                        fail('Original write modifies executing code')
                        return
                    device.write(memory, p, byte, state['flags'])
                if not record(kind, p, byte):
                    return
                for at in (address+n, p, p+(1 << 20)):
                    if 0 <= at < 1 << 21:
                        uc.mem_write(at, bytes((byte,)))
        except BaseException as error:
            fail('Original provider failure: '+repr(error))

    def read(cpu, access_type, address, size, value, context):
        access('read', address, size)
    def write(cpu, access_type, address, size, value, context):
        access('write', address, size, value)
    def output(cpu, port, size, value, context):
        try:
            if size != 2:
                fail('Original non-word port output')
                return
            device.out(port, value, state['flags'])
            record('out', port, value)
        except BaseException as error:
            fail('Original port provider failure: '+repr(error))
    def interrupt(cpu, number, context):
        fail(f'Unexpected original INT {number:02x}')
    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, read)
    uc.hook_add(UC_HOOK_MEM_WRITE, write)
    uc.hook_add(UC_HOOK_INSN, output, None, 1, 0, x.UC_X86_INS_OUT)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    uc.emu_start(physical(regs['cs'], ENTRY), 0, count=STEP_LIMIT)
    if state['failure'] or not state['done']:
        raise VerificationFailure(state['failure'] or 'Original instruction budget exhausted')
    if bytes(uc.mem_read(0, 1 << 20)) != bytes(memory):
        raise VerificationFailure('Original canonical memory and emulator mirror differ')
    result = dict(memory=bytes(memory), device=device.state(),
        regs={n: uc.reg_read(r) for n, r in oracle.REG.items()},
        flags=uc.reg_read(x.UC_X86_REG_EFLAGS)&65535, mask=state['mask'])
    return dict(after=result, boundary=state['boundary'], events=events, seen=seen, edges=edges,
                columns=state['columns'], samples=state['samples'], changed=state['changed'])


def cases():
    out = []
    def add(name, **values):
        out.append(dict(name=name, seed=len(out), columns=13, **values))
    for column in (0, 192, 200, 0x7fef, 0x7ff0, 0x8000, 0xfff0):
        add(f'column-{column:04x}', column=column)
    add('DF-backward-clear', df=True)
    for sp in (0, 1, 65535):
        add(f'stack-{sp:04x}', sp=sp)
    add('physical-call-word-wrap', ss=65535, sp=0x11)
    # SS:000E=FF08 has high byte atFFFFF; it changes the straddling
    # CALL word's low byte. This is an early clear return, not13 columns.
    out[-1].update(columns=0, expected_return=0x37ff)
    add('physical-outer-return-wrap', ss=65535, sp=0x0f)
    # SS:000C=0F01 changes the CALL low byte atFFFFD to0F;
    # SS:000E=FF08 changes its high byte atFFFFE to08 (observed080F).
    out[-1].update(columns=0, expected_return=0x080f)
    add('data-segment-wrap', ds=65535)
    add('saved-counter-overwrites-graphics-input', alias='graphics-input')
    add('graphics-publication-overwrites-outer-return', alias='graphics-output')
    add('saved-counter-from-CS-scratch', alias='counter')
    out[-1]['columns'] = 1
    add('restored-DS-and-counter-from-CS-scratch', alias='data-counter')
    out[-1]['columns'] = 1
    add('column-return-to-own-RET-boundary', alias='data-counter-return')
    out[-1].update(columns=1, expected_return=OWN_RET)
    add('clear-return-mirror-overwrite', ss=0x7000, sp=10)
    out[-1].update(columns=0, expected_return=0x0f02)
    add('clear-return-VGA-overwrite', ss=0xa000, sp=0xcc42)
    out[-1].update(columns=0, expected_return=0)
    add('minimap-inner-return-VGA', ss=0xa000, sp=0xe000)
    out[-1]['columns'] = 1
    return out


def prepare(case):
    rng = random.Random(0x3776+case['seed'])
    load = (0x1010, 0x1213, 0x2345)[case['seed']%3]
    memory = bytearray(rng.randbytes(1 << 20))
    memory[load << 4:(load << 4)+len(IMAGE)] = relocated(IMAGE, META['relocations'], load)
    regs = {n: rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load, ip=ENTRY, ds=case.get('ds', load+0x9a9),
                ss=case.get('ss', 0x7000), sp=case.get('sp', 0x9000))
    alias = case.get('alias')
    if alias in ('counter', 'data-counter', 'data-counter-return'):
        regs.update(ss=load, sp=field('MinimapColumnBits')+(2 if alias=='counter' else 6))
    elif alias in ('graphics-input', 'graphics-output'):
        regs['ss'] = regs['ds']
        regs['sp'] = field('LevelGraphicsSegment')+2 if alias=='graphics-input' else field('GraphicsResourceSegment')
    flags = 2 | ((case['seed']*0x95)&0xad5) | (0x400 if case.get('df') else 0)
    put_word(memory, regs['ss'], regs['sp'], 0xed00)
    put_word(memory, regs['ds'], field('MinimapSourceColumnByteOffset'), case.get('column', 0))
    put_word(memory, regs['ds'], field('LevelGraphicsSegment'), 0x5100)
    put_word(memory, 0x6000, field('LevelGraphicsSegment'), 0xa55a)
    device = bus_support.configure_vga(memory, case['seed'], read_plane=3, write_mask=15)
    for column in range(0, 208, 16):
        for row in range(20):
            row_bits = (row*37 + column + case['seed']*13) & 255
            for sample in range(8):
                at = (column+0x5740+row*0x680+sample*2)&65535
                word = 65535 if row_bits & (0x80 >> sample) else 0
                device.planes[3][at] = word >> 8
                device.planes[3][(at+1)&65535] = word & 255
    if alias in ('counter', 'data-counter', 'data-counter-return'):
        rows = bytearray(20)
        if alias == 'counter':
            rows[0] = 1
        else:
            rows[:8] = bytes((0, 0x60, 0x80, 0x37, 1, 0, 0, 0xed))
            if alias == 'data-counter-return':
                rows[2] = 0x89
        for row, bits in enumerate(rows):
            for sample in range(8):
                at = (16+0x5740+row*0x680+sample*2)&65535
                byte = 255 if bits & (0x80 >> sample) else 0
                device.planes[3][at] = byte
                device.planes[3][(at+1)&65535] = byte
    return memory, regs, flags, device


def load_library(directory, mutation=0):
    lib = ctypes.CDLL(str(Path(directory)/f'level-finish-m{mutation}.dll'))
    lib.lmn_finish_level_initialization_adapter.argtypes = [MEM, ctypes.POINTER(Regs), ctypes.POINTER(bus_support.RasterBus)]
    lib.lmn_finish_level_initialization_adapter.restype = None
    lib.lmn_finish_level_initialization_core.argtypes = [MEM, ctypes.POINTER(Call), ctypes.POINTER(bus_support.RasterBus)]
    lib.lmn_finish_level_initialization_core.restype = Result
    return lib


def compare(lib, case):
    memory, regs, flags, device = prepare(case)
    expected = original(case, bytearray(memory), regs, flags, copy.deepcopy(device))
    for mode in ('adapter', 'core'):
        actual_mem = bytearray(memory)
        native_device = copy.deepcopy(device)
        native_bus = NativeBus(actual_mem, native_device)
        actual = Regs(**regs, flags=flags)
        view = (ctypes.c_uint8*(1 << 20)).from_buffer(actual_mem)
        if mode == 'adapter':
            lib.lmn_finish_level_initialization_adapter(view, ctypes.byref(actual), ctypes.byref(native_bus.bus))
            target, event_count = expected['after'], len(expected['events'])
        else:
            call = Call(regs['cs'], regs['ds'], regs['ss'], regs['sp'], regs['bx'], regs['si'], flags)
            result = lib.lmn_finish_level_initialization_core(view, ctypes.byref(call), ctypes.byref(native_bus.bus))
            target = expected['boundary'] or expected['after']
            event_count = target.get('event_count', len(expected['events']))
            for name, register in (('value','ax'), ('target_cursor','bx'), ('count','cx'),
                    ('port_or_population','dx'), ('source_cursor','si'), ('output_cursor','di'),
                    ('data_segment','ds'), ('extra_segment','es'), ('stack_offset','sp'),
                    ('continuation','ip'), ('flags','flags')):
                setattr(actual, register, getattr(result, name))
            require(bool(result.changed_return) == expected['changed'], case['name']+': changed-return status differs')
        require(bytes(actual_mem) == target['memory'], case['name']+'/'+mode+': whole RAM differs')
        require(native_device.state() == target['device'], case['name']+'/'+mode+': VGA planes/latches/registers differ')
        for name, value in target['regs'].items():
            require(getattr(actual, name) == value, f'{case["name"]}/{mode}: {name} {getattr(actual,name):04x} != {value:04x}')
        require(((actual.flags^target['flags'])&target['mask']) == 0, case['name']+'/'+mode+': final defined flags differ')
        require(len(native_bus.events) == event_count, f'{case["name"]}/{mode}: event count {len(native_bus.events)} != {event_count}')
        for index, (event, wanted) in enumerate(zip(native_bus.events, expected['events'][:event_count])):
            kind, address, value, event_flags, mask, pc = wanted
            require(event[:3] == (kind, address, value), f'{case["name"]}/{mode}: event{index}/{pc:04x} {event[:3]} != {wanted[:3]}')
            require(((event[3]^event_flags)&mask) == 0, f'{case["name"]}/{mode}: flags event{index}/{pc:04x} {event[3]:04x} != {event_flags:04x} mask{mask:04x}')
    return expected


def compile_library(directory, mutation):
    build(Path(directory)/f'level-finish-m{mutation}.dll',mutation,'level_finish')


def worker(directory, hash_file):
    before = read_json(hash_file)
    baseline = cases()
    if (len(baseline), len(LOCAL), len(INS), len(EDGES)) != (22, 9, 133, 17):
        raise VerificationFailure('Pinned case/site/edge counts changed')
    lib = load_library(directory)
    seen, edges, details = set(), set(), []
    for case in baseline:
        result = compare(lib, case)
        require(result['columns'] == case['columns'], case['name']+': original column count differs')
        if 'expected_return' in case:
            require(result['after']['regs']['ip'] == case['expected_return'] and result['changed'],
                    case['name']+': original changed return differs')
        if case.get('alias') in ('counter', 'data-counter'):
            require(result['samples'] == 160 and result['after']['regs']['cx'] == 0,
                    case['name']+': live savedCX must finish after one complete column')
        if case.get('alias') == 'data-counter':
            require(result['after']['regs']['ds'] == 0x6000 and result['after']['regs']['ax'] == 0xa55a,
                    case['name']+': final read must use the live restored DS')
        if case.get('alias') == 'data-counter-return':
            _memory, entry_regs, _flags, _device = prepare(case)
            require(result['after']['regs']['sp'] == (entry_regs['sp']-2)&65535
                    and result['boundary'] is None,
                    case['name']+': changed target must stop before own RET with outer CX still saved')
        seen |= result['seen']; edges |= result['edges']
        details.append(dict(name=case['name'], columns=result['columns'], samples=result['samples'],
            continuation=result['after']['regs']['ip'], changed_child_return=result['changed'],
            events=len(result['events'])))
        print(f'PASS {case["name"]}: {result["columns"]} columns, {len(result["events"])} events', flush=True)
        del result
        gc.collect()
    require(seen == set(INS) and edges == EDGES,
            f'Site/edge coverage missing {set(INS)-seen}/{EDGES-edges}; extra {seen-set(INS)}/{edges-EDGES}')
    mutants = []
    for mutation, name in ((1,'saved-counter-from-CS-scratch'),
            (2,'restored-DS-and-counter-from-CS-scratch'), (3,'clear-return-VGA-overwrite'),
            (4,'column-0000')):
        case = next(c for c in baseline if c['name']==name)
        print(f'CHECK completed mutation{mutation}: {name}', flush=True)
        try:
            compare(load_library(directory, mutation), case)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name, mismatch=str(error)))
        else:
            raise VerificationFailure(f'Completed mutation{mutation} survived')
        gc.collect()
    check_hashes(before)
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE), case_count=len(baseline),
        adapter_case_count=len(baseline), core_boundary_case_count=len(baseline),
        mutation_count=len(mutants), mutations_detected=mutants, cases=details,
        caller_instruction_addresses=sorted(LOCAL), executed_instruction_addresses=sorted(seen),
        branch_edges=sorted(edges), translated_code_bytes=20, native_code_ranges=[[ENTRY,END]],
        input_hashes=before, limits=dict(native_events=EVENT_LIMIT, original_steps=STEP_LIMIT,
            worker_seconds=120, process_memory_mib=512, tree_memory_mib=768),
        domain='3776..3789 clear/minimap tail; actual SS saves, nested CALL/RET, live LOOP CX and returned DS, whole canonical RAM, ordered bus/port definedflags, VGA state; intact code, quiescent IRQ.'))
    print(f'PASS level finish: {len(baseline)} cases, {len(LOCAL)} caller/{len(seen)} integrated sites, {len(edges)} edges, {len(mutants)} completed mutants')


def main():
    if len(sys.argv)==4 and sys.argv[1]=='--worker':
        worker(sys.argv[2],sys.argv[3]); return
    if len(sys.argv)!=1:
        raise SystemExit('Unexpected arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT.unlink(missing_ok=True)
    before = input_hashes()
    try:
        with temporary_build_directory(prefix='level-finish-',parent=BUILD) as directory:
            hash_file=Path(directory)/'inputs.json'
            write_json(hash_file,before)
            for mutation in range(5):
                compile_library(directory,mutation)
            run_bounded([sys.executable,str(Path(__file__).resolve()),'--worker',directory,str(hash_file)],
                        cwd=ROOT,timeout=120,memory_mib=512)
    finally:
        check_hashes(before)


if __name__=='__main__':
    main()

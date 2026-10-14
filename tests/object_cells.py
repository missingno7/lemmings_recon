"""Bounded 37C2 object interaction-cell oracle and native comparisons."""
import ctypes
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import capstone
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn import UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
import dat_io as oracle
from dat_io_c import Regs, MEM
from common import ROOT, BUILD, read_json, write_json, sha
from cbuild import build
from resources import section_spans, decode_section
from unpack import ASSET, unpack, relocated

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {s['symbol_name']: s for s in read_json(ROOT / 'metadata/symbols.json')}
ROUTINE = SYMS['WriteObjectInteractionCells']
ENTRY = ROUTINE['address']
END = ENTRY + ROUTINE['size']
DEFINITIONS = SYMS['LevelObjectDefinitions']['address']
GROUND = SYMS['GroundResourceBuffer']['address']
MAP_BASE = SYMS['InteractionCellMapBase']['address']
RET = END - 1
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {i.address: i for i in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
BRANCHES = {pc for pc, i in INS.items()
            if i.group(capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
CONDITIONAL = {pc for pc, i in INS.items()
               if pc in BRANCHES and i.mnemonic not in ('jmp', 'ljmp')}
EDGES = set()
for pc in BRANCHES:
    ins = INS[pc]
    target = ins.operands[0].imm & 0xffff
    EDGES.add((pc, target))
    if pc in CONDITIONAL:
        EDGES.add((pc, pc + ins.size))

MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
ARITH = 0x08d5
DF = 0x0400
IF = 0x0200
LOADS = (0x1010, 0x1213, 0x2345)


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xffff)) & MEMORY_MASK


def read8(memory, segment, offset):
    return memory[physical(segment, offset)]


def read16(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & MEMORY_MASK] << 8)


def read_be16(memory, segment, offset):
    return (read8(memory, segment, offset) << 8) | \
        read8(memory, segment, (offset + 1) & 0xffff)


def write_bytes(memory, segment, offset, data):
    for index, value in enumerate(data):
        memory[physical(segment, (offset + index) & 0xffff)] = value


def write16(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xff
    memory[(address + 1) & MEMORY_MASK] = (value >> 8) & 0xff


def put_definition(memory, segment, index, x_value, y_value, object_type):
    offset = (DEFINITIONS + index * 8) & 0xffff
    write_bytes(memory, segment, offset,
                (x_value >> 8, x_value & 0xff,
                 y_value >> 8, y_value & 0xff,
                 object_type >> 8, object_type & 0xff, 0, 0))


def template_offset(object_type):
    return (GROUND + ((object_type * 28) & 0xffff)) & 0xffff


def put_template(memory, segment, object_type, x_offset=0, y_offset=1,
                 width=2, height=2, kind=0x80):
    offset = template_offset(object_type)
    write16(memory, segment, (offset + 0x0e) & 0xffff, x_offset)
    write16(memory, segment, (offset + 0x10) & 0xffff, y_offset)
    write_bytes(memory, segment, (offset + 0x12) & 0xffff,
                (width & 0xff, height & 0xff, kind & 0xff))


def target_template(target, x_value, y_value, width, height, kind,
                    object_type=0, y_offset=None):
    if y_offset is None:
        y_offset = (1 - (y_value >> 2)) & 0xffff
    row = ((y_value >> 2) + y_offset - 1) & 0xffff
    x_offset = (target - MAP_BASE - (x_value >> 2) - 416 * row) & 0xffff
    return (object_type, x_offset, y_offset, width, height, kind)


def add_case(out, name, definitions=(), templates=(), **kwargs):
    out.append(dict(name=name, definitions=tuple(definitions),
                    templates=tuple(templates), seed=len(out), **kwargs))


def cases():
    out = []
    add_case(out, 'all-inactive-preserves-bx', bx=0xbeef)
    add_case(out, 'inactive-nonzero-types-compute-final-product',
             ((0, 0, 0, 0xffff), (15, 0, 0xffff, 0x7fff)), bx=0x5aa5)
    add_case(out, 'active-before-inactive-final-state',
             ((0, 4, 0, 0),), ((0, 0, 1, 2, 1, 0x80),))
    add_case(out, 'only-first-sixteen-of-thirty-two',
             ((16, 4, 0, 0), (31, 4, 0, 0)),
             ((0, 0, 1, 2, 1, 0x80),))

    for index in range(16):
        add_case(out, f'ordinal-{index:02d}', ((index, 4, index * 4, 0),),
                 ((0, 0, 1, 2, 1, 0x80),), df=bool(index & 1))

    add_case(out, 'all-sixteen-active-kind-upper-bits',
             ((i, 4 + (i % 4) * 4, (i % 5) * 4, i % 4)
              for i in range(16)),
             tuple((t, 0, 1, 1 + (t % 3), 1 + (t % 2), 0xa5)
                   for t in range(4)))
    add_case(out, 'be-definitions-le-template-offsets',
             ((3, 0x1234, 0x5678, 3),),
             ((3, 0x0102, 0x0304, 3, 2, 0x85),))

    for object_type in (0x0010, 0x0011, 0x0100, 0x7fff, 0xffff):
        add_case(out, f'unchecked-type-{object_type:04x}',
                 ((0, 4, 0, object_type),),
                 ((object_type, 0, 1, 2, 1, 0x61),))

    add_case(out, 'x-y-arithmetic-wrap', ((0, 0xfffc, 0xfffc, 0),),
             ((0, 0xfff0, 0x4000, 2, 2, 0x72),))
    add_case(out, 'width-zero-means-256-height-one', ((0, 4, 0, 0),),
             ((0, 0, 1, 0, 1, 0x21),))
    add_case(out, 'width-255-height-one', ((0, 4, 0, 0),),
             ((0, 0, 1, 255, 1, 0x22),))
    add_case(out, 'width-one-height-zero-means-256', ((0, 4, 0, 0),),
             ((0, 0, 1, 1, 0, 0x23),))
    add_case(out, 'width-one-height-255', ((0, 4, 0, 0),),
             ((0, 0, 1, 1, 255, 0x24),))
    add_case(out, 'width-height-zero-65536-writes', ((0, 4, 0, 0),),
             (target_template(0, 4, 0, 0, 0, 0x03),),
             sp=0xa044, ds=0x6000)

    add_case(out, 'saved-bx-dx-alias-controls-next-row', ((15, 4, 0, 0),),
             (target_template(0x7ffc, 4, 0, 4, 1, 2),), sp=0x8000,
             ds=0x6000, ss=0x7000, alias='row-saves')
    add_case(out, 'ds-ss-alias-overwrites-next-definition',
             ((0, 4, 0, 0), (1, 4, 0, 0)),
             (target_template(DEFINITIONS + 8, 4, 0, 8, 1, 0),),
             ds=0x7000, ss=0x7000, sp=0x9000, alias='definition')
    add_case(out, 'live-ret-word-is-overwritten', ((0, 4, 0, 0),),
             (target_template(0x8000, 4, 0, 1, 1, 0x5a),),
             ds=0x6000, ss=0x7000, sp=0x8000, return_word=0xff00,
             alias='return')

    for sp in (0, 1, 0xffff):
        add_case(out, f'stack-pointer-{sp:04x}', ((0, 4, 0, 0),),
                 ((0, 0, 1, 2, 2, 0x44),), sp=sp)
    add_case(out, 'a20-data-read-and-write-wrap', ((0, 4, 0, 0),),
             (target_template(0x000c, 4, 0, 8, 1, 0x55),),
             ds=0xffff, ss=0xffff, sp=0x8000, alias='a20')
    add_case(out, 'segment-offset-wrap-at-ffff', ((0, 4, 0, 0),),
             (target_template(0xfffc, 4, 0, 8, 1, 0x66),),
             ds=0x6000, ss=0x7000, sp=0x8000)
    add_case(out, 'if-and-df-preserved-set', ((0, 4, 0, 0),),
             ((0, 0, 1, 2, 2, 0x77),), df=True, iflag=True)
    add_case(out, 'if-and-df-preserved-clear', ((0, 4, 0, 0),),
             ((0, 0, 1, 2, 2, 0x77),), df=False, iflag=False)

    consumed_assets = []
    for group in range(10):
        asset = f'assets/level{group:03d}.dat'
        packed = (ROOT / asset).read_bytes()
        spans = section_spans(packed)
        if len(spans) != 8:
            raise AssertionError(f'{asset}: expected eight pinned LEVEL sections')
        consumed_assets.append(asset)
        for section, (start, end) in enumerate(spans):
            record, _ = decode_section(packed[start:end])
            if len(record) != 2048:
                raise AssertionError(f'{asset} section {section}: unexpected record size')
            ground_asset = f"assets/ground{record[27]}o.dat"
            ground = (ROOT / ground_asset).read_bytes()
            if ground_asset not in consumed_assets:
                consumed_assets.append(ground_asset)
            out.append(dict(name=f'real-level-{group:03d}-{section}', seed=len(out),
                real=True, level_asset=asset, ground_asset=ground_asset,
                section=section, record=record, ground=ground,
                df=False, iflag=False))
    return out, consumed_assets


def prepare(case):
    rng = random.Random(0x37c2 + case['seed'])
    load = LOADS[case['seed'] % len(LOADS)]
    memory = bytearray(rng.randbytes(MEMORY_SIZE))
    memory[load << 4:(load << 4) + len(IMAGE)] = \
        relocated(IMAGE, ORACLE['relocations'], load)
    regs = {name: rng.randrange(65536) for name in oracle.REG_NAMES}
    ds = case.get('ds', (load + 0x09a9) & 0xffff)
    regs.update(cs=load, ip=ENTRY, ds=ds,
                es=rng.randrange(65536), ss=case.get('ss', 0x7000),
                sp=case.get('sp', 0x8000))
    write_bytes(memory, ds, DEFINITIONS, bytes(32 * 8))
    if case.get('real'):
        write_bytes(memory, ds, DEFINITIONS, case['record'][32:32 + 32 * 8])
        write_bytes(memory, ds, GROUND, case['ground'])
    else:
        ground = bytes((n * 29 + case['seed'] * 13 + 0x47) & 0xff
                       for n in range(0x1000))
        write_bytes(memory, ds, GROUND, ground)
        for index, x_value, y_value, object_type in case.get('definitions', ()):
            put_definition(memory, ds, index, x_value, y_value, object_type)
        for object_type, x_offset, y_offset, width, height, kind in case.get('templates', ()):
            put_template(memory, ds, object_type, x_offset, y_offset,
                         width, height, kind)

    flags = 2 | (rng.randrange(65536) & (ARITH | DF | IF))
    if case.get('df') is True:
        flags |= DF
    elif case.get('df') is False:
        flags &= ~DF
    if case.get('iflag') is True:
        flags |= IF
    elif case.get('iflag') is False:
        flags &= ~IF
    write16(memory, regs['ss'], regs['sp'], case.get('return_word', 0xff00))
    if 'bx' in case:
        regs['bx'] = case['bx']
    return memory, regs, flags


def library(mutation=0):
    path = BUILD / f'object-cells-m{mutation}.dll'
    lib = ctypes.CDLL(str(build(path, mutation, 'object_cells')))
    lib.lmn_write_object_interaction_cells_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs)]
    lib.lmn_write_object_interaction_cells_adapter.restype = None
    return lib


def independent_rectangle(memory, case, regs):
    """Model the rectangle writes for cases with disjoint data/stack state."""
    if case.get('alias'):
        return None, 0
    expected = bytearray(memory)
    ds = regs['ds']
    ss = regs['ss']
    definition_reads = set()
    for index in range(16):
        definition = (DEFINITIONS + index * 8) & 0xffff
        definition_reads.update((definition + offset) & 0xffff
                                for offset in (0, 1, 2, 3, 4, 5))
    stack_live = {(regs['sp'] + delta) & 0xffff for delta in (-4, -3, -2, -1, 0, 1)}
    writes = 0

    # Verify each potential output cell stays away from live stack words and
    # from every DS byte that the routine reads during its remaining scan.
    for index in range(16):
        definition = (DEFINITIONS + index * 8) & 0xffff
        x_value = read_be16(expected, ds, definition)
        if x_value == 0:
            continue
        y_value = read_be16(expected, ds, (definition + 2) & 0xffff)
        object_type = read_be16(expected, ds, (definition + 4) & 0xffff)
        template = template_offset(object_type)
        x_offset = read16(expected, ds, (template + 0x0e) & 0xffff)
        y_offset = read16(expected, ds, (template + 0x10) & 0xffff)
        row = ((y_value >> 2) + y_offset - 1) & 0xffff
        base = (MAP_BASE + (x_value >> 2) + x_offset + 416 * row) & 0xffff
        width_byte = read8(expected, ds, (template + 0x12) & 0xffff)
        height_byte = read8(expected, ds, (template + 0x13) & 0xffff)
        width = width_byte or 256
        height = height_byte or 256
        kind = read8(expected, ds, (template + 0x14) & 0xffff)
        value = ((index << 4) | kind) & 0xff
        coordinate_base = (x_value >> 2) + x_offset
        write16(expected, ss, (regs['sp'] - 2) & 0xffff, coordinate_base)
        for row_index in range(height):
            row_base = (base + 416 * row_index) & 0xffff
            dimensions = ((width_byte << 8) |
                          ((height_byte - row_index) & 0xff))
            write16(expected, ss, (regs['sp'] - 2) & 0xffff, dimensions)
            write16(expected, ss, (regs['sp'] - 4) & 0xffff, row_base)
            for column in range(width):
                offset = (row_base + column) & 0xffff
                if ds == ss and offset in definition_reads:
                    return None, writes
                if offset in stack_live:
                    return None, writes
                expected[physical(ss, offset)] = value
                writes += 1
    return expected, writes


def run_case(lib, case, collect_coverage=False):
    memory, regs, flags = prepare(case)
    expected, expected_writes = independent_rectangle(memory, case, regs)
    c_memory = bytearray(memory)
    c_regs = Regs(**regs, flags=flags)
    lib.lmn_write_object_interaction_cells_adapter(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(c_memory), ctypes.byref(c_regs))

    # The upper MiB is a synchronized mirror so Unicorn's 16-bit segmented
    # reads and writes expose the real-mode twenty-bit bus.
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, 1 << 21)
    uc.mem_write(0, bytes(memory) + bytes(memory))
    for name, reg in oracle.REG.items():
        uc.reg_write(reg, regs[name])
    uc.reg_write(x.UC_X86_REG_EFLAGS, flags)
    sites = set()
    edges = set()
    previous = None
    done = False

    def code(machine, pc, _size, _user):
        nonlocal previous, done
        if previous == RET:
            done = True
            machine.emu_stop()
            return
        offset = (pc - (regs['cs'] << 4)) & 0xffff
        if previous in BRANCHES:
            edges.add((previous, offset))
        if machine.reg_read(oracle.REG['cs']) != regs['cs'] or offset not in INS:
            raise AssertionError(f"{case['name']}: original escaped at {offset:04x}")
        sites.add(offset)
        previous = offset

    def a20_read(machine, _access, address, size, _value, _user):
        for index in range(size):
            current = address + index
            if current >= MEMORY_SIZE:
                machine.mem_write(current, bytes(machine.mem_read(current & MEMORY_MASK, 1)))

    def a20_write(machine, _access, address, size, value, _user):
        for index in range(size):
            current = address + index
            byte = bytes(((value >> (8 * index)) & 0xff,))
            if current >= MEMORY_SIZE:
                machine.mem_write(current & MEMORY_MASK, byte)
            else:
                machine.mem_write(current + MEMORY_SIZE, byte)

    def interrupt(_machine, number, _user):
        raise AssertionError(f"{case['name']}: unexpected interrupt {number}")

    uc.hook_add(UC_HOOK_CODE, code)
    uc.hook_add(UC_HOOK_MEM_READ, a20_read)
    uc.hook_add(UC_HOOK_MEM_WRITE, a20_write)
    uc.hook_add(UC_HOOK_INTR, interrupt)
    uc.emu_start(physical(regs['cs'], ENTRY), 0, count=2_000_000)
    if not done:
        raise AssertionError(f"{case['name']}: routine exceeded bounded execution")

    original_regs = {name: uc.reg_read(reg) for name, reg in oracle.REG.items()}
    original_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
    original_memory = bytes(uc.mem_read(0, MEMORY_SIZE))
    for name in oracle.REG_NAMES:
        got = getattr(c_regs, name)
        if original_regs[name] != got:
            raise AssertionError(f"{case['name']}: {name} C={got:04x}/original={original_regs[name]:04x}")
    if (c_regs.flags ^ original_flags) & (ARITH | DF | IF):
        raise AssertionError(f"{case['name']}: C defined flags differ")
    if bytes(c_memory) != original_memory:
        offset = next(i for i, pair in enumerate(zip(c_memory, original_memory))
                      if pair[0] != pair[1])
        raise AssertionError(f"{case['name']}: whole RAM differs at {offset:05x}")

    if expected is not None:
        if bytes(expected) != original_memory:
            offset = next(i for i, pair in enumerate(zip(expected, original_memory))
                          if pair[0] != pair[1])
            raise AssertionError(f"{case['name']}: independent rectangle/stale-SS model differs at {offset:05x}")
    if case.get('name') == 'width-height-zero-65536-writes' and expected_writes != 65536:
        raise AssertionError(f"zero dimensions model counted {expected_writes} writes")
    if case.get('name') == 'saved-bx-dx-alias-controls-next-row':
        if c_regs.bx != 0x7c32 or c_regs.dx != 0xf200:
            raise AssertionError(f'saved BX/DX alias result BX={c_regs.bx:04x} DX={c_regs.dx:04x}')
        if any(read8(original_memory, regs['ss'], offset) != 0xf2
               for offset in range(0xf492, 0xf492 + 0xf2)):
            raise AssertionError('saved BX alias did not redirect the following rectangle row')
    if case.get('name') == 'live-ret-word-is-overwritten':
        if c_regs.ip != 0xff5a or original_regs['ip'] != 0xff5a:
            raise AssertionError('RET alias fixture did not change the live continuation word')
    if collect_coverage:
        return sites, edges
    return None


def main():
    report = BUILD / 'object-cells-differential.json'
    report.unlink(missing_ok=True)
    baseline, consumed_assets = cases()
    lib = library()
    sites = set()
    edges = set()
    by_name = {case['name']: case for case in baseline}
    for case in baseline:
        case_sites, case_edges = run_case(lib, case, True)
        sites |= case_sites
        edges |= case_edges
    if sites != set(INS):
        raise AssertionError(f'Missing instruction sites: {sorted(set(INS) - sites)}')
    if edges != EDGES:
        raise AssertionError(f'Branch-edge coverage differs; missing={sorted(EDGES-edges)}, extra={sorted(edges-EDGES)}')

    mutant_fixtures = {
        1: 'width-zero-means-256-height-one',
        2: 'saved-bx-dx-alias-controls-next-row',
        3: 'unchecked-type-ffff',
    }
    mutations = []
    for mutation, name in mutant_fixtures.items():
        try:
            run_case(library(mutation), by_name[name])
        except AssertionError:
            mutations.append(dict(mutation=mutation, case=name))
        else:
            raise AssertionError(f'Compiled mutation {mutation} survived on {name}')

    paths = ('c/object_cells.c', 'c/object_cells.h', 'c/regs.h',
             'c/lemmings_sym.h', 'tests/object_cells.py',
             'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/common.py',
             'tools/cbuild.py', 'tools/difftest.py', 'tools/resources.py',
             'tools/unpack.py', 'metadata/symbols.json', 'metadata/inputs.json')
    paths += tuple(consumed_assets)
    write_json(report, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(baseline), cases=[case['name'] for case in baseline],
        mutation_count=len(mutations), mutations_detected=mutations,
        translated_code_bytes=sum(ins.size for ins in INS.values()),
        instruction_addresses=sorted(INS),
        executed_instruction_addresses=sorted(sites),
        instruction_sites=sorted(sites),
        branch_instruction_addresses=sorted(BRANCHES),
        branch_edges=[list(edge) for edge in sorted(edges)],
        routine=dict(name='WriteObjectInteractionCells', start=ENTRY, end=END,
                     byte_count=END-ENTRY, bytes=IMAGE[ENTRY:END].hex(),
                     byte_sha256=sha(IMAGE[ENTRY:END])),
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
        consumed_level_and_ground_assets=consumed_assets,
        flag_notes='The final DEC CX determines PF/ZF/SF/AF/OF; CF comes from the final ADD DI,8. DF and IF are preserved. AF is architecturally defined by this final DEC.',
        domain='Sixteen live big-endian object definitions, unchecked wrapped type*28 template lookup, ' \
               'little-endian template offsets, SS cell writes with live row stack words, ' \
               'decrement dimensions where zero means 256, full RAM/all registers/defined flags, ' \
               '20-bit physical wrapping, segment-offset wrapping, and live RET reads after the core.'))
    print(f'PASS object interaction cells C: {len(baseline)} cases, {len(sites)} instruction sites, '
          f'{len(edges)} branch edges; {len(mutations)} compiled mutations detected')


if __name__ == '__main__':
    main()

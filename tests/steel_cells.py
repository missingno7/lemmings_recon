"""Bounded original and native checks for steel interaction-cell writes."""
import ctypes
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import capstone
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x
import dat_io as oracle
from common import ROOT, BUILD, read_json, write_json, sha
from cbuild import build
from unpack import ASSET, unpack, relocated
from resources import section_spans, decode_section

MEMORY_SIZE = 1 << 20
MEMORY_MASK = MEMORY_SIZE - 1
IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {row['symbol_name']: row for row in read_json(ROOT / 'metadata/symbols.json')}
ROUTINE = SYMS['WriteSteelInteractionCells']
ENTRY = ROUTINE['address']
END = ENTRY + ROUTINE['size']
DEFINITIONS = SYMS['LevelSteelDefinitions']['address']
LEVEL_RECORD = SYMS['LoadedLevelRecord']['address']
MAP_BASE = SYMS['InteractionCellMapBase']['address']
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {ins.address: ins for ins in MD.disasm(IMAGE[ENTRY:END], ENTRY)}
BRANCHES = {pc for pc, ins in INS.items()
            if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
EDGES = {(pc, ins.operands[0].imm & 0xffff)
         for pc, ins in INS.items() if pc in BRANCHES}
EDGES |= {(pc, ins.address + ins.size)
          for pc, ins in INS.items() if pc in BRANCHES}
RETS = {pc for pc, ins in INS.items() if ins.mnemonic == 'ret'}
ARITH = 0x08d5
DF = 0x0400
IF = 0x0200
CONTROL = DF | IF
MEM = ctypes.POINTER(ctypes.c_uint8)


class Regs(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
                 'cs', 'ds', 'es', 'ss', 'ip', 'flags')]


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xffff)) & MEMORY_MASK


def get16(mem, segment, offset):
    return oracle.get16(mem, segment, offset)


def put8(mem, segment, offset, value):
    mem[physical(segment, offset)] = value & 255


def put_bytes(mem, segment, offset, values):
    for index, value in enumerate(values):
        put8(mem, segment, (offset + index) & 0xffff, value)


def record(byte0=0, byte1=0, byte2=0, byte3=0):
    return bytes((byte0 & 255, byte1 & 255, byte2 & 255, byte3 & 255))


def definitions_with(records=()):
    out = bytearray(32 * 4)
    for index, value in records:
        if len(value) != 4:
            raise ValueError('each steel definition must be four bytes')
        out[index * 4:index * 4 + 4] = value
    return bytes(out)


def cases():
    out = []

    def add(name, definitions, **kw):
        out.append(dict(name=name, seed=len(out), definitions=definitions, **kw))

    add('all-inactive', definitions_with())
    for index in range(32):
        b0 = (0x11 + index * 7) & 255
        b1 = 0x80 | ((index * 3 + 5) & 0x7f)
        b2 = (((index * 5) & 0x0f) << 4) | ((index * 7) & 0x0f)
        add(f'single-active-at-{index:02d}',
            definitions_with(((index, record(b0, b1, b2, index * 13)),)),
            df=bool(index & 1), iflag=bool(index & 2))

    add('all-active-and-varied', definitions_with((index,
        record(0x20 + index, 0x80 | ((index * 9) & 0x7f),
               (((index % 4) << 4) | ((index // 4) % 4)), index ^ 0xa5))
        for index in range(32)), df=True, iflag=True)
    add('byte3-alone-keeps-record-active',
        definitions_with(((0, record(0, 0, 0, 0x80)),)))
    add('byte2-alone-keeps-record-active',
        definitions_with(((0, record(0, 0, 0x10, 0)),)))
    add('firstword-ffff-and-max-dimensions',
        definitions_with(((31, record(0xff, 0xff, 0xff, 0xff)),)), df=True)
    add('zero-x-and-nonzero-byte3',
        definitions_with(((0, record(0, 0, 0, 1)),)))
    add('x-bit7-contributes-one',
        definitions_with(((0, record(0x21, 0x80, 0, 0)),)))

    for dimension_byte in range(256):
        add(f'dimensions-{dimension_byte:02x}', definitions_with(((0,
            record(0x35, 0x8b, dimension_byte, dimension_byte ^ 0xa5)),)))

    for sp in (0, 1, 0xffff):
        add(f'stack-offset-{sp:04x}',
            definitions_with(((4, record(0x05, 0x8e, 0x11, 0x00)),)), sp=sp)
    add('a20-low-to-high-mirror', definitions_with(((0, record(2, 0x80, 0, 0)),)),
        ss=0, sp=0xf000, check_mirror=True)
    add('a20-high-to-low-mirror', definitions_with(((0, record(2, 0x80, 0, 0)),)),
        ss=0xffff, sp=0xf000, check_mirror=True)
    add('data-segment-physical-wrap-ffff',
        definitions_with(((0, record(0x37, 0x80, 0x11, 0)),)), ds=0xffff)
    add('data-segment-physical-wrap-fff0',
        definitions_with(((0, record(0x29, 0x8f, 0x21, 0)),)), ds=0xfff0)

    # BX is saved at SP-4; two writes replace both live save bytes.
    add('saved-bx-alias', definitions_with(((0, record(0xa8, 9, 0x10, 0)),)),
        ds=0x6000, ss=0x6000, sp=0x1000, stack_alias=True)
    # The first cell write changes saved DX low byte to 9, extending the row
    # loop to nine rows while retaining the live saved-DX behavior.
    add('saved-dx-alias', definitions_with(((0, record(0xa9, 9, 0, 0)),)),
        ds=0x6000, ss=0x6000, sp=0x1000, stack_alias=True)
    add('live-ret-word-alias', definitions_with(((0, record(0xa8, 9, 0, 0)),)),
        ss=0x6000, sp=0x0ffc, return_word=0xaabb)
    # The first rectangle writes into the next live steel record, making that
    # record active before DI reaches it. This uses DS == SS intentionally.
    add('live-definition-input-alias', definitions_with(((0,
        record(0x41, 0x8e, 0, 0)),)), ds=0x6000, ss=0x6000,
        sp=0xf000, stack_alias=True)

    consumed_assets = []
    for group in range(10):
        asset = f'assets/level{group:03d}.dat'
        packed = (ROOT / asset).read_bytes()
        spans = section_spans(packed)
        if len(spans) != 8:
            raise AssertionError(f'{asset}: expected eight LEVEL sections, found {len(spans)}')
        consumed_assets.append(asset)
        for section, (start, end) in enumerate(spans):
            level, _ = decode_section(packed[start:end])
            if len(level) != 2048:
                raise AssertionError(f'{asset} section {section}: unexpected level size')
            steel = level[1888:2016]
            if len(steel) != 128:
                raise AssertionError(f'{asset} section {section}: unexpected steel record span')
            add(f'real-level-{group:03d}-section-{section:02d}', steel,
                real=True, level_asset=asset, section=section)
    return out, consumed_assets


def prepare(case):
    rng = random.Random(0x3839 + case['seed'])
    load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
    mem = bytearray(rng.randbytes(MEMORY_SIZE))
    base = load << 4
    mem[base:base + len(IMAGE)] = relocated(IMAGE, ORACLE['relocations'], load)
    regs = {name: rng.randrange(65536) for name in oracle.REG_NAMES}
    ds = case.get('ds', load + 0x09a9)
    regs.update(cs=load, ip=ENTRY, ds=ds, es=rng.randrange(65536),
                ss=case.get('ss', 0x7000), sp=case.get('sp', 0xf000))
    # Cases carry the extracted 128-byte steel span, not the complete record.
    # Load it at DS:172B in both real and constructed fixtures.
    put_bytes(mem, ds, DEFINITIONS, case['definitions'])
    loaded=bytes(mem[physical(ds,DEFINITIONS+i)] for i in range(128))
    if loaded!=case['definitions']:raise AssertionError('Steel fixture is absent at the original definition cursor')
    flags = 2 | (rng.randrange(65536) & ARITH)
    if case.get('df', bool(case['seed'] & 1)):
        flags |= DF
    else:
        flags &= ~DF
    if case.get('iflag', bool(case['seed'] & 2)):
        flags |= IF
    else:
        flags &= ~IF
    oracle.put16(mem, regs['ss'], regs['sp'], case.get('return_word', 0xff00))
    return mem, regs, flags


def independent_cells(mem, regs):
    """Compute only the rectangle footprint from the documented field rules."""
    footprint = set()
    stale_candidates = set()
    ds = regs['ds']
    ss = regs['ss']
    for index in range(32):
        di = (DEFINITIONS + index * 4) & 0xffff
        byte0 = mem[physical(ds, di)]
        byte1 = mem[physical(ds, (di + 1) & 0xffff)]
        byte2 = mem[physical(ds, (di + 2) & 0xffff)]
        byte3 = mem[physical(ds, (di + 3) & 0xffff)]
        if (byte0 | byte1 | byte2 | byte3) == 0:
            continue
        x_cell = (byte0 << 1) | (byte1 >> 7)
        row = byte1 & 0x7f
        width = (byte2 >> 4) + 1
        height = (byte2 & 0x0f) + 1
        first = (MAP_BASE + x_cell + 416 * row) & 0xffff
        for row_index in range(height):
            row_start = (first + 416 * row_index) & 0xffff
            for column in range(width):
                footprint.add(physical(ss, (row_start + column) & 0xffff))
            stale_candidates.add(physical(ss, (row_start - 1) & 0xffff))
            stale_candidates.add(physical(ss, (row_start + width) & 0xffff))
    return footprint, stale_candidates


def library(mutation=0):
    lib = ctypes.CDLL(str(build(BUILD / f'steel-cells-m{mutation}.dll',
                                mutation, 'steel_cells')))
    lib.lmn_write_steel_interaction_cells_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs)]
    lib.lmn_write_steel_interaction_cells_adapter.restype = None
    return lib


def run_case(lib, case, collect_coverage=False):
    mem, regs, flags = prepare(case)
    c_mem = bytearray(mem)
    c_regs = Regs(**regs, flags=flags)
    lib.lmn_write_steel_interaction_cells_adapter(
        (ctypes.c_uint8 * MEMORY_SIZE).from_buffer(c_mem), ctypes.byref(c_regs))

    # The upper MiB mirrors the DOS 20-bit bus. The write hook keeps writes in
    # either linear half visible through the other half.
    u = Uc(UC_ARCH_X86, UC_MODE_16)
    u.mem_map(0, 1 << 21)
    u.mem_write(0, bytes(mem))
    u.mem_write(MEMORY_SIZE, bytes(mem))
    for name, reg in oracle.REG.items():
        u.reg_write(reg, regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS, flags)
    sites, edges = set(), set()
    previous = None
    done = False

    def code(uc, pc, _size, _user):
        nonlocal previous, done
        offset = pc - (regs['cs'] << 4)
        if previous in RETS:
            done = True
            uc.emu_stop()
            return
        if previous in BRANCHES:
            edges.add((previous, offset))
        if uc.reg_read(oracle.REG['cs']) != regs['cs'] or offset not in INS:
            raise AssertionError(f"{case['name']}: original escaped to {offset & 0xffff:04x}")
        sites.add(offset)
        previous = offset

    def mirror_write(uc, _access, address, size, value, _user):
        for byte_index in range(size):
            current = address + byte_index
            mirror = (current - MEMORY_SIZE if current >= MEMORY_SIZE
                      else current + MEMORY_SIZE)
            uc.mem_write(mirror, bytes(((value >> (8 * byte_index)) & 255,)))

    def interrupt(uc, number, _user):
        raise AssertionError(f"{case['name']}: unexpected interrupt {number}")

    u.hook_add(UC_HOOK_CODE, code)
    u.hook_add(UC_HOOK_MEM_WRITE, mirror_write)
    u.hook_add(oracle.UC_HOOK_INTR, interrupt)
    u.emu_start(physical(regs['cs'], ENTRY), 0, count=1_000_000)
    if not done:
        raise AssertionError(f"{case['name']}: original exceeded the bounded instruction run")

    original_regs = {name: u.reg_read(reg) for name, reg in oracle.REG.items()}
    original_flags = u.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
    original_mem = bytes(u.mem_read(0, MEMORY_SIZE))
    if any(original_regs[name] != getattr(c_regs, name) for name in oracle.REG_NAMES):
        name = next(name for name in oracle.REG_NAMES
                    if original_regs[name] != getattr(c_regs, name))
        raise AssertionError(f"{case['name']}: {name} C={getattr(c_regs, name):04x}/"
                             f"original={original_regs[name]:04x}")
    flags_mask = ARITH | CONTROL
    if (original_flags ^ c_regs.flags) & flags_mask:
        raise AssertionError(f"{case['name']}: C and original defined flags differ")
    if bytes(c_mem) != original_mem:
        p = next(i for i, (left, right) in enumerate(zip(c_mem, original_mem))
                 if left != right)
        raise AssertionError(f"{case['name']}: whole RAM differs at {p:05x}")

    # Independent rectangle checks are kept away from DS/SS live-input aliases.
    if not case.get('stack_alias'):
        footprint, stale = independent_cells(mem, regs)
        for address in footprint:
            if original_mem[address] != 0x09:
                raise AssertionError(f"{case['name']}: expected cell byte 09 at {address:05x}")
        stack_words = set()
        if footprint:
            for delta in (2, 4):
                stack_words.update((physical(regs['ss'], regs['sp'] - delta),
                                    physical(regs['ss'], regs['sp'] - delta + 1)))
        for address in stale - footprint - stack_words:
            if original_mem[address] != mem[address]:
                raise AssertionError(f"{case['name']}: stale SS byte changed at {address:05x}")

    if case.get('check_mirror'):
        upper = bytes(u.mem_read(MEMORY_SIZE, MEMORY_SIZE))
        if upper != original_mem:
            raise AssertionError(f"{case['name']}: A20 mirror halves differ after writes")
    if collect_coverage:
        return sites, edges
    return None


def main():
    report = BUILD / 'steel-cells-differential.json'
    report.unlink(missing_ok=True)
    baseline, consumed_assets = cases()
    if ROUTINE['address'] != 0x3839 or ROUTINE['size'] != 102:
        raise AssertionError('Unexpected symbol-ledger extent for WriteSteelInteractionCells')
    if len(INS) != 47 or sum(ins.size for ins in INS.values()) != 102:
        raise AssertionError(f'Unexpected decoded extent: {len(INS)} sites, '
                             f'{sum(ins.size for ins in INS.values())} bytes')
    lib = library()
    sites, edges = set(), set()
    for case in baseline:
        case_sites, case_edges = run_case(lib, case, True)
        sites |= case_sites
        edges |= case_edges
    if sites != set(INS):
        raise AssertionError(f'Missing instruction sites: {sorted(set(INS) - sites)}')
    if edges != EDGES:
        raise AssertionError(f'Missing branch edges: {sorted(EDGES - edges)}')

    by_name = {case['name']: case for case in baseline}
    mutant_inputs = (
        (1, 'byte3-alone-keeps-record-active'),
        (2, 'x-bit7-contributes-one'),
        (3, 'dimensions-01'),
    )
    mutations = []
    for mutation, name in mutant_inputs:
        try:
            run_case(library(mutation), by_name[name])
        except AssertionError:
            mutations.append(dict(mutation=mutation, case=name))
        else:
            raise AssertionError(f'Compiled steel-cell mutation {mutation} survived on {name}')

    paths = ('c/steel_cells.c', 'c/steel_cells.h', 'c/regs.h', 'c/lemmings_sym.h',
             'tests/steel_cells.py', 'tests/dat_io.py', 'tools/common.py',
             'tools/cbuild.py', 'tools/difftest.py', 'tools/unpack.py',
             'tools/resources.py', 'metadata/symbols.json', 'metadata/inputs.json',
             'assets/vgalemmi.exe') + tuple(consumed_assets)
    public_cases = []
    for case in baseline:
        row = dict(name=case['name'], df=bool(case.get('df')), iflag=bool(case.get('iflag')))
        if case.get('real'):
            row.update(level_asset=case['level_asset'], section=case['section'])
        else:
            row.update(stack_alias=bool(case.get('stack_alias')),
                       physical_wrap=bool(case.get('ds') in (0xfff0, 0xffff) or
                                           case.get('ss') in (0, 0xffff)))
        public_cases.append(row)
    write_json(report, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(baseline), cases=public_cases,
        mutation_count=len(mutations), mutations_detected=mutations,
        translated_code_bytes=sum(ins.size for ins in INS.values()),
        instruction_addresses=sorted(INS), executed_instruction_addresses=sorted(sites),
        instruction_sites=sorted(sites), branch_instruction_addresses=sorted(BRANCHES),
        branch_edges=sorted(edges),
        routine=dict(name=ROUTINE['symbol_name'], start=ENTRY, end=END,
                     byte_count=END-ENTRY, bytes=IMAGE[ENTRY:END].hex(),
                     byte_sha256=sha(IMAGE[ENTRY:END])),
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
        consumed_level_assets=consumed_assets,
        fixture_domains=dict(single_active_positions=32, exhaustive_dimension_bytes=256,
            byte3_only_presence=True, firstword_ffff=True, df_ignored=True,
            stack_offsets=[0, 1, 0xffff], saved_bx_and_dx_aliases=True,
            ds_ss_live_definition_alias=True, live_ret_alias=True,
            a20_mirror_directions=['low-to-high', 'high-to-low'], real_level_sections=80),
        flag_notes='All arithmetic flags are defined by the final ADD DI,4; IF and DF '
                   'remain live and unchanged.',
        domain='Original bounded CS:3839..389E and C11 core; 32 live DS records, '
               'unchecked X and row offsets, byte3-sensitive presence, packed dimensions, '
               'live SS row saves, DS/SS aliases, 16-bit offsets and DOS 20-bit memory.'))
    print(f'PASS steel interaction cells C: {len(baseline)} cases, {len(sites)} '
          f'instruction sites, {len(edges)} branch edges; 3 compiled mutations detected')


if __name__ == '__main__':
    main()

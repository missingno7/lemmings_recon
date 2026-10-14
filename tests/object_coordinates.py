"""Type-one coordinate collection: bounded original ASM versus native C."""
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

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {row['symbol_name']: row for row in read_json(ROOT / 'metadata/symbols.json')}
ROUTINE = SYMS['CollectTypeOneObjectCoordinates']
ENTRY = ROUTINE['address']
END = ENTRY + ROUTINE['size']
DATA = {'definitions': SYMS['LevelObjectDefinitions']['address'],
        'coordinates': SYMS['TypeOneObjectCoordinates']['address']}
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
AF = 0x0010
DF = 0x0400
IF = 0x0200
CONTROL = DF | IF
MEM = ctypes.POINTER(ctypes.c_uint8)


class Regs(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in
                ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
                 'cs', 'ds', 'es', 'ss', 'ip', 'flags')]


def physical(segment, offset):
    return ((segment << 4) + (offset & 0xffff)) & 0xfffff


def get16(mem, segment, offset):
    return oracle.get16(mem, segment, offset)


def put16(mem, segment, offset, value):
    oracle.put16(mem, segment, offset, value)


def get_be16(mem, segment, offset):
    return (mem[physical(segment, offset)] << 8) | mem[physical(segment, offset + 1)]


def put_be16(mem, segment, offset, value):
    mem[physical(segment, offset)] = (value >> 8) & 255
    mem[physical(segment, offset + 1)] = value & 255


def synthetic_definitions(seed, matches=(), zero_x=(), coords=None, types=None):
    matches = set(matches)
    zero_x = set(zero_x)
    coords = coords or {}
    types = types or {}
    out = bytearray()
    for index in range(32):
        x_value, y_value = coords.get(index,
            ((seed * 313 + index * 719 + 0x1234) & 0xffff,
             (seed * 911 + index * 337 + 0x5678) & 0xffff))
        if index in zero_x:
            x_value = 0
        type_value = types.get(index, 1 if index in matches else 0x0101)
        out += x_value.to_bytes(2, 'big')
        out += y_value.to_bytes(2, 'big')
        out += type_value.to_bytes(2, 'big')
        out += bytes(((seed + index * 3) & 255, (seed ^ index * 11) & 255))
    assert len(out) == 32 * 8
    return bytes(out)


def cases():
    out = []

    def add(name, definitions, **kw):
        out.append(dict(name=name, seed=len(out), definitions=definitions, **kw))

    for count in range(33):
        add(f'match-count-{count:02d}', synthetic_definitions(
            0x389f + count, range(count)))
    for index in range(32):
        add(f'single-match-at-{index:02d}', synthetic_definitions(
            0x6100 + index, (index,)))
    add('zero-x-is-a-valid-match', synthetic_definitions(
        0x6200, (0,), zero_x=(0,)))
    add('be-type-0101-is-not-one', synthetic_definitions(
        0x6201, (), types={0: 0x0101}))
    add('be-type-0100-is-not-one', synthetic_definitions(
        0x6202, (), types={0: 0x0100}))
    add('coordinates-wrap-to-zero', synthetic_definitions(
        0x6203, (0,), coords={0: (0xffe8, 0xffe2)}))
    add('count-four-final-definition-is-nonmatch', synthetic_definitions(
        0x6204, range(4)))
    add('df-set-and-if-set', synthetic_definitions(0x6205, (3,)), df=True, iflag=True)
    add('df-clear-and-if-clear', synthetic_definitions(0x6206, (9,)), df=False, iflag=False)
    add('data-segment-a20-wrap', synthetic_definitions(0x6207, (0, 7)), ds=0xffff)
    add('data-segment-high-wrap', synthetic_definitions(0x6208, (1, 31)), ds=0xfff0)
    for sp in (0, 1, 0xffff):
        add(f'stack-offset-{sp:04x}', synthetic_definitions(0x6300 + sp, (2,)), sp=sp)
    add('ret-alias-single-pair', synthetic_definitions(
        0x6301, (0,), coords={0: (0xfee8, 0x3456)}), ds=0x3333, ss=0x3333,
        sp=DATA['coordinates'], return_word=0xaaaa)
    add('ret-alias-default-pair', synthetic_definitions(0x6302),
        ds=0x3333, ss=0x3333, sp=DATA['coordinates'], return_word=0xaaaa)

    consumed_assets = []
    for group in range(10):
        asset = f'assets/level{group:03d}.dat'
        packed = (ROOT / asset).read_bytes()
        spans = section_spans(packed)
        if len(spans) != 8:
            raise AssertionError(f'{asset}: expected 8 sections, found {len(spans)}')
        consumed_assets.append(asset)
        for section, (start, end) in enumerate(spans):
            record, _ = decode_section(packed[start:end])
            if len(record) != 2048:
                raise AssertionError(f'{asset} section {section}: unexpected record size')
            add(f'real-level-{group:03d}-section-{section:02d}', record[32:288])
    return out, consumed_assets


def prepare(case):
    rng = random.Random(0x389f + case['seed'])
    load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
    mem = bytearray(rng.randbytes(1 << 20))
    base = load << 4
    mem[base:base + len(IMAGE)] = relocated(IMAGE, ORACLE['relocations'], load)
    regs = {name: rng.randrange(65536) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=ENTRY, ds=case.get('ds', load + 0x09a9),
                ss=case.get('ss', 0x7000), sp=case.get('sp', 0x8000))
    definitions = case['definitions']
    if len(definitions) != 256:
        raise AssertionError(f"{case['name']}: expected 256 definition bytes")
    data_segment = regs['ds']
    for index, value in enumerate(definitions):
        mem[physical(data_segment, DATA['definitions'] + index)] = value
    flags = 2 | (rng.randrange(65536) & ARITH)
    if case.get('df', bool(case['seed'] & 1)):
        flags |= DF
    if case.get('iflag', bool(case['seed'] & 2)):
        flags |= IF
    put16(mem, regs['ss'], regs['sp'], case.get('return_word', 0xff00))
    return mem, regs, flags


def cmp16_flags(flags, left, right):
    result = (left - right) & 0xffff
    parity = 4 if (result & 255).bit_count() % 2 == 0 else 0
    out = (0x40 if result == 0 else 0) | (0x80 if result & 0x8000 else 0) | parity
    if left < right:
        out |= 1
    if (left ^ right ^ result) & 0x10:
        out |= AF
    if (left ^ right) & (left ^ result) & 0x8000:
        out |= 0x800
    return (flags & ~ARITH) | out


def independent_result(mem, regs, flags):
    expected = bytearray(mem)
    ds = regs['ds']
    si = DATA['definitions']
    bx = DATA['coordinates']
    ax = 0
    cx = 0
    selected = []

    for index in range(32):
        cursor = (si + index * 8) & 0xffff
        type_value = get_be16(mem, ds, (cursor + 4) & 0xffff)
        ax = type_value
        if type_value == 1:
            x_value = (get_be16(mem, ds, cursor) + 24) & 0xffff
            y_value = (get_be16(mem, ds, (cursor + 2) & 0xffff) + 30) & 0xffff
            put16(expected, ds, bx, x_value)
            put16(expected, ds, (bx + 2) & 0xffff, y_value)
            selected.append((x_value, y_value))
            bx = (bx + 4) & 0xffff
            ax = y_value

    bp = len(selected)
    cx = 0
    if bp == 0:
        ax = 0x0100
        cx = 0x0010
        put16(expected, ds, bx, ax)
        put16(expected, ds, (bx + 2) & 0xffff, cx)
        put16(expected, ds, (bx + 4) & 0xffff, ax)
        put16(expected, ds, (bx + 6) & 0xffff, cx)
        put16(expected, ds, (bx + 8) & 0xffff, ax)
        put16(expected, ds, (bx + 0x0a) & 0xffff, cx)
        put16(expected, ds, (bx + 0x0a) & 0xffff, ax)
        put16(expected, ds, (bx + 0x0e) & 0xffff, cx)
        outflags = (flags & ~ARITH) | 0x44
    elif bp == 1:
        ax, cx = selected[-1]
        for slot in (1, 2, 3):
            put16(expected, ds, (DATA['coordinates'] + 4 * slot) & 0xffff, ax)
            put16(expected, ds, (DATA['coordinates'] + 4 * slot + 2) & 0xffff, cx)
        outflags = cmp16_flags(flags, bp, 1)
    elif bp == 2:
        ax, cx = selected[-1]
        put16(expected, ds, (DATA['coordinates'] + 8) & 0xffff, ax)
        put16(expected, ds, (DATA['coordinates'] + 10) & 0xffff, cx)
        ax, cx = selected[0]
        put16(expected, ds, (DATA['coordinates'] + 12) & 0xffff, ax)
        put16(expected, ds, (DATA['coordinates'] + 14) & 0xffff, cx)
        outflags = cmp16_flags(flags, bp, 2)
    elif bp == 3:
        ax, cx = selected[1]
        put16(expected, ds, (DATA['coordinates'] + 12) & 0xffff, ax)
        put16(expected, ds, (DATA['coordinates'] + 14) & 0xffff, cx)
        outflags = cmp16_flags(flags, bp, 3)
    else:
        # The last definition body leaves either its type word or wrapped Y in AX.
        outflags = cmp16_flags(flags, bp, 3)

    out_regs = dict(regs)
    out_regs.update(ax=ax, bx=bx, cx=cx,
                    si=(DATA['definitions'] + 32 * 8) & 0xffff,
                    bp=bp,
                    ip=get16(expected, regs['ss'], regs['sp']),
                    sp=(regs['sp'] + 2) & 0xffff)
    return expected, out_regs, outflags


def load_library(mutation=0):
    lib = ctypes.CDLL(str(build(BUILD / f'object-coordinates-m{mutation}.dll',
                                mutation, 'object_coordinates')))
    lib.lmn_collect_type_one_object_coordinates_adapter.argtypes = [
        MEM, ctypes.POINTER(Regs)]
    lib.lmn_collect_type_one_object_coordinates_adapter.restype = None
    return lib


def run_case(lib, case):
    mem, regs, flags = prepare(case)
    expected, expected_regs, expected_flags = independent_result(mem, regs, flags)

    c_mem = bytearray(mem)
    c_regs = Regs(**regs, flags=flags)
    lib.lmn_collect_type_one_object_coordinates_adapter(
        (ctypes.c_uint8 * (1 << 20)).from_buffer(c_mem), ctypes.byref(c_regs))

    # A second 1 MiB mirror lets Unicorn execute segment accesses above 1 MiB;
    # the hook below keeps its writes consistent with the DOS 20-bit bus.
    doubled = bytes(mem) + bytes(mem)
    u = Uc(UC_ARCH_X86, UC_MODE_16)
    u.mem_map(0, 1 << 21)
    u.mem_write(0, doubled)
    for name, reg in oracle.REG.items():
        u.reg_write(reg, regs[name])
    u.reg_write(x.UC_X86_REG_EFLAGS, flags)
    sites = set()
    edges = set()
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
            raise AssertionError(f"{case['name']}: routine escaped to {offset & 0xffff:04x}")
        sites.add(offset)
        previous = offset

    def a20_wrap(uc, _access, address, size, value, _user):
        for byte_index in range(size):
            target = address + byte_index
            if target >= 1 << 20:
                uc.mem_write(target & 0xfffff,
                             bytes([(value >> (8 * byte_index)) & 255]))

    u.hook_add(UC_HOOK_CODE, code)
    u.hook_add(UC_HOOK_MEM_WRITE, a20_wrap)
    u.emu_start(physical(regs['cs'], ENTRY), 0, count=2000)
    if not done:
        raise AssertionError(f"{case['name']}: routine exceeded instruction budget")

    original_regs = {name: u.reg_read(reg) for name, reg in oracle.REG.items()}
    original_flags = u.reg_read(x.UC_X86_REG_EFLAGS) & 0xffff
    original_mem = bytes(u.mem_read(0, 1 << 20))
    for name in oracle.REG_NAMES:
        if original_regs[name] != expected_regs[name]:
            raise AssertionError(f"{case['name']}: original {name} differs from independent contract")
        if getattr(c_regs, name) != original_regs[name]:
            raise AssertionError(f"{case['name']}: C {name}={getattr(c_regs, name):04x}, "
                                 f"original={original_regs[name]:04x}")

    flags_mask = ARITH | CONTROL
    if expected_regs['bp'] == 0:
        flags_mask &= ~AF
    if (original_flags ^ expected_flags) & flags_mask:
        raise AssertionError(f"{case['name']}: original defined flags differ from independent contract")
    if (c_regs.flags ^ original_flags) & flags_mask:
        raise AssertionError(f"{case['name']}: C defined flags differ from original")
    if original_mem != bytes(expected):
        p = next(i for i, (a, b) in enumerate(zip(original_mem, expected)) if a != b)
        raise AssertionError(f"{case['name']}: original whole RAM differs at {p:05x}")
    if bytes(c_mem) != original_mem:
        p = next(i for i, (a, b) in enumerate(zip(bytes(c_mem), original_mem)) if a != b)
        raise AssertionError(f"{case['name']}: C whole RAM differs at {p:05x}")
    return sites, edges


def main():
    report = BUILD / 'object-coordinates-differential.json'
    report.unlink(missing_ok=True)
    baseline, consumed_assets = cases()
    lib = load_library()
    sites, edges = set(), set()
    for case in baseline:
        case_sites, case_edges = run_case(lib, case)
        sites |= case_sites
        edges |= case_edges
    if sites != set(INS):
        raise AssertionError(f'Missing instruction sites: {sorted(set(INS) - sites)}')
    if edges != EDGES:
        raise AssertionError(f'Missing branch edges: {sorted(EDGES - edges)}')

    mutant_inputs = (
        (1, 'match-count-00'),
        (2, 'match-count-32'),
        (3, 'zero-x-is-a-valid-match'),
    )
    mutations = []
    by_name = {case['name']: case for case in baseline}
    for mutation, name in mutant_inputs:
        try:
            run_case(load_library(mutation), by_name[name])
        except AssertionError:
            mutations.append(dict(mutation=mutation, case=name))
        else:
            raise AssertionError(f'Compiled mutation {mutation} survived on {name}')

    paths = ('c/object_coordinates.c', 'c/object_coordinates.h', 'c/regs.h',
             'c/lemmings_sym.h', 'tests/object_coordinates.py', 'tools/cbuild.py',
             'tools/difftest.py', 'metadata/symbols.json', 'metadata/inputs.json')
    paths += tuple(consumed_assets)
    write_json(report, dict(image='main', image_sha256=sha(IMAGE),
        case_count=len(baseline), cases=[case['name'] for case in baseline],
        mutation_count=len(mutations), mutations_detected=mutations,
        translated_code_bytes=sum(ins.size for ins in INS.values()),
        instruction_addresses=sorted(INS),
        executed_instruction_addresses=sorted(sites),
        instruction_sites=sorted(sites), branch_instruction_addresses=sorted(BRANCHES),
        branch_edges=sorted(edges),
        routine=dict(name='CollectTypeOneObjectCoordinates', start=ENTRY, end=END,
                     byte_count=END-ENTRY, bytes=IMAGE[ENTRY:END].hex(),
                     byte_sha256=sha(IMAGE[ENTRY:END])),
        input_hashes={path: sha((ROOT / path).read_bytes()) for path in paths},
        consumed_level_assets=consumed_assets,
        flag_notes='AF is excluded only when selected_count is zero because AND BP,BP leaves AF undefined; all other arithmetic flags and incoming DF/IF are compared.',
        domain='32 live big-endian eight-byte definitions; exact type-one scan and ' \
               'count-specific replication; wrapped coordinates; full RAM, all boundary ' \
               'registers, defined arithmetic flags, DF/IF preservation, 20-bit physical ' \
               'wrapping and post-write live RET reads'))
    print(f'PASS object coordinates C: {len(baseline)} cases, {len(sites)} instruction sites, '
          f'{len(edges)} branch edges; {len(mutations)} compiled mutations detected')


if __name__ == '__main__':
    main()

"""Original-only bounded contract for the DAT cache allocation candidate.

Runs the pinned instructions at 1ED7..1F18 with a constructed INT 21h/AH=48h
provider and an independent logical state model. It neither invokes C nor boots
the game; this contract is not evidence that the candidate is reachable.
"""
import gc
import hashlib
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
from aligned_masked import TraceDevice
from bounded_process import run_bounded
from common import ROOT, BUILD, read_json, sha, write_json
import drawing_caller_oracle as original_caller
import terrain_drawing as piece
from unpack import ASSET, unpack, relocated


START = 0x1ED7
END = 0x1F19
THRESHOLD = 0x0C80
CODE_BYTES = 66
DEFINED_FLAGS = 0x0FC7  # arithmetic flags except undefined AF, plus TF/IF/DF
ARITHMETIC_FLAGS = 0x08D5  # CF/PF/AF/ZF/SF/OF
LOGICAL_FLAGS = 0x08C5  # CF/PF/ZF/SF/OF; AF remains undefined
FLAG_CF = 0x0001
FLAG_PF = 0x0004
FLAG_AF = 0x0010
FLAG_ZF = 0x0040
FLAG_SF = 0x0080
FLAG_TF = 0x0100
FLAG_IF = 0x0200
FLAG_DF = 0x0400
FLAG_OF = 0x0800
OUTPUT_WORDS = (0x1F80, 0x1F82, 0x1F84, 0x1F86, 0x1F88,
                0x1F8A, 0x1F8C, 0x1F8E, 0x1F90)
OUTPUT_BYTES = (0x1F92, 0x1F93, 0x1F94)
LOADS = (0x1010, 0x1213, 0x2345)
MAX_INSTRUCTIONS = 100
MAX_BUS_EVENTS = 128
MAX_DEVICE_EVENTS = 128
RET_SEED = 0xBEEF
PINNED_IMAGE_SHA256 = 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e'
PINNED_CODE = bytes.fromhex(
    'b448bbffffcd2181fb800c722f891e8e1f891e901fb448cd21a3801fa3841fa3881f'
    'a38c1f33c0a3821fa3861fa38a1fa2921fa2941fb0ffa2931fc332c0a2931fc3')

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
IMAGE, ORACLE = unpack(ASSET.read_bytes())
REPORT_PATH = BUILD / 'cache-allocation-contract-original.json'


class ContractFailure(AssertionError):
    """A completed original execution disagreed with the logical model."""


def require(condition, message):
    if not condition:
        raise ContractFailure(message)


def physical(segment, offset):
    return (((segment << 4) + (offset & 0xFFFF)) & 0xFFFFF)


def read_word(memory, segment, offset):
    address = physical(segment, offset)
    return memory[address] | (memory[(address + 1) & 0xFFFFF] << 8)


def write_word(memory, segment, offset, value):
    address = physical(segment, offset)
    memory[address] = value & 0xFF
    memory[(address + 1) & 0xFFFFF] = (value >> 8) & 0xFF


def sub16_flags(flags, left, right):
    value = (left - right) & 0xFFFF
    result = flags & ~ARITHMETIC_FLAGS
    if left < right:
        result |= FLAG_CF
    if (value & 0xFF).bit_count() % 2 == 0:
        result |= FLAG_PF
    if (left ^ right ^ value) & 0x10:
        result |= FLAG_AF
    if value == 0:
        result |= FLAG_ZF
    if value & 0x8000:
        result |= FLAG_SF
    if ((left ^ right) & (left ^ value) & 0x8000) != 0:
        result |= FLAG_OF
    return result & 0xFFFF


def xor_zero_flags(flags):
    # XOR clears CF/OF, sets PF/ZF, clears SF; AF is undefined and not compared.
    return ((flags & ~LOGICAL_FLAGS) | FLAG_PF | FLAG_ZF) & 0xFFFF


def provider_flags(case, stage):
    if stage == 0:
        carry = case['first_cf']
        df, iff = case['first_df'], case['first_if']
        pattern = case['first_status']
    else:
        carry = case['second_cf']
        df, iff = case['second_df'], case['second_if']
        pattern = case['second_status']
    flags = 0x0002 | pattern | (FLAG_CF if carry else 0)
    flags |= FLAG_DF if df else 0
    flags |= FLAG_IF if iff else 0
    return flags & 0xFFFF


def static_instructions():
    require(sha(IMAGE) == PINNED_IMAGE_SHA256,
            'unpacked image differs from the pinned executable identity')
    require(len(PINNED_CODE) == CODE_BYTES,
            f'pinned literal has {len(PINNED_CODE)} bytes, expected {CODE_BYTES}')
    require(IMAGE[START:END] == PINNED_CODE,
            'candidate bytes differ from the pinned literal')

    symbols = read_json(ROOT / 'metadata/symbols.json')
    by_name = {row.get('symbol_name'): row for row in symbols}
    routine = by_name.get('AllocateDatCache')
    require(routine is not None and
            (routine.get('address'), routine.get('size')) == (START, CODE_BYTES),
            'symbol ledger no longer identifies the pinned routine interval')
    paragraphs = by_name.get('DatCacheRequestedParagraphs')
    require(paragraphs is not None and paragraphs.get('address') == 0x1F8E,
            'symbol ledger no longer identifies the first returned paragraph field')

    decoded = tuple(MD.disasm(PINNED_CODE, START))
    require(len(decoded) == 25, f'expected 25 decoded sites, got {len(decoded)}')
    cursor = START
    for instruction in decoded:
        require(instruction.address == cursor,
                f'decode gap at {cursor:04X}, got {instruction.address:04X}')
        cursor += instruction.size
    require(cursor == END, f'decode stopped at {cursor:04X}, expected {END:04X}')
    branch = next((i for i in decoded if i.mnemonic == 'jb'), None)
    require(branch is not None and branch.address == 0x1EE2 and
            branch.operands[0].imm == 0x1F13,
            'unsigned threshold branch no longer matches the static contract')
    instructions = {i.address: i for i in decoded}
    branch_edges = {(branch.address, 0x1F13),
                    (branch.address, branch.address + branch.size)}
    return instructions, branch_edges


def scenarios():
    result = []

    def add(name, returned_bx, first_cf, df, iff, *, second_ax=None,
            second_cf=0, ss=0x7000, sp=0x8F20, ds=0x3000,
            alias_kind=None):
        seed = len(result)
        result.append(dict(
            name=name, seed=seed, returned_bx=returned_bx,
            first_cf=first_cf, second_cf=second_cf,
            initial_df=df, initial_if=iff,
            first_df=1 - df, first_if=1 - iff,
            second_df=df, second_if=1 - iff,
            first_status=((seed * 0x35) & (FLAG_PF | FLAG_AF | FLAG_ZF |
                          FLAG_SF | FLAG_OF)),
            second_status=((seed * 0x59 + 0x84) &
                           (FLAG_PF | FLAG_AF | FLAG_ZF | FLAG_SF | FLAG_OF)),
            second_ax=second_ax, ss=ss, sp=sp, ds=ds,
            alias_kind=alias_kind))

    # Cross all threshold values with first DOS carry and input DF/IF states.
    # Large allocations also cross both second AX outcomes and its carry bit.
    for returned_bx in (0x0000, 0x0C7F, 0x0C80, 0xFFFF):
        for first_cf in (0, 1):
            for df in (0, 1):
                for iff in (0, 1):
                    if returned_bx < THRESHOLD:
                        add(f'below-{returned_bx:04X}-cf{first_cf}-df{df}-if{iff}',
                            returned_bx, first_cf, df, iff)
                    else:
                        for second_ax in (0x0008, (0x4200 | (len(result) & 0xFF))):
                            for second_cf in (0, 1):
                                add(f'large-{returned_bx:04X}-cf{first_cf}-df{df}-if{iff}'
                                    f'-ax{second_ax:04X}-cf2{second_cf}',
                                    returned_bx, first_cf, df, iff,
                                    second_ax=second_ax, second_cf=second_cf)

    # Each large-path store is allowed to overwrite the caller's real RET word.
    for offset in (0x1F80, 0x1F82, 0x1F8E, 0x1F92, 0x1F93, 0x1F94):
        seed = len(result)
        add(f'large-live-ret-{offset:04X}', 0x0C80, 1, seed & 1,
            (seed >> 1) & 1, second_ax=0x0008, second_cf=1,
            ss=0x3500, ds=0x3500, sp=offset, alias_kind='large-output')
    seed = len(result)
    add('small-live-ret-1F93', 0x0000, 0, seed & 1, (seed >> 1) & 1,
        ss=0x3500, ds=0x3500, sp=0x1F93, alias_kind='small-enable-byte')

    add('stack-offset-wrap-SP-FFFF', 0xFFFF, 0, 1, 0,
        second_ax=0xA55A, second_cf=1, ss=0x7000, ds=0x3000,
        sp=0xFFFF, alias_kind='SP-wrap')
    add('physical-word-wrap-SS-FFFF-SP-000F', 0x0C80, 1, 0, 1,
        second_ax=0x0008, second_cf=0, ss=0xFFFF, ds=0x3000,
        sp=0x000F, alias_kind='A20-word-successor')
    return result


def prepare(case, load):
    seed = case['seed'] * 17 + LOADS.index(load)
    rng = random.Random(0x1ED7CACE + seed)
    memory = bytearray(rng.randbytes(1 << 20))
    loaded = relocated(IMAGE, ORACLE['relocations'], load)
    memory[load << 4:(load << 4) + len(loaded)] = loaded

    registers = {name: rng.randrange(0x10000)
                 for name in piece.oracle.REG_NAMES}
    initial_al = (0x31 + case['seed'] * 17) & 0xFF
    registers.update(ax=0xA500 | initial_al, bx=rng.randrange(0x10000),
                     cs=load, ip=START, ds=case['ds'], es=0x6200,
                     ss=case['ss'], sp=case['sp'])
    flags = (0x0002 | (FLAG_DF if case['initial_df'] else 0) |
             (FLAG_IF if case['initial_if'] else 0) |
             ((case['seed'] * 0x35) & (FLAG_CF | FLAG_PF | FLAG_AF |
                                        FLAG_ZF | FLAG_SF | FLAG_OF)))
    return_word = (RET_SEED ^ ((case['seed'] * 0x31) & 0xFFFF)) & 0xFFFF
    write_word(memory, registers['ss'], registers['sp'], return_word)
    return memory, registers, flags, return_word


def logical_expected(case, memory, registers, flags, initial_return):
    expected_memory = bytearray(memory)
    expected_registers = dict(registers)
    ds, ss, sp = registers['ds'], registers['ss'], registers['sp']
    initial_al = registers['ax'] & 0xFF
    first_input_ax = 0x4800 | initial_al
    first_ax = 0xA500 | (initial_al ^ 0x5A)
    first_bx = case['returned_bx']
    first_flags = provider_flags(case, 0)
    calls = [dict(function=0x48, interrupt=0x21,
                  incoming_ax=first_input_ax, incoming_bx=0xFFFF,
                  incoming_flags=flags & 0xFFFF,
                  returned_ax=first_ax, returned_bx=first_bx,
                  returned_flags=first_flags)]
    writes = []
    expected_registers.update(ax=first_ax, bx=first_bx)

    if first_bx < THRESHOLD:
        expected_memory[physical(ds, 0x1F93)] = 0
        writes.append(dict(offset=0x1F93, size=1, value=0))
        expected_registers['ax'] = first_ax & 0xFF00
        final_flags = xor_zero_flags(first_flags)
        branch_taken = True
    else:
        write_word(expected_memory, ds, 0x1F8E, first_bx)
        write_word(expected_memory, ds, 0x1F90, first_bx)
        writes.extend((dict(offset=0x1F8E, size=2, value=first_bx),
                       dict(offset=0x1F90, size=2, value=first_bx)))

        compare_flags = sub16_flags(first_flags, first_bx, THRESHOLD)
        second_input_ax = 0x4800 | (first_ax & 0xFF)
        second_ax = case['second_ax']
        second_bx = (0x9C37 + case['seed'] * 11) & 0xFFFF
        second_flags = provider_flags(case, 1)
        calls.append(dict(function=0x48, interrupt=0x21,
                          incoming_ax=second_input_ax, incoming_bx=first_bx,
                          incoming_flags=compare_flags,
                          returned_ax=second_ax, returned_bx=second_bx,
                          returned_flags=second_flags))
        for offset in (0x1F80, 0x1F84, 0x1F88, 0x1F8C):
            write_word(expected_memory, ds, offset, second_ax)
            writes.append(dict(offset=offset, size=2, value=second_ax))
        for offset in (0x1F82, 0x1F86, 0x1F8A):
            write_word(expected_memory, ds, offset, 0)
            writes.append(dict(offset=offset, size=2, value=0))
        for offset in (0x1F92, 0x1F94):
            expected_memory[physical(ds, offset)] = 0
            writes.append(dict(offset=offset, size=1, value=0))
        expected_memory[physical(ds, 0x1F93)] = 0xFF
        writes.append(dict(offset=0x1F93, size=1, value=0xFF))
        expected_registers.update(ax=0x00FF, bx=second_bx)
        final_flags = xor_zero_flags(second_flags)
        branch_taken = False

    # RET reads the word only after all aliased DS stores and wraps its high
    # byte at the 20-bit physical successor; SP itself advances modulo 16 bits.
    returned_ip = read_word(expected_memory, ss, sp)
    expected_registers['ip'] = returned_ip
    expected_registers['sp'] = (sp + 2) & 0xFFFF
    return dict(memory=expected_memory, registers=expected_registers,
                flags=final_flags, calls=calls, writes=writes,
                branch_taken=branch_taken, initial_return=initial_return,
                returned_ip=returned_ip)


def dos_provider(case, actual_calls):
    def interrupt(cpu, number, _device):
        require(number == 0x21,
                f"{case['name']}: unexpected INT {number:02X}")
        ax = cpu.reg_read(piece.oracle.REG['ax']) & 0xFFFF
        bx = cpu.reg_read(piece.oracle.REG['bx']) & 0xFFFF
        flags = cpu.reg_read(piece.x.UC_X86_REG_EFLAGS) & 0xFFFF
        call_index = len(actual_calls)
        require((ax >> 8) == 0x48,
                f"{case['name']}: AH={ax >> 8:02X}, expected DOS AH=48")
        if call_index == 0:
            require(bx == 0xFFFF,
                    f"{case['name']}: first allocator BX={bx:04X}, expected FFFF")
            returned = (0xA500 | ((case['initial_al'] ^ 0x5A) & 0xFF),
                        case['returned_bx'], provider_flags(case, 0))
        elif call_index == 1:
            require(case['returned_bx'] >= THRESHOLD,
                    f"{case['name']}: second allocation on undersized first result")
            require(bx == case['returned_bx'],
                    f"{case['name']}: second allocator BX={bx:04X}, expected "
                    f"{case['returned_bx']:04X}")
            require((ax & 0xFF) == (case['first_return_ax'] & 0xFF),
                    f"{case['name']}: second allocation did not receive prior AL")
            returned = (case['second_ax'],
                        (0x9C37 + case['seed'] * 11) & 0xFFFF,
                        provider_flags(case, 1))
        else:
            raise ContractFailure(f"{case['name']}: unexpected extra DOS allocation")
        actual_calls.append(dict(function=ax >> 8, interrupt=number,
                                 incoming_ax=ax, incoming_bx=bx,
                                 incoming_flags=flags,
                                 returned_ax=returned[0], returned_bx=returned[1],
                                 returned_flags=returned[2]))
        # INT 21h/AH=48h fixture owns exactly AX, BX and FLAGS.
        cpu.reg_write(piece.oracle.REG['ax'], returned[0])
        cpu.reg_write(piece.oracle.REG['bx'], returned[1])
        cpu.reg_write(piece.x.UC_X86_REG_EFLAGS, returned[2])
    return interrupt


def case_with_load(case, load):
    value = dict(case)
    value['load'] = load
    value['name'] = f"{case['name']}-load-{load:04X}"
    value['initial_al'] = (0x31 + case['seed'] * 17) & 0xFF
    value['first_return_ax'] = 0xA500 | (value['initial_al'] ^ 0x5A)
    if value['second_ax'] is None:
        value['second_ax'] = 0
    return value


def run_case(case, instructions):
    memory, registers, flags, initial_return = prepare(case, case['load'])
    expected = logical_expected(case, memory, registers, flags, initial_return)
    original_device = TraceDevice(bytearray(memory), 0xCA110C + case['seed'])
    actual_calls = []
    actual, mask, sites, edges, boundary, _child, _body = original_caller.original(
        case, original_device, registers, flags, instructions=instructions,
        far_calls=set(), continuations=(), max_steps=MAX_INSTRUCTIONS,
        interrupt=dos_provider(case, actual_calls))

    require(boundary[0] == 'outer-return' and boundary[1] == case['load'] and
            actual['ip'] == expected['returned_ip'],
            f"{case['name']}: wrong actual RET boundary {boundary!r}")
    require(mask == DEFINED_FLAGS,
            f"{case['name']}: final defined flag mask {mask:04X}, expected {DEFINED_FLAGS:04X}")
    for name in piece.oracle.REG_NAMES:
        require(actual[name] == expected['registers'][name],
                f"{case['name']}: {name.upper()}={actual[name]:04X}, expected "
                f"{expected['registers'][name]:04X}")
    require(((actual['flags'] ^ expected['flags']) & DEFINED_FLAGS) == 0,
            f"{case['name']}: defined EFLAGS differ")
    require(original_device.memory == expected['memory'],
            f"{case['name']}: complete canonical RAM differs from logical model")
    require(actual_calls == expected['calls'],
            f"{case['name']}: DOS provider call order/inputs/outputs differ")
    require(len(sites) <= MAX_INSTRUCTIONS,
            f"{case['name']}: executed more than {MAX_INSTRUCTIONS} instructions")
    expected_count = 8 if expected['branch_taken'] else 22
    require(len(sites) == expected_count,
            f"{case['name']}: executed {len(sites)} sites, expected {expected_count}")
    require(len(actual_calls) == (1 if expected['branch_taken'] else 2),
            f"{case['name']}: wrong DOS allocation call count")
    if expected['branch_taken']:
        require(len(expected['writes']) == 1 and
                expected['writes'][0]['offset'] == 0x1F93,
                f"{case['name']}: undersized path wrote stale cache fields")
    else:
        require(read_word(expected['memory'], case['ds'], 0x1F8E) ==
                case['returned_bx'] and
                read_word(expected['memory'], case['ds'], 0x1F90) ==
                case['returned_bx'],
                f"{case['name']}: returned BX was not published")
        if case['second_ax'] == 0x0008:
            require(all(read_word(expected['memory'], case['ds'], offset) == 0x0008
                        for offset in (0x1F80, 0x1F84, 0x1F88, 0x1F8C)) and
                    expected['memory'][physical(case['ds'], 0x1F93)] == 0xFF,
                    f"{case['name']}: failed second allocation was not published/enabled")
    code_at = physical(case['load'], START)
    expected_code = relocated(IMAGE, ORACLE['relocations'], case['load'])[START:END]
    require(original_device.memory[code_at:code_at + CODE_BYTES] ==
            expected_code,
            f"{case['name']}: candidate code bytes changed during execution")
    original_device.check(case['name'])

    return dict(
        name=case['name'], load_segment=f"{case['load']:04X}",
        threshold_result=f"{case['returned_bx']:04X}",
        branch='below-threshold' if expected['branch_taken'] else 'allocate-cache',
        alias_kind=case['alias_kind'],
        first_cf=case['first_cf'], second_cf=(case['second_cf']
                                               if not expected['branch_taken'] else None),
        second_ax=(f"{case['second_ax']:04X}"
                   if not expected['branch_taken'] else None),
        provider_calls=actual_calls,
        executed_sites=sorted(f"{site:04X}" for site in sites),
        branch_edges=[[f"{src:04X}", f"{dst:04X}"]
                      for src, dst in sorted(edges)],
        initial_return=f"{initial_return:04X}",
        returned_ip=f"{actual['ip']:04X}",
        return_word_changed=actual['ip'] != initial_return,
        final_registers={name: f"{actual[name]:04X}"
                         for name in piece.oracle.REG_NAMES},
        final_flags=f"{actual['flags'] & DEFINED_FLAGS:04X}",
        defined_flag_mask=f"{mask:04X}",
        initial_ram_sha256=sha(memory),
        final_ram_sha256=sha(original_device.memory),
        full_ram_matches=True,
        logical_stores=[dict(offset=f"{row['offset']:04X}", size=row['size'],
                             value=f"{row['value']:0{row['size'] * 2}X}")
                        for row in expected['writes']],
        low_path_cache_fields_stale=(
            expected['branch_taken'] and
            all(row['offset'] == 0x1F93 for row in expected['writes'])))


def loaded_input_paths():
    # Preserve executable/contract inputs, excluding unrelated progress prose.
    paths = {
        'tests/cache_allocation_contract.py',
        'src/game_code.asm', 'src/resources.asm', 'src/image_tail.asm',
        'src/entry_services.asm', 'src/program.asm',
        'metadata/symbols.json', 'metadata/oracle.json',
        'metadata/inputs.json', 'metadata/toolchain-lock.json',
        'assets/vgalemmi.exe', 'tools/unpack.py',
        'tools/bounded_process.py', 'tools/common.py',
        'tests/drawing_caller_oracle.py', 'tests/terrain_drawing.py',
        'tests/aligned_masked.py', 'tests/minimap_vga.py', 'tests/dat_io.py',
    }
    roots = ((ROOT / 'tests').resolve(), (ROOT / 'tools').resolve())
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if not filename:
            continue
        try:
            path = Path(filename).resolve()
            relative = path.relative_to(ROOT.resolve()).as_posix()
        except (OSError, RuntimeError, ValueError):
            continue
        if path.suffix == '.py' and any(path.is_relative_to(root) for root in roots):
            paths.add(relative)
    return tuple(sorted(paths))


def input_hashes():
    return {path: sha((ROOT / path).read_bytes()) for path in loaded_input_paths()}


def check():
    import aligned_masked as aligned

    # Tight traces are ample for this 25-site routine and turn unexpected
    # accesses or runaway execution into failures, never evidence of a quirk.
    aligned.MAX_BUS_EVENTS = MAX_BUS_EVENTS
    aligned.MAX_VGA_EVENTS = MAX_DEVICE_EVENTS
    piece.common.MAX_VGA_EVENTS = MAX_DEVICE_EVENTS
    instructions, expected_edges = static_instructions()
    before = input_hashes()
    result_rows = []
    all_sites, all_edges = set(), set()
    branch_counts = {'below-threshold': 0, 'allocate-cache': 0}
    case_specs = scenarios()
    for spec in case_specs:
        for load in LOADS:
            case = case_with_load(spec, load)
            row = run_case(case, instructions)
            result_rows.append(row)
            all_sites.update(int(site, 16) for site in row['executed_sites'])
            all_edges.update((int(edge[0], 16), int(edge[1], 16))
                             for edge in row['branch_edges'])
            branch_counts[row['branch']] += 1
            gc.collect()

    expected_sites = set(instructions)
    require(all_sites == expected_sites,
            f"executed site union differs: missing={expected_sites-all_sites}, "
            f"extra={all_sites-expected_sites}")
    require(all_edges == expected_edges,
            f"branch outcomes differ: expected={expected_edges}, actual={all_edges}")
    require(branch_counts == {'below-threshold': 51, 'allocate-cache': 216},
            f"unexpected branch outcome counts: {branch_counts}")
    after = input_hashes()
    require(before == after, 'cache-allocation contract inputs changed during execution')

    report = dict(
        evidence_kind='original-only-cache-allocation-contract',
        c_coverage_claimed=False,
        reachability_proven=False,
        classification_performed_by_test=False,
        bytes_reclassified_by_test=0,
        native_c_coverage_added=0,
        routine=dict(start=f'{START:04X}', end_exclusive=f'{END:04X}',
                     byte_count=CODE_BYTES, decoded_sites=len(instructions),
                     image_sha256=sha(IMAGE), raw_bytes=PINNED_CODE.hex(),
                     executed_original_sites=sorted(f'{site:04X}' for site in all_sites)),
        case_count=len(result_rows), cases=result_rows,
        branch_outcomes={
            'tested_branch': '1EE2 JB 1F13 iff returned BX < 0C80',
            'counts': branch_counts,
            'edges': [[f'{source:04X}', f'{target:04X}']
                      for source, target in sorted(all_edges)]},
        quirks=[
            'MOV AH,48 preserves incoming AL on the first allocator request.',
            'First allocator BX is FFFF; returned BX is compared unsigned with 0C80.',
            'Both DOS carry results are ignored; a second AX=0008 is still published.',
            'The small path clears only DS:1F93 and preserves returned AX high byte and other cache fields.',
            'The large path stores first returned BX at DS:1F8E and DS:1F90, then passes prior returned AL to the second AH=48 request.',
            'The large path publishes second AX to DS:1F80/1F84/1F88/1F8C and enables the cache even for AX=0008.',
            'All stores precede the real near RET; DS=SS aliases can change its target, and SP advances modulo 16 bits.',
            'Near-return word high bytes use physical+1 with 20-bit wrap.'
        ],
        provider_contract=dict(interrupt='INT 21h', function='AH=48h',
                               outputs=['AX', 'BX', 'EFLAGS'],
                               other_registers_preserved=True,
                               memory_side_effects=False),
        limits=dict(instructions_per_case=MAX_INSTRUCTIONS,
                    coordinator_timeout_seconds=60,
                    windows_process_commit_mib=256),
        input_sha256=before)
    write_json(REPORT_PATH, report)
    return dict(case_count=len(result_rows), decoded_sites=len(instructions),
                executed_sites=len(all_sites), branch_edges=len(all_edges),
                branch_outcomes=branch_counts, input_sha256=after,
                c_coverage=0, reachability_proven=False,
                bytes_reclassified_by_test=0)


def worker():
    metrics = check()
    print(f"PASS original-only cache allocation: {metrics['case_count']} cases, "
          f"{metrics['executed_sites']} sites, {metrics['branch_edges']} branch outcomes; "
          'zero C coverage')


def main():
    if len(sys.argv) == 2 and sys.argv[1] == '--bounded-worker':
        worker()
        return
    if len(sys.argv) != 1:
        raise SystemExit('Unexpected cache-allocation contract arguments')
    BUILD.mkdir(exist_ok=True)
    REPORT_PATH.unlink(missing_ok=True)
    run_bounded([sys.executable, str(Path(__file__).resolve()), '--bounded-worker'],
                cwd=ROOT, check=True, timeout=60, memory_mib=256)


if __name__ == '__main__':
    main()

"""Bounded original-vs-C checks for the ten- and thirteen-row mask leaves."""
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
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, read_json, sha, write_json
from dat_io import REG_NAMES
import entity_mask as helpers
from unpack import ASSET
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN)
from unicorn import x86_const as x


IMAGE, ORACLE = helpers.IMAGE, helpers.ORACLE
LOAD = helpers.LOAD
MEMORY_SIZE = helpers.MEMORY_SIZE
MEMORY_MASK = helpers.MEMORY_MASK
DATA_SEGMENT = helpers.DATA_SEGMENT
RESOURCE_SEGMENT = 0x6200
BUFFER_SEGMENT = 0x7000
ALTERNATE_BUFFER_SEGMENT = 0x7100
TEN, THIRTEEN = 'ten', 'thirteen'
SPECS = {
    TEN: dict(name='DrawTenRowEntityMask', entry=0x5FAC, ret=0x606A,
              rows=10, byte_count=191, site_count=88),
    THIRTEEN: dict(name='DrawThirteenRowEntityMask', entry=0x606B,
                   ret=0x6140, rows=13, byte_count=214, site_count=99),
}
for spec in SPECS.values():
    spec['end'] = spec['ret'] + 1
    spec['code'] = IMAGE[spec['entry']:spec['end']]

MAX_EVENTS = 2048
MAX_INSTRUCTIONS = 1400
GUARD_EXIT, CALLBACK_EXIT = helpers.GUARD_EXIT, helpers.CALLBACK_EXIT
FLAGS = helpers.INITIAL_DEFINED_FLAGS
TF = 0x0100
CF, PF, AF, ZF, SF, IF, DF, OF = (
    helpers.CF, helpers.PF, helpers.AF, helpers.ZF, helpers.SF,
    helpers.IF, helpers.DF, helpers.OF)
REPORT = BUILD / 'entity-mask-rows-differential.json'
REGS = REG_NAMES
REG_ID = {name: getattr(x, 'UC_X86_REG_' + name.upper()) for name in REGS}
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
INS = {key: {ins.address: ins for ins in MD.disasm(spec['code'], spec['entry'])}
       for key, spec in SPECS.items()}
BRANCHES = {key: {pc for pc, ins in insns.items()
                  if ins.group(capstone.CS_GRP_JUMP) or
                  ins.mnemonic.startswith('loop')}
            for key, insns in INS.items()}
EXPECTED_EDGES = {
    (0x6009, 0x600B), (0x6009, 0x600F),
    (0x6065, 0x6030), (0x6065, 0x6067),
    (0x60B1, 0x60B3), (0x60B1, 0x60BA),
    (0x60E0, 0x60E2), (0x60E0, 0x60E6),
    (0x613B, 0x6106), (0x613B, 0x613D),
}
ALL_SITES = set(INS[TEN]) | set(INS[THIRTEEN])


class RowsCall(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'data_segment', 'stack_segment', 'stack_offset', 'record_cursor',
        'selection', 'alignment_index', 'flags')]


class RowsResult(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'value', 'mask_word', 'row_count', 'port', 'source_cursor',
        'destination_offset', 'data_segment', 'output_segment',
        'stack_offset', 'alignment_index', 'flags')]


class VerificationFailure(RuntimeError):
    """A finite original execution or input-fixture budget failed."""


class NativeMismatch(AssertionError):
    """A completed bounded native comparison differs from original ASM."""


def oracle_require(condition, message):
    if not condition:
        raise VerificationFailure(message)


def require(condition, message):
    if not condition:
        raise NativeMismatch(message)


def spec_for(entry):
    return SPECS[entry]


def put_byte(memory, segment, offset, value):
    memory[helpers.physical(segment, offset)] = value & 0xFF


def put_bytes(memory, segment, offset, values):
    address = helpers.physical(segment, offset)
    values = bytes(values)
    first = min(len(values), MEMORY_SIZE - address)
    memory[address:address + first] = values[:first]
    if first < len(values):
        memory[:len(values) - first] = values[first:]


def read_byte(memory, segment, offset):
    return memory[helpers.physical(segment, offset)]


def deterministic_byte(seed, index):
    return (seed * 73 + index * 151 + (index >> 2) * 19 + 0xA7) & 0xFF


def producer_raw_words(seed):
    return [helpers.source_word(seed, index) for index in range(154)]


def expected_bank(words):
    return bytes(byte for shift in range(8) for word in words
                 for byte in helpers.shifted_word_mask(word, shift))


def put_row_banks(memory, segment, seed):
    """Independent 5CDD shift-chain banks for ordinary ten/thirteen calls."""
    for selection in range(8):
        words = [helpers.source_word(seed, selection * 10 + row)
                 for row in range(10)]
        put_bytes(memory, segment, selection * 240, expected_bank(words))
    for selection in range(4):
        words = [helpers.source_word(seed, 80 + selection * 13 + row)
                 for row in range(13)]
        put_bytes(memory, segment, 0x780 + selection * 312,
                  expected_bank(words))


def seed_producer_source(memory, data_segment, seed):
    words = producer_raw_words(seed)
    for index, word in enumerate(words):
        helpers.put_word(memory, RESOURCE_SEGMENT, index * 2, word)
    for offset in range(0x134, 0x184):
        put_byte(memory, RESOURCE_SEGMENT, offset,
                 deterministic_byte(seed, offset))
    helpers.put_word(memory, data_segment, 0x1FE4, RESOURCE_SEGMENT)
    return words


def make_cases():
    cases = []

    def add(name, entry, **values):
        defaults = dict(seed=0x3300 + len(cases), x=0x0120, y=0x0030,
                        record4=0, record6=0x0010, field27=0,
                        field28=0, selection=0, alignment_index=0xBEEF,
                        df=False, independent=False)
        defaults.update(values)
        cases.append(dict(name=name, entry=entry, **defaults))

    for entry in (TEN, THIRTEEN):
        for shift in range(8):
            for reverse in (False, True):
                field28 = shift & 3 if entry == THIRTEEN else 0
                field27 = 0xFF if shift == 3 else 0
                add(f'{entry}-shift-{shift}-' + ('reverse' if reverse else 'forward'),
                    entry, x=0x0120 + shift, y=0x0030,
                    record4=0, record6=0x0010, field27=field27,
                    field28=field28, selection=(shift if entry == TEN else shift & 3),
                    alignment_index=(0x6B11 + shift * 13) & 0xFFFF,
                    df=reverse, independent=True)

    for index, selection in enumerate((0x007F, 0xFF80, 0xFFFE, 0xFFFF)):
        add(f'thirteen-unchecked-selection-{selection:04x}', THIRTEEN,
            selection=selection, x=0x01A5 + index, y=0x0031 + index,
            record4=0x0101 + index * 7, record6=0x0014 + index,
            field27=(0x7F, 0x80, 0xFE, 0xFF)[index], field28=index,
            alignment_index=0x1100 + index)

    for index, direction in enumerate((0x00, 0x7F, 0x80, 0xFF)):
        add(f'thirteen-state-two-signed-record27-{direction:02x}', THIRTEEN,
            selection=index & 1, x=0x0125 + index, y=0x0030 + index,
            record4=0x0003 + index, record6=0x0010 + index,
            field27=direction, field28=2, alignment_index=0x5A00 + index,
            independent=True)

    add('ten-provider-live-saved-base', TEN, selection=2, x=0x0125,
        provider='saved-base', replacement_base=0x4567)
    add('thirteen-provider-live-saved-base', THIRTEEN, selection=1, x=0x0126,
        provider='saved-base', replacement_base=0x7654)
    add('ten-provider-second-x-and-record4', TEN, selection=1, x=0x0125,
        record4=2, provider='second-x', replacement_x=0x0131,
        replacement_record4=7)
    add('ten-provider-live-buffer-selector', TEN, selection=0, x=0x0123,
        provider='buffer-segment', alternate_segment=ALTERNATE_BUFFER_SEGMENT)

    for entry in (TEN, THIRTEEN):
        add(f'{entry}-push-ds-overwrites-selector', entry,
            ds=0x3000, ss=0x3000, si=0x4000, sp=0x1FEC,
            buffer_segment=ALTERNATE_BUFFER_SEGMENT,
            selector_after_stack=0x3000)
        add(f'{entry}-ds-vga-record-and-selector', entry, ds=0xA000,
            ds_vga_record=True, read_map=3, gc5=0x08,
            gc2=0x0A, gc7=0x0D)
        add(f'{entry}-ss-vga-saved-words', entry, ss=0xA000,
            ss_vga_stack=True, sp=0x8000, gc5=0, gc8=0,
            no_op_ports=True)
        add(f'{entry}-ss-vga-real-ports-map-zero', entry, ss=0xA000,
            ss_vga_stack=True, sp=0x8000, gc5=0, gc8=0,
            seq_mask=0, vga_saved_dx=0x03CE)
        add(f'{entry}-return-word-overwritten-by-bitmask-mirror', entry,
            sp=0x000E)
        add(f'{entry}-entry-if-clear-draw-then-sti', entry, iflag=False)
        add(f'{entry}-record-offset-and-y-wrap', entry, si=0xFFFC,
            x=0xFFFF, y=0x0011, record4=0x0021, record6=0x0020,
            field27=0xFF, field28=2 if entry == THIRTEEN else 0)
        add(f'{entry}-record-physical-word-wrap', entry, ds=0xFFFF,
            si=0x000F, x=0x0137, y=0x0027, record4=0x0005,
            record6=0x0011, field27=0x80,
            field28=2 if entry == THIRTEEN else 0)

    add('ten-stack-word-physical-wrap', TEN, ss=0xFFFF, sp=0x0011,
        selection=1, x=0x0127)

    add('ten-no-op-unexpected-popped-port', TEN, null_device=True,
        provider='dx-zero-on-pop')
    add('thirteen-vga-write-mode-one-latch-order', THIRTEEN,
        gc5=0x01, seq_mask=0x05, gc8=0xFF, read_map=2,
        independent=True)
    add('ten-vga-readmode-one-partial-map', TEN, gc5=0x09,
        seq_mask=0x0A, gc2=0x09, gc7=0x05, read_map=1,
        independent=True)
    add('thirteen-vga-write-mode-zero-partial-map', THIRTEEN,
        gc5=0, seq_mask=0x05, gc8=0xD3, independent=True)

    add('ten-producer-bank-handoff', TEN, producer_handoff=True,
        x=0x0123, selection=0, record4=0, record6=0x0010,
        field27=0, independent=True)
    add('thirteen-producer-bank-handoff-physical-wrap', THIRTEEN,
        producer_handoff=True, buffer_segment=0xFF72, x=0x0121,
        selection=1, record4=0, record6=0x0010, field27=0,
        field28=0, independent=True)
    return cases


def input_hashes():
    paths = (
        'AGENTS.md', 'docs/executable.md', 'docs/next-work.md',
        'docs/bottom-up.md', 'docs/entity-mask.md',
        'docs/generated-graphics.md', 'docs/entity-vga.md',
        'src/game_code_late_after_palette.asm', 'src/entity_graphics.asm',
        'src/game_code_late_after_entities.asm', 'src/program.asm',
        'assets/vgalemmi.exe',
        'metadata/symbols.json', 'metadata/inputs.json', 'metadata/oracle.json',
        'c/entity_mask_rows.c', 'c/entity_mask_rows.h',
        'c/generated_graphics.c', 'c/generated_graphics.h',
        'c/mask_generators.c', 'c/mask_generators.h', 'c/special_blit.h',
        'c/regs.h', 'c/lemmings_sym.h', 'tests/entity_mask_rows.py',
        'tests/entity_mask.py', 'tests/minimap_vga.py', 'tests/dat_io.py',
        'tests/dat_io_c.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/common.py', 'tools/difftest.py', 'tools/unpack.py',
        'tools/coverage.py',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def make_providers(case, regs):
    effects = []
    mode = case.get('provider')
    if mode == 'saved-base':
        offset = 2 if case['entry'] == TEN else 0
        effects.append(dict(
            trigger=helpers.physical(regs['ds'], (regs['si'] + offset) & 0xFFFF),
            after=0,
            writes=[(helpers.physical(regs['ss'], (regs['sp'] - 2) & 0xFFFF),
                     bytes((case['replacement_base'] & 0xFF,
                            case['replacement_base'] >> 8)))],
        ))
    elif mode == 'second-x':
        effects.append(dict(
            trigger=helpers.physical(regs['ds'], regs['si']), after=1,
            writes=[
                (helpers.physical(regs['ds'], regs['si']),
                 bytes((case['replacement_x'] & 0xFF,
                        case['replacement_x'] >> 8))),
                (helpers.physical(regs['ds'], (regs['si'] + 4) & 0xFFFF),
                 bytes((case['replacement_record4'] & 0xFF,
                        case['replacement_record4'] >> 8))),
            ],
        ))
    elif mode == 'buffer-segment':
        target = helpers.physical(regs['ds'], 0x1FE8)
        effects.append(dict(trigger=target, after=0,
                            writes=[(target, bytes((case['alternate_segment'] & 0xFF,
                                                   case['alternate_segment'] >> 8)))]))
    elif mode == 'dx-zero-on-pop':
        target = helpers.physical(regs['ss'], (regs['sp'] - 4) & 0xFFFF)
        effects.append(dict(trigger=target, after=0,
                            writes=[(target, b'\x00\x00')], replace_read=True))
    return effects


def set_plane_bytes(device, offset, values, plane=3):
    for index, value in enumerate(values):
        device.planes[plane][(offset + index) & 0xFFFF] = value & 0xFF


def effective_buffer_segment(case, regs):
    if case.get('selector_after_stack') is not None:
        return case['selector_after_stack']
    return case.get('buffer_segment', BUFFER_SEGMENT)


def prepare(case):
    rng = random.Random(0x5FAC + case['seed'] * 0x9E3779B1)
    memory = bytearray(rng.randbytes(MEMORY_SIZE))
    loaded = helpers.relocated(IMAGE, ORACLE['relocations'], LOAD)
    image_base = LOAD << 4
    memory[image_base:image_base + len(loaded)] = loaded
    regs = {name: rng.randrange(65536) for name in REGS}
    regs.update(cs=LOAD, ip=case_spec(case)['entry'],
                ax=case.get('selection', 0),
                bp=case.get('alignment_index', 0xBEEF),
                ds=case.get('ds', DATA_SEGMENT),
                ss=case.get('ss', 0x5300), es=rng.randrange(65536),
                si=case.get('si', 0x4000), sp=case.get('sp', 0x8000))
    flags = 2 | (rng.randrange(65536) & (FLAGS & ~TF))
    flags &= ~TF
    flags = flags | DF if case.get('df', False) else flags & ~DF
    if 'iflag' in case:
        flags = flags | IF if case['iflag'] else flags & ~IF
    regs['flags'] = flags

    device = None if case.get('null_device') else helpers.configure_device(
        case, 0x5FAC + case['seed'])
    if case.get('ds_vga_record'):
        device.gc[4] = 3
        device.gc[5] = case.get('gc5', 0) & 0x0B
        device.gc[2] = case.get('gc2', device.gc[2]) & 0x0F
        device.gc[7] = case.get('gc7', device.gc[7]) & 0x0F

    fields = dict(x=case.get('x', 0x0120), y=case.get('y', 0x0030),
                  record4=case.get('record4', 0),
                  record6=case.get('record6', 0x0010),
                  field27=case.get('field27', 0),
                  field28=case.get('field28', 0))
    if case.get('ds_vga_record'):
        for offset, word in ((regs['si'], fields['x']),
                             ((regs['si'] + 2) & 0xFFFF, fields['y']),
                             ((regs['si'] + 4) & 0xFFFF, fields['record4']),
                             ((regs['si'] + 6) & 0xFFFF, fields['record6'])):
            helpers.set_plane_word(device, offset, word)
        set_plane_bytes(device, (regs['si'] + 0x27) & 0xFFFF,
                        (fields['field27'], fields['field28']))
        helpers.set_plane_word(device, 0x1FE8,
                               case.get('buffer_segment', BUFFER_SEGMENT))
    else:
        for offset, value in ((regs['si'], fields['x']),
                              ((regs['si'] + 2) & 0xFFFF, fields['y']),
                              ((regs['si'] + 4) & 0xFFFF, fields['record4']),
                              ((regs['si'] + 6) & 0xFFFF, fields['record6'])):
            helpers.put_word(memory, regs['ds'], offset, value)
        put_byte(memory, regs['ds'], (regs['si'] + 0x27) & 0xFFFF,
                 fields['field27'])
        put_byte(memory, regs['ds'], (regs['si'] + 0x28) & 0xFFFF,
                 fields['field28'])
        helpers.put_word(memory, regs['ds'], 0x1FE8,
                         case.get('buffer_segment', BUFFER_SEGMENT))

    producer_words = None
    if case.get('producer_handoff'):
        producer_words = seed_producer_source(memory, regs['ds'], case['seed'])
    else:
        segment = effective_buffer_segment(case, regs)
        put_row_banks(memory, segment, case['seed'])
        if case.get('alternate_segment') is not None:
            put_row_banks(memory, case['alternate_segment'], case['seed'])

    if case.get('ss_vga_stack'):
        device.gc[4] = 3
        device.gc[5] = 0
        device.gc[8] = 0
        helpers.set_plane_word(device, regs['sp'],
                               case.get('return_word', 0xE800 | case['seed']))
        # Seed the first live save slots so stack aliases observe real plane data.
        for delta, word in ((2, 0xA512), (4, case.get('vga_saved_dx', 0xC34E)), (6, 0x2901)):
            helpers.set_plane_word(device, (regs['sp'] - delta) & 0xFFFF, word)
    else:
        helpers.put_word(memory, regs['ss'], regs['sp'],
                         case.get('return_word', 0xE800 | case['seed']))

    return memory, regs, device, producer_words, make_providers(case, regs)


def case_spec(case):
    return spec_for(case['entry'])


def input_expected_bank(words, entry, selection=0):
    spec = case_spec({'entry': entry})
    if entry == TEN:
        return expected_bank(words[selection * spec['rows']:(selection + 1) * spec['rows']])
    return expected_bank(words[80 + selection * 13:80 + (selection + 1) * 13])


def producer_handoff(producer, memory, case, words):
    call = helpers.ProducerCall(DATA_SEGMENT, 0x5400, 0x8000, 0, 0, 0x0002)
    result = producer.core(helpers.c_buffer(memory), ctypes.byref(call), None)
    oracle_require(result.ready_to_return == 1 and result.continuation == 0x5B10,
                   f'{case["name"]}: generated bank producer missed core boundary')
    selection = case.get('selection', 0)
    if case['entry'] == TEN:
        offset = selection * 240
        bank = input_expected_bank(words, TEN, selection)
    else:
        offset = 0x780 + selection * 312
        bank = input_expected_bank(words, THIRTEEN, selection)
    segment = case.get('buffer_segment', BUFFER_SEGMENT)
    start = helpers.physical(segment, offset)
    actual = bytes(memory[(start + index) & MEMORY_MASK]
                   for index in range(len(bank)))
    oracle_require(actual == bank,
                   f'{case["name"]}: producer bank differs from independent shift chain')


class OriginalRun:
    def __init__(self, case, memory, regs, device, effects, *, core):
        self.case, self.spec = case, case_spec(case)
        self.entry, self.ret = self.spec['entry'], self.spec['ret']
        self.ins = INS[case['entry']]
        self.core = core
        self.memory, self.regs_in = memory, regs
        self.device, self.effects = device, effects
        self.events, self.sites, self.edges = [], set(), set()
        self.instruction_count = 0
        self.read_counts, self.used_effects = {}, set()
        self.previous = None
        self.current_flags = regs['flags']
        self.entry_flag_mask = FLAGS
        self.flag_mask = FLAGS
        self.failure = None
        self.stopped = False
        self.stop_kind = None
        self.continuation = None
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, 2 * MEMORY_SIZE)
        initial = bytes(memory)
        self.cpu.mem_write(0, initial)
        self.cpu.mem_write(MEMORY_SIZE, initial)
        for name in REGS:
            self.cpu.reg_write(REG_ID[name], regs[name])
        self.cpu.reg_write(x.UC_X86_REG_EFLAGS, regs['flags'])

        def fail(message):
            if self.failure is None:
                self.failure = message
            self.cpu.emu_stop()

        def mirror(linear, physical, value):
            byte = bytes((value & 0xFF,))
            for address in (linear, physical, physical + MEMORY_SIZE):
                if 0 <= address < 2 * MEMORY_SIZE:
                    self.cpu.mem_write(address, byte)

        def apply_effect(address):
            count = self.read_counts.get(address, 0)
            for index, effect in enumerate(self.effects):
                if (index not in self.used_effects and
                        address == effect['trigger'] and
                        count == effect['after']):
                    self.used_effects.add(index)
                    for target, data in effect['writes']:
                        for offset, value in enumerate(data):
                            p = (target + offset) & MEMORY_MASK
                            self.memory[p] = value
                            mirror(p, p, value)

        def code(uc, _address, _size, _user):
            off = uc.reg_read(x.UC_X86_REG_IP) & 0xFFFF
            cs = uc.reg_read(x.UC_X86_REG_CS) & 0xFFFF
            if self.previous in BRANCHES[self.case['entry']]:
                self.edges.add((self.previous, off))
            if self.previous is not None:
                self.flag_mask = helpers.flags_defined_after(
                    self.ins[self.previous], self.flag_mask)
            if self.previous == self.ret:
                self.continuation = off
                self.stop_kind = 'outer-return'
                self.stopped = True
                uc.emu_stop()
                return
            if cs != self.regs_in['cs'] or off not in self.ins:
                fail(f'{self.case["name"]}: original escaped at {cs:04X}:{off:04X}')
                return
            if self.core and off == self.ret:
                self.continuation = off
                self.stop_kind = 'core-boundary'
                self.stopped = True
                uc.emu_stop()
                return
            if self.instruction_count >= MAX_INSTRUCTIONS:
                fail(f'{self.case["name"]}: original instruction budget exhausted')
                return
            self.instruction_count += 1
            self.sites.add(off)
            self.current_flags = uc.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
            self.entry_flag_mask = self.flag_mask
            self.previous = off

        def event(kind, address, value):
            if len(self.events) >= MAX_EVENTS:
                fail(f'{self.case["name"]}: original bus-event budget exhausted')
                return
            self.events.append((kind, address, value & 0xFFFF,
                                self.current_flags & 0xFFFF,
                                self.entry_flag_mask))

        def memory_read(uc, _access, address, size, _value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * MEMORY_SIZE:
                        fail(f'{self.case["name"]}: original read escaped mapped memory')
                        return
                    p = linear & MEMORY_MASK
                    apply_effect(p)
                    value = (self.device.read(self.memory, p, self.current_flags)
                             if self.device is not None and
                             helpers.VGA_BASE <= p < helpers.VGA_END
                             else self.memory[p])
                    event('read', p, value)
                    if self.failure:
                        return
                    mirror(linear, p, value)
                    self.read_counts[p] = self.read_counts.get(p, 0) + 1
                    if self.device is not None and len(self.device.trace) > MAX_EVENTS:
                        fail(f'{self.case["name"]}: original VGA callback cap exhausted')
                        return
            except BaseException as error:
                fail(f'{self.case["name"]}: original read callback failed: {error}')

        def memory_write(uc, _access, address, size, value, _user):
            try:
                for n in range(size):
                    linear = address + n
                    if not 0 <= linear < 2 * MEMORY_SIZE:
                        fail(f'{self.case["name"]}: original write escaped mapped memory')
                        return
                    p = linear & MEMORY_MASK
                    byte = (value >> (8 * n)) & 0xFF
                    if (self.device is not None and
                            helpers.VGA_BASE <= p < helpers.VGA_END):
                        self.device.write(self.memory, p, byte, self.current_flags)
                    else:
                        self.memory[p] = byte
                    event('write', p, byte)
                    if self.failure:
                        return
                    mirror(linear, p, byte)
                    if self.device is not None and len(self.device.trace) > MAX_EVENTS:
                        fail(f'{self.case["name"]}: original VGA callback cap exhausted')
                        return
            except BaseException as error:
                fail(f'{self.case["name"]}: original write callback failed: {error}')

        def output(uc, port, size, value, _user):
            try:
                if size != 2:
                    fail(f'{self.case["name"]}: unexpected non-word OUT width {size}')
                    return
                if self.device is not None and not self.case.get('no_op_ports'):
                    self.device.out(port, value, self.current_flags)
                event('out', port, value)
                if self.device is not None and len(self.device.trace) > MAX_EVENTS:
                    fail(f'{self.case["name"]}: original VGA OUT cap exhausted')
            except BaseException as error:
                fail(f'{self.case["name"]}: original OUT provider failed: {error}')

        self._callbacks = (code, memory_read, memory_write, output)
        self.cpu.hook_add(UC_HOOK_CODE, code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, memory_read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, memory_write)
        self.cpu.hook_add(UC_HOOK_INSN, output, None, 1, 0, x.UC_X86_INS_OUT)

    def run(self):
        try:
            self.cpu.emu_start(helpers.physical(self.regs_in['cs'], self.entry), 0,
                               count=MAX_INSTRUCTIONS)
        except UcError as error:
            raise VerificationFailure(f'{self.case["name"]}: Unicorn failed: {error}') from error
        oracle_require(not self.failure, self.failure or 'original execution failed')
        oracle_require(self.stopped,
                       f'{self.case["name"]}: original missed bounded continuation')
        state = {name: self.cpu.reg_read(REG_ID[name]) & 0xFFFF for name in REGS}
        state['flags'] = self.cpu.reg_read(x.UC_X86_REG_EFLAGS) & 0xFFFF
        return dict(memory=bytes(self.cpu.mem_read(0, MEMORY_SIZE)), state=state,
                    events=self.events, sites=self.sites, edges=self.edges,
                    instruction_count=self.instruction_count,
                    used_effects=set(self.used_effects), device=self.device,
                    stop_kind=self.stop_kind, continuation=self.continuation,
                    flag_mask=self.flag_mask)


class Native:
    def __init__(self, directory, mutation=0):
        self.library = ctypes.CDLL(str(Path(directory) / f'entity-mask-rows-m{mutation}.dll'))
        self.ten_core = self.library.lmn_draw_ten_row_entity_mask_core
        self.thirteen_core = self.library.lmn_draw_thirteen_row_entity_mask_core
        for function in (self.ten_core, self.thirteen_core):
            function.argtypes = [helpers.MEM, ctypes.POINTER(RowsCall),
                                 ctypes.POINTER(helpers.RasterBus)]
            function.restype = RowsResult
        self.ten_adapter = self.library.lmn_draw_ten_row_entity_mask_adapter
        self.thirteen_adapter = self.library.lmn_draw_thirteen_row_entity_mask_adapter
        for function in (self.ten_adapter, self.thirteen_adapter):
            function.argtypes = [helpers.MEM, ctypes.POINTER(helpers.Regs),
                                 ctypes.POINTER(helpers.RasterBus)]
            function.restype = None

    def functions(self, entry):
        if entry == TEN:
            return self.ten_core, self.ten_adapter
        return self.thirteen_core, self.thirteen_adapter


def state_from_core(result, initial):
    state = dict(initial)
    state.update(ax=result.value, bx=result.mask_word, cx=result.row_count,
                 dx=result.port, si=result.source_cursor,
                 di=result.destination_offset, ds=result.data_segment,
                 es=result.output_segment, sp=result.stack_offset,
                 bp=result.alignment_index, ip=case_spec(initial['_case'])['ret'],
                 flags=result.flags)
    state.pop('_case', None)
    return state


def compare_state(case, actual, expected, label, flag_mask):
    for name in REGS:
        if actual[name] != expected[name]:
            raise NativeMismatch(f'{case["name"]} {label} {name} differs: '
                                 f'{actual[name]:04X}/{expected[name]:04X}')
    if ((actual['flags'] ^ expected['flags']) & flag_mask) != 0:
        raise NativeMismatch(f'{case["name"]} {label} defined flags differ: '
                             f'{actual["flags"]:04X}/{expected["flags"]:04X}')


def compare_memory(case, actual, expected, label):
    if actual == expected:
        return
    at = next((index for index, pair in enumerate(zip(actual, expected))
               if pair[0] != pair[1]), None)
    raise NativeMismatch(f'{case["name"]} {label} RAM differs at {at:05X}: '
                         f'{actual[at]:02X}/{expected[at]:02X}')


def expected_coordinates(case, memory):
    regs = case['_regs']
    ds, si = regs['ds'], regs['si']
    read_word = lambda offset: helpers.get_word(memory, ds, (si + offset) & 0xFFFF)
    xvalue = read_word(0)
    yvalue = read_word(2)
    record4 = read_word(4)
    record6 = read_word(6)
    field27 = read_byte(memory, ds, (si + 0x27) & 0xFFFF)
    field28 = read_byte(memory, ds, (si + 0x28) & 0xFFFF)
    if case['entry'] == TEN:
        destination_y = (yvalue + record6 - 0x10) & 0xFFFF
        xsum = (xvalue + record4) & 0xFFFF
        destination = ((0xD0 * destination_y) & 0xFFFF)
        destination = (destination + (xsum >> 3) + 0x4A40) & 0xFFFF
        base = (case['selection'] * 240) & 0xFFFF
        if field27 == 0xFF:
            base = (base + 0x3C0) & 0xFFFF
        cursor = (base + 30 * (xsum & 7)) & 0xFFFF
        return cursor, destination

    if field28 == 2:
        yvalue = (yvalue + 1) & 0xFFFF
        signed27 = field27 - 0x100 if field27 & 0x80 else field27
        xvalue = (xvalue + signed27) & 0xFFFF
    destination_y = (yvalue + record6 - 0x10) & 0xFFFF
    xsum = (xvalue + record4) & 0xFFFF
    destination = ((0xD0 * destination_y) & 0xFFFF)
    destination = (destination + (xsum >> 3) + 0x4A40) & 0xFFFF
    base = (0x780 + 312 * case['selection']) & 0xFFFF
    if field27 == 0xFF:
        base = (base + 0x270) & 0xFFFF
    cursor = (base + 39 * (xsum & 7)) & 0xFFFF
    return cursor, destination


def source_masks(memory, source_segment, cursor, rows, df):
    masks = []
    step = -1 if df else 1
    si = cursor
    for _ in range(rows):
        at = helpers.physical(source_segment, si)
        low = memory[at]
        high = memory[(at + 1) & MEMORY_MASK]
        si = (si + step * 2) & 0xFFFF
        third = memory[helpers.physical(source_segment, si)]
        si = (si + step) & 0xFFFF
        masks.append((low, high, third))
    return masks


def independent_plane_check(case, original_start_memory, initial_device,
                            actual_device):
    if (not case.get('independent') or initial_device is None or
            case.get('provider') or case.get('ds_vga_record') or
            case.get('selector_after_stack') is not None):
        return False
    rows = case_spec(case)['rows']
    regs = case['_regs']
    cursor, destination = expected_coordinates(case, original_start_memory)
    source_segment = case.get('buffer_segment', BUFFER_SEGMENT)
    masks = source_masks(original_start_memory, source_segment, cursor, rows,
                         case.get('df', False))
    expected = [bytearray(plane) for plane in initial_device.planes]
    map_mask = initial_device.seq[2] & 0x0F
    write_mode = initial_device.gc[5] & 3
    oracle_require(write_mode in (0, 1),
                   f'{case["name"]}: independent checker unsupported write mode')
    row_start = destination
    delta = -1 if case.get('df', False) else 1
    for row_masks in masks:
        for col, mask_byte in enumerate(row_masks):
            offset = (row_start + delta * col) & 0xFFFF
            if write_mode == 0:
                for plane in range(4):
                    if map_mask & (1 << plane):
                        expected[plane][offset] &= (~mask_byte) & 0xFF
        row_start = (row_start + delta * 3 + 0xCD) & 0xFFFF
    for plane in range(4):
        oracle_require(bytes(actual_device.planes[plane]) == bytes(expected[plane]),
                       f'{case["name"]}: independent mask/plane check failed on {plane}')
    return True


def native_run(native, case, initial, initial_regs, initial_device, effects,
               *, core):
    memory = bytearray(initial)
    device = copy.deepcopy(initial_device)
    callbacks, bus, events, used_effects = helpers.make_raster_bus(
        memory, device, effects,
        no_op_ports=bool(case.get('null_device') or case.get('no_op_ports')))
    call_core, call_adapter = native.functions(case['entry'])
    if core:
        call = RowsCall(initial_regs['ds'], initial_regs['ss'],
                        initial_regs['sp'], initial_regs['si'],
                        initial_regs['ax'], initial_regs['bp'],
                        initial_regs['flags'])
        result = call_core(helpers.c_buffer(memory), ctypes.byref(call),
                           ctypes.byref(bus))
        starting = dict(initial_regs)
        starting['_case'] = case
        state = state_from_core(result, starting)
    else:
        live = helpers.Regs(**{name: initial_regs[name] for name in REGS},
                             flags=initial_regs['flags'])
        call_adapter(helpers.c_buffer(memory), ctypes.byref(live), ctypes.byref(bus))
        state = {name: getattr(live, name) for name in REGS}
        state['flags'] = live.flags
    return dict(memory=bytes(memory), state=state, events=events,
                device=device, callbacks=callbacks,
                used_effects=set(used_effects))


def compare_case(native, case, producer=None):
    initial, regs, device, producer_words, effects = prepare(case)
    case = dict(case, _regs=regs)
    if case.get('producer_handoff'):
        oracle_require(producer is not None, 'producer handoff library missing')
        producer_handoff(producer, initial, case, producer_words)
    start_memory = bytes(initial)
    initial_device = copy.deepcopy(device)
    observations = {}
    independent_checked = False
    for core in (True, False):
        original = OriginalRun(case, bytearray(start_memory), dict(regs),
                               copy.deepcopy(initial_device), effects,
                               core=core).run()
        actual = native_run(native, case, start_memory, regs, initial_device,
                            effects, core=core)
        oracle_require(original['used_effects'] == set(range(len(effects))),
                       f'{case["name"]}: original did not use every provider effect')
        oracle_require(actual['used_effects'] == set(range(len(effects))),
                       f'{case["name"]}: native did not use every provider effect')
        label = 'core' if core else 'adapter'
        compare_state(case, actual['state'], original['state'], label,
                      original['flag_mask'])
        compare_memory(case, actual['memory'], original['memory'], label)
        helpers.compare_events(case, actual['events'], original['events'])
        if initial_device is not None:
            require(actual['device'].state() == original['device'].state(),
                    f'{case["name"]}: {label} VGA state differs')
            if core:
                independent_checked = independent_plane_check(
                    case, start_memory, initial_device, original['device'])
        if core:
            oracle_require(original['stop_kind'] == 'core-boundary' and
                           original['continuation'] == case_spec(case)['ret'],
                           f'{case["name"]}: original missed the pre-RET boundary')
            oracle_require(original['state']['sp'] == regs['sp'],
                           f'{case["name"]}: original core left an unbalanced stack')
            require(actual['state']['ip'] == case_spec(case)['ret'],
                    f'{case["name"]}: native core boundary differs')
        else:
            oracle_require(original['stop_kind'] == 'outer-return',
                           f'{case["name"]}: original did not execute actual RET')
            oracle_require(original['state']['sp'] == ((regs['sp'] + 2) & 0xFFFF),
                           f'{case["name"]}: RET did not consume actual return word')
        observations['core' if core else 'adapter'] = dict(
            sites=original['sites'], edges=original['edges'],
            instruction_count=original['instruction_count'],
            event_count=len(original['events']), stop_kind=original['stop_kind'],
            continuation=original['continuation'])
        gc.collect()
    return observations, independent_checked


def worker(directory, before_path):
    before = read_json(before_path)
    oracle_require(before == input_hashes(),
                   'entity mask rows inputs changed between build and worker')
    oracle_require(sha(ASSET.read_bytes()) ==
                   '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d',
                   'Pinned executable identity changed')
    oracle_require(sha(IMAGE) ==
                   'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e',
                   'Pinned static image identity changed')
    oracle_require(len(SPECS[TEN]['code']) == 191 and
                   len(INS[TEN]) == 88 and len(SPECS[THIRTEEN]['code']) == 214 and
                   len(INS[THIRTEEN]) == 99 and len(ALL_SITES) == 187,
                   '5FAC/606B byte and instruction accounting changed')

    cases = make_cases()
    baseline = Native(directory)
    producer = helpers.Native(directory, producer=True)
    by_name = {case['name']: case for case in cases}
    coverage, edges, total_events = set(), set(), 0
    rows, independent_count = [], 0
    for case in cases:
        observation, checked = compare_case(baseline, case, producer)
        case_sites = (set(observation['core']['sites']) |
                      set(observation['adapter']['sites']))
        case_edges = (set(observation['core']['edges']) |
                      set(observation['adapter']['edges']))
        coverage.update(case_sites)
        edges.update(case_edges)
        total_events += (observation['core']['event_count'] +
                         observation['adapter']['event_count'])
        independent_count += bool(checked)
        rows.append(dict(name=case['name'], entry=case['entry'],
                         row_count=case_spec(case)['rows'],
                         selection=case.get('selection', 0),
                         x=case.get('x', 0x0120), y=case.get('y', 0x0030),
                         record4=case.get('record4', 0),
                         record6=case.get('record6', 0x0010),
                         field27=case.get('field27', 0),
                         field28=case.get('field28', 0), df=case.get('df', False),
                         provider=case.get('provider'),
                         port_provider=('no-op' if case.get('null_device') or case.get('no_op_ports') else 'VGA'),
                         stack_segment=case.get('ss', 0x5300),
                         producer_handoff=bool(case.get('producer_handoff')),
                         independent_mask_plane_check=checked,
                         boundaries={name: dict(
                             instruction_count=part['instruction_count'],
                             event_count=part['event_count'],
                             stop_kind=part['stop_kind'],
                             continuation=part['continuation'])
                             for name, part in observation.items()}))
        gc.collect()

    oracle_require(coverage == ALL_SITES,
                   f'Original executed-site union differs: missing={sorted(ALL_SITES-coverage)}')
    oracle_require(edges == EXPECTED_EDGES,
                   f'Original branch-edge set differs: {sorted(edges)}')

    witnesses = (
        (1, 'ten-shift-7-forward', 'ten-row source base scale'),
        (2, 'thirteen-state-two-signed-record27-80', 'state==2 coordinate adjustment'),
        (3, 'ten-provider-live-saved-base', 'ten-row live popped base'),
        (3, 'thirteen-provider-live-saved-base', 'thirteen-row live popped base'),
        (4, 'ten-shift-4-reverse', 'DF-sensitive LODS/STOS steps'),
        (5, 'thirteen-vga-write-mode-one-latch-order', 'per-pixel latch reads'),
        (6, 'ten-return-word-overwritten-by-bitmask-mirror', 'actual outer RET read'),
        (7, 'thirteen-entry-if-clear-draw-then-sti', 'unconditional STI'),
        (8, 'thirteen-state-two-signed-record27-80', 'BP receives sum&7'),
        (9, 'ten-provider-second-x-and-record4', 'second live X/record4 read'),
    )
    mutations = []
    for number, case_name, label in witnesses:
        mutant = Native(directory, number)
        try:
            compare_case(mutant, by_name[case_name], producer)
        except (NativeMismatch, helpers.NativeMismatch) as error:
            mutations.append(dict(mutation=number, name=label, case=case_name,
                                  mismatch=str(error), completed=True))
        else:
            raise VerificationFailure(
                f'Entity-mask-rows mutation {number} survived {case_name}')
        gc.collect()

    after = input_hashes()
    oracle_require(before == after,
                   'entity mask rows inputs changed during bounded campaign')
    unique_mutants = {entry['mutation'] for entry in mutations}
    oracle_require(60 <= len(cases) <= 68 and unique_mutants == set(range(1, 10)),
                   'Entity-mask-rows fixture/mutant scope changed')
    write_json(REPORT, dict(image='main', image_sha256=sha(IMAGE),
        asset_sha256=sha(ASSET.read_bytes()),
        static_image_sha256=sha(IMAGE),
        case_count=len(cases), boundary_call_count=2 * len(cases),
        mutation_count=len(unique_mutants), mutations=mutations, cases=rows,
        translated_code_bytes=sum(spec['byte_count'] for spec in SPECS.values()),
        native_code_ranges=[[SPECS[TEN]['entry'], SPECS[TEN]['end']],
                            [SPECS[THIRTEEN]['entry'], SPECS[THIRTEEN]['end']]],
        routine_bytes={entry: spec['code'].hex()
                       for entry, spec in SPECS.items()},
        executed_instruction_addresses=sorted(coverage),
        instruction_sites=sorted(coverage), instruction_site_count=len(coverage),
        branch_instruction_addresses=sorted(
            BRANCHES[TEN] | BRANCHES[THIRTEEN]),
        branch_edges=sorted(edges), total_bus_events=total_events,
        independent_mask_plane_checks=independent_count,
        generated_bank_handoffs=[
            dict(case='ten-producer-bank-handoff', output_offset=0,
                 checked_bytes=8 * 10 * 3,
                 formula='selection*240 + 30*shift; 24-bit AL/AH/DL shift'),
            dict(case='thirteen-producer-bank-handoff-physical-wrap',
                 output_offset=0x780 + 312,
                 checked_bytes=8 * 13 * 3,
                 formula='0780h + 312*selection + 39*shift; physical FFFFFh wrap'),
        ],
        domains=[
            '5FAC..606A ten-row entry (191 bytes/88 sites), pre-RET core and actual-RET adapter',
            '606B..6140 thirteen-row entry (214 bytes/99 sites), pre-RET core and actual-RET adapter',
            'all eight source shifts in both DF directions; fixed ten/thirteen-row bodies and forward CDh add',
            'unchecked AX selections, saved base/DX, live DS selector, post-PUSH record/selector reads and providers',
            'ten-row reread of X/record+4 after PUSH SI; thirteen-row record+28h equality and signed record+27h',
            'live SS, DS, SI, stack/record word wrap, source physical FFFFFh/00000h wrap and actual RET aliases',
            'incoming VGA map mask/read/write modes, ordered latch reads, mirrors, no-op unexpected port',
            'thirteen-row BP clobber/result, ten-row BP preservation, IF clear/DF set and unconditional STI',
            'whole 1 MiB RAM, all adapter registers, per-instruction defined flags and bounded bus events',
        ],
        limits=dict(worker_seconds=180, windows_process_mib=384,
                    windows_tree_commit_mib=640,
                    original_instruction_limit=MAX_INSTRUCTIONS,
                    original_instruction_counts=dict(
                        total=sum(part['instruction_count'] for row in rows
                                  for part in row['boundaries'].values()),
                        maximum=max(part['instruction_count'] for row in rows
                                    for part in row['boundaries'].values())),
                    native_callback_event_limit=MAX_EVENTS,
                    callback_budget_exit=GUARD_EXIT,
                    callback_error_exit=CALLBACK_EXIT),
        input_hashes=after))
    print(f'PASS entity mask rows C: {len(cases)} fixtures, {total_events} events, '
          f'{len(coverage)} instruction sites, {len(edges)} branch edges, '
          f'{len(unique_mutants)} completed mutants, {independent_count} independent plane checks',
          flush=True)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:]:
        raise SystemExit('Unexpected entity-mask-rows arguments')
    BUILD.mkdir(parents=True, exist_ok=True)
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='entity-mask-rows-', parent=BUILD) as directory:
        before_path = Path(directory) / 'input-hashes.json'
        before = input_hashes()
        write_json(before_path, before)
        for mutation in range(10):
            build(Path(directory) / f'entity-mask-rows-m{mutation}.dll', mutation,
                  'entity_mask_rows')
        build(Path(directory) / 'generated-graphics-producer.dll', 0,
              'generated_graphics')
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker',
                     directory, str(before_path)], cwd=ROOT, timeout=180,
                    memory_mib=384)


if __name__ == '__main__':
    main()

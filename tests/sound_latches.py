"""Bounded driver dispatch prefixes and six live-stack setter tails.

Update/detect/reset are explicit untranslated exits; no playback is executed.
"""
import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from resources import sound_images
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unicorn import Uc, UcError, UC_ARCH_X86, UC_MODE_16
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import x86_const as x

SIZE, MASK, FLAGS = 1 << 20, (1 << 20) - 1, 0x0FD7
CAP, STEPS = 64, 64
REPORT = BUILD / 'sound-latches-differential.json'
IMAGES = sound_images()
TAILS = {'adlib': {3: (0x22, 0xED), 4: (0x2A, 0xF0), 5: (0x32, 0xEE)},
         'tandysnd': {3: (0x19, 0x4A), 4: (0x21, 0x4C), 5: (0x29, 0x4B)}}
NAMES = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'sp',
         'cs', 'ds', 'es', 'ss', 'ip', 'flags')
IDS = {n: getattr(x, 'UC_X86_REG_' + n.upper()) for n in NAMES[:-1]}
IDS['flags'] = x.UC_X86_REG_EFLAGS
MEM = ct.POINTER(ct.c_uint8)

class Regs(ct.Structure):
    _fields_ = [(n, ct.c_uint16) for n in NAMES]

class Call(ct.Structure):
    _fields_ = [(n, ct.c_uint16) for n in
                ('driver_segment', 'data_segment', 'stack_segment',
                 'stack_offset', 'value', 'flags')]

class Result(ct.Structure):
    _fields_ = [(n, ct.c_uint16) for n in ('data_segment', 'stack_offset', 'flags')]

class ControlResult(ct.Structure):
    _fields_ = [(n, ct.c_uint16) for n in ('value', 'data_segment', 'stack_offset',
                                        'flags', 'continuation', 'exit_kind')]

READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8, ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)

class Bus(ct.Structure):
    _fields_ = [('context', ct.c_void_p), ('read_byte', READ),
                ('write_byte', WRITE), ('out_word', OUT)]

class Mismatch(AssertionError):
    """Only a completed native comparison can produce mutant credit."""

def require(ok, message):
    if not ok:
        raise Mismatch(message)

def physical(seg, off):
    return ((seg << 4) + (off & 0xFFFF)) & MASK

def word(memory, address, value):
    memory[address & MASK] = value & 255
    memory[(address + 1) & MASK] = value >> 8

def cases():
    rows = []
    for driver in TAILS:
        for command, (entry, latch) in TAILS[driver].items():
            variants = [(f'value-{v:02x}', dict(value=v))
                        for v in (0, 5, 12, 0x7F, 0x80, 0xFF)]
            variants += [('sp-zero', dict(sp=0)), ('sp-one', dict(sp=1)),
                         ('sp-ffff', dict(sp=0xFFFF)),
                         ('physical-word-wrap', dict(ss=0xFFFF, sp=0x13)),
                         ('driver-physical-wrap', dict(cs=0xFFFF)),
                         ('latch-saved-ds-low', dict(ss=0x3000, sp=latch + 2)),
                         ('latch-saved-ds-high', dict(ss=0x3000, sp=latch + 1)),
                         ('latch-return-ip', dict(ss=0x3000, sp=latch)),
                         ('latch-return-cs', dict(ss=0x3000, sp=latch - 2)),
                         ('latch-return-flags', dict(ss=0x3000, sp=latch - 4)),
                         ('latch-return-flags-low-05', dict(ss=0x3000, sp=latch - 4, value=5)),
                         ('latch-return-flags-low-00', dict(ss=0x3000, sp=latch - 4, value=0)),
                         ('iret-reserved-flags', dict(iret_flags=0xFCAA)),
                         ('live-temporary-segment', dict(effect='temporary-ds')),
                         ('live-saved-and-iret', dict(effect='after-store')),
                         ('live-iret-flags', dict(effect='iret-flags')),
                         ('vga-latch', dict(cs=0x9FFF, vga='latch')),
                         ('vga-stack', dict(ss=0xA000, vga='stack'))]
            for name, values in variants:
                rows.append(dict(driver=driver, command=command, entry=entry,
                                 latch=latch, name=driver + '-' + str(command) + '-' + name,
                                 variant=name, **values))
    return rows

def setup(case):
    seed = 0x6100 + list(TAILS).index(case['driver']) * 100 + case['command']
    rng = random.Random(seed)
    memory = bytearray(rng.randbytes(SIZE))
    regs = {n: rng.randrange(0x10000) for n in NAMES}
    regs.update(cs=case.get('cs', 0x3000), ds=0x6100, ss=case.get('ss', 0x5000),
                sp=case.get('sp', 0x8200), ip=case['entry'],
                ax=(case['command'] << 8) | case.get('value', 0xB7),
                flags=2 | (seed * 0x95 & 0xED5))
    # Only the independently identified tail/prefix needs executable backing.
    image = IMAGES[case['driver']][0]
    for offset, value in enumerate(image[:0x3A]):
        memory[physical(regs['cs'], offset)] = value
    for delta, value in ((0, 0xE123), (2, 0x1240), (4, case.get('iret_flags',0x0AD7))):
        word(memory, physical(regs['ss'], regs['sp'] + delta), value)
    device = None
    if case.get('vga'):
        device = MinimapVga(seed, read_map=3)
        device.seq[2] = 0x0F if case['vga'] == 'latch' else 0
        device.gc[0] = device.gc[1] = device.gc[3] = device.gc[5] = 0
        device.gc[8] = 0xFF
        if case['vga'] == 'stack':
            # Writes are observable but do not change plane3: temporary POP DS
            # receives this live device word, then POP DS/IRET reread plane3.
            for off, val in ((-4, 0x3300), (-2, 0x6222), (0, 0xE321),
                             (2, 0x1241), (4, 0x0A97)):
                word(device.planes[3], (regs['sp'] + off) & 0xFFFF, val)
    return memory, regs, device

class Access:
    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.events, self.used = [], set()
        self.mirror = None

    def store(self, address, value):
        address &= MASK
        self.memory[address] = value
        if self.mirror:
            self.mirror(address, value)

    def effect(self, name):
        if name in self.used:
            return
        self.used.add(name)
        r = self.regs
        stores = []
        if name == 'temporary-ds':
            stores = [(-4, 0x3400)]
        elif name == 'after-store':
            stores = [(-2, 0x6333), (0, 0xE551), (2, 0x1250), (4, 0x0693)]
        elif name == 'iret-flags':
            stores = [(4, 0x0497)]
        for off, value in stores:
            p = physical(r['ss'], r['sp'] + off)
            self.store(p, value & 255)
            self.store(p + 1, value >> 8)

    def access(self, kind, address, flags, value=None):
        if len(self.events) >= CAP:
            raise RuntimeError('sound latch callback budget exhausted')
        address &= MASK
        r, effect = self.regs, self.case.get('effect')
        if kind == 'read':
            if effect == 'temporary-ds' and address == physical(r['ss'], r['sp'] - 4):
                self.effect(effect)
            if effect == 'iret-flags' and address == physical(r['ss'], r['sp'] + 2):
                self.effect(effect)
            value = (self.device.read(self.memory, address, flags) if self.device and
                     VGA_BASE <= address < VGA_END else self.memory[address])
            self.store(address, value)
        else:
            if self.device and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            self.store(address, value)
        self.events.append((kind, address, value, flags & FLAGS))
        if kind == 'write' and effect == 'after-store' and address == physical(r['cs'], self.case['latch']):
            self.effect(effect)
        return value

def original(case, memory, regs, device, core, dispatch=False, control=False):
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, SIZE * 2)
    cpu.mem_write(0, bytes(memory)); cpu.mem_write(SIZE, bytes(memory))
    for n, v in regs.items():
        cpu.reg_write(IDS[n], v)
    access = Access(case, memory, regs, device)
    def mirror(p, v):
        for at in (p, p + SIZE):
            cpu.mem_write(at, bytes((v,)))
    access.mirror = mirror
    sites, prefix, edges = set(), set(), set()
    previous, stopped, captured = None, False, None
    current_flags = regs['flags']
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    image = IMAGES[case['driver']][0]
    ins = {i.address: i for i in md.disasm(image[:0x3A], 0)}
    ret = case['entry'] + 7
    seam = None
    if control:
        command = regs['ax'] >> 8
        if command < 3:
            seam = ({'adlib': (0x115, 0xA3, 0x3A),
                     'tandysnd': (0x72, 0x43, 0x31)}[case['driver']][command])
        elif command > 5:
            ret = 0x21 if case['driver'] == 'adlib' else 0x18
        dispatch = True
    if dispatch:
        cpu.reg_write(IDS['ip'], 0)
    def code(u, _address, _size, _):
        nonlocal previous, stopped, current_flags, captured
        off, cs = u.reg_read(IDS['ip']), u.reg_read(IDS['cs'])
        if previous == ret:
            stopped = True; u.emu_stop(); return
        if previous is not None and ins[previous].mnemonic.startswith('j'):
            edges.add((previous, off))
        if cs != regs['cs']:
            raise AssertionError('original escaped before IRET')
        if control and off == seam:
            stopped = True; u.emu_stop(); return
        if off == case['entry'] and captured is None:
            captured = {n: u.reg_read(IDS[n]) & 0xFFFF for n in NAMES}
        if core and off == ret:
            stopped = True; u.emu_stop(); return
        if not case['entry'] <= off <= ret:
            if not dispatch or (captured is not None and not control) or off not in ins:
                raise AssertionError(f'original escaped tail at {cs:04x}:{off:04x}')
            prefix.add(off)
        else:
            sites.add(off)
        current_flags = u.reg_read(IDS['flags']) & 0xFFFF
        previous = off
    def read(u, _kind, address, size, _value, _):
        for i in range(size):
            access.access('read', address + i, current_flags)
    def write(u, _kind, address, size, value, _):
        for i in range(size):
            access.access('write', address + i, current_flags, (value >> (i * 8)) & 255)
    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_MEM_READ, read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, write)
    try:
        cpu.emu_start(physical(regs['cs'], 0 if dispatch else case['entry']), 0, count=STEPS)
    except UcError as error:
        raise AssertionError(case['name'] + ': original failed bounded IRET') from error
    assert stopped, case['name'] + ': original budget/escape failure'
    result = {n: cpu.reg_read(IDS[n]) & 0xFFFF for n in NAMES}
    # Original IRET memory hooks can include its frame reread. The trace must
    # reflect actual observed ordered accesses, with no deduplication here.
    return dict(memory=bytes(memory), regs=result, device=device, events=access.events,
                used=access.used, sites=sites, prefix=prefix, edges=edges,
                captured=captured, exit_kind=1 if seam is not None else 0)

class Native:
    def __init__(self, directory, mutation=0):
        self.lib = ct.CDLL(str(build(Path(directory) / f'latches-{mutation}.dll',
                                      mutation, 'sound_latches')))
        for driver in TAILS:
            short = 'adlib' if driver == 'adlib' else 'tandy'
            for command in TAILS[driver]:
                for core in (True, False):
                    f = getattr(self.lib, f'lmn_{short}_latch{command}_' + ('core' if core else 'adapter'))
                    f.argtypes = [MEM, ct.POINTER(Call if core else Regs), ct.POINTER(Bus)]
                    f.restype = Result if core else None
            for core in (True, False):
                f = getattr(self.lib, f'lmn_{short}_control_' + ('core' if core else 'adapter'))
                f.argtypes = [MEM, ct.POINTER(Call if core else Regs), ct.POINTER(Bus)]
                f.restype = ControlResult if core else ct.c_uint16

    def run(self, case, memory, regs, device, core, null=False, control=False):
        access = Access(case, memory, regs, device)
        def die(error):
            os.write(2, (str(error) + '\n').encode()); os._exit(86)
        def read(_ctx, _mem, address, flags):
            try: return access.access('read', address, flags)
            except BaseException as error: die(error)
        def write(_ctx, _mem, address, value, flags):
            try: access.access('write', address, flags, value)
            except BaseException as error: die(error)
        def out(*_args): die('unexpected sound-latch port')
        callbacks = READ(read), WRITE(write), OUT(out)
        bus = Bus(None, *callbacks)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        short = 'adlib' if case['driver'] == 'adlib' else 'tandy'
        stem = 'control_' if control else f'latch{case["command"]}_'
        f = getattr(self.lib, f'lmn_{short}_' + stem + ('core' if core else 'adapter'))
        exit_kind = None
        if core:
            call = Call(regs['cs'], regs['ds'], regs['ss'], regs['sp'], regs['ax'], regs['flags'])
            result = f(ram, ct.byref(call), None if null else ct.byref(bus))
            state.ds, state.sp, state.flags = result.data_segment, result.stack_offset, result.flags
            state.ip = case['entry'] + 7
            if control:
                state.ax, state.ip = result.value, result.continuation
                exit_kind = result.exit_kind
        else:
            exit_kind = f(ram, ct.byref(state), None if null else ct.byref(bus))
        return dict(memory=bytes(memory), regs={n: getattr(state, n) for n in NAMES},
                    events=access.events, used=access.used, device=device, exit_kind=exit_kind)

def dispatch_case(driver, command, **kwargs):
    entry, latch = TAILS[driver].get(command, TAILS[driver][4])
    return dict(driver=driver, command=command, entry=entry, latch=latch,
                value=kwargs.pop('value', 0x0C), variant='dispatch',
                name=f'{driver}-dispatch-{command:02x}', **kwargs)

def compare_control(native, case, core=False, null=False):
    memory, regs, device = setup(case)
    regs['ip'] = 0
    expected = original(case, bytearray(memory), dict(regs), copy.deepcopy(device), core, control=True)
    actual = native.run(case, bytearray(memory), regs, copy.deepcopy(device), core, null, control=True)
    require(actual['exit_kind'] == expected['exit_kind'], case['name'] + ': exit kind differs')
    require(actual['memory'] == expected['memory'], case['name'] + ': control memory differs')
    for n in NAMES:
        mask = 0xFFFF
        # AH0 stops after AND: AF is undefined. Every other command has DEC.
        if n == 'flags' and case['command'] == 0:
            mask &= ~0x10
        require((actual['regs'][n] & mask) == (expected['regs'][n] & mask),
                f'{case["name"]}: control {n} differs {actual["regs"][n]:04x}/{expected["regs"][n]:04x}')
    if not null:
        require(actual['events'] == expected['events'], case['name'] + ': control events differ')
    if device:
        require(actual['device'].state() == expected['device'].state(), case['name'] + ': control VGA state differs')
        require(actual['device'].trace == expected['device'].trace, case['name'] + ': control VGA trace differs')
    # Independently check dispatcher output before IRET/untranslated children.
    if core or case['command'] < 3:
        command = case['command']
        high = command - min(command, 5)
        assert expected['regs']['ax'] == (high << 8) | (regs['ax'] & 255)
        if command:
            old, result = (high + 1) & 255, high & 255
            status = (4 if result.bit_count() % 2 == 0 else 0) | (0x40 if result == 0 else 0) | (result & 0x80)
            if old & 15 == 0: status |= 0x10
            if old == 0x80: status |= 0x800
            assert (expected['regs']['flags'] & 0x8D5) == status
    return expected

def compare(native, case, core=False, dispatch=False, null=False):
    memory, regs, device = setup(case)
    expected = original(case, bytearray(memory), dict(regs), copy.deepcopy(device), core, dispatch)
    actual_regs = expected['captured'] if dispatch else regs
    # Prefix has no memory accesses on these commands. Verify this handoff
    # explicitly; native coverage begins at the setter entry, not at offset0.
    assert actual_regs is not None
    if dispatch:
        assert actual_regs['ax'] == (regs['ax'] & 255)
        assert all(actual_regs[n] == regs[n] for n in NAMES if n not in ('ax', 'ip', 'flags'))
    actual = native.run(case, bytearray(memory), actual_regs, copy.deepcopy(device), core, null)
    require(expected['memory'] == actual['memory'], case['name'] + ': full memory differs')
    for n in NAMES:
        mask = 0xFFFF
        require((expected['regs'][n] & mask) == (actual['regs'][n] & mask),
                f'{case["name"]}: {n} differs {expected["regs"][n]:04x}/{actual["regs"][n]:04x}')
    if not null:
        require(expected['events'] == actual['events'],
                case['name'] + ': ordered bus events differ\n' + str(expected['events']) + '\n' + str(actual['events']))
        require(expected['used'] == actual['used'], case['name'] + ': effects differ')
    if device:
        require(expected['device'].state() == actual['device'].state(), case['name'] + ': VGA state differs')
        require(expected['device'].trace == actual['device'].trace, case['name'] + ': VGA trace differs')
    if case['variant'].startswith('value-'):
        want = bytearray(memory)
        ss, sp = regs['ss'], regs['sp']
        word(want, physical(ss, sp - 2), regs['ds'])
        word(want, physical(ss, sp - 4), regs['cs'])
        want[physical(regs['cs'], case['latch'])] = regs['ax'] & 255
        assert expected['memory'] == bytes(want), 'independent transport/latch expectation differs'
    return expected

def input_hashes():
    paths = ['c/sound_latches.c', 'c/sound_latches.h', 'c/sound_latches_sym.h',
             'c/regs.h', 'c/special_blit.h', 'tools/cbuild.py', 'tools/difftest.py',
             'tools/bounded_process.py', 'tools/sound_latch_symtab.py',
             'tools/resources.py', 'tools/common.py', 'tests/sound_latches.py',
             'tests/minimap_vga.py', 'metadata/sound-oracle.json',
             'metadata/toolchain-lock.json']
    for name in TAILS:
        paths += [f'src/sound/{name}.asm', f'metadata/{name}-symbols.json',
                  f'metadata/{name}-regions.json', f'assets/{name}.dat']
    return {p: sha((ROOT / p).read_bytes()) for p in paths}

def worker(directory):
    before = input_hashes()
    pins = json.loads((ROOT/'metadata/sound-oracle.json').read_text())
    for driver, tails in TAILS.items():
        image, meta = IMAGES[driver]
        assert meta == pins[driver], 'Sound executable identity changed: ' + driver
        for start, latch in tails.values():
            assert image[start:start+8] == bytes((0x1E, 0x0E, 0x1F, 0xA2,
                                                latch & 255, latch >> 8, 0x1F, 0xCF))
    native = Native(directory)
    rows, sites, total, prefix = [], {n: set() for n in TAILS}, 0, {n: set() for n in TAILS}
    control_sites = {n: set() for n in TAILS}
    control_edges = {n: set() for n in TAILS}
    for case in cases():
        for core in (True, False):
            result = compare(native, case, core)
            sites[case['driver']].update(result['sites'])
            total += len(result['events'])
        if case['variant'].startswith('value-'):
            for core in (True, False):
                compare(native, case, core, null=True)
        rows.append(dict(name=case['name'], driver=case['driver'], command=case['command'],
                         core_and_adapter=True, provider=case.get('effect'), vga=case.get('vga')))
        gc.collect()
    dispatch_count = 0
    for driver in TAILS:
        for command in TAILS[driver]:
            case = next(c for c in cases() if c['driver'] == driver and c['command'] == command and c['variant'] == 'value-0c')
            for core in (True, False):
                result = compare(native, case, core, dispatch=True)
                prefix[driver].update(result['prefix'])
            dispatch_count += 1
    control_specs = [dispatch_case(driver, command) for driver in TAILS for command in range(256)]
    control_specs += [dispatch_case(driver, 4, value=5) | dict(name=driver+'-main-request-0405')
                      for driver in TAILS]
    for case in cases():
        if not case['variant'].startswith('value-'):
            control_specs.append(case | dict(name=case['name'] + '-control'))
    for case in control_specs:
        for core in (True, False):
            result = compare_control(native, case, core)
            control_sites[case['driver']].update(result['sites'] | result['prefix'])
            control_edges[case['driver']].update(result['edges'])
            total += len(result['events'])
        if case['variant'] == 'dispatch' and case['command'] in (0, 1, 2, 3, 4, 5, 6, 0x84, 255):
            for core in (True, False):
                compare_control(native, case, core, null=True)
        rows.append(dict(name=case['name'], driver=case['driver'], command=case['command'],
                         core_and_adapter=True, control=True,
                         provider=case.get('effect'), vga=case.get('vga')))
        gc.collect()
    witnesses = [(1, 'latch-saved-ds-low', True), (2, 'live-temporary-segment', True),
                 (3, 'value-0c', True), (4, 'live-saved-and-iret', False),
                 (5, 'value-0c', True), (6, 'live-saved-and-iret', False),
                 (10, 'latch-return-flags-low-05', False)]
    mutations = []
    for mutation, variant, core in witnesses:
        mutant = Native(directory, mutation)
        case = next(c for c in cases() if c['driver'] == 'adlib' and c['command'] == 4 and c['variant'] == variant)
        try:
            compare(mutant, case, core)
        except Mismatch as error:
            mutations.append(dict(mutation=mutation, case=case['name'], completed=True, mismatch=str(error)))
        else:
            raise AssertionError(f'Sound latch mutant{mutation} survived')
        gc.collect()
    for mutation, command in ((7, 4), (8, 4), (9, 6)):
        mutant = Native(directory, mutation)
        case = dispatch_case('adlib', command)
        try:
            compare_control(mutant, case, core=True)
        except Mismatch as error:
            mutations.append(dict(mutation=mutation, case=case['name'], completed=True, mismatch=str(error)))
        else:
            raise AssertionError(f'Sound control mutant{mutation} survived')
        gc.collect()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
    md.detail = True
    components = {}
    for driver, tails in TAILS.items():
        image = IMAGES[driver][0]
        wanted = {i.address for start, _ in tails.values() for i in md.disasm(image[start:start+8], start)}
        assert sites[driver] == wanted
        ranges = [[0, 0x14], [0x15, 0x3A]] if driver == 'adlib' else [[0, 0x31]]
        translated_ins = [i for start, end in ranges for i in md.disasm(image[start:end], start)]
        translated = {i.address for i in translated_ins}
        assert control_sites[driver] == translated, (driver, control_sites[driver] ^ translated)
        expected_edges = set()
        for ins in translated_ins:
            if ins.group(capstone.CS_GRP_JUMP):
                expected_edges.add((ins.address, ins.operands[0].imm & 0xFFFF))
                if ins.mnemonic != 'jmp':
                    expected_edges.add((ins.address, ins.address + ins.size))
        assert control_edges[driver] == expected_edges, (driver, control_edges[driver] ^ expected_edges)
        components[driver] = dict(image_sha256=sha(image), translated_code_bytes=sum(b-a for a,b in ranges),
            native_code_ranges=ranges, executed_instruction_addresses=sorted(control_sites[driver]),
            branch_edges=sorted(control_edges[driver]),
            tail_instruction_addresses=sorted(sites[driver]))
    assert before == input_hashes(), 'Inputs changed during bounded sound-latch campaign'
    write_json(REPORT, dict(case_count=len(rows), cases=rows, mutation_count=len(mutations),
        mutations=mutations, translated_code_bytes=106, components=components,
        dispatch_handoff_cases=dispatch_count, total_bus_events=total,
        limits=dict(worker_seconds=180, windows_process_mib=384, windows_tree_mib=640,
                    native_callback_budget=CAP, original_instruction_limit=STEPS),
        input_hashes=before,
        scope='Dispatch prefixes and six setter tails; update/detect/reset explicit untranslated exits; no playback or timing claim'))
    print(f'PASS sound control: {len(rows)} fixtures at core+IRET/seam boundaries; 106 bytes/65 sites/27 edges; '
          f'{dispatch_count} original-dispatch handoffs, {total} events, {len(mutations)} completed mutants', flush=True)

def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2]); return
    if sys.argv[1:]:
        raise SystemExit('Unexpected sound-latch arguments')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='sound-latches-', parent=BUILD) as directory:
        run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                    cwd=ROOT, timeout=180, memory_mib=384)

if __name__ == '__main__':
    main()

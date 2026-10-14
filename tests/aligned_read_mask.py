"""969C differential with explicit byte-port providers and live saved DX."""
import ctypes
import gc
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import aligned_masked as oracle
from common import ROOT, BUILD, sha, write_json
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build

CURRENT_CASE = {}
ORIGINAL_PREPARE = oracle.prepare
ORIGINAL_DEVICE = oracle.TraceDevice


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'initial_data_segment', 'game_data_segment', 'stack_segment', 'stack_offset',
        'packed_counts', 'width_state', 'source_cursor', 'mask_cursor',
        'destination_cursor', 'flags')]


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'work_value', 'packed_counts', 'port', 'source_cursor', 'mask_cursor',
        'destination_cursor', 'plane_counter', 'stack_offset', 'source_segment',
        'output_segment', 'flags')]


OUT_BYTE = ctypes.CFUNCTYPE(None, ctypes.c_void_p, oracle.MEM,
                           ctypes.c_uint16, ctypes.c_uint8, ctypes.c_uint16)
IN_BYTE = ctypes.CFUNCTYPE(ctypes.c_uint8, ctypes.c_void_p, oracle.MEM,
                          ctypes.c_uint16, ctypes.c_uint16)


class Ports(ctypes.Structure):
    _fields_ = [('context', ctypes.c_void_p), ('out_byte', OUT_BYTE),
                ('in_byte', IN_BYTE)]


def prepare(case):
    global CURRENT_CASE
    CURRENT_CASE = case
    return ORIGINAL_PREPARE(case)


class PortDevice(ORIGINAL_DEVICE):
    def __init__(self, *args):
        super().__init__(*args)
        self.case = dict(CURRENT_CASE)
        self.bus.device = self
        normal_out = self.vga.out

        def word_out(port, value, flags):
            if port not in (0x3c4, 0x3ce) and self.case.get('saved_dx'):
                # A constructed external-port provider records the live port.
                # No card/foreign-device equivalence is claimed for this case.
                self.vga.trace.append(('external-out', port, value, flags))
                self.vga.outcount += 1
            else:
                normal_out(port, value, flags)
        self.vga.out = word_out

    def out_port_byte(self, port, value, flags, mask=0xffff):
        if port != 0x3ce or value != 5:
            raise oracle.VerificationFailure('Unexpected byte selector provider argument')
        self.vga.gi = value
        self.vga.outcount += 1
        self.vga.trace.append(('outb', port, value, flags))
        self.events.add('outb', port, value, flags, mask)

    def in_port_byte(self, port, flags, mask=0xffff, uc=None):
        if port != 0x3cf:
            raise oracle.VerificationFailure('Unexpected byte read provider argument')
        value = self.case.get('mode_reply', self.vga.gc[self.vga.gi])
        self.vga.trace.append(('inb', port, value, flags))
        self.events.add('inb', port, value, flags, mask)
        if self.case.get('saved_dx'):
            load = (0x1010, 0x1213, 0x2345)[self.case['seed'] % 3]
            ss = self.case.get('ss', 0x7000)
            if self.case.get('same_segments'):
                ss = (load + 0x9a9) & 0xffff
            offset = (self.case.get('sp', 0x8000) - 14) & 0xffff
            oracle.put16(self.memory, ss, offset, self.case['saved_dx'])
            if uc is not None:
                raw = (ss << 4) + offset
                for n in range(2):
                    p = (raw + n) & 0xfffff
                    uc.mem_write(raw + n, bytes((self.memory[p],)))
                    if raw + n != p:
                        uc.mem_write(p, bytes((self.memory[p],)))
        return value


def configure():
    oracle.START, oracle.END, oracle.RETF = 0x969c, 0x9737, 0x9736
    oracle.UNKNOWN = set()
    oracle.ALL_INS = {i.address: i for i in oracle.MD.disasm(
        oracle.IMAGE[oracle.START:oracle.END], oracle.START)}
    oracle.BODY_INS = {p: i for p, i in oracle.ALL_INS.items() if p != oracle.RETF}
    oracle.BRANCHES = {p for p, i in oracle.BODY_INS.items()
        if i.group(oracle.capstone.CS_GRP_JUMP) or i.mnemonic.startswith('loop')}
    oracle.EDGES = {(p, i.operands[0].imm & 0xffff)
        for p, i in oracle.BODY_INS.items() if p in oracle.BRANCHES}
    oracle.EDGES |= {(p, p + i.size) for p, i in oracle.BODY_INS.items()
        if p in oracle.BRANCHES and i.mnemonic != 'jmp'}
    oracle.ARITH |= {'cmp'}
    oracle.EventTrace._KINDS |= {'outb': 3, 'inb': 4}
    oracle.TraceDevice = PortDevice
    oracle.prepare = prepare
    oracle.independent_planes = independent_planes


def independent_planes(initial, memory, regs, case, flags):
    planes = [bytearray(p) for p in initial]
    source_segment = oracle.oracle.get16(memory, regs['ds'],
                                          oracle.field('GraphicsResourceSegment'))
    source, mask, target = regs['si'], regs['bx'], regs['di']
    rows = (regs['cx'] >> 8) or 256
    count = (regs['cx'] & 255) or 65536
    direction = -1 if flags & 0x400 else 1
    for _ in range(rows):
        for _ in range(count):
            source_byte = memory[oracle.physical(source_segment, source)]
            selection = planes[3][target] & memory[oracle.physical(source_segment, mask)]
            keep = ~selection & 255
            planes[0][target] = (source_byte & selection) | (planes[0][target] & keep)
            planes[1][target] &= keep
            planes[2][target] |= selection
            planes[3][target] &= keep
            source = (source + direction) & 65535
            target = (target + direction) & 65535
            mask = (mask + 1) & 65535
        source = (source + case.get('source_row_advance', 7)) & 65535
        mask = (mask + case.get('source_row_advance', 7)) & 65535
        target = (target + 9) & 65535
    return planes


class Native:
    _MaskedCall, _MaskedResult = Call, Result
    def __init__(self, directory, mutation=0):
        self.dll = ctypes.CDLL(str(build(Path(directory) / f'read-mask-{mutation}.dll',
                                         mutation, 'aligned_read_mask')))
        self.core = self.dll.lmn_draw_aligned_read_mask_core
        self.core.argtypes = [oracle.MEM, ctypes.POINTER(Call),
                              ctypes.POINTER(oracle.RasterBus), ctypes.POINTER(Ports)]
        self.core.restype = Result
        self.adapter = self.dll.lmn_draw_aligned_read_mask_adapter
        self.adapter.argtypes = [oracle.MEM, ctypes.POINTER(oracle.Regs), ctypes.c_uint16,
                                 ctypes.POINTER(oracle.RasterBus), ctypes.POINTER(Ports)]
        self.adapter.restype = None

    def provider(self, bus):
        device = bus._obj.device
        @OUT_BYTE
        def out(_ctx, _mem, port, value, flags):
            try:
                device.out_port_byte(port, value, flags)
                device.check('byte selector')
            except BaseException as error:
                oracle.native_failure(oracle.NATIVE_CALLBACK_EXIT, str(error))
        @IN_BYTE
        def inp(_ctx, _mem, port, flags):
            try:
                result = device.in_port_byte(port, flags)
                device.check('byte read')
                return result
            except BaseException as error:
                oracle.native_failure(oracle.NATIVE_CALLBACK_EXIT, str(error))
        return Ports(None, out, inp)

    def lmn_draw_aligned_masked_core(self, memory, call, bus):
        ports = self.provider(bus)
        return self.core(memory, call, bus, ctypes.byref(ports))

    def lmn_draw_aligned_masked_adapter(self, memory, regs, game_ds, bus):
        ports = self.provider(bus)
        self.adapter(memory, regs, game_ds, bus, ctypes.byref(ports))


def cases():
    out = []
    def add(name, **fields):
        out.append(dict(name=name, seed=len(out), plane_limit=4, **fields))
    for df in (0, 1):
        for reply in (8, 9, 0, 255):
            add(f'read-mode-{reply}-df-{df}', width=3, height=2, df=df,
                mode_reply=reply, independent=True)
    add('zero-byte-count-65536', width=0, height=1)
    add('zero-row-count-256', width=1, height=0, independent=True)
    add('provider-changes-live-saved-DX', width=2, height=1, saved_dx=0x3cf)
    add('push-DS-overwrites-graphics-pointer', width=1, height=1,
        same_segments=True, sp=0x1fe6)
    add('saved-cursors-alias-row-fields', width=2, height=2,
        same_segments=True, sp=0x670c)
    add('distinct-incoming-DS', width=2, height=2, initial_data_segment=0x6000,
        independent=True)
    add('mask-INC-overflow', width=2, height=1, mask_cursor=0x7fff, independent=True)
    add('physical-and-offset-wrap', width=2, height=1, df=True,
        source_segment=0xffff, source_cursor=0xffff, mask_cursor=0xffff,
        destination_cursor=0xffff, ss=0xffff, sp=0x0010)
    add('SP-FFFE-frame-boundary', width=1, height=1, sp=0xfffe, return_boundary=True)
    return out


def worker(directory):
    configure()
    report = BUILD / 'aligned-read-mask-differential.json'
    report.unlink(missing_ok=True)
    lib = Native(directory)
    baseline = cases()
    sites, edges = set(), set()
    for case in baseline:
        seen, branches, _ = oracle.compare_core(lib, case)
        sites |= seen; edges |= branches
        gc.collect()
    if sites != set(oracle.BODY_INS) or edges != oracle.EDGES:
        raise oracle.VerificationFailure('Read-mask core site/edge coverage differs')
    probes = [baseline[0], baseline[1], baseline[10]]
    for case in probes:
        oracle.isolated_original_retf(lib, case)
        gc.collect()
    oracle.check_adapter(lib, baseline[-1])
    mutations = []
    for mutation in (1, 2, 3):
        try:
            oracle.compare_core(Native(directory, mutation), baseline[0])
        except oracle.Mismatch as error:
            mutations.append(dict(mutation=mutation, case=baseline[0]['name'], reason=str(error)))
        else:
            raise oracle.VerificationFailure(f'READ_MASK_MUTATION={mutation} survived')
        finally:
            gc.collect()
    dependencies = ('c/aligned_read_mask.c', 'c/aligned_read_mask.h', 'c/lemmings_sym.h',
        'c/special_blit.h', 'c/regs.h', 'tests/aligned_read_mask.py', 'tests/aligned_masked.py',
        'tests/minimap_vga.py', 'tests/dat_io.py', 'tests/dat_io_c.py', 'tools/cbuild.py',
        'tools/bounded_process.py', 'tools/difftest.py', 'tools/coverage.py',
        'tools/unpack.py', 'metadata/symbols.json', 'src/planar_drawing.asm')
    write_json(report, dict(image='main', image_sha256=sha(oracle.IMAGE), case_count=len(baseline),
        cases=baseline, mutation_count=3, mutations_detected=mutations,
        executed_instruction_addresses=sorted(sites | {oracle.RETF}),
        body_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
        translated_code_bytes=155, physical_code_bytes=155,
        routine=dict(start=0x969c,end=0x9737,byte_count=155,
                     byte_sha256=sha(oracle.IMAGE[0x969c:0x9737])),
        original_retf_probe_case_count=len(probes),
        original_retf_probe_cases=[c['name'] for c in probes],
        input_hashes={p: sha((ROOT / p).read_bytes()) for p in dependencies},
        domain='Constructed969C body, explicit byte OUT/IN provider including mode-byte replies8/9/0/FF and live saved-DX change. Normal ports use VGA readmode1 plane3 comparison/mask; changed wordport3CF is a recorded external provider seam with no card-equivalence claim. AllRAM/registers/defined flags/ordered RAM and ports and VGA state; independent normal plane footprints. Intact code/quiescent IRQ. SPFFFE adapter-only boundary.'))
    print(f'PASS aligned read mask: {len(baseline)} cases, {len(sites)} body sites, '
          f'{len(edges)} edges, {len(probes)} RETF probes; 3 mutants detected')


if __name__ == '__main__':
    (BUILD / 'aligned-read-mask-differential.json').unlink(missing_ok=True)
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        worker(sys.argv[2])
    elif len(sys.argv) == 1:
        with temporary_build_directory(prefix='aligned-read-mask-', parent=BUILD) as directory:
            run_bounded([sys.executable, str(Path(__file__).resolve()), '--worker', directory],
                         cwd=ROOT, timeout=180)
    else:
        raise SystemExit('Unexpected aligned_read_mask arguments')

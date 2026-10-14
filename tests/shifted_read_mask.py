"""Bounded original/native differential for shifted read-mask body 8D66."""
import ctypes
import gc
import random
import subprocess
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import capstone
import aligned_masked as oracle
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, write_json
from dat_io_c import Regs
from minimap_vga import VGA_BASE
from unpack import relocated


START = 0x8d66
RETF = 0x8ff6
END = RETF + 1
UNKNOWN = {0x8f8d}
MAX_STEPS = 8_000_000
MAX_BUS_EVENTS = 4_000_000
MAX_VGA_EVENTS = 400_000
oracle.MAX_STEPS = MAX_STEPS
oracle.MAX_BUS_EVENTS = MAX_BUS_EVENTS
oracle.MAX_VGA_EVENTS = MAX_VGA_EVENTS

IMAGE, ORACLE = oracle.IMAGE, oracle.ORACLE
SYMS = oracle.SYMS
MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True


class Call(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'initial_data_segment', 'game_data_segment', 'stack_segment',
        'stack_offset', 'packed_counts', 'width_state', 'source_cursor',
        'mask_cursor', 'destination_cursor', 'flags')]


class Result(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint16) for name in (
        'work_value', 'packed_counts', 'port', 'source_cursor',
        'mask_cursor', 'destination_cursor', 'plane_counter', 'stack_offset',
        'source_segment', 'output_segment', 'flags')]


class Native:
    _MaskedCall = Call

    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'shifted-read-mask-m{mutation}.dll',
                     mutation, 'shifted_read_mask')
        self.dll = ctypes.CDLL(str(path))
        self.core = self.dll.lmn_draw_shifted_read_mask_core
        self.core.argtypes = [oracle.MEM, ctypes.POINTER(Call),
                              ctypes.POINTER(oracle.RasterBus)]
        self.core.restype = Result
        self.adapter = self.dll.lmn_draw_shifted_read_mask_adapter
        self.adapter.argtypes = [oracle.MEM, ctypes.POINTER(Regs),
                                 ctypes.c_uint16,
                                 ctypes.POINTER(oracle.RasterBus)]
        self.adapter.restype = None

    # Reuse the shared bounded Unicorn/VGA comparison by exposing its logical
    # renderer entry names around this body's own API.
    def lmn_draw_aligned_masked_core(self, memory, call, bus):
        return self.core(memory, call, bus)

    def lmn_draw_aligned_masked_adapter(self, memory, regs, game_ds, bus):
        self.adapter(memory, regs, game_ds, bus)


def configure():
    oracle.START, oracle.END, oracle.RETF = START, END, RETF
    oracle.UNKNOWN = set(UNKNOWN)
    decoded = {i.address: i for i in MD.disasm(IMAGE[START:END], START)}
    oracle.ALL_INS = {address: ins for address, ins in decoded.items()
                      if address not in UNKNOWN}
    oracle.BODY_INS = {address: ins for address, ins in oracle.ALL_INS.items()
                       if address != RETF}
    oracle.BRANCHES = {address for address, ins in oracle.BODY_INS.items()
        if ins.group(capstone.CS_GRP_JUMP) or ins.mnemonic.startswith('loop')}
    oracle.EDGES = {(address, ins.operands[0].imm & 0xffff)
        for address, ins in oracle.BODY_INS.items()
        if address in oracle.BRANCHES}
    oracle.EDGES |= {(address, address + ins.size)
        for address, ins in oracle.BODY_INS.items()
        if address in oracle.BRANCHES and ins.mnemonic != 'jmp'}
    oracle.ARITH |= {'cmp'}
    oracle.independent_planes = independent_planes
    if len(decoded) != 370 or len(oracle.BODY_INS) != 368:
        raise oracle.VerificationFailure(
            f'unexpected static accounting: {len(decoded)} decoded sites, '
            f'{len(oracle.BODY_INS)} core sites')
    if IMAGE[0x8f8d] != 0x90:
        raise oracle.VerificationFailure('UNKNOWN byte 8F8D changed')


def prepare(case):
    rng = random.Random(0x8d66 + case['seed'])
    load = (0x1010, 0x1213, 0x2345)[case['seed'] % 3]
    memory = bytearray(rng.randbytes(1 << 20))
    memory[load << 4:(load << 4) + len(IMAGE)] = relocated(
        IMAGE, ORACLE['relocations'], load)
    game_ds = (load + 0x09a9) & 0xffff
    initial_ds = case.get('initial_ds', game_ds)
    ss = case.get('ss', 0x7000)
    sp = case.get('sp', 0x8000)
    if case.get('same_segments'):
        initial_ds = game_ds
        ss = game_ds
    source_segment = (game_ds if case.get('source_is_game_data') else
                      case.get('source_segment', 0x5000))

    # The width-zero shifter makes the original LOOP wrap through all 65,536
    # bytes of live DS. Seed that whole constructed segment so its first
    # forward carry sweep leaves the subsequent A948 read at one instead of
    # accidentally launching the unchecked 0/large-shift path.
    if case.get('zero_cl_stable_field'):
        base = oracle.physical(game_ds, 0)
        for offset in range(0x10000):
            memory[(base + offset) & 0xfffff] = 0

    # The first DEC reads incoming DS:6704. Later row/plane fields are loaded
    # through the live game-data ES/DS values and remain memory-backed.
    oracle.put16(memory, game_ds, oracle.field('DrawingSourcePlaneExtent'),
                 case.get('plane_extent', 0x0040))
    oracle.put16(memory, game_ds, oracle.field('DrawingSourceRowAdvance'),
                 case.get('source_row_advance', 0x0007))
    oracle.put16(memory, game_ds,
                 oracle.field('DrawingActiveDestinationRowAdvance'),
                 case.get('destination_advance', 0x0009))
    oracle.put_byte(memory, game_ds, oracle.field('DrawingLeftBitShiftByte'),
                    case.get('shift', 1))
    if case.get('zero_cl_stable_field'):
        oracle.put_byte(memory, game_ds,
                        oracle.field('DrawingLeftBitShiftByte') - 1, 1)
    oracle.put16(memory, initial_ds, oracle.field('GraphicsResourceSegment'),
                 source_segment)
    if oracle.physical(initial_ds, oracle.field('DrawingActiveDestinationRowAdvance')) != \
            oracle.physical(game_ds, oracle.field('DrawingActiveDestinationRowAdvance')):
        oracle.put16(memory, initial_ds,
                     oracle.field('DrawingActiveDestinationRowAdvance'),
                     case.get('entry_destination_advance', 0x0011))

    regs = {name: rng.randrange(0x10000) for name in oracle.oracle.REG_NAMES}
    regs.update(cs=load, ip=START, ds=initial_ds, ss=ss, sp=sp,
        cx=((case['height'] & 0xff) << 8) | (case['width'] & 0xff),
        dx=((case.get('plane_limit', 1) & 0xff) << 8) |
           case.get('low_state', 0x6d),
        bx=case.get('mask_cursor', 0x1000),
        si=case.get('source_cursor', 0x2000),
        di=case.get('destination_cursor', 0x0410),
        bp=case.get('incoming_bp', 0x7654))
    flags = 2 | ((case['seed'] * 0x95) & 0x0ad5)
    if case.get('df'):
        flags |= 0x0400
    else:
        flags &= ~0x0400
    oracle.put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xedd1))
    oracle.put16(memory, regs['ss'], (regs['sp'] + 2) & 0xffff,
                 case.get('outer_cs', 0xbabe))
    for n, value in enumerate(case.get('mask_bytes', ())):
        oracle.put_byte(memory, source_segment, (regs['bx'] + n) & 0xffff, value)
    for n, value in enumerate(case.get('source_bytes', ())):
        oracle.put_byte(memory, source_segment, (regs['si'] + n) & 0xffff, value)
    return memory, regs, flags, game_ds


def _shift_right(values, count):
    values = list(values)
    for _ in range(count):
        carry = 0
        for index, value in enumerate(values):
            values[index] = (value >> 1) | (carry << 7)
            carry = value & 1
    return values


def independent_planes(initial_planes, memory, regs, case, flags):
    """Proved normal DF-clear, nonalias pixel path, computed without C helpers."""
    expected = [bytearray(plane) for plane in initial_planes]
    initial_ds = regs['ds']
    game_ds = (regs['cs'] + 0x09a9) & 0xffff
    source_segment = oracle.oracle.get16(memory, initial_ds,
                                        oracle.field('GraphicsResourceSegment'))
    width = regs['cx'] & 0xff
    rows_byte = regs['cx'] >> 8
    rows = rows_byte if rows_byte else 256
    planes = (regs['dx'] >> 8) & 0xff
    passes = min(planes, 4) if planes else 4
    source_advance = oracle.oracle.get16(memory, game_ds,
                                        oracle.field('DrawingSourceRowAdvance'))
    dest_advance = oracle.oracle.get16(memory, game_ds,
        oracle.field('DrawingActiveDestinationRowAdvance'))
    if oracle.physical(initial_ds,
            oracle.field('DrawingActiveDestinationRowAdvance')) == \
            oracle.physical(game_ds,
            oracle.field('DrawingActiveDestinationRowAdvance')):
        dest_advance = (dest_advance - 1) & 0xffff
    extent = oracle.oracle.get16(memory, game_ds,
                                oracle.field('DrawingSourcePlaneExtent'))
    shift = memory[oracle.physical(game_ds,
                                   oracle.field('DrawingLeftBitShiftByte'))]

    # The initial cache pass shifts mask bytes with SHR/RCR, then intersects
    # them with read-mode-1 color-compare output (only plane 3 is cared). The
    # cache is packed as width+1 bytes per row, independent of the later source
    # row stride. These fixtures keep DF clear and scratch/source ranges apart.
    mask_rows = []
    mask_source = regs['bx']
    destination = regs['di']
    for _row in range(rows):
        original = [memory[oracle.physical(source_segment,
                    (mask_source + n) & 0xffff)] for n in range(width)]
        shifted = _shift_right(original + [0], shift)
        gated = []
        for column, mask in enumerate(shifted):
            target = (destination + column) & 0xffff
            gated.append(mask & initial_planes[3][target])
        mask_rows.append(gated)
        mask_source=(mask_source + width + source_advance) & 0xffff
        destination=(destination + width + 1 + dest_advance) & 0xffff

    for plane in range(passes):
        source=(regs['si'] + plane * extent) & 0xffff
        destination=regs['di']
        for row in range(rows):
            original=[memory[oracle.physical(source_segment,
                    (source+n)&0xffff)] for n in range(width)]
            pixels=_shift_right(original+[0],shift)
            for column, source_byte in enumerate(pixels):
                target=(destination+column)&0xffff
                mask=mask_rows[row][column]
                # Each path reads A000:DI immediately before its write, so
                # latches contain the current destination bytes at this offset.
                if plane == 0:
                    cpu=(source_byte&mask)
                    for lane in range(4):
                        old=expected[lane][target]
                        # Setup writes AX=0003: GC3 data is zero (replace,
                        # no rotation), despite index 3 being the register.
                        data=0 if lane else cpu
                        expected[lane][target]=(data&mask)|(old&(~mask&0xff))
                else:
                    expected[plane][target]=(
                        expected[plane][target] | (source_byte&mask))
            source=(source + width + source_advance)&0xffff
            destination=(destination + width + 1 + dest_advance)&0xffff
    return expected


def cases():
    out=[]
    def add(name,**fields):
        out.append(dict(name=name,seed=len(out),**fields))

    # Every plane-count branch plus each of the seven legal shifts and both
    # row-loop outcomes. Small default cases also feed the independent planes.
    for limit in range(1,6):
        add(f'planes-{limit}-shift-{(limit % 7) + 1}-two-rows',
            plane_limit=limit,width=2,height=2,shift=(limit % 7)+1,
            source_row_advance=5,destination_advance=9,independent=True,
            mask_bytes=(0x01,0x02,0x04,0x08,0x10,0x20),
            source_bytes=(0x81,0x42,0x24,0x18,0x66,0x99))
    for shift in range(1,8):
        add(f'one-plane-shift-{shift}',plane_limit=1,width=3,height=1,
            shift=shift,source_row_advance=5,destination_advance=9,
            independent=True,mask_bytes=(1,2,4,8),
            source_bytes=(0x81,0x42,0x24,0x18))
    add('zero-plane-count-wraps-through-four-passes',plane_limit=0,
        width=2,height=1,shift=3,source_row_advance=7,independent=True)
    add('ff-plane-count-still-stops-after-four-passes',plane_limit=0xff,
        width=2,height=1,shift=5,source_row_advance=7)
    add('DF-reverses-source-copies-and-sentinels',plane_limit=4,width=3,
        height=2,shift=4,df=True,source_cursor=0x2100,mask_cursor=0x1100,
        destination_cursor=0x0420,source_row_advance=5)
    add('zero-shift-byte-wraps-to-256-passes',plane_limit=1,width=2,
        height=1,shift=0,source_row_advance=3)
    add('zero-CL-shift-LOOP-wraps-to-65536',plane_limit=1,width=0,
        height=1,shift=8,source_row_advance=1,mask_cursor=0x2000,
        source_cursor=0x3000,zero_cl_stable_field=True)
    add('CL-FF-drawing-loop-wraps-to-65536',plane_limit=1,width=0xff,
        height=1,shift=1,source_row_advance=1,mask_cursor=0x1000,
        source_cursor=0x3000)
    add('zero-CH-runs-256-rows',plane_limit=1,width=1,height=0,
        shift=2,source_row_advance=3,destination_advance=5)
    add('incoming-DS-distinct-from-relocated-game-DS',plane_limit=3,
        width=2,height=2,shift=7,initial_ds=0x6000,
        source_row_advance=0x000b,entry_destination_advance=0x0017,
        destination_advance=0x000d)
    add('entry-push-overwrites-live-shift-byte',plane_limit=1,width=1,
        height=1,shift=2,same_segments=True,ss=0x7000,sp=0xa94a)
    add('live-SS-save-overwrites-plane-extent',plane_limit=2,width=1,
        height=1,shift=2,same_segments=True,sp=0x66fa)
    add('live-SS-save-overwrites-source-scratch',plane_limit=1,width=2,
        height=2,shift=3,same_segments=True,sp=0x674a)
    add('scratch-source-and-mask-start-alias',plane_limit=2,width=2,
        height=2,shift=2,source_is_game_data=True,mask_cursor=0x6748,
        source_cursor=0x6706,source_row_advance=5)
    add('physical-and-SP-wrap-with-DF',plane_limit=2,width=2,height=1,
        shift=6,df=True,initial_ds=0xffff,source_segment=0xffff,
        source_cursor=0xfffe,mask_cursor=0xfffe,destination_cursor=0xfffe,
        ss=0xffff,sp=0x0002)
    return out


def _compare_case(lib, case):
    oracle.prepare = prepare
    return oracle.compare_core(lib, case)


def worker(directory):
    configure()
    report_path=BUILD/'shifted-read-mask-differential.json'
    report_path.unlink(missing_ok=True)
    baseline=Native(directory)
    fixture_cases=cases()
    seen=set(); edges=set(); reports=[]
    for case in fixture_cases:
        if case.get('independent') and (case.get('df') or
                case.get('source_is_game_data') or case.get('same_segments')):
            raise oracle.VerificationFailure(
                'independent VGA case has an aliasing or reverse-copy domain')
        c_sites,c_edges,result=_compare_case(baseline,case)
        seen|=c_sites; edges|=c_edges
        reports.append(dict(name=case['name'],seed=case['seed'],input=case,
            result={name:getattr(result,name) for name,_ in result._fields_}))
        gc.collect()
    if seen != set(oracle.BODY_INS):
        raise oracle.VerificationFailure(
            f'core site coverage differs: missing={sorted(set(oracle.BODY_INS)-seen)}')
    if edges != oracle.EDGES:
        raise oracle.VerificationFailure(
            f'branch-edge coverage differs: missing={sorted(oracle.EDGES-edges)}, '
            f'extra={sorted(edges-oracle.EDGES)}')

    retf_cases=[fixture_cases[0],fixture_cases[3],fixture_cases[19]]
    for case in retf_cases:
        oracle.isolated_original_retf(baseline,case)
        gc.collect()
    adapter_cases=(fixture_cases[0],fixture_cases[1],fixture_cases[4],
                   fixture_cases[-1])
    for case in adapter_cases:
        oracle.check_adapter(baseline,case)
        gc.collect()

    sentinels={
        1: next(c for c in fixture_cases if c['name']=='one-plane-shift-1'),
        2: next(c for c in fixture_cases if c['name']=='planes-2-shift-3-two-rows'),
        3: next(c for c in fixture_cases if c['name']=='planes-2-shift-3-two-rows'),
    }
    mutations=[]
    for mutation in (1,2,3):
        detected=None
        try:
            _compare_case(Native(directory,mutation),sentinels[mutation])
        except oracle.Mismatch as error:
            detected=dict(case=sentinels[mutation]['name'],reason=str(error)[:400])
        if detected is None:
            raise oracle.VerificationFailure(
                f'SHIFTED_READ_MASK_MUTATION={mutation} survived')
        mutations.append(dict(mutation=mutation,**detected))
        gc.collect()

    inputs=(
        'c/shifted_read_mask.c','c/shifted_read_mask.h','c/special_blit.h',
        'c/regs.h','c/lemmings_sym.h','tests/shifted_read_mask.py',
        'tests/aligned_masked.py','tests/minimap_vga.py','tests/dat_io.py',
        'tests/dat_io_c.py','tools/common.py','tools/unpack.py',
        'tools/cbuild.py','tools/bounded_process.py','metadata/symbols.json',
        'build/unpack.json','src/planar_drawing.asm',
        'docs/shifted-drawing.md','docs/shifted-read-mask.md')
    write_json(report_path,dict(image='main',image_sha256=sha(IMAGE),
        case_count=len(fixture_cases),cases=reports,
        mutation_count=len(mutations),mutations_detected=mutations,
        executed_instruction_addresses=sorted(seen|{RETF}),
        body_instruction_addresses=sorted(seen),
        branch_edges=sorted([list(edge) for edge in edges]),
        physical_code_bytes=END-START,
        translated_code_bytes=sum(ins.size for ins in oracle.BODY_INS.values()),
        decoded_code_bytes_excluding_unknown=sum(ins.size for ins in oracle.ALL_INS.values()),
        physical_instruction_sites=369,core_instruction_sites=len(oracle.BODY_INS),
        decoded_instruction_sites_excluding_unknown=len(oracle.ALL_INS),
        decoded_instruction_sites_including_unknown=(len(oracle.ALL_INS)+len(UNKNOWN)),
        branch_edge_count=len(edges),
        adapter_instruction_sites=1,adapter_code_bytes=1,
        adapter_instruction_address=RETF,adapter_instruction_addresses=[RETF],
        unknown_sites_excluded=sorted(UNKNOWN),
        unknown_bytes=[dict(address=address,value=IMAGE[address])
                       for address in sorted(UNKNOWN)],
        range_inclusive=f'{START:04X}..{RETF:04X}',
        range_sha256=sha(IMAGE[START:END]),
        original_retf_probe_cases=[c['name'] for c in retf_cases],
        original_retf_probe_exclusions=[fixture_cases[-1]['name']],
        adapter_probe_case_count=len(adapter_cases),
        adapter_probe_cases=[c['name'] for c in adapter_cases],
        input_hashes={path:sha((ROOT/path).read_bytes()) for path in inputs},
        event_limits=dict(original_steps=MAX_STEPS,bus_events=MAX_BUS_EVENTS,
                          vga_device_trace=MAX_VGA_EVENTS),
        defined_flags=dict(arithmetic='0x0FD7',
                           logical_with_AF_undefined='0x0FC7'),
        domain='Constructed 1MiB memory and quiescent IRQs. The only discovered normal incoming edge is 88F0->8D66; the core ends after POP DS at 8FF5 and the adapter consumes the unchanged RETF at 8FF6. UNKNOWN 8F8D is excluded. Coverage separates 656 decoded body bytes, UNKNOWN classification, translated C sites, executed sites, and the adapter. Word-port outputs, SS mirrors, VGA state, ordered RAM accesses and defined flags are compared. All count/shift wrap cases have hard worker, event, and memory limits; a limit failure is a verification failure.'))
    print(f'PASS shifted read-mask: {len(fixture_cases)} cases, {len(seen)} core sites, '
          f'{len(edges)} branch edges, {len(retf_cases)} RETF probes, '
          f'{len(adapter_cases)} adapter probes; {len(mutations)} mutations detected')


def main():
    report=BUILD/'shifted-read-mask-differential.json'
    report.unlink(missing_ok=True)
    if len(sys.argv)==3 and sys.argv[1]=='--worker':
        worker(sys.argv[2])
        return
    with temporary_build_directory(prefix='shifted-read-mask-',parent=BUILD) as temp:
        result=run_bounded([sys.executable,str(Path(__file__).resolve()),
                            '--worker',temp],cwd=ROOT,timeout=180,
                           memory_mib=512,check=False,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,text=True)
        if result.returncode==86:
            raise oracle.GuardExhaustion(
                'native callback worker exited after a finite trace guard: '
                f'{result.stdout}{result.stderr}')
        if result.returncode==87:
            raise oracle.VerificationFailure(
                'native callback worker exited after a callback failure')
        if result.returncode!=0:
            raise oracle.VerificationFailure(
                f'bounded worker failed ({result.returncode}): {result.stdout}\n'
                f'{result.stderr}')
        print(result.stdout,end='')


if __name__=='__main__':
    main()

"""Exhaustive byte-pair channel arithmetic and bounded live-stack wrappers."""
import ast
import ctypes
import gc
import random
import subprocess
import time
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE
from unicorn import x86_const as x
import video_restore as video
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import ROOT, BUILD, sha, read_json, write_json
from unpack import ASSET, unpack, relocated

common, caller = video.fixture, video.drawing
oracle = caller.oracle
IMAGE, ORACLE = unpack(ASSET.read_bytes())
ENTRIES = (0x566c, 0x5685, 0x5696, 0x569b, 0x570c)
RETURNS = ((0x5684,), (0x5695,), (0x56e1,), (0x56e1,), (0x571e, 0x5725))
BLOCKS = ((0x566c, bytes.fromhex('d0e8d0ebd0e8d0eb240980e309e81f00d0e0d0e3d0e0d0e3c3')),
    (0x5685, bytes.fromhex('d0e8d0eb240980e309e80a00d0e0d0e3c3')),
    (0x5696, bytes.fromhex('240980e3098ae0d0e8d0e8d0e8d0e480e40224010ac48afbd0ebd0ebd0ebd0e780e70280e3010adf3ac3740e7707fec0bdff00eb05fec8bdff008ae0d0e0d0e0d0e0d0ec240880e4010ac4c3')),
    (0x570c, bytes.fromhex('3ac4740e7f0dfec0b3ff3ac474047f07fec0c3fec8ebf1fec8c3')))
INS = {i.address: i for p, b in BLOCKS for i in video.MD.disasm(b, p)}
EDGES = {(p, i.operands[0].imm & 65535) for p, i in INS.items() if i.group(video.capstone.CS_GRP_JUMP)}
EDGES |= {(p, p+i.size) for p, i in INS.items() if i.group(video.capstone.CS_GRP_JUMP) and i.mnemonic != 'jmp'}
REPORT = BUILD / 'palette-channels-differential.json'
ORIGINAL_REPORT = BUILD / 'palette-channels-contract-original.json'
ARITH, FULL, LOGIC = 0x8d5, 0xfd7, 0xfc7


class Result(ctypes.Structure):
    _fields_ = [('state', video.State), ('code_segment', ctypes.c_uint16),
               ('continuation', ctypes.c_uint16), ('status', ctypes.c_int)]


def fail(message):
    raise common.VerificationFailure(message)


def status_bits(value):
    return (4 if value.bit_count() % 2 == 0 else 0) | (0x40 if value == 0 else 0) | (value & 0x80)


def mathematical(regs, flags, entry):
    """Channel values/last-operation flags, independent of instruction replay."""
    result = dict(regs, flags=flags)
    low, target = regs['ax'] & 255, (regs['ax'] >> 8) if entry == 4 else regs['bx'] & 255
    if entry == 4:
        current_signed = low if low < 128 else low - 256
        target_signed = target if target < 128 else target - 256
        distance = abs(target_signed-current_signed)
        direction = 1 if target_signed > current_signed else -1
        value = (current_signed + direction * min(2, distance)) & 255
        if distance:
            result['bx'] = (regs['bx'] & 0xff00) | 255
        result['ax'] = (target << 8) | value
        result['ip'] = 0x5725 if direction == -1 and distance >= 2 else 0x571e
        if distance < 2:
            changed = 0x44  # The final CMP sees equal bytes.
        else:
            before = (current_signed + direction) & 255
            changed = status_bits(value) | (1 if before < target else 0)
            if (before ^ 1 ^ value) & 16: changed |= 16
            if direction == 1 and before == 127 or direction == -1 and before == 128: changed |= 0x800
        result['flags'] = (flags & ~ARITH) | changed
        return result, FULL
    shift = (2, 1, 0, 0)[entry]
    source, destination = low >> shift, target >> shift
    decode = lambda v: ((v & 1) << 1) | ((v >> 3) & 1)
    current, wanted = decode(source), decode(destination)
    stepped = current + (1 if wanted > current else -1 if wanted < current else 0)
    encoded = ((stepped & 1) << 3) | (stepped >> 1)
    result['ax'] = ((stepped >> 1) << 8) | (encoded << shift)
    result['bx'] = (((destination << 1) & 2) << 8) | (wanted << shift)
    if current != wanted: result['bp'] = 255
    result['flags'] = (flags & ~ARITH) | status_bits(wanted << shift if shift else encoded)
    result['ip'] = RETURNS[entry][0]
    return result, LOGIC


def mask_after(pc, prior):
    mnemonic = INS[pc].mnemonic
    if mnemonic in ('and', 'or', 'shr', 'shl'): return LOGIC
    if mnemonic == 'cmp': return FULL
    if mnemonic in ('inc', 'dec'): return (prior & 1) | (FULL & ~1)
    return prior


class Native:
    def __init__(self, directory, mutation=0, *, compile=False):
        p = Path(directory) / f'palette-channels-m{mutation}.dll'
        if compile: build(p, mutation, 'palette_channels')
        self.lib = ctypes.CDLL(str(p))
        self.core = self.lib.lmn_step_palette_channel_core
        self.core.argtypes = [video.MEM, ctypes.c_uint16, ctypes.POINTER(video.State), ctypes.c_int, ctypes.POINTER(common.RasterBus)]
        self.core.restype = Result
        self.adapter = self.lib.lmn_step_palette_channel_adapter
        self.adapter.argtypes = [video.MEM, ctypes.POINTER(video.Regs), ctypes.c_int, ctypes.POINTER(common.RasterBus)]
        self.adapter.restype = None


def input_hashes(native=False):
    paths = set(video.input_hashes(False)) | {'tests/palette_channels.py', 'docs/palette-channels.md'}
    if native:
        paths |= {'c/palette_channels.c', 'c/palette_channels.h', 'c/video_restore.h',
            'c/regs.h', 'c/special_blit.h', 'c/lemmings_sym.h', 'tools/cbuild.py',
            'tools/difftest.py', 'tools/coverage.py'}
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def identity():
    if (sha(IMAGE) != 'b0c4ef403e4bd28fa7913cb51a8c87e4dbbba8c4f1c36ea1594ba4424d64ee4e'
        or sha(ASSET.read_bytes()) != '5e176d21570eb474f68b12920450f5b4ccc25a10c3dd2a47e126b0b143ee0b8d'
        or ORACLE != read_json(ROOT/'metadata/oracle.json') or len(INS) != 69
        or any(IMAGE[p:p+len(b)] != b for p, b in BLOCKS)):
        fail('Pinned palette channel identity/boundaries differ')


def matrix_worker(entry, directory, native_directory=None, count=65536):
    """One fixed-size machine; only outer-RET hooks, no growing case traces."""
    identity()
    before = input_hashes(native_directory is not None)
    memory = bytearray((1 << 20))
    load = (0x1010, 0x1213, 0x2345)[entry % 3]
    loaded = relocated(IMAGE, ORACLE['relocations'], load)
    memory[load << 4:(load << 4)+len(loaded)] = loaded
    native_memory = bytearray(memory)
    machine = Uc(UC_ARCH_X86, UC_MODE_16)
    machine.mem_map(0, 2 << 20)
    machine.mem_write(0, bytes(memory)*2)
    stopped, failed = [False], []
    def stop(_uc, _pc, _size, _):
        stopped[0] = True; machine.emu_stop()
    for pc in RETURNS[entry]:
        p = (load << 4) + pc
        machine.hook_add(UC_HOOK_CODE, stop, begin=p, end=p)
    stack = 0x78000
    # Only wrappers write/read their known two-byte near-CALL frame.
    def guard(_uc, access, address, size, value, _):
        if entry >= 2 or address != stack-2 or size != 2:
            failed.append((access,address,size)); machine.emu_stop()
        elif access == UC_MEM_WRITE:  # UC_MEM_WRITE, shadow only the actual word store.
            memory[address:address+2] = value.to_bytes(2, 'little')
    machine.hook_add(UC_HOOK_MEM_READ, guard)
    machine.hook_add(UC_HOOK_MEM_WRITE, guard)
    native = Native(native_directory) if native_directory is not None else None
    mem_buffer = video.buffer(native_memory)
    names = tuple(oracle.REG)
    ids = tuple(oracle.REG[n] for n in names) + (x.UC_X86_REG_EFLAGS,)
    for pair in range(count):
        current, wanted = pair >> 8, pair & 255
        regs = {n: (pair * (17+2*k) + 0x1357+k*113) & 65535 for k,n in enumerate(names)}
        regs.update(cs=load, ip=ENTRIES[entry], ss=0x7000, sp=0x8000,
            ax=((wanted if entry == 4 else (pair*37+91)&255) << 8) | current,
            bx=(((pair*19+73)&255) << 8) | wanted)
        flags = 2 | ((pair * 0x95 ^ 0xad5) & 0xed5)
        expected, mask = mathematical(regs, flags, entry)
        machine.reg_write_batch(tuple(zip(ids, [regs[n] for n in names]+[flags])))
        stopped[0] = False
        machine.emu_start((load << 4)+ENTRIES[entry], 0, count=128)
        if failed or not stopped[0]: fail(f'Matrix entry{entry}/{pair:04x} original access/control guard: {failed}')
        got = dict(zip((*names, 'flags'), machine.reg_read_batch(ids)))
        if any(got[n] != expected[n] for n in names) or (got['flags'] ^ expected['flags']) & mask:
            fail(f'Matrix entry{entry}/{pair:04x}: original disagrees with channel mathematics: {got}/{expected}')
        if native:
            state = video.to_state(dict(regs, flags=flags))
            out = native.core(mem_buffer, load, ctypes.byref(state), entry, None)
            values = dict(video.state_dict(out.state), cs=out.code_segment, ip=out.continuation)
            common.require(out.status == 0, 'Matrix native status differs')
            common.require(all(values[n] == got[n] for n in names) and not ((values['flags'] ^ got['flags']) & mask), f'Matrix native entry{entry}/{pair:04x} differs')
    if bytes(machine.mem_read(0, 1 << 20)) != bytes(memory): fail('Original matrix touched unexpected RAM')
    if native: common.require(native_memory == memory, 'Native matrix final whole RAM differs')
    if before != input_hashes(native is not None): fail('Matrix verification inputs changed')
    write_json(Path(directory)/f'matrix-{entry}.json', dict(entry=ENTRIES[entry], byte_pairs=count,
        complete_byte_pair_matrix=count == 65536, boundary='before outer near RET',
        original_instruction_budget_per_pair=128, final_whole_ram_equal=True, input_hashes=before))
    print(f'PASS palette matrix {ENTRIES[entry]:04X}: {count} byte pairs, original/math'+('/C' if native else ''), flush=True)


def cases():
    rows = []
    for entry in range(5):
        for a,b in ((0,0),(1,0),(0,1),(9,8),(8,9),(0x7f,0x80),(0x80,0x7f),(0xff,0),(0,0xff),(0x1f,0x21),(0xf0,0xee)):
            rows.append(dict(name=f'e{entry}-{a:02x}-{b:02x}', entry=entry,a=a,b=b))
        for sp in (0,1,0xfffe,0xffff): rows.append(dict(name=f'e{entry}-sp{sp:04x}',entry=entry,a=9,b=0x21,sp=sp))
        rows.append(dict(name=f'e{entry}-A20', entry=entry,a=0x80,b=0x7f,ss=0xffff,sp=0xf))
        rows.append(dict(name=f'e{entry}-VGA', entry=entry,a=0x7f,b=0x80,ss=0xa000,vga=True))
    rows.append(dict(name='target-BH-clobber',entry=3,a=0,b=1,bh=0))
    # A stack provider changes only the child's near-return low byte.
    for entry in (0,1):
        rows.append(dict(name=f'e{entry}-changed-child',entry=entry,a=9,b=8,ss=0xa000,vga=True,change_child=True))
    for seed, case in enumerate(rows): case['seed'] = seed
    return rows


def prepare(case):
    rng = random.Random(0x569b+case['seed'])
    load = (0x1010,0x1213,0x2345)[case['seed']%3]
    memory = bytearray(rng.randbytes(1 << 20))
    loaded = relocated(IMAGE,ORACLE['relocations'],load)
    memory[load << 4:(load << 4)+len(loaded)] = loaded
    regs = {n:rng.randrange(65536) for n in oracle.REG_NAMES}
    regs.update(cs=load,ip=ENTRIES[case['entry']],ds=0x3000,es=0x6000,
        ss=case.get('ss',0x7000),sp=case.get('sp',0x8000),
        ax=((case['b'] if case['entry']==4 else rng.randrange(256)) << 8) | case['a'],
        bx=(case.get('bh',rng.randrange(256)) << 8) | case['b'],bp=0x5aa5)
    flags = 2 | ((case['seed']*0x95 ^ 0xad5) & 0xed5)
    video.putword(memory,regs['ss'],regs['sp'],0xeed1)
    return memory,regs,flags


def device_for(memory,case,regs,native=False):
    device = common.TraceDevice(bytearray(memory),0x569b+case['seed'])
    if case.get('change_child'):
        target = video.physical(regs['ss'],(regs['sp']-2)&65535)
        # Same byte-store provider for Unicorn and native: canonical frame byte
        # becomes01 instead of7C/91. The CPU's subsequent RET reads it live.
        original_write = device.vga.write
        def write(mem,p,value,flags):
            original_write(mem,p,value,flags)
            if p == target:
                mem[p] = 1
                for plane in device.vga.planes: plane[p-0xa0000] = 1
        device.vga.write = write
    return device


def compare(native,case,core):
    memory,regs,flags = prepare(case)
    original = device_for(memory,case,regs)
    # Stop at all outer RET sites while letting wrapper child56E1 RET execute.
    ret_set = RETURNS[case['entry']]
    result = caller.original(case,original,regs,flags,instructions=INS,far_calls=set(),
        continuations=ret_set if core else (),max_steps=128,defined_mask_after=mask_after)
    actual,mask,sites,edges,boundary,_child,_body = result
    if case.get('change_child'):
        expected_ip = 0x5601
        if boundary != ('changed-child-near',regs['cs'],expected_ip): fail(case['name']+': changed frame was not exercised '+str(boundary))
    else:
        expected,expected_mask = mathematical(regs,flags,case['entry'])
        expected['sp'] = regs['sp'] if core else (regs['sp']+2)&65535
        if not core: expected['ip'] = oracle.get16(original.memory,regs['ss'],regs['sp'])
        for n in oracle.REG_NAMES:
            if actual[n] != expected[n]: fail(case['name']+': original/math '+n+' differs')
        if (actual['flags'] ^ expected['flags']) & expected_mask: fail('Boundary original/math flags differ')
    if native:
        for null in ((False,) if case.get('vga') or case.get('change_child') else (False,True)):
            device = device_for(memory,case,regs,True)
            bus = None if null else ctypes.byref(device.bus)
            if core:
                out = native.core(video.buffer(device.memory),regs['cs'],ctypes.byref(video.to_state(dict(regs,flags=flags))),case['entry'],bus)
                got = dict(video.state_dict(out.state),cs=out.code_segment,ip=out.continuation)
                common.require(out.status == int(bool(case.get('change_child'))),case['name']+': status differs')
            else:
                r = video.Regs(**regs,flags=flags)
                native.adapter(video.buffer(device.memory),ctypes.byref(r),case['entry'],bus)
                got = {n:getattr(r,n) for n in (*oracle.REG_NAMES,'flags')}
            common.require(all(got[n] == actual[n] for n in oracle.REG_NAMES) and not ((got['flags'] ^ actual['flags']) & mask),case['name']+': native state differs')
            common.require(device.memory == original.memory,case['name']+': full RAM differs')
            common.require(device.vga.state() == original.vga.state(),case['name']+': VGA differs')
            if not null: common.compare_event_traces(device.events,original.events,case['name'])
    return dict(name=case['name'],core=core,sites=sorted(sites),edges=sorted(edges),boundary=boundary)


def boundary_worker(directory,native_directory=None):
    common.MAX_BUS_EVENTS = 256
    common.MAX_VGA_EVENTS = 128
    identity()
    before=input_hashes(native_directory is not None)
    native=Native(native_directory) if native_directory is not None else None
    rows=[]
    for case in cases():
        for core in (False,True):rows.append(compare(native,case,core))
        gc.collect()
    sites={p for r in rows for p in r['sites']};edges={tuple(e) for r in rows for e in r['edges']}
    if sites != set(INS) or edges != EDGES: fail(f'Channel site/edge coverage incomplete: {set(INS)-sites}/{EDGES-edges}')
    mutations=[]
    if native:
        for mutation,name in ((1,'e4-7f-80'),(2,'e4-1f-21'),(3,'e3-00-00'),(4,'target-BH-clobber'),(5,'e0-00-ff'),(6,'e0-changed-child')):
            lib=Native(native_directory,mutation,compile=True)
            case=next(c for c in cases() if c['name']==name)
            try:compare(lib,case,True)
            except common.Mismatch as error:mutations.append(dict(mutation=mutation,case=name,reason=str(error)))
            else:fail(f'PALETTE_CHANNELS_MUTATION={mutation} survived')
            gc.collect()
    if before!=input_hashes(native is not None):fail('Channel boundary inputs changed')
    write_json(Path(directory)/'boundaries.json',dict(case_count=len(cases()),cases=rows,
        sites=sorted(sites),edges=sorted(edges),mutations=mutations,input_hashes=before))
    print(f'PASS palette channel boundaries: {len(cases())} fixtures x2,69 sites,{len(edges)} edges,{len(mutations)} mutants',flush=True)


def run(original=False):
    report=ORIGINAL_REPORT if original else REPORT
    report.unlink(missing_ok=True)
    before=input_hashes(not original)
    deadline=time.monotonic()+330
    def launch(arguments):
        remaining=deadline-time.monotonic()-5
        if remaining<=0:fail('Channel campaign deadline exhausted')
        run_bounded([sys.executable,str(Path(__file__).resolve()),*arguments],cwd=ROOT,
                    timeout=min(120,remaining),memory_mib=384)
    try:
        with temporary_build_directory(prefix='palette-channels-',parent=BUILD) as directory:
            if not original:build(Path(directory)/'palette-channels-m0.dll',0,'palette_channels')
            native_args=[] if original else [directory]
            for entry in range(5):
                launch(['--matrix-worker',str(entry),directory,*native_args])
            launch(['--boundary-worker',directory,*native_args])
            matrices=[read_json(Path(directory)/f'matrix-{e}.json') for e in range(5)]
            boundaries=read_json(Path(directory)/'boundaries.json')
        if before!=input_hashes(not original):fail('Channel campaign inputs changed')
        if any(m['byte_pairs']!=65536 or m['input_hashes']!=before for m in matrices) or boundaries['input_hashes']!=before:fail('Channel campaign incomplete/stale')
        write_json(report,dict(image='main',image_sha256=sha(IMAGE),case_count=5*65536+len(cases()),
            exhaustive_byte_pairs_each_entry=65536,matrix_entry_count=5,matrices=matrices,
            boundary_fixture_count=len(cases()),boundaries_each_fixture=2,boundary_cases=boundaries['cases'],
            translated_code_bytes=0 if original else 144,native_code_ranges=[] if original else [[0x566c,0x56e2],[0x570c,0x5726]],
            caller_instruction_addresses=sorted(INS),executed_instruction_addresses=boundaries['sites'],
            branch_edges=boundaries['edges'],mutation_count=len(boundaries['mutations']),mutations_detected=boundaries['mutations'],
            input_hashes=before,c_coverage_claimed=not original,
            limits=dict(campaign_seconds=330,each_worker_seconds=120,windows_process_mib=384,windows_tree_mib=640,instructions_per_call=128,boundary_bus_events=256),
            domain='All byte pairs at five core entries, mathematical channel/flag model, reused fixed machine with guarded frame-only data accesses and final matrix RAM check; separate fullRAM/allCPU/phaseflags/orderedbus/VGA/actualnearreturn fixtures at core and adapter, including live changed wrapper returns. Intact decoded code, quiescent IRQs, permissive20bit word bus; no device timing or hardware segment-limit claim.'))
        print(f'PASS palette channels {"original" if original else "C"}: 327680 byte pairs + {len(cases())} x2 boundary fixtures,144 bytes/69 sites,{len(boundaries["mutations"])} mutants',flush=True)
    except BaseException:
        report.unlink(missing_ok=True);raise


if __name__ == '__main__':
    args=sys.argv[1:]
    if args and args[0]=='--matrix-worker' and len(args) in (3,4):matrix_worker(int(args[1]),args[2],args[3] if len(args)==4 else None)
    elif args and args[0]=='--boundary-worker' and len(args) in (2,3):boundary_worker(args[1],args[2] if len(args)==3 else None)
    elif args==['--original-only']:run(True)
    elif not args:run()
    else:raise SystemExit('Unexpected palette channel arguments')

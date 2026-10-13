"""Bounded Unicorn differential coverage for CS:8343 and CS:8363."""
import ctypes
import hashlib
import json
import random
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_16, CS_GRP_JUMP
import unicorn
from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE
from unicorn.x86_const import *

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "build" / "differential.json"
REPORT_PATH.unlink(missing_ok=True)
sys.path.insert(0, str(ROOT / "tools"))
from cbuild import build
from unpack import ASSET, unpack, relocated

with (ROOT / "metadata" / "symbols.json").open(encoding="utf-8") as f:
    SYMBOL_ROWS = {row["symbol_name"]: row for row in json.load(f)}
SYMBOLS = {name: row["address"] for name, row in SYMBOL_ROWS.items()}
WINDOW_SIZE = SYMBOL_ROWS["ChecksumWindow"]["size"]
PACKED = ASSET.read_bytes()
UNPACKED, ORACLE = unpack(PACKED)
CS = 0x1010
IMAGE = relocated(UNPACKED, ORACLE["relocations"], CS)
LOAD = CS << 4
MEM_SIZE = 1 << 20
STOP_IP = 0xFF00
FLAGS_MASK = 0x0FD7
AF = 0x0010
REG_MAP = {
    "ax": UC_X86_REG_AX, "bx": UC_X86_REG_BX, "cx": UC_X86_REG_CX,
    "dx": UC_X86_REG_DX, "si": UC_X86_REG_SI, "di": UC_X86_REG_DI,
    "bp": UC_X86_REG_BP, "sp": UC_X86_REG_SP, "cs": UC_X86_REG_CS,
    "ds": UC_X86_REG_DS, "es": UC_X86_REG_ES, "ss": UC_X86_REG_SS,
    "ip": UC_X86_REG_IP,
}
DISASM = Cs(CS_ARCH_X86, CS_MODE_16)
DISASM.detail = True
ORIGINAL_INSNS = {}
BRANCH_ADDRS = set()
for lo, hi in ((SYMBOLS["InitializeCodeChecksum"], SYMBOLS["AdvanceCodeChecksum"]),
               (SYMBOLS["AdvanceCodeChecksum"], SYMBOLS["ChecksumLimit"])):
    for insn in DISASM.disasm(IMAGE[lo:hi], lo):
        ORIGINAL_INSNS[insn.address] = insn
        if CS_GRP_JUMP in insn.groups or insn.mnemonic.startswith("loop"):
            BRANCH_ADDRS.add(insn.address)
EXPECTED_BRANCH_EDGES = set()
for address in BRANCH_ADDRS:
    insn = ORIGINAL_INSNS[address]
    target = insn.operands[0].imm & 0xffff
    EXPECTED_BRANCH_EDGES.add((address, target))
    if insn.mnemonic != "jmp":
        EXPECTED_BRANCH_EDGES.add((address, address + insn.size))

class CRegs(ctypes.Structure):
    _fields_ = [(n, ctypes.c_uint16) for n in
                ("ax", "bx", "cx", "dx", "si", "di", "bp", "sp",
                 "cs", "ds", "es", "ss", "ip", "flags")]

def load_library(path):
    lib = ctypes.CDLL(str(path))
    for name in ("lmn_initialize_code_checksum_adapter", "lmn_advance_code_checksum_adapter"):
        f = getattr(lib, name)
        f.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(CRegs)]
        f.restype = None
    return lib

def make_memory(tag, kind, state=None):
    rng = random.Random(tag)
    mem = bytearray(rng.randbytes(MEM_SIZE))
    mem[LOAD:LOAD + len(IMAGE)] = IMAGE
    if kind == "init" and tag != 1:
        start = SYMBOLS["ChecksumWindow"]
        mem[LOAD + start:LOAD + start + WINDOW_SIZE] = bytes(
            (tag * 17 + i * 29) & 0xff for i in range(WINDOW_SIZE))
    return mem

def make_regs(poison_seed):
    rng = random.Random(0xC5A0 + poison_seed)
    r = CRegs()
    r.ax, r.bx, r.cx, r.dx = [rng.randrange(0x10000) for _ in range(4)]
    r.si, r.di, r.bp = [rng.randrange(0x10000) for _ in range(3)]
    r.sp = 0x7F00
    r.cs = CS
    r.ds = rng.choice([0x5678, 0x4321, 0x0FED])
    r.es = rng.randrange(0x10000)
    r.ss = rng.randrange(0xD000, 0xF000)
    r.ip = 0
    # Keep TF clear to avoid single-step behavior; vary the other flags.
    r.flags = (rng.getrandbits(16) & 0x0ED7) | 0x0002
    return r

def put16(mem, off, value):
    mem[LOAD + off] = value & 0xff
    mem[LOAD + off + 1] = value >> 8

def prepare_case(kind, patch, tag):
    mem = make_memory(tag, kind, patch)
    r = make_regs(tag)
    if kind != "init":
        phase, cursor, acc = patch
        mem[LOAD + SYMBOLS["ChecksumPhase"]] = phase
        mem[LOAD + SYMBOLS["ChecksumAccumulator"]] = acc
        put16(mem, SYMBOLS["ChecksumCursor"], cursor)
    stack = ((r.ss << 4) + r.sp) & 0xfffff
    mem[stack] = STOP_IP & 0xff
    mem[(stack + 1) & 0xfffff] = STOP_IP >> 8
    return mem, r

def run_native(lib, kind, mem, regs):
    buf = (ctypes.c_uint8 * MEM_SIZE).from_buffer(mem)
    fn = getattr(lib, "lmn_initialize_code_checksum_adapter" if kind == "init"
                 else "lmn_advance_code_checksum_adapter")
    fn(buf, ctypes.byref(regs))

def run_unicorn(kind, mem, regs):
    uc = Uc(UC_ARCH_X86, UC_MODE_16)
    uc.mem_map(0, MEM_SIZE)
    uc.mem_write(0, bytes(mem))
    for n, reg in REG_MAP.items():
        uc.reg_write(reg, getattr(regs, n))
    uc.reg_write(UC_X86_REG_EFLAGS, regs.flags)
    start = LOAD + (SYMBOLS["InitializeCodeChecksum"] if kind == "init"
                    else SYMBOLS["AdvanceCodeChecksum"])
    stop = (regs.cs << 4) + STOP_IP
    seen = set()
    order = []
    stopped = False
    count = 0
    def hook(machine, address, size, _user):
        nonlocal stopped, count
        count += 1
        if LOAD + SYMBOLS["InitializeCodeChecksum"] <= address < LOAD + SYMBOLS["ChecksumLimit"]:
            current = address - LOAD
            if order and order[-1] in BRANCH_ADDRS:
                seen.add((order[-1], current))
            order.append(current)
        if address == stop:
            stopped = True
            machine.emu_stop()
    uc.hook_add(UC_HOOK_CODE, hook)
    # The largest path runs 0x800 five-instruction loop iterations.
    budget = 20000
    uc.emu_start(start, 0, count=budget)
    if not stopped:
        raise AssertionError(f"Unicorn failed to reach RET stop within {budget} instructions (executed {count})")
    final_regs = {n: uc.reg_read(reg) & 0xffff for n, reg in REG_MAP.items()}
    final_regs["flags"] = uc.reg_read(UC_X86_REG_EFLAGS) & 0xffff
    final_mem = bytearray(uc.mem_read(0, MEM_SIZE))
    return final_mem, final_regs, seen, set(order)

def compare(lib, kind, case, check_memory=True):
    mem, regs = prepare_case(kind, case[1], case[2])
    c_mem = bytearray(mem)
    c_regs = CRegs.from_buffer_copy(bytes(regs))
    u_mem, u_regs, edges, instructions = run_unicorn(kind, mem, regs)
    run_native(lib, kind, c_mem, c_regs)
    c_values = {n: getattr(c_regs, n) for n in REG_MAP}
    c_values["flags"] = c_regs.flags
    for n in REG_MAP:
        if c_values[n] != u_regs[n]:
            raise AssertionError(f"{case[0]} {n}: C={c_values[n]:04x} Unicorn={u_regs[n]:04x}")
    flags_mask = FLAGS_MASK
    if kind == "advance" and case[1][0] == 0xff:
        flags_mask &= ~AF
    if (c_values["flags"] ^ u_regs["flags"]) & flags_mask:
        raise AssertionError(f"{case[0]} flags: C={c_values['flags']:04x} Unicorn={u_regs['flags']:04x}")
    if check_memory and c_mem != u_mem:
        different = [i for i, (a, b) in enumerate(zip(c_mem, u_mem)) if a != b]
        raise AssertionError(f"{case[0]} memory differs at {different[:8]}")
    return instructions, edges

CASES = [
    ("initialize-window", "init", None, 1),
    ("initialize-window-poison-b", "init", None, 8),
    ("initialize-window-poison-c", "init", None, 9),
    ("phase-wrap-reset", "advance", (0xFF, 0x7777, 0xA6), 2),
    ("advance-800-byte-chunk", "advance", (0x00, 0x2000, 0x5C), 3),
    ("cursor-at-limit", "advance", (0x00, SYMBOLS["ChecksumLimit"], 0x37), 4),
    ("cursor-before-limit", "advance", (0x10, SYMBOLS["ChecksumLimit"] - 1, 0x83), 5),
    ("cursor-after-limit", "advance", (0x21, SYMBOLS["ChecksumLimit"] + 1, 0xCD), 6),
    ("self-overlap-state-scan", "advance", (0x42, SYMBOLS["ChecksumPhase"] - 1, 0x91), 10),
    ("cursor-wrap-ffff", "advance", (0x7F, 0xFFFF, 0x24), 7),
    ("final-bx-7fff", "advance", (0x7F, 0x77FF, 0x4D), 11),
    ("final-bx-8000", "advance", (0x7F, 0x7800, 0x73), 12),
]

def main():
    main_lib = load_library(build())
    coverage = set()
    branch_edges = set()
    baseline = []
    for name, kind, state, seed in CASES:
        case_instructions, case_edges = compare(main_lib, kind, (name, state, seed))
        coverage |= case_instructions
        branch_edges |= case_edges
        baseline.append((name, kind, state, seed))
    translated = set(ORIGINAL_INSNS)
    missing = translated - coverage
    if missing:
        raise AssertionError("unexecuted translated instruction addresses: " +
                             ", ".join(f"{x:04x}" for x in sorted(missing)))
    if branch_edges != EXPECTED_BRANCH_EDGES:
        raise AssertionError(f"branch edges {sorted(branch_edges)} != {sorted(EXPECTED_BRANCH_EDGES)}")

    # Each mutant is separately compiled and executed against the same bounded oracle cases.
    mutation_hits = []
    for mutation in (1, 2, 3):
        mut_lib = load_library(build(ROOT / "build" / f"checksum-mut{mutation}.dll", mutation))
        detected = None
        for name, kind, state, seed in baseline:
            try:
                compare(mut_lib, kind, (name, state, seed))
            except AssertionError:
                detected = name
                break
        if detected is None:
            raise AssertionError(f"compiled mutation {mutation} was not detected")
        mutation_hits.append(f"M{mutation}:{detected}")

    report = {
        "schema": 1,
        "oracle": {"engine": f"Unicorn {unicorn.__version__}", "packed_sha256": hashlib.sha256(PACKED).hexdigest(),
                   "relocated_image_sha256": hashlib.sha256(IMAGE).hexdigest(),
                   "load_segment": f"{CS:04X}"},
        "routines": [
            {"start": f"{SYMBOLS['InitializeCodeChecksum']:04X}",
             "end_exclusive": f"{SYMBOLS['AdvanceCodeChecksum']:04X}",
             "translated_bytes": SYMBOLS['AdvanceCodeChecksum'] - SYMBOLS['InitializeCodeChecksum'],
             "translated_instruction_addresses": [f"{a:04X}" for a in sorted(ORIGINAL_INSNS)
                                                    if SYMBOLS["InitializeCodeChecksum"] <= a < SYMBOLS["AdvanceCodeChecksum"]],
             "executed_instruction_addresses": [f"{a:04X}" for a in sorted(coverage)
                                                   if SYMBOLS["InitializeCodeChecksum"] <= a < SYMBOLS["AdvanceCodeChecksum"]],
             "branch_edges": [[f"{a:04X}", f"{b:04X}"] for a, b in sorted(branch_edges)
                              if SYMBOLS["InitializeCodeChecksum"] <= a < SYMBOLS["AdvanceCodeChecksum"]]},
            {"start": f"{SYMBOLS['AdvanceCodeChecksum']:04X}",
             "end_exclusive": f"{SYMBOLS['ChecksumLimit']:04X}",
             "translated_bytes": SYMBOLS['ChecksumLimit'] - SYMBOLS['AdvanceCodeChecksum'],
             "translated_instruction_addresses": [f"{a:04X}" for a in sorted(ORIGINAL_INSNS)
                                                    if SYMBOLS["AdvanceCodeChecksum"] <= a < SYMBOLS["ChecksumLimit"]],
             "executed_instruction_addresses": [f"{a:04X}" for a in sorted(coverage)
                                                   if SYMBOLS["AdvanceCodeChecksum"] <= a < SYMBOLS["ChecksumLimit"]],
             "branch_edges": [[f"{a:04X}", f"{b:04X}"] for a, b in sorted(branch_edges)
                              if SYMBOLS["AdvanceCodeChecksum"] <= a < SYMBOLS["ChecksumLimit"]],
             "reachability": "unresolved"}],
        "case_count": len(CASES), "mutation_count": len(mutation_hits),
        "cases": [{"name": name, "routine": kind, "poison_seed": seed}
                  for name, kind, _state, seed in CASES],
        "mutations_detected": mutation_hits,
        "flags_note": "AF is ignored only on phase-wrap path ending XOR AH,AH; all other cases compare AF.",
        "input_hashes": {
            "checksum.c": hashlib.sha256((ROOT / "c" / "checksum.c").read_bytes()).hexdigest(),
            "checksum.h": hashlib.sha256((ROOT / "c" / "checksum.h").read_bytes()).hexdigest(),
            "lemmings_sym.h": hashlib.sha256((ROOT / "c" / "lemmings_sym.h").read_bytes()).hexdigest(),
            "symbols.json": hashlib.sha256((ROOT / "metadata" / "symbols.json").read_bytes()).hexdigest(),
            "checksum.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "difftest.py": hashlib.sha256((ROOT / "tools" / "difftest.py").read_bytes()).hexdigest(),
            "cbuild.py": hashlib.sha256((ROOT / "tools" / "cbuild.py").read_bytes()).hexdigest(),
        },
        "stack_fixture": "Near-call return word at SS:SP; saved DS/CS pushes do not alias checksum state or scanned bytes.",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"PASS: {len(CASES)} differential cases; instruction addresses covered {len(coverage)}/{len(translated)}")
    print("Cases: " + ", ".join(row[0] for row in CASES))
    print("Mutation checks: " + ", ".join(mutation_hits))
    print("AF ignored: architecturally undefined after XOR/AND; all other modeled flags compared.")
    print(f"Machine-readable report: {REPORT_PATH}")

if __name__ == "__main__":
    main()

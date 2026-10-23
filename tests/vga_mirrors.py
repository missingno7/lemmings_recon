"""Bounded original-versus-native checks for VGA mirror initialization/restore."""
from __future__ import annotations

import copy
import ctypes as ct
import gc
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests")]

import capstone
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from minimap_vga import MinimapVga, VGA_BASE, VGA_END
from unpack import ASSET, relocated, unpack
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_INSN)
from unicorn import x86_const as uc_x86

IMAGE, ORACLE = unpack(ASSET.read_bytes())
SIZE, MASK, FLAGS = 1 << 20, (1 << 20) - 1, 0x0FD7
LOGIC, IF, DF = FLAGS & ~0x10, 0x0200, 0x0400
ARITH_LOGIC = 0x08C5
LOADS = (0x1010, 0x1213, 0x2345)
RESTORE, RESTORE_RET, RESTORE_END = 0x587F, 0x58D1, 0x58D2
INIT, INIT_RET, INIT_END = 0x04F9, 0x054D, 0x054E
MAX_STEPS, MAX_EVENTS = 128, 256
WORKER_SECONDS, MEMORY_MIB = 420, 384
READY = 0
REPORT = BUILD / "vga-mirrors-differential.json"
ORIGINAL_REPORT = BUILD / "vga-mirrors-original-differential.json"
CALL_FIELDS = ("ax", "bx", "cx", "dx", "si", "di", "bp", "code_segment",
               "data_segment", "extra_segment", "stack_segment", "stack_offset",
               "flags")
RESULT_FIELDS = CALL_FIELDS + ("continuation", "status")
CALL_REGS = ("ax", "bx", "cx", "dx", "si", "di", "bp", "cs", "ds", "es",
             "ss", "sp", "flags")
REG_NAMES = ("ax", "bx", "cx", "dx", "si", "di", "bp", "sp", "cs",
             "ds", "es", "ss", "ip", "flags")
REG_IDS = {name: getattr(uc_x86, "UC_X86_REG_" + name.upper())
           for name in REG_NAMES if name != "flags"}
REG_IDS["flags"] = uc_x86.UC_X86_REG_EFLAGS
MEM = ct.POINTER(ct.c_uint8)


class Regs(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in REG_NAMES]

MD = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_16)
MD.detail = True
RESTORE_INS = {ins.address: ins for ins in MD.disasm(
    IMAGE[RESTORE:RESTORE_END], RESTORE)}
INIT_INS = {ins.address: ins for ins in MD.disasm(IMAGE[INIT:INIT_END], INIT)}
OWN_INS = {"restore": RESTORE_INS, "initialize": INIT_INS}
OWN_SITES = {name: set(instructions) for name, instructions in OWN_INS.items()}
if len(RESTORE_INS) != 38 or len(INIT_INS) != 25:
    raise AssertionError("pinned VGA mirror instruction layout changed")

MIRROR_OFFSETS = (0x08, 0x00, 0x02, 0x04, 0x06, 0x0A, 0x0C, 0x0E, 0x10)
PORT_INDEX = (0x02, 0x05, 0x03, 0x02, 0x07, 0x00, 0x01, 0x08, 0x04)
PORT_NUMBERS = (0x03C4,) + (0x03CE,) * 8
INIT_STORES = ((0x08, 0x0002), (0x0A, 0x0000), (0x0C, 0x0001),
               (0x04, 0x0002), (0x02, 0x0003), (0x10, 0x0004),
               (0x00, 0x0005), (0x06, 0x0F07), (0x10, 0xFF08))
REGISTER_TO_STATE = dict(code_segment="cs", data_segment="ds",
                         extra_segment="es", stack_segment="ss",
                         stack_offset="sp")


class Call(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in CALL_FIELDS]


class Result(ct.Structure):
    _fields_ = [(name, ct.c_uint16) for name in RESULT_FIELDS]


READ = ct.CFUNCTYPE(ct.c_uint8, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint16)
WRITE = ct.CFUNCTYPE(None, ct.c_void_p, MEM, ct.c_uint32, ct.c_uint8,
                     ct.c_uint16)
OUT = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_uint16, ct.c_uint16, ct.c_uint16)


class Bus(ct.Structure):
    _fields_ = [("context", ct.c_void_p), ("read_byte", READ),
                ("write_byte", WRITE), ("out_word", OUT)]


class OracleFailure(AssertionError):
    pass


class Mismatch(AssertionError):
    pass


def check(condition, message):
    if not condition:
        raise OracleFailure(message)


def require(condition, message):
    if not condition:
        raise Mismatch(message)


def physical(segment, offset):
    return (((segment & 0xFFFF) << 4) + (offset & 0xFFFF)) & MASK


def get16(memory, segment, offset):
    at = physical(segment, offset)
    return memory[at] | (memory[(at + 1) & MASK] << 8)


def put8(memory, segment, offset, value):
    memory[physical(segment, offset)] = value & 0xFF


def sync_memory_byte(memory, device, segment, offset, value):
    at = physical(segment, offset)
    value &= 0xFF
    memory[at] = value
    if device is not None and VGA_BASE <= at < VGA_END:
        index = at - VGA_BASE
        for plane in device.planes:
            plane[index] = value


def put16(memory, segment, offset, value, device=None):
    at = physical(segment, offset)
    for delta, byte in enumerate((value & 0xFF, (value >> 8) & 0xFF)):
        address = (at + delta) & MASK
        memory[address] = byte
        if device is not None and VGA_BASE <= address < VGA_END:
            for plane in device.planes:
                plane[address - VGA_BASE] = byte


def add8_flags(flags, left, right):
    left &= 0xFF
    right &= 0xFF
    total = left + right
    result = total & 0xFF
    arithmetic = 0
    if total > 0xFF:
        arithmetic |= 0x0001
    if ((left & 0x0F) + (right & 0x0F)) > 0x0F:
        arithmetic |= 0x0010
    if result == 0:
        arithmetic |= 0x0040
    if result.bit_count() % 2 == 0:
        arithmetic |= 0x0004
    if result & 0x80:
        arithmetic |= 0x0080
    if (~(left ^ right) & (left ^ result) & 0x80):
        arithmetic |= 0x0800
    return ((flags & ~0x08D5) | arithmetic) & 0xFFFF


def loaded_image(load):
    return relocated(IMAGE, ORACLE["relocations"], load)


def code_image(memory, load):
    image = loaded_image(load)
    base = (load << 4) & MASK
    first = min(len(image), SIZE - base)
    memory[base:base + first] = image[:first]
    if first < len(image):
        memory[:len(image) - first] = image[first:]
    return image


def fixed_segment(load):
    return (0x143E + load) & 0xFFFF


def default_regs(load, seed, *, ss=0x5000, sp=0x9000, ds=0x3000,
                 es=0x6400, flags=0x0AD7):
    rng = random.Random(seed)
    return dict(ax=rng.randrange(0x10000), bx=rng.randrange(0x10000),
                cx=0x3A71 ^ seed, dx=0x91C2 ^ seed,
                si=rng.randrange(0x10000), di=rng.randrange(0x10000),
                bp=rng.randrange(0x10000), cs=load, ds=ds, es=es,
                ss=ss, sp=sp, ip=0, flags=flags & 0xFFFF)


def new_device(seed):
    device = MinimapVga(seed, read_map=0)
    device.seq[2] = 0x0F
    device.gc[0] = 0
    device.gc[1] = 0
    device.gc[3] = 0
    device.gc[5] = 0
    device.gc[8] = 0xFF
    return device


def seed_mirrors(memory, device, segment, seed):
    for index, offset in enumerate((0x00, 0x02, 0x04, 0x06, 0x08,
                                    0x0A, 0x0C, 0x0E, 0x10)):
        # Distinct high and low bytes expose ordering, AL replacement and XOR.
        low = (0x31 + 7 * index + seed) & 0xFF
        high = (0x42 + 19 * index + (seed >> 1)) & 0xFF
        if offset == 0x0A:
            low = 0x06
        put16(memory, segment, offset, (high << 8) | low, device)


def initial_memory(case):
    rng = random.Random(case.get("seed", 0x587F))
    memory = bytearray(rng.randbytes(SIZE))
    load = case.get("load", LOADS[0])
    code_image(memory, load)
    device = new_device(case.get("seed", 0x587F) ^ 0xA5A5)
    return memory, device


def fixture_case(name, *, entry, load=LOADS[0], seed=0x587F, **options):
    row = dict(name=name, entry=entry, load=load, seed=seed)
    row.update(options)
    return row


def cases():
    rows = []
    for index, load in enumerate(LOADS):
        rows.append(fixture_case(f"restore-load-{load:04x}", entry="restore",
                                 load=load, seed=0x587F + index * 0x111))
    rows += [
        fixture_case("restore-live-ss-distinct-fixed-frame", entry="restore",
                     seed=0x5881, ss=0x3512, sp=0x9000, fixed_seed=0xD1),
        fixture_case("restore-if-clear-df-set", entry="restore", seed=0x5882,
                     flags=0x04D7),
        fixture_case("restore-if-set-df-clear", entry="restore", seed=0x5883,
                     flags=0x02D7),
        fixture_case("restore-live-pop-cx-provider", entry="restore",
                     seed=0x5884, provider="replace-saved-cx",
                     provider_word=0xBEEF),
        fixture_case("restore-live-operand-provider", entry="restore",
                     seed=0x5885, provider="replace-code-operand",
                     operand_segment=0x2A31),
        fixture_case("restore-stack-code-operand-alias", entry="restore",
                     seed=0x5886, ss=LOADS[0], sp=0x5886,
                     cx=0x2A31, core_only=True,
                     allowed_operand_write=True),
        fixture_case("restore-fixed-frame-stack-mirror-alias",
                     entry="restore", seed=0x5886, ss_fixed=True, sp=0x000A),
        fixture_case("restore-live-outer-ret-provider", entry="restore",
                     seed=0x5887, provider="replace-outer-ret",
                     provider_word=0x1234),
        fixture_case("restore-sp-zero", entry="restore", seed=0x5888,
                     sp=0x0000),
        fixture_case("restore-sp-ffff", entry="restore", seed=0x5889,
                     sp=0xFFFF),
        fixture_case("restore-stack-physical-fffff", entry="restore",
                     seed=0x5890, ss=0xFFFF, sp=0x0011),
        fixture_case("restore-fixed-segment-ffff-a20", entry="restore",
                     load=0xEBC1, seed=0x5891),
        fixture_case("restore-fixed-frame-vga", entry="restore",
                     load=0x8BC2, seed=0x5892),
        fixture_case("restore-vga-stack", entry="restore", seed=0x5893,
                     ss=0xA000, sp=0x8000),
        fixture_case("restore-ds-vga-is-preserved", entry="restore",
                     seed=0x5894, ds=0xA000),
        fixture_case("restore-xor-al-index-zero", entry="restore",
                     seed=0x5895, mirror_seed=0x44),
    ]
    for index, load in enumerate(LOADS):
        rows.append(fixture_case(f"initialize-load-{load:04x}",
                                 entry="initialize", load=load,
                                 seed=0x04F9 + index * 0x101,
                                 bios_port=(0x03B4, 0x03C4, 0x03D4)[index]))
    rows += [
        fixture_case("initialize-dl-wrap-carry", entry="initialize",
                     seed=0x0500, bios_port=0x03FA),
        fixture_case("initialize-dl-signed-overflow", entry="initialize",
                     seed=0x0501, bios_port=0x127F),
        fixture_case("initialize-entry-es-overwritten", entry="initialize",
                     seed=0x0502, es=0xFFFF, bios_port=0x03C4),
        fixture_case("initialize-ds-vga-alias", entry="initialize",
                     seed=0x0503, ds=0x9E03, bios_port=0x03C4),
        fixture_case("initialize-ss-vga-alias", entry="initialize",
                     seed=0x0504, ss=0xA000, sp=0x8000,
                     bios_port=0x03C4),
        fixture_case("initialize-outer-ret-overwritten-by-mirror",
                     entry="initialize", seed=0x0505, sp=0x000A,
                     bios_port=0x03C4),
        fixture_case("initialize-sp-one-wrap", entry="initialize",
                     seed=0x0506, sp=0x0001, bios_port=0x03C4),
        fixture_case("initialize-stack-physical-fffff", entry="initialize",
                     seed=0x0507, ss=0xFFFF, sp=0x0011,
                     bios_port=0x03C4),
        fixture_case("initialize-if-df-entry", entry="initialize",
                     seed=0x0508, flags=0x04D7, bios_port=0x03C4),
    ]
    return rows


def differential_cases():
    # Unicorn cannot single-step the exact PUSH that writes its translated
    # code page. That alias receives a separately bounded native-only witness.
    return [case for case in cases()
            if case["name"] != "restore-stack-code-operand-alias"]


class Access:
    def __init__(self, case, memory, regs, device):
        self.case, self.memory, self.regs, self.device = case, memory, regs, device
        self.events = []
        self.providers = set()
        self.current_flags = regs["flags"]
        self.current_mask = FLAGS
        self.sync_uc = None

    def _sync(self, address, value):
        if self.sync_uc is not None:
            address &= MASK
            self.sync_uc(address, bytes((value & 0xFF,)))
            self.sync_uc(address + SIZE, bytes((value & 0xFF,)))

    def _provider_word(self, segment, offset, value, name):
        start = physical(segment, offset)
        for delta, byte in enumerate((value & 0xFF, (value >> 8) & 0xFF)):
            address = (start + delta) & MASK
            self.memory[address] = byte
            if self.device is not None and VGA_BASE <= address < VGA_END:
                for plane in self.device.planes:
                    plane[address - VGA_BASE] = byte
            self._sync(address, byte)
        self.providers.add(name)

    def _provider(self, kind, address, byte_index):
        provider = self.case.get("provider")
        if kind == "write" and provider == "replace-code-operand":
            push_address = physical(self.regs["ss"], (self.regs["sp"] - 2) & 0xFFFF)
            if address == push_address and "operand" not in self.providers:
                code_segment = self.case["operand_segment"]
                self._provider_word(self.regs["cs"], 0x5884,
                                    code_segment, "operand")
        if kind == "out" and provider in ("replace-saved-cx",
                                           "replace-outer-ret"):
            marker = "applied:" + provider
            if marker not in self.providers:
                if provider == "replace-saved-cx":
                    offset = (self.regs["sp"] - 2) & 0xFFFF
                    name = "saved-cx"
                else:
                    offset = self.regs["sp"]
                    name = "outer-ret"
                self._provider_word(self.regs["ss"], offset,
                                    self.case["provider_word"], name)
                self.providers.add(marker)

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        if len(self.events) >= MAX_EVENTS:
            raise OracleFailure("VGA mirror bus-event budget exhausted")
        address &= MASK
        if kind == "read":
            if self.device is not None and VGA_BASE <= address < VGA_END:
                value = self.device.read(self.memory, address, flags)
            else:
                value = self.memory[address]
        else:
            value &= 0xFF
            if self.device is not None and VGA_BASE <= address < VGA_END:
                self.device.write(self.memory, address, value, flags)
            else:
                self.memory[address] = value
        self.events.append((kind, address, value & 0xFF, flags & 0xFFFF, mask))
        self._provider(kind, address, 0)
        return value & 0xFF

    def out_word(self, port, value, flags, mask=FLAGS):
        if len(self.events) >= MAX_EVENTS:
            raise OracleFailure("VGA mirror bus-event budget exhausted")
        self.device.out(port, value, flags)
        self.events.append(("out", port & 0xFFFF, value & 0xFFFF,
                            flags & 0xFFFF, mask))
        self._provider("out", port, 0)


class Original:
    """One pinned 16-bit Unicorn memory machine with two bounded entry domains."""
    def __init__(self, memory, device):
        self.memory, self.device = memory, device
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, SIZE * 2)
        self.cpu.mem_write(0, bytes(memory))
        self.cpu.mem_write(SIZE, bytes(memory))
        self.current = None
        self.previous = None
        self.failure = None
        self.stopped = False
        self.steps = 0
        self.sites = set()
        self.events_start = 0
        self.code_hook = self.cpu.hook_add(UC_HOOK_CODE, self._code)
        self.cpu.hook_add(UC_HOOK_MEM_READ, self._read)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self._write)
        self.cpu.hook_add(UC_HOOK_INSN, self._out, None, 1, 0,
                          uc_x86.UC_X86_INS_OUT)

    def _fail(self, message):
        if self.failure is None:
            self.failure = message
        self.cpu.emu_stop()

    def _sync(self, address, data):
        self.cpu.mem_write(address, data)

    def _after_mask(self, ins, previous_mask):
        mnemonic = ins.mnemonic.lower()
        if mnemonic in ("add", "sub", "cmp", "neg"):
            return FLAGS
        if mnemonic in ("and", "or", "xor", "test"):
            return LOGIC
        if mnemonic in ("cli", "sti"):
            return previous_mask | IF
        return previous_mask

    def _code(self, cpu, _address, _size, _):
        current = self.current
        if self.previous is not None:
            previous_address, previous_ins = self.previous
            current["mask"] = self._after_mask(previous_ins, current["mask"])

        cs = cpu.reg_read(REG_IDS["cs"]) & 0xFFFF
        off = cpu.reg_read(REG_IDS["ip"]) & 0xFFFF
        if cs != current["load"] or off not in current["instructions"]:
            self._fail(f'{current["case"]["name"]}: escaped at {cs:04X}:{off:04X}')
            return
        if current["core"] and off == current["ret"]:
            self.stopped = True
            current["core_stop"] = True
            cpu.emu_stop()
            return
        ins = current["instructions"][off]
        expected = bytearray(current["loaded"][off:off + ins.size])
        override = current.get("operand_override")
        if current["kind"] == "restore" and off == 0x5883 and override is not None:
            expected[1:3] = int(override).to_bytes(2, "little")
        actual = bytes(cpu.mem_read(physical(cs, off), ins.size))
        if actual != bytes(expected):
            self._fail(f'{current["case"]["name"]}: code bytes at {off:04X} '
                       f'{actual.hex()}/{bytes(expected).hex()}')
            return
        flags = cpu.reg_read(REG_IDS["flags"]) & 0xFFFF
        current["flags"] = flags
        current["access"].current_flags = flags
        current["access"].current_mask = current["mask"]
        self.previous = off, ins
        current["sites"].add(off)
        current["trace"].append(off)
        current["steps"] += 1
        if current["steps"] > MAX_STEPS:
            self._fail("VGA mirror original instruction budget exhausted at "
                       + repr(current["trace"][-24:]))

    def _read(self, cpu, _kind, address, size, _value, _):
        current = self.current
        for delta in range(size):
            raw = address + delta
            p = raw & MASK
            value = current["access"].access(
                "read", p, current["flags"], current["mask"])
            # Keep both Unicorn aliases synchronized with the canonical bus byte.
            cpu.mem_write(p, bytes((value,)))
            cpu.mem_write(p + SIZE, bytes((value,)))

    def _write(self, cpu, _kind, address, size, value, _):
        current = self.current
        code_operand = {physical(current["load"], 0x5884),
                        physical(current["load"], 0x5885)}
        for delta in range(size):
            raw = address + delta
            p = raw & MASK
            operand_push = (current["kind"] == "restore" and
                            current["case"].get("allowed_operand_write") and
                            self.previous is not None and
                            self.previous[0] == 0x5880 and p in code_operand)
            if p in current["code_bytes"] and not (
                    operand_push):
                self._fail(f'{current["case"]["name"]}: undeclared code write at {p:05X}')
                return
            byte = (value >> (8 * delta)) & 0xFF
            current["access"].access("write", p, current["flags"],
                                     current["mask"], byte)
        # A declared provider may replace CS:5884 during PUSH. Resynchronize
        # after the whole word write so its exact operand bytes win.
        for delta in range(size):
            p = (address + delta) & MASK
            if (current["case"].get("allowed_operand_write") and
                    self.previous is not None and self.previous[0] == 0x5880 and
                    p in code_operand):
                # Unicorn will commit the CPU's own self-write after this hook.
                # A nested API write to the translated instruction page aborts
                # this one-instruction PUSH before it updates SP.
                continue
            byte = current["access"].memory[p]
            cpu.mem_write(p, bytes((byte,)))
            cpu.mem_write(p + SIZE, bytes((byte,)))

    def _out(self, cpu, port, size, value, _):
        current = self.current
        if size != 2:
            self._fail("VGA mirror oracle observed non-word OUT")
            return
        try:
            current["access"].out_word(port, value,
                                       current["flags"], current["mask"])
        except BaseException as error:
            self._fail(f"VGA mirror output provider failed: {error}")

    def run(self, case, kind, regs, access, *, core, operand_override=None):
        load = case["load"]
        loaded = loaded_image(load)
        self.previous = None
        self.failure = None
        self.stopped = False
        self.steps = 0
        instructions = OWN_INS[kind]
        ret = INIT_RET if kind == "initialize" else RESTORE_RET
        entry = INIT if kind == "initialize" else RESTORE
        code_bytes = set()
        for address, ins in instructions.items():
            code_bytes.update(physical(load, address + n)
                              for n in range(ins.size))
        current = dict(case=case, kind=kind, load=load, loaded=loaded,
                       instructions=instructions, ret=ret, entry=entry,
                       core=core, access=access, mask=FLAGS, flags=regs["flags"],
                       steps=0, sites=set(), trace=[], code_bytes=code_bytes,
                       operand_override=operand_override)
        self.current = current
        access.sync_uc = self._sync
        for name, register in REG_IDS.items():
            self.cpu.reg_write(register, regs[name] & 0xFFFF)
        self.cpu.reg_write(REG_IDS["cs"], load)
        self.cpu.reg_write(REG_IDS["ip"], entry)
        start = physical(load, entry)
        try:
            executed = 0
            while not self.stopped and executed <= MAX_STEPS:
                cs = self.cpu.reg_read(REG_IDS["cs"]) & 0xFFFF
                ip = self.cpu.reg_read(REG_IDS["ip"]) & 0xFFFF
                self.cpu.emu_start(physical(cs, ip), 0, count=1)
                executed += 1
                # The MOV immediate at 5883 is intentionally live after PUSH CX.
                # Clear Unicorn's translated block after each single instruction
                # so an operand alias is fetched from canonical RAM on the next step.
                self.cpu.ctl_remove_cache(0, SIZE * 2)
                if (self.previous is not None and
                        self.previous[1].mnemonic.lower() == "ret"):
                    current["ret_observed"] = True
                    self.stopped = True
        except UcError as error:
            raise OracleFailure(f'{case["name"]}: bounded Unicorn execution failed') from error
        check(self.stopped and self.failure is None,
              case["name"] + ": " + (self.failure or "did not reach boundary"))
        state = {name: self.cpu.reg_read(REG_IDS[name]) & 0xFFFF
                 for name in REG_NAMES}
        memory = bytearray(self.memory)
        # Bus hooks update the canonical bytearray; assert Unicorn's low image agrees.
        check(bytes(self.cpu.mem_read(0, SIZE)) == bytes(memory),
              case["name"] + ": Unicorn RAM differs from canonical bus RAM")
        return dict(memory=memory, regs=state, device=copy.deepcopy(self.device),
                    events=access.events, providers=set(access.providers),
                    status=READY, sites=set(current["sites"]),
                    steps=current["steps"], flag_mask=current["mask"],
                    continuation=state["ip"], core_stop=current.get("core_stop", False))


def make_setup(case, kind, *, core):
    memory, device = initial_memory(case)
    load = case["load"]
    regs = default_regs(load, case["seed"],
                        ss=(fixed_segment(load) if case.get("ss_fixed")
                            else case.get("ss", 0x5000)),
                        sp=case.get("sp", 0x9000),
                        ds=case.get("ds", 0x3000),
                        es=case.get("es", 0x6400),
                        flags=case.get("flags", 0x0AD7))
    for key in ("ax", "bx", "cx", "dx", "si", "di", "bp"):
        if key in case:
            regs[key] = case[key] & 0xFFFF
    regs["ip"] = INIT if kind == "initialize" else RESTORE
    regs["flags"] = (regs["flags"] & 0x7FD7) | 2
    if kind == "initialize":
        bios = case.get("bios_port", 0x03C4)
        put16(memory, 0x0040, 0x0063, bios, device)
    else:
        fixed = fixed_segment(load)
        seed_mirrors(memory, device, fixed,
                     case.get("mirror_seed", case.get("fixed_seed", case["seed"])))
        if case.get("name") == "restore-stack-code-operand-alias":
            seed_mirrors(memory, device, regs["cx"], case["seed"] ^ 0x5A)
        if case.get("provider") == "replace-code-operand":
            seed_mirrors(memory, device, case["operand_segment"], case["seed"] ^ 0x5A)
    if not core or not case.get("core_only"):
        put16(memory, regs["ss"], regs["sp"],
              case.get("outer_return", (0xD000 ^ case["seed"]) & 0xFFFF), device)
    if case.get("entry") == "initialize" and regs["ds"] == 0x9E03:
        # The DS words land in A0000..AFFFF and therefore share the VGA bus.
        for address in (physical(regs["ds"], 0x1FDA),
                        physical(regs["ds"], 0x1FDA) + 1,
                        physical(regs["ds"], 0x1FDC),
                        physical(regs["ds"], 0x1FDC) + 1):
            if VGA_BASE <= address < VGA_END:
                index = address - VGA_BASE
                for plane in device.planes:
                    plane[index] = memory[address]
    return memory, regs, device


def independent_restore_words(case, memory, regs, device):
    """Model the declared PUSH/provider effects, then each mirror read and OUT."""
    model_memory = bytearray(memory)
    model_device = copy.deepcopy(device)

    # PUSH CX is the only pre-read stack mutation. Preserve the VGA bus effect
    # when the live stack aliases the aperture.
    push_offset = (regs["sp"] - 2) & 0xFFFF
    push_address = physical(regs["ss"], push_offset)
    push_flags = regs["flags"] & ~IF
    for delta, byte in enumerate((regs["cx"] & 0xFF,
                                  (regs["cx"] >> 8) & 0xFF)):
        address = (push_address + delta) & MASK
        if VGA_BASE <= address < VGA_END:
            model_device.write(model_memory, address, byte, push_flags)
        else:
            model_memory[address] = byte

    # The test provider has one precise write contract: after PUSH it replaces
    # only the relocated segment immediate at CS:5884.
    if case.get("provider") == "replace-code-operand":
        operand_address = physical(regs["cs"], 0x5884)
        for delta, byte in enumerate(case["operand_segment"].to_bytes(2, "little")):
            address = (operand_address + delta) & MASK
            model_memory[address] = byte
            if VGA_BASE <= address < VGA_END:
                index = address - VGA_BASE
                for plane in model_device.planes:
                    plane[index] = byte

    segment = get16(model_memory, regs["cs"], 0x5884)
    words = []
    for index, offset in enumerate(MIRROR_OFFSETS):
        value_bytes = []
        for delta in (0, 1):
            address = (physical(segment, offset) + delta) & MASK
            if VGA_BASE <= address < VGA_END:
                value = model_device.read(model_memory, address, regs["flags"])
            else:
                value = model_memory[address]
            value_bytes.append(value)
        value = value_bytes[0] | (value_bytes[1] << 8)
        word = (value & 0xFF00) | PORT_INDEX[index]
        port = PORT_NUMBERS[index]
        words.append((port, word))
        model_device.out(port, word, regs["flags"])
    return segment, words, model_memory, model_device


def expected_init_writes(case, regs, memory):
    bios = get16(memory, 0x0040, 0x0063)
    adjusted = (bios & 0xFF00) | ((bios + 6) & 0xFF)
    words = [(regs["ds"], 0x1FDA, bios),
             (regs["ds"], 0x1FDC, adjusted)]
    words += [(regs["ss"], offset, value) for offset, value in INIT_STORES]
    return bios, adjusted, words


def byte_trace(kind, words, flags):
    rows = []
    for segment, offset, value, phase_flags in words:
        address = physical(segment, offset)
        for delta, byte in enumerate((value & 0xFF, (value >> 8) & 0xFF)):
            rows.append((kind, (address + delta) & MASK, byte,
                         phase_flags & 0xFFFF, FLAGS))
    return rows


def independent_init(case, initial_memory, regs, expected):
    if case["entry"] != "initialize":
        return
    bios = get16(initial_memory, 0x0040, 0x0063)
    adjusted = (bios & 0xFF00) | ((bios + 6) & 0xFF)
    out = expected["regs"]
    check(out["es"] == 0x0040,
          case["name"] + ": initializer did not replace entry ES with 0040")
    check(out["dx"] == adjusted,
          case["name"] + ": ADD DL,6 carried into DH or used word arithmetic")
    check(get16(expected["memory"], regs["ds"], 0x1FDA) == bios,
          case["name"] + ": BIOS base word was not stored to DS:1FDA")
    check(get16(expected["memory"], regs["ds"], 0x1FDC) == adjusted,
          case["name"] + ": byte-wrapped port+6 word differs")
    check(get16(expected["memory"], regs["ss"], 0x0010) ==
          0xFF08,
          case["name"] + ": final mirror store did not preserve the literal SS:0010 target")
    check(get16(expected["memory"], regs["ss"], 0x000E) ==
          get16(initial_memory, regs["ss"], 0x000E),
          case["name"] + ": initializer changed the intentionally untouched SS:000E")
    add_flags = add8_flags(regs["flags"], bios & 0xFF, 6)
    arithmetic_mask = 0x08D5
    check(((out["flags"] ^ add_flags) & arithmetic_mask) == 0,
          case["name"] + ": byte ADD DL,6 flag result differs")


def validate_original(case, kind, regs, initial_memory, result, *, core):
    name = case["name"]
    check(result["status"] == READY, name + ": original status is not READY")
    expected_ret = INIT_RET if kind == "initialize" else RESTORE_RET
    if core:
        check(result["regs"]["ip"] == expected_ret,
              name + ": core did not stop before the actual RET")
        check(result["regs"]["sp"] == regs["sp"],
              name + ": core changed SP")
    else:
        expected_ip = get16(result["memory"], regs["ss"], regs["sp"])
        check(result["regs"]["ip"] == expected_ip,
              name + ": adapter did not consume the current live near-RET word")
        check(result["regs"]["sp"] == ((regs["sp"] + 2) & 0xFFFF),
              name + ": adapter did not advance SP after actual RET")
    if kind == "restore":
        check(result["regs"]["es"] == regs["es"],
              name + ": restore did not restore entry ES before POP CX")
        check(result["regs"]["dx"] == 0x03CE,
              name + ": final port selector is not 03CE")
        check(result["regs"]["flags"] & IF,
              name + ": STI did not force IF on")
        check((result["regs"]["flags"] & DF) == (regs["flags"] & DF),
              name + ": restore changed DF")
        outputs = [(event[1], event[2]) for event in result["events"]
                   if event[0] == "out"]
        check(len(outputs) == 9 and
              [(port, word & 0xFF) for port, word in outputs] ==
              list(zip(PORT_NUMBERS, PORT_INDEX)),
              name + ": restore port/index sequence differs")
        first_out = next(event for event in result["events"] if event[0] == "out")
        check(not (first_out[3] & IF), name + ": restore OUT ran with IF set")
        zero_out = [event for event in result["events"]
                    if event[0] == "out"][5]
        check((zero_out[3] & ARITH_LOGIC) == 0x0044,
              name + ": XOR AL,AL flag phase at index-0 OUT differs")
    else:
        check(result["regs"]["ax"] == 0xFF08,
              name + ": initializer final AX differs")
        independent_init(case, initial_memory, regs, result)
        if not core and case.get("sp") == 0x000A:
            check(result["regs"]["ip"] == 0,
                  name + ": SS:000A overwrite did not control the live RET")
    return result


def compare_memory_and_regs(actual, expected, label):
    require(actual["status"] == expected["status"], label + ": status differs")
    require(bytes(actual["memory"]) == bytes(expected["memory"]),
            label + ": RAM differs")
    expected_mask = expected["flag_mask"]
    for name in REG_NAMES:
        mask = expected_mask if name == "flags" else 0xFFFF
        require(((actual["regs"][name] ^ expected["regs"][name]) & mask) == 0,
                f'{label}: {name} {actual["regs"][name]:04X}/'
                f'{expected["regs"][name]:04X} under {mask:04X}')
    require(actual["providers"] == expected["providers"],
            label + ": provider boundary differs")
    require(len(actual["events"]) == len(expected["events"]),
            label + ": event count differs")
    for index, (got, want) in enumerate(zip(actual["events"], expected["events"])):
        require(got[:3] == want[:3],
                f"{label}: event {index} {got[:3]!r}/{want[:3]!r}")
        require(((got[3] ^ want[3]) & want[4]) == 0,
                f"{label}: event {index} FLAGS differ under {want[4]:04X}")
    require(actual["device"].state() == expected["device"].state(),
            label + ": VGA state differs")
    require([(row[0], row[1], row[2]) for row in actual["device"].trace] ==
            [(row[0], row[1], row[2]) for row in expected["device"].trace],
            label + ": VGA read/write/OUT order differs")


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f"vga-mirrors-m{mutation}.dll",
                     mutation, "vga_mirrors")
        self.lib = ct.CDLL(str(path))
        self.restore_core = self.lib.lmn_restore_vga_register_mirrors_core
        self.restore_core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(Bus)]
        self.restore_core.restype = Result
        self.restore_adapter = self.lib.lmn_restore_vga_register_mirrors_adapter
        self.restore_adapter.argtypes = [MEM, ct.POINTER(Regs),
                                        ct.POINTER(Bus)]
        self.restore_adapter.restype = ct.c_uint16
        self.initialize_core = self.lib.lmn_initialize_vga_register_mirrors_core
        self.initialize_core.argtypes = [MEM, ct.POINTER(Call), ct.POINTER(Bus)]
        self.initialize_core.restype = Result
        self.initialize_adapter = self.lib.lmn_initialize_vga_register_mirrors_adapter
        self.initialize_adapter.argtypes = [MEM, ct.POINTER(Regs),
                                            ct.POINTER(Bus)]
        self.initialize_adapter.restype = ct.c_uint16

    def run(self, case, kind, memory, regs, device, *, core, ram=None):
        access = Access(case, memory, regs, device)

        def die(error):
            code = 86 if "budget" in str(error).lower() else 87
            try:
                os.write(2, (str(error) + "\n").encode(
                    "utf-8", errors="backslashreplace"))
            finally:
                os._exit(code)

        def read(_context, _memory, address, flags):
            try:
                return access.access("read", address, flags)
            except BaseException as error:
                die(error)

        def write(_context, _memory, address, value, flags):
            try:
                access.access("write", address, flags, value=value)
            except BaseException as error:
                die(error)

        def out(_context, port, value, flags):
            try:
                access.out_word(port, value, flags)
            except BaseException as error:
                die(error)

        callbacks = (READ(read), WRITE(write), OUT(out))
        bus = Bus(None, *callbacks)
        ram = ram if ram is not None else (ct.c_uint8 * SIZE).from_buffer(memory)
        state = Regs(**regs)
        if core:
            call = Call(*(regs[REGISTER_TO_STATE.get(role, role)]
                          for role in CALL_FIELDS))
            function = (self.initialize_core if kind == "initialize"
                        else self.restore_core)
            result = function(ram, ct.byref(call), ct.byref(bus))
            for role in CALL_FIELDS:
                target = REGISTER_TO_STATE.get(role, role)
                setattr(state, target, getattr(result, role))
            state.ip = result.continuation
            status = result.status
            flag_mask = FLAGS
            sites = OWN_SITES[kind]
            steps = len(sites) - 1
        else:
            function = (self.initialize_adapter if kind == "initialize"
                        else self.restore_adapter)
            status = function(ram, ct.byref(state), ct.byref(bus))
            flag_mask = FLAGS
            sites = OWN_SITES[kind]
            steps = len(sites)
        return dict(memory=bytearray(memory), regs={name: getattr(state, name)
                                         for name in REG_NAMES},
                    device=copy.deepcopy(device), events=access.events,
                    providers=set(access.providers), status=status,
                    flag_mask=flag_mask, sites=set(sites), steps=steps)


def original_single(case, kind, memory, regs, device, *, core):
    initial_memory = bytearray(memory)
    access = Access(case, memory, regs, device)
    runner = Original(memory, device)
    operand_override = None
    if case.get("provider") == "replace-code-operand":
        operand_override = case["operand_segment"]
    elif case.get("name") == "restore-stack-code-operand-alias":
        operand_override = regs["cx"]
    expected = runner.run(case, kind, regs, access, core=core,
                          operand_override=operand_override)
    return validate_original(case, kind, regs, initial_memory, expected,
                             core=core)


def independent_case_checks(case, kind, memory, regs, device, expected, *, core):
    if kind == "restore":
        outputs = [event[2] for event in expected["events"] if event[0] == "out"]
        segment, expected_words, _modeled_memory, _modeled_device = independent_restore_words(
            case, memory, regs, device)
        check([(event[1], event[2]) for event in expected["events"]
               if event[0] == "out"] == expected_words,
              case["name"] + ": OUT words do not match independently modeled mirrors")
        read_addresses = [event[1] for event in expected["events"]
                          if event[0] == "read"]
        mirror_addresses = []
        for offset in MIRROR_OFFSETS:
            at = physical(segment, offset)
            mirror_addresses.extend((at, (at + 1) & MASK))
        check(read_addresses[:18] == mirror_addresses,
              case["name"] + ": mirror reads are not in the declared nine-word order")
        if case.get("provider") == "replace-saved-cx":
            check(expected["regs"]["cx"] == case["provider_word"],
                  case["name"] + ": POP CX did not reread provider-updated SS word")
            check(expected["regs"]["es"] == regs["es"],
                  case["name"] + ": entry ES restoration preceded live POP CX")
        if case.get("provider") == "replace-outer-ret" and not core:
            check(expected["regs"]["ip"] == case["provider_word"],
                  case["name"] + ": RET did not reread provider-updated outer word")
        if case.get("name") == "restore-stack-code-operand-alias":
            operand = get16(expected["memory"], regs["cs"], 0x5884)
            check(operand == regs["cx"],
                  case["name"] + ": PUSH CX did not overwrite relocated operand")
            check(expected["regs"]["es"] == regs["es"],
                  case["name"] + ": ES did not restore entry value after operand alias")
        if case.get("provider") == "replace-code-operand":
            check(get16(expected["memory"], regs["cs"], 0x5884) ==
                  case["operand_segment"],
                  case["name"] + ": PUSH provider did not change exact MOV operand")
            check(expected["regs"]["es"] == regs["es"],
                  case["name"] + ": changed relocated segment leaked into entry ES")
    else:
        bios, adjusted, words = expected_init_writes(case, regs, memory)
        independent_init(case, memory, regs, expected)
        check(expected["regs"]["dx"] == adjusted,
              case["name"] + ": independently calculated byte port addition differs")
        reads = [event for event in expected["events"] if event[0] == "read"]
        bios_address = physical(0x0040, 0x0063)
        check([(event[1], event[2]) for event in reads[:2]] ==
              [(bios_address, bios & 0xFF),
               ((bios_address + 1) & MASK, (bios >> 8) & 0xFF)],
              case["name"] + ": BIOS word was not read from 0040:0063")
        writes = [event for event in expected["events"] if event[0] == "write"]
        expected_rows = []
        for index, (segment, offset, value) in enumerate(words):
            # ADD changes the defined arithmetic flags before DS:1FDC is written.
            phase_flags = regs["flags"] if index == 0 else expected["regs"]["flags"]
            expected_rows.extend(byte_trace("write",
                                             [(segment, offset, value, phase_flags)],
                                             phase_flags))
        actual_shape = [(event[0], event[1], event[2]) for event in writes]
        expected_shape = [(event[0], event[1], event[2]) for event in expected_rows]
        check(actual_shape == expected_shape,
              case["name"] + ": initializer ordered word-write trace differs")
        check(get16(expected["memory"], regs["ss"], 0x000E) ==
              get16(memory, regs["ss"], 0x000E),
              case["name"] + ": untouched SS:000E changed")
        check(get16(expected["memory"], regs["ss"], 0x0010) == 0xFF08,
              case["name"] + ": the literal final SS:0010 store is missing")
        if not core and case.get("sp") == 0x000A:
            check(expected["regs"]["ip"] == 0,
                  case["name"] + ": mirror write did not overwrite live outer RET")


def compare_one(native, case, kind, *, core):
    memory, regs, device = make_setup(case, kind, core=core)
    expected = original_single(case, kind, bytearray(memory), dict(regs),
                               copy.deepcopy(device), core=core)
    independent_case_checks(case, kind, memory, regs, device, expected, core=core)
    actual = native.run(case, kind, bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=core)
    compare_memory_and_regs(actual, expected,
                            case["name"] + (" core" if core else " adapter"))
    actual["sites"] = expected["sites"]
    actual["steps"] = expected["steps"]
    return expected


def native_only_stack_alias_witness(native):
    case = next(row for row in cases()
                if row["name"] == "restore-stack-code-operand-alias")
    memory, regs, device = make_setup(case, "restore", core=True)
    segment, expected_words, expected_memory, expected_device = (
        independent_restore_words(case, memory, regs, device))
    actual = native.run(case, "restore", bytearray(memory), dict(regs),
                        copy.deepcopy(device), core=True)

    require(actual["status"] == READY, case["name"] + ": native status differs")
    require(bytes(actual["memory"]) == bytes(expected_memory),
            case["name"] + ": native PUSH bytes differ from exact CS:5884 expectation")
    require(get16(actual["memory"], regs["cs"], 0x5884) == regs["cx"],
            case["name"] + ": native PUSH did not replace the live relocated operand")
    expected_regs = {
        "ax": expected_words[-1][1], "cx": regs["cx"], "dx": 0x03CE,
        "es": regs["es"], "sp": regs["sp"], "ip": RESTORE_RET,
    }
    for name in ("bx", "si", "di", "bp", "cs", "ds", "ss"):
        expected_regs[name] = regs[name]
    for name, value in expected_regs.items():
        require(actual["regs"][name] == value,
                f'{case["name"]}: {name} {actual["regs"][name]:04X}/{value:04X}')
    before_xor = regs["flags"] & ~IF
    after_xor = (before_xor & ~ARITH_LOGIC) | 0x0044
    final_flags = after_xor | IF
    require(((actual["regs"]["flags"] ^ final_flags) & (FLAGS & ~0x0010)) == 0,
            case["name"] + ": native CLI/XOR/STI flag phases differ")

    expected_kinds = ["write", "write"] + ["read", "read", "out"] * 9 + ["read", "read"]
    require(len(actual["events"]) == 31 and
            [event[0] for event in actual["events"]] == expected_kinds,
            case["name"] + ": expected exactly 2 PUSH writes, 20 reads, and 9 OUTs")
    writes = actual["events"][:2]
    push_address = physical(regs["ss"], (regs["sp"] - 2) & 0xFFFF)
    require([(event[1], event[2]) for event in writes] ==
            [(push_address, regs["cx"] & 0xFF),
             ((push_address + 1) & MASK, regs["cx"] >> 8)],
            case["name"] + ": native PUSH byte order or destination differs")
    output_events = [event for event in actual["events"] if event[0] == "out"]
    require([(event[1], event[2]) for event in output_events] == expected_words,
            case["name"] + ": native mirror OUT words differ from declared live alias")
    require(all((event[3] & IF) == 0 for event in actual["events"]),
            case["name"] + ": a native bus event ran after STI")
    for index, event in enumerate(output_events):
        wanted_flags = before_xor if index < 5 else after_xor
        require(((event[3] ^ wanted_flags) & (FLAGS & ~0x0010)) == 0,
                f"{case['name']}: OUT {index} flag phase differs")

    expected_event_flags = [before_xor, before_xor]
    for index in range(9):
        read_flags = before_xor if index <= 5 else after_xor
        out_flags = before_xor if index < 5 else after_xor
        expected_event_flags.extend((read_flags, read_flags, out_flags))
    expected_event_flags.extend((after_xor, after_xor))
    for index, (event, flags) in enumerate(zip(actual["events"],
                                                expected_event_flags)):
        require(((event[3] ^ flags) & (FLAGS & ~0x0010)) == 0,
                f"{case['name']}: bus event {index} FLAGS phase differs")

    mirror_reads = [event[1] for event in actual["events"]
                    if event[0] == "read"]
    wanted_reads = []
    for offset in MIRROR_OFFSETS:
        address = physical(segment, offset)
        wanted_reads.extend((address, (address + 1) & MASK))
    wanted_reads.extend((push_address, (push_address + 1) & MASK))
    require(mirror_reads == wanted_reads,
            case["name"] + ": native mirror/POP read order or alias address differs")
    require(actual["device"].state() == expected_device.state(),
            case["name"] + ": native VGA output state differs")
    require([(row[0], row[1], row[2]) for row in actual["device"].trace] ==
            [(row[0], row[1], row[2]) for row in expected_device.trace],
            case["name"] + ": native read/OUT trace differs")
    return dict(case=case["name"], domain="restore", boundary="native-only-core",
                original_executed=False, original_instruction_sites=[],
                native_status=actual["status"], push_address=push_address,
                loaded_mirror_segment=segment, expected_out_words=expected_words,
                ordered_bus_events=len(actual["events"]), reads=20, writes=2,
                outs=9, preserved_cx=True, restored_es=True, live_sp_restored=True,
                continuation=actual["regs"]["ip"])


def chain_case(name, *, load, init_ss, restore_ss, seed):
    return dict(name=name, entry="chain", load=load, seed=seed,
                init_ss=init_ss, restore_ss=restore_ss,
                bios_port=0x03FA)


def chain_setup(case):
    memory, device = initial_memory(case)
    load = case["load"]
    fixed = fixed_segment(load)
    # The fixed frame remains distinguishable when initializer SS differs.
    seed_mirrors(memory, device, fixed, case["seed"] ^ 0x31)
    init_regs = default_regs(load, case["seed"], ss=case["init_ss"], sp=0x7000,
                             ds=0x3000, es=0x0040, flags=0x06D7)
    init_regs["ip"] = INIT
    put16(memory, 0x0040, 0x0063, case["bios_port"], device)
    put16(memory, init_regs["ss"], init_regs["sp"], 0xABCD, device)
    # The equal-frame case has one physical E slot; otherwise keep both distinct.
    if init_regs["ss"] == fixed:
        put16(memory, fixed, 0x000E, 0xC35A, device)
    else:
        put16(memory, init_regs["ss"], 0x000E, 0xA55A, device)
        put16(memory, fixed, 0x000E, 0xC35A, device)
    restore_regs = default_regs(load, case["seed"] ^ 0xA0,
                                ss=case["restore_ss"], sp=0x7100,
                                ds=0x7777, es=0x6D42, flags=0x0AD7)
    restore_regs["ip"] = RESTORE
    put16(memory, restore_regs["ss"], restore_regs["sp"], 0xD00D, device)
    return memory, init_regs, restore_regs, device


def chain_original(case, memory, init_regs, restore_regs, device):
    runner = Original(memory, device)
    init_access = Access(case, memory, init_regs, device)
    init_expected = runner.run(case, "initialize", init_regs, init_access, core=False)
    init_expected["device"] = copy.deepcopy(init_expected["device"])
    check(init_expected["regs"]["ip"] == 0xABCD,
          case["name"] + ": initializer chain did not consume its own outer RET")
    # The second API receives an independent register setup over the same RAM.
    put16(memory, restore_regs["ss"], restore_regs["sp"], 0xD00D, device)
    restore_stack = physical(restore_regs["ss"], restore_regs["sp"])
    runner._sync(restore_stack, bytes(memory[restore_stack:restore_stack + 2]))
    restore_access = Access(case, memory, restore_regs, device)
    restore_expected = runner.run(case, "restore", restore_regs, restore_access,
                                  core=False)
    return init_expected, restore_expected


def chain_native(native, case, memory, init_regs, restore_regs, device):
    # Both adapters receive the same ctypes view of the one bytearray.
    ram = (ct.c_uint8 * SIZE).from_buffer(memory)
    init_actual = native.run(case, "initialize", memory, dict(init_regs),
                             device, core=False, ram=ram)
    init_actual["memory"] = bytearray(memory)
    init_actual["device"] = copy.deepcopy(device)
    put16(memory, restore_regs["ss"], restore_regs["sp"], 0xD00D, device)
    restore_actual = native.run(case, "restore", memory, dict(restore_regs),
                                 device, core=False, ram=ram)
    return init_actual, restore_actual


def chain_independent(case, initial_memory, initial_device, init_regs,
                      restore_regs, init_result, restore_result):
    fixed = fixed_segment(case["load"])
    init_ss = case["init_ss"]
    expected_memory = bytearray(initial_memory)
    expected_device = copy.deepcopy(initial_device)
    bios = get16(expected_memory, 0x0040, 0x0063)
    adjusted = (bios & 0xFF00) | ((bios + 6) & 0xFF)
    init_words = expected_init_writes(case, init_regs, expected_memory)[2]
    add_flags = add8_flags(init_regs["flags"], bios & 0xFF, 6)
    for index, (segment, offset, value) in enumerate(init_words):
        phase_flags = init_regs["flags"] if index == 0 else add_flags
        for delta, byte in enumerate((value & 0xFF, (value >> 8) & 0xFF)):
            address = (physical(segment, offset) + delta) & MASK
            if VGA_BASE <= address < VGA_END:
                expected_device.write(expected_memory, address, byte, phase_flags)
            else:
                expected_memory[address] = byte

    check(get16(init_result["memory"], init_regs["ds"], 0x1FDA) == bios,
          case["name"] + ": initializer chain omitted BIOS base store")
    check(get16(init_result["memory"], init_regs["ds"], 0x1FDC) == adjusted,
          case["name"] + ": initializer chain used word rather than byte addition")
    check(get16(init_result["memory"], init_ss, 0x000E) ==
          get16(initial_memory, init_ss, 0x000E),
          case["name"] + ": initializer filled or changed the intentionally missing E slot")
    check(get16(init_result["memory"], init_ss, 0x0010) == 0xFF08,
          case["name"] + ": FF08 did not overwrite SS:0010")
    check(get16(init_result["memory"], fixed, 0x0010) ==
          (0xFF08 if init_ss == fixed else get16(initial_memory, fixed, 0x0010)),
          case["name"] + ": initializer did not write only its live SS frame")
    check(get16(expected_memory, init_ss, 0x0010) == 0xFF08,
          case["name"] + ": independent initializer model missed final FF08")
    expected_segment, expected_words, _restore_memory, _restore_device = independent_restore_words(
        case, expected_memory, restore_regs, expected_device)
    check(expected_segment == fixed,
          case["name"] + ": chained restore did not use its fixed relocated frame")
    actual_words = [(event[1], event[2]) for event in restore_result["events"]
                    if event[0] == "out"]
    check(actual_words == expected_words,
          case["name"] + ": chained restore outputs differ from independently modeled words")
    by_port = dict(expected_words)
    check(by_port[0x03CE] & 0xFF == 0x04,
          case["name"] + ": final read-map output index is not 04")
    if init_ss == fixed:
        check(by_port[0x03CE] >> 8 == 0xFF,
              case["name"] + ": duplicate SS:0010 write was not visible as AH=FF")
        check(by_port[0x03CE] & 0xFF == 0x04 and
              expected_words[7][1] >> 8 ==
              (get16(initial_memory, fixed, 0x000E) >> 8),
              case["name"] + ": untouched SS:000E was not read as the bit-mask word")
    else:
        check(by_port[0x03CE] >> 8 != 0xFF,
              case["name"] + ": live SS initializer writes leaked into fixed ES frame")


def verify_add_truth_table():
    """Exhaust all BIOS DL bytes against an independent 8-bit flag calculation."""
    add_bytes = bytes(IMAGE[0x0507:0x050A])
    check(add_bytes == bytes.fromhex("80 C2 06"),
          "pinned initializer ADD DL,6 bytes changed")
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, 0x10000)
    # Execute the exact pinned ADD DL,6 bytes; only that instruction runs.
    cpu.mem_write(0x0100, add_bytes + b"\xF4")
    flag_inputs = (0x0002, 0x0AD7, 0x04D7)
    tested = 0
    for value in range(256):
        for flags in flag_inputs:
            cpu.reg_write(REG_IDS["cs"], 0)
            cpu.reg_write(REG_IDS["ip"], 0x0100)
            cpu.reg_write(REG_IDS["dx"], 0xA500 | value)
            cpu.reg_write(REG_IDS["flags"], flags)
            cpu.emu_start(0x0100, 0, count=1)
            got = cpu.reg_read(REG_IDS["flags"]) & 0xFFFF
            want = add8_flags(flags, value, 6)
            check(((got ^ want) & 0x08D5) == 0,
                  f"ADD DL,6 flags differ for DL={value:02X}, FLAGS={flags:04X}: "
                  f"{got:04X}/{want:04X}")
            check(cpu.reg_read(REG_IDS["dx"]) == 0xA500 | ((value + 6) & 0xFF),
                  f"ADD DL,6 changed DH for DL={value:02X}")
            tested += 1
    return tested


def compare_chain(native, case):
    memory, init_regs, restore_regs, device = chain_setup(case)
    original_memory = bytearray(memory)
    original_device = copy.deepcopy(device)
    original_runner_memory = bytearray(original_memory)
    original_runner_device = copy.deepcopy(original_device)
    init_expected, restore_expected = chain_original(
        case, original_runner_memory, init_regs, restore_regs, original_runner_device)

    native_memory = bytearray(original_memory)
    native_device = copy.deepcopy(original_device)
    init_actual, restore_actual = chain_native(
        native, case, native_memory, init_regs, restore_regs, native_device)
    compare_memory_and_regs(init_actual, init_expected,
                            case["name"] + " initializer adapter")
    compare_memory_and_regs(restore_actual, restore_expected,
                            case["name"] + " restore adapter")
    chain_independent(case, original_memory, original_device,
                      init_regs, restore_regs,
                      init_expected, restore_expected)
    return init_expected, restore_expected


def report_rows_original():
    before = hash_inputs()
    add_truth_cases = verify_add_truth_table()
    rows = []
    for case in differential_cases():
        kind = case["entry"]
        memory, regs, device = make_setup(case, kind, core=False)
        boundaries = (True,) if case.get("core_only") else (True, False)
        for core in boundaries:
            print(f"CHECKED original {case['name']} {'core' if core else 'adapter'}",
                  flush=True)
            expected = original_single(case, kind, bytearray(memory), dict(regs),
                                       copy.deepcopy(device), core=core)
            independent_case_checks(case, kind, memory, regs, device, expected,
                                    core=core)
            rows.append(dict(case=case["name"], domain=kind,
                             boundary="core" if core else "adapter",
                             sites=sorted(expected["sites"]),
                             edges=[], events=len(expected["events"]),
                             steps=expected["steps"],
                             providers=sorted(expected["providers"])))
            gc.collect()
    chain_rows = []
    for index, (init_ss, restore_ss) in enumerate(
            ((fixed_segment(LOADS[0]), fixed_segment(LOADS[0])),
             (0x3512, 0x3512))):
        case = chain_case("chain-equal-frame" if index == 0 else "chain-live-ss-diff-frame",
                          load=LOADS[0], init_ss=init_ss,
                          restore_ss=restore_ss, seed=0xA700 + index)
        memory, init_regs, restore_regs, device = chain_setup(case)
        runner = Original(bytearray(memory), copy.deepcopy(device))
        init_expected, restore_expected = chain_original(
            case, runner.memory, init_regs, restore_regs, runner.device)
        chain_independent(case, memory, device, init_regs, restore_regs,
                          init_expected, restore_expected)
        chain_rows.extend([
            dict(case=case["name"], domain="initialize", boundary="adapter",
                 sites=sorted(init_expected["sites"]), edges=[],
                 events=len(init_expected["events"]), steps=init_expected["steps"],
                 providers=sorted(init_expected["providers"]), chain_phase=1),
            dict(case=case["name"], domain="restore", boundary="adapter",
                 sites=sorted(restore_expected["sites"]), edges=[],
                 events=len(restore_expected["events"]), steps=restore_expected["steps"],
                 providers=sorted(restore_expected["providers"]), chain_phase=2),
        ])
    rows.extend(chain_rows)
    verify_coverage(rows)
    check(before == hash_inputs(), "inputs changed during original mirror campaign")
    return before, rows, add_truth_cases


def verify_coverage(rows):
    for domain in ("initialize", "restore"):
        sites = {address for row in rows if row["domain"] == domain
                 for address in row["sites"]}
        check(sites == OWN_SITES[domain],
              f"{domain}: missing sites {OWN_SITES[domain] - sites}")
    check(all(not row["edges"] for row in rows),
          "mirror leaves unexpectedly acquired branch edges")


def hash_inputs():
    # Pin the executable, exact maintained ASM, native API and local oracle closure.
    paths = {
        "assets/vgalemmi.exe", "metadata/inputs.json",
        "metadata/oracle.json",
        "metadata/toolchain-lock.json",
        "src/entry_services.asm", "src/game_code_late_after_palette.asm",
        "c/vga_mirrors.c", "c/vga_mirrors.h", "c/lemmings_sym.h",
        "c/regs.h", "c/special_blit.h", "tests/vga_mirrors.py",
        "tests/minimap_vga.py",
        "tools/bounded_process.py", "tools/cbuild.py", "tools/common.py",
        "tools/difftest.py", "tools/unpack.py",
    }
    return {path: sha((ROOT / path).read_bytes()) for path in sorted(paths)}


def publish(path, before, rows, mutants=None, add_truth_cases=0,
            native_only_witnesses=None):
    unions = {domain: sorted({address for row in rows if row["domain"] == domain
                              for address in row["sites"]})
              for domain in OWN_SITES}
    verify_coverage(rows)
    all_sites = sorted(set(unions["initialize"]) | set(unions["restore"]))
    event_totals = {}
    for row in rows:
        key = row["domain"] + "/" + row["boundary"]
        event_totals[key] = event_totals.get(key, 0) + row["events"]
    native_only_witnesses = native_only_witnesses or []
    report = dict(image="main", image_sha256=sha(IMAGE),
                  entries=dict(initialize=INIT, restore=RESTORE),
                  returns=dict(initialize=INIT_RET, restore=RESTORE_RET),
                  ends=dict(initialize=INIT_END, restore=RESTORE_END),
                  case_count=len(differential_cases()) + 2 +
                             len(native_only_witnesses),
                  total_case_count=len(differential_cases()) + 2 +
                                   len(native_only_witnesses),
                  single_fixture_count=len(differential_cases()),
                  chain_fixture_count=2, chain_comparison_count=4,
                  native_only_fixture_count=len(native_only_witnesses),
                  native_only_witnesses=native_only_witnesses,
                  original_excluded_cases=[dict(
                      case="restore-stack-code-operand-alias",
                      reason="Unicorn restarts one-step PUSH when SS:CS:5884 aliases its translated code page; retained as a native-only independent witness.")],
                  comparison_count=len(rows),
                  translated_code_bytes=sum(END - START for START, END in
                    ((INIT, INIT_END), (RESTORE, RESTORE_END))),
                  instruction_sites=sum(len(sites) for sites in OWN_SITES.values()),
                  executed_instruction_addresses=all_sites,
                  site_union_by_domain=unions, branch_edges=[], branch_edge_count=0,
                  ordered_events=sum(row["events"] for row in rows),
                  events_by_domain_boundary=event_totals,
                  instruction_steps=sum(row["steps"] for row in rows),
                  independent_add_flag_cases=add_truth_cases,
                  original_only=mutants is None, mutation_count=len(mutants or []),
                  mutations=mutants or [], rows=rows, input_hashes=before,
                  limits=dict(timeout_seconds=WORKER_SECONDS,
                               process_commit_mib=MEMORY_MIB,
                               original_instruction_limit=MAX_STEPS,
                               bus_event_limit=MAX_EVENTS))
    write_json(path, report)
    comparison_scope = "original-only" if mutants is None else "original/native"
    print(f"PASS VGA mirrors: {len(rows)} {comparison_scope} comparisons, "
          f"{len(all_sites)} sites, {report['ordered_events']} events, "
          f"{len(mutants or [])} mutants", flush=True)


def original_worker():
    before, rows, add_truth_cases = report_rows_original()
    publish(ORIGINAL_REPORT, before, rows, add_truth_cases=add_truth_cases)


def worker(directory, snapshot):
    before = json.loads(Path(snapshot).read_text(encoding="utf-8"))
    check(before == hash_inputs(), "input hash snapshot differs")
    native = Native(directory, mutation=0)
    rows = []
    for case in differential_cases():
        kind = case["entry"]
        boundaries = (True,) if case.get("core_only") else (True, False)
        for core in boundaries:
            expected = compare_one(native, case, kind, core=core)
            rows.append(dict(case=case["name"], domain=kind,
                             boundary="core" if core else "adapter",
                             sites=sorted(expected["sites"]), edges=[],
                             events=len(expected["events"]), steps=expected["steps"],
                             providers=sorted(expected["providers"])))
        gc.collect()
    chains = (
        chain_case("chain-equal-frame", load=LOADS[0],
                   init_ss=fixed_segment(LOADS[0]),
                   restore_ss=fixed_segment(LOADS[0]), seed=0xA700),
        chain_case("chain-live-ss-diff-frame", load=LOADS[0],
                   init_ss=0x3512, restore_ss=0x3512, seed=0xA701),
    )
    for case in chains:
        init_expected, restore_expected = compare_chain(native, case)
        rows.extend([
            dict(case=case["name"], domain="initialize", boundary="adapter",
                 sites=sorted(init_expected["sites"]), edges=[],
                 events=len(init_expected["events"]), steps=init_expected["steps"],
                 providers=sorted(init_expected["providers"]), chain_phase=1),
            dict(case=case["name"], domain="restore", boundary="adapter",
                 sites=sorted(restore_expected["sites"]), edges=[],
                 events=len(restore_expected["events"]), steps=restore_expected["steps"],
                 providers=sorted(restore_expected["providers"]), chain_phase=2),
        ])

    witnesses = (
        (1, "restore-live-pop-cx-provider", "restore", False),
        (2, "restore-live-ss-distinct-fixed-frame", "restore", True),
        (3, "restore-load-1010", "restore", True),
        (4, "restore-load-1010", "restore", True),
        (5, "restore-xor-al-index-zero", "restore", True),
        (6, "restore-if-clear-df-set", "restore", False),
        (7, "chain-equal-frame", "chain", False),
        (8, "initialize-load-1010", "initialize", False),
        (9, "chain-equal-frame", "chain", False),
        (10, "initialize-dl-wrap-carry", "initialize", True),
    )
    by_name = {case["name"]: case for case in cases()}
    by_name.update({case["name"]: case for case in chains})
    mutants = []
    for mutation, name, kind, core in witnesses:
        mutant = Native(directory, mutation=mutation)
        try:
            if kind == "chain":
                compare_chain(mutant, by_name[name])
            else:
                compare_one(mutant, by_name[name], kind, core=core)
        except Mismatch as error:
            mutants.append(dict(mutation=mutation, case=name, domain=kind,
                                core=core, completed=True, mismatch=str(error)))
        else:
            raise OracleFailure(f"mutation {mutation} survived its declared witness")
        gc.collect()
    native_only_witnesses = [native_only_stack_alias_witness(native)]
    verify_coverage(rows)
    check(before == hash_inputs(), "inputs changed during native mirror campaign")
    publish(REPORT, before, rows, mutants,
            add_truth_cases=verify_add_truth_table(),
            native_only_witnesses=native_only_witnesses)


def main():
    BUILD.mkdir(exist_ok=True)
    if sys.argv[1:] == ["--original-worker"]:
        original_worker()
        return
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:] == ["--original-only"]:
        run_bounded([sys.executable, __file__, "--original-worker"], cwd=ROOT,
                    timeout=WORKER_SECONDS, memory_mib=MEMORY_MIB, check=True)
        return
    if sys.argv[1:]:
        raise SystemExit("usage: vga_mirrors.py [--original-only]")
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix="vga-mirrors-", parent=BUILD) as directory:
        snapshot = Path(directory) / "input-hashes.json"
        snapshot.write_text(json.dumps(hash_inputs(), sort_keys=True),
                            encoding="utf-8")
        run_bounded([sys.executable, __file__, "--worker", str(directory),
                     str(snapshot)], cwd=ROOT, timeout=WORKER_SECONDS,
                    memory_mib=MEMORY_MIB, check=True)


if __name__ == "__main__":
    main()

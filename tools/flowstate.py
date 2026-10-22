"""Conservative 16-bit flow state over explore's decoded instructions and edges.

No decoder, emulator, game execution, or source generation lives here. Procedure
summaries are symbolic transformers, not an assumed PUSH/POP calling convention.
CALL pushes the real continuation; RET/RETF/IRET read the abstract stack words.

Two scopes must not be confused. Decoded-edge results assume unchanged decoded
instructions and the listed edges. Unclosed transfers/aliases can reenter any
instruction: the unconditional whole-machine result is TOP in that case. The
report retains both, rather than presenting a conditional result as a proof.

The optional intact-stack mode excludes non-stack-addressed writes to live saves.
Undeclared INT services havoc *all* tracked state, including SS/SP/FLAGS. Service
declarations describe a conditional IRET/frame contract, not proven BIOS/DOS ABIs.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass, field
from itertools import product
import re

from common import ROOT, BUILD, read_json, write_json, sha

REGS = ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp', 'ds', 'es', 'ss', 'cs')
HALVES = {a + b: (a + 'x', 8 if b == 'h' else 0)
          for a in 'abcd' for b in ('l', 'h')}
CAP = 4
# None is TOP, frozenset() is BOTTOM. Atoms may be constants or provenance tuples.
TOP = None
ZERO = frozenset((0,))
ONE = frozenset((1,))


def val(atom):
    return frozenset((atom,))


def union(a, b):
    if a is None or b is None:
        return TOP
    c = a | b
    return c if len(c) <= CAP else TOP


def only(v):
    return next(iter(v)) if v is not None and len(v) == 1 else None


def numbers(v):
    return v is not None and all(isinstance(a, int) for a in v)


def may(v, bit):
    return v is None or bit in v or any(not isinstance(a, int) for a in v)


def add(v, n):
    if v is None:
        return TOP
    out = frozenset((a + n) & 0xffff if isinstance(a, int) else
                    (a[0], (a[1] + n) & 0xffff) if a[0] in ('sp', 'reloc')
                    else ('unknown-arithmetic',) for a in v)
    return TOP if ('unknown-arithmetic',) in out else out


def flags(df, iff):
    return val(('flags', df, iff))


def flag_part(v, index):
    if v is None:
        return TOP
    result = frozenset()
    for a in v:
        part = val((a >> (10 if index == 1 else 9)) & 1) if isinstance(a, int) else (
            a[index] if a[0] == 'flags' else
            val(('flag-bit', val(a), index)) if a[0] in ('stack', 'in') else TOP)
        result = union(result, part)
    return result


@dataclass(frozen=True)
class Slot:
    value: object = TOP
    pushes: frozenset = frozenset()


@dataclass
class State:
    regs: dict = field(default_factory=lambda: dict.fromkeys(REGS, TOP))
    df: object = TOP
    iff: object = TOP
    sp: int | None = 0
    slots: dict = field(default_factory=dict)
    polluted: bool = False
    shadow: object = ZERO

    @classmethod
    def symbolic(cls):
        return cls({r: val(('in', r)) for r in REGS},
                   val(('in', 'df')), val(('in', 'if')))

    @classmethod
    def havoc(cls):
        return cls(sp=None, polluted=True, shadow=TOP)

    def copy(self):
        return State(dict(self.regs), self.df, self.iff, self.sp,
                     dict(self.slots), self.polluted, self.shadow)

    def read_slot(self, offset):
        if offset is None:
            return Slot()
        return self.slots.get(offset & 0xffff,
                              Slot(TOP if self.polluted else val(('stack', offset & 0xffff))))

    def poison(self):
        self.slots.clear()
        self.polluted = True

    def write_slot(self, offset, value, pushes=frozenset()):
        if offset is None:
            self.poison()
            return
        offset &= 0xffff
        # Word high bytes are physically adjacent, including at offset FFFF.
        # Without an absolute stack anchor, conservatively include both wrap
        # interpretations when invalidating overlapping word saves.
        for p in (offset - 1, offset + 1):
            if (p & 0xffff) in self.slots:
                self.slots[p & 0xffff] = Slot()
        self.slots[offset] = Slot(value, pushes)
        if len(self.slots) > 64:
            self.poison()

    def push(self, value, address):
        self.sp = None if self.sp is None else (self.sp - 2) & 0xffff
        self.write_slot(self.sp, value, frozenset((address,)))

    def pop(self):
        result = self.read_slot(self.sp)
        self.sp = None if self.sp is None else (self.sp + 2) & 0xffff
        return result


def merge(a, b):
    if a is None:
        return b.copy()
    sp = a.sp if a.sp == b.sp else None
    polluted = a.polluted or b.polluted or sp is None
    slots = {}
    if sp is not None:
        for p in a.slots.keys() | b.slots.keys():
            x, y = a.read_slot(p), b.read_slot(p)
            slots[p] = Slot(union(x.value, y.value), x.pushes | y.pushes)
    if len(slots) > 64:
        slots, polluted = {}, True
    return State({r: union(a.regs[r], b.regs[r]) for r in REGS},
                 union(a.df, b.df), union(a.iff, b.iff), sp, slots,
                 polluted, union(a.shadow, b.shadow))


def substitute(v, incoming, base):
    if v is None:
        return TOP
    result = frozenset()
    for a in v:
        if isinstance(a, int):
            part = val(a)
        elif a[0] == 'in':
            part = incoming.df if a[1] == 'df' else incoming.iff if a[1] == 'if' else incoming.regs[a[1]]
        elif a[0] == 'stack':
            part = incoming.read_slot(None if base is None else base + a[1]).value
        elif a[0] == 'sp':
            part = TOP if base is None else val(('sp', (base + a[1]) & 0xffff))
        elif a[0] == 'flags':
            part = flags(substitute(a[1], incoming, base), substitute(a[2], incoming, base))
        elif a[0] == 'flag-bit':
            part = flag_part(substitute(a[1], incoming, base), a[2])
        else:
            part = val(a)
        result = union(result, part)
    return result


def instantiate(template, incoming):
    """Apply a symbolic procedure state with its entry at incoming.SP."""
    base = incoming.sp
    out = incoming.copy()
    out.regs = {r: substitute(template.regs[r], incoming, base) for r in REGS}
    out.df, out.iff = (substitute(v, incoming, base) for v in (template.df, template.iff))
    out.shadow = substitute(template.shadow, incoming, base)
    out.sp = None if base is None or template.sp is None else (base + template.sp) & 0xffff
    if template.polluted:
        out.poison()
    for p, slot in sorted(template.slots.items()):
        pushes = slot.pushes
        if slot.value is not None:
            for atom in slot.value:
                if not isinstance(atom, int) and atom[0] == 'stack':
                    pushes |= incoming.read_slot(None if base is None else base + atom[1]).pushes
        out.write_slot(None if base is None else base + p,
                       substitute(slot.value, incoming, base), pushes)
    return out


def operands(row):
    # explore owns decoding; its normalized x86 operand spelling has no comma
    # inside these 16-bit addressing expressions.
    return [s.strip() for s in row.get('operands', '').split(',') if s.strip()]


def integer(s):
    try:
        return int(s, 0)
    except ValueError:
        return None


def getreg(s, name):
    if name == 'sp':
        return TOP if s.sp is None else val(('sp', s.sp))
    if name in HALVES:
        reg, shift = HALVES[name]
        value = s.regs[reg]
        return frozenset((a >> shift) & 0xff for a in value) if numbers(value) else TOP
    return s.regs.get(name, TOP)


def setreg(s, name, value):
    if name == 'sp':
        atom = only(value)
        s.sp = atom[1] if isinstance(atom, tuple) and atom[0] == 'sp' else None
        if s.sp is None:
            s.poison()
    elif name in HALVES:
        reg, shift = HALVES[name]
        old = s.regs[reg]
        mask = 0xff << shift
        s.regs[reg] = (frozenset(((a & ~mask) | ((b & 0xff) << shift)) & 0xffff
                                for a, b in product(old, value))
                       if numbers(old) and numbers(value) else TOP)
        if s.regs[reg] is not None and len(s.regs[reg]) > CAP:
            s.regs[reg] = TOP
    elif name in REGS:
        s.regs[name] = value
        if name == 'ss':
            # Changing the segment breaks every old physical slot identity.
            s.poison()
            s.shadow = ONE


def memory_offset(s, operand):
    """Resolve only genuine SS:SP/BP-relative stack expressions."""
    if '[' not in operand:
        return None
    explicit = re.search(r'\b(cs|ds|es|ss):', operand)
    expr = operand.split('[', 1)[1].split(']', 1)[0].replace(' ', '')
    uses_bp = 'bp' in expr
    if (explicit and explicit[1] != 'ss') or (not explicit and not uses_bp and 'sp' not in expr):
        return None
    terms = re.findall(r'[+-]?[^+-]+', expr)
    relative, offset = False, 0
    for term in terms:
        sign = -1 if term.startswith('-') else 1
        term = term.lstrip('+-')
        n = integer(term)
        if n is not None:
            offset += sign * n
        else:
            atom = only(getreg(s, term))
            if sign != 1 or relative or not isinstance(atom, tuple) or atom[0] != 'sp':
                return None
            relative, offset = True, offset + atom[1]
    return offset & 0xffff if relative else None


def read_operand(s, operand, site=None):
    if '[' in operand:
        p = memory_offset(s, operand)
        return s.read_slot(p).value if p is not None and 'byte ptr' not in operand else (
            val(('read', site, operand)) if site is not None else TOP)
    n = integer(operand)
    return val(n & 0xffff) if n is not None else getreg(s, operand)


def write_operand(s, operand, value, intact_stack):
    if '[' not in operand:
        setreg(s, operand, value)
        return
    p = memory_offset(s, operand)
    if p is not None:
        if 'byte ptr' in operand:
            # Partial writes destroy both potentially overlapping words.
            for q in (p, (p - 1) & 0xffff):
                s.slots[q] = Slot()
        else:
            s.write_slot(p, value)
    elif not intact_stack:
        s.poison()


def arithmetic(m, left, right, same=False):
    if same and m in ('xor', 'sub'):
        return ZERO
    n = only(right)
    if m in ('add', 'sub') and isinstance(n, int):
        return add(left, n if m == 'add' else -n)
    if not numbers(left) or not numbers(right):
        return TOP
    out = set()
    for a, b in product(left, right):
        if m in ('shl', 'shr', 'sar') and not 0 <= b < 16:
            # Do not select an 8086/286/386 count-masking rule implicitly.
            return TOP
        if m == 'and': c = a & b
        elif m == 'or': c = a | b
        elif m == 'xor': c = a ^ b
        elif m == 'shl': c = a << (b & 31)
        elif m == 'shr': c = a >> (b & 31)
        elif m == 'sar': c = (a if a < 0x8000 else a - 0x10000) >> (b & 31)
        else: return TOP
        out.add(c & 0xffff)
    return frozenset(out) if len(out) <= CAP else TOP


def transfer(row, state, *, intact_stack=False, relocations=(), services=None):
    """One instruction, excluding CALL/RET edges. No assumed FLAGS ABI."""
    s = state.copy()
    s.shadow = ZERO  # STI / MOV SS / POP SS inhibit exactly the next instruction.
    m, ops, p = row['mnemonic'], operands(row), row['address']
    if m in ('cld', 'std'):
        s.df = ZERO if m == 'cld' else ONE
    elif m in ('cli', 'sti'):
        s.iff = ZERO if m == 'cli' else ONE
        if m == 'sti': s.shadow = ONE
    elif m == 'pushf':
        s.push(flags(s.df, s.iff), p)
    elif m == 'popf':
        f = s.pop().value
        s.df, s.iff = flag_part(f, 1), flag_part(f, 2)
    elif m == 'push':
        s.push(read_operand(s, ops[0], p), p)
    elif m == 'pop':
        value = s.pop().value
        write_operand(s, ops[0], value, intact_stack)
    elif m in ('mov', 'lea'):
        value = read_operand(s, ops[1], p)
        if m == 'lea':
            expr = ops[1].split('[', 1)[1].split(']', 1)[0]
            n = integer(expr)
            value = val(n) if n is not None else TOP
        elif any(p < site < p + row['size'] for site in relocations) and integer(ops[1]) is not None:
            value = val(('reloc', integer(ops[1])))
        write_operand(s, ops[0], value, intact_stack)
    elif m == 'xchg':
        a, b = (read_operand(s, op) for op in ops)
        write_operand(s, ops[0], b, intact_stack)
        write_operand(s, ops[1], a, intact_stack)
    elif m in ('lds', 'les'):
        setreg(s, ops[0], TOP)
        setreg(s, 'ds' if m == 'lds' else 'es', TOP)
    elif m in ('inc', 'dec', 'neg', 'not'):
        a = read_operand(s, ops[0])
        value = add(a, 1 if m == 'inc' else -1) if m in ('inc', 'dec') else (
            frozenset(((-x if m == 'neg' else ~x) & 0xffff) for x in a) if numbers(a) else TOP)
        write_operand(s, ops[0], value, intact_stack)
    elif m in ('add', 'sub', 'adc', 'sbb', 'and', 'or', 'xor', 'shl', 'shr', 'sar', 'rol', 'ror', 'rcl', 'rcr'):
        a, b = (read_operand(s, op) for op in ops)
        value = arithmetic(m, a, b, ops[0] == ops[1] and '[' not in ops[0])
        # Byte arithmetic uses 8-bit signedness and count rules; forget rather
        # than reuse word arithmetic (its flags are outside this domain).
        if ops[0] in HALVES and m not in ('xor', 'sub', 'and', 'or'):
            value = TOP
        write_operand(s, ops[0], value, intact_stack)
    elif any(k in m for k in ('stos', 'movs', 'lods', 'scas', 'cmps')):
        width = 2 if m.endswith('w') else 1
        repeated = m.startswith(('rep ', 'repe ', 'repne '))
        count = only(s.regs['cx']) if repeated else 1
        direction = only(s.df)
        delta = width * count * (1 if direction == 0 else -1) if isinstance(count, int) and direction in (0, 1) else None
        if any(k in m for k in ('stos', 'movs')) and count != 0 and not intact_stack:
            s.poison()
        if any(k in m for k in ('movs', 'lods', 'cmps')):
            s.regs['si'] = add(s.regs['si'], delta) if delta is not None else TOP
        if any(k in m for k in ('movs', 'stos', 'scas', 'cmps')):
            s.regs['di'] = add(s.regs['di'], delta) if delta is not None else TOP
        if 'lods' in m: setreg(s, 'ax' if width == 2 else 'al', TOP)
        if repeated: s.regs['cx'] = ZERO if m.startswith('rep ') else TOP
    elif m.startswith('loop'):
        s.regs['cx'] = add(s.regs['cx'], -1)
    elif m in ('mul', 'imul', 'div', 'idiv'):
        s.regs['ax'] = s.regs['dx'] = TOP
    elif m in ('cwde', 'cbw'):
        # Capstone calls opcode98 cwde in this decoder. Preserve 16-bit CBW.
        a = getreg(s, 'al')
        s.regs['ax'] = frozenset(x if x < 128 else x + 0xff00 for x in a) if numbers(a) else TOP
    elif m in ('cwd', 'cdq'):
        s.regs['dx'] = TOP
    elif m in ('in', 'xlatb'):
        setreg(s, ops[0] if m == 'in' else 'al', TOP)
    elif m in ('int', 'int3'):
        declaration = (services or {}).get(p)
        if declaration is None:
            return State.havoc()
        if not declaration.get('evidence') or not declaration.get('intact_iret_frame'):
            raise ValueError('Service needs evidence and an explicit intact_iret_frame contract')
        # CPU frame exists even when the body is a platform transformer.
        s.push(flags(s.df, s.iff), p)
        s.push(s.regs['cs'], p)
        s.push(val((p + row['size']) & 0xffff), p)
        frame_sp = s.sp
        frame_slots = {((frame_sp + n) & 0xffff): s.read_slot(frame_sp + n)
                       for n in (0, 2, 4)} if frame_sp is not None else {}
        if not declaration.get('preserve_caller_stack', False):
            s.poison()
            s.slots.update(frame_slots)
        s.iff = ZERO
        preserve = set(declaration.get('preserve', []))
        for reg in REGS:
            if reg not in preserve: s.regs[reg] = TOP
        for reg, atom in declaration.get('set', {}).items():
            if reg not in REGS or reg in ('ss', 'cs'):
                raise ValueError('IRET transformer set supports general registers/DS/ES only')
            setreg(s, reg, val(tuple(atom) if isinstance(atom, list) else atom))
        # Frame-preserving service also restores its original SS:SP. A service
        # needing another stack/return contract must stay undeclared here.
        s.regs['ss'] = state.regs['ss']
        s.pop()
        s.regs['cs'] = s.pop().value
        f = s.pop().value
        s.df, s.iff = flag_part(f, 1), flag_part(f, 2)
        for flag, value in declaration.get('return_flags', {}).items():
            if flag not in ('DF', 'IF') or value not in (0, 1, 'unknown'):
                raise ValueError('return_flags supports DF/IF with 0, 1, or unknown')
            if flag == 'DF': s.df = TOP if value == 'unknown' else val(value)
            else: s.iff = TOP if value == 'unknown' else val(value)
        if declaration.get('return_flags') and s.sp is not None:
            pos = (s.sp - 2) & 0xffff
            s.write_slot(pos, flags(s.df, s.iff), s.read_slot(pos).pushes)
    elif m in ('nop', 'cmp', 'test', 'out', 'stc', 'clc', 'cmc', 'jmp', 'ljmp',
               'call', 'lcall', 'ret', 'retf', 'iret', 'hlt') or m.startswith('j'):
        pass
    else:
        # Unmodelled instructions must never accidentally preserve state.
        return State.havoc()
    return s


@dataclass
class Exit:
    state: State
    ip: object
    cs: object
    kind: str


class Analyzer:
    """Finite symbolic summary worklist; callers restart only when a child grows."""
    def __init__(self, analysis, entries=(), *, intact_stack=False,
                 services=None, relocations=(), irq_mode='havoc'):
        self.instructions = {r['address']: r for r in analysis['instructions']}
        self.edges = defaultdict(list)
        for e in analysis['edges']: self.edges[e['source']].append(e)
        self.frontiers = {r['address']: r for r in analysis.get('unresolved', [])}
        self.entries = sorted(set(entries) | set(analysis.get('routines', [])) |
                              {e['target'] for e in analysis['edges'] if 'call' in e['kind'] and e['target'] is not None})
        self.intact_stack, self.services = intact_stack, services or {}
        self.relocations, self.irq_mode = set(relocations), irq_mode
        self.states, self.exits = {}, defaultdict(dict)
        self.dependencies, self.calls = defaultdict(set), {}
        self.queue, self.queued = deque(), set()
        self.events = set()
        self.steps = 0

    def offer(self, entry, address, state):
        if address not in self.instructions:
            self.events.add((address, 'undecoded_target'))
            return
        key = (entry, address)
        joined = merge(self.states.get(key), state)
        if joined != self.states.get(key):
            self.states[key] = joined
            if key not in self.queued:
                self.queued.add(key)
                self.queue.append(key)

    def before(self, state):
        if self.irq_mode == 'havoc' and may(state.iff, 1) and may(state.shadow, 0):
            # Arbitrary installed/nested handlers and providers have not been
            # certified to preserve frames, code, or state. Include every return
            # effect, not just register preservation on a nominal IRET path.
            return merge(state, State.havoc())
        return state

    def run(self):
        for entry in self.entries:
            self.offer(entry, entry, State.symbolic())
        while self.queue:
            entry, p = self.queue.popleft()
            self.queued.remove((entry, p))
            self.steps += 1
            if self.steps > 2_000_000:
                raise RuntimeError('Flow-state work budget exceeded; no report accepted')
            self.process(entry, p)
        return self

    def process(self, entry, p):
        row = self.instructions[p]
        incoming = self.before(self.states[entry, p])
        m, nxt = row['mnemonic'], (p + row['size']) & 0xffff
        if m in ('int', 'int3') and p not in self.services:
            self.events.add((p, 'undeclared_interrupt_service'))
        out = transfer(row, incoming, intact_stack=self.intact_stack,
                       relocations=self.relocations, services=self.services)
        edges = self.edges[p]
        if m in ('ret', 'retf', 'iret'):
            ip = out.pop().value
            cs = out.pop().value if m != 'ret' else out.regs['cs']
            if m == 'iret':
                f = out.pop().value
                out.df, out.iff = flag_part(f, 1), flag_part(f, 2)
            out.regs['cs'] = cs
            op = operands(row)
            if op: out.sp = None if out.sp is None else (out.sp + int(op[0], 0)) & 0xffff
            # RET of a locally constructed constant is a real transfer, not
            # necessarily a procedure return (e.g. dispatch/shared continuation).
            if numbers(ip) and (m == 'ret' or cs in (val(('reloc', 0)), val(('in', 'cs')))):
                for target in sorted(ip): self.offer(entry, target, out)
                return
            old = self.exits[entry].get(p)
            new = Exit(merge(old.state if old else None, out),
                       union(old.ip, ip) if old else ip,
                       union(old.cs, cs) if old else cs, m)
            if new != old:
                self.exits[entry][p] = new
                for caller in sorted(self.dependencies[entry]):
                    if caller not in self.queued:
                        self.queue.append(caller)
                        self.queued.add(caller)
            if ip is None: self.events.add((p, 'unknown_return_word'))
            return
        if m in ('call', 'lcall'):
            frame = incoming.copy()
            frame.shadow = ZERO
            unknown_base = frame.sp is None
            if unknown_base:
                # The new CALL still writes a known return word at a new
                # relative anchor, even if earlier code lost the caller's SP.
                frame.sp = 0
                frame.poison()
            if m == 'lcall': frame.push(frame.regs['cs'], p)
            frame.push(val(nxt), p)
            targets = [e['target'] for e in edges if 'call' in e['kind'] and e['target'] is not None]
            self.calls[entry, p] = (frame, tuple(sorted(targets)))
            for target in targets:
                if target == nxt:
                    if unknown_base:
                        frame.sp = None
                        frame.poison()
                    self.offer(entry, nxt, frame)  # CALL-next / POP transport
                    continue
                self.dependencies[target].add((entry, p))
                for exit_ in self.exits[target].values():
                    resumed = instantiate(exit_.state, frame)
                    ips = substitute(exit_.ip, frame, frame.sp)
                    css = substitute(exit_.cs, frame, frame.sp)
                    if unknown_base:
                        resumed.sp = None
                        resumed.poison()
                        for reg, value in resumed.regs.items():
                            if value is not None and any(isinstance(a, tuple) and a[0] == 'sp' for a in value):
                                resumed.regs[reg] = TOP
                    if numbers(ips):
                        for ip in sorted(ips):
                            if css == frame.regs['cs']:
                                self.offer(entry, ip, resumed)
                            else:
                                self.events.add((p, 'unresolved_return_segment'))
                                self.offer(entry, nxt, State.havoc())
                    else:
                        self.events.add((p, 'unresolved_return_destination'))
                        self.offer(entry, nxt, State.havoc())
            if not targets:
                self.events.add((p, 'unknown_call_target'))
                self.offer(entry, nxt, State.havoc())
            return
        external = [e for e in edges if e['kind'] == 'external_interrupt_return']
        if external:
            # Its metadata declares an intact caller-supplied IRET frame, with
            # otherwise unconstrained provider registers/segments. No CALL here.
            out = incoming.copy()
            if not self.intact_stack:
                frame_slots = {((out.sp + n) & 0xffff): out.read_slot(out.sp + n)
                               for n in (0, 2, 4)} if out.sp is not None else {}
                out.poison()
                out.slots.update(frame_slots)
            out.regs = dict.fromkeys(REGS, TOP)
            out.regs['ss'] = incoming.regs['ss']
            ip, cs, f = out.pop().value, out.pop().value, out.pop().value
            out.regs['cs'], out.df, out.iff = cs, flag_part(f, 1), flag_part(f, 2)
            targets = set(ip) if numbers(ip) else {e['target'] for e in external}
            if not numbers(ip): self.events.add((p, 'unresolved_external_iret_word'))
            for target in sorted(targets): self.offer(entry, target, out)
            return
        for edge in edges:
            if edge['target'] is not None and edge['kind'] not in ('call', 'far_call', 'indirect_call'):
                self.offer(entry, edge['target'], out)
        if p in self.frontiers: self.events.add((p, self.frontiers[p]['kind']))

    def aggregate(self):
        states = {}
        for (_, p), s in sorted(self.states.items()):
            states[p] = merge(states.get(p), self.before(s))
        return states

    def project(self, roots):
        """Instantiate generic summaries from DOS/handler/frontier inputs.

        The finite join at each callee deliberately forgets which caller supplied
        a value. It never uses routine-discovery seeds as reachable machine roots.
        SP in each callee is relative to that callee's own entry, not a guessed
        whole-program stack depth. Local entry-relative states remain separate.
        """
        by_entry = defaultdict(list)
        for (entry, p), state in sorted(self.states.items()):
            by_entry[entry].append((p, state))
        inputs, observed = {}, {}
        pending, queued = deque(), set()

        def offer(entry, incoming):
            joined = merge(inputs.get(entry), incoming)
            if joined != inputs.get(entry):
                inputs[entry] = joined
                if entry not in queued:
                    pending.append(entry)
                    queued.add(entry)

        for entry, state in sorted(roots.items()): offer(entry, state)
        while pending:
            entry = pending.popleft()
            queued.remove(entry)
            incoming = inputs[entry]
            for p, template in by_entry[entry]:
                actual = self.before(instantiate(template, incoming))
                observed[p] = merge(observed.get(p), actual)
                call = self.calls.get((entry, p))
                if call is None: continue
                frame_template, targets = call
                frame = instantiate(frame_template, incoming)
                for target in targets:
                    if target == (p + self.instructions[p]['size']) & 0xffff: continue
                    normalized = frame.copy()
                    base = frame.sp
                    normalized.sp = 0
                    normalized.slots = {}
                    normalized.polluted = True
                    if base is not None:
                        for pos, slot in frame.slots.items():
                            normalized.slots[(pos - base) & 0xffff] = slot
                    # BP/SP-derived pointers into the caller's stack need the
                    # same coordinate change as the slots, including across CALL.
                    for reg, value in frame.regs.items():
                        if value is not None:
                            normalized.regs[reg] = frozenset(
                                ('sp', (a[1] - base) & 0xffff) if isinstance(a, tuple) and a[0] == 'sp' and base is not None
                                else a for a in value)
                    offer(target, normalized)
        return observed, inputs


def display_atom(a):
    if isinstance(a, int): return f'{a:04X}'
    if a[0] == 'reloc': return 'CS' if a[1] == 0 else f'relocated:{a[1]:04X}'
    if a[0] == 'in': return 'saved-from-entry:' + a[1]
    if a[0] == 'sp': return f'entry-SP{signed(a[1]):+d}'
    if a[0] == 'stack': return f'saved-from-entry-stack{signed(a[1]):+d}'
    if a[0] == 'flags': return {'DF': display(a[1], True), 'IF': display(a[2], True)}
    if a[0] == 'flag-bit': return {'saved-FLAGS-bit': 10 if a[2] == 1 else 9, 'from': display(a[1])}
    if a[0] == 'read': return f'memory-read@{a[1]:04X}:{a[2]}'
    return ':'.join(str(p) for p in a)


def stable_key(a):
    """Python hash randomization must not order nested FLAGS alternatives."""
    if a is None: return ('0',)
    if isinstance(a, int): return ('1', a)
    if isinstance(a, str): return ('2', a)
    if isinstance(a, frozenset): return ('3', tuple(sorted(stable_key(x) for x in a)))
    return ('4', tuple(stable_key(x) for x in a))


def display(v, bit=False):
    if v is None: return 'unknown'
    if bit and numbers(v): return only(v) if len(v) == 1 else sorted(v)
    atoms = [display_atom(a) for a in sorted(v, key=stable_key)]
    return atoms[0] if len(atoms) == 1 else atoms


def signed(n):
    return n if n < 0x8000 else n - 0x10000


def state_json(s):
    return dict(DF=display(s.df, True), IF=display(s.iff, True),
                segments={r.upper(): display(s.regs[r]) for r in ('cs', 'ds', 'es', 'ss')},
                registers={r.upper(): display(s.regs[r]) for r in ('ax', 'bx', 'cx', 'dx', 'si', 'di', 'bp')},
                SP_relative_to_entry=signed(s.sp) if s.sp is not None else 'unknown',
                interrupt_shadow=display(s.shadow, True),
                maskable_IRQ_may_land=may(s.iff, 1) and may(s.shadow, 0),
                stack_default='unknown' if s.polluted else 'saved-from-entry-stack',
                popped_slot_residues_not_printed=True,
                slots=[dict(offset=signed(p), value=display(slot.value),
                            pushes=[f'{a:04X}' for a in sorted(slot.pushes)])
                       for p, slot in sorted(s.slots.items(), key=lambda pair: signed(pair[0]))
                       if s.sp is not None and ((p - s.sp) & 0xffff) < 0x8000])


def load_component(name):
    if name == 'main':
        from explore import analyze
        from unpack import unpack, ASSET
        image, meta = unpack(ASSET.read_bytes())
        return analyze(), image, [r['linear'] for r in meta['relocations']]
    from resources import sound_images
    from sound import analyze_driver
    image, _ = sound_images()[name]
    return analyze_driver(name, image), image, []


def report(analysis, image, relocations=(), *, component='main', services=None, entries=()):
    roots = set(entries)
    for frontier in analysis.get('unresolved', []):
        roots.update(frontier.get('known_targets', []))
        if frontier.get('continuation') is not None: roots.add(frontier['continuation'])
        if 'target' in frontier['kind']: roots.add(frontier['address'])
    installations = []
    if component == 'main':
        installations = read_json(ROOT/'metadata/interrupt-evidence.json')['installations']
        roots.add(0)
        roots.add(0xdff)  # Installed transformed INT1; not raw-decoded as code.
        # Includes the explicitly installed INT3 handler and isolated coherent
        # candidates. These are inventory roots, not claimed startup reachability.
        roots.update(r['offset'] for r in read_json(ROOT/'metadata/hints.json')['entries'])
        for frontier in read_json(ROOT/'metadata/control-frontier.json'):
            roots.update(int(p, 16) for p in frontier.get('known_targets', []))
        roots.update(r['offset'] for r in installations if r['target_image'] == 'main')
    else:
        roots.add(0x182 if component == 'pcspeaker' else 0)
    # Every declared frontier target, even undecoded/protected, remains in the
    # inventory. Absent instruction states mean unavailable, never unreachable.
    investigations = set(roots)
    if component == 'main':
        investigations.update((0x13dc, 0x1bb0, 0x1d2e, 0x30a6, 0x3336, 0x410f,
                               0x4c7e, 0x706f, 0x796f, 0x8822))
    elif component == 'adlib':
        investigations.update((0x115, 0x177, 0x1ea, 0x2bb, 0x457))
    strict = Analyzer(analysis, investigations, relocations=relocations, services=services).run()
    serial = Analyzer(analysis, investigations, relocations=relocations, services=services,
                      intact_stack=True, irq_mode='disabled').run()
    root_states = {entry: State.havoc() for entry in roots}
    for state in root_states.values():
        state.sp = 0
        state.shadow = ZERO
    if component == 'main':
        dos = State(polluted=True)
        dos.regs.update(cs=val(('reloc', 0)), ds=val(('PSP',)),
                        es=val(('PSP',)), ss=val(('reloc', 0x143e)))
        root_states[0] = dos
        for installation in installations:
            if installation['target_image'] != 'main': continue
            entry = installation['offset']
            if installation.get('kind') != 'far_mouse_callback':
                handler = State(polluted=True, iff=ZERO)
                handler.regs['cs'] = val(('reloc', 0))
                handler.slots = {0: Slot(), 2: Slot(), 4: Slot(flags(TOP, ONE))}
                # Critical-error INT24 is a synchronous DOS callback, not a
                # hardware IRQ. Its interrupted IF is consequently unspecified.
                if installation.get('vector') == 0x24:
                    handler.slots[4] = Slot(flags(TOP, TOP))
                root_states[entry] = handler
        # Installed dynamic INT3 and transformed INT1 are not regular maskable
        # IRQs. INT1 plaintext is outside analyze() and stays an explicit seam.
        root_states[0xdb3] = State(iff=ZERO, polluted=True)
        root_states[0xdff] = State(iff=ZERO, polluted=True)
    else:
        entry = 0x182 if component == 'pcspeaker' else 0
        root_states[entry].iff = ZERO
        root_states[entry].regs['cs'] = val(('component-CS', component))
    aggregate, _ = strict.project(root_states)
    model, entry_inputs = serial.project(root_states)
    open_control = bool(analysis.get('unresolved')) or bool(strict.events)
    top = state_json(State.havoc())
    import json
    pool, interned = {}, {}

    def intern(s):
        encoded = json.dumps(s, sort_keys=True, separators=(',', ':'))
        if encoded not in interned:
            key = f'S{len(pool):05d}'
            interned[encoded], pool[key] = key, s
        return interned[encoded]

    rows = {}
    for p, ins in sorted(strict.instructions.items()):
        rows[f'{p:04X}'] = dict(instruction=ins['mnemonic'] + ' ' + ins.get('operands', ''),
            REP_internal_IRQ_boundaries=ins['mnemonic'].startswith(('rep ', 'repe ', 'repne ')),
            whole_machine=intern(top if open_control else state_json(aggregate.get(p, State.havoc()))),
            decoded_concurrent=intern(state_json(aggregate.get(p, State.havoc()))),
            serial_intact_saves=intern(state_json(model.get(p, State.havoc()))))
    local = {}
    interesting = investigations
    for entry in sorted(interesting):
        local[f'{entry:04X}'] = {f'{p:04X}': intern(state_json(s)) for (e, p), s in sorted(serial.states.items()) if e == entry}
    return dict(schema='flowstate-v1', component=component, image_sha256=sha(image),
        inputs={str(path.relative_to(ROOT)).replace('\\', '/'): sha(path.read_bytes())
                for path in [ROOT/'tools/flowstate.py', ROOT/'tools/explore.py',
                             ROOT/'metadata/hints.json', ROOT/'metadata/legacy-seeds.json',
                             ROOT/'metadata/interrupt-evidence.json', ROOT/'metadata/sound-hints.json',
                             ROOT/'metadata/control-frontier.json', ROOT/'metadata/protection-cfg.json']},
        decoded_CFG_sha256=sha(json.dumps(analysis, sort_keys=True, separators=(',', ':')).encode()),
        semantics=dict(arithmetic='16-bit offsets modulo 65536; no flat segment equality assumed',
            DOS_entry='CS=load,DS=ES=PSP,SS=load+143E,SP=4AF4; DF/IF unspecified by footer',
            whole_machine='TOP when unclosed control/providers/code or frame aliases admit arbitrary reentry',
            decoded_concurrent='decoded CFG only; may-IRQ havocs state, including nested/provider/frame effects',
            serial_intact_saves='conditional: fixed decoded instructions/known edges, no asynchronous IRQ, non-stack writes do not alias live saves',
            services='undeclared INT havocs registers/segments/DF/IF/SS/SP/saves; no implicit preservation',
            root_SP='DOS absolute 4AF4 is known at entry only; propagated SP is relative to each procedure entry, never a startup-wide stack-depth certificate',
            procedure_states='symbolic per-entry inputs, not proof that an entry is reached',
            stack='word slots modulo16; unproved word-at-FFFF physical overlap is overapproximated',
            target_domain_complete=False),
        service_declarations={f'{p:04X}': d for p, d in sorted((services or {}).items())},
        roots=[f'{p:04X}' for p in sorted(roots)], installations=installations,
        unavailable_execution_views=(['metadata/protection-cfg.json: TF-on/off stream and INT1 plaintext; not raw-CFG successors'] if component == 'main' else []),
        root_states={f'{p:04X}': state_json(s) for p, s in sorted(root_states.items())},
        serial_entry_inputs={f'{p:04X}': state_json(s) for p, s in sorted(entry_inputs.items())},
        frontiers=analysis.get('unresolved', []), target_domain_complete=False,
        work=dict(concurrent_steps=strict.steps, serial_steps=serial.steps,
                  concurrent_contexts=len(strict.states), serial_contexts=len(serial.states)),
        events=[dict(address=f'{p:04X}', kind=k) for p, k in sorted(strict.events | serial.events)],
        states=pool, instructions=rows, entry_relative=local)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('address', nargs='?', help='hex address or ledger name (main)')
    parser.add_argument('--component', choices=('main', 'adlib', 'tandysnd', 'pcspeaker'), default='main')
    parser.add_argument('--entry', action='append', default=[], help='additional symbolic entry (hex)')
    parser.add_argument('--services', type=str, help='JSON site -> declared intact-IRET transformer')
    parser.add_argument('--output', type=str, default=str(BUILD/'flowstate.json'))
    args = parser.parse_args()
    services = {int(k, 16): v for k, v in read_json(args.services).items()} if args.services else None
    analysis, image, relocations = load_component(args.component)
    result = report(analysis, image, relocations, component=args.component, services=services,
                    entries=[int(p, 16) for p in args.entry])
    write_json(args.output, result)
    if args.address:
        from where import address
        p = address(args.address) if args.component == 'main' else int(args.address, 16)
        key = f'{p:04X}'
        import json
        found = dict(result['instructions'].get(key, {'state': 'undecoded/unknown'}))
        for scope in ('whole_machine', 'decoded_concurrent', 'serial_intact_saves'):
            if scope in found: found[scope] = result['states'][found[scope]]
        print(json.dumps(dict(address=key, **found), indent=2))
        # Local contexts retain which saved entry word supplies a POP.
        for entry, states in result['entry_relative'].items():
            if key in states:
                print('entry', entry, json.dumps(result['states'][states[key]], sort_keys=True))
    else:
        print(args.output, result['work'], 'target_domain_complete=false')


if __name__ == '__main__':
    main()

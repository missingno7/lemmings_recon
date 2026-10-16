"""Bounded original/native tests for the connected input polling routines."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tools')]

import verification as base
import port_io as port
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json
from unicorn import UC_HOOK_INTR

SIZE, MASK, FLAGS = base.SIZE, base.MASK, base.FLAGS
IMAGE, LOADS = base.IMAGE, base.LOADS
REGS, IDS, Regs, MEM = base.REG_NAMES, base.REG_IDS, base.Regs, base.MEM
physical, put16, get16 = base.physical, base.put16, base.get16
check, require, Mismatch, Failure = base.check, base.require, base.Mismatch, base.OracleFailure

START = {'input': 0x418C, 'mouse': 0x4252}
OUTER = {'keyboard': 0x4251, 'mouse': 0x42A0, 'callback': 0x4333}
INPUT = {i.address: i for i in base.MD.disasm(IMAGE[0x418C:0x4334], 0x418C)}
MOUSE = {i.address: i for i in base.MD.disasm(IMAGE[0x4252:0x42A1], 0x4252)}
PORT = {at: ins for at, ins in port.INS.items() if at >= 0x4334}
INS = INPUT | MOUSE | PORT

EDGES = base.direct_jump_edges(INS)

MAX_STEPS, MAX_EVENTS, SECONDS, MEMORY_MIB = 100_000, 10_000, 420, 384
REPORT = BUILD / 'input-poll-differential.json'
ORIGINAL = BUILD / 'input-poll-original-differential.json'


class Result(ct.Structure):
    _fields_ = [('registers', Regs), ('status', ct.c_uint16), ('service_status', ct.c_uint16)]


INT33, Service = base.INTERRUPT, base.InterruptService


def u16(value):
    return value & 0xFFFF


def s16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def signed_clamp(value, low, high):
    value = u16(value)
    return low if s16(value) <= low else high if s16(value) > high else value


def cases():
    rows = [
        dict(name='mouse-default', entry='mouse'),
        dict(name='mouse-x-low-y-low', entry='mouse', mouse_x=0xFFFF, mouse_y=7),
        dict(name='mouse-x-high-y-high', entry='mouse', mouse_x=0x0149, mouse_y=0x00C9),
        dict(name='mouse-clamp-boundaries', entry='mouse', mouse_x=0x0148, mouse_y=0x00C8),
        dict(name='mouse-suppress-exact-ff', entry='mouse', suppression=0xFF),
        dict(name='mouse-saved-frame-registers', entry='mouse', saved_bx=0xBEEF,
             saved_dx=0xD00D, saved_ds=0x4100, saved_es=0x4567),
        dict(name='mouse-service-stop', entry='mouse', service_status=0x1357, expected=2),
        dict(name='mouse-unbound-vector', entry='mouse', no_service=True, expected=1),
        dict(name='mouse-vector-mismatch', entry='mouse', vector_ip=0x0222, expected=1),
        dict(name='mouse-changed-iret-ip', entry='mouse', nested_ip=0xD123, expected=3),
        dict(name='mouse-changed-iret-cs', entry='mouse', nested_cs=0x7123, expected=3),
        dict(name='mouse-normalized-iret-flags', entry='mouse', provider_flags=0x8000),
        dict(name='mouse-moved-stack', entry='mouse', new_stack=(0x6500, 0x6000),
             saved_ds=0x4100, saved_es=0x4567, saved_bx=0xBEEF),
        dict(name='mouse-int-frame-ivt-alias', entry='mouse', ss=0, sp=0x00E6, expected=1),
        dict(name='mouse-offset-wrap', entry='mouse', ss=0x5000, sp=0x0003),
        dict(name='mouse-physical-wrap', entry='mouse', ss=0xFFFF, sp=0x0003),
        dict(name='mouse-ds-ss-data-stack-alias', entry='mouse', ss=0x3000, ds=0x3000, sp=0x0024),
        dict(name='mouse-df-if', entry='mouse', flags=0x06D7),
    ]

    # Every input mode selects a distinct entry or the keyboard default path.
    rows += [
        dict(name='mode-zero-mouse', entry='input', mode=0),
        dict(name='mode-one-low-callback', entry='input', mode=1, callback=0x4334,
             port_kind='low', samples=(1, 0), buttons=0xCF),
        dict(name='mode-one-high-callback', entry='input', mode=1, callback=0x4359,
             port_kind='high', samples=(4, 0), buttons=0x3F),
        dict(name='mode-one-mouse-callback', entry='input', mode=1, callback=0x4252),
        dict(name='mode-one-high-dl-ff', entry='input', mode=1, callback=0x4359,
             dx=0x12FF, port_kind='high', buttons=0x3F),
        dict(name='mode-one-unknown-callback', entry='input', mode=1, callback=0x4111,
             expected=6),
        dict(name='mode-one-ff-dl-dh-preserved', entry='input', mode=1, callback=0x4334,
             dx=0x12FF, port_kind='low', buttons=0x3F),
        dict(name='mode-one-missing-out', entry='input', mode=1, callback=0x4334,
             port_kind='low', missing_out=True, expected=5, expected_service=1,
             missing_port_status=5, missing_service_status=1),
        dict(name='mode-one-missing-in', entry='input', mode=1, callback=0x4334,
             port_kind='low', samples=(1, 0), missing_in=True, expected=5, expected_service=1,
             missing_port_status=5, missing_service_status=1),
        dict(name='mode-one-changed-measure-ret', entry='input', mode=1, callback=0x4334,
             port_kind='low', samples=(1, 0), port_change='measure-ret',
             expected=5, expected_service=2),
        dict(name='mode-one-changed-callback-ret', entry='input', mode=1, callback=0x4334,
             port_kind='low', samples=(1, 0), port_change='callback-ret', expected=4),
    ]

    # Keyboard mask groups: no direction, each signed direction and both button bits.
    for i, keymask in enumerate((0, 0x401, 0x802, 0x1004, 0x2008,
                                 0x401 | 0x802, 0x1004 | 0x2008,
                                 0x1FC7, 0x4000, 0x0010, 0x4010)):
        rows.append(dict(name=f'keyboard-mask-{keymask:04x}', entry='input', mode=2,
                         keymask=keymask, accel_x=(0x10 + i), accel_y=(0x10 - min(i, 8))))
    rows += [
        dict(name='keyboard-ff-default', entry='input', mode=0xFF, keymask=0x4010,
             accel_x=0, accel_y=0, base_x=0xFFFF, base_y=0xFFFF),
        dict(name='keyboard-accel-lower-clamp', entry='input', mode=2,
             keymask=0x1004 | 0x401, accel_x=0, accel_y=0, base_x=8, base_y=8),
        dict(name='keyboard-accel-upper-clamp', entry='input', mode=2,
             keymask=0x2008 | 0x802, accel_x=0x20, accel_y=0x20,
             base_x=0x0148, base_y=0x00C8),
        dict(name='keyboard-ds-ss-alias', entry='input', mode=0xFF,
             ds=0x3000, ss=0x3000, sp=0x0018, keymask=0x4010),
        dict(name='keyboard-flags-wrap', entry='input', mode=2, flags=0x06D7,
             keymask=0x2008 | 0x802, accel_x=0xFFFF, accel_y=0xFFFF,
             base_x=0xFFF8, base_y=0xFFF8),
    ]

    # Axis dead-zone boundaries and signed scale paths through real callbacks.
    for scale in range(6):
        rows.append(dict(name=f'calibration-scale-{scale}', entry='input', mode=1,
                         callback=0x4334, port_kind='low', samples=(3, 3, 3, 0),
                         buttons=0xFF, scale=scale, base_x=0x0018, base_y=0x0010,
                         baseline_x=0x0018, baseline_y=0x0010))
    for base_x in (8, 9):
        rows.append(dict(name=f'calibration-deadzone-neg-{base_x}', entry='input', mode=1,
                         callback=0x4334, port_kind='low', samples=(0,), buttons=0xFF,
                         scale=2, base_x=8, base_y=8, baseline_x=base_x, baseline_y=8))
    for base_x in (0xFFF8, 0xFFF7):
        rows.append(dict(name=f'calibration-deadzone-pos-{base_x:04x}', entry='input', mode=1,
                         callback=0x4334, port_kind='low', samples=(0,), buttons=0xFF,
                         scale=3, base_x=8, base_y=8, baseline_x=base_x, baseline_y=8))
    rows += [
        dict(name='calibration-signed-sar-mutant', entry='input', mode=1, callback=0x4334,
             port_kind='low', samples=(0,), buttons=0xFF, scale=2,
             base_x=8, base_y=8, baseline_x=9, baseline_y=8),
        dict(name='calibration-y-lower-clamp', entry='input', mode=1, callback=0x4334,
             port_kind='low', samples=(0,), buttons=0xFF, scale=4,
             base_x=8, base_y=8, baseline_x=8, baseline_y=9),
        dict(name='calibration-asymmetric-xy', entry='input', mode=1, callback=0x4359,
             port_kind='high', samples=(0x0C, 0x04, 0), buttons=0xFF, scale=4,
             base_x=0x20, base_y=0x30, baseline_x=0x30, baseline_y=0x20),
        dict(name='calibration-upper-clamps', entry='input', mode=1, callback=0x4334,
             port_kind='low', samples=(0,), buttons=0xFF, scale=4,
             base_x=0x148, base_y=0xC8, baseline_x=0xFFF7, baseline_y=0xFFF7),
        dict(name='callback-dl-skip-vs-full-dx', entry='input', mode=1, callback=0x4334,
             port_kind='low', dx=0x12FF, buttons=0xCF, base_x=0x80, base_y=0x80,
             baseline_x=0x40, baseline_y=0x40),
        dict(name='input-load-1010', entry='input', mode=2, load=0x1010),
        dict(name='input-load-1213', entry='input', mode=2, load=0x1213),
        dict(name='input-load-2345', entry='input', mode=2, load=0x2345),
    ]
    return [dict(load=0x1010, seed=0x418C + i) | c for i, c in enumerate(rows)]


class Access(port.Access):
    """Reuse port_io's live-byte provider and add the outer callback seam."""
    def __init__(self, c, memory, registers, device):
        port_case = dict(c)
        port_case['kind'] = c.get('port_kind', 'low')
        # Provider stack edits below use the composed parent's actual frame offsets.
        port_case.pop('provider', None)
        super().__init__(port_case, memory, registers, device)
        self.max_events = MAX_EVENTS
        self.service_events = []

    def out(self, port_number, value, flags, mask=FLAGS):
        super().out(port_number, value, flags, mask)
        change = self.c.get('port_change')
        if change and change not in self.providers:
            if change == 'measure-ret':
                # Parent push DX, CALL AX, then child CALL MeasurePort201Axes.
                delta = 6 if self.c['entry'] == 'input' else 2
            elif change == 'callback-ret':
                # Change the actual CALL AX return word at 42A7.
                delta = 4
            else:
                raise Failure('unknown declared callback stack provider')
            self.patch(self.r['ss'], (self.r['sp'] - delta) & 0xFFFF,
                       0xD234, change)


def _outer(machine, off):
    c = machine.c
    if c['entry'] == 'mouse':
        return off == 0x42A0
    mode = c.get('mode', 0)
    ret = 0x42A0 if mode == 0 else 0x4333 if mode == 1 else 0x4251
    return off == ret


def _before(machine, ins):
    c = machine.c
    if ins.address == 0x42A5:
        target = machine.state()['ax']
        if target not in (0x4252, 0x4334, 0x4359):
            machine.stop(6)
            return True
        machine.callback_target = target
    return False


def _change_return(machine, off):
    mapping = {0x43CD: (5, 2), 0x42A0: (4, 0),
               0x4358: (4, 0), 0x4385: (4, 0)}
    return mapping


class Machine(base.OriginalMachine):
    def __init__(self, c, memory, registers, device, core):
        self.callback_target = None
        self.binding = (0x7100, 0x0200)
        access = Access(c, memory, registers, device)
        def interrupt(machine, number):
            check(number == 0x33, 'unexpected software interrupt in input domain')
            provider = None if c.get('no_service') else external
            machine.software_interrupt(0x33, 0x4261, self.binding, provider)
        super().__init__(c, memory, registers, device, core, instructions=INS,
                         access=access, outer_returns=_outer,
                         child_returns={0x42A0: {0x42A7}, 0x4358: {0x42A7},
                                        0x4385: {0x42A7},
                                        0x43CD: {0x4341, 0x4366}},
                         max_steps=MAX_STEPS,
                         changed_return_status=_change_return(self, 0),
                         before=_before, interrupt=interrupt)
        self.binding = (0x7100, 0x0200)

    def run(self):
        result = super().run()
        result['service_status'] = self.service_status
        result['services'] = self.access.service_events
        result['transport_events'] = self.access.transport_events
        result['service_calls'] = len(self.access.service_events)
        result['provider_events'] = sum(item['provider_events'] for item in self.access.service_events)
        return result


def external(access, r):
    """Construct only the declared INT33 provider and its live interrupt frame."""
    c = access.c
    if c.get('no_service'):
        return 0
    start = len(access.events)
    frame = [get16(access.memory, r['ss'], (r['sp'] + 2 * i) & 0xFFFF)
             for i in range(13)]
    access.service_events.append({'entry': dict(r), 'frame': frame})
    r.update(ax=0xA1B2, bx=c.get('mouse_buttons', 0xA55A),
             cx=c.get('mouse_x', 0x0060), dx=c.get('mouse_y', 0x0030),
             si=0x1A2B, di=0x3C4D, bp=0x5E6F,
             ds=c.get('provider_ds', r['ds']), es=c.get('provider_es', r['es']))
    if 'provider_flags' in c:
        r['flags'] = c['provider_flags']
    if c.get('new_stack'):
        new_ss, new_sp = c['new_stack']
        count = 16 if c['entry'] == 'input' and c.get('mode') == 1 else 14
        words = [get16(access.memory, r['ss'], (r['sp'] + 2 * i) & 0xFFFF)
                 for i in range(count)]
        r['ss'], r['sp'] = new_ss, new_sp
        for index, word in enumerate(words):
            access.word_write(r['ss'], (r['sp'] + 2 * index) & 0xFFFF,
                              word, r['flags'])
    changes = {0: c.get('nested_ip'), 2: c.get('nested_cs'),
               4: c.get('provider_flags'), 6: c.get('saved_ds'),
               8: c.get('saved_dx'), 10: c.get('saved_cx'),
               12: c.get('saved_bx'), 14: c.get('saved_ax'),
               16: c.get('saved_di'), 18: c.get('saved_si'),
               20: c.get('saved_bp'), 22: c.get('saved_ds_entry'),
               24: c.get('saved_es')}
    for offset, value in changes.items():
        if value is not None:
            access.word_write(r['ss'], (r['sp'] + offset) & 0xFFFF,
                              value, r['flags'])
    status = c.get('service_status', 0)
    access.service_events[-1]['before_iret'] = dict(r)
    access.service_events[-1]['status'] = status
    access.service_events[-1]['provider_events'] = len(access.events) - start
    return status


def setup(c):
    memory, device = base.initial_memory(c)
    load = c['load']
    regs = base.default_regs(load, c['seed'], ss=c.get('ss', 0x5000),
                             sp=c.get('sp', 0x9000), ds=c.get('ds', 0x3000),
                             flags=c.get('flags', 0x00D7))
    regs.update(ax=0xA53E, bx=0x1111, cx=0x2222, dx=c.get('dx', 0x1234),
                si=0x3333, di=0x4444, bp=0x5555,
                ip=START[c['entry']])
    regs['flags'] = (regs['flags'] & 0x7ED5) | 2
    ds = regs['ds']
    put16(memory, ds, 0x0010, c.get('base_x', 0x0060), device)
    put16(memory, ds, 0x0012, c.get('base_y', 0x0030), device)
    put16(memory, ds, 0x0014, c.get('buttons_initial', 0xBEEF), device)
    put16(memory, ds, 0x0016, c.get('accel_x', 0x0010), device)
    put16(memory, ds, 0x0018, c.get('accel_y', 0x0010), device)
    put16(memory, ds, 0x1FC7, c.get('keymask', 0), device)
    put16(memory, ds, 0x200B, c.get('suppression', 0), device)
    put16(memory, ds, 0x2005, c.get('scale', 0), device)
    put16(memory, ds, 0x25A0, c.get('callback', 0x4334), device)
    put16(memory, ds, 0x25A2, c.get('baseline_x', 0x0060), device)
    put16(memory, ds, 0x25A4, c.get('baseline_y', 0x0030), device)
    memory[physical(ds, 0x25A6)] = c.get('mode', 2)
    put16(memory, regs['ss'], regs['sp'], c.get('outer_word', 0xD00D), device)
    vector = (c.get('vector_cs', 0x7100), c.get('vector_ip', 0x0200))
    put16(memory, 0, 0xCC, vector[1], device)
    put16(memory, 0, 0xCE, vector[0], device)
    return memory, regs, device, (0x7100, 0x0200)


def _copy_saved_stack(access, r, count, new_ss, new_sp):
    words = [get16(access.memory, r['ss'], (r['sp'] + 2 * i) & 0xFFFF)
             for i in range(count)]
    r['ss'], r['sp'] = new_ss, new_sp
    for index, word in enumerate(words):
        access.word_write(r['ss'], (r['sp'] + 2 * index) & 0xFFFF,
                          word, r['flags'])


def _keyboard_expected(c, memory, r):
    ds = r['ds']
    bx = get16(memory, ds, 0x16)
    cx = get16(memory, ds, 0x18)
    ax = get16(memory, ds, 0x1FC7)
    if not (ax & 0x0C03):
        cx = 0x10
    else:
        if ax & 0x0401:
            cx = u16(cx - 1)
            if s16(cx) < 0:
                cx = 0
        if ax & 0x0802:
            cx = u16(cx + 1)
            if s16(cx) > 0x20:
                cx = 0x20
    if not (ax & 0x300C):
        bx = 0x10
    else:
        if ax & 0x1004:
            bx = u16(bx - 1)
            if s16(bx) < 0:
                bx = 0
        if ax & 0x2008:
            bx = u16(bx + 1)
            if s16(bx) > 0x20:
                bx = 0x20
    bx, cx = u16(bx), u16(cx)
    x_delta = u16((bx >> 2) - 4)
    y_delta = u16((cx >> 2) - 4)
    x_value = signed_clamp(get16(memory, ds, 0x10) + x_delta, 8, 0x148)
    y_value = signed_clamp(get16(memory, ds, 0x12) + y_delta, 8, 0xC8)
    buttons = 1 if (ax & 0x4010) else 0
    return bx, cx, x_value, y_value, buttons


def _mouse_expected(c, memory, r):
    ds = c.get('saved_ds', r['ds'])
    x_value = signed_clamp(c.get('mouse_x', 0x60), 8, 0x148)
    y_value = signed_clamp(c.get('mouse_y', 0x30), 8, 0xC8)
    buttons = get16(memory, ds, 0x14)
    if c.get('suppression', 0) != 0xFF:
        buttons = c.get('mouse_buttons', 0xA55A)
    return ds, x_value, y_value, buttons


def _sar(value, count):
    return u16(s16(value) >> count)


def _calibration_expected(c, memory, r, bx, cx):
    ds = r['ds']
    x_value = get16(memory, ds, 0x10)
    y_value = get16(memory, ds, 0x12)
    baseline_x = get16(memory, ds, 0x25A2)
    baseline_y = get16(memory, ds, 0x25A4)
    selector = memory[physical(ds, 0x2005)]
    x_shifts = {2: 5, 3: 3, 4: 2}.get(selector, 6)
    y_shifts = {2: 4, 3: 2, 4: 1}.get(selector, 5)
    delta_x = u16(bx - baseline_x)
    delta_y = u16(cx - baseline_y)
    if s16(delta_x) < -8 or s16(delta_x) > 8:
        delta_x = _sar(delta_x, x_shifts)
        x_value = signed_clamp(x_value + delta_x, 8, 0x148)
    if s16(delta_y) < -8 or s16(delta_y) > 8:
        delta_y = _sar(delta_y, y_shifts)
        y_value = signed_clamp(y_value + delta_y, 8, 0xC8)
    return x_value, y_value


def _port_expected(c, memory, r):
    kind = c.get('port_kind', 'low')
    dx = c.get('dx', 0x1234)
    takes = (dx & 0xFF) != 0xFF
    samples = list(c.get('samples', (15, 0))) if takes else []
    mask = 3 if kind == 'low' else 12
    totals = [0, 0, 0, 0]
    consumed = 0
    if takes:
        for index, value in enumerate(samples):
            if index == 0 and 'new_mask' in c:
                mask = c['new_mask']
            masked = value & mask
            consumed += 1
            for axis in range(4):
                if masked & (1 << axis):
                    totals[axis] = (totals[axis] + (2 if axis in (1, 3) else 1)) & 0xFFFF
            if not masked:
                break
        else:
            raise Failure('independent port sequence did not terminate')
    buttons_in = c.get('buttons', 0xCF)
    button = ((~buttons_in) >> (4 if kind == 'low' else 6)) & 3
    return dict(button=button, totals=totals, consumed=consumed + 1,
                takes=takes, kind=kind)


def independent(c, memory, r, ref, core):
    check(ref['status'] == c.get('expected', 0), c['name'] + ': stop status differs')
    check(ref['service_status'] == c.get('expected_service', c.get('service_status', 0)),
          c['name'] + ': service status differs')
    if ref['status'] != 0:
        return
    out = ref['regs']
    mode = c.get('mode', 0) if c['entry'] == 'input' else None
    mouse_path = c['entry'] == 'mouse' or mode == 0
    mouse_callback = c['entry'] == 'input' and mode == 1 and c.get('callback') == 0x4252
    keyboard_path = c['entry'] == 'input' and mode not in (0, 1)
    port_path = c['entry'] == 'input' and mode == 1 and c.get('callback') in (0x4334, 0x4359)
    if mouse_path:
        ds, x_value, y_value, buttons = _mouse_expected(c, memory, r)
        check(get16(ref['memory'], ds, 0x10) == x_value,
              c['name'] + ': independent mouse X clamp differs')
        check(get16(ref['memory'], ds, 0x12) == y_value,
              c['name'] + ': independent mouse Y clamp differs')
        check(get16(ref['memory'], ds, 0x14) == buttons,
              c['name'] + ': independent mouse button/suppression differs')
    if mouse_callback:
        ds, _, _, buttons = _mouse_expected(c, memory, r)
        check(get16(ref['memory'], ds, 0x14) == buttons,
              c['name'] + ': independent callback mouse buttons differ')
        x_value, y_value = _calibration_expected(c, memory, r, r['bx'], r['cx'])
        check(get16(ref['memory'], ds, 0x10) == x_value and
              get16(ref['memory'], ds, 0x12) == y_value,
              c['name'] + ': independent callback mouse calibration differs')
    elif keyboard_path:
        bx, cx, x_value, y_value, buttons = _keyboard_expected(c, memory, r)
        ds = r['ds']
        check(get16(ref['memory'], ds, 0x16) == bx and get16(ref['memory'], ds, 0x18) == cx,
              c['name'] + ': independent keyboard acceleration steps differ')
        check(get16(ref['memory'], ds, 0x10) == x_value and get16(ref['memory'], ds, 0x12) == y_value,
              c['name'] + ': independent keyboard signed clamp differs')
        check(get16(ref['memory'], ds, 0x14) == buttons,
              c['name'] + ': independent keyboard button group differs')
    elif port_path:
        expected = _port_expected(c, memory, r)
        ds = r['ds']
        check(get16(ref['memory'], ds, 0x14) == expected['button'],
              c['name'] + ': independent port button bits differ')
        check(ref['cursor'] == expected['consumed'],
              c['name'] + ': independent port sample count differs')
        if expected['takes']:
            totals = expected['totals']
            if expected['kind'] == 'low':
                bx, cx = totals[0], _sar(totals[1], 1)
            else:
                bx, cx = totals[2], _sar(totals[3], 1)
        else:
            bx, cx = r['bx'], r['cx']
        if c.get('dx', 0x1234) & 0xFF == 0xFF:
            x_value, y_value = get16(memory, ds, 0x10), get16(memory, ds, 0x12)
        else:
            x_value, y_value = _calibration_expected(c, memory, r, bx, cx)
        check(get16(ref['memory'], ds, 0x10) == x_value and
              get16(ref['memory'], ds, 0x12) == y_value,
              c['name'] + ': independent callback calibration differs')

    outer_ss, outer_sp = r['ss'], r['sp']
    if c.get('new_stack') and (c['entry'] == 'mouse' or mode == 0 or mouse_callback):
        outer_ss, frame_sp = c['new_stack']
        outer_sp = u16(frame_sp + (30 if mouse_callback else 26))
    if core:
        ret = 0x42A0 if mouse_path else OUTER['callback'] if mode == 1 else OUTER['keyboard']
        check(out['ip'] == ret and out['ss'] == outer_ss and out['sp'] == outer_sp,
              c['name'] + ': core RET boundary differs')
    else:
        ret = 0x42A0 if mouse_path else OUTER['callback'] if mode == 1 else OUTER['keyboard']
        check(out['sp'] == u16(outer_sp + 2) and out['ss'] == outer_ss,
              c['name'] + ': adapter SP differs')
        check(out['ip'] == get16(ref['memory'], outer_ss, outer_sp),
              c['name'] + ': live outer RET differs')
        check(ret in (0x4251, 0x42A0, 0x4333), 'invalid independent outer return')


def compare(native, c, core, reference=None):
    memory, regs, device, binding = setup(c)
    if reference is None:
        machine = Machine(c, bytearray(memory), regs, copy.deepcopy(device), core)
        reference = machine.run()
        independent(c, memory, regs, reference, core)
    if native:
        actual = native.run(c, bytearray(memory), regs, copy.deepcopy(device), binding, core)
        base.compare_states(c['name'], actual, reference)
    return reference


def hashes():
    paths = (
        'AGENTS.md', 'assets/vgalemmi.exe', 'metadata/oracle.json',
        'metadata/inputs.json', 'metadata/toolchain-lock.json',
        'docs/executable.md', 'docs/port-io.md',
        'src/input_poll.asm', 'src/port201_input.asm',
        'c/input_poll.c', 'c/input_poll.h', 'c/port_io.c', 'c/port_io.h',
        'c/interrupt_service.c', 'c/interrupt_service.h',
        'c/lemmings_sym.h', 'c/aligned_read_mask.h', 'c/special_blit.h', 'c/regs.h',
        'tests/input_poll.py', 'tests/port_io.py', 'tests/verification.py',
        'tests/minimap_vga.py', 'tools/bounded_process.py', 'tools/cbuild.py',
        'tools/difftest.py', 'tools/common.py', 'tools/unpack.py',
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


class Native:
    def __init__(self, directory, mutation=0):
        self.lib = ct.CDLL(str(build(Path(directory) / f'input-poll-{mutation}.dll',
                                     mutation, 'input_poll')))
        self.functions = {}
        for entry, name in (('mouse', 'lmn_poll_mouse_position'),
                            ('input', 'lmn_poll_input_state')):
            for core in (True, False):
                fn = getattr(self.lib, name + ('_core' if core else '_adapter'))
                fn.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(Service),
                               ct.POINTER(base.Ports), ct.POINTER(base.Bus)]
                fn.restype = Result
                self.functions[entry, core] = fn

    def run(self, c, memory, regs, device, binding, core):
        access = Access(c, memory, regs, device)
        callbacks = base.NativeCallbacks(access, missing_in=c.get('missing_in'),
                                         missing_out=c.get('missing_out'))

        service_callback = callbacks.interrupt(external)
        service = Service(None, service_callback, *binding)
        ram = (ct.c_uint8 * SIZE).from_buffer(memory)
        entry_regs = Regs(**regs)
        result = self.functions[c['entry'], core](
            ram, ct.byref(entry_regs), None if c.get('no_service') else ct.byref(service),
            ct.byref(callbacks.ports), ct.byref(callbacks.bus))
        return dict(regs={name: getattr(result.registers, name) for name in REGS},
                    status=result.status, service_status=result.service_status,
                    memory=memory, device=device, events=access.events,
                    providers=access.providers, cursor=access.cursor,
                    services=access.service_events,
                    transport_events=access.transport_events,
                    service_calls=len(access.service_events),
                    provider_events=sum(item['provider_events'] for item in access.service_events))


def worker(directory=None, snapshot=None):
    before = hashes()
    if snapshot:
        check(before == json.loads(Path(snapshot).read_text()), 'input-poll input snapshot differs')
    native = Native(directory) if directory else None
    rows = []
    for c in cases():
        for core in (True, False):
            ref = compare(native, c, core)
            rows.append(dict(case=c['name'], entry=c['entry'], core=core,
                             status=ref['status'], service_status=ref['service_status'],
                             sites=sorted(ref['sites']), edges=sorted(ref['edges']),
                             steps=ref['steps'], events=len(ref['events']),
                             transport_events=ref['transport_events'],
                             service_calls=ref['service_calls'],
                             provider_events=ref['provider_events'], port_count=ref['cursor']))
        gc.collect()
        print('CHECKED ' + c['name'], flush=True)

    mutations = None
    if native:
        mutations = []
        lookup = {case['name']: case for case in cases()}
        witnesses = (
            (1, 'mouse-int-frame-ivt-alias'),
            (2, 'mouse-moved-stack'),
            (3, 'mouse-normalized-iret-flags'),
            (4, 'mode-one-unknown-callback'),
            (5, 'mode-one-changed-callback-ret'),
            (6, 'mode-one-ff-dl-dh-preserved'),
            (7, 'calibration-signed-sar-mutant'),
        )
        for number, name in witnesses:
            mutant = Native(directory, number)
            c = lookup[name]
            try:
                compare(mutant, c, True)
            except Mismatch as error:
                mutations.append(dict(mutation=number, case=name, core=True,
                                      completed=True, mismatch=str(error)))
            else:
                raise Failure(f'input_poll mutation {number} survived its witness')
            gc.collect()

    sites = {address for row in rows for address in row['sites']}
    edges = {tuple(edge) for row in rows for edge in row['edges']}
    expected_sites = set(INS)
    check(sites == expected_sites, f'instruction coverage differs: missing={sorted(expected_sites-sites)} extra={sorted(sites-expected_sites)}')
    check(edges == EDGES, f'branch coverage differs: missing={sorted(EDGES-edges)} extra={sorted(edges-EDGES)}')
    check(before == hashes(), 'input-poll campaign inputs changed during execution')
    report = dict(image='main', image_sha256=sha(IMAGE), connected_code_bytes=576,
                  input_parent_bytes=345, mouse_bytes=79, port_child_bytes=152,
                  case_count=len(cases()), comparison_count=len(rows),
                  executed_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
                  instruction_steps=sum(row['steps'] for row in rows),
                  ordered_events=sum(row['events'] for row in rows),
                  declared_transport_events=sum(row['transport_events'] for row in rows),
                  declared_provider_events=sum(row['provider_events'] for row in rows),
                  declared_service_calls=sum(row['service_calls'] for row in rows),
                  mutation_count=len(mutations or []), mutations=mutations or [], rows=rows,
                  input_hashes=before,
                  limits=dict(timeout_seconds=SECONDS, process_commit_mib=MEMORY_MIB,
                              instructions=MAX_STEPS, events=MAX_EVENTS),
                  scope='Connected input parent, mouse provider seam and port-201 callback children on constructed finite state; no game boot, asynchronous IRQ scheduling, or unsupported callback body')
    write_json(REPORT if native else ORIGINAL, report)
    print(f'PASS input poll: {len(rows)} comparisons, {len(sites)} sites, '
          f'{len(edges)} edges, {len(mutations or [])} mutants', flush=True)


def main():
    if sys.argv[1:] == ['--original-worker']:
        worker()
        return
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], sys.argv[3])
        return
    if sys.argv[1:] == ['--original-only']:
        run_bounded([sys.executable, __file__, '--original-worker'], cwd=ROOT,
                    timeout=SECONDS, memory_mib=MEMORY_MIB, check=True)
        return
    if sys.argv[1:]:
        raise SystemExit('usage: input_poll.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='input-poll-', parent=BUILD) as directory:
        snapshot = Path(directory) / 'input-hashes.json'
        snapshot.write_text(json.dumps(hashes(), sort_keys=True))
        run_bounded([sys.executable, __file__, '--worker', directory, str(snapshot)],
                    cwd=ROOT, timeout=SECONDS, memory_mib=MEMORY_MIB, check=True)


if __name__ == '__main__':
    main()

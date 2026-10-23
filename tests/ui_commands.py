"""Bounded tests for the connected foreground input-command/UI subsystem."""
import copy
import ctypes as ct
import gc
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tools')]

import verification as base
from bounded_process import run_bounded, temporary_build_directory
from cbuild import build
from common import BUILD, sha, write_json

SIZE, MASK, FLAGS = base.SIZE, base.MASK, base.FLAGS
IMAGE, LOADS = base.IMAGE, base.LOADS
REGS, IDS, Regs, MEM = base.REG_NAMES, base.REG_IDS, base.Regs, base.MEM
physical, put16, get16 = base.physical, base.put16, base.get16
put8 = base.put8
check, require, Mismatch, Failure = base.check, base.require, base.Mismatch, base.OracleFailure
INTERRUPT, Service = base.INTERRUPT, base.InterruptService

ENTRY = 0x3E6F
PARENT = ((0x3E6F, 0x3EE3), (0x3EE4, 0x3EED), (0x3EEE, 0x3F14),
          (0x3F15, 0x3F91), (0x3F92, 0x4085))
VIEW = ((0x410F, 0x414F),)
INS = {ins.address: ins for lo, hi in PARENT + VIEW
       for ins in base.MD.disasm(IMAGE[lo:hi], lo)}
STATIC_EDGES = base.direct_jump_edges(INS)
# In this synchronous caller BX=(origin>>4)+D0 is 208..4303. If the first
# JNL at 3FB0 falls through, AX < BX; after adding 24 it remains AX < BX.
# Thus 3FB7 always takes its target, and 3FB9/3FBC are not reachable.
INFEASIBLE_EDGES = {(0x3FB7, 0x3FB9), (0x3FBC, 0x3FE9), (0x3FBC, 0x3FBE)}
EXPECTED_EDGES = STATIC_EDGES - INFEASIBLE_EDGES
EXPECTED_SITES = set(INS) - {0x3FB9, 0x3FBC}
UNKNOWN = (0x3EE3, 0x3EED, 0x3F14, 0x3F91)

MAX_STEPS, MAX_EVENTS = 100_000, 10_000
SECONDS, MEMORY_MIB = 420, 384
REPORT = BUILD / 'ui-commands-differential.json'
ORIGINAL = BUILD / 'ui-commands-original-differential.json'

OUTER_RETS = {0x3FE8, 0x3FEE}
CHILD_RETS = {0x414E: {0x3FE1}}

OFF = {
    'origin_pixels': 0x0000, 'origin_bytes': 0x0002,
    'dirty_a': 0x0026, 'dirty_b': 0x0028,
    'update_gate': 0x002B, 'slot_bound': 0x0043,
    'creation_limit': 0x0047, 'creation_reload': 0x0049,
    'scan_request': 0x004B, 'release_min': 0x0064,
    'release': 0x0067, 'release_refresh': 0x0069,
    'panel_latch': 0x0062, 'action_selector': 0x0082,
    'status_refresh': 0x0084, 'scan': 0x1FD0,
    'fg_counter': 0x0052, 'toggle_snapshot': 0x0053,
    'action_counter': 0x1FD3, 'action_snapshot': 0x1FD4,
    'timer_chain': 0x1FCF, 'pointer_x': 0x0010,
    'pointer_y': 0x0012, 'buttons': 0x0014,
    'external_sound': 0x2010, 'sound_options': 0x25A7,
}


class UiResult(ct.Structure):
    _fields_ = [('registers', Regs), ('status', ct.c_uint16),
                ('service_status', ct.c_uint16)]


def u8(value):
    return value & 0xFF


def u16(value):
    return value & 0xFFFF


def s8(value):
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def s16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def put_data(memory, ds, name, value, device=None, word=False):
    if word:
        put16(memory, ds, OFF[name], value, device)
    else:
        put8(memory, ds, OFF[name], value)


def cases():
    rows = []
    # Every explicit keyboard selector, plus release actions and the two
    # byte-counter routes.
    for scan in range(0x3D, 0x45):
        rows.append(dict(name=f'scan-selector-{scan:02x}', scan=scan,
                         expected_selector=scan - 0x3B))
    rows += [
        dict(name='release-decrement', scan=0x3B, release=0x20, release_min=0x10),
        dict(name='release-min-equality', scan=0x3B, release=0x10, release_min=0x10),
        dict(name='release-below-minimum-wrap', scan=0x3B, release=0x05, release_min=0x10),
        dict(name='release-refresh-block', scan=0x3B, release=0x20,
             release_min=0x10, release_refresh=1),
        dict(name='release-increment', scan=0x3C, release=0x20),
        dict(name='release-increment-at-99', scan=0x3C, release=0x63),
        dict(name='release-increment-refresh-block', scan=0x3C, release=0x20,
             release_refresh=1),
        dict(name='toggle-counter-wrap-accepted', scan=0x4E, fg_counter=0x01,
             toggle_snapshot=0xFF, update_gate=0x35),
        dict(name='toggle-counter-wrap-rejected', scan=0x57, fg_counter=0x00,
             toggle_snapshot=0xFF, update_gate=0x35),
        dict(name='toggle-byte-delta-unsigned', scan=0x4E, fg_counter=0x01,
             toggle_snapshot=0x80, update_gate=0x35),
        dict(name='action-counter-signed-wrap', scan=0x58, action_counter=0x00,
             action_snapshot=0x01, entity_slot_bound=0x29),
        dict(name='action-counter-threshold-five', scan=0x53, action_counter=0x15,
             action_snapshot=0x10, entity_slot_bound=0x31),
        dict(name='action-counter-over-five', scan=0x58, action_counter=0x16,
             action_snapshot=0x10, entity_slot_bound=0x31),
        dict(name='action-counter-update-gate-ff', scan=0x53, update_gate=0xFF,
             action_counter=0x17, action_snapshot=0x10),
    ]

    # Default click path: button, signed coordinate gates, exact refresh/latch
    # sentinels, and the selector sub-actions.
    rows += [
        dict(name='click-no-primary-button', buttons=0xFFFE, panel_latch=0x32,
             outer_ret=0x3FE8),
        dict(name='click-y-below-threshold', buttons=1, pointer_y=0x00B7),
        dict(name='click-y-signed-wrap', buttons=1, pointer_y=0xFFF7),
        dict(name='click-y-threshold-exact', buttons=1, pointer_y=0x00B8,
             pointer_x=0x00A8),
        dict(name='click-pointer-index-zero-update-disabled', buttons=1,
             pointer_x=0x0008, pointer_y=0x00B8, update_gate=0xFF),
        dict(name='click-pointer-index-zero-release-decrease', buttons=1,
             pointer_x=0x0008, pointer_y=0x00B8, update_gate=0xFE,
             release=0x20, release_min=0x10),
        dict(name='click-pointer-index-one-release-increase', buttons=1,
             pointer_x=0x0018, pointer_y=0x00B8, release=0x20),
        dict(name='click-status-refresh-suppressed', buttons=1,
             pointer_x=0x00A8, pointer_y=0x00B8, status_refresh=1),
        dict(name='click-latch-exact-ff-suppressed', buttons=1,
             pointer_x=0x00A8, pointer_y=0x00B8, panel_latch=0xFF),
        dict(name='click-latch-fe-is-not-suppressed', buttons=1,
             pointer_x=0x00A8, pointer_y=0x00B8, panel_latch=0xFE,
             fg_counter=2, toggle_snapshot=0),
        dict(name='click-action-a-toggle', buttons=1, pointer_x=0x00A8,
             pointer_y=0x00B8, fg_counter=2, toggle_snapshot=0, update_gate=0x35),
        dict(name='click-action-b-reset', buttons=1, pointer_x=0x00B8,
             pointer_y=0x00B8, action_counter=0x12, action_snapshot=0x10,
             entity_slot_bound=0x24),
        dict(name='click-action-c-return', buttons=1, pointer_x=0x00C8,
             pointer_y=0x00B8, release=0x20),
        dict(name='click-action-default-selector', buttons=1, pointer_x=0x0028,
             pointer_y=0x00B8, external_sound=0, sound_options=0),
        dict(name='click-default-update-gate-exact-ff', buttons=1,
             pointer_x=0x0058, pointer_y=0x00B8, update_gate=0xFF),
        dict(name='click-default-update-gate-fe', buttons=1,
             pointer_x=0x0058, pointer_y=0x00B8, update_gate=0xFE,
             expected_selector=5),
        dict(name='scan-action-status-refresh-suppressed', scan=0x3D,
             status_refresh=1),
    ]

    # INT 61/60 gates and provider-returned full register/segment state.
    rows += [
        dict(name='action-sound-driver-disabled', scan=0x3D,
             external_sound=0x00, sound_options=0x00),
        dict(name='action-sound-bits-clear', scan=0x3D,
             external_sound=0xFF, sound_options=0),
        dict(name='action-int61-only', scan=0x3D,
             external_sound=0xFF, sound_options=0x02,
             service61={}),
        dict(name='action-int60-only', scan=0x3D,
             external_sound=0x00, sound_options=0x01,
             service60={}),
        dict(name='action-returned-ds-enables-int60', scan=0x3D,
             external_sound=0xFF, sound_options=0x01,
             service61={'new_ds': 0x3600}, service60={},
             returned_data=(0x3600, 0x00, 0x01)),
        dict(name='action-returned-ds-suppresses-int60', scan=0x3D,
             external_sound=0x00, sound_options=0x01,
             service60={'new_ds': 0x3600},
             returned_data=(0x3600, 0xFF, 0x00)),
        dict(name='action-int61-unbound', scan=0x3D,
             external_sound=0xFF, sound_options=0x02, no_service61=True,
             expected_status=1),
        dict(name='action-int60-unbound', scan=0x3D,
             external_sound=0x00, sound_options=0x01, no_service60=True,
             expected_status=1),
        dict(name='action-int61-provider-stop', scan=0x3D,
             external_sound=0xFF, sound_options=0x02,
             service61={'status': 0x1357}, expected_status=2,
             expected_service_status=0x1357),
        dict(name='action-int60-provider-stop', scan=0x3D,
             external_sound=0x00, sound_options=0x01,
             service60={'status': 0x2468}, expected_status=2,
             expected_service_status=0x2468),
        dict(name='action-int61-changed-iret', scan=0x3D,
             external_sound=0xFF, sound_options=0x02,
             service61={'iret_ip': 0xD123}, expected_status=3),
        dict(name='action-int60-changed-iret', scan=0x3D,
             external_sound=0x00, sound_options=0x01,
             service60={'iret_cs': 0x7123}, expected_status=3),
        dict(name='action-int61-moved-stack-and-ds', scan=0x3D,
             external_sound=0xFF, sound_options=0x02,
             service61={'new_ds': 0x3600, 'new_stack': (0x6500, 0x7000)},
             returned_data=(0x3600, 0xFF, 0x00)),
        dict(name='action-int61-normalizes-saved-flags', scan=0x3D,
             external_sound=0xFF, sound_options=0x02,
             service61={'saved_flags': 0x8000}),
        dict(name='action-int61-frame-overwrites-ivt', scan=0x3D,
             external_sound=0xFF, sound_options=0x02,
             ss=0, sp=0x018A, expected_status=1),
        dict(name='action-int61-frame-overwrites-live-gate', scan=0x3D,
             external_sound=0xFF, sound_options=0x01,
             ss=0x3000, ds=0x3000, sp=0x2016, service61={}, service60={}),
        dict(name='action-int61-word-stack-wrap', scan=0x3D,
             external_sound=0xFF, sound_options=0x02,
             ss=0xFFFF, sp=0x0003, service61={}),
    ]

    # Scroll path and actual child integration, including live operand and
    # child-return aliases. Origin values exercise both signed clamps and DF.
    rows += [
        dict(name='scroll-lower-clamp-and-child', buttons=1, pointer_x=0x00E0,
             pointer_y=0x00B8, origin_pixels=0, marker_a=0x42, marker_b=0x57,
             scroll_expect=(0x0010, 0x0002)),
        dict(name='scroll-upper-clamp-and-child', buttons=1, pointer_x=0x0140,
             pointer_y=0x00B8, origin_pixels=0, marker_a=0x42, marker_b=0x57,
             scroll_expect=(0x0500, 0x00A0)),
        dict(name='scroll-origin-ahead-of-pointer', buttons=1, pointer_x=0x00E0,
             pointer_y=0x00B8, origin_pixels=0x5000, marker_a=0x42,
             marker_b=0x57, scroll_expect=(0x0010, 0x0002)),
        dict(name='scroll-middle-origin-child-df', buttons=1, pointer_x=0x0110,
             pointer_y=0x00B8, origin_pixels=0x0100, marker_a=0x42,
             marker_b=0x57, flags=0x06D7, scroll_expect=(0x02F0, 0x005E)),
        dict(name='scroll-timer-chain-suppression', buttons=1,
             pointer_x=0x00E0, pointer_y=0x00B8, timer_chain=1),
        dict(name='scroll-child-ret-marker-alias', buttons=1,
             pointer_x=0x00E0, pointer_y=0x00B8, load=0x1010,
             marker_a=0x00FE, marker_b=0x0200, child_ret_alias=True,
             scroll_expect=(0x0010, 0x0002), expected_status=4),
        dict(name='scroll-provider-changes-live-4137', buttons=1,
             pointer_x=0x00E0, pointer_y=0x00B8, load=0x1010,
             operand_provider=0x6200, marker_a=0xF000, marker_b=0xF001,
             scroll_expect=(0x0010, 0x0002)),
        dict(name='scroll-load-1213', buttons=1, pointer_x=0x0110,
             pointer_y=0x00B8, origin_pixels=0x0100, load=0x1213,
             scroll_expect=(0x02F0, 0x005E)),
        dict(name='scroll-load-2345', buttons=1, pointer_x=0x0110,
             pointer_y=0x00B8, origin_pixels=0x0100, load=0x2345,
             scroll_expect=(0x02F0, 0x005E)),
    ]
    return [dict(load=0x1010, seed=0x3E6F + index) | row
            for index, row in enumerate(rows)]


def setup(c):
    memory, device = base.initial_memory(c)
    load = c['load']
    r = base.default_regs(load, c['seed'], ss=c.get('ss', 0x5000),
                          sp=c.get('sp', 0x9000), ds=c.get('ds', 0x3000),
                          flags=c.get('flags', 0x00D7))
    r.update(ax=0xA53E, bx=0xB217, cx=0x8A51, dx=0x3CE0,
             si=0x5123, di=0x42A7, bp=0x6D93, ip=ENTRY)
    r['flags'] = (r['flags'] & 0x7ED5) | 2
    ds = r['ds']
    defaults = {
        'origin_pixels': (0, True), 'origin_bytes': (2, True),
        'dirty_a': (c.get('marker_a', 0x42), True),
        'dirty_b': (c.get('marker_b', 0x57), True),
        'update_gate': (0, False),
        'slot_bound': (c.get('entity_slot_bound', c.get('slot_bound', 0x2A)), False),
        'creation_limit': (0x11, False), 'creation_reload': (0x5C, False),
        'scan_request': (0x17, False), 'release_min': (0x10, False),
        'release': (0x20, False), 'release_refresh': (0, False),
        'panel_latch': (0, False), 'action_selector': (0x55, False),
        'status_refresh': (0, False), 'scan': (0x20, False),
        'fg_counter': (0, False), 'toggle_snapshot': (0, False),
        'action_counter': (0, False), 'action_snapshot': (0, False),
        'timer_chain': (0, False), 'pointer_x': (0x60, True),
        'pointer_y': (0x30, True), 'buttons': (0, True),
        'external_sound': (0, False), 'sound_options': (0, False),
    }
    for name, (default, word) in defaults.items():
        put_data(memory, ds, name, c.get(name, default), device, word)
    if c.get('returned_data'):
        seg, external, options = c['returned_data']
        put8(memory, seg, OFF['external_sound'], external)
        put8(memory, seg, OFF['sound_options'], options)

    # The two real DOS software vectors lead to declared, isolated services.
    binding60 = c.get('binding60', (0x7200, 0x0300))
    binding61 = c.get('binding61', (0x7100, 0x0200))
    put16(memory, 0, 0x180, binding60[1], device)
    put16(memory, 0, 0x182, binding60[0], device)
    put16(memory, 0, 0x184, binding61[1], device)
    put16(memory, 0, 0x186, binding61[0], device)

    if c.get('outer_word_from_code'):
        outer_word = get16(memory, load, 0x4139)
        check(outer_word == 0xC18E, 'declared 4137 alias no longer preserves MOV ES,CX')
    else:
        outer_word = c.get('outer_word', 0xD00D)
    put16(memory, r['ss'], r['sp'], outer_word, device)

    if c.get('child_ret_alias'):
        runtime_segment = get16(memory, load, 0x4137)
        check(runtime_segment == u16(load + 0x143E), 'relocated live segment differs')
        r['ss'] = runtime_segment
        r['sp'] = 0x0100
        put16(memory, r['ss'], r['sp'], 0xD00D, device)
        put16(memory, ds, OFF['dirty_a'], 0x00FE, device)
    if c.get('ivt_alias'):
        r['ss'], r['sp'] = 0, 0x018A
        put16(memory, 0, r['sp'], 0xD00D, device)
    return memory, r, device, (binding60, binding61)


def provider_for(which, c):
    spec = c.get('service' + which)
    if spec is None or c.get('no_service' + which):
        return None

    def provider(access, r):
        before = len(access.events)
        access.providers.add('int' + which + '-provider')
        if spec.get('new_stack'):
            new_ss, new_sp = spec['new_stack']
            saved = [access.word_read(r['ss'], (r['sp'] + 2 * i) & 0xFFFF,
                                      r['flags']) for i in range(4)]
            r['ss'], r['sp'] = new_ss, new_sp
            for index, value in enumerate(saved):
                access.word_write(r['ss'], (r['sp'] + 2 * index) & 0xFFFF,
                                  value, r['flags'])
        if 'new_ds' in spec:
            r['ds'] = spec['new_ds']
        if 'new_es' in spec:
            r['es'] = spec['new_es']
        if 'new_bx' in spec:
            r['bx'] = spec['new_bx']
        if 'saved_flags' in spec:
            access.word_write(r['ss'], (r['sp'] + 4) & 0xFFFF,
                              spec['saved_flags'], r['flags'])
        if 'iret_ip' in spec:
            access.word_write(r['ss'], r['sp'], spec['iret_ip'], r['flags'])
        if 'iret_cs' in spec:
            access.word_write(r['ss'], (r['sp'] + 2) & 0xFFFF,
                              spec['iret_cs'], r['flags'])
        event = dict(vector=int(which, 16), provider_events=len(access.events) - before,
                     status=spec.get('status', 0))
        access.service_events.append(event)
        return spec.get('status', 0)
    return provider


class Access(base.BusAccess):
    def __init__(self, c, memory, r, device):
        super().__init__(c, memory, r, device, max_events=MAX_EVENTS)
        self.live_operand_patched = False

    def access(self, kind, address, flags, mask=FLAGS, value=None):
        result = super().access(kind, address, flags, mask, value)
        if (kind == 'write' and not self.live_operand_patched and
                'operand_provider' in self.c and
                address == physical(self.c.get('ds', 0x3000), 0x0EA8)):
            self.patch(self.c['load'], 0x4137, self.c['operand_provider'],
                       'live-view-operand-provider')
            self.live_operand_patched = True
        return result


class Machine(base.OriginalMachine):
    def __init__(self, c, memory, r, device, core, bindings):
        self.bindings = bindings
        access = Access(c, memory, r, device)
        providers = {0x60: provider_for('60', c), 0x61: provider_for('61', c)}

        def interrupt(machine, number):
            check(number in (0x60, 0x61), f'unexpected INT {number:02X}')
            resume = {0x60: 0x3F8F, 0x61: 0x3F7C}[number]
            binding = bindings[0] if number == 0x60 else bindings[1]
            machine.software_interrupt(number, resume, binding, providers[number])

        super().__init__(c, memory, r, device, core, instructions=INS,
                         access=access, outer_returns=OUTER_RETS,
                         child_returns=CHILD_RETS, max_steps=MAX_STEPS,
                         changed_return_status=4, interrupt=interrupt,
                         mutable_operands=((0x4137, 2),))

    def run(self):
        out = super().run()
        out['service_status'] = self.service_status
        out['services'] = copy.deepcopy(self.access.service_events)
        out['transport_events'] = self.access.transport_events
        out['service_calls'] = len(self.access.service_events)
        out['provider_events'] = sum(x['provider_events'] for x in self.access.service_events)
        return out


class Native:
    def __init__(self, directory, mutation=0):
        path = build(Path(directory) / f'ui-commands-{mutation}.dll',
                     mutation, 'ui_commands')
        self.library = ct.CDLL(str(path))
        self.functions = {}
        for kind in ('core', 'adapter'):
            fn = getattr(self.library, 'lmn_process_input_commands_' + kind)
            fn.argtypes = [MEM, ct.POINTER(Regs), ct.POINTER(Service),
                           ct.POINTER(Service), ct.POINTER(base.Bus)]
            fn.restype = UiResult
            self.functions[kind] = fn

    def run(self, directory, c, initial, r, device, bindings, core):
        memory = bytearray(initial)
        access = Access(c, memory, dict(r), copy.deepcopy(device))
        callbacks = base.NativeCallbacks(access)
        keepalive = []
        service_ptrs = []
        for which, binding in ((60, bindings[0]), (61, bindings[1])):
            provider = provider_for(str(which), c)
            if provider is None:
                service_ptrs.append(ct.POINTER(Service)())
                continue
            callback = callbacks.interrupt(provider)
            service = Service(None, callback, binding[0], binding[1])
            keepalive.extend((callback, service))
            service_ptrs.append(ct.pointer(service))
        native_memory = (ct.c_uint8 * SIZE).from_buffer(memory)
        regs = Regs(**r)
        result = self.functions['core' if core else 'adapter'](
            native_memory, ct.byref(regs), service_ptrs[0], service_ptrs[1],
            ct.byref(callbacks.bus))
        return dict(regs={n: getattr(result.registers, n) & 0xFFFF for n in REGS},
                    status=result.status, service_status=result.service_status,
                    memory=memory, device=access.device, events=access.events,
                    providers=access.providers, services=access.service_events,
                    cursor=access.cursor)


def release_reload(value):
    return u8(4 + (u8(99 - value) >> 1))


def independent(c, initial, r, ref, core):
    check(ref['status'] == c.get('expected_status', 0),
          c['name'] + ': unexpected independent status')
    check(ref['service_status'] == c.get('expected_service_status', 0),
          c['name'] + ': unexpected provider status')
    out = ref['regs']
    if c.get('outer_ret') is not None:
        expected_ret = c['outer_ret']
    else:
        expected_ret = (0x3FE8 if c.get('scan') is None and
                        (c.get('buttons', 0) & 1) == 0 else 0x3FEE)
    if ref['status'] == 0:
        if core:
            check(out['ip'] == expected_ret, c['name'] + ': core RET boundary differs')
            service = c.get('service61') or c.get('service60') or {}
            expected_stack = service.get('new_stack')
            if expected_stack:
                check((out['ss'], out['sp']) ==
                      (expected_stack[0], u16(expected_stack[1] + 6)),
                      c['name'] + ': provider-owned stack did not flow through IRET')
            elif c.get('child_ret_alias'):
                check((out['ss'], out['sp']) ==
                      (u16(r['ss']), u16(r['sp'] - 2)),
                      c['name'] + ': changed child return stack differs')
            else:
                check((out['ss'], out['sp']) == (r['ss'], r['sp']),
                      c['name'] + ': core changed caller stack')
        else:
            if c.get('outer_word_from_code'):
                outer_word = 0xC18E
            else:
                outer_word = c.get('outer_word', 0xD00D)
            service = c.get('service61') or c.get('service60') or {}
            stack = service.get('new_stack')
            ss, sp = stack if stack else (r['ss'], r['sp'])
            if c.get('child_ret_alias'):
                check(out['ip'] == 0x3FFF,
                      c['name'] + ': marker did not change actual child RET')
                return
            outer_sp = u16(sp + 6) if stack else sp
            check(out['ip'] == outer_word and (out['ss'], out['sp']) ==
                  (ss, u16(outer_sp + 2)), c['name'] + ': adapter live RET differs')
    elif c.get('child_ret_alias') and ref['status'] == 4:
        expected_ss = u16(c['load'] + 0x143E)
        check((out['ip'], out['ss'], out['sp']) ==
              (0x3FFF, expected_ss, 0x0100),
              c['name'] + ': actual changed child RET boundary differs')

    ds = r['ds']
    mem = ref['memory']
    if c.get('expected_selector') is not None and ref['status'] == 0:
        check(get8(mem, ds, OFF['action_selector']) == c['expected_selector'],
              c['name'] + ': action selector differs')
    if c.get('scan') in (0x3B, 0x3C) and ref['status'] == 0:
        before = c.get('release', 0x20)
        refresh = c.get('release_refresh', 0)
        expected = before
        if c['scan'] == 0x3B:
            if not refresh and before != c.get('release_min', 0x10):
                expected = u8(before - 1)
        elif not refresh and before != 0x63:
            expected = u8(before + 1)
        check(get8(mem, ds, OFF['release']) == expected,
              c['name'] + ': release setting differs')
        if expected != before:
            check(get8(mem, ds, OFF['creation_reload']) == release_reload(expected),
                  c['name'] + ': independent release reload equation differs')
    if c.get('scan') in (0x4E, 0x57) and ref['status'] == 0:
        current = c.get('fg_counter', 0)
        old = c.get('toggle_snapshot', 0)
        gate = c.get('update_gate', 0)
        if u8(current - old) >= 2:
            gate ^= 0xFF
        check(get8(mem, ds, OFF['update_gate']) == u8(gate),
              c['name'] + ': independent unsigned toggle delta differs')
        expected_snapshot = current if u8(current - old) >= 2 else old
        check(get8(mem, ds, OFF['toggle_snapshot']) == expected_snapshot,
              c['name'] + ': toggle snapshot differs')
    if c.get('scan') in (0x53, 0x58) and ref['status'] == 0:
        delta = s8(c.get('action_counter', 0) - c.get('action_snapshot', 0))
        gate_allows = c.get('update_gate', 0) != 0xFF
        accepted = delta <= 5 and gate_allows
        expected_snapshot = c.get('action_counter', 0) if gate_allows else c.get('action_snapshot', 0)
        check(get8(mem, ds, OFF['action_snapshot']) == expected_snapshot,
              c['name'] + ': action counter snapshot did not refresh')
        check(get8(mem, ds, OFF['scan']) ==
              (0 if gate_allows else c['scan']),
              c['name'] + ': escape scan-code clear differs')
        if accepted:
            check(get8(mem, ds, OFF['scan_request']) == 0xFF and
                  get8(mem, ds, OFF['creation_limit']) ==
                  c.get('entity_slot_bound', c.get('slot_bound', 0x2A)),
                  c['name'] + ': accepted action request/limit differs')

    if c.get('buttons', 0) and c.get('scroll_expect') is not None:
        expected_pixels, expected_bytes = c['scroll_expect']
        check(get16(mem, ds, OFF['origin_pixels']) == expected_pixels and
              get16(mem, ds, OFF['origin_bytes']) == expected_bytes,
              c['name'] + ': independent scroll-origin clamp differs')

    if ref['status'] in (0, 4) and c.get('scroll_expect') is not None:
        assert_view_projection(c, initial, ref)


def get8(memory, segment, offset):
    return memory[physical(segment, offset)]


def assert_view_projection(c, initial, ref):
    """Check the child’s clear/fill footprint and live dirty markers by equation."""
    ds = c.get('ds', 0x3000)
    memory = ref['memory']
    pixels, _ = c['scroll_expect']
    step = -1 if c.get('flags', 0x00D7) & 0x0400 else 1
    expected = {}
    for index in range(0x68):
        offset = u16(0x0EA8 + step * index * 2)
        expected[physical(ds, offset)] = 0
        expected[physical(ds, u16(offset + 1))] = 0
    fill = u16(0x0EA8 + (pixels >> 3) - 2)
    for index in range(0x29):
        expected[physical(ds, u16(fill + step * index))] = 1
    for address, value in expected.items():
        check(memory[address] == value,
              f"{c['name']}: visibility map byte {address:05X} differs")
    runtime = c.get('operand_provider', u16(c['load'] + 0x143E))
    for marker in (c.get('marker_a', 0x42), c.get('marker_b', 0x57)):
        check(get8(memory, runtime, marker) == 0xFF,
              c['name'] + ': visibility marker write differs')


def compare(native, c, core):
    initial, r, device, bindings = setup(c)
    machine = Machine(c, bytearray(initial), dict(r), copy.deepcopy(device), core, bindings)
    ref = machine.run()
    independent(c, initial, r, ref, core)
    if native:
        actual = native.run(None, c, initial, r, device, bindings, core)
        base.compare_states(c['name'], actual, ref)
    return ref


def hashes():
    paths = (
        'assets/vgalemmi.exe', 'metadata/inputs.json',
        'metadata/oracle.json', 'metadata/toolchain-lock.json',
        'src/input_commands.asm', 'src/view_visibility.asm',
        'c/ui_commands.c', 'c/ui_commands.h', 'c/interrupt_service.c',
        'c/interrupt_service.h', 'c/view_visibility.c', 'c/view_visibility.h',
        'c/lemmings_sym.h', 'c/special_blit.h', 'c/regs.h',
        'tests/ui_commands.py', 'tests/verification.py', 'tests/minimap_vga.py',
        'tools/resources.py', 'tools/unpack.py', 'tools/common.py',
        'tools/bounded_process.py', 'tools/cbuild.py', 'tools/difftest.py',
    )
    missing = [p for p in paths if not (ROOT / p).is_file()]
    check(not missing, 'missing consumed inputs: ' + ', '.join(missing))
    return {p: sha((ROOT / p).read_bytes()) for p in paths}


def worker(directory=None, snapshot=None):
    before = hashes()
    if snapshot:
        check(before == json.loads(Path(snapshot).read_text()),
              'ui-commands input snapshot differs')
    native = Native(directory) if directory else None
    rows = []
    for c in cases():
        for core in (True, False):
            ref = compare(native, c, core)
            rows.append(dict(case=c['name'], core=core, status=ref['status'],
                             service_status=ref['service_status'],
                             sites=sorted(ref['sites']), edges=sorted(ref['edges']),
                             steps=ref['steps'], events=len(ref['events']),
                             transport_events=ref['transport_events'],
                             service_calls=ref['service_calls'],
                             provider_events=ref['provider_events']))
        gc.collect()
        print('CHECKED ' + c['name'], flush=True)

    mutations = None
    if native:
        mutations = []
        lookup = {c['name']: c for c in cases()}
        witnesses = ((1, 'action-counter-signed-wrap'),
                     (2, 'action-returned-ds-enables-int60'),
                     (3, 'release-below-minimum-wrap'),
                     (4, 'scroll-child-ret-marker-alias'),
                     (5, 'toggle-byte-delta-unsigned'))
        for mutation, name in witnesses:
            mutant = Native(directory, mutation)
            try:
                compare(mutant, lookup[name], True)
            except Mismatch as error:
                mutations.append(dict(mutation=mutation, case=name,
                                      completed=True, mismatch=str(error)))
            else:
                raise Failure(f'ui_commands mutant {mutation} survived')
            gc.collect()

    sites = {address for row in rows for address in row['sites']}
    edges = {tuple(edge) for row in rows for edge in row['edges']}
    check(sites == EXPECTED_SITES,
          f'executed code differs: missing={sorted(EXPECTED_SITES-sites)} '
          f'extra={sorted(sites-EXPECTED_SITES)}')
    check(edges == EXPECTED_EDGES,
          f'branch coverage differs: missing={sorted(EXPECTED_EDGES-edges)} '
          f'extra={sorted(edges-EXPECTED_EDGES)}')
    check(before == hashes(), 'campaign inputs changed')
    report = dict(
        image='main', image_sha256=sha(IMAGE), known_connected_bytes=594,
        input_command_bytes=530, visibility_child_bytes=64,
        unknown_bytes=[f'{x:04X}' for x in UNKNOWN],
        case_count=len(cases()), comparison_count=len(rows),
        executed_instruction_addresses=sorted(sites), branch_edges=sorted(edges),
        infeasible_edges=[list(edge) for edge in sorted(INFEASIBLE_EDGES)],
        infeasibility_proof=('BX is origin_pixels>>4 plus D0, hence 208..4303. '
            'If 3FB0 falls through then signed AX<BX; adding 24 cannot make '
            'AX reach BX, so 3FB7 always branches to 3FBE and 3FB9/3FBC are unexecuted.'),
        instruction_steps=sum(row['steps'] for row in rows),
        ordered_bus_events=sum(row['events'] for row in rows),
        declared_interrupt_transport_events=sum(row['transport_events'] for row in rows),
        declared_provider_events=sum(row['provider_events'] for row in rows),
        declared_service_calls=sum(row['service_calls'] for row in rows),
        mutation_count=len(mutations or []), mutations=mutations or [], rows=rows,
        input_hashes=before,
        limits=dict(timeout_seconds=SECONDS, process_commit_mib=MEMORY_MIB,
                    instructions=MAX_STEPS, events=MAX_EVENTS),
        scope=('Connected 3E6F input-command parent and actual 410F visibility '
            'CALL/RET child on constructed synchronous state. UNKNOWN bytes, '
            'unreachable 3FB9/3FBC comparisons, async input timing and live '
            'interrupt scheduling are outside the tested domain.'))
    write_json(REPORT if native else ORIGINAL, report)
    print(f'PASS UI commands: {len(rows)} comparisons, {len(sites)} sites, '
          f'{len(edges)} branch outcomes, {len(mutations or [])} mutants', flush=True)


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
        raise SystemExit('usage: ui_commands.py [--original-only]')
    REPORT.unlink(missing_ok=True)
    with temporary_build_directory(prefix='ui-commands-', parent=BUILD) as directory:
        snapshot = Path(directory) / 'input-hashes.json'
        snapshot.write_text(json.dumps(hashes(), sort_keys=True))
        run_bounded([sys.executable, __file__, '--worker', str(directory), str(snapshot)],
                    cwd=ROOT, timeout=SECONDS, memory_mib=MEMORY_MIB, check=True)


if __name__ == '__main__':
    main()

"""Bounded original-only machine for the identified 58D2 composition.

The suite owns fixtures and service models. This helper executes original bytes
and captures pre-RET and actual-RET references in the same execution. It never
calls the C translation or substitutes a decoded resource for the DOS stream.
"""
import copy

import capstone
from unicorn import (Uc, UcError, UC_ARCH_X86, UC_MODE_16, UC_HOOK_CODE,
                     UC_HOOK_INTR, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE,
                     UC_HOOK_INSN)
from unicorn import x86_const as x


def original(h, case, initial, entry_regs, initial_device):
    size, mask = h.SIZE, h.MASK
    memory = bytearray(initial)
    regs = dict(entry_regs)
    ids = h.oracle.REG_IDS
    device = copy.deepcopy(initial_device)
    dos = h.DosProvider(case, memory, regs)
    access = h.Access(case, memory, regs, device)
    logged = (set(h.OWN_INS) | set(h.sprite_parent.MAIN_INS) |
              set(h.fixed_words.MAIN_INS) | set(h.graphics_parent.INS) |
              set(h.plane_copy.OWN_INS) | {0x1BAE})
    returns = {0x1B79: 0x1BAE, 0x1BA9: 0x1BAE, 0x57D1: 0x5826,
               0x59BB: 0x5AC0, 0x5CC1: 0x5D17, 0x5AC1: 0x5B10,
               0x5B11: 0x5BAF, 0x5BB0: 0x5C05, 0x5C06: 0x5CC0,
               0x5CDD: 0x5D17, 0x5D66: 0x5D93}
    cpu = Uc(UC_ARCH_X86, UC_MODE_16)
    cpu.mem_map(0, size * 2)
    cpu.mem_write(0, bytes(memory))
    cpu.mem_write(size, bytes(memory))
    for name, value in regs.items():
        cpu.reg_write(ids[name], value)
    # These are fixture-loaded bytes, including all declared DOS relocations.
    expected_code = bytes(initial[(regs['cs'] << 4):
                                  (regs['cs'] << 4) + len(h.IMAGE)])

    def mirror(address, value):
        address &= mask
        byte = bytes((value & 255,))
        cpu.mem_write(address, byte)
        cpu.mem_write(address + size, byte)

    def synchronize_all():
        cpu.mem_write(0, bytes(memory))
        cpu.mem_write(size, bytes(memory))

    access.mirror = mirror
    previous = None
    current_mask = h.FLAGS
    current_flags = regs['flags']
    stopped, failure = False, None
    steps = 0
    sites, edges, all_sites, all_edges = set(), set(), set(), set()
    frames, calls = [], []
    core_snapshot = adapter_snapshot = None

    def state():
        return {name: cpu.reg_read(register) & 65535
                for name, register in ids.items()}

    def snapshot(status, continuation, child_entry=0, child_status=0):
        actual = bytes(cpu.mem_read(0, size))
        h.check(actual == bytes(memory), case['name'] + ': RAM mirror diverged')
        return dict(memory=actual, regs=state(), device=copy.deepcopy(device),
                    events=access.events, events_count=len(access.events),
                    dos_events=copy.deepcopy(dos.events), dos_used=set(dos.used),
                    providers=set(access.used), status=status,
                    continuation=continuation, child_entry=child_entry,
                    child_status=child_status, flag_mask=current_mask,
                    steps=steps, sites=set(sites), edges=set(edges),
                    integrated_sites=set(all_sites), integrated_edges=set(all_edges),
                    calls=copy.deepcopy(calls))

    def stop(message=None):
        nonlocal stopped, failure
        stopped, failure = True, message
        cpu.emu_stop()

    def set_reg(name, value):
        cpu.reg_write(ids[name], value & 65535)

    def service_budget():
        h.check(len(dos.events) < h.MAX_DOS_EVENTS,
                'original DOS callback budget exhausted')

    def interrupt(u, number, _):
        nonlocal current_mask
        try:
            h.check(number == 0x21, f'unexpected original INT {number:02X}')
            service_budget()
            function = (u.reg_read(ids['ax']) >> 8) & 255
            segment, offset = u.reg_read(ids['ds']), u.reg_read(ids['dx'])
            flags = u.reg_read(ids['flags']) & 65535
            before = set(dos.used)
            if function == 0x3F:
                count, handle = u.reg_read(ids['cx']), u.reg_read(ids['bx'])
                cursor = dos.position
                value, returned, out_flags, failed = dos.file_service(
                    function, segment, offset, flags, count=count, handle=handle)
                if not failed:
                    # A declared DOS buffer is a linear physical byte extent;
                    # CPU string cursor wrap is a separate instruction effect.
                    base = h.physical(segment, offset)
                    payload = h.MAIN_DATA[cursor:cursor + returned]
                    for index, byte in enumerate(payload):
                        memory[(base + index) & mask] = byte
                    first = min(len(payload), size - base)
                    if first:
                        u.mem_write(base, payload[:first])
                        u.mem_write(base + size, payload[:first])
                    if first < len(payload):
                        u.mem_write(0, payload[first:])
                        u.mem_write(size, payload[first:])
            elif function in (0x43, 0x3D):
                value, returned, out_flags, _failed = dos.file_service(
                    function, segment, offset, flags)
                if function == 0x43:
                    set_reg('cx', returned)
            elif function == 0x23:
                # Direct fixtures normally bypass caching. Keep the declared
                # size service exact if an explicitly constructed state uses it.
                h.put16(memory, segment, (offset + 33) & 65535,
                        len(h.MAIN_DATA) & 65535)
                h.put16(memory, segment, (offset + 35) & 65535,
                        len(h.MAIN_DATA) >> 16)
                dos.events.append(dict(function=0x23, segment=segment,
                                       offset=offset, input_flags=flags & 0xFD7))
                value, out_flags = 0x2300, (flags & ~0x8D5) | 0x894
                synchronize_all()
            else:
                raise h.OracleFailure(f'unsupported original DOS AH={function:02X}')
            # Stack/code changes made by a service provider are real writes,
            # including providers which do not perform a file read.
            if before != set(dos.used):
                synchronize_all()
            set_reg('ax', value)
            set_reg('flags', out_flags)
            current_mask = h.FLAGS
        except BaseException as error:
            stop(str(error))

    def retry_return():
        nonlocal current_mask
        service_budget()
        view = state()
        ss, sp = view['ss'], view['sp']
        # The retry helper is a declared service, not discovered execution.
        target = h.get16(memory, ss, sp)
        h.check(target in (h.files.field('DatAfterFileRetry'),
                           h.files.field('DatAfterResourceRetry')),
                'retry service saw an undeclared near return')
        ax, bx, bp, flags = dos.retry(view)
        synchronize_all()
        for name, value in dict(ax=ax, bx=bx, bp=bp, si=0x2222, di=0x3333,
                                ds=0x4444, es=0x5555, cx=0x6666,
                                dx=0x7777, ip=target, sp=sp + 2,
                                flags=flags).items():
            set_reg(name, value)
        current_mask = h.FLAGS

    def code_impl(u):
        nonlocal previous, current_flags, current_mask, steps, core_snapshot, adapter_snapshot
        cs, off = u.reg_read(ids['cs']) & 65535, u.reg_read(ids['ip']) & 65535
        if previous is not None:
            prev_off, prev_ins = previous
            current_mask = h.oracle.flags_after(prev_ins, current_mask)
            access.instruction_complete()
            if prev_off in h.BRANCHES:
                all_edges.add((prev_off, off))
                if prev_off in h.PARENT_BRANCHES:
                    edges.add((prev_off, off))
            if prev_ins.mnemonic == 'call' and prev_off in logged:
                entry = prev_ins.operands[0].imm & 65535
                h.check(entry in returns and cs == regs['cs'] and off == entry,
                        f'original CALL {prev_off:04X} escaped its declared entry')
                top = prev_off in h.CALL_TARGETS
                h.check(top or frames, 'graphics call has no parent frame')
                owner = entry if top else frames[0]['owner']
                frames.append(dict(entry=entry, owner=owner,
                                   call_site=prev_off, top=top,
                                   return_site=returns[entry],
                                   return_ip=(prev_off + prev_ins.size) & 65535))
                calls.append((prev_off, entry))
            elif prev_ins.mnemonic == 'ret':
                if prev_off == h.RET:
                    h.check(not frames, 'outer RET left a child frame active')
                    adapter_snapshot = snapshot(0, off)
                    stop()
                    return
                if frames and prev_off == frames[-1]['return_site']:
                    frame = frames.pop()
                    if cs != regs['cs'] or off != frame['return_ip']:
                        child_status = (0 if frame['top'] else
                                        {0x59BB: 2, 0x5CC1: 1,
                                         0x5AC1: 0}.get(frame['owner'], 0))
                        core_snapshot = snapshot(2, off, frame['owner'], child_status)
                        stop()
                        return
                elif prev_off in logged:
                    raise h.OracleFailure(f'original RET {prev_off:04X} has no matching frame')
        if cs == regs['cs'] and off in h.FATAL_OFFSETS:
            child = frames[0]['owner'] if frames else 0
            core_snapshot = snapshot(3, off, child, 1 if off == 0x1949 else 2)
            stop()
            return
        if cs == regs['cs'] and off == h.files.RETRY:
            retry_return()
            previous = None
            return
        h.check(cs == regs['cs'] and off in h.MAIN_INS,
                f'original escaped identified composition at {cs:04X}:{off:04X}')
        ins = h.MAIN_INS[off]
        actual = bytes(u.mem_read(h.physical(cs, off), ins.size))
        expected = expected_code[off:off + ins.size]
        if off == 0x5967 and 'sound-segment' in dos.used:
            # A specifically declared service-time operand write is checked
            # against its exact new word; no unexplained bits are masked.
            expected = expected[:1] + int(case['sound_segment']).to_bytes(2, 'little')
        h.check(actual == expected, f'original code changed at {cs:04X}:{off:04X}')
        # Capture FLAGS at the instruction boundary, as in the child oracle.
        # Unicorn's memory-hook view may still expose deferred arithmetic
        # flags from before the preceding instruction (for example ADD DI,3
        # before POP CX at 5B82). Bus accesses observe instruction-entry FLAGS.
        current_flags = u.reg_read(ids['flags']) & 65535
        access.enabled = off in logged
        if off == h.RET:
            h.check(not frames, 'core boundary left a child frame active')
            core_snapshot = snapshot(0, h.RET)
        h.check(steps < h.MAX_STEPS, 'original instruction budget exhausted')
        steps += 1
        all_sites.add(off)
        if off in h.OWN_INS:
            sites.add(off)
        previous = (off, ins)

    def code(u, _address, _size, _):
        try:
            code_impl(u)
        except BaseException as error:
            stop(str(error))

    def on_read(u, _kind, address, width, _value, _):
        try:
            if access.enabled:
                for delta in range(width):
                    access.access('read', (address + delta) & mask,
                                  current_flags, current_mask)
        except BaseException as error:
            stop(str(error))

    def on_write(u, _kind, address, width, value, _):
        try:
            for delta in range(width):
                p, byte = (address + delta) & mask, (value >> (delta * 8)) & 255
                if access.enabled:
                    access.access('write', p, current_flags, current_mask, value=byte)
                else:
                    memory[p] = byte
                    mirror(p, byte)
        except BaseException as error:
            stop(str(error))

    def on_out(u, port, width, value, _):
        try:
            h.check(width == 2 and access.enabled,
                    'original OUT outside declared VGA domain')
            access.out_word(port, value, current_flags,
                            current_mask)
        except BaseException as error:
            stop(str(error))

    cpu.hook_add(UC_HOOK_CODE, code)
    cpu.hook_add(UC_HOOK_INTR, interrupt)
    cpu.hook_add(UC_HOOK_MEM_READ, on_read)
    cpu.hook_add(UC_HOOK_MEM_WRITE, on_write)
    cpu.hook_add(UC_HOOK_INSN, on_out, None, 1, 0, x.UC_X86_INS_OUT)
    try:
        cpu.emu_start(h.physical(regs['cs'], regs['ip']), 0,
                      count=h.MAX_STEPS + 1)
    except UcError as error:
        raise h.OracleFailure(case['name'] + ': bounded original failed') from error
    h.check(stopped and failure is None,
            case['name'] + ': ' + (failure or 'did not reach a declared boundary'))
    h.check(core_snapshot is not None, case['name'] + ': missing core reference')
    if adapter_snapshot is None:
        adapter_snapshot = core_snapshot
    return dict(core=core_snapshot, adapter=adapter_snapshot,
                dos_events=dos.events, dos_used=set(dos.used), providers=set(access.used),
                sites=sites, edges=edges, integrated_sites=all_sites,
                integrated_edges=all_edges, steps=steps, calls=calls,
                event_count=len(access.events), events=access.events,
                device=device, memory=bytes(memory), regs=regs)

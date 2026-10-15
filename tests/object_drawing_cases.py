"""Deterministic entry-state fixtures for the 397D..39CD object suffix.

This module prepares memory after the 378A graphics-record copy.  Synthetic
cases install their own bounded working slots; real cases use the pinned
LEVEL/GROUND inputs and a separate forward byte-copy model before entry.
"""
import random
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]

import dat_io as oracle
import object_graphics as graphics
from common import ROOT, read_json
from unpack import ASSET, relocated, unpack


IMAGE, ORACLE = unpack(ASSET.read_bytes())
SYMS = {symbol['symbol_name']: symbol
        for symbol in read_json(ROOT / 'metadata/symbols.json')}
START, END = 0x397d, 0x39ce
MEMORY_SIZE = 1 << 20
DF = 0x0400
_RELOCATED_IMAGES = {}


def field(name):
    return SYMS[name]['address']


def _physical(segment, offset):
    return ((segment << 4) + (offset & 0xffff)) & (MEMORY_SIZE - 1)


def _read8(memory, segment, offset):
    return memory[_physical(segment, offset)]


def _write8(memory, segment, offset, value):
    memory[_physical(segment, offset)] = value & 0xff


def _write_be16(memory, segment, offset, value):
    _write8(memory, segment, offset, value >> 8)
    _write8(memory, segment, offset + 1, value)


def _relocated_image(load):
    if load not in _RELOCATED_IMAGES:
        _RELOCATED_IMAGES[load] = relocated(IMAGE, ORACLE['relocations'], load)
    return _RELOCATED_IMAGES[load]


def _clear_synthetic_definitions(memory, ds):
    definitions = field('LevelObjectDefinitions')
    for offset in range(32 * 8):
        _write8(memory, ds, definitions + offset, 0)


def _write_synthetic_object(memory, ds, row, *, object_type=0):
    index, x, y, drawing_flags, width, height, source, mask_relative = row
    definition = field('LevelObjectDefinitions') + index * 8
    working = field('LevelObjectGraphicsRecords') + index * 28
    _write_be16(memory, ds, definition, x)
    _write_be16(memory, ds, definition + 2, y)
    _write_be16(memory, ds, definition + 4, object_type)
    _write_be16(memory, ds, definition + 6, drawing_flags)

    # Keep unrelated bytes stable and visibly distinct between slots.  Only
    # the four fields consumed by 397D..39CD are assigned below.
    for offset in range(28):
        _write8(memory, ds, working + offset,
                (0x53 + index * 29 + offset * 17) & 0xff)
    _write8(memory, ds, working + 4, width)
    _write8(memory, ds, working + 5, height)
    # +08 is a mask-relative offset; the drawing loop adds current frame +17
    # to it for DI.  SI itself receives the +17 word.
    oracle.put16(memory, ds, working + 8, mask_relative)
    oracle.put16(memory, ds, working + 0x17, source)


def _copy_real_graphics_records(memory, ds):
    """Apply the ordinary forward REP MOVSB record-copy behavior in Python."""
    definitions = field('LevelObjectDefinitions')
    ground = field('GroundResourceBuffer')
    output = field('LevelObjectGraphicsRecords')
    for index in range(32):
        definition = definitions + index * 8
        x = (_read8(memory, ds, definition) << 8) | _read8(
            memory, ds, definition + 1)
        if x == 0:
            continue
        object_type = (_read8(memory, ds, definition + 4) << 8) | _read8(
            memory, ds, definition + 5)
        source = (ground + ((object_type * 28) & 0xffff)) & 0xffff
        destination = (output + index * 28) & 0xffff
        for byte_index in range(28):
            value = _read8(memory, ds, (source + byte_index) & 0xffff)
            _write8(memory, ds, (destination + byte_index) & 0xffff, value)


def _put_renderer_layout(memory, ds, *, source_segment=0x5000):
    for name, value in (
        ('DrawingWidthPixels', 1664),
        ('DrawingHeight', 164),
        ('DrawingPitchBytes', 208),
        ('DrawingOrigin', 0x4a40),
        ('DrawingPageByteOffset', 0),
        ('DrawingDirtyCellMapOffset', 0x6000),
        ('DrawingSourcePlaneExtent', 0x2000),
        ('DrawingSourcePitchBytes', 32),
        ('DrawingSourceRowAdvance', 0),
        ('DrawingActiveDestinationRowAdvance', 0),
        ('DrawingDestinationRowAdvance', 0),
        ('DrawingHorizontalSkipBytes', 0),
        ('DrawingVerticalSkipBytes', 0),
        ('LevelGraphicsSegment', source_segment),
    ):
        oracle.put16(memory, ds, field(name), value)
    _write8(memory, ds, field('DrawingDirtyCellsEnabledByte'), 0)


def _put_source_pixels(memory, source_segment=0x5000):
    """Install deterministic bytes for four source planes and their masks."""
    start = _physical(source_segment, 0)
    pixels = bytes(
        ((offset * 37 + (offset >> 5) * 11 + (offset >> 12) * 53 + 0x5b)
         & 0xff) for offset in range(0x10000))
    first = min(len(pixels), MEMORY_SIZE - start)
    memory[start:start + first] = pixels[:first]
    if first < len(pixels):
        memory[:len(pixels) - first] = pixels[first:]


def _base(case):
    seed = 0x397d + case['seed']
    rng = random.Random(seed)
    load = case.get('load', (0x1010, 0x1213, 0x2345)[case['seed'] % 3])
    memory = bytearray(rng.randbytes(MEMORY_SIZE))
    image = _relocated_image(load)
    memory[load << 4:(load << 4) + len(IMAGE)] = image
    ds = (load + 0x09a9) & 0xffff
    _clear_synthetic_definitions(memory, ds)
    regs = {name: rng.randrange(0x10000) for name in oracle.REG_NAMES}
    regs.update(cs=load, ip=START, ds=ds, es=ds, ss=0x7000, sp=0x8000,
                ax=0x1357, bx=0x2468, cx=0x5a5a, dx=0x369c, bp=0x7fff)
    flags = 2 | (rng.randrange(0x10000) & 0x0ad5)
    if case.get('df'):
        flags |= DF
    else:
        flags &= ~DF
    _put_renderer_layout(memory, ds,
                         source_segment=case.get('source_segment', 0x5000))
    _put_source_pixels(memory, case.get('source_segment', 0x5000))
    oracle.put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xeed1))
    return memory, regs, flags, ds


def _constructed_case(name, objects=(), **kwargs):
    return dict(name=name, objects=tuple(objects), seed=kwargs.pop('_seed', 0),
                real=False, independent=True, **kwargs)


def _default_object(index, x, y, drawing_flags=0x0001, width=24, height=3):
    return (index, x, y, drawing_flags, width, height,
            0x1000 + index * 0x0100, 0x7000 + index * 0x0100)


def _real_level_cases():
    return [case for case in graphics.cases() if case.get('real')]


def _assert_constructed_active_indices(memory, ds, objects):
    expected = {row[0] for row in objects}
    definitions = field('LevelObjectDefinitions')
    actual = set()
    for index in range(32):
        base = definitions + index * 8
        x = (_read8(memory, ds, base) << 8) | _read8(memory, ds, base + 1)
        if x:
            actual.add(index)
    if actual != expected:
        raise AssertionError(
            f'constructed active definitions differ: {sorted(actual)} != {sorted(expected)}')


def _assert_original_suffix_intact(memory, regs):
    image = _relocated_image(regs['cs'])
    start = regs['cs'] << 4
    actual = bytes(memory[start + START:start + END])
    if actual != image[START:END]:
        raise AssertionError('fixture setup changed original 397D..39CD bytes')


def cases():
    out = []

    def add(name, objects=(), **kwargs):
        out.append(_constructed_case(name, objects, _seed=len(out), **kwargs))

    add('all-inactive')
    add('one-active-first', (_default_object(0, 1, 0, 0x0001, 8, 1),))
    add('one-active-middle', (_default_object(15, 7, 1, 0x400f, 16, 2),), df=True)
    add('one-active-last', (_default_object(31, 1663, 163, 0xc00f, 32, 3),))
    add('multiple-active-forward', (
        _default_object(0, 1, 0, 0x000f, 8, 1),
        _default_object(5, 15, 159, 0x4021, 16, 2),
        _default_object(31, 1663, 163, 0x8003, 24, 3)))
    add('multiple-active-backward', (
        _default_object(2, 7, 1, 0x0023, 32, 4),
        _default_object(16, 8, 162, 0x0041, 24, 2),
        _default_object(30, 1655, 164, 0x4003, 16, 1)), df=True)

    all_forward = tuple(_default_object(
        index, (1, 7, 8, 15, 16, 1655, 1663)[index % 7],
        (0, 1, 159, 162, 163, 164)[index % 6],
        (0x0001, 0x0003, 0x0021, 0x0041, 0x4003, 0x8001, 0xc021)[index % 7],
        (8, 16, 24, 32)[index % 4], (1, 2, 3, 4)[index % 4])
        for index in range(32))
    add('all-32-active-forward', all_forward)
    add('all-32-active-backward', all_forward, df=True)

    for slot, x, y in ((0, 1, 0), (1, 7, 1), (2, 8, 159),
                       (3, 15, 162), (4, 16, 163), (5, 1655, 164),
                       (6, 1663, 0)):
        add(f'coordinate-boundary-{slot}',
            (_default_object(slot, x, y, 0x0003, 16, 2),), df=bool(slot & 1))

    for number, (width, height) in enumerate(
            ((1, 1), (7, 2), (8, 3), (9, 4), (16, 1), (24, 2), (32, 3))):
        add(f'finite-size-{width}x{height}',
            (_default_object(number, 17 + number, number, 0x0001, width, height),),
            df=bool(number & 1))

    for name, drawing_flags, df in (
        ('opaque-bit0-cleared', 0x0001, False),
        ('masked-bit0-cleared', 0x0003, True),
        ('protected-bit0-cleared', 0x8001, False),
        ('read-mask-bit0-cleared', 0x4001, True),
        ('effect-20-bit0-cleared', 0x0021, False),
        ('effect-40-bit0-cleared', 0x0041, True),
        ('effect-reverse-bit0-cleared', 0x0081, False),
        ('combined-read-mask-effect-bit0-cleared', 0x4021, True),
        ('combined-protected-effect-bit0-cleared', 0x8041, False),
        ('combined-read-protected-effects-bit0-cleared', 0xc061, True),
    ):
        add(name, (_default_object(4, 19, 3, drawing_flags, 24, 3),), df=df)

    sources = _real_level_cases()
    if len(sources) != 80:
        raise AssertionError(f'expected 80 real LEVEL sections, found {len(sources)}')
    for source_case in sources:
        out.append(dict(name=f"real-{source_case['level_asset'][-7:-4]}-"
                             f"{source_case['section']}",
                        seed=len(out), real=True, independent=True, df=False,
                        source_case=source_case,
                        level_asset=source_case['level_asset'],
                        ground_asset=source_case['ground_asset'],
                        section=source_case['section']))
    return out


def prepare(case):
    """Return (memory, registers, flags, game_ds) at suffix entry 397D."""
    if case.get('real'):
        memory, regs, flags = graphics.prepare(case['source_case'])
        ds = regs['ds']
        # The LEVEL/GROUND loader has completed. Independently reproduce the
        # ordinary DF-clear 378A destination contents before starting 397D.
        flags &= ~DF
        _copy_real_graphics_records(memory, ds)
        regs['ip'] = START
        regs['es'] = ds
        regs['sp'] = 0x8000
        regs['ss'] = 0x7000
        _put_renderer_layout(memory, ds, source_segment=0x5000)
        _put_source_pixels(memory, 0x5000)
    else:
        memory, regs, flags, ds = _base(case)
        # Inactive destination slots remain distinct stale bytes. Active rows
        # use explicit small dimensions and finite source/mask offsets.
        for index, row in enumerate(case['objects']):
            _write_synthetic_object(memory, ds, row, object_type=index % 16)
        _assert_constructed_active_indices(memory, ds, case['objects'])

    # The preceding 378A call leaves ES=DS in the ordinary intact-stack case.
    regs.update(ip=START, es=ds)
    oracle.put16(memory, regs['ss'], regs['sp'], case.get('outer_ip', 0xeed1))
    _assert_original_suffix_intact(memory, regs)
    return memory, regs, flags, (regs['cs'] + 0x09a9) & 0xffff


"""Independent normal-path layout for the 59BB sprite-bank transform.

This is immutable source/output arithmetic only.  It does not model mutable
guest registers or execute the caller or any producer.
"""
from __future__ import annotations

from collections.abc import Sequence
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]

import entity_sprite_layout as layout
from resources import decode_section, section_spans


# The LOOP counts and SI additions are literal values from 59BB..5AC0.  Keep
# source_advance independent of each child's source_size: ADD SI executes once
# per successful child return, even if a future boundary analysis changes.
GROUPS = (
    dict(count=0x12, dx=0x020A, child_entry=0x5B11,
         call_site=0x59CF, return_ip=0x59D2, source_advance=0x28),
    dict(count=0x10, dx=0x030E, child_entry=0x5BB0,
         call_site=0x59DF, return_ip=0x59E2, source_advance=0x54),
    dict(count=0x10, dx=0x020C, child_entry=0x5BB0,
         call_site=0x59EF, return_ip=0x59F2, source_advance=0x30),
    dict(count=0x10, dx=0x020A, child_entry=0x5B11,
         call_site=0x59FF, return_ip=0x5A02, source_advance=0x28),
    dict(count=0x10, dx=0x020C, child_entry=0x5BB0,
         call_site=0x5A0F, return_ip=0x5A12, source_advance=0x30),
    dict(count=0x20, dx=0x030D, child_entry=0x5BB0,
         call_site=0x5A1F, return_ip=0x5A22, source_advance=0x4E),
    dict(count=0x40, dx=0x030A, child_entry=0x5BB0,
         call_site=0x5A2F, return_ip=0x5A32, source_advance=0x3C),
    dict(count=0x30, dx=0x030D, child_entry=0x5BB0,
         call_site=0x5A3F, return_ip=0x5A42, source_advance=0x4E),
    dict(count=0x08, dx=0x020A, child_entry=0x5B11,
         call_site=0x5A4F, return_ip=0x5A52, source_advance=0x28),
    dict(count=0x10, dx=0x0310, child_entry=0x5BB0,
         call_site=0x5A5F, return_ip=0x5A62, source_advance=0x60),
    dict(count=0x10, dx=0x020A, child_entry=0x5B11,
         call_site=0x5A6F, return_ip=0x5A72, source_advance=0x28),
    dict(count=0x08, dx=0x020D, child_entry=0x5BB0,
         call_site=0x5A7F, return_ip=0x5A82, source_advance=0x34),
    dict(count=0x0E, dx=0x040E, child_entry=0x5BB0,
         call_site=0x5A8F, return_ip=0x5A92, source_advance=0x70),
    dict(count=0x10, dx=0x020A, child_entry=0x5B11,
         call_site=0x5A9F, return_ip=0x5AA2, source_advance=0x28),
    dict(count=0x20, dx=0x020A, child_entry=0x5B11,
         call_site=0x5AAF, return_ip=0x5AB2, source_advance=0x28),
)

FINAL_CHILD = dict(child_entry=0x5C06, call_site=0x5AB8,
                   return_ip=0x5ABB, dx=None, source_advance=0x180)
FINAL_SOURCE_SIZE = 0x180
NORMAL_SOURCE_END = 0x5270
NORMAL_IMMEDIATE_SOURCE_END = 0x50F0
NORMAL_OUTPUT_END = 0x194B8
NORMAL_IMMEDIATE_OUTPUT_END = 0x180B8
NOMINAL_GENERATED_BUFFER_PARAGRAPHS = 0x1D0C


def main_source() -> bytes:
    """Decode MAIN.DAT section zero in memory and return its immutable bytes."""
    packed = (ROOT / 'assets' / 'main.dat').read_bytes()
    spans = section_spans(packed)
    if len(spans) != 7:
        raise ValueError(f'expected seven MAIN.DAT sections, found {len(spans)}')
    start, end = spans[0]
    image, _meta = decode_section(packed[start:end])
    if len(image) < NORMAL_SOURCE_END:
        raise ValueError(
            f'MAIN.DAT section zero has {len(image):#x} bytes; '
            f'59BB needs at least {NORMAL_SOURCE_END:#x}')
    return image


def _source_size(child_entry: int, dx: int | None) -> int:
    if child_entry == 0x5C06:
        return FINAL_SOURCE_SIZE
    if dx is None:
        raise ValueError('5B11/5BB0 child requires a DX selector')
    return 2 * ((dx >> 8) & 0xFF) * (dx & 0xFF)


def _leaf_output(child_entry: int, dx: int | None,
                 child_source: bytes) -> tuple[bytes, tuple[int, ...]]:
    if child_entry == 0x5B11:
        if dx is None:
            raise ValueError('5B11 child requires a DX selector')
        banks = layout.expected_5b11(child_source, dx)
    elif child_entry == 0x5BB0:
        if dx is None:
            raise ValueError('5BB0 child requires a DX selector')
        banks = (layout.expected_5bb0(child_source, dx),)
    elif child_entry == 0x5C06:
        banks = layout.expected_5c06(child_source)
    else:
        raise ValueError(f'unsupported sprite child {child_entry:04X}')
    return b''.join(banks), tuple(len(bank) for bank in banks)


def _counts_or_default(counts: Sequence[int] | None) -> tuple[int, ...]:
    if counts is None:
        return tuple(group['count'] for group in GROUPS)
    if (not isinstance(counts, Sequence) or
            isinstance(counts, (str, bytes, bytearray)) or len(counts) != len(GROUPS)):
        raise ValueError(f'counts must be a sequence of exactly {len(GROUPS)} values')
    values = tuple(counts)
    if any(type(value) is not int or not 0 < value <= 0xFFFF for value in values):
        raise ValueError('each constructed group count must be a positive 16-bit integer')
    return values


def expected(source: bytes, counts: Sequence[int] | None = None
             ) -> tuple[bytes, tuple[dict, ...]]:
    """Return normal-layout output and per-call source/output descriptors.

    ``counts`` changes only the fifteen finite outer group counts, for bounded
    constructed-provider cases.  Every child consumes its dimension-derived
    source span; parent SI movement always follows the literal ASM addition.
    """
    if not isinstance(source, bytes):
        raise TypeError('source must be immutable bytes')
    selected_counts = _counts_or_default(counts)
    source_cursor = 0
    output_cursor = 0
    call_index = 0
    output_parts = []
    descriptors = []

    def append_call(group_index: int, frame_index: int, child_entry: int,
                    call_site: int, return_ip: int, dx: int | None,
                    source_advance: int) -> None:
        nonlocal source_cursor, output_cursor, call_index
        source_size = _source_size(child_entry, dx)
        source_end = source_cursor + source_size
        if source_end > len(source):
            raise ValueError(
                f'source span {source_cursor:#x}..{source_end:#x} exceeds '
                f'{len(source):#x} decoded bytes')
        child_source = source[source_cursor:source_end]
        child_output, bank_sizes = _leaf_output(child_entry, dx, child_source)
        descriptor = dict(
            group_index=group_index,
            frame_index=frame_index,
            call_index=call_index,
            child_entry=child_entry,
            call_site=call_site,
            return_ip=return_ip,
            source_offset=source_cursor,
            source_size=source_size,
            source_advance=source_advance,
            output_offset=output_cursor,
            output_size=len(child_output),
            dx=dx,
            bank_sizes=bank_sizes,
        )
        descriptors.append(descriptor)
        output_parts.append(child_output)
        source_cursor += source_advance
        output_cursor += len(child_output)
        call_index += 1

    for group_index, (group, count) in enumerate(zip(GROUPS, selected_counts)):
        for frame_index in range(count):
            append_call(group_index, frame_index, group['child_entry'],
                        group['call_site'], group['return_ip'], group['dx'],
                        group['source_advance'])

    append_call(len(GROUPS), 0, FINAL_CHILD['child_entry'],
                FINAL_CHILD['call_site'], FINAL_CHILD['return_ip'],
                FINAL_CHILD['dx'], FINAL_CHILD['source_advance'])
    result = b''.join(output_parts)

    if counts is None:
        if source_cursor != NORMAL_SOURCE_END or len(result) != NORMAL_OUTPUT_END:
            raise AssertionError('normal sprite transform arithmetic drifted')
        final = descriptors[-1]
        previous = descriptors[-2]
        if (previous['source_offset'] + previous['source_advance'] !=
                NORMAL_IMMEDIATE_SOURCE_END or
                previous['output_offset'] + previous['output_size'] !=
                NORMAL_IMMEDIATE_OUTPUT_END or
                final['source_offset'] != NORMAL_IMMEDIATE_SOURCE_END or
                final['output_offset'] != NORMAL_IMMEDIATE_OUTPUT_END):
            raise AssertionError('normal sprite transform boundary drifted')
    return result, tuple(descriptors)


def input_hashes() -> dict[str, str]:
    """Hashes for the model, its equations, decoder, source asset and parent."""
    paths = (
        'tests/entity_sprite_bank_layout.py',
        'tests/entity_sprite_layout.py',
        'tools/resources.py',
        'tools/common.py',
        'tools/unpack.py',
        'assets/vgalemmi.exe',
        'assets/main.dat',
        'src/game_code_late_after_palette.asm',
    )
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in paths}


if __name__ == '__main__':
    source = main_source()
    result, descriptors = expected(source)
    normal_calls = sum(group['count'] for group in GROUPS)
    source_hash = hashlib.sha256(source).hexdigest()
    print(f'MAIN.DAT section 0: {len(source)} bytes, SHA256 {source_hash}')
    print(f'59BB normal layout: {normal_calls} immediate calls + final 5C06; '
          f'source 0000..{len(source):04X} decoded ({NORMAL_SOURCE_END:04X} used), '
          f'output 00000..{len(result):05X}, {len(result)} bytes')
    print(f'last immediate group ends DS:SI={NORMAL_IMMEDIATE_SOURCE_END:04X}, '
          f'ES:DI={NORMAL_IMMEDIATE_OUTPUT_END:05X}; final 5C06 ends '
          f'DS:SI={NORMAL_SOURCE_END:04X}, ES:DI={NORMAL_OUTPUT_END:05X}; '
          f'nominal generated-buffer base is '
          f'{NOMINAL_GENERATED_BUFFER_PARAGRAPHS * 16 - NORMAL_OUTPUT_END:#x} '
          f'bytes beyond output end')

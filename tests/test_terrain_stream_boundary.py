"""Stopping before a continuation must retain the executed incoming edge."""
import gc
import subprocess
import sys
import unittest
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'),
                str(Path(__file__).resolve().parent)]
import terrain_stream as stream
from bounded_process import run_bounded


def worker():
    stream.common.MAX_BUS_EVENTS = 5_000
    stream.common.MAX_VGA_EVENTS = 1_000
    stream.piece.MAX_STEPS = 100_000
    for redraw in (0, 1):
        entry, finished = stream.RANGES[redraw]
        jump = entry + 0x19
        sentinel_branch = entry + 0x14
        for nonempty in (False, True):
            case = dict(name=f'continuation-edge-{redraw}-{nonempty}',
                        seed=0, redraw=redraw,
                        commands=[stream.command(8191, 5)] if nonempty else [])
            memory, registers, flags, _game_ds = stream.prepare(case)
            device = stream.common.TraceDevice(bytearray(memory), 0x3752)
            actual, _mask, seen, edges, boundary, _child, _body = stream.piece.original(
                case, device, registers, flags, continuations=(finished,))
            if boundary != ('continuation', registers['cs'], finished):
                raise AssertionError(f'Wrong stream boundary: {boundary}')
            if actual['ip'] != finished or finished in seen:
                raise AssertionError('Continuation was counted as an executed instruction')
            expected = {(sentinel_branch, finished)}
            if nonempty:
                expected |= {(sentinel_branch, sentinel_branch + 2), (jump, entry + 3)}
            local_edges = {edge for edge in edges if entry <= edge[0] < finished}
            if local_edges != expected:
                raise AssertionError(f'Lost executed stream edge: {local_edges} != {expected}')
            gc.collect()
    print('PASS terrain continuation edges:4 original-only cases; destination sites unexecuted')


class TerrainStreamBoundaryTests(unittest.TestCase):
    def test_executed_edges_before_unexecuted_continuation(self):
        result = run_bounded(
            [sys.executable, str(Path(__file__).resolve()), '--worker'],
            cwd=stream.ROOT, timeout=15, memory_mib=256,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.assertIn('PASS terrain continuation edges:4', result.stdout)


if __name__ == '__main__':
    if sys.argv[1:] == ['--worker']:
        worker()
    else:
        unittest.main()

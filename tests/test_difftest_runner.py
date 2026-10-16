"""Focused selection must retain native bounds and fail closed."""
import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import difftest


class DifferentialRunnerTests(unittest.TestCase):
    def invoke(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = difftest.main(args)
        return result, output.getvalue()

    def test_invalid_or_ambiguous_selections_cannot_start_workers(self):
        for args in ([], ['--plan'], ['drawing_clip', 'missing'],
                     ['../assets/vgalemmi'], ['--all', 'drawing_clip'],
                     ['--list', '--all'], ['--list', '--plan']):
            with self.subTest(args=args), patch.object(difftest, 'run_bounded') as run:
                with self.assertRaises(SystemExit) as error:
                    self.invoke(args)
                self.assertEqual(error.exception.code, 2)
                run.assert_not_called()

    def test_listing_and_planning_do_not_execute_tests(self):
        with patch.object(difftest, 'run_bounded') as run:
            _, listing = self.invoke(['--list'])
            self.assertIn('terrain_stream: timeout=14460s process_commit=512MiB', listing)
            _, plan = self.invoke(['display_status', 'drawing_clip', '--plan'])
            self.assertEqual(plan.splitlines(), [
                'display_status: timeout=180s process_commit=384MiB',
                'drawing_clip: timeout=120s process_commit=512MiB'])
            self.assertNotIn('PASS', plan)
            run.assert_not_called()

    def test_focused_runs_preserve_order_deduplicate_and_keep_bounds(self):
        with patch.object(difftest, 'run_bounded') as run:
            result, output = self.invoke(['display_status', 'drawing_clip', 'display_status'])
            self.assertEqual(result, 0)
            self.assertEqual(run.call_count, 2)
            for call, name, timeout, memory in zip(run.call_args_list,
                    ('display_status', 'drawing_clip'), (180, 120), (384, 512)):
                self.assertEqual(call.args[0], [sys.executable, str(ROOT / 'tests' / (name + '.py'))])
                self.assertEqual(call.kwargs, dict(cwd=ROOT, timeout=timeout,
                                                  memory_mib=memory, check=True))
            self.assertIn('PASS 2 selected suites', output)

    def test_full_campaign_remains_explicit_and_complete(self):
        with patch.object(difftest, 'run_bounded') as run:
            self.invoke(['--all'])
        self.assertEqual(len(difftest.SUITES), 106)
        self.assertEqual(len({s.name for s in difftest.SUITES}), 106)
        self.assertEqual([Path(c.args[0][1]).stem for c in run.call_args_list],
                         [s.name for s in difftest.SUITES])
        for suite, call in zip(difftest.SUITES, run.call_args_list):
            self.assertGreater(suite.timeout, 0)
            self.assertGreater(suite.memory_mib, 0)
            self.assertEqual(call.kwargs['timeout'], suite.timeout)
            self.assertEqual(call.kwargs['memory_mib'], suite.memory_mib)
            self.assertTrue(call.kwargs['check'])

    def test_native_failure_stops_campaign_without_success_credit(self):
        failure = subprocess.CalledProcessError(86, ['constructed-worker'])
        output = io.StringIO()
        with patch.object(difftest, 'run_bounded', side_effect=failure) as run:
            with contextlib.redirect_stdout(output), self.assertRaises(subprocess.CalledProcessError):
                difftest.main(['drawing_clip', 'display_status'])
            self.assertEqual(run.call_count, 1)
        self.assertNotIn('PASS', output.getvalue())

    def test_timeout_is_a_failure_and_stops_the_campaign(self):
        failure = subprocess.TimeoutExpired(['constructed-worker'], 120)
        with patch.object(difftest, 'run_bounded', side_effect=failure) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.invoke(['drawing_clip', 'display_status'])
            self.assertEqual(run.call_count, 1)

    def test_missing_later_suite_file_prevents_any_native_work(self):
        exists = Path.is_file

        def missing(path):
            return False if path.name == 'display_status.py' else exists(path)

        with patch.object(Path, 'is_file', missing), patch.object(difftest, 'run_bounded') as run:
            with self.assertRaises(SystemExit):
                self.invoke(['drawing_clip', 'display_status'])
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()

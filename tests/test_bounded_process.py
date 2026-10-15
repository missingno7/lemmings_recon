"""Regression checks for native hangs, commit growth, and worker cleanup."""
import os
import ctypes
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from bounded_process import run_bounded, temporary_build_directory
import bounded_process


class BoundedProcessTests(unittest.TestCase):
    def test_success_and_nonzero_exit(self):
        result = run_bounded([sys.executable, '-c', 'print("finished")'],
                             timeout=5, stdout=subprocess.PIPE, text=True)
        self.assertEqual(result.stdout.strip(), 'finished')
        with self.assertRaises(subprocess.CalledProcessError) as error:
            run_bounded([sys.executable, '-c', 'raise SystemExit(7)'], timeout=5)
        self.assertEqual(error.exception.returncode, 7)

    def test_timeout_reaps_worker(self):
        launched = []
        original = subprocess.Popen

        def record(*args, **kwargs):
            process = original(*args, **kwargs)
            launched.append(process)
            return process

        with patch('bounded_process.subprocess.Popen', side_effect=record):
            with self.assertRaises(subprocess.TimeoutExpired):
                run_bounded([sys.executable, '-c', 'while True: pass'], timeout=1)
        self.assertEqual(len(launched), 1)
        self.assertIsNotNone(launched[0].poll())

    @unittest.skipUnless(os.name == 'nt', 'Windows suspended launch')
    def test_child_cannot_execute_before_job_is_installed(self):
        with temporary_build_directory(prefix='job-start-regression-',
                                       parent=ROOT / 'build') as directory:
            marker = Path(directory) / 'executed'
            install = bounded_process._windows_job

            def delayed_install(process, memory_mib):
                time.sleep(0.3)
                self.assertFalse(marker.exists(), 'Child ran before job setup')
                return install(process, memory_mib)

            code = 'import pathlib,sys; pathlib.Path(sys.argv[1]).touch()'
            with patch('bounded_process._windows_job', side_effect=delayed_install):
                run_bounded([sys.executable, '-c', code, str(marker)], timeout=5)
            self.assertTrue(marker.exists(), 'Guarded child never executed')

    @unittest.skipUnless(os.name == 'nt', 'Windows suspended launch')
    def test_failed_job_setup_reaps_child_without_executing_it(self):
        with temporary_build_directory(prefix='job-failure-regression-',
                                       parent=ROOT / 'build') as directory:
            marker = Path(directory) / 'executed'

            def reject_install(process, memory_mib):
                time.sleep(0.3)
                raise RuntimeError('Constructed job setup failure')

            code = 'import pathlib,sys; pathlib.Path(sys.argv[1]).touch()'
            with patch('bounded_process._windows_job', side_effect=reject_install):
                with self.assertRaisesRegex(RuntimeError, 'job setup failure'):
                    run_bounded([sys.executable, '-c', code, str(marker)], timeout=5)
            self.assertFalse(marker.exists(), 'Unguarded child executed')

    @unittest.skipUnless(os.name == 'nt', 'Windows commit ceiling')
    def test_memory_ceiling_rejects_allocation(self):
        # Request only 256 MiB, far below host exhaustion, under a 64 MiB cap.
        code = ('import time; time.sleep(0.1)\n'
                'try: data = bytearray(256 * 1024 * 1024)\n'
                'except MemoryError: raise SystemExit(77)\n'
                'raise SystemExit(0)')
        result = run_bounded([sys.executable, '-c', code], timeout=5,
                             memory_mib=64, check=False)
        self.assertEqual(result.returncode, 77)

    @unittest.skipUnless(os.name == 'nt', 'Windows process-tree cleanup')
    def test_timeout_also_terminates_descendant(self):
        with temporary_build_directory(prefix='child-tree-regression-',
                                       parent=ROOT / 'build') as directory:
            pid_path = Path(directory) / 'child.pid'
            code = ('import subprocess, sys, pathlib\n'
                    'child = subprocess.Popen([sys.executable, "-c", '
                    '"while True: pass"])\n'
                    'pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n'
                    'while True: pass')
            with self.assertRaises(subprocess.TimeoutExpired):
                run_bounded([sys.executable, '-c', code, str(pid_path)], timeout=2)
            pid = int(pid_path.read_text())
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int,
                                          ctypes.c_uint32]
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel.WaitForSingleObject.restype = ctypes.c_uint32
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.OpenProcess(0x100000, False, pid)
            if handle:
                try:
                    self.assertEqual(kernel.WaitForSingleObject(handle, 1000), 0)
                finally:
                    kernel.CloseHandle(handle)

    def test_runaway_clipping_trace_exits_at_budget(self):
        build = ROOT / 'build'
        build.mkdir(exist_ok=True)
        with temporary_build_directory(prefix='clip-budget-regression-',
                                       parent=build) as directory:
            result = run_bounded([sys.executable, str(ROOT / 'tests/drawing_clip.py'),
                                  '--runaway-probe', directory], cwd=ROOT,
                                 timeout=15, check=False, stderr=subprocess.PIPE,
                                 text=True)
            self.assertEqual(result.returncode, 86, result.stderr)
            self.assertIn('native access budget exceeded', result.stderr)
        self.assertFalse(Path(directory).exists())

    def test_null_bus_native_hang_is_killed_and_artifacts_removed(self):
        with temporary_build_directory(prefix='clip-timeout-regression-',
                                       parent=ROOT / 'build') as directory:
            with self.assertRaises(subprocess.TimeoutExpired):
                run_bounded([sys.executable, str(ROOT / 'tests/drawing_clip.py'),
                             '--null-runaway-probe', directory], cwd=ROOT, timeout=5)
        self.assertFalse(Path(directory).exists())


if __name__ == '__main__':
    unittest.main()

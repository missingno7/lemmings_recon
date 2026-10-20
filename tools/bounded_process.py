"""Terminate test subprocesses on timeout; cap Windows process-tree commit."""
import ctypes
import os
import subprocess
import tempfile
import shutil
import uuid
from pathlib import Path
import time
from ctypes import wintypes
from contextlib import contextmanager


DEFAULT_MEMORY_MIB = 512


@contextmanager
def temporary_build_directory(*, prefix, parent):
    """Remove owned DLLs, allowing a bounded Windows image-release delay."""
    # Python3.12's Windows mkdir(0700) replaces the inherited DACL. A restricted
    # workspace token can then lose access to its own directory. Keep the
    # workspace ACL on Windows; retain private tempfile permissions elsewhere.
    directory = None
    if os.name == 'nt':
        path = Path(parent) / (prefix + uuid.uuid4().hex)
        path.mkdir()
    else:
        directory = tempfile.TemporaryDirectory(prefix=prefix, dir=parent)
        path = Path(directory.name)
    try:
        yield str(path)
    finally:
        for attempt in range(40):
            try:
                if directory is None:
                    shutil.rmtree(path)
                else:
                    directory.cleanup()
                break
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.05)


class _BasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', wintypes.DWORD), ('minimum_working_set', ctypes.c_size_t),
                ('maximum_working_set', ctypes.c_size_t),
                ('active_process_limit', wintypes.DWORD), ('affinity', ctypes.c_size_t),
                ('priority_class', wintypes.DWORD), ('scheduling_class', wintypes.DWORD)]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ('read_operations', 'write_operations', 'other_operations',
                 'read_bytes', 'write_bytes', 'other_bytes')]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [('basic', _BasicLimits), ('io', _IoCounters),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t),
                ('peak_job_memory', ctypes.c_size_t)]


def _windows_job(process, memory_mib):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                              ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        limits = _ExtendedLimits()
        # PROCESS_MEMORY, JOB_MEMORY, KILL_ON_JOB_CLOSE. Children inherit the job.
        limits.basic.flags = 0x100 | 0x200 | 0x2000
        limits.process_memory = memory_mib * 1024 * 1024
        limits.job_memory = (memory_mib + 256) * 1024 * 1024
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits),
                                              ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        handle = kernel.OpenProcess(0x100 | 0x1, False, process.pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not kernel.AssignProcessToJobObject(job, handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)
    except BaseException:
        kernel.CloseHandle(job)
        raise
    return kernel, job


def _resume_windows_process(process):
    # Popen closes the primary thread handle. Resume the suspended process by
    # process handle only after its job is installed. If this API is unavailable
    # or fails, the caller reaps the still-suspended child without running it.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    native = ctypes.WinDLL('ntdll')
    native.NtResumeProcess.argtypes = [wintypes.HANDLE]
    native.NtResumeProcess.restype = ctypes.c_int32
    handle = kernel.OpenProcess(0x0800, False, process.pid)  # PROCESS_SUSPEND_RESUME
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        status = native.NtResumeProcess(handle)
        if status != 0:
            raise OSError(f'NtResumeProcess failed: NTSTATUS {status & 0xffffffff:08X}')
    finally:
        kernel.CloseHandle(handle)


def run_bounded(args, *, timeout, memory_mib=DEFAULT_MEMORY_MIB, check=True,
                **kwargs):
    """Like subprocess.run, with guaranteed reaping and a Windows commit ceiling.

    A timeout is a failed check, never evidence of a differential mismatch.
    Windows children start suspended until their job limits are installed, so
    even redirectors cannot launch descendants outside the job during setup.
    Closing the Windows job also terminates any remaining compiler/test children.
    Other hosts retain the wall-clock bound; memory limits here are Windows-only.
    """
    if timeout <= 0 or memory_mib <= 0:
        raise ValueError('Test limits must be positive')
    if os.name == 'nt':
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | 0x00000004
    process = subprocess.Popen(args, **kwargs)
    job = None
    try:
        if os.name == 'nt':
            job = _windows_job(process, memory_mib)
            _resume_windows_process(process)
        stdout, stderr = process.communicate(timeout=timeout)
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result
    finally:
        if job is not None:
            kernel, handle = job
            kernel.CloseHandle(handle)
        if process.poll() is None:
            process.kill()
        process.wait()

#!/usr/bin/env python3
# Part A - Policy engine & configuration
# Author: Ankit Ray (24BCE0497)
"""Platform-aware enforcement helpers for cpu-affinity-agent.

Thin wrappers around the kernel operations: set CPU affinity and set the
scheduling priority (nice). On Linux they call the native os.sched_* functions;
elsewhere they fall back to psutil so the agent still runs for development.
"""

from __future__ import annotations

import os
from typing import Any

import psutil

IS_POSIX = os.name == "posix"
HAS_SCHED_AFFINITY = hasattr(os, "sched_setaffinity")


def _nice_for_platform(nice_value: int) -> Any:
    """Translate a POSIX nice value to whatever the current OS expects.

    On POSIX the integer is used directly. On Windows there is no nice value,
    so we map ranges onto Win32 priority classes; this keeps the same config
    working for development/testing on Windows.
    """
    if IS_POSIX:
        return nice_value
    # Windows priority-class mapping (lower nice => higher priority).
    if nice_value <= -15:
        return psutil.REALTIME_PRIORITY_CLASS
    if nice_value <= -8:
        return psutil.HIGH_PRIORITY_CLASS
    if nice_value < 0:
        return psutil.ABOVE_NORMAL_PRIORITY_CLASS
    if nice_value == 0:
        return psutil.NORMAL_PRIORITY_CLASS
    if nice_value <= 9:
        return psutil.BELOW_NORMAL_PRIORITY_CLASS
    return psutil.IDLE_PRIORITY_CLASS


def set_affinity(proc: psutil.Process, cores: list[int]) -> None:
    """Pin a process to a set of logical CPUs.

    Prefers the native os.sched_setaffinity on Linux (the direct syscall
    wrapper); falls back to psutil elsewhere.
    """
    if HAS_SCHED_AFFINITY:
        os.sched_setaffinity(proc.pid, set(cores))
    else:
        proc.cpu_affinity(cores)


def get_affinity(proc: psutil.Process) -> list[int]:
    if HAS_SCHED_AFFINITY:
        return sorted(os.sched_getaffinity(proc.pid))
    return sorted(proc.cpu_affinity())


def set_nice(proc: psutil.Process, nice_value: int) -> None:
    proc.nice(_nice_for_platform(nice_value))

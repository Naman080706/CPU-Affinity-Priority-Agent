#!/usr/bin/env python3
# Part A - Policy engine & configuration
# Author: Ankit Ray (24BCE0497)
"""Matching engine for cpu-affinity-agent.

Pure logic that decides whether a process matches a rule. No system calls, so
it can be unit tested on any platform with plain dictionaries.
"""

from __future__ import annotations

from typing import Any

from .config import Rule


def process_matches(rule: Rule, proc_info: dict[str, Any]) -> bool:
    """Return True if a process (described by psutil-style info) matches a rule.

    Supported match keys (all present keys must match -> logical AND):
      name            : exact process name, case-insensitive
      name_regex      : regex tested against the process name
      cmdline_contains: substring that must appear in the joined command line
      pid             : exact process id
      user            : owning username (exact)
    """
    m = rule.match
    name = (proc_info.get("name") or "")
    cmdline = " ".join(proc_info.get("cmdline") or [])

    if "name" in m and name.lower() != str(m["name"]).lower():
        return False
    if rule._name_regex is not None and not rule._name_regex.search(name):
        return False
    if "cmdline_contains" in m and str(m["cmdline_contains"]) not in cmdline:
        return False
    if "pid" in m and proc_info.get("pid") != int(m["pid"]):
        return False
    if "user" in m and proc_info.get("username") != m["user"]:
        return False
    return True

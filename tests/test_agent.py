# Part B - Daemon, service & packaging
# Author: Naman Jain (24BKT0140)
"""Tests for the Agent daemon (poll cycle, dry-run, applied-state cache).

These exercise the service layer in agent.py, which drives the Part A engine.

Run:  python -m pytest tests/test_agent.py -v
  or:  python tests/test_agent.py        (no pytest required)
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psutil  # noqa: E402

from cpu_affinity_agent.agent import Agent  # noqa: E402
from cpu_affinity_agent.config import Config  # noqa: E402
from cpu_affinity_agent.enforcement import get_affinity  # noqa: E402


def test_dry_run_cycle_marks_self():
    me = psutil.Process()
    cfg = Config.from_dict({
        "poll_interval_seconds": 1,
        "dry_run": True,
        "rules": [{"name": "match-self", "match": {"pid": me.pid}, "nice": 1}],
    })
    agent = Agent("<memory>", cfg)
    acted = agent.run_cycle()
    assert acted >= 1
    assert me.pid in agent._applied
    # Second cycle should be a no-op (already applied, nothing changed).
    assert agent.run_cycle() == 0


def test_run_cycle_enforces_on_child():
    """End-to-end: the Agent pins a real child process in a single cycle."""
    ncpu = psutil.cpu_count(logical=True) or 1
    if ncpu < 2:
        return  # need at least 2 logical CPUs
    try:
        psutil.Process().cpu_affinity()
    except (AttributeError, NotImplementedError, psutil.AccessDenied):
        return  # affinity not supported here

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        time.sleep(0.2)
        cfg = Config.from_dict({
            "poll_interval_seconds": 1,
            "dry_run": False,
            "rules": [{"name": "pin-child",
                       "match": {"pid": child.pid},
                       "cpu_affinity": [0, 1], "nice": 5}],
        })
        agent = Agent("<memory>", cfg)
        acted = agent.run_cycle()
        assert acted >= 1
        assert set(get_affinity(psutil.Process(child.pid))) == {0, 1}
    finally:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()


# --------------------------------------------------------------------------- #
# Allow `python tests/test_agent.py` without pytest installed
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    failures = 0
    for fname, fn in sorted(dict(globals()).items()):
        if fname.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {fname}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"FAIL {fname}: {exc!r}")
    print(f"\n{'OK' if failures == 0 else 'FAILED'} ({failures} failure(s))")
    sys.exit(1 if failures else 0)

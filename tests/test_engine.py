# Part A - Policy engine & configuration
# Author: Ankit Ray (24BCE0497)
"""Unit + integration tests for the policy engine (config, matching, enforcement).

The config loader and matching engine are pure logic and run on any OS.
The affinity integration test spawns a real child process and pins it; it is
skipped automatically if the platform/CPU cannot support the requested cores.

Run:  python -m pytest tests/test_engine.py -v
  or:  python tests/test_engine.py        (no pytest required)
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import psutil  # noqa: E402
import pytest  # noqa: E402

from cpu_affinity_agent.config import Config, Rule  # noqa: E402
from cpu_affinity_agent.enforcement import get_affinity, set_affinity  # noqa: E402
from cpu_affinity_agent.matching import process_matches  # noqa: E402


# --------------------------------------------------------------------------- #
# Config loading / validation
# --------------------------------------------------------------------------- #
def test_config_from_dict_ok():
    cfg = Config.from_dict({
        "poll_interval_seconds": 2,
        "rules": [{"name": "r1", "match": {"name": "x"}, "nice": 5}],
    })
    assert cfg.poll_interval_seconds == 2
    assert len(cfg.rules) == 1
    assert cfg.rules[0].nice == 5


def test_rule_requires_action():
    with pytest.raises(ValueError):
        Rule(name="bad", match={"name": "x"})  # no affinity, no nice


def test_rule_rejects_bad_nice():
    with pytest.raises(ValueError):
        Rule(name="bad", match={"name": "x"}, nice=99)


def test_rule_rejects_empty_match():
    with pytest.raises(ValueError):
        Rule(name="bad", match={}, nice=1)


def test_rule_rejects_bad_affinity():
    with pytest.raises(ValueError):
        Rule(name="bad", match={"name": "x"}, cpu_affinity=[-1])


def test_config_rejects_nonpositive_interval():
    with pytest.raises(ValueError):
        Config.from_dict({"poll_interval_seconds": 0, "rules": []})


# --------------------------------------------------------------------------- #
# Matching engine
# --------------------------------------------------------------------------- #
def test_match_name_exact_case_insensitive():
    rule = Rule(name="r", match={"name": "NGINX"}, nice=0)
    assert process_matches(rule, {"pid": 1, "name": "nginx", "cmdline": []})
    assert not process_matches(rule, {"pid": 1, "name": "apache", "cmdline": []})


def test_match_regex():
    rule = Rule(name="r", match={"name_regex": "^cc1(plus)?$"}, nice=0)
    assert process_matches(rule, {"pid": 1, "name": "cc1", "cmdline": []})
    assert process_matches(rule, {"pid": 1, "name": "cc1plus", "cmdline": []})
    assert not process_matches(rule, {"pid": 1, "name": "gcc", "cmdline": []})


def test_match_cmdline_contains():
    rule = Rule(name="r", match={"cmdline_contains": "rsync"}, nice=0)
    assert process_matches(
        rule, {"pid": 1, "name": "sh", "cmdline": ["/bin/sh", "-c", "rsync -a a b"]}
    )
    assert not process_matches(
        rule, {"pid": 1, "name": "sh", "cmdline": ["/bin/sh", "-c", "cp a b"]}
    )


def test_match_pid():
    rule = Rule(name="r", match={"pid": 42}, nice=0)
    assert process_matches(rule, {"pid": 42, "name": "x", "cmdline": []})
    assert not process_matches(rule, {"pid": 7, "name": "x", "cmdline": []})


def test_match_is_logical_and():
    rule = Rule(name="r", match={"name": "python", "cmdline_contains": "worker"}, nice=0)
    assert process_matches(
        rule, {"pid": 1, "name": "python", "cmdline": ["python", "worker.py"]}
    )
    assert not process_matches(
        rule, {"pid": 1, "name": "python", "cmdline": ["python", "main.py"]}
    )


def test_match_handles_missing_fields():
    rule = Rule(name="r", match={"name": "x"}, nice=0)
    # No name/cmdline present -> should simply not match, not raise.
    assert not process_matches(rule, {"pid": 1})


# --------------------------------------------------------------------------- #
# Real affinity integration test (spawns a sleeping child process)
# --------------------------------------------------------------------------- #
def test_set_and_get_affinity_on_child():
    ncpu = psutil.cpu_count(logical=True) or 1
    if ncpu < 2:
        pytest.skip("need at least 2 logical CPUs")
    try:
        psutil.Process().cpu_affinity()
    except (AttributeError, NotImplementedError, psutil.AccessDenied):
        pytest.skip("cpu_affinity not supported on this platform")

    # A short-lived child we are allowed to control (same user).
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    try:
        proc = psutil.Process(child.pid)
        time.sleep(0.2)
        target = [0, 1]
        set_affinity(proc, target)
        got = get_affinity(proc)
        assert set(got) == set(target), f"expected {target}, got {got}"
    finally:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()


# --------------------------------------------------------------------------- #
# Allow `python tests/test_engine.py` without pytest installed
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    failures = 0
    for fname, fn in sorted(dict(globals()).items()):
        if fname.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {fname}")
            except Exception as exc:  # noqa: BLE001
                if exc.__class__.__name__ == "Skipped":
                    print(f"SKIP {fname}: {exc}")
                else:
                    failures += 1
                    print(f"FAIL {fname}: {exc!r}")
    print(f"\n{'OK' if failures == 0 else 'FAILED'} ({failures} failure(s))")
    sys.exit(1 if failures else 0)

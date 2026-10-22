# Contributors

This project was built by two people. The code is split into two parts with no
shared files, so each person owns a clear set of modules and the two sets merge
cleanly in git.

| Author | Reg. No. | GitHub | Part |
|--------|----------|--------|------|
| Ankit Ray | 24BCE0497 | _(add handle)_ | Part A - Policy engine & configuration |
| Naman Jain | 24BKT0140 | Naman080706 | Part B - Daemon, service & packaging |

## Part A - Policy engine & configuration (Ankit Ray)

The pure logic that decides what to do, with no long-running service and no
direct dependence on Part B.

- `cpu_affinity_agent/config.py` - `Rule` and `Config`: load and validate the JSON rules.
- `cpu_affinity_agent/matching.py` - `process_matches()`: test a process against a rule.
- `cpu_affinity_agent/enforcement.py` - `set_affinity()` / `set_nice()`: the kernel calls.
- `config/agent.json` - sample rules.
- `tests/test_engine.py` - unit tests for the above plus a real affinity test.

## Part B - Daemon, service & packaging (Naman Jain)

The long-running service that drives the Part A engine, plus everything needed
to install and run it as a systemd service.

- `cpu_affinity_agent/agent.py` - the `Agent` daemon: poll loop, signal handling, sd_notify, CLI.
- `cpu_affinity_agent/__init__.py` - package init and lazy re-exports.
- `systemd/cpu-affinity-agent.service` - the systemd unit.
- `install.sh`, `requirements.txt` - installation.
- `tests/test_agent.py` - tests for the daemon and an end-to-end enforcement test.
- `README.md` - documentation.

Part B imports Part A (`from .config import Config`, etc.). Part A never imports
Part B, so the engine can be tested on its own.

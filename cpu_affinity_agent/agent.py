#!/usr/bin/env python3
# Part B - Daemon, service & packaging
# Author: Naman Jain (24BKT0140)
"""cpu-affinity-agent: the daemon.

A headless (no-UI) agent, designed to run as a systemd service on Ubuntu Linux.
It enforces CPU affinity (which logical cores a process may run on) and
scheduling priority (the POSIX "nice" value) for processes matched by a set of
user-defined rules.

This module owns the long-running service: the poll loop, signal handling,
systemd readiness notification, and the command-line entry point. The policy
engine it drives (configuration, matching, enforcement) lives in the sibling
modules config.py, matching.py and enforcement.py.

Primary target        : Ubuntu Linux, run under systemd (Type=notify/simple).
Logging               : stdout/stderr -> captured by journald (journalctl).
Reconfigure           : SIGHUP reloads the config without restarting.
Graceful shutdown     : SIGTERM / SIGINT.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from typing import Any

import psutil

from .config import Config, Rule
from .enforcement import HAS_SCHED_AFFINITY, set_affinity, set_nice
from .matching import process_matches

IS_POSIX = os.name == "posix"

log = logging.getLogger("cpu-affinity-agent")


# --------------------------------------------------------------------------- #
# The agent
# --------------------------------------------------------------------------- #
class Agent:
    def __init__(self, config_path: str, config: Config) -> None:
        self.config_path = config_path
        self.config = config
        self._running = True
        self._reload_requested = False
        # Remember what we have already applied so we only log/act on changes:
        # key = pid, value = (rule_name, tuple(affinity) | None, nice | None)
        self._applied: dict[int, tuple[str, tuple[int, ...] | None, int | None]] = {}
        self._online_cpus = self._detect_online_cpus()

    @staticmethod
    def _detect_online_cpus() -> set[int]:
        if HAS_SCHED_AFFINITY:
            return set(os.sched_getaffinity(0))
        return set(range(psutil.cpu_count(logical=True) or 1))

    # -- signal handlers -------------------------------------------------- #
    def request_stop(self, *_: Any) -> None:
        log.info("shutdown signal received; stopping after current cycle")
        self._running = False

    def request_reload(self, *_: Any) -> None:
        log.info("SIGHUP received; config reload requested")
        self._reload_requested = True

    def _reload(self) -> None:
        try:
            self.config = Config.load(self.config_path)
            self._applied.clear()
            log.info(
                "config reloaded: %d rule(s), interval=%.1fs, dry_run=%s",
                len(self.config.rules),
                self.config.poll_interval_seconds,
                self.config.dry_run,
            )
        except Exception as exc:  # noqa: BLE001 - keep running on bad reload
            log.error("config reload failed, keeping previous config: %s", exc)
        self._reload_requested = False

    # -- enforcement ------------------------------------------------------ #
    def _enforce_on(self, proc: psutil.Process, info: dict[str, Any], rule: Rule) -> None:
        pid = info["pid"]
        want_aff = tuple(sorted(rule.cpu_affinity)) if rule.cpu_affinity else None
        want_nice = rule.nice
        prev = self._applied.get(pid)
        if prev == (rule.name, want_aff, want_nice):
            return  # already enforced for this pid; nothing changed

        label = f"{info.get('name')}({pid})"
        if self.config.dry_run:
            log.info(
                "[dry-run] would apply rule '%s' to %s: affinity=%s nice=%s",
                rule.name, label, want_aff, want_nice,
            )
            self._applied[pid] = (rule.name, want_aff, want_nice)
            return

        try:
            if want_aff is not None:
                cores = [c for c in want_aff if c in self._online_cpus]
                if not cores:
                    log.warning(
                        "rule '%s': none of %s are online CPUs %s; skipping affinity",
                        rule.name, list(want_aff), sorted(self._online_cpus),
                    )
                else:
                    set_affinity(proc, cores)
            if want_nice is not None:
                set_nice(proc, want_nice)
            self._applied[pid] = (rule.name, want_aff, want_nice)
            log.info(
                "applied rule '%s' to %s: affinity=%s nice=%s",
                rule.name, label, want_aff, want_nice,
            )
        except psutil.NoSuchProcess:
            self._applied.pop(pid, None)
        except psutil.AccessDenied:
            log.warning(
                "access denied applying rule '%s' to %s "
                "(agent likely needs root/CAP_SYS_NICE)", rule.name, label,
            )
        except (OSError, ValueError) as exc:
            log.error("error applying rule '%s' to %s: %s", rule.name, label, exc)

    def run_cycle(self) -> int:
        """Scan all processes once and apply rules. Returns #processes acted on."""
        acted = 0
        seen: set[int] = set()
        attrs = ["pid", "name", "cmdline", "username"]
        for proc in psutil.process_iter(attrs=attrs):
            try:
                info = proc.info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            seen.add(info["pid"])
            for rule in self.config.rules:
                if process_matches(rule, info):
                    before = self._applied.get(info["pid"])
                    self._enforce_on(proc, info, rule)
                    if self._applied.get(info["pid"]) != before:
                        acted += 1
                    break  # first matching rule wins
        # Forget pids that have exited so the cache does not grow forever.
        for dead in set(self._applied) - seen:
            self._applied.pop(dead, None)
        return acted

    def run(self) -> None:
        log.info(
            "cpu-affinity-agent starting: %d rule(s), interval=%.1fs, "
            "online CPUs=%s, dry_run=%s, backend=%s",
            len(self.config.rules),
            self.config.poll_interval_seconds,
            sorted(self._online_cpus),
            self.config.dry_run,
            "os.sched_*" if HAS_SCHED_AFFINITY else "psutil",
        )
        _notify_systemd("READY=1")
        while self._running:
            if self._reload_requested:
                self._reload()
            try:
                acted = self.run_cycle()
                if acted:
                    log.debug("cycle complete: %d process(es) (re)configured", acted)
            except Exception as exc:  # noqa: BLE001 - never die on a transient error
                log.error("error during scan cycle: %s", exc)
            # Sleep in small slices so signals are handled promptly.
            slept = 0.0
            while slept < self.config.poll_interval_seconds and self._running:
                if self._reload_requested:
                    break
                time.sleep(min(0.5, self.config.poll_interval_seconds - slept))
                slept += 0.5
        _notify_systemd("STOPPING=1")
        log.info("cpu-affinity-agent stopped")


# --------------------------------------------------------------------------- #
# systemd sd_notify (optional; only if the service is Type=notify)
# --------------------------------------------------------------------------- #
def _notify_systemd(state: str) -> None:
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr or not IS_POSIX:
        return
    try:
        import socket

        if addr[0] == "@":  # abstract namespace
            addr = "\0" + addr[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(addr)
            sock.sendall(state.encode())
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def _default_config_path() -> str:
    for candidate in ("/etc/cpu-affinity-agent/config.json",
                      os.path.join(os.path.dirname(__file__), "..", "config", "agent.json")):
        if os.path.exists(candidate):
            return os.path.abspath(candidate)
    return "/etc/cpu-affinity-agent/config.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CPU Affinity & Priority Agent")
    parser.add_argument(
        "-c", "--config", default=_default_config_path(),
        help="path to JSON config (default: %(default)s)",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="run a single enforcement cycle and exit (useful for testing)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="validate the config file and exit",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    try:
        config = Config.load(args.config)
    except FileNotFoundError:
        log.error("config file not found: %s", args.config)
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        log.error("invalid config %s: %s", args.config, exc)
        return 2

    if args.check:
        log.info("config OK: %d rule(s)", len(config.rules))
        return 0

    agent = Agent(args.config, config)

    if args.once:
        agent.run_cycle()
        return 0

    signal.signal(signal.SIGTERM, agent.request_stop)
    signal.signal(signal.SIGINT, agent.request_stop)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, agent.request_reload)

    agent.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

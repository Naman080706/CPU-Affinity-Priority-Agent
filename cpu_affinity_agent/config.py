#!/usr/bin/env python3
# Part A - Policy engine & configuration
# Author: Ankit Ray (24BCE0497)
"""Configuration model for cpu-affinity-agent.

Defines the Rule and Config dataclasses and the loading/validation logic that
turns a JSON file into validated objects. No system calls happen here, so this
module is pure and easy to test.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Rule:
    """A single enforcement rule."""

    name: str
    match: dict[str, Any]
    cpu_affinity: list[int] | None = None
    nice: int | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("rule is missing a 'name'")
        if not isinstance(self.match, dict) or not self.match:
            raise ValueError(f"rule '{self.name}' has an empty/invalid 'match'")
        if self.cpu_affinity is None and self.nice is None:
            raise ValueError(
                f"rule '{self.name}' must set 'cpu_affinity' and/or 'nice'"
            )
        if self.cpu_affinity is not None:
            if (
                not isinstance(self.cpu_affinity, list)
                or not self.cpu_affinity
                or not all(isinstance(c, int) and c >= 0 for c in self.cpu_affinity)
            ):
                raise ValueError(
                    f"rule '{self.name}': 'cpu_affinity' must be a non-empty "
                    "list of non-negative integers"
                )
        if self.nice is not None and not (-20 <= self.nice <= 19):
            raise ValueError(
                f"rule '{self.name}': 'nice' must be within [-20, 19]"
            )
        # Pre-compile a regex match if present so matching stays cheap.
        self._name_regex = (
            re.compile(self.match["name_regex"]) if "name_regex" in self.match else None
        )


@dataclass
class Config:
    poll_interval_seconds: float = 5.0
    dry_run: bool = False
    rules: list[Rule] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Config":
        if not isinstance(data, dict):
            raise ValueError("config root must be a JSON object")
        interval = float(data.get("poll_interval_seconds", 5.0))
        if interval <= 0:
            raise ValueError("'poll_interval_seconds' must be > 0")
        rules_raw = data.get("rules", [])
        if not isinstance(rules_raw, list):
            raise ValueError("'rules' must be a list")
        rules = [
            Rule(
                name=r.get("name", ""),
                match=r.get("match", {}),
                cpu_affinity=r.get("cpu_affinity"),
                nice=r.get("nice"),
            )
            for r in rules_raw
        ]
        return Config(
            poll_interval_seconds=interval,
            dry_run=bool(data.get("dry_run", False)),
            rules=rules,
        )

    @staticmethod
    def load(path: str) -> "Config":
        with open(path, encoding="utf-8") as fh:
            return Config.from_dict(json.load(fh))

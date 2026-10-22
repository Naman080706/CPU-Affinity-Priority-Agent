# Part B - Daemon, service & packaging
# Author: Naman Jain (24BKT0140)
"""cpu-affinity-agent package.

Convenience re-exports so callers can do `from cpu_affinity_agent import Agent`.
Imports are lazy (PEP 562) so that `python -m cpu_affinity_agent.agent` starts
without the "module found in sys.modules" RuntimeWarning.

The implementation is split across:
  config.py       - Rule, Config          (Part A, Ankit Ray)
  matching.py     - process_matches        (Part A, Ankit Ray)
  enforcement.py  - set_affinity, set_nice (Part A, Ankit Ray)
  agent.py        - Agent, main            (Part B, Naman Jain)
"""

__version__ = "1.0.0"

__all__ = ["Agent", "Config", "Rule", "main", "__version__"]


def __getattr__(name):  # PEP 562 lazy re-exports
    if name in ("Agent", "main"):
        from . import agent
        return getattr(agent, name)
    if name in ("Config", "Rule"):
        from . import config
        return getattr(config, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

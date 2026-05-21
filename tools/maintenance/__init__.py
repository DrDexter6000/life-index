"""Life Index - Maintenance Cycle (gbrain Phase D).

Dry-run/report-only maintenance cycle that aggregates six health checks
without production writes. All external CLI calls are delegated via
subprocess — no direct imports of called module internals.
"""

from .core import run_maintenance

__all__ = ["run_maintenance"]

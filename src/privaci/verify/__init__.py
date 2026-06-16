"""Value-free masking verification.

Compares a completed run's target database against its source and emits only
counts, rates, and verdicts — never raw cell values — so reports are safe to
print in any environment.
"""

from __future__ import annotations

from privaci.verify.models import CheckResult, Verdict, VerifyReport
from privaci.verify.runner import run_verification

__all__ = ["CheckResult", "Verdict", "VerifyReport", "run_verification"]

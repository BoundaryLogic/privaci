"""Custom exception hierarchy for PrivaCI.

Every PrivaCI error follows a **Context + Cause + Remediation** structure so
operators always learn what the engine was doing, why it failed, and the exact
next step to take. Each error class carries a stable ``exit_code`` and a
``doc_anchor`` into ``docs/error-codes.md``.

See ``docs/error-codes.md`` for the full exit-code catalogue and message format.
"""

from __future__ import annotations

ERROR_DOCS_PATH = "docs/error-codes.md"


class PrivaCIError(Exception):
    """Base exception using a Context + Cause + Remediation message format.

    Passing only ``context`` keeps the rendered message equal to that string,
    so terse internal raises stay readable. Supplying ``cause`` and/or
    ``remediation`` switches on the structured, operator-facing format.

    Attributes:
        exit_code: Process exit code associated with this error class.
        context: What the engine was doing when the failure occurred.
        cause: Why it failed. MUST NOT contain PII or secret values.
        remediation: The concrete next action the operator should take.
        doc_anchor: Anchor in ``docs/error-codes.md`` explaining this error.
    """

    exit_code: int = 1
    default_doc_anchor: str = "exit-code-1-generic-error"

    def __init__(
        self,
        context: str,
        *,
        cause: str | None = None,
        remediation: str | None = None,
        exit_code: int | None = None,
        doc_anchor: str | None = None,
    ) -> None:
        self.context = context
        self.cause = cause
        self.remediation = remediation
        if exit_code is not None:
            self.exit_code = exit_code
        self.doc_anchor = doc_anchor or self.default_doc_anchor
        super().__init__(self._render())

    def _render(self) -> str:
        """Render the message in C+C+R form, or bare context when minimal."""
        if self.cause is None and self.remediation is None:
            return self.context
        lines = [f"Context: {self.context}"]
        if self.cause is not None:
            lines.append(f"Cause: {self.cause}")
        if self.remediation is not None:
            lines.append(f"Remediation: {self.remediation}")
        lines.append(f"See: {ERROR_DOCS_PATH}#{self.doc_anchor}")
        return "\n".join(lines)


class ConfigError(PrivaCIError):
    """Raised when mask-rules.yaml or CLI config is invalid."""

    exit_code = 3
    default_doc_anchor = "exit-code-3-config-validation-failure"


class CatalogError(PrivaCIError):
    """Raised when schema introspection fails during pre-flight."""

    exit_code = 2
    default_doc_anchor = "exit-code-2-pre-flight-failure"


class PreflightError(PrivaCIError):
    """Raised when a pre-flight check fails before any writes."""

    exit_code = 2
    default_doc_anchor = "exit-code-2-pre-flight-failure"


class MaskingError(PrivaCIError):
    """Raised when the masking pipeline cannot process a value."""

    exit_code = 1
    default_doc_anchor = "exit-code-1-generic-error"


class StateError(PrivaCIError):
    """Raised when run state or checkpoint operations fail."""

    exit_code = 1
    default_doc_anchor = "exit-code-1-generic-error"


class SecretError(PrivaCIError):
    """Raised when a secret URI cannot be resolved or is malformed."""

    exit_code = 4
    default_doc_anchor = "exit-code-4-missing-or-invalid-salt"


class StorageError(PrivaCIError):
    """Raised when an object URI cannot be parsed or written."""

    exit_code = 1
    default_doc_anchor = "exit-code-1-generic-error"


class L3NotInstalledError(PrivaCIError):
    """Raised when Level 3 LLM masking is requested without the commercial layer."""

    exit_code = 3
    default_doc_anchor = "exit-code-3-config-validation-failure"


class LicenseError(PrivaCIError):
    """Raised when Marketplace entitlement or license validation fails."""

    exit_code = 5
    default_doc_anchor = "exit-code-5-license-entitlement-failure"


class DriftError(PrivaCIError):
    """Raised when schema/config drift is detected (commercial)."""

    exit_code = 6
    default_doc_anchor = "exit-code-6-drift-detected"


class RunInterruptedError(PrivaCIError):
    """Raised when a run is stopped by SIGINT/SIGTERM after checkpoint flush."""

    exit_code = 130
    default_doc_anchor = "exit-code-130-interrupted-by-signal"

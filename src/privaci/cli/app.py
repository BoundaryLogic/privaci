"""Typer CLI application for PrivaCI."""

from __future__ import annotations

import secrets
import sys
import uuid
from pathlib import Path

import typer

from privaci.cli._catalog import inspect_source
from privaci.cli._detect_drift import execute_detect_drift
from privaci.cli._errors import run_cli
from privaci.cli._preview import execute_preview
from privaci.cli._resume import execute_resume
from privaci.cli._run import execute_run, execute_verify
from privaci.cli.generate_ci import generate_ci_files
from privaci.cli.logging_setup import configure_cli_logging
from privaci.cli.options import (
    ConfigPathOption,
    DryRunOption,
    LogLevelOption,
    NoAuditTableOption,
    PrometheusPortOption,
    SourceDbOption,
    TargetDbOption,
)
from privaci.config import export_json_schema, load_config, migrate_config
from privaci.contracts import CONTRACT_VERSION, load_plugins
from privaci.observability import start_metrics_server
from privaci.packs import install_pack

app = typer.Typer(
    name="privaci",
    help="In-VPC PostgreSQL masking and anonymization engine.",
    no_args_is_help=False,
    add_completion=False,
)

schema_app = typer.Typer(help="Export machine-readable schemas.")
app.add_typer(schema_app, name="schema")

catalog_app = typer.Typer(help="Inspect the source database schema.")
app.add_typer(catalog_app, name="catalog")


def _invoke_run(
    *,
    config: str,
    source: str | None,
    target: str | None,
    dry_run: bool,
    no_audit_table: bool,
    report_path: str | None = None,
    prometheus_port: int | None = None,
) -> None:
    """Shared implementation for ``privaci`` (default) and ``privaci run``."""
    if prometheus_port is not None:
        start_metrics_server(prometheus_port)
    audit_enabled = None if not no_audit_table else False
    execute_run(
        config_path=config,
        source=source,
        target=target,
        dry_run=dry_run,
        audit_enabled=audit_enabled,
        report_path=report_path,
    )


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    log_level: LogLevelOption = "info",
    contract_version: bool = typer.Option(
        False,
        "--contract-version",
        help="Print the commercial-tier contract version and exit.",
        is_eager=True,
    ),
    config: ConfigPathOption = "/config/mask-rules.yaml",
    source: SourceDbOption = None,
    target: TargetDbOption = None,
    dry_run: DryRunOption = False,
    no_audit_table: NoAuditTableOption = False,
    prometheus_port: PrometheusPortOption = None,
) -> None:
    """Default entry: run masking when no subcommand is given."""
    if contract_version:
        typer.echo(CONTRACT_VERSION)
        raise typer.Exit(0)
    configure_cli_logging(log_level)
    if ctx.invoked_subcommand is None:
        _invoke_run(
            config=config,
            source=source,
            target=target,
            dry_run=dry_run,
            no_audit_table=no_audit_table,
            prometheus_port=prometheus_port,
        )


@app.command()
def run(
    config: ConfigPathOption = "/config/mask-rules.yaml",
    source: SourceDbOption = None,
    target: TargetDbOption = None,
    dry_run: DryRunOption = False,
    no_audit_table: NoAuditTableOption = False,
    prometheus_port: PrometheusPortOption = None,
) -> None:
    """Execute a masking run against the configured source and target."""
    _invoke_run(
        config=config,
        source=source,
        target=target,
        dry_run=dry_run,
        no_audit_table=no_audit_table,
        prometheus_port=prometheus_port,
    )


@app.command("detect-drift")
def detect_drift_cmd(
    source: SourceDbOption = None,
    target: TargetDbOption = None,
    accept_drift: bool = typer.Option(
        False,
        "--accept-drift",
        help="Emit findings JSON but do not exit 6 when drift is detected.",
    ),
) -> None:
    """Compare live source schema to the last snapshot on target (commercial)."""
    execute_detect_drift(source=source, target=target, accept_drift=accept_drift)


@app.command()
def preview(
    config: ConfigPathOption = "/config/mask-rules.yaml",
    source: SourceDbOption = None,
    target: TargetDbOption = None,
    commercial_extensions: str | None = typer.Option(
        None,
        "--commercial-extensions",
        help="Path to commercial-extensions.yaml (subset, json_mask).",
    ),
    sample: int = typer.Option(0, "--sample", min=0, max=100),
    policy_diff: str | None = typer.Option(None, "--policy-diff"),
    sarif: str | None = typer.Option(None, "--sarif"),
) -> None:
    """Safe sample preview, policy diff JSON, and SARIF output (commercial)."""
    execute_preview(
        config=config,
        source=source,
        target=target,
        commercial_extensions=commercial_extensions,
        sample=sample,
        policy_diff=policy_diff,
        sarif=sarif,
    )


@app.command("dry-run")
def dry_run_cmd(
    config: ConfigPathOption = "/config/mask-rules.yaml",
    source: SourceDbOption = None,
    target: TargetDbOption = None,
    report: str | None = typer.Option(
        None,
        "--report",
        help="Write a markdown auto-detect report to this path.",
    ),
) -> None:
    """Pre-flight checks only; no writes."""
    _invoke_run(
        config=config,
        source=source,
        target=target,
        dry_run=True,
        no_audit_table=False,
        report_path=report,
    )


@app.command()
def validate(config: ConfigPathOption = "/config/mask-rules.yaml") -> None:
    """Validate the config file (connectivity checks run during `run`)."""
    load_config(config)
    typer.echo(f"Config {config} is valid.")


@app.command()
def verify(
    config: ConfigPathOption = "/config/mask-rules.yaml",
    source: SourceDbOption = None,
    target: TargetDbOption = None,
    sample_size: int = typer.Option(
        1000,
        "--sample-size",
        help="Rows per table to sample for row-level checks.",
    ),
) -> None:
    """Audit a completed run: compare target against source (value-free)."""
    execute_verify(
        config_path=config,
        source=source,
        target=target,
        sample_size=sample_size,
    )


@schema_app.command("config")
def schema_config() -> None:
    """Print the mask-rules.yaml JSON Schema to stdout."""
    typer.echo(export_json_schema())


@catalog_app.command("inspect")
def catalog_inspect(source: SourceDbOption = None) -> None:
    """Introspect the source schema and print tables, load order, warnings."""
    inspect_source(source)


@app.command("migrate-config")
def migrate_config_cmd(
    path: str = typer.Argument(..., help="Path to the config file to migrate."),
    from_version: str = typer.Option(..., "--from", help="Current schema version."),
    to_version: str = typer.Option(..., "--to", help="Target schema version."),
) -> None:
    """Upgrade a config between schema versions (no-op when versions match)."""
    _ = path
    typer.echo(migrate_config(from_version, to_version))


@app.command("gen-salt")
def gen_salt() -> None:
    """Emit a 64-character hex salt to stdout."""
    typer.echo(secrets.token_hex(32))


@app.command("generate-ci")
def generate_ci(
    platform: str = typer.Option(
        ...,
        "--platform",
        help="github-actions | gitlab-ci | k8s-cronjob",
    ),
    output_dir: str = typer.Option(
        ".",
        "--output-dir",
        help="Directory to write generated files into.",
    ),
) -> None:
    """Emit CI/CD workflow files for a chosen platform."""
    paths = generate_ci_files(platform, output_dir=Path(output_dir))
    for path in paths:
        typer.echo(f"Wrote {path}")


@app.command("install-pack")
def install_pack_cmd(
    name: str = typer.Argument(..., help="Pack name (e.g. hipaa)."),
    *,
    config: ConfigPathOption = "/config/mask-rules.yaml",
    registry_url: str = typer.Option(
        "https://raw.githubusercontent.com/boundarylogic/config-packs/main",
        "--registry-url",
        help="Base URL for pack manifests.",
    ),
    local_pack_dir: str | None = typer.Option(
        None,
        "--local-pack-dir",
        help="Offline pack directory (contains <name>/manifest.json).",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Apply the merge without prompting.",
    ),
) -> None:
    """Fetch, verify, and merge a signed vertical config pack."""
    install_pack(
        name,
        config_path=Path(config),
        registry_url=registry_url,
        local_dir=Path(local_pack_dir) if local_pack_dir else None,
        assume_yes=yes,
    )


@app.command()
def resume(
    config: ConfigPathOption = "/config/mask-rules.yaml",
    source: SourceDbOption = None,
    target: TargetDbOption = None,
    no_audit_table: NoAuditTableOption = False,
) -> None:
    """Resume an interrupted run from checkpoints."""
    execute_resume(
        config_path=config,
        source=source,
        target=target,
        no_audit_table=no_audit_table,
    )


@app.command()
def report(
    run_id: str = typer.Option(..., "--run", help="Run UUID to report on."),
    output_format: str = typer.Option(
        "json",
        "--format",
        help="Output format (json; pdf requires commercial layer).",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        help="Write report bytes to this path (default: stdout).",
    ),
) -> None:
    """Render a compliance report for a completed run."""
    plugins = load_plugins()
    payload = plugins.report_renderer.render(
        uuid.UUID(run_id), output_format=output_format
    )
    if output is None:
        typer.echo(payload.decode())
        return
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(payload)
    typer.echo(f"Wrote report to {out_path}")


def main() -> int:
    """CLI entrypoint for setuptools scripts.

    Runs the Typer app in non-standalone mode so the centralized error boundary
    can render PrivaCIError in Context + Cause + Remediation form and map every
    outcome to a stable exit code (see docs/error-codes.md).
    """
    return run_cli(lambda: app(standalone_mode=False))


if __name__ == "__main__":
    sys.exit(main())

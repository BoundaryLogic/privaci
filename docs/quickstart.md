# Quickstart

Copy-pasteable path from zero to your first masked row. This guide uses the
self-contained evaluation stack (synthetic Postgres source + empty target +
PrivaCI engine). For your own databases, skip to
[Run against your databases](#run-against-your-databases).

## Prerequisites

- [Docker Desktop](deployment.md#windows) (WSL2 backend) **or** Linux with
  Docker/Podman
- Git

## 1. Clone and enter the repo

```bash
git clone https://github.com/BoundaryLogic/privaci.git
cd privaci
```

## 2. Generate a salt

The salt must be at least 32 characters and must never change between runs
that should produce identical fakes.

```bash
# Option A — if privaci is installed locally:
export ANONYMIZATION_SALT="$(privaci gen-salt)"

# Option B — offline (any shell with openssl):
export ANONYMIZATION_SALT="$(openssl rand -hex 32)"
```

PowerShell:

```powershell
$env:ANONYMIZATION_SALT = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) })
```

## 3. Start the evaluation stack

```bash
make eval-up
```

`make eval-up` auto-detects `docker compose` or `podman compose`. The stack:

- Seeds **source** Postgres with ~500 synthetic users (`example.test` emails).
- Creates an empty **target** Postgres.
- Runs PrivaCI with `examples/mask-rules.demo.yaml`.

Watch stdout for a JSON `run.end` event with `"status": "succeeded"`.

```bash
make eval-down   # tear down containers and volumes
```

## 4. Confirm masked data

Connect to the target (password `dev`, database `privaci_target` on port
mapped by compose) and spot-check:

```bash
docker compose exec target-pg psql -U postgres -d privaci_target \
  -c "SELECT email, first_name FROM public.users LIMIT 5;"
```

Emails should be synthetic (`example.test` domain is replaced); names should
not match the source.

## Run against your databases

```bash
pip install -e .

export ANONYMIZATION_SALT="$(privaci gen-salt)"
export SOURCE_DB_URL=postgresql://user:pass@source-host:5432/app
export TARGET_DB_URL=postgresql://user:pass@target-host:5432/staging

# Author mask-rules.yaml — start from examples/mask-rules.example.yaml
privaci validate --config mask-rules.yaml
privaci dry-run  --config mask-rules.yaml
privaci run      --config mask-rules.yaml
privaci verify   --config mask-rules.yaml
```

See [configuration.md](configuration.md) for every `mask-rules.yaml` field and
[deployment.md](deployment.md) for the production container image and Helm chart.

## Next steps

- [CLI guide](cli-reference.md) — examples for every subcommand
- [Error codes](error-codes.md) — exit codes and remediation
- [Observability](observability.md) — JSON-lines event stream on stdout

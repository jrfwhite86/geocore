[README.md](https://github.com/user-attachments/files/30218212/README.md)
# geodb_connect

IAM-authenticated connectivity toolkit for the geodb RDS PostgreSQL instance.

This replaces the previous flat `scripts/pg_iam_connect.py` (see
`docs/solid-dry-review.md`, SRP section) with a small package split by
responsibility:

| Module | Responsibility |
|---|---|
| `config.py` | Loads settings from `geodb/config/environment.env` + env vars |
| `auth.py` | Generates IAM RDS auth tokens |
| `db.py` | Opens a `psycopg` connection using a fresh token |
| `cli.py` | Command-line entry point (`geodb-connect`) |

## geodb_etl

A second, sibling package in this same project — a multi-format ETL pipeline that loads
geotechnical/project data into the geoCore schema. **See
[`docs/geodb_etl-overview.md`](./docs/geodb_etl-overview.md) for the full package guide**,
including a per-format status table and run instructions — short version: the EHS `.xlsx`
pipeline is fully implemented (parse → validate → transform → load) and runnable via the
`geodb-etl-load-ehs` console script (step-by-step usage in
[`docs/ehs-etl-usage.md`](./docs/ehs-etl-usage.md)); AGS4, CPT JSON, and both pdtable
formats (project-input, layout-input) are not yet runnable end to end (mapping-design only,
or — for pdtable project-input — mapping design plus an implemented `load` stage but stubbed
`parse`/`validate`/`transform`).

`geodb_etl` supports (or, for the mapping-design-only formats, is designed against) more
than one input source format — see `geodb_etl.mappings.types.SourceFormat`:

| Format | Status | Mapping module | Design doc |
|---|---|---|---|
| EHS `.xlsx` | Runnable (full pipeline) | `geodb_etl/mappings/xlsx/` | `docs/ehs-etl-mapping.md` |
| pdtable project-input | Not runnable (mapping + load only) | `geodb_etl/mappings/pdtable/` | `docs/pdtable-etl-mapping.md` |
| pdtable layout-input | Not runnable (mapping-design only) | `geodb_etl/mappings/pdtable/` | `docs/pdtable-etl-mapping.md` |
| pdtable exploratory-hole-input | Runnable (full pipeline, `geodb-etl-load-exploratory-hole`) | `geodb_etl/mappings/pdtable/` | `docs/pdtable-etl-mapping.md` |
| AGS4 | Not runnable (mapping-design only) | `geodb_etl/mappings/ags/` | `docs/ags-etl-mapping.md` |
| CPT "silver" JSON | Not runnable (mapping-design only) | `geodb_etl/mappings/json/` | `docs/json-etl-mapping.md` |

All formats declare their field mappings using the same shared, format-agnostic
contract (`geodb_etl.mappings.types.FieldMapping`/`RejectedRow`) so later pipeline stages
don't need per-format special-casing.

## Install

Managed with [Pixi](https://pixi.sh) — a single `pyproject.toml` is the source of truth
for both the package metadata and the dev environment (no separate `pixi.toml`).

```bash
# Install Pixi itself, once per machine (Windows PowerShell):
iwr -useb https://pixi.sh/install.ps1 | iex
# ...or WSL/Linux:
curl -fsSL https://pixi.sh/install.sh | bash

cd geodb/python
pixi install          # creates ./.pixi/ (gitignored) from pixi.toml + pixi.lock
```

`pip install -e ".[dev]"` (into your own venv) still works as an unsupported
fallback if you can't install Pixi, but Pixi is the only environment CI and these
docs are verified against — prefer it.

### PyCharm interpreter

PyCharm has no native Pixi integration, so add the Pixi env's Python as a system
interpreter:

1. **File → Settings → Project: geodb-connect → Python Interpreter**.
2. Gear icon → **Add Interpreter → Add Local Interpreter… → System Interpreter**.
3. Browse to the interpreter inside `geodb/python/.pixi/envs/default/`:
   - Windows: `.pixi\envs\default\python.exe`
   - WSL/Linux: `.pixi/envs/default/bin/python`
   (Unsure of the exact path? Run `pixi info` from `geodb/python/` and read the
   `Environments` line.)
4. Click **OK** and let PyCharm finish indexing.
5. **Mark the source root**: right-click `geodb/python/src` → **Mark Directory as →
   Sources Root**, so imports resolve correctly.

## Usage

```bash
aws sso login --profile geotech-dev
export AWS_PROFILE=geotech-dev
pixi run geodb-connect --role superuser   # or: pixi run python -m geodb_connect.cli --role dba
```

## Tests

```bash
pixi run test    # pytest tests
pixi run lint    # ruff check src tests
```

No AWS credentials are required to run the test suite — `boto3`/`psycopg` calls
are not exercised by the current tests (see `tests/test_config.py`).

## Updating the environment

```bash
pixi add <package>          # add a runtime/dev dependency, updates pyproject.toml + pixi.lock
pixi remove <package>
pixi install                 # resync ./.pixi/ after pulling pyproject.toml/pixi.lock changes
pixi list                    # what's installed
pixi info                    # env paths, platforms
```

Commit `pixi.lock` alongside any `pyproject.toml` dependency change — it pins exact
resolved versions for both `win-64` and `linux-64` so CI and every machine solve
identically. `.pixi/` itself is never committed (gitignored, machine-local).



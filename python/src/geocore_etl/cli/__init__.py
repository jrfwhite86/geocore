"""geodb_etl.cli: unified CLI package, one module per source format.

Per `tasks/plan/codebase-structure-cleanup.md` Task 8 ("Unify CLI entry
point"): `geodb_etl/cli.py` (EHS) and `geodb_etl/cli_pdtable.py` (pdtable
project-input) previously lived as two unrelated top-level modules with no
shared organization. They now live side by side as `geodb_etl.cli.ehs` and
`geodb_etl.cli.pdtable` -- mirroring the format-subdirectory pattern already
used by `parse/`, `validate/`, and `transform/` (`{xlsx,pdtable}/...`).

The two existing `[project.scripts]` console entry points
(`geodb-etl-load-ehs`, `geodb-etl-load-project`) are preserved unchanged as
public interfaces -- only the internal module path changed, from
`geodb_etl.cli:main` / `geodb_etl.cli_pdtable:main` to
`geodb_etl.cli.ehs:main` / `geodb_etl.cli.pdtable:main` (see pyproject.toml).

`dispatch()` below is a thin, format-agnostic entry point for future use (e.g.
a single `geodb-etl load <file> --format {ehs_xlsx,pdtable_csv}` script) --
each format's CLI keeps its own distinct argument shape (EHS needs
`--project-code`, pdtable does not) for now, so the two console scripts stay
the primary, documented way to invoke either pipeline.
"""

from __future__ import annotations

from . import ehs as ehs
from . import pdtable as pdtable

__all__ = ["dispatch", "ehs", "pdtable"]


def dispatch(source_format: str, argv: list[str] | None = None) -> int:
    """Dispatch to the CLI `main()` for the given source format.

    Args:
        source_format: One of "ehs_xlsx" or "pdtable_csv" (matches
            `geodb_etl.mappings.types.SourceFormat` values already in use
            elsewhere in this package).
        argv: Forwarded to the chosen format's `main()`.

    Raises:
        ValueError: `source_format` is not a recognised value.
    """

    if source_format == "ehs_xlsx":
        return ehs.main(argv)
    if source_format == "pdtable_csv":
        # geodb_etl.cli.pdtable.main() is still a NotImplementedError
        # placeholder (see its module docstring) -- calling it here surfaces
        # that error rather than hiding it behind a different message.
        return pdtable.main()  # type: ignore[func-returns-value]
    raise ValueError(
        f"Unrecognised source_format {source_format!r} -- expected 'ehs_xlsx' or 'pdtable_csv'."
    )


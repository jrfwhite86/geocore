"""Shared, coloured terminal reporting helpers for every `geodb_etl.cli.*` entry
point.

Previously each of cli.ehs / cli.exploratory_hole / cli.layout / cli.pdtable
declared its own near-identical, plain (uncoloured) `_print_rejections`
function, and two of them (`cli.ehs`, `cli.exploratory_hole`) additionally
declared their own `_print_warnings(list[str])`. Centralised here, once, so:

- every CLI prints rejections/warnings identically, instead of four
  independently-maintained copies that could silently drift apart;
- colour (matching geocore_tracker's `typer.secho(fg=...)` convention --
  ERROR red, WARNING yellow -- see that package's `cli._echo_report`) is
  added in exactly one place, not four.

Uses `click.secho` directly rather than adopting `typer` (these CLIs stay on
argparse -- see e.g. cli.pdtable's module docstring) -- `typer` itself is
built on `click` and calls this same `secho` under the hood, so this matches
tracker's actual terminal output, not just its intent.
"""

from __future__ import annotations

import click

from ..mappings.types import RejectedRow, ValidationWarning


def _finding_line(group: str, row_number: int, field_name: str | None, reason: str) -> str:
    field = f" [{field_name}]" if field_name else ""
    return f"{group} row {row_number}{field}: {reason}"


def print_rejections(rejections: list[RejectedRow]) -> None:
    """Print every RejectedRow to stderr in red, prefixed `[ERROR  ]`."""

    click.secho(f"{len(rejections)} row(s) rejected:", fg="red", err=True)
    for rejected in rejections:
        line = _finding_line(
            rejected.group, rejected.row_number, rejected.field_name, rejected.reason
        )
        click.secho(f"  [ERROR  ] {line}", fg="red", err=True)


def print_validation_warnings(warnings: list[ValidationWarning]) -> None:
    """Print every ValidationWarning to stderr in yellow, prefixed `[WARNING]`.

    Non-fatal by construction (see ValidationWarning's docstring) -- callers
    must not let these affect a process's exit code.
    """

    click.secho(f"{len(warnings)} warning(s):", fg="yellow", err=True)
    for warning in warnings:
        line = _finding_line(
            warning.group, warning.row_number, warning.field_name, warning.reason
        )
        click.secho(f"  [WARNING] {line}", fg="yellow", err=True)


def print_warning_messages(messages: list[str]) -> None:
    """Print plain-string warnings (cli.ehs / cli.exploratory_hole's
    non-blocking cross-check messages, which predate ValidationWarning and
    aren't attributable to a single (group, row_number, field_name) --
    see each of those module's own `_print_warnings` docstring) to stderr in
    yellow, prefixed `[WARNING]`.
    """

    for message in messages:
        click.secho(f"[WARNING] {message}", fg="yellow", err=True)


__all__ = ["print_rejections", "print_validation_warnings", "print_warning_messages"]

"""Shared ``pdtable`` ``ParseFixer`` subclass for every pdtable parse stage.

``pdtable.io.parsers.fixer.ParseFixer`` records a detailed, human-readable
message (in ``self.messages``) for every cell/row it silently repairs (e.g.
``"Illegal value 'xx' for unit 'm ' in table 'exploratory_hole_details'."``),
but its own ``report()`` method -- called internally by ``pdtable.io.csv.
read_csv`` once per table block, before control returns to our parse
functions -- only ever prints an aggregate count to stdout/stderr:

    Warning: 6 data errors fixed while parsing table 'exploratory_hole_details'

not the messages themselves, which is not actionable for a caller trying to
find out *what* was fixed. ``SilentParseFixer`` suppresses that generic
print/write (the two branches are otherwise byte-for-byte identical to the
base class, including the ``stop_on_errors`` raise) so parse functions can
surface ``fixer.messages`` themselves instead, via each ``Pdtable*Document``'s
``parse_warnings`` field.
"""

from __future__ import annotations

from pdtable.io.parsers.fixer import ParseFixer


class SilentParseFixer(ParseFixer):
    """``ParseFixer`` whose ``report()`` never prints -- see module docstring."""

    def report(self) -> None:
        if self.fixes > 0 and self.stop_on_errors:
            txt = (
                f"Stopped parsing after {self.fixes} errors in table "
                f"'{self.table_name}' with messages:\n" + "\n".join(self.messages)
            )
            raise ValueError(txt)


__all__ = ["SilentParseFixer"]

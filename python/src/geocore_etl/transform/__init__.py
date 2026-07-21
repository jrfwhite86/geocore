"""geodb_etl transform stage entry points.

Pure functions turning validated rows into typed, load-ready records — no DB
I/O (see tasks/plan/phase-3b-pipeline-implementation.md Task 9's `transform/
ags.py` for the AGS4 shape this mirrors). Only geodb_etl.transform.xlsx
exists so far.
"""

from __future__ import annotations


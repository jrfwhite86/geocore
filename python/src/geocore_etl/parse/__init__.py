"""EHS xlsx / AGS4 / CPT-JSON parse stage entry points.

Read a landed file (see a later "land" increment) into an in-memory,
per-format-appropriate structure. No validation, no transform, no DB writes —
mirrors the parse-stage scope tasks/plan/phase-3b-pipeline-implementation.md
describes for AGS4/CPT-JSON.
"""

from __future__ import annotations


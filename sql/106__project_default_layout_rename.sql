-- =============================================================================
-- Project: default layout placeholder rename (PENDING/PROP -> L000/PLC)
-- =============================================================================
-- Depends on:
--   040__project_project.sql
--   090__reference_layout_status.sql
--   100__project_layout.sql
--   105__project_default_layout.sql
--
-- 105__project_default_layout.sql originally created every project's
-- placeholder project.layout row with layout_code = 'PENDING' and
-- layout_status_code = 'PROP'. Both literals have since been corrected in
-- 105 itself (layout_code = 'L000', layout_status_code = 'PLC' -- 'PROP' is
-- reserved for a genuinely proposed/under-consideration layout, not a
-- not-yet-populated placeholder). A fresh apply of the corrected 105 never
-- produces the old literals, so this file is a no-op there.
--
-- For a database that already applied the *old* 105 (i.e. already has
-- project.layout rows with layout_code = 'PENDING'), this file backfills
-- those rows to the corrected literals. Idempotent and safe to re-run:
-- the first UPDATE only matches rows still named 'PENDING' (a no-op on any
-- later run), and the second only matches a placeholder row still flagged
-- 'PROP' (also a no-op after its first successful run).
--
-- Mirrors 105's own "no explicit BEGIN/COMMIT" rationale -- see that file's
-- header comment for why (this repo's two supported psql apply modes).

UPDATE project.layout
SET layout_code = 'L000',
    layout_name = 'Placeholder layout'
WHERE layout_code = 'PENDING';

UPDATE project.layout
SET layout_status_code = 'PLC'
WHERE layout_code = 'L000'
  AND layout_status_code = 'PROP';

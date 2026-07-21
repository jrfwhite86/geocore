-- =============================================================================
-- Reference data: hole_status, termination_reason
-- =============================================================================
-- Production-safe reference data (see geodb/sql/README.md).
--
-- Two deliberately separate concerns:
--   - hole_status: WHERE a hole is in the SI lifecycle (scheduled, in
--     progress, or one of several terminal outcomes).
--   - termination_reason: WHY a hole stopped (only meaningful once a hole
--     has actually been attempted; NULL for SCHEDULED/CANCELLED holes).
-- Keeping these separate lets a hole be e.g. ACCEPTED (project decision to
-- treat a short hole as complete) for any of several termination_reasons
-- (REFUSAL, EQUIPMENT, ...), without a combinatorial explosion of statuses.

CREATE TABLE reference.hole_status (
    hole_status_code VARCHAR(10) PRIMARY KEY,
    hole_status_name TEXT NOT NULL,
    is_terminal BOOLEAN NOT NULL,
    description TEXT
);

INSERT INTO reference.hole_status (hole_status_code, hole_status_name, is_terminal, description)
VALUES
('SCHEDULED',  'Scheduled',   false, 'Planned position, not yet occupied by the vessel/rig'),
('INPROGRESS', 'In progress', false, 'Operations under way at the position'),
('COMPLETED',  'Completed',   true,  'Achieved target depth (or contractual acceptance criteria) as planned'),
('ACCEPTED',   'Accepted',    true,  'Terminated short of target depth but accepted by the project as complete; no bumpover required'),
('FAILED',     'Failed',      true,  'Terminated prematurely (early refusal, equipment failure, tool loss etc.) and not accepted; typically superseded by a bumpover'),
('ABANDONED',  'Abandoned',   true,  'Attempted or partially attempted, then abandoned by project decision; will not be completed or bumped over'),
('CANCELLED',  'Cancelled',   true,  'Removed from the schedule before any attempt was made');


CREATE TABLE reference.termination_reason (
    termination_reason_code VARCHAR(10) PRIMARY KEY,
    termination_reason_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.termination_reason (termination_reason_code, termination_reason_name, description)
VALUES
('TARGET',    'Target achieved',    'Terminated at target depth'),
('REFUSAL',   'Early refusal',      'Refusal above target depth (e.g. cone refusal, spudcan/hard stratum)'),
('EQUIPMENT', 'Equipment failure',  'Tool, rig or vessel equipment failure'),
('WEATHER',   'Weather/downtime',   'Terminated due to weather or operational downtime'),
('PROJECT',   'Project decision',   'Terminated or abandoned by project/client instruction'),
('OTHER',     'Other',              'Other reason; see comments');

COMMENT ON COLUMN reference.hole_status.is_terminal IS
'TRUE if this status is an end state for the hole (no further progress is
expected against this row). SI progress dashboards can use this to compute
percent complete = terminal-and-successful (COMPLETED, ACCEPTED) over all
non-CANCELLED holes, and outstanding work = SCHEDULED + INPROGRESS +
FAILED-awaiting-bumpover.';

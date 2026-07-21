"""Shared types for the geoCore ETL mapping layer (tasks/plan.md Phase 3, Task 4).

These types are the contract every later pipeline stage builds against, and are
deliberately format-agnostic: geodb_etl ingests more than one source format
(AGS4 today, a JSON "silver" format under development — see
geodb_etl.mappings.ags / geodb_etl.mappings.json), and both must declare their
mappings using the same shapes so later stages (validate/transform/load) don't
need per-format special-casing.

- FieldMapping declares, as data, how one source field (an AGS4 heading code,
  or a JSON path in the new format) maps onto one geoCore column (or documents
  that a target field is synthesized/resolved rather than copied verbatim from
  a single source field).
- RejectedRow is the one shape used everywhere a row fails validation — per the
  repo's data-integrity standard, invalid rows are never silently discarded,
  they are always turned into a RejectedRow carrying enough context to find
  the offending data again.

No I/O, no format-specific parsing, no database access here — pure data
declarations, importable and unit-testable without python-ags4 or a live
database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceFormat(str, Enum):
    """The input formats geodb_etl ingests.

    AGS4 is the original, established format (tasks/plan.md Phase 3, Task 4).
    CPT_JSON is a new "silver" JSON format under development for cone
    penetration test data (see tasks/cpt_silver.schema.json,
    $id "urn:ags4+f:cone_penetration_test:1.0") — it is expected to eventually
    supersede AGS4 for CPT data industry-wide, but for now runs alongside it
    as a second, independently-supported source format, not a replacement.
    EHS_XLSX is an "Exploratory Hole Schedule" .xlsx workbook issued to the SI
    contractor prior to mobilisation (see geodb_etl.mappings.xlsx.ehs) — a
    third, independent source format, earliest in a campaign's document
    lifecycle (it creates geotech.site_investigation rather than merely
    resolving/checking against it, unlike AGS4/CPT_JSON).
    PDTABLE_CSV is a pdtable ("StarTable") semicolon-delimited .csv, the
    project-input file a data engineer prepares when creating a new asset
    project (see geodb_etl.mappings.pdtable.project) — earliest still in a
    project's overall lifecycle (it creates/owns project.project and
    location.development_area, the two tables every other format only ever
    resolves against).
    """

    AGS4 = "ags4"
    CPT_JSON = "cpt_json"
    EHS_XLSX = "ehs_xlsx"
    PDTABLE_CSV = "pdtable_csv"


class AgsVersion(str, Enum):
    """Base AGS4 dictionary versions this pipeline knows how to interpret.

    An AGS4 file declares its base dictionary version via the TRAN group's
    TRAN_AGS heading. Confirmed against real reference artefacts (moved
    2026-07-09 to geodb/sample-data/ags/reference-files/):
    - geodb/sample-data/ags/bronze/Gardline (2023). HEW02_GTR_CPT-scope.ags
      declares TRAN_AGS == "4.1.1".
    - geodb/sample-data/ags/reference-files/AGS4+E.xlsx (Ørsted's in-house
      "AGS 4+ (Revision E)" template) declares TRAN_AGS == "4.0.4" — see the
      important correction below.
    - geodb/sample-data/ags/reference-files/AGS4-0-4.xlsx (added 2026-07-09), a
      dedicated public AGS4.0.4 template with no Revision E marker — grounds
      "4.0.4" as an ordinary base version independently of the Revision E
      template above, which only ever demonstrated "4.0.4" alongside Revision E.

    IMPORTANT (corrected 2026-07-09, see geodb_etl.mappings.ags.version):
    "AGS 4+ (Revision E)" is NOT a value TRAN_AGS itself takes — it is an
    independent extension flag carried in the TRAN group's *TRAN_REM* heading
    (confirmed value: "AGS4+ Rev 00637136_E"), layered on top of whatever base
    version TRAN_AGS declares. An earlier version of this enum incorrectly
    modelled it as a peer member here (V4_PLUS_REV_E) before this was verified
    against the real AGS4+E.xlsx template — that member has been removed.
    See geodb_etl.mappings.ags.version.AgsFileVersion for the corrected,
    two-axis (base version + is_revision_e flag) model.
    """

    V4_0 = "4.0"
    V4_0_4 = "4.0.4"
    V4_1 = "4.1"
    V4_1_1 = "4.1.1"



class UnitConversion(str, Enum):
    """Named unit conversions applied during the transform stage (Task 9/10).

    Kept as a small closed enum rather than an arbitrary callable — every
    conversion this pipeline needs is known up front from the Task 4 mapping
    review, and a closed set is easier to unit-test exhaustively than
    arbitrary functions declared inline.
    """

    NONE = "none"
    MPA_TO_PA = "mpa_to_pa"
    KPA_TO_PA = "kpa_to_pa"


@dataclass(frozen=True)
class FieldMapping:
    """One source field -> one geoCore column, declared as data.

    Attributes:
        source_field: The source field this value is read from — an AGS4
            heading code (e.g. "LOCA_NATE") for SourceFormat.AGS4, or a
            dotted JSON path (e.g. "logged_data.cone_resistance") for
            SourceFormat.CPT_JSON — or None if the target column is
            synthesized/resolved rather than copied from a single source
            field (e.g. a foreign key resolved via lookup, or a value
            supplied by the pipeline operator).
        source_format: Which input format this mapping applies to. Defaults
            to SourceFormat.AGS4 since that was geodb_etl's only supported
            format when this field was added — every AGS mapping module
            relies on this default rather than repeating it per declaration.
        target_table: Fully-qualified geoCore table name (e.g.
            "geotech.exploratory_hole").
        target_column: geoCore column name within target_table.
        unit_conversion: Named conversion applied when copying the value
            across (see UnitConversion). UnitConversion.NONE if the source
            unit already matches the geoCore column's stored unit.
        required: Whether a missing/blank value for this field causes the row
            to be rejected (see RejectedRow) rather than loaded with a NULL.
        min_source_version: The earliest source-format dictionary/schema
            version this field is available in, as a plain version string
            (e.g. "4.1" for an AGS4 heading introduced in AGS4.1; "1.0" for a
            CPT-JSON schema field). None means "available in every version
            this pipeline supports" (the common case — most fields haven't
            changed across versions). Deliberately a plain string rather than
            AgsVersion, since it must also work for SourceFormat.CPT_JSON's
            own schema versioning ($id "...:1.0") — comparison/resolution
            logic is format-specific (see geodb_etl.mappings.ags.version for
            the AGS4 case) and lives outside this shared contract.
        notes: Free-text clarification — e.g. why a conversion applies, or
            what "resolved" means for a None source_field field.
    """

    source_field: str | None
    target_table: str
    target_column: str
    source_format: SourceFormat = SourceFormat.AGS4
    unit_conversion: UnitConversion = UnitConversion.NONE
    required: bool = True
    min_source_version: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class RejectedRow:
    """A single source data row that failed validation (syntactic or semantic).

    Every rejection produced anywhere in the pipeline (Tasks 7/8) uses this
    shape, for every supported SourceFormat, so a quarantine report can always
    answer "which file, which group, which row, and why" — per the repo's
    data-integrity standard, nothing is ever silently dropped.

    Attributes:
        group: The source-format-specific grouping the row belongs to — an
            AGS4 group code (e.g. "LOCA") for SourceFormat.AGS4, or a JSON
            section name (e.g. "pushes" or "logged_data") for
            SourceFormat.CPT_JSON.
        field_name: The specific source field within the row that failed, if
            attributable to one field (an AGS4 heading, e.g. "LOCA_ID", or a
            JSON path, e.g. "pushes.push-1.logged_data.depth") — None if the
            failure isn't attributable to a single field (e.g. a whole-row
            structural problem).
    """

    source_file: str
    group: str
    row_number: int
    reason: str
    field_name: str | None = None
    context: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationWarning:
    """A non-fatal, suspicious-but-not-rejected finding surfaced during validation.

    UNLIKE RejectedRow, a ValidationWarning never causes a row/block to be
    dropped -- the row is still validated and loaded normally. It exists for
    checks that are cheap, prose-level consistency cross-checks rather than
    hard structural/type failures, e.g. a coordinate_reference_system block
    whose free-text map_projection field (e.g. "UTM Zone 32N") disagrees with
    its own EPSG_code (e.g. 25831, which is actually UTM zone 31N) -- data
    that is internally inconsistent but not unusable, so it is surfaced to
    the operator rather than silently accepted or needlessly rejected. Same
    shape as RejectedRow so every stage can report both kinds of finding
    through one consistent (source_file, group, row_number, field_name)
    addressing scheme.
    """

    source_file: str
    group: str
    row_number: int
    reason: str
    field_name: str | None = None
    context: dict[str, str] = field(default_factory=dict)


"""Transform stage for pdtable layout-input (Phase 10b rewrite).

Pure functions -- no I/O, no database access. Shapes here are the
load.py-verified contract: every field name, order, and nullability matches
how ``load.pdtable.layout.load_pdtable_layout_transform_result()`` and its
``_upsert_*()`` helpers consume them.

Every asset ``AssetDetailsRecord`` carries its own ``project_code`` +
``layout_code`` pair (which originates from the ``**layout_configuration``
block's own destination tags, not a per-row column -- see
``validate.pdtable.layout`` and mappings.pdtable.layout.
MULTI_PROJECT_DESTINATION_CONVENTION). The load stage resolves
``project.layout.layout_id`` by looking that (project_code, layout_code)
pair up in the ``layout_catalogue`` records it upserts first (same
transaction), so the ordering here matters -- ``layout_catalogue`` MUST be
processed before ``asset_details`` at load time. A single
``PdtableLayoutTransformResult`` may span multiple projects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ...validate.pdtable.layout import ValidatedPdtableLayoutDocument


@dataclass(frozen=True)
class LayoutCatalogueRecord:
    """project.layout upsert shape (one per layout_details row).

    ``project_code`` is carried on every record now that a file may cover
    multiple projects (see mappings.pdtable.layout.
    MULTI_PROJECT_DESTINATION_CONVENTION) -- load resolves project_id from
    it per record rather than receiving a single file-wide project_id
    parameter. See mappings.pdtable.layout.LAYOUT_STATUS_AUTHORITY for why
    ``layout_status_code`` is only written on first INSERT, never in
    DO UPDATE SET.
    """

    project_code: str
    layout_code: str
    layout_name: str | None
    layout_status_code: str
    effective_date: date | None
    description: str | None


@dataclass(frozen=True)
class AssetLocationRecord:
    """location.asset_location upsert shape.

    project_id is NOT a field here -- load receives it as a separate
    parameter.
    """

    internal_reference: str
    asset_type_code: str
    leg_label: str | None = None
    parent_asset_name: str | None = None


@dataclass(frozen=True)
class AssetLayoutPositionRecord:
    """project.layout_asset upsert shape.

    layout_id and coordinate_system_id are NOT fields here -- load resolves
    them separately. asset_location_id is NOT a field here -- load resolves
    it after inserting/updating the paired AssetLocationRecord.
    """

    internal_reference: str
    eastings_m: float
    northings_m: float
    seabed_level_m: float | None
    water_level: float | None
    foundation_type_code: str | None
    rdspp_code: str | None = None


@dataclass(frozen=True)
class AssetDetailsRecord:
    """Paired asset_location + layout_asset for one layout_configuration row.

    Every row carries a concrete ``project_code``/``layout_code`` pair (the
    block's own destination tags, never None) -- the historical per-row
    ``layout_reference`` column is gone. Load resolves this to a
    ``project.layout.layout_id`` against the same file's ``layout_catalogue``
    upserts for the matching project_code.
    """

    location: AssetLocationRecord
    position: AssetLayoutPositionRecord
    project_code: str
    layout_code: str


@dataclass(frozen=True)
class PdtableLayoutTransformResult:
    """Full transform result for one input_layout_{area_code}.csv (may span
    multiple projects -- see mappings.pdtable.layout.
    MULTI_PROJECT_DESTINATION_CONVENTION). (See
    load.load_pdtable_layout_transform_result.)
    """

    layout_catalogue: list[LayoutCatalogueRecord] = field(default_factory=list)
    asset_details: list[AssetDetailsRecord] = field(default_factory=list)


def transform_pdtable_layout_document(
    document: ValidatedPdtableLayoutDocument,
) -> PdtableLayoutTransformResult:
    """Map a ``ValidatedPdtableLayoutDocument`` onto load-ready records.

    Pure mapping only -- coordinate_system_id, layout_id, project_id, and
    asset_location_id resolution are deferred to load.py (they require
    database access).
    """

    layout_catalogue = [
        LayoutCatalogueRecord(
            project_code=entry.project_code,
            layout_code=entry.layout_code,
            layout_name=entry.layout_name,
            layout_status_code=entry.layout_status_code,
            effective_date=entry.effective_date,
            description=entry.description,
        )
        for entry in document.layout_catalogue
    ]

    asset_details = [
        AssetDetailsRecord(
            location=AssetLocationRecord(
                internal_reference=asset.asset_name,
                asset_type_code=asset.asset_type_code,
                leg_label=asset.leg_label,
                parent_asset_name=asset.parent_asset_name,
            ),
            position=AssetLayoutPositionRecord(
                internal_reference=asset.asset_name,
                eastings_m=asset.eastings_m,
                northings_m=asset.northings_m,
                seabed_level_m=asset.seabed_level_m,
                water_level=asset.water_level,
                foundation_type_code=asset.foundation_type_code,
                rdspp_code=asset.rdspp_code,
            ),
            project_code=asset.project_code,
            layout_code=asset.layout_code,
        )
        for asset in document.asset_details
    ]

    return PdtableLayoutTransformResult(
        layout_catalogue=layout_catalogue,
        asset_details=asset_details,
    )

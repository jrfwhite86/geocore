# geodb sample data

Fictional/illustrative data for developing and testing against the `geodb`
schema (`geodb/sql/`). **Never apply anything in this directory to a real
environment** — see `geodb/sql/README.md`'s "production-safe vs. dev-only"
section.

| File | Demonstrates |
|---|---|
| `sql/demo-boundary-how04.sql` | `location.boundary`/`boundary_vertex` shape and the closure-validation trigger. Deliberately out-of-scale coordinates (±100,000,000 m) — a placeholder, not real geometry. |
| `sql/demo-chw22.sql` | The layout-independent asset identity model end-to-end: asset locations, an asset reshuffle across two layouts, and exploratory holes linked via both available paths (direct-to-asset-location and via-layout-position), including a bumpover hole. Uses the real `CHW22` project code (seeded in `geodb/sql/040__project_project.sql`) but entirely invented layouts/holes/dates. |

## Applying (after `geodb/sql/` has been applied)

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f geodb/sample-data/sql/demo-boundary-how04.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f geodb/sample-data/sql/demo-chw22.sql
```

Future exemplar formats (`.ags`, `.csv`, `.geojson` — see `tasks/plan.md` Phase 4)
will land in sibling `ags/`, `csv/`, and `gis/` directories here.


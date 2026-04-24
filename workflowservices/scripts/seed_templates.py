"""
Seed dashboard_templates table from the compliance skill's templates_registry.json.

Usage:
    python scripts/seed_templates.py
    python scripts/seed_templates.py --registry /path/to/templates_registry.json
    python scripts/seed_templates.py --dry-run
"""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path

# Allow running from repo root or scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_REGISTRY = Path(__file__).resolve().parents[4] / (
    "complianceskill/data/dashboard/templates_registry.json"
)

LAYOUT_KEYS = (
    "primitives", "panels", "strip_cells", "has_chat",
    "has_graph", "has_filters", "theme_hint", "chart_types",
    "components", "filter_options", "layout_grid",
)


def build_layout(t: dict) -> dict:
    """Build layout dict depending on registry format."""
    # dashboard_registry.json — layout is already a dedicated field
    if "layout" in t and isinstance(t["layout"], dict):
        layout = dict(t["layout"])
        # Merge in other relevant fields
        for k in ("components", "filters", "interactions"):
            if k in t:
                layout[k] = t[k]
        return layout
    # templates_registry.json — layout fields are top-level
    return {k: t[k] for k in LAYOUT_KEYS if k in t}


def normalize(t: dict) -> dict:
    """Normalize a record from either registry format into a common shape."""
    return {
        "id": t.get("id") or t.get("template_id"),
        "name": t.get("name", ""),
        "description": t.get("description", ""),
        "category": t.get("category", ""),
        "complexity": t.get("complexity"),
        "source": t.get("source"),
        "audience": t.get("audience", []),
        "domains": t.get("domains", []),
        "best_for": t.get("best_for", []),
        "layout": build_layout(t),
    }


def load_templates(registry_path: Path) -> list[dict]:
    with open(registry_path, encoding="utf-8") as f:
        data = json.load(f)
    # Support both formats
    if "templates" in data:
        return [normalize(t) for t in data["templates"]]
    if "dashboards" in data:
        return [normalize(d) for d in data["dashboards"]]
    raise KeyError(f"No 'templates' or 'dashboards' key found in {registry_path}")


def seed(registry_path: Path, dry_run: bool = False) -> None:
    import psycopg2
    import psycopg2.extras

    templates = load_templates(registry_path)
    print(f"Loaded {len(templates)} templates from {registry_path}")

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "genaipostgresqlserver.postgres.database.azure.com"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "phenom_gen_ai"),
        user=os.getenv("POSTGRES_USER", "phegenaiadmin"),
        password=os.getenv("POSTGRES_PASSWORD", "vwm8$S4VVpn%2J_"),
        sslmode="require",
    )
    cur = conn.cursor()

    created = updated = skipped = 0

    for t in templates:
        source_id = t["id"]
        if not source_id:
            skipped += 1
            continue
        layout = json.dumps(t["layout"])
        domains = json.dumps(t["domains"])
        best_for = json.dumps(t["best_for"])

        cur.execute("SELECT id FROM dashboard_templates WHERE source_id = %s", (source_id,))
        row = cur.fetchone()

        if row:
            if dry_run:
                print(f"  [DRY-RUN] would UPDATE {source_id}")
                updated += 1
                continue
            cur.execute("""
                UPDATE dashboard_templates SET
                    name = %s,
                    description = %s,
                    category = %s,
                    complexity = %s,
                    domains = %s,
                    best_for = %s,
                    layout = %s,
                    updated_at = NOW()
                WHERE source_id = %s
            """, (
                t["name"], t["description"], t["category"],
                t["complexity"], domains, best_for, layout, source_id,
            ))
            updated += 1
            print(f"  UPDATED  {source_id}: {t['name']}")
        else:
            if dry_run:
                print(f"  [DRY-RUN] would INSERT {source_id}")
                created += 1
                continue
            cur.execute("""
                INSERT INTO dashboard_templates
                    (id, source_id, name, description, template_type,
                     category, complexity, domains, best_for, layout,
                     is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())
            """, (
                str(uuid.uuid4()), source_id, t["name"],
                t["description"], "dashboard",
                t["category"], t["complexity"],
                domains, best_for, layout,
            ))
            created += 1
            print(f"  INSERTED {source_id}: {t['name']}")

    if not dry_run:
        conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone — created: {created}, updated: {updated}, skipped: {skipped}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed dashboard_templates from registry JSON")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if not args.registry.exists():
        print(f"ERROR: registry not found at {args.registry}", file=sys.stderr)
        sys.exit(1)

    seed(args.registry, dry_run=args.dry_run)

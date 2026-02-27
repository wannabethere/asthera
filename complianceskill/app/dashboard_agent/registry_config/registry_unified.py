"""
CCE Template Registry — Unified (23 Templates)
================================================
Merges the base 17 templates + 6 L&D/Training templates
into a single registry for the Layout Advisor Agent.

Template counts by category:
  Security Operations .... 4  (command-center, triage-focused, vulnerability-posture, incident-timeline)
  Executive / Board ...... 2  (posture-overview, executive-risk-summary)
  HR & Learning .......... 3  (lms-training, hr-workforce, onboarding-offboarding)
  Cross-Domain ........... 1  (hybrid-compliance)
  Data Operations ........ 2  (migration-tracker, pipeline-health)
  GRC / Risk ............. 3  (risk-register, vendor-risk, regulatory-change)
  Identity & Access ...... 1  (access-certification)
  Compliance ............. 1  (audit-evidence)
  Learning & Training .... 4  (training-plan-tracker, team-training-analytics, learner-profile, lms-engagement)   ← NEW
  L&D Operations ......... 2  (ld-operations, learning-measurement)                                               ← NEW
  ─────────────────────────
  TOTAL ................. 23
"""

from ..templates import TEMPLATES, CATEGORIES, DECISION_TREE, AUTO_RESOLVE_HINTS, get_template_embedding_text
from .templates_ld import LD_TEMPLATES, LD_CATEGORIES, LD_DECISION_OPTIONS, LD_AUTO_RESOLVE_HINTS, get_ld_template_embedding_text


# ═══════════════════════════════════════════════════════════════════════
# MERGED REGISTRY
# ═══════════════════════════════════════════════════════════════════════

ALL_TEMPLATES: dict[str, dict] = {**TEMPLATES, **LD_TEMPLATES}

ALL_CATEGORIES: dict[str, dict] = {**CATEGORIES, **LD_CATEGORIES}


# ═══════════════════════════════════════════════════════════════════════
# EXTENDED DECISION TREE
# ═══════════════════════════════════════════════════════════════════════

def build_extended_decision_tree() -> list[dict]:
    """
    Extend the base decision tree with L&D-specific options.
    Adds new intent options and audience options for L&D users.
    """
    extended = []
    for decision in DECISION_TREE:
        d = {**decision, "options": list(decision["options"])}

        if decision["id"] == "intent":
            # Add L&D intent options
            d["options"].extend(LD_DECISION_OPTIONS["intent"])

        elif decision["id"] == "audience":
            # Add L&D audience options
            d["options"].extend(LD_DECISION_OPTIONS["audience"])

        elif decision["id"] == "systems":
            # Add LMS-specific system option
            d["options"].append({
                "label": "LMS platform (Cornerstone, SumTotal, Saba)",
                "maps_to": {"domain": "lms"},
            })

        extended.append(d)

    return extended


EXTENDED_DECISION_TREE = build_extended_decision_tree()


# ═══════════════════════════════════════════════════════════════════════
# EXTENDED AUTO-RESOLVE
# ═══════════════════════════════════════════════════════════════════════

EXTENDED_AUTO_RESOLVE = {**AUTO_RESOLVE_HINTS}
for key, hints in LD_AUTO_RESOLVE_HINTS.items():
    if key in EXTENDED_AUTO_RESOLVE:
        EXTENDED_AUTO_RESOLVE[key] = {**EXTENDED_AUTO_RESOLVE[key], **hints}
    else:
        EXTENDED_AUTO_RESOLVE[key] = hints

# Add LMS domain hints
if "systems" in EXTENDED_AUTO_RESOLVE:
    EXTENDED_AUTO_RESOLVE["systems"].update({
        "lms": 5, "saba": 5, "sumtotal": 5,
        "training": 1, "learning": 1,
    })


# ═══════════════════════════════════════════════════════════════════════
# UNIFIED EMBEDDING TEXT BUILDER
# ═══════════════════════════════════════════════════════════════════════

def get_unified_embedding_text(template: dict) -> str:
    """Build embedding text for any template (base or L&D)."""
    if template["category"] in LD_CATEGORIES:
        return get_ld_template_embedding_text(template)
    return get_template_embedding_text(template)


# ═══════════════════════════════════════════════════════════════════════
# SCORING: Extended to handle L&D-specific matching
# ═══════════════════════════════════════════════════════════════════════

def score_all_templates(decisions: dict) -> list[tuple[str, int, list[str]]]:
    """
    Score all 23 templates against decisions.
    Extends base scoring with L&D-specific domain matching.
    """
    scores = {}

    for tid, tpl in ALL_TEMPLATES.items():
        score = 0
        reasons = []

        # Category match (30 pts)
        if decisions.get("category"):
            if tpl["category"] in decisions["category"]:
                score += 30
                reasons.append(f"category: {tpl['category']}")

        # Domain match (25 pts)
        if decisions.get("domain"):
            domain = decisions["domain"]
            if domain in tpl.get("domains", []):
                score += 25
                reasons.append(f"domain: {domain}")
            # Cross-match: "lms" domain should also match "cornerstone"
            if domain == "lms" and "cornerstone" in tpl.get("domains", []):
                score += 20
                reasons.append("lms↔cornerstone cross-match")
            if domain == "cornerstone" and "lms" in tpl.get("domains", []):
                score += 20
                reasons.append("cornerstone↔lms cross-match")

        # Theme match (10 pts)
        if decisions.get("theme") and tpl.get("theme_hint"):
            if decisions["theme"] in tpl["theme_hint"]:
                score += 10
                reasons.append(f"theme: {decisions['theme']}")

        # Complexity match (10 pts)
        if decisions.get("complexity") and tpl.get("complexity"):
            if tpl["complexity"] == decisions["complexity"]:
                score += 10
                reasons.append(f"complexity: {decisions['complexity']}")

        # Chat match (15 pts)
        if decisions.get("has_chat") is not None:
            if tpl["has_chat"] == decisions["has_chat"]:
                score += 15
                reasons.append(f"chat: {'yes' if decisions['has_chat'] else 'no'}")

        # Strip cells match (10 pts)
        if decisions.get("strip_cells") is not None:
            if decisions["strip_cells"] == 0 and tpl["strip_cells"] == 0:
                score += 10
                reasons.append("no KPI strip")
            elif decisions["strip_cells"] > 0 and tpl["strip_cells"] > 0:
                score += 5
                if abs(decisions["strip_cells"] - tpl["strip_cells"]) <= 2:
                    score += 5
                    reasons.append(f"strip ~{tpl['strip_cells']}")

        # L&D-specific: chart type preference
        if decisions.get("preferred_charts") and tpl.get("chart_types"):
            overlap = set(decisions["preferred_charts"]) & set(tpl["chart_types"])
            if overlap:
                boost = min(len(overlap) * 5, 15)
                score += boost
                reasons.append(f"chart match: {', '.join(overlap)}")

        # L&D-specific: table requirement
        if decisions.get("needs_detail_table") and tpl.get("table_columns"):
            score += 10
            reasons.append("has detail table")

        scores[tid] = {"score": score, "reasons": reasons}

    ranked = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    return [(tid, data["score"], data["reasons"]) for tid, data in ranked]


# ═══════════════════════════════════════════════════════════════════════
# TEMPLATE LOOKUP HELPERS
# ═══════════════════════════════════════════════════════════════════════

def get_templates_by_category(category: str) -> list[dict]:
    """Get all templates in a category."""
    return [t for t in ALL_TEMPLATES.values() if t["category"] == category]


def get_templates_by_domain(domain: str) -> list[dict]:
    """Get all templates that serve a domain."""
    return [t for t in ALL_TEMPLATES.values() if domain in t.get("domains", [])]


def get_ld_templates() -> list[dict]:
    """Get only the L&D templates."""
    ld_cats = set(LD_CATEGORIES.keys())
    return [t for t in ALL_TEMPLATES.values() if t["category"] in ld_cats]


def get_template_summary() -> dict:
    """Get a summary of all templates by category."""
    summary = {}
    for cat_id, cat in ALL_CATEGORIES.items():
        templates = get_templates_by_category(cat_id)
        summary[cat_id] = {
            "label": cat["label"],
            "count": len(templates),
            "templates": [{"id": t["id"], "name": t["name"]} for t in templates],
        }
    return summary


# ═══════════════════════════════════════════════════════════════════════
# PRINT SUMMARY
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"Total templates: {len(ALL_TEMPLATES)}")
    print(f"Total categories: {len(ALL_CATEGORIES)}")
    print()

    summary = get_template_summary()
    for cat_id, info in summary.items():
        if info["count"] > 0:
            icon = ALL_CATEGORIES[cat_id].get("icon", "")
            print(f"  {icon} {info['label']} ({info['count']})")
            for t in info["templates"]:
                print(f"    → {t['id']}: {t['name']}")
    
    print()
    ld = get_ld_templates()
    print(f"L&D templates: {len(ld)}")
    for t in ld:
        print(f"  {t['icon']} {t['name']} — {t['description'][:80]}…")

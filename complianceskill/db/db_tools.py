"""
Postgres database-based security intelligence tools.
Aligned with the tactic-aware CVE → ATT&CK → Control pipeline.

Changes from original:
- CVEtoATTACKMapperTool: cache-first (cve_intelligence → cve_attack_mapping),
  returns attack_tactic_slug in addition to attack_tactic, includes CVE enrichment
  fields (cvss_score, epss_score, exploit_maturity) in the result.
- ATTACKtoControlMapperTool: reads from attack_control_mappings (4-col PK table)
  instead of attack_technique_control_mapping; supports tactic filter; falls back
  to attack_technique_control_mapping for rows pre-dating the tactic-aware pipeline.
- CPEResolverTool: unchanged in behaviour, kept for compatibility.
- New: CVEIntelligenceTool — returns full CVE enrichment record from cve_intelligence.
- New: TacticContextTool — reads/writes tactic_contexts cache.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.tools.base import ToolResult, SecurityTool
from app.storage.sqlalchemy_session import get_session, get_security_intel_session

logger = logging.getLogger(__name__)


# ============================================================================
# CVE Intelligence Tool  (new)
# ============================================================================

class CVEIntelligenceInput(BaseModel):
    cve_id: str = Field(description="CVE identifier e.g. CVE-2024-3400")


class CVEIntelligenceTool(SecurityTool):
    """
    Return full CVE enrichment record from cve_intelligence table.
    Checked first by CVEtoATTACKMapperTool to skip NVD/EPSS API calls
    for CVEs already processed.
    """

    @property
    def tool_name(self) -> str:
        return "cve_intelligence_lookup"

    def cache_key(self, **kwargs) -> str:
        return f"cve_intel:{kwargs.get('cve_id', '')}"

    def execute(self, cve_id: str) -> ToolResult:
        try:
            with get_security_intel_session("cve_attack") as session:
                row = session.execute(
                    text("""
                        SELECT cve_id, description, cvss_score, cvss_vector,
                               attack_vector, attack_complexity, privileges_required,
                               cwe_ids, affected_products, epss_score,
                               exploit_available, exploit_maturity, kev_listed,
                               published_date, last_modified,
                               technique_ids, tactics, frameworks_mapped
                        FROM cve_intelligence
                        WHERE cve_id = :cve_id
                    """),
                    {"cve_id": cve_id.upper()}
                ).fetchone()

                if not row:
                    return ToolResult(
                        success=True,
                        data={"cve_id": cve_id, "found": False},
                        source="postgres_cve_intelligence",
                        timestamp=datetime.utcnow().isoformat()
                    )

                return ToolResult(
                    success=True,
                    data={
                        "found": True,
                        "cve_id":              row[0],
                        "description":         row[1],
                        "cvss_score":          float(row[2]) if row[2] else None,
                        "cvss_vector":         row[3],
                        "attack_vector":       row[4],
                        "attack_complexity":   row[5],
                        "privileges_required": row[6],
                        "cwe_ids":             row[7] or [],
                        "affected_products":   row[8] or [],
                        "epss_score":          float(row[9]) if row[9] else None,
                        "exploit_available":   row[10],
                        "exploit_maturity":    row[11],
                        "kev_listed":          row[12],
                        "published_date":      str(row[13]) if row[13] else None,
                        "last_modified":       str(row[14]) if row[14] else None,
                        "technique_ids":       row[15] or [],
                        "tactics":             row[16] or [],
                        "frameworks_mapped":   row[17] or [],
                    },
                    source="postgres_cve_intelligence",
                    timestamp=datetime.utcnow().isoformat()
                )
        except Exception as e:
            logger.error(f"CVEIntelligenceTool error: {e}")
            return ToolResult(
                success=False, data=None,
                source="postgres_cve_intelligence",
                timestamp=datetime.utcnow().isoformat(),
                error_message=str(e)
            )


def create_cve_intelligence_tool() -> StructuredTool:
    tool = CVEIntelligenceTool()

    def _execute(cve_id: str) -> Dict[str, Any]:
        return tool.execute(cve_id).to_dict()

    return StructuredTool.from_function(
        func=_execute,
        name="cve_intelligence_lookup",
        description=(
            "Return full CVE enrichment record (CVSS, EPSS, CWE, KEV status, "
            "affected products, exploit maturity) from the local cve_intelligence cache. "
            "Call this before CVE API calls to avoid redundant network requests."
        ),
        args_schema=CVEIntelligenceInput,
    )


# ============================================================================
# CVE → ATT&CK Mapper  (fixed)
# ============================================================================

class CVEtoATTACKInput(BaseModel):
    cve_id: str = Field(description="CVE identifier e.g. CVE-2024-3400")
    tactic_filter: Optional[str] = Field(
        default=None,
        description="Optional ATT&CK tactic slug to filter results e.g. 'initial-access'"
    )


class CVEtoATTACKMapperTool(SecurityTool):
    """
    Map CVE to MITRE ATT&CK techniques via Postgres.

    Resolution order:
    1. Query cve_attack_mapping for existing (cve_id, technique, tactic) rows — return immediately if found.
    2. If no rows exist, return empty result with a flag indicating the CVE needs enrichment.
       The caller (CVEToATTACKMapperTool orchestrator) then runs CWE crosswalk + LLM mapping
       and writes results back to cve_attack_mapping before calling downstream tools.

    The tool no longer silently returns empty — it tells the caller exactly why
    (no rows vs table missing) so the orchestrator can take the right action.
    """

    @property
    def tool_name(self) -> str:
        return "cve_to_attack_mapper"

    def cache_key(self, **kwargs) -> str:
        cve_id = kwargs.get("cve_id", "")
        tactic = kwargs.get("tactic_filter", "all")
        return f"cve_attack:{cve_id}:{tactic}"

    def execute(self, cve_id: str, tactic_filter: Optional[str] = None) -> ToolResult:
        try:
            with get_security_intel_session("cve_attack") as session:
                try:
                    query = """
                        SELECT
                            attack_technique_id,
                            attack_tactic,
                            attack_tactic_slug,
                            mapping_source,
                            confidence_score,
                            cvss_score,
                            epss_score,
                            attack_vector,
                            cwe_ids,
                            exploit_available,
                            exploit_maturity,
                            notes
                        FROM cve_attack_mapping
                        WHERE cve_id = :cve_id
                    """
                    params: Dict[str, Any] = {"cve_id": cve_id.upper()}

                    if tactic_filter:
                        query += " AND attack_tactic_slug = :tactic"
                        params["tactic"] = tactic_filter

                    query += " ORDER BY confidence_score DESC"

                    rows = session.execute(text(query), params).fetchall()

                    if not rows:
                        return ToolResult(
                            success=True,
                            data={
                                "cve_id": cve_id,
                                "attack_techniques": [],
                                "needs_enrichment": True,
                                "message": (
                                    "No ATT&CK mappings found. "
                                    "Run CVEToATTACKMapperTool to generate mappings via "
                                    "CWE crosswalk and LLM before calling downstream tools."
                                )
                            },
                            source="postgres_cve_attack_mapping",
                            timestamp=datetime.utcnow().isoformat()
                        )

                    techniques = []
                    for row in rows:
                        techniques.append({
                            "technique_id":    row[0],
                            "tactic":          row[1],           # title-cased e.g. "Initial Access"
                            "tactic_slug":     row[2],           # slug e.g. "initial-access"
                            "mapping_source":  row[3],
                            "confidence_score":float(row[4]) if row[4] else None,
                            "cvss_score":      float(row[5]) if row[5] else None,
                            "epss_score":      float(row[6]) if row[6] else None,
                            "attack_vector":   row[7],
                            "cwe_ids":         row[8] or [],
                            "exploit_available": row[9],
                            "exploit_maturity": row[10],
                            "notes":           row[11],
                        })

                    return ToolResult(
                        success=True,
                        data={
                            "cve_id": cve_id,
                            "needs_enrichment": False,
                            "attack_techniques": techniques,
                            "tactic_slugs": list({t["tactic_slug"] for t in techniques if t["tactic_slug"]}),
                        },
                        source="postgres_cve_attack_mapping",
                        timestamp=datetime.utcnow().isoformat()
                    )

                except Exception as e:
                    if "does not exist" in str(e).lower() or "relation" in str(e).lower():
                        logger.warning(f"cve_attack_mapping table missing: {e}")
                        return ToolResult(
                            success=True,
                            data={
                                "cve_id": cve_id,
                                "attack_techniques": [],
                                "needs_enrichment": True,
                                "message": "cve_attack_mapping table not yet created. Run migrate_schema.sql."
                            },
                            source="postgres_cve_attack_mapping",
                            timestamp=datetime.utcnow().isoformat()
                        )
                    raise

        except Exception as e:
            logger.error(f"CVEtoATTACKMapperTool error: {e}")
            return ToolResult(
                success=False, data=None,
                source="postgres_cve_attack_mapping",
                timestamp=datetime.utcnow().isoformat(),
                error_message=str(e)
            )


def create_cve_to_attack_tool() -> StructuredTool:
    tool = CVEtoATTACKMapperTool()

    def _execute(cve_id: str, tactic_filter: Optional[str] = None) -> Dict[str, Any]:
        return tool.execute(cve_id, tactic_filter).to_dict()

    return StructuredTool.from_function(
        func=_execute,
        name="cve_to_attack_mapper",
        description=(
            "Map a CVE to MITRE ATT&CK techniques from the local Postgres cache. "
            "Returns technique IDs, tactic slugs, confidence scores, and CVE context "
            "(CVSS, EPSS, exploit maturity). "
            "If needs_enrichment=True in the response, run CVEToATTACKMapperTool "
            "to generate new mappings before calling downstream tools."
        ),
        args_schema=CVEtoATTACKInput,
    )


# ============================================================================
# ATT&CK → Control Mapper  (fixed — reads attack_control_mappings first)
# ============================================================================

class ATTACKtoControlInput(BaseModel):
    technique_id: str = Field(description="ATT&CK technique ID e.g. T1190")
    tactic: Optional[str] = Field(
        default=None,
        description="ATT&CK tactic slug to filter e.g. 'initial-access'. Recommended — different tactics produce different control mappings."
    )
    framework_ids: Optional[List[str]] = Field(
        default=None,
        description="Framework IDs to filter e.g. ['cis_v8_1', 'nist_800_53r5']"
    )
    min_confidence: Optional[str] = Field(
        default=None,
        description="Minimum confidence level: 'high', 'medium', or 'low'"
    )


class ATTACKtoControlMapperTool(SecurityTool):
    """
    Map ATT&CK technique (+ optional tactic) to framework controls.

    Resolution order:
    1. Query attack_control_mappings (4-col PK: technique, tactic, item, framework).
       This is the tactic-aware table written by AttackControlMappingTool.
    2. Fall back to attack_technique_control_mapping (legacy, no tactic column)
       for techniques that pre-date the tactic-aware pipeline.

    Callers should always pass tactic when known — the same technique maps to
    different controls under different tactics.
    """

    @property
    def tool_name(self) -> str:
        return "attack_to_control_mapper"

    def cache_key(self, **kwargs) -> str:
        technique = kwargs.get("technique_id", "")
        tactic = kwargs.get("tactic", "all")
        frameworks = ":".join(kwargs.get("framework_ids") or [])
        return f"attack_control:{technique}:{tactic}:{frameworks}"

    def execute(
        self,
        technique_id: str,
        tactic: Optional[str] = None,
        framework_ids: Optional[List[str]] = None,
        min_confidence: Optional[str] = None,
    ) -> ToolResult:
        try:
            with get_security_intel_session("cve_attack") as session:
                # ── Primary: tactic-aware attack_control_mappings ──────────────
                results = self._query_tactic_aware(
                    session, technique_id, tactic, framework_ids, min_confidence
                )

                if results:
                    return ToolResult(
                        success=True,
                        data={
                            "technique_id": technique_id,
                            "tactic":       tactic,
                            "source":       "attack_control_mappings",
                            "controls":     results,
                        },
                        source="postgres_attack_control_mappings",
                        timestamp=datetime.utcnow().isoformat()
                    )

                # ── Fallback: legacy attack_technique_control_mapping ──────────
                legacy = self._query_legacy(session, technique_id, framework_ids)
                return ToolResult(
                    success=True,
                    data={
                        "technique_id": technique_id,
                        "tactic":       tactic,
                        "source":       "attack_technique_control_mapping_legacy",
                        "controls":     legacy,
                        "message": (
                            "No tactic-aware mappings found. "
                            "Returned legacy mappings (no tactic context). "
                            "Run AttackControlMappingTool to generate tactic-specific mappings."
                        ) if not legacy else None,
                    },
                    source="postgres_attack_technique_control_mapping",
                    timestamp=datetime.utcnow().isoformat()
                )

        except Exception as e:
            logger.error(f"ATTACKtoControlMapperTool error: {e}")
            return ToolResult(
                success=False, data=None,
                source="postgres_attack_control_mapping",
                timestamp=datetime.utcnow().isoformat(),
                error_message=str(e)
            )

    def _query_tactic_aware(
        self,
        session: Session,
        technique_id: str,
        tactic: Optional[str],
        framework_ids: Optional[List[str]],
        min_confidence: Optional[str],
    ) -> List[Dict[str, Any]]:
        try:
            confidence_rank = {"high": 3, "medium": 2, "low": 1}
            min_rank = confidence_rank.get(min_confidence or "low", 1)

            query = """
                SELECT
                    technique_id, tactic, item_id, framework_id,
                    framework_name, control_family, item_title,
                    relevance_score, confidence, rationale,
                    tactic_risk_lens, blast_radius,
                    attack_tactics, attack_platforms, loss_outcomes,
                    validated
                FROM attack_control_mappings
                WHERE technique_id = :technique_id
                  AND CASE confidence
                        WHEN 'high'   THEN 3
                        WHEN 'medium' THEN 2
                        ELSE 1
                      END >= :min_rank
            """
            params: Dict[str, Any] = {
                "technique_id": technique_id.upper(),
                "min_rank": min_rank,
            }

            if tactic:
                query += " AND tactic = :tactic"
                params["tactic"] = tactic

            if framework_ids:
                placeholders = ", ".join(f":fw_{i}" for i in range(len(framework_ids)))
                query += f" AND framework_id IN ({placeholders})"
                for i, fid in enumerate(framework_ids):
                    params[f"fw_{i}"] = fid

            query += " ORDER BY relevance_score DESC, confidence DESC"

            rows = session.execute(text(query), params).fetchall()
            return [
                {
                    "technique_id":    row[0],
                    "tactic":          row[1],
                    "item_id":         row[2],
                    "framework_id":    row[3],
                    "framework_name":  row[4],
                    "control_family":  row[5],
                    "item_title":      row[6],
                    "relevance_score": float(row[7]) if row[7] else None,
                    "confidence":      row[8],
                    "rationale":       row[9],
                    "tactic_risk_lens":row[10],
                    "blast_radius":    row[11],
                    "attack_tactics":  row[12] or [],
                    "attack_platforms":row[13] or [],
                    "loss_outcomes":   row[14] or [],
                    "validated":       row[15],
                }
                for row in rows
            ]
        except Exception as e:
            if "does not exist" in str(e).lower():
                return []
            raise

    def _query_legacy(
        self,
        session: Session,
        technique_id: str,
        framework_ids: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        try:
            query = """
                SELECT
                    atcm.attack_technique_id,
                    c.id            AS control_id,
                    c.name          AS control_name,
                    c.description   AS control_description,
                    f.id            AS framework_id,
                    f.name          AS framework_name,
                    atcm.mitigation_effectiveness,
                    atcm.confidence_score,
                    atcm.notes
                FROM attack_technique_control_mapping atcm
                JOIN controls c   ON atcm.control_id = c.id
                JOIN frameworks f ON c.framework_id  = f.id
                WHERE atcm.attack_technique_id = :technique_id
            """
            params: Dict[str, Any] = {"technique_id": technique_id.upper()}

            if framework_ids:
                placeholders = ", ".join(f":fw_{i}" for i in range(len(framework_ids)))
                query += f" AND f.id IN ({placeholders})"
                for i, fid in enumerate(framework_ids):
                    params[f"fw_{i}"] = fid

            query += " ORDER BY atcm.confidence_score DESC"

            rows = session.execute(text(query), params).fetchall()
            return [
                {
                    "technique_id":           row[0],
                    "control_id":             row[1],
                    "control_name":           row[2],
                    "control_description":    row[3],
                    "framework_id":           row[4],
                    "framework_name":         row[5],
                    "mitigation_effectiveness": row[6],
                    "confidence_score":       float(row[7]) if row[7] else None,
                    "notes":                  row[8],
                    "tactic":                 None,   # legacy rows have no tactic
                }
                for row in rows
            ]
        except Exception as e:
            if "does not exist" in str(e).lower():
                return []
            raise


def create_attack_to_control_tool() -> StructuredTool:
    tool = ATTACKtoControlMapperTool()

    def _execute(
        technique_id: str,
        tactic: Optional[str] = None,
        framework_ids: Optional[List[str]] = None,
        min_confidence: Optional[str] = None,
    ) -> Dict[str, Any]:
        return tool.execute(technique_id, tactic, framework_ids, min_confidence).to_dict()

    return StructuredTool.from_function(
        func=_execute,
        name="attack_to_control_mapper",
        description=(
            "Map a MITRE ATT&CK technique to framework controls (CIS, NIST, HIPAA, etc.). "
            "Pass tactic when known — the same technique maps to different controls under "
            "different tactics. Returns controls with relevance scores, rationale, and "
            "tactic risk lens. Falls back to legacy table for pre-pipeline mappings."
        ),
        args_schema=ATTACKtoControlInput,
    )


# ============================================================================
# Tactic Context Tool  (new)
# ============================================================================

class TacticContextInput(BaseModel):
    technique_id: str = Field(description="ATT&CK technique ID e.g. T1078")
    tactic: str = Field(description="ATT&CK tactic slug e.g. 'persistence'")


class TacticContextTool(SecurityTool):
    """
    Read cached tactic risk lens from tactic_contexts table.
    Returns None if not yet derived — caller should invoke TacticContextualiserTool
    to generate and cache the lens.
    """

    @property
    def tool_name(self) -> str:
        return "tactic_context_lookup"

    def cache_key(self, **kwargs) -> str:
        return f"tactic_ctx:{kwargs.get('technique_id','')}:{kwargs.get('tactic','')}"

    def execute(self, technique_id: str, tactic: str) -> ToolResult:
        try:
            with get_security_intel_session("cve_attack") as session:
                row = session.execute(
                    text("""
                        SELECT technique_id, tactic, tactic_risk_lens,
                               blast_radius, primary_asset_types, derived_at
                        FROM tactic_contexts
                        WHERE technique_id = :tid AND tactic = :tactic
                    """),
                    {"tid": technique_id.upper(), "tactic": tactic}
                ).fetchone()

                if not row:
                    return ToolResult(
                        success=True,
                        data={
                            "found": False,
                            "technique_id": technique_id,
                            "tactic": tactic,
                            "message": "Tactic context not yet derived. Run TacticContextualiserTool."
                        },
                        source="postgres_tactic_contexts",
                        timestamp=datetime.utcnow().isoformat()
                    )

                return ToolResult(
                    success=True,
                    data={
                        "found":              True,
                        "technique_id":       row[0],
                        "tactic":             row[1],
                        "tactic_risk_lens":   row[2],
                        "blast_radius":       row[3],
                        "primary_asset_types":row[4] or [],
                        "derived_at":         str(row[5]) if row[5] else None,
                        "source":             "cache_postgres",
                    },
                    source="postgres_tactic_contexts",
                    timestamp=datetime.utcnow().isoformat()
                )
        except Exception as e:
            logger.error(f"TacticContextTool error: {e}")
            return ToolResult(
                success=False, data=None,
                source="postgres_tactic_contexts",
                timestamp=datetime.utcnow().isoformat(),
                error_message=str(e)
            )


def create_tactic_context_tool() -> StructuredTool:
    tool = TacticContextTool()

    def _execute(technique_id: str, tactic: str) -> Dict[str, Any]:
        return tool.execute(technique_id, tactic).to_dict()

    return StructuredTool.from_function(
        func=_execute,
        name="tactic_context_lookup",
        description=(
            "Look up the cached tactic risk lens for a (technique, tactic) pair. "
            "Returns the natural-language risk framing used for vector store retrieval "
            "and LLM mapping prompts. If found=False, call TacticContextualiserTool first."
        ),
        args_schema=TacticContextInput,
    )


# ============================================================================
# CPE Resolver Tool  (unchanged)
# ============================================================================

class CPEResolverInput(BaseModel):
    vendor: Optional[str] = Field(default=None, description="Vendor name e.g. apache")
    product: Optional[str] = Field(default=None, description="Product name e.g. log4j")
    version: Optional[str] = Field(default=None, description="Version e.g. 2.14.1")
    cpe_uri: Optional[str] = Field(default=None, description="Full CPE URI")


class CPEResolverTool(SecurityTool):

    @property
    def tool_name(self) -> str:
        return "cpe_resolver"

    def cache_key(self, **kwargs) -> str:
        cpe_uri = kwargs.get("cpe_uri", "")
        vendor  = kwargs.get("vendor", "")
        product = kwargs.get("product", "")
        version = kwargs.get("version", "")
        return f"cpe_resolver:{cpe_uri or f'{vendor}:{product}:{version}'}"

    def execute(
        self,
        vendor: Optional[str] = None,
        product: Optional[str] = None,
        version: Optional[str] = None,
        cpe_uri: Optional[str] = None
    ) -> ToolResult:
        try:
            with get_security_intel_session("cpe") as session:
                try:
                    if cpe_uri:
                        stmt = text("""
                            SELECT cve_id, version_start, version_end,
                                   version_start_including, version_end_including
                            FROM cve_cpe_affected WHERE cpe_uri = :cpe_uri ORDER BY cve_id
                        """)
                        result = session.execute(stmt, {"cpe_uri": cpe_uri})
                    elif vendor and product:
                        query = """
                            SELECT DISTINCT cca.cve_id, cca.version_start, cca.version_end,
                                   cca.version_start_including, cca.version_end_including,
                                   cd.cpe_uri, cd.cpe_title
                            FROM cve_cpe_affected cca
                            JOIN cpe_dictionary cd ON cca.cpe_uri = cd.cpe_uri
                            WHERE cd.vendor = :vendor AND cd.product = :product
                        """
                        params: Dict[str, Any] = {"vendor": vendor, "product": product}
                        if version:
                            query += " AND cd.version = :version"
                            params["version"] = version
                        query += " ORDER BY cca.cve_id"
                        result = session.execute(text(query), params)
                    else:
                        return ToolResult(
                            success=False, data=None,
                            source="postgres_cpe_resolver",
                            timestamp=datetime.utcnow().isoformat(),
                            error_message="Must provide either cpe_uri or both vendor and product"
                        )

                    rows = result.fetchall()
                    if not rows:
                        return ToolResult(
                            success=True,
                            data={"cves": [], "message": "No CVEs found for the specified CPE"},
                            source="postgres_cpe_resolver",
                            timestamp=datetime.utcnow().isoformat()
                        )

                    cves = []
                    for row in rows:
                        entry: Dict[str, Any] = {
                            "cve_id":                 row[0],
                            "version_start":          row[1],
                            "version_end":            row[2],
                            "version_start_including":row[3],
                            "version_end_including":  row[4],
                        }
                        if len(row) > 5:
                            entry["cpe_uri"]   = row[5]
                            entry["cpe_title"] = row[6]
                        cves.append(entry)

                    return ToolResult(
                        success=True,
                        data={"cves": cves},
                        source="postgres_cpe_resolver",
                        timestamp=datetime.utcnow().isoformat()
                    )

                except Exception as e:
                    if "does not exist" in str(e).lower() or "relation" in str(e).lower():
                        return ToolResult(
                            success=True,
                            data={"cves": [], "message": "CPE tables not yet populated"},
                            source="postgres_cpe_resolver",
                            timestamp=datetime.utcnow().isoformat()
                        )
                    raise

        except Exception as e:
            logger.error(f"CPEResolverTool error: {e}")
            return ToolResult(
                success=False, data=None,
                source="postgres_cpe_resolver",
                timestamp=datetime.utcnow().isoformat(),
                error_message=str(e)
            )


def create_cpe_resolver_tool() -> StructuredTool:
    tool = CPEResolverTool()

    def _execute(
        vendor: Optional[str] = None,
        product: Optional[str] = None,
        version: Optional[str] = None,
        cpe_uri: Optional[str] = None
    ) -> Dict[str, Any]:
        return tool.execute(vendor, product, version, cpe_uri).to_dict()

    return StructuredTool.from_function(
        func=_execute,
        name="cpe_resolver",
        description=(
            "Resolve CPE (Common Platform Enumeration) to find affected CVEs. "
            "Search by vendor/product/version or full CPE URI."
        ),
        args_schema=CPEResolverInput,
    )

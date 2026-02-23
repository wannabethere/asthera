"""
Cross-framework mapping validation.

After all frameworks are ingested, this pass resolves the deferred
`target_control_id` references in `cross_framework_mappings`.

During ingestion, CIS controls may reference SOC2 codes like "CC 2.1" before
SOC2 controls are ingested. The orchestrator stores `target_raw_code` but leaves
`target_control_id = NULL`. This validator runs a second pass to match those
raw codes to actual Postgres control IDs.

Also generates a summary report of mapping coverage and unresolved references.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from app.storage.sqlalchemy_session import get_session
from app.ingestion.models import CrossFrameworkMapping, Control, Framework

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation report
# ---------------------------------------------------------------------------

@dataclass
class MappingValidationReport:
    total_mappings: int = 0
    resolved: int = 0
    unresolved: int = 0
    # List of (source_control_id, target_framework_id, target_raw_code) for unresolved
    unresolved_details: List[Tuple[str, str, str]] = field(default_factory=list)
    # Coverage per (source_framework, target_framework)
    coverage: Dict[Tuple[str, str], Dict] = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [
            "=" * 60,
            "Cross-Framework Mapping Validation Report",
            "=" * 60,
            f"Total mappings:  {self.total_mappings}",
            f"Resolved:        {self.resolved} ({self._pct(self.resolved)}%)",
            f"Unresolved:      {self.unresolved} ({self._pct(self.unresolved)}%)",
        ]
        if self.coverage:
            lines.append("\nCoverage by framework pair:")
            for (src_fw, tgt_fw), stats in sorted(self.coverage.items()):
                pct = stats["resolved"] / stats["total"] * 100 if stats["total"] else 0
                lines.append(
                    f"  {src_fw} → {tgt_fw}: "
                    f"{stats['resolved']}/{stats['total']} ({pct:.0f}%)"
                )
        if self.unresolved_details:
            lines.append(f"\nFirst 20 unresolved mappings:")
            for src, tgt_fw, raw_code in self.unresolved_details[:20]:
                lines.append(f"  {src} → {tgt_fw} '{raw_code}'")
        lines.append("=" * 60)
        return "\n".join(lines)

    def _pct(self, n: int) -> str:
        if self.total_mappings == 0:
            return "0"
        return f"{n / self.total_mappings * 100:.1f}"


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class CrossFrameworkMappingValidator:
    """
    Resolves unlinked cross-framework mapping records and validates coverage.
    """

    def validate_and_resolve(self) -> MappingValidationReport:
        """
        Main entry point. Resolves all unresolved mappings and returns a report.
        """
        with get_session() as session:
            # Build lookup: (framework_id, control_code) → postgres control.id
            control_lookup = self._build_control_lookup(session)
            logger.info(f"Control lookup table built: {len(control_lookup)} entries")

            resolved_count = self._resolve_mappings(session, control_lookup)
            report = self._generate_report(session, resolved_count)

        return report

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def _build_control_lookup(self, session: Session) -> Dict[Tuple[str, str], str]:
        """
        Returns dict mapping (framework_id, normalized_code) → control.id.
        Normalization: strip whitespace, lowercase spaces for comparison.
        
        Also includes requirements that can be resolved to controls via RequirementControl
        relationships. This handles cases where cross-framework mappings reference requirements
        (e.g., SOC2 "CC 2.1") rather than direct control codes.
        """
        from app.ingestion.models import Requirement, RequirementControl
        
        # Build control lookup
        stmt = select(Control.id, Control.framework_id, Control.control_code)
        rows = session.execute(stmt).all()

        lookup: Dict[Tuple[str, str], str] = {}
        for ctrl_id, fw_id, ctrl_code in rows:
            lookup[(fw_id, ctrl_code.strip())] = ctrl_id
            # Also index without spaces for codes like "CC 2.1" → "CC2.1"
            lookup[(fw_id, ctrl_code.replace(" ", "").strip())] = ctrl_id
        
        # Also build requirement-to-control mapping for frameworks that use requirements
        # (e.g., SOC2 requirements like "CC 2.1" that are referenced in cross-framework mappings)
        req_stmt = select(Requirement.id, Requirement.framework_id, Requirement.requirement_code)
        req_rows = session.execute(req_stmt).all()
        
        # For each requirement, find associated controls via RequirementControl
        for req_id, fw_id, req_code in req_rows:
            normalized_req_code = req_code.strip()
            normalized_req_code_no_space = req_code.replace(" ", "").strip()
            
            # Find controls linked to this requirement
            req_controls = session.execute(
                select(RequirementControl.control_id).where(
                    RequirementControl.requirement_id == req_id
                )
            ).scalars().all()
            
            # If requirement has linked controls, add them to lookup
            if req_controls:
                # Use the first linked control (or could use all, but first is simplest)
                control_id = req_controls[0]
                
                # Add requirement code → control mapping
                if (fw_id, normalized_req_code) not in lookup:
                    lookup[(fw_id, normalized_req_code)] = control_id
                if (fw_id, normalized_req_code_no_space) not in lookup:
                    lookup[(fw_id, normalized_req_code_no_space)] = control_id
            else:
                # Fallback: If no controls linked to requirement, try to find controls
                # that mention this requirement code in their framework_requirement metadata
                # This handles cases where controls reference requirements but aren't linked via RequirementControl
                controls_with_req = session.execute(
                    select(Control.id, Control.metadata_)
                    .where(Control.framework_id == fw_id)
                ).all()
                
                for ctrl_id, metadata in controls_with_req:
                    if not metadata:
                        continue
                    # Check if control's framework_requirement field contains this requirement code
                    framework_req = metadata.get("framework_requirement") or ""
                    if normalized_req_code in framework_req or normalized_req_code_no_space in framework_req:
                        # Add requirement code → control mapping
                        if (fw_id, normalized_req_code) not in lookup:
                            lookup[(fw_id, normalized_req_code)] = ctrl_id
                        if (fw_id, normalized_req_code_no_space) not in lookup:
                            lookup[(fw_id, normalized_req_code_no_space)] = ctrl_id
                        break  # Use first matching control
        
        return lookup

    def _resolve_mappings(
        self, session: Session,
        control_lookup: Dict[Tuple[str, str], str],
    ) -> int:
        """
        Attempt to resolve all mappings where target_control_id is NULL.
        Returns number of newly resolved mappings.
        """
        unresolved = session.execute(
            select(CrossFrameworkMapping).where(
                CrossFrameworkMapping.target_control_id.is_(None)
            )
        ).scalars().all()

        resolved = 0
        for mapping in unresolved:
            if not mapping.target_raw_code:
                continue

            target_fw = mapping.target_framework_id
            raw_code = mapping.target_raw_code.strip()

            # Try exact match first
            ctrl_id = control_lookup.get((target_fw, raw_code))

            # Try without spaces (e.g. "CC 2.1" → "CC2.1")
            if not ctrl_id:
                ctrl_id = control_lookup.get((target_fw, raw_code.replace(" ", "")))

            # Try case-insensitive
            if not ctrl_id:
                ctrl_id = self._case_insensitive_lookup(control_lookup, target_fw, raw_code)

            if ctrl_id:
                mapping.target_control_id = ctrl_id
                resolved += 1
                logger.debug(
                    f"Resolved: {mapping.source_control_id} → {target_fw}/{raw_code} = {ctrl_id}"
                )
            else:
                logger.debug(
                    f"Unresolved: {mapping.source_control_id} → {target_fw}/{raw_code}"
                )

        logger.info(f"Resolved {resolved}/{len(unresolved)} previously unlinked mappings")
        return resolved

    @staticmethod
    def _case_insensitive_lookup(
        lookup: Dict[Tuple[str, str], str],
        fw_id: str, raw_code: str,
    ) -> Optional[str]:
        raw_lower = raw_code.lower()
        for (l_fw, l_code), ctrl_id in lookup.items():
            if l_fw == fw_id and l_code.lower() == raw_lower:
                return ctrl_id
        return None

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def _generate_report(
        self, session: Session, newly_resolved: int
    ) -> MappingValidationReport:
        report = MappingValidationReport()

        # Total counts
        all_mappings = session.execute(select(CrossFrameworkMapping)).scalars().all()
        report.total_mappings = len(all_mappings)
        report.resolved = sum(1 for m in all_mappings if m.target_control_id is not None)
        report.unresolved = report.total_mappings - report.resolved

        # Unresolved details
        report.unresolved_details = [
            (m.source_control_id, m.target_framework_id, m.target_raw_code or "")
            for m in all_mappings
            if m.target_control_id is None
        ]

        # Coverage by framework pair
        coverage: Dict[Tuple[str, str], Dict] = {}
        for m in all_mappings:
            key = (m.source_framework_id, m.target_framework_id)
            if key not in coverage:
                coverage[key] = {"total": 0, "resolved": 0}
            coverage[key]["total"] += 1
            if m.target_control_id is not None:
                coverage[key]["resolved"] += 1
        report.coverage = coverage

        return report


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def validate_cross_framework_mappings() -> MappingValidationReport:
    """
    Run the full validation pass and return a report.

    Usage:
        report = validate_cross_framework_mappings()
        print(report)
    """
    validator = CrossFrameworkMappingValidator()
    report = validator.validate_and_resolve()
    logger.info(f"Validation complete. {report.resolved}/{report.total_mappings} mappings resolved.")
    return report

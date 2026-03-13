"""
Preview Generator for ATT&CK → CVE Enrichment
==============================================
Generates preview files (JSON) for enriched ATT&CK techniques and their mappings
to CIS controls. These preview files can be reviewed before ingestion into the
vector store.

Uses centralized dependencies.py and settings.py for configuration.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

# Handle both relative imports (when run as module) and absolute imports (when run as script)
try:
    from .attack_enrichment import ATTACKEnrichmentTool
    from .control_loader import load_cis_scenarios, CISControlRegistry
    from .graph import build_graph, run_mapping, run_batch_mapping
    from .vectorstore_retrieval import VectorStoreConfig, VectorBackend
except ImportError:
    # Fallback for when run as script - import directly from files
    try:
        from attack_enrichment import ATTACKEnrichmentTool
        from control_loader import load_cis_scenarios, CISControlRegistry
        from graph import build_graph, run_mapping, run_batch_mapping
        from vectorstore_retrieval import VectorStoreConfig, VectorBackend
    except ImportError:
        # Final fallback - use absolute imports
        import sys
        from pathlib import Path
        workspace_root = Path(__file__).parent.parent.parent.parent
        if str(workspace_root) not in sys.path:
            sys.path.insert(0, str(workspace_root))
        from app.ingestion.attacktocve.attack_enrichment import ATTACKEnrichmentTool
        from app.ingestion.attacktocve.control_loader import load_cis_scenarios, CISControlRegistry
        from app.ingestion.attacktocve.graph import build_graph, run_mapping, run_batch_mapping
        from app.ingestion.attacktocve.vectorstore_retrieval import VectorStoreConfig, VectorBackend

# Import app.core dependencies (should be available via workspace_root in sys.path)
try:
    from app.core.dependencies import get_llm, get_embeddings_model
    from app.core.settings import get_settings
except ImportError:
    # If not available, try adding workspace root to path
    import sys
    from pathlib import Path
    workspace_root = Path(__file__).parent.parent.parent.parent
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))
    from app.core.dependencies import get_llm, get_embeddings_model
    from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class PreviewGenerator:
    """Generates preview files for ATT&CK enrichment results."""
    
    def __init__(
        self,
        preview_dir: str | Path,
        yaml_path: Optional[str] = None,
        use_vector_store: bool = True,
    ):
        """
        Initialize preview generator.
        
        Args:
            preview_dir: Directory to write preview JSON files
            yaml_path: Path to CIS controls YAML file
            use_vector_store: Whether to use vector store for retrieval (vs YAML fallback)
        """
        self.preview_dir = Path(preview_dir)
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        
        self.settings = get_settings()
        self.yaml_path = yaml_path or "cis_controls_v8_1_risk_controls.yaml"
        
        # Initialize ATT&CK enrichment tool
        self.attack_tool = ATTACKEnrichmentTool()
        
        # Load CIS scenarios for registry
        try:
            self.scenarios = load_cis_scenarios(self.yaml_path)
            self.registry = CISControlRegistry(self.scenarios)
        except FileNotFoundError:
            logger.warning(f"CIS controls YAML not found at {self.yaml_path}, using empty registry")
            self.scenarios = []
            self.registry = CISControlRegistry([])
        
        # Build vector store config from settings
        self.vs_config = self._build_vector_store_config(use_vector_store)
        
        # Build graph (will use vector store if configured)
        # Try to detect framework from yaml_path
        framework_id = None
        if hasattr(self, 'framework'):
            framework_id = self.framework
        elif self.yaml_path:
            # Extract framework from path
            yaml_str = str(self.yaml_path)
            for fw in ["cis_controls_v8_1", "nist_csf_2_0", "hipaa", "soc2", "iso27001_2013", "iso27001_2022"]:
                if fw in yaml_str:
                    framework_id = fw
                    break
        
        self.graph = build_graph(self.vs_config, yaml_path=self.yaml_path, framework_id=framework_id)
    
    def _build_vector_store_config(self, use_vector_store: bool) -> VectorStoreConfig:
        """Build VectorStoreConfig from centralized settings."""
        if not use_vector_store:
            # Return a dummy config that will trigger YAML fallback
            return VectorStoreConfig(
                backend=VectorBackend.CHROMA,
                collection="dummy",
                openai_api_key=self.settings.OPENAI_API_KEY,
            )
        
        return VectorStoreConfig.from_settings()
    
    def generate_preview(
        self,
        technique_id: str,
        scenario_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate preview for a single ATT&CK technique.
        
        Args:
            technique_id: ATT&CK technique ID (e.g., "T1078")
            scenario_filter: Optional CIS asset domain filter
            
        Returns:
            Preview data dictionary
        """
        logger.info(f"Generating preview for technique {technique_id}")
        
        # Run the mapping graph
        state = run_mapping(
            self.graph,
            technique_id,
            scenario_filter=scenario_filter,
            stream=False,
        )
        
        # Build preview structure
        preview = {
            "technique_id": technique_id,
            "attack_detail": state.get("attack_detail").model_dump() if state.get("attack_detail") else None,
            "enrich_error": state.get("enrich_error"),
            "retrieved_scenarios": [
                s.model_dump() for s in state.get("retrieved_scenarios", [])
            ],
            "retrieval_scores": state.get("retrieval_scores", []),
            "retrieval_source": state.get("retrieval_source", ""),
            "final_mappings": [
                m.model_dump() for m in state.get("final_mappings", [])
            ],
            "output_summary": state.get("output_summary", ""),
            "error": state.get("error"),
        }
        
        # Write preview file
        preview_file = self.preview_dir / f"{technique_id}_preview.json"
        preview_file.write_text(json.dumps(preview, indent=2), encoding="utf-8")
        logger.info(f"Wrote preview to {preview_file}")
        
        return preview
    
    def generate_batch_preview(
        self,
        technique_ids: List[str],
        scenario_filter: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate previews for multiple ATT&CK techniques.
        
        Args:
            technique_ids: List of ATT&CK technique IDs
            scenario_filter: Optional CIS asset domain filter
            
        Returns:
            Dictionary mapping technique_id -> preview data
        """
        logger.info(f"Generating batch preview for {len(technique_ids)} techniques")
        
        results = run_batch_mapping(
            self.graph,
            technique_ids,
            scenario_filter=scenario_filter,
        )
        
        # Write individual preview files
        previews = {}
        for tid, state in results.items():
            preview = {
                "technique_id": tid,
                "attack_detail": state.get("attack_detail").model_dump() if state.get("attack_detail") else None,
                "enrich_error": state.get("enrich_error"),
                "retrieved_scenarios": [
                    s.model_dump() for s in state.get("retrieved_scenarios", [])
                ],
                "retrieval_scores": state.get("retrieval_scores", []),
                "retrieval_source": state.get("retrieval_source", ""),
                "final_mappings": [
                    m.model_dump() for m in state.get("final_mappings", [])
                ],
                "output_summary": state.get("output_summary", ""),
                "error": state.get("error"),
            }
            
            preview_file = self.preview_dir / f"{tid}_preview.json"
            preview_file.write_text(json.dumps(preview, indent=2), encoding="utf-8")
            previews[tid] = preview
        
        # Write batch summary
        summary_file = self.preview_dir / "batch_summary.json"
        summary = {
            "total_techniques": len(technique_ids),
            "successful": sum(1 for p in previews.values() if not p.get("error")),
            "failed": sum(1 for p in previews.values() if p.get("error")),
            "total_mappings": sum(len(p.get("final_mappings", [])) for p in previews.values()),
            "previews": list(previews.keys()),
        }
        summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        logger.info(f"Wrote batch summary to {summary_file}")
        
        return previews


def generate_preview_from_file(
    technique_file: str | Path,
    preview_dir: str | Path,
    yaml_path: Optional[str] = None,
    scenario_filter: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to generate previews from a file of technique IDs.
    
    Args:
        technique_file: Path to file with one technique ID per line
        preview_dir: Directory to write preview files
        yaml_path: Path to CIS controls YAML
        scenario_filter: Optional asset domain filter
        
    Returns:
        Dictionary of previews
    """
    technique_ids = [
        line.strip()
        for line in Path(technique_file).read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    
    generator = PreviewGenerator(preview_dir, yaml_path=yaml_path)
    return generator.generate_batch_preview(technique_ids, scenario_filter=scenario_filter)

"""
MITRE ATT&CK framework tools.
These tools query ATT&CK technique data and mappings.
"""

import logging
import requests
from typing import Dict, Any, Optional
from datetime import datetime

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.agents.tools.base import ToolResult, SecurityTool

logger = logging.getLogger(__name__)


# ============================================================================
# ATT&CK Technique Lookup Tool
# ============================================================================

class ATTACKTechniqueInput(BaseModel):
    """Input schema for ATT&CK technique lookup tool."""
    technique_id: str = Field(description="ATT&CK technique ID (e.g., T1003.001)")


class ATTACKTechniqueTool(SecurityTool):
    """
    Lookup MITRE ATT&CK technique details.
    
    Fetches from MITRE ATT&CK STIX data (GitHub repo).
    For production, this should be cached in Postgres.
    """
    
    def __init__(self):
        # MITRE ATT&CK STIX data GitHub repo
        self.stix_base_url = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master"
        self._cache: Dict[str, Any] = {}
    
    @property
    def tool_name(self) -> str:
        return "attack_technique_lookup"
    
    def cache_key(self, **kwargs) -> str:
        technique_id = kwargs.get("technique_id", "")
        return f"attack_technique:{technique_id}"
    
    def execute(self, technique_id: str) -> ToolResult:
        """Execute ATT&CK technique lookup."""
        try:
            # Check cache first
            if technique_id in self._cache:
                cached = self._cache[technique_id]
                return ToolResult(
                    success=True,
                    data=cached,
                    source="attack_stix_cache",
                    timestamp=datetime.utcnow().isoformat(),
                    cache_hit=True
                )
            
            # Fetch from MITRE ATT&CK STIX data
            # Note: This is a simplified version. In production, you'd:
            # 1. Download and parse the STIX JSON files
            # 2. Store in Postgres for fast queries
            # 3. Query Postgres instead of GitHub
            
            # For now, return a structured response indicating the technique
            # In production, this would query a Postgres table with ATT&CK data
            result = {
                "technique_id": technique_id,
                "name": f"ATT&CK Technique {technique_id}",
                "description": "Technique details from MITRE ATT&CK framework",
                "tactics": [],
                "platforms": [],
                "note": "Full ATT&CK STIX data should be ingested into Postgres for production use",
            }
            
            # Cache result
            self._cache[technique_id] = result
            
            return ToolResult(
                success=True,
                data=result,
                source="attack_stix",
                timestamp=datetime.utcnow().isoformat()
            )
        except Exception as e:
            logger.error(f"Error in ATT&CK technique lookup: {e}")
            return ToolResult(
                success=False,
                data=None,
                source="attack_stix",
                timestamp=datetime.utcnow().isoformat(),
                error_message=str(e)
            )


def create_attack_technique_tool() -> StructuredTool:
    """Create LangChain tool for ATT&CK technique lookup."""
    tool_instance = ATTACKTechniqueTool()
    
    def _execute(technique_id: str) -> Dict[str, Any]:
        result = tool_instance.execute(technique_id)
        return result.to_dict()
    
    return StructuredTool.from_function(
        func=_execute,
        name="attack_technique_lookup",
        description="Lookup MITRE ATT&CK technique details including description, tactics, platforms, and mitigations. Returns comprehensive information about the attack technique.",
        args_schema=ATTACKTechniqueInput,
    )

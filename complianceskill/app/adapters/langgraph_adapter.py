"""
LangGraph Adapter (Legacy)

⚠️ DEPRECATED: This adapter has been refactored into:
- BaseLangGraphAdapter: Generic base adapter
- CSODLangGraphAdapter: CSOD-specific adapter

This file is kept for backward compatibility. New code should use:
- BaseLangGraphAdapter for generic workflows
- CSODLangGraphAdapter for CSOD workflows
- Create specialized adapters for other workflows (MDL, DT, etc.)

This adapter now aliases to BaseLangGraphAdapter for backward compatibility.
"""

from app.adapters.base_langgraph_adapter import BaseLangGraphAdapter

# Backward compatibility alias
LangGraphAdapter = BaseLangGraphAdapter

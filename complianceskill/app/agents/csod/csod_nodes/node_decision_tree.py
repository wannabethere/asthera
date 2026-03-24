"""
DEPRECATED — merged into node_scoring.py as csod_metric_qualification_node.

This module re-exports the merged node for backward compatibility.
"""
from app.agents.csod.csod_nodes.node_scoring import csod_metric_qualification_node

# Backward compat alias
csod_decision_tree_resolver_node = csod_metric_qualification_node

"""
Detection & Triage Workflows — Compliance workflow (original pipeline).
"""
from .workflow import (
    build_compliance_workflow,
    create_compliance_app,
    get_compliance_app,
)

__all__ = [
    "build_compliance_workflow",
    "create_compliance_app",
    "get_compliance_app",
]

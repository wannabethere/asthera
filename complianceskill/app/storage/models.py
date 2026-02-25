"""
Data models for Contextual Graph PostgreSQL entities

DEPRECATED: Models have been moved to app/models/storage.py
This file now re-exports for backward compatibility.
"""
from app.models.storage import (
    Control,
    Requirement,
    EvidenceType,
    ControlRequirementMapping,
    ComplianceMeasurement,
    ControlRiskAnalytics,
)

__all__ = [
    "Control",
    "Requirement",
    "EvidenceType",
    "ControlRequirementMapping",
    "ComplianceMeasurement",
    "ControlRiskAnalytics",
]

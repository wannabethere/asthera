"""
Configuration rules for LLM-based extraction agents.

This module defines the structure for configurable extraction rules that allow
the extractors to work for different domains (compliance, finance, healthcare, etc.)
instead of being hardcoded for compliance.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import json


@dataclass
class FieldExtractionRule:
    """Defines a field to extract from text"""
    name: str
    description: str
    data_type: str = "string"  # string, list, int, float, bool
    required: bool = False
    default_value: Any = None
    validation_rules: Optional[Dict[str, Any]] = None
    examples: Optional[List[str]] = None


@dataclass
class ExtractionRules:
    """Complete set of rules for an extraction task"""
    extraction_type: str  # e.g., "context", "control", "evidence", "requirement"
    domain: str  # e.g., "compliance", "finance", "healthcare"
    
    # System prompt configuration
    system_role: str  # Role description for the LLM
    system_instructions: str  # Detailed instructions for extraction
    
    # Fields to extract
    fields: List[FieldExtractionRule] = field(default_factory=list)
    
    # Document generation rules (for creating rich documents)
    document_sections: List[Dict[str, str]] = field(default_factory=list)
    
    # Prompt templates
    human_prompt_template: str = "{input}"
    human_prompt_variables: List[str] = field(default_factory=list)
    
    # Output configuration
    output_format: str = "json"  # json, text
    use_json_parser: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "extraction_type": self.extraction_type,
            "domain": self.domain,
            "system_role": self.system_role,
            "system_instructions": self.system_instructions,
            "fields": [
                {
                    "name": f.name,
                    "description": f.description,
                    "data_type": f.data_type,
                    "required": f.required,
                    "default_value": f.default_value,
                    "validation_rules": f.validation_rules,
                    "examples": f.examples
                }
                for f in self.fields
            ],
            "document_sections": self.document_sections,
            "human_prompt_template": self.human_prompt_template,
            "human_prompt_variables": self.human_prompt_variables,
            "output_format": self.output_format,
            "use_json_parser": self.use_json_parser
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionRules":
        """Create from dictionary"""
        fields = [
            FieldExtractionRule(
                name=f["name"],
                description=f["description"],
                data_type=f.get("data_type", "string"),
                required=f.get("required", False),
                default_value=f.get("default_value"),
                validation_rules=f.get("validation_rules"),
                examples=f.get("examples")
            )
            for f in data.get("fields", [])
        ]
        
        return cls(
            extraction_type=data["extraction_type"],
            domain=data["domain"],
            system_role=data["system_role"],
            system_instructions=data["system_instructions"],
            fields=fields,
            document_sections=data.get("document_sections", []),
            human_prompt_template=data.get("human_prompt_template", "{input}"),
            human_prompt_variables=data.get("human_prompt_variables", []),
            output_format=data.get("output_format", "json"),
            use_json_parser=data.get("use_json_parser", True)
        )


# Predefined rules for backward compatibility (compliance domain)
def get_compliance_context_rules() -> ExtractionRules:
    """Get compliance-specific context extraction rules"""
    return ExtractionRules(
        extraction_type="context",
        domain="compliance",
        system_role="expert at analyzing organizational contexts for compliance",
        system_instructions="""Extract structured information from the description:
1. Industry (healthcare, technology, finance, etc.)
2. Organization size (small, medium, large)
3. Employee count range
4. Maturity level (nascent, developing, mature)
5. Regulatory frameworks applicable
6. Data types handled (ePHI, PII, PCI, etc.)
7. Systems in use
8. Automation capability (low, medium, high)
9. Current situation (pre_audit, first_audit_prep, ongoing_compliance, etc.)
10. Audit timeline (days until audit if applicable)

Return a JSON object with all extracted fields.""",
        fields=[
            FieldExtractionRule("context_type", "Type of context", default_value="organizational_situational"),
            FieldExtractionRule("industry", "Industry sector"),
            FieldExtractionRule("organization_size", "Organization size", examples=["small", "medium", "large"]),
            FieldExtractionRule("employee_count_range", "Employee count range"),
            FieldExtractionRule("maturity_level", "Maturity level", examples=["nascent", "developing", "mature"]),
            FieldExtractionRule("regulatory_frameworks", "Regulatory frameworks", data_type="list", default_value=[]),
            FieldExtractionRule("data_types", "Data types handled", data_type="list", default_value=[]),
            FieldExtractionRule("systems", "Systems in use", data_type="list", default_value=[]),
            FieldExtractionRule("automation_capability", "Automation capability", examples=["low", "medium", "high"]),
            FieldExtractionRule("current_situation", "Current situation"),
            FieldExtractionRule("audit_timeline_days", "Audit timeline in days", data_type="int"),
        ],
        human_prompt_template="""Extract context information from this description:

{description}

Provide structured context metadata.""",
        human_prompt_variables=["description"]
    )


def get_compliance_control_rules() -> ExtractionRules:
    """Get compliance-specific control extraction rules"""
    return ExtractionRules(
        extraction_type="control",
        domain="compliance",
        system_role="expert at extracting compliance control information from regulatory text",
        system_instructions="""Extract the following information:
1. Control ID (e.g., "HIPAA-AC-001", "SOC2-CC6.1")
2. Control name
3. Control description
4. Category (e.g., "access_control", "encryption", "audit")
5. Requirements (list of atomic requirements)
6. Evidence types needed
7. Implementation guidance

For the context document, create a rich, detailed description that includes:
- Control overview and purpose
- Context-specific implementation considerations
- Risk assessment in the given context
- Implementation roadmap
- Evidence strategy
- Metrics and success criteria

Return a JSON object with the extracted information.""",
        fields=[
            FieldExtractionRule("control_id", "Control ID", required=True),
            FieldExtractionRule("control_name", "Control name", required=True),
            FieldExtractionRule("control_description", "Control description"),
            FieldExtractionRule("category", "Control category"),
            FieldExtractionRule("requirements", "List of requirements", data_type="list", default_value=[]),
            FieldExtractionRule("evidence_types", "Evidence types needed", data_type="list", default_value=[]),
            FieldExtractionRule("implementation_guidance", "Implementation guidance"),
        ],
        document_sections=[
            {"name": "Control Overview", "description": "What the control requires"},
            {"name": "Context-Specific Implementation", "description": "How to implement given the organization's situation"},
            {"name": "Risk Assessment", "description": "Risk in this specific context"},
            {"name": "Implementation Roadmap", "description": "Step-by-step plan"},
            {"name": "Evidence Strategy", "description": "What evidence is needed"},
            {"name": "Metrics", "description": "How to measure success"},
        ],
        human_prompt_template="""Extract control information from this {framework} regulatory text:

{text}

Context: {context_metadata}

Provide a complete control extraction with rich context document.""",
        human_prompt_variables=["text", "framework", "context_metadata"]
    )


def get_compliance_evidence_rules() -> ExtractionRules:
    """Get compliance-specific evidence extraction rules"""
    return ExtractionRules(
        extraction_type="evidence",
        domain="compliance",
        system_role="expert at creating evidence collection guides",
        system_instructions="""Create a detailed evidence document that explains:
1. What this evidence type is
2. How to collect it in this specific context
3. What systems/tools to use
4. Retention requirements
5. Quality criteria""",
        document_sections=[
            {"name": "Evidence Type Overview", "description": "What this evidence type is"},
            {"name": "Collection Methods", "description": "How to collect it in this specific context"},
            {"name": "Systems and Tools", "description": "What systems/tools to use"},
            {"name": "Retention Requirements", "description": "Retention requirements"},
            {"name": "Quality Criteria", "description": "Quality criteria"},
        ],
        human_prompt_template="""Evidence: {evidence_name}
Requirement: {requirement_id}
Context: {context_metadata}

Create a comprehensive evidence collection guide for this context.""",
        human_prompt_variables=["evidence_name", "requirement_id", "context_metadata"],
        use_json_parser=False  # Evidence extractor returns text, not JSON
    )


def get_compliance_requirement_rules() -> ExtractionRules:
    """Get compliance-specific requirement extraction rules"""
    return ExtractionRules(
        extraction_type="requirement",
        domain="compliance",
        system_role="expert at creating detailed contextual requirement documents",
        system_instructions="""Create a detailed contextual requirement document that explains:
1. What the requirement means in this specific context
2. Why it's important for this organization
3. How to implement it given the context
4. What evidence is needed
5. Risk if not implemented properly""",
        document_sections=[
            {"name": "Requirement Meaning", "description": "What the requirement means in this specific context"},
            {"name": "Importance", "description": "Why it's important for this organization"},
            {"name": "Implementation", "description": "How to implement it given the context"},
            {"name": "Evidence Needs", "description": "What evidence is needed"},
            {"name": "Risk Assessment", "description": "Risk if not implemented properly"},
        ],
        human_prompt_template="""Requirement: {requirement_text}
Control: {control_id}
Context: {context_metadata}

Create a comprehensive requirement document for this context.""",
        human_prompt_variables=["requirement_text", "control_id", "context_metadata"],
        use_json_parser=False  # Requirement extractor returns text, not JSON
    )


def get_default_fields_rules() -> ExtractionRules:
    """Get default rules for field extraction"""
    return ExtractionRules(
        extraction_type="fields",
        domain="generic",
        system_role="expert at extracting structured fields from text",
        system_instructions="""Extract all relevant fields from the text based on the field definitions provided.
For each field found:
1. Extract the field name and value
2. Identify the source entity (if applicable)
3. Determine the relationship/edge type
4. Create contextual edge information

Return a JSON object with:
- extracted_fields: List of objects with field_name, field_value, source_entity_id, source_entity_type
- edges: List of objects with source_entity_id, target_entity_id, edge_type, relationship_description""",
        fields=[
            FieldExtractionRule("extracted_fields", "List of extracted fields with metadata", data_type="list"),
            FieldExtractionRule("edges", "List of contextual edges to create", data_type="list"),
        ],
        human_prompt_template="""Extract fields from this text:

{text}

Context: {context_metadata}

Field definitions to extract:
{field_definitions}

Provide structured field extraction with edge relationships.""",
        human_prompt_variables=["text", "context_metadata", "field_definitions"],
        use_json_parser=True
    )


def get_default_entities_rules() -> ExtractionRules:
    """Get default rules for entity extraction"""
    return ExtractionRules(
        extraction_type="entities",
        domain="generic",
        system_role="expert at extracting entities and their relationships from text",
        system_instructions="""Extract entities and their relationships from the text.
For each entity found:
1. Identify the entity type and ID
2. Extract entity properties/attributes
3. Identify relationships to other entities
4. Determine edge types and context

Return a JSON object with:
- entities: List of objects with entity_id, entity_type, entity_name, properties
- relationships: List of objects with source_entity_id, target_entity_id, edge_type, relationship_description, context_id""",
        fields=[
            FieldExtractionRule("entities", "List of extracted entities", data_type="list"),
            FieldExtractionRule("relationships", "List of entity relationships/edges", data_type="list"),
        ],
        human_prompt_template="""Extract entities and relationships from this text:

{text}

Context: {context_metadata}

Entity types to identify:
{entity_types}

Provide structured entity extraction with relationship edges.""",
        human_prompt_variables=["text", "context_metadata", "entity_types"],
        use_json_parser=True
    )


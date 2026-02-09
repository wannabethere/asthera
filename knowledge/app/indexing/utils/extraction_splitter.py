"""
Utility to split documents with combined extraction results into separate documents.

This utility takes documents that contain multiple extraction types (control, entities, 
fields, evidence, requirements, context) and splits them into separate documents,
one for each extraction type. Also converts JSON content to markdown format for better
searchability and prompt efficiency.
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional, Union
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class ExtractionSplitter:
    """
    Splits documents containing multiple extraction types into separate documents.
    
    Each extraction type (control, entities, fields, evidence, requirements, context)
    becomes its own document with appropriate metadata. Converts JSON content to
    markdown format for better searchability.
    """
    
    # Patterns to identify extraction sections in text
    EXTRACTION_PATTERNS = {
        "entities": re.compile(r"Extracted Entities:\s*(\[.*?\])", re.DOTALL),
        "fields": re.compile(r"Extracted Fields:\s*(\[.*?\])", re.DOTALL),
        "evidence": re.compile(r"Extracted Evidence:\s*(\[.*?\])", re.DOTALL),
        "requirements": re.compile(r"Extracted Requirements:\s*(\[.*?\])", re.DOTALL),
        "context": re.compile(r"Extracted Context:\s*(\{.*?\})", re.DOTALL),
    }
    
    def json_to_markdown(self, data: Union[Dict, List], extraction_type: str = "base") -> str:
        """
        Convert JSON data to markdown format for better searchability.
        
        Args:
            data: JSON data (dict or list)
            extraction_type: Type of extraction (control, entities, fields, etc.)
            
        Returns:
            Markdown formatted string
        """
        if not data:
            return f"# {extraction_type.title()}\nNo data available."
        
        if extraction_type == "control":
            if isinstance(data, dict):
                return self._control_to_markdown(data)
            else:
                return f"# Control\n{json.dumps(data, indent=2)}"
        elif extraction_type == "entities":
            if isinstance(data, list):
                return self._entities_to_markdown(data)
            else:
                return f"# Entities\n{json.dumps(data, indent=2)}"
        elif extraction_type == "fields":
            if isinstance(data, list):
                return self._fields_to_markdown(data)
            else:
                return f"# Fields\n{json.dumps(data, indent=2)}"
        elif extraction_type == "evidence":
            if isinstance(data, list):
                return self._evidence_to_markdown(data)
            else:
                return f"# Evidence\n{json.dumps(data, indent=2)}"
        elif extraction_type == "requirements":
            if isinstance(data, list):
                return self._requirements_to_markdown(data)
            else:
                return f"# Requirements\n{json.dumps(data, indent=2)}"
        elif extraction_type == "context":
            if isinstance(data, dict):
                return self._context_to_markdown(data)
            else:
                return f"# Context\n{json.dumps(data, indent=2)}"
        else:
            if isinstance(data, dict):
                return self._base_to_markdown(data)
            else:
                return f"# Data\n{json.dumps(data, indent=2)}"
    
    def _control_to_markdown(self, control: Dict[str, Any]) -> str:
        """Convert control extraction to markdown."""
        lines = ["# Control Information\n"]
        
        # Main control fields
        if control.get("Control ID") or control.get("control_id"):
            lines.append(f"## Control ID: {control.get('Control ID') or control.get('control_id')}\n")
        
        if control.get("Control name") or control.get("control_name"):
            lines.append(f"## Control Name: {control.get('Control name') or control.get('control_name')}\n")
        
        if control.get("Control description") or control.get("control_description"):
            desc = control.get("Control description") or control.get("control_description")
            lines.append(f"## Description\n{desc}\n")
        
        if control.get("Category") or control.get("category"):
            lines.append(f"## Category: {control.get('Category') or control.get('category')}\n")
        
        # Requirements
        requirements = control.get("Requirements") or control.get("requirements", [])
        if requirements:
            lines.append("## Requirements\n")
            for i, req in enumerate(requirements, 1):
                lines.append(f"{i}. {req}")
            lines.append("")
        
        # Evidence types
        evidence_types = control.get("Evidence types needed") or control.get("evidence_types", [])
        if evidence_types:
            lines.append("## Evidence Types Needed\n")
            for evidence in evidence_types:
                lines.append(f"- {evidence}")
            lines.append("")
        
        # Implementation guidance
        guidance = control.get("Implementation guidance") or control.get("implementation_guidance", {})
        if guidance:
            lines.append("## Implementation Guidance\n")
            
            if isinstance(guidance, dict):
                for key, value in guidance.items():
                    # Format key as header
                    key_formatted = key.replace("_", " ").title()
                    lines.append(f"### {key_formatted}\n")
                    
                    if isinstance(value, list):
                        for item in value:
                            lines.append(f"- {item}")
                    elif isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            lines.append(f"**{sub_key}**: {sub_value}")
                    else:
                        lines.append(str(value))
                    lines.append("")
            else:
                lines.append(str(guidance))
                lines.append("")
        
        return "\n".join(lines)
    
    def _entities_to_markdown(self, entities: List[Dict[str, Any]]) -> str:
        """Convert entities extraction to markdown."""
        lines = ["# Extracted Entities\n"]
        
        for i, entity in enumerate(entities, 1):
            lines.append(f"## Entity {i}\n")
            
            if entity.get("entity_id"):
                lines.append(f"**Entity ID**: {entity['entity_id']}\n")
            
            if entity.get("entity_type"):
                lines.append(f"**Entity Type**: {entity['entity_type']}\n")
            
            if entity.get("entity_name"):
                lines.append(f"**Entity Name**: {entity['entity_name']}\n")
            
            # Properties
            properties = entity.get("properties", {})
            if properties:
                lines.append("**Properties**:\n")
                for key, value in properties.items():
                    if isinstance(value, (list, dict)):
                        value_str = json.dumps(value, indent=2)
                    else:
                        value_str = str(value)
                    lines.append(f"- {key}: {value_str}")
                lines.append("")
        
        return "\n".join(lines)
    
    def _fields_to_markdown(self, fields: List[Dict[str, Any]]) -> str:
        """Convert fields extraction to markdown."""
        lines = ["# Extracted Fields\n"]
        
        for field in fields:
            field_name = field.get("field_name", "Unknown")
            field_value = field.get("field_value", "")
            source_entity_id = field.get("source_entity_id", "")
            source_entity_type = field.get("source_entity_type", "")
            
            lines.append(f"## {field_name}\n")
            lines.append(f"**Value**: {field_value}\n")
            
            if source_entity_id:
                lines.append(f"**Source Entity ID**: {source_entity_id}\n")
            
            if source_entity_type:
                lines.append(f"**Source Entity Type**: {source_entity_type}\n")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _evidence_to_markdown(self, evidence: List[Dict[str, Any]]) -> str:
        """Convert evidence extraction to markdown."""
        lines = ["# Extracted Evidence\n"]
        
        for i, ev in enumerate(evidence, 1):
            lines.append(f"## Evidence {i}\n")
            
            for key, value in ev.items():
                if isinstance(value, (list, dict)):
                    value_str = json.dumps(value, indent=2)
                else:
                    value_str = str(value)
                lines.append(f"**{key.replace('_', ' ').title()}**: {value_str}\n")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _requirements_to_markdown(self, requirements: List[Dict[str, Any]]) -> str:
        """Convert requirements extraction to markdown."""
        lines = ["# Extracted Requirements\n"]
        
        for i, req in enumerate(requirements, 1):
            lines.append(f"## Requirement {i}\n")
            
            for key, value in req.items():
                if isinstance(value, (list, dict)):
                    value_str = json.dumps(value, indent=2)
                else:
                    value_str = str(value)
                lines.append(f"**{key.replace('_', ' ').title()}**: {value_str}\n")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _context_to_markdown(self, context: Dict[str, Any]) -> str:
        """Convert context extraction to markdown."""
        lines = ["# Extracted Context\n"]
        
        for key, value in context.items():
            key_formatted = key.replace("_", " ").title()
            
            if isinstance(value, list):
                lines.append(f"## {key_formatted}\n")
                for item in value:
                    lines.append(f"- {item}")
                lines.append("")
            elif isinstance(value, dict):
                lines.append(f"## {key_formatted}\n")
                for sub_key, sub_value in value.items():
                    lines.append(f"**{sub_key.replace('_', ' ').title()}**: {sub_value}\n")
                lines.append("")
            else:
                lines.append(f"**{key_formatted}**: {value}\n")
        
        return "\n".join(lines)
    
    def _base_to_markdown(self, data: Dict[str, Any]) -> str:
        """Convert base row data to markdown."""
        lines = ["# Row Data\n"]
        
        if data.get("sheet_name"):
            lines.append(f"**Sheet**: {data['sheet_name']}\n")
        
        if data.get("row_index") is not None:
            lines.append(f"**Row Index**: {data['row_index']}\n")
        
        if data.get("framework"):
            lines.append(f"**Framework**: {data['framework']}\n")
        
        # Data fields
        row_data = data.get("data", {})
        if row_data:
            lines.append("## Data\n")
            for key, value in row_data.items():
                if value:  # Only include non-empty values
                    lines.append(f"**{key}**: {value}\n")
        
        # Columns info
        columns = data.get("columns", [])
        if columns:
            lines.append(f"\n**Columns**: {', '.join(columns)}\n")
        
        return "\n".join(lines)
    
    def split_document(self, doc: Document) -> List[Document]:
        """
        Split a document containing multiple extraction types into separate documents.
        
        Args:
            doc: Document with combined extraction results
            
        Returns:
            List of documents, one for each extraction type found
        """
        documents = []
        
        try:
            # Parse the base content (JSON)
            base_content = self._parse_base_content(doc.page_content)
            
            # Extract control if present
            if base_content and "extracted_control" in base_content:
                control_doc = self._create_control_document(
                    base_content["extracted_control"],
                    doc.metadata,
                    base_content
                )
                documents.append(control_doc)
            
            # Extract entities from text
            entities = self._extract_from_text(doc.page_content, "entities")
            if entities:
                entities_doc = self._create_entities_document(
                    entities,
                    doc.metadata,
                    base_content
                )
                documents.append(entities_doc)
            
            # Extract fields from text
            fields = self._extract_from_text(doc.page_content, "fields")
            if fields:
                fields_doc = self._create_fields_document(
                    fields,
                    doc.metadata,
                    base_content
                )
                documents.append(fields_doc)
            
            # Extract evidence from text
            evidence = self._extract_from_text(doc.page_content, "evidence")
            if evidence:
                evidence_doc = self._create_evidence_document(
                    evidence,
                    doc.metadata,
                    base_content
                )
                documents.append(evidence_doc)
            
            # Extract requirements from text
            requirements = self._extract_from_text(doc.page_content, "requirements")
            if requirements:
                requirements_doc = self._create_requirements_document(
                    requirements,
                    doc.metadata,
                    base_content
                )
                documents.append(requirements_doc)
            
            # Extract context from text
            context = self._extract_from_text(doc.page_content, "context")
            if context:
                context_doc = self._create_context_document(
                    context,
                    doc.metadata,
                    base_content
                )
                documents.append(context_doc)
            
            # Create base document (without extractions)
            base_doc = self._create_base_document(
                base_content,
                doc.metadata
            )
            documents.append(base_doc)
            
            logger.debug(f"Split document into {len(documents)} separate documents")
            return documents
            
        except Exception as e:
            logger.error(f"Error splitting document: {e}", exc_info=True)
            # Return original document if splitting fails
            return [doc]
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Split multiple documents containing extraction results.
        
        Args:
            documents: List of documents with combined extraction results
            
        Returns:
            List of all split documents
        """
        all_split_docs = []
        
        for doc in documents:
            split_docs = self.split_document(doc)
            all_split_docs.extend(split_docs)
        
        logger.info(f"Split {len(documents)} documents into {len(all_split_docs)} separate documents")
        return all_split_docs
    
    def _parse_base_content(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse the base JSON content from document."""
        try:
            # Try to parse the entire content as JSON first
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
            
            # If that fails, try to find JSON content before extraction sections
            # Look for the first JSON object
            json_match = re.search(r'^(\{.*?)\n\nExtracted', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                # Find balanced braces
                brace_count = 0
                start_idx = json_str.find('{')
                if start_idx != -1:
                    for i in range(start_idx, len(json_str)):
                        if json_str[i] == '{':
                            brace_count += 1
                        elif json_str[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_str = json_str[start_idx:i+1]
                                return json.loads(json_str)
            
            # Try to find any JSON object at the start
            json_match = re.search(r'^(\{.*?\})', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                # Find balanced braces
                brace_count = 0
                start_idx = 0
                for i in range(len(json_str)):
                    if json_str[i] == '{':
                        brace_count += 1
                    elif json_str[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = json_str[start_idx:i+1]
                            return json.loads(json_str)
        except Exception as e:
            logger.debug(f"Error parsing base content: {e}")
        
        return None
    
    def _extract_from_text(self, content: str, extraction_type: str) -> Optional[List[Dict[str, Any]]]:
        """Extract extraction data from text using regex patterns."""
        pattern = self.EXTRACTION_PATTERNS.get(extraction_type)
        if not pattern:
            return None
        
        match = pattern.search(content)
        if match:
            try:
                extracted_json = match.group(1)
                return json.loads(extracted_json)
            except json.JSONDecodeError as e:
                logger.warning(f"Error parsing {extraction_type} JSON: {e}")
        
        return None
    
    def _create_base_document(
        self,
        base_content: Optional[Dict[str, Any]],
        original_metadata: Dict[str, Any]
    ) -> Document:
        """Create base document without extraction results."""
        # Remove extracted_control from base content
        if base_content and "extracted_control" in base_content:
            base_content = base_content.copy()
            base_content.pop("extracted_control", None)
        
        # Convert to markdown
        content = self.json_to_markdown(base_content, "base") if base_content else "# Row Data\nNo data available."
        
        metadata = original_metadata.copy()
        metadata["extraction_type"] = "base"
        metadata["entity_type"] = metadata.get("entity_type", "row")
        
        return Document(
            page_content=content,
            metadata=metadata
        )
    
    def _create_control_document(
        self,
        control_data: Dict[str, Any],
        original_metadata: Dict[str, Any],
        base_content: Optional[Dict[str, Any]]
    ) -> Document:
        """Create document for extracted control."""
        # Convert to markdown
        content = self.json_to_markdown(control_data, "control")
        
        metadata = original_metadata.copy()
        metadata["extraction_type"] = "control"
        metadata["entity_type"] = "control"
        metadata["control_id"] = control_data.get("Control ID") or control_data.get("control_id")
        metadata["control_name"] = control_data.get("Control name") or control_data.get("control_name")
        
        # Add reference to source
        if base_content:
            metadata["source_sheet"] = base_content.get("sheet_name")
            metadata["source_row_index"] = base_content.get("row_index")
        
        return Document(
            page_content=content,
            metadata=metadata
        )
    
    def _create_entities_document(
        self,
        entities: List[Dict[str, Any]],
        original_metadata: Dict[str, Any],
        base_content: Optional[Dict[str, Any]]
    ) -> Document:
        """Create document for extracted entities."""
        # Convert to markdown
        content = self.json_to_markdown(entities, "entities")
        
        metadata = original_metadata.copy()
        metadata["extraction_type"] = "entities"
        metadata["entity_type"] = "entities"
        metadata["entity_count"] = len(entities)
        
        # Add reference to source
        if base_content:
            metadata["source_sheet"] = base_content.get("sheet_name")
            metadata["source_row_index"] = base_content.get("row_index")
        
        return Document(
            page_content=content,
            metadata=metadata
        )
    
    def _create_fields_document(
        self,
        fields: List[Dict[str, Any]],
        original_metadata: Dict[str, Any],
        base_content: Optional[Dict[str, Any]]
    ) -> Document:
        """Create document for extracted fields."""
        # Convert to markdown
        content = self.json_to_markdown(fields, "fields")
        
        metadata = original_metadata.copy()
        metadata["extraction_type"] = "fields"
        metadata["entity_type"] = "fields"
        metadata["field_count"] = len(fields)
        
        # Add reference to source
        if base_content:
            metadata["source_sheet"] = base_content.get("sheet_name")
            metadata["source_row_index"] = base_content.get("row_index")
        
        return Document(
            page_content=content,
            metadata=metadata
        )
    
    def _create_evidence_document(
        self,
        evidence: List[Dict[str, Any]],
        original_metadata: Dict[str, Any],
        base_content: Optional[Dict[str, Any]]
    ) -> Document:
        """Create document for extracted evidence."""
        # Convert to markdown
        content = self.json_to_markdown(evidence, "evidence")
        
        metadata = original_metadata.copy()
        metadata["extraction_type"] = "evidence"
        metadata["entity_type"] = "evidence"
        metadata["evidence_count"] = len(evidence)
        
        # Add reference to source
        if base_content:
            metadata["source_sheet"] = base_content.get("sheet_name")
            metadata["source_row_index"] = base_content.get("row_index")
        
        return Document(
            page_content=content,
            metadata=metadata
        )
    
    def _create_requirements_document(
        self,
        requirements: List[Dict[str, Any]],
        original_metadata: Dict[str, Any],
        base_content: Optional[Dict[str, Any]]
    ) -> Document:
        """Create document for extracted requirements."""
        # Convert to markdown
        content = self.json_to_markdown(requirements, "requirements")
        
        metadata = original_metadata.copy()
        metadata["extraction_type"] = "requirements"
        metadata["entity_type"] = "requirements"
        metadata["requirement_count"] = len(requirements)
        
        # Add reference to source
        if base_content:
            metadata["source_sheet"] = base_content.get("sheet_name")
            metadata["source_row_index"] = base_content.get("row_index")
        
        return Document(
            page_content=content,
            metadata=metadata
        )
    
    def _create_context_document(
        self,
        context: Dict[str, Any],
        original_metadata: Dict[str, Any],
        base_content: Optional[Dict[str, Any]]
    ) -> Document:
        """Create document for extracted context."""
        # Convert to markdown
        content = self.json_to_markdown(context, "context")
        
        metadata = original_metadata.copy()
        metadata["extraction_type"] = "context"
        metadata["entity_type"] = "context"
        
        # Add reference to source
        if base_content:
            metadata["source_sheet"] = base_content.get("sheet_name")
            metadata["source_row_index"] = base_content.get("row_index")
        
        return Document(
            page_content=content,
            metadata=metadata
        )


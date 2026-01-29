"""
Configurable LLM extractor for extracting fields from text and creating contextual edges.

This extractor extracts structured fields from text based on configurable rules
and creates contextual edges based on the fields and relationships found.
"""
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json
from uuid import uuid4

from app.agents.extractors.extraction_rules import ExtractionRules, get_default_fields_rules

if TYPE_CHECKING:
    from app.services.contextual_graph_storage import ContextualEdge

logger = logging.getLogger(__name__)


class FieldsExtractor:
    """
    Extract fields from text and create contextual edges based on extracted fields.
    
    Uses ExtractionRules to define what fields to extract and how to create edges.
    """
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o",
        rules: Optional[ExtractionRules] = None
    ):
        """
        Initialize with LLM and extraction rules.
        
        Args:
            llm: Optional LLM instance
            model_name: Model name if llm not provided
            rules: ExtractionRules configuration. If None, uses default rules.
        """
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.rules = rules or get_default_fields_rules()
        self.json_parser = JsonOutputParser() if self.rules.use_json_parser else None
    
    async def extract_fields_and_create_edges(
        self,
        text: str,
        context_id: str,
        source_entity_id: Optional[str] = None,
        source_entity_type: Optional[str] = None,
        field_definitions: Optional[List[Dict[str, Any]]] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract fields from text and create contextual edges.
        
        Args:
            text: Text to extract fields from
            context_id: Context ID for creating edges
            source_entity_id: Optional source entity ID (if fields belong to an entity)
            source_entity_type: Optional source entity type
            field_definitions: Optional list of field definitions to extract
            context_metadata: Optional context metadata
            **kwargs: Additional variables for prompt template
            
        Returns:
            Dictionary with:
            - extracted_fields: List of extracted fields
            - edges: List of ContextualEdge objects created
        """
        # Build system prompt from rules
        system_prompt = f"You are an {self.rules.system_role}.\n\n{self.rules.system_instructions}"
        
        # If using JSON parser, explicitly instruct to return strict JSON only (using markdown format)
        if self.rules.use_json_parser:
            system_prompt += "\n\n**Output Format:** Return ONLY valid JSON (no markdown, no code blocks, no explanations). Start with opening brace and end with closing brace."
        
        # Format field definitions for prompt
        field_defs_text = ""
        if field_definitions:
            field_defs_text = "\n".join([
                f"- {fd.get('name', 'unknown')}: {fd.get('description', '')} (type: {fd.get('data_type', 'string')})"
                for fd in field_definitions
            ])
        else:
            # Use rules fields if no field definitions provided
            field_defs_text = "\n".join([
                f"- {f.name}: {f.description} (type: {f.data_type})"
                for f in self.rules.fields
            ])
        
        # Build prompt variables
        # Convert context_metadata to JSON string, but escape curly braces for LangChain template
        context_metadata_str = json.dumps(context_metadata or {}, indent=2) if context_metadata else "{}"
        # Escape curly braces in JSON string to prevent LangChain from treating them as template variables
        context_metadata_str = context_metadata_str.replace("{", "{{").replace("}", "}}")
        
        prompt_vars = {
            "text": text,
            "context_metadata": context_metadata_str,
            "field_definitions": field_defs_text
        }
        prompt_vars.update(kwargs)
        
        # Build human prompt template - add compact JSON format instruction if needed
        human_prompt_template = self.rules.human_prompt_template
        if self.rules.use_json_parser:
            human_prompt_template += "\n\n**Return ONLY valid JSON** (no markdown, no code blocks)."
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", human_prompt_template)
        ])
        
        # Build chain
        if self.rules.use_json_parser and self.json_parser:
            chain = prompt | self.llm | self.json_parser
        else:
            chain = prompt | self.llm
        
        try:
            result = await chain.ainvoke(prompt_vars)
            
            # If not using JSON parser, result is a message object
            if not self.rules.use_json_parser:
                result_text = result.content if hasattr(result, 'content') else str(result)
                logger.warning("Fields extractor requires JSON parser for structured output")
                return {
                    "extracted_fields": [],
                    "edges": [],
                    "raw_result": result_text
                }
            
            # Extract fields and create edges
            extracted_fields = result.get("extracted_fields", [])
            edge_data = result.get("edges", [])
            
            from app.services.contextual_graph_storage import ContextualEdge
            edges = []
            for edge_info in edge_data:
                try:
                    edge_id = edge_info.get("edge_id") or f"edge_{uuid4().hex[:12]}"
                    edge_doc = edge_info.get("relationship_description") or edge_info.get("document") or ""
                    
                    # Create edge document if not provided
                    if not edge_doc:
                        edge_doc = self._create_edge_document(edge_info, extracted_fields)
                    
                    edge = ContextualEdge(
                        edge_id=edge_id,
                        document=edge_doc,
                        source_entity_id=edge_info.get("source_entity_id") or source_entity_id or "unknown",
                        source_entity_type=edge_info.get("source_entity_type") or source_entity_type or "entity",
                        target_entity_id=edge_info.get("target_entity_id") or "unknown",
                        target_entity_type=edge_info.get("target_entity_type") or "field",
                        edge_type=edge_info.get("edge_type") or "HAS_FIELD_IN_CONTEXT",
                        context_id=context_id,
                        relevance_score=edge_info.get("relevance_score", 0.0)
                    )
                    edges.append(edge)
                except Exception as e:
                    logger.error(f"Error creating edge from {edge_info}: {str(e)}", exc_info=True)
            
            return {
                "extracted_fields": extracted_fields,
                "edges": edges,
                "raw_result": result
            }
            
        except Exception as e:
            logger.error(f"Error extracting fields: {str(e)}", exc_info=True)
            return {
                "extracted_fields": [],
                "edges": [],
                "error": str(e)
            }
    
    def _create_edge_document(
        self,
        edge_info: Dict[str, Any],
        extracted_fields: List[Dict[str, Any]]
    ) -> str:
        """Create a document description for an edge"""
        source_id = edge_info.get("source_entity_id", "unknown")
        target_id = edge_info.get("target_entity_id", "unknown")
        edge_type = edge_info.get("edge_type", "HAS_FIELD_IN_CONTEXT")
        
        # Find related fields
        related_fields = [
            f for f in extracted_fields
            if f.get("source_entity_id") == source_id or f.get("field_name") == target_id
        ]
        
        doc_parts = [
            f"Edge Type: {edge_type}",
            f"Source Entity: {source_id}",
            f"Target Entity: {target_id}",
        ]
        
        if related_fields:
            doc_parts.append("\nRelated Fields:")
            for field in related_fields:
                doc_parts.append(f"- {field.get('field_name')}: {field.get('field_value')}")
        
        return "\n".join(doc_parts)


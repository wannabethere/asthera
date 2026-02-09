"""
Configurable LLM extractor for extracting entities and their relationships from text.

This extractor extracts entities and creates contextual edges based on the relationships
found between entities in the text.
"""
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json
from uuid import uuid4

from app.agents.extractors.extraction_rules import ExtractionRules, get_default_entities_rules

if TYPE_CHECKING:
    from app.services.contextual_graph_storage import ContextualEdge

logger = logging.getLogger(__name__)


class EntitiesExtractor:
    """
    Extract entities and their relationships from text and create contextual edges.
    
    Uses ExtractionRules to define what entities to extract and how to create edges.
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
        self.rules = rules or get_default_entities_rules()
        self.json_parser = JsonOutputParser() if self.rules.use_json_parser else None
    
    async def extract_entities_and_create_edges(
        self,
        text: str,
        context_id: str,
        entity_types: Optional[List[str]] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract entities and their relationships from text and create contextual edges.
        
        Args:
            text: Text to extract entities from
            context_id: Context ID for creating edges
            entity_types: Optional list of entity types to identify
            context_metadata: Optional context metadata
            **kwargs: Additional variables for prompt template
            
        Returns:
            Dictionary with:
            - entities: List of extracted entities
            - edges: List of ContextualEdge objects created
        """
        # Build system prompt from rules
        system_prompt = f"You are an {self.rules.system_role}.\n\n{self.rules.system_instructions}"
        
        # If using JSON parser, explicitly instruct to return strict JSON only (using markdown format)
        if self.rules.use_json_parser:
            system_prompt += "\n\n**Output Format:** Return ONLY valid JSON (no markdown, no code blocks, no explanations). Start with opening brace and end with closing brace."
        
        # Format entity types for prompt
        entity_types_text = ""
        if entity_types:
            entity_types_text = "\n".join([f"- {et}" for et in entity_types])
        else:
            entity_types_text = "Any relevant entities (controls, requirements, evidence, systems, etc.)"
        
        # Build prompt variables
        # Convert context_metadata to JSON string, but escape curly braces for LangChain template
        context_metadata_str = json.dumps(context_metadata or {}, indent=2) if context_metadata else "{}"
        # Escape curly braces in JSON string to prevent LangChain from treating them as template variables
        context_metadata_str = context_metadata_str.replace("{", "{{").replace("}", "}}")
        
        prompt_vars = {
            "text": text,
            "context_metadata": context_metadata_str,
            "entity_types": entity_types_text
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
                logger.warning("Entities extractor requires JSON parser for structured output")
                return {
                    "entities": [],
                    "edges": [],
                    "raw_result": result_text
                }
            
            # Extract entities and relationships
            entities = result.get("entities", [])
            relationships = result.get("relationships", [])
            
            from app.services.contextual_graph_storage import ContextualEdge
            edges = []
            for rel_info in relationships:
                try:
                    edge_id = rel_info.get("edge_id") or f"edge_{uuid4().hex[:12]}"
                    edge_doc = rel_info.get("relationship_description") or rel_info.get("document") or ""
                    
                    # Create edge document if not provided
                    if not edge_doc:
                        edge_doc = self._create_edge_document(rel_info, entities)
                    
                    edge = ContextualEdge(
                        edge_id=edge_id,
                        document=edge_doc,
                        source_entity_id=rel_info.get("source_entity_id") or "unknown",
                        source_entity_type=rel_info.get("source_entity_type") or "entity",
                        target_entity_id=rel_info.get("target_entity_id") or "unknown",
                        target_entity_type=rel_info.get("target_entity_type") or "entity",
                        edge_type=rel_info.get("edge_type") or "RELATED_TO_IN_CONTEXT",
                        context_id=rel_info.get("context_id") or context_id,
                        relevance_score=rel_info.get("relevance_score", 0.0),
                        priority_in_context=rel_info.get("priority_in_context"),
                        risk_score_in_context=rel_info.get("risk_score_in_context")
                    )
                    edges.append(edge)
                except Exception as e:
                    logger.error(f"Error creating edge from {rel_info}: {str(e)}", exc_info=True)
            
            return {
                "entities": entities,
                "edges": edges,
                "raw_result": result
            }
            
        except Exception as e:
            logger.error(f"Error extracting entities: {str(e)}", exc_info=True)
            return {
                "entities": [],
                "edges": [],
                "error": str(e)
            }
    
    def _create_edge_document(
        self,
        rel_info: Dict[str, Any],
        entities: List[Dict[str, Any]]
    ) -> str:
        """Create a document description for an edge based on relationship info"""
        source_id = rel_info.get("source_entity_id", "unknown")
        target_id = rel_info.get("target_entity_id", "unknown")
        edge_type = rel_info.get("edge_type", "RELATED_TO_IN_CONTEXT")
        
        # Find source and target entities
        source_entity = next(
            (e for e in entities if e.get("entity_id") == source_id),
            None
        )
        target_entity = next(
            (e for e in entities if e.get("entity_id") == target_id),
            None
        )
        
        doc_parts = [
            f"Relationship Type: {edge_type}",
            f"Source Entity: {source_entity.get('entity_name', source_id) if source_entity else source_id} ({source_entity.get('entity_type', 'entity') if source_entity else 'unknown'})",
            f"Target Entity: {target_entity.get('entity_name', target_id) if target_entity else target_id} ({target_entity.get('entity_type', 'entity') if target_entity else 'unknown'})",
        ]
        
        if source_entity and source_entity.get("properties"):
            doc_parts.append("\nSource Entity Properties:")
            for key, value in source_entity["properties"].items():
                doc_parts.append(f"- {key}: {value}")
        
        if target_entity and target_entity.get("properties"):
            doc_parts.append("\nTarget Entity Properties:")
            for key, value in target_entity["properties"].items():
                doc_parts.append(f"- {key}: {value}")
        
        return "\n".join(doc_parts)


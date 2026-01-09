"""
Integration Test for Document Ingestion and Storage

This test demonstrates:
1. Extracting controls from HIPAA/SOC2 PDF content (as text)
2. Extracting context from organizational descriptions
3. Storing API definitions as knowledge context
4. Storing metrics registry with SOC2 compliance mapping
5. Processing business process wiki content
6. Extracting fields from documents using FieldsExtractor and creating contextual edges
7. Extracting entities and relationships using EntitiesExtractor and creating contextual edges
8. Storing everything in PostgreSQL and ChromaDB
9. Querying and displaying results

Prerequisites:
- PostgreSQL database with tables created (see migrations/)
- ChromaDB will be created locally in ./test_chroma_db
- OPENAI_API_KEY environment variable must be set
"""
import asyncio
import logging
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import asyncpg
import chromadb
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.settings import get_settings, clear_settings_cache, set_os_environ
from app.core.dependencies import (
    get_chromadb_client,
    get_database_pool,
    get_embeddings_model,
    get_llm,
    clear_all_caches
)
from app.services.extraction_service import ExtractionService
from app.services.contextual_graph_service import ContextualGraphService
from app.services.models import (
    ContextSearchRequest,
    ContextSaveRequest,
    ControlSaveRequest,
    ControlSearchRequest,
    PriorityControlsRequest
)
from app.agents.extractors import (
    FieldsExtractor, 
    EntitiesExtractor,
    ExtractionRules,
    FieldExtractionRule
)
from tests.test_data import (
    HIPAA_CONTROL_TEXT,
    SOC2_CONTROL_TEXT,
    API_DEFINITION_DOC,
    METRICS_REGISTRY_DOC,
    BUSINESS_PROCESS_WIKI,
    HEALTHCARE_CONTEXT_DESCRIPTION,
    TECH_COMPANY_CONTEXT_DESCRIPTION
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegrationTest:
    """Integration test for document ingestion"""
    
    def __init__(self):
        # Load settings from app.core.settings (includes PostgreSQL config and OpenAI API key)
        self.settings = get_settings()
        
        # Initialize to None - will be set in setup()
        self.db_pool: asyncpg.Pool = None
        self.chroma_client: chromadb.PersistentClient = None
        self.embeddings: OpenAIEmbeddings = None
        self.llm: ChatOpenAI = None
        self.extraction_service: ExtractionService = None
        self.contextual_graph_service: ContextualGraphService = None
        self.fields_extractor: FieldsExtractor = None
        self.entities_extractor: EntitiesExtractor = None
        
        # Test data storage
        self.contexts: Dict[str, str] = {}  # context_id -> context_id
        self.controls: Dict[str, Dict[str, Any]] = {}  # control_id -> control data
        self.edges_created: int = 0  # Count of edges created
    
    async def setup(self):
        """Set up database and service connections"""
        logger.info("=" * 80)
        logger.info("Setting up integration test environment")
        logger.info("=" * 80)
        
        # Get settings and ensure environment variables are set
        # This will set OPENAI_API_KEY and other env vars from settings
        self.settings = get_settings()
        set_os_environ(self.settings)
        
        # Verify OpenAI API key is available
        openai_api_key = os.getenv("OPENAI_API_KEY") or self.settings.OPENAI_API_KEY
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in settings or environment")
        logger.info(f"Using OpenAI API key from settings: {bool(openai_api_key)}")
        
        # Set test-specific ChromaDB path via environment variable
        # This will be picked up by get_chromadb_client()
        test_chroma_path = "./test_chroma_db"
        os.environ["CHROMA_STORE_PATH"] = test_chroma_path
        os.environ["CHROMA_USE_LOCAL"] = "true"
        
        # Clear caches to ensure fresh settings
        clear_settings_cache()
        clear_all_caches()
        
        # Initialize PostgreSQL connection pool using dependencies
        # This uses POSTGRES_* settings from app.core.settings
        logger.info("Connecting to PostgreSQL...")
        logger.info(f"  Host: {self.settings.POSTGRES_HOST}")
        logger.info(f"  Port: {self.settings.POSTGRES_PORT}")
        logger.info(f"  Database: {self.settings.POSTGRES_DB}")
        self.db_pool = await get_database_pool()
        logger.info(f"✓ Connected to PostgreSQL: {self.settings.POSTGRES_DB}")
        
        # Initialize ChromaDB using dependencies
        logger.info(f"Initializing ChromaDB at: {test_chroma_path}")
        self.chroma_client = get_chromadb_client()
        logger.info("✓ ChromaDB initialized")
        
        # Initialize embeddings using dependencies
        # Uses EMBEDDING_MODEL and OPENAI_API_KEY from settings
        logger.info("Initializing OpenAI embeddings...")
        self.embeddings = get_embeddings_model(
            model=self.settings.EMBEDDING_MODEL,
            api_key=self.settings.OPENAI_API_KEY
        )
        logger.info(f"✓ Embeddings model: {self.settings.EMBEDDING_MODEL}")
        
        # Initialize LLM using dependencies from app.core.dependencies
        # Uses LLM_MODEL, LLM_TEMPERATURE, and OPENAI_API_KEY from settings
        logger.info("Initializing LLM...")
        self.llm = get_llm(
            temperature=self.settings.LLM_TEMPERATURE,
            model=self.settings.LLM_MODEL
        )
        logger.info(f"✓ LLM model: {self.settings.LLM_MODEL}, temperature: {self.settings.LLM_TEMPERATURE}")
        
        # Initialize Extraction Service with db_pool for doc insights
        logger.info("Initializing Extraction Service...")
        self.extraction_service = ExtractionService(
            llm=self.llm,
            model_name=self.settings.LLM_MODEL,
            db_pool=self.db_pool
        )
        await self.extraction_service.initialize()
        logger.info("✓ Extraction Service initialized")
        
        # Initialize Contextual Graph Service
        logger.info("Initializing Contextual Graph Service...")
        self.contextual_graph_service = ContextualGraphService(
            db_pool=self.db_pool,
            chroma_client=self.chroma_client,
            embeddings_model=self.embeddings,
            llm=self.llm
        )
        logger.info("✓ Contextual Graph Service initialized")
        
        # Initialize Fields and Entities Extractors
        logger.info("Initializing Fields and Entities Extractors...")
        self.fields_extractor = FieldsExtractor(
            llm=self.llm,
            model_name=self.settings.LLM_MODEL
        )
        self.entities_extractor = EntitiesExtractor(
            llm=self.llm,
            model_name=self.settings.LLM_MODEL
        )
        logger.info("✓ Fields and Entities Extractors initialized")
        
        logger.info("Setup complete!\n")
    
    async def save_doc_insight_for_fields_or_entities(
        self,
        doc_id: str,
        document_content: str,
        extraction_type: str,
        extracted_data: Dict[str, Any],
        context_id: Optional[str] = None,
        extraction_metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Helper method to save doc insights for fields/entities extractions
        (which are done via FieldsExtractor/EntitiesExtractor, not ExtractionService).
        
        This is a temporary helper until we integrate fields/entities into ExtractionService.
        """
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO document_kg_insights (
                        doc_id, document_content, extraction_type, extracted_data,
                        context_id, extraction_metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (doc_id) DO UPDATE SET
                        document_content = EXCLUDED.document_content,
                        extraction_type = EXCLUDED.extraction_type,
                        extracted_data = EXCLUDED.extracted_data,
                        context_id = EXCLUDED.context_id,
                        extraction_metadata = EXCLUDED.extraction_metadata,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    doc_id,
                    document_content,
                    extraction_type,
                    json.dumps(extracted_data),
                    context_id,
                    json.dumps(extraction_metadata) if extraction_metadata else None
                )
                logger.info(f"✓ Saved doc insight: {doc_id} (type: {extraction_type})")
        except Exception as e:
            logger.error(f"✗ Failed to save doc insight {doc_id}: {str(e)}", exc_info=True)
    
    async def test_1_extract_and_save_contexts(self):
        """Test 1: Extract and save organizational contexts
        
        Demonstrates:
        - Using custom rules for healthcare domain
        - Using custom rules for tech company domain
        - Using default compliance rules (backward compatible)
        """
        logger.info("=" * 80)
        logger.info("TEST 1: Extract and Save Organizational Contexts")
        logger.info("=" * 80)
        
        # Example 1: Healthcare context with custom rules
        logger.info("\n--- Example 1: Healthcare context with custom rules ---")
        healthcare_rules = ExtractionRules(
            extraction_type="context",
            domain="healthcare",
            system_role="expert at analyzing healthcare organizational contexts",
            system_instructions="""Extract structured information about healthcare organizations:
1. Healthcare setting (hospital, clinic, research facility, etc.)
2. Patient volume and demographics
3. Data types handled (PHI, ePHI, research data)
4. HIPAA compliance status and maturity
5. Systems in use (EHR, billing, research systems)
6. Regulatory frameworks applicable
7. Risk profile""",
            fields=[
                FieldExtractionRule("healthcare_setting", "Type of healthcare setting", 
                                  examples=["hospital", "clinic", "research", "pharmacy"]),
                FieldExtractionRule("patient_volume", "Monthly patient volume", data_type="int"),
                FieldExtractionRule("data_types", "Types of data handled", data_type="list",
                                  examples=["PHI", "ePHI", "research_data", "billing_data"]),
                FieldExtractionRule("hipaa_compliant", "HIPAA compliance status", data_type="bool"),
                FieldExtractionRule("systems_in_use", "Systems and applications", data_type="list"),
            ],
            human_prompt_template="Analyze this healthcare organization context: {description}",
            human_prompt_variables=["description"]
        )
        
        response = await self.extraction_service.extract_context(
            description=HEALTHCARE_CONTEXT_DESCRIPTION,
            context_id="healthcare_ctx",
            configuration={"rules": healthcare_rules}
        )
        
        if not response.success:
            logger.error(f"Failed to extract healthcare context: {response.error}")
        else:
            extracted_data = response.extracted_data
            logger.info(f"✓ Extracted healthcare context with custom rules")
            logger.info(f"  Healthcare setting: {extracted_data.get('healthcare_setting', 'N/A')}")
            logger.info(f"  Patient volume: {extracted_data.get('patient_volume', 'N/A')}")
            logger.info(f"  HIPAA compliant: {extracted_data.get('hipaa_compliant', 'N/A')}")
            
            # Save context to vector store
            save_request = ContextSaveRequest(
                context_id="healthcare_ctx",
                document=HEALTHCARE_CONTEXT_DESCRIPTION,
                context_type=extracted_data.get("context_type", "organizational_situational"),
                industry=extracted_data.get("industry"),
                organization_size=extracted_data.get("organization_size"),
                maturity_level=extracted_data.get("maturity_level"),
                regulatory_frameworks=extracted_data.get("regulatory_frameworks", [])
            )
            
            save_response = await self.contextual_graph_service.save_context(save_request)
            if save_response.success:
                logger.info(f"✓ Successfully saved context: healthcare_ctx")
                self.contexts["healthcare_ctx"] = "healthcare_ctx"
        
        # Example 2: Tech company context with custom rules
        logger.info("\n--- Example 2: Tech company context with custom rules ---")
        tech_rules = ExtractionRules(
            extraction_type="context",
            domain="technology",
            system_role="expert at analyzing technology company contexts",
            system_instructions="""Extract structured information about technology companies:
1. Company type (SaaS, infrastructure, fintech, etc.)
2. Scale metrics (users, revenue, employees)
3. Compliance frameworks (SOC2, ISO27001, GDPR, etc.)
4. Security maturity level
5. Data handling practices
6. Infrastructure and cloud usage""",
            fields=[
                FieldExtractionRule("company_type", "Type of technology company",
                                  examples=["SaaS", "infrastructure", "fintech", "healthtech"]),
                FieldExtractionRule("user_count", "Number of users/customers", data_type="int"),
                FieldExtractionRule("compliance_frameworks", "Compliance frameworks", data_type="list",
                                  examples=["SOC2", "ISO27001", "GDPR", "HIPAA"]),
                FieldExtractionRule("security_maturity", "Security maturity level",
                                  examples=["basic", "intermediate", "advanced", "enterprise"]),
                FieldExtractionRule("cloud_providers", "Cloud infrastructure providers", data_type="list"),
            ],
            human_prompt_template="Analyze this technology company context: {description}",
            human_prompt_variables=["description"]
        )
        
        response = await self.extraction_service.extract_context(
            description=TECH_COMPANY_CONTEXT_DESCRIPTION,
            context_id="tech_company_ctx",
            configuration={"rules": tech_rules}
        )
        
        if not response.success:
            logger.error(f"Failed to extract tech company context: {response.error}")
        else:
            extracted_data = response.extracted_data
            logger.info(f"✓ Extracted tech company context with custom rules")
            logger.info(f"  Company type: {extracted_data.get('company_type', 'N/A')}")
            logger.info(f"  Security maturity: {extracted_data.get('security_maturity', 'N/A')}")
            
            # Save context to vector store
            save_request = ContextSaveRequest(
                context_id="tech_company_ctx",
                document=TECH_COMPANY_CONTEXT_DESCRIPTION,
                context_type=extracted_data.get("context_type", "organizational_situational"),
                industry=extracted_data.get("industry"),
                organization_size=extracted_data.get("organization_size"),
                maturity_level=extracted_data.get("maturity_level"),
                regulatory_frameworks=extracted_data.get("regulatory_frameworks", [])
            )
            
            save_response = await self.contextual_graph_service.save_context(save_request)
            if save_response.success:
                logger.info(f"✓ Successfully saved context: tech_company_ctx")
                self.contexts["tech_company_ctx"] = "tech_company_ctx"
        
        # Example 3: Using default rules (backward compatible)
        logger.info("\n--- Example 3: Using default compliance rules (backward compatible) ---")
        contexts_to_process = [
            ("healthcare_ctx_default", HEALTHCARE_CONTEXT_DESCRIPTION),
            ("tech_company_ctx_default", TECH_COMPANY_CONTEXT_DESCRIPTION)
        ]
        
        for context_id, description in contexts_to_process:
            logger.info(f"\nProcessing context with default rules: {context_id}")
            
            # Extract context using extraction service with default rules
            response = await self.extraction_service.extract_context(
                description=description,
                context_id=context_id
            )
            
            if not response.success:
                logger.error(f"Failed to extract context {context_id}: {response.error}")
                continue
            
            extracted_data = response.extracted_data
            logger.info(f"Extracted context data: {extracted_data}")
            
            # Save context to vector store
            save_request = ContextSaveRequest(
                context_id=context_id,
                document=description,
                context_type=extracted_data.get("context_type", "organizational_situational"),
                industry=extracted_data.get("industry"),
                organization_size=extracted_data.get("organization_size"),
                maturity_level=extracted_data.get("maturity_level"),
                regulatory_frameworks=extracted_data.get("regulatory_frameworks", [])
            )
            
            save_response = await self.contextual_graph_service.save_context(save_request)
            
            if save_response.success:
                logger.info(f"✓ Successfully saved context: {context_id}")
                self.contexts[context_id] = context_id
                # Note: Doc insight is automatically saved by ExtractionService
            else:
                logger.error(f"✗ Failed to save context {context_id}: {save_response.error}")
        
        logger.info(f"\nTotal contexts saved: {len(self.contexts)}\n")
    
    async def test_2_extract_and_save_controls(self):
        """Test 2: Extract and save controls from regulatory text
        
        Demonstrates:
        - Using default compliance rules
        - Using custom rules for HIPAA controls
        - Using custom rules for SOC2 controls
        """
        logger.info("=" * 80)
        logger.info("TEST 2: Extract and Save Controls from Regulatory Text")
        logger.info("=" * 80)
        
        # Example 1: HIPAA control with custom rules
        logger.info("\n--- Example 1: HIPAA control with custom healthcare-focused rules ---")
        hipaa_control_rules = ExtractionRules(
            extraction_type="control",
            domain="healthcare",
            system_role="expert at extracting HIPAA control information",
            system_instructions="""Extract HIPAA control information with focus on:
1. Control ID and name
2. HIPAA section reference (164.312, etc.)
3. PHI access requirements
4. Authentication and authorization mechanisms
5. Audit logging requirements
6. Implementation guidance for healthcare settings""",
            fields=[
                FieldExtractionRule("control_id", "HIPAA control identifier", required=True),
                FieldExtractionRule("hipaa_section", "HIPAA regulation section", 
                                  examples=["164.312(a)(1)", "164.312(a)(2)"]),
                FieldExtractionRule("phi_access_requirements", "PHI access requirements", data_type="list"),
                FieldExtractionRule("authentication_mechanisms", "Required authentication", data_type="list"),
                FieldExtractionRule("audit_requirements", "Audit logging requirements", data_type="list"),
            ],
            human_prompt_template="Extract HIPAA control from: {text}\nFramework: {framework}",
            human_prompt_variables=["text", "framework"]
        )
        
        response = await self.extraction_service.extract_control(
            text=HIPAA_CONTROL_TEXT,
            framework="HIPAA",
            context_metadata={"context_id": "healthcare_ctx"},
            configuration={"rules": hipaa_control_rules}
        )
        
        if not response.success:
            logger.error(f"Failed to extract HIPAA control: {response.error}")
        else:
            extracted_data = response.extracted_data
            logger.info(f"✓ Extracted HIPAA control with custom rules")
            logger.info(f"  Control ID: {extracted_data.get('control_id', 'N/A')}")
            logger.info(f"  HIPAA Section: {extracted_data.get('hipaa_section', 'N/A')}")
            
            # Save control
            control_id = extracted_data.get("control_id") or "HIPAA-AC-001"
            save_request = ControlSaveRequest(
                control_id=control_id,
                framework="HIPAA",
                control_name=extracted_data.get("control_name", "HIPAA Control"),
                control_description=extracted_data.get("control_description", ""),
                category=extracted_data.get("category", "access_control"),
                context_document=extracted_data.get("context_document", ""),
                context_metadata={"context_id": "healthcare_ctx"}
            )
            
            save_response = await self.contextual_graph_service.save_control(save_request)
            if save_response.success:
                logger.info(f"✓ Successfully saved control: {control_id}")
                self.controls[control_id] = {
                    "control_id": control_id,
                    "framework": "HIPAA",
                    "context_id": "healthcare_ctx"
                }
        
        # Example 2: SOC2 control with custom rules
        logger.info("\n--- Example 2: SOC2 control with custom technology-focused rules ---")
        soc2_control_rules = ExtractionRules(
            extraction_type="control",
            domain="technology",
            system_role="expert at extracting SOC2 control information",
            system_instructions="""Extract SOC2 control information with focus on:
1. Control ID and name
2. SOC2 criteria (CC6.1, CC6.7, etc.)
3. Logical access control mechanisms
4. Encryption and data protection requirements
5. Monitoring and logging requirements
6. Implementation guidance for cloud/SaaS environments""",
            fields=[
                FieldExtractionRule("control_id", "SOC2 control identifier", required=True),
                FieldExtractionRule("soc2_criteria", "SOC2 criteria reference",
                                  examples=["CC6.1", "CC6.7", "CC7.2"]),
                FieldExtractionRule("access_control_mechanisms", "Access control mechanisms", data_type="list"),
                FieldExtractionRule("encryption_requirements", "Encryption requirements", data_type="list"),
                FieldExtractionRule("monitoring_requirements", "Monitoring and logging", data_type="list"),
            ],
            human_prompt_template="Extract SOC2 control from: {text}\nFramework: {framework}",
            human_prompt_variables=["text", "framework"]
        )
        
        response = await self.extraction_service.extract_control(
            text=SOC2_CONTROL_TEXT,
            framework="SOC2",
            context_metadata={"context_id": "tech_company_ctx"},
            configuration={"rules": soc2_control_rules}
        )
        
        if not response.success:
            logger.error(f"Failed to extract SOC2 control: {response.error}")
        else:
            extracted_data = response.extracted_data
            logger.info(f"✓ Extracted SOC2 control with custom rules")
            logger.info(f"  Control ID: {extracted_data.get('control_id', 'N/A')}")
            logger.info(f"  SOC2 Criteria: {extracted_data.get('soc2_criteria', 'N/A')}")
            
            # Save control
            control_id = extracted_data.get("control_id") or "SOC2-CC6.1"
            save_request = ControlSaveRequest(
                control_id=control_id,
                framework="SOC2",
                control_name=extracted_data.get("control_name", "SOC2 Control"),
                control_description=extracted_data.get("control_description", ""),
                category=extracted_data.get("category", "access_control"),
                context_document=extracted_data.get("context_document", ""),
                context_metadata={"context_id": "tech_company_ctx"}
            )
            
            save_response = await self.contextual_graph_service.save_control(save_request)
            if save_response.success:
                logger.info(f"✓ Successfully saved control: {control_id}")
                self.controls[control_id] = {
                    "control_id": control_id,
                    "framework": "SOC2",
                    "context_id": "tech_company_ctx"
                }
        
        # Example 3: Using default rules (backward compatible)
        logger.info("\n--- Example 3: Using default compliance rules (backward compatible) ---")
        controls_to_process = [
            {
                "text": HIPAA_CONTROL_TEXT,
                "framework": "HIPAA",
                "context_id": "healthcare_ctx",
                "control_id_prefix": "HIPAA-AC-001"
            },
            {
                "text": SOC2_CONTROL_TEXT,
                "framework": "SOC2",
                "context_id": "tech_company_ctx",
                "control_id_prefix": "SOC2-CC6.1"
            }
        ]
        
        for control_info in controls_to_process:
            framework = control_info["framework"]
            context_id = control_info["context_id"]
            logger.info(f"\nProcessing {framework} control with default rules for context: {context_id}")
            
            # Extract control using extraction service with default rules
            response = await self.extraction_service.extract_control(
                text=control_info["text"],
                framework=framework,
                context_metadata={"context_id": context_id}
            )
            
            if not response.success:
                logger.error(f"Failed to extract {framework} control: {response.error}")
                continue
            
            extracted_data = response.extracted_data
            logger.info(f"Extracted control data keys: {list(extracted_data.keys())}")
            
            # Get control details
            control_id = extracted_data.get("control_id") or control_info["control_id_prefix"]
            control_name = extracted_data.get("control_name", f"{framework} Control")
            control_description = extracted_data.get("control_description", "")
            category = extracted_data.get("category", "access_control")
            context_document = extracted_data.get("context_document", "")
            
            logger.info(f"Control ID: {control_id}")
            logger.info(f"Control Name: {control_name}")
            logger.info(f"Category: {category}")
            
            # Save control to database and vector store
            save_request = ControlSaveRequest(
                control_id=control_id,
                framework=framework,
                control_name=control_name,
                control_description=control_description,
                category=category,
                context_document=context_document,
                context_metadata={"context_id": context_id}
            )
            
            save_response = await self.contextual_graph_service.save_control(save_request)
            
            if save_response.success:
                logger.info(f"✓ Successfully saved control: {control_id}")
                self.controls[control_id] = {
                    "control_id": control_id,
                    "framework": framework,
                    "context_id": context_id
                }
                # Note: Doc insight is automatically saved by ExtractionService
                
                # Extract entities from control text and create edges
                logger.info(f"Extracting entities from {control_id}...")
                
                # Example: Using ExtractionService with custom rules for entity extraction
                logger.info("  Using ExtractionService with custom entity extraction rules...")
                entity_extraction_rules = ExtractionRules(
                    extraction_type="entities",
                    domain="compliance",
                    system_role="expert at extracting compliance entities and relationships",
                    system_instructions="""Extract entities and relationships from compliance text:
1. Control entities with their properties
2. Requirement entities linked to controls
3. Evidence types needed for compliance
4. System entities involved in compliance
5. Relationships between entities (implements, requires, generates, etc.)""",
                    fields=[
                        FieldExtractionRule("entity_type", "Type of entity",
                                          examples=["control", "requirement", "evidence", "system"]),
                        FieldExtractionRule("entity_name", "Name of the entity", required=True),
                        FieldExtractionRule("relationships", "Relationships to other entities", data_type="list"),
                    ],
                    human_prompt_template="Extract entities and relationships from: {text}",
                    human_prompt_variables=["text"]
                )
                
                entities_response = await self.extraction_service.extract_entities(
                    text=control_info["text"],
                    context_id=context_id,
                    entity_types=["control", "requirement", "evidence", "system"],
                    context_metadata={
                        "context_id": context_id,
                        "framework": framework,
                        "control_id": control_id
                    },
                    configuration={"rules": entity_extraction_rules}
                )
                
                if entities_response.success:
                    logger.info(f"  ✓ Extracted entities using ExtractionService with custom rules")
                    entities_data = entities_response.extracted_data
                    logger.info(f"    Entities: {entities_data.get('entities_count', 0)}")
                    logger.info(f"    Edges: {entities_data.get('edges_count', 0)}")
                
                # Also use EntitiesExtractor for backward compatibility
                entities_result = await self.entities_extractor.extract_entities_and_create_edges(
                    text=control_info["text"],
                    context_id=context_id,
                    entity_types=["control", "requirement", "evidence", "system"],
                    context_metadata={
                        "context_id": context_id,
                        "framework": framework,
                        "control_id": control_id
                    }
                )
                
                # Save doc insight for entities extraction (done via EntitiesExtractor)
                if entities_result.get("entities") or entities_result.get("edges"):
                    await self.save_doc_insight_for_fields_or_entities(
                        doc_id=f"{control_id}_{context_id}_entities",
                        document_content=control_info["text"],
                        extraction_type="entities",
                        extracted_data={
                            "entities": entities_result.get("entities", []),
                            "entity_types": ["control", "requirement", "evidence", "system"],
                            "edges_count": len(entities_result.get("edges", []))
                        },
                        context_id=context_id,
                        extraction_metadata={
                            "framework": framework,
                            "control_id": control_id,
                            "entity_types": ["control", "requirement", "evidence", "system"]
                        }
                    )
                
                if entities_result.get("edges"):
                    edges = entities_result["edges"]
                    logger.info(f"  Created {len(edges)} entity relationship edges")
                    for edge in edges:
                        self.contextual_graph_service.vector_storage.save_contextual_edge(edge)
                        self.edges_created += 1
            else:
                logger.error(f"✗ Failed to save control {control_id}: {save_response.error}")
        
        logger.info(f"\nTotal controls saved: {len(self.controls)}")
        logger.info(f"Total edges created: {self.edges_created}\n")
    
    async def test_3_save_api_definition_as_context(self):
        """Test 3: Save API definition as knowledge context"""
        logger.info("=" * 80)
        logger.info("TEST 3: Save API Definition as Knowledge Context")
        logger.info("=" * 80)
        
        context_id = "api_security_context"
        
        # Create a context for API security
        api_context_description = f"""
API Security and Access Control Context

This context represents our API security and access control implementation.

{API_DEFINITION_DOC}

This API definition includes authentication, authorization, and security controls
that map to SOC2 CC6.1 (Logical Access Controls) and HIPAA 164.312(a)(1) (Access Control).
"""
        
        # Extract and save context
        response = await self.extraction_service.extract_context(
            description=api_context_description,
            context_id=context_id
        )
        
        if response.success:
            extracted_data = response.extracted_data
            
            save_request = ContextSaveRequest(
                context_id=context_id,
                document=api_context_description,
                context_type="technical_implementation",
                industry="technology",
                regulatory_frameworks=["SOC2", "HIPAA"],
                metadata={
                    "document_type": "api_definition",
                    "systems": ["authentication_api", "authorization_api"]
                }
            )
            
            save_response = await self.contextual_graph_service.save_context(save_request)
            
            if save_response.success:
                logger.info(f"✓ Successfully saved API definition context: {context_id}")
                self.contexts[context_id] = context_id
                # Note: Doc insight is automatically saved by ExtractionService
            else:
                logger.error(f"✗ Failed to save API context: {save_response.error}")
        else:
            logger.error(f"✗ Failed to extract API context: {response.error}")
        
        logger.info("")
    
    async def test_4_save_metrics_registry(self):
        """Test 4: Save metrics registry with SOC2 compliance mapping"""
        logger.info("=" * 80)
        logger.info("TEST 4: Save Metrics Registry with SOC2 Compliance Mapping")
        logger.info("=" * 80)
        
        context_id = "metrics_registry_context"
        
        # Create context for metrics registry
        metrics_context_description = f"""
Metrics Registry and Compliance Mapping Context

This context contains our metrics registry with SOC2 compliance mappings.

{METRICS_REGISTRY_DOC}

This metrics registry provides measurable controls that demonstrate compliance
with SOC2 requirements, particularly CC6.1 (Logical Access Controls), CC6.7 (Encryption),
and CC7.2 (System Monitoring).
"""
        
        # Extract and save context
        response = await self.extraction_service.extract_context(
            description=metrics_context_description,
            context_id=context_id
        )
        
        if response.success:
            extracted_data = response.extracted_data
            
            save_request = ContextSaveRequest(
                context_id=context_id,
                document=metrics_context_description,
                context_type="compliance_measurement",
                industry="technology",
                regulatory_frameworks=["SOC2"],
                metadata={
                    "document_type": "metrics_registry",
                    "compliance_framework": "SOC2"
                }
            )
            
            save_response = await self.contextual_graph_service.save_context(save_request)
            
            if save_response.success:
                logger.info(f"✓ Successfully saved metrics registry context: {context_id}")
                self.contexts[context_id] = context_id
                # Note: Doc insight is automatically saved by ExtractionService
                
                # Extract fields from metrics registry and create edges
                logger.info("Extracting fields from metrics registry...")
                
                # Example: Using ExtractionService with custom rules for metrics field extraction
                logger.info("  Using ExtractionService with custom metrics field extraction rules...")
                metrics_fields_rules = ExtractionRules(
                    extraction_type="fields",
                    domain="compliance_measurement",
                    system_role="expert at extracting compliance metrics and measurement fields",
                    system_instructions="""Extract compliance metrics fields with focus on:
1. Metric identifiers and names
2. SOC2/regulatory framework mappings
3. Target values and thresholds
4. Measurement frequency and methods
5. Data sources and collection systems""",
                    fields=[
                        FieldExtractionRule("metric_id", "Metric identifier", required=True),
                        FieldExtractionRule("metric_name", "Metric name", required=True),
                        FieldExtractionRule("soc2_mapping", "SOC2 control mapping"),
                        FieldExtractionRule("target_value", "Target metric value"),
                        FieldExtractionRule("frequency", "Measurement frequency"),
                        FieldExtractionRule("data_source", "Data source system"),
                    ],
                    human_prompt_template="Extract compliance metrics fields from: {text}",
                    human_prompt_variables=["text"]
                )
                
                field_definitions = [
                    {"name": "metric_id", "description": "Metric identifier", "data_type": "string"},
                    {"name": "metric_name", "description": "Metric name", "data_type": "string"},
                    {"name": "soc2_mapping", "description": "SOC2 control mapping", "data_type": "string"},
                    {"name": "target_value", "description": "Target metric value", "data_type": "string"},
                    {"name": "frequency", "description": "Measurement frequency", "data_type": "string"},
                    {"name": "data_source", "description": "Data source system", "data_type": "string"},
                ]
                
                fields_response = await self.extraction_service.extract_fields(
                    text=METRICS_REGISTRY_DOC,
                    context_id=context_id,
                    source_entity_id=context_id,
                    source_entity_type="context",
                    field_definitions=field_definitions,
                    context_metadata={
                        "context_id": context_id,
                        "document_type": "metrics_registry"
                    },
                    configuration={"rules": metrics_fields_rules}
                )
                
                if fields_response.success:
                    logger.info(f"  ✓ Extracted fields using ExtractionService with custom rules")
                    extracted_fields = fields_response.extracted_data.get("extracted_fields", [])
                    logger.info(f"    Extracted {len(extracted_fields)} fields")
                
                # Also use FieldsExtractor for backward compatibility
                fields_result = await self.fields_extractor.extract_fields_and_create_edges(
                    text=METRICS_REGISTRY_DOC,
                    context_id=context_id,
                    source_entity_id=context_id,
                    source_entity_type="context",
                    field_definitions=field_definitions,
                    context_metadata={
                        "context_id": context_id,
                        "document_type": "metrics_registry"
                    }
                )
                
                # Save doc insight for fields extraction (done via FieldsExtractor)
                if fields_result.get("extracted_fields"):
                    await self.save_doc_insight_for_fields_or_entities(
                        doc_id=f"{context_id}_fields",
                        document_content=METRICS_REGISTRY_DOC,
                        extraction_type="fields",
                        extracted_data={
                            "extracted_fields": fields_result.get("extracted_fields", []),
                            "field_definitions": field_definitions
                        },
                        context_id=context_id,
                        extraction_metadata={
                            "document_type": "metrics_registry",
                            "source_entity_id": context_id,
                            "source_entity_type": "context"
                        }
                    )
                
                if fields_result.get("edges"):
                    edges = fields_result["edges"]
                    logger.info(f"  Created {len(edges)} field relationship edges")
                    for edge in edges:
                        edge_doc_id = self.contextual_graph_service.vector_storage.save_contextual_edge(edge)
                        self.edges_created += 1
            else:
                logger.error(f"✗ Failed to save metrics context: {save_response.error}")
        else:
            logger.error(f"✗ Failed to extract metrics context: {response.error}")
        
        logger.info("")
    
    async def test_5_save_business_process(self):
        """Test 5: Save business process wiki content"""
        logger.info("=" * 80)
        logger.info("TEST 5: Save Business Process Wiki Content")
        logger.info("=" * 80)
        
        context_id = "employee_onboarding_process"
        
        # Create context for business process
        process_context_description = f"""
Employee Onboarding Process - Access Provisioning

This context describes our employee onboarding and access provisioning process.

{BUSINESS_PROCESS_WIKI}

This process demonstrates how we implement access controls in practice, mapping
to SOC2 CC6.1 requirements and HIPAA access control requirements.
"""
        
        # Extract and save context
        response = await self.extraction_service.extract_context(
            description=process_context_description,
            context_id=context_id
        )
        
        if response.success:
            extracted_data = response.extracted_data
            
            save_request = ContextSaveRequest(
                context_id=context_id,
                document=process_context_description,
                context_type="business_process",
                industry="technology",
                regulatory_frameworks=["SOC2", "HIPAA"],
                metadata={
                    "document_type": "business_process",
                    "process_name": "employee_onboarding",
                    "process_type": "access_provisioning"
                }
            )
            
            save_response = await self.contextual_graph_service.save_context(save_request)
            
            if save_response.success:
                logger.info(f"✓ Successfully saved business process context: {context_id}")
                self.contexts[context_id] = context_id
                # Note: Doc insight is automatically saved by ExtractionService
                
                # Extract entities from business process and create edges
                logger.info("Extracting entities and relationships from business process...")
                
                # Example: Using ExtractionService with custom rules for business process entity extraction
                logger.info("  Using ExtractionService with custom business process entity extraction rules...")
                business_process_entity_rules = ExtractionRules(
                    extraction_type="entities",
                    domain="business_process",
                    system_role="expert at extracting business process entities and relationships",
                    system_instructions="""Extract entities and relationships from business process documentation:
1. Process entities with steps and workflows
2. System entities involved in the process
3. Role entities (who performs actions)
4. Control entities (compliance controls)
5. Requirement entities (what must be done)
6. Relationships (performs, uses, requires, implements, etc.)""",
                    fields=[
                        FieldExtractionRule("entity_type", "Type of entity",
                                          examples=["process", "system", "role", "control", "requirement"]),
                        FieldExtractionRule("entity_name", "Name of the entity", required=True),
                        FieldExtractionRule("process_step", "Process step number or sequence", data_type="int"),
                        FieldExtractionRule("relationships", "Relationships to other entities", data_type="list"),
                    ],
                    human_prompt_template="Extract business process entities from: {text}",
                    human_prompt_variables=["text"]
                )
                
                entities_response = await self.extraction_service.extract_entities(
                    text=BUSINESS_PROCESS_WIKI,
                    context_id=context_id,
                    entity_types=["process", "system", "role", "control", "requirement"],
                    context_metadata={
                        "context_id": context_id,
                        "document_type": "business_process",
                        "process_name": "employee_onboarding"
                    },
                    configuration={"rules": business_process_entity_rules}
                )
                
                if entities_response.success:
                    logger.info(f"  ✓ Extracted entities using ExtractionService with custom rules")
                    entities_data = entities_response.extracted_data
                    logger.info(f"    Entities: {entities_data.get('entities_count', 0)}")
                    logger.info(f"    Edges: {entities_data.get('edges_count', 0)}")
                
                # Also use EntitiesExtractor for backward compatibility
                entities_result = await self.entities_extractor.extract_entities_and_create_edges(
                    text=BUSINESS_PROCESS_WIKI,
                    context_id=context_id,
                    entity_types=["process", "system", "role", "control", "requirement"],
                    context_metadata={
                        "context_id": context_id,
                        "document_type": "business_process",
                        "process_name": "employee_onboarding"
                    }
                )
                
                if entities_result.get("entities"):
                    logger.info(f"  Extracted {len(entities_result['entities'])} entities using EntitiesExtractor")
                    for entity in entities_result["entities"][:5]:  # Show first 5
                        logger.info(f"    - {entity.get('entity_name', entity.get('entity_id'))} ({entity.get('entity_type')})")
                
                # Save doc insight for entities extraction (done via EntitiesExtractor)
                if entities_result.get("entities") or entities_result.get("edges"):
                    await self.save_doc_insight_for_fields_or_entities(
                        doc_id=f"{context_id}_entities",
                        document_content=BUSINESS_PROCESS_WIKI,
                        extraction_type="entities",
                        extracted_data={
                            "entities": entities_result.get("entities", []),
                            "entity_types": ["process", "system", "role", "control", "requirement"]
                        },
                        context_id=context_id,
                        extraction_metadata={
                            "document_type": "business_process",
                            "process_name": "employee_onboarding"
                        }
                    )
                
                if entities_result.get("edges"):
                    edges = entities_result["edges"]
                    logger.info(f"  Created {len(edges)} entity relationship edges")
                    for edge in edges:
                        edge_doc_id = self.contextual_graph_service.vector_storage.save_contextual_edge(edge)
                        self.edges_created += 1
            else:
                logger.error(f"✗ Failed to save process context: {save_response.error}")
        else:
            logger.error(f"✗ Failed to extract process context: {response.error}")
        
        logger.info("")
    
    async def test_6_query_contexts(self):
        """Test 6: Query and search contexts"""
        logger.info("=" * 80)
        logger.info("TEST 6: Query and Search Contexts")
        logger.info("=" * 80)
        
        # Search for healthcare contexts
        logger.info("\nSearching for healthcare-related contexts...")
        search_request = ContextSearchRequest(
            description="healthcare organization with HIPAA requirements",
            top_k=5
        )
        
        search_response = await self.contextual_graph_service.search_contexts(search_request)
        
        if search_response.success:
            contexts = search_response.data.get("contexts", [])
            logger.info(f"Found {len(contexts)} healthcare contexts:")
            for ctx in contexts:
                logger.info(f"  - {ctx.get('context_id')}: {ctx.get('metadata', {})}")
        else:
            logger.error(f"Search failed: {search_response.error}")
        
        # Search for SOC2 contexts
        logger.info("\nSearching for SOC2-related contexts...")
        search_request = ContextSearchRequest(
            description="SOC2 compliance and access controls",
            top_k=5
        )
        
        search_response = await self.contextual_graph_service.search_contexts(search_request)
        
        if search_response.success:
            contexts = search_response.data.get("contexts", [])
            logger.info(f"Found {len(contexts)} SOC2 contexts:")
            for ctx in contexts:
                logger.info(f"  - {ctx.get('context_id')}: {ctx.get('metadata', {})}")
        else:
            logger.error(f"Search failed: {search_response.error}")
        
        logger.info("")
    
    async def test_7_query_controls(self):
        """Test 7: Query controls by context"""
        logger.info("=" * 80)
        logger.info("TEST 7: Query Controls by Context")
        logger.info("=" * 80)
        
        # Search for controls in healthcare context
        logger.info("\nSearching for controls in healthcare context...")
        search_request = ControlSearchRequest(
            context_id="healthcare_ctx",
            query="access control HIPAA",
            top_k=10
        )
        
        search_response = await self.contextual_graph_service.search_controls(search_request)
        
        if search_response.success:
            controls = search_response.data.get("controls", [])
            logger.info(f"Found {len(controls)} controls:")
            for i, ctrl in enumerate(controls, 1):
                control_data = ctrl.get("control", {})
                logger.info(f"  {i}. {control_data.get('control_id')}: {control_data.get('control_name')}")
                if ctrl.get("analytics"):
                    logger.info(f"     Analytics: {ctrl.get('analytics')}")
        else:
            logger.error(f"Search failed: {search_response.error}")
        
        # Search for priority controls
        logger.info("\nSearching for priority controls in tech company context...")
        priority_request = PriorityControlsRequest(
            context_id="tech_company_ctx",
            query="access control and authentication",
            top_k=5
        )
        
        priority_response = await self.contextual_graph_service.get_priority_controls(priority_request)
        
        if priority_response.success:
            controls = priority_response.data.get("controls", [])
            logger.info(f"Found {len(controls)} priority controls:")
            for i, ctrl in enumerate(controls, 1):
                logger.info(f"  {i}. {ctrl.get('control_id')}: {ctrl.get('control_name')}")
        else:
            logger.error(f"Priority search failed: {priority_response.error}")
        
        logger.info("")
    
    async def test_8_extract_fields_from_api_definition(self):
        """Test 8: Extract fields from API definition and create edges
        
        Demonstrates:
        - Using ExtractionService for fields extraction with custom rules
        - Using FieldsExtractor directly (legacy approach)
        """
        logger.info("=" * 80)
        logger.info("TEST 8: Extract Fields from API Definition")
        logger.info("=" * 80)
        
        context_id = "api_security_context"
        
        # Example 1: Using ExtractionService with custom rules
        logger.info("\n--- Example 1: Using ExtractionService with custom API security rules ---")
        api_fields_rules = ExtractionRules(
            extraction_type="fields",
            domain="technology",
            system_role="expert at extracting API security field information",
            system_instructions="""Extract API security fields with focus on:
1. Endpoint paths and HTTP methods
2. Authentication and authorization requirements
3. Security requirements (encryption, rate limiting, etc.)
4. Input validation requirements
5. Response security headers""",
            fields=[
                FieldExtractionRule("endpoint", "API endpoint path", required=True),
                FieldExtractionRule("method", "HTTP method", 
                                  examples=["GET", "POST", "PUT", "DELETE", "PATCH"]),
                FieldExtractionRule("authentication_required", "Authentication requirement", data_type="bool"),
                FieldExtractionRule("security_requirements", "Security requirements", data_type="list"),
                FieldExtractionRule("rate_limiting", "Rate limiting configuration"),
            ],
            human_prompt_template="Extract API security fields from: {text}",
            human_prompt_variables=["text"]
        )
        
        # Define fields to extract from API definition
        field_definitions = [
            {"name": "endpoint", "description": "API endpoint path", "data_type": "string"},
            {"name": "method", "description": "HTTP method (GET, POST, etc.)", "data_type": "string"},
            {"name": "authentication_required", "description": "Whether authentication is required", "data_type": "bool"},
            {"name": "security_requirements", "description": "Security requirements for the endpoint", "data_type": "list"},
            {"name": "rate_limiting", "description": "Rate limiting configuration", "data_type": "string"},
        ]
        
        logger.info("Extracting fields from API definition using ExtractionService...")
        fields_response = await self.extraction_service.extract_fields(
            text=API_DEFINITION_DOC,
            context_id=context_id,
            source_entity_id=context_id,
            source_entity_type="api_definition",
            field_definitions=field_definitions,
            context_metadata={
                "context_id": context_id,
                "document_type": "api_definition"
            },
            configuration={"rules": api_fields_rules}
        )
        
        if fields_response.success:
            logger.info(f"✓ Extracted fields using ExtractionService with custom rules")
            extracted_fields = fields_response.extracted_data.get("extracted_fields", [])
            logger.info(f"  Extracted {len(extracted_fields)} fields")
            for field in extracted_fields[:5]:  # Show first 5
                logger.info(f"    - {field.get('field_name')}: {field.get('field_value')}")
        else:
            logger.error(f"✗ Fields extraction failed: {fields_response.error}")
        
        # Example 2: Using FieldsExtractor directly (legacy approach)
        logger.info("\n--- Example 2: Using FieldsExtractor directly (legacy approach) ---")
        fields_result = await self.fields_extractor.extract_fields_and_create_edges(
            text=API_DEFINITION_DOC,
            context_id=context_id,
            source_entity_id=context_id,
            source_entity_type="api_definition",
            field_definitions=field_definitions,
            context_metadata={
                "context_id": context_id,
                "document_type": "api_definition"
            }
        )
        
        if fields_result.get("extracted_fields"):
            logger.info(f"  Extracted {len(fields_result['extracted_fields'])} fields using FieldsExtractor")
            for field in fields_result["extracted_fields"][:5]:  # Show first 5
                logger.info(f"    - {field.get('field_name')}: {field.get('field_value')}")
        
        # Save doc insight for fields extraction (done via FieldsExtractor)
        if fields_result.get("extracted_fields"):
            await self.save_doc_insight_for_fields_or_entities(
                doc_id=f"{context_id}_api_fields",
                document_content=API_DEFINITION_DOC,
                extraction_type="fields",
                extracted_data={
                    "extracted_fields": fields_result.get("extracted_fields", []),
                    "field_definitions": field_definitions
                },
                context_id=context_id,
                extraction_metadata={
                    "document_type": "api_definition",
                    "source_entity_id": context_id,
                    "source_entity_type": "api_definition"
                }
            )
        
        if fields_result.get("edges"):
            edges = fields_result["edges"]
            logger.info(f"  Created {len(edges)} field relationship edges")
            for edge in edges:
                edge_doc_id = self.contextual_graph_service.vector_storage.save_contextual_edge(edge)
                self.edges_created += 1
                logger.info(f"    ✓ Saved edge: {edge.edge_type} ({edge.source_entity_id} -> {edge.target_entity_id})")
        
        logger.info("")
    
    async def test_9_display_summary(self):
        """Test 9: Display summary of ingested data"""
        logger.info("=" * 80)
        logger.info("TEST 9: Summary of Ingested Data")
        logger.info("=" * 80)
        
        logger.info(f"\nTotal Contexts Created: {len(self.contexts)}")
        for ctx_id in self.contexts.keys():
            logger.info(f"  - {ctx_id}")
        
        logger.info(f"\nTotal Controls Created: {len(self.controls)}")
        for ctrl_id, ctrl_data in self.controls.items():
            logger.info(f"  - {ctrl_id} ({ctrl_data['framework']}) for context: {ctrl_data['context_id']}")
        
        logger.info(f"\nTotal Contextual Edges Created: {self.edges_created}")
        
        # Query edges for each context
        for ctx_id in self.contexts.keys():
            edges = self.contextual_graph_service.vector_storage.get_edges_for_context(
                context_id=ctx_id,
                top_k=100
            )
            if edges:
                logger.info(f"  Context '{ctx_id}' has {len(edges)} edges")
                edge_types = {}
                for edge in edges:
                    edge_type = edge.edge_type
                    edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
                for edge_type, count in edge_types.items():
                    logger.info(f"    - {edge_type}: {count}")
        
        # Query doc insights by extraction type
        try:
            async with self.db_pool.acquire() as conn:
                total_count = await conn.fetchval("SELECT COUNT(*) FROM document_kg_insights")
                logger.info(f"\nTotal Doc Insights Saved: {total_count}")
                
                for extraction_type in ["context", "control", "fields", "entities", "requirement", "evidence"]:
                    count = await conn.fetchval(
                        "SELECT COUNT(*) FROM document_kg_insights WHERE extraction_type = $1",
                        extraction_type
                    )
                    if count and count > 0:
                        logger.info(f"  Doc insights ({extraction_type}): {count}")
        except Exception as e:
            logger.warning(f"Could not query doc insights: {str(e)}")
        
        logger.info("\n" + "=" * 80)
        logger.info("Integration test completed successfully!")
        logger.info("=" * 80)
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info("\nCleaning up resources...")
        
        if self.db_pool:
            await self.db_pool.close()
            logger.info("PostgreSQL connection pool closed")
        
        # Clear all caches
        clear_all_caches()
        logger.info("Cleared all dependency caches")
        
        logger.info("Cleanup complete")
    
    async def run_all_tests(self):
        """Run all integration tests"""
        try:
            await self.setup()
            
            await self.test_1_extract_and_save_contexts()
            await self.test_2_extract_and_save_controls()
            await self.test_3_save_api_definition_as_context()
            await self.test_4_save_metrics_registry()
            await self.test_5_save_business_process()
            await self.test_6_query_contexts()
            await self.test_7_query_controls()
            await self.test_8_extract_fields_from_api_definition()
            await self.test_9_display_summary()
            
        except Exception as e:
            logger.error(f"Test failed with error: {str(e)}", exc_info=True)
            raise
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    test = IntegrationTest()
    await test.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())


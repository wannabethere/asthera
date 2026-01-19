"""
Compliance Document Processor
Processes SOC2 controls, policy documents, and risk controls using extraction pipelines.
"""
import logging
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from app.agents.extractors.context_extractor import ContextExtractor
from app.agents.extractors.control_extractor import ControlExtractor
from app.agents.extractors.entities_extractor import EntitiesExtractor
from app.agents.extractors.evidence_extractor import EvidenceExtractor
from app.agents.extractors.fields_extractor import FieldsExtractor
from app.agents.extractors.requirement_extractor import RequirementExtractor
from app.agents.extractors.extraction_rules import (
    get_compliance_context_rules,
    get_compliance_control_rules,
    get_compliance_evidence_rules,
    get_compliance_requirement_rules
)
from app.core.dependencies import get_llm

logger = logging.getLogger(__name__)


class ComplianceDocumentProcessor:
    """Processes compliance documents (SOC2, policies, risk controls) with extraction pipelines."""
    
    def __init__(
        self,
        llm=None,
        enable_extraction: bool = True
    ):
        """
        Initialize the compliance document processor.
        
        Args:
            llm: Language model for extraction (uses dependency injection if None)
            enable_extraction: Whether to enable extraction pipelines
        """
        self.llm = llm or get_llm(temperature=0.2)
        self.enable_extraction = enable_extraction
        
        # Initialize extractors
        if enable_extraction:
            self.context_extractor = ContextExtractor(llm=self.llm)
            self.control_extractor = ControlExtractor(llm=self.llm)
            self.entities_extractor = EntitiesExtractor(llm=self.llm)
            self.evidence_extractor = EvidenceExtractor(llm=self.llm)
            self.fields_extractor = FieldsExtractor(llm=self.llm)
            self.requirement_extractor = RequirementExtractor(llm=self.llm)
        
        logger.info("ComplianceDocumentProcessor initialized")
    
    async def process_pdf_document(
        self,
        pdf_path: Union[str, Path],
        document_type: str = "policy",
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Process a PDF document and extract structured information.
        
        Args:
            pdf_path: Path to PDF file
            document_type: Type of document ("policy", "soc2_controls", "risk_controls")
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            List of Document objects with extracted information
        """
        logger.info(f"Processing PDF document: {pdf_path}, type: {document_type}")
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Load PDF with fallback options
        pdf_documents = None
        error_messages = []
        successful_pages = 0
        
        # Try PyPDFLoader first
        try:
            loader = PyPDFLoader(str(pdf_path))
            pdf_documents = loader.load()
            successful_pages = len([d for d in pdf_documents if d.page_content.strip()])
            logger.info(f"Loaded PDF with PyPDFLoader: {len(pdf_documents)} pages, {successful_pages} with content")
        except Exception as e:
            error_messages.append(f"PyPDFLoader error: {e}")
            logger.warning(f"PyPDFLoader failed: {e}, trying alternative methods...")
            pdf_documents = None
        
        # If PyPDFLoader failed or extracted too few pages, try pdfplumber (better for complex PDFs)
        if pdf_documents is None or successful_pages < len(pdf_documents) * 0.5:
            try:
                import pdfplumber
                logger.info("Attempting to load PDF with pdfplumber...")
                pdf_documents_plumber = []
                with pdfplumber.open(str(pdf_path)) as pdf:
                    for i, page in enumerate(pdf.pages):
                        try:
                            # Try multiple extraction methods
                            text = page.extract_text() or ""
                            # If no text, try extracting tables
                            if not text.strip() and page.extract_tables():
                                # Convert tables to text
                                table_texts = []
                                for table in page.extract_tables():
                                    if table:
                                        table_texts.append("\n".join(["\t".join([str(cell) if cell else "" for cell in row]) for row in table]))
                                text = "\n\n".join(table_texts)
                            
                            if text.strip():
                                pdf_documents_plumber.append(Document(
                                    page_content=text,
                                    metadata={"page": i, "source": str(pdf_path), "extraction_method": "pdfplumber"}
                                ))
                        except Exception as page_error:
                            logger.debug(f"Error extracting text from page {i} with pdfplumber: {page_error}")
                            # Skip pages that fail silently
                            continue
                
                if pdf_documents_plumber:
                    successful_pages = len(pdf_documents_plumber)
                    logger.info(f"Loaded PDF with pdfplumber: {successful_pages} pages with content")
                    pdf_documents = pdf_documents_plumber
            except ImportError:
                error_messages.append("pdfplumber not available")
                logger.warning("pdfplumber not available. Install with: pip install pdfplumber")
            except Exception as e:
                error_messages.append(f"pdfplumber error: {e}")
                logger.warning(f"pdfplumber failed: {e}, trying pypdf...")
        
        # If pdfplumber failed or not available, try pypdf as fallback
        if pdf_documents is None or successful_pages == 0:
            try:
                import pypdf
                logger.info("Attempting to load PDF with pypdf...")
                pdf_reader = pypdf.PdfReader(str(pdf_path))
                pdf_documents_pypdf = []
                for i, page in enumerate(pdf_reader.pages):
                    try:
                        # Try to extract text with error handling
                        text = page.extract_text()
                        if text and text.strip():
                            pdf_documents_pypdf.append(Document(
                                page_content=text,
                                metadata={"page": i, "source": str(pdf_path), "extraction_method": "pypdf"}
                            ))
                    except (KeyError, AttributeError, Exception) as page_error:
                        # Skip pages with bbox errors or other extraction issues
                        logger.debug(f"Skipping page {i} due to extraction error: {page_error}")
                        continue
                
                if pdf_documents_pypdf:
                    successful_pages = len(pdf_documents_pypdf)
                    logger.info(f"Loaded PDF with pypdf: {successful_pages} pages with content")
                    pdf_documents = pdf_documents_pypdf
            except ImportError:
                error_messages.append("pypdf not available")
                logger.warning("pypdf not available")
            except Exception as e:
                error_messages.append(f"pypdf error: {e}")
                logger.warning(f"pypdf failed: {e}")
        
        if pdf_documents is None or len(pdf_documents) == 0:
            error_msg = "Failed to load PDF with all available methods. Errors: " + "; ".join(error_messages)
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Filter out empty documents (shouldn't be needed but just in case)
        pdf_documents = [doc for doc in pdf_documents if doc.page_content.strip()]
        
        if len(pdf_documents) == 0:
            raise ValueError("PDF loaded but no text content extracted from any pages")
        
        logger.info(f"Successfully loaded {len(pdf_documents)} pages with content from {pdf_path.name}")
        
        # Combine all pages
        full_content = "\n\n".join([doc.page_content for doc in pdf_documents])
        
        # Create base document
        base_metadata = {
            "content_type": document_type,
            "source_file": str(pdf_path),
            "file_name": pdf_path.name,
            "document_type": document_type,
            "domain": domain or "compliance",
            "indexed_at": datetime.utcnow().isoformat(),
            "page_count": len(pdf_documents),
            **(metadata or {})
        }
        
        documents = []
        
        # Process based on document type
        if document_type == "policy":
            docs = await self._process_policy_document(full_content, base_metadata)
            documents.extend(docs)
        elif document_type == "soc2_controls":
            docs = await self._process_soc2_controls_document(full_content, base_metadata)
            documents.extend(docs)
        elif document_type == "risk_controls":
            docs = await self._process_risk_controls_document(full_content, base_metadata)
            documents.extend(docs)
        else:
            # Generic processing
            doc = Document(
                page_content=full_content,
                metadata=base_metadata
            )
            documents.append(doc)
        
        logger.info(f"Created {len(documents)} documents from PDF")
        return documents
    
    async def process_excel_document(
        self,
        excel_path: Union[str, Path],
        document_type: str = "risk_controls",
        sheet_name: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[Document]:
        """
        Process an Excel document and extract structured information.
        
        Args:
            excel_path: Path to Excel file
            document_type: Type of document ("risk_controls", "soc2_controls")
            sheet_name: Specific sheet to process (None for all sheets)
            domain: Domain filter
            metadata: Additional metadata
            
        Returns:
            List of Document objects with extracted information
        """
        logger.info(f"Processing Excel document: {excel_path}, type: {document_type}")
        
        excel_path = Path(excel_path)
        if not excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")
        
        # Load Excel
        try:
            excel_file = pd.ExcelFile(str(excel_path))
            sheets_to_process = [sheet_name] if sheet_name else excel_file.sheet_names
            logger.info(f"Found {len(excel_file.sheet_names)} sheets, processing {len(sheets_to_process)}")
        except Exception as e:
            logger.error(f"Error loading Excel: {e}")
            raise
        
        documents = []
        
        for sheet in sheets_to_process:
            try:
                df = pd.read_excel(excel_file, sheet_name=sheet)
                logger.info(f"Loaded sheet '{sheet}': {len(df)} rows, {len(df.columns)} columns")
                
                # Convert DataFrame to structured content
                content = self._dataframe_to_content(df, sheet)
                
                base_metadata = {
                    "content_type": document_type,
                    "source_file": str(excel_path),
                    "file_name": excel_path.name,
                    "document_type": document_type,
                    "sheet_name": sheet,
                    "domain": domain or "compliance",
                    "indexed_at": datetime.utcnow().isoformat(),
                    "row_count": len(df),
                    "column_count": len(df.columns),
                    **(metadata or {})
                }
                
                # Process based on document type
                if document_type == "risk_controls":
                    docs = await self._process_risk_controls_excel(df, content, base_metadata)
                    documents.extend(docs)
                elif document_type == "soc2_controls":
                    docs = await self._process_soc2_controls_excel(df, content, base_metadata)
                    documents.extend(docs)
                else:
                    # Generic processing
                    doc = Document(
                        page_content=content,
                        metadata=base_metadata
                    )
                    documents.append(doc)
                    
            except Exception as e:
                logger.error(f"Error processing sheet '{sheet}': {e}")
                continue
        
        logger.info(f"Created {len(documents)} documents from Excel")
        return documents
    
    async def _process_policy_document(
        self,
        content: str,
        base_metadata: Dict[str, Any]
    ) -> List[Document]:
        """Process a policy document with extraction pipelines."""
        documents = []
        
        # Extract context
        if self.enable_extraction:
            try:
                context_def = await self.context_extractor.extract_context_from_description(
                    description=content[:5000],  # Limit for context extraction
                    context_id=f"policy_{base_metadata.get('file_name', 'unknown')}"
                )
                
                # Create context document
                context_doc = Document(
                    page_content=json.dumps({
                        "context_type": context_def.context_type,
                        "industry": context_def.industry,
                        "organization_size": context_def.organization_size,
                        "regulatory_frameworks": context_def.regulatory_frameworks,
                        "data_types": context_def.data_types,
                        "systems": context_def.systems,
                        "maturity_level": context_def.maturity_level
                    }, indent=2),
                    metadata={
                        **base_metadata,
                        "extraction_type": "context",
                        "context_id": context_def.context_id
                    }
                )
                documents.append(context_doc)
            except Exception as e:
                logger.warning(f"Error extracting context: {e}")
        
        # Extract entities
        if self.enable_extraction:
            try:
                entities_result = await self.entities_extractor.extract_entities_and_create_edges(
                    text=content,
                    context_id=f"policy_{base_metadata.get('file_name', 'unknown')}",
                    entity_types=["policy", "requirement", "control", "procedure"]
                )
                
                if entities_result.get("entities"):
                    # Convert ContextualEdge objects to dicts for JSON serialization
                    serializable_result = self._serialize_entities_result(entities_result)
                    
                    entities_doc = Document(
                        page_content=json.dumps(serializable_result, indent=2, default=str),
                        metadata={
                            **base_metadata,
                            "extraction_type": "entities",
                            "entity_count": len(entities_result.get("entities", []))
                        }
                    )
                    documents.append(entities_doc)
            except Exception as e:
                logger.warning(f"Error extracting entities: {e}")
        
        # Extract requirements
        if self.enable_extraction:
            try:
                # Split content into sections for requirement extraction
                sections = content.split("\n\n")
                for i, section in enumerate(sections[:10]):  # Limit to first 10 sections
                    if len(section.strip()) > 100:  # Only process substantial sections
                        try:
                            req_doc_content = await self.requirement_extractor.create_requirement_edge_document(
                                requirement_text=section,
                                control_id=None,  # Explicitly pass None for policy documents
                                context_metadata=base_metadata
                            )
                            
                            if req_doc_content and req_doc_content.strip():
                                req_doc = Document(
                                    page_content=req_doc_content,
                                    metadata={
                                        **base_metadata,
                                        "extraction_type": "requirement",
                                        "section_index": i
                                    }
                                )
                                documents.append(req_doc)
                        except Exception as section_error:
                            logger.debug(f"Error extracting requirement from section {i}: {section_error}")
                            continue
            except Exception as e:
                logger.warning(f"Error extracting requirements: {e}")
        
        # Add full content document
        full_doc = Document(
            page_content=content,
            metadata={**base_metadata, "extraction_type": "full_content"}
        )
        documents.append(full_doc)
        
        return documents
    
    async def _process_soc2_controls_document(
        self,
        content: str,
        base_metadata: Dict[str, Any]
    ) -> List[Document]:
        """Process SOC2 controls document with extraction pipelines."""
        documents = []
        
        # Extract controls
        if self.enable_extraction:
            try:
                # Split content into potential control sections
                sections = content.split("\n\n")
                control_count = 0
                
                for section in sections:
                    if len(section.strip()) > 200:  # Only process substantial sections
                        try:
                            control_result = await self.control_extractor.extract_control_from_text(
                                text=section,
                                framework="SOC2",
                                context_metadata=base_metadata
                            )
                            
                            if control_result.get("control_id"):
                                control_doc = Document(
                                    page_content=json.dumps(control_result, indent=2),
                                    metadata={
                                        **base_metadata,
                                        "extraction_type": "control",
                                        "control_id": control_result.get("control_id"),
                                        "framework": "SOC2"
                                    }
                                )
                                documents.append(control_doc)
                                control_count += 1
                        except Exception as e:
                            logger.debug(f"Error extracting control from section: {e}")
                            continue
                
                logger.info(f"Extracted {control_count} controls from SOC2 document")
            except Exception as e:
                logger.warning(f"Error extracting controls: {e}")
        
        # Extract entities
        if self.enable_extraction:
            try:
                entities_result = await self.entities_extractor.extract_entities_and_create_edges(
                    text=content,
                    context_id=f"soc2_{base_metadata.get('file_name', 'unknown')}",
                    entity_types=["control", "trust_service_criteria", "control_activity", "evidence"]
                )
                
                if entities_result.get("entities"):
                    # Convert ContextualEdge objects to dicts for JSON serialization
                    serializable_result = self._serialize_entities_result(entities_result)
                    
                    entities_doc = Document(
                        page_content=json.dumps(serializable_result, indent=2, default=str),
                        metadata={
                            **base_metadata,
                            "extraction_type": "entities",
                            "entity_count": len(entities_result.get("entities", []))
                        }
                    )
                    documents.append(entities_doc)
            except Exception as e:
                logger.warning(f"Error extracting entities: {e}")
        
        # Add full content document
        full_doc = Document(
            page_content=content,
            metadata={**base_metadata, "extraction_type": "full_content"}
        )
        documents.append(full_doc)
        
        return documents
    
    async def _process_risk_controls_document(
        self,
        content: str,
        base_metadata: Dict[str, Any]
    ) -> List[Document]:
        """Process risk controls document with extraction pipelines."""
        documents = []
        
        # Similar to SOC2 but focused on risk and controls
        if self.enable_extraction:
            try:
                sections = content.split("\n\n")
                # Filter sections by length
                valid_sections = [
                    (idx, section) for idx, section in enumerate(sections)
                    if len(section.strip()) > 200
                ]
                
                total_sections = len(valid_sections)
                control_count = 0
                batch_size = 10
                
                # Process sections in batches
                for i in range(0, total_sections, batch_size):
                    batch = valid_sections[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    total_batches = (total_sections + batch_size - 1) // batch_size
                    
                    logger.info(f"Processing risk controls PDF batch {batch_num}/{total_batches} ({len(batch)} sections)")
                    
                    # Create tasks for batch
                    import asyncio
                    batch_tasks = [
                        self._process_single_risk_section(section, idx, base_metadata)
                        for idx, section in batch
                    ]
                    
                    try:
                        batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                        
                        # Handle results
                        for result in batch_results:
                            if isinstance(result, Exception):
                                logger.warning(f"Error in batch processing: {result}")
                                continue
                            if result:  # Only add non-None results
                                documents.append(result)
                                control_count += 1
                                
                    except Exception as e:
                        logger.error(f"Error processing batch {batch_num}: {e}")
                        # Fallback: process sections individually
                        for idx, section in batch:
                            try:
                                doc = await self._process_single_risk_section(section, idx, base_metadata)
                                if doc:
                                    documents.append(doc)
                                    control_count += 1
                            except Exception as section_error:
                                logger.warning(f"Error processing section {idx}: {section_error}")
                
                logger.info(f"Extracted {control_count} controls from risk document")
            except Exception as e:
                logger.warning(f"Error extracting controls: {e}")
        
        # Add full content document
        full_doc = Document(
            page_content=content,
            metadata={**base_metadata, "extraction_type": "full_content"}
        )
        documents.append(full_doc)
        
        return documents
    
    async def _process_single_risk_control_row(
        self,
        idx: int,
        row: pd.Series,
        base_metadata: Dict[str, Any]
    ) -> Document:
        """Process a single risk control row."""
        try:
            # Convert row to text description
            row_text = self._row_to_text(row)
            
            if self.enable_extraction and len(row_text.strip()) > 50:
                try:
                    control_result = await self.control_extractor.extract_control_from_text(
                        text=row_text,
                        framework="Risk Management",
                        context_metadata={**base_metadata, "row_index": idx}
                    )
                    
                    control_doc = Document(
                        page_content=json.dumps({
                            "row_data": row.to_dict(),
                            "extracted_control": control_result
                        }, indent=2, default=str),
                        metadata={
                            **base_metadata,
                            "extraction_type": "control",
                            "row_index": idx,
                            "control_id": control_result.get("control_id"),
                            "framework": "Risk Management"
                        }
                    )
                    return control_doc
                except Exception as e:
                    logger.debug(f"Error extracting control from row {idx}: {e}")
                    # Still create document with raw data
                    control_doc = Document(
                        page_content=json.dumps(row.to_dict(), indent=2, default=str),
                        metadata={
                            **base_metadata,
                            "extraction_type": "raw_data",
                            "row_index": idx
                        }
                    )
                    return control_doc
            else:
                # Create document with raw data if extraction not enabled or text too short
                control_doc = Document(
                    page_content=json.dumps(row.to_dict(), indent=2, default=str),
                    metadata={
                        **base_metadata,
                        "extraction_type": "raw_data",
                        "row_index": idx
                    }
                )
                return control_doc
        except Exception as e:
            logger.warning(f"Error processing row {idx}: {e}")
            # Return a minimal document on error
            return Document(
                page_content=json.dumps(row.to_dict(), indent=2, default=str),
                metadata={
                    **base_metadata,
                    "extraction_type": "error",
                    "row_index": idx,
                    "error": str(e)
                }
            )
    
    async def _process_risk_controls_excel(
        self,
        df: pd.DataFrame,
        content: str,
        base_metadata: Dict[str, Any],
        batch_size: int = 10
    ) -> List[Document]:
        """Process risk controls from Excel DataFrame in batches."""
        import asyncio
        
        documents = []
        total_rows = len(df)
        
        # Process rows in batches
        for i in range(0, total_rows, batch_size):
            batch_indices = list(range(i, min(i + batch_size, total_rows)))
            batch_num = (i // batch_size) + 1
            total_batches = (total_rows + batch_size - 1) // batch_size
            
            logger.info(f"Processing risk controls batch {batch_num}/{total_batches} ({len(batch_indices)} rows)")
            
            # Create tasks for batch
            batch_tasks = [
                self._process_single_risk_control_row(idx, df.iloc[idx], base_metadata)
                for idx in batch_indices
            ]
            
            try:
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Handle results
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.warning(f"Error in batch processing: {result}")
                        continue
                    if result:  # Only add non-None results
                        documents.append(result)
                        
            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {e}")
                # Fallback: process rows individually
                for idx in batch_indices:
                    try:
                        doc = await self._process_single_risk_control_row(idx, df.iloc[idx], base_metadata)
                        if doc:
                            documents.append(doc)
                    except Exception as row_error:
                        logger.warning(f"Error processing row {idx}: {row_error}")
        
        logger.info(f"Processed {len(documents)} risk control documents from {total_rows} rows")
        return documents
    
    async def _process_soc2_controls_excel(
        self,
        df: pd.DataFrame,
        content: str,
        base_metadata: Dict[str, Any]
    ) -> List[Document]:
        """Process SOC2 controls from Excel DataFrame."""
        # Similar to risk controls but with SOC2 framework
        return await self._process_risk_controls_excel(df, content, {
            **base_metadata,
            "framework": "SOC2"
        })
    
    def _serialize_entities_result(self, entities_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert entities result to JSON-serializable format.
        Handles ContextualEdge objects by converting them to dictionaries.
        
        Args:
            entities_result: Result dictionary from extract_entities_and_create_edges
            
        Returns:
            Serializable dictionary
        """
        from app.services.contextual_graph_storage import ContextualEdge
        
        serializable = {}
        
        # Copy entities as-is (should already be dicts)
        if "entities" in entities_result:
            serializable["entities"] = entities_result["entities"]
        
        # Convert ContextualEdge objects to dicts
        if "edges" in entities_result:
            edges = entities_result["edges"]
            serializable["edges"] = []
            for edge in edges:
                if isinstance(edge, ContextualEdge):
                    # Convert to dict using to_metadata and add document
                    edge_dict = edge.to_metadata()
                    edge_dict["document"] = edge.document
                    serializable["edges"].append(edge_dict)
                elif isinstance(edge, dict):
                    serializable["edges"].append(edge)
                else:
                    # Fallback: convert to string representation
                    serializable["edges"].append(str(edge))
        
        # Copy any other fields
        for key, value in entities_result.items():
            if key not in ["entities", "edges"]:
                serializable[key] = value
        
        return serializable
    
    def _dataframe_to_content(self, df: pd.DataFrame, sheet_name: str) -> str:
        """Convert DataFrame to readable text content."""
        lines = [f"Sheet: {sheet_name}", f"Rows: {len(df)}", f"Columns: {', '.join(df.columns)}", ""]
        
        # Add column descriptions
        for col in df.columns:
            non_null_count = df[col].notna().sum()
            lines.append(f"Column '{col}': {non_null_count} non-null values")
        
        lines.append("")
        lines.append("Data Preview:")
        lines.append(df.head(10).to_string())
        
        return "\n".join(lines)
    
    def _row_to_text(self, row: pd.Series) -> str:
        """Convert a DataFrame row to text description."""
        parts = []
        for col, val in row.items():
            if pd.notna(val) and str(val).strip():
                parts.append(f"{col}: {val}")
        return "\n".join(parts)


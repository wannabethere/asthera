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
        
        # Create base metadata
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
            # For policy documents, split by policy sections from table of contents
            # Replace "Tellius" with "organization" in content (case-insensitive)
            import re
            
            # Combine all pages into full text
            full_text = "\n\n".join([doc.page_content for doc in pdf_documents])
            
            # Replace "Tellius" with "organization" (case-insensitive, whole word)
            # First handle possessive forms: Tellius's -> organization's
            full_text = re.sub(r'\bTellius\'s\b', "organization's", full_text, flags=re.IGNORECASE)
            # Then handle all other occurrences of Tellius
            full_text = re.sub(r'\bTellius\b', 'organization', full_text, flags=re.IGNORECASE)
            
            # Split by policy sections
            policy_sections = self._split_policy_by_sections(full_text, pdf_documents)
            
            # Process each policy section with extraction
            for policy_name, policy_content in policy_sections.items():
                policy_docs = await self._process_policy_section(
                    policy_name=policy_name,
                    policy_content=policy_content,
                    base_metadata=base_metadata
                )
                documents.extend(policy_docs)
            
            logger.info(f"Split policy document into {len(policy_sections)} policy sections, created {len(documents)} documents")
        elif document_type == "soc2_controls":
            # Combine all pages for SOC2 controls (keep existing behavior)
            full_content = "\n\n".join([doc.page_content for doc in pdf_documents])
            docs = await self._process_soc2_controls_document(full_content, base_metadata)
            documents.extend(docs)
        elif document_type == "risk_controls":
            # Combine all pages for risk controls (keep existing behavior)
            full_content = "\n\n".join([doc.page_content for doc in pdf_documents])
            docs = await self._process_risk_controls_document(full_content, base_metadata)
            documents.extend(docs)
        else:
            # Generic processing - combine all pages
            full_content = "\n\n".join([doc.page_content for doc in pdf_documents])
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
        metadata: Optional[Dict] = None,
        ignore_sheets: Optional[List[str]] = None
    ) -> List[Document]:
        """
        Process an Excel document and extract structured information.
        
        Args:
            excel_path: Path to Excel file
            document_type: Type of document ("risk_controls", "soc2_controls")
            sheet_name: Specific sheet to process (None for all sheets)
            domain: Domain filter
            metadata: Additional metadata
            ignore_sheets: List of sheet names to ignore (default: ["Risk Assessment Snapshot", "Risk Overview"])
            
        Returns:
            List of Document objects with extracted information (one per sheet)
        """
        logger.info(f"Processing Excel document: {excel_path}, type: {document_type}")
        
        excel_path = Path(excel_path)
        if not excel_path.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_path}")
        
        # Default ignored sheets
        if ignore_sheets is None:
            ignore_sheets = ["Risk Assessment Snapshot", "Risk Overview"]
        
        # Load Excel
        try:
            excel_file = pd.ExcelFile(str(excel_path))
            all_sheets = [sheet_name] if sheet_name else excel_file.sheet_names
            # Filter out ignored sheets
            sheets_to_process = [s for s in all_sheets if s not in ignore_sheets]
            logger.info(f"Found {len(excel_file.sheet_names)} sheets, processing {len(sheets_to_process)} (ignored: {len(all_sheets) - len(sheets_to_process)})")
        except Exception as e:
            logger.error(f"Error loading Excel: {e}")
            raise
        
        documents = []
        
        for sheet in sheets_to_process:
            try:
                df = pd.read_excel(excel_file, sheet_name=sheet)
                logger.info(f"Loaded sheet '{sheet}': {len(df)} rows, {len(df.columns)} columns")
                
                # Convert DataFrame to structured content - combine all rows for this sheet
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
                
                # Process based on document type - may create multiple documents per sheet (grouped by framework)
                if document_type == "risk_controls":
                    docs = await self._process_risk_controls_sheet(df, content, base_metadata)
                    if docs:
                        documents.extend(docs)
                elif document_type == "soc2_controls":
                    docs = await self._process_soc2_controls_sheet(df, content, base_metadata)
                    if docs:
                        documents.extend(docs)
                else:
                    # Generic processing - one document per sheet
                    doc = Document(
                        page_content=content,
                        metadata=base_metadata
                    )
                    documents.append(doc)
                    
            except Exception as e:
                logger.error(f"Error processing sheet '{sheet}': {e}")
                continue
        
        logger.info(f"Created {len(documents)} documents from Excel (one per sheet)")
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
    
    async def _process_single_risk_section(
        self,
        section: str,
        idx: int,
        base_metadata: Dict[str, Any]
    ) -> Optional[Document]:
        """Process a single risk section from PDF document."""
        try:
            if self.enable_extraction and len(section.strip()) > 200:
                try:
                    control_result = await self.control_extractor.extract_control_from_text(
                        text=section,
                        framework="Risk Management",
                        context_metadata={**base_metadata, "section_index": idx}
                    )
                    
                    if control_result.get("control_id"):
                        control_doc = Document(
                            page_content=json.dumps(control_result, indent=2, default=str),
                            metadata={
                                **base_metadata,
                                "extraction_type": "control",
                                "control_id": control_result.get("control_id"),
                                "framework": "Risk Management",
                                "section_index": idx
                            }
                        )
                        return control_doc
                except Exception as e:
                    logger.debug(f"Error extracting control from section {idx}: {e}")
                    return None
            return None
        except Exception as e:
            logger.warning(f"Error processing section {idx}: {e}")
            return None
    
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
    
    def _detect_framework_column(self, df: pd.DataFrame) -> Optional[str]:
        """
        Detect the column name that contains framework information.
        Looks for common framework column names.
        """
        framework_column_names = [
            "Control Framework", "Framework", "Compliance Framework",
            "Framework Name", "Control Framework Name", "Framework Type"
        ]
        
        # Check for exact matches (case-insensitive)
        for col in df.columns:
            if col in framework_column_names:
                return col
        
        # Check for case-insensitive matches
        df_cols_lower = {col.lower(): col for col in df.columns}
        for framework_name in framework_column_names:
            if framework_name.lower() in df_cols_lower:
                return df_cols_lower[framework_name.lower()]
        
        # Check for partial matches
        for col in df.columns:
            col_lower = col.lower()
            if "framework" in col_lower or "compliance" in col_lower:
                return col
        
        return None
    
    def _extract_framework_from_row(self, row: pd.Series, framework_column: Optional[str] = None) -> str:
        """
        Extract framework name from a row.
        Tries multiple methods:
        1. Direct framework column value
        2. Control ID patterns (CC6.1 = SOC2, PCI-DSS 3.4 = PCI-DSS, etc.)
        3. Framework keywords in row data
        4. Default to "Risk Management"
        """
        import re
        
        # Method 1: Check framework column if provided
        if framework_column and framework_column in row.index:
            framework_value = row[framework_column]
            if pd.notna(framework_value) and str(framework_value).strip():
                return str(framework_value).strip()
        
        # Method 2: Check for framework column in row data
        for col in row.index:
            col_lower = str(col).lower()
            if "framework" in col_lower or "compliance" in col_lower:
                value = row[col]
                if pd.notna(value) and str(value).strip():
                    return str(value).strip()
        
        # Method 3: Check control ID patterns
        for col in row.index:
            value = row[col]
            if pd.notna(value):
                value_str = str(value).upper()
                
                # SOC2 patterns: CC6.1, CC7.2, etc.
                if re.search(r'CC\d+\.\d+', value_str):
                    return "SOC2"
                
                # PCI-DSS patterns: PCI-DSS 3.4, PCI DSS 3.4, etc.
                if re.search(r'PCI[- ]?DSS', value_str, re.IGNORECASE):
                    return "PCI-DSS"
                
                # HIPAA patterns: HIPAA, 164.308, etc.
                if re.search(r'HIPAA|164\.\d+', value_str, re.IGNORECASE):
                    return "HIPAA"
                
                # ISO patterns: ISO 27001, ISO/IEC 27001, etc.
                if re.search(r'ISO[\s/]?IEC?\s*27001', value_str, re.IGNORECASE):
                    return "ISO 27001"
                if re.search(r'ISO\s*27001', value_str, re.IGNORECASE):
                    return "ISO 27001"
                
                # GDPR patterns: GDPR, Article 32, etc.
                if re.search(r'GDPR|Article\s*\d+', value_str, re.IGNORECASE):
                    return "GDPR"
                
                # NIST patterns: NIST 800-53, NIST CSF, etc.
                if re.search(r'NIST\s*(800[- ]?53|CSF)', value_str, re.IGNORECASE):
                    return "NIST"
        
        # Method 4: Check for framework keywords in all row values
        all_text = " ".join([str(v) for v in row.values if pd.notna(v)]).upper()
        
        framework_keywords = {
            "SOC2": ["SOC2", "SOC 2", "TRUST SERVICE CRITERIA", "TSC"],
            "HIPAA": ["HIPAA", "HEALTH INSURANCE PORTABILITY"],
            "PCI-DSS": ["PCI-DSS", "PCI DSS", "PAYMENT CARD INDUSTRY"],
            "ISO 27001": ["ISO 27001", "ISO/IEC 27001"],
            "GDPR": ["GDPR", "GENERAL DATA PROTECTION REGULATION"],
            "NIST": ["NIST", "NATIONAL INSTITUTE OF STANDARDS"]
        }
        
        for framework, keywords in framework_keywords.items():
            if any(keyword in all_text for keyword in keywords):
                return framework
        
        # Default fallback
        return "Risk Management"
    
    async def _process_risk_controls_sheet(
        self,
        df: pd.DataFrame,
        content: str,
        base_metadata: Dict[str, Any],
        batch_size: int = 10
    ) -> List[Document]:
        """
        Process a single sheet and create one document per row.
        Each document will have a framework (SOC2, HIPAA, ISO, etc.) extracted from the row data.
        Processes rows in batches of 10 for improved performance.
        """
        import asyncio
        
        documents = []
        
        try:
            # Detect framework column if it exists
            framework_column = self._detect_framework_column(df)
            
            logger.info(f"Processing sheet '{base_metadata.get('sheet_name')}' - creating one document per row (batch size: {batch_size})")
            if framework_column:
                logger.info(f"Framework column detected: {framework_column}")
            
            total_rows = len(df)
            total_batches = (total_rows + batch_size - 1) // batch_size
            
            # Process rows in batches
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, total_rows)
                batch_indices = list(range(start_idx, end_idx))
                
                logger.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_indices)} rows)")
                
                # Create tasks for batch - process rows concurrently
                batch_tasks = [
                    self._process_single_risk_control_row_from_df(
                        idx=idx,
                        row=df.iloc[idx],
                        framework_column=framework_column,
                        base_metadata=base_metadata
                    )
                    for idx in batch_indices
                ]
                
                try:
                    # Process batch concurrently
                    batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    
                    # Handle results
                    for result in batch_results:
                        if isinstance(result, Exception):
                            logger.warning(f"Error in batch processing: {result}")
                            continue
                        if result:  # Only add non-None results
                            documents.append(result)
                            
                except Exception as e:
                    logger.error(f"Error processing batch {batch_num + 1}: {e}")
                    # Fallback: process rows individually
                    for idx in batch_indices:
                        try:
                            doc = await self._process_single_risk_control_row_from_df(
                                idx=idx,
                                row=df.iloc[idx],
                                framework_column=framework_column,
                                base_metadata=base_metadata
                            )
                            if doc:
                                documents.append(doc)
                        except Exception as row_error:
                            logger.warning(f"Error processing row {idx}: {row_error}")
            
            logger.info(f"Created {len(documents)} document(s) from sheet '{base_metadata.get('sheet_name')}' ({total_rows} rows)")
            return documents
            
        except Exception as e:
            logger.error(f"Error processing sheet '{base_metadata.get('sheet_name')}': {e}")
            # Return a minimal document on error
            return [Document(
                page_content=json.dumps({"error": str(e), "sheet_name": base_metadata.get("sheet_name")}, indent=2),
                metadata={
                    **base_metadata,
                    "extraction_type": "error",
                    "entity_type": "sheet",
                    "framework": "Risk Management"
                }
            )]
    
    async def _process_single_risk_control_row_from_df(
        self,
        idx: int,
        row: pd.Series,
        framework_column: Optional[str],
        base_metadata: Dict[str, Any]
    ) -> Optional[Document]:
        """
        Process a single risk control row from DataFrame.
        This is called in batches for concurrent processing.
        """
        try:
            # Extract framework from this row
            framework = self._extract_framework_from_row(row, framework_column)
            
            # Convert row to dict, removing NaN values
            row_dict = row.to_dict()
            row_dict = {k: v for k, v in row_dict.items() if pd.notna(v)}
            
            # Create content for this row
            row_content = {
                "sheet_name": base_metadata.get("sheet_name", "unknown"),
                "row_index": int(idx),
                "framework": framework,
                "columns": list(row.index),
                "data": row_dict
            }
            
            # Create text content for extraction
            row_text = self._row_to_text(row)
            
            # If extraction is enabled, try to extract control information
            if self.enable_extraction and len(row_text.strip()) > 50:
                try:
                    control_result = await self.control_extractor.extract_control_from_text(
                        text=row_text,
                        framework=framework,
                        context_metadata={**base_metadata, "row_index": int(idx)}
                    )
                    row_content["extracted_control"] = control_result
                    
                    doc = Document(
                        page_content=json.dumps(row_content, indent=2, default=str),
                        metadata={
                            **base_metadata,
                            "extraction_type": "control",
                            "control_id": control_result.get("control_id"),
                            "framework": framework,
                            "entity_type": "row",
                            "row_index": int(idx)
                        }
                    )
                    return doc
                except Exception as e:
                    logger.debug(f"Error extracting control from row {idx}: {e}")
                    # Fall through to create document without extraction
            
            # Create document without extraction or if extraction failed
            doc = Document(
                page_content=json.dumps(row_content, indent=2, default=str),
                metadata={
                    **base_metadata,
                    "extraction_type": "row_data",
                    "framework": framework,
                    "entity_type": "row",
                    "row_index": int(idx)
                }
            )
            return doc
            
        except Exception as row_error:
            logger.warning(f"Error processing row {idx}: {row_error}")
            # Create error document for this row
            error_doc = Document(
                page_content=json.dumps({
                    "error": str(row_error),
                    "sheet_name": base_metadata.get("sheet_name"),
                    "row_index": int(idx),
                    "data": {k: v for k, v in row.to_dict().items() if pd.notna(v)}
                }, indent=2),
                metadata={
                    **base_metadata,
                    "extraction_type": "error",
                    "entity_type": "row",
                    "row_index": int(idx),
                    "framework": "Risk Management"
                }
            )
            return error_doc
    
    async def _process_soc2_controls_sheet(
        self,
        df: pd.DataFrame,
        content: str,
        base_metadata: Dict[str, Any]
    ) -> List[Document]:
        """
        Process a single SOC2 controls sheet, creating separate documents grouped by framework.
        Similar to risk controls but with SOC2 framework.
        """
        # Use risk controls processing but with SOC2 metadata
        base_metadata_soc2 = {
            **base_metadata,
            "framework": "SOC2"
        }
        docs = await self._process_risk_controls_sheet(df, content, base_metadata_soc2)
        
        # Update metadata to reflect SOC2 for all documents
        for doc in docs:
            # Update framework in metadata (but preserve framework from grouping if it exists)
            if "framework" not in doc.metadata or doc.metadata.get("entity_type") == "sheet":
                doc.metadata["framework"] = "SOC2"
            
            # Try to update the framework in the extracted control if possible
            if "extracted_control" in doc.page_content:
                try:
                    content_dict = json.loads(doc.page_content)
                    if "extracted_control" in content_dict and isinstance(content_dict["extracted_control"], dict):
                        # Only override if framework wasn't already set from grouping
                        if "framework" not in content_dict["extracted_control"]:
                            content_dict["extracted_control"]["framework"] = "SOC2"
                    doc.page_content = json.dumps(content_dict, indent=2, default=str)
                except:
                    pass
        
        return docs
    
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
    
    def _dataframe_to_content(self, df: pd.DataFrame, sheet_name: str, include_all_rows: bool = True) -> str:
        """Convert DataFrame to readable text content."""
        lines = [f"Sheet: {sheet_name}", f"Rows: {len(df)}", f"Columns: {', '.join(df.columns)}", ""]
        
        # Add column descriptions
        for col in df.columns:
            non_null_count = df[col].notna().sum()
            lines.append(f"Column '{col}': {non_null_count} non-null values")
        
        lines.append("")
        if include_all_rows and len(df) > 0:
            lines.append("All Data:")
            # Include all rows for better extraction
            lines.append(df.to_string())
        else:
            lines.append("Data Preview:")
            lines.append(df.head(10).to_string())
        
        return "\n".join(lines)
    
    def _split_policy_by_sections(
        self,
        full_text: str,
        pdf_documents: List[Document]
    ) -> Dict[str, str]:
        """
        Split policy document by sections based on table of contents.
        
        Detects policy sections from common patterns:
        - Policy names in table of contents
        - Section headers in the document
        
        Returns:
            Dictionary mapping policy name to policy content
        """
        import re
        
        # List of known policy names (from table of contents)
        policy_names = [
            "Access Control Policy",
            "Asset Management Policy",
            "Business Continuity and Disaster Recovery Plan",
            "Code of Conduct",
            "Cryptography Policy",
            "Data Management Policy",
            "Human Resource Security Policy",
            "Incident Response Plan",
            "Information Security Policy (AUP)",
            "Information Security Roles and Responsibilities",
            "Operations Security Policy",
            "Physical Security Policy",
            "Risk Management Policy",
            "Secure Development Policy",
            "Third-Party Management Policy"
        ]
        
        # Create patterns to match policy headers
        # Match patterns like "Access Control Policy", "1. Access Control Policy", etc.
        # Also handle variations like "Access Control Policy 12" (with page numbers)
        policy_patterns = {}
        for policy_name in policy_names:
            # Escape special regex characters
            escaped_name = re.escape(policy_name)
            # Match policy name at start of line, possibly with number prefix or page number suffix
            # Pattern: optional leading number/dot/space, policy name, optional page number, end of line or colon
            pattern = re.compile(
                r'^[\d\.\s]*' + escaped_name + r'(?:\s+\d+)?(?:\s|$|:|\n)',
                re.MULTILINE | re.IGNORECASE
            )
            policy_patterns[policy_name] = pattern
        
        # Find all policy section boundaries
        section_boundaries = []
        for policy_name, pattern in policy_patterns.items():
            for match in pattern.finditer(full_text):
                section_boundaries.append((match.start(), policy_name))
        
        # Remove duplicates (keep first occurrence)
        seen = set()
        unique_boundaries = []
        for pos, name in section_boundaries:
            if (pos, name) not in seen:
                seen.add((pos, name))
                unique_boundaries.append((pos, name))
        
        # Sort by position
        unique_boundaries.sort(key=lambda x: x[0])
        
        # If no sections found, try a more lenient approach
        if not unique_boundaries:
            logger.warning("No policy sections detected with strict patterns, trying lenient matching")
            # Try matching just the policy name without strict formatting
            for policy_name in policy_names:
                # Simple pattern: policy name as a phrase
                simple_pattern = re.compile(
                    r'\b' + re.escape(policy_name) + r'\b',
                    re.IGNORECASE
                )
                matches = list(simple_pattern.finditer(full_text))
                if matches:
                    # Use first match as section start
                    unique_boundaries.append((matches[0].start(), policy_name))
            
            unique_boundaries.sort(key=lambda x: x[0])
        
        # If still no sections found, return full text as single section
        if not unique_boundaries:
            logger.warning("No policy sections detected, treating as single document")
            return {"Full Policy Document": full_text}
        
        # Extract sections
        policy_sections = {}
        for i, (start_pos, policy_name) in enumerate(unique_boundaries):
            # Find end position (start of next section or end of document)
            if i + 1 < len(unique_boundaries):
                end_pos = unique_boundaries[i + 1][0]
            else:
                end_pos = len(full_text)
            
            # Extract section content
            section_content = full_text[start_pos:end_pos].strip()
            
            # Skip if section is too short (likely false positive)
            if len(section_content) < 100:
                continue
            
            # Store section (handle duplicates by appending number)
            if policy_name in policy_sections:
                policy_sections[f"{policy_name} (Section {i+1})"] = section_content
            else:
                policy_sections[policy_name] = section_content
        
        logger.info(f"Detected {len(policy_sections)} policy sections: {list(policy_sections.keys())}")
        return policy_sections
    
    async def _process_policy_section(
        self,
        policy_name: str,
        policy_content: str,
        base_metadata: Dict[str, Any]
    ) -> List[Document]:
        """
        Process a single policy section and extract different types.
        
        For each policy section, extracts:
        - context (domain_knowledge)
        - entities
        - evidence
        - fields
        - controls
        - full_content (domain_knowledge)
        
        Returns:
            List of documents, one for each extraction type
        """
        documents = []
        
        # Create policy-specific metadata
        policy_metadata = {
            **base_metadata,
            "policy_name": policy_name,
            "policy_section": policy_name
        }
        
        # Extract context (domain_knowledge)
        if self.enable_extraction:
            try:
                context_def = await self.context_extractor.extract_context_from_description(
                    description=policy_content[:5000],  # Limit for context extraction
                    context_id=f"policy_{policy_name}_{base_metadata.get('file_name', 'unknown')}"
                )
                
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
                        **policy_metadata,
                        "extraction_type": "context",
                        "context_id": context_def.context_id
                    }
                )
                documents.append(context_doc)
            except Exception as e:
                logger.warning(f"Error extracting context for {policy_name}: {e}")
        
        # Extract entities
        if self.enable_extraction:
            try:
                entities_result = await self.entities_extractor.extract_entities_and_create_edges(
                    text=policy_content,
                    context_id=f"policy_{policy_name}_{base_metadata.get('file_name', 'unknown')}",
                    entity_types=["policy", "requirement", "control", "procedure"]
                )
                
                if entities_result.get("entities"):
                    serializable_result = self._serialize_entities_result(entities_result)
                    
                    entities_doc = Document(
                        page_content=json.dumps(serializable_result, indent=2, default=str),
                        metadata={
                            **policy_metadata,
                            "extraction_type": "entities",
                            "entity_count": len(entities_result.get("entities", []))
                        }
                    )
                    documents.append(entities_doc)
            except Exception as e:
                logger.warning(f"Error extracting entities for {policy_name}: {e}")
        
        # Extract evidence
        if self.enable_extraction:
            try:
                # Use evidence extractor to create evidence documents
                # Extract potential evidence mentions from policy content
                # Look for common evidence patterns (e.g., "logs", "reports", "documentation")
                evidence_keywords = ["log", "report", "documentation", "evidence", "record", "audit", "monitoring"]
                found_evidence = []
                for keyword in evidence_keywords:
                    if keyword.lower() in policy_content.lower():
                        try:
                            evidence_doc_content = await self.evidence_extractor.create_evidence_edge_document(
                                evidence_name=f"{keyword.title()} Evidence",
                                requirement_id=None,
                                context_metadata=policy_metadata
                            )
                            if evidence_doc_content and evidence_doc_content.strip():
                                found_evidence.append({
                                    "evidence_name": f"{keyword.title()} Evidence",
                                    "content": evidence_doc_content
                                })
                        except Exception as ev_error:
                            logger.debug(f"Error creating evidence document for {keyword}: {ev_error}")
                            continue
                
                if found_evidence:
                    evidence_doc = Document(
                        page_content=json.dumps(found_evidence, indent=2, default=str),
                        metadata={
                            **policy_metadata,
                            "extraction_type": "evidence",
                            "evidence_count": len(found_evidence)
                        }
                    )
                    documents.append(evidence_doc)
            except Exception as e:
                logger.warning(f"Error extracting evidence for {policy_name}: {e}")
        
        # Extract fields
        if self.enable_extraction:
            try:
                fields_result = await self.fields_extractor.extract_fields_and_create_edges(
                    text=policy_content,
                    context_id=f"policy_{policy_name}_{base_metadata.get('file_name', 'unknown')}",
                    context_metadata=policy_metadata
                )
                
                if fields_result and (fields_result.get("extracted_fields") or fields_result.get("edges")):
                    fields_doc = Document(
                        page_content=json.dumps(fields_result, indent=2, default=str),
                        metadata={
                            **policy_metadata,
                            "extraction_type": "fields",
                            "fields_count": len(fields_result.get("extracted_fields", [])),
                            "edges_count": len(fields_result.get("edges", []))
                        }
                    )
                    documents.append(fields_doc)
            except Exception as e:
                logger.warning(f"Error extracting fields for {policy_name}: {e}")
        
        # Extract controls
        if self.enable_extraction:
            try:
                # Try to extract controls from policy content
                control_result = await self.control_extractor.extract_control_from_text(
                    text=policy_content,
                    framework=base_metadata.get("framework", "Policy"),
                    context_metadata=policy_metadata
                )
                
                if control_result and control_result.get("control_id"):
                    control_doc = Document(
                        page_content=json.dumps(control_result, indent=2, default=str),
                        metadata={
                            **policy_metadata,
                            "extraction_type": "control",
                            "control_id": control_result.get("control_id")
                        }
                    )
                    documents.append(control_doc)
            except Exception as e:
                logger.warning(f"Error extracting controls for {policy_name}: {e}")
        
        # Extract requirements
        if self.enable_extraction:
            try:
                # Split content into sections for requirement extraction
                sections = policy_content.split("\n\n")
                for i, section in enumerate(sections[:10]):  # Limit to first 10 sections
                    if len(section.strip()) > 100:  # Only process substantial sections
                        try:
                            req_doc_content = await self.requirement_extractor.create_requirement_edge_document(
                                requirement_text=section,
                                control_id=None,
                                context_metadata=policy_metadata
                            )
                            
                            if req_doc_content and req_doc_content.strip():
                                req_doc = Document(
                                    page_content=req_doc_content,
                                    metadata={
                                        **policy_metadata,
                                        "extraction_type": "requirement",
                                        "section_index": i
                                    }
                                )
                                documents.append(req_doc)
                        except Exception as section_error:
                            logger.debug(f"Error extracting requirement from section {i} of {policy_name}: {section_error}")
                            continue
            except Exception as e:
                logger.warning(f"Error extracting requirements for {policy_name}: {e}")
        
        # Add full content document (domain_knowledge)
        full_doc = Document(
            page_content=policy_content,
            metadata={
                **policy_metadata,
                "extraction_type": "full_content"
            }
        )
        documents.append(full_doc)
        
        logger.info(f"Processed policy section '{policy_name}': created {len(documents)} documents")
        return documents
    
    def _row_to_text(self, row: pd.Series) -> str:
        """Convert a DataFrame row to text description."""
        parts = []
        for col, val in row.items():
            if pd.notna(val) and str(val).strip():
                parts.append(f"{col}: {val}")
        return "\n".join(parts)


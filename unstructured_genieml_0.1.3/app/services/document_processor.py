import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from langchain_core.language_models.llms import BaseLLM
from langchain_core.language_models.chat_models import BaseChatModel
from typing import Union
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

from app.config.settings import get_settings
from ingestions.doc_extraction import PDFExtractor, InsightExtractor, DocumentInsightPipeline
from ingestions.doc_insight_extraction import QuestionBasedProcessor, DocumentChunk
from app.models.dbmodels import DocumentInsight
from app.services.database.dbservice import DatabaseService
from app.utils.chromadb import ChromaDB


class DocumentProcessor:
    def __init__(self, 
                 llm: Optional[Union[BaseLLM, ChatOpenAI]] = None,
                 use_chromadb: bool = False):
        self.settings = get_settings()
        self.llm = llm or ChatOpenAI(
            temperature=self.settings.TEMPERATURE,
            model=self.settings.OPENAI_MODEL,
            api_key=SecretStr(self.settings.OPENAI_API_KEY)
        )
        self.use_chromadb = use_chromadb
        
        # Initialize classes from document extraction modules
        self.pdf_extractor = PDFExtractor(self.llm)
        self.insight_extractor = InsightExtractor(self.llm)
        self.doc_pipeline = DocumentInsightPipeline(
            llm=self.llm,
            chroma_collection="documents"
        )
        
        # Initialize question-based processor from doc_insight_extraction
        self.question_processor = QuestionBasedProcessor(
            model_name=self.settings.OPENAI_MODEL, 
            questions_collection="extraction_questions"
        )
        
        self.db_service = DatabaseService()
        
        # Set up embeddings for ChromaDB
        if self.use_chromadb:
            self.embeddings = OpenAIEmbeddings(
                api_key=SecretStr(self.settings.OPENAI_API_KEY)
            )
            # Create ChromaDB HTTP client that connects to server
            self.chroma_db = ChromaDB(
                connection_params={
                    "host": self.settings.CHROMA_HOST,
                    "port": self.settings.CHROMA_PORT,
                }
            )
            print(f"Using ChromaDB server at {self.settings.CHROMA_HOST}:{self.settings.CHROMA_PORT}")
            
            # Ensure extraction_questions collection exists
            try:
                # Check if we can access the extraction_questions collection
                self.chroma_db.get_collection("extraction_questions")
                print(f"[DOCUMENT_PROCESSOR] Successfully connected to extraction_questions collection")
            except Exception as e:
                print(f"[DOCUMENT_PROCESSOR] Warning: Could not access extraction_questions collection: {e}")
                print(f"[DOCUMENT_PROCESSOR] Make sure to run embed_questions_to_chromadb.py to create and populate the collection")

    def store_in_chromadb(self, content: str, metadata: Dict, doc_id: str, insights: Optional[Dict] = None) -> List[str]:
        """Store document content and insights in ChromaDB after splitting into chunks"""
        if not self.use_chromadb:
            return []
            
        try:
            # Use the document pipeline's storage instead of reimplementing
            # First create a DocumentInsight object
            doc_insight = DocumentInsight(
                id=str(metadata.get("insight_id", "")),
                document_id=doc_id,
                phrases=insights.get("phrases", []) if insights else [],
                insight=insights.get("insight", {}) if insights else {},
                source_type=metadata.get("source_type", ""),
                document_type=metadata.get("document_type", ""),
                extracted_entities=insights.get("extracted_entities", {}) if insights else {},
                ner_text=insights.get("ner_text", "") if insights else "",
                event_timestamp=datetime.now().isoformat(),
                chromadb_ids=[],
                event_type=metadata.get("event_type", ""),
                created_by=metadata.get("created_by", ""),
                enhanced_insights=insights.get("enhanced_insights", None) if insights else None
            )
            
            # Store using the pipeline's storage
            result = self.doc_pipeline.storage.store_document_insight(doc_insight)
            
            # The result might be a DocumentInsight or a list of IDs, handle both cases
            if isinstance(result, DocumentInsight) and hasattr(result, 'chromadb_ids'):
                return result.chromadb_ids
            elif isinstance(result, list):
                return result
            else:
                print(f"[DOCUMENT_PROCESSOR] Warning: Unexpected result type from store_document_insight: {type(result)}")
                return []
            
        except Exception as e:
            print(f"Error storing document in ChromaDB: {e}")
            import traceback
            traceback.print_exc()
            return []

    def process_jsonl_file(self, 
                           jsonl_path: str,
                           source_type: str,
                           document_type: str,
                           event_type: str,
                           created_by: str) -> List[DocumentInsight]:
        """Process a JSONL file containing document data"""
        print(f"Loading JSONL from: {jsonl_path}")
        
        insights = []
        
        try:
            with open(jsonl_path, 'r') as file:
                for line in file:
                    if not line.strip():
                        continue
                    
                    json_data = json.loads(line)
                    doc_insight = self.process_json_record(
                        json_data=json_data,
                        source_type=source_type,
                        document_type=document_type,
                        event_type=event_type,
                        created_by=created_by
                    )
                    
                    if doc_insight:
                        insights.append(doc_insight)
            
            print(f"Processed {len(insights)} documents from JSONL file")
            return insights
        
        except Exception as e:
            print(f"Error processing JSONL file: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def process_json_record(self,
                            json_data: Dict[str, Any],
                            source_type: str,
                            document_type: str,
                            event_type: str,
                            created_by: str,
                            test_mode: bool = False,
                            user_context: Optional[str] = None) -> Optional[DocumentInsight]:
        """
        Process a single JSON record and extract insights
        
        Args:
            json_data: JSON data containing document content
            source_type: Source type of the document
            document_type: Type of document
            event_type: Type of event
            created_by: User or system that created the document
            test_mode: If True, no data will be written to databases
            user_context: Optional user-provided context to guide extraction
        """
        try:
            print(f"[DOCUMENT_PROCESSOR] {'TEST MODE' if test_mode else 'NORMAL MODE'} - Starting document processing")
            if user_context:
                print(f"[DOCUMENT_PROCESSOR] User context provided: {user_context[:100]}{'...' if len(user_context) > 100 else ''}")
            
            # Check if content is directly at top level or nested in "document" field
            content = ""
            if "document" in json_data and isinstance(json_data["document"], dict):
                content = json_data["document"].get("content", "")
                print(f"[DOCUMENT_PROCESSOR] Found content in document field: {len(content)} chars")
            else:
                content = json_data.get("content", "")
                print(f"[DOCUMENT_PROCESSOR] Found content in top level: {len(content)} chars")
            
            if not content:
                print("[DOCUMENT_PROCESSOR] Empty content in JSON record, skipping")
                return None
                
            # Metadata from the JSON record
            metadata = {
                "document_key": json_data.get("document_key", ""),
                "source_file_last_modified": json_data.get("_ab_source_file_last_modified", ""),
                "source_file_url": json_data.get("_ab_source_file_url", ""),
                "processing_time": datetime.now().isoformat(),
                "source_type": source_type,
                "document_type": document_type,
                "user_context": user_context
            }
            
            # If nested document structure exists, merge any metadata from it
            if "document" in json_data and isinstance(json_data["document"], dict) and "metadata" in json_data["document"]:
                doc_metadata = json_data["document"].get("metadata", {})
                metadata.update(doc_metadata)
                print(f"[DOCUMENT_PROCESSOR] Merged metadata from document field")
            
            # If in test mode, we'll still process but skip database writes
            if test_mode:
                print(f"[DOCUMENT_PROCESSOR] TEST MODE: Processing document without database writes")
                doc_id = "test-" + str(uuid.uuid4())
                print(f"[DOCUMENT_PROCESSOR] Generated test document ID: {doc_id}")
            else:
                # First save the document to get the ID
                print(f"[DOCUMENT_PROCESSOR] Storing document in database")
                doc_id = self.db_service.store_document(
                    content=content,
                    metadata=metadata,
                    created_by=created_by or "system",
                    source_type=source_type,
                    document_type=document_type
                )
                print(f"[DOCUMENT_PROCESSOR] Stored document with ID: {doc_id}")
            
            # Use the document pipeline for extraction
            try:
                # Create a document structure with the document_id that we either got from the database
                # or created as a test ID
                prepared_json = {
                    "document": {
                        "id": doc_id,
                        "content": content,
                        "metadata": metadata
                    }
                }
                
                # First process the document using the pipeline without storing in ChromaDB
                # by not passing enhanced_insights (which will skip ChromaDB storage)
                print(f"[DOCUMENT_PROCESSOR] Calling doc_pipeline.process_json with test_mode={test_mode}")
                doc_insight = self.doc_pipeline.process_json(
                    json_data=prepared_json,
                    source_type=source_type,
                    document_type=document_type,
                    event_type=event_type,
                    created_by=created_by,
                    test_mode=test_mode,
                    user_context=user_context
                )
                
                # Perform enhanced question-based processing before storage
                enhanced_results = None
                if doc_insight:
                    print(f"[DOCUMENT_PROCESSOR] Document basic processing successful - Document ID: {doc_insight.document_id}")
                    
                    try:
                        print(f"[DOCUMENT_PROCESSOR] Starting enhanced question-based processing")
                        # Process with QuestionBasedProcessor for enhanced insights
                        chunks = [
                            DocumentChunk(
                                chunk_id=f"{doc_id}-chunk-0",
                                content=content[:8000],  # Truncate if too long
                                metadata=metadata
                            )
                        ]
                        
                        # Use ChromaDB to retrieve relevant questions
                        print(f"[DOCUMENT_PROCESSOR] Using ChromaDB to retrieve relevant questions for document type: {document_type}")
                        
                        # Process with the question processor - not passing explicit questions
                        # so it will use ChromaDB to find relevant questions automatically
                        enhanced_results = self.question_processor.process_multiple_questions(
                            chunks=chunks,
                            document_type=document_type,
                            use_chromadb=True
                        )
                        
                        print(f"[DOCUMENT_PROCESSOR] Successfully generated enhanced insights with question-based processing")
                        
                        # Store the enhanced insights in a separate collection
                        if not test_mode:
                            # The QuestionBasedProcessor no longer has store_insights method
                            # Just log the enhanced results without storing them separately
                            print(f"[DOCUMENT_PROCESSOR] Enhanced insights generated but not stored separately (functionality removed)")
                            if enhanced_results:
                                print(f"[DOCUMENT_PROCESSOR] Generated insights for {len(enhanced_results)} questions")
                        else:
                            print(f"[DOCUMENT_PROCESSOR] Test mode: skipped storing insights")
                        
                        # Note: enhanced insights are only included in the document processing
                        print(f"[DOCUMENT_PROCESSOR] Enhanced insights included in document processing only")
                    except Exception as e:
                        # Enhanced processing failed but we still have the basic doc_insight
                        print(f"[DOCUMENT_PROCESSOR] Enhanced question-based processing failed: {e}")
                        print("[DOCUMENT_PROCESSOR] Continuing with basic insights only")
                
                # Now that we have all insights including enhanced insights,
                # process again to store everything at once in ChromaDB
                if not test_mode and self.use_chromadb and doc_insight:
                    print(f"[DOCUMENT_PROCESSOR] Storing document in ChromaDB (enhanced insights stored separately in 'insights' collection)")
                    # Process again with the complete set of insights
                    doc_insight = self.doc_pipeline.process_json(
                        json_data=prepared_json,
                        source_type=source_type,
                        document_type=document_type,
                        event_type=event_type,
                        created_by=created_by,
                        test_mode=test_mode,
                        user_context=user_context,
                        enhanced_insights=enhanced_results  # Pass the enhanced insights
                    )
                    print(f"[DOCUMENT_PROCESSOR] ChromaDB storage complete")
                
                print(f"[DOCUMENT_PROCESSOR] {'TEST MODE' if test_mode else 'NORMAL MODE'} - Document processing completed successfully")
                return doc_insight
            except Exception as e:
                print(f"[DOCUMENT_PROCESSOR] Error in document extraction processing: {e}")
                import traceback
                traceback.print_exc()
                
                # If extraction fails completely, return None
                return None
                
        except Exception as e:
            print(f"[DOCUMENT_PROCESSOR] Error processing JSON record: {e}")
            import traceback
            traceback.print_exc()
            return None
            
    def process_json(self,
                    json_data: Dict[str, Any],
                    source_type: str,
                    document_type: str,
                    event_type: str,
                    created_by: str) -> DocumentInsight:
        """Process JSON data and extract insights"""
        # Use DocumentInsightPipeline directly
        try:
            result = self.doc_pipeline.process_json(
                json_data=json_data,
                source_type=source_type,
                document_type=document_type,
                event_type=event_type,
                created_by=created_by
            )
            return result
        except Exception as e:
            print(f"Error in DocumentInsightPipeline.process_json: {e}")
            # Fallback to process_json_record
            result = self.process_json_record(
                json_data=json_data,
                source_type=source_type,
                document_type=document_type,
                event_type=event_type,
                created_by=created_by
            )
            
            if result is None:
                # Use default insights for fallback
                fallback_json = {
                    "document": {
                        "content": "Empty or invalid JSON content",
                        "metadata": {
                            "source": "json_fallback",
                            "processing_time": datetime.now().isoformat()
                        }
                    },
                    "extraction": {
                        "phrases": ["Unknown", "Invalid data"],
                        "insight": {"main_topic": "Unknown", "purpose": "Unknown"},
                        "extracted_entities": {"organizations": [], "concepts": []},
                        "ner_text": "No valid content available for entity extraction"
                    }
                }
                
                result = self.insight_extractor.extract_from_json(
                    json_data=fallback_json,
                    source_type=source_type,
                    document_type=document_type,
                    event_type=event_type,
                    created_by=created_by
                )
            
            return result

    def process_pdf(self, 
                   pdf_path: str,
                   source_type: str,
                   document_type: str,
                   event_type: str,
                   created_by: str) -> DocumentInsight:
        """Process a PDF document and extract insights using PDFExtractor"""
        # Check if the PDF has a corresponding JSON entry
        pdf_filename = Path(pdf_path).name
        jsonl_path = Path(pdf_path).parent / "airbyte_json_pdf_files.jsonl"
        
        if jsonl_path.exists():
            print(f"Found JSONL file for PDF: {jsonl_path}")
            try:
                with open(jsonl_path, 'r') as file:
                    for line in file:
                        if not line.strip():
                            continue
                        
                        json_data = json.loads(line)
                        if json_data.get("document_key") == pdf_filename or json_data.get("_ab_source_file_url") == pdf_filename:
                            print(f"Found JSON record for PDF: {pdf_filename}")
                            result = self.process_json_record(
                                json_data=json_data,
                                source_type=source_type,
                                document_type=document_type,
                                event_type=event_type,
                                created_by=created_by
                            )
                            if result is not None:
                                return result
            except Exception as e:
                print(f"Error finding JSON for PDF: {str(e)}")
        
        # Use PDFExtractor from doc_extraction.py for direct PDF processing
        try:
            # Use DocumentInsightPipeline to process the PDF directly
            doc_insight = self.doc_pipeline.process_pdf(
                pdf_path=pdf_path,
                source_type=source_type,
                document_type=document_type,
                event_type=event_type,
                created_by=created_by
            )
            
            return doc_insight
            
        except Exception as e:
            print(f"Error processing PDF with DocumentInsightPipeline: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback to simpler extraction
            # First extract document using PDFExtractor
            document = self.pdf_extractor.extract_document(pdf_path)
            
            # Then extract insights using InsightExtractor
            doc_insight = self.insight_extractor.extract_from_document(
                document=document,
                source_type=source_type,
                document_type=document_type,
                event_type=event_type,
                created_by=created_by
            )
            
            # Save to database
            self.db_service.add_document_insight(
                document_id=doc_insight.document_id,
                phrases=doc_insight.phrases,
                insight=doc_insight.insight,
                extracted_entities=doc_insight.extracted_entities,
                ner_text=doc_insight.ner_text,
                chromadb_ids=getattr(doc_insight, 'chromadb_ids', []),  # Use getattr with default empty list
                event_type=event_type,
                created_by=created_by,
                source_type=source_type,
                document_type=document_type
            )
            
            return doc_insight 
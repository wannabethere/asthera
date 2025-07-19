import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

# External libraries
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from langchain.schema import Document as LangchainDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.language_models.llms import BaseLLM
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.models.dbmodels import Document, DocumentInsight
from app.services.vectorstore.documentstore import DocumentChromaStore


class InsightExtractionSchema(BaseModel):
    """Schema for extracting insights from documents"""
    phrases: List[str] = Field(description="Key phrases or quotes from the document")
    insight: Dict = Field(description="Key insights from the document content")
    extracted_entities: Dict = Field(description="Named entities extracted from the document")
    ner_text: str = Field(description="Text describing the named entities")


class PDFExtractor:
    def __init__(self, llm: Union[BaseLLM, ChatOpenAI]):
        self.llm = llm
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=200
        )
        
    def extract_text_from_pdf(self, pdf_path: str) -> List[LangchainDocument]:
        """Extract text from PDF file"""
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        return self.text_splitter.split_documents(documents)
    
    def extract_document(self, pdf_path: str) -> Document:
        """Extract a Document object from a PDF file"""
        docs = self.extract_text_from_pdf(pdf_path)
        content = " ".join([doc.page_content for doc in docs])
        
        # Generate basic metadata
        metadata = {
            "source": pdf_path,
            "page_count": len(docs),
            "extraction_time": datetime.now().isoformat(),
        }
        
        return Document(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            version=1,
            content=content,
            json_metadata=metadata,
            source_type="upload",
            document_type="financial_report",
            created_at=datetime.now()
        )


class InsightExtractor:
    def __init__(self, llm: Union[BaseLLM, ChatOpenAI]):
        self.llm = llm
        self.setup_extraction_chain()
        
    def setup_extraction_chain(self):
        """Set up the LangChain for extraction using modern RunnableSequence approach"""
        self.parser = PydanticOutputParser(pydantic_object=InsightExtractionSchema)
        
        prompt_template = """
        You are an expert document analyzer. Extract key information from the following document text.
        
        Document content:
        {document_content}
        
        Extract the following information:
        1. Key phrases or important quotes
        2. Main insights from the document
        3. Named entities (people, organizations, locations, etc.)
        4. A brief summary of the named entities found

        IMPORTANT: Do NOT wrap your response in backticks (```) or markdown code blocks. Return a plain JSON object directly.
        
        {format_instructions}
        """
        
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["document_content"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        # Create a RunnableSequence instead of LLMChain
        self.extraction_chain = prompt | self.llm | self.parser
        
    def extract_from_document(self, document: Document, 
                              source_type: str, 
                              document_type: str,
                              event_type: str,
                              created_by: str) -> DocumentInsight:
        """Extract insights from a document and create DocumentInsight object"""
        # Process the document content with LLM
        parsed_output = self.extraction_chain.invoke({"document_content": document.content[:8000]})  # Truncate if too long
        
        # Create DocumentInsight
        return DocumentInsight(
            id=str(uuid.uuid4()),
            document_id=str(document.id),
            phrases=parsed_output.phrases,
            insight=parsed_output.insight,
            source_type=source_type,
            document_type=document_type,
            extracted_entities=parsed_output.extracted_entities,
            ner_text=parsed_output.ner_text,
            event_timestamp=datetime.now().isoformat(),
            chromadb_ids=[],  # Will be populated after storing in ChromaDB
            event_type=event_type,
            created_by=created_by,
            document=document
        )
    
    def extract_from_json(self, json_data: Dict, 
                         source_type: str, 
                         document_type: str,
                         event_type: str,
                         created_by: str) -> DocumentInsight:
        """Extract insights from JSON data and create DocumentInsight object"""
        print(f"[EXTRACT_FROM_JSON] Begin extraction process for {source_type}/{document_type}")
        
        # For the second extraction method where we already have JSON data
        document = None
        if "document" in json_data:
            print(f"[EXTRACT_FROM_JSON] Document data found in JSON")
            doc_data = json_data["document"]
            # Handle test mode IDs that start with "test-"
            doc_id = doc_data.get("id", str(uuid.uuid4()))
            print(f"[EXTRACT_FROM_JSON] Document ID from input: {doc_id}")
            
            # For Document class, we need an actual UUID object
            if isinstance(doc_id, str) and doc_id.startswith("test-"):
                print(f"[EXTRACT_FROM_JSON] Test mode ID detected: {doc_id}")
                # For test mode, create a valid UUID
                document_id = uuid.uuid4()
                # We'll store the test ID in metadata
                test_id = doc_id
                print(f"[EXTRACT_FROM_JSON] Created valid UUID for test mode: {document_id}")
            else:
                try:
                    document_id = uuid.UUID(doc_id)
                    test_id = None
                    print(f"[EXTRACT_FROM_JSON] Using provided UUID: {document_id}")
                except ValueError:
                    # If invalid UUID format, generate a new one
                    document_id = uuid.uuid4()
                    test_id = None
                    print(f"[EXTRACT_FROM_JSON] Invalid UUID format, generated new one: {document_id}")
                
            # Prepare metadata with test ID if applicable
            metadata = doc_data.get("metadata", {})
            if test_id:
                metadata["test_id"] = test_id
                print(f"[EXTRACT_FROM_JSON] Added test_id to metadata: {test_id}")
                
            document = Document(
                id=document_id,
                document_id=uuid.uuid4(),
                version=1,
                content=doc_data.get("content", ""),
                json_metadata=metadata,
                source_type="api",
                document_type="json",
                created_at=datetime.now()
            )
            print(f"[EXTRACT_FROM_JSON] Created Document object with ID: {document.id}")
            
        # Process or use existing extraction data
        if "extraction" in json_data:
            print(f"[EXTRACT_FROM_JSON] Using extraction data from JSON")
            extraction = json_data["extraction"]
            phrases = extraction.get("phrases", [])
            insight = extraction.get("insight", {})
            extracted_entities = extraction.get("extracted_entities", {})
            ner_text = extraction.get("ner_text", "")
        else:
            # Need to extract from document content
            if document and document.content:
                print(f"[EXTRACT_FROM_JSON] Extracting insights from document content ({len(document.content)} chars)")
                parsed_output = self.extraction_chain.invoke({"document_content": document.content[:8000]})
                print(f"[EXTRACT_FROM_JSON] LLM extraction completed")
                phrases = parsed_output.phrases
                insight = parsed_output.insight
                extracted_entities = parsed_output.extracted_entities
                ner_text = parsed_output.ner_text
                print(f"[EXTRACT_FROM_JSON] Parsed extraction output successfully")
            else:
                print(f"[EXTRACT_FROM_JSON] No document content available, using empty values")
                phrases = []
                insight = {}
                extracted_entities = {}
                ner_text = ""
        
        # Create DocumentInsight
        # Handle test mode ID
        insight_id = json_data.get("id", str(uuid.uuid4()))
        print(f"[EXTRACT_FROM_JSON] Using insight ID: {insight_id}")
        
        # Determine the document_id
        if document:
            # If we have a document, use its ID, but check for test_id in metadata
            if document.json_metadata and "test_id" in document.json_metadata:
                doc_id = document.json_metadata["test_id"]
                print(f"[EXTRACT_FROM_JSON] Using test_id from metadata as document_id: {doc_id}")
            else:
                doc_id = str(document.id)
                print(f"[EXTRACT_FROM_JSON] Using document.id as document_id: {doc_id}")
        else:
            # Otherwise use the document_id from JSON or generate one
            doc_id = json_data.get("document_id", str(uuid.uuid4()))
            print(f"[EXTRACT_FROM_JSON] Using document_id from JSON: {doc_id}")
        
        print(f"[EXTRACT_FROM_JSON] Creating DocumentInsight with id={insight_id}, document_id={doc_id}")
        doc_insight = DocumentInsight(
            id=insight_id,
            document_id=doc_id,
            phrases=phrases,
            insight=insight,
            source_type=source_type,
            document_type=document_type,
            extracted_entities=extracted_entities,
            ner_text=ner_text,
            event_timestamp=json_data.get("event_timestamp", datetime.now().isoformat()),
            chromadb_ids=json_data.get("chromadb_ids", []),
            event_type=event_type,
            created_by=created_by,
            document=document
        )
        print(f"[EXTRACT_FROM_JSON] DocumentInsight created successfully")
        return doc_insight


class DocumentInsightPipeline:
    """Main pipeline for processing documents and extracting insights"""
    
    def __init__(self, 
                 llm: Optional[Union[BaseLLM, ChatOpenAI]] = None,
                 chroma_collection: str = "generic"):
        
        # Initialize LLM if not provided
        self.llm = llm or ChatOpenAI(temperature=0, model="gpt-4o")
        
        # Initialize components
        self.pdf_extractor = PDFExtractor(self.llm)
        self.extractor = InsightExtractor(self.llm)
        self.storage = DocumentChromaStore(
            collection_name=chroma_collection
        )
    
    def process_pdf(self, 
                    pdf_path: str,
                    source_type: str,
                    document_type: str,
                    event_type: str,
                    created_by: str,
                    test_mode: bool = False) -> DocumentInsight:
        """
        Process a PDF document and extract insights
        
        Args:
            pdf_path: Path to the PDF file
            source_type: Source type of the document
            document_type: Type of document
            event_type: Type of event
            created_by: User or system that created the document
            test_mode: If True, no data will be written to databases
        """
        # Extract document content
        document = self.pdf_extractor.extract_document(pdf_path)
        
        # Extract insights
        doc_insight = self.extractor.extract_from_document(
            document=document,
            source_type=source_type,
            document_type=document_type,
            event_type=event_type,
            created_by=created_by
        )
        
        # Store in ChromaDB (unless in test mode)
        if not test_mode:
            doc_insight = self.storage.store_document_insight(doc_insight)
        else:
            print(f"TEST MODE: Skipping database writes for document {doc_insight.id}")
        
        return doc_insight
    
    def process_json(self,
                     json_data: Dict,
                     source_type: str,
                     document_type: str,
                     event_type: str,
                     created_by: str,
                     test_mode: bool = False,
                     user_context: Optional[str] = None,
                     enhanced_insights: Optional[Dict] = None) -> DocumentInsight:
        """
        Process document from JSON data
        
        Args:
            json_data: JSON document data
            source_type: Source type of the document
            document_type: Type of document
            event_type: Type of event
            created_by: User or system that created the document
            test_mode: If True, no data will be written to databases
            user_context: Optional user-provided context to guide extraction
            enhanced_insights: Optional pre-generated enhanced insights to include
            
        Returns:
            DocumentInsight object with extracted info
        """
        print(f"[DOCUMENT_PIPELINE] {'TEST MODE' if test_mode else 'NORMAL MODE'} - Processing JSON document")
        if user_context:
            print(f"[DOCUMENT_PIPELINE] User context provided: {user_context[:100]}{'...' if len(user_context) > 100 else ''}")
            print("\n===== DOCUMENT_PIPELINE USER CONTEXT =====")
            print(user_context)
            print("===== END OF USER CONTEXT =====\n")
            
            # Add user context to the document if it has metadata
            if "document" in json_data and "metadata" in json_data["document"]:
                json_data["document"]["metadata"]["user_context"] = user_context
                print(f"[DOCUMENT_PIPELINE] Added user context to document metadata")
                
        # Extract insights from the document
        doc_insight = self.extractor.extract_from_json(
            json_data=json_data,
            source_type=source_type,
            document_type=document_type,
            event_type=event_type,
            created_by=created_by
        )
        print(f"[DOCUMENT_PIPELINE] Insight extraction completed successfully")
        
        # Add enhanced insights if provided
        if enhanced_insights:
            print(f"[DOCUMENT_PIPELINE] Using provided enhanced insights")
            doc_insight.enhanced_insights = enhanced_insights
        
        # In test mode, we don't save to DB
        if test_mode:
            print(f"[DOCUMENT_PIPELINE] TEST MODE: Skipping database storage")
            return doc_insight
            
        # Make sure chromadb_ids is initialized
        if not doc_insight.chromadb_ids:
            doc_insight.chromadb_ids = []
            
        try:
            # Only save to ChromaDB if we're not waiting for enhanced insights
            # or if enhanced insights are already provided
            if enhanced_insights is not None:
                print(f"[DOCUMENT_PIPELINE] Storing document insight in ChromaDB (with enhanced insights)")
                doc_insight = self.storage.store_document_insight(doc_insight)
                print(f"[DOCUMENT_PIPELINE] Storage successful, ChromaDB IDs: {doc_insight.chromadb_ids}")
            else:
                print(f"[DOCUMENT_PIPELINE] Skipping ChromaDB storage until enhanced insights are available")
        except Exception as e:
            print(f"[DOCUMENT_PIPELINE] Error storing document insight: {e}")
            import traceback
            traceback.print_exc()
            # We don't want to fail the entire pipeline if storage fails
        
        return doc_insight
    
    def to_dict(self, doc_insight: DocumentInsight) -> Dict:
        """Convert DocumentInsight to dictionary"""
        return asdict(doc_insight)


# Example usage
if __name__ == "__main__":
    # Initialize the pipeline
    pipeline = DocumentInsightPipeline()
    
    # Example 1: Process a PDF file
    pdf_insight = pipeline.process_pdf(
        pdf_path="example.pdf",
        source_type="upload",
        document_type="financial_report",
        event_type="document_analysis",
        created_by="system"
    )
    
    print(f"Extracted DocumentInsight from PDF with ID: {pdf_insight.id}")
    print(f"Number of phrases extracted: {len(pdf_insight.phrases)}")
    print(f"Number of ChromaDB entries: {len(pdf_insight.chromadb_ids)}")
    
    # Example 2: Process JSON data
    json_data = {
        "document": {
            "content": "This is a sample document content describing the financial performance...",
            "metadata": {"title": "Financial Report 2025", "author": "Finance Team"},
            "source_path": "uploaded_file.json"
        },
        "extraction": {
            "phrases": ["Financial performance exceeded expectations", "Revenue grew by 15%"],
            "insight": {"theme": "growth", "sentiment": "positive"},
            "extracted_entities": {"organizations": ["Acme Corp"], "date": "2025-03-15"},
            "ner_text": "Acme Corp reported financial results on March 15, 2025."
        }
    }
    
    json_insight = pipeline.process_json(
        json_data=json_data,
        source_type="api",
        document_type="financial_report",
        event_type="data_import",
        created_by="api_user"
    )
    
    print(f"Extracted DocumentInsight from JSON with ID: {json_insight.id}")
    
    # Search for similar documents
    search_results: Dict[str, Any] = pipeline.storage.search_similar(
        query="financial performance growth",
        n_results=3,
        filter_criteria={"document_type": "financial_report"}
    )
    
    if search_results and search_results.get('ids'):
        print(f"Search results: {len(search_results['ids'])} matches found")
        for i, doc_id in enumerate(search_results['ids']):
            print(f"Match {i+1}: {doc_id} - Distance: {search_results['distances'][i]}")
            print(f"Content: {search_results['documents'][i][:100]}...")
    else:
        print("No search results found")
"""
Document vectorizer for PDF documents.

This module provides the vectorizer for PDF documents, creating chunks, summaries, and key facts.
"""
import logging
import re
import json
import asyncio
from typing import Dict, List, Any, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_openai import ChatOpenAI

from .base import IVectorizer

# Configure logging
logger = logging.getLogger(__name__)

# Configure callback manager for verbose output
callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])

class DocumentVectorizer(IVectorizer):
    """Vectorizer for processing PDF documents."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """
        Initialize the vectorizer with an OpenAI API key.
        
        Args:
            openai_api_key: Optional OpenAI API key for insights generation
        """
        self.openai_api_key = openai_api_key
        self._llm = None
        self.debug_mode = False
    
    @property
    def llm(self):
        """Get or create the LLM instance."""
        if not self._llm:
            model_name = "gpt-4o-mini"  # Default model
            self._llm = ChatOpenAI(
                temperature=0, 
                model=model_name,
                api_key=self.openai_api_key,
                callback_manager=callback_manager
            )
        return self._llm
    
    def vectorize(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process PDF documents into vector chunks, summaries, and key facts.
        
        Args:
            documents: List of document dictionaries to vectorize
            
        Returns:
            List of vector chunks, including summaries and key facts
        """
        # Check if debug mode is enabled in any of the documents' metadata
        self.debug_mode = False
        for doc in documents:
            metadata = doc.get("metadata", {})
            if metadata.get("debug", False):
                self.debug_mode = True
                break
        
        result_vectors = []
        
        logger.info(f"Processing {len(documents)} documents")
        
        # First, determine document types and create summaries
        summaries, document_types = self._create_summaries(documents)
        result_vectors.extend(summaries)
        
        # Add document_type to each document
        for doc in documents:
            source = doc['metadata'].get('source', '')
            doc_type = document_types.get(source, 'unknown')
            doc['metadata']['document_type'] = doc_type
        
        # Split documents into chunks
        chunks = self._split_documents(documents)
        
        # Extract key facts from chunks
        key_facts = self._extract_key_facts(chunks)
        result_vectors.extend(key_facts)
        
        # Add chunks to results
        result_vectors.extend(chunks)
        
        logger.info(f"Vectorization completed. Generated {len(chunks)} chunks, {len(summaries)} summaries, and {len(key_facts)} key facts.")
        return result_vectors
    
    def _split_documents(self, documents: List[Dict[str, Any]], 
                        chunk_size: int = 1000, 
                        chunk_overlap: int = 200) -> List[Dict[str, Any]]:
        """Split documents into chunks."""
        logger.info(f"Splitting documents into chunks (size={chunk_size}, overlap={chunk_overlap})...")
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            add_start_index=True,
        )
        
        all_chunks = []
        
        for doc in documents:
            # Create a Langchain Document for splitting
            langchain_doc = Document(
                page_content=doc['content'],
                metadata=doc['metadata']
            )
            
            # Split into chunks
            doc_chunks = text_splitter.split_documents([langchain_doc])
            
            # Convert back to our format
            for i, chunk in enumerate(doc_chunks):
                # Extract terms using TF-IDF
                terms = self._compute_top_terms([chunk.page_content])[0]
                
                chunk_dict = {
                    "content": chunk.page_content,
                    "metadata": {
                        **chunk.metadata,
                        "chunk_index": i,
                        "chunk_type": "document_chunk",
                        "vector_type": "chunk",
                        "terms": ", ".join(terms)
                    }
                }
                all_chunks.append(chunk_dict)
                
                if self.debug_mode and i == 0:
                    logger.debug(f"Sample chunk for document {chunk.metadata.get('source', 'unknown')}")
                    logger.debug(f"DOCUMENT VECTORIZER CHUNK OUTPUT: {json.dumps(chunk_dict, indent=2, default=str)[:500]}...")
        
        logger.info(f"Created {len(all_chunks)} chunks")
        return all_chunks
    
    def _create_summaries(self, documents: List[Dict[str, Any]]) -> tuple:
        """Create summaries for each document and determine document types."""
        logger.info(f"Creating document summaries...")
        
        summaries = []
        document_types = {}
        
        # Group documents by source
        grouped_docs = {}
        for doc in documents:
            source = doc['metadata'].get('source', 'unknown')
            if source not in grouped_docs:
                grouped_docs[source] = []
            grouped_docs[source].append(doc)
        
        # Create a summary for each document
        for source, docs in grouped_docs.items():
            logger.info(f"Creating summary for {source}...")
            
            # Extract document name from source for section identification
            section = source.replace('.pdf', '')
            
            # Combine text from all parts of this document
            combined_text = "\n\n".join([doc['content'] for doc in docs])
            
            try:
                # Generate summary with document type classification
                response = self.llm.invoke(
                    f"""You are an expert summarization assistant with pharmaceutical industry experience. Read the following text and produce a JSON output with two fields:
                1. "summary": A clear, concise summary that covers:
                   - The main purpose
                   - The key supporting points
                   - Any conclusions or recommendations
                2. "document_type": The type of document (e.g., report, agreement, article, manual, clinical_trial_protocol, etc.)

                Your summary should be:
                - Written in neutral, objective language
                - Around 6-7 sentences (or ~150 words)
                - Do not include any information that is not supported by the text

                Return ONLY valid JSON with these two fields. DO NOT include markdown formatting, code blocks, or backticks (```) in your response. Return only the raw JSON object.

                TEXT:
                {combined_text[:10000]}  # Limit text length to avoid context limits

                JSON OUTPUT:"""
                )
                
                # Parse the JSON response
                if hasattr(response, 'content') and isinstance(response.content, str):
                    json_content = response.content.strip()
                else:
                    json_content = str(response).strip() if isinstance(response, str) else str(response.content).strip()
                
                # Remove any potential code block markers
                json_content = re.sub(r'^```json\s*|\s*```$', '', json_content, flags=re.MULTILINE)
                json_content = re.sub(r'^```\s*|\s*```$', '', json_content, flags=re.MULTILINE)
                
                result = json.loads(json_content)
                summary = result.get("summary", "")
                document_type = result.get("document_type", "unknown")
                
                # Store document type for later use
                document_types[source] = document_type
                
                # Create a summary vector
                summary_vector = {
                    "content": summary,
                    "metadata": {
                        "source": source,
                        "source_type": "pdf",
                        "type": "summary",
                        "document_type": document_type,
                        "document_count": len(docs),
                        "section": section,
                        "vector_type": "summary"
                    }
                }
                
                # Add top terms for the summary
                terms = self._compute_top_terms([summary])[0]
                summary_vector["metadata"]["terms"] = ", ".join(terms)
                
                summaries.append(summary_vector)
                
                if self.debug_mode:
                    logger.debug(f"Created summary for document {source}")
                    logger.debug(f"DOCUMENT VECTORIZER SUMMARY OUTPUT: {json.dumps(summary_vector, indent=2, default=str)}")
                
            except Exception as e:
                logger.error(f"Error creating summary for {source}: {str(e)}")
                # Add a default document type
                document_types[source] = "unknown"
        
        logger.info(f"Created {len(summaries)} document summaries")
        return summaries, document_types
    
    def _extract_key_facts(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract key facts from document chunks."""
        logger.info(f"Extracting key facts from chunks...")
        
        key_facts = []
        
        # Process in batches to avoid overloading
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}...")
            
            for chunk in batch:
                # Skip very short chunks
                if len(chunk['content']) < 100:
                    continue
                    
                try:
                    # Extract key information using the LLM
                    response = self.llm.invoke(
                        f"""You are a document analyst with pharmaceutical industry experience. From the following text, automatically:
                    1. Identify and list the **named entities** (people, organizations, locations).
                    2. Pull out all **dates** and their context (deadlines, effective dates, publication dates).
                    3. Find any **monetary amounts** or financial figures, with their descriptions.
                    4. Summarize any **obligations or action items** (e.g., deliverables, tasks, next steps).
                    5. Highlight any **critical conditions or clauses** (e.g., termination, confidentiality, warranties).
                    6. Capture any **performance metrics or thresholds** mentioned.
                    7. Note any **recommendations, conclusions, or key findings**.
                    8. Include any other **notable details** that a reader should be aware of.

                    **Output** each item as a separate bullet, prefixed by its category, and include a one-line **document-type** heading at the very top. If a category yields no results, simply omit it.
                    
                    IMPORTANT: DO NOT include any markdown formatting, code blocks, or JSON syntax in your response. Return only plain text bullets.

                    **TEXT:**
                    {chunk['content']}

                    **EXTRACTION:**"""
                    )
                    
                    # Clean up the response
                    if hasattr(response, 'content') and isinstance(response.content, str):
                        cleaned_content = response.content.strip()
                    else:
                        cleaned_content = str(response).strip() if isinstance(response, str) else str(response.content).strip()

                    cleaned_content = re.sub(r'^```json\s*|\s*```$', '', cleaned_content, flags=re.MULTILINE)
                    cleaned_content = re.sub(r'^```\s*|\s*```$', '', cleaned_content, flags=re.MULTILINE)
                    
                    # Split the response into individual facts
                    extracted_facts = cleaned_content.split('\n')
                    
                    # Create vectors for each extracted fact
                    for fact in extracted_facts:
                        fact = fact.strip()
                        if fact and len(fact) > 20:  # Ignore very short facts
                            # Create key fact vector
                            key_fact = {
                                "content": fact,
                                "metadata": {
                                    **chunk['metadata'],
                                    "type": "key_facts",
                                    "vector_type": "key_fact",
                                }
                            }
                            
                            # Add top terms for this fact
                            terms = self._compute_top_terms([fact])[0]
                            key_fact["metadata"]["terms"] = ", ".join(terms)
                            
                            key_facts.append(key_fact)
                            
                            if self.debug_mode and len(key_facts) <= 1:
                                logger.debug(f"Sample key fact extraction")
                                logger.debug(f"DOCUMENT VECTORIZER KEY FACT OUTPUT: {json.dumps(key_fact, indent=2, default=str)}")
                
                except Exception as e:
                    logger.error(f"Error extracting key facts: {str(e)}")
        
        logger.info(f"Extracted {len(key_facts)} key facts")
        return key_facts
    
    def _compute_top_terms(self, texts: List[str], top_n: int = 10) -> List[List[str]]:
        """Compute top terms for a list of texts using TF-IDF."""
        try:
            vec = TfidfVectorizer(stop_words="english")
            X = vec.fit_transform(texts)
            names = vec.get_feature_names_out()
            terms_list = []
            
            # Process each document's TF-IDF scores
            for i in range(X.shape[0]):
                # Extract the row directly using scipy's methods
                row = X.getrow(i).toarray().flatten()
                # Find indices of top terms
                top_idx = row.argsort()[-top_n:][::-1]
                # Extract terms with positive scores
                terms = [names[idx] for idx in top_idx if row[idx] > 0]
                terms_list.append(terms)
            
            return terms_list
        except Exception as e:
            logger.error(f"Error computing top terms: {str(e)}")
            return [[] for _ in range(len(texts))] 
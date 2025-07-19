import os
import glob
import json
import re
from typing import List, Optional, Dict, Any
import argparse
from pathlib import Path
import chromadb as chromadb
from chromadb.utils import embedding_functions

from langchain_community.document_loaders import UnstructuredPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chains.summarize import load_summarize_chain
from langchain_openai import ChatOpenAI
from sklearn.feature_extraction.text import TfidfVectorizer

from dotenv import load_dotenv
load_dotenv()

# Configure callback manager for verbose output
callback_manager = CallbackManager([StreamingStdOutCallbackHandler()])

def load_pdfs(directory_path: str) -> List[Document]:
    """
    Load all PDFs from a directory
    
    Args:
        directory_path: Path to directory containing PDFs
        
    Returns:
        List of Document objects
    """
    print(f"Loading PDFs from {directory_path}...")
    
    # Check if directory exists
    if not os.path.exists(directory_path):
        raise ValueError(f"Directory {directory_path} does not exist")
    
    # Load all PDFs from directory
    loader = DirectoryLoader(
        directory_path, 
        glob="**/*.pdf",
        loader_cls=UnstructuredPDFLoader
    )
    
    documents = loader.load()
    print(f"Loaded {len(documents)} documents")
    return documents

def split_documents(documents: List[Document], 
                   chunk_size: int = 1000, 
                   chunk_overlap: int = 200) -> List[Document]:
    """
    Split documents into chunks
    
    Args:
        documents: List of Document objects
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of Document chunks
    """
    print(f"Splitting documents into chunks (size={chunk_size}, overlap={chunk_overlap})...")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        add_start_index=True,
    )
    
    chunks = text_splitter.split_documents(documents)
    
    # Update metadata for each chunk
    for chunk in chunks:
        # Extract filename from path
        source_path = chunk.metadata.get('source', 'unknown')
        chunk.metadata['source'] = os.path.basename(source_path)
        # Add source_type field
        chunk.metadata['source_type'] = 'pdf'
    
    print(f"Created {len(chunks)} chunks")
    return chunks

def create_summaries(documents: List[Document], 
                    llm_model: str = "gpt-4o-mini") -> List[Document]:
    """
    Create analytical summaries for each document focused on contract performance and risks
    
    Args:
        documents: List of Document objects
        llm_model: LLM model to use for summarization
        
    Returns:
        List of Document objects with summaries
    """
    print(f"Creating contract analytics summaries using {llm_model}...")
    
    llm = ChatOpenAI(
        temperature=0, 
        model=llm_model,
        callback_manager=callback_manager
    )
    
    # Group documents by source file and create a summary for each file
    summaries = []
    document_types = {}  # Store document types by source for later use
    
    # Group documents by source
    grouped_docs = {}
    for doc in documents:
        source = doc.metadata.get('source', 'unknown')
        if source not in grouped_docs:
            grouped_docs[source] = []
        grouped_docs[source].append(doc)
    
    # Create a summary for each group
    for source, docs in grouped_docs.items():
        print(f"Creating contract analytics summary for {source}...")
        
        # Extract document name from source path for section identification
        filename = os.path.basename(source)
        section = filename.replace('.pdf', '')
        
        # Use custom summarization prompt instead of default chain
        combined_text = "\n\n".join([doc.page_content for doc in docs])
        
        response = llm.invoke(
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
        {combined_text}

        JSON OUTPUT:"""
        )
        
        # Parse the JSON response
        try:
            # Clean up any potential markdown formatting that might have been included
            json_content = response.content.strip()
            # Remove any potential code block markers
            json_content = re.sub(r'^```json\s*|\s*```$', '', json_content, flags=re.MULTILINE)
            json_content = re.sub(r'^```\s*|\s*```$', '', json_content, flags=re.MULTILINE)
            
            result = json.loads(json_content)
            summary = result.get("summary", "")
            document_type = result.get("document_type", "unknown")
        except json.JSONDecodeError:
            # Fallback if JSON parsing fails
            summary = response.content.strip()
            # Try to extract document type using regex
            match = re.search(r"document_type[\"']?\s*:\s*[\"']([^\"']+)[\"']", response.content)
            document_type = match.group(1) if match else "unknown"
        
        # Store document type for later use with chunks
        document_types[source] = document_type
        
        # Create a new document with the summary
        summary_doc = Document(
            page_content=summary,
            metadata={
                "source": filename,
                "source_type": "pdf",
                "type": "summary",
                "document_type": document_type,
                "document_count": len(docs),
                "section": section
            }
        )
        
        summaries.append(summary_doc)
    
    # Return both summaries and document types
    print(f"Created {len(summaries)} contract analytics summaries")
    return summaries, document_types

def extract_quotes(chunks: List[Document], 
                  llm_model: str = "gpt-4o-mini") -> List[Document]:
    """
    Extract important key facts from document chunks with focus on contractual information
    
    Args:
        chunks: List of Document chunks
        llm_model: LLM model to use for key fact extraction
        
    Returns:
        List of Document objects with key facts
    """
    print(f"Extracting key contractual information using {llm_model}...")
    
    llm = ChatOpenAI(
        temperature=0, 
        model=llm_model,
        callback_manager=callback_manager
    )
    
    quotes = []
    
    # Process in batches to avoid overloading the API
    batch_size = 10
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}...")
        
        for doc in batch:
            # Skip very short chunks
            if len(doc.page_content) < 100:
                continue
                
            # Extract key contractual information using the LLM
            response = llm.invoke(
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
            {doc.page_content}

            **EXTRACTION:**"""
            )
            
            # Clean up any potential markdown formatting
            cleaned_content = response.content.strip()
            cleaned_content = re.sub(r'^```json\s*|\s*```$', '', cleaned_content, flags=re.MULTILINE)
            cleaned_content = re.sub(r'^```\s*|\s*```$', '', cleaned_content, flags=re.MULTILINE)
            
            # Split the response into individual facts
            extracted_quotes = cleaned_content.split('\n')
            
            # Create a new document for each extracted fact
            for quote in extracted_quotes:
                quote = quote.strip()
                if quote and len(quote) > 20:  # Ignore very short quotes
                    # Get the source filename
                    source_path = doc.metadata.get('source', 'unknown')
                    filename = os.path.basename(source_path)
                    
                    quote_doc = Document(
                        page_content=quote,
                        metadata={
                            "source": filename,
                            "source_type": "pdf",
                            "type": "key_facts",
                            "page": doc.metadata.get('page', 0),
                            "document_type": doc.metadata.get('document_type', 'unknown'),
                            "chunk_index": doc.metadata.get('start_index', 0)
                        }
                    )
                    quotes.append(quote_doc)
    
    print(f"Extracted {len(quotes)} key contract facts")
    return quotes

def compute_top_terms(texts, top_n=10):
    """
    Compute top terms for a list of texts using TF-IDF
    
    Args:
        texts: List of text strings
        top_n: Number of top terms to extract per document
        
    Returns:
        List of lists of top terms
    """
    print(f"Computing top {top_n} terms for {len(texts)} texts...")
    
    vec = TfidfVectorizer(stop_words="english")
    X = vec.fit_transform(texts)
    names = vec.get_feature_names_out()
    terms_list = []
    for row in X:
        scores = row.toarray().ravel()
        top_idx = scores.argsort()[-top_n:][::-1]
        terms = [names[i] for i in top_idx if scores[i] > 0]
        terms_list.append(terms)
    
    return terms_list

def create_vector_stores(chunks: List[Document],
                        summaries: List[Document],
                        quotes: List[Document],
                        chunks_terms: List[List[str]],
                        summaries_terms: List[List[str]],
                        quotes_terms: List[List[str]],
                        dry_run: bool = False):
    """
    Create and save vector stores to the remote ChromaDB instance specified in environment variables
    
    Args:
        chunks: List of Document chunks
        summaries: List of Document summaries with contract analytics focus
        quotes: List of Document key contract facts
        chunks_terms: List of lists of top terms for chunks
        summaries_terms: List of lists of top terms for summaries
        quotes_terms: List of lists of top terms for quotes
        dry_run: If True, only print sample data without storing to ChromaDB
    """
    if dry_run:
        print("\n=== DRY RUN MODE: No data will be stored to ChromaDB ===\n")
        
        # Print sample data for chunks
        print("\n=== SAMPLE CHUNK DATA ===")
        if chunks:
            sample_chunk = {
                "content": chunks[0].page_content[:200] + "..." if len(chunks[0].page_content) > 200 else chunks[0].page_content,
                "metadata": chunks[0].metadata,
                "terms": chunks_terms[0] if chunks_terms else []
            }
            print(json.dumps(sample_chunk, indent=2, default=str))
        
        # Print sample data for summaries
        print("\n=== SAMPLE SUMMARY DATA ===")
        if summaries:
            sample_summary = {
                "content": summaries[0].page_content,
                "metadata": summaries[0].metadata,
                "terms": summaries_terms[0] if summaries_terms else []
            }
            print(json.dumps(sample_summary, indent=2, default=str))
        
        # Print sample data for quotes
        print("\n=== SAMPLE QUOTE DATA ===")
        if quotes:
            sample_quote = {
                "content": quotes[0].page_content,
                "metadata": quotes[0].metadata,
                "terms": quotes_terms[0] if quotes_terms else []
            }
            print(json.dumps(sample_quote, indent=2, default=str))
        
        print("\n=== END OF DRY RUN ===\n")
        return
    
    print("Creating vector stores with ChromaDB...")
    
    # Get ChromaDB connection details from environment variables
    chroma_host = os.getenv("CHROMA_HOST")
    chroma_port = os.getenv("CHROMA_PORT")
    
    if chroma_host and chroma_port:
        print(f"Connecting to remote ChromaDB at {chroma_host}:{chroma_port}")
        client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
    else:
        print("No remote ChromaDB configuration found. Using local persistence.")
        client = chromadb.PersistentClient("./chromadb_local")
    
    # Create document chunks collection
    print("Creating document chunks collection...")
    try:
        client.delete_collection("document_chunks")
    except:
        pass
    chunks_collection = client.create_collection(
        name="document_chunks",
        metadata={"description": "Document chunks from PDFs"}
    )
    
    # Add documents to chunks collection
    documents, metadatas, ids = [], [], []
    for i, doc in enumerate(chunks):
        documents.append(doc.page_content)
        md = doc.metadata.copy()
        # Convert terms list to a string with comma separation
        md["terms"] = ", ".join(chunks_terms[i]) if chunks_terms[i] else ""
        metadatas.append(md)
        ids.append(f"chunk_{i}")
    
    # Add in batches to avoid token limits
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        end_idx = min(i + batch_size, len(documents))
        chunks_collection.add(
            documents=documents[i:end_idx],
            metadatas=metadatas[i:end_idx],
            ids=ids[i:end_idx]
        )
    
    # Create document summaries collection
    print("Creating document summaries collection...")
    try:
        client.delete_collection("document_summaries")
    except:
        pass
    summaries_collection = client.create_collection(
        name="document_summaries",
        metadata={"description": "Document summaries with contract analytics focus"}
    )
    
    # Add documents to summaries collection
    documents, metadatas, ids = [], [], []
    for i, doc in enumerate(summaries):
        documents.append(doc.page_content)
        md = doc.metadata.copy()
        # Convert terms list to a string with comma separation
        md["terms"] = ", ".join(summaries_terms[i]) if summaries_terms[i] else ""
        metadatas.append(md)
        ids.append(f"summary_{i}")
    
    summaries_collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    # Create key facts collection
    print("Creating key facts collection...")
    try:
        client.delete_collection("key_facts")
    except:
        pass
    key_facts_collection = client.create_collection(
        name="key_facts",
        metadata={"description": "Key contract facts extracted from documents"}
    )
    
    # Add documents to key facts collection
    documents, metadatas, ids = [], [], []
    for i, doc in enumerate(quotes):
        documents.append(doc.page_content)
        md = doc.metadata.copy()
        # Convert terms list to a string with comma separation
        md["terms"] = ", ".join(quotes_terms[i]) if quotes_terms[i] else ""
        metadatas.append(md)
        ids.append(f"fact_{i}")
    
    # Add in batches to avoid token limits
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        end_idx = min(i + batch_size, len(documents))
        key_facts_collection.add(
            documents=documents[i:end_idx],
            metadatas=metadatas[i:end_idx],
            ids=ids[i:end_idx]
        )
    
    print("ChromaDB vector stores created successfully!")
    print(f"Data stored to {'remote ChromaDB at ' + chroma_host + ':' + chroma_port if chroma_host and chroma_port else 'local ChromaDB'}")

def main():
    parser = argparse.ArgumentParser(description="Create vector stores from PDFs")
    parser.add_argument("--pdf_dir", type=str, required=True, help="Directory containing PDFs")
    parser.add_argument("--chunk_size", type=int, default=1000, help="Size of each chunk")
    parser.add_argument("--chunk_overlap", type=int, default=200, help="Overlap between chunks")
    parser.add_argument("--llm_model", type=str, default="gpt-4o-mini", help="LLM model to use")
    parser.add_argument("--dry_run", action="store_true", help="Dry run mode - print sample data without storing to ChromaDB")
    
    args = parser.parse_args()

    chroma_host = os.getenv("CHROMA_HOST")
    chroma_port = os.getenv("CHROMA_PORT")

    try:
        client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        # Test connection
        client.heartbeat()
        print(f"Successfully connected to remote ChromaDB at {chroma_host}:{chroma_port}")
    except Exception as e:
        print(f"Failed to connect to remote ChromaDB: {str(e)}")
    
    # Load PDFs
    documents = load_pdfs(args.pdf_dir)
    
    # Split documents into chunks
    chunks = split_documents(documents, args.chunk_size, args.chunk_overlap)
    
    # Create summaries and get document types
    summaries, document_types = create_summaries(documents, args.llm_model)
    
    # Add document_type to chunks based on their source
    for chunk in chunks:
        source_path = chunk.metadata.get('source', 'unknown')
        original_source = next((s for s in document_types.keys() if source_path in s or os.path.basename(source_path) in s), None)
        if original_source:
            chunk.metadata['document_type'] = document_types[original_source]
        else:
            chunk.metadata['document_type'] = 'unknown'
    
    # Compute sparse term lists for chunks
    chunk_texts = [c.page_content for c in chunks]
    chunks_terms = compute_top_terms(chunk_texts, top_n=10)
    
    # Compute sparse term lists for summaries
    summary_texts = [s.page_content for s in summaries]
    summaries_terms = compute_top_terms(summary_texts, top_n=10)
    
    # Extract quotes
    quotes = extract_quotes(chunks, args.llm_model)
    quote_texts = [q.page_content for q in quotes]
    quotes_terms = compute_top_terms(quote_texts, top_n=10)
    
    # Create vector stores - will automatically save to the default locations
    create_vector_stores(
        chunks, summaries, quotes,
        chunks_terms=chunks_terms,
        summaries_terms=summaries_terms,
        quotes_terms=quotes_terms,
        dry_run=args.dry_run
    )

if __name__ == "__main__":
    main() 
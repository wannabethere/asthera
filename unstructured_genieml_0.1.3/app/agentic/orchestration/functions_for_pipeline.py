import chromadb
from langchain.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.documents import Document

from langgraph.graph import END, StateGraph

from dotenv import load_dotenv
from pprint import pprint
import os
import time
import datetime
import pathlib
from typing_extensions import TypedDict
from typing import List, TypedDict, Optional
from collections import defaultdict

from app.config.settings import get_settings
from app.utils.chromadb import ChromaDB
from .personas.personas_config import get_persona

from .helper_functions import escape_quotes, text_wrap

from app.utils.llm_factory import get_default_llm, get_answer_generation_llm
from rank_bm25 import BM25Okapi
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import numpy as np

# DEBUG flag - set to False to disable debug prints and timing logs
# When DEBUG = False, all debug_print() calls and timing logs will be suppressed
# When DEBUG = True, you'll see detailed timing information for each operation
DEBUG = True

# LOG_TO_FILE flag - set to True to save logs to a file
LOG_TO_FILE = False

# Global variables for tracking elapsed time regardless of DEBUG setting
PIPELINE_START_TIME = None
PIPELINE_ELAPSED_TIME = None

# Get the directory of the current file
CURRENT_DIR = pathlib.Path(__file__).parent.absolute()


# Create a log file with timestamp
def get_log_file_path():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return CURRENT_DIR / f"pipeline_timing_{timestamp}.log"


# Global log file handle
log_file = None

# Initialize log file if needed
if LOG_TO_FILE:  # Removed DEBUG condition to always create log file when LOG_TO_FILE is True
    log_file_path = get_log_file_path()
    try:
        log_file = open(log_file_path, 'w')
        log_file.write(
            f"=== Pipeline Timing Log - Started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
        print(f"Logging timing information to: {log_file_path}")

        # Register cleanup function to close log file when script exits
        import atexit


        def close_log_file():
            if log_file:
                try:
                    log_file.write(
                        f"\n=== Pipeline Timing Log - Ended at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                    if PIPELINE_ELAPSED_TIME is not None:
                        log_file.write(f"\n=== TOTAL PIPELINE ELAPSED TIME: {PIPELINE_ELAPSED_TIME:.2f} seconds ===\n")
                    log_file.close()
                    print(f"Closed log file: {log_file_path}")
                except Exception as e:
                    print(f"Error closing log file: {e}")


        atexit.register(close_log_file)
    except Exception as e:
        print(f"Error opening log file: {e}")
        log_file = None


# Timing utility functions
def debug_print(*args, **kwargs):
    """Print only when DEBUG is True and optionally log to file"""
    # Create the message
    message = " ".join(str(arg) for arg in args)

    # Print to console if DEBUG is True
    if DEBUG:
        print(*args, **kwargs)

    # Write to log file if enabled (regardless of DEBUG setting)
    if LOG_TO_FILE and log_file:
        try:
            log_file.write(f"{message}\n")
            log_file.flush()  # Ensure it's written immediately
        except Exception as e:
            print(f"Error writing to log file: {e}")


def time_function(func_name=None):
    """Decorator to time function execution"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            if not DEBUG:
                return func(*args, **kwargs)

            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time

            name = func_name or func.__name__
            message = f"⏱️  {name} took {execution_time:.2f} seconds"
            debug_print(message)
            return result

        return wrapper

    return decorator


def log_time(operation_name):
    """Context manager for timing operations"""

    class TimeLogger:
        def __init__(self, name):
            self.name = name
            self.start_time = None

        def __enter__(self):
            if DEBUG:
                self.start_time = time.time()
                debug_print(f"🔄 Starting {self.name}...")
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if DEBUG and self.start_time:
                end_time = time.time()
                execution_time = end_time - self.start_time
                message = f"✅ {self.name} completed in {execution_time:.2f} seconds"
                debug_print(message)

    return TimeLogger(operation_name)


# Function to start tracking pipeline elapsed time
def start_pipeline_timer():
    global PIPELINE_START_TIME
    PIPELINE_START_TIME = time.time()
    message = f"🕒 Pipeline timer started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    # Always print this message
    print(message)

    # Always log this message if logging is enabled
    if LOG_TO_FILE and log_file:
        log_file.write(f"{message}\n")
        log_file.flush()


# Function to stop tracking pipeline elapsed time
def stop_pipeline_timer():
    global PIPELINE_START_TIME, PIPELINE_ELAPSED_TIME
    if PIPELINE_START_TIME is not None:
        PIPELINE_ELAPSED_TIME = time.time() - PIPELINE_START_TIME
        message = f"🕒 Pipeline timer stopped. Total elapsed time: {PIPELINE_ELAPSED_TIME:.2f} seconds"

        # Always print this message
        print(message)

        # Always log this message if logging is enabled
        if LOG_TO_FILE and log_file:
            log_file.write(f"{message}\n")
            log_file.flush()

        return PIPELINE_ELAPSED_TIME
    return None


"""
Set the environment variables for the API keys.
"""
# Load settings
settings = get_settings()
os.environ["PYDEVD_WARN_EVALUATION_TIMEOUT"] = "100000"
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY


# groq_api_key = os.getenv('GROQ_API_KEY')

# Hybrid ChromaDB retriever class that combines vector and metadata search
class ChromaHybridRetriever:
    def __init__(self, collection, k=5, alpha=0.5, beta=0.3):
        """
        collection: a chromadb.Collection or ChromaDB collection wrapper
        k: number of top docs to retrieve from each pass
        alpha: weight on semantic (vector) score
        beta: weight on BM25 score
        gamma (1-alpha-beta): weight on keyword metadata
        """
        self.coll = collection
        self.k = k
        self.alpha = alpha
        self.beta = beta
        self.gamma = 1 - alpha - beta
        debug_print(
            f"Initialized ChromaHybridRetriever with collection={collection}, k={k}, alpha={alpha}, beta={beta}, gamma={self.gamma}")

        # Initialize BM25 index with all documents in collection
        self._initialize_bm25_index()

    def _initialize_bm25_index(self):
        """Build BM25 index from all documents in the collection"""
        with log_time("BM25 index initialization"):
            debug_print("Building BM25 index from collection documents...")
            try:
                # Get all documents from collection
                result = self.coll.get(include=["documents"])
                if "documents" in result and result["documents"]:
                    # Simple tokenization for BM25
                    self.doc_texts = result["documents"]
                    self.tokenized_corpus = [self._tokenize(doc) for doc in self.doc_texts]
                    self.bm25 = BM25Okapi(self.tokenized_corpus)
                    debug_print(f"BM25 index built with {len(self.tokenized_corpus)} documents")
                else:
                    debug_print("No documents found in collection for BM25 indexing")
                    self.doc_texts = []
                    self.tokenized_corpus = []
                    self.bm25 = None
            except Exception as e:
                debug_print(f"Error building BM25 index: {str(e)}")
                self.doc_texts = []
                self.tokenized_corpus = []
                self.bm25 = None

    def _tokenize(self, text):
        """Simple tokenization for BM25"""
        if not text:
            return []
        # Convert to lowercase, split on whitespace, and filter out tokens shorter than 2 chars
        return [token.lower() for token in text.split() if len(token) > 2]

    def vector_pass(self, query: str):
        with log_time("Vector search pass"):
            debug_print(f"\n=== VECTOR SEARCH PASS ===")
            debug_print(f"Query: '{query}'")
            debug_print(f"Collection: {self.coll}")
            result = self.coll.query(
                query_texts=[query],
                n_results=self.k,
                include=["documents", "distances", "metadatas"]
            )

            # Log the results
            if "documents" in result and result["documents"] and len(result["documents"]) > 0:
                doc_count = len(result["documents"][0])
                debug_print(f"Vector search returned {doc_count} documents")
                # Only print the first 10 documents to avoid overwhelming logs
                for i, (doc, dist) in enumerate(zip(
                        result["documents"][0][:10],  # Limit to first 10
                        result["distances"][0][:10] if "distances" in result and result["distances"] else [0.0] * min(
                            10, len(result["documents"][0]))
                )):
                    # Convert L2 distance to cosine similarity
                    sim_score = 1.0 / (1.0 + dist) if dist > 0 else 1.0
                    debug_print(f"  Doc {i + 1}: Distance={dist:.4f}, Similarity={sim_score:.4f}")
                    debug_print(f"    Content: {doc[:100]}..." if len(doc) > 100 else f"    Content: {doc}")

                if doc_count > 10:
                    debug_print(f"  ... and {doc_count - 10} more documents (not shown)")
            else:
                debug_print("Vector search returned no documents")

            return result

    def metadata_pass(self, query: str):
        with log_time("Metadata search pass"):
            # simple tokenizer; adjust if you need more robust keyword extraction
            terms = [t.lower() for t in query.split() if len(t) > 2]

            debug_print(f"\n=== METADATA SEARCH PASS ===")
            debug_print(f"Query: '{query}'")
            debug_print(f"Extracted terms: {terms}")

            if not terms:
                # If no valid terms, just return the vector search results
                debug_print("No valid terms extracted for metadata search, falling back to vector search")
                return self.vector_pass(query)

            # Create OR conditions for each term
            where_conditions = []
            for term in terms:
                where_conditions.append({"$contains": term})

            # Use where_document for the ChromaDB utility class
            where_document = {"$or": where_conditions}
            debug_print(f"Metadata search filter: {where_document}")

            result = self.coll.query(
                query_texts=[query],
                n_results=self.k,
                where_document=where_document,
                include=["documents", "distances", "metadatas"]
            )

            # Log the results
            if "documents" in result and result["documents"] and len(result["documents"]) > 0:
                doc_count = len(result['documents'][0])
                debug_print(f"Metadata search returned {doc_count} documents")
                # Only print the first 10 documents to avoid overwhelming logs
                for i, (doc, dist) in enumerate(zip(
                        result["documents"][0][:10],  # Limit to first 10
                        result["distances"][0][:10] if "distances" in result and result["distances"] else [0.0] * min(
                            10, len(result["documents"][0]))
                )):
                    # Convert L2 distance to similarity score
                    sim_score = 1.0 / (1.0 + dist) if dist > 0 else 1.0
                    debug_print(f"  Doc {i + 1}: Distance={dist:.4f}, Similarity={sim_score:.4f}")
                    debug_print(f"    Content: {doc[:100]}..." if len(doc) > 100 else f"    Content: {doc}")

                if doc_count > 10:
                    debug_print(f"  ... and {doc_count - 10} more documents (not shown)")
            else:
                debug_print("Metadata search returned no documents")

            return result

    def bm25_pass(self, query: str):
        """Run BM25 search on the query"""
        with log_time("BM25 search pass"):
            debug_print(f"\n=== BM25 SEARCH PASS ===")
            debug_print(f"Query: '{query}'")

            if not self.bm25:
                debug_print("BM25 index not initialized, skipping BM25 search")
                return {"documents": [[]], "distances": [[]], "metadatas": [[]]}

            # Tokenize query
            query_tokens = self._tokenize(query)
            if not query_tokens:
                debug_print("No valid tokens in query for BM25 search")
                return {"documents": [[]], "distances": [[]], "metadatas": [[]]}

            # Get BM25 scores
            scores = self.bm25.get_scores(query_tokens)

            # Sort by score and get top k
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:self.k]
            top_docs = [self.doc_texts[i] for i in top_indices]
            top_scores = [scores[i] for i in top_indices]

            # Log the results
            doc_count = len(top_docs)
            debug_print(f"BM25 search returned {doc_count} documents")
            # Only print the first 10 documents to avoid overwhelming logs
            for i, (doc, score) in enumerate(zip(top_docs[:10], top_scores[:10])):
                debug_print(f"  Doc {i + 1}: BM25 Score={score:.4f}")
                debug_print(f"    Content: {doc[:100]}..." if len(doc) > 100 else f"    Content: {doc}")

            if doc_count > 10:
                debug_print(f"  ... and {doc_count - 10} more documents (not shown)")

            # Format results similar to Chroma's query output
            result = {
                "documents": [top_docs],
                "distances": [[1.0 / (1.0 + score) for score in top_scores]],  # Convert to distance-like metric
                "metadatas": [[{}] * len(top_docs)]
            }

            return result

    def fuse_results(self, vec_res, meta_res, bm25_res):
        with log_time("Fusing search results"):
            debug_print("\n=== FUSING SEARCH RESULTS ===")
            import numpy as np

            # Extract document content and metadata from results
            vec_docs = vec_res["documents"][0] if "documents" in vec_res and vec_res["documents"] and len(
                vec_res["documents"]) > 0 else []
            meta_docs = meta_res["documents"][0] if "documents" in meta_res and meta_res["documents"] and len(
                meta_res["documents"]) > 0 else []
            bm25_docs = bm25_res["documents"][0] if "documents" in bm25_res and bm25_res["documents"] and len(
                bm25_res["documents"]) > 0 else []

            # Extract metadata
            vec_metas = vec_res["metadatas"][0] if "metadatas" in vec_res and vec_res["metadatas"] else [{}] * len(
                vec_docs)
            meta_metas = meta_res["metadatas"][0] if "metadatas" in meta_res and meta_res["metadatas"] else [{}] * len(
                meta_docs)
            bm25_metas = bm25_res["metadatas"][0] if "metadatas" in bm25_res and bm25_res["metadatas"] else [{}] * len(
                bm25_docs)

            # Log counts
            debug_print(
                f"Processing {len(vec_docs)} vector results, {len(meta_docs)} metadata results, and {len(bm25_docs)} BM25 results")

            # Early return if no documents
            if not vec_docs and not meta_docs and not bm25_docs:
                debug_print("No documents found in any search results")
                return []

            # VECTORIZED APPROACH FOR EACH RESULT SET

            # 1. Vector search results processing
            if vec_docs:
                # Get distances as numpy array
                vec_dists = np.array(
                    vec_res["distances"][0] if "distances" in vec_res and vec_res["distances"] else [0.0] * len(
                        vec_docs))
                # Convert distances to similarities in bulk
                vec_sims = 1.0 / (1.0 + vec_dists)
                # Create document-to-score and document-to-metadata mappings
                vec_doc_to_sim = {doc: sim for doc, sim in zip(vec_docs, vec_sims)}
                vec_doc_to_meta = {doc: meta for doc, meta in zip(vec_docs, vec_metas)}
            else:
                vec_doc_to_sim = {}
                vec_doc_to_meta = {}

            # 2. Metadata search results processing
            if meta_docs:
                # Get distances as numpy array
                meta_dists = np.array(
                    meta_res["distances"][0] if "distances" in meta_res and meta_res["distances"] else [0.0] * len(
                        meta_docs))
                # Convert distances to similarities in bulk
                meta_sims = 1.0 / (1.0 + meta_dists)
                # Create document-to-score and document-to-metadata mappings
                meta_doc_to_sim = {doc: sim for doc, sim in zip(meta_docs, meta_sims)}
                meta_doc_to_meta = {doc: meta for doc, meta in zip(meta_docs, meta_metas)}
            else:
                meta_doc_to_sim = {}
                meta_doc_to_meta = {}

            # 3. BM25 search results processing
            if bm25_docs:
                # Get distances as numpy array
                bm25_dists = np.array(
                    bm25_res["distances"][0] if "distances" in bm25_res and bm25_res["distances"] else [0.0] * len(
                        bm25_docs))
                # Convert distances to similarities in bulk
                bm25_sims = 1.0 / (1.0 + bm25_dists)
                # Normalize BM25 scores
                max_bm25_sim = np.max(bm25_sims) if np.max(bm25_sims) > 0 else 1.0
                bm25_sims = bm25_sims / max_bm25_sim
                # Create document-to-score and document-to-metadata mappings
                bm25_doc_to_sim = {doc: sim for doc, sim in zip(bm25_docs, bm25_sims)}
                bm25_doc_to_meta = {doc: meta for doc, meta in zip(bm25_docs, bm25_metas)}
            else:
                bm25_doc_to_sim = {}
                bm25_doc_to_meta = {}

            # Get unique documents across all search methods
            all_docs = list(set(vec_docs) | set(meta_docs) | set(bm25_docs))
            debug_print(f"Found {len(all_docs)} unique documents across all search methods")

            if not all_docs:
                return []

            # Create score arrays for all unique documents
            v_scores = np.array([vec_doc_to_sim.get(doc, 0.0) for doc in all_docs])
            m_scores = np.array([meta_doc_to_sim.get(doc, 0.0) for doc in all_docs])
            b_scores = np.array([bm25_doc_to_sim.get(doc, 0.0) for doc in all_docs])

            # FULLY VECTORIZED COMPUTATION OF HYBRID SCORES
            # Stack the score arrays into a matrix of shape (3, N)
            sim_matrix = np.stack([v_scores, b_scores, m_scores], axis=0)

            # Create weight vector of shape (3, 1)
            weights = np.array([self.alpha, self.beta, self.gamma])[:, None]

            # Compute hybrid scores with one matrix operation
            hybrid_scores = (weights * sim_matrix).sum(axis=0)

            # Get indices of top-k scores
            top_k_indices = np.argsort(-hybrid_scores)[:self.k]

            # Create final results
            results = []
            debug_print("\n=== FINAL SELECTED DOCUMENTS ===")

            for i, idx in enumerate(top_k_indices):
                doc = all_docs[idx]
                score = float(hybrid_scores[idx])

                # Get metadata (prioritize vector metadata if available)
                meta = vec_doc_to_meta.get(doc) or meta_doc_to_meta.get(doc) or bm25_doc_to_meta.get(doc) or {}

                # Make a copy to avoid modifying original metadata
                if meta:
                    meta = meta.copy()
                else:
                    meta = {}

                # Add score components to metadata
                meta.update({
                    "vector_score": float(v_scores[idx]),
                    "bm25_score": float(b_scores[idx]),
                    "metadata_score": float(m_scores[idx]),
                    "hybrid_score": score
                })

                # Print document details (limited to first 10)
                if i < 10:
                    doc_preview = doc[:50] + "..." if doc and len(doc) > 50 else doc
                    source = meta.get('source', 'unknown')
                    doc_type = meta.get('document_type', 'unknown')
                    debug_print(f"Document {i + 1}: Score={score:.4f}, Source={source}, Type={doc_type}")
                    debug_print(f"  Preview: {doc_preview}")

                # Add to results
                results.append(Document(page_content=doc, metadata=meta))

            doc_count = len(results)
            if doc_count > 10:
                debug_print(f"  ... and {doc_count - 10} more documents (not shown)")

            return results

    def get_relevant_documents(self, query: str):
        with log_time("Hybrid document retrieval"):
            try:
                with ThreadPoolExecutor(max_workers=3) as exe:
                    vec_f = exe.submit(self.vector_pass, query)
                    meta_f = exe.submit(self.metadata_pass, query)
                    bm25_f = exe.submit(self.bm25_pass, query)
                    vp, mp, bp = vec_f.result(), meta_f.result(), bm25_f.result()
                return self.fuse_results(vp, mp, bp)
            except Exception as e:
                debug_print(f"Error in hybrid search: {str(e)}. Falling back to vector search only.")
                # Fallback to just vector search if there's an error
                try:
                    vp = self.vector_pass(query)
                    docs = []

                    # Apply deduplication to fallback results as well
                    seen_docs = set()

                    # Check if we have valid results
                    if "documents" in vp and vp["documents"] and len(vp["documents"]) > 0:
                        for i, (doc, meta, dist) in enumerate(zip(
                                vp["documents"][0],
                                vp["metadatas"][0] if "metadatas" in vp and vp["metadatas"] else [{}] * len(
                                    vp["documents"][0]),
                                vp["distances"][0] if "distances" in vp and vp["distances"] else [0.0] * len(
                                    vp["documents"][0])
                        )):
                            if doc not in seen_docs:
                                seen_docs.add(doc)
                                # Convert L2 distance to similarity score
                                sim = 1.0 / (1.0 + dist) if dist > 0 else 1.0
                                docs.append(Document(
                                    page_content=doc,
                                    metadata={**(meta or {}), "hybrid_score": sim}
                                ))

                                # Break if we've reached the desired number of results
                                if len(docs) >= self.k:
                                    break

                    return docs
                except Exception as fallback_e:
                    debug_print(f"Fallback vector search also failed: {str(fallback_e)}. Returning empty results.")
                    return []


def create_retrievers(k_chunks=50, k_summaries=50, k_facts=50, alpha=0.5, beta=0.3):
    """
    Create hybrid retrievers that combine vector search, BM25, and keyword search

    Args:
        k_chunks: Number of chunks to retrieve
        k_summaries: Number of summaries to retrieve
        k_facts: Number of key facts to retrieve
        alpha: Weight on semantic (vector) score
        beta: Weight on BM25 score
        gamma (1-alpha-beta): Weight on metadata score

    Returns:
        Tuple of retrievers for chunks, summaries, and key facts
    """
    with log_time("Creating retrievers"):
        # Initialize ChromaDB using the utility class
        debug_print("Connecting to ChromaDB using ChromaDB utility")
        chroma_client = ChromaDB()

        # Get collections
        chunks_coll = chroma_client.get_collection("document_chunks")
        document_summaries_coll = chroma_client.get_collection("document_summaries")
        key_facts_coll = chroma_client.get_collection("key_facts")

        # Create hybrid retrievers
        chunks_qr = ChromaHybridRetriever(chunks_coll, k=k_chunks, alpha=alpha, beta=beta)
        summaries_qr = ChromaHybridRetriever(document_summaries_coll, k=k_summaries, alpha=alpha, beta=beta)
        facts_qr = ChromaHybridRetriever(key_facts_coll, k=k_facts, alpha=alpha, beta=beta)

        return chunks_qr, summaries_qr, facts_qr


# Initialize retrievers with larger retrieval limits
chunks_query_retriever, document_summaries_query_retriever, key_facts_query_retriever = create_retrievers(
    k_chunks=100,
    k_summaries=100,
    k_facts=100,
    alpha=0.5,
    beta=0.3
)


def retrieve_context_per_question(state):
    """
    Retrieves relevant context for a given question. The context is retrieved from the document chunks and document summaries.

    Args:
        state: A dictionary containing the question to answer.
    """
    with log_time("Retrieve context per question"):
        # Retrieve relevant documents
        debug_print("Retrieving relevant chunks...")
        question = state["question"]
        docs = chunks_query_retriever.get_relevant_documents(question)

        # Count unique documents by content
        unique_chunks = set(doc.page_content for doc in docs)
        debug_print(f"DEBUG: Retrieved {len(docs)} document chunks ({len(unique_chunks)} unique chunks)")

        # Format each chunk with metadata
        formatted_chunks = []
        for doc in docs:
            source = doc.metadata.get('source', 'unknown')
            document_type = doc.metadata.get('document_type', 'unknown')
            page = doc.metadata.get('page', 0)

            formatted_chunk = f"CHUNK [Source: {source}, Type: {document_type}"
            if page != 0:
                formatted_chunk += f", Page: {page}"
            formatted_chunk += f"]:\n{doc.page_content}"
            formatted_chunks.append(formatted_chunk)

        # Concatenate document content
        context = "\n\n".join(formatted_chunks)

        debug_print("Retrieving relevant document summaries...")
        docs_summaries = document_summaries_query_retriever.get_relevant_documents(state["question"])

        # Count unique documents by content
        unique_summaries = set(doc.page_content for doc in docs_summaries)
        debug_print(
            f"DEBUG: Retrieved {len(docs_summaries)} document summaries ({len(unique_summaries)} unique summaries)")

        # Format each summary with metadata
        formatted_summaries = []
        for doc in docs_summaries:
            source = doc.metadata.get('source', 'unknown')
            section = doc.metadata.get('section', 'unknown')
            document_type = doc.metadata.get('document_type', 'unknown')

            formatted_summary = f"SUMMARY [Source: {source}, Type: {document_type}, Section: {section}]:\n{doc.page_content}"
            formatted_summaries.append(formatted_summary)

        # Concatenate document summaries
        context_summaries = "\n\n".join(formatted_summaries)

        debug_print("Retrieving relevant key facts...")
        docs_key_facts = key_facts_query_retriever.get_relevant_documents(state["question"])

        # Count unique documents by content
        unique_facts = set(doc.page_content for doc in docs_key_facts)
        debug_print(f"DEBUG: Retrieved {len(docs_key_facts)} key facts ({len(unique_facts)} unique facts)")

        # Format each key fact with metadata
        formatted_facts = []
        for doc in docs_key_facts:
            source = doc.metadata.get('source', 'unknown')
            document_type = doc.metadata.get('document_type', 'unknown')
            page = doc.metadata.get('page', 0)
            score = doc.metadata.get("hybrid_score", 0.0)

            formatted_fact = f"KEY FACT [Source: {source}, Type: {document_type}"
            if page != 0:
                formatted_fact += f", Page: {page}"
            formatted_fact += f", Score: {score:.3f}]:\n{doc.page_content}"
            formatted_facts.append(formatted_fact)

        key_facts = "\n\n".join(formatted_facts)

        # Combine all contexts with clear section separators
        all_contexts = ""
        if context:
            all_contexts += "=== DOCUMENT CHUNKS ===\n\n" + context
        if context_summaries:
            if all_contexts:
                all_contexts += "\n\n"
            all_contexts += "=== DOCUMENT SUMMARIES ===\n\n" + context_summaries
        if key_facts:
            if all_contexts:
                all_contexts += "\n\n"
            all_contexts += "=== KEY FACTS ===\n\n" + key_facts

        all_contexts = escape_quotes(all_contexts)

        return {"context": all_contexts, "question": question}


def create_document_grader_chain():
    """
    Creates a document grader chain that assesses the relevance of a document to a question.

    Returns:
        A chain that grades document relevance.
    """

    class GradeDocument(BaseModel):
        binary_score: str = Field(description="'yes' if relevant, 'no' otherwise")
        explanation: str = Field(description="Brief explanation of why the document is or is not relevant")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "binary_score": "yes",
                        "explanation": "The document directly addresses the question."
                    }
                ]
            }
        }

    class BatchGradeDocuments(BaseModel):
        grades: List[GradeDocument] = Field(description="List of relevance grades for each document")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "grades": [
                            {"binary_score": "yes", "explanation": "Relevant because..."},
                            {"binary_score": "no", "explanation": "Not relevant because..."}
                        ]
                    }
                ]
            }
        }

    document_grader_llm = get_default_llm(task_name="document_grader")

    # Individual document grading prompt
    document_grader_prompt_template = """
    You are a grader assessing the relevance of a document to a question.
    Score 'yes' if it contains information relevant to the question; otherwise 'no'.

    Document:
    {document}

    Question:
    {question}

    Provide a binary score ('yes' or 'no') and a brief explanation of your assessment.
    """

    document_grader_prompt = PromptTemplate(
        template=document_grader_prompt_template,
        input_variables=["document", "question"],
    )

    document_grader_chain = document_grader_prompt | document_grader_llm.with_structured_output(GradeDocument)

    # Batch document grading prompt
    batch_grader_prompt_template = """
    You are a grader assessing the relevance of multiple documents to a question.
    For each document, score 'yes' if it contains information relevant to the question; otherwise 'no'.

    Question:
    {question}

    Documents to grade:
    {documents}

    For each document, provide a binary score ('yes' or 'no') and a brief explanation of your assessment.
    Return your assessment as a list of grades, one for each document in the same order they were provided.
    """

    batch_grader_prompt = PromptTemplate(
        template=batch_grader_prompt_template,
        input_variables=["documents", "question"],
    )

    batch_grader_chain = batch_grader_prompt | document_grader_llm.with_structured_output(BatchGradeDocuments)

    return document_grader_chain, batch_grader_chain


# Create the document grader chains
document_grader_chain, batch_grader_chain = create_document_grader_chain()


def keep_only_relevant_content(state):
    """
    Implements Corrective RAG to filter only relevant content from retrieved documents.
    Uses a two-phase approach:
    1. Programmatic pre-filtering based on hybrid scores
    2. Single LLM review of pre-filtered candidates

    Args:
        state: A dictionary containing the question and context.

    Returns:
        The state with filtered relevant context.
    """
    question = state["question"]
    context = state["context"]

    # DEBUG: Print context length and part of the context
    print(f"DEBUG: Context length: {len(context)} characters")
    print(f"DEBUG: Context snippet: {context[:3000]}..." if context else "DEBUG: Context is empty")

    if not context:
        print("No context provided to filter")
        return {"relevant_context": "", "context": "", "question": question}

    # Define ReviewItem schema for parsing LLM output
    class ReviewItem(BaseModel):
        id: int = Field(description="The numeric position of the document in the list")
        relevant: bool = Field(description="Whether the document is relevant to the query")
        reason: str = Field(description="Brief explanation of why the document is relevant")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "id": 1,
                        "relevant": True,
                        "reason": "Contains key information about the topic."
                    }
                ]
            }
        }

    class ReviewResults(BaseModel):
        results: List[ReviewItem] = Field(description="List of document review results")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "results": [
                            {"id": 1, "relevant": True, "reason": "Contains key information."},
                            {"id": 2, "relevant": False, "reason": "Not related to the query."}
                        ]
                    }
                ]
            }
        }

    # 1) Programmatic pre-filtering - get documents and sort by hybrid score
    # For this example, we'll use the chunks_query_retriever to get documents
    print("Performing programmatic pre-filtering based on hybrid scores...")
    docs = chunks_query_retriever.get_relevant_documents(question)

    # Set the threshold and max number of documents to review
    SCORE_THRESHOLD = 0.3  # Minimum hybrid score to consider
    MAX_DOCS_TO_REVIEW = 25  # Maximum number of documents to send to LLM

    # Filter by score threshold and sort by score
    filtered_docs = [doc for doc in docs if doc.metadata.get("hybrid_score", 0) >= SCORE_THRESHOLD]
    filtered_docs = sorted(filtered_docs, key=lambda d: d.metadata.get("hybrid_score", 0), reverse=True)

    # Limit to top K documents
    filtered_docs = filtered_docs[:MAX_DOCS_TO_REVIEW]

    print(f"After pre-filtering: {len(filtered_docs)} documents selected for LLM review")

    if not filtered_docs:
        print("No documents passed pre-filtering criteria")
        return {"relevant_context": "", "context": context, "question": question}

    # 2) Single "review & label" prompt
    # Format documents for review
    joined_docs = "\n\n---\n\n".join(
        f"{i + 1}. {doc.page_content}" for i, doc in enumerate(filtered_docs)
    )

    review_prompt = PromptTemplate(
        template="""
You are given {count} document excerpts and a question:

Question:
{question}

Documents:
{joined_docs}

For each excerpt, determine if it contains information relevant to answering the question.
Output a JSON array of objects with:
- id: the numeric position in the list (1-{count})
- relevant: true/false
- reason: one-sentence explanation if relevant

Return only the JSON array.
""",
        input_variables=["count", "question", "joined_docs"]
    )

    print("Sending pre-filtered documents for LLM review...")
    llm = get_default_llm(task_name="review_chain")
    review_chain = review_prompt | llm.with_structured_output(ReviewResults)

    review_result = review_chain.invoke({
        "count": len(filtered_docs),
        "question": question,
        "joined_docs": joined_docs
    })

    # 3) Pull out the "relevant==true" docs
    relevant_items = [item for item in review_result.results if item.relevant]
    print(f"LLM identified {len(relevant_items)} relevant documents")

    # for item in relevant_items:
    #     print(f"Document {item.id} is relevant: {item.reason}")

    # Get the actual document content for relevant items
    relevant_docs = [filtered_docs[item.id - 1] for item in relevant_items]

    # Format each relevant document with its metadata
    formatted_relevant_docs = []
    for doc in relevant_docs:
        source = doc.metadata.get('source', 'unknown')
        document_type = doc.metadata.get('document_type', 'unknown')
        page = doc.metadata.get('page', 0)
        score = doc.metadata.get('hybrid_score', 0.0)

        formatted_doc = f"DOCUMENT [Source: {source}, Type: {document_type}"
        if page != 0:
            formatted_doc += f", Page: {page}"
        formatted_doc += f", Score: {score:.3f}]:\n{doc.page_content}"
        formatted_relevant_docs.append(formatted_doc)

    # Combine the relevant chunks
    relevant_content = "\n\n".join(formatted_relevant_docs)
    relevant_content = escape_quotes(relevant_content)

    # DEBUG: Print relevant content length and part of the content
    print(f"DEBUG: Relevant content length: {len(relevant_content)} characters")
    print(
        f"DEBUG: Relevant content snippet: {relevant_content[:3000]}..." if relevant_content else "DEBUG: Relevant content is empty")

    return {"relevant_context": relevant_content, "context": context, "question": question}


def create_question_answer_from_context_cot_chain():
    class QuestionAnswerFromContext(BaseModel):
        answer_based_on_content: str = Field(description="generates an answer to a query based on a given context.")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "answer_based_on_content": "This is an example answer based on the provided context."
                    }
                ]
            }
        }

    question_answer_from_context_llm = get_default_llm(task_name="question_answer_from_context_llm")

    question_answer_cot_prompt_template = """ 
    Examples of Chain-of-Thought Reasoning

    Example 1

    Context: The rebate structure offers a 20% base rebate off WAC for every Covered Claim, with potential increases to 25% and 30% if quarterly market shares exceed 75% and 80%, respectively.
    Question: What is the maximum rebate percentage available?
    Reasoning Chain:
    The context mentions a base rebate of 20% off WAC for every Covered Claim
    It states there are potential increases to 25% if quarterly market shares exceed 75%
    And further increases to 30% if quarterly market shares exceed 80%
    So the rebate percentages mentioned are 20%, 25%, and 30%
    Therefore, the maximum rebate percentage available is 30%

    Example 2
    Context: The Budget-Cap Expenditure Agreement between GlobalCare Alliance and PharmaCo Inc. for ImmunoBoost™ is effective from January 1, 2025, to December 31, 2028. Under this agreement, if annual spending is below 90% of the cap, the payer pays a 5% fee on the shortfall.
    Question: What happens if spending is below 90% of the cap?
    Reasoning Chain:
    The context describes a Budget-Cap Expenditure Agreement for ImmunoBoost™
    It specifies what happens when annual spending is below 90% of the cap
    In that case, the payer (GlobalCare Alliance) must pay a fee
    The fee is calculated as 5% of the shortfall (the difference between 90% of the cap and actual spending)
    So if spending is below 90% of the cap, the payer pays a 5% fee on the shortfall

    Example 3 
    Context: The Exclusive Formulary Access Agreement between MedVista Health Plans and PharmaCo Inc. for OncoSure™ runs from March 1, 2024, to February 28, 2027.
    Question: Why did MedVista Health Plans agree to the exclusive formulary placement?
    Reasoning Chain:
    The context states that there is an Exclusive Formulary Access Agreement between MedVista Health Plans and PharmaCo Inc. for OncoSure™
    It mentions the agreement period from March 1, 2024, to February 28, 2027
    However, the context does not provide any information about why MedVista Health Plans agreed to the exclusive formulary placement
    There are no details about MedVista's motivations, benefits they receive, or the reasoning behind their decision
    Without additional context about MedVista's decision-making process, there is no way to determine why they agreed to the exclusive formulary placement

    For the question below, provide your answer by first showing your step-by-step reasoning process, breaking down the problem into a chain of thought before arriving at the final answer,
    just like in the previous examples.

    Context
    {context}
    Question
    {question}
    """

    question_answer_from_context_cot_prompt = PromptTemplate(
        template=question_answer_cot_prompt_template,
        input_variables=["context", "question", "persona_instructions"],
    )
    question_answer_from_context_cot_chain = question_answer_from_context_cot_prompt | question_answer_from_context_llm.with_structured_output(
        QuestionAnswerFromContext)
    return question_answer_from_context_cot_chain


question_answer_from_context_cot_chain = create_question_answer_from_context_cot_chain()


def answer_question_from_context(state):
    """
    Answers a question from a given context.

    Args:
        question: The query question.
        context: The context to answer the question from.
        chain: The LLMChain instance.

    Returns:
        The answer to the question from the context.
    """
    with log_time("Answer question from context"):
        question = state["question"]
        context = state["aggregated_context"] if "aggregated_context" in state else state["context"]

        # Get persona instructions if available
        persona_instructions = ""
        if "persona" in state and state["persona"]:
            persona = get_persona(state["persona"])
            if persona:
                persona_instructions = persona.instructions

                debug_print(f"Using {persona.name} persona instructions for answer generation")

        input_data = {
            "question": question,
            "context": context,
            "persona_instructions": persona_instructions
        }
        debug_print("Answering the question from the retrieved context...")

        output = question_answer_from_context_cot_chain.invoke(input_data)
        answer = output.answer_based_on_content
        debug_print(f'answer before checking hallucination: {answer}')
        return {"answer": answer, "context": context, "question": question}


def create_final_answer_chain():
    class FinalAnswer(BaseModel):
        final_answer: str = Field(
            description="The final, concise answer to the user's question based on the provided context.")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "final_answer": "This is a concise final answer to the user's question."
                    }
                ]
            }
        }

    final_answer_llm = get_default_llm(task_name="final_answer_llm")

    final_answer_prompt_template = """ 
    Your task is to answer the user question based on the provided context and following the Persona Instructions.

    The context may contain information from multiple sources, indicated by "SOURCE:" markers. When answering:
    1. Consider sources in the context
    2. Compare and contrast information across different sources when appropriate
    3. Mention specific sources in your answer when providing source-specific information
    4. Synthesize information from multiple sources into a coherent response
    5. If sources provide conflicting information, acknowledge this and explain the differences
    6. Your answer should have a 2-3 explanation for each source-specific information.

    Persona Instructions:
    {persona_instructions}

    Context:
    {context}

    Question:
    {question}

    Final Answer:
    <your answer here>
    """

    final_answer_prompt = PromptTemplate(
        template=final_answer_prompt_template,
        input_variables=["context", "question", "persona_instructions"],
    )
    final_answer_chain = final_answer_prompt | final_answer_llm.with_structured_output(FinalAnswer)
    return final_answer_chain


final_answer_chain = create_final_answer_chain()


def final_answer_from_context(state):
    """
    Answers a question from a given context.

    Args:
        question: The query question.
        context: The context to answer the question from.
        chain: The LLMChain instance.

    Returns:
        The answer to the question from the context.
    """
    with log_time("Generate final answer"):
        question = state["question"]
        context = state["aggregated_context"] if "aggregated_context" in state else state["context"]

        # Get persona instructions if available
        persona_instructions = ""
        if "persona" in state and state["persona"]:
            persona = get_persona(state["persona"])
            if persona:
                persona_instructions = persona.instructions

                debug_print(f"Using {persona.name} persona instructions for answer generation")

        input_data = {
            "question": question,
            "context": context,
            "persona_instructions": persona_instructions
        }
        debug_print("Generating the final answer...")

        output = final_answer_chain.invoke(input_data)
        answer = output.final_answer
        debug_print(f'answer before checking hallucination: {answer}')
        return {"answer": answer, "context": context, "question": question}


def create_is_relevant_content_chain():
    is_relevant_content_prompt_template = """You receive a user question: {query} and context snippets with their hybrid scores: {context}. 

    Determine if these snippets directly or indirectly help answer the question. Analyze the content carefully and provide:
    1. A boolean "is_relevant" field (true/false) indicating if the content is relevant
    2. A numerical "relevance_score" between 0.0 and 1.0 (where 1.0 is highly relevant)
    3. A brief explanation of your assessment

    Even partial relevance should be considered - if the content contains ANY information that helps answer the question, it should be marked as relevant.
    """

    class Relevance(BaseModel):
        is_relevant: bool = Field(description="Whether the document is relevant to the query.")
        relevance_score: float = Field(description="Relevance score from 0.0 to 1.0, where 1.0 is highly relevant.")
        explanation: str = Field(description="An explanation of why the document is relevant or not.")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "is_relevant": True,
                        "relevance_score": 0.85,
                        "explanation": "The document directly addresses the key aspects of the query."
                    }
                ]
            }
        }

    is_relevant_llm = get_default_llm(task_name="is_relevant_llm")

    is_relevant_content_prompt = PromptTemplate(
        template=is_relevant_content_prompt_template,
        input_variables=["query", "context"],
    )
    is_relevant_content_chain = is_relevant_content_prompt | is_relevant_llm.with_structured_output(Relevance)
    return is_relevant_content_chain


is_relevant_content_chain = create_is_relevant_content_chain()


def is_relevant_content(state):
    """
    Determines if the document is relevant to the query.

    Args:
        question: The query question.
        context: The context to determine relevance.
    """

    question = state["question"]
    context = state["context"]

    # DEBUG: Print question and context length
    print(f"DEBUG: Question being evaluated: {question}")
    print(f"DEBUG: Context length for relevance check: {len(context)} characters")

    input_data = {
        "query": question,
        "context": context
    }

    # Invoke the chain to determine if the document is relevant
    output = is_relevant_content_chain.invoke(input_data)
    print("Determining if the document is relevant...")

    # DEBUG: Print explanation from the relevance check
    print(f"DEBUG: Relevance explanation: {output.explanation}")

    if output.is_relevant == True:
        print("The document is relevant.")
        return "relevant"
    else:
        print("The document is not relevant.")
        return "not relevant"


def create_is_grounded_on_facts_chain():
    class is_grounded_on_facts(BaseModel):
        """
        Output schema for the rewritten question.
        """
        grounded_on_facts: bool = Field(description="Answer is grounded in the facts, 'yes' or 'no'")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "grounded_on_facts": True
                    }
                ]
            }
        }

    is_grounded_on_facts_llm = get_default_llm(task_name="is_grounded_on_facts_llm")
    is_grounded_on_facts_prompt_template = """You are a balanced fact-checker evaluating if an answer is reasonably grounded in the provided context.

    CONTEXT:
    {context}

    ANSWER TO EVALUATE:
    {answer}

    EVALUATION INSTRUCTIONS:
    1. Check if the MAIN factual claims in the answer are supported by the context
    2. Allow for reasonable inferences, generalizations, and synthesized conclusions based on the context
    3. Ignore stylistic differences, rephrasing, or minor elaborations if the core factual content matches
    4. Only flag as hallucination if the answer contains SIGNIFICANT claims that clearly contradict or have no basis in the context
    5. When in doubt, be charitable in your interpretation - if a reasonable person could infer the information from context, consider it grounded

    Return a JSON with a single field "grounded_on_facts" that is TRUE if the answer is reasonably grounded in the context (even with some minor elaboration), and FALSE only if there are significant unsupported claims.
    """
    is_grounded_on_facts_prompt = PromptTemplate(
        template=is_grounded_on_facts_prompt_template,
        input_variables=["context", "answer"],
    )
    is_grounded_on_facts_chain = is_grounded_on_facts_prompt | is_grounded_on_facts_llm.with_structured_output(
        is_grounded_on_facts)
    return is_grounded_on_facts_chain


def create_can_be_answered_chain():
    can_be_answered_prompt_template = """You receive a query: {question} and a context: {context}. 
    You need to determine if the question can be fully answered based on the context."""

    class QuestionAnswer(BaseModel):
        can_be_answered: bool = Field(description="binary result of whether the question can be fully answered or not")
        explanation: str = Field(description="An explanation of why the question can be fully answered or not.")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "can_be_answered": True,
                        "explanation": "The context contains all necessary information to answer the question."
                    }
                ]
            }
        }

    # can_be_answered_json_parser = JsonOutputParser(pydantic_object=QuestionAnswer)

    answer_question_prompt = PromptTemplate(
        template=can_be_answered_prompt_template,
        input_variables=["question", "context"],
        # partial_variables={"format_instructions": can_be_answered_json_parser.get_format_instructions()},
    )

    # can_be_answered_llm = ChatGroq(temperature=0, model_name="llama3-70b-8192", groq_api_key=groq_api_key, max_tokens=4000)
    can_be_answered_llm = get_default_llm(task_name="can_be_answered_llm")
    can_be_answered_chain = answer_question_prompt | can_be_answered_llm.with_structured_output(QuestionAnswer)
    return can_be_answered_chain


def create_is_distilled_content_grounded_on_content_chain():
    is_distilled_content_grounded_on_content_prompt_template = """you receive some distilled content: {distilled_content} and the original context: {original_context}.
        you need to determine if the distilled content is grounded on the original context.
        if the distilled content is grounded on the original context, set the grounded field to true.
        if the distilled content is not grounded on the original context, set the grounded field to false."""

    class IsDistilledContentGroundedOnContent(BaseModel):
        grounded: bool = Field(description="Whether the distilled content is grounded on the original context.")
        explanation: str = Field(
            description="An explanation of why the distilled content is or is not grounded on the original context.")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "grounded": True,
                        "explanation": "The distilled content accurately represents the information in the original context."
                    }
                ]
            }
        }

    # is_distilled_content_grounded_on_content_json_parser = JsonOutputParser(pydantic_object=IsDistilledContentGroundedOnContent)

    is_distilled_content_grounded_on_content_prompt = PromptTemplate(
        template=is_distilled_content_grounded_on_content_prompt_template,
        input_variables=["distilled_content", "original_context"],
        # partial_variables={"format_instructions": is_distilled_content_grounded_on_content_json_parser.get_format_instructions()},
    )

    # is_distilled_content_grounded_on_content_llm = ChatGroq(temperature=0, model_name="llama3-70b-8192", groq_api_key=groq_api_key, max_tokens=4000)
    is_distilled_content_grounded_on_content_llm = get_default_llm(
        task_name="is_distilled_content_grounded_on_content_llm")

    is_distilled_content_grounded_on_content_chain = is_distilled_content_grounded_on_content_prompt | is_distilled_content_grounded_on_content_llm.with_structured_output(
        IsDistilledContentGroundedOnContent)
    return is_distilled_content_grounded_on_content_chain


is_distilled_content_grounded_on_content_chain = create_is_distilled_content_grounded_on_content_chain()


def is_distilled_content_grounded_on_content(state):
    pprint("--------------------")

    """
    Determines if the distilled content is grounded on the original context.

    Args:
        distilled_content: The distilled content.
        original_context: The original context.

    Returns:
        Whether the distilled content is grounded on the original context.
    """

    print("Determining if the distilled content is grounded on the original context...")
    distilled_content = state["relevant_context"]
    original_context = state["context"]

    input_data = {
        "distilled_content": distilled_content,
        "original_context": original_context
    }

    output = is_distilled_content_grounded_on_content_chain.invoke(input_data)
    grounded = output.grounded

    if grounded:
        print("The distilled content is grounded on the original context.")
        return "grounded on the original context"
    else:
        print("The distilled content is not grounded on the original context.")
        return "not grounded on the original context"


def retrieve_chunks_context_per_question(state):
    """
    Retrieves relevant context for a given question. The context is retrieved from document chunks.

    Args:
        state: A dictionary containing the question to answer.
    """
    # Retrieve relevant documents
    print("Retrieving relevant chunks...")
    question = state["question"]
    docs = chunks_query_retriever.get_relevant_documents(question)

    # Count unique documents by content
    unique_docs = set(doc.page_content for doc in docs)
    print(f"DEBUG: Retrieved {len(docs)} document chunks ({len(unique_docs)} unique chunks)")

    # Format each chunk with metadata
    formatted_chunks = []
    for doc in docs:
        source = doc.metadata.get('source', 'unknown')
        document_type = doc.metadata.get('document_type', 'unknown')
        page = doc.metadata.get('page', 0)

        formatted_chunk = f"CHUNK [Source: {source}, Type: {document_type}"
        if page != 0:
            formatted_chunk += f", Page: {page}"
        formatted_chunk += f"]:\n{doc.page_content}"
        formatted_chunks.append(formatted_chunk)

    # Concatenate document content
    context = "\n\n".join(formatted_chunks)
    context = escape_quotes(context)
    return {"context": context, "question": question}


def retrieve_summaries_context_per_question(state):
    """
    Retrieves relevant document summaries for a given question.

    Args:
        state: A dictionary containing the question to answer.
    """
    print("Retrieving relevant document summaries...")
    docs_summaries = document_summaries_query_retriever.get_relevant_documents(state["question"])

    # Count unique documents by content
    unique_docs = set(doc.page_content for doc in docs_summaries)
    print(f"DEBUG: Retrieved {len(docs_summaries)} document summaries ({len(unique_docs)} unique summaries)")

    if docs_summaries:
        print(f"DEBUG: First document summary: {docs_summaries[0].page_content[:3000]}...")
        print(f"DEBUG: First document metadata: {docs_summaries[0].metadata}")

    # Format each summary with metadata
    formatted_summaries = []
    for doc in docs_summaries:
        source = doc.metadata.get('source', 'unknown')
        section = doc.metadata.get('section', 'unknown')
        document_type = doc.metadata.get('document_type', 'unknown')

        formatted_summary = f"SUMMARY [Source: {source}, Type: {document_type}, Section: {section}]:\n{doc.page_content}"
        formatted_summaries.append(formatted_summary)

    # Concatenate document summaries
    context_summaries = "\n\n".join(formatted_summaries)
    context_summaries = escape_quotes(context_summaries)

    return {"context": context_summaries, "question": state["question"]}


def retrieve_key_facts_context_per_question(state):
    """
    Retrieves relevant key facts for a given question.

    Args:
        state: A dictionary containing the question to answer.
    """
    print("Retrieving relevant key facts...")
    docs_key_facts = key_facts_query_retriever.get_relevant_documents(state["question"])

    # Count unique documents by content
    unique_docs = set(doc.page_content for doc in docs_key_facts)
    print(f"DEBUG: Retrieved {len(docs_key_facts)} key facts ({len(unique_docs)} unique facts)")

    # Format each key fact with metadata
    entries = []
    for doc in docs_key_facts:
        source = doc.metadata.get('source', 'unknown')
        document_type = doc.metadata.get('document_type', 'unknown')
        page = doc.metadata.get('page', 0)
        score = doc.metadata.get("hybrid_score", 0.0)

        entry = f"KEY FACT [Source: {source}, Type: {document_type}"
        if page != 0:
            entry += f", Page: {page}"
        entry += f", Score: {score:.3f}]:\n{doc.page_content}"
        entries.append(entry)

    key_facts_context = escape_quotes("\n\n".join(entries))
    return {"context": key_facts_context, "question": state["question"]}


class QualitativeRetrievalGraphState(TypedDict):
    """
    Represents the state of our graph.
    """

    question: str
    context: str
    relevant_context: str


def fetch_and_filter_summaries(state):
    """
    1) Retrieve top-K summaries in one call.
    2) Apply programmatic pre-filtering based on hybrid scores.
    3) Send all pre-filtered summaries to LLM in a single call for relevance assessment.
    4) Collect all relevant snippets with their sources.
    """
    with log_time("Fetch and filter summaries"):
        question = state["question"]
        debug_print("Batch-fetching and filtering document summaries...")

        # 1) batch-fetch
        docs = document_summaries_query_retriever.get_relevant_documents(question)

        # Count unique documents by content
        unique_docs = set(doc.page_content for doc in docs)
        debug_print(f"DEBUG: Retrieved {len(docs)} document summaries ({len(unique_docs)} unique documents)")

        if not docs:
            debug_print("No document summaries found")
            return {"relevant_context": "", "context": "", "question": question, "source_count": 0}

        # 2) Programmatic pre-filtering
        # Set the threshold and max number of documents to review
        SCORE_THRESHOLD = 0.0  # Minimum hybrid score to consider (changed from 0.3 to 0.0 to handle normalized scores)
        MAX_DOCS_TO_REVIEW = 50  # Maximum number of documents to send to LLM

        # Filter by score threshold and sort by score
        filtered_docs = [doc for doc in docs if doc.metadata.get("hybrid_score", 0) >= SCORE_THRESHOLD]
        filtered_docs = sorted(filtered_docs, key=lambda d: d.metadata.get("hybrid_score", 0), reverse=True)

        # Limit to top K documents
        filtered_docs = filtered_docs[:MAX_DOCS_TO_REVIEW]

        debug_print(f"After pre-filtering: {len(filtered_docs)} summaries selected for LLM review")

        if not filtered_docs:
            debug_print("No summaries passed pre-filtering criteria")
            return {"relevant_context": "", "context": "", "question": question, "source_count": 0}

    # 3) Single LLM call for relevance assessment
    with log_time("LLM relevance assessment"):
        # Define ReviewItem schema for parsing LLM output
        class ReviewItem(BaseModel):
            id: int = Field(description="The numeric position of the document in the list")
            relevant: bool = Field(description="Whether the document is relevant to the query")
            reason: str = Field(description="Brief explanation of why the document is relevant")

            model_config = {
                "json_schema_extra": {
                    "examples": [
                        {
                            "id": 1,
                            "relevant": True,
                            "reason": "Contains key information about the topic."
                        }
                    ]
                }
            }

        class ReviewResults(BaseModel):
            results: List[ReviewItem] = Field(description="List of document review results")

            model_config = {
                "json_schema_extra": {
                    "examples": [
                        {
                            "results": [
                                {"id": 1, "relevant": True, "reason": "Contains key information."},
                                {"id": 2, "relevant": False, "reason": "Not related to the query."}
                            ]
                        }
                    ]
                }
            }

        # Format documents for review with their IDs
        formatted_docs = []
        for i, doc in enumerate(filtered_docs):
            source = doc.metadata.get('source', 'unknown')
            section = doc.metadata.get('section', 'unknown')
            document_type = doc.metadata.get('document_type', 'unknown')

            formatted_doc = f"{i + 1}. DOCUMENT SUMMARY:\n{doc.page_content}\n\nSource: {source}, Document Type: {document_type}, Section: {section}"
            formatted_docs.append(formatted_doc)

        joined_docs = "\n\n---\n\n".join(formatted_docs)

        review_prompt = PromptTemplate(
            template="""
You are given {count} document summaries and a question:

Question:
{question}

Document summaries:
{joined_docs}

For each summary, determine if it contains information relevant to answering the question.
Output a JSON array of objects with:
- id: the numeric position in the list (1-{count})
- relevant: true/false
- reason: one-sentence explanation if relevant

Return only the JSON array.
""",
            input_variables=["count", "question", "joined_docs"]
        )

        debug_print("Sending pre-filtered summaries for LLM review in a single call...")
        llm = get_default_llm(task_name="review_chain")
        review_chain = review_prompt | llm.with_structured_output(ReviewResults)

        review_result = review_chain.invoke({
            "count": len(filtered_docs),
            "question": question,
            "joined_docs": joined_docs
        })

        # 4) Extract relevant documents
        if isinstance(review_result, dict):
            relevant_items = [item for item in review_result.get('results', []) if item.get('relevant')]
        else:
            relevant_items = [item for item in review_result.results if item.relevant]
        debug_print(f"LLM identified {len(relevant_items)} relevant summaries")

        # for item in relevant_items:
        #     debug_print(f"Summary {item.id} is relevant: {item.reason}")

        # Get the actual document content for relevant items
        relevant_docs = [filtered_docs[item.id - 1] for item in relevant_items]

        # Format each relevant document with its metadata
        formatted_relevant_docs = []
        relevant_sources = set()

        for doc in relevant_docs:
            source = doc.metadata.get('source', 'unknown')
            section = doc.metadata.get('section', 'unknown')
            document_type = doc.metadata.get('document_type', 'unknown')
            score = doc.metadata.get('hybrid_score', 0.0)

            formatted_doc = f"DOCUMENT SUMMARY [Source: {source}, Type: {document_type}, Section: {section}, Score: {score:.3f}]:\n{doc.page_content}"
            formatted_relevant_docs.append(formatted_doc)
            relevant_sources.add(source)

        # Combine all relevant snippets with clear source attribution
        if formatted_relevant_docs:
            debug_print(
                f"Found {len(formatted_relevant_docs)} relevant summaries from {len(relevant_sources)} different sources")
            combined_context = "\n\n---\n\n".join([
                f"SOURCE: {source}\n{doc}"
                for source, doc in
                zip([d.metadata.get('source', 'unknown') for d in relevant_docs], formatted_relevant_docs)
            ])
            return {
                "relevant_context": combined_context,
                "context": combined_context,
                "question": question,
                "source_count": len(relevant_sources)
            }
        else:
            debug_print("No relevant summaries found after LLM review")
            return {"relevant_context": "", "context": "", "question": question, "source_count": 0}


def fetch_and_filter_chunks(state):
    """
    1) Retrieve top-K chunks in one call.
    2) Apply programmatic pre-filtering based on hybrid scores.
    3) Send all pre-filtered chunks to LLM in a single call for relevance assessment.
    4) Collect all relevant snippets with their sources.
    """
    with log_time("Fetch and filter chunks"):
        question = state["question"]
        debug_print("Batch-fetching and filtering document chunks...")

        # 1) batch-fetch
        docs = chunks_query_retriever.get_relevant_documents(question)

        # Count unique documents by content
        unique_docs = set(doc.page_content for doc in docs)
        debug_print(f"DEBUG: Retrieved {len(docs)} document chunks ({len(unique_docs)} unique chunks)")

        if not docs:
            debug_print("No document chunks found")
            return {"relevant_context": "", "context": "", "question": question, "source_count": 0}

        # 2) Programmatic pre-filtering
        # Set the threshold and max number of documents to review
        SCORE_THRESHOLD = 0.0  # Minimum hybrid score to consider (changed from 0.3 to 0.0 to handle normalized scores)
        MAX_DOCS_TO_REVIEW = 25  # Maximum number of documents to send to LLM

        # Filter by score threshold and sort by score
        filtered_docs = [doc for doc in docs if doc.metadata.get("hybrid_score", 0) >= SCORE_THRESHOLD]
        filtered_docs = sorted(filtered_docs, key=lambda d: d.metadata.get("hybrid_score", 0), reverse=True)

        # Limit to top K documents
        filtered_docs = filtered_docs[:MAX_DOCS_TO_REVIEW]

        debug_print(f"After pre-filtering: {len(filtered_docs)} chunks selected for LLM review")

        if not filtered_docs:
            debug_print("No chunks passed pre-filtering criteria")
            return {"relevant_context": "", "context": "", "question": question, "source_count": 0}

    # 3) Single LLM call for relevance assessment
    # Define ReviewItem schema for parsing LLM output
    class ReviewItem(BaseModel):
        id: int = Field(description="The numeric position of the document in the list")
        relevant: bool = Field(description="Whether the document is relevant to the query")
        reason: str = Field(description="Brief explanation of why the document is relevant")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "id": 1,
                        "relevant": True,
                        "reason": "Contains key information about the topic."
                    }
                ]
            }
        }

    class ReviewResults(BaseModel):
        results: List[ReviewItem] = Field(description="List of document review results")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "results": [
                            {"id": 1, "relevant": True, "reason": "Contains key information."},
                            {"id": 2, "relevant": False, "reason": "Not related to the query."}
                        ]
                    }
                ]
            }
        }

    # Format documents for review with their IDs
    formatted_docs = []
    for i, doc in enumerate(filtered_docs):
        source = doc.metadata.get('source', 'unknown')
        document_type = doc.metadata.get('document_type', 'unknown')
        page = doc.metadata.get('page', 0)

        formatted_doc = f"{i + 1}. DOCUMENT CHUNK:\n{doc.page_content}\n\nSource: {source}, Document Type: {document_type}"
        if page != 0:
            formatted_doc += f", Page: {page}"

        formatted_docs.append(formatted_doc)

    joined_docs = "\n\n---\n\n".join(formatted_docs)

    review_prompt = PromptTemplate(
        template="""
You are given {count} document chunks and a question:

Question:
{question}

Document chunks:
{joined_docs}

For each chunk, determine if it contains information relevant to answering the question.
Output a JSON array of objects with:
- id: the numeric position in the list (1-{count})
- relevant: true/false
- reason: one-sentence explanation if relevant

Return only the JSON array.
""",
        input_variables=["count", "question", "joined_docs"]
    )

    print("Sending pre-filtered chunks for LLM review in a single call...")
    llm = get_default_llm(task_name="review_chain")
    review_chain = review_prompt | llm.with_structured_output(ReviewResults)

    review_result = review_chain.invoke({
        "count": len(filtered_docs),
        "question": question,
        "joined_docs": joined_docs
    })

    # 4) Extract relevant documents
    if isinstance(review_result, dict):
        relevant_items = [item for item in review_result.get('results', []) if item.get('relevant')]
    else:
        relevant_items = [item for item in review_result.results if item.relevant]
    print(f"LLM identified {len(relevant_items)} relevant chunks")

    # for item in relevant_items:
    #     print(f"Chunk {item.id} is relevant: {item.reason}")

    # Get the actual document content for relevant items
    relevant_docs = [filtered_docs[item.id - 1] for item in relevant_items]

    # Format each relevant document with its metadata
    formatted_relevant_docs = []
    relevant_sources = set()

    for doc in relevant_docs:
        source = doc.metadata.get('source', 'unknown')
        document_type = doc.metadata.get('document_type', 'unknown')
        page = doc.metadata.get('page', 0)
        score = doc.metadata.get('hybrid_score', 0.0)

        formatted_doc = f"DOCUMENT CHUNK [Source: {source}, Type: {document_type}"
        if page != 0:
            formatted_doc += f", Page: {page}"
        formatted_doc += f", Score: {score:.3f}]:\n{doc.page_content}"
        formatted_relevant_docs.append(formatted_doc)
        relevant_sources.add(source)

    # Combine all relevant snippets with clear source attribution
    if formatted_relevant_docs:
        print(f"Found {len(formatted_relevant_docs)} relevant chunks from {len(relevant_sources)} different sources")
        combined_context = "\n\n---\n\n".join([
            f"SOURCE: {source}\n{doc}"
            for source, doc in
            zip([d.metadata.get('source', 'unknown') for d in relevant_docs], formatted_relevant_docs)
        ])
        return {
            "relevant_context": combined_context,
            "context": combined_context,
            "question": question,
            "source_count": len(relevant_sources)
        }
    else:
        print("No relevant chunks found after LLM review")
        return {"relevant_context": "", "context": "", "question": question, "source_count": 0}


def fetch_and_filter_key_facts(state):
    """
    1) Retrieve top-K key facts in one call.
    2) Apply programmatic pre-filtering based on hybrid scores.
    3) Send all pre-filtered key facts to LLM in a single call for relevance assessment.
    4) Collect all relevant snippets with their sources.
    """
    with log_time("Fetch and filter key facts"):
        question = state["question"]
        debug_print("Batch-fetching and filtering key facts...")

        # 1) batch-fetch
        docs = key_facts_query_retriever.get_relevant_documents(question)

        # Count unique documents by content
        unique_docs = set(doc.page_content for doc in docs)
        debug_print(f"DEBUG: Retrieved {len(docs)} key facts ({len(unique_docs)} unique facts)")

        if not docs:
            debug_print("No key facts found")
            return {"relevant_context": "", "context": "", "question": question, "source_count": 0}

        # 2) Programmatic pre-filtering
        # Set the threshold and max number of documents to review
        SCORE_THRESHOLD = 0.0  # Minimum hybrid score to consider (changed from 0.3 to 0.0 to handle normalized scores)
        MAX_DOCS_TO_REVIEW = 25  # Maximum number of documents to send to LLM

        # Filter by score threshold and sort by score
        filtered_docs = [doc for doc in docs if doc.metadata.get("hybrid_score", 0) >= SCORE_THRESHOLD]
        filtered_docs = sorted(filtered_docs, key=lambda d: d.metadata.get("hybrid_score", 0), reverse=True)

        # Limit to top K documents
        filtered_docs = filtered_docs[:MAX_DOCS_TO_REVIEW]

        debug_print(f"After pre-filtering: {len(filtered_docs)} key facts selected for LLM review")

        if not filtered_docs:
            debug_print("No key facts passed pre-filtering criteria")
            return {"relevant_context": "", "context": "", "question": question, "source_count": 0}

    # 3) Single LLM call for relevance assessment
    # Define ReviewItem schema for parsing LLM output
    class ReviewItem(BaseModel):
        id: int = Field(description="The numeric position of the document in the list")
        relevant: bool = Field(description="Whether the document is relevant to the query")
        reason: str = Field(description="Brief explanation of why the document is relevant")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "id": 1,
                        "relevant": True,
                        "reason": "Contains key information about the topic."
                    }
                ]
            }
        }

    class ReviewResults(BaseModel):
        results: List[ReviewItem] = Field(description="List of document review results")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "results": [
                            {"id": 1, "relevant": True, "reason": "Contains key information."},
                            {"id": 2, "relevant": False, "reason": "Not related to the query."}
                        ]
                    }
                ]
            }
        }

    # Format documents for review with their IDs
    formatted_docs = []
    for i, doc in enumerate(filtered_docs):
        source = doc.metadata.get('source', 'unknown')
        document_type = doc.metadata.get('document_type', 'unknown')
        page = doc.metadata.get('page', 0)
        score = doc.metadata.get("hybrid_score", 0.0)

        formatted_doc = f"{i + 1}. KEY FACT: {doc.page_content}\n\nSource: {source}, Document Type: {document_type}"
        if page != 0:
            formatted_doc += f", Page: {page}"
        formatted_doc += f" [Relevance score: {score:.3f}]"

        formatted_docs.append(formatted_doc)

    joined_docs = "\n\n---\n\n".join(formatted_docs)

    review_prompt = PromptTemplate(
        template="""
You are given {count} key facts and a question:

Question:
{question}

Key facts:
{joined_docs}

For each key fact, determine if it contains information relevant to answering the question.
Output a JSON array of objects with:
- id: the numeric position in the list (1-{count})
- relevant: true/false
- reason: one-sentence explanation if relevant

Return only the JSON array.
""",
        input_variables=["count", "question", "joined_docs"]
    )

    print("Sending pre-filtered key facts for LLM review in a single call...")
    llm = get_default_llm(task_name="review_chain")
    review_chain = review_prompt | llm.with_structured_output(ReviewResults)

    review_result = review_chain.invoke({
        "count": len(filtered_docs),
        "question": question,
        "joined_docs": joined_docs
    })

    # 4) Extract relevant documents
    relevant_items = [item for item in review_result.results if item.relevant]
    print(f"LLM identified {len(relevant_items)} relevant key facts")

    # for item in relevant_items:
    #     print(f"Key fact {item.id} is relevant: {item.reason}")

    # Get the actual document content for relevant items
    relevant_docs = [filtered_docs[item.id - 1] for item in relevant_items]

    # Format each relevant document with its metadata
    formatted_relevant_docs = []
    relevant_sources = set()

    for doc in relevant_docs:
        source = doc.metadata.get('source', 'unknown')
        document_type = doc.metadata.get('document_type', 'unknown')
        page = doc.metadata.get('page', 0)
        score = doc.metadata.get('hybrid_score', 0.0)

        formatted_doc = f"KEY FACT [Source: {source}, Type: {document_type}"
        if page != 0:
            formatted_doc += f", Page: {page}"
        formatted_doc += f", Score: {score:.3f}]:\n{doc.page_content}"
        formatted_relevant_docs.append(formatted_doc)
        relevant_sources.add(source)

    # Combine all relevant snippets with clear source attribution
    if formatted_relevant_docs:
        print(f"Found {len(formatted_relevant_docs)} relevant key facts from {len(relevant_sources)} different sources")
        combined_context = "\n\n---\n\n".join([
            f"SOURCE: {source}\n{doc}"
            for source, doc in
            zip([d.metadata.get('source', 'unknown') for d in relevant_docs], formatted_relevant_docs)
        ])
        return {
            "relevant_context": combined_context,
            "context": combined_context,
            "question": question,
            "source_count": len(relevant_sources)
        }
    else:
        print("No relevant key facts found after LLM review")
        return {"relevant_context": "", "context": "", "question": question, "source_count": 0}


def create_qualitative_document_chunks_retrieval_workflow_app():
    """
    Creates a qualitative document chunks retrieval workflow app.

    Returns:
        The compiled qualitative document chunks retrieval workflow app.
    """
    # Create a new graph
    qualitative_chunks_retrieval_workflow = StateGraph(QualitativeRetrievalGraphState)

    # Define the nodes - replace the two-node pattern with a single node
    qualitative_chunks_retrieval_workflow.add_node("fetch_and_filter_chunks", fetch_and_filter_chunks)

    # Build the graph
    qualitative_chunks_retrieval_workflow.set_entry_point("fetch_and_filter_chunks")

    # Simple edge to END - no conditional logic or loops
    qualitative_chunks_retrieval_workflow.add_edge("fetch_and_filter_chunks", END)

    qualitative_chunks_retrieval_workflow_app = qualitative_chunks_retrieval_workflow.compile()
    return qualitative_chunks_retrieval_workflow_app


def create_qualitative_document_summaries_retrieval_workflow_app():
    """
    Creates a qualitative document summaries retrieval workflow app.

    Returns:
        The compiled qualitative document summaries retrieval workflow app.
    """
    # Create a new graph
    qualitative_summaries_retrieval_workflow = StateGraph(QualitativeRetrievalGraphState)

    # Define the nodes - replace the two-node pattern with a single node
    qualitative_summaries_retrieval_workflow.add_node("fetch_and_filter_summaries", fetch_and_filter_summaries)

    # Build the graph
    qualitative_summaries_retrieval_workflow.set_entry_point("fetch_and_filter_summaries")

    # Simple edge to END - no conditional logic or loops
    qualitative_summaries_retrieval_workflow.add_edge("fetch_and_filter_summaries", END)

    qualitative_summaries_retrieval_workflow_app = qualitative_summaries_retrieval_workflow.compile()
    return qualitative_summaries_retrieval_workflow_app


def create_qualitative_key_facts_retrieval_workflow_app():
    """
    Creates a qualitative key facts retrieval workflow app.

    Returns:
        The compiled qualitative key facts retrieval workflow app.
    """
    # Create a new graph
    qualitative_key_facts_retrieval_workflow = StateGraph(QualitativeRetrievalGraphState)

    # Define the nodes - replace the two-node pattern with a single node
    qualitative_key_facts_retrieval_workflow.add_node("fetch_and_filter_key_facts", fetch_and_filter_key_facts)

    # Build the graph
    qualitative_key_facts_retrieval_workflow.set_entry_point("fetch_and_filter_key_facts")

    # Simple edge to END - no conditional logic or loops
    qualitative_key_facts_retrieval_workflow.add_edge("fetch_and_filter_key_facts", END)

    qualitative_key_facts_retrieval_workflow_app = qualitative_key_facts_retrieval_workflow.compile()
    return qualitative_key_facts_retrieval_workflow_app


is_grounded_on_facts_chain = create_is_grounded_on_facts_chain()


def is_answer_grounded_on_context(state):
    """Determines if the answer to the question is grounded in the facts.

    Args:
        state: A dictionary containing the context and answer.
    """
    print("Checking if the answer is grounded in the facts...")
    context = state["context"]
    answer = state["answer"]

    result = is_grounded_on_facts_chain.invoke({"context": context, "answer": answer})
    grounded_on_facts = result.grounded_on_facts

    # Add a retry counter to the state if it doesn't exist
    if "hallucination_check_count" not in state:
        state["hallucination_check_count"] = 0

    state["hallucination_check_count"] += 1

    if not grounded_on_facts:
        print("The answer is considered a hallucination.")
        print(f"Hallucination check count: {state['hallucination_check_count']}")

        # If we've tried multiple times, provide a warning
        if state["hallucination_check_count"] >= 3:
            print("WARNING: Multiple hallucination checks have failed. The system may be caught in a loop.")
            print("Consider reviewing the context or allowing the current answer if it seems reasonable.")
            # After 5 attempts, accept the answer anyway to break potential loops
            if state["hallucination_check_count"] >= 5:
                print("BREAKING POTENTIAL LOOP: Accepting answer after multiple attempts")
                return "grounded on context"

        return "hallucination"
    else:
        print("The answer is grounded in the facts.")
        return "grounded on context"


def create_qualitative_answer_workflow_app():
    class QualitativeAnswerGraphState(TypedDict):
        """
        Represents the state of our graph.

        """

        question: str
        context: str
        answer: str
        persona: Optional[str]
        hallucination_check_count: Optional[int]

    qualitative_answer_workflow = StateGraph(QualitativeAnswerGraphState)

    # Define the nodes

    qualitative_answer_workflow.add_node("answer_question_from_context", answer_question_from_context)

    # Build the graph
    qualitative_answer_workflow.set_entry_point("answer_question_from_context")

    qualitative_answer_workflow.add_conditional_edges(
        "answer_question_from_context", is_answer_grounded_on_context,
        {"hallucination": "answer_question_from_context", "grounded on context": END}

    )

    qualitative_answer_workflow_app = qualitative_answer_workflow.compile()
    return qualitative_answer_workflow_app


class PlanExecute(TypedDict):
    curr_state: str
    question: str
    anonymized_question: str
    query_to_retrieve_or_answer: str
    plan: List[str]
    past_steps: List[str]
    mapping: dict
    curr_context: str
    aggregated_context: str
    tool: str
    response: str
    persona: Optional[str]
    # Track retrieval operations
    retrieval_sources_used: List[str]
    all_sources_exhausted: bool


class Plan(BaseModel):
    """Plan to follow in future"""

    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "steps": ["Step 1: Research X", "Step 2: Analyze Y", "Step 3: Conclude Z"]
                }
            ]
        }
    }


def create_plan_chain():
    planner_prompt = """ For the given query {question}, come up with a focused, streamlined plan to find the answer.

    Create a plan with 3-4 key steps that will efficiently lead to the correct answer. Focus on:

    1. Identifying the CORE information needed (not every possible detail)
    2. Grouping related information needs into single steps
    3. Eliminating redundant or tangential research steps
    4. Ensuring the final step synthesizes the findings into an answer

    Each step should be clear, specific, and directly contribute to answering the query.
    Avoid creating separate steps for closely related information - consolidate them.

    The result of the final step should be the complete answer to the query.

    """

    planner_prompt = PromptTemplate(
        template=planner_prompt,
        input_variables=["question"],
    )

    planner_llm = get_default_llm(task_name="planner")

    planner = planner_prompt | planner_llm.with_structured_output(Plan)
    return planner


def create_break_down_plan_chain():
    break_down_plan_prompt_template = """You receive a plan {plan} which contains a series of steps to follow in order to answer a query. 
    You need to optimize and streamline this plan according to these guidelines:

    1. Every step must be executable by either:
        i. retrieving relevant information from a vector store of document chunks
        ii. retrieving relevant information from a vector store of document summaries
        iii. retrieving relevant information from a vector store of key facts
        iv. answering a question from a given context.

    2. CONSOLIDATE STEPS: Combine related steps to minimize the number of separate retrievals.
       - If two or more steps use the same vector store and target the same topic or same kind of clause, merge them into one.
        - Example: If your draft plan has two steps that both "retrieve from document chunks" about data security or HIPAA, merge them into a single "retrieve from document chunks" step that covers both identifying the standards **and** finding contract examples.
       - Aim for maximum 3-4 total unique RETRIEVAL FROM VECTOR STORE steps in the final plan

    3. CRITICAL: Each step MUST EXPLICITLY mention which vector store to use:
       - Use phrases like "retrieve from document chunks", "search in document summaries", or "find in key facts"
       - FINAL STEP: Always end with a single "answer from aggregated context" step that formulates the final response. (This will be the only answer synthesis step)
       - For the FINAL ANSWER STEP, specify that the answer should be generated "from the aggregated context"

    4. Follow these guidelines for choosing the appropriate vector store for each step:
       - Use "document chunks" when you need detailed, specific information or examples
       - Use "document summaries" when you need high-level overviews or general information
       - Use "key facts" when you need concise data points, definitions, or specific facts
       - Choose the most appropriate store for each information need
       - You may use different stores for different steps based on the specific information required

    Output a streamlined plan with 3-4 total steps, ensuring each step clearly states which vector store to use.
    """

    break_down_plan_prompt = PromptTemplate(
        template=break_down_plan_prompt_template,
        input_variables=["plan"],
    )

    break_down_plan_llm = get_default_llm(task_name="break_down_plan")

    break_down_plan_chain = break_down_plan_prompt | break_down_plan_llm.with_structured_output(Plan)

    return break_down_plan_chain


def create_replanner_chain():
    # class ActPossibleResults(BaseModel):
    #     """Possible results of the action."""
    #     plan: Plan = Field(description="Plan to follow in future.")
    #     explanation: str = Field(description="Explanation of the action.")

    # act_possible_results_parser = JsonOutputParser(pydantic_object=ActPossibleResults)

    replanner_prompt_template = """ For the given objective, create a focused, streamlined plan to find the answer.

    Create a plan with 3-4 key steps that will efficiently lead to the correct answer. Focus on:

    1. Identifying what CORE information is still missing from the context
    2. Consolidating related information needs into single steps
    3. Eliminating redundant or tangential research steps
    4. Ensuring the final step synthesizes the findings into an answer

    IMPORTANT: For each retrieval step, explicitly specify which vector store to use:
    - Use "document chunks" when you need detailed, specific information or examples
    - Use "document summaries" when you need high-level overviews or general information
    - Use "key facts" when you need concise data points, definitions, or specific facts
    - Choose the most appropriate store for each information need based on what it contains

    Your objective was this:
    {question}

    Your original plan was this:
    {plan}

    You have currently done the follow steps:
    {past_steps}

    You already have the following context:
    {aggregated_context}

    Update your plan with ONLY the minimum necessary steps to complete the task.
    Do not return previously done steps as part of the plan.
    If you have sufficient information, include just one step: "Answer the question from the aggregated context"

    the format is json so escape quotes and new lines.

    """

    replanner_prompt = PromptTemplate(
        template=replanner_prompt_template,
        input_variables=["question", "plan", "past_steps", "aggregated_context"],
        # partial_variables={"format_instructions": act_possible_results_parser.get_format_instructions()},
    )

    replanner_llm = get_default_llm(task_name="replanner")

    replanner = replanner_prompt | replanner_llm.with_structured_output(Plan)
    return replanner


def create_task_handler_chain():
    tasks_handler_prompt_template = """You are a task handler that determines which tool to use for the current task: {curr_task}

    Available tools:
    - retrieve_chunks: Retrieves detailed information from document chunks
    - retrieve_summaries: Retrieves high-level overviews from document summaries
    - retrieve_key_facts: Retrieves specific data points from key facts
    - answer_from_context: Generates an answer using the aggregated context

    Selection rules:
    1. If the task mentions "document chunks" → use retrieve_chunks
    2. If the task mentions "document summaries" → use retrieve_summaries
    3. If the task mentions "key facts" → use retrieve_key_facts
    4. If the task mentions "answer", "synthesize", "aggregated context" → use answer_from_context
    5. Final steps in plans typically require answer_from_context, not more retrieval

    For retrieval tools (retrieve_chunks, retrieve_summaries, retrieve_key_facts):
    - Formulate a focused query targeting the specific information needed
    - Set curr_context to an empty string

    For answer_from_context:
    - Use the question as the query
    - Set curr_context to the aggregated context

    Context:
    - Past steps: {past_steps}
    - Original question: {question}
    """

    class TaskHandlerOutput(BaseModel):
        """Output schema for the task handler."""
        query: str = Field(
            description="The query to be either retrieved from the vector store, or the question that should be answered from context.")
        curr_context: str = Field(description="The context to be based on in order to answer the query.")
        tool: str = Field(
            description="The tool to be used should be either retrieve_chunks, retrieve_summaries, retrieve_key_facts, or answer_from_context.")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "query": "What are the key features of Product X?",
                        "curr_context": "",
                        "tool": "retrieve_chunks"
                    }
                ]
            }
        }

    task_handler_prompt = PromptTemplate(
        template=tasks_handler_prompt_template,
        input_variables=["curr_task", "aggregated_context", "past_steps", "question"],
    )

    task_handler_llm = get_default_llm(task_name="task_handler")
    task_handler_chain = task_handler_prompt | task_handler_llm.with_structured_output(TaskHandlerOutput)
    return task_handler_chain


def create_anonymize_question_chain():
    class AnonymizeQuestion(BaseModel):
        """Anonymized question and mapping."""
        anonymized_question: str = Field(description="Anonymized question.")
        mapping: dict = Field(description="Mapping of original name entities to variables.")
        explanation: str = Field(description="Explanation of the action.")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "anonymized_question": "What is X?",
                        "mapping": {"X": "ProductName"},
                        "explanation": "Replaced product name with variable X."
                    }
                ]
            }
        }

    anonymize_question_parser = JsonOutputParser(pydantic_object=AnonymizeQuestion)

    anonymize_question_prompt_template = """ You are a question anonymizer. The input You receive is a string containing several words that
    construct a question {question}. Your goal is to changes all name entities in the input to variables, and remember the mapping of the original name entities to the variables.
    ```example1:
            if the input is \"what is ImmunoBoost?\" the output should be \"what is X?\" and the mapping should be {{\"X\": \"ImmunoBoost\"}} ```
    ```example2:
            if the input is \"how does CardioVance work with GlobalCare Alliance and PharmaCo Inc?\"
            the output should be \"how does X work with Y and Z?\" and the mapping should be {{\"X\": \"CardioVance\", \"Y\": \"GlobalCare Alliance\", \"Z\": \"PharmaCo Inc\"}}```
    you must replace all name entities in the input with variables, and remember the mapping of the original name entities to the variables.
    output the anonymized question and the mapping as two separate fields in a json format as described here, without any additional text apart from the json format.
   """

    anonymize_question_prompt = PromptTemplate(
        template=anonymize_question_prompt_template,
        input_variables=["question"],
        partial_variables={"format_instructions": anonymize_question_parser.get_format_instructions()},
    )

    anonymize_question_llm = get_default_llm(task_name="anonymize_question")
    anonymize_question_chain = anonymize_question_prompt | anonymize_question_llm | anonymize_question_parser
    return anonymize_question_chain


def create_deanonymize_plan_chain():
    class DeAnonymizePlan(BaseModel):
        """Possible results of the action."""
        plan: List[str] = Field(
            description="Plan to follow in future. with all the variables replaced with the mapped words.")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "plan": ["Research ProductName features", "Analyze ProductName pricing"]
                    }
                ]
            }
        }

    de_anonymize_plan_prompt_template = """ you receive a list of tasks: {plan}, where some of the words are replaced with mapped variables. you also receive
    the mapping for those variables to words {mapping}. replace all the variables in the list of tasks with the mapped words. if no variables are present,
    return the original list of tasks. in any case, just output the updated list of tasks in a json format as described here, without any additional text apart from the
    """

    de_anonymize_plan_prompt = PromptTemplate(
        template=de_anonymize_plan_prompt_template,
        input_variables=["plan", "mapping"],
    )

    de_anonymize_plan_llm = get_default_llm(task_name="de_anonymize_plan")
    de_anonymize_plan_chain = de_anonymize_plan_prompt | de_anonymize_plan_llm.with_structured_output(DeAnonymizePlan)
    return de_anonymize_plan_chain


def create_can_be_answered_already_chain():
    class CanBeAnsweredAlready(BaseModel):
        """Possible results of the action."""
        can_be_answered: bool = Field(
            description="Whether the question can be fully answered or not based on the given context.")

        model_config = {
            "json_schema_extra": {
                "examples": [
                    {
                        "can_be_answered": True
                    }
                ]
            }
        }

    can_be_answered_already_prompt_template = """You receive a query: {question} and a context: {context}.
    You need to determine if the question can be fully answered relying only the given context.
    The only infomation you have and can rely on is the context you received. 
    you have no prior knowledge of the question or the context.
    if you think the question can be answered based on the context, output 'true', otherwise output 'false'.
    """

    can_be_answered_already_prompt = PromptTemplate(
        template=can_be_answered_already_prompt_template,
        input_variables=["question", "context"],
    )

    can_be_answered_already_llm = get_default_llm(task_name="can_be_answered_already_llm")
    can_be_answered_already_chain = can_be_answered_already_prompt | can_be_answered_already_llm.with_structured_output(
        CanBeAnsweredAlready)
    return can_be_answered_already_chain


task_handler_chain = create_task_handler_chain()
qualitative_document_chunks_retrieval_workflow_app = create_qualitative_document_chunks_retrieval_workflow_app()
qualitative_document_summaries_retrieval_workflow_app = create_qualitative_document_summaries_retrieval_workflow_app()
qualitative_key_facts_retrieval_workflow_app = create_qualitative_key_facts_retrieval_workflow_app()
qualitative_answer_workflow_app = create_qualitative_answer_workflow_app()
de_anonymize_plan_chain = create_deanonymize_plan_chain()
planner = create_plan_chain()
break_down_plan_chain = create_break_down_plan_chain()
replanner = create_replanner_chain()
anonymize_question_chain = create_anonymize_question_chain()
can_be_answered_already_chain = create_can_be_answered_already_chain()


def validate_task_handler_decision(curr_task, tool_decision):
    """
    Validates if the task handler's tool decision aligns with the vector store mentioned in the plan step.
    If not, it overrides the decision based on explicit vector store mentions.

    Args:
        curr_task: The current plan step being executed
        tool_decision: The tool decision made by the task handler

    Returns:
        The validated or corrected tool decision
    """
    curr_task_lower = curr_task.lower()

    # Check for explicit vector store mentions in the plan step
    if "document chunks" in curr_task_lower or "from chunks" in curr_task_lower:
        correct_tool = "retrieve_chunks"
    elif "document summaries" in curr_task_lower or "from summaries" in curr_task_lower:
        correct_tool = "retrieve_summaries"
    elif "key facts" in curr_task_lower or "from facts" in curr_task_lower:
        correct_tool = "retrieve_key_facts"
    # Expanded patterns for recognizing answer steps
    elif any(phrase in curr_task_lower for phrase in [
        "answer from", "aggregated context", "synthesize", "final answer",
        "summarize findings", "conclude", "formulate response", "provide answer"
    ]):
        correct_tool = "answer_from_context"
    else:
        # If no explicit mention, log a warning and return the original decision
        debug_print(f"WARNING: No explicit vector store or action mentioned in task: '{curr_task}'")
        return tool_decision

    # If the tool decision doesn't match what's specified in the plan, log and correct it
    if tool_decision != correct_tool:
        debug_print(
            f"CORRECTING TOOL DECISION: Plan specified '{correct_tool}' but task handler chose '{tool_decision}'")

    return correct_tool


def track_plan_execution_alignment(state, curr_task, original_tool, validated_tool):
    """
    Tracks metrics about how well the plan execution aligns with the task handler decisions.

    Args:
        state: The current state of the plan execution
        curr_task: The current plan step being executed
        original_tool: The tool originally selected by the task handler
        validated_tool: The validated/corrected tool to use

    Returns:
        Updated state with alignment metrics
    """
    # Initialize alignment tracking if it doesn't exist
    if "plan_execution_alignment" not in state:
        state["plan_execution_alignment"] = {
            "total_steps": 0,
            "aligned_steps": 0,
            "overridden_steps": 0,
            "alignment_rate": 0.0,
            "details": []
        }

    # Update metrics
    state["plan_execution_alignment"]["total_steps"] += 1

    if original_tool == validated_tool:
        state["plan_execution_alignment"]["aligned_steps"] += 1
        alignment_status = "aligned"
    else:
        state["plan_execution_alignment"]["overridden_steps"] += 1
        alignment_status = "overridden"

    # Calculate alignment rate
    total = state["plan_execution_alignment"]["total_steps"]
    aligned = state["plan_execution_alignment"]["aligned_steps"]
    state["plan_execution_alignment"]["alignment_rate"] = (aligned / total) * 100 if total > 0 else 0.0

    # Record details about this step
    step_details = {
        "task": curr_task,
        "original_tool": original_tool,
        "validated_tool": validated_tool,
        "status": alignment_status
    }
    state["plan_execution_alignment"]["details"].append(step_details)

    # Log alignment information
    debug_print(f"PLAN-EXECUTION ALIGNMENT: Step {total}, Status: {alignment_status.upper()}")
    debug_print(
        f"PLAN-EXECUTION ALIGNMENT: Current alignment rate: {state['plan_execution_alignment']['alignment_rate']:.1f}%")

    return state


def run_task_handler_chain(state: PlanExecute):
    """ Run the task handler chain to decide which tool to use to execute the task.
    Args:
       state: The current state of the plan execution.
    Returns:
       The updated state of the plan execution.
    """
    with log_time("Task handler chain"):
        state["curr_state"] = "task_handler"
        debug_print("the current plan is:")
        debug_print(state["plan"])
        pprint("--------------------")

        # Ensure past_steps is initialized
        if "past_steps" not in state or state["past_steps"] is None:
            state["past_steps"] = []

        curr_task = state["plan"][0]

        inputs = {"curr_task": curr_task,
                  "aggregated_context": state["aggregated_context"],
                  "past_steps": state["past_steps"],
                  "question": state["question"]}

        output = task_handler_chain.invoke(inputs)

        state["past_steps"].append(curr_task)
        state["plan"].pop(0)

        # Always set the query and curr_context from the output
        state["query_to_retrieve_or_answer"] = output.query
        state["curr_context"] = output.curr_context

        # Validate and potentially override the tool decision
        original_tool = output.tool
        validated_tool = validate_task_handler_decision(curr_task, original_tool)

        # Track plan-execution alignment
        state = track_plan_execution_alignment(state, curr_task, original_tool, validated_tool)

        if validated_tool != original_tool:
            debug_print(
                f"Tool decision changed from {original_tool} to {validated_tool} based on plan step requirements")

        # Set the tool based on the validated decision
        if validated_tool == "retrieve_chunks":
            state["tool"] = "retrieve_chunks"
        elif validated_tool == "retrieve_summaries":
            state["tool"] = "retrieve_summaries"
        elif validated_tool == "retrieve_key_facts":
            state["tool"] = "retrieve_key_facts"
        elif validated_tool == "answer_from_context":
            state["tool"] = "answer"
        else:
            raise ValueError(
                "Invalid tool was outputed. Must be either 'retrieve_chunks', 'retrieve_summaries', 'retrieve_key_facts', or 'answer_from_context'")

        return state


def retrieve_or_answer(state: PlanExecute):
    """Decide whether to retrieve or answer the question based on the current state.
    Args:
        state: The current state of the plan execution.
    Returns:
        updates the tool to use .
    """
    state["curr_state"] = "decide_tool"
    print("deciding whether to retrieve or answer")
    if state["tool"] == "retrieve_chunks":
        return "chosen_tool_is_retrieve_chunks"
    elif state["tool"] == "retrieve_summaries":
        return "chosen_tool_is_retrieve_summaries"
    elif state["tool"] == "retrieve_key_facts":
        return "chosen_tool_is_retrieve_key_facts"
    elif state["tool"] == "answer":
        return "chosen_tool_is_answer"
    else:
        raise ValueError("Invalid tool was outputed. Must be either 'retrieve' or 'answer_from_context'")


def run_qualitative_document_chunks_retrieval_workflow(state):
    """
    Run the qualitative document chunks retrieval workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    with log_time("Document chunks retrieval workflow"):
        state["curr_state"] = "retrieve_chunks"
        debug_print("Running the qualitative document chunks retrieval workflow...")
        debug_print("PLAN-EXECUTION ALIGNMENT: Using document_chunks vector store as specified in the plan")
        question = state["query_to_retrieve_or_answer"]
        inputs = {"question": question}

        # Execute the workflow
        output = qualitative_document_chunks_retrieval_workflow_app.invoke(inputs)

        # Track that we've used the chunks source
        if "retrieval_sources_used" not in state:
            state["retrieval_sources_used"] = []
        if "document_chunks" not in state["retrieval_sources_used"]:
            state["retrieval_sources_used"].append("document_chunks")

        # Only append to aggregated context if relevant content was found
        if output['relevant_context']:
            source_count = output.get('source_count', 1)
            if not state["aggregated_context"]:
                state["aggregated_context"] = ""
            else:
                # Add a separator if there's already content
                state["aggregated_context"] += "\n\n--- DOCUMENT CHUNKS ---\n\n"

            state["aggregated_context"] += output['relevant_context']
            debug_print(f"Added relevant chunk content from {source_count} different sources to aggregated context")
        else:
            debug_print("No relevant chunk content found to add to aggregated context")

        return state


def run_qualitative_document_summaries_retrieval_workflow(state):
    """
    Run the qualitative document summaries retrieval workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    with log_time("Document summaries retrieval workflow"):
        state["curr_state"] = "retrieve_summaries"
        debug_print("Running the qualitative document summaries retrieval workflow...")
        debug_print("PLAN-EXECUTION ALIGNMENT: Using document_summaries vector store as specified in the plan")
        question = state["query_to_retrieve_or_answer"]
        inputs = {"question": question}

        # Execute the workflow
        output = qualitative_document_summaries_retrieval_workflow_app.invoke(inputs)

        # Track that we've used the summaries source
        if "retrieval_sources_used" not in state:
            state["retrieval_sources_used"] = []
        if "document_summaries" not in state["retrieval_sources_used"]:
            state["retrieval_sources_used"].append("document_summaries")

        # Only append to aggregated context if relevant content was found
        if output['relevant_context']:
            source_count = output.get('source_count', 1)
            if not state["aggregated_context"]:
                state["aggregated_context"] = ""
            else:
                # Add a separator if there's already content
                state["aggregated_context"] += "\n\n--- DOCUMENT SUMMARIES ---\n\n"

            state["aggregated_context"] += output['relevant_context']
            debug_print(f"Added relevant summary content from {source_count} different sources to aggregated context")
        else:
            debug_print("No relevant summary content found to add to aggregated context")

        return state


def run_qualitative_key_facts_retrieval_workflow(state):
    """
    Run the qualitative key facts retrieval workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    with log_time("Key facts retrieval workflow"):
        state["curr_state"] = "retrieve_key_facts"
        debug_print("Running the qualitative key facts retrieval workflow...")
        debug_print("PLAN-EXECUTION ALIGNMENT: Using key_facts vector store as specified in the plan")
        question = state["query_to_retrieve_or_answer"]
        inputs = {"question": question}

        # Execute the workflow
        output = qualitative_key_facts_retrieval_workflow_app.invoke(inputs)

        # Track that we've used the key facts source
        if "retrieval_sources_used" not in state:
            state["retrieval_sources_used"] = []
        if "key_facts" not in state["retrieval_sources_used"]:
            state["retrieval_sources_used"].append("key_facts")

        # Only append to aggregated context if relevant content was found
        if output['relevant_context']:
            source_count = output.get('source_count', 1)
            if not state["aggregated_context"]:
                state["aggregated_context"] = ""
            else:
                # Add a separator if there's already content
                state["aggregated_context"] += "\n\n--- KEY FACTS ---\n\n"

            state["aggregated_context"] += output['relevant_context']
            debug_print(f"Added relevant key facts content from {source_count} different sources to aggregated context")
        else:
            debug_print("No relevant key facts content found to add to aggregated context")

        return state


def run_qualtative_answer_workflow(state):
    """
    Run the qualitative answer workflow.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated aggregated context.
    """
    state["curr_state"] = "answer"
    print("Running the qualitative answer workflow...")
    question = state["query_to_retrieve_or_answer"]
    context = state["curr_context"]

    # Create a copy of the state with just the required fields for the workflow
    workflow_state = {
        "question": question,
        "context": context
    }

    # Pass persona if available
    if "persona" in state:
        workflow_state["persona"] = state["persona"]

    # Stream through the workflow and capture the answer value
    answer_text = ""
    for output in qualitative_answer_workflow_app.stream(workflow_state):
        for _, val in output.items():
            answer_text = val

    if not state["aggregated_context"]:
        state["aggregated_context"] = ""
    else:
        # Add a separator if there's already content
        state["aggregated_context"] += "\n\n--- INTERMEDIATE ANSWER ---\n\n"
    # Append the captured answer text
    state["aggregated_context"] += answer_text
    return state


def run_qualtative_answer_workflow_for_final_answer(state):
    """
    Run the qualitative answer workflow for the final answer.
    Args:
        state: The current state of the plan execution.
    Returns:
        The state with the updated response.
    """
    state["curr_state"] = "get_final_answer"
    print("Running the qualitative answer workflow for final answer...")
    question = state["question"]
    context = state["aggregated_context"]
    inputs = {"question": question, "context": context}

    # Pass the persona to the state so it can be used in answer_question_from_context
    if "persona" in state:
        print(f"Using {state['persona']} persona for final answer generation")

    for output in final_answer_workflow_app.stream(inputs):
        for _, value in output.items():
            pass
        pprint("--------------------")
    state["response"] = value

    # Stop the pipeline timer when final answer is generated
    stop_pipeline_timer()

    # Record which persona was used in the state
    if "persona" in state:
        state["persona_used"] = state["persona"]

    # Log a summary of the plan-execution alignment
    if "plan_execution_alignment" in state:
        metrics = state["plan_execution_alignment"]
        debug_print("\n=== PLAN-EXECUTION ALIGNMENT SUMMARY ===")
        debug_print(f"Total steps executed: {metrics['total_steps']}")
        debug_print(f"Steps with aligned decisions: {metrics['aligned_steps']} ({metrics['alignment_rate']:.1f}%)")
        debug_print(f"Steps requiring override: {metrics['overridden_steps']}")

        # Add detailed breakdown if there were any overrides
        if metrics['overridden_steps'] > 0:
            debug_print("\nOverridden steps:")
            for i, detail in enumerate(metrics['details']):
                if detail['status'] == 'overridden':
                    debug_print(f"  Step {i + 1}: '{detail['task']}'")
                    debug_print(f"    Original tool: {detail['original_tool']}")
                    debug_print(f"    Corrected to: {detail['validated_tool']}")

        debug_print("==========================================\n")

    return state


def anonymize_queries(state: PlanExecute):
    """
    Anonymizes the question.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the anonymized question and mapping.
    """
    # Start the pipeline timer when anonymize_queries is called
    start_pipeline_timer()

    with log_time("Anonymize queries"):
        state["curr_state"] = "anonymize_question"
        debug_print("state['question']: ", state['question'])
        debug_print("Anonymizing question")
        pprint("--------------------")
        input_values = {"question": state['question']}
        anonymized_question_output = anonymize_question_chain.invoke(input_values)
        debug_print(f'anonymized_question_output: {anonymized_question_output}')
        anonymized_question = anonymized_question_output["anonymized_question"]
        debug_print(f'anonimized_querry: {anonymized_question}')
        pprint("--------------------")
        mapping = anonymized_question_output["mapping"]
        state["anonymized_question"] = anonymized_question
        state["mapping"] = mapping

        # Initialize other required fields if they don't exist
        if "past_steps" not in state:
            state["past_steps"] = []
        if "aggregated_context" not in state:
            state["aggregated_context"] = ""
        if "tool" not in state:
            state["tool"] = ""
        if "query_to_retrieve_or_answer" not in state:
            state["query_to_retrieve_or_answer"] = ""
        if "curr_context" not in state:
            state["curr_context"] = ""
        if "response" not in state:
            state["response"] = ""

        return state


def deanonymize_queries(state: PlanExecute):
    """
    De-anonymizes the plan.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the de-anonymized plan.
    """
    state["curr_state"] = "de_anonymize_plan"
    print("De-anonymizing plan")
    pprint("--------------------")
    deanonimzed_plan = de_anonymize_plan_chain.invoke({"plan": state["plan"], "mapping": state["mapping"]})
    state["plan"] = deanonimzed_plan.plan
    print(f'de-anonimized_plan: {deanonimzed_plan.plan}')
    return state


def plan_step(state: PlanExecute):
    """
    Plans the next step.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the plan.
    """
    with log_time("Plan step"):
        state["curr_state"] = "planner"
        debug_print("Planning step")
        pprint("--------------------")
        plan = planner.invoke({"question": state['anonymized_question']})
        state["plan"] = plan.steps
        debug_print(f'plan: {state["plan"]}')
        return state


def break_down_plan_step(state: PlanExecute):
    """
    Breaks down the plan steps into retrievable or answerable tasks.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the refined plan.
    """
    state["curr_state"] = "break_down_plan"
    print("Breaking down plan steps into retrievable or answerable tasks")
    pprint("--------------------")
    refined_plan = break_down_plan_chain.invoke(state["plan"])
    state["plan"] = refined_plan.steps
    return state


def replan_step(state: PlanExecute):
    """
    Replans the next step based on what information is still needed.
    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with the plan.
    """
    state["curr_state"] = "replan"
    print("Replanning step")
    pprint("--------------------")

    # Ensure past_steps is initialized
    if "past_steps" not in state or state["past_steps"] is None:
        state["past_steps"] = []

    # Track what sources have been used for informational purposes only
    if "retrieval_sources_used" in state:
        all_sources = ["document_chunks", "document_summaries", "key_facts"]
        missing_sources = [source for source in all_sources if source not in state["retrieval_sources_used"]]

        if missing_sources:
            print(f"Note: Some retrieval sources not yet used: {missing_sources}")
        else:
            print("Note: All retrieval sources have been used")

    # Let the replanner decide what information is still needed
    inputs = {
        "question": state["question"],
        "plan": state["plan"],
        "past_steps": state["past_steps"],
        "aggregated_context": state["aggregated_context"]
    }

    plan = replanner.invoke(inputs)
    state["plan"] = plan.steps

    print(f"New plan created with {len(state['plan'])} steps")
    return state


def can_be_answered(state: PlanExecute):
    """
    Determines if the question can be answered based solely on the available context.

    Args:
        state: The current state of the plan execution.
    Returns:
        The updated state with a can_answer_result field.
    """
    state["curr_state"] = "can_be_answered"

    print("Checking if the ORIGINAL QUESTION can be answered with the current context.")
    pprint("--------------------")
    question = state["question"]
    context = state["aggregated_context"]

    inputs = {
        "question": question,
        "context": context
    }

    output = can_be_answered_already_chain.invoke(inputs)
    if output.can_be_answered == True:
        print("The ORIGINAL QUESTION can be fully answered with the current context.")
        pprint("--------------------")
        # print("the aggregated context is:")
        # print(text_wrap(state["aggregated_context"]))
        print("--------------------")
        state["can_answer"] = True
        state["can_answer_result"] = "can_be_answered_already"
    else:
        print("The ORIGINAL QUESTION cannot be fully answered with the current context.")
        pprint("--------------------")
        state["can_answer"] = False
        state["can_answer_result"] = "can_be_answered_already"  # "cannot_be_answered_yet"

    return state


def create_agent():
    agent_workflow = StateGraph(PlanExecute)

    # Add the anonymize node
    agent_workflow.add_node("anonymize_question", anonymize_queries)

    # Add the plan node
    agent_workflow.add_node("planner", plan_step)

    # Add the break down plan node
    agent_workflow.add_node("break_down_plan", break_down_plan_step)

    # Add the deanonymize node
    agent_workflow.add_node("de_anonymize_plan", deanonymize_queries)

    # Add the qualitative document retrieval node
    agent_workflow.add_node("retrieve_chunks", run_qualitative_document_chunks_retrieval_workflow)

    # Add the qualitative summaries retrieval node
    agent_workflow.add_node("retrieve_summaries", run_qualitative_document_summaries_retrieval_workflow)

    # Add the qualitative key facts retrieval node
    agent_workflow.add_node("retrieve_key_facts", run_qualitative_key_facts_retrieval_workflow)

    # Add the qualitative answer node
    agent_workflow.add_node("answer", run_qualtative_answer_workflow)

    # Add the task handler node
    agent_workflow.add_node("task_handler", run_task_handler_chain)

    # Add a replan node
    agent_workflow.add_node("replan", replan_step)

    # Add answer from context node
    agent_workflow.add_node("get_final_answer", run_qualtative_answer_workflow_for_final_answer)

    # Add a check_plan node to determine if the plan is empty or not
    def check_plan(state):
        """Check if the plan is empty or not."""
        if not state["plan"]:
            print("Plan is empty. Checking if question can be answered...")
            return "plan_empty"
        else:
            print(f"Plan still has {len(state['plan'])} steps. Continuing execution...")
            return "plan_not_empty"

    # Set the entry point
    agent_workflow.set_entry_point("anonymize_question")

    # From anonymize we go to plan
    agent_workflow.add_edge("anonymize_question", "planner")

    # From plan we go to deanonymize
    agent_workflow.add_edge("planner", "de_anonymize_plan")

    # From deanonymize we go to break down plan
    agent_workflow.add_edge("de_anonymize_plan", "break_down_plan")

    # From break_down_plan we go to task handler
    agent_workflow.add_edge("break_down_plan", "task_handler")

    # From task handler we go to either retrieve or answer
    agent_workflow.add_conditional_edges(
        "task_handler",
        retrieve_or_answer,
        {
            "chosen_tool_is_retrieve_chunks": "retrieve_chunks",
            "chosen_tool_is_retrieve_summaries": "retrieve_summaries",
            "chosen_tool_is_retrieve_key_facts": "retrieve_key_facts",
            "chosen_tool_is_answer": "answer"
        }
    )

    # After each retrieval or answer operation, check if the plan is empty
    agent_workflow.add_conditional_edges(
        "retrieve_chunks",
        check_plan,
        {"plan_empty": "can_be_answered", "plan_not_empty": "task_handler"}
    )

    agent_workflow.add_conditional_edges(
        "retrieve_summaries",
        check_plan,
        {"plan_empty": "can_be_answered", "plan_not_empty": "task_handler"}
    )

    agent_workflow.add_conditional_edges(
        "retrieve_key_facts",
        check_plan,
        {"plan_empty": "can_be_answered", "plan_not_empty": "task_handler"}
    )

    agent_workflow.add_conditional_edges(
        "answer",
        check_plan,
        {"plan_empty": "can_be_answered", "plan_not_empty": "task_handler"}
    )

    # Add a node to check if the question can be answered
    agent_workflow.add_node("can_be_answered", can_be_answered)

    # After checking if the question can be answered, either get the final answer or replan
    agent_workflow.add_conditional_edges(
        "can_be_answered",
        lambda state: state["can_answer_result"],  # Use the can_answer_result field from the state
        {"can_be_answered_already": "get_final_answer", "cannot_be_answered_yet": "replan"}
    )

    # After replanning, go back to break_down_plan
    agent_workflow.add_edge("replan", "break_down_plan")

    # After getting the final answer we end
    agent_workflow.add_edge("get_final_answer", END)

    plan_and_execute_app = agent_workflow.compile()

    # Add a parameter to the agent's input state for persona selection
    def initialize_agent_state(question: str, persona: Optional[str] = None):
        """Initialize the agent state with a question and optional persona."""
        state = {
            "question": question,
            "anonymized_question": "",
            "query_to_retrieve_or_answer": "",
            "plan": [],
            "past_steps": [],
            "mapping": {},
            "curr_context": "",
            "aggregated_context": "",
            "tool": "",
            "response": "",
            "retrieval_sources_used": [],
            "all_sources_exhausted": False
        }

        # Add persona if specified
        if persona:
            state["persona"] = persona

        return state

    # Return both the agent workflow and the initializer
    return plan_and_execute_app, initialize_agent_state


def create_final_answer_workflow_app():
    class FinalAnswerGraphState(TypedDict):
        question: str
        context: str
        answer: str
        persona: Optional[str]
        hallucination_check_count: Optional[int]

    final_answer_workflow = StateGraph(FinalAnswerGraphState)

    # Add the final_answer_from_context node instead of answer_question_from_context
    final_answer_workflow.add_node("final_answer_from_context", final_answer_from_context)

    # Set entry point
    final_answer_workflow.set_entry_point("final_answer_from_context")

    # Add the same conditional edges for hallucination checking
    final_answer_workflow.add_conditional_edges(
        "final_answer_from_context", is_answer_grounded_on_context,
        {"hallucination": "final_answer_from_context", "grounded on context": END}
    )

    final_answer_workflow_app = final_answer_workflow.compile()
    return final_answer_workflow_app


final_answer_workflow_app = create_final_answer_workflow_app()
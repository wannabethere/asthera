
import json
import sys
from pathlib import Path

def populate_collection(preview_file, collection_name, batch_size=10):
    """Worker function that imports chromadb"""
    from app.core.dependencies import get_chromadb_client, get_embeddings_model
    from app.storage.documents import DocumentChromaStore, ChromaDBEmbeddingFunction
    from langchain_core.documents import Document
    
    print(f"Loading {preview_file}...")
    with open(preview_file, 'r') as f:
        data = json.load(f)
    
    documents = []
    for doc_data in data.get("documents", []):
        doc = Document(
            page_content=doc_data["page_content"],
            metadata=doc_data.get("metadata", {})
        )
        documents.append(doc)
    
    print(f"Loaded {len(documents)} documents")
    print(f"Initializing ChromaDB client...")
    
    client = get_chromadb_client()
    embeddings = get_embeddings_model()
    chroma_emb = ChromaDBEmbeddingFunction(embeddings)
    
    try:
        collection = client.get_collection(collection_name, embedding_function=chroma_emb)
        print(f"Using existing collection '{collection_name}'")
    except:
        collection = client.create_collection(collection_name, embedding_function=chroma_emb)
        print(f"Created collection '{collection_name}'")
    
    store = DocumentChromaStore(client=client, collection_name=collection_name, embeddings=embeddings)
    
    current_count = collection.count()
    print(f"Current collection size: {current_count}")
    
    # Batch ingestion
    total = len(documents)
    ingested = 0
    for i in range(0, total, batch_size):
        batch = documents[i:i+batch_size]
        try:
            store.add_documents(batch)
            ingested += len(batch)
            print(f"Progress: {ingested}/{total}")
        except Exception as e:
            print(f"Batch failed: {e}")
    
    final_count = collection.count()
    print(f"Final count: {final_count}")
    print(f"Added: {final_count - current_count}")
    
    return final_count - current_count

if __name__ == "__main__":
    preview_file = sys.argv[1]
    collection_name = sys.argv[2]
    batch_size = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    added = populate_collection(preview_file, collection_name, batch_size)
    print(f"SUCCESS: Added {added} documents")

from typing import Any, Dict, List, Optional
import os
import datetime

from chromadb import (
    Collection,
    Documents,
    EmbeddingFunction,
    Embeddings,
    HttpClient,
    IDs,
    Metadata,
    Where,
    WhereDocument,
)
from chromadb.utils import embedding_functions
from app.settings import get_settings

settings = get_settings()
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY

class ChromaDB:
    def __init__(self, connection_params: Dict[str, Any] | None = None):
        """
        Initialize ChromaDB client with connection settings.

        Args:
            connection_params: Optional dictionary of connection parameters.
            Optionally accepting these so this class can be used without running the api.
            If not provided, the connection parameters will be taken from the environment variables.
        """
        self.client = None
        
        self.connection_params = {
            "host": "40.124.72.73",
            "port": 8015,
        }
        
        self._close_client()
        
        # Get OpenAI API key from environment variable
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
            
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=openai_api_key,
            model_name="text-embedding-ada-002"
        )

    def _connect_client(self) -> None:
        """Connect to the ChromaDB client."""
        self.client = HttpClient(**self.connection_params)
        print("connected")

    def _close_client(self) -> None:
        """Close the ChromaDB client connection."""
        if self.client:
            self.client.close()
            self.client = None
   
    def create_collection(
        self,
        name: str,
        metadata: Optional[Dict] = None,
        embedding_function: Optional[EmbeddingFunction] = None,
    ) -> Collection:
        """Create a new collection or get existing one.

        Args:
            name: Name of the collection
            metadata: Optional metadata for the collection
            embedding_function: Optional custom embedding function

        Returns:
            Collection object
        """
        try:
            self._connect_client()
            return self.client.create_collection(
                name=name,
                metadata=metadata,
                embedding_function=embedding_function,
                get_or_create=True,
            )
        except Exception as e:
            raise Exception(f"Failed to create/get collection {name}: {str(e)}") from e
        
    def add_documents(
        self,
        collection_name: str,
        documents: Documents,
        ids: IDs,
        metadata: Optional[Metadata] = None,
    ) -> None:
        """Add documents to a collection.

        Args:
            collection_name: Name of the collection
            documents: List of documents to add
            ids: List of IDs for the documents
            metadata: Optional metadata for each document
        """
        try:
            self._connect_client()
            print("connected")
            collection: Collection = self.get_collection(collection_name)

            # Convert list metadata values to strings and handle None values
            if metadata:
                processed_metadata = []
                for meta in metadata:
                    processed_meta = {}
                    for key, value in meta.items():
                        if value is None:
                            processed_meta[key] = ""  # Convert None to empty string
                        elif isinstance(value, list):
                            processed_meta[key] = ", ".join(str(v) for v in value)
                        else:
                            processed_meta[key] = value
                    processed_metadata.append(processed_meta)
                metadata = processed_metadata

            collection.add(
                documents=documents, ids=ids, metadatas=metadata
            )
        except Exception as e:
            raise Exception(
                f"Failed to add documents to collection {collection_name}: {str(e)}"
            ) from e

    def query_collection(
        self,
        collection_name: str,
        query_texts: Optional[Documents] = None,
        query_embeddings: Optional[Embeddings] = None,
        n_results: int = 10,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
    ) -> Dict:
        """Query a collection for similar documents.

        Args:
            collection_name: Name of the collection
            query_texts: Text to search for
            query_embeddings: Pre-computed embeddings to search with
            n_results: Number of results to return
            where: Optional filtering conditions on metadata
            where_document: Optional filtering conditions on documents

        Returns:
            Query results
        """
        try:
            self._connect_client()
            collection: Collection = self.get_collection(collection_name)
            return collection.query(
                query_texts=query_texts,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=["documents", "distances"],
            )
        except Exception as e:
            raise Exception(
                f"Failed to query collection {collection_name}: {str(e)}"
            ) from e
        
    def query_collection_with_relevance_scores(
        self,
        collection_name: str,
        query_texts: Optional[Documents] = None,
        query_embeddings: Optional[Embeddings] = None,
        n_results: int = 10,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
    ) -> Dict:
        """Query a collection for similar documents with relevance scores.

        Args:
            collection_name: Name of the collection
            query_texts: Text to search for
            query_embeddings: Pre-computed embeddings to search with
            n_results: Number of results to return
            where: Optional filtering conditions on metadata
            where_document: Optional filtering conditions on documents      

        Returns:
            Query results
        """
        try:
            self._connect_client()
            print("connected")
            collection: Collection = self.get_collection(collection_name)   
            return collection.query(
                query_texts=query_texts,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=["documents", "distances"],
            )   
        except Exception as e:
            raise Exception(
                f"Failed to query collection {collection_name}: {str(e)}"
            ) from e

    def delete_items(
        self,
        collection_name: str,
        ids: Optional[IDs] = None,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
    ) -> None:
        """Delete items from a collection.

        Args:
            collection_name: Name of the collection
            ids: Optional list of IDs to delete
            where: Optional filtering conditions on metadata
            where_document: Optional filtering conditions on documents
        """
        try:
            self._connect_client()
            collection: Collection = self.get_collection(collection_name)
            collection.delete(ids=ids, where=where, where_document=where_document)
        except Exception as e:
            raise Exception(
                f"Failed to delete items from collection {collection_name}: {str(e)}"
            ) from e

    def get_record(self, collection_name: str, document_id: str) -> Dict:
        """Get a record from a collection.

        Args:
            collection_name: Name of the collection
            document_id: ID of the document to get

        Returns:
            Dict containing the record data
        """
        try:
            self._connect_client()
            collection: Collection = self.get_collection(collection_name)
            return collection.get(ids=[document_id])
        except Exception as e:
            raise Exception(
                f"Failed to get record {document_id} from collection {collection_name}: {str(e)}"
            ) from e

    def get_collection(self, name: str) -> Collection:
        """Get a collection by name.

        Args:
            name: Name of the collection to get

        Returns:
            Collection object
        """
        try:
            self._connect_client()
            return self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_function
            )
        except Exception as e:
            raise Exception(f"Failed to get collection {name}: {str(e)}") from e

    def list_collections(self) -> List[str]:
        """List all collections in the database.

        Returns:
            List of collection names
        """
        try:
            self._connect_client()
            return [collection.name for collection in self.client.list_collections()]
        except Exception as e:
            raise Exception(f"Failed to list collections: {str(e)}") from e

    def import_from_jsonl(self, jsonl_path: str, collection_name: str, batch_size: int = 100) -> None:
        """Import data from a JSONL file into a ChromaDB collection.

        Args:
            jsonl_path: Path to the JSONL file
            collection_name: Name of the collection to import into
            batch_size: Number of documents to process in each batch
        """
        try:
            import json
            from pathlib import Path
            import time

            print(f"\nStarting import of {jsonl_path}")
            print(f"Target collection: {collection_name}")
            print(f"Batch size: {batch_size}")
            
            start_time = time.time()
            
            # Read the JSONL file
            all_documents = []
            all_ids = []
            all_metadatas = []

            print("\nReading JSONL file...")
            with open(jsonl_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    if line_num % 1000 == 0:
                        print(f"Read {line_num} lines...")
                    data = json.loads(line)
                    
                    # Extract content and id
                    content = data['content']
                    doc_id = data['id']
                    
                    # Process metadata based on document type
                    metadata = data.get('metadata', {})
                    
                    # Add source information
                    metadata['source_file'] = Path(jsonl_path).name
                    metadata['imported_at'] = datetime.datetime.now().isoformat()
                    
                    # Add to lists
                    all_documents.append(content)
                    all_ids.append(doc_id)
                    all_metadatas.append(metadata)

            total_docs = len(all_documents)
            print(f"\nTotal documents to process: {total_docs}")
            print(f"Estimated number of batches: {(total_docs + batch_size - 1)//batch_size}")

            # Process in batches
            successful_batches = 0
            failed_batches = 0
            total_processed = 0

            for i in range(0, total_docs, batch_size):
                batch_start_time = time.time()
                batch_num = i//batch_size + 1
                total_batches = (total_docs + batch_size - 1)//batch_size
                
                print(f"\nProcessing batch {batch_num} of {total_batches}...")
                print(f"Documents {i+1} to {min(i+batch_size, total_docs)} of {total_docs}")
                
                batch_docs = all_documents[i:i + batch_size]
                batch_ids = all_ids[i:i + batch_size]
                batch_metadatas = all_metadatas[i:i + batch_size]

                try:
                    # Add documents to collection
                    self.add_documents(
                        collection_name=collection_name,
                        documents=batch_docs,
                        ids=batch_ids,
                        metadata=batch_metadatas
                    )
                    successful_batches += 1
                    total_processed += len(batch_docs)
                    
                    batch_time = time.time() - batch_start_time
                    print(f"Batch {batch_num} completed in {batch_time:.2f} seconds")
                    print(f"Progress: {total_processed}/{total_docs} documents ({total_processed/total_docs*100:.1f}%)")
                    
                except Exception as e:
                    failed_batches += 1
                    print(f"Error in batch {batch_num}: {str(e)}")
                    continue

            total_time = time.time() - start_time
            
            print("\nImport Summary:")
            print(f"Total documents processed: {total_processed}")
            print(f"Successful batches: {successful_batches}")
            print(f"Failed batches: {failed_batches}")
            print(f"Total time: {total_time:.2f} seconds")
            print(f"Average time per batch: {total_time/successful_batches:.2f} seconds")
            print(f"Average time per document: {total_time/total_processed:.2f} seconds")
            
            if failed_batches > 0:
                print(f"\nWarning: {failed_batches} batches failed to process")
            else:
                print("\nAll batches processed successfully!")

        except Exception as e:
            raise Exception(f"Failed to import from JSONL file {jsonl_path}: {str(e)}") from e

if __name__ == "__main__":
    import datetime
    
    chroma = ChromaDB()
    
    # Import all Gong data files
    base_path = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/gong_data"
    
    print("\n=== Starting Gong Data Import ===")
    
    # Import chunks with smaller batch size
    print("\n1. Importing Gong Chunks...")
    chunks_path = f"{base_path}/gong_chunks_export.jsonl"
    chroma.import_from_jsonl(chunks_path, "gong_chunks", batch_size=50)
    
    # Import insights
    print("\n2. Importing Gong Insights...")
    insights_path = f"{base_path}/gong_insights_export.jsonl"
    chroma.import_from_jsonl(insights_path, "gong_insights", batch_size=50)
    
    # Import transcripts
    print("\n3. Importing Gong Transcripts...")
    transcripts_path = f"{base_path}/gong_transcripts_only.jsonl"
    chroma.import_from_jsonl(transcripts_path, "gong_transcripts", batch_size=50)
    
    # List all collections
    print("\n=== Import Complete ===")
    print("\nAvailable collections:")
    print(chroma.list_collections())

from typing import Any, Dict, List, Optional, Union, cast, Literal
import json

from chromadb import (
    Collection,
    Documents,
    EmbeddingFunction,
    Embeddings,
    HttpClient,
    IDs,
    Include,
    Where,
    WhereDocument,
)
from chromadb.api.types import QueryResult

from app.config.settings import get_settings


class ChromaDB:
    def __init__(self, connection_params: Dict[str, Any] | None = None, log_level: str = "INFO",embedding_function: Optional[EmbeddingFunction] = None):
        """
        Initialize ChromaDB client with connection settings.

        Args:
            connection_params: Optional dictionary of connection parameters.
            Optionally accepting these so this class can be used without running the api.
            If not provided, the connection parameters will be taken from the environment variables.
            log_level: Logging level, one of "DEBUG", "INFO", "WARNING", "ERROR", "NONE"
        """
        self.client: HttpClient = None  # type: ignore
        self.log_level = log_level.upper()
        self.embedding_function = embedding_function
        
        if connection_params is None:
            settings = get_settings()
            self.connection_params = {
                "host": settings.CHROMA_HOST,
                "port": settings.CHROMA_PORT,
            }
        else:
            self.connection_params = connection_params

    def _log(self, level: str, message: str) -> None:
        """
        Log a message if the log level allows it.
        
        Args:
            level: Log level of the message ("DEBUG", "INFO", "WARNING", "ERROR")
            message: Message to log
        """
        # Define log level hierarchy
        level_hierarchy = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "ERROR": 3,
            "NONE": 4
        }
        
        # Check if we should log this message
        if level_hierarchy.get(level.upper(), 0) >= level_hierarchy.get(self.log_level, 1):
            print(f"[ChromaDB] {message}")

    def _connect_client(self) -> None:
        """Connect to the ChromaDB client."""
        if self.client is None:
            self.client = HttpClient(**self.connection_params)
            if self.client is None:
                raise Exception("Failed to initialize ChromaDB client")

    def _close_client(self) -> None:
        """Close the ChromaDB client connection."""
        if self.client:
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
                embedding_function=embedding_function if embedding_function is not None else self.embedding_function,
                get_or_create=True,
            )
        except Exception as e:
            raise Exception(f"Failed to create/get collection {name}: {str(e)}") from e

    def get_collection(self, name: str) -> Collection:
        """Get an existing collection.

        Args:
            name: Name of the collection

        Returns:
            Collection object

        Raises:
            Exception: If collection doesn't exist and cannot be created
        """
        try:
            self._connect_client()
            try:
                return self.client.get_collection(name)
            except Exception:
                # If collection doesn't exist, create it
                return self.create_collection(name)
        except Exception as e:
            raise Exception(f"Failed to get/create collection {name}: {str(e)}") from e

    def get_or_create_collection_with_embedding(self, name: str, metadata: Optional[Dict] = None) -> Collection:
        """Get an existing collection or create it with the default embedding function.

        Args:
            name: Name of the collection
            metadata: Optional metadata for the collection

        Returns:
            Collection object with embedding function configured

        Raises:
            Exception: If collection cannot be created
        """
        try:
            self._connect_client()
            try:
                collection = self.client.get_collection(name)
                # Check if the collection has an embedding function
                if not hasattr(collection, '_embedding_function') or collection._embedding_function is None:
                    self._log("WARNING", f"Collection '{name}' exists but has no embedding function. Recreating with embedding function.")
                    # Delete the existing collection and recreate it
                    self.client.delete_collection(name=name)
                    return self.create_collection(name, metadata)
                return collection
            except Exception:
                # If collection doesn't exist, create it
                return self.create_collection(name, metadata)
        except Exception as e:
            raise Exception(f"Failed to get/create collection {name} with embedding function: {str(e)}") from e

    def list_collections(self) -> List[Collection]:
        """List all available collections.

        Returns:
            List of Collection objects
        """
        try:
            self._connect_client()
            return self.client.list_collections()
        except Exception as e:
            raise Exception(f"Failed to list collections: {str(e)}") from e

    def delete_collection(self, name: str) -> None:
        """Delete a collection.

        Args:
            name: Name of the collection to delete
        """
        try:
            self._connect_client()
            self.client.delete_collection(name=name)
        except Exception as e:
            raise Exception(f"Failed to delete collection {name}: {str(e)}") from e

    def recreate_collection_with_embedding(self, name: str, metadata: Optional[Dict] = None) -> Collection:
        """Delete and recreate a collection with the default embedding function.

        Args:
            name: Name of the collection to recreate
            metadata: Optional metadata for the collection

        Returns:
            Newly created Collection object with embedding function

        Raises:
            Exception: If collection cannot be recreated
        """
        try:
            self._connect_client()
            self._log("INFO", f"Recreating collection '{name}' with embedding function")
            
            # Delete existing collection if it exists
            try:
                self.client.delete_collection(name=name)
                self._log("INFO", f"Deleted existing collection '{name}'")
            except Exception:
                # Collection might not exist, which is fine
                self._log("INFO", f"Collection '{name}' did not exist, creating new one")
            
            # Create new collection with embedding function
            return self.create_collection(name, metadata)
        except Exception as e:
            raise Exception(f"Failed to recreate collection {name} with embedding function: {str(e)}") from e

    def check_collection_embedding_function(self, name: str) -> bool:
        """Check if a collection has an embedding function configured.

        Args:
            name: Name of the collection to check

        Returns:
            True if collection has embedding function, False otherwise
        """
        try:
            self._connect_client()
            collection = self.client.get_collection(name)
            return hasattr(collection, '_embedding_function') and collection._embedding_function is not None
        except Exception as e:
            self._log("ERROR", f"Failed to check embedding function for collection {name}: {str(e)}")
            return False

    def add_documents(
        self,
        collection_name: str,
        documents: Documents,
        ids: IDs,
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Add documents to a collection."""
        try:
            self._connect_client()
            collection: Collection = self.get_collection(collection_name)

            # Convert metadata to ChromaDB format
            if metadata:
                processed_metadata = []
                for meta in metadata:
                    if isinstance(meta, str):
                        processed_metadata.append({"content": meta})
                    else:
                        processed_meta = {}
                        for key, value in meta.items():
                            if value is None:
                                processed_meta[key] = ""  # Convert None to empty string
                            elif isinstance(value, list):
                                # Keep lists as JSON strings
                                processed_meta[key] = json.dumps(value)
                            elif isinstance(value, dict):
                                # Keep dicts as JSON strings
                                processed_meta[key] = json.dumps(value)
                            else:
                                processed_meta[key] = str(value) if value is not None else ""
                        processed_metadata.append(processed_meta)
                metadata = processed_metadata

            collection.add(
                documents=documents,
                ids=ids,
                metadatas=metadata  # type: ignore
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
    ) -> Dict[str, Any]:
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
            
            # Only log essential query information
            if where:
                self._log("INFO", f"Querying collection '{collection_name}' with {n_results} results, where filter present")
            else:
                self._log("INFO", f"Querying collection '{collection_name}' with {n_results} results")
            
            results = collection.query(
                query_texts=query_texts,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=["documents", "distances", "metadatas"],  # type: ignore
            )
            
            # Just log the result count, not the full contents
            result_count = len(results['ids'][0]) if results['ids'] and len(results['ids']) > 0 else 0
            self._log("INFO", f"Query returned {result_count} results")
            
            return {
                'ids': results['ids'],
                'distances': results['distances'],
                'documents': results['documents'],
                'metadatas': results.get('metadatas', [])
            }
        except Exception as e:
            self._log("ERROR", f"Error querying collection: {e}")
            import traceback
            traceback.print_exc()
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

    def get_record(self, collection_name: str, document_id: str) -> Dict[str, Any]:
        """Get a record from a collection."""
        try:
            self._connect_client()
            collection: Collection = self.get_collection(collection_name)
            results = collection.get(ids=[document_id])
            return {
                'ids': results['ids'],
                'documents': results['documents'],
                'metadatas': results['metadatas']
            }
        except Exception as e:
            raise Exception(
                f"Failed to get record {document_id} from collection {collection_name}: {str(e)}"
            ) from e

    def query_collection_with_relevance_scores(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[Embeddings] = None,
        n_results: int = 10,
        where: Optional[Where] = None,
        where_document: Optional[WhereDocument] = None,
    ) -> List[Dict[str, Any]]:
        """Query a collection for similar documents with relevance scores.

        Args:
            collection_name: Name of the collection
            query_texts: Text to search for
            query_embeddings: Pre-computed embeddings to search with
            n_results: Number of results to return
            where: Optional filtering conditions on metadata
            where_document: Optional filtering conditions on documents

        Returns:
            List of dictionaries containing query results with relevance scores
        """
        try:
            self._connect_client()
            # Use the method that ensures embedding function is configured
            collection = self.get_or_create_collection_with_embedding(collection_name)
            
            # Streamlined logging for query
            if where:
                self._log("INFO", f"Querying '{collection_name}' for {n_results} results with filter")
            else:
                # For non-filtered searches, just log a simpler message
                self._log("INFO", f"Querying '{collection_name}' for {n_results} results")
            
            # Define what to include in the results using a list of valid values
            results = collection.query(
                query_texts=query_texts,
                query_embeddings=query_embeddings,
                n_results=n_results,
                where=where,
                where_document=where_document,
                include=["documents", "metadatas", "distances"]  # type: ignore
            )
            
            # Format results into a list of documents with relevance scores
            formatted_results = []
            
            if len(results['ids']) > 0 and len(results['ids'][0]) > 0:
                # Get all distances for normalization
                all_distances = results['distances'][0] if 'distances' in results and results['distances'] else []
                
                # Calculate min/max for normalization if we have distances
                min_dist = min(all_distances) if all_distances else 0
                max_dist = max(all_distances) if all_distances else 1
                # Ensure we don't divide by zero
                range_dist = max_dist - min_dist if max_dist > min_dist else 1
                
                # Log only the result count, not individual distances
                self._log("INFO", f"Found {len(results['ids'][0])} results with distance range: {min_dist:.4f}-{max_dist:.4f}")
                
                for i in range(len(results['ids'][0])):
                    doc_id = results['ids'][0][i]
                    distance = results['distances'][0][i] if 'distances' in results and results['distances'] else 0.0
                    document = results['documents'][0][i] if 'documents' in results and results['documents'] else ""
                    metadata = results['metadatas'][0][i] if 'metadatas' in results and results['metadatas'] else {}
                    
                    # Normalize distance to [0,1] range
                    if range_dist > 0:
                        normalized_distance = (distance - min_dist) / range_dist
                    else:
                        normalized_distance = 0.0
                    
                    # Convert to relevance score (1.0 - normalized_distance)
                    relevance_score = 1.0 - normalized_distance
                    
                    # Log only in debug mode
                    self._log("DEBUG", f"Document {doc_id}: distance={distance:.4f}, relevance={relevance_score:.4f}")
                    
                    formatted_results.append({
                        'document_id': doc_id,
                        'document_type': metadata.get('document_type', 'unknown'),
                        'content': document,
                        'metadata': metadata,
                        'distance': distance,
                        'relevance_score': relevance_score
                    })
            else:
                self._log("INFO", f"No results found for query in collection {collection_name}")
                
            return formatted_results
            
        except Exception as e:
            self._log("ERROR", f"Error in query_collection_with_relevance_scores: {e}")
            import traceback
            traceback.print_exc()
            # Check if the error is specifically about missing embedding function
            if "embedding function" in str(e).lower():
                self._log("ERROR", f"Collection '{collection_name}' requires an embedding function to be configured")
                raise Exception(
                    f"Collection '{collection_name}' requires an embedding function to be configured. "
                    f"Please ensure the collection was created with an embedding function or use a different query method. "
                    f"Original error: {str(e)}"
                ) from e
            else:
                raise Exception(
                    f"Failed to query collection {collection_name} with relevance scores: {str(e)}"
                ) from e

    def query_by_ids_with_relevance(
        self,
        collection_name: str,
        ids: List[str],
        query_texts: Optional[List[str]] = None,
        n_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Query specific documents by their IDs and calculate relevance scores against a query.

        Args:
            collection_name: Name of the collection
            ids: List of document IDs to query
            query_texts: Text to calculate relevance against
            n_results: Maximum number of results to return

        Returns:
            List of dictionaries containing documents with relevance scores
        """
        try:
            self._connect_client()
            # Use the method that ensures embedding function is configured
            collection = self.get_or_create_collection_with_embedding(collection_name)

            self._log("INFO", f"Querying {len(ids)} specific documents from '{collection_name}' by ID")

            # First, get the documents by their IDs
            results = collection.get(
                ids=ids,
                include=["documents", "metadatas"]  # type: ignore
            )

            # If no query_texts provided, return documents without relevance scores
            if not query_texts:
                formatted_results = []

                # Check if results contains the expected keys
                if 'ids' in results and results['ids'] and len(results['ids']) > 0:
                    for i in range(len(results['ids'])):
                        doc_id = results['ids'][i]
                        document = results['documents'][i] if 'documents' in results and results['documents'] else ""
                        metadata = results['metadatas'][i] if 'metadatas' in results and results['metadatas'] else {}

                        formatted_results.append({
                            'document_id': doc_id,
                            'document_type': metadata.get('document_type', 'unknown'),
                            'content': document,
                            'metadata': metadata,
                            'relevance_score': 0.5  # Default neutral score
                        })
                return formatted_results

            # If we have query_texts, calculate relevance scores
            # Check if collection has an embedding function before using it
            if not hasattr(collection, '_embedding_function') or collection._embedding_function is None:
                self._log("WARNING", "Collection does not have an embedding function, returning documents without relevance scores")

                # Return documents without relevance scores
                formatted_results = []
                if 'ids' in results and results['ids'] and len(results['ids']) > 0:
                    for i in range(len(results['ids'])):
                        doc_id = results['ids'][i]
                        document = results['documents'][i] if 'documents' in results and results['documents'] else ""
                        metadata = results['metadatas'][i] if 'metadatas' in results and results['metadatas'] else {}

                        formatted_results.append({
                            'document_id': doc_id,
                            'document_type': metadata.get('document_type', 'unknown'),
                            'content': document,
                            'metadata': metadata,
                            'relevance_score': 0.5  # Default neutral score
                        })
                return formatted_results

            # Get documents for embedding
            documents = []
            if 'documents' in results and results['documents'] and len(results['documents']) > 0:
                documents = results['documents']

            # Skip embedding calculation if no documents
            if not documents:
                self._log("WARNING", "No documents found for embedding calculation")
                return []

            # Calculate distances using collection's query method with the query text
            query_results = collection.query(
                query_texts=query_texts,
                n_results=len(ids),  # Get scores for all documents
                include=["distances"]  # type: ignore
            )

            # Map results back to original document order
            id_to_result = {}
            if 'ids' in query_results and query_results['ids'] and len(query_results['ids']) > 0:
                for i in range(len(query_results['ids'][0])):
                    doc_id = query_results['ids'][0][i]
                    distance = query_results['distances'][0][i] if 'distances' in query_results and query_results['distances'] else 0.0
                    id_to_result[doc_id] = {
                        'distance': distance
                    }

            # Calculate min/max for normalization
            distances = [id_to_result.get(doc_id, {}).get('distance', 0.0) for doc_id in results['ids']]
            min_dist = min(distances) if distances else 0
            max_dist = max(distances) if distances else 1
            range_dist = max_dist - min_dist if max_dist > min_dist else 1

            # Format results with relevance scores
            formatted_results = []

            if 'ids' in results and results['ids'] and len(results['ids']) > 0:
                for i in range(len(results['ids'])):
                    doc_id = results['ids'][i]
                    document = results['documents'][i] if 'documents' in results and results['documents'] else ""
                    metadata = results['metadatas'][i] if 'metadatas' in results and results['metadatas'] else {}

                    # Get distance from query results or use default
                    distance = id_to_result.get(doc_id, {}).get('distance', 0.0)

                    # Normalize distance to [0,1] range
                    if range_dist > 0:
                        normalized_distance = (distance - min_dist) / range_dist
                    else:
                        normalized_distance = 0.0

                    # Convert to relevance score (1.0 - normalized_distance)
                    relevance_score = 1.0 - normalized_distance

                    formatted_results.append({
                        'document_id': doc_id,
                        'document_type': metadata.get('document_type', 'unknown'),
                        'content': document,
                        'metadata': metadata,
                        'distance': distance,
                        'relevance_score': relevance_score
                    })

            # Sort by relevance score and limit results
            formatted_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            return formatted_results[:n_results]

        except Exception as e:
            self._log("ERROR", f"Error in query_by_ids_with_relevance: {e}")
            import traceback
            traceback.print_exc()

            # Fallback: return documents without relevance scores
            try:
                results = collection.get(
                    ids=ids,
                    include=["documents", "metadatas"]  # type: ignore
                )

                formatted_results = []
                if 'ids' in results and results['ids'] and len(results['ids']) > 0:
                    for i in range(len(results['ids'])):
                        doc_id = results['ids'][i]
                        document = results['documents'][i] if 'documents' in results and results['documents'] else ""
                        metadata = results['metadatas'][i] if 'metadatas' in results and results['metadatas'] else {}

                        formatted_results.append({
                            'document_id': doc_id,
                            'document_type': metadata.get('document_type', 'unknown'),
                            'content': document,
                            'metadata': metadata,
                            'relevance_score': 0.5  # Default neutral score
                        })
                return formatted_results

            except Exception as fallback_error:
                self._log("ERROR", f"Fallback retrieval also failed: {fallback_error}")
                raise Exception(
                    f"Failed to query documents by ID with relevance scores: {str(e)}"
                ) from e

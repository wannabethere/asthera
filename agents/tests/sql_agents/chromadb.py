from typing import Any, Dict, List, Optional
import chromadb
from chromadb import (
    Collection,
    Documents,
    EmbeddingFunction,
    Embeddings,
    HttpClient,
    PersistentClient,
    IDs,
    Metadata,
    Where,
    WhereDocument,
)
from app.settings import get_settings
settings = get_settings()

class ChromaDB:
    def __init__(self, client=None, connection_params: Dict[str, Any] | None = None):
        """
        Initialize ChromaDB client with connection settings.

        Args:
            client: Optional ChromaDB client instance. If provided, will use this client.
            connection_params: Optional dictionary of connection parameters.
            Optionally accepting these so this class can be used without running the api.
            If not provided, the connection parameters will be taken from the environment variables.
        """
        self.client = client
        self.connection_params = connection_params
        self._connect_client()

    def _connect_client(self) -> None:
        """Connect to the ChromaDB client."""
        if self.client is None:
            
            if settings.CHROMA_USE_LOCAL:
                # Use local persistent client
                self.client=chromadb.PersistentClient(path=settings.CHROMA_STORE_PATH)
            else:
                # Use HTTP client (default)
                self.client=chromadb.HttpClient(
                    host=settings.CHROMA_HOST, 
                    port=settings.CHROMA_PORT
                )
        else:
            self.client = self.client
            
        # If client is already provided, no need to connect

    def _close_client(self) -> None:
        """Close the ChromaDB client connection."""
        if self.client and hasattr(self.client, 'close'):
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
            
            
            # Verify client is properly initialized
            if self.client is None:
                raise ValueError("ChromaDB client is not initialized")
            return self.client.get_or_create_collection(
                    name=name,
                    metadata=metadata,
                    embedding_function=embedding_function,
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

    def add_documents_with_embeddings(
        self,
        collection_name: str,
        documents: Documents,
        ids: IDs,
        embeddings: Embeddings,
        metadata: Optional[Metadata] = None,
    ) -> None:
        """Add documents with pre-computed embeddings to a collection.

        Args:
            collection_name: Name of the collection
            documents: List of documents to add
            ids: List of IDs for the documents
            embeddings: Pre-computed embeddings for the documents
            metadata: Optional metadata for each document
        """
        try:
            self._connect_client()
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
                documents=documents, ids=ids, embeddings=embeddings, metadatas=metadata
            )
        except Exception as e:
            raise Exception(
                f"Failed to add documents with embeddings to collection {collection_name}: {str(e)}"
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

    def get_all_records(self, collection_name: str) -> Dict:
        """Get all records from a collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Dict containing all records
        """
        try:
            self._connect_client()
            collection: Collection = self.get_collection(collection_name)
            return collection.get()
        except Exception as e:
            raise Exception(
                f"Failed to get all records from collection {collection_name}: {str(e)}"
            ) from e

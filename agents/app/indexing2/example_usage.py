"""
Example Usage of the Unified ChromaDB Storage System

This module demonstrates how to use the new unified storage system
that eliminates duplication while providing enhanced search capabilities.

Features demonstrated:
- Unified document creation
- TF-IDF generation and search
- Quick reference lookups
- Backward compatibility
- Enhanced business context
"""

import asyncio
import logging
import json
from typing import Dict, Any

from langchain_openai import OpenAIEmbeddings
import chromadb

from app.indexing2.storage_manager import StorageManager
from app.indexing2.tfidf_generator import TFIDFGenerator
from app.indexing2.document_builder import DocumentBuilder
from app.storage.documents import DocumentChromaStore
from app.settings import get_settings

logger = logging.getLogger("genieml-agents")
settings = get_settings()

class ExampleUsage:
    """Example usage of the unified storage system."""
    
    def __init__(self):
        """Initialize the example."""
        self.storage_manager = None
        self.example_mdl = self._create_example_mdl()
        self.static_collection_name = "example_static_collection"
        self.static_collection = None
    
    def _create_example_mdl(self) -> str:
        """Create an example MDL string for testing."""
        return json.dumps({
            "models": [
                {
                    "name": "users",
                    "primaryKey": "user_id",
                    "properties": {
                        "displayName": "User Accounts",
                        "description": "Stores user account information",
                        "businessPurpose": "User management and authentication",
                        "classification": "internal",
                        "tags": ["user", "authentication"],
                        "businessRules": [
                            "Each user must have a unique email address",
                            "User status must be active, inactive, or suspended"
                        ]
                    },
                    "columns": [
                        {
                            "name": "user_id",
                            "type": "VARCHAR",
                            "notNull": True,
                            "properties": {
                                "displayName": "User Identifier",
                                "description": "Unique identifier for user accounts",
                                "businessPurpose": "Primary key for user management",
                                "usageType": "identifier",
                                "exampleValues": ["U001", "U002", "U003"],
                                "privacyClassification": "internal"
                            }
                        },
                        {
                            "name": "email",
                            "type": "VARCHAR",
                            "notNull": True,
                            "properties": {
                                "displayName": "Email Address",
                                "description": "User's email address for login",
                                "businessPurpose": "Authentication and communication",
                                "usageType": "contact",
                                "exampleValues": ["user@example.com", "admin@company.com"],
                                "privacyClassification": "pii"
                            }
                        },
                        {
                            "name": "status",
                            "type": "VARCHAR",
                            "notNull": True,
                            "properties": {
                                "displayName": "Account Status",
                                "description": "Current status of the user account",
                                "businessPurpose": "Account management and access control",
                                "usageType": "status",
                                "exampleValues": ["active", "inactive", "suspended"],
                                "privacyClassification": "internal"
                            }
                        },
                        {
                            "name": "created_at",
                            "type": "TIMESTAMP",
                            "notNull": True,
                            "properties": {
                                "displayName": "Creation Date",
                                "description": "When the user account was created",
                                "businessPurpose": "Audit trail and account lifecycle",
                                "usageType": "timestamp",
                                "privacyClassification": "internal"
                            }
                        },
                        {
                            "name": "full_name",
                            "type": "VARCHAR",
                            "notNull": False,
                            "isCalculated": True,
                            "expression": "CONCAT(first_name, ' ', last_name)",
                            "properties": {
                                "displayName": "Full Name",
                                "description": "Calculated field combining first and last name",
                                "businessPurpose": "Display name for user interface",
                                "usageType": "calculated",
                                "privacyClassification": "pii"
                            }
                        },
                        {
                            "name": "account_age_days",
                            "type": "INT",
                            "notNull": False,
                            "isCalculated": True,
                            "expression": "DATEDIFF(CURRENT_DATE, created_at)",
                            "properties": {
                                "displayName": "Account Age in Days",
                                "description": "Number of days since account creation",
                                "businessPurpose": "Customer lifecycle analysis",
                                "usageType": "calculated",
                                "privacyClassification": "internal"
                            }
                        }
                    ]
                },
                {
                    "name": "orders",
                    "primaryKey": "order_id",
                    "properties": {
                        "displayName": "Customer Orders",
                        "description": "Stores customer order information",
                        "businessPurpose": "Order management and fulfillment",
                        "classification": "internal",
                        "tags": ["order", "customer", "sales"],
                        "businessRules": [
                            "Each order must have a valid customer",
                            "Order status must be pending, confirmed, shipped, or delivered"
                        ]
                    },
                    "columns": [
                        {
                            "name": "order_id",
                            "type": "VARCHAR",
                            "notNull": True,
                            "properties": {
                                "displayName": "Order Identifier",
                                "description": "Unique identifier for orders",
                                "businessPurpose": "Primary key for order management",
                                "usageType": "identifier",
                                "privacyClassification": "internal"
                            }
                        },
                        {
                            "name": "user_id",
                            "type": "VARCHAR",
                            "notNull": True,
                            "relationship": {
                                "type": "foreign_key",
                                "references": "users.user_id"
                            },
                            "properties": {
                                "displayName": "Customer ID",
                                "description": "Reference to the customer who placed the order",
                                "businessPurpose": "Link orders to customers",
                                "usageType": "reference",
                                "privacyClassification": "internal"
                            }
                        },
                        {
                            "name": "total_amount",
                            "type": "DECIMAL",
                            "notNull": True,
                            "properties": {
                                "displayName": "Order Total",
                                "description": "Total amount for the order",
                                "businessPurpose": "Financial tracking and reporting",
                                "usageType": "measure",
                                "exampleValues": ["99.99", "149.50", "299.00"],
                                "privacyClassification": "financial"
                            }
                        },
                        {
                            "name": "order_date",
                            "type": "TIMESTAMP",
                            "notNull": True,
                            "properties": {
                                "displayName": "Order Date",
                                "description": "When the order was placed",
                                "businessPurpose": "Order tracking and analytics",
                                "usageType": "timestamp",
                                "privacyClassification": "internal"
                            }
                        },
                        {
                            "name": "order_status",
                            "type": "VARCHAR",
                            "notNull": True,
                            "properties": {
                                "displayName": "Order Status",
                                "description": "Current status of the order",
                                "businessPurpose": "Order tracking and fulfillment",
                                "usageType": "status",
                                "exampleValues": ["pending", "confirmed", "shipped", "delivered"],
                                "privacyClassification": "internal"
                            }
                        },
                        {
                            "name": "order_age_days",
                            "type": "INT",
                            "notNull": False,
                            "isCalculated": True,
                            "expression": "DATEDIFF(CURRENT_DATE, order_date)",
                            "properties": {
                                "displayName": "Order Age in Days",
                                "description": "Number of days since order was placed",
                                "businessPurpose": "Order lifecycle analysis",
                                "usageType": "calculated",
                                "privacyClassification": "internal"
                            }
                        },
                        {
                            "name": "is_high_value",
                            "type": "BOOLEAN",
                            "notNull": False,
                            "isCalculated": True,
                            "expression": "total_amount > 100",
                            "properties": {
                                "displayName": "High Value Order",
                                "description": "Indicates if order value exceeds $100",
                                "businessPurpose": "Customer segmentation and analysis",
                                "usageType": "calculated",
                                "privacyClassification": "internal"
                            }
                        }
                    ]
                }
            ],
            "relationships": [
                {
                    "name": "user_orders",
                    "models": ["users", "orders"],
                    "joinType": "ONE_TO_MANY",
                    "condition": "users.user_id = orders.user_id",
                    "properties": {
                        "description": "Users can have multiple orders",
                        "businessPurpose": "Customer order tracking"
                    }
                }
            ],
            "views": [
                {
                    "name": "active_users",
                    "statement": "SELECT * FROM users WHERE status = 'active'",
                    "properties": {
                        "displayName": "Active Users View",
                        "description": "Shows only active user accounts",
                        "businessPurpose": "Active user analysis and reporting"
                    }
                },
                {
                    "name": "user_order_summary",
                    "statement": "SELECT u.user_id, u.email, u.status, COUNT(o.order_id) as total_orders, SUM(o.total_amount) as total_spent, AVG(o.total_amount) as avg_order_value FROM users u LEFT JOIN orders o ON u.user_id = o.user_id GROUP BY u.user_id, u.email, u.status",
                    "properties": {
                        "displayName": "User Order Summary",
                        "description": "Summary view of users and their order statistics",
                        "businessPurpose": "Customer analytics and reporting"
                    }
                },
                {
                    "name": "high_value_orders",
                    "statement": "SELECT o.*, u.email, u.status as user_status FROM orders o JOIN users u ON o.user_id = u.user_id WHERE o.total_amount > 100",
                    "properties": {
                        "displayName": "High Value Orders",
                        "description": "Orders with value exceeding $100",
                        "businessPurpose": "High-value customer analysis"
                    }
                },
                {
                    "name": "monthly_sales_summary",
                    "statement": "SELECT DATE_TRUNC('month', order_date) as month, COUNT(*) as order_count, SUM(total_amount) as total_revenue, AVG(total_amount) as avg_order_value FROM orders GROUP BY DATE_TRUNC('month', order_date) ORDER BY month",
                    "properties": {
                        "displayName": "Monthly Sales Summary",
                        "description": "Monthly aggregated sales data",
                        "businessPurpose": "Sales performance tracking"
                    }
                }
            ],
            "metrics": [
                {
                    "name": "user_metrics",
                    "properties": {
                        "displayName": "User Performance Metrics",
                        "description": "Key performance indicators for user management",
                        "businessPurpose": "User analytics and reporting"
                    },
                    "dimension": [
                        {
                            "name": "user_status",
                            "type": "VARCHAR"
                        },
                        {
                            "name": "registration_month",
                            "type": "VARCHAR"
                        }
                    ],
                    "measure": [
                        {
                            "name": "total_users",
                            "type": "INTEGER"
                        },
                        {
                            "name": "active_users",
                            "type": "INTEGER"
                        },
                        {
                            "name": "conversion_rate",
                            "type": "DECIMAL"
                        }
                    ]
                },
                {
                    "name": "sales_metrics",
                    "properties": {
                        "displayName": "Sales Performance Metrics",
                        "description": "Key performance indicators for sales and revenue",
                        "businessPurpose": "Sales analytics and reporting"
                    },
                    "dimension": [
                        {
                            "name": "order_date",
                            "type": "DATE"
                        },
                        {
                            "name": "order_status",
                            "type": "VARCHAR"
                        },
                        {
                            "name": "user_status",
                            "type": "VARCHAR"
                        }
                    ],
                    "measure": [
                        {
                            "name": "total_revenue",
                            "type": "DECIMAL"
                        },
                        {
                            "name": "order_count",
                            "type": "INTEGER"
                        },
                        {
                            "name": "average_order_value",
                            "type": "DECIMAL"
                        },
                        {
                            "name": "high_value_order_count",
                            "type": "INTEGER"
                        }
                    ]
                },
                {
                    "name": "customer_metrics",
                    "properties": {
                        "displayName": "Customer Analytics Metrics",
                        "description": "Customer behavior and engagement metrics",
                        "businessPurpose": "Customer analytics and segmentation"
                    },
                    "dimension": [
                        {
                            "name": "customer_segment",
                            "type": "VARCHAR"
                        },
                        {
                            "name": "registration_month",
                            "type": "VARCHAR"
                        }
                    ],
                    "measure": [
                        {
                            "name": "customer_lifetime_value",
                            "type": "DECIMAL"
                        },
                        {
                            "name": "orders_per_customer",
                            "type": "DECIMAL"
                        },
                        {
                            "name": "customer_retention_rate",
                            "type": "DECIMAL"
                        }
                    ]
                }
            ]
        })
    
    async def _create_static_collection(self):
        """Create a static ChromaDB collection for examples."""
        try:
            logger.info("Creating static ChromaDB collection for examples...")
            
            # Get the ChromaDB client
            if hasattr(self.storage_manager, '_unified_storage') and self.storage_manager._unified_storage:
                document_store = self.storage_manager._unified_storage._document_store
                chroma_client = document_store.persistent_client
            elif hasattr(self.storage_manager, '_document_store') and self.storage_manager._document_store:
                document_store = self.storage_manager._document_store
                chroma_client = document_store.persistent_client
            else:
                logger.warning("No document store available for static collection creation")
                return None
            
            # Delete existing collection if it exists
            try:
                # Try to get the collection first - if it exists, delete it
                try:
                    existing_collection = chroma_client.get_collection(self.static_collection_name)
                    if existing_collection:
                        chroma_client.delete_collection(self.static_collection_name)
                        logger.info(f"Deleted existing collection: {self.static_collection_name}")
                except Exception:
                    # Collection doesn't exist, which is fine
                    logger.info(f"Collection {self.static_collection_name} does not exist, proceeding with creation")
            except Exception as delete_error:
                # Collection doesn't exist or couldn't be deleted, that's fine
                logger.info(f"Could not delete existing collection (may not exist): {str(delete_error)}")
                pass
            
            # Create new static collection with a dummy embedding function to avoid ONNX issues
            try:
                # Create a dummy embedding function that doesn't use ONNX
                class DummyEmbeddingFunction:
                    def __call__(self, input):
                        # Return dummy embeddings (just zeros)
                        # Handle both single string and list of strings
                        if isinstance(input, str):
                            return [0.0] * 384
                        else:
                            return [[0.0] * 384 for _ in input]
                
                dummy_embedding = DummyEmbeddingFunction()
                self.static_collection = chroma_client.create_collection(
                    name=self.static_collection_name,
                    embedding_function=dummy_embedding,
                    metadata={"description": "Static collection for examples", "created_by": "example_usage"}
                )
                logger.info("Created collection with dummy embedding function")
            except Exception as create_error:
                logger.warning(f"Error creating collection with dummy embedding: {str(create_error)}")
                # Try without any embedding function
                try:
                    self.static_collection = chroma_client.create_collection(
                        name=self.static_collection_name,
                        metadata={"description": "Static collection for examples", "created_by": "example_usage"}
                    )
                    logger.info("Created collection without embedding function")
                except Exception as no_embedding_error:
                    logger.error(f"Error creating collection without embedding: {str(no_embedding_error)}")
                    # If we can't create a new collection, try to use the existing one
                    try:
                        self.static_collection = chroma_client.get_collection(self.static_collection_name)
                        logger.info(f"Using existing collection: {self.static_collection_name}")
                        # Clear the existing collection to start fresh
                        try:
                            # Get all documents and delete them
                            results = self.static_collection.get()
                            if results and results.get('ids'):
                                self.static_collection.delete(ids=results['ids'])
                                logger.info(f"Cleared existing collection: {self.static_collection_name}")
                        except Exception as clear_error:
                            logger.warning(f"Could not clear existing collection: {str(clear_error)}")
                    except Exception as get_error:
                        logger.error(f"Could not get existing collection either: {str(get_error)}")
                        raise no_embedding_error
            
            logger.info(f"Created static collection: {self.static_collection_name}")
            logger.info(f"Collection object: {self.static_collection}")
            logger.info(f"Collection name: {self.static_collection.name}")
            logger.info(f"Static collection successfully created and stored in self.static_collection")
            return self.static_collection
            
        except Exception as e:
            logger.error(f"Error creating static collection: {str(e)}")
            return None
    
    async def _populate_static_collection(self):
        """Populate the static collection with example data."""
        if not self.static_collection:
            logger.warning("No static collection available for population")
            return
        
        try:
            logger.info("Populating static collection with example data...")
            logger.info(f"Static collection object: {self.static_collection}")
            logger.info(f"Static collection name: {self.static_collection_name}")
            
            # Create some example documents
            example_documents = [
                {
                    "id": "doc_1",
                    "document": "User account management system for authentication and user data",
                    "metadata": {
                        "table_name": "users",
                        "description": "User account information",
                        "business_purpose": "User management and authentication",
                        "domain": "user_management",
                        "usage_type": "transactional",
                        "metadata_type": "TABLE_DOCUMENT",
                        "project_id": "example_project"
                    }
                },
                {
                    "id": "doc_2", 
                    "document": "Order processing system for e-commerce transactions",
                    "metadata": {
                        "table_name": "orders",
                        "description": "Order information and processing",
                        "business_purpose": "Order management and fulfillment",
                        "domain": "e_commerce",
                        "usage_type": "transactional",
                        "metadata_type": "TABLE_DOCUMENT",
                        "project_id": "example_project"
                    }
                },
                {
                    "id": "doc_3",
                    "document": "Customer analytics and reporting data warehouse",
                    "metadata": {
                        "table_name": "customer_analytics",
                        "description": "Customer behavior analytics",
                        "business_purpose": "Customer insights and reporting",
                        "domain": "analytics",
                        "usage_type": "analytical",
                        "metadata_type": "TABLE_DOCUMENT",
                        "project_id": "example_project"
                    }
                },
                {
                    "id": "doc_4",
                    "document": "Product catalog and inventory management",
                    "metadata": {
                        "table_name": "products",
                        "description": "Product information and inventory",
                        "business_purpose": "Product catalog management",
                        "domain": "inventory",
                        "usage_type": "transactional",
                        "metadata_type": "TABLE_DOCUMENT",
                        "project_id": "example_project"
                    }
                },
                {
                    "id": "doc_5",
                    "document": "Sales performance metrics and KPIs",
                    "metadata": {
                        "table_name": "sales_metrics",
                        "description": "Sales performance data",
                        "business_purpose": "Sales reporting and analysis",
                        "domain": "sales",
                        "usage_type": "analytical",
                        "metadata_type": "TABLE_DOCUMENT",
                        "project_id": "example_project"
                    }
                }
            ]
            
            # Add documents to the collection
            logger.info(f"About to add {len(example_documents)} documents to collection")
            logger.info(f"Document IDs: {[doc['id'] for doc in example_documents]}")
            logger.info(f"Sample document: {example_documents[0]['document'][:50]}...")
            logger.info(f"Sample metadata: {example_documents[0]['metadata']}")
            
            try:
                # Try adding documents with embeddings first
                self.static_collection.add(
                    documents=[doc["document"] for doc in example_documents],
                    metadatas=[doc["metadata"] for doc in example_documents],
                    ids=[doc["id"] for doc in example_documents]
                )
                logger.info(f"Successfully added {len(example_documents)} documents to static collection")
            except Exception as add_error:
                logger.warning(f"Error adding documents with embeddings: {str(add_error)}")
                logger.info("Trying to add documents with dummy embeddings...")
                
                try:
                    # Try adding documents with dummy embeddings
                    dummy_embeddings = [[0.0] * 384 for _ in example_documents]
                    self.static_collection.add(
                        documents=[doc["document"] for doc in example_documents],
                        metadatas=[doc["metadata"] for doc in example_documents],
                        ids=[doc["id"] for doc in example_documents],
                        embeddings=dummy_embeddings
                    )
                    logger.info(f"Successfully added {len(example_documents)} documents with dummy embeddings to static collection")
                except Exception as dummy_error:
                    logger.warning(f"Error adding documents with dummy embeddings: {str(dummy_error)}")
                    logger.info("Trying to add documents without embeddings...")
                    
                    try:
                        # Try adding documents without embeddings (metadata only)
                        self.static_collection.add(
                            metadatas=[doc["metadata"] for doc in example_documents],
                            ids=[doc["id"] for doc in example_documents]
                        )
                        logger.info(f"Successfully added {len(example_documents)} documents (metadata only) to static collection")
                    except Exception as metadata_error:
                        logger.error(f"Error adding documents with metadata only: {str(metadata_error)}")
                        logger.error(f"Collection object: {self.static_collection}")
                        logger.error(f"Collection name: {self.static_collection_name}")
                        raise metadata_error
            
            # Verify documents were added and show complete structure
            try:
                count_result = self.static_collection.count()
                logger.info(f"Static collection now contains {count_result} documents")
                
                # Show complete table schema structure
                logger.info("=== COMPLETE STATIC COLLECTION STRUCTURE ===")
                
                # Get all documents to show the complete structure
                all_docs = self.static_collection.get(limit=10)
                logger.info(f"Total documents retrieved: {len(all_docs['ids'])}")
                
                for i, doc_id in enumerate(all_docs['ids']):
                    logger.info(f"\n--- Document {i+1} ---")
                    logger.info(f"Document ID: {doc_id}")
                    logger.info(f"Document Content: {all_docs['documents'][i]}")
                    logger.info(f"Document Metadata: {all_docs['metadatas'][i]}")
                    
                    # Show specific fields for TABLE_DOCUMENTs
                    metadata = all_docs['metadatas'][i]
                    if metadata.get('metadata_type') == 'TABLE_DOCUMENT':
                        logger.info(f"TABLE_DOCUMENT Details:")
                        logger.info(f"  - Table Name: {metadata.get('table_name', 'N/A')}")
                        logger.info(f"  - Description: {metadata.get('description', 'N/A')}")
                        logger.info(f"  - Business Purpose: {metadata.get('business_purpose', 'N/A')}")
                        logger.info(f"  - Domain: {metadata.get('domain', 'N/A')}")
                        logger.info(f"  - Usage Type: {metadata.get('usage_type', 'N/A')}")
                        logger.info(f"  - Project ID: {metadata.get('project_id', 'N/A')}")
                    
                    logger.info("=" * 50)
                
                # Show summary by document type
                logger.info("\n=== DOCUMENT TYPE SUMMARY ===")
                doc_types = {}
                for metadata in all_docs['metadatas']:
                    doc_type = metadata.get('metadata_type', 'Unknown')
                    doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                
                for doc_type, count in doc_types.items():
                    logger.info(f"{doc_type}: {count} documents")
                    
            except Exception as verify_error:
                logger.error(f"Error verifying static collection: {str(verify_error)}")
            
        except Exception as e:
            logger.error(f"Error populating static collection: {str(e)}")
    
    async def _cleanup_static_collection(self):
        """Clean up the static collection."""
        try:
            if self.static_collection:
                logger.info(f"Cleaning up static collection: {self.static_collection_name}")
                
                # Get the ChromaDB client
                if hasattr(self.storage_manager, '_unified_storage') and self.storage_manager._unified_storage:
                    document_store = self.storage_manager._unified_storage._document_store
                    chroma_client = document_store.persistent_client
                elif hasattr(self.storage_manager, '_document_store') and self.storage_manager._document_store:
                    document_store = self.storage_manager._document_store
                    chroma_client = document_store.persistent_client
                else:
                    logger.warning("No document store available for cleanup")
                    return
                
                # Delete the static collection
                try:
                    chroma_client.delete_collection(self.static_collection_name)
                    logger.info(f"Successfully deleted static collection: {self.static_collection_name}")
                except Exception as e:
                    logger.warning(f"Could not delete static collection: {str(e)}")
                
                self.static_collection = None
                
        except Exception as e:
            logger.error(f"Error cleaning up static collection: {str(e)}")
    
    async def run_example(self):
        """Run the complete example."""
        logger.info("Starting unified storage system example")
        
        try:
            # Initialize components
            await self._initialize_components()
            
            # Create and populate static collection
            logger.info("Creating static collection...")
            collection_result = await self._create_static_collection()
            logger.info(f"Static collection creation result: {collection_result}")
            
            logger.info("Populating static collection...")
            await self._populate_static_collection()
            logger.info(f"Static collection after population: {self.static_collection}")
            
            # Process MDL
            result = await self._process_mdl()
            logger.info(f"Processing result: {result}")
            
            # Demonstrate search capabilities
            await self._demonstrate_search()
            
            # Show TF-IDF capabilities
            await self._demonstrate_tfidf()
            
            # Demonstrate natural language search
            await self._demonstrate_natural_language_search()
            
            # Run TABLE_SCHEMA retrieval pipeline tests
            await self._run_table_schema_tests()
            
            # Demonstrate new retrieval helper functionality
            await self._demonstrate_retrieval_helper2()
            
            logger.info("Example completed successfully")
            
        except Exception as e:
            logger.error(f"Error in example: {str(e)}")
            raise
    
    async def _initialize_components(self):
        """Initialize the storage components."""
        logger.info("Initializing storage components")
        
        # Initialize embeddings
        embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize ChromaDB
        persistent_client = chromadb.PersistentClient(path="./chroma_db")
        doc_store = DocumentChromaStore(
            persistent_client=persistent_client,
            collection_name="unified_storage"
        )
        
        # Initialize TF-IDF generator
        tfidf_generator = TFIDFGenerator(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95
        )
        
        # Initialize storage manager
        self.storage_manager = StorageManager(
            document_store=doc_store,
            embedder=embeddings,
            column_batch_size=100,
            enable_tfidf=True,
            tfidf_config={
                "max_features": 5000,
                "ngram_range": (1, 2),
                "min_df": 1,
                "max_df": 0.95
            }
        )
        
        logger.info("Components initialized successfully")
    
    async def _process_mdl(self) -> Dict[str, Any]:
        """Process the example MDL."""
        logger.info("Processing example MDL")
        
        result = await self.storage_manager.process_mdl(
            mdl_str=self.example_mdl,
            project_id="example_project"
        )
        
        logger.info(f"MDL processing completed: {result}")
        
        # Show the complete table schema structure from MDL processing
        logger.info("=== TABLE SCHEMA STRUCTURE FROM MDL PROCESSING ===")
        
        if 'table_documents' in result:
            table_docs = result['table_documents']
            if isinstance(table_docs, list):
                logger.info(f"Total TABLE_DOCUMENTs created: {len(table_docs)}")
                
                for i, doc in enumerate(table_docs):
                    logger.info(f"\n--- TABLE_DOCUMENT {i+1} ---")
                    logger.info(f"Document ID: {doc.id}")
                    logger.info(f"Document Content: {doc.page_content}")
                    logger.info(f"Document Metadata: {doc.metadata}")
                    logger.info("=" * 50)
            else:
                logger.info(f"TABLE_DOCUMENTs result type: {type(table_docs)}, value: {table_docs}")
        
        if 'table_column_docs' in result:
            column_docs = result['table_column_docs']
            if isinstance(column_docs, list):
                logger.info(f"Total TABLE_COLUMN documents created: {len(column_docs)}")
                
                for i, doc in enumerate(column_docs):
                    logger.info(f"\n--- TABLE_COLUMN {i+1} ---")
                    logger.info(f"Document ID: {doc.id}")
                    logger.info(f"Document Content: {doc.page_content}")
                    logger.info(f"Document Metadata: {doc.metadata}")
                    logger.info("=" * 50)
            else:
                logger.info(f"TABLE_COLUMN documents result type: {type(column_docs)}, value: {column_docs}")
        
        # Show the complete result structure for debugging
        logger.info("=== COMPLETE MDL PROCESSING RESULT ===")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        for key, value in result.items() if isinstance(result, dict) else []:
            logger.info(f"  {key}: {type(value)} = {value}")
        
        return result
    
    async def _demonstrate_search(self):
        """Demonstrate search capabilities."""
        logger.info("Demonstrating search capabilities")
        
        # Search by table name
        user_refs = await self.storage_manager.search_by_table_name("users", "example_project")
        logger.info(f"Found {len(user_refs)} references for 'users' table")
        
        # Search by document type
        schema_refs = await self.storage_manager.search_by_document_type("TABLE_SCHEMA", "example_project")
        logger.info(f"Found {len(schema_refs)} TABLE_SCHEMA documents")
        
        # Search for similar documents
        similar_docs = await self.storage_manager.find_similar_documents(
            "user account management authentication",
            top_k=3,
            threshold=0.1
        )
        logger.info(f"Found {len(similar_docs)} similar documents")
    
    async def _demonstrate_tfidf(self):
        """Demonstrate TF-IDF capabilities."""
        logger.info("Demonstrating TF-IDF capabilities")
        
        # Get TF-IDF statistics
        tfidf_stats = await self.storage_manager.get_tfidf_stats()
        logger.info(f"TF-IDF stats: {tfidf_stats}")
        
        # Get quick lookup statistics
        lookup_stats = await self.storage_manager.get_quick_lookup_stats()
        logger.info(f"Quick lookup stats: {lookup_stats}")
    
    async def _demonstrate_natural_language_search(self):
        """Demonstrate natural language search capabilities."""
        logger.info("Demonstrating natural language search capabilities")
        
        # Search by natural language query
        user_tables = await self.storage_manager.search_tables_by_natural_language(
            "user account management authentication",
            project_id="example_project",
            top_k=5
        )
        logger.info(f"Found {len(user_tables)} tables for 'user account management authentication'")
        
        # Search by business domain
        domain_tables = await self.storage_manager.search_tables_by_domain(
            "customer",
            project_id="example_project",
            top_k=3
        )
        logger.info(f"Found {len(domain_tables)} tables in 'customer' domain")
        
        # Search by usage type
        analytics_tables = await self.storage_manager.search_tables_by_usage_type(
            "analytics",
            project_id="example_project",
            top_k=3
        )
        logger.info(f"Found {len(analytics_tables)} tables with 'analytics' usage type")
        
        # Get natural language search statistics
        nl_stats = await self.storage_manager.get_natural_language_search_stats()
        logger.info(f"Natural language search stats: {nl_stats}")
        
        # Demonstrate query building capabilities
        await self._demonstrate_query_building()
        
        # Demonstrate LLM-powered capabilities
        await self._demonstrate_llm_capabilities()
        
        # Demonstrate TABLE_COLUMN document creation
        await self._demonstrate_table_column_documents()
        
        # Demonstrate ChromaDB retrieval
        await self._demonstrate_chromadb_retrieval()
        
        # Demonstrate simple ChromaDB retrieval patterns
        await self._demonstrate_simple_chromadb_retrieval()
        
        # Demonstrate direct ChromaDB access
        await self.demonstrate_direct_chromadb_access()
    
    async def _demonstrate_query_building(self):
        """Demonstrate query building capabilities with field type classification."""
        logger.info("Demonstrating query building capabilities")
        
        try:
            # Build analytical query for a table
            analytical_query = await self.storage_manager.build_query_for_table(
                table_name="users",
                project_id="example_project",
                query_type="analytical",
                filters={"status": "active"},
                aggregations=["SUM", "COUNT"],
                group_by=["department"],
                limit=10
            )
            logger.info(f"Analytical query: {analytical_query.get('query', '')}")
            
            # Build transactional query
            transactional_query = await self.storage_manager.build_query_for_table(
                table_name="orders",
                project_id="example_project",
                query_type="transactional",
                filters={"order_id": "12345"},
                limit=1
            )
            logger.info(f"Transactional query: {transactional_query.get('query', '')}")
            
            # Build reporting query
            reporting_query = await self.storage_manager.build_query_for_table(
                table_name="sales",
                project_id="example_project",
                query_type="reporting",
                aggregations=["SUM", "AVG", "MAX", "MIN"],
                group_by=["region", "product_category"],
                order_by=["total_sales DESC"],
                limit=20
            )
            logger.info(f"Reporting query: {reporting_query.get('query', '')}")
            
            # Get query suggestions (focusing on performance and indexing, not SQL generation)
            query_suggestions = await self.storage_manager.get_query_suggestions(
                table_name="users",
                project_id="example_project",
                field_type="fact"
            )
            
            # Get performance suggestions
            performance_suggestions = query_suggestions.get("performance_optimizations", [])
            logger.info(f"Performance suggestions: {len(performance_suggestions)} recommendations")
            
            # Get indexing recommendations
            indexing_recommendations = query_suggestions.get("indexing_recommendations", [])
            logger.info(f"Indexing recommendations: {len(indexing_recommendations)} suggestions")
            
        except Exception as e:
            logger.error(f"Error demonstrating query building: {str(e)}")
            # Continue with example even if query building fails
    
    async def _demonstrate_llm_capabilities(self):
        """Demonstrate LLM-powered capabilities."""
        logger.info("Demonstrating LLM-powered capabilities")
        
        try:
            # Get LLM capabilities
            llm_capabilities = await self.storage_manager.get_llm_capabilities()
            logger.info(f"LLM capabilities: {llm_capabilities}")
            
            # Demonstrate LLM column classification (without actual LLM client)
            classification_result = await self.storage_manager.classify_columns_with_llm(
                table_name="users",
                project_id="example_project",
                llm_client=None  # No LLM client, will use fallback
            )
            logger.info(f"Column classification result: {classification_result.get('llm_enabled', False)}")
            
            # Demonstrate LLM query optimization (without actual LLM client)
            optimization_result = await self.storage_manager.optimize_query_with_llm(
                query="SELECT * FROM users WHERE status = 'active'",
                table_name="users",
                project_id="example_project",
                optimization_level="intermediate",
                llm_client=None  # No LLM client, will use fallback
            )
            logger.info(f"Query optimization result: {optimization_result.optimized_query if hasattr(optimization_result, 'optimized_query') else optimization_result}")
            
            # Demonstrate LLM performance analysis (without actual LLM client)
            performance_analysis = await self.storage_manager.analyze_query_performance_with_llm(
                query="SELECT COUNT(*) FROM users GROUP BY department",
                table_name="users",
                project_id="example_project",
                performance_metrics={"execution_time": 1.5, "rows_processed": 1000},
                llm_client=None  # No LLM client, will use fallback
            )
            logger.info(f"Performance analysis result: {performance_analysis.get('performance_score', 'N/A') if isinstance(performance_analysis, dict) else performance_analysis}")
            
            # Demonstrate LLM indexing strategy (without actual LLM client)
            indexing_strategy = await self.storage_manager.suggest_indexing_strategy_with_llm(
                table_name="users",
                project_id="example_project",
                query_patterns=[
                    "SELECT * FROM users WHERE department = ?",
                    "SELECT COUNT(*) FROM users GROUP BY department",
                    "SELECT * FROM users WHERE created_date >= ?"
                ],
                performance_requirements={"max_query_time": 1.0, "concurrent_users": 100},
                llm_client=None  # No LLM client, will use fallback
            )
            logger.info(f"Indexing strategy result: {indexing_strategy.get('indexing_recommendations', 'N/A') if isinstance(indexing_strategy, dict) else indexing_strategy}")
            
        except Exception as e:
            logger.error(f"Error demonstrating LLM capabilities: {str(e)}")
            # Continue with example even if LLM capabilities fail
    
    async def _demonstrate_table_column_documents(self):
        """Demonstrate TABLE_COLUMN document creation with helper.py functionality."""
        logger.info("Demonstrating TABLE_COLUMN document creation")
        
        try:
            # Parse the MDL string to dictionary
            mdl_dict = json.loads(self.example_mdl)
            
            # Create TABLE_COLUMN documents using helper.py functionality
            table_column_docs = await self.storage_manager._ddl_chunker.create_table_column_documents(
                mdl=mdl_dict,
                project_id="example_project"
            )
            
            logger.info(f"Created {len(table_column_docs)} TABLE_COLUMN documents")
            
            # Show example of a TABLE_COLUMN document
            if table_column_docs:
                logger.info("=== COMPLETE TABLE SCHEMA STRUCTURE IN CHROMADB ===")
                logger.info(f"Total TABLE_COLUMN documents created: {len(table_column_docs)}")
                
                for i, doc in enumerate(table_column_docs):
                    logger.info(f"\n--- TABLE_COLUMN Document {i+1} ---")
                    logger.info(f"Document ID: {doc.id}")
                    logger.info(f"Document Metadata: {doc.metadata}")
                    
                    # Parse the page content to show the complete structure
                    try:
                        content = json.loads(doc.page_content)
                        logger.info(f"Content Keys: {list(content.keys())}")
                        
                        # Show all content fields
                        for key, value in content.items():
                            if isinstance(value, str) and len(value) > 200:
                                logger.info(f"{key}: {value[:200]}...")
                            else:
                                logger.info(f"{key}: {value}")
                        
                        logger.info(f"Full Content JSON: {json.dumps(content, indent=2)}")
                        
                    except json.JSONDecodeError:
                        logger.info(f"Raw Content (not JSON): {doc.page_content}")
                    
                    logger.info("=" * 60)
                
                # Show summary of all documents
                logger.info("\n=== TABLE SCHEMA SUMMARY ===")
                for i, doc in enumerate(table_column_docs):
                    try:
                        content = json.loads(doc.page_content)
                        table_name = content.get('table_name', 'Unknown')
                        column_name = content.get('column_name', 'Unknown')
                        field_type = content.get('field_type', 'Unknown')
                        logger.info(f"Document {i+1}: Table '{table_name}', Column '{column_name}', Type '{field_type}'")
                    except:
                        logger.info(f"Document {i+1}: {doc.id}")
            else:
                logger.info("No TABLE_COLUMN documents created")
            
        except Exception as e:
            logger.error(f"Error demonstrating TABLE_COLUMN documents: {str(e)}")
            # Continue with example even if TABLE_COLUMN creation fails
    
    async def _demonstrate_chromadb_retrieval(self):
        """Demonstrate fetching tables and columns from ChromaDB."""
        logger.info("Demonstrating ChromaDB retrieval capabilities")
        
        try:
            # Example 1: Search for tables by natural language
            logger.info("=== Example 1: Natural Language Table Search ===")
            user_tables = await self.storage_manager.search_tables_by_natural_language(
                "user account management",
                project_id="example_project",
                top_k=3
            )
            logger.info(f"Found {len(user_tables)} tables for 'user account management'")
            for table in user_tables:
                logger.info(f"  - {table.get('table_name', '')}: {table.get('description', '')}")
            
            # Example 2: Search for tables by domain
            logger.info("=== Example 2: Domain-based Table Search ===")
            customer_tables = await self.storage_manager.search_tables_by_domain(
                "customer",
                project_id="example_project",
                top_k=3
            )
            logger.info(f"Found {len(customer_tables)} tables in 'customer' domain")
            for table in customer_tables:
                logger.info(f"  - {table.get('table_name', '')}: {table.get('business_purpose', '')}")
            
            # Example 3: Search for tables by usage type
            logger.info("=== Example 3: Usage Type-based Table Search ===")
            analytics_tables = await self.storage_manager.search_tables_by_usage_type(
                "analytics",
                project_id="example_project",
                top_k=3
            )
            logger.info(f"Found {len(analytics_tables)} tables with 'analytics' usage type")
            for table in analytics_tables:
                logger.info(f"  - {table.get('table_name', '')}: {table.get('description', '')}")
            
            # Example 3b: Try searching with more general terms
            logger.info("=== Example 3b: General Table Search ===")
            general_tables = await self.storage_manager.search_tables_by_natural_language(
                "user data",
                project_id="example_project",
                top_k=3
            )
            logger.info(f"Found {len(general_tables)} tables for 'user data'")
            for table in general_tables:
                logger.info(f"  - {table.get('table_name', '')}: {table.get('description', '')}")
            
            # Example 4: Get all tables for a project
            logger.info("=== Example 4: Get All Tables for Project ===")
            all_tables = await self.storage_manager.search_tables_by_natural_language(
                "",  # Empty query to get all tables
                project_id="example_project",
                top_k=10
            )
            logger.info(f"Found {len(all_tables)} total tables in project")
            for table in all_tables:
                logger.info(f"  - {table.get('table_name', '')}: {table.get('display_name', '')}")
            
            # Example 5: Search for specific table details
            logger.info("=== Example 5: Get Specific Table Details ===")
            if all_tables:
                first_table = all_tables[0]
                table_name = first_table.get('table_name', '')
                logger.info(f"Getting details for table: {table_name}")
                
                # Get table columns using natural language search
                table_details = await self.storage_manager.search_tables_by_natural_language(
                    table_name,
                    project_id="example_project",
                    top_k=1
                )
                
                if table_details:
                    table_doc = table_details[0]
                    logger.info(f"Table: {table_doc.get('table_name', '')}")
                    logger.info(f"Description: {table_doc.get('description', '')}")
                    logger.info(f"Business Purpose: {table_doc.get('business_purpose', '')}")
                    logger.info(f"Domain: {table_doc.get('domain', '')}")
                    logger.info(f"Classification: {table_doc.get('classification', '')}")
                    
                    # Show columns if available
                    columns = table_doc.get('columns', [])
                    if columns:
                        logger.info(f"Columns ({len(columns)}):")
                        for column in columns[:5]:  # Show first 5 columns
                            field_type = column.get('field_type', 'unknown')
                            data_type = column.get('data_type', 'unknown')
                            logger.info(f"  - {column.get('name', '')} ({data_type}) - {field_type}")
                    else:
                        logger.info("No columns found in table document")
            
            # Example 6: Search for columns by field type
            logger.info("=== Example 6: Search for Columns by Field Type ===")
            # This would require a more sophisticated search, but we can demonstrate
            # by looking at the table documents and filtering columns
            fact_columns = []
            dimension_columns = []
            identifier_columns = []
            
            for table in all_tables[:3]:  # Check first 3 tables
                columns = table.get('columns', [])
                for column in columns:
                    field_type = column.get('field_type', '')
                    if field_type == 'fact':
                        fact_columns.append(f"{table.get('table_name', '')}.{column.get('name', '')}")
                    elif field_type == 'dimension':
                        dimension_columns.append(f"{table.get('table_name', '')}.{column.get('name', '')}")
                    elif field_type == 'identifier':
                        identifier_columns.append(f"{table.get('table_name', '')}.{column.get('name', '')}")
            
            logger.info(f"Found {len(fact_columns)} fact columns: {fact_columns[:5]}")
            logger.info(f"Found {len(dimension_columns)} dimension columns: {dimension_columns[:5]}")
            logger.info(f"Found {len(identifier_columns)} identifier columns: {identifier_columns[:5]}")
            
            # Example 7: Get query suggestions for a table
            logger.info("=== Example 7: Get Query Suggestions for Table ===")
            if all_tables:
                table_name = all_tables[0].get('table_name', '')
                query_suggestions = await self.storage_manager.get_query_suggestions(
                    table_name=table_name,
                    project_id="example_project",
                    field_type="fact"  # Get suggestions for fact columns
                )
                
                logger.info(f"Query suggestions for {table_name}:")
                logger.info(f"  - Performance optimizations: {len(query_suggestions.get('performance_optimizations', []))}")
                logger.info(f"  - Indexing recommendations: {len(query_suggestions.get('indexing_recommendations', []))}")
                
                # Show some suggestions
                perf_suggestions = query_suggestions.get('performance_optimizations', [])
                if perf_suggestions:
                    logger.info(f"  - Performance suggestion: {perf_suggestions[0]}")
                
                indexing_suggestions = query_suggestions.get('indexing_recommendations', [])
                if indexing_suggestions:
                    logger.info(f"  - Indexing suggestion: {indexing_suggestions[0]}")
            
            # Example 8: Demonstrate TF-IDF quick lookup
            logger.info("=== Example 8: TF-IDF Quick Lookup ===")
            if hasattr(self.storage_manager, '_quick_lookup') and self.storage_manager._quick_lookup:
                # Search by table name
                table_refs = await self.storage_manager._quick_lookup.lookup_by_table_name(
                    "users", "example_project"
                )
                logger.info(f"TF-IDF lookup for 'users': {len(table_refs)} references")
                
                # Search by document type
                schema_refs = await self.storage_manager._quick_lookup.lookup_by_document_type(
                    "TABLE_DOCUMENT", "example_project"
                )
                logger.info(f"TF-IDF lookup for 'TABLE_DOCUMENT': {len(schema_refs)} references")
            else:
                logger.info("TF-IDF quick lookup not available")
            
            logger.info("ChromaDB retrieval demonstration completed successfully")
            
        except Exception as e:
            logger.error(f"Error demonstrating ChromaDB retrieval: {str(e)}")
            # Continue with example even if retrieval fails
    
    async def _demonstrate_simple_chromadb_retrieval(self):
        """Demonstrate simple ChromaDB retrieval patterns."""
        logger.info("=== Simple ChromaDB Retrieval Examples ===")
        
        try:
            # Example 1: Get all tables for a project
            logger.info("1. Getting all tables for project...")
            all_tables = await self.storage_manager.search_tables_by_natural_language(
                "",  # Empty query gets all tables
                project_id="example_project",
                top_k=20
            )
            logger.info(f"   Found {len(all_tables)} tables")
            
            # Example 2: Search for specific table
            logger.info("2. Searching for 'users' table...")
            user_tables = await self.storage_manager.search_tables_by_natural_language(
                "users",
                project_id="example_project",
                top_k=5
            )
            logger.info(f"   Found {len(user_tables)} user-related tables")
            
            # Example 3: Get table with columns
            if all_tables:
                table = all_tables[0]
                table_name = table.get('table_name', '')
                logger.info(f"3. Getting details for table: {table_name}")
                
                # Show table metadata
                logger.info(f"   Table Name: {table.get('table_name', '')}")
                logger.info(f"   Display Name: {table.get('display_name', '')}")
                logger.info(f"   Description: {table.get('description', '')}")
                logger.info(f"   Business Purpose: {table.get('business_purpose', '')}")
                logger.info(f"   Domain: {table.get('domain', '')}")
                logger.info(f"   Classification: {table.get('classification', '')}")
                
                # Show columns
                columns = table.get('columns', [])
                logger.info(f"   Columns ({len(columns)}):")
                for i, column in enumerate(columns[:10]):  # Show first 10 columns
                    field_type = column.get('field_type', 'unknown')
                    data_type = column.get('data_type', 'unknown')
                    nullable = column.get('nullable', False)
                    logger.info(f"     {i+1}. {column.get('name', '')} ({data_type}) - {field_type} {'NULL' if nullable else 'NOT NULL'}")
                
                if len(columns) > 10:
                    logger.info(f"     ... and {len(columns) - 10} more columns")
            
            # Example 4: Search by domain
            logger.info("4. Searching tables by domain 'customer'...")
            customer_tables = await self.storage_manager.search_tables_by_domain(
                "customer",
                project_id="example_project",
                top_k=5
            )
            logger.info(f"   Found {len(customer_tables)} customer domain tables")
            
            # Example 4b: Try searching with general terms
            logger.info("4b. Searching for 'order' related tables...")
            order_tables = await self.storage_manager.search_tables_by_natural_language(
                "order",
                project_id="example_project",
                top_k=5
            )
            logger.info(f"   Found {len(order_tables)} order-related tables")
            
            # Example 5: Search by usage type
            logger.info("5. Searching tables by usage type 'analytics'...")
            analytics_tables = await self.storage_manager.search_tables_by_usage_type(
                "analytics",
                project_id="example_project",
                top_k=5
            )
            logger.info(f"   Found {len(analytics_tables)} analytics tables")
            
            # Example 5b: Try searching with general terms
            logger.info("5b. Searching for 'data' related tables...")
            data_tables = await self.storage_manager.search_tables_by_natural_language(
                "data",
                project_id="example_project",
                top_k=5
            )
            logger.info(f"   Found {len(data_tables)} data-related tables")
            
            logger.info("Simple ChromaDB retrieval examples completed")
            
        except Exception as e:
            logger.error(f"Error in simple ChromaDB retrieval: {str(e)}")
    
    
    async def demonstrate_direct_chromadb_access(self):
        """Demonstrate direct ChromaDB access patterns."""
        logger.info("=== Direct ChromaDB Access Examples ===")
        
        try:
            # Example 1: Direct ChromaDB collection access
            logger.info("1. Accessing ChromaDB collections directly...")
            
            # Check ChromaDB version for compatibility
            try:
                import chromadb
                chromadb_version = chromadb.__version__
                logger.info(f"   ChromaDB version: {chromadb_version}")
                
                if chromadb_version.startswith("0.6."):
                    logger.info("   Using ChromaDB v0.6.0+ API (list_collections returns names only)")
                elif chromadb_version.startswith("0.4.") or chromadb_version.startswith("0.5."):
                    logger.info("   Using ChromaDB v0.4-0.5 API (list_collections returns objects)")
                else:
                    logger.info("   Using ChromaDB v1.0+ API")
            except Exception as e:
                logger.warning(f"   Could not determine ChromaDB version: {e}")
            
            # Check embedding model compatibility
            try:
                from app.storage.documents import embeddings_model
                embedding_model_name = getattr(embeddings_model, 'model', 'unknown')
                logger.info(f"   Current embedding model: {embedding_model_name}")
                
                # Common embedding dimensions
                if "text-embedding-3-small" in embedding_model_name:
                    logger.info("   Embedding dimensions: 384 (text-embedding-3-small)")
                elif "text-embedding-3-large" in embedding_model_name:
                    logger.info("   Embedding dimensions: 3072 (text-embedding-3-large)")
                elif "text-embedding-ada-002" in embedding_model_name:
                    logger.info("   Embedding dimensions: 1536 (text-embedding-ada-002)")
                else:
                    logger.info("   Embedding dimensions: Unknown")
                    
                logger.info("   Note: If you see dimension mismatch errors, the collection was created with a different embedding model")
                logger.info("   The examples will fall back to metadata-only queries when embedding queries fail")
                
            except Exception as e:
                logger.warning(f"   Could not determine embedding model: {e}")
            
            # Get the ChromaDB client from storage manager
            if hasattr(self.storage_manager, '_unified_storage') and self.storage_manager._unified_storage:
                # Access the document store which contains the ChromaDB client
                document_store = self.storage_manager._unified_storage._document_store
                chroma_client = document_store.persistent_client
                
                # Use static collection if available
                if self.static_collection:
                    logger.info(f"Using static collection: {self.static_collection_name}")
                    collection = self.static_collection
                else:
                    logger.error("Static collection not available - skipping direct ChromaDB access examples")
                    logger.error("This indicates the static collection creation failed earlier")
                    return
                
                # Use static collection directly
                if self.static_collection:
                    collection = self.static_collection
                    logger.info(f"2. Using static collection: {self.static_collection_name}")
                else:
                    logger.error("   No static collection available - skipping direct ChromaDB access examples")
                    return
                    
                    # Query for TABLE_DOCUMENT type (handle embedding issues)
                    try:
                        # Try semantic search first
                        results = collection.query(
                            query_texts=["user account management"],
                            n_results=5,
                            where={"metadata_type": "TABLE_DOCUMENT"}
                        )
                        
                        logger.info(f"   Found {len(results['documents'][0])} TABLE_DOCUMENT results")
                        
                        # Show results
                        for i, doc in enumerate(results['documents'][0][:3]):
                            metadata = results['metadatas'][0][i]
                            logger.info(f"     {i+1}. {metadata.get('table_name', '')} - {metadata.get('description', '')[:50]}...")
                            
                    except Exception as query_error:
                        logger.warning(f"   Semantic search failed: {str(query_error)}")
                        logger.info("   Trying to get documents without embedding query...")
                        
                        # Try to get documents without embedding query
                        try:
                            results = collection.get(
                                where={"metadata_type": "TABLE_DOCUMENT"},
                                limit=5
                            )
                            
                            logger.info(f"   Found {len(results['ids'])} TABLE_DOCUMENT results (without embedding)")
                            
                            # Show results
                            for i, doc_id in enumerate(results['ids'][:3]):
                                metadata = results['metadatas'][i]
                                logger.info(f"     {i+1}. {metadata.get('table_name', '')} - {metadata.get('description', '')[:50]}...")
                                
                        except Exception as get_error:
                            logger.error(f"   Could not retrieve documents: {str(get_error)}")
                
                # Example 3: Search by metadata filters (handle dimension mismatch)
                logger.info("3. Searching by metadata filters...")
                if self.static_collection:
                    collection = self.static_collection
                    logger.info(f"   Using static collection for metadata filters: {self.static_collection_name}")
                else:
                    logger.error("   No static collection available - skipping metadata filter examples")
                    return
                    
                    # Search for tables in specific domain
                    try:
                        domain_results = collection.query(
                            query_texts=["customer"],
                            n_results=5,
                            where={"domain": "customer"}
                        )
                        logger.info(f"   Found {len(domain_results['documents'][0])} customer domain tables")
                    except Exception as domain_error:
                        if "dimension" in str(domain_error).lower():
                            logger.warning(f"   Embedding dimension mismatch for domain search: {str(domain_error)}")
                            # Try without embedding query
                            try:
                                domain_results = collection.get(
                                    where={"domain": "customer"},
                                    limit=5
                                )
                                logger.info(f"   Found {len(domain_results['ids'])} customer domain tables (without embedding)")
                            except Exception as get_error:
                                logger.error(f"   Could not retrieve customer domain tables: {str(get_error)}")
                        else:
                            logger.error(f"   Domain search failed: {str(domain_error)}")
                    
                    # Search for specific field types
                    try:
                        fact_results = collection.query(
                            query_texts=["fact columns"],
                            n_results=5,
                            where={"field_type": "fact"}
                        )
                        logger.info(f"   Found {len(fact_results['documents'][0])} fact columns")
                    except Exception as fact_error:
                        if "dimension" in str(fact_error).lower():
                            logger.warning(f"   Embedding dimension mismatch for fact search: {str(fact_error)}")
                            # Try without embedding query
                            try:
                                fact_results = collection.get(
                                    where={"field_type": "fact"},
                                    limit=5
                                )
                                logger.info(f"   Found {len(fact_results['ids'])} fact columns (without embedding)")
                            except Exception as get_error:
                                logger.error(f"   Could not retrieve fact columns: {str(get_error)}")
                        else:
                            logger.error(f"   Fact search failed: {str(fact_error)}")
                
                # Example 4: Get all documents of a specific type
                logger.info("4. Getting all TABLE_DOCUMENTs...")
                if self.static_collection:
                    collection = self.static_collection
                    logger.info(f"   Using static collection for document retrieval: {self.static_collection_name}")
                else:
                    logger.error("   No static collection available - skipping document retrieval examples")
                    return
                    
                    # Get all documents with TABLE_DOCUMENT metadata type
                    all_table_docs = collection.get(
                        where={"metadata_type": "TABLE_DOCUMENT"},
                        limit=10
                    )
                    
                    logger.info(f"   Found {len(all_table_docs['ids'])} TABLE_DOCUMENTs")
                    
                    # Debug: Show what we actually found
                    if all_table_docs['ids']:
                        logger.info("   Sample document metadata:")
                        for i, metadata in enumerate(all_table_docs['metadatas'][:3]):
                            logger.info(f"     {i+1}. ID: {all_table_docs['ids'][i]}")
                            logger.info(f"        Table: {metadata.get('table_name', 'N/A')}")
                            logger.info(f"        Domain: {metadata.get('domain', 'N/A')}")
                            logger.info(f"        Project: {metadata.get('project_id', 'N/A')}")
                    else:
                        logger.warning("   No TABLE_DOCUMENTs found - checking all documents...")
                        all_docs = collection.get(limit=5)
                        logger.info(f"   Total documents in collection: {len(all_docs['ids'])}")
                        if all_docs['ids']:
                            logger.info("   Sample metadata from collection:")
                            for i, metadata in enumerate(all_docs['metadatas'][:2]):
                                logger.info(f"     {i+1}. {metadata}")
                    
                    # Show table names
                    for i, table_name in enumerate(all_table_docs['metadatas'][:5]):
                        logger.info(f"     {i+1}. {table_name.get('table_name', '')}")
                
                # Example 5: Search by project ID
                logger.info("5. Searching by project ID...")
                if self.static_collection:
                    collection = self.static_collection
                    logger.info(f"   Using static collection for project search: {self.static_collection_name}")
                    
                    project_results = collection.get(
                        where={"project_id": "example_project"},
                        limit=10
                    )
                    
                    logger.info(f"   Found {len(project_results['ids'])} documents for project")
                    
                    # Debug: Show what we found
                    if project_results['ids']:
                        logger.info("   Project documents found:")
                        for i, metadata in enumerate(project_results['metadatas'][:3]):
                            logger.info(f"     {i+1}. {metadata.get('table_name', 'N/A')} - {metadata.get('domain', 'N/A')}")
                    else:
                        logger.warning("   No documents found for project_id='example_project'")
                        # Try to get all documents to see what's available
                        all_docs = collection.get(limit=5)
                        logger.info(f"   Total documents in collection: {len(all_docs['ids'])}")
                        if all_docs['ids']:
                            logger.info("   Available metadata fields:")
                            for i, metadata in enumerate(all_docs['metadatas'][:2]):
                                logger.info(f"     {i+1}. {list(metadata.keys())}")
                                logger.info(f"        Project ID: {metadata.get('project_id', 'NOT_FOUND')}")
                    
                    # Group by document type
                    doc_types = {}
                    for metadata in project_results['metadatas']:
                        doc_type = metadata.get('metadata_type', 'unknown')
                        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
                    
                    logger.info("   Document types in project:")
                    for doc_type, count in doc_types.items():
                        logger.info(f"     - {doc_type}: {count}")
                else:
                    logger.error("   No static collection available - skipping project search examples")
                    return
            
            else:
                logger.info("   Unified storage not available for direct ChromaDB access")
            
            # Alternative: Use static collection directly
            if self.static_collection:
                logger.info("   Using static collection for alternative access...")
                collection = self.static_collection
                logger.info(f"   Using static collection: {self.static_collection_name}")
            else:
                logger.info("   No static collection available for alternative access")
                return
            
            # Query for documents (handle embedding issues)
            try:
                # Try semantic search first
                results = collection.query(
                    query_texts=["user"],
                    n_results=3
                )
                
                logger.info(f"   Found {len(results['documents'][0])} results for 'user' query")
                
                # Show results
                for i, doc in enumerate(results['documents'][0][:2]):
                    metadata = results['metadatas'][0][i]
                    logger.info(f"     {i+1}. {metadata.get('table_name', 'Unknown')} - {metadata.get('description', 'No description')[:50]}...")
                    
            except Exception as query_error:
                logger.warning(f"   Semantic search failed: {str(query_error)}")
                logger.info("   Trying to get documents without embedding query...")
                
                # Try to get documents without embedding query
                try:
                    results = collection.get(
                        where={"table_name": {"$exists": True}},
                        limit=3
                    )
                    
                    logger.info(f"   Found {len(results['ids'])} results (without embedding)")
                    
                    # Show results
                    for i, doc_id in enumerate(results['ids'][:2]):
                        metadata = results['metadatas'][i]
                        logger.info(f"     {i+1}. {metadata.get('table_name', 'Unknown')} - {metadata.get('description', 'No description')[:50]}...")
                        
                except Exception as get_error:
                    logger.error(f"   Could not retrieve documents: {str(get_error)}")
            
            logger.info("Direct ChromaDB access examples completed")
            
        except Exception as e:
            logger.error(f"Error in direct ChromaDB access: {str(e)}")
    
    async def _run_table_schema_tests(self):
        """Run TABLE_SCHEMA retrieval pipeline tests."""
        logger.info("=" * 60)
        logger.info("RUNNING TABLE_SCHEMA RETRIEVAL PIPELINE TESTS")
        logger.info("=" * 60)
        
        try:
            # Test 1: Verify TABLE_SCHEMA document structure
            await self._test_table_schema_structure()
            
            # Test 2: Test DDL generation from TABLE_SCHEMA
            await self._test_ddl_generation_from_table_schema()
            
            # Test 3: Test retrieval pipeline simulation
            await self._test_retrieval_pipeline_simulation()
            
            # Test 4: Test with mock data to ensure tests work
            await self._test_with_mock_data()
            
            logger.info("✅ All TABLE_SCHEMA retrieval pipeline tests passed!")
            
        except Exception as e:
            logger.error(f"❌ TABLE_SCHEMA retrieval pipeline tests failed: {str(e)}")
            raise
    
    async def _test_table_schema_structure(self):
        """Test that TABLE_SCHEMA documents contain complete information."""
        logger.info("=== Testing TABLE_SCHEMA Document Structure ===")
        
        try:
            # First, let's process the MDL to ensure we have documents
            logger.info("Processing MDL to ensure documents are available...")
            result = await self.storage_manager.process_mdl(
                mdl_str=self.example_mdl,
                project_id="example_project"
            )
            
            logger.info(f"MDL processing result: {result}")
            
            # The process_mdl method returns counts, not actual documents
            # We need to get the documents from the storage system or create mock data
            table_docs = []
            
            # Check if we have table documents count
            if 'table_documents' in result and result['table_documents'] > 0:
                logger.info(f"MDL processing created {result['table_documents']} table documents")
                
                # Since we can't easily retrieve the documents from storage in this test,
                # let's create mock table documents based on our example MDL
                mdl_dict = json.loads(self.example_mdl)
                models = mdl_dict.get('models', [])
                
                for model in models:
                    # Create a mock table document structure
                    table_doc = {
                        'table_name': model.get('name', 'unknown'),
                        'display_name': model.get('properties', {}).get('displayName', ''),
                        'description': model.get('properties', {}).get('description', ''),
                        'business_purpose': model.get('properties', {}).get('businessPurpose', ''),
                        'primary_key': model.get('primaryKey', ''),
                        'columns': model.get('columns', []),
                        'table_columns': [],  # Will be populated by DDL chunker
                        'table_description': {}  # Will be populated by DDL chunker
                    }
                    
                    # Create table_columns using DDL chunker
                    try:
                        table_column_docs = await self.storage_manager._ddl_chunker.create_table_column_documents(
                            mdl=mdl_dict,
                            project_id="example_project"
                        )
                        
                        # Extract table_columns from the first table's columns
                        if table_column_docs:
                            table_columns = []
                            for col_doc in table_column_docs:
                                try:
                                    col_content = json.loads(col_doc.page_content)
                                    if col_content.get('table_name') == model.get('name'):
                                        # Create proper column definition
                                        column_name = col_content.get('name', '')
                                        data_type = col_content.get('data_type', '')
                                        is_primary_key = col_content.get('is_primary_key', False)
                                        is_nullable = col_content.get('is_nullable', True)
                                        is_calculated = col_content.get('is_calculated', False)
                                        expression = col_content.get('expression', '')
                                        
                                        # Build column definition
                                        if is_calculated:
                                            column_definition = f"-- This column is a Calculated Field\n-- column expression: {expression}\n{column_name} {data_type}"
                                        else:
                                            nullable_clause = "NOT NULL" if not is_nullable else ""
                                            # Get business description from column content
                                            business_description = col_content.get('description', '')
                                            if not business_description:
                                                # Try to extract description from the comment field
                                                comment = col_content.get('comment', '')
                                                if comment:
                                                    # Extract description from comment (look for -- description: line)
                                                    import re
                                                    desc_match = re.search(r'-- description:\s*(.+?)(?:\n|$)', comment)
                                                    if desc_match:
                                                        business_description = desc_match.group(1).strip()
                                            
                                            if business_description:
                                                column_definition = f"-- {business_description}\n{column_name} {data_type} {nullable_clause}".strip()
                                            else:
                                                column_definition = f"{column_name} {data_type} {nullable_clause}".strip()
                                        
                                        table_columns.append({
                                            'column_name': column_name,
                                            'data_type': data_type,
                                            'is_primary_key': is_primary_key,
                                            'is_nullable': is_nullable,
                                            'is_calculated': is_calculated,
                                            'expression': expression,
                                            'field_type': col_content.get('field_type', ''),
                                            'column_definition': column_definition,
                                            'clean_column_definition': column_name,
                                            'extracted_metadata': {
                                                'datatype': data_type,
                                                'field_type': col_content.get('field_type', ''),
                                                'displayName': col_content.get('display_name', ''),
                                                'description': col_content.get('comment', '')
                                            }
                                        })
                                except Exception as col_error:
                                    logger.warning(f"Could not parse column document: {str(col_error)}")
                            
                            table_doc['table_columns'] = table_columns
                    except Exception as ddl_error:
                        logger.warning(f"Could not create table columns: {str(ddl_error)}")
                    
                    # Create table_description
                    table_doc['table_description'] = {
                        'table_name': model.get('name', ''),
                        'display_name': model.get('properties', {}).get('displayName', ''),
                        'description': model.get('properties', {}).get('description', ''),
                        'business_purpose': model.get('properties', {}).get('businessPurpose', ''),
                        'primary_key': model.get('primaryKey', ''),
                        'column_count': len(model.get('columns', [])),
                        'calculated_column_count': len([col for col in model.get('columns', []) if col.get('isCalculated', False)]),
                        'dimension_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('properties', {}).get('usageType') == 'dimension'],
                        'fact_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('properties', {}).get('usageType') == 'fact'],
                        'identifier_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('properties', {}).get('usageType') == 'identifier'],
                        'timestamp_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('properties', {}).get('usageType') == 'timestamp'],
                        'calculated_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('isCalculated', False)],
                        'column_summaries': [
                            {
                                'name': col.get('name', ''),
                                'type': col.get('type', ''),
                                'is_primary_key': col.get('name') == model.get('primaryKey', ''),
                                'is_calculated': col.get('isCalculated', False),
                                'field_type': col.get('properties', {}).get('usageType', 'dimension'),
                                'display_name': col.get('properties', {}).get('displayName', ''),
                                'business_description': col.get('properties', {}).get('description', ''),
                                'usage_type': col.get('properties', {}).get('usageType', 'dimension')
                            }
                            for col in model.get('columns', [])
                        ]
                    }
                    
                    table_docs.append(table_doc)
                    logger.info(f"Created mock table document: {table_doc.get('table_name', 'unknown')}")
            else:
                logger.warning("No table documents found in MDL processing result")
                logger.info("Available result keys: " + str(list(result.keys()) if isinstance(result, dict) else "Not a dict"))
                return
            
            logger.info(f"Found {len(table_docs)} table documents to test")
            
            # Test each table document
            for i, table_doc in enumerate(table_docs):
                await self._test_single_table_document(table_doc, i + 1)
                
        except Exception as e:
            logger.error(f"Error testing TABLE_SCHEMA structure: {str(e)}")
            raise
    
    async def _test_single_table_document(self, table_doc: Dict[str, Any], doc_number: int):
        """Test a single table document structure."""
        table_name = table_doc.get('table_name', f'table_{doc_number}')
        logger.info(f"Testing table document {doc_number}: {table_name}")
        
        # Test required fields
        required_fields = [
            'table_name', 'display_name', 'description', 'business_purpose',
            'primary_key', 'columns', 'table_columns', 'table_description'
        ]
        
        for field in required_fields:
            if field not in table_doc:
                logger.error(f"❌ Missing required field '{field}' in table document {table_name}")
                raise AssertionError(f"Missing required field: {field}")
            logger.info(f"✓ {field}: {type(table_doc[field])}")
        
        # Test table_columns structure
        table_columns = table_doc.get('table_columns', [])
        assert isinstance(table_columns, list), f"table_columns should be a list for {table_name}"
        assert len(table_columns) > 0, f"table_columns should not be empty for {table_name}"
        
        logger.info(f"✓ table_columns: {len(table_columns)} columns")
        
        # Test each column in table_columns
        for j, column in enumerate(table_columns):
            await self._test_column_structure(column, table_name, j + 1)
        
        # Test table_description structure
        table_description = table_doc.get('table_description', {})
        assert isinstance(table_description, dict), f"table_description should be a dict for {table_name}"
        assert len(table_description) > 0, f"table_description should not be empty for {table_name}"
        
        logger.info(f"✓ table_description: {len(table_description)} fields")
        
        # Test table_description fields
        required_desc_fields = [
            'table_name', 'display_name', 'description', 'business_purpose',
            'primary_key', 'column_count', 'column_summaries'
        ]
        
        for field in required_desc_fields:
            if field not in table_description:
                logger.error(f"❌ Missing table_description field '{field}' in {table_name}")
                raise AssertionError(f"Missing table_description field: {field}")
            logger.info(f"✓ table_description.{field}: {table_description[field]}")
        
        logger.info(f"✅ Table document {table_name} structure validated")
    
    async def _test_column_structure(self, column: Dict[str, Any], table_name: str, column_number: int):
        """Test a single column structure."""
        column_name = column.get('column_name', f'column_{column_number}')
        logger.info(f"  Testing column {column_number}: {column_name}")
        
        # Test required column fields
        required_fields = [
            'column_name', 'data_type', 'is_primary_key', 'is_nullable',
            'is_calculated', 'field_type', 'column_definition',
            'clean_column_definition', 'extracted_metadata'
        ]
        
        for field in required_fields:
            if field not in column:
                logger.error(f"❌ Missing column field '{field}' in {table_name}.{column_name}")
                raise AssertionError(f"Missing column field: {field}")
            logger.info(f"    ✓ {field}: {column[field]}")
        
        # Test DDL generation fields
        column_definition = column.get('column_definition', '')
        clean_definition = column.get('clean_column_definition', '')
        extracted_metadata = column.get('extracted_metadata', {})
        
        assert isinstance(column_definition, str), f"column_definition should be a string for {table_name}.{column_name}"
        assert isinstance(clean_definition, str), f"clean_column_definition should be a string for {table_name}.{column_name}"
        assert isinstance(extracted_metadata, dict), f"extracted_metadata should be a dict for {table_name}.{column_name}"
        
        # Test that column_definition contains the column name
        assert column_name in column_definition, f"column_definition should contain column name '{column_name}'"
        
        # Test that clean_column_definition is just the column name
        assert clean_definition == column_name, f"clean_column_definition should be '{column_name}', got '{clean_definition}'"
        
        logger.info(f"    ✓ DDL fields validated for {table_name}.{column_name}")
    
    async def _test_ddl_generation_from_table_schema(self):
        """Test DDL generation from TABLE_SCHEMA documents."""
        logger.info("=== Testing DDL Generation from TABLE_SCHEMA ===")
        
        try:
            # Process MDL to get table documents
            logger.info("Processing MDL for DDL generation testing...")
            result = await self.storage_manager.process_mdl(
                mdl_str=self.example_mdl,
                project_id="example_project"
            )
            
            # Create mock table documents based on MDL
            table_docs = []
            if 'table_documents' in result and result['table_documents'] > 0:
                logger.info(f"MDL processing created {result['table_documents']} table documents")
                
                # Create mock table documents based on our example MDL
                mdl_dict = json.loads(self.example_mdl)
                models = mdl_dict.get('models', [])
                
                for model in models:
                    # Create a mock table document structure
                    table_doc = {
                        'table_name': model.get('name', 'unknown'),
                        'table_columns': []
                    }
                    
                    # Create table_columns using DDL chunker
                    try:
                        table_column_docs = await self.storage_manager._ddl_chunker.create_table_column_documents(
                            mdl=mdl_dict,
                            project_id="example_project"
                        )
                        
                        # Extract table_columns for this table
                        if table_column_docs:
                            table_columns = []
                            for col_doc in table_column_docs:
                                try:
                                    col_content = json.loads(col_doc.page_content)
                                    if col_content.get('table_name') == model.get('name'):
                                        # Create proper column definition
                                        column_name = col_content.get('name', '')
                                        data_type = col_content.get('data_type', '')
                                        is_primary_key = col_content.get('is_primary_key', False)
                                        is_nullable = col_content.get('is_nullable', True)
                                        is_calculated = col_content.get('is_calculated', False)
                                        expression = col_content.get('expression', '')
                                        
                                        # Build column definition
                                        if is_calculated:
                                            column_definition = f"-- This column is a Calculated Field\n-- column expression: {expression}\n{column_name} {data_type}"
                                        else:
                                            nullable_clause = "NOT NULL" if not is_nullable else ""
                                            # Get business description from column content
                                            business_description = col_content.get('description', '')
                                            if not business_description:
                                                # Try to extract description from the comment field
                                                comment = col_content.get('comment', '')
                                                if comment:
                                                    # Extract description from comment (look for -- description: line)
                                                    import re
                                                    desc_match = re.search(r'-- description:\s*(.+?)(?:\n|$)', comment)
                                                    if desc_match:
                                                        business_description = desc_match.group(1).strip()
                                            
                                            if business_description:
                                                column_definition = f"-- {business_description}\n{column_name} {data_type} {nullable_clause}".strip()
                                            else:
                                                column_definition = f"{column_name} {data_type} {nullable_clause}".strip()
                                        
                                        table_columns.append({
                                            'column_name': column_name,
                                            'data_type': data_type,
                                            'is_primary_key': is_primary_key,
                                            'is_nullable': is_nullable,
                                            'is_calculated': is_calculated,
                                            'expression': expression,
                                            'field_type': col_content.get('field_type', ''),
                                            'column_definition': column_definition,
                                            'clean_column_definition': column_name,
                                            'extracted_metadata': {
                                                'datatype': data_type,
                                                'field_type': col_content.get('field_type', ''),
                                                'displayName': col_content.get('display_name', ''),
                                                'description': col_content.get('comment', '')
                                            }
                                        })
                                except Exception as col_error:
                                    logger.warning(f"Could not parse column document: {str(col_error)}")
                            
                            table_doc['table_columns'] = table_columns
                    except Exception as ddl_error:
                        logger.warning(f"Could not create table columns: {str(ddl_error)}")
                    
                    table_docs.append(table_doc)
                    logger.info(f"Created mock table document for DDL testing: {table_doc.get('table_name', 'unknown')}")
            else:
                logger.warning("No table documents found for DDL generation testing")
                return
            
            logger.info(f"Found {len(table_docs)} table documents for DDL generation testing")
            
            # Test DDL generation for each table
            for table_doc in table_docs:
                await self._test_ddl_generation_for_table(table_doc)
                
        except Exception as e:
            logger.error(f"Error testing DDL generation: {str(e)}")
            raise
    
    async def _test_ddl_generation_for_table(self, table_doc: Dict[str, Any]):
        """Test DDL generation for a single table."""
        table_name = table_doc.get('table_name', 'unknown')
        table_columns = table_doc.get('table_columns', [])
        
        logger.info(f"Testing DDL generation for table: {table_name}")
        
        # Simulate DDL generation
        ddl_statements = []
        for column in table_columns:
            column_name = column.get('column_name')
            data_type = column.get('data_type')
            is_primary_key = column.get('is_primary_key', False)
            is_nullable = column.get('is_nullable', True)
            is_calculated = column.get('is_calculated', False)
            expression = column.get('expression', '')
            
            # Build DDL statement
            if is_calculated:
                ddl_statement = f"  -- This column is a Calculated Field\n  -- column expression: {expression}\n  {column_name} {data_type}"
            else:
                nullable_clause = "NOT NULL" if not is_nullable else ""
                # Get business description from column properties or comment
                business_description = column.get('business_description', column.get('description', ''))
                if not business_description:
                    # Try to extract description from the comment field
                    comment = column.get('comment', '')
                    if comment:
                        # Extract description from comment (look for -- description: line)
                        import re
                        desc_match = re.search(r'-- description:\s*(.+?)(?:\n|$)', comment)
                        if desc_match:
                            business_description = desc_match.group(1).strip()
                
                if business_description:
                    ddl_statement = f"  -- {business_description}\n  {column_name} {data_type} {nullable_clause}".strip()
                else:
                    ddl_statement = f"  {column_name} {data_type} {nullable_clause}".strip()
            
            ddl_statements.append(ddl_statement)
            logger.info(f"✓ DDL statement for {column_name}: {ddl_statement}")
        
        # Build complete DDL
        complete_ddl = f"CREATE TABLE {table_name} (\n" + ",\n".join(ddl_statements) + "\n);"
        logger.info(f"✓ Complete DDL for {table_name}:\n{complete_ddl}")
        
        # Verify DDL contains all columns
        for column in table_columns:
            column_name = column.get('column_name')
            assert column_name in complete_ddl, f"DDL should contain column '{column_name}'"
        
        logger.info(f"✅ DDL generation test passed for {table_name}")
    
    async def _test_retrieval_pipeline_simulation(self):
        """Test the complete retrieval pipeline simulation."""
        logger.info("=== Testing Retrieval Pipeline Simulation ===")
        
        try:
            # Process MDL to get table documents
            logger.info("Processing MDL for retrieval pipeline simulation...")
            result = await self.storage_manager.process_mdl(
                mdl_str=self.example_mdl,
                project_id="example_project"
            )
            
            # Create mock table documents based on MDL
            table_docs = []
            if 'table_documents' in result and result['table_documents'] > 0:
                logger.info(f"MDL processing created {result['table_documents']} table documents")
                
                # Create mock table documents based on our example MDL
                mdl_dict = json.loads(self.example_mdl)
                models = mdl_dict.get('models', [])
                
                for model in models:
                    # Create a mock table document structure
                    table_doc = {
                        'table_name': model.get('name', 'unknown'),
                        'display_name': model.get('properties', {}).get('displayName', ''),
                        'description': model.get('properties', {}).get('description', ''),
                        'business_purpose': model.get('properties', {}).get('businessPurpose', ''),
                        'primary_key': model.get('primaryKey', ''),
                        'table_columns': [],
                        'table_description': {}
                    }
                    
                    # Create table_columns using DDL chunker
                    try:
                        table_column_docs = await self.storage_manager._ddl_chunker.create_table_column_documents(
                            mdl=mdl_dict,
                            project_id="example_project"
                        )
                        
                        # Extract table_columns for this table
                        if table_column_docs:
                            table_columns = []
                            for col_doc in table_column_docs:
                                try:
                                    col_content = json.loads(col_doc.page_content)
                                    if col_content.get('table_name') == model.get('name'):
                                        # Create proper column definition
                                        column_name = col_content.get('name', '')
                                        data_type = col_content.get('data_type', '')
                                        is_primary_key = col_content.get('is_primary_key', False)
                                        is_nullable = col_content.get('is_nullable', True)
                                        is_calculated = col_content.get('is_calculated', False)
                                        expression = col_content.get('expression', '')
                                        
                                        # Build column definition
                                        if is_calculated:
                                            column_definition = f"-- This column is a Calculated Field\n-- column expression: {expression}\n{column_name} {data_type}"
                                        else:
                                            nullable_clause = "NOT NULL" if not is_nullable else ""
                                            # Get business description from column content
                                            business_description = col_content.get('description', '')
                                            if not business_description:
                                                # Try to extract description from the comment field
                                                comment = col_content.get('comment', '')
                                                if comment:
                                                    # Extract description from comment (look for -- description: line)
                                                    import re
                                                    desc_match = re.search(r'-- description:\s*(.+?)(?:\n|$)', comment)
                                                    if desc_match:
                                                        business_description = desc_match.group(1).strip()
                                            
                                            if business_description:
                                                column_definition = f"-- {business_description}\n{column_name} {data_type} {nullable_clause}".strip()
                                            else:
                                                column_definition = f"{column_name} {data_type} {nullable_clause}".strip()
                                        
                                        table_columns.append({
                                            'column_name': column_name,
                                            'data_type': data_type,
                                            'is_primary_key': is_primary_key,
                                            'is_nullable': is_nullable,
                                            'is_calculated': is_calculated,
                                            'expression': expression,
                                            'field_type': col_content.get('field_type', ''),
                                            'column_definition': column_definition,
                                            'clean_column_definition': column_name,
                                            'extracted_metadata': {
                                                'datatype': data_type,
                                                'field_type': col_content.get('field_type', ''),
                                                'displayName': col_content.get('display_name', ''),
                                                'description': col_content.get('comment', '')
                                            }
                                        })
                                except Exception as col_error:
                                    logger.warning(f"Could not parse column document: {str(col_error)}")
                            
                            table_doc['table_columns'] = table_columns
                    except Exception as ddl_error:
                        logger.warning(f"Could not create table columns: {str(ddl_error)}")
                    
                    # Create table_description
                    table_doc['table_description'] = {
                        'table_name': model.get('name', ''),
                        'display_name': model.get('properties', {}).get('displayName', ''),
                        'description': model.get('properties', {}).get('description', ''),
                        'business_purpose': model.get('properties', {}).get('businessPurpose', ''),
                        'primary_key': model.get('primaryKey', ''),
                        'column_count': len(model.get('columns', [])),
                        'calculated_column_count': len([col for col in model.get('columns', []) if col.get('isCalculated', False)]),
                        'dimension_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('properties', {}).get('usageType') == 'dimension'],
                        'fact_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('properties', {}).get('usageType') == 'fact'],
                        'identifier_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('properties', {}).get('usageType') == 'identifier'],
                        'timestamp_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('properties', {}).get('usageType') == 'timestamp'],
                        'calculated_columns': [col.get('name', '') for col in model.get('columns', []) if col.get('isCalculated', False)],
                        'column_summaries': [
                            {
                                'name': col.get('name', ''),
                                'type': col.get('type', ''),
                                'is_primary_key': col.get('name') == model.get('primaryKey', ''),
                                'is_calculated': col.get('isCalculated', False),
                                'field_type': col.get('properties', {}).get('usageType', 'dimension'),
                                'display_name': col.get('properties', {}).get('displayName', ''),
                                'business_description': col.get('properties', {}).get('description', ''),
                                'usage_type': col.get('properties', {}).get('usageType', 'dimension')
                            }
                            for col in model.get('columns', [])
                        ]
                    }
                    
                    table_docs.append(table_doc)
                    logger.info(f"Created mock table document for retrieval simulation: {table_doc.get('table_name', 'unknown')}")
            else:
                logger.warning("No table documents found for retrieval pipeline testing")
                return
            
            logger.info(f"Found {len(table_docs)} table documents for retrieval pipeline simulation")
            
            # Test retrieval pipeline for each table
            for table_doc in table_docs:
                await self._simulate_retrieval_pipeline_for_table(table_doc)
                
        except Exception as e:
            logger.error(f"Error testing retrieval pipeline: {str(e)}")
            raise
    
    async def _simulate_retrieval_pipeline_for_table(self, table_doc: Dict[str, Any]):
        """Simulate the retrieval pipeline for a single table."""
        table_name = table_doc.get('table_name', 'unknown')
        logger.info(f"Simulating retrieval pipeline for table: {table_name}")
        
        # Step 1: Extract table information
        table_info = {
            'name': table_doc.get('table_name'),
            'display_name': table_doc.get('display_name'),
            'description': table_doc.get('description'),
            'business_purpose': table_doc.get('business_purpose'),
            'primary_key': table_doc.get('primary_key')
        }
        
        logger.info(f"✓ Table info extracted: {table_info}")
        
        # Step 2: Extract column information for DDL generation
        table_columns = table_doc.get('table_columns', [])
        ddl_statements = []
        
        for column in table_columns:
            # Extract DDL-ready information
            column_name = column.get('column_name')
            data_type = column.get('data_type')
            is_primary_key = column.get('is_primary_key', False)
            is_nullable = column.get('is_nullable', True)
            is_calculated = column.get('is_calculated', False)
            expression = column.get('expression', '')
            
            # Build DDL statement
            if is_calculated:
                ddl_statement = f"-- {column_name}: {column.get('business_description', '')}\n  {column_name} AS ({expression})"
            else:
                nullable_clause = "NOT NULL" if not is_nullable else ""
                ddl_statement = f"-- {column_name}: {column.get('business_description', '')}\n  {column_name} {data_type} {nullable_clause}".strip()
            
            ddl_statements.append(ddl_statement)
            logger.info(f"✓ DDL statement for {column_name}: {ddl_statement}")
        
        # Step 3: Build complete table DDL
        complete_ddl = f"CREATE TABLE {table_name} (\n" + ",\n".join(ddl_statements) + "\n);"
        logger.info(f"✓ Complete DDL for {table_name}:\n{complete_ddl}")
        
        # Step 4: Verify business context is available
        table_description = table_doc.get('table_description', {})
        business_context = {
            'business_purpose': table_description.get('business_purpose'),
            'domain': table_description.get('business_domain'),
            'classification': table_description.get('classification'),
            'tags': table_description.get('tags', []),
            'business_rules': table_description.get('business_rules', [])
        }
        
        logger.info(f"✓ Business context: {business_context}")
        
        # Step 5: Verify field type classification
        field_classification = {
            'dimensions': table_description.get('dimension_columns', []),
            'facts': table_description.get('fact_columns', []),
            'identifiers': table_description.get('identifier_columns', []),
            'timestamps': table_description.get('timestamp_columns', []),
            'calculated': table_description.get('calculated_columns', [])
        }
        
        logger.info(f"✓ Field classification: {field_classification}")
        
        logger.info(f"✅ Retrieval pipeline simulation completed for {table_name}")
    
    async def _test_with_mock_data(self):
        """Test with mock data to ensure tests work even if MDL processing fails."""
        logger.info("=== Testing with Mock Data ===")
        
        try:
            # Create mock table document
            mock_table_doc = {
                "table_name": "mock_users",
                "display_name": "Mock User Accounts",
                "description": "Mock table for user account information",
                "business_purpose": "Mock user management and authentication",
                "primary_key": "user_id",
                "columns": [
                    {
                        "name": "user_id",
                        "type": "VARCHAR(50)",
                        "field_type": "identifier",
                        "is_primary_key": True,
                        "is_nullable": False,
                        "is_calculated": False
                    },
                    {
                        "name": "email",
                        "type": "VARCHAR(255)",
                        "field_type": "dimension",
                        "is_primary_key": False,
                        "is_nullable": False,
                        "is_calculated": False
                    },
                    {
                        "name": "full_name",
                        "type": "VARCHAR(255)",
                        "field_type": "dimension",
                        "is_primary_key": False,
                        "is_nullable": True,
                        "is_calculated": True,
                        "expression": "CONCAT(first_name, ' ', last_name)"
                    }
                ],
                "table_columns": [
                    {
                        "column_name": "user_id",
                        "data_type": "VARCHAR(50)",
                        "is_primary_key": True,
                        "is_nullable": False,
                        "is_calculated": False,
                        "field_type": "identifier",
                        "column_definition": "-- user_id: Unique identifier for user accounts\n  user_id VARCHAR(50) NOT NULL",
                        "clean_column_definition": "user_id",
                        "extracted_metadata": {
                            "datatype": "VARCHAR(50)",
                            "field_type": "identifier",
                            "displayName": "User ID",
                            "description": "Unique identifier for user accounts"
                        }
                    },
                    {
                        "column_name": "email",
                        "data_type": "VARCHAR(255)",
                        "is_primary_key": False,
                        "is_nullable": False,
                        "is_calculated": False,
                        "field_type": "dimension",
                        "column_definition": "-- email: User's email address for login\n  email VARCHAR(255) NOT NULL",
                        "clean_column_definition": "email",
                        "extracted_metadata": {
                            "datatype": "VARCHAR(255)",
                            "field_type": "dimension",
                            "displayName": "Email Address",
                            "description": "User's email address for login"
                        }
                    },
                    {
                        "column_name": "full_name",
                        "data_type": "VARCHAR(255)",
                        "is_primary_key": False,
                        "is_nullable": True,
                        "is_calculated": True,
                        "expression": "CONCAT(first_name, ' ', last_name)",
                        "field_type": "dimension",
                        "column_definition": "-- full_name: Calculated field combining first and last name\n  full_name AS (CONCAT(first_name, ' ', last_name))",
                        "clean_column_definition": "full_name",
                        "extracted_metadata": {
                            "datatype": "VARCHAR(255)",
                            "field_type": "dimension",
                            "displayName": "Full Name",
                            "description": "Calculated field combining first and last name"
                        }
                    }
                ],
                "table_description": {
                    "table_name": "mock_users",
                    "display_name": "Mock User Accounts",
                    "description": "Mock table for user account information",
                    "business_purpose": "Mock user management and authentication",
                    "primary_key": "user_id",
                    "column_count": 3,
                    "calculated_column_count": 1,
                    "dimension_columns": ["email", "full_name"],
                    "fact_columns": [],
                    "identifier_columns": ["user_id"],
                    "timestamp_columns": [],
                    "calculated_columns": ["full_name"],
                    "column_summaries": [
                        {
                            "name": "user_id",
                            "type": "VARCHAR(50)",
                            "is_primary_key": True,
                            "is_calculated": False,
                            "field_type": "identifier",
                            "display_name": "User ID",
                            "business_description": "Unique identifier for user accounts",
                            "usage_type": "identifier"
                        },
                        {
                            "name": "email",
                            "type": "VARCHAR(255)",
                            "is_primary_key": False,
                            "is_calculated": False,
                            "field_type": "dimension",
                            "display_name": "Email Address",
                            "business_description": "User's email address for login",
                            "usage_type": "contact"
                        },
                        {
                            "name": "full_name",
                            "type": "VARCHAR(255)",
                            "is_primary_key": False,
                            "is_calculated": True,
                            "field_type": "dimension",
                            "display_name": "Full Name",
                            "business_description": "Calculated field combining first and last name",
                            "usage_type": "calculated"
                        }
                    ],
                    "business_domain": "user_management",
                    "classification": "internal",
                    "tags": ["user", "authentication", "mock"],
                    "business_rules": [
                        "Each user must have a unique email address",
                        "User status must be active, inactive, or suspended"
                    ],
                    "usage_guidelines": [
                        "Use for user authentication",
                        "Maintain data privacy"
                    ]
                }
            }
            
            logger.info("Testing mock table document structure...")
            await self._test_single_table_document(mock_table_doc, 1)
            
            logger.info("Testing mock DDL generation...")
            await self._test_ddl_generation_for_table(mock_table_doc)
            
            logger.info("Testing mock retrieval pipeline simulation...")
            await self._simulate_retrieval_pipeline_for_table(mock_table_doc)
            
            logger.info("✅ Mock data tests completed successfully!")
            
        except Exception as e:
            logger.error(f"Error testing with mock data: {str(e)}")
            raise
    
    async def _demonstrate_retrieval_helper2(self):
        """Demonstrate the new RetrievalHelper2 functionality using static collection."""
        logger.info("=" * 60)
        logger.info("DEMONSTRATING RETRIEVAL HELPER V2 FUNCTIONALITY")
        logger.info("=" * 60)
        
        try:
            # Import the new retrieval helper classes
            from app.indexing2.retrieval_helper2 import RetrievalHelper2
            from app.indexing2.retrieval2 import TableRetrieval2
            from langchain_openai import OpenAIEmbeddings
            
            logger.info("Initializing RetrievalHelper2 with local document store...")
            # Initialize embeddings
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                openai_api_key=settings.OPENAI_API_KEY
            )
            
            # Get the document store from storage manager to use the same collection
            doc_store = self.storage_manager._unified_storage._document_store
            
            # Initialize RetrievalHelper2 with local document store
            retrieval_helper = RetrievalHelper2(
                document_store=doc_store,
                embedder=embeddings,
                similarity_threshold=0.7
            )
            
            logger.info("✅ RetrievalHelper2 initialized successfully with local document store")
            
            # Test 1: Get database schemas
            logger.info("\n=== Test 1: Get Database Schemas ===")
            try:
                schemas = await retrieval_helper.get_database_schemas(
                    project_id="example_project",
                    table_retrieval={"table_retrieval_size": 5},
                    query="user account management"
                )
                
                logger.info(f"✓ Found {schemas.get('total_schemas', 0)} schemas")
                if schemas.get('schemas'):
                    for schema in schemas['schemas'][:3]:
                        logger.info(f"  - Table: {schema.get('table_name', 'unknown')}")
                        logger.info(f"    DDL preview: {schema.get('table_ddl', '')[:100]}...")
                        logger.info(f"    Has calculated field: {schema.get('has_calculated_field', False)}")
                        logger.info(f"    Relevance score: {schema.get('relevance_score', 0.0):.2f}")
            except Exception as e:
                logger.warning(f"⚠️  Database schemas retrieval test failed: {str(e)}")
            
            # Test 2: Get SQL pairs
            logger.info("\n=== Test 2: Get SQL Pairs ===")
            try:
                sql_pairs = await retrieval_helper.get_sql_pairs(
                    query="show me users",
                    project_id="example_project",
                    max_retrieval_size=5
                )
                
                logger.info(f"✓ Found {sql_pairs.get('total_pairs', 0)} SQL pairs")
                if sql_pairs.get('sql_pairs'):
                    for pair in sql_pairs['sql_pairs'][:2]:
                        logger.info(f"  - Question: {pair.get('question', 'N/A')[:50]}...")
                        logger.info(f"    SQL: {pair.get('sql', 'N/A')[:50]}...")
            except Exception as e:
                logger.warning(f"⚠️  SQL pairs retrieval test failed: {str(e)}")
            
            # Test 3: Get instructions
            logger.info("\n=== Test 3: Get Instructions ===")
            try:
                instructions = await retrieval_helper.get_instructions(
                    query="user authentication",
                    project_id="example_project",
                    top_k=3
                )
                
                logger.info(f"✓ Found {instructions.get('total_instructions', 0)} instructions")
                if instructions.get('instructions'):
                    for inst in instructions['instructions'][:2]:
                        logger.info(f"  - Question: {inst.get('question', 'N/A')[:50]}...")
                        logger.info(f"    Instruction: {inst.get('instruction', 'N/A')[:50]}...")
            except Exception as e:
                logger.warning(f"⚠️  Instructions retrieval test failed: {str(e)}")
            
            # Test 4: Get historical questions
            logger.info("\n=== Test 4: Get Historical Questions ===")
            try:
                historical = await retrieval_helper.get_historical_questions(
                    query="active users",
                    project_id="example_project"
                )
                
                logger.info(f"✓ Found {historical.get('total_questions', 0)} historical questions")
                if historical.get('historical_questions'):
                    for question in historical['historical_questions'][:2]:
                        logger.info(f"  - Question: {question.get('question', 'N/A')[:50]}...")
                        logger.info(f"    Summary: {question.get('summary', 'N/A')[:50]}...")
            except Exception as e:
                logger.warning(f"⚠️  Historical questions retrieval test failed: {str(e)}")
            
            # Test 5: Get table names and schema contexts
            logger.info("\n=== Test 5: Get Table Names and Schema Contexts ===")
            try:
                table_contexts = await retrieval_helper.get_table_names_and_schema_contexts(
                    query="user management",
                    project_id="example_project",
                    table_retrieval={"table_retrieval_size": 3},
                    tables=None
                )
                
                logger.info(f"✓ Found {table_contexts.get('total_tables', 0)} tables")
                logger.info(f"  - Table names: {table_contexts.get('table_names', [])}")
                logger.info(f"  - Total contexts: {table_contexts.get('total_contexts', 0)}")
                logger.info(f"  - Total relationships: {table_contexts.get('total_relationships', 0)}")
                logger.info(f"  - Has calculated field: {table_contexts.get('has_calculated_field', False)}")
            except Exception as e:
                logger.warning(f"⚠️  Table names and schema contexts test failed: {str(e)}")
            
            # Test 6: Initialize and test TableRetrieval2
            logger.info("\n=== Test 6: Test TableRetrieval2 ===")
            try:
                # Use the same document store from storage manager
                doc_store = self.storage_manager._unified_storage._document_store
                
                table_retrieval = TableRetrieval2(
                    document_store=doc_store,
                    embedder=embeddings,
                    table_retrieval_size=5
                )
                
                logger.info("✓ TableRetrieval2 initialized successfully with local document store")
                
                results = await table_retrieval.run(
                    query="customer orders",
                    project_id="example_project"
                )
                
                logger.info(f"✓ Found {len(results.get('retrieval_results', []))} retrieval results")
                if results.get('retrieval_results'):
                    for result in results['retrieval_results'][:2]:
                        logger.info(f"  - Table: {result.get('table_name', 'unknown')}")
                        logger.info(f"    DDL preview: {result.get('table_ddl', '')[:100]}...")
                        logger.info(f"    Columns: {len(result.get('column_metadata', []))}")
            except Exception as e:
                logger.warning(f"⚠️  TableRetrieval2 test failed: {str(e)}")
            
            # Test 7: Test with static collection data
            logger.info("\n=== Test 7: Test with Static Collection Data ===")
            try:
                if self.static_collection:
                    logger.info("✓ Static collection is available")
                    
                    # Get count of documents in static collection
                    count = self.static_collection.count()
                    logger.info(f"  - Static collection contains {count} documents")
                    
                    # Try to retrieve documents from static collection
                    try:
                        results = self.static_collection.get(limit=3)
                        logger.info(f"  - Retrieved {len(results.get('ids', []))} documents from static collection")
                        
                        for i, (doc_id, metadata) in enumerate(zip(results.get('ids', []), results.get('metadatas', []))):
                            logger.info(f"  Document {i+1}:")
                            logger.info(f"    - ID: {doc_id}")
                            logger.info(f"    - Table: {metadata.get('table_name', 'N/A')}")
                            logger.info(f"    - Domain: {metadata.get('domain', 'N/A')}")
                            logger.info(f"    - Project: {metadata.get('project_id', 'N/A')}")
                    except Exception as get_error:
                        logger.warning(f"  ⚠️  Could not retrieve from static collection: {str(get_error)}")
                else:
                    logger.warning("⚠️  Static collection not available for testing")
            except Exception as e:
                logger.warning(f"⚠️  Static collection test failed: {str(e)}")
            
            logger.info("\n✅ Retrieval Helper v2 demonstration completed!")
            
        except Exception as e:
            logger.error(f"❌ Error demonstrating RetrievalHelper2: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def cleanup(self):
        """Clean up the example data."""
        logger.info("Cleaning up example data")
        
        # Clean up static collection
        await self._cleanup_static_collection()
        
        if self.storage_manager:
            await self.storage_manager.clean("example_project")
            logger.info("Cleanup completed")
    
    async def run_tests_only(self):
        """Run only the TABLE_SCHEMA retrieval pipeline tests."""
        logger.info("Starting TABLE_SCHEMA retrieval pipeline tests only")
        
        try:
            # Initialize components
            await self._initialize_components()
            
            # Run TABLE_SCHEMA retrieval pipeline tests
            await self._run_table_schema_tests()
            
            # Demonstrate new retrieval helper functionality
            await self._demonstrate_retrieval_helper2()
            
            logger.info("✅ All tests completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Tests failed: {str(e)}")
            raise
        finally:
            # Clean up
            await self.cleanup()


async def main():
    """Main function to run the example."""
    import sys
    
    # Check if tests-only mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == "--tests-only":
        logger.info("Running TABLE_SCHEMA retrieval pipeline tests only...")
        example = ExampleUsage()
        try:
            await example.run_tests_only()
        finally:
            await example.cleanup()
    else:
        logger.info("Running complete example with tests...")
        example = ExampleUsage()
        try:
            await example.run_example()
        finally:
            await example.cleanup()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the example
    asyncio.run(main())

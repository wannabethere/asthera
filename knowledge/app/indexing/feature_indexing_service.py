"""
Feature Indexing Service
Indexes feature knowledge JSON files as natural language questions.
"""
import json
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

from app.indexing.storage.feature_storage import FeatureStorageService
from app.indexing.storage.file_storage import FileStorage
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class FeatureIndexingService:
    """Service for indexing feature knowledge JSON files."""
    
    def __init__(
        self,
        vector_store_type: str = "chroma",
        persistent_client=None,
        qdrant_client=None,
        embeddings_model: Optional[OpenAIEmbeddings] = None,
        llm: Optional[ChatOpenAI] = None,
        collection_prefix: str = "feature_store",
        preview_mode: bool = False,
        preview_output_dir: str = "indexing_preview"
    ):
        """
        Initialize the feature indexing service.
        
        Args:
            vector_store_type: "chroma" or "qdrant"
            persistent_client: ChromaDB persistent client (for chroma)
            qdrant_client: Qdrant client (for qdrant)
            embeddings_model: Embeddings model instance
            llm: LLM instance for question generation (optional)
            collection_prefix: Prefix for collection names
            preview_mode: If True, saves to files instead of indexing to database
            preview_output_dir: Directory for preview files
        """
        self.vector_store_type = vector_store_type
        self.collection_prefix = collection_prefix
        self.preview_mode = preview_mode
        settings = get_settings()
        
        # Initialize embeddings
        self.embeddings_model = embeddings_model or OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENAI_API_KEY
        )
        
        # Initialize LLM (optional, for question generation)
        self.llm = llm or (ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            openai_api_key=settings.OPENAI_API_KEY
        ) if not preview_mode else None)
        
        # Initialize storage service
        if not preview_mode:
            self.storage_service = FeatureStorageService(
                vector_store_type=vector_store_type,
                persistent_client=persistent_client,
                qdrant_client=qdrant_client,
                embeddings_model=self.embeddings_model,
                collection_prefix=collection_prefix
            )
        else:
            self.storage_service = None
            self.file_storage = FileStorage(output_dir=preview_output_dir)
        
        logger.info(f"FeatureIndexingService initialized with {vector_store_type}, preview_mode={preview_mode}")
    
    def _determine_feature_type(self, feature: Dict[str, Any], category: Dict[str, Any]) -> str:
        """
        Determine the feature type based on feature and category metadata.
        
        Args:
            feature: Feature definition
            category: Category definition
        
        Returns:
            Feature type (control, risk, impact, likelihood, evidence, effectiveness)
        """
        # Check category classification
        classification = category.get("classification", "").lower()
        
        # Map classification to feature type
        if "control" in classification or "safeguard" in classification.lower():
            return "control"
        elif "risk" in classification:
            return "risk"
        elif "impact" in classification:
            return "impact"
        elif "likelihood" in classification:
            return "likelihood"
        elif "evidence" in classification or "monitoring" in classification.lower():
            return "evidence"
        elif "effective" in classification:
            return "effectiveness"
        
        # Check feature name patterns
        name = feature.get("name", "").lower()
        if "control" in name or "safeguard" in name:
            return "control"
        elif "risk" in name:
            return "risk"
        elif "impact" in name:
            return "impact"
        elif "likelihood" in name:
            return "likelihood"
        elif "evidence" in name or "monitoring" in name or "agent" in name:
            return "evidence"
        elif "effective" in name:
            return "effectiveness"
        
        # Default based on category name
        category_name = category.get("name", "").lower()
        if "control" in category_name:
            return "control"
        elif "risk" in category_name:
            return "risk"
        elif "impact" in category_name:
            return "impact"
        elif "likelihood" in category_name:
            return "likelihood"
        elif "evidence" in category_name or "monitoring" in category_name:
            return "evidence"
        elif "effective" in category_name:
            return "effectiveness"
        
        # Default to "risk" if cannot determine
        return "risk"
    
    def _extract_compliance_framework(self, feature_kb: Dict[str, Any]) -> Optional[str]:
        """
        Extract compliance framework from feature knowledge base.
        
        Args:
            feature_kb: Feature knowledge base dictionary
        
        Returns:
            Compliance framework name or None
        """
        # Check name for framework indicators
        name = feature_kb.get("name", "").lower()
        if "soc2" in name or "soc_2" in name:
            return "SOC2"
        elif "hipaa" in name:
            return "HIPAA"
        elif "iso" in name or "27001" in name:
            return "ISO27001"
        elif "pci" in name:
            return "PCI-DSS"
        elif "nist" in name:
            return "NIST"
        
        # Check properties
        properties = feature_kb.get("properties", {})
        framework = properties.get("framework") or properties.get("compliance")
        if framework:
            return framework.upper()
        
        # Check description
        description = feature_kb.get("description", "").lower()
        if "soc2" in description or "soc 2" in description:
            return "SOC2"
        elif "hipaa" in description:
            return "HIPAA"
        elif "iso" in description or "27001" in description:
            return "ISO27001"
        
        return None
    
    def _generate_question(self, feature: Dict[str, Any], feature_type: str) -> str:
        """
        Generate a natural language question from feature definition.
        
        Args:
            feature: Feature definition
            feature_type: Type of feature
        
        Returns:
            Natural language question
        """
        name = feature.get("name", "")
        display_name = feature.get("displayName", name)
        description = feature.get("description", "")
        purpose = feature.get("purpose", "")
        
        # Generate question based on feature type
        if feature_type == "control":
            if description:
                return f"What controls are in place for {display_name}? {description}"
            return f"What controls are in place for {display_name}?"
        
        elif feature_type == "risk":
            if description:
                return f"What is the risk level for {display_name}? {description}"
            return f"What is the risk level for {display_name}?"
        
        elif feature_type == "impact":
            if description:
                return f"What is the impact of {display_name}? {description}"
            return f"What is the impact of {display_name}?"
        
        elif feature_type == "likelihood":
            if description:
                return f"What is the likelihood of {display_name}? {description}"
            return f"What is the likelihood of {display_name}?"
        
        elif feature_type == "evidence":
            if description:
                return f"What evidence exists for {display_name}? {description}"
            return f"What evidence exists for {display_name}?"
        
        elif feature_type == "effectiveness":
            if description:
                return f"How effective is {display_name}? {description}"
            return f"How effective is {display_name}?"
        
        # Default question
        if description:
            return f"Tell me about {display_name}. {description}"
        return f"Tell me about {display_name}"
    
    def _extract_control_identifier(self, feature: Dict[str, Any], category: Dict[str, Any]) -> Optional[str]:
        """
        Extract control identifier from feature or category.
        
        Args:
            feature: Feature definition
            category: Category definition
        
        Returns:
            Control identifier or None
        """
        # Check feature properties
        properties = feature.get("properties", {})
        control = properties.get("control") or properties.get("control_id") or properties.get("controlFamily")
        if control:
            return str(control)
        
        # Check category properties
        category_properties = category.get("properties", {})
        control = category_properties.get("control") or category_properties.get("control_id")
        if control:
            return str(control)
        
        return None
    
    def index_feature_knowledge_file(
        self,
        file_path: Union[str, Path],
        compliance: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Index a feature knowledge JSON file.
        
        Args:
            file_path: Path to feature knowledge JSON file
            compliance: Override compliance framework (if not in file)
            metadata: Additional metadata
        
        Returns:
            Dictionary with indexing results
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        logger.info(f"Indexing feature knowledge file: {file_path}")
        
        # Load feature knowledge base
        with open(file_path, 'r') as f:
            feature_kb = json.load(f)
        
        # Extract compliance framework
        framework = compliance or self._extract_compliance_framework(feature_kb)
        if not framework:
            framework = "GENERIC"
            logger.warning(f"Could not determine compliance framework from {file_path}, using GENERIC")
        
        # Process categories and features
        categories = feature_kb.get("categories", {})
        results = {
            "features_indexed": 0,
            "by_type": {},
            "by_category": {},
            "errors": []
        }
        
        all_documents = []
        
        for category_name, category in categories.items():
            features = category.get("features", [])
            category_indexed = 0
            
            for feature in features:
                try:
                    # Determine feature type
                    feature_type = self._determine_feature_type(feature, category)
                    
                    # Generate question
                    question = self._generate_question(feature, feature_type)
                    
                    # Extract control identifier
                    control = self._extract_control_identifier(feature, category)
                    
                    # Create document content
                    content = {
                        "question": question,
                        "feature_type": feature_type,
                        "compliance": framework,
                        "control": control,
                        "description": feature.get("description", ""),
                        "purpose": feature.get("purpose", ""),
                        "feature_name": feature.get("name", ""),
                        "display_name": feature.get("displayName", ""),
                        "category": category_name,
                        "category_display_name": category.get("displayName", category_name)
                    }
                    
                    # Create document metadata
                    doc_metadata = {
                        "feature_type": feature_type,
                        "compliance": framework,
                        "control": control or "none",
                        "source": "feature_knowledge",
                        "source_file": str(file_path),
                        "feature_name": feature.get("name", ""),
                        "category": category_name,
                        "data_type": feature.get("dataType", ""),
                        "indexed_at": datetime.utcnow().isoformat(),
                        **(metadata or {})
                    }
                    
                    # Create document
                    doc = Document(
                        page_content=json.dumps(content, indent=2),
                        metadata=doc_metadata
                    )
                    
                    all_documents.append(doc)
                    results["features_indexed"] += 1
                    category_indexed += 1
                    
                    # Update counters
                    results["by_type"][feature_type] = results["by_type"].get(feature_type, 0) + 1
                    results["by_category"][category_name] = category_indexed
                    
                except Exception as e:
                    error_msg = f"Error processing feature {feature.get('name', 'unknown')}: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
        
        # Store documents
        if self.preview_mode:
            # Save to files
            file_result = self.file_storage.save_documents(
                documents=all_documents,
                content_type="feature_knowledge",
                domain="features",
                product_name=framework,
                metadata={**(metadata or {}), "source_file": str(file_path)}
            )
            results["preview_mode"] = True
            results["file_storage"] = file_result
        else:
            # Store in database
            try:
                store = self.storage_service.stores["features"]
                result = store.add_documents(all_documents)
                results["result"] = result
                logger.info(f"Indexed {results['features_indexed']} features to database")
            except Exception as e:
                logger.error(f"Error storing features: {e}")
                results["error"] = str(e)
        
        return {
            "success": True,
            "framework": framework,
            "file_path": str(file_path),
            **results
        }
    
    def index_feature_knowledge_directory(
        self,
        directory_path: Union[str, Path],
        compliance: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Index all feature knowledge JSON files in a directory.
        
        Args:
            directory_path: Path to directory containing feature knowledge files
            compliance: Override compliance framework (if not in files)
            metadata: Additional metadata
        
        Returns:
            Dictionary with indexing results
        """
        directory_path = Path(directory_path)
        if not directory_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Find all JSON files
        json_files = list(directory_path.glob("*.json"))
        
        logger.info(f"Found {len(json_files)} JSON files in {directory_path}")
        
        results = {
            "files_processed": 0,
            "files_succeeded": 0,
            "files_failed": 0,
            "total_features_indexed": 0,
            "file_results": []
        }
        
        for json_file in json_files:
            try:
                file_result = self.index_feature_knowledge_file(
                    file_path=json_file,
                    compliance=compliance,
                    metadata=metadata
                )
                
                results["files_processed"] += 1
                if file_result.get("success"):
                    results["files_succeeded"] += 1
                    results["total_features_indexed"] += file_result.get("features_indexed", 0)
                else:
                    results["files_failed"] += 1
                
                results["file_results"].append({
                    "file": str(json_file),
                    "success": file_result.get("success", False),
                    "features_indexed": file_result.get("features_indexed", 0),
                    "framework": file_result.get("framework", "unknown")
                })
                
            except Exception as e:
                logger.error(f"Error processing file {json_file}: {e}")
                results["files_processed"] += 1
                results["files_failed"] += 1
                results["file_results"].append({
                    "file": str(json_file),
                    "success": False,
                    "error": str(e)
                })
        
        return results


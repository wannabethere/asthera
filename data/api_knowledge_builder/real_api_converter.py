#!/usr/bin/env python3
"""
Real API Spec Converter - Main entry point for converting OpenAPI specs to enhanced MDL
Fetches and converts actual API specifications with agent-based enhancements.

This is the main entry point that:
1. Fetches OpenAPI specs from URLs, files, or known APIs
2. Converts to MDL using api_to_mdl_converter.py
3. Enhances with agents:
   - Semantic descriptions
   - Schema documentation
   - Relationship recommendations
   - Business context

Usage:
    python real_api_converter.py --input <url_or_file> --output <output_file.json> [options]
    python real_api_converter.py --api snyk --version 2025-11-05 --output snyk_mdl.json
"""
import asyncio
import json
import argparse
import os
import sys
import requests
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

# Add current directory to path for local imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Add dataservices to path for agent imports
dataservices_path = Path(__file__).parent.parent.parent / "dataservices"
sys.path.insert(0, str(dataservices_path))

# Local imports
from api_to_mdl_converter import APIToMDLConverter
from openapi_parser import OpenAPIParser

# Standalone settings and dependencies
from standalone_settings import get_settings, init_environment
from standalone_dependencies import get_llm, get_embeddings

# Import agents
from app.agents.semantics_description import SemanticsDescription
from app.agents.relationship_recommendation import RelationshipRecommendation
from app.agents.schema_manager import LLMSchemaDocumentationGenerator
from app.agents.project_manager import MDLSchemaGenerator
from app.service.models import DomainContext, SchemaInput


class CheckpointManager:
    """Manages checkpoints for resuming long-running conversions"""
    
    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = checkpoint_file
        self.state = {}
        self.load_checkpoint()
    
    def load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint state from file"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    self.state = json.load(f)
                print(f"📂 Loaded checkpoint from: {self.checkpoint_file}")
                print(f"   Last checkpoint: {self.state.get('last_checkpoint', 'unknown')}")
                return self.state
            except Exception as e:
                print(f"⚠️  Failed to load checkpoint: {e}")
                self.state = {}
        return {}
    
    def save_checkpoint(self, checkpoint_name: str, data: Dict[str, Any], 
                       metadata: Optional[Dict[str, Any]] = None):
        """Save checkpoint state to file"""
        self.state[checkpoint_name] = {
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        self.state['last_checkpoint'] = checkpoint_name
        self.state['last_updated'] = datetime.now().isoformat()
        
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            print(f"💾 Checkpoint saved: {checkpoint_name}")
        except Exception as e:
            print(f"⚠️  Failed to save checkpoint: {e}")
    
    def get_checkpoint(self, checkpoint_name: str) -> Optional[Dict[str, Any]]:
        """Get checkpoint data by name"""
        checkpoint = self.state.get(checkpoint_name)
        if checkpoint:
            return checkpoint.get('data')
        return None
    
    def has_checkpoint(self, checkpoint_name: str) -> bool:
        """Check if a checkpoint exists"""
        return checkpoint_name in self.state
    
    def clear_checkpoint(self, checkpoint_name: str):
        """Clear a specific checkpoint"""
        if checkpoint_name in self.state:
            del self.state[checkpoint_name]
            self.save_checkpoint('_internal', {})  # Trigger save
    
    def clear_all(self):
        """Clear all checkpoints"""
        self.state = {}
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
        print("🗑️  All checkpoints cleared")


class ProgressTracker:
    """Tracks progress through conversion steps"""
    
    def __init__(self, total_steps: int = 7):
        self.total_steps = total_steps
        self.current_step = 0
        self.step_start_time = None
        self.step_times = []
        self.start_time = time.time()
    
    def start_step(self, step_name: str, step_num: int):
        """Start a new step"""
        if self.step_start_time:
            elapsed = time.time() - self.step_start_time
            self.step_times.append(elapsed)
        
        self.current_step = step_num
        self.step_start_time = time.time()
        elapsed_total = time.time() - self.start_time
        progress_pct = (step_num / self.total_steps) * 100
        
        print(f"\n{'='*80}")
        print(f"📊 Step {step_num}/{self.total_steps}: {step_name} ({progress_pct:.1f}% complete)")
        print(f"   Elapsed: {self._format_time(elapsed_total)}")
        if self.step_times:
            avg_time = sum(self.step_times) / len(self.step_times)
            remaining_steps = self.total_steps - step_num
            estimated_remaining = avg_time * remaining_steps
            print(f"   Estimated remaining: {self._format_time(estimated_remaining)}")
        print(f"{'='*80}")
    
    def end_step(self):
        """End current step"""
        if self.step_start_time:
            elapsed = time.time() - self.step_start_time
            print(f"   ✅ Step completed in {self._format_time(elapsed)}")
    
    def _format_time(self, seconds: float) -> str:
        """Format time in human-readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds/60:.1f}m"
        else:
            return f"{seconds/3600:.1f}h"
    
    def get_summary(self) -> Dict[str, Any]:
        """Get progress summary"""
        total_elapsed = time.time() - self.start_time
        return {
            'total_steps': self.total_steps,
            'current_step': self.current_step,
            'total_elapsed': total_elapsed,
            'step_times': self.step_times
        }


class RealAPIConverter:
    """
    Main utility for converting real-world API specifications to enhanced MDL
    Integrates with agents for semantic enhancement and documentation
    """
    
    # Known OpenAPI spec URLs
    KNOWN_SPECS = {
        'snyk_rest': 'https://api.snyk.io/rest/openapi',
        # Add more as needed
    }
    
    def __init__(self, 
                 api_token: Optional[str] = None,
                 enable_agents: bool = True,
                 domain_id: str = "api",
                 domain_name: str = "API Data",
                 business_domain: str = "api_integration"):
        """
        Initialize with optional API token and agent configuration
        
        Args:
            api_token: Optional API token for authenticated endpoints
            enable_agents: Whether to enable agent-based enhancements
            domain_id: Domain identifier for agent context
            domain_name: Domain display name
            business_domain: Business domain name
        """
        self.api_token = api_token
        self.session = requests.Session()
        self.enable_agents = enable_agents
        
        if api_token:
            self.session.headers.update({
                'Authorization': f'token {api_token}'
            })
        
        # Initialize agents if enabled
        if enable_agents:
            # Initialize environment FIRST (before any agents)
            init_environment()
            
            self.domain_id = domain_id
            self.domain_name = domain_name
            self.business_domain = business_domain
            
            # Initialize agents
            self.semantics_agent = SemanticsDescription()
            self.relationship_agent = RelationshipRecommendation()
            llm = get_llm()
            self.schema_manager = LLMSchemaDocumentationGenerator(llm=llm)
            
            # Create base domain context (will be enhanced with API docs)
            self._base_domain_context = {
                'domain_id': domain_id,
                'domain_name': domain_name,  # Note: DomainContext uses 'domain_name', not 'project_name'
                'business_domain': business_domain,
                'purpose': f"API data integration and analysis for {domain_name}",
                'target_users': ["API Developers", "Data Analysts", "Business Analysts"],
                'key_business_concepts': ["api_integration", "data_access", "endpoint_analysis"],
                'data_sources': ["REST API"],
                'compliance_requirements': []
            }
            
            self.domain_context = DomainContext(**self._base_domain_context)
    
    def _create_enhanced_domain_context(self, 
                                       endpoint_docs: Dict[str, Any],
                                       associated_docs: Dict[str, str]) -> DomainContext:
        """
        Create enhanced domain context with API documentation
        
        Args:
            endpoint_docs: Dictionary of endpoint documentation
            associated_docs: Dictionary of associated API documentation
            
        Returns:
            Enhanced DomainContext
        """
        # Build enhanced purpose with API docs context
        purpose = self._base_domain_context['purpose']
        
        if endpoint_docs:
            purpose += f"\n\nAPI Endpoints: {len(endpoint_docs)} GET endpoints documented"
            # Add key endpoint summaries
            key_endpoints = list(endpoint_docs.values())[:5]  # First 5
            for doc in key_endpoints:
                if doc.get('summary'):
                    purpose += f"\n- {doc.get('method')} {doc.get('path')}: {doc.get('summary')}"
        
        if associated_docs:
            purpose += f"\n\nAssociated Documentation: {len(associated_docs)} additional documentation sources"
            for url in list(associated_docs.keys())[:3]:  # First 3 URLs
                purpose += f"\n- {url}"
        
        # Build enhanced business concepts from endpoint tags
        concepts = set(self._base_domain_context['key_business_concepts'])
        for doc in endpoint_docs.values():
            concepts.update(doc.get('tags', []))
        
        return DomainContext(
            domain_id=self._base_domain_context['domain_id'],
            domain_name=self._base_domain_context['domain_name'],  # Use 'domain_name', not 'project_name'
            business_domain=self._base_domain_context['business_domain'],
            purpose=purpose,
            target_users=self._base_domain_context['target_users'],
            key_business_concepts=list(concepts),
            data_sources=self._base_domain_context['data_sources'],
            compliance_requirements=self._base_domain_context['compliance_requirements']
        )
    
    def fetch_spec(self, 
                   url: str,
                   version: Optional[str] = None,
                   headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Fetch OpenAPI spec from URL
        
        Args:
            url: URL to OpenAPI spec
            version: Optional API version parameter
            headers: Optional additional headers
            
        Returns:
            OpenAPI spec as dictionary
        """
        request_headers = headers or {}
        
        # For Snyk API, if version is provided, use path-based format directly
        if version and 'api.snyk.io' in url and '/rest/openapi' in url:
            version_url = url.rstrip('/') + '/' + version
            print(f"Fetching OpenAPI spec from: {version_url} (Snyk API with version in path)")
            response = self.session.get(version_url, headers=request_headers)
            response.raise_for_status()
            spec = response.json()
            
            # If it's still a list, fall through to list handling logic below
            if not isinstance(spec, list):
                # Validate it's actually an OpenAPI spec
                if 'openapi' not in spec and 'swagger' not in spec:
                    print(f"⚠️  Warning: Response doesn't appear to be an OpenAPI spec (missing 'openapi' or 'swagger' key)")
                    print(f"   Top-level keys: {list(spec.keys())[:10]}")
                
                # Extract info safely
                info = spec.get('info', {})
                if isinstance(info, dict):
                    title = info.get('title', 'Unknown')
                    spec_version = info.get('version', 'Unknown')
                else:
                    title = 'Unknown'
                    spec_version = 'Unknown'
                
                print(f"✅ Fetched spec: {title}")
                print(f"   Spec version: {spec_version}")
                
                return spec
        
        # Default behavior: try base URL first (may return list of versions)
        params = {}
        if version:
            params['version'] = version
        
        print(f"Fetching OpenAPI spec from: {url}")
        if params:
            print(f"Parameters: {params}")
        
        response = self.session.get(url, params=params, headers=request_headers)
        response.raise_for_status()
        
        spec = response.json()
        
        # Handle case where API returns a list of version strings (e.g., Snyk API)
        if isinstance(spec, list):
            if len(spec) > 0:
                # Check if it's a list of version strings
                first_item = spec[0]
                if isinstance(first_item, str):
                    # This is a list of version strings, not OpenAPI specs
                    print(f"📋 API returned a list of {len(spec)} available versions")
                    print(f"   Available versions (first 10): {', '.join([str(v) for v in spec[:10]])}")
                    
                    # Find the requested version or use default
                    target_version = version or "2025-11-05"
                    
                    # Try to find exact match or closest match
                    matching_version = None
                    
                    # First, try exact match
                    if target_version in spec:
                        matching_version = target_version
                        print(f"   Found exact match for version: {target_version}")
                    else:
                        # Try to find version that starts with the target (handles "2025-11-05~experimental")
                        for v in spec:
                            if isinstance(v, str) and v.startswith(target_version):
                                matching_version = v
                                print(f"   Found version starting with {target_version}: {matching_version}")
                                break
                        
                        # If still no match, try to find version containing the target
                        if not matching_version:
                            for v in spec:
                                if isinstance(v, str) and target_version in v:
                                    matching_version = v
                                    print(f"   Found version containing {target_version}: {matching_version}")
                                    break
                        
                        # If still no match, use the first non-experimental, non-beta version
                        if not matching_version:
                            for v in spec:
                                if isinstance(v, str) and '~experimental' not in v and '~beta' not in v:
                                    matching_version = v
                                    print(f"   Using first stable version: {matching_version}")
                                    break
                        
                        # Fallback to first item
                        if not matching_version:
                            matching_version = first_item
                            print(f"   Using first available version: {matching_version}")
                    
                    # Clean up version string (remove ~experimental, ~beta suffixes for the API call)
                    clean_version = matching_version.split('~')[0] if '~' in matching_version else matching_version
                    print(f"   Fetching OpenAPI spec for version: {clean_version}")
                    
                    # Fetch the actual OpenAPI spec for this version
                    # Snyk API format: https://api.snyk.io/rest/openapi/{version}
                    # Construct URL with version in path
                    version_url = url.rstrip('/') + '/' + clean_version
                    print(f"   Using path-based URL: {version_url}")
                    version_response = self.session.get(version_url, headers=request_headers)
                    version_response.raise_for_status()
                    spec = version_response.json()
                    
                    # Handle if this also returns a list
                    if isinstance(spec, list):
                        # Look for OpenAPI spec in the list
                        openapi_spec = None
                        for item in spec:
                            if isinstance(item, dict) and ('openapi' in item or 'swagger' in item):
                                openapi_spec = item
                                break
                        
                        if openapi_spec:
                            spec = openapi_spec
                        elif len(spec) > 0 and isinstance(spec[0], dict):
                            spec = spec[0]
                        else:
                            raise ValueError(f"Could not find OpenAPI spec in version response for {clean_version}")
                else:
                    # It's a list of objects, try to find OpenAPI spec
                    openapi_spec = None
                    for item in spec:
                        if isinstance(item, dict) and ('openapi' in item or 'swagger' in item):
                            openapi_spec = item
                            break
                    
                    if openapi_spec:
                        print(f"⚠️  API returned a list with {len(spec)} items, found OpenAPI spec")
                        spec = openapi_spec
                    elif len(spec) > 0 and isinstance(spec[0], dict):
                        print(f"⚠️  API returned a list with {len(spec)} items, using first item")
                        spec = spec[0]
                    else:
                        raise ValueError("API returned a list but could not find valid OpenAPI spec")
            else:
                raise ValueError("API returned an empty list")
        
        # Validate it's now a dict
        if not isinstance(spec, dict):
            raise ValueError(
                f"Expected OpenAPI spec to be a dictionary, got {type(spec)}. "
                f"Content preview: {str(spec)[:200]}"
            )
        
        # Validate it's actually an OpenAPI spec
        if 'openapi' not in spec and 'swagger' not in spec:
            print(f"⚠️  Warning: Response doesn't appear to be an OpenAPI spec (missing 'openapi' or 'swagger' key)")
            print(f"   Top-level keys: {list(spec.keys())[:10]}")
        
        # Extract info safely
        info = spec.get('info', {})
        if isinstance(info, dict):
            title = info.get('title', 'Unknown')
            spec_version = info.get('version', 'Unknown')
        else:
            title = 'Unknown'
            spec_version = 'Unknown'
        
        print(f"✅ Fetched spec: {title}")
        print(f"   Spec version: {spec_version}")
        
        return spec
    
    async def fetch_associated_api_docs(self, doc_urls: List[str]) -> Dict[str, str]:
        """
        Fetch associated API documentation from URLs
        
        Args:
            doc_urls: List of URLs to fetch documentation from
            
        Returns:
            Dictionary mapping URLs to their content
        """
        docs = {}
        
        for url in doc_urls:
            try:
                print(f"   Fetching associated API docs from: {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                # Try to parse as JSON first, then fallback to text
                try:
                    content = response.json()
                    docs[url] = json.dumps(content, indent=2)
                except:
                    docs[url] = response.text
                
                print(f"   ✅ Fetched {len(docs[url])} characters from {url}")
            except Exception as e:
                print(f"   ⚠️  Failed to fetch {url}: {str(e)}")
                docs[url] = f"Error fetching: {str(e)}"
        
        return docs
    
    def extract_endpoint_documentation(self, endpoint, parser: OpenAPIParser) -> Dict[str, Any]:
        """
        Extract documentation from an endpoint for business context
        
        Args:
            endpoint: EndpointDefinition object
            parser: OpenAPIParser instance
            
        Returns:
            Dictionary with endpoint documentation
        """
        doc = {
            'path': endpoint.path,
            'method': endpoint.method,
            'operation_id': endpoint.operation_id,
            'summary': endpoint.summary or '',
            'description': endpoint.description or '',
            'tags': endpoint.tags,
            'parameters': []
        }
        
        # Extract parameter descriptions
        for param in endpoint.parameters:
            param_doc = {
                'name': param.get('name', ''),
                'in': param.get('in', ''),
                'description': param.get('description', ''),
                'required': param.get('required', False),
                'schema': param.get('schema', {})
            }
            doc['parameters'].append(param_doc)
        
        # Extract response descriptions
        doc['responses'] = {}
        if hasattr(endpoint, 'responses') and endpoint.responses:
            for status_code, response in endpoint.responses.items():
                response_doc = {
                    'description': response.get('description', ''),
                    'content': response.get('content', {})
                }
                doc['responses'][status_code] = response_doc
        
        return doc
    
    async def convert_spec_from_url(self,
                             url: str,
                             catalog: str = "api",
                             schema: str = "public",
                             version: Optional[str] = None,
                             output_file: Optional[str] = None,
                                    filter_get_only: bool = True,
                                    filter_tags: Optional[List[str]] = None,
                                    associated_api_docs: Optional[List[str]] = None,
                             **converter_kwargs) -> Dict[str, Any]:
        """
        Fetch and convert OpenAPI spec from URL with optional agent enhancements
        
        Args:
            url: URL to OpenAPI spec
            catalog: MDL catalog name
            schema: MDL schema name
            version: Optional API version
            output_file: Optional output file path
            filter_get_only: Whether to only process GET endpoints
            **converter_kwargs: Additional arguments for converter
            
        Returns:
            Enhanced MDL schema dictionary
        """
        # Fetch spec
        spec = self.fetch_spec(url, version=version)
        
        # Fetch associated API docs if provided
        associated_docs = {}
        if associated_api_docs:
            print("\n📚 Fetching associated API documentation...")
            associated_docs = await self.fetch_associated_api_docs(associated_api_docs)
        
        # Save raw spec
        if output_file:
            raw_spec_file = output_file.replace('.json', '_raw_openapi.json')
            with open(raw_spec_file, 'w') as f:
                json.dump(spec, f, indent=2)
            print(f"📄 Saved raw OpenAPI spec to: {raw_spec_file}")
        
        # Convert using api_to_mdl_converter
        resume = converter_kwargs.pop('resume', True)
        return await self._convert_with_enhancement(
            spec, catalog, schema, output_file, filter_get_only, 
            filter_tags=filter_tags,
            associated_api_docs=associated_docs,
            resume=resume,
            **converter_kwargs
        )
    
    async def convert_spec_from_file(self,
                                     filepath: str,
                                     catalog: str = "api",
                                     schema: str = "public",
                                     output_file: Optional[str] = None,
                                     filter_get_only: bool = True,
                                     filter_tags: Optional[List[str]] = None,
                                     associated_api_docs: Optional[List[str]] = None,
                                     **converter_kwargs) -> Dict[str, Any]:
        """
        Convert OpenAPI spec from local file with optional agent enhancements
        
        Args:
            filepath: Path to OpenAPI spec file
            catalog: MDL catalog name
            schema: MDL schema name
            output_file: Optional output file path
            filter_get_only: Whether to only process GET endpoints
            associated_api_docs: Optional list of URLs to associated API documentation
            **converter_kwargs: Additional arguments for converter
            
        Returns:
            Enhanced MDL schema dictionary
        """
        print(f"Loading OpenAPI spec from file: {filepath}")
        parser = OpenAPIParser.from_file(filepath)
        spec = parser.spec
        
        # Fetch associated API docs if provided
        associated_docs = {}
        if associated_api_docs:
            print("\n📚 Fetching associated API documentation...")
            associated_docs = await self.fetch_associated_api_docs(associated_api_docs)
        
        resume = converter_kwargs.pop('resume', True)
        return await self._convert_with_enhancement(
            spec, catalog, schema, output_file, filter_get_only,
            filter_tags=filter_tags,
            associated_api_docs=associated_docs,
            resume=resume,
            **converter_kwargs
        )
    
    async def _convert_with_enhancement(self,
                                       spec: Dict[str, Any],
                                       catalog: str,
                                       schema: str,
                                       output_file: Optional[str],
                                       filter_get_only: bool,
                                       filter_tags: Optional[List[str]] = None,
                                       associated_api_docs: Optional[Dict[str, str]] = None,
                                       resume: bool = True,
                                       **converter_kwargs) -> Dict[str, Any]:
        """
        Internal method to convert spec with enhancement pipeline
        
        Args:
            spec: OpenAPI specification dictionary
            catalog: MDL catalog name
            schema: MDL schema name
            output_file: Optional output file path
            filter_get_only: Whether to only process GET endpoints
            filter_tags: Optional list of tags to filter by
            associated_api_docs: Dictionary of associated API documentation (URL -> content)
            resume: Whether to resume from checkpoint if available
            **converter_kwargs: Additional converter arguments
        """
        # Initialize checkpoint manager and progress tracker
        checkpoint_file = None
        checkpoint_manager = None
        if output_file:
            checkpoint_file = output_file.replace('.json', '_checkpoint.json')
            checkpoint_manager = CheckpointManager(checkpoint_file)
        
        progress = ProgressTracker(total_steps=7)
        
        print("=" * 80)
        print("🚀 Starting MDL Generation from OpenAPI")
        print("=" * 80)
        
        # Check if we can resume from checkpoint
        if resume and checkpoint_manager and checkpoint_manager.has_checkpoint('initial_mdl'):
            print("\n🔄 Found checkpoint, resuming...")
            return await self._resume_from_checkpoint(checkpoint_manager, output_file, progress)
        
        # Step 1: Parse and filter endpoints
        progress.start_step("Parsing OpenAPI specification", 1)
        
        # Check checkpoint for parsed endpoints
        parser = None
        endpoint_docs = None
        if checkpoint_manager and checkpoint_manager.has_checkpoint('parsed_endpoints'):
            print("   📂 Loading parsed endpoints from checkpoint...")
            checkpoint_data = checkpoint_manager.get_checkpoint('parsed_endpoints')
            # Recreate parser from checkpoint
            parser = OpenAPIParser(spec)
            parser.parse()
            # Restore filtered endpoints if available
            if checkpoint_data.get('filtered_endpoint_paths'):
                filtered_paths = set(checkpoint_data['filtered_endpoint_paths'])
                parser.endpoints = [ep for ep in parser.endpoints if ep.path in filtered_paths]
            endpoint_docs = checkpoint_data.get('endpoint_docs', {})
        else:
            parser = OpenAPIParser(spec)
            parser.parse()
        
        if not endpoint_docs:
            # Extract endpoint documentation for GET endpoints
            endpoint_docs = {}
            get_endpoints = [ep for ep in parser.endpoints if ep.method.upper() == 'GET']
            for endpoint in get_endpoints:
                endpoint_docs[endpoint.path] = self.extract_endpoint_documentation(endpoint, parser)
        
        if endpoint_docs:
            print(f"   Extracted documentation for {len(endpoint_docs)} GET endpoints")
        
        progress.end_step()
        
        # Filter for GET endpoints only if requested
        get_tags = None
        get_schemas = None
        if filter_get_only:
            print("\n🔍 Filtering for GET endpoints only...")
            original_endpoints = parser.endpoints
            get_endpoints = [
                ep for ep in original_endpoints 
                if ep.method.upper() == 'GET'
            ]
            
            # Apply tag filter if specified
            if filter_tags:
                print(f"   Filtering by tags: {', '.join(filter_tags)}")
                print(f"   Available tags in GET endpoints (first 20): {', '.join(set(tag for ep in get_endpoints for tag in ep.tags)[:20])}")
                
                # Case-insensitive tag matching
                filter_tags_lower = [tag.lower() for tag in filter_tags]
                filtered_endpoints = []
                for ep in get_endpoints:
                    ep_tags_lower = [tag.lower() for tag in ep.tags]
                    if any(ft in ep_tags_lower for ft in filter_tags_lower):
                        filtered_endpoints.append(ep)
                        print(f"   ✓ {ep.method} {ep.path} (tags: {', '.join(ep.tags)})")
                
                get_endpoints = filtered_endpoints
                print(f"   Found {len(get_endpoints)} GET endpoints matching specified tags (out of {len([ep for ep in original_endpoints if ep.method.upper() == 'GET'])} GET endpoints)")
            else:
                # Log all endpoints if no filter
                print(f"   Processing all {len(get_endpoints)} GET endpoints")
                for ep in get_endpoints[:10]:  # Show first 10
                    print(f"   - {ep.method} {ep.path} (tags: {', '.join(ep.tags)})")
                if len(get_endpoints) > 10:
                    print(f"   ... and {len(get_endpoints) - 10} more")
            
            parser.endpoints = get_endpoints
            print(f"   Total GET endpoints to process: {len(parser.endpoints)} (out of {len(original_endpoints)} total endpoints)")
            
            get_tags = set()
            get_schemas = set()
            schema_to_endpoints = {}  # Track which endpoints reference which schemas
            
            # Collect all schemas referenced by GET endpoints (recursively)
            def collect_schemas_from_response(response_schema_name: str, visited: set, source_endpoint: str, depth: int = 0):
                """Recursively collect all schemas referenced by a response schema"""
                if not response_schema_name or response_schema_name in visited:
                    return
                visited.add(response_schema_name)
                get_schemas.add(response_schema_name)
                
                # Track which endpoint this schema comes from
                if response_schema_name not in schema_to_endpoints:
                    schema_to_endpoints[response_schema_name] = []
                schema_to_endpoints[response_schema_name].append({
                    'endpoint': source_endpoint,
                    'depth': depth,
                    'is_direct': depth == 0
                })
                
                # Get the schema definition
                schema_def = parser.schemas.get(response_schema_name)
                if not schema_def:
                    return
                
                # Check all properties for nested schema references
                for prop in schema_def.properties:
                    if prop.ref:
                        # Extract schema name from ref (e.g., "#/components/schemas/SchemaName" -> "SchemaName")
                        ref_name = prop.ref.split('/')[-1]
                        if ref_name and ref_name not in visited:
                            collect_schemas_from_response(ref_name, visited, source_endpoint, depth + 1)
                    elif prop.items:
                        # Handle array items
                        if isinstance(prop.items, dict) and '$ref' in prop.items:
                            ref_name = prop.items['$ref'].split('/')[-1]
                            if ref_name and ref_name not in visited:
                                collect_schemas_from_response(ref_name, visited, source_endpoint, depth + 1)
            
            for ep in get_endpoints:
                get_tags.update(ep.tags)
                endpoint_key = f"{ep.method} {ep.path}"
                # Collect schemas referenced by GET endpoints
                response_schema = parser.get_response_schema(ep)
                if response_schema:
                    collect_schemas_from_response(response_schema, set(), endpoint_key, 0)
                else:
                    # If no schema found, try to extract from response directly
                    response = ep.responses.get('200', {})
                    if response:
                        content = response.get('content', {})
                        json_content = content.get('application/json', {})
                        schema_obj = json_content.get('schema', {})
                        if schema_obj:
                            # Try to find schema name in the response structure
                            if '$ref' in schema_obj:
                                ref_name = schema_obj['$ref'].split('/')[-1]
                                collect_schemas_from_response(ref_name, set(), endpoint_key, 0)
            
            print(f"   GET endpoints use tags: {', '.join(sorted(get_tags)) if get_tags else 'none'}")
            print(f"   GET endpoints reference {len(get_schemas)} unique schemas")
            
            # Log schema-to-endpoint mapping with details
            print(f"\n   📋 Schema-to-Endpoint Mapping (showing why each schema is included):")
            schemas_sorted = sorted(list(get_schemas))
            for schema_name in schemas_sorted[:30]:  # Show first 30 schemas
                endpoints_info = schema_to_endpoints.get(schema_name, [])
                if endpoints_info:
                    # Group by endpoint
                    endpoint_groups = {}
                    for info in endpoints_info:
                        ep = info['endpoint']
                        if ep not in endpoint_groups:
                            endpoint_groups[ep] = []
                        endpoint_groups[ep].append(info)
                    
                    # Show first endpoint that references this schema
                    first_ep = list(endpoint_groups.keys())[0]
                    first_info = endpoint_groups[first_ep][0]
                    depth_indicator = " (direct)" if first_info['is_direct'] else f" (nested, depth {first_info['depth']})"
                    ref_count = len(endpoints_info)
                    ref_text = f" ({ref_count} refs)" if ref_count > 1 else ""
                    print(f"      {schema_name:<40} <- {first_ep[:50]}{depth_indicator}{ref_text}")
                else:
                    print(f"      {schema_name:<40} <- ❓ Unknown source")
            
            if len(get_schemas) > 30:
                print(f"      ... and {len(get_schemas) - 30} more schemas")
            
            # Also show endpoint-to-schema mapping for direct references
            print(f"\n   📋 Direct Endpoint-to-Schema Mapping (first 15 endpoints):")
            for ep in get_endpoints[:15]:
                response_schema = parser.get_response_schema(ep)
                schema_info = response_schema if response_schema else "❌ No schema"
                print(f"      {ep.method} {ep.path[:60]:<60} -> {schema_info}")
            if len(get_endpoints) > 15:
                print(f"      ... and {len(get_endpoints) - 15} more endpoints")
            
            # Log which endpoints have schemas and which don't
            endpoints_with_schemas = 0
            endpoints_without_schemas = 0
            for ep in get_endpoints:
                response_schema = parser.get_response_schema(ep)
                if response_schema:
                    endpoints_with_schemas += 1
                else:
                    endpoints_without_schemas += 1
                    print(f"   ⚠️  GET endpoint {ep.method} {ep.path} has no response schema")
            
            print(f"   GET endpoints with schemas: {endpoints_with_schemas}, without schemas: {endpoints_without_schemas}")
            
            # If no schemas found, don't filter - convert all schemas but only create views for GET endpoints
            if not get_schemas:
                print(f"   ⚠️  Warning: No response schemas found for GET endpoints. Will convert all schemas but only create views for GET endpoints.")
                get_schemas = None
        
        # Save checkpoint after filtering
        if checkpoint_manager:
            checkpoint_manager.save_checkpoint('parsed_endpoints', {
                'endpoint_docs': endpoint_docs,
                'filtered_endpoint_paths': [ep.path for ep in parser.endpoints],
                'total_endpoints': len(parser.endpoints)
            }, {'filter_get_only': filter_get_only, 'filter_tags': filter_tags})
        
        # Step 2: Convert using api_to_mdl_converter
        progress.start_step("Converting OpenAPI to MDL", 2)
        
        # Check checkpoint for initial MDL
        mdl = None
        if checkpoint_manager and checkpoint_manager.has_checkpoint('initial_mdl'):
            print("   📂 Loading initial MDL from checkpoint...")
            mdl = checkpoint_manager.get_checkpoint('initial_mdl')
            print(f"   ✅ Loaded MDL: {len(mdl.get('models', []))} models, {len(mdl.get('views', []))} views")
        else:
            converter = APIToMDLConverter(
                spec, 
                catalog=catalog, 
                schema=schema, 
                create_endpoint_views=True,
                infer_relationships=True,
                **converter_kwargs
            )
            
            # Replace parser with filtered one
            converter.parser = parser
            
            # Convert schemas and create views
            # Since parser.endpoints is already filtered to GET-only when filter_get_only=True,
            # we don't need to filter by tags - all endpoints in parser are already GET endpoints
            if filter_get_only:
                # Only convert schemas referenced by filtered GET endpoints
                # This ensures we only create models for schemas actually used by our filtered endpoints
                if get_schemas:
                    print(f"   Converting {len(get_schemas)} schemas referenced by filtered GET endpoints")
                    mdl = converter.convert(
                        filter_schemas=list(get_schemas),  # Only convert schemas from filtered endpoints
                        filter_tags=None     # Don't filter by tags - parser.endpoints already has only GET endpoints
                    )
                else:
                    print(f"   ⚠️  No schemas found, converting all schemas (but only creating views for filtered GET endpoints)")
                    mdl = converter.convert(
                        filter_schemas=None,  # Convert all schemas to models
                        filter_tags=None     # Don't filter by tags - parser.endpoints already has only GET endpoints
                    )
            else:
                mdl = converter.convert()
            
            print(f"   ✅ Initial MDL generated: {len(mdl.get('models', []))} models, {len(mdl.get('views', []))} views")
            
            # Log which models and views were created
            if mdl.get('models'):
                print(f"\n   📊 Models created ({len(mdl.get('models', []))}):")
                for model in mdl.get('models', [])[:20]:
                    print(f"      - {model.get('name', 'Unknown')}")
                if len(mdl.get('models', [])) > 20:
                    print(f"      ... and {len(mdl.get('models', [])) - 20} more models")
            
            if mdl.get('views'):
                print(f"\n   📊 Views created ({len(mdl.get('views', []))}):")
                for view in mdl.get('views', [])[:20]:
                    view_name = view.get('name', 'Unknown')
                    view_query = view.get('query', '')
                    # Extract endpoint info from view name or query
                    print(f"      - {view_name}")
                if len(mdl.get('views', [])) > 20:
                    print(f"      ... and {len(mdl.get('views', [])) - 20} more views")
            
            # Save checkpoint after initial MDL conversion
            if checkpoint_manager:
                checkpoint_manager.save_checkpoint('initial_mdl', mdl, {
                    'models_count': len(mdl.get('models', [])),
                    'views_count': len(mdl.get('views', [])),
                    'model_names': [m.get('name') for m in mdl.get('models', [])],
                    'view_names': [v.get('name') for v in mdl.get('views', [])]
                })
        
        progress.end_step()
        
        # Step 3: Enhance domain context with API documentation
        if self.enable_agents:
            progress.start_step("Enhancing domain context", 3)
            self.domain_context = self._create_enhanced_domain_context(
                endpoint_docs, associated_api_docs or {}
            )
            print(f"   Enhanced context with {len(endpoint_docs)} endpoint docs and {len(associated_api_docs or {})} associated docs")
            progress.end_step()
        
        # Step 4: Enhance with agents if enabled
        if self.enable_agents:
            progress.start_step("Enhancing models with semantics", 4)
            
            # Check checkpoint for semantics enhancement
            if checkpoint_manager and checkpoint_manager.has_checkpoint('semantics_enhanced'):
                print("   📂 Loading semantics-enhanced MDL from checkpoint...")
                mdl = checkpoint_manager.get_checkpoint('semantics_enhanced')
            else:
                mdl = await self._enhance_models_with_semantics(
                    mdl, endpoint_docs, associated_api_docs or {}
                )
                if checkpoint_manager:
                    checkpoint_manager.save_checkpoint('semantics_enhanced', mdl, {
                        'models_count': len(mdl.get('models', []))
                    })
            
            progress.end_step()
            
            progress.start_step("Enhancing with schema documentation", 5)
            
            # Check checkpoint for schema documentation
            if checkpoint_manager and checkpoint_manager.has_checkpoint('schema_documented'):
                print("   📂 Loading schema-documented MDL from checkpoint...")
                mdl = checkpoint_manager.get_checkpoint('schema_documented')
            else:
                mdl = await self._enhance_with_schema_documentation(
                    mdl, endpoint_docs, associated_api_docs or {}
                )
                if checkpoint_manager:
                    checkpoint_manager.save_checkpoint('schema_documented', mdl, {
                        'models_count': len(mdl.get('models', []))
                    })
            
            progress.end_step()
            
            progress.start_step("Recommending relationships", 6)
            
            # Check checkpoint for relationships
            if checkpoint_manager and checkpoint_manager.has_checkpoint('relationships_added'):
                print("   📂 Loading relationships from checkpoint...")
                mdl = checkpoint_manager.get_checkpoint('relationships_added')
            else:
                mdl = await self._enhance_with_relationships(mdl)
                if checkpoint_manager:
                    checkpoint_manager.save_checkpoint('relationships_added', mdl, {
                        'relationships_count': len(mdl.get('relationships', []))
                    })
            
            progress.end_step()
            
            # Validate
            progress.start_step("Validating MDL schema", 7)
            is_valid, errors = MDLSchemaGenerator.validate_mdl_schema(mdl)
            if not is_valid:
                print(f"   ⚠️  MDL validation found {len(errors)} issues:")
                for error in errors[:10]:
                    print(f"   - {error}")
            else:
                print("   ✅ MDL schema validation passed")
            progress.end_step()
        
        # Save MDL
        if output_file:
            progress.start_step("Saving final MDL", 8)
            with open(output_file, 'w') as f:
                json.dump(mdl, f, indent=2)
            print(f"   💾 Saved MDL to: {output_file}")
            
            # Save final checkpoint
            if checkpoint_manager:
                checkpoint_manager.save_checkpoint('final_mdl', mdl, {
                    'models_count': len(mdl.get('models', [])),
                    'views_count': len(mdl.get('views', [])),
                    'relationships_count': len(mdl.get('relationships', []))
                })
                # Optionally clean up intermediate checkpoints
                # checkpoint_manager.clear_checkpoint('initial_mdl')
            
            progress.end_step()
        
        print("\n" + "=" * 80)
        print("✅ MDL Generation Complete!")
        print("=" * 80)
        print(f"   Models: {len(mdl.get('models', []))}")
        print(f"   Views: {len(mdl.get('views', []))}")
        print(f"   Relationships: {len(mdl.get('relationships', []))}")
        print(f"   Metrics: {len(mdl.get('metrics', []))}")
        
        return mdl
    
    async def _resume_from_checkpoint(self, checkpoint_manager: CheckpointManager, 
                                     output_file: Optional[str],
                                     progress: ProgressTracker) -> Dict[str, Any]:
        """Resume conversion from the last checkpoint"""
        print("\n🔄 Resuming from checkpoint...")
        
        # Find the last completed checkpoint
        last_checkpoint = checkpoint_manager.state.get('last_checkpoint')
        if not last_checkpoint:
            print("   ⚠️  No checkpoint found, starting from beginning")
            return None
        
        print(f"   📂 Last checkpoint: {last_checkpoint}")
        
        # Load MDL from the most recent checkpoint
        mdl = None
        if checkpoint_manager.has_checkpoint('relationships_added'):
            mdl = checkpoint_manager.get_checkpoint('relationships_added')
            print("   ✅ Resuming from: Relationships added")
            progress.current_step = 6
        elif checkpoint_manager.has_checkpoint('schema_documented'):
            mdl = checkpoint_manager.get_checkpoint('schema_documented')
            print("   ✅ Resuming from: Schema documentation")
            progress.current_step = 5
        elif checkpoint_manager.has_checkpoint('semantics_enhanced'):
            mdl = checkpoint_manager.get_checkpoint('semantics_enhanced')
            print("   ✅ Resuming from: Semantics enhanced")
            progress.current_step = 4
        elif checkpoint_manager.has_checkpoint('initial_mdl'):
            mdl = checkpoint_manager.get_checkpoint('initial_mdl')
            print("   ✅ Resuming from: Initial MDL conversion")
            progress.current_step = 2
        else:
            print("   ⚠️  No valid checkpoint found, cannot resume")
            return None
        
        # Continue from where we left off
        if progress.current_step < 7:
            # Continue with remaining steps
            if progress.current_step < 4 and self.enable_agents:
                # Need to reload endpoint_docs for agent enhancements
                endpoint_docs_data = checkpoint_manager.get_checkpoint('parsed_endpoints')
                endpoint_docs = endpoint_docs_data.get('endpoint_docs', {}) if endpoint_docs_data else {}
                associated_api_docs = {}  # Would need to be saved in checkpoint if needed
                
                if progress.current_step < 4:
                    progress.start_step("Enhancing models with semantics", 4)
                    mdl = await self._enhance_models_with_semantics(mdl, endpoint_docs, associated_api_docs)
                    checkpoint_manager.save_checkpoint('semantics_enhanced', mdl, {
                        'models_count': len(mdl.get('models', []))
                    })
                    progress.end_step()
                
                if progress.current_step < 5:
                    progress.start_step("Enhancing with schema documentation", 5)
                    mdl = await self._enhance_with_schema_documentation(mdl, endpoint_docs, associated_api_docs)
                    checkpoint_manager.save_checkpoint('schema_documented', mdl, {
                        'models_count': len(mdl.get('models', []))
                    })
                    progress.end_step()
                
                if progress.current_step < 6:
                    progress.start_step("Recommending relationships", 6)
                    mdl = await self._enhance_with_relationships(mdl)
                    checkpoint_manager.save_checkpoint('relationships_added', mdl, {
                        'relationships_count': len(mdl.get('relationships', []))
                    })
                    progress.end_step()
            
            # Validate
            progress.start_step("Validating MDL schema", 7)
            is_valid, errors = MDLSchemaGenerator.validate_mdl_schema(mdl)
            if not is_valid:
                print(f"   ⚠️  MDL validation found {len(errors)} issues:")
                for error in errors[:10]:
                    print(f"   - {error}")
            else:
                print("   ✅ MDL schema validation passed")
            progress.end_step()
        
        # Save final MDL
        if output_file:
            progress.start_step("Saving final MDL", 8)
            with open(output_file, 'w') as f:
                json.dump(mdl, f, indent=2)
            print(f"   💾 Saved MDL to: {output_file}")
            
            checkpoint_manager.save_checkpoint('final_mdl', mdl, {
                'models_count': len(mdl.get('models', [])),
                'views_count': len(mdl.get('views', [])),
                'relationships_count': len(mdl.get('relationships', []))
            })
            progress.end_step()
        
        print("\n" + "=" * 80)
        print("✅ MDL Generation Complete!")
        print("=" * 80)
        print(f"   Models: {len(mdl.get('models', []))}")
        print(f"   Views: {len(mdl.get('views', []))}")
        print(f"   Relationships: {len(mdl.get('relationships', []))}")
        print(f"   Metrics: {len(mdl.get('metrics', []))}")
        
        return mdl
    
    async def convert_snyk_api(self,
                              version: Optional[str] = None,
                        catalog: str = "snyk",
                        schema: str = "rest_api",
                        output_file: str = "snyk_mdl.json",
                              filter_get_only: bool = True,
                              filter_tags: Optional[List[str]] = None,
                              associated_api_docs: Optional[List[str]] = None,
                        **kwargs) -> Dict[str, Any]:
        """
        Convert Snyk REST API to MDL with agent enhancements
        
        Args:
            version: Snyk API version (default: 2025-11-05, will auto-select if not provided)
            catalog: MDL catalog name
            schema: MDL schema name
            output_file: Output file path
            filter_get_only: Whether to only process GET endpoints
            associated_api_docs: Optional list of URLs to associated API documentation
            **kwargs: Additional converter arguments
            
        Returns:
            Enhanced MDL schema
        """
        url = self.KNOWN_SPECS['snyk_rest']
        
        # Default to 2025-11-05 if no version specified
        if version is None:
            version = "2025-11-05"
        
        print(f"Converting Snyk REST API (version: {version})")
        print("-" * 70)
        
        return await self.convert_spec_from_url(
            url=url,
            catalog=catalog,
            schema=schema,
            version=version,
            output_file=output_file,
            filter_get_only=filter_get_only,
            filter_tags=filter_tags,
            associated_api_docs=associated_api_docs,
            resume=kwargs.pop('resume', True),
            **kwargs
        )

    async def _enhance_models_with_semantics(self, 
                                            mdl: Dict[str, Any],
                                            endpoint_docs: Dict[str, Any],
                                            associated_docs: Dict[str, str]) -> Dict[str, Any]:
        """Enhance models with semantic descriptions using API documentation"""
        models = mdl.get('models', [])
        
        # Build context from associated docs
        associated_context = ""
        if associated_docs:
            associated_context = "\n\nAssociated API Documentation:\n"
            for url, content in associated_docs.items():
                associated_context += f"\nFrom {url}:\n{content[:2000]}...\n"  # Limit length
        
        for i, model in enumerate(models):
            try:
                print(f"   Processing model {i+1}/{len(models)}: {model.get('name', 'Unknown')}")
                
                # Find related endpoint documentation
                related_endpoint_docs = []
                model_name_lower = model.get('name', '').lower()
                for path, doc in endpoint_docs.items():
                    # Match if endpoint path or tags relate to model
                    if (model_name_lower in path.lower() or 
                        any(model_name_lower in tag.lower() for tag in doc.get('tags', []))):
                        related_endpoint_docs.append(doc)
                
                # Build enhanced description with API docs
                base_description = model.get('description', '') or model.get('properties', {}).get('description', '')
                api_doc_context = ""
                
                if related_endpoint_docs:
                    api_doc_context = "\n\nAPI Endpoint Documentation:\n"
                    for doc in related_endpoint_docs:
                        api_doc_context += f"Endpoint: {doc.get('method')} {doc.get('path')}\n"
                        if doc.get('summary'):
                            api_doc_context += f"Summary: {doc.get('summary')}\n"
                        if doc.get('description'):
                            api_doc_context += f"Description: {doc.get('description')}\n"
                        api_doc_context += "\n"
                
                # Convert model to table_data format for semantics agent
                table_data = {
                    'name': model.get('name', ''),
                    'description': base_description + api_doc_context + associated_context,
                    'columns': []
                }
                
                # Convert columns
                for col in model.get('columns', []):
                    col_data = {
                        'name': col.get('name', ''),
                        'display_name': col.get('properties', {}).get('displayName', col.get('name', '')),
                        'description': col.get('description', '') or col.get('properties', {}).get('description', ''),
                        'data_type': col.get('type', 'VARCHAR'),
                        'is_primary_key': col.get('name') == model.get('primaryKey'),
                        'is_nullable': not col.get('notNull', False)
                    }
                    table_data['columns'].append(col_data)
                
                # Get semantic description
                result = await self.semantics_agent.describe(
                    SemanticsDescription.Input(
                        id=f"semantics_{model.get('name', '')}",
                        table_data=table_data,
                        domain_id=self.domain_id
                    )
                )
                
                if result.status == "finished" and result.response:
                    semantic_data = result.response
                    
                    # Update model description
                    if semantic_data.get('description'):
                        if 'properties' not in model:
                            model['properties'] = {}
                        model['properties']['semantic_description'] = semantic_data['description']
                        model['properties']['table_purpose'] = semantic_data.get('table_purpose', '')
                        model['properties']['business_context'] = semantic_data.get('business_context', '')
                        
                        if not model.get('description'):
                            model['description'] = semantic_data['description']
                    
                    # Update column descriptions
                    key_columns = semantic_data.get('key_columns', [])
                    for key_col in key_columns:
                        col_name = key_col.get('name')
                        for col in model.get('columns', []):
                            if col.get('name') == col_name:
                                if 'properties' not in col:
                                    col['properties'] = {}
                                col['properties']['business_significance'] = key_col.get('business_significance', '')
                                if not col.get('description'):
                                    col['description'] = key_col.get('description', '')
                                break
                
            except Exception as e:
                print(f"   ⚠️  Error enhancing model {model.get('name', 'Unknown')}: {str(e)}")
                continue
        
        return mdl
    
    async def _enhance_with_schema_documentation(self,
                                                mdl: Dict[str, Any],
                                                endpoint_docs: Dict[str, Any],
                                                associated_docs: Dict[str, str]) -> Dict[str, Any]:
        """Enhance models with schema documentation using API documentation"""
        models = mdl.get('models', [])
        
        # Build context from associated docs
        associated_context = ""
        if associated_docs:
            associated_context = "\n\nAssociated API Documentation:\n"
            for url, content in associated_docs.items():
                associated_context += f"\nFrom {url}:\n{content[:2000]}...\n"
        
        for i, model in enumerate(models):
            try:
                print(f"   Processing model {i+1}/{len(models)}: {model.get('name', 'Unknown')}")
                
                # Find related endpoint documentation
                related_endpoint_docs = []
                model_name_lower = model.get('name', '').lower()
                for path, doc in endpoint_docs.items():
                    if (model_name_lower in path.lower() or 
                        any(model_name_lower in tag.lower() for tag in doc.get('tags', []))):
                        related_endpoint_docs.append(doc)
                
                # Build enhanced description with API docs
                base_description = model.get('description', '') or model.get('properties', {}).get('description', '')
                api_doc_context = ""
                
                if related_endpoint_docs:
                    api_doc_context = "\n\nAPI Endpoint Documentation:\n"
                    for doc in related_endpoint_docs:
                        api_doc_context += f"Endpoint: {doc.get('method')} {doc.get('path')}\n"
                        if doc.get('summary'):
                            api_doc_context += f"Summary: {doc.get('summary')}\n"
                        if doc.get('description'):
                            api_doc_context += f"Description: {doc.get('description')}\n"
                        if doc.get('parameters'):
                            api_doc_context += f"Parameters: {len(doc.get('parameters', []))} parameters\n"
                        api_doc_context += "\n"
                
                # Convert model to SchemaInput format
                columns = []
                for col in model.get('columns', []):
                    col_dict = {
                        'name': col.get('name', ''),
                        'type': col.get('type', 'VARCHAR'),
                        'data_type': col.get('type', 'VARCHAR'),
                        'nullable': not col.get('notNull', False),
                        'primary_key': col.get('name') == model.get('primaryKey'),
                        'description': col.get('description', '') or col.get('properties', {}).get('description', '')
                    }
                    columns.append(col_dict)
                
                # Enhanced description with API docs context
                enhanced_description = base_description + api_doc_context + associated_context
                
                schema_input = SchemaInput(
                    table_name=model.get('name', ''),
                    table_description=enhanced_description,
                    columns=columns,
                    sample_data=None
                )
                
                # Generate documentation
                documented_table = await self.schema_manager.document_table_schema(
                    schema_input,
                    self.domain_context
                )
                
                # Update model with documentation
                if 'properties' not in model:
                    model['properties'] = {}
                
                model['properties']['display_name'] = documented_table.display_name
                model['properties']['business_purpose'] = documented_table.business_purpose
                model['properties']['primary_use_cases'] = ','.join(documented_table.primary_use_cases)
                model['properties']['key_relationships'] = ','.join(documented_table.key_relationships)
                model['properties']['update_frequency'] = documented_table.update_frequency
                
                # Add API documentation context
                if related_endpoint_docs:
                    model['properties']['api_endpoints'] = json.dumps([
                        {
                            'path': doc.get('path'),
                            'method': doc.get('method'),
                            'summary': doc.get('summary'),
                            'description': doc.get('description')
                        }
                        for doc in related_endpoint_docs
                    ])
                
                if associated_docs:
                    model['properties']['associated_api_docs'] = json.dumps(list(associated_docs.keys()))
                
                if not model.get('description'):
                    model['description'] = documented_table.description
                
                # Update columns with enhanced documentation
                for doc_col in documented_table.columns:
                    for mdl_col in model.get('columns', []):
                        if mdl_col.get('name') == doc_col.column_name:
                            if 'properties' not in mdl_col:
                                mdl_col['properties'] = {}
                            
                            mdl_col['properties']['displayName'] = doc_col.display_name
                            mdl_col['properties']['businessDescription'] = doc_col.business_description
                            mdl_col['properties']['usageType'] = doc_col.usage_type.value
                            
                            if doc_col.example_values:
                                mdl_col['properties']['exampleValues'] = ','.join(doc_col.example_values[:5])
                            
                            if not mdl_col.get('description'):
                                mdl_col['description'] = doc_col.description
                            break
                
            except Exception as e:
                print(f"   ⚠️  Error documenting model {model.get('name', 'Unknown')}: {str(e)}")
                continue
        
        return mdl
    
    async def _enhance_with_relationships(self, mdl: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance MDL with relationship recommendations"""
        models = mdl.get('models', [])
        
        if len(models) < 2:
            print("   ⚠️  Need at least 2 models for relationship recommendations")
            return mdl
        
        try:
            # Convert models to table_data format
            tables_data = []
            for model in models:
                table_data = {
                    'name': model.get('name', ''),
                    'display_name': model.get('properties', {}).get('display_name', model.get('name', '')),
                    'description': model.get('description', '') or model.get('properties', {}).get('description', ''),
                    'columns': []
                }
                
                for col in model.get('columns', []):
                    col_data = {
                        'name': col.get('name', ''),
                        'display_name': col.get('properties', {}).get('displayName', col.get('name', '')),
                        'description': col.get('description', '') or col.get('properties', {}).get('description', ''),
                        'data_type': col.get('type', 'VARCHAR'),
                        'is_primary_key': col.get('name') == model.get('primaryKey'),
                        'is_nullable': not col.get('notNull', False),
                        'is_foreign_key': False
                    }
                    table_data['columns'].append(col_data)
                
                tables_data.append(table_data)
            
            # Get relationship recommendations
            result = await self.relationship_agent.recommend(
                RelationshipRecommendation.Input(
                    id="relationship_recommendations",
                    tables_data=tables_data,
                    domain_id=self.domain_id
                )
            )
            
            if result.status == "finished" and result.response:
                recommendations = result.response.get('relationships', [])
                
                # Add recommended relationships to MDL
                existing_relationships = {rel.get('name'): rel for rel in mdl.get('relationships', [])}
                
                for rec in recommendations:
                    rel_name = f"{rec['source_table']}_{rec['target_table']}"
                    
                    if rel_name not in existing_relationships:
                        relationship = {
                            'name': rel_name,
                            'models': [rec['source_table'], rec['target_table']],
                            'joinType': rec['relationship_type'].upper().replace('-', '_'),
                            'condition': f"{rec['source_table']}.{rec['source_column']} = {rec['target_table']}.{rec['target_column']}",
                            'properties': {
                                'explanation': rec.get('explanation', ''),
                                'business_value': rec.get('business_value', ''),
                                'confidence_score': str(rec.get('confidence_score', 0.0))
                            }
                        }
                        
                        if 'relationships' not in mdl:
                            mdl['relationships'] = []
                        mdl['relationships'].append(relationship)
                
                print(f"   ✅ Added {len(recommendations)} relationship recommendations")
        
        except Exception as e:
            print(f"   ⚠️  Error recommending relationships: {str(e)}")
        
        return mdl


async def example_snyk_conversion():
    """Example: Convert Snyk API"""
    print("\n" + "="*70)
    print("EXAMPLE: Snyk API Conversion")
    print("="*70)
    
    converter = RealAPIConverter(enable_agents=True)
    
    try:
        mdl = await converter.convert_snyk_api(
            version="2025-11-05",  # Using 2025-11-05 as default for Snyk
            catalog="snyk",
            schema="rest_api_v1",
            output_file="snyk_rest_api_mdl.json",
            filter_get_only=True
        )
        
        print("\n✅ Conversion complete!")
        print(f"Models: {len(mdl.get('models', []))}")
        print(f"Views: {len(mdl.get('views', []))}")
        print(f"Relationships: {len(mdl.get('relationships', []))}")
        
        return mdl
        
    except Exception as e:
        print(f"\n❌ Error converting Snyk API: {e}")
        print("\nNote: The Snyk API may require authentication or the endpoint may have changed.")
        print("You can try downloading the OpenAPI spec manually from:")
        print("https://apidocs.snyk.io/ (use browser dev tools to capture the spec)")
        return None


async def example_generic_api_conversion():
    """Example: Convert any OpenAPI spec URL"""
    print("\n" + "="*70)
    print("EXAMPLE: Generic API Conversion")
    print("="*70)
    
    # Example with a public API
    api_spec_url = "https://petstore3.swagger.io/api/v3/openapi.json"
    
    converter = RealAPIConverter(enable_agents=True)
    
    try:
        mdl = await converter.convert_spec_from_url(
            url=api_spec_url,
            catalog="petstore",
            schema="v3",
            output_file="petstore_mdl.json",
            filter_get_only=True
        )
        
        print("\n✅ Conversion complete!")
        return mdl
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None


async def example_with_local_spec():
    """Example: Convert from a downloaded OpenAPI spec file"""
    print("\n" + "="*70)
    print("EXAMPLE: Convert from Local File")
    print("="*70)
    
    spec_file = "snyk_openapi.json"
    
    try:
        print(f"\nAttempting to load: {spec_file}")
        converter = RealAPIConverter(enable_agents=True)
        mdl = await converter.convert_spec_from_file(
            filepath=spec_file,
            catalog="snyk",
            schema="rest",
            output_file="snyk_from_file_mdl.json",
            filter_get_only=True
        )
        print("✅ Conversion complete!")
        return mdl
        
    except FileNotFoundError:
        print(f"❌ File not found: {spec_file}")
        print("Please download the OpenAPI spec first")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def create_manual_schema_template():
    """Create a template for manually building schemas when OpenAPI is not available"""
    print("\n" + "="*70)
    print("EXAMPLE: Manual Schema Template")
    print("="*70)
    
    template = {
        "api_name": "Your API Name",
        "base_url": "https://api.example.com",
        "endpoints": [
            {
                "path": "/v1/resources",
                "method": "GET",
                "description": "List resources",
                "response_schema": {
                    "name": "Resource",
                    "properties": [
                        {
                            "name": "id",
                            "type": "string",
                            "format": "uuid",
                            "description": "Unique identifier",
                            "required": True
                        },
                        {
                            "name": "name",
                            "type": "string",
                            "description": "Resource name",
                            "required": True
                        },
                        {
                            "name": "created_at",
                            "type": "string",
                            "format": "date-time",
                            "description": "Creation timestamp"
                        }
                    ]
                }
            }
        ]
    }
    
    output_file = "manual_schema_template.json"
    with open(output_file, 'w') as f:
        json.dump(template, f, indent=2)
    
    print(f"✅ Template saved to: {output_file}")
    print("\nYou can use this template to:")
    print("1. Document API endpoints manually")
    print("2. Convert to OpenAPI spec format")
    print("3. Then use the converter on the generated spec")
    
    return template


async def main():
    """Main entry point with command-line interface"""
    parser = argparse.ArgumentParser(
        description='Convert OpenAPI specifications to enhanced MDL schemas with agent-based enhancements',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # From URL
  python real_api_converter.py --input https://api.example.com/openapi.json --output mdl.json
  
  # From file
  python real_api_converter.py --input openapi.json --output mdl.json
  
  # From known API (Snyk) - defaults to 2025-11-05 if version not specified
  python real_api_converter.py --api snyk --version 2025-11-05 --output snyk_mdl.json
  
  # With associated API documentation
  python real_api_converter.py --input openapi.json --output mdl.json --associated-docs https://docs.example.com/api-guide https://docs.example.com/authentication
  
  # Without agent enhancements
  python real_api_converter.py --input openapi.json --output mdl.json --no-agents
  
  # All HTTP methods (not just GET)
  python real_api_converter.py --input openapi.json --output mdl.json --all-methods
  
  # Filter by specific tags (e.g., only Assets, Issues, Cloud APIs)
  python real_api_converter.py --api snyk --output snyk_mdl.json --filter-tags Assets Issues Cloud IacSettings AuditLogs
        """
    )
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--input',
        type=str,
        help='Input OpenAPI specification (file path or URL)'
    )
    input_group.add_argument(
        '--api',
        type=str,
        choices=['snyk'],
        help='Use a known API specification (e.g., snyk)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Output MDL JSON file path'
    )
    
    parser.add_argument(
        '--api-token',
        type=str,
        help='API token for authenticated endpoints'
    )
    
    parser.add_argument(
        '--version',
        type=str,
        help='API version (for APIs that support versioning, e.g., Snyk)'
    )
    
    parser.add_argument(
        '--catalog',
        type=str,
        default='api',
        help='MDL catalog name (default: api)'
    )
    
    parser.add_argument(
        '--schema',
        type=str,
        default='public',
        help='MDL schema name (default: public)'
    )
    
    parser.add_argument(
        '--domain-id',
        type=str,
        default='api',
        help='Domain identifier (default: api)'
    )
    
    parser.add_argument(
        '--domain-name',
        type=str,
        default='API Data',
        help='Domain display name (default: API Data)'
    )
    
    parser.add_argument(
        '--no-agents',
        action='store_true',
        help='Disable agent-based enhancements (faster, less detailed)'
    )
    
    parser.add_argument(
        '--all-methods',
        action='store_true',
        help='Process all HTTP methods, not just GET (default: GET only)'
    )
    
    parser.add_argument(
        '--indent',
        type=int,
        default=2,
        help='JSON indentation (default: 2)'
    )
    
    parser.add_argument(
        '--associated-docs',
        type=str,
        nargs='+',
        help='URLs to associated API documentation (space-separated)'
    )
    
    parser.add_argument(
        '--filter-tags',
        type=str,
        nargs='+',
        help='Filter endpoints by tags (e.g., --filter-tags Assets Issues Cloud). Only endpoints with matching tags will be processed.'
    )
    
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Disable checkpoint resuming (start fresh, ignoring existing checkpoints)'
    )
    
    args = parser.parse_args()
    
    # Initialize converter
    converter = RealAPIConverter(
        api_token=args.api_token,
        enable_agents=not args.no_agents,
        domain_id=args.domain_id,
        domain_name=args.domain_name
    )
    
    try:
        # Determine input source and convert
        associated_docs = args.associated_docs if args.associated_docs else None
        filter_tags = args.filter_tags if args.filter_tags else None
        
        if args.api:
            if args.api == 'snyk':
                version = args.version or "2025-11-05"  # Default to 2025-11-05 for Snyk API
                mdl = await converter.convert_snyk_api(
                    version=version,
                    catalog=args.catalog,
                    schema=args.schema,
                    output_file=args.output,
                    filter_get_only=not args.all_methods,
                    filter_tags=filter_tags,
                    associated_api_docs=associated_docs,
                    resume=not args.no_resume
                )
            else:
                print(f"❌ Unknown API: {args.api}")
                sys.exit(1)
        elif args.input:
            if args.input.startswith('http://') or args.input.startswith('https://'):
                mdl = await converter.convert_spec_from_url(
                    url=args.input,
                    catalog=args.catalog,
                    schema=args.schema,
                    version=args.version,
                    output_file=args.output,
                    filter_get_only=not args.all_methods,
                    filter_tags=filter_tags,
                    associated_api_docs=associated_docs,
                    resume=not args.no_resume
                )
            else:
                if not os.path.exists(args.input):
                    print(f"❌ Error: File not found: {args.input}")
                    sys.exit(1)
                mdl = await converter.convert_spec_from_file(
                    filepath=args.input,
                    catalog=args.catalog,
                    schema=args.schema,
                    output_file=args.output,
                    filter_get_only=not args.all_methods,
                    filter_tags=filter_tags,
                    associated_api_docs=associated_docs,
                    resume=not args.no_resume
                )
        
        print(f"\n✅ Successfully generated MDL schema: {args.output}")
        print(f"\n📊 Final Summary:")
        print(f"   Models: {len(mdl.get('models', []))}")
        print(f"   Views: {len(mdl.get('views', []))}")
        print(f"   Relationships: {len(mdl.get('relationships', []))}")
        print(f"   Metrics: {len(mdl.get('metrics', []))}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

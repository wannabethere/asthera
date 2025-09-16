"""
Configuration Manager and Client Library
========================================
"""

import os
import json
import yaml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import httpx
import asyncio
from datetime import datetime

# Configuration Management
@dataclass
class PipelineServiceConfig:
    """Configuration for Pipeline Execution Service"""
    
    # Service settings
    base_directory: str = "/tmp/pipeline_executions"
    timeout_seconds: int = 300
    cleanup_after_execution: bool = False
    log_level: str = "INFO"
    
    # Python environment
    python_path_additions: List[str] = field(default_factory=list)
    additional_env_vars: Dict[str, str] = field(default_factory=dict)
    
    # API settings
    api_host: str = "localhost"
    api_port: int = 8000
    api_base_url: Optional[str] = None
    
    # Security
    api_key: Optional[str] = None
    allowed_hosts: List[str] = field(default_factory=lambda: ["localhost", "127.0.0.1"])
    
    # Features
    enable_monitoring: bool = False
    enable_caching: bool = False
    redis_url: Optional[str] = None
    
    def __post_init__(self):
        if self.api_base_url is None:
            self.api_base_url = f"http://{self.api_host}:{self.api_port}"
    
    @classmethod
    def from_env(cls) -> 'PipelineServiceConfig':
        """Create config from environment variables"""
        return cls(
            base_directory=os.getenv("PIPELINE_BASE_DIR", "/tmp/pipeline_executions"),
            timeout_seconds=int(os.getenv("DEFAULT_TIMEOUT", "300")),
            cleanup_after_execution=os.getenv("CLEANUP_AFTER_EXECUTION", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            python_path_additions=os.getenv("ADDITIONAL_PYTHON_PATHS", "").split(":") if os.getenv("ADDITIONAL_PYTHON_PATHS") else [],
            api_host=os.getenv("API_HOST", "localhost"),
            api_port=int(os.getenv("PORT", "8000")),
            api_key=os.getenv("API_KEY"),
            enable_monitoring=os.getenv("ENABLE_MONITORING", "false").lower() == "true",
            enable_caching=os.getenv("ENABLE_CACHING", "false").lower() == "true",
            redis_url=os.getenv("REDIS_URL")
        )
    
    @classmethod
    def from_file(cls, file_path: str) -> 'PipelineServiceConfig':
        """Load config from YAML or JSON file"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {file_path}")
        
        with open(path, 'r') as f:
            if path.suffix.lower() in ['.yml', '.yaml']:
                data = yaml.safe_load(f)
            elif path.suffix.lower() == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported config file format: {path.suffix}")
        
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'base_directory': self.base_directory,
            'timeout_seconds': self.timeout_seconds,
            'cleanup_after_execution': self.cleanup_after_execution,
            'log_level': self.log_level,
            'python_path_additions': self.python_path_additions,
            'additional_env_vars': self.additional_env_vars,
            'api_host': self.api_host,
            'api_port': self.api_port,
            'api_base_url': self.api_base_url,
            'api_key': self.api_key,
            'allowed_hosts': self.allowed_hosts,
            'enable_monitoring': self.enable_monitoring,
            'enable_caching': self.enable_caching,
            'redis_url': self.redis_url
        }
    
    def save_to_file(self, file_path: str):
        """Save config to file"""
        path = Path(file_path)
        data = self.to_dict()
        
        with open(path, 'w') as f:
            if path.suffix.lower() in ['.yml', '.yaml']:
                yaml.dump(data, f, default_flow_style=False)
            elif path.suffix.lower() == '.json':
                json.dump(data, f, indent=2)
            else:
                raise ValueError(f"Unsupported config file format: {path.suffix}")


# Client Library
class PipelineExecutionClient:
    """Client for interacting with Pipeline Execution Service"""
    
    def __init__(self, config: PipelineServiceConfig = None, base_url: str = None):
        """Initialize client"""
        self.config = config or PipelineServiceConfig.from_env()
        self.base_url = base_url or self.config.api_base_url
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.aclose()
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        if not self.session:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get("/health")
        else:
            response = await self.session.get("/health")
        
        response.raise_for_status()
        return response.json()
    
    async def execute_pipeline(self, 
                             code: str,
                             execution_id: Optional[str] = None,
                             additional_env_vars: Optional[Dict[str, str]] = None,
                             additional_python_paths: Optional[List[str]] = None,
                             timeout_seconds: Optional[int] = None) -> Dict[str, Any]:
        """Execute pipeline code synchronously"""
        payload = {
            "code": code,
            "execution_id": execution_id,
            "additional_env_vars": additional_env_vars,
            "additional_python_paths": additional_python_paths,
            "timeout_seconds": timeout_seconds or self.config.timeout_seconds
        }
        
        if not self.session:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=timeout_seconds or 300) as client:
                response = await client.post("/execute", json=payload, headers=self._get_headers())
        else:
            response = await self.session.post("/execute", json=payload, headers=self._get_headers())
        
        response.raise_for_status()
        return response.json()
    
    async def execute_pipeline_async(self, 
                                   code: str,
                                   execution_id: Optional[str] = None,
                                   additional_env_vars: Optional[Dict[str, str]] = None,
                                   additional_python_paths: Optional[List[str]] = None) -> str:
        """Execute pipeline code asynchronously and return execution ID"""
        payload = {
            "code": code,
            "execution_id": execution_id,
            "additional_env_vars": additional_env_vars,
            "additional_python_paths": additional_python_paths
        }
        
        if not self.session:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.post("/execute-async", json=payload, headers=self._get_headers())
        else:
            response = await self.session.post("/execute-async", json=payload, headers=self._get_headers())
        
        response.raise_for_status()
        result = response.json()
        return result["execution_id"]
    
    async def execute_generated_pipeline(self, 
                                       analysis_results: Dict[str, Any],
                                       data_file_path: Optional[str] = None) -> Dict[str, Any]:
        """Execute pipeline from analysis results"""
        payload = {
            "analysis_results": analysis_results,
            "data_file_path": data_file_path
        }
        
        if not self.session:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=300) as client:
                response = await client.post("/execute-generated", json=payload, headers=self._get_headers())
        else:
            response = await self.session.post("/execute-generated", json=payload, headers=self._get_headers())
        
        response.raise_for_status()
        return response.json()
    
    async def get_execution_status(self, execution_id: str) -> Dict[str, Any]:
        """Get execution status"""
        if not self.session:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get(f"/status/{execution_id}")
        else:
            response = await self.session.get(f"/status/{execution_id}")
        
        response.raise_for_status()
        return response.json()
    
    async def get_execution_result(self, execution_id: str) -> Dict[str, Any]:
        """Get execution result"""
        if not self.session:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get(f"/result/{execution_id}")
        else:
            response = await self.session.get(f"/result/{execution_id}")
        
        response.raise_for_status()
        return response.json()
    
    async def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """Cancel execution"""
        if not self.session:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.delete(f"/cancel/{execution_id}")
        else:
            response = await self.session.delete(f"/cancel/{execution_id}")
        
        response.raise_for_status()
        return response.json()
    
    async def list_executions(self) -> Dict[str, Any]:
        """List all executions"""
        if not self.session:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get("/executions")
        else:
            response = await self.session.get("/executions")
        
        response.raise_for_status()
        return response.json()
    
    async def upload_data_file(self, file_path: str) -> Dict[str, Any]:
        """Upload a data file"""
        with open(file_path, "rb") as f:
            files = {"file": (Path(file_path).name, f, "application/octet-stream")}
            
            if not self.session:
                async with httpx.AsyncClient(base_url=self.base_url) as client:
                    response = await client.post("/upload-data", files=files)
            else:
                response = await self.session.post("/upload-data", files=files)
        
        response.raise_for_status()
        return response.json()
    
    async def wait_for_completion(self, 
                                execution_id: str, 
                                poll_interval: float = 2.0,
                                max_wait_time: Optional[float] = None) -> Dict[str, Any]:
        """Wait for execution to complete and return result"""
        start_time = datetime.now()
        
        while True:
            status = await self.get_execution_status(execution_id)
            
            if not status["is_running"]:
                return await self.get_execution_result(execution_id)
            
            # Check timeout
            if max_wait_time:
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > max_wait_time:
                    raise TimeoutError(f"Execution {execution_id} did not complete within {max_wait_time} seconds")
            
            await asyncio.sleep(poll_interval)


# High-level wrapper for easy usage
class PipelineExecutor:
    """High-level wrapper for pipeline execution"""
    
    def __init__(self, config_file: str = None, **config_kwargs):
        """Initialize executor"""
        if config_file:
            self.config = PipelineServiceConfig.from_file(config_file)
        else:
            self.config = PipelineServiceConfig.from_env()
        
        # Override with kwargs
        for key, value in config_kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        
        self.client = PipelineExecutionClient(self.config)
    
    async def run_pipeline(self, 
                          code: str,
                          data_file_path: Optional[str] = None,
                          wait_for_completion: bool = True,
                          **kwargs) -> Dict[str, Any]:
        """Run a pipeline with simplified interface"""
        async with self.client:
            # Upload data file if provided
            if data_file_path and Path(data_file_path).exists():
                upload_result = await self.client.upload_data_file(data_file_path)
                kwargs["additional_env_vars"] = kwargs.get("additional_env_vars", {})
                kwargs["additional_env_vars"]["UPLOADED_DATA_PATH"] = upload_result["file_path"]
            
            if wait_for_completion:
                return await self.client.execute_pipeline(code, **kwargs)
            else:
                execution_id = await self.client.execute_pipeline_async(code, **kwargs)
                return {"execution_id": execution_id, "status": "started"}
    
    async def run_generated_pipeline(self, 
                                   analysis_results: Dict[str, Any],
                                   data_file_path: Optional[str] = None) -> Dict[str, Any]:
        """Run a generated pipeline"""
        async with self.client:
            return await self.client.execute_generated_pipeline(analysis_results, data_file_path)


# Example usage and testing
async def example_usage():
    """Example usage of the client library"""
    
    # Configuration
    config = PipelineServiceConfig(
        api_host="localhost",
        api_port=8000,
        timeout_seconds=300
    )
    
    # Example pipeline code
    pipeline_code = '''
import pandas as pd
import numpy as np

def main():
    print("Running example pipeline...")
    
    # Create some sample data
    data = {
        'date': pd.date_range('2024-01-01', periods=100),
        'value': np.random.randn(100).cumsum()
    }
    df = pd.DataFrame(data)
    
    # Simple analysis
    print(f"Data shape: {df.shape}")
    print(f"Mean value: {df['value'].mean():.2f}")
    print(f"Std value: {df['value'].std():.2f}")
    
    return {"status": "success", "mean": df['value'].mean()}

if __name__ == "__main__":
    result = main()
    print(f"Pipeline result: {result}")
'''
    
    # Using the client directly
    async with PipelineExecutionClient(config) as client:
        # Check health
        health = await client.health_check()
        print(f"Service health: {health}")
        
        # Execute pipeline
        result = await client.execute_pipeline(pipeline_code)
        print(f"Execution result: {result}")
    
    # Using the high-level executor
    executor = PipelineExecutor()
    result = await executor.run_pipeline(pipeline_code)
    print(f"Executor result: {result}")


if __name__ == "__main__":
    asyncio.run(example_usage())


# Sample configuration files

# config.yaml
SAMPLE_CONFIG_YAML = """
# Pipeline Service Configuration
base_directory: "/app/pipeline_executions"
timeout_seconds: 300
cleanup_after_execution: false
log_level: "INFO"

# Python environment
python_path_additions:
  - "/app"
  - "/app/ml_tools"
  - "/app/app"

additional_env_vars:
  ML_BACKEND: "sklearn"
  DATA_PROCESSING_MODE: "batch"

# API settings
api_host: "localhost"
api_port: 8000

# Security
api_key: null
allowed_hosts:
  - "localhost"
  - "127.0.0.1"
  - "0.0.0.0"

# Features
enable_monitoring: false
enable_caching: false
redis_url: null
"""

# Save sample config
def create_sample_config(file_path: str = "config.yaml"):
    """Create a sample configuration file"""
    with open(file_path, 'w') as f:
        f.write(SAMPLE_CONFIG_YAML)
    print(f"Sample configuration saved to: {file_path}")
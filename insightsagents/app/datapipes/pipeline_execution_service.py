"""
Pipeline Execution Service
==========================
A service that saves generated pipeline code, sets up the environment, and executes the scripts.
"""

import os
import sys
import subprocess
import tempfile
import shutil
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid
import asyncio
from dataclasses import dataclass
from enum import Enum


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ExecutionResult:
    """Result of pipeline execution"""
    execution_id: str
    status: ExecutionStatus
    start_time: datetime
    end_time: Optional[datetime]
    output: str
    error: str
    exit_code: Optional[int]
    file_path: str
    duration: Optional[float] = None


class PipelineExecutionService:
    """Service for executing generated pipeline code"""
    
    def __init__(self, 
                 base_directory: str = "/tmp/pipeline_executions",
                 python_path_additions: List[str] = None,
                 timeout_seconds: int = 300,
                 cleanup_after_execution: bool = False,
                 log_level: str = "INFO"):
        """
        Initialize the Pipeline Execution Service
        
        Args:
            base_directory: Base directory for saving pipeline files
            python_path_additions: Additional paths to add to PYTHONPATH
            timeout_seconds: Maximum execution time before timeout
            cleanup_after_execution: Whether to clean up files after execution
            log_level: Logging level
        """
        self.base_directory = Path(base_directory)
        self.python_path_additions = python_path_additions or []
        self.timeout_seconds = timeout_seconds
        self.cleanup_after_execution = cleanup_after_execution
        
        # Setup logging
        logging.basicConfig(level=getattr(logging, log_level.upper()))
        self.logger = logging.getLogger(__name__)
        
        # Create base directory if it doesn't exist
        self.base_directory.mkdir(parents=True, exist_ok=True)
        
        # Track running executions
        self.running_executions: Dict[str, subprocess.Popen] = {}
    
    def save_pipeline_code(self, 
                          code: str, 
                          execution_id: str = None,
                          filename: str = None) -> str:
        """
        Save pipeline code to a file
        
        Args:
            code: The Python code to save
            execution_id: Unique execution ID (generated if not provided)
            filename: Custom filename (generated if not provided)
            
        Returns:
            Path to the saved file
        """
        if execution_id is None:
            execution_id = str(uuid.uuid4())
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"pipeline_{execution_id[:8]}_{timestamp}.py"
        
        # Create execution directory
        execution_dir = self.base_directory / execution_id
        execution_dir.mkdir(parents=True, exist_ok=True)
        
        # Save the code
        file_path = execution_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        self.logger.info(f"Pipeline code saved to: {file_path}")
        return str(file_path)
    
    def setup_environment(self, additional_paths: List[str] = None) -> Dict[str, str]:
        """
        Setup the execution environment with proper PYTHONPATH
        
        Args:
            additional_paths: Additional paths to add for this execution
            
        Returns:
            Environment dictionary
        """
        env = os.environ.copy()
        
        # Build PYTHONPATH
        python_paths = []
        
        # Add current PYTHONPATH if it exists
        if 'PYTHONPATH' in env:
            python_paths.append(env['PYTHONPATH'])
        
        # Add configured additional paths
        python_paths.extend(self.python_path_additions)
        
        # Add execution-specific paths
        if additional_paths:
            python_paths.extend(additional_paths)
        
        # Set PYTHONPATH
        if python_paths:
            env['PYTHONPATH'] = os.pathsep.join(python_paths)
            self.logger.info(f"PYTHONPATH set to: {env['PYTHONPATH']}")
        
        return env
    
    async def execute_pipeline(self, 
                              code: str,
                              execution_id: str = None,
                              data_file_path: str = None,
                              additional_env_vars: Dict[str, str] = None,
                              additional_python_paths: List[str] = None) -> ExecutionResult:
        """
        Execute a pipeline code asynchronously
        
        Args:
            code: The Python code to execute
            execution_id: Unique execution ID
            data_file_path: Path to data file (if needed)
            additional_env_vars: Additional environment variables
            additional_python_paths: Additional Python paths for this execution
            
        Returns:
            ExecutionResult object
        """
        if execution_id is None:
            execution_id = str(uuid.uuid4())
        
        start_time = datetime.now()
        self.logger.info(f"Starting execution {execution_id}")
        
        try:
            # Save the code
            file_path = self.save_pipeline_code(code, execution_id)
            
            # Setup environment
            env = self.setup_environment(additional_python_paths)
            
            # Add additional environment variables
            if additional_env_vars:
                env.update(additional_env_vars)
            
            # Add data file path if provided
            if data_file_path:
                env['DATA_FILE_PATH'] = data_file_path
            
            # Execute the script
            result = await self._run_script(file_path, env, execution_id, start_time)
            
            # Cleanup if requested
            if self.cleanup_after_execution:
                self._cleanup_execution(execution_id)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error executing pipeline {execution_id}: {str(e)}")
            end_time = datetime.now()
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                output="",
                error=str(e),
                exit_code=None,
                file_path="",
                duration=(end_time - start_time).total_seconds()
            )
    
    async def _run_script(self, 
                         file_path: str, 
                         env: Dict[str, str], 
                         execution_id: str,
                         start_time: datetime) -> ExecutionResult:
        """
        Run the Python script with proper error handling and timeout
        """
        try:
            # Create the subprocess
            process = await asyncio.create_subprocess_exec(
                sys.executable, file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(Path(file_path).parent)
            )
            
            # Store the process for potential cancellation
            self.running_executions[execution_id] = process
            
            try:
                # Wait for completion with timeout
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=self.timeout_seconds
                )
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # Determine status based on exit code
                status = ExecutionStatus.COMPLETED if process.returncode == 0 else ExecutionStatus.FAILED
                
                result = ExecutionResult(
                    execution_id=execution_id,
                    status=status,
                    start_time=start_time,
                    end_time=end_time,
                    output=stdout.decode('utf-8') if stdout else "",
                    error=stderr.decode('utf-8') if stderr else "",
                    exit_code=process.returncode,
                    file_path=file_path,
                    duration=duration
                )
                
                self.logger.info(f"Execution {execution_id} completed with status: {status}")
                return result
                
            except asyncio.TimeoutError:
                # Handle timeout
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                self.logger.warning(f"Execution {execution_id} timed out after {duration} seconds")
                
                return ExecutionResult(
                    execution_id=execution_id,
                    status=ExecutionStatus.TIMEOUT,
                    start_time=start_time,
                    end_time=end_time,
                    output="",
                    error=f"Execution timed out after {self.timeout_seconds} seconds",
                    exit_code=None,
                    file_path=file_path,
                    duration=duration
                )
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.logger.error(f"Error running script {execution_id}: {str(e)}")
            
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                output="",
                error=str(e),
                exit_code=None,
                file_path=file_path,
                duration=duration
            )
        
        finally:
            # Clean up tracking
            if execution_id in self.running_executions:
                del self.running_executions[execution_id]
    
    def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution
        
        Args:
            execution_id: ID of the execution to cancel
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        if execution_id in self.running_executions:
            process = self.running_executions[execution_id]
            try:
                process.terminate()
                self.logger.info(f"Cancelled execution {execution_id}")
                return True
            except Exception as e:
                self.logger.error(f"Error cancelling execution {execution_id}: {str(e)}")
                return False
        return False
    
    def _cleanup_execution(self, execution_id: str):
        """Clean up files for a completed execution"""
        execution_dir = self.base_directory / execution_id
        if execution_dir.exists():
            shutil.rmtree(execution_dir)
            self.logger.info(f"Cleaned up execution directory: {execution_dir}")
    
    def get_execution_logs(self, execution_id: str) -> Optional[str]:
        """Get logs for a specific execution"""
        log_file = self.base_directory / execution_id / "execution.log"
        if log_file.exists():
            with open(log_file, 'r') as f:
                return f.read()
        return None
    
    def list_executions(self) -> List[str]:
        """List all execution directories"""
        if not self.base_directory.exists():
            return []
        return [d.name for d in self.base_directory.iterdir() if d.is_dir()]


# Example usage and API wrapper
class PipelineExecutionAPI:
    """REST API wrapper for the Pipeline Execution Service"""
    
    def __init__(self, service: PipelineExecutionService):
        self.service = service
    
    async def execute_generated_pipeline(self, 
                                       analysis_results: Dict[str, Any],
                                       data_file_path: str = None) -> ExecutionResult:
        """
        Execute a pipeline from analysis results
        
        Args:
            analysis_results: Results from the code generation pipeline
            data_file_path: Path to the data file
            
        Returns:
            ExecutionResult object
        """
        if "generated_code" not in analysis_results:
            raise ValueError("No generated code found in analysis results")
        
        code = analysis_results["generated_code"]
        execution_id = str(uuid.uuid4())
        
        # Add any additional environment setup based on the analysis
        additional_env_vars = {
            "PIPELINE_ANALYSIS_TYPE": analysis_results.get("analysis_type", "unknown"),
            "PIPELINE_GENERATION_TIME": str(datetime.now().isoformat())
        }
        
        return await self.service.execute_pipeline(
            code=code,
            execution_id=execution_id,
            data_file_path=data_file_path,
            additional_env_vars=additional_env_vars
        )


# Example usage
async def main():
    """Example usage of the Pipeline Execution Service"""
    
    # Initialize the service
    service = PipelineExecutionService(
        base_directory="/tmp/pipeline_executions",
        python_path_additions=[
            "/path/to/your/ml/tools",  # Add path to your ML tools
            "/path/to/app"  # Add app path
        ],
        timeout_seconds=300,
        cleanup_after_execution=False
    )
    
    # Example generated code (from your document)
    generated_code = '''
"""
Generated Pipeline Code
Analysis: anomaly_detection
Question: Find anomalies in daily spending patterns
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Your generated pipeline code here
def run_generated_pipeline(df):
    """Execute the generated pipeline"""
    try:
        print("Pipeline executed successfully!")
        return {"status": "success", "message": "Anomaly detection completed"}
    except Exception as e:
        print(f"Error running pipeline: {e}")
        return None

if __name__ == "__main__":
    print("Starting pipeline execution...")
    result = run_generated_pipeline(None)
    print(f"Result: {result}")
'''
    
    # Execute the pipeline
    result = await service.execute_pipeline(
        code=generated_code,
        data_file_path="/path/to/your/data.csv"
    )
    
    print(f"Execution ID: {result.execution_id}")
    print(f"Status: {result.status}")
    print(f"Duration: {result.duration} seconds")
    print(f"Output: {result.output}")
    if result.error:
        print(f"Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
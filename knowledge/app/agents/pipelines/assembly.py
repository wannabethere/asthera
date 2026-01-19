"""
Pipeline Assembly Architecture

A general-purpose pipeline orchestration system that allows composing
multiple pipelines together in a reusable way. This enables:
- Chaining pipelines together
- Parallel execution of pipelines
- Conditional routing based on results
- Pipeline composition for integration/assembly

This architecture can be used by any service that needs to orchestrate
multiple pipelines, such as contextual assistants, integration services, etc.
"""
import logging
from typing import Any, Dict, Optional, Callable, List, Union, Literal
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field

from .base import ExtractionPipeline

logger = logging.getLogger(__name__)


class PipelineExecutionMode(str, Enum):
    """Execution modes for pipeline assembly"""
    SEQUENTIAL = "sequential"  # Execute pipelines one after another
    PARALLEL = "parallel"  # Execute pipelines in parallel
    CONDITIONAL = "conditional"  # Execute pipelines based on conditions


@dataclass
class PipelineStep:
    """Represents a single pipeline step in an assembly"""
    pipeline: ExtractionPipeline
    step_id: str
    step_name: str
    description: Optional[str] = None
    input_mapper: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    output_mapper: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    required: bool = True  # If False, step can be skipped on failure
    retry_count: int = 0  # Number of retries on failure
    timeout: Optional[float] = None  # Timeout in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineAssemblyConfig:
    """Configuration for pipeline assembly"""
    assembly_id: str
    assembly_name: str
    description: Optional[str] = None
    execution_mode: PipelineExecutionMode = PipelineExecutionMode.SEQUENTIAL
    max_concurrent: int = 5  # For parallel execution
    error_handling: Literal["stop", "continue", "skip"] = "stop"
    result_aggregator: Optional[Callable[[List[Dict[str, Any]]], Dict[str, Any]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PipelineAssembly(ExtractionPipeline):
    """
    General-purpose pipeline assembly/orchestration system.
    
    Allows composing multiple pipelines together in various execution modes:
    - Sequential: Execute pipelines one after another, passing results forward
    - Parallel: Execute pipelines simultaneously, aggregate results
    - Conditional: Execute pipelines based on conditions
    
    Example:
        assembly = PipelineAssembly(
            config=PipelineAssemblyConfig(
                assembly_id="contextual_reasoning_assembly",
                assembly_name="Contextual Reasoning Assembly",
                execution_mode=PipelineExecutionMode.SEQUENTIAL
            )
        )
        
        assembly.add_step(
            PipelineStep(
                pipeline=retrieval_pipeline,
                step_id="retrieve_context",
                step_name="Context Retrieval"
            )
        )
        
        assembly.add_step(
            PipelineStep(
                pipeline=reasoning_pipeline,
                step_id="reason",
                step_name="Contextual Reasoning",
                input_mapper=lambda state: {
                    "query": state.get("query"),
                    "context_id": state.get("context_ids", [None])[0]
                }
            )
        )
        
        result = await assembly.run(inputs={"query": "..."})
    """
    
    def __init__(
        self,
        config: PipelineAssemblyConfig,
        **kwargs
    ):
        """
        Initialize pipeline assembly
        
        Args:
            config: Assembly configuration
            **kwargs: Additional arguments passed to base class
        """
        super().__init__(
            name=config.assembly_name,
            version="1.0.0",
            description=config.description or f"Pipeline assembly: {config.assembly_name}",
            **kwargs
        )
        self.config = config
        self.steps: List[PipelineStep] = []
        self._step_map: Dict[str, PipelineStep] = {}
    
    def add_step(self, step: PipelineStep) -> "PipelineAssembly":
        """
        Add a pipeline step to the assembly
        
        Args:
            step: Pipeline step to add
            
        Returns:
            Self for method chaining
        """
        if step.step_id in self._step_map:
            raise ValueError(f"Step with id '{step.step_id}' already exists")
        
        self.steps.append(step)
        self._step_map[step.step_id] = step
        logger.info(f"Added step '{step.step_id}' ({step.step_name}) to assembly '{self.config.assembly_id}'")
        return self
    
    def remove_step(self, step_id: str) -> "PipelineAssembly":
        """
        Remove a pipeline step from the assembly
        
        Args:
            step_id: ID of step to remove
            
        Returns:
            Self for method chaining
        """
        if step_id not in self._step_map:
            raise ValueError(f"Step with id '{step_id}' not found")
        
        step = self._step_map[step_id]
        self.steps.remove(step)
        del self._step_map[step_id]
        logger.info(f"Removed step '{step_id}' from assembly '{self.config.assembly_id}'")
        return self
    
    def get_step(self, step_id: str) -> Optional[PipelineStep]:
        """Get a step by ID"""
        return self._step_map.get(step_id)
    
    async def initialize(self, **kwargs) -> None:
        """Initialize all pipelines in the assembly"""
        await super().initialize(**kwargs)
        
        logger.info(f"Initializing {len(self.steps)} pipeline steps...")
        for step in self.steps:
            try:
                if not step.pipeline.is_initialized:
                    await step.pipeline.initialize(**kwargs)
                    logger.info(f"  ✓ Initialized step '{step.step_id}'")
                else:
                    logger.info(f"  - Step '{step.step_id}' already initialized")
            except Exception as e:
                logger.error(f"  ✗ Failed to initialize step '{step.step_id}': {str(e)}")
                if step.required:
                    raise
        
        logger.info(f"Assembly '{self.config.assembly_id}' initialized")
    
    async def run(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        configuration: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the pipeline assembly
        
        Args:
            inputs: Input data for the assembly
            status_callback: Optional callback for status updates
            configuration: Optional configuration overrides
            **kwargs: Additional parameters
            
        Returns:
            Dictionary with assembly results
        """
        if not self._is_initialized:
            await self.initialize()
        
        if status_callback:
            status_callback("assembly_started", {
                "assembly_id": self.config.assembly_id,
                "step_count": len(self.steps),
                "execution_mode": self.config.execution_mode.value
            })
        
        try:
            if self.config.execution_mode == PipelineExecutionMode.SEQUENTIAL:
                result = await self._run_sequential(inputs, status_callback, **kwargs)
            elif self.config.execution_mode == PipelineExecutionMode.PARALLEL:
                result = await self._run_parallel(inputs, status_callback, **kwargs)
            elif self.config.execution_mode == PipelineExecutionMode.CONDITIONAL:
                result = await self._run_conditional(inputs, status_callback, **kwargs)
            else:
                raise ValueError(f"Unknown execution mode: {self.config.execution_mode}")
            
            # Aggregate results if aggregator provided
            if self.config.result_aggregator and isinstance(result, dict) and "step_results" in result:
                aggregated = self.config.result_aggregator(result["step_results"])
                result["aggregated"] = aggregated
            
            if status_callback:
                status_callback("assembly_completed", {
                    "assembly_id": self.config.assembly_id,
                    "success": True
                })
            
            return {
                "success": True,
                "assembly_id": self.config.assembly_id,
                "data": result
            }
            
        except Exception as e:
            logger.error(f"Assembly execution failed: {str(e)}", exc_info=True)
            if status_callback:
                status_callback("assembly_error", {
                    "assembly_id": self.config.assembly_id,
                    "error": str(e)
                })
            
            return {
                "success": False,
                "error": str(e),
                "assembly_id": self.config.assembly_id
            }
    
    async def _run_sequential(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute pipelines sequentially, passing results forward"""
        current_state = inputs.copy()
        step_results = []
        
        for i, step in enumerate(self.steps):
            # Check condition if provided
            if step.condition and not step.condition(current_state):
                logger.info(f"Skipping step '{step.step_id}' due to condition")
                continue
            
            if status_callback:
                status_callback("step_started", {
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "step_index": i,
                    "total_steps": len(self.steps)
                })
            
            try:
                # Map inputs for this step
                step_inputs = current_state
                if step.input_mapper:
                    step_inputs = step.input_mapper(current_state)
                
                # Execute step
                step_result = await self._execute_step_with_retry(step, step_inputs, **kwargs)
                
                # Map outputs
                if step.output_mapper:
                    step_result = step.output_mapper(step_result)
                
                # Merge results into current state
                if isinstance(step_result, dict):
                    if "data" in step_result:
                        current_state.update(step_result["data"])
                    else:
                        current_state.update(step_result)
                
                step_results.append({
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "success": True,
                    "result": step_result
                })
                
                if status_callback:
                    status_callback("step_completed", {
                        "step_id": step.step_id,
                        "step_name": step.step_name,
                        "step_index": i
                    })
                
            except Exception as e:
                logger.error(f"Step '{step.step_id}' failed: {str(e)}", exc_info=True)
                
                step_results.append({
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "success": False,
                    "error": str(e)
                })
                
                if step.required:
                    if self.config.error_handling == "stop":
                        raise
                    elif self.config.error_handling == "skip":
                        continue
                    # "continue" means continue but mark as failed
                else:
                    logger.warning(f"Step '{step.step_id}' failed but is not required, continuing...")
        
        return {
            "final_state": current_state,
            "step_results": step_results,
            "steps_executed": len(step_results)
        }
    
    async def _run_parallel(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute pipelines in parallel"""
        import asyncio
        
        async def execute_step_async(step: PipelineStep, index: int):
            """Execute a single step asynchronously"""
            try:
                # Check condition
                if step.condition and not step.condition(inputs):
                    return {
                        "step_id": step.step_id,
                        "step_name": step.step_name,
                        "success": False,
                        "skipped": True,
                        "reason": "condition_not_met"
                    }
                
                if status_callback:
                    status_callback("step_started", {
                        "step_id": step.step_id,
                        "step_name": step.step_name,
                        "step_index": index
                    })
                
                # Map inputs
                step_inputs = inputs
                if step.input_mapper:
                    step_inputs = step.input_mapper(inputs)
                
                # Execute
                step_result = await self._execute_step_with_retry(step, step_inputs, **kwargs)
                
                # Map outputs
                if step.output_mapper:
                    step_result = step.output_mapper(step_result)
                
                if status_callback:
                    status_callback("step_completed", {
                        "step_id": step.step_id,
                        "step_name": step.step_name
                    })
                
                return {
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "success": True,
                    "result": step_result
                }
                
            except Exception as e:
                logger.error(f"Step '{step.step_id}' failed: {str(e)}", exc_info=True)
                return {
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "success": False,
                    "error": str(e)
                }
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def execute_with_semaphore(step, index):
            async with semaphore:
                return await execute_step_async(step, index)
        
        # Execute all steps in parallel
        tasks = [execute_with_semaphore(step, i) for i, step in enumerate(self.steps)]
        step_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for result in step_results:
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        # Merge all successful results
        final_state = inputs.copy()
        for result in processed_results:
            if result.get("success") and "result" in result:
                result_data = result["result"]
                if isinstance(result_data, dict):
                    if "data" in result_data:
                        final_state.update(result_data["data"])
                    else:
                        final_state.update(result_data)
        
        return {
            "final_state": final_state,
            "step_results": processed_results,
            "steps_executed": len(processed_results)
        }
    
    async def _run_conditional(
        self,
        inputs: Dict[str, Any],
        status_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute pipelines based on conditions"""
        current_state = inputs.copy()
        step_results = []
        
        for i, step in enumerate(self.steps):
            # Check condition
            should_execute = True
            if step.condition:
                should_execute = step.condition(current_state)
            
            if not should_execute:
                logger.info(f"Skipping step '{step.step_id}' due to condition")
                step_results.append({
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "success": False,
                    "skipped": True,
                    "reason": "condition_not_met"
                })
                continue
            
            if status_callback:
                status_callback("step_started", {
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "step_index": i
                })
            
            try:
                # Map inputs
                step_inputs = current_state
                if step.input_mapper:
                    step_inputs = step.input_mapper(current_state)
                
                # Execute
                step_result = await self._execute_step_with_retry(step, step_inputs, **kwargs)
                
                # Map outputs
                if step.output_mapper:
                    step_result = step.output_mapper(step_result)
                
                # Merge results
                if isinstance(step_result, dict):
                    if "data" in step_result:
                        current_state.update(step_result["data"])
                    else:
                        current_state.update(step_result)
                
                step_results.append({
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "success": True,
                    "result": step_result
                })
                
                if status_callback:
                    status_callback("step_completed", {
                        "step_id": step.step_id,
                        "step_name": step.step_name
                    })
                
            except Exception as e:
                logger.error(f"Step '{step.step_id}' failed: {str(e)}", exc_info=True)
                step_results.append({
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "success": False,
                    "error": str(e)
                })
                
                if step.required and self.config.error_handling == "stop":
                    raise
        
        return {
            "final_state": current_state,
            "step_results": step_results,
            "steps_executed": len([r for r in step_results if not r.get("skipped", False)])
        }
    
    async def _execute_step_with_retry(
        self,
        step: PipelineStep,
        inputs: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a step with retry logic"""
        import asyncio
        
        last_error = None
        for attempt in range(step.retry_count + 1):
            try:
                if step.timeout:
                    result = await asyncio.wait_for(
                        step.pipeline.run(inputs=inputs, **kwargs),
                        timeout=step.timeout
                    )
                else:
                    result = await step.pipeline.run(inputs=inputs, **kwargs)
                
                return result
                
            except Exception as e:
                last_error = e
                if attempt < step.retry_count:
                    logger.warning(f"Step '{step.step_id}' failed (attempt {attempt + 1}/{step.retry_count + 1}), retrying...")
                    await asyncio.sleep(1)  # Brief delay before retry
                else:
                    logger.error(f"Step '{step.step_id}' failed after {step.retry_count + 1} attempts")
        
        raise last_error
    
    async def cleanup(self) -> None:
        """Clean up all pipelines in the assembly"""
        logger.info(f"Cleaning up assembly '{self.config.assembly_id}'...")
        
        for step in self.steps:
            try:
                await step.pipeline.cleanup()
                logger.info(f"  ✓ Cleaned up step '{step.step_id}'")
            except Exception as e:
                logger.error(f"  ✗ Error cleaning up step '{step.step_id}': {str(e)}")
        
        await super().cleanup()
        logger.info(f"Assembly '{self.config.assembly_id}' cleanup complete")


def create_contextual_reasoning_assembly(
    retrieval_pipeline: ExtractionPipeline,
    reasoning_pipeline: ExtractionPipeline,
    assembly_id: str = "contextual_reasoning_assembly",
    **kwargs
) -> PipelineAssembly:
    """
    Factory function to create a contextual reasoning assembly
    
    This is a common pattern: retrieve contexts, then reason with them.
    
    Args:
        retrieval_pipeline: ContextualGraphRetrievalPipeline instance
        reasoning_pipeline: ContextualGraphReasoningPipeline instance
        assembly_id: ID for the assembly
        **kwargs: Additional arguments for PipelineAssemblyConfig
        
    Returns:
        Configured PipelineAssembly
    """
    config = PipelineAssemblyConfig(
        assembly_id=assembly_id,
        assembly_name="Contextual Reasoning Assembly",
        description="Assembles context retrieval and reasoning pipelines",
        execution_mode=PipelineExecutionMode.SEQUENTIAL,
        **kwargs
    )
    
    assembly = PipelineAssembly(config=config)
    
    # Step 1: Context Retrieval
    assembly.add_step(
        PipelineStep(
            pipeline=retrieval_pipeline,
            step_id="retrieve_context",
            step_name="Context Retrieval",
            description="Retrieve relevant contexts from contextual graph",
            input_mapper=lambda state: {
                "query": state.get("query", ""),
                "context_ids": state.get("context_ids"),
                "include_all_contexts": state.get("include_all_contexts", True),
                "top_k": state.get("top_k", 5),
                "filters": state.get("filters")
            },
            output_mapper=lambda result: {
                "context_ids": result.get("data", {}).get("context_ids", []),
                "context_metadata": result.get("data", {}).get("contexts", []),
                "reasoning_plan": result.get("data", {}).get("reasoning_plan")
            }
        )
    )
    
    # Step 2: Contextual Reasoning
    assembly.add_step(
        PipelineStep(
            pipeline=reasoning_pipeline,
            step_id="reason",
            step_name="Contextual Reasoning",
            description="Perform context-aware reasoning",
            input_mapper=lambda state: {
                "query": state.get("query", ""),
                "context_id": state.get("context_ids", [None])[0] if state.get("context_ids") else None,
                "reasoning_plan": state.get("reasoning_plan"),
                "max_hops": state.get("max_hops", 3),
                "reasoning_type": state.get("reasoning_type", "multi_hop")
            },
            output_mapper=lambda result: {
                "reasoning_result": result.get("data", {}),
                "reasoning_path": result.get("data", {}).get("reasoning_path", [])
            },
            condition=lambda state: bool(state.get("context_ids"))
        )
    )
    
    return assembly


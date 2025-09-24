"""
Enhanced Function Retrieval Service

This module provides an enhanced function retrieval system that efficiently matches
analysis functions to specific steps in reasoning plans using ChromaDB and LLM-based matching.

Key improvements:
1. Batch ChromaDB retrieval using comprehensive context
2. LLM-based function-to-step matching
3. Efficient caching and error handling
4. Fallback mechanisms for robustness
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from langfuse.decorators import observe
from pydantic import BaseModel

from app.agents.retrieval.retrieval_helper import RetrievalHelper

logger = logging.getLogger("enhanced-function-retrieval")


class FunctionMatch(BaseModel):
    """Model for function match results"""
    function_name: str
    pipe_name: str
    description: str
    usage_description: str
    relevance_score: float
    reasoning: str
    category: str = "unknown"
    function_definition: Optional[Dict[str, Any]] = None
    examples: Optional[List[Dict[str, Any]]] = None
    instructions: Optional[List[Dict[str, Any]]] = None
    examples_store: Optional[List[Dict[str, Any]]] = None
    historical_rules: Optional[List[Dict[str, Any]]] = None


class StepFunctionMatch(BaseModel):
    """Model for step-function matching results"""
    step_number: int
    step_title: str
    matched_functions: List[FunctionMatch]
    total_relevance_score: float


class EnhancedFunctionRetrievalResult(BaseModel):
    """Result model for enhanced function retrieval"""
    step_matches: Dict[int, List[Dict[str, Any]]]
    total_functions_retrieved: int
    total_steps_covered: int
    average_relevance_score: float
    confidence_score: float
    reasoning: str
    fallback_used: bool = False


class EnhancedFunctionRetrieval:
    """
    Enhanced function retrieval system that efficiently matches functions to analysis steps
    using ChromaDB and LLM-based matching.
    """
    
    def __init__(self, llm, retrieval_helper: Optional[RetrievalHelper] = None):
        """
        Initialize the Enhanced Function Retrieval system
        
        Args:
            llm: LangChain LLM instance
            retrieval_helper: RetrievalHelper instance for accessing function definitions
        """
        self.llm = llm
        self.retrieval_helper = retrieval_helper or RetrievalHelper()
    
    async def retrieve_and_match_functions(
        self,
        reasoning_plan: List[Dict[str, Any]],
        question: str,
        rephrased_question: str,
        dataframe_description: str,
        dataframe_summary: str,
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> EnhancedFunctionRetrievalResult:
        """
        Main method to retrieve and match functions to analysis steps
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            question: Original user question
            rephrased_question: Rephrased question from Step 1
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns
            project_id: Optional project ID
            
        Returns:
            EnhancedFunctionRetrievalResult with step-function matches
        """
        try:
            logger.info("Starting enhanced function retrieval and matching...")
            
            # Step 1: Fetch relevant functions from ChromaDB
            relevant_functions = await self._fetch_relevant_functions_from_chromadb(
                reasoning_plan=reasoning_plan,
                question=question,
                rephrased_question=rephrased_question,
                dataframe_description=dataframe_description,
                dataframe_summary=dataframe_summary,
                available_columns=available_columns,
                project_id=project_id
            )
            
            if not relevant_functions:
                logger.warning("No relevant functions found in ChromaDB")
                return self._create_empty_result("No relevant functions found")
            
            # Step 2: Enrich functions with context (examples, instructions, etc.)
            enriched_functions = []
            for func in relevant_functions:
                enriched_func = await self._enrich_function_with_context(
                    function_data=func,
                    question=question,
                    project_id=project_id
                )
                enriched_functions.append(enriched_func)
            
            # Step 3: Match functions to steps using LLM
            step_function_matches = await self._match_functions_to_steps_with_llm(
                reasoning_plan=reasoning_plan,
                relevant_functions=enriched_functions,
                question=question,
                dataframe_description=dataframe_description,
                available_columns=available_columns
            )
            
            # Step 4: Calculate metrics and create result
            result = self._create_result_from_matches(
                step_function_matches=step_function_matches,
                total_functions=len(enriched_functions),
                reasoning_plan=reasoning_plan,
                fallback_used=False
            )
            
            logger.info(f"Enhanced function retrieval completed successfully")
            logger.info(f"  - Retrieved {len(relevant_functions)} functions")
            logger.info(f"  - Matched to {len(step_function_matches)} steps")
            logger.info(f"  - Average relevance score: {result.average_relevance_score:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in enhanced function retrieval: {e}")
            return self._create_empty_result(f"Error: {str(e)}", fallback_used=True)
    
    async def _fetch_relevant_functions_from_chromadb(
        self,
        reasoning_plan: List[Dict[str, Any]],
        question: str,
        rephrased_question: str,
        dataframe_description: str,
        dataframe_summary: str,
        available_columns: List[str],
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant functions from ChromaDB using comprehensive context.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            question: Original user question
            rephrased_question: Rephrased question from Step 1
            dataframe_description: Description of the dataframe
            dataframe_summary: Summary of the dataframe
            available_columns: List of available columns
            project_id: Optional project ID
            
        Returns:
            List of relevant function definitions from ChromaDB
        """
        try:
            if not self.retrieval_helper:
                logger.warning("RetrievalHelper not available")
                return []
            
            # Create a comprehensive query that includes the reasoning plan
            plan_context = "\n".join([
                f"Step {step.get('step_number', i+1)}: {step.get('step_title', '')} - {step.get('step_description', '')}"
                for i, step in enumerate(reasoning_plan)
            ])
            
            # Combine all context for a comprehensive search
            comprehensive_query = f"""
            User Question: {question}
            Rephrased Question: {rephrased_question}
            Dataframe Description: {dataframe_description}
            Available Columns: {', '.join(available_columns)}
            
            Analysis Plan:
            {plan_context}
            """
            
            logger.info(f"Fetching functions from ChromaDB with comprehensive query")
            
            # Fetch multiple relevant functions from ChromaDB
            all_functions = []
            
            # Try different search strategies to get comprehensive results
            search_queries = [
                comprehensive_query,
                rephrased_question,
                plan_context,
                question
            ]
            
            # Also add individual step queries for more targeted results
            for step in reasoning_plan:
                step_query = f"{step.get('step_title', '')} {step.get('step_description', '')}"
                if step_query.strip():
                    search_queries.append(step_query)
            
            # Add column-specific queries
            if available_columns:
                column_query = f"functions for columns: {', '.join(available_columns[:5])}"  # Limit to first 5 columns
                search_queries.append(column_query)
            
            logger.info(f"Using {len(search_queries)} different search queries for comprehensive retrieval")
            
            for i, query in enumerate(search_queries):
                try:
                    # Use the retrieval helper to get function definitions
                    function_result = await self.retrieval_helper.get_function_definition_by_query(
                        query=query,
                        similarity_threshold=0.5,  # Lower threshold to get more candidates
                        top_k=15  # Increased from 10 to get more results
                    )
                    
                    if function_result:
                        # Handle both single function and multiple functions
                        if function_result.get("function_definitions"):
                            # Multiple functions returned
                            for func in function_result["function_definitions"]:
                                if func:
                                    all_functions.append(func)
                                    logger.info(f"Query {i+1}: Found function: {func.get('function_name', 'unknown')} (score: {func.get('relevance_score', 0.0):.2f})")
                        elif function_result.get("function_definition"):
                            # Single function returned
                            all_functions.append(function_result["function_definition"])
                            logger.info(f"Query {i+1}: Found function: {function_result['function_definition'].get('function_name', 'unknown')}")
                        elif isinstance(function_result, list):
                            # Legacy format - list of functions
                            for func in function_result:
                                if func and func.get("function_definition"):
                                    all_functions.append(func["function_definition"])
                                    logger.info(f"Query {i+1}: Found function: {func['function_definition'].get('function_name', 'unknown')}")
                    
                except Exception as e:
                    logger.warning(f"Failed to fetch functions with query {i+1} '{query[:50]}...': {e}")
                    continue
            
            # Remove duplicates based on function name and keep the best version
            unique_functions = {}
            for func in all_functions:
                func_name = func.get("function_name", "")
                if func_name:
                    # Keep the function with the highest relevance score if we have duplicates
                    if func_name not in unique_functions:
                        unique_functions[func_name] = func
                    else:
                        # Compare relevance scores if available
                        current_score = func.get("relevance_score", 0.0)
                        existing_score = unique_functions[func_name].get("relevance_score", 0.0)
                        if current_score > existing_score:
                            unique_functions[func_name] = func
            
            logger.info(f"Retrieved {len(unique_functions)} unique functions from ChromaDB using {len(search_queries)} queries")
            return list(unique_functions.values())
            
        except Exception as e:
            logger.error(f"Error fetching functions from ChromaDB: {e}")
            return []
    
    async def _match_functions_to_steps_with_llm(
        self,
        reasoning_plan: List[Dict[str, Any]],
        relevant_functions: List[Dict[str, Any]],
        question: str,
        dataframe_description: str,
        available_columns: List[str]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Use LLM to match functions to specific steps in the reasoning plan.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            relevant_functions: List of relevant functions from ChromaDB
            question: Original user question
            dataframe_description: Description of the dataframe
            available_columns: List of available columns
            
        Returns:
            Dictionary mapping step numbers to matched functions
        """
        try:
            # Format functions for LLM prompt with enriched context
            function_descriptions = []
            for func in relevant_functions:
                desc = f"""
                Function: {func.get('function_name', 'unknown')}
                Pipeline: {func.get('pipe_name', 'unknown')}
                Description: {func.get('description', 'No description')}
                Usage: {func.get('usage_description', 'No usage info')}
                Category: {func.get('category', 'unknown')}
                """
                
                # Add examples if available
                examples = func.get('examples', [])
                if examples:
                    desc += f"\nExamples ({len(examples)} available):\n"
                    for i, example in enumerate(examples[:3], 1):  # Show top 3 examples
                        desc += f"  {i}. {str(example)[:200]}...\n"
                
                # Add instructions if available
                instructions = func.get('instructions', [])
                if instructions:
                    desc += f"\nInstructions ({len(instructions)} available):\n"
                    for i, instruction in enumerate(instructions[:2], 1):  # Show top 2 instructions
                        desc += f"  {i}. {instruction.get('instruction', str(instruction))[:150]}...\n"
                
                # Add historical rules if available
                historical_rules = func.get('historical_rules', [])
                if historical_rules:
                    desc += f"\nHistorical Rules ({len(historical_rules)} available):\n"
                    for i, rule in enumerate(historical_rules[:2], 1):  # Show top 2 rules
                        content = rule.get('content', str(rule))
                        if isinstance(content, str):
                            desc += f"  {i}. {content[:150]}...\n"
                        else:
                            desc += f"  {i}. {str(content)[:150]}...\n"
                
                function_descriptions.append(desc)
            
            # Format reasoning plan for LLM prompt
            plan_description = "\n".join([
                f"Step {step.get('step_number', i+1)}: {step.get('step_title', '')}\n"
                f"Description: {step.get('step_description', '')}\n"
                f"Data Requirements: {', '.join(step.get('data_requirements', []))}\n"
                for i, step in enumerate(reasoning_plan)
            ])
            
            # Create LLM prompt for function matching
            prompt = f"""
            You are an expert data analyst who matches analysis functions to specific analysis steps.
            
            USER QUESTION: {question}
            DATAFRAME DESCRIPTION: {dataframe_description}
            AVAILABLE COLUMNS: {', '.join(available_columns)}
            
            ANALYSIS PLAN:
            {plan_description}
            
            AVAILABLE FUNCTIONS:
            {chr(10).join(function_descriptions)}
            
            TASK: For each step in the analysis plan, identify ALL relevant and appropriate functions.
            
            INSTRUCTIONS:
            1. Analyze each step's requirements and data needs comprehensively
            2. Match MULTIPLE functions that can fulfill those requirements (aim for 3-5 functions per step)
            3. Include both primary functions and alternative/backup functions
            4. Score each function's relevance (0.0 to 1.0) for each step
            5. Provide detailed reasoning for each match
            6. Consider different approaches: aggregation, time series, statistical analysis, etc.
            7. Include functions that could work together or provide different perspectives
            8. Return results as JSON
            
            OUTPUT FORMAT:
            CRITICAL: You must return ONLY a valid JSON object without any markdown formatting, code blocks, or extra text.
            
            CORRECT FORMAT:
            {{
                "step_matches": {{
                    "1": [
                        {{
                            "function_name": "function_name",
                            "pipe_name": "pipe_name", 
                            "relevance_score": 0.95,
                            "reasoning": "Why this function is relevant for this step",
                            "description": "function description",
                            "usage_description": "usage description",
                            "category": "category",
                            "function_definition": {{...}}
                        }}
                    ],
                    "2": [...],
                    ...
                }}
            }}
            
            WRONG FORMATS (DO NOT USE):
            ❌ ```json
            ❌ ```python
            ❌ Any markdown formatting
            ❌ Explanations before or after the JSON
            ❌ Extra text or comments
            
            CONSEQUENCES OF IMPROPER FORMAT:
            - If you return markdown code blocks, the parsing will fail
            - If you add extra text, the JSON parsing will fail
            - If you don't return valid JSON, the system will fall back to basic parsing
            - This will result in poor function matching quality
            
            Focus on functions that directly address each step's specific requirements.
            Return ONLY the JSON object, nothing else.
            """
            
            # Get LLM response
            llm_response = await self._classify_with_llm(prompt)
            
            # Log the response type for debugging
            logger.debug(f"LLM response type: {type(llm_response)}")
            logger.debug(f"LLM response: {llm_response[:500]}...")  # Log first 500 chars
            
            # Clean and parse the response
            try:
                # Clean the response - remove markdown formatting and empty content
                cleaned_response = llm_response.strip()
                
                # Remove markdown code blocks
                import re
                cleaned_response = re.sub(r'```json\s*', '', cleaned_response)
                cleaned_response = re.sub(r'```\s*', '', cleaned_response)
                cleaned_response = cleaned_response.strip()
                
                # Check if response is empty or just whitespace
                if not cleaned_response or cleaned_response.isspace():
                    logger.warning("LLM returned empty response, using fallback")
                    return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
                
                # Try to parse JSON
                response_data = json.loads(cleaned_response)
                step_matches = response_data.get("step_matches", {})
                
                # Convert string keys to integers and validate
                validated_matches = {}
                for step_key, functions in step_matches.items():
                    try:
                        step_num = int(step_key)
                        if step_num > 0 and isinstance(functions, list) and len(functions) > 0:
                            validated_matches[step_num] = functions
                    except ValueError:
                        continue
                
                # Check if we have enough functions - if not, use fallback
                total_functions = sum(len(funcs) for funcs in validated_matches.values())
                if total_functions < 2:  # Require at least 2 functions total
                    logger.warning(f"LLM returned only {total_functions} functions, using fallback matching")
                    return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
                
                logger.info(f"LLM matched {total_functions} functions to {len(validated_matches)} steps")
                return validated_matches
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse LLM response as JSON: {e}")
                logger.warning(f"Original response: {llm_response[:200]}...")
                logger.warning(f"Cleaned response: {cleaned_response[:200]}...")
                # Fallback: assign functions to steps based on simple matching
                return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
                
        except Exception as e:
            logger.error(f"Error in LLM function matching: {e}")
            # Fallback: assign functions to steps based on simple matching
            return self._fallback_function_step_matching(reasoning_plan, relevant_functions)
    
    def _fallback_function_step_matching(
        self,
        reasoning_plan: List[Dict[str, Any]],
        relevant_functions: List[Dict[str, Any]]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Fallback function matching when LLM matching fails.
        
        Args:
            reasoning_plan: The reasoning plan from Step 1
            relevant_functions: List of relevant functions from ChromaDB
            
        Returns:
            Dictionary mapping step numbers to matched functions
        """
        step_matches = {}
        
        for step in reasoning_plan:
            step_num = step.get("step_number", 0)
            step_title = step.get("step_title", "").lower()
            step_desc = step.get("step_description", "").lower()
            
            matched_functions = []
            
            for func in relevant_functions:
                func_name = func.get("function_name", "").lower()
                func_desc = func.get("description", "").lower()
                func_usage = func.get("usage_description", "").lower()
                
                # Simple keyword matching
                relevance_score = 0.0
                reasoning = ""
                
                # Check for keyword matches
                keywords = step_title.split() + step_desc.split()
                for keyword in keywords:
                    if keyword in func_name or keyword in func_desc or keyword in func_usage:
                        relevance_score += 0.2
                
                # Additional scoring based on function category and pipeline type
                func_category = func.get("category", "").lower()
                func_pipe = func.get("pipe_name", "").lower()
                
                # Boost score for time series related functions
                if any(ts_word in step_title or ts_word in step_desc for ts_word in ["time", "date", "rolling", "moving", "trend", "variance"]):
                    if any(ts_word in func_name or ts_word in func_desc for ts_word in ["time", "date", "rolling", "moving", "trend", "variance"]):
                        relevance_score += 0.3
                
                # Boost score for aggregation functions
                if any(agg_word in step_title or agg_word in step_desc for agg_word in ["aggregate", "group", "sum", "mean", "count"]):
                    if any(agg_word in func_name or agg_word in func_desc for agg_word in ["aggregate", "group", "sum", "mean", "count"]):
                        relevance_score += 0.2
                
                # Boost score for analysis functions
                if any(analysis_word in step_title or analysis_word in step_desc for analysis_word in ["analysis", "analyze", "calculate", "compute"]):
                    if any(analysis_word in func_name or analysis_word in func_desc for analysis_word in ["analysis", "analyze", "calculate", "compute"]):
                        relevance_score += 0.2
                
                # Normalize score
                relevance_score = min(1.0, relevance_score)
                
                if relevance_score > 0.2:  # Lowered threshold to include more functions
                    matched_functions.append({
                        "function_name": func.get("function_name", ""),
                        "pipe_name": func.get("pipe_name", ""),
                        "relevance_score": relevance_score,
                        "reasoning": f"Keyword match with step: {step_title}",
                        "description": func.get("description", ""),
                        "usage_description": func.get("usage_description", ""),
                        "category": func.get("category", ""),
                        "function_definition": func,
                        "examples": func.get("examples", []),
                        "instructions": func.get("instructions", []),
                        "examples_store": func.get("examples_store", []),
                        "historical_rules": func.get("historical_rules", [])
                    })
            
            # Sort by relevance score and take top functions
            matched_functions.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
            
            if matched_functions:
                # Take top 5 functions or all if less than 5
                top_functions = matched_functions[:5]
                step_matches[step_num] = top_functions
                logger.info(f"Step {step_num}: Matched {len(top_functions)} functions (top relevance: {top_functions[0].get('relevance_score', 0.0):.2f})")
        
        logger.info(f"Fallback matching assigned functions to {len(step_matches)} steps")
        return step_matches
    
    async def _classify_with_llm(self, prompt: str) -> str:
        """
        Classify using LLM with error handling
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            LLM response as string
        """
        try:
            # Create the chain with StrOutputParser
            chain = PromptTemplate.from_template("{prompt}") | self.llm | StrOutputParser()
            
            # Generate response with timeout
            import asyncio
            try:
                response = await asyncio.wait_for(
                    chain.ainvoke({"prompt": prompt}),
                    timeout=30.0  # 30 second timeout
                )
                
                # Validate response
                if not response or not isinstance(response, str):
                    logger.warning(f"LLM returned invalid response type: {type(response)}")
                    return ""
                
                return response
                
            except asyncio.TimeoutError:
                logger.error("LLM call timed out after 30 seconds")
                return ""
                
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return ""
    
    def _create_result_from_matches(
        self,
        step_function_matches: Dict[int, List[Dict[str, Any]]],
        total_functions: int,
        reasoning_plan: List[Dict[str, Any]],
        fallback_used: bool = False
    ) -> EnhancedFunctionRetrievalResult:
        """
        Create result object from step-function matches
        
        Args:
            step_function_matches: Dictionary mapping step numbers to matched functions
            total_functions: Total number of functions retrieved
            reasoning_plan: The reasoning plan from Step 1
            fallback_used: Whether fallback matching was used
            
        Returns:
            EnhancedFunctionRetrievalResult
        """
        # Calculate metrics
        total_steps_covered = len(step_function_matches)
        total_steps = len(reasoning_plan)
        
        # Calculate average relevance score
        all_scores = []
        for functions in step_function_matches.values():
            for func in functions:
                all_scores.append(func.get("relevance_score", 0.0))
        
        average_relevance_score = sum(all_scores) / len(all_scores) if all_scores else 0.0
        
        # Calculate confidence score
        coverage_ratio = total_steps_covered / total_steps if total_steps > 0 else 0.0
        confidence_score = (coverage_ratio + average_relevance_score) / 2
        
        reasoning = f"Matched {total_functions} functions to {total_steps_covered}/{total_steps} steps with average relevance {average_relevance_score:.2f}"
        if fallback_used:
            reasoning += " (using fallback matching)"
        
        return EnhancedFunctionRetrievalResult(
            step_matches=step_function_matches,
            total_functions_retrieved=total_functions,
            total_steps_covered=total_steps_covered,
            average_relevance_score=average_relevance_score,
            confidence_score=confidence_score,
            reasoning=reasoning,
            fallback_used=fallback_used
        )
    
    def _create_empty_result(self, reasoning: str, fallback_used: bool = True) -> EnhancedFunctionRetrievalResult:
        """
        Create empty result when no functions are found
        
        Args:
            reasoning: Reason for empty result
            fallback_used: Whether fallback was used
            
        Returns:
            EnhancedFunctionRetrievalResult
        """
        return EnhancedFunctionRetrievalResult(
            step_matches={},
            total_functions_retrieved=0,
            total_steps_covered=0,
            average_relevance_score=0.0,
            confidence_score=0.0,
            reasoning=reasoning,
            fallback_used=fallback_used
        )
    
    async def _enrich_function_with_context(
        self,
        function_data: Dict[str, Any],
        question: str,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich function data with examples, instructions, and examples store
        
        Args:
            function_data: Function data dictionary
            question: Original user question
            project_id: Optional project ID for instructions
            
        Returns:
            Enriched function data
        """
        if not self.retrieval_helper:
            return function_data
        
        function_name = function_data.get("function_name", "")
        if not function_name:
            return function_data
        
        try:
            # Retrieve examples, instructions, and examples store in parallel
            examples_task = self.retrieval_helper.get_function_examples(
                function_name=function_name,
                similarity_threshold=0.6,
                top_k=5
            )
            
            insights_task = self.retrieval_helper.get_function_insights(
                function_name=function_name,
                similarity_threshold=0.6,
                top_k=3
            )
            
            instructions_task = None
            if project_id:
                instructions_task = self.retrieval_helper.get_instructions(
                    query=question,
                    project_id=project_id,
                    similarity_threshold=0.7,
                    top_k=5
                )
            
            # Wait for all tasks to complete
            examples_result = await examples_task
            insights_result = await insights_task
            instructions_result = await instructions_task if instructions_task else {"instructions": []}
            
            # Extract examples
            examples = []
            if examples_result and not examples_result.get("error"):
                examples = examples_result.get("examples", [])
            
            # Extract insights (used as examples store for historical patterns)
            examples_store = []
            if insights_result and not insights_result.get("error"):
                examples_store = insights_result.get("insights", [])
            
            # Extract instructions
            instructions = []
            if instructions_result and not instructions_result.get("error"):
                instructions = instructions_result.get("instructions", [])
            
            # Get historical rules from examples store
            historical_rules = await self._get_historical_rules(function_name, question)
            
            # Update function data
            function_data.update({
                "examples": examples,
                "instructions": instructions,
                "examples_store": examples_store,
                "historical_rules": historical_rules
            })
            
            logger.info(f"Enriched {function_name} with {len(examples)} examples, {len(instructions)} instructions, {len(examples_store)} insights, {len(historical_rules)} historical rules")
            
        except Exception as e:
            logger.error(f"Error enriching function {function_name}: {e}")
            # Return original data if enrichment fails
            function_data.update({
                "examples": [],
                "instructions": [],
                "examples_store": [],
                "historical_rules": []
            })
        
        return function_data
    
    async def _get_historical_rules(
        self,
        function_name: str,
        question: str
    ) -> List[Dict[str, Any]]:
        """
        Get historical rules and patterns for the function
        
        Args:
            function_name: Name of the function
            question: User question for context
            
        Returns:
            List of historical rules and patterns
        """
        if not self.retrieval_helper:
            return []
        
        try:
            # Get examples store for historical patterns
            examples_store_result = await self.retrieval_helper.get_function_examples(
                function_name=function_name,
                similarity_threshold=0.5,
                top_k=10
            )
            
            historical_rules = []
            if examples_store_result and not examples_store_result.get("error"):
                examples = examples_store_result.get("examples", [])
                
                # Filter for historical patterns and rules
                for example in examples:
                    if isinstance(example, dict):
                        # Look for rule-like patterns in the example
                        if any(keyword in str(example).lower() for keyword in ["rule", "pattern", "best_practice", "guideline", "convention"]):
                            historical_rules.append({
                                "type": "historical_pattern",
                                "content": example,
                                "source": "examples_store"
                            })
            
            # Add hardcoded rules based on function type
            hardcoded_rules = self._get_hardcoded_rules(function_name)
            historical_rules.extend(hardcoded_rules)
            
            return historical_rules
            
        except Exception as e:
            logger.error(f"Error getting historical rules for {function_name}: {e}")
            return []
    
    def _get_hardcoded_rules(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Get hardcoded rules based on function type and name
        
        Args:
            function_name: Name of the function
            
        Returns:
            List of hardcoded rules
        """
        rules = []
        function_lower = function_name.lower()
        
        # Time series analysis rules
        if any(keyword in function_lower for keyword in ["variance", "rolling", "moving", "time_series"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For time series analysis, always ensure data is sorted by time column before applying rolling functions",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule", 
                    "content": "Use appropriate window sizes based on data frequency - daily data: 7-30 days, hourly data: 24-168 hours",
                    "source": "hardcoded"
                }
            ])
        
        # Cohort analysis rules
        if any(keyword in function_lower for keyword in ["cohort", "retention", "churn"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For cohort analysis, ensure user_id and date columns are properly formatted and contain no null values",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Use consistent time periods (monthly, weekly) for cohort calculations to ensure comparability",
                    "source": "hardcoded"
                }
            ])
        
        # Risk analysis rules
        if any(keyword in function_lower for keyword in ["var", "risk", "monte_carlo", "stress_test"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For risk analysis, use appropriate confidence levels (95% for VaR, 99% for stress testing)",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Ensure sufficient historical data (minimum 1 year) for reliable risk calculations",
                    "source": "hardcoded"
                }
            ])
        
        # Segmentation rules
        if any(keyword in function_lower for keyword in ["cluster", "segment", "dbscan", "kmeans"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For clustering, normalize numerical features before applying clustering algorithms",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Use appropriate distance metrics - Euclidean for continuous variables, Jaccard for categorical",
                    "source": "hardcoded"
                }
            ])
        
        # Funnel analysis rules
        if any(keyword in function_lower for keyword in ["funnel", "conversion", "step"]):
            rules.extend([
                {
                    "type": "hardcoded_rule",
                    "content": "For funnel analysis, ensure event sequences are properly ordered by timestamp",
                    "source": "hardcoded"
                },
                {
                    "type": "hardcoded_rule",
                    "content": "Handle duplicate events by keeping only the first occurrence in each funnel step",
                    "source": "hardcoded"
                }
            ])
        
        return rules

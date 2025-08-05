from typing import Dict, List, Any, Optional, Union, Tuple
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
import json
import re
from enum import Enum
import ast
from app.storage.documents import DocumentChromaStore
from .analysis_intent_classification import AnalysisIntentResult
import logging

logger = logging.getLogger("select-pipe-generator")

class SelectionStrategy(Enum):
    """Selection strategies for different analysis types"""
    BASIC_COLUMNS = "basic_columns"
    TIME_SERIES = "time_series"
    COHORT_ANALYSIS = "cohort_analysis"
    SEGMENTATION = "segmentation"
    FUNNEL_ANALYSIS = "funnel_analysis"
    RISK_ANALYSIS = "risk_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    METRICS_CALCULATION = "metrics_calculation"
    OPERATIONS_ANALYSIS = "operations_analysis"
    TREND_ANALYSIS = "trend_analysis"
    SEGMENTATION_ANALYSIS = "segmentation_analysis"

class SelectCodeQuality(Enum):
    """Code quality grades for SelectPipe code"""
    EXCELLENT = "excellent"
    GOOD = "good"
    POOR = "poor"
    INVALID = "invalid"

class SelfCorrectingSelectPipeGenerator:
    """
    Self-correcting RAG-based SelectPipe code generator that produces complete 
    SelectPipe chains with proper column selection, renaming, and reordering.
    
    Implements adaptive RAG pattern with:
    - Multi-store document retrieval
    - Relevance grading
    - SelectPipe code generation with validation
    - Self-correction loops
    """
    
    def __init__(self, 
                 llm,
                 usage_examples_store: DocumentChromaStore,
                 code_examples_store: DocumentChromaStore, 
                 function_definition_store: DocumentChromaStore,
                 max_iterations: int = 3,
                 relevance_threshold: float = 0.7):
        """
        Initialize the self-correcting SelectPipe code generator
        
        Args:
            llm: Language model instance
            usage_examples_store: Store containing usage examples (instructions)
            code_examples_store: Store containing code examples
            function_definition_store: Store containing function definitions
            max_iterations: Maximum number of self-correction iterations
            relevance_threshold: Threshold for document relevance scoring
        """
        self.llm = llm
        self.usage_examples_store = usage_examples_store
        self.code_examples_store = code_examples_store
        self.function_definition_store = function_definition_store
        self.max_iterations = max_iterations
        self.relevance_threshold = relevance_threshold
        
        # Intent type to selection strategy mapping
        self.intent_to_strategy = {
            "time_series_analysis": SelectionStrategy.TIME_SERIES,
            "trend_analysis": SelectionStrategy.TREND_ANALYSIS,
            "cohort_analysis": SelectionStrategy.COHORT_ANALYSIS,
            "segmentation_analysis": SelectionStrategy.SEGMENTATION_ANALYSIS,
            "funnel_analysis": SelectionStrategy.FUNNEL_ANALYSIS,
            "risk_analysis": SelectionStrategy.RISK_ANALYSIS,
            "anomaly_detection": SelectionStrategy.ANOMALY_DETECTION,
            "metrics_calculation": SelectionStrategy.METRICS_CALCULATION,
            "operations_analysis": SelectionStrategy.OPERATIONS_ANALYSIS,
            "unclear_intent": SelectionStrategy.BASIC_COLUMNS,
            "unsupported_analysis": SelectionStrategy.BASIC_COLUMNS
        }
        
        # Common column patterns for different data types
        self.column_patterns = {
            "identifier": ["id", "key", "uuid", "identifier", "user_id", "customer_id", "account_id"],
            "temporal": ["date", "time", "timestamp", "created", "updated", "datetime", "_at", "_date"],
            "numeric": ["amount", "value", "price", "cost", "revenue", "total", "count", "quantity", "score"],
            "categorical": ["type", "category", "status", "region", "segment", "group", "class"],
            "text": ["name", "title", "description", "comment", "text", "label"],
            "boolean": ["is_", "has_", "active", "enabled", "flag", "bool"]
        }
    
    async def generate_select_pipe_code(self, 
                                       context: str,
                                       classification: Union[Dict[str, Any], AnalysisIntentResult],
                                       available_columns: List[str],
                                       engine_name: str = "engine",
                                       table_name: str = "df",
                                       dataset_description: Optional[str] = None,
                                       columns_description: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Generate complete SelectPipe code with self-correction
        
        Args:
            context: Natural language description of the task
            classification: Analysis intent classification results
            available_columns: List of available columns in the dataset
            engine_name: Name of the engine variable (default: "engine")
            table_name: Name of the table/dataframe (default: "df")
            dataset_description: Optional description of the dataset
            columns_description: Optional dictionary mapping column names to descriptions
            
        Returns:
            Dictionary containing generated SelectPipe code and metadata
        """
        
        # Extract classification information
        if hasattr(classification, 'intent_type'):
            # Pydantic model (AnalysisIntentResult)
            intent_type = getattr(classification, 'intent_type', 'unclear_intent')
            reasoning_plan = getattr(classification, 'reasoning_plan', [])
            required_columns = getattr(classification, 'required_data_columns', [])
            rephrased_question = getattr(classification, 'rephrased_question', context)
        else:
            # Dictionary
            intent_type = classification.get('intent_type', 'unclear_intent')
            reasoning_plan = classification.get('reasoning_plan', [])
            required_columns = classification.get('required_data_columns', [])
            rephrased_question = classification.get('rephrased_question', context)
        
        # Determine selection strategy
        selection_strategy = self.intent_to_strategy.get(intent_type, SelectionStrategy.BASIC_COLUMNS)
        
        # Extract data selection requirements from reasoning plan
        data_selection_steps = await self._extract_data_selection_steps(reasoning_plan)
        
        query_state = {
            "context": context,
            "rephrased_question": rephrased_question,
            "classification": classification,
            "intent_type": intent_type,
            "selection_strategy": selection_strategy,
            "available_columns": available_columns,
            "required_columns": required_columns,
            "data_selection_steps": data_selection_steps,
            "engine_name": engine_name,
            "table_name": table_name,
            "dataset_description": dataset_description,
            "columns_description": columns_description,
            "iteration": 0,
            "retrieved_docs": {},
            "code_attempts": [],
            "final_code": None,
            "reasoning": []
        }
        
        # Self-correction loop
        for iteration in range(self.max_iterations):
            query_state["iteration"] = iteration
            
            # Step 1: Retrieve documents
            retrieved_docs = await self._retrieve_documents(query_state)
            
            # Step 2: Grade document relevance
            relevant_docs = await self._grade_documents(retrieved_docs, query_state)
            
            # Step 3: Generate SelectPipe code
            generated_code = await self._generate_select_pipe_code(relevant_docs, query_state)
            
            # Step 4: Validate and grade code
            code_quality = await self._grade_select_code(generated_code, query_state)
            
            # Step 5: Decide on next action
            if code_quality in [SelectCodeQuality.EXCELLENT, SelectCodeQuality.GOOD]:
                query_state["final_code"] = generated_code
                break
            elif iteration < self.max_iterations - 1:
                # Self-correct: refine query and try again
                query_state = await self._refine_query_state(query_state, code_quality)
        
        return await self._format_final_result(query_state)
    
    async def _extract_data_selection_steps(self, reasoning_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract data selection related steps from the reasoning plan using LLM analysis
        
        Args:
            reasoning_plan: List of reasoning plan steps
            
        Returns:
            List of data selection steps
        """
        data_selection_steps = []
        
        if not reasoning_plan or not isinstance(reasoning_plan, list):
            return data_selection_steps
        
        # Create LLM prompt for data selection step extraction
        extraction_prompt = PromptTemplate(
            input_variables=["reasoning_plan"],
            template="""
            You are an expert data scientist analyzing a reasoning plan to identify data selection and preparation steps.
            
            TASK: Analyze the provided reasoning plan and identify steps that involve data selection, preparation, filtering, or column selection operations.
            
            REASONING PLAN:
            {reasoning_plan}
            
            INSTRUCTIONS:
            1. Review each step in the reasoning plan
            2. Identify steps that involve:
               - Data selection or column selection
               - Data preparation or preprocessing
               - Data filtering or subsetting
               - Column renaming or reordering
               - Data cleaning or validation
               - Feature selection or engineering
               - Data transformation for analysis
            3. For each identified step, extract the relevant information
            4. If no explicit data selection steps are found, create a default step based on data requirements mentioned in other steps
            
            OUTPUT FORMAT:
            Return a JSON array of data selection steps. Each step should contain:
            {{
                "step_number": <sequential number>,
                "step_title": "<brief title>",
                "step_description": "<detailed description>",
                "data_requirements": ["<list of required columns or data types>"],
                "expected_outcome": "<what this step produces>",
                "considerations": "<important considerations or notes>"
            }}
            
            EXAMPLES OF DATA SELECTION STEPS:
            - Steps mentioning "select columns", "choose features", "filter data"
            - Steps involving "data preparation", "preprocessing", "cleaning"
            - Steps with "column selection", "feature selection", "data subsetting"
            - Steps that mention specific columns or data types needed
            - Steps involving data transformation or formatting
            
            CRITICAL: Only return the JSON array, no additional text or explanations.
            """
        )
        
        try:
            # Create the extraction chain
            extraction_chain = extraction_prompt | self.llm | StrOutputParser()
            
            # Call the LLM to extract data selection steps
            llm_response = await extraction_chain.ainvoke({
                "reasoning_plan": json.dumps(reasoning_plan, indent=2)
            })
            
            # Parse the LLM response
            try:
                # Try to extract JSON from the response
                json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
                if json_match:
                    extracted_steps = json.loads(json_match.group())
                else:
                    # If no JSON array found, try to parse the entire response
                    extracted_steps = json.loads(llm_response)
                
                # Validate and process the extracted steps
                if isinstance(extracted_steps, list):
                    for step in extracted_steps:
                        if isinstance(step, dict):
                            # Ensure all required fields are present
                            processed_step = {
                                "step_number": step.get("step_number", len(data_selection_steps) + 1),
                                "step_title": step.get("step_title", ""),
                                "step_description": step.get("step_description", ""),
                                "data_requirements": step.get("data_requirements", []),
                                "expected_outcome": step.get("expected_outcome", ""),
                                "considerations": step.get("considerations", "")
                            }
                            data_selection_steps.append(processed_step)
                
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse LLM response for data selection steps: {e}")
                # Fallback to keyword-based extraction
                data_selection_steps = self._fallback_keyword_extraction(reasoning_plan)
                
        except Exception as e:
            logger.error(f"Error in LLM-based data selection step extraction: {e}")
            # Fallback to keyword-based extraction
            data_selection_steps = self._fallback_keyword_extraction(reasoning_plan)
        
        return data_selection_steps
    
    def _fallback_keyword_extraction(self, reasoning_plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fallback method using keyword matching for data selection step extraction
        
        Args:
            reasoning_plan: List of reasoning plan steps
            
        Returns:
            List of data selection steps
        """
        data_selection_steps = []
        
        for step in reasoning_plan:
            if not isinstance(step, dict):
                continue
                
            step_title = step.get('step_title', '').lower()
            step_description = step.get('step_description', '').lower()
            data_requirements = step.get('data_requirements', [])
            
            # Look for data preparation, selection, or filtering steps
            selection_keywords = ['data preparation', 'data selection', 'select columns', 'filter data', 
                                'prepare data', 'column selection', 'data filtering', 'subset data',
                                'choose columns', 'extract columns', 'data cleaning', 'data preprocessing']
            
            if any(keyword in step_title or keyword in step_description for keyword in selection_keywords):
                data_selection_steps.append({
                    "step_number": step.get('step_number', len(data_selection_steps) + 1),
                    "step_title": step.get('step_title', ''),
                    "step_description": step.get('step_description', ''),
                    "data_requirements": data_requirements,
                    "expected_outcome": step.get('expected_outcome', ''),
                    "considerations": step.get('considerations', '')
                })
        
        # If no explicit data selection steps found, create a default one based on data requirements
        if not data_selection_steps:
            # Look for any steps that mention specific columns or data requirements
            all_data_requirements = []
            for step in reasoning_plan:
                if isinstance(step, dict) and 'data_requirements' in step:
                    requirements = step.get('data_requirements', [])
                    if isinstance(requirements, list):
                        all_data_requirements.extend(requirements)
            
            if all_data_requirements:
                data_selection_steps.append({
                    "step_number": 1,
                    "step_title": "Data Selection and Preparation",
                    "step_description": "Select relevant columns for analysis based on requirements",
                    "data_requirements": list(set(all_data_requirements)),
                    "expected_outcome": "Dataset with selected columns ready for analysis",
                    "considerations": "Ensure all required columns are available and properly formatted"
                })
        
        return data_selection_steps
    
    async def _retrieve_documents(self, query_state: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve relevant documents from all stores"""
        context = query_state["context"]
        selection_strategy = query_state["selection_strategy"]
        intent_type = query_state["intent_type"]
        
        # Create enhanced query for retrieval
        enhanced_query = self._create_enhanced_query(context, selection_strategy, intent_type)
        
        retrieved_docs = {}
        
        # Retrieve from usage examples store (instructions)
        if self.usage_examples_store:
            usage_results = self.usage_examples_store.semantic_searches(
                [enhanced_query, "SelectPipe column selection", f"{intent_type} data selection"], 
                n_results=5
            )
            retrieved_docs["usage_examples"] = self._parse_retrieval_results(usage_results)
        
        # Retrieve from code examples store
        if self.code_examples_store:
            code_results = self.code_examples_store.semantic_searches(
                [enhanced_query, "SelectPipe examples", f"{selection_strategy.value} selection"], 
                n_results=5
            )
            retrieved_docs["code_examples"] = self._parse_retrieval_results(code_results)
        
        # Retrieve from function definition store
        if self.function_definition_store:
            func_results = self.function_definition_store.semantic_searches(
                ["SelectPipe", "Select", "Rename", "Reorder", "column selection"], 
                n_results=5
            )
            retrieved_docs["function_definitions"] = self._parse_retrieval_results(func_results)
        
        return retrieved_docs
    
    def _create_enhanced_query(self, context: str, selection_strategy: SelectionStrategy, 
                              intent_type: str) -> str:
        """Create enhanced query for better retrieval"""
        return f"{context} {selection_strategy.value} {intent_type} SelectPipe column selection data preparation"
    
    def _parse_retrieval_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse retrieval results into structured format"""
        documents = []
        
        if results and "documents" in results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results.get("distances", [[]])[0][i] if "distances" in results else 0.0
                
                # Parse document if it's a JSON string
                if isinstance(doc, str):
                    try:
                        doc = json.loads(doc)
                    except:
                        doc = {"content": doc}
                
                documents.append({
                    "content": doc,
                    "distance": distance,
                    "relevance_score": 1.0 - distance
                })
        
        return documents
    
    async def _grade_documents(self, retrieved_docs: Dict[str, List[Dict[str, Any]]], 
                              query_state: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Grade document relevance and filter relevant ones"""
        context = query_state["context"]
        selection_strategy = query_state["selection_strategy"]
        
        grading_prompt = PromptTemplate(
            input_variables=["context", "selection_strategy", "document", "doc_type"],
            template="""
            You are a document relevance grader for SelectPipe code generation.
            
            CONTEXT: {context}
            SELECTION STRATEGY: {selection_strategy}
            DOCUMENT TYPE: {doc_type}
            DOCUMENT: {document}
            
            Grade the relevance of this document for generating SelectPipe code:
            - RELEVANT: Document directly helps with SelectPipe column selection
            - PARTIALLY_RELEVANT: Document has some useful information about data selection
            - IRRELEVANT: Document is not useful for SelectPipe generation
            
            Return only: RELEVANT, PARTIALLY_RELEVANT, or IRRELEVANT
            """
        )
        
        grading_chain = grading_prompt | self.llm | StrOutputParser()
        
        relevant_docs = {}
        
        for doc_type, documents in retrieved_docs.items():
            relevant_docs[doc_type] = []
            
            for doc in documents:
                try:
                    relevance = await grading_chain.ainvoke({
                        "context": context,
                        "selection_strategy": selection_strategy.value,
                        "document": json.dumps(doc, indent=2),
                        "doc_type": doc_type
                    })
                    relevance = relevance.strip().upper()
                    
                    if relevance in ["RELEVANT", "PARTIALLY_RELEVANT"]:
                        doc["relevance_grade"] = relevance
                        relevant_docs[doc_type].append(doc)
                        
                except Exception as e:
                    # If grading fails, include the document
                    doc["relevance_grade"] = "UNKNOWN"
                    relevant_docs[doc_type].append(doc)
        
        return relevant_docs
    
    async def _generate_select_pipe_code(self, relevant_docs: Dict[str, List[Dict[str, Any]]], 
                                        query_state: Dict[str, Any]) -> str:
        """Generate complete SelectPipe code"""
        context = query_state["context"]
        rephrased_question = query_state["rephrased_question"]
        intent_type = query_state["intent_type"]
        selection_strategy = query_state["selection_strategy"]
        available_columns = query_state["available_columns"]
        required_columns = query_state["required_columns"]
        data_selection_steps = query_state["data_selection_steps"]
        engine_name = query_state["engine_name"]
        table_name = query_state["table_name"]
        dataset_description = query_state.get("dataset_description")
        columns_description = query_state.get("columns_description", {})
        classification = query_state.get("classification", {})
        
        # Format relevant documents
        docs_context = self._format_documents_for_generation(relevant_docs)
        
        # Format classification context
        classification_context = self._format_classification_context(classification)
        
        # Format dataset context
        dataset_context = self._format_dataset_context(dataset_description, columns_description)
        
        # Format data selection steps
        selection_steps_context = self._format_selection_steps(data_selection_steps)
        
        generation_prompt = PromptTemplate(
            input_variables=[
                "context", "rephrased_question", "intent_type", "selection_strategy", 
                "available_columns", "required_columns", "engine_name", "table_name",
                "data_selection_steps", "docs_context", "classification_context", 
                "dataset_context", "selection_steps_context", "iteration"
            ],
            template="""
            You are an expert SelectPipe code generator for data column selection and preparation.
            
            ORIGINAL CONTEXT: {context}
            REPHRASED QUESTION: {rephrased_question}
            INTENT TYPE: {intent_type}
            SELECTION STRATEGY: {selection_strategy}
            ENGINE NAME: {engine_name}
            TABLE NAME: {table_name}
            ITERATION: {iteration}
            
            AVAILABLE COLUMNS: {available_columns}
            REQUIRED COLUMNS: {required_columns}
            
            DATA SELECTION STEPS FROM REASONING PLAN:
            {selection_steps_context}
            
            CLASSIFICATION ANALYSIS:
            {classification_context}
            
            DATASET INFORMATION:
            {dataset_context}
            
            RELEVANT DOCUMENTATION:
            {docs_context}
            
            Generate a complete SelectPipe code that:
            1. Uses SelectPipe.from_engine({engine_name}, '{table_name}') initialization
            2. Applies appropriate column selection using Select() with relevant selectors
            3. Uses column renaming with Rename() if needed for clarity
            4. Applies column reordering with Reorder() for logical organization
            5. Follows the data selection requirements from the reasoning plan
            6. Considers the intent type and selection strategy
            7. Uses .to_df() at the end to return a DataFrame
            
            AVAILABLE SELECTORS:
            - cols('col1', 'col2', ...): Select specific columns by name
            - startswith('prefix'): Select columns starting with prefix
            - endswith('suffix'): Select columns ending with suffix  
            - contains('substring'): Select columns containing substring
            - matches('regex'): Select columns matching regex pattern
            - has_type('dtype'): Select columns of specific data type
            - numeric(): Select all numeric columns
            - string(): Select all string/text columns
            - temporal(): Select all date/time columns
            - categorical(): Select all categorical columns
            - everything(): Select all columns
            - Logical operators: & (and), | (or), ~ (not), - (subtract)
            
            SELECTION STRATEGY GUIDELINES:
            
            TIME_SERIES: Focus on temporal columns, numeric metrics, and identifiers
            - Prioritize: date/time columns, value columns, grouping columns
            - Example: temporal() | contains('value') | contains('id')
            
            COHORT_ANALYSIS: Focus on user identifiers, dates, and behavioral metrics
            - Prioritize: user_id, date columns, event columns, value columns
            - Example: contains('user') | temporal() | contains('event') | numeric()
            
            SEGMENTATION: Focus on categorical features and numeric metrics
            - Prioritize: categorical columns, numeric features, identifiers
            - Example: categorical() | numeric() | contains('id')
            
            FUNNEL_ANALYSIS: Focus on user identifiers, events, and timestamps
            - Prioritize: user_id, event columns, timestamps, step indicators
            - Example: contains('user') | contains('event') | temporal()
            
            RISK_ANALYSIS: Focus on numeric metrics and risk indicators
            - Prioritize: numeric columns, volatility measures, identifiers
            - Example: numeric() | contains('risk') | contains('volatility')
            
            ANOMALY_DETECTION: Focus on metrics to analyze and time indicators
            - Prioritize: numeric columns, time columns, contextual features
            - Example: numeric() | temporal() | categorical()
            
            METRICS_CALCULATION: Focus on relevant business metrics
            - Prioritize: numeric columns, grouping dimensions
            - Example: numeric() | categorical() | contains('id')
            
            OPERATIONS_ANALYSIS: Focus on operational metrics and dimensions
            - Prioritize: numeric metrics, categorical dimensions, identifiers
            - Example: numeric() | categorical() | contains('id')

            RISK_ANALYSIS: Focus on numeric metrics and risk indicators
            - Prioritize: numeric columns, volatility measures, identifiers
            - Example: numeric() | contains('risk') | contains('volatility')

            TREND_ANALYSIS: Focus on temporal columns and metrics
            - Prioritize: temporal columns, numeric metrics, identifiers
            - Example: temporal() | numeric() | contains('id')

            
            CRITICAL SYNTAX REQUIREMENTS:
            - Use proper SelectPipe initialization: SelectPipe.from_engine({engine_name}, '{table_name}')
            - Chain operations with pipe operator (|)
            - Use proper selector syntax: Select(selector1 | selector2 | selector3)
            - Use dictionary syntax for Rename: Rename({{'old_name': 'new_name'}})
            - Use positional arguments for Reorder: Reorder('col1', 'col2', 'col3')
            - End with .to_df() to return DataFrame
            - Use proper indentation (4 spaces for continued lines)
            - Ensure all parentheses are properly closed
            
            EXAMPLE OUTPUT FORMATS:
            
            Example 1 - Basic column selection:
            ```python
            result = (
                SelectPipe.from_engine({engine_name}, '{table_name}')
                | Select(
                    # Required columns for analysis
                    cols('customer_id', 'order_date', 'amount') |
                    # Additional relevant columns
                    contains('region') | contains('product')
                )
            ).to_df()
            ```
            
            Example 2 - Complex selection with renaming and reordering:
            ```python
            result = (
                SelectPipe.from_engine({engine_name}, '{table_name}')
                | Select(
                    # Customer identifiers
                    cols('customer_id', 'customer_name') |
                    # Temporal columns
                    temporal() |
                    # Business metrics
                    contains('amount') | contains('quantity') |
                    # Categorical dimensions
                    cols('region', 'product_category')
                )
                | Rename({{
                    'order_amount': 'revenue',
                    'order_quantity': 'units_sold',
                    'customer_age': 'age',
                    'region_name': 'region'
                }})
                | Reorder(
                    'customer_id', 'customer_name', 'age', 'region',
                    'order_date', 'revenue', 'units_sold', 'product_category'
                )
            ).to_df()
            ```
            
            Example 3 - Time series specific selection:
            ```python
            result = (
                SelectPipe.from_engine({engine_name}, '{table_name}')
                | Select(
                    # Time column for analysis
                    temporal() |
                    # Metrics to analyze over time
                    numeric() & ~contains('id') |
                    # Grouping dimensions
                    categorical() |
                    # Identifiers
                    contains('id')
                )
                | Rename({{
                    'timestamp': 'date',
                    'transaction_value': 'value',
                    'user_identifier': 'user_id'
                }})
                | Reorder(
                    'date', 'user_id', 'value', 'category', 'region'
                )
            ).to_df()
            ```
            
            Generate ONLY the SelectPipe code following the patterns above. Use the actual column names from AVAILABLE_COLUMNS.
            Consider the REQUIRED_COLUMNS and DATA_SELECTION_STEPS to inform your selection logic.
            """
        )
        
        generation_chain = generation_prompt | self.llm | StrOutputParser()
        
        try:
            generated_code = await generation_chain.ainvoke({
                "context": context,
                "rephrased_question": rephrased_question,
                "intent_type": intent_type,
                "selection_strategy": selection_strategy.value,
                "available_columns": json.dumps(available_columns),
                "required_columns": json.dumps(required_columns),
                "engine_name": engine_name,
                "table_name": table_name,
                "data_selection_steps": json.dumps(data_selection_steps, indent=2),
                "docs_context": docs_context,
                "classification_context": classification_context,
                "dataset_context": dataset_context,
                "selection_steps_context": selection_steps_context,
                "iteration": query_state["iteration"]
            })
            
            # Clean up the generated code
            code = self._clean_generated_code(generated_code)
            
            # Validate the cleaned code
            try:
                ast.parse(code)
                logger.info("Generated SelectPipe code passed syntax validation")
            except SyntaxError as e:
                logger.warning(f"Syntax error in SelectPipe code: {e}")
                # Try to fix the code
                code = self._fix_select_code_syntax(code)
                logger.info("Attempted to fix SelectPipe code syntax")
            
            query_state["code_attempts"].append(code)
            
            return code
            
        except Exception as e:
            logger.error(f"Error in SelectPipe code generation: {e}")
            fallback_code = self._generate_fallback_select_code(
                engine_name, table_name, available_columns, required_columns
            )
            query_state["code_attempts"].append(fallback_code)
            return fallback_code
    
    def _format_documents_for_generation(self, relevant_docs: Dict[str, List[Dict[str, Any]]]) -> str:
        """Format documents for code generation prompt"""
        formatted_docs = []
        
        for doc_type, documents in relevant_docs.items():
            if documents:
                formatted_docs.append(f"\n{doc_type.upper()}:")
                for doc in documents[:3]:  # Limit to top 3 per type
                    content = doc["content"]
                    if isinstance(content, dict):
                        content = json.dumps(content, indent=2)
                    elif len(str(content)) > 500:
                        content = str(content)[:500] + "..."
                    formatted_docs.append(f"- {content}")
        
        return "\n".join(formatted_docs) if formatted_docs else "No relevant documents available."
    
    def _format_classification_context(self, classification: Optional[Union[Dict[str, Any], AnalysisIntentResult]]) -> str:
        """Format classification information for code generation prompt"""
        if not classification:
            return "No classification information available."
        
        parts = []
        
        # Handle both dictionary and Pydantic model inputs
        if hasattr(classification, 'intent_type'):
            # Pydantic model (AnalysisIntentResult)
            intent_type = getattr(classification, 'intent_type', '')
            confidence_score = getattr(classification, 'confidence_score', 0.0)
            suggested_functions = getattr(classification, 'suggested_functions', [])
            required_columns = getattr(classification, 'required_data_columns', [])
            reasoning = getattr(classification, 'reasoning', '')
        else:
            # Dictionary
            intent_type = classification.get('intent_type', '')
            confidence_score = classification.get('confidence_score', 0.0)
            suggested_functions = classification.get('suggested_functions', [])
            required_columns = classification.get('required_data_columns', [])
            reasoning = classification.get('reasoning', '')
        
        if intent_type:
            parts.append(f"Intent Type: {intent_type} (confidence: {confidence_score:.2f})")
        if suggested_functions:
            parts.append(f"Suggested Functions: {', '.join(suggested_functions)}")
        if required_columns:
            parts.append(f"Required Columns: {', '.join(required_columns)}")
        if reasoning:
            parts.append(f"Reasoning: {reasoning}")
        
        return "\n".join(parts) if parts else "No classification information available."
    
    def _format_dataset_context(self, dataset_description: Optional[str], 
                               columns_description: Dict[str, str]) -> str:
        """Format dataset information for code generation prompt"""
        parts = []
        
        if dataset_description:
            parts.append(f"Dataset: {dataset_description}")
        
        if columns_description:
            parts.append("Columns Analysis:")
            parts.append(json.dumps(columns_description, indent=2))
            
        return "\n".join(parts) if parts else "No dataset information available."
    
    def _format_selection_steps(self, data_selection_steps: List[Dict[str, Any]]) -> str:
        """Format data selection steps for the prompt"""
        if not data_selection_steps:
            return "No specific data selection steps identified."
        
        formatted_steps = []
        for step in data_selection_steps:
            step_text = f"Step {step.get('step_number', '?')}: {step.get('step_title', 'Unknown')}"
            if step.get('step_description'):
                step_text += f"\n  Description: {step.get('step_description')}"
            if step.get('data_requirements'):
                step_text += f"\n  Data Requirements: {', '.join(step.get('data_requirements', []))}"
            if step.get('expected_outcome'):
                step_text += f"\n  Expected Outcome: {step.get('expected_outcome')}"
            formatted_steps.append(step_text)
        
        return "\n\n".join(formatted_steps)
    
    async def _grade_select_code(self, generated_code: str, query_state: Dict[str, Any]) -> SelectCodeQuality:
        """Grade the quality of generated SelectPipe code"""
        # Syntax validation
        try:
            ast.parse(generated_code)
        except SyntaxError as e:
            logger.warning(f"Syntax error in generated SelectPipe code: {e}")
            return SelectCodeQuality.INVALID
        
        # Basic semantic validation - check if it contains expected elements
        engine_name = query_state["engine_name"]
        table_name = query_state["table_name"]
        
        # Check for basic required elements
        if "SelectPipe.from_engine" not in generated_code:
            return SelectCodeQuality.POOR
        
        if engine_name not in generated_code:
            return SelectCodeQuality.POOR
        
        if table_name not in generated_code:
            return SelectCodeQuality.POOR
        
        if "Select(" not in generated_code:
            return SelectCodeQuality.POOR
        
        if ".to_df()" not in generated_code:
            return SelectCodeQuality.POOR
        
        # Check for proper selector usage
        selectors = ["cols(", "startswith(", "endswith(", "contains(", "matches(", 
                    "has_type(", "numeric()", "string(", "temporal(", "categorical("]
        
        has_selectors = any(selector in generated_code for selector in selectors)
        if not has_selectors:
            return SelectCodeQuality.POOR
        
        # If syntax is valid and basic elements are present, consider it GOOD
        return SelectCodeQuality.GOOD
    
    async def _refine_query_state(self, query_state: Dict[str, Any], 
                                 code_quality: SelectCodeQuality) -> Dict[str, Any]:
        """Refine query state based on code quality feedback"""
        if code_quality == SelectCodeQuality.INVALID:
            query_state["reasoning"].append("SelectPipe code had syntax errors, refining generation approach")
        elif code_quality == SelectCodeQuality.POOR:
            query_state["reasoning"].append("SelectPipe code quality was poor, improving selector usage and structure")
        
        # Enhance context for next iteration
        query_state["context"] += f" [Iteration {query_state['iteration'] + 1}: Improve SelectPipe structure and selector usage]"
        
        return query_state
    
    def _clean_generated_code(self, code: str) -> str:
        """Clean and format generated SelectPipe code"""
        if not code or not isinstance(code, str):
            return ""
        
        # Remove markdown code blocks
        code = re.sub(r'```python\s*', '', code)
        code = re.sub(r'```\s*', '', code)
        
        # Clean whitespace and remove empty lines
        lines = [line.rstrip() for line in code.split('\n') if line.strip()]
        
        if not lines:
            return ""
        
        # Join lines back together
        code = '\n'.join(lines)
        
        # Fix common SelectPipe syntax issues
        code = self._fix_select_code_syntax(code)
        
        return code
    
    def _fix_select_code_syntax(self, code: str) -> str:
        """Fix common syntax issues in SelectPipe code"""
        # Fix missing .to_df() parentheses
        code = re.sub(r'\.to_df\s*$', '.to_df()', code, flags=re.MULTILINE)
        code = re.sub(r'\.to_df\s*\n', '.to_df()\n', code)
        
        # Fix Select() syntax - ensure proper parentheses
        code = re.sub(r'Select\s*\(\s*\)', 'Select(everything())', code)
        
        # Fix Rename() syntax - ensure dictionary format
        code = re.sub(r'Rename\s*\(\s*([^{])', r'Rename({\1', code)
        
        # Fix Reorder() syntax - ensure proper comma separation
        code = re.sub(r'Reorder\s*\(\s*\[([^\]]+)\]\s*\)', r'Reorder(\1)', code)
        
        # Fix pipe operator spacing
        code = re.sub(r'\|\s*\|', ' |', code)
        code = re.sub(r'\s*\|\s*', ' | ', code)
        
        # Fix parentheses balance
        open_parens = code.count('(')
        close_parens = code.count(')')
        
        if open_parens > close_parens:
            missing = open_parens - close_parens
            code += ')' * missing
        elif close_parens > open_parens:
            extra = close_parens - open_parens
            for _ in range(extra):
                if code.endswith(')'):
                    code = code[:-1]
        
        return code
    
    def _generate_fallback_select_code(self, engine_name: str, table_name: str, 
                                      available_columns: List[str], 
                                      required_columns: List[str]) -> str:
        """Generate fallback SelectPipe code when main generation fails"""
        try:
            # Use required columns if available, otherwise select basic columns
            if required_columns:
                columns_selector = f"cols({', '.join([f\"'{col}'\" for col in required_columns[:5]])})"
            else:
                # Fallback to selecting first few available columns
                selected_cols = available_columns[:5] if available_columns else ['id', 'name', 'value']
                columns_selector = f"cols({', '.join([f\"'{col}'\" for col in selected_cols])})"
            
            fallback_code = f"""result = (
    SelectPipe.from_engine({engine_name}, '{table_name}')
    | Select(
        {columns_selector}
    )
).to_df()"""
            
            # Validate the fallback code
            try:
                ast.parse(fallback_code)
                return fallback_code
            except SyntaxError:
                # If even the fallback has syntax errors, return the most basic version
                return f"""result = (
    SelectPipe.from_engine({engine_name}, '{table_name}')
    | Select(everything())
).to_df()"""
                
        except Exception as e:
            logger.error(f"Error generating fallback SelectPipe code: {e}")
            # Return the most basic valid code
            return f"""result = (
    SelectPipe.from_engine(engine, 'df')
    | Select(everything())
).to_df()"""
    
    async def _format_final_result(self, query_state: Dict[str, Any]) -> Dict[str, Any]:
        """Format the final result"""
        final_code = query_state["final_code"] or (query_state["code_attempts"][-1] if query_state["code_attempts"] else None)
        has_generated_code = final_code is not None
        
        return {
            "status": "success" if has_generated_code else "error",
            "generated_code": final_code,
            "iterations": query_state["iteration"] + 1,
            "attempts": query_state["code_attempts"],
            "reasoning": query_state["reasoning"],
            "selection_strategy": query_state["selection_strategy"].value,
            "intent_type": query_state["intent_type"],
            "data_selection_steps": query_state["data_selection_steps"],
            "required_columns": query_state["required_columns"],
            "available_columns": query_state["available_columns"],
            "classification": query_state.get("classification"),
            "dataset_description": query_state.get("dataset_description"),
            "columns_description": query_state.get("columns_description"),
            "enhanced_context": query_state["context"]
        }

# Example usage
if __name__ == "__main__":
    import asyncio
    from unittest.mock import Mock
    
    async def test_select_pipe_generator():
        # Mock LLM for testing
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = '''
        result = (
            SelectPipe.from_engine(engine, 'customers')
            | Select(
                # Customer identifiers
                cols('customer_id', 'customer_name') |
                # Order information
                startswith('order') |
                # Customer demographics
                cols('customer_age', 'region_code') |
                # Business metrics
                contains('discount') | contains('score')
            )
            | Rename({
                'order_amount': 'revenue',
                'order_quantity': 'units_sold',
                'customer_age': 'age',
                'discount_pct': 'discount_rate'
            })
            | Reorder(
                'customer_id', 'customer_name', 'age', 'region_code',
                'order_date', 'revenue', 'units_sold', 'discount_rate'
            )
        ).to_df()
        '''
        mock_llm.ainvoke = Mock(return_value=mock_response)
        
        # Mock ChromaDB stores
        mock_store = Mock()
        mock_store.semantic_searches = Mock(return_value={"documents": [[]], "distances": [[]]})
        
        # Initialize SelectPipe generator
        select_generator = SelfCorrectingSelectPipeGenerator(
            llm=mock_llm,
            usage_examples_store=mock_store,
            code_examples_store=mock_store,
            function_definition_store=mock_store
        )
        
        # Mock classification results
        classification = {
            "intent_type": "metrics_calculation",
            "confidence_score": 0.9,
            "rephrased_question": "Calculate customer metrics by region",
            "required_data_columns": ["customer_id", "order_amount", "region_code"],
            "reasoning_plan": [
                {
                    "step_number": 1,
                    "step_title": "Data Selection and Preparation",
                    "step_description": "Select relevant customer and order columns",
                    "data_requirements": ["customer_id", "customer_name", "order_amount", "region_code"],
                    "expected_outcome": "Dataset with customer metrics ready for analysis"
                }
            ]
        }
        
        # Available columns in the dataset
        available_columns = [
            "customer_id", "customer_name", "customer_age", "region_code",
            "order_date", "order_amount", "order_quantity", "discount_pct",
            "loyalty_score", "product_category"
        ]
        
        # Generate SelectPipe code
        result = await select_generator.generate_select_pipe_code(
            context="Select relevant columns for customer analysis by region",
            classification=classification,
            available_columns=available_columns,
            engine_name="engine",
            table_name="customers",
            dataset_description="Customer orders dataset with demographics and transaction data"
        )
        
        print(f"Status: {result['status']}")
        print(f"Iterations: {result['iterations']}")
        print(f"Selection Strategy: {result['selection_strategy']}")
        print(f"Generated Code:\n{result['generated_code']}")
        
        return "Test completed successfully!"
    
    # Run the test
    test_result = asyncio.run(test_select_pipe_generator())
    print(f"\nOverall result: {test_result}")
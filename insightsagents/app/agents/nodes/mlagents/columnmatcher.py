from typing import Optional, List, Dict, Any
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
import json
import re

class ColumnMatcher:
    def __init__(self, llm):
        self.llm = llm

    def _find_closest_column(self, column_name: str, available_columns: List[str], 
                            dataframe_description: Dict[str, Any] = None, 
                            context: str = "") -> Optional[str]:
        """
        Find the closest matching column name using LLM-based intelligent reasoning
        
        Args:
            column_name: The type of column needed (e.g., 'user_id_column', 'date_column')
            available_columns: List of available column names in the dataframe
            dataframe_description: Optional dictionary with schema, descriptions, and statistics
            context: Optional context about how this column will be used
            
        Returns:
            Best matching column name or None if no suitable match found
        """
        if not available_columns:
            return None
        
        # Create a comprehensive prompt for LLM-based column matching
        column_matching_prompt = PromptTemplate(
            input_variables=[
                "column_type_needed", "available_columns", "dataframe_description", 
                "context", "schema_info"
            ],
            template="""
            You are an expert data scientist who specializes in mapping function requirements to dataset columns.
            
            COLUMN TYPE NEEDED: {column_type_needed}
            
            AVAILABLE COLUMNS: {available_columns}
            
            DATAFRAME DESCRIPTION: {dataframe_description}
            
            SCHEMA INFORMATION: {schema_info}
            
            CONTEXT: {context}
            
            Your task is to identify the BEST matching column from the available columns that would be most suitable for the {column_type_needed} requirement.
            
            ANALYSIS PROCESS:
            1. Understand what type of data the {column_type_needed} parameter expects
            2. Examine each available column name for semantic meaning
            3. Consider the data types from the schema if available
            4. Look at any descriptions or sample values if provided
            5. Consider the context of how this column will be used
            6. Apply data science best practices for column selection
            
            MATCHING CRITERIA:
            - Semantic meaning of column names (e.g., 'user_id' for user identification)
            - Data types that make sense for the parameter (e.g., datetime for date columns)
            - Common naming conventions in data science
            - Context clues about the intended use
            - Avoid columns that would be inappropriate for the intended use
            
            RESPONSE FORMAT:
            Provide your analysis and conclusion in this exact format:
            
            ANALYSIS:
            [Your step-by-step reasoning about each potential column]
            
            BEST_MATCH: [exact_column_name_or_NONE]
            
            CONFIDENCE: [HIGH/MEDIUM/LOW]
            
            REASONING: [Brief explanation of why this column was selected or why no match was found]
            
            IMPORTANT:
            - Return NONE if no column is truly suitable (don't force a match)
            - Consider data types carefully (don't match text columns to numeric parameters)
            - Think about the intended use case
            - Be precise with column names (must match exactly from available columns)
            """
        )
        
        # Prepare schema information if available
        schema_info = "No schema information available"
        if dataframe_description:
            if 'schema' in dataframe_description:
                schema_details = []
                for col, dtype in dataframe_description['schema'].items():
                    if col in available_columns:
                        schema_details.append(f"{col}: {dtype}")
                if schema_details:
                    schema_info = "Column types: " + ", ".join(schema_details)
            
            # Add sample values or descriptions if available
            if 'sample_values' in dataframe_description:
                sample_info = []
                for col, samples in dataframe_description['sample_values'].items():
                    if col in available_columns:
                        sample_info.append(f"{col}: {samples}")
                if sample_info:
                    schema_info += "\nSample values: " + ", ".join(sample_info)
            
            if 'column_descriptions' in dataframe_description:
                desc_info = []
                for col, desc in dataframe_description['column_descriptions'].items():
                    if col in available_columns:
                        desc_info.append(f"{col}: {desc}")
                if desc_info:
                    schema_info += "\nColumn descriptions: " + ", ".join(desc_info)
        
        # Format dataframe description for the prompt
        df_desc_str = json.dumps(dataframe_description, indent=2) if dataframe_description else "No description provided"
        
        # Create the LLM chain
        column_matching_chain = column_matching_prompt | self.llm | StrOutputParser()
        
        try:
            # Run the LLM analysis
            result = column_matching_chain.invoke({
                "column_type_needed": column_name,
                "available_columns": ", ".join(available_columns),
                "dataframe_description": df_desc_str,
                "schema_info": schema_info,
                "context": context or f"Need to identify the best column for {column_name} parameter"
            })
            
            # Parse the LLM response
            best_match = None
            confidence = "LOW"
            reasoning = "No reasoning provided"
            
            # Extract BEST_MATCH
            best_match_pattern = r"BEST_MATCH:\s*(.*?)(?:\n|$)"
            match = re.search(best_match_pattern, result, re.IGNORECASE)
            if match:
                best_match_str = match.group(1).strip()
                if best_match_str.upper() == "NONE":
                    best_match = None
                elif best_match_str in available_columns:
                    best_match = best_match_str
                else:
                    # Try to find a case-insensitive match
                    for col in available_columns:
                        if col.lower() == best_match_str.lower():
                            best_match = col
                            break
            
            # Extract CONFIDENCE
            confidence_pattern = r"CONFIDENCE:\s*(.*?)(?:\n|$)"
            conf_match = re.search(confidence_pattern, result, re.IGNORECASE)
            if conf_match:
                confidence = conf_match.group(1).strip().upper()
            
            # Extract REASONING
            reasoning_pattern = r"REASONING:\s*(.*?)(?:\n|$)"
            reason_match = re.search(reasoning_pattern, result, re.IGNORECASE)
            if reason_match:
                reasoning = reason_match.group(1).strip()
            
            # Log the decision for debugging/transparency
            if hasattr(self, '_log_column_selection'):
                self._log_column_selection(column_name, best_match, confidence, reasoning, available_columns)
            
            # Only return high/medium confidence matches, or if explicitly requested
            if confidence in ["HIGH", "MEDIUM"] or not best_match:
                return best_match
            else:
                # For low confidence, return None to avoid bad matches
                return None
                
        except Exception as e:
            print(f"Error in LLM column matching for {column_name}: {e}")
            # Fallback: return None rather than trying a basic match
            # This forces the calling code to handle missing columns appropriately
            return None

    def _log_column_selection(self, column_type: str, selected_column: Optional[str], 
                            confidence: str, reasoning: str, available_columns: List[str]):
        """
        Optional logging method for column selection decisions
        
        Args:
            column_type: Type of column that was needed
            selected_column: Column that was selected (or None)
            confidence: Confidence level of the selection
            reasoning: LLM's reasoning for the selection
            available_columns: All available columns
        """
        print(f"🔍 Column Selection for {column_type}:")
        print(f"   Available: {', '.join(available_columns)}")
        print(f"   Selected: {selected_column or 'None'}")
        print(f"   Confidence: {confidence}")
        print(f"   Reasoning: {reasoning}")
        print()

    # Enhanced version with additional context awareness
    def _find_closest_column_with_context(self, column_name: str, available_columns: List[str],
                                        dataframe_description: Dict[str, Any] = None,
                                        context: str = "",
                                        function_name: str = "",
                                        analysis_type: str = "") -> Optional[str]:
        """
        Enhanced version that includes function and analysis context for better matching
        
        Args:
            column_name: The type of column needed
            available_columns: List of available column names
            dataframe_description: Optional dataframe metadata
            context: Context about the analysis task
            function_name: Name of the function this column is for
            analysis_type: Type of analysis being performed
            
        Returns:
            Best matching column name or None
        """
        if not available_columns:
            return None
        
        # Enhanced prompt with additional context
        enhanced_prompt = PromptTemplate(
            input_variables=[
                "column_type_needed", "available_columns", "dataframe_description", 
                "context", "function_name", "analysis_type", "schema_info"
            ],
            template="""
            You are an expert data scientist with deep knowledge of data analysis functions and column requirements.
            
            ANALYSIS CONTEXT:
            - Analysis Type: {analysis_type}
            - Function Name: {function_name}
            - Column Parameter: {column_type_needed}
            - Task Context: {context}
            
            AVAILABLE COLUMNS: {available_columns}
            
            DATAFRAME INFORMATION:
            {dataframe_description}
            
            SCHEMA DETAILS:
            {schema_info}
            
            Your expertise includes understanding:
            1. What data types different analysis functions expect
            2. Common column naming conventions in data science
            3. How different analysis types use different column types
            4. The semantic meaning of column names in business contexts
            
            SPECIFIC ANALYSIS KNOWLEDGE:
            - Time series analysis typically needs datetime columns for dates, numeric for values
            - Cohort analysis needs user IDs, dates, and value/event columns
            - Segmentation needs feature columns (numeric/categorical for clustering)
            - Risk analysis needs return/price columns (numeric)
            - Funnel analysis needs event, user ID, and timestamp columns
            
            TASK:
            Find the BEST column from available columns for the {column_type_needed} parameter in {function_name} function.
            
            STRICT REQUIREMENTS:
            - Consider the specific needs of {analysis_type} analysis
            - Match data types appropriately (datetime for dates, numeric for calculations, etc.)
            - Don't force matches - return NONE if no column is truly suitable
            - Consider business meaning and common patterns
            
            RESPONSE FORMAT:
            COLUMN_ANALYSIS:
            [Analyze each relevant column and why it would/wouldn't work for this specific use case]
            
            FUNCTION_REQUIREMENTS:
            [What this specific function parameter typically expects based on the analysis type]
            
            BEST_MATCH: [exact_column_name_or_NONE]
            
            CONFIDENCE: [HIGH/MEDIUM/LOW]
            
            REASONING: [Why this column is the best choice for this specific analysis function]
            """
        )
        
        # Prepare enhanced schema information
        schema_info = self._prepare_enhanced_schema_info(available_columns, dataframe_description)
        
        # Create enhanced LLM chain
        enhanced_chain = enhanced_prompt | self.llm | StrOutputParser()
        
        try:
            result = enhanced_chain.invoke({
                "column_type_needed": column_name,
                "available_columns": ", ".join(available_columns),
                "dataframe_description": json.dumps(dataframe_description, indent=2) if dataframe_description else "No description provided",
                "schema_info": schema_info,
                "context": context,
                "function_name": function_name,
                "analysis_type": analysis_type
            })
            
            # Parse result (same parsing logic as before)
            best_match = self._parse_llm_column_response(result, available_columns)
            
            return best_match
            
        except Exception as e:
            print(f"Error in enhanced LLM column matching: {e}")
            return None

    def _prepare_enhanced_schema_info(self, available_columns: List[str], 
                                    dataframe_description: Dict[str, Any] = None) -> str:
        """Prepare comprehensive schema information for LLM analysis"""
        schema_parts = []
        
        if not dataframe_description:
            return "No schema information available"
        
        # Add data types
        if 'schema' in dataframe_description:
            type_info = []
            for col in available_columns:
                if col in dataframe_description['schema']:
                    dtype = dataframe_description['schema'][col]
                    type_info.append(f"{col} ({dtype})")
            if type_info:
                schema_parts.append("Data Types: " + ", ".join(type_info))
        
        # Add statistics if available
        if 'stats' in dataframe_description:
            stats_info = []
            for col in available_columns:
                if col in dataframe_description['stats']:
                    col_stats = dataframe_description['stats'][col]
                    if isinstance(col_stats, dict):
                        key_stats = []
                        for stat_name in ['count', 'mean', 'min', 'max', 'unique']:
                            if stat_name in col_stats:
                                key_stats.append(f"{stat_name}: {col_stats[stat_name]}")
                        if key_stats:
                            stats_info.append(f"{col}: {', '.join(key_stats)}")
            if stats_info:
                schema_parts.append("Statistics: " + "; ".join(stats_info))
        
        # Add sample values
        if 'sample_values' in dataframe_description:
            sample_info = []
            for col in available_columns:
                if col in dataframe_description['sample_values']:
                    samples = dataframe_description['sample_values'][col]
                    if isinstance(samples, list):
                        sample_info.append(f"{col}: {samples[:3]}")  # Show first 3 samples
            if sample_info:
                schema_parts.append("Sample Values: " + "; ".join(sample_info))
        
        return "\n".join(schema_parts) if schema_parts else "Basic column list only"

    def _parse_llm_column_response(self, result: str, available_columns: List[str]) -> Optional[str]:
        """Parse LLM response to extract the best matching column"""
        # Extract BEST_MATCH
        best_match_pattern = r"BEST_MATCH:\s*(.*?)(?:\n|$)"
        match = re.search(best_match_pattern, result, re.IGNORECASE)
        
        if not match:
            return None
            
        best_match_str = match.group(1).strip()
        
        if best_match_str.upper() == "NONE":
            return None
        
        # Exact match
        if best_match_str in available_columns:
            return best_match_str
        
        # Case-insensitive match
        for col in available_columns:
            if col.lower() == best_match_str.lower():
                return col
        
        # No valid match found
        return None



    def find_column_match_with_schema(self, 
                                    column_type: str, 
                                    available_columns: List[str], 
                                    dataframe_description: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find the best matching column using LLM-based analysis with schema information, descriptions, and statistics
        
        Args:
            column_type: Type of column to find (e.g., 'event_column', 'user_id_column')
            available_columns: List of available column names in the dataframe
            dataframe_description: Dictionary containing schema, descriptions, and statistics
            
        Returns:
            Dictionary with matched column and reasoning
        """
        if not available_columns:
            return {
                "column": None,
                "reasoning": "No columns available to match."
            }
                
        try:
            # Extract comprehensive schema information
            schema_details = self._extract_comprehensive_schema_info(available_columns, dataframe_description)
            
            # Create an enhanced prompt template that doesn't rely on hardcoded keywords
            schema_prompt_template = PromptTemplate(
                input_variables=["column_type", "available_columns", "schema_details", "summary_text"],
                template="""
                You are an expert data scientist and column mapping specialist with deep knowledge of data analysis requirements.
                
                TASK: Find the BEST column from available columns that matches the requirements for: {column_type}
                
                AVAILABLE COLUMNS: {available_columns}
                
                COMPREHENSIVE SCHEMA INFORMATION:
                {schema_details}
                
                DATAFRAME SUMMARY:
                {summary_text}
                
                EXPERT ANALYSIS REQUIRED:
                As a data science expert, you understand that different analysis functions require specific types of data:
                
                1. COLUMN PURPOSE ANALYSIS:
                - What type of data would a {column_type} parameter typically contain?
                - What data types are appropriate for this use case?
                - What are common naming patterns for this type of column?
                - How is this column typically used in data analysis?
                
                2. SCHEMA-BASED EVALUATION:
                - Examine each column's data type for compatibility
                - Consider statistical properties (unique values, nulls, distribution)
                - Look at sample values to understand column content
                - Evaluate column names for semantic meaning
                
                3. BUSINESS CONTEXT UNDERSTANDING:
                - Apply domain knowledge about common data structures
                - Consider industry-standard naming conventions
                - Think about how this data would be collected and stored
                - Evaluate the logical flow of the analysis
                
                4. QUALITY ASSESSMENT:
                - Ensure the column has appropriate data quality
                - Check for sufficient non-null values
                - Verify the data type makes sense for the intended use
                - Consider uniqueness requirements where applicable
                
                ANALYSIS PROCESS:
                1. Define what {column_type} should contain based on its name and purpose
                2. Examine each available column for semantic fit
                3. Check data types and statistics for compatibility
                4. Evaluate sample values for content appropriateness
                5. Apply data science best practices for column selection
                6. Make a decision based on comprehensive analysis
                
                RESPONSE FORMAT:
                COLUMN_PURPOSE:
                [Explain what type of data {column_type} should contain and why]
                
                COLUMN_ANALYSIS:
                [For each relevant column, analyze its suitability including name, type, stats, and sample values]
                
                BEST_MATCH: [exact_column_name_or_NONE]
                
                CONFIDENCE: [HIGH/MEDIUM/LOW]
                
                REASONING: [Detailed explanation of why this column was selected, including specific evidence from schema]
                
                IMPORTANT:
                - Be rigorous in your analysis - don't force matches
                - Consider data types carefully (datetime for dates, numeric for metrics, etc.)
                - Return NONE if no column is truly suitable
                - Base decisions on actual data characteristics, not just column names
                """
            )
            
            # Create the LLM chain
            schema_column_matcher_chain = schema_prompt_template | self.llm | StrOutputParser()
            
            # Run the chain
            result = schema_column_matcher_chain.invoke({
                "column_type": column_type,
                "available_columns": ", ".join(available_columns),
                "schema_details": schema_details,
                "summary_text": dataframe_description.get('summary', 'No summary provided')
            })
            
            # Parse the result using the enhanced parser
            parsed_result = self._parse_enhanced_column_response(result, available_columns)
            
            return parsed_result
                
        except Exception as e:
            return {
                "column": None,
                "reasoning": f"Error finding column match using schema: {str(e)}"
            }

    def find_column_match(self, column_type: str, available_columns: List[str]) -> Dict[str, Any]:
        """
        Find the best matching column using LLM-based analysis without schema information
        
        Args:
            column_type: Type of column to find (e.g., 'event_column', 'user_id_column')
            available_columns: List of available column names in the dataframe
            
        Returns:
            Dictionary with matched column and reasoning
        """
        if not available_columns:
            return {
                "column": None,
                "reasoning": "No columns available to match."
            }
                
        try:
            # Create a comprehensive prompt template for column matching without schema
            cot_prompt_template = PromptTemplate(
                input_variables=["column_type", "available_columns"],
                template="""
                You are an expert data scientist specializing in column identification and data structure analysis.
                
                TASK: Identify the BEST column from the available columns that would be suitable for: {column_type}
                
                AVAILABLE COLUMNS: {available_columns}
                
                EXPERT KNOWLEDGE APPLICATION:
                You have extensive experience with data analysis and understand:
                
                1. COLUMN TYPE REQUIREMENTS:
                - What does a {column_type} parameter typically represent?
                - What kind of data would it contain?
                - What are the functional requirements for this column type?
                - How is this type of column typically used in analysis?
                
                2. NAMING CONVENTION EXPERTISE:
                - Industry-standard naming patterns for different column types
                - Common abbreviations and variations
                - Database and data warehouse naming conventions
                - Business terminology vs technical terminology
                
                3. SEMANTIC ANALYSIS:
                - Understand the meaning behind column names
                - Recognize synonyms and related terms
                - Identify columns that serve similar purposes
                - Apply context from the column type requirement
                
                4. DATA SCIENCE BEST PRACTICES:
                - Choose columns that will work well for the intended analysis
                - Consider data quality implications
                - Think about downstream usage requirements
                - Apply domain knowledge about common data structures
                
                ANALYSIS METHODOLOGY:
                1. Parse the {column_type} requirement to understand what's needed
                2. Examine each available column name for semantic relevance
                3. Apply knowledge of common naming patterns and conventions
                4. Consider synonyms and alternative representations
                5. Evaluate the logical fit for the intended use case
                6. Make an informed decision based on best practices
                
                DETAILED ANALYSIS:
                For each column, consider:
                - Does the name suggest it contains the right type of data?
                - Is this a common way to name this type of column?
                - Would this column logically serve the intended purpose?
                - Are there any red flags that suggest it's not suitable?
                
                RESPONSE FORMAT:
                REQUIREMENT_ANALYSIS:
                [Explain what {column_type} needs and what you're looking for]
                
                COLUMN_EVALUATION:
                [Evaluate each available column for its potential match to the requirement]
                
                BEST_MATCH: [exact_column_name_or_NONE]
                
                CONFIDENCE: [HIGH/MEDIUM/LOW]
                
                REASONING: [Explain why this column was selected based on semantic analysis and naming conventions]
                
                GUIDELINES:
                - Use your expertise to make intelligent matches
                - Don't force matches - return NONE if no column is truly suitable
                - Consider multiple possible naming conventions
                - Apply data science domain knowledge
                - Be conservative - better to return NONE than a bad match
                """
            )
            
            # Create the LLM chain  
            cot_column_matcher_chain = cot_prompt_template | self.llm | StrOutputParser()
            
            # Run the chain
            result = cot_column_matcher_chain.invoke({
                "column_type": column_type,
                "available_columns": ", ".join(available_columns)
            })
            
            # Parse the result
            parsed_result = self._parse_enhanced_column_response(result, available_columns)
            
            return parsed_result
                
        except Exception as e:
            return {
                "column": None,
                "reasoning": f"Error finding column match: {str(e)}"
            }

    def _extract_comprehensive_schema_info(self, available_columns: List[str], 
                                        dataframe_description: Dict[str, Any]) -> str:
        """
        Extract comprehensive schema information for LLM analysis
        
        Args:
            available_columns: List of available column names
            dataframe_description: Dictionary with schema, stats, and other metadata
            
        Returns:
            Formatted string with comprehensive schema information
        """
        schema_parts = []
        
        # Extract data types
        if 'schema' in dataframe_description:
            type_info = []
            for col in available_columns:
                if col in dataframe_description['schema']:
                    dtype = dataframe_description['schema'][col]
                    type_info.append(f"  {col}: {dtype}")
            if type_info:
                schema_parts.append("DATA TYPES:\n" + "\n".join(type_info))
        
        # Extract statistics
        if 'stats' in dataframe_description:
            stats_info = []
            for col in available_columns:
                if col in dataframe_description['stats']:
                    col_stats = dataframe_description['stats'][col]
                    if isinstance(col_stats, dict):
                        stat_details = []
                        for stat_name, stat_value in col_stats.items():
                            if stat_name in ['count', 'unique', 'mean', 'std', 'min', 'max', 'null_count']:
                                stat_details.append(f"{stat_name}: {stat_value}")
                        if stat_details:
                            stats_info.append(f"  {col}: {', '.join(stat_details)}")
            if stats_info:
                schema_parts.append("STATISTICS:\n" + "\n".join(stats_info))
        
        # Extract sample values
        if 'sample_values' in dataframe_description:
            sample_info = []
            for col in available_columns:
                if col in dataframe_description['sample_values']:
                    samples = dataframe_description['sample_values'][col]
                    if isinstance(samples, list) and samples:
                        # Show first few samples
                        sample_str = str(samples[:5])[1:-1]  # Remove brackets
                        sample_info.append(f"  {col}: {sample_str}")
            if sample_info:
                schema_parts.append("SAMPLE VALUES:\n" + "\n".join(sample_info))
        
        # Extract column descriptions if available
        if 'column_descriptions' in dataframe_description:
            desc_info = []
            for col in available_columns:
                if col in dataframe_description['column_descriptions']:
                    description = dataframe_description['column_descriptions'][col]
                    desc_info.append(f"  {col}: {description}")
            if desc_info:
                schema_parts.append("COLUMN DESCRIPTIONS:\n" + "\n".join(desc_info))
        
        # Extract data quality information
        if 'data_quality' in dataframe_description:
            quality_info = []
            for col in available_columns:
                if col in dataframe_description['data_quality']:
                    quality = dataframe_description['data_quality'][col]
                    if isinstance(quality, dict):
                        quality_details = []
                        for metric, value in quality.items():
                            quality_details.append(f"{metric}: {value}")
                        quality_info.append(f"  {col}: {', '.join(quality_details)}")
            if quality_info:
                schema_parts.append("DATA QUALITY:\n" + "\n".join(quality_info))
        
        return "\n\n".join(schema_parts) if schema_parts else "No detailed schema information available"

    def _parse_enhanced_column_response(self, result: str, available_columns: List[str]) -> Dict[str, Any]:
        """
        Parse the enhanced LLM response to extract column match and metadata
        
        Args:
            result: LLM response text
            available_columns: List of available columns for validation
            
        Returns:
            Dictionary with column, reasoning, and confidence
        """
        parsed = {
            "column": None,
            "reasoning": "No clear reasoning provided.",
            "confidence": "LOW"
        }
        
        try:
            # Extract BEST_MATCH
            best_match_pattern = r"BEST_MATCH:\s*(.*?)(?:\n|$)"
            match = re.search(best_match_pattern, result, re.IGNORECASE)
            if match:
                column_name = match.group(1).strip()
                if column_name.upper() == "NONE":
                    parsed["column"] = None
                elif column_name in available_columns:
                    parsed["column"] = column_name
                else:
                    # Try case-insensitive match
                    for col in available_columns:
                        if col.lower() == column_name.lower():
                            parsed["column"] = col
                            break
            
            # Extract CONFIDENCE
            confidence_pattern = r"CONFIDENCE:\s*(.*?)(?:\n|$)"
            conf_match = re.search(confidence_pattern, result, re.IGNORECASE)
            if conf_match:
                confidence = conf_match.group(1).strip().upper()
                if confidence in ["HIGH", "MEDIUM", "LOW"]:
                    parsed["confidence"] = confidence
            
            # Extract REASONING
            reasoning_pattern = r"REASONING:\s*(.*?)(?:\n(?:[A-Z_]+:|$))"
            reasoning_match = re.search(reasoning_pattern, result, re.IGNORECASE | re.DOTALL)
            if reasoning_match:
                parsed["reasoning"] = reasoning_match.group(1).strip()
            
            # If no reasoning found, try to extract from other sections
            if parsed["reasoning"] == "No clear reasoning provided.":
                # Try to extract from COLUMN_ANALYSIS or COLUMN_EVALUATION
                analysis_pattern = r"(?:COLUMN_ANALYSIS|COLUMN_EVALUATION):\s*(.*?)(?:\n(?:[A-Z_]+:|$))"
                analysis_match = re.search(analysis_pattern, result, re.IGNORECASE | re.DOTALL)
                if analysis_match:
                    parsed["reasoning"] = analysis_match.group(1).strip()[:200] + "..."  # Truncate if too long
        
        except Exception as e:
            parsed["reasoning"] = f"Error parsing LLM response: {str(e)}"
        
        return parsed

    def _log_column_matching_decision(self, column_type: str, result: Dict[str, Any], 
                                    available_columns: List[str], has_schema: bool = False):
        """
        Log the column matching decision for debugging and transparency
        
        Args:
            column_type: Type of column that was requested
            result: Result dictionary from column matching
            available_columns: List of available columns
            has_schema: Whether schema information was available
        """
        print(f"🔍 Column Matching Decision for '{column_type}':")
        print(f"   Method: {'Schema-based' if has_schema else 'Name-based'} LLM analysis")
        print(f"   Available columns: {', '.join(available_columns)}")
        print(f"   Selected: {result['column'] or 'None'}")
        print(f"   Confidence: {result.get('confidence', 'Unknown')}")
        print(f"   Reasoning: {result['reasoning'][:100]}{'...' if len(result['reasoning']) > 100 else ''}")
        print()

    # Enhanced wrapper functions that include logging
    def find_column_match_with_logging(self, column_type: str, available_columns: List[str], 
                                    dataframe_description: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Wrapper function that adds logging to column matching
        """
        if dataframe_description:
            result = self.find_column_match_with_schema(column_type, available_columns, dataframe_description)
            self._log_column_matching_decision(column_type, result, available_columns, has_schema=True)
        else:
            result = self.find_column_match(column_type, available_columns)
            self._log_column_matching_decision(column_type, result, available_columns, has_schema=False)
        
        return result

    # Example integration method
    def integrate_enhanced_column_matching(self):
        """
        Integration method to replace existing column matching in your classes
        
        Replace calls to the old functions with these enhanced versions:
        
        OLD:
        result = self.find_column_match_with_schema(column_type, columns, description)
        
        NEW: 
        result = find_column_match_with_schema(self, column_type, columns, description)
        
        Or better yet, use the wrapper with logging:
        result = find_column_match_with_logging(self, column_type, columns, description)
        """
        pass


# Example usage integration
"""
# In your existing class, replace the _find_closest_column method with:

def _find_closest_column(self, column_name: str, available_columns: List[str]) -> Optional[str]:
    # Use the enhanced version with additional context if available
    return _find_closest_column_with_context(
        self, column_name, available_columns,
        dataframe_description=getattr(self, 'dataframe_description', None),
        context=getattr(self, 'current_context', ''),
        function_name=getattr(self, 'current_function', ''),
        analysis_type=getattr(self, 'analysis_type', '')
    )
"""
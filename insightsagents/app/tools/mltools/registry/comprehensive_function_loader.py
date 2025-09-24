"""
Comprehensive Function Loader for Enhanced ML Function Registry

This module provides a comprehensive loader that combines function specifications,
usage examples, code snippets, and instructions from JSON files to create
rich function metadata for better code generation.
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from langchain_core.documents import Document
import logging
import chromadb
from chromadb.config import Settings

from app.storage.documents import DocumentChromaStore, CHROMA_STORE_PATH, create_langchain_doc_util

logger = logging.getLogger("comprehensive-function-loader")


@dataclass
class ComprehensiveFunctionData:
    """Comprehensive function data structure combining all sources."""
    # Basic function info
    function_name: str
    pipe_name: str
    module: str
    category: str
    subcategory: str
    description: str
    complexity: str
    
    # Function specification
    required_params: List[Dict[str, Any]]
    optional_params: List[Dict[str, Any]]
    outputs: Dict[str, Any]
    data_requirements: List[str]
    use_cases: List[str]
    tags: List[str]
    keywords: List[str]
    
    # Code and implementation
    source_code: str
    function_signature: str
    docstring: str
    
    # Examples and usage
    examples: List[Dict[str, Any]]
    usage_patterns: List[str]
    code_snippets: List[str]
    usage_description: str
    
    # Instructions and guidance
    instructions: List[Dict[str, Any]]
    business_cases: List[str]
    natural_language_questions: List[str]
    configuration_hints: Dict[str, str]
    typical_parameters: Dict[str, Any]
    
    # Historical data and insights
    historical_rules: List[Dict[str, Any]]
    insights: List[Dict[str, Any]]
    examples_store: List[Dict[str, Any]]
    
    # Metadata
    confidence_score: float
    llm_generated: bool
    source_files: List[str]


class ComprehensiveFunctionLoader:
    """Comprehensive loader that combines all function data sources."""
    
    def __init__(
        self,
        toolspecs_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/toolspecs",
        instructions_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/instructions",
        usage_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/usage_examples",
        code_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/code_examples"
    ):
        """
        Initialize the comprehensive function loader.
        
        Args:
            toolspecs_path: Path to function specifications JSON files
            instructions_path: Path to instructions JSON files
            usage_examples_path: Path to usage examples JSON files
            code_examples_path: Path to code examples JSON files
        """
        self.toolspecs_path = Path(toolspecs_path)
        self.instructions_path = Path(instructions_path)
        self.usage_examples_path = Path(usage_examples_path)
        self.code_examples_path = Path(code_examples_path)
        
        # Validate paths
        for path_name, path in [
            ("toolspecs", self.toolspecs_path),
            ("instructions", self.instructions_path),
            ("usage_examples", self.usage_examples_path),
            ("code_examples", self.code_examples_path)
        ]:
            if not path.exists():
                logger.warning(f"{path_name} path does not exist: {path}")
    
    def load_all_functions(self) -> List[ComprehensiveFunctionData]:
        """
        Load all functions with comprehensive data from all sources.
        
        Returns:
            List of ComprehensiveFunctionData objects
        """
        logger.info("Loading comprehensive function data from all sources...")
        
        # Load function specifications
        function_specs = self._load_function_specifications()
        logger.info(f"Loaded {len(function_specs)} function specifications")
        
        # Load instructions
        instructions_data = self._load_instructions()
        logger.info(f"Loaded instructions for {len(instructions_data)} functions")
        
        # Load usage examples
        usage_examples = self._load_usage_examples()
        logger.info(f"Loaded usage examples for {len(usage_examples)} functions")
        
        # Load code examples
        code_examples = self._load_code_examples()
        logger.info(f"Loaded code examples for {len(code_examples)} functions")
        
        # Combine all data
        comprehensive_functions = []
        for func_name, spec in function_specs.items():
            try:
                comprehensive_func = self._create_comprehensive_function(
                    func_name=func_name,
                    spec=spec,
                    instructions=instructions_data.get(func_name, []),
                    usage_examples=usage_examples.get(func_name, []),
                    code_examples=code_examples.get(func_name, [])
                )
                comprehensive_functions.append(comprehensive_func)
            except Exception as e:
                logger.error(f"Error creating comprehensive function for {func_name}: {e}")
                continue
        
        logger.info(f"Created {len(comprehensive_functions)} comprehensive function definitions")
        return comprehensive_functions
    
    def _load_function_specifications(self) -> Dict[str, Dict[str, Any]]:
        """Load function specifications from toolspecs JSON files."""
        function_specs = {}
        
        if not self.toolspecs_path.exists():
            logger.warning(f"Toolspecs path does not exist: {self.toolspecs_path}")
            return function_specs
        
        for json_file in self.toolspecs_path.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                if "functions" in data:
                    for func_name, func_data in data["functions"].items():
                        # Add source file information
                        func_data["source_file"] = str(json_file.name)
                        function_specs[func_name] = func_data
                        
            except Exception as e:
                logger.error(f"Error loading function specs from {json_file}: {e}")
                continue
        
        return function_specs
    
    def _load_instructions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load instructions from instructions JSON files."""
        instructions_data = {}
        
        if not self.instructions_path.exists():
            logger.warning(f"Instructions path does not exist: {self.instructions_path}")
            return instructions_data
        
        for json_file in self.instructions_path.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    examples = json.load(f)
                
                for example in examples:
                    if isinstance(example, dict):
                        func_name = example.get("function", "")
                        if func_name:
                            if func_name not in instructions_data:
                                instructions_data[func_name] = []
                            
                            instruction_data = {
                                "query": example.get("query", ""),
                                "category": example.get("category", ""),
                                "inputs": example.get("inputs", {}),
                                "example": example.get("example", ""),
                                "instructions": example.get("instructions", {}),
                                "patterns": example.get("patterns", {}),
                                "input_data": example.get("input_data", {}),
                                "output_data": example.get("output_data", {}),
                                "code_snippet": example.get("code_snippet", ""),
                                "source_file": str(json_file.name)
                            }
                            instructions_data[func_name].append(instruction_data)
                            
            except Exception as e:
                logger.error(f"Error loading instructions from {json_file}: {e}")
                continue
        
        return instructions_data
    
    def _load_usage_examples(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load usage examples from usage_examples JSON files."""
        usage_examples = {}
        
        if not self.usage_examples_path.exists():
            logger.warning(f"Usage examples path does not exist: {self.usage_examples_path}")
            return usage_examples
        
        for json_file in self.usage_examples_path.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    examples = json.load(f)
                
                for example in examples:
                    if isinstance(example, dict):
                        func_name = example.get("function", "")
                        if func_name:
                            if func_name not in usage_examples:
                                usage_examples[func_name] = []
                            
                            usage_data = {
                                "query": example.get("query", ""),
                                "example": example.get("example", ""),
                                "description": example.get("description", ""),
                                "category": example.get("category", ""),
                                "inputs": example.get("inputs", {}),
                                "code_snippet": example.get("code_snippet", ""),
                                "source_file": str(json_file.name)
                            }
                            usage_examples[func_name].append(usage_data)
                            
            except Exception as e:
                logger.error(f"Error loading usage examples from {json_file}: {e}")
                continue
        
        return usage_examples
    
    def _load_code_examples(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load code examples from code_examples JSON files."""
        code_examples = {}
        
        if not self.code_examples_path.exists():
            logger.warning(f"Code examples path does not exist: {self.code_examples_path}")
            return code_examples
        
        for json_file in self.code_examples_path.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    examples = json.load(f)
                
                for example in examples:
                    if isinstance(example, dict) and "page_content" in example:
                        # Parse page content to extract function name
                        page_content = example.get("page_content", "")
                        try:
                            content_data = json.loads(page_content)
                            func_name = content_data.get("function_name", "")
                            if func_name:
                                if func_name not in code_examples:
                                    code_examples[func_name] = []
                                
                                code_data = {
                                    "page_content": page_content,
                                    "metadata": example.get("metadata", {}),
                                    "source_file": str(json_file.name)
                                }
                                code_examples[func_name].append(code_data)
                        except json.JSONDecodeError:
                            continue
                            
            except Exception as e:
                logger.error(f"Error loading code examples from {json_file}: {e}")
                continue
        
        return code_examples
    
    def _create_comprehensive_function(
        self,
        func_name: str,
        spec: Dict[str, Any],
        instructions: List[Dict[str, Any]],
        usage_examples: List[Dict[str, Any]],
        code_examples: List[Dict[str, Any]]
    ) -> ComprehensiveFunctionData:
        """Create a comprehensive function data object from all sources."""
        
        # Extract basic info from spec
        pipe_name = spec.get("pipe_name", "UnknownPipe")
        module = spec.get("module", "unknown")
        category = spec.get("category", "unknown")
        subcategory = spec.get("subcategory", "")
        description = spec.get("description", "")
        complexity = spec.get("complexity", "intermediate")
        
        # Extract parameters
        required_params = spec.get("required_params", [])
        optional_params = spec.get("optional_params", [])
        outputs = spec.get("outputs", {})
        
        # Extract metadata
        data_requirements = spec.get("data_requirements", [])
        use_cases = spec.get("use_cases", [])
        tags = spec.get("tags", [])
        keywords = spec.get("keywords", [])
        confidence_score = spec.get("confidence_score", 0.8)
        llm_generated = spec.get("llm_generated", True)
        
        # Process instructions
        processed_instructions = []
        business_cases = []
        natural_language_questions = []
        configuration_hints = {}
        typical_parameters = {}
        
        for instruction in instructions:
            processed_instructions.append(instruction)
            
            # Extract business cases
            if "instructions" in instruction:
                inst_data = instruction["instructions"]
                if "business_case" in inst_data:
                    business_cases.append(inst_data["business_case"])
                if "natural_language_questions" in inst_data:
                    natural_language_questions.extend(inst_data["natural_language_questions"])
                if "configuration_hints" in inst_data:
                    configuration_hints.update(inst_data["configuration_hints"])
                if "typical_parameters" in inst_data:
                    typical_parameters.update(inst_data["typical_parameters"])
        
        # Process examples and code snippets
        processed_examples = []
        code_snippets = []
        usage_patterns = []
        usage_description = ""
        
        # Add instruction examples
        for instruction in instructions:
            if "example" in instruction and instruction["example"]:
                processed_examples.append({
                    "type": "instruction_example",
                    "content": instruction["example"],
                    "query": instruction.get("query", ""),
                    "source": "instructions"
                })
                code_snippets.append(instruction["example"])
        
        # Add usage examples
        for usage in usage_examples:
            if "example" in usage and usage["example"]:
                processed_examples.append({
                    "type": "usage_example",
                    "content": usage["example"],
                    "query": usage.get("query", ""),
                    "source": "usage_examples"
                })
                code_snippets.append(usage["example"])
                
                # Extract usage description from usage examples
                if "description" in usage and usage["description"]:
                    if usage_description:
                        usage_description += " " + usage["description"]
                    else:
                        usage_description = usage["description"]
        
        # Add code examples
        for code_ex in code_examples:
            if "page_content" in code_ex:
                try:
                    content_data = json.loads(code_ex["page_content"])
                    if "example" in content_data:
                        processed_examples.append({
                            "type": "code_example",
                            "content": content_data["example"],
                            "query": content_data.get("query", ""),
                            "source": "code_examples"
                        })
                        code_snippets.append(content_data["example"])
                except json.JSONDecodeError:
                    continue
        
        # Generate usage patterns from examples
        for example in processed_examples:
            if "content" in example:
                # Extract function call patterns
                content = example["content"]
                if func_name in content:
                    # Find the function call pattern
                    lines = content.split('\n')
                    for line in lines:
                        if func_name in line and '(' in line:
                            usage_patterns.append(line.strip())
                            break
        
        # If no usage description found, use the function description as fallback
        if not usage_description:
            usage_description = description
        
        # Create source code placeholder (would be filled from actual function source)
        source_code = f"def {func_name}(...):\n    \"\"\"{description}\"\"\"\n    pass"
        function_signature = f"def {func_name}(...)"
        docstring = description
        
        # Create historical rules and insights (placeholder for now)
        historical_rules = []
        insights = []
        examples_store = processed_examples.copy()
        
        # Collect source files
        source_files = [spec.get("source_file", "")]
        for instruction in instructions:
            if "source_file" in instruction:
                source_files.append(instruction["source_file"])
        for usage in usage_examples:
            if "source_file" in usage:
                source_files.append(usage["source_file"])
        for code_ex in code_examples:
            if "source_file" in code_ex:
                source_files.append(code_ex["source_file"])
        
        source_files = list(set(filter(None, source_files)))
        
        return ComprehensiveFunctionData(
            function_name=func_name,
            pipe_name=pipe_name,
            module=module,
            category=category,
            subcategory=subcategory,
            description=description,
            complexity=complexity,
            required_params=required_params,
            optional_params=optional_params,
            outputs=outputs,
            data_requirements=data_requirements,
            use_cases=use_cases,
            tags=tags,
            keywords=keywords,
            source_code=source_code,
            function_signature=function_signature,
            docstring=docstring,
            examples=processed_examples,
            usage_patterns=usage_patterns,
            code_snippets=code_snippets,
            usage_description=usage_description,
            instructions=processed_instructions,
            business_cases=business_cases,
            natural_language_questions=natural_language_questions,
            configuration_hints=configuration_hints,
            typical_parameters=typical_parameters,
            historical_rules=historical_rules,
            insights=insights,
            examples_store=examples_store,
            confidence_score=confidence_score,
            llm_generated=llm_generated,
            source_files=source_files
        )
    
    def create_langchain_documents(self, comprehensive_functions: List[ComprehensiveFunctionData]) -> List[Document]:
        """
        Convert comprehensive function data to LangChain documents for ChromaDB storage.
        
        Args:
            comprehensive_functions: List of comprehensive function data
            
        Returns:
            List of LangChain documents
        """
        documents = []
        
        for func_data in comprehensive_functions:
            try:
                # Create comprehensive page content
                page_content = self._create_comprehensive_page_content(func_data)
                
                # Create metadata
                metadata = {
                    "function_name": func_data.function_name,
                    "pipe_name": func_data.pipe_name,
                    "module": func_data.module,
                    "category": func_data.category,
                    "subcategory": func_data.subcategory,
                    "complexity": func_data.complexity,
                    "tags": ",".join(func_data.tags),
                    "keywords": ",".join(func_data.keywords),
                    "use_cases": ",".join(func_data.use_cases),
                    "data_requirements": ",".join(func_data.data_requirements),
                    "has_examples": len(func_data.examples) > 0,
                    "has_instructions": len(func_data.instructions) > 0,
                    "has_code_snippets": len(func_data.code_snippets) > 0,
                    "examples_count": len(func_data.examples),
                    "instructions_count": len(func_data.instructions),
                    "code_snippets_count": len(func_data.code_snippets),
                    "business_cases_count": len(func_data.business_cases),
                    "confidence_score": func_data.confidence_score,
                    "llm_generated": func_data.llm_generated,
                    "source_files": ",".join(func_data.source_files),
                    "type": "comprehensive_function_definition"
                }
                
                # Create document
                doc = Document(
                    page_content=page_content,
                    metadata=metadata
                )
                documents.append(doc)
                
            except Exception as e:
                logger.error(f"Error creating document for {func_data.function_name}: {e}")
                continue
        
        return documents
    
    def _create_comprehensive_page_content(self, func_data: ComprehensiveFunctionData) -> str:
        """Create comprehensive page content for a function."""
        content_parts = [
            f"FUNCTION: {func_data.function_name}",
            f"PIPE: {func_data.pipe_name}",
            f"MODULE: {func_data.module}",
            f"CATEGORY: {func_data.category}",
            f"SUBCATEGORY: {func_data.subcategory}",
            f"COMPLEXITY: {func_data.complexity}",
            f"CONFIDENCE: {func_data.confidence_score}",
            "",
            f"DESCRIPTION: {func_data.description}",
            "",
            "PARAMETERS:",
        ]
        
        # Add required parameters
        if func_data.required_params:
            content_parts.append("Required:")
            for param in func_data.required_params:
                if isinstance(param, dict):
                    param_str = f"  - {param.get('name', 'unknown')}: {param.get('type', 'Any')} - {param.get('description', '')}"
                else:
                    param_str = f"  - {param}"
                content_parts.append(param_str)
        
        # Add optional parameters
        if func_data.optional_params:
            content_parts.append("Optional:")
            for param in func_data.optional_params:
                if isinstance(param, dict):
                    param_str = f"  - {param.get('name', 'unknown')}: {param.get('type', 'Any')} - {param.get('description', '')}"
                else:
                    param_str = f"  - {param}"
                content_parts.append(param_str)
        
        content_parts.extend([
            "",
            f"OUTPUTS: {func_data.outputs}",
            "",
            f"USE CASES: {', '.join(func_data.use_cases)}",
            "",
            f"DATA REQUIREMENTS: {', '.join(func_data.data_requirements)}",
            "",
            f"TAGS: {', '.join(func_data.tags)}",
            f"KEYWORDS: {', '.join(func_data.keywords)}",
        ])
        
        # Add business cases
        if func_data.business_cases:
            content_parts.extend([
                "",
                "BUSINESS CASES:",
            ])
            for i, case in enumerate(func_data.business_cases, 1):
                content_parts.append(f"  {i}. {case}")
        
        # Add natural language questions
        if func_data.natural_language_questions:
            content_parts.extend([
                "",
                "NATURAL LANGUAGE QUESTIONS:",
            ])
            for i, question in enumerate(func_data.natural_language_questions, 1):
                content_parts.append(f"  {i}. {question}")
        
        # Add configuration hints
        if func_data.configuration_hints:
            content_parts.extend([
                "",
                "CONFIGURATION HINTS:",
            ])
            for key, hint in func_data.configuration_hints.items():
                content_parts.append(f"  {key}: {hint}")
        
        # Add typical parameters
        if func_data.typical_parameters:
            content_parts.extend([
                "",
                "TYPICAL PARAMETERS:",
            ])
            for key, value in func_data.typical_parameters.items():
                content_parts.append(f"  {key}: {value}")
        
        # Add examples
        if func_data.examples:
            content_parts.extend([
                "",
                "EXAMPLES:",
            ])
            for i, example in enumerate(func_data.examples, 1):
                content_parts.append(f"  Example {i} ({example.get('type', 'unknown')}):")
                content_parts.append(f"    Query: {example.get('query', 'N/A')}")
                content_parts.append(f"    Code: {example.get('content', 'N/A')}")
                content_parts.append("")
        
        # Add code snippets
        if func_data.code_snippets:
            content_parts.extend([
                "",
                "CODE SNIPPETS:",
            ])
            for i, snippet in enumerate(func_data.code_snippets, 1):
                content_parts.append(f"  Snippet {i}:")
                content_parts.append(f"    {snippet}")
                content_parts.append("")
        
        # Add usage patterns
        if func_data.usage_patterns:
            content_parts.extend([
                "",
                "USAGE PATTERNS:",
            ])
            for i, pattern in enumerate(func_data.usage_patterns, 1):
                content_parts.append(f"  {i}. {pattern}")
        
        # Add instructions
        if func_data.instructions:
            content_parts.extend([
                "",
                "INSTRUCTIONS:",
            ])
            for i, instruction in enumerate(func_data.instructions, 1):
                content_parts.append(f"  Instruction {i}:")
                content_parts.append(f"    Query: {instruction.get('query', 'N/A')}")
                if "instructions" in instruction:
                    inst_data = instruction["instructions"]
                    if "business_case" in inst_data:
                        content_parts.append(f"    Business Case: {inst_data['business_case']}")
                    if "data_keywords" in inst_data:
                        content_parts.append(f"    Data Keywords: {', '.join(inst_data['data_keywords'])}")
                content_parts.append("")
        
        return "\n".join(content_parts)


def load_comprehensive_functions(
    toolspecs_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/toolspecs",
    instructions_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/instructions",
    usage_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/usage_examples",
    code_examples_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/code_examples"
) -> Tuple[List[ComprehensiveFunctionData], List[Document]]:
    """
    Load comprehensive function data and create LangChain documents.
    
    Args:
        toolspecs_path: Path to function specifications
        instructions_path: Path to instructions
        usage_examples_path: Path to usage examples
        code_examples_path: Path to code examples
        
    Returns:
        Tuple of (comprehensive_functions, langchain_documents)
    """
    loader = ComprehensiveFunctionLoader(
        toolspecs_path=toolspecs_path,
        instructions_path=instructions_path,
        usage_examples_path=usage_examples_path,
        code_examples_path=code_examples_path
    )
    
    # Load comprehensive functions
    comprehensive_functions = loader.load_all_functions()
    
    # Create LangChain documents
    documents = loader.create_langchain_documents(comprehensive_functions)
    
    return comprehensive_functions, documents



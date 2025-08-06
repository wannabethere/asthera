import json
import os
from typing import List, Dict, Any,Optional
from langchain_core.documents import Document
from pathlib import Path
import chromadb
from langchain.schema import HumanMessage, SystemMessage
from app.storage.documents import DocumentChromaStore, CHROMA_STORE_PATH, create_langchain_doc_util

#from chatbot.multiagent_planners.nodes.recommender_agent import RetrievalFunctionsAgent
from app.utils.insight_utils import  extract_insights_nb
from langchain_openai import ChatOpenAI

class CodeExampleLoader:
    def __init__(self, base_path: str = ""):
        """
        Initialize the code example loader.
        
        Args:
            base_path (str): Base path to the code examples directory
        """
        self.base_path = Path(base_path)
        if not self.base_path.exists():
            raise ValueError(f"Base path {base_path} does not exist")
    
    def load_examples(self) -> List[Document]:
        """
        Load all code examples from JSON files and convert them to LangChain Documents.
        
        Returns:
            List[Document]: List of LangChain Documents containing code examples
        """
        documents = []
        
        # Get all JSON files in the directory
        json_files = list(self.base_path.glob("*.json"))
        
        for json_file in json_files:
            if json_file.stat().st_size == 0:  # Skip empty files
                continue
            
            try:
                # Read and parse JSON file
                with open(json_file, 'r') as f:
                    examples = json.load(f)
                print(f"examples loaded from {json_file} length: {len(examples)}")
                # Convert each example to a Document
                for example in examples:
                    if "page_content" and "metadata" in example:
                        # Extract page_content and metadata
                        page_content = example.get("page_content", "")
                        metadata = example.get("metadata", {})
                        
                        # Add source file information to metadata
                        metadata["source_file"] = str(json_file.name)
                        print("metadata",metadata)
                        print("page_content",page_content)
                        # Create LangChain Document
                        doc = Document(
                            page_content=page_content,
                            metadata=metadata
                        )
                        documents.append(doc)
                print("documents added length: ",len(documents))
            except json.JSONDecodeError as e:
                print(f"Error parsing {json_file}: {e}")
            except Exception as e:
                print(f"Error processing {json_file}: {e}")
        
        return documents
    
    def get_examples_by_category(self, category: str) -> List[Document]:
        """
        Get all examples from a specific category.
        
        Args:
            category (str): Category to filter by (e.g., 'time_series_analysis', 'funnel_analysis')
            
        Returns:
            List[Document]: List of LangChain Documents matching the category
        """
        all_docs = self.load_examples()
        return [doc for doc in all_docs if doc.metadata.get("category") == category]
    
    def get_examples_by_function(self, function_name: str) -> List[Document]:
        """
        Get all examples for a specific function.
        
        Args:
            function_name (str): Function name to filter by
            
        Returns:
            List[Document]: List of LangChain Documents matching the function name
        """
        all_docs = self.load_examples()
        return [doc for doc in all_docs if doc.metadata.get("function_name") == function_name]

class CodeFunctionLoader:
    """
    Loads function definitions from JSON files and creates Document objects.
    """
    def __init__(self, json_files_path: str = ""):
        """
        Initialize the loader with path to JSON file.
        
        Args:
            json_file_path (str): Path to the JSON file containing function definitions
        """
        self.directory_path = Path(json_files_path)
        if not self.directory_path.exists():
            raise ValueError(f"Base path {json_files_path} does not exist")
        
    def load_functions(self,json_file_path:str) -> List[Document]:
        """
        Load function definitions from JSON and convert to Documents.
        
        Returns:
            List[Document]: List of LangChain Documents containing function definitions
        """
        documents = []
        
        try:
            with open(json_file_path) as f:
                data = json.load(f)
            print(f"data: {json_file_path}")
            if "functions" in data:
                for func_name, func_data in data["functions"].items():
                    #print("func_name",func_name)
                    # Create page content from function data
                    page_content = json.dumps({
                        "function_name": func_name,
                        "description": func_data.get("description", ""),
                        "category": func_data.get("category", ""),
                        "type_of_operation": func_data.get("type_of_operation", ""),
                        "inputs": func_data.get("inputs", {}),
                        "required_params": func_data.get("required_params", {}),
                        "optional_params": func_data.get("optional_params", {}),
                        "outputs": func_data.get("outputs", {})
                    })
                    # Create metadata
                    metadata = {
                        "function_name": func_name,
                        "source_file": str(json_file_path),
                        "type": "function_definition",
                        "category": func_data.get("category", ""),
                        "type_of_operation": func_data.get("type_of_operation", ""),
                        "description": func_data.get("description", "")
                    }
                  
                    # Create Document
                    doc = Document(
                        page_content=json.dumps(page_content),
                        metadata=metadata
                    )
                    documents.append(doc)        
        except json.JSONDecodeError as e:
            print(f"Error parsing {self.json_file_path}: {e}")
        except Exception as e:
            print(f"Error processing {self.json_file_path}: {e}")
        return documents

    def load_functions_as_dict(self,json_file_path:str) -> List[Document]:
        """
        Load function definitions from JSON and convert to Documents.
        
        Returns:
            List[Document]: List of LangChain Documents containing function definitions
        """
        documents = []
        
        try:
            with open(json_file_path) as f:
                data = json.load(f)
            
            if "functions" in data:
                for func_name, func_data in data["functions"].items():
                    documents.append({"function_name": func_name,
                        "description": func_data.get("description", ""),
                        "inputs": func_data.get("inputs", {}),
                        #"required_params": func_data.get("required_params", {}),
                        #"optional_params": func_data.get("optional_params", {}),
                        "outputs": func_data.get("outputs", {})})
        except json.JSONDecodeError as e:
            print(f"Error parsing {self.json_file_path}: {e}")
        except Exception as e:
            print(f"Error processing {self.json_file_path}: {e}")
        return documents
    
    def load_all_functions(self) -> List[Document]:
        """
        Load function definitions from all JSON files in a directory.
        
        Args:
            directory_path (str): Path to directory containing JSON function definition files
            
        Returns:
            List[Document]: Combined list of Documents containing function definitions from all files
        """
        all_documents = []
        
        try:
            # Get all JSON files in directory
            json_files = [f for f in os.listdir(self.directory_path) if f.endswith('.json')]
            
            # Process each JSON file
            for json_file in json_files:
                file_path = os.path.join(self.directory_path, json_file)
                print(f"file_path: {file_path}")
                documents = self.load_functions(file_path)
                print(f"documents: done for {json_file} length: {len(documents)}")
                #print(f"documents: {documents}")
                all_documents.extend(documents)
                
        except Exception as e:
            print(f"Error processing directory {self.directory_path}: {e}")
            
        return all_documents
    
    def load_all_docs_as_funcs(self) -> List[Document]:
        """
        Load all documents as function definitions.
        
        Returns:
            List[Document]: List of LangChain Documents containing function definitions
        """
        all_documents = []
        
        try:
            # Get all JSON files in directory
            json_files = [f for f in os.listdir(self.directory_path) if f.endswith('.json')]
            
            # Process each JSON file
            for json_file in json_files:
                file_path = os.path.join(self.directory_path, json_file)
                
                if file_path.endswith("analysis_tools.json"):
                    continue
                documents = self.load_functions_as_dict(file_path)
                #print(f"documents: {documents}")
                all_documents.extend(documents)
                
        except Exception as e:
            print(f"Error processing directory {self.directory_path}: {e}")
            
        return all_documents

class UsageExampleLoader:
    """
    Loads usage examples from JSON files and creates Document objects.
    """
    def __init__(self, base_path: str = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/instructions"):
        """
        Initialize the usage example loader.
        
        Args:
            base_path (str): Base path to the usage examples directory
        """
        self.base_path = Path(base_path)
        if not self.base_path.exists():
            raise ValueError(f"Base path {base_path} does not exist")
    
    def load_examples(self) -> List[Document]:
        """
        Load all usage examples from JSON files and convert them to LangChain Documents.
        
        Returns:
            List[Document]: List of LangChain Documents containing usage examples
        """
        documents = []
        
        # Get all JSON files in the directory
        json_files = list(self.base_path.glob("*.json"))
        
        for json_file in json_files:
            if json_file.stat().st_size == 0:  # Skip empty files
                continue
            
            try:
                # Read and parse JSON file
                with open(json_file, 'r') as f:
                    examples = json.load(f)
                print(f"Usage examples loaded from {json_file} length: {len(examples)}")
                
                # Convert each example to a Document
                for example in examples:
                    if isinstance(example, dict):
                        # Extract instructions and patterns for better searchability
                        instructions = example.get("instructions", {})
                        patterns = example.get("patterns", {})
                        
                        # Create searchable text from instructions
                        searchable_instructions = ""
                        if instructions:
                            business_case = instructions.get("business_case", "")
                            natural_language_questions = instructions.get("natural_language_questions", [])
                            data_keywords = instructions.get("data_keywords", [])
                            configuration_hints = instructions.get("configuration_hints", {})
                            typical_parameters = instructions.get("typical_parameters", {})
                            
                            searchable_instructions = f"{business_case} {' '.join(natural_language_questions)} {' '.join(data_keywords)}"
                            if configuration_hints:
                                searchable_instructions += f" {' '.join([f'{k}: {v}' for k, v in configuration_hints.items()])}"
                            if typical_parameters:
                                searchable_instructions += f" {' '.join([f'{k}: {v}' for k, v in typical_parameters.items()])}"
                        
                        # Create searchable text from patterns
                        searchable_patterns = ""
                        if patterns:
                            function_patterns = patterns.get("function_patterns", [])
                            metrics_patterns = patterns.get("metrics_patterns", [])
                            num_patterns = patterns.get("num_patterns", [])
                            time_patterns = patterns.get("time_patterns", [])
                            
                            searchable_patterns = f"{' '.join(function_patterns)} {' '.join(metrics_patterns)} {' '.join(num_patterns)} {' '.join(time_patterns)}"
                        
                        # Create page content from example data with new format support
                        page_content = json.dumps({
                            "query": example.get("query", ""),
                            "example": example.get("example", ""),
                            "description": example.get("description", ""),
                            "function_name": example.get("function", ""),
                            "category": example.get("category", ""),
                            "inputs": example.get("inputs", {}),
                            "instructions": example.get("instructions", {}),
                            "patterns": example.get("patterns", {}),
                            "searchable_instructions": searchable_instructions,
                            "searchable_patterns": searchable_patterns,
                            "input_data": example.get("input_data", {}),
                            "output_data": example.get("output_data", {}),
                            "code_snippet": example.get("code_snippet", "")
                        })
                        
                        # Create metadata with enhanced information
                        metadata = {
                            "source_file": str(json_file.name),
                            "type": "usage_example",
                            "function_name": example.get("function", ""),
                            "category": example.get("category", ""),
                            "example_type": example.get("example_type", ""),
                            "query": example.get("query", ""),
                            "has_instructions": bool(example.get("instructions")),
                            "has_patterns": bool(example.get("patterns"))
                        }
                        
                        # Create LangChain Document
                        doc = Document(
                            page_content=page_content,
                            metadata=metadata
                        )
                        documents.append(doc)
                        
            except json.JSONDecodeError as e:
                print(f"Error parsing {json_file}: {e}")
            except Exception as e:
                print(f"Error processing {json_file}: {e}")
        
        return documents
    
    def get_examples_by_function(self, function_name: str) -> List[Document]:
        """
        Get all usage examples for a specific function.
        
        Args:
            function_name (str): Function name to filter by
            
        Returns:
            List[Document]: List of LangChain Documents matching the function name
        """
        all_docs = self.load_examples()
        return [doc for doc in all_docs if doc.metadata.get("function_name") == function_name]
    
    def get_examples_by_category(self, category: str) -> List[Document]:
        """
        Get all usage examples from a specific category.
        
        Args:
            category (str): Category to filter by
            
        Returns:
            List[Document]: List of LangChain Documents matching the category
        """
        all_docs = self.load_examples()
        return [doc for doc in all_docs if doc.metadata.get("category") == category]
    
    def get_examples_by_query(self, query: str) -> List[Document]:
        """
        Get all usage examples that match a specific query.
        
        Args:
            query (str): Query text to filter by
            
        Returns:
            List[Document]: List of LangChain Documents matching the query
        """
        all_docs = self.load_examples()
        return [doc for doc in all_docs if doc.metadata.get("query") == query]
    
    def get_examples_with_instructions(self) -> List[Document]:
        """
        Get all usage examples that have instructions.
        
        Returns:
            List[Document]: List of LangChain Documents with instructions
        """
        all_docs = self.load_examples()
        return [doc for doc in all_docs if doc.metadata.get("has_instructions", False)]
    
    def get_examples_with_patterns(self) -> List[Document]:
        """
        Get all usage examples that have patterns.
        
        Returns:
            List[Document]: List of LangChain Documents with patterns
        """
        all_docs = self.load_examples()
        return [doc for doc in all_docs if doc.metadata.get("has_patterns", False)]
    
    def search_examples_by_keyword(self, keyword: str) -> List[Document]:
        """
        Search for examples by keyword in query, instructions, or patterns.
        
        Args:
            keyword (str): Keyword to search for
            
        Returns:
            List[Document]: List of LangChain Documents containing the keyword
        """
        all_docs = self.load_examples()
        matching_docs = []
        
        for doc in all_docs:
            try:
                content = json.loads(doc.page_content)
                query = content.get("query", "").lower()
                searchable_instructions = content.get("searchable_instructions", "").lower()
                searchable_patterns = content.get("searchable_patterns", "").lower()
                function_name = content.get("function_name", "").lower()
                category = content.get("category", "").lower()
                
                if (keyword.lower() in query or 
                    keyword.lower() in searchable_instructions or 
                    keyword.lower() in searchable_patterns or
                    keyword.lower() in function_name or
                    keyword.lower() in category):
                    matching_docs.append(doc)
            except (json.JSONDecodeError, KeyError):
                continue
                
        return matching_docs
    
    def get_examples_by_business_case(self, business_case_keyword: str) -> List[Document]:
        """
        Get examples that match a specific business case keyword.
        
        Args:
            business_case_keyword (str): Business case keyword to search for
            
        Returns:
            List[Document]: List of LangChain Documents matching the business case
        """
        all_docs = self.load_examples()
        matching_docs = []
        
        for doc in all_docs:
            try:
                content = json.loads(doc.page_content)
                instructions = content.get("instructions", {})
                business_case = instructions.get("business_case", "").lower()
                
                if business_case_keyword.lower() in business_case:
                    matching_docs.append(doc)
            except (json.JSONDecodeError, KeyError):
                continue
                
        return matching_docs
    
    def get_examples_by_data_keywords(self, keywords: list) -> List[Document]:
        """
        Get examples that match specific data keywords from instructions.
        
        Args:
            keywords (list): List of data keywords to search for
            
        Returns:
            List[Document]: List of LangChain Documents matching the data keywords
        """
        all_docs = self.load_examples()
        matching_docs = []
        
        for doc in all_docs:
            try:
                content = json.loads(doc.page_content)
                instructions = content.get("instructions", {})
                data_keywords = instructions.get("data_keywords", [])
                
                # Check if any of the provided keywords match the data keywords
                if any(keyword.lower() in [kw.lower() for kw in data_keywords] for keyword in keywords):
                    matching_docs.append(doc)
            except (json.JSONDecodeError, KeyError):
                continue
                
        return matching_docs
    
    def get_examples_by_natural_language_question(self, question_keyword: str) -> List[Document]:
        """
        Get examples that contain specific natural language questions.
        
        Args:
            question_keyword (str): Keyword to search for in natural language questions
            
        Returns:
            List[Document]: List of LangChain Documents matching the question keyword
        """
        all_docs = self.load_examples()
        matching_docs = []
        
        for doc in all_docs:
            try:
                content = json.loads(doc.page_content)
                instructions = content.get("instructions", {})
                natural_language_questions = instructions.get("natural_language_questions", [])
                
                # Check if the keyword appears in any of the natural language questions
                if any(question_keyword.lower() in question.lower() for question in natural_language_questions):
                    matching_docs.append(doc)
            except (json.JSONDecodeError, KeyError):
                continue
                
        return matching_docs

def load_usage_examples(base_path:str):
    usage_example_loader = UsageExampleLoader(base_path=base_path)
    return usage_example_loader.load_examples()




def initialize_insights_vectorstore(vectorstore:DocumentChromaStore):
    
    insights_list = []
    
    for i in range(1,100):
        insights = extract_insights_nb(exp_dict={"do_sensitivity": False,'dataset_id':i, "slope": 2})
        #print("insights",insights)
        if (insights is not None and len(insights)>0) and (insights['metadata'] is not None and len(insights['metadata'])>0) and (insights['data'] is not None and len(insights['data'])>0):
            #id,doc = create_langchain_doc_util(metadata=insights['metadata'], data=insights['data'])
            insights_list.append(insights)
            #print("insight doc",insights)
    print("insights_list",len(insights_list))
    vectorstore.add_documents(insights_list)
    
    return vectorstore

def main():
    # Example usage
    
    usage_example_loader = CodeExampleLoader(base_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/code_examples/")
    function_loader = CodeFunctionLoader(json_files_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/toolspecs")
    usage_example_loader_new = UsageExampleLoader(base_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/instructions")
    
    # Load all examples
    all_functions = function_loader.load_all_functions()
    #print("all_functions",all_functions)
    client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
    examples_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_examples_collection")
    functions_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_spec_collection")
    insights_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_insights_collection")
    usage_examples_vectorstore = DocumentChromaStore(persistent_client=client,collection_name="usage_examples_collection")
    #print(f"Loaded {len(all_functions)} total examples")
   
    
    usage_examples = usage_example_loader.load_examples()
    new_usage_examples = usage_example_loader_new.load_examples()
    print(f"Loaded {len(new_usage_examples)} usage examples")
    
    # Load usage examples into ChromaDB
    #usage_examples_vectorstore.add_documents(new_usage_examples)
    print("Usage examples loaded into ChromaDB")
    
    #print("examples",examples)
    usage_examples_vectorstore.add_documents(new_usage_examples)
    examples_vectorstore.add_documents(usage_examples)
    functions_vectorstore.add_documents(all_functions)
    initialize_insights_vectorstore(insights_vectorstore)
        
    # Get examples by function
    search_query = "How do I create lead values for multiple columns in panel data with groups?"
    results_functions  = functions_vectorstore.semantic_search(search_query, k=2)
    print("results_functions",results_functions)
    functions =functions_vectorstore.semantic_search('lead',k=3)
    for function in functions:
        function_spec = json.loads(json.loads(function['content']))
        if function_spec['function_name'] == 'lead':
            print(function_spec)

    results_examples = examples_vectorstore.semantic_search(search_query, k=2)
    print("results_examples",results_examples)
    results_insights = insights_vectorstore.semantic_search(search_query, k=2)
    print("results_insights",results_insights)
    print("length of results_examples",len(results_examples))
    print("length of results_functions",len(results_functions))
    print("length of results_insights",len(results_insights))
    #print(results_insights)


    search_query = "How do I analyze funnel performance across different user segments with my event data?"
    functions =functions_vectorstore.semantic_search('analyze_funnel_by_segment',k=3)
    for function in functions:
        function_spec = json.loads(json.loads(function['content']))
        if function_spec['function_name'] == 'analyze_funnel_by_segment':
            print(function_spec)
    
    #results_functions = functions_vectorstore.semantic_search(search_query, k=2)    
    #results_examples = examples_vectorstore.semantic_search(search_query, k=2)
    #results_insights = insights_vectorstore.semantic_search(search_query, k=2)
    #print(results_insights)

    results_functions = functions_vectorstore.semantic_searches(query_texts=[search_query], n_results=5)    
    results_examples = examples_vectorstore.semantic_searches(query_texts=[search_query], n_results=5)
    results_insights = insights_vectorstore.semantic_searches(query_texts=[search_query], n_results=5)
    results_usage_examples = usage_examples_vectorstore.semantic_searches(query_texts=[search_query], n_results=5)
    print("results_functions",results_functions)
    print("results_examples",results_examples)
    print("results_insights",results_insights)
    print("results_usage_examples",results_usage_examples)
    print("length of results_usage_examples",len(results_usage_examples))
    results_functions = functions_vectorstore.semantic_searches(query_texts=["mean"], n_results=5)    
    results_examples = examples_vectorstore.semantic_searches(query_texts=["mean"], n_results=5)
    results_insights = insights_vectorstore.semantic_searches(query_texts=["mean"], n_results=5)
    results_usage_examples = usage_examples_vectorstore.semantic_searches(query_texts=["mean"], n_results=5)
    print("results_functions anamoly_detection",results_functions)
    print("results_examples anamoly_detection",results_examples)
    print("results_insights anamoly_detection",results_insights)
    print("results_usage_examples anamoly_detection",results_usage_examples)
    print("length of results_usage_examples",len(results_usage_examples))


    results_functions = functions_vectorstore.semantic_searches(query_texts=["GroupBy"], n_results=5)    
    results_examples = examples_vectorstore.semantic_searches(query_texts=["GroupBy"], n_results=5)
    results_insights = insights_vectorstore.semantic_searches(query_texts=["GroupBy"], n_results=5)
    results_usage_examples = usage_examples_vectorstore.semantic_searches(query_texts=["GroupBy"], n_results=5)
    print("results_functions time_series_analysis",results_functions)
    print("results_examples time_series_analysis",results_examples)
    print("results_insights time_series_analysis",results_insights)
    print("results_usage_examples time_series_analysis",results_usage_examples)
    print("length of results_usage_examples",len(results_usage_examples))
    #print(results_examples)
    #print(results_insights)

    #os.environ["OPENAI_API_KEY"] = "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"
    #llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    #functions_retrieval_agent = RetrievalFunctionsAgent(functions_vectorstore,llm)
    # Example of accessing document content
    #results_functions,content = functions_retrieval_agent.retrieve(search_query)
    #print("results_functions",results_functions)
    #print("content",content)
    
    # Example: Search for usage examples by function name
    print("\n--- Usage Examples Search Demo ---")
    #usage_examples_for_lead = usage_example_loader_new.get_examples_by_function("lead")
    #print(f"Found {len(usage_examples_for_lead)} usage examples for 'lead' function")
    
    # Example: Search for usage examples by category
    #usage_examples_by_category = usage_example_loader_new.get_examples_by_category("time_series_analysis")
    #print(f"Found {len(usage_examples_by_category)} usage examples for 'time_series_analysis' category")
    
    # Test new functionality with the updated format
    print("\n--- Testing Updated UsageExampleLoader with New Format ---")
    updated_usage_loader = UsageExampleLoader(base_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genieml/data/meta/instructions")
    
    # Load examples with new format
    new_format_examples = updated_usage_loader.load_examples()
    print(f"Loaded {len(new_format_examples)} examples with new format")
    
    if new_format_examples:
        # Test search by function
        anomaly_examples = updated_usage_loader.get_examples_by_function("detect_statistical_outliers")
        print(f"Found {len(anomaly_examples)} examples for 'detect_statistical_outliers'")
        
        # Test search by category
        anomaly_category_examples = updated_usage_loader.get_examples_by_category("anomaly_detection")
        print(f"Found {len(anomaly_category_examples)} examples for 'anomaly_detection' category")
        
        # Test search by keyword
        temperature_examples = updated_usage_loader.search_examples_by_keyword("temperature")
        print(f"Found {len(temperature_examples)} examples containing 'temperature'")
        
        # Test search by business case
        quality_control_examples = updated_usage_loader.get_examples_by_business_case("Quality Control")
        print(f"Found {len(quality_control_examples)} examples with 'Quality Control' business case")
        
        # Test examples with instructions
        examples_with_instructions = updated_usage_loader.get_examples_with_instructions()
        print(f"Found {len(examples_with_instructions)} examples with instructions")
        
        # Show first example structure
        first_example = new_format_examples[0]
        print(f"\nFirst example metadata keys: {list(first_example.metadata.keys())}")
        print(f"Has instructions: {first_example.metadata.get('has_instructions')}")
        print(f"Has patterns: {first_example.metadata.get('has_patterns')}")
        print(f"Query: {first_example.metadata.get('query')}")
        
        # Test search by data keywords
        sensor_examples = updated_usage_loader.get_examples_by_data_keywords(["sensor", "temperature"])
        print(f"Found {len(sensor_examples)} examples with sensor/temperature data keywords")
        
        # Test search by natural language question
        unusual_examples = updated_usage_loader.get_examples_by_natural_language_question("unusual")
        print(f"Found {len(unusual_examples)} examples with 'unusual' in natural language questions")
    
if __name__ == "__main__":
    #function_spec = json.loads('"{\\"function_name\\": \\"lead\\", \\"description\\": \\"Create lead (future) values for specified columns\\", \\"inputs\\": {}, \\"required_params\\": [\\"columns\\"], \\"optional_params\\": [\\"periods\\", \\"time_column\\", \\"group_columns\\", \\"suffix\\"], \\"outputs\\": {\\"type\\": \\"Callable\\", \\"description\\": \\"Function that creates lead values in a TimeSeriesPipe\\"}}"')
    #print(type(function_spec))
    #print(json.loads(function_spec))
    main()
import json
import os
from typing import List, Dict, Any,Optional
from langchain_core.documents import Document
from pathlib import Path
import chromadb
from langchain.schema import HumanMessage, SystemMessage
from genimel.services.documents import DocumentChromaStore, CHROMA_STORE_PATH, create_langchain_doc_util

#from chatbot.multiagent_planners.nodes.recommender_agent import RetrievalFunctionsAgent
from genimel.agents.utils.agent_utils import  extract_insights_nb
from langchain_openai import ChatOpenAI

class CodeExampleLoader:
    def __init__(self, base_path: str = "/unstructured/end-to-end-chatbot/meta/code_examples"):
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
    def __init__(self, json_files_path: str = "/unstructured/end-to-end-chatbot/meta/tools"):
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
                    # Create page content from function data
                    page_content = json.dumps({
                        "function_name": func_name,
                        "description": func_data.get("description", ""),
                        "inputs": func_data.get("inputs", {}),
                        "required_params": func_data.get("required_params", {}),
                        "optional_params": func_data.get("optional_params", {}),
                        "outputs": func_data.get("outputs", {})
                    })
                    # Create metadata
                    metadata = {
                        "function_name": func_name,
                        "source_file": str(json_file_path),
                        "type": "function_definition"
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
    
    example_loader = CodeExampleLoader(base_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genimel/meta/code_examples/")
    function_loader = CodeFunctionLoader(json_files_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/genimel/meta/toolspecs")
    # Load all examples
    #all_functions = function_loader.load_all_functions()
    #print("all_functions",all_functions)
    client = chromadb.PersistentClient(path=CHROMA_STORE_PATH)
    examples_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_examples_collection")
    functions_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_spec_collection")
    insights_vectorstore  = DocumentChromaStore(persistent_client=client,collection_name="tools_insights_collection")
    #print(f"Loaded {len(all_functions)} total examples")
   
    
    #examples = example_loader.load_examples()
    #print("examples",examples)
    #examples_vectorstore.add_documents(examples)
    #functions_vectorstore.add_documents(all_functions)
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
    #print(results_examples)
    #print(results_insights)


    search_query = "Help me segment customers based on their purchase history?"
    functions =functions_vectorstore.semantic_search('analyze_funnel_by_segment',k=3)
    for function in functions:
        function_spec = json.loads(json.loads(function['content']))
        if function_spec['function_name'] == 'analyze_funnel_by_segment':
            print(function_spec)
    
    results_functions = functions_vectorstore.semantic_search(search_query, k=2)    
    results_examples = examples_vectorstore.semantic_search(search_query, k=2)
    results_insights = insights_vectorstore.semantic_search(search_query, k=2)
    print(results_insights)
    #print(results_examples)
    #print(results_insights)

    os.environ["OPENAI_API_KEY"] = "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"
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
    #functions_retrieval_agent = RetrievalFunctionsAgent(functions_vectorstore,llm)
    # Example of accessing document content
    #results_functions,content = functions_retrieval_agent.retrieve(search_query)
    #print("results_functions",results_functions)
    #print("content",content)
    
if __name__ == "__main__":
    function_spec = json.loads('"{\\"function_name\\": \\"lead\\", \\"description\\": \\"Create lead (future) values for specified columns\\", \\"inputs\\": {}, \\"required_params\\": [\\"columns\\"], \\"optional_params\\": [\\"periods\\", \\"time_column\\", \\"group_columns\\", \\"suffix\\"], \\"outputs\\": {\\"type\\": \\"Callable\\", \\"description\\": \\"Function that creates lead values in a TimeSeriesPipe\\"}}"')
    print(type(function_spec))
    print(json.loads(function_spec))
    main()
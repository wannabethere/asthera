import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Union
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import BaseOutputParser
from langchain.callbacks import get_openai_callback
import json
import logging
from datetime import datetime
from app.core.dependencies import get_llm
from app.core.pandas_engine import convert_to_json_serializable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SummaryOutputParser(BaseOutputParser):
    """Custom parser for structured summary outputs"""
    
    def parse(self, text: str) -> Dict[str, Any]:
        try:
            # Try to parse as JSON first
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback to simple text parsing
            return {
                "summary": text.strip(),
                "key_insights": [],
                "metrics": {},
                "recommendations": []
            }
        except Exception as e:
            # Handle any other parsing errors
            logger.warning(f"Error parsing LLM output: {e}")
            return {
                "summary": str(text).strip(),
                "key_insights": [],
                "metrics": {},
                "recommendations": []
            }

class RecursiveDataSummarizer:
    """
    LangChain-based recursive summarizer for large datasets
    Generates natural language summaries suitable for reports
    """
    
    def __init__(
        self,
        chunk_size: int = 150,
        language: str = "English",
        llm: ChatOpenAI = None
    ):
        print(f"RecursiveDataSummarizer init - LLM type: {type(llm)}")
        print(f"RecursiveDataSummarizer init - LLM value: {llm}")
        
        self.llm = llm or get_llm()  # Use provided LLM or get default
        print(f"RecursiveDataSummarizer init - Final LLM type: {type(self.llm)}")
        print(f"RecursiveDataSummarizer init - Final LLM value: {self.llm}")
        
        self.chunk_size = chunk_size
        self.output_parser = SummaryOutputParser()
        
        # Initialize prompt templates
        self._setup_prompts()
        
        # Initialize chains
        self._setup_chains()
        
        # Track processing stats
        self.stats = {
            "total_rows": 0,
            "chunks_processed": 0,
            "summarization_levels": 0,
            "total_tokens": 0,
            "total_cost": 0.0
        }
    
    def _setup_prompts(self):
        """Setup different prompt templates for various summarization levels"""
        
        # Chunk-level summarization prompt
        self.chunk_prompt = PromptTemplate(
            input_variables=["data_chunk", "data_description"],
            template="""
You are a data analyst creating a summary for a business report. 

Data Description: {data_description}

Analyze this data chunk and provide a concise summary:

{data_chunk}

Please provide:
1. Key patterns and trends observed
2. Notable statistics or metrics
3. Any anomalies or outliers
4. Important insights for business stakeholders

Keep the summary clear, quantitative where possible, and suitable for executive reporting.

Summary:
"""
        )
        
        # Intermediate summarization prompt
        self.intermediate_prompt = PromptTemplate(
            input_variables=["summaries", "data_description"],
            template="""
You are consolidating multiple data summaries into a coherent section summary for a business report.

Data Description: {data_description}

Previous summaries to consolidate:
{summaries}

Create a unified summary that:
1. Identifies overarching themes and patterns
2. Consolidates key metrics and statistics
3. Highlights the most important business insights
4. Maintains quantitative details where relevant

Provide a well-structured summary suitable for inclusion in an executive report.

Consolidated Summary:
"""
        )
        
        # Final executive summary prompt
        self.final_prompt = PromptTemplate(
            input_variables=["summaries", "data_description", "total_rows"],
            template="""
You are creating the final executive summary for a comprehensive data analysis report.

Dataset: {data_description}
Total Records Analyzed: {total_rows:,}

Section summaries to synthesize:
{summaries}

Create a polished executive summary that includes:

**EXECUTIVE SUMMARY**
- High-level overview of key findings
- Most critical business insights
- Primary trends and patterns

**KEY METRICS**
- Important quantitative findings
- Performance indicators
- Statistical highlights


Make this suitable for senior executives and stakeholders. Use clear, professional language with quantitative support where appropriate.
**Keep the summary in less than 500 words.**

Final Executive Summary:
"""
        )
    
    def _setup_chains(self):
        """Initialize LangChain chains for different summarization levels using modern pipe operator"""
        print(f"_setup_chains - LLM type: {type(self.llm)}")
        print(f"_setup_chains - LLM value: {self.llm}")
        
        if not self.llm:
            raise ValueError("LLM is not initialized. Please provide a valid LLM instance.")
        
        # Create chains using the modern pipe operator pattern
        self.chunk_chain = self.chunk_prompt | self.llm | self.output_parser
        print(f"_setup_chains - chunk_chain created: {type(self.chunk_chain)}")
        
        self.intermediate_chain = self.intermediate_prompt | self.llm | self.output_parser
        print(f"_setup_chains - intermediate_chain created: {type(self.intermediate_chain)}")
        
        self.final_chain = self.final_prompt | self.llm | self.output_parser
        print(f"_setup_chains - final_chain created: {type(self.final_chain)}")
    


    def _prepare_data_chunk(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to string format for LLM processing"""
        try:
            # Basic statistics
            stats = df.describe(include='all').to_string()
            
            # Sample rows
            sample_size = min(5, len(df))
            sample_rows = df.head(sample_size).to_string()
            
            # Column info - convert data types to strings for JSON serialization
            data_types_dict = {}
            for col, dtype in df.dtypes.items():
                try:
                    # Handle pandas data types properly
                    if hasattr(dtype, 'name'):
                        data_types_dict[str(col)] = dtype.name
                    else:
                        data_types_dict[str(col)] = str(dtype)
                except Exception as e:
                    logger.warning(f"Failed to convert data type for column {col}: {e}")
                    data_types_dict[str(col)] = "unknown"
            
            missing_values_dict = {}
            for col, count in df.isnull().sum().items():
                missing_values_dict[str(col)] = int(count)
            
            # Ensure all values are strings before concatenation
            column_info = f"Columns: {list(df.columns)}\n"
            column_info += f"Data types: {str(data_types_dict)}\n"
            column_info += f"Total rows: {str(len(df))}\n"
            column_info += f"Missing values: {str(missing_values_dict)}\n"
            
            return f"""
{column_info}

SAMPLE DATA:
{sample_rows}

STATISTICAL SUMMARY:
{stats}
"""
        except Exception as e:
            logger.error(f"Error in _prepare_data_chunk: {e}")
            # Fallback: return basic information
            return f"""
Error preparing data chunk: {str(e)}

Basic info:
- Shape: {str(df.shape) if hasattr(df, 'shape') else 'unknown'}
- Columns: {str(list(df.columns)) if hasattr(df, 'columns') else 'unknown'}
- Total rows: {str(len(df)) if hasattr(df, '__len__') else 'unknown'}
"""
    
    def _chunk_data(self, df: pd.DataFrame) -> List[pd.DataFrame]:
        """Split DataFrame into manageable chunks"""
        chunks = []
        for i in range(0, len(df), self.chunk_size):
            chunk = df.iloc[i:i + self.chunk_size].copy()
            chunks.append(chunk)
        return chunks
    
    def _summarize_chunk(self, data: Union[pd.DataFrame, Dict[str, Any]], data_description: str) -> str:
        """Summarize a single data chunk"""
        try:
            # Ensure data_description is a string
            data_description_str = str(data_description) if data_description is not None else "Unknown data"
            
            # Check if chain is properly initialized
            if not hasattr(self, 'chunk_chain') or self.chunk_chain is None:
                raise ValueError("Chunk chain is not properly initialized. Please check LLM configuration.")
            
            # Convert DataFrame to summary format if needed
            if isinstance(data, pd.DataFrame):
                chunk_text = self._prepare_data_chunk(data)
            else:
                # Format dictionary data for summarization with JSON serialization handling
                def convert_to_serializable(obj):
                    """Convert pandas objects to JSON-serializable formats"""
                    import pandas as pd
                    
                    # Handle pandas data types specifically
                    if hasattr(obj, 'dtype'):
                        if isinstance(obj.dtype, pd.api.extensions.ExtensionDtype):
                            return str(obj.dtype)
                        elif hasattr(obj, 'to_dict'):
                            try:
                                return obj.to_dict()
                            except Exception:
                                return str(obj)
                        else:
                            return str(obj)
                    elif isinstance(obj, dict):
                        return {str(k): convert_to_serializable(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_to_serializable(item) for item in obj]
                    elif isinstance(obj, (int, float, str, bool, type(None))):
                        return obj
                    elif hasattr(obj, '__class__') and 'pandas' in str(obj.__class__):
                        # Handle any pandas objects
                        return str(obj)
                    elif hasattr(obj, '__class__') and 'numpy' in str(obj.__class__):
                        # Handle numpy objects
                        return str(obj)
                    else:
                        return str(obj)
                
                # Convert data to JSON-serializable format
                serializable_data = convert_to_serializable(data)
                try:
                    chunk_text = json.dumps(serializable_data, indent=2)
                except Exception as json_error:
                    logger.warning(f"JSON serialization failed, using string representation: {json_error}")
                    # Fallback: convert to string representation
                    chunk_text = str(serializable_data)
            
            with get_openai_callback() as cb:
                result = self.chunk_chain.invoke({
                    "data_chunk": chunk_text,
                    "data_description": data_description_str
                })
                
                # Update stats
                self.stats["total_tokens"] += cb.total_tokens
                self.stats["total_cost"] += cb.total_cost
                self.stats["chunks_processed"] += 1
               
            
            # Handle different result types
            if isinstance(result, str):
                return result
            elif isinstance(result, dict):
                return result.get("summary", str(result))
            else:
                return str(result)
            
        except Exception as e:
            logger.error(f"Error summarizing chunk: {e}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error details: {str(e)}")
            return f"Error processing data: {str(e)}"
    
    def _combine_summaries(self, summaries: List[str], data_description: str, is_final: bool = False) -> str:
        """Combine multiple summaries into one"""
        try:
            # Ensure data_description is a string
            data_description_str = str(data_description) if data_description is not None else "Unknown data"
            
            # Check if chains are properly initialized
            if not hasattr(self, 'final_chain') or not hasattr(self, 'intermediate_chain'):
                raise ValueError("Chains are not properly initialized. Please check LLM configuration.")
            
            summaries_text = "\n\n".join([f"Summary {i+1}:\n{summary}" for i, summary in enumerate(summaries)])
            
            with get_openai_callback() as cb:
                if is_final:
                    result = self.final_chain.invoke({
                        "summaries": summaries_text,
                        "data_description": data_description_str,
                        "total_rows": self.stats["total_rows"]
                    })
                else:
                    result = self.intermediate_chain.invoke({
                        "summaries": summaries_text,
                        "data_description": data_description_str
                    })
                
                # Update stats
                self.stats["total_tokens"] += cb.total_tokens
                self.stats["total_cost"] += cb.total_cost
            
            
            
            # Handle different result types
            if isinstance(result, str):
                return result
            elif isinstance(result, dict):
                return result.get("summary", str(result))
            else:
                return str(result)
            
        except Exception as e:
            logger.error(f"Error combining summaries: {e}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error details: {str(e)}")
            return f"Error combining {len(summaries)} summaries: {str(e)}"
    
   
    
    def _recursive_summarize(
        self,
        data: Union[pd.DataFrame, Dict[str, Any]],
        data_description: str,
        progress_callback: Optional[callable] = None,
        level: int = 0
    ) -> str:
        """
        Generate a single batch summary for the input data
        
        Args:
            data: Input data as DataFrame or dictionary
            data_description: Description of the data
            progress_callback: Optional callback for progress updates
            level: Current recursion level (not used in single batch mode)
            
        Returns:
            str: Generated summary
        """
        try:
            # Ensure data_description is a string
            data_description_str = str(data_description) if data_description is not None else "Unknown data"
            
            print(f"Summarizing data: {data}")
            if isinstance(data, pd.DataFrame):
                if progress_callback:
                   progress_callback(f"Summarizing DataFrame with {len(data)} rows")
                print(f"Summarizing data: {data}")
                # Convert data types to strings to ensure JSON serialization
                data_types_dict = {}
                for col, dtype in data.dtypes.items():
                    try:
                        # Handle pandas data types properly
                        if hasattr(dtype, 'name'):
                            data_types_dict[str(col)] = dtype.name
                        else:
                            data_types_dict[str(col)] = str(dtype)
                    except Exception as e:
                        logger.warning(f"Failed to convert data type for column {col}: {e}")
                        data_types_dict[str(col)] = "unknown"
                
                # Convert missing values to JSON-serializable format
                missing_values_dict = {}
                for col, count in data.isnull().sum().items():
                    missing_values_dict[str(col)] = int(count)
                
                # Convert basic stats to JSON-serializable format
                basic_stats_dict = {}
                try:
                    describe_df = data.describe(include='all')
                    for col in describe_df.columns:
                        col_stats = {}
                        for stat, value in describe_df[col].items():
                            if pd.isna(value):
                                col_stats[str(stat)] = None
                            elif isinstance(value, (int, float)):
                                col_stats[str(stat)] = float(value) if isinstance(value, float) else int(value)
                            else:
                                col_stats[str(stat)] = str(value)
                        basic_stats_dict[str(col)] = col_stats
                except Exception as e:
                    logger.warning(f"Could not generate basic stats: {e}")
                    basic_stats_dict = {}
                
                # Prepare DataFrame summary with JSON-serializable data
                # Convert sample data to JSON-serializable format
                sample_df = data.head(5)
                sample_data_serializable = convert_to_json_serializable(sample_df)
                
                summary_data = {
                    "shape": list(data.shape),  # Convert tuple to list
                    "columns": [str(col) for col in data.columns],
                    "data_types": data_types_dict,
                    "missing_values": missing_values_dict,
                    "sample_data": sample_data_serializable.get("data", []),
                    "basic_stats": basic_stats_dict
                }
                
                # Generate summary using the chunk summarizer
                return self._summarize_chunk(summary_data, data_description_str)
                
            elif isinstance(data, dict):
                if progress_callback:
                    progress_callback("Summarizing dictionary data")
               
                # If the dictionary contains a DataFrame, convert it
                if "data" in data and isinstance(data["data"], pd.DataFrame):
                    df = data["data"]
                    return self._recursive_summarize(df, data_description_str, progress_callback)
                
                # Otherwise, summarize the dictionary directly
                return self._summarize_chunk(data, data_description_str)
                
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")
                
        except Exception as e:
            logger.error(f"Error in single batch summarization: {e}")
            logger.error(f"Error type: {type(e)}")
            logger.error(f"Error details: {str(e)}")
            return f"Error generating summary: {str(e)}"

    def summarize_dataframe(
        self,
        df: pd.DataFrame,
        data_description: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive summary of a DataFrame
        
        Args:
            df: Input DataFrame to summarize
            data_description: Description of the data
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dict containing the summary and metadata
        """
        try:
            # Ensure data_description is a string
            data_description_str = str(data_description) if data_description is not None else "Unknown data"
            
            # Update stats
            self.stats["total_rows"] = len(df)
            self.stats["summarization_levels"] = 1
            
            if progress_callback:
                progress_callback(f"Starting summarization of {len(df)} rows")
            
            # Generate the summary
            executive_summary = self._recursive_summarize(
                df, 
                data_description_str, 
                progress_callback
            )
            
            # Prepare data overview
            data_overview = {
                "shape": list(df.shape),
                "columns": [str(col) for col in df.columns],
                "data_types": {str(col): str(dtype) for col, dtype in df.dtypes.items()},
                "missing_values": {str(col): int(count) for col, count in df.isnull().sum().items()}
            }
            
            # Prepare metadata
            metadata = {
                "timestamp": datetime.now().isoformat(),
                "data_description": data_description_str,
                "total_rows": self.stats["total_rows"],
                "chunks_processed": self.stats["chunks_processed"],
                "summarization_levels": self.stats["summarization_levels"],
                "total_tokens": self.stats["total_tokens"],
                "total_cost": self.stats["total_cost"]
            }
            
            return {
                "executive_summary": executive_summary,
                "data_overview": data_overview,
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"Error in summarize_dataframe: {e}")
            return {
                "executive_summary": f"Error generating summary: {str(e)}",
                "data_overview": {},
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "data_description": data_description_str,
                    "total_rows": len(df) if hasattr(df, '__len__') else 0,
                    "error": str(e)
                }
            }

# Example usage and helper functions
def load_and_summarize_csv(
    file_path: str,
    data_description: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function to load CSV and generate summary
    """
    df = pd.read_csv(file_path)
    summarizer = RecursiveDataSummarizer(**kwargs)
    
    return summarizer.summarize_dataframe(df, data_description)

def save_summary_report(summary_result: Dict[str, Any], output_path: str):
    """
    Save the summary result to a formatted report file
    """
    try:
        with open(output_path, 'w') as f:
            f.write("# DATA ANALYSIS SUMMARY REPORT\n\n")
            f.write(f"Generated: {summary_result['metadata']['timestamp']}\n")
            f.write(f"Dataset: {summary_result['metadata']['data_description']}\n")
            f.write(f"Records Analyzed: {summary_result['metadata']['total_rows']:,}\n\n")
            
            f.write("## Executive Summary\n\n")
            f.write(str(summary_result['executive_summary']))
            f.write("\n\n")
            
            f.write("## Data Overview\n\n")
            f.write(f"- **Shape**: {summary_result['data_overview']['shape']}\n")
            f.write(f"- **Columns**: {', '.join([str(col) for col in summary_result['data_overview']['columns']])}\n")
            f.write(f"- **Processing Stats**: {summary_result['metadata']['chunks_processed']} chunks in {summary_result['metadata']['summarization_levels']} levels\n")
    except Exception as e:
        logger.error(f"Error saving summary report: {e}")
        # Fallback: save basic information
        with open(output_path, 'w') as f:
            f.write(f"Error saving report: {str(e)}\n")
            f.write(f"Basic info: {str(summary_result)}\n")

# Example usage
if __name__ == "__main__":
    # Example with sample data
    np.random.seed(42)
    sample_data = pd.DataFrame({
        'date': pd.date_range('2023-01-01', periods=10000),
        'sales': np.random.normal(1000, 200, 10000),
        'region': np.random.choice(['North', 'South', 'East', 'West'], 10000),
        'product': np.random.choice(['A', 'B', 'C', 'D'], 10000),
        'customer_satisfaction': np.random.uniform(1, 5, 10000)
    })
    
    # Create summarizer
    summarizer = RecursiveDataSummarizer(
        chunk_size=200,
        llm=ChatOpenAI(model="gpt-3.5-turbo", temperature=0.3)
    )
    
    # Generate summary
    def progress_update(message):
        print(f"Progress: {message}")
    
    result = summarizer.summarize_dataframe(
        sample_data,
        "Sales performance data with regional and product breakdowns",
        progress_callback=progress_update
    )
    
    # Print results
    print("EXECUTIVE SUMMARY:")
    print("=" * 50)
    print(result['executive_summary'])
    print("\nPROCESSING METADATA:")
    print("=" * 50)
    for key, value in result['metadata'].items():
        print(f"{key}: {value}")

    """
    Removed this block of text from the out put 
    **INSIGHTS & IMPLICATIONS**
    - Business implications of the findings
    - Notable trends or changes
    - Areas requiring attention

    **RECOMMENDATIONS**
    - Actionable recommendations based on the data
    - Suggested next steps
    - Priority areas for investigation

    """
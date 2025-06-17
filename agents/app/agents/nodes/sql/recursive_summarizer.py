import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Union
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.schema import BaseOutputParser
from langchain.callbacks import get_openai_callback
import json
import logging
from datetime import datetime
from app.core.dependencies import get_llm

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
        self.llm = llm
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

**INSIGHTS & IMPLICATIONS**
- Business implications of the findings
- Notable trends or changes
- Areas requiring attention

**RECOMMENDATIONS**
- Actionable recommendations based on the data
- Suggested next steps
- Priority areas for investigation

Make this suitable for senior executives and stakeholders. Use clear, professional language with quantitative support where appropriate.
**Keep the summary in less than 500 words.**

Final Executive Summary:
"""
        )
    
    def _setup_chains(self):
        """Initialize LangChain chains for different summarization levels"""
        self.chunk_chain = LLMChain(
            llm=self.llm,
            prompt=self.chunk_prompt,
            output_parser=self.output_parser
        )
        
        self.intermediate_chain = LLMChain(
            llm=self.llm,
            prompt=self.intermediate_prompt,
            output_parser=self.output_parser
        )
        
        self.final_chain = LLMChain(
            llm=self.llm,
            prompt=self.final_prompt,
            output_parser=self.output_parser
        )
    
    def _prepare_data_chunk(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to string format for LLM processing"""
        # Basic statistics
        stats = df.describe(include='all').to_string()
        
        # Sample rows
        sample_size = min(5, len(df))
        sample_rows = df.head(sample_size).to_string()
        
        # Column info
        column_info = f"Columns: {list(df.columns)}\n"
        column_info += f"Data types: {df.dtypes.to_dict()}\n"
        column_info += f"Total rows: {len(df)}\n"
        column_info += f"Missing values: {df.isnull().sum().to_dict()}\n"
        
        return f"""
{column_info}

SAMPLE DATA:
{sample_rows}

STATISTICAL SUMMARY:
{stats}
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
            # Convert DataFrame to summary format if needed
            if isinstance(data, pd.DataFrame):
                chunk_text = self._prepare_data_chunk(data)
            else:
                # Format dictionary data for summarization
                chunk_text = json.dumps(data, indent=2)
            
            with get_openai_callback() as cb:
                result = self.chunk_chain.run(
                    data_chunk=chunk_text,
                    data_description=data_description
                )
                
                # Update stats
                self.stats["total_tokens"] += cb.total_tokens
                self.stats["total_cost"] += cb.total_cost
                self.stats["chunks_processed"] += 1
            
            return result if isinstance(result, str) else result.get("summary", str(result))
            
        except Exception as e:
            logger.error(f"Error summarizing chunk: {e}")
            return f"Error processing data: {str(e)}"
    
    def _combine_summaries(self, summaries: List[str], data_description: str, is_final: bool = False) -> str:
        """Combine multiple summaries into one"""
        try:
            summaries_text = "\n\n".join([f"Summary {i+1}:\n{summary}" for i, summary in enumerate(summaries)])
            
            with get_openai_callback() as cb:
                if is_final:
                    result = self.final_chain.run(
                        summaries=summaries_text,
                        data_description=data_description,
                        total_rows=self.stats["total_rows"]
                    )
                else:
                    result = self.intermediate_chain.run(
                        summaries=summaries_text,
                        data_description=data_description
                    )
                
                # Update stats
                self.stats["total_tokens"] += cb.total_tokens
                self.stats["total_cost"] += cb.total_cost
            
            return result if isinstance(result, str) else result.get("summary", str(result))
            
        except Exception as e:
            logger.error(f"Error combining summaries: {e}")
            return f"Error combining {len(summaries)} summaries: {str(e)}"
    
    def summarize_dataframe(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        data_description: str = "Dataset",
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Main method to summarize data, handling both DataFrame and dictionary of DataFrames
        
        Args:
            data: DataFrame or dictionary of DataFrames to summarize
            data_description: Description of what the data represents
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Dictionary containing the summary and metadata
        """
        logger.info(f"Starting summarization of data")
        
        # Initialize stats
        self.stats["total_rows"] = 0
        self.stats["chunks_processed"] = 0
        self.stats["summarization_levels"] = 0
        
        try:
            summaries = []
            
            if isinstance(data, pd.DataFrame):
                # Single DataFrame case
                self.stats["total_rows"] = len(data)
                
                if len(data) <= self.chunk_size:
                    # Small DataFrame - process directly
                    if progress_callback:
                        progress_callback(f"Processing small DataFrame with {len(data)} rows")
                    summary = self._recursive_summarize(data, data_description, progress_callback)
                    summaries.append(summary)
                else:
                    # Large DataFrame - process in batches
                    if progress_callback:
                        progress_callback(f"Processing large DataFrame with {len(data)} rows in batches")
                    
                    chunks = self._chunk_data(data)
                    for i, chunk in enumerate(chunks):
                        if progress_callback:
                            progress_callback(f"Processing batch {i+1}/{len(chunks)}")
                        summary = self._recursive_summarize(chunk, data_description, progress_callback)
                        summaries.append(summary)
                
            elif isinstance(data, dict):
                # Dictionary of DataFrames case
                if progress_callback:
                    progress_callback(f"Processing dictionary with {len(data)} DataFrames")
                
                for name, df in data.items():
                    if not isinstance(df, pd.DataFrame):
                        logger.warning(f"Skipping non-DataFrame item: {name}")
                        continue
                    
                    self.stats["total_rows"] += len(df)
                    
                    if progress_callback:
                        progress_callback(f"Processing DataFrame '{name}' with {len(df)} rows")
                    
                    if len(df) <= self.chunk_size:
                        # Small DataFrame - process directly
                        summary = self._recursive_summarize(df, f"{data_description} - {name}", progress_callback)
                        summaries.append(summary)
                    else:
                        # Large DataFrame - process in batches
                        chunks = self._chunk_data(df)
                        df_summaries = []
                        
                        for i, chunk in enumerate(chunks):
                            if progress_callback:
                                progress_callback(f"Processing batch {i+1}/{len(chunks)} for '{name}'")
                            chunk_summary = self._recursive_summarize(chunk, f"{data_description} - {name}", progress_callback)
                            df_summaries.append(chunk_summary)
                        
                        # Combine summaries for this DataFrame
                        df_summary = self._combine_summaries(df_summaries, f"{data_description} - {name}", is_final=True)
                        summaries.append(df_summary)
            
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")
            
            # Combine all summaries
            if len(summaries) > 1:
                if progress_callback:
                    progress_callback(f"Combining {len(summaries)} summaries")
                final_summary = self._combine_summaries(summaries, data_description, is_final=True)
            elif summaries:
                final_summary = summaries[0]
            else:
                final_summary = "No valid data found to summarize"
            
            # Prepare result
            result = {
                "executive_summary": final_summary,
                "metadata": {
                    "total_rows": self.stats["total_rows"],
                    "chunks_processed": self.stats["chunks_processed"],
                    "summarization_levels": self.stats["summarization_levels"],
                    "total_tokens": self.stats["total_tokens"],
                    "estimated_cost": self.stats["total_cost"],
                    "timestamp": datetime.now().isoformat(),
                    "data_description": data_description
                }
            }
            
            # Add data overview
            if isinstance(data, pd.DataFrame):
                result["data_overview"] = {
                    "shape": data.shape,
                    "columns": list(data.columns),
                    "data_types": data.dtypes.to_dict(),
                    "missing_values": data.isnull().sum().to_dict()
                }
            elif isinstance(data, dict):
                result["data_overview"] = {
                    "dataframes": {
                        name: {
                            "shape": df.shape,
                            "columns": list(df.columns),
                            "data_types": df.dtypes.to_dict(),
                            "missing_values": df.isnull().sum().to_dict()
                        }
                        for name, df in data.items()
                        if isinstance(df, pd.DataFrame)
                    }
                }
            
            logger.info(f"Summarization complete. Processed {self.stats['chunks_processed']} chunks")
            return result
            
        except Exception as e:
            logger.error(f"Error in summarize_dataframe: {e}")
            return {
                "error": str(e),
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "data_description": data_description
                }
            }
    
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
            if isinstance(data, pd.DataFrame):
                if progress_callback:
                    progress_callback(f"Summarizing DataFrame with {len(data)} rows")
                
                # Prepare DataFrame summary
                summary_data = {
                    "shape": data.shape,
                    "columns": list(data.columns),
                    "data_types": data.dtypes.to_dict(),
                    "missing_values": data.isnull().sum().to_dict(),
                    "sample_data": data.head(5).to_dict(orient='records'),
                    "basic_stats": data.describe(include='all').to_dict()
                }
                
                # Generate summary using the chunk summarizer
                return self._summarize_chunk(summary_data, data_description)
                
            elif isinstance(data, dict):
                if progress_callback:
                    progress_callback("Summarizing dictionary data")
                
                # If the dictionary contains a DataFrame, convert it
                if "data" in data and isinstance(data["data"], pd.DataFrame):
                    df = data["data"]
                    return self._recursive_summarize(df, data_description, progress_callback)
                
                # Otherwise, summarize the dictionary directly
                return self._summarize_chunk(data, data_description)
                
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")
                
        except Exception as e:
            logger.error(f"Error in single batch summarization: {e}")
            return f"Error generating summary: {str(e)}"

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
    with open(output_path, 'w') as f:
        f.write("# DATA ANALYSIS SUMMARY REPORT\n\n")
        f.write(f"Generated: {summary_result['metadata']['timestamp']}\n")
        f.write(f"Dataset: {summary_result['metadata']['data_description']}\n")
        f.write(f"Records Analyzed: {summary_result['metadata']['total_rows']:,}\n\n")
        
        f.write("## Executive Summary\n\n")
        f.write(summary_result['executive_summary'])
        f.write("\n\n")
        
        f.write("## Data Overview\n\n")
        f.write(f"- **Shape**: {summary_result['data_overview']['shape']}\n")
        f.write(f"- **Columns**: {', '.join(summary_result['data_overview']['columns'])}\n")
        f.write(f"- **Processing Stats**: {summary_result['metadata']['chunks_processed']} chunks in {summary_result['metadata']['summarization_levels']} levels\n")

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
        model_name="gpt-3.5-turbo",
        temperature=0.3,
        chunk_size=200
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
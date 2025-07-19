from typing import Dict, Any, Optional
import logging
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
import os

# Configure logging
logger = logging.getLogger(__name__)

class MetadataSummarizerAgent:
    """Agent for summarizing document metadata in markdown format."""
    
    def __init__(self, model_name="gpt-4o"):
        """Initialize the metadata summarizer agent.
        
        Args:
            model_name: The name of the OpenAI model to use
        """
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=0,
        )
        self.output_parser = StrOutputParser()
        
        # Create the prompt template for summarizing metadata
        self.metadata_summary_prompt = PromptTemplate.from_template(
            """You are an expert technical writer and metadata summarization specialist. Your goal is to consume a rich metadata JSON payload and produce a single, highly polished Markdown report that captures every key detail in a clear, organized, and visually appealing way.
Input:
{metadata}

Your tasks:
1. Create a title that reflects the nature of the document (e.g., “Invoice Metadata Summary”).
2. Generate logical sections with headers (using `#`, `##`, `###`) for:
   - **Overview** (invoice number, total amount, subtotal, GST)
   - **Line Items** (item names, unit prices, quantities)
   - **Entities & Locations** (people, companies, addresses)
   - **Analysis & Insights** (NER summary, sentiment, any enhanced insights)
   - **Identifiers** (list of ChromaDB IDs or other reference IDs)
3. Display the line-item table with columns: Item, Price per kg, Quantity, and compute a “Line Total” column (price × quantity).
4. Summarize the NER text in a concise bullet list.
5. Present enhanced insights:
   - List each entity, its type, relevance score, and any key attributes.
   - Show key phrases and sentiment distribution (positive/negative/neutral counts).
6. Include a compact list of all ChromaDB IDs under a collapsible details section.
7. Use Markdown features:
   - **Bold** for important labels.
   - `Inline code` for exact values and identifiers.
   - Code blocks for any JSON or technical snippet that cannot be reformatted.
   - Tables for structured data.
   - Bullet and numbered lists as appropriate.
8. Ensure the final output:
   - Is concise (under 300 words) yet comprehensive.
   - Removes any redundant or empty fields.
   - Uses proper Markdown link formatting for URLs if present.
   - Omits raw JSON—you may embed short examples in code blocks only when necessary.
   - Does **not** wrap the entire Markdown in triple backticks.

Output only the Markdown report.
"""
        )
        
        # Create the metadata summarization chain
        self.metadata_summarization_chain = (
            RunnablePassthrough()
            | self.metadata_summary_prompt
            | self.llm
            | self.output_parser
        )
    
    def summarize_metadata(self, 
                           document_type: str,
                           document_id: str,
                           document_name: str,
                           metadata: Dict[str, Any]) -> str:
        """Summarize document metadata into markdown format.
        
        Args:
            document_type: The type of document
            document_id: The ID of the document
            document_name: The name of the document
            metadata: The document's metadata dictionary
            
        Returns:
            str: Markdown formatted summary of the document metadata
        """
        try:
            logger.info(f"Generating markdown summary for document {document_id}")
            
            # Format metadata for better readability in the prompt
            formatted_metadata = self._format_metadata_for_prompt(metadata)
            
            # Create input for the chain
            chain_input = {
                "metadata": formatted_metadata
            }
            
            # Run the chain
            markdown_summary = self.metadata_summarization_chain.invoke(chain_input)
            
            logger.info(f"Successfully generated markdown summary for document {document_id}")
            return markdown_summary
            
        except Exception as e:
            logger.error(f"Error generating markdown summary: {str(e)}")
            # Return a basic markdown summary in case of error
            return f"""# Metadata Summary

## Error
Error generating complete summary: {str(e)}
"""
    
    def _format_metadata_for_prompt(self, metadata: Dict[str, Any]) -> str:
        """Format metadata dictionary as a readable string for the prompt.
        
        Args:
            metadata: Dictionary containing document metadata
            
        Returns:
            str: Formatted metadata string
        """
        if not metadata:
            return "No metadata available"
            
        # Convert metadata dict to a formatted string
        formatted_parts = []
        for key, value in metadata.items():
            if isinstance(value, dict):
                formatted_parts.append(f"{key}:\n{self._format_nested_dict(value, indent=2)}")
            elif isinstance(value, list):
                if value:
                    list_items = "\n".join([f"  - {item}" for item in value])
                    formatted_parts.append(f"{key}:\n{list_items}")
                else:
                    formatted_parts.append(f"{key}: []")
            else:
                formatted_parts.append(f"{key}: {value}")
                
        return "\n".join(formatted_parts)
    
    def _format_nested_dict(self, d: Dict[str, Any], indent: int = 0) -> str:
        """Format a nested dictionary with proper indentation.
        
        Args:
            d: Dictionary to format
            indent: Number of spaces to indent
            
        Returns:
            str: Formatted string representation of the nested dictionary
        """
        indent_str = " " * indent
        parts = []
        
        for key, value in d.items():
            if isinstance(value, dict):
                parts.append(f"{indent_str}{key}:\n{self._format_nested_dict(value, indent + 2)}")
            elif isinstance(value, list):
                if value:
                    list_items = "\n".join([f"{indent_str}  - {item}" for item in value])
                    parts.append(f"{indent_str}{key}:\n{list_items}")
                else:
                    parts.append(f"{indent_str}{key}: []")
            else:
                parts.append(f"{indent_str}{key}: {value}")
                
        return "\n".join(parts)


# Singleton instance for use throughout the application
metadata_summarizer = MetadataSummarizerAgent() 
import asyncio
import json
from pathlib import Path
from langchain_kpi_extractor import KPIStrategyMapAgent

async def extract_strategy_map_from_pdf(pdf_path, config_path="patterns.yaml"):
    """
    Extract KPI Strategy Map from a PDF document.
    
    Args:
        pdf_path: Path to the PDF file
        config_path: Path to the pattern configuration file
        
    Returns:
        Extracted strategy map data
    """
    # Initialize the agent with the configuration
    agent = KPIStrategyMapAgent(config_path)
    
    # Read the PDF file
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    # Process the PDF and extract the strategy map
    print(f"Processing {pdf_path}...")
    result = await agent.process_pdf(pdf_bytes)
    
    # Generate a summary of the extracted information
    summary = agent.get_summary(result)
    print("\nExtraction Summary:")
    print(summary)
    
    # Save the result to a JSON file
    output_path = Path(pdf_path).with_suffix('.json')
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\nExtracted data saved to {output_path}")
    
    return result

async def batch_process_pdfs(pdf_directory, config_path="patterns.yaml"):
    """
    Process multiple PDF files in a directory.
    
    Args:
        pdf_directory: Directory containing PDF files
        config_path: Path to the pattern configuration file
    """
    pdf_dir = Path(pdf_directory)
    pdf_files = list(pdf_dir.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {pdf_directory}")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Process each PDF file
    for pdf_file in pdf_files:
        print(f"\n{'=' * 50}")
        print(f"Processing {pdf_file}")
        print(f"{'=' * 50}")
        
        await extract_strategy_map_from_pdf(str(pdf_file), config_path)

async def main():
    """Main function demonstrating usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract KPI Strategy Maps from PDF documents")
    parser.add_argument("--pdf", help="Path to a PDF file to process")
    parser.add_argument("--dir", help="Directory containing PDF files to process")
    parser.add_argument("--config", default="patterns.yaml", 
                        help="Path to pattern configuration file")
    
    args = parser.parse_args()
    
    if args.pdf:
        # Process a single PDF file
        await extract_strategy_map_from_pdf(args.pdf, args.config)
    elif args.dir:
        # Process all PDF files in a directory
        await batch_process_pdfs(args.dir, args.config)
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())
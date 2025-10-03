#!/usr/bin/env python3
"""
Script to convert parquet files to CSV format with row limit truncation.
Converts all parquet files in the current directory to CSV with max 10,000 rows.
"""

import pandas as pd
import os
import glob
from pathlib import Path

def convert_parquet_to_csv(parquet_file, max_rows=10000):
    """
    Convert a single parquet file to CSV with row limit.
    
    Args:
        parquet_file (str): Path to the parquet file
        max_rows (int): Maximum number of rows to include in CSV
    
    Returns:
        str: Path to the created CSV file
    """
    try:
        print(f"Processing: {parquet_file}")
        
        # Read parquet file
        df = pd.read_parquet(parquet_file)
        original_rows = len(df)
        
        # Truncate to max_rows if necessary
        if original_rows > max_rows:
            df = df.head(max_rows)
            print(f"  Original rows: {original_rows:,}, truncated to: {max_rows:,}")
        else:
            print(f"  Rows: {original_rows:,} (no truncation needed)")
        
        # Create CSV filename
        csv_file = parquet_file.replace('.parquet', '.csv')
        
        # Write to CSV
        df.to_csv(csv_file, index=False)
        print(f"  Created: {csv_file}")
        
        return csv_file
        
    except Exception as e:
        print(f"  Error processing {parquet_file}: {e}")
        return None

def main():
    """Main function to convert all parquet files in current directory."""
    
    # Get current directory
    current_dir = Path.cwd()
    print(f"Working directory: {current_dir}")
    
    # Find all parquet files
    parquet_files = glob.glob("*.parquet")
    
    if not parquet_files:
        print("No parquet files found in current directory.")
        return
    
    print(f"Found {len(parquet_files)} parquet files:")
    for file in parquet_files:
        print(f"  - {file}")
    
    print("\nStarting conversion...")
    print("=" * 50)
    
    converted_files = []
    failed_files = []
    
    for parquet_file in parquet_files:
        csv_file = convert_parquet_to_csv(parquet_file)
        if csv_file:
            converted_files.append(csv_file)
        else:
            failed_files.append(parquet_file)
        print()  # Add blank line between files
    
    # Summary
    print("=" * 50)
    print("CONVERSION SUMMARY")
    print("=" * 50)
    print(f"Successfully converted: {len(converted_files)} files")
    print(f"Failed conversions: {len(failed_files)} files")
    
    if converted_files:
        print("\nConverted files:")
        for file in converted_files:
            print(f"  ✓ {file}")
    
    if failed_files:
        print("\nFailed files:")
        for file in failed_files:
            print(f"  ✗ {file}")
    
    print(f"\nAll CSV files saved in: {current_dir}")

if __name__ == "__main__":
    main()

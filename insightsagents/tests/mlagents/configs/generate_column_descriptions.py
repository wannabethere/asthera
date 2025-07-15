#!/usr/bin/env python3
"""
Generate column descriptions for bv_finance_flux_final.csv
"""

import pandas as pd
from typing import Dict, List, Any

def generate_column_descriptions() -> Dict[str, str]:
    """
    Generate comprehensive column descriptions for the finance flux dataset
    """
    
    column_descriptions = {
        "Date": "Transaction date in YYYY-MM-DD format, indicating when the financial transaction occurred",
        
        "Region": "Geographic region or country where the transaction took place (e.g., France, Germany, United Kingdom, United Arab Emirates)",
        
        "Cost center": "Organizational cost center identifier, typically 'Center A' in this dataset, representing the department or unit responsible for the cost",
        
        "Project": "Project identifier or project number, can be numeric (e.g., 10.0, 20.0) or empty, indicating which project the transaction is associated with",
        
        "Account": "Account number or identifier, appears to be consistently '2' in this dataset, representing the general ledger account",
        
        "Source": "Source system or module that generated the transaction (e.g., PROJECT ACCOUNTING, PAYABLES, REVALUATION, SPREADSHEET)",
        
        "Category": "Transaction category or type (e.g., MISCELLANEOUS_COST, PURCHASE INVOICES, ACCRUAL - AUTOREVERSE, REVALUE PROFIT/LOSS)",
        
        "Event Type": "Specific event or action type (e.g., MISC_COST_DIST, INVOICE VALIDATED, INVOICE CANCELLED, CREDIT MEMO VALIDATED, MISC_COST_DIST_ADJ)",
        
        "PO No": "Purchase Order number identifier, format like 'NEW_PO_XXXX' where XXXX is a numeric identifier",
        
        "Transactional value": "Original transaction amount in the transaction currency, can be positive or negative values representing debits and credits",
        
        "Functional value": "Transaction amount converted to the functional currency (typically the reporting currency), accounting for exchange rate differences",
        
        "PO with Line item": "Purchase Order number with line item suffix (e.g., 'NEW_PO_2019-', 'NEW_PO_3298-'), providing detailed line-level tracking"
    }
    
    return column_descriptions

def create_static_columns_array() -> List[str]:
    """
    Create a static array of column names
    """
    columns = [
        "Date",
        "Region", 
        "Cost center",
        "Project",
        "Account",
        "Source",
        "Category",
        "Event Type",
        "PO No",
        "Transactional value",
        "Functional value",
        "PO with Line item"
    ]
    
    return columns

def print_column_info():
    """
    Print comprehensive column information
    """
    print("Column Descriptions for bv_finance_flux_final.csv")
    print("=" * 60)
    
    # Get column descriptions
    descriptions = generate_column_descriptions()
    columns = create_static_columns_array()
    
    print(f"Total Columns: {len(columns)}")
    print(f"Columns: {columns}")
    print("\nDetailed Descriptions:")
    print("-" * 60)
    
    for i, column in enumerate(columns, 1):
        print(f"{i:2d}. {column}")
        print(f"    {descriptions[column]}")
        print()
    
    # Create Python code for easy use
    print("Python Code for Column Descriptions:")
    print("-" * 60)
    print("columns_description = {")
    for column in columns:
        description = descriptions[column].replace('"', '\\"')
        print(f'    "{column}": "{description}",')
    print("}")
    
    print("\nStatic Columns Array:")
    print("-" * 60)
    print("columns = [")
    for column in columns:
        print(f'    "{column}",')
    print("]")

def create_usage_example():
    """
    Create usage example for the column descriptions
    """
    print("\nUsage Example:")
    print("-" * 60)
    print("""
# Load the data
po_df = pd.read_csv("/Users/sameerm/ComplianceSpark/byziplatform/unstructured/ai-report/app/bv_finance_flux_final.csv")

# Column descriptions for analysis
columns_description = {
    "Date": "Transaction date in YYYY-MM-DD format, indicating when the financial transaction occurred",
    "Region": "Geographic region or country where the transaction took place (e.g., France, Germany, United Kingdom, United Arab Emirates)",
    "Cost center": "Organizational cost center identifier, typically 'Center A' in this dataset, representing the department or unit responsible for the cost",
    "Project": "Project identifier or project number, can be numeric (e.g., 10.0, 20.0) or empty, indicating which project the transaction is associated with",
    "Account": "Account number or identifier, appears to be consistently '2' in this dataset, representing the general ledger account",
    "Source": "Source system or module that generated the transaction (e.g., PROJECT ACCOUNTING, PAYABLES, REVALUATION, SPREADSHEET)",
    "Category": "Transaction category or type (e.g., MISCELLANEOUS_COST, PURCHASE INVOICES, ACCRUAL - AUTOREVERSE, REVALUE PROFIT/LOSS)",
    "Event Type": "Specific event or action type (e.g., MISC_COST_DIST, INVOICE VALIDATED, INVOICE CANCELLED, CREDIT MEMO VALIDATED, MISC_COST_DIST_ADJ)",
    "PO No": "Purchase Order number identifier, format like 'NEW_PO_XXXX' where XXXX is a numeric identifier",
    "Transactional value": "Original transaction amount in the transaction currency, can be positive or negative values representing debits and credits",
    "Functional value": "Transaction amount converted to the functional currency (typically the reporting currency), accounting for exchange rate differences",
    "PO with Line item": "Purchase Order number with line item suffix (e.g., 'NEW_PO_2019-', 'NEW_PO_3298-'), providing detailed line-level tracking"
}

# Static columns array
columns = [
    "Date",
    "Region", 
    "Cost center",
    "Project",
    "Account",
    "Source",
    "Category",
    "Event Type",
    "PO No",
    "Transactional value",
    "Functional value",
    "PO with Line item"
]

# Use in analysis
print(f"Dataset has {len(columns)} columns")
print(f"Columns: {columns}")

# Example: Get unique values for categorical columns
print(f"Unique regions: {po_df['Region'].unique()}")
print(f"Unique sources: {po_df['Source'].unique()}")
print(f"Unique categories: {po_df['Category'].unique()}")
""")

if __name__ == "__main__":
    print_column_info()
    create_usage_example() 
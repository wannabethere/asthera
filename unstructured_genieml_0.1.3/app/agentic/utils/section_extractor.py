"""
Utilities for extracting structured sections from documents.
Particularly useful for processing Gong call data.
"""

import re
import json
import logging
from typing import Dict, List, Any

# Set up logging
logger = logging.getLogger("SectionExtractor")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

def extract_structured_sections(content: str) -> Dict[str, Dict[str, Any]]:
    """
    Extract structured sections like Pain Points, Features, etc. from Gong insights content.
    
    Args:
        content: The text content to extract sections from
        
    Returns:
        Dictionary mapping section names to their structured content
    """
    structured_content = {}
    
    # Updated section patterns to match exactly how gong sections are formatted
    section_patterns = {
        'customer_pain_points': r'Customer Pain Points\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'product_features': r'Product Features(?:\s*Discussed)?\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'objections': r'Objections(?:\s*Raised)?\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'action_items': r'(?:Next Steps\s*/\s*)?Action Items\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'competitors': r'Competitors(?:\s*Mentioned)?\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'decision_criteria': r'Decision Criteria\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'buyer_roles': r'(?:Buyer Roles\s*/\s*)?Personas\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'deal_stage': r'Deal Stage(?:\s*/\s*Intent)?\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'use_cases': r'Use Cases(?:\s*Mentioned)?\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'decisions': r'Decisions\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'issues': r'Issues\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)',
        'key_points': r'Key Points\s*\((\d+)\):(.*?)(?=\n\w+\s+\(\d+\):|$)'
    }
    
    # Extract each section
    for section_key, pattern in section_patterns.items():
        matches = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if matches:
            count = matches.group(1)
            section_content = matches.group(2).strip()
            
            # Further parse numbered items
            items = []
            item_pattern = r'(\d+)\.\s+(.*?)(?=\n\d+\.|$)'
            item_matches = re.findall(item_pattern, section_content, re.DOTALL)
            
            if item_matches:
                for item_num, item_text in item_matches:
                    items.append(item_text.strip())
            else:
                # If no numbered items found, use the whole section
                items = [section_content]
                
            structured_content[section_key] = {
                'count': int(count),
                'items': items
            }
    
    # Extract section keywords to help with filtering in other parts of the agent
    section_keywords = set()
    
    # Pattern matching for section headings
    section_heading_patterns = [
        r'(Customer Pain Points|Product Features|Objections|Action Items|Competitors|Decision Criteria|Use Cases|Deal Stage|Buyer Roles)',
        r'(\w+\s+Points?)\s*\(\d+\):',
        r'(\w+\s+Items?)\s*\(\d+\):',
        r'(\w+\s+Discussed)\s*\(\d+\):',
        r'(\w+\s+Mentioned)\s*\(\d+\):',
        r'(\w+\s+Raised)\s*\(\d+\):'
    ]
    
    for pattern in section_heading_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                section_keywords.update(match)
            else:
                section_keywords.add(match)
    
    # Add structured_content sections as additional keyword sources
    structured_content['section_keywords'] = list(section_keywords)
    
    return structured_content

def format_structured_sections_for_context(structured_content: Dict[str, Dict[str, Any]]) -> str:
    """
    Format structured sections for inclusion in context.
    
    Args:
        structured_content: The structured content dictionary
        
    Returns:
        Formatted text for inclusion in context
    """
    if not structured_content or structured_content == {} or ('section_keywords' in structured_content and len(structured_content) == 1):
        return ""
        
    context_parts = []
    
    # Format each section in a clean, organized way
    for section_key, section_data in structured_content.items():
        # Skip section_keywords which is not a real section
        if section_key == 'section_keywords':
            continue
            
        # Convert section_key from snake_case to Title Case
        section_title = ' '.join(word.capitalize() for word in section_key.split('_'))
        count = section_data.get('count', 0)
        items = section_data.get('items', [])
        
        context_parts.append(f"\n### {section_title} ({count})")
        
        # Add each item with its number
        for i, item in enumerate(items):
            context_parts.append(f"{i+1}. {item}")
    
    return '\n'.join(context_parts)

def parse_json_list_field(field_value: Any) -> List[str]:
    """
    Parse a field that might be a JSON string list or already a list.
    
    Args:
        field_value: The field value to parse
        
    Returns:
        Parsed list of strings
    """
    result = []
    
    if isinstance(field_value, str):
        try:
            parsed = json.loads(field_value)
            if isinstance(parsed, list):
                result = parsed
        except json.JSONDecodeError:
            # Not valid JSON, treat as a single item
            if field_value:
                result = [field_value]
    elif isinstance(field_value, list):
        result = field_value
    
    return result 
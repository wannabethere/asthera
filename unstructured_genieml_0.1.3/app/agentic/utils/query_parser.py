"""
Query Parser Utility

This utility houses functions for parsing user queries to extract key information 
such as company names, Salesforce IDs, and temporal expressions.
"""
import re
from typing import Any, Dict, List, Optional
import logging

# Set up logging
logger = logging.getLogger(__name__)

def extract_potential_company_names(query: str) -> List[str]:
    """
    Extract potential company or customer names from a query.
    This helps with identifying specific company mentions like "Electronic Arts" or "EA".
    
    Args:
        query: The user's question
        
    Returns:
        A list of potential company name phrases
    """
    # Convert to lowercase for easier processing
    query_lower = query.lower()
    
    # Common words to exclude from company name extraction
    common_words = [
        "the", "and", "or", "in", "on", "at", "with", "for", "about", "from", "to",
        "how", "what", "when", "where", "why", "who", "which", "that", "this", "these", 
        "those", "their", "our", "your", "my", "his", "her", "its", "their"
    ]
    
    # Common words that indicate a company might follow
    company_indicators = ["company", "client", "customer", "account", "opportunity", "deal"]
    
    potential_names = []
    
    # Split into words
    words = query_lower.replace("?", "").replace(".", "").replace(",", "").split()
    
    # Look for capitalized phrases in the original query (potential proper nouns)
    words_original = query.split()
    for i in range(len(words_original)):
        # Check if word starts with capital letter (potential company name)
        if i < len(words_original) and words_original[i][0:1].isupper():
            # Try to capture multi-word company names
            name_parts = [words_original[i]]
            j = i + 1
            # Continue adding words if they start with a capital letter or are connecting words
            while j < len(words_original) and (
                words_original[j][0:1].isupper() or 
                words_original[j].lower() in ["and", "of", "the", "&"]):
                name_parts.append(words_original[j])
                j += 1
            
            if len(name_parts) > 0:
                potential_names.append(" ".join(name_parts))
    
    # Look for words after company indicators
    for i in range(len(words) - 1):
        if words[i] in company_indicators and i < len(words) - 1:
            # Extract the next word(s) that aren't common words
            next_words = []
            j = i + 1
            while j < len(words) and words[j] not in common_words:
                next_words.append(words[j])
                j += 1
            
            if next_words:
                potential_names.append(" ".join(next_words))
    
    # Look for potential acronyms (all caps in original query)
    for word in query.split():
        if word.isupper() and len(word) >= 2 and len(word) <= 5:
            potential_names.append(word)
    
    # Extract potentially standalone words that aren't common words
    # and are long enough to be company names
    standalone_words = []
    for word in words:
        if (word not in common_words and len(word) >= 4 and 
            word not in company_indicators):
            standalone_words.append(word)
    
    # Add standalone words as potential names
    potential_names.extend(standalone_words)
    
    # Remove duplicates and very short terms
    filtered_names = list(set([name for name in potential_names if len(name) > 2]))
    
    logger.info(f"Extracted potential company names: {filtered_names}")
    
    return filtered_names

def extract_potential_ids(query: str, id_type: str = "opportunity") -> List[str]:
    """
    Extract potential Salesforce IDs from the query.
    
    Args:
        query: The user's question
        id_type: Type of ID to extract ("opportunity" or "account")
        
    Returns:
        A list of potential ID strings
    """
    # Standard Salesforce ID patterns
    # Opportunity IDs typically start with '006'
    # Account IDs typically start with '001'
    sf_id_pattern = r'\b\w{15,18}\b'  # Salesforce IDs are 15 or 18 chars
    
    # Look for explicit mentions with labels
    explicit_patterns = {
        "opportunity": [
            r'opportunity id:?\s*(\w{15,18})',
            r'opportunity id\s+is\s+(\w{15,18})',
            r'opportunity\s*#\s*(\w{15,18})',
            r'opp id:?\s*(\w{15,18})',
            r'opp\s*#\s*(\w{15,18})'
        ],
        "account": [
            r'account id:?\s*(\w{15,18})',
            r'account id\s+is\s+(\w{15,18})',
            r'account\s*#\s*(\w{15,18})'
        ]
    }
    
    found_ids = []
    
    # Check for explicit ID mentions first
    patterns_to_check = explicit_patterns.get(id_type, [])
    for pattern in patterns_to_check:
        matches = re.finditer(pattern, query.lower())
        for match in matches:
            if match.group(1):
                found_ids.append(match.group(1))
    
    # If no explicit mentions, look for any Salesforce-like IDs
    if not found_ids:
        matches = re.finditer(sf_id_pattern, query)
        for match in matches:
            potential_id = match.group(0)
            # Apply some validation based on ID type
            if id_type == "opportunity" and (potential_id.startswith("006") or potential_id.startswith("00Q")):
                found_ids.append(potential_id)
            elif id_type == "account" and potential_id.startswith("001"):
                found_ids.append(potential_id)
            # If no specific type validation passes but it's long enough, include it as a fallback
            elif len(potential_id) >= 15:
                found_ids.append(potential_id)
    
    return found_ids

def parse_time_filter(query: str, topics: List[str]) -> Optional[Dict[str, Any]]:
    """
    Parse temporal expressions from the query and topics to create appropriate time filters.
    
    Args:
        query: The user's question
        topics: Extracted topics that might contain temporal expressions
        
    Returns:
        A dictionary with time filter parameters or None if no time expressions found
    """
    # Convert query to lowercase for easier matching
    query_lower = query.lower()
    
    # Dictionary to store the result
    time_filter = None
    
    # Common temporal patterns to look for
    time_patterns = [
        # Days patterns
        (r'last (\d+) days?', 'days'),
        (r'past (\d+) days?', 'days'),
        (r'previous (\d+) days?', 'days'),
        (r'(\d+) days? ago', 'days'),
        (r'(\d+)[ -]days?', 'days'),  # Handle "2-days" or "2 days"
        
        # Weeks patterns
        (r'last (\d+) weeks?', 'weeks'),
        (r'past (\d+) weeks?', 'weeks'),
        (r'previous (\d+) weeks?', 'weeks'),
        (r'(\d+) weeks? ago', 'weeks'),
        (r'(\d+)[ -]weeks?', 'weeks'),  # Handle "2-weeks" or "2 weeks"
        
        # Months patterns
        (r'last (\d+) months?', 'months'),
        (r'past (\d+) months?', 'months'),
        (r'previous (\d+) months?', 'months'),
        (r'(\d+) months? ago', 'months'),
        (r'(\d+)[ -]months?', 'months'),  # Handle "2-months" or "2 months"
        
        # Special cases
        (r'yesterday', 'days', 1),
        (r'last week', 'weeks', 1),
        (r'past week', 'weeks', 1),
        (r'this week', 'weeks', 1),
        (r'last month', 'months', 1),
        (r'past month', 'months', 1),
        (r'this month', 'months', 1),
        (r'last quarter', 'months', 3),
        (r'this quarter', 'months', 3),
        (r'last 7 days', 'days', 7),  # Common specific time ranges
        (r'last 14 days', 'days', 14),
        (r'last 30 days', 'days', 30),
        (r'last 60 days', 'days', 60),
        (r'last 90 days', 'days', 90),
    ]
    
    # Also check for specific standalone numeric time expressions in topics
    numeric_time_topic_patterns = {
        "two weeks": {"unit": "weeks", "value": 2},
        "2 weeks": {"unit": "weeks", "value": 2},
        "2-weeks": {"unit": "weeks", "value": 2},
        "two-weeks": {"unit": "weeks", "value": 2},
        "three weeks": {"unit": "weeks", "value": 3},
        "3 weeks": {"unit": "weeks", "value": 3},
        "four weeks": {"unit": "weeks", "value": 4},
        "4 weeks": {"unit": "weeks", "value": 4},
        "one month": {"unit": "months", "value": 1},
        "1 month": {"unit": "months", "value": 1},
        "two months": {"unit": "months", "value": 2},
        "2 months": {"unit": "months", "value": 2},
        "three months": {"unit": "months", "value": 3},
        "3 months": {"unit": "months", "value": 3},
    }
    
    # First check the main query
    for pattern_info in time_patterns:
        if len(pattern_info) == 2:
            pattern, unit = pattern_info
            # Search for patterns with numeric values
            matches = re.search(pattern, query_lower)
            if matches and matches.group(1).isdigit():
                value = int(matches.group(1))
                logger.info(f"Found temporal expression in query: {matches.group(0)} → {value} {unit}")
                return {'unit': unit, 'value': value, 'expression': matches.group(0)}
        else:
            pattern, unit, value = pattern_info
            # Search for fixed expressions like "yesterday", "last week"
            if re.search(pattern, query_lower):
                logger.info(f"Found special temporal expression in query: {pattern} → {value} {unit}")
                return {'unit': unit, 'value': value, 'expression': pattern}
    
    # Then check the topics for temporal expressions
    for topic in topics:
        topic_lower = topic.lower()
        
        # Check exact match in our numeric time topics dictionary
        if topic_lower in numeric_time_topic_patterns:
            time_info = numeric_time_topic_patterns[topic_lower]
            logger.info(f"Found exact temporal expression in topics: {topic_lower} → {time_info['value']} {time_info['unit']}")
            return {
                'unit': time_info['unit'], 
                'value': time_info['value'], 
                'expression': topic_lower
            }
        
        # Check regex patterns
        for pattern_info in time_patterns:
            if len(pattern_info) == 2:
                pattern, unit = pattern_info
                matches = re.search(pattern, topic_lower)
                if matches and matches.group(1).isdigit():
                    value = int(matches.group(1))
                    logger.info(f"Found temporal expression in topics: {matches.group(0)} → {value} {unit}")
                    return {'unit': unit, 'value': value, 'expression': matches.group(0)}
            else:
                pattern, unit, value = pattern_info
                if re.search(pattern, topic_lower):
                    logger.info(f"Found special temporal expression in topics: {pattern} → {value} {unit}")
                    return {'unit': unit, 'value': value, 'expression': pattern}
    
    # Special case for if "two weeks" appears in the topics
    for topic in topics:
        # Convert numbers written as words to actual numbers
        topic_lower = topic.lower()
        # Add any other specific cases needed here
        
    # Default to None if no temporal expressions found
    logger.info(f"No temporal expressions found in query or topics")
    return None 
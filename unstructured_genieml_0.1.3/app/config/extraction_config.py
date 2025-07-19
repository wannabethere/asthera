"""
Configuration settings for document extraction and analysis processes.
"""
from typing import List, Dict, Any

# Standard business questions for document analysis
STANDARD_BUSINESS_QUESTIONS: List[str] = [
    "What are the key entities mentioned in this document?",
    "What are the main topics discussed in this document?",
    "What is the sentiment expressed in this document?"
]

# Additional domain-specific questions that can be used for deeper analysis
FINANCIAL_QUESTIONS: List[str] = [
    "What financial metrics are discussed in this document?",
    "Are there any financial risks mentioned?",
    "What financial performance indicators are highlighted?"
]

COMPLIANCE_QUESTIONS: List[str] = [
    "What compliance requirements are mentioned in this document?",
    "Are there any regulatory concerns discussed?",
    "What legal or compliance risks are identified?"
]

PRODUCT_QUESTIONS: List[str] = [
    "What products or services are mentioned in this document?",
    "How are products described or positioned?",
    "What product performance metrics are discussed?"
]

# Question collections by document type
DOCUMENT_TYPE_QUESTIONS: Dict[str, List[str]] = {
    "financial_report": STANDARD_BUSINESS_QUESTIONS + FINANCIAL_QUESTIONS,
    "compliance_document": STANDARD_BUSINESS_QUESTIONS + COMPLIANCE_QUESTIONS,
    "product_documentation": STANDARD_BUSINESS_QUESTIONS + PRODUCT_QUESTIONS,
    # Default to standard questions for other document types
    "default": STANDARD_BUSINESS_QUESTIONS
}

# Function to get appropriate questions based on document type
def get_questions_for_document_type(document_type: str) -> List[str]:
    """
    Get the appropriate list of questions for a given document type.
    
    Args:
        document_type: The type of document being analyzed
        
    Returns:
        A list of relevant business questions for analysis
    """
    return DOCUMENT_TYPE_QUESTIONS.get(document_type, DOCUMENT_TYPE_QUESTIONS["default"]) 
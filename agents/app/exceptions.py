class RAGException(Exception):
    """Base exception for RAG-related errors."""
    pass

class ValidationError(RAGException):
    """Raised when validation repeatedly fails."""
    def __init__(self, attempts: int, last_confidence: float, message: str = None):
        self.attempts = attempts
        self.last_confidence = last_confidence
        self.message = message or f"Validation failed after {attempts} attempts. Last confidence: {last_confidence}"
        super().__init__(self.message)

class ContextRetrievalError(RAGException):
    """Raised when relevant context cannot be retrieved."""
    pass

class ModelError(RAGException):
    """Raised when there's an error with the language model."""
    pass
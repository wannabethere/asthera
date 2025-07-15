from typing import Dict, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from chatbot.multiagent_planners.models.models import ValidationResult
from chatbot.multiagent_planners.exceptions import ValidationError

class ResponseValidator:
    """Handles validation of RAG responses."""
    
    def __init__(
        self,
        model_name: str = "gpt-4-turbo-preview",
        temperature: float = 0.0
    ):
        self.llm = ChatOpenAI(model_name=model_name, temperature=temperature)
        self.validation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a validation assistant responsible for ensuring 
            the quality and accuracy of RAG system responses. Your job is to 
            critically evaluate if the given response accurately answers the 
            question based on the provided context."""),
            ("user", """
            Context: {context}
            Question: {question}
            Response: {response}
            
            Evaluate the response and provide:
            1. Is it valid and accurate based on the context?
            2. Confidence score (0-1)
            3. Specific feedback for improvement if needed
            
            Focus on:
            - Factual accuracy compared to context
            - Completeness of the answer
            - Relevance to the question
            - Logical consistency
            """)
        ])
        self.output_parser = JsonOutputParser()
        
    def validate(
        self,
        context: str,
        question: str,
        response: str
    ) -> ValidationResult:
        """
        Validates a response against the given context and question.
        
        Args:
            context: The context used to generate the response
            question: The original question
            response: The generated response to validate
            
        Returns:
            ValidationResult containing validation metrics and feedback
        """
        try:
            validation_chain = self.validation_prompt | self.llm | self.output_parser
            result = validation_chain.invoke({
                "context": context,
                "question": question,
                "response": response
            })
            return ValidationResult(**result)
        except Exception as e:
            raise ValidationError(
                attempts=1,
                last_confidence=0.0,
                message=f"Validation failed due to: {str(e)}"
            )

    def is_response_valid(
        self,
        validation_result: ValidationResult,
        min_confidence: float = 0.8
    ) -> bool:
        """
        Determines if a response meets the validation criteria.
        
        Args:
            validation_result: The validation result to check
            min_confidence: Minimum acceptable confidence score
            
        Returns:
            bool indicating if the response is valid
        """
        return (
            validation_result.is_valid and 
            validation_result.confidence_score >= min_confidence
        )
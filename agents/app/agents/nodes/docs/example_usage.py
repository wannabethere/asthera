"""
Example usage of the Document Planning System

This file demonstrates how to use the enhanced document planning system
that integrates with docmodels for intelligent document retrieval and analysis.
"""

import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

# Import the document planning components
from app.agents.nodes.docs.document_planning_service import DocumentPlanningService
from app.agents.nodes.docs.enhanced_document_planner import (
    DocumentPlanningStrategy, RetrievalGrade
)
from app.core.dependencies import get_document_service, get_chroma_store

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def example_basic_question_answering():
    """Example: Basic question answering using document planning"""
    
    print("=" * 60)
    print("EXAMPLE 1: Basic Question Answering")
    print("=" * 60)
    
    # Initialize the document planning service
    # In a real application, these would be properly configured
    service = DocumentPlanningService()
    
    # Example questions
    questions = [
        {
            "question": "What are the key financial metrics mentioned in the quarterly reports?",
            "document_type": "financial_report",
            "description": "Financial analysis question"
        },
        {
            "question": "Compare the performance metrics across different departments",
            "document_type": "performance_report", 
            "description": "Comparative analysis question"
        },
        {
            "question": "What are the main topics discussed in the recent meeting notes?",
            "document_type": "meeting_notes",
            "description": "Content summarization question"
        }
    ]
    
    for i, q in enumerate(questions, 1):
        print(f"\n--- Question {i}: {q['description']} ---")
        print(f"Question: {q['question']}")
        
        try:
            # Answer the question
            response = await service.answer_question(
                question=q['question'],
                document_type=q['document_type'],
                max_documents=10
            )
            
            # Display results
            print(f"Strategy: {response.strategy}")
            print(f"Confidence: {response.confidence:.2f}")
            print(f"Retrieval Grade: {response.retrieval_grade}")
            print(f"Documents Found: {response.documents_found}")
            print(f"Execution Successful: {response.execution_successful}")
            print(f"Execution Time: {response.execution_time:.2f} seconds")
            print(f"Answer: {response.final_answer}")
            
            if response.recommendations:
                print(f"Recommendations: {', '.join(response.recommendations)}")
                
        except Exception as e:
            print(f"Error answering question: {e}")

async def example_document_analysis():
    """Example: Analyzing specific documents"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Document Analysis")
    print("=" * 60)
    
    service = DocumentPlanningService()
    
    # Example document IDs (these would be real document IDs in practice)
    document_ids = ["doc1", "doc2", "doc3"]
    
    analysis_types = [
        {
            "type": "comprehensive",
            "description": "Full document analysis with detailed insights"
        },
        {
            "type": "structured", 
            "description": "Extract structured data like tables and lists"
        },
        {
            "type": "summary",
            "description": "Generate document summaries"
        }
    ]
    
    for analysis in analysis_types:
        print(f"\n--- {analysis['description']} ---")
        
        try:
            result = await service.get_document_analysis(
                document_ids=document_ids,
                analysis_type=analysis['type']
            )
            
            print(f"Analysis Type: {result['analysis_type']}")
            print(f"Documents Analyzed: {result['documents_analyzed']}")
            print(f"Execution Successful: {result['execution_successful']}")
            print(f"Final Analysis: {result['final_analysis']}")
            
        except Exception as e:
            print(f"Error in {analysis['type']} analysis: {e}")

async def example_document_search():
    """Example: Searching documents with quality analysis"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Document Search with Quality Analysis")
    print("=" * 60)
    
    service = DocumentPlanningService()
    
    # Example search queries
    search_queries = [
        {
            "query": "revenue growth",
            "document_type": "financial_report",
            "description": "Search for revenue growth information"
        },
        {
            "query": "customer feedback",
            "document_type": "survey",
            "description": "Search for customer feedback data"
        },
        {
            "query": "project timeline",
            "document_type": "project_document",
            "description": "Search for project timeline information"
        }
    ]
    
    for i, search in enumerate(search_queries, 1):
        print(f"\n--- Search {i}: {search['description']} ---")
        print(f"Query: {search['query']}")
        
        try:
            results = await service.search_documents(
                query=search['query'],
                document_type=search['document_type'],
                max_documents=5
            )
            
            print(f"Total Found: {results['total_found']}")
            print(f"Retrieval Grade: {results['retrieval_grade']}")
            print(f"Relevance Scores: {results['relevance_scores']}")
            
            if results['documents']:
                print("Sample Documents:")
                for j, doc in enumerate(results['documents'][:2], 1):
                    print(f"  {j}. {doc['type']} - {doc['content_preview'][:100]}...")
            
            if results['gaps_identified']:
                print(f"Gaps Identified: {', '.join(results['gaps_identified'])}")
            
            if results['recommendations']:
                print(f"Recommendations: {', '.join(results['recommendations'])}")
                
        except Exception as e:
            print(f"Error searching: {e}")

async def example_planning_insights():
    """Example: Getting planning insights for questions"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Planning Insights")
    print("=" * 60)
    
    service = DocumentPlanningService()
    
    # Example questions for planning analysis
    questions = [
        "What are the key performance indicators for Q4?",
        "How has customer satisfaction changed over time?",
        "What are the main risks identified in the risk assessment?",
        "Compare the budget vs actual spending across departments"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n--- Planning Analysis {i} ---")
        print(f"Question: {question}")
        
        try:
            insights = await service.get_planning_insights(
                question=question,
                document_type="performance_report"
            )
            
            print(f"Reframed Question: {insights['reframed_question']}")
            print(f"Recommended Strategy: {insights['recommended_strategy']}")
            print(f"Confidence: {insights['confidence']:.2f}")
            print(f"Retrieval Grade: {insights['retrieval_grade']}")
            print(f"Documents Available: {insights['documents_available']}")
            print(f"Estimated Complexity: {insights['estimated_complexity']}")
            
            print("Plan Steps:")
            for step in insights['plan_steps']:
                print(f"  {step['step_number']}. {step['action']} - {step['reasoning']}")
            
            if insights['suggested_improvements']:
                print(f"Suggested Improvements: {', '.join(insights['suggested_improvements'])}")
                
        except Exception as e:
            print(f"Error getting insights: {e}")

async def example_strategy_comparison():
    """Example: Comparing different planning strategies"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Strategy Comparison")
    print("=" * 60)
    
    service = DocumentPlanningService()
    
    question = "What are the key financial metrics and how do they compare across quarters?"
    
    print(f"Question: {question}")
    print("\nAnalyzing with different approaches...")
    
    # Test with different document types to see strategy differences
    document_types = [
        ("financial_report", "Financial documents"),
        ("performance_report", "Performance documents"),
        (None, "All document types")
    ]
    
    for doc_type, description in document_types:
        print(f"\n--- {description} ---")
        
        try:
            insights = await service.get_planning_insights(
                question=question,
                document_type=doc_type
            )
            
            print(f"Strategy: {insights['recommended_strategy']}")
            print(f"Confidence: {insights['confidence']:.2f}")
            print(f"Documents Available: {insights['documents_available']}")
            print(f"Complexity: {insights['estimated_complexity']}")
            
        except Exception as e:
            print(f"Error with {description}: {e}")

async def example_error_handling():
    """Example: Error handling and edge cases"""
    
    print("\n" + "=" * 60)
    print("EXAMPLE 6: Error Handling")
    print("=" * 60)
    
    service = DocumentPlanningService()
    
    # Test various error conditions
    error_cases = [
        {
            "question": "",
            "description": "Empty question"
        },
        {
            "question": "What are the financial metrics?",
            "document_type": "nonexistent_type",
            "description": "Non-existent document type"
        },
        {
            "question": "Very complex question that requires extensive analysis and multiple data sources and cross-referencing and detailed comparison",
            "description": "Overly complex question"
        }
    ]
    
    for i, case in enumerate(error_cases, 1):
        print(f"\n--- Error Case {i}: {case['description']} ---")
        
        try:
            response = await service.answer_question(
                question=case['question'],
                document_type=case.get('document_type'),
                max_documents=5
            )
            
            print(f"Execution Successful: {response.execution_successful}")
            print(f"Confidence: {response.confidence:.2f}")
            print(f"Retrieval Grade: {response.retrieval_grade}")
            print(f"Answer: {response.final_answer}")
            
            if not response.execution_successful:
                print("Error handled gracefully")
            
        except Exception as e:
            print(f"Exception caught: {e}")

async def main():
    """Run all examples"""
    
    print("Document Planning System - Usage Examples")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    try:
        # Run all examples
        await example_basic_question_answering()
        await example_document_analysis()
        await example_document_search()
        await example_planning_insights()
        await example_strategy_comparison()
        await example_error_handling()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print(f"Finished at: {datetime.now().isoformat()}")
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        logger.error(f"Error in main: {e}")

def run_examples():
    """Entry point for running examples"""
    asyncio.run(main())

if __name__ == "__main__":
    run_examples()

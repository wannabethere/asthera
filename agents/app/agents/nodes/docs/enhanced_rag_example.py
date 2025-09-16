"""
Example usage of the Enhanced Self-RAG Agent

This example demonstrates how to use the enhanced self-rag agent with:
- Document planning integration
- TF-IDF ranking for better relevance
- Tavily web search as fallback
- Enhanced summarization with metadata
"""

import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

# Import the enhanced agent
from .enhanced_self_rag_agent import EnhancedSelfRAGAgent
from app.schemas.document_schemas import DocumentType
from app.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def example_enhanced_rag_usage():
    """Example: Using the Enhanced Self-RAG Agent"""
    
    print("=" * 60)
    print("ENHANCED SELF-RAG AGENT EXAMPLE")
    print("=" * 60)
    
    # Initialize the enhanced agent
    agent = EnhancedSelfRAGAgent()
    
    # Example questions that would benefit from different features
    test_cases = [
        {
            "question": "What are the key financial metrics mentioned in our quarterly reports?",
            "source_type": DocumentType.GENERIC,
            "description": "Document planning + TF-IDF ranking",
            "expected_features": ["document_planning", "tfidf_ranking", "metadata_extraction"]
        },
        {
            "question": "How has our sales performance changed over the last quarter?",
            "source_type": DocumentType.GENERIC,
            "description": "Document analysis with performance metrics",
            "expected_features": ["document_analysis", "comparative_analysis", "performance_metrics"]
        },
        {
            "question": "What are the latest trends in AI and machine learning for enterprise applications?",
            "source_type": DocumentType.GENERIC,
            "description": "Web search fallback when documents insufficient",
            "expected_features": ["web_search", "tavily_integration", "external_sources"]
        },
        {
            "question": "Compare our Q3 performance with industry benchmarks",
            "source_type": DocumentType.GENERIC,
            "description": "Multi-source analysis with web search",
            "expected_features": ["multi_source", "web_search", "comparative_analysis"]
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*20} TEST CASE {i} {'='*20}")
        print(f"Question: {test_case['question']}")
        print(f"Description: {test_case['description']}")
        print(f"Expected Features: {', '.join(test_case['expected_features'])}")
        print("-" * 60)
        
        try:
            # Run the enhanced agent
            start_time = datetime.now()
            
            response = await agent.run_agent(
                messages=[],  # Empty chat history for this example
                question=test_case['question'],
                source_type=test_case['source_type']
            )
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            # Display results
            print(f"Execution Time: {execution_time:.2f} seconds")
            print(f"Response Type: {type(response)}")
            
            if 'messages' in response and response['messages']:
                message = response['messages'][0]
                print(f"Answer: {message['message_content'][:200]}...")
                
                # Display metadata if available
                if 'message_extra' in message and message['message_extra']:
                    extra = message['message_extra']
                    print(f"Metadata: {extra}")
                
                # Display sources if available
                if 'sources' in message['message_content']:
                    print("Sources included in response")
            else:
                print("No response generated")
                
        except Exception as e:
            print(f"Error in test case {i}: {e}")
            logger.error(f"Error in test case {i}: {e}")

async def example_with_specific_documents():
    """Example: Using specific document IDs"""
    
    print("\n" + "=" * 60)
    print("ENHANCED RAG WITH SPECIFIC DOCUMENTS")
    print("=" * 60)
    
    agent = EnhancedSelfRAGAgent()
    
    # Example with specific document IDs
    document_ids = ["doc_123", "doc_456", "doc_789"]  # Replace with actual document IDs
    
    question = "What are the main findings in these specific documents?"
    
    print(f"Question: {question}")
    print(f"Document IDs: {document_ids}")
    
    try:
        response = await agent.run_agent(
            messages=[],
            question=question,
            source_type=DocumentType.GENERIC,
            document_ids=document_ids
        )
        
        print(f"Response: {response}")
        
    except Exception as e:
        print(f"Error with specific documents: {e}")

async def example_chat_conversation():
    """Example: Multi-turn conversation"""
    
    print("\n" + "=" * 60)
    print("ENHANCED RAG CHAT CONVERSATION")
    print("=" * 60)
    
    agent = EnhancedSelfRAGAgent()
    
    # Simulate a conversation
    conversation = [
        {
            "role": "user",
            "content": "What are our main revenue streams?"
        },
        {
            "role": "assistant", 
            "content": "Based on our financial reports, our main revenue streams include..."
        },
        {
            "role": "user",
            "content": "How has the SaaS revenue changed over time?"
        },
        {
            "role": "assistant",
            "content": "Let me analyze the SaaS revenue trends..."
        },
        {
            "role": "user",
            "content": "What external factors might be affecting our growth?"
        }
    ]
    
    # Process each turn
    chat_history = []
    
    for i, turn in enumerate(conversation):
        print(f"\n--- Turn {i+1} ---")
        print(f"{turn['role'].title()}: {turn['content']}")
        
        if turn['role'] == 'user':
            try:
                response = await agent.run_agent(
                    messages=chat_history,
                    question=turn['content'],
                    source_type=DocumentType.GENERIC
                )
                
                # Add to chat history
                chat_history.append({
                    "message_type": "human",
                    "message_content": turn['content']
                })
                
                if 'messages' in response and response['messages']:
                    assistant_message = response['messages'][0]['message_content']
                    print(f"Assistant: {assistant_message[:200]}...")
                    
                    chat_history.append({
                        "message_type": "ai",
                        "message_content": assistant_message
                    })
                else:
                    print("Assistant: No response generated")
                    
            except Exception as e:
                print(f"Error in turn {i+1}: {e}")

async def example_error_handling():
    """Example: Error handling and edge cases"""
    
    print("\n" + "=" * 60)
    print("ENHANCED RAG ERROR HANDLING")
    print("=" * 60)
    
    agent = EnhancedSelfRAGAgent()
    
    # Test various error conditions
    error_cases = [
        {
            "question": "",
            "description": "Empty question"
        },
        {
            "question": "What is the meaning of life, the universe, and everything?",
            "description": "Very abstract question"
        },
        {
            "question": "Show me all documents from the year 2050",
            "description": "Question about non-existent future data"
        }
    ]
    
    for i, case in enumerate(error_cases, 1):
        print(f"\n--- Error Case {i}: {case['description']} ---")
        print(f"Question: '{case['question']}'")
        
        try:
            response = await agent.run_agent(
                messages=[],
                question=case['question'],
                source_type=DocumentType.GENERIC
            )
            
            if 'messages' in response and response['messages']:
                message = response['messages'][0]
                print(f"Response: {message['message_content'][:150]}...")
                
                # Check if error was handled gracefully
                if "error" in message['message_content'].lower():
                    print("✓ Error handled gracefully")
                else:
                    print("✓ Response generated despite edge case")
            else:
                print("✗ No response generated")
                
        except Exception as e:
            print(f"✗ Exception not caught: {e}")

async def example_performance_analysis():
    """Example: Performance analysis and optimization"""
    
    print("\n" + "=" * 60)
    print("ENHANCED RAG PERFORMANCE ANALYSIS")
    print("=" * 60)
    
    agent = EnhancedSelfRAGAgent()
    
    # Test questions of varying complexity
    complexity_tests = [
        {
            "question": "What is our company name?",
            "expected_complexity": "simple"
        },
        {
            "question": "What are the key metrics in our Q3 financial report?",
            "expected_complexity": "medium"
        },
        {
            "question": "Compare our performance across all departments and identify areas for improvement with specific recommendations",
            "expected_complexity": "complex"
        }
    ]
    
    for test in complexity_tests:
        print(f"\n--- Complexity Test: {test['expected_complexity']} ---")
        print(f"Question: {test['question']}")
        
        # Run multiple times to get average performance
        times = []
        for i in range(3):  # Run 3 times for average
            start_time = datetime.now()
            
            try:
                response = await agent.run_agent(
                    messages=[],
                    question=test['question'],
                    source_type=DocumentType.GENERIC
                )
                
                end_time = datetime.now()
                execution_time = (end_time - start_time).total_seconds()
                times.append(execution_time)
                
            except Exception as e:
                print(f"Error in iteration {i+1}: {e}")
                times.append(0)
        
        if times:
            avg_time = sum(times) / len(times)
            print(f"Average execution time: {avg_time:.2f} seconds")
            print(f"Times: {[f'{t:.2f}s' for t in times]}")
            
            # Performance analysis
            if avg_time < 5:
                print("✓ Good performance")
            elif avg_time < 15:
                print("⚠ Moderate performance")
            else:
                print("✗ Slow performance")

async def main():
    """Run all examples"""
    
    print("Enhanced Self-RAG Agent - Usage Examples")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    try:
        # Run all examples
        await example_enhanced_rag_usage()
        await example_with_specific_documents()
        await example_chat_conversation()
        await example_error_handling()
        await example_performance_analysis()
        
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

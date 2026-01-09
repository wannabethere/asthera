"""
Example: Generate HR Compliance Metadata using Transfer Learning

This example demonstrates how to use the Universal Metadata Framework
to generate HR compliance metadata by learning from cybersecurity patterns.
"""
import asyncio
import os
from langchain_openai import ChatOpenAI

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from knowledge.app.agents import generate_metadata_for_domain


async def main():
    """Generate HR compliance metadata"""
    
    # Initialize LLM
    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        temperature=0.2
    )
    
    # HR compliance documents
    hr_documents = [
        """
        Title VII of the Civil Rights Act of 1964 prohibits employment
        discrimination based on race, color, religion, sex, or national origin.
        Discriminatory hiring practices can result in:
        - EEOC investigations
        - Class-action lawsuits
        - Significant financial penalties
        - Reputational damage
        
        Common violations include:
        - Demographic disparities in hiring rates
        - Biased interview processes
        - Discriminatory job requirements
        """,
        """
        The Fair Labor Standards Act (FLSA) establishes minimum wage, overtime
        pay, recordkeeping, and youth employment standards. Key requirements:
        - Overtime pay (1.5x) for hours worked over 40 per week
        - Proper classification of exempt vs. non-exempt employees
        - Accurate time tracking and recordkeeping
        
        Common violations:
        - Misclassification of employees as exempt
        - Failure to pay overtime
        - Off-the-clock work
        - Meal break violations
        """,
        """
        The Americans with Disabilities Act (ADA) requires employers to provide
        reasonable accommodations for qualified individuals with disabilities.
        Employers must engage in an interactive process to determine appropriate
        accommodations.
        
        Common violations:
        - Failure to provide requested accommodations
        - Delayed accommodation processes
        - Retaliation against employees requesting accommodations
        - Inadequate interactive process
        """,
        """
        The Family and Medical Leave Act (FMLA) provides eligible employees
        with up to 12 weeks of unpaid, job-protected leave per year for:
        - Serious health conditions
        - Birth/adoption of a child
        - Care for family member with serious health condition
        
        Common violations:
        - Interference with FMLA rights
        - Retaliation for taking FMLA leave
        - Failure to restore employee to position
        - Inadequate notice of FMLA rights
        """
    ]
    
    print("=" * 80)
    print("HR Compliance Metadata Generation")
    print("=" * 80)
    print(f"\nGenerating metadata for {len(hr_documents)} HR compliance documents...")
    print("Using transfer learning from cybersecurity domain...\n")
    
    # Generate metadata
    state = await generate_metadata_for_domain(
        target_domain="hr_compliance",
        target_documents=hr_documents,
        source_domains=["cybersecurity"],
        target_framework="GENERAL",
        llm=llm
    )
    
    # Display results
    print("=" * 80)
    print("GENERATION RESULTS")
    print("=" * 80)
    print(f"\nStatus: {state['status']}")
    print(f"Session ID: {state.get('session_id', 'N/A')}")
    print(f"Entries Created: {state['metadata_entries_created']}")
    print(f"Overall Confidence: {state['overall_confidence']:.2%}")
    
    # Display quality scores
    quality_scores = state.get('quality_scores', {})
    if quality_scores:
        print(f"\nQuality Scores:")
        print(f"  - Completeness: {quality_scores.get('completeness', 0):.2%}")
        print(f"  - Consistency: {quality_scores.get('consistency', 0):.2%}")
        print(f"  - Accuracy: {quality_scores.get('accuracy', 0):.2%}")
    
    # Display generated metadata
    refined_metadata = state.get('refined_metadata', [])
    if refined_metadata:
        print(f"\n{'=' * 80}")
        print("GENERATED METADATA ENTRIES")
        print(f"{'=' * 80}\n")
        
        for i, entry in enumerate(refined_metadata, 1):
            print(f"{i}. {entry.get('code', 'N/A').upper()}")
            print(f"   Category: {entry.get('metadata_category', 'N/A')}")
            print(f"   Description: {entry.get('description', 'N/A')}")
            print(f"   Risk Score: {entry.get('risk_score') or entry.get('numeric_score', 0):.1f}")
            
            if entry.get('occurrence_likelihood'):
                print(f"   Occurrence Likelihood: {entry['occurrence_likelihood']:.1f}")
            if entry.get('consequence_severity'):
                print(f"   Consequence Severity: {entry['consequence_severity']:.1f}")
            
            if entry.get('rationale'):
                print(f"   Rationale: {entry['rationale'][:200]}...")
            
            if entry.get('data_indicators'):
                print(f"   Data Indicators: {entry['data_indicators'][:150]}...")
            
            print()
    
    # Display learned patterns
    learned_patterns = state.get('learned_patterns', [])
    if learned_patterns:
        print(f"{'=' * 80}")
        print("LEARNED PATTERNS")
        print(f"{'=' * 80}\n")
        for pattern in learned_patterns[:5]:  # Show first 5
            print(f"- {pattern.get('pattern_name', 'N/A')} ({pattern.get('pattern_type', 'N/A')})")
            print(f"  Confidence: {pattern.get('confidence', 0):.2%}")
            if pattern.get('description'):
                print(f"  {pattern['description'][:100]}...")
            print()
    
    # Display domain mappings
    domain_mappings = state.get('domain_mappings', [])
    if domain_mappings:
        print(f"{'=' * 80}")
        print("DOMAIN MAPPINGS")
        print(f"{'=' * 80}\n")
        for mapping in domain_mappings[:5]:  # Show first 5
            print(f"- {mapping.get('source_domain', 'N/A')}:{mapping.get('source_code', 'N/A')} → "
                  f"{mapping.get('target_domain', 'N/A')}:{mapping.get('target_code', 'N/A')}")
            print(f"  Type: {mapping.get('mapping_type', 'N/A')}, "
                  f"Similarity: {mapping.get('similarity_score', 0):.2%}")
            print()
    
    # Display errors/warnings if any
    errors = state.get('errors', [])
    warnings = state.get('warnings', [])
    
    if errors:
        print(f"{'=' * 80}")
        print("ERRORS")
        print(f"{'=' * 80}\n")
        for error in errors:
            print(f"  - {error}")
        print()
    
    if warnings:
        print(f"{'=' * 80}")
        print("WARNINGS")
        print(f"{'=' * 80}\n")
        for warning in warnings:
            print(f"  - {warning}")
        print()
    
    print("=" * 80)
    print("Generation Complete!")
    print("=" * 80)


if __name__ == "__main__":
    # Set OpenAI API key if not already set
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set")
        print("Please set it before running this example:")
        print("  export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)
    
    asyncio.run(main())


"""
Example usage of ExtractionService with async batch processing
"""
import asyncio
import os
from langchain_openai import ChatOpenAI

from app.services.extraction_service import ExtractionService
from app.services.models import ExtractionRequest, BatchExtractionRequest


async def main():
    """Example of using ExtractionService"""
    
    # Initialize service
    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
    service = ExtractionService(llm=llm)
    await service.initialize()
    
    print("=" * 80)
    print("Example 1: Single Control Extraction")
    print("=" * 80)
    
    # Single extraction
    response = await service.extract_control(
        text="""
        HIPAA requires that covered entities implement access controls to ensure
        that only authorized individuals can access ePHI. This includes both
        physical and technical safeguards.
        """,
        framework="HIPAA",
        context_metadata={
            "industry": "healthcare",
            "organization_size": "medium"
        }
    )
    
    if response.success:
        print(f"✓ Control extracted successfully")
        print(f"  Data: {response.extracted_data}")
    else:
        print(f"✗ Extraction failed: {response.error}")
    
    print("\n" + "=" * 80)
    print("Example 2: Batch Control Extraction")
    print("=" * 80)
    
    # Batch extraction
    texts = [
        {
            "text": "SOC2 requires logical access controls for all systems.",
            "framework": "SOC2",
            "context_metadata": {"industry": "technology"}
        },
        {
            "text": "GDPR requires data encryption for personal data at rest.",
            "framework": "GDPR",
            "context_metadata": {"industry": "finance"}
        },
        {
            "text": "PCI-DSS requires network segmentation for cardholder data.",
            "framework": "PCI-DSS",
            "context_metadata": {"industry": "retail"}
        }
    ]
    
    batch_response = await service.batch_extract_controls(
        texts=texts,
        max_concurrent=3
    )
    
    if batch_response.success:
        print(f"✓ Batch extraction completed")
        print(f"  Total: {batch_response.total}")
        print(f"  Successful: {batch_response.successful}")
        print(f"  Failed: {batch_response.failed}")
        
        for i, result in enumerate(batch_response.results or []):
            if result.get("success"):
                print(f"\n  Result {i+1}: ✓ Success")
                print(f"    Data: {result.get('result', {}).get('data', {})}")
            else:
                print(f"\n  Result {i+1}: ✗ Failed")
                print(f"    Error: {result.get('error', 'Unknown error')}")
    else:
        print(f"✗ Batch extraction failed: {batch_response.error}")
    
    print("\n" + "=" * 80)
    print("Example 3: Context Extraction")
    print("=" * 80)
    
    context_response = await service.extract_context(
        description="""
        We are a mid-sized healthcare organization with 500 employees.
        We handle ePHI and are preparing for our first HIPAA audit in 90 days.
        We use AWS for cloud infrastructure and have basic automation capabilities.
        """
    )
    
    if context_response.success:
        print(f"✓ Context extracted successfully")
        print(f"  Context ID: {context_response.extracted_data.get('context_id')}")
        print(f"  Industry: {context_response.extracted_data.get('industry')}")
        print(f"  Organization Size: {context_response.extracted_data.get('organization_size')}")
    else:
        print(f"✗ Context extraction failed: {context_response.error}")
    
    print("\n" + "=" * 80)
    print("Example 4: Using Request Models Directly")
    print("=" * 80)
    
    # Using request models
    request = ExtractionRequest(
        extraction_type="requirement",
        inputs={
            "requirement_text": "Implement multi-factor authentication",
            "control_id": "HIPAA-AC-001",
            "context_metadata": {"industry": "healthcare"}
        }
    )
    
    req_response = await service.process_request(request)
    if req_response.success:
        print(f"✓ Requirement extraction successful")
        print(f"  Data: {req_response.data}")
    else:
        print(f"✗ Requirement extraction failed: {req_response.error}")
    
    print("\n" + "=" * 80)
    print("Example 5: Batch Context Extraction")
    print("=" * 80)
    
    descriptions = [
        {"description": "Small tech startup, 50 employees, handling PII"},
        {"description": "Large healthcare system, 5000 employees, ePHI, mature compliance"},
        {"description": "Medium finance company, 200 employees, PCI-DSS compliance"}
    ]
    
    batch_context_response = await service.batch_extract_contexts(
        descriptions=descriptions,
        max_concurrent=3
    )
    
    if batch_context_response.success:
        print(f"✓ Batch context extraction completed")
        print(f"  Total: {batch_context_response.total}")
        print(f"  Successful: {batch_context_response.successful}")
        print(f"  Failed: {batch_context_response.failed}")
    
    # Cleanup
    await service._control_pipeline.cleanup()
    await service._context_pipeline.cleanup()
    await service._requirement_pipeline.cleanup()
    await service._evidence_pipeline.cleanup()
    
    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())


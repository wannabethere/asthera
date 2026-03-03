"""
Example usage of the compliance automation workflow.

This demonstrates how to use the LangGraph workflow to generate
compliance artifacts from a user query.
"""
import uuid
from datetime import datetime
from app.agents import get_compliance_app, EnhancedCompliancePipelineState


def example_hipaa_breach_detection():
    """
    Example: Generate complete HIPAA breach detection and response pipeline.
    """
    # Get the compiled workflow app
    app = get_compliance_app()
    
    # Create initial state
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
    initial_state: EnhancedCompliancePipelineState = {
        "user_query": "Build complete HIPAA breach detection and response for requirement 164.308(a)(6)(ii)",
        "messages": [],
        "session_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        
        # Initialize empty artifact lists
        "controls": [],
        "risks": [],
        "scenarios": [],
        "test_cases": [],
        "siem_rules": [],
        "playbooks": [],
        "test_scripts": [],
        "data_pipelines": [],
        
        # Initialize validation & refinement tracking
        "validation_results": [],
        "validation_passed": True,
        "iteration_count": 0,
        "max_iterations": 3,
        "refinement_history": [],
        "context_cache": {},
        
        # Initialize planning
        "execution_plan": None,
        "current_step_index": 0,
        "plan_completion_status": {},
    }
    
    # Run the workflow
    print("Starting compliance automation workflow...")
    print(f"User Query: {initial_state['user_query']}")
    print("-" * 70)
    
    # Invoke the workflow
    final_state = app.invoke(initial_state, config)
    
    # Display results
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)
    
    print(f"\nQuality Score: {final_state.get('quality_score', 0):.1f}/100")
    print(f"Validation Passed: {final_state.get('validation_passed', False)}")
    print(f"Iterations: {final_state.get('iteration_count', 0)}")
    
    print(f"\nGenerated Artifacts:")
    print(f"  - SIEM Rules: {len(final_state.get('siem_rules', []))}")
    print(f"  - Playbooks: {len(final_state.get('playbooks', []))}")
    print(f"  - Test Scripts: {len(final_state.get('test_scripts', []))}")
    print(f"  - Data Pipelines: {len(final_state.get('data_pipelines', []))}")
    
    # Display validation results
    validation_results = final_state.get("validation_results", [])
    if validation_results:
        print(f"\nValidation Results:")
        for result in validation_results:
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"  {status} - {result.artifact_type} ({result.artifact_id}): "
                  f"confidence={result.confidence_score:.2f}")
            if not result.passed and result.issues:
                print(f"    Issues: {len(result.issues)}")
                for issue in result.issues[:3]:  # Show first 3 issues
                    print(f"      - [{issue['severity']}] {issue['message']}")
    
    # Display messages
    messages = final_state.get("messages", [])
    if messages:
        print(f"\nWorkflow Messages ({len(messages)}):")
        for msg in messages[-5:]:  # Show last 5 messages
            if hasattr(msg, 'content'):
                print(f"  - {msg.content[:100]}...")
    
    return final_state


def example_detection_engineering_only():
    """
    Example: Generate only SIEM detection rules.
    """
    app = get_compliance_app()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    
    initial_state: EnhancedCompliancePipelineState = {
        "user_query": "Generate Splunk rules to detect credential stuffing attacks against patient portal",
        "messages": [],
        "session_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "controls": [],
        "risks": [],
        "scenarios": [],
        "test_cases": [],
        "siem_rules": [],
        "playbooks": [],
        "test_scripts": [],
        "data_pipelines": [],
        "validation_results": [],
        "validation_passed": True,
        "iteration_count": 0,
        "max_iterations": 3,
        "refinement_history": [],
        "context_cache": {},
        "execution_plan": None,
        "current_step_index": 0,
        "plan_completion_status": {},
    }
    
    print("Starting detection engineering workflow...")
    final_state = app.invoke(initial_state, config)
    
    print(f"\nGenerated {len(final_state.get('siem_rules', []))} SIEM rules")
    
    return final_state


if __name__ == "__main__":
    # Run example
    example_hipaa_breach_detection()

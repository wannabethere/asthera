"""
Report Writing Agent Example

This example demonstrates how to use the report writing agent with:
1. Different writer actor types
2. Business goal configurations
3. Self-correcting RAG capabilities
4. Quality evaluation and feedback
"""

import asyncio
import json
from typing import Dict, Any
from uuid import uuid4
from datetime import datetime

# Mock data for demonstration
MOCK_THREAD_COMPONENTS = [
    {
        "id": str(uuid4()),
        "component_type": "question",
        "sequence_order": 1,
        "question": "What are the key performance indicators for our sales team?",
        "description": "Analysis of sales team KPIs and performance metrics",
        "overview": {
            "data_source": "Sales CRM",
            "time_period": "Q1 2024",
            "metrics": ["Revenue", "Conversion Rate", "Sales Cycle Length"]
        },
        "chart_config": {
            "type": "line_chart",
            "x_axis": "Month",
            "y_axis": "Revenue"
        },
        "created_at": datetime.now()
    },
    {
        "id": str(uuid4()),
        "component_type": "insight",
        "sequence_order": 2,
        "question": "How do our sales compare to industry benchmarks?",
        "description": "Competitive analysis of sales performance",
        "overview": {
            "benchmark_source": "Industry Reports",
            "comparison_metrics": ["Market Share", "Growth Rate", "Efficiency"]
        },
        "created_at": datetime.now()
    },
    {
        "id": str(uuid4()),
        "component_type": "metric",
        "sequence_order": 3,
        "question": "What is the customer acquisition cost trend?",
        "description": "Analysis of CAC trends and optimization opportunities",
        "overview": {
            "calculation_method": "Total Marketing Spend / New Customers",
            "trend_period": "12 months"
        },
        "created_at": datetime.now()
    }
]

MOCK_BUSINESS_GOALS = {
    "executive": {
        "primary_objective": "Optimize sales team performance and increase revenue by 25%",
        "target_audience": ["C-Suite", "Sales VP", "Board Members"],
        "decision_context": "Strategic planning for Q2-Q4 2024 sales initiatives",
        "success_metrics": ["Revenue Growth", "Sales Efficiency", "Market Share"],
        "timeframe": "Q2-Q4 2024",
        "risk_factors": ["Market Competition", "Economic Conditions", "Team Turnover"]
    },
    "analyst": {
        "primary_objective": "Identify actionable insights to improve sales team productivity",
        "target_audience": ["Sales Managers", "Business Analysts", "Operations Team"],
        "decision_context": "Operational improvements and process optimization",
        "success_metrics": ["Conversion Rate", "Sales Cycle Length", "Lead Quality"],
        "timeframe": "Immediate to 3 months",
        "risk_factors": ["Data Quality", "Implementation Challenges", "Change Resistance"]
    },
    "technical": {
        "primary_objective": "Implement data-driven sales analytics and reporting system",
        "target_audience": ["Data Engineers", "IT Team", "Analytics Team"],
        "decision_context": "Technical architecture and system implementation",
        "success_metrics": ["System Performance", "Data Accuracy", "User Adoption"],
        "timeframe": "6-12 months",
        "risk_factors": ["Technical Complexity", "Integration Challenges", "Resource Constraints"]
    }
}


async def demonstrate_report_generation():
    """Demonstrate the complete report generation process"""
    
    print("🚀 Report Writing Agent Demonstration")
    print("=" * 50)
    
    # Import the agent (this would be from your actual implementation)
    try:
        from app.agents.report_writing_agent import (
            ReportWritingAgent,
            WriterActorType,
            BusinessGoal,
            create_report_writing_agent
        )
        from app.config.report_writing_config import get_config, get_writer_actor_config
        
        print("✅ Successfully imported report writing agent")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("This example assumes the agent is properly installed")
        return
    
    # Demonstrate different writer actor types
    for actor_type in ["executive", "analyst", "technical"]:
        print(f"\n📝 Demonstrating {actor_type.upper()} Writer Actor")
        print("-" * 40)
        
        # Get configuration for this actor type
        actor_config = get_writer_actor_config(actor_type)
        print(f"Actor Configuration: {json.dumps(actor_config, indent=2)}")
        
        # Create business goal
        business_goal_data = MOCK_BUSINESS_GOALS[actor_type]
        business_goal = BusinessGoal(**business_goal_data)
        print(f"Business Goal: {business_goal.primary_objective}")
        
        # Simulate report generation (without actual LLM calls)
        print("Simulating report generation...")
        
        # Mock report result
        mock_report_result = {
            "report_outline": {
                "executive_summary": f"Strategic analysis for {actor_type} audience",
                "sections": [
                    {
                        "title": "Executive Summary",
                        "key_insights": ["Key insight 1", "Key insight 2"],
                        "data_sources": ["Sales CRM", "Industry Reports"],
                        "recommendations": ["Recommendation 1", "Recommendation 2"]
                    }
                ],
                "key_findings": ["Finding 1", "Finding 2", "Finding 3"],
                "overall_recommendations": ["Strategic recommendation 1", "Strategic recommendation 2"],
                "data_quality_assessment": "High quality data with minor gaps",
                "limitations": ["Limited historical data", "Sample size constraints"]
            },
            "final_content": {
                "Executive Summary": f"Comprehensive {actor_type} analysis report content...",
                "Key Findings": "Detailed findings analysis...",
                "Recommendations": "Actionable recommendations..."
            },
            "quality_assessment": {
                "total_sections": 3,
                "average_quality_score": 0.85,
                "overall_grade": "B",
                "strengths": ["Clear structure", "Actionable insights"],
                "areas_for_improvement": ["More data visualization", "Detailed methodology"]
            },
            "correction_history": [],
            "generation_metadata": {
                "writer_actor": actor_type,
                "business_goal": business_goal_data,
                "iterations": 2,
                "generated_at": datetime.now().isoformat()
            }
        }
        
        print(f"✅ Generated report for {actor_type} actor")
        print(f"   Quality Score: {mock_report_result['quality_assessment']['average_quality_score']}")
        print(f"   Overall Grade: {mock_report_result['quality_assessment']['overall_grade']}")
        print(f"   Iterations: {mock_report_result['generation_metadata']['iterations']}")
    
    # Demonstrate configuration options
    print(f"\n⚙️ Configuration Demonstration")
    print("-" * 40)
    
    config = get_config("production")
    print(f"Production Config - LLM Temperature: {config.llm_temperature}")
    print(f"Production Config - Quality Threshold: {config.quality_thresholds.minimum_overall_score}")
    
    dev_config = get_config("development")
    print(f"Development Config - LLM Temperature: {dev_config.llm_temperature}")
    print(f"Development Config - Quality Threshold: {dev_config.quality_thresholds.minimum_overall_score}")
    
    high_quality_config = get_config("high_quality")
    print(f"High Quality Config - Max Iterations: {high_quality_config.self_correction.max_iterations}")
    print(f"High Quality Config - Quality Improvement Threshold: {high_quality_config.self_correction.quality_improvement_threshold}")


def demonstrate_api_usage():
    """Demonstrate how to use the API endpoints"""
    
    print(f"\n🌐 API Usage Demonstration")
    print("-" * 40)
    
    # Example API requests
    api_examples = {
        "Generate Report": {
            "endpoint": "POST /report-writing/generate",
            "request_body": {
                "workflow_id": "uuid-here",
                "writer_actor": "executive",
                "business_goal": {
                    "primary_objective": "Optimize sales performance",
                    "target_audience": ["C-Suite", "Sales VP"],
                    "decision_context": "Strategic planning for Q2-Q4 2024",
                    "success_metrics": ["Revenue Growth", "Sales Efficiency"],
                    "timeframe": "Q2-Q4 2024",
                    "risk_factors": ["Market Competition", "Economic Conditions"]
                }
            }
        },
        "Get Report Status": {
            "endpoint": "GET /report-writing/status/{workflow_id}",
            "response": {
                "workflow_id": "uuid-here",
                "has_generated_report": True,
                "last_generation": "2024-01-15T10:30:00Z",
                "writer_actor": "executive",
                "quality_score": 0.85,
                "iterations": 2
            }
        },
        "Regenerate Report": {
            "endpoint": "POST /report-writing/regenerate/{workflow_id}",
            "request_body": {
                "business_objective": "Updated objective with more focus on efficiency",
                "target_audience": ["C-Suite", "Sales VP", "Operations Team"],
                "decision_context": "Updated context with operational focus",
                "additional_requirements": "Include cost-benefit analysis",
                "style_preferences": {
                    "tone": "more analytical",
                    "include_charts": True
                }
            }
        },
        "Get Quality Metrics": {
            "endpoint": "GET /report-writing/quality-metrics/{workflow_id}",
            "response": {
                "workflow_id": "uuid-here",
                "quality_score": 0.87,
                "iterations": 3,
                "writer_actor": "executive",
                "business_goal_alignment": {"score": 0.9, "feedback": "Excellent alignment"},
                "generation_timestamp": "2024-01-15T10:30:00Z",
                "is_regeneration": False
            }
        }
    }
    
    for operation, details in api_examples.items():
        print(f"\n{operation}:")
        print(f"  Endpoint: {details['endpoint']}")
        if 'request_body' in details:
            print(f"  Request Body: {json.dumps(details['request_body'], indent=4)}")
        if 'response' in details:
            print(f"  Response: {json.dumps(details['response'], indent=4)}")


def demonstrate_self_correcting_rag():
    """Demonstrate the self-correcting RAG capabilities"""
    
    print(f"\n🔧 Self-Correcting RAG Demonstration")
    print("-" * 40)
    
    # Simulate the self-correction process
    correction_steps = [
        {
            "iteration": 1,
            "initial_quality": 0.65,
            "feedback": {
                "relevance_score": 0.6,
                "clarity_score": 0.7,
                "accuracy_score": 0.65,
                "actionability_score": 0.7,
                "overall_score": 0.65,
                "feedback": "Content lacks focus on business impact",
                "suggestions": ["Emphasize ROI", "Add executive summary", "Include action items"]
            },
            "correction_applied": "Restructured content to emphasize business impact and ROI"
        },
        {
            "iteration": 2,
            "improved_quality": 0.82,
            "feedback": {
                "relevance_score": 0.85,
                "clarity_score": 0.8,
                "accuracy_score": 0.8,
                "actionability_score": 0.85,
                "overall_score": 0.82,
                "feedback": "Much better business focus, could improve clarity",
                "suggestions": ["Simplify language", "Add more examples", "Improve structure"]
            },
            "correction_applied": "Simplified language, added examples, improved structure"
        },
        {
            "iteration": 3,
            "final_quality": 0.89,
            "feedback": {
                "relevance_score": 0.9,
                "clarity_score": 0.85,
                "accuracy_score": 0.9,
                "actionability_score": 0.9,
                "overall_score": 0.89,
                "feedback": "Excellent quality, meets business requirements",
                "suggestions": ["Ready for production use"]
            },
            "correction_applied": "Final polish and quality assurance"
        }
    ]
    
    for step in correction_steps:
        print(f"\nIteration {step['iteration']}:")
        if 'initial_quality' in step:
            print(f"  Initial Quality: {step['initial_quality']}")
        if 'improved_quality' in step:
            print(f"  Improved Quality: {step['improved_quality']}")
        if 'final_quality' in step:
            print(f"  Final Quality: {step['final_quality']}")
        
        print(f"  Feedback: {step['feedback']['feedback']}")
        print(f"  Suggestions: {', '.join(step['feedback']['suggestions'])}")
        print(f"  Correction Applied: {step['correction_applied']}")
    
    print(f"\n✅ Self-correction process completed successfully!")
    print(f"   Quality improved from 0.65 to 0.89")
    print(f"   Total iterations: 3")


def main():
    """Main demonstration function"""
    
    print("🎯 Comprehensive Report Writing Agent Demonstration")
    print("=" * 60)
    
    # Run demonstrations
    asyncio.run(demonstrate_report_generation())
    demonstrate_api_usage()
    demonstrate_self_correcting_rag()
    
    print(f"\n🎉 Demonstration completed successfully!")
    print(f"\nKey Features Demonstrated:")
    print(f"  ✅ Multiple writer actor types (Executive, Analyst, Technical)")
    print(f"  ✅ Business goal configuration and validation")
    print(f"  ✅ Self-correcting RAG architecture")
    print(f"  ✅ Quality evaluation and iterative improvement")
    print(f"  ✅ Comprehensive API endpoints")
    print(f"  ✅ Configuration management and presets")
    print(f"  ✅ Thread component integration")
    
    print(f"\nNext Steps:")
    print(f"  1. Integrate with your existing workflow system")
    print(f"  2. Configure LLM providers and API keys")
    print(f"  3. Customize writer actor configurations")
    print(f"  4. Set up quality thresholds for your use case")
    print(f"  5. Test with real thread components and data")


if __name__ == "__main__":
    main()

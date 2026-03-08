#!/usr/bin/env python3
"""
Test suite for compliance pipeline agents using HIPAA breach detection use case.

This test validates the complete compliance-to-operations pipeline:
1. Intent Classification
2. Planning (multi-step execution plan)
3. Framework Analysis (requirement → risk → control mapping)
4. Artifact Generation (SIEM rules, playbooks, test scripts)
5. Validation (syntax, logic, completeness)
6. Iterative Refinement (feedback loop)

Uses .env configuration (lines 6-10) for ChromaDB settings:
- CHROMA_HOST
- CHROMA_PORT
- CHROMA_PERSIST_DIRECTORY

Based on the use case from docs/compliance_usecases.md and agent design from
docs/langgraphlangchain_design.md.
"""
import os
import sys
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load .env file before importing app modules
base_dir = Path(__file__).resolve().parent.parent
env_file = base_dir / ".env"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"✓ Loaded .env file from: {env_file}")
    
    # Verify .env lines 6-10 are loaded
    chroma_host = os.getenv("CHROMA_HOST")
    chroma_port = os.getenv("CHROMA_PORT")
    chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIRECTORY")
    
    print(f"✓ ChromaDB Configuration:")
    print(f"  CHROMA_HOST: {chroma_host}")
    print(f"  CHROMA_PORT: {chroma_port}")
    print(f"  CHROMA_PERSIST_DIRECTORY: {chroma_persist_dir}")
else:
    print("⚠️  No .env file found. Using default environment variables.")

# Add parent directory to path
sys.path.insert(0, str(base_dir))

from app.agents.detectiontriageworkflows.workflow import create_compliance_app
from app.agents.state import EnhancedCompliancePipelineState
from langgraph.checkpoint.memory import MemorySaver

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class CompliancePipelineTester:
    """Test suite for compliance pipeline agents."""
    
    def __init__(self):
        self.app = None
        self.checkpointer = MemorySaver()
        self.config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self.results = []
    
    def setup(self):
        """Initialize the compliance app."""
        logger.info("Setting up compliance pipeline app...")
        self.app = create_compliance_app(checkpointer=self.checkpointer)
        logger.info("✓ Compliance app initialized")
    
    def create_initial_state(self, user_query: str) -> EnhancedCompliancePipelineState:
        """Create initial state for the pipeline."""
        return {
            "user_query": user_query,
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
            "dashboards": [],
            "vulnerability_mappings": [],
            
            # Initialize execution logging
            "execution_steps": [],
            "gap_analysis_results": [],
            "cross_framework_mappings": [],
            "metrics_context": [],
            "xsoar_indicators": [],
            
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
            
            # Optional fields
            "intent": None,
            "framework_id": None,
            "requirement_id": None,
            "requirement_code": None,
            "requirement_name": None,
            "requirement_description": None,
            "next_agent": None,
            "error": None,
            "quality_score": None,
            
            # New fields for profile/metrics/calculation flow
            "data_enrichment": {
                "needs_mdl": False,
                "needs_metrics": False,
                "needs_xsoar_dashboard": False,
                "suggested_focus_areas": [],
                "metrics_intent": None
            },
            "compliance_profile": None,
            "selected_data_sources": [],
            "resolved_focus_areas": [],
            "focus_area_categories": [],
            "resolved_metrics": [],
            "calculation_plan": None,
        }
    
    def test_hipaa_breach_detection_pipeline(self) -> Dict[str, Any]:
        """
        Test the complete HIPAA breach detection pipeline.
        
        Based on the use case from compliance_usecases.md:
        - Requirement: HIPAA §164.308(a)(6)(ii) - Response and Reporting
        - Expected outputs: SIEM rules, playbooks, test scripts
        """
        logger.info("=" * 80)
        logger.info("TEST: HIPAA Breach Detection Pipeline")
        logger.info("=" * 80)
        
        user_query = (
            "Build complete HIPAA breach detection and response pipeline "
            "for requirement 164.308(a)(6)(ii) - Security Incident Procedures. "
            "I need SIEM detection rules, incident response playbooks, and "
            "automated test scripts for validating controls."
        )
        
        initial_state = self.create_initial_state(user_query)
        
        try:
            # Run the pipeline
            logger.info(f"Executing pipeline with query: {user_query[:100]}...")
            result = self.app.invoke(initial_state, self.config)
            
            # Validate results
            validation_results = self.validate_pipeline_output(result)
            
            return {
                "test_name": "hipaa_breach_detection_pipeline",
                "success": validation_results["overall_success"],
                "user_query": user_query,
                "result": result,
                "validation": validation_results,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            return {
                "test_name": "hipaa_breach_detection_pipeline",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def validate_pipeline_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the pipeline output against expected criteria."""
        validation = {
            "overall_success": True,
            "checks": {},
            "issues": []
        }
        
        # Check 1: Intent was classified
        intent = result.get("intent")
        validation["checks"]["intent_classified"] = intent is not None
        if not intent:
            validation["issues"].append("Intent was not classified")
            validation["overall_success"] = False
        
        # Check 1a: Profile was resolved (new flow)
        compliance_profile = result.get("compliance_profile")
        selected_data_sources = result.get("selected_data_sources", [])
        validation["checks"]["profile_resolved"] = compliance_profile is not None or len(selected_data_sources) > 0
        if not validation["checks"]["profile_resolved"]:
            validation["issues"].append("Profile was not resolved")
        
        # Check 1b: Focus areas were resolved (new flow)
        resolved_focus_areas = result.get("resolved_focus_areas", [])
        focus_area_categories = result.get("focus_area_categories", [])
        validation["checks"]["focus_areas_resolved"] = len(resolved_focus_areas) > 0 or len(focus_area_categories) > 0
        if not validation["checks"]["focus_areas_resolved"]:
            validation["issues"].append("Focus areas were not resolved")
        
        # Check 1c: Metrics resolved (if dashboard intent)
        if intent == "dashboard_generation":
            resolved_metrics = result.get("resolved_metrics", [])
            validation["checks"]["metrics_resolved"] = len(resolved_metrics) > 0
            if not validation["checks"]["metrics_resolved"]:
                validation["issues"].append("Metrics were not resolved for dashboard intent")
            else:
                logger.info(f"  ✓ Metrics resolved: {len(resolved_metrics)}")
        
        # Check 2: Execution plan was created
        execution_plan = result.get("execution_plan")
        validation["checks"]["plan_created"] = execution_plan is not None and len(execution_plan) > 0
        if not validation["checks"]["plan_created"]:
            validation["issues"].append("No execution plan was created")
            validation["overall_success"] = False
        else:
            validation["checks"]["plan_steps"] = len(execution_plan)
            logger.info(f"  ✓ Execution plan created with {len(execution_plan)} steps")
        
        # Check 3: Framework metadata extracted
        framework_id = result.get("framework_id")
        requirement_code = result.get("requirement_code")
        validation["checks"]["framework_extracted"] = framework_id is not None
        validation["checks"]["requirement_extracted"] = requirement_code is not None
        
        if framework_id:
            logger.info(f"  ✓ Framework ID: {framework_id}")
        if requirement_code:
            logger.info(f"  ✓ Requirement Code: {requirement_code}")
        
        # Check 4: Context was retrieved (controls, risks, scenarios)
        controls = result.get("controls", [])
        risks = result.get("risks", [])
        scenarios = result.get("scenarios", [])
        test_cases = result.get("test_cases", [])
        
        validation["checks"]["controls_retrieved"] = len(controls) > 0
        validation["checks"]["risks_retrieved"] = len(risks) > 0
        validation["checks"]["scenarios_retrieved"] = len(scenarios) > 0
        validation["checks"]["test_cases_retrieved"] = len(test_cases) > 0
        
        logger.info(f"  ✓ Controls retrieved: {len(controls)}")
        logger.info(f"  ✓ Risks retrieved: {len(risks)}")
        logger.info(f"  ✓ Scenarios retrieved: {len(scenarios)}")
        logger.info(f"  ✓ Test cases retrieved: {len(test_cases)}")
        
        # Check 5: Artifacts were generated
        siem_rules = result.get("siem_rules", [])
        playbooks = result.get("playbooks", [])
        test_scripts = result.get("test_scripts", [])
        
        validation["checks"]["siem_rules_generated"] = len(siem_rules) > 0
        validation["checks"]["playbooks_generated"] = len(playbooks) > 0
        validation["checks"]["test_scripts_generated"] = len(test_scripts) > 0
        
        logger.info(f"  ✓ SIEM rules generated: {len(siem_rules)}")
        logger.info(f"  ✓ Playbooks generated: {len(playbooks)}")
        logger.info(f"  ✓ Test scripts generated: {len(test_scripts)}")
        
        # Check 6: Artifact quality
        if siem_rules:
            for rule in siem_rules:
                has_spl = "spl_code" in rule or "spl" in rule.get("content", "")
                has_name = "name" in rule or "title" in rule
                has_severity = "severity" in rule
                
                if not (has_spl and has_name and has_severity):
                    validation["issues"].append(f"SIEM rule missing required fields: {rule.get('id', 'unknown')}")
        
        if playbooks:
            for playbook in playbooks:
                has_content = "markdown_content" in playbook or "content" in playbook
                has_sections = False
                if has_content:
                    content = playbook.get("markdown_content", playbook.get("content", ""))
                    # Check for key sections
                    has_sections = any(
                        section in content.upper() 
                        for section in ["DETECT", "TRIAGE", "CONTAIN", "INVESTIGATE", "REMEDIATE"]
                    )
                
                if not (has_content and has_sections):
                    validation["issues"].append(f"Playbook missing required sections: {playbook.get('id', 'unknown')}")
        
        if test_scripts:
            for script in test_scripts:
                has_code = "python_code" in script or "code" in script
                has_test_function = False
                if has_code:
                    code = script.get("python_code", script.get("code", ""))
                    has_test_function = "def test_" in code.lower()
                
                if not (has_code and has_test_function):
                    validation["issues"].append(f"Test script missing test function: {script.get('id', 'unknown')}")
        
        # Check 7: Validation was performed
        validation_results = result.get("validation_results", [])
        validation["checks"]["validation_performed"] = len(validation_results) > 0
        
        if validation_results:
            passed_count = sum(1 for v in validation_results if v.passed)
            total_count = len(validation_results)
            validation["checks"]["validation_pass_rate"] = passed_count / total_count if total_count > 0 else 0
            logger.info(f"  ✓ Validation performed: {passed_count}/{total_count} passed")
        
        # Check 8: Quality score
        quality_score = result.get("quality_score")
        if quality_score is not None:
            validation["checks"]["quality_score"] = quality_score
            logger.info(f"  ✓ Quality score: {quality_score:.1f}/100")
        
        # Check 9: Calculation plan (if dashboard intent)
        if intent == "dashboard_generation":
            calculation_plan = result.get("calculation_plan")
            validation["checks"]["calculation_plan_generated"] = calculation_plan is not None
            if calculation_plan:
                field_instructions = calculation_plan.get("field_instructions", [])
                metric_instructions = calculation_plan.get("metric_instructions", [])
                validation["checks"]["calculation_plan_has_instructions"] = (
                    len(field_instructions) > 0 or len(metric_instructions) > 0
                )
                if validation["checks"]["calculation_plan_has_instructions"]:
                    logger.info(f"  ✓ Calculation plan: {len(field_instructions)} fields, {len(metric_instructions)} metrics")
        
        # Check 10: No critical errors
        error = result.get("error")
        validation["checks"]["no_errors"] = error is None
        if error:
            validation["issues"].append(f"Pipeline error: {error}")
            validation["overall_success"] = False
        
        # Update overall success based on critical checks
        critical_checks = [
            "intent_classified",
            "plan_created",
            "siem_rules_generated",
            "playbooks_generated",
            "test_scripts_generated",
            "no_errors"
        ]
        
        # For dashboard intent, also check metrics and calculation plan
        if intent == "dashboard_generation":
            if not validation["checks"].get("metrics_resolved", False):
                validation["overall_success"] = False
        
        for check in critical_checks:
            if not validation["checks"].get(check, False):
                validation["overall_success"] = False
        
        return validation
    
    def test_planner_agent(self) -> Dict[str, Any]:
        """Test the planner agent in isolation."""
        logger.info("=" * 80)
        logger.info("TEST: Planner Agent")
        logger.info("=" * 80)
        
        user_query = "Build HIPAA breach detection for requirement 164.308(a)(6)(ii)"
        
        initial_state = self.create_initial_state(user_query)
        initial_state["intent"] = "compliance_validation"  # Set intent directly
        
        try:
            from app.agents.nodes import planner_node
            
            # Run planner
            result = planner_node(initial_state)
            
            # Validate plan
            plan = result.get("execution_plan")
            success = plan is not None and len(plan) > 0
            
            if success:
                logger.info(f"  ✓ Plan created with {len(plan)} steps")
                for i, step in enumerate(plan, 1):
                    logger.info(f"    Step {i}: {step.description} → {step.agent}")
            
            return {
                "test_name": "planner_agent",
                "success": success,
                "plan_steps": len(plan) if plan else 0,
                "plan": [{"step_id": s.step_id, "description": s.description, "agent": s.agent} for s in plan] if plan else [],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Planner test failed: {e}", exc_info=True)
            return {
                "test_name": "planner_agent",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_detection_engineer_agent(self) -> Dict[str, Any]:
        """Test the detection engineer agent in isolation."""
        logger.info("=" * 80)
        logger.info("TEST: Detection Engineer Agent")
        logger.info("=" * 80)
        
        initial_state = self.create_initial_state("Generate SIEM rules")
        
        # Mock context
        initial_state["scenarios"] = [
            {
                "id": "HIPAA-SCENARIO-012",
                "name": "Credential stuffing attack against patient portal",
                "severity": "critical",
                "description": "Attacker uses leaked credentials to access patient records"
            }
        ]
        initial_state["controls"] = [
            {
                "id": "AM-5",
                "control_code": "AM-5",
                "name": "Multi-factor authentication for ePHI access",
                "control_type": "preventive"
            }
        ]
        initial_state["requirement_code"] = "164.308(a)(6)(ii)"
        initial_state["framework_id"] = "hipaa"
        
        try:
            from app.agents.nodes import detection_engineer_node
            
            # Run detection engineer
            result = detection_engineer_node(initial_state)
            
            # Validate output
            siem_rules = result.get("siem_rules", [])
            success = len(siem_rules) > 0
            
            if success:
                logger.info(f"  ✓ Generated {len(siem_rules)} SIEM rules")
                for rule in siem_rules:
                    has_spl = "spl_code" in rule or "spl" in str(rule)
                    logger.info(f"    Rule: {rule.get('name', 'unnamed')} - SPL: {'✓' if has_spl else '✗'}")
            
            return {
                "test_name": "detection_engineer_agent",
                "success": success,
                "rules_generated": len(siem_rules),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Detection engineer test failed: {e}", exc_info=True)
            return {
                "test_name": "detection_engineer_agent",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_playbook_writer_agent(self) -> Dict[str, Any]:
        """Test the playbook writer agent in isolation."""
        logger.info("=" * 80)
        logger.info("TEST: Playbook Writer Agent")
        logger.info("=" * 80)
        
        initial_state = self.create_initial_state("Generate incident response playbook")
        
        # Mock context
        initial_state["scenarios"] = [
            {
                "id": "HIPAA-SCENARIO-012",
                "name": "Credential stuffing attack",
                "severity": "critical"
            }
        ]
        initial_state["controls"] = [
            {
                "id": "AM-5",
                "control_code": "AM-5",
                "name": "Multi-factor authentication"
            }
        ]
        initial_state["test_cases"] = [
            {
                "id": "TEST-AM-5-001",
                "name": "Verify MFA enforced",
                "test_type": "preventive_control_verification"
            }
        ]
        
        try:
            from app.agents.nodes import playbook_writer_node
            
            # Run playbook writer
            result = playbook_writer_node(initial_state)
            
            # Validate output
            playbooks = result.get("playbooks", [])
            success = len(playbooks) > 0
            
            if success:
                logger.info(f"  ✓ Generated {len(playbooks)} playbooks")
                for pb in playbooks:
                    has_content = "markdown_content" in pb or "content" in pb
                    logger.info(f"    Playbook: {pb.get('name', 'unnamed')} - Content: {'✓' if has_content else '✗'}")
            
            return {
                "test_name": "playbook_writer_agent",
                "success": success,
                "playbooks_generated": len(playbooks),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Playbook writer test failed: {e}", exc_info=True)
            return {
                "test_name": "playbook_writer_agent",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_test_generator_agent(self) -> Dict[str, Any]:
        """Test the test generator agent in isolation."""
        logger.info("=" * 80)
        logger.info("TEST: Test Generator Agent")
        logger.info("=" * 80)
        
        initial_state = self.create_initial_state("Generate test scripts")
        initial_state["intent"] = "test_generation"
        initial_state["data_enrichment"] = {
            "needs_metrics": True,
            "metrics_intent": "current_state"
        }
        
        # Mock context
        initial_state["controls"] = [
            {
                "id": "AM-5",
                "control_code": "AM-5",
                "name": "Multi-factor authentication",
                "control_type": "preventive"
            }
        ]
        initial_state["test_cases"] = [
            {
                "id": "TEST-AM-5-001",
                "name": "Verify MFA enforced on all ePHI systems",
                "test_type": "preventive_control_verification",
                "pass_criteria": "100% of ePHI access requires MFA"
            }
        ]
        initial_state["requirement_code"] = "164.308(a)(6)(ii)"
        
        try:
            from app.agents.nodes import test_generator_node
            
            # Run test generator
            result = test_generator_node(initial_state)
            
            # Validate output
            test_scripts = result.get("test_scripts", [])
            success = len(test_scripts) > 0
            
            # Capture LLM response and prompt for review
            llm_response = result.get("llm_response", "")
            llm_prompt = result.get("llm_prompt", {})
            
            if success:
                logger.info(f"  ✓ Generated {len(test_scripts)} test scripts")
                for script in test_scripts:
                    has_code = "python_code" in script or "code" in script
                    logger.info(f"    Script: {script.get('name', 'unnamed')} - Code: {'✓' if has_code else '✗'}")
            
            # Get execution steps for JSON output
            execution_steps = result.get("execution_steps", [])
            
            return {
                "test_name": "test_generator_agent",
                "success": success,
                "scripts_generated": len(test_scripts),
                "test_scripts": test_scripts,  # Include full test scripts
                "llm_response": llm_response,  # Include full LLM response
                "llm_prompt": llm_prompt,  # Include prompt for validation
                "execution_steps": execution_steps,  # Include all execution steps with inputs/outputs
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Test generator test failed: {e}", exc_info=True)
            return {
                "test_name": "test_generator_agent",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_dashboard_generator_agent(self) -> Dict[str, Any]:
        """Test the dashboard generator agent in isolation."""
        logger.info("=" * 80)
        logger.info("TEST: Dashboard Generator Agent")
        logger.info("=" * 80)
        
        initial_state = self.create_initial_state("Generate compliance dashboard for HIPAA")
        initial_state["intent"] = "dashboard_generation"
        initial_state["framework_id"] = "hipaa"
        initial_state["requirement_code"] = "164.308(a)(6)(ii)"
        initial_state["data_enrichment"] = {
            "needs_mdl": True,
            "needs_metrics": True,
            "needs_xsoar_dashboard": True,
            "suggested_focus_areas": ["audit_logging", "access_control"],
            "metrics_intent": "current_state"
        }
        initial_state["selected_data_sources"] = ["qualys", "snyk"]
        initial_state["focus_area_categories"] = ["vulnerabilities", "audit_logging"]
        
        # Mock context
        initial_state["controls"] = [
            {
                "id": "AM-5",
                "control_code": "AM-5",
                "name": "Multi-factor authentication",
                "control_type": "preventive"
            },
            {
                "id": "AU-12",
                "control_code": "AU-12",
                "name": "Centralized security event logging",
                "control_type": "detective"
            }
        ]
        initial_state["requirements"] = [
            {
                "id": "hipaa__164_308_a__6__ii",
                "requirement_code": "164.308(a)(6)(ii)",
                "name": "Security Incident Procedures - Response and Reporting",
                "description": "Identify and respond to suspected or known security incidents"
            }
        ]
        
        try:
            from app.agents.nodes import dashboard_generator_node
            
            # Run dashboard generator
            result = dashboard_generator_node(initial_state)
            
            # Validate output
            dashboards = result.get("dashboards", [])
            success = len(dashboards) > 0
            
            # Capture LLM response and prompt for review
            llm_response = result.get("llm_response", "")
            llm_prompt = result.get("llm_prompt", {})
            
            if success:
                logger.info(f"  ✓ Generated {len(dashboards)} dashboard(s)")
                for dashboard in dashboards:
                    has_spec = "dashboard_spec" in dashboard or "specification" in dashboard
                    logger.info(f"    Dashboard: {dashboard.get('name', 'unnamed')} - Spec: {'✓' if has_spec else '✗'}")
            
            # Get execution steps for JSON output
            execution_steps = result.get("execution_steps", [])
            
            return {
                "test_name": "dashboard_generator_agent",
                "success": success,
                "dashboards_generated": len(dashboards),
                "dashboards": dashboards,  # Include full dashboards
                "llm_response": llm_response,  # Include full LLM response
                "llm_prompt": llm_prompt,  # Include prompt for validation
                "execution_steps": execution_steps,  # Include all execution steps with inputs/outputs
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Dashboard generator test failed: {e}", exc_info=True)
            return {
                "test_name": "dashboard_generator_agent",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_profile_resolver_agent(self) -> Dict[str, Any]:
        """Test the profile resolver agent in isolation."""
        logger.info("=" * 80)
        logger.info("TEST: Profile Resolver Agent")
        logger.info("=" * 80)
        
        initial_state = self.create_initial_state("Generate dashboard for SOC2")
        initial_state["intent"] = "dashboard_generation"
        initial_state["framework_id"] = "soc2"
        initial_state["data_enrichment"] = {
            "needs_mdl": True,
            "needs_metrics": True,
            "needs_xsoar_dashboard": True,
            "suggested_focus_areas": ["vulnerability_management"],
            "metrics_intent": "trend"
        }
        
        try:
            from app.agents.nodes import profile_resolver_node
            
            # Run profile resolver
            result = profile_resolver_node(initial_state)
            
            # Validate output
            compliance_profile = result.get("compliance_profile")
            selected_data_sources = result.get("selected_data_sources", [])
            resolved_focus_areas = result.get("resolved_focus_areas", [])
            focus_area_categories = result.get("focus_area_categories", [])
            
            success = (
                compliance_profile is not None and
                len(selected_data_sources) > 0 and
                len(resolved_focus_areas) > 0 and
                len(focus_area_categories) > 0
            )
            
            if success:
                logger.info(f"  ✓ Profile resolved")
                logger.info(f"    Data sources: {selected_data_sources}")
                logger.info(f"    Focus areas: {len(resolved_focus_areas)}")
                logger.info(f"    Categories: {focus_area_categories}")
            
            return {
                "test_name": "profile_resolver_agent",
                "success": success,
                "compliance_profile": compliance_profile,
                "selected_data_sources": selected_data_sources,
                "resolved_focus_areas_count": len(resolved_focus_areas),
                "focus_area_categories": focus_area_categories,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Profile resolver test failed: {e}", exc_info=True)
            return {
                "test_name": "profile_resolver_agent",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_metrics_recommender_agent(self) -> Dict[str, Any]:
        """Test the metrics recommender agent in isolation."""
        logger.info("=" * 80)
        logger.info("TEST: Metrics Recommender Agent")
        logger.info("=" * 80)
        
        initial_state = self.create_initial_state("Show vulnerability metrics with trends")
        initial_state["intent"] = "dashboard_generation"
        initial_state["framework_id"] = "soc2"
        initial_state["selected_data_sources"] = ["qualys", "snyk"]
        initial_state["focus_area_categories"] = ["vulnerabilities"]
        initial_state["data_enrichment"] = {
            "needs_metrics": True,
            "metrics_intent": "trend"
        }
        
        try:
            from app.agents.nodes import metrics_recommender_node
            
            # Run metrics recommender
            result = metrics_recommender_node(initial_state)
            
            # Validate output
            resolved_metrics = result.get("resolved_metrics", [])
            success = len(resolved_metrics) > 0
            
            if success:
                logger.info(f"  ✓ Resolved {len(resolved_metrics)} metrics")
                for metric in resolved_metrics[:3]:  # Show first 3
                    metric_id = metric.get("metric_id", "unknown")
                    name = metric.get("name", "unnamed")
                    source_schemas = metric.get("source_schemas", [])
                    kpis = metric.get("kpis", [])
                    logger.info(f"    Metric: {name} ({metric_id})")
                    logger.info(f"      Source schemas: {len(source_schemas)}")
                    logger.info(f"      KPIs: {len(kpis)}")
            
            return {
                "test_name": "metrics_recommender_agent",
                "success": success,
                "metrics_resolved": len(resolved_metrics),
                "resolved_metrics": resolved_metrics[:5] if resolved_metrics else [],  # Include first 5 for validation
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Metrics recommender test failed: {e}", exc_info=True)
            return {
                "test_name": "metrics_recommender_agent",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_calculation_planner_agent(self) -> Dict[str, Any]:
        """Test the calculation planner agent in isolation."""
        logger.info("=" * 80)
        logger.info("TEST: Calculation Planner Agent")
        logger.info("=" * 80)
        
        initial_state = self.create_initial_state("Calculate vulnerability remediation metrics with trends")
        initial_state["intent"] = "dashboard_generation"
        initial_state["framework_id"] = "soc2"
        
        # Mock resolved metrics
        initial_state["resolved_metrics"] = [
            {
                "metric_id": "vuln_count_by_severity",
                "name": "Vulnerability Count by Severity",
                "description": "Count of vulnerabilities grouped by severity",
                "category": "vulnerabilities",
                "source_schemas": ["vulnerability_instances_schema", "cve_schema"],
                "source_capabilities": ["qualys.vulnerabilities"],
                "kpis": ["Critical vuln count", "High vuln count"],
                "trends": ["Vuln count over time"],
                "natural_language_question": "How many critical and high severity vulnerabilities do we have?",
                "data_capability": ["temporal", "semantic"]
            }
        ]
        
        # Mock schema resolution output
        initial_state["context_cache"] = {
            "schema_resolution": {
                "schemas": [
                    {
                        "table_name": "vulnerabilities",
                        "table_ddl": "CREATE TABLE vulnerabilities (id VARCHAR, severity VARCHAR, status VARCHAR, created_at TIMESTAMP, fixed_at TIMESTAMP)",
                        "description": "Vulnerability tracking table",
                        "column_metadata": [
                            {"name": "id", "type": "VARCHAR"},
                            {"name": "severity", "type": "VARCHAR"},
                            {"name": "status", "type": "VARCHAR"},
                            {"name": "created_at", "type": "TIMESTAMP"},
                            {"name": "fixed_at", "type": "TIMESTAMP"}
                        ]
                    }
                ],
                "table_descriptions": []
            }
        }
        
        try:
            from app.agents.dt_nodes import calculation_planner_node
            
            # Run calculation planner
            result = calculation_planner_node(initial_state)
            
            # Validate output
            calculation_plan = result.get("calculation_plan")
            success = (
                calculation_plan is not None and
                "field_instructions" in calculation_plan and
                "metric_instructions" in calculation_plan
            )
            
            if success:
                field_instructions = calculation_plan.get("field_instructions", [])
                metric_instructions = calculation_plan.get("metric_instructions", [])
                silver_suggestion = calculation_plan.get("silver_time_series_suggestion")
                
                logger.info(f"  ✓ Calculation plan generated")
                logger.info(f"    Field instructions: {len(field_instructions)}")
                logger.info(f"    Metric instructions: {len(metric_instructions)}")
                logger.info(f"    Silver time series: {'✓' if silver_suggestion else '✗'}")
                
                if field_instructions:
                    logger.info(f"    Example field: {field_instructions[0].get('name', 'unknown')}")
                if metric_instructions:
                    logger.info(f"    Example metric: {metric_instructions[0].get('name', 'unknown')}")
            
            return {
                "test_name": "calculation_planner_agent",
                "success": success,
                "calculation_plan": calculation_plan,
                "field_instructions_count": len(calculation_plan.get("field_instructions", [])) if calculation_plan else 0,
                "metric_instructions_count": len(calculation_plan.get("metric_instructions", [])) if calculation_plan else 0,
                "has_silver_suggestion": bool(calculation_plan.get("silver_time_series_suggestion")) if calculation_plan else False,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Calculation planner test failed: {e}", exc_info=True)
            return {
                "test_name": "calculation_planner_agent",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_dashboard_generation_flow(self) -> Dict[str, Any]:
        """Test the complete dashboard generation flow with new nodes."""
        logger.info("=" * 80)
        logger.info("TEST: Dashboard Generation Flow (New Workflow)")
        logger.info("=" * 80)
        
        user_query = (
            "Show me my SOC2 vulnerability management compliance posture with trends. "
            "I need a dashboard with KPIs and time-series metrics."
        )
        
        initial_state = self.create_initial_state(user_query)
        
        try:
            from app.agents.nodes import (
                intent_classifier_node,
                profile_resolver_node,
                metrics_recommender_node,
                dashboard_generator_node
            )
            from app.agents.dt_nodes import (
                calculation_planner_node
            )
            
            # Step 1: Intent classification
            logger.info("Step 1: Intent Classification")
            result = intent_classifier_node(initial_state)
            intent = result.get("intent")
            data_enrichment = result.get("data_enrichment", {})
            logger.info(f"  ✓ Intent: {intent}")
            logger.info(f"  ✓ Data enrichment: {data_enrichment}")
            
            # Step 2: Profile resolution
            logger.info("Step 2: Profile Resolution")
            result = profile_resolver_node(result)
            selected_data_sources = result.get("selected_data_sources", [])
            resolved_focus_areas = result.get("resolved_focus_areas", [])
            focus_area_categories = result.get("focus_area_categories", [])
            logger.info(f"  ✓ Data sources: {selected_data_sources}")
            logger.info(f"  ✓ Focus areas: {len(resolved_focus_areas)}")
            logger.info(f"  ✓ Categories: {focus_area_categories}")
            
            # Step 3: Metrics recommendation
            logger.info("Step 3: Metrics Recommendation")
            result = metrics_recommender_node(result)
            resolved_metrics = result.get("resolved_metrics", [])
            logger.info(f"  ✓ Resolved metrics: {len(resolved_metrics)}")
            if resolved_metrics:
                for metric in resolved_metrics[:2]:
                    logger.info(f"    - {metric.get('name', 'unknown')} ({metric.get('metric_id', 'unknown')})")
            
            # Step 4: Calculation planning (if metrics and schemas available)
            if resolved_metrics and result.get("context_cache", {}).get("schema_resolution"):
                logger.info("Step 4: Calculation Planning")
                result = calculation_planner_node(result)
                calculation_plan = result.get("calculation_plan")
                if calculation_plan:
                    field_instructions = calculation_plan.get("field_instructions", [])
                    metric_instructions = calculation_plan.get("metric_instructions", [])
                    logger.info(f"  ✓ Field instructions: {len(field_instructions)}")
                    logger.info(f"  ✓ Metric instructions: {len(metric_instructions)}")
            else:
                logger.info("Step 4: Calculation Planning (skipped - no schemas)")
                calculation_plan = None
            
            # Step 5: Dashboard generation
            logger.info("Step 5: Dashboard Generation")
            result = dashboard_generator_node(result)
            dashboards = result.get("dashboards", [])
            logger.info(f"  ✓ Dashboards generated: {len(dashboards)}")
            
            # Validate complete flow
            success = (
                intent == "dashboard_generation" and
                len(selected_data_sources) > 0 and
                len(resolved_focus_areas) > 0 and
                len(resolved_metrics) > 0 and
                len(dashboards) > 0
            )
            
            return {
                "test_name": "dashboard_generation_flow",
                "success": success,
                "intent": intent,
                "selected_data_sources": selected_data_sources,
                "resolved_focus_areas_count": len(resolved_focus_areas),
                "focus_area_categories": focus_area_categories,
                "resolved_metrics_count": len(resolved_metrics),
                "calculation_plan_generated": calculation_plan is not None,
                "dashboards_generated": len(dashboards),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Dashboard generation flow test failed: {e}", exc_info=True)
            return {
                "test_name": "dashboard_generation_flow",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def test_risk_control_mapper_agent(self) -> Dict[str, Any]:
        """Test the risk control mapper agent in isolation."""
        logger.info("=" * 80)
        logger.info("TEST: Risk Control Mapper Agent")
        logger.info("=" * 80)
        
        initial_state = self.create_initial_state("Map CVE-2024-50349 to HIPAA controls and risks")
        initial_state["framework_id"] = "hipaa"
        
        # Mock context
        initial_state["controls"] = [
            {
                "id": "IR-8",
                "control_code": "IR-8",
                "name": "Endpoint detection and response deployed",
                "control_type": "detective"
            },
            {
                "id": "SI-3",
                "control_code": "SI-3",
                "name": "Malicious code protection",
                "control_type": "preventive"
            }
        ]
        initial_state["risks"] = [
            {
                "id": "HIPAA-RISK-041",
                "risk_code": "HIPAA-RISK-041",
                "name": "Malware infection leading to ePHI exfiltration",
                "likelihood": 0.6,
                "impact": 0.95
            }
        ]
        initial_state["scenarios"] = [
            {
                "id": "HIPAA-SCENARIO-034",
                "name": "Ransomware deployment via phishing email",
                "severity": "critical"
            }
        ]
        
        try:
            from app.agents.nodes import risk_control_mapper_node
            
            # Run risk control mapper
            result = risk_control_mapper_node(initial_state)
            
            # Validate output
            vulnerability_mappings = result.get("vulnerability_mappings", [])
            success = len(vulnerability_mappings) > 0
            
            # Capture LLM response and prompt for review
            llm_response = result.get("llm_response", "")
            llm_prompt = result.get("llm_prompt", {})
            
            if success:
                logger.info(f"  ✓ Generated {len(vulnerability_mappings)} vulnerability mapping(s)")
                for mapping in vulnerability_mappings:
                    has_cve = "cve_id" in mapping or "vulnerability_id" in mapping
                    has_controls = "controls" in mapping or "mapped_controls" in mapping
                    logger.info(f"    Mapping: {mapping.get('cve_id', 'unnamed')} - Controls: {'✓' if has_controls else '✗'}")
            
            # Get execution steps for JSON output
            execution_steps = result.get("execution_steps", [])
            
            return {
                "test_name": "risk_control_mapper_agent",
                "success": success,
                "mappings_generated": len(vulnerability_mappings),
                "vulnerability_mappings": vulnerability_mappings,  # Include full mappings
                "llm_response": llm_response,  # Include full LLM response
                "llm_prompt": llm_prompt,  # Include prompt for validation
                "execution_steps": execution_steps,  # Include all execution steps with inputs/outputs
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Risk control mapper test failed: {e}", exc_info=True)
            return {
                "test_name": "risk_control_mapper_agent",
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and generate summary."""
        logger.info("=" * 80)
        logger.info("COMPLIANCE PIPELINE AGENT TEST SUITE")
        logger.info("=" * 80)
        logger.info("")
        
        self.setup()
        
        # Run individual agent tests
        tests = [
            ("Profile Resolver", self.test_profile_resolver_agent),
            ("Metrics Recommender", self.test_metrics_recommender_agent),
            ("Calculation Planner", self.test_calculation_planner_agent),
            ("Dashboard Generation Flow", self.test_dashboard_generation_flow),
            ("Planner", self.test_planner_agent),
            ("Detection Engineer", self.test_detection_engineer_agent),
            ("Playbook Writer", self.test_playbook_writer_agent),
            ("Test Generator", self.test_test_generator_agent),
            ("Dashboard Generator", self.test_dashboard_generator_agent),
            ("Risk Control Mapper", self.test_risk_control_mapper_agent),
            ("Full Pipeline", self.test_hipaa_breach_detection_pipeline),
        ]
        
        results = {}
        for test_name, test_func in tests:
            try:
                result = test_func()
                results[test_name] = result
                self.results.append(result)
            except Exception as e:
                logger.error(f"Test '{test_name}' failed with exception: {e}", exc_info=True)
                results[test_name] = {
                    "test_name": test_name.lower().replace(" ", "_"),
                    "success": False,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
            logger.info("")
        
        # Generate summary
        self.print_summary(results)
        
        return {
            "summary": self.generate_summary(results),
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate test summary."""
        total = len(results)
        passed = sum(1 for r in results.values() if r.get("success", False))
        failed = total - passed
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / total * 100) if total > 0 else 0
        }
    
    def print_summary(self, results: Dict[str, Any]):
        """Print test summary."""
        summary = self.generate_summary(results)
        
        logger.info("=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total tests: {summary['total']}")
        logger.info(f"✅ Passed: {summary['passed']}")
        logger.info(f"❌ Failed: {summary['failed']}")
        logger.info(f"Pass rate: {summary['pass_rate']:.1f}%")
        logger.info("")
        
        logger.info("Test Results:")
        for test_name, result in results.items():
            status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
            logger.info(f"  {status} {test_name}")
            if not result.get("success", False) and "error" in result:
                logger.info(f"    Error: {result['error']}")
        logger.info("")


def sanitize_results_for_json(results: Dict[str, Any], max_response_length: int = 10000, include_full_artifacts: bool = False) -> Dict[str, Any]:
    """
    Sanitize results to reduce JSON file size by truncating large content.
    
    Args:
        results: Test results dictionary
        max_response_length: Maximum length for LLM responses (default 10KB)
        include_full_artifacts: Whether to include full artifact content (default False)
    """
    sanitized = {}
    
    for key, value in results.items():
        if key == "results" and isinstance(value, dict):
            # Handle nested results
            sanitized[key] = sanitize_results_for_json(value, max_response_length, include_full_artifacts)
        elif key == "llm_response" and isinstance(value, str):
            # Truncate LLM responses
            if len(value) > max_response_length:
                sanitized[key] = {
                    "truncated": True,
                    "original_length": len(value),
                    "preview": value[:max_response_length],
                    "suffix": value[-500:] if len(value) > 500 else value
                }
            else:
                sanitized[key] = value
        elif key == "llm_prompt" and isinstance(value, dict):
            # Truncate prompt content
            sanitized_prompt = {}
            for prompt_key, prompt_value in value.items():
                if isinstance(prompt_value, str) and len(prompt_value) > max_response_length:
                    sanitized_prompt[prompt_key] = {
                        "truncated": True,
                        "original_length": len(prompt_value),
                        "preview": prompt_value[:max_response_length]
                    }
                else:
                    sanitized_prompt[prompt_key] = prompt_value
            sanitized[key] = sanitized_prompt
        elif key == "execution_steps" and isinstance(value, list):
            # Limit execution step details
            sanitized_steps = []
            for step in value:
                sanitized_step = {
                    "step_name": step.get("step_name"),
                    "agent_name": step.get("agent_name"),
                    "timestamp": step.get("timestamp"),
                    "status": step.get("status"),
                    "error": step.get("error")
                }
                # Include inputs/outputs but truncate large content
                if "inputs" in step:
                    sanitized_inputs = {}
                    for input_key, input_value in step["inputs"].items():
                        if isinstance(input_value, str) and len(input_value) > 1000:
                            sanitized_inputs[input_key] = f"[TRUNCATED: {len(input_value)} chars] {input_value[:500]}"
                        else:
                            sanitized_inputs[input_key] = input_value
                    sanitized_step["inputs"] = sanitized_inputs
                
                if "outputs" in step:
                    sanitized_outputs = {}
                    for output_key, output_value in step["outputs"].items():
                        if isinstance(output_value, str) and len(output_value) > 1000:
                            sanitized_outputs[output_key] = f"[TRUNCATED: {len(output_value)} chars] {output_value[:500]}"
                        else:
                            sanitized_outputs[output_key] = output_value
                    sanitized_step["outputs"] = sanitized_outputs
                
                sanitized_steps.append(sanitized_step)
            sanitized[key] = sanitized_steps
        elif key in ["test_scripts", "siem_rules", "playbooks", "dashboards", "vulnerability_mappings"] and isinstance(value, list):
            # Optionally include full artifacts or just metadata
            if include_full_artifacts:
                sanitized[key] = value
            else:
                # Include only metadata, not full content
                sanitized[key] = [
                    {
                        k: v for k, v in item.items() 
                        if k not in ["python_code", "spl_code", "markdown_content", "dashboard_spec", "specification", "code"]
                    }
                    if isinstance(item, dict) else item
                    for item in value
                ]
        else:
            sanitized[key] = value
    
    return sanitized


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test compliance pipeline agents",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--test',
        choices=['all', 'profile_resolver', 'metrics_recommender', 'calculation_planner', 'dashboard_flow', 'planner', 'detection_engineer', 'playbook_writer', 'test_generator', 'dashboard_generator', 'risk_control_mapper', 'pipeline'],
        default='all',
        help='Which test to run'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--include-full-artifacts',
        action='store_true',
        help='Include full artifact content in JSON (default: metadata only)'
    )
    
    parser.add_argument(
        '--max-response-length',
        type=int,
        default=10000,
        help='Maximum length for LLM responses in JSON (default: 10000 chars)'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    tester = CompliancePipelineTester()
    results = None
    
    if args.test == 'all':
        results = tester.run_all_tests()
    elif args.test == 'profile_resolver':
        tester.setup()
        result = tester.test_profile_resolver_agent()
        tester.print_summary({"Profile Resolver": result})
        results = {"results": result}
    elif args.test == 'metrics_recommender':
        tester.setup()
        result = tester.test_metrics_recommender_agent()
        tester.print_summary({"Metrics Recommender": result})
        results = {"results": result}
    elif args.test == 'calculation_planner':
        tester.setup()
        result = tester.test_calculation_planner_agent()
        tester.print_summary({"Calculation Planner": result})
        results = {"results": result}
    elif args.test == 'dashboard_flow':
        tester.setup()
        result = tester.test_dashboard_generation_flow()
        tester.print_summary({"Dashboard Generation Flow": result})
        results = {"results": result}
    elif args.test == 'planner':
        tester.setup()
        result = tester.test_planner_agent()
        tester.print_summary({"Planner": result})
        results = {"results": result}
    elif args.test == 'detection_engineer':
        tester.setup()
        result = tester.test_detection_engineer_agent()
        tester.print_summary({"Detection Engineer": result})
        results = {"results": result}
    elif args.test == 'playbook_writer':
        tester.setup()
        result = tester.test_playbook_writer_agent()
        tester.print_summary({"Playbook Writer": result})
        results = {"results": result}
    elif args.test == 'test_generator':
        tester.setup()
        result = tester.test_test_generator_agent()
        tester.print_summary({"Test Generator": result})
        results = {"results": result}
    elif args.test == 'dashboard_generator':
        tester.setup()
        result = tester.test_dashboard_generator_agent()
        tester.print_summary({"Dashboard Generator": result})
        results = {"results": result}
    elif args.test == 'risk_control_mapper':
        tester.setup()
        result = tester.test_risk_control_mapper_agent()
        tester.print_summary({"Risk Control Mapper": result})
        results = {"results": result}
    elif args.test == 'pipeline':
        tester.setup()
        result = tester.test_hipaa_breach_detection_pipeline()
        validation = result.get("validation", {})
        logger.info(f"Pipeline test: {'✅ PASS' if validation.get('overall_success') else '❌ FAIL'}")
        results = {"results": result}
    
    # Save results to file
    if results:
        # Sanitize results to reduce file size
        sanitized_results = sanitize_results_for_json(
            results,
            max_response_length=args.max_response_length,
            include_full_artifacts=args.include_full_artifacts
        )
        
        output_file = base_dir / "tests" / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump(sanitized_results, f, indent=2, default=str)
        
        # Calculate file size
        file_size = output_file.stat().st_size
        file_size_mb = file_size / (1024 * 1024)
        
        logger.info(f"Results saved to: {output_file}")
        logger.info(f"File size: {file_size_mb:.2f} MB ({file_size:,} bytes)")
        
        if file_size_mb > 100:
            logger.warning(f"Large file size detected ({file_size_mb:.2f} MB). Consider using --max-response-length or --no-include-full-artifacts to reduce size.")


if __name__ == '__main__':
    main()

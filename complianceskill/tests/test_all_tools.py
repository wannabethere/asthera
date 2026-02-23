#!/usr/bin/env python3
"""
Comprehensive test script for all security intelligence tools.

This script tests all available tools in the TOOL_REGISTRY, handling:
- Missing API keys (graceful failures)
- Database tools (uses populated database)
- API tools (requires API keys)
- Error handling and reporting

Usage:
    # Test all tools
    python -m tests.test_all_tools

    # Test specific category
    python -m tests.test_all_tools --category database

    # Test specific tool
    python -m tests.test_all_tools --tool cve_to_attack_mapper

    # Verbose output
    python -m tests.test_all_tools --verbose
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from dotenv import load_dotenv

# Load .env file before importing app modules
# Try multiple locations for .env file
env_file = None
base_dir = Path(__file__).resolve().parent.parent
for possible_env in [base_dir / ".env", base_dir.parent / ".env", Path.cwd() / ".env"]:
    if possible_env.exists():
        env_file = possible_env
        break

if env_file:
    load_dotenv(env_file, override=True)
    print(f"✓ Loaded .env file from: {env_file}")
else:
    print("⚠️  No .env file found. Environment variables may not be loaded.")

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.tools import TOOL_REGISTRY, get_all_tools
from app.storage.sqlalchemy_session import get_session
from sqlalchemy import text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


class ToolTester:
    """Test all security intelligence tools."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: Dict[str, Dict[str, Any]] = {}
        self.summary = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }
    
    def check_api_key(self, key_name: str) -> bool:
        """Check if an API key is set."""
        value = os.getenv(key_name)
        return value is not None and value.strip() != ""
    
    def get_env_var_status(self, key_name: str) -> Tuple[bool, str]:
        """Get environment variable status with masked value."""
        value = os.getenv(key_name)
        if value:
            # Mask the value for security (show first 4 and last 4 chars)
            if len(value) > 8:
                masked = f"{value[:4]}...{value[-4:]}"
            else:
                masked = "***" if len(value) > 0 else ""
            return True, masked
        return False, "Not set"
    
    def get_test_data_from_db(self, table: str, column: str, limit: int = 1) -> List[str]:
        """Get test data from database."""
        try:
            with get_session() as session:
                stmt = text(f"SELECT DISTINCT {column} FROM {table} LIMIT :limit")
                result = session.execute(stmt, {"limit": limit})
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            if self.verbose:
                logger.debug(f"Could not fetch test data from {table}.{column}: {e}")
            return []
    
    def test_tool(
        self, 
        tool_name: str, 
        tool_creator, 
        test_input: Dict[str, Any],
        requires_api_key: Optional[str] = None,
        skip_if_no_data: bool = False
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Test a single tool.
        
        Returns:
            (success, message, result_data)
        """
        self.summary["total"] += 1
        
        # Check API key requirement
        if requires_api_key and not self.check_api_key(requires_api_key):
            self.summary["skipped"] += 1
            return False, f"SKIPPED: {requires_api_key} not set", None
        
        # Check if we need database data
        if skip_if_no_data:
            # Try to get test data from database
            test_data = self.get_test_data_from_db("cve_attack_mapping", "cve_id", 1)
            if not test_data:
                self.summary["skipped"] += 1
                return False, "SKIPPED: No data in database", None
            # Update test input with actual data
            if "cve_id" in test_input:
                test_input["cve_id"] = test_data[0]
        
        try:
            # Create tool instance
            tool = tool_creator()
            
            # Invoke tool
            if self.verbose:
                logger.info(f"Testing {tool_name} with input: {test_input}")
            
            result = tool.invoke(test_input)
            
            # Check if result is valid
            if isinstance(result, dict):
                success = result.get("success", False)
                error = result.get("error_message")
                
                if success:
                    self.summary["passed"] += 1
                    return True, "PASSED", result
                else:
                    self.summary["failed"] += 1
                    error_msg = error or "Tool returned success=False"
                    return False, f"FAILED: {error_msg}", result
            else:
                # Some tools might return raw data
                self.summary["passed"] += 1
                return True, "PASSED", {"result": result}
                
        except Exception as e:
            self.summary["failed"] += 1
            error_msg = str(e)
            self.summary["errors"].append(f"{tool_name}: {error_msg}")
            return False, f"ERROR: {error_msg}", None
    
    def run_all_tests(self, category: Optional[str] = None, tool_name: Optional[str] = None):
        """Run all tool tests."""
        logger.info("=" * 80)
        logger.info("Security Intelligence Tools Test Suite")
        logger.info("=" * 80)
        logger.info("")
        
        # Define test configurations for each tool
        test_configs = {
            # === CVE & Vulnerability Intelligence ===
            "cve_intelligence": {
                "test_input": {"cve_id": "CVE-2021-44228"},  # Log4j
                "requires_api_key": None,  # Works without key, but rate limited
                "category": "api"
            },
            "cve_details": {
                "test_input": {"cve_id": "CVE-2021-44228"},
                "requires_api_key": None,
                "category": "api",
                "skip": True  # Alias, skip duplicate
            },
            "epss_lookup": {
                "test_input": {"cve_id": "CVE-2021-44228"},
                "requires_api_key": None,
                "category": "api"
            },
            "cisa_kev_check": {
                "test_input": {"cve_id": "CVE-2021-44228"},
                "requires_api_key": None,
                "category": "api"
            },
            "github_advisory_search": {
                "test_input": {"query": "log4j", "limit": 5},
                "requires_api_key": None,  # Optional
                "category": "api"
            },
            "cpe_lookup": {
                "test_input": {"cpe_uri": "cpe:2.3:a:apache:log4j:2.14.1"},
                "requires_api_key": None,  # Optional
                "category": "api"
            },
            
            # === Database Tools ===
            "cve_to_attack_mapper": {
                "test_input": {"cve_id": "CVE-2024-1234"},  # Will be replaced with actual data
                "requires_api_key": None,
                "category": "database",
                "skip_if_no_data": True
            },
            "attack_to_control_mapper": {
                "test_input": {"technique_id": "T1003.001"},
                "requires_api_key": None,
                "category": "database",
                "skip_if_no_data": True
            },
            "cpe_resolver": {
                "test_input": {"vendor": "apache", "product": "log4j"},
                "requires_api_key": None,
                "category": "database",
                "skip_if_no_data": True
            },
            
            # === Exploit Intelligence ===
            "exploit_db_search": {
                "test_input": {"query": "log4j", "limit": 5},
                "requires_api_key": None,
                "category": "exploit",
                "skip_if_no_data": True
            },
            "metasploit_module_search": {
                "test_input": {"cve_id": "CVE-2021-44228", "limit": 5},
                "requires_api_key": None,
                "category": "exploit",
                "skip_if_no_data": True
            },
            "nuclei_template_search": {
                "test_input": {"cve_id": "CVE-2021-44228", "limit": 5},
                "requires_api_key": None,
                "category": "exploit",
                "skip_if_no_data": True
            },
            
            # === ATT&CK Framework ===
            "attack_technique_lookup": {
                "test_input": {"technique_id": "T1003.001"},
                "requires_api_key": None,
                "category": "attack"
            },
            
            # === Compliance & Frameworks ===
            "framework_control_search": {
                "test_input": {"query": "authentication"},
                "requires_api_key": None,
                "category": "compliance"
            },
            "cis_benchmark_lookup": {
                "test_input": {"benchmark_id": "CIS_Ubuntu_Linux_22.04", "rule_number": "1.1.1.1"},
                "requires_api_key": None,
                "category": "compliance",
                "skip_if_no_data": True
            },
            "gap_analysis": {
                "test_input": {
                    "framework_id": "hipaa",
                    "control_ids": ["AC-2", "AC-3"]
                },
                "requires_api_key": None,
                "category": "compliance"
            },
            
            # === Threat Intelligence ===
            "otx_pulse_search": {
                "test_input": {"query": "log4j", "limit": 5},
                "requires_api_key": "OTX_API_KEY",
                "category": "threat_intel"
            },
            "virustotal_lookup": {
                "test_input": {"resource": "example.com"},
                "requires_api_key": "VIRUSTOTAL_API_KEY",
                "category": "threat_intel"
            },
            
            # === Analysis & Synthesis ===
            "attack_path_builder": {
                "test_input": {
                    "start_technique": "T1003.001",
                    "target_technique": "T1078",
                    "max_depth": 3
                },
                "requires_api_key": None,
                "category": "analysis"
            },
            "risk_calculator": {
                "test_input": {
                    "cve_ids": ["CVE-2021-44228"],
                    "asset_criticality": "high"
                },
                "requires_api_key": None,
                "category": "analysis"
            },
            "remediation_prioritizer": {
                "test_input": {
                    "cve_ids": ["CVE-2021-44228"],
                    "framework_id": "hipaa"
                },
                "requires_api_key": None,
                "category": "analysis"
            },
            
            # === Web Search ===
            "tavily_search": {
                "test_input": {"query": "CVE-2021-44228 log4j vulnerability", "max_results": 5},
                "requires_api_key": "TAVILY_API_KEY",
                "category": "search"
            },
        }
        
        # Filter tools if category or tool_name specified
        tools_to_test = {}
        if tool_name:
            if tool_name in TOOL_REGISTRY:
                tools_to_test[tool_name] = TOOL_REGISTRY[tool_name]
            else:
                logger.error(f"Tool '{tool_name}' not found in TOOL_REGISTRY")
                return
        elif category:
            category_map = {
                "api": ["cve_intelligence", "epss_lookup", "cisa_kev_check", "github_advisory_search", "cpe_lookup"],
                "database": ["cve_to_attack_mapper", "attack_to_control_mapper", "cpe_resolver"],
                "exploit": ["exploit_db_search", "metasploit_module_search", "nuclei_template_search"],
                "compliance": ["framework_control_search", "cis_benchmark_lookup", "gap_analysis"],
                "threat_intel": ["otx_pulse_search", "virustotal_lookup"],
                "attack": ["attack_technique_lookup", "cve_to_attack_mapper", "attack_to_control_mapper"],
                "analysis": ["attack_path_builder", "risk_calculator", "remediation_prioritizer"],
                "search": ["tavily_search"],
            }
            tool_names = category_map.get(category, [])
            tools_to_test = {name: TOOL_REGISTRY[name] for name in tool_names if name in TOOL_REGISTRY}
        else:
            tools_to_test = TOOL_REGISTRY
        
        # Run tests
        logger.info(f"Testing {len(tools_to_test)} tools...")
        logger.info("")
        
        for tool_name, tool_creator in tools_to_test.items():
            config = test_configs.get(tool_name, {})
            
            # Skip if marked to skip
            if config.get("skip", False):
                continue
            
            # Skip if category filter doesn't match
            if category and config.get("category") != category:
                continue
            
            test_input = config.get("test_input", {})
            requires_api_key = config.get("requires_api_key")
            skip_if_no_data = config.get("skip_if_no_data", False)
            
            logger.info(f"Testing: {tool_name}")
            
            success, message, result = self.test_tool(
                tool_name,
                tool_creator,
                test_input,
                requires_api_key=requires_api_key,
                skip_if_no_data=skip_if_no_data
            )
            
            self.results[tool_name] = {
                "success": success,
                "message": message,
                "result": result,
                "category": config.get("category", "unknown")
            }
            
            status_icon = "✅" if success else "❌" if "FAILED" in message or "ERROR" in message else "⏭️"
            logger.info(f"  {status_icon} {message}")
            
            if self.verbose and result:
                logger.info(f"  Result: {json.dumps(result, indent=2, default=str)[:500]}")
            
            logger.info("")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary."""
        logger.info("=" * 80)
        logger.info("Test Summary")
        logger.info("=" * 80)
        logger.info(f"Total tools tested: {self.summary['total']}")
        logger.info(f"✅ Passed: {self.summary['passed']}")
        logger.info(f"❌ Failed: {self.summary['failed']}")
        logger.info(f"⏭️  Skipped: {self.summary['skipped']}")
        logger.info("")
        
        # Group by category
        by_category = defaultdict(list)
        for tool_name, result in self.results.items():
            category = result.get("category", "unknown")
            by_category[category].append((tool_name, result))
        
        logger.info("Results by Category:")
        logger.info("")
        for category, tools in sorted(by_category.items()):
            logger.info(f"  {category.upper()}:")
            for tool_name, result in tools:
                status_icon = "✅" if result["success"] else "❌" if "FAILED" in result["message"] or "ERROR" in result["message"] else "⏭️"
                logger.info(f"    {status_icon} {tool_name}: {result['message']}")
            logger.info("")
        
        # Show errors if any
        if self.summary["errors"]:
            logger.info("Errors:")
            for error in self.summary["errors"]:
                logger.error(f"  - {error}")
            logger.info("")
        
        # API key status
        logger.info("API Key Status:")
        api_keys = {
            "NVD_API_KEY": "Optional (increases rate limit)",
            "TAVILY_API_KEY": "Required for tavily_search",
            "OTX_API_KEY": "Required for otx_pulse_search",
            "VIRUSTOTAL_API_KEY": "Required for virustotal_lookup",
            "GITHUB_TOKEN": "Optional (increases rate limit)",
        }
        for key, description in api_keys.items():
            is_set, masked_value = self.get_env_var_status(key)
            status = "✅ Set" if is_set else "❌ Not set"
            if is_set:
                logger.info(f"  {status} {key}: {description} (value: {masked_value})")
            else:
                logger.info(f"  {status} {key}: {description}")
        
        # Show any custom environment variables from .env
        logger.info("")
        logger.info("Other Environment Variables (from .env):")
        # Check for common environment variable prefixes used in the project
        env_prefixes = ["CHROMA_", "POSTGRES_", "SEC_INTEL_", "QDRANT_", "REDIS_"]
        found_custom = False
        
        # Get all environment variables
        all_env_vars = dict(os.environ)
        
        # Filter and display relevant ones
        relevant_vars = {}
        for key, value in all_env_vars.items():
            # Skip sensitive keys that are already shown above
            if key in api_keys:
                continue
            # Include vars with relevant prefixes
            if any(key.startswith(prefix) for prefix in env_prefixes):
                relevant_vars[key] = value
        
        # Also check for any custom vars the user might have added
        # (You can add specific var names here if you know them)
        custom_var_names = [
            "CHROMA_HOST",
            "CHROMA_PORT",
            "CHROMA_USE_LOCAL",
            "CHROMA_PERSIST_DIRECTORY",
        ]
        for var_name in custom_var_names:
            if var_name in all_env_vars and var_name not in relevant_vars:
                relevant_vars[var_name] = all_env_vars[var_name]
        
        if relevant_vars:
            for var_name, value in sorted(relevant_vars.items()):
                found_custom = True
                # Mask sensitive values (passwords, keys, etc.)
                if "PASSWORD" in var_name or "KEY" in var_name or "TOKEN" in var_name:
                    if len(value) > 8:
                        masked = f"{value[:4]}...{value[-4:]}"
                    else:
                        masked = "***"
                    logger.info(f"  ✅ {var_name}: {masked}")
                else:
                    logger.info(f"  ✅ {var_name}: {value}")
        
        if not found_custom:
            logger.info("  (No additional environment variables found)")
        logger.info("")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test all security intelligence tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test all tools
  python -m tests.test_all_tools

  # Test specific category
  python -m tests.test_all_tools --category database

  # Test specific tool
  python -m tests.test_all_tools --tool cve_to_attack_mapper

  # Verbose output
  python -m tests.test_all_tools --verbose
        """
    )
    
    parser.add_argument(
        '--category',
        choices=['api', 'database', 'exploit', 'compliance', 'threat_intel', 'attack', 'analysis', 'search'],
        help='Test only tools in this category'
    )
    
    parser.add_argument(
        '--tool',
        help='Test only this specific tool'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run tests
    tester = ToolTester(verbose=args.verbose)
    tester.run_all_tests(category=args.category, tool_name=args.tool)


if __name__ == '__main__':
    main()

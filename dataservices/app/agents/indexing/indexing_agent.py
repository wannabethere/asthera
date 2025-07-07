#!/usr/bin/env python3
"""
LLM-Powered Project Generation Agent

This agent uses LLMs to generate comprehensive project documentation and artifacts.
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI


@dataclass
class MDLGenerationResult:
    """Result of MDL generation process"""
    mdl_json: Dict[str, Any]
    metrics: List[Dict[str, Any]]
    views: List[Dict[str, Any]]
    models: List[Dict[str, Any]]
    properties: Dict[str, Any]


@dataclass
class SQLPairsResult:
    """Result of SQL pairs generation process"""
    sql_pairs_json: List[Dict[str, Any]]
    categories_covered: List[str]

@dataclass
class CSVAnalysisResult:
    """Generic result of CSV analysis"""
    row_count: int
    column_count: int
    schema: Dict[str, Any]
    sample_rows: List[Dict[str, Any]]
    statistics: Dict[str, Any]
    time_series_column: Optional[str]
    groupby_columns: List[str]
    aggregation_functions: Dict[str, List[str]]
    correlations: Dict[str, Dict[str, float]]
    missing_data_info: Dict[str, Any]
    suggested_functions: List[Dict[str, Any]]
    context: str
    data_patterns: Dict[str, Any]
    business_context: str
    inferred_domain: str
    key_metrics: List[str]

@dataclass
class ProjectArtifacts:
    """All project artifacts generated"""
    project_id: str
    project_folder: str
    mdl_json: Dict[str, Any]
    instructions_json: Dict[str, Any]
    sql_pairs_json: List[Dict[str, Any]]
    table_description_json: Dict[str, Any]
    project_summary: Dict[str, Any]


class InstructionsGenerator:
    """LLM agent for generating comprehensive project instructions"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
    
    def generate_instructions(self, 
                            project_name: str,
                            analysis_result: CSVAnalysisResult,
                            mdl_result: MDLGenerationResult,
                            sql_result: SQLPairsResult,
                            business_purpose: str,
                            questions: List[str]) -> Dict[str, Any]:
        """Generate comprehensive project instructions using LLM"""
        
        instructions_prompt = ChatPromptTemplate.from_template("""
        You are a senior data analytics consultant creating comprehensive project guidance
        for a data analytics implementation.
        
        Project Details:
        - Name: {project_name}
        - Purpose: {business_purpose}
        - Domain: {domain}
        - Data Size: {row_count} rows, {column_count} columns
        - Quality Score: {quality_score}
        
        Generated Artifacts:
        - MDL Metrics: {metrics_count}
        - SQL Pairs: {sql_pairs_count}
        - Categories: {categories}
        
        Business Questions:
        {questions}
        
        Key Insights from Analysis:
        {key_insights}
        
        Create comprehensive implementation guidance as JSON:
        {{
            "executive_summary": {{
                "project_overview": "concise business overview",
                "key_value_propositions": ["value1", "value2", "value3"],
                "success_criteria": ["criteria1", "criteria2"],
                "implementation_timeline": "estimated timeline",
                "resource_requirements": ["requirement1", "requirement2"]
            }},
            "business_context": {{
                "domain_analysis": "detailed domain analysis",
                "stakeholder_map": {{
                    "primary_users": ["user_type1", "user_type2"],
                    "secondary_users": ["user_type3"],
                    "decision_makers": ["decision_maker_types"]
                }},
                "use_case_scenarios": [
                    {{
                        "scenario_name": "scenario1",
                        "description": "detailed scenario description",
                        "business_value": "value delivered",
                        "frequency": "how_often_used"
                    }}
                ],
                "success_metrics": [
                    {{
                        "metric_name": "success_metric",
                        "measurement": "how_to_measure",
                        "target": "target_value",
                        "timeline": "when_to_achieve"
                    }}
                ]
            }},
            "technical_implementation": {{
                "data_architecture": {{
                    "source_systems": "data_source_description",
                    "data_flow": "how_data_flows",
                    "storage_strategy": "storage_approach",
                    "refresh_patterns": "how_often_to_refresh"
                }},
                "analytics_framework": {{
                    "core_metrics": "overview_of_key_metrics",
                    "dimensional_model": "star_schema_approach",
                    "calculation_logic": "key_calculations_explained",
                    "aggregation_strategy": "pre_agg_vs_real_time"
                }},
                "performance_optimization": {{
                    "indexing_strategy": ["index_recommendations"],
                    "query_optimization": ["optimization_tips"],
                    "caching_approach": "caching_recommendations",
                    "scalability_plan": "how_to_scale"
                }}
            }},
            "user_adoption": {{
                "training_plan": {{
                    "business_users": ["training_for_business_users"],
                    "technical_users": ["training_for_technical_users"],
                    "administrators": ["training_for_admins"]
                }},
                "change_management": {{
                    "communication_strategy": "how_to_communicate_changes",
                    "rollout_approach": "phased_vs_big_bang",
                    "support_model": "ongoing_support_structure"
                }},
                "governance": {{
                    "data_quality_monitoring": "how_to_monitor_quality",
                    "access_controls": "who_can_access_what",
                    "audit_requirements": "audit_trail_needs"
                }}
            }},
            "operational_guidelines": {{
                "daily_operations": ["daily_tasks"],
                "weekly_reviews": ["weekly_review_items"],
                "monthly_assessments": ["monthly_assessment_areas"],
                "troubleshooting": [
                    {{
                        "issue": "common_issue",
                        "symptoms": "how_to_identify",
                        "resolution": "how_to_fix"
                    }}
                ]
            }},
            "future_roadmap": {{
                "phase_1": "immediate_implementation",
                "phase_2": "6_month_enhancements",
                "phase_3": "1_year_vision",
                "expansion_opportunities": ["future_expansion_areas"]
            }}
        }}
        
        Focus on practical, actionable guidance that ensures project success.
        """)
        
        # Prepare key insights
        key_insights = []
        if analysis_result.data_patterns:
            domain_info = analysis_result.data_patterns.get('domain_analysis', {})
            key_insights.append(f"Domain: {domain_info.get('primary_domain', 'Unknown')} with {domain_info.get('confidence', 0):.2f} confidence")
            
            entities = analysis_result.data_patterns.get('business_entities', {})
            if entities.get('primary_entities'):
                key_insights.append(f"Key entities: {len(entities['primary_entities'])} business entities identified")
        
        inputs = {
            "project_name": project_name,
            "business_purpose": business_purpose,
            "domain": analysis_result.inferred_domain,
            "row_count": analysis_result.row_count,
            "column_count": analysis_result.column_count,
            "quality_score": analysis_result.data_quality_assessment.get('overall_quality_score', 0.8),
            "metrics_count": mdl_result.metrics_count,
            "sql_pairs_count": sql_result.total_pairs,
            "categories": ", ".join(sql_result.categories_covered),
            "questions": "\n".join([f"- {q}" for q in questions[:10]]),
            "key_insights": " | ".join(key_insights) if key_insights else "Comprehensive data analysis completed"
        }
        
        try:
            chain = instructions_prompt | self.llm | JsonOutputParser()
            return chain.invoke(inputs)
        except Exception as e:
            print(f"Error generating instructions: {e}")
            return self._create_fallback_instructions(project_name, analysis_result, business_purpose)
    
    def _create_fallback_instructions(self, project_name: str, analysis_result: CSVAnalysisResult, business_purpose: str) -> Dict[str, Any]:
        """Create fallback instructions if LLM fails"""
        return {
            "executive_summary": {
                "project_overview": f"{project_name} - {business_purpose}",
                "key_value_propositions": ["Data-driven insights", "Improved decision making", "Operational efficiency"],
                "success_criteria": ["User adoption > 80%", "Query performance < 5 seconds", "Data quality > 95%"]
            },
            "business_context": {
                "domain_analysis": f"Analysis focused on {analysis_result.inferred_domain} domain",
                "use_case_scenarios": [{"scenario_name": "Primary Analysis", "description": business_purpose}]
            }
        }


class TableDocumentationGenerator:
    """LLM agent for generating comprehensive table documentation"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
    
    def generate_documentation(self, 
                             project_name: str,
                             analysis_result: CSVAnalysisResult,
                             mdl_result: MDLGenerationResult,
                             business_purpose: str) -> Dict[str, Any]:
        """Generate comprehensive table documentation using LLM"""
        
        documentation_prompt = ChatPromptTemplate.from_template("""
        You are a data documentation specialist creating comprehensive data catalog entries.
        
        Project: {project_name}
        Purpose: {business_purpose}
        Domain: {domain}
        
        Data Analysis Results:
        - Quality Score: {quality_score}
        - Key Metrics: {key_metrics}
        - Business Entities: {entities}
        - Time Series: {has_time_series}
        
        Schema Information:
        {schema_info}
        
        MDL Generation Results:
        {mdl_info}
        
        Create comprehensive data documentation as JSON:
        {{
            "data_asset_profile": {{
                "asset_name": "business_friendly_name",
                "technical_name": "technical_identifier",
                "asset_type": "table/view/dataset",
                "domain": "business_domain",
                "classification": "public/internal/confidential/restricted",
                "business_criticality": "critical/high/medium/low",
                "data_steward": "responsible_role",
                "created_date": "creation_date",
                "last_updated": "last_update_date"
            }},
            "business_metadata": {{
                "business_purpose": "detailed_business_purpose",
                "business_rules": [
                    {{
                        "rule_name": "business_rule_name",
                        "description": "rule_description",
                        "enforcement": "system/manual/advisory"
                    }}
                ],
                "key_business_concepts": [
                    {{
                        "concept": "business_concept",
                        "definition": "clear_definition",
                        "examples": ["example1", "example2"]
                    }}
                ],
                "business_glossary": {{
                    "term1": "definition1",
                    "term2": "definition2"
                }}
            }},
            "technical_metadata": {{
                "data_lineage": {{
                    "source_systems": ["system1", "system2"],
                    "transformation_summary": "key_transformations_applied",
                    "data_flow": "source -> processing -> destination",
                    "dependencies": ["upstream_dependencies"]
                }},
                "data_quality": {{
                    "quality_score": "overall_quality_rating",
                    "quality_dimensions": {{"completeness": 0.0-1.0, "accuracy": 0.0-1.0}},
                    "known_issues": ["issue1", "issue2"],
                    "quality_controls": ["control1", "control2"]
                }},
                "performance_characteristics": {{
                    "data_volume": "volume_description",
                    "growth_rate": "growth_pattern",
                    "query_patterns": "typical_query_types",
                    "performance_expectations": "response_time_expectations"
                }}
            }},
            "schema_documentation": [
                {{
                    "column_name": "column_name",
                    "display_name": "user_friendly_name",
                    "data_type": "technical_data_type",
                    "business_type": "business_classification",
                    "description": "comprehensive_business_description",
                    "business_rules": ["applicable_rules"],
                    "validation_rules": ["validation_checks"],
                    "example_values": ["sample_values"],
                    "related_columns": ["related_columns"],
                    "calculation_logic": "if_calculated_field",
                    "privacy_classification": "public/pii/sensitive",
                    "usage_guidelines": "how_to_use_this_column"
                }}
            ],
            "usage_guidelines": {{
                "primary_use_cases": [
                    {{
                        "use_case": "use_case_name",
                        "description": "detailed_description", 
                        "example_queries": ["query_examples"],
                        "best_practices": ["practice1", "practice2"]
                    }}
                ],
                "query_patterns": [
                    {{
                        "pattern_name": "common_pattern",
                        "sql_template": "query_template",
                        "when_to_use": "usage_scenario",
                        "performance_notes": "performance_considerations"
                    }}
                ],
                "integration_guidelines": {{
                    "api_access": "how_to_access_via_api",
                    "export_formats": ["supported_formats"],
                    "refresh_schedule": "data_refresh_timing",
                    "access_patterns": "recommended_access_patterns"
                }}
            }},
            "compliance_and_governance": {{
                "data_retention": "retention_policy",
                "access_controls": "who_can_access",
                "audit_requirements": "audit_trail_needs",
                "regulatory_compliance": ["applicable_regulations"],
                "privacy_considerations": ["privacy_requirements"]
            }}
        }}
        
        Make this a comprehensive, production-ready data catalog entry.
        """)
        
        # Prepare schema information
        schema_summary = []
        for col_name, col_info in list(analysis_result.schema.items())[:15]:
            schema_summary.append({
                "name": col_name,
                "type": col_info['type'],
                "unique_count": col_info['unique_count'],
                "nullable": col_info['nullable'],
                "categorical": col_info.get('is_categorical', False)
            })
        
        inputs = {
            "project_name": project_name,
            "business_purpose": business_purpose,
            "domain": analysis_result.inferred_domain,
            "quality_score": analysis_result.data_quality_assessment.get('overall_quality_score', 0.8),
            "key_metrics": ", ".join(analysis_result.key_metrics[:5]),
            "entities": ", ".join(analysis_result.business_entities[:5]),
            "has_time_series": "Yes" if analysis_result.time_series_column else "No",
            "schema_info": json.dumps(schema_summary, indent=2),
            "mdl_info": json.dumps({
                "table_name": mdl_result.table_name,
                "metrics_count": mdl_result.metrics_count,
                "views_count": mdl_result.views_count
            }, indent=2)
        }
        
        try:
            chain = documentation_prompt | self.llm | JsonOutputParser()
            return chain.invoke(inputs)
        except Exception as e:
            print(f"Error generating documentation: {e}")
            return self._create_fallback_documentation(project_name, analysis_result, business_purpose)
    
    def _create_fallback_documentation(self, project_name: str, analysis_result: CSVAnalysisResult, business_purpose: str) -> Dict[str, Any]:
        """Create fallback documentation if LLM fails"""
        return {
            "data_asset_profile": {
                "asset_name": project_name,
                "technical_name": project_name.lower().replace(' ', '_'),
                "domain": analysis_result.inferred_domain,
                "business_criticality": "medium"
            },
            "business_metadata": {
                "business_purpose": business_purpose,
                "business_rules": []
            },
            "schema_documentation": [
                {
                    "column_name": col_name,
                    "description": f"Data field containing {col_name} information",
                    "data_type": col_info['type']
                }
                for col_name, col_info in list(analysis_result.schema.items())[:10]
            ]
        }


class ProjectGenerationAgent:
    """Main LLM-powered project generation agent"""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.instructions_generator = InstructionsGenerator(llm)
        self.documentation_generator = TableDocumentationGenerator(llm)
        
    def generate_project(self, 
                        project_name: str,
                        analysis_result: CSVAnalysisResult,
                        mdl_result: MDLGenerationResult,
                        sql_pairs_result: SQLPairsResult,
                        business_purpose: str,
                        questions: List[str]) -> ProjectArtifacts:
        """
        Generate complete project with all required artifacts using LLM intelligence
        """
        print("📦 Starting LLM-powered project generation...")
        
        # Generate project ID and folder structure
        project_id = self._generate_project_id(project_name)
        project_folder = self._generate_project_folder(project_name, project_id)
        print(f"🆔 Generated project ID: {project_id}")
        
        # Generate instructions using LLM
        print("📋 Generating comprehensive instructions using LLM...")
        instructions_json = self.instructions_generator.generate_instructions(
            project_name, analysis_result, mdl_result, sql_pairs_result, business_purpose, questions
        )
        
        # Generate table description using LLM
        print("📚 Generating comprehensive documentation using LLM...")
        table_description_json = self.documentation_generator.generate_documentation(
            project_name, analysis_result, mdl_result, business_purpose
        )
        
        # Generate project summary
        project_summary = self._generate_project_summary(
            project_name, analysis_result, mdl_result, sql_pairs_result, business_purpose
        )
        
        # Create project artifacts
        artifacts = ProjectArtifacts(
            project_id=project_id,
            project_folder=project_folder,
            mdl_json=mdl_result.mdl_schema,
            instructions_json=instructions_json,
            sql_pairs_json=sql_pairs_result.sql_pairs,
            table_description_json=table_description_json,
            project_summary=project_summary
        )
        
        print("✅ Project artifacts generated successfully")
        return artifacts
    
    def _generate_project_id(self, project_name: str) -> str:
        """Generate unique project ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_name = project_name.lower().replace(' ', '_').replace('-', '_')
        unique_id = str(uuid.uuid4())[:8]
        return f"{clean_name}_{timestamp}_{unique_id}"
    
    def _generate_project_folder(self, project_name: str, project_id: str) -> str:
        """Generate project folder name"""
        clean_name = project_name.lower().replace(' ', '_').replace('-', '_')
        return f"analytics_project_{clean_name}_{project_id}"
    
    def _generate_project_summary(self, 
                                 project_name: str,
                                 analysis_result: CSVAnalysisResult,
                                 mdl_result: MDLGenerationResult,
                                 sql_pairs_result: SQLPairsResult,
                                 business_purpose: str) -> Dict[str, Any]:
        """Generate project summary"""
        return {
            "project_metadata": {
                "name": project_name,
                "purpose": business_purpose,
                "domain": analysis_result.inferred_domain,
                "created_at": datetime.now().isoformat(),
                "generator_version": "LLM-Powered Analytics Workflow v2.0"
            },
            "data_summary": {
                "rows": analysis_result.row_count,
                "columns": analysis_result.column_count,
                "quality_score": analysis_result.data_quality_assessment.get('overall_quality_score', 0.8),
                "key_metrics": analysis_result.key_metrics,
                "business_entities": analysis_result.business_entities,
                "has_time_series": analysis_result.time_series_column is not None
            },
            "generated_artifacts": {
                "mdl_schema": {
                    "metrics_count": mdl_result.metrics_count,
                    "views_count": mdl_result.views_count,
                    "table_name": mdl_result.table_name,
                    "catalog_name": mdl_result.catalog_name
                },
                "sql_pairs": {
                    "total_pairs": sql_pairs_result.total_pairs,
                    "categories_covered": sql_pairs_result.categories_covered,
                    "difficulty_distribution": sql_pairs_result.generation_summary.get('difficulty_distribution', {})
                }
            },
            "recommendations": {
                "next_steps": [
                    "Review generated SQL queries for business accuracy",
                    "Validate MDL schema against data warehouse",
                    "Set up automated data quality monitoring",
                    "Plan user training and adoption program"
                ],
                "optimization_opportunities": [
                    "Consider pre-aggregating frequently queried metrics",
                    "Implement caching for dashboard queries",
                    "Set up incremental data refresh processes"
                ]
            }
        }
    
    def save_artifacts_to_disk(self, artifacts: ProjectArtifacts, output_directory: str = "./output") -> Dict[str, str]:
        """
        Save all project artifacts to disk with enhanced organization
        """
        output_path = Path(output_directory)
        project_path = output_path / artifacts.project_folder
        project_path.mkdir(parents=True, exist_ok=True)
        
        file_paths = {}
        
        # Save MDL JSON
        mdl_path = project_path / "mdl.json"
        with open(mdl_path, 'w', encoding='utf-8') as f:
            json.dump(artifacts.mdl_json, f, indent=2, ensure_ascii=False)
        file_paths["mdl"] = str(mdl_path)
        
        # Save Instructions JSON
        instructions_path = project_path / "instructions.json"
        with open(instructions_path, 'w', encoding='utf-8') as f:
            json.dump(artifacts.instructions_json, f, indent=2, ensure_ascii=False)
        file_paths["instructions"] = str(instructions_path)
        
        # Save SQL Pairs JSON
        sql_pairs_path = project_path / "sql_pairs.json"
        with open(sql_pairs_path, 'w', encoding='utf-8') as f:
            json.dump(artifacts.sql_pairs_json, f, indent=2, ensure_ascii=False)
        file_paths["sql_pairs"] = str(sql_pairs_path)
        
        # Save Table Description JSON
        table_desc_path = project_path / "table_description.json"
        with open(table_desc_path, 'w', encoding='utf-8') as f:
            json.dump(artifacts.table_description_json, f, indent=2, ensure_ascii=False)
        file_paths["table_description"] = str(table_desc_path)
        
        # Save Project Summary
        summary_path = project_path / "project_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(artifacts.project_summary, f, indent=2, ensure_ascii=False)
        file_paths["project_summary"] = str(summary_path)
        
        # Save Project Manifest
        manifest = {
            "project_id": artifacts.project_id,
            "project_folder": artifacts.project_folder,
            "created_at": datetime.now().isoformat(),
            "files": file_paths,
            "generator": "LLM-Powered Analytics Workflow",
            "version": "2.0"
        }
        
        manifest_path = project_path / "project_manifest.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        file_paths["manifest"] = str(manifest_path)
        
        # Create README file
        readme_path = project_path / "README.md"
        self._create_project_readme(readme_path, artifacts)
        file_paths["readme"] = str(readme_path)
        
        return file_paths
    
    def _create_project_readme(self, readme_path: Path, artifacts: ProjectArtifacts) -> None:
        """Create a README file for the project"""
        
        summary = artifacts.project_summary
        project_meta = summary.get('project_metadata', {})
        data_summary = summary.get('data_summary', {})
        artifacts_info = summary.get('generated_artifacts', {})
        
        readme_content = f"""# {project_meta.get('name', 'Analytics Project')}

## Project Overview
**Purpose**: {project_meta.get('purpose', 'Data analysis project')}
**Domain**: {project_meta.get('domain', 'Generic')}
**Created**: {project_meta.get('created_at', 'Unknown')}

## Data Summary
- **Records**: {data_summary.get('rows', 0):,} rows
- **Fields**: {data_summary.get('columns', 0)} columns  
- **Quality Score**: {data_summary.get('quality_score', 0):.2f}
- **Time Series**: {'Yes' if data_summary.get('has_time_series') else 'No'}

## Generated Artifacts

### 📊 MDL Schema (`mdl.json`)
- **Metrics**: {artifacts_info.get('mdl_schema', {}).get('metrics_count', 0)}
- **Views**: {artifacts_info.get('mdl_schema', {}).get('views_count', 0)}
- **Table**: `{artifacts_info.get('mdl_schema', {}).get('table_name', 'unknown')}`

### 🔍 SQL Query Pairs (`sql_pairs.json`)
- **Total Queries**: {artifacts_info.get('sql_pairs', {}).get('total_pairs', 0)}
- **Categories**: {', '.join(artifacts_info.get('sql_pairs', {}).get('categories_covered', []))}

### 📋 Implementation Guide (`instructions.json`)
Comprehensive implementation guidance including:
- Executive summary and business context
- Technical implementation details
- User adoption strategies
- Operational guidelines

### 📚 Data Documentation (`table_description.json`)
Complete data catalog entry with:
- Business and technical metadata
- Schema documentation
- Usage guidelines
- Compliance information

## Quick Start
1. Review `project_summary.json` for overview
2. Check `instructions.json` for implementation guidance
3. Explore `sql_pairs.json` for example queries
4. Use `mdl.json` for schema implementation

## Next Steps
{chr(10).join([f"- {step}" for step in summary.get('recommendations', {}).get('next_steps', [])])}

---
*Generated by LLM-Powered Analytics Workflow*
"""
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
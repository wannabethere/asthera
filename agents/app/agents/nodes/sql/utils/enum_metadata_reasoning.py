import asyncio
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
import json
import re
from langchain.prompts import ChatPromptTemplate
from langchain.schema import AIMessage, HumanMessage, SystemMessage

from app.agents.nodes.sql.utils.sql_prompts import SQL_GENERATION_MODEL_KWARGS

logger = logging.getLogger("lexy-ai-service")


class EnumMetadataReasoningAgent:
    """
    Agent for generating reasoning plans using enum metadata tables.
    
    This agent analyzes user queries, knowledge, and schemas to determine:
    1. Which enum metadata tables are needed
    2. How to classify assets (impact_class, propagation_class, etc.)
    3. How to calculate scores using enum metadata
    4. What SQL joins and calculations are needed
    """
    
    def __init__(self, llm, enum_metadata_path: Optional[str] = None, sql_examples_path: Optional[str] = None):
        """
        Initialize Enum Metadata Reasoning Agent
        
        Args:
            llm: Language model instance
            enum_metadata_path: Optional path to enum_metadata.mdl.json file
            sql_examples_path: Optional path to metadata_transformation_examples.sql file
        """
        self.llm = llm
        self._enum_metadata = self._load_enum_metadata(enum_metadata_path)
        self._sql_examples = self._load_sql_examples(sql_examples_path)
    
    def _load_enum_metadata(self, enum_metadata_path: Optional[str] = None) -> Dict[str, Any]:
        """Load enum metadata MDL JSON file"""
        try:
            # Try provided path first
            if enum_metadata_path:
                path = Path(enum_metadata_path)
                if path.exists():
                    with open(path, 'r') as f:
                        enum_metadata = json.load(f)
                        logger.info(f"Loaded enum metadata from {path}")
                        return enum_metadata
            
            # Try multiple possible paths
            possible_paths = [
                Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "cvedata" / "migrations" / "enum_metadata.mdl.json",
                Path(__file__).parent.parent.parent.parent.parent.parent.parent / "flowharmonicai" / "data" / "cvedata" / "migrations" / "enum_metadata.mdl.json",
                Path("/Users/sameermangalampalli/flowharmonicai/data/cvedata/migrations/enum_metadata.mdl.json"),
            ]
            
            for path in possible_paths:
                if path.exists():
                    with open(path, 'r') as f:
                        enum_metadata = json.load(f)
                        logger.info(f"Loaded enum metadata from {path}")
                        return enum_metadata
            
            logger.warning("Enum metadata file not found, using empty dict")
            return {}
        except Exception as e:
            logger.error(f"Error loading enum metadata: {e}")
            return {}
    
    def _load_sql_examples(self, sql_examples_path: Optional[str] = None) -> List[Dict[str, str]]:
        """Load SQL examples from metadata_transformation_examples.sql file"""
        try:
            # Try provided path first
            if sql_examples_path:
                path = Path(sql_examples_path)
                if path.exists():
                    examples = self._parse_sql_examples_file(path)
                    logger.info(f"Loaded {len(examples)} SQL examples from {path}")
                    return examples
            
            # Try multiple possible paths
            possible_paths = [
                Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "cvedata" / "migrations" / "metadata_transformation_examples.sql",
                Path(__file__).parent.parent.parent.parent.parent.parent.parent / "flowharmonicai" / "data" / "cvedata" / "migrations" / "metadata_transformation_examples.sql",
                Path("/Users/sameermangalampalli/flowharmonicai/data/cvedata/migrations/metadata_transformation_examples.sql"),
            ]
            
            for path in possible_paths:
                if path.exists():
                    examples = self._parse_sql_examples_file(path)
                    logger.info(f"Loaded {len(examples)} SQL examples from {path}")
                    return examples
            
            logger.warning("SQL examples file not found, using empty list")
            return []
        except Exception as e:
            logger.error(f"Error loading SQL examples: {e}")
            return []
    
    def _parse_sql_examples_file(self, file_path: Path) -> List[Dict[str, str]]:
        """Parse SQL examples file and extract individual examples with descriptions"""
        examples = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split content by example section markers
            # Pattern: -- =====... Example N: Description =====
            example_sections = re.split(
                r'-- =+.*?Example (\d+):\s*(.*?)\s*-+',
                content,
                flags=re.DOTALL | re.IGNORECASE
            )
            
            # Process sections (skip first empty part, then process in groups of 3: num, desc, content)
            for i in range(1, len(example_sections), 3):
                if i + 2 < len(example_sections):
                    example_num = example_sections[i].strip()
                    description = example_sections[i + 1].strip()
                    section_content = example_sections[i + 2]
                    
                    # Extract SQL query from the section
                    # Find the first SELECT or WITH statement
                    sql_match = re.search(
                        r'(SELECT|WITH).*?(?=-- =+.*?Example|\Z)',
                        section_content,
                        re.DOTALL | re.IGNORECASE
                    )
                    
                    if sql_match:
                        sql_query = sql_match.group(0).strip()
                        # Clean up: remove trailing comments and extra whitespace
                        sql_query = re.sub(r'--.*$', '', sql_query, flags=re.MULTILINE)
                        sql_query = re.sub(r'\n\s*\n\s*\n+', '\n\n', sql_query)  # Remove excessive blank lines
                        sql_query = sql_query.strip()
                        
                        if sql_query and len(sql_query) > 20:  # Ensure it's a real query
                            examples.append({
                                "example_number": example_num,
                                "description": description,
                                "sql": sql_query
                            })
            
            # Fallback: If regex splitting didn't work, try line-by-line parsing
            if not examples:
                lines = content.split('\n')
                current_example = None
                current_sql = []
                in_sql = False
                
                for line in lines:
                    # Check for example header
                    example_match = re.match(r'-- =+.*?Example (\d+):\s*(.*?)\s*-+', line, re.IGNORECASE)
                    if example_match:
                        # Save previous example if exists
                        if current_example and current_sql:
                            sql_query = '\n'.join(current_sql).strip()
                            if sql_query:
                                examples.append(current_example)
                        
                        # Start new example
                        current_example = {
                            "example_number": example_match.group(1),
                            "description": example_match.group(2).strip(),
                            "sql": ""
                        }
                        current_sql = []
                        in_sql = False
                        continue
                    
                    # Check if we're in SQL section
                    if re.match(r'^\s*(SELECT|WITH)', line, re.IGNORECASE):
                        in_sql = True
                    
                    # Collect SQL lines
                    if in_sql and current_example:
                        # Stop if we hit next example marker
                        if re.match(r'-- =+.*?Example', line, re.IGNORECASE):
                            in_sql = False
                            if current_sql:
                                current_example["sql"] = '\n'.join(current_sql).strip()
                                examples.append(current_example)
                                current_example = None
                                current_sql = []
                        else:
                            # Remove inline comments but keep the line
                            clean_line = re.sub(r'\s*--.*$', '', line)
                            if clean_line.strip():
                                current_sql.append(clean_line)
                
                # Save last example
                if current_example and current_sql:
                    current_example["sql"] = '\n'.join(current_sql).strip()
                    if current_example["sql"]:
                        examples.append(current_example)
            
            logger.info(f"Parsed {len(examples)} SQL examples from file")
            return examples
            
        except Exception as e:
            logger.error(f"Error parsing SQL examples file: {e}")
            return []
    
    async def generate_reasoning_plan(
        self,
        query: str,
        knowledge: Optional[List[str]] = None,
        contexts: List[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate reasoning plan for using enum metadata tables to create calculated columns.
        
        Args:
            query: Natural language question
            knowledge: Additional knowledge context
            contexts: Schema contexts
            **kwargs: Additional arguments
            
        Returns:
            Dictionary with enum metadata reasoning plan
        """
        try:
            # Extract enum metadata tables information
            enum_metadata_text = self._format_enum_metadata_for_prompt(self._enum_metadata)
            
            # Format knowledge
            knowledge_text = ""
            if knowledge:
                knowledge_text = "\n### ADDITIONAL KNOWLEDGE ###\n"
                for k in knowledge:
                    knowledge_text += f"- {k}\n"
            
            # Format schema contexts (filter to show only relevant parts)
            schema_text = ""
            if contexts:
                schema_text = "\n### DATABASE SCHEMA ###\n"
                # Show first 3 schema contexts to avoid overwhelming the prompt
                for ctx in contexts[:3]:
                    schema_text += f"{ctx}\n\n"
            
            # Format SQL examples
            sql_examples_text = self._format_sql_examples_for_prompt(self._sql_examples)
            
            # Build prompt
            system_prompt = self._get_enum_metadata_reasoning_system_prompt()
            user_prompt = f"""
### USER QUESTION ###
{query}

{enum_metadata_text}

{sql_examples_text}

{schema_text}

{knowledge_text}

### TASK ###
Analyze the user's question and determine:
1. Which enum metadata tables are needed (e.g., risk_impact_metadata, roles_metadata, asset_classification_metadata)
2. What classifications need to be calculated (e.g., impact_class, propagation_class, risk_level)
3. How to join enum metadata tables with asset tables
4. What numeric scores need to be retrieved from enum metadata
5. What calculated columns or metrics need to be created
6. Step-by-step SQL approach using enum metadata

Use the SQL examples provided above as reference patterns for how to:
- Join enum metadata tables (never use 'id' column, use 'code', 'enum_type', 'classification_type')
- Calculate classifications using CASE statements
- Retrieve numeric scores dynamically from metadata tables
- Combine multiple metadata sources using CTEs or subqueries
- Apply weights and multipliers from metadata tables

Generate a detailed reasoning plan in JSON format.
"""
            
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            
            prompt = ChatPromptTemplate.from_messages(messages)
            chain = prompt | self.llm
            
            result = await chain.ainvoke(
                {
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt
                },
                **SQL_GENERATION_MODEL_KWARGS
            )
            
            # Extract reasoning from result
            reasoning_content = result.content if hasattr(result, 'content') else str(result)
            
            # Parse reasoning to extract structured information
            reasoning_plan = self._parse_enum_metadata_reasoning(reasoning_content)
            
            logger.info(f"Generated enum metadata reasoning plan: {reasoning_plan.get('enum_tables_used', [])}")
            
            return {
                "success": True,
                "reasoning": reasoning_content,
                "reasoning_plan": reasoning_plan
            }
            
        except Exception as e:
            logger.error(f"Error generating enum metadata reasoning: {e}")
            return {
                "success": False,
                "reasoning": "",
                "reasoning_plan": {},
                "error": str(e)
            }
    
    def _format_enum_metadata_for_prompt(self, enum_metadata: Dict[str, Any]) -> str:
        """Format enum metadata MDL JSON for prompt"""
        if not enum_metadata or not enum_metadata.get("models"):
            return "### ENUM METADATA TABLES ###\nNo enum metadata available.\n"
        
        text = "### ENUM METADATA TABLES ###\n"
        text += "The following enum metadata tables are available for classification and scoring:\n\n"
        
        for model in enum_metadata.get("models", []):
            name = model.get("name", "")
            description = model.get("properties", {}).get("description", "")
            table_ref = model.get("tableReference", {}).get("table", name)
            
            text += f"**{name}** (table: {table_ref})\n"
            if description:
                text += f"Description: {description}\n"
            
            # List key columns
            columns = model.get("columns", [])
            key_columns = []
            for col in columns:
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                col_desc = col.get("properties", {}).get("description", "")
                if col_name in ["enum_type", "code", "numeric_score", "priority_order", "criticality_score", "risk_score"]:
                    key_columns.append(f"  - {col_name} ({col_type}): {col_desc}")
            
            if key_columns:
                text += "Key columns:\n" + "\n".join(key_columns[:10]) + "\n"  # Limit to 10 columns
            
            text += "\n"
        
        return text
    
    def _format_sql_examples_for_prompt(self, sql_examples: List[Dict[str, str]]) -> str:
        """Format SQL examples for inclusion in the prompt"""
        if not sql_examples:
            return "### SQL EXAMPLES ###\nNo SQL examples available.\n"
        
        text = "### SQL EXAMPLES ###\n"
        text += "The following SQL examples demonstrate how to use enum metadata tables to calculate impact, risk, and likelihood scores.\n"
        text += "These examples show the patterns and join strategies you should follow:\n\n"
        
        # Include up to 5-7 most relevant examples (to avoid overwhelming the prompt)
        # Prioritize examples that show different patterns
        examples_to_show = sql_examples[:7] if len(sql_examples) > 7 else sql_examples
        
        for example in examples_to_show:
            example_num = example.get("example_number", "?")
            description = example.get("description", "")
            sql = example.get("sql", "")
            
            text += f"**Example {example_num}: {description}**\n"
            text += "```sql\n"
            # Truncate very long SQL queries to keep prompt manageable
            if len(sql) > 2000:
                sql_preview = sql[:2000] + "\n-- ... (truncated) ..."
            else:
                sql_preview = sql
            text += sql_preview
            text += "\n```\n\n"
        
        if len(sql_examples) > len(examples_to_show):
            text += f"*Note: {len(sql_examples) - len(examples_to_show)} more examples available in the examples file.*\n\n"
        
        text += "### KEY PATTERNS FROM EXAMPLES ###\n"
        text += "1. **Join Pattern**: Always join on 'code', 'enum_type', or 'classification_type', NEVER on 'id'\n"
        text += "2. **Classification**: Use CASE statements to map asset attributes to metadata codes\n"
        text += "3. **Score Retrieval**: Join with metadata tables using enum_type + code to get numeric_score\n"
        text += "4. **Combined Calculations**: Use CTEs to combine multiple metadata sources with weighted formulas\n"
        text += "5. **Dynamic Lookup**: Retrieve scores dynamically from metadata, don't hardcode values\n\n"
        
        return text
    
    def _get_enum_metadata_reasoning_system_prompt(self) -> str:
        """Get system prompt for enum metadata reasoning generation"""
        return """
### TASK ###
You are an expert SQL data analyst specializing in using enum metadata tables to create calculated columns and classifications.

You analyze user questions to determine how to use enum metadata tables (like risk_impact_metadata, roles_metadata, asset_classification_metadata) to:
1. Classify assets (e.g., impact_class, propagation_class, risk_level)
2. Calculate numeric scores from enum metadata
3. Join enum metadata tables with asset tables
4. Create calculated columns that combine enum metadata scores

### ENUM METADATA USAGE PATTERNS ###
1. **Classification**: Use enum metadata to classify assets based on their attributes
   - Example: Classify asset as "Mission Critical" by checking roles_metadata.criticality_score >= 90
   - Example: Classify asset as "Perimeter" by checking network interfaces and using risk_impact_metadata for propagation_class
   
2. **Score Retrieval**: Query enum metadata tables to get numeric scores
   - Example: Get numeric_score from risk_impact_metadata WHERE enum_type='impact_class' AND code='Mission Critical'
   - Example: Get criticality_score from roles_metadata WHERE code='DNS'
   
3. **Combined Calculations**: Combine multiple enum metadata scores
   - Example: Calculate combined impact = (impact_class_score * 0.7) + (propagation_class_score * 0.3)
   - Example: Calculate risk score using multiple enum metadata tables

4. **SQL Examples**: Reference the SQL examples provided in the user prompt to see concrete implementations
   - The examples show how to join metadata tables correctly (using code, enum_type, classification_type)
   - They demonstrate CASE statement patterns for classification
   - They show how to combine multiple metadata sources using CTEs
   - They illustrate dynamic score retrieval patterns

### REASONING PLAN REQUIREMENTS ###
Your reasoning plan must identify:
1. **Enum Tables Needed**: Which enum metadata tables are required
2. **Classifications**: What classifications need to be determined (impact_class, propagation_class, etc.)
3. **Join Strategy**: How to join enum metadata tables with asset tables
4. **Score Retrieval**: Which numeric scores to retrieve from enum metadata
5. **Calculation Steps**: Step-by-step approach to create calculated columns
6. **SQL Pattern**: SQL pattern to use (e.g., CASE statements, JOINs, subqueries)
7. **ID Column Usage**: We should not use it for any join purpose as it would be a wrong approach for metadata.

### OUTPUT FORMAT ###
Provide a structured reasoning plan in JSON format:
{
    "enum_tables_used": ["risk_impact_metadata", "roles_metadata"],
    "classifications_needed": ["impact_class", "propagation_class"],
    "join_strategy": {
        "primary_table": "dev_assets",
        "joins": [
            {"table": "roles_metadata", "condition": "assets.roles = roles_metadata.code"},
            {"table": "risk_impact_metadata", "condition": "risk_impact_metadata.enum_type = 'impact_class' AND risk_impact_metadata.code = calculated_impact_class"}
        ]
    },
    "score_retrieval": [
        {"source": "risk_impact_metadata", "enum_type": "impact_class", "code": "Mission Critical", "score_column": "numeric_score"},
        {"source": "risk_impact_metadata", "enum_type": "propagation_class", "code": "Perimeter", "score_column": "numeric_score"}
    ],
    "calculation_steps": [
        {
            "step": 1,
            "description": "Classify asset impact class based on roles",
            "sql_pattern": "CASE WHEN roles_metadata.criticality_score >= 90 THEN 'Mission Critical' ..."
        }
    ],
    "final_calculation": "combined_score = (impact_score * 0.7) + (propagation_score * 0.3)"
}
"""
    
    def _parse_enum_metadata_reasoning(
        self,
        reasoning_content: str
    ) -> Dict[str, Any]:
        """Parse the enum metadata reasoning content to extract structured information"""
        try:
            # Try to extract JSON from the reasoning
            json_match = re.search(r'\{[\s\S]*\}', reasoning_content)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    return parsed
                except json.JSONDecodeError:
                    pass
            
            # Fallback: Extract information using heuristics
            reasoning_lower = reasoning_content.lower()
            
            enum_tables = []
            if "risk_impact_metadata" in reasoning_lower:
                enum_tables.append("risk_impact_metadata")
            if "roles_metadata" in reasoning_lower:
                enum_tables.append("roles_metadata")
            if "asset_classification_metadata" in reasoning_lower:
                enum_tables.append("asset_classification_metadata")
            
            classifications = []
            if "impact_class" in reasoning_lower or "impact class" in reasoning_lower:
                classifications.append("impact_class")
            if "propagation_class" in reasoning_lower or "propagation class" in reasoning_lower:
                classifications.append("propagation_class")
            if "risk_level" in reasoning_lower or "risk level" in reasoning_lower:
                classifications.append("risk_level")
            
            return {
                "enum_tables_used": enum_tables,
                "classifications_needed": classifications,
                "join_strategy": {},
                "score_retrieval": [],
                "calculation_steps": [],
                "final_calculation": ""
            }
            
        except Exception as e:
            logger.error(f"Error parsing enum metadata reasoning: {e}")
            return {
                "enum_tables_used": [],
                "classifications_needed": [],
                "join_strategy": {},
                "score_retrieval": [],
                "calculation_steps": [],
                "final_calculation": ""
            }
    
    def get_enum_metadata(self) -> Dict[str, Any]:
        """Get the loaded enum metadata"""
        return self._enum_metadata
    
    def get_sql_examples(self) -> List[Dict[str, str]]:
        """Get the loaded SQL examples"""
        return self._sql_examples


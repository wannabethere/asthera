from sqlalchemy.orm import Session
from app.schemas.dbmodels import  Metric, View,  CalculatedColumn, Table, SQLColumn
from app.utils.history import ProjectManager
from app.service.models import GeneratedDefinition, DefinitionType,UserExample
import uuid
from typing import List,Dict,Any
from datetime import datetime
from app.mcpserver import MCPServerClient
from app.agents.project_manager import LLMDefinitionGenerator,DefinitionValidationService,TableMatchingTool
# from langchain_community.llms import OpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from dotenv import load_dotenv
import traceback
from fastapi import HTTPException
from dataclasses import asdict
load_dotenv()

class DefinitionPersistenceService:
    """Service for persisting generated definitions to database"""
    
    def __init__(self, session: Session, project_manager: ProjectManager):
        self.session = session
        self.project_manager = project_manager
    
    def persist_definition(self, definition: GeneratedDefinition, 
                         project_id: str, created_by: str) -> str:
        """Persist generated definition to database"""
        try:
            if definition.definition_type == DefinitionType.METRIC:
                entity_id = self._create_metric(definition, project_id, created_by)
            elif definition.definition_type == DefinitionType.VIEW:
                entity_id = self._create_view(definition, project_id, created_by)
            elif definition.definition_type == DefinitionType.CALCULATED_COLUMN:
                entity_id = self._create_calculated_column(definition, project_id, created_by)
            else:
                raise ValueError(f"Unknown definition type: {definition.definition_type}")
            
            self.session.commit()
            return str(entity_id)
            
        except Exception as e:
            self.session.rollback()
            raise Exception(f"Failed to persist definition: {str(e)}")
    
    def _create_metric(self, definition: GeneratedDefinition, 
                      project_id: str, created_by: str) -> uuid.UUID:
        """Create metric in database"""
        # Find appropriate table for the metric
        table = self._find_primary_table(definition.related_tables, project_id)
        
        metric = Metric(
            table_id=table.table_id,
            name=definition.name,
            display_name=definition.display_name,
            description=definition.description,
            metric_sql=definition.sql_query,
            metric_type=definition.metadata.get('metric_type', 'custom'),
            aggregation_type=definition.metadata.get('aggregation_type', 'sum'),
            format_string=definition.metadata.get('format_string'),
            modified_by=created_by,
            metadata={
                **definition.metadata,
                'chain_of_thought': definition.chain_of_thought,
                'confidence_score': definition.confidence_score,
                'suggestions': definition.suggestions,
                'related_tables': definition.related_tables,
                'related_columns': definition.related_columns,
                'generated_by': 'llm_service',
                'generation_timestamp': datetime.utcnow().isoformat()
            }
        )
        
        self.session.add(metric)
        self.session.flush()  # Get the ID
        return metric.metric_id
    
    def _create_view(self, definition: GeneratedDefinition, 
                    project_id: str, created_by: str) -> uuid.UUID:
        """Create view in database"""
        table = self._find_primary_table(definition.related_tables, project_id)
        
        view = View(
            table_id=table.table_id,
            name=definition.name,
            display_name=definition.display_name,
            description=definition.description,
            view_sql=definition.sql_query,
            view_type=definition.metadata.get('view_type', 'custom'),
            modified_by=created_by,
            metadata={
                **definition.metadata,
                'chain_of_thought': definition.chain_of_thought,
                'confidence_score': definition.confidence_score,
                'suggestions': definition.suggestions,
                'related_tables': definition.related_tables,
                'related_columns': definition.related_columns,
                'generated_by': 'llm_service',
                'generation_timestamp': datetime.utcnow().isoformat()
            }
        )
        
        self.session.add(view)
        self.session.flush()
        return view.view_id
    
    def _create_calculated_column(self, definition: GeneratedDefinition, 
                                project_id: str, created_by: str) -> uuid.UUID:
        """Create calculated column in database"""
        table = self._find_primary_table(definition.related_tables, project_id)
        
        # Create the SQLColumn with type 'calculated_column'
        column = SQLColumn(
            table_id=table.table_id,
            name=definition.name,
            display_name=definition.display_name,
            description=definition.description,
            column_type='calculated_column',  # Mark as calculated column
            data_type=definition.metadata.get('data_type', 'VARCHAR'),
            usage_type=definition.metadata.get('usage_type', 'calculated'),
            is_nullable=definition.metadata.get('is_nullable', True),
            is_primary_key=definition.metadata.get('is_primary_key', False),
            is_foreign_key=definition.metadata.get('is_foreign_key', False),
            default_value=definition.metadata.get('default_value'),
            ordinal_position=definition.metadata.get('ordinal_position'),
            json_metadata={
                **definition.metadata,
                'chain_of_thought': definition.chain_of_thought,
                'confidence_score': definition.confidence_score,
                'suggestions': definition.suggestions,
                'related_tables': definition.related_tables,
                'related_columns': definition.related_columns,
                'generated_by': 'llm_service',
                'generation_timestamp': datetime.utcnow().isoformat()
            },
            modified_by=created_by
        )
        
        self.session.add(column)
        self.session.flush()
        
        # Create the associated CalculatedColumn with the calculation details
        calc_column = CalculatedColumn(
            column_id=column.column_id,
            calculation_sql=definition.sql_query,
            function_id=definition.metadata.get('function_id'),
            dependencies=definition.related_columns,
            modified_by=created_by
        )
        
        self.session.add(calc_column)
        self.session.flush()
        return column.column_id
    
    def _find_primary_table(self, table_names: List[str], project_id: str) -> Table:
        """Find the primary table for the definition"""
        if not table_names:
            # Default to first table if none specified
            table = self.session.query(Table).filter(
                Table.project_id == project_id
            ).first()
        else:
            # Use the first mentioned table
            table = self.session.query(Table).filter(
                Table.project_id == project_id,
                Table.name == table_names[0]
            ).first()
        
        if not table:
            raise ValueError(f"No suitable table found for definition")
        
        return table



class LLMDefinitionService:
    """Main orchestration service for LLM-powered definition creation"""
    
    def __init__(self, session: Session, openai_api_key: str, 
                 mcp_server_url: str, project_id: str):
        self.session = session
        self.project_id = project_id
        self.project_manager = ProjectManager(session)
        
        # Initialize services
        self.mcp_client = MCPServerClient(mcp_server_url, project_id)
        self.llm_generator = LLMDefinitionGenerator(openai_api_key)
        self.validator = DefinitionValidationService(session, project_id)
        self.persistence = DefinitionPersistenceService(session, self.project_manager)
        
        # Table matching tool (legacy initialize_agent / ConversationBufferMemory removed in LangChain 0.3+)
        self.table_matching_tool = TableMatchingTool(
            session=session,
            domain_id=project_id,
        )
    
    async def create_definition_from_example(self, user_example: UserExample) -> Dict[str, Any]:
        """Main flow: create definition from user example"""
        try:
            # Step 1: Get project context from MCP server
            context = await self.mcp_client.get_project_context()
            print("context in llmservice", context)
            print("userExample in llmservice", user_example)
            
            # Step 2: Match tables and columns via tool
            table_matches = await self.table_matching_tool.ainvoke(
                f"Find tables and columns related to: {user_example.description}"
            )
            
            # Step 3: Generate definition using LLM
            if user_example.definition_type == DefinitionType.METRIC:
                definition = await self.llm_generator.generate_metric_definition(
                    user_example, context
                )
            elif user_example.definition_type == DefinitionType.VIEW:
                definition = await self.llm_generator.generate_view_definition(
                    user_example, context
                )
            elif user_example.definition_type == DefinitionType.CALCULATED_COLUMN:
                definition = await self.llm_generator.generate_calculated_column_definition(
                    user_example, context
                )
            else:
                raise ValueError(f"Unknown definition type: {user_example.definition_type}")
            
            # Step 4: Validate the generated definition
            is_valid, validation_errors = self.validator.validate_definition(definition)
            
            # Step 5: If valid, persist to database
            entity_id = None
            if is_valid:
                entity_id = self.persistence.persist_definition(
                    definition, self.project_id, user_example.user_id
                )
            
            # Step 6: Return comprehensive result
            return {
                "success": is_valid,
                "entity_id": entity_id,
                "definition": asdict(definition) if definition else None,
                "table_matches": table_matches,
                "validation_errors": validation_errors,
                "context_used": {
                    "tables_analyzed": len(context.get('tables', {})),
                    "existing_metrics": len(context.get('existing_metrics', [])),
                    "business_rules_applied": len(context.get('business_context', {}).get('business_rules', []))
                }
            }
            
        except Exception as e:
            
        # --- THIS IS THE CRITICAL DIAGNOSTIC CHANGE ---
            print("--- !!! AN EXCEPTION OCCURRED !!! ---")
            print(f"Python Exception Type: {type(e)}")
            print(f"Python Exception repr: {repr(e)}")
            print("--- FULL TRACEBACK ---")
            
            # This will print the complete error stack trace to your console
            traceback.print_exc() 
            
            print("--- END TRACEBACK ---")
            
            # We raise a generic error to the client, but the real error is in our logs.
            # raise HTTPException(status_code=500, detail="An internal error occurred. Check server logs for full traceback.")
            return {
                "success": False,
                "error": str(e),
                "definition": None,
                "entity_id": None
            }
    
    async def interactive_definition_creation(self, definition_type: DefinitionType) -> Dict[str, Any]:
        """Interactive flow for creating definitions with user guidance"""
        
        print(f"\n🚀 Creating a new {definition_type.value}")
        print("=" * 50)
        
        # Collect user input
        name = input("Enter the name: ").strip()
        description = input("Enter the description: ").strip()
        
        sql = None
        if input("Do you have SQL code? (y/n): ").lower().startswith('y'):
            print("Enter your SQL (press Enter twice to finish):")
            sql_lines = []
            while True:
                line = input()
                if line == "" and sql_lines and sql_lines[-1] == "":
                    break
                sql_lines.append(line)
            sql = "\n".join(sql_lines[:-1])  # Remove last empty line
        
        # Additional context
        additional_context = {}
        if input("Add additional context? (y/n): ").lower().startswith('y'):
            context_input = input("Enter context (JSON format or description): ").strip()
            try:
                additional_context = json.loads(context_input)
            except:
                additional_context = {"description": context_input}
        
        # Create user example
        user_example = UserExample(
            definition_type=definition_type,
            name=name,
            description=description,
            sql=sql,
            additional_context=additional_context,
            user_id="interactive_user"
        )
        
        print("\n🔄 Processing your request...")
        
        # Generate definition
        result = await self.create_definition_from_example(user_example)
        
        # Display results
        if result["success"]:
            print("\n✅ Definition created successfully!")
            print(f"Entity ID: {result['entity_id']}")
            print(f"Generated Name: {result['definition']['name']}")
            print(f"Display Name: {result['definition']['display_name']}")
            print(f"Confidence Score: {result['definition']['confidence_score']}")
            print(f"\nSQL Query:\n{result['definition']['sql_query']}")
            print(f"\nChain of Thought:\n{result['definition']['chain_of_thought']}")
            
            if result['definition']['suggestions']:
                print(f"\n💡 Suggestions:")
                for suggestion in result['definition']['suggestions']:
                    print(f"  - {suggestion}")
        else:
            print("\n❌ Failed to create definition")
            print(f"Error: {result.get('error', 'Unknown error')}")
            if result.get('validation_errors'):
                print("Validation Errors:")
                for error in result['validation_errors']:
                    print(f"  - {error}")
        
        return result
    
    async def batch_create_definitions(self, examples: List[UserExample]) -> List[Dict[str, Any]]:
        """Create multiple definitions in batch"""
        results = []
        
        for i, example in enumerate(examples):
            print(f"\nProcessing definition {i+1}/{len(examples)}: {example.name}")
            result = await self.create_definition_from_example(example)
            results.append(result)
            
            if result["success"]:
                print(f"✅ Created: {result['definition']['name']}")
            else:
                print(f"❌ Failed: {result.get('error', 'Unknown error')}")
        
        return results
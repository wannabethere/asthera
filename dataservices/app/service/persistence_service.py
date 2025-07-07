from app.service.models import GeneratedDefinition, DefinitionType, UserExample
from app.utils.history import ProjectManager
from app.schemas.dbmodels import (
    Metric, View, CalculatedColumn, SQLColumn, Table, Project, 
    SQLFunction, Instruction, KnowledgeBase, Example
)
from app.core.session_manager import SessionManager
from sqlalchemy.orm import Session
from sqlalchemy import select
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DefinitionPersistenceService:
    """Service for persisting generated definitions to database"""
    
    def __init__(self, session_manager: SessionManager, project_manager: ProjectManager):
        self.session_manager = session_manager
        self.project_manager = project_manager
    
    async def persist_definition(self, definition: GeneratedDefinition, 
                               project_id: str, created_by: str) -> str:
        """Persist generated definition to database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                if definition.definition_type == DefinitionType.METRIC:
                    entity_id = await self._create_metric(session, definition, project_id, created_by)
                elif definition.definition_type == DefinitionType.VIEW:
                    entity_id = await self._create_view(session, definition, project_id, created_by)
                elif definition.definition_type == DefinitionType.CALCULATED_COLUMN:
                    entity_id = await self._create_calculated_column(session, definition, project_id, created_by)
                else:
                    raise ValueError(f"Unknown definition type: {definition.definition_type}")
                
                await session.commit()
                return str(entity_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist definition: {str(e)}")
    
    async def _create_metric(self, session: Session, definition: GeneratedDefinition, 
                           project_id: str, created_by: str) -> uuid.UUID:
        """Create metric in database"""
        # Find appropriate table for the metric
        table = await self._find_primary_table(session, definition.related_tables, project_id)
        
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
            json_metadata={
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
        
        session.add(metric)
        await session.flush()  # Get the ID
        return metric.metric_id
    
    async def _create_view(self, session: Session, definition: GeneratedDefinition, 
                          project_id: str, created_by: str) -> uuid.UUID:
        """Create view in database"""
        table = await self._find_primary_table(session, definition.related_tables, project_id)
        
        view = View(
            table_id=table.table_id,
            name=definition.name,
            display_name=definition.display_name,
            description=definition.description,
            view_sql=definition.sql_query,
            view_type=definition.metadata.get('view_type', 'custom'),
            modified_by=created_by,
            json_metadata={
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
        
        session.add(view)
        await session.flush()
        return view.view_id
    
    async def _create_calculated_column(self, session: Session, definition: GeneratedDefinition, 
                                      project_id: str, created_by: str) -> uuid.UUID:
        """Create calculated column in database"""
        table = await self._find_primary_table(session, definition.related_tables, project_id)
        
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
        
        session.add(column)
        await session.flush()
        
        # Create the associated CalculatedColumn with the calculation details
        calc_column = CalculatedColumn(
            column_id=column.column_id,
            calculation_sql=definition.sql_query,
            function_id=definition.metadata.get('function_id'),
            dependencies=definition.related_columns,
            modified_by=created_by
        )
        
        session.add(calc_column)
        await session.flush()
        return column.column_id
    
    async def _find_primary_table(self, session: Session, table_names: List[str], project_id: str) -> Table:
        """Find the primary table for the definition"""
        if not table_names:
            # Default to first table if none specified
            result = await session.execute(
                select(Table).where(Table.project_id == project_id).limit(1)
            )
            table = result.scalar_one_or_none()
        else:
            # Use the first mentioned table
            result = await session.execute(
                select(Table).where(
                    Table.project_id == project_id,
                    Table.name == table_names[0]
                )
            )
            table = result.scalar_one_or_none()
        
        if not table:
            raise ValueError(f"No suitable table found for definition")
        
        return table


class ProjectPersistenceService:
    """Service for persisting project to database"""
    
    def __init__(self, session_manager: SessionManager, project_manager: ProjectManager):
        self.session_manager = session_manager
        self.project_manager = project_manager
        
    async def persist_project(self, project: Project, created_by: str) -> str:
        """Persist project to database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Set the created_by field
                project.created_by = created_by
                
                # Add to session and commit
                session.add(project)
                await session.commit()
                
                return project.project_id
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist project: {str(e)}")
    
    async def update_project(self, project_id: str, updates: Dict[str, Any], 
                           modified_by: str) -> Project:
        """Update project in database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(Project).where(Project.project_id == project_id)
                )
                project = result.scalar_one_or_none()
                
                if not project:
                    raise ValueError(f"Project {project_id} not found")
                
                # Update fields
                for key, value in updates.items():
                    if hasattr(project, key):
                        setattr(project, key, value)
                
                project.last_modified_by = modified_by
                project.updated_at = datetime.utcnow()
                
                await session.commit()
                return project
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to update project: {str(e)}")
    
    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(Project).where(Project.project_id == project_id)
            )
            return result.scalar_one_or_none()
    
    async def list_projects(self, status: Optional[str] = None) -> List[Project]:
        """List projects with optional status filter"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(Project)
            if status:
                query = query.where(Project.status == status)
            result = await session.execute(query)
            return result.scalars().all()


class UserExamplePersistenceService:
    """Service for persisting user examples to database"""
    
    def __init__(self, session_manager: SessionManager, project_manager: ProjectManager,
                 sql_pairs_processor=None, instructions_processor=None):
        self.session_manager = session_manager
        self.project_manager = project_manager
        self.sql_pairs_processor = sql_pairs_processor
        self.instructions_processor = instructions_processor
    
    async def persist_user_example(self, user_example: UserExample, 
                                 project_id: str) -> str:
        """Persist user example to database and optionally index to ChromaDB"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Convert UserExample to Example model
                example = Example(
                    project_id=project_id,
                    definition_type=user_example.definition_type.value if user_example.definition_type else 'sql_pair',
                    name=user_example.name,
                    question=user_example.description,
                    sql_query=user_example.sql or "",
                    context=user_example.additional_context.get('context') if user_example.additional_context else None,
                    document_reference=user_example.additional_context.get('document_reference') if user_example.additional_context else None,
                    instructions=user_example.additional_context.get('instructions') if user_example.additional_context else None,
                    categories=[user_example.definition_type.value] if user_example.definition_type else [],
                    samples=user_example.additional_context.get('samples') if user_example.additional_context else None,
                    additional_context=user_example.additional_context,
                    user_id=user_example.user_id,
                    modified_by=user_example.user_id,
                    json_metadata={
                        'definition_type': user_example.definition_type.value if user_example.definition_type else None,
                        'original_name': user_example.name,
                        'additional_context': user_example.additional_context,
                        'created_from': 'user_example'
                    }
                )
                
                session.add(example)
                await session.commit()
                
                # Index to ChromaDB if definition type is sql_pair or instruction
                if user_example.definition_type in [DefinitionType.SQL_PAIR, DefinitionType.INSTRUCTION]:
                    await self._index_to_chromadb(example, user_example)
                
                return str(example.example_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist user example: {str(e)}")
    
    async def _index_to_chromadb(self, example: Example, user_example: UserExample):
        """Index example to ChromaDB based on definition type"""
        try:
            if user_example.definition_type == DefinitionType.SQL_PAIR and self.sql_pairs_processor:
                # Convert to SqlPair format
                sql_pair_data = {
                    "question": example.question,
                    "sql": example.sql_query,
                    "instructions": example.instructions,
                    "chain_of_thought": example.json_metadata.get('chain_of_thought')
                }
                
                await self.sql_pairs_processor.run(
                    sql_pairs=[sql_pair_data],
                    project_id=example.project_id
                )
                logger.info(f"Indexed SQL pair to ChromaDB: {example.example_id}")
                
            elif user_example.definition_type == DefinitionType.INSTRUCTION and self.instructions_processor:
                # Convert to Instruction format
                from app.agents.indexing.instructions import Instruction as ChromaInstruction
                
                instruction = ChromaInstruction(
                    instruction=example.instructions or example.question,
                    question=example.question,
                    sql=example.sql_query,
                    chain_of_thought=example.json_metadata.get('chain_of_thought'),
                    is_default=False
                )
                
                await self.instructions_processor.run(
                    instructions=[instruction],
                    project_id=example.project_id
                )
                logger.info(f"Indexed instruction to ChromaDB: {example.example_id}")
                
        except Exception as e:
            logger.error(f"Failed to index example to ChromaDB: {str(e)}")
            # Don't raise the exception to avoid failing the database transaction
            # The example is still saved to the database
    
    async def get_user_examples(self, project_id: str, 
                              definition_type: Optional[DefinitionType] = None) -> List[Example]:
        """Get user examples for a project"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(Example).where(Example.project_id == project_id)
            
            if definition_type:
                query = query.where(Example.categories.contains([definition_type.value]))
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_user_example_by_id(self, example_id: str) -> Optional[Example]:
        """Get user example by ID"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(Example).where(Example.example_id == example_id)
            )
            return result.scalar_one_or_none()
    
    async def update_user_example(self, example_id: str, updates: Dict[str, Any], 
                                modified_by: str) -> Example:
        """Update user example"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(Example).where(Example.example_id == example_id)
                )
                example = result.scalar_one_or_none()
                
                if not example:
                    raise ValueError(f"Example {example_id} not found")
                
                # Update fields
                for key, value in updates.items():
                    if hasattr(example, key):
                        setattr(example, key, value)
                
                example.modified_by = modified_by
                example.updated_at = datetime.utcnow()
                
                await session.commit()
                return example
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to update user example: {str(e)}")
    
    async def delete_user_example(self, example_id: str) -> bool:
        """Delete user example"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(Example).where(Example.example_id == example_id)
                )
                example = result.scalar_one_or_none()
                
                if not example:
                    raise ValueError(f"Example {example_id} not found")
                
                await session.delete(example)
                await session.commit()
                return True
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to delete user example: {str(e)}")


class SQLFunctionPersistenceService:
    """Service for persisting SQL functions to database"""
    
    def __init__(self, session_manager: SessionManager, project_manager: ProjectManager):
        self.session_manager = session_manager
        self.project_manager = project_manager
    
    async def persist_sql_function(self, function_data: Dict[str, Any], 
                                 created_by: str, project_id: Optional[str] = None) -> str:
        """Persist SQL function to database with optional project_id"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                sql_function = SQLFunction(
                    project_id=project_id,
                    name=function_data['name'],
                    display_name=function_data.get('display_name'),
                    description=function_data.get('description'),
                    function_sql=function_data['function_sql'],
                    return_type=function_data.get('return_type'),
                    parameters=function_data.get('parameters', []),
                    modified_by=created_by,
                    json_metadata=function_data.get('metadata', {})
                )
                
                session.add(sql_function)
                await session.commit()
                
                return str(sql_function.function_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist SQL function: {str(e)}")
    
    async def persist_sql_functions_batch(self, functions_data: List[Dict[str, Any]], 
                                        created_by: str, project_id: Optional[str] = None) -> List[str]:
        """Persist multiple SQL functions in batch with optional project_id"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                function_ids = []
                
                for function_data in functions_data:
                    sql_function = SQLFunction(
                        project_id=project_id,
                        name=function_data['name'],
                        display_name=function_data.get('display_name'),
                        description=function_data.get('description'),
                        function_sql=function_data['function_sql'],
                        return_type=function_data.get('return_type'),
                        parameters=function_data.get('parameters', []),
                        modified_by=created_by,
                        json_metadata=function_data.get('metadata', {})
                    )
                    
                    session.add(sql_function)
                    function_ids.append(sql_function)
                
                await session.commit()
                
                return [str(sql_function.function_id) for sql_function in function_ids]
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist SQL functions batch: {str(e)}")
    
    async def get_sql_functions(self, project_id: Optional[str] = None) -> List[SQLFunction]:
        """Get all SQL functions, optionally filtered by project_id"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(SQLFunction)
            if project_id:
                query = query.where(SQLFunction.project_id == project_id)
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_sql_functions_by_name(self, name: str, project_id: Optional[str] = None) -> List[SQLFunction]:
        """Get SQL functions by name, optionally filtered by project_id"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(SQLFunction).where(SQLFunction.name == name)
            if project_id:
                query = query.where(SQLFunction.project_id == project_id)
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_sql_function(self, function_id: str) -> Optional[SQLFunction]:
        """Get SQL function by ID"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(SQLFunction).where(SQLFunction.function_id == function_id)
            )
            return result.scalar_one_or_none()
    
    async def get_global_sql_functions(self) -> List[SQLFunction]:
        """Get all SQL functions that are not associated with any project (global functions)"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(SQLFunction).where(SQLFunction.project_id.is_(None))
            )
            return result.scalars().all()
    
    async def search_sql_functions(self, search_term: str, project_id: Optional[str] = None) -> List[SQLFunction]:
        """Search SQL functions by name or description"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(SQLFunction).where(
                (SQLFunction.name.ilike(f"%{search_term}%")) |
                (SQLFunction.description.ilike(f"%{search_term}%"))
            )
            if project_id:
                query = query.where(SQLFunction.project_id == project_id)
            result = await session.execute(query)
            return result.scalars().all()
    
    async def update_sql_function(self, function_id: str, updates: Dict[str, Any], 
                                modified_by: str) -> SQLFunction:
        """Update SQL function"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(SQLFunction).where(SQLFunction.function_id == function_id)
                )
                sql_function = result.scalar_one_or_none()
                
                if not sql_function:
                    raise ValueError(f"SQL Function {function_id} not found")
                
                # Update fields
                for key, value in updates.items():
                    if hasattr(sql_function, key):
                        setattr(sql_function, key, value)
                
                sql_function.modified_by = modified_by
                sql_function.updated_at = datetime.utcnow()
                
                await session.commit()
                return sql_function
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to update SQL function: {str(e)}")
    
    async def delete_sql_function(self, function_id: str) -> bool:
        """Delete SQL function"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(SQLFunction).where(SQLFunction.function_id == function_id)
                )
                sql_function = result.scalar_one_or_none()
                
                if not sql_function:
                    raise ValueError(f"SQL Function {function_id} not found")
                
                await session.delete(sql_function)
                await session.commit()
                return True
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to delete SQL function: {str(e)}")
    
    async def get_sql_function_summary(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of SQL functions for a project or globally"""
        functions = await self.get_sql_functions(project_id)
        
        summary = {
            'total_functions': len(functions),
            'project_id': project_id,
            'return_types': {},
            'recent_functions': [],
            'total_parameters': 0
        }
        
        for function in functions:
            # Count return types
            return_type = function.return_type or 'unknown'
            summary['return_types'][return_type] = summary['return_types'].get(return_type, 0) + 1
            
            # Count parameters
            if function.parameters:
                summary['total_parameters'] += len(function.parameters)
            
            # Get recent functions (last 5)
            if len(summary['recent_functions']) < 5:
                summary['recent_functions'].append({
                    'function_id': str(function.function_id),
                    'name': function.name,
                    'display_name': function.display_name,
                    'return_type': function.return_type,
                    'created_at': function.created_at.isoformat() if function.created_at else None
                })
        
        return summary
    
    async def copy_sql_function_to_project(self, function_id: str, target_project_id: str, 
                                         created_by: str) -> str:
        """Copy a SQL function to another project"""
        try:
            source_function = await self.get_sql_function(function_id)
            if not source_function:
                raise ValueError(f"SQL Function {function_id} not found")
            
            # Create a copy with new project_id
            function_data = {
                'name': source_function.name,
                'display_name': source_function.display_name,
                'description': source_function.description,
                'function_sql': source_function.function_sql,
                'return_type': source_function.return_type,
                'parameters': source_function.parameters or [],
                'metadata': {
                    **(source_function.json_metadata or {}),
                    'copied_from': str(source_function.function_id),
                    'copied_at': datetime.utcnow().isoformat()
                }
            }
            
            return await self.persist_sql_function(function_data, created_by, target_project_id)
            
        except Exception as e:
            raise Exception(f"Failed to copy SQL function: {str(e)}")


class InstructionPersistenceService:
    """Service for persisting instructions to database"""
    
    def __init__(self, session_manager: SessionManager, project_manager: ProjectManager):
        self.session_manager = session_manager
        self.project_manager = project_manager
    
    async def persist_instruction(self, instruction_data: Dict[str, Any], 
                                project_id: str, created_by: str) -> str:
        """Persist instruction to database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                instruction = Instruction(
                    project_id=project_id,
                    question=instruction_data['question'],
                    instructions=instruction_data['instructions'],
                    sql_query=instruction_data['sql_query'],
                    chain_of_thought=instruction_data.get('chain_of_thought'),
                    modified_by=created_by,
                    json_metadata=instruction_data.get('metadata', {})
                )
                
                session.add(instruction)
                await session.commit()
                
                return str(instruction.instruction_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist instruction: {str(e)}")
    
    async def persist_instructions_batch(self, instructions_data: List[Dict[str, Any]], 
                                       project_id: str, created_by: str) -> List[str]:
        """Persist multiple instructions in batch"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                instruction_ids = []
                
                for instruction_data in instructions_data:
                    instruction = Instruction(
                        project_id=project_id,
                        question=instruction_data['question'],
                        instructions=instruction_data['instructions'],
                        sql_query=instruction_data['sql_query'],
                        chain_of_thought=instruction_data.get('chain_of_thought'),
                        modified_by=created_by,
                        json_metadata=instruction_data.get('metadata', {})
                    )
                    
                    session.add(instruction)
                    instruction_ids.append(instruction)
                
                await session.commit()
                
                return [str(instruction.instruction_id) for instruction in instruction_ids]
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist instructions batch: {str(e)}")
    
    async def get_instructions(self, project_id: str) -> List[Instruction]:
        """Get all instructions for a project"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(Instruction).where(Instruction.project_id == project_id)
            )
            return result.scalars().all()
    
    async def get_instruction_by_id(self, instruction_id: str) -> Optional[Instruction]:
        """Get instruction by ID"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(Instruction).where(Instruction.instruction_id == instruction_id)
            )
            return result.scalar_one_or_none()
    
    async def get_instruction(self, instruction_id: str) -> Optional[Instruction]:
        """Get instruction by ID"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(Instruction).where(Instruction.instruction_id == instruction_id)
            )
            return result.scalar_one_or_none()
    
    async def update_instruction(self, instruction_id: str, updates: Dict[str, Any], 
                               modified_by: str) -> Instruction:
        """Update instruction"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(Instruction).where(Instruction.instruction_id == instruction_id)
                )
                instruction = result.scalar_one_or_none()
                
                if not instruction:
                    raise ValueError(f"Instruction {instruction_id} not found")
                
                # Update fields
                for key, value in updates.items():
                    if hasattr(instruction, key):
                        setattr(instruction, key, value)
                
                instruction.modified_by = modified_by
                instruction.updated_at = datetime.utcnow()
                
                await session.commit()
                return instruction
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to update instruction: {str(e)}")
    
    async def delete_instruction(self, instruction_id: str) -> bool:
        """Delete instruction"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(Instruction).where(Instruction.instruction_id == instruction_id)
                )
                instruction = result.scalar_one_or_none()
                
                if not instruction:
                    raise ValueError(f"Instruction {instruction_id} not found")
                
                await session.delete(instruction)
                await session.commit()
                return True
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to delete instruction: {str(e)}")


class KnowledgeBasePersistenceService:
    """Service for persisting knowledge base entries to database"""
    
    def __init__(self, session_manager: SessionManager, project_manager: ProjectManager):
        self.session_manager = session_manager
        self.project_manager = project_manager
    
    async def persist_knowledge_base_entry(self, kb_data: Dict[str, Any], 
                                         project_id: str, created_by: str) -> str:
        """Persist knowledge base entry to database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                kb_entry = KnowledgeBase(
                    project_id=project_id,
                    name=kb_data['name'],
                    display_name=kb_data.get('display_name'),
                    description=kb_data.get('description'),
                    file_path=kb_data.get('file_path'),
                    content_type=kb_data.get('content_type', 'text'),
                    content=kb_data.get('content'),
                    modified_by=created_by,
                    json_metadata=kb_data.get('metadata', {})
                )
                
                session.add(kb_entry)
                await session.commit()
                
                return str(kb_entry.kb_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist knowledge base entry: {str(e)}")
    
    async def persist_knowledge_base_batch(self, kb_entries_data: List[Dict[str, Any]], 
                                         project_id: str, created_by: str) -> List[str]:
        """Persist multiple knowledge base entries in batch"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                kb_ids = []
                
                for kb_data in kb_entries_data:
                    kb_entry = KnowledgeBase(
                        project_id=project_id,
                        name=kb_data['name'],
                        display_name=kb_data.get('display_name'),
                        description=kb_data.get('description'),
                        file_path=kb_data.get('file_path'),
                        content_type=kb_data.get('content_type', 'text'),
                        content=kb_data.get('content'),
                        modified_by=created_by,
                        json_metadata=kb_data.get('metadata', {})
                    )
                    
                    session.add(kb_entry)
                    kb_ids.append(kb_entry)
                
                await session.commit()
                
                return [str(kb_entry.kb_id) for kb_entry in kb_ids]
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist knowledge base batch: {str(e)}")
    
    async def get_knowledge_base_entries(self, project_id: str, 
                                       content_type: Optional[str] = None) -> List[KnowledgeBase]:
        """Get knowledge base entries for a project"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(KnowledgeBase).where(KnowledgeBase.project_id == project_id)
            
            if content_type:
                query = query.where(KnowledgeBase.content_type == content_type)
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_knowledge_base_by_id(self, kb_id: str) -> Optional[KnowledgeBase]:
        """Get knowledge base entry by ID"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.kb_id == kb_id)
            )
            return result.scalar_one_or_none()
    
    async def get_knowledge_base_entry(self, kb_id: str) -> Optional[KnowledgeBase]:
        """Get knowledge base entry by ID"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(KnowledgeBase).where(KnowledgeBase.kb_id == kb_id)
            )
            return result.scalar_one_or_none()
    
    async def search_knowledge_base(self, project_id: str, search_term: str) -> List[KnowledgeBase]:
        """Search knowledge base entries by content"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.project_id == project_id,
                    KnowledgeBase.content.ilike(f"%{search_term}%")
                )
            )
            return result.scalars().all()
    
    async def update_knowledge_base_entry(self, kb_id: str, updates: Dict[str, Any], 
                                        modified_by: str) -> KnowledgeBase:
        """Update knowledge base entry"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(KnowledgeBase).where(KnowledgeBase.kb_id == kb_id)
                )
                kb_entry = result.scalar_one_or_none()
                
                if not kb_entry:
                    raise ValueError(f"Knowledge Base entry {kb_id} not found")
                
                # Update fields
                for key, value in updates.items():
                    if hasattr(kb_entry, key):
                        setattr(kb_entry, key, value)
                
                kb_entry.modified_by = modified_by
                kb_entry.updated_at = datetime.utcnow()
                
                await session.commit()
                return kb_entry
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to update knowledge base entry: {str(e)}")
    
    async def delete_knowledge_base_entry(self, kb_id: str) -> bool:
        """Delete knowledge base entry"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(KnowledgeBase).where(KnowledgeBase.kb_id == kb_id)
                )
                kb_entry = result.scalar_one_or_none()
                
                if not kb_entry:
                    raise ValueError(f"Knowledge Base entry {kb_id} not found")
                
                await session.delete(kb_entry)
                await session.commit()
                return True
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to delete knowledge base entry: {str(e)}")
    
    async def get_knowledge_base_summary(self, project_id: str) -> Dict[str, Any]:
        """Get summary of knowledge base for a project"""
        entries = await self.get_knowledge_base_entries(project_id)
        
        summary = {
            'total_entries': len(entries),
            'content_types': {},
            'recent_entries': [],
            'total_content_size': 0
        }
        
        for entry in entries:
            # Count content types
            content_type = entry.content_type or 'unknown'
            summary['content_types'][content_type] = summary['content_types'].get(content_type, 0) + 1
            
            # Calculate content size
            if entry.content:
                summary['total_content_size'] += len(entry.content)
            
            # Get recent entries (last 5)
            if len(summary['recent_entries']) < 5:
                summary['recent_entries'].append({
                    'kb_id': str(entry.kb_id),
                    'name': entry.name,
                    'display_name': entry.display_name,
                    'content_type': entry.content_type,
                    'created_at': entry.created_at.isoformat() if entry.created_at else None
                })
        
        return summary


class PersistenceServiceFactory:
    """Factory class to provide access to all persistence services"""
    
    def __init__(self, session_manager: SessionManager, project_manager: ProjectManager,
                 sql_pairs_processor=None, instructions_processor=None):
        self.session_manager = session_manager
        self.project_manager = project_manager
        self.sql_pairs_processor = sql_pairs_processor
        self.instructions_processor = instructions_processor
        
        # Initialize all services
        self.definition_service = DefinitionPersistenceService(session_manager, project_manager)
        self.project_service = ProjectPersistenceService(session_manager, project_manager)
        self.user_example_service = UserExamplePersistenceService(
            session_manager, project_manager, sql_pairs_processor, instructions_processor
        )
        self.sql_function_service = SQLFunctionPersistenceService(session_manager, project_manager)
        self.instruction_service = InstructionPersistenceService(session_manager, project_manager)
        self.knowledge_base_service = KnowledgeBasePersistenceService(session_manager, project_manager)
    
    def get_definition_service(self) -> DefinitionPersistenceService:
        """Get definition persistence service"""
        return self.definition_service
    
    def get_project_service(self) -> ProjectPersistenceService:
        """Get project persistence service"""
        return self.project_service
    
    def get_user_example_service(self) -> UserExamplePersistenceService:
        """Get user example persistence service"""
        return self.user_example_service
    
    def get_sql_function_service(self) -> SQLFunctionPersistenceService:
        """Get SQL function persistence service"""
        return self.sql_function_service
    
    def get_instruction_service(self) -> InstructionPersistenceService:
        """Get instruction persistence service"""
        return self.instruction_service
    
    def get_knowledge_base_service(self) -> KnowledgeBasePersistenceService:
        """Get knowledge base persistence service"""
        return self.knowledge_base_service
    
    def get_all_services(self) -> Dict[str, Any]:
        """Get all services as a dictionary"""
        return {
            'definition': self.definition_service,
            'project': self.project_service,
            'user_example': self.user_example_service,
            'sql_function': self.sql_function_service,
            'instruction': self.instruction_service,
            'knowledge_base': self.knowledge_base_service
        }


# Example usage and testing
if __name__ == "__main__":
    # Example usage with SessionManager
    # from app.core.session_manager import SessionManager
    # from app.core.settings import ServiceConfig
    # 
    # # Initialize session manager
    # session_manager = SessionManager(ServiceConfig())
    # 
    # # Initialize services
    # project_manager = ProjectManager(None)  # We don't need a session for ProjectManager
    # factory = PersistenceServiceFactory(session_manager, project_manager)
    # 
    # # Use services
    # project_service = factory.get_project_service()
    # kb_service = factory.get_knowledge_base_service()
    # 
    # # Create a project (async)
    # project = Project(
    #     project_id='test_project',
    #     display_name='Test Project',
    #     description='A test project'
    # )
    # project_id = await project_service.persist_project(project, 'admin')
    # 
    # # Add knowledge base entry (async)
    # kb_data = {
    #     'name': 'business_rules',
    #     'display_name': 'Business Rules',
    #     'description': 'Project business rules',
    #     'content': 'All sales must be above $100',
    #     'content_type': 'text'
    # }
    # kb_id = await kb_service.persist_knowledge_base_entry(kb_data, project_id, 'admin')
    # 
    # print(f"Created project: {project_id}")
    # print(f"Created KB entry: {kb_id}")
    
    pass
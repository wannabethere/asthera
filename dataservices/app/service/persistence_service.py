from app.service.models import GeneratedDefinition, DefinitionType, UserExample
from app.utils.history import DomainManager
from app.schemas.dbmodels import (
    Metric, View, CalculatedColumn, SQLColumn, Table, Domain, 
    SQLFunction, Instruction, KnowledgeBase, Example
)
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.session_manager import SessionManager
from sqlalchemy import select
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
import traceback
from app.service.share_permissions import SharePermissions
from fastapi import HTTPException
logger = logging.getLogger(__name__)


class DefinitionPersistenceService:
    """Service for persisting generated definitions to database"""
    
    def __init__(self, session_manager: SessionManager, domain_manager: DomainManager):
        self.session_manager = session_manager
        self.domain_manager = domain_manager
    
    async def persist_definition(self, definition: GeneratedDefinition, 
                               domain_id: str, created_by: str) -> str:
        """Persist generated definition to database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                if definition.definition_type == DefinitionType.METRIC:
                    entity_id = await self._create_metric(session, definition, domain_id, created_by)
                elif definition.definition_type == DefinitionType.VIEW:
                    entity_id = await self._create_view(session, definition, domain_id, created_by)
                elif definition.definition_type == DefinitionType.CALCULATED_COLUMN:
                    entity_id = await self._create_calculated_column(session, definition, domain_id, created_by)
                else:
                    raise ValueError(f"Unknown definition type: {definition.definition_type}")
                
                await session.commit()
                return str(entity_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist definition: {str(e)}")
    
    async def _create_metric(self, session: AsyncSession, definition: GeneratedDefinition, 
                           domain_id: str, created_by: str) -> uuid.UUID:
        """Create metric in database"""
        # Find appropriate table for the metric
        table = await self._find_primary_table(session, definition.related_tables, domain_id)
        
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
    
    async def _create_view(self, session: AsyncSession, definition: GeneratedDefinition, 
                          domain_id: str, created_by: str) -> uuid.UUID:
        """Create view in database"""
        table = await self._find_primary_table(session, definition.related_tables, domain_id)
        
        view = View(
            table_id=table.table_id,
            name=definition.name,
            display_name=definition.display_name,
            description=definition.description,
            view_sql=definition.sql_query,
            view_type=definition.json_metadata.get('view_type', 'custom'),
            modified_by=created_by,
            json_metadata={
                **definition.json_metadata,
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
    
    async def _create_calculated_column(self, session: AsyncSession, definition: GeneratedDefinition, 
                                      domain_id: str, created_by: str) -> uuid.UUID:
        """Create calculated column in database"""
        table = await self._find_primary_table(session, definition.related_tables, domain_id)
        
        # Create the SQLColumn with type 'calculated_column'
        column = SQLColumn(
            table_id=table.table_id,
            name=definition.name,
            display_name=definition.display_name,
            description=definition.description,
            column_type='calculated_column',  # Mark as calculated column
            data_type=definition.json_metadata.get('data_type', 'VARCHAR'),
            usage_type=definition.json_metadata.get('usage_type', 'calculated'),
            is_nullable=definition.json_metadata.get('is_nullable', True),
            is_primary_key=definition.json_metadata.get('is_primary_key', False),
            is_foreign_key=definition.json_metadata.get('is_foreign_key', False),
            default_value=definition.json_metadata.get('default_value'),
            ordinal_position=definition.json_metadata.get('ordinal_position'),
            json_metadata={
                **definition.json_metadata,
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
            function_id=definition.json_metadata.get('function_id',None),
            dependencies=definition.related_columns,
            modified_by=created_by
        )
        
        session.add(calc_column)
        await session.flush()
        return column.column_id
    
    async def _find_primary_table(self, session: AsyncSession, table_names: List[str], domain_id: str) -> Table:
        """Find the primary table for the definition"""
        if not table_names:
            # Default to first table if none specified
            result = await session.execute(
                select(Table).where(Table.domain_id == domain_id).limit(1)
            )
            table = result.scalar_one_or_none()
        else:
            # Use the first mentioned table
            result = await session.execute(
                select(Table).where(
                    Table.domain_id == domain_id,
                    Table.name == table_names[0]
                )
            )
            table = result.scalar_one_or_none()
        
        if not table:
            raise ValueError(f"No suitable table found for definition")
        
        return table


class DomainPersistenceService:
    """Service for persisting domain to database"""
    
    def __init__(self, session_manager: SessionManager, domain_manager: DomainManager):
        self.session_manager = session_manager
        self.domain_manager = domain_manager
        
    async def persist_domain(self, domain: Domain, created_by: str) -> str:
        """Persist domain to database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                # Set the created_by field
                domain.created_by = created_by
                
                # Add to session and commit
                session.add(domain)
                await session.commit()
                
                return domain.domain_id
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist domain: {str(e)}")
    
    async def update_domain(self, domain_id: str, updates: Dict[str, Any], 
                           modified_by: str) -> Domain:
        """Update domain in database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(Domain).where(Domain.domain_id == domain_id)
                )
                domain = result.scalar_one_or_none()
                
                if not domain:
                    raise ValueError(f"Domain {domain_id} not found")
                
                # Update fields
                for key, value in updates.items():
                    if hasattr(domain, key):
                        setattr(domain, key, value)
                
                domain.last_modified_by = modified_by
                domain.updated_at = datetime.utcnow()
                
                await session.commit()
                return domain
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to update domain: {str(e)}")
    
    async def get_domain(self, domain_id: str) -> Optional[Domain]:
        """Get domain by ID"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(Domain).where(Domain.domain_id == domain_id)
            )
            return result.scalar_one_or_none()
    
    async def list_domains(self, status: Optional[str] = None) -> List[Domain]:
        """List domains with optional status filter"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(Domain)
            if status:
                query = query.where(Domain.status == status)
            result = await session.execute(query)
            return result.scalars().all()


class UserExamplePersistenceService:
    """Service for persisting user examples to database"""
    
    def __init__(self, session_manager: SessionManager, domain_manager: DomainManager,
                 sql_pairs_processor=None, instructions_processor=None):
        self.session_manager = session_manager
        self.domain_manager = domain_manager
        self.sql_pairs_processor = sql_pairs_processor
        self.instructions_processor = instructions_processor
    
    async def persist_user_example(self, user_example: UserExample, 
                                 domain_id: str, token: str) -> str:
        """Persist user example to database and optionally index to ChromaDB"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                check_permissions= await SharePermissions().check_user_permission(token, domain_id)
                if not check_permissions:
                    raise HTTPException(status_code=403, detail="User does not have permission to access this domain")
                
                # Convert UserExample to Example model
                example = Example(
                    domain_id=domain_id,
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
                    created_by=user_example.created_by,
                    updated_by=user_example.created_by,
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
                    domain_id=example.domain_id
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
                    domain_id=example.domain_id
                )
                logger.info(f"Indexed instruction to ChromaDB: {example.example_id}")
                
        except Exception as e:
            logger.error(f"Failed to index example to ChromaDB: {str(e)}")
            # Don't raise the exception to avoid failing the database transaction
            # The example is still saved to the database
    
    # async def get_user_examples(self, domain_id: str, 
    #                           definition_type: Optional[DefinitionType] = None,token: str) -> List[Example]:
    #     """Get user examples for a domain"""
    #     async with self.session_manager.get_async_db_session() as session:
    #         query = select(Example)
            
    #         if definition_type:
    #             query = query.where(Example.categories.contains([definition_type.value]))
    #         elif domain_id:
    #             query=query.where(Example.domain_id == domain_id)
            
    #         result = await session.execute(query)
    #         return result.scalars().all()
    async def get_user_examples(self, domain_id: str = None, 
                         definition_type: Optional[DefinitionType] = None, token: str = None) -> List[Example]:
        """Get user examples for a domain or all accessible domains"""
        async with self.session_manager.get_async_db_session() as session:
            
            if domain_id:
                # Check permission for specific domain
                checkPermission = await SharePermissions().check_user_permission(token, domain_id)
                if not checkPermission['has_permission']:
                    raise HTTPException(
                        status_code=403, 
                        detail="User does not have permission to access this domain"
                    )
                
                query = select(Example).where(Example.domain_id == domain_id)
                
                if definition_type:
                    query = query.where(Example.categories.contains([definition_type.value]))
                
                result = await session.execute(query)
                return result.scalars().all()
            else:
                # Get all accessible domain_ids for user
                user_datasets = await SharePermissions().get_user_domains(token)
                accessible_domain_ids = set()
                
                # Collect domain_ids from owned datasets
                for dataset in user_datasets.get("my_datasets", []):
                    if "project_info" in dataset and "domain_id" in dataset["project_info"]:
                        accessible_domain_ids.add(dataset["project_info"]["domain_id"])
                
                # Collect domain_ids from shared datasets
                for dataset in user_datasets.get("shared_datasets", []):
                    if "project_info" in dataset and "domain_id" in dataset["project_info"]:
                        accessible_domain_ids.add(dataset["project_info"]["domain_id"])
                
                if not accessible_domain_ids:
                    return []
                
                # Get examples for all accessible domains
                query = select(Example).where(Example.domain_id.in_(accessible_domain_ids))
                
                if definition_type:
                    query = query.where(Example.categories.contains([definition_type.value]))
                
                result = await session.execute(query)
                return result.scalars().all()
    
    async def get_user_example_by_id(self, example_id: str,token: str) -> Optional[Example]:
        """Get user example by ID"""
        
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(Example).where(Example.example_id == example_id)
            )
            result = result.scalar_one_or_none()
            domain_id=result.domain_id
            check_permissions=await SharePermissions().check_user_permission(token, domain_id)
            if not check_permissions:
                raise HTTPException(status_code=403, detail="User does not have permission to access this domain")
            
            
            return result
    
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
    
    def __init__(self, session_manager: SessionManager, domain_manager: DomainManager):
        self.session_manager = session_manager
        self.domain_manager = domain_manager
    
    async def persist_sql_function(self, function_data: Dict[str, Any], 
                                 created_by: str, domain_id: Optional[str] = None) -> str:
        """Persist SQL function to database with optional domain_id"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                print(f"Entered Persistent SQL Function with {function_data}")

                sql_function = SQLFunction(
                    domain_id=domain_id,
                    name=function_data['name'],
                    display_name=function_data.get('display_name'),
                    description=function_data.get('description'),
                    function_sql=function_data['function_sql'],
                    return_type=function_data.get('return_type'),
                    parameters=function_data.get('parameters', []),
                    modified_by=created_by,
                    json_metadata=function_data.get('json_metadata', {})
                )
                
                session.add(sql_function)
                await session.commit()
                print(f"After SQL FUnction commit ")
                
                return str(sql_function.function_id)
                
            except Exception as e:
                print("======================= Error in Persistent SQL Function started ========================")
                traceback.print_exc()
                print("========================== Error ended here ====================")
                await session.rollback()
                raise Exception(f"Failed to persist SQL function: {str(e)}")
    
    async def persist_sql_functions_batch(self, functions_data: List[Dict[str, Any]], 
                                        created_by: str, domain_id: Optional[str] = None) -> List[str]:
        """Persist multiple SQL functions in batch with optional domain_id"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                function_ids = []
                
                for function_data in functions_data:
                    sql_function = SQLFunction(
                        domain_id=domain_id,
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
    
    async def get_sql_functions(self, domain_id: Optional[str] = None) -> List[SQLFunction]:
        """Get all SQL functions, optionally filtered by domain_id"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(SQLFunction)
            if domain_id:
                query = query.where(SQLFunction.domain_id == domain_id)
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_sql_functions_by_name(self, name: str, domain_id: Optional[str] = None) -> List[SQLFunction]:
        """Get SQL functions by name, optionally filtered by domain_id"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(SQLFunction).where(SQLFunction.name == name)
            if domain_id:
                query = query.where(SQLFunction.domain_id == domain_id)
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
        """Get all SQL functions that are not associated with any domain (global functions)"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(SQLFunction).where(SQLFunction.domain_id.is_(None))
            )
            return result.scalars().all()
    
    async def search_sql_functions(self, search_term: str, domain_id: Optional[str] = None) -> List[SQLFunction]:
        """Search SQL functions by name or description"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(SQLFunction).where(
                (SQLFunction.name.ilike(f"%{search_term}%")) |
                (SQLFunction.description.ilike(f"%{search_term}%"))
            )
            if domain_id:
                query = query.where(SQLFunction.domain_id == domain_id)
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
    
    async def get_sql_function_summary(self, domain_id: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of SQL functions for a domain or globally"""
        functions = await self.get_sql_functions(domain_id)
        
        summary = {
            'total_functions': len(functions),
            'domain_id': domain_id,
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
    
    async def copy_sql_function_to_domain(self, function_id: str, target_domain_id: str, 
                                         created_by: str) -> str:
        """Copy a SQL function to another domain"""
        try:
            source_function = await self.get_sql_function(function_id)
            if not source_function:
                raise ValueError(f"SQL Function {function_id} not found")
            
            # Create a copy with new domain_id
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
            
            return await self.persist_sql_function(function_data, created_by, target_domain_id)
            
        except Exception as e:
            raise Exception(f"Failed to copy SQL function: {str(e)}")


class InstructionPersistenceService:
    """Service for persisting instructions to database"""
    
    def __init__(self, session_manager: SessionManager, domain_manager: DomainManager):
        self.session_manager = session_manager
        self.domain_manager = domain_manager
    
    async def persist_instruction(self, instruction_data: Dict[str, Any], 
                                domain_id: str, created_by: str,token:str) -> str:
        """Persist instruction to database"""
        checkPermission = await SharePermissions().check_user_permission(token, domain_id)
        
        if not checkPermission['has_permission']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have permission to access this domain"
            )
        
        async with self.session_manager.get_async_db_session() as session:
            try:
                instruction = Instruction(
                    domain_id=domain_id,
                    question=instruction_data['question'],
                    instructions=instruction_data['instructions'],
                    sql_query=instruction_data['sql_query'],
                    chain_of_thought=instruction_data.get('chain_of_thought'),
                    modified_by=created_by,
                    json_metadata=instruction_data.get('json_metadata', {}),
                    created_by=created_by,
                    updated_by=created_by

                )
                
                session.add(instruction)
                await session.commit()
                
                return str(instruction.instruction_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist instruction: {str(e)}")
    
    async def persist_instructions_batch(self, instructions_data: List[Dict[str, Any]], 
                                       domain_id: str, created_by: str) -> List[str]:
        """Persist multiple instructions in batch"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                instruction_ids = []
                
                for instruction_data in instructions_data:
                    instruction = Instruction(
                        domain_id=domain_id,
                        question=instruction_data['question'],
                        instructions=instruction_data['instructions'],
                        sql_query=instruction_data['sql_query'],
                        chain_of_thought=instruction_data.get('chain_of_thought'),
                        modified_by=created_by,
                        json_metadata=instruction_data.get('json_metadata', {})
                    )
                    
                    session.add(instruction)
                    instruction_ids.append(instruction)
                
                await session.commit()
                
                return [str(instruction.instruction_id) for instruction in instruction_ids]
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist instructions batch: {str(e)}")
    
    async def get_instructions(self, domain_id: str=None, token: str=None) -> List[Instruction]:
        """Get all instructions for a domain or all accessible domains"""
        async with self.session_manager.get_async_db_session() as session:
            
            if domain_id:
                result = await session.execute(
                    select(Instruction).where(Instruction.domain_id == domain_id)
                )
                return result.scalars().all()
            else:
                
                user_datasets = await SharePermissions().get_user_domains(token)
                accessible_domain_ids = set()
                
                # Collect domain_ids from owned datasets
                for dataset in user_datasets.get("my_datasets", []):
                    if "project_info" in dataset and "domain_id" in dataset["project_info"]:
                        accessible_domain_ids.add(dataset["project_info"]["domain_id"])
                
                # Collect domain_ids from shared datasets
                for dataset in user_datasets.get("shared_datasets", []):
                    if "project_info" in dataset and "domain_id" in dataset["project_info"]:
                        accessible_domain_ids.add(dataset["project_info"]["domain_id"])
                
                if not accessible_domain_ids:
                    return []
                
                # Get instructions for all accessible domains
                result = await session.execute(
                    select(Instruction).where(Instruction.domain_id.in_(accessible_domain_ids))
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
    
    async def delete_instruction(self, instruction_id: str,token) -> bool:
        """Delete instruction"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                result = await session.execute(
                    select(Instruction).where(Instruction.instruction_id == instruction_id)
                )
                instruction = result.scalar_one_or_none()
                domain_id=instruction.domain_id
                checkPermission = await SharePermissions().check_user_permission(token,domain_id)
                if not checkPermission['has_permission']:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="User does not have permission to access this domain"
                    )
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
    
    def __init__(self, session_manager: SessionManager, domain_manager: DomainManager):
        self.session_manager = session_manager
        self.domain_manager = domain_manager
    
    async def persist_knowledge_base_entry(self, kb_data: Dict[str, Any], 
                                         domain_id: str, created_by: str) -> str:
        """Persist knowledge base entry to database"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                kb_entry = KnowledgeBase(
                    domain_id=domain_id,
                    name=kb_data['name'],
                    display_name=kb_data.get('display_name'),
                    description=kb_data.get('description'),
                    file_path=kb_data.get('file_path'),
                    content_type=kb_data.get('content_type', 'text'),
                    content=kb_data.get('content'),
                    modified_by=created_by,
                    json_metadata=kb_data.get('json_metadata', {})
                )
                
                session.add(kb_entry)
                await session.commit()
                
                return str(kb_entry.kb_id)
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist knowledge base entry: {str(e)}")
    
    async def persist_knowledge_base_batch(self, kb_entries_data: List[Dict[str, Any]], 
                                         domain_id: str, created_by: str) -> List[str]:
        """Persist multiple knowledge base entries in batch"""
        async with self.session_manager.get_async_db_session() as session:
            try:
                kb_ids = []
                
                for kb_data in kb_entries_data:
                    kb_entry = KnowledgeBase(
                        domain_id=domain_id,
                        name=kb_data['name'],
                        display_name=kb_data.get('display_name'),
                        description=kb_data.get('description'),
                        file_path=kb_data.get('file_path'),
                        content_type=kb_data.get('content_type', 'text'),
                        content=kb_data.get('content'),
                        modified_by=created_by,
                        json_metadata=kb_data.get('json_metadata', {})
                    )
                    
                    session.add(kb_entry)
                    kb_ids.append(kb_entry)
                
                await session.commit()
                
                return [str(kb_entry.kb_id) for kb_entry in kb_ids]
                
            except Exception as e:
                await session.rollback()
                raise Exception(f"Failed to persist knowledge base batch: {str(e)}")
    
    async def get_knowledge_base_entries(self, domain_id: str, 
                                       content_type: Optional[str] = None) -> List[KnowledgeBase]:
        """Get knowledge base entries for a domain"""
        async with self.session_manager.get_async_db_session() as session:
            query = select(KnowledgeBase).where(KnowledgeBase.domain_id == domain_id)
            
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
    
    async def search_knowledge_base(self, domain_id: str, search_term: str) -> List[KnowledgeBase]:
        """Search knowledge base entries by content"""
        async with self.session_manager.get_async_db_session() as session:
            result = await session.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.domain_id == domain_id,
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
    
    async def get_knowledge_base_summary(self, domain_id: str) -> Dict[str, Any]:
        """Get summary of knowledge base for a domain"""
        entries = await self.get_knowledge_base_entries(domain_id)
        
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
    
    def __init__(self, session_manager: SessionManager, domain_manager: DomainManager,
                 sql_pairs_processor=None, instructions_processor=None):
        self.session_manager = session_manager
        self.domain_manager = domain_manager
        self.sql_pairs_processor = sql_pairs_processor
        self.instructions_processor = instructions_processor
        
        # Initialize all services
        self.definition_service = DefinitionPersistenceService(session_manager, domain_manager)
        self.domain_service = DomainPersistenceService(session_manager, domain_manager)
        self.user_example_service = UserExamplePersistenceService(
            session_manager, domain_manager, sql_pairs_processor, instructions_processor
        )
        self.sql_function_service = SQLFunctionPersistenceService(session_manager, domain_manager)
        self.instruction_service = InstructionPersistenceService(session_manager, domain_manager)
        self.knowledge_base_service = KnowledgeBasePersistenceService(session_manager, domain_manager)
    
    def get_definition_service(self) -> DefinitionPersistenceService:
        """Get definition persistence service"""
        return self.definition_service
    
    def get_domain_service(self) -> DomainPersistenceService:
        """Get domain persistence service"""
        return self.domain_service
    
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
            'domain': self.domain_service,
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
    # domain_manager = DomainManager(None)  # We don't need a session for DomainManager
    # factory = PersistenceServiceFactory(session_manager, domain_manager)
    # 
    # # Use services
    # domain_service = factory.get_domain_service()
    # kb_service = factory.get_knowledge_base_service()
    # 
    # # Create a domain (async)
    # domain = Domain(
    #     domain_id='test_domain',
    #     display_name='Test Domain',
    #     description='A test domain'
    # )
    # domain_id = await domain_service.persist_domain(domain, 'admin')
    # 
    # # Add knowledge base entry (async)
    # kb_data = {
    #     'name': 'business_rules',
    #     'display_name': 'Business Rules',
    #     'description': 'Domain business rules',
    #     'content': 'All sales must be above $100',
    #     'content_type': 'text'
    # }
    # kb_id = await kb_service.persist_knowledge_base_entry(kb_data, domain_id, 'admin')
    # 
    # print(f"Created domain: {domain_id}")
    # print(f"Created KB entry: {kb_id}")
    
    pass
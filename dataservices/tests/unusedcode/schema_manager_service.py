from app.service.models import ProjectContext,DocumentedTable
from app.service.project_management_service import ProjectManager
from app.agents.schema_manager import LLMSchemaDocumentationGenerator
from app.utils.parser import SchemaParser
import datetime
from sqlalchemy.orm import Session
from app.schemas.dbmodels import Table, SQLColumn as Columns
from typing import List, Dict, Any,Optional
# ===============================================
# =============================
# SCHEMA DOCUMENTATION SERVICE
# ============================================================================

class SchemaDocumentationService:
    """Main service for schema documentation"""
    
    def __init__(self, session: Session, llm, project_id: str):
        self.session = session
        self.project_id = project_id
        self.project_manager = ProjectManager(session)
        self.llm_generator = LLMSchemaDocumentationGenerator(llm)
        self.schema_parser = SchemaParser()
    
    async def document_schema_from_ddl(self, ddl_statement: str, 
                                     project_context: ProjectContext) -> DocumentedTable:
        """Document schema from DDL statement"""
        schema_input = self.schema_parser.parse_ddl(ddl_statement)
        return await self.llm_generator.document_table_schema(schema_input, project_context)
    
    async def document_existing_table(self, table_name: str, 
                                    project_context: ProjectContext,
                                    include_sample_data: bool = False) -> DocumentedTable:
        """Document existing table in database"""
        # Get table from database
        table = self.session.query(Table).filter(
            Table.project_id == self.project_id,
            Table.name == table_name
        ).first()
        
        if not table:
            raise ValueError(f"Table {table_name} not found in project {self.project_id}")
        
        # Convert to schema input
        schema_input = self.schema_parser.parse_sqlalchemy_table(table)
        
        # Optionally include sample data
        if include_sample_data:
            schema_input.sample_data = await self._get_sample_data(table_name)
        
        return await self.llm_generator.document_table_schema(schema_input, project_context)
    
    async def document_schema_from_jsons(self, schema_json: Dict[str, Any],
                                      project_context: ProjectContext) -> DocumentedTable:
        """Document schema from JSON definition"""
        schema_input = self.schema_parser.parse_json_schema(schema_json)
        return await self.llm_generator.document_table_schema(schema_input, project_context)
    
    async def batch_document_project_tables(self, project_context: ProjectContext,
                                          table_names: Optional[List[str]] = None) -> List[DocumentedTable]:
        """Document all or specified tables in a project"""
        # Get tables to document
        query = self.session.query(Table).filter(Table.project_id == self.project_id)
        if table_names:
            query = query.filter(Table.name.in_(table_names))
        
        tables = query.all()
        
        if not tables:
            raise ValueError(f"No tables found in project {self.project_id}")
        
        # Document each table
        documented_tables = []
        for table in tables:
            try:
                schema_input = self.schema_parser.parse_sqlalchemy_table(table)
                documented_table = await self.llm_generator.document_table_schema(
                    schema_input, project_context
                )
                documented_tables.append(documented_table)
            except Exception as e:
                print(f"Warning: Failed to document table {table.name}: {str(e)}")
        
        return documented_tables
    
    async def update_database_with_documentation(self, documented_table: DocumentedTable) -> bool:
        """Update database with generated documentation"""
        try:
            # Update table documentation
            table = self.session.query(Table).filter(
                Table.project_id == self.project_id,
                Table.name == documented_table.table_name
            ).first()
            
            if not table:
                return False
            
            table.display_name = documented_table.display_name
            table.description = documented_table.description
            table.metadata = {
                **(table.metadata or {}),
                'business_purpose': documented_table.business_purpose,
                'primary_use_cases': documented_table.primary_use_cases,
                'key_relationships': documented_table.key_relationships,
                'data_lineage': documented_table.data_lineage,
                'update_frequency': documented_table.update_frequency,
                'data_retention': documented_table.data_retention,
                'access_patterns': documented_table.access_patterns,
                'performance_considerations': documented_table.performance_considerations,
                'documentation_generated_at': datetime.utcnow().isoformat(),
                'documentation_source': 'llm_schema_service'
            }
            
            # Update column documentation
            for col_doc in documented_table.columns:
                column = self.session.query(Columns).filter(
                    Columns.table_id == table.table_id,
                    Columns.name == col_doc.column_name
                ).first()
                
                if column:
                    column.display_name = col_doc.display_name
                    column.description = col_doc.description
                    column.usage_type = col_doc.usage_type.value
                    column.metadata = {
                        **(column.metadata or {}),
                        'business_description': col_doc.business_description,
                        'example_values': col_doc.example_values,
                        'business_rules': col_doc.business_rules,
                        'data_quality_checks': col_doc.data_quality_checks,
                        'related_concepts': col_doc.related_concepts,
                        'privacy_classification': col_doc.privacy_classification,
                        'aggregation_suggestions': col_doc.aggregation_suggestions,
                        'filtering_suggestions': col_doc.filtering_suggestions,
                        'documentation_metadata': col_doc.metadata,
                        'documentation_generated_at': datetime.utcnow().isoformat()
                    }
            
            self.session.commit()
            return True
            
        except Exception as e:
            self.session.rollback()
            raise Exception(f"Failed to update database with documentation: {str(e)}")
    
    async def _get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample data from table"""
        try:
            # This is a simplified version - in production, use proper query building
            query = text(f"SELECT * FROM {table_name} LIMIT {limit}")
            result = self.session.execute(query)
            
            sample_data = []
            for row in result:
                sample_data.append(dict(row._mapping))
            
            return sample_data
        except Exception as e:
            print(f"Warning: Could not fetch sample data for {table_name}: {str(e)}")
            return []
        

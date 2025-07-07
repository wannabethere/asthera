# Persistence Services Documentation

This document describes the comprehensive persistence services available for managing project data, user examples, SQL functions, instructions, and knowledge base entries.

## Overview

The persistence services provide a clean, type-safe interface for database operations with automatic versioning, error handling, and transaction management. All services are designed to work with the project versioning system.

## Services Available

### 1. ProjectPersistenceService
Manages project creation, updates, and retrieval.

### 2. UserExamplePersistenceService  
Handles user-provided examples for creating definitions (metrics, views, calculated columns).

### 3. SQLFunctionPersistenceService
Manages reusable SQL functions within projects.

### 4. InstructionPersistenceService
Handles project-specific instructions and guidelines.

### 5. KnowledgeBasePersistenceService
Manages knowledge base entries with search and summary capabilities.

### 6. DefinitionPersistenceService
Handles generated definitions (metrics, views, calculated columns).

## Quick Start

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.service.persistence_service import PersistenceServiceFactory
from app.utils.history import ProjectManager

# Setup database connection
engine = create_engine('postgresql://user:password@localhost/project_db')
Session = sessionmaker(bind=engine)
session = Session()

# Initialize services
project_manager = ProjectManager(session)
factory = PersistenceServiceFactory(session, project_manager)

# Get specific services
project_service = factory.get_project_service()
kb_service = factory.get_knowledge_base_service()
```

## Service Details

### ProjectPersistenceService

**Methods:**
- `persist_project(project: Project, created_by: str) -> str`
- `update_project(project_id: str, updates: Dict[str, Any], modified_by: str) -> Project`
- `get_project(project_id: str) -> Optional[Project]`
- `list_projects(status: Optional[str] = None) -> List[Project]`

**Example:**
```python
from app.schemas.dbmodels import Project

# Create a project
project = Project(
    project_id='sales_analytics',
    display_name='Sales Analytics Project',
    description='Comprehensive sales analysis and reporting'
)
project_id = project_service.persist_project(project, 'admin')

# Update project
updates = {'description': 'Updated description'}
updated_project = project_service.update_project(project_id, updates, 'admin')
```

### UserExamplePersistenceService

**Methods:**
- `persist_user_example(user_example: UserExample, project_id: str) -> str`
- `get_user_examples(project_id: str, definition_type: Optional[DefinitionType] = None) -> List[Example]`
- `update_user_example(example_id: str, updates: Dict[str, Any], modified_by: str) -> Example`
- `delete_user_example(example_id: str) -> bool`

**Example:**
```python
from app.service.models import UserExample, DefinitionType

# Create user example
user_example = UserExample(
    definition_type=DefinitionType.METRIC,
    name='monthly_revenue',
    description='Calculate monthly revenue from sales table',
    sql='SELECT DATE_TRUNC(\'month\', sale_date) as month, SUM(amount) as revenue FROM sales GROUP BY month',
    user_id='analyst1'
)
example_id = user_example_service.persist_user_example(user_example, 'sales_analytics')

# Get examples by type
metric_examples = user_example_service.get_user_examples('sales_analytics', DefinitionType.METRIC)
```

### SQLFunctionPersistenceService

**Methods:**
- `persist_sql_function(function_data: Dict[str, Any], project_id: str, created_by: str) -> str`
- `get_sql_functions(project_id: str) -> List[SQLFunction]`
- `get_sql_function(function_id: str) -> Optional[SQLFunction]`
- `update_sql_function(function_id: str, updates: Dict[str, Any], modified_by: str) -> SQLFunction`
- `delete_sql_function(function_id: str) -> bool`

**Example:**
```python
# Create SQL function
function_data = {
    'name': 'calculate_discount',
    'display_name': 'Calculate Discount',
    'description': 'Calculate discount based on customer tier',
    'function_sql': '''
        CREATE OR REPLACE FUNCTION calculate_discount(amount DECIMAL, tier VARCHAR)
        RETURNS DECIMAL AS $$
        BEGIN
            CASE tier
                WHEN 'gold' THEN RETURN amount * 0.15;
                WHEN 'silver' THEN RETURN amount * 0.10;
                ELSE RETURN amount * 0.05;
            END CASE;
        END;
        $$ LANGUAGE plpgsql;
    ''',
    'return_type': 'DECIMAL',
    'parameters': [
        {'name': 'amount', 'type': 'DECIMAL'},
        {'name': 'tier', 'type': 'VARCHAR'}
    ]
}
function_id = sql_function_service.persist_sql_function(function_data, 'sales_analytics', 'admin')
```

### InstructionPersistenceService

**Methods:**
- `persist_instruction(instruction_data: Dict[str, Any], project_id: str, created_by: str) -> str`
- `persist_instructions_batch(instructions_data: List[Dict[str, Any]], project_id: str, created_by: str) -> List[str]`
- `get_instructions(project_id: str) -> List[Instruction]`
- `get_instruction(instruction_id: str) -> Optional[Instruction]`
- `update_instruction(instruction_id: str, updates: Dict[str, Any], modified_by: str) -> Instruction`
- `delete_instruction(instruction_id: str) -> bool`

**Example:**
```python
# Create instruction
instruction_data = {
    'question': 'How to calculate customer lifetime value?',
    'instructions': 'Use the customer_orders table and aggregate by customer_id',
    'sql_query': 'SELECT customer_id, SUM(order_amount) as clv FROM customer_orders GROUP BY customer_id',
    'chain_of_thought': 'CLV is calculated by summing all order amounts per customer'
}
instruction_id = instruction_service.persist_instruction(instruction_data, 'sales_analytics', 'admin')

# Batch create instructions
instructions_batch = [
    {
        'question': 'Revenue by region',
        'instructions': 'Group sales by region and sum amounts',
        'sql_query': 'SELECT region, SUM(amount) FROM sales GROUP BY region'
    },
    {
        'question': 'Top customers',
        'instructions': 'Find customers with highest total purchases',
        'sql_query': 'SELECT customer_id, SUM(amount) FROM sales GROUP BY customer_id ORDER BY SUM(amount) DESC LIMIT 10'
    }
]
instruction_ids = instruction_service.persist_instructions_batch(instructions_batch, 'sales_analytics', 'admin')
```

### KnowledgeBasePersistenceService

**Methods:**
- `persist_knowledge_base_entry(kb_data: Dict[str, Any], project_id: str, created_by: str) -> str`
- `persist_knowledge_base_batch(kb_entries_data: List[Dict[str, Any]], project_id: str, created_by: str) -> List[str]`
- `get_knowledge_base_entries(project_id: str, content_type: Optional[str] = None) -> List[KnowledgeBase]`
- `get_knowledge_base_entry(kb_id: str) -> Optional[KnowledgeBase]`
- `search_knowledge_base(project_id: str, search_term: str) -> List[KnowledgeBase]`
- `update_knowledge_base_entry(kb_id: str, updates: Dict[str, Any], modified_by: str) -> KnowledgeBase`
- `delete_knowledge_base_entry(kb_id: str) -> bool`
- `get_knowledge_base_summary(project_id: str) -> Dict[str, Any]`

**Example:**
```python
# Create knowledge base entry
kb_data = {
    'name': 'business_rules',
    'display_name': 'Business Rules',
    'description': 'Project-specific business rules and constraints',
    'content': '''
    Business Rules:
    1. All sales must be above $10
    2. Customer discounts cannot exceed 25%
    3. Orders must have valid customer_id
    4. Product prices must be positive
    ''',
    'content_type': 'text',
    'metadata': {
        'category': 'rules',
        'priority': 'high',
        'last_reviewed': '2024-01-15'
    }
}
kb_id = kb_service.persist_knowledge_base_entry(kb_data, 'sales_analytics', 'admin')

# Search knowledge base
search_results = kb_service.search_knowledge_base('sales_analytics', 'discount')

# Get summary
summary = kb_service.get_knowledge_base_summary('sales_analytics')
print(f"Total entries: {summary['total_entries']}")
print(f"Content types: {summary['content_types']}")
```

## Error Handling

All services include comprehensive error handling with:
- Automatic transaction rollback on errors
- Detailed error messages
- Proper exception propagation

```python
try:
    project_id = project_service.persist_project(project, 'admin')
except Exception as e:
    print(f"Failed to persist project: {e}")
    # Handle error appropriately
```

## Version Management

All services integrate with the project versioning system:
- Automatic version increments when entities are modified
- Version history tracking
- Version locking support

## Best Practices

1. **Use the Factory**: Always use `PersistenceServiceFactory` to get service instances
2. **Error Handling**: Wrap service calls in try-catch blocks
3. **Batch Operations**: Use batch methods for multiple operations
4. **Metadata**: Leverage metadata fields for additional context
5. **Search**: Use search capabilities for knowledge base queries

## Testing

```python
# Example test setup
def test_project_persistence():
    session = create_test_session()
    project_manager = ProjectManager(session)
    factory = PersistenceServiceFactory(session, project_manager)
    
    project_service = factory.get_project_service()
    
    # Test project creation
    project = Project(project_id='test', display_name='Test')
    project_id = project_service.persist_project(project, 'test_user')
    
    assert project_id == 'test'
    
    # Test project retrieval
    retrieved_project = project_service.get_project(project_id)
    assert retrieved_project.display_name == 'Test'
```

## Dependencies

- SQLAlchemy for ORM
- PostgreSQL for database
- Pydantic for data validation
- UUID for ID generation
- Datetime for timestamps

## Migration Notes

When updating existing code:
1. Replace direct database operations with service calls
2. Use the factory pattern for service instantiation
3. Update error handling to use service exceptions
4. Leverage batch operations for better performance 
# Relationship Workflow Management

## Overview

The Relationship Workflow Management system is a new workflow step that occurs after table creation in the domain workflow. This step leverages the existing **RelationshipRecommendation service** to analyze all tables in the workflow and generate relationship recommendations. It is essential for creating the MDL (Model Definition Language) schema as it allows users to:

1. **Get LLM-generated relationship recommendations** for all tables in the workflow using the existing service
2. **Add custom relationships** based on business knowledge
3. **Manage and validate relationships** before committing to the database
4. **Prepare the workflow** for MDL schema generation

## Why This Step is Important

Relationships cannot be created during table creation because:
- **Multiple tables are needed** to define relationships
- **Business context is required** to understand table relationships
- **LLM analysis** needs to see all tables to generate meaningful recommendations
- **MDL schema generation** depends on complete relationship definitions

## Integration with Existing Services

This workflow step **reuses the existing RelationshipRecommendation service** rather than creating duplicate functionality:

- **Leverages existing LLM prompts** and relationship analysis logic
- **Uses the same MDL input format** that the service expects
- **Maintains consistency** with other relationship recommendation endpoints
- **Reduces code duplication** and maintenance overhead

The workflow step simply:
1. **Builds an MDL representation** from the workflow tables
2. **Calls the existing service** with the MDL data
3. **Processes the response** into workflow-friendly format
4. **Manages the workflow state** for relationship storage

## Workflow Sequence

```
1. Create Domain
   ↓
2. Add Tables (one by one)
   ↓
3. 🔗 RELATIONSHIP WORKFLOW STEP ← NEW!
   ↓
4. Commit Workflow to Database
   ↓
5. Generate MDL Schema
```

## Relationship Workflow Management Process

The relationship workflow step follows this process:

### **Step 1: Initialize Workflow Management**
```http
POST /workflow/relationships/manage
```
- Automatically generates LLM recommendations if none exist
- Returns current workflow state and available actions
- Sets up the workflow for relationship management

### **Step 2: Review LLM Recommendations**
- Examine automatically generated relationships
- Understand confidence scores and reasoning
- Identify high-priority relationships to implement

### **Step 3: Add Custom Relationships**
```http
POST /workflow/relationships/custom
```
- Add business-specific relationships not detected by LLM
- Define custom relationship types and descriptions
- Set business justification and implementation notes

### **Step 4: Edit and Update Relationships**
```http
PUT /workflow/relationships/update
```
- Modify relationship details (description, confidence, reasoning)
- Update relationship types or column mappings
- Add business context and implementation notes

### **Step 5: Remove Unwanted Relationships**
```http
DELETE /workflow/relationships/{relationship_id}
```
- Remove relationships that don't fit business requirements
- Clean up test or temporary relationships
- Maintain workflow consistency

### **Step 6: Batch Operations (Optional)**
```http
POST /workflow/relationships/batch-operations
```
- Perform multiple operations in a single request
- Efficiently manage large numbers of relationships
- Reduce API calls for bulk operations

### **Step 7: Validate Workflow**
```http
POST /workflow/relationships/validate/{domain_id}
```
- Check relationship validity and consistency
- Verify table references exist
- Ensure proper relationship types

### **Step 8: Commit Workflow**
- Save all relationships to the workflow state
- Prepare for database commit
- Generate MDL schema with defined relationships

## API Endpoints

### Base URL
```
/workflow/relationships
```

### Endpoints

#### 1. Generate Relationship Recommendations
```http
POST /workflow/relationships/recommendations
```
Generates comprehensive relationship recommendations for all tables in the workflow using LLM analysis.

**Request Body:**
```json
{
  "session_id": "optional_session_id",
  "domain_id": "your_domain_id",
  "domain_name": "Your Domain Name",
  "business_domain": "Your Business Domain"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Successfully generated relationship recommendations",
  "data": {
    "domain_id": "your_domain_id",
    "total_tables": 5,
    "cross_table_relationships": [...],
    "summary": {
      "total_relationships": 8,
      "high_priority_relationships": [...],
      "medium_priority_relationships": [...],
      "low_priority_relationships": [...],
      "recommendations": [...]
    }
  }
}
```

#### 2. Add Custom Relationship
```http
POST /workflow/relationships/custom
```
Allows users to manually define relationships that may not be detected by LLM analysis.

**Request Body:**
```json
{
  "from_table": "orders",
  "to_table": "customers",
  "relationship_type": "many_to_one",
  "from_column": "customer_id",
  "to_column": "customer_id",
  "name": "orders_to_customers",
  "description": "Orders belong to customers",
  "confidence_score": 1.0,
  "reasoning": "Business rule: Orders must have a customer",
  "business_justification": "Core business model requirement"
}
```

#### 3. Get Workflow Relationships
```http
GET /workflow/relationships/workflow?domain_id={domain_id}&session_id={session_id}
```
Retrieves all relationships currently defined in the workflow.

#### 4. Update Relationship
```http
PUT /workflow/relationships/update
```
Updates an existing relationship in the workflow.

#### 5. Remove Relationship
```http
DELETE /workflow/relationships/{relationship_id}?domain_id={domain_id}&session_id={session_id}
```
Removes a relationship from the workflow.

#### 6. Get Workflow Status
```http
GET /workflow/relationships/status/{domain_id}?session_id={session_id}
```
Provides information about the current progress of the relationship workflow step.

#### 7. Validate Workflow
```http
POST /workflow/relationships/validate/{domain_id}?session_id={session_id}
```
Performs validation checks on the relationships defined in the workflow.

#### 8. Manage Relationships Workflow (Main Endpoint)
```http
POST /workflow/relationships/manage
```
**Main endpoint for relationship workflow management.** This provides a comprehensive workflow that:
- Generates LLM recommendations if not already available
- Returns current relationships and recommendations
- Provides available actions and next steps
- Sets up the workflow for relationship management

**Request Body:**
```json
{
  "session_id": "optional_session_id",
  "domain_id": "your_domain_id",
  "domain_name": "Your Domain Name",
  "business_domain": "Your Business Domain"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Relationship workflow ready for management",
  "data": {
    "domain_id": "your_domain_id",
    "workflow_status": "ready_for_management",
    "current_state": {
      "relationships": [...],
      "recommendations": {...},
      "summary": {...}
    },
    "available_actions": [
      "generate_recommendations",
      "add_custom_relationship",
      "update_relationship",
      "remove_relationship",
      "validate_workflow",
      "commit_workflow"
    ],
    "next_steps": [
      "Review LLM-generated recommendations",
      "Add custom relationships if needed",
      "Update relationship details",
      "Validate all relationships",
      "Commit workflow when ready"
    ]
  }
}
```

#### 9. Batch Operations
```http
POST /workflow/relationships/batch-operations
```
Perform multiple relationship operations (add, update, delete) in a single request for efficiency.

**Request Body:**
```json
{
  "workflow_request": {
    "domain_id": "your_domain_id"
  },
  "operations": [
    {
      "action": "add",
      "data": {
        "from_table": "orders",
        "to_table": "customers",
        "relationship_type": "many_to_one"
      }
    },
    {
      "action": "update",
      "relationship_id": "rel_123",
      "data": {
        "description": "Updated description"
      }
    },
    {
      "action": "delete",
      "relationship_id": "rel_456"
    }
  ]
}
```

## Usage Examples

### Python Example

```python
import asyncio
from app.service.project_workflow_service import DomainWorkflowService
from app.service.models import DomainContext

async def manage_relationships():
    # Create workflow service
    workflow_service = DomainWorkflowService(
        user_id="your_user_id",
        session_id="your_session_id"
    )
    
    # Create domain context
    domain_context = DomainContext(
        domain_id="your_domain_id",
        domain_name="Your Domain",
        business_domain="Your Business Domain",
        purpose="Your domain purpose",
        target_users=["Data Analysts", "Business Users"],
        key_business_concepts=["Data Analysis", "Business Intelligence"]
    )
    
    # Step 1: Generate recommendations using existing RelationshipRecommendation service
    # This internally builds MDL from workflow tables and calls the existing service
    recommendations = await workflow_service.get_comprehensive_relationship_recommendations(
        domain_context
    )
    
    print(f"Generated {recommendations['summary']['total_relationships']} recommendations")
    print(f"Using existing service: {recommendations.get('source', 'unknown')}")
    
    # Step 2: Add custom relationship
    custom_rel = await workflow_service.add_custom_relationship({
        "from_table": "orders",
        "to_table": "customers",
        "relationship_type": "many_to_one",
        "from_column": "customer_id",
        "to_column": "customer_id",
        "description": "Orders belong to customers"
    }, domain_context)
    
    # Step 3: Get workflow status
    status = await workflow_service.get_workflow_relationships()
    print(f"Total relationships: {status['summary']['total_relationships']}")

# Run the example
asyncio.run(manage_relationships())
```

### Complete Workflow Management Example

```python
import asyncio
import requests

async def complete_relationship_workflow():
    """Complete example using the workflow management endpoints"""
    
    base_url = "http://localhost:8000/workflow/relationships"
    headers = {"Authorization": "Bearer YOUR_TOKEN"}
    
    # Step 1: Initialize workflow management
    manage_response = requests.post(
        f"{base_url}/manage",
        json={
            "domain_id": "your_domain_id",
            "domain_name": "Your Domain",
            "business_domain": "Your Business Domain"
        },
        headers=headers
    )
    
    if manage_response.status_code == 200:
        workflow_data = manage_response.json()["data"]
        print(f"Workflow Status: {workflow_data['workflow_status']}")
        print(f"Available Actions: {workflow_data['available_actions']}")
        
        # Step 2: Add custom relationships
        custom_rel = requests.post(
            f"{base_url}/custom",
            json={
                "workflow_request": {"domain_id": "your_domain_id"},
                "request": {
                    "from_table": "orders",
                    "to_table": "customers",
                    "relationship_type": "many_to_one",
                    "description": "Orders belong to customers"
                }
            },
            headers=headers
        )
        
        # Step 3: Batch operations for efficiency
        batch_ops = requests.post(
            f"{base_url}/batch-operations",
            json={
                "workflow_request": {"domain_id": "your_domain_id"},
                "operations": [
                    {
                        "action": "add",
                        "data": {
                            "from_table": "products",
                            "to_table": "categories",
                            "relationship_type": "many_to_one",
                            "description": "Products belong to categories"
                        }
                    },
                    {
                        "action": "add",
                        "data": {
                            "from_table": "order_items",
                            "to_table": "orders",
                            "relationship_type": "many_to_one",
                            "description": "Order items belong to orders"
                        }
                    }
                ]
            },
            headers=headers
        )
        
        # Step 4: Validate workflow
        validation = requests.post(
            f"{base_url}/validate/your_domain_id",
            headers=headers
        )
        
        if validation.status_code == 200:
            validation_data = validation.json()["data"]
            print(f"Validation: {validation_data['validation_passed']}")
            if not validation_data['validation_passed']:
                print(f"Errors: {validation_data['errors']}")
        
        # Step 5: Get final workflow state
        final_state = requests.get(
            f"{base_url}/workflow?domain_id=your_domain_id",
            headers=headers
        )
        
        if final_state.status_code == 200:
            final_data = final_state.json()["data"]
            print(f"Final Relationships: {final_data['summary']['total_relationships']}")
            print("Workflow ready for commit!")

# Run the complete workflow
asyncio.run(complete_relationship_workflow())
```

### cURL Examples

#### Generate Recommendations
```bash
curl -X POST "http://localhost:8000/workflow/relationships/recommendations" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "domain_id": "your_domain_id",
    "domain_name": "Your Domain",
    "business_domain": "Your Business Domain"
  }'
```

#### Add Custom Relationship
```bash
curl -X POST "http://localhost:8000/workflow/relationships/custom" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "workflow_request": {
      "domain_id": "your_domain_id"
    },
    "request": {
      "from_table": "orders",
      "to_table": "customers",
      "relationship_type": "many_to_one",
      "from_column": "customer_id",
      "to_column": "customer_id",
      "description": "Orders belong to customers"
    }
  }'
```

## Relationship Types

The system supports the following relationship types:

- **one_to_one**: Each record in table A relates to exactly one record in table B
- **one_to_many**: Each record in table A can relate to multiple records in table B
- **many_to_one**: Multiple records in table A can relate to one record in table B
- **many_to_many**: Multiple records in table A can relate to multiple records in table B

## Confidence Scoring

LLM-generated relationships include confidence scores:

- **High (0.8-1.0)**: Strong patterns, clear business logic
- **Medium (0.6-0.79)**: Good patterns, some ambiguity
- **Low (0.3-0.59)**: Weak patterns, requires business validation

## Business Logic Patterns

The system automatically detects common business relationship patterns:

- **Employee → Department**: Many-to-one
- **Customer → Orders**: One-to-many
- **Product → Category**: Many-to-one
- **Transaction → Account**: Many-to-one
- **Event → Date**: Many-to-one

## Validation Rules

The workflow validation checks:

1. **Table Existence**: All referenced tables exist in the workflow
2. **Relationship Types**: Valid relationship type values
3. **Column References**: Valid column references when specified
4. **Business Logic**: Basic business rule validation

## Next Steps After Relationships

Once relationships are defined:

1. **Review all relationships** for accuracy
2. **Validate against business requirements**
3. **Commit workflow** to database
4. **Generate MDL schema** with defined relationships
5. **Implement database constraints** based on relationships

## Error Handling

Common error scenarios and solutions:

- **No tables in workflow**: Add tables before generating relationships
- **Invalid relationship type**: Use one of the four supported types
- **Missing required fields**: Ensure all required fields are provided
- **Table not found**: Verify table names exist in the workflow

## Best Practices

1. **Generate recommendations first** to see what LLM suggests
2. **Review high-confidence relationships** for immediate implementation
3. **Validate medium-confidence relationships** against business rules
4. **Add custom relationships** for business-specific logic
5. **Use descriptive names** for relationships
6. **Document business justification** for custom relationships
7. **Validate workflow** before committing

## Integration with MDL Schema

The relationship workflow step is designed to prepare data for MDL schema generation:

- **Table definitions** from the table creation step
- **Relationship definitions** from this step
- **Business context** from domain creation
- **Column metadata** from enhanced column definitions

This creates a complete data model that can be exported to MDL format for use in BI tools and data modeling applications.

## Troubleshooting

### Common Issues

1. **Recommendations not generated**
   - Ensure tables exist in workflow
   - Check domain context is properly set
   - Verify LLM service is accessible

2. **Relationships not saving**
   - Check workflow session is active
   - Verify user permissions
   - Ensure required fields are provided

3. **Validation errors**
   - Review error messages for specific issues
   - Check table and column references
   - Verify relationship type values

### Debug Information

Enable debug logging to see detailed workflow operations:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Support

For issues or questions about the relationship workflow:

1. Check the logs for error details
2. Verify workflow state using status endpoints
3. Use validation endpoints to identify issues
4. Review the example code for usage patterns

## Future Enhancements

Planned improvements:

- **Visual relationship diagram** generation
- **Relationship impact analysis** for schema changes
- **Automated relationship testing** and validation
- **Integration with database schema** generation tools
- **Relationship versioning** and change tracking

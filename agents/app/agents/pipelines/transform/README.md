# Transformation Pipeline Architecture

## Overview

The Transformation Pipeline provides a high-level architecture for feature recommendation and transformation generation. It wraps the feature engineering agent and provides a clean interface designed to support chat-based interactions where users ask questions and receive feature recommendations.

## Architecture

The pipeline follows a three-stage workflow:

1. **Feature Recommendation**: Generate features based on user queries
2. **Feature Selection**: Manage selected features in a registry
3. **Pipeline Generation**: Generate transformation pipelines (Bronze → Silver → Gold) for selected features

## Key Components

### TransformationPipeline

The main pipeline class that orchestrates the feature recommendation workflow.

```python
from app.agents.pipelines.transform import TransformationPipeline

pipeline = TransformationPipeline(
    llm=get_llm(),
    retrieval_helper=RetrievalHelper(),
    domain_config=get_domain_config("cybersecurity")
)
```

### FeatureRecommendationRequest

Request model for feature recommendations:

```python
request = FeatureRecommendationRequest(
    user_query="I need SOC2 vulnerability features",
    project_id="cve_data",
    domain="cybersecurity",
    include_risk_features=True,
    include_impact_features=True,
    include_likelihood_features=True
)
```

### FeatureRegistryEntry

Represents a feature in the registry with all its metadata:

- `feature_id`: Unique identifier
- `feature_name`: Name of the feature
- `natural_language_question`: The question this feature answers
- `transformation_layer`: "silver" or "gold"
- `silver_pipeline`: Bronze → Silver transformation structure
- `gold_pipeline`: Silver → Gold transformation structure
- `depends_on`: List of feature IDs this feature depends on

### ConversationContext

Maintains context across conversation turns:

- `project_id`: Project identifier
- `domain`: Domain context (cybersecurity, hr_compliance, etc.)
- `previous_queries`: History of queries
- `selected_features`: Set of selected feature IDs
- `feature_registry`: Dictionary of all features

## Usage Examples

### 1. Feature Recommendation

```python
# Initialize pipeline
pipeline = TransformationPipeline()
await pipeline.initialize()

# Create request
request = FeatureRecommendationRequest(
    user_query="Create a report for Snyk that looks at Critical and High vulnerabilities",
    project_id="cve_data",
    domain="cybersecurity"
)

# Get recommendations
response = await pipeline.recommend_features(request)

if response.success:
    for feature in response.recommended_features:
        print(f"{feature.feature_name}: {feature.natural_language_question}")
```

### 2. Feature Selection

```python
# Select features from recommendations
feature_ids = [f.feature_id for f in response.recommended_features[:3]]
result = await pipeline.select_features(
    feature_ids=feature_ids,
    conversation_context=response.conversation_context
)
```

### 3. Pipeline Generation

```python
# Generate pipelines for selected features
pipeline_request = PipelineGenerationRequest(
    feature_ids=feature_ids,
    conversation_context=response.conversation_context,
    export_format="dbt",  # or "airflow", "databricks", "sql"
    include_dependencies=True
)

pipeline_response = await pipeline.generate_pipelines(pipeline_request)

if pipeline_response.success:
    for feature_id, pipeline_data in pipeline_response.pipelines.items():
        print(f"Feature: {pipeline_data['feature_name']}")
        print(f"Silver Pipeline: {pipeline_data['silver_pipeline']}")
        print(f"Gold Pipeline: {pipeline_data['gold_pipeline']}")
```

### 4. Using the run() Method

The pipeline also supports a unified `run()` method:

```python
# Recommend features
result = await pipeline.run(
    operation="recommend",
    user_query="I need SOC2 vulnerability features",
    project_id="cve_data",
    domain="cybersecurity"
)

# Select features
result = await pipeline.run(
    operation="select",
    feature_ids=["feature_1", "feature_2"],
    conversation_context=context
)

# Generate pipelines
result = await pipeline.run(
    operation="generate_pipelines",
    request=pipeline_request
)
```

## Integration with Chat UX

This pipeline is designed to work with the chat-based UX shown in `CompletePipelineWithExport.jsx`. The workflow matches the user interaction flow:

1. **User asks a question** → `recommend_features()` is called
2. **User selects features** → `select_features()` is called
3. **User views pipeline** → `generate_pipelines()` is called
4. **User exports** → Pipeline structure is ready for export

## Pipeline Structure

Each feature has a pipeline structure that follows the Medallion Architecture:

### Silver Pipeline (Bronze → Silver)
- **Source Tables**: Bronze layer tables
- **Destination Table**: Silver layer table
- **Transformation**: Basic calculations, cleaning, normalization

### Gold Pipeline (Silver → Gold)
- **Source Tables**: Silver layer tables
- **Destination Table**: Gold layer table
- **Transformation**: Aggregations, complex multi-step calculations

## Dependencies

The pipeline automatically resolves feature dependencies and calculates execution order using topological sort. Features that depend on other features will be executed after their dependencies.

## Metrics

The pipeline tracks metrics:

- `total_recommendations`: Total number of features recommended
- `total_selections`: Total number of features selected
- `total_pipelines_generated`: Total number of pipelines generated
- `average_recommendation_score`: Average recommendation score

Access metrics via:

```python
metrics = pipeline.get_metrics()
```

## Conversation Context Management

The pipeline maintains conversation contexts per project/domain combination:

```python
# Get context
context = pipeline.get_conversation_context("cve_data", "cybersecurity")

# Clear context
pipeline.clear_conversation_context("cve_data", "cybersecurity")
```

## Export Formats

Supported export formats:

- **dbt**: SQL models with dependencies
- **airflow**: Python DAG with tasks
- **databricks**: Spark transformations
- **sql**: Standalone SQL scripts

## Error Handling

All methods return response objects with `success` and `error` fields:

```python
response = await pipeline.recommend_features(request)
if not response.success:
    print(f"Error: {response.error}")
```

## See Also

- `example_usage.py`: Complete usage examples
- `demo_feature_engineering_agent.py`: Demo showing feature engineering
- `CompletePipelineWithExport.jsx`: UX implementation


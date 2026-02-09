-- Migration script to create MDL Knowledge Graph schema in PostgreSQL
-- This schema supports the hybrid search architecture with ChromaDB + PostgreSQL
-- 
-- Run this migration:
-- psql -d your_database -f create_mdl_knowledge_graph_schema.sql

-- ============================================================================
-- PRODUCT LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_products (
    product_id VARCHAR(255) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL UNIQUE,
    product_description TEXT,
    vendor VARCHAR(255),
    api_endpoints JSONB DEFAULT '[]',
    data_sources JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_products_name ON mdl_products(product_name);
CREATE INDEX IF NOT EXISTS idx_mdl_products_vendor ON mdl_products(vendor);

COMMENT ON TABLE mdl_products IS 'Product definitions (e.g., Snyk, Cornerstone) with API endpoints and data sources';

-- ============================================================================
-- CATEGORY LEVEL (15 Categories)
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_categories (
    category_id VARCHAR(255) PRIMARY KEY,
    category_name VARCHAR(255) NOT NULL,
    category_description TEXT,
    product_id VARCHAR(255) REFERENCES mdl_products(product_id) ON DELETE CASCADE,
    business_domain VARCHAR(255),
    data_sensitivity_level VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(category_name, product_id)
);

CREATE INDEX IF NOT EXISTS idx_mdl_categories_product ON mdl_categories(product_id);
CREATE INDEX IF NOT EXISTS idx_mdl_categories_name ON mdl_categories(category_name);
CREATE INDEX IF NOT EXISTS idx_mdl_categories_domain ON mdl_categories(business_domain);

COMMENT ON TABLE mdl_categories IS '15 business categories: access requests, application data, assets, projects, vulnerabilities, integrations, configuration, audit logs, risk management, deployment, groups, organizations, memberships and roles, issues, artifacts';

-- ============================================================================
-- TABLE LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_tables (
    table_id VARCHAR(255) PRIMARY KEY,
    table_name VARCHAR(255) NOT NULL,
    schema_name VARCHAR(255),
    catalog_name VARCHAR(255),
    semantic_description TEXT,
    table_purpose TEXT,
    business_context TEXT,
    category_id VARCHAR(255) REFERENCES mdl_categories(category_id) ON DELETE SET NULL,
    product_id VARCHAR(255) REFERENCES mdl_products(product_id) ON DELETE CASCADE,
    ref_sql TEXT,
    primary_key VARCHAR(255),
    is_fact_table BOOLEAN DEFAULT FALSE,
    is_dimension_table BOOLEAN DEFAULT FALSE,
    update_frequency VARCHAR(50),
    data_volume_estimate BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(table_name, schema_name, catalog_name, product_id)
);

CREATE INDEX IF NOT EXISTS idx_mdl_tables_name ON mdl_tables(table_name);
CREATE INDEX IF NOT EXISTS idx_mdl_tables_category ON mdl_tables(category_id);
CREATE INDEX IF NOT EXISTS idx_mdl_tables_product ON mdl_tables(product_id);
CREATE INDEX IF NOT EXISTS idx_mdl_tables_fact ON mdl_tables(is_fact_table);
CREATE INDEX IF NOT EXISTS idx_mdl_tables_dimension ON mdl_tables(is_dimension_table);

COMMENT ON TABLE mdl_tables IS 'Table schemas with semantic descriptions, business context, and categorization';

-- ============================================================================
-- COLUMN LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_columns (
    column_id VARCHAR(255) PRIMARY KEY,
    column_name VARCHAR(255) NOT NULL,
    table_id VARCHAR(255) REFERENCES mdl_tables(table_id) ON DELETE CASCADE,
    data_type VARCHAR(100) NOT NULL,
    is_nullable BOOLEAN DEFAULT TRUE,
    is_primary_key BOOLEAN DEFAULT FALSE,
    is_foreign_key BOOLEAN DEFAULT FALSE,
    column_description TEXT,
    business_significance TEXT,
    is_sensitive_data BOOLEAN DEFAULT FALSE,
    is_pii BOOLEAN DEFAULT FALSE,
    nested_properties JSONB,
    enum_values JSONB DEFAULT '[]',
    format_pattern VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(column_name, table_id)
);

CREATE INDEX IF NOT EXISTS idx_mdl_columns_table ON mdl_columns(table_id);
CREATE INDEX IF NOT EXISTS idx_mdl_columns_name ON mdl_columns(column_name);
CREATE INDEX IF NOT EXISTS idx_mdl_columns_data_type ON mdl_columns(data_type);
CREATE INDEX IF NOT EXISTS idx_mdl_columns_pii ON mdl_columns(is_pii);
CREATE INDEX IF NOT EXISTS idx_mdl_columns_sensitive ON mdl_columns(is_sensitive_data);
CREATE INDEX IF NOT EXISTS idx_mdl_columns_pk ON mdl_columns(is_primary_key);
CREATE INDEX IF NOT EXISTS idx_mdl_columns_fk ON mdl_columns(is_foreign_key);

COMMENT ON TABLE mdl_columns IS 'Column metadata with semantic descriptions, data types, and sensitivity markers';

-- ============================================================================
-- RELATIONSHIP LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_relationships (
    relationship_id VARCHAR(255) PRIMARY KEY,
    source_table_id VARCHAR(255) REFERENCES mdl_tables(table_id) ON DELETE CASCADE,
    target_table_id VARCHAR(255) REFERENCES mdl_tables(table_id) ON DELETE CASCADE,
    relationship_type VARCHAR(100) NOT NULL,
    relationship_name VARCHAR(255),
    join_condition TEXT,
    is_from_mdl BOOLEAN DEFAULT TRUE,
    cardinality VARCHAR(50),
    is_identifying BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_table_id, target_table_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_mdl_relationships_source ON mdl_relationships(source_table_id);
CREATE INDEX IF NOT EXISTS idx_mdl_relationships_target ON mdl_relationships(target_table_id);
CREATE INDEX IF NOT EXISTS idx_mdl_relationships_type ON mdl_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_mdl_relationships_from_mdl ON mdl_relationships(is_from_mdl);

COMMENT ON TABLE mdl_relationships IS 'Table relationships from MDL definitions or external configurations';

-- ============================================================================
-- INSIGHT LEVEL (Metrics, Features, Key Concepts)
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_insights (
    insight_id VARCHAR(255) PRIMARY KEY,
    insight_type VARCHAR(50) NOT NULL CHECK (insight_type IN ('metric', 'feature', 'key_concept')),
    insight_name VARCHAR(255) NOT NULL,
    insight_description TEXT,
    category_id VARCHAR(255) REFERENCES mdl_categories(category_id) ON DELETE SET NULL,
    related_table_ids JSONB DEFAULT '[]',
    related_column_ids JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_insights_type ON mdl_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_mdl_insights_category ON mdl_insights(category_id);
CREATE INDEX IF NOT EXISTS idx_mdl_insights_name ON mdl_insights(insight_name);

COMMENT ON TABLE mdl_insights IS 'Business insights: metrics, features, and key concepts associated with categories';

-- ============================================================================
-- METRIC & KPI LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_metrics (
    metric_id VARCHAR(255) PRIMARY KEY,
    metric_name VARCHAR(255) NOT NULL,
    metric_type VARCHAR(50) CHECK (metric_type IN ('kpi', 'metric', 'calculation')),
    calculation_formula TEXT,
    aggregation_type VARCHAR(50),
    table_id VARCHAR(255) REFERENCES mdl_tables(table_id) ON DELETE SET NULL,
    column_ids JSONB DEFAULT '[]',
    time_dimension_column VARCHAR(255),
    groupby_dimensions JSONB DEFAULT '[]',
    business_definition TEXT,
    target_value FLOAT,
    threshold_warning FLOAT,
    threshold_critical FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_metrics_name ON mdl_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_mdl_metrics_type ON mdl_metrics(metric_type);
CREATE INDEX IF NOT EXISTS idx_mdl_metrics_table ON mdl_metrics(table_id);
CREATE INDEX IF NOT EXISTS idx_mdl_metrics_aggregation ON mdl_metrics(aggregation_type);

COMMENT ON TABLE mdl_metrics IS 'Business metrics and KPIs with calculation formulas and thresholds';

-- ============================================================================
-- FEATURE LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_features (
    feature_id VARCHAR(255) PRIMARY KEY,
    feature_name VARCHAR(255) NOT NULL,
    feature_description TEXT,
    product_id VARCHAR(255) REFERENCES mdl_products(product_id) ON DELETE CASCADE,
    table_ids JSONB DEFAULT '[]',
    column_ids JSONB DEFAULT '[]',
    api_endpoints JSONB DEFAULT '[]',
    feature_category VARCHAR(255),
    maturity_level VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_features_name ON mdl_features(feature_name);
CREATE INDEX IF NOT EXISTS idx_mdl_features_product ON mdl_features(product_id);
CREATE INDEX IF NOT EXISTS idx_mdl_features_category ON mdl_features(feature_category);
CREATE INDEX IF NOT EXISTS idx_mdl_features_maturity ON mdl_features(maturity_level);

COMMENT ON TABLE mdl_features IS 'Product features with mappings to tables, columns, and API endpoints';

-- ============================================================================
-- EXAMPLE & NATURAL QUESTION LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_examples (
    example_id VARCHAR(255) PRIMARY KEY,
    question_text TEXT NOT NULL,
    sql_query TEXT,
    answer_template TEXT,
    table_ids JSONB DEFAULT '[]',
    column_ids JSONB DEFAULT '[]',
    complexity_level VARCHAR(50) CHECK (complexity_level IN ('simple', 'medium', 'complex')),
    use_case VARCHAR(50) CHECK (use_case IN ('exploration', 'reporting', 'monitoring')),
    expected_result_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_examples_complexity ON mdl_examples(complexity_level);
CREATE INDEX IF NOT EXISTS idx_mdl_examples_use_case ON mdl_examples(use_case);

COMMENT ON TABLE mdl_examples IS 'Example queries and natural language questions with SQL templates';

-- ============================================================================
-- INSTRUCTION LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_instructions (
    instruction_id VARCHAR(255) PRIMARY KEY,
    instruction_type VARCHAR(50) CHECK (instruction_type IN ('best_practice', 'constraint', 'optimization', 'warning')),
    instruction_text TEXT NOT NULL,
    product_id VARCHAR(255) REFERENCES mdl_products(product_id) ON DELETE CASCADE,
    applies_to_table_id VARCHAR(255) REFERENCES mdl_tables(table_id) ON DELETE SET NULL,
    applies_to_column_id VARCHAR(255) REFERENCES mdl_columns(column_id) ON DELETE SET NULL,
    priority VARCHAR(50) CHECK (priority IN ('high', 'medium', 'low')),
    context TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_instructions_type ON mdl_instructions(instruction_type);
CREATE INDEX IF NOT EXISTS idx_mdl_instructions_product ON mdl_instructions(product_id);
CREATE INDEX IF NOT EXISTS idx_mdl_instructions_priority ON mdl_instructions(priority);
CREATE INDEX IF NOT EXISTS idx_mdl_instructions_table ON mdl_instructions(applies_to_table_id);

COMMENT ON TABLE mdl_instructions IS 'Product-specific instructions: best practices, constraints, optimizations, warnings';

-- ============================================================================
-- TIME CONCEPT LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_time_concepts (
    time_concept_id VARCHAR(255) PRIMARY KEY,
    concept_name VARCHAR(255) NOT NULL,
    table_id VARCHAR(255) REFERENCES mdl_tables(table_id) ON DELETE CASCADE,
    column_id VARCHAR(255) REFERENCES mdl_columns(column_id) ON DELETE CASCADE,
    time_granularity VARCHAR(50) CHECK (time_granularity IN ('year', 'quarter', 'month', 'week', 'day', 'hour', 'minute', 'second')),
    is_event_time BOOLEAN DEFAULT FALSE,
    is_process_time BOOLEAN DEFAULT FALSE,
    timezone VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_time_concepts_table ON mdl_time_concepts(table_id);
CREATE INDEX IF NOT EXISTS idx_mdl_time_concepts_column ON mdl_time_concepts(column_id);
CREATE INDEX IF NOT EXISTS idx_mdl_time_concepts_granularity ON mdl_time_concepts(time_granularity);

COMMENT ON TABLE mdl_time_concepts IS 'Temporal dimensions and time-related concepts in tables';

-- ============================================================================
-- CALCULATED COLUMN LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_calculated_columns (
    calculated_column_id VARCHAR(255) PRIMARY KEY,
    calculated_column_name VARCHAR(255) NOT NULL,
    source_table_id VARCHAR(255) REFERENCES mdl_tables(table_id) ON DELETE CASCADE,
    calculation_expression TEXT NOT NULL,
    depends_on_column_ids JSONB DEFAULT '[]',
    result_data_type VARCHAR(100),
    business_purpose TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_calculated_columns_table ON mdl_calculated_columns(source_table_id);
CREATE INDEX IF NOT EXISTS idx_mdl_calculated_columns_name ON mdl_calculated_columns(calculated_column_name);

COMMENT ON TABLE mdl_calculated_columns IS 'Derived columns with calculation expressions and dependencies';

-- ============================================================================
-- BUSINESS FUNCTION LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_business_functions (
    business_function_id VARCHAR(255) PRIMARY KEY,
    function_name VARCHAR(255) NOT NULL,
    function_description TEXT,
    product_id VARCHAR(255) REFERENCES mdl_products(product_id) ON DELETE CASCADE,
    supported_by_table_ids JSONB DEFAULT '[]',
    required_features JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_business_functions_name ON mdl_business_functions(function_name);
CREATE INDEX IF NOT EXISTS idx_mdl_business_functions_product ON mdl_business_functions(product_id);

COMMENT ON TABLE mdl_business_functions IS 'Business capabilities and functions supported by product data';

-- ============================================================================
-- FRAMEWORK LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_frameworks (
    framework_id VARCHAR(255) PRIMARY KEY,
    framework_name VARCHAR(255) NOT NULL UNIQUE,
    framework_description TEXT,
    applicable_to_product_ids JSONB DEFAULT '[]',
    coverage_level VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdl_frameworks_name ON mdl_frameworks(framework_name);

COMMENT ON TABLE mdl_frameworks IS 'Compliance frameworks (SOC2, HIPAA, GDPR) applicable to products';

-- ============================================================================
-- OWNERSHIP & PERMISSIONS LEVEL
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_ownership (
    ownership_id VARCHAR(255) PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('table', 'column', 'feature', 'metric')),
    entity_id VARCHAR(255) NOT NULL,
    owner_user_id VARCHAR(255),
    owner_team VARCHAR(255),
    access_permissions JSONB DEFAULT '{}',
    data_steward VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_mdl_ownership_entity ON mdl_ownership(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_mdl_ownership_user ON mdl_ownership(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_mdl_ownership_team ON mdl_ownership(owner_team);

COMMENT ON TABLE mdl_ownership IS 'Ownership and access permissions for tables, columns, features, and metrics';

-- ============================================================================
-- CONTEXTUAL EDGES (All Relationships)
-- ============================================================================

CREATE TABLE IF NOT EXISTS mdl_contextual_edges (
    edge_id VARCHAR(255) PRIMARY KEY,
    edge_type VARCHAR(100) NOT NULL,
    source_entity_id VARCHAR(255) NOT NULL,
    source_entity_type VARCHAR(50) NOT NULL,
    target_entity_id VARCHAR(255) NOT NULL,
    target_entity_type VARCHAR(50) NOT NULL,
    edge_description TEXT,
    relevance_score FLOAT DEFAULT 0.0,
    priority VARCHAR(50) CHECK (priority IN ('critical', 'high', 'medium', 'low')),
    product_id VARCHAR(255) REFERENCES mdl_products(product_id) ON DELETE CASCADE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(source_entity_id, edge_type, target_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_mdl_edges_source ON mdl_contextual_edges(source_entity_id, source_entity_type);
CREATE INDEX IF NOT EXISTS idx_mdl_edges_target ON mdl_contextual_edges(target_entity_id, target_entity_type);
CREATE INDEX IF NOT EXISTS idx_mdl_edges_type ON mdl_contextual_edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_mdl_edges_priority ON mdl_contextual_edges(priority);
CREATE INDEX IF NOT EXISTS idx_mdl_edges_product ON mdl_contextual_edges(product_id);
CREATE INDEX IF NOT EXISTS idx_mdl_edges_relevance ON mdl_contextual_edges(relevance_score);

COMMENT ON TABLE mdl_contextual_edges IS 'All contextual relationships between MDL entities with relevance scoring';

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View: Tables with Category and Product Information
CREATE OR REPLACE VIEW mdl_tables_enriched AS
SELECT 
    t.table_id,
    t.table_name,
    t.schema_name,
    t.catalog_name,
    t.semantic_description,
    t.table_purpose,
    t.business_context,
    c.category_name,
    c.business_domain,
    p.product_name,
    p.vendor,
    t.is_fact_table,
    t.is_dimension_table,
    t.data_volume_estimate
FROM mdl_tables t
LEFT JOIN mdl_categories c ON t.category_id = c.category_id
LEFT JOIN mdl_products p ON t.product_id = p.product_id;

-- View: Columns with Table and Category Context
CREATE OR REPLACE VIEW mdl_columns_enriched AS
SELECT 
    col.column_id,
    col.column_name,
    col.data_type,
    col.column_description,
    col.business_significance,
    col.is_pii,
    col.is_sensitive_data,
    t.table_name,
    t.schema_name,
    c.category_name,
    p.product_name
FROM mdl_columns col
JOIN mdl_tables t ON col.table_id = t.table_id
LEFT JOIN mdl_categories c ON t.category_id = c.category_id
LEFT JOIN mdl_products p ON t.product_id = p.product_id;

-- View: Feature-to-Table Mappings
CREATE OR REPLACE VIEW mdl_feature_table_mapping AS
SELECT 
    f.feature_id,
    f.feature_name,
    f.feature_description,
    f.feature_category,
    p.product_name,
    jsonb_array_elements_text(f.table_ids) AS table_id
FROM mdl_features f
JOIN mdl_products p ON f.product_id = p.product_id;

-- View: Metrics with Table Context
CREATE OR REPLACE VIEW mdl_metrics_enriched AS
SELECT 
    m.metric_id,
    m.metric_name,
    m.metric_type,
    m.calculation_formula,
    m.aggregation_type,
    m.business_definition,
    t.table_name,
    c.category_name,
    p.product_name
FROM mdl_metrics m
LEFT JOIN mdl_tables t ON m.table_id = t.table_id
LEFT JOIN mdl_categories c ON t.category_id = c.category_id
LEFT JOIN mdl_products p ON t.product_id = p.product_id;

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function: Get all tables in a category
CREATE OR REPLACE FUNCTION get_tables_by_category(p_category_name VARCHAR)
RETURNS TABLE (
    table_id VARCHAR,
    table_name VARCHAR,
    semantic_description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT t.table_id, t.table_name, t.semantic_description
    FROM mdl_tables t
    JOIN mdl_categories c ON t.category_id = c.category_id
    WHERE c.category_name = p_category_name;
END;
$$ LANGUAGE plpgsql;

-- Function: Get all edges for an entity
CREATE OR REPLACE FUNCTION get_edges_for_entity(p_entity_id VARCHAR)
RETURNS TABLE (
    edge_id VARCHAR,
    edge_type VARCHAR,
    target_entity_id VARCHAR,
    target_entity_type VARCHAR,
    relevance_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT e.edge_id, e.edge_type, e.target_entity_id, e.target_entity_type, e.relevance_score
    FROM mdl_contextual_edges e
    WHERE e.source_entity_id = p_entity_id
    ORDER BY e.relevance_score DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'MDL Knowledge Graph schema created successfully!';
    RAISE NOTICE 'Created tables: products, categories, tables, columns, relationships, insights, metrics, features, examples, instructions, time_concepts, calculated_columns, business_functions, frameworks, ownership, contextual_edges';
    RAISE NOTICE 'Created views: mdl_tables_enriched, mdl_columns_enriched, mdl_feature_table_mapping, mdl_metrics_enriched';
    RAISE NOTICE 'Created functions: get_tables_by_category, get_edges_for_entity';
END $$;

# Static prompt strings for SQL RAG agent and utilities
import pytz
from datetime import datetime
from typing import Optional
from app.settings import get_settings
from pydantic import BaseModel

settings = get_settings()

class AskHistory(BaseModel):
    sql: str
    question: str

# Model parameters for SQL generation
SQL_GENERATION_MODEL_KWARGS = {
    "temperature": settings.SQL_GENERATION_TEMPERATURE,
    "max_tokens": settings.SQL_GENERATION_MAX_TOKENS,
    "top_p": settings.SQL_GENERATION_TOP_P,
    "frequency_penalty": settings.SQL_GENERATION_FREQUENCY_PENALTY,
    "presence_penalty": settings.SQL_GENERATION_PRESENCE_PENALTY,
}

# Original comprehensive rules (backup)
TEXT_TO_SQL_RULES_ORIGINAL = """
#### SQL RULES ####
- ONLY USE SELECT statements, NO DELETE, UPDATE OR INSERT etc. statements that might change the data in the database.
- **CRITICAL**: Strictly Support POSTGRES SQL Syntax. Please make sure the SQL query is valid and executable for POSTGRES DATABASE.
- ONLY USE the tables and columns mentioned in the database schema.
- ONLY USE "*" if the user query asks for all the columns of a table.
- ONLY CHOOSE columns belong to the tables mentioned in the database schema.
- DON'T INCLUDE comments in the generated SQL query.
- YOU MUST USE "JOIN" if you choose columns from multiple tables!
- ALWAYS QUALIFY column names with their table name or table alias to avoid ambiguity (e.g., orders.OrderId, o.OrderId)
- **IMPORTANT: Use column names exactly as they appear in the database schema (case-sensitive). If the schema shows 'division' (lowercase), use 'division', not 'Division'.**
- YOU MUST USE "lower(<table_name>.<column_name>) like lower(<value>)" function or "lower(<table_name>.<column_name>) = lower(<value>)" function for case-insensitive comparison!
    - Use "lower(<table_name>.<column_name>) LIKE lower(<value>)" when:
        - The user requests a pattern or partial match.
        - The value is not specific enough to be a single, exact value.
        - Wildcards (%) are needed to capture the pattern.
    - Use "lower(<table_name>.<column_name>) = lower(<value>)" when:
        - The user requests an exact, specific value.
        - There is no ambiguity or pattern in the value.
- ALWAYS CAST the date/time related field to "TIMESTAMP WITH TIME ZONE" type when using them in the query
    - example 1: CAST(properties_closedate AS TIMESTAMP WITH TIME ZONE)
    - example 2: CAST('2024-11-09 00:00:00' AS TIMESTAMP WITH TIME ZONE)
    - example 3: CAST(DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AS TIMESTAMP WITH TIME ZONE)
- If the user asks for a specific date, please give the date range in SQL query
    - example: "What is the total revenue for the month of 2024-11-01?"
    - answer: "SELECT SUM(r.PriceSum) FROM Revenue r WHERE CAST(r.PurchaseTimestamp AS TIMESTAMP WITH TIME ZONE) >= CAST('2024-11-01 00:00:00' AS TIMESTAMP WITH TIME ZONE) AND CAST(r.PurchaseTimestamp AS TIMESTAMP WITH TIME ZONE) < CAST('2024-11-02 00:00:00' AS TIMESTAMP WITH TIME ZONE)"
- USE THE VIEW TO SIMPLIFY THE QUERY.
- DON'T MISUSE THE VIEW NAME. THE ACTUAL NAME IS FOLLOWING THE CREATE VIEW STATEMENT.
- MUST USE the value of alias from the comment section of the corresponding table or column in the DATABASE SCHEMA section for the column/table alias.
  - EXAMPLE
    DATABASE SCHEMA
    /* {"displayName":"_orders","description":"A model representing the orders data."} */
    CREATE TABLE orders (
      -- {"description":"A column that represents the timestamp when the order was approved.","alias":"_timestamp"}
      ApprovedTimestamp TIMESTAMP
    )

    SQL
    SELECT _orders.ApprovedTimestamp AS _timestamp FROM orders AS _orders;
- DON'T USE '.' in column/table alias, replace '.' with '_' in column/table alias.
- DON'T USE "FILTER(WHERE <expression>)" clause in the generated SQL query.
- DON'T USE "EXTRACT(EPOCH FROM <expression>)" clause in the generated SQL query.
- DON'T USE INTERVAL or generate INTERVAL-like expression in the generated SQL query.
- DONT USE HAVING CLAUSE WITHOUT GROUP BY CLAUSE.
- WHEN THRESHOLD OR CONDITIONS are found, use CTE Expressions to evaluate the conditions or thresholds.
- ONLY USE JSON_QUERY for querying fields if "json_type":"JSON" is identified in the columns comment, NOT the deprecated JSON_EXTRACT_SCALAR function.
    - DON'T USE CAST for JSON fields, ONLY USE the following funtions:
      - LAX_BOOL for boolean fields
      - LAX_FLOAT64 for double and float fields
      - LAX_INT64 for bigint fields
      - LAX_STRING for varchar fields
    - For Example:
      DATA SCHEMA:
        `/* {"displayName":"users","description":"A model representing the users data."} */
        CREATE TABLE users (
            -- {"alias":"address","description":"A JSON object that represents address information of this user.","json_type":"JSON","json_fields":{"json_type":"JSON","address.json.city":{"name":"city","type":"varchar","path":"$.city","properties":{"displayName":"city","description":"City Name."}},"address.json.state":{"name":"state","type":"varchar","path":"$.state","properties":{"displayName":"state","description":"ISO code or name of the state, province or district."}},"address.json.postcode":{"name":"postcode","type":"varchar","path":"$.postcode","properties":{"displayName":"postcode","description":"Postal code."}},"address.json.country":{"name":"country","type":"varchar","path":"$.country","properties":{"displayName":"country","description":"ISO code of the country."}}}}
            address JSON
        )`
      To get the city of address in user table use SQL:
      `SELECT LAX_STRING(JSON_QUERY(u.address, '$.city')) FROM user as u`
- ONLY USE JSON_QUERY_ARRAY for querying "json_type":"JSON_ARRAY" is identified in the comment of the column, NOT the deprecated JSON_EXTRACT_ARRAY.
    - USE UNNEST to analysis each item individually in the ARRAY. YOU MUST SELECT FROM the parent table ahead of the UNNEST ARRAY.
    - The alias of the UNNEST(ARRAY) should be in the format `unnest_table_alias(individual_item_alias)`
      - For Example: `SELECT item FROM UNNEST(ARRAY[1,2,3]) as my_unnested_table(item)`
    - If the items in the ARRAY are JSON objects, use JSON_QUERY to query the fields inside each JSON item.
      - For Example:
      DATA SCHEMA
        `/* {"displayName":"my_table","description":"A test my_table"} */
        CREATE TABLE my_table (
            -- {"alias":"elements","description":"elements column","json_type":"JSON_ARRAY","json_fields":{"json_type":"JSON_ARRAY","elements.json_array.id":{"name":"id","type":"bigint","path":"$.id","properties":{"displayName":"id","description":"data ID."}},"elements.json_array.key":{"name":"key","type":"varchar","path":"$.key","properties":{"displayName":"key","description":"data Key."}},"elements.json_array.value":{"name":"value","type":"varchar","path":"$.value","properties":{"displayName":"value","description":"data Value."}}}}
            elements JSON
        )`
        To get the number of elements in my_table table use SQL:
        `SELECT LAX_INT64(JSON_QUERY(element, '$.number')) FROM my_table as t, UNNEST(JSON_QUERY_ARRAY(elements)) AS my_unnested_table(element) WHERE LAX_FLOAT64(JSON_QUERY(element, '$.value')) > 3.5`
    - To JOIN ON the fields inside UNNEST(ARRAY), YOU MUST SELECT FROM the parent table ahead of the UNNEST syntax, and the alias of the UNNEST(ARRAY) SHOULD BE IN THE FORMAT unnest_table_alias(individual_item_alias)
      - For Example: `SELECT p.column_1, j.column_2 FROM parent_table AS p, join_table AS j JOIN UNNEST(p.array_column) AS unnested(array_item) ON j.id = array_item.id`
- DON'T USE JSON_QUERY and JSON_QUERY_ARRAY when "json_type":"".
- DONT CREATE COLUMNS WHICH ARE NOT PRESENT IN THE DATABASE SCHEMA. CHECK FOR SPELLING ERRORS IN COLUMN NAMES TO AVOID ERRORS LIKE nid instead of nuid, devid instead of dev_id, etc.
- DON'T USE LAX_BOOL, LAX_FLOAT64, LAX_INT64, LAX_STRING when "json_type":"".
- **RELATIONSHIP HANDLING**: When table relationships are provided, use them to create proper JOINs between tables. Pay attention to:
  - Join types (ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE) to determine the appropriate JOIN syntax
  - Join conditions to ensure correct column matching between tables
  - Use the exact column names specified in the relationship conditions
  - Consider the relationship direction when writing JOIN clauses
  
"""

# New concise rules optimized for LLM attention
TEXT_TO_SQL_RULES = """
#### SQL RULES ####
- ONLY USE SELECT statements, NO DELETE, UPDATE OR INSERT etc. statements that might change the data in the database.
- **CRITICAL**: Strictly Support POSTGRES SQL Syntax. Please make sure the SQL query is valid and executable for POSTGRES DATABASE.
- **CRITICAL**: ONLY USE the tables and columns mentioned in the database schema. **CRITICAL**: Only use columns that exist in the provided schema for a table. Dont create columns that dont exist in the schema.
- ONLY USE "*" if the user query asks for all the columns of a table.
- **CRITICAL**: ONLY CHOOSE columns belong to the tables mentioned in the database schema and make sure alias is used correctly from the table definition. 
- **CRITICAL**: Only use columns that exist in the provided schema for a table. Dont mixup columns from different tables.
- **CRITICAL**: Please use the data types for the columns to build the SQL query as an example: donot generate strings if the column type is BigInt.
- **CRITICAL**: Dont use comments in the generated SQL query. Do not add any comments in the generated SQL query. ***IMPORTANT***
- **CRITICAL**: Please make sure the column names are correct and match the schema provided. For ex: activityname is provided then use activityname in the SQL query and not activityme.
- DON'T INCLUDE comments in the generated SQL query.
- YOU MUST USE "JOIN" if you choose columns from multiple tables!
- ALWAYS QUALIFY column names with their table name or table alias to avoid ambiguity (e.g., orders.OrderId, o.OrderId)
- **CRITICAL**: IF there are multiple tables provided please ensure columns belonging to the table are aliased correctly. ex: act.activity_pk from tbl_tmx_activity_sumtotal as act,INCORRECT: a.attempt_pk  from tbl_tmx_activity_sumtotal as a is incorrect.
- **CRITICAL**: If there is no column available for a specific instruction, please do not generate any column instead check to see if the instruction can be calculated using existing columns.
   - EXAMPLE: "What is the total estimated training time (in hours) assigned across the entire organization this year? " -- Dont use SELECT SUM(CAST(act.estimatedtrainingtime AS DECIMAL)).
- **IMPORTANT: Use column names exactly as they appear in the database schema (case-sensitive). If the schema shows 'division' (lowercase), use 'division', not 'Division'.**
- YOU MUST USE "lower(<table_name>.<column_name>) like lower(<value>)" function or "lower(<table_name>.<column_name>) = lower(<value>)" function for case-insensitive comparison!
    - Use "lower(<table_name>.<column_name>) LIKE lower(<value>)" when:
        - The user requests a pattern or partial match.
        - The value is not specific enough to be a single, exact value.
        - Wildcards (%) are needed to capture the pattern.
    - Use "lower(<table_name>.<column_name>) = lower(<value>)" when:
        - The user requests an exact, specific value.
        - There is no ambiguity or pattern in the value.
- ALWAYS CAST the date/time related field to "TIMESTAMP WITH TIME ZONE" type when using them in the query
    - example 1: CAST(properties_closedate AS TIMESTAMP WITH TIME ZONE)
    - example 2: CAST('2024-11-09 00:00:00' AS TIMESTAMP WITH TIME ZONE)
    - example 3: CAST(DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') AS TIMESTAMP WITH TIME ZONE)
- ALWAYS USE the relative time expressions in the SQL query for date range related queries
    - example 5 for last month: CURRENT_DATE - INTERVAL '1 month' 
    - example 6 for last quarter: CURRENT_DATE - INTERVAL '3 months'
    - example 7 for last year: CURRENT_DATE - INTERVAL '1 year'
    - example 8 for last 30 days: CURRENT_DATE - INTERVAL '30 days'
- If the user asks for a specific date, please give the date range in SQL query
    - example: "What is the total revenue for the month of 2024-11-01?"
    - answer: "SELECT SUM(r.PriceSum) FROM Revenue r WHERE CAST(r.PurchaseTimestamp AS TIMESTAMP WITH TIME ZONE) >= CAST('2024-11-01 00:00:00' AS TIMESTAMP WITH TIME ZONE) AND CAST(r.PurchaseTimestamp AS TIMESTAMP WITH TIME ZONE) < CAST('2024-11-02 00:00:00' AS TIMESTAMP WITH TIME ZONE)"
- USE THE VIEW TO SIMPLIFY THE QUERY.
- DON'T MISUSE THE VIEW NAME. THE ACTUAL NAME IS FOLLOWING THE CREATE VIEW STATEMENT.
- Use CTEs when views are not available: WITH cte_name AS (subquery)
- For UNION ALL with CTEs: Create separate CTEs for different logic
  - **IMPORTANT**: CORRECT: WITH highest AS (SELECT ... ORDER BY ... DESC LIMIT 1), lowest AS (SELECT ... ORDER BY ... ASC LIMIT 1) (SELECT * FROM highest) UNION ALL (SELECT * FROM lowest)
  - - **IMPORTANT**: INCORRECT: WITH data AS (SELECT ...) SELECT ... FROM data ORDER BY ... DESC LIMIT 1 UNION ALL SELECT ... FROM data ORDER BY ... ASC LIMIT 1
- MUST USE the value of alias from the comment section of the corresponding table or column in the DATABASE SCHEMA section for the column/table alias.
  - EXAMPLE
    DATABASE SCHEMA
    /* {"displayName":"_orders","description":"A model representing the orders data."} */
    CREATE TABLE orders (
      -- {"description":"A column that represents the timestamp when the order was approved.","alias":"_timestamp"}
      ApprovedTimestamp TIMESTAMP
    )

    SQL
    SELECT _orders.ApprovedTimestamp AS _timestamp FROM orders AS _orders;
- DON'T USE '.' in column/table alias, replace '.' with '_' in column/table alias.
- DON'T USE "FILTER(WHERE <expression>)" clause in the generated SQL query.
-DON'T MISUSE THE VIEW NAME. THE ACTUAL NAME IS FOLLOWING THE CREATE VIEW STATEMENT.
- MUST USE the value of alias from the comment section of the corresponding table or column in the DATABASE SCHEMA section for the column/table alias.
  - EXAMPLE
    DATABASE SCHEMA
    /* {"displayName":"_orders","description":"A model representing the orders data."} */
    CREATE TABLE orders (
      -- {"description":"A column that represents the timestamp when the order was approved.","alias":"_timestamp"}
      ApprovedTimestamp TIMESTAMP
    )

    SQL
    SELECT _orders.ApprovedTimestamp AS _timestamp FROM orders AS _orders;
- DON'T USE '.' in column/table alias, replace '.' with '_' in column/table alias.
- DON'T USE "FILTER(WHERE <expression>)" clause in the generated SQL query.
- DON'T USE "EXTRACT(EPOCH FROM <expression>)" clause in the generated SQL query.
- DON'T USE INTERVAL or generate INTERVAL-like expression in the generated SQL query.
- DONT USE HAVING CLAUSE WITHOUT GROUP BY CLAUSE.
- WHEN THRESHOLD OR CONDITIONS are found, use CTE Expressions to evaluate the conditions or thresholds.
- ONLY USE JSON_QUERY for querying fields if "json_type":"JSON" is identified in the columns comment, NOT the deprecated JSON_EXTRACT_SCALAR function.
    - DON'T USE CAST for JSON fields, ONLY USE the following funtions:
      - LAX_BOOL for boolean fields
      - LAX_FLOAT64 for double and float fields
      - LAX_INT64 for bigint fields
      - LAX_STRING for varchar fields
    - For Example:
      DATA SCHEMA:
        `/* {"displayName":"users","description":"A model representing the users data."} */
        CREATE TABLE users (
            -- {"alias":"address","description":"A JSON object that represents address information of this user.","json_type":"JSON","json_fields":{"json_type":"JSON","address.json.city":{"name":"city","type":"varchar","path":"$.city","properties":{"displayName":"city","description":"City Name."}},"address.json.state":{"name":"state","type":"varchar","path":"$.state","properties":{"displayName":"state","description":"ISO code or name of the state, province or district."}},"address.json.postcode":{"name":"postcode","type":"varchar","path":"$.postcode","properties":{"displayName":"postcode","description":"Postal code."}},"address.json.country":{"name":"country","type":"varchar","path":"$.country","properties":{"displayName":"country","description":"ISO code of the country."}}}}
            address JSON
        )`
      To get the city of address in user table use SQL:
      `SELECT LAX_STRING(JSON_QUERY(u.address, '$.city')) FROM user as u`
- ONLY USE JSON_QUERY_ARRAY for querying "json_type":"JSON_ARRAY" is identified in the comment of the column, NOT the deprecated JSON_EXTRACT_ARRAY.
    - USE UNNEST to analysis each item individually in the ARRAY. YOU MUST SELECT FROM the parent table ahead of the UNNEST ARRAY.
    - The alias of the UNNEST(ARRAY) should be in the format `unnest_table_alias(individual_item_alias)`
      - For Example: `SELECT item FROM UNNEST(ARRAY[1,2,3]) as my_unnested_table(item)`
    - If the items in the ARRAY are JSON objects, use JSON_QUERY to query the fields inside each JSON item.
      - For Example:
      DATA SCHEMA
        `/* {"displayName":"my_table","description":"A test my_table"} */
        CREATE TABLE my_table (
            -- {"alias":"elements","description":"elements column","json_type":"JSON_ARRAY","json_fields":{"json_type":"JSON_ARRAY","elements.json_array.id":{"name":"id","type":"bigint","path":"$.id","properties":{"displayName":"id","description":"data ID."}},"elements.json_array.key":{"name":"key","type":"varchar","path":"$.key","properties":{"displayName":"key","description":"data Key."}},"elements.json_array.value":{"name":"value","type":"varchar","path":"$.value","properties":{"displayName":"value","description":"data Value."}}}}
            elements JSON
        )`
        To get the number of elements in my_table table use SQL:
        `SELECT LAX_INT64(JSON_QUERY(element, '$.number')) FROM my_table as t, UNNEST(JSON_QUERY_ARRAY(elements)) AS my_unnested_table(element) WHERE LAX_FLOAT64(JSON_QUERY(element, '$.value')) > 3.5`
    - To JOIN ON the fields inside UNNEST(ARRAY), YOU MUST SELECT FROM the parent table ahead of the UNNEST syntax, and the alias of the UNNEST(ARRAY) SHOULD BE IN THE FORMAT unnest_table_alias(individual_item_alias)
      - For Example: `SELECT p.column_1, j.column_2 FROM parent_table AS p, join_table AS j JOIN UNNEST(p.array_column) AS unnested(array_item) ON j.id = array_item.id`
- DON'T USE JSON_QUERY and JSON_QUERY_ARRAY when "json_type":"".
- DONT CREATE COLUMNS WHICH ARE NOT PRESENT IN THE DATABASE SCHEMA. CHECK FOR SPELLING ERRORS IN COLUMN NAMES TO AVOID ERRORS LIKE nid instead of nuid, devid instead of dev_id, etc.
- DON'T USE LAX_BOOL, LAX_FLOAT64, LAX_INT64, LAX_STRING when "json_type":"".
- **RELATIONSHIP HANDLING**: When table relationships are provided, use them to create proper JOINs between tables. Pay attention to:
  - Join types (ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE) to determine the appropriate JOIN syntax
  - Join conditions to ensure correct column matching between tables
  - Use the exact column names specified in the relationship conditions
  - Consider the relationship direction when writing JOIN clauses
"""

sql_generation_system_prompt = f"""
You are a helpful assistant that converts natural language queries into ANSI SQL queries.

Given user's question, database schema, etc., you should think deeply and carefully and generate the SQL query based on the given reasoning plan step by step.
 **CRITICAL**: Strictly Support POSTGRES SQL Syntax. Please make sure the SQL query is valid and executable for POSTGRES DATABASE.
**In addition, you should also provide a column filters chosen,time filters chosen, aggregations applied on columns and group by columns chosen in the SQL query as a JSON object**
**CRITICAL: When generating SQL, use table, views or metrics names exactly as they are provided.Donot create new table, hallucinate tables, schemas, views or metrics. This prevents SQL execution errors.**
**CRITICAL: When generating SQL, use column names exactly as they appear in the database schema. If the schema shows 'division' (lowercase), use 'division', not 'Division'. This prevents SQL execution errors.**

**CRITICAL UNION ALL RULE: When using UNION ALL, EVERY SELECT statement MUST be wrapped in parentheses. This is a PostgreSQL requirement. Example: (SELECT ... ORDER BY ... LIMIT 1) UNION ALL (SELECT ... ORDER BY ... LIMIT 1)**
**CRITICAL COLUMN RULE: person_sumtotal table does NOT have a 'position' column. Use p.firstname, p.lastname, p.fullname instead. NEVER use p.position.**
**CRITICAL ACTIVITY PK RULE: activity_pk belongs to tbl_tmx_activity_sumtotal (alias 'act'), NOT tbl_tmx_attempt_sumtotal (alias 'a'). Use act.activity_pk, NEVER use a.activity_pk.**

**IMPORTANT: Generate SQL queries as single-line statements without unnecessary line breaks. The SQL should be compact and executable. Should not have any comments in them.**
**IMPORTANT: Generate one final SQL query, no multiple SQL queries.**
**IMPORTANT: Your entire response must be ONLY a valid JSON object with SQL and parsed_entities nothing else.**

{TEXT_TO_SQL_RULES}

### CRITICAL OUTPUT FORMAT REQUIREMENTS ###
**YOU MUST RESPOND WITH ONLY A VALID JSON OBJECT. NO EXPLANATIONS, NO STEP-BY-STEP BREAKDOWN, NO ADDITIONAL TEXT.**

**DO NOT INCLUDE:**
- Explanations or reasoning
- Step-by-step breakdowns
- Code examples
- Markdown formatting
- Any text before or after the JSON

**ONLY INCLUDE:**
- A single, valid JSON object with the exact structure shown below

### REQUIRED JSON FORMAT ###
{{
    "sql": "<YOUR_SQL_QUERY_HERE>",
    "parsed_entities": {{
        "column_filters": {{}},
        "time_filters": {{}},
        "aggregations": {{}},
        "group_by_columns": {{}}
    }}
}}

**REMEMBER: Your entire response must be ONLY this JSON object, nothing else.**
"""

calculated_field_instructions = """
#### Instructions for Calculated Field ####

The first structure is the special column marked as "Calculated Field". You need to interpret the purpose and calculation basis for these columns, then utilize them in the following text-to-sql generation tasks.
First, provide a brief explanation of what each field represents in the context of the schema, including how each field is computed using the relationships between models.
Then, during the following tasks, if the user queries pertain to any calculated fields defined in the database schema, ensure to utilize those calculated fields appropriately in the output SQL queries.
The goal is to accurately reflect the intent of the question in the SQL syntax, leveraging the pre-computed logic embedded within the calculated fields.

EXAMPLES:
The given schema is created by the SQL command:

CREATE TABLE orders (
  OrderId VARCHAR PRIMARY KEY,
  CustomerId VARCHAR,
  -- This column is a Calculated Field
  -- column expression: avg(reviews.Score)
  Rating DOUBLE,
  -- This column is a Calculated Field
  -- column expression: count(reviews.Id)
  ReviewCount BIGINT,
  -- This column is a Calculated Field
  -- column expression: count(order_items.ItemNumber)
  Size BIGINT,
  -- This column is a Calculated Field
  -- column expression: count(order_items.ItemNumber) > 1
  Large BOOLEAN,
  FOREIGN KEY (CustomerId) REFERENCES customers(Id)
);

Interpret the columns that are marked as Calculated Fields in the schema:
Rating (DOUBLE) - Calculated as the average score (avg) of the Score field from the reviews table where the reviews are associated with the order. This field represents the overall customer satisfaction rating for the order based on review scores.
ReviewCount (BIGINT) - Calculated by counting (count) the number of entries in the reviews table associated with this order. It measures the volume of customer feedback received for the order.
Size (BIGINT) - Represents the total number of items in the order, calculated by counting the number of item entries (ItemNumber) in the order_items table linked to this order. This field is useful for understanding the scale or size of an order.
Large (BOOLEAN) - A boolean value calculated to check if the number of items in the order exceeds one (count(order_items.ItemNumber) > 1). It indicates whether the order is considered large in terms of item quantity.

And if the user input queries like these:
1. "How many large orders have been placed by customer with ID 'C1234'?"
2. "What is the average customer rating for orders that were rated by more than 10 reviewers?"

For the first query:
First try to intepret the user query, the user wants to know the average rating for orders which have attracted significant review activity, specifically those with more than 10 reviews.
Then, according to the above intepretation about the given schema, the term 'Rating' is predefined in the Calculated Field of the 'orders' model. And, the number of reviews is also predefined in the 'ReviewCount' Calculated Field.
So utilize those Calculated Fields in the SQL generation process to give an answer like this:

SQL Query: SELECT AVG(Rating) FROM orders WHERE ReviewCount > 10
"""

metric_instructions = """
#### Instructions for Metric ####

Second, you will learn how to effectively utilize the special "metric" structure in text-to-SQL generation tasks.
Metrics in a data model simplify complex data analysis by structuring data through predefined dimensions and measures.
This structuring closely mirrors the concept of OLAP (Online Analytical Processing) cubes but is implemented in a more flexible and SQL-friendly manner.

The metric typically constructed of the following components:
1. Base Object
The "base object" of a metric indicates the primary data source or table that provides the raw data.
Metrics are constructed by selecting specific data points (dimensions and measures) from this base object, effectively creating a summarized or aggregated view of the data that can be queried like a normal table.
Base object is the attribute of the metric, showing the origin of this metric and is typically not used in the query.
2. Dimensions
Dimensions in a metric represent the various axes along which data can be segmented for analysis.
These are fields that provide a categorical breakdown of data.
Each dimension provides a unique perspective on the data, allowing users to "slice and dice" the data cube to view different facets of the information contained within the base dataset.
Dimensions are used as table columns in the querying process. Querying a dimension means to get the statistic from the certain perspective.
3. Measures
Measures are numerical or quantitative statistics calculated from the data. Measures are key results or outputs derived from data aggregation functions like SUM, COUNT, or AVG.
Measures are used as table columns in the querying process, and are the main querying items in the metric structure.
The expression of a measure represents the definition of the  that users are intrested in. Make sure to understand the meaning of measures from their expressions.
4. Time Grain
Time Grain specifies the granularity of time-based data aggregation, such as daily, monthly, or yearly, facilitating trend analysis over specified periods.

If the given schema contains the structures marked as 'metric', you should first interpret the metric schema based on the above definition.
Then, during the following tasks, if the user queries pertain to any metrics defined in the database schema, ensure to utilize those metrics appropriately in the output SQL queries.
The target is making complex data analysis more accessible and manageable by pre-aggregating data and structuring it using the metric structure, and supporting direct querying for business insights.

EXAMPLES:
The given schema is created by the SQL command:

/* This table is a metric */
/* Metric Base Object: orders */
CREATE TABLE Revenue (
  -- This column is a dimension
  PurchaseTimestamp TIMESTAMP,
  -- This column is a dimension
  CustomerId VARCHAR,
  -- This column is a dimension
  Status VARCHAR,
  -- This column is a measure
  -- expression: sum(order_items.Price)
  PriceSum DOUBLE,
  -- This column is a measure
  -- expression: count(OrderId)
  NumberOfOrders BIGINT
);

Interpret the metric with the understanding of the metric structure:
1. Base Object: orders
This is the primary data source for the metric.
The orders table provides the underlying data from which dimensions and measures are derived.
"""

from pydantic import BaseModel
from typing import Optional

class Configuration(BaseModel):
    class FiscalYear(BaseModel):
        start: str
        end: str

    class Timezone(BaseModel):
        name: str = "UTC"
        utc_offset: str = ""  # Deprecated, will be removed in the future

    def show_current_time(self):
        # Get the current time in the specified timezone
        tz = pytz.timezone(
            self.timezone.name
        )  # Assuming timezone.name contains the timezone string
        current_time = datetime.now(tz)

        return f"{current_time.strftime('%Y-%m-%d %A %H:%M:%S')}"  # YYYY-MM-DD weekday_name HH:MM:SS, ex: 2024-10-23 Wednesday 12:00:00

    fiscal_year: Optional[FiscalYear] = None
    language: Optional[str] = "English"
    timezone: Optional[Timezone] = Timezone()
   # Add any other fields as needed

# --- Calculation plan from Data Assistance (table retrieval -> SQL Planner handoff) ---
# When the intent planner / data assistance graph has run table retrieval and the calculation
# planner, it may pass field_instructions, metric_instructions, and silver time series
# suggestion. Use these to guide text-to-SQL generation (calculated columns, metrics, and
# advanced functions like mean, lag, lead, trend).

CALCULATION_PLAN_HEADER = """
#### Calculation Plan Instructions (from Data Assistance) ####
The following field and metric instructions were produced by the Calculation Planner from contextual table retrieval.
Use them to generate correct SQL: implement calculated fields and metrics as described.
For time series or silver-table suggestions, you may use advanced SQL: LAG, LEAD, window aggregates (AVG() OVER, SUM() OVER), DATE_TRUNC for grain, and trend expressions (e.g. value - LAG(value) OVER (PARTITION BY ... ORDER BY time)).
"""


def format_calculation_plan_instructions(calculation_plan: Optional[dict]) -> str:
    """
    Format a calculation_plan dict (from Data Assistance calculation_planner node) into
    prompt text for the SQL Planner (text-to-SQL). Includes field instructions, metric
    instructions, and optional silver time series calculation steps.
    """
    if not calculation_plan or not isinstance(calculation_plan, dict):
        return ""
    out = [CALCULATION_PLAN_HEADER]
    # Field instructions
    fields = calculation_plan.get("field_instructions") or []
    if fields:
        out.append("**Field instructions (implement as derived columns or WHERE logic):**")
        for f in fields:
            name = f.get("name", "")
            display = f.get("display_name", name)
            desc = f.get("description", "")
            basis = f.get("calculation_basis", "")
            cols = f.get("source_columns", [])
            out.append(f"- {display} ({name}): {desc}. Calculation: {basis}. Source columns: {cols}")
    # Metric instructions
    metrics = calculation_plan.get("metric_instructions") or []
    if metrics:
        out.append("\n**Metric instructions (implement as aggregations/dimensions):**")
        for m in metrics:
            name = m.get("name", "")
            display = m.get("display_name", name)
            base = m.get("base_table", "")
            measure = m.get("measure", "")
            dims = m.get("dimensions", [])
            grain = m.get("time_grain", "")
            out.append(f"- {display} ({name}): base_table={base}, measure={measure}, dimensions={dims}, time_grain={grain}")
    # Silver time series suggestion and calculation steps (natural language -> SQL hints)
    silver = calculation_plan.get("silver_time_series_suggestion")
    if silver and isinstance(silver, dict):
        if silver.get("suggest_silver_table") and silver.get("silver_table_suggestion"):
            tbl = silver["silver_table_suggestion"]
            out.append("\n**Silver time series suggestion:**")
            out.append(f"- Table purpose: {tbl.get('purpose', '')}; grain: {tbl.get('grain', '')}; source_tables: {tbl.get('source_tables', [])}")
        steps = silver.get("calculation_steps") or []
        if steps:
            out.append("\n**Calculation steps (implement using SQL; use LAG, LEAD, window aggregates, DATE_TRUNC, trend as needed):**")
            for s in steps:
                num = s.get("step_number", 0)
                desc = s.get("description", "")
                technique = s.get("technique", "")
                detail = s.get("detail", "")
                out.append(f"  {num}. [{technique}] {desc}. {detail}")
        funcs = silver.get("advanced_functions_used") or []
        if funcs:
            out.append(f"\nAdvanced functions to consider: {', '.join(funcs)}")
    reasoning = calculation_plan.get("reasoning", "").strip()
    if reasoning:
        out.append(f"\n**Reasoning:** {reasoning}")
    return "\n".join(out)


def construct_instructions(
    configuration: Configuration | None = Configuration(),
    has_calculated_field: bool = False,
    has_metric: bool = False,
    instructions: list[dict] | None = None,
    calculation_plan: Optional[dict] = None,
):
    _instructions = ""
    if configuration:
        if configuration.fiscal_year:
            _instructions += f"\n- For calendar year related computation, it should be started from {configuration.fiscal_year.start} to {configuration.fiscal_year.end}\n\n"
    if has_calculated_field:
        _instructions += calculated_field_instructions
    if has_metric:
        _instructions += metric_instructions
    if instructions:
        _instructions += "\n\n".join(
            [f"{instruction.get('instruction')}\n\n" for instruction in instructions]
        )
    if calculation_plan:
        _instructions += "\n\n" + format_calculation_plan_instructions(calculation_plan)

    return _instructions

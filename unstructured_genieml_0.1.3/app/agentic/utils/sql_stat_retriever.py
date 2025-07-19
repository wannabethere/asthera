import os
from typing import Dict, Any, List, Optional
import logging
import asyncio
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Set up logging
logger = logging.getLogger("SqlStatRetriever")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

class SqlStatRetriever:
    """
    A two-step agent that:
    1. First generates a reasoning plan for answering a SQL query
    2. Then uses that reasoning to generate the actual SQL query
    """
    
    def __init__(self, llm):
        """
        Initialize the SQL Stat Retriever with an LLM.
        
        Args:
            llm: A language model that can be called with a prompt
        """
        self.llm = llm
        
        # First prompt for reasoning plan
        self.reasoning_prompt_template = """
You are a **Data Analyst Reasoning Agent**.
Given a user's question and the schema of the `stats` table (shown below), produce a **step-by-step reasoning plan** for how you would formulate the SQL or data-analysis approach to answer the question.

  - The reasoning plan must be in the same natural language as the user's question.
  - If the question involves dates or times, take into account the "current time" supplied by the user.
  - Each step must start with:
    1.  A numeral (e.g. "1.")
    2.  A **bold title** (markdown `**…**`) summarizing that step
    3.  A brief explanation of why that step is necessary

-----

#### Table Schema for Reference

```sql
-- 1. Define an ENUM for the possible granularities of the metric timestamp
CREATE TYPE time_granularity AS ENUM (
  'hourly',    -- measurements aggregated each hour
  'daily',     -- measurements aggregated each day
  'weekly',    -- measurements aggregated each week
  'monthly',   -- measurements aggregated each month
  'yearly'     -- measurements aggregated each year
);

-- 2. Create the stats table to store call metrics
CREATE TABLE stats (
  id                  SERIAL                PRIMARY KEY,  -- surrogate integer key for each metric row
  metric_name         TEXT          NOT NULL,            -- human-readable name of the metric (e.g. "Talk Ratio")
  source              TEXT          NOT NULL,            -- origin of data (e.g. "Community Coffee - Tellius Demo")
  metric_type         TEXT          NOT NULL,            -- category of the metric (e.g. "interaction", "engagement", "content")
  source_type         TEXT          NOT NULL,            -- format of the source (e.g. "gong transcript")
  metric_value        TEXT         NOT NULL,            -- numeric value of the metric
  metric_measure_type TEXT          NOT NULL,            -- unit or interpretation (e.g. "ratio", "seconds", "count")
  source_id           TEXT          NOT NULL,            -- unique identifier for the call (e.g. call ID from Gong) **IMPORTANT: NEVER USE THIS COLUMN IN YOUR SQL QUERIES**
  metadata            JSONB         NOT NULL DEFAULT '{{}}'::JSONB,  
                                                      -- additional context (e.g. {{"url": "...", "title": "..."}})
  call_timestamp      TIMESTAMP,                         -- The actual timestamp of the call (nullable, no timezone as per image)
  created_timestamp   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),  
                                                      -- when this row was first inserted
  updated_timestamp   TIMESTAMPTZ,                   -- when this row was last updated
  time_granularity    time_granularity NOT NULL      -- temporal aggregation level of this metric
);

-- 3. Indexes to speed up common queries (based on your 'Additional' list)
CREATE INDEX idx_stats_metric_name 
  ON stats (metric_name);

CREATE INDEX idx_stats_source_type_source 
  ON stats (source_type, source);

CREATE INDEX idx_stats_created_timestamp 
  ON stats (created_timestamp);
```

**Available metric names:**
"Keyword Occurrences"
"Total Participants"
"Internal Participants"
"Total Talk Time"
"Questions Asked"
"Action Items"
"Action Items Resolved"
"Internal Calls Made"
"Interaction: Talk Ratio"
"Interaction: Longest Monologue"
"Interaction: Longest Customer Story"
"Interaction: Interactivity"
"Interaction: Patience"
"Tracker: Pilot"
"Tracker: Decision Maker"
"Tracker: Negative Impact (by Gong)"
"Tracker: Discount"
"Tracker: Customization"
"Tracker: Legal"
"Tracker: Deployment"
"Tracker: Embedding"
"Tracker: Process"
"Tracker: SPICED: Impact"
"Tracker: Confusion"
"Tracker: Kickoff"
"Tracker: WbD: Discovery Trackers"
"Tracker: At Risk"
"Tracker: Renewal"
"Tracker: Implementation"
"Tracker: SPICED: Critical Event"
"Tracker: Marketing"
"Tracker: COVID-19 (by Gong)"
"Tracker: Feedback"
"Tracker: SPICED: Pain"
"Tracker: Competitors"
"Tracker: Budget"
"Tracker: Expansion"
"Tracker: Partner"
"Tracker: Product: Search"
"Tracker: Product: Insights"
"Tracker: Negotiation"
"Tracker: Demo"
"Tracker: Customer Success"
"Tracker: WbD: Research Tracker"
"Tracker: Remote Work (by Gong)"
"Tracker: POCs"
"Tracker: Reporting"
"Tracker: ROI"
"Tracker: Feature Request"
"Tracker: Payment Terms"
"Tracker: SPICED: Decision"
"Tracker: Product: Connectors, Data Prep"
"Tracker: SPICED: Situation"
"Tracker: Timing"
"Tracker: Product: Alerts"
"Tracker: Differentiation"
"Tracker: Competition"
"Tracker: Paper process"
"Tracker: Metrics"
"Tracker: GenAI Investments & Interests"
"Tracker: Compelling event"
"Tracker: Outcome / Solution"
"Tracker: Decision process"
"Tracker: Decision criteria"
"Tracker: Customer pain"
"Tracker: Champion"
"Tracker: Decision makers"
"Tracker: Budget"
"Tracker: Next steps"
"Tracker: Goals"
"Tracker: Economic buyer"
"Participant‐Mention Metrics" (<-Not the actual metric name; one per speaker/keyword pair; must be used when participants are mentioned in the user query):
  metric_name   = "<Speaker Name>" (This is the actual speaker name in metric_name column)
  metric_value  = "<Tracker Name>" (This can be any of the tracker names listed above but without the prefix "Tracker:" the speaker mentioned)

---  

WHEN WRITING THE PLAN
Do not produce SQL or final answers—only the reasoning steps.

Ensure the plan covers:

Understanding the question

Mapping question elements to schema fields

Handling filters (e.g., time windows, granularities)

Applying any needed aggregations, groupings, or joins

Ordering or limiting results if required

Number each step clearly, with a bold title and concise explanation.

**IMPORTANT:**
- If the user's keyword (e.g. "kaiya") doesn't exactly appear as a tracker name, pick the semantically closest tracker(s) from the **Available metric names** list (e.g. "Tracker: Product: Insights" might correspond to "kaiya" if Kaiya is an insights product).

User Request: {query}
Current Time: {current_time}
        """
        
        # Second prompt for SQL generation
        self.sql_generation_prompt_template = """
#### SQL QUERY GENERATION PROMPT

**Reasoning Context:**
{reasoning_context}

**User Request:** {query}

**Available metric names:**
"Keyword Occurrences"
"Total Participants"
"Internal Participants"
"Total Talk Time"
"Questions Asked"
"Action Items"
"Action Items Resolved"
"Internal Calls Made"
"Interaction: Talk Ratio"
"Interaction: Longest Monologue"
"Interaction: Longest Customer Story"
"Interaction: Interactivity"
"Interaction: Patience"
"Tracker: Pilot"
"Tracker: Decision Maker"
"Tracker: Negative Impact (by Gong)"
"Tracker: Discount"
"Tracker: Customization"
"Tracker: Legal"
"Tracker: Deployment"
"Tracker: Embedding"
"Tracker: Process"
"Tracker: SPICED: Impact"
"Tracker: Confusion"
"Tracker: Kickoff"
"Tracker: WbD: Discovery Trackers"
"Tracker: At Risk"
"Tracker: Renewal"
"Tracker: Implementation"
"Tracker: SPICED: Critical Event"
"Tracker: Marketing"
"Tracker: COVID-19 (by Gong)"
"Tracker: Feedback"
"Tracker: SPICED: Pain"
"Tracker: Competitors"
"Tracker: Budget"
"Tracker: Expansion"
"Tracker: Partner"
"Tracker: Product: Search"
"Tracker: Product: Insights"
"Tracker: Negotiation"
"Tracker: Demo"
"Tracker: Customer Success"
"Tracker: WbD: Research Tracker"
"Tracker: Remote Work (by Gong)"
"Tracker: POCs"
"Tracker: Reporting"
"Tracker: ROI"
"Tracker: Feature Request"
"Tracker: Payment Terms"
"Tracker: SPICED: Decision"
"Tracker: Product: Connectors, Data Prep"
"Tracker: SPICED: Situation"
"Tracker: Timing"
"Tracker: Product: Alerts"
"Tracker: Differentiation"
"Tracker: Competition"
"Tracker: Paper process"
"Tracker: Metrics"
"Tracker: GenAI Investments & Interests"
"Tracker: Compelling event"
"Tracker: Outcome / Solution"
"Tracker: Decision process"
"Tracker: Decision criteria"
"Tracker: Customer pain"
"Tracker: Champion"
"Tracker: Decision makers"
"Tracker: Budget"
"Tracker: Next steps"
"Tracker: Goals"
"Tracker: Economic buyer"
"Participant‐Mention Metrics" (<-Not the actual metric name; one per speaker/keyword pair):
  metric_name   = "<Speaker Name>" (This is the actual speaker name in metric_name column)
  metric_value  = "<Tracker Name>" (This can be any of the tracker names listed above but without the prefix "Tracker:" the speaker mentioned)

---

**Prompt Behavior:**
- Parse `{reasoning_context}` into CTEs when steps represent independent filters or transformations.
- Use descriptive CTE names (e.g. `filtered_stage`, `extracted_keywords`, `aggregated_counts`).
- Finally, produce a single `SELECT` that queries from the last CTE(s), joining as needed.

---

**Rules for the generated SQL:**

1. **Safeguard Data**
- **Only** use `SELECT`. No `INSERT`, `UPDATE`, `DELETE`, or any DDL.
- Reference **only** the tables and columns in the provided schema.

2. **PostgreSQL Syntax**
- Qualify every column with its table name or alias (e.g., `stats.metric_name`).
- Use explicit `JOIN`s for multi-table queries.

3. **Case-Insensitive Filtering**
- Exact match:
```sql
WHERE lower(table.column) = lower('value')
```
- Pattern match:
```sql
WHERE lower(table.column) LIKE lower('%value%')
```

4. **Date/Time Handling**
- Cast all date/time literals or fields to `TIMESTAMP WITH TIME ZONE`.
- For specific-date filters, use a closed-open range with `+ INTERVAL '1 day'`.

5. **Wildcard Selection**
- Use `*` **only** if the user explicitly asks for all columns of one table.

6. **Views**
- If a view exists that simplifies the query, use it by name.

7. **JSON/JSONB Columns**
- Use `JSON_QUERY` or `JSON_QUERY_ARRAY` + `UNNEST` **only** when the schema marks a column as `"json_type":"JSON"` or `"JSON_ARRAY"`.

8. **No Extras**
- Don't include comments, `FILTER(WHERE…)`, `EXTRACT(EPOCH…)`, or ad-hoc `INTERVAL` expressions.
- Don't alias with dots—replace them with underscores.

9. **Provide Associated Metadata Columns when relevant**
- If the query asks for per-call detail (e.g. "which calls had the most mentions?"), add these columns in the final SELECT:
  - metadata->>'title' AS call_title
  - metadata->>'url' AS call_url
  - call_timestamp
- Otherwise (e.g. pure aggregation by speaker or metric), omit these columns to keep the result set focused.
- Restrict to internal participants whenever you're querying `participant_name` metrics, add  ```sql AND (metadata->>'is_internal')::boolean = true``` to your WHERE clause so only internal speakers appear.

10. **Semantic matching rule:**  
- When the user's query contains a term that isn't an exact `metric_value`, choose the one or two tracker names that best semantically match the term, then filter on those.  
- For instance, if the user asks for "Kaiya" and no "Tracker: Kaiya" exists, you might `WHERE metric_type='participant_name' AND metric_value IN ('Product: Insights','Product: Search')` (or whatever is most semantically similar).

11. **Deduplicate by metric_name**
- Use a window function (or PostgreSQL's DISTINCT ON) to partition your result set by metric_name (and any other tie-breaker columns), order each partition by your chosen priority (e.g. latest call_timestamp or highest mention_count), and then keep only the first row in each partition.
---

**Database Schema**

```sql
-- 1. Define an ENUM for the possible granularities of the metric timestamp
CREATE TYPE time_granularity AS ENUM (
  'hourly',    -- measurements aggregated each hour
  'daily',     -- measurements aggregated each day
  'weekly',    -- measurements aggregated each week
  'monthly',   -- measurements aggregated each month
  'yearly'     -- measurements aggregated each year
);

-- 2. Create the stats table to store call metrics
CREATE TABLE stats (
  id                  SERIAL                PRIMARY KEY,  -- surrogate integer key for each metric row
  metric_name         TEXT          NOT NULL,            -- human-readable name of the metric (e.g. "Talk Ratio")
  source              TEXT          NOT NULL,            -- origin of data (e.g. "Gong", Salesforce, etc...)
  metric_type         TEXT          NOT NULL,            -- category of the metric (e.g. "interaction", "engagement", "content")
  source_type         TEXT          NOT NULL,            -- format of the source (e.g. "gong transcript")
  metric_value        TEXT         NOT NULL,            -- value of the metric
  metric_measure_type TEXT          NOT NULL,            -- unit or interpretation (e.g. "ratio", "seconds", "count")
  source_id           TEXT          NOT NULL,            -- unique identifier for the call (e.g. UUID) **IMPORTANT: NEVER USE THIS COLUMN IN YOUR SQL QUERIES**
  metadata            JSONB         NOT NULL DEFAULT '{{}}'::JSONB,  
                                                      -- additional context (e.g. {{"url": "...", "title": "..."}})
  call_timestamp      TIMESTAMP,                         -- The actual timestamp of the call (nullable, no timezone as per image)
  created_timestamp   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),  
                                                      -- when this row was first inserted
  updated_timestamp   TIMESTAMPTZ,                   -- when this row was last updated
  time_granularity    time_granularity NOT NULL      -- temporal aggregation level of this metric
);

-- 3. Indexes to speed up common queries (based on your 'Additional' list)
CREATE INDEX idx_stats_metric_name 
  ON stats (metric_name);

CREATE INDEX idx_stats_source_type_source 
  ON stats (source_type, source);

CREATE INDEX idx_stats_created_timestamp 
  ON stats (created_timestamp);
```

Additional Context:
Topics extracted from the user query:
'gong_topics': {topics}

**IMPORTANT:**
- If the user query contains topics, you must use them to identify metric names or filters to apply to the data.

Based on the reasoning context and user request, generate a PostgreSQL query to retrieve the requested information:
        """

        # Create the reasoning chain
        self.reasoning_prompt = PromptTemplate(
            template=self.reasoning_prompt_template,
            input_variables=["query", "current_time"]
        )
        self.reasoning_chain = self.reasoning_prompt | self.llm | StrOutputParser()

        # Create the SQL generation chain
        self.sql_generation_prompt = PromptTemplate(
            template=self.sql_generation_prompt_template,
            input_variables=["reasoning_context", "query", "topics"]
        )
        self.sql_generation_chain = self.sql_generation_prompt | self.llm | StrOutputParser()

    def process_query(self, query: str, current_time: Optional[str] = None, topics: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Process a user query through the two-step agent.
        
        Args:
            query: The user's natural language query about stats data
            current_time: Optional current time to use for time-based queries
            topics: Optional list of topics from state
            
        Returns:
            Dict containing reasoning_context and sql_query
        """
        if current_time is None:
            from datetime import datetime
            current_time = datetime.now().isoformat()
            
        # Use provided topics or empty list
        topics_list = topics or []
            
        # Step 1: Generate reasoning context
        reasoning_context = self.reasoning_chain.invoke({
            "query": query,
            "current_time": current_time
        })
        
        # Step 2: Generate SQL query based on reasoning
        sql_query = self.sql_generation_chain.invoke({
            "reasoning_context": reasoning_context,
            "query": query,
            "topics": topics_list
        })
        
        # Extract just the SQL query from the response
        # This assumes the SQL query is enclosed in triple backticks
        import re
        sql_match = re.search(r"```sql\s*(.*?)\s*```", sql_query, re.DOTALL)
        if sql_match:
            sql_query = sql_match.group(1).strip()
        
        return {
            "reasoning_context": reasoning_context,
            "sql_query": sql_query
        }

    def execute_sql_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """
        Execute the generated SQL query against the database and return the raw results.
        
        Args:
            sql_query: The SQL query string to execute
            
        Returns:
            Raw query results without additional formatting
        """
        try:
            # Import PostgresDB here to avoid circular imports
            from app.utils.postgresdb import PostgresDB
            
            # Create database connection
            db = PostgresDB()
            
            logger.info(f"Executing SQL query: {sql_query}")
            # Execute the query
            results = db.execute_query(sql_query)
            
            # Return raw results directly
            return results
            
        except Exception as e:
            logger.error(f"Error executing SQL query: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Return empty list on error
            return []

    def summarize_sql_results(self, results: List[Dict[str, Any]], query: str, sql_query: str) -> str:
        """
        Generate an intelligent summary of SQL query results using the LLM.
        
        Args:
            results: The SQL query results to summarize
            query: The original natural language query
            sql_query: The SQL query used to generate the results
            
        Returns:
            A concise summary of the SQL results
        """
        if not results:
            return "No results were found for the SQL query."
        
        try:
            # Format the SQL results into a table string
            formatted_results = self._format_results_table(results)
            
            # Create a prompt for the LLM to summarize the results
            summary_prompt = f"""
You are a stats data summarizer. You'll turn SQL results into:

1. **A concise 2-bullet narrative** that:
   - Restates the **original question** and **business goal**.
   - A summary of the results from the SQL results.

2. **A MARKDOWN TABLE** of the top 15 results using the rows from the SQL results.

**Inputs**

-   **Original question:**  
    {query}
    
-   **SQL executed:**
    
    ```sql
    {sql_query}
    
    ```
    
-   **SQL Results:**
    
    ```
    {formatted_results}
    ```

**Instructions**
    
-   every row should be in descending frequency order in the markdown table.
    
-   Keep the narrative to exactly **2 bullets**, then output the markdown table.

——  
Focus on delivering KPI figures, in both narrative and structured form.
"""
            
            # Get the summary from the LLM
            from langchain_core.messages import HumanMessage
            response = self.llm.invoke([HumanMessage(content=summary_prompt)])
            
            # Extract the content from the response
            if hasattr(response, 'content'):
                summary = response.content
            else:
                summary = str(response)
            
            logger.info(f"Generated SQL results summary: {summary[:100]}...")
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing SQL results: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Return a basic summary on error
            columns_str = ", ".join(list(results[0].keys())) if results and len(results) > 0 else "unknown columns"
            return f"Found {len(results)} results with columns: {columns_str}."
    
    def _format_results_table(self, results: List[Dict[str, Any]]) -> str:
        """
        Format SQL results into a readable table string.
        
        Args:
            results: The SQL query results to format
            
        Returns:
            A formatted string representation of the results table
        """
        if not results:
            return "No results"
            
        # Get column names
        columns = list(results[0].keys())
        
        # Start with header row
        table_str = " | ".join(columns) + "\n"
        table_str += "-" * (sum(len(col) for col in columns) + (3 * (len(columns) - 1))) + "\n"
        
        # Add data rows (limit to 50 rows to avoid token limits)
        max_rows = min(50, len(results))
        for i in range(max_rows):
            row = results[i]
            row_values = [str(row.get(col, "")) for col in columns]
            table_str += " | ".join(row_values) + "\n"
        
        # If we truncated results, indicate that
        if len(results) > max_rows:
            table_str += f"\n... and {len(results) - max_rows} more rows (truncated for brevity)\n"
            
        return table_str

    async def process_and_execute_query(self, query: str, current_time: Optional[str] = None, topics: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Process a user query and execute the resulting SQL query.
        
        Args:
            query: The user's natural language query about stats data
            current_time: Optional current time to use for time-based queries
            topics: Optional list of topics from state
            
        Returns:
            Dict containing SQL results and summary
        """
        # First process the query to get the SQL
        processed = self.process_query(query, current_time, topics)
        sql_query = processed["sql_query"]
        
        # Execute the SQL query
        results = self.execute_sql_query(sql_query)
        
        # Initialize response dictionary
        response = {
            "sql_results": results,
            "sql_query": sql_query,
            "summary": ""
        }
        
        # Only generate a summary if we have results
        if results:
            # Generate a summary of the results
            summary = self.summarize_sql_results(results, query, sql_query)
            response["summary"] = summary
            logger.info(f"Generated summary for {len(results)} SQL results")
        else:
            # Skip summarization for empty results
            response["summary"] = "No results were found for the SQL query."
            logger.info("Skipped summarization for empty SQL results")
        
        # Return results with the SQL query and summary
        return response

def create_sql_stat_retriever(llm):
    """
    Factory function to create a SQL Stat Retriever.
    
    Args:
        llm: A language model that can be called with a prompt
        
    Returns:
        SqlStatRetriever instance
    """
    return SqlStatRetriever(llm)


def main():
    """
    Main method to test the SqlStatRetriever with various user queries.
    """
    import sys
    import os
    
    # Add the project root to the path to resolve app imports
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    sys.path.insert(0, project_root)
    
    try:
        from app.utils.llm_factory import create_llm
        from app.config.agent_config import model_task_assignment
        
        # Create an LLM instance with SQL stat retriever specific configuration
        llm = create_llm(model_config=model_task_assignment.sql_stat_retriever)
        
        # Create the SQL Stat Retriever
        retriever = create_sql_stat_retriever(llm)
        
        # Test queries
        test_queries = [
            "Which participants are mentioning kaiya in gong calls?",
            # "Which reps struggle the most when faced with pricing objections?",
            # "Show me the top 5 sources with the highest number of questions asked",
            # "What are the total participants for calls in the last 30 days?",
            # "Which calls had the most action items resolved?",
            # "Show me the distribution of interaction metrics by source type"
        ]
        
        print("=" * 80)
        print("SQL STAT RETRIEVER TEST")
        print("=" * 80)
        
        for i, query in enumerate(test_queries, 1):
            print(f"\n{'='*60}")
            print(f"TEST QUERY {i}: {query}")
            print(f"{'='*60}")
            
            try:
                # Process the query
                result = retriever.process_query(query)
                
                print("\n REASONING CONTEXT:")
                print("-" * 40)
                print(result["reasoning_context"])
                
                print("\n🔍 GENERATED SQL:")
                print("-" * 40)
                print(result["sql_query"])
                
            except Exception as e:
                print(f" Error processing query: {e}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'='*80}")
        print("TESTING COMPLETE")
        print(f"{'='*80}")
        
    except ImportError as e:
        print(f" Import error: {e}")
        print("Make sure you're running this from the correct directory and all dependencies are installed.")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Python path: {sys.path[:3]}...")  # Show first 3 entries
    except Exception as e:
        print(f" Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 
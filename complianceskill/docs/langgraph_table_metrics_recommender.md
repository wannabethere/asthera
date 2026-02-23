Lets create a new workflow engine:
- detection_engineer: Generates SIEM rules
- triage engineering: Searches for necessary steps to identify the key metrics and how to calculate them for each source.

Our goal is to generate a plan only using the given data sources and nothing else. 


User: "Build HIPAA breach detection..."
           ↓
    ┌─────────────┐
    │  INTENT     │
    │  CLASSIFIER │
    └──────┬──────┘
           ↓
    ┌─────────────┐
    │  PLANNER    │  ← NEW: Breaks into atomic steps
    └──────┬──────┘
           ↓
    ┌─────────────┐
    │  SUPERVISOR │  ← Routes based on plan
    └──────┬──────┘
           ↓
    ┌──────────────────────────────┐
    │  EXECUTION PHASE             │
    │  ┌─────────┐  ┌─────────┐  │
    │  │Framework│  │Detection│  │
    │  │Analyzer │  │Engineer │  │
    │  └────┬────┘  └────┬────┘  │
    └───────┼────────────┼────────┘
            ↓            ↓
    ┌──────────────────────────────┐
    │  VALIDATION PHASE  ← NEW     │
    │  ┌─────────┐  ┌─────────┐  │
    │  │Rule     │  │Playbook │  │
    │  │Validator│  │Validator│  │
    │  └────┬────┘  └────┬────┘  │
    └───────┼────────────┼────────┘
            ↓            ↓
         PASS?       FAIL?
            │            │
            ↓            ↓
    ┌─────────┐   ┌──────────┐
    │ SUCCESS │   │ FEEDBACK │
    │         │   │ LOOP     │ ← Iterative refinement
    └─────────┘   └────┬─────┘
                       │
                       └→ Back to generator

Lets skip XSOAR Recommendations in this flow:
1. Intent classifier breaksdown to recommend metrics, available tables for the purpose or suggest how to create silver tables or suggest gold table metrics. 
2. Planner then identifies the Framework controls to fetch, Correct Controls and Risks-- Helps Identify the MDL Focus Areas necessary for understanding the question.
Inputs for planner: 
    - Focus areas for each source-- These are hardcoded in the config 
    - Frameworks available 
Outputs for planner: 
 --Steps for performing the actions -- All semantic qustions with Reasoning (Each semantic question is used for searching in the vector store)
   - MDL table retrieval
   - Metrics lookups based
   - Framework controls look up 
   - Final plan of how to put together this playbook.
Lets come up with an example playbook template to be used that will be recommended and we will pick that up for generating the final version


3. Retrieval of these sources with relevancy scores 
    Sources to be used for finding the data:
    a. We will have the mdl tables for Final Version in the system -- Called ProjectId - (GoldStandardTables) for each category
    -- Assets, Ports, Vulnerabilities, Softwares, Patch, CVE etc...
    b. Metrics Registry
      -- Registry of metrics 
      -- Registry of metrics for each source.
    c. MDL Schemas for each source
    -- Search tables in mdl repository
    d. Fetch the relevant risks and controls.
4. Score the metrics, tables with their descriptions and purpose for the risks of given control by looking up
5. Score and validate the retrieved documentation for purposes of the goals. Drop unnecessary recommendation
6. Finally, look at the MDL and generate metrics,KPIs and widgets to show.
   - Given the data source
   - Given the GoldStandardTables 
   - Use the calculation node to generate the following
     - What will be a time series table from the source
     - What will be a silver table in the medallion architecture
     - What will be the gold table
     - Finally a set of over 10 recommendations of metrics, kpis and widgets 
        - Each metric as a natural language question.
        - Each metric calculation plan steps without any sql or data generation just natural language
        - Each metric calculation is based on SQL and available SQL functions nothing more at this time.


        



 
  


 


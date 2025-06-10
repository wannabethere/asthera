from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response, Depends
import logging
from typing import Dict, Any, Optional, List
import traceback
import uuid
import os
from io import BytesIO, StringIO
from collections import defaultdict, deque
from langchain_core.messages import HumanMessage
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import xlsx2csv as xlsx
import polars as pl
import json as j
import re
import matplotlib.pyplot as plt
from typing import AsyncGenerator

import pandas as pd
from passlib.context import CryptContext
from fastapi.responses import FileResponse
from app.settings import get_settings
from app.routes import thread as thread_router
from app.routes import team as team_router
from app.routes import invite as invite_router
from app.routes import auth, rbac, chat
from app.database import engine, Base, init_db, get_db
from app.utils.init_rbac import init_rbac
from app.bmodels import SignUpRequest, LoginRequest, ChatRequest, ChatResponse, ModelName, addChat, UserIn, CollaboratorRequest
from app.routes import organization, workspace
from app.routes.user import router as user_router

PLOT_DIR = "/tmp/ai_plots"  # Or any other path
os.makedirs(PLOT_DIR, exist_ok=True)
settings = get_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="GenieML API",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()

# Include routers with API_V1_STR prefix
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(rbac.router, prefix=settings.API_V1_STR)
app.include_router(thread_router.router, prefix=settings.API_V1_STR)
app.include_router(team_router.router, prefix=settings.API_V1_STR)
app.include_router(invite_router.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(organization.router, prefix=settings.API_V1_STR)
app.include_router(workspace.router, prefix=settings.API_V1_STR)
app.include_router(user_router, prefix=settings.API_V1_STR)

# Initialize RBAC system
#init_rbac()

# Global variables
chat_sessions: Dict[str, Dict[str, Any]] = {}
addedChats = {"AddedChats":[]}
thread_collaborators: Dict[str, List[Dict[str, str]]] = {}
chatHistory = defaultdict(lambda: {"sessionid": None, "Questions": deque(), "owner": None, "collaborators": []})
uploadedFiles = {"Files":deque(),"SavedFiles":defaultdict(lambda: {"FunFiles": deque()})}
task_metadata = {}
users_db = {}
logged_in_users = set()
# Create database tables
Base.metadata.create_all(bind=engine)

def extract_and_execute_plot(code_block: str, full_data: Optional[List[Dict]] = None) -> Optional[str]:
    try:
        import matplotlib.pyplot as plt
        import re
        import pandas as pd

        # Clean up code block (e.g., remove plt.show())
        code_block = re.sub(r'plt\.show\(\)', '', code_block)

        temp_file_path = os.path.join(PLOT_DIR, f"plot_{uuid.uuid4().hex}.png")

        # Convert full_data (list of dicts) to DataFrame if provided
        df = pd.DataFrame(full_data) if full_data else pd.DataFrame()

        # Prepare the exec environment
        plt.figure()
        exec(code_block, {"plt": plt, "df": df})

        if not plt.get_fignums():
            plt.plot([1, 2, 3], [3, 2, 1])
            plt.title("Fallback Plot")

        plt.savefig(temp_file_path)
        plt.close()
        return temp_file_path

    except Exception as e:
        logger.error(f"Plot execution failed: {e}")
        return None

def get_user_role(session_id: str, user_email: str) -> str:
    meta = task_metadata.get(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Session metadata not found")
    if user_email == meta.get("owner"):
        return "owner"
    return meta.get("collaborators", {}).get(user_email)

def check_permission(session_id: str, user_email: str, required_role: str):
    role = get_user_role(session_id, user_email)
    if role is None:
        raise HTTPException(status_code=403, detail="Access denied")
    if required_role == "read" and role in ["read", "read-write", "owner"]:
        return
    elif required_role == "read-write" and role in ["read-write", "owner"]:
        return
    elif required_role == "owner" and role == "owner":
        return
    raise HTTPException(status_code=403, detail="Insufficient permissions")

async def uploadfile(file: UploadFile, sessionid):
    fileType = vars(file)['headers'].get('content-type')
    contents = await file.read()
    filesize=len(contents)
    
    
    if file.filename.endswith('.xlsx') and fileType == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
        stream = BytesIO(contents)
        csvio = StringIO()
        xlsx.Xlsx2csv(stream,outputencoding="utf-8").convert(csvio)
        csvio.seek(0)
        fileInfo= {"file_id": str(uuid.uuid4()),
                "filename": file.filename,
                "file_type": "xlsx",
                "DataFrame": pl.read_csv(csvio).lazy(),
                "createdDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sessionId": sessionid,
                "size": (f"{filesize} B" if filesize < 1024 else f"{filesize / 1024:.2f} KB" if filesize < 1048576 else f"{filesize / 1048576:.2f} MB")
            
        }
        uploadedFiles["Files"].append(fileInfo)
        uploadedFiles["SavedFiles"][sessionid]["FunFiles"].append(fileInfo)
        print("Uploaded file info")
        return await analysis(sessionid)
        
    elif file.filename.endswith('.csv') and fileType=='text/csv':
        csvio = StringIO(contents.decode('utf-8'))
        fileInfo= {"file_id": str(uuid.uuid4()),
                "filename": file.filename,
                "file_type": "xlsx",
                "DataFrame": pl.read_csv(csvio).lazy(),
                "createdDate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sessionId": sessionid,
                "size": (f"{filesize} B" if filesize < 1024 else f"{filesize / 1024:.2f} KB" if filesize < 1048576 else f"{filesize / 1048576:.2f} MB")
            
        }
        uploadedFiles["Files"].append(fileInfo)
        uploadedFiles["SavedFiles"][sessionid]["FunFiles"].append(fileInfo)
        print("Uploaded file info")
        return await analysis(sessionid)
        
        
    else:
        return f"Hi Dude, Given format is not Supported ... {fileType}"
    

async def analysis(sessionid:str):
    print(f"I am analysis Functions with session id : {sessionid}")
    fun_files = uploadedFiles["SavedFiles"][sessionid]["FunFiles"]
    latestFile = fun_files[-1] if len(fun_files) > 1 else fun_files[0] if fun_files else None
    df = latestFile['DataFrame'].collect()
    global summary
    summary = {
    "head": df.head(5).to_dicts(),  # Preview top 5 rows
    "schema": {col: str(dtype) for col, dtype in df.schema.items()},  # Column names with types
    "columns": {
        col: str(dtype) for col, dtype in df.schema.items()  # Column names with data types for clarity
    },
    "stats": df.describe().to_dicts(),  # Descriptive statistics
    "null_counts": df.null_count().to_dict(as_series=False),  # Count of null values per column
    "unique_counts": {col: df[col].n_unique() for col in df.columns},  # Unique values per column
    "value_counts": {
        col: df[col].value_counts().sort(f"count", descending=True).head(5).to_dicts()
        for col, dtype in df.schema.items() if dtype in [pl.Utf8, pl.Categorical]
    },
    "cardinality": {col: df[col].n_unique() for col in df.columns},  # Cardinality info (number of unique values)
}

    if summary:
            
        del df
        return True
    else:
        return False

async def visualCalci(gmd, sessionid):
    print(f"I am visualCalci Function with gmd: {gmd}")

    
    graph_type = gmd.get("graph_type", "line")
    xaxis_col = gmd["xaxis"]["column_name"]
    xaxis_label = gmd["xaxis"]["label"]
    yaxis_col = gmd["yaxis"]["column_name"]
    yaxis_label = gmd["yaxis"]["label"]
    aggr = gmd["aggregation"]["method"].lower()
    tmeperd = gmd.get("time_period", "").lower() if gmd.get("time_period") else None
    print(tmeperd)
    filter_column = None
    filter_value = None

    filter_data = gmd.get("filter")

    if isinstance(filter_data, dict):
        filter_column = filter_data.get("column")
        filter_value = filter_data.get("value")
    elif isinstance(filter_data, str):
        # If it's just a string, maybe that's the column name and no value
        filter_column = filter_data
        filter_value = None
    else:
        filter_column = None
        filter_value = None

    
    

    
    fun_files = uploadedFiles["SavedFiles"][sessionid]["FunFiles"]
    latest_file = fun_files[-1] if fun_files else None
    if not latest_file:
        return {"error": "No data file available."}

    df = latest_file["DataFrame"].collect()

    if xaxis_col not in df.columns:
        return {"error": f"X-axis column '{xaxis_col}' not found."}
    if yaxis_col not in df.columns:
        return {"error": f"Y-axis column '{yaxis_col}' not found."}
    print(df[xaxis_col].dtype)
    
    if df[xaxis_col].dtype in (pl.Utf8,"String")  and tmeperd in ("month","year"):
        try:
            df = df.with_columns(
            pl.col(xaxis_col)
            .map_elements(lambda x: x.replace("/", "-") if isinstance(x, str) else x)
            .alias(xaxis_col)
        )

        
            df = df.with_columns(
            pl.col(xaxis_col).str.to_datetime("%Y-%m-%d", strict=False).alias(xaxis_col)
        )

            print(df.head(3),df[xaxis_col].dtype)
        except Exception as e:
            return {"error": f"Failed to parse datetime: {str(e)}"}

    
    if filter_column and filter_value is not None:
        if filter_column in df.columns:
            df = df.filter(pl.col(filter_column).str.contains(filter_value))
            print(df)
        else:
            return {"error": f"Filter column '{filter_column}' not found."}

    
    if tmeperd == "month":
        df = df.with_columns([
            pl.col(xaxis_col).dt.year().alias("Year"),
            pl.col(xaxis_col).dt.month().alias("Month")
        ])
        df = df.with_columns(
            pl.concat_str([
                pl.col("Month").cast(str).map_elements(lambda m: m.zfill(2)),
                pl.lit("-"),
                pl.col("Year").cast(str)
            ]).alias("MonthYear")
        )
        group_col = "MonthYear"

    elif tmeperd == "year":
        df = df.with_columns(
            pl.col(xaxis_col).dt.year().cast(str).alias("Year")
        )
        group_col = "Year"

    elif tmeperd == "day":
        df = df.with_columns(
            pl.col(xaxis_col).cast(pl.Date).alias("Day")
        )
        group_col = "Day"

    else:
        group_col = xaxis_col

    
    agg_label_map = {
        "sum": f"{yaxis_col}_sum",
        "mean": f"{yaxis_col}_mean",
        "count": f"{yaxis_col}_count",
        "min": f"{yaxis_col}_min",
        "max": f"{yaxis_col}_max",
        "average":f"{yaxis_col}_average"
    }

    if aggr not in agg_label_map:
        return {"error": f"Unsupported aggregation method '{aggr}'"}

    agg_col_name = agg_label_map[aggr]

    agg_expr = {
        "sum": pl.col(yaxis_col).sum().alias(agg_col_name),
        "mean": pl.col(yaxis_col).mean().alias(agg_col_name),
        "count": pl.col(yaxis_col).count().alias(agg_col_name),
        "min": pl.col(yaxis_col).min().alias(agg_col_name),
        "max": pl.col(yaxis_col).max().alias(agg_col_name),
        "average":pl.col(yaxis_col).mean().alias(agg_col_name)

    }[aggr]

    breakdown_col = None
    breakdown_label = None

    breakdown = gmd.get("breakdown", {})

    if isinstance(breakdown, dict):
        breakdown_col = breakdown.get("column")
        breakdown_label = breakdown.get("value")
    elif isinstance(breakdown, str):
        # If it's just a string, maybe that's the column name and no value
        breakdown_col = breakdown
        breakdown_label = None
    else:
        breakdown_col = None
        breakdown_label = None
    # breakdown_col = gmd.get("breakdown", {}).get("column") if gmd.get("breakdown").get("column") else None
    # breakdown_label = gmd.get("breakdown", {}).get("label") if gmd.get("breakdown").get("label") else None


    if graph_type in ("grouped bar", "stacked bar") and breakdown_col and breakdown_col in df.columns:
        result = df.group_by([group_col, breakdown_col]).agg(agg_expr).sort([group_col, breakdown_col])

        grouped_data = {}
        for row in result.iter_rows():
            group_value = row[0] 
            breakdown_value = row[1] 
            y_value = round(row[2], 1)

            if group_value not in grouped_data:
                grouped_data[group_value] = []

            grouped_data[group_value].append({
                "label": breakdown_value,
                "value": y_value
            })

        data = [
            {
                "group": group,
                "values": values
            }
            for group, values in grouped_data.items()
        ]

        return {
            "responseType":"visual",
            "graphType": graph_type,
            "summary":gmd['Graph Summary'],
            "graphData": data
        }

    
    else:
        result = df.group_by(group_col).agg(agg_expr).sort(group_col)
        data = [
            {
                "column": row[0],
                "value": round(row[1], 1),
                "label": yaxis_label
            }
            for row in result.iter_rows()
        ]

        return {
            "responseType":"visual",
            "graphType": graph_type,
            "summary":gmd['Graph Summary'],
            "graphData": data
        }

async def mathquery(metadata: dict,sessionid,cs,usrinp):


    group_by = metadata.get("group_by")
    value = metadata.get("value")
    aggregation = metadata.get("aggregation")
    filter_info = metadata.get("filter") if  metadata.get("filter") else None
    print("Filter_info",filter_info)
    top_n = metadata.get("top_n") if metadata.get("top_n") else 1
    print(top_n,type(top_n))
    fun_files = uploadedFiles["SavedFiles"][sessionid]["FunFiles"]
    latest_file = fun_files[-1] if fun_files else None
    if not latest_file:
        return {"error": "No data file available."}

    df = latest_file["DataFrame"].collect()
    filtercondition = None
    if isinstance(filter_info,list):
        for filter in filter_info:
            if filter and filter.get("column") and filter.get("value"):
                filter_col = filter["column"]
                filter_val = filter["value"]
                if df[filter_col].dtype == pl.Utf8:
                    condition= pl.col(filter_col).str.contains(str(filter_val))
                elif df[filter_col].dtype == pl.Int64 or df[filter_col].dtype == pl.Float64:
                    condition = pl.col(filter_col) == filter_val
                elif df[filter_col].dtype in (pl.Date, pl.Datetime):
                    condition = pl.col(filter_col).dt.year() == int(filter_val)
                else:
                    condition = pl.col(filter_col) == filter_val
                if filtercondition is None:
                    filtercondition = condition
                    print("Filterconditionj",filtercondition)
                else:
                    filtercondition = (filtercondition) & (condition)
                    print("Filtercondition in else block",filtercondition)
        if filtercondition is not None:
            df = df.filter(filtercondition)
    else:
        if filter_info:
           
            if filter_info and filter_info.get("column") and filter_info.get("value"):
                filter_col = filter_info["column"]
                filter_val = filter_info["value"]
                if df[filter_col] is not None and df[filter_col].dtype == pl.Utf8:
                    df = df.filter(pl.col(filter_col).str.contains(str(filter_val)))
                elif df[filter_col] is not None and df[filter_col].dtype == pl.Int64 or df[filter_col].dtype == pl.Float64:
                    df = df.filter(pl.col(filter_col) == filter_val)
                elif df[filter_col] is not None and df[filter_col].dtype in (pl.Date, pl.Datetime):
                    df = df.filter(pl.col(filter_col).dt.year() == int(filter_val))
                else:
                    if df[filter_col] is not None:
                        df = df.filter(pl.col(filter_col) == filter_val)
        else:
             print("Hi Bro, Filter Value is NUll or None For Your Question")

    
    agg_func_map = {
        "sum": pl.col(value).sum().alias(value),
        "mean": pl.col(value).mean().alias(value),
        "max": pl.col(value).max().alias(value),
        "min": pl.col(value).min().alias(value),
        "count": pl.col(value).count().alias(value)
    }

    if aggregation not in agg_func_map:
        raise ValueError(f"Unsupported aggregation method: {aggregation}")

    agg_expr = agg_func_map[aggregation]

    
    if not group_by:
        result = df.select(agg_expr)
    else:
        result = df.group_by(group_by).agg(agg_expr).sort(value, descending=True)

    # Handle top_n
    if group_by and top_n:
        if isinstance(group_by, list) and len(group_by) > 1:
            
            subgroup = group_by[-1]
            other_group = group_by[:-1]
            
            
            grouped = df.group_by(group_by).agg(agg_expr)
            
            
            result = (
                grouped
                .sort([subgroup, value], descending=[False, True])
                .group_by(subgroup)
                .head(top_n)
            )
    else:
        
        result = (
            df.group_by(group_by)
            .agg(agg_expr)
            .sort(value, descending=True)
            .head(top_n)
        )
    prompt = f""" user asked me this question {usrinp} and i got this answer {result.to_dicts()} please provide a summary about the result and some recommended questions"""
    vars(cs["graph"])["temperature"] = 0.2
    cs["state"]["messages"].append(HumanMessage(
        content=prompt
    ))
    new_state = cs["graph"].invoke(cs["state"], cs["config"])
    cs.update({"state": new_state})
    print("New State Message",new_state["messages"][-1].content)
    temp = new_state["messages"][-1].content
    print(temp, "temp type", type(temp))
    return {
        "responseType":"maths",
        "result": result.to_dicts(),
        "summary": temp
    }

async def InitialPrompts(userinput:str):
    prompt = None
    if summary is None :
        prompt = userinput if userinput else "Hi GenAI, How are You?"
        print(prompt,userinput)
        return prompt,userinput
    else:
        userquery= userinput if userinput else 'Analyze the data and provide me KPI metrics with some useful analysis questions related to data'
        prompt = f"""
You are a classification engine for user questions related to an uploaded dataset. Below is a summary of the dataset:

{summary}

Classify the following user question into one of the categories:

- **"summary"**: Overview, statistics, or general insights (e.g., "What is the total revenue?")
- **"math"**: Computation or aggregation (e.g., "What is the average sales by region?")
- **"visualization"**: Visualization request (e.g., "Create a bar chart for sales over time.")
- **"unrelated"**: Question unrelated to the dataset (e.g., "What is the capital of France?")

User Question: "{userquery}"

Return a **Raw JSON** like:
{{
  "category": "summary" | "math" | "visualization" | "unrelated",
  "reason": "Why this category was chosen."
}}
Do not wrap it in a string, or include escape characters.
### **Guidelines**:
- **"summary"**: Asks for dataset overview or statistics.
- **"math"**: Requests a computation (sum, average, count).
- **"visualization"**: Wants a chart or visual.
- **"unrelated"**: Question has no relation to the dataset.

"""
    print(prompt,userquery)
    return prompt,userquery

async def responsechecker(response_str):
    try:
        # Try to load the string as JSON
        parsed = j.loads(response_str)
        print("parsed in response checker",parsed)
        # If successful, return the dict
        return True,parsed
    except j.JSONDecodeError:
        # If it's not valid JSON, return the original string
        print("I am in Except block")
        return False,response_str

async def questionValidator(response,usrinp,cs,sessionid):
    dict,data = await responsechecker(response)
    print(type(data),"in questionValidator")
    if not dict:
        return data

    if data['category'] == "summary":
        return await summaryGenerator(usrinp,cs)
    elif data['category'] == "math":
        return await MathGenerator(usrinp,cs,sessionid)
    elif data['category'] == "visualization":
        return await VisualGenerator(usrinp,cs,sessionid)
    elif data['category'] == "unrelated":
        return await unrelatedGenerator(usrinp,cs,sessionid)
    else:
        return "Null"

async def summaryGenerator(usrinp,cs):
    print("Chart Session sended by Continue API in SummaryGenerator",usrinp)
    prompt = f"""You are a smart data analyst.

Given the dataset summary and a user question, analyze the dataset very deeply and return what you understand to a structured JSON response with the following keys:

{{
  "overview": "Briefly describe what the data is about and what the question focuses on. provide 4 lines don't include word dataset",
  "key_insights": "Explain key findings, trends, or patterns in a simple, narrative style.",
  "kpis": "provide all relevant key performance indicators or metrics based on given dataset.",
  "predictions": "If possible, provide trends or logical forecasts based on the data.",
  "recommended_questions": ["List of 2–3 follow-up questions the user might ask next."]
}}

Guidelines:
- Be concise, clear, and human-readable.
- Use a friendly, business-like tone.
- Avoid technical jargon or raw data unless essential.
- Respond with only the JSON object.
Dataset Summary:
{summary}
User Question:
"{usrinp}"
"""
    vars(cs["graph"])["temperature"] = 0.3
    cs["state"]["messages"].append(HumanMessage(
        content=prompt
    ))
    new_state = cs["graph"].invoke(cs["state"], cs["config"])
    cs.update({"state": new_state})
    print("New State Message",new_state["messages"][-1].content)
    temp = new_state["messages"][-1].content
    print(temp, "temp type", type(temp))
    return {
        "responseType":"Summary",
        "summary":temp
    }

async def VisualGenerator(usrinp,cs,sessionid):
    prompt = f"""
You are a data visualization assistant.

Given the dataset schema and a user question, generate the most **accurate and suitable graph metadata** for visualizing the data. Consider edge cases (like missing values, time series, or skewed distributions) and ensure the graph type aligns with the user's question **and** the data structure (categorical, numerical, date/time, etc.).

Return a **structured JSON object** with the following keys:

{{
  "graph_type": "Best graph type (e.g., line, bar, stacked bar, grouped bar, scatter, pie, histogram, etc.)",
  "Graph Summary": "Provide a brief summary explaining how the selected graph type (e.g., bar chart) will analyze the user Question. give some insights or recommended questions based on the below graph"
  "xaxis": {{
    "column_name": "Column name used for the x-axis",
    "label": "Label for the x-axis"
  }},
  "yaxis": {{
    "column_name": "Column name used for the y-axis",
    "label": "Label for the y-axis"
  }},
  "aggregation": {{
    "method": "Aggregation method (e.g., sum, average, count) if needed"
  }},
  "breakdown": {{
    "column": "Second categorical column for stacked/grouped charts if applicable, else null",
    "label": "Label for breakdown column"
  }},
  "filter": {{
    "column": "Any column to filter (if relevant), else null",
    "value": "Value to filter on, if applicable"
  }},
  "time_period": "Month, Year, or null if time-based data is not relevant",
  "edge_case_handling": "Explanation of how edge cases are addressed (e.g., missing data, outliers, non-uniform time intervals)"
}}

## Guidelines:
- Use the most suitable graph type (e.g., line for time series, grouped bar for comparing categories).
- Use "breakdown" only if two valid categorical columns exist.
- Choose correct aggregation (sum, avg, count) — never use it to form a new column name.
- Only use column names that exist in the provided schema — do **not invent** or guess (e.g., avoid "average_profit").
- `label` can be human-friendly, but `column_name` must exactly match schema.
- If the question mentions a missing column (e.g., "Region"), map to a close one like "Country" only if clearly logical.
- Handle edge cases (missing values, skewed data, empty categories).
- Use time fields (Month, Year) if present — never return "null" if time exists.
- Return only valid structured JSON — no extra text.


Dataset Schema:
{summary}

User Question:
"{usrinp}"

Respond with the **graph metadata in JSON format only**.
"""
    vars(cs["graph"])["temperature"] = 0.2
    cs["state"]["messages"].append(HumanMessage(
        content=prompt
    ))
    new_state = cs["graph"].invoke(cs["state"], cs["config"])
    cs.update({"state": new_state})
    print("New State Message",new_state["messages"][-1].content)
    temp = new_state["messages"][-1].content
    print(temp, "temp type", type(temp))
    return await visualCalci(j.loads(temp),sessionid)    

async def unrelatedGenerator(usrinp,cs,sessionid):
    prompt = f""" Answer the Question asked by User {usrinp} with detailed explanation having atleast 20 lines """
    vars(cs["graph"])["temperature"] = 0.2
    cs["state"]["messages"].append(HumanMessage(
        content=prompt
    ))
    new_state = cs["graph"].invoke(cs["state"], cs["config"])
    cs.update({"state": new_state})
    print("New State Message",new_state["messages"][-1].content)
    temp = new_state["messages"][-1].content
    print(temp, "temp type", type(temp))
    return {
        "responseType": "unrelated",
        "summary": temp
    }

async def MathGenerator(usrinp,cs,sessionid):
    prompt = f"""
The user has asked a math-related question. Extract the minimal metadata required to answer it using a Polars DataFrame.

Return the following in JSON format:

group_by: column name to group by (e.g., "Sales_Rep_Name", "MonthYear"). 
Only include this if the question asks to compare between categories (e.g., products, reps, dates). 
If the question is asking for a single overall value, set group_by to null.

value: the column that should be aggregated (e.g., "Total_Sale_Value")

aggregation: the aggregation method to apply (e.g., "sum", "max", "mean", "count")

filter: an object with column and value if any filter (e.g., {{"column": "Sale_Date", "value": "2024"}})

top_n: Based on question's context provide top or bottom results, specify number (e.g., 5), else null

Your job is to interpret the user's question and return this metadata.

User Question: "{usrinp}"
"""
    vars(cs["graph"])["temperature"] = 0.2
    cs["state"]["messages"].append(HumanMessage(
        content=prompt
    ))
    new_state = cs["graph"].invoke(cs["state"], cs["config"])
    cs.update({"state": new_state})
    print("New State Message",new_state["messages"][-1].content)
    temp = new_state["messages"][-1].content
    print(temp, "temp type", type(temp))
    return await mathquery(j.loads(temp),sessionid,cs,usrinp)
  
async def saveChatHistory(
    sessionid: str,
    CalInput: Any,
    response: Any,
    uploadedFiles: Optional[UploadFile] = None,
    question_id: Optional[str] = None,
    sender_email: str = None  
):
    file_name = getattr(uploadedFiles, "filename", None)
    question_id= question_id
    new_question = {
        "QuestionId": question_id,
        "Question": f"Summary-{file_name}" if file_name else CalInput,
        "response": response,
        "history": [],
        "isEdited": bool(question_id),
        "sender": sender_email  # Include sender info
    }

    if sessionid not in chatHistory:
        chatHistory[sessionid] = {
            "sessionid": sessionid,
            "Questions": [new_question],
            "owner": task_metadata.get(sessionid, {}).get("owner", ""),
            "collaborators": []
        }
    else:
        if question_id:
            found = False
            for q in chatHistory[sessionid]["Questions"]:
                if q["QuestionId"] == question_id:
                    previous_version = {
                        "Question": q["Question"],
                        "response": q["response"],
                        "sender": q.get("sender")
                    }
                    q.setdefault("history", []).append(previous_version)
                    q.update({
                        "Question": new_question["Question"],
                        "response": new_question["response"],
                        "isEdited": True,
                        "sender": sender_email  # update sender if edited
                    })
                    logger.info(f"[EDITED] Question ID: {question_id}")
                    logger.info(f"📝 Edit Details:\n→ Old: {previous_version['Question']}\n→ New: {new_question['Question']}")
                    found = True
                    break
            if not found:
                chatHistory[sessionid]["Questions"].append(new_question)
        else:
            chatHistory[sessionid]["Questions"].append(new_question)
            logger.info(f"[NEW QUESTION] Added to session {sessionid}")
 
    return new_question

async def delFile(fileid:str):
    print("I am delfile async Function",fileid)
    for file in uploadedFiles["Files"]:
        if file["file_id"] == fileid:
            uploadedFiles["Files"].remove(file)
            return {"message": "File deleted successfully"}
    return {"message": "File not found"}
     


@app.post("/signup")
async def signup(request: SignUpRequest):
    if request.email in users_db:
        raise HTTPException(status_code=400, detail="User already exists")

    hashed_password = pwd_context.hash(request.password)
    users_db[request.email] = {
        "name": request.name,
        "email": request.email,
        "hashed_password": hashed_password,
    }
    print(f"users = {users_db}")

    return {
        "email": request.email,
        "name": request.name,
        "message": "Signup successful"
    }


@app.get("/all-users")
async def get_all_users():
    print("users_db:", users_db)
    return {"users": list(users_db.values())}

#
    
#
    

    



#API: To get All Uploaded Files
@app.get("/chat/uploadedFiles",name="Get Uploaded Files")
async def get_uploaded_files():
    """Get all uploaded files"""
    if not uploadedFiles["Files"]:
        raise HTTPException(status_code=404, detail="No files found")
    responsedata = [
        {
            "file_id": file["file_id"],
            "filename": file["filename"],
            "file_type": file["file_type"],
            "createdDate": file["createdDate"],
            "sessionId": file["sessionId"],
            "size": file["size"]
            

        }
        for file in uploadedFiles["Files"]
    ]

    return {"uploadedFiles": responsedata}

@app.post("/uploadfile", name="Upload File Only")
async def upload_file_api(
    session_id: Optional[str] = Form(None),
    file: UploadFile = File(...)
):
    try:
       
        json_preview = await uploadfile(session_id, file)
        
       
        file_info = uploadedFiles["Files"][-1] if uploadedFiles["Files"] else None
 
        if not file_info:
            raise HTTPException(status_code=500, detail="File was not saved correctly")
 
        return {
            "message": "File uploaded successfully",
            "file_id": file_info["file_id"],
            "filename": file_info["filename"],
            "file_type": file_info["file_type"],
            "createdDate": file_info["createdDate"],
            "session_id": session_id,
            "size": file_info["size"],
            "preview": json_preview
        }
 
    except Exception as e:
        logger.error(f"Upload API error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to upload file")
    

#API: To get a specific file
@app.get("/uploadedfiles/{file_id}/download")
async def download_file(file_id: str):
    """Allow downloading the file associated with a session"""
    for session_files in uploadedFiles.values():
        for file_info in session_files:
            if file_info["file_id"] == file_id:
                
                filename = file_info["filename"]
                content = file_info["content"]
                
               
                return Response(
                    content, 
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # MIME type for Excel file
                    headers={"Content-Disposition": f"attachment; filename={filename}"}
                )

#API: To delete a file
@app.delete("/chat/delete/uploadedFiles/{fileid}",name="Delete Uploaded Files")
async def deleteUploadedFile(fileid:str):
    print(fileid)
    """Delete a file"""
    delete = await delFile(fileid)
    return delete


@app.post("/newchat/", name="New Chat through MyFiles")
async def newChat(fileid:str):
    pass

@app.get("/chat/{userid}/chathistory", name='LoggedIn User Chat History')
async def getWholeChatHistory(userid: str):
    if userid == 22 :
        return {'chatHistory' : chatHistory}
    
@app.get("/chatHistory/{sessionid}",name="Get Chat History")
async def getChatHistory(sessionid:str):
    if sessionid in chatHistory:
        return {"chatHistory":chatHistory[sessionid]}

@app.post("/chat/add-chats/")
async def addChats(addchat:addChat):
    print("Add charts",addchat,type(addchat))
    if addchat:
        addedChats['AddedChats'].append(vars(addchat))
        return {"message":"Hi Dude, chat Added to Report Successfully"}
    else:
        return {"message":"Hi Dude, Unable to add. Please Try again Later"}
 
@app.get("/chat/getAddedCharts")
async def getAddedCharts():
    return addedChats 

@app.get("/")
async def root():
    return {"message": "Welcome to GenieML API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    
    # Log startup information
    logger.info(f"Starting API server on {settings.API_HOST}:{settings.API_PORT}")
    logger.info(f"Environment: {settings.ENV}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Start the server
    uvicorn.run(
        "main:app", 
        host=settings.API_HOST, 
        port=settings.API_PORT, 
        reload=settings.DEBUG
    )
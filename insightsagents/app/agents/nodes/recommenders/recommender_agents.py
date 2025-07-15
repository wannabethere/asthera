import os
import json
from typing import List, Dict, Any, TypedDict, Optional, Union, Callable, Tuple
import numpy as np
import pandas as pd

# LangChain imports
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.agents import AgentExecutor, create_react_agent, create_openai_functions_agent
from langchain.tools import Tool, BaseTool
from langchain_core.prompts.chat import SystemMessagePromptTemplate, HumanMessagePromptTemplate, MessagesPlaceholder
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import PromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers.json import JsonOutputParser
from langchain_core.output_parsers.string import StrOutputParser
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.memory import ConversationBufferMemory
from langchain.tools import tool
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field

from app.agents.models.dsmodels import DocumentInfo, InsightManagerState, DocumentGrade, RecommendedQuestion
from app.utils.df_utils import get_schema_and_top_values
from app.agents.nodes.recommenders.ds_agents import (
    RetrievalInsightsAgent,
    SummarizeDatasetAgent,
    RecommendQuestionsAgent,
    RecommendationGradingAgent
)

# Define actor types with their personalities and approaches
ACTOR_TYPES = {
    "data_scientist": {
        "persona": "Expert data scientist focused on data analysis, statistical modeling, and insights generation",
        "approach": "Analytical, detail-oriented, uses statistical terminology, focuses on data patterns and correlations",
        "question_style": "Technical, specific, focused on statistical significance and data quality"
    },
    "business_analyst": {
        "persona": "Business analyst who translates data into business insights and strategic recommendations",
        "approach": "Business-focused, emphasizes ROI and KPIs, translates technical concepts to business language",
        "question_style": "Business-oriented, focused on actionable insights and business impact"
    },
    "product_manager": {
        "persona": "Product manager focused on user needs, feature requirements, and product roadmaps",
        "approach": "User-centric, focuses on outcomes and use cases, frames data in terms of product improvements",
        "question_style": "User-focused, oriented toward product improvements and feature prioritization"
    },
    "executive": {
        "persona": "Executive level leader focused on high-level strategy and business impact",
        "approach": "Strategic, concise, focuses on bottom-line impacts and competitive advantages",
        "question_style": "High-level, strategic, focused on competitive positioning and market trends"
    }
}
FUNCTIONS_AVAILABLE = [
  {"name": "form_time_cohorts", "category": "cohort_analysis", "description": "Form cohorts based on time periods" },
  {"name": "form_behavioral_cohorts", "category": "cohort_analysis", "description": "Form cohorts based on user behavior" },
  {"name": "calculate_retention", "category": "cohort_analysis", "description": "Calculate retention metrics for cohorts" },
  {"name": "calculate_conversion", "category": "cohort_analysis", "description": "Calculate conversion funnel metrics for cohorts" },
  {"name": "calculate_lifetime_value", "category": "cohort_analysis", "description": "Calculate lifetime value metrics for cohorts" },
  {"name": "analyze_funnel", "category": "funnel_analysis", "description": "Analyze a user funnel using the existing CohortPipe framework" },
  {"name": "analyze_funnel_by_time", "category": "funnel_analysis", "description": "Analyze funnel performance over time using the existing CohortPipe framework" },
  {"name": "analyze_funnel_by_segment", "category": "funnel_analysis", "description": "Analyze funnel performance by user segments" },
  {"name": "analyze_user_paths", "category": "funnel_analysis", "description": "Analyze common user paths through the funnel" },
  {"name": "get_funnel_summary", "category": "funnel_analysis", "description": "Get a summary of funnel analysis results" },
  {"name": "compare_segments", "category": "funnel_analysis", "description": "Compare funnel performance across different segments" },
  {"name": "lead", "category": "time_series_analysis", "description": "Create lead (future) values for specified columns" },
  {"name": "lag", "category": "time_series_analysis", "description": "Create lag (past) values for specified columns" },
  {"name": "variance_analysis", "category": "time_series_analysis", "description": "Calculate variance and standard deviation for time series data" },
  {"name": "distribution_analysis", "category": "time_series_analysis", "description": "Analyze the distribution of values in specified columns" },
  {"name": "cumulative_distribution", "category": "time_series_analysis", "description": "Calculate cumulative distribution for specified columns" },
  {"name": "custom_calculation", "category": "time_series_analysis", "description": "Apply a custom calculation function to the time series data" },
  {"name": "dbscan", "category": "segmentation", "description": "DBSCAN Clustering for segmentation" },
  {"name": "hierarchical", "category": "segmentation", "description": "Hierarchical Clustering for segmentation" },
  {"name": "rule_based", "category": "segmentation", "description": "Rule-Based Segmentation" },
  {"name": "generate_summary", "category": "segmentation", "description": "Segment Summary Generator" },
  {"name": "get_segment_data", "category": "segmentation", "description": "Segment Data Extractor" },
  {"name": "compare_algorithms", "category": "segmentation", "description": "Algorithm Comparison" },
  {"name": "aggregate_by_time", "category": "trend_analysis", "description": "Aggregate data by time periods" },
  {"name": "calculate_growth_rates", "category": "trend_analysis", "description": "Calculate growth rates for aggregated metrics" },
  {"name": "calculate_moving_average", "category": "trend_analysis", "description": "Calculate moving averages for time series data" },
  {"name": "decompose_trend", "category": "trend_analysis", "description": "Decompose time series into trend, seasonal, and residual components" },
  {"name": "forecast_metric", "category": "trend_analysis", "description": "Forecast future values of    a metric" },
  {"name": "calculate_statistical_trend", "category": "trend_analysis", "description": "Calculate statistical significance of trends" },
  {"name": "compare_periods", "category": "trend_analysis", "description": "Compare metrics across different time periods" },
  {"name": "get_top_metrics", "category": "trend_analysis", "description": "Get top performing metrics based on specified criteria" },
]

class RetrievalInsightsAgent:
    """Agent responsible for document retrieval and initial filtering."""
    
    def __init__(self, vectorstore, llm):
        self.vectorstore = vectorstore
        self.llm = llm
        
        @tool
        def search_documents(query: str) -> List[Dict[str, Any]]:
            """Search for relevant documents using the query."""
            docs = self.vectorstore.similarity_search(query, k=5) 
            return [{"content": doc.page_content, "metadata": doc.metadata} for doc in docs]
        
        self.tools = [search_documents]
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a document retrieval expert. Your goal is to retrieve 
            relevant documents to answer the given question. Consider:
            1. Key terms and concepts in the question
            2. Potential variations of the query
            3. Related topics that might be relevant
            """),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        self.agent = (
            {
                "input": lambda x: x["input"],
                "chat_history": lambda x: x["chat_history"],
                "agent_scratchpad": lambda x: format_to_openai_function_messages(
                    x["intermediate_steps"]
                )
            }
            | self.prompt
            | self.llm
            | OpenAIFunctionsAgentOutputParser()
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True
        )

    def retrieve(self, question: str, state: InsightManagerState=None) -> Tuple[List[DocumentInfo], List[str]]:
        """Retrieve relevant documents for the question."""
        result = self.agent_executor.invoke(
            {
                "input": question,
                "chat_history": []
            }
        )
        
        docs = []
        content = []
        if isinstance(result['output'], list) or isinstance(result['output'], dict):
            for doc in result['output']:
                if isinstance(doc, dict):
                    docs.append(DocumentInfo(page_content=doc.get('content', ''), metadata=doc.get('metadata', {})))
                    content.append(doc.get('content', ''))
                else:
                    docs.append(DocumentInfo(page_content=doc, metadata={}))
                    content.append(doc)
        else:
            docs.append(DocumentInfo(page_content=result['output'], metadata={}))
            content.append(result['output'])
            
        return docs, content

class SummarizeDatasetAgent:
    """Agent responsible for summarizing a dataset."""
    def __init__(self, llm):
        self.llm = llm
        self.prompt = PromptTemplate(
            template = """
            I require the services of your team to help me reach my goal.
            You are the manager of a data science team whose goal is to help stakeholders within your company extract actionable 
            insights from their data. 
            You have access to a team of highly skilled data scientists that can answer complex questions about the data.
            You call the shots and they do the work.
            Your ultimate deliverable is a report that summarizes the findings and makes hypothesis for any trend or anomaly that was found.
            question: {question}
            context: {context}
            goal: {goal}
            schema: {schema}
            sample: {sample}
            top_values: {top_values}
            Instructions:
                * Given a context and a goal, and all the history of <question_i><answer_i> pairs from the above list generate the 3 top actionable insights.
                * Make sure they don't offer actions and the summary should be more about highlights of the findings
                * Output each insight within this tag <insight></insight>.
                * Each insight should be a meaningful conclusion that can be acquired from the analysis in laymans terms and should be as quantiative as possible and should aggregate the findings.
            """,
            input_variables=["question", "sample", "schema", "top_values", "context", "goal"]
        )
        self.agent = self.prompt | self.llm | StrOutputParser()      
    
    def summarize(self, dataset_path: str, question: str, state: InsightManagerState) -> str:
        """Summarize the dataset."""
        df = self._read_dataset(dataset_path)
        schema, top_values = self._get_schema_and_top_values(df)
        state['schema'] = schema
        state['top_values'] = top_values
        state['sample'] = df
        return self.summarize_dataframe(df, question, state)
    
    def summarize_dataframe(self, dataframe: pd.DataFrame, question: str, state: InsightManagerState) -> str:
        """Summarize the dataframe."""
        return self.agent.invoke({
            "question": question, 
            "dataset": dataframe, 
            "sample": dataframe.head(), 
            "schema": dataframe.columns.tolist(), 
            "top_values": dataframe.describe(), 
            "context": state.get('context', ''), 
            "goal": state.get('goal', '')
        })
    
    def _read_dataset(self, path: str) -> pd.DataFrame:
        """Read the dataset from a file path."""
        if path.endswith('.csv'):
            return pd.read_csv(path)
        elif path.endswith('.xlsx') or path.endswith('.xls'):
            return pd.read_excel(path)
        elif path.endswith('.json'):
            return pd.read_json(path)
        else:
            raise ValueError(f"Unsupported file format: {path}")
    
    def _get_schema_and_top_values(self, df: pd.DataFrame) -> Tuple[List[str], Dict[str, Any]]:
        """Extract schema and top values from a dataframe."""
        schema = df.columns.tolist()
        top_values = {}
        
        # Get top values for each column
        for col in schema:
            if df[col].dtype == 'object' or df[col].dtype == 'category':
                # For categorical columns
                top_values[col] = df[col].value_counts().head(5).to_dict()
            else:
                # For numerical columns
                top_values[col] = {
                    "min": df[col].min() if not pd.isna(df[col].min()) else None,
                    "max": df[col].max() if not pd.isna(df[col].max()) else None,
                    "mean": df[col].mean() if not pd.isna(df[col].mean()) else None,
                    "median": df[col].median() if not pd.isna(df[col].median()) else None
                }
        
        return schema, top_values

class RecommendQuestionsAgent:
    """Agent responsible for recommending questions."""
    def __init__(self, llm):
        self.llm = llm
        self.prompt = PromptTemplate(
            template="""
            You are a data science team manager. You have a team of highly skilled data scientists that can answer complex questions about the data.
            Given the following context:
            <context>{context}</context>

            Given the following goal:
            <goal>{goal}</goal>

            Given the following schema:
            <schema>{schema}</schema>

            Instructions:
            * Write a list of questions to be solved by the data scientists in your team to explore my data and reach my goal.
            * Explore diverse aspects of the data, and ask questions that are relevant to my goal.
            * Categorize the questions into KPIs, EDA (Univariate, Bivariate, Multivariate) and Analysis (Trends, Anomalies, etc.) questions.
            * You must ask the right questions to surface anything interesting (trends, anomalies, etc.)
            * Make sure these can realistically be answered based on the data schema.
            * The insights that your team will extract will be used to generate a report.
            * Each question should only have one part, that is a single '?' at the end which only require a single answer.
            * Do not number the questions.
            * You can produce at most {max_questions} questions for each type of question. Example 10 max questions for KPIs, 10 max questions for EDA, 10 max questions for Analysis. Stop generation after that.
            * For each type question, please provide a chain of thought of how you picked the example question from the possible insights.
            * Most importantly, each question must be enclosed within json tags. Refer to the example response below:

            Example Insights:
            {similar_insights}
            Example JSON response should include the following fields:
                "kpis": [
                    "type": "metric", "question": "What is the average age of the customers?", "chain_of_thought": "I picked the question because it is a metric question and it is relevant to the goal."
                    "type": "metric", "question": "What is the distribution of the customers based on their age?", "chain_of_thought": "I picked the question because it is a metric question and it is relevant to the goal."
                    "type": "operations", "question": "What is the distribution of the customers based on their age?", "chain_of_thought": "I picked the question because it is a metric question and it is relevant to the goal."
                ],
                "eda": [
                    "type": "univariate", "question": "What is the average age of the customers?", "chain_of_thought": "I picked the question because it is a univariate question and it is relevant to the goal."
                    "type": "bivariate", "question": "What is the distribution of the customers based on their age?", "chain_of_thought": "I picked the question because it is a bivariate question and it is relevant to the goal."
                ],
                "features": [
                    "type": "feature", "question": "What is the average age of the customers?", "chain_of_thought": "I picked the question because it is a feature question and it is relevant to the goal."
                    "type": "feature", "question": "What is the distribution of the customers based on their age?", "chain_of_thought": "I picked the question because it is a feature question and it is relevant to the goal."
                ],
                "analysis": [
                    "type": "trend", "question": "What is the average age of the customers?", "chain_of_thought": "I picked the question because it is a trend question and it is relevant to the goal."
                    "type": "anomaly", "question": "What is the distribution of the customers based on their age?", "chain_of_thought": "I picked the question because it is an anomaly question and it is relevant to the goal."
                ]
            

            ### Response:
            """,
            input_variables=["context", "goal", "schema", "similar_insights", "max_questions"]
        )
        self.agent = self.prompt | self.llm | JsonOutputParser()
    
    def recommend_questions(self, state: InsightManagerState) -> Dict[str, Any]:
        """Recommend questions."""
        return self.agent.invoke({
            "context": state.get('context', ''), 
            "goal": state.get('goal', ''), 
            "schema": state.get('schema', []), 
            "similar_insights": state.get('similar_insights', []), 
            "max_questions": state.get('max_questions', 5)
        })

class RecommendationGradingAgent:
    """Agent responsible for grading recommendation questions relevance."""
    
    def __init__(self, llm):
        self.llm = llm
        self.prompt = PromptTemplate(
            template="""You are a expert data science team who are helping grade the questions for analysis. Grade each document's 
            relevance to the question on a scale of 0.0 to 1.0. Provide clear 
            reasoning for your grades. Consider:
            1. Direct relevance to the question
            2. Information completeness
            3. Factual importance
            4. Context applicability
            5. Parse the recommendations json and grade each question based on the above criteria
            6. Grade each question based on the type of question it is and the context of the question
            7. Grade each question based on the relevance to the goal
            8. Return the sorted list of recommendations based on the grade
            Question: {question}
            Recommendations: {recommendations} - List of recommendations
            context: {context}
            goal: {goal}
            schema: {schema}
            
            Grade this document's relevance and explain your reasoning.
            Respond in JSON format with 'relevance_score' and 'reasoning' and 'preamble context' for the grade fields.
            """,
            input_variables=["question", "recommendations", "context", "goal", "schema"]
        )
        self.retrieval_grader = self.prompt | self.llm | JsonOutputParser()
    
    def grade_document(self, question: str, state: InsightManagerState) -> DocumentGrade:
        """Grade a single document's relevance."""
        response = self.retrieval_grader.invoke({
            "question": question, 
            "recommendations": state.get('recommendations', {}), 
            "context": state.get('context', ''), 
            "goal": state.get('goal', ''), 
            "schema": state.get('schema', [])
        })
        
        return response

    
class InsightVectorStoreTool(BaseTool):
    """Tool for retrieving insights from the vector store with self-evaluation."""
    
    #name = "insight_vector_store_tool"
    #description = "Retrieves and evaluates relevant insights and examples from the vector store based on the query"
    #return_direct = False
    
    # Define these as class variables to satisfy Pydantic
    vector_store: Any = None
    llm: Any = None

    def __init__(self, vector_store, llm,**kwargs):
        super().__init__(
           name = "dataset_info_tool",
           description = "Retrieves information about the dataset structure, schema, and sample data",
           vector_store=vector_store, llm=llm, **kwargs
        )
        self.vector_store = vector_store
        self.llm = llm
    
    def _run(self, query: str) -> str:
        """Use the vector store to get relevant insights with self-evaluation."""
        # Retrieve candidate documents
        if not hasattr(self.vector_store, 'semantic_search'):
            # Fallback to similarity_search if semantic_search doesn't exist
            search_method = getattr(self.vector_store, 'similarity_search', None)
            if search_method is None:
                return "Vector store doesn't have search capability."
            results = search_method(query, k=5)
        else:
            results = self.vector_store.semantic_search(query, k=5)
        
        if not results:
            return "No relevant insights found."
        
        
        # Self-evaluation of retrieved documents
        evaluated_results = []
        for i, doc in enumerate(results):
            # Evaluate relevance using the LLM
            eval_prompt = PromptTemplate(
                template="""
                Query: {query}
                Document: {doc.page_content if hasattr(doc, 'page_content') else doc}
                On a scale of 1-10, how relevant is this document to the query?
                Consider:
                1. Direct relevance to the specific query
                    2. Usefulness for generating relevant questions
                3. Quality and specificity of the insight
                
                Provide a single number score and a brief explanation.
                """,
                input_variables=["query", "doc"]
            )
            
            evaluation = eval_prompt | self.llm | StrOutputParser()
            eval_score_text = evaluation.invoke({"query": query, "doc": doc})
            
            # Extract score from evaluation
            try:
                # Try to extract just the numeric score
                eval_score_text = evaluation.strip().split('\\n')[0]
                eval_score = float(eval_score_text.split(':')[-1].strip()) if ':' in eval_score_text else float(eval_score_text)
            except:
                # If parsing fails, default to using a middle score
                eval_score = 5
            
            # Calculate vector similarity score (if available)
            vector_score = 0
            if hasattr(doc, 'similarity'):
                vector_score = doc.similarity
            
            evaluated_results.append({
                "doc": doc,
                "eval_score": eval_score,
                "evaluation": evaluation,
                "combined_score": eval_score  # If vector_score is available: (eval_score * 0.7) + (vector_score * 0.3)
            })
        
        # Sort by combined score and take top 3
        evaluated_results.sort(key=lambda x: x["combined_score"], reverse=True)
        top_results = evaluated_results[:3]
        
        formatted_results = []
        for i, result in enumerate(top_results):
            doc = result["doc"]
            doc_content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            formatted_results.append(
                f"Insight {i+1} (relevance: {result['combined_score']:.1f}/10): {doc_content}"
            )
        
        return "\n\n".join(formatted_results)

class DatasetInfoTool(BaseTool):
    """Tool for accessing dataset information."""
    
    #name = "dataset_info_tool"
    #description = "Retrieves information about the dataset structure, schema, and sample data"
    dataset_description: str = Field(description="Description of the dataset")
    sample_data: Any = Field(description="Sample data from the dataset")
    
    def __init__(self, dataset_description, sample_data, **kwargs):
        super().__init__(
            name = "dataset_info_tool",
            description = "Retrieves information about the dataset structure, schema, and sample data",
            dataset_description=dataset_description,
            sample_data=sample_data,
            **kwargs
        )
        self.dataset_description = dataset_description
        self.sample_data = sample_data
    
    def _run(self, query: str = "") -> str:
        """Return information about the dataset."""
        # If a specific query is provided, we could filter the information
        if "schema" in query.lower():
            # Return just the schema information
            if isinstance(self.sample_data, pd.DataFrame):
                schema = self.sample_data.dtypes.to_dict()
                return f"Dataset schema:\n{json.dumps({k: str(v) for k, v in schema.items()}, indent=2)}"
            elif isinstance(self.sample_data, dict):
                schema = {k: type(v).__name__ for k, v in self.sample_data.items()}
                return f"Dataset schema:\n{json.dumps(schema, indent=2)}"
            elif isinstance(self.sample_data, list) and self.sample_data:
                sample = self.sample_data[0] if self.sample_data else {}
                if isinstance(sample, dict):
                    schema = {k: type(v).__name__ for k, v in sample.items()}
                    return f"Dataset schema (based on first record):\n{json.dumps(schema, indent=2)}"
        
        # Default: return full dataset description and a sample
        result = f"Dataset description: {self.dataset_description}\n\n"
        
        if isinstance(self.sample_data, pd.DataFrame):
            sample_str = self.sample_data.head(3).to_json(orient='records', indent=2)
            result += f"Sample data (showing 3 records):\n{sample_str}"
        elif isinstance(self.sample_data, list):
            sample_size = min(3, len(self.sample_data))
            sample_str = json.dumps(self.sample_data[:sample_size], indent=2)
            result += f"Sample data (showing {sample_size} records):\n{sample_str}"
        else:
            result += f"Sample data:\n{json.dumps(self.sample_data, indent=2)}"
            
        return result

class QuestionEvaluator:
    """Evaluates the quality of questions based on various criteria."""
    
    def __init__(self, llm):
        self.llm = llm
        # Cache to store previous evaluations
        self.evaluation_cache = {}
    def evaluate_question(self, question: str, goal: str, schema: list, context: str = "") -> Dict[str, Any]:
        """Evaluate a question based on multiple dimensions."""
        # Check if we already evaluated this question with these parameters
        cache_key = f"{question}_{goal}_{','.join(schema)}_{context}"
        if cache_key in self.evaluation_cache:
            return self.evaluation_cache[cache_key]
            
        prompt = f"""
        You are a data science expert evaluating the quality of analytical questions.
        
        Evaluate the following question based on the context, goal, and data schema:
        
        Question: {question}
        
        Goal: {goal}
        
        Data Schema: {', '.join(schema)}
        
        Context: {context}
        
        Please score this question on the following dimensions (1-10 scale):
        1. Relevance: How directly does this question address the stated goal?
        2. Specificity: How precise and well-defined is this question?
        3. Answerability: Can this question be answered with the available data schema?
        4. Insight Potential: How likely is this question to lead to valuable insights?
        5. Business Impact: How actionable would the answer to this question be?
        
        For each dimension, provide a score and a brief justification.
        Also provide an overall score and a summary of the question's strengths and weaknesses.
        
        Your response MUST be a valid JSON object with the following structure, and nothing else:
        {{
            "relevance": {{
                "score": X,
                "justification": "Brief explanation"
            }},
            "specificity": {{
                "score": X,
                "justification": "Brief explanation"
            }},
            "answerability": {{
                "score": X,
                "justification": "Brief explanation"
            }},
            "insight_potential": {{
                "score": X,
                "justification": "Brief explanation"
            }},
            "business_impact": {{
                "score": X,
                "justification": "Brief explanation"
            }},
            "overall": {{
                "score": X,
                "summary": "Overall assessment"
            }}
        }}
        
        IMPORTANT: Return ONLY the JSON with no additional text, markdown formatting, or explanations.
        """
        
        try:
            response = self.llm.invoke(prompt)
            
            # Extract the JSON from the response
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
                
            # Clean up the response text to ensure it's valid JSON
            # Remove any leading/trailing whitespace, backticks, or markdown formatting
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.startswith('```'):
                response_text = response_text[3:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            try:
                # First try to parse the entire text as JSON
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from the text
                json_pattern = re.compile(r'({.*})', re.DOTALL)
                json_match = json_pattern.search(response_text)
                
                if json_match:
                    json_str = json_match.group(1)
                    result = json.loads(json_str)
                else:
                    # If no JSON found, create a default response
                    print(f"Could not extract JSON from response: {response_text[:100]}...")
                    result = {
                        "overall": {
                            "score": 5,
                            "summary": "Unable to evaluate question due to parsing error."
                        }
                    }
            
            # Validate the result has the expected structure
            if "overall" not in result or not isinstance(result["overall"], dict) or "score" not in result["overall"]:
                # If missing required fields, add default ones
                result["overall"] = result.get("overall", {})
                result["overall"]["score"] = result["overall"].get("score", 5)
                result["overall"]["summary"] = result["overall"].get("summary", "Partial evaluation completed.")
            
            # Cache the result
            self.evaluation_cache[cache_key] = result
            return result
            
        except Exception as e:
            print(f"Error getting scores from LLM: {e}")
            # Return a default evaluation object
            default_result = {
                "relevance": {"score": 5, "justification": "Automatic score due to evaluation error."},
                "specificity": {"score": 5, "justification": "Automatic score due to evaluation error."},
                "answerability": {"score": 5, "justification": "Automatic score due to evaluation error."},
                "insight_potential": {"score": 5, "justification": "Automatic score due to evaluation error."},
                "business_impact": {"score": 5, "justification": "Automatic score due to evaluation error."},
                "overall": {"score": 5, "summary": f"Error during evaluation: {str(e)}"}
            }
            self.evaluation_cache[cache_key] = default_result
            return default_result

    def calculate_precision_recall(self, recommended_questions: List[str], ideal_questions: List[str]) -> Dict[str, float]:
        """
        Calculate precision and recall for question recommendations.
        
        Args:
            recommended_questions: List of questions recommended by the system
            ideal_questions: List of ideal questions that should be recommended (gold standard)
            
        Returns:
            Dictionary with precision, recall, and F1 scores
        """
        if not recommended_questions or not ideal_questions:
            return {
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0
            }
        
        # Use LLM to determine matches (more flexible than exact string matching)
        matches = 0
        
        for rec_q in recommended_questions:
            # For each recommended question, check if it semantically matches any ideal question
            for ideal_q in ideal_questions:
                match_prompt = f"""
                Determine if these two questions are semantically equivalent:
                
                Question 1: {rec_q}
                Question 2: {ideal_q}
                
                Consider them equivalent if they are asking for the same information, even if worded differently.
                Answer with only 'Yes' or 'No'.
                """
                
                response = self.llm.predict(match_prompt).strip().lower()
                
                if response == 'yes':
                    matches += 1
                    break  # Move to next recommended question once a match is found
        
        # Calculate precision and recall
        precision = matches / len(recommended_questions) if recommended_questions else 0
        recall = matches / len(ideal_questions) if ideal_questions else 0
        
        # Calculate F1 score
        f1_score = 0
        if precision + recall > 0:
            f1_score = 2 * (precision * recall) / (precision + recall)
        
        return {
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score
        }
    
    def batch_evaluate_questions(self, questions: List[str], goal: str, schema: list, context: str = "") -> List[Dict[str, Any]]:
        """Evaluate multiple questions and return their evaluations."""
        evaluations = []
        
        for question in questions:
            evaluation = self.evaluate_question(question, goal, schema, context)
            evaluations.append({
                "question": question,
                "evaluation": evaluation,
                "score": evaluation.get("overall", {}).get("score", 5)
            })
        
        # Sort by score
        evaluations.sort(key=lambda x: x["score"], reverse=True)
        
        return evaluations

class IntegratedRecommendationSystem:
    """Main system that integrates dataset summarization, question recommendation and drill-down."""
    
    def __init__(
        self,
        llm=None,
        vector_store=None,
        insights_vector_store=None,
        examples_vector_store=None,
    ):
        # Initialize LLM
            
        self.llm = llm
            
        # Store vectorstores
        self.vector_store = vector_store
        self.insights_vector_store = insights_vector_store
        self.examples_vector_store = examples_vector_store
        
        # Initialize the question evaluator
        self.evaluator = QuestionEvaluator(self.llm)
        
        # Initialize state
        self.state = InsightManagerState()
        
        # Initialize agents (will be created when needed)
        self.summarize_agent = SummarizeDatasetAgent(self.llm)
        self.retrieval_agent = RetrievalInsightsAgent(self.insights_vector_store, self.llm) if self.insights_vector_store else None
        self.recommendation_grading_agent = RecommendationGradingAgent(self.llm)
        
        # Current recommendation agent (set when initialized)
        self.current_recommendation_agent = None
        
    def summarize_dataset(self, dataset_path: str, question: str, context: str, goal: str) -> str:
        """Summarize the dataset and update state."""
        # Update state with context and goal
        self.state['context'] = context
        self.state['goal'] = goal
        
        return self.summarize_agent.summarize(dataset_path, question, self.state)
    
    def summarize_dataframe(self, dataframe: pd.DataFrame, question: str, context: str, goal: str) -> str:
        """Summarize a dataframe and update state."""
        # Update state with context and goal
        self.state['context'] = context
        self.state['goal'] = goal
        
        return self.summarize_agent.summarize_dataframe(dataframe, question, self.state)
        
    def initialize_recommendation_agent(self, actor_type: str, goal: str, dataset_description: str, sample_data: Any) -> List[Dict[str, Any]]:
        """Initialize a recommendation agent with specific actor type and goal."""
        self.current_recommendation_agent = QuestionRecommendationAgent(
            llm=self.llm,
            actor_type=actor_type,
            goal=goal,
            insight_vector_store=self.insights_vector_store,
            function_vector_store=self.vector_store,
            dataset_description=dataset_description,
            sample_data=sample_data,
            evaluator=self.evaluator
        )
        
        # Get and return initial questions
        return self.current_recommendation_agent.get_initial_questions()
    
    def get_drill_down_questions(self, selected_question: str) -> List[Dict[str, Any]]:
        """Get drill-down questions for a selected question."""
        if not self.current_recommendation_agent:
            raise ValueError("No recommendation agent initialized.")
            
        return self.current_recommendation_agent.get_drill_down_questions(selected_question)
    
    def recommend_questions(self, context: str, goal: str, schema: list, max_questions: int = 5) -> Dict[str, Any]:
        """Recommend questions based on context, goal, and schema."""
        # Update state
        self.state['context'] = context
        self.state['goal'] = goal
        self.state['schema'] = schema
        self.state['max_questions'] = max_questions
        
        # Get similar insights if available
        if self.insights_vector_store:
            similar_insights = self.get_similar_insights(goal, context)
            self.state['similar_insights'] = similar_insights
        else:
            self.state['similar_insights'] = []
        
        # Create recommend questions agent
        recommend_agent = RecommendQuestionsAgent(self.llm)
        
        # Get recommendations
        recommendations = recommend_agent.recommend_questions(self.state)
        self.state['recommendations'] = recommendations
        
        # Grade recommendations if needed
        graded_recommendations = self.grade_recommendations(goal, recommendations)
        
        return graded_recommendations
    
    def get_similar_insights(self, goal: str, context: str) -> List[str]:
        """Get similar insights from the insights vector store."""
        if not self.insights_vector_store:
            return []
            
        query = f"Goal: {goal}. Context: {context}"
        
        try:
            docs = self.insights_vector_store.similarity_search(query, k=3)
            return [doc.page_content if hasattr(doc, 'page_content') else str(doc) for doc in docs]
        except Exception as e:
            print(f"Error retrieving similar insights: {e}")
            return []
    
    def grade_recommendations(self, question: str, recommendations: Dict[str, Any]) -> Dict[str, Any]:
        """Grade recommendations for relevance."""
        if self.recommendation_grading_agent:
            try:
                graded_data = self.recommendation_grading_agent.grade_document(question, self.state)
                return graded_data
            except Exception as e:
                print(f"Error grading recommendations: {e}")
        
        # Return original recommendations if grading fails
        return recommendations
    
    def evaluate_questions(self, questions: List[str]) -> List[Dict[str, Any]]:
        """Evaluate a list of questions using the evaluator."""
        return self.evaluator.batch_evaluate_questions(
            questions=questions,
            goal=self.state.get('goal', ''),
            schema=self.state.get('schema', []),
            context=self.state.get('context', '')
        )
        
    def calculate_question_metrics(self, recommended_questions: List[str], ideal_questions: List[str]) -> Dict[str, float]:
        """Calculate precision, recall, and F1 score for recommended questions."""
        return self.evaluator.calculate_precision_recall(recommended_questions, ideal_questions)


class QuestionRecommendationAgent:
    """Agent that recommends and evaluates relevant questions based on context."""
    
    def __init__(
        self,
        llm,
        actor_type: str,
        goal: str,
        insight_vector_store,
        function_vector_store,
        dataset_description: str,
        sample_data: Any,
        evaluator: QuestionEvaluator
    ):
        self.llm = llm
        self.actor_type = actor_type
        self.goal = goal
        self.memory = ConversationBufferMemory(return_messages=True)
        self.evaluator = evaluator
        # Set up question cache
        self.question_cache = {}
        self.tools = json.dumps(FUNCTIONS_AVAILABLE)
        
        # Validate actor type
        if actor_type not in ACTOR_TYPES:
            raise ValueError(f"Invalid actor type: {actor_type}. Available types: {list(ACTOR_TYPES.keys())}")
        
        # Create tools
        self.tools = [
            InsightVectorStoreTool(
                vector_store=insight_vector_store,
                llm=llm
            ),
            InsightVectorStoreTool(
                vector_store=function_vector_store,
                llm=llm
            ),
            DatasetInfoTool(
                dataset_description=dataset_description,
                sample_data=sample_data
            )
        ]
        
        # Create the prompt for the initial question recommendation with evaluation
        self.init_question_prompt = ChatPromptTemplate.from_messages([
            ("system",
                f"""You are an AI assistant acting as a {ACTOR_TYPES[actor_type]['persona']}. 
                    Your approach is {ACTOR_TYPES[actor_type]['approach']}.
                    Your questions should reflect {ACTOR_TYPES[actor_type]['question_style']}.
                    
                    The user's goal is: {goal}
                    
                    PROCESS:
                    1. First, use the tools to gather relevant insights and dataset information.
                    2. Then, generate 8-10 candidate questions that would help achieve the user's goal.
                    3. Evaluate each question using the following criteria:
                    - Relevance to the user's goal (scale 1-10)
                    - Alignment with insights from the vector store (scale 1-10)
                    - Specificity and actionability (scale 1-10)
                    - Appropriateness for the {actor_type} role (scale 1-10)
                    4. Calculate a combined score for each question.
                    5. Select the top 5 questions based on their scores.
                    
                    In your final response, provide:
                    1. A numbered list of the top 5 questions.
                    2. For each question, include the score in parentheses.
                    
                    Each question should be direct, specific, and actionable.
                    
                    Available tools: {{tools}}
                """
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}")
        ])
        
        # Create the prompt for drill-down question recommendation with evaluation
        self.drill_down_prompt = ChatPromptTemplate.from_messages([
            ("system",
                f"""You are an AI assistant acting as a {ACTOR_TYPES[actor_type]['persona']}. 
                    Your approach is {ACTOR_TYPES[actor_type]['approach']}.
                    Your questions should reflect {ACTOR_TYPES[actor_type]['question_style']}.
                    
                    The user's goal is: {goal}
                    
                    The user has selected this question to explore: "{{selected_question}}"
                    
                    PROCESS:
                    1. First, use the tools to gather relevant insights and dataset information specifically related to the selected question.
                    2. Then, generate 6-8 candidate follow-up questions that would help explore this topic in greater depth.
                    3. Evaluate each question using the following criteria:
                    - Relevance to the selected question (scale 1-10)
                    - Builds upon insights from the vector store (scale 1-10)
                    - Provides meaningful new information beyond the selected question (scale 1-10)
                    - Appropriateness for the {actor_type} role (scale 1-10)
                    4. Calculate a combined score for each question.
                    5. Select the top 3-4 questions based on their scores.
                    
                    In your final response, provide:
                    1. A numbered list of the top 3-4 drill-down questions.
                    2. For each question, include the score in parentheses.
                    
                    Each question should be direct, specific, and actionable.
                    
                    Available tools: {{tools}}
                """
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}")
        ])
        self.init_question_agent = (
            {
                "input": lambda x: x["input"],
                "chat_history": lambda x: x.get("chat_history", []),
                "agent_scratchpad": lambda x: format_to_openai_function_messages(x.get("intermediate_steps", [])),
                "tools": lambda x: self.tools
            }
            | self.init_question_prompt
            | self.llm
            | OpenAIFunctionsAgentOutputParser()
        )

        self.drill_down_agent = (
            {
                "input": lambda x: x["input"],
                "chat_history": lambda x: x.get("chat_history", []),
                "agent_scratchpad": lambda x: format_to_openai_function_messages(x.get("intermediate_steps", [])),
                "tools": lambda x: self.tools,
                "selected_question": lambda x: x.get("selected_question", "")
            }
            | self.drill_down_prompt
            | self.llm
            | OpenAIFunctionsAgentOutputParser()
        )

        # Create executors
        self.init_question_executor = AgentExecutor(
            agent=self.init_question_agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )

        self.drill_down_executor = AgentExecutor(
            agent=self.drill_down_agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )
        
    def evaluate_question_against_insights(self, question: str, insights: List[str]) -> Dict[str, Any]:
        """Evaluate a single question against retrieved insights."""
        evaluation_prompt = PromptTemplate(
            template="""
            Question: {question}    
            Available insights:
            {insights}
            
            Evaluate this question on a scale of 1-10 for the following criteria:
            1. Relevance to the insights (How well does it connect to the provided insights?)
            2. Potential for valuable answers (How likely would answers be useful?)
            3. Specificity (How specific and focused is the question?)
            4. Actionability (How actionable are potential answers to this question?)
            
            For each criterion, provide a score and brief justification.
            Then provide an overall score out of 10.
            """,
            input_variables=["question", "insights"]
        )
        
        evaluation_result = evaluation_prompt | self.llm | StrOutputParser()
        evaluation_result = evaluation_result.invoke({"question": question, "insights": json.dumps(insights)})
        # Extract the overall score (simplified extraction)
        overall_score = None
        for line in evaluation_result.split('\n'):
            if "overall" in line.lower() and "score" in line.lower():
                try:
                    # Try to extract score from text like "Overall score: 8/10"
                    score_text = line.split(':')[1].strip()
                    if '/' in score_text:
                        score_num, score_denom = score_text.split('/')
                        overall_score = float(score_num) / float(score_denom) * 10
                    else:
                        # Just a number
                        overall_score = float(''.join(c for c in score_text if c.isdigit() or c == '.'))
                except:
                    # If parsing fails, default to None
                    pass
        
        return {
            "question": question,
            "evaluation": evaluation_result,
            "overall_score": overall_score
        }
    
    def get_initial_questions(self) -> List[Dict[str, Any]]:
        """Generate and evaluate initial relevant questions based on the context."""
        response = self.init_question_executor.invoke({
            "input": f"Suggest and evaluate relevant questions for a {self.actor_type} trying to {self.goal}"
        })
        # Check the response type and extract the output
        if isinstance(response, dict) and 'output' in response:
            response_text = response['output']
        else:
            response_text = str(response)
        print("Initial Questions: ", response_text)
        # Parse the questions and their scores from the response
        questions = []
        for line in response_text.split('\n'):
            line = line.strip()
            if line and line[0].isdigit() and '. ' in line:
                # Extract the question and score if present
                question_text = line.split('. ', 1)[1]
                
                # Look for a score in parentheses at the end
                score = None
                if '(' in question_text and question_text.endswith(')'):
                    try:
                        score_part = question_text.split('(')[-1].strip(')')
                        if '/' in score_part:
                            score_num, score_denom = score_part.split('/')
                            score = float(score_num) / float(score_denom) * 10
                        else:
                            score = float(score_part)
                        
                        # Remove the score from the question text
                        question_text = question_text.split(' (')[0].strip()
                    except ValueError:
                        # If parsing fails, just use the whole text as the question
                        pass
                
                # Evaluate the question using our evaluator
                if self.evaluator:
                    evaluation = self.evaluator.evaluate_question(
                        question=question_text,
                        goal=self.goal,
                        schema=[],  # This should be filled with actual schema
                        context=""  # This should be filled with actual context
                    )
                    detailed_score = evaluation.get("overall", {}).get("score", None)
                    
                    # Use the evaluator's score if available, otherwise use the extracted score
                    if detailed_score is not None:
                        score = detailed_score
                
                questions.append({
                    "text": question_text,
                    "score": score,
                    "evaluation": evaluation if self.evaluator else None
                })
        
        # Sort by score if available
        if all(q["score"] is not None for q in questions):
            questions.sort(key=lambda x: x["score"], reverse=True)
        
        return questions
    
    def get_drill_down_questions(self, selected_question: str) -> List[Dict[str, Any]]:
        """Generate and evaluate drill-down questions based on the selected question."""
        # Extract the base question without the score part
        base_question = selected_question
        if " (Score:" in selected_question:
            base_question = selected_question.split(" (Score:")[0]
        
        # Add the selected question to chat history
        self.add_to_chat_history(f"I want to explore: {base_question}")
        
        response = self.drill_down_executor.invoke({
            "input": f"The user selected this question: '{base_question}'. Suggest and evaluate relevant drill-down questions.",
        })
        
        if isinstance(response, dict) and 'output' in response:
            response_text = response['output']
        else:
            response_text = str(response)
        print("Drill Down Questions: ", response_text)
        # Parse the questions and their scores from the response
        questions = []
        for line in response_text.split('\n'):
            line = line.strip()
            if line and line[0].isdigit() and '. ' in line:
                # Extract the question and score if present
                question_text = line.split('. ', 1)[1]
                
                # Look for a score in parentheses at the end
                score = None
                if '(' in question_text and question_text.endswith(')'):
                    try:
                        score_part = question_text.split('(')[-1].strip(')')
                        if '/' in score_part:
                            score_num, score_denom = score_part.split('/')
                            score = float(score_num) / float(score_denom) * 10
                        else:
                            score = float(score_part)
                        
                        # Remove the score from the question text
                        question_text = question_text.split(' (')[0].strip()
                    except ValueError:
                        # If parsing fails, just use the whole text as the question
                        pass
                
                # Evaluate the question using our evaluator
                if self.evaluator:
                    evaluation = self.evaluator.evaluate_question(
                        question=question_text,
                        goal=self.goal,
                        schema=[],  # This should be filled with actual schema
                        context=""  # This should be filled with actual context
                    )
                    detailed_score = evaluation.get("overall", {}).get("score", None)
                    
                    # Use the evaluator's score if available, otherwise use the extracted score
                    if detailed_score is not None:
                        score = detailed_score
                
                questions.append({
                    "text": question_text,
                    "score": score,
                    "evaluation": evaluation if self.evaluator else None
                })
        
        # Sort by score if available
        if all(q["score"] is not None for q in questions):
            questions.sort(key=lambda x: x["score"], reverse=True)
        
        return questions
    
    def add_to_chat_history(self, message: str, is_user: bool = True):
        """Add a message to the chat history."""
        if is_user:
            self.memory.chat_memory.add_user_message(message)
        else:
            self.memory.chat_memory.add_ai_message(message)
    
    def get_question_details(self, question: str) -> Dict[str, Any]:
        """Get detailed information about a question, including its evaluation and relevance."""
        # Extract the base question without the score part
        base_question = question
        if " (Score:" in question:
            base_question = question.split(" (Score:")[0]
            
        # Try to find in cache
        if base_question in self.question_cache:
            return self.question_cache[base_question]
        
        # Get relevant insights from vector store
        relevant_insights = []
        tool = self.tools[0]
        insights_text = tool._run(base_question)
        relevant_insights = insights_text.split("\n\n")
        
        # Evaluate against these insights
        evaluation = self.evaluate_question_against_insights(
            base_question, 
            relevant_insights
        )
        
        # Cache the result
        self.question_cache[base_question] = {
            "question": base_question,
            "evaluation": evaluation.get("evaluation", "No evaluation available"),
            "overall_score": evaluation.get("overall_score"),
            "relevant_insights": relevant_insights
        }
        
        return self.question_cache[base_question]
    
    def get_agent_reasoning(self, question: str) -> str:
        """Get the agent's reasoning process for recommending this question."""
        # Extract the base question without the score part
        base_question = question
        if " (Score:" in question:
            base_question = question.split(" (Score:")[0]
        
        # Prompt the LLM to explain its reasoning
        reasoning_prompt = f"""
        As a {ACTOR_TYPES[self.actor_type]['persona']}, explain why the following question is valuable for a user whose goal is: {self.goal}
        
        Question: {base_question}
        
        Please explain:
        1. How this question relates to the user's goal
        2. What insights this question might uncover
        3. How answering this question could lead to actionable decisions
        4. Why this question is particularly appropriate for a {self.actor_type}
        
        Provide a structured, thoughtful explanation.
        """
        
        reasoning = self.llm.predict(reasoning_prompt)
        return reasoning
    
    def get_question_suggestions_with_context(self, text_input: str) -> List[Dict[str, Any]]:
        """Generate question suggestions based on free text input."""
        # Add the input to chat history
        self.add_to_chat_history(text_input)
        
        # Create a prompt for generating contextual questions
        contextual_prompt = f"""
        The user has provided the following input: "{text_input}"
        
        As a {ACTOR_TYPES[self.actor_type]['persona']} with the goal of helping the user {self.goal},
        generate 3-5 highly relevant questions that would help address this specific input.
        
        Consider:
        1. How this input relates to the overall goal
        2. What specific aspects of the data would be most relevant
        3. What insights would be most valuable to the user right now
        
        First, use the vector store tool to find relevant insights, then generate your questions.
        """
        
        # First get insights
        tool = self.tools[0]
        insights = tool._run(text_input)
        
        # Combine with prompt
        full_prompt = f"{contextual_prompt}\n\nRelevant insights:\n{insights}"
        
        # Generate suggestions
        response = self.llm.predict(full_prompt)
        
        # Parse questions
        questions = []
        for line in response.split('\n'):
            line = line.strip()
            if line and line[0].isdigit() and '. ' in line:
                questions.append(line.split('. ', 1)[1])
        
        # Evaluate each question and add scores
        results = []
        for q in questions:
            # Evaluate
            evaluation = self.evaluate_question_against_insights(q, insights.split("\n\n"))
            score = evaluation.get("overall_score")
            
            # Cache
            self.question_cache[q] = {
                "question": q,
                "evaluation": evaluation.get("evaluation", "No evaluation available"),
                "overall_score": score,
                "relevant_insights": insights.split("\n\n")
            }
            
            # Format with score
            results.append({
                "text": q,
                "score": score,
                "evaluation": evaluation
            })
        
        # Sort by score
        if all(q["score"] is not None for q in results):
            results.sort(key=lambda x: x["score"], reverse=True)
            
        return results
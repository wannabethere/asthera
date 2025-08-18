from typing import List, Dict, Any, TypedDict
import os
import json
import pandas as pd
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain.tools import Tool
from langchain_core.prompts import ChatPromptTemplate,PromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers.json import JsonOutputParser 
from langchain_core.output_parsers.string import StrOutputParser
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.tools import tool
from langchain_core.callbacks import dispatch_custom_event
from langchain_core.runnables import RunnableLambda
from app.agents.models.dsmodels import InsightManagerState,VisualizationState,DocumentInfo
from app.core.settings import Settings
from app.utils import df_utils
from app.utils.telemetry import traced
from app.agents.models.models import DocumentGrade
from app.core.settings import get_settings

settings = get_settings()
os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
llm = ChatOpenAI(model=settings.MODEL_NAME, temperature=settings.TEMPERATURE)

class RetrievalInsightsAgent:
    """Agent responsible for document retrieval and initial filtering."""
    
    def __init__(self, vectorstore):
        self.vectorstore = vectorstore
        
        @tool
        def search_documents(query: str) -> List[Dict[str, Any]]:
            """Search for relevant documents using the query."""
            #TODO: add where clause to the search
            docs = self.vectorstore.similarity_search(query, k=5) 
            print("retrieved docs", docs)
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
                ),
            }
            | self.prompt
            | llm
            | OpenAIFunctionsAgentOutputParser()
        )
        
        self.agent_executor =  AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True
        )
        

    #@traced(name="retrieve_documents")
    def retrieve(self, question: str,state: InsightManagerState=None) -> List[DocumentInfo]:
        """Retrieve relevant documents for the question."""
        result = self.agent_executor.invoke(
            {
                "input": question,
                "chat_history": []
            }
        )
        #print("received result", result)
        docs = []
        content = []
        if isinstance(result['output'],list) or isinstance(result['output'],dict):
            for doc in result['output']:
                if isinstance(doc,dict):
                    docs.append(DocumentInfo(**doc))
                    print("dict doc",doc)
                    content.append(doc['page_content'])
                else:
                    docs.append(DocumentInfo(page_content=doc, metadata={}))
                    print("list doc",doc)
                    content.append(doc)
        else:
            docs.append(DocumentInfo(page_content=result['output'], metadata={}))
            content.append(result['output'])
        return docs,content

class SummarizeDatasetAgent:
    """Agent responsible for summarizing a dataset."""
    def __init__(self):
        self.prompt = PromptTemplate(
            template = """
            I require the services of your team to help me reach my goal.
            You the manager of a data science team whose goal is to help stakeholders within your company extract actionable 
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
            input_variables=["question", "sample","schema","top_values","context","goal"]
        )
        self.agent = self.prompt | llm | StrOutputParser()      
    
    def summarize(self, dataset_path: str, question: str, state: InsightManagerState) -> str:
        """Summarize the dataset."""
        df = df_utils.read_dataset(dataset_path)
        schema, top_values = df_utils.get_schema_and_top_values(df)
        state['schema'] = schema
        state['top_values'] = top_values
        state['sample'] = df
        return self.summarize_dataframe(df, question, state)
    
    def summarize_dataframe(self, dataframe: pd.DataFrame, question: str, state: InsightManagerState) -> str:
        """Summarize the dataframe."""
        return self.agent.invoke({"question": question, "dataset": dataframe, "sample": dataframe.head(), "schema": dataframe.columns.tolist(), "top_values": dataframe.describe(), "context": state['context'], "goal": state['goal']})


class RecommendQuestionsAgent:
    """Agent responsible for recommending questions."""
    def __init__(self):
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
        self.agent = self.prompt | llm | JsonOutputParser()
    
    def recommend_questions(self, state: InsightManagerState) -> List[Dict[str, Any]]:
        """Recommend questions."""
        return self.agent.invoke({"context": state['context'], "goal": state['goal'], "schema": state['schema'], "similar_insights": state['similar_insights'], "max_questions": state['max_questions']})

class RecommendationGradingAgent:
    """Agent responsible for grading recommendation questions relevance."""
    
    def __init__(self):
        
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
        self.retrieval_grader = self.prompt | llm | JsonOutputParser()
    #@traced(name="grade_documents")
    def grade_document(self, question: str, state: InsightManagerState) -> DocumentGrade:
        """Grade a single document's relevance."""
        """
        response = llm.invoke(
            self.prompt.format(
                question=question,
                document=document.content
            )
        )
        """
        response = self.retrieval_grader.invoke({"question": question, "recommendations": state['recommendations'], "context": state['context'], "goal": state['goal'], "schema": state['schema']})
        # Parse the JSON response
        grade_data = response
        
        return grade_data

class MarkdownAgent:
    """Agent responsible for generating markdown."""
    def __init__(self, llmm: None):
        self.llm = llmm or llm
        self.md_prompt = PromptTemplate.from_template("""
            You are an AI assistant that generates markdown for a given question and answer.
            Please generate summarize the answer, context and goal. After this convert into markdown format that can be used in a React application. Please dont generate javascript code.
            The answer is a list of KPIs, EDA, Features and Analysis questions with the chain of thought for each question.
            Answer: {answer}
            Context: {context}
            Goal: {goal}
            The answer contains a list of questions for Determinining the KPIs, EDA, Features and Analysis questions. Please generate a markdown for each of the questions showing the recommended questions and the chain of thought for each question.
            The goal needs to be highlighted as a question in the markdown and the answer should be the response to the question in markdown format.
            Output in markdown format in Json format with the following fields:
                "markdown": "markdown"
            """)
        self.md_agent = self.md_prompt | self.llm | JsonOutputParser()
    
    def generate_markdown(self, answer: str, context: str, goal: str) -> str:
        """Generate markdown."""
        return self.md_agent.invoke({"answer": answer, "context": context, "goal": goal})
                                                       

"""
class AnalysisQuestionAgent:
    Agent responsible for analyzing questions.
    def __init__(self,llmm: None):
        self.llm = llmm or llm
        self.prompt = PromptTemplate.from_template(
            You are a data science team manager. You have a team of highly skilled data scientists that can answer complex questions about the data.
            Given the following context:
            <context>{context}</context>

            Given the following goal:
            <goal>{goal}</goal>

            Given the following schema:
            <schema>{schema}</schema>

            Instructions:
            * Analyze the goal and determine the type of Analysis to perform.
            * Categorize the Analysis into Variance, Trends, Anomalies, Segments, Cohorts etc.
            * Return the type of analysis and questions to help identify the timeline, cohorts to perform the analysis in the json format with the following fields:
            * type: The type of analysis it is.
            * question: The question itself.
            * timelinequestion: The timeline to perform the analysis on.
            * cohortsquestion: The cohorts to perform the analysis on.
            * chain_of_thought: The chain of thought process for the question.
            * Example:
            {{
                "type": "cohorts analysis"
            }}
            
            {{
                "type": "cohorts analysis", "question": "Please select the cohorts to analyze. Example questions: Which project cost centers and regions should we focus on for this analysis? | Give me some key groups to analyze in projects cost centers", "chain_of_thought": "I picked the question because it is a metric question and it is relevant to the goal."
            }}
            {{
                "type": "timeline analysis", "question": "What is the average age of the customers?", "chain_of_thought": "I picked the question because it is a metric question and it is relevant to the goal."
            }}
                                                   
            
        )
        self.agent = self.prompt | self.llm | JsonOutputParser()

    def analyze_question(self, question: str, state: InsightManagerState) -> str:
        Analyze a question.
        response = self.agent.invoke({"question": question, "context": state['context'], "goal": state['goal'], "schema": state['schema']},verbose=True)
        print("analyze_question response", response)
        return response
"""




class RecommendationScoringAgent:
    """Agent that evaluates and scores analysis recommendations."""
    
    def __init__(self, llmm=None, playbook_store=None):
        """
        Initialize the scoring agent.
        
        Args:
            llm: Language model for scoring
            playbook_store: Repository of analysis playbooks for reference
        """
        
        self.llm = llmm or llm
        self.playbook_store = playbook_store
        
        # Scoring criteria
        self.scoring_criteria = {
            "relevance": "How relevant is the question to the business goal?",
            "actionability": "How actionable would the answer to this question be?",
            "clarity": "How clear and specific is the question?", 
            "feasibility": "How feasible is it to answer this question with the available data?",
            "insightfulness": "How likely is this question to lead to valuable insights?"
        }
    
    def get_playbook_context(self, analysis_type=None, domain=None):
        """Get relevant playbook content for scoring context."""
        if not self.playbook_store:
            # Default playbook guidelines
            return {
                "descriptive": "Questions should focus on summarizing patterns in the data",
                "diagnostic": "Questions should focus on uncovering relationships and causes",
                "predictive": "Questions should focus on forecasting future outcomes",
                "prescriptive": "Questions should focus on recommended actions",
                "comparative": "Questions should enable effective comparisons between segments",
                "exploratory": "Questions should be open-ended but specific enough to guide analysis",
                "anomaly": "Questions should help identify and explain unusual patterns",
                "segmentation": "Questions should help identify meaningful groups",
                "trend": "Questions should clarify time-based patterns",
                "cohort": "Questions should define and compare cohorts"
            }.get(analysis_type, "Questions should be relevant, specific, and lead to actionable insights")
        
        # If playbook store exists, retrieve relevant playbook
        try:
            if analysis_type:
                playbook = self.playbook_store.get_by_analysis_type(analysis_type)
                return playbook.get("evaluation_guidelines", "")
            elif domain:
                playbook = self.playbook_store.get_by_domain(domain)
                return playbook.get("evaluation_guidelines", "")
            else:
                return "Questions should be relevant, specific, and lead to actionable insights"
        except Exception as e:
            print(f"Error retrieving playbook: {e}")
            return "Questions should be relevant, specific, and lead to actionable insights"
    
    def score_questions(self, recommendations: dict, business_question: str, schema: str, 
                       goal: str = "", domain: str = None) -> dict:
        """
        Score the recommended questions based on multiple criteria.
        
        Args:
            recommendations: Dictionary of recommended questions
            business_question: The original business question
            schema: Data schema
            goal: The analysis goal
            domain: Optional domain for specialized scoring
            
        Returns:
            Recommendations with scores added
        """
        # Get playbook guidance for evaluation
        analysis_type = recommendations.get("analysis_type", "exploratory")
        playbook_guidance = self.get_playbook_context(analysis_type, domain)
        
        # Create a copy of recommendations to add scores
        scored_recommendations = recommendations.copy()
        
        # Add a scores section
        scored_recommendations["scores"] = {
            "overall": 0,
            "by_category": {},
            "details": []
        }
        
        # Score each question category
        all_questions = []
        category_scores = {}
        
        for category, questions in recommendations["questions"].items():
            if not questions:
                continue
                
            # Prepare scoring prompt for this category
            prompt = self._create_scoring_prompt()
            
            # Get scores from LLM
            try:
                scores = self._get_scores_from_llm(prompt, questions, business_question, goal, schema, analysis_type, playbook_guidance)
                
                # Calculate average score for the category
                if scores:
                    category_avg = sum(score.get("overall", 0) for score in scores) / len(scores)
                    category_scores[category] = category_avg
                    
                    # Add scores to each question
                    scored_questions = []
                    for i, question in enumerate(questions):
                        if i < len(scores):
                            score_info = scores[i]
                            scored_question = {
                                "question": question,
                                "scores": {
                                    "overall": score_info.get("overall", 0),
                                    "criteria": {
                                        "relevance": score_info.get("relevance", 0),
                                        "actionability": score_info.get("actionability", 0),
                                        "clarity": score_info.get("clarity", 0),
                                        "feasibility": score_info.get("feasibility", 0),
                                        "insightfulness": score_info.get("insightfulness", 0)
                                    }
                                },
                                "feedback": score_info.get("feedback", "")
                            }
                            scored_questions.append(scored_question)
                            all_questions.append(scored_question)
                    
                    # Update the questions in the category
                    scored_recommendations["questions"][category] = scored_questions
            except Exception as e:
                print(f"Error scoring questions for {category}: {e}")
        
        # Calculate overall score
        if category_scores:
            overall_score = sum(category_scores.values()) / len(category_scores)
            scored_recommendations["scores"]["overall"] = round(overall_score, 2)
            scored_recommendations["scores"]["by_category"] = {k: round(v, 2) for k, v in category_scores.items()}
        
        # Sort all questions by score for the "details" section
        all_questions.sort(key=lambda x: x["scores"]["overall"], reverse=True)
        scored_recommendations["scores"]["details"] = all_questions[:5]  # Top 5 questions overall
        
        return scored_recommendations
    
    def _create_scoring_prompt(self):
        """Create a prompt for scoring a set of questions."""
        prompt = PromptTemplate(
            template="""
        You are an expert in data analysis and evaluation. Your task is to evaluate the quality of analysis questions.
        
        Business Question: {business_question}
        Goal: {goal}
        Data Schema: {schema_str}
        Analysis Type: {analysis_type}
        Question Category: {category}
        
        Playbook Guidance: {playbook_guidance}
        
        Please evaluate each of the following questions on a scale of 0-10 based on these criteria:
        - Relevance: How relevant is the question to the business goal? (0-10)
        - Actionability: How actionable would the answer to this question be? (0-10)
        - Clarity: How clear and specific is the question? (0-10)
        - Feasibility: How feasible is it to answer this question with the available data? (0-10)
        - Insightfulness: How likely is this question to lead to valuable insights? (0-10)
        
        Questions to evaluate:
        {questions}
        
        For each question, provide:
        1. Scores for each criterion (0-10)
        2. Overall score (0-10)
        3. Brief feedback explaining strengths and weaknesses
        
        Return your evaluation as a JSON array with one object per question, like this:
        [
            {{
                "question": "Question text",
                "relevance": 8,
                "actionability": 7,
                "clarity": 9,
                "feasibility": 6,
                "insightfulness": 8,
                "overall": 7.6,
                "feedback": "This question is well-formulated and relevant, but may be challenging to answer with the available data."
            }},
            ...
        ]
        """,
            input_variables=["business_question", "goal", "schema_str", "analysis_type", "category", "playbook_guidance","questions"]
        )
        self.agent = prompt | self.llm | JsonOutputParser()
        return prompt
    
    def _get_scores_from_llm(self, prompt, questions, business_question, goal, schema_str, analysis_type, playbook_guidance):
        """Get scores from the LLM."""
        try:
            # Format questions as a string with proper JSON formatting
            formatted_questions = json.dumps(questions, indent=2)
            
            # Create input dictionary with properly formatted values
            input_dict = {
                "questions": formatted_questions,
                "business_question": business_question,
                "goal": goal,
                "schema_str": schema_str,
                "analysis_type": analysis_type,
                "category": "generic",
                "playbook_guidance": playbook_guidance
            }
            
            # Invoke the agent with the properly formatted input
            response = self.agent.invoke(input_dict)
            
            
            #response = agent.invoke({"questions": questions, "business_question": business_question, "goal": goal, "schema_str": schema_str, "analysis_type": analysis_type, "playbook_guidance": playbook_guidance})
            
            # Extract JSON from response
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
            
            # Find JSON in the text
            import re
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                scores = json.loads(json_str)
                return scores
            
            # If regex fails, try finding JSON starting and ending brackets
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                scores = json.loads(json_str)
                return scores
            
            # Fallback
            return []
        except Exception as e:
            print(f"Error getting scores from LLM: {e}")
            return []
    
    def format_scores(self, scored_recommendations: dict, include_feedback: bool = True) -> str:
        """
        Format the scores in a readable way.
        
        Args:
            scored_recommendations: Dictionary of recommendations with scores
            include_feedback: Whether to include detailed feedback
            
        Returns:
            Formatted string with scores
        """
        formatted_output = "# Analysis Recommendation Scores\n\n"
        
        # Overall scores
        overall_score = scored_recommendations["scores"].get("overall", 0)
        formatted_output += f"## Overall Score: {overall_score:.2f}/10\n\n"
        
        # Category scores
        formatted_output += "## Scores by Category\n\n"
        for category, score in scored_recommendations["scores"].get("by_category", {}).items():
            category_name = category.replace("_", " ").title()
            formatted_output += f"* **{category_name}**: {score:.2f}/10\n"
        
        formatted_output += "\n"
        
        # Top questions
        formatted_output += "## Top Questions\n\n"
        top_questions = scored_recommendations["scores"].get("details", [])
        for i, q in enumerate(top_questions, 1):
            question = q.get("question", "")
            score = q.get("scores", {}).get("overall", 0)
            formatted_output += f"{i}. **{question}** (Score: {score:.2f}/10)\n"
            
            if include_feedback and "feedback" in q:
                formatted_output += f"   - *{q['feedback']}*\n"
                
            # Add score breakdown if requested
            if include_feedback and "scores" in q and "criteria" in q["scores"]:
                formatted_output += "   - Score breakdown: "
                criteria_scores = []
                for criterion, score in q["scores"]["criteria"].items():
                    criteria_scores.append(f"{criterion}: {score:.1f}")
                formatted_output += ", ".join(criteria_scores) + "\n"
            
            formatted_output += "\n"
        
        return formatted_output


class AnalysisQuestionAgent:
    """
    Agent responsible for analyzing questions and recommending analysis approaches
    based on data schema, context, goal, and actor type.
    """
    def __init__(self, llmm=None, function_store=None, playbook_store=None):
        """
        Initialize the Analysis Question Agent.
        
        Args:
            llm: Language model for generating analysis recommendations
            function_store: Repository of available analysis functions
            playbook_store: Repository of analysis playbooks for different domains
        """
        self.llm = llmm or llm
        
        # Store the function and playbook repositories
        self.function_store = function_store
        self.playbook_store = playbook_store
        
        # Initialize the scoring agent
        self.scoring_agent = RecommendationScoringAgent(llmm=self.llm, playbook_store=playbook_store)
        
        # Define actor types with their personalities and approaches
        self.actor_types = {
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
        
        # Define SQL tool
        self.sql_tool = {
            "name": "sql_query_tool",
            "description": "Generates SQL queries that could be used to analyze data",
            "parameters": {
                "required": ["query"],
                "optional": ["limit", "datasource"]
            },
            "examples": [
                "SELECT category, AVG(metric) FROM dataset GROUP BY category ORDER BY AVG(metric) DESC", 
                "SELECT time_period, SUM(value) FROM dataset WHERE dimension='X' GROUP BY time_period"
            ]
        }
        
        # Define analysis types with descriptions
        self.analysis_types = {
            "descriptive": "Summarizing and understanding what happened in the data",
            "diagnostic": "Understanding why something happened through correlations and patterns",
            "predictive": "Forecasting or estimating future trends based on historical data",
            "prescriptive": "Determining actions to take based on the insights",
            "comparative": "Comparing different segments, periods, or metrics",
            "exploratory": "Open-ended discovery of patterns and relationships",
            "anomaly": "Identification of outliers and unusual patterns",
            "segmentation": "Grouping data into meaningful clusters",
            "trend": "Analyzing how metrics change over time",
            "cohort": "Studying groups sharing common characteristics over time"
        }
        
        self.prompt = PromptTemplate.from_template("""
            You are a data analysis expert. You have expertise across multiple domains and analysis techniques.
            
            Given the following context:
            <context>{context}</context>

            Given the following goal:
            <goal>{goal}</goal>

            Given the following data schema:
            <schema>{schema}</schema>
            
            Your role: {persona}
            Your approach: {approach}
            Your question style: {question_style}
            
            Available analysis functions:
            {available_functions}
            
            Available analysis playbooks:
            {available_playbooks}
            
            SQL query generation is also available:
            {sql_tool}

            Instructions:
            * Analyze the goal and determine the most appropriate type of analysis to perform.
            * Consider the following analysis types: {analysis_types}
            * Return the type of analysis and questions to help guide the analysis in the JSON format with the following fields:
                * analysis_type: The type of analysis that would be most appropriate.
                * primary_question: The main question to be answered.
                * dimension_questions: Questions about what dimensions to analyze.
                * time_questions: Questions about relevant time periods or trends.
                * metric_questions: Questions about what metrics to focus on.
                * method_questions: Questions about analysis methodologies that could help reach the goal to answer the primary question.
                * visualization_questions: Questions about how to visualize the results.
                * chain_of_thought: Your reasoning process for these recommendations.
                * relevant_functions: List of function names that could be used.
                * relevant_sql: Potential SQL queries as natural language questions that could help answer these questions.
                * relevant_playbooks: Analysis playbooks that might be helpful.
            
            Example output:
            {{
                "analysis_type": "trend",
                "primary_question": "How has user engagement changed over the past 12 months?",
                "dimension_questions": ["Which user segments should we analyze?", "Which features show the most significant usage trends?"],
                "time_questions": ["What time granularity is appropriate for the trend analysis?", "Are there seasonal patterns we should account for?"],
                "metric_questions": ["Which KPIs best represent user engagement?", "How should we normalize metrics for comparison?"],
                "method_questions": ["Should we use moving averages to smooth out the trends?", "How should we handle outliers in the trend analysis?"],
                "visualization_questions": ["What visualization would best highlight the trend patterns?"],
                "chain_of_thought": "Based on the goal of understanding user engagement changes, a trend analysis is most appropriate. We need to identify the right metrics, dimensions, time periods, and methodology.",
                "relevant_functions": ["trend_analysis", "moving_average", "segment_comparison"],
                "relevant_sql": ["What is the average revenue per user by region?", "What is the total revenue by product category?"],
                "relevant_playbooks": ["user_engagement_analysis", "trend_detection_playbook"]
            }}
            """
        )
        self.agent = self.prompt | self.llm | JsonOutputParser()
    
    def get_available_functions(self, query=None, domain=None, limit=5):
        """Get available functions from the function store."""
        if not self.function_store:
            # Default functions if no function store is provided
            return [
                {
                    "name": "descriptive_statistics",
                    "description": "Calculate common statistical measures (mean, median, mode, etc.)",
                    "parameters": {
                        "required": ["columns"],
                        "optional": ["groupby", "percentiles", "include_outliers"]
                    }
                },
                {
                    "name": "correlation_analysis",
                    "description": "Analyze correlations between variables",
                    "parameters": {
                        "required": ["columns"],
                        "optional": ["method", "threshold", "visualization"]
                    }
                },
                {
                    "name": "trend_analysis",
                    "description": "Analyze trends over time",
                    "parameters": {
                        "required": ["time_column", "value_columns"],
                        "optional": ["period", "method", "group_by"]
                    }
                },
                {
                    "name": "segment_comparison",
                    "description": "Compare metrics across different segments",
                    "parameters": {
                        "required": ["segment_column", "metric_columns"],
                        "optional": ["test_type", "visualization", "min_sample_size"]
                    }
                },
                {
                    "name": "anomaly_detection",
                    "description": "Detect outliers and anomalies in the data",
                    "parameters": {
                        "required": ["columns"],
                        "optional": ["method", "threshold", "time_column"]
                    }
                }
            ]
        
        # If function store exists, retrieve functions
        try:
            if query:
                # Search for relevant functions
                functions, _ = self.function_store.retrieve(query)
                functions_list = [f.page_content for f in functions][:limit]
                return functions_list
            elif domain:
                # Filter by domain
                domain_functions = self.function_store.filter_by_domain(domain)
                return domain_functions[:limit]
            else:
                # Get all functions
                all_functions = self.function_store.get_all()
                return all_functions[:limit]
        except Exception as e:
            print(f"Error retrieving functions: {e}")
            return []
    
    def get_available_playbooks(self, analysis_type=None, domain=None, limit=3):
        """Get available playbooks from the playbook store."""
        if not self.playbook_store:
            # Default playbooks if no playbook store is provided
            return {
                "trend_analysis_playbook": "Standard approach for analyzing trends over time",
                "segmentation_playbook": "Methods for segmenting data and comparing segments",
                "anomaly_detection_playbook": "Techniques for identifying outliers and unusual patterns",
                "correlation_analysis_playbook": "Process for identifying relationships between variables",
                "forecasting_playbook": "Methods for predicting future values based on historical data"
            }
        
        # If playbook store exists, retrieve playbooks
        try:
            if analysis_type:
                playbooks = self.playbook_store.get_by_analysis_type(analysis_type)
                return playbooks[:limit]
            elif domain:
                playbooks = self.playbook_store.get_by_domain(domain)
                return playbooks[:limit]
            else:
                all_playbooks = self.playbook_store.get_all()
                return all_playbooks[:limit]
        except Exception as e:
            print(f"Error retrieving playbooks: {e}")
            return {}

    def analyze_question(self, question: str, state: InsightManagerState) -> dict:
        """
        Analyze a question based on actor type and domain.
        
        Args:
            question: The question to analyze
            state: Dictionary containing context, goal, and schema
            actor_type: Type of actor/persona to use (data_scientist, business_analyst, etc.)
            domain: Optional domain for specialized analysis (e.g., marketing, finance, etc.)
            
        Returns:
            Dictionary containing analysis recommendations
        """
        # Get actor persona information
        actor_info = self.actor_types.get(state['actor_type'], self.actor_types["data_scientist"])
        
        # Get relevant functions and playbooks
        available_functions = self.get_available_functions(query=question, domain=state['domain'])
        available_playbooks = self.get_available_playbooks(domain=state['domain'])
        
        # Format analysis types for prompt
        analysis_types_str = ", ".join([f"{k} ({v})" for k, v in self.analysis_types.items()])
        
        response = self.agent.invoke({
            "question": question, 
            "context": state.get('context', ''), 
            "goal": state.get('goal', ''), 
            "schema": state.get('schema', []),
            "persona": actor_info["persona"],
            "approach": actor_info["approach"],
            "question_style": actor_info["question_style"],
            "available_functions": available_functions,
            "available_playbooks": available_playbooks,
            "sql_tool": self.sql_tool,
            "analysis_types": analysis_types_str
        })
        print("analyze_question response: ", response)
        return response
        
    def recommend_analysis_questions(self, business_question: str, state: InsightManagerState, score_recommendations: bool = True) -> dict:
        """
        Generate analysis questions based on a business question.
        
        Args:
            business_question: The high-level business question
            schema: Data schema as comma-separated column names
            context: Additional context about the data and business
            goal: Specific goal for the analysis
            actor_type: Type of actor/persona making the recommendation
            domain: Optional domain for specialized analysis
            score_recommendations: Whether to score the recommendations
            
        Returns:
            Dictionary containing recommended analysis questions
        """
        # Create a state dictionary
        business_question = state['business_question'] or f"Analyze data to answer: {state['goal']}"
        schema = state['schema']
        actor_type = state['actor_type']
        domain = state['domain']
        # Construct a detailed analysis request
        analysis_request = f"""
        I need to analyze data to answer an important business question.
        Business Question: {business_question}
        Data Schema: {schema}
        
        Please recommend the best analysis approach and questions to help guide this analysis.
        """
        
        response = self.analyze_question(analysis_request, state)
        
        # Format the response into a standardized structure
        formatted_response = {
            "analysis_type": response.get("analysis_type", "exploratory"),
            "questions": {
                "primary": response.get("primary_question", business_question),
                "dimensions": response.get("dimension_questions", []),
                "time_periods": response.get("time_questions", []),
                "metrics": response.get("metric_questions", []),
                "methodology": response.get("method_questions", []),
                "visualization": response.get("visualization_questions", [])
            },
            "resources": {
                "functions": response.get("relevant_functions", []),
                "sql_queries": response.get("relevant_sql", []),
                "playbooks": response.get("relevant_playbooks", [])
            },
            "reasoning": response.get("chain_of_thought", "")
        }
        
        # If no questions were provided in certain categories, add defaults based on domain and actor type
        self._add_default_questions(formatted_response, actor_type, domain, schema)
        goal = state['goal']
        # Score recommendations if requested
        if score_recommendations:
            formatted_response = self.scoring_agent.score_questions(
                recommendations=formatted_response,
                business_question=business_question,
                schema=schema,
                goal=goal,
                domain=domain
            )
        
        return formatted_response
    
    def _add_default_questions(self, response, actor_type, domain, schema):
        """Add default questions to any empty categories based on actor type and domain."""
        # Get schema as a list for reference
        schema_list = schema.split(',') if isinstance(schema, str) else schema
        
        # Default questions by actor type
        default_questions = {
            "data_scientist": {
                "dimensions": ["Which variables show the strongest relationships with the target variable?"],
                "time_periods": ["What is the appropriate time granularity for this analysis?"],
                "metrics": ["Which statistical measures are most appropriate for this analysis?"],
                "methodology": ["What statistical methods should we apply?"],
                "visualization": ["What visualization would best highlight the statistical significance?"]
            },
            "business_analyst": {
                "dimensions": ["Which business segments should we prioritize in this analysis?"],
                "time_periods": ["What business cycles or periods are most relevant?"],
                "metrics": ["Which KPIs would best measure business impact?"],
                "methodology": ["What analytical approach would provide actionable insights?"],
                "visualization": ["What dashboard elements would communicate insights to stakeholders?"]
            },
            "executive": {
                "dimensions": ["Which strategic business segments should we focus on?"],
                "time_periods": ["What timeframe aligns with our strategic planning?"],
                "metrics": ["Which metrics directly tie to our strategic objectives?"],
                "methodology": ["What analysis approach will yield strategic insights?"],
                "visualization": ["What summary visualizations would highlight the key strategic implications?"]
            },
            "product_manager": {
                "dimensions": ["Which product features or user segments should we analyze?"],
                "time_periods": ["What time periods align with our product development cycles?"],
                "metrics": ["Which user-centered metrics should we focus on?"],
                "methodology": ["What user-focused analysis approach should we use?"],
                "visualization": ["What visualizations would best communicate product insights?"]
            }
        }
        
        # Add domain-specific default questions if domain is provided
        if domain:
            domain_questions = self._get_domain_specific_questions(domain, schema_list)
            
            # Merge domain questions with actor type questions
            actor_defaults = default_questions.get(actor_type, default_questions["data_scientist"])
            for category in actor_defaults:
                if category in domain_questions:
                    actor_defaults[category].extend(domain_questions[category])
        else:
            actor_defaults = default_questions.get(actor_type, default_questions["data_scientist"])
                
        # Fill in empty categories with defaults
        for category, questions in actor_defaults.items():
            if not response["questions"].get(category) or len(response["questions"][category]) == 0:
                response["questions"][category] = questions
    
    def _get_domain_specific_questions(self, domain, schema):
        """Get domain-specific default questions."""
        # Sample domain-specific questions
        domain_questions = {
            "marketing": {
                "dimensions": ["Which marketing channels should we analyze?", "Which customer segments show different responses?"],
                "time_periods": ["How do campaign results vary by season?", "What is the appropriate attribution window?"],
                "metrics": ["Which conversion metrics are most important?", "How should we measure ROI across channels?"],
                "methodology": ["How should we attribute conversions across touchpoints?"],
                "visualization": ["What visualization would best show the customer journey?"]
            },
            "finance": {
                "dimensions": ["Which financial categories show unusual patterns?", "Which segments contribute most to variance?"],
                "time_periods": ["What fiscal periods should we compare?", "How do patterns change month-over-month?"],
                "metrics": ["Which financial ratios are most important to calculate?", "How should we measure volatility?"],
                "methodology": ["Should we apply time-series decomposition?", "How should we handle seasonality?"],
                "visualization": ["What visualization would clearly show financial trends and anomalies?"]
            },
            "product": {
                "dimensions": ["Which features are most used?", "Which user segments show different usage patterns?"],
                "time_periods": ["How does usage evolve after onboarding?", "What is the appropriate cohort period?"],
                "metrics": ["Which engagement metrics best predict retention?", "How should we measure feature adoption?"],
                "methodology": ["Should we use cohort analysis or funnel analysis?"],
                "visualization": ["What visualization would best show the user journey?"]
            },
            "operations": {
                "dimensions": ["Which operational processes should we analyze?", "Which locations or teams show different patterns?"],
                "time_periods": ["How do operations vary by time of day or day of week?", "What seasonal factors affect operations?"],
                "metrics": ["Which efficiency metrics are most important?", "How should we measure process quality?"],
                "methodology": ["Should we use process mining or statistical process control?"],
                "visualization": ["What visualization would best show process bottlenecks?"]
            }
        }
        
        return domain_questions.get(domain, {})
    
    def format_recommendations(self, recommendations: dict, actor_type: str = "data_scientist") -> str:
        """
        Format recommendations in a user-friendly way, tailored to actor type.
        
        Args:
            recommendations: The recommendations dictionary
            actor_type: Type of actor/persona for formatting
            
        Returns:
            Formatted string with recommendations
        """
        print("recommendations: ", recommendations)
        actor_info = self.actor_types.get(actor_type, self.actor_types["data_scientist"])
        persona = actor_info["persona"].split(' ')[0]  # Just get the first word of the persona
        
        analysis_type = recommendations.get("analysis_type", "exploratory")
        
        formatted_output = f"# Analysis Recommendations ({persona} Perspective)\n\n"
        formatted_output += f"## Recommended Approach: {analysis_type.capitalize()} Analysis\n\n"
        
        # Add primary question
        primary_question = recommendations["questions"].get("primary", "")
        if primary_question:
            formatted_output += f"### Primary Question\n{primary_question}\n\n"
        
        # Add question categories
        question_categories = {
            "dimensions": "🧩 **Dimension Questions**",
            "time_periods": "🕒 **Time Period Questions**",
            "metrics": "📊 **Metric Questions**",
            "methodology": "🔍 **Methodology Questions**",
            "visualization": "📈 **Visualization Questions**"
        }
        
        # Customize for executive - simplify and focus
        if actor_type == "executive":
            question_categories = {
                "dimensions": "🧩 **Strategic Focus Areas**",
                "time_periods": "🕒 **Relevant Timeframes**",
                "metrics": "📊 **Key Performance Indicators**",
                "methodology": "🔍 **Analysis Approach**",
                "visualization": "📈 **Executive Dashboard Elements**"
            }
        
        for category, title in question_categories.items():
            questions = recommendations["questions"].get(category, [])
            if questions:
                formatted_output += f"{title}\n"
                
                # Add each question with numbering
                for i, question_item in enumerate(questions, 1):
                    # Handle both plain string questions and question objects with scores
                    if isinstance(question_item, str):
                        question = question_item
                        formatted_output += f"{i}. {question}\n"
                    elif isinstance(question_item, dict):
                        question = question_item.get("question", "")
                        
                        # Check if this is a scored question
                        if "scores" in question_item and "overall" in question_item["scores"]:
                            score = question_item["scores"]["overall"]
                            formatted_output += f"{i}. {question} (Score: {score:.1f}/10)\n"
                        else:
                            formatted_output += f"{i}. {question}\n"
                            
                        # Add feedback if available
                        if "feedback" in question_item:
                            formatted_output += f"   - *{question_item['feedback']}*\n"
                
                formatted_output += "\n"
        
        # Add resources if available
        resources = recommendations.get("resources", {})
        if resources:
            formatted_output += "### Recommended Resources\n\n"
            
            # Add functions
            functions = resources.get("functions", [])
            if functions:
                formatted_output += "**Analysis Functions:**\n"
                functions_str = ", ".join([f"`{func}`" for func in functions])
                formatted_output += f"{functions_str}\n\n"
            
            # Add playbooks
            playbooks = resources.get("playbooks", [])
            if playbooks:
                formatted_output += "**Analysis Playbooks:**\n"
                playbooks_str = ", ".join([f"`{book}`" for book in playbooks])
                formatted_output += f"{playbooks_str}\n\n"
            
            # Add SQL
            sql_queries = resources.get("sql_queries", [])
            if sql_queries:
                if actor_type == "data_scientist" or actor_type == "business_analyst":
                    formatted_output += "**Example SQL Query:**\n```sql\n"
                    if isinstance(sql_queries, list):
                        formatted_output += sql_queries[0] if sql_queries else ""
                    else:
                        formatted_output += sql_queries
                    formatted_output += "\n```\n\n"
        
        # Add reasoning if available
        reasoning = recommendations.get("reasoning", "")
        if reasoning and actor_type in ["data_scientist", "business_analyst"]:
            formatted_output += f"### Analysis Rationale\n{reasoning}\n"
        
        # Add overall score information if available
        if "scores" in recommendations and "overall" in recommendations["scores"]:
            overall_score = recommendations["scores"]["overall"]
            formatted_output += f"\n## Quality Score: {overall_score:.2f}/10\n"
            
            # Add category scores if available
            if "by_category" in recommendations["scores"]:
                formatted_output += "\n**Category Scores:**\n"
                for category, score in recommendations["scores"]["by_category"].items():
                    category_name = category.replace("_", " ").title()
                    formatted_output += f"- {category_name}: {score:.2f}/10\n"
        
        return formatted_output
    
    def score_and_optimize_recommendations(self, recommendations: dict, business_question: str, schema: str, goal: str = "", actor_type: str = "data_scientist", domain: str = None) -> dict:
        """
        Score the recommendations and optimize by replacing low-scoring questions.
        
        Args:
            recommendations: Dictionary of recommended questions
            business_question: The original business question
            schema: Data schema
            goal: The analysis goal
            actor_type: Type of actor/persona
            domain: Optional domain for specialized analysis
            
        Returns:
            Optimized recommendations with improved questions
        """
        # First score the current recommendations
        scored_recommendations = self.scoring_agent.score_questions(
            recommendations=recommendations,
            business_question=business_question,
            schema=schema,
            goal=goal,
            domain=domain
        )
        
        # Identify low-scoring categories (below 6.0)
        low_scoring_categories = []
        category_scores = scored_recommendations["scores"].get("by_category", {})
        
        for category, score in category_scores.items():
            if score < 6.0:
                low_scoring_categories.append(category)
        
        # If there are low-scoring categories, generate better questions for those categories
        if low_scoring_categories:
            improved_recommendations = scored_recommendations.copy()
            
            for category in low_scoring_categories:
                # Create a targeted prompt to generate better questions for this category
                prompt = f"""
                You are an expert in data analysis specializing in {domain or 'data analytics'}.
                
                I need to improve questions for a {category} analysis to better answer this business question:
                "{business_question}"
                
                Data schema: {schema}
                Goal: {goal}
                
                The current questions in this category scored below 6.0/10 in quality.
                
                Please generate 3-4 high-quality {category} questions that:
                1. Are directly relevant to the business question
                2. Are specific and actionable
                3. Can be answered with the available data schema
                4. Will lead to valuable insights
                5. Are appropriate for a {actor_type}
                
                Return only the questions, one per line.
                """
                
                # Get improved questions from LLM
                try:
                    response = self.llm.invoke(prompt)
                    
                    # Extract questions from response
                    if hasattr(response, 'content'):
                        response_text = response.content
                    else:
                        response_text = str(response)
                    
                    # Split by newlines and filter empty lines
                    new_questions = [q.strip() for q in response_text.split('\n') if q.strip()]
                    
                    # Filter out lines that don't end with a question mark
                    new_questions = [q for q in new_questions if q.endswith('?')]
                    
                    # Replace the questions in this category
                    if new_questions:
                        improved_recommendations["questions"][category] = new_questions
                except Exception as e:
                    print(f"Error generating improved questions for {category}: {e}")
            
            # Score the improved recommendations
            final_recommendations = self.scoring_agent.score_questions(
                recommendations=improved_recommendations,
                business_question=business_question,
                schema=schema,
                goal=goal,
                domain=domain
            )
            
            return final_recommendations
        
        # If no low-scoring categories, return the original scored recommendations
        return scored_recommendations






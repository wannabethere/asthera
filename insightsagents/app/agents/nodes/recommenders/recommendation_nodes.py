import os
from typing import List, Dict, Any, Optional, Tuple

# LangChain imports
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.schema import AIMessage, HumanMessage, SystemMessage
from langchain.agents import Tool, AgentExecutor, create_react_agent
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import json

# Configuration
class Config:
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MODEL_NAME = "gpt-3.5-turbo"
    API_KEY = os.environ.get("OPENAI_API_KEY", "")

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

# Custom Tools for Vector Store Access
class InsightVectorStoreTool(BaseTool):
    """Tool for retrieving insights from the vector store with self-evaluation."""
    
    name = "insight_vector_store_tool"
    description = "Retrieves and evaluates relevant insights and examples from the vector store based on the query"
    
    vector_store: Any = Field(description="The vector store containing insights")
    llm: Any = Field(description="The LLM to use for evaluation")
    
    def _run(self, query: str) -> str:
        """Use the vector store to get relevant insights with self-evaluation."""
        # Retrieve candidate documents
        results = self.vector_store.semantic_search(query, k=5)  # Get more candidates for filtering
        
        if not results:
            return "No relevant insights found."
        
        # Self-evaluation of retrieved documents
        evaluated_results = []
        for i, (doc, score) in enumerate(results):
            # Evaluate relevance using the LLM
            eval_prompt = f"""
            Query: {query}
            Document: {doc.page_content}
            
            On a scale of 1-10, how relevant is this document to the query?
            Consider:
            1. Direct relevance to the specific query
            2. Usefulness for generating relevant questions
            3. Quality and specificity of the insight
            
            Provide a single number score and a brief explanation.
            """
            
            evaluation = self.llm.predict(eval_prompt)
            
            # Extract score from evaluation
            try:
                # Try to extract just the numeric score
                eval_score_text = evaluation.strip().split('\n')[0]
                eval_score = float(eval_score_text.split(':')[-1].strip()) if ':' in eval_score_text else float(eval_score_text)
            except:
                # If parsing fails, default to using the similarity score
                eval_score = 10 - (score * 10)  # Convert similarity score to 0-10 scale
            
            evaluated_results.append({
                "doc": doc,
                "vector_score": score,
                "eval_score": eval_score,
                "evaluation": evaluation,
                "combined_score": (eval_score * 0.7) + ((10 - (score * 10)) * 0.3)  # Weighted combination
            })
        
        # Sort by combined score and take top 3
        evaluated_results.sort(key=lambda x: x["combined_score"], reverse=True)
        top_results = evaluated_results[:3]
        
        formatted_results = []
        for i, result in enumerate(top_results):
            doc = result["doc"]
            formatted_results.append(
                f"Insight {i+1} (relevance: {result['combined_score']:.1f}/10): {doc.page_content}\n"
                f"Source: {doc.metadata.get('source', 'Unknown')}"
            )
        
        return "\n\n".join(formatted_results)
    
    async def _arun(self, query: str) -> str:
        """Async implementation."""
        return self._run(query)

class StatisticalAgentTool(BaseTool):
    """Tool for accessing statistical analysis capabilities from other agents."""
    
    name = "statistical_agent_tool"
    description = "Performs statistical operations on the dataset using specialized agents"
    
    statistical_agents: Dict[str, Any] = Field(description="Dictionary of statistical agents")
    
    def _run(self, operation: str) -> str:
        """Run a statistical operation using the appropriate agent."""
        # Parse the operation to determine which agent to use
        try:
            op_data = json.loads(operation)
            op_type = op_data.get("operation_type", "")
            
            if op_type in self.statistical_agents:
                # Execute the operation with the specified agent
                return self.statistical_agents[op_type].run(operation)
            else:
                available_ops = list(self.statistical_agents.keys())
                return f"Operation type '{op_type}' not found. Available operations: {available_ops}"
        except json.JSONDecodeError:
            return "Invalid operation format. Please provide a JSON string with 'operation_type' specified."
    
    async def _arun(self, operation: str) -> str:
        """Async implementation."""
        return self._run(operation)

class DatasetInfoTool(BaseTool):
    """Tool for accessing dataset information."""
    
    name = "dataset_info_tool"
    description = "Retrieves information about the dataset structure, schema, and sample data"
    
    dataset_description: str = Field(description="Description of the dataset")
    sample_data: Any = Field(description="Sample data from the dataset")
    
    def _run(self, query: str = "") -> str:
        """Return information about the dataset."""
        # If a specific query is provided, we could filter the information
        if "schema" in query.lower():
            # Return just the schema information
            if isinstance(self.sample_data, dict):
                schema = {k: type(v).__name__ for k, v in self.sample_data.items()}
                return f"Dataset schema:\n{json.dumps(schema, indent=2)}"
            elif isinstance(self.sample_data, list) and self.sample_data:
                sample = self.sample_data[0] if self.sample_data else {}
                if isinstance(sample, dict):
                    schema = {k: type(v).__name__ for k, v in sample.items()}
                    return f"Dataset schema (based on first record):\n{json.dumps(schema, indent=2)}"
        
        # Default: return full dataset description and a sample
        result = f"Dataset description: {self.dataset_description}\n\n"
        
        if isinstance(self.sample_data, list):
            sample_size = min(3, len(self.sample_data))
            sample_str = json.dumps(self.sample_data[:sample_size], indent=2)
            result += f"Sample data (showing {sample_size} records):\n{sample_str}"
        else:
            result += f"Sample data:\n{json.dumps(self.sample_data, indent=2)}"
            
        return result
    
    async def _arun(self, query: str = "") -> str:
        """Async implementation."""
        return self._run(query)

# Main Question Recommendation Agent with Self-Evaluation
class QuestionRecommendationAgent:
    """Agent that recommends and evaluates relevant questions based on context."""
    
    def __init__(
        self,
        llm,
        actor_type: str,
        goal: str,
        insight_vector_store,
        dataset_description: str,
        sample_data: Any,
        statistical_agents: Dict[str, Any] = None
    ):
        self.llm = llm
        self.actor_type = actor_type
        self.goal = goal
        self.memory = ConversationBufferMemory(return_messages=True)
        
        # Validate actor type
        if actor_type not in ACTOR_TYPES:
            raise ValueError(f"Invalid actor type: {actor_type}. Available types: {list(ACTOR_TYPES.keys())}")
        
        # Create tools with self-evaluation capability
        self.tools = [
            InsightVectorStoreTool(
                vector_store=insight_vector_store,
                llm=llm,  # Pass LLM for self-evaluation
                name="insight_vector_store_tool"
            ),
            DatasetInfoTool(
                dataset_description=dataset_description,
                sample_data=sample_data,
                name="dataset_info_tool"
            )
        ]
        
        # Add statistical agent tool if provided
        if statistical_agents:
            self.tools.append(StatisticalAgentTool(
                statistical_agents=statistical_agents,
                name="statistical_agent_tool"
            ))
        
        # Create the prompt for the initial question recommendation with evaluation
        self.init_question_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
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
                """
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])
        
        # Create the prompt for drill-down question recommendation with evaluation
        self.drill_down_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(
                f"""You are an AI assistant acting as a {ACTOR_TYPES[actor_type]['persona']}. 
                Your approach is {ACTOR_TYPES[actor_type]['approach']}.
                Your questions should reflect {ACTOR_TYPES[actor_type]['question_style']}.
                
                The user's goal is: {goal}
                
                The user has selected this question to explore: "{'{selected_question}'}"
                
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
                """
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{input}")
        ])
        
        # Create the React agent for initial questions
        self.init_question_agent = create_react_agent(
            llm=llm,
            tools=self.tools,
            prompt=self.init_question_prompt
        )
        
        self.init_question_executor = AgentExecutor.from_agent_and_tools(
            agent=self.init_question_agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )
        
        # Create the React agent for drill-down questions
        self.drill_down_agent = create_react_agent(
            llm=llm,
            tools=self.tools,
            prompt=self.drill_down_prompt
        )
        
        self.drill_down_executor = AgentExecutor.from_agent_and_tools(
            agent=self.drill_down_agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )
    
    def get_initial_questions(self) -> List[Dict[str, Any]]:
        """Generate and evaluate initial relevant questions based on the context."""
        response = self.init_question_executor.run(
            input=f"Suggest and evaluate relevant questions for a {self.actor_type} trying to {self.goal}"
        )
        
        # Parse the questions and their scores from the response
        questions = []
        for line in response.split('\n'):
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
                
                questions.append({
                    "text": question_text,
                    "score": score
                })
        
        # Sort by score if available
        if all(q["score"] is not None for q in questions):
            questions.sort(key=lambda x: x["score"], reverse=True)
        
        return questions
    
    def get_drill_down_questions(self, selected_question: str) -> List[Dict[str, Any]]:
        """Generate and evaluate drill-down questions based on the selected question."""
        response = self.drill_down_executor.run(
            input=f"The user selected this question: '{selected_question}'. Suggest and evaluate relevant drill-down questions.",
            selected_question=selected_question
        )
        
        # Parse the questions and their scores from the response
        questions = []
        for line in response.split('\n'):
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
                
                questions.append({
                    "text": question_text,
                    "score": score
                })
        
        # Sort by score if available
        if all(q["score"] is not None for q in questions):
            questions.sort(key=lambda x: x["score"], reverse=True)
        
        return questions
    
    def evaluate_question_against_insights(self, question: str, insights: List[str]) -> Dict[str, Any]:
        """Evaluate a single question against retrieved insights."""
        evaluation_prompt = f"""
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
        """
        
        evaluation_result = self.llm.predict(evaluation_prompt)
        
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
    
    def add_to_chat_history(self, message: str, is_user: bool = True):
        """Add a message to the chat history."""
        if is_user:
            self.memory.chat_memory.add_user_message(message)
        else:
            self.memory.chat_memory.add_ai_message(message)

# Main application class for managing the conversational agents
class ConversationalDashboardAssistant:
    """Main application class for the conversational dashboard assistant with self-evaluation."""
    
    def __init__(
        self,
        insight_vector_store,
        dataset_description: str,
        sample_data: Any,
        llm: Any
    ):
        # Set API key if provided
      
        
        # Store the inputs
        self.insight_vector_store = insight_vector_store
        self.dataset_description = dataset_description
        self.sample_data = sample_data
        
        # Initialize statistical agents (placeholder - to be integrated with external agents)
        self.statistical_agents = {
            "descriptive_statistics": None,  # These would be actual agent instances
            "correlation_analysis": None,
            "regression_analysis": None,
            "clustering": None
        }
        
        # Initialize LLM for generation and evaluation
        
        self.llm = llm
        
        # Current active agent
        self.current_agent = None
        
        # Question cache for storing evaluations
        self.question_cache = {}
        
    def initialize_agent(self, actor_type: str, goal: str):
        """Initialize a new agent with the specified actor type and goal."""
        self.current_agent = QuestionRecommendationAgent(
            llm=self.llm,
            actor_type=actor_type,
            goal=goal,
            insight_vector_store=self.insight_vector_store,
            dataset_description=self.dataset_description,
            sample_data=self.sample_data,
            statistical_agents=self.statistical_agents
        )
        
        # Get initial questions with evaluations
        question_objects = self.current_agent.get_initial_questions()
        
        # Store in cache for future reference
        self.question_cache = {q["text"]: q for q in question_objects}
        
        # Format for display
        formatted_questions = []
        for q in question_objects:
            score_display = f" (Score: {q['score']:.1f}/10)" if q["score"] is not None else ""
            formatted_questions.append(f"{q['text']}{score_display}")
        
        return formatted_questions
    
    def select_question(self, question: str):
        """Process a selected question and return drill-down questions with evaluations."""
        if not self.current_agent:
            raise ValueError("No active agent. Initialize one first with initialize_agent().")
        
        # Extract the base question without the score part
        base_question = question
        if " (Score:" in question:
            base_question = question.split(" (Score:")[0]
        
        # Add the selected question to chat history
        self.current_agent.add_to_chat_history(f"I want to explore: {base_question}")
        
        # Get drill-down questions with evaluations
        question_objects = self.current_agent.get_drill_down_questions(base_question)
        
        # Store in cache for future reference
        for q in question_objects:
            self.question_cache[q["text"]] = q
        
        # Format for display
        formatted_questions = []
        for q in question_objects:
            score_display = f" (Score: {q['score']:.1f}/10)" if q["score"] is not None else ""
            formatted_questions.append(f"{q['text']}{score_display}")
        
        return formatted_questions
    
    def get_question_evaluation(self, question: str):
        """Get the evaluation details for a specific question."""
        # Extract the base question without the score part
        base_question = question
        if " (Score:" in question:
            base_question = question.split(" (Score:")[0]
            
        # Try to find in cache
        if base_question in self.question_cache:
            return self.question_cache[base_question]
        
        # If not in cache and we have an agent, do a live evaluation
        if self.current_agent:
            # Get recent insights from the vector store
            tool = self.current_agent.tools[0]
            insights = tool._run(base_question)
            
            # Evaluate against these insights
            evaluation = self.current_agent.evaluate_question_against_insights(
                base_question, 
                insights
            )
            
            # Cache the result
            self.question_cache[base_question] = evaluation
            
            return evaluation
            
        return {"question": base_question, "evaluation": "No evaluation available", "overall_score": None}
    
    def add_user_message(self, message: str):
        """Add a user message to the chat history."""
        if not self.current_agent:
            raise ValueError("No active agent. Initialize one first with initialize_agent().")
        
        self.current_agent.add_to_chat_history(message, is_user=True)
    
    def add_system_message(self, message: str):
        """Add a system message to the chat history."""
        if not self.current_agent:
            raise ValueError("No active agent. Initialize one first with initialize_agent().")
        
        self.current_agent.add_to_chat_history(message, is_user=False)
        
    def get_question_details(self, question: str):
        """Get detailed information about a question, including its evaluation and relevance."""
        # Extract the base question without the score part
        base_question = question
        if " (Score:" in question:
            base_question = question.split(" (Score:")[0]
            
        # Try to find in cache
        evaluation = self.get_question_evaluation(base_question)
        
        # Get relevant insights from vector store
        relevant_insights = []
        if self.current_agent:
            tool = self.current_agent.tools[0]
            insights_text = tool._run(base_question)
            relevant_insights = insights_text.split("\n\n")
        
        return {
            "question": base_question,
            "evaluation": evaluation.get("evaluation", "No evaluation available"),
            "overall_score": evaluation.get("overall_score"),
            "relevant_insights": relevant_insights
        }
    
    def get_agent_reasoning(self, question: str):
        """Get the agent's reasoning process for recommending this question."""
        if not self.current_agent:
            return "No active agent. Initialize one first with initialize_agent()."
        
        # Extract the base question without the score part
        base_question = question
        if " (Score:" in question:
            base_question = question.split(" (Score:")[0]
        
        # Prompt the LLM to explain its reasoning
        reasoning_prompt = f"""
        As a {ACTOR_TYPES[self.current_agent.actor_type]['persona']}, explain why the following question is valuable for a user whose goal is: {self.current_agent.goal}
        
        Question: {base_question}
        
        Please explain:
        1. How this question relates to the user's goal
        2. What insights this question might uncover
        3. How answering this question could lead to actionable decisions
        4. Why this question is particularly appropriate for a {self.current_agent.actor_type}
        
        Provide a structured, thoughtful explanation.
        """
        
        reasoning = self.llm.predict(reasoning_prompt)
        return reasoning
    
    def evaluate_all_questions(self, questions: List[str]):
        """Run a comprehensive evaluation on a list of questions."""
        results = []
        
        for question in questions:
            # Extract the base question without the score part
            base_question = question
            if " (Score:" in question:
                base_question = question.split(" (Score:")[0]
                
            # Get insights for this question
            tool = self.current_agent.tools[0]
            insights = tool._run(base_question)
            
            # Evaluate against insights
            evaluation = self.current_agent.evaluate_question_against_insights(
                base_question, 
                insights
            )
            
            # Cache the result
            self.question_cache[base_question] = evaluation
            
            # Add to results
            results.append({
                "question": base_question,
                "score": evaluation.get("overall_score"),
                "evaluation": evaluation.get("evaluation"),
                "relevant_insights": insights
            })
        
        # Sort by score
        results.sort(key=lambda x: x.get("score", 0) or 0, reverse=True)
        return results
    
    def get_question_suggestions_with_context(self, text_input: str):
        """Generate question suggestions based on free text input from the user."""
        if not self.current_agent:
            raise ValueError("No active agent. Initialize one first with initialize_agent().")
        
        # Add the input to chat history
        self.current_agent.add_to_chat_history(text_input)
        
        # Create a prompt for generating contextual questions
        contextual_prompt = f"""
        The user has provided the following input: "{text_input}"
        
        As a {ACTOR_TYPES[self.current_agent.actor_type]['persona']} with the goal of helping the user {self.current_agent.goal},
        generate 3-5 highly relevant questions that would help address this specific input.
        
        Consider:
        1. How this input relates to the overall goal
        2. What specific aspects of the data would be most relevant
        3. What insights would be most valuable to the user right now
        
        First, use the vector store tool to find relevant insights, then generate your questions.
        """
        
        # Use a simplified agent to get suggestions
        context_chain = LLMChain(
            llm=self.llm,
            prompt=ChatPromptTemplate.from_template(contextual_prompt),
            verbose=True
        )
        
        # First get insights
        tool = self.current_agent.tools[0]
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
        formatted_questions = []
        for q in questions:
            # Evaluate
            evaluation = self.current_agent.evaluate_question_against_insights(q, insights)
            score = evaluation.get("overall_score")
            
            # Cache
            self.question_cache[q] = evaluation
            
            # Format with score
            score_display = f" (Score: {score:.1f}/10)" if score is not None else ""
            formatted_questions.append(f"{q}{score_display}")
        
        return formatted_questions

# Example usage (commented out since we're not implementing the vector store)
'''
# Example dataset description and sample data
dataset_description = "Customer transaction data including purchase amount, product category, customer demographics, and satisfaction scores"
sample_data = [
    {
        "customer_id": "C001",
        "purchase_amount": 120.50,
        "product_category": "Electronics",
        "age": 34,
        "gender": "F",
        "satisfaction_score": 4.2
    },
    {
        "customer_id": "C002",
        "purchase_amount": 85.25,
        "product_category": "Clothing",
        "age": 45,
        "gender": "M",
        "satisfaction_score": 3.8
    }
]

# Initialize the assistant
assistant = ConversationalDashboardAssistant(
    insight_vector_store=None,  # This would be the provided vector store
    dataset_description=dataset_description,
    sample_data=sample_data
)

# Start a new conversation with a business analyst persona
initial_questions = assistant.initialize_agent(
    actor_type="business_analyst",
    goal="build a dashboard tracking customer satisfaction trends"
)

print("Initial questions:")
for i, question in enumerate(initial_questions):
    print(f"{i+1}. {question}")

# User selects a question (e.g., the first one)
selected_question = initial_questions[0]
drill_down_questions = assistant.select_question(selected_question)

print(f"\nDrill-down questions for: {selected_question}")
for i, question in enumerate(drill_down_questions):
    print(f"{i+1}. {question}")
'''
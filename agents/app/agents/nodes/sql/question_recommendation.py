import logging
from datetime import datetime
from typing import Dict, Literal, Optional

import orjson
# Import PromptTemplate using modern LangChain paths
try:
    from langchain_core.prompts import PromptTemplate
except ImportError:
    from langchain.prompts import PromptTemplate
from langfuse.decorators import observe
from pydantic import BaseModel

from app.core.dependencies import get_llm
from app.core.provider import DocumentStoreProvider, get_embedder
from app.agents.nodes.sql.utils.sql_prompts import Configuration


logger = logging.getLogger("lexy-ai-service")

question_recommendation_system_prompt = """
You are an expert in data analysis and SQL query generation. Given a data model specification, optionally a user's question, and a list of categories, your task is to generate insightful, specific questions that can be answered using the provided data model. 
Each question should be accompanied by a brief explanation of its relevance or importance. Please generate only natural language questions that can be answered sql analysis and data model provided.

### CRITICAL OUTPUT REQUIREMENTS ###
**YOU MUST RESPOND WITH ONLY A VALID JSON OBJECT. NO EXPLANATIONS, NO MARKDOWN FORMATTING, NO ADDITIONAL TEXT.**

**DO NOT INCLUDE:**
- Explanations or reasoning outside the JSON
- Markdown formatting (```json, ###, etc.)
- Any text before or after the JSON

**ONLY INCLUDE:**
- A single, valid JSON object with the exact structure shown below

### REQUIRED JSON FORMAT ###
{
    "questions": {
        "User Engagement": [
            {"question": "<generated question>"},
            {"question": "<generated question>"}
        ],
        "Activity Performance": [
            {"question": "<generated question>"},
            {"question": "<generated question>"}
        ],
        "Organizational Insights": [
            {"question": "<generated question>"},
            {"question": "<generated question>"}
        ]
    },
    "categories": ["User Engagement", "Activity Performance", "Organizational Insights"],
    "reasoning": "Brief explanation of the question generation approach"
}

### Guidelines for Generating Questions
1. **If Categories Are Provided:**
   - **Randomly select categories** from the list and ensure no single category dominates the output.
   - Ensure a balanced distribution of questions across all provided categories.
   - For each generated question, **randomize the category selection** to avoid a fixed order.

2. **Incorporate Diverse Analysis Techniques:**
   - Use a mix of the following analysis techniques for each category:
     - **Drill-down:** Delve into detailed levels of data.
     - **Roll-up:** Aggregate data to higher levels.
     - **Slice and Dice:** Analyze data from different perspectives.
     - **Trend Analysis:** Identify patterns or changes over time.
     - **Comparative Analysis:** Compare segments, groups, or time periods.

3. **If a User Question is Provided:**
   - Generate questions that are closely related to the user's previous question.
   - Use **random category selection** to introduce diverse perspectives.
   - Apply the analysis techniques above to enhance relevance and depth.

4. **If No User Question is Provided:**
   - Ensure questions cover different aspects of the data model.
   - Randomly distribute questions across all categories.

5. **General Guidelines for All Questions:**
   - Ensure questions can be answered using the data model.
   - Mix simple and complex questions.
   - Avoid open-ended questions – each should have a definite answer.
   - Incorporate time-based analysis where relevant.
   - Combine multiple analysis techniques when appropriate.
"""

question_recommendation_template = """
Data Model Specification:
{models}

Previous Questions: {previous_questions}

Categories: {categories}

Current Date: {current_date}

Please generate {max_questions} sql related insightful questions for each of the {max_categories} categories based on the provided data model. Both the questions and category names should be translated into {language}. If previous questions are provided, ensure the new questions are related to the user's question.

**CRITICAL: You MUST respond with ONLY a valid JSON object. No explanations, no markdown formatting, no additional text.**

**REQUIRED JSON FORMAT:**
{{
    "questions": {{
        "User Engagement": [
            {{"question": "question 1"}},
            {{"question": "question 2"}}
        ],
        "Activity Performance": [
            {{"question": "question 1"}},
            {{"question": "question 2"}}
        ],
        "Organizational Insights": [
            {{"question": "question 1"}},
            {{"question": "question 2"}}
        ]
    }},
    "categories": ["User Engagement", "Activity Performance", "Organizational Insights"],
    "reasoning": "Brief explanation of the question generation approach"
}}

**REMEMBER: Your entire response must be ONLY this JSON object, nothing else.**
"""


class Question(BaseModel):
    question: str
    category: str


class QuestionResult(BaseModel):
    questions: list[Question]


class QuestionRecommendation:
    def __init__(
        self,
        doc_store_provider: DocumentStoreProvider,
    ):
        self.doc_store_provider = doc_store_provider
        self.llm = get_llm()

    @observe(name="Question Recommendation")
    async def run(
        self,
        user_question: str,
        mdl: dict,
        previous_questions: list[str] = [],
        categories: list[str] = [],
        language: str = "en",
        current_date: str = datetime.now().strftime("%Y-%m-%d %A %H:%M:%S"),
        max_questions: int = 5,
        max_categories: int = 3,
        **_,
    ) -> dict:
        logger.info("Question Recommendation pipeline is running...")

        try:
            # Create prompt for question recommendation
            prompt = PromptTemplate(
                input_variables=[
                    "models",
                    "previous_questions",
                    "categories",
                    "current_date",
                    "max_questions",
                    "max_categories",
                    "language",
                    "user_question"
                ],
                template=question_recommendation_template
            )
            print(f"Prompt: {prompt}")
            
            
            # Create the chain with system prompt
            chain = prompt | self.llm
            print(f"Chain is created")
            
            # Generate questions
            result = await chain.ainvoke({
                "models": mdl,
                "previous_questions": previous_questions,
                "categories": categories,
                "current_date": current_date,
                "max_questions": max_questions,
                "max_categories": max_categories,
                "language": language,
                "user_question": user_question
            })

            # Parse the result
            print(f"Result: {result}")
            try:
                # Try to parse as JSON first
                content = result.content
                logger.info(f"Raw LLM response: {content}")
                
                # Try to extract JSON from the response
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group(0)
                    logger.info(f"Extracted JSON: {json_str}")
                    recommendations = orjson.loads(json_str)
                    logger.info(f"Parsed JSON successfully: {recommendations}")
                else:
                    # Fallback to markdown parsing if no JSON found
                    logger.warning("No JSON found in response, falling back to markdown parsing")
                    recommendations = {"content": content}
                    print(f"Recommendations: {recommendations}")
                    
            except orjson.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Response content: {result}")
                return {
                    "status": "failed",
                    "error": {
                        "code": "JSON_PARSE_ERROR",
                        "message": f"Failed to parse JSON response: {str(e)}"
                    }
                }
            except Exception as e:
                logger.error(f"Failed to parse response: {str(e)}")
                logger.error(f"Response content: {result}")
                return {
                    "status": "failed",
                    "error": {
                        "code": "PARSE_ERROR",
                        "message": f"Failed to parse response: {str(e)}"
                    }
                }
            
            # Update metrics
            self.doc_store_provider.update_metrics("question_recommendation", "query")

            return {
                "status": "success",
                "response": recommendations
            }

        except Exception as e:
            logger.error(f"An error occurred during question recommendation generation: {str(e)}")
            return {
                "status": "failed",
                "error": {
                    "code": "GENERATION_ERROR",
                    "message": f"An error occurred during question recommendation generation: {str(e)}"
                }
            }

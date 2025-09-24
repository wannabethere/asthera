import asyncio
import logging
from typing import Dict, Literal, Optional, List,Any
import json

import orjson
from cachetools import TTLCache
from langfuse.decorators import observe
from pydantic import BaseModel

from app.agents.pipelines.base import Pipeline as BasicPipeline
from app.agents.nodes.sql.utils.sql_prompts import Configuration
from app.services.sql.models import Error, Event
from app.agents.pipelines.pipeline_container import PipelineContainer

logger = logging.getLogger("lexy-ai-service")


class QuestionRecommendation:
    class Request(BaseModel):
        event_id: str
        mdl: str
        user_question: str
        project_id: str
        configuration: Optional[Configuration] = None
        previous_questions: List[str] = []
        max_questions: int = 5
        max_categories: int = 3
        regenerate: bool = False

    class Response(BaseModel):
        status: str
        response: Dict[str, Any]

    def __init__(self, pipelines: Optional[Dict[str, any]] = None):
        self._pipeline_container = PipelineContainer.get_instance()
        self._pipelines = self._pipeline_container.get_all_pipelines()

    def _handle_exception(
        self,
        event_id: str,
        error_message: str,
        code: str = "OTHERS",
        trace_id: Optional[str] = None,
    ):
        self._cache[event_id] = Event(
            event_id=event_id,
            status="failed",
            error=Error(code=code, message=error_message),
            trace_id=trace_id,
        )
        logger.error(error_message)

    async def _document_retrieval(self, candidate: dict, project_id: str) -> tuple[list[str], bool, bool]:
        # Get database schemas
        schema_result = await self._pipeline_container.get_pipeline("database_schemas").run(
            query=candidate["question"],
            project_id=project_id,
            retrieval_type="database_schemas",
            table_retrieval={
                "table_retrieval_size": 10,
                "table_column_retrieval_size": 100,
                "allow_using_db_schemas_without_pruning": False
            }
        )
        
        
        #TODO: Add metrics and views retrieval
        # Get metrics and views
        metrics_result = await self._pipeline_container.get_pipeline("metrics").run(
            query=candidate["question"],
            project_id=project_id,
            retrieval_type="metrics"
        )
        
        views_result = await self._pipeline_container.get_pipeline("views").run(
            query=candidate["question"],
            project_id=project_id,
            retrieval_type="views"
        )
        
        
        table_ddls = schema_result
        
        # Check if we have any metrics or views
        has_metric = False #len(metrics_result.get("metrics", [])) > 0
        has_calculated_field = False #len(views_result.get("views", [])) > 0
        
        return table_ddls, has_calculated_field, has_metric

    async def _sql_pairs_retrieval(self, candidate: dict, project_id: str) -> list[dict]:
        sql_pairs_result = await self._pipeline_container.get_pipeline("sql_pairs").run(
            query=candidate["question"],
            project_id=project_id,
            retrieval_type="sql_pairs"
        )
        sql_samples = sql_pairs_result["formatted_output"].get("documents", [])
        return sql_samples

    async def _instructions_retrieval(self, candidate: dict, project_id: str) -> list[dict]:
        result = await self._pipeline_container.get_pipeline("instructions").run(
            query=candidate["question"],
            project_id=project_id,
            retrieval_type="instructions"   
        )
        instructions = result["formatted_output"].get("instructions", [])
        return instructions
   
    @observe(name="Validate Question")
    async def _validate_question(
        self,
        candidate: dict,
        request_id: str,
        max_questions: int,
        max_categories: int,
        project_id: Optional[str] = None,
        configuration: Optional[Configuration] = Configuration(),
    ):
       

        try:
            _document, sql_samples, instructions = await asyncio.gather(
                self._document_retrieval(candidate, project_id),
                self._sql_pairs_retrieval(candidate, project_id),
                self._instructions_retrieval(candidate, project_id),
            )
            table_ddls, has_calculated_field, has_metric = _document
            

            sql_generation_reasoning = (
                await self._pipelines["sql_generation_reasoning"].run(
                    query=candidate["question"],
                    contexts=table_ddls,
                    sql_samples=sql_samples,
                    instructions=instructions,
                    configuration=configuration,
                )
            ).get("post_process", {})

            generated_sql = await self._pipelines["sql_generation"].run(
                query=candidate["question"],
                contexts=table_ddls,
                sql_generation_reasoning=sql_generation_reasoning,
                project_id=project_id,
                configuration=configuration,
                sql_samples=sql_samples,
                instructions=instructions,
                has_calculated_field=has_calculated_field,
                has_metric=has_metric,
            )

            post_process = generated_sql["post_process"]

            if len(post_process["valid_generation_results"]) == 0:
                return post_process

            valid_sql = post_process["valid_generation_results"][0]["sql"]

            # Partial update the resource
            current = self._cache[request_id]
            questions = current.response["questions"]

            if (
                candidate["category"] not in questions
                and len(questions) >= max_categories
            ):
                # Skip to update the question dictionary if it is already full
                return post_process

            currnet_category = questions.setdefault(candidate["category"], [])

            if len(currnet_category) >= max_questions:
                # Skip to update the questions for the category if it is already full
                return post_process

            currnet_category.append({**candidate, "sql": valid_sql})
            return post_process

        except Exception as e:
            logger.error(f"Request {request_id}: Error validating question: {str(e)}")

    def _extract_recommendations(self, result: dict) -> dict:
        """Extract and format recommendations from the result"""
        post_process = result["post_process"]
        content = post_process.get("content", "")
        
        # Initialize result dictionary
        result_dict = {
            "questions": {},
            "categories": [],
            "reasoning": ""
        }
        
        try:
            # Try to parse as JSON first (expected format)
            import json
            # Extract JSON from content if it's wrapped in markdown code blocks
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                if json_end != -1:
                    json_content = content[json_start:json_end].strip()
                else:
                    json_content = content[json_start:].strip()
            elif "```" in content:
                # Handle case where JSON is in generic code block
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                if json_end != -1:
                    json_content = content[json_start:json_end].strip()
                else:
                    json_content = content[json_start:].strip()
            else:
                # Try to find JSON object in the content
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_content = content[json_start:json_end]
                else:
                    json_content = content
            
            # Parse the JSON
            parsed_data = json.loads(json_content)
            
            if "questions" in parsed_data and isinstance(parsed_data["questions"], list):
                # Process questions from JSON format
                for question_item in parsed_data["questions"]:
                    if isinstance(question_item, dict) and "question" in question_item and "category" in question_item:
                        category = question_item["category"]
                        question_text = question_item["question"]
                        
                        if category not in result_dict["questions"]:
                            result_dict["questions"][category] = []
                            result_dict["categories"].append(category)
                        
                        result_dict["questions"][category].append({"question": question_text})
                
                # Extract reasoning from any text outside the JSON
                reasoning_text = content
                if "```json" in content:
                    # Remove the JSON code block from reasoning
                    json_block_start = content.find("```json")
                    json_block_end = content.find("```", json_block_start + 7) + 3
                    if json_block_end > 2:
                        reasoning_text = content[:json_block_start] + content[json_block_end:]
                elif "```" in content:
                    json_block_start = content.find("```")
                    json_block_end = content.find("```", json_block_start + 3) + 3
                    if json_block_end > 2:
                        reasoning_text = content[:json_block_start] + content[json_block_end:]
                elif json_start != -1 and json_end > json_start:
                    reasoning_text = content[:json_start] + content[json_end:]
                
                result_dict["reasoning"] = reasoning_text.strip()
                
            else:
                # Fallback to markdown parsing if JSON parsing fails
                self._parse_markdown_format(content, result_dict)
                
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse JSON response, falling back to markdown parsing: {str(e)}")
            # Fallback to markdown parsing
            self._parse_markdown_format(content, result_dict)
        
        return result_dict
    
    def _parse_markdown_format(self, content: str, result_dict: dict) -> None:
        """Fallback method to parse markdown format"""
        lines = content.split('\n')
        current_category = None
        reasoning = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for category headers
            if line.startswith('### Category'):
                current_category = line.replace('### Category', '').strip(': ')
                result_dict["categories"].append(current_category)
                result_dict["questions"][current_category] = []
            # Check for numbered questions
            elif line[0].isdigit() and '. ' in line:
                if current_category:
                    question = line.split('. ', 1)[1]
                    result_dict["questions"][current_category].append({"question": question})
            # Add any non-category, non-question lines to reasoning
            elif not line.startswith('###') and not line[0].isdigit():
                reasoning.append(line)
        
        result_dict["reasoning"] = "\n".join(reasoning).strip()
    
    async def recommend(self, request: Request) -> Response:
        """Generate question recommendations based on the user's question and context"""
        try:
            # Convert configuration to dict if it exists
            config_dict = request.configuration.dict() if request.configuration else {}

            # Get question recommendation pipeline
            recommendation_pipeline = self._pipeline_container.get_pipeline("question_recommendation")
            if not recommendation_pipeline:
                raise ValueError("Question recommendation pipeline not found")
            
            candidate = {
                "question": request.user_question,
                "previous_questions": request.previous_questions
            }
            _document, sql_samples = await asyncio.gather(
                self._document_retrieval(candidate, request.project_id),
                self._sql_pairs_retrieval(candidate, request.project_id)
            )
            table_ddls, _, _ = _document
            models= {
                "table_ddls": table_ddls,
                "sql_samples": sql_samples
            }
            

            # Generate recommendations
            result = await recommendation_pipeline.run(
                user_question=request.user_question,
                mdl=models,
                project_id=request.project_id,
                configuration=config_dict,
                previous_questions=request.previous_questions,
                max_questions=request.max_questions,
                max_categories=request.max_categories,
                regenerate=request.regenerate
            )
            print("result in question recommendation", result)
            # Process and format the results
            if result and "post_process" in result:
                return self.Response(
                    status="finished",
                    response=self._extract_recommendations(result)
                )
            else:
                logger.error("No recommendations generated from pipeline")
                return self.Response(
                    status="failed",
                    response={
                        "questions": {},
                        "categories": [],
                        "reasoning": "Failed to generate recommendations"
                    }
                )

        except Exception as e:
            logger.error(f"An error occurred during question recommendation generation: {str(e)}")
            return self.Response(
                status="error",
                response={
                    "questions": {},
                    "categories": [],
                    "reasoning": f"Error: {str(e)}"
                }
            )

    def __getitem__(self, id: str) -> Event:
        response = self._cache.get(id)

        if response is None:
            message = f"Question Recommendation Resource with ID '{id}' not found."
            logger.exception(message)
            return Event(
                event_id=id,
                status="failed",
                error=Error(code="RESOURCE_NOT_FOUND", message=message),
            )

        return response

    def __setitem__(self, id: str, value: Event):
        self._cache[id] = value

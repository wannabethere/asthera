"""
Node functions for Contextual Assistants

Each node performs a specific function in the assistant workflow:
1. Intent Understanding - Analyzes user query to determine intent
2. Context Retrieval - Retrieves relevant contexts from contextual graph
3. Contextual Reasoning - Performs context-aware reasoning
4. Q&A Agent - Answers questions using contextual information
5. Writer Agent - Generates written content based on context
6. Graph Router - Routes to other graphs if needed
"""
import json
import logging
from typing import Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.messages import HumanMessage, AIMessage

from .state import ContextualAssistantState
from .actor_types import get_actor_config, get_actor_prompt_context

logger = logging.getLogger(__name__)


class IntentUnderstandingNode:
    """Node that understands user intent and determines routing"""
    
    def __init__(self, llm: Optional[ChatOpenAI] = None, model_name: str = "gpt-4o-mini"):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Understand user intent and determine next steps"""
        logger.info("IntentUnderstandingNode: Starting execution")
        query = state.get("query", "")
        actor_type = state.get("actor_type", "consultant")
        project_id = state.get("project_id")
        user_context = state.get("user_context", {})
        
        logger.info(f"IntentUnderstandingNode: query={query[:100] if query else 'None'}, actor_type={actor_type}, project_id={project_id}")
        
        # Extract project_id from user_context if not directly in state
        if not project_id and isinstance(user_context, dict):
            project_id = user_context.get("project_id")
            logger.info(f"IntentUnderstandingNode: Extracted project_id from user_context: {project_id}")
        
        if not query:
            logger.error("IntentUnderstandingNode: No query provided")
            state["status"] = "error"
            state["error"] = "No query provided"
            return state
        
        try:
            logger.info("IntentUnderstandingNode: Building prompt and invoking LLM")
            # Get actor context
            actor_context = get_actor_prompt_context(actor_type)
            
            # Extract domain and product information from user_context
            domain = None
            product = None
            if user_context and isinstance(user_context, dict):
                domain = user_context.get("domain")
                product = user_context.get("product") or project_id  # Use project_id as product if product not specified
            
            logger.info(f"IntentUnderstandingNode: Using context - actor={actor_type}, domain={domain}, product={product}, project_id={project_id}")
            
            # Build context information for intent understanding
            # Focus on: actor types, domain, product, and available context docs only
            # DO NOT include schema information - this causes performance issues
            context_info = ""
            
            # Actor type information
            if actor_type:
                context_info += f"\nActor Type: {actor_type}\n"
            
            # Domain information
            if domain:
                context_info += f"\nDomain: {domain}\n"
            
            # Product/Project information
            if product or project_id:
                product_name = product or project_id
                context_info += f"\nProduct/Project: {product_name}\n"
                context_info += "Consider product-specific context when determining intent.\n"
            
            # Additional context items (excluding project_id, domain, product which are handled above)
            if user_context and isinstance(user_context, dict):
                context_items = {
                    k: v for k, v in user_context.items() 
                    if k not in ["project_id", "domain", "product"] and v is not None
                }
                if context_items:
                    # Format context_items as JSON to avoid curly braces being interpreted as template variables
                    context_info += f"\nAdditional Context: {json.dumps(context_items, indent=2)}\n"
            
            # Intent understanding prompt
            # Use template variables instead of f-string interpolation to avoid JSON braces being interpreted as variables
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an intent understanding system for a contextual assistant.

{actor_context}
{context_info}

Your task is to analyze the user's query and:
1. Suggest the steps or purpose of the question
2. Determine the primary intent based on actor type, domain, product, and available context
3. Identify what actions are needed
4. Specify what context types are required

CRITICAL: 
- DO NOT use or reference MDL schemas, database schemas, or data structures
- Focus ONLY on: actor types, domain, product information, and available context documents
- This is a lightweight intent understanding step - schema retrieval happens later in the workflow
- Your goal is to understand the PURPOSE and SUGGEST STEPS, not to analyze data structures

If a project/product is provided, consider that this query may require:
- Retrieving relevant context documents for this product/domain
- Using product-specific instructions and context
- Understanding the actor's role and typical actions

Return JSON with:
- intent: one of ['question', 'execution', 'analysis', 'writing', 'graph_query', 'general']
  - 'question': User wants an answer/explanation (use Q&A node)
  - 'execution': User wants to perform actions/operations (use Executor node)
  - 'analysis': User wants analysis (use Q&A node with analysis focus)
  - 'writing': User wants written content (use Q&A then Writer)
  - 'graph_query': User wants to query another graph
  - 'general': General query
- confidence: float between 0.0 and 1.0
- reasoning: why this intent was chosen (focus on actor, domain, product, and purpose)
- suggested_steps: list of suggested steps to address the query (e.g., ['understand context', 'retrieve relevant docs', 'analyze information'])
- purpose: brief description of the purpose of this query
- required_context_types: list of context types needed (e.g., ['organizational', 'temporal', 'project', 'domain'])
- actions: list of actions needed (e.g., ['retrieve_context', 'reason', 'answer', 'execute'])
- needs_writing: boolean indicating if written content is needed
- needs_graph: boolean indicating if another graph should be invoked
- execution_type: if intent is 'execution', what type of execution (e.g., 'query', 'analysis', 'generation')
"""),
                ("human", "Query: {query}")
            ])
            
            chain = prompt | self.llm | self.json_parser
            logger.info("IntentUnderstandingNode: Invoking LLM chain")
            
            # Add timeout to prevent hanging
            import asyncio
            try:
                result = await asyncio.wait_for(
                    chain.ainvoke({
                        "query": query,
                        "actor_context": actor_context,
                        "context_info": context_info or ""
                    }),
                    timeout=30.0  # 30 second timeout
                )
                logger.info(f"IntentUnderstandingNode: LLM returned result: {result}")
            except asyncio.TimeoutError:
                logger.error("IntentUnderstandingNode: LLM call timed out after 30 seconds")
                raise Exception("LLM call timed out - the model may be unresponsive")
            except Exception as e:
                logger.error(f"IntentUnderstandingNode: LLM call failed: {str(e)}", exc_info=True)
                raise
            
            # Log intent understanding result
            logger.info(f"Intent understanding result - intent={result.get('intent')}, confidence={result.get('confidence')}, purpose={result.get('purpose', 'N/A')[:100] if result.get('purpose') else 'N/A'}, suggested_steps={len(result.get('suggested_steps', []))} steps")
            
            # Update state
            state["intent"] = result.get("intent", "general")
            state["intent_confidence"] = result.get("confidence", 0.5)
            state["intent_details"] = result
            # Store suggested steps and purpose for downstream nodes
            if "suggested_steps" in result:
                state["suggested_steps"] = result.get("suggested_steps", [])
            if "purpose" in result:
                state["query_purpose"] = result.get("purpose", "")
            
            # Determine next node (always retrieve context first)
            intent = result.get("intent", "general")
            state["next_node"] = "retrieve_context"  # Always go to context retrieval first
            
            state["current_node"] = "intent_understanding"
            state["status"] = "processing"
            
            logger.info(f"IntentUnderstandingNode: Intent understood: {intent} (confidence: {state['intent_confidence']}), next_node: {state['next_node']}")
            logger.info(f"IntentUnderstandingNode: Returning state with keys: {list(state.keys())}")
            
        except Exception as e:
            logger.error(f"IntentUnderstandingNode: Error in intent understanding: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["intent"] = "general"
            state["intent_confidence"] = 0.0
            state["next_node"] = "retrieve_context"
        
        logger.info(f"IntentUnderstandingNode: Execution complete, returning state")
        return state


class ContextRetrievalNode:
    """Node that retrieves relevant contexts from contextual graph"""
    
    def __init__(
        self,
        contextual_graph_service: Any,
        retrieval_pipeline: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini",
        retrieval_helper: Optional[Any] = None  # Optional retrieval helper for schema retrieval
    ):
        self.contextual_graph_service = contextual_graph_service
        self.retrieval_pipeline = retrieval_pipeline
        self.retrieval_helper = retrieval_helper
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Retrieve relevant contexts and create reasoning plan"""
        logger.info("ContextRetrievalNode: Starting execution")
        query = state.get("query", "")
        user_context = state.get("user_context", {})
        intent_details = state.get("intent_details", {})
        project_id = state.get("project_id")
        
        logger.info(f"ContextRetrievalNode: query={query[:100] if query else 'None'}, project_id={project_id}, intent_details={intent_details}")
        
        # Extract project_id from user_context if not directly in state
        if not project_id and isinstance(user_context, dict):
            project_id = user_context.get("project_id")
            logger.info(f"ContextRetrievalNode: Extracted project_id from user_context: {project_id}")
        
        try:
            # STEP 1: First do context breakdown via retrieval pipeline
            # This will break down the query into compliance, action, product, intent, etc.
            # DO NOT retrieve database schemas before this - it can lead to confusion
            # Extract actor, domain, and product information from state/user_context
            actor_type = state.get("actor_type") or user_context.get("actor_type")
            domain = user_context.get("domain")
            product = user_context.get("product") or project_id  # Use project_id as product if available
            
            # Build lists for context breakdown
            available_actors = [actor_type] if actor_type else None
            available_domains = [domain] if domain else None
            available_products = [product] if product else None
            
            retrieval_input = {
                "query": query,
                "context_ids": user_context.get("context_ids"),  # If user has specific contexts
                "include_all_contexts": True,
                "top_k": 5,
                "filters": user_context.get("filters"),
                # Pass actor, domain, and product information to help context breakdown
                "available_actors": available_actors,
                "available_domains": available_domains,
                "available_products": available_products
            }
            
            logger.info(f"ContextRetrievalNode: Running retrieval pipeline to get context breakdown first (actor={actor_type}, domain={domain}, product={product})")
            retrieval_result = await self.retrieval_pipeline.run(
                inputs=retrieval_input
            )
            
            # Extract context breakdown from retrieval result
            context_breakdown = None
            if retrieval_result.get("success"):
                data = retrieval_result.get("data", {})
                
                # Get context breakdown from retrieval result (if available)
                if "context_breakdown" in data:
                    context_breakdown = data["context_breakdown"]
                    logger.info(f"ContextRetrievalNode: Got context breakdown - compliance={context_breakdown.get('compliance_context')}, action={context_breakdown.get('action_context')}, product={context_breakdown.get('product_context')}")
                
                state["context_ids"] = data.get("context_ids", [])
                state["context_metadata"] = data.get("contexts", [])
                reasoning_plan = data.get("reasoning_plan")
                
                # Store context breakdown in state for deep research to use
                if context_breakdown:
                    state["context_breakdown"] = context_breakdown
                    # Also store as generic_breakdown for compatibility with deep research
                    state["generic_breakdown"] = {
                        "compliance_context": context_breakdown.get("compliance_context"),
                        "action_context": context_breakdown.get("action_context"),
                        "product_context": context_breakdown.get("product_context"),
                        "user_intent": context_breakdown.get("user_intent"),
                        "frameworks": context_breakdown.get("frameworks", []),
                        "identified_entities": context_breakdown.get("identified_entities", []),
                        "query_type": "mdl_query" if context_breakdown.get("identified_entities") else "general"
                    }
            
            # STEP 2: Now retrieve database schemas AFTER context breakdown
            # Use the breakdown to inform what schemas to retrieve
            schema_info = None
            if project_id and self.retrieval_helper:
                try:
                    # Build query based on context breakdown if available
                    schema_query = query
                    if context_breakdown:
                        # Use action_context and user_intent to build better schema query
                        breakdown_parts = []
                        if context_breakdown.get("action_context"):
                            breakdown_parts.append(context_breakdown["action_context"])
                        if context_breakdown.get("user_intent"):
                            breakdown_parts.append(context_breakdown["user_intent"])
                        if breakdown_parts:
                            schema_query = " ".join(breakdown_parts)
                            logger.info(f"ContextRetrievalNode: Using context breakdown to inform schema retrieval: {schema_query[:100]}")
                    
                    logger.info(f"ContextRetrievalNode: Retrieving database schemas for project {project_id} based on context breakdown")
                    db_schemas = await self.retrieval_helper.get_database_schemas(
                        project_id=project_id,
                        table_retrieval={
                            "table_retrieval_size": 5,  # Limit to top 5 for reasoning plan
                            "table_column_retrieval_size": 50,
                            "allow_using_db_schemas_without_pruning": False
                        },
                        query=schema_query  # Use breakdown-informed query
                    )
                    schemas = db_schemas.get("schemas", [])
                    if schemas:
                        schema_info = {
                            "schemas_count": len(schemas),
                            "schema_names": [s.get("table_name", "Unknown") for s in schemas[:5]],
                            "schema_summary": self._format_schema_summary_for_plan(schemas[:5])
                        }
                        logger.info(f"ContextRetrievalNode: Retrieved {len(schemas)} schemas based on context breakdown")
                        state["db_schemas"] = schemas  # Store full schemas for deep research
                except Exception as e:
                    logger.warning(f"ContextRetrievalNode: Error retrieving schemas after breakdown: {e}", exc_info=True)
            
            # STEP 3: Enhance reasoning plan with schema information if available
            if retrieval_result.get("success"):
                if reasoning_plan and schema_info:
                    reasoning_plan = self._enhance_reasoning_plan_with_schemas(
                        reasoning_plan, 
                        schema_info,
                        query
                    )
                    state["reasoning_plan"] = reasoning_plan
                else:
                    state["reasoning_plan"] = reasoning_plan
            else:
                logger.warning(f"Context retrieval failed: {retrieval_result.get('error')}")
                state["context_ids"] = []
                state["context_metadata"] = []
                state["reasoning_plan"] = None
            
            # Determine next node based on intent
            intent = state.get("intent", "general")
            if intent == "question":
                state["next_node"] = "contextual_reasoning"
            elif intent == "analysis":
                state["next_node"] = "contextual_reasoning"
            elif intent == "writing":
                state["next_node"] = "contextual_reasoning"
            else:
                state["next_node"] = "contextual_reasoning"
            
            state["current_node"] = "context_retrieval"
            logger.info(f"ContextRetrievalNode: Retrieved {len(state.get('context_ids', []))} contexts, next_node: {state.get('next_node')}")
            logger.info(f"ContextRetrievalNode: Returning state with keys: {list(state.keys())}")
            
        except Exception as e:
            logger.error(f"ContextRetrievalNode: Error in context retrieval: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["context_ids"] = []
            state["next_node"] = "qa_agent"  # Fallback to Q&A
            
        logger.info("ContextRetrievalNode: Execution complete, returning state")
        return state
    
    def _format_schema_summary_for_plan(self, schemas: List[Dict[str, Any]]) -> str:
        """Format schema summary for reasoning plan"""
        if not schemas:
            return ""
        
        summary_parts = []
        for schema in schemas:
            table_name = schema.get("table_name", "Unknown")
            table_ddl = schema.get("table_ddl", "")
            # Extract key columns from DDL
            summary_parts.append(f"Table: {table_name}\n{table_ddl[:300]}...")
        
        return "\n\n".join(summary_parts)
    
    def _enhance_reasoning_plan_with_schemas(
        self, 
        reasoning_plan: Dict[str, Any], 
        schema_info: Dict[str, Any],
        query: str
    ) -> Dict[str, Any]:
        """Enhance reasoning plan with schema information"""
        if not reasoning_plan:
            return reasoning_plan
        
        # Add schema information to reasoning plan
        reasoning_plan["schema_info"] = schema_info
        
        # Update strategy to mention schemas
        original_strategy = reasoning_plan.get("strategy", "")
        schema_context = f"\n\nAvailable Database Schemas: {schema_info.get('schemas_count', 0)} tables including {', '.join(schema_info.get('schema_names', [])[:3])}"
        
        if "schema" not in original_strategy.lower() and "database" not in original_strategy.lower():
            reasoning_plan["strategy"] = original_strategy + schema_context
        
        # Add schema-aware reasoning steps if needed
        reasoning_steps = reasoning_plan.get("reasoning_steps", [])
        if reasoning_steps:
            # Check if any step should consider schemas
            for step in reasoning_steps:
                step_type = step.get("step_type", "").lower()
                if step_type in ["data_analysis", "query", "execution", "metric"]:
                    step["consider_schemas"] = True
                    step["available_schemas"] = schema_info.get("schema_names", [])
        
        # Add schema summary to expected outputs
        expected_outputs = reasoning_plan.get("expected_outputs", [])
        if expected_outputs:
            expected_outputs.append({
                "type": "schema_aware_analysis",
                "description": "Analysis that considers available database schemas and table structures"
            })
            reasoning_plan["expected_outputs"] = expected_outputs
        
        logger.info(f"Enhanced reasoning plan with schema information: {schema_info.get('schemas_count')} schemas")
        return reasoning_plan


class ContextualReasoningNode:
    """Node that performs context-aware reasoning"""
    
    def __init__(
        self,
        reasoning_pipeline: Any,
        llm: Optional[ChatOpenAI] = None
    ):
        self.reasoning_pipeline = reasoning_pipeline
        self.llm = llm
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Perform context-aware reasoning and suggest relevant tables"""
        logger.info("ContextualReasoningNode: Starting reasoning")
        query = state.get("query", "")
        context_ids = state.get("context_ids", [])
        reasoning_plan = state.get("reasoning_plan")
        intent = state.get("intent", "general")
        project_id = state.get("project_id")
        
        logger.info(f"ContextualReasoningNode: Input - query={query[:100]}, intent={intent}, context_ids={context_ids}, has_reasoning_plan={bool(reasoning_plan)}")
        
        if not context_ids:
            logger.warning("ContextualReasoningNode: No contexts available for reasoning")
            state["next_node"] = "qa_agent"
            return state
        
        try:
            # Use primary context for reasoning
            primary_context_id = context_ids[0] if context_ids else None
            
            if not primary_context_id:
                logger.warning("ContextualReasoningNode: No primary context ID")
                state["next_node"] = "qa_agent"
                return state
            
            logger.info(f"ContextualReasoningNode: Using primary_context_id={primary_context_id}")
            
            # For data assistance, suggest relevant tables first
            # This helps focus data retrieval on the most relevant tables
            # Check if reasoning plan requires schema/table retrieval
            should_retrieve_schemas = False
            if reasoning_plan:
                reasoning_steps = reasoning_plan.get("reasoning_steps", [])
                for step in reasoning_steps:
                    stores_to_query = step.get("stores_to_query", [])
                    if isinstance(stores_to_query, list) and "schemas" in stores_to_query:
                        should_retrieve_schemas = True
                        logger.info("Reasoning plan explicitly requires schema retrieval")
                        break
                    if step.get("table_retrieval_needed") or step.get("consider_schemas"):
                        should_retrieve_schemas = True
                        logger.info("Reasoning plan step indicates schema/table retrieval needed")
                        break
            
            suggested_tables = []
            # Always suggest tables for data assistance queries, or if reasoning plan requires it
            if project_id and hasattr(self.reasoning_pipeline, 'agent') and (should_retrieve_schemas or project_id):
                logger.info("ContextualReasoningNode: Suggesting relevant tables for data assistance")
                try:
                    table_suggestion_result = await self.reasoning_pipeline.agent.suggest_relevant_tables(
                        query=query,
                        context_id=primary_context_id,
                        project_id=project_id,
                        top_k=10,
                        reasoning_plan=reasoning_plan if should_retrieve_schemas else None
                    )
                    if table_suggestion_result.get("success"):
                        suggested_tables = table_suggestion_result.get("suggested_tables", [])
                        state["suggested_tables"] = suggested_tables
                        state["table_suggestion_strategy"] = table_suggestion_result.get("overall_strategy", "")
                        state["table_relationships"] = table_suggestion_result.get("table_relationships", [])
                        logger.info(f"ContextualReasoningNode: Suggested {len(suggested_tables)} relevant tables")
                    else:
                        logger.warning(f"Table suggestion failed: {table_suggestion_result.get('error')}")
                except Exception as e:
                    logger.warning(f"Error suggesting tables: {e}")
                    # Continue without table suggestions
            
            # Determine reasoning type based on intent
            reasoning_type = "multi_hop"
            if intent == "analysis":
                reasoning_type = "priority_controls"
            elif intent == "question":
                reasoning_type = "multi_hop"
            
            # Run reasoning pipeline
            reasoning_input = {
                "query": query,
                "context_id": primary_context_id,
                "reasoning_plan": reasoning_plan,
                "max_hops": 3,
                "reasoning_type": reasoning_type
            }
            
            reasoning_result = await self.reasoning_pipeline.run(
                inputs=reasoning_input
            )
            
            if reasoning_result.get("success"):
                data = reasoning_result.get("data", {})
                state["reasoning_result"] = data
                state["reasoning_path"] = data.get("reasoning_path", [])
            else:
                logger.warning(f"Reasoning failed: {reasoning_result.get('error')}")
                state["reasoning_result"] = None
                state["reasoning_path"] = []
            
            # Next node will be determined by routing based on intent
            state["current_node"] = "contextual_reasoning"
            logger.info("Contextual reasoning completed")
            
        except Exception as e:
            logger.error(f"Error in contextual reasoning: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["next_node"] = "qa_agent"  # Fallback
        
        # Return only the fields we updated to avoid conflicts
        # Build result with required fields first
        result = {}
        
        # Required fields (always include if set)
        if "reasoning_result" in state:
            result["reasoning_result"] = state["reasoning_result"]
        if "reasoning_path" in state:
            result["reasoning_path"] = state.get("reasoning_path", [])
        if "current_node" in state and state.get("current_node"):
            result["current_node"] = state["current_node"]
        if "next_node" in state:
            result["next_node"] = state["next_node"]
        
        # Optional fields (only include if actually set)
        if state.get("suggested_tables"):
            result["suggested_tables"] = state["suggested_tables"]
        if state.get("table_suggestion_strategy"):
            result["table_suggestion_strategy"] = state["table_suggestion_strategy"]
        if state.get("table_relationships"):
            result["table_relationships"] = state["table_relationships"]
        if state.get("status"):
            result["status"] = state["status"]
        if state.get("error"):
            result["error"] = state["error"]
        
        return result


class QAAgentNode:
    """Node that answers questions using contextual information"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Answer question using contextual information"""
        query = state.get("query", "")
        actor_type = state.get("actor_type", "consultant")
        reasoning_result = state.get("reasoning_result", {})
        reasoning_path = state.get("reasoning_path", [])
        context_metadata = state.get("context_metadata", [])
        
        try:
            # Get actor context
            actor_context = get_actor_prompt_context(actor_type)
            actor_config = get_actor_config(actor_type)
            
            # Build context summary
            context_summary = ""
            if context_metadata:
                context_summary = "\n".join([
                    f"- {ctx.get('context_name', 'Unknown')}: {ctx.get('context_definition', {}).get('industry', 'N/A')}"
                    for ctx in context_metadata[:3]
                ])
            
            # Build reasoning summary
            reasoning_summary = ""
            if reasoning_path:
                reasoning_summary = "\n".join([
                    f"Step {i+1}: {hop.get('reasoning', 'N/A')}"
                    for i, hop in enumerate(reasoning_path[:5])
                ])
            
            final_answer = reasoning_result.get("final_answer", "") if reasoning_result else ""
            
            # Q&A prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are a contextual Q&A assistant.

{actor_context}

You answer questions using context-aware information from a contextual graph system.
Your answers should be:
- Context-specific and relevant to the user's situation
- Aligned with the {actor_config['communication_style']} style
- At {actor_config['preferred_detail_level']} detail level
- Focused on: {', '.join(actor_config['focus_areas'])}

Use the reasoning path and context information provided to give accurate, context-aware answers."""),
                ("human", """Answer this question: {query}

Context Information:
{context_summary}

Reasoning Path:
{reasoning_summary}

Reasoning Result:
{final_answer}

Provide a clear, context-aware answer that directly addresses the question.
If the reasoning result provides an answer, use it as the foundation.
If additional context is needed, indicate what's missing.
""")
            ])
            
            chain = prompt | self.llm
            response = await chain.ainvoke({
                "query": query,
                "context_summary": context_summary or "No specific context available",
                "reasoning_summary": reasoning_summary or "No reasoning path available",
                "final_answer": final_answer or "No direct answer from reasoning"
            })
            
            answer = response.content if hasattr(response, "content") else str(response)
            
            # Extract sources from reasoning path
            sources = []
            for hop in reasoning_path:
                entities = hop.get("entities_found", [])
                if entities:
                    sources.append({
                        "type": hop.get("entity_type", "unknown"),
                        "entities": entities[:5],
                        "reasoning": hop.get("reasoning", "")
                    })
            
            state["qa_answer"] = answer
            state["qa_sources"] = sources
            state["qa_confidence"] = state.get("intent_confidence", 0.5)
            
            # Add to messages
            messages = list(state.get("messages", []))
            messages.append(HumanMessage(content=query))
            messages.append(AIMessage(content=answer))
            state["messages"] = messages
            
            # Always route to writer node (writer will decide what to do)
            state["next_node"] = "writer_agent"
            state["current_node"] = "qa_agent"
            logger.info("Q&A answer generated")
            
        except Exception as e:
            logger.error(f"Error in Q&A agent: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["qa_answer"] = f"Error generating answer: {str(e)}"
            state["next_node"] = "finalize"
        
        return state


class ExecutorNode:
    """Node that executes actions/operations based on user intent"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Execute actions based on user intent"""
        query = state.get("query", "")
        actor_type = state.get("actor_type", "consultant")
        reasoning_result = state.get("reasoning_result", {})
        reasoning_path = state.get("reasoning_path", [])
        context_metadata = state.get("context_metadata", [])
        intent_details = state.get("intent_details", {})
        
        try:
            # Get actor context
            actor_context = get_actor_prompt_context(actor_type)
            actor_config = get_actor_config(actor_type)
            
            # Build context summary
            context_summary = ""
            if context_metadata:
                context_summary = "\n".join([
                    f"- {ctx.get('context_name', 'Unknown')}: {ctx.get('context_definition', {}).get('industry', 'N/A')}"
                    for ctx in context_metadata[:3]
                ])
            
            # Build reasoning summary
            reasoning_summary = ""
            if reasoning_path:
                reasoning_summary = "\n".join([
                    f"Step {i+1}: {hop.get('reasoning', 'N/A')}"
                    for i, hop in enumerate(reasoning_path[:5])
                ])
            
            execution_type = intent_details.get("execution_type", "general")
            
            # Executor prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", f"""You are an executor that performs actions and operations based on user requests.

{actor_context}

You execute actions using context-aware information from a contextual graph system.
Your execution should:
- Be context-specific and relevant to the user's situation
- Use {actor_config['communication_style']} style for output
- Provide {actor_config['preferred_detail_level']} level of detail
- Focus on: {', '.join(actor_config['focus_areas'])}

Based on the reasoning path and context, determine what actions need to be performed and execute them.
Return a structured result with:
- actions_performed: List of actions that were executed
- results: Results from each action
- output: Formatted output for the user
- metadata: Additional metadata about the execution
"""),
                ("human", """Execute actions for this request: {query}

Execution Type: {execution_type}

Context Information:
{context_summary}

Reasoning Path:
{reasoning_summary}

Reasoning Result:
{reasoning_result}

Based on the context and reasoning, determine and execute the appropriate actions.
Return a JSON object with actions_performed, results, output, and metadata.
""")
            ])
            
            from langchain_core.output_parsers import JsonOutputParser
            json_parser = JsonOutputParser()
            
            chain = prompt | self.llm | json_parser
            result = await chain.ainvoke({
                "query": query,
                "execution_type": execution_type,
                "context_summary": context_summary or "No specific context available",
                "reasoning_summary": reasoning_summary or "No reasoning path available",
                "reasoning_result": str(reasoning_result) if reasoning_result else "No reasoning results"
            })
            
            # Store executor results
            state["executor_result"] = result
            # Ensure executor_output is always a string
            output_value = result.get("output", result)
            if isinstance(output_value, dict):
                # If output is a dict, convert to formatted string
                state["executor_output"] = json.dumps(output_value, indent=2)
            elif isinstance(output_value, (list, tuple)):
                # If output is a list, convert to formatted string
                state["executor_output"] = json.dumps(output_value, indent=2)
            else:
                state["executor_output"] = str(output_value) if output_value else str(result)
            state["executor_actions"] = result.get("actions_performed", [])
            
            # Add to messages - ensure content is a string
            messages = list(state.get("messages", []))
            executor_content = state["executor_output"]
            if not isinstance(executor_content, str):
                executor_content = str(executor_content)
            messages.append(AIMessage(content=executor_content))
            state["messages"] = messages
            
            # Always route to writer node (writer will decide what to do)
            state["next_node"] = "writer_agent"
            state["current_node"] = "executor"
            logger.info(f"Executor completed: {len(state['executor_actions'])} actions")
            
        except Exception as e:
            logger.error(f"Error in executor: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["executor_output"] = f"Error executing actions: {str(e)}"
            state["executor_result"] = {"error": str(e)}
            state["next_node"] = "writer_agent"  # Still route to writer for error handling
        
        return state


class WriterAgentNode:
    """Node that decides whether to summarize or return result based on intent reasoning"""
    
    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o"
    ):
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.3)
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Decide whether to create summary or return result, then generate output"""
        query = state.get("query", "")
        actor_type = state.get("actor_type", "consultant")
        reasoning_result = state.get("reasoning_result", {})
        qa_answer = state.get("qa_answer", "")
        executor_output = state.get("executor_output", "")
        executor_result = state.get("executor_result", {})
        context_metadata = state.get("context_metadata", [])
        intent = state.get("intent", "general")
        intent_details = state.get("intent_details", {})
        
        try:
            # Get actor context
            actor_context = get_actor_prompt_context(actor_type)
            actor_config = get_actor_config(actor_type)
            
            # Determine what input we have
            has_qa = bool(qa_answer)
            has_executor = bool(executor_output)
            
            # Decision prompt: Should we summarize or return result?
            # Note: actor_context and preferred_detail_level are interpolated at creation time
            # All other values are template variables filled at invocation time
            # Build system message using string concatenation to properly handle template variables
            preferred_detail = actor_config['preferred_detail_level']
            system_message = """You are a writer that decides how to format the final output.

""" + actor_context + """

Based on the user's intent and the available results, decide:
1. Should you create a summary? (if results are complex, multiple sources, or user asked for summary)
2. Should you return the result directly? (if result is simple, direct answer, or user asked for specific output)

Consider:
- User intent: {intent}
- Intent details: {intent_details}
- Available results: Q&A answer: {has_qa}, Executor output: {has_executor}
- Actor type: {actor_type} (prefers """ + preferred_detail + """ detail)

Return JSON with:
- decision: 'summary' or 'return_result'
- reasoning: why this decision was made
- content_type: type of content to create (if summary) or format (if return_result)
"""
            decision_prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("human", """User Query: {query}

Q&A Answer (if available):
{qa_answer}

Executor Output (if available):
{executor_output}

Make a decision: summary or return_result?
""")
            ])
            
            from langchain_core.output_parsers import JsonOutputParser
            json_parser = JsonOutputParser()
            
            logger.info("WriterAgentNode: Starting decision LLM call")
            logger.info(f"WriterAgentNode: Input - query={query[:100]}, intent={intent}, has_qa={has_qa}, has_executor={has_executor}, actor_type={actor_type}")
            logger.info(f"WriterAgentNode: qa_answer length={len(qa_answer) if qa_answer else 0}, executor_output length={len(executor_output) if executor_output else 0}")
            
            # Log the prompt inputs
            decision_inputs = {
                "query": query,
                "intent": intent,
                "intent_details": str(intent_details),
                "has_qa": str(has_qa),
                "has_executor": str(has_executor),
                "actor_type": actor_type,
                "qa_answer": qa_answer or "Not available",
                "executor_output": executor_output or "Not available"
            }
            logger.info(f"WriterAgentNode: Decision prompt inputs: {str(decision_inputs)[:1000]}...")
            
            decision_chain = decision_prompt | self.llm | json_parser
            decision_result = await decision_chain.ainvoke(decision_inputs)
            
            logger.info(f"WriterAgentNode: Decision LLM returned: {decision_result}")
            
            decision = decision_result.get("decision", "return_result")
            content_type = decision_result.get("content_type", "response")
            state["writer_decision"] = decision
            logger.info(f"WriterAgentNode: Decision={decision}, content_type={content_type}")
            
            # Build context for writing
            context_info = ""
            if context_metadata:
                context_info = "\n".join([
                    f"- {ctx.get('context_name', 'Unknown')}: {ctx.get('context_definition', {})}"
                    for ctx in context_metadata[:3]
                ])
            
            if decision == "summary":
                # Check if MDL summary is available (from MDL reasoning integration)
                mdl_summary = state.get("mdl_summary", {})
                mdl_final_result = state.get("mdl_final_result", {})
                
                # If MDL summary is available, use it as the primary source
                if mdl_summary:
                    # Format MDL summary for writer prompt
                    mdl_answer = mdl_summary.get("answer", "")
                    mdl_key_tables = mdl_summary.get("key_tables", [])
                    mdl_relationships = mdl_summary.get("relationships", "")
                    mdl_contexts = mdl_summary.get("contexts", "")
                    mdl_metrics = mdl_summary.get("metrics", [])
                    mdl_insights = mdl_summary.get("insights", "")
                    
                    # Get full schemas from data_knowledge
                    data_knowledge = state.get("data_knowledge", {})
                    schemas = data_knowledge.get("schemas", [])
                    
                    # Create a map of table_name -> schema for quick lookup
                    schema_map = {}
                    for schema in schemas:
                        table_name = schema.get("table_name", "")
                        if table_name:
                            schema_map[table_name] = schema
                    
                    # Format key tables with full schema information
                    key_tables_text = ""
                    if mdl_key_tables:
                        table_sections = []
                        for t in mdl_key_tables[:10]:
                            table_name = t.get("table_name", "Unknown")
                            description = t.get("description", "")
                            full_description = t.get("full_description", "")
                            
                            # Get DDL from MDL key_tables (enriched) or from schema_map
                            ddl = t.get("ddl", "")
                            columns = t.get("columns", [])
                            
                            # If not in MDL key_tables, try to get from schema_map
                            if not ddl and table_name in schema_map:
                                schema = schema_map[table_name]
                                ddl = schema.get("table_ddl", "")
                                if not columns:
                                    columns = schema.get("columns", [])
                            
                            # Format table information
                            table_section = f"### {table_name}\n"
                            if full_description:
                                table_section += f"**Description:** {full_description}\n\n"
                            elif description:
                                table_section += f"**Description:** {description}\n\n"
                            
                            if ddl:
                                # Format DDL - handle both string and dict formats
                                if isinstance(ddl, dict):
                                    import json
                                    ddl_str = json.dumps(ddl, indent=2)
                                else:
                                    ddl_str = str(ddl)
                                table_section += f"**Schema (DDL):**\n```sql\n{ddl_str}\n```\n\n"
                            
                            if columns:
                                table_section += f"**Columns:**\n"
                                for col in columns[:20]:  # Limit to 20 columns
                                    if isinstance(col, dict):
                                        col_name = col.get("name", col.get("column_name", ""))
                                        col_type = col.get("type", col.get("data_type", ""))
                                        col_desc = col.get("description", "")
                                        if col_name:
                                            col_info = f"- `{col_name}`"
                                            if col_type:
                                                col_info += f" ({col_type})"
                                            if col_desc:
                                                col_info += f": {col_desc}"
                                            table_section += col_info + "\n"
                                    elif isinstance(col, str):
                                        table_section += f"- `{col}`\n"
                                table_section += "\n"
                            
                            table_sections.append(table_section)
                        
                        key_tables_text = "\n".join(table_sections)
                    
                    # Check if deep research was skipped
                    skip_deep_research = state.get("skip_deep_research", False)
                    deep_research_note = ""
                    if skip_deep_research:
                        deep_research_note = "\n\n**Note:** This is a simplified analysis focusing on table recommendations. Deep contextual edge analysis was not performed."
                    
                    # Format metrics
                    metrics_text = ""
                    if mdl_metrics:
                        if isinstance(mdl_metrics, list):
                            metrics_text = "\n".join([
                                f"- {m.get('metric_name', m.get('name', 'Unknown'))}: {m.get('description', '')[:200]}"
                                for m in mdl_metrics[:10]
                            ])
                        else:
                            metrics_text = str(mdl_metrics)[:500]
                    
                    # Get additional data from data_knowledge for comprehensive summary
                    existing_metrics = data_knowledge.get("metrics", []) if data_knowledge else []
                    controls = data_knowledge.get("controls", []) if data_knowledge else []
                    features = data_knowledge.get("features", []) if data_knowledge else []
                    generated_metrics = state.get("generated_metrics", [])
                    
                    # Format additional data
                    additional_metrics_text = ""
                    if existing_metrics or generated_metrics:
                        additional_metrics_text = "**Additional Metrics:**\n"
                        for metric in (existing_metrics + generated_metrics)[:10]:
                            name = metric.get("metric_name") or metric.get("name", "Unknown")
                            desc = metric.get("description", "")
                            additional_metrics_text += f"- {name}: {desc[:200]}\n"
                    
                    controls_text = ""
                    if controls:
                        controls_text = "**Compliance Controls:**\n"
                        for control in controls[:10]:
                            if isinstance(control, dict):
                                control_obj = control.get("control") or control
                                control_id = control_obj.get("control_id", "Unknown")
                                control_name = control_obj.get("control_name", "")
                                controls_text += f"- {control_id}: {control_name}\n"
                    
                    features_text = ""
                    if features:
                        features_text = "**Features:**\n"
                        for feature in features[:10]:
                            feature_name = feature.get("display_name") or feature.get("feature_name", "Unknown")
                            feature_desc = feature.get("description", "")
                            features_text += f"- {feature_name}: {feature_desc[:200]}\n"
                    
                    # Create a summary using MDL results with actor context and full schemas
                    summary_prompt = ChatPromptTemplate.from_messages([
                        ("system", f"""You are a professional writer creating {content_type} documents.

{actor_context}

Create a comprehensive markdown summary that:
- Synthesizes information from MDL reasoning results, full database schemas, and other available sources
- Is context-aware and relevant to the user's situation
- Uses {actor_config['communication_style']} style
- Provides {actor_config['preferred_detail_level']} level of detail
- Focuses on: {', '.join(actor_config['focus_areas'])}
- Addresses the actor directly if specified
- Includes full table schemas with DDL and columns when relevant

Structure the summary clearly with appropriate sections:
1. Executive Summary (for the actor)
2. Key Tables and Schemas (with full DDL and columns)
3. Relationships and Contexts
4. Compliance Controls and Features
5. Metrics and Insights
6. Recommendations

The MDL reasoning has already identified relevant tables, contexts, and relationships - use this as the foundation, but include full schema details from the database schemas."""),
                        ("human", """Create a comprehensive {content_type} summary in markdown format based on:

User Query: {query}

MDL Reasoning Results (Primary Source):
- Answer: {mdl_answer}

Key Tables with Full Schemas:
{key_tables_text}

Relationships: {mdl_relationships}

Contexts: {mdl_contexts}

MDL Metrics:
{metrics_text}

{additional_metrics_text}

{controls_text}

{features_text}

Insights: {mdl_insights}

Additional Context Information:
{context_info}

Q&A Answer (if available):
{qa_answer}

Executor Output (if available):
{executor_output}

{deep_research_note}

Generate a comprehensive markdown summary that synthesizes all available information including full table schemas. The summary should be written for the actor ({actor_type}) and use appropriate tone and detail level. Include full DDL and column information for all relevant tables.
""")
                    ])
                else:
                    # Fallback to original summary generation if MDL summary not available
                    summary_prompt = ChatPromptTemplate.from_messages([
                        ("system", f"""You are a professional writer creating {content_type} documents.

{actor_context}

Create a summary that:
- Synthesizes information from all available sources
- Is context-aware and relevant to the user's situation
- Uses {actor_config['communication_style']} style
- Provides {actor_config['preferred_detail_level']} level of detail
- Focuses on: {', '.join(actor_config['focus_areas'])}

Structure the summary clearly with appropriate sections."""),
                        ("human", """Create a {content_type} summary based on:

User Query: {query}

Context Information:
{context_info}

Reasoning Results:
{reasoning_result}

Q&A Answer (if available):
{qa_answer}

Executor Output (if available):
{executor_output}

Generate a comprehensive summary that synthesizes all available information.
""")
                    ])
                
                logger.info("WriterAgentNode: Starting summary generation LLM call")
                logger.info(f"WriterAgentNode: Summary input - query={query[:100]}, content_type={content_type}")
                
                # Prepare summary inputs based on whether MDL summary is available
                if mdl_summary:
                    mdl_answer = mdl_summary.get("answer", "")
                    mdl_key_tables = mdl_summary.get("key_tables", [])
                    mdl_relationships = mdl_summary.get("relationships", "")
                    mdl_contexts = mdl_summary.get("contexts", "")
                    mdl_metrics = mdl_summary.get("metrics", [])
                    mdl_insights = mdl_summary.get("insights", "")
                    
                    # Get full schemas from data_knowledge
                    data_knowledge = state.get("data_knowledge", {})
                    schemas = data_knowledge.get("schemas", [])
                    
                    # Create a map of table_name -> schema for quick lookup
                    schema_map = {}
                    for schema in schemas:
                        table_name = schema.get("table_name", "")
                        if table_name:
                            schema_map[table_name] = schema
                    
                    # Format key tables with full schema information
                    key_tables_text = ""
                    if mdl_key_tables:
                        table_sections = []
                        for t in mdl_key_tables[:10]:
                            table_name = t.get("table_name", "Unknown")
                            description = t.get("description", "")
                            full_description = t.get("full_description", "")
                            
                            # Get DDL from MDL key_tables (enriched) or from schema_map
                            ddl = t.get("ddl", "")
                            columns = t.get("columns", [])
                            
                            # If not in MDL key_tables, try to get from schema_map
                            if not ddl and table_name in schema_map:
                                schema = schema_map[table_name]
                                ddl = schema.get("table_ddl", "")
                                if not columns:
                                    columns = schema.get("columns", [])
                            
                            # Format table information
                            table_section = f"### {table_name}\n"
                            if full_description:
                                table_section += f"**Description:** {full_description}\n\n"
                            elif description:
                                table_section += f"**Description:** {description}\n\n"
                            
                            if ddl:
                                # Format DDL - handle both string and dict formats
                                if isinstance(ddl, dict):
                                    import json
                                    ddl_str = json.dumps(ddl, indent=2)
                                else:
                                    ddl_str = str(ddl)
                                table_section += f"**Schema (DDL):**\n```sql\n{ddl_str}\n```\n\n"
                            
                            if columns:
                                table_section += f"**Columns:**\n"
                                for col in columns[:20]:  # Limit to 20 columns
                                    if isinstance(col, dict):
                                        col_name = col.get("name", col.get("column_name", ""))
                                        col_type = col.get("type", col.get("data_type", ""))
                                        col_desc = col.get("description", "")
                                        if col_name:
                                            col_info = f"- `{col_name}`"
                                            if col_type:
                                                col_info += f" ({col_type})"
                                            if col_desc:
                                                col_info += f": {col_desc}"
                                            table_section += col_info + "\n"
                                    elif isinstance(col, str):
                                        table_section += f"- `{col}`\n"
                                table_section += "\n"
                            
                            table_sections.append(table_section)
                        
                        key_tables_text = "\n".join(table_sections)
                    
                    metrics_text = ""
                    if mdl_metrics:
                        if isinstance(mdl_metrics, list):
                            metrics_text = "\n".join([
                                f"- {m.get('metric_name', m.get('name', 'Unknown'))}: {m.get('description', '')[:200]}"
                                for m in mdl_metrics[:10]
                            ])
                        else:
                            metrics_text = str(mdl_metrics)[:500]
                    
                    # Get additional data from data_knowledge
                    existing_metrics = data_knowledge.get("metrics", []) if data_knowledge else []
                    controls = data_knowledge.get("controls", []) if data_knowledge else []
                    features = data_knowledge.get("features", []) if data_knowledge else []
                    generated_metrics = state.get("generated_metrics", [])
                    
                    # Format additional data
                    additional_metrics_text = ""
                    if existing_metrics or generated_metrics:
                        additional_metrics_text = "**Additional Metrics:**\n"
                        for metric in (existing_metrics + generated_metrics)[:10]:
                            name = metric.get("metric_name") or metric.get("name", "Unknown")
                            desc = metric.get("description", "")
                            additional_metrics_text += f"- {name}: {desc[:200]}\n"
                    
                    controls_text = ""
                    if controls:
                        controls_text = "**Compliance Controls:**\n"
                        for control in controls[:10]:
                            if isinstance(control, dict):
                                control_obj = control.get("control") or control
                                control_id = control_obj.get("control_id", "Unknown")
                                control_name = control_obj.get("control_name", "")
                                controls_text += f"- {control_id}: {control_name}\n"
                    
                    features_text = ""
                    if features:
                        features_text = "**Features:**\n"
                        for feature in features[:10]:
                            feature_name = feature.get("display_name") or feature.get("feature_name", "Unknown")
                            feature_desc = feature.get("description", "")
                            features_text += f"- {feature_name}: {feature_desc[:200]}\n"
                    
                    summary_inputs = {
                        "content_type": content_type,
                        "query": query,
                        "actor_type": actor_type,
                        "mdl_answer": mdl_answer or "No MDL answer",
                        "key_tables_text": key_tables_text or "No key tables",
                        "mdl_relationships": mdl_relationships or "No relationships",
                        "mdl_contexts": mdl_contexts or "No contexts",
                        "metrics_text": metrics_text or "No metrics",
                        "additional_metrics_text": additional_metrics_text or "",
                        "controls_text": controls_text or "",
                        "features_text": features_text or "",
                        "mdl_insights": mdl_insights or "No insights",
                        "context_info": context_info or "No specific context",
                        "qa_answer": qa_answer or "No Q&A answer available",
                        "executor_output": executor_output or "No executor output available",
                        "deep_research_note": deep_research_note
                    }
                    logger.info(f"WriterAgentNode: Using MDL summary with full schemas - key_tables={len(mdl_key_tables)}, schemas={len(schemas)}, metrics={len(mdl_metrics) if isinstance(mdl_metrics, list) else 0}")
                else:
                    summary_inputs = {
                        "content_type": content_type,
                        "query": query,
                        "context_info": context_info or "No specific context",
                        "reasoning_result": str(reasoning_result) if reasoning_result else "No reasoning results",
                        "qa_answer": qa_answer or "No Q&A answer available",
                        "executor_output": executor_output or "No executor output available"
                    }
                    logger.info(f"WriterAgentNode: No MDL summary - using fallback")
                
                logger.info(f"WriterAgentNode: Summary prompt inputs: {str(summary_inputs)[:1000]}...")
                
                chain = summary_prompt | self.llm
                response = await chain.ainvoke(summary_inputs)
                
                content = response.content if hasattr(response, "content") else str(response)
                logger.info(f"WriterAgentNode: Summary LLM returned content length={len(content) if content else 0}")
                logger.info(f"WriterAgentNode: Summary content preview={content[:500] if content else 'None'}...")
                
                state["written_content"] = content
                state["content_type"] = content_type
                
            else:
                # Return result directly (format it nicely)
                if has_executor:
                    # Use executor output, format it nicely
                    format_prompt = ChatPromptTemplate.from_messages([
                        ("system", f"""You are formatting executor results for the user.

{actor_context}

Format the executor output in a clear, {actor_config['communication_style']} style.
Provide {actor_config['preferred_detail_level']} level of detail.
Focus on: {', '.join(actor_config['focus_areas'])}"""),
                        ("human", """Format this executor output for the user:

Query: {query}
Executor Output: {executor_output}
Executor Result: {executor_result}

Format it clearly and professionally.
""")
                    ])
                    
                    logger.info("WriterAgentNode: Starting format executor output LLM call")
                    logger.info(f"WriterAgentNode: Executor output length={len(executor_output) if executor_output else 0}")
                    
                    # Log the format prompt inputs
                    format_inputs = {
                        "query": query,
                        "executor_output": executor_output,
                        "executor_result": str(executor_result)
                    }
                    logger.info(f"WriterAgentNode: Format prompt inputs: {str(format_inputs)[:1000]}...")
                    
                    chain = format_prompt | self.llm
                    response = await chain.ainvoke(format_inputs)
                    content = response.content if hasattr(response, "content") else executor_output
                    logger.info(f"WriterAgentNode: Format LLM returned content length={len(content) if content else 0}")
                    logger.info(f"WriterAgentNode: Formatted content preview={content[:500] if content else 'None'}...")
                    
                elif has_qa:
                    # Use Q&A answer, format it nicely
                    logger.info(f"WriterAgentNode: Using Q&A answer directly, length={len(qa_answer) if qa_answer else 0}")
                    content = qa_answer  # Q&A is already formatted
                else:
                    # Fallback
                    logger.warning("WriterAgentNode: No results available, using fallback")
                    content = "No results available"
                
                state["written_content"] = content
                state["content_type"] = "formatted_result"
                logger.info(f"WriterAgentNode: Final written_content length={len(state.get('written_content', ''))}")
                logger.info(f"WriterAgentNode: Final written_content preview={state.get('written_content', '')[:500]}...")
            
            state["content_metadata"] = {
                "actor_type": actor_type,
                "context_count": len(context_metadata),
                "has_reasoning": bool(reasoning_result),
                "has_qa": has_qa,
                "has_executor": has_executor,
                "decision": decision,
                "decision_reasoning": decision_result.get("reasoning", "")
            }
            
            # Add to messages
            messages = list(state.get("messages", []))
            messages.append(AIMessage(content=state["written_content"]))
            state["messages"] = messages
            
            state["next_node"] = "finalize"
            state["current_node"] = "writer_agent"
            logger.info(f"WriterAgentNode: Writer decision: {decision}, content_type: {state['content_type']}")
            logger.info(f"WriterAgentNode: Final state keys: {list(state.keys())}")
            logger.info(f"WriterAgentNode: written_content in state: {'written_content' in state}")
            logger.info(f"WriterAgentNode: written_content value: {state.get('written_content', 'NOT SET')[:200] if state.get('written_content') else 'EMPTY'}")
            
        except Exception as e:
            logger.error(f"Error in writer agent: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            # Fallback: use whatever we have
            if executor_output:
                state["written_content"] = executor_output
            elif qa_answer:
                state["written_content"] = qa_answer
            else:
                state["written_content"] = f"Error generating content: {str(e)}"
            state["next_node"] = "finalize"
        
        return state


class GraphRouterNode:
    """Node that routes to other graphs if needed"""
    
    def __init__(
        self,
        graph_registry: Any,
        llm: Optional[ChatOpenAI] = None,
        model_name: str = "gpt-4o-mini"
    ):
        self.graph_registry = graph_registry
        self.llm = llm or ChatOpenAI(model=model_name, temperature=0.2)
        self.json_parser = JsonOutputParser()
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Route to another graph if needed"""
        query = state.get("query", "")
        intent_details = state.get("intent_details", {})
        
        try:
            # Check if graph routing is needed
            if not intent_details.get("needs_graph", False):
                state["next_node"] = "retrieve_context"
                return state
            
            # Determine which graph to use (this could be enhanced with LLM selection)
            # For now, we'll use a simple heuristic or allow it to be specified
            selected_graph_id = state.get("selected_graph_id")
            
            if not selected_graph_id:
                # Could use LLM to select graph, but for now skip routing
                logger.info("Graph routing requested but no graph_id specified")
                state["next_node"] = "retrieve_context"
                return state
            
            # Prepare graph input
            graph_input = {
                "query": query,
                "context": state.get("user_context", {}),
                "reasoning_result": state.get("reasoning_result")
            }
            
            state["graph_input"] = graph_input
            state["selected_graph_id"] = selected_graph_id
            state["next_node"] = "invoke_graph"
            state["current_node"] = "graph_router"
            
            logger.info(f"Routing to graph: {selected_graph_id}")
            
        except Exception as e:
            logger.error(f"Error in graph router: {str(e)}", exc_info=True)
            state["status"] = "error"
            state["error"] = str(e)
            state["next_node"] = "retrieve_context"  # Fallback
        
        return state


class FinalizeNode:
    """Node that finalizes the response"""
    
    async def __call__(self, state: ContextualAssistantState) -> ContextualAssistantState:
        """Finalize the response"""
        logger.info("FinalizeNode: Starting finalization")
        logger.info(f"FinalizeNode: State keys: {list(state.keys())}")
        
        written_content = state.get("written_content")
        qa_answer = state.get("qa_answer")
        executor_output = state.get("executor_output")
        writer_decision = state.get("writer_decision")
        
        logger.info(f"FinalizeNode: written_content present={bool(written_content)}, length={len(written_content) if written_content else 0}")
        logger.info(f"FinalizeNode: qa_answer present={bool(qa_answer)}, length={len(qa_answer) if qa_answer else 0}")
        logger.info(f"FinalizeNode: executor_output present={bool(executor_output)}, length={len(executor_output) if executor_output else 0}")
        logger.info(f"FinalizeNode: writer_decision={writer_decision}")
        
        # Writer node should have created written_content, but fallback to others
        if written_content:
            logger.info(f"FinalizeNode: Using written_content, preview: {written_content[:200]}...")
            state["final_answer"] = written_content
            state["final_output"] = {
                "type": "written_content",
                "content": written_content,
                "content_type": state.get("content_type"),
                "writer_decision": writer_decision,
                "metadata": state.get("content_metadata")
            }
        elif executor_output:
            logger.info(f"FinalizeNode: Using executor_output, preview: {executor_output[:200]}...")
            state["final_answer"] = executor_output
            state["final_output"] = {
                "type": "executor_result",
                "output": executor_output,
                "result": state.get("executor_result", {}),
                "actions": state.get("executor_actions", [])
            }
        elif qa_answer:
            logger.info(f"FinalizeNode: Using qa_answer, preview: {qa_answer[:200]}...")
            state["final_answer"] = qa_answer
            state["final_output"] = {
                "type": "qa_answer",
                "answer": qa_answer,
                "sources": state.get("qa_sources", []),
                "confidence": state.get("qa_confidence", 0.5)
            }
        else:
            logger.error("FinalizeNode: No content available! State dump:")
            logger.error(f"FinalizeNode: State keys: {list(state.keys())}")
            logger.error(f"FinalizeNode: State values (first 500 chars each):")
            for key in ['written_content', 'qa_answer', 'executor_output', 'error', 'status']:
                if key in state:
                    val = str(state[key])
                    logger.error(f"FinalizeNode:   {key}={val[:500]}...")
            
            state["final_answer"] = "Unable to generate response"
            state["final_output"] = {
                "type": "error",
                "error": state.get("error", "Unknown error")
            }
        
        state["status"] = "completed"
        state["current_node"] = "finalize"
        state["next_node"] = None
        
        logger.info(f"FinalizeNode: Response finalized. final_answer length={len(state.get('final_answer', ''))}")
        logger.info(f"FinalizeNode: final_answer preview: {state.get('final_answer', '')[:500]}...")
        logger.info(f"FinalizeNode: final_output type: {state.get('final_output', {}).get('type', 'unknown')}")
        
        return state


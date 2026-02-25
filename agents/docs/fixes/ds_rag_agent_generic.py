"""DS RAG Agent - SQL generation restricted to appendix functions.

Flow for SQL Function analysis (per ds_rag_fixes):
  Step 1: DS_PIPELINE_PLANNER — structured plan (data fetch, transformation, operations)
  Step 2: DS_NL_QUESTION_GENERATOR — precise NL questions per step
  (Steps 3–4: NL-to-SQL × 3 and _propagate_step_context removed for debugging)
  → Single-shot GENERATION with 3-step CTE pattern + appendix contracts

Internal flow:
1. TASK_DECOMPOSITION: Break task into (data fetch, transformation, operations)
2. DS_PIPELINE_PLANNER: Build structured plan from decomposition + schema
3. DS_NL_QUESTION_GENERATOR: Generate NL question per step
4. REASONING: Plan using decomposition + pipeline plan + appendix
5. GENERATION: Generate SQL using DS_GENERATION_SYSTEM_PROMPT (3-CTE pattern)

Uses retrieval_helper for tables/schemas by project_id.
"""
import json
import logging
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.prompts import PromptTemplate

from app.agents.nodes.sql.sql_rag_agent import SQLRAGAgent, SQLOperationType
from app.agents.nodes.ds.appendix_loader import (
    load_appendix_functions,
    format_appendix_for_prompt,
)
from app.agents.nodes.ds.ds_sql_generator import (
    build_ddl_for_step_output,
    generate_sql_for_ds_step,
    get_schema_for_step,
    propagate_step_context,
)
from app.agents.nodes.ds.ds_prompts import (
    APPENDIX_RESTRICTION,
    REASONING_APPENDIX_TAIL,
    BREAKDOWN_APPENDIX_TAIL,
    GENERATION_APPENDIX_TAIL,
    EXPANSION_SYSTEM_PROMPT_TEMPLATE,
    EXPANSION_USER_PROMPT_TEMPLATE,
    GENERATION_APPENDIX_PREFIX,
    DS_GENERATION_SYSTEM_PROMPT,
    TASK_DECOMPOSITION_SYSTEM_PROMPT,
    TASK_DECOMPOSITION_USER_TEMPLATE,
    TASK_DECOMPOSITION_METADATA_HEADER,
    SAMPLE_DATA_CONTEXT_HEADER,
    get_ds_pipeline_planner_prompt,
    get_ds_nl_question_generator_prompt,
    get_ds_transformation_ambiguity_detector_prompt,
    get_ds_transformation_resolution_builder_prompt,
    get_ds_function_map_generator_prompt,
)

logger = logging.getLogger("lexy-ai-service")


class DSOperationType(Enum):
    """Operation types for DS RAG flow - mirrors SQL RAG + task decomposition."""
    TASK_DECOMPOSITION = "task_decomposition"
    GENERATION = "generation"
    BREAKDOWN = "breakdown"
    EXPANSION = "expansion"
    CORRECTION = "correction"
    REGENERATION = "regeneration"
    REFRESH = "refresh"
    REASONING = "reasoning"
    ANSWER = "answer"
    QUESTION = "question"
    SUMMARY = "summary"
    GENERATE_TRANSFORM = "generate_transform"


class DSRAgent(SQLRAGAgent):
    """DataScience RAG agent - restricts SQL to appendix functions only.

    Flow for SQL Function analysis:
    - TASK_DECOMPOSITION: Break task into data fetch, transformation, operations
    - REASONING: Planner uses decomposition + appendix functions
    - BREAKDOWN: Breaks down the plan into steps
    - EXPANSION: Further filters/refines queries
    - GENERATION: Generates SQL using only appendix functions
    """

    def __init__(self, *args, appendix_path: Optional[Path] = None, **kwargs):
        kwargs = dict(kwargs)
        kwargs.pop("appendix_path", None)
        path = Path(appendix_path) if appendix_path is not None else None
        self._appendix_functions = load_appendix_functions(path=path)
        self._appendix_prompt = format_appendix_for_prompt(self._appendix_functions)
        self._appendix_names = {f.get("function") for f in self._appendix_functions}
        super().__init__(*args, **kwargs)
        logger.info(f"DSRAgent initialized with {len(self._appendix_functions)} appendix functions")

    def _initialize_system_prompts(self) -> Dict[str, str]:
        """Override prompts to inject appendix restriction for REASONING, BREAKDOWN, GENERATION, EXPANSION."""
        base = super()._initialize_system_prompts()
        appendix_block = self._appendix_prompt + APPENDIX_RESTRICTION

        # REASONING: Planner must select functions from appendix
        base[SQLOperationType.REASONING.value] = (
            base[SQLOperationType.REASONING.value]
            + "\n\n"
            + appendix_block
            + REASONING_APPENDIX_TAIL
        )

        # BREAKDOWN: Steps must use only appendix functions
        base[SQLOperationType.BREAKDOWN.value] = (
            base[SQLOperationType.BREAKDOWN.value]
            + "\n\n"
            + appendix_block
            + BREAKDOWN_APPENDIX_TAIL
        )

        # GENERATION: SQL must use only appendix functions
        base[SQLOperationType.GENERATION.value] = (
            base[SQLOperationType.GENERATION.value]
            + "\n\n"
            + appendix_block
            + GENERATION_APPENDIX_TAIL
        )

        return base

    def _format_metadata_for_reasoning(self, metadata: Dict[str, Any]) -> str:
        """Prepend task decomposition, pipeline plan, NL questions, sample data, and appendix to metadata for reasoning."""
        base = super()._format_metadata_for_reasoning(metadata)
        parts = [self._appendix_prompt]
        if getattr(self, "_last_task_decomposition", None):
            parts.insert(0, TASK_DECOMPOSITION_METADATA_HEADER + self._last_task_decomposition + "\n\n")
        planning = getattr(self, "_ds_cached_pipeline_planning", None)
        if planning:
            plan = planning.get("pipeline_plan", {})
            nl_questions = planning.get("nl_questions", [])
            if plan or nl_questions:
                plan_block = "### DS PIPELINE PLAN (from DS_PIPELINE_PLANNER) ###\n"
                if plan:
                    plan_block += json.dumps(plan, indent=2) + "\n\n"
                if nl_questions:
                    plan_block += "### NL QUESTIONS (from DS_NL_QUESTION_GENERATOR) ###\n"
                    for nq in nl_questions:
                        plan_block += f"- {nq.get('step', '')}: {nq.get('nl_question', '')}\n"
                parts.insert(len(parts) - 1, plan_block)
        sample_data = getattr(self, "_sample_data_for_reasoning", None)
        if sample_data:
            parts.append(SAMPLE_DATA_CONTEXT_HEADER + sample_data)
        return "\n\n".join(parts) + "\n\n" + base

    async def _fetch_schemas_for_project(
        self,
        query: str,
        project_id: str,
        table_retrieval: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch tables and schema contexts for project_id via retrieval_helper."""
        if not self.retrieval_helper:
            logger.warning("DS agent: no retrieval_helper, cannot fetch schemas")
            return {"table_names": [], "schema_contexts": [], "relationships": []}
        config = table_retrieval or {
            "table_retrieval_size": 5,
            "table_column_retrieval_size": 100,
            "allow_using_db_schemas_without_pruning": False,
        }
        return await self.retrieval_helper.get_table_names_and_schema_contexts(
            query=query,
            project_id=project_id,
            table_retrieval=config,
        )

    async def _fetch_sample_data_for_planning(
        self,
        query: str,
        project_id: str,
        table_names: List[str],
        schema_contexts: List[str],
        max_tables: int = 3,
        sample_limit: int = 10,
    ) -> str:
        """Fetch sample data via SQL pipeline (generate + execute) for planning.
        Returns formatted string of sample rows per table.
        """
        if not table_names or not schema_contexts:
            return ""
        try:
            from app.agents.pipelines.pipeline_container import PipelineContainer
            container = PipelineContainer.get_instance()
            sql_gen = container.get_pipeline("sql_generation")
            sql_exec = container.get_pipeline("sql_execution")
        except Exception as e:
            logger.warning(f"DS agent: could not get SQL pipelines for sample data: {e}")
            return ""
        samples = []
        for table_name in table_names[:max_tables]:
            try:
                sample_query = f"Show me {sample_limit} sample rows from table {table_name}"
                gen_result = await sql_gen.run(
                    query=sample_query,
                    project_id=project_id,
                    schema_context=schema_contexts,
                    language="English",
                )
                sql = None
                if gen_result.get("success"):
                    data = gen_result.get("data") or {}
                    if isinstance(data, dict):
                        sql = data.get("sql", "")
                    elif isinstance(data, list) and data:
                        first = data[0] if isinstance(data[0], dict) else {}
                        sql = first.get("sql", "") if isinstance(first, dict) else ""
                if not sql:
                    continue
                exec_result = await sql_exec.run(sql=sql, project_id=project_id, configuration={"dry_run": False})
                post = exec_result.get("post_process", {}) or {}
                rows = post.get("data", []) or post.get("rows", [])
                if rows:
                    samples.append(f"**Table {table_name}** (sample):\n{str(rows[:5])}")
            except Exception as e:
                logger.debug(f"DS agent: sample fetch failed for {table_name}: {e}")
        return "\n\n".join(samples) if samples else ""

    async def _decompose_task_internal(self, query: str, language: str = "English") -> str:
        """Break user task into: data fetch question, transformation layer, operations on data."""
        try:
            user_prompt = TASK_DECOMPOSITION_USER_TEMPLATE.format(query=query, language=language)
            appendix_block = self._appendix_prompt if self._appendix_functions else ""
            system_with_appendix = TASK_DECOMPOSITION_SYSTEM_PROMPT
            if appendix_block:
                system_with_appendix += "\n\n### AVAILABLE SQL FUNCTIONS (for Operations on Data) ###\n" + appendix_block
            full_prompt = system_with_appendix + "\n\n" + user_prompt
            result = await self.llm.ainvoke(full_prompt)
            content = result.content if hasattr(result, "content") else str(result)
            return content.strip()
        except Exception as e:
            logger.error(f"Error in task decomposition: {e}")
            return ""

    async def _reason_sql_internal(self, query: str, contexts: List[str], language: str, relationships: List[Dict] = None, **kwargs) -> Dict[str, Any]:
        """Override: use retrieval_helper for schemas when project_id provided; fetch sample data via SQL pipeline; decompose task; then reason."""
        project_id = kwargs.get("project_id")
        schema_contexts = list(contexts) if contexts else []
        schema_relationships = list(relationships) if relationships else []
        table_names = list(getattr(self, "_ds_cached_table_names", None) or kwargs.get("cached_table_names") or [])

        if project_id and self.retrieval_helper and not table_names:
            schema_data = await self._fetch_schemas_for_project(query, project_id)
            table_names = schema_data.get("table_names", [])
            if not schema_contexts:
                schema_contexts = schema_data.get("schema_contexts", [])
            if not schema_relationships:
                schema_relationships = schema_data.get("relationships", [])

        self._sample_data_for_reasoning = ""
        if project_id and table_names and schema_contexts:
            self._sample_data_for_reasoning = await self._fetch_sample_data_for_planning(
                query=query,
                project_id=project_id,
                table_names=table_names,
                schema_contexts=schema_contexts,
            )

        # Use decomposition from planning phase if already run (avoids duplicate LLM call)
        planning = getattr(self, "_ds_cached_pipeline_planning", None)
        if planning and planning.get("decomposition"):
            decomposition = planning["decomposition"]
        else:
            decomposition = await self._decompose_task_internal(query, language)

        # Capture on the generation-scoped slot (set by _handle_sql_generation)
        if hasattr(self, "_captured_task_decomposition"):
            self._captured_task_decomposition = decomposition

        self._last_task_decomposition = decomposition
        try:
            kwargs_for_super = {k: v for k, v in kwargs.items() if k != "language"}
            result = await super()._reason_sql_internal(
                query, schema_contexts, language, schema_relationships, **kwargs_for_super
            )
            if isinstance(result, dict):
                result["task_decomposition"] = decomposition
            return result
        finally:
            if hasattr(self, "_last_task_decomposition"):
                del self._last_task_decomposition
            if hasattr(self, "_sample_data_for_reasoning"):
                del self._sample_data_for_reasoning

    def _get_expansion_system_prompt(self) -> str:
        """Build expansion system prompt with appendix restriction."""
        appendix_block = self._appendix_prompt + APPENDIX_RESTRICTION
        return EXPANSION_SYSTEM_PROMPT_TEMPLATE.format(appendix_block=appendix_block)

    async def _expand_sql_internal(
        self,
        query: str,
        original_sql: str,
        contexts: Any,
        original_reasoning: str = "",
        original_query: str = "",
    ) -> Dict[str, Any]:
        """Override expansion to use appendix-restricted prompt."""
        try:
            prompt_template = PromptTemplate(
                input_variables=["query", "original_sql", "contexts", "original_reasoning", "original_query"],
                template=EXPANSION_USER_PROMPT_TEMPLATE,
            )
            system_prompt = self._get_expansion_system_prompt()
            full_prompt = PromptTemplate(
                input_variables=["system_prompt", "user_prompt"],
                template="{system_prompt}\n\n{user_prompt}",
            )
            ctx_str = "\n".join(contexts) if isinstance(contexts, (list, tuple)) else str(contexts)
            user_prompt = prompt_template.format(
                query=query,
                original_sql=original_sql,
                contexts=ctx_str,
                original_reasoning=original_reasoning,
                original_query=original_query,
            )
            prompt = full_prompt.format(system_prompt=system_prompt, user_prompt=user_prompt)
            result = await self.llm.ainvoke(prompt)
            result_content = result.content if hasattr(result, "content") else str(result)
            extracted = self._extract_sql_from_content(result_content)
            expanded_sql = (extracted.get("sql", "") or "").strip()
            if not expanded_sql:
                expanded_sql = result_content.strip()
            return {"sql": expanded_sql, "success": bool(expanded_sql)}
        except Exception as e:
            logger.error(f"Error in DS SQL expansion: {e}")
            return {"sql": "", "success": False, "error": str(e)}

    async def _handle_sql_generation(self, query: str, **kwargs) -> Dict[str, Any]:
        """Override: fetch schemas, run generation, bubble up task_decomposition."""
        project_id = kwargs.get("project_id")
        if not project_id:
            raise ValueError("project_id is required for DS agent")
        if not self.retrieval_helper:
            raise ValueError("retrieval_helper is required for DS agent")

        schema_data = await self._fetch_schemas_for_project(query, project_id)
        schema_contexts = schema_data.get("schema_contexts", [])
        relationships = schema_data.get("relationships", [])
        table_names = schema_data.get("table_names", [])

        if not schema_contexts:
            return {"error": "No schema information found for project", "success": False}

        kwargs["unified_context"] = {
            "schema_contexts": schema_contexts,
            "relationships": relationships,
            "reasoning": "",
        }
        self._ds_cached_table_names = table_names
        self._captured_task_decomposition = ""

        # Run DS_PIPELINE_PLANNER + DS_NL_QUESTION_GENERATOR (Steps 1–2 per ds_rag_fixes)
        planning_result = await self._run_ds_pipeline_planning_phase(
            query=query,
            table_names=table_names,
            schema_contexts=schema_contexts,
            language=kwargs.get("language", "English"),
        )
        self._ds_cached_pipeline_planning = planning_result

        # Run per-step SQL generation (uses DDL from previous step for steps 2+)
        # Does NOT call sql_rag_agent — uses ds_sql_generator
        use_stepwise_sql = kwargs.pop("use_stepwise_sql", False)
        stepwise_result = {}
        if planning_result.get("pipeline_plan", {}).get("steps") and planning_result.get("nl_questions"):
            stepwise_result = await self._run_stepwise_sql_generation(
                planning_result=planning_result,
                schema_contexts=schema_contexts,
                nl_questions=planning_result.get("nl_questions", []),
                query=query,
            )

        try:
            if use_stepwise_sql and stepwise_result.get("success") and stepwise_result.get("combined_sql"):
                # Use stepwise SQL as final output — do NOT call sql_rag_agent
                result = {
                    "success": True,
                    "data": {
                        "sql": stepwise_result["combined_sql"],
                        "reasoning": "",
                        "parsed_entities": {},
                    },
                    "error": None,
                }
            else:
                result = await super()._handle_sql_generation(query, **kwargs)

            # Bubble task_decomposition up to top-level result
            if isinstance(result, dict) and self._captured_task_decomposition:
                result["task_decomposition"] = self._captured_task_decomposition

            # Bubble pipeline_plan, nl_questions, and stepwise SQL
            if isinstance(result, dict) and planning_result:
                result["pipeline_plan"] = planning_result.get("pipeline_plan", {})
                result["nl_questions"] = planning_result.get("nl_questions", [])
            if isinstance(result, dict) and stepwise_result:
                result["step_sqls"] = stepwise_result.get("step_sqls", {})
                result["step_ddls"] = stepwise_result.get("step_ddls", {})
                result["step_errors"] = stepwise_result.get("step_errors", {})
                result["combined_sql"] = stepwise_result.get("combined_sql", "")

            return result
        finally:
            if hasattr(self, "_ds_cached_table_names"):
                del self._ds_cached_table_names
            if hasattr(self, "_captured_task_decomposition"):
                del self._captured_task_decomposition
            if hasattr(self, "_ds_cached_pipeline_planning"):
                del self._ds_cached_pipeline_planning

    def _build_confirmed_models_from_schema(
        self,
        table_names: List[str],
        schema_contexts: List[str],
    ) -> List[Dict[str, Any]]:
        """Build confirmed_models structure from table names and schema DDL for pipeline planner."""
        sql_types = (
            r"VARCHAR|TEXT|INTEGER|BIGINT|DECIMAL|NUMERIC|FLOAT|REAL|"
            r"DATE|TIMESTAMP|BOOLEAN|JSONB|JSON|CHAR|SMALLINT"
        )
        skip = {"PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT", "KEY", "REFERENCES"}
        models = []
        for i, table_name in enumerate(table_names):
            columns = []
            if i < len(schema_contexts):
                ddl = schema_contexts[i] or ""
                for match in re.finditer(
                    rf"(?:^|[,\(])\s*[\"']?(\w+)[\"']?\s+(?:{sql_types})",
                    ddl,
                    re.IGNORECASE,
                ):
                    col = match.group(1)
                    if col.upper() not in skip:
                        columns.append({"name": col, "type": "VARCHAR"})
            if not columns:
                columns = [{"name": "id", "type": "VARCHAR"}]
            models.append({
                "model_id": table_name,
                "display_name": table_name.replace("_", " ").title(),
                "columns": columns,
                "grain": [c["name"] for c in columns[:2]] if len(columns) >= 2 else [columns[0]["name"]],
            })
        return models

    async def _generate_function_map(
        self,
        query: str,
        decomposition: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate the function map from the user question using DS_FUNCTION_MAP_GENERATOR prompt.
        Replaces keyword matching — the LLM reads the question + appendix and selects
        which functions are needed and in what order.

        Returns [] if no appendix function is needed (pure aggregation questions).
        """
        try:
            prompt_text = get_ds_function_map_generator_prompt()
        except Exception:
            logger.warning("DS_FUNCTION_MAP_GENERATOR prompt not found, returning empty map")
            return []

        prompt = (
            f"{prompt_text}"
            f"\n\n### AVAILABLE SQL FUNCTIONS ###\n{self._appendix_prompt}"
            f"\n\n### USER QUESTION ###\n{query}"
            f"\n\n### TASK DECOMPOSITION ###\n{decomposition}"
        )
        try:
            from langchain_core.messages import HumanMessage
            result = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = result.content if hasattr(result, "content") else str(result)
            clean = re.sub(r"```(?:json)?\s*|\s*```", "", content).strip()
            fn_map = json.loads(clean)
            return fn_map if isinstance(fn_map, list) else []
        except Exception as e:
            logger.warning(f"Function map generation failed: {e}")
            return []

    async def _run_ds_pipeline_planning_phase(
        self,
        query: str,
        table_names: List[str],
        schema_contexts: List[str],
        language: str = "English",
    ) -> Dict[str, Any]:
        """
        Run DS_PIPELINE_PLANNER + DS_NL_QUESTION_GENERATOR (Steps 1–2 per ds_rag_fixes).
        Returns {pipeline_plan, nl_questions, decomposition}.
        """
        result = {"pipeline_plan": {}, "nl_questions": [], "decomposition": ""}
        if not table_names or not schema_contexts:
            result["decomposition"] = await self._decompose_task_internal(query, language)
            return result
        try:
            decomposition = await self._decompose_task_internal(query, language)
            result["decomposition"] = decomposition

            confirmed_models = self._build_confirmed_models_from_schema(table_names, schema_contexts)
            # LLM-driven function selection — no keyword matching in Python
            function_map = await self._generate_function_map(query, decomposition)
            # Planner derives all parameters from question + schema — no hardcoded grain/time
            resolved_parameters: Dict[str, Any] = {}

            plan = await self._build_pipeline_plan(
                query=query,
                confirmed_models=confirmed_models,
                resolved_parameters=resolved_parameters,
                function_map=function_map,
            )
            result["pipeline_plan"] = plan or {}

            steps = plan.get("steps", {}) if plan else {}
            step_keys = sorted(
                [k for k in steps if isinstance(k, str) and k.startswith("step_")],
                key=lambda k: int(k[5:]) if k[5:].isdigit() else 999,
            )
            available_schema = {
                "tables": table_names,
                "columns": [
                    c["name"]
                    for m in confirmed_models
                    for c in m.get("columns", [])
                ],
            }
            for step_key in step_keys:
                nl_result = await self._generate_nl_question(
                    step_definition=steps[step_key],
                    available_schema=available_schema,
                )
                result["nl_questions"].append({
                    "step": step_key,
                    "nl_question": nl_result.get("nl_question", ""),
                })
        except Exception as e:
            logger.warning(f"DS pipeline planning phase failed: {e}")
        return result

    def _extract_sql_from_response(self, content: str) -> str:
        """Extract SQL from LLM response (handles <sql></sql> and ```sql blocks)."""
        if not content:
            return ""
        content = content.strip()
        sql_match = re.search(r"<sql>\s*([\s\S]*?)</sql>", content, re.IGNORECASE)
        if sql_match:
            return sql_match.group(1).strip()
        code_match = re.search(r"```(?:sql)?\s*([\s\S]*?)```", content)
        if code_match:
            return code_match.group(1).strip()
        return content

    async def _run_stepwise_sql_generation(
        self,
        planning_result: Dict[str, Any],
        schema_contexts: List[str],
        nl_questions: List[Dict[str, Any]],
        query: str,
    ) -> Dict[str, Any]:
        """
        Generate SQL per pipeline step.
        DDL for each step is resolved from plan.input_source — NOT from the previous step index.
        This correctly handles parallel branches (e.g., step_3 and step_4 both reading step_2).
        """
        result = {"step_sqls": {}, "step_ddls": {}, "step_errors": {}, "combined_sql": "", "success": False}
        plan = planning_result.get("pipeline_plan", {})
        steps = plan.get("steps", {}) or {}
        if not steps or not nl_questions:
            return result

        appendix_block = self._appendix_prompt + APPENDIX_RESTRICTION
        step_keys = sorted(
            [k for k in steps if isinstance(k, str) and k.startswith("step_")],
            key=lambda k: int(k[5:]) if k[5:].isdigit() else 999,
        )
        nl_by_step = {nq["step"]: nq.get("nl_question", "") for nq in nl_questions}
        real_schema_ddl = "\n\n".join(schema_contexts) if schema_contexts else ""

        for i, step_key in enumerate(step_keys):
            step_plan = steps.get(step_key, {})
            nl_question = nl_by_step.get(step_key, "")

            # Resolve schema from plan.input_source — handles parallel branches transparently.
            # step_3 and step_4 both get step_2_output DDL if both have input_source="step_2".
            current_schema_ddl = get_schema_for_step(
                step_key=step_key,
                step_plan=step_plan,
                all_steps=steps,
                real_schema_ddl=real_schema_ddl,
            )

            result["step_ddls"][step_key] = current_schema_ddl
            result[f"{step_key}_ddl"] = current_schema_ddl

            # Resolve previous SQL from the actual input_source step (not positionally i-1).
            input_source = step_plan.get("input_source", "")
            previous_sql = result["step_sqls"].get(input_source) if input_source in result["step_sqls"] else None

            gen_result = await generate_sql_for_ds_step(
                llm=self.llm,
                nl_question=nl_question,
                schema_ddl=current_schema_ddl,
                appendix_block=appendix_block,
                step_number=i + 1,
                previous_step_sql=previous_sql,
                step_plan=step_plan,
                extract_sql_fn=self._extract_sql_from_response,
            )
            step_sql = gen_result.get("sql", "")
            step_err = gen_result.get("error")
            result["step_sqls"][step_key] = step_sql
            result[f"{step_key}_sql"] = step_sql
            if step_err:
                result["step_errors"][step_key] = step_err
                result[f"{step_key}_error"] = step_err

            if not step_sql:
                logger.warning(f"Step {step_key} SQL generation returned empty — continuing (parallel branches may succeed)")

        if result["step_sqls"]:
            result["success"] = True
            result["combined_sql"] = self._assemble_pipeline_sql(plan, result["step_sqls"])

        return result

    def _assemble_pipeline_sql(
        self,
        plan: Dict[str, Any],
        step_sqls: Dict[str, str],
    ) -> str:
        """
        Assemble step SQLs into a single CTE pipeline, driven by plan.final_select.
        No conditions on plan_type or step count — all topology is in the plan.

        plan.final_select.type controls the final SELECT:
          "simple"  → SELECT * FROM {from_step}_output
          "join"    → JOIN across parallel branch CTEs on shared keys
        """
        step_keys = sorted(
            step_sqls.keys(),
            key=lambda k: int(k[5:]) if k[5:].isdigit() else 999,
        )
        ctes = []
        for step_key in step_keys:
            sql = step_sqls[step_key].strip().rstrip(";")
            if sql:
                ctes.append(f"{step_key}_output AS (\n{sql}\n)")

        if not ctes:
            return ""

        cte_block = "WITH\n" + ",\n".join(ctes)
        final_spec = plan.get("final_select", {})
        select_type = final_spec.get("type", "simple")

        if select_type == "join" and final_spec.get("join_steps"):
            final_select = self._build_join_final_select(final_spec)
        else:
            final_select = self._build_simple_final_select(final_spec, step_sqls)

        return f"{cte_block}\n{final_select}".strip()

    def _build_simple_final_select(
        self,
        spec: Dict[str, Any],
        step_sqls: Dict[str, str],
    ) -> str:
        """
        Build: SELECT * FROM {from_step}_output [WHERE ...] [ORDER BY ...]
        Falls back to the highest-numbered step if from_step is not in spec.
        """
        from_step = spec.get("from_step")
        if not from_step:
            keys = sorted(step_sqls.keys(), key=lambda k: int(k[5:]) if k[5:].isdigit() else 0)
            from_step = keys[-1] if keys else "step_1"

        sql = f"SELECT * FROM {from_step}_output"
        if spec.get("post_filter"):
            sql += f"\nWHERE {spec['post_filter']}"
        if spec.get("order_by"):
            sql += f"\nORDER BY {', '.join(spec['order_by'])}"
        return sql

    def _build_join_final_select(self, spec: Dict[str, Any]) -> str:
        """
        Build a JOIN final select for parallel-branch pipelines.
        primary_step JOIN join_steps[N] ON shared keys, then optional WHERE + ORDER BY.

        Alias convention: primary step = "p", join_steps = "j0", "j1", ...
        """
        primary = spec.get("primary_step", "")
        primary_cols = spec.get("primary_columns", [])
        join_steps = spec.get("join_steps", [])

        select_cols = [f"p.{col}" for col in primary_cols] if primary_cols else ["p.*"]
        for j, jspec in enumerate(join_steps):
            alias = f"j{j}"
            for col in jspec.get("select_columns", []):
                select_cols.append(f"{alias}.{col}")

        select_clause = ",\n    ".join(select_cols)
        from_clause = f"FROM {primary}_output p"
        join_clauses = []
        for j, jspec in enumerate(join_steps):
            alias = f"j{j}"
            step = jspec.get("step", "")
            join_type = jspec.get("join_type", "JOIN")
            on_cols = jspec.get("on", [])
            on_expr = " AND ".join(f"p.{col} = {alias}.{col}" for col in on_cols)
            join_clauses.append(f"{join_type} {step}_output {alias} ON {on_expr}")

        sql = f"SELECT\n    {select_clause}\n{from_clause}"
        if join_clauses:
            sql += "\n" + "\n".join(join_clauses)
        if spec.get("post_filter"):
            sql += f"\nWHERE {spec['post_filter']}"
        if spec.get("order_by"):
            sql += f"\nORDER BY {', '.join(spec['order_by'])}"
        return sql

    def _extract_json(self, content: str) -> str:
        """Extract JSON from LLM response (handles markdown code blocks)."""
        content = content.strip()
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
        if json_match:
            return json_match.group(1).strip()
        brace = content.find("{")
        if brace >= 0:
            depth = 0
            for i, c in enumerate(content[brace:], brace):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        return content[brace : i + 1]
        return content

    async def _detect_transformation_ambiguity(
        self,
        query: str,
        confirmed_models: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Detect output_grain, time_spine, comparison_baseline ambiguity. Uses DS_TRANSFORMATION_AMBIGUITY_DETECTOR prompt."""
        prompt_text = get_ds_transformation_ambiguity_detector_prompt()
        if not prompt_text:
            return {"has_ambiguity": False, "skip_user_turn": True, "parameters": {}}
        prompt = prompt_text + f"\n\n### USER QUESTION ###\n{query}\n\n### CONFIRMED MODELS ###\n{json.dumps(confirmed_models, indent=2)}"
        result = await self.llm.ainvoke(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        try:
            return json.loads(self._extract_json(content))
        except Exception as e:
            logger.error(f"Transformation ambiguity detection failed: {e}")
            return {"has_ambiguity": False, "skip_user_turn": True, "parameters": {}}

    async def _resolve_transformation_parameters(
        self,
        detection_output: Dict[str, Any],
        user_answers: Dict[str, Any],
        confirmed_models: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Resolve parameters to concrete values. Uses DS_TRANSFORMATION_RESOLUTION_BUILDER prompt."""
        prompt_text = get_ds_transformation_resolution_builder_prompt()
        if not prompt_text:
            return {"resolved_parameters": {}, "pipeline_constraints": {}}
        prompt = (
            prompt_text
            + f"\n\n### AMBIGUITY DETECTION OUTPUT ###\n{json.dumps(detection_output, indent=2)}"
            + f"\n\n### USER ANSWERS ###\n{json.dumps(user_answers, indent=2)}"
            + f"\n\n### CONFIRMED MODELS ###\n{json.dumps(confirmed_models, indent=2)}"
        )
        result = await self.llm.ainvoke(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        try:
            return json.loads(self._extract_json(content))
        except Exception as e:
            logger.error(f"Parameter resolution failed: {e}")
            return {"resolved_parameters": {}, "pipeline_constraints": {}}

    async def _build_pipeline_plan(
        self,
        query: str,
        confirmed_models: List[Dict[str, Any]],
        resolved_parameters: Dict[str, Any],
        function_map: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build structured 3-step execution plan. Uses DS_PIPELINE_PLANNER prompt."""
        prompt_text = get_ds_pipeline_planner_prompt()
        if not prompt_text:
            return {}
        appendix_block = self._appendix_prompt + APPENDIX_RESTRICTION if self._appendix_functions else ""
        prompt = (
            prompt_text
            + (f"\n\n### AVAILABLE SQL FUNCTIONS (APPENDIX) ###\n{appendix_block}" if appendix_block else "")
            + f"\n\n### USER QUESTION ###\n{query}"
            + f"\n\n### CONFIRMED MODELS ###\n{json.dumps(confirmed_models, indent=2)}"
            + f"\n\n### RESOLVED PARAMETERS ###\n{json.dumps(resolved_parameters, indent=2)}"
            + f"\n\n### FUNCTION EXECUTION PLAN ###\n{json.dumps(function_map, indent=2)}"
        )
        result = await self.llm.ainvoke(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        try:
            return json.loads(self._extract_json(content))
        except Exception as e:
            logger.error(f"Pipeline planning failed: {e}")
            return {}

    async def _generate_nl_question(
        self,
        step_definition: Dict[str, Any],
        available_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate a single NL question for one pipeline step. Uses DS_NL_QUESTION_GENERATOR prompt."""
        prompt_text = get_ds_nl_question_generator_prompt()
        if not prompt_text:
            return {"step": 0, "nl_question": "", "agent_context": available_schema}
        prompt = (
            prompt_text
            + f"\n\n### STEP DEFINITION ###\n{json.dumps(step_definition, indent=2)}"
            + f"\n\n### AVAILABLE SCHEMA ###\n{json.dumps(available_schema, indent=2)}"
        )
        result = await self.llm.ainvoke(prompt)
        content = result.content if hasattr(result, "content") else str(result)
        try:
            return json.loads(self._extract_json(content))
        except Exception as e:
            logger.error(f"NL question generation failed: {e}")
            return {"nl_question": "", "agent_context": available_schema}

    async def _generate_sql_internal(
        self,
        query: str,
        contexts: List[str],
        reasoning: str = "",
        configuration: Dict = None,
        relationships: List[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Override: inject DS generation system prompt with 3-step CTE pattern,
        pipeline plan, NL questions, and full appendix contracts before calling base SQL generator.
        """
        appendix_block = self._appendix_prompt + APPENDIX_RESTRICTION

        # Include pipeline plan and NL questions from planning phase when available
        plan_context = ""
        planning = getattr(self, "_ds_cached_pipeline_planning", None)
        if planning:
            plan = planning.get("pipeline_plan", {})
            nl_questions = planning.get("nl_questions", [])
            if plan or nl_questions:
                plan_context = "\n\n### DS PIPELINE PLAN ###\n"
                if plan:
                    plan_context += json.dumps(plan, indent=2)
                if nl_questions:
                    plan_context += "\n\n### NL QUESTIONS ###\n"
                    for nq in nl_questions:
                        plan_context += f"- {nq.get('step', '')}: {nq.get('nl_question', '')}\n"

        # Prepend DS generation prompt + appendix + plan + reasoning
        augmented_reasoning = (
            DS_GENERATION_SYSTEM_PROMPT
            + "\n\n"
            + appendix_block
            + plan_context
            + "\n\n### REASONING PLAN ###\n"
            + (reasoning or "")
        )

        return await super()._generate_sql_internal(
            query,
            contexts,
            augmented_reasoning,
            configuration,
            relationships,
            **kwargs
        )

"""
Integration demo for DS RAG agent with project_id=cornerstone.

Uses app.settings and app.core.dependencies like demo_askandquestion_recommendation.
Flow: PipelineContainer.initialize() -> index cornerstone (optional) -> DSRAgent.process_sql_request(GENERATION).

DS RAG flow (per ds_rag_fixes):
  Step 1: DS_PIPELINE_PLANNER — structured plan (data fetch, transformation, operations)
  Step 2: DS_NL_QUESTION_GENERATOR — precise NL questions per step
  (Steps 3–4: NL-to-SQL × 3 and _propagate_step_context removed for debugging; single-shot generation used)

Output includes task_decomposition (bubbled from _reason_sql_internal) and generated SQL.

Run with --output FILE to save stage outputs to a file for inspection.
Run with --errors FILE to save all errors to a separate file for review (one error per section).
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, TextIO

from app.settings import get_settings
from app.core.dependencies import get_llm, get_doc_store_provider, clear_chromadb_cache
from app.core.engine_provider import EngineProvider
from app.agents.pipelines.pipeline_container import PipelineContainer
from app.agents.nodes.sql.sql_rag_agent import SQLOperationType
from app.agents.nodes.ds.ds_rag_agent import DSRAgent
from app.indexing.project_reader_qdrant import ProjectReaderQdrant
from app.settings import VectorStoreType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("lexy-ai-service")

logging.getLogger("app.storage").setLevel(logging.WARNING)
logging.getLogger("app.indexing").setLevel(logging.WARNING)

PROJECT_ID = "cornerstone"


def _write_stage(f: TextIO, label: str, content: Any) -> None:
    """Write a stage label and content to the output file."""
    f.write("\n")
    f.write("=" * 80 + "\n")
    f.write(f"## {label}\n")
    f.write("=" * 80 + "\n")
    if isinstance(content, (dict, list)):
        f.write(json.dumps(content, indent=2, default=str))
    else:
        f.write(str(content))
    f.write("\n")


def _write_error(errors_file: TextIO, error_num: int, context: Dict[str, Any], error_msg: str) -> None:
    """Write a single error to the errors file for review."""
    errors_file.write("\n")
    errors_file.write("#" * 80 + "\n")
    errors_file.write(f"# ERROR {error_num}\n")
    errors_file.write("#" * 80 + "\n")
    errors_file.write(json.dumps(context, indent=2, default=str))
    errors_file.write("\n\n--- ERROR MESSAGE ---\n")
    errors_file.write(str(error_msg))
    errors_file.write("\n")


class DSRAgentCornerstoneDemo:
    """Integration demo: DS RAG agent for cornerstone project."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DSRAgentCornerstoneDemo, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                settings = get_settings()
                clear_chromadb_cache()

                # Initialize pipeline container (needed for DS agent sample data fetch)
                self.pipeline_container = PipelineContainer.initialize()

                llm = get_llm(
                    temperature=getattr(settings, "SQL_GENERATION_TEMPERATURE", 0.0),
                    model=getattr(settings, "MODEL_NAME", "gpt-4o-mini"),
                )
                engine = EngineProvider.get_engine()
                doc_store_provider = get_doc_store_provider()
                retrieval_helper = self.pipeline_container._retrieval_helper

                appendix_path = settings.BASE_DIR / "data" / "sql_functions" / "sql_function_appendix.json"
                if not appendix_path.exists():
                    logger.warning("Appendix not found: %s. DS agent will have empty appendix.", appendix_path)

                self.ds_agent = DSRAgent(
                    llm=llm,
                    engine=engine,
                    document_store_provider=doc_store_provider,
                    retrieval_helper=retrieval_helper,
                    appendix_path=appendix_path,
                )
                self._initialized = True
                logger.info("DSRAgentCornerstoneDemo initialized")
            except Exception as e:
                logger.error("Failed to initialize: %s", e)
                self._initialization_failed = True
                self._initialized = True

    async def index_cornerstone(self) -> Dict[str, Any]:
        """Index cornerstone project from sql_meta into Qdrant (if path exists)."""
        if getattr(self, "_initialization_failed", False):
            return {"status": "error", "error": "Initialization failed"}
        try:
            settings = get_settings()
            base_path = settings.BASE_DIR / "data" / "sql_meta"
            ds_functions_path = settings.BASE_DIR / "data" / "sql_functions"
            if not base_path.exists():
                logger.warning("sql_meta path does not exist: %s. Skipping indexing.", base_path)
                return {"status": "skipped", "reason": "sql_meta not found"}

            host = getattr(settings, "QDRANT_HOST", None) or "localhost"
            port = int(getattr(settings, "QDRANT_PORT", 6333))
            reader = ProjectReaderQdrant(
                base_path=str(base_path),
                ds_functions_base_path=str(ds_functions_path),
                host=host,
                port=port,
            )
            projects = reader.list_projects()
            if PROJECT_ID not in projects:
                logger.warning("Project %s not in sql_meta. Available: %s", PROJECT_ID, projects)
                return {"status": "skipped", "reason": f"project {PROJECT_ID} not found"}

            data = await reader.index_project(PROJECT_ID)
            return {
                "status": "success",
                "project_id": data.get("project_id"),
                "tables": len(data.get("tables", [])),
            }
        except Exception as e:
            logger.exception("Index failed: %s", e)
            return {"status": "error", "error": str(e)}

    async def fetch_schema_for_query(
        self,
        query: str,
        project_id: str = PROJECT_ID,
    ) -> Dict[str, Any]:
        """Fetch schema context for a query (for output capture)."""
        if getattr(self, "_initialization_failed", False):
            return {"status": "error", "error": "Initialization failed"}
        try:
            retrieval_helper = self.pipeline_container._retrieval_helper
            result = await retrieval_helper.get_table_names_and_schema_contexts(
                query=query,
                project_id=project_id,
                table_retrieval={"table_retrieval_size": 10, "table_column_retrieval_size": 100},
            )
            return {"status": "success", "result": result}
        except Exception as e:
            logger.exception("Schema fetch failed: %s", e)
            return {"status": "error", "error": str(e)}

    async def process_question(
        self,
        query: str,
        project_id: str = PROJECT_ID,
        language: str = "English",
        output_file: Optional[TextIO] = None,
        use_stepwise_sql: bool = False,
        errors_file: Optional[TextIO] = None,
        errors_list: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Process a natural language question through DS RAG agent.

        use_stepwise_sql: If True, use per-step SQL generation (DDL from previous step)
        instead of single-shot sql_rag_agent generation.
        errors_list: If provided, errors are appended here for later writing to errors file.
        """
        if getattr(self, "_initialization_failed", False):
            return {"status": "error", "error": "Initialization failed"}
        try:
            if output_file:
                _write_stage(output_file, "STAGE: Schema retrieval", {"query": query})
                schema_result = await self.fetch_schema_for_query(query, project_id)
                if schema_result["status"] == "success":
                    r = schema_result.get("result", {})
                    _write_stage(
                        output_file,
                        "Schema retrieval result",
                        {
                            "table_names": r.get("table_names", []),
                            "schema_contexts_count": len(r.get("schema_contexts", [])),
                            "schema_contexts_preview": [
                                (s[:300] + "..." if len(s) > 300 else s)
                                for s in (r.get("schema_contexts", []) or [])[:3]
                            ],
                        },
                    )
                else:
                    _write_stage(output_file, "Schema retrieval (failed)", schema_result)
                    if errors_list is not None:
                        errors_list.append({
                            "source": "schema_retrieval",
                            "query": query,
                            "error": schema_result.get("error", schema_result),
                        })

            result = await self.ds_agent.process_sql_request(
                SQLOperationType.GENERATION,
                query=query,
                project_id=project_id,
                language=language,
                use_stepwise_sql=use_stepwise_sql,
            )

            if output_file:
                r = result
                _write_stage(output_file, "STAGE: Task decomposition", r.get("task_decomposition", ""))
                _write_stage(output_file, "STAGE: Pipeline plan", r.get("pipeline_plan", {}))
                _write_stage(output_file, "STAGE: NL questions", r.get("nl_questions", []))
                step_sqls = r.get("step_sqls", {})
                step_ddls = r.get("step_ddls", {})
                if step_sqls or step_ddls:
                    all_step_keys = sorted(
                        set((step_sqls or {}).keys()) | set((step_ddls or {}).keys()),
                        key=lambda k: (int(k.split("_")[1]) if "_" in k and k.split("_")[1].isdigit() else 999),
                    )
                    for step_key in all_step_keys:
                        if step_key in step_sqls or step_key in step_ddls:
                            step_label = f"STEP: {step_key}"
                            step_block = {
                                "ddl_used": step_ddls.get(step_key, "(not available)"),
                                "sql_generated": step_sqls.get(step_key, "(not available)"),
                            }
                            nl_q = next((nq for nq in (r.get("nl_questions") or []) if nq.get("step") == step_key), None)
                            if nl_q:
                                step_block["nl_question"] = nl_q.get("nl_question", "")
                            _write_stage(output_file, step_label, step_block)
                _write_stage(output_file, "STAGE: Combined SQL (from steps)", r.get("combined_sql", ""))
                data = r.get("data", {}) or {}
                _write_stage(output_file, "STAGE: Reasoning", data.get("reasoning", ""))
                _write_stage(output_file, "STAGE: Generated SQL", data.get("sql", ""))
                _write_stage(
                    output_file,
                    "STAGE: Full result summary",
                    {
                        "success": r.get("success"),
                        "error": r.get("error"),
                        "parsed_entities": data.get("parsed_entities"),
                    },
                )
                output_file.flush()
                if errors_list is not None:
                    if not r.get("success") and r.get("error"):
                        errors_list.append({
                            "source": "generation",
                            "query": query,
                            "error": r.get("error"),
                            "result_summary": {"success": r.get("success"), "error": r.get("error")},
                        })
                    step_errors = r.get("step_errors", {})
                    for step_key, err in step_errors.items():
                        errors_list.append({
                            "source": "step_sql",
                            "step": step_key,
                            "query": query,
                            "error": err,
                        })

            return {"status": "success", "result": result}
        except Exception as e:
            logger.exception("Process question failed: %s", e)
            if output_file:
                _write_stage(output_file, "STAGE: Error", {"error": str(e)})
            if errors_list is not None:
                errors_list.append({
                    "source": "exception",
                    "query": query,
                    "error": str(e),
                })
            return {"status": "error", "error": str(e)}


async def run_demo(
    output_path: Optional[Path] = None,
    use_stepwise_sql: bool = False,
    errors_path: Optional[Path] = None,
):
    """Run DS RAG integration demo for cornerstone."""
    settings = get_settings()
    if settings.VECTOR_STORE_TYPE != VectorStoreType.QDRANT:
        logger.warning(
            "VECTOR_STORE_TYPE=%s. Set VECTOR_STORE_TYPE=qdrant for schema retrieval from Qdrant.",
            settings.VECTOR_STORE_TYPE,
        )

    demo = DSRAgentCornerstoneDemo()
    if getattr(demo, "_initialization_failed", False):
        logger.error("Demo initialization failed, aborting")
        return

    output_file = None
    errors_file = None
    errors_path_resolved = errors_path
    if errors_path_resolved is None and output_path:
        errors_path_resolved = output_path.parent / (output_path.stem + "_errors.txt")
    errors_list: Optional[List[Dict[str, Any]]] = [] if errors_path_resolved else None

    if output_path:
        output_file = open(output_path, "w", encoding="utf-8")
        output_file.write(f"DS RAG Integration Demo Output\n")
        output_file.write(f"Generated: {datetime.now().isoformat()}\n")
        output_file.write(f"Project ID: {PROJECT_ID}\n")

    if errors_path_resolved:
        errors_file = open(errors_path_resolved, "w", encoding="utf-8")
        errors_file.write(f"DS RAG Demo — Errors\n")
        errors_file.write(f"Generated: {datetime.now().isoformat()}\n")
        errors_file.write(f"Project ID: {PROJECT_ID}\n")

    try:
        # Step 1: Index cornerstone (optional - skip if already indexed)
        logger.info("Step 1: Index cornerstone (if sql_meta exists)")
        index_result = await demo.index_cornerstone()
        logger.info("Index result: %s", index_result)
        if output_file:
            _write_stage(output_file, "Index result", index_result)
        if index_result.get("status") == "error" and errors_list is not None:
            errors_list.append({
                "source": "index",
                "error": index_result.get("error", index_result),
            })

        # Step 2: Process test questions
        test_cases = [
            # 3-step pipelines
            "Show the 7-day moving average of completion rate by division for cornerstone over the last 6 months",
            "Calculate the statistical trend of enrollment count by division for cornerstone over the last 6 months",
            "What is the proportion of different Transcript Status (Assigned / Satisfied / Expired / Waived)?",
            # 4-step parallel (trend + anomaly)
            "Detect anomalies in the statistical trend of completion rate by division for cornerstone over the last 6 months",
            "Detect anomalies in completion rate using 7-day moving average by division for cornerstone over the last 6 months",
            # Complex pipelines — different functions
            "Classify the trend direction (strong up, up, flat, down, strong down) of completion count by division for cornerstone over the last 6 months",
            "Show the exponential moving average of completion count by division for cornerstone over the last 6 months",
            "Show the 7-day moving average of completion count by division and position for cornerstone over the last 6 months",
            "Which divisions have a statistically significant decreasing trend in completion rate for cornerstone over the last 6 months?",
            "Compare completion count between the first 3 months and last 3 months by division for cornerstone over the last 6 months",
        ]

        for i, query in enumerate(test_cases):
            logger.info("\n" + "=" * 60)
            logger.info("Test case %d: %s", i + 1, query)
            if output_file:
                output_file.write("\n")
                output_file.write("#" * 80 + "\n")
                output_file.write(f"# TEST CASE {i + 1}\n")
                output_file.write(f"# Query: {query}\n")
                output_file.write("#" * 80 + "\n")

            result = await demo.process_question(
                query=query,
                output_file=output_file,
                use_stepwise_sql=use_stepwise_sql,
                errors_list=errors_list if errors_list is not None else None,
            )
            if result["status"] == "error" and errors_list is not None:
                errors_list.append({
                    "source": "process_question",
                    "query": query,
                    "error": result.get("error", result),
                })
            if result["status"] == "success":
                r = result.get("result", {})
                if r.get("success"):
                    data = r.get("data", {}) or {}
                    sql = data.get("sql", "") or r.get("sql", "")
                    logger.info("Generated SQL: %s", sql[:200] + "..." if len(sql) > 200 else sql)
                    if r.get("task_decomposition"):
                        logger.info("Task decomposition: %s", (r["task_decomposition"] or "")[:150] + "...")
                else:
                    logger.warning("Result: %s", r.get("error", r))
            else:
                logger.warning("Error: %s", result.get("error", result))

        logger.info("\nIntegration demo complete")
        if output_file:
            output_file.write("\n")
            output_file.write("=" * 80 + "\n")
            output_file.write("## Demo complete\n")
            output_file.write("=" * 80 + "\n")
        if errors_file and errors_list:
            errors_file.write(f"\n\nTotal errors: {len(errors_list)}\n")
            for i, err_entry in enumerate(errors_list, 1):
                _write_error(errors_file, i, err_entry, err_entry.get("error", err_entry))
            logger.info("Errors saved to %s (%d errors)", errors_path_resolved, len(errors_list))
    finally:
        if output_file:
            output_file.close()
            logger.info("Output saved to %s", output_path)
        if errors_file:
            errors_file.close()
            if errors_path_resolved:
                logger.info("Errors file: %s", errors_path_resolved)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DS RAG integration demo for cornerstone")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Path to save stage outputs (e.g. demo_output.txt)",
    )
    parser.add_argument(
        "-e", "--errors",
        type=Path,
        default=None,
        help="Path to save errors (default: <output_stem>_errors.txt when -o is used)",
    )
    parser.add_argument(
        "--stepwise",
        action="store_true",
        help="Use per-step SQL generation (DDL from previous step) instead of single-shot",
    )
    args = parser.parse_args()
    asyncio.run(run_demo(
        output_path=args.output,
        use_stepwise_sql=args.stepwise,
        errors_path=args.errors,
    ))

"""
Index utility for core DataScience SQL function assets.
Loads sql_functions.json, sql_function_examples.json, and sql_instructions.json
from a configurable base path and indexes them into three collections:
- core_ds_functions
- core_ds_function_examples
- core_ds_function_instructions
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from langchain_core.documents import Document

logger = logging.getLogger("genieml-agents")


def _load_json(path: Path) -> Optional[Any]:
    """Load JSON file, return None on error."""
    if not path.exists():
        logger.warning(f"DS function file not found: {path}")
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading {path}: {e}")
        return None


def _build_function_documents(functions_data: Dict[str, Any]) -> List[Document]:
    """Build documents for core_ds_functions from sql_functions.json."""
    documents = []
    func_ref = functions_data.get("function_reference", functions_data)
    if not isinstance(func_ref, dict):
        logger.warning("function_reference not found or not a dict in sql_functions.json")
        return documents

    for func_name, func_def in func_ref.items():
        try:
            description = func_def.get("description", "")
            parameters = func_def.get("parameters", [])
            returns = func_def.get("returns", "")
            usage = func_def.get("usage", "")
            example = func_def.get("example", "")

            # Extract param types for SqlFunction compatibility (e.g. "p_x: TEXT" -> "TEXT")
            param_types = []
            for p in parameters:
                if isinstance(p, str) and ":" in p:
                    param_types.append(p.split(":")[-1].strip().split("(")[0].strip())
                elif isinstance(p, dict):
                    param_types.append(p.get("type", "any"))
                else:
                    param_types.append("any")
            param_types_str = ",".join(param_types) if param_types else "any"

            # Embeddable text for retrieval
            param_str = ", ".join(p if isinstance(p, str) else str(p) for p in parameters)
            content_parts = [
                f"Function: {func_name}",
                f"Description: {description}",
                f"Parameters: {param_str}",
                f"Returns: {returns}",
                f"Usage: {usage}",
                f"Example: {example}",
            ]
            page_content = "\n".join(content_parts)

            doc = Document(
                page_content=page_content,
                metadata={
                    "type": "DS_FUNCTION",
                    "name": func_name,
                    "description": description[:300] if description else "",
                    "returns": str(returns)[:200] if returns else "",
                    "param_types": param_types_str,
                    "return_type": str(returns)[:100] if returns else "any",
                    "parameters": parameters,
                    "usage": usage[:200] if usage else "",
                },
            )
            documents.append(doc)
        except Exception as e:
            logger.warning(f"Error processing function {func_name}: {e}")
    return documents


def _build_example_documents(examples_data: Dict[str, Any]) -> List[Document]:
    """Build documents for core_ds_function_examples from sql_function_examples.json."""
    documents = []
    examples = examples_data.get("examples", [])
    if not isinstance(examples, list):
        logger.warning("examples not found or not a list in sql_function_examples.json")
        return documents

    for ex in examples:
        try:
            ex_id = ex.get("id", "")
            function_name = ex.get("function_name", "")
            category = ex.get("category", "")
            question = ex.get("question", "")
            description = ex.get("description", "")
            steps = ex.get("steps", [])
            sql = ex.get("sql", "")
            source_table = ex.get("source_table", {})
            output_columns = ex.get("output_columns", [])

            # Embeddable text
            steps_str = "\n".join(f"- {s}" for s in steps) if isinstance(steps, list) else str(steps)
            table_name = source_table.get("table_name", "") if isinstance(source_table, dict) else ""
            out_cols = (
                [c.get("name", "") for c in output_columns if isinstance(c, dict)]
                if isinstance(output_columns, list)
                else []
            )

            content_parts = [
                f"Example ID: {ex_id}",
                f"Function: {function_name}",
                f"Category: {category}",
                f"Question: {question}",
                f"Description: {description}",
                f"Steps:\n{steps_str}",
                f"Source table: {table_name}",
                f"Output columns: {', '.join(out_cols)}",
                f"SQL:\n{sql}",
            ]
            page_content = "\n".join(content_parts)

            doc = Document(
                page_content=page_content,
                metadata={
                    "type": "DS_FUNCTION_EXAMPLE",
                    "id": ex_id,
                    "function_name": function_name,
                    "category": category,
                    "question": question[:200] if question else "",
                },
            )
            documents.append(doc)
        except Exception as e:
            logger.warning(f"Error processing example {ex.get('id', 'unknown')}: {e}")
    return documents


def _build_instruction_documents(instructions_data: Dict[str, Any]) -> List[Document]:
    """Build documents for core_ds_function_instructions from sql_instructions.json."""
    documents = []

    # 1. Meta + critical_rules
    meta = instructions_data.get("meta", {})
    if meta:
        critical_rules = meta.get("critical_rules", [])
        source_files = meta.get("source_files", [])
        desc = meta.get("description", "")
        content = f"Description: {desc}\nSource files: {', '.join(source_files)}\n\nCritical rules:\n"
        for r in critical_rules:
            content += f"- {r}\n"
        doc = Document(
            page_content=content.strip(),
            metadata={"type": "DS_INSTRUCTION_META", "section": "meta_critical_rules"},
        )
        documents.append(doc)

    # 2. Installation order phases
    install = instructions_data.get("installation_order", {})
    if install:
        phases = install.get("phases", [])
        for phase_obj in phases:
            phase_num = phase_obj.get("phase", 0)
            label = phase_obj.get("label", "")
            items = phase_obj.get("items", [])
            source_files = phase_obj.get("source_files", [])
            note = phase_obj.get("note", "")
            content = f"Phase {phase_num}: {label}\nItems: {', '.join(items)}\n"
            if source_files:
                content += f"Source files: {', '.join(source_files)}\n"
            if note:
                content += f"Note: {note}\n"
            doc = Document(
                page_content=content.strip(),
                metadata={
                    "type": "DS_INSTRUCTION_INSTALL",
                    "section": "installation_order",
                    "phase": phase_num,
                    "label": label,
                },
            )
            documents.append(doc)

    # 3. JSONB input contracts groups
    contracts = instructions_data.get("jsonb_input_contracts", {})
    groups = contracts.get("groups", {}) if isinstance(contracts, dict) else {}
    for group_name, group_data in groups.items():
        if not isinstance(group_data, dict):
            continue
        key_schema = group_data.get("key_schema", {})
        applies_to = group_data.get("applies_to", [])
        example = group_data.get("example", "")
        content = f"JSONB contract group: {group_name}\n"
        content += f"Key schema: {json.dumps(key_schema)}\n"
        content += f"Applies to: {', '.join(applies_to)}\n"
        if example:
            content += f"Example: {example}\n"
        doc = Document(
            page_content=content.strip(),
            metadata={
                "type": "DS_INSTRUCTION_JSONB_CONTRACT",
                "section": "jsonb_input_contracts",
                "group": group_name,
            },
        )
        documents.append(doc)

    # 4. Per-function instructions from "functions" key
    funcs = instructions_data.get("functions", {})
    for func_name, func_inst in funcs.items():
        if not isinstance(func_inst, dict):
            continue
        content_parts = [f"Function: {func_name}"]
        for k, v in func_inst.items():
            if isinstance(v, (str, int, float, bool)):
                content_parts.append(f"{k}: {v}")
            elif isinstance(v, (list, dict)):
                content_parts.append(f"{k}: {json.dumps(v)[:500]}")
        doc = Document(
            page_content="\n".join(content_parts),
            metadata={
                "type": "DS_INSTRUCTION_FUNCTION",
                "section": "functions",
                "function_name": func_name,
            },
        )
        documents.append(doc)

    # 5. Database table dependencies
    deps = instructions_data.get("database_table_dependencies", {})
    tables = deps.get("tables", {}) if isinstance(deps, dict) else {}
    for table_name, table_info in tables.items():
        if not isinstance(table_info, dict):
            continue
        required_by = table_info.get("required_by", [])
        note = table_info.get("note", "")
        expected_cols = table_info.get("expected_columns", [])
        content = f"Table: {table_name}\nRequired by: {', '.join(required_by)}\n"
        if expected_cols:
            content += f"Expected columns: {', '.join(expected_cols)}\n"
        if note:
            content += f"Note: {note}\n"
        doc = Document(
            page_content=content.strip(),
            metadata={
                "type": "DS_INSTRUCTION_TABLE_DEP",
                "section": "database_table_dependencies",
                "table_name": table_name,
            },
        )
        documents.append(doc)

    return documents


def index_ds_functions(
    base_path: Path,
    stores: Dict[str, Any],
    preview: bool = False,
) -> Dict[str, int]:
    """
    Load SQL function assets and index into the three core_ds_* stores.

    Args:
        base_path: Path to directory containing sql_functions.json,
                   sql_function_examples.json, sql_instructions.json
        stores: Dict with keys "core_ds_functions", "core_ds_function_examples",
                "core_ds_function_instructions" mapping to document stores
        preview: If True, do not write to stores (return counts only)

    Returns:
        Dict with documents_written per collection
    """
    results = {"core_ds_functions": 0, "core_ds_function_examples": 0, "core_ds_function_instructions": 0}

    # Load JSON files
    func_path = base_path / "sql_functions.json"
    ex_path = base_path / "sql_function_examples.json"
    inst_path = base_path / "sql_instructions.json"
    logger.info("Loading DS function files: %s, %s, %s", func_path, ex_path, inst_path)

    functions_data = _load_json(func_path)
    examples_data = _load_json(ex_path)
    instructions_data = _load_json(inst_path)

    if not functions_data and not examples_data and not instructions_data:
        logger.warning("No DS function data loaded from %s. Check that sql_functions.json, sql_function_examples.json, and sql_instructions.json exist.", base_path)

    if functions_data:
        func_docs = _build_function_documents(functions_data)
        store = stores.get("core_ds_functions")
        if store and func_docs and not preview:
            store.add_documents(func_docs)
            results["core_ds_functions"] = len(func_docs)
            logger.info(f"Indexed {len(func_docs)} documents into core_ds_functions")
        elif func_docs:
            results["core_ds_functions"] = len(func_docs)

    if examples_data:
        ex_docs = _build_example_documents(examples_data)
        store = stores.get("core_ds_function_examples")
        if store and ex_docs and not preview:
            store.add_documents(ex_docs)
            results["core_ds_function_examples"] = len(ex_docs)
            logger.info(f"Indexed {len(ex_docs)} documents into core_ds_function_examples")
        elif ex_docs:
            results["core_ds_function_examples"] = len(ex_docs)

    if instructions_data:
        inst_docs = _build_instruction_documents(instructions_data)
        store = stores.get("core_ds_function_instructions")
        if store and inst_docs and not preview:
            store.add_documents(inst_docs)
            results["core_ds_function_instructions"] = len(inst_docs)
            logger.info(f"Indexed {len(inst_docs)} documents into core_ds_function_instructions")
        elif inst_docs:
            results["core_ds_function_instructions"] = len(inst_docs)

    return results

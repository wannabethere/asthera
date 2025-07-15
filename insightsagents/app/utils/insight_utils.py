import re
import nbformat
from io import StringIO
from pathlib import Path
from copy import deepcopy
from typing import Dict
import json
import os
import pandas as pd
from langchain_core.documents import Document as LangchainDocument

def chat_and_retry(chat, messages, n_retry, parser):
    """
    Retry querying the chat models until it returns a valid value with a maximum number of retries.

    Parameters:
    -----------
        chat: callable
            A langchain chat object taking a list of messages and returning the llm's message.
        messages: list
            The list of messages so far.
        n_retry: int
            The maximum number of retries.
        parser: callable
            A function taking a message and returning a tuple (value, valid, retry_message)
            where value is the parsed value, valid is a boolean indicating if the value is valid and retry_message
            is a message to display to the user if the value is not valid.

    Returns:
    --------
        value: object
            The parsed value.

    Raises:
    -------
        ValueError: if the value could not be parsed after n_retry retries.

    """
    for i in range(n_retry):
        messages = convert_messages_to_text(messages)
        print(messages)
        answer = chat.invoke(messages)
        
        value, valid, retry_message = parser(answer.content)

        if valid:
            return value

        msg = f"Query failed. Retrying {i+1}/{n_retry}.\n[LLM]:\n{answer}\n[User]:\n{retry_message}"
        
        messages += answer.content
        messages += retry_message

    return {
        "answer": "Error occured",
        "justification": f"Could not parse a valid value after {n_retry} retries.",
    }


def convert_messages_to_text(messages):
    """
    Convert a list of messages to a string

    Parameters
    ----------
    messages : list
        List of messages to convert

    Returns
    -------
    str
        String representation of the messages

    """
    
    return "\n".join(
        [
            (
                f"[INST]\n{m.content}\n[/INST]"
            )
            for m in messages
        ]
    )

def extract_html_tags(text, keys):
    """Extract the content within HTML tags for a list of keys.

    Parameters
    ----------
    text : str
        The input string containing the HTML tags.
    keys : list of str
        The HTML tags to extract the content from.

    Returns
    -------
    dict
        A dictionary mapping each key to a list of subset in `text` that match the key.

    Notes
    -----
    All text and keys will be converted to lowercase before matching.

    """
    content_dict = {}
    keys = set(keys)
    for key in keys:
        pattern = f"<{key}>(.*?)</{key}>"
        matches = re.findall(pattern, text, re.DOTALL)
        # print(matches)
        if matches:
            content_dict[key] = [match.strip() for match in matches]
    return content_dict



def _parse_human_readable_insight(output):
    """
    A parser that makes sure that the human readable insight is produced in the correct format

    """
    try:
        answer = extract_html_tags(output, ["answer"])
        if "answer" not in answer:
            return (
                "",
                False,
                f"Error: you did not generate answers within the <answer></answer> tags",
            )
        answer = answer["answer"][0]
    except ValueError as e:
        return (
            "",
            False,
            f"The following error occured while extracting the value for the <answer> tag: {str(e)}",
        )

    try:
        justification = extract_html_tags(output, ["justification"])
        if "justification" not in justification:
            return (
                "",
                False,
                f"Error: you did not generate answers within the <justification></justification> tags",
            )
        justification = justification["justification"][0]
    except ValueError as e:
        return (
            "",
            False,
            f"The following error occured while extracting the value for the <justification> tag: {str(e)}",
        )
    try:
        insight = extract_html_tags(output, ["insight"])
        if "insight" not in insight:
            return (
                "",
                False,
                f"Error: you did not generate answers within the <insight></insight> tags",
            )
        insight = insight["insight"][0]
    except ValueError as e:
        return (
            "",
            False,
            f"The following error occured while extracting the value for the <insight> tag: {str(e)}",
        )

    return (
        {"answer": answer, "justification": justification, "insight": insight},
        True,
        "",
    )


def _build_insight_prompt(solution) -> str:
    """
    Gather all plots and statistics produced by the model and format then nicely into text

    """
    insight_prompt = ""
    for i, var in enumerate(solution["vars"]):
        insight_prompt += f"<insight id='{i}'>"
        insight_prompt += f"    <stat>"
        insight_prompt += f"        <name>{var['stat'].get('name', 'n/a')}</name>"
        insight_prompt += f"        <description>{var['stat'].get('description', 'n/a')}</description>"
        stat_val = var["stat"].get("value", "n/a")
        stat_val = stat_val[:50] if isinstance(stat_val, list) else stat_val
        insight_prompt += f"        <value>{stat_val}</value>"
        insight_prompt += f"    </stat>"
        insight_prompt += f"    <plot filename='{var['plot']['name']}'>"
        insight_prompt += f"        <xaxis>"
        insight_prompt += f"            <description>{var['x_axis'].get('description', 'n/a')}</description>"
        x_val = var["x_axis"].get("value", "n/a")
        x_val = x_val[:50] if isinstance(x_val, list) else x_val
        insight_prompt += f"            <value>{x_val}</value>"
        insight_prompt += f"        </xaxis>"
        insight_prompt += f"        <yaxis>"
        insight_prompt += f"            <description>{var['y_axis'].get('description', 'n/a')}</description>"
        y_val = var["y_axis"].get("value", "n/a")
        y_val = y_val[:50] if isinstance(y_val, list) else y_val
        insight_prompt += f"            <value>{y_val}</value>"
        insight_prompt += f"        </yaxis>"
        insight_prompt += f"    </plot>"
        insight_prompt += f"</insight>"
    return insight_prompt



def analysis_nb_to_gt(fname_notebook, include_df_head=False) -> None:
    """
    Reads all ipynb files in data_dir and parses each cell and converts it into a ground truth file.
    The ipynb files are structured as follows: code (outputs plot), then a cell with an insight dict
    """

    def _extract_metadata(nb):
        # iterate through the cells
        metadata = {}
        # extract metadata

        # extract name of the dataset from the first cell
        dname = re.findall(r"## (.+) \(Flag \d+\)", nb.cells[0].source)[0].strip()
        metadata["dataset_name"] = dname
        # extract dataset description
        description = (
            re.findall(
                r"(Dataset Overview|Description)(.+)(Your Objective|Task)",
                nb.cells[0].source,
                re.DOTALL,
            )[0][1]
            .replace("#", "")
            .strip()
        )
        metadata["dataset_description"] = description

        # extract goal and role
        metadata["goal"] = re.findall(r"Goal|Objective\**:(.+)", nb.cells[0].source)[
            0
        ].strip()
        metadata["role"] = re.findall(r"Role\**:(.+)", nb.cells[0].source)[0].strip()

        metadata["difficulty"] = re.findall(
            r"Difficulty|Challenge Level\**: (\d) out of \d", nb.cells[0].source
        )[0].strip()
        metadata["difficulty_description"] = (
            re.findall(
                r"Difficulty|Challenge Level\**: \d out of \d(.+)", nb.cells[0].source
            )[0]
            .replace("*", "")
            .strip()
        )
        metadata["dataset_category"] = re.findall(
            r"Category\**: (.+)", nb.cells[0].source
        )[0].strip()

        # Get Dataset Info
        tag = r"^dataset_path =(.+)"

        dataset_csv_path = None
        for cell in nb.cells:
            if cell.cell_type == "code":
                if re.search(tag, cell.source):
                    dataset_csv_path = (
                        re.findall(tag, cell.source)[0]
                        .strip()
                        .replace("'", "")
                        .replace('"', "")
                    )
                    break
        assert dataset_csv_path is not None
        metadata["dataset_csv_path"] = dataset_csv_path

        if include_df_head:
            metadata["df_head"] = pd.read_html(
                StringIO(cell.outputs[0]["data"]["text/html"])
            )

        # Get Dataset Info
        tag = r"user_dataset_path =(.+)"

        user_dataset_csv_path = None
        for cell in nb.cells:
            if cell.cell_type == "code":
                if re.search(tag, cell.source):
                    user_dataset_csv_path = (
                        re.findall(tag, cell.source)[0]
                        .strip()
                        .replace("'", "")
                        .replace('"', "")
                    )
                    break
        metadata["user_dataset_csv_path"] = user_dataset_csv_path

        # Get Summary of Findings
        tag = r"Summary of Findings \(Flag \d+\)(.+)"

        flag = None
        for cell in reversed(nb.cells):
            if cell.cell_type == "markdown":
                if re.search(tag, cell.source, re.DOTALL | re.IGNORECASE):
                    flag = (
                        re.findall(tag, cell.source, re.DOTALL | re.IGNORECASE)[0]
                        .replace("#", "")
                        .replace("*", "")
                        .strip()
                    )
                    break
        assert flag is not None
        metadata["flag"] = flag

        return metadata

    def _parse_question(nb, cell_idx):
        qdict = {}
        qdict["question"] = (
            re.findall(
                r"Question( |-)(\d+).*:(.+)", nb.cells[cell_idx].source, re.IGNORECASE
            )[0][2]
            .replace("*", "")
            .strip()
        )

        if nb.cells[cell_idx + 2].cell_type == "code":
            # action to take to answer the question
            assert nb.cells[cell_idx + 1].cell_type == "markdown"
            qdict["q_action"] = nb.cells[cell_idx + 1].source.replace("#", "").strip()
            assert nb.cells[cell_idx + 2].cell_type == "code"
            qdict["code"] = nb.cells[cell_idx + 2].source
            # extract output plot. Note that this image data is in str,
            # will need to use base64 to load this data

            qdict["plot"] = nb.cells[cell_idx + 2].outputs
            # loop as there might be multiple outputs and some might be stderr
            for o in qdict["plot"]:
                if "data" in o and "image/png" in o["data"]:
                    qdict["plot"] = o["data"]["image/png"]
                    break

            # extract the insight
            try:
                qdict["insight_dict"] = json.loads(nb.cells[cell_idx + 4].source)
            except Exception as e:
                # find the next cell with the insight dict
                for cell in nb.cells[cell_idx + 3 :]:
                    try:
                        qdict["insight_dict"] = json.loads(cell.source)
                        break
                    except Exception as e:
                        continue

        else:
            # print(f"Found prescriptive insight in {fname_notebook}")
            qdict["insight_dict"] = {
                "data_type": "prescriptive",
                "insight": nb.cells[cell_idx + 1].source.strip(),
                "question": qdict["question"],
            }
        return qdict

    def _parse_notebook(nb):
        gt_dict = _extract_metadata(nb)

        # extract questions, code, and outputs
        que_indices = [
            idx
            for idx, cell in enumerate(nb.cells)
            if cell.cell_type == "markdown"
            and re.search(r"Question( |-)\d+", cell.source, re.IGNORECASE)
        ]
        gt_dict["insights"] = []
        for que_idx in que_indices:
            gt_dict["insights"].append(_parse_question(nb, que_idx))
        return gt_dict

    # Convert the notebook to a ground truth file
    if not fname_notebook.endswith(".ipynb"):
        raise ValueError("The file must be an ipynb file")
    else:
        # extract dataset id from flag-analysis-i.ipynb using re
        fname_json = fname_notebook.replace(".ipynb", ".json")

        with open(fname_notebook, "r") as f:
            notebook = nbformat.read(f, as_version=4)
        gt_dict = _parse_notebook(notebook)

    return gt_dict


def extract_insights_from_file(file_name,datadir_path="/Users/sameerm/ComplianceSpark/byziplatform/unstructured/insight-bench/data/notebooks"):
    fname_ipynb = os.path.join(datadir_path, file_name)
    gt_insights_dict = analysis_nb_to_gt(fname_ipynb)
    insights_data = get_all_values_for_key(gt_insights_dict,'insight_dict')
        #save_json("flag_2.json",gt_insights_dict)
    print("insights_data extracted")
    
    insights= remove_key(gt_insights_dict,'plot')

    insights_data = getDocFromInsights({"name": fname_ipynb,"insights_data":insights_data, 
                "metadata": {
                        "goal": str(gt_insights_dict['goal']),
                        "role": str(gt_insights_dict['role']),
                        "dataset_name": str(gt_insights_dict['dataset_name']),
                        "dataset_csv_path": str(gt_insights_dict['dataset_csv_path']),
                        "user_dataset_csv_path": str(gt_insights_dict['user_dataset_csv_path']),
                        "flag": str(gt_insights_dict['flag']),
                        "difficulty": str(gt_insights_dict['difficulty']),
                        "difficulty_description": str(gt_insights_dict['difficulty_description']),
                        "dataset_category": str(gt_insights_dict['dataset_category']),
                        "category": str(gt_insights_dict['dataset_category']),
                        "dataset_description": str(gt_insights_dict['dataset_description']),
                        "difficulty_description": str(gt_insights_dict['difficulty_description'])
                    }
                })
    
    return insights_data, insights
    

def extract_insights_nb(exp_dict,datadir_path = "/Users/sameerm/ComplianceSpark/byziplatform/unstructured/insight-bench/data/notebooks", **args):
    # Print Exp dict as hyperparamters and savedir
    """
    print("\nExperiment Dict:")
    print(f"\nSavedir: {savedir}\n")
    if args.reset and os.path.exists(savedir) and not args.eval_only:
        # assert savedir has exp_dict.json for safety
        assert os.path.exists(os.path.join(savedir, "exp_dict.json"))
        os.system(f"rm -rf {savedir}")
    save_json(os.path.join(savedir, "exp_dict.json"), exp_dict)
    """
    
    try:
        # Get dataset paths
        if exp_dict["do_sensitivity"]:
            fname_ipynb = os.path.join(datadir_path, "flag-2.ipynb")
            gt_insights_dict = analysis_nb_to_gt(fname_ipynb)
            slope = exp_dict["slope"]
            dataset_csv_path = (
                f"csvs/sensitivity_analysis/incidents_with_slope_{slope:03d}.csv"
            )
        else:
            fname_ipynb = os.path.join(datadir_path, f"flag-{exp_dict['dataset_id']}.ipynb")
            gt_insights_dict = analysis_nb_to_gt(fname_ipynb)
            dataset_csv_path = gt_insights_dict["dataset_csv_path"]
        
        insights_data = get_all_values_for_key(gt_insights_dict,'insight_dict')
        #save_json("flag_2.json",gt_insights_dict)
        print("insights_data extracted")
        insights_data = getDocFromInsights({"name": fname_ipynb,"insights_data":insights_data, 
                    "metadata": {
                            "goal": str(gt_insights_dict['goal']),
                            "role": str(gt_insights_dict['role']),
                            "dataset_name": str(gt_insights_dict['dataset_name']),
                            "dataset_csv_path": str(gt_insights_dict['dataset_csv_path']),
                            "user_dataset_csv_path": str(gt_insights_dict['user_dataset_csv_path']),
                            "flag": str(gt_insights_dict['flag']),
                            "difficulty": str(gt_insights_dict['difficulty']),
                            "difficulty_description": str(gt_insights_dict['difficulty_description']),
                            "dataset_category": str(gt_insights_dict['dataset_category']),
                            "category": str(gt_insights_dict['dataset_category']),
                            "dataset_description": str(gt_insights_dict['dataset_description']),
                            "difficulty_description": str(gt_insights_dict['difficulty_description'])
                        }
                    })
        return insights_data
    except:
        return {}

def getDocFromInsights(insights):
    insights_data = insights['insights_data']
    return {"data":insights_data,"metadata":insights['metadata']}

def get_all_values_for_key(data, key):
    result = []
    for k, v in data.items():
        if k == key:
            if 'plot' in v: 
                v.pop('plot')
            result.append(v)
        if isinstance(v, dict):
            res = get_all_values_for_key(v, key)
            if res is not None and len(res) > 0:
                if 'plot' in res: 
                    res.pop('plot')
                result.append(res)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    res = get_all_values_for_key(item, key)
                    if res is not None and len(res) > 0:
                        result.append(res)
    return result

def remove_key(data, key):
    if isinstance(data, dict):
        if key in data:
            data.pop(key)
        for v in data.values():
            remove_key(v, key)
    elif isinstance(data, list):
        for item in data:
            remove_key(item, key)
    return data

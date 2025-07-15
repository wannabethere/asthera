import re
import json
import nbformat
import pandas as pd
from io import StringIO
from langchain_core.documents import Document as LangchainDocument
from chatbot.multiagent_planners.services.documentstore import DocumentChromaStore, persistent_client

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

if __name__ == "__main__":
    import os
    

    # Directory containing notebooks
    notebooks_dir = "/Users/sameerm/llm/insight-bench/data/notebooks"  # Replace with your notebooks directory
    
    # Initialize document store
    doc_store = DocumentChromaStore(persistent_client=persistent_client,collection_name="notebook_insights_v2",vectorstore_path="./data/vector_store")
    # Initialize vector store with appropriate configuration    
    doc_store.initialize()
    # Process each notebook in the directory
    i = 0
    documents = []
    """
    for fname in os.listdir(notebooks_dir):
        print(f"{i}\n")
        if fname.endswith(".ipynb"):
            notebook_path = os.path.join(notebooks_dir, fname)
            try:
                # Parse notebook to get ground truth
                gt_dict = analysis_nb_to_gt(notebook_path)
                
                for insight in gt_dict["insights"]:
                    if "plot" in insight:
                        del insight["plot"]
                documents.append(
                    LangchainDocument(
                        page_content = json.dumps(gt_dict),
                        metadata= {
                            "dataset_name": gt_dict.get("dataset_name", ""),
                            "id": fname.replace(".ipynb", ""),
                            "description": gt_dict.get("dataset_description", ""),
                            "difficulty": gt_dict.get("difficulty", ""),
                            "category": gt_dict.get("dataset_category", ""),
                            "goal": gt_dict.get("goal", ""),
                            "role": gt_dict.get("role", ""),
                            "flag": gt_dict.get("flag", ""),
                        },
                        id =fname.replace(".ipynb", "")
                    )
                )
                doc_store.add_documents(documents)
                print(f"Successfully processed and stored {fname}")
            except Exception as e:
                print(f"Error processing {fname}: {str(e)}")
    """
    # Test semantic search with BM25 ranking
    search_query = "For the given Purchase Order data, what are the some KPIs, EDA, Features and Analysis questions inorder to explain Variance accrued, invoiced and paid by project cost center and region?"
    
    # Get semantic search results
    semantic_results = doc_store.semantic_search(
        query=search_query,
        k=5
    )
    for result in semantic_results:
        print(f"semantic_results {json.loads(result['content'])['insights']} \n {result['metadata']}\n")
   
   
    
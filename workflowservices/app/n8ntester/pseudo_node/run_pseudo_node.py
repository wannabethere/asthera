import json
from config import CONFIG
from n8ncomponents.workflow import Workflow
from n8ncomponents.node import n8nPythonNode
from .ai_node import run_ai_completion
from .utils import fill_return_data, replace_exp



def run_pseudo_workflow(input_data: list, constant_workflow: Workflow) -> str:
    """
    Run a pseudo workflow using the provided input data and constant workflow.

    Args:
        input_data (list): The input data for the pseudo workflow.
        constant_workflow (n8nPythonWorkflow): The constant workflow to be used.

    Returns:
        str: The final return data of the pseudo workflow.
    """
    # import pdb; pdb.set_trace()
    node_var:n8nPythonNode = constant_workflow['nodes'][-1]
    params_raw = node_var['parameters']

    # params_list = replace_exp(input_data, params_raw)
    params_list = [params_raw]

    if node_var['type'].split('.')[-1] == 'aiCompletion':
        return_list = [] #by passing for testing run_ai_completion(params_list)
    else:
        return_list = []
    final_return_data = fill_return_data(return_list)

    return final_return_data

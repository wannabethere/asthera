from typing import List, Dict
from dataclasses import dataclass, field
from enum import Enum, unique
from copy import deepcopy
import json

from .models import NodeType, ToolCallStatus, RunTimeStatus
from .parameters import *
from enum import Enum, unique

    
@dataclass
class n8nNodeMeta():
    node_type: NodeType = NodeType.action
    integration_name: str = ""
    resource_name: str = ""
    operation_name: str = ""
    operation_description: str = ""

    def to_action_string(self):
        """
        Generates a string representation of the action performed by the node.
        
        Returns:
            str: The string representation of the action.
        """
        output = f"{self.node_type.name}(resource={self.resource_name}, operation={self.operation_name})"
        if self.operation_description != "":
            output += f": {self.operation_description}"
        return output
    
@dataclass
class n8nPythonNode():
    node_id: int = 1
    node_meta: n8nNodeMeta = field(default_factory=n8nNodeMeta())
    node_comments: str = ""
    note_todo: List[str] = field(default_factory=lambda: [])
    node_json: dict = field(default_factory=lambda: {})
    params: Dict[str, Parameter] = field(default_factory=lambda: {})
    node_pre: List[str] = field(default_factory=lambda: [])
    node_post: List[str] = field(default_factory=lambda: [])
    implemented: bool = False
    

    def get_name(self):
        """
        Returns a string representing the name of the node.
        
        Parameters:
            self (Node): The Node object.
        
        Returns:
            str: The name of the node, which is a combination of the node type and the node ID.
        """
        return f"{self.node_meta.node_type.name}_{self.node_id}"

    def get_runtime_description(self) -> str:
        """
        Get the information about the last runtime of the Workflow.

        Returns:
            str: The description of the last runtime.

        """
        if self.last_runtime_info == RunTimeStatus.DidNotImplemented:
            return f"This {self.node_meta.node_type} has not been implemented"

    def update_implement_info(self):
        if len(self.params) == 0:
            self.implemented = True
            return
        for key, value in self.params.items():
            if value.data_is_set:
                self.implemented = True
                return


    def print_self_clean(self):
        """Returns a multiline text."""
        lines = []
        input_data = "input_data: List[Dict] =  [{...}]" if self.node_meta.node_type == NodeType.action else ""
        define_line = f"def {self.get_name()}({input_data}):"
        lines.append(define_line)
        param_json = {}
        for key, value in self.params.items():
            param = value.to_json()
            if param != None:
                param_json[key] = param


        param_str = json.dumps(param_json, indent = 2, ensure_ascii=False)
        param_str = param_str.splitlines(True)
        param_str = [line.strip("\n") for line in param_str]
        prefix = "  params = "
        param_str[0] = prefix + param_str[0]
        if not self.implemented:
            if len(self.params) > 0:
                param_str[0] += "  # to be Implemented"
            else:
                param_str[0] += "  # This function doesn't need spesific param"
        for i in range(1, len(param_str)):
            param_str[i] = " "*len(prefix) + param_str[i]
        lines.extend(param_str)

        lines.append(f"  function = transparent_{self.node_meta.node_type.name}(integration=\"{self.node_meta.integration_name}\", resource=\"{self.node_meta.resource_name}\", operation=\"{self.node_meta.operation_name}\")")
    
        if self.node_meta.node_type == NodeType.action:
            lines.append( "  output_data = function.run(input_data=input_data, params=params)")
        else:
            lines.append( "  output_data = function.run(input_data=None, params=params)")

        lines.append("  return output_data")

        return lines 
    

    def print_self(self):
        """Returns a multiline text."""
        lines = []
        input_data = "input_data: List[Dict] =  [{...}]" if self.node_meta.node_type == NodeType.action else ""
        define_line = f"def {self.get_name()}({input_data}):"
        lines.append(define_line)
        if self.node_comments != "" or self.note_todo != []:
            lines.append(f"  \"\"\"")
        if self.node_comments != "":
            lines.append(f"  comments: {self.node_comments}")
        
        if self.note_todo != []:
            lines.append(f"  TODOs: ")
            for todo in self.note_todo:
                lines.append(f"    - {todo}")
        lines.append(f"  \"\"\"")
        
        param_json = {}
        for key, value in self.params.items():
            param = value.to_json()
            if param != None:
                param_json[key] = param


        param_str = json.dumps(param_json, indent = 2, ensure_ascii=False)
        param_str = param_str.splitlines(True)
        param_str = [line.strip("\n") for line in param_str]
        prefix = "  params = "
        param_str[0] = prefix + param_str[0]
        if not self.implemented:
            if len(self.params) > 0:
                param_str[0] += "  # to be Implemented"
            else:
                param_str[0] += "  # This function doesn't need spesific param"
        for i in range(1, len(param_str)):
            param_str[i] = " "*len(prefix) + param_str[i]
        lines.extend(param_str)

        lines.append(f"  function = transparent_{self.node_meta.node_type.name}(integration=\"{self.node_meta.integration_name}\", resource=\"{self.node_meta.resource_name}\", operation=\"{self.node_meta.operation_name}\")")
    
        if self.node_meta.node_type == NodeType.action:
            lines.append( "  output_data = function.run(input_data=input_data, params=params)")
        else:
            lines.append( "  output_data = function.run(input_data=None, params=params)")

        lines.append("  return output_data")

        return lines 
    
    def parse_parameters(self, param_json: dict) -> (ToolCallStatus, str):
        """
        Parses the input parameters and checks if they conform to the expected format.
        Args:
            param_json (dict): The input parameters in JSON format.
        Returns:
            tuple: A tuple containing the status of the tool call and a JSON string
                representing the result.
        Raises:
            TypeError: If the input parameter is not of type dict.
        """
        new_params = deepcopy(self.params)
        for key in new_params:
            new_params[key].refresh()

        tool_call_result = []

        if not isinstance(param_json, dict):
            tool_status = ToolCallStatus.ParamTypeError
            error_string = "Parameter Type Error: The parameter is expected to be a json format string which can be parsed as dict type. However, you are giving string parsed"
            return tool_status, json.dumps({"error": error_string})

        for key in param_json.keys():
            if key not in new_params.keys():
                tool_status = ToolCallStatus.UndefinedParam
                return tool_status, json.dumps({"error": f"Undefined input parameter \"{key}\" for {self.get_name()}.Supported parameters: {list(new_params.keys())}", "result": "Nothing happened.", "status": tool_status.name})
            if type(param_json[key]) == str and (len(param_json[key]) == 0):
                tool_status = ToolCallStatus.RequiredParamUnprovided
                return tool_status, json.dumps({"error": f"input parameter is null, \"{key}\" for {self.get_name()}. You should put something in it.", "result": "Nothing happened.", "status": tool_status.name})
            parse_status, parse_output = new_params[key].parse_value(param_json[key])
            if parse_status != ToolCallStatus.ToolCallSuccess:
                tool_status = parse_status
                return tool_status, json.dumps({"error": f"{parse_output}", "result": "Nothing Happened", "status": tool_status.name})
            tool_call_result.append(parse_output)

        self.params = new_params
        tool_status = ToolCallStatus.ToolCallSuccess

        self.update_implement_info()
        return tool_status, json.dumps({"result": tool_call_result, "status": tool_status.name})


def parse_display_options(display_options, node: n8nPythonNode) -> bool:
    """
    Check if the given display options should be parsed for the given n8nPythonNode.

    Args:
        display_options (dict): The display options to be parsed.
        node (n8nPythonNode): The n8nPythonNode to be checked against.

    Returns:
        bool: True if the display options should be parsed, False otherwise.
    """
    if "show" in display_options.keys():
        if "resource" in display_options["show"]:
            if node.node_meta.resource_name not in display_options["show"]["resource"]:
                return False
        if "operation" in display_options["show"]:
            if node.node_meta.operation_name not in display_options["show"]["operation"]:
                return False
    else:
        return False
    return True

def parse_properties(node: n8nPythonNode):
    """
    This function parses the properties of a given node and returns a dictionary with parameter descriptions for the model.
    Args:
        node (PythonNode): The node object containing the properties to parse.
    Returns:
        dict: A dictionary containing the parameter descriptions.
    """
    node_json = node.node_json
    parameter_descriptions = {}

    for content in node_json["properties"]:
        assert type(content) == dict
        parameter_name = content["name"]

        if parameter_name in ["resource", "operation", "authentication"]:
            continue
        
        if "displayOptions" in content.keys() and (parse_display_options(content["displayOptions"], node) == False):
            continue

        parameter_type = content["type"]

        new_param = visit_parameter(content)
        if new_param != None:
            parameter_descriptions[parameter_name] = new_param
    return parameter_descriptions
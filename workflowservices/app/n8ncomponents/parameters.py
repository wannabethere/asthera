from enum import Enum, unique
from abc import abstractmethod
from typing import Any
from dataclasses import dataclass, field
from copy import deepcopy
import json

from .models import ToolCallStatus

expression_schema = "str(\"=.*($json\..*)\.*\")"

@unique
class ParameterType(Enum):
    """
    Parameter Type
    """
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    LIST = "list"
    JSON = "json"
    COLOR = "color"
    DATATIME = "dateTime"
    COLLECTION = "collection"
    FIXEDCOLLECTION = "fixedCollection"
    OPTIONS = "options"
    MULTIOPTIONS = "multiOptions"
    RESOURCELOCATOR = "resourceLocator"
    RESOURCEMAPPER = "resourceMapper"
    NOTICE = "notice"
    ERROR = "error" #不能有这个


def visit_parameter(param_json: dict):
    """
    Visits a parameter based on its type and returns the result.
    
    Parameters:
        param_json (dict): A dictionary representing the parameter in JSON format.
        
    Returns:
        The result of visiting the parameter based on its type.
    """

    param_type = param_json["type"]

    # if param_type == ParameterType.NOTICE.value:
    #     return Notice.visit(param_json)
    if param_type == ParameterType.BOOLEAN.value:
        return Boolean.visit(param_json)
    elif param_type == ParameterType.NUMBER.value:
        return Number.visit(param_json)
    elif param_type == ParameterType.STRING.value:
        return String.visit(param_json)
    elif param_type == ParameterType.OPTIONS.value:
        return Option.visit(param_json)
    elif param_type == ParameterType.COLLECTION.value:
        return Collection.visit(param_json)
    elif param_type == ParameterType.FIXEDCOLLECTION.value:
        return FixedCollection.visit(param_json)
    elif param_type == ParameterType.RESOURCELOCATOR.value:
        return ResourceLocator.visit(param_json)
    else:
        print(f"{param_json['name']}: {param_type} not parsed")
        # raise NotImplementedError


@dataclass
class Parameter():
    parent: 'Parameter' = None
    param_type: ParameterType = ParameterType.ERROR 

    name: str = ""
    required: bool = False
    default: Any = None
    description: str = ""
    no_data_expression: bool = False
    display_string: str = ""
    multiple_values: bool = False

    use_expression: bool = False
    data_is_set: bool = False

    def __init__(self, param_json):
        """
        Initializes an instance of the class.
        
        Args:
            param_json (dict): A dictionary containing the parameters of the function.
        
        Returns:
            None
        """
        if "type" in param_json.keys():
            self.param_type = ParameterType(param_json["type"])
        if "name" in param_json.keys():
            self.name = param_json["name"]
        if "default" in param_json.keys():
            self.default = param_json["default"]
        if "required" in param_json.keys():
            self.required = param_json["required"]
        if "displayName" in param_json.keys():
            self.description = param_json["displayName"]
        if "description" in param_json.keys():
            self.description +=  ". " + param_json["description"]
        if "placeholder" in param_json.keys():
            self.description +=  f"({param_json['placeholder']})"

        if "noDataExpression" in param_json.keys():
            self.no_data_expression = param_json["noDataExpression"]


        if "displayOptions" in param_json.keys():
            if "show" in param_json.keys():
                for instance in param_json["displayOptions"]["show"]:
                    if instance not in ["resource", "operation"]:
                        expression = f"{instance} in {param_json['displayOptions']['show'][instance]}"
                        if self.display_string != "":
                            self.display_string += " and "
                        self.display_string += expression

        if "typeOptions" in param_json.keys() and "multipleValues" in param_json["typeOptions"].keys():
            self.multiple_values = param_json["typeOptions"]["multipleValues"]

    def get_depth(self):
        """
        Returns the depth of the current node in the tree.

        Returns:
            int: The depth of the current node in the tree.
        """
        if self.parent == None:
            return 1
        return self.parent.get_depth() + 1

    @classmethod
    @abstractmethod
    def visit(cls, param_json):
        pass
    
    @abstractmethod
    def to_description(self, prefix_ids, indent=2, max_depth=1):
        pass

    @abstractmethod
    def parse_value(self, value: any) -> (ToolCallStatus, str):
        return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} not implemented"

    def get_parameter_name(self):
        """
        Returns the parameter name for the current node in the  workflow.

        Returns:
            str: The parameter name for the current node.

        Raises:
            AssertionError: If the parameter type is `FIXEDCOLLECTION` and the parent node has multiple values.
        """

        if self.parent == None:
            return f"params[\"{self.name}\"]"

        prefix_names = self.parent.get_parameter_name()

        if self.parent.param_type == ParameterType.COLLECTION and self.parent.multiple_values:
            prefix_names += "[0]"
            return prefix_names +f"[\"{self.name}\"]"
        elif self.parent.param_type == ParameterType.FIXEDCOLLECTION and self.parent.multiple_values:
            assert self.param_type == ParameterType.COLLECTION, f"{self.param_type.name}"
            names = f"{prefix_names}[\"{self.name}\"]"
            return names
        elif self.parent.param_type == ParameterType.RESOURCELOCATOR:
            for key,value in self.parent.meta.items():
                if value == self:
                    name = f"{prefix_names}[\"value\"](when \"mode\"=\"{key}\")"
                    return name
        else:
            return prefix_names +f"[\"{self.name}\"]"
    
    def refresh(self):
        """
        Refreshes the data by setting the `data_is_set` attribute to False.
        """
        self.data_is_set = False

def to_json(self):
    """
    Convert python_parameters to _json recursively.
    """
    return None

@dataclass
class Notice(Parameter):
    notice: str = ""

    def __init__(self, param_json):
        """
        Initializes an instance of the class.

        Args:
            param_json (dict): A dictionary containing the parameters.

        Returns:
            None
        """
        super().__init__(param_json)

    @staticmethod
    def visit(param_json):
        """
        Visit the given param_json and create an Notice node.

        Args:
            param_json (dict): The JSON object containing the parameter data.

        Returns:
            Notice: The created Notice node.
        """
        node = Notice(param_json)

        node.notice = param_json["displayName"]
        return node

    def to_description(self, prefix_ids, indent=2, max_depth=1):
        return []
    
@dataclass
class Number(Parameter):
    fixed_value: float = 0.0
    var: str = ""
    def __init__(self, param_json):
        super().__init__(param_json)
        self.fixed_value = 0.0
        self.var = ""
    @classmethod
    def visit(cls, param_json):
        node = Number(param_json)
        return node

    @abstractmethod
    def parse_value(self, value: any) -> (ToolCallStatus, str):
        if type(value) in [int, bool]:
            self.use_expression = False
            self.fixed_value = value
            self.data_is_set = True
            return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as fixed_value"
        elif type(value) == str:
            if value.startswith("\"") and value.endswith("\""):
                value = value[1:-1]
            if self.no_data_expression:
                return ToolCallStatus.UnsupportedExpression, f"{self.get_parameter_name()} don't support expression"
            # TODO: check expression available
            if not value.startswith("="):
                return ToolCallStatus.ExpressionError, f"{self.get_parameter_name()} doesn't have a expression schema: {expression_schema}"

            self.var = value
            self.use_expression = True
            self.data_is_set = True
            return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as expression" 
        else:
            available_types = ["int", "float"]
            if not self.no_data_expression:
                available_types.append(expression_schema)
            return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} can only be parsed as {available_types}, got {json.dumps(value)}" 

    def to_description(self, prefix_ids, indent=2, max_depth=1):
        all_name = self.get_parameter_name()
        line1 = " "*indent + f"{prefix_ids} {all_name}: {self.param_type.value}"

        if self.default != None:
            line1 += f" = {self.default}"
        if self.display_string != "":
            if self.required:
                line1 += f", Required when ({self.display_string}), otherwise do not provide"
            else:
                line1 += f", Activate(Not Required) when ({self.display_string}), otherwise do not provide"
        else:
            if self.required:
                line1 += f", Required"

        line1 +=  f": {self.description}"
        if self.no_data_expression:
            line1 += f". You can't use expression."
        return [line1]

    def to_json(self):
        """
        python_parameters -> _json        
        """
        if not self.data_is_set:
            return None
        if self.use_expression:
            return self.var
        else:
            return self.fixed_value


@dataclass
class Boolean(Parameter):
    fixed_value: bool = False
    var: str = ""

    def __init__(self, param_json):
        super().__init__(param_json)
        self.fixed_value = False
        self.var = ""
    @classmethod
    def visit(cls, param_json):
        node = Boolean(param_json)

        return node

    @abstractmethod
    def parse_value(self, value: any) -> (ToolCallStatus, str):
        """
        Parses the given value and returns the parsed value along with the parsing status.

        Parameters:
            value (any): The value to be parsed.

        Returns:
            tuple: A tuple containing the parsing status and the parsed value.

        Raises:
            None
        """
        if type(value) == bool:
            self.use_expression = False
            self.fixed_value = value
            self.data_is_set = True
            return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as fixed_value"
        elif type(value) == str:
            if value.startswith("\"") and value.endswith("\""):
                value = value[1:-1]
            if self.no_data_expression:
                return ToolCallStatus.UnsupportedExpression, f"{self.get_parameter_name()} don't support expression"
            # TODO: check expression available
            if not value.startswith("="):
                return ToolCallStatus.ExpressionError, f"{self.get_parameter_name()} doesn't have a expression schema: {expression_schema}"

            self.var = value
            self.use_expression = True
            self.data_is_set = True
            return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as expression" 
        else:
            available_types = ["bool"]
            if not self.no_data_expression:
                available_types.append(expression_schema)
            return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} can only be parsed as {available_types}, got {json.dumps(value)}" 


    def to_description(self, prefix_ids, indent=2, max_depth=1):
        """
        Converts the parameter object to a description line.

        Args:
            prefix_ids (str): The prefix IDs for the parameter.
            indent (int): The number of spaces to indent the line. Defaults to 2.
            max_depth (int): The maximum depth of the parameter object. Defaults to 1.

        Returns:
            list: A list containing the description line.
        """
        all_name = self.get_parameter_name()
        line1 = " "*indent + f"{prefix_ids} {all_name}: {self.param_type.value}"

        if self.default != None:
            line1 += f" = {self.default}"
        if self.display_string != "":
            if self.required:
                line1 += f", Required when ({self.display_string}), otherwise do not provide"
            else:
                line1 += f", Activate(Not Required) when ({self.display_string}), otherwise do not provide"
        else:
            if self.required:
                line1 += f", Required"

        line1 +=  f": {self.description}"
        if self.no_data_expression:
            line1 += f". You can't use expression."
        return [line1]
    
    def to_json(self):
        """
        Convert the object to JSON format.
        
        Returns:
            The object in JSON format.
        """
        if not self.data_is_set:
            return None
        if self.use_expression:
            return self.var
        else:
            return self.fixed_value

@dataclass
class String(Parameter):
    value: str = ""
    def __init__(self, param_json):
        super().__init__(param_json)
        self.value = ""
    @classmethod
    def visit(cls, param_json):
        node = String(param_json)
        #TODO: validation
        return node

    @abstractmethod
    def parse_value(self, value: any) -> (ToolCallStatus, str):
        """
        Parses the given value and returns the parsing status and a message.
        
        Args:
            value (any): The value to be parsed.
        
        Returns:
            Tuple[ToolCallStatus, str]: A tuple containing the parsing status and a message.
        """
        if type(value) == str:
            if value.startswith("\"") and value.endswith("\""):
                value = value[1:-1]

            if value.startswith("="):
                if self.no_data_expression:
                    return ToolCallStatus.UnsupportedExpression, f"{self.get_parameter_name()} don't support expression"
                # TODO: check expression available
                self.value = value
                self.data_is_set = True
                return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as expression" 
            else:
                self.value = value
                self.data_is_set = True
                return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as normal-string" 
        else:
            available_types = ["str"]
            if not self.no_data_expression:
                available_types.append(expression_schema)
            return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} can only be parsed as {available_types}, got {json.dumps(value)}" 

    def to_description(self, prefix_ids, indent=2, max_depth=1):
        """
        Converts the current parameter to a description string.

        Args:
            prefix_ids (str): The prefix IDs for the parameter.
            indent (int, optional): The number of spaces to indent the description. Defaults to 2.
            max_depth (int, optional): The maximum depth of the description. Defaults to 1.

        Returns:
            list: A list containing the converted description string.

        Raises:
            None.

        Notes:
            - The `prefix_ids` parameter is used to determine the prefix IDs for the parameter.
            - The `indent` parameter is used to control the level of indentation in the description.
            - The `max_depth` parameter is used to limit the depth of the description.

        Examples:
            >>> to_description("param", indent=4, max_depth=2)
            ['    param: str']
        """
        all_name = self.get_parameter_name()
        line1 = " "*indent + f"{prefix_ids} {all_name}: {self.param_type.value}"

        if self.default != None:
            line1 += f" = \"{self.default}\""
        if self.display_string != "":
            if self.required:
                line1 += f", Required when ({self.display_string}), otherwise do not provide"
            else:
                line1 += f", Activate(Not Required) when ({self.display_string}), otherwise do not provide"
        else:
            if self.required:
                line1 += f", Required"

        line1 +=  f": {self.description}"
        if self.no_data_expression:
            line1 += f". You can't use expression."
        return [line1]
    
    def to_json(self):
        if not self.data_is_set:
            return None
        return self.value

@dataclass
class Option(Parameter):
    value: str = ""

    enum: list = field(default_factory=list)
    enum_descriptions: list = field(default_factory=list)

    def __init__(self, param_json):
        super().__init__(param_json)
        self.enum = []
        self.enum_descriptions = []

    @classmethod
    def visit(cls, param_json):
        """
        Generates a node object from the provided JSON representation.

        :param param_json: The JSON representation of the node.
        :type param_json: dict
        :return: The generated node object.
        :rtype: Option
        """
        node = Option(param_json)
        if "options" in param_json.keys():
            for cont in param_json["options"]:
                node.enum.append(cont["value"])
                enum_des = cont["name"]
                if "description" in cont.keys():
                    enum_des += f". {cont['description']}"
                node.enum_descriptions.append(enum_des)
        else:
            pass
        return node

    @abstractmethod
    def parse_value(self, value: any) -> (ToolCallStatus, str):
        """
        Parses a value and returns the corresponding ToolCallStatus and a string message.
        
        Parameters:
            value (any): The value to be parsed.
        
        Returns:
            Tuple[ToolCallStatus, str]: A tuple containing the ToolCallStatus and a string message.
        """
        if type(value) == str:
            if value.startswith("\"") and value.endswith("\""):
                value = value[1:-1]
            if "," in value:
                return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} doesn't support multiple values (split by ',')"

            if value.startswith("="):
                if self.no_data_expression:
                    return ToolCallStatus.UnsupportedExpression, f"{self.get_parameter_name()} don't support expression"
                self.value = value
                self.data_is_set = True
                return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as expression" 
            else:
                if value not in self.enum:
                    return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} should in {self.enum}, found \"{value}\""
                self.value = value
                self.data_is_set = True
                return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as normal-string" 
        else:
            available_type = f"enum[str] in {self.enum}"
            return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} can only be parsed as {available_type}, got {json.dumps(value)}" 


    def to_description(self, prefix_ids, indent=2, max_depth=1):
        """
        Generate the function comment for the given function body in a markdown code block with the correct language syntax.

        Parameters:
            prefix_ids (str): The prefix IDs.
            indent (int): The number of spaces to indent each line of the comment. Defaults to 2.
            max_depth (int): The maximum depth of the comment. Defaults to 1.

        Returns:
            list: The lines of the function comment.

        Raises:
            None

        """
        all_name = self.get_parameter_name()
        lines = []
        line1 = f"{prefix_ids} {all_name}: enum[string]"

        if self.default != None:
            line1 += f" = \"{self.default}\""
        if self.display_string != "":
            if self.required:
                line1 += f", Required when ({self.display_string}), otherwise do not provide"
            else:
                line1 += f", Activate(Not Required) when ({self.display_string}), otherwise do not provide"
        else:
            if self.required:
                line1 += f", Required"

        line1 +=  f": {self.description} "
        if self.no_data_expression:
            line1 += f" You can't use expression."
        line1 += f". Available values:"
        lines.append(line1)
        for k, (enum,des) in enumerate(zip(self.enum, self.enum_descriptions)):
            lines.append(f"  {prefix_ids}.{k} value==\"{enum}\": {des}")
        
        lines = [" "*indent + line for line in lines]
        return lines
    
    def to_json(self):
        """
        Returns the JSON representation of the object.
        
        Returns:
            None: If the data is not set.
            Any: The JSON value of the object.
        """
        if not self.data_is_set:
            return None
        return self.value

@dataclass
class Collection(Parameter):
    meta: dict = field(default_factory=dict)
    value: dict = field(default_factory=list)

    def __init__(self, param_json):
        """
        Initializes the object with the given `param_json`.

        Parameters:
            param_json (dict): A dictionary containing the parameters for initialization.

        Returns:
            None
        """
        super().__init__(param_json)
        self.meta = {}
        self.value = []

    @classmethod
    def visit(cls, param_json):
        """
        Generates the node object from the given JSON representation.

        Args:
            param_json (dict): The JSON representation of the node.

        Returns:
            Collection: The generated node object.
        """
        node = Collection(param_json)
        if type(node.default) == dict and node.multiple_values:
            node.default = [node.default]
        if "options" in param_json.keys():
            for instance in param_json["options"]:
                name = instance["name"]
                sub_param = visit_parameter(instance)
                if sub_param != None:
                    node.meta[name] = sub_param
                    node.meta[name].parent = node
        else:
            assert False
            
        return node

    def parse_single_dict(self, value, list_count=False) -> (ToolCallStatus, str, dict):
        """
        Parses a single dictionary value.

        Args:
            value (dict): The dictionary value to parse.
            list_count (bool, optional): Indicates whether the dictionary value is part of a list. Defaults to False.

        Returns:
            tuple: A tuple containing the tool call status, a message, and a new dictionary.

        Raises:
            AssertionError: If the value is not of type dict.

        Example:
            parse_single_dict({"key": "value"}, list_count=True)
        """
        assert type(value) == dict, f"{value}"

        new_value = {}
        for key in value.keys():
            if key not in self.meta.keys():
                if list_count != -1:
                    param_name = f"{self.get_parameter_name()}[{list_count}]"
                else:
                    param_name = self.get_parameter_name()
                return ToolCallStatus.UndefinedParam, f"Undefined property \"{key}\" for {param_name}, supported properties: {list(self.meta.keys())}", {}
            right_value_subparam = deepcopy(self.meta[key])
            sub_param_status, sub_param_parse_result = right_value_subparam.parse_value(value[key])
            if sub_param_status != ToolCallStatus.ToolCallSuccess:
                return sub_param_status, sub_param_parse_result, {}
            new_value[key] = right_value_subparam
        return ToolCallStatus.ToolCallSuccess, "", new_value

    @abstractmethod
    def parse_value(self, value: any) -> (ToolCallStatus, str):
        """
        Parses the given value and returns the status code and result.

        Args:
            value (any): The value to be parsed.

        Returns:
            tuple: A tuple containing the tool call status code and the result string.
        """
        if type(value) == list:
            if not self.multiple_values:
                return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} can only be parsed as dict, got {json.dumps(value)}" 

            new_value = []
            for k, content in enumerate(value):
                status_code, result, output_result = self.parse_single_dict(content, list_count=k)
                if status_code != ToolCallStatus.ToolCallSuccess:
                    return status_code, result
                new_value.append(output_result)
            self.value = new_value
            self.data_is_set = True
            return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as list with {len(self.value)} items"

        elif type(value) == dict:

            if self.multiple_values:
                return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} can only be parsed as list[dict], got {json.dumps(value)}" 
            status_code, result, output_result = self.parse_single_dict(value, list_count = -1)
            if status_code != ToolCallStatus.ToolCallSuccess:
                return status_code, result
            self.value.append(output_result)
            self.data_is_set = True
            return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed as dict, got {json.dumps(value)}"

        elif type(value) == str:
            return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} doesn't support expression now" 
       
        else:
            if self.multiple_values:
                available_type = "list[dict]"
            else:
                available_type = "dict"
            return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} can only be parsed as {available_type}, got {type(value)}" 


    def to_description(self, prefix_ids, indent=2, max_depth=1):
        """
        Generates a description of the function, including its parameters and return types.

        Parameters:
            prefix_ids (str): The prefix for the parameter IDs.
            indent (int): The number of spaces to indent each line of the description. Defaults to 2.
            max_depth (int): The maximum depth to include in the description. Defaults to 1.

        Returns:
            list[str]: The lines of the function description.
        """
        all_name = self.get_parameter_name()
        lines = []
        if self.multiple_values:
            type_string = "list[dict]"
        else:
            type_string = "dict"
        line1 = f"{prefix_ids} {all_name}: {type_string}"

        if self.default != None:
            line1 += f" = {self.default}"
        if self.display_string != "":
            if self.required:
                line1 += f", Required when ({self.display_string}), otherwise do not provide"
            else:
                line1 += f", Activate(Not Required) when ({self.display_string}), otherwise do not provide"
        else:
            if self.required:
                line1 += f", Required"

        line1 +=  f": {self.description} "
        if self.no_data_expression:
            line1 += f" You can't use expression."
        line1 += f". properties description:"
        lines.append(" "*indent + line1)
        if self.get_depth() >= max_depth and self.required == False:
            lines.append(" "*indent+ "  ...hidden...")
        elif self.required:
            for k, (property_name, property) in enumerate(self.meta.items()):
                sublines = property.to_description(prefix_ids+f".{k}", indent=indent+2, max_depth=1000)
                lines.extend(sublines)
        else:
            for k, (property_name, property) in enumerate(self.meta.items()):
                sublines = property.to_description(prefix_ids+f".{k}", indent=indent+2, max_depth=max_depth)
                lines.extend(sublines)

        return lines
    
    def refresh(self):
        """
        Refreshes the data in the object.

        Sets `data_is_set` to `False`.
        Clears `value`.
        Calls the `refresh` method on each key in `meta`.

        Parameters:
            None

        Returns:
            None
        """
        self.data_is_set = False
        self.value.clear()
        for key in self.meta.keys():
            self.meta[key].refresh()

    def to_json(self):
        """
        Converts the object to a JSON representation.

        Returns:
            - If `data_is_set` is `False`, returns `None`.
            - If `multiple_values` is `True`, returns a list of dictionaries where each dictionary represents a key-value pair in the object's `value` attribute.
            - If `multiple_values` is `False`, returns a dictionary representing the key-value pairs in the first element of the object's `value` attribute.
        """
        if not self.data_is_set:
            return None
        
        if self.multiple_values:
            json_data = [{key: value.to_json() for key, value in data.items()} for data in self.value]
            return json_data
        else:
            json_data = {key: value.to_json() for key, value in self.value[0]}
        
        return json_data

    
@dataclass
class FixedCollection(Parameter):
    meta: dict = field(default_factory=dict)
    value: dict = field(default_factory=list)

    def __init__(self, param_json):
        """
        Initializes the class instance with the given `param_json`.

        Parameters:
            param_json (dict): A dictionary containing the parameters for initialization.
        
        Returns:
            None
        """
        super().__init__(param_json)
        self.meta = {}
        self.value = {}

    @classmethod
    def visit(cls, param_json):
        """
        Visits the given `param_json` and returns a `FixedCollection` node.

        Args:
            param_json (dict): The JSON parameter to visit.

        Returns:
            FixedCollection: The visited `FixedCollection` node.

        Raises:
            AssertionError: If `options` is not present in `param_json`.

        """
        node = FixedCollection(param_json)

        if "options" in param_json.keys():
            for instance in param_json["options"]:
                name = instance["name"]

                sub_node = Collection(instance)
                sub_node.param_type = ParameterType.COLLECTION
                sub_node.multiple_values = node.multiple_values


                if type(sub_node.default) == dict and sub_node.multiple_values:
                    sub_node.default = [sub_node.default]
                if "values" in instance.keys():
                    for sub_instance in instance["values"]:
                        subparam_key_name = sub_instance["name"]
                        sub_sub_param = visit_parameter(sub_instance)
                        if sub_sub_param != None:
                            sub_node.meta[subparam_key_name] = sub_sub_param
                            sub_node.meta[subparam_key_name].parent = sub_node
                else:
                    assert False
                
                node.meta[name] = sub_node
                node.meta[name].parent = node
        else:
            assert False
            
        return node

    def to_json(self):
        """
        Converts the object to a JSON representation.

        Returns:
            dict: A dictionary containing the JSON representation of the object.
                  If the object data is not set, returns None.
        """
        if not self.data_is_set:
            return None
        json_data = {}
        for key,value in self.value.items():
            sub_param = value.to_json()
            if sub_param != None:
                json_data[key] = sub_param
    
        return json_data

    @abstractmethod
    def parse_value(self, value: any) -> (ToolCallStatus, str):
        """
        Parses the given value and returns a tuple containing the status of the tool call and a message.

        Args:
            value (any): The value to be parsed.

        Returns:
            Tuple[ToolCallStatus, str]: A tuple containing the status of the tool call and a message.

        Raises:
            None

        Example:
            parse_value({"key": "value"}) -> (ToolCallStatus.ToolCallSuccess, "parameter parsed with keys: ['key']")
        """
        if type(value) == dict:
            new_value = {}
            for key in value.keys():
                if key not in self.meta.keys():
                    return ToolCallStatus.UndefinedParam, f"Undefined property \"{key}\" for {self.get_parameter_name()}, supported properties: {list(self.meta.keys())}"
                new_param = deepcopy(self.meta[key])
                subparam_status, subparam_data = new_param.parse_value(value=value[key])
                if subparam_status != ToolCallStatus.ToolCallSuccess:
                    return subparam_status, subparam_data
                new_value[key] = new_param
            self.data_is_set = True
            self.value = new_value
            return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed with keys: {list(self.value.keys())}"
        else:
            if self.multiple_values:
                available_type = "dict[str,list[dict[str,any]]]"
            else:
                available_type = "dict[str,dict[str,any]]"
            return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} can only be parsed as {available_type}, got {json.dumps(value)}" 


    def refresh(self):
        """
        Refreshes the data in the object.

        This function sets the `data_is_set` attribute to `False`, clears the `value` attribute, 
        and refreshes each key in the `meta` dictionary by calling the `refresh` method on each 
        corresponding value.

        Parameters:
            None

        Returns:
            None
        """
        self.data_is_set = False
        self.value.clear()
        for key in self.meta.keys():
            self.meta[key].refresh()

    def to_description(self, prefix_ids, indent=2, max_depth=1):
        """
        Generate the function comment for the given function body in a markdown code block with the correct language syntax.

        Args:
            prefix_ids (str): The prefix ids.
            indent (int, optional): The number of spaces to indent. Defaults to 2.
            max_depth (int, optional): The maximum depth. Defaults to 1.

        Returns:
            list[str]: The lines of the function comment.
        """
        all_name = self.get_parameter_name()
        lines = []
        if self.multiple_values:
            type_string = "dict[str,list[dict[str,any]]]"
        else:
            type_string = "dict[str,dict[str,any]]"
        line1 = f"{prefix_ids} {all_name}: {type_string}"

        if self.default != None:
            line1 += f" = {self.default}"
        if self.display_string != "":
            if self.required:
                line1 += f", Required when ({self.display_string}), otherwise do not provide"
            else:
                line1 += f", Activate(Not Required) when ({self.display_string}), otherwise do not provide"
        else:
            if self.required:
                line1 += f", Required"

        line1 +=  f": {self.description} "
        if self.no_data_expression:
            line1 += f" You can't use expression."
        line1 += f". properties description:"
        lines.append(" "*indent + line1)

        if self.get_depth() >= max_depth and self.required == False:
            lines.append(" "*indent+ "  ...hidden...")
        elif self.required:
            for k, (property_name, property) in enumerate(self.meta.items()):
                sublines = property.to_description(prefix_ids+f".{k}", indent=indent+2, max_depth=1000)
                lines.extend(sublines)
        else:
            for k, (property_name, property) in enumerate(self.meta.items()):
                sublines = property.to_description(prefix_ids+f".{k}", indent=indent+2, max_depth=max_depth)
                lines.extend(sublines)

        return lines


    
@dataclass
class ResourceLocator(Parameter):
    meta: dict = field(default_factory=dict)
    mode: str = ""
    value: any = None

    def __init__(self, param_json):
        """
        Initializes the class with the given `param_json`.

        Parameters:
            param_json (dict): A dictionary containing the parameters for initialization.

        Returns:
            None
        """
        super().__init__(param_json)
        self.meta = {}
        self.mode = ""
        self.value = None

    @classmethod
    def visit(cls, param_json):
        """
        Visits a parameter JSON and creates a node object.

        Args:
            param_json (dict): The parameter JSON to be visited.

        Returns:
            Node: The created node object.

        Raises:
            AssertionError: If the "modes" key is missing in the parameter JSON.

        """
        node = ResourceLocator(param_json)
        assert "modes" in param_json.keys()
        for instance in param_json["modes"]:
            name = instance["name"]
            result_node = visit_parameter(instance)
            if result_node != None:
                node.meta[name] = result_node
                node.meta[name].parent = node
    
        return node

    def refresh(self):
        self.data_is_set = False

    def to_description(self, prefix_ids, indent=2, max_depth=1):
        """
        Generate the function comment for the given function body.

        Parameters:
            prefix_ids (str): The prefix IDs.
            indent (int): The indentation level. Defaults to 2.
            max_depth (int): The maximum depth. Defaults to 1.

        Returns:
            list[str]: The lines of the function comment.
        """
        all_name = self.get_parameter_name()
        lines = []
        type_string = "dict{\"mode\":enum(str),\"values\":any}"
        line1 = f"{prefix_ids} {all_name}: {type_string}"

        if self.default != None:
            line1 += f" = {self.default}"
        if self.display_string != "":
            if self.required:
                line1 += f", Required when ({self.display_string}), otherwise do not provide"
            else:
                line1 += f", Activate(Not Required) when ({self.display_string}), otherwise do not provide"
        else:
            if self.required:
                line1 += f", Required"
    
        line1 +=  f": {self.description} "
        if self.no_data_expression:
            line1 += f" You can't use expression."
        line1 += f". \"mode\" should be one of {list(self.meta.keys())}: "
        lines.append(" "*indent + line1)


        if self.get_depth() >= max_depth and self.required == False:
            lines.append(" "*indent+ "  ...hidden...")
        elif self.required:
            for k, key in enumerate(self.meta.keys()):
                new_lines = self.meta[key].to_description(f"{prefix_ids}.{k}", indent=indent+2, max_depth=1000)
                lines.extend(new_lines)
        else:
            for k, key in enumerate(self.meta.keys()):
                new_lines = self.meta[key].to_description(f"{prefix_ids}.{k}", indent=indent+2, max_depth=max_depth)
                lines.extend(new_lines)

        return lines

    def to_json(self):
        """
        Convert the object to a JSON representation.
        
        Returns:
            dict: A dictionary containing the JSON representation of the object.
                  The dictionary has the following keys:
                  - "mode" (str): The mode of the object.
                  - "value" (dict): The JSON representation of the value attribute.
        
                  If the data is not set, returns None.
        """
        if not self.data_is_set:
            return None
        json_data = {
            "mode": self.mode,
            "value": self.value.to_json()
        }
        return json_data

    @abstractmethod
    def parse_value(self, value: any) -> (ToolCallStatus, str):
        """
        Parses the given value and returns a tuple containing the tool call status and a string message.

        Parameters:
            value (any): The value to be parsed.

        Returns:
            Tuple[ToolCallStatus, str]: A tuple containing the tool call status and a message.

        Raises:
            None
        """
        if type(value) == dict and (list(value.keys()) == ["mode","value"] or list(value.keys()) == ["value","mode"]):
            if value["mode"] not in self.meta.keys():
                return ToolCallStatus.UndefinedParam, f"Undefined mode \"{value['mode']}\" for {self.get_parameter_name()}, supported modes: {list(self.meta.keys())}"
            value_value = value["value"]
            temp_value = deepcopy(self.meta[value["mode"]])
            subparam_status, subparam_data = temp_value.parse_value(value=value_value)
            if subparam_status != ToolCallStatus.ToolCallSuccess:
                return subparam_status, subparam_data
            self.data_is_set = True
            self.mode = value["mode"]
            self.value = temp_value
            return ToolCallStatus.ToolCallSuccess, f"{self.get_parameter_name()} parsed with \"mode\"={self.mode}"
        else:
            available_type = "dict{\"mode\":str, \"value\":any}"
            return ToolCallStatus.ParamTypeError, f"{self.get_parameter_name()} can only be parsed as {available_type}, got {json.dumps(value)}"
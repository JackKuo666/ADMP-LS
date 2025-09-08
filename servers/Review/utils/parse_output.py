import json
from typing import Any, Callable

from pydantic import BaseModel


class OutputParserError(Exception):
    """
    Exception raised when the output parser fails to parse the output.
    """

    def __init__(self, message, output=None):
        self.message = message
        self.output = output
        super().__init__(self.message)

    def __str__(self):
        if self.output:
            return f"{self.message}\nProblematic output: {self.output}"
        return self.message


def find_json_in_string(string: str) -> str:
    """
    Method to extract all text in the left-most brace that appears in a string.
    Used to extract JSON from a string (note that this function does not validate the JSON).

    Example:
        string = "bla bla bla {this is {some} text{{}and it's sneaky}} because {it's} confusing"
        output = "{this is {some} text{{}and it's sneaky}}"
    """
    stack = 0
    start_index = None

    for i, c in enumerate(string):
        if c == "{":
            if stack == 0:
                start_index = i  # Start index of the first '{'
            stack += 1  # Push to stack
        elif c == "}":
            stack -= 1  # Pop stack
            if stack == 0:
                # Return the substring from the start of the first '{' to the current '}'
                return string[start_index : i + 1] if start_index is not None else ""

    # If no complete set of braces is found, return an empty string
    return ""


def parse_json_output(output: str) -> Any:
    """Take a string output and parse it as JSON"""
    # First try to load the string as JSON
    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        print(f"Failed to parse output as direct JSON: {e}")
        pass

    # If that fails, assume that the output is in a code block - remove the code block markers and try again
    parsed_output = output
    if "```" in parsed_output:
        try:
            parts = parsed_output.split("```")
            if len(parts) >= 3:
                parsed_output = parts[1]
                if parsed_output.startswith("json") or parsed_output.startswith("JSON"):
                    parsed_output = parsed_output[4:].strip()
                return json.loads(parsed_output)
        except (IndexError, json.JSONDecodeError) as e:
            print(f"Failed to parse output from code block: {e}")
            pass

    # As a last attempt, try to manually find the JSON object in the output and parse it
    parsed_output = find_json_in_string(output)
    if parsed_output:
        try:
            return json.loads(parsed_output)
        except json.JSONDecodeError as e:
            print(f"Failed to parse extracted JSON: {e}")
            # raise OutputParserError(f"Failed to parse output as JSON: {e}", output)
            raise ValueError("Failed to parse output as JSON")

    # If all fails, raise an error
    # raise OutputParserError("Failed to parse output as JSON", output)
    raise ValueError("Failed to parse output as JSON")


def create_type_parser(type: BaseModel) -> Callable[[str], BaseModel]:
    """Create a function that takes a string output and parses it as a specified Pydantic model"""

    def convert_json_string_to_type(output: str) -> BaseModel:
        """Take a string output and parse it as a Pydantic model"""
        output_dict = parse_json_output(output)
        return type.model_validate(output_dict)

    return convert_json_string_to_type

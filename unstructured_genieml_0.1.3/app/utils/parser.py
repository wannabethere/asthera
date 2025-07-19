import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger("MessageParser")


def parse_json_from_message(message: dict) -> Dict[str, Any]:
    """Parse JSON from the agent's output"""
    try:
        # Look for JSON object in the text
        json_match = re.search(r"\{.*\}", message, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            extracted_data = json.loads(json_str)
            logger.info("Successfully extracted metadata")
            return extracted_data
    except Exception as json_error:
        logger.warning("Error parsing JSON from output: %s", str(json_error))

    return None

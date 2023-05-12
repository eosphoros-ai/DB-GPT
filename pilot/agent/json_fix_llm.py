
import json
from typing import Any, Dict
import contextlib
from colorama import Fore
from regex import regex

from pilot.configs.config import Config
from pilot.logs import logger
from pilot.speech import say_text

from pilot.json_utils.json_fix_general import fix_invalid_escape,add_quotes_to_property_names,balance_braces

CFG = Config()

def fix_and_parse_json(
    json_to_load: str, try_to_fix_with_gpt: bool = True
) -> Dict[Any, Any]:
    """Fix and parse JSON string

    Args:
        json_to_load (str): The JSON string.
        try_to_fix_with_gpt (bool, optional): Try to fix the JSON with GPT.
            Defaults to True.

    Returns:
        str or dict[Any, Any]: The parsed JSON.
    """

    with contextlib.suppress(json.JSONDecodeError):
        json_to_load = json_to_load.replace("\t", "")
        return json.loads(json_to_load)

    with contextlib.suppress(json.JSONDecodeError):
        json_to_load = correct_json(json_to_load)
        return json.loads(json_to_load)
    # Let's do something manually:
    # sometimes GPT responds with something BEFORE the braces:
    # "I'm sorry, I don't understand. Please try again."
    # {"text": "I'm sorry, I don't understand. Please try again.",
    #  "confidence": 0.0}
    # So let's try to find the first brace and then parse the rest
    #  of the string
    try:
        brace_index = json_to_load.index("{")
        maybe_fixed_json = json_to_load[brace_index:]
        last_brace_index = maybe_fixed_json.rindex("}")
        maybe_fixed_json = maybe_fixed_json[: last_brace_index + 1]
        return json.loads(maybe_fixed_json)
    except (json.JSONDecodeError, ValueError) as e:
       logger.error("参数解析错误", e)


def fix_json_using_multiple_techniques(assistant_reply: str) -> Dict[Any, Any]:
    """Fix the given JSON string to make it parseable and fully compliant with two techniques.

    Args:
        json_string (str): The JSON string to fix.

    Returns:
        str: The fixed JSON string.
    """
    assistant_reply = assistant_reply.strip()
    if assistant_reply.startswith("```json"):
        assistant_reply = assistant_reply[7:]
    if assistant_reply.endswith("```"):
        assistant_reply = assistant_reply[:-3]
    try:
        return json.loads(assistant_reply)  # just check the validity
    except json.JSONDecodeError as e:  # noqa: E722
        print(f"JSONDecodeError: {e}")
        pass

    if assistant_reply.startswith("json "):
        assistant_reply = assistant_reply[5:]
        assistant_reply = assistant_reply.strip()
    try:
        return json.loads(assistant_reply)  # just check the validity
    except json.JSONDecodeError:  # noqa: E722
        pass

    # Parse and print Assistant response
    assistant_reply_json = fix_and_parse_json(assistant_reply)
    logger.debug("Assistant reply JSON: %s", str(assistant_reply_json))
    if assistant_reply_json == {}:
        assistant_reply_json = attempt_to_fix_json_by_finding_outermost_brackets(
            assistant_reply
        )

    logger.debug("Assistant reply JSON 2: %s", str(assistant_reply_json))
    if assistant_reply_json != {}:
        return assistant_reply_json

    logger.error(
        "Error: The following AI output couldn't be converted to a JSON:\n",
        assistant_reply,
    )
    if CFG.speak_mode:
        say_text("I have received an invalid JSON response from the OpenAI API.")

    return {}


def correct_json(json_to_load: str) -> str:
    """
    Correct common JSON errors.
    Args:
        json_to_load (str): The JSON string.
    """

    try:
        logger.debug("json", json_to_load)
        json.loads(json_to_load)
        return json_to_load
    except json.JSONDecodeError as e:
        logger.debug("json loads error", e)
        error_message = str(e)
        if error_message.startswith("Invalid \\escape"):
            json_to_load = fix_invalid_escape(json_to_load, error_message)
        if error_message.startswith(
            "Expecting property name enclosed in double quotes"
        ):
            json_to_load = add_quotes_to_property_names(json_to_load)
            try:
                json.loads(json_to_load)
                return json_to_load
            except json.JSONDecodeError as e:
                logger.debug("json loads error - add quotes", e)
                error_message = str(e)
        if balanced_str := balance_braces(json_to_load):
            return balanced_str
    return json_to_load


def attempt_to_fix_json_by_finding_outermost_brackets(json_string: str):
    if CFG.speak_mode and CFG.debug_mode:
        say_text(
            "I have received an invalid JSON response from the OpenAI API. "
            "Trying to fix it now."
        )
        logger.error("Attempting to fix JSON by finding outermost brackets\n")

    try:
        json_pattern = regex.compile(r"\{(?:[^{}]|(?R))*\}")
        json_match = json_pattern.search(json_string)

        if json_match:
            # Extract the valid JSON object from the string
            json_string = json_match.group(0)
            logger.typewriter_log(
                title="Apparently json was fixed.", title_color=Fore.GREEN
            )
            if CFG.speak_mode and CFG.debug_mode:
                say_text("Apparently json was fixed.")
        else:
            return {}

    except (json.JSONDecodeError, ValueError):
        if CFG.debug_mode:
            logger.error(f"Error: Invalid JSON: {json_string}\n")
        if CFG.speak_mode:
            say_text("Didn't work. I will have to ignore this response then.")
        logger.error("Error: Invalid JSON, setting it to empty JSON now.\n")
        json_string = {}

    return fix_and_parse_json(json_string)

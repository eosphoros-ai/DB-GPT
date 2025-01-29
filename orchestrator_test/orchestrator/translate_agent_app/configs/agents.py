from ..triage_instructions import triage_instructions
from ..configs.tools import *

from ..prompts.routines.language_translate.rules import LANGUAGE_TRANSLATE_RULE
from ..prompts.main_prompt import STARTER_PROMPT
from dbgpt.orhestrator.core import Agent

def transfer_to_language_translate():
    return language_translate

# def transfer_to_translate_judgement():
#     return translate_judgement

# def transfer_to_translate_modification():
#     return translate_modification



def transfer_to_triage():
    """Call this function when a user needs to be transferred to a different agent and a different rule.
    For instance, if a user is asking about a topic that is not handled by the current agent, call this function.
    """
    return triage_agent

# define the triage agent
triage_agent = Agent(
    name="Triage Agent",
    instructions=triage_instructions,
    functions=[
        transfer_to_language_translate
    ]
)

# # define the specific agent
# translate_modification = Agent(
#     name="Translate Modification Agent",
#     instructions="""You are a Multi-Language Translate Modification Agent for a customer service translation company.
#         You are an export customer service agent deciding which sub intent
#     """
# )

language_translate = Agent(
    name="Language translate",
    instructions=STARTER_PROMPT + LANGUAGE_TRANSLATE_RULE,
    functions=[
        escalte_to_agent,
        initiate_config,
        translate_judge,
        transfer_to_triage,
        short_translate,
        case_resolved,
    ]
)



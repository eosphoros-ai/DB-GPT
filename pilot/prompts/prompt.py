
from pilot.configs.config import Config
from pilot.prompts.generator import PromptGenerator


CFG = Config()

DEFAULT_TRIGGERING_PROMPT = (
    "Determine which next command to use, and respond using the format specified above"
)

DEFAULT_PROMPT_OHTER = (
    "Previous response was excellent. Please response according to the requirements based on the new goal"
)

def build_default_prompt_generator() -> PromptGenerator:
    """
    This function generates a prompt string that includes various constraints,
        commands, resources, and performance evaluations.

    Returns:
        str: The generated prompt string.
    """

    # Initialize the PromptGenerator object
    prompt_generator = PromptGenerator()

    # Add constraints to the PromptGenerator object
    # prompt_generator.add_constraint(
    #     "~4000 word limit for short term memory. Your short term memory is short, so"
    #     " immediately save important information to files."
    # )
    prompt_generator.add_constraint(
        "If you are unsure how you previously did something or want to recall past"
        " events, thinking about similar events will help you remember."
    )
    # prompt_generator.add_constraint("No user assistance")

    prompt_generator.add_constraint(
        'Only output one correct JSON response at a time'
    )
    prompt_generator.add_constraint(
        'Exclusively use the commands listed in double quotes e.g. "command name"'
    )
    prompt_generator.add_constraint(
        'If there is SQL in the args parameter, ensure to use the database and table definitions in  Schema, and ensure that the fields and table names are in the definition'
    )
    prompt_generator.add_constraint(
        'The generated command args need to comply with the definition of the command'
    )

    # Add resources to the PromptGenerator object
    # prompt_generator.add_resource(
    #     "Internet access for searches and information gathering."
    # )
    # prompt_generator.add_resource("Long Term memory management.")
    # prompt_generator.add_resource(
    #     "DB-GPT powered Agents for delegation of simple tasks."
    # )
    # prompt_generator.add_resource("File output.")

    # Add performance evaluations to the PromptGenerator object
    prompt_generator.add_performance_evaluation(
        "Continuously review and analyze your actions to ensure you are performing to"
        " the best of your abilities."
    )
    prompt_generator.add_performance_evaluation(
        "Constructively self-criticize your big-picture behavior constantly."
    )
    prompt_generator.add_performance_evaluation(
        "Reflect on past decisions and strategies to refine your approach."
    )
    # prompt_generator.add_performance_evaluation(
    #     "Every command has a cost, so be smart and efficient. Aim to complete tasks in"
    #     " the least number of steps."
    # )
    # prompt_generator.add_performance_evaluation("Write all code to a file.")
    return prompt_generator

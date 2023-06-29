from pilot.prompts.example_base import ExampleSelector

## Two examples are defined by default
EXAMPLES = [
    [{"system": "123"},{"system":"xxx"},{"human":"xxx"},{"assistant":"xxx"}],
    [{"system": "123"},{"system":"xxx"},{"human":"xxx"},{"assistant":"xxx"}]
]

plugin_example = ExampleSelector(examples_record=EXAMPLES, use_example=True)

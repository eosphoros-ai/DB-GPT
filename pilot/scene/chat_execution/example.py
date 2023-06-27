from pilot.prompts.example_base import ExampleSelector

## Two examples are defined by default
EXAMPLES = [
    [{"System": "123"}, {"System": "xxx"}, {"User": "xxx"}, {"Assistant": "xxx"}],
    [{"System": "123"}, {"System": "xxx"}, {"User": "xxx"}, {"Assistant": "xxx"}],
]

example = ExampleSelector(examples=EXAMPLES, use_example=True)

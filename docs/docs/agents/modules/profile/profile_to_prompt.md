# Profile To Prompt

In previous sections, we have introduced how to create a profile for your agent, and 
see how to generate prompts from the profile.

In this section, we will introduce more about how to generate prompts from the profile.

## What's The Prompt Template

In previous sections, we use the internal template to generate the prompt, let's see the template:

```python
from dbgpt.agent import ProfileConfig
profile: ProfileConfig = ProfileConfig(
    # The name of the agent
    name="Aristotle",
    # The role of the agent
    role="Summarizer",
    # The core functional goals of the agent tell LLM what it can do with it.
    goal=(
        "Summarize answer summaries based on user questions from provided "
        "resource information or from historical conversation memories."
    ),
    # Introduction and description of the agent, used for task assignment and display. 
    # If it is empty, the goal content will be used.
    desc=(
        "You can summarize provided text content according to user's questions"
        " and output the summarization."
    ),
)

real_profile = profile.create_profile()

print(f"System Prompt Template: \n{real_profile.get_system_prompt_template()}")
print("#" * 50)
print(f"User Prompt Template: \n{real_profile.get_user_prompt_template()}")
```

Running the above code will generate the following output:
```
System Prompt Template: 
You are a {{ role }}, {% if name %}named {{ name }}, {% endif %}your goal is {{ goal }}.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.
{% if resource_prompt %}{{ resource_prompt }} 
{% endif %}{% if expand_prompt %}{{ expand_prompt }} 
{% endif %}
*** IMPORTANT REMINDER ***
{% if language == 'zh' %}Please answer in simplified Chinese.
{% else %}Please answer in English.
{% endif %}
{% if constraints %}{% for constraint in constraints %}{{ loop.index }}. {{ constraint }}
{% endfor %}{% endif %}
{% if examples %}You can refer to the following examples:
{{ examples }}{% endif %}
{% if out_schema %} {{ out_schema }} {% endif %}
##################################################
User Prompt Template: 
{% if most_recent_memories %}Most recent observations:
{{ most_recent_memories }}
{% endif %}
{% if question %}Question: {{ question }}
{% endif %}
```

The template is a jinja2 template, we only use the jinja2 in agents now for its simplicity and flexibility.

## Use Your Custom Prompt Template

Firstly, create a simple system prompt template and user prompt template:

```python
my_system_prompt_template = """\
You are a {{ role }}, {% if name %}named {{ name }}, {% endif %}your goal is {{ goal }}.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
{% if language == 'zh' %}\
Please answer in simplified Chinese.
{% else %}\
Please answer in English.
{% endif %}\
"""  # noqa

my_user_prompt_template = "User question: {{ question }}"
```

Then, create a profile with the custom prompt template:

```python
from dbgpt.agent import ProfileConfig

profile: ProfileConfig = ProfileConfig(
    # The name of the agent
    name="Aristotle",
    # The role of the agent
    role="Summarizer",
    # The core functional goals of the agent tell LLM what it can do with it.
    goal=(
        "Summarize answer summaries based on user questions from provided "
        "resource information or from historical conversation memories."
    ),
    # Introduction and description of the agent, used for task assignment and display. 
    # If it is empty, the goal content will be used.
    desc=(
        "You can summarize provided text content according to user's questions"
        " and output the summarization."
    ),
    system_prompt_template=my_system_prompt_template,
    user_prompt_template=my_user_prompt_template,
)

real_profile = profile.create_profile()

system_prompt = real_profile.format_system_prompt(question="What can you do?")
user_prompt = real_profile.format_user_prompt(question="What can you do?")
print(f"System Prompt: \n{system_prompt}")
print("#" * 50)
print(f"User Prompt: \n{user_prompt}")
```

Running the above code will generate the following prompts:
```
System Prompt: 
You are a Summarizer, named Aristotle, your goal is Summarize answer summaries based on user questions from provided resource information or from historical conversation memories..
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.

##################################################
User Prompt: 
User question: What can you do?
```
# Dynamic Profile

In the previous sections, we have introduced how generate prompts from the profile.
In sometimes, you just want to modify a part of the profile in a simple way, here we 
introduce how to create a dynamic profile.

## Dynamic Fields Of Profile

Here we use `DynConfig` to create a dynamic profile, you can modify the fields of the original profile.

Create a python file named `profile_dynamic.py` and add the following code:

```python
from dbgpt.agent import ProfileConfig, DynConfig

profile: ProfileConfig = ProfileConfig(
    # The name of the agent
    name=DynConfig(
        "Aristotle",
       key="summary_profile_name",
       provider="env"
    ),
    # The role of the agent
    role="Summarizer",
)
```
In the above example, we use `DynConfig` to create a dynamic profile field "name", the 
default value is "Aristotle", and the key is "summary_profile_name", the provider is "env", 
`provider="env"` means the value of the field will be read from the environment variable

Then, you can create a profile from the configuration and generate the prompt.

```python
real_profile = profile.create_profile()
system_prompt = real_profile.format_system_prompt(question="What can you do?")
user_prompt = real_profile.format_user_prompt(question="What can you do?")
print(f"System Prompt: \n{system_prompt}")
print("#" * 50)
print(f"User Prompt: \n{user_prompt}")
```

Running the above code without setting the environment variable:
```bash
python profile_dynamic.py
```

The output will be:
```
System Prompt: 
You are a Summarizer, named Aristotle, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.




##################################################
User Prompt: 

Question: What can you do?
```

Running the above code with setting the environment variable:
```bash
summary_profile_name="Plato" python profile_dynamic.py
```

The output will be:
```
System Prompt: 
You are a Summarizer, named Plato, your goal is None.
Please think step by step to achieve the goal. You can use the resources given below. 
At the same time, please strictly abide by the constraints and specifications in IMPORTANT REMINDER.

*** IMPORTANT REMINDER ***
Please answer in English.




##################################################
User Prompt: 

Question: What can you do?
```
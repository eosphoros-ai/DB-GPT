# Profile Creation

In this section, you will learn more about creating a profile for your agent.

## Method 1: Using the ProfileConfig Class

As mentioned in the [Profile](profile.md) section, the `ProfileConfig` class is used to 
define the profile of the agent. It is a simple way to define the agent's profile. 

Formally, the `ProfileConfig` class supports the following parameters:
- `name`: The name of the agent.
- `role`: What is the role of the agent.
- `goal`: The core functional goals of the agent tell LLM what it can do with it.
- `desc`: Introduction and description of the agent, used for task assignment and display. If it is empty, the goal content will be used.
- `constraints`: It can contain multiple constraints and reasoning restriction logic
- `expand_prompt`: A expand content to add to the prompt, you can pass some custom text to be added to the prompt.
- `examples`: Some examples in your prompt

This is a full example of creating a profile using the `ProfileConfig` class:

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
    # Constraints of the agent
    constraints=[
        "Prioritize the summary of answers to user questions from the improved "
        "resource text. If no relevant information is found, summarize it from "
        "the historical dialogue memory given. It is forbidden to make up your "
        "own.",
        "You need to first detect user's question that you need to answer with "
        "your summarization.",
        "Extract the provided text content used for summarization.",
        "Then you need to summarize the extracted text content.",
        "Output the content of summarization ONLY related to user's question. "
        "The output language must be the same to user's question language.",
        "If you think the provided text content is not related to user "
        "questions at all, ONLY output 'Did not find the information you "
        "want.'!!.",
    ],
    # Introduction and description of the agent, used for task assignment and display.
    # If it is empty, the goal content will be used.
    desc=(
        "You can summarize provided text content according to user's questions"
        " and output the summarization."
    ),
    expand_prompt="Keep your answer concise",
    # Some examples in your prompt
    examples=""
)
```
In the above example, we can see 'constraints' and 'expand_prompt' added to the profile.

Let's see the final prompt generated from a profile.

```python
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
Keep your answer concise 

*** IMPORTANT REMINDER ***
Please answer in English.

1. Prioritize the summary of answers to user questions from the improved resource text. If no relevant information is found, summarize it from the historical dialogue memory given. It is forbidden to make up your own.
2. You need to first detect user's question that you need to answer with your summarization.
3. Extract the provided text content used for summarization.
4. Then you need to summarize the extracted text content.
5. Output the content of summarization ONLY related to user's question. The output language must be the same to user's question language.
6. If you think the provided text content is not related to user questions at all, ONLY output 'Did not find the information you want.'!!.



##################################################
User Prompt: 

Question: What can you do?
```

## Method 2: Using `ProfileFactory`

It is a more flexible way to create a profile using the `ProfileFactory`.


### Create a Profile Factory

```python
from typing import Optional
from dbgpt.agent import ProfileFactory, Profile, DefaultProfile

class MyProfileFactory(ProfileFactory):
    def create_profile(
        self,
        profile_id: int,
        name: Optional[str] = None,
        role: Optional[str] = None,
        goal: Optional[str] = None,
        prefer_prompt_language: Optional[str] = None,
        prefer_model: Optional[str] = None,
    ) -> Optional[Profile]:
        return DefaultProfile(
            name="Aristotle",
            role="Summarizer",
            goal=(
                "Summarize answer summaries based on user questions from provided "
                "resource information or from historical conversation memories."
            ),
            desc=(
                "You can summarize provided text content according to user's questions"
                " and output the summarization."
            ),
            expand_prompt="Keep your answer concise",
            examples=""
        )
```

### Use the Profile Factory

For using the profile factory, you need to pass the factory to the `ProfileConfig` class.
You don't need to provide the name, role, goal, and description of the agent in this case.

```python
from dbgpt.agent import ProfileConfig

profile: ProfileConfig = ProfileConfig(
    factory=MyProfileFactory(),
)
```
Let's see the final prompt generated from a profile.

```python
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
Keep your answer concise 

*** IMPORTANT REMINDER ***
Please answer in English.




##################################################
User Prompt: 

Question: What can you do?
```

## Summary

In this section, you learned how to create a profile for your agent using the 
`ProfileConfig` class and `ProfileFactory`.
It is flexible and easy to define the agent's profile using these methods, especially 
when you need to create thousands of agent scenarios.
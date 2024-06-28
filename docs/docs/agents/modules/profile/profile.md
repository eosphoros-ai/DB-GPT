# Profiling Module

> Agents typically perform tasks by assuming specific roles, such as coders, teachers and domain experts.
The profiling module aims to indicate the profiles of the agent roles, which are usually 
written into the prompt to influence the LLM behaviors. Agent profiles typically encompass 
basic information such as age, gender, and career, as well as psychology information, 
reflecting the personalities of the agent, and social information, detailing the relationships between agents.
>
> The choice of information to profile the agent is largely determined by the specific application scenarios. 
For instance, if the application aims to study human cognitive process, then the psychology information becomes pivotal.


## Profiles In DB-GPT Agents

Profiles are essential for agents in DB-GPT, as they are used to influence the agent's behaviors.

You have already seen a basic example of a profile in the [Write Your Custom Agent](../../introduction/custom_agents.md) section.

```python
from dbgpt.agent import ConversableAgent, ProfileConfig

class MySummarizerAgent(ConversableAgent):
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
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

In the above example, the `ProfileConfig` class is used to define the profile of the agent.
It is a simple way to define the agent's profile, you just need to provide the name, role, goal, and description of the agent.

Let's see the final prompt generated from a profile.
First, let's create a profile configuration separately.

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

# Create a profile from the configuration
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

Question: What can you do?
```
As you can see, the profile is used to generate the system and user prompts, they will 
be passed to the LLM to generate the response.

So, you can easily see the real prompt generated from the profile, this is very useful 
in debugging and understanding the agent's behavior, we don't hide too much details from you.


## What Next?
- How many ways can you create a profile for an agent? [Learn more](./profile_creation.md)
- How is profile converted to LLM prompt? [Learn more](./profile_to_prompt.md)
# Write Your Custom Agent

## Introduction

In this example, we will show you how to create a custom agent that can be used as a 
summarizer.

## Installations

Install the required packages by running the following command:

```bash
pip install "dbgpt[agent]>=0.5.4rc0" -U
pip install openai
```

## Create a Custom Agent

### Initialize The Agent

In most cases, you just need to inherit basic agents and override the corresponding
methods.

```python
from dbgpt.agent import ConversableAgent

class MySummarizerAgent(ConversableAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

### Define the profile

Before designing each Agent, it is necessary to define its role, identity, and 
functional role. The specific definitions are as follows:

```python
from dbgpt.agent import ConversableAgent

class MySummarizerAgent(ConversableAgent):
    # The name of the agent
    name = "Aristotle"
    # The profile of the agent
    profile: str = "Summarizer"
    # The core functional goals of the agent tell LLM what it can do with it.
    goal: str = (
        "Summarize answer summaries based on user questions from provided "
        "resource information or from historical conversation memories."
    ) 
    # Introduction and description of the agent, used for task assignment and display. 
    # If it is empty, the goal content will be used.
    desc: str = (
        "You can summarize provided text content according to user's questions"
        " and output the summarization."
    )
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

### Supplementary Prompt Constraints

Agent's prompt is assembled using a fixed template by default(an external template can 
be bound if there are some special requirements). which mainly includes:
1. Identity definition(automatically constructed)
2. Resource information(automatically constructed)
3. Constraint logic
4. Reference case (optional)
5. Output format templates and constraints (automatically constructed)

So, we can define the constraints of the agent's prompt as follows:

```python
from dbgpt.agent import ConversableAgent

class MySummarizerAgent(ConversableAgent):
    # The name of the agent
    name = "Aristotle"
    # The profile of the agent
    profile: str = "Summarizer"
    # The core functional goals of the agent tell LLM what it can do with it.
    goal: str = (
        "Summarize answer summaries based on user questions from provided "
        "resource information or from historical conversation memories."
    ) 
    # Introduction and description of the agent, used for task assignment and display. 
    # If it is empty, the goal content will be used.
    desc: str = (
        "You can summarize provided text content according to user's questions"
        " and output the summarization."
    )
    # Refer to the following. It can contain multiple constraints and reasoning 
    # restriction logic, and supports the use of parameter template {param_name}.
    constraints: list[str] = [
        "Prioritize the summary of answers to user questions from the improved resource"
        " text. If no relevant information is found, summarize it from the historical "
        "dialogue memory given. It is forbidden to make up your own.",
        "You need to first detect user's question that you need to answer with your"
        " summarization.",
        "Extract the provided text content used for summarization.",
        "Then you need to summarize the extracted text content.",
        "Output the content of summarization ONLY related to user's question. The "
        "output language must be the same to user's question language.",
        "If you think the provided text content is not related to user questions at "
        "all, ONLY output '{not_related_message}'!!.",
    ]
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
```

### Prompt Template Format

If dynamic parameters are used in the prompt, the actual dialogue process is required 
to assemble the values, and the following interface (`_init_reply_message`) needs to be 
overloaded and implemented:

```python
from dbgpt.agent import ConversableAgent, AgentMessage

NOT_RELATED_MESSAGE = "Did not find the information you want."

class MySummarizerAgent(ConversableAgent):
    # The name of the agent
    name = "Aristotle"
    # The profile of the agent
    profile: str = "Summarizer"
    # The core functional goals of the agent tell LLM what it can do with it.
    goal: str = (
        "Summarize answer summaries based on user questions from provided "
        "resource information or from historical conversation memories."
    ) 
    # Introduction and description of the agent, used for task assignment and display. 
    # If it is empty, the goal content will be used.
    desc: str = (
        "You can summarize provided text content according to user's questions"
        " and output the summarization."
    )
    # Refer to the following. It can contain multiple constraints and reasoning 
    # restriction logic, and supports the use of parameter template {param_name}.
    constraints: list[str] = [
        "Prioritize the summary of answers to user questions from the improved resource"
        " text. If no relevant information is found, summarize it from the historical "
        "dialogue memory given. It is forbidden to make up your own.",
        "You need to first detect user's question that you need to answer with your"
        " summarization.",
        "Extract the provided text content used for summarization.",
        "Then you need to summarize the extracted text content.",
        "Output the content of summarization ONLY related to user's question. The "
        "output language must be the same to user's question language.",
        "If you think the provided text content is not related to user questions at "
        "all, ONLY output '{not_related_message}'!!.",
    ]
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _init_reply_message(self, received_message: AgentMessage) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message)
        # Fill in the dynamic parameters in the prompt template
        reply_message.context = {
            "not_related_message": NOT_RELATED_MESSAGE
        }
        return reply_message
```

### Resource Preloading (Optional)

If there are some specific resources, the bound resources must be loaded in advance 
when the agent is initialized. You can refer to the following implementation. 
It is determined based on the actual situation of the resources. In most cases, it is 
not necessary.

```python
from dbgpt.agent import ConversableAgent, AgentMessage

class MySummarizerAgent(ConversableAgent):
    # ... other code
    async def preload_resource(self) -> None:
        # Load the required resources
        for resource in self.resources:
            # Load your resource, please write your own code here
            pass
```

### Result Checking (Optional)

If the action execution results need to be strictly verified and verified, there are 
two modes: code logic verification and LLM verification. Of course, verification is not 
necessary and the default pass is not implemented. Here is an example using LL verification:

```python

from typing import Tuple, Optional

from dbgpt.agent import ConversableAgent, AgentMessage
from dbgpt.core import ModelMessageRoleType

CHECK_RESULT_SYSTEM_MESSAGE = (
    "You are an expert in analyzing the results of a summary task."
    "Your responsibility is to check whether the summary results can summarize the "
    "input provided by the user, and then make a judgment. You need to answer "
    "according to the following rules:\n"
    "    Rule 1: If you think the summary results can summarize the input provided"
    " by the user, only return True.\n"
    "    Rule 2: If you think the summary results can NOT summarize the input "
    "provided by the user, return False and the reason, split by | and ended "
    "by TERMINATE. For instance: False|Some important concepts in the input are "
    "not summarized. TERMINATE"
)

class MySummarizerAgent(ConversableAgent):
    # ... other code
    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        current_goal = message.current_goal
        action_report = message.action_report
        task_result = ""
        if action_report:
            task_result = action_report.get("content", "")

        check_result, model = await self.thinking(
            messages=[
                AgentMessage(
                    role=ModelMessageRoleType.HUMAN,
                    content=(
                        "Please understand the following user input and summary results"
                        " and give your judgment:\n"
                        f"User Input: {current_goal}\n"
                        f"Summary Results: {task_result}"
                    ),
                )
            ],
            prompt=CHECK_RESULT_SYSTEM_MESSAGE,
        )
        
        fail_reason = ""
        if check_result and (
            "true" in check_result.lower() or "yes" in check_result.lower()
        ):
            success = True
        else:
            success = False
            try:
                _, fail_reason = check_result.split("|")
                fail_reason = (
                    "The summary results cannot summarize the user input due"
                    f" to: {fail_reason}. Please re-understand and complete the summary"
                    " task."
                )
            except Exception:
                fail_reason = (
                    "The summary results cannot summarize the user input. "
                    "Please re-understand and complete the summary task."
                )
        return success, fail_reason
```

## Create A Custom Action

### Initialize The Action

All Agent's operations on the external environment and the real world are implemented 
through `Action`. Action defines the Agent's output content structure and actually 
performs the corresponding operations. The specific `Action` implementation inherits 
the `Action` base class, as follows:

```python
from typing import Optional
from pydantic import BaseModel, Field
from dbgpt.vis import Vis
from dbgpt.agent import Action, ActionOutput, AgentResource, ResourceType
from dbgpt.agent.util import cmp_string_equal

NOT_RELATED_MESSAGE = "Did not find the information you want."

# The parameter object that the Action that the current Agent needs to execute needs to output.
class SummaryActionInput(BaseModel):
    summary: str = Field(
        ...,
        description="The summary content",
    )

class SummaryAction(Action[SummaryActionInput]):
    def __init__(self):
        super().__init__()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        # The resource type that the current Agent needs to use
        # here we do not need to use resources, just return None
        return None
    
    @property
    def render_protocol(self) -> Optional[Vis]:
        # The visualization rendering protocol that the current Agent needs to use
        # here we do not need to use visualization rendering, just return None
        return None
    
    @property
    def out_model_type(self):
        return SummaryActionInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action.
        
        The entry point for actual execution of Action. Action execution will be 
        automatically initiated after model inference. 
        """
        try:
            # Parse the input message
            param: SummaryActionInput = self._input_convert(ai_message, SummaryActionInput)
        except Exception:
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found, "
                f"ai message: {ai_message}",
            )
        # Check if the summary content is not related to user questions
        if param.summary and cmp_string_equal(
            param.summary, 
            NOT_RELATED_MESSAGE,
            ignore_case=True,
            ignore_punctuation=True,
            ignore_whitespace=True,
        ):
            return ActionOutput(
                is_exe_success=False,
                content="the provided text content is not related to user questions at all."
                f"ai message: {ai_message}",
            )
        else:
            return ActionOutput(
                is_exe_success=True,
                content=param.summary,
            )
```

### Binding Action to Agent

After the development and definition of agent and cction are completed, 
bind the action to the corresponding agent.

```python
from pydantic import BaseModel
from dbgpt.agent import Action,ConversableAgent

class SummaryActionInput(BaseModel):
    ...

class SummaryAction(Action[SummaryActionInput]):
    ...

class MySummarizerAgent(ConversableAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([SummaryAction])
```

### Action Extended Parameter Processing

```python
from typing import Optional, Dict, Any
from pydantic import BaseModel
from dbgpt.agent import Action, ActionOutput, AgentResource, ConversableAgent


class SummaryActionInput(BaseModel):
    ...

class SummaryAction(Action[SummaryActionInput]):
    ...

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        # Read the extended parameters passed in by the agent
        extra_param = kwargs.get("action_extra_param_key", None)
        pass
    
class MySummarizerAgent(ConversableAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([SummaryAction])
    
    def prepare_act_param(self) -> Dict[str, Any]:
        return {"action_extra_param_key": "this is extra param"}
```

## Use Your Custom Agent

After the custom agent is created, you can use it in the following way:

```python

import asyncio

from dbgpt.agent import AgentContext, ConversableAgent, GptsMemory, LLMConfig, UserProxyAgent
from dbgpt.model.proxy import OpenAILLMClient

class MySummarizerAgent(ConversableAgent):
    ...

async def main():
    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="summarize")

    default_memory: GptsMemory = GptsMemory()

    summarizer = (
        await MySummarizerAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(default_memory)
        .build()
    )

    user_proxy = await UserProxyAgent().bind(default_memory).bind(context).build()
  

    await user_proxy.initiate_chat(
        recipient=summarizer,
        reviewer=user_proxy,
        message="""I want to summarize advantages of Nuclear Power according to the following content.
            Nuclear power in space is the use of nuclear power in outer space, typically either small fission systems or radioactive decay for electricity or heat. Another use is for scientific observation, as in a Mössbauer spectrometer. The most common type is a radioisotope thermoelectric generator, which has been used on many space probes and on crewed lunar missions. Small fission reactors for Earth observation satellites, such as the TOPAZ nuclear reactor, have also been flown.[1] A radioisotope heater unit is powered by radioactive decay and can keep components from becoming too cold to function, potentially over a span of decades.[2]
            The United States tested the SNAP-10A nuclear reactor in space for 43 days in 1965,[3] with the next test of a nuclear reactor power system intended for space use occurring on 13 September 2012 with the Demonstration Using Flattop Fission (DUFF) test of the Kilopower reactor.[4]
            After a ground-based test of the experimental 1965 Romashka reactor, which used uranium and direct thermoelectric conversion to electricity,[5] the USSR sent about 40 nuclear-electric satellites into space, mostly powered by the BES-5 reactor. The more powerful TOPAZ-II reactor produced 10 kilowatts of electricity.[3]
            Examples of concepts that use nuclear power for space propulsion systems include the nuclear electric rocket (nuclear powered ion thruster(s)), the radioisotope rocket, and radioisotope electric propulsion (REP).[6] One of the more explored concepts is the nuclear thermal rocket, which was ground tested in the NERVA program. Nuclear pulse propulsion was the subject of Project Orion.[7]
            Regulation and hazard prevention[edit]
            After the ban of nuclear weapons in space by the Outer Space Treaty in 1967, nuclear power has been discussed at least since 1972 as a sensitive issue by states.[8] Particularly its potential hazards to Earth's environment and thus also humans has prompted states to adopt in the U.N. General Assembly the Principles Relevant to the Use of Nuclear Power Sources in Outer Space (1992), particularly introducing safety principles for launches and to manage their traffic.[8]
            Benefits
            Both the Viking 1 and Viking 2 landers used RTGs for power on the surface of Mars. (Viking launch vehicle pictured)
            While solar power is much more commonly used, nuclear power can offer advantages in some areas. Solar cells, although efficient, can only supply energy to spacecraft in orbits where the solar flux is sufficiently high, such as low Earth orbit and interplanetary destinations close enough to the Sun. Unlike solar cells, nuclear power systems function independently of sunlight, which is necessary for deep space exploration. Nuclear-based systems can have less mass than solar cells of equivalent power, allowing more compact spacecraft that are easier to orient and direct in space. In the case of crewed spaceflight, nuclear power concepts that can power both life support and propulsion systems may reduce both cost and flight time.[9]
            Selected applications and/or technologies for space include:
            Radioisotope thermoelectric generator
            Radioisotope heater unit
            Radioisotope piezoelectric generator
            Radioisotope rocket
            Nuclear thermal rocket
            Nuclear pulse propulsion
            Nuclear electric rocket
            """,
    )
    print(await default_memory.one_chat_completions("summarize"))

if __name__ == "__main__":
    asyncio.run(main())
```

Full code as follows:

```python
import asyncio
from typing import Any, Dict, Optional, Tuple

from dbgpt.agent import (
    Action,
    ActionOutput,
    AgentContext,
    AgentMessage,
    AgentResource,
    ConversableAgent,
    GptsMemory,
    LLMConfig,
    ResourceType,
    UserProxyAgent,
)
from dbgpt.agent.util import cmp_string_equal
from dbgpt.core import ModelMessageRoleType
from dbgpt.model.proxy import OpenAILLMClient
from dbgpt.vis import Vis
from pydantic import BaseModel, Field


NOT_RELATED_MESSAGE = "Did not find the information you want."

CHECK_RESULT_SYSTEM_MESSAGE = (
    "You are an expert in analyzing the results of a summary task."
    "Your responsibility is to check whether the summary results can summarize the "
    "input provided by the user, and then make a judgment. You need to answer "
    "according to the following rules:\n"
    "    Rule 1: If you think the summary results can summarize the input provided"
    " by the user, only return True.\n"
    "    Rule 2: If you think the summary results can NOT summarize the input "
    "provided by the user, return False and the reason, split by | and ended "
    "by TERMINATE. For instance: False|Some important concepts in the input are "
    "not summarized. TERMINATE"
)
class MySummarizerAgent(ConversableAgent):
    # The name of the agent
    name = "Aristotle"
    # The profile of the agent
    profile: str = "Summarizer"
    # The core functional goals of the agent tell LLM what it can do with it.
    goal: str = (
        "Summarize answer summaries based on user questions from provided "
        "resource information or from historical conversation memories."
    ) 
    # Introduction and description of the agent, used for task assignment and display. 
    # If it is empty, the goal content will be used.
    desc: str = (
        "You can summarize provided text content according to user's questions"
        " and output the summarization."
    )
    # Refer to the following. It can contain multiple constraints and reasoning 
    # restriction logic, and supports the use of parameter template {param_name}.
    constraints: list[str] = [
        "Prioritize the summary of answers to user questions from the improved resource"
        " text. If no relevant information is found, summarize it from the historical "
        "dialogue memory given. It is forbidden to make up your own.",
        "You need to first detect user's question that you need to answer with your"
        " summarization.",
        "Extract the provided text content used for summarization.",
        "Then you need to summarize the extracted text content.",
        "Output the content of summarization ONLY related to user's question. The "
        "output language must be the same to user's question language.",
        "If you think the provided text content is not related to user questions at "
        "all, ONLY output '{not_related_message}'!!.",
    ]
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([SummaryAction])

    def _init_reply_message(self, received_message: AgentMessage) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message)
        # Fill in the dynamic parameters in the prompt template
        reply_message.context = {
            "not_related_message": NOT_RELATED_MESSAGE
        }
        return reply_message
    
    def prepare_act_param(self) -> Dict[str, Any]:
        return {"action_extra_param_key": "this is extra param"}

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        current_goal = message.current_goal
        action_report = message.action_report
        task_result = ""
        if action_report:
            task_result = action_report.get("content", "")

        check_result, model = await self.thinking(
            messages=[
                AgentMessage(
                    role=ModelMessageRoleType.HUMAN,
                    content=(
                        "Please understand the following user input and summary results"
                        " and give your judgment:\n"
                        f"User Input: {current_goal}\n"
                        f"Summary Results: {task_result}"
                    ),
                )
            ],
            prompt=CHECK_RESULT_SYSTEM_MESSAGE,
        )
        
        fail_reason = ""
        if check_result and (
            "true" in check_result.lower() or "yes" in check_result.lower()
        ):
            success = True
        else:
            success = False
            try:
                _, fail_reason = check_result.split("|")
                fail_reason = (
                    "The summary results cannot summarize the user input due"
                    f" to: {fail_reason}. Please re-understand and complete the summary"
                    " task."
                )
            except Exception:
                fail_reason = (
                    "The summary results cannot summarize the user input. "
                    "Please re-understand and complete the summary task."
                )
        return success, fail_reason


# The parameter object that the Action that the current Agent needs to execute needs to output.
class SummaryActionInput(BaseModel):
    summary: str = Field(
        ...,
        description="The summary content",
    )

class SummaryAction(Action[SummaryActionInput]):
    def __init__(self):
        super().__init__()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        # The resource type that the current Agent needs to use
        # here we do not need to use resources, just return None
        return None
    
    @property
    def render_protocol(self) -> Optional[Vis]:
        # The visualization rendering protocol that the current Agent needs to use
        # here we do not need to use visualization rendering, just return None
        return None
    
    @property
    def out_model_type(self):
        return SummaryActionInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action.
        
        The entry point for actual execution of Action. Action execution will be 
        automatically initiated after model inference. 
        """
        extra_param = kwargs.get("action_extra_param_key", None)
        try:
            # Parse the input message
            param: SummaryActionInput = self._input_convert(ai_message, SummaryActionInput)
        except Exception:
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found, "
                f"ai message: {ai_message}",
            )
        # Check if the summary content is not related to user questions
        if param.summary and cmp_string_equal(
            param.summary, 
            NOT_RELATED_MESSAGE,
            ignore_case=True,
            ignore_punctuation=True,
            ignore_whitespace=True,
        ):
            return ActionOutput(
                is_exe_success=False,
                content="the provided text content is not related to user questions at all."
                f"ai message: {ai_message}",
            )
        else:
            return ActionOutput(
                is_exe_success=True,
                content=param.summary,
            )


async def main():
    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="summarize")

    default_memory: GptsMemory = GptsMemory()

    summarizer = (
        await MySummarizerAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(default_memory)
        .build()
    )

    user_proxy = await UserProxyAgent().bind(default_memory).bind(context).build()
  

    await user_proxy.initiate_chat(
        recipient=summarizer,
        reviewer=user_proxy,
        message="""I want to summarize advantages of Nuclear Power according to the following content.
            Nuclear power in space is the use of nuclear power in outer space, typically either small fission systems or radioactive decay for electricity or heat. Another use is for scientific observation, as in a Mössbauer spectrometer. The most common type is a radioisotope thermoelectric generator, which has been used on many space probes and on crewed lunar missions. Small fission reactors for Earth observation satellites, such as the TOPAZ nuclear reactor, have also been flown.[1] A radioisotope heater unit is powered by radioactive decay and can keep components from becoming too cold to function, potentially over a span of decades.[2]
            The United States tested the SNAP-10A nuclear reactor in space for 43 days in 1965,[3] with the next test of a nuclear reactor power system intended for space use occurring on 13 September 2012 with the Demonstration Using Flattop Fission (DUFF) test of the Kilopower reactor.[4]
            After a ground-based test of the experimental 1965 Romashka reactor, which used uranium and direct thermoelectric conversion to electricity,[5] the USSR sent about 40 nuclear-electric satellites into space, mostly powered by the BES-5 reactor. The more powerful TOPAZ-II reactor produced 10 kilowatts of electricity.[3]
            Examples of concepts that use nuclear power for space propulsion systems include the nuclear electric rocket (nuclear powered ion thruster(s)), the radioisotope rocket, and radioisotope electric propulsion (REP).[6] One of the more explored concepts is the nuclear thermal rocket, which was ground tested in the NERVA program. Nuclear pulse propulsion was the subject of Project Orion.[7]
            Regulation and hazard prevention[edit]
            After the ban of nuclear weapons in space by the Outer Space Treaty in 1967, nuclear power has been discussed at least since 1972 as a sensitive issue by states.[8] Particularly its potential hazards to Earth's environment and thus also humans has prompted states to adopt in the U.N. General Assembly the Principles Relevant to the Use of Nuclear Power Sources in Outer Space (1992), particularly introducing safety principles for launches and to manage their traffic.[8]
            Benefits
            Both the Viking 1 and Viking 2 landers used RTGs for power on the surface of Mars. (Viking launch vehicle pictured)
            While solar power is much more commonly used, nuclear power can offer advantages in some areas. Solar cells, although efficient, can only supply energy to spacecraft in orbits where the solar flux is sufficiently high, such as low Earth orbit and interplanetary destinations close enough to the Sun. Unlike solar cells, nuclear power systems function independently of sunlight, which is necessary for deep space exploration. Nuclear-based systems can have less mass than solar cells of equivalent power, allowing more compact spacecraft that are easier to orient and direct in space. In the case of crewed spaceflight, nuclear power concepts that can power both life support and propulsion systems may reduce both cost and flight time.[9]
            Selected applications and/or technologies for space include:
            Radioisotope thermoelectric generator
            Radioisotope heater unit
            Radioisotope piezoelectric generator
            Radioisotope rocket
            Nuclear thermal rocket
            Nuclear pulse propulsion
            Nuclear electric rocket
            """,
    )
    print(await default_memory.one_chat_completions("summarize"))

if __name__ == "__main__":
    asyncio.run(main())
```
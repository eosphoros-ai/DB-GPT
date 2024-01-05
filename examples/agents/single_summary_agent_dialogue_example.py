"""Agents: single agents about CodeAssistantAgent?

    Examples:
     
        Execute the following command in the terminal:
        Set env params.
        .. code-block:: shell

            export OPENAI_API_KEY=sk-xx
            export OPENAI_API_BASE=https://xx:80/v1

        run example.
        ..code-block:: shell
            python examples/agents/single_summary_agent_dialogue_example.py
"""

import asyncio
import os

from dbgpt.agent.agents.agent import AgentContext
from dbgpt.agent.agents.expand.summary_assistant_agent import SummaryAssistantAgent
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.core.interface.llm import ModelMetadata

if __name__ == "__main__":
    from dbgpt.model import OpenAILLMClient

    llm_client = OpenAILLMClient()
    context: AgentContext = AgentContext(conv_id="summarize", llm_provider=llm_client)
    context.llm_models = [ModelMetadata(model="gpt-3.5-turbo")]

    default_memory = GptsMemory()
    summarizer = SummaryAssistantAgent(memory=default_memory, agent_context=context)

    user_proxy = UserProxyAgent(memory=default_memory, agent_context=context)

    asyncio.run(
        user_proxy.a_initiate_chat(
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
    )

    ## dbgpt-vis message infos
    print(asyncio.run(default_memory.one_plan_chat_competions("summarize")))

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

from dbgpt.agent import AgentContext, AgentMemory, LLMConfig, UserProxyAgent
from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent


async def summary_example_with_success():
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="summarize")

    agent_memory = AgentMemory()
    summarizer = (
        await SummaryAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

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

    # dbgpt-vis message infos
    print(await agent_memory.gpts_memory.one_chat_completions("summarize"))


async def summary_example_with_faliure():
    from dbgpt.model.proxy import OpenAILLMClient

    llm_client = OpenAILLMClient(model_alias="gpt-3.5-turbo")
    context: AgentContext = AgentContext(conv_id="summarize")

    agent_memory = AgentMemory()
    summarizer = (
        await SummaryAssistantAgent()
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .build()
    )

    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    # Test the failure example

    await user_proxy.initiate_chat(
        recipient=summarizer,
        reviewer=user_proxy,
        message="""I want to summarize advantages of Nuclear Power according to the following content.

            Taylor Swift is an American singer-songwriter and actress who is one of the most prominent and successful figures in the music industry. She was born on December 13, 1989, in Reading, Pennsylvania, USA. Taylor Swift gained widespread recognition for her narrative songwriting style, which often draws from her personal experiences and relationships.

            Swift's career began in country music, and her self-titled debut album was released in 2006. She quickly became a sensation in the country music scene with hits like "Tim McGraw" and "Teardrops on My Guitar." However, it was her transition to pop music with albums like "Fearless," "Speak Now," and "Red" that catapulted her to international superstardom.

            Throughout her career, Taylor Swift has won numerous awards, including multiple Grammy Awards. Her albums consistently top charts, and her songs resonate with a wide audience due to their relatable lyrics and catchy melodies. Some of her most famous songs include "Love Story," "Blank Space," "Shake It Off," "Bad Blood," and "Lover."

            Beyond music, Taylor Swift has ventured into acting with roles in movies like "Valentine's Day" and "The Giver." She is also known for her philanthropic efforts and her willingness to use her platform to advocate for various causes.

            Taylor Swift is not only a successful artist but also an influential cultural icon known for her evolving musical style, storytelling abilities, and her impact on the entertainment industry.
            """,
    )

    print(await agent_memory.gpts_memory.one_chat_completions("summarize"))


if __name__ == "__main__":
    print(
        "\033[92m=======================Start The Summary Assistant with Successful Results==================\033[0m"
    )
    asyncio.run(summary_example_with_success())
    print(
        "\033[92m=======================The Summary Assistant with Successful Results Ended==================\n\n\033[91m"
    )

    print(
        "\033[91m=======================Start The Summary Assistant with Fail Results==================\033[91m"
    )
    asyncio.run(summary_example_with_faliure())
    print(
        "\033[91m=======================The Summary Assistant with Fail Results Ended==================\033[91m"
    )

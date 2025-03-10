# TODO add example run code here

import asyncio

# Agents examples
from .agents.auto_plan_agent_dialogue_example import main as auto_plan_main
from .agents.awel_layout_agents_chat_examples import main as awel_layout_main
from .agents.custom_tool_agent_example import main as custom_tool_main
from .agents.plugin_agent_dialogue_example import main as plugin_main
from .agents.retrieve_summary_agent_dialogue_example import (
    main as retrieve_summary_main,
)
from .agents.sandbox_code_agent_example import main as sandbox_code_main
from .agents.single_agent_dialogue_example import main as single_agent_main
from .agents.sql_agent_dialogue_example import main as sql_main

if __name__ == "__main__":
    # Run the examples

    ## Agent examples
    asyncio.run(auto_plan_main())
    asyncio.run(awel_layout_main())
    asyncio.run(custom_tool_main())
    asyncio.run(retrieve_summary_main())
    asyncio.run(plugin_main())
    asyncio.run(sandbox_code_main())
    asyncio.run(single_agent_main())
    asyncio.run(sql_main())

    ## awel examples
    print("hello world!")

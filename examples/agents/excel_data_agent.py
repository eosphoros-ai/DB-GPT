"""Excel Data Analysis Agent Example (ReAct Version with Built-in Skill Metadata).

This example demonstrates a ReAct agent that has pre-loaded metadata about available skills
in its system prompt. It can choose to load a specific skill to get detailed instructions
without needing to search/list first.
"""

import asyncio
import logging
import os
import sys

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.append(project_root)

from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    LLMConfig,
    ProfileConfig,
    UserProxyAgent,
)
from dbgpt.agent.expand.actions.react_action import Terminate
from dbgpt.agent.expand.react_agent import ReActAgent
from dbgpt.agent.resource import ToolPack, tool
from dbgpt.agent.resource.manage import (
    get_resource_manager,
    initialize_resource,
)
from dbgpt.agent.resource.skill_resource import SkillResource
from dbgpt.agent.skill import (
    SkillLoader,
    initialize_skill,
)
from dbgpt.model import AutoLLMClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Global Execution Context ---
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

GLOBAL_EXECUTION_CONTEXT = {"pd": pd, "np": np, "plt": plt, "print": print}


# --- Helpers ---


def scan_skills(skills_dir: str):
    """Scan the skills directory and return a list of skill metadata dicts."""
    skills = []
    if not os.path.exists(skills_dir):
        return skills

    # Use SkillLoader to properly load metadata if possible,
    # but for scanning we might just want to peek at files to be fast.
    # Here we will try to load them to get accurate descriptions.
    loader = SkillLoader()

    for root, dirs, files in os.walk(skills_dir):
        if "SKILL.md" in files:
            skill_path = os.path.join(root, "SKILL.md")
            try:
                # We load the skill to get its metadata (name, description)
                skill = loader.load_skill_from_file(skill_path)
                if skill and skill.metadata:
                    skills.append(
                        {
                            "name": skill.metadata.name,
                            "description": skill.metadata.description,
                            "path": os.path.relpath(skill_path, project_root),
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to load skill at {skill_path}: {e}")
    return skills


# --- Tools ---


@tool
def code_interpreter(code: str) -> str:
    """Execute Python code for data analysis.

    This tool allows you to run Python code to analyze data. You can use pandas, numpy,
    matplotlib, etc. The environment is persistent between calls.

    Args:
        code: The Python code to execute.

    Returns:
        The standard output and any error messages from the execution.
    """
    try:
        import ast
        import io
        import sys

        # AST transformation: wrap last expression in print() if needed
        try:
            tree = ast.parse(code)
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                expr_node = tree.body[-1]
                print_call = ast.Call(
                    func=ast.Name(id="print", ctx=ast.Load()),
                    args=[expr_node.value],
                    keywords=[],
                )
                tree.body[-1] = ast.Expr(value=print_call)
                ast.fix_missing_locations(tree)
                compiled_code = compile(tree, filename="<string>", mode="exec")
        except Exception:
            compiled_code = code

        old_stdout = sys.stdout
        redirected_output = sys.stdout = io.StringIO()

        exec(compiled_code, GLOBAL_EXECUTION_CONTEXT)

        sys.stdout = old_stdout
        return redirected_output.getvalue()
    except Exception as e:
        return f"Execution Error: {str(e)}"


@tool
def load_skill(skill_name: str) -> str:
    """Load a skill to get detailed instructions for a specific task.

    Use this tool when you want to "read" or "activate" a skill from your available list.
    It returns the full content and instructions of the skill.

    Args:
        skill_name: The name of the skill to load (must be one of the available skills).

    Returns:
        The detailed instructions and workflow defined in the skill.
    """
    # In a real implementation, we would use the SkillManager or a registry lookup.
    # For this script, we'll scan again or use a cached lookup to find the path.
    skills_dir = os.path.join(project_root, "skills")
    target_skill_path = None

    # Simple search
    for root, dirs, files in os.walk(skills_dir):
        if "SKILL.md" in files:
            # Check if this folder or metadata matches the requested name
            # We'll try to match loosely by folder name or strict check if we loaded metadata
            # For robustness in this example, let's load it to check name.
            try:
                loader = SkillLoader()
                path = os.path.join(root, "SKILL.md")
                skill = loader.load_skill_from_file(path)
                if skill and skill.metadata.name == skill_name:
                    target_skill_path = path
                    break
            except Exception:
                continue

    if not target_skill_path:
        return f"Error: Skill '{skill_name}' not found."

    try:
        with open(target_skill_path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"Successfully loaded skill '{skill_name}'.\n\nSKILL CONTENT:\n{content}"
    except Exception as e:
        return f"Error reading skill file: {str(e)}"


async def main():
    """Main execution function."""
    system_app = SystemApp()

    # 1. Initialize Managers
    initialize_skill(system_app)
    initialize_resource(system_app)

    # 2. Setup LLM
    llm_client = AutoLLMClient(
        provider=os.getenv("LLM_PROVIDER", "proxy/siliconflow"),
        name=os.getenv("LLM_MODEL_NAME", "Qwen/Qwen2.5-Coder-32B-Instruct"),
    )

    # 3. Scan for Skills
    skills_dir = os.path.join(project_root, "skills")
    available_skills_list = scan_skills(skills_dir)

    # 4. Construct Skill Prompt Section
    if not available_skills_list:
        skill_section = "Load a skill to get detailed instructions for a specific task. No skills are currently available."
    else:
        skills_xml = []
        for s in available_skills_list:
            skills_xml.append(f"  <skill>")
            skills_xml.append(f"    <name>{s['name']}</name>")
            skills_xml.append(f"    <description>{s['description']}</description>")
            skills_xml.append(f"  </skill>")

        skill_section_str = "\n".join(skills_xml)
        skill_section = (
            "Load a skill to get detailed instructions for a specific task.\n"
            "Skills provide specialized knowledge and step-by-step guidance.\n"
            "Use this when a task matches an available skill's description.\n"
            "Only the skills listed here are available:\n"
            "<available_skills>\n"
            f"{skill_section_str}\n"
            "</available_skills>"
        )

    # 5. Context & Memory
    context = AgentContext(
        conv_id="skill_metadata_session", gpts_app_name="Skill Specialist"
    )
    agent_memory = AgentMemory()
    agent_memory.gpts_memory.init(conv_id="skill_metadata_session")

    # 6. Tools (Notice: No list tool, just load/read)
    tools = ToolPack([load_skill, code_interpreter, Terminate()])

    # 7. Profile
    profile = ProfileConfig(
        name="SkillAwareAgent",
        role="Adaptive Assistant",
        goal=(
            "You are an intelligent assistant. "
            f"{skill_section}\n\n"
            "WORKFLOW:\n"
            "1. Analyze the user's request.\n"
            "2. Identify if an available skill in <available_skills> matches the request.\n"
            "3. If yes, use the `load_skill` tool with the skill's name to get instructions.\n"
            "4. Follow the loaded instructions strictly to complete the task using `code_interpreter`."
        ),
    )

    # 8. Build ReAct Agent
    agent = (
        await ReActAgent(
            profile=profile,
            max_retry_count=5,
        )
        .bind(context)
        .bind(LLMConfig(llm_client=llm_client))
        .bind(agent_memory)
        .bind(tools)
        .build()
    )

    # 9. User Proxy
    user_proxy = await UserProxyAgent().bind(agent_memory).bind(context).build()

    # 10. Test Data Setup
    test_file = "sales_data_sample.xlsx"
    df = pd.DataFrame(
        {
            "Date": pd.date_range(start="1/1/2023", periods=10),
            "Product": ["Widget A", "Widget B", "Widget A", "Widget C", "Widget B"] * 2,
            "Sales": [100, 200, 150, 300, 250, 120, 220, 160, 310, 260],
            "Region": ["North", "South", "North", "East", "South"] * 2,
        }
    )
    df.to_excel(test_file, index=False)
    abs_test_file = os.path.abspath(test_file)
    logger.info(f"Created test file: {abs_test_file}")

    # 11. Start Chat
    msg = f"I have a file at '{abs_test_file}'. Analyze the sales data."

    logger.info("Starting session...")
    await user_proxy.initiate_chat(
        recipient=agent,
        reviewer=user_proxy,
        message=msg,
    )

    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)
        logger.info("Test file cleaned up.")


from dbgpt.component import SystemApp

if __name__ == "__main__":
    asyncio.run(main())

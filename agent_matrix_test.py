from orchestrator_test.orchestrator.translate_agent_app.agentic_orchestrator_example import main
from orchestrator_test.orchestrator.translate_agent_app.configs.agents  import triage_agent
from orchestrator_test.orchestrator.translate_agent_app.background import context_variables
from dbgpt.orhestrator.core import Matrix, Agent

if __name__ == "__main__":
    main(
        triage_agent,
        context_variables=context_variables,
        debug=True
    )
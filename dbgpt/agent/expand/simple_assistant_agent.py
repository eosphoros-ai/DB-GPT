"""Simple Assistant Agent."""

import logging
from typing import Dict, List, Optional, Tuple

from dbgpt.rag.retriever.rerank import RetrieverNameRanker

from .. import AgentMessage
from ..core.action.blank_action import BlankAction
from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig

logger = logging.getLogger(__name__)


class SimpleAssistantAgent(ConversableAgent):
    """Simple Assistant Agent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "Tom",
            category="agent",
            key="dbgpt_agent_expand_simple_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "AI Assistant",
            category="agent",
            key="dbgpt_agent_expand_simple_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "Understand user questions and give professional answer",
            category="agent",
            key="dbgpt_agent_expand_simple_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Please make sure your answer is clear, logical, "
                "friendly, and human-readable."
            ],
            category="agent",
            key="dbgpt_agent_expand_simple_assistant_agent_profile_constraints",
        ),
        desc=DynConfig(
            "I am a universal simple AI assistant.",
            category="agent",
            key="dbgpt_agent_expand_summary_assistant_agent_profile_desc",
        ),
    )

    def __init__(self, **kwargs):
        """Create a new SummaryAssistantAgent instance."""
        super().__init__(**kwargs)
        self._post_reranks = [RetrieverNameRanker(5)]
        self._init_actions([BlankAction])

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        """Load agent bind resource."""
        if self.resource:
            if self.resource.is_pack:
                sub_resources = self.resource.sub_resources
                candidates_results: List = []
                resource_candidates_map = {}
                info_map = {}
                prompt_list = []
                for resource in sub_resources:
                    (
                        candidates,
                        prompt_template,
                        resource_reference,
                    ) = await resource.get_resources(question=question)
                    resource_candidates_map[resource.name] = (
                        candidates,
                        resource_reference,
                        prompt_template,
                    )
                    candidates_results.extend(candidates)  # type: ignore # noqa
                new_candidates_map = self.post_filters(resource_candidates_map)
                for resource, (
                    candidates,
                    references,
                    prompt_template,
                ) in new_candidates_map.items():
                    content = "\n".join(
                        [
                            f"--{i}--:" + chunk.content
                            for i, chunk in enumerate(candidates)  # type: ignore # noqa
                        ]
                    )
                    prompt_list.append(
                        prompt_template.format(name=resource, content=content)
                    )
                    info_map.update(references)
                return "\n".join(prompt_list), info_map
            else:
                resource_prompt, resource_reference = await self.resource.get_prompt(
                    lang=self.language, question=question
                )
                return resource_prompt, resource_reference
        return None, None

    def _init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message, rely_messages)
        reply_message.context = {
            "user_question": received_message.content,
        }
        return reply_message

    def post_filters(self, resource_candidates_map: Optional[Dict[str, Tuple]] = None):
        """Post filters for resource candidates."""
        if resource_candidates_map:
            new_candidates_map = resource_candidates_map.copy()
            filter_hit = False
            for resource, (
                candidates,
                references,
                prompt_template,
            ) in resource_candidates_map.items():
                for rerank in self._post_reranks:
                    filter_candidates = rerank.rank(candidates)
                    new_candidates_map[resource] = [], [], prompt_template
                    if filter_candidates and len(filter_candidates) > 0:
                        new_candidates_map[resource] = (
                            filter_candidates,
                            references,
                            prompt_template,
                        )
                        filter_hit = True
                        break
            if filter_hit:
                logger.info("Post filters hit, use new candidates.")
                return new_candidates_map
        return resource_candidates_map

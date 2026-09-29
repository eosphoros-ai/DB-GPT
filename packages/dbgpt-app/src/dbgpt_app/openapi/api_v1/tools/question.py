"""question tool — ask user questions and block until answered."""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List

from pydantic import BaseModel, Field

from dbgpt.agent.resource.tool.base import tool

from .question_manager import question_manager

logger = logging.getLogger(__name__)


class QuestionChoice(BaseModel):
    label: str = Field(min_length=1)
    description: str = ""


class QuestionPrompt(BaseModel):
    question: str = Field(min_length=1)
    header: str = ""
    options: List[QuestionChoice] = Field(default_factory=list)
    multiple: bool = False
    custom: bool = True


_DESCRIPTION = """\
Use this tool when you need to ask the user questions during \
execution. This allows you to:
1. Gather user preferences or requirements
2. Clarify ambiguous instructions
3. Get decisions on implementation choices as you work
4. Offer choices to the user about what direction to take.

Usage notes:
- Only ask for missing business information. Tool failures, invalid parameters,
  and internal exceptions are execution failures, never questions for the user.
- IMPORTANT: Always write the question text, header, option \
labels, and descriptions in the SAME language the user is using. \
If the user writes in English, all content must be in English; \
if in Chinese, use Chinese, etc.
- When `custom` is enabled (default), a "Type your own answer" \
option is added automatically; don't include "Other" or \
catch-all options
- Answers are returned as arrays of labels; set `multiple: true` \
to allow selecting more than one
- options and header are optional; omitting options asks a free-text question.
- If you recommend a specific option, make that the first option \
in the list and add "(Recommended)" at the end of the label
Parameter: {"questions": [{"question": "...", "header": "...", \
"options": [{"label": "...", "description": "..."}], \
"multiple": false}]}
"""


def make_question(react_state: Dict[str, Any], stream_callback: Callable):
    """Return a ``question`` FunctionTool bound to react_state and stream_callback."""

    @tool(
        description=_DESCRIPTION,
        args={
            "questions": {
                "type": "array",
                "required": True,
                "description": (
                    "Non-empty array of {question: string, header?: string, "
                    "options?: [{label: string, description?: string}], "
                    "multiple?: boolean, custom?: boolean}. Defaults: options=[], "
                    "multiple=false, custom=true. Legacy strings become free-text "
                    "questions; a JSON-encoded array is also accepted."
                ),
            }
        },
    )
    async def question(questions: Any) -> str:
        """Ask the user one or more questions and wait for their answers.

        Args:
            questions: A list (or JSON-encoded list) of question objects with:
                - question (str): Complete question text
                - header (str): Very short label (max 30 chars)
                - options (list): [{label, description}] available choices
                - multiple (bool, optional): allow multi-select
        """
        conv_id = react_state.get("conv_id", "default")
        if react_state.get("dashboard_tool_failure"):
            # Defense in depth for direct/reordered tool dispatch in a failed turn.
            # No request registration and, crucially, no question.asked event.
            raise RuntimeError(react_state["dashboard_tool_failure"]["message"])

        # Parse questions JSON
        try:
            parsed_questions = (
                json.loads(questions) if isinstance(questions, str) else questions
            )
            if not isinstance(parsed_questions, list):
                parsed_questions = parsed_questions.get("questions", [])
            if not isinstance(parsed_questions, list) or not parsed_questions:
                raise ValueError("At least one non-empty question is required.")
            # Normalize, never filter: answers retain their original question slot.
            parsed_questions = [
                QuestionPrompt.model_validate(
                    {"question": item} if isinstance(item, str) else item
                ).model_dump()
                for item in parsed_questions
            ]
            if any(not item["question"].strip() for item in parsed_questions):
                raise ValueError("Question text must not be blank.")
            if any(
                not item["options"] and not item["custom"] for item in parsed_questions
            ):
                raise ValueError("A question needs options or enabled custom input.")
        except Exception as e:
            return json.dumps(
                {
                    "__dashboard_tool_error__": {
                        "tool": "question",
                        "code": "invalid_question_parameters",
                        "reason": f"Error: invalid questions JSON — {e}",
                    },
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Error: invalid questions JSON — {e}",
                        }
                    ],
                },
                ensure_ascii=False,
            )

        # 1. Register in QuestionManager → creates asyncio.Event
        pq = question_manager.create(conv_id=conv_id, questions=parsed_questions)

        # 2. Push question.asked SSE event to frontend
        await stream_callback(
            "question.asked",
            {
                "request_id": pq.request_id,
                "conv_id": conv_id,
                "questions": parsed_questions,
                "sequence": pq.sequence,
            },
        )
        logger.info(
            "question tool: pushed question.asked, request_id=%s", pq.request_id
        )

        # 3. Block until user answers (or timeout)
        try:
            await asyncio.wait_for(pq.event.wait(), timeout=300)
        except asyncio.TimeoutError:
            question_manager.remove(pq.request_id)
            await stream_callback(
                "question.rejected", {"request_id": pq.request_id, "conv_id": conv_id}
            )
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": (
                                "Question timed out after 300 seconds."
                                " Proceeding without user answer."
                            ),
                        }
                    ]
                },
                ensure_ascii=False,
            )
        finally:
            question_manager.remove(pq.request_id)

        await stream_callback(
            "question.rejected" if pq.rejected else "question.replied",
            {"request_id": pq.request_id, "conv_id": conv_id, "sequence": pq.sequence},
        )

        # 4. User rejected
        if pq.rejected:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": (
                                "The user dismissed the question."
                                " Proceeding without answer."
                            ),
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # 5. Format answers for the LLM
        answers = pq.answers or []
        parts = []
        for i, q in enumerate(parsed_questions):
            q_text = q.get("question", "")
            a_text = (
                ", ".join(answers[i])
                if i < len(answers) and answers[i]
                else "Unanswered"
            )
            parts.append(f'"{q_text}"="{a_text}"')
        formatted = ", ".join(parts)
        output = (
            f"User has answered your questions: {formatted}."
            " You can now continue with the user's answers"
            " in mind."
        )
        return json.dumps(
            {"chunks": [{"output_type": "text", "content": output}]},
            ensure_ascii=False,
        )

    return question

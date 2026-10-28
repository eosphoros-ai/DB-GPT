"""Expose actual server-preloaded skill documents in the execution timeline."""

from typing import Any, Dict, List, Optional


def preloaded_skill_steps(
    *, binding: Optional[Any] = None, skill: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """Describe already-read documents; never infer a successful read from intent."""
    steps = []
    if binding is not None and binding.command_skill_text and not binding.command_error:
        documents = list(binding.loaded_documents)
        if documents and all(doc.get("status") == "loaded" for doc in documents):
            documents = [
                {**documents[0], "content": binding.command_skill_text},
                *documents[1:],
            ]
            steps.append(
                _read_step(
                    "skill-read-suite",
                    binding.command_skill,
                    documents,
                    f"Expert suite: {binding.name}@{binding.version}",
                )
            )
    if skill is not None:
        instructions = skill.instructions or ""
        if instructions:
            steps.append(
                _read_step(
                    "skill-read-selected",
                    skill.metadata.name,
                    [
                        {
                            "path": skill.metadata.file_path or "SKILL.md",
                            "content": instructions,
                        }
                    ],
                    "Server-preloaded skill",
                )
            )
    return steps


def _read_step(
    step_id: str, name: str, documents: List[Dict[str, Any]], source: str
) -> Dict[str, Any]:
    return {
        "id": step_id,
        "title": "读取技能",
        "detail": source,
        "phase": "skill_loading",
        "action": "load_skill",
        "action_input": {"skill_name": name, "file_path": documents[0]["path"]},
        "outputs": [
            {
                "output_type": "text",
                "content": f"Skill: {name}\n{source}\n"
                + "\n".join(f"File: {doc['path']}" for doc in documents),
            },
            *[
                {
                    "output_type": "markdown",
                    "content": f"### {doc['path']}\n\n{doc['content']}",
                }
                for doc in documents
                if doc.get("content")
            ],
        ],
        "status": "done",
    }


def skill_read_events(step: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Use the existing SSE vocabulary and the same persisted step identity."""
    return [
        {
            "type": "step.start",
            **{key: step[key] for key in ("id", "title", "detail", "phase", "action")},
        },
        {
            "type": "step.meta",
            **{key: step[key] for key in ("id", "title", "action", "action_input")},
        },
        *[
            {"type": "step.chunk", "id": step["id"], **output}
            for output in step["outputs"]
        ],
        {"type": "step.done", "id": step["id"], "status": "done"},
    ]

"""Load dashboard-design skill resources without sample data or catalog SQL."""

import json
import re
from copy import deepcopy

from .assistant_skills import dashboard_internal_skill_root
from .schemas import DashboardLayouts, DashboardVisualTheme


def design_skill_root():
    return dashboard_internal_skill_root("dashboard-design")


def is_internal_dashboard_skill(file_path):
    """Nested helpers remain loadable but are not independent user tasks."""
    return "dashboard-builder/internal/" in str(file_path).replace("\\", "/")


def load_gallery_reference(selection):
    if not isinstance(selection, str) or not re.fullmatch(
        r"(?:catalog|design):[a-z0-9]+(?:-[a-z0-9]+)*", selection
    ):
        raise ValueError("Unknown gallery style reference.")
    try:
        resolve_gallery_selection(selection)
    except ValueError as exc:
        raise ValueError("Unknown gallery style reference.") from exc
    path = design_skill_root() / "references" / (selection.replace(":", "-") + ".md")
    if not path.is_file():
        raise ValueError("Unknown gallery style reference.")
    body = path.read_text(encoding="utf-8")
    reference = json.loads(body.split("```json\n", 1)[1].split("\n```", 1)[0])
    if reference["selection"] != selection:
        raise ValueError("Gallery reference does not match the selected style.")
    return reference


def available_gallery_styles():
    """Expose the small index only when a user asks the agent to select a style."""
    return (design_skill_root() / "references" / "index.md").read_text("utf-8")


def resolve_gallery_selection(selection):
    """Accept an exact, unique display name without guessing a user's style."""
    if not isinstance(selection, str):
        raise ValueError("Unknown gallery style reference.")
    selection = selection.strip()
    entries = re.findall(
        r"^- `((?:catalog|design):[a-z0-9-]+)` — \[([^\]]+)\]",
        available_gallery_styles(),
        flags=re.MULTILINE,
    )
    if selection in {key for key, _ in entries}:
        return selection
    matches = {
        key for key, title in entries if title.casefold() == selection.casefold()
    }
    if len(matches) != 1:
        raise ValueError(
            "Unknown or ambiguous style name; omit selection to list styles."
        )
    return matches.pop()


def _skill_instructions(path):
    return path.read_text(encoding="utf-8").split("---", 2)[-1].strip()


def gallery_plan_context(selection):
    reference = load_gallery_reference(selection)
    root = design_skill_root()
    instructions = _skill_instructions(root / "SKILL.md")
    if selection.startswith("design:"):
        guidance = root.parent / selection.removeprefix("design:") / "SKILL.md"
        if guidance.is_file():
            instructions += "\n\n" + _skill_instructions(guidance)
    return {
        "selection": selection,
        "skill": "dashboard-design",
        "reference": "references/" + selection.replace(":", "-") + ".md",
        "title": reference["title"],
        "description": reference["description"],
        "widgets": [
            {key: w[key] for key in ("id", "suggested_type", "reference_title")}
            for w in reference["widgets"]
        ],
        "instruction": instructions,
    }


def apply_gallery_appearance(schema, selection, *, saved_schema=None):
    if saved_schema is not None:
        # Existing plans own their appearance, even after a gallery reference
        # is removed from the application package.
        originals = {w.id: w for w in saved_schema.widgets}
        if {w.id for w in schema.widgets} != set(originals):
            raise ValueError(
                "Keep the selected template slot ids: " + ", ".join(originals)
            )
        schema.dashboard.theme = saved_schema.dashboard.theme.model_copy(deep=True)
        schema.layouts = saved_schema.layouts.model_copy(deep=True)
        for widget in schema.widgets:
            original = originals[widget.id]
            widget.style = deepcopy(original.style)
            widget.presentation.colors = list(original.presentation.colors)
        return
    reference = load_gallery_reference(selection)
    originals = {w["id"]: w for w in reference["widgets"]}
    if {w.id for w in schema.widgets} != set(originals):
        raise ValueError("Keep the selected template slot ids: " + ", ".join(originals))
    schema.dashboard.theme = DashboardVisualTheme.model_validate(reference["theme"])
    schema.layouts = DashboardLayouts.model_validate(reference["layouts"])
    schema.metadata.compatibility.update(reference["compatibility"])
    for widget in schema.widgets:
        original = originals[widget.id]
        widget.style = {
            key: value
            for key, value in original["style"].items()
            if key in {"hero_image", "metric_icon"}
        }
        widget.presentation.colors = list(original["colors"])
    schema.metadata.compatibility["gallery_template"] = selection
    schema.metadata.compatibility["gallery_skill"] = "dashboard-design"

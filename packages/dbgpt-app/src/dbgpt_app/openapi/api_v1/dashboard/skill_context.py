"""Keep dashboard phases focused without dropping shared skill rules."""

import re


def _without_unrelated_sections(instructions, required_heading, unrelated):
    """Remove only known, unrelated phases; unknown/new sections remain intact."""
    sections = re.split(r"(?=^## )", instructions, flags=re.MULTILINE)
    headings = {section.splitlines()[0].strip() for section in sections if section}
    if required_heading not in headings:
        # A customized/older skill must keep its complete instructions.
        return instructions
    return "".join(
        section
        for section in sections
        if section and section.splitlines()[0].strip() not in unrelated
    )


def planning_skill_instructions(instructions: str) -> str:
    """Planning still keeps shared data checks, but not SQL payload instructions."""
    return _without_unrelated_sections(
        instructions,
        "## New dashboard: plan first",
        {"## Confirmed plan: generate queries", "## Selection-aware annotation"},
    )


def confirmed_skill_instructions(instructions: str) -> str:
    """Confirmation consumes the saved plan instead of repeating discovery."""
    return _without_unrelated_sections(
        instructions,
        "## Confirmed plan: generate queries",
        {"## New dashboard: plan first", "## Selection-aware annotation"},
    )


def confirmed_gallery_context(context):
    """Appearance is already persisted; SQL uses the confirmed business plan."""
    return {
        "selection": context["selection"],
        "skill": context["skill"],
        "instruction": (
            "The selected appearance is saved in the confirmed dashboard. The "
            "server preserves its layout and colors. Generate only the confirmed "
            "plan's queries; do not reload styles or repeat the reference metrics."
        ),
    }

"""Claude-style SKILL mechanism for DB-GPT agents.

This module implements a simple SKILL system similar to Claude's SKILL mechanism,
where skills are defined in Markdown files with metadata and instructions.
"""

import dataclasses
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from dbgpt.core import PromptTemplate


def escape_jinja2_syntax(text: str) -> str:
    """转义 Jinja2 模板语法，使文本在 Jinja2 模板中始终按字面量渲染。

    技能指令来自用户上传的 SKILL.md，属于不可信数据，不能直接当作 Jinja2
    模板源码使用。否则其中的 ``{{ }}`` / ``{% %}`` / ``{# #}`` 会被当作模板
    指令求值：

    - 未定义的变量会被静默渲染成空字符串，技能指令中的内容凭空丢失；
    - 非法语法（例如文档里常见的 JSON 示例 ``{{ "k": "v" }}``）会直接抛出
      TemplateSyntaxError，导致技能无法加载；
    - 构造的载荷还可能构成服务端模板注入（SSTI）。

    这里把三种定界符替换为等价的字面量表达式，保证技能指令始终以原文形式
    呈现给模型。

    Args:
        text: 原始文本。

    Returns:
        转义后的文本，作为 Jinja2 模板渲染时输出与原文一致。
    """
    # 注意替换顺序：先替换 "{{"，避免替换结果中的 "{{" 被二次处理
    return (
        text.replace("{{", "{{ '{{' }}")
        .replace("{%", "{{ '{%' }}")
        .replace("{#", "{{ '{#' }}")
    )


class SkillPromptTemplate(PromptTemplate):
    """Prompt template of a skill, keeping the original text of the skill.

    The template source of a skill is the Jinja2 escaped version of the skill
    instructions, so that the instructions are never evaluated as template
    source. ``raw_template`` keeps the original text, so that callers can
    return the skill content verbatim (see
    ``SkillManager.get_skill_content``) instead of rendering the template.
    """

    raw_template: str = ""
    """The original, unescaped text of the skill."""


@dataclasses.dataclass
class SkillMetadata:
    """Metadata for a Claude-style SKILL file."""

    name: str
    description: str
    file_path: Optional[str] = None
    triggers: Set[str] = dataclasses.field(default_factory=set)
    # Optional fields supported in SKILL.md frontmatter
    version: Optional[str] = None
    author: Optional[str] = None
    skill_type: Optional[str] = None
    tags: List[str] = dataclasses.field(default_factory=list)
    required_tools: List[str] = dataclasses.field(default_factory=list)
    required_knowledge: List[str] = dataclasses.field(default_factory=list)
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.name}: {self.description}"


class ClaudeSkill(ABC):
    """Base class for Claude-style SKILL."""

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        """Return the skill name."""
        pass

    @classmethod
    @abstractmethod
    def description(cls) -> str:
        """Return the skill description."""
        pass

    @classmethod
    @abstractmethod
    def instructions(cls) -> str:
        """Return the skill instructions."""
        pass

    @classmethod
    def matches(cls, user_input: str) -> bool:
        """Check if the user input matches this skill.

        Can be overridden for custom matching logic.

        Args:
            user_input: The user's input string.

        Returns:
            True if the skill should be activated.
        """
        return False

    @classmethod
    def get_prompt(cls) -> PromptTemplate:
        """Get the prompt template for this skill.

        Returns:
            PromptTemplate with the skill instructions.
        """
        instructions = cls.instructions()
        prompt = f"""{instructions}"""
        return PromptTemplate.from_template(prompt)


class FileBasedSkill:
    """Skill loaded from a SKILL.md file.

    This implements Claude's SKILL.md file format:

    ---
    name: skill-name
    description: Skill description
    ---

    Instructions here...

    Examples triggers are in the description.
    """

    def __init__(self, file_path: str):
        """Initialize from a SKILL.md file.

        Args:
            file_path: Path to the SKILL.md file.
        """
        self.file_path = file_path
        self._metadata, self._instructions = self._parse_file(file_path)

    def _parse_file(self, file_path: str) -> tuple[SkillMetadata, str]:
        """Parse a SKILL.md file.

        Args:
            file_path: Path to the file.

        Returns:
            Tuple of (metadata, instructions).
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        content = content.strip()

        if not content.startswith("---"):
            raise ValueError(f"SKILL file must start with '---': {file_path}")

        parts = content.split("---", 2)

        if len(parts) < 3:
            raise ValueError(
                "Invalid SKILL file format. "
                f"Expected '---metadata---instructions': {file_path}"
            )

        metadata_text = parts[1].strip()
        instructions = parts[2].strip()

        metadata = self._parse_metadata(metadata_text, file_path)

        return metadata, instructions

    def _parse_metadata(self, text: str, file_path: str) -> SkillMetadata:
        """Parse metadata section.

        Args:
            text: Metadata text.
            file_path: File path for error messages.

        Returns:
            SkillMetadata instance.
        """
        # Prefer parsing the frontmatter with PyYAML for robust typing support.
        try:
            import yaml

            parsed = yaml.safe_load(text)
            if not isinstance(parsed, dict):
                raise ValueError("SKILL frontmatter is not a mapping")

            if "name" not in parsed:
                raise ValueError(f"SKILL file missing 'name': {file_path}")
            if "description" not in parsed:
                raise ValueError(f"SKILL file missing 'description': {file_path}")

            name = parsed.get("name")
            description = parsed.get("description")
            version = parsed.get("version")
            author = parsed.get("author")
            skill_type = parsed.get("skill_type")

            def to_list(val):
                if val is None:
                    return []
                if isinstance(val, list):
                    return val
                if isinstance(val, str):
                    return [t.strip() for t in val.split(",") if t.strip()]
                return [val]

            tags = to_list(parsed.get("tags"))
            required_tools = to_list(parsed.get("required_tools"))
            required_knowledge = to_list(parsed.get("required_knowledge"))
            config = parsed.get("config") or {}

            metadata = SkillMetadata(
                name=name or "",
                description=description or "",
                file_path=file_path,
                version=version,
                author=author,
                skill_type=skill_type,
                tags=tags,
                required_tools=required_tools,
                required_knowledge=required_knowledge,
                config=config,
            )
            return metadata
        except ImportError:
            # PyYAML not installed; fallback to line-based parsing
            metadata_dict = {}

            for line in text.split("\n"):
                line = line.strip()
                if not line or ":" not in line:
                    continue

                key, value = line.split(":", 1)
                key = key.strip().lower()
                value = value.strip()

                metadata_dict[key] = value

            if "name" not in metadata_dict:
                raise ValueError(f"SKILL file missing 'name': {file_path}")
            if "description" not in metadata_dict:
                raise ValueError(f"SKILL file missing 'description': {file_path}")

            name = metadata_dict["name"]
            description = metadata_dict["description"]

            version = metadata_dict.get("version")
            author = metadata_dict.get("author")
            skill_type = metadata_dict.get("skill_type")
            tags = [
                t.strip() for t in metadata_dict.get("tags", "").split(",") if t.strip()
            ]
            required_tools = [
                t.strip()
                for t in metadata_dict.get("required_tools", "").split(",")
                if t.strip()
            ]
            required_knowledge = [
                t.strip()
                for t in metadata_dict.get("required_knowledge", "").split(",")
                if t.strip()
            ]

            metadata = SkillMetadata(
                name=name or "",
                description=description or "",
                file_path=file_path,
                version=version,
                author=author,
                skill_type=skill_type,
                tags=tags,
                required_tools=required_tools,
                required_knowledge=required_knowledge,
            )

            return metadata

    @property
    def metadata(self) -> SkillMetadata:
        """Return the skill metadata."""
        return self._metadata

    @property
    def instructions(self) -> str:
        """Return the skill instructions."""
        return self._instructions

    def matches(self, user_input: str) -> bool:
        """Check if user input matches this skill.

        Simple matching based on description containing trigger phrases.

        Args:
            user_input: User input string.

        Returns:
            True if should activate this skill.
        """
        user_input_lower = user_input.lower()
        description_lower = self.metadata.description.lower()

        keywords = self._extract_keywords(description_lower)

        for keyword in keywords:
            if keyword in user_input_lower:
                return True

        name_lower = self.metadata.name.lower()
        tags_lower = [tag.lower() for tag in (self.metadata.tags or [])]
        if (
            "excel" in name_lower
            or "excel" in description_lower
            or "excel" in tags_lower
        ):
            return any(
                kw in user_input_lower
                for kw in [
                    "excel",
                    "xlsx",
                    "xls",
                    "spreadsheet",
                    "sheet",
                    "workbook",
                    "表格",
                    "工作表",
                    "电子表格",
                ]
            )

        return False

    def _extract_keywords(self, description: str) -> List[str]:
        """Extract potential trigger keywords from description.

        Args:
            description: Skill description.

        Returns:
            List of keywords.
        """
        keywords = []

        pattern = (
            r"(?:when|use|for|to)\s+(?:the\s+)?(?:user\s+)?"
            r"(?:asks|requests|wants|needs)?\s*(?:to\s+)?([a-z\s]+?)"
            r"(?:\s*(?:\.|,|;|or|\(|\)|use when|$))"
        )
        matches = re.findall(pattern, description, re.IGNORECASE)

        for match in matches:
            words = [w.strip() for w in match.split() if len(w.strip()) > 2]
            keywords.extend(words)

        keywords.append(self.metadata.name.lower())

        return list(set(keywords))

    def get_prompt(self) -> PromptTemplate:
        """Get the prompt template for this skill.

        技能指令是不可信数据，这里先转义其中的 Jinja2 语法，避免它在渲染
        系统提示词时被当作模板源码求值（内容丢失、语法报错或 SSTI）。

        Returns:
            PromptTemplate with the skill instructions.
        """
        prompt = escape_jinja2_syntax(self.instructions)
        return SkillPromptTemplate.from_template(
            prompt,
            template_format="jinja2",
            template_is_strict=False,
            raw_template=self.instructions,
        )

    def __str__(self) -> str:
        return str(self.metadata)


class SkillRegistry:
    """Registry for managing Claude-style skills."""

    def __init__(self):
        """Initialize the skill registry."""
        self._skills: Dict[str, FileBasedSkill] = {}
        self._class_skills: Dict[str, type] = {}

    def register_skill(self, skill: FileBasedSkill):
        """Register a file-based skill.

        Args:
            skill: FileBasedSkill instance.
        """
        self._skills[skill.metadata.name] = skill

    def register_skill_class(self, skill_class: type):
        """Register a skill class.

        Args:
            skill_class: A subclass of ClaudeSkill.
        """
        if not issubclass(skill_class, ClaudeSkill):
            raise ValueError(f"{skill_class} must be a subclass of ClaudeSkill")

        self._class_skills[skill_class.name()] = skill_class

    def get_skill(self, name: str) -> Optional[FileBasedSkill]:
        """Get a skill by name.

        Args:
            name: Skill name.

        Returns:
            FileBasedSkill or None.
        """
        return self._skills.get(name)

    def get_skill_class(self, name: str) -> Optional[type]:
        """Get a skill class by name.

        Args:
            name: Skill name.

        Returns:
            Skill class or None.
        """
        return self._class_skills.get(name)

    def list_skills(self) -> List[SkillMetadata]:
        """List all registered skills.

        Returns:
            List of skill metadata.
        """
        return [skill.metadata for skill in self._skills.values()]

    def match_skill(self, user_input: str) -> Optional[FileBasedSkill]:
        """Find a matching skill for the user input.

        Args:
            user_input: User's input string.

        Returns:
            Matching skill or None.
        """
        matches = []

        for skill in self._skills.values():
            if skill.matches(user_input):
                matches.append(skill)

        if not matches:
            return None

        if len(matches) == 1:
            return matches[0]

        matches.sort(key=lambda s: -len(s.instructions))
        return matches[0]

    def load_from_directory(self, directory: str, recursive: bool = True):
        """Load all SKILL.md files from a directory.

        Args:
            directory: Directory path.
            recursive: Whether to search recursively.
        """
        dir_path = Path(directory)

        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"Directory not found: {directory}")

        pattern = "**/SKILL.md" if recursive else "*/SKILL.md"

        for skill_file in dir_path.glob(pattern):
            try:
                skill = FileBasedSkill(str(skill_file))
                self.register_skill(skill)
            except Exception as e:
                print(f"Failed to load skill from {skill_file}: {e}")


_global_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """Get the global skill registry.

    Returns:
        SkillRegistry instance.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
    return _global_registry


def load_skills_from_dir(directory: str, recursive: bool = True):
    """Load skills from a directory into the global registry.

    Args:
        directory: Directory containing SKILL.md files.
        recursive: Whether to search recursively.
    """
    registry = get_registry()
    registry.load_from_directory(directory, recursive)

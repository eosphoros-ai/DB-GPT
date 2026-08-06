"""Skill loader for loading skills from various sources."""

import importlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .base import Skill, SkillBase, SkillMetadata, SkillType

logger = logging.getLogger(__name__)


class SkillLoader:
    """Skill loader for loading skills from files or modules."""

    def __init__(self, skill_dirs: Optional[List[str]] = None):
        """Initialize skill loader.

        Args:
            skill_dirs: List of directories to search for skills.
        """
        self.skill_dirs = skill_dirs or []

    def load_skill_from_file(self, file_path: str) -> Optional[SkillBase]:
        """Load a skill from a JSON/YAML file.

        Args:
            file_path: Path to the skill file.

        Returns:
            Skill instance.
        """
        # Normalize and resolve the incoming path. Accepts absolute or relative paths.
        path = Path(file_path).expanduser()

        # If the provided path is not absolute or doesn't exist, try resolving
        # it relative to the current working directory (common when running
        # scripts from project root) to give better UX.
        tried_paths = [path]
        if not path.is_absolute():
            tried_paths.append(Path.cwd() / path)

        # Try all candidate paths and pick the first existing one.
        resolved = None
        for p in tried_paths:
            try:
                rp = p.resolve()
            except Exception:
                rp = p
            if rp.exists():
                resolved = rp
                break

        if resolved is None or not resolved.exists():
            logger.error(
                "Skill file not found. Tried: %s",
                ", ".join(str(p) for p in tried_paths),
            )
            return None

        path = resolved

        if path.suffix == ".json":
            return self._load_from_json(path)
        elif path.name == "SKILL.md":
            return self._load_from_markdown(path)
        elif path.suffix in [".yaml", ".yml"]:
            return self._load_from_yaml(path)
        else:
            logger.error(f"Unsupported file format: {path.suffix}")
            return None

    def load_skill_from_module(self, module_path: str) -> Optional[SkillBase]:
        """Load a skill from a Python module.

        Args:
            module_path: Python module path (e.g., "my_skills.coding_skill").

        Returns:
            Skill instance.
        """
        try:
            module = importlib.import_module(module_path)
            skill_cls = getattr(module, "Skill", None)
            if skill_cls and issubclass(skill_cls, SkillBase):
                return skill_cls()
            logger.warning(f"No Skill class found in module: {module_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to load skill from module {module_path}: {e}")
            return None

    def load_skills_from_directory(
        self, directory: str, recursive: bool = True
    ) -> List[SkillBase]:
        """Load all skills from a directory.

        Args:
            directory: Directory path.
            recursive: Whether to search recursively.

        Returns:
            List of skill instances.
        """
        skills: List[SkillBase] = []
        path = Path(directory)

        if not path.exists() or not path.is_dir():
            logger.warning(f"Directory not found: {directory}")
            return skills

        # Look for JSON/YAML files and Claude-style SKILL.md files
        pattern = "**/*" if recursive else "*"
        for file_path in path.glob(pattern):
            if (
                file_path.is_file()
                and file_path.suffix
                in [
                    ".json",
                    ".yaml",
                    ".yml",
                ]
                or file_path.name == "SKILL.md"
            ):
                # load_skill_from_file will dispatch appropriately
                skill = self.load_skill_from_file(str(file_path))
                if skill:
                    skills.append(skill)

        return skills

    def _load_from_json(self, path: Path) -> Optional[Skill]:
        """Load skill from JSON file.

        Args:
            path: Path to JSON file.

        Returns:
            Skill instance.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            skill = self._create_skill_from_dict(data)
            if skill:
                # Store the file path in config
                skill._config["file_path"] = str(path)
            return skill
        except Exception as e:
            logger.error(f"Failed to load JSON skill from {path}: {e}")
            return None

    def _load_from_markdown(self, path: Path) -> Optional[Skill]:
        """Load a skill from a Claude-style SKILL.md file.

        This uses the FileBasedSkill parser implemented in the claude_skill module
        to parse the SKILL.md frontmatter and instructions, and then converts
        it into a core Skill instance.
        """
        try:
            from dbgpt.agent.claude_skill import FileBasedSkill

            file_skill = FileBasedSkill(str(path))
            # Build core Skill from FileBasedSkill
            metadata = file_skill.metadata

            prompt_template = file_skill.get_prompt()
            # Map additional fields from Claude-style SkillMetadata
            # into core SkillMetadata
            # Map Claude-style metadata into core Skill and SkillMetadata
            from .base import Skill, SkillMetadata, SkillType

            # try to coerce skill_type to known SkillType, fallback to Custom
            skill_type_val = SkillType.Custom
            if getattr(metadata, "skill_type", None):
                try:
                    skill_type_val = SkillType(metadata.skill_type)
                except Exception:
                    skill_type_val = SkillType.Custom

            core_meta = SkillMetadata(
                name=metadata.name,
                description=metadata.description,
                version=getattr(metadata, "version", "1.0.0") or "1.0.0",
                author=getattr(metadata, "author", None),
                skill_type=skill_type_val,
                tags=getattr(metadata, "tags", []) or [],
            )

            # Build the Skill copying required fields from FileBasedSkill.metadata
            skill = Skill(
                metadata=core_meta,
                prompt_template=prompt_template,
                required_tools=getattr(metadata, "required_tools", []) or [],
                required_knowledge=getattr(metadata, "required_knowledge", []) or [],
                config={
                    "file_path": str(path),
                    **(getattr(metadata, "config", {}) or {}),
                },
            )

            return skill
        except Exception as e:
            logger.error(f"Failed to load SKILL.md skill from {path}: {e}")
            return None

    def _load_from_yaml(self, path: Path) -> Optional[Skill]:
        """Load skill from YAML file.

        Args:
            path: Path to YAML file.

        Returns:
            Skill instance.
        """
        try:
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            skill = self._create_skill_from_dict(data)
            if skill:
                skill._config["file_path"] = str(path)
            return skill
        except ImportError:
            logger.error("PyYAML not installed, cannot load YAML skills")
            return None
        except Exception as e:
            logger.error(f"Failed to load YAML skill from {path}: {e}")
            return None

    def _create_skill_from_dict(self, data: Dict[str, Any]) -> Optional[Skill]:
        """Create a skill from dictionary data.

        Args:
            data: Skill data dictionary.

        Returns:
            Skill instance.
        """
        try:
            metadata_data = data.get("metadata", {})
            metadata = SkillMetadata(
                name=metadata_data.get("name", "Unknown"),
                description=metadata_data.get("description", ""),
                version=metadata_data.get("version", "1.0.0"),
                author=metadata_data.get("author"),
                skill_type=SkillType(metadata_data.get("skill_type", "custom")),
                tags=metadata_data.get("tags", []),
            )

            return Skill(
                metadata=metadata,
                config=data.get("config"),
            )
        except Exception as e:
            logger.error(f"Failed to create skill from dict: {e}")
            return None


class SkillBuilder:
    """Builder for creating skills programmatically."""

    def __init__(self, name: str, description: str):
        """Initialize skill builder.

        Args:
            name: Skill name.
            description: Skill description.
        """
        self._metadata = SkillMetadata(
            name=name,
            description=description,
        )
        self._prompt_template: Optional[str] = None
        self._required_tools: List[str] = []
        self._required_knowledge: List[str] = []
        self._actions: List[Any] = []
        self._config: Dict[str, Any] = {}

    def with_version(self, version: str) -> "SkillBuilder":
        """Set skill version.

        Args:
            version: Version string.

        Returns:
            Self for chaining.
        """
        self._metadata.version = version
        return self

    def with_author(self, author: str) -> "SkillBuilder":
        """Set skill author.

        Args:
            author: Author name.

        Returns:
            Self for chaining.
        """
        self._metadata.author = author
        return self

    def with_skill_type(self, skill_type: Union[str, SkillType]) -> "SkillBuilder":
        """Set skill type.

        Args:
            skill_type: Skill type.

        Returns:
            Self for chaining.
        """
        if isinstance(skill_type, str):
            skill_type = SkillType(skill_type)
        self._metadata.skill_type = skill_type
        return self

    def with_tags(self, tags: List[str]) -> "SkillBuilder":
        """Set skill tags.

        Args:
            tags: List of tags.

        Returns:
            Self for chaining.
        """
        self._metadata.tags = tags
        return self

    def with_prompt_template(self, prompt_template: str) -> "SkillBuilder":
        """Set prompt template.

        Args:
            prompt_template: Prompt template string.

        Returns:
            Self for chaining.
        """
        self._prompt_template = prompt_template
        return self

    def with_required_tool(self, tool_name: str) -> "SkillBuilder":
        """Add a required tool.

        Args:
            tool_name: Tool name.

        Returns:
            Self for chaining.
        """
        self._required_tools.append(tool_name)
        return self

    def with_required_knowledge(self, knowledge_name: str) -> "SkillBuilder":
        """Add required knowledge.

        Args:
            knowledge_name: Knowledge name.

        Returns:
            Self for chaining.
        """
        self._required_knowledge.append(knowledge_name)
        return self

    def with_action(self, action: Any) -> "SkillBuilder":
        """Add an action.

        Args:
            action: Action instance.

        Returns:
            Self for chaining.
        """
        self._actions.append(action)
        return self

    def with_config(self, config: Dict[str, Any]) -> "SkillBuilder":
        """Set configuration.

        Args:
            config: Configuration dictionary.

        Returns:
            Self for chaining.
        """
        self._config.update(config)
        return self

    def build(self) -> Skill:
        """Build the skill.

        Returns:
            Skill instance.
        """
        from dbgpt.core import PromptTemplate

        prompt_template = None
        if self._prompt_template:
            prompt_template = PromptTemplate.from_template(self._prompt_template)

        return Skill(
            metadata=self._metadata,
            prompt_template=prompt_template,
            required_tools=self._required_tools,
            required_knowledge=self._required_knowledge,
            actions=self._actions,
            config=self._config,
        )

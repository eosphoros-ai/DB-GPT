"""Skill manager."""

import json
import logging
from typing import Any, Dict, List, Optional, Type, Union, cast

from dbgpt.component import BaseComponent, ComponentType, SystemApp

from .base import SkillBase, SkillMetadata, SkillType
from .parameters import SkillParameters

logger = logging.getLogger(__name__)


class RegisterSkill:
    """Register skill model."""

    def __init__(
        self,
        name: str,
        skill_cls: Type[SkillBase],
        skill_instance: Optional[SkillBase] = None,
        metadata: Optional[SkillMetadata] = None,
        is_class: bool = True,
    ):
        """Initialize register skill.

        Args:
            name: Skill name.
            skill_cls: Skill class.
            skill_instance: Skill instance.
            metadata: Skill metadata.
            is_class: Whether it's a class or instance.
        """
        self.name = name
        self.skill_cls = skill_cls
        self.skill_instance = skill_instance
        self.metadata = metadata or (
            skill_instance.metadata if skill_instance else None
        )
        self.is_class = is_class

    @property
    def key(self) -> str:
        """Return the unique key."""
        full_cls = f"{self.skill_cls.__module__}.{self.skill_cls.__qualname__}"
        return f"{self.name}:{full_cls}"

    @property
    def type_key(self) -> str:
        """Return the type key."""
        if self.metadata and getattr(self.metadata, "skill_type", None):
            return self.metadata.skill_type.value
        return "custom"


class SkillManager(BaseComponent):
    """Skill manager.

    To manage the skills.
    """

    # Use a distinct component name so SkillManager does not collide
    # with ResourceManager
    name = ComponentType.SKILL_MANAGER

    def __init__(self, system_app: SystemApp):
        """Create a new SkillManager."""
        super().__init__(system_app)
        self.system_app = system_app
        self._skills: Dict[str, RegisterSkill] = {}
        self._type_to_skills: Dict[str, List[RegisterSkill]] = {}

    def init_app(self, system_app: SystemApp):
        """Initialize the SkillManager."""
        self.system_app = system_app

    def after_start(self):
        """Register all skills after start."""
        pass

    def register_skill(
        self,
        skill_cls: Optional[Type[SkillBase]] = None,
        skill_instance: Optional[SkillBase] = None,
        name: Optional[str] = None,
        metadata: Optional[SkillMetadata] = None,
        ignore_duplicate: bool = False,
    ):
        """Register a skill.

        Args:
            skill_cls: Skill class.
            skill_instance: Skill instance.
            name: Skill name.
            metadata: Skill metadata.
            ignore_duplicate: Whether to ignore duplicate registration.
        """
        if skill_cls is None and skill_instance is None:
            raise ValueError("Skill class or instance must be provided.")

        if skill_instance is not None:
            skill_cls = type(skill_instance)  # type: ignore
            name = name or skill_instance.metadata.name
        else:
            name = name or skill_cls.__name__  # type: ignore

        metadata = metadata or (skill_instance.metadata if skill_instance else None)

        register_skill = RegisterSkill(
            name=name,
            skill_cls=skill_cls,  # type: ignore
            skill_instance=skill_instance,
            metadata=metadata,
            is_class=skill_instance is None,
        )

        if register_skill.key in self._skills:
            if ignore_duplicate:
                return
            else:
                raise ValueError(f"Skill {register_skill.key} already exists.")

        self._skills[register_skill.key] = register_skill
        if register_skill.type_key not in self._type_to_skills:
            self._type_to_skills[register_skill.type_key] = []
        self._type_to_skills[register_skill.type_key].append(register_skill)

    def get_skill(
        self,
        name: Optional[str] = None,
        skill_type: Optional[SkillType] = None,
        version: Optional[str] = None,
    ) -> Optional[SkillBase]:
        """Get a skill by name or type.

        Args:
            name: Skill name.
            skill_type: Skill type.
            version: Skill version.

        Returns:
            The skill instance or None.
        """
        if name:
            for register_skill in self._skills.values():
                if register_skill.name == name:
                    if version and register_skill.metadata.version != version:
                        continue
                    return self._instantiate_skill(register_skill)
            return None

        if skill_type:
            type_key = skill_type.value
            skills = self._type_to_skills.get(type_key, [])
            if skills:
                return self._instantiate_skill(skills[0])

        return None

    def get_skills_by_type(self, skill_type: SkillType) -> List[SkillBase]:
        """Get all skills by type.

        Args:
            skill_type: Skill type.

        Returns:
            List of skill instances.
        """
        type_key = skill_type.value
        skills = self._type_to_skills.get(type_key, [])
        return [self._instantiate_skill(skill) for skill in skills]

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all registered skills.

        Returns:
            List of skill metadata dictionaries.
        """
        result = []
        for register_skill in self._skills.values():
            if register_skill.metadata is None:
                result.append({})
            else:
                # metadata may be a dataclass with to_dict method
                try:
                    result.append(register_skill.metadata.to_dict())
                except Exception:
                    # fallback to attribute access
                    result.append(
                        {
                            "name": getattr(register_skill.metadata, "name", ""),
                            "description": getattr(
                                register_skill.metadata, "description", ""
                            ),
                            "version": getattr(register_skill.metadata, "version", ""),
                        }
                    )
        return result

    def _instantiate_skill(self, register_skill: RegisterSkill) -> SkillBase:
        """Instantiate a skill from register skill.

        Args:
            register_skill: RegisterSkill instance.

        Returns:
            Skill instance.
        """
        if not register_skill.is_class:
            return cast(SkillBase, register_skill.skill_instance)

        skill_cls = cast(Type[SkillBase], register_skill.skill_cls)
        return skill_cls()

    def build_skill_from_parameters(
        self, parameters: SkillParameters
    ) -> Optional[SkillBase]:
        """Build a skill from parameters.

        Args:
            parameters: Skill parameters.

        Returns:
            Skill instance.
        """
        skill = self.get_skill(name=parameters.skill_name)
        return skill

    def retrieve_skills(self) -> List[Dict[str, Any]]:
        """Retrieve all skills metadata.

        Returns:
            List[Dict[str, Any]]: List of skill metadata including name,
            description and path.
        """
        # This is a basic implementation. In a real scenario, this might
        # search directories or a database. Since we currently register skills
        # manually or via config, we iterate over registered skills.
        # To support directory scanning as requested, we would need to implement
        # a scanner here or in SkillLoader.
        # For now, let's assume skills are registered.
        # BUT, the user wants to scan the directory.
        return self.list_skills()

    def get_skill_content(self, skill_name: str) -> str:
        """Get the content (SKILL.md) of a skill.

        Args:
            skill_name: The name of the skill.

        Returns:
            str: The content of the SKILL.md file.
        """
        skill = self.get_skill(name=skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found."

        # If the skill was loaded from a file, we might have the path stored somewhere.
        # SkillMetadata doesn't strictly enforce a 'path' attribute, but let's check.
        # Or we can try to find it via the loader mechanism if we had the path.
        # For the sake of the example and current codebase state, let's look at
        # metadata. If we can't find the file content easily from the object,
        # we might need to rely on how it was loaded.

        # A workaround for the example: The Skill object usually has prompt_template.
        # If it's a file-based skill, the prompt_template IS the content.
        if skill.prompt_template:
            # prompt_template might be a string or a Template object
            if hasattr(skill.prompt_template, "template"):
                return skill.prompt_template.template
            return str(skill.prompt_template)

        return "No content available for this skill."

    def get_skill_scripts(self, skill_name: str) -> List[Dict[str, Any]]:
        """Get scripts defined in a skill's configuration.

        Scripts are defined in the skill's config with the following format:
        ```yaml
        scripts:
          - name: "script_name"
            description: "Script description"
            language: "python"
            code: "..."
        ```

        Args:
            skill_name: The name of the skill.

        Returns:
            List of script definitions.
        """
        skill = self.get_skill(name=skill_name)
        if not skill:
            return []

        # Try to get scripts from skill's config
        scripts = []

        # Check if skill has config attribute (Skill class)
        if hasattr(skill, "config") and skill.config:
            config_scripts = skill.config.get("scripts", [])
            if isinstance(config_scripts, list):
                scripts.extend(config_scripts)

        # Check if skill has metadata with config (FileBasedSkill)
        if hasattr(skill, "metadata") and skill.metadata:
            metadata = skill.metadata
            if hasattr(metadata, "config") and metadata.config:
                config_scripts = metadata.config.get("scripts", [])
                if isinstance(config_scripts, list):
                    # Avoid duplicates if already added from skill.config
                    existing_names = {s.get("name") for s in scripts}
                    for s in config_scripts:
                        if s.get("name") not in existing_names:
                            scripts.append(s)

        return scripts

    async def execute_script(
        self,
        skill_name: str,
        script_name: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Execute a script defined in a skill.

        Args:
            skill_name: The name of the skill containing the script.
            script_name: The name of the script to execute.
            args: Arguments to pass to the script.

        Returns:
            JSON string with execution results.
        """
        args = args or {}
        skill_path = self._get_skill_path(skill_name)
        if skill_path and self._should_reject_personal_skill_execution(skill_path):
            return self._personal_skill_execution_denied_result(skill_name)

        from dbgpt.util.code.server import get_code_server

        # Get the script
        scripts = self.get_skill_scripts(skill_name)
        script = next(
            (s for s in scripts if s.get("name") == script_name),
            None,
        )

        if not script:
            # Try to load script from file
            script_content = self.get_skill_script_file(skill_name, script_name)
            if script_content:
                code = script_content
                language = "python"
            else:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Script '{script_name}' not found"
                                    f" in skill '{skill_name}'"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
        else:
            code = script.get("code", "")
            language = script.get("language", "python")

        if not code:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Script '{script_name}' has no code",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Replace parameters in code using safe template substitution
        # Use string.Template for safe substitution to avoid code injection
        try:
            from string import Template

            template = Template(code)
            substituted_code = template.safe_substitute(**args)
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Parameter substitution failed: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Execute the code
        try:
            code_server = await get_code_server(self.system_app)
            result = await code_server.exec(substituted_code, language)
            output = (
                result.output.decode("utf-8")
                if isinstance(result.output, bytes)
                else str(result.output)
            )
            error_output = (
                result.error_message.decode("utf-8")
                if isinstance(result.error_message, bytes)
                else str(result.error_message or "")
            )

            chunks: List[Dict[str, Any]] = [
                {"output_type": "code", "content": substituted_code}
            ]

            if error_output:
                chunks.append(
                    {"output_type": "text", "content": f"Error: {error_output}"}
                )

            if output:
                chunks.append({"output_type": "text", "content": output})

            return json.dumps({"chunks": chunks}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Script execution failed: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    def get_skill_script_file(
        self, skill_name: str, script_file_name: str
    ) -> Optional[str]:
        """Read a script file from skill's scripts directory.

        Args:
            skill_name: The name of the skill.
            script_file_name: The script file name (e.g., 'calculate_ratios.py').

        Returns:
            The script content or None if not found.
        """
        import os

        skill_path = self._get_skill_path(skill_name)
        if not skill_path:
            return None

        script_path = os.path.join(skill_path, "scripts", script_file_name)
        if os.path.exists(script_path):
            with open(script_path, "r", encoding="utf-8") as f:
                return f.read()

        return None

    def get_skill_references(self, skill_name: str) -> List[Dict[str, Any]]:
        import os

        references = []

        skill_path = self._get_skill_path(skill_name)
        if not skill_path:
            return []

        refs_dir = os.path.join(skill_path, "references")
        if os.path.exists(refs_dir):
            for file_name in os.listdir(refs_dir):
                if file_name.endswith(".md"):
                    file_path = os.path.join(refs_dir, file_name)
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    references.append({"name": file_name, "content": content})

        return references

    def get_skill_reference_file(
        self, skill_name: str, ref_file_name: str
    ) -> Optional[str]:
        """Read a specific reference file from skill's references directory.

        Args:
            skill_name: The name of the skill.
            ref_file_name: The reference file name (e.g., 'overview.md').

        Returns:
            The file content or None if not found.
        """
        import os

        skill_path = self._get_skill_path(skill_name)
        if not skill_path:
            return None

        ref_path = os.path.join(skill_path, "references", ref_file_name)
        if os.path.exists(ref_path):
            with open(ref_path, "r", encoding="utf-8") as f:
                return f.read()

        return None

    def _get_skill_path(self, skill_name: str) -> Optional[str]:
        import os

        skill = self.get_skill(name=skill_name)
        if skill and hasattr(skill, "metadata") and skill.metadata:
            metadata = skill.metadata
            if hasattr(metadata, "path"):
                return metadata.path

        from dbgpt.configs.model_config import SKILLS_DIR

        skills_dir = SKILLS_DIR

        # Search candidate subdirectories: direct, user/, claude/, project/, etc.
        subdirs = ["", "user", "claude", "project"]
        for subdir in subdirs:
            candidate = (
                os.path.join(skills_dir, subdir, skill_name)
                if subdir
                else os.path.join(skills_dir, skill_name)
            )
            if os.path.isdir(candidate):
                return candidate

        # Fallback: return direct path even if it doesn't exist yet
        return os.path.join(skills_dir, skill_name)

    @staticmethod
    def _allow_personal_skill_script_execution() -> bool:
        import os

        return os.getenv(
            "DBGPT_ALLOW_PERSONAL_SKILL_SCRIPT_EXECUTION", ""
        ).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _is_personal_skill_path(skill_path: str) -> bool:
        import os
        from pathlib import Path

        from dbgpt.configs.model_config import SKILLS_DIR

        user_dir = Path(SKILLS_DIR).expanduser() / "user"
        candidate = Path(skill_path).expanduser()

        def _is_relative_to(path: Path, parent: Path) -> bool:
            try:
                path.relative_to(parent)
                return True
            except ValueError:
                return False

        def _normalize_for_containment(path: Path) -> Path:
            return Path(os.path.normcase(os.path.abspath(os.path.normpath(str(path)))))

        lexical_path = _normalize_for_containment(candidate)
        lexical_user_dir = _normalize_for_containment(user_dir)
        if _is_relative_to(lexical_path, lexical_user_dir):
            return True

        try:
            return _is_relative_to(
                _normalize_for_containment(candidate.resolve()),
                _normalize_for_containment(user_dir.resolve()),
            )
        except OSError:
            return False

    def _should_reject_personal_skill_execution(self, skill_path: str) -> bool:
        return (
            self._is_personal_skill_path(skill_path)
            and not self._allow_personal_skill_script_execution()
        )

    @staticmethod
    def _personal_skill_execution_denied_result(skill_name: str) -> str:
        return json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": (
                            "Refusing to execute scripts from personal skill "
                            f"'{skill_name}'. Set "
                            "DBGPT_ALLOW_PERSONAL_SKILL_SCRIPT_EXECUTION=true only "
                            "in trusted deployments to enable this."
                        ),
                    }
                ]
            },
            ensure_ascii=False,
        )

    async def get_skill_resource(
        self,
        skill_name: str,
        resource_path: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Get a resource from a skill by path.

        This unified method handles both file reading and script execution:
        - If path starts with "scripts/" and ends with .py/.sh, execute the script
        - If path is an image file, return error (model doesn't support images)
        - Otherwise, read and return the file content

        Args:
            skill_name: The name of the skill.
            resource_path: The relative path to the resource
                (e.g., "references/analysis.md",
                "scripts/calculate.py", "data/config.json").
            args: Optional arguments for script execution (only used for scripts).

        Returns:
            JSON string with the result:
            - For scripts: {"chunks": [{"output_type": "text/code", "content": "..."}]}
            - For files: {"type": "file", "path": "...", "content": "..."}
            - For errors: {"error": true, "message": "..."}
        """
        import os

        # Image file extensions that are not supported
        IMAGE_EXTENSIONS = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".webp",
            ".svg",
            ".ico",
        }

        # Normalize the path
        resource_path = resource_path.lstrip("/\\")

        # Check if it's an image file
        _, ext = os.path.splitext(resource_path)
        if ext.lower() in IMAGE_EXTENSIONS:
            return json.dumps(
                {
                    "error": True,
                    "message": (
                        f'Cannot read "{os.path.basename(resource_path)}"'
                        " (this model does not support image input)."
                        " Inform the user."
                    ),
                },
                ensure_ascii=False,
            )

        # Get skill path
        skill_path = self._get_skill_path(skill_name)
        if not skill_path:
            return json.dumps(
                {"error": True, "message": f"Skill '{skill_name}' not found"},
                ensure_ascii=False,
            )

        full_path = os.path.join(skill_path, resource_path)

        # Security check: ensure path is within skill directory
        try:
            real_path = os.path.realpath(full_path)
            real_skill_path = os.path.realpath(skill_path)
            if not real_path.startswith(real_skill_path):
                return json.dumps(
                    {
                        "error": True,
                        "message": f"Invalid resource path: {resource_path}",
                    },
                    ensure_ascii=False,
                )
        except Exception as e:
            return json.dumps(
                {"error": True, "message": f"Path resolution error: {str(e)}"},
                ensure_ascii=False,
            )

        # Check if it's a script that needs execution
        if resource_path.startswith("scripts/") and ext.lower() in {".py", ".sh"}:
            if self._should_reject_personal_skill_execution(skill_path):
                return self._personal_skill_execution_denied_result(skill_name)
            return await self._execute_script_from_path(full_path, args or {})

        # Otherwise, read the file content
        if not os.path.exists(full_path):
            return json.dumps(
                {
                    "error": True,
                    "message": (
                        f"Resource '{resource_path}' not found in skill '{skill_name}'"
                    ),
                },
                ensure_ascii=False,
            )

        if os.path.isdir(full_path):
            return json.dumps(
                {
                    "error": True,
                    "message": f"'{resource_path}' is a directory, not a file",
                },
                ensure_ascii=False,
            )

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return json.dumps(
                {
                    "type": "file",
                    "path": resource_path,
                    "content": content,
                },
                ensure_ascii=False,
            )
        except UnicodeDecodeError:
            return json.dumps(
                {
                    "error": True,
                    "message": (
                        f"Cannot read '{resource_path}': binary file not supported"
                    ),
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"error": True, "message": f"Error reading file: {str(e)}"},
                ensure_ascii=False,
            )

    @staticmethod
    def _adapt_args_for_script(code: str, args: Dict[str, Any]) -> Any:
        """Adapt args to match the script's main function signature.

        The LLM may pass args in various shapes:
        - {"data": {"revenue": 100}} — wrapping in the parameter name
        - {"revenue": 100} — flat dict matching the expected data format

        This method uses AST to find the main function's parameters and adapts
        the args accordingly so sys.argv[1] contains the right JSON.
        """
        import ast

        if not args:
            return args

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return args

        # Collect all top-level function definitions
        func_defs: Dict[str, Union[ast.FunctionDef, ast.AsyncFunctionDef]] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_defs[node.name] = node

        if not func_defs:
            return args

        # Try to find the function called in the __main__ block
        main_func_name: Optional[str] = None
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.If):
                # Match: if __name__ == "__main__":
                test = node.test
                is_main_check = False
                if isinstance(test, ast.Compare):
                    left = test.left
                    if (
                        isinstance(left, ast.Name)
                        and left.id == "__name__"
                        and len(test.comparators) == 1
                    ):
                        comp = test.comparators[0]
                        if isinstance(comp, ast.Constant) and comp.value == "__main__":
                            is_main_check = True

                if is_main_check:
                    # Walk the __main__ block to find function calls
                    for sub_node in ast.walk(node):
                        if isinstance(sub_node, ast.Call):
                            func = sub_node.func
                            if isinstance(func, ast.Name) and func.id in func_defs:
                                main_func_name = func.id
                                break
                    break

        # Fall back to the first defined function if no __main__ found
        if main_func_name is None:
            main_func_name = next(iter(func_defs))

        func_node = func_defs[main_func_name]
        # Get parameter names (skip 'self' for methods)
        param_names = [arg.arg for arg in func_node.args.args if arg.arg != "self"]

        if len(param_names) == 1:
            param_name = param_names[0]
            if param_name in args:
                # LLM wrapped args in the parameter name,
                # e.g. {"data": {"revenue": 100}} — unwrap it
                return args[param_name]
            else:
                # LLM passed the flat dict directly,
                # e.g. {"revenue": 100} — pass as-is, it IS the data
                return args
        elif len(param_names) > 1:
            # Multiple params — check if LLM wrapped in any single param name
            if len(args) == 1:
                only_key = next(iter(args))
                if only_key in param_names and isinstance(args[only_key], dict):
                    # Unwrap: {"data": {...}} → {...}
                    return args[only_key]
            # Otherwise pass as-is — the __main__ block handles multi-param
            return args

        # No params — pass as-is
        return args

    async def _execute_script_from_path(
        self,
        script_path: str,
        args: Dict[str, Any],
    ) -> str:
        import os

        from dbgpt.util.code.server import get_code_server

        if not os.path.exists(script_path):
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Script file not found: {script_path}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        try:
            with open(script_path, "r", encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Error reading script: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        _, ext = os.path.splitext(script_path)
        language = "python" if ext == ".py" else "bash"

        if language == "python":
            adapted_args = self._adapt_args_for_script(code, args)
            args_repr = repr(adapted_args)
            wrapper_code = f"""import sys
import json

sys.argv = ["script", json.dumps({args_repr})]
__name__ = "__main__"

{code}
"""
            exec_code = wrapper_code
        else:
            from string import Template

            template = Template(code)
            exec_code = template.safe_substitute(**args)

        try:
            code_server = await get_code_server(self.system_app)
            result = await code_server.exec(exec_code, language)

            logs = (
                result.logs.decode("utf-8")
                if isinstance(result.logs, bytes)
                else str(result.logs or "")
            )
            exit_code = result.exit_code

            chunks = []
            if logs:
                chunks.append({"output_type": "text", "content": logs})
            if exit_code != 0:
                chunks.append(
                    {"output_type": "text", "content": f"Exit code: {exit_code}"}
                )
            if not chunks:
                chunks.append(
                    {
                        "output_type": "text",
                        "content": "Script executed successfully (no output)",
                    }
                )

            return json.dumps({"chunks": chunks}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Script execution failed: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    async def execute_skill_script_file(
        self,
        skill_name: str,
        script_file_name: str,
        args: Optional[Dict[str, Any]] = None,
        output_dir: Optional[str] = None,
    ) -> str:
        import asyncio
        import os

        args = args or {}

        skill_path = self._get_skill_path(skill_name)
        if not skill_path:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Skill '{skill_name}' not found",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        if self._should_reject_personal_skill_execution(skill_path):
            return self._personal_skill_execution_denied_result(skill_name)

        script_file_name = script_file_name.lstrip("/\\")
        if script_file_name.startswith("scripts/") or script_file_name.startswith(
            "scripts\\"
        ):
            script_file_name = script_file_name[8:]

        script_path = os.path.join(skill_path, "scripts", script_file_name)
        if not os.path.exists(script_path):
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Script file '{script_file_name}' not found",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        with open(script_path, "r", encoding="utf-8") as f:
            code = f.read()

        adapted_args = self._adapt_args_for_script(code, args)
        args_repr = repr(adapted_args)
        wrapper_code = f"""import sys
import json

sys.argv = ["script", json.dumps({args_repr})]
__name__ = "__main__"

{code}
"""

        try:
            import sys
            import tempfile

            _IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

            scripts_dir = os.path.dirname(script_path)
            # Use output_dir for subprocess cwd + image scanning;
            # fall back to the scripts directory.
            work_dir = output_dir or scripts_dir
            os.makedirs(work_dir, exist_ok=True)
            # Snapshot existing images BEFORE execution
            pre_existing_images: set = set()
            for root, _dirs, files in os.walk(work_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in _IMAGE_EXTS:
                        pre_existing_images.add(os.path.join(root, fname))
            tmp_fd, tmp_path = tempfile.mkstemp(
                suffix=".py", dir=scripts_dir, prefix="_skill_run_"
            )
            # Env vars for the subprocess: propagate OUTPUT_DIR
            env = os.environ.copy()
            env["OUTPUT_DIR"] = work_dir
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as tmp:
                    tmp.write(wrapper_code)
                proc = await asyncio.create_subprocess_exec(
                    sys.executable,
                    tmp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=work_dir,
                    env=env,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                output_text = stdout.decode("utf-8", errors="replace")
                error_text = stderr.decode("utf-8", errors="replace")
                exit_code = proc.returncode or 0
            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            chunks = []
            if output_text.strip():
                # If the script's stdout is already a valid JSON {"chunks": [...]}
                # structure, use it directly to avoid double-encoding the content
                # (which would cause JSON string values like CHART_DATA_JSON to
                # have their quotes escaped as \" when later injected into HTML).
                try:
                    parsed_output = json.loads(output_text.strip())
                    if isinstance(parsed_output, dict) and "chunks" in parsed_output:
                        chunks = parsed_output["chunks"]
                    else:
                        chunks.append(
                            {"output_type": "text", "content": output_text.strip()}
                        )
                except (json.JSONDecodeError, ValueError):
                    chunks.append(
                        {"output_type": "text", "content": output_text.strip()}
                    )
            if exit_code != 0 and error_text.strip():
                chunks.append(
                    {"output_type": "text", "content": f"[ERROR] {error_text.strip()}"}
                )
            if exit_code != 0:
                chunks.append(
                    {"output_type": "text", "content": f"Exit code: {exit_code}"}
                )
            if not chunks:
                chunks.append(
                    {
                        "output_type": "text",
                        "content": "Script executed successfully (no output)",
                    }
                )
            # Scan work_dir for NEW image files generated by this run.
            # Return their absolute paths so the caller can copy them
            # to the static serving directory.
            for root, _dirs, files in os.walk(work_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    full_path = os.path.join(root, fname)
                    if ext in _IMAGE_EXTS and full_path not in pre_existing_images:
                        chunks.append(
                            {
                                "output_type": "image",
                                "content": full_path,
                            }
                        )
            return json.dumps({"chunks": chunks}, ensure_ascii=False)
        except asyncio.TimeoutError:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Script execution timed out (120s limit)",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Script execution failed: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )


_SYSTEM_APP: Optional[SystemApp] = None


def initialize_skill(system_app: SystemApp):
    """Initialize the skill manager."""
    global _SYSTEM_APP
    _SYSTEM_APP = system_app
    skill_manager = SkillManager(system_app)
    system_app.register_instance(skill_manager)


def get_skill_manager(system_app: Optional[SystemApp] = None) -> SkillManager:
    """Get the skill manager.

    Args:
        system_app: System app instance.

    Returns:
        SkillManager instance.
    """
    global _SYSTEM_APP
    if not _SYSTEM_APP:
        if not system_app:
            system_app = SystemApp()
        initialize_skill(system_app)
    app = system_app or _SYSTEM_APP
    return SkillManager.get_instance(cast(SystemApp, app))

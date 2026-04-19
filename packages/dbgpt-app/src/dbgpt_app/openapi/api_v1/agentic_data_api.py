import io
import json
import logging
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from dbgpt._private.config import Config
from dbgpt._private.pydantic import BaseModel as _BaseModel
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.skill.manage import get_skill_manager
from dbgpt.component import ComponentType
from dbgpt.configs.model_config import SKILLS_DIR, resolve_root_path
from dbgpt.core import PromptTemplate
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt_app.openapi.api_view_model import (
    ConversationVo,
    Result,
)
from dbgpt_serve.datasource.manages import ConnectorManager
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

router = APIRouter()
CFG = Config()
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from dbgpt.agent.core.memory.gpts import GptsMemory

REACT_AGENT_MEMORY_CACHE: Dict[str, "GptsMemory"] = {}

DEFAULT_SKILLS_DIR = SKILLS_DIR
AUTO_DATA_MARKER_PATTERN = re.compile(
    r"###([A-Z0-9_]+)_START###\s*(.*?)\s*###\1_END###", re.DOTALL
)


def _extract_auto_data_markers(text: str) -> tuple[str, Dict[str, str]]:
    """Extract generic marker blocks from script output text.

    Marker format:
        ###KEY_START###...###KEY_END###
    """

    if not text or "###" not in text:
        return text, {}

    extracted: Dict[str, str] = {}

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        value = match.group(2).strip()
        if value:
            extracted[key] = value
        return ""

    cleaned = AUTO_DATA_MARKER_PATTERN.sub(_replace, text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, extracted


async def _execute_skill_script_impl(
    skill_name: str, script_name: str, args: dict
) -> str:
    """Execute a script from a skill (implementation)."""
    skill_manager = get_skill_manager(CFG.SYSTEM_APP)
    result = await skill_manager.execute_script(skill_name, script_name, args)
    return result


@tool(
    description='执行技能中的脚本。参数: {"skill_name": "技能名称", '
    '"script_name": "脚本名称", "args": {参数}}'
)
async def execute_skill_script(skill_name: str, script_name: str, args: dict) -> str:
    """Execute a script from a skill."""
    return await _execute_skill_script_impl(skill_name, script_name, args)


@tool(
    description="获取技能资源文件内容。"
    "根据路径读取技能中的参考文档、配置文件等非脚本资源。"
    '参数: {"skill_name": "技能名称", "resource_path": "资源路径"}'
    "\\n示例:"
    '\\n- 读取参考文档: {"skill_name": "my-skill", '
    '"resource_path": "references/analysis_framework.md"}'
    "\n注意: 执行脚本请使用 shell_interpreter 工具"
)
async def get_skill_resource(
    skill_name: str, resource_path: str, args: Optional[dict] = None
) -> str:
    from dbgpt.agent.skill.manage import get_skill_manager

    try:
        sm = get_skill_manager(CFG.SYSTEM_APP)
        result = await sm.get_skill_resource(skill_name, resource_path, args or {})
        return result
    except Exception as e:
        import json

        return json.dumps(
            {"error": True, "message": f"Error: {str(e)}"},
            ensure_ascii=False,
        )


@tool(
    description="执行技能scripts目录下的脚本文件。参数: "
    '{"skill_name": "技能名称", "script_file_name": "脚本文件名", "args": {参数}}'
)
async def execute_skill_script_file(
    skill_name: str, script_file_name: str, args: Optional[dict] = None
) -> str:
    """Execute a script file from a skill's scripts directory."""
    from dbgpt.agent.skill.manage import get_skill_manager

    try:
        sm = get_skill_manager(CFG.SYSTEM_APP)
        result = await sm.execute_skill_script_file(
            skill_name, script_file_name, args or {}
        )
        return result
    except Exception as e:
        import json

        return json.dumps(
            {"chunks": [{"output_type": "text", "content": f"Error: {str(e)}"}]},
            ensure_ascii=False,
        )


@router.get("/v1/skills/list", response_model=Result)
async def list_skills(
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """List all available skills from the skills directory.

    Returns a list of skills with their metadata, including:
    - id: Unique identifier for the skill
    - name: Display name of the skill
    - description: Brief description of what the skill does
    - version: Skill version
    - author: Skill author
    - skill_type: Type of skill (e.g., data_analysis, chat, coding)
    - tags: List of tags for categorization
    - type: 'official' for claude/ directory, 'personal' for user/ directory
    - file_path: Relative path to the skill file
    """
    from dbgpt.agent.skill.loader import SkillLoader

    skills_data = []
    skills_dir = DEFAULT_SKILLS_DIR
    skills_dir_resolved = Path(skills_dir).expanduser().resolve()

    try:
        loader = SkillLoader()
        skills = loader.load_skills_from_directory(skills_dir, recursive=True)

        for skill in skills:
            if not skill or not skill.metadata:
                continue

            metadata = skill.metadata
            # Determine if the skill is official or personal based on file path
            file_path = getattr(metadata, "file_path", None) or ""
            if not file_path and hasattr(skill, "_config"):
                file_path = skill._config.get("file_path", "")

            # Convert absolute file_path to relative (relative to skills_dir)
            if file_path:
                try:
                    file_path = str(
                        Path(file_path)
                        .expanduser()
                        .resolve()
                        .relative_to(skills_dir_resolved)
                    )
                except Exception:
                    pass

            # Determine type based on directory structure
            skill_type_category = "official"
            if "user/" in file_path or "/user/" in file_path:
                skill_type_category = "personal"
            elif "claude/" in file_path or "/claude/" in file_path:
                skill_type_category = "official"

            # Get skill_type value
            skill_type_val = metadata.skill_type
            if hasattr(skill_type_val, "value"):
                skill_type_val = skill_type_val.value

            skill_info = {
                "id": metadata.name,
                "name": metadata.name,
                "description": metadata.description or "",
                "version": getattr(metadata, "version", "1.0.0") or "1.0.0",
                "author": getattr(metadata, "author", None),
                "skill_type": skill_type_val,
                "tags": getattr(metadata, "tags", []) or [],
                "type": skill_type_category,
                "file_path": file_path,
            }
            skills_data.append(skill_info)

        # Sort skills: official first, then by name
        skills_data.sort(key=lambda x: (0 if x["type"] == "official" else 1, x["name"]))

        return Result.succ(skills_data)
    except Exception as e:
        logger.exception("Failed to load skills from directory")
        return Result.failed(code="E5001", msg=f"Failed to load skills: {str(e)}")


@router.get("/v1/skills/detail", response_model=Result)
async def skill_detail(
    skill_name: str = Query("", description="Skill name"),
    file_path: str = Query("", description="Skill file path"),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Load a skill detail, including file tree and SKILL.md content."""
    if not file_path:
        return Result.failed(code="E4001", msg="file_path is required")

    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()

    # Always treat file_path as relative to skills_dir.
    # If an absolute path was provided (legacy), try to make it relative first.
    fp = Path(file_path).expanduser()
    if fp.is_absolute():
        try:
            fp = fp.resolve().relative_to(skills_dir)
        except Exception:
            return Result.failed(code="E4002", msg="Invalid skill file path")
    target = (skills_dir / fp).resolve()

    # Security: ensure target is under skills_dir
    try:
        target.relative_to(skills_dir)
    except Exception:
        return Result.failed(code="E4002", msg="Invalid skill file path")

    if not target.exists():
        return Result.failed(code="E4040", msg="Skill file not found")

    root_dir = target if target.is_dir() else target.parent

    def build_tree(path: Path, base: Path) -> Dict[str, Any]:
        rel = path.relative_to(base)
        node: Dict[str, Any] = {
            "title": path.name,
            "key": str(rel),
        }
        if path.is_dir():
            children = sorted(
                [p for p in path.iterdir() if not p.name.startswith(".")],
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
            node["children"] = [build_tree(child, base) for child in children]
        return node

    tree = build_tree(root_dir, root_dir)

    skill_md_path = root_dir / "SKILL.md"
    frontmatter = ""
    instructions = ""
    raw_content = ""
    content_type = ""

    if skill_md_path.exists():
        raw_content = skill_md_path.read_text(encoding="utf-8")
        content_type = "skill_md"
        content = raw_content.strip()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                instructions = parts[2].strip()
            else:
                instructions = content
        else:
            instructions = content
    elif target.is_file():
        raw_content = target.read_text(encoding="utf-8")
        suffix = target.suffix.lower()
        if suffix in {".yaml", ".yml"}:
            content_type = "yaml"
            frontmatter = raw_content
        elif suffix == ".json":
            content_type = "json"
            frontmatter = raw_content
        else:
            content_type = "text"
            instructions = raw_content

    metadata: Dict[str, Any] = {}
    try:
        from dbgpt.agent.skill.loader import SkillLoader

        loader = SkillLoader()
        skill = loader.load_skill_from_file(str(target))
        if skill and getattr(skill, "metadata", None):
            try:
                metadata = skill.metadata.to_dict()  # type: ignore[attr-defined]
            except Exception:
                metadata = {
                    "name": getattr(skill.metadata, "name", ""),
                    "description": getattr(skill.metadata, "description", ""),
                    "version": getattr(skill.metadata, "version", ""),
                    "author": getattr(skill.metadata, "author", ""),
                    "skill_type": getattr(skill.metadata, "skill_type", ""),
                    "tags": getattr(skill.metadata, "tags", []) or [],
                }
    except Exception:
        metadata = {}

    if not frontmatter and metadata:
        frontmatter = "\n".join(
            [
                f"name: {metadata.get('name', '')}",
                f"description: {metadata.get('description', '')}",
                f"version: {metadata.get('version', '')}",
                f"author: {metadata.get('author', '')}",
                f"skill_type: {metadata.get('skill_type', '')}",
            ]
        ).strip()

    display_path = str(target)
    display_root = str(root_dir)
    try:
        display_path = str(target.relative_to(skills_dir))
        display_root = str(root_dir.relative_to(skills_dir))
    except Exception:
        pass

    return Result.succ(
        {
            "skill_name": skill_name or metadata.get("name", ""),
            "file_path": display_path,
            "root_dir": display_root,
            "tree": tree,
            "frontmatter": frontmatter,
            "instructions": instructions,
            "raw_content": raw_content,
            "content_type": content_type,
            "metadata": metadata,
        }
    )


def _install_skill_from_dir(src_dir: Path, skill_name: str, user_dir: Path) -> str:
    """Copy an extracted skill directory into the user skills directory.

    Args:
        src_dir (Path): Directory containing the skill's files (already extracted).
        skill_name (str): Name to use for the skill directory under ``user_dir``.
        user_dir (Path): The ``skills/user/`` directory.

    Returns:
        str: Path of the installed skill directory relative to the skills root
             (i.e. ``user/<skill_name>``).
    """
    dest = user_dir / skill_name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src_dir, dest)
    # Return path relative to skills_dir (parent of user_dir)
    return str(dest.relative_to(user_dir.parent))


@router.post("/v1/skills/upload", response_model=Result)
async def skill_upload(
    file: UploadFile = File(...),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Upload a skill package (.zip, .skill) or a single file to pilot/tmp/."""
    if not file.filename:
        return Result.failed(code="E4001", msg="No file provided")

    upload_dir = Path(resolve_root_path("pilot/tmp") or "pilot/tmp").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
    user_dir = skills_dir / "user"
    user_dir.mkdir(parents=True, exist_ok=True)

    filename = file.filename
    suffix = Path(filename).suffix.lower()
    stem = Path(filename).stem

    try:
        content_bytes = await file.read()

        tmp_file = upload_dir / filename
        tmp_file.write_bytes(content_bytes)

        is_archive = False
        if suffix == ".zip":
            is_archive = True
        elif suffix == ".skill":
            buf = io.BytesIO(content_bytes)
            is_archive = zipfile.is_zipfile(buf)

        if is_archive:
            # Reuse the robust _extract_skill_from_zip helper (same one used
            # by the GitHub import endpoint) to avoid the nested-directory bug
            # that the old inline extractall logic suffered from.
            #
            # strict=False: uploaded packages may not contain a SKILL.md yet.
            tmp_zip = upload_dir / f"{uuid.uuid4().hex}.zip"
            tmp_zip.write_bytes(content_bytes)
            try:
                with tempfile.TemporaryDirectory(dir=upload_dir) as tmp_extract:
                    dest_in_tmp = Path(tmp_extract) / "skill"
                    try:
                        dest_name = _extract_skill_from_zip(
                            tmp_zip, subpath=None, dest_dir=dest_in_tmp, strict=False
                        )
                    except ValueError as exc:
                        return Result.failed(code="E4002", msg=str(exc))

                    rel_path = _install_skill_from_dir(dest_in_tmp, dest_name, user_dir)
            finally:
                tmp_zip.unlink(missing_ok=True)

        else:
            dest = user_dir / stem
            dest.mkdir(parents=True, exist_ok=True)

            if suffix in (".md", ".skill"):
                target_name = "SKILL.md"
            else:
                target_name = filename
            target_file = dest / target_name

            target_file.write_bytes(content_bytes)

            rel_path = str(dest.relative_to(skills_dir))

        return Result.succ(
            {
                "file_path": rel_path,
                "tmp_path": str(tmp_file),
                "message": f"Skill uploaded successfully: {rel_path}",
            }
        )
    except Exception as e:
        logger.exception("Failed to upload skill")
        return Result.failed(code="E5002", msg=f"Upload failed: {str(e)}")


def _parse_github_url(
    github_url: str,
) -> "tuple[str, str, str, Optional[str]]":
    """Parse a GitHub or skills.sh URL into (owner, repo, branch, subdir).

    Supported formats:
      - https://github.com/owner/repo
      - https://github.com/owner/repo/tree/<branch>[/optional/sub/dir]
      - https://github.com/owner/repo/blob/<branch>/path/to/FILE.md
      - https://skills.sh/owner/repo
      - https://skills.sh/owner/repo[/skill-name]

    Returns:
        tuple[str, str, str, Optional[str]]
          (owner, repo, branch, subdir) — branch is always a str (defaults to "main")

    Raises:
        ValueError: if the URL is not a recognisable GitHub/skills.sh repo URL.
    """
    parsed = urlparse(github_url)
    is_skills_sh = parsed.netloc in ("skills.sh", "www.skills.sh")
    is_github = parsed.netloc in ("github.com", "www.github.com")

    if not is_github and not is_skills_sh:
        raise ValueError(f"Not a GitHub URL: {github_url!r}")

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ValueError(f"Cannot extract owner/repo from URL: {github_url!r}")

    owner, repo = parts[0], parts[1]
    # Strip '.git' suffix if present
    if repo.endswith(".git"):
        repo = repo[:-4]

    branch: str = "main"
    subdir: Optional[str] = None

    if is_skills_sh:
        # skills.sh: /owner/repo[/skill-name[/more]]
        # Everything after owner/repo is treated as subpath
        if len(parts) >= 3:
            subdir = "/".join(parts[2:])
    else:
        # GitHub
        if len(parts) >= 4 and parts[2] == "tree":
            # /owner/repo/tree/<branch>[/path/to/subdir]
            branch = parts[3]
            if len(parts) >= 5:
                subdir = "/".join(parts[4:])
        elif len(parts) >= 4 and parts[2] == "blob":
            # /owner/repo/blob/<branch>/path/to/FILE.md — strip filename
            branch = parts[3]
            if len(parts) >= 6:
                # Keep everything except the last component (the filename)
                subdir = "/".join(parts[4:-1])
            # If exactly 5 parts: blob/<branch>/filename — no subdir

    return owner, repo, branch, subdir


def _construct_download_url(owner: str, repo: str, branch: str) -> str:
    """Return the GitHub archive ZIP download URL for the given branch.

    Args:
        owner (str): Repository owner/organisation.
        repo (str): Repository name.
        branch (str): Branch name.

    Returns:
        str: URL pointing to the ZIP archive for the branch.
    """
    return f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"


def _is_macos_junk(name: str) -> bool:
    """Return True if the archive entry is a macOS metadata artifact."""
    parts = name.split("/")
    return any(p == "__MACOSX" or p.startswith("._") for p in parts)


def _extract_skill_from_zip(
    zip_path: "Path",
    subpath: "Optional[str]",
    dest_dir: "Path",
    strict: bool = True,
) -> str:
    """Extract a skill from a ZIP archive into ``dest_dir``.

    The ZIP is expected to have a single top-level directory (e.g.
    ``repo-main/``).  That top-level directory is stripped when extracting so
    that the files inside it land directly in ``dest_dir``.

    When ``subpath`` is given, only the files under
    ``{top_dir}/{subpath}/`` are extracted (again, stripped to ``dest_dir``).

    macOS metadata entries (``__MACOSX/`` directories and ``._*`` files) are
    automatically filtered out before any directory-structure analysis so they
    do not cause spurious nested directories.

    Args:
        zip_path (Path): Path to the ZIP file on disk.
        subpath (Optional[str]): Relative sub-directory inside the archive
            (after stripping the top-level dir) that contains the skill.
            Pass ``None`` to use the root of the archive.
        dest_dir (Path): Directory into which the skill files are extracted.
            It is created if it does not exist; if it already exists its
            contents are removed before extraction.
        strict (bool): When ``True`` (default), raise ``ValueError`` if no
            ``SKILL.md`` is found in the archive.  When ``False``, skip the
            ``SKILL.md`` validation — useful for uploading generic skill
            packages that may not yet contain a ``SKILL.md``.

    Returns:
        str: The skill name derived from ``subpath`` (last component) or from
        the top-level archive directory name.

    Raises:
        ValueError: If the archive contains path-traversal sequences.
        ValueError: If no ``SKILL.md`` is found after extraction (only when
            ``strict=True``).
        ValueError: If the archive root contains multiple sub-directories with
            ``SKILL.md`` files and no ``subpath`` was specified (the error
            message lists the available sub-directory names).
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        all_names = zf.namelist()

        # Security: reject any path-traversal entries
        for name in all_names:
            normalized = os.path.normpath(name)
            if normalized.startswith("..") or ".." in normalized.split(os.sep):
                raise ValueError(f"Unsafe path in archive: {name!r}")

        # Filter out macOS metadata artifacts before analysing structure
        valid_names = [n for n in all_names if not _is_macos_junk(n)]

        # Detect the single top-level directory (GitHub archives always have one)
        top_dirs = {n.split("/")[0] for n in valid_names if "/" in n}
        archive_root: Optional[str] = top_dirs.pop() if len(top_dirs) == 1 else None

        # Build the prefix inside the archive that maps to dest_dir
        if subpath:
            skill_prefix = (
                f"{archive_root}/{subpath}/" if archive_root else f"{subpath}/"
            )
            skill_name = subpath.split("/")[-1]
        else:
            skill_prefix = f"{archive_root}/" if archive_root else ""
            skill_name = archive_root or dest_dir.name

        # Check whether SKILL.md exists under the chosen prefix
        skill_md_entry = next(
            (n for n in valid_names if n == skill_prefix + "SKILL.md"),
            None,
        )

        if skill_md_entry is None and not subpath:
            # No SKILL.md at root — scan one level of subdirectories
            subdirs_with_skill = []
            for name in valid_names:
                if not name.startswith(skill_prefix):
                    continue
                rel = name[len(skill_prefix) :]
                parts = rel.split("/")
                if len(parts) == 2 and parts[1] == "SKILL.md":
                    subdirs_with_skill.append(parts[0])

            if len(subdirs_with_skill) > 1:
                raise ValueError(
                    "Multiple skills found. Specify a subpath. "
                    "Available: " + ", ".join(sorted(subdirs_with_skill))
                )

            # If exactly one sub-directory has SKILL.md, use it automatically
            if len(subdirs_with_skill) == 1:
                only_subdir = subdirs_with_skill[0]
                skill_prefix = f"{skill_prefix}{only_subdir}/"
                skill_name = only_subdir
                skill_md_entry = skill_prefix + "SKILL.md"

        if strict and skill_md_entry is None:
            raise ValueError(
                "No SKILL.md found in the archive"
                + (f" under '{subpath}'" if subpath else "")
                + ". Make sure the skill directory contains a SKILL.md file."
            )

        # Prepare dest_dir: remove existing content then (re-)create
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Extract valid members individually (no extractall) for security
        for member in valid_names:
            if not member.startswith(skill_prefix) or member == skill_prefix:
                continue
            rel = member[len(skill_prefix) :]
            if not rel:
                continue
            target = dest_dir / rel
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(member))

    return skill_name


@router.post("/v1/skills/import_github", response_model=Result)
async def skill_import_from_github_v2(
    request: Request,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Import a skill from a GitHub or skills.sh URL.

    Accepts ``{ "url": "..." }`` from the frontend, downloads the repository
    ZIP, extracts the skill, installs it to ``skills/user/<name>/``, and
    returns a success response.

    This endpoint:

    - Accepts a raw JSON body ``{ "url": "..." }`` (no Pydantic model).
    - Supports branch fallback: tries ``main`` first, then ``master`` if 404.
    - Enforces a 50 MB download size limit.
    - Delegates extraction/installation to the modular helpers
      ``_extract_skill_from_zip`` and ``_install_skill_from_dir``.

    Error codes:
        - ``E4001``: Empty URL.
        - ``E4003``: Malformed or non-GitHub/skills.sh URL.
        - ``E4004``: ``SKILL.md`` not found in the downloaded content.
        - ``E4005``: Download failed or size limit exceeded.
        - ``E5002``: Unexpected server-side error.
    """
    import httpx

    # --- parse JSON body --------------------------------------------------------
    body = await request.json()
    url = body.get("url", "").strip()
    if not url:
        return Result.failed(code="E4001", msg="URL must not be empty")

    # --- parse URL --------------------------------------------------------------
    try:
        owner, repo, branch, subpath = _parse_github_url(url)
    except ValueError as exc:
        return Result.failed(code="E4003", msg=str(exc))

    # --- resolve dirs -----------------------------------------------------------
    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
    user_dir = skills_dir / "user"
    user_dir.mkdir(parents=True, exist_ok=True)

    upload_dir = Path(resolve_root_path("pilot/tmp") or "pilot/tmp").resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    # --- download with branch fallback (main → master) --------------------------
    zip_path: Optional[Path] = None
    tmp_dir_obj = None  # tempfile.TemporaryDirectory kept alive until finally

    try:
        zip_url = _construct_download_url(owner, repo, branch)

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(120.0),
        ) as client:
            response = await client.get(zip_url)

            # Branch fallback: if the resolved branch gives 404, try "master"
            if response.status_code == 404 and branch == "main":
                fallback_branch = "master"
                fallback_url = _construct_download_url(owner, repo, fallback_branch)
                response = await client.get(fallback_url)
                if response.status_code == 200:
                    branch = fallback_branch
                    zip_url = fallback_url

            if response.status_code != 200:
                return Result.failed(
                    code="E4005",
                    msg=(
                        f"Failed to download {zip_url!r}: HTTP {response.status_code}"
                    ),
                )

            content_bytes = response.content

        # --- size limit check ---------------------------------------------------
        if len(content_bytes) > 50 * 1024 * 1024:
            return Result.failed(
                code="E4005",
                msg=(
                    f"Download size {len(content_bytes) // (1024 * 1024)} MB "
                    "exceeds the 50 MB limit"
                ),
            )

        # --- save raw zip to tmp ------------------------------------------------
        zip_filename = f"{repo}-{branch}.zip"
        zip_path = upload_dir / zip_filename
        zip_path.write_bytes(content_bytes)

        # --- extract into a temp directory, then install ------------------------
        tmp_dir_obj = tempfile.TemporaryDirectory(dir=upload_dir)
        dest_dir_in_temp = Path(tmp_dir_obj.name) / "skill"
        dest_dir_in_temp.mkdir(parents=True, exist_ok=True)

        try:
            skill_name = _extract_skill_from_zip(zip_path, subpath, dest_dir_in_temp)
        except ValueError as exc:
            err_msg = str(exc)
            if "SKILL.md" in err_msg:
                return Result.failed(code="E4004", msg=err_msg)
            return Result.failed(code="E4003", msg=err_msg)

        rel_path = _install_skill_from_dir(dest_dir_in_temp, skill_name, user_dir)

        return Result.succ(
            {
                "file_path": rel_path,
                "message": f"Skill imported successfully from GitHub: {rel_path}",
            }
        )

    except httpx.RequestError as exc:
        logger.exception("Network error while downloading skill from GitHub")
        return Result.failed(
            code="E4005", msg=f"Network error downloading skill: {str(exc)}"
        )
    except Exception as exc:
        logger.exception("Failed to import skill from GitHub (v2)")
        return Result.failed(code="E5002", msg=f"Import failed: {str(exc)}")
    finally:
        # Clean up temp zip file
        if zip_path is not None:
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass
        # Clean up temp extraction directory
        if tmp_dir_obj is not None:
            try:
                tmp_dir_obj.cleanup()
            except Exception:
                pass


def _sse_event(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _react_agent_stream(
    dialogue: ConversationVo,
) -> AsyncGenerator[str, None]:
    import asyncio

    from dbgpt.agent import AgentContext, AgentMemory, AgentMessage
    from dbgpt.agent.claude_skill import get_registry, load_skills_from_dir
    from dbgpt.agent.core.memory.gpts import (
        DefaultGptsPlansMemory,
        GptsMemory,
    )
    from dbgpt.agent.expand.actions.react_action import Terminate
    from dbgpt.agent.expand.react_agent import ReActAgent
    from dbgpt.agent.resource import ToolPack, tool
    from dbgpt.agent.resource.base import AgentResource, ResourceType
    from dbgpt.agent.resource.manage import get_resource_manager
    from dbgpt.agent.util.llm.llm import LLMConfig, LLMStrategyType
    from dbgpt.agent.util.react_parser import ReActOutputParser
    from dbgpt.core import StorageConversation
    from dbgpt.model.cluster.client import DefaultLLMClient
    from dbgpt.util.code.server import get_code_server
    from dbgpt_serve.agent.agents.db_gpts_memory import MetaDbGptsMessageMemory
    from dbgpt_serve.conversation.serve import Serve as ConversationServe

    step = 0
    user_input = dialogue.user_input
    if not isinstance(user_input, str):
        user_input = str(user_input or "")

    file_path = None
    knowledge_space = None
    skill_name = None
    database_name = None
    if dialogue.ext_info and isinstance(dialogue.ext_info, dict):
        file_path = dialogue.ext_info.get("file_path")
        skill_name = dialogue.ext_info.get("skill_name")
        # Support multiple field names for knowledge space
        knowledge_space = (
            dialogue.ext_info.get("knowledge_space")
            or dialogue.ext_info.get("knowledge_space_name")
            or dialogue.ext_info.get("knowledge_space_id")
        )
        database_name = dialogue.ext_info.get("database_name")

    def infer_phase(action: str) -> str:
        """根据 action 名称推断所属阶段，返回自由文本描述"""
        if not action:
            return "执行操作"
        action_lower = action.lower()
        if any(kw in action_lower for kw in ["think", "plan", "reason", "analyze"]):
            return "分析与规划"
        elif any(kw in action_lower for kw in ["skill", "load_skill"]):
            return "加载技能"
        elif any(
            kw in action_lower
            for kw in [
                "sql",
                "query",
                "database",
                "execute",
                "read",
                "write",
                "calculate",
            ]
        ):
            return "执行操作"
        else:
            return "执行操作"

    def build_step(title: str, detail: str, phase: str = None):
        nonlocal step
        step += 1
        step_id = f"step-{step}"
        event_data = {
            "type": "step.start",
            "step": step,
            "id": step_id,
            "title": title,
            "detail": detail,
        }
        if phase:
            event_data["phase"] = phase
        return step_id, _sse_event(event_data)

    def step_output(detail: str):
        return _sse_event({"type": "step.output", "step": step, "detail": detail})

    def step_chunk(step_id: str, output_type: str, content: Any):
        return _sse_event(
            {
                "type": "step.chunk",
                "id": step_id,
                "output_type": output_type,
                "content": content,
            }
        )

    def step_done(step_id: str, status: str = "done"):
        return _sse_event({"type": "step.done", "id": step_id, "status": status})

    def step_meta(
        step_id: str,
        thought: Optional[str],
        action: Optional[str],
        action_input: Optional[str],
        title: Optional[str] = None,
    ):
        return _sse_event(
            {
                "type": "step.meta",
                "id": step_id,
                "thought": thought,
                "action": action,
                "action_input": action_input,
                "title": title,
            }
        )

    def chunk_text(text: str, max_len: int = 800) -> List[str]:
        if not text:
            return []
        chunks: List[str] = []
        start = 0
        while start < len(text):
            chunks.append(text[start : start + max_len])
            start += max_len
        return chunks

    def emit_tool_chunks(step_id: str, content: Any) -> List[str]:
        raw_chunks: List[str] = []
        if content is None:
            return raw_chunks
        parsed = None
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = None
        if isinstance(parsed, dict) and isinstance(parsed.get("chunks"), list):
            for item in parsed["chunks"]:
                if not isinstance(item, dict):
                    continue
                output_type = item.get("output_type") or "text"
                payload = item.get("content")
                if output_type in ["code", "markdown"] and isinstance(payload, str):
                    # Send code and markdown as a single chunk — never split it.
                    raw_chunks.append(step_chunk(step_id, output_type, payload))
                elif output_type in ["text"] and isinstance(payload, str):
                    for chunk in chunk_text(payload, max_len=800):
                        raw_chunks.append(step_chunk(step_id, output_type, chunk))
                else:
                    raw_chunks.append(step_chunk(step_id, output_type, payload))
            return raw_chunks
        if isinstance(content, str) and content:
            for chunk in chunk_text(content, max_len=800):
                raw_chunks.append(step_chunk(step_id, "text", chunk))
        return raw_chunks

    skills_dir = DEFAULT_SKILLS_DIR
    registry = get_registry()

    # Step 1: Pre-load skills
    load_skills_from_dir(skills_dir, recursive=True)
    all_skills = registry.list_skills()

    # Step 2: Get business tools from ResourceManager
    rm = get_resource_manager(CFG.SYSTEM_APP)
    business_tools: List[Any] = []
    try:
        # Get all registered tool resources from ResourceManager
        tool_resources = rm._type_to_resources.get("tool", [])
        for reg_resource in tool_resources:
            if reg_resource.resource_instance is not None:
                business_tools.append(reg_resource.resource_instance)
    except Exception:
        pass  # If no business tools, continue with empty list

    # Step 3: Load knowledge space resource if specified in ext_info
    knowledge_resources: List[Any] = []
    knowledge_context = ""
    if knowledge_space:
        try:
            from dbgpt_serve.agent.resource.knowledge import (
                KnowledgeSpaceRetrieverResource,
            )

            knowledge_resource = KnowledgeSpaceRetrieverResource(
                name=f"knowledge_space_{knowledge_space}",
                space_name=knowledge_space,
                top_k=4,
                system_app=CFG.SYSTEM_APP,
            )
            knowledge_resources.append(knowledge_resource)
            knowledge_context = f"""
## Knowledge Base
- Knowledge space: {knowledge_resource.retriever_name or knowledge_space}
- Description: {knowledge_resource.retriever_desc or "Knowledge retrieval available"}
- You can use the 'knowledge_retrieve' tool to search this knowledge base.
"""
            logger.info(
                f"Loaded knowledge space resource: {knowledge_space} "
                f"(name: {knowledge_resource.retriever_name})"
            )
        except Exception as e:
            logger.warning(f"Failed to load knowledge space resource: {e}", exc_info=e)
            knowledge_context = f"""
## Knowledge Base
- Warning: Failed to load knowledge space '{knowledge_space}'. Error: {str(e)}
"""

    # Step 4: Load database connector if specified in ext_info
    database_connector = None
    database_context = ""
    if database_name:
        try:
            local_db_manager = ConnectorManager.get_instance(CFG.SYSTEM_APP)
            database_connector = local_db_manager.get_connector(database_name)
            table_names = list(database_connector.get_table_names())
            table_info = database_connector.get_table_info_no_throw()
            database_context = f"""
## 数据库信息
- 数据库名: {database_name}
- 可用表: {", ".join(table_names)}
- 表结构:
{table_info}
- 使用 'sql_query' 工具执行 SQL 查询
- **只允许 SELECT 查询，禁止 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE**
"""
            logger.info(
                f"Loaded database connector: {database_name} "
                f"(tables: {', '.join(table_names)})"
            )
        except Exception as e:
            logger.warning(f"Failed to load database connector: {e}", exc_info=e)
            database_context = f"""
## 数据库
- 警告: 加载数据库 '{database_name}' 失败。错误: {str(e)}
"""

    react_state: Dict[str, Any] = {
        "skills_loaded": True,  # Skills are pre-loaded now
        "matched": None,
        "skill_prompt": None,
        "file_path": file_path,
    }

    # Pre-select skill if skill_name provided in ext_info
    pre_matched_skill = None
    if skill_name:
        pre_matched_skill = registry.get_skill(skill_name)
        if not pre_matched_skill:
            # Try case-insensitive match
            for s in registry.list_skills():
                if s.name.lower() == skill_name.lower():
                    pre_matched_skill = registry.get_skill(s.name)
                    break
        if pre_matched_skill:
            react_state["matched"] = pre_matched_skill
            react_state["skill_prompt"] = pre_matched_skill.get_prompt()
            logger.info(f"Pre-selected skill from ext_info: {skill_name}")

    # Build skills_context based on whether skill is pre-selected
    if pre_matched_skill:
        # User specified a skill: show only the selected skill
        skills_context = (
            f"- {pre_matched_skill.metadata.name}: "
            f"{pre_matched_skill.metadata.description}"
        )
    else:
        # User did not specify a skill: show all available skills
        skills_context = (
            "\n".join([f"- {s.name}: {s.description}" for s in all_skills])
            if all_skills
            else "No skills available."
        )

    def _mentions_excel(text: str) -> bool:
        lowered = text.lower()
        keywords = [
            "excel",
            "xlsx",
            "xls",
            "spreadsheet",
            "workbook",
            "sheet",
            "工作表",
            "表格",
            "电子表格",
        ]
        return any(keyword in lowered for keyword in keywords)

    def _is_excel_skill(meta) -> bool:
        name = (meta.name or "").lower()
        desc = (meta.description or "").lower()
        tags = [tag.lower() for tag in (meta.tags or [])]
        return any(
            token in name or token in desc or token in tags
            for token in ["excel", "xlsx", "xls", "spreadsheet"]
        )

    @tool(
        description="Select the most relevant skill based on user query from the "
        "available skills list in system prompt."
    )
    def select_skill(query: str) -> str:
        match_input = query or ""
        if react_state.get("file_path"):
            match_input = f"{match_input} excel xlsx spreadsheet file"
        matched = registry.match_skill(match_input)
        if (
            matched
            and _is_excel_skill(matched.metadata)
            and not (_mentions_excel(query) or react_state.get("file_path"))
        ):
            matched = None
        react_state["matched"] = matched
        if matched:
            detail = (
                f"Matched: {matched.metadata.name} - {matched.metadata.description}"
            )
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": detail}]},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "chunks": [
                    {
                        "output_type": "text",
                        "content": "No skill matched; proceed without skill",
                    }
                ]
            },
            ensure_ascii=False,
        )

    @tool(
        description="Load skill content by skill name and file path. "
        "Returns the SKILL.md content of the specified skill. "
        '参数: {"skill_name": "技能名称", "file_path": "技能文件路径"}'
    )
    def load_skill(skill_name: str, file_path: str) -> str:
        """Load the skill content (SKILL.md) by skill name and file path.

        Args:
            skill_name: The name of the skill to load.
            file_path: The file path of the skill.
        """
        from dbgpt.agent.claude_skill import get_registry

        # Try to get skill from registry
        registry = get_registry()
        matched = registry.get_skill(skill_name)

        # If not found, try case-insensitive match
        if not matched:
            for s in registry.list_skills():
                if s.name.lower() == skill_name.lower():
                    matched = registry.get_skill(s.name)
                    break

        if not matched:
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

        # Update react_state for compatibility with existing logic
        react_state["matched"] = matched
        react_state["skill_prompt"] = matched.get_prompt()

        # Build response content
        chunks = [
            {
                "output_type": "text",
                "content": f"Skill: {matched.metadata.name}",
            },
            {
                "output_type": "text",
                "content": f"File path: {file_path}",
            },
            {"output_type": "text", "content": "---"},
        ]

        # Add skill content/prompt
        if matched.instructions:
            chunks.append({"output_type": "markdown", "content": matched.instructions})
        elif matched.prompt_template:
            prompt_text = (
                matched.prompt_template.template
                if hasattr(matched.prompt_template, "template")
                else str(matched.prompt_template)
            )
            chunks.append({"output_type": "markdown", "content": prompt_text})

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Load uploaded file info if provided.")
    def load_file() -> str:
        if not react_state.get("file_path"):
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No file uploaded"}]},
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "chunks": [
                    {"output_type": "text", "content": react_state["file_path"]},
                    {
                        "output_type": "text",
                        "content": "File path provided by user upload",
                    },
                ]
            },
            ensure_ascii=False,
        )

    @tool(description="Execute quick analysis on uploaded Excel/CSV file.")
    async def execute_analysis() -> str:
        matched = react_state.get("matched")
        if not react_state.get("file_path"):
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": "No file to analyze"}]},
                ensure_ascii=False,
            )
        if matched and not _is_excel_skill(matched.metadata):
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "Selected skill is not for Excel analysis",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        code_server = await get_code_server(CFG.SYSTEM_APP)
        analysis_code = """
import json
import pandas as pd

file_path = r"{file_path}"
if file_path.lower().endswith((".xls", ".xlsx")):
    df = pd.read_excel(file_path)
else:
    df = pd.read_csv(file_path)
summary = {{
    "shape": list(df.shape),
    "columns": list(df.columns),
    "dtypes": {{col: str(dtype) for col, dtype in df.dtypes.items()}},
    "head": df.head(5).to_dict(orient="records"),
}}
print(json.dumps(summary, ensure_ascii=False))
""".format(file_path=react_state["file_path"])
        result = await code_server.exec(analysis_code, "python")
        output_text = (
            result.output.decode("utf-8") if isinstance(result.output, bytes) else ""
        )
        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": analysis_code.strip()}
        ]
        if output_text:
            try:
                summary = json.loads(output_text)
                chunks.append({"output_type": "json", "content": summary})
                head_rows = summary.get("head")
                columns = summary.get("columns")
                if isinstance(head_rows, list) and isinstance(columns, list):
                    chunks.append(
                        {
                            "output_type": "table",
                            "content": {
                                "columns": [
                                    {"title": col, "dataIndex": col, "key": col}
                                    for col in columns
                                ],
                                "rows": head_rows,
                            },
                        }
                    )
                numeric_columns = [
                    col
                    for col, dtype in (summary.get("dtypes") or {}).items()
                    if "int" in dtype or "float" in dtype
                ]
                if numeric_columns and isinstance(head_rows, list):
                    series_col = numeric_columns[0]
                    data = [
                        {"x": idx + 1, "y": row.get(series_col)}
                        for idx, row in enumerate(head_rows)
                        if row.get(series_col) is not None
                    ]
                    if data:
                        chunks.append(
                            {
                                "output_type": "chart",
                                "content": {
                                    "data": data,
                                    "xField": "x",
                                    "yField": "y",
                                },
                            }
                        )
            except Exception:
                chunks.append({"output_type": "text", "content": output_text})
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Resolve required tools for the selected skill.")
    def load_tools() -> str:
        matched = react_state.get("matched")
        rm = get_resource_manager(CFG.SYSTEM_APP)
        required_tools = matched.metadata.required_tools if matched else []
        if not required_tools:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No required tools specified",
                        }
                    ]
                },
                ensure_ascii=False,
            )
        loaded = []
        failed = []
        for tool_name in required_tools:
            try:
                rm.build_resource_by_type(
                    ResourceType.Tool.value,
                    AgentResource(type=ResourceType.Tool.value, value=tool_name),
                )
                loaded.append(tool_name)
            except Exception as e:
                failed.append(f"{tool_name} ({e})")
        chunks = []
        if loaded:
            chunks.append(
                {"output_type": "text", "content": f"Loaded: {', '.join(loaded)}"}
            )
        if failed:
            chunks.append(
                {"output_type": "text", "content": f"Failed: {', '.join(failed)}"}
            )
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(description="Execute a tool by name with JSON args.")
    async def execute_tool(tool_name: str, args: dict) -> str:
        rm = get_resource_manager(CFG.SYSTEM_APP)
        try:
            tool_resource = rm.build_resource_by_type(
                ResourceType.Tool.value,
                AgentResource(type=ResourceType.Tool.value, value=tool_name),
            )
            tool_pack = ToolPack([tool_resource])
            result = await tool_pack.async_execute(resource_name=tool_name, **args)
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": str(result)}]},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Tool execute failed: {e}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    @tool(
        description="Retrieve relevant information from the knowledge base. "
        "Use this tool when the user question involves content that may be "
        'in the knowledge base. Parameters: {{"query": "search query"}}'
    )
    async def knowledge_retrieve(query: str) -> str:
        if not knowledge_resources:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No knowledge base available",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        resource = knowledge_resources[0]
        try:
            chunks = await resource.retrieve(query)
            if chunks:
                content = "\n".join(
                    [f"[{i + 1}] {chunk.content}" for i, chunk in enumerate(chunks[:5])]
                )
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Retrieved {len(chunks)} relevant documents"
                                ),
                            },
                            {"output_type": "markdown", "content": content},
                        ]
                    },
                    ensure_ascii=False,
                )
            else:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": "No relevant information found",
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
                            "content": f"Knowledge retrieval failed: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    @tool(
        description=(
            "对用户选择的数据库执行 SQL 查询（仅支持 SELECT）。"
            '参数: {"sql": "SELECT 语句"}'
        )
    )
    def sql_query(sql: str) -> str:
        """Execute a read-only SQL query against the selected database."""
        if database_connector is None:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "未选择数据库，请先在左侧面板选择一个数据源。",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        sql_stripped = sql.strip().rstrip(";")
        sql_upper = sql_stripped.upper().lstrip()
        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "TRUNCATE",
            "CREATE",
            "GRANT",
            "REVOKE",
        ]
        for kw in forbidden:
            if sql_upper.startswith(kw):
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"安全限制: 不允许执行 {kw} 语句，"
                                    f"仅支持 SELECT 查询。"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        try:
            result = database_connector.run(sql_stripped)
            if not result:
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "text", "content": "查询返回空结果。"}
                        ]
                    },
                    ensure_ascii=False,
                )

            # result[0] = column names, result[1:] = data rows
            columns = result[0]
            col_names = [str(c[0]) if isinstance(c, tuple) else str(c) for c in columns]
            rows = result[1:]

            # Build markdown table
            header = "| " + " | ".join(col_names) + " |"
            separator = "| " + " | ".join(["---"] * len(col_names)) + " |"
            md_rows = []
            for row in rows[:50]:
                md_rows.append("| " + " | ".join(str(v) for v in row) + " |")
            table = "\n".join([header, separator] + md_rows)
            if len(rows) > 50:
                table += f"\n\n（仅显示前 50 行，共 {len(rows)} 行）"

            return json.dumps(
                {"chunks": [{"output_type": "markdown", "content": table}]},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"SQL 执行失败: {str(e)}",
                        }
                    ]
                },
                ensure_ascii=False,
            )

    def _try_repair_truncated_code(raw_code: str) -> Optional[str]:
        """Attempt to fix code that was truncated by the LLM's token limit.

        Common symptoms: unterminated string literals, unclosed brackets/parens.
        Strategy:
          1. Remove the last (likely incomplete) logical line.
          2. Close any remaining open brackets / parentheses.
          3. Re-compile. If it passes, return the repaired code.
        Returns None if repair is not possible.
        """

        lines = raw_code.split("\n")
        # Try progressively removing trailing lines (up to 10) to find a
        # clean cut-off point.
        for trim in range(1, min(11, len(lines))):
            candidate_lines = lines[: len(lines) - trim]
            if not candidate_lines:
                continue
            candidate = "\n".join(candidate_lines)

            # Strip any trailing incomplete string by trying to tokenize
            # and removing broken tail tokens.
            # Close unmatched brackets/parens/braces
            open_chars = {"(": ")", "[": "]", "{": "}"}
            close_chars = set(open_chars.values())
            stack: list = []
            for ch in candidate:
                if ch in open_chars:
                    stack.append(open_chars[ch])
                elif ch in close_chars:
                    if stack and stack[-1] == ch:
                        stack.pop()

            # Append closing chars in reverse order
            if stack:
                candidate += "\n" + "".join(reversed(stack))

            try:
                compile(candidate, "<repair>", "exec")
                return candidate
            except SyntaxError:
                continue
        return None

    @tool(
        description="Execute Python code for data analysis and computation. "
        "Supports pandas, numpy, matplotlib, json, os, etc. "
        "Use this tool when you need to run Python code to process data, "
        "generate charts, or perform calculations. "
        'Parameters: {{"code": "python code string"}}'
    )
    async def code_interpreter(code: str) -> str:
        """Execute arbitrary Python code and return stdout/stderr.

        Runs in a subprocess using the project's Python interpreter,
        so all installed packages (pandas, numpy, etc.) are available.
        CRITICAL: Each call is completely independent — variables do NOT
        persist between calls. Every code snippet MUST include all necessary
        data loading (e.g. df = pd.read_csv(FILE_PATH)) and processing.
        Never assume df or any other variable already exists.
        Always print() results you want to see in the output.
        """
        import asyncio
        import shutil
        import sys
        import uuid

        from dbgpt.configs.model_config import PILOT_PATH, STATIC_MESSAGE_IMG_PATH

        if not code or not code.strip():
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No code provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Use persistent work dir under pilot/tmp/{conv_id} so files
        # survive across calls and can be referenced later (e.g. in HTML).
        cid = react_state.get("conv_id") or "default"
        work_dir = os.path.join(PILOT_PATH, "tmp", cid)
        os.makedirs(work_dir, exist_ok=True)

        # Collect image files that existed BEFORE this run
        IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
        pre_existing_images: set = set()
        for root, _dirs, files in os.walk(work_dir):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in IMAGE_EXTS:
                    pre_existing_images.add(os.path.join(root, f))

        preamble_lines = [
            "import json",
            "import os",
            "import pandas as pd",
            "import numpy as np",
            f'PLOT_DIR = r"{work_dir}"',
            "os.makedirs(PLOT_DIR, exist_ok=True)",
        ]
        fp = react_state.get("file_path")
        if fp:
            preamble_lines.append(f'FILE_PATH = r"{fp}"')
        preamble = "\n".join(preamble_lines) + "\n"
        full_code = preamble + code

        try:
            compile(full_code, "<code_interpreter>", "exec")
        except SyntaxError as se:
            # Attempt auto-repair for truncated code (common with long LLM
            # outputs that hit the token limit).
            repaired = _try_repair_truncated_code(full_code)
            if repaired is not None:
                logger.warning(
                    "code_interpreter: auto-repaired truncated code "
                    f"(original SyntaxError: {se.msg} line {se.lineno})"
                )
                full_code = repaired
                # Strip the preamble back out for the "code" display chunk
                code = full_code[len(preamble) :]
            else:
                error_msg = (
                    f"SyntaxError before execution: {se.msg} "
                    f"(line {se.lineno})\n"
                    "Please regenerate complete, syntactically valid Python "
                    "code. Keep code under 80 lines and split long tasks "
                    "into multiple code_interpreter calls."
                )
                return json.dumps(
                    {
                        "chunks": [
                            {"output_type": "code", "content": code.strip()},
                            {"output_type": "text", "content": error_msg},
                        ]
                    },
                    ensure_ascii=False,
                )

        try:
            tmp_path = os.path.join(work_dir, "_run.py")
            with open(tmp_path, "w", encoding="utf-8") as tmp:
                tmp.write(full_code)

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            output_text = stdout.decode("utf-8", errors="replace")
            error_text = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0 and error_text:
                output_text = (
                    output_text + "\n[ERROR]\n" + error_text
                    if output_text
                    else error_text
                )
        except asyncio.TimeoutError:
            output_text = "Execution timed out (60s limit)"
        except Exception as e:
            output_text = f"Execution error: {e}"

        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            clean_output = output_text.strip()
            max_out_len = 2000
            if len(clean_output) > max_out_len:
                truncation_notice = (
                    f"\n\n... [Output truncated, length: {len(clean_output)} chars."
                    f" Only showing first {max_out_len} chars."
                    f" If you generated HTML, the file is saved.]"
                )
                clean_output = clean_output[:max_out_len] + truncation_notice
            chunks.append({"output_type": "text", "content": clean_output})
        else:
            chunks.append(
                {
                    "output_type": "text",
                    "content": "(no output — add print() to see results)",
                }
            )

        # Scan work_dir recursively for NEW image files generated by this run
        try:
            os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
            for root, _dirs, files in os.walk(work_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    full_path = os.path.join(root, fname)
                    if ext in IMAGE_EXTS and full_path not in pre_existing_images:
                        unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                        dest = os.path.join(STATIC_MESSAGE_IMG_PATH, unique_name)
                        shutil.copy2(full_path, dest)
                        img_url = f"/images/{unique_name}"
                        chunks.append(
                            {
                                "output_type": "image",
                                "content": img_url,
                            }
                        )
                        # Track generated images in react_state for
                        # html_interpreter to reference later
                        react_state.setdefault("generated_images", []).append(img_url)
        except Exception:
            pass

        # Clean up the temp script file but keep work_dir for persistence
        try:
            script_path = os.path.join(work_dir, "_run.py")
            if os.path.exists(script_path):
                os.remove(script_path)
        except Exception:
            pass

        # Append a summary of ALL generated images so far, so the LLM
        # has a clear reference when generating HTML later.
        all_images = react_state.get("generated_images", [])
        if all_images:
            img_summary = "已生成的图片URL（在生成HTML时请使用这些URL）:\n" + "\n".join(
                f"  - {url}" for url in all_images
            )
            chunks.append({"output_type": "text", "content": img_summary})

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(
        description="Execute shell/bash commands in a sandboxed environment. "
        "Use this tool when you need to run shell commands such as ls, cat, "
        "grep, curl, apt, pip, git, or any other CLI tool. "
        "The sandbox provides resource limits (256MB memory, 30s timeout) "
        "and process isolation. "
        'Parameters: {"code": "shell command(s) to execute"}'
    )
    async def shell_interpreter(code: str) -> str:
        """Execute shell/bash commands in a sandboxed environment.

        Uses dbgpt-sandbox LocalRuntime to run bash scripts with:
        - Memory limit: 256MB
        - Timeout: 30 seconds
        - Process tree management (cleanup on timeout/error)
        - Security validation (blocks dangerous patterns like rm -rf /)
        Each call is independent — no state persists between calls.
        """
        import uuid

        if not code or not code.strip():
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No command provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        try:
            from dbgpt_sandbox.sandbox.execution_layer.base import (
                ExecutionStatus,
                SessionConfig,
            )
            from dbgpt_sandbox.sandbox.execution_layer.local_runtime import (
                LocalRuntime,
            )
        except ImportError:
            return json.dumps(
                {
                    "chunks": [
                        {"output_type": "code", "content": code.strip()},
                        {
                            "output_type": "text",
                            "content": (
                                "Error: dbgpt-sandbox package is not installed. "
                                "Please install it with: pip install dbgpt-sandbox"
                            ),
                        },
                    ]
                },
                ensure_ascii=False,
            )

        session_id = f"bash_{uuid.uuid4().hex[:12]}"
        runtime = LocalRuntime()

        from dbgpt.configs.model_config import ROOT_PATH

        sandbox_work_dir = ROOT_PATH
        os.makedirs(sandbox_work_dir, exist_ok=True)

        config = SessionConfig(
            language="bash",
            working_dir=sandbox_work_dir,
            max_memory=256 * 1024 * 1024,  # 256MB
            timeout=30,
        )

        output_text = ""
        try:
            session = await runtime.create_session(session_id, config)
            result = await session.execute(code)

            if result.status == ExecutionStatus.SUCCESS:
                output_text = result.output or ""
            elif result.status == ExecutionStatus.TIMEOUT:
                output_text = f"Execution timed out ({config.timeout}s limit)"
            else:
                output_text = result.error or "Unknown execution error"
                if result.output:
                    output_text = result.output + "\n[ERROR]\n" + output_text
        except Exception as e:
            output_text = f"Sandbox execution error: {e}"
        finally:
            try:
                await runtime.destroy_session(session_id)
            except Exception:
                pass

        chunks: List[Dict[str, Any]] = [
            {"output_type": "code", "content": code.strip()},
        ]
        if output_text.strip():
            chunks.append({"output_type": "text", "content": output_text.strip()})
        else:
            chunks.append(
                {
                    "output_type": "text",
                    "content": "(no output)",
                }
            )

        # ── Safety-net post-processing for skill script execution ──
        # If the LLM used shell_interpreter to run a skill script despite
        # the prompt requesting execute_skill_script_file, we still capture
        # critical side-effects (ratio_data, images) into react_state.
        _code_lower = code.strip().lower()
        _is_skill_script = "skills/" in _code_lower and ".py" in _code_lower
        if _is_skill_script and output_text.strip():
            import shutil

            from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

            # 1) Capture calculate_ratios.py output as ratio_data
            if "calculate_ratios" in _code_lower:
                try:
                    ratio_data = json.loads(output_text.strip())
                    if isinstance(ratio_data, dict):
                        react_state["ratio_data"] = ratio_data
                        logger.info(
                            "shell_interpreter: captured %d ratio_data keys",
                            len(ratio_data),
                        )
                except Exception:
                    pass

            # 2) Capture generate_charts.py output — look for image paths
            #    and copy them to static dir, same as execute_skill_script_file
            if "generate_charts" in _code_lower:
                try:
                    os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
                    IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
                    # Try to parse JSON output for image paths
                    try:
                        chart_output = json.loads(output_text.strip())
                        if isinstance(chart_output, dict):
                            # Might be {"charts": {...}} or flat dict
                            chart_map = chart_output.get("charts", chart_output)
                            for name, abs_path in chart_map.items():
                                if isinstance(abs_path, str) and os.path.isfile(
                                    abs_path
                                ):
                                    ext = os.path.splitext(abs_path)[1].lower()
                                    if ext in IMAGE_EXTS:
                                        unique_name = (
                                            f"{uuid.uuid4().hex[:8]}_"
                                            f"{os.path.basename(abs_path)}"
                                        )
                                        dest = os.path.join(
                                            STATIC_MESSAGE_IMG_PATH, unique_name
                                        )
                                        shutil.copy2(abs_path, dest)
                                        img_url = f"/images/{unique_name}"
                                        react_state.setdefault(
                                            "generated_images", []
                                        ).append(img_url)
                                        orig_stem = os.path.splitext(
                                            os.path.basename(abs_path)
                                        )[0].lower()
                                        react_state.setdefault("image_url_map", {})[
                                            orig_stem
                                        ] = img_url
                    except (json.JSONDecodeError, TypeError):
                        pass
                    # Also scan the output dir for any new .png files
                    cid = react_state.get("conv_id") or "default"
                    from dbgpt.configs.model_config import PILOT_PATH

                    out_dir = os.path.join(PILOT_PATH, "tmp", cid)
                    if os.path.isdir(out_dir):
                        for fname in os.listdir(out_dir):
                            ext = os.path.splitext(fname)[1].lower()
                            if ext in IMAGE_EXTS:
                                abs_path = os.path.join(out_dir, fname)
                                orig_stem = os.path.splitext(fname)[0].lower()
                                if orig_stem not in react_state.get(
                                    "image_url_map", {}
                                ):
                                    unique_name = f"{uuid.uuid4().hex[:8]}_{fname}"
                                    dest = os.path.join(
                                        STATIC_MESSAGE_IMG_PATH, unique_name
                                    )
                                    shutil.copy2(abs_path, dest)
                                    img_url = f"/images/{unique_name}"
                                    react_state.setdefault(
                                        "generated_images", []
                                    ).append(img_url)
                                    react_state.setdefault("image_url_map", {})[
                                        orig_stem
                                    ] = img_url
                    # Append image URL summary for LLM reference
                    all_images = react_state.get("generated_images", [])
                    if all_images:
                        img_summary = (
                            "\u5df2\u751f\u6210\u7684\u56fe\u7247URL\uff08\u5728\u751f\u6210HTML\u62a5\u544a\u65f6\u8bf7\u4f7f\u7528\u8fd9\u4e9bURL\uff09:\n"
                            + "\n".join(f"  - {url}" for url in all_images)
                        )
                        chunks.append({"output_type": "text", "content": img_summary})
                    logger.info(
                        "shell_interpreter: captured %d images for skill script",
                        len(react_state.get("image_url_map", {})),
                    )
                except Exception as e:
                    logger.warning(
                        "shell_interpreter: image post-processing failed: %s", e
                    )

        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    @tool(
        description="执行技能scripts目录下的脚本文件。参数: "
        '{"skill_name": "技能名称", "script_file_name": "脚本文件名", "args": {参数}}'
    )
    async def execute_skill_script_file(
        skill_name: str, script_file_name: str, args: Optional[dict] = None
    ) -> str:
        """Execute a script file from a skill's scripts directory.

        After execution, any new image files (.png, .jpg, etc.) generated
        by the script are automatically copied to the static images directory
        and their URLs are returned in the output chunks.
        """
        import shutil
        import uuid

        from dbgpt.agent.skill.manage import get_skill_manager
        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

        try:
            from dbgpt.configs.model_config import PILOT_PATH

            sm = get_skill_manager(CFG.SYSTEM_APP)
            cid = react_state.get("conv_id") or "default"
            out_dir = os.path.join(PILOT_PATH, "tmp", cid)
            os.makedirs(out_dir, exist_ok=True)
            # Auto-inject the correct file path from react_state into args.
            # The LLM sometimes corrupts the uploaded file path (e.g. changing
            # 'dbgpt-app' to 'dbgpt_app'), so we override any file-path-like
            # keys in args with the known-good path from react_state.
            real_file_path = react_state.get("file_path")
            if real_file_path and args:
                _FILE_PATH_KEYS = {
                    "input_file",
                    "file_path",
                    "data_path",
                    "csv_path",
                    "excel_path",
                    "data_file",
                }
                for key in list(args.keys()):
                    if key in _FILE_PATH_KEYS:
                        args[key] = real_file_path
            result_str = await sm.execute_skill_script_file(
                skill_name,
                script_file_name,
                args or {},
                output_dir=out_dir,
            )

            # Read script source code and prepend as a 'code' chunk
            # so the frontend can display it in the left pane.
            try:
                _skill_path = sm._get_skill_path(skill_name)
                _sf = script_file_name.lstrip("/\\")
                if _sf.startswith("scripts/") or _sf.startswith("scripts\\"):
                    _sf = _sf[8:]
                _script_abs = os.path.join(_skill_path, "scripts", _sf)
                with open(_script_abs, "r", encoding="utf-8") as _f:
                    _script_source = _f.read()
            except Exception:
                _script_source = None

            # Post-process: copy image files to static dir and replace
            # absolute paths with /images/ URLs.
            try:
                result_obj = json.loads(result_str)
                chunks = result_obj.get("chunks", [])
                # Prepend script source code as a 'code' chunk
                if _script_source:
                    chunks.insert(
                        0,
                        {
                            "output_type": "code",
                            "content": _script_source,
                        },
                    )
                os.makedirs(STATIC_MESSAGE_IMG_PATH, exist_ok=True)
                IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
                for chunk in chunks:
                    if chunk.get("output_type") == "image":
                        abs_path = chunk["content"]
                        if os.path.isabs(abs_path) and os.path.isfile(abs_path):
                            ext = os.path.splitext(abs_path)[1].lower()
                            if ext in IMAGE_EXTS:
                                unique_name = (
                                    f"{uuid.uuid4().hex[:8]}_"
                                    f"{os.path.basename(abs_path)}"
                                )
                                dest = os.path.join(
                                    STATIC_MESSAGE_IMG_PATH, unique_name
                                )
                                shutil.copy2(abs_path, dest)
                                img_url = f"/images/{unique_name}"
                                chunk["content"] = img_url
                                react_state.setdefault("generated_images", []).append(
                                    img_url
                                )
                                # Also store a map: original filename (no ext)
                                # -> served URL for template placeholder
                                # resolution.
                                orig_stem = os.path.splitext(
                                    os.path.basename(abs_path)
                                )[0].lower()
                                react_state.setdefault("image_url_map", {})[
                                    orig_stem
                                ] = img_url

                # Append image URL summary for LLM reference
                all_images = react_state.get("generated_images", [])
                if all_images:
                    img_summary = (
                        "已生成的图片URL（在生成HTML报告时请使用这些URL）:\n"
                        + "\n".join(f"  - {url}" for url in all_images)
                    )
                    chunks.append({"output_type": "text", "content": img_summary})
                auto_data = react_state.get("auto_data")
                if not isinstance(auto_data, dict):
                    auto_data = {}
                    react_state["auto_data"] = auto_data
                filtered_chunks = []
                for chunk in chunks:
                    if chunk.get("output_type") != "text":
                        filtered_chunks.append(chunk)
                        continue
                    content = chunk.get("content") or ""
                    cleaned, extracted = _extract_auto_data_markers(content)
                    if extracted:
                        auto_data.update(extracted)
                        logger.info(
                            "execute_skill_script_file: captured auto_data keys=%s",
                            sorted(extracted.keys()),
                        )
                    if cleaned:
                        chunk["content"] = cleaned
                        filtered_chunks.append(chunk)
                    elif not extracted:
                        filtered_chunks.append(chunk)
                chunks = filtered_chunks

                # Compatibility path for existing financial-report skill.
                if script_file_name == "calculate_ratios.py":
                    for chunk in chunks:
                        if chunk.get("output_type") == "text":
                            try:
                                ratio_data = json.loads(chunk["content"])
                                react_state["ratio_data"] = ratio_data
                            except Exception:
                                pass
                return json.dumps({"chunks": chunks}, ensure_ascii=False)
            except (json.JSONDecodeError, KeyError):
                return result_str
        except Exception as e:
            return json.dumps(
                {"chunks": [{"output_type": "text", "content": f"Error: {str(e)}"}]},
                ensure_ascii=False,
            )

    @tool(
        description="将 HTML 渲染为可交互的网页报告，这是向用户展示网页报告的唯一方式。"
        "【默认用法】直接传入完整的 HTML 字符串："
        '{"html": "<html>...</html>", "title": "报告标题"}。'
        "你需要自己生成完整的 HTML 代码"
        "（包含 <!DOCTYPE html>、<html>、<head>、<body> 等），"
        "然后传给 html 参数即可。"
        "HTML 可以很长，没有长度限制，不需要分段传入。"
        "【禁止】不要用 code_interpreter 写 HTML 再 print，"
        "不要用 code_interpreter 把 HTML 写入文件再读取，"
        "直接把 HTML 传给本工具即可。"
        "【技能模式 - 仅在使用技能时可选】如果正在使用技能（skill），可以用模板模式："
        '{"template_path": "技能名/templates/模板.html", '
        '"data": {"KEY": "值"}, "title": "标题"}。'
        '也可以用文件模式：{"file_path": "/path/to/report.html"}'
    )
    async def html_interpreter(
        html: str = "",
        title: str = "Report",
        file_path: str = "",
        template_path: str = "",
        data: dict | str = None,
    ) -> str:
        """Render HTML as an interactive web report.

        Default usage: pass a complete HTML string via the `html` parameter.
        The HTML can be arbitrarily long — no length limit, no chunking needed.

        Skill template mode (optional): pass `template_path` (relative to skills
        dir) plus a `data` dict whose keys match {{PLACEHOLDER}} tokens in the
        template. The backend reads the template and performs all replacements.

        Legacy fallback: `file_path` reads HTML from a file on disk.
        """
        import re

        from dbgpt.configs.model_config import STATIC_MESSAGE_IMG_PATH

        # ── Mode 1: template_path + data ──────────────────────────────
        if template_path and template_path.strip():
            tp = template_path.strip()
            skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
            target = (skills_dir / tp).resolve()
            # Security: must be under skills_dir
            try:
                target.relative_to(skills_dir)
            except ValueError:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Invalid template_path: {tp}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            if not target.is_file():
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Template not found: {tp}. "
                                    "This skill does not have HTML templates. "
                                    "Please retry by calling html_interpreter "
                                    "with the `html` parameter instead — "
                                    "generate the complete HTML report code "
                                    "yourself and pass it directly via "
                                    '{"html": "<html>...</html>", '
                                    '"title": "report title"}.'
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            try:
                raw_template = target.read_text(encoding="utf-8")
            except Exception as e:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading template: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            # Replace {{KEY}} placeholders with values from data dict
            # Sometimes the LLM passes data as a JSON string instead of a dict
            replacements = data
            if isinstance(replacements, str):
                try:
                    replacements = json.loads(replacements)
                except Exception as e:
                    logger.warning(
                        f"html_interpreter failed to parse string data as json: {e}"
                    )
                    # Attempt to fix truncated JSON by appending closing
                    # braces/quotes
                    try:
                        fixed = str(replacements).rstrip()
                        if not fixed.endswith("}"):
                            if fixed.endswith('"'):
                                fixed += "}"
                            else:
                                fixed += '"}'
                        replacements = json.loads(fixed)
                    except Exception:
                        replacements = {}
            if not isinstance(replacements, dict):
                replacements = {}
            auto_data = react_state.get("auto_data", {})
            if isinstance(auto_data, dict):
                replacements = {**auto_data, **replacements}

            # Merge LLM replacements with ratio_data from calculate_ratios.py
            ratio_data = react_state.get("ratio_data", {})
            if isinstance(ratio_data, dict):
                # auto_data / LLM data overwrites ratio_data if keys overlap
                merged = {**ratio_data, **replacements}
                replacements = merged

            # Auto-resolve CHART_* placeholders from generated images.
            # image_url_map: {
            #     "financial_overview": "/images/abc_financial_overview.png"
            # }
            # Template uses:
            #     {{CHART_FINANCIAL_OVERVIEW}}
            #     -> /images/abc_financial_overview.png
            image_url_map = react_state.get("image_url_map", {})
            if isinstance(image_url_map, dict):
                for stem, url in image_url_map.items():
                    chart_key = f"CHART_{stem.upper()}"
                    if chart_key not in replacements:
                        replacements[chart_key] = url

            def _replace_placeholder(m):
                key = m.group(1)
                return str(replacements.get(key, ""))

            html = re.sub(r"\{\{([A-Z_0-9]+)\}\}", _replace_placeholder, raw_template)
            if not title or title == "Report":
                title = target.stem
            logger.info(
                "html_interpreter: template=%s, %d placeholders replaced, "
                "html=%d chars",
                tp,
                len(replacements),
                len(html),
            )

        # ── Mode 2: file_path ─────────────────────────────────────────
        elif file_path and file_path.strip():
            fp = file_path.strip()
            if not os.path.isfile(fp):
                cid = react_state.get("conv_id") or "default"
                from dbgpt.configs.model_config import PILOT_PATH

                alt = os.path.join(PILOT_PATH, "data", cid, os.path.basename(fp))
                if os.path.isfile(alt):
                    fp = alt
                else:
                    return json.dumps(
                        {
                            "chunks": [
                                {
                                    "output_type": "text",
                                    "content": f"File not found: {file_path}",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    )
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    html = f.read()
                if not title or title == "Report":
                    title = os.path.splitext(os.path.basename(fp))[0]
                logger.info(
                    "html_interpreter: read %d chars from file %s",
                    len(html),
                    fp,
                )
            except Exception as e:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": f"Error reading file: {e}",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )

        # ── Mode 3: inline html ──────────────────────────────────────
        # Unescape literal \n sequences that LLM may produce.
        # IMPORTANT: Only apply this unescape when html was provided directly
        # (inline mode).  Template mode (Mode 1) and file mode (Mode 2) produce
        # real HTML that already contains actual newlines and may contain JS
        # regex literals like /\\n/ which must NOT be collapsed into real
        # newlines — doing so corrupts the JS and breaks chart rendering.
        if html and isinstance(html, str) and not template_path and not file_path:
            if "\\n" in html:
                html = html.replace("\\n", "\n")
            if "\\t" in html:
                html = html.replace("\\t", "\t")
        if not html or not html.strip():
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No HTML content provided",
                        }
                    ]
                },
                ensure_ascii=False,
            )

        # Post-process: fix image URLs that the LLM may have guessed wrong.
        # Files in STATIC_MESSAGE_IMG_PATH are named "{uuid8}_{original}.ext".
        # The LLM might reference "/images/original.ext" (without UUID prefix)
        # or even just "original.ext".  Build a lookup and replace.
        fixed_html = html.strip()
        try:
            IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
            # Map: lowercase base name (without uuid prefix) -> served path
            # e.g. "monthly_sales_trend.png"
            #      -> "/images/a1b2c3ff_monthly_sales_trend.png"
            name_to_served: Dict[str, str] = {}
            if os.path.isdir(STATIC_MESSAGE_IMG_PATH):
                for fname in os.listdir(STATIC_MESSAGE_IMG_PATH):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in IMAGE_EXTS:
                        continue
                    # Strip the 8-char hex UUID prefix + underscore
                    # Pattern: <8 hex chars>_<original_name>
                    m = re.match(r"^[0-9a-f]{8}_(.+)$", fname, re.IGNORECASE)
                    if m:
                        base_name = m.group(1).lower()
                        served_path = f"/images/{fname}"
                        # Keep the latest (last alphabetically = most recent
                        # UUID)
                        name_to_served[base_name] = served_path

            if name_to_served:
                # Replace patterns like:
                #   src="/images/monthly_sales_trend.png"
                #   src="images/monthly_sales_trend.png"
                #   src="monthly_sales_trend.png"
                # with the correct served path.
                def _fix_img_src(match: re.Match) -> str:
                    prefix = match.group(1)  # src=" or src='
                    raw_path = match.group(2)  # the path value
                    quote = match.group(3)  # closing quote

                    # Extract just the filename from the path
                    filename = raw_path.rsplit("/", 1)[-1].lower()

                    # Check if it's already a correct served path
                    if re.match(r"^[0-9a-f]{8}_.+$", filename, re.IGNORECASE):
                        return match.group(0)  # Already has UUID prefix

                    if filename in name_to_served:
                        return f"{prefix}{name_to_served[filename]}{quote}"
                    return match.group(0)  # No match, keep original

                # Match src="..." or src='...' containing image references
                fixed_html = re.sub(
                    r"""(src\s*=\s*["'])"""
                    r"""([^"']+\.(?:png|jpg|jpeg|gif|svg|webp))"""
                    r"""(["'])""",
                    _fix_img_src,
                    fixed_html,
                    flags=re.IGNORECASE,
                )
        except Exception:
            pass  # If post-processing fails, use original HTML

        # Auto-append images generated during this session that the LLM
        # forgot to include in the HTML.
        try:
            gen_images = react_state.get("generated_images", [])
            if gen_images:
                # Extract all image filenames already referenced in the HTML
                # (e.g. "time_series_trend.png" from any src="...time_series_trend.png")
                html_img_stems = set(
                    re.sub(r"^[0-9a-f]+_", "", os.path.basename(src))
                    for src in re.findall(
                        r'<img[^>]+src=["\']([^"\']+)["\']', fixed_html, re.IGNORECASE
                    )
                )

                # An image is "missing" only when neither its exact URL nor its
                # stem (filename with UUID prefix stripped) is already covered.
                def _img_stem(url):
                    return re.sub(r"^[0-9a-f]+_", "", os.path.basename(url))

                missing = [
                    url
                    for url in gen_images
                    if url not in fixed_html and _img_stem(url) not in html_img_stems
                ]
                if missing:
                    imgs_html = "".join(
                        f'<div style="margin:16px 0">'
                        f'<img src="{url}" '
                        f'style="max-width:100%;height:auto;'
                        f'border-radius:8px">'
                        f"</div>"
                        for url in missing
                    )
                    section = (
                        '<div style="margin-top:32px">'
                        "<h2>📊 分析图表</h2>"
                        f"{imgs_html}</div>"
                    )
                    # Insert before </body> if present, otherwise append
                    if "</body>" in fixed_html.lower():
                        fixed_html = re.sub(
                            r"(</body>)",
                            section + r"\1",
                            fixed_html,
                            count=1,
                            flags=re.IGNORECASE,
                        )
                    else:
                        fixed_html += section
        except Exception:
            pass

        chunks: List[Dict[str, Any]] = [
            {"output_type": "html", "content": fixed_html, "title": title},
        ]
        return json.dumps({"chunks": chunks}, ensure_ascii=False)

    llm_client = DefaultLLMClient(
        CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create(),
        auto_convert_message=True,
    )
    # If user specified a model_name, use Priority strategy to ensure the
    # agent uses the requested model instead of picking the first available one.
    if dialogue.model_name:
        llm_config = LLMConfig(
            llm_client=llm_client,
            llm_strategy=LLMStrategyType.Priority,
            strategy_context=json.dumps([dialogue.model_name]),
        )
    else:
        llm_config = LLMConfig(llm_client=llm_client)

    conv_id = dialogue.conv_uid or str(uuid.uuid4())
    react_state["conv_id"] = conv_id
    if conv_id in REACT_AGENT_MEMORY_CACHE:
        gpt_memory = REACT_AGENT_MEMORY_CACHE[conv_id]
    else:
        gpt_memory = GptsMemory(
            plans_memory=DefaultGptsPlansMemory(),
            message_memory=MetaDbGptsMessageMemory(),
        )
        gpt_memory.init(conv_id, enable_vis_message=False)
        REACT_AGENT_MEMORY_CACHE[conv_id] = gpt_memory
    agent_memory = AgentMemory(gpts_memory=gpt_memory)

    # --- Persist conversation to chat_history for sidebar display ---
    conv_serve = ConversationServe.get_instance(CFG.SYSTEM_APP)
    storage_conv = StorageConversation(
        conv_uid=conv_id,
        chat_mode=dialogue.chat_mode or "chat_react_agent",
        user_name=dialogue.user_name,
        sys_code=dialogue.sys_code,
        summary=dialogue.user_input,
        app_code=dialogue.app_code,
        conv_storage=conv_serve.conv_storage,
        message_storage=conv_serve.message_storage,
    )
    storage_conv.save_to_storage()
    storage_conv.start_new_round()
    storage_conv.add_user_message(user_input)
    context = AgentContext(
        conv_id=conv_id,
        gpts_app_code="react_agent",
        gpts_app_name="ReAct",
        language="zh",
        temperature=dialogue.temperature or 0.2,
    )

    # Build file context if file uploaded
    file_context = ""
    if file_path:
        file_context = f"""
## User Uploaded File
- File path: {file_path}
- Analyze this file if needed for the user's request.
"""

    # Build skill context for system prompt when skill is pre-selected
    skill_prompt_context = ""
    execution_instruction = ""
    if pre_matched_skill and react_state.get("skill_prompt"):
        skill_template = react_state["skill_prompt"]
        skill_text = (
            skill_template.template
            if hasattr(skill_template, "template")
            else str(skill_template)
        )
        skill_prompt_context = f"""
## 已加载技能指令（{pre_matched_skill.metadata.name}）
以下是用户选择的技能的完整指令，请严格按照这些指令进行操作：

{skill_text}
"""
        execution_instruction = f"""
## 执行要求
1. 用户已明确选择技能：{pre_matched_skill.metadata.name}
2. 你必须严格按照上述技能指令的步骤执行
3. 阅读技能指令，理解每一步需要调用的工具
4. 按顺序执行工具调用，完成技能目标
"""

    # Build a hint listing all images currently available in
    # STATIC_MESSAGE_IMG_PATH so the LLM can reference them correctly in
    # html_interpreter.
    # NOTE: This is the initial hint at prompt build time. Images generated
    # during the session are tracked in react_state["generated_images"] and
    # appended to html_interpreter output dynamically.
    available_images_hint = ""

    # Check if skill is pre-selected to use simplified prompt
    is_skill_mode = pre_matched_skill is not None
    _skill_name = pre_matched_skill.metadata.name if pre_matched_skill else "skill"

    if is_skill_mode:
        # Simplified prompt for skill mode - only skill-related tools +
        # html_interpreter
        workflow_prompt = f"""
You are the DB-GPT intelligent assistant, executing the skill task selected by the user.
Please always response in the same language as the user's input language.

## Autonomous Decision Principles
1. Strictly follow the instructions of the loaded skill.
2. For each step, output Thought -> Phase -> Action -> Action Input.
3. Wait for the system to return Observation before deciding on the next step.
4. **[Mandatory Rule] If the task requires generating an analysis report, you MUST
call `html_interpreter` for HTML rendering.** By default, generate complete HTML
code yourself and pass it via the `html` parameter (include DOCTYPE, html, head,
body, styles, and all content). Only use `template_path` mode if the skill
explicitly provides HTML templates in its `templates/` directory and its
documentation references them. When using template mode, provide ALL required
placeholders in the `data` dictionary.
5. If the task does not require generating a report, directly call terminate to
return the final result. The Action Input format must be
{{"result": "final answer"}}.

{skill_prompt_context}
{execution_instruction}

## Skill Execution Norms
### Resource Usage
- **Need to execute skill script** -> Use `execute_skill_script_file` with
parameters {{"skill_name": "skill name", "script_file_name": "script file name",
"args": {{parameters}}}}. This tool will automatically handle image copying and
data recording.
- **Need to understand indicator definitions/analysis framework** -> Use
`get_skill_resource` and specify the `references/xxx.md` path to read the
reference document.
- **Encounter image file** -> If the model does not support image input, it will
return an error prompt.
- **Need to generate report** -> Call `html_interpreter`. **Default: directly pass
complete HTML via the `html` parameter** — you generate the full HTML code
yourself (including `<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`, styles,
content). The HTML can be as long as needed. **Only use `template_path` if the
skill explicitly provides HTML templates in its `templates/` directory and its
documentation tells you to use them.** Do not use `code_interpreter` to generate
the report.

## Available Tools Description
1. **execute_skill_script_file** (recommended for executing skill scripts): Execute
script files in the skills scripts directory, automatically handling
post-processing such as copying images to the static directory and recording
calculation results.
   Parameters: {{"skill_name": "skill name", "script_file_name": "script file
name", "args": {{parameters}}}}
   - Example: {{"skill_name": "{_skill_name}",
"script_file_name": "calculate_ratios.py",
"args": {{"input_data": "..."}}}}
   - **Must use this tool when executing skill scripts**, do not use
shell_interpreter.
2. **get_skill_resource**: Read reference documents, configurations, templates, and
other non-script resource files in the skill.
   Parameters: {{"skill_name": "skill name", "resource_path": "resource path"}}
   - Read reference document: {{"skill_name": "{_skill_name}",
"resource_path": "references/analysis_framework.md"}}
   - Note: For generating reports, prefer using html_interpreter directly with the
`html` parameter. Only use template_path if the skill explicitly provides
templates.
3. **execute_skill_script**: Execute the inline script defined in the skill
(backup). Parameters: {{"skill_name": "skill name", "script_name": "script name",
"args": {{"parameter name": "parameter value"}}}}
4. **shell_interpreter**: Execute shell/bash commands (only for non-skill script
system commands, such as ls, cat, etc.).
   Parameters: {{"code": "shell command"}}
   - Each call is independent and does not retain state. If multi-step operations
are needed, use `&&` or `;` to connect commands.
   - **Note: Do not use this tool to execute skill scripts**, as it will not
automatically handle images and data recording.
5. **html_interpreter**: Render HTML as an interactive web report. This is the ONLY
way to display reports on the right panel.
   **Default usage (recommended)**: {{"html": "<html>your complete HTML code</html>",
"title": "report title"}}
   - Generate complete HTML yourself (DOCTYPE, html, head, body, CSS styles,
content). No length limit.
   - **Do not** use code_interpreter to write HTML. Directly pass the HTML string
to this tool.
   **Template mode (only when skill has templates/)**: {{"template_path":
"skill-name/templates/template.html", "data": {{"KEY": "value"}}, "title": "title"}}
   - Only use this if the skill's documentation explicitly provides template paths.
If template_path returns "Template not found", immediately switch to the default
`html` parameter usage.
   {available_images_hint}
6. **terminate**: Return the final answer when the task is completed. Action Input
must be {{"result": "your final answer content"}}.

{file_context}
{knowledge_context}
{database_context}
## Phase (Must output for each step)
Phase is a short text description expressing the intention or stage of the current
step. Example: "Load sales analysis skill", "Execute data extraction script",
"Render analysis report".
## ReAct Output Format
Must output for each interaction round:
Thought: Analyze current task status and think about what to do next
Phase: Use a short text to describe the intention of the current step (e.g.,
"Load sales analysis skill", "Execute data extraction script",
"Render analysis report")
Action: The selected tool name (must be one of the tools listed above)
Action Input: The JSON format of tool parameters
""".strip()

        tool_pack = ToolPack(
            [
                execute_skill_script,
                get_skill_resource,
                execute_skill_script_file,
                shell_interpreter,
                html_interpreter,
                sql_query,
                Terminate(),
            ]
            + business_tools
        )
    else:
        # Full prompt with all tools when no skill is pre-selected
        workflow_prompt = f"""
You are the DB-GPT intelligent assistant, capable of autonomously selecting tools
to solve problems based on user tasks.
Please always response in the same language as the user's input language.

## Autonomous Decision Principles
1. Carefully analyze the user's task requirements.
2. Autonomously select required tools based on requirements (do not follow a fixed
order, select as needed).
3. For each step, output Thought -> Phase -> Action -> Action Input.
4. Wait for the system to return Observation before deciding on the next step.
5. When the task is completed, call the terminate tool to return the final result.
The Action Input format must be {{"result": "final answer"}}.
6. **[Mandatory Rule] If there is a requirement for an analysis report, you MUST call
`html_interpreter` for HTML rendering. When the user requests generating a webpage,
HTML report, or interactive report, the final presentation step must call
`html_interpreter` to render it. It is forbidden to output HTML using only
`code_interpreter` and then directly terminate. Correct process: code_interpreter
writes to .html file -> html_interpreter(file_path=...) renders -> terminate.**

## Available Skills List (Pre-loaded)
{skills_context}

## Skill Execution Norms (Important)
When using a skill, the following rules must be followed:

### 1. Understand the Workflow
After loading the skill, carefully read the **Core Workflow** section in SKILL.md
and execute it in order. If a step explicitly states conditions to skip (such as
when user intent is clear), directly skip to the next step; do not force the
execution of every step. Prioritize producing results quickly, and perform
iterative optimization in subsequent steps.

### 2. Resource Usage Timing
- **Need to calculate/process data** -> Use `execute_skill_script_file` to execute
scripts in the skill's scripts directory (this tool automatically handles images
and data recording). Parameters are {{"skill_name": "skill name",
"script_file_name": "script.py", "args": {{parameters}}}}.
- **Need to understand indicator definitions/analysis framework** -> Use
`get_skill_resource` and specify the `references/xxx.md` path to read the
reference document.
- **Encounter image file** -> If the model does not support image input, it will
return an error prompt.

### 3. Execution Order
Complete each workflow step before moving to the next. Do not mix multiple tool
calls in the same step.

### 4. Special Scenarios
- For report generation: Same as the principle above, must finally call
`html_interpreter` to render.

## Available Tools Description
1. **load_skill**: Load skill content by skill name and file path.
Parameters: {{"skill_name": "skill name", "file_path": "skill file path"}}
2. **execute_skill_script_file**: Execute script files in the skill's scripts
directory. Parameters: {{"skill_name": "skill name",
"script_file_name": "script file name", "args": {{parameters}}}}
3. **get_skill_resource**: Read reference documents in the skill.
Parameters: {{"skill_name": "skill name", "resource_path": "resource path"}}
4. **execute_skill_script**: Execute the inline script defined in the skill.
Parameters: {{"skill_name": "skill name", "script_name": "script name",
"args": {{parameters}}}}
5. **shell_interpreter**: Execute shell/bash commands.
Parameters: {{"code": "shell command"}}
6. **code_interpreter**: Execute arbitrary Python code.
Parameters: {{"code": "python code string"}}
7. **load_file**: Load uploaded file info. Parameters: none.
8. **execute_analysis**: Execute quick analysis on uploaded Excel/CSV file.
Parameters: none.
9. **knowledge_retrieve**: Retrieve relevant info from knowledge base.
Parameters: {{"query": "search query"}}
10. **sql_query**: Execute a read-only SQL query against the selected database.
Parameters: {{"sql": "SELECT statement"}}
11. **load_tools**: Resolve required tools for the selected skill. Parameters: none.
12. **execute_tool**: Execute a tool by name with JSON args.
Parameters: {{"tool_name": "tool name", "args": {{parameters}}}}
13. **html_interpreter**: Render HTML as an interactive web report (the ONLY way
to display reports on the right panel). Default usage:
{{"html": "<html>complete HTML code</html>", "title": "title"}}. Template mode:
{{"template_path": "skill/templates/xxx.html", "data": {{...}}, "title": "title"}}.
File mode: {{"file_path": "/path/to/report.html"}}
14. **terminate**: Finish the task. Parameters: {{"result": "final answer"}}

{file_context}
{knowledge_context}
{database_context}

## Phase (Must output for each step)
Phase is a short text description expressing the intention or stage of the current
step. Example: "Select skill", "Analyze data", "Render report".

## ReAct Output Format
Must output for each interaction round:
Thought: Analyze current task status and think about what to do next
Phase: Use a short text to describe the intention of the current step
Action: The selected tool name
Action Input: The JSON format of tool parameters
""".strip()

        tool_pack = ToolPack(
            [
                load_skill,
                load_tools,
                knowledge_retrieve,
                execute_skill_script,
                get_skill_resource,
                execute_skill_script_file,
                code_interpreter,
                shell_interpreter,
                html_interpreter,
                sql_query,
                Terminate(),
            ]
            + business_tools
        )

    # Debug: print all registered tools
    logger.info(f"ToolPack resources: {list(tool_pack._resources.keys())}")
    if "execute_skill_script" not in tool_pack._resources:
        logger.error("execute_skill_script NOT in ToolPack!")

    # Combine tool_pack and knowledge_resources into a single ResourcePack
    all_resources = [tool_pack]
    if knowledge_resources:
        all_resources.extend(knowledge_resources)
    # Convert workflow_prompt to PromptTemplate so it is used as system prompt
    # Use jinja2 format to avoid issues with JSON braces { } in the prompt
    workflow_prompt_template = PromptTemplate(
        template=workflow_prompt,
        input_variables=[],
        template_format="jinja2",
    )

    agent_builder = (
        ReActAgent(max_retry_count=30)
        .bind(context)
        .bind(agent_memory)
        .bind(llm_config)
        .bind(tool_pack)
        .bind(workflow_prompt_template)
    )

    agent = await agent_builder.build()

    parser = ReActOutputParser()
    received = AgentMessage(content=user_input)
    stream_queue: asyncio.Queue = asyncio.Queue()

    async def stream_callback(event_type: str, payload: Dict[str, Any]) -> None:
        await stream_queue.put({"type": event_type, **payload})

    async def run_agent():
        return await agent.generate_reply(
            received_message=received,
            sender=agent,
            stream_callback=stream_callback,
        )

    agent_task = asyncio.create_task(run_agent())
    round_step_map: Dict[int, str] = {}
    pending_thoughts: Dict[
        int, List[str]
    ] = {}  # Buffer thinking content for delayed step creation
    # --- History persistence: collect step data during streaming ---
    history_steps: List[Dict[str, Any]] = []
    current_history_step: Optional[Dict[str, Any]] = None

    # Emit pre-loaded skill as an SSE step before agent starts processing
    if pre_matched_skill:
        skill_step_id, skill_step_event = build_step(
            f"Load Skill: {pre_matched_skill.metadata.name}",
            "Pre-loaded skill from user selection",
            phase="加载技能",
        )
        current_history_step = {
            "id": skill_step_id,
            "title": f"Load Skill: {pre_matched_skill.metadata.name}",
            "detail": "Pre-loaded skill from user selection",
            "phase": "加载技能",
            "thought": None,
            "action": None,
            "action_input": None,
            "outputs": [],
            "status": "done",
        }
        yield skill_step_event
        # Emit skill metadata as text chunk
        skill_desc = (
            f"Skill: {pre_matched_skill.metadata.name}"
            f" - {pre_matched_skill.metadata.description}"
        )
        yield step_chunk(skill_step_id, "text", skill_desc)
        current_history_step["outputs"].append(
            {"output_type": "text", "content": skill_desc}
        )
        # Emit skill instructions as markdown content (shows in right panel)
        if pre_matched_skill.instructions:
            yield step_chunk(skill_step_id, "markdown", pre_matched_skill.instructions)
            current_history_step["outputs"].append(
                {
                    "output_type": "markdown",
                    "content": pre_matched_skill.instructions,
                }
            )
        yield step_done(skill_step_id)
        history_steps.append(current_history_step)
        current_history_step = None

    while True:
        if agent_task.done() and stream_queue.empty():
            break
        try:
            event = await asyncio.wait_for(stream_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            continue

        event_type = event.get("type")
        if event_type == "thinking":
            # Parse thinking content but don't create step yet
            # Step will be created when 'act' event arrives with confirmed
            # action
            round_num = int(event.get("round") or (len(round_step_map) + 1))
            llm_reply = event.get("llm_reply") or ""
            thought = None
            action = None
            action_input = None
            try:
                steps = parser.parse(llm_reply)
                if steps:
                    thought = steps[0].thought
                    action = steps[0].action
                    action_input = steps[0].action_input
            except Exception:
                pass

            # Store parsed thinking info in pending_thoughts for later use
            if round_num not in pending_thoughts:
                pending_thoughts[round_num] = []
            if thought:
                pending_thoughts[round_num].append(thought)
            # Don't emit anything yet - wait for 'act' event to create step

        elif event_type == "thinking_chunk":
            round_num = int(event.get("round") or (len(round_step_map) + 1))
            delta_thinking = event.get("delta_thinking") or ""
            delta_text = event.get("delta_text") or ""

            chunk = delta_thinking or delta_text
            if chunk:
                # Clean chunk: remove Action Input JSON to keep thought pure
                # Split on Action Input pattern and keep only thought part
                clean_chunk = re.split(
                    r"\n\s*Action\s*Input\s*:\s*\{", chunk, maxsplit=1
                )[0]
                # Also remove Action: lines
                clean_chunk = re.sub(r"\n\s*Action\s*:\s*\w+", "", clean_chunk)
                # Remove Thought: prefix if present
                if clean_chunk.startswith("Thought:"):
                    clean_chunk = clean_chunk[len("Thought:") :].strip()
                if clean_chunk:
                    if round_num not in pending_thoughts:
                        pending_thoughts[round_num] = []
                    pending_thoughts[round_num].append(clean_chunk)
                    if round_num not in round_step_map:
                        pending_step_id, pending_step_event = build_step(
                            "思考中",
                            "Thought/Action/Observation",
                        )
                        round_step_map[round_num] = pending_step_id
                        yield pending_step_event
                    target_id = round_step_map[round_num]
                    yield _sse_event(
                        {
                            "type": "step.thought",
                            "id": target_id,
                            "content": clean_chunk,
                        }
                    )

        elif event_type == "act":
            # Create step ONLY when action is confirmed
            round_num = int(event.get("round") or (len(round_step_map) + 1))

            action_output = event.get("action_output") or {}
            thoughts = action_output.get("thoughts")
            action = action_output.get("action")
            action_input = action_output.get("action_input")
            action_input_data = None
            if action_input is not None:
                if isinstance(action_input, str):
                    try:
                        action_input_data = json.loads(action_input)
                    except Exception:
                        action_input_data = action_input
                else:
                    action_input_data = action_input

            # Skip step display for terminate action — its output will be
            # sent as a streaming "final" event instead of a step card.
            # Also skip emitting the thought for terminate since it's noise.
            # Note: TerminateAction.run() sets terminate=True but does NOT
            # set the action field, so we must check the terminate boolean.
            is_terminate = action_output.get("terminate") or (
                action and action.lower() == "terminate"
            )
            if is_terminate:
                pending_thoughts.pop(round_num, [])
                continue

            # Collect buffered thoughts for history persistence
            # (already streamed to frontend via thinking_chunk handler)
            buffered_thoughts = pending_thoughts.pop(round_num, [])
            thought_text = None
            if buffered_thoughts:
                full_thought = "".join(buffered_thoughts)
                full_thought = re.split(r"\n\s*Action\s*:", full_thought, maxsplit=1)[
                    0
                ].strip()
                if full_thought.startswith("Thought:"):
                    full_thought = full_thought[len("Thought:") :].strip()
                if full_thought:
                    thought_text = full_thought

            # Use the actual action name as the step title (Manus-style UI)
            action_title = action or f"ReAct Round {round_num}"
            # Infer phase from action name
            inferred_phase = action_output.get("phase") or infer_phase(action)
            if round_num in round_step_map:
                # Step already exists (from thinking) - update title/phase with same id
                react_step_id = round_step_map[round_num]
                updated_event = _sse_event(
                    {
                        "type": "step.start",
                        "step": step,
                        "id": react_step_id,
                        "title": action_title,
                        "detail": "Thought/Action/Observation",
                        "phase": inferred_phase,
                    }
                )
                yield updated_event
            else:
                react_step_id, react_step_event = build_step(
                    action_title,
                    "Thought/Action/Observation",
                    phase=inferred_phase,
                )
                round_step_map[round_num] = react_step_id
                yield react_step_event

            # --- History: create step record ---
            action_input_str = None
            if action_input is not None:
                action_input_str = (
                    action_input
                    if isinstance(action_input, str)
                    else json.dumps(action_input, ensure_ascii=False)
                )
            current_history_step = {
                "id": react_step_id,
                "title": action_title,
                "detail": "Thought/Action/Observation",
                "phase": inferred_phase,
                "thought": thought_text,
                "action": action,
                "action_input": action_input_str,
                "outputs": [],
                "status": "running",
            }

            # Stream action code to frontend for right panel
            # (code_interpreter)
            code_payload = None
            if action == "code_interpreter" and isinstance(action_input_data, dict):
                code_payload = action_input_data.get("code")
            if isinstance(code_payload, str) and code_payload.strip():
                yield step_chunk(react_step_id, "code", code_payload)
                if current_history_step is not None:
                    current_history_step["outputs"].append(
                        {"output_type": "code", "content": code_payload}
                    )

            # Emit thinking metadata
            if thoughts or action or action_input:
                step_action_input = (
                    None if action == "code_interpreter" else action_input
                )
                yield step_meta(
                    react_step_id,
                    thoughts,
                    action,
                    step_action_input,
                    action_title,
                )

            # Emit observation (action execution result)
            observation_text = action_output.get("observations") or action_output.get(
                "content"
            )
            if observation_text:
                raw_chunks = emit_tool_chunks(react_step_id, observation_text)
                if raw_chunks:
                    for chunk in raw_chunks:
                        yield chunk
                else:
                    for chunk in chunk_text(str(observation_text), max_len=600):
                        yield step_chunk(react_step_id, "text", chunk)
                # --- History: collect outputs from observation ---
                if current_history_step is not None:
                    parsed_obs = None
                    if isinstance(observation_text, str):
                        try:
                            parsed_obs = json.loads(observation_text)
                        except Exception:
                            pass
                    if isinstance(parsed_obs, dict) and isinstance(
                        parsed_obs.get("chunks"), list
                    ):
                        for item in parsed_obs["chunks"]:
                            if isinstance(item, dict):
                                current_history_step["outputs"].append(
                                    {
                                        "output_type": item.get("output_type", "text"),
                                        "content": item.get("content"),
                                    }
                                )
                    elif isinstance(observation_text, str) and observation_text:
                        current_history_step["outputs"].append(
                            {
                                "output_type": "text",
                                "content": observation_text,
                            }
                        )

            # Mark step as done and track as last completed
            status = "done" if action_output.get("is_exe_success", True) else "failed"
            yield step_done(react_step_id, status)

            # --- History: finalize step ---
            if current_history_step is not None:
                current_history_step["status"] = status
                history_steps.append(current_history_step)
                current_history_step = None

    try:
        reply = await agent_task
    except Exception as e:
        err_msg = f"React agent failed: {e}"
        # Persist error reply with structured history payload
        error_payload = json.dumps(
            {
                "version": 1,
                "type": "react-agent",
                "final_content": err_msg,
                "steps": history_steps,
                "generated_images": react_state.get("generated_images", []),
            },
            ensure_ascii=False,
        )
        storage_conv.add_view_message(error_payload)
        storage_conv.end_current_round()
        storage_conv.save_to_storage()
        yield _sse_event({"type": "final", "content": err_msg})
        yield _sse_event({"type": "done"})
        return

    if reply.action_report and reply.action_report.terminate:
        raw_content = reply.action_report.content or ""
        # The terminate ActionOutput.content is the full raw LLM text, e.g.:
        # "Thought: ...\nAction: terminate\nAction Input: {"result": "..."}"
        # We need to extract the "result" value from Action Input.
        final_content = raw_content
        try:
            steps = parser.parse(raw_content)
            if steps:
                action_input = steps[0].action_input
                if action_input:
                    # action_input could be a string like '{"result": "..."}'
                    if isinstance(action_input, str):
                        parsed_input = json.loads(action_input)
                    else:
                        parsed_input = action_input
                    if isinstance(parsed_input, dict) and "result" in parsed_input:
                        final_content = parsed_input["result"]
        except Exception:
            pass
    elif reply.action_report:
        # Loop ended without terminate (max retries or timeout).
        # reply.content is raw LLM output containing ReAct prefixes.
        # Try to extract a clean summary from the last step's thought.
        raw = reply.content or reply.action_report.content or ""
        final_content = raw
        try:
            steps = parser.parse(raw)
            if steps:
                last_step = steps[-1]
                # Prefer observation (execution result) > thought
                if last_step.observations:
                    final_content = last_step.observations
                elif last_step.thoughts:
                    final_content = last_step.thoughts
        except Exception:
            pass
        # Fallback: strip remaining ReAct prefixes via regex
        final_content = re.sub(
            r"^(Thought|Action|Action Input|Observation|Phase):\s*",
            "",
            final_content,
            flags=re.MULTILINE,
        ).strip()
        if not final_content:
            final_content = "任务执行已达到最大步数限制，请查看上方各步骤的执行结果。"
    else:
        final_content = reply.content or ""

    # Persist AI reply with structured history payload
    history_payload = json.dumps(
        {
            "version": 1,
            "type": "react-agent",
            "final_content": final_content,
            "steps": history_steps,
            "generated_images": react_state.get("generated_images", []),
        },
        ensure_ascii=False,
    )
    storage_conv.add_view_message(history_payload)
    storage_conv.end_current_round()
    storage_conv.save_to_storage()

    yield _sse_event({"type": "final", "content": final_content})
    yield _sse_event({"type": "done"})


# ---------------------------------------------------------------------------
# Share link APIs
# ---------------------------------------------------------------------------


class ShareCreateRequest(_BaseModel):
    """Request body for creating a share link."""

    conv_uid: str


class ShareCreateResponse(_BaseModel):
    """Response body for share link creation."""

    token: str
    conv_uid: str
    share_url: str


class ShareConvResponse(_BaseModel):
    """Public payload returned when viewing a shared conversation."""

    conv_uid: str
    token: str
    messages: list  # list[{role, context, order}]


def _get_share_dao():
    """Lazily instantiate the ShareLinkDao (avoids import-time side-effects)."""
    from dbgpt_app.share.models import ShareLinkDao

    return ShareLinkDao()


def _get_conversation_service():
    """Return the ConversationServe Service component."""
    from dbgpt_serve.conversation.config import SERVE_SERVICE_COMPONENT_NAME
    from dbgpt_serve.conversation.service.service import Service

    return CFG.SYSTEM_APP.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


@router.post("/v1/chat/share", response_model=Result)
async def create_share_link(
    body: ShareCreateRequest = Body(),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Create (or return existing) share link for a conversation.

    The returned ``share_url`` is a relative path that the client should
    prepend with the current host to form an absolute URL.
    """
    dao = _get_share_dao()
    created_by = user_token.user_id if user_token else None
    entity = dao.create_share(conv_uid=body.conv_uid, created_by=created_by)
    if entity is None:
        return Result.failed(msg="Failed to create share link")
    return Result.succ(
        ShareCreateResponse(
            token=entity.token,
            conv_uid=entity.conv_uid,
            share_url=f"/share/{entity.token}",
        )
    )


@router.get("/v1/chat/share/{token}", response_model=Result)
async def get_share_conversation(token: str):
    """Public endpoint — no authentication required.

    Returns the full conversation history for the given share token so that the
    replay page can reconstruct and animate the session.
    """
    dao = _get_share_dao()
    link = dao.get_by_token(token)
    if link is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Share link not found")

    service = _get_conversation_service()
    from dbgpt_serve.conversation.api.schemas import ServeRequest

    history = service.get_history_messages(ServeRequest(conv_uid=link.conv_uid))

    messages = [
        {"role": m.role, "context": m.context, "order": m.order}
        for m in (history or [])
    ]
    return Result.succ(
        ShareConvResponse(
            conv_uid=link.conv_uid,
            token=token,
            messages=messages,
        )
    )


@router.delete("/v1/chat/share/{token}", response_model=Result)
async def delete_share_link(
    token: str,
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Revoke a share link.  Only the owner (or any authenticated user) may delete."""
    dao = _get_share_dao()
    deleted = dao.delete_by_token(token)
    if not deleted:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Share link not found")
    return Result.succ({"deleted": True, "token": token})


@router.get("/v1/agent/files/download")
async def download_agent_file(
    file_path: str = Query(..., description="Absolute path to the file to download"),
):
    """Download a file created by agent tools (shell_interpreter, code_interpreter).

    Only files under allowed directories (/tmp, PILOT_PATH/tmp/) can be downloaded.
    This prevents arbitrary file access on the server.
    """
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    from dbgpt.configs.model_config import PILOT_PATH, ROOT_PATH

    # If path is not absolute, resolve relative to ROOT_PATH (sandbox working dir)
    if not os.path.isabs(file_path):
        file_path = os.path.join(ROOT_PATH, file_path)

    # Resolve to absolute path and prevent path traversal
    try:
        resolved = os.path.realpath(file_path)
    except (ValueError, OSError):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Allowed base directories for agent-created files
    allowed_dirs = [
        os.path.realpath("/tmp"),
        os.path.realpath(os.path.join(PILOT_PATH, "tmp")),
        os.path.realpath(ROOT_PATH),
    ]

    if not any(resolved.startswith(d + os.sep) or resolved == d for d in allowed_dirs):
        raise HTTPException(
            status_code=403,
            detail="Access denied: file is not in an allowed directory",
        )

    if not os.path.isfile(resolved):
        raise HTTPException(status_code=404, detail="File not found")

    filename = os.path.basename(resolved)
    return FileResponse(
        path=resolved,
        filename=filename,
        media_type="application/octet-stream",
    )


@router.get("/v1/agent/skills/download")
async def download_skill_package(
    skill_name: str = Query(..., description="Skill folder name"),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    """Download a skill folder as a .zip archive."""
    from fastapi import HTTPException

    if not skill_name:
        raise HTTPException(status_code=400, detail="skill_name is required")

    skills_dir = Path(DEFAULT_SKILLS_DIR).expanduser().resolve()
    skill_path = (skills_dir / skill_name).resolve()

    # Security: ensure path is under skills_dir
    try:
        skill_path.relative_to(skills_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not skill_path.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    # Build zip in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(skill_path):
            for fname in files:
                abs_file = os.path.join(root, fname)
                arc_name = os.path.relpath(abs_file, skill_path)
                zf.write(abs_file, arcname=os.path.join(skill_name, arc_name))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{skill_name}.zip"',
        },
    )


@router.post("/v1/chat/react-agent")
async def chat_react_agent(
    dialogue: ConversationVo = Body(),
    user_token: UserRequest = Depends(get_user_from_headers),
):
    logger.info(
        "chat_react_agent:%s,%s,%s",
        dialogue.chat_mode,
        dialogue.select_param,
        dialogue.model_name,
    )
    dialogue.user_name = user_token.user_id if user_token else dialogue.user_name
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    try:
        return StreamingResponse(
            _react_agent_stream(dialogue),
            headers=headers,
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.exception("React Agent Exception!%s", dialogue, exc_info=e)

        async def error_text(err_msg):
            yield f"data:{err_msg}\n\n"

        return StreamingResponse(
            error_text(str(e)),
            headers=headers,
            media_type="text/plain",
        )

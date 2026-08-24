#!/usr/bin/env python
# /// script
# dependencies = [
#   "tomli",
#   "click",
#   "inquirer",
# ]
# [tool.uv]
# exclude-newer = "2025-03-07T00:00:00Z"
# ///
import glob
import os
from pathlib import Path
from typing import Any, Dict

import click
import inquirer
import tomli


# For I18N support, we use a simple class to store translations and a global instance
# to access it.
class I18N:
    # Define supported languages in current install help script
    SUPPORTED_LANGUAGES = ["en", "zh"]

    # The translation dictionary contains a mapping from language code to a dictionary
    TRANSLATIONS = {
        "en": {
            # Common
            "workspace_not_found": "Workspace root not found.",
            "cannot_parse": "Cannot parse {}: {}",
            "no_extras_defined": "No extras defined",
            "no_extras_found": "No workspace or extras found.",
            "operation_canceled": "Operation canceled.",
            "available_packages": "Available packages: {}",
            "copy_command": "Please copy the above command to execute in terminal. For more help, run:",
            "finished": "Finished!",
            # Description of the CLI command
            "cli_description": "UV Workspace Extras Helper - Manage optional dependencies in UV workspace",
            "list_cmd_description": "List all extras in the workspace",
            "install_cmd_description": "Generate installation commands for extras",
            "deploy_cmd_description": "Use predefined deployment templates",
            # Option descriptions
            "verbose_option": "Show detailed dependency information",
            "interactive_option": "Interactive guide to generate installation commands",
            "all_option": "Generate command to install all extras",
            "china_option": "Use Tsinghua PyPI mirror for faster installation in China",
            "preset_option": "Use predefined deployment template",
            "list_presets_option": "List all predefined deployment templates",
            "language_option": "Specify language (en/zh)",
            # List command
            "extras_in_workspace": "Extras in workspace:\n",
            "available_extras": "Available extras:",
            "dependencies": "dependencies",
            # Installation command
            "install_all_extras": "# Install all optional features:",
            "install_extras_for": "# Install {} feature for {}:",
            "package_not_in_workspace": "Error: Package '{}' not in workspace or has no extras defined.",
            "package_no_extras": "Package '{}' has no extras defined.",
            "extra_not_in_package": "Error: Extra '{}' not found in package '{}'.",
            "available_extras_in_package": "Available extras: {}",
            # Interactive installation
            "welcome": "Welcome to DB-GPT Installation Assistant!",
            "help_message": "This tool will help you generate the correct installation commands.\n",
            "select_mode": "Please select installation mode",
            "select_extras": "Please select extras to install (space to select/deselect, enter to confirm)",
            "installation_info": "📋 Installation Information",
            "selected_mode": "📦 Selected mode: {}",
            "description": "📝 Description: {}",
            "note": "ℹ️  Note: {}",
            "will_install": "🧩 Will install the following extras: {}",
            "config_file": "⚙️  Configuration file: {}",
            "generate_command": "Generate installation command?",
            "installation_command": "🚀 Installation Command",
            "startup_command": "🏃 Startup Command",
            "further_configuration": "⚠️  Further Configuration",
            "set_api_key": "Please make sure you set the correct API Key in the configuration file {}",
            "set_model_path": "Please make sure you set the correct model path in the configuration file {}",
            # Deployment command
            "available_presets": "Available deployment presets:",
            "specify_preset": "Please specify a deployment preset name, or use --list to view all presets",
            "preset_not_found": "Error: Preset '{}' not found",
            "available_presets_list": "Available presets: {}",
            "using_preset": "Using preset '{}' to generate deployment command",
            # Preset descriptions
            "openai_preset": "OpenAI Proxy Mode",
            "openai_desc": "Using OpenAI API as proxy, suitable for environments without GPU",
            "openai_note": "Requires OpenAI API Key",
            "deepseek_preset": "DeepSeek Proxy Mode",
            "deepseek_desc": "Using DeepSeek API as proxy, suitable for environments without GPU",
            "deepseek_note": "Requires DeepSeek API Key",
            "glm4_preset": "GLM4 Local Mode",
            "glm4_desc": "Using local GLM4 model, requires GPU environment",
            "glm4_note": "Requires local model path configuration",
            "vllm_preset": "VLLM Local Mode",
            "vllm_desc": "Using VLLM framework to load local model, requires GPU environment",
            "vllm_note": "Requires local model path configuration",
            "llama_cpp_preset": "LLAMA_CPP Local Mode",
            "llama_cpp_desc": "Using LLAMA.cpp framework to load local model, can run on CPU but GPU recommended",
            "llama_cpp_note": 'Requires local model path configuration, for CUDA support set CMAKE_ARGS="-DGGML_CUDA=ON"',
            "ollama_preset": "Ollama Proxy Mode",
            "ollama_desc": "Using Ollama as proxy, suitable for environments without GPU",
            "ollama_note": "Requires Ollama API Base",
            "custom_preset": "Custom Mode",
            "custom_desc": "Manually select needed extras",
            "custom_note": "Suitable for advanced users",
        },
        "zh": {
            # Common
            "workspace_not_found": "未找到工作区根目录",
            "cannot_parse": "无法解析 {}: {}",
            "no_extras_defined": "没有定义 extras",
            "no_extras_found": "未找到工作区或没有可选依赖。",
            "operation_canceled": "操作已取消。",
            "available_packages": "可用的包: {}",
            "copy_command": "请复制上面的命令到终端执行。如需更多帮助，请运行：",
            "finished": "完成！",
            # Description of the CLI command
            "cli_description": "UV Workspace Extras Helper - 管理UV工作区的可选依赖",
            "list_cmd_description": "列出工作区中的所有extras",
            "install_cmd_description": "生成安装extras的命令",
            "deploy_cmd_description": "使用预设的部署方案",
            # Option descriptions
            "verbose_option": "显示详细依赖信息",
            "interactive_option": "交互式引导生成安装命令",
            "all_option": "生成安装所有extras的命令",
            "china_option": "使用清华pip镜像源加速安装",
            "preset_option": "使用预设的部署方案",
            "list_presets_option": "列出所有预设部署方案",
            "language_option": "指定语言 (en/zh)",
            # List command
            "extras_in_workspace": "工作区中的可选依赖 (extras):\n",
            "available_extras": "可用的 extras:",
            "dependencies": "个依赖",
            # Installation command
            "install_all_extras": "# 安装所有可选功能:",
            "install_extras_for": "# 安装 {} 的 {} 功能:",
            "package_not_in_workspace": "错误: 包 '{}' 不在工作区中或没有定义extras。",
            "package_no_extras": "包 '{}' 没有定义extras。",
            "extra_not_in_package": "错误: 包 '{}' 中没有名为 '{}' 的extra。",
            "available_extras_in_package": "可用的extras: {}",
            # Interactive installation
            "welcome": "欢迎使用 DB-GPT 安装引导助手！",
            "help_message": "这个工具将帮助你生成正确的安装命令。\n",
            "select_mode": "请选择安装模式",
            "select_extras": "请选择需要安装的extras（空格选择/取消，回车确认）",
            "installation_info": "📋 安装信息",
            "selected_mode": "📦 选择的模式: {}",
            "description": "📝 描述: {}",
            "note": "ℹ️  注意事项: {}",
            "will_install": "🧩 将安装以下extras: {}",
            "config_file": "⚙️  配置文件: {}",
            "generate_command": "是否生成安装命令？",
            "installation_command": "🚀 安装命令",
            "startup_command": "🏃 启动命令",
            "further_configuration": "⚠️  后续配置",
            "set_api_key": "请确保在配置文件 {} 中设置了正确的API Key",
            "set_model_path": "请确保在配置文件 {} 中设置了正确的模型路径",
            # Deployment command
            "available_presets": "可用的部署预设:",
            "specify_preset": "请指定部署预设名称，或使用 --list 查看所有预设",
            "preset_not_found": "错误: 未找到预设 '{}'",
            "available_presets_list": "可用的预设: {}",
            "using_preset": "使用预设 '{}' 生成部署命令",
            # Preset descriptions
            "openai_preset": "OpenAI 代理模式",
            "openai_desc": "使用OpenAI API作为代理，适合无GPU环境",
            "openai_note": "需要提供OpenAI API Key",
            "deepseek_preset": "DeepSeek 代理模式",
            "deepseek_desc": "使用DeepSeek API作为代理，适合无GPU环境",
            "deepseek_note": "需要提供DeepSeek API Key",
            "glm4_preset": "GLM4 本地模式",
            "glm4_desc": "使用本地GLM4模型，需要GPU环境",
            "glm4_note": "需要配置本地模型路径",
            "vllm_preset": "VLLM 本地模式",
            "vllm_desc": "使用VLLM框架加载本地模型，需要GPU环境",
            "vllm_note": "需要配置本地模型路径",
            "llama_cpp_preset": "LLAMA_CPP 本地模式",
            "llama_cpp_desc": "使用LLAMA.cpp框架加载本地模型，CPU也可运行但推荐GPU",
            "llama_cpp_note": '需要配置本地模型路径，启用CUDA需设置CMAKE_ARGS="-DGGML_CUDA=ON"',
            "ollama_preset": "Ollama 代理模式",
            "ollama_desc": "使用Ollama作为代理，适合无GPU环境",
            "ollama_note": "需要提供Ollama API Base",
            "custom_preset": "自定义模式",
            "custom_desc": "手动选择需要的extras",
            "custom_note": "适合高级用户",
        },
    }

    def __init__(self, lang=None):
        """Initialize the I18N instance with the specified language"""
        # If language is not specified, try to get from environment
        if not lang:
            try:
                import locale

                try:
                    # First try to get the locale from the environment
                    lang = locale.getlocale()[0]
                except (AttributeError, ValueError):
                    try:
                        lang = locale.getdefaultlocale()[0]
                    except (AttributeError, ValueError):
                        lang = "en"

                if lang:
                    lang = lang.split("_")[0]
                else:
                    lang = "en"
            except (ImportError, AttributeError, ValueError):
                lang = "en"

        # If the language is not supported, default to English
        if lang not in self.SUPPORTED_LANGUAGES:
            lang = "en"

        self.lang = lang

    def get(self, key):
        """Get the translation for the specified key"""
        return self.TRANSLATIONS.get(self.lang, {}).get(key, key)


i18n = I18N()


def set_language(lang):
    """Set the global language for the script"""
    global i18n
    i18n = I18N(lang)


def extract_workspace_extras():
    """Determine the workspace root and extract extras dependencies for all packages"""
    # First locate the workspace root (directory containing pyproject.toml with
    # tool.uv.workspace)
    current_dir = os.getcwd()
    workspace_root = None

    # Find the workspace root
    while current_dir != os.path.dirname(current_dir):  # Stop at root
        pyproject_path = os.path.join(current_dir, "pyproject.toml")
        if os.path.exists(pyproject_path):
            try:
                with open(pyproject_path, "rb") as f:
                    pyproject_data = tomli.load(f)
                    if pyproject_data.get("tool", {}).get("uv", {}).get("workspace"):
                        workspace_root = current_dir
                        break
            except Exception as e:
                print(i18n.get("cannot_parse").format(pyproject_path, e))
        current_dir = os.path.dirname(current_dir)

    if not workspace_root:
        print(i18n.get("workspace_not_found"))
        return {}

    # Read the workspace configuration
    with open(os.path.join(workspace_root, "pyproject.toml"), "rb") as f:
        root_data = tomli.load(f)

    workspace_config = root_data.get("tool", {}).get("uv", {}).get("workspace", {})
    members_patterns = workspace_config.get("members", [])
    exclude_patterns = workspace_config.get("exclude", [])

    # Extract all member packages
    member_dirs = []
    for pattern in members_patterns:
        # Convert glob pattern to absolute path
        full_pattern = os.path.join(workspace_root, pattern)
        matches = glob.glob(full_pattern, recursive=True)

        for match in matches:
            if os.path.isdir(match) and os.path.exists(
                os.path.join(match, "pyproject.toml")
            ):
                # Check if the directory should be excluded
                should_exclude = False
                for exclude_pattern in exclude_patterns:
                    if Path(match).match(os.path.join(workspace_root, exclude_pattern)):
                        should_exclude = True
                        break

                if not should_exclude:
                    member_dirs.append(match)

    # Add the workspace root as a member package
    member_dirs.append(workspace_root)

    # Extract extras for each member package
    all_extras = {}

    for member_dir in member_dirs:
        member_path = os.path.join(member_dir, "pyproject.toml")
        try:
            with open(member_path, "rb") as f:
                member_data = tomli.load(f)

            project_name = member_data.get("project", {}).get(
                "name", os.path.basename(member_dir)
            )
            optional_deps = member_data.get("project", {}).get(
                "optional-dependencies", {}
            )

            if optional_deps:
                all_extras[project_name] = {
                    "path": member_dir,
                    "extras": list(optional_deps.keys()),
                    "details": optional_deps,
                }

        except Exception as e:
            print(i18n.get("cannot_parse").format(member_path, e))

    return all_extras


# Preset deployment templates
def get_deployment_presets():
    """Get localized deployment presets"""
    return {
        i18n.get("openai_preset"): {
            "extras": ["base", "proxy_openai", "rag", "storage_chromadb", "dbgpts"],
            "config": "configs/dbgpt-proxy-openai.toml",
            "description": i18n.get("openai_desc"),
            "note": i18n.get("openai_note"),
        },
        i18n.get("deepseek_preset"): {
            "extras": ["base", "proxy_openai", "rag", "storage_chromadb", "dbgpts"],
            "config": "configs/dbgpt-proxy-deepseek.toml",
            "description": i18n.get("deepseek_desc"),
            "note": i18n.get("deepseek_note"),
        },
        i18n.get("glm4_preset"): {
            "extras": [
                "base",
                "hf",
                "cuda121",
                "rag",
                "storage_chromadb",
                "quant_bnb",
                "dbgpts",
            ],
            "config": "configs/dbgpt-local-glm.toml",
            "description": i18n.get("glm4_desc"),
            "note": i18n.get("glm4_note"),
        },
        i18n.get("vllm_preset"): {
            "extras": [
                "base",
                "hf",
                "cuda121",
                "vllm",
                "rag",
                "storage_chromadb",
                "quant_bnb",
                "dbgpts",
            ],
            "config": "configs/dbgpt-local-vllm.toml",
            "description": i18n.get("vllm_desc"),
            "note": i18n.get("vllm_note"),
        },
        i18n.get("llama_cpp_preset"): {
            "extras": [
                "base",
                "hf",
                "cuda121",
                "llama_cpp",
                "rag",
                "storage_chromadb",
                "quant_bnb",
                "dbgpts",
            ],
            "config": "configs/dbgpt-local-llama-cpp.toml",
            "description": i18n.get("llama_cpp_desc"),
            "note": i18n.get("llama_cpp_note"),
        },
        i18n.get("ollama_preset"): {
            "extras": ["base", "proxy_ollama", "rag", "storage_chromadb", "dbgpts"],
            "config": "configs/dbgpt-proxy-ollama.toml",
            "description": i18n.get("ollama_desc"),
            "note": i18n.get("ollama_note"),
        },
        i18n.get("custom_preset"): {
            "extras": [],
            "config": "",
            "description": i18n.get("custom_desc"),
            "note": i18n.get("custom_note"),
        },
    }


@click.group()
@click.option(
    "--language",
    "-l",
    type=click.Choice(["en", "zh"]),
    help=I18N().get("language_option"),
)
def cli(language):
    """UV Workspace Extras Helper - Manage optional dependencies in UV workspace"""
    if language:
        set_language(language)
    # Update command descriptions to the current language
    cli.help = i18n.get("cli_description")
    list_extras.help = i18n.get("list_cmd_description")
    install_command.help = i18n.get("install_cmd_description")
    deploy_preset.help = i18n.get("deploy_cmd_description")


@cli.command("list")
@click.option("--verbose", "-v", is_flag=True, help=i18n.get("verbose_option"))
def list_extras(verbose):
    """List all extras in the workspace"""
    extras = extract_workspace_extras()

    if not extras:
        click.echo(i18n.get("no_extras_found"))
        return

    click.echo(i18n.get("extras_in_workspace"))

    for package, info in extras.items():
        click.echo(
            click.style(f"📦 {package}", fg="green")
            + click.style(f" ({os.path.relpath(info['path'])})", fg="blue")
        )

        if info["extras"]:
            click.echo(f"  {i18n.get('available_extras')}")
            for extra in info["extras"]:
                deps = info["details"][extra]
                click.echo(
                    f"    - {click.style(extra, fg='yellow')}: {len(deps)} {i18n.get('dependencies')}"
                )

                if verbose:
                    for dep in deps:
                        click.echo(f"      • {dep}")
        else:
            click.echo(f"  {i18n.get('no_extras_defined')}")
        click.echo()


@cli.command("install-cmd")
@click.option("--interactive", "-i", is_flag=True, help=i18n.get("interactive_option"))
@click.option("--all", "install_all", is_flag=True, help=i18n.get("all_option"))
@click.option("--china", is_flag=True, help=i18n.get("china_option"))
@click.argument("package", required=False)
@click.argument("extra", required=False)
def install_command(interactive, install_all, china, package, extra):
    """Generate installation commands for extras"""
    extras = extract_workspace_extras()

    if not extras:
        click.echo(i18n.get("no_extras_found"))
        return

    # Interactive mode
    if interactive:
        _interactive_install_guide(extras, china)
        return

    # Install all extras
    if install_all:
        all_extras = []
        for pkg_info in extras.values():
            all_extras.extend(pkg_info["extras"])

        if all_extras:
            cmd = "uv sync --all-packages " + " ".join(
                [f'--extra "{e}"' for e in all_extras]
            )
            if china:
                cmd += " --index-url=https://pypi.tuna.tsinghua.edu.cn/simple"
            click.echo(i18n.get("install_all_extras"))
            click.echo(cmd)
        else:
            click.echo(i18n.get("no_extras_found"))
        return

    # If no package or extra is provided, show all possible installation commands
    if not package:
        for pkg, info in extras.items():
            if info["extras"]:
                for e in info["extras"]:
                    cmd = f'uv sync --extra "{e}"'
                    if china:
                        cmd += " --index-url=https://pypi.tuna.tsinghua.edu.cn/simple"
                    click.echo(i18n.get("install_extras_for").format(pkg, e))
                    click.echo(cmd)
                click.echo()
        return

    # Check if the specified package exists
    if package not in extras:
        click.echo(i18n.get("package_not_in_workspace").format(package))
        click.echo(i18n.get("available_packages").format(", ".join(extras.keys())))
        return

    # If no extra is provided, show all extras for the package
    if not extra:
        pkg_extras = extras[package]["extras"]
        if not pkg_extras:
            click.echo(i18n.get("package_no_extras").format(package))
            return

        cmd = "uv sync " + " ".join([f'--extra "{e}"' for e in pkg_extras])
        if china:
            cmd += " --index-url=https://pypi.tuna.tsinghua.edu.cn/simple"
        click.echo(i18n.get("install_extras_for").format(package, " ".join(pkg_extras)))
        click.echo(cmd)
        return

    # Check if the specified extra exists
    if extra not in extras[package]["extras"]:
        click.echo(i18n.get("extra_not_in_package").format(extra, package))
        click.echo(
            i18n.get("available_extras_in_package").format(
                ", ".join(extras[package]["extras"])
            )
        )
        return

    # Show the command to install the specified extra
    cmd = f'uv sync --extra "{extra}"'
    if china:
        cmd += " --index-url=https://pypi.tuna.tsinghua.edu.cn/simple"
    click.echo(i18n.get("install_extras_for").format(package, extra))
    click.echo(cmd)


def _interactive_install_guide(extras: Dict[str, Any], use_china_mirror: bool = False):
    """Interactive installation guide"""
    click.echo(click.style(i18n.get("welcome"), fg="green", bold=True))
    click.echo(i18n.get("help_message"))

    # Get deployment presets
    deployment_presets = get_deployment_presets()

    # First step: select installation mode
    questions = [
        inquirer.List(
            "preset",
            message=i18n.get("select_mode"),
            choices=[
                (f"{name} - {info['description']}", name)
                for name, info in deployment_presets.items()
            ],
            carousel=True,
        )
    ]
    answers = inquirer.prompt(questions)

    if not answers:
        return  # Operation canceled

    selected_preset = answers["preset"]
    preset_info = deployment_presets[selected_preset]

    # Custom mode: let user select extras
    if selected_preset == i18n.get("custom_preset"):
        # Collect all available extras
        all_available_extras = set()
        for pkg_info in extras.values():
            all_available_extras.update(pkg_info["extras"])

        questions = [
            inquirer.Checkbox(
                "selected_extras",
                message=i18n.get("select_extras"),
                choices=sorted(list(all_available_extras)),
                carousel=True,
            )
        ]
        answers = inquirer.prompt(questions)

        if not answers or not answers["selected_extras"]:
            click.echo(i18n.get("operation_canceled"))
            return

        preset_info["extras"] = answers["selected_extras"]

    # Show installation information
    click.echo("\n" + click.style(i18n.get("installation_info"), fg="blue", bold=True))
    click.echo(
        f"{i18n.get('selected_mode')} {click.style(selected_preset, fg='green')}"
    )
    click.echo(f"{i18n.get('description')} {preset_info['description']}")
    click.echo(f"{i18n.get('note')} {preset_info['note']}")
    click.echo(f"{i18n.get('will_install')} {', '.join(preset_info['extras'])}")

    if preset_info["config"]:
        click.echo(f"{i18n.get('config_file')} {preset_info['config']}")

    # Confirm installation
    questions = [
        inquirer.Confirm("confirm", message=i18n.get("generate_command"), default=True)
    ]
    answers = inquirer.prompt(questions)

    if not answers or not answers["confirm"]:
        click.echo(i18n.get("operation_canceled"))
        return

    # Create installation command
    cmd = "uv sync --all-packages " + " ".join(
        [f'--extra "{e}"' for e in preset_info["extras"]]
    )
    if use_china_mirror:
        cmd += " --index-url=https://pypi.tuna.tsinghua.edu.cn/simple"

    click.echo(
        "\n" + click.style(i18n.get("installation_command"), fg="green", bold=True)
    )
    click.echo(cmd)

    if preset_info.get("config"):
        click.echo(
            "\n" + click.style(i18n.get("startup_command"), fg="green", bold=True)
        )
        click.echo(f"uv run dbgpt start webserver --config {preset_info['config']}")

    # The step to configure the API key or model path
    if (
        i18n.get("openai_note") in preset_info["note"]
        or i18n.get("deepseek_note") in preset_info["note"]
    ):
        click.echo(
            "\n"
            + click.style(i18n.get("further_configuration"), fg="yellow", bold=True)
        )
        if (
            i18n.get("openai_note") in preset_info["note"]
            or i18n.get("deepseek_note") in preset_info["note"]
        ):
            click.echo(i18n.get("set_api_key").format(preset_info["config"]))
    elif (
        i18n.get("glm4_note") in preset_info["note"]
        or i18n.get("vllm_note") in preset_info["note"]
        or i18n.get("llama_cpp_note") in preset_info["note"]
    ):
        click.echo(
            "\n"
            + click.style(i18n.get("further_configuration"), fg="yellow", bold=True)
        )
        if (
            i18n.get("glm4_note") in preset_info["note"]
            or i18n.get("vllm_note") in preset_info["note"]
            or i18n.get("llama_cpp_note") in preset_info["note"]
        ):
            click.echo(i18n.get("set_model_path").format(preset_info["config"]))

    click.echo("\n" + click.style(f"🎉 {i18n.get('finished')}", fg="green", bold=True))
    click.echo(i18n.get("copy_command"))
    click.echo("uv run install_help.py --help")


@cli.command("deploy")
@click.option("--preset", "-p", help=i18n.get("preset_option"))
@click.option("--china", is_flag=True, help=i18n.get("china_option"))
@click.option(
    "--list", "list_presets", is_flag=True, help=i18n.get("list_presets_option")
)
def deploy_preset(preset, china, list_presets):
    """Use predefined deployment templates"""
    deployment_presets = get_deployment_presets()

    if list_presets:
        click.echo(click.style(i18n.get("available_presets"), fg="green", bold=True))
        for name, info in deployment_presets.items():
            click.echo(f"\n{click.style(name, fg='yellow', bold=True)}")
            click.echo(f"{i18n.get('description')} {info['description']}")
            click.echo(f"{i18n.get('note')} {info['note']}")
            click.echo(f"Extras: {', '.join(info['extras'])}")
            if info["config"]:
                click.echo(f"{i18n.get('config_file')} {info['config']}")
        return

    if not preset:
        click.echo(i18n.get("specify_preset"))
        return

    if preset not in deployment_presets:
        click.echo(i18n.get("preset_not_found").format(preset))
        click.echo(
            i18n.get("available_presets_list").format(
                ", ".join(deployment_presets.keys())
            )
        )
        return

    preset_info = deployment_presets[preset]

    click.echo(i18n.get("using_preset").format(preset))
    click.echo(f"{i18n.get('description')} {preset_info['description']}")
    click.echo(f"{i18n.get('note')} {preset_info['note']}")

    cmd = "uv sync --all-packages " + " ".join(
        [f'--extra "{e}"' for e in preset_info["extras"]]
    )
    if china:
        cmd += " --index-url=https://pypi.tuna.tsinghua.edu.cn/simple"

    click.echo(
        "\n" + click.style(i18n.get("installation_command"), fg="green", bold=True)
    )
    click.echo(cmd)

    if preset_info.get("config"):
        click.echo(
            "\n" + click.style(i18n.get("startup_command"), fg="green", bold=True)
        )
        click.echo(f"uv run dbgpt start webserver --config {preset_info['config']}")


if __name__ == "__main__":
    cli()

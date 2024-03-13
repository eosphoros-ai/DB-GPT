import os

import click


@click.command(name="serve")
@click.option(
    "-n",
    "--name",
    required=True,
    type=str,
    show_default=True,
    help="The name of the serve module to create",
)
@click.option(
    "-t",
    "--template",
    required=False,
    type=str,
    default="default_serve_template",
    show_default=True,
    help="The template to use to create the serve module",
)
def serve(name: str, template: str):
    """Create a serve module structure with the given name."""
    from dbgpt.configs.model_config import ROOT_PATH

    base_path = os.path.join(ROOT_PATH, "dbgpt", "serve", name)
    template_path = os.path.join(
        ROOT_PATH, "dbgpt", "serve", "utils", "_template_files", template
    )
    if not os.path.exists(template_path):
        raise ValueError(f"Template '{template}' not found")
    if os.path.exists(base_path):
        # TODO: backup the old serve module
        click.confirm(
            f"Serve module '{name}' already exists in {base_path}, do you want to overwrite it?",
            abort=True,
        )
        import shutil

        shutil.rmtree(base_path)

    copy_template_files(template_path, base_path, name)
    click.echo(f"Serve application '{name}' created successfully in {base_path}")


def replace_template_variables(content: str, app_name: str):
    """Replace the template variables in the given content with the given app name."""
    template_values = {
        "{__template_app_name__}": app_name,
        "{__template_app_name__all_lower__}": app_name.lower(),
        "{__template_app_name__hump__}": "".join(
            part.capitalize() for part in app_name.split("_")
        ),
    }

    for key in sorted(template_values, key=len, reverse=True):
        content = content.replace(key, template_values[key])

    return content


def copy_template_files(src_dir: str, dst_dir: str, app_name: str):
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if not _should_ignore(d)]
        relative_path = os.path.relpath(root, src_dir)
        if relative_path == ".":
            relative_path = ""

        target_dir = os.path.join(dst_dir, relative_path)
        os.makedirs(target_dir, exist_ok=True)

        for file in files:
            if _should_ignore(file):
                continue
            try:
                with open(os.path.join(root, file), "r") as f:
                    content = f.read()

                content = replace_template_variables(content, app_name)

                with open(os.path.join(target_dir, file), "w") as f:
                    f.write(content)
            except Exception as e:
                click.echo(f"Error copying file {file} from {src_dir} to {dst_dir}")
                raise e


def _should_ignore(file_or_dir: str):
    """Return True if the given file or directory should be ignored.""" ""
    ignore_patterns = [".pyc", "__pycache__"]
    return any(pattern in file_or_dir for pattern in ignore_patterns)

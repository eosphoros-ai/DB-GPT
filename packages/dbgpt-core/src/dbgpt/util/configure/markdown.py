import hashlib
import json
import logging
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Type

from dbgpt.util.configure.manager import (
    ConfigurationManager,
    RegisterParameters,
)
from dbgpt.util.module_utils import import_from_string
from dbgpt.util.parameter_utils import ParameterDescription

logger = logging.getLogger(__name__)


def is_direct_subclass(cls, parent_cls):
    """Determine if a class is a direct subclass of another class."""
    # Check if the class is a subclass of the parent class
    if not issubclass(cls, parent_cls):
        return False

    # Check if the class is a direct subclass of the parent class
    return parent_cls in cls.__bases__


def _is_skip_class(cls):
    return is_direct_subclass(cls, RegisterParameters)


class MDXDocGenerator:
    def __init__(self):
        self.processed_classes: Set[str] = set()
        self.link_cache: Dict[str, str] = {}  # {class_path: filename}
        self._doc_cache: Dict[str, str] = {}
        self.generated_files: Set[str] = set()

    def generate_safe_filename(self, doc_id: str) -> str:
        """Generate a safe filename for the given doc_id."""
        if doc_id in self.link_cache:
            return self.link_cache[doc_id]

        parts = doc_id.split(".")[-2:]  # Just use the last two parts
        main_part = "_".join(parts)
        hash_suffix = hashlib.md5(doc_id.encode()).hexdigest()[:6]
        filename = f"{main_part}_{hash_suffix}.mdx".lower()
        self.link_cache[doc_id] = filename
        return filename

    def get_abs_link(self, cls: Type, doc_id: str) -> str:
        filename = self.generate_safe_filename(doc_id)
        link_url = "/docs/config-reference/"
        cfg_type, _ = self._parse_class_metadata(cls)
        if cfg_type:
            link_url += f"{cfg_type}/"
        link_url += filename[:-4]
        return link_url

    def get_rel_link(self, cls: Type, doc_id: str, source_cls: Type = None) -> str:
        """Generate a relative link from the source class to the target class.

        Args:
            cls: The target class to generate a link to
            doc_id: The document ID of the target class
            source_cls: The source class that will contain the link (optional)

        Returns:
            A relative URL path to the target class documentation
        """
        filename = self.generate_safe_filename(doc_id)
        target_type, _ = self._parse_class_metadata(cls)

        # If source_cls is not provided, return a simple path without relative
        # navigation
        if not source_cls:
            if target_type:
                return f"{target_type}/{filename[:-4]}"
            return filename[:-4]

        # Get the source class type to determine relative path
        source_type, _ = self._parse_class_metadata(source_cls)

        # Same type - link within the same directory
        if source_type == target_type:
            return filename[:-4]

        # Different types - need to navigate up and then down
        if source_type and target_type:
            return f"../{target_type}/{filename[:-4]}"
        elif source_type and not target_type:
            return f"../{filename[:-4]}"
        elif not source_type and target_type:
            return f"{target_type}/{filename[:-4]}"
        else:
            return filename[:-4]

    def get_desc_for_class(self, cls: Type, default_desc: str = "") -> str:
        """Get the description for a class."""
        doc_id = self.get_class_doc_id(cls)
        return self._doc_cache.get(doc_id, default_desc)

    def get_class_doc_id(self, cls: Type) -> str:
        """Get the unique identifier for a class."""
        return f"{cls.__module__}.{cls.__name__}"

    def convert_to_mdx_dict(self, value: Any) -> Dict:
        """Convert a value to a dictionary that can be used in MDX components."""
        if value is None:
            return {"type": "code", "content": "None"}

        if is_dataclass(type(value)):
            return {"type": "code", "content": value.__class__.__name__}

        if isinstance(value, str):
            if "${" in value or "/" in value:
                return {"type": "code", "content": value}
            if len(value) > 50:
                return {"type": "codeblock", "content": value}
            return {"type": "code", "content": value}

        if isinstance(value, (list, dict, tuple)):
            return {"type": "codeblock", "language": "python", "content": repr(value)}

        return {"type": "code", "content": str(value)}

    def process_nested_fields(
        self,
        nested_fields: Dict[str, List[ParameterDescription]],
        output_dir: Path,
        source_cls: Type,
    ) -> Tuple[List[Dict], List[str]]:
        """Handle nested fields in a parameter description."""
        links = []
        generated_files = []

        for type_name, params in nested_fields.items():
            if not params:
                continue

            try:
                nested_cls = import_from_string(params[0].param_class)

                doc_id = self.get_class_doc_id(nested_cls)

                if doc_id not in self.processed_classes:
                    new_files = self.generate_class_doc(nested_cls, output_dir)
                    generated_files.extend(new_files)
                # Use relative link instead of absolute link
                link_url = self.get_rel_link(nested_cls, doc_id, source_cls=source_cls)
                links.append(
                    {
                        "type": "link",
                        "text": f"{type_name} configuration",
                        "url": f"{link_url}",
                    }
                )

            except ImportError:
                logger.warning(
                    f"Cann't import configuration class: {params[0].param_class}"
                )
                links.append({"type": "text", "content": type_name})

        return links, generated_files

    def _parse_class_doc(self, param_cls: Type) -> Tuple[str, str, str]:
        metadata_name = f"_resource_metadata_{param_cls.__name__}"
        if hasattr(param_cls, metadata_name):
            from dbgpt.core.awel.flow import ResourceMetadata

            flow_metadata: ResourceMetadata = getattr(param_cls, metadata_name)
            label = flow_metadata.label
            description = flow_metadata.description
            documentation_url = flow_metadata.documentation_url
        else:
            label = param_cls.__name__
            description = param_cls.__doc__.strip() if param_cls.__doc__ else ""
            documentation_url = ""
        return label, description, documentation_url

    def _parse_class_metadata(self, param_cls: Type) -> Tuple[str | None, str | None]:
        cfg_type = None
        cfg_desc = None
        if hasattr(param_cls, "__cfg_type__"):
            cfg_type = getattr(param_cls, "__cfg_type__")
        if hasattr(param_cls, "__cfg_desc__"):
            cfg_desc = getattr(param_cls, "__cfg_desc__")
        return cfg_type, cfg_desc

    def generate_class_doc(self, cls: Type, output_dir: Path) -> List[str]:
        """Generate documentation for a configuration class."""
        # if _is_base_config(cls) or cls is RegisterParameters:
        #     return []
        if not is_dataclass(cls):
            return []
        doc_id = self.get_class_doc_id(cls)
        if doc_id in self.processed_classes:
            return []

        self.processed_classes.add(doc_id)
        generated_files = []

        descriptions = ConfigurationManager.parse_description(
            cls, cache_enable=True, verbose=True
        )
        cfg_type, cfg_desc = self._parse_class_metadata(cls)

        filename = self.generate_safe_filename(doc_id)
        if cfg_type:
            output_path = output_dir / cfg_type / filename
        else:
            output_path = output_dir / filename

        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)
        generated_files.append(filename)

        cls_label, cls_desc, cls_doc_url = self._parse_class_doc(cls)
        self._doc_cache[doc_id] = cls_desc
        with open(output_path, "w", encoding="utf-8") as f:
            # Add frontmatter to set the page title
            f.write("---\n")
            f.write(f'title: "{cls_label} Configuration"\n')
            f.write(f'description: "{cls_desc}"\n')
            f.write("---\n\n")

            # Use custom component to render the config detail
            _config_component = '"@site/src/components/mdx/ConfigDetail";\n\n'
            f.write("import { ConfigDetail } from " + _config_component)

            # Build the full config data
            config_data = {
                "name": cls.__name__,
                "description": cls_desc,
                "documentationUrl": cls_doc_url,
                "parameters": [],
            }

            for param in sorted(
                descriptions,
                key=lambda x: (
                    x.param_order
                    if x.param_order is not None
                    else (1000 if x.required else float("inf"))
                ),
            ):
                param_data = {
                    "name": param.param_name,
                    "type": param.param_type or "",
                    "required": param.required,
                    "description": param.description or "",
                }
                # Handle nested fields
                if param.nested_fields:
                    nested_links, nested_files = self.process_nested_fields(
                        param.nested_fields, output_dir, source_cls=cls
                    )
                    generated_files.extend(nested_files)
                    if nested_links:
                        param_data["nestedTypes"] = nested_links

                # Handle default value
                if param.default_value is not None:
                    if is_dataclass(type(param.default_value)):
                        param_data["defaultValue"] = (
                            param.default_value.__class__.__name__
                        )
                    else:
                        param_data["defaultValue"] = str(param.default_value)

                # Handle valid values
                if param.valid_values:
                    param_data["validValues"] = [str(v) for v in param.valid_values]

                config_data["parameters"].append(param_data)

            # Write the config detail component
            f.write("<ConfigDetail config={")
            f.write(json.dumps(config_data, indent=2, ensure_ascii=False))
            f.write("} />\n\n")

            # If the class is abstract, list all concrete implementations
            if hasattr(cls, "__abstract__"):
                subs = [c for c in cls.__subclasses__() if is_dataclass(c)]
                if subs:
                    f.write("## Implementations\n\n")
                    for sub_cls in subs:
                        sub_files = self.generate_class_doc(sub_cls, output_dir)
                        generated_files.extend(sub_files)

                        sub_doc_id = self.get_class_doc_id(sub_cls)
                        sub_filename = self.generate_safe_filename(sub_doc_id)
                        f.write(
                            f"- [{sub_cls.__name__} configuretion](./{sub_filename})\n"
                        )

        self.generated_files.add(filename)
        return generated_files

    def _collect_relationships(
        self, cls: Type, processed: Set[str], relationships: List[Dict]
    ):
        """Collect relationships between classes."""

        if not is_dataclass(cls):
            return
        class_id = self.get_class_doc_id(cls)
        if class_id in processed:
            return
        processed.add(class_id)

        descriptions = ConfigurationManager.parse_description(
            cls, cache_enable=True, verbose=True
        )
        for param in descriptions:
            if param.nested_fields:
                for nested_type, nested_params in param.nested_fields.items():
                    if nested_params:
                        try:
                            nested_cls = import_from_string(
                                nested_params[0].param_class
                            )
                            relationships.append(
                                {
                                    "from": cls.__name__,
                                    "to": nested_cls.__name__,
                                    "label": param.param_name,
                                }
                            )
                            self._collect_relationships(
                                nested_cls, processed, relationships
                            )
                        except ImportError:
                            logger.warning(
                                "Can't import configuration class: "
                                f"{nested_params[0].param_class}"
                            )

    def generate_overview(self, output_dir: Path, config_classes: List[Type]):
        """Generate an overview document for all configuration classes grouped by
        __cfg_type__."""

        overview_path = output_dir / "overview.mdx"

        # Collect all relationships between classes
        relationships = []
        processed = set()

        for cls in config_classes:
            self._collect_relationships(cls, processed, relationships)

        # Group classes by __cfg_type__
        type_groups = {}
        class_map = {
            cls.__name__: cls for cls in config_classes if hasattr(cls, "__name__")
        }

        # Get all classes and group them by __cfg_type__
        for cls in config_classes:
            if _is_skip_class(cls):
                logger.info("Skipping class: %s", cls)
                continue
            # Otherwise, default to "other"
            cfg_type = getattr(cls, "__cfg_type__", "other")
            if not cfg_type:
                cfg_type = "other"

            if cfg_type not in type_groups:
                type_groups[cfg_type] = []
            type_groups[cfg_type].append(cls)

        # type_relationships = {cfg_type: [] for cfg_type in type_groups}
        type_relationships = {}
        for rel in relationships:
            from_cls = class_map.get(rel["from"])
            to_cls = class_map.get(rel["to"])

            if from_cls and to_cls:
                from_type = getattr(from_cls, "__cfg_type__", "other") or "other"
                to_type = getattr(to_cls, "__cfg_type__", "other") or "other"

                # If the two classes belong to the same type, add the relationship to
                # that type
                if from_type == to_type:
                    if from_type not in type_relationships:
                        type_relationships[from_type] = []
                    type_relationships[from_type].append(rel)

        # Write the overview document
        with open(overview_path, "w", encoding="utf-8") as f:
            f.write("---\n")
            f.write('title: "Configuration Overview"\n')
            f.write("---\n\n")

            f.write("# Configuration Overview\n\n")
            f.write(
                "This document provides an overview of all configuration classes "
                "organized by type.\n\n"
            )

            # Create a table of contents with links to each type
            f.write("## Configuration Types\n\n")

            for cfg_type, classes in sorted(type_groups.items()):
                f.write(
                    f"- [{cfg_type}](#type-{cfg_type.lower().replace(' ', '-')}) ({len(classes)} classes)\n"  # noqa
                )

            f.write("\n## Type Details\n\n")

            # Create a section for each type
            for cfg_type, classes in sorted(type_groups.items()):
                if cfg_type != "other":
                    index_path = output_dir / f"{cfg_type}/index.mdx"
                    with open(index_path, "w", encoding="utf-8") as f_index:
                        f_index.write("---\n")
                        f_index.write(f'title: "{cfg_type}"\n')
                        f_index.write(f'description: "{cfg_type} Configuration"\n')
                        f_index.write("---\n\n")
                        f_index.write(
                            f"# {cfg_type} Configuration\n\n"
                            f"This document provides an overview of all configuration classes in {cfg_type} type.\n\n"  # noqa
                        )

                        # Use custom component to render the config class table
                        f_index.write(
                            "import { ConfigClassTable } from '@site/src/components/mdx/ConfigClassTable';\n\n"  # noqa
                        )  # noqa

                        # Write the config class table component
                        f_index.write("## Configuration Classes\n\n")
                        f_index.write("<ConfigClassTable classes={[\n")

                        # Write the config class table component
                        for cls in sorted(classes, key=lambda x: x.__name__):
                            cls_name = cls.__name__
                            cfg_desc = getattr(cls, "__cfg_desc__", "") or ""
                            cfg_desc = self.get_desc_for_class(cls, cfg_desc)

                            doc_id = self.get_class_doc_id(cls)
                            # doc_link = self.get_abs_link(cls, doc_id)
                            doc_link = self.generate_safe_filename(doc_id)
                            f_index.write("  {\n")
                            f_index.write(f'    "name": "{cls_name}",\n')
                            f_index.write(
                                f'    "description": {json.dumps(cfg_desc)},\n'
                            )  # noqa
                            if doc_link:
                                f_index.write(f'    "link": "./{doc_link[:-4]}"\n')
                            else:
                                f_index.write('    "link": ""\n')
                            f_index.write("  },\n")

                        f_index.write("]} />\n\n")

                # Create an anchor by replacing spaces with dashes
                anchor = f"type-{cfg_type.lower().replace(' ', '-')}"
                f.write(f"### {cfg_type} {{#{anchor}}}\n\n")

                # Show the number of classes in this type
                f.write(f"This type contains {len(classes)} configuration classes.\n\n")

                # Obtain relationships for this type
                type_rels = type_relationships.get(cfg_type, [])

                # If the number of relationships is moderate, draw a relationship
                # diagram
                if 1 <= len(type_rels) <= 30:
                    f.write("#### Relationships\n\n")
                    f.write("```mermaid\ngraph TD\n")

                    for rel in type_rels:
                        f.write(f"    {rel['from']} -->|{rel['label']}| {rel['to']}\n")

                    f.write("```\n\n")
                elif len(type_rels) > 30:
                    # If there are too many relationships, add a note
                    f.write(
                        f"This type has {len(type_rels)} relationships, which is too many to display in a single diagram.\n\n"  # noqa
                    )

                # List all classes and their links
                f.write("#### Configuration Classes\n\n")
                f.write("| Class | Description |\n")
                f.write("|-------|-------------|\n")

                for cls in sorted(classes, key=lambda x: x.__name__):
                    cls_name = cls.__name__
                    cfg_desc = getattr(cls, "__cfg_desc__", "")
                    # cfg_desc = self.get_desc_for_class(cls, cfg_desc)
                    # cfg_desc = cfg_desc.replace("`", "'")
                    doc_id = self.get_class_doc_id(cls)
                    if doc_id in self.link_cache:
                        # Use relative links based on the config type
                        if cfg_type != "other":
                            link_url = (
                                f"{cfg_type}/{self.generate_safe_filename(doc_id)[:-4]}"
                            )
                        else:
                            link_url = f"{self.generate_safe_filename(doc_id)[:-4]}"
                        f.write(f"| [{cls_name}]({link_url}) | {cfg_desc} |\n")
                    else:
                        f.write(f"| {cls_name} | {cfg_desc} |\n")

                f.write("\n---\n\n")  # Split sections

            # Add cross-type relationships
            f.write("## Cross-Type Relationships\n\n")
            f.write(
                "The following diagram shows relationships between different configuration types:\n\n"  # noqa
            )

            # Create relationships between types
            type_to_type = {}
            for rel in relationships:
                from_cls = class_map.get(rel["from"])
                to_cls = class_map.get(rel["to"])

                if from_cls and to_cls:
                    from_type = getattr(from_cls, "__cfg_type__", "other") or "other"
                    to_type = getattr(to_cls, "__cfg_type__", "other") or "other"

                    if from_type != to_type:
                        key = f"{from_type}|{to_type}"
                        if key not in type_to_type:
                            type_to_type[key] = 0
                        type_to_type[key] += 1

            if type_to_type:
                f.write("```mermaid\ngraph TD\n")

                # Add nodes for each type
                for cfg_type in type_groups:
                    f.write(
                        f"    {cfg_type}[{cfg_type} - {len(type_groups[cfg_type])} classes]\n"  # noqa
                    )

                # Add relationships between types
                for key, count in type_to_type.items():
                    from_type, to_type = key.split("|")
                    f.write(f"    {from_type} -->|{count} connections| {to_type}\n")

                f.write("```\n\n")
            else:
                f.write("No cross-type relationships found.\n\n")

            # Add a search prompt
            f.write("## Looking for a specific configuration?\n\n")
            f.write("1. Use the search function in the documentation site\n")
            f.write("2. Browse the configuration types above\n")
            f.write(
                "3. Check the specific class documentation for detailed parameter information\n"  # noqa
            )


def generate_docs(config_classes: List[Type], output_path: str):
    """The entry point for generating documentation."""
    generator = MDXDocGenerator()
    output_dir = Path(output_path)
    backup_dir = None
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        backup_dir = Path("/tmp") / "dbgpt_tmp_backup"
        if backup_dir.exists():
            os.system(f"rm -rf {backup_dir}")
        # Backup the existing files, Move the existing files to the backup directory
        os.system(f"mv {output_dir} {backup_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    ConfigurationManager._description_cache = {}
    # Generate documentation for each class
    try:
        all_generated_files = []
        for cls in config_classes[:1]:
            # Just generate the first class for now
            generated_files = generator.generate_class_doc(cls, output_dir)
            all_generated_files.extend(generated_files)

        # Generate an overview
        generator.generate_overview(output_dir, config_classes)
    except Exception as e:
        logger.error(f"Error generating documentation: {e}")
        # Restore the backup
        if backup_dir:
            # Delete the output directory
            os.system(f"rm -rf {output_dir}")
            os.system(f"mv {backup_dir} {output_dir}")
        raise e

    return all_generated_files


def _get_all_subclasses(cls):
    all_subclasses = []
    direct_subclasses = cls.__subclasses__()
    all_subclasses.extend(direct_subclasses)
    for subclass in direct_subclasses:
        all_subclasses.extend(_get_all_subclasses(subclass))

    return all_subclasses


if __name__ == "__main__":
    import os
    import sys

    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    from dbgpt.configs.model_config import ROOT_PATH
    from dbgpt_app.config import ApplicationConfig
    from dbgpt_app.dbgpt_server import scan_configs

    output_path = os.path.join(ROOT_PATH, "docs", "docs", "config-reference")

    scan_configs()

    config_classes = [ApplicationConfig]
    for subclass in _get_all_subclasses(RegisterParameters):
        config_classes.append(subclass)
    logger.info(f"Generating docs for {len(config_classes)} classes")
    logger.info(f"Generated for classes: {config_classes}")

    generate_docs(config_classes, output_path=output_path)

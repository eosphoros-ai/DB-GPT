import hashlib
import json
import logging
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Type

from dbgpt.util.configure.manager import ConfigurationManager
from dbgpt.util.module_utils import import_from_string
from dbgpt.util.parameter_utils import ParameterDescription

logger = logging.getLogger(__name__)


class MDXDocGenerator:
    def __init__(self):
        self.processed_classes: Set[str] = set()
        self.link_cache: Dict[str, str] = {}  # {class_path: filename}
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
        self, nested_fields: Dict[str, List[ParameterDescription]], output_dir: Path
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

                filename = self.generate_safe_filename(doc_id)
                # Remove ".mdx" suffix
                link_url = f"./{filename[:-4]}"
                links.append(
                    {
                        "type": "link",
                        "text": f"{type_name} configuration",
                        "url": f"./{link_url}",
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

    def generate_class_doc(self, cls: Type, output_dir: Path) -> List[str]:
        """Generate documentation for a configuration class."""
        # if _is_base_config(cls):
        #     return
        doc_id = self.get_class_doc_id(cls)
        if doc_id in self.processed_classes:
            return []

        self.processed_classes.add(doc_id)
        generated_files = []

        descriptions = ConfigurationManager.parse_description(cls)
        filename = self.generate_safe_filename(doc_id)
        output_path = output_dir / filename
        generated_files.append(filename)

        cls_label, cls_desc, cls_doc_url = self._parse_class_doc(cls)

        with open(output_path, "w", encoding="utf-8") as f:
            # Add frontmatter to set the page title
            f.write("---\n")
            f.write(f'title: "{cls_label} Configuration"\n')
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
                descriptions, key=lambda x: x.param_order or float("inf")
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
                        param.nested_fields, output_dir
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

    def generate_overview(self, output_dir: Path, config_classes: List[Type]):
        """Generate an overview document for all configuration classes."""
        overview_path = output_dir / "overview.mdx"

        with open(overview_path, "w", encoding="utf-8") as f:
            _config_diagram = '"@site/src/components/mdx/ConfigDiagram";\n\n'
            f.write("import { ConfigDiagram } from " + _config_diagram)
            f.write("# Configuration Overview\n\n")
            f.write("## The layout of configuration classes\n\n")

            # Collect all relationships between classes
            relationships = []
            processed = set()

            for cls in config_classes:
                self._collect_relationships(cls, processed, relationships)

            f.write("<ConfigDiagram relationships={")
            f.write(json.dumps(relationships, indent=2, ensure_ascii=False))
            f.write("} />")

    def _collect_relationships(
        self, cls: Type, processed: Set[str], relationships: List[Dict]
    ):
        """Collect relationships between classes."""
        class_id = self.get_class_doc_id(cls)
        if class_id in processed:
            return
        processed.add(class_id)

        descriptions = ConfigurationManager.parse_description(cls)
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


def generate_docs(config_classes: List[Type], output_path: str):
    """The entry point for generating documentation."""
    generator = MDXDocGenerator()
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate documentation for each class
    all_generated_files = []
    for cls in config_classes:
        generated_files = generator.generate_class_doc(cls, output_dir)
        all_generated_files.extend(generated_files)

    # Generate an overview
    generator.generate_overview(output_dir, config_classes)

    return all_generated_files


if __name__ == "__main__":
    import os

    from dbgpt.configs.model_config import ROOT_PATH
    from dbgpt_app.config import ApplicationConfig
    from dbgpt_app.dbgpt_server import scan_configs

    scan_configs()

    output_path = os.path.join(ROOT_PATH, "docs", "docs", "config-reference")

    generate_docs(config_classes=[ApplicationConfig], output_path=output_path)

import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, cast

import schedule
import tomlkit

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field, model_validator
from dbgpt.component import BaseComponent, SystemApp
from dbgpt.core.awel import DAG
from dbgpt.core.awel.flow.flow_factory import FlowPanel
from dbgpt.util.dbgpts.base import (
    DBGPTS_METADATA_FILE,
    INSTALL_DIR,
    INSTALL_METADATA_FILE,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


class BasePackage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = Field(..., description="The name of the package")
    label: str = Field(..., description="The label of the package")
    package_type: str = Field(..., description="The type of the package")
    version: str = Field(..., description="The version of the package")
    description: str = Field(..., description="The description of the package")
    path: str = Field(..., description="The path of the package")
    authors: List[str] = Field(
        default_factory=list, description="The authors of the package"
    )
    definition_type: str = Field(
        default="python", description="The type of the package"
    )
    definition_file: Optional[str] = Field(
        default=None, description="The definition " "file of the package"
    )
    root: str = Field(..., description="The root of the package")
    repo: str = Field(..., description="The repository of the package")
    package: str = Field(..., description="The package name(like name in pypi)")

    @classmethod
    def build_from(cls, values: Dict[str, Any], ext_dict: Dict[str, Any]):
        return cls(**values)

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-fill the definition_file"""
        if not isinstance(values, dict):
            return values
        import importlib.resources as pkg_resources

        name = values.get("name")
        root = values.get("root")
        if not name:
            raise ValueError("The name is required")
        if not root:
            raise ValueError("The root is required")
        if root not in sys.path:
            sys.path.append(root)
        with pkg_resources.path(name, "__init__.py") as path:
            # Read the file
            values["path"] = os.path.dirname(os.path.abspath(path))
        return values

    def abs_definition_file(self) -> str:
        return str(Path(self.path) / self.definition_file)

    @classmethod
    def load_module_class(
        cls,
        values: Dict[str, Any],
        expected_cls: Type[T],
        predicates: Optional[List[Callable[..., bool]]] = None,
    ) -> Tuple[List[Type[T]], List[Any], List[Any]]:
        import importlib.resources as pkg_resources

        from dbgpt.core.awel.dag.loader import _load_modules_from_file

        name = values.get("name")
        root = values.get("root")
        if not name:
            raise ValueError("The name is required")
        if not root:
            raise ValueError("The root is required")
        if root not in sys.path:
            sys.path.append(root)
        try:
            with pkg_resources.path(name, "__init__.py") as path:
                mods = _load_modules_from_file(str(path), name, show_log=False)
                all_cls = [_get_classes_from_module(m) for m in mods]
                all_predicate_results = []
                for m in mods:
                    all_predicate_results.extend(_get_from_module(m, predicates))
                module_cls = []
                for list_cls in all_cls:
                    for c in list_cls:
                        if issubclass(c, expected_cls):
                            module_cls.append(c)
                return module_cls, all_predicate_results, mods
        except Exception as e:
            logger.warning(f"load_module_class error!{str(e)}", e)
            raise e


class FlowPackage(BasePackage):
    package_type: str = "flow"

    @classmethod
    def build_from(
        cls, values: Dict[str, Any], ext_dict: Dict[str, Any]
    ) -> "FlowPackage":
        if values["definition_type"] == "json":
            return FlowJsonPackage.build_from(values, ext_dict)
        return FlowPythonPackage.build_from(values, ext_dict)


class FlowPythonPackage(FlowPackage):
    dag: DAG = Field(..., description="The DAG of the package")

    @classmethod
    def build_from(cls, values: Dict[str, Any], ext_dict: Dict[str, Any]):
        from dbgpt.core.awel.dag.loader import _process_modules

        _, _, mods = cls.load_module_class(values, DAG)

        dags = _process_modules(mods, show_log=False)
        if not dags:
            raise ValueError("No DAGs found in the package")
        if len(dags) > 1:
            raise ValueError("Only support one DAG in the package")
        values["dag"] = dags[0]
        return cls(**values)


class FlowJsonPackage(FlowPackage):
    @classmethod
    def build_from(cls, values: Dict[str, Any], ext_dict: Dict[str, Any]):
        if "json_config" not in ext_dict:
            raise ValueError("The json_config is required")
        if "file_path" not in ext_dict["json_config"]:
            raise ValueError("The file_path is required")
        values["definition_file"] = ext_dict["json_config"]["file_path"]
        return cls(**values)

    def read_definition_json(self) -> Dict[str, Any]:
        import json

        with open(self.abs_definition_file(), "r", encoding="utf-8") as f:
            return json.loads(f.read())


class OperatorPackage(BasePackage):
    package_type: str = "operator"

    operators: List[type] = Field(
        default_factory=list, description="The operators of the package"
    )

    @classmethod
    def build_from(cls, values: Dict[str, Any], ext_dict: Dict[str, Any]):
        from dbgpt.core.awel import BaseOperator

        values["operators"], _, _ = cls.load_module_class(values, BaseOperator)
        return cls(**values)


class AgentPackage(BasePackage):
    package_type: str = "agent"

    agents: List[type] = Field(
        default_factory=list, description="The agents of the package"
    )

    @classmethod
    def build_from(cls, values: Dict[str, Any], ext_dict: Dict[str, Any]):
        from dbgpt.agent import ConversableAgent

        values["agents"], _, _ = cls.load_module_class(values, ConversableAgent)
        return cls(**values)


class ResourcePackage(BasePackage):
    package_type: str = "resource"

    resources: List[type] = Field(
        default_factory=list, description="The resources of the package"
    )
    resource_instances: List[Any] = Field(
        default_factory=list, description="The resource instances of the package"
    )

    @classmethod
    def build_from(cls, values: Dict[str, Any], ext_dict: Dict[str, Any]):
        from dbgpt.agent.resource import Resource
        from dbgpt.agent.resource.tool.pack import _is_function_tool

        def _predicate(obj):
            if not obj:
                return False
            elif _is_function_tool(obj):
                return True
            elif isinstance(obj, Resource):
                return True
            elif isinstance(obj, type) and issubclass(obj, Resource):
                return True
            else:
                return False

        _, predicted_cls, _ = cls.load_module_class(values, Resource, [_predicate])
        resource_instances = []
        resources = []
        for o in predicted_cls:
            if _is_function_tool(o) or isinstance(o, Resource):
                resource_instances.append(o)
            elif isinstance(o, type) and issubclass(o, Resource):
                resources.append(o)
        values["resource_instances"] = resource_instances
        values["resources"] = resources
        return cls(**values)


class InstalledPackage(BaseModel):
    name: str = Field(..., description="The name of the package")
    repo: str = Field(..., description="The repository of the package")
    root: str = Field(..., description="The root of the package")
    package: str = Field(..., description="The package name(like name in pypi)")


def _get_classes_from_module(module):
    classes = [
        obj
        for name, obj in inspect.getmembers(module, inspect.isclass)
        if obj.__module__ == module.__name__
    ]
    return classes


def _get_from_module(module, predicates: Optional[List[str]] = None):
    if not predicates:
        return []
    results = []
    for predicate in predicates:
        for name, obj in inspect.getmembers(module, predicate):
            if obj.__module__ == module.__name__:
                results.append(obj)
    return results


def parse_package_metadata(package: InstalledPackage) -> BasePackage:
    with open(
        Path(package.root) / DBGPTS_METADATA_FILE, mode="r+", encoding="utf-8"
    ) as f:
        metadata = tomlkit.loads(f.read())
    ext_metadata = {}
    pkg_dict = {}
    for key, value in metadata.items():
        if key == "flow":
            pkg_dict = {k: v for k, v in value.items()}
            pkg_dict["package_type"] = "flow"
        elif key == "operator":
            pkg_dict = {k: v for k, v in value.items()}
            pkg_dict["package_type"] = "operator"
        elif key == "agent":
            pkg_dict = {k: v for k, v in value.items()}
            pkg_dict["package_type"] = "agent"
        elif key == "resource":
            pkg_dict = {k: v for k, v in value.items()}
            pkg_dict["package_type"] = "resource"
        else:
            ext_metadata[key] = value
    pkg_dict["root"] = package.root
    pkg_dict["repo"] = package.repo
    pkg_dict["package"] = package.package
    if pkg_dict["package_type"] == "flow":
        return FlowPackage.build_from(pkg_dict, ext_metadata)
    elif pkg_dict["package_type"] == "operator":
        return OperatorPackage.build_from(pkg_dict, ext_metadata)
    elif pkg_dict["package_type"] == "agent":
        return AgentPackage.build_from(pkg_dict, ext_metadata)
    elif pkg_dict["package_type"] == "resource":
        return ResourcePackage.build_from(pkg_dict, ext_metadata)
    else:
        raise ValueError(
            f"Unsupported package package_type: {pkg_dict['package_type']}"
        )


def _load_installed_package(path: str) -> List[InstalledPackage]:
    packages = []
    for package in os.listdir(path):
        full_path = Path(path) / package
        install_metadata_file = full_path / INSTALL_METADATA_FILE
        dbgpts_metadata_file = full_path / DBGPTS_METADATA_FILE
        if (
            full_path.is_dir()
            and install_metadata_file.exists()
            and dbgpts_metadata_file.exists()
        ):
            with open(install_metadata_file) as f:
                metadata = tomlkit.loads(f.read())
                name = metadata["name"]
                repo = metadata["repo"]
                packages.append(
                    InstalledPackage(
                        name=name, repo=repo, root=str(full_path), package=package
                    )
                )
    return packages


def _load_package_from_path(path: str):
    """Load the package from the specified path"""
    packages = _load_installed_package(path)
    parsed_packages = []
    for package in packages:
        try:
            parsed_packages.append(parse_package_metadata(package))
        except Exception as e:
            logger.warning(f"Load package failed!{str(e)}", e)

    return parsed_packages


def _load_flow_package_from_path(
    name: str, path: str = INSTALL_DIR, filter_by_name: bool = True
) -> FlowPackage:
    raw_packages = _load_installed_package(path)
    new_name = name.replace("_", "-")
    if filter_by_name:
        packages = [p for p in raw_packages if p.package == name or p.name == name]
        if not packages:
            packages = [
                p for p in raw_packages if p.package == new_name or p.name == new_name
            ]
    else:
        packages = raw_packages
    if not packages:
        raise ValueError(f"Can't find the package {name} or {new_name}")
    flow_package = parse_package_metadata(packages[0])
    if flow_package.package_type != "flow":
        raise ValueError(f"Unsupported package type: {flow_package.package_type}")
    return cast(FlowPackage, flow_package)


def _load_flow_package_from_zip_path(zip_path: str) -> FlowPanel:
    import tempfile
    import zipfile

    with tempfile.TemporaryDirectory() as temp_dir:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
        package_names = os.listdir(temp_dir)
        if not package_names:
            raise ValueError("No package found in the zip file")
        if len(package_names) > 1:
            raise ValueError("Only support one package in the zip file")
        package_name = package_names[0]
        with open(
            Path(temp_dir) / package_name / INSTALL_METADATA_FILE, mode="w+"
        ) as f:
            # Write the metadata
            import tomlkit

            install_metadata = {
                "name": package_name,
                "repo": "local/dbgpts",
            }
            tomlkit.dump(install_metadata, f)

        package = _load_flow_package_from_path("", path=temp_dir, filter_by_name=False)
        return _flow_package_to_flow_panel(package)


def _flow_package_to_flow_panel(package: FlowPackage) -> FlowPanel:
    dict_value = {
        "name": package.name,
        "label": package.label,
        "version": package.version,
        "editable": False,
        "description": package.description,
        "source": package.repo,
        "define_type": "json",
        "authors": package.authors,
    }
    if isinstance(package, FlowJsonPackage):
        dict_value["flow_data"] = package.read_definition_json()
    elif isinstance(package, FlowPythonPackage):
        dict_value["flow_data"] = {
            "nodes": [],
            "edges": [],
            "viewport": {
                "x": 213,
                "y": 269,
                "zoom": 0,
            },
        }
        dict_value["flow_dag"] = package.dag
        dict_value["define_type"] = "python"
    else:
        raise ValueError(f"Unsupported package type: {package}")
    return FlowPanel(**dict_value)


class DBGPTsLoader(BaseComponent):
    """The loader of the dbgpts packages"""

    name: str = "dbgpt_dbgpts_loader"

    def __init__(
        self,
        system_app: Optional[SystemApp] = None,
        install_dir: Optional[str] = None,
        load_dbgpts_interval: int = 10,
    ):
        """Initialize the DBGPTsLoader."""
        self._system_app = None
        self._install_dir = install_dir or INSTALL_DIR
        self._packages: Dict[str, BasePackage] = {}
        self._load_dbgpts_interval = load_dbgpts_interval
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp):
        """Initialize the DBGPTsLoader."""
        self._system_app = system_app

    def before_start(self):
        """Execute after the application starts."""
        self.load_package(is_first=True)

        schedule.every(self._load_dbgpts_interval).seconds.do(self.load_package)

    def load_package(self, is_first: bool = False) -> None:
        """Load the package by name."""
        try:
            packages = _load_package_from_path(self._install_dir)
            if is_first:
                logger.info(
                    f"Found {len(packages)} dbgpts packages from {self._install_dir}"
                )
            for package in packages:
                self._packages[package.name] = package
                self._register_packages(package)
        except Exception as e:
            logger.warning(f"Load dbgpts package error: {e}", e)

    def get_flow_package(self, flow_name: str) -> Optional[BasePackage]:
        try:
            packages = _load_package_from_path(self._install_dir)
            for package in packages:
                if package.name == flow_name:
                    return package
            return None
        except Exception as e:
            logger.warning(f"Get flow package error: {str(e)}", e)
            return None

    def get_flows(self) -> List[FlowPanel]:
        """Get the flows.

        Returns:
            List[FlowPanel]: The list of the flows
        """
        panels = []
        for package in self._packages.values():
            if package.package_type != "flow":
                continue
            package = cast(FlowPackage, package)
            flow_panel = _flow_package_to_flow_panel(package)
            panels.append(flow_panel)
        return panels

    def _register_packages(self, package: BasePackage):
        if package.package_type == "agent":
            from dbgpt.agent import ConversableAgent, get_agent_manager

            agent_manager = get_agent_manager(self._system_app)
            pkg = cast(AgentPackage, package)
            for agent_cls in pkg.agents:
                if issubclass(agent_cls, ConversableAgent):
                    try:
                        agent_manager.register_agent(agent_cls, ignore_duplicate=True)
                    except ValueError as e:
                        logger.warning(f"Register agent {agent_cls} error: {e}")
        elif package.package_type == "resource":
            from dbgpt.agent.resource import Resource
            from dbgpt.agent.resource.manage import get_resource_manager

            pkg = cast(ResourcePackage, package)
            rm = get_resource_manager(self._system_app)
            for inst in pkg.resource_instances:
                try:
                    rm.register_resource(resource_instance=inst, ignore_duplicate=True)
                except ValueError as e:
                    logger.warning(f"Register resource {inst} error: {e}")
            for res in pkg.resources:
                try:
                    if issubclass(res, Resource):
                        rm.register_resource(res, ignore_duplicate=True)
                except ValueError as e:
                    logger.warning(f"Register resource {res} error: {e}")

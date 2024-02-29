import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import schedule
import tomlkit

from dbgpt._private.pydantic import BaseModel, Field, root_validator
from dbgpt.component import BaseComponent, SystemApp
from dbgpt.core.awel.flow.flow_factory import FlowPanel
from dbgpt.util.dbgpts.base import (
    DBGPTS_METADATA_FILE,
    INSTALL_DIR,
    INSTALL_METADATA_FILE,
)

logger = logging.getLogger(__name__)


class BasePackage(BaseModel):
    class Config:
        arbitrary_types_allowed = True

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

    @classmethod
    def build_from(cls, values: Dict[str, Any], ext_dict: Dict[str, Any]):
        return cls(**values)

    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-fill the definition_file"""
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


class FlowPackage(BasePackage):
    package_type = "flow"

    @classmethod
    def build_from(
        cls, values: Dict[str, Any], ext_dict: Dict[str, Any]
    ) -> "FlowPackage":
        if values["definition_type"] == "json":
            return FlowJsonPackage.build_from(values, ext_dict)
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
    package_type = "operator"

    operators: List[type] = Field(
        default_factory=list, description="The operators of the package"
    )

    @classmethod
    def build_from(cls, values: Dict[str, Any], ext_dict: Dict[str, Any]):
        import importlib.resources as pkg_resources

        from dbgpt.core.awel import BaseOperator
        from dbgpt.core.awel.dag.loader import _load_modules_from_file

        name = values.get("name")
        root = values.get("root")
        if root not in sys.path:
            sys.path.append(root)
        with pkg_resources.path(name, "__init__.py") as path:
            mods = _load_modules_from_file(str(path), name, show_log=False)
            all_cls = [_get_classes_from_module(m) for m in mods]
            operators = []
            for list_cls in all_cls:
                for c in list_cls:
                    if issubclass(c, BaseOperator):
                        operators.append(c)
            values["operators"] = operators
        return cls(**values)


class InstalledPackage(BaseModel):
    name: str = Field(..., description="The name of the package")
    repo: str = Field(..., description="The repository of the package")
    root: str = Field(..., description="The root of the package")


def _get_classes_from_module(module):
    classes = [
        obj
        for name, obj in inspect.getmembers(module, inspect.isclass)
        if obj.__module__ == module.__name__
    ]
    return classes


def _parse_package_metadata(package: InstalledPackage) -> BasePackage:
    with open(
        Path(package.root) / DBGPTS_METADATA_FILE, mode="r+", encoding="utf-8"
    ) as f:
        metadata = tomlkit.loads(f.read())
    ext_metadata = {}
    pkg_dict = {}
    for key, value in metadata.items():
        if key == "flow":
            pkg_dict = value
            pkg_dict["package_type"] = "flow"
        elif key == "operator":
            pkg_dict = {k: v for k, v in value.items()}
            pkg_dict["package_type"] = "operator"
        else:
            ext_metadata[key] = value
    pkg_dict["root"] = package.root
    pkg_dict["repo"] = package.repo
    if pkg_dict["package_type"] == "flow":
        return FlowPackage.build_from(pkg_dict, ext_metadata)
    elif pkg_dict["package_type"] == "operator":
        return OperatorPackage.build_from(pkg_dict, ext_metadata)
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
                    InstalledPackage(name=name, repo=repo, root=str(full_path))
                )
    return packages


def _load_package_from_path(path: str):
    """Load the package from the specified path"""
    packages = _load_installed_package(path)
    parsed_packages = []
    for package in packages:
        parsed_packages.append(_parse_package_metadata(package))
    return parsed_packages


class DBGPTsLoader(BaseComponent):
    """The loader of the dbgpts packages"""

    name = "dbgpt_dbgpts_loader"

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
        except Exception as e:
            logger.warning(f"Load dbgpts package error: {e}")

    def get_flows(self) -> List[FlowPanel]:
        """Get the flows.

        Returns:
            List[FlowPanel]: The list of the flows
        """
        panels = []
        for package in self._packages.values():
            if package.package_type != "flow":
                continue
            package = cast(FlowJsonPackage, package)
            dict_value = {
                "name": package.name,
                "label": package.label,
                "version": package.version,
                "editable": False,
                "description": package.description,
                "source": package.repo,
                "flow_data": package.read_definition_json(),
            }
            panels.append(FlowPanel(**dict_value))
        return panels

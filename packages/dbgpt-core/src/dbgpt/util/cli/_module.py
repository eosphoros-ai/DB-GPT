from typing import List, Optional, cast

from dbgpt.core.awel import BaseOperator
from dbgpt.core.awel.flow import (
    OperatorCategory,
    ResourceCategory,
    ResourceMetadata,
    ViewMetadata,
)
from dbgpt.core.awel.flow.compat import FlowCompatMetadata
from dbgpt.util.module_utils import ModelScanner, ScannerConfig


def _is_flow_operator(cls):
    return (
        issubclass(cls, BaseOperator)
        and hasattr(cls, "metadata")
        and isinstance(cls.metadata, ViewMetadata)
    )


def _is_flow_resource(cls):
    metadata_name = f"_resource_metadata_{cls.__name__}"
    metadata = getattr(cls, metadata_name, None)
    return metadata is not None and isinstance(metadata, ResourceMetadata)


def _scan_awel_flow(modules: Optional[List[str]] = None):
    scanner = ModelScanner[object]()
    if not modules:
        modules = ["dbgpt", "dbgpt_client", "dbgpt_ext", "dbgpt_serve", "dbgpt_app"]
    for module in modules:
        config = ScannerConfig(
            module_path=module,
            base_class=object,
            recursive=True,
            class_filter=lambda cls: _is_flow_operator(cls) or _is_flow_resource(cls),
            skip_files=["test_*.py", "*_test.py"],
        )
        scanner.scan_and_register(config)
    flow_cls = scanner.get_registered_items()
    compat_metadata = []
    for cls_name, cls in flow_cls.items():
        if _is_flow_operator(cls):
            metadata = cast(ViewMetadata, cls.metadata)
        else:
            metadata_name = f"_resource_metadata_{cls.__name__}"
            metadata = getattr(cls, metadata_name)
        parameters = []
        outputs = []
        inputs = []
        for param in metadata.parameters:
            parameters.append(param.name)
        if isinstance(metadata, ViewMetadata):
            for output in metadata.outputs:
                outputs.append(output.name)
            for input in metadata.inputs:
                inputs.append(input.name)
        category = metadata.category
        if isinstance(category, (OperatorCategory, ResourceCategory)):
            category = category.value

        compat_metadata.append(
            FlowCompatMetadata(
                type="operator" if _is_flow_operator(cls) else "resource",
                type_cls=metadata.type_cls,
                type_name=metadata.type_name,
                name=metadata.name,
                id=metadata.id,
                category=category,
                parameters=parameters,
                outputs=outputs,
                inputs=inputs,
            )
        )
    return compat_metadata


if __name__ == "__main__":
    res = _scan_awel_flow()
    print(res)

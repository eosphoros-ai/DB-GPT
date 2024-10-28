"""UI components for AWEL flow."""

from typing import Any, Dict, List, Literal, Optional, Union

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict, model_validator
from dbgpt.core.interface.serialization import Serializable

from .exceptions import FlowUIComponentException

_UI_TYPE = Literal[
    "select",
    "cascader",
    "checkbox",
    "radio",
    "date_picker",
    "input",
    "text_area",
    "auto_complete",
    "slider",
    "time_picker",
    "tree_select",
    "upload",
    "variables",
    "password",
    "code_editor",
]

_UI_SIZE_TYPE = Literal["large", "middle", "small"]
_SIZE_ORDER = {"large": 6, "middle": 4, "small": 2}


def _size_to_order(size: str) -> int:
    """Convert size to order."""
    if size not in _SIZE_ORDER:
        return -1
    return _SIZE_ORDER[size]


class RefreshableMixin(BaseModel):
    """Refreshable mixin."""

    refresh: Optional[bool] = Field(
        False,
        description="Whether to enable the refresh",
    )
    refresh_depends: Optional[List[str]] = Field(
        None,
        description="The dependencies of the refresh",
    )


class StatusMixin(BaseModel):
    """Status mixin."""

    status: Optional[Literal["error", "warning"]] = Field(
        None,
        description="Status of the input",
    )


class PanelEditorMixin(BaseModel):
    """Edit the content in the panel."""

    class Editor(BaseModel):
        """Editor configuration."""

        width: Optional[int] = Field(
            None,
            description="The width of the panel",
        )
        height: Optional[int] = Field(
            None,
            description="The height of the panel",
        )

    editor: Optional[Editor] = Field(
        default_factory=lambda: PanelEditorMixin.Editor(width=800, height=400),
        description="The editor configuration",
    )


class UIComponent(RefreshableMixin, Serializable, BaseModel):
    """UI component."""

    class UIAttribute(BaseModel):
        """Base UI attribute."""

        disabled: bool = Field(
            False,
            description="Whether the component is disabled",
        )

    ui_type: _UI_TYPE = Field(..., description="UI component type")
    size: Optional[_UI_SIZE_TYPE] = Field(
        None,
        description="The size of the component(small, middle, large)",
    )

    attr: Optional[UIAttribute] = Field(
        None,
        description="The attributes of the component",
    )

    def check_parameter(self, parameter_dict: Dict[str, Any]):
        """Check parameter.

        Raises:
            FlowUIParameterException: If the parameter is invalid.
        """

    def _check_options(self, options: Dict[str, Any]):
        """Check options."""
        if not options:
            raise FlowUIComponentException("options is required", self.ui_type)

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        return model_to_dict(self)


class UISelect(UIComponent):
    """Select component."""

    class UIAttribute(StatusMixin, UIComponent.UIAttribute):
        """Select attribute."""

        show_search: bool = Field(
            False,
            description="Whether to show search input",
        )
        mode: Optional[Literal["tags"]] = Field(
            None,
            description="The mode of the select",
        )
        placement: Optional[
            Literal["topLeft", "topRight", "bottomLeft", "bottomRight"]
        ] = Field(
            None,
            description="The position of the picker panel, None means bottomLeft",
        )

    ui_type: Literal["select"] = Field("select", frozen=True)
    attr: Optional[UIAttribute] = Field(
        None,
        description="The attributes of the component",
    )

    def check_parameter(self, parameter_dict: Dict[str, Any]):
        """Check parameter."""
        self._check_options(parameter_dict.get("options", {}))


class UICascader(UIComponent):
    """Cascader component."""

    class UIAttribute(StatusMixin, UIComponent.UIAttribute):
        """Cascader attribute."""

        show_search: bool = Field(
            False,
            description="Whether to show search input",
        )

    ui_type: Literal["cascader"] = Field("cascader", frozen=True)

    attr: Optional[UIAttribute] = Field(
        None,
        description="The attributes of the component",
    )

    def check_parameter(self, parameter_dict: Dict[str, Any]):
        """Check parameter."""
        options = parameter_dict.get("options")
        if not options:
            raise FlowUIComponentException("options is required", self.ui_type)
        first_level = options[0]
        if "children" not in first_level:
            raise FlowUIComponentException(
                "children is required in options", self.ui_type
            )


class UICheckbox(UIComponent):
    """Checkbox component."""

    ui_type: Literal["checkbox"] = Field("checkbox", frozen=True)

    def check_parameter(self, parameter_dict: Dict[str, Any]):
        """Check parameter."""
        self._check_options(parameter_dict.get("options", {}))


class UIRadio(UICheckbox):
    """Radio component."""

    ui_type: Literal["radio"] = Field("radio", frozen=True)  # type: ignore


class UIDatePicker(UIComponent):
    """Date picker component."""

    class UIAttribute(StatusMixin, UIComponent.UIAttribute):
        """Date picker attribute."""

        placement: Optional[
            Literal["topLeft", "topRight", "bottomLeft", "bottomRight"]
        ] = Field(
            None,
            description="The position of the picker panel, None means bottomLeft",
        )

    ui_type: Literal["date_picker"] = Field("date_picker", frozen=True)

    attr: Optional[UIAttribute] = Field(
        None,
        description="The attributes of the component",
    )


class UIInput(UIComponent):
    """Input component."""

    class UIAttribute(StatusMixin, UIComponent.UIAttribute):
        """Input attribute."""

        prefix: Optional[str] = Field(
            None,
            description="The prefix, icon or text",
            examples=["$", "icon:UserOutlined"],
        )
        suffix: Optional[str] = Field(
            None,
            description="The suffix, icon or text",
            examples=["$", "icon:SearchOutlined"],
        )
        show_count: Optional[bool] = Field(
            None,
            description="Whether to show count",
        )
        max_length: Optional[int] = Field(
            None,
            description="The maximum length of the input",
        )

    ui_type: Literal["input"] = Field("input", frozen=True)

    attr: Optional[UIAttribute] = Field(
        None,
        description="The attributes of the component",
    )


class UITextArea(PanelEditorMixin, UIInput):
    """Text area component."""

    class UIAttribute(UIInput.UIAttribute):
        """Text area attribute."""

        class AutoSize(BaseModel):
            """Auto size configuration."""

            min_rows: Optional[int] = Field(
                None,
                description="The minimum number of rows",
            )
            max_rows: Optional[int] = Field(
                None,
                description="The maximum number of rows",
            )

        auto_size: Optional[Union[bool, AutoSize]] = Field(
            None,
            description="Whether the height of the textarea automatically adjusts "
            "based on the content",
        )

    ui_type: Literal["text_area"] = Field("text_area", frozen=True)  # type: ignore
    attr: Optional[UIAttribute] = Field(
        None,
        description="The attributes of the component",
    )

    @model_validator(mode="after")
    def check_size(self) -> "UITextArea":
        """Check the size.

        Automatically set the size to large if the max_rows is greater than 10.
        """
        attr = self.attr
        auto_size = attr.auto_size if attr else None
        if not attr or not auto_size or isinstance(auto_size, bool):
            return self
        max_rows = (
            auto_size.max_rows
            if isinstance(auto_size, self.UIAttribute.AutoSize)
            else None
        )
        size = self.size
        if not size and max_rows and max_rows > 10:
            # Automatically set the size to large if the max_rows is greater than 10
            self.size = "large"
        return self


class UIAutoComplete(UIInput):
    """Auto complete component."""

    ui_type: Literal["auto_complete"] = Field(  # type: ignore
        "auto_complete", frozen=True
    )


class UISlider(UIComponent):
    """Slider component."""

    class UIAttribute(UIComponent.UIAttribute):
        """Slider attribute."""

        min: Optional[int | float] = Field(
            None,
            description="The minimum value",
        )
        max: Optional[int | float] = Field(
            None,
            description="The maximum value",
        )
        step: Optional[int | float] = Field(
            None,
            description="The step of the slider",
        )

    ui_type: Literal["slider"] = Field("slider", frozen=True)

    show_input: bool = Field(
        False, description="Whether to display the value in a input component"
    )

    attr: Optional[UIAttribute] = Field(
        None,
        description="The attributes of the component",
    )


class UITimePicker(UIComponent):
    """Time picker component."""

    class UIAttribute(StatusMixin, UIComponent.UIAttribute):
        """Time picker attribute."""

        format: Optional[str] = Field(
            None,
            description="The format of the time",
            examples=["HH:mm:ss", "HH:mm"],
        )
        hour_step: Optional[int] = Field(
            None,
            description="The step of the hour input",
        )
        minute_step: Optional[int] = Field(
            None,
            description="The step of the minute input",
        )
        second_step: Optional[int] = Field(
            None,
            description="The step of the second input",
        )

    ui_type: Literal["time_picker"] = Field("time_picker", frozen=True)

    attr: Optional[UIAttribute] = Field(
        None,
        description="The attributes of the component",
    )


class UITreeSelect(UICascader):
    """Tree select component."""

    ui_type: Literal["tree_select"] = Field("tree_select", frozen=True)  # type: ignore

    def check_parameter(self, parameter_dict: Dict[str, Any]):
        """Check parameter."""
        options = parameter_dict.get("options")
        if not options:
            raise FlowUIComponentException("options is required", self.ui_type)
        first_level = options[0]
        if "children" not in first_level:
            raise FlowUIComponentException(
                "children is required in options", self.ui_type
            )


class UIUpload(UIComponent):
    """Upload component."""

    class UIAttribute(UIComponent.UIAttribute):
        """Upload attribute."""

        max_count: Optional[int] = Field(
            None,
            description="The maximum number of files that can be uploaded",
        )

    ui_type: Literal["upload"] = Field("upload", frozen=True)
    attr: Optional[UIAttribute] = Field(
        None,
        description="The attributes of the component",
    )
    max_file_size: Optional[int] = Field(
        None,
        description="The maximum size of the file, in bytes",
    )

    file_types: Optional[List[str]] = Field(
        None,
        description="The file types that can be accepted",
        examples=[[".png", ".jpg"]],
    )
    up_event: Optional[Literal["after_select", "button_click"]] = Field(
        None,
        description="The event that triggers the upload",
    )
    drag: bool = Field(
        False,
        description="Whether to support drag and drop upload",
    )
    action: Optional[str] = Field(
        "/api/v2/serve/file/files/dbgpt",
        description="The URL for the file upload(default bucket is 'dbgpt')",
    )


class UIVariablesInput(UIInput):
    """Variables input component."""

    ui_type: Literal["variable"] = Field("variables", frozen=True)  # type: ignore
    key: str = Field(..., description="The key of the variable")
    key_type: Literal["common", "secret"] = Field(
        "common",
        description="The type of the key",
    )
    scope: str = Field("global", description="The scope of the variables")
    scope_key: Optional[str] = Field(
        None,
        description="The key of the scope",
    )
    refresh: Optional[bool] = Field(
        True,
        description="Whether to enable the refresh",
    )

    def check_parameter(self, parameter_dict: Dict[str, Any]):
        """Check parameter."""
        self._check_options(parameter_dict.get("options", {}))


class UIPasswordInput(UIVariablesInput):
    """Password input component."""

    ui_type: Literal["password"] = Field("password", frozen=True)  # type: ignore

    key_type: Literal["secret"] = Field(
        "secret",
        description="The type of the key",
    )

    def check_parameter(self, parameter_dict: Dict[str, Any]):
        """Check parameter."""
        self._check_options(parameter_dict.get("options", {}))


class UICodeEditor(UITextArea):
    """Code editor component."""

    ui_type: Literal["code_editor"] = Field("code_editor", frozen=True)  # type: ignore

    language: Optional[str] = Field(
        "python",
        description="The language of the code",
    )


class DefaultUITextArea(UITextArea):
    """Default text area component."""

    attr: Optional[UITextArea.UIAttribute] = Field(
        default_factory=lambda: UITextArea.UIAttribute(
            auto_size=UITextArea.UIAttribute.AutoSize(min_rows=2, max_rows=20)
        ),
        description="The attributes of the component",
    )

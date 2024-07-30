"""UI components for AWEL flow."""

from typing import Any, Dict, List, Literal, Optional

from dbgpt._private.pydantic import BaseModel, Field

from .exceptions import FlowUIComponentException

_UI_TYPE = Literal[
    "cascader",
    "checkbox",
    "date_picker",
    "input",
    "text_area",
    "auto_complete",
    "slider",
    "time_picker",
    "tree_select",
    "upload",
    "variable",
    "password",
    "code_editor",
]


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


class UIComponent(RefreshableMixin, BaseModel):
    """UI component."""

    class UIRange(BaseModel):
        """UI range."""

        min: int | float | str | None = Field(None, description="Minimum value")
        max: int | float | str | None = Field(None, description="Maximum value")
        step: int | float | str | None = Field(None, description="Step value")
        format: str | None = Field(None, description="Format")

    ui_type: _UI_TYPE = Field(..., description="UI component type")

    disabled: bool = Field(
        False,
        description="Whether the component is disabled",
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


class StatusMixin(BaseModel):
    """Status mixin."""

    status: Optional[Literal["error", "warning"]] = Field(
        None,
        description="Status of the input",
    )


class RangeMixin(BaseModel):
    """Range mixin."""

    ui_range: Optional[UIComponent.UIRange] = Field(
        None,
        description="Range for the component",
    )


class InputMixin(BaseModel):
    """Input mixin."""

    class Count(BaseModel):
        """Count."""

        show: Optional[bool] = Field(
            None,
            description="Whether to show count",
        )
        max: Optional[int] = Field(
            None,
            description="The maximum count",
        )
        exceed_strategy: Optional[Literal["cut", "warning"]] = Field(
            None,
            description="The strategy when the count exceeds",
        )

    count: Optional[Count] = Field(
        None,
        description="Count configuration",
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
        None,
        description="The editor configuration",
    )


class UICascader(StatusMixin, UIComponent):
    """Cascader component."""

    ui_type: Literal["cascader"] = Field("cascader", frozen=True)

    show_search: bool = Field(
        False,
        description="Whether to show search input",
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


class UIDatePicker(StatusMixin, RangeMixin, UIComponent):
    """Date picker component."""

    ui_type: Literal["date_picker"] = Field("date_picker", frozen=True)

    placement: Optional[
        Literal["topLeft", "topRight", "bottomLeft", "bottomRight"]
    ] = Field(
        None,
        description="The position of the picker panel, None means bottomLeft",
    )


class UIInput(StatusMixin, InputMixin, UIComponent):
    """Input component."""

    ui_type: Literal["input"] = Field("input", frozen=True)

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


class UITextArea(PanelEditorMixin, UIInput):
    """Text area component."""

    ui_type: Literal["text_area"] = Field("text_area", frozen=True)  # type: ignore
    auto_size: Optional[bool] = Field(
        None,
        description="Whether the height of the textarea automatically adjusts based "
        "on the content",
    )
    min_rows: Optional[int] = Field(
        None,
        description="The minimum number of rows",
    )
    max_rows: Optional[int] = Field(
        None,
        description="The maximum number of rows",
    )


class UIAutoComplete(UIInput):
    """Auto complete component."""

    ui_type: Literal["auto_complete"] = Field(  # type: ignore
        "auto_complete", frozen=True
    )


class UISlider(RangeMixin, UIComponent):
    """Slider component."""

    ui_type: Literal["slider"] = Field("slider", frozen=True)

    show_input: bool = Field(
        False, description="Whether to display the value in a input component"
    )


class UITimePicker(StatusMixin, UIComponent):
    """Time picker component."""

    ui_type: Literal["time_picker"] = Field("time_picker", frozen=True)

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


class UITreeSelect(StatusMixin, UIComponent):
    """Tree select component."""

    ui_type: Literal["tree_select"] = Field("tree_select", frozen=True)

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


class UIUpload(StatusMixin, UIComponent):
    """Upload component."""

    ui_type: Literal["upload"] = Field("upload", frozen=True)

    max_file_size: Optional[int] = Field(
        None,
        description="The maximum size of the file, in bytes",
    )
    max_count: Optional[int] = Field(
        None,
        description="The maximum number of files that can be uploaded",
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
        None,
        description="The URL for the file upload",
    )


class UIVariableInput(UIInput):
    """Variable input component."""

    ui_type: Literal["variable"] = Field("variable", frozen=True)  # type: ignore
    key: str = Field(..., description="The key of the variable")
    key_type: Literal["common", "secret"] = Field(
        "common",
        description="The type of the key",
    )
    refresh: Optional[bool] = Field(
        True,
        description="Whether to enable the refresh",
    )

    def check_parameter(self, parameter_dict: Dict[str, Any]):
        """Check parameter."""
        self._check_options(parameter_dict.get("options", {}))


class UIPasswordInput(UIVariableInput):
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

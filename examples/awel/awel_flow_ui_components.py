"""Some UI components for the AWEL flow."""

import json
import logging
from typing import Any, Dict, List, Optional

from dbgpt.core.awel import JoinOperator, MapOperator
from dbgpt.core.awel.flow import (
    FunctionDynamicOptions,
    IOField,
    OperatorCategory,
    OptionValue,
    Parameter,
    VariablesDynamicOptions,
    ViewMetadata,
    ui,
)
from dbgpt.core.interface.file import FileStorageClient
from dbgpt.core.interface.variables import (
    BUILTIN_VARIABLES_CORE_EMBEDDINGS,
    BUILTIN_VARIABLES_CORE_FLOW_NODES,
    BUILTIN_VARIABLES_CORE_FLOWS,
    BUILTIN_VARIABLES_CORE_LLMS,
    BUILTIN_VARIABLES_CORE_SECRETS,
    BUILTIN_VARIABLES_CORE_VARIABLES,
)

logger = logging.getLogger(__name__)


class ExampleFlowSelectOperator(MapOperator[str, str]):
    """An example flow operator that includes a select as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Select",
        name="example_flow_select",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a select as parameter.",
        parameters=[
            Parameter.build_from(
                "Fruits Selector",
                "fruits",
                type=str,
                optional=True,
                default=None,
                placeholder="Select the fruits",
                description="The fruits you like.",
                options=[
                    OptionValue(label="Apple", name="apple", value="apple"),
                    OptionValue(label="Banana", name="banana", value="banana"),
                    OptionValue(label="Orange", name="orange", value="orange"),
                    OptionValue(label="Pear", name="pear", value="pear"),
                ],
                ui=ui.UISelect(attr=ui.UISelect.UIAttribute(show_search=True)),
            )
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Fruits",
                "fruits",
                str,
                description="User's favorite fruits.",
            )
        ],
    )

    def __init__(self, fruits: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.fruits = fruits

    async def map(self, user_name: str) -> str:
        """Map the user name to the fruits."""
        return "Your name is %s, and you like %s." % (user_name, self.fruits)


class ExampleFlowCascaderOperator(MapOperator[str, str]):
    """An example flow operator that includes a cascader as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Cascader",
        name="example_flow_cascader",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a cascader as parameter.",
        parameters=[
            Parameter.build_from(
                "Address Selector",
                "address",
                type=str,
                is_list=True,
                optional=True,
                default=None,
                placeholder="Select the address",
                description="The address of the location.",
                options=[
                    OptionValue(
                        label="Zhejiang",
                        name="zhejiang",
                        value="zhejiang",
                        children=[
                            OptionValue(
                                label="Hangzhou",
                                name="hangzhou",
                                value="hangzhou",
                                children=[
                                    OptionValue(
                                        label="Xihu",
                                        name="xihu",
                                        value="xihu",
                                    ),
                                    OptionValue(
                                        label="Feilaifeng",
                                        name="feilaifeng",
                                        value="feilaifeng",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    OptionValue(
                        label="Jiangsu",
                        name="jiangsu",
                        value="jiangsu",
                        children=[
                            OptionValue(
                                label="Nanjing",
                                name="nanjing",
                                value="nanjing",
                                children=[
                                    OptionValue(
                                        label="Zhonghua Gate",
                                        name="zhonghuamen",
                                        value="zhonghuamen",
                                    ),
                                    OptionValue(
                                        label="Zhongshanling",
                                        name="zhongshanling",
                                        value="zhongshanling",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
                ui=ui.UICascader(attr=ui.UICascader.UIAttribute(show_search=True)),
            )
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Address",
                "address",
                str,
                description="User's address.",
            )
        ],
    )

    def __int__(self, address: Optional[List[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.address = address or []

    async def map(self, user_name: str) -> str:
        """Map the user name to the address."""
        full_address_str = " ".join(self.address)
        return "Your name is %s, and your address is %s." % (
            user_name,
            full_address_str,
        )


class ExampleFlowCheckboxOperator(MapOperator[str, str]):
    """An example flow operator that includes a checkbox as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Checkbox",
        name="example_flow_checkbox",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a checkbox as parameter.",
        parameters=[
            Parameter.build_from(
                "Fruits Selector",
                "fruits",
                type=str,
                is_list=True,
                optional=True,
                default=None,
                placeholder="Select the fruits",
                description="The fruits you like.",
                options=[
                    OptionValue(label="Apple", name="apple", value="apple"),
                    OptionValue(label="Banana", name="banana", value="banana"),
                    OptionValue(label="Orange", name="orange", value="orange"),
                    OptionValue(label="Pear", name="pear", value="pear"),
                ],
                ui=ui.UICheckbox(),
            )
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Fruits",
                "fruits",
                str,
                description="User's favorite fruits.",
            )
        ],
    )

    def __init__(self, fruits: Optional[List[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.fruits = fruits or []

    async def map(self, user_name: str) -> str:
        """Map the user name to the fruits."""
        return "Your name is %s, and you like %s." % (user_name, ", ".join(self.fruits))


class ExampleFlowRadioOperator(MapOperator[str, str]):
    """An example flow operator that includes a radio as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Radio",
        name="example_flow_radio",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a radio as parameter.",
        parameters=[
            Parameter.build_from(
                "Fruits Selector",
                "fruits",
                type=str,
                optional=True,
                default=None,
                placeholder="Select the fruits",
                description="The fruits you like.",
                options=[
                    OptionValue(label="Apple", name="apple", value="apple"),
                    OptionValue(label="Banana", name="banana", value="banana"),
                    OptionValue(label="Orange", name="orange", value="orange"),
                    OptionValue(label="Pear", name="pear", value="pear"),
                ],
                ui=ui.UIRadio(),
            )
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Fruits",
                "fruits",
                str,
                description="User's favorite fruits.",
            )
        ],
    )

    def __init__(self, fruits: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.fruits = fruits

    async def map(self, user_name: str) -> str:
        """Map the user name to the fruits."""
        return "Your name is %s, and you like %s." % (user_name, self.fruits)


class ExampleFlowDatePickerOperator(MapOperator[str, str]):
    """An example flow operator that includes a date picker as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Date Picker",
        name="example_flow_date_picker",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a date picker as parameter.",
        parameters=[
            Parameter.build_from(
                "Date Selector",
                "date",
                type=str,
                placeholder="Select the date",
                description="The date you choose.",
                ui=ui.UIDatePicker(
                    attr=ui.UIDatePicker.UIAttribute(placement="bottomLeft")
                ),
            )
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Date",
                "date",
                str,
                description="User's selected date.",
            )
        ],
    )

    def __init__(self, date: str, **kwargs):
        super().__init__(**kwargs)
        self.date = date

    async def map(self, user_name: str) -> str:
        """Map the user name to the date."""
        return "Your name is %s, and you choose the date %s." % (user_name, self.date)


class ExampleFlowInputOperator(MapOperator[str, str]):
    """An example flow operator that includes an input as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Input",
        name="example_flow_input",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a input as parameter.",
        parameters=[
            Parameter.build_from(
                "Your hobby",
                "hobby",
                type=str,
                placeholder="Please input your hobby",
                description="The hobby you like.",
                ui=ui.UIInput(
                    attr=ui.UIInput.UIAttribute(
                        prefix="icon:UserOutlined", show_count=True, maxlength=200
                    )
                ),
            )
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "User Hobby",
                "hobby",
                str,
                description="User's hobby.",
            )
        ],
    )

    def __init__(self, hobby: str, **kwargs):
        super().__init__(**kwargs)
        self.hobby = hobby

    async def map(self, user_name: str) -> str:
        """Map the user name to the input."""
        return "Your name is %s, and your hobby is %s." % (user_name, self.hobby)


class ExampleFlowTextAreaOperator(MapOperator[str, str]):
    """An example flow operator that includes a text area as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Text Area",
        name="example_flow_text_area",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a text area as parameter.",
        parameters=[
            Parameter.build_from(
                "Your comment",
                "comment",
                type=str,
                placeholder="Please input your comment",
                description="The comment you want to say.",
                ui=ui.UITextArea(
                    attr=ui.UITextArea.UIAttribute(
                        show_count=True,
                        maxlength=1000,
                        auto_size=ui.UITextArea.UIAttribute.AutoSize(
                            min_rows=2, max_rows=6
                        ),
                    ),
                ),
            )
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "User Comment",
                "comment",
                str,
                description="User's comment.",
            )
        ],
    )

    def __init__(self, comment: str, **kwargs):
        super().__init__(**kwargs)
        self.comment = comment

    async def map(self, user_name: str) -> str:
        """Map the user name to the text area."""
        return "Your name is %s, and your comment is %s." % (user_name, self.comment)


class ExampleFlowSliderOperator(MapOperator[float, float]):
    metadata = ViewMetadata(
        label="Example Flow Slider",
        name="example_flow_slider",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a slider as parameter.",
        parameters=[
            Parameter.build_from(
                "Default Temperature",
                "default_temperature",
                type=float,
                optional=True,
                default=0.7,
                placeholder="Set the default temperature, e.g., 0.7",
                description="The default temperature to pass to the LLM.",
                ui=ui.UISlider(
                    show_input=True,
                    attr=ui.UISlider.UIAttribute(min=0.0, max=2.0, step=0.1),
                ),
            )
        ],
        inputs=[
            IOField.build_from(
                "Temperature",
                "temperature",
                float,
                description="The temperature.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Temperature",
                "temperature",
                float,
                description="The temperature to pass to the LLM.",
            )
        ],
    )

    def __init__(self, default_temperature: float = 0.7, **kwargs):
        super().__init__(**kwargs)
        self.default_temperature = default_temperature

    async def map(self, temperature: float) -> float:
        """Map the temperature to the result."""
        if temperature < 0.0 or temperature > 2.0:
            logger.warning("Temperature out of range: %s", temperature)
            return self.default_temperature
        else:
            return temperature


class ExampleFlowSliderListOperator(MapOperator[float, float]):
    """An example flow operator that includes a slider list as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Slider List",
        name="example_flow_slider_list",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a slider list as parameter.",
        parameters=[
            Parameter.build_from(
                "Temperature Selector",
                "temperature_range",
                type=float,
                is_list=True,
                optional=True,
                default=None,
                placeholder="Set the temperature, e.g., [0.1, 0.9]",
                description="The temperature range to pass to the LLM.",
                ui=ui.UISlider(
                    show_input=True,
                    attr=ui.UISlider.UIAttribute(min=0.0, max=2.0, step=0.1),
                ),
            )
        ],
        inputs=[
            IOField.build_from(
                "Temperature",
                "temperature",
                float,
                description="The temperature.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Temperature",
                "temperature",
                float,
                description="The temperature to pass to the LLM.",
            )
        ],
    )

    def __init__(self, temperature_range: Optional[List[float]] = None, **kwargs):
        super().__init__(**kwargs)
        temperature_range = temperature_range or [0.1, 0.9]
        if temperature_range and len(temperature_range) != 2:
            raise ValueError("The length of temperature range must be 2.")
        self.temperature_range = temperature_range

    async def map(self, temperature: float) -> float:
        """Map the temperature to the result."""
        min_temperature, max_temperature = self.temperature_range
        if temperature < min_temperature or temperature > max_temperature:
            logger.warning(
                "Temperature out of range: %s, min: %s, max: %s",
                temperature,
                min_temperature,
                max_temperature,
            )
            return min_temperature
        return temperature


class ExampleFlowTimePickerOperator(MapOperator[str, str]):
    """An example flow operator that includes a time picker as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Time Picker",
        name="example_flow_time_picker",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a time picker as parameter.",
        parameters=[
            Parameter.build_from(
                "Time Selector",
                "time",
                type=str,
                placeholder="Select the time",
                description="The time you choose.",
                ui=ui.UITimePicker(
                    attr=ui.UITimePicker.UIAttribute(
                        format="HH:mm:ss", hour_step=2, minute_step=10, second_step=10
                    ),
                ),
            )
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Time",
                "time",
                str,
                description="User's selected time.",
            )
        ],
    )

    def __init__(self, time: str, **kwargs):
        super().__init__(**kwargs)
        self.time = time

    async def map(self, user_name: str) -> str:
        """Map the user name to the time."""
        return "Your name is %s, and you choose the time %s." % (user_name, self.time)


class ExampleFlowTreeSelectOperator(MapOperator[str, str]):
    """An example flow operator that includes a tree select as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Tree Select",
        name="example_flow_tree_select",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a tree select as parameter.",
        parameters=[
            Parameter.build_from(
                "Address Selector",
                "address",
                type=str,
                is_list=True,
                optional=True,
                default=None,
                placeholder="Select the address",
                description="The address of the location.",
                options=[
                    OptionValue(
                        label="Zhejiang",
                        name="zhejiang",
                        value="zhejiang",
                        children=[
                            OptionValue(
                                label="Hangzhou",
                                name="hangzhou",
                                value="hangzhou",
                                children=[
                                    OptionValue(
                                        label="Xihu",
                                        name="xihu",
                                        value="xihu",
                                    ),
                                    OptionValue(
                                        label="Feilaifeng",
                                        name="feilaifeng",
                                        value="feilaifeng",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    OptionValue(
                        label="Jiangsu",
                        name="jiangsu",
                        value="jiangsu",
                        children=[
                            OptionValue(
                                label="Nanjing",
                                name="nanjing",
                                value="nanjing",
                                children=[
                                    OptionValue(
                                        label="Zhonghua Gate",
                                        name="zhonghuamen",
                                        value="zhonghuamen",
                                    ),
                                    OptionValue(
                                        label="Zhongshanling",
                                        name="zhongshanling",
                                        value="zhongshanling",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
                ui=ui.UITreeSelect(attr=ui.UITreeSelect.UIAttribute(show_search=True)),
            )
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Address",
                "address",
                str,
                description="User's address.",
            )
        ],
    )

    def __int__(self, address: Optional[List[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.address = address or []

    async def map(self, user_name: str) -> str:
        """Map the user name to the address."""
        full_address_str = " ".join(self.address)
        return "Your name is %s, and your address is %s." % (
            user_name,
            full_address_str,
        )


def get_recent_3_times(time_interval: int = 1) -> List[OptionValue]:
    """Get the recent times."""
    from datetime import datetime, timedelta

    now = datetime.now()
    recent_times = [now - timedelta(hours=time_interval * i) for i in range(3)]
    formatted_times = [time.strftime("%Y-%m-%d %H:%M:%S") for time in recent_times]
    option_values = [
        OptionValue(label=formatted_time, name=f"time_{i + 1}", value=formatted_time)
        for i, formatted_time in enumerate(formatted_times)
    ]

    return option_values


class ExampleFlowRefreshOperator(MapOperator[str, str]):
    """An example flow operator that includes a refresh option."""

    metadata = ViewMetadata(
        label="Example Refresh Operator",
        name="example_refresh_operator",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a refresh option.",
        parameters=[
            Parameter.build_from(
                "Time Interval",
                "time_interval",
                type=int,
                optional=True,
                default=1,
                placeholder="Set the time interval",
                description="The time interval to fetch the times",
            ),
            Parameter.build_from(
                "Recent Time",
                "recent_time",
                type=str,
                optional=True,
                default=None,
                placeholder="Select the recent time",
                description="The recent time to choose.",
                options=FunctionDynamicOptions(func=get_recent_3_times),
                ui=ui.UISelect(
                    refresh=True,
                    refresh_depends=["time_interval"],
                    attr=ui.UISelect.UIAttribute(show_search=True),
                ),
            ),
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Time",
                "time",
                str,
                description="User's selected time.",
            )
        ],
    )

    def __init__(
        self, time_interval: int = 1, recent_time: Optional[str] = None, **kwargs
    ):
        super().__init__(**kwargs)
        self.time_interval = time_interval
        self.recent_time = recent_time

    async def map(self, user_name: str) -> str:
        """Map the user name to the time."""
        return "Your name is %s, and you choose the time %s." % (
            user_name,
            self.recent_time,
        )


class ExampleFlowUploadOperator(MapOperator[str, str]):
    """An example flow operator that includes an upload as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Upload",
        name="example_flow_upload",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a upload as parameter.",
        parameters=[
            Parameter.build_from(
                "Single File Selector",
                "file",
                type=str,
                optional=True,
                default=None,
                placeholder="Select the file",
                description="The file you want to upload.",
                ui=ui.UIUpload(
                    max_file_size=1024 * 1024 * 100,
                    up_event="after_select",
                    attr=ui.UIUpload.UIAttribute(max_count=1),
                ),
            ),
            Parameter.build_from(
                "Multiple Files Selector",
                "multiple_files",
                type=str,
                is_list=True,
                optional=True,
                default=None,
                placeholder="Select the multiple files",
                description="The multiple files you want to upload.",
                ui=ui.UIUpload(
                    max_file_size=1024 * 1024 * 100,
                    up_event="button_click",
                    attr=ui.UIUpload.UIAttribute(max_count=5),
                ),
            ),
            Parameter.build_from(
                "CSV File Selector",
                "csv_file",
                type=str,
                optional=True,
                default=None,
                placeholder="Select the CSV file",
                description="The CSV file you want to upload.",
                ui=ui.UIUpload(
                    max_file_size=1024 * 1024 * 100,
                    up_event="after_select",
                    file_types=[".csv"],
                    attr=ui.UIUpload.UIAttribute(max_count=1),
                ),
            ),
            Parameter.build_from(
                "Images Selector",
                "images",
                type=str,
                is_list=True,
                optional=True,
                default=None,
                placeholder="Select the images",
                description="The images you want to upload.",
                ui=ui.UIUpload(
                    max_file_size=1024 * 1024 * 100,
                    up_event="button_click",
                    file_types=["image/*", ".pdf"],
                    drag=True,
                    attr=ui.UIUpload.UIAttribute(max_count=5),
                ),
            ),
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "File",
                "file",
                str,
                description="User's uploaded file.",
            )
        ],
    )

    def __init__(
        self,
        file: Optional[str] = None,
        multiple_files: Optional[List[str]] = None,
        csv_file: Optional[str] = None,
        images: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.file = file
        self.multiple_files = multiple_files or []
        self.csv_file = csv_file
        self.images = images or []

    async def map(self, user_name: str) -> str:
        """Map the user name to the file."""

        fsc = FileStorageClient.get_instance(self.system_app)
        files_metadata = await self.blocking_func_to_async(
            self._parse_files_metadata, fsc
        )
        files_metadata_str = json.dumps(files_metadata, ensure_ascii=False, indent=4)
        return "Your name is %s, and you files are %s." % (
            user_name,
            files_metadata_str,
        )

    def _parse_files_metadata(self, fsc: FileStorageClient) -> List[Dict[str, Any]]:
        """Parse the files metadata."""
        if not self.file:
            raise ValueError("The file is not uploaded.")
        if not self.multiple_files:
            raise ValueError("The multiple files are not uploaded.")
        files = [self.file] + self.multiple_files + [self.csv_file] + self.images
        results = []
        for file in files:
            _, metadata = fsc.get_file(file)
            results.append(
                {
                    "bucket": metadata.bucket,
                    "file_id": metadata.file_id,
                    "file_size": metadata.file_size,
                    "storage_type": metadata.storage_type,
                    "uri": metadata.uri,
                    "file_hash": metadata.file_hash,
                }
            )
        return results


class ExampleFlowVariablesOperator(MapOperator[str, str]):
    """An example flow operator that includes a variables option."""

    metadata = ViewMetadata(
        label="Example Variables Operator",
        name="example_variables_operator",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a variables option.",
        parameters=[
            Parameter.build_from(
                "OpenAI API Key",
                "openai_api_key",
                type=str,
                placeholder="Please select the OpenAI API key",
                description="The OpenAI API key to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIPasswordInput(
                    key="dbgpt.model.openai.api_key",
                ),
            ),
            Parameter.build_from(
                "Model",
                "model",
                type=str,
                placeholder="Please select the model",
                description="The model to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key="dbgpt.model.openai.model",
                ),
            ),
            Parameter.build_from(
                "Builtin Flows",
                "builtin_flow",
                type=str,
                placeholder="Please select the builtin flows",
                description="The builtin flows to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key=BUILTIN_VARIABLES_CORE_FLOWS,
                ),
            ),
            Parameter.build_from(
                "Builtin Flow Nodes",
                "builtin_flow_node",
                type=str,
                placeholder="Please select the builtin flow nodes",
                description="The builtin flow nodes to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key=BUILTIN_VARIABLES_CORE_FLOW_NODES,
                ),
            ),
            Parameter.build_from(
                "Builtin Variables",
                "builtin_variable",
                type=str,
                placeholder="Please select the builtin variables",
                description="The builtin variables to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key=BUILTIN_VARIABLES_CORE_VARIABLES,
                ),
            ),
            Parameter.build_from(
                "Builtin Secrets",
                "builtin_secret",
                type=str,
                placeholder="Please select the builtin secrets",
                description="The builtin secrets to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key=BUILTIN_VARIABLES_CORE_SECRETS,
                ),
            ),
            Parameter.build_from(
                "Builtin LLMs",
                "builtin_llm",
                type=str,
                placeholder="Please select the builtin LLMs",
                description="The builtin LLMs to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key=BUILTIN_VARIABLES_CORE_LLMS,
                ),
            ),
            Parameter.build_from(
                "Builtin Embeddings",
                "builtin_embedding",
                type=str,
                placeholder="Please select the builtin embeddings",
                description="The builtin embeddings to use.",
                options=VariablesDynamicOptions(),
                ui=ui.UIVariablesInput(
                    key=BUILTIN_VARIABLES_CORE_EMBEDDINGS,
                ),
            ),
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Model info",
                "model",
                str,
                description="The model info.",
            ),
        ],
    )

    def __init__(
        self,
        openai_api_key: str,
        model: str,
        builtin_flow: str,
        builtin_flow_node: str,
        builtin_variable: str,
        builtin_secret: str,
        builtin_llm: str,
        builtin_embedding: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.openai_api_key = openai_api_key
        self.model = model
        self.builtin_flow = builtin_flow
        self.builtin_flow_node = builtin_flow_node
        self.builtin_variable = builtin_variable
        self.builtin_secret = builtin_secret
        self.builtin_llm = builtin_llm
        self.builtin_embedding = builtin_embedding

    async def map(self, user_name: str) -> str:
        """Map the user name to the model."""
        dict_dict = {
            "openai_api_key": self.openai_api_key,
            "model": self.model,
            "builtin_flow": self.builtin_flow,
            "builtin_flow_node": self.builtin_flow_node,
            "builtin_variable": self.builtin_variable,
            "builtin_secret": self.builtin_secret,
            "builtin_llm": self.builtin_llm,
            "builtin_embedding": self.builtin_embedding,
        }
        json_data = json.dumps(dict_dict, ensure_ascii=False)
        return "Your name is %s, and your model info is %s." % (user_name, json_data)


class ExampleFlowTagsOperator(MapOperator[str, str]):
    """An example flow operator that includes a tags option."""

    metadata = ViewMetadata(
        label="Example Tags Operator",
        name="example_tags_operator",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a tags",
        parameters=[],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Tags",
                "tags",
                str,
                description="The tags to use.",
            ),
        ],
        tags={"order": "higher-order", "type": "example"},
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def map(self, user_name: str) -> str:
        """Map the user name to the tags."""
        return "Your name is %s, and your tags are %s." % (user_name, "higher-order")


class ExampleFlowCodeEditorOperator(MapOperator[str, str]):
    """An example flow operator that includes a code editor as parameter."""

    metadata = ViewMetadata(
        label="Example Flow Code Editor",
        name="example_flow_code_editor",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes a code editor as parameter.",
        parameters=[
            Parameter.build_from(
                "Code Editor",
                "code",
                type=str,
                placeholder="Please input your code",
                description="The code you want to edit.",
                ui=ui.UICodeEditor(
                    language="python",
                ),
            ),
            Parameter.build_from(
                "Language",
                "lang",
                type=str,
                optional=True,
                default="python",
                placeholder="Please select the language",
                description="The language of the code.",
                options=[
                    OptionValue(label="Python", name="python", value="python"),
                    OptionValue(
                        label="JavaScript", name="javascript", value="javascript"
                    ),
                ],
                ui=ui.UISelect(),
            ),
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            )
        ],
        outputs=[
            IOField.build_from(
                "Code",
                "code",
                str,
                description="Result of the code.",
            )
        ],
    )

    def __init__(self, code: str, lang: str = "python", **kwargs):
        super().__init__(**kwargs)
        self.code = code
        self.lang = lang

    async def map(self, user_name: str) -> str:
        """Map the user name to the code."""

        code = self.code
        exit_code = -1
        try:
            exit_code, logs = await self.execute_code_blocks(code, self.lang)
        except Exception as e:
            logger.error(f"Failed to execute code: {e}")
            logs = f"Failed to execute code: {e}"
        return (
            f"Your name is {user_name}, and your code is \n\n```python\n{code}"
            f"\n\n```\n\nThe execution result is \n\n```\n{logs}\n\n```\n\n"
            f"Exit code: {exit_code}."
        )

    async def execute_code_blocks(self, code_blocks: str, lang: str):
        """Execute the code blocks and return the result."""
        from dbgpt.util.code.server import CodeResult, get_code_server

        code_server = await get_code_server(self.system_app)
        result: CodeResult = await code_server.exec(code_blocks, lang)
        return result.exit_code, result.logs


class ExampleFlowDynamicParametersOperator(MapOperator[str, str]):
    """An example flow operator that includes dynamic parameters."""

    metadata = ViewMetadata(
        label="Example Dynamic Parameters Operator",
        name="example_dynamic_parameters_operator",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes dynamic parameters.",
        parameters=[
            Parameter.build_from(
                "Dynamic String",
                "dynamic_1",
                type=str,
                is_list=True,
                placeholder="Please input the dynamic parameter",
                description="The dynamic parameter you want to use, you can add more, "
                "at least 1 parameter.",
                dynamic=True,
                dynamic_minimum=1,
                ui=ui.UIInput(),
            ),
            Parameter.build_from(
                "Dynamic Integer",
                "dynamic_2",
                type=int,
                is_list=True,
                placeholder="Please input the dynamic parameter",
                description="The dynamic parameter you want to use, you can add more, "
                "at least 0 parameter.",
                dynamic=True,
                dynamic_minimum=0,
            ),
        ],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Dynamic",
                "dynamic",
                str,
                description="User's selected dynamic.",
            ),
        ],
    )

    def __init__(self, dynamic_1: List[str], dynamic_2: List[int], **kwargs):
        super().__init__(**kwargs)
        if not dynamic_1:
            raise ValueError("The dynamic string is empty.")
        self.dynamic_1 = dynamic_1
        self.dynamic_2 = dynamic_2

    async def map(self, user_name: str) -> str:
        """Map the user name to the dynamic."""
        return "Your name is %s, and your dynamic is %s." % (
            user_name,
            f"dynamic_1: {self.dynamic_1}, dynamic_2: {self.dynamic_2}",
        )


class ExampleFlowDynamicOutputsOperator(MapOperator[str, str]):
    """An example flow operator that includes dynamic outputs."""

    metadata = ViewMetadata(
        label="Example Dynamic Outputs Operator",
        name="example_dynamic_outputs_operator",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes dynamic outputs.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Dynamic",
                "dynamic",
                str,
                description="User's selected dynamic.",
                dynamic=True,
                dynamic_minimum=1,
            ),
        ],
    )

    async def map(self, user_name: str) -> str:
        """Map the user name to the dynamic."""
        return "Your name is %s, this operator has dynamic outputs." % user_name


class ExampleFlowDynamicInputsOperator(JoinOperator[str]):
    """An example flow operator that includes dynamic inputs."""

    metadata = ViewMetadata(
        label="Example Dynamic Inputs Operator",
        name="example_dynamic_inputs_operator",
        category=OperatorCategory.EXAMPLE,
        description="An example flow operator that includes dynamic inputs.",
        parameters=[],
        inputs=[
            IOField.build_from(
                "User Name",
                "user_name",
                str,
                description="The name of the user.",
            ),
            IOField.build_from(
                "Other Inputs",
                "other_inputs",
                str,
                description="Other inputs.",
                dynamic=True,
                dynamic_minimum=0,
            ),
        ],
        outputs=[
            IOField.build_from(
                "Dynamic",
                "dynamic",
                str,
                description="User's selected dynamic.",
            ),
        ],
    )

    def __init__(self, **kwargs):
        super().__init__(combine_function=self.join, **kwargs)

    async def join(self, user_name: str, *other_inputs: str) -> str:
        """Map the user name to the dynamic."""
        if not other_inputs:
            dyn_inputs = ["You have no other inputs."]
        else:
            dyn_inputs = [
                f"Input {i}: {input_data}" for i, input_data in enumerate(other_inputs)
            ]
        dyn_str = "\n".join(dyn_inputs)
        return "Your name is %s, and your dynamic is %s." % (
            user_name,
            f"other_inputs:\n{dyn_str}",
        )

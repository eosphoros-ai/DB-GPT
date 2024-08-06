"""Some UI components for the AWEL flow."""

import logging
from typing import List, Optional

from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import (
    FunctionDynamicOptions,
    IOField,
    OperatorCategory,
    OptionValue,
    Parameter,
    ViewMetadata,
    ui,
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
                ui=ui.UICheckbox(attr=ui.UICheckbox.UIAttribute(show_search=True)),
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
                    attr=ui.UITextArea.UIAttribute(show_count=True, maxlength=1000),
                    autosize=ui.UITextArea.AutoSize(min_rows=2, max_rows=6),
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

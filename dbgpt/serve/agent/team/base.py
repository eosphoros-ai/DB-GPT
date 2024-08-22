import logging
from enum import Enum
from typing import List, Union

logger = logging.getLogger(__name__)


class TeamMode(Enum):
    def __new__(
        cls, value, name_cn, name_en, description, description_en, remark, remark_en
    ):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.name_cn = name_cn
        obj.name_en = name_en
        obj.description = description
        obj.description_en = description_en
        obj.remark_en = remark_en
        obj.remark = remark
        return obj

    AUTO_PLAN = (
        "auto_plan",
        "多智能体自动规划模式",
        "Multi-agent automatic planning",
        "可以选择多个Agent",
        "Multiple Agents can be selected",
        "自动根据用户目标进行任务规划拆分，分布推进解决，最终完成用户目标",
        "Automatically carry out task planning and splitting according to user goals, distribute and promote solutions, and finally complete user goals",
    )
    AWEL_LAYOUT = (
        "awel_layout",
        "任务流编排模式",
        "AWEL Flow App",
        "选择一个AWEL工作流",
        "Choose an AWEL workflow",
        "根据指定任务流执行，常用于需要保证执行顺序的应用场景",
        "Execute according to the specified task flow, often used in application scenarios that need to ensure the order of execution",
    )
    SINGLE_AGENT = (
        "single_agent",
        "单一智能体模式",
        "Single Agent",
        "只能选择一个Agent",
        "Only one Agent can be selected",
        "和单个Agent进行对话",
        "Conversation with a single Agent",
    )
    NATIVE_APP = (
        "native_app",
        "原生应用模式",
        "Native application",
        "选择应用模板",
        "Choose a native app template",
        "基于现有原生应用模板快速创建应用",
        "Quickly create apps based on existing native app templates",
    )

    def to_dict(self):
        return {
            "name": self.name,
            "value": self.value,
            "name_cn": self.name_cn,
            "name_en": self.name_en,
            "description": self.description,
            "description_en": self.description_en,
            "remark": self.remark,
            "remark_en": self.remark_en,
        }


def content_str(content: Union[str, List, None]) -> str:
    """Converts `content` into a string format.

    This function processes content that may be a string, a list of mixed text and image URLs, or None,
    and converts it into a string. Text is directly appended to the result string, while image URLs are
    represented by a placeholder image token. If the content is None, an empty string is returned.

    Args:
        - content (Union[str, List, None]): The content to be processed. Can be a string, a list of dictionaries
                                      representing text and image URLs, or None.

    Returns:
        str: A string representation of the input content. Image URLs are replaced with an image token.

    Note:
    - The function expects each dictionary in the list to have a "type" key that is either "text" or "image_url".
      For "text" type, the "text" key's value is appended to the result. For "image_url", an image token is appended.
    - This function is useful for handling content that may include both text and image references, especially
      in contexts where images need to be represented as placeholders.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise TypeError(f"content must be None, str, or list, but got {type(content)}")

    rst = ""
    for item in content:
        if not isinstance(item, dict):
            raise TypeError(
                "Wrong content format: every element should be dict if the content is a list."
            )
        assert (
            "type" in item
        ), "Wrong content format. Missing 'type' key in content's dict."
        if item["type"] == "text":
            rst += item["text"]
        elif item["type"] == "image_url":
            rst += "<image>"
        else:
            raise ValueError(
                f"Wrong content format: unknown type {item['type']} within the content"
            )
    return rst

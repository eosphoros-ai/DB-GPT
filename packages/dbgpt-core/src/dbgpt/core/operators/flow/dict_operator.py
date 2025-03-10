"""Dict tool operators."""

from typing import Dict

from dbgpt.core.awel import JoinOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.util.i18n_utils import _


class MergeStringToDictOperator(JoinOperator[Dict[str, str]]):
    """Merge two strings to a dict."""

    metadata = ViewMetadata(
        label=_("Merge String to Dict Operator"),
        name="merge_string_to_dict_operator",
        category=OperatorCategory.COMMON,
        description=_(
            "Merge two strings to a dict, the fist string which is the value from first"
            " upstream is the value of the key `first_key`, the second string which is "
            "the value from second upstream is the value of the key `second_key`."
        ),
        parameters=[
            Parameter.build_from(
                _("First Key"),
                "first_key",
                str,
                optional=True,
                default="user_input",
                description=_("The key for the first string, default is `user_input`."),
            ),
            Parameter.build_from(
                _("Second Key"),
                "second_key",
                str,
                optional=True,
                default="context",
                description=_("The key for the second string, default is `context`."),
            ),
        ],
        inputs=[
            IOField.build_from(
                _("First String"),
                "first",
                str,
                description=_("The first string from first upstream."),
            ),
            IOField.build_from(
                _("Second String"),
                "second",
                str,
                description=_("The second string from second upstream."),
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Output"),
                "output",
                dict,
                description=_(
                    "The merged dict. example: "
                    "{'user_input': 'first', 'context': 'second'}."
                ),
            ),
        ],
    )

    def __init__(
        self, first_key: str = "user_input", second_key: str = "context", **kwargs
    ):
        """Create a MergeStringToDictOperator instance."""
        self._first_key = first_key
        self._second_key = second_key
        super().__init__(combine_function=self._merge_to_dict, **kwargs)

    def _merge_to_dict(self, first: str, second: str) -> Dict[str, str]:
        return {self._first_key: first, self._second_key: second}

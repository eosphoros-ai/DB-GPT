"""Module for managing commands and command plugins."""

import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from dbgpt._private.pydantic import BaseModel
from dbgpt.agent.core.schema import Status
from dbgpt.util.json_utils import serialize
from dbgpt.util.string_utils import extract_content, extract_content_open_ending

logger = logging.getLogger(__name__)


class PluginStatus(BaseModel):
    """A class representing the status of a plugin."""

    name: str
    location: List[int]
    args: dict
    status: Union[Status, str] = Status.TODO.value
    logo_url: Optional[str] = None
    api_result: Optional[str] = None
    err_msg: Optional[str] = None
    start_time: float = datetime.now().timestamp() * 1000
    end_time: Optional[str] = None

    df: Any = None


class ApiCall:
    """A class representing an API call."""

    agent_prefix = "<api-call>"
    agent_end = "</api-call>"
    name_prefix = "<name>"
    name_end = "</name>"

    def __init__(
        self,
        plugin_generator: Any = None,
        display_registry: Any = None,
        backend_rendering: bool = False,
    ):
        """Create a new ApiCall object."""
        self.plugin_status_map: Dict[str, PluginStatus] = {}

        self.plugin_generator = plugin_generator
        self.display_registry = display_registry
        self.start_time = datetime.now().timestamp() * 1000
        self.backend_rendering: bool = backend_rendering

    def _is_need_wait_plugin_call(self, api_call_context):
        start_agent_count = api_call_context.count(self.agent_prefix)

        if start_agent_count > 0:
            return True
        else:
            # Check the new character at the end
            check_len = len(self.agent_prefix)
            last_text = api_call_context[-check_len:]
            for i in range(check_len):
                text_tmp = last_text[-i:]
                prefix_tmp = self.agent_prefix[:i]
                if text_tmp == prefix_tmp:
                    return True
                else:
                    i += 1
        return False

    def check_last_plugin_call_ready(self, all_context):
        """Check if the last plugin call is ready."""
        start_agent_count = all_context.count(self.agent_prefix)
        end_agent_count = all_context.count(self.agent_end)

        if start_agent_count > 0 and start_agent_count == end_agent_count:
            return True
        return False

    def _deal_error_md_tags(self, all_context, api_context, include_end: bool = True):
        error_md_tags = [
            "```",
            "```python",
            "```xml",
            "```json",
            "```markdown",
            "```sql",
        ]
        if not include_end:
            md_tag_end = ""
        else:
            md_tag_end = "```"
        for tag in error_md_tags:
            all_context = all_context.replace(
                tag + api_context + md_tag_end, api_context
            )
            all_context = all_context.replace(
                tag + "\n" + api_context + "\n" + md_tag_end, api_context
            )
            all_context = all_context.replace(
                tag + " " + api_context + " " + md_tag_end, api_context
            )
            all_context = all_context.replace(tag + api_context, api_context)
        return all_context

    def _format_api_context(self, raw_api_context: str) -> str:
        """Format the API context."""
        # Remove newline characters

        raw_api_context = (
            raw_api_context.replace("\\n", " ")
            .replace("\n", " ")
            .replace("\_", "_")
            .replace("\\", " ")
        )
        return raw_api_context

    def api_view_context(self, all_context: str, display_mode: bool = False):
        """Return the view content."""
        call_context_map = extract_content_open_ending(
            all_context, self.agent_prefix, self.agent_end, True
        )
        for api_index, api_context in call_context_map.items():
            key_api_context = self._format_api_context(api_context)
            api_status = self.plugin_status_map.get(key_api_context)
            if api_status is not None:
                if display_mode:
                    all_context = self._deal_error_md_tags(all_context, api_context)
                    if Status.FAILED.value == api_status.status:
                        err_msg = api_status.err_msg
                        all_context = all_context.replace(
                            api_context,
                            f'\n<span style="color:red">Error:</span>{err_msg}\n'
                            + self.to_view_antv_vis(api_status),
                        )
                    else:
                        all_context = all_context.replace(
                            api_context, self.to_view_antv_vis(api_status)
                        )

                else:
                    all_context = self._deal_error_md_tags(
                        all_context, api_context, False
                    )
                    all_context = all_context.replace(
                        api_context, self.to_view_text(api_status)
                    )

            else:
                # not ready api call view change
                now_time = datetime.now().timestamp() * 1000
                cost = (now_time - self.start_time) / 1000
                cost_str = "{:.2f}".format(cost)
                all_context = self._deal_error_md_tags(all_context, api_context)

                all_context = all_context.replace(
                    api_context,
                    f'\n<span style="color:green">Waiting...{cost_str}S</span>\n',
                )

        return all_context

    # def update_from_context(self, all_context):
    #     """Modify the plugin status map based on the context."""
    #     api_context_map: Dict[int, str] = extract_content(
    #         all_context, self.agent_prefix, self.agent_end, True
    #     )
    #     for api_index, api_context in api_context_map.items():
    #         api_context = api_context.replace("\\n", "").replace("\n", "")
    #         api_call_element = ET.fromstring(api_context)
    #         api_name = api_call_element.find("name").text
    #         if api_name.find("[") >= 0 or api_name.find("]") >= 0:
    #             api_name = api_name.replace("[", "").replace("]", "")
    #         api_args = {}
    #         args_elements = api_call_element.find("args")
    #         for child_element in args_elements.iter():
    #             api_args[child_element.tag] = child_element.text
    #
    #         api_status = self.plugin_status_map.get(api_context)
    #         if api_status is None:
    #             api_status = PluginStatus(
    #                 name=api_name, location=[api_index], args=api_args
    #             )
    #             self.plugin_status_map[api_context] = api_status
    #         else:
    #             api_status.location.append(api_index)

    def update_from_context(self, all_context):
        """Modify the plugin status map based on the context."""
        api_context_map: Dict[int, str] = extract_content(
            all_context, self.agent_prefix, self.agent_end, True
        )
        for api_index, api_context in api_context_map.items():
            try:
                # Format the API context
                api_context = self._format_api_context(api_context)
                key_api_context = api_context

                # Try to parse directly
                try:
                    api_call_element = ET.fromstring(api_context)
                except ET.ParseError:
                    # If the parsing fails, try to escape special characters
                    # First find the SQL part and wrap it in CDATA or escape it
                    import re

                    # Find the content between <sql> and </sql> using regular
                    # expressions
                    sql_match = re.search(r"<sql>(.*?)</sql>", api_context, re.DOTALL)
                    if sql_match:
                        sql_content = sql_match.group(1)
                        # Wrap the SQL content in CDATA
                        escaped_sql = f"<sql><![CDATA[{sql_content}]]></sql>"
                        # Replace the original SQL part
                        api_context = api_context.replace(
                            f"<sql>{sql_content}</sql>", escaped_sql
                        )
                        # Try to parse again
                        api_call_element = ET.fromstring(api_context)
                    else:
                        # If the SQL part cannot be found, throw the original error
                        raise

                api_name = api_call_element.find("name").text
                if api_name.find("[") >= 0 or api_name.find("]") >= 0:
                    api_name = api_name.replace("[", "").replace("]", "")

                api_args = {}
                args_elements = api_call_element.find("args")
                for child_element in args_elements.iter():
                    if child_element.tag != "args":  # Skip the args tag
                        # Check if there is CDATA content
                        if child_element.text and "CDATA" in str(child_element.text):
                            # Extract the actual content in CDATA
                            cdata_content = child_element.text.replace(
                                "<![CDATA[", ""
                            ).replace("]]>", "")
                            api_args[child_element.tag] = cdata_content
                        else:
                            api_args[child_element.tag] = child_element.text

                api_status = self.plugin_status_map.get(key_api_context)
                if api_status is None:
                    api_status = PluginStatus(
                        name=api_name, location=[api_index], args=api_args
                    )
                    self.plugin_status_map[key_api_context] = api_status
                else:
                    api_status.location.append(api_index)

            except Exception as e:
                import traceback

                logger.warning(
                    f"Error parsing API context at index {api_index}: {str(e)}"
                )
                logger.warning(f"API context: {api_context}")
                logger.warning(traceback.format_exc())

                continue

    def _to_view_param_str(self, api_status):
        param = {}
        if api_status.name:
            param["name"] = api_status.name
        param["status"] = api_status.status
        if api_status.logo_url:
            param["logo"] = api_status.logo_url

        if api_status.err_msg:
            param["err_msg"] = api_status.err_msg

        if api_status.api_result:
            param["result"] = api_status.api_result

        return json.dumps(param, default=serialize, ensure_ascii=False)

    def to_view_text(self, api_status: PluginStatus):
        """Return the view content."""
        api_call_element = ET.Element("dbgpt-view")
        api_call_element.text = self._to_view_param_str(api_status)
        result = ET.tostring(api_call_element, encoding="utf-8")
        return result.decode("utf-8")

    def to_view_antv_vis(self, api_status: PluginStatus):
        """Return the vis content."""
        if self.backend_rendering:
            html_table = api_status.df.to_html(
                index=False, escape=False, sparsify=False
            )
            table_str = "".join(html_table.split())
            table_str = table_str.replace("\n", " ")
            sql = api_status.args["sql"]
            html = (
                f' \n<div><b>[SQL]{sql}</b></div><div class="w-full overflow-auto">'
                f"{table_str}</div>\n "
            )
            return html
        else:
            api_call_element = ET.Element("chart-view")
            api_call_element.attrib["content"] = self._to_antv_vis_param(api_status)
            api_call_element.text = "\n"
            result = ET.tostring(api_call_element, encoding="utf-8")
            return result.decode("utf-8")

    def _to_antv_vis_param(self, api_status: PluginStatus):
        param = {}
        if api_status.name:
            param["type"] = api_status.name
        if api_status.args:
            param["sql"] = api_status.args["sql"]

        data: Any = []
        if api_status.api_result:
            data = api_status.api_result
        param["data"] = data
        return json.dumps(param, ensure_ascii=False)

    def run_display_sql(self, llm_text, sql_run_func):
        """Run the API calls for displaying SQL data."""
        if self._is_need_wait_plugin_call(
            llm_text
        ) and self.check_last_plugin_call_ready(llm_text):
            # wait api call generate complete
            self.update_from_context(llm_text)
            for key, value in self.plugin_status_map.items():
                if value.status == Status.TODO.value:
                    value.status = Status.RUNNING.value
                    logger.info(f"sql display execution:{value.name},{value.args}")
                    try:
                        sql = value.args["sql"]
                        if sql:
                            param = {
                                "df": sql_run_func(sql),
                            }
                            value.df = param["df"]
                            if self.display_registry.is_valid_command(value.name):
                                value.api_result = self.display_registry.call(
                                    value.name, **param
                                )
                            else:
                                value.api_result = self.display_registry.call(
                                    "response_table", **param
                                )

                        value.status = Status.COMPLETE.value
                    except Exception as e:
                        value.status = Status.FAILED.value
                        value.err_msg = str(e)
                    value.end_time = datetime.now().timestamp() * 1000
        return self.api_view_context(llm_text, True)

    def display_sql_llmvis(self, llm_text, sql_run_func):
        """Render charts using the Antv standard protocol.

        Args:
            llm_text: LLM response text
            sql_run_func: sql run  function

        Returns:
           ChartView protocol text
        """
        try:
            if self._is_need_wait_plugin_call(
                llm_text
            ) and self.check_last_plugin_call_ready(llm_text):
                # wait api call generate complete
                self.update_from_context(llm_text)
                for key, value in self.plugin_status_map.items():
                    if value.status == Status.TODO.value:
                        value.status = Status.RUNNING.value
                        logger.info(f"SQL execution:{value.name},{value.args}")
                        try:
                            sql = value.args["sql"]
                            if sql is not None and len(sql) > 0:
                                data_df = sql_run_func(sql)
                                value.df = data_df
                                value.api_result = json.loads(
                                    data_df.to_json(
                                        orient="records",
                                        date_format="iso",
                                        date_unit="s",
                                    )
                                )
                                value.status = Status.COMPLETE.value
                            else:
                                value.status = Status.FAILED.value
                                value.err_msg = "No executable sql！"

                        except Exception as e:
                            logger.error(f"data prepare exception！{str(e)}")
                            value.status = Status.FAILED.value
                            value.err_msg = str(e)
                        value.end_time = datetime.now().timestamp() * 1000
        except Exception as e:
            logger.error("Api parsing exception", e)
            raise ValueError("Api parsing exception," + str(e))

        return self.api_view_context(llm_text, True)

    def display_only_sql_vis(self, chart: dict, sql_2_df_func):
        """Display the chart using the vis standard protocol."""
        err_msg = None
        sql = chart.get("sql", None)
        try:
            param = {}
            df = sql_2_df_func(sql)
            if not sql or len(sql) <= 0:
                return None

            param["sql"] = sql
            param["type"] = chart.get("display_type", "response_table")
            param["title"] = chart.get("title", "")
            param["describe"] = chart.get("thought", "")

            param["data"] = json.loads(
                df.to_json(orient="records", date_format="iso", date_unit="s")
            )
            view_json_str = json.dumps(param, default=serialize, ensure_ascii=False)
        except Exception as e:
            logger.error("parse_view_response error!" + str(e))
            err_param = {"sql": f"{sql}", "type": "response_table", "data": []}
            err_msg = str(e)
            view_json_str = json.dumps(err_param, default=serialize, ensure_ascii=False)

        # api_call_element.text = view_json_str
        result = f"```vis-chart\n{view_json_str}\n```"
        if err_msg:
            return f"""<span style=\"color:red\">ERROR!</span>{err_msg} \n {result}"""
        else:
            return result

    def display_dashboard_vis(
        self, charts: List[dict], sql_2_df_func, title: Optional[str] = None
    ):
        """Display the dashboard using the vis standard protocol."""
        err_msg = None
        view_json_str = None

        chart_items = []
        try:
            if not charts or len(charts) <= 0:
                return "Have no chart data!"
            for chart in charts:
                param = {}
                sql = chart.get("sql", "")
                param["sql"] = sql
                param["type"] = chart.get("display_type", "response_table")
                param["title"] = chart.get("title", "")
                param["describe"] = chart.get("thought", "")
                try:
                    df = sql_2_df_func(sql)
                    param["data"] = json.loads(
                        df.to_json(orient="records", date_format="iso", date_unit="s")
                    )
                except Exception as e:
                    param["data"] = []
                    param["err_msg"] = str(e)
                chart_items.append(param)

            dashboard_param = {
                "data": chart_items,
                "chart_count": len(chart_items),
                "title": title,
                "display_strategy": "default",
                "style": "default",
            }
            view_json_str = json.dumps(
                dashboard_param, default=serialize, ensure_ascii=False
            )

        except Exception as e:
            logger.error("parse_view_response error!" + str(e))
            return f"```error\nReport rendering exception！{str(e)}\n```"

        result = f"```vis-dashboard\n{view_json_str}\n```"
        if err_msg:
            return (
                f"""\\n <span style=\"color:red\">ERROR!</span>{err_msg} \n {result}"""
            )
        else:
            return result

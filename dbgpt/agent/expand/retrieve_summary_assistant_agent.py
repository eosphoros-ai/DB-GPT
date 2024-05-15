"""Retrieve Summary Assistant Agent."""

import glob
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from dbgpt.configs.model_config import PILOT_PATH
from dbgpt.core import ModelMessageRoleType

from ..core.action.base import Action, ActionOutput
from ..core.agent import Agent, AgentMessage, AgentReviewInfo
from ..core.base_agent import ConversableAgent
from ..core.profile import ProfileConfig
from ..resource.base import AgentResource
from ..util.cmp import cmp_string_equal

try:
    from unstructured.partition.auto import partition

    HAS_UNSTRUCTURED = True
except ImportError:
    HAS_UNSTRUCTURED = False

logger = logging.getLogger()

TEXT_FORMATS = [
    "txt",
    "json",
    "csv",
    "tsv",
    "md",
    "html",
    "htm",
    "rtf",
    "rst",
    "jsonl",
    "log",
    "xml",
    "yaml",
    "yml",
    "pdf",
]
UNSTRUCTURED_FORMATS = [
    "doc",
    "docx",
    "epub",
    "msg",
    "odt",
    "org",
    "pdf",
    "ppt",
    "pptx",
    "rtf",
    "rst",
    "xlsx",
]  # These formats will be parsed by the 'unstructured' library, if installed.
if HAS_UNSTRUCTURED:
    TEXT_FORMATS += UNSTRUCTURED_FORMATS
    TEXT_FORMATS = list(set(TEXT_FORMATS))

VALID_CHUNK_MODES = frozenset({"one_line", "multi_lines"})


def _get_max_tokens(model="gpt-3.5-turbo"):
    """Get the maximum number of tokens for a given model."""
    if "32k" in model:
        return 32000
    elif "16k" in model:
        return 16000
    elif "gpt-4" in model:
        return 8000
    else:
        return 4000


_NO_RESPONSE = "NO RELATIONSHIP.UPDATE TEXT CONTENT."


class RetrieveSummaryAssistantAgent(ConversableAgent):
    """Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default
    system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    """

    PROMPT_QA: str = (
        "You are a great summary writer to summarize the provided text content "
        "according to user questions.\n"
        "User's Question is: {input_question}\n\n"
        "Provided text content is: {input_context}\n\n"
        "Please complete this task step by step following instructions below:\n"
        "   1. You need to first detect user's question that you need to answer with "
        "your summarization.\n"
        "   2. Then you need to summarize the provided text content that ONLY CAN "
        "ANSWER user's question and filter useless information as possible as you can. "
        "YOU CAN ONLY USE THE PROVIDED TEXT CONTENT!! DO NOT CREATE ANY SUMMARIZATION "
        "WITH YOUR OWN KNOWLEDGE!!!\n"
        "   3. Output the content of summarization that ONLY CAN ANSWER user's question"
        " and filter useless information as possible as you can. The output language "
        "must be the same to user's question language!! You must give as short an "
        "summarization as possible!!! DO NOT CREATE ANY SUMMARIZATION WITH YOUR OWN "
        "KNOWLEDGE!!!\n\n"
        "####Important Notice####\n"
        "If the provided text content CAN NOT ANSWER user's question, ONLY output "
        "'NO RELATIONSHIP.UPDATE TEXT CONTENT.'!!."
    )
    CHECK_RESULT_SYSTEM_MESSAGE: str = (
        "You are an expert in analyzing the results of a summary task."
        "Your responsibility is to check whether the summary results can summarize the "
        "input provided by the user, and then make a judgment. You need to answer "
        "according to the following rules:\n"
        "    Rule 1: If you think the summary results can summarize the input provided"
        " by the user, only return True.\n"
        "    Rule 2: If you think the summary results can NOT summarize the input "
        "provided by the user, return False and the reason, split by | and ended "
        "by TERMINATE. For instance: False|Some important concepts in the input are "
        "not summarized. TERMINATE"
    )

    DEFAULT_DESCRIBE: str = (
        "Summarize provided content according to user's questions and "
        "the provided file paths."
    )
    profile: ProfileConfig = ProfileConfig(
        name="RetrieveSummarizer",
        role="Assistant",
        goal="You're an extraction expert. You need to extract Please complete this "
        "task step by step following instructions below:\n"
        "   1. You need to first ONLY extract user's question that you need to answer "
        "without ANY file paths and URLs. \n"
        "   2. Extract the provided file paths and URLs.\n"
        "   3. Construct the extracted file paths and URLs as a list of strings.\n"
        "   4. ONLY output the extracted results with the following json format: "
        "{{ response }}.",
        desc=DEFAULT_DESCRIBE,
    )

    chunk_token_size: int = 4000
    chunk_mode: str = "multi_lines"

    _model: str = "gpt-3.5-turbo-16k"
    _max_tokens: int = _get_max_tokens(_model)
    context_max_tokens: int = int(_max_tokens * 0.8)

    def __init__(
        self,
        **kwargs,
    ):
        """Create a new instance of the agent."""
        super().__init__(
            **kwargs,
        )
        self._init_actions([SummaryAction])

    def _init_reply_message(self, received_message: AgentMessage) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message)
        json_data = {"user_question": "user's question", "file_list": "file&URL list"}
        reply_message.context = {"response": json.dumps(json_data, ensure_ascii=False)}
        return reply_message

    async def generate_reply(
        self,
        received_message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ):
        """Generate a reply based on the received messages."""
        reply_message: AgentMessage = self._init_reply_message(
            received_message=received_message
        )
        # 1.Think about how to do things
        llm_reply, model_name = await self.thinking(
            await self._load_thinking_messages(
                received_message,
                sender,
                rely_messages,
                context=reply_message.get_dict_context(),
            )
        )

        if not llm_reply:
            raise ValueError("No reply from LLM.")
        ai_reply_dic = json.loads(llm_reply)
        user_question = ai_reply_dic["user_question"]
        file_list = ai_reply_dic["file_list"]

        # 2. Split files and URLs in the file list dictionary into chunks
        extracted_files = self._get_files_from_dir(file_list)
        chunks = await self._split_files_to_chunks(files=extracted_files)

        summaries = ""
        for count, chunk in enumerate(chunks[:]):
            print(count)
            temp_sys_message = self.PROMPT_QA.format(
                input_question=user_question, input_context=chunk
            )
            chunk_ai_reply, model = await self.thinking(
                messages=[
                    AgentMessage(role=ModelMessageRoleType.HUMAN, content=user_question)
                ],
                prompt=temp_sys_message,
            )
            if chunk_ai_reply and not cmp_string_equal(
                _NO_RESPONSE, chunk_ai_reply, True, True, True
            ):
                summaries += f"{chunk_ai_reply}\n"

        temp_sys_message = self.PROMPT_QA.format(
            input_question=user_question, input_context=summaries
        )

        final_summary_ai_reply, model = await self.thinking(
            messages=[
                AgentMessage(role=ModelMessageRoleType.HUMAN, content=user_question)
            ],
            prompt=temp_sys_message,
        )
        reply_message.model_name = model
        reply_message.content = final_summary_ai_reply

        print("HERE IS THE FINAL SUMMARY!!!!!")
        print(final_summary_ai_reply)

        approve = True
        comments = None
        if reviewer and final_summary_ai_reply:
            approve, comments = await reviewer.review(final_summary_ai_reply, self)

        reply_message.review_info = AgentReviewInfo(
            approve=approve,
            comments=comments,
        )
        if approve:
            # 3.Act based on the results of your thinking
            act_extent_param = self.prepare_act_param()
            act_out: Optional[ActionOutput] = await self.act(
                message=final_summary_ai_reply,
                sender=sender,
                reviewer=reviewer,
                **act_extent_param,
            )
            if act_out:
                reply_message.action_report = act_out.to_dict()
            # 4.Reply information verification
            check_pass, reason = await self.verify(reply_message, sender, reviewer)
            is_success = check_pass
            # 5.Optimize wrong answers myself
            if not check_pass:
                reply_message.content = reason
            reply_message.success = is_success
        return reply_message

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        """Verify the correctness of the results."""
        action_report = message.action_report
        task_result = ""
        if action_report:
            task_result = action_report.get("content", "")

        check_result, model = await self.thinking(
            messages=[
                AgentMessage(
                    role=ModelMessageRoleType.HUMAN,
                    content=(
                        "Please understand the following user input and summary results"
                        " and give your judgment:\n"
                        f"User Input: {message.current_goal}\n"
                        f"Summary Results: {task_result}"
                    ),
                )
            ],
            prompt=self.CHECK_RESULT_SYSTEM_MESSAGE,
        )
        fail_reason = ""
        if check_result and (
            "true" in check_result.lower() or "yes" in check_result.lower()
        ):
            success = True
        elif not check_result:
            success = False
            fail_reason = (
                "The summary results cannot summarize the user input. "
                "Please re-understand and complete the summary task."
            )
        else:
            success = False
            try:
                _, fail_reason = check_result.split("|")
                fail_reason = (
                    "The summary results cannot summarize the user input due"
                    f" to: {fail_reason}. Please re-understand and complete the summary"
                    " task."
                )
            except Exception:
                logger.warning(
                    "The model thought the results are irrelevant but did not give the"
                    " correct format of results."
                )
                fail_reason = (
                    "The summary results cannot summarize the user input. "
                    "Please re-understand and complete the summary task."
                )
        return success, fail_reason

    def _get_files_from_dir(
        self,
        dir_path: Union[str, List[str]],
        types: list = TEXT_FORMATS,
        recursive: bool = True,
    ):
        """Return a list of all the files in a given directory.

        A url, a file path or a list of them.
        """
        if len(types) == 0:
            raise ValueError("types cannot be empty.")
        types = [t[1:].lower() if t.startswith(".") else t.lower() for t in set(types)]
        types += [t.upper() for t in types]

        files = []
        # If the path is a list of files or urls, process and return them
        if isinstance(dir_path, list):
            for item in dir_path:
                if os.path.isfile(item):
                    files.append(item)
                elif self._is_url(item):
                    files.append(self._get_file_from_url(item))
                elif os.path.exists(item):
                    try:
                        files.extend(self._get_files_from_dir(item, types, recursive))
                    except ValueError:
                        logger.warning(f"Directory {item} does not exist. Skipping.")
                else:
                    logger.warning(f"File {item} does not exist. Skipping.")
            return files

        # If the path is a file, return it
        if os.path.isfile(dir_path):
            return [dir_path]

        # If the path is a url, download it and return the downloaded file
        if self._is_url(dir_path):
            return [self._get_file_from_url(dir_path)]

        if os.path.exists(dir_path):
            for type in types:
                if recursive:
                    files += glob.glob(
                        os.path.join(dir_path, f"**/*.{type}"), recursive=True
                    )
                else:
                    files += glob.glob(
                        os.path.join(dir_path, f"*.{type}"), recursive=False
                    )
        else:
            logger.error(f"Directory {dir_path} does not exist.")
            raise ValueError(f"Directory {dir_path} does not exist.")
        return files

    def _get_file_from_url(self, url: str, save_path: Optional[str] = None):
        """Download a file from a URL."""
        import requests
        from bs4 import BeautifulSoup

        if save_path is None:
            target_directory = os.path.join(PILOT_PATH, "data")
            os.makedirs(target_directory, exist_ok=True)
            save_path = os.path.join(target_directory, os.path.basename(url))
        else:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
        proxies: Dict[str, Any] = {}
        if os.getenv("http_proxy"):
            proxies["http"] = os.getenv("http_proxy")
        if os.getenv("https_proxy"):
            proxies["https"] = os.getenv("https_proxy")
        with requests.get(url, proxies=proxies, timeout=10, stream=True) as r:
            r.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        with open(save_path, "r", encoding="utf-8") as file:
            html_content = file.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # 可以根据需要从Beautiful Soup对象中提取数据，例如：
        # title = soup.title.string  # 获取网页标题
        paragraphs = soup.find_all("p")  # 获取所有段落文本

        # 将解析后的内容重新写入到相同的save_path
        with open(save_path, "w", encoding="utf-8") as f:
            for paragraph in paragraphs:
                f.write(paragraph.get_text() + "\n")  # 获取段落文本并写入文件

        return save_path

    def _is_url(self, string: str):
        """Return True if the string is a valid URL."""
        try:
            result = urlparse(string)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    async def _split_text_to_chunks(
        self,
        text: str,
        chunk_mode: str = "multi_lines",
        must_break_at_empty_line: bool = True,
    ):
        """Split a long text into chunks of max_tokens."""
        max_tokens = self.chunk_token_size
        if chunk_mode not in VALID_CHUNK_MODES:
            raise AssertionError
        if chunk_mode == "one_line":
            must_break_at_empty_line = False
        chunks = []
        lines = text.split("\n")
        lines_tokens = [await self._count_token(line) for line in lines]
        sum_tokens = sum(lines_tokens)
        while sum_tokens > max_tokens:
            if chunk_mode == "one_line":
                estimated_line_cut = 2
            else:
                estimated_line_cut = int(max_tokens / sum_tokens * len(lines)) + 1
            cnt = 0
            prev = ""
            for cnt in reversed(range(estimated_line_cut)):
                if must_break_at_empty_line and lines[cnt].strip() != "":
                    continue
                if sum(lines_tokens[:cnt]) <= max_tokens:
                    prev = "\n".join(lines[:cnt])
                    break
            if cnt == 0:
                logger.warning(
                    f"max_tokens is too small to fit a single line of text. Breaking "
                    f"this line:\n\t{lines[0][:100]} ..."
                )
                if not must_break_at_empty_line:
                    split_len = int(max_tokens / lines_tokens[0] * 0.9 * len(lines[0]))
                    prev = lines[0][:split_len]
                    lines[0] = lines[0][split_len:]
                    lines_tokens[0] = await self._count_token(lines[0])
                else:
                    logger.warning(
                        "Failed to split docs with must_break_at_empty_line being True,"
                        " set to False."
                    )
                    must_break_at_empty_line = False
            (
                chunks.append(prev) if len(prev) > 10 else None
            )  # don't add chunks less than 10 characters
            lines = lines[cnt:]
            lines_tokens = lines_tokens[cnt:]
            sum_tokens = sum(lines_tokens)
        text_to_chunk = "\n".join(lines)
        (
            chunks.append(text_to_chunk) if len(text_to_chunk) > 10 else None
        )  # don't add chunks less than 10 characters
        return chunks

    def _extract_text_from_pdf(self, file: str) -> str:
        """Extract text from PDF files."""
        text = ""
        import pypdf

        with open(file, "rb") as f:
            reader = pypdf.PdfReader(f)
            if reader.is_encrypted:  # Check if the PDF is encrypted
                try:
                    reader.decrypt("")
                except pypdf.errors.FileNotDecryptedError as e:
                    logger.warning(f"Could not decrypt PDF {file}, {e}")
                    return text  # Return empty text if PDF could not be decrypted

            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                text += page.extract_text()

        if not text.strip():  # Debugging line to check if text is empty
            logger.warning(f"Could not decrypt PDF {file}")

        return text

    async def _split_files_to_chunks(
        self,
        files: list,
        chunk_mode: str = "multi_lines",
        must_break_at_empty_line: bool = True,
        custom_text_split_function: Optional[Callable] = None,
    ):
        """Split a list of files into chunks of max_tokens."""
        chunks = []

        for file in files:
            _, file_extension = os.path.splitext(file)
            file_extension = file_extension.lower()

            if HAS_UNSTRUCTURED and file_extension[1:] in UNSTRUCTURED_FORMATS:
                text = partition(file)
                text = "\n".join([t.text for t in text]) if len(text) > 0 else ""
            elif file_extension == ".pdf":
                text = self._extract_text_from_pdf(file)
            else:  # For non-PDF text-based files
                with open(file, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

            if (
                not text.strip()
            ):  # Debugging line to check if text is empty after reading
                logger.warning(f"No text available in file: {file}")
                continue  # Skip to the next file if no text is available

            if custom_text_split_function is not None:
                chunks += custom_text_split_function(text)
            else:
                chunks += await self._split_text_to_chunks(
                    text, chunk_mode, must_break_at_empty_line
                )

        return chunks

    async def _count_token(
        self, input: Union[str, List, Dict], model: str = "gpt-3.5-turbo-0613"
    ) -> int:
        """Count number of tokens used by an OpenAI model.

        Args:
            input: (str, list, dict): Input to the model.
            model: (str): Model name.

        Returns:
            int: Number of tokens from the input.
        """
        _llm_client = self.not_null_llm_client
        if isinstance(input, str):
            return await _llm_client.count_token(model, input)
        elif isinstance(input, list):
            return sum([await _llm_client.count_token(model, i) for i in input])
        else:
            raise ValueError("input must be str or list")


class SummaryAction(Action[None]):
    """Simple Summary Action."""

    def __init__(self):
        """Create a new instance of the action."""
        super().__init__()

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action."""
        fail_reason = None
        response_success = True
        view = None
        content = None
        if ai_message is None:
            # Answer failed, turn on automatic repair
            fail_reason += "Nothing is summarized, please check your input."
            response_success = False
        else:
            try:
                if "NO RELATIONSHIP." in ai_message:
                    fail_reason = (
                        "Return summarization error, the provided text "
                        "content has no relationship to user's question. TERMINATE."
                    )
                    response_success = False
                else:
                    content = ai_message
                    view = content
            except Exception as e:
                fail_reason = f"Return summarization error, {str(e)}"
                response_success = False

        if not response_success:
            content = fail_reason
        return ActionOutput(is_exe_success=response_success, content=content, view=view)

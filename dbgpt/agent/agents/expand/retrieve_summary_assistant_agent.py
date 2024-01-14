import os
import glob
import requests
import logging
import tiktoken
import pypdf
import asyncio
import json
import pdb


from urllib.parse import urlparse
from typing import Callable, Dict, Literal, Optional, Union, List
from bs4 import BeautifulSoup

from dbgpt.agent.agents.base_agent import ConversableAgent
from dbgpt.agent.plugin.commands.command_mange import ApiCall

from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.agent.agents.agent import Agent, AgentContext
from dbgpt.core.interface.message import ModelMessageRoleType

from dbgpt.configs.model_config import PILOT_PATH

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x


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


class RetrieveSummaryAssistantAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    DEFAULT_SYSTEM_MESSAGE = """You're an expert extrater. You need to extract
        Please complete this task step by step following instructions below:
           1. You need to first ONLY extract user's question that you need to answer without ANY file paths and URLs.
           3. Extract the provided file paths and URLs.
           4. Construct the extracted file paths and URLs as a list of strings.
           5. ONLY output the extracted results with the following json format: "{"user_question": user's question, "file_list": file&URL list}".
        """

    PROMPT_QA = """You are a great summary writter to summarize the provided text content according to user questions.

                User's Question is: {input_question}

                Provided text content is: {input_context}

                Please complete this task step by step following instructions below:
                1. You need to first detect user's question that you need to answer with your summarization.
                2. Then you need to summarize the provided text content that ONLY CAN ANSWER user's question and filter useless information as possible as you can. YOU CAN ONLY USE THE PROVIDED TEXT CONTENT!! DO NOT CREATE ANY SUMMARIZATION WITH YOUR OWN KNOWLEGE!!!
                3. Output the content of summarization that ONLY CAN ANSWER user's question and filter useless information as possible as you can. The output language must be the same to user's question language!! You must give as short an summarization as possible!!! DO NOT CREATE ANY SUMMARIZATION WITH YOUR OWN KNOWLEGE!!!

                ####Important Notice####
                If the provided text content CAN NOT ANSWER user's question, ONLY output "NO RELATIONSHIP.UPDATE TEXT CONTENT."!!.
                """

    CHECK_RESULT_SYSTEM_MESSAGE = f"""
    You are an expert in analyzing the results of a summary task.
    Your responsibility is to check whether the summary results can summarize the input provided by the user, and then make a judgment. You need to answer according to the following rules:
        Rule 1: If you think the summary results can summarize the input provided by the user, only return True.
        Rule 2: If you think the summary results can NOT summarize the input provided by the user, return False and the reason, splitted by | and ended by TERMINATE. For instance: False|Some important concepts in the input are not summarized. TERMINATE
    """

    DEFAULT_DESCRIBE = """Summarize provided content according to user's questions and the provided file paths."""

    NAME = "RetrieveSummarizer"

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
        describe: Optional[str] = DEFAULT_DESCRIBE,
        is_termination_msg: Optional[Callable[[Dict], bool]] = lambda x: isinstance(
            x, dict
        )
        and "TERMINATE" in str(x).upper(),
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "NEVER",
        retrieve_config: Optional[Dict] = None,
        **kwargs,
    ):
        super().__init__(
            name=self.NAME,
            memory=memory,
            describe=describe,
            system_message="",
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode="NEVER",
            agent_context=agent_context,
            **kwargs,
        )

        self.chunk_token_size = 4000
        self.chunk_mode = "multi_lines"
        self._model = "gpt-3.5-turbo-16k"
        self._max_tokens = self.get_max_tokens(self._model)
        self.context_max_tokens = self._max_tokens * 0.8
        self.search_string = ""  # the search string used in the current query
        self.chunks = []

        # Register_reply
        self.register_reply(Agent, RetrieveSummaryAssistantAgent.retrieve_summary_reply)
        self.agent_context = agent_context

    @staticmethod
    def get_max_tokens(model="gpt-3.5-turbo"):
        if "32k" in model:
            return 32000
        elif "16k" in model:
            return 16000
        elif "gpt-4" in model:
            return 8000
        else:
            return 4000

    async def a_generate_reply(
        self,
        message: Optional[Dict],
        sender: Agent,
        reviewer: Agent,
        silent: Optional[bool] = False,
        rely_messages: Optional[List[Dict]] = None,
    ):
        print("HERE IS THE MESSAGE!!!!!")
        print(message["content"])
        ## 1.Using LLM to reason user's question and list of file and URLs context
        await self.a_system_fill_param()
        await asyncio.sleep(5)  ##TODO  Rate limit reached for gpt-3.5-turbo
        current_messages = self.process_now_message(message, sender, rely_messages)
        print("HERE IS THE CURRENT MESSAGE!!!!!")
        print(current_messages)
        ai_reply, model = await self.a_reasoning_reply(messages=current_messages)
        ai_reply_dic = json.loads(ai_reply)
        user_question = ai_reply_dic["user_question"]
        file_list = ai_reply_dic["file_list"]

        ## 2. Split files and URLs in the file list dictionary into chunks
        extracted_files = self._get_files_from_dir(file_list)
        self.chunks = self._split_files_to_chunks(files=extracted_files)

        ## New message build
        new_message = {}
        new_message["context"] = current_messages[-1].get("context", None)
        new_message["current_gogal"] = current_messages[-1].get("current_gogal", None)
        new_message["role"] = "assistant"
        new_message["content"] = user_question
        new_message["model_name"] = model
        # current_messages.append(new_message)
        ## 3. Update system message as a summarizer message for each chunk
        print(len(self.chunks))
        ## Summary message build
        summary_message = {}
        summary_message["context"] = message.get("context", None)
        summary_message["current_gogal"] = message.get("current_gogal", None)

        summaries = ""
        count = 0
        for chunk in self.chunks[:]:
            count += 1
            print(count)
            temp_sys_message = self.PROMPT_QA.format(
                input_question=user_question, input_context=chunk
            )
            self.update_system_message(system_message=temp_sys_message)
            chunk_message = self.process_now_message(
                current_message=new_message, sender=sender, rely_messages=None
            )
            chunk_message[0]["role"] = "assistant"
            chunk_ai_reply, model = await self.a_reasoning_reply(messages=chunk_message)
            if chunk_ai_reply != "NO RELATIONSHIP. UPDATE TEXT CONTENT.":
                summaries += f"{chunk_ai_reply}\n"

        temp_sys_message = self.PROMPT_QA.format(
            input_question=user_question, input_context=summaries
        )
        self.update_system_message(system_message=temp_sys_message)
        final_summary_message = self.process_now_message(
            current_message=new_message, sender=sender, rely_messages=None
        )
        final_summary_message[0]["role"] = "assistant"
        final_summary_ai_reply, model = await self.a_reasoning_reply(
            messages=final_summary_message
        )
        summary_message["content"] = final_summary_ai_reply
        summary_message["model_name"] = model
        print("HERE IS THE FINAL SUMMARY!!!!!")
        print(final_summary_ai_reply)

        ## 4.Review of reasoning results
        approve = True
        comments = None
        if reviewer and final_summary_ai_reply:
            approve, comments = await reviewer.a_review(final_summary_ai_reply, self)
        summary_message["review_info"] = {"approve": approve, "comments": comments}

        ## 3.reasoning result action
        if approve:
            excute_reply = await self.a_action_reply(
                message=final_summary_ai_reply,
                sender=sender,
                reviewer=reviewer,
            )
            summary_message["action_report"] = self._process_action_reply(excute_reply)

        # 4.verify reply
        return await self.a_verify_reply(summary_message, sender, reviewer)

    async def a_verify(self, message: Optional[Dict]):
        self.update_system_message(self.CHECK_RESULT_SYSTEM_MESSAGE)
        current_goal = message.get("current_gogal", None)
        action_report = message.get("action_report", None)
        task_result = ""
        if action_report:
            task_result = action_report.get("content", "")

        check_result, model = await self.a_reasoning_reply(
            [
                {
                    "role": ModelMessageRoleType.HUMAN,
                    "content": f"""Please understand the following user input and summary results and give your judgment:
                        User Input: {current_goal}
                        Summary Results: {task_result}
                    """,
                }
            ]
        )
        fail_reason = ""
        if "True" in check_result:
            success = True
        else:
            success = False
            try:
                _, fail_reason = check_result.split("|")
                fail_reason = f"The summary results cannot summarize the user input due to: {fail_reason}. Please re-understand and complete the summary task."
            except:
                logger.warning(
                    f"The model thought the results are irrelevant but did not give the correct format of results."
                )
                fail_reason = "The summary results cannot summarize the user input. Please re-understand and complete the summary task."
        return success, fail_reason

    async def retrieve_summary_reply(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply with summary."""
        # TODO:
        # 1. Extract User Question from massage - Done with parameteres
        # 2. Extract file / webpage list from message
        # 3. Summarize each chunk
        # 4. Combine summarization of each chunk

        fail_reason = None
        response_success = True
        view = None
        content = None
        if message is None:
            # Answer failed, turn on automatic repair
            fail_reason += f"Nothing is summarized, please check your input."
            response_success = False
        else:
            try:
                if "NO RELATIONSHIP." in message:
                    fail_reason = f"Return summarization error, the provided text content has no relationship to user's question. TERMINATE."
                    response_success = False
                else:
                    content = message
                    view = content
            except Exception as e:
                fail_reason = f"Return summarization error, {str(e)}"
                response_success = False

        if not response_success:
            content = fail_reason
        return True, {
            "is_exe_success": response_success,
            "content": content,
            "view": view,
        }

    def _get_files_from_dir(
        self,
        dir_path: Union[str, List[str]],
        types: list = TEXT_FORMATS,
        recursive: bool = True,
    ):
        """Return a list of all the files in a given directory, a url, a file path or a list of them."""
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

    def _get_file_from_url(self, url: str, save_path: str = None):
        """Download a file from a URL."""
        if save_path is None:
            target_directory = os.path.join(PILOT_PATH, "data")
            os.makedirs(target_directory, exist_ok=True)
            save_path = os.path.join(target_directory, os.path.basename(url))
        else:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with requests.get(url, stream=True) as r:
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

    def _split_text_to_chunks(
        self,
        text: str,
        max_tokens: int = 4000,
        chunk_mode: str = "multi_lines",
        must_break_at_empty_line: bool = True,
        overlap: int = 10,
    ):
        """Split a long text into chunks of max_tokens."""
        max_tokens = self.chunk_token_size
        if chunk_mode not in VALID_CHUNK_MODES:
            raise AssertionError
        if chunk_mode == "one_line":
            must_break_at_empty_line = False
        chunks = []
        lines = text.split("\n")
        lines_tokens = [self._count_token(line) for line in lines]
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
                    f"max_tokens is too small to fit a single line of text. Breaking this line:\n\t{lines[0][:100]} ..."
                )
                if not must_break_at_empty_line:
                    split_len = int(max_tokens / lines_tokens[0] * 0.9 * len(lines[0]))
                    prev = lines[0][:split_len]
                    lines[0] = lines[0][split_len:]
                    lines_tokens[0] = self._count_token(lines[0])
                else:
                    logger.warning(
                        "Failed to split docs with must_break_at_empty_line being True, set to False."
                    )
                    must_break_at_empty_line = False
            chunks.append(prev) if len(
                prev
            ) > 10 else None  # don't add chunks less than 10 characters
            lines = lines[cnt:]
            lines_tokens = lines_tokens[cnt:]
            sum_tokens = sum(lines_tokens)
        text_to_chunk = "\n".join(lines)
        chunks.append(text_to_chunk) if len(
            text_to_chunk
        ) > 10 else None  # don't add chunks less than 10 characters
        return chunks

    def _extract_text_from_pdf(self, file: str) -> str:
        """Extract text from PDF files"""
        text = ""
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

    def _split_files_to_chunks(
        self,
        files: list,
        max_tokens: int = 4000,
        chunk_mode: str = "multi_lines",
        must_break_at_empty_line: bool = True,
        custom_text_split_function: Callable = None,
    ):
        """Split a list of files into chunks of max_tokens."""
        max_tokens = self.chunk_token_size
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
                chunks += self._split_text_to_chunks(
                    text, max_tokens, chunk_mode, must_break_at_empty_line
                )

        return chunks

    def _count_token(
        self, input: Union[str, List, Dict], model: str = "gpt-3.5-turbo-0613"
    ) -> int:
        """Count number of tokens used by an OpenAI model.
        Args:
            input: (str, list, dict): Input to the model.
            model: (str): Model name.

        Returns:
            int: Number of tokens from the input.
        """
        if isinstance(input, str):
            return self._num_token_from_text(input, model=model)
        elif isinstance(input, list) or isinstance(input, dict):
            return self._num_token_from_messages(input, model=model)
        else:
            raise ValueError("input must be str, list or dict")

    def _num_token_from_text(self, text: str, model: str = "gpt-3.5-turbo-0613"):
        """Return the number of tokens used by a string."""
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"Model {model} not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))


if __name__ == "__main__":
    import asyncio
    import os

    from dbgpt.agent.agents.agent import AgentContext
    from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent

    from dbgpt.core.interface.llm import ModelMetadata
    from dbgpt.model import OpenAILLMClient

    llm_client = OpenAILLMClient()
    context: AgentContext = AgentContext(
        conv_id="retrieve_summarize", llm_provider=llm_client
    )
    context.llm_models = [ModelMetadata(model="gpt-3.5-turbo-16k")]

    default_memory = GptsMemory()
    summarizer = RetrieveSummaryAssistantAgent(
        memory=default_memory, agent_context=context
    )

    user_proxy = UserProxyAgent(memory=default_memory, agent_context=context)

    asyncio.run(
        user_proxy.a_initiate_chat(
            recipient=summarizer,
            reviewer=user_proxy,
            message="""I want to summarize advantages of Nuclear Power. 
            You can refer the following file paths and URLs: ['/home/ubuntu/chenguang-dbgpt/DB-GPT/dbgpt/agent/agents/expand/Nuclear_power.pdf', 'https://en.wikipedia.org/wiki/Modern_Family', '/home/ubuntu/chenguang-dbgpt/DB-GPT/dbgpt/agent/agents/expand/Taylor_Swift.pdf', 'https://en.wikipedia.org/wiki/Chernobyl_disaster']
            """,
        )
    )

    ## dbgpt-vis message infos
    print(asyncio.run(default_memory.one_plan_chat_competions("summarize")))

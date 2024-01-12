import os
import glob
import requests
from urllib.parse import urlparse
from typing import Callable, Dict, Literal, Optional, Union, List

from dbgpt._private.config import Config
from dbgpt.agent.agents.base_agent import ConversableAgent
from dbgpt.agent.plugin.commands.command_mange import ApiCall

from ...memory.gpts_memory import GptsMemory
from ..agent import Agent, AgentContext

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


class RetrieveSummaryAssistantAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    # TODO: Write a new default system message. This message is copied from AutoGen
    DEFAULT_SYSTEM_MESSAGE = """You're a retrieve augmented chatbot. You answer user's questions based on your own knowledge and the
        context provided by the user.
        If you can't answer the question with or without the current context, you should reply exactly `UPDATE CONTEXT`.
        You must give as short an answer as possible.

        User's question is: {input_question}

        Context is: {input_context}
    """

    DEFAULT_DESCRIBE = """Summarize provided content according to user's questions and output the summaraization."""

    NAME = "Retrieve_Summarizer"

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
        describe: Optional[str] = DEFAULT_DESCRIBE,
        is_termination_msg: Optional[Callable[[Dict], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "NEVER",
        retrieve_config: Optional[Dict] = None,
        **kwargs,
    ):
        super().__init__(
            name=self.NAME,
            memory=memory,
            describe=describe,
            system_message=self.DEFAULT_SYSTEM_MESSAGE,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
            retrieve_config = retrieve_config
            **kwargs,
        )

        # Add parameters in retrieve_config
        self._retrieve_config = {} if retrieve_config is None else retrieve_config
        self._docs_path = self._retrieve_config.get("docs_path", None)
        if "docs_path" not in self._retrieve_config:
            logger.warning(
                "docs_path is not provided in retrieve_config. "
                "Set docs_path to None to suppress this warning."
            )
        self._model = self._retrieve_config.get("model", "gpt-4")
        self._max_tokens = self.get_max_tokens(self._model)
        self._chunk_token_size = int(self._retrieve_config.get("chunk_token_size", self._max_tokens * 0.4))
        self._chunk_mode = self._retrieve_config.get("chunk_mode", "multi_lines")
        self._must_break_at_empty_line = self._retrieve_config.get("must_break_at_empty_line", True)
        # self.customized_prompt = self._retrieve_config.get("customized_prompt", None)
        # self.customized_answer_prefix = self._retrieve_config.get("customized_answer_prefix", "").upper()
        # self.update_context = self._retrieve_config.get("update_context", True)
        self._get_or_create = self._retrieve_config.get("get_or_create", False) if self._docs_path is not None else True
        # self.custom_token_count_function = self._retrieve_config.get("custom_token_count_function", count_token)
        # self.custom_text_split_function = self._retrieve_config.get("custom_text_split_function", None)
        self._custom_text_types = self._retrieve_config.get("custom_text_types", TEXT_FORMATS)
        # self._recursive = self._retrieve_config.get("recursive", True)
        # self._context_max_tokens = self._max_tokens * 0.8
        self._collection = True if self._docs_path is None else False  # whether the collection is created
        self._doc_idx = -1  # the index of the current used doc
        self._results = {}  # the results of the current query
        self._intermediate_answers = set()  # the intermediate answers
        self._doc_contents = []  # the contents of the current used doc
        self._doc_ids = []  # the ids of the current used doc
        self._search_string = ""  # the search string used in the current query
        # update the termination message function
        self._is_termination_msg = (
            self._is_termination_msg_retrievechat if is_termination_msg is None else is_termination_msg
        )

        # Register_reply
        self.register_reply(Agent, RetrieveSummaryAssistantAgent.generate_summary_reply)
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

    def _reset(self, intermediate=False):
        self._doc_idx = -1  # the index of the current used doc
        self._results = {}  # the results of the current query
        if not intermediate:
            self._intermediate_answers = set()  # the intermediate answers
            self._doc_contents = []  # the contents of the current used doc
            self._doc_ids = []  # the ids of the current used doc

    def _generate_message(self, doc_contents):
        if not doc_contents:
            print(colored("No more context, will terminate.", "green"), flush=True)
            return "TERMINATE"
        message = self.DEFAULT_SYSTEM_MESSAGE.format(input_question=self.problem, input_context=doc_contents)
        return message

    async def generate_retrieve_summary_reply(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply with summary."""

        # TODO: 
        # 1. Extract User Question from massage
        # 2. Extract file / webpage list from message
        # 3. Summarize each chunk
        # 4. Combine summarization of each chunk
        summary_result = ""
        response_success = True
        view = None
        content = None
        if message is None:
            # Answer failed, turn on automatic repair
            fail_reason += f"Nothing is summarized, please check your input."
            response_success = False
        else:
            try:
                vis_client = ApiCall()
                content = summary_result
                view = summary_result
            except Exception as e:
                fail_reason += f"Return summarization error, {str(e)}"
                response_success = False

        if not response_success:
            content = fail_reason
        return True, {
            "is_exe_success": response_success,
            "content": content,
            "view": view,
        }

    def retrieve_docs(self, problem: str, n_results: int = 20, search_string: str = ""):
        """Retrieve docs based on the given problem and assign the results to the class property `_results`.
        In case you want to customize the retrieval process, such as using a different vector db whose APIs are not
        compatible with chromadb or filter results with metadata, you can override this function. Just keep the current
        parameters and add your own parameters with default values, and keep the results in below type.

        Type of the results: Dict[str, List[List[Any]]], should have keys "ids" and "documents", "ids" for the ids of
        the retrieved docs and "documents" for the contents of the retrieved docs. Any other keys are optional. Refer
        to `chromadb.api.types.QueryResult` as an example.
            ids: List[string]
            documents: List[List[string]]

        Args:
            problem (str): the problem to be solved.
            n_results (int): the number of results to be retrieved. Default is 20.
            search_string (str): only docs that contain an exact match of this string will be retrieved. Default is "".
        """
        if not self._collection or not self._get_or_create:
            print("Trying to create collection.")
            self._client = create_vector_db_from_dir(
                dir_path=self._docs_path,
                max_tokens=self._chunk_token_size,
                client=self._client,
                collection_name=self._collection_name,
                chunk_mode=self._chunk_mode,
                must_break_at_empty_line=self._must_break_at_empty_line,
                embedding_model=self._embedding_model,
                get_or_create=self._get_or_create,
                embedding_function=self._embedding_function,
                custom_text_split_function=self.custom_text_split_function,
                custom_text_types=self._custom_text_types,
                recursive=self._recursive,
                extra_docs=self._extra_docs,
            )
            self._collection = True
            self._get_or_create = True

        results = query_vector_db(
            query_texts=[problem],
            n_results=n_results,
            search_string=search_string,
            client=self._client,
            collection_name=self._collection_name,
            embedding_model=self._embedding_model,
            embedding_function=self._embedding_function,
        )
        self._search_string = search_string
        self._results = results
        print("doc_ids: ", results["ids"])

    def _get_files_from_dir(self, dir_path: Union[str, List[str]], types: list = TEXT_FORMATS, recursive: bool = True):
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
                    files += glob.glob(os.path.join(dir_path, f"**/*.{type}"), recursive=True)
                else:
                    files += glob.glob(os.path.join(dir_path, f"*.{type}"), recursive=False)
        else:
            logger.error(f"Directory {dir_path} does not exist.")
            raise ValueError(f"Directory {dir_path} does not exist.")
        return files

    def _get_file_from_url(url: str, save_path: str = None):
        """Download a file from a URL."""
        if save_path is None:
            os.makedirs("/tmp/DB-GPT/retrieved_urls", exist_ok=True)
            save_path = os.path.join("/tmp/DB-GPT/retrieved_urls", os.path.basename(url))
        else:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return save_path


    def _is_url(string: str):
        """Return True if the string is a valid URL."""
        try:
            result = urlparse(string)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

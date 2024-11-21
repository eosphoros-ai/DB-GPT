"""Text splitter module for splitting text into chunks."""

import copy
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Iterable, List, Optional, TypedDict, Union, cast

from dbgpt.core import Chunk, Document
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


class TextSplitter(ABC):
    """Interface for splitting text into chunks.

    Refer to `Langchain Text Splitter <https://github.com/langchain-ai/langchain/blob/
    master/libs/langchain/langchain/text_splitter.py>`_
    """

    outgoing_edges = 1

    def __init__(
        self,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
        filters=None,
        separator: str = "",
    ):
        """Create a new TextSplitter."""
        if filters is None:
            filters = []
        if chunk_overlap > chunk_size:
            raise ValueError(
                f"Got a larger chunk overlap ({chunk_overlap}) than chunk size "
                f"({chunk_size}), should be smaller."
            )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._length_function = length_function
        self._filter = filters
        self._separator = separator

    @abstractmethod
    def split_text(self, text: str, **kwargs) -> List[str]:
        """Split text into multiple components."""

    def create_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        separator: Optional[str] = None,
        **kwargs,
    ) -> List[Chunk]:
        """Create documents from a list of texts."""
        _metadatas = metadatas or [{}] * len(texts)
        chunks = []
        for i, text in enumerate(texts):
            if _metadatas[i].get("type") == "excel":
                table_chunk = Chunk(content=text, metadata=copy.deepcopy(_metadatas[i]))
                chunks.append(table_chunk)
            else:
                for chunk in self.split_text(text, separator=separator, **kwargs):
                    new_doc = Chunk(
                        content=chunk, metadata=copy.deepcopy(_metadatas[i])
                    )
                    chunks.append(new_doc)
        return chunks

    def split_documents(self, documents: Iterable[Document], **kwargs) -> List[Chunk]:
        """Split documents."""
        texts = []
        metadatas = []
        for doc in documents:
            # Iterable just supports one iteration
            texts.append(doc.content)
            metadatas.append(doc.metadata)
        return self.create_documents(texts, metadatas, **kwargs)

    def _join_docs(self, docs: List[str], separator: str, **kwargs) -> Optional[str]:
        text = separator.join(docs)
        text = text.strip()
        if text == "":
            return None
        else:
            return text

    def _merge_splits(
        self,
        splits: Iterable[str | dict],
        separator: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> List[str]:
        # We now want to combine these smaller pieces into medium size
        # chunks to send to the LLM.
        if chunk_size is None:
            chunk_size = self._chunk_size
        if chunk_overlap is None:
            chunk_overlap = self._chunk_overlap
        if separator is None:
            separator = self._separator
        separator_len = self._length_function(separator)

        docs = []
        current_doc: List[str] = []
        total = 0
        for s in splits:
            d = cast(str, s)
            _len = self._length_function(d)
            if (
                total + _len + (separator_len if len(current_doc) > 0 else 0)
                > chunk_size
            ):
                if total > chunk_size:
                    logger.warning(
                        f"Created a chunk of size {total}, "
                        f"which is longer than the specified {chunk_size}"
                    )
                if len(current_doc) > 0:
                    doc = self._join_docs(current_doc, separator)
                    if doc is not None:
                        docs.append(doc)
                    # Keep on popping if:
                    # - we have a larger chunk than in the chunk overlap
                    # - or if we still have any chunks and the length is long
                    while total > chunk_overlap or (
                        total + _len + (separator_len if len(current_doc) > 0 else 0)
                        > chunk_size
                        and total > 0
                    ):
                        total -= self._length_function(current_doc[0]) + (
                            separator_len if len(current_doc) > 1 else 0
                        )
                        current_doc = current_doc[1:]
            current_doc.append(d)
            total += _len + (separator_len if len(current_doc) > 1 else 0)
        doc = self._join_docs(current_doc, separator)
        if doc is not None:
            docs.append(doc)
        return docs

    def clean(self, documents: List[dict], filters: List[str]):
        """Clean the documents."""
        for special_character in filters:
            for doc in documents:
                doc["content"] = doc["content"].replace(special_character, "")
        return documents

    def run(  # type: ignore
        self,
        documents: Union[dict, List[dict]],
        meta: Optional[Union[Dict[str, str], List[Dict[str, str]]]] = None,
        separator: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        filters: Optional[List[str]] = None,
    ):
        """Run the text splitter."""
        if separator is None:
            separator = self._separator
        if chunk_size is None:
            chunk_size = self._chunk_size
        if chunk_overlap is None:
            chunk_overlap = self._chunk_overlap
        if filters is None:
            filters = self._filter
        ret = []
        if type(documents) == dict:  # single document
            text_splits = self.split_text(
                documents["content"],
                separator=separator,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            for i, txt in enumerate(text_splits):
                doc = copy.deepcopy(documents)
                doc["content"] = txt

                if "meta" not in doc.keys() or doc["meta"] is None:
                    doc["meta"] = {}

                doc["meta"]["_split_id"] = i
                ret.append(doc)

        elif type(documents) == list:  # list document
            for document in documents:
                text_splits = self.split_text(
                    document["content"],
                    separator=separator,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                for i, txt in enumerate(text_splits):
                    doc = copy.deepcopy(document)
                    doc["content"] = txt

                    if "meta" not in doc.keys() or doc["meta"] is None:
                        doc["meta"] = {}

                    doc["meta"]["_split_id"] = i
                    ret.append(doc)
        if filters is not None and len(filters) > 0:
            ret = self.clean(ret, filters)
        result = {"documents": ret}
        return result, "output_1"


@register_resource(
    _("Character Text Splitter"),
    "character_text_splitter",
    category=ResourceCategory.RAG,
    parameters=[
        Parameter.build_from(
            _("Separator"),
            "separator",
            str,
            description=_("Separator to split the text."),
            optional=True,
            default="\n\n",
        ),
    ],
    description="Split text by characters.",
)
class CharacterTextSplitter(TextSplitter):
    """Implementation of splitting text that looks at characters.

    Refer to `Langchain Test Splitter <https://github.com/langchain-ai/langchain/blob/
    master/libs/langchain/langchain/text_splitter.py>`_
    """

    def __init__(self, separator: str = "\n\n", filters=None, **kwargs: Any):
        """Create a new TextSplitter."""
        super().__init__(**kwargs)
        if filters is None:
            filters = []
        self._separator = separator
        self._filter = filters

    def split_text(
        self, text: str, separator: Optional[str] = None, **kwargs
    ) -> List[str]:
        """Split incoming text and return chunks."""
        # First we naively split the large input into a bunch of smaller ones.
        if separator is None:
            separator = self._separator
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)
        return self._merge_splits(splits, separator, **kwargs)


@register_resource(
    _("Recursive Character Text Splitter"),
    "recursive_character_text_splitter",
    category=ResourceCategory.RAG,
    parameters=[
        # TODO: Support list of separators
        # Parameter.build_from(
        #     "Separators",
        #     "separators",
        #     List[str],
        #     description="List of separators to split the text.",
        #     optional=True,
        #     default=["###", "\n", " ", ""],
        # ),
    ],
    description=_("Split text by characters recursively."),
)
class RecursiveCharacterTextSplitter(TextSplitter):
    """Implementation of splitting text that looks at characters.

    Recursively tries to split by different characters to find one
    that works.

    Refer to `Langchain Test Splitter <https://github.com/langchain-ai/langchain/blob/
    master/libs/langchain/langchain/text_splitter.py>`_
    """

    def __init__(self, separators: Optional[List[str]] = None, **kwargs: Any):
        """Create a new TextSplitter."""
        super().__init__(**kwargs)
        self._separators = separators or ["###", "\n", " ", ""]

    def split_text(
        self, text: str, separator: Optional[str] = None, **kwargs
    ) -> List[str]:
        """Split incoming text and return chunks."""
        final_chunks = []
        # Get appropriate separator to use
        separator = self._separators[-1]
        for _s in self._separators:
            if _s == "":
                separator = _s
                break
            if _s in text:
                separator = _s
                break
        # Now that we have the separator, split the text
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)
        # Now go merging things, recursively splitting longer texts.
        _good_splits = []
        for s in splits:
            if self._length_function(s) < self._chunk_size:
                _good_splits.append(s)
            else:
                if _good_splits:
                    merged_text = self._merge_splits(
                        _good_splits,
                        separator,
                        chunk_size=kwargs.get("chunk_size", None),
                        chunk_overlap=kwargs.get("chunk_overlap", None),
                    )
                    final_chunks.extend(merged_text)
                    _good_splits = []
                other_info = self.split_text(s)
                final_chunks.extend(other_info)
        if _good_splits:
            merged_text = self._merge_splits(
                _good_splits,
                separator,
                chunk_size=kwargs.get("chunk_size", None),
                chunk_overlap=kwargs.get("chunk_overlap", None),
            )
            final_chunks.extend(merged_text)
        return final_chunks


@register_resource(
    _("Spacy Text Splitter"),
    "spacy_text_splitter",
    category=ResourceCategory.RAG,
    parameters=[
        Parameter.build_from(
            _("Pipeline"),
            "pipeline",
            str,
            description=_("Spacy pipeline to use for tokenization."),
            optional=True,
            default="zh_core_web_sm",
        ),
    ],
    description=_("Split text by sentences using Spacy."),
)
class SpacyTextSplitter(TextSplitter):
    """Implementation of splitting text that looks at sentences using Spacy.

    Refer to `Langchain Test Splitter <https://github.com/langchain-ai/langchain/blob/
    master/libs/langchain/langchain/text_splitter.py>`_
    """

    def __init__(self, pipeline: str = "zh_core_web_sm", **kwargs: Any) -> None:
        """Initialize the spacy text splitter."""
        super().__init__(**kwargs)
        try:
            import spacy
        except ImportError:
            raise ImportError(
                "Spacy is not installed, please install it with `pip install spacy`."
            )
        try:
            self._tokenizer = spacy.load(pipeline)
        except Exception:
            spacy.cli.download(pipeline)
            self._tokenizer = spacy.load(pipeline)

    def split_text(
        self, text: str, separator: Optional[str] = None, **kwargs
    ) -> List[str]:
        """Split incoming text and return chunks."""
        if len(text) > 1000000:
            self._tokenizer.max_length = len(text) + 100
        splits = (str(s) for s in self._tokenizer(text).sents)
        return self._merge_splits(splits, separator, **kwargs)


class HeaderType(TypedDict):
    """Header type as typed dict."""

    level: int
    name: str
    data: str


class LineType(TypedDict):
    """Line type as typed dict."""

    metadata: Dict[str, str]
    content: str


@register_resource(
    _("Markdown Header Text Splitter"),
    "markdown_header_text_splitter",
    category=ResourceCategory.RAG,
    parameters=[
        Parameter.build_from(
            _("Return Each Line"),
            "return_each_line",
            bool,
            description=_("Return each line with associated headers."),
            optional=True,
            default=False,
        ),
        Parameter.build_from(
            _("Chunk Size"),
            "chunk_size",
            int,
            description=_("Size of each chunk."),
            optional=True,
            default=4000,
        ),
        Parameter.build_from(
            _("Chunk Overlap"),
            "chunk_overlap",
            int,
            description=_("Overlap between chunks."),
            optional=True,
            default=200,
        ),
        Parameter.build_from(
            _("Separator"),
            "separator",
            str,
            description=_("Separator to split the text."),
            optional=True,
            default="\n",
        ),
    ],
    description=_("Split markdown text by headers."),
)
class MarkdownHeaderTextSplitter(TextSplitter):
    """Implementation of splitting markdown files based on specified headers.

    Refer to `Langchain Text Splitter <https://github.com/langchain-ai/langchain/blob/
    master/libs/langchain/langchain/text_splitter.py>`_
    """

    outgoing_edges = 1

    def __init__(
        self,
        headers_to_split_on=None,
        return_each_line: bool = False,
        filters=None,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
        separator="\n",
    ):
        """Create a new MarkdownHeaderTextSplitter.

        Args:
            headers_to_split_on: Headers we want to track
            return_each_line: Return each line w/ associated headers
        """
        # Output line-by-line or aggregated into chunks w/ common headers
        if headers_to_split_on is None:
            headers_to_split_on = [
                ("#", "Header1"),
                ("##", "Header2"),
                ("###", "Header3"),
                ("####", "Header4"),
                ("#####", "Header5"),
                ("######", "Header6"),
            ]
        if filters is None:
            filters = []
        self.return_each_line = return_each_line
        self._chunk_size = chunk_size
        # Given the headers we want to split on,
        # (e.g., "#, ##, etc") order by length
        self.headers_to_split_on = sorted(
            headers_to_split_on, key=lambda split: len(split[0]), reverse=True
        )
        self._filter = filters
        self._length_function = length_function
        self._separator = separator
        self._chunk_overlap = chunk_overlap

    def create_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        separator: Optional[str] = None,
        **kwargs,
    ) -> List[Chunk]:
        """Create documents from a list of texts."""
        _metadatas = metadatas or [{}] * len(texts)
        chunks = []
        for i, text in enumerate(texts):
            if _metadatas[i].get("type") == "excel":
                table_chunk = Chunk(content=text, metadata=copy.deepcopy(_metadatas[i]))
                chunks.append(table_chunk)
            else:
                for chunk in self.split_text(text, separator, **kwargs):
                    metadata = chunk.metadata or {}
                    metadata.update(_metadatas[i])
                    new_doc = Chunk(content=chunk.content, metadata=metadata)
                    chunks.append(new_doc)
        return chunks

    def aggregate_lines_to_chunks(self, lines: List[LineType]) -> List[Chunk]:
        """Aggregate lines into chunks based on common metadata.

        Args:
            lines: Line of text / associated header metadata
        """
        aggregated_chunks: List[LineType] = []

        for line in lines:
            if (
                aggregated_chunks
                and aggregated_chunks[-1]["metadata"] == line["metadata"]
            ):
                # If the last line in the aggregated list
                # has the same metadata as the current line,
                # append the current content to the last lines's content
                aggregated_chunks[-1]["content"] += "  \n" + line["content"]
            else:
                # Otherwise, append the current line to the aggregated list
                subtitles = "-".join((list(line["metadata"].values())))
                line["content"] = f'"{subtitles}": ' + line["content"]
                aggregated_chunks.append(line)

        return [
            Chunk(content=chunk["content"], metadata=chunk["metadata"])
            for chunk in aggregated_chunks
        ]

    def split_text(  # type: ignore
        self,
        text: str,
        separator: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        **kwargs,
    ) -> List[Chunk]:
        """Split incoming text and return chunks.

        Args:
            text(str): The input text
            separator(str): The separator to use for splitting the text
            chunk_size(int): The size of each chunk
            chunk_overlap(int): The overlap between chunks
        """
        if separator is None:
            separator = self._separator
        if chunk_size is None:
            chunk_size = self._chunk_size
        if chunk_overlap is None:
            chunk_overlap = self._chunk_overlap

        # Split the input text by newline character ("\n").
        lines = text.split(separator)
        # Final output
        lines_with_metadata: List[LineType] = []
        # Content and metadata of the chunk currently being processed
        current_content: List[str] = []
        current_metadata: Dict[str, str] = {}
        # Keep track of the nested header structure
        # header_stack: List[Dict[str, Union[int, str]]] = []
        header_stack: List[HeaderType] = []
        initial_metadata: Dict[str, str] = {}
        # Determine whether a line is within a markdown code block.
        in_code_block = False
        for line in lines:
            stripped_line = line.strip()
            # A code frame starts with "```"
            with_code_frame = stripped_line.startswith("```") and (
                stripped_line != "```"
            )
            if (not in_code_block) and with_code_frame:
                in_code_block = True
            # Check each line against each of the header types (e.g., #, ##)
            for sep, name in self.headers_to_split_on:
                # Check if line starts with a header that we intend to split on
                if (
                    (not in_code_block)
                    and stripped_line.startswith(sep)
                    and (
                        # Header with no text OR header is followed by space
                        # Both are valid conditions that sep is being used a header
                        len(stripped_line) == len(sep)
                        or stripped_line[len(sep)] == " "
                    )
                ):
                    # Ensure we are tracking the header as metadata
                    if name is not None:
                        # Get the current header level
                        current_header_level = sep.count("#")

                        # Pop out headers of lower or same level from the stack
                        while (
                            header_stack
                            and header_stack[-1]["level"] >= current_header_level
                        ):
                            # We have encountered a new header
                            # at the same or higher level
                            popped_header = header_stack.pop()
                            # Clear the metadata for the
                            # popped header in initial_metadata
                            if popped_header["name"] in initial_metadata:
                                initial_metadata.pop(popped_header["name"])

                        # Push the current header to the stack
                        header: HeaderType = {
                            "level": current_header_level,
                            "name": name,
                            "data": stripped_line[len(sep) :].strip(),
                        }
                        header_stack.append(header)
                        # Update initial_metadata with the current header
                        initial_metadata[name] = header["data"]

                    # Add the previous line to the lines_with_metadata
                    # only if current_content is not empty
                    if current_content:
                        lines_with_metadata.append(
                            {
                                "content": separator.join(current_content),
                                "metadata": current_metadata.copy(),
                            }
                        )
                        current_content.clear()

                    break
            else:
                if stripped_line:
                    current_content.append(stripped_line)
                elif current_content:
                    lines_with_metadata.append(
                        {
                            "content": separator.join(current_content),
                            "metadata": current_metadata.copy(),
                        }
                    )
                    current_content.clear()

            # Code block ends
            if in_code_block and stripped_line == "```":
                in_code_block = False

            current_metadata = initial_metadata.copy()
        if current_content:
            lines_with_metadata.append(
                {
                    "content": separator.join(current_content),
                    "metadata": current_metadata,
                }
            )
        # lines_with_metadata has each line with associated header metadata
        # aggregate these into chunks based on common metadata
        if not self.return_each_line:
            return self.aggregate_lines_to_chunks(lines_with_metadata)
        else:
            return [
                Document(content=chunk["content"], metadata=chunk["metadata"])
                for chunk in lines_with_metadata
            ]

    def clean(self, documents: List[dict], filters: Optional[List[str]] = None):
        """Clean the documents."""
        if filters is None:
            filters = self._filter
        for special_character in filters:
            for doc in documents:
                doc["content"] = doc["content"].replace(special_character, "")
        return documents

    def _join_docs(self, docs: List[str], separator: str, **kwargs) -> Optional[str]:
        text = separator.join(docs)
        text = text.strip()
        if text == "":
            return None
        else:
            return text

    def _merge_splits(
        self,
        documents: Iterable[str | dict],
        separator: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ) -> List[str]:
        # We now want to combine these smaller pieces into medium size
        # chunks to send to the LLM.
        if chunk_size is None:
            chunk_size = self._chunk_size
        if chunk_overlap is None:
            chunk_overlap = self._chunk_overlap
        if separator is None:
            separator = self._separator
        separator_len = self._length_function(separator)

        docs = []
        current_doc: List[str] = []
        total = 0
        for _doc in documents:
            dict_doc = cast(dict, _doc)
            if dict_doc["metadata"] != {}:
                head = sorted(
                    dict_doc["metadata"].items(), key=lambda x: x[0], reverse=True
                )[0][1]
                d = head + separator + dict_doc["page_content"]
            else:
                d = dict_doc["page_content"]
            _len = self._length_function(d)
            if (
                total + _len + (separator_len if len(current_doc) > 0 else 0)
                > chunk_size
            ):
                if total > chunk_size:
                    logger.warning(
                        f"Created a chunk of size {total}, "
                        f"which is longer than the specified {chunk_size}"
                    )
                if len(current_doc) > 0:
                    doc = self._join_docs(current_doc, separator)
                    if doc is not None:
                        docs.append(doc)
                    # Keep on popping if:
                    # - we have a larger chunk than in the chunk overlap
                    # - or if we still have any chunks and the length is long
                    while total > chunk_overlap or (
                        total + _len + (separator_len if len(current_doc) > 0 else 0)
                        > chunk_size
                        and total > 0
                    ):
                        total -= self._length_function(current_doc[0]) + (
                            separator_len if len(current_doc) > 1 else 0
                        )
                        current_doc = current_doc[1:]
            current_doc.append(d)
            total += _len + (separator_len if len(current_doc) > 1 else 0)
        doc = self._join_docs(current_doc, separator)
        if doc is not None:
            docs.append(doc)
        return docs

    def run(
        self,
        documents: Union[dict, List[dict]],
        meta: Optional[Union[Dict[str, str], List[Dict[str, str]]]] = None,
        separator: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        filters: Optional[List[str]] = None,
    ):
        """Run the text splitter."""
        if filters is None:
            filters = self._filter
        if chunk_size is None:
            chunk_size = self._chunk_size
        if chunk_overlap is None:
            chunk_overlap = self._chunk_overlap
        if separator is None:
            separator = self._separator
        ret = []
        if type(documents) == list:
            for document in documents:
                text_splits = self.split_text(
                    document["content"], separator, chunk_size, chunk_overlap
                )
                for i, txt in enumerate(text_splits):
                    doc = {"content": txt}

                    if "meta" not in doc.keys() or doc["meta"] is None:
                        doc["meta"] = {}  # type: ignore

                    doc["meta"]["_split_id"] = i
                    ret.append(doc)
        elif type(documents) == dict:
            text_splits = self.split_text(
                documents["content"], separator, chunk_size, chunk_overlap
            )
            for i, txt in enumerate(text_splits):
                doc = {"content": txt}

                if "meta" not in doc.keys() or doc["meta"] is None:
                    doc["meta"] = {}  # type: ignore

                doc["meta"]["_split_id"] = i
                ret.append(doc)
        if filters is None:
            filters = self._filter
        if filters is not None and len(filters) > 0:
            ret = self.clean(ret, filters)
        result = {"documents": ret}
        return result, "output_1"


class ParagraphTextSplitter(CharacterTextSplitter):
    """Implementation of splitting text that looks at paragraphs."""

    def __init__(
        self,
        separator="\n",
        chunk_size: int = 0,
        chunk_overlap: int = 0,
    ):
        """Create a new ParagraphTextSplitter."""
        self._separator = separator
        if self._separator is None:
            self._separator = "\n"
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._is_paragraph = chunk_overlap

    def split_text(
        self, text: str, separator: Optional[str] = "\n", **kwargs
    ) -> List[str]:
        """Split incoming text and return chunks."""
        paragraphs = text.strip().split(self._separator)
        paragraphs = [p.strip() for p in paragraphs if p.strip() != ""]
        return paragraphs


@register_resource(
    _("Separator Text Splitter"),
    "separator_text_splitter",
    category=ResourceCategory.RAG,
    parameters=[
        Parameter.build_from(
            _("Separator"),
            "separator",
            str,
            description=_("Separator to split the text."),
            optional=True,
            default="\\n",
        ),
    ],
    description=_("Split text by separator."),
)
class SeparatorTextSplitter(CharacterTextSplitter):
    """The SeparatorTextSplitter class."""

    def __init__(self, separator: str = "\n", filters=None, **kwargs: Any):
        """Create a new TextSplitter."""
        if filters is None:
            filters = []
        self._merge = kwargs.pop("enable_merge") or False
        super().__init__(**kwargs)
        self._separator = separator
        self._filter = filters

    def split_text(
        self, text: str, separator: Optional[str] = None, **kwargs
    ) -> List[str]:
        """Split incoming text and return chunks."""
        if separator is None:
            separator = self._separator
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)
        if self._merge:
            return self._merge_splits(splits, separator, chunk_overlap=0, **kwargs)
        return list(filter(None, text.split(separator)))


@register_resource(
    _("Page Text Splitter"),
    "page_text_splitter",
    category=ResourceCategory.RAG,
    parameters=[
        Parameter.build_from(
            _("Separator"),
            "separator",
            str,
            description=_("Separator to split the text."),
            optional=True,
            default="\n\n",
        ),
    ],
    description=_("Split text by page."),
)
class PageTextSplitter(TextSplitter):
    """The PageTextSplitter class."""

    def __init__(self, separator: str = "\n\n", filters=None, **kwargs: Any):
        """Create a new TextSplitter."""
        super().__init__(**kwargs)
        if filters is None:
            filters = []
        self._separator = separator
        self._filter = filters

    def split_text(
        self, text: str, separator: Optional[str] = None, **kwargs
    ) -> List[str]:
        """Split incoming text and return chunks."""
        return [text]

    def create_documents(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        separator: Optional[str] = None,
        **kwargs,
    ) -> List[Chunk]:
        """Create documents from a list of texts."""
        _metadatas = metadatas or [{}] * len(texts)
        chunks = []
        for i, text in enumerate(texts):
            new_doc = Chunk(content=text, metadata=copy.deepcopy(_metadatas[i]))
            chunks.append(new_doc)
        return chunks

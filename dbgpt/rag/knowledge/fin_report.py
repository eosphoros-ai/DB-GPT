"""FinReport Knowledge."""
import json
import logging
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

from dbgpt.core import Document
from dbgpt.rag.knowledge.base import (
    ChunkStrategy,
    DocumentType,
    Knowledge,
    KnowledgeType,
)

logger = logging.getLogger()


class FinReportKnowledge(Knowledge):
    """FinReport Knowledge."""

    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: KnowledgeType = KnowledgeType.FIN_REPORT,
        loader: Optional[Any] = None,
        language: Optional[str] = "zh",
        metadata: Optional[Dict[str, Union[str, List[str]]]] = None,
        tmp_dir_path: str = "./tmp",
        **kwargs: Any,
    ) -> None:
        """Create FinReport Knowledge with Knowledge arguments.

        Args:
            file_path(str,  optional): file path
            knowledge_type(KnowledgeType, optional): knowledge type
            loader(Any, optional): loader
            language(str, optional): language
        """
        super().__init__(
            path=file_path,
            knowledge_type=knowledge_type,
            data_loader=loader,
            metadata=metadata,
            **kwargs,
        )
        self.filepath = file_path
        self._report_processor = PDFProcessor(self.filepath)
        self._tmp_dir_path = tmp_dir_path
        self._tmp_txt_path = os.path.join(
            tmp_dir_path + "/txt",
            os.path.basename(file_path).replace(".pdf", ".txt"),  # type: ignore
        )

        self.allrow = 0
        self.last_num = 0
        self._language = language

    def _load(self) -> List[Document]:
        """Load pdf document from loader."""
        if self._loader:
            documents = self._loader.load()
        else:
            self._report_processor.process_pdf()

            documents = [
                Document(content=item[1]["inside"], metadata=item[1])
                for item in list(self._report_processor.all_text.items())
            ]
            return documents
        return [Document.langchain2doc(lc_document) for lc_document in documents]

    @property
    def all_text(self):
        """Get all text from pdf."""
        return self._report_processor.all_text

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """Return support chunk strategy."""
        return [
            ChunkStrategy.CHUNK_BY_PAGE,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        """Return default chunk strategy."""
        return ChunkStrategy.CHUNK_BY_PAGE

    @classmethod
    def type(cls) -> KnowledgeType:
        """Return knowledge type."""
        return KnowledgeType.FIN_REPORT

    @classmethod
    def document_type(cls) -> Any:
        """Return document type."""
        return DocumentType.PDF


class PDFProcessor:
    """PDFProcessor class.

    Reference: https://github.com/MetaGLM/FinGLM
    """

    def __init__(self, filepath):
        """Initialize PDFProcessor class."""
        self.filepath = filepath
        try:
            import pdfplumber  # type: ignore
        except ImportError:
            raise ImportError("Please install pdfplumber first.")
        self.pdf = pdfplumber.open(filepath)
        self.all_text = defaultdict(dict)
        self.allrow = 0
        self.last_num = 0

    def check_lines(self, page, top, buttom):
        """Check lines."""
        lines = page.extract_words()[::]
        text = ""
        last_top = 0
        last_check = 0
        for line in range(len(lines)):
            each_line = lines[line]
            check_re = (
                "(?:。|；|单位：人民币元|金额单位：人民币元|单位：万元|币种：人民币|\d|"
                "报告(?:全文)?(?:（修订版）|（修订稿）|（更正后）)?)$"
            )
            if top == "" and buttom == "":
                if abs(last_top - each_line["top"]) <= 2 or (
                    last_check > 0
                    and (page.height * 0.9 - each_line["top"]) > 0
                    and not re.search(check_re, text)
                ):
                    text = text + each_line["text"]
                else:
                    text = text + "\n" + each_line["text"]
            elif top == "":
                if each_line["top"] > buttom:
                    if abs(last_top - each_line["top"]) <= 2 or (
                        last_check > 0
                        and (page.height * 0.85 - each_line["top"]) > 0
                        and not re.search(check_re, text)
                    ):
                        text = text + each_line["text"]
                    else:
                        text = text + "\n" + each_line["text"]
            else:
                if each_line["top"] < top and each_line["top"] > buttom:
                    if abs(last_top - each_line["top"]) <= 2 or (
                        last_check > 0
                        and (page.height * 0.85 - each_line["top"]) > 0
                        and not re.search(check_re, text)
                    ):
                        text = text + each_line["text"]
                    else:
                        text = text + "\n" + each_line["text"]
            last_top = each_line["top"]
            last_check = each_line["x1"] - page.width * 0.85

        return text

    def drop_empty_cols(self, data):
        """Delete empty column."""
        transposed_data = list(map(list, zip(*data)))
        filtered_data = [
            col for col in transposed_data if not all(cell == "" for cell in col)
        ]
        result = list(map(list, zip(*filtered_data)))
        return result

    def extract_text_and_tables(self, page):
        """Extract text and tables."""
        buttom = 0
        tables = page.find_tables()
        if len(tables) >= 1:
            count = len(tables)
            for table in tables:
                # 处理越界的表格
                if table.bbox[3] < buttom:
                    pass
                else:
                    count -= 1
                    # 处理表格上方的文本
                    top = table.bbox[1]
                    text = self.check_lines(page, top, buttom)
                    text_list = text.split("\n")
                    for _t in range(len(text_list)):
                        self.all_text[self.allrow] = {
                            "page": page.page_number,
                            "allrow": self.allrow,
                            "type": "text",
                            "inside": text_list[_t],
                        }
                        self.allrow += 1

                    # 处理表格
                    buttom = table.bbox[3]
                    new_table = table.extract()
                    r_count = 0
                    for r in range(len(new_table)):
                        row = new_table[r]
                        if row[0] is None:
                            r_count += 1
                            for c in range(len(row)):
                                if row[c] is not None and row[c] not in ["", " "]:
                                    if new_table[r - r_count][c] is None:
                                        new_table[r - r_count][c] = row[c]
                                    else:
                                        new_table[r - r_count][c] += row[c]
                                    new_table[r][c] = None
                        else:
                            r_count = 0

                    end_table = []
                    for row in new_table:
                        if row[0] is not None:
                            cell_list = []
                            cell_check = False
                            for cell in row:
                                if cell is not None:
                                    cell = cell.replace("\n", "")
                                else:
                                    cell = ""
                                if cell != "":
                                    cell_check = True
                                cell_list.append(cell)
                            if cell_check:
                                end_table.append(cell_list)

                    end_table = self.drop_empty_cols(end_table)

                    # # 处理列名为空的情况
                    if len(end_table) > 0:
                        for i in range(len(end_table[0])):
                            if end_table[0][i] == "":
                                if 0 < i < len(end_table[0]) - 1:
                                    # left column name
                                    left_column = end_table[0][i - 1]
                                    # right column name
                                    right_column = end_table[0][i + 1]
                                    # current name = left name + right name
                                    end_table[0][i] = left_column + right_column
                                else:
                                    # 当前列为空且位于首列，赋值为右列名
                                    # 当前列为空且位于末尾列，赋值为左列名
                                    end_table[0][i] = (
                                        end_table[0][i - 1]
                                        if i == len(end_table[0]) - 1
                                        else end_table[0][i + 1]
                                    )

                    # 处理列值为空的情况, 取左边的列
                    for i in range(1, len(end_table)):
                        for j in range(len(end_table[i])):
                            if end_table[i][j] == "":
                                end_table[i][j] = end_table[i][j - 1]

                    for row in end_table:
                        self.all_text[self.allrow] = {
                            "page": page.page_number,
                            "allrow": self.allrow,
                            "type": "excel",
                            "inside": str(row),
                        }
                        # self.all_text[self.allrow] = {'page': page.page_number,
                        # 'allrow': self.allrow, 'type': 'excel',
                        #                               'inside': ' '.join(row)}
                        self.allrow += 1

                    if count == 0:
                        text = self.check_lines(page, "", buttom)
                        text_list = text.split("\n")
                        for _t in range(len(text_list)):
                            self.all_text[self.allrow] = {
                                "page": page.page_number,
                                "allrow": self.allrow,
                                "type": "text",
                                "inside": text_list[_t],
                            }
                            self.allrow += 1

        else:
            text = self.check_lines(page, "", "")
            text_list = text.split("\n")
            for _t in range(len(text_list)):
                self.all_text[self.allrow] = {
                    "page": page.page_number,
                    "allrow": self.allrow,
                    "type": "text",
                    "inside": text_list[_t],
                }
                self.allrow += 1

        first_re = "[^计](?:报告(?:全文)?(?:（修订版）|（修订稿）|（更正后）)?)$"
        end_re = "^(?:\d|\\|\/|第|共|页|-|_| ){1,}"
        if self.last_num == 0:
            try:
                first_text = str(self.all_text[1]["inside"])
                end_text = str(self.all_text[len(self.all_text) - 1]["inside"])
                if re.search(first_re, first_text) and "[" not in end_text:
                    self.all_text[1]["type"] = "页眉"
                    if re.search(end_re, end_text) and "[" not in end_text:
                        self.all_text[len(self.all_text) - 1]["type"] = "页脚"
            except Exception:
                print(page.page_number)
        else:
            try:
                first_text = str(self.all_text[self.last_num + 2]["inside"])
                end_text = str(self.all_text[len(self.all_text) - 1]["inside"])
                if re.search(first_re, first_text) and "[" not in end_text:
                    self.all_text[self.last_num + 2]["type"] = "页眉"
                if re.search(end_re, end_text) and "[" not in end_text:
                    self.all_text[len(self.all_text) - 1]["type"] = "页脚"
            except Exception:
                print(page.page_number)

        self.last_num = len(self.all_text) - 1

    def process_pdf(self):
        """Process pdf."""
        for i in range(len(self.pdf.pages)):
            self.extract_text_and_tables(self.pdf.pages[i])
            logger.info(f"{self.filepath} page {i} extract text success")

    def save_all_text(self, path):
        """Save all text."""
        directory = os.path.dirname(path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        for key in self.all_text.keys():
            with open(path, "a+", encoding="utf-8") as file:
                file.write(json.dumps(self.all_text[key], ensure_ascii=False) + "\n")

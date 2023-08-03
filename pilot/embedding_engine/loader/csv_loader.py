"""Loads a CSV file into a list of documents.

Each document represents one row of the CSV file. Every row is converted into a
key/value pair and outputted to a new line in the document's page_content.

The source for each document loaded from csv is set to the value of the
`file_path` argument for all documents by default.
You can override this by setting the `source_column` argument to the
name of a column in the CSV file.
The source of each document will then be set to the value of the column
with the name specified in `source_column`.

Output Example:
    .. code-block:: txt

        column1: value1
        column2: value2
        column3: value3
"""
from typing import Optional, Dict, List
import csv
from langchain.document_loaders.base import BaseLoader
from langchain.schema import Document


class NewCSVLoader(BaseLoader):
    def __init__(
        self,
        file_path: str,
        source_column: Optional[str] = None,
        csv_args: Optional[Dict] = None,
        encoding: Optional[str] = None,
    ):
        """

        Args:
            file_path: The path to the CSV file.
            source_column: The name of the column in the CSV file to use as the source.
              Optional. Defaults to None.
            csv_args: A dictionary of arguments to pass to the csv.DictReader.
              Optional. Defaults to None.
            encoding: The encoding of the CSV file. Optional. Defaults to None.
        """
        self.file_path = file_path
        self.source_column = source_column
        self.encoding = encoding
        self.csv_args = csv_args or {}

    def load(self) -> List[Document]:
        """Load data into document objects."""

        docs = []
        with open(self.file_path, newline="", encoding=self.encoding) as csvfile:
            csv_reader = csv.DictReader(csvfile, **self.csv_args)  # type: ignore
            for i, row in enumerate(csv_reader):
                strs = []
                for k, v in row.items():
                    if k is None or v is None:
                        continue
                    strs.append(f"{k.strip()}: {v.strip()}")
                content = "\n".join(strs)
                try:
                    source = (
                        row[self.source_column]
                        if self.source_column is not None
                        else self.file_path
                    )
                except KeyError:
                    raise ValueError(
                        f"Source column '{self.source_column}' not found in CSV file."
                    )
                metadata = {"source": source, "row": i}
                doc = Document(page_content=content, metadata=metadata)
                docs.append(doc)

        return docs

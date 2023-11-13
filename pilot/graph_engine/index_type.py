"""IndexStructType class."""

from enum import Enum


class IndexStructType(str, Enum):
    """Index struct type. Identifier for a "type" of index.

    Attributes:
        TREE ("tree"): Tree index. See :ref:`Ref-Indices-Tree` for tree indices.
        LIST ("list"): Summary index. See :ref:`Ref-Indices-List` for summary indices.
        KEYWORD_TABLE ("keyword_table"): Keyword table index. See
            :ref:`Ref-Indices-Table`
            for keyword table indices.
        DICT ("dict"): Faiss Vector Store Index. See
            :ref:`Ref-Indices-VectorStore`
            for more information on the faiss vector store index.
        SIMPLE_DICT ("simple_dict"): Simple Vector Store Index. See
            :ref:`Ref-Indices-VectorStore`
            for more information on the simple vector store index.
        KG ("kg"): Knowledge Graph index.
            See :ref:`Ref-Indices-Knowledge-Graph` for KG indices.
        DOCUMENT_SUMMARY ("document_summary"): Document Summary Index.
            See :ref:`Ref-Indices-Document-Summary` for Summary Indices.

    """

    # TODO: refactor so these are properties on the base class

    NODE = "node"
    TREE = "tree"
    LIST = "list"
    KEYWORD_TABLE = "keyword_table"

    DICT = "dict"
    # simple
    SIMPLE_DICT = "simple_dict"
    # for KG index
    KG = "kg"
    SIMPLE_KG = "simple_kg"
    NEBULAGRAPH = "nebulagraph"
    FALKORDB = "falkordb"

    # EMPTY
    EMPTY = "empty"
    COMPOSITE = "composite"

    DOCUMENT_SUMMARY = "document_summary"

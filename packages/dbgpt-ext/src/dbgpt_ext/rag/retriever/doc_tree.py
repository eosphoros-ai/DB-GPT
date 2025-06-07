"""Tree-based document retriever."""

import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import List, Optional

from dbgpt.core import Document
from dbgpt.rag.retriever import BaseRetriever, DefaultRanker, QueryRewrite, Ranker
from dbgpt.rag.transformer.base import ExtractorBase
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)

RETRIEVER_NAME = "doc_tree_retriever"
TITLE = "title"
HEADER1 = "Header1"
HEADER2 = "Header2"
HEADER3 = "Header3"
HEADER4 = "Header4"
HEADER5 = "Header5"
HEADER6 = "Header6"


class TreeNode:
    """TreeNode class to represent a node in the document tree."""

    def __init__(
        self, node_id: str, level_text: str, level: int, content: Optional[str] = None
    ):
        """Initialize a TreeNode."""
        self.node_id = node_id
        self.level = level  # 0: title, 1: header1, 2: header2, 3: header3
        self.level_text = level_text  # 0: title, 1: header1, 2: header2, 3: header3
        self.children = []
        self.content = content
        self.retriever = RETRIEVER_NAME

    def add_child(self, child_node):
        """Add a child node to the current node."""
        self.children.append(child_node)


class DocTreeIndex:
    def __init__(self):
        """Initialize the document tree index."""
        self.root = TreeNode("root_id", "Root", -1)

    def add_nodes(
        self,
        node_id: str,
        title: str,
        header1: Optional[str] = None,
        header2: Optional[str] = None,
        header3: Optional[str] = None,
        header4: Optional[str] = None,
        header5: Optional[str] = None,
        header6: Optional[str] = None,
        content: Optional[str] = None,
    ):
        """Add nodes to the document tree.

        Args:
            node_id (str): The ID of the node.
            title (str): The title of the document.
            header1 (Optional[str]): The first header.
            header2 (Optional[str]): The second header.
            header3 (Optional[str]): The third header.
            header4 (Optional[str]): The fourth header.
            header5 (Optional[str]): The fifth header.
            header6 (Optional[str]): The sixth header.
            content (Optional[str]): The content of the node.
        """
        # Assuming titles is a dictionary containing title and headers
        title_node = None
        if title:
            title_nodes = self.get_node_by_level(0)
            if not title_nodes:
                # If title already exists, do not add it again
                title_node = TreeNode(node_id, title, 0, content)
                self.root.add_child(title_node)
            else:
                title_node = title_nodes[0]
        current_node = title_node
        headers = [header1, header2, header3, header4, header5, header6]
        for level, header in enumerate(headers, start=1):
            if header:
                header_nodes = self.get_node_by_level_text(header)
                if header_nodes:
                    # If header already exists, do not add it again
                    current_node = header_nodes[0]
                    continue
                new_header_node = TreeNode(node_id, header, level, content)
                current_node.add_child(new_header_node)
                current_node = new_header_node

    def add_nodes_with_content(
        self,
        node_id: str,
        title: str,
        header1: Optional[str] = None,
        header2: Optional[str] = None,
        header3: Optional[str] = None,
        header4: Optional[str] = None,
        header5: Optional[str] = None,
        header6: Optional[str] = None,
    ):
        """Add nodes to the document tree.

        Args:
            node_id (str): The ID of the node.
            title (str): The title of the document.
            header1 (Optional[str]): The first header.
            header2 (Optional[str]): The second header.
            header3 (Optional[str]): The third header.
            header4 (Optional[str]): The fourth header.
            header5 (Optional[str]): The fifth header.
            header6 (Optional[str]): The sixth header.
        """
        # Assuming titles is a dictionary containing title and headers
        title_node = None
        if title:
            title_nodes = self.get_node_by_level(0)
            if not title_nodes:
                # If title already exists, do not add it again
                title_node = TreeNode(node_id, title, 0)
                self.root.add_child(title_node)
            else:
                title_node = title_nodes[0]
        current_node = title_node
        headers = [header1, header2, header3, header4, header5, header6]
        for level, header in enumerate(headers, start=1):
            if header:
                header_nodes = self.get_node_by_level_text(header)
                if header_nodes:
                    # If header already exists, do not add it again
                    current_node = header_nodes[0]
                    continue
                new_header_node = TreeNode(node_id, header, level)
                current_node.add_child(new_header_node)
                current_node = new_header_node

    def get_node_by_level(self, level):
        """Get nodes by level."""
        # Traverse the tree to find nodes at the specified level
        result = []
        self._traverse(self.root, level, result)
        return result

    def get_node_by_level_text(self, content):
        """Get nodes by level."""
        # Traverse the tree to find nodes at the specified level
        result = []
        self._traverse_by_level_text(self.root, content, result)
        return result

    def get_all_children(self, node):
        """get all children of the node."""
        # Get all children of the current node
        result = []
        self._traverse(node, node.level, result)
        return result

    def display_tree(self, node: TreeNode, prefix: Optional[str] = ""):
        """Recursive function to display the directory structure with visual cues."""
        # Print the current node title with prefix
        if node.content:
            print(
                f"{prefix}├── {node.level_text} (node_id: {node.node_id}) "
                f"(content: {node.content})"
            )
        else:
            print(f"{prefix}├── {node.level_text} (node_id: {node.node_id})")

        # Update prefix for children
        new_prefix = prefix + "│   "  # Extend the prefix for child nodes
        for i, child in enumerate(node.children):
            if i == len(node.children) - 1:  # If it's the last child
                new_prefix_child = prefix + "└── "
            else:
                new_prefix_child = new_prefix

            # Recursive call for the next child node
            self.display_tree(child, new_prefix_child)

    def _traverse(self, node, level, result):
        """Traverse the tree to find nodes at the specified level."""
        # If the current node's level matches the specified level, add it to the result
        if node.level == level:
            result.append(node)
        # Recursively traverse child nodes
        for child in node.children:
            self._traverse(child, level, result)

    def _traverse_by_level_text(self, node, level_text, result):
        """Traverse the tree to find nodes at the specified level."""
        # If the current node's level matches the specified level, add it to the result
        if node.level_text == level_text:
            result.append(node)
        # Recursively traverse child nodes
        for child in node.children:
            self._traverse_by_level_text(child, level_text, result)

    def search_keywords(self, node, keyword) -> Optional[TreeNode]:
        # Check if the keyword matches the current node title
        if keyword.lower() == node.level_text.lower():
            logger.info(f"DocTreeIndex Match found in: {node.level_text}")
            return node
        # Recursively search in child nodes
        for child in node.children:
            result = self.search_keywords(child, keyword)
            if result:
                return result
        # Check if the keyword matches any of the child nodes
        # If no match, continue to search in all children
        return None


class DocTreeRetriever(BaseRetriever):
    """Doc Tree retriever."""

    def __init__(
        self,
        docs: List[Document] = None,
        top_k: Optional[int] = 10,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Optional[Ranker] = None,
        keywords_extractor: Optional[ExtractorBase] = None,
        with_content: bool = False,
        show_tree: bool = True,
        executor: Optional[Executor] = None,
    ):
        """Create DocTreeRetriever.

        Args:
            docs (List[Document]): List of documents to initialize the tree with.
            top_k (int): top k
            query_rewrite (Optional[QueryRewrite]): query rewrite
            rerank (Ranker): rerank
            keywords_extractor (Optional[ExtractorBase]): keywords extractor
            with_content: bool: whether to include content
            executor (Optional[Executor]): executor

        Returns:
            DocTreeRetriever: BM25 retriever
        """
        super().__init__()
        self._top_k = top_k
        self._query_rewrite = query_rewrite
        self._rerank = rerank or DefaultRanker(self._top_k)
        self._keywords_extractor = keywords_extractor
        self._with_content = with_content
        self._show_tree = show_tree
        self._tree_indexes = self._initialize_doc_tree(docs)
        self._executor = executor or ThreadPoolExecutor()

    def get_tree_indexes(self):
        """Get the tree indexes."""
        return self._tree_indexes

    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[TreeNode]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        raise NotImplementedError("DocTreeRetriever does not support retrieval.")

    def _retrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[TreeNode]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks with score
        """
        raise NotImplementedError("DocTreeRetriever does not support score retrieval.")

    async def _aretrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[TreeNode]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text.
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        keywords = [query]
        if self._keywords_extractor:
            keywords = await self._keywords_extractor.extract(query)
        all_nodes = []
        for keyword in keywords:
            for tree_index in self._tree_indexes:
                retrieve_node = tree_index.search_keywords(tree_index.root, keyword)
                if retrieve_node:
                    # If a match is found, return the corresponding chunks
                    if self._show_tree:
                        logger.info(
                            f"DocTreeIndex Match found in: {retrieve_node.level_text}"
                        )
                        tree_index.display_tree(retrieve_node)
                    all_nodes.append(retrieve_node)
        return all_nodes

    async def _aretrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[TreeNode]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks with score
        """
        return await self._aretrieve(query, filters)

    def _initialize_doc_tree(self, docs: List[Document]):
        """Initialize the document tree with docs.

        Args:
            docs (List[Document]): List of docs to initialize the tree with.
        """
        tree_indexes = []
        for doc in docs:
            tree_index = DocTreeIndex()
            for chunk in doc.chunks:
                title = chunk.metadata.get("title") or "title"
                if not self._with_content:
                    tree_index.add_nodes(
                        node_id=chunk.chunk_id,
                        title=title,
                        header1=chunk.metadata.get(HEADER1),
                        header2=chunk.metadata.get(HEADER2),
                        header3=chunk.metadata.get(HEADER3),
                        header4=chunk.metadata.get(HEADER4),
                        header5=chunk.metadata.get(HEADER5),
                        header6=chunk.metadata.get(HEADER6),
                    )
                else:
                    tree_index.add_nodes(
                        node_id=chunk.chunk_id,
                        title=title,
                        header1=chunk.metadata.get(HEADER1),
                        header2=chunk.metadata.get(HEADER2),
                        header3=chunk.metadata.get(HEADER3),
                        header4=chunk.metadata.get(HEADER4),
                        header5=chunk.metadata.get(HEADER5),
                        header6=chunk.metadata.get(HEADER6),
                        content=chunk.content,
                    )
            tree_indexes.append(tree_index)
        return tree_indexes

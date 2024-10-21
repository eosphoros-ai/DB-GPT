from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Chunk:
    """
    原始 Markdown 块的数据类。

    Attributes:
        chunk_id: 块的唯一标识符
        content: 块的实际内容
        metadata: 包含块的元数据，如标题层级等
    """

    chunk_id: str
    content: str
    metadata: Dict[str, str]


@dataclass
class ParsedChunk:
    """
    解析后的 Markdown 块的数据类。

    Attributes:
        id: 块的唯一标识符
        title: 块的标题
        directory_keys: 标题层级列表
        level: 当前块的层级
        content: 块的实际内容
        parent_id: 父块的ID
        parent_title: 父块的标题
        type: 块的类型，默认为 "chunk"
        chunk_index: 块在文档中的索引位置
        metadata: 原始元数据
    """

    id: str
    title: str
    directory_keys: List[str]
    level: str
    content: str
    parent_id: Optional[str]
    parent_title: Optional[str]
    type: str = "chunk"
    chunk_index: int = 0
    metadata: Dict[str, str] = None

    def asdict(self) -> Dict:
        """
        将 ParsedChunk 对象转换为字典形式。

        Returns:
            Dict: 包含块所有属性的字典
        """
        return {
            "id": self.id,
            "title": self.title,
            "directory_keys": self.directory_keys,
            "level": self.level,
            "content": self.content,
            "parent_id": self.parent_id,
            "parent_title": self.parent_title,
            "type": self.type,
            "chunk_index": self.chunk_index,
        }


class MarkdownParser:
    """
    Markdown 解析器类，用于处理 markdown 文档的层级结构。
    """

    def parse_chunks(slef, chunks: List[Chunk]):
        """Parse the chunks by anlyzing the markdown chunks."""
        # TODO: Need to refact.
        data = []
        for chunk_index, chunk in enumerate(chunks):
            parent = None
            directory_keys = list(chunk.metadata.keys())[:-1]
            parent_level = directory_keys[-2] if len(directory_keys) > 1 else None
            current_level = directory_keys[-1] if directory_keys else "Header0"

            chunk_data = {
                "id": chunk.chunk_id,
                "title": chunk.metadata.get(current_level, "none_header_chunk"),
                "directory_keys": directory_keys,
                "level": current_level,
                "content": chunk.content,
                "parent_id": None,
                "parent_title": None,
                "type": "chunk",
                "chunk_index": chunk_index,
            }

            # Find the parent chunk
            if parent_level:
                for parent_direct in reversed(directory_keys[:-1]):
                    parent_titile = chunk.metadata.get(parent_direct, None)
                    for n in range(chunk_index - 1, -1, -1):
                        metadata = chunks[n].metadata
                        keys = list(metadata.keys())[:-1]
                        if (
                            metadata
                            and parent_direct == keys[-1]
                            and parent_titile == metadata.get(parent_direct)
                        ):
                            parent = chunks[n]
                            chunk_data["parent_id"] = parent.chunk_id
                            chunk_data["parent_title"] = parent_titile
                            break
                        if chunk_index - n > len(directory_keys):
                            break
                    if chunk_data["parent_id"]:
                        break

            if not chunk_data["parent_id"]:
                chunk_data["parent_id"] = "document"
            data.append(chunk_data)
        return data


# 测试代码和其他部分保持不变


# 测试代码
TEST_MARKDOWN = """# First Section
Some content in first section

## 1.1 Sub Section
Content in 1.1

### 1.1.1 Deep Section
Very deep content

## 1.2 Another Sub
Content in 1.2

# Second Section
Top level again

## 2.1 Sub of Second
Content here

Random content without header
More random content

## 2.2 Last Sub
Final content

# Empty Section
"""


def create_test_chunks():
    """Create test chunks from markdown text."""
    return [
        Chunk("1", "Some content in first section", {"Header1": "First Section"}),
        Chunk(
            "2",
            "Content in 1.1",
            {"Header1": "First Section", "Header2": "1.1 Sub Section"},
        ),
        Chunk(
            "3",
            "Very deep content",
            {
                "Header1": "First Section",
                "Header2": "1.1 Sub Section",
                "Header3": "1.1.1 Deep Section",
            },
        ),
        Chunk(
            "4",
            "Content in 1.2",
            {"Header1": "First Section", "Header2": "1.2 Another Sub"},
        ),
        Chunk("5", "Top level again", {"Header1": "Second Section"}),
        Chunk(
            "6",
            "Content here",
            {"Header1": "Second Section", "Header2": "2.1 Sub of Second"},
        ),
        Chunk("7", "Random content without header\nMore random content", {}),
        Chunk(
            "8",
            "Final content",
            {"Header1": "Second Section", "Header2": "2.2 Last Sub"},
        ),
        Chunk("9", "", {"Header1": "Empty Section"}),
    ]


def test_comprehensive_structure():
    parser = MarkdownParser()
    result = parser.parse_chunks(create_test_chunks())

    # 测试总体结构
    assert len(result) == 9

    # 测试第一层级结构
    first_section = result[0]
    assert first_section["title"] == "First Section"
    assert first_section["parent_id"] == "document"

    # 测试第二层级结构
    sub_section = result[1]
    assert sub_section["title"] == "1.1 Sub Section"
    assert sub_section["parent_id"] == "1"

    # 测试第三层级结构
    deep_section = result[2]
    assert deep_section["title"] == "1.1.1 Deep Section"
    assert deep_section["parent_id"] == "2"

    # 测试平行的第二层级
    another_sub = result[3]
    assert another_sub["title"] == "1.2 Another Sub"
    assert another_sub["parent_id"] == "1"


def test_edge_cases():
    parser = MarkdownParser()
    result = parser.parse_chunks(create_test_chunks())

    # 测试无标题块
    no_header_chunk = result[6]
    assert no_header_chunk["title"] == "none_header_chunk"
    assert no_header_chunk["parent_id"] == "document"

    # 测试空内容块
    empty_section = result[8]
    assert empty_section["title"] == "Empty Section"
    assert empty_section["content"] == ""


def test_parent_child_relationships():
    parser = MarkdownParser()
    result = parser.parse_chunks(create_test_chunks())

    second_section_sub = result[5]
    assert second_section_sub["parent_id"] == "5"

    last_sub = result[7]
    assert last_sub["parent_id"] == "5"


def test_metadata_structure():
    parser = MarkdownParser()
    result = parser.parse_chunks(create_test_chunks())

    deep_section = result[2]
    assert len(deep_section["directory_keys"]) == 3
    assert "Header1" in deep_section["directory_keys"]
    assert "Header2" in deep_section["directory_keys"]
    assert "Header3" in deep_section["directory_keys"]


if __name__ == "__main__":
    # 运行所有测试
    test_comprehensive_structure()
    test_edge_cases()
    test_parent_child_relationships()
    test_metadata_structure()
    print("All tests passed!")

Markdown
==================================
markdown embedding can import md text into a vector knowledge base. The entire embedding process includes the read (loading data), data_process (data processing), and index_to_store (embedding to the vector database) methods.

inheriting the SourceEmbedding

```
class  MarkdownEmbedding(SourceEmbedding):
    """pdf embedding for read markdown document."""

    def __init__(self, file_path, vector_store_config, text_splitter):
        """Initialize with markdown path."""
        super().__init__(file_path, vector_store_config, text_splitter)
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.text_splitter = text_splitter or Nore
```
implement read() and data_process()
read() method allows you to read data and split data into chunk

```
@register
    def read(self):
        """Load from markdown path."""
        loader = EncodeTextLoader(self.file_path)
        if self.text_splitter is None:
            try:
                self.text_splitter = SpacyTextSplitter(
                    pipeline="zh_core_web_sm",
                    chunk_size=100,
                    chunk_overlap=100,
                )
            except Exception:
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=100, chunk_overlap=50
                )

        return loader.load_and_split(self.text_splitter)
```

data_process() method allows you to pre processing your ways
```
@register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            documents[i].page_content = d.page_content.replace("\n", "")
            i += 1
        return documents
```

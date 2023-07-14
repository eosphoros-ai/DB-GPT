String
==================================
string embedding can import a long raw text into a vector knowledge base. The entire embedding process includes the read (loading data), data_process (data processing), and index_to_store (embedding to the vector database) methods.

inheriting the SourceEmbedding
```
class StringEmbedding(SourceEmbedding):
    """string embedding for read string document."""

    def __init__(
        self,
        file_path,
        vector_store_config,
        text_splitter: Optional[TextSplitter] = None,
    ):
        """Initialize raw text word path."""
        super().__init__(file_path=file_path, vector_store_config=vector_store_config)
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.text_splitter = text_splitter or None
```

implement read() and data_process()
read() method allows you to read data and split data into chunk
```
@register
    def read(self):
        """Load from String path."""
        metadata = {"source": "raw text"}
        return [Document(page_content=self.file_path, metadata=metadata)]
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

PPTEmbedding
==================================
ppt embedding can import ppt text into a vector knowledge base. The entire embedding process includes the read (loading data), data_process (data processing), and index_to_store (embedding to the vector database) methods.

inheriting the SourceEmbedding
```
class PPTEmbedding(SourceEmbedding):
    """ppt embedding for read ppt document."""

    def __init__(self, file_path, vector_store_config):
        """Initialize with pdf path."""
        super().__init__(file_path, vector_store_config)
        self.file_path = file_path
        self.vector_store_config = vector_store_config
```

implement read() and data_process()
read() method allows you to read data and split data into chunk
```
@register
    def read(self):
        """Load from ppt path."""
        loader = UnstructuredPowerPointLoader(self.file_path)
        textsplitter = SpacyTextSplitter(
            pipeline="zh_core_web_sm",
            chunk_size=CFG.KNOWLEDGE_CHUNK_SIZE,
            chunk_overlap=200,
        )
        return loader.load_and_split(textsplitter)
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

URL
==================================
url embedding can import PDF text into a vector knowledge base. The entire embedding process includes the read (loading data), data_process (data processing), and index_to_store (embedding to the vector database) methods.

inheriting the SourceEmbedding
```
class URLEmbedding(SourceEmbedding):
    """url embedding for read url document."""

        def __init__(
        self,
        file_path,
        vector_store_config,
        text_splitter: Optional[TextSplitter] = None,
    ):
        """Initialize url word path."""
        super().__init__(file_path, vector_store_config, text_splitter=None)
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.text_splitter = text_splitter or None
```

implement read() and data_process()
read() method allows you to read data and split data into chunk
```
@register
    def read(self):
        """Load from url path."""
        loader = WebBaseLoader(web_path=self.file_path)
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
            content = d.page_content.replace("\n", "")
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["!doctype", "meta"]):
                tag.extract()
            documents[i].page_content = soup.get_text()
            i += 1
        return documents
```

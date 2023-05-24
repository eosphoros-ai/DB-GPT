import os

from bs4 import BeautifulSoup
from langchain.document_loaders import TextLoader, markdown, PyPDFLoader
from langchain.embeddings import HuggingFaceEmbeddings

from pilot.configs.config import Config
from pilot.configs.model_config import DATASETS_DIR, KNOWLEDGE_CHUNK_SPLIT_SIZE
from pilot.source_embedding.chn_document_splitter import CHNDocumentSplitter
from pilot.source_embedding.csv_embedding import CSVEmbedding
from pilot.source_embedding.markdown_embedding import MarkdownEmbedding
from pilot.source_embedding.pdf_embedding import PDFEmbedding
import markdown

from pilot.vector_store.connector import VectorStoreConnector

CFG = Config()

class KnowledgeEmbedding:
    def __init__(self, file_path, model_name, vector_store_config, local_persist=True):
        """Initialize with Loader url, model_name, vector_store_config"""
        self.file_path = file_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config
        self.file_type = "default"
        self.embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
        self.vector_store_config["embeddings"] = self.embeddings
        self.local_persist = local_persist
        if not self.local_persist:
            self.knowledge_embedding_client = self.init_knowledge_embedding()

    def knowledge_embedding(self):
        self.knowledge_embedding_client.source_embedding()

    def knowledge_embedding_batch(self):
        self.knowledge_embedding_client.batch_embedding()

    def init_knowledge_embedding(self):
        if self.file_path.endswith(".pdf"):
            embedding = PDFEmbedding(file_path=self.file_path, model_name=self.model_name,
                                     vector_store_config=self.vector_store_config)
        elif self.file_path.endswith(".md"):
            embedding = MarkdownEmbedding(file_path=self.file_path, model_name=self.model_name, vector_store_config=self.vector_store_config)

        elif self.file_path.endswith(".csv"):
            embedding = CSVEmbedding(file_path=self.file_path, model_name=self.model_name,
                                     vector_store_config=self.vector_store_config)
        elif self.file_type == "default":
            embedding = MarkdownEmbedding(file_path=self.file_path, model_name=self.model_name, vector_store_config=self.vector_store_config)

        return embedding

    def similar_search(self, text, topk):
        return self.knowledge_embedding_client.similar_search(text, topk)

    def knowledge_persist_initialization(self, append_mode):
        documents = self._load_knownlege(self.file_path)
        self.vector_client = VectorStoreConnector(CFG.VECTOR_STORE_TYPE, self.vector_store_config)
        self.vector_client.load_document(documents)
        return self.vector_client

    def _load_knownlege(self, path):
        docments = []
        for root, _, files in os.walk(path, topdown=False):
            for file in files:
                filename = os.path.join(root, file)
                docs = self._load_file(filename)
                new_docs = []
                for doc in docs:
                    doc.metadata = {"source": doc.metadata["source"].replace(DATASETS_DIR, "")}
                    print("doc is embedding...", doc.metadata)
                    new_docs.append(doc)
                docments += new_docs
        return docments

    def _load_file(self, filename):
        if filename.lower().endswith(".md"):
            loader = TextLoader(filename)
            text_splitter = CHNDocumentSplitter(pdf=True, sentence_size=KNOWLEDGE_CHUNK_SPLIT_SIZE)
            docs = loader.load_and_split(text_splitter)
            i = 0
            for d in docs:
                content = markdown.markdown(d.page_content)
                soup = BeautifulSoup(content, 'html.parser')
                for tag in soup(['!doctype', 'meta', 'i.fa']):
                    tag.extract()
                docs[i].page_content = soup.get_text()
                docs[i].page_content = docs[i].page_content.replace("\n", " ")
                i += 1
        elif filename.lower().endswith(".pdf"):
            loader = PyPDFLoader(filename)
            textsplitter = CHNDocumentSplitter(pdf=True, sentence_size=KNOWLEDGE_CHUNK_SPLIT_SIZE)
            docs = loader.load_and_split(textsplitter)
            i = 0
            for d in docs:
                docs[i].page_content = d.page_content.replace("\n", " ").replace("�", "")
                i += 1
        else:
            loader = TextLoader(filename)
            text_splitor = CHNDocumentSplitter(sentence_size=KNOWLEDGE_CHUNK_SPLIT_SIZE)
            docs = loader.load_and_split(text_splitor)
        return docs
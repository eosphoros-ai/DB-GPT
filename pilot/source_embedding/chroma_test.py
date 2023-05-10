from langchain.document_loaders import UnstructuredFileLoader
from langchain.text_splitter import CharacterTextSplitter

from pilot import TextToVector

path="/Users/chenketing/Downloads/OceanBase-数据库-V4.1.0-OceanBase-介绍.pdf"


loader = UnstructuredFileLoader(path)
text_splitor = CharacterTextSplitter()
docs = loader.load_and_split(text_splitor)


# doc["vector"] = TextToVector.textToVector(doc["content"])[0]

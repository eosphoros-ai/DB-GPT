from langchain.embeddings.huggingface import HuggingFaceEmbeddings
import torch


device = "cuda" if torch.cuda.is_available() else "cpu"


class TextToVector:

    @staticmethod
    def textToVector(text):
        hfemb = HuggingFaceEmbeddings(model_name="/Users/chenketing/Desktop/project/all-MiniLM-L6-v2")
        return hfemb.embed_documents([text])

    @staticmethod
    def textlist_to_vector(textlist):
        hfemb = HuggingFaceEmbeddings(model_name="/Users/chenketing/Desktop/project/all-MiniLM-L6-v2")
        return hfemb.embed_documents(textlist)